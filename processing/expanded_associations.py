"""Individual-feature adjusted association forests, in logarithmic and integer linear scales."""
from pathlib import Path
import hashlib,json,re,textwrap,warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator,StrMethodFormatter

ROOT=Path(__file__).resolve().parents[1]
KEYWORDS={
 'bachelor':r'\b(?:bachelor|batchelor|bachelors)\b',
 'bachelorette':r'\b(?:bachelorette|batchelorette|bachelorettes|hen party)\b',
 'engagement':r'\b(?:engagement|engaged|proposal)\b',
 'wedding':r'\b(?:wedding|weddings|bridal|newlyweds)\b',
 'pool_table':r'\b(?:pool table|billiards?)\b',
 'swimming_pool':r'\bpool\b(?!\s+table)|\bswimming\b',
 'hot_tub':r'\bhot[ -]?tub\b',
 'jacuzzi':r'\bjacuzzi\b'}
EVENTS={'bachelor','bachelorette','engagement','wedding'}
NEGATIVE=r'\b(?:no|not|prohibited|forbidden|unavailable|banned|disallowed|cannot|never)\b'
NEARBY=r'\b(?:nearby|walk to|walking distance|minutes? away|blocks? away|short drive|off[ -]site)\b'
AFFIRM=r'\b(?:welcome|welcomes|hosting|host|celebrate|celebrating|celebration|ideal|perfect|great|suitable|suited|designed|accommodate|enjoy|getaway|retreat|destination)\b'

def display_label(label):
    label=re.sub(r'\s*\(positive mention\)| positive mention$', '', str(label),flags=re.I)
    return re.sub(r' invitation$', ' events',label,flags=re.I)

def keyword_rows(part,skipped):
    context=part.iloc[0];chart=part[part.family.eq('keywords')].copy()
    missing=set('keyword_'+k for k in KEYWORDS)-set(chart.feature)
    for feature in sorted(missing):
        rows=skipped[skipped.feature.eq(feature)]
        for key in ['cohort','capacity_control','scope','outcome']:rows=rows[rows[key].eq(context[key])]
        if rows.empty:continue
        row=rows.iloc[0].to_dict();row.update(adjusted_rate_ratio=np.nan,ci_low=np.nan,ci_high=np.nan,q_fdr=np.nan)
        chart=pd.concat([chart,pd.DataFrame([row])],ignore_index=True)
    return chart

def forest(part,path,title,note,linear=False):
    part=part.sort_values('adjusted_rate_ratio');fig,ax=plt.subplots(figsize=(13,max(6,2.8+len(part)*.36)))
    yy=np.arange(len(part));ratio=part.adjusted_rate_ratio
    ax.errorbar(ratio,yy,xerr=[ratio-part.ci_low,part.ci_high-ratio],fmt='o',capsize=3,color='#2563eb',label='Adjusted rate ratio with 95% interval')
    ax.axvline(1,color='#64748b',linestyle='--',label='No modeled association: ratio 1')
    ax.set_yticks(yy,[f'{display_label(r.label)}  [n={r.present_properties}; '+(f'q={r.q_fdr:.3f}]' if np.isfinite(r.q_fdr) else 'not estimated]') if 'q_fdr' in part else str(r.feature).replace('_',' ') for r in part.itertuples()])
    for i,r in enumerate(part.itertuples()):
        if not np.isfinite(r.adjusted_rate_ratio):ax.text(1,i,'  insufficient support',va='center',fontsize=8,color='#64748b')
    ax.set_ylim(-.6,len(part)-.4)
    if linear:
        ax.set_xlim(0,max(2,float(part.ci_high.max())*1.04));ax.xaxis.set_major_locator(MaxNLocator(nbins=8,integer=True));ax.xaxis.set_major_formatter(StrMethodFormatter('{x:.0f}'))
    else:ax.set_xscale('log')
    ax.set(title=title,xlabel='Adjusted call-rate ratio')
    ax.grid(axis='x',alpha=.2);ax.legend(fontsize=8)
    if note:
        fig.text(.02,.015,'\n'.join(textwrap.wrap(note,155)),fontsize=8,va='bottom')
        fig.tight_layout(rect=(0,.16,1,1))
    else:
        fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(path.with_suffix('.'+ext),dpi=145)
    plt.close(fig)

