"""Exploratory same-listing amenity/capacity combinations, with clustered uncertainty and FDR."""
from pathlib import Path
from itertools import combinations
import hashlib
import json
import shutil
import textwrap
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from processing.amenity_votes import PHYSICAL
from processing.plot_axes import discrete_axis

ROOT=Path(__file__).resolve().parents[1]

def run(root=ROOT):
    root=Path(root);out=root/'party_combination_analysis';plots=out/'plots'
    plots.mkdir(parents=True,exist_ok=True)
    source=root/'amenity_votes/data.js'
    data=json.loads(source.read_text(encoding='utf-8').removeprefix('window.AMENITY_VOTES=').removesuffix(';'))
    assert data['summary']['properties']>0 and data['summary']['citizen_only']
    audit_hash=hashlib.sha256((root/'processed_data/listing_matches/source_match_audit.csv').read_bytes()).hexdigest()
    assert data['summary']['source_hashes']['processed_data/listing_matches/source_match_audit.csv']==audit_hash,'Rebuild amenity data after match audit changes'
    all_properties=data['properties'];props=[p for p in all_properties if p['advertised_guests'] is not None]
    labels={f['id']:f['label'] for f in data['features']}
    # Spatially overlapping neighborhoods are one uncertainty cluster.
    parents=list(range(len(props)))
    def find(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    by_parcel={}
    for i,p in enumerate(props):
        for pin in [p['pin']]+p['neighbor_ids']:
            if pin in by_parcel:parents[find(i)]=find(by_parcel[pin])
            else:by_parcel[pin]=i
    clusters=np.array([find(i) for i in range(len(props))])
    cap=np.array([p['advertised_guests'] for p in props],float)
    base=pd.DataFrame(dict(intercept=1.,log_capacity=np.log1p(cap),owner=[float(p['permit_type']=='owner') for p in props],log_licenses=np.log1p([p['license_count'] for p in props])))
    masks={};candidate_count=0
    def add(features,evidence,cutoff=None):
        nonlocal candidate_count
        candidate_count+=1
        mask=np.array([any(all(f in l[evidence] for f in features) and (cutoff is None or (l['guests'] is not None and l['guests']>=cutoff)) for l in p['listings']) for p in props])
        if not features:mask=cap>=cutoff
        signature=np.packbits(mask).tobytes().hex()
        description=(' + '.join(labels[f] for f in features) if features else 'Guest capacity')+(f' + {cutoff}+ advertised guests' if features and cutoff is not None else f' {cutoff}+' if cutoff is not None else '')
        family='physical on-site' if evidence=='onsite' else 'positive description/amenity mentions'
        if signature not in masks:masks[signature]=dict(mask=mask,features=list(features),evidence=evidence,capacity_minimum=cutoff,label=description,family=family,aliases=[])
        masks[signature]['aliases'].append(family+': '+description)
    for evidence,features in [('onsite',sorted(PHYSICAL)),('mention',sorted(labels))]:
        for length in [1,2]:
            for pair in combinations(features,length):
                add(pair,evidence)
                for cutoff in [6,8,10,12]:add(pair,evidence,cutoff)
    for cutoff in [6,8,10,12]:add([], 'mention',cutoff)
    records=[];skipped=[];fitted={};outcome='Noise-party-disturbance'
    for index,(signature,candidate) in enumerate(masks.items()):
        indicator=candidate['mask'];n=int(indicator.sum());other=len(props)-n
        for scope in ['direct','combined']:
            y=np.array([p['counts'][scope][outcome] for p in props],float)
            exposure=np.array([data['years'][outcome]*(.59 if scope=='direct' else p['neighbor_count']+.59) for p in props])
            events=int(y[indicator].sum());other_events=int(y[~indicator].sum())
            support=dict(signature=signature,scope=scope,label=candidate['label'],family=candidate['family'],features=' | '.join(candidate['features']),evidence=candidate['evidence'],capacity_minimum=candidate['capacity_minimum'],properties=n,other_properties=other,calls=events,other_calls=other_events,
                positive_properties=int((y[indicator]>0).sum()),exposed_clusters=len(set(clusters[indicator])),total_clusters=len(set(clusters)))
            if n<15 or other<15 or events<8 or other_events<8 or support['positive_properties']<5 or int((y[~indicator]>0).sum())<5 or support['exposed_clusters']<8:
                skipped.append(dict(**support,status='insufficient properties/events/clusters'));continue
            x=base.copy();x['combination']=indicator.astype(float)
            if np.linalg.matrix_rank(x.to_numpy())<x.shape[1]:skipped.append(dict(**support,status='collinear with size/type controls'));continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    model=sm.GLM(y,x,family=sm.families.Poisson(),offset=np.log(exposure)).fit(maxiter=100,cov_type='cluster',cov_kwds={'groups':clusters})
                beta=float(model.params['combination']);se=float(model.bse['combination'])
                if not model.converged or not np.isfinite(beta+se) or se>5:raise ValueError('unstable estimate')
                record=dict(**support,status='estimated',adjusted_rate_ratio=float(np.exp(beta)),ci_low=float(np.exp(beta-1.96*se)),ci_high=float(np.exp(beta+1.96*se)),p_value=float(model.pvalues['combination']),
                    raw_rate_present=float(y[indicator].sum()/exposure[indicator].sum()),raw_rate_other=float(y[~indicator].sum()/exposure[~indicator].sum()),
                    same_listing=True,alias_count=len(candidate['aliases']))
                records.append(record);fitted[signature]=candidate
            except Exception as error:skipped.append(dict(**support,status='fit failed: '+str(error)))
        if (index+1)%100==0:print(f'Assessed {index+1}/{len(masks)} distinct exposure groups',flush=True)
    results=pd.DataFrame(records)
    assert len(results)>0
    results['q_fdr']=multipletests(results.p_value.to_numpy(),method='fdr_bh')[1]
    results['passes_fdr_05']=results.q_fdr.le(.05)&results.adjusted_rate_ratio.gt(1)
    results=results.sort_values(['q_fdr','ci_low','adjusted_rate_ratio'],ascending=[True,False,False])
    results.to_csv(out/'all_adjusted_combinations.csv',index=False)
    pd.DataFrame(skipped).to_csv(out/'insufficient_support_or_failed.csv',index=False)
    pd.DataFrame([dict(signature=s,label=c['label'],family=c['family'],aliases=' || '.join(c['aliases']),properties=int(c['mask'].sum())) for s,c in masks.items()]).to_csv(out/'candidate_masks_and_aliases.csv',index=False)
    # Top ten are review candidates, not a declaration that ten effects were established.
    direct=results[results.scope.eq('direct')&results.adjusted_rate_ratio.gt(1)].sort_values(['q_fdr','ci_low'],ascending=[True,False])
    top=direct.drop_duplicates('signature').head(10).copy();top.insert(0,'review_rank',range(1,len(top)+1))
    top.to_csv(out/'top_10_direct_candidates.csv',index=False)
    audits=[]
    for rank,(_,row) in enumerate(top.iterrows(),1):
        mask=fitted[row.signature]['mask'];y=np.array([p['counts']['direct'][outcome] for p in props],float)
        mean_yes=float(y[mask].mean()/data['years'][outcome]/.59);mean_no=float(y[~mask].mean()/data['years'][outcome]/.59)
        fig,ax=plt.subplots(figsize=(12,7));ax.bar(['Advertises condition','Other matched properties'],[mean_yes,mean_no],color=['#126d78','#91a7b7'])
        category_reference=sum(data['baselines'][k] for k in ['Noise complaints','Loud party','Disturbance / nuisance'])
        ax.axhline(category_reference,color='#875d28',linestyle='--',label=f'All residential: same noise/party/disturbance types ({category_reference:.3f}/year)')
        ax.axhline(data['baselines']['All calls'],color='#64748b',linestyle=':',label=f'All residential: ALL citizen call types ({data["baselines"]["All calls"]:.3f}/year; context only)')
        for i,(value,count,events) in enumerate([(mean_yes,int(mask.sum()),int(y[mask].sum())),(mean_no,int((~mask).sum()),int(y[~mask].sum()))]):ax.annotate(f'{count} properties; {events} calls',(i,value),xytext=(0,8),textcoords='offset points',ha='center')
        ax.set(title='Review candidate '+str(rank)+': '+row.label,xlabel='Same-listing advertised condition',ylabel='Direct citizen noise/party/disturbance calls per estimated occupied year',ylim=(0,None));ax.margins(y=.25);ax.legend()
        note=f'Adjusted rate ratio {row.adjusted_rate_ratio:.2f} (clustered 95% interval {row.ci_low:.2f}-{row.ci_high:.2f}); multiple-testing q={row.q_fdr:.3f}. Bars count only noise/party/disturbance calls. Both reference lines use all 4,806 eligible residential parcels; the ALL-call line is not a like-for-like outcome comparison. Adjusted model controls log advertised capacity, owner type and log license count. 59% scenario; full available period. Exploratory, not cause or demonstrated synergy.'
        fig.text(.07,.02,'\n'.join(textwrap.wrap(note,width=150)),fontsize=8);fig.tight_layout(rect=(0,.15,1,1))
        for extension in ['png','svg']:fig.savefig(plots/f'{rank:02d}__candidate.{extension}',dpi=140)
        plt.close(fig)
        for i,p in enumerate(props):
            if mask[i]:audits.append(dict(candidate_rank=rank,condition=row.label,pin=p['pin'],address=p['address'],capacity=p['advertised_guests'],approved_guests=p['approved_guests'],direct_calls=p['counts']['direct'][outcome],combined_calls=p['counts']['combined'][outcome],listing_urls=' | '.join(l['url'] for l in p['listings'])))
    pd.DataFrame(audits).to_csv(out/'candidate_properties_and_calls.csv',index=False)
    # Test whether top two-feature conditions show extra interaction beyond their individual features.
    synergy=[]
    for signature in top.signature:
        c=fitted[signature]
        if len(c['features'])!=2:continue
        a,b=c['features'];evidence=c['evidence']
        aa=np.array([any(a in l[evidence] for l in p['listings']) for p in props]);bb=np.array([any(b in l[evidence] for l in p['listings']) for p in props]);yy=np.array([p['counts']['direct'][outcome] for p in props],float)
        cells=[aa&bb,aa&~bb,~aa&bb,~aa&~bb]
        row=dict(label=c['label'],cell_properties=' | '.join(str(int(cell.sum())) for cell in cells),status='insufficient four-cell support')
        if c['capacity_minimum'] is not None:
            row['status']='capacity-conditioned pattern; not a two-feature synergy test';synergy.append(row);continue
        if not np.array_equal(aa&bb,c['mask']):
            row['status']='cross-listing pairs differ from same-listing pairs; synergy not estimated';synergy.append(row);continue
        if all(cell.sum()>=10 and yy[cell].sum()>=3 for cell in cells):
            xx=base.copy();xx['A']=aa.astype(float);xx['B']=bb.astype(float);xx['interaction']=(aa&bb).astype(float)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore');m=sm.GLM(yy,xx,family=sm.families.Poisson(),offset=np.repeat(np.log(data['years'][outcome]*.59),len(yy))).fit(cov_type='cluster',cov_kwds={'groups':clusters})
                row.update(status='estimated',extra_interaction_rate_ratio=float(np.exp(m.params['interaction'])),p_value=float(m.pvalues['interaction']))
            except Exception as error:row['status']='failed: '+str(error)
        synergy.append(row)
    pd.DataFrame(synergy).to_csv(out/'pair_synergy_support.csv',index=False)
    old=pd.read_csv(root/'plots_with_trends_with_averages/increasing_plot_rankings.csv').drop_duplicates('data_signature').drop_duplicates('plot').head(10)
    size_dir=out/'top_10_size_trends';size_dir.mkdir(exist_ok=True)
    for rank,(_,r) in enumerate(old.iterrows(),1):
        for ext in ['png','svg']:shutil.copy2(root/'plots_with_trends_with_averages'/(r['plot']+'.'+ext),size_dir/(f'{rank:02d}__'+r['plot']+'.'+ext))
    summary=dict(validated_properties=len(all_properties),properties_with_advertised_capacity=len(props),direct_target_calls=sum(p['counts']['direct'][outcome] for p in all_properties),
        candidate_descriptions=candidate_count,distinct_property_groups=len(masks),fitted_tests=len(results),fdr05_increases=int(results.passes_fdr_05.sum()),top_direct_candidates=len(top),
        uncertainty_clusters=len(set(clusters)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        policy='Citizen initiation only; patrol excluded. Noise/loud-party/disturbance outcomes. Same-listing features and capacity. Clustered uncertainty; FDR across fitted direct and neighborhood tests.')
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    size_table=['| Rank | Size measure | Call type | Cohort | Parcels | Calls | Plot |','|---:|---|---|---|---:|---:|---|']
    names={'bedrooms':'Advertised bedrooms','guests':'Advertised guests','licensed_bedrooms':'Licensed bedrooms','approved_guests':'Approved guest capacity'}
    for rank,(_,r) in enumerate(old.iterrows(),1):
        parts=r['plot'].split('__');size_table.append(f"| {rank} | {names.get(parts[2],parts[2])} | {r.category} | {'Matched Airbnb' if parts[1]=='matched_airbnb' else 'All covered licenses with known size'} | {r.parcels} | {r.category_events:.0f} | [View](top_10_size_trends/{rank:02d}__{r['plot']}.png) |")
    text=['# Corrected size and party-feature associations','',f"{summary['validated_properties']} source-validated matched parcels, including zeros. {summary['direct_target_calls']} direct noise/loud-party/disturbance calls; only {len(props)} parcels have known advertised capacity for modeling.",'',
        'These are recorded-address citizen calls, not confirmed crimes, guest responsibility or verified 911 origin. Medical and other unrelated categories are not counted in this primary outcome. Direct and combined neighborhood results are separate. The main available period is January 1, 2024-October 16, 2026; 59% adjusts only focal rental exposure, not neighbors. The later source remains a retained/filtered extract.','',
        '## Top ten size plots','', '[Open the copied size-trend plots](top_10_size_trends/) or [the interactive source-property explorer](../top_correlations/index.html). These rank supported exact-size group-mean rises, not causal effects or individual-property explained variance. All ten selected series are non-owner-occupied.','',*size_table,'',
        '## Top ten combination review candidates','',f"Search considered {candidate_count} descriptions, collapsed to {len(masks)} distinct property groups. {len(results)} direct/neighborhood tests passed minimum support and were fitted. {summary['fdr05_increases']} increases passed the 5% false-discovery screen. All ten below remain exploratory review candidates; higher joint rates do not establish extra synergy.",'',
        '| Rank | Condition | Properties | Calls | Adjusted ratio | Clustered 95% interval | FDR q |','|---:|---|---:|---:|---:|---:|---:|']
    for _,r in top.iterrows():text.append(f"| {r.review_rank} | [{r.label}](plots/{r.review_rank:02d}__candidate.png) | {r.properties} | {r.calls} | {r.adjusted_rate_ratio:.2f} | {r.ci_low:.2f}-{r.ci_high:.2f} | {r.q_fdr:.3f} |")
    text+=['','[Property and Airbnb links behind each candidate](candidate_properties_and_calls.csv) · [All adjusted results](all_adjusted_combinations.csv) · [Unsupported/failed conditions](insufficient_support_or_failed.csv) · [Interaction support](pair_synergy_support.csv)','',
        '## Method and limits','',
        'Physical on-site evidence and positive description/party-language evidence are declared separate families. Each condition must occur in one listing; a capacity cutoff must apply to that same listing. Each parcel is counted once. Identical exposed-property groups are tested once, retaining their aliases. Broad party words are not physical amenities.','',
        'Each binary condition is tested with a Poisson model, controlling log(1 + advertised capacity), owner-occupied permit type and log(1 + license count), using an exposure offset. Combined-neighbor counts use the eligible neighbor count plus 0.59 focal rental. Uncertainty clusters connect neighborhoods sharing any parcel. Minimum support: 15 exposed and 15 comparison parcels, 8 events and 5 positive-call parcels on each side, and 8 exposed spatial clusters. Controls do not remove all location or reporting confounding.','',
        'Benjamini-Hochberg false-discovery correction includes every fitted unique condition across both scopes. Large searches can create impressive accidental ratios; do not rank by raw votes or take the top row as established fact. Pair interaction tests require adequate observations in all four presence/absence cells. Sparse combinations are flagged rather than forced.','',
        'This data set is small enough for CPU analysis. CUDA memory or overnight computation cannot repair sparse outcomes, missing coverage or uncertain source matches. Rebuild with `python -m processing.party_combination_analysis`.']
    (out/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
    return summary

if __name__=='__main__':run()
