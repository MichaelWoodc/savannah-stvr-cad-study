"""Reproduce the final feature set for direct/neighborhood and explicit CAD call groups."""
from pathlib import Path
import json,re,warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from processing.citizen_only import select
from processing.expanded_associations import forest

ROOT=Path(__file__).resolve().parents[1]

def run():
    out=ROOT/'final/call_groups';out.mkdir(exist_ok=True)
    features=pd.read_csv(ROOT/'final/all__advertised_guests__combined__all_calls__all_features__linear.csv')[['feature','label','family']]
    props=pd.read_csv(ROOT/'adjusted_association_plots/property_feature_call_audit.csv',dtype={'pin':str})
    props=props[props.advertised_guests.notna()&props.advertised_guests.gt(0)].copy()
    data=json.loads((ROOT/'amenity_votes/data.js').read_text(encoding='utf-8').split('=',1)[1].rstrip(';'))
    audit=json.loads((ROOT/'listing_match_validation.js').read_text(encoding='utf-8').split('=',1)[1].rstrip(';'))
    assert data['summary']['source_hashes']['processed_data/listing_matches/source_match_audit.csv']==audit['audit_sha256']
    neighborhoods={p['pin']:[p['pin'],*p['neighbor_ids']] for p in data['properties']}
    calls=select(pd.read_csv(ROOT/'processed_data/full_period_calls/combined_calls.csv',dtype=str).fillna(''))
    assert calls.number.is_unique
    violent_categories={'Assaults / stabbings','Fights / physical disturbances','Robbery / holdup / abduction','Sexual offenses'}
    calls['nuisance']=calls.type.str.contains(r'NOISE|LOUD PARTY',case=False,regex=True)|calls.category.eq('Disturbance / nuisance')
    calls['violence_sex']=calls.category.isin(violent_categories)|calls.type.str.contains(r'\bSHOOTING\b|\bHOMICIDE\b|\bMURDER\b',case=False,regex=True)|(calls.category.eq('Domestic disturbances')&calls.type.str.contains(r'CHOKED|INJURY',case=False,regex=True))
    calls['all_calls']=True
    calls.groupby(['category','type','nuisance','violence_sex']).size().rename('calls').reset_index().to_csv(out/'call_type_definitions.csv',index=False)
    clusters=pd.read_csv(ROOT/'amenity_votes/validation_groups.csv',dtype={'pin':str}).set_index('pin').validation_group
    years=data['years']['All calls'];rows=[];records=[];ledger=[]
    names={'all_calls':'All citizen calls','nuisance':'Noise, loud party and nuisance calls','violence_sex':'Violence / sexual-offense reports'}
    for scope in ['direct','combined']:
      for group in names:
        counts={}
        for p in props.itertuples():
            eligible=[p.pin] if scope=='direct' else neighborhoods[p.pin]
            matching=calls[calls.pin.isin(eligible)&calls[group]]
            counts[p.pin]=len(matching)
            ledger.extend(dict(scope=scope,group=group,focal_pin=p.pin,recorded_pin=c.pin,number=c.number,date=c.date,type=c.type,category=c.category,side='direct' if c.pin==p.pin else 'neighbor') for c in matching.itertuples())
        y=props.pin.map(counts).astype(float)
        if group in ['all_calls','nuisance']:
            old=props[scope+'_'+('All calls' if group=='all_calls' else 'Noise-party-disturbance')]
            assert np.array_equal(y.to_numpy(),old.to_numpy()),(scope,group)
        exposure=years*props[scope+'_exposure']
        for f in features.itertuples():
            present=props[f.feature].eq(1)
            row=dict(scope=scope,group=group,feature=f.feature,label=f.label,family=f.family,properties=len(props),events=int(y.sum()),present_properties=int(present.sum()),absent_properties=int((~present).sum()),present_calls=int(y[present].sum()),absent_calls=int(y[~present].sum()),adjusted_rate_ratio=np.nan,ci_low=np.nan,ci_high=np.nan,p_value=np.nan,status='insufficient support')
            if min(present.sum(),(~present).sum())>=10 and min(y[present].sum(),y[~present].sum())>=3 and y.sum()>=20:
                x=pd.DataFrame(dict(intercept=1.,feature=props[f.feature].astype(float),log_capacity=np.log1p(props.advertised_guests),log_license_count=np.log1p(props.license_count),owner=props.permit_type.eq('owner').astype(float)),index=props.index)
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore');m=sm.GLM(y,x,family=sm.families.Poisson(),offset=np.log(exposure)).fit(cov_type='cluster',cov_kwds={'groups':props.pin.map(clusters)},maxiter=100)
                    beta=float(m.params['feature']);se=float(m.bse['feature'])
                    if not m.converged or not np.isfinite(beta+se) or se>2.5:raise ValueError('unstable estimate')
                    row.update(status='estimated',adjusted_rate_ratio=np.exp(beta),ci_low=np.exp(beta-1.96*se),ci_high=np.exp(beta+1.96*se),p_value=float(m.pvalues['feature']))
                except Exception as error:row['status']=str(error)
            records.append(row)
        rows.extend(dict(scope=scope,group=group,pin=p.pin,address=p.address,calls=counts[p.pin],exposure_years=float(exposure.loc[p.Index]),advertised_guests=p.advertised_guests,permit_type=p.permit_type,urls=p.urls) for p in props.itertuples())
    result=pd.DataFrame(records);result['q_fdr']=np.nan;valid=result.p_value.notna()
    result.loc[valid,'q_fdr']=multipletests(result.loc[valid,'p_value'],method='fdr_bh')[1]
    result.to_csv(out/'all_models.csv',index=False);pd.DataFrame(rows).to_csv(out/'property_counts.csv',index=False);pd.DataFrame(ledger).to_csv(out/'call_memberships.csv',index=False)
    manifest=[]
    for (scope,group),part in result.groupby(['scope','group']):
        stem=scope+'__'+group;part.to_csv(out/(stem+'.csv'),index=False)
        title=names[group]+' | '+('direct property only' if scope=='direct' else 'property and touching neighbors')
        for scale in ['linear','log']:
            name=stem+'__'+scale;forest(part,out/name,title,'',linear=scale=='linear');manifest.append(dict(plot=name+'.png',svg=name+'.svg',csv=stem+'.csv',scope=scope,group=group,scale=scale))
    pd.DataFrame(manifest).to_csv(out/'manifest.csv',index=False)
    summary=dict(properties=len(props),years=years,estimated_models=int(valid.sum()),plots=len(manifest),counts=pd.DataFrame(rows).groupby(['scope','group']).calls.sum().to_dict())
    summary['counts']={scope+' / '+group:int(n) for (scope,group),n in summary['counts'].items()}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'README.md').write_text('''# Final call-group forest plots

Three outcomes, each with direct-only and property-plus-touching-neighbor versions, in regular integer-tick and logarithmic scales. Footer-free PNG and SVG, with paired model CSVs. Original final features are retained once each. Sparse features display without an estimate.

All calls are citizen-initiated and retain the existing patrol/proactive exclusions. Nuisance includes noise, loud-party and disturbance/nuisance labels; it excludes parking. Violence/sex includes assault/stabbing, physical fights, robbery/holdup/abduction, sexual-offense labels (including indecency/lewdness and pornography), shooting/homicide/murder labels, and domestic choking/injury labels. Undifferentiated or verbal domestic disputes, threats/harassment, burglary, medical calls, ShotSpotter and heard-only gunshots do not enter this restricted group. These are dispatch reports, not confirmed crimes or evidence of guest responsibility. call_type_definitions.csv records the exact included/excluded types.

Models keep all 472 matched parcels with known positive advertised capacity, including zeros. Each feature is fitted separately with advertised capacity, owner permit type and license-count controls. Exposure is the full observed period with a 59% focal rental scenario; neighboring parcels retain calendar exposure. Spatially clustered 95% intervals account for overlapping neighborhoods. Minimum support: 10 properties and 3 events on each side, with 20 events total. q values correct all estimated models in this six-comparison set. These q values therefore differ from the earlier broader search even when estimates coincide. Counts with neighbors are memberships and may overlap between focal rentals. They are not regional unique-call totals. No causal conclusion is established.

property_counts.csv includes zero-call rows; call_memberships.csv links each count to its original call number and parcel. Rebuild with `python -m processing.final_call_groups`.
''',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':run()
