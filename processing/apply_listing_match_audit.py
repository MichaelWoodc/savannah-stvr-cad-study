"""Replace historical folder-derived joins with source-validated joins, preserving an audit snapshot."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def run(root=ROOT):
    root=Path(root);directory=root/'processed_data/listing_matches'
    audit=pd.read_csv(directory/'source_match_audit.csv',dtype=str).fillna('')
    audit['verified']=audit.source_verified.str.lower().eq('true')
    by_id=audit.set_index('listing_id').to_dict('index')
    table=pd.read_csv(root/'listing_screen_all.csv',dtype=str).fillna('')
    snapshot=directory/'original_listing_screen_all.csv'
    if not snapshot.exists():table.to_csv(snapshot,index=False)
    folder_map={};path_map={};old_rows=table.copy()
    lic=pd.read_csv(root/'processed_data/licenses/licenses_normalized.csv',dtype=str).fillna('')
    addresses={p:g.normalized_license_address.iloc[0] if 'normalized_license_address' in g else g.normalized_building_address.iloc[0] for p,g in lic.groupby('source_apn_key')}
    parcels=pd.read_csv(root/'parcel_rates.csv',dtype=str).fillna('');canonical={p.replace(' ',''):p for p in parcels.pin}
    rates=parcels.set_index('pin').to_dict('index')
    for index,row in table.iterrows():
        a=by_id.get(row.listing_id)
        if not a:continue
        old_folder=row.folder_name;new_folder=a['current_folder']
        folder_map[old_folder]=new_folder;path_map[row.source_file]='Savannah/'+new_folder+'/details.txt'
        table.loc[index,'folder_name']=new_folder;table.loc[index,'source_file']=path_map[row.source_file]
        table.loc[index,'match_validation_status']=a['status']
        table.loc[index,'permit_match_source']='source_text_validated' if a['verified'] else 'none_source_match_quarantined'
        table.loc[index,'permit_numbers']=a['matched_permits'] if a['verified'] else a['source_text_permits']
        table.loc[index,'old_unverified_parcel_PIN']=row.parcel_PIN
        if a['verified'] and a['status']=='source_supported_in_study':
            pin=canonical[a['matched_pin']]
            table.loc[index,'parcel_PIN']=pin;table.loc[index,'scope_status']='eligible_residential'
            table.loc[index,'location_exclusion']='';table.loc[index,'normalized_license_address']=addresses[a['matched_pin']]
            table.loc[index,'matched_approved_capacity']=a['approved_capacity'];table.loc[index,'capacity_basis']='source_text_certificates'
            capacity=pd.to_numeric(row.advertised_capacity,errors='coerce');approved=float(a['approved_capacity'])
            table.loc[index,'capacity_overage']=str(capacity-approved) if pd.notna(capacity) else ''
            table.loc[index,'capacity_status']='unknown_advertised_capacity' if pd.isna(capacity) else ('advertised_above_source_matched_allowance' if capacity>approved else 'not_above_source_matched_allowance')
            for key,source in [('direct_calls','direct_calls'),('neighbor_only_calls','neighbor_only_calls'),('direct_calls_per_year','direct_per_year'),('neighbor_only_calls_per_focal_year','neighbor_only_per_year')]:table.loc[index,key]=rates[pin][source]
        else:
            if row.parcel_PIN:table.loc[index,'rejected_candidate_parcel_PIN']=row.parcel_PIN
            for key in ['parcel_PIN','normalized_license_address','matched_approved_capacity','capacity_overage','direct_calls','neighbor_only_calls','direct_calls_per_year','neighbor_only_calls_per_focal_year']:table.loc[index,key]=''
            table.loc[index,'capacity_status']='unknown_unverified_match'
            table.loc[index,'scope_status']='excluded_Tybee_Island_location' if row.scope_status=='excluded_Tybee_Island_location' else ('outside_fixed_residential_coverage' if a['verified'] else 'quarantined_'+a['status'])
            table.loc[index,'location_exclusion']=a['status']
    table.to_csv(root/'listing_screen_all.csv',index=False)
    table[table.scope_status.eq('eligible_residential')].to_csv(root/'ranked_listings_with_calls.csv',index=False)
    # Update only reference metadata in the original keyword evidence, never quotes/source hashes.
    for name in ['listing_keyword_evidence.csv']:
        evidence=pd.read_csv(root/name,dtype=str).fillna('')
        if 'folder_name' in evidence:evidence['folder_name']=evidence.folder_name.map(lambda v:folder_map.get(v,v))
        if 'source_file' in evidence:evidence['source_file']=evidence.source_file.map(lambda v:path_map.get(v,v))
        evidence.to_csv(root/name,index=False)
    source=root/'data.js';study=json.loads(source.read_text(encoding='utf-8-sig').split('=',1)[1].strip().rstrip(';'))
    old_embedded={r['listing_id']:r for r in study['listingScreen']['listings']}
    rows=[]
    for record in table[table.scope_status.eq('eligible_residential')].to_dict('records'):
        row=dict(old_embedded.get(record['listing_id'],{}));row.update(record)
        for field in ['advertised_capacity','advertised_bedrooms','matched_approved_capacity','capacity_overage','direct_calls','neighbor_only_calls','direct_calls_per_year','neighbor_only_calls_per_focal_year']:
            value=pd.to_numeric(row.get(field,''),errors='coerce');row[field]=float(value) if pd.notna(value) else None
        for field in ['folder_text_permit_conflict','advertised_capacity_is_lower_bound']:row[field]=str(row.get(field,'')).lower()=='true'
        row['pin']=row['parcel_PIN'].replace(' ','')
        for out,key in [('activeFeatures','active_mention_features'),('onSiteFeatures','on_site_feature_candidates'),('restrictionFeatures','restriction_mentions')]:row[out]=[v for v in row[key].split(' | ') if v]
        row.setdefault('evidence',[]);row.setdefault('featureStatuses',{})
        rows.append(row)
    study['listingScreen']['listings']=rows
    summary=study['listingScreen']['summary']
    summary.update(eligible_listing_rows=len(rows),text_covered_residential_licensed_parcels=len({r['pin'] for r in rows}),
        advertised_above_capacity_eligible_listings=sum(r['capacity_overage'] is not None and r['capacity_overage']>0 for r in rows),
        match_policy='Source-text permits required; folder names are never match evidence; contradictory displayed locations quarantined.')
    source.write_text('window.STVR_STUDY='+json.dumps(study,separators=(',',':'),allow_nan=False)+';',encoding='utf-8')
    print(f'Installed {len(rows)} source-supported listing joins across {len({r["pin"] for r in rows})} parcels; historical joins preserved in {snapshot.name}.')
    return table

if __name__=='__main__':run()