def run():
    out=ROOT/'adjusted_association_plots';out.mkdir(exist_ok=True)
    data=json.loads((ROOT/'amenity_votes/data.js').read_text(encoding='utf-8').split('=',1)[1].rstrip(';'))
    audit=json.loads((ROOT/'listing_match_validation.js').read_text(encoding='utf-8').split('=',1)[1].rstrip(';'))
    assert data['summary']['source_hashes']['processed_data/listing_matches/source_match_audit.csv']==audit['audit_sha256']
    keyword_by_listing={};evidence=[]
    verified=pd.read_csv(ROOT/'processed_data/listing_matches/verified_listing_matches.csv',dtype=str)
    for r in verified.itertuples():
        raw=(ROOT/'amenity_word_bank/source_cache'/(r.listing_id+'.txt')).read_bytes();assert hashlib.sha256(raw).hexdigest()==r.details_sha256
        flags=set();section=''
        for line_number,line in enumerate(raw.decode('utf-8-sig').splitlines(),1):
            if line.startswith('==='):section=line.strip('= ').upper();continue
            if section not in ('FULL DESCRIPTION','AMENITIES'):continue
            for sentence in re.split(r'(?<=[.!?])\s+',line):
                for key,pattern in KEYWORDS.items():
                    if not re.search(pattern,sentence,re.I):continue
                    reason='prohibition / negation' if re.search(NEGATIVE,sentence,re.I) else 'nearby / off-site' if re.search(NEARBY,sentence,re.I) else 'no affirmative event marketing' if key in EVENTS and not re.search(AFFIRM,sentence,re.I) else 'included positive mention'
                    if reason=='included positive mention':flags.add(key)
                    evidence.append(dict(listing_id=r.listing_id,keyword=key,included=reason=='included positive mention',reason=reason,section=section,line=line_number,text=sentence,sha256=r.details_sha256))
        keyword_by_listing[r.listing_id]=flags
    rows=[];labels={};family={}
    for p in data['properties']:
        row={k:p[k] for k in ['pin','address','permit_type','license_count','advertised_guests','approved_guests']}
        row['urls']=' | '.join(l['url'] for l in p['listings'])
        for f in data['features']:
            key='mention_'+f['id'];row[key]=int(any(f['id'] in l['mention'] for l in p['listings']));labels[key]=f['label'];family[key]='amenities'
        flags=set().union(*(keyword_by_listing[l['listing_id']] for l in p['listings']))
        for word in KEYWORDS:
            key='keyword_'+word;row[key]=int(word in flags);labels[key]=word.replace('_',' ').title()+(' events' if word in EVENTS else '');family[key]='keywords'
        for scope in ['direct','combined']:
            for outcome in data['outcomes']:
                row[scope+'_'+outcome]=p['counts'][scope][outcome]
            row[scope+'_exposure']=.59+(p['neighbor_count'] if scope=='combined' else 0)
        rows.append(row)
    frame=pd.DataFrame(rows);assert frame.pin.is_unique
    clusters=pd.read_csv(ROOT/'amenity_votes/validation_groups.csv',dtype={'pin':str}).set_index('pin').validation_group
    results=[];skipped=[]
    for cohort in ['all','owner','non_owner']:
      for capacity in ['advertised_guests','approved_guests']:
       part=frame[(frame.permit_type.eq(cohort) if cohort!='all' else np.ones(len(frame),bool))&frame[capacity].notna()&frame[capacity].gt(0)].copy()
       for scope in ['direct','combined']:
        for outcome in data['outcomes']:
         y=part[scope+'_'+outcome].astype(float)
         for feature in labels:
          present=part[feature].eq(1)
          info=dict(cohort=cohort,capacity_control=capacity,scope=scope,outcome=outcome,feature=feature,label=labels[feature],family=family[feature],properties=len(part),events=int(y.sum()),present_properties=int(present.sum()),absent_properties=int((~present).sum()),present_calls=int(y[present].sum()),absent_calls=int(y[~present].sum()))
          if min(present.sum(),(~present).sum())<10 or min(y[present].sum(),y[~present].sum())<3 or y.sum()<20:
            skipped.append(dict(**info,status='insufficient support'));continue
          x=pd.DataFrame(dict(intercept=1.,feature=part[feature].astype(float),log_capacity=np.log1p(part[capacity]),log_license_count=np.log1p(part.license_count)),index=part.index)
          if cohort=='all':x['owner']=part.permit_type.eq('owner').astype(float)
          try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore');model=sm.GLM(y,x,family=sm.families.Poisson(),offset=np.log(data['years'][outcome]*part[scope+'_exposure'])).fit(cov_type='cluster',cov_kwds={'groups':part.pin.map(clusters)},maxiter=100)
            beta=float(model.params['feature']);se=float(model.bse['feature'])
            if not model.converged or not np.isfinite(beta+se) or se>2.5:raise ValueError('unstable estimate')
            results.append(dict(**info,adjusted_rate_ratio=np.exp(beta),ci_low=np.exp(beta-1.96*se),ci_high=np.exp(beta+1.96*se),p_value=float(model.pvalues['feature'])))
          except Exception as e:skipped.append(dict(**info,status=str(e)))
    result=pd.DataFrame(results);result['q_fdr']=multipletests(result.p_value,method='fdr_bh')[1]
    result.to_csv(out/'all_adjusted_associations.csv',index=False);pd.DataFrame(skipped).to_csv(out/'insufficient_support.csv',index=False)
    pd.DataFrame(evidence).to_csv(out/'keyword_source_evidence.csv',index=False);frame.to_csv(out/'property_feature_call_audit.csv',index=False)
    manifest=[]
    for keys,part in result.groupby(['cohort','capacity_control','scope','outcome']):
      cohort,capacity,scope,outcome=keys
      for subset in ['all_features','invitation_and_leisure_keywords']:
        chart=part if subset=='all_features' else keyword_rows(part,pd.DataFrame(skipped))
        if chart.empty:continue
        title=f'{outcome} | {scope} | {cohort.replace("_"," ")} permits | control: {capacity.replace("_"," ")}'
        years=data['years'][outcome];calendar=data['baselines'][outcome]
        note=f'Citizen calls only, patrol excluded. One binary feature per Poisson model; controls log(1 + capacity), log(1 + licenses), plus owner status in pooled models. Spatially clustered 95% intervals; q corrects all {len(result)} fitted comparisons. {years:.3f} observed years; rental exposure 59%, neighbors calendar exposure. Same-category residential average {calendar:.3f}/year across 4,806 parcels.'
        # Rate-ratio plots have a ratio-one reference, not a call-rate average line.
        note=note+' A residential call-rate average is not a ratio and cannot be placed on this axis. All zero-call parcels remain. Features are parcel-level presence across listings; maximum advertised capacity is a parcel proxy. No causal claim. Sparse features omitted.'
        name='__'.join([cohort,capacity,scope,re.sub(r'[^a-z0-9]+','_',outcome.lower()).strip('_'),subset])
        chart.to_csv(out/(name+'.csv'),index=False)
        for linear in [False,True]:
            stem=name+('__linear' if linear else '__log');forest(chart,out/stem,title,note,linear)
            manifest.append(dict(plot=stem+'.png',svg=stem+'.svg',csv=name+'.csv',cohort=cohort,capacity=capacity,scope=scope,outcome=outcome,subset=subset,scale='linear' if linear else 'log',features=len(chart)))
      print('Plotted',keys,flush=True)
    pd.DataFrame(manifest).to_csv(out/'manifest.csv',index=False)
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><title>Expanded adjusted associations</title><link rel="stylesheet" href="../amenity_votes/style.css"><main><h1>Individual amenities and invitation keywords, adjusted for occupancy</h1><p>Each image is a single forest plot, with 95% intervals and a no-association line at ratio 1. Both logarithmic and integer-tick linear scales are available. Zero-call parcels are included. Associations are exploratory; q values correct the fitted search. No on-site amenity count is used.</p><label>Filter plot names<input id="search" type="search" placeholder="wedding, keywords, non_owner, linear..."></label><p><a href="keyword_source_evidence.csv">Included and rejected source excerpts</a> | <a href="all_adjusted_associations.csv">All estimates</a> | <a href="insufficient_support.csv">Sparse / failed estimates</a></p><ul id="plots">']
    for r in manifest:
        words=' '.join(KEYWORDS).replace('_',' ') if r['subset']=='invitation_and_leisure_keywords' else ''
        html.append(f'<li data-keywords="{words}"><a href="{r["plot"]}">{r["plot"]}</a> | <a href="{r["svg"]}">SVG</a> | <a href="{r["csv"]}">data</a></li>')
    html.append('</ul></main><script>document.getElementById("search").addEventListener("input",e=>document.querySelectorAll("#plots li").forEach(li=>li.hidden=!(li.textContent+" "+(li.dataset.keywords||"")).toLowerCase().includes(e.target.value.toLowerCase())));</script><script src="../page-preferences.js"></script></html>')
    (out/'index.html').write_text(''.join(html),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(dict(properties=len(frame),models=len(result),plots=len(manifest),source_audit=audit['audit_sha256']),indent=2))
    print('Finished',len(manifest),'plots;',len(result),'models',flush=True)

if __name__=='__main__':run()
