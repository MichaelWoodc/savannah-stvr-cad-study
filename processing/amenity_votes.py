"""Auditable amenity call votes, residential-baseline subtraction and exposure models."""
from pathlib import Path
import hashlib
import json
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from processing.citizen_only import select as citizen_only

ROOT=Path(__file__).resolve().parents[1]
PHYSICAL={'hot_tub','pool','grill','fire_pit','sound_system','bar','outdoor_dining','patio','yard','games','table_tennis','rooftop','pool_table','cornhole','karaoke'}
SCOPES=['direct','neighbors','combined']

def run(root=ROOT):
    root=Path(root);out=root/'amenity_votes';out.mkdir(exist_ok=True)
    report=json.loads((root/'direct_listing_calls/report_data.js').read_text(encoding='utf-8').removeprefix('window.DIRECT_REPORT=').removesuffix(';'))
    controls=report['controls'];coverage=report['summary']['call_coverage']
    study=json.loads((root/'data.js').read_text(encoding='utf-8-sig').split('=',1)[1].strip().rstrip(';'))
    labels={f['id']:f['label'] for f in study['listingScreen']['features']}
    calls=citizen_only(pd.read_csv(root/'processed_data/full_period_calls/combined_calls.csv',dtype=str).fillna(''))
    assert calls.number.is_unique
    def classify(r):
        t=r.type.upper()
        if 'PARKING COMPLAINT' in t:return 'Parking complaints'
        if 'LOUD PARTY' in t:return 'Loud party'
        if 'NOISE' in t:return 'Noise complaints'
        if r.category=='Disturbance / nuisance':return 'Disturbance / nuisance'
        return 'Other'
    calls['outcome']=[classify(r) for r in calls.itertuples()]
    outcomes=['All calls','Noise-party-disturbance','Parking complaints','Noise complaints','Loud party','Disturbance / nuisance']
    years={k:coverage['parking_exposure_years'] if k=='Parking complaints' else coverage['exposure_years'] for k in outcomes}
    relevant=lambda data,k: data if k=='All calls' else data[data.outcome.isin(['Noise complaints','Loud party','Disturbance / nuisance'])] if k=='Noise-party-disturbance' else data[data.outcome.eq(k)]
    eligible=set(pd.read_csv(root/'parcel_rates.csv',dtype=str).pin)
    canonical={p.replace(' ',''):p for p in eligible}
    assert set(calls.pin)<=eligible
    baselines={k:len(relevant(calls,k))/len(eligible)/years[k] for k in outcomes}
    focal=[p for p in controls['properties'] if p['listings']]
    links=pd.read_csv(root/'neighborhood_occupancy_plots/all_direct_boundary_links.csv',dtype=str)
    links['focal']=links.focal_pin.map(canonical);links['neighbor']=links.neighbor_pin.map(canonical)
    excluded=links[links.neighbor.isna() & links.focal.isin([p['pin'] for p in focal])]
    excluded.to_csv(out/'neighbors_outside_fixed_residential_coverage.csv',index=False)
    links=links[links.focal.isin([p['pin'] for p in focal])&links.neighbor.notna()].drop_duplicates(['focal','neighbor'])
    links.to_csv(out/'included_neighbor_links.csv',index=False)
    property_records=[];listing_scores=[];memberships=[];vote_records=[]
    for p in focal:
        neighbors=sorted(set(links.loc[links.focal.eq(p['pin']),'neighbor'])-{p['pin']})
        own=calls[calls.pin.eq(p['pin'])];near=calls[calls.pin.isin(neighbors)]
        combined=pd.concat([own,near],ignore_index=True).drop_duplicates('number')
        positive=sorted(set(k for l in p['listings'] for k in l['mention']))
        onsite=sorted(set(k for l in p['listings'] for k in l['onsite']))
        group_counts={scope:{k:len(relevant(data,k)) for k in outcomes} for scope,data in [('direct',own),('neighbors',near),('combined',combined)]}
        assert group_counts['direct']['All calls']==p['counts']['citizen']['All calls']
        assert all(group_counts['combined'][k]==group_counts['direct'][k]+group_counts['neighbors'][k] for k in outcomes)
        max_score=max(len(set(l['mention'])) for l in p['listings'])
        onsite_score=max(len(set(l['onsite'])&PHYSICAL) for l in p['listings'])
        guests=[l['guests'] for l in p['listings'] if l['guests'] is not None]
        bedrooms=[l['bedrooms'] for l in p['listings'] if l['bedrooms'] is not None]
        row=dict(pin=p['pin'],address=p['address'],permit_type=p['permit_type'],license_count=p['license_count'],
            approved_guests=p['approved_guests'],licensed_bedrooms=p['licensed_bedrooms'],
            advertised_guests=max(guests) if guests else None,advertised_bedrooms=max(bedrooms) if bedrooms else None,
            neighbor_ids=neighbors,neighbor_count=len(neighbors),property_count=1+len(neighbors),
            advertised_features=positive,onsite_features=onsite,advertised_feature_union_count=len(positive),
            max_single_listing_feature_count=max_score,max_single_listing_physical_count=onsite_score,
            counts=group_counts,listings=p['listings'],
            calls=[dict(number=r.number,date=r.date,type=r.type,outcome=r.outcome,recorded_address=r.address,
                recorded_pin=r.pin,side='direct' if r.pin==p['pin'] else 'neighbors') for r in combined.itertuples()])
        property_records.append(row)
        for l in p['listings']:
            listing_scores.append(dict(pin=p['pin'],listing_id=l['listing_id'],url=l['url'],title=l['title'],advertised_guests=l['guests'],
                approved_guests=l['approved_guests'],advertised_feature_count=len(set(l['mention'])),
                physical_onsite_count=len(set(l['onsite'])&PHYSICAL),features=' | '.join(l['mention']),
                direct_calls=group_counts['direct']['All calls'],neighbor_calls=group_counts['neighbors']['All calls'],
                note='Parcel call totals repeat across listings; never sum listing rows.'))
        for r in combined.itertuples():
            side='direct' if r.pin==p['pin'] else 'neighbors'
            memberships.append(dict(focal_pin=p['pin'],recorded_pin=r.pin,call_number=r.number,date=r.date,call_type=r.type,outcome=r.outcome,side=side))
            for feature in positive:vote_records.append(dict(feature=feature,focal_pin=p['pin'],call_number=r.number,side=side,outcome=r.outcome))
    members=pd.DataFrame(memberships);votes=pd.DataFrame(vote_records)
    assert not members.duplicated(['focal_pin','call_number']).any()
    assert not votes.duplicated(['feature','focal_pin','call_number']).any()
    members.to_csv(out/'neighborhood_call_memberships.csv',index=False)
    votes.to_csv(out/'raw_amenity_vote_ledger.csv',index=False)
    pd.DataFrame(listing_scores).to_csv(out/'listing_scores.csv',index=False)
    scores=[]
    for p in property_records:
        row={k:p[k] for k in ['pin','address','permit_type','advertised_guests','approved_guests','licensed_bedrooms','neighbor_count','max_single_listing_feature_count','advertised_feature_union_count','max_single_listing_physical_count']}
        row['listing_urls']=' | '.join(l['url'] for l in p['listings'])
        for scope in SCOPES:
            opportunities=.59 if scope=='direct' else p['neighbor_count'] if scope=='neighbors' else p['neighbor_count']+.59
            for k in outcomes:
                n=p['counts'][scope][k];exposure=years[k]*opportunities
                row[f'{scope}__{k}__calls']=n
                row[f'{scope}__{k}__expected']=baselines[k]*exposure
                row[f'{scope}__{k}__excess_votes']=n-baselines[k]*exposure
                row[f'{scope}__{k}__annual_rate']=n/exposure if exposure else np.nan
        scores.append(row)
    pd.DataFrame(scores).to_csv(out/'property_scores.csv',index=False)
    tallies=[]
    for feature,label in labels.items():
        advertisers=[p for p in property_records if feature in p['advertised_features']]
        for scope in SCOPES:
            for k in outcomes:
                values=[];raw=0;expected=0.;exposure_total=0.
                for p in advertisers:
                    exposure=years[k]*(.59 if scope=='direct' else p['neighbor_count'] if scope=='neighbors' else p['neighbor_count']+.59)
                    if exposure<=0:continue
                    n=p['counts'][scope][k];raw+=n;expected+=baselines[k]*exposure;exposure_total+=exposure;values.append(n/exposure-baselines[k])
                tallies.append(dict(feature=feature,label=label,scope=scope,outcome=k,advertising_properties=len(advertisers),scored_properties=len(values),
                    raw_call_votes=raw,expected_calls=expected,excess_call_votes=raw-expected,
                    votes_per_advertiser=raw/len(values) if values else np.nan,
                    mean_excess_annual_rate=float(np.mean(values)) if values else np.nan,
                    pooled_calls_per_property_year=raw/exposure_total if exposure_total else np.nan))
    pd.DataFrame(tallies).to_csv(out/'amenity_vote_tallies.csv',index=False)
    self_models=fit_models(property_records,years,out)
    summary=dict(properties=len(property_records),listings=len(listing_scores),features=len(labels),
        unique_calls_in_neighborhoods=int(members.call_number.nunique()),call_memberships=len(members),raw_feature_vote_memberships=len(votes),
        residential_baseline_properties=len(eligible),date_start=coverage['date_start'],date_end=coverage['date_end'],
        parking_note=report['summary']['category_coverage_note'],citizen_only=True,
        source_hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['direct_listing_calls/report_data.js','processed_data/full_period_calls/combined_calls.csv','neighborhood_occupancy_plots/all_direct_boundary_links.csv','processed_data/listing_matches/source_match_audit.csv']})
    payload=dict(properties=property_records,features=[dict(id=k,label=v,family='physical candidate' if k in PHYSICAL else 'advertising / activity language') for k,v in labels.items()],
        outcomes=outcomes,years=years,baselines=baselines,summary=summary,models=self_models)
    (out/'data.js').write_text('window.AMENITY_VOTES='+json.dumps(payload,allow_nan=False)+';',encoding='utf-8')
    (out/'analysis_summary.json').write_text(json.dumps(summary,indent=2))
    (out/'README.md').write_text('''# Amenity vote analysis

Open index.html for live scoring. All citizen-only currently licensed, address-matched properties are included, with zero-call cases and touching residential neighbors inside the fixed call-coverage population. Corners and across-road parcels are not neighbors; saved commercial/hotel exclusions and the established geometry rules are retained.

A raw vote is one feature/focal-parcel/call-number membership. Repeated mentions or listings do not duplicate a feature's vote inside a focal neighborhood. A call can vote for several features and several overlapping rental neighborhoods. This is not causal attribution or a regional unique-call total. The ledger preserves every membership.

The live subtract-average checkbox scores observed minus expected calls, or annualized rate minus the residential reference. Below-average properties contribute negative values. A separate per-advertising-property checkbox prevents raw totals automatically favoring common features. Both scoring choices and their units are displayed explicitly.

Expected calls = residential category rate × category years × exposure properties. Exposure is the booking fraction for the rental, one calendar year per eligible neighbor, or their sum. The 59% scenario applies only to the focal rental; neighbors are not assumed to share its booking rate. Parking uses the entire supported early period and never treats missing later coverage as zero.

Feature tallies use the union of captured positive feature/party-language mentions across matched listings on the parcel, while both union and maximum-single-listing scores are retained. Physical on-site evidence is also available separately. Generic language and physical amenities remain labeled separately. Evidence absence is not verified amenity absence. Scores are associations, not proof an amenity produced a call.

The rough capacity × amenity-count equation is compared with fitted Poisson alternatives using held-out groups. Neighborhoods that share a parcel are kept in the same validation group. This reduces shared-neighbor leakage but does not remove all spatial/temporal confounding or establish causality. Full available dates are retained, with the stated parking coverage exception. Rebuild: python -m processing.amenity_votes.
''',encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return payload

def fit_models(properties,years,out):
    # Keep overlapping neighborhoods in one fold; never split a shared call opportunity across train/test.
    parents=list(range(len(properties)))
    def find(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    owner={}
    for i,p in enumerate(properties):
        for pin in [p['pin']]+p['neighbor_ids']:
            if pin in owner:parents[find(i)]=find(owner[pin])
            else:owner[pin]=i
    components={}
    for i in range(len(properties)):components.setdefault(find(i),[]).append(i)
    loads=[0]*5;folds={}
    for group,ids in sorted(components.items(),key=lambda item:-len(item[1])):
        fold=int(np.argmin(loads));loads[fold]+=len(ids)
        for i in ids:folds[i]=fold
    comparison=[];coefficients=[]
    for scope in ['direct','combined']:
        for outcome in ['All calls','Noise-party-disturbance']:
            valid=[(i,p) for i,p in enumerate(properties) if p['advertised_guests'] is not None]
            y=np.array([p['counts'][scope][outcome] for _,p in valid],float)
            exposure=np.array([years[outcome]*(.59 if scope=='direct' else p['neighbor_count']+.59) for _,p in valid])
            cap=np.array([p['advertised_guests'] for _,p in valid],float)
            score=np.array([p['max_single_listing_feature_count'] for _,p in valid],float)
            logcap=np.log1p(cap);ownerflag=np.array([p['permit_type']=='owner' for _,p in valid],float)
            licenses=np.log1p([p['license_count'] for _,p in valid]);fold=np.array([folds[i] for i,_ in valid])
            designs={'size_only':np.column_stack([np.ones(len(y)),logcap,ownerflag,licenses]),
                'amenity_count_only':np.column_stack([np.ones(len(y)),score,ownerflag,licenses]),
                'size_plus_amenities':np.column_stack([np.ones(len(y)),logcap,score,ownerflag,licenses]),
                'size_amenities_interaction':np.column_stack([np.ones(len(y)),logcap,score,logcap*score,ownerflag,licenses])}
            for name in list(designs)+['rough_capacity_times_amenities','rough_capacity_times_one_plus_amenities']:
                predictions=np.full(len(y),np.nan);status='estimated'
                try:
                    for held in sorted(set(fold)):
                        train=fold!=held;test=~train
                        if name.startswith('rough_'):
                            z=cap*(score if name=='rough_capacity_times_amenities' else score+1)
                            k=y[train].sum()/max(1e-12,float((exposure[train]*z[train]).sum()))
                            predictions[test]=exposure[test]*z[test]*k
                        else:
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore');m=sm.GLM(y[train],designs[name][train],family=sm.families.Poisson(),offset=np.log(exposure[train])).fit(maxiter=100)
                            predictions[test]=m.predict(designs[name][test],offset=np.log(exposure[test]))
                    assert np.isfinite(predictions).all()
                    safe=np.maximum(predictions,1e-9)
                    deviance=float(2*np.mean(np.where(y>0,y*np.log(np.maximum(y,1e-9)/safe)-y+safe,safe)))
                    mae=float(np.mean(abs(y-predictions)))
                    if name in designs:
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore');full=sm.GLM(y,designs[name],family=sm.families.Poisson(),offset=np.log(exposure)).fit(maxiter=100)
                        coefficients.append(dict(scope=scope,outcome=outcome,model=name,coefficients=json.dumps(full.params.tolist())))
                    comparison.append(dict(scope=scope,outcome=outcome,model=name,properties=len(y),events=int(y.sum()),validation_groups=len(components),held_out_deviance=deviance,held_out_mean_absolute_error=mae,status=status))
                except Exception as error:comparison.append(dict(scope=scope,outcome=outcome,model=name,status='failed: '+str(error)))
    table=pd.DataFrame(comparison);table.to_csv(out/'capacity_amenity_model_comparison.csv',index=False)
    pd.DataFrame(coefficients).to_csv(out/'capacity_amenity_model_coefficients.csv',index=False)
    pd.DataFrame([dict(pin=p['pin'],validation_group=find(i),validation_fold=folds[i]) for i,p in enumerate(properties)]).to_csv(out/'validation_groups.csv',index=False)
    return table.replace({np.nan:None}).to_dict('records')

if __name__=='__main__':run()
