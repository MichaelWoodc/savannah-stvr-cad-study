"""Combine all supplied call windows; preserve per-category coverage explicitly."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import pandas as pd
from processing.cad_normalization import normalize_cad_address

def load_calls(root, study, parcels):
    root=Path(root);out=root/'processed_data/full_period_calls';out.mkdir(parents=True,exist_ok=True)
    sources=['data.js','parcel_rates.csv','occupancy_plots/cad_rental_match_audit.csv',
             'neighborhood_occupancy_plots/digest_parcel_addresses.csv',
             'processed_data/licenses/licenses_normalized.csv','processing/entire_call_period.py']
    hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources}
    meta=out/'coverage.json'
    if meta.exists():
        saved=json.loads(meta.read_text())
        if saved.get('source_sha256')==hashes:
            return pd.read_csv(out/'combined_calls.csv',dtype=str).fillna(''),saved
    canonical={p.replace(' ',''):p for p in parcels.pin}
    digest=pd.read_csv(root/sources[3],dtype=str).fillna('')
    addresses=defaultdict(set)
    for r in digest.itertuples():
        key=normalize_cad_address(r.PropAddress_Full)['street_building_candidate_key']
        if key:addresses[key].add(r.parcel_key)
    licenses=pd.read_csv(root/sources[4],dtype=str).fillna('')
    for r in licenses.itertuples():
        if r.house_number and r.street_suffix:addresses[r.normalized_building_address].add(r.source_apn_key)
    raw=pd.read_csv(root/sources[2],dtype=str).fillna('')
    raw['parsed_date']=pd.to_datetime(raw.Date,format='%m/%d/%Y',errors='coerce')
    assigned=[];methods=[]
    for r in raw.itertuples():
        candidates=addresses.get(r.street_building_candidate_key,set()) if r.street_building_candidate_key else set()
        spatial=r.coordinate_parcel_candidates.split('|') if r.coordinate_parcel_candidates else []
        pin='';method='no_unique_address'
        if len(candidates)==1:
            p=next(iter(candidates))
            if len(spatial)>1:method='ambiguous_coordinate_parcels'
            elif spatial and spatial[0]!=p:method='address_coordinate_conflict'
            elif p not in canonical:method='outside_fixed_residential_cohort'
            else:pin=canonical[p];method='address_and_coordinate' if spatial else 'address_only'
        assigned.append(pin);methods.append(method)
    raw['assigned_study_pin']=assigned;raw['full_period_match_method']=methods
    raw[['source_excel_row','Call Number','Date','Address','Call Type','assigned_study_pin','full_period_match_method']].to_csv(out/'early_cad_match_audit.csv',index=False)
    raw[raw.parsed_date.isna()|raw['Call Number'].eq('')].to_csv(out/'invalid_date_or_call_number.csv',index=False)
    early=raw[raw.assigned_study_pin.ne('')&raw.parsed_date.notna()&raw['Call Number'].ne('')].copy()
    early=pd.DataFrame(dict(number=early['Call Number'],pin=early.assigned_study_pin,date=early.parsed_date.dt.strftime('%Y-%m-%d'),
        type=early['Call Type'],initiation=early.Initiation,address=early.Address,source='raw_CAD',category=''))
    later=pd.DataFrame(study['calls'])
    later['pin']=later.pin.str.replace(' ','').map(canonical)
    later['source']='published_extract'
    # Preserve original category taxonomy wherever the same dispatch label is available.
    type_category={str(t).upper():c for t,c in zip(later.type,later.category)}
    early['category']=early.type.str.upper().map(type_category).fillna('Other / unclear')
    merged=pd.concat([early,later[['number','pin','date','type','initiation','address','source','category']]],ignore_index=True)
    conflicts=merged.groupby('number')[['pin','date','type','initiation']].nunique().gt(1).any(axis=1)
    bad=set(conflicts.index[conflicts])
    merged[merged.number.isin(bad)].to_csv(out/'conflicting_call_numbers.csv',index=False)
    combined=merged[~merged.number.isin(bad)].drop_duplicates('number').copy()
    assert combined.number.is_unique and combined.pin.isin(parcels.pin).all()
    start=raw.parsed_date.min().normalize();end=pd.Timestamp(study['summary']['date_end'])
    early_end=raw.parsed_date.max().normalize();later_start=pd.Timestamp(study['summary']['date_start'])
    assert early_end+pd.Timedelta(days=1)==later_start,'Coverage gap requires review'
    coverage=dict(date_start=str(start.date()),date_end=str(end.date()),exposure_days=(end-start).days+1,
        exposure_years=((end-start).days+1)/365.25,
        parking_date_start=str(start.date()),parking_date_end=str(early_end.date()),
        parking_exposure_years=((early_end-start).days+1)/365.25,
        raw_rows=len(raw),early_matched_calls=int(combined.source.eq('raw_CAD').sum()),
        published_matched_calls=int(combined.source.eq('published_extract').sum()),
        combined_calls=len(combined),conflicting_call_numbers=len(bad),source_sha256=hashes,
        source_coverage_note='Uses every available date. Later publication is a retained/filtered extract, not the full source CAD. Parking coverage exists only in the early raw CAD window. Complete category coverage over the entire span is not established.')
    combined.to_csv(out/'combined_calls.csv',index=False)
    meta.write_text(json.dumps(coverage,indent=2))
    return combined,coverage
