"""Build a deduplicated property payload and complete license-address audit for live filters."""
import re
import numpy as np
import pandas as pd
from processing.citizen_only import select as citizen_only

FEATURES={'hot_tub':'Hot tub','pool':'Pool','grill':'Grill / BBQ','fire_pit':'Fire pit',
          'sound_system':'Sound system','bar':'Bar','outdoor_dining':'Outdoor dining',
          'patio':'Patio','yard':'Yard','events':'Events','wedding':'Wedding',
          'bachelorette':'Bachelorette','bachelor':'Bachelor'}

def build(root,out,parcels,calls,active,categories,years,parking_years):
    licenses=pd.read_csv(root/'processed_data/licenses/licenses_normalized.csv',dtype=str).fillna('')
    assert licenses['Permit Number'].is_unique
    canonical={p.replace(' ',''):p for p in parcels.pin}
    licenses['pin']=licenses.source_apn_key.map(canonical).fillna('')
    excluded=set(pd.read_csv(root/'excluded_properties.csv',dtype=str).PIN.str.replace(' ',''))
    licenses['call_coverage_available']=licenses.pin.ne('') & ~licenses.source_apn_key.isin(excluded)
    licenses['approved_guests']=pd.to_numeric(licenses['Max. occupancy'],errors='coerce')
    licenses['licensed_bedrooms']=pd.to_numeric(licenses.Bedrooms,errors='coerce')
    licenses['permit_type']=licenses['Owner Occupied vs Non-Owner Occupied'].map(
        lambda value:'owner' if value.startswith('Type 1:') else ('non_owner' if value.startswith('Type 2:') else 'unknown'))
    licenses['recorded_capacity_rule']=np.select([
        licenses.approved_guests.eq(2*licenses.licensed_bedrooms),
        licenses.approved_guests.eq(2*licenses.licensed_bedrooms+2)],
        ['recorded limit = 2 per bedroom','recorded limit = 2 per bedroom + 2'],default='other recorded limit')
    lookup=licenses.set_index('Permit Number')
    listing_records=[]
    for r in active.to_dict('records'):
        permits=re.findall(r'SVR-\d+',r['permit_numbers'])
        matched=lookup.loc[[p for p in permits if p in lookup.index]]
        complete=bool(permits) and len(matched)==len(permits) and matched.approved_guests.notna().all()
        same_parcel=complete and matched.pin.eq(r['parcel_PIN']).all()
        approved=float(matched.approved_guests.sum()) if same_parcel else None
        bedrooms=float(matched.licensed_bedrooms.sum()) if same_parcel and matched.licensed_bedrooms.notna().all() else None
        guests=r['guests'] if pd.notna(r['guests']) else None
        listing_records.append(dict(listing_id=r['listing_id'],url=r['listing_url'],title=r['title'],pin=r['parcel_PIN'],
            guests=guests,bedrooms=r['bedrooms'] if pd.notna(r['bedrooms']) else None,
            approved_guests=approved,licensed_bedrooms=bedrooms,permits=permits,
            permit_types=sorted(set(matched.permit_type)) if len(matched) else ['unknown'],
            over_limit=bool(guests is not None and approved is not None and guests>approved),
            overage=(guests-approved) if guests is not None and approved is not None else None,
            onsite=[x for x in r['on_site_feature_candidates'].split(' | ') if x],
            mention=[x for x in r['active_mention_features'].split(' | ') if x],
            restriction=[x for x in r['restriction_mentions'].split(' | ') if x]))
    by_pin={}
    for r in listing_records:by_pin.setdefault(r['pin'],[]).append(r)
    properties=[]
    for pin,g in licenses[licenses.call_coverage_available].groupby('pin'):
        listings=by_pin.get(pin,[])
        types=sorted(set(g.permit_type))
        record=dict(pin=pin,address=str(parcels.loc[parcels.pin.eq(pin),'address'].iloc[0]),
            permit_type=types[0] if len(types)==1 else 'mixed',permit_types=types,
            license_count=len(g),approved_guests=float(g.approved_guests.sum()) if g.approved_guests.notna().all() else None,
            licensed_bedrooms=float(g.licensed_bedrooms.sum()) if g.licensed_bedrooms.notna().all() else None,
            listings=listings,rates={},counts={})
        for measure in ['citizen']:
            subset=calls[calls.pin.eq(pin)]
            subset=citizen_only(subset)
            record['rates'][measure]={};record['counts'][measure]={}
            for cat in categories:
                n=len(subset if cat=='All calls' else subset[subset.analysis_category.eq(cat)])
                record['counts'][measure][cat]=n
                record['rates'][measure][cat]=n/(parking_years if cat=='Parking complaints' else years)
        properties.append(record)
    assert len({p['pin'] for p in properties})==len(properties)
    address_records=[]
    for r in licenses.to_dict('records'):
        address_records.append(dict(permit=r['Permit Number'],address=r['normalized_delivery_address'],
            unit=r['Unit Number'],pin=r['pin'],source_apn=r['source_apn_key'],
            permit_type=r['permit_type'],permit_type_original=r['Owner Occupied vs Non-Owner Occupied'],
            approved_guests=r['approved_guests'] if pd.notna(r['approved_guests']) else None,
            licensed_bedrooms=r['licensed_bedrooms'] if pd.notna(r['licensed_bedrooms']) else None,
            call_coverage_available=bool(r['call_coverage_available']),capacity_rule=r['recorded_capacity_rule'],
            listing_ids=[x['listing_id'] for x in by_pin.get(r['pin'],[]) if r['Permit Number'] in x['permits']]))
    licenses.to_csv(out/'complete_license_address_audit.csv',index=False)
    pd.DataFrame(listing_records).to_csv(out/'listing_license_capacity_audit.csv',index=False)
    return dict(properties=properties,license_addresses=address_records,features=FEATURES,categories=categories,
        counts=dict(complete_license_rows=len(licenses),covered_license_rows=int(licenses.call_coverage_available.sum()),
            covered_license_parcels=len(properties),matched_listing_parcels=sum(bool(p['listings']) for p in properties),
            license_rows_by_type=licenses.permit_type.value_counts().to_dict(),
            covered_parcels_by_type=pd.Series([p['permit_type'] for p in properties]).value_counts().to_dict(),
            listings_over_approved_limit=sum(r['over_limit'] for r in listing_records)))
