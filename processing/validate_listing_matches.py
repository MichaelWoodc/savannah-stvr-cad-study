"""Verify listing joins from source-text permits and location; safely normalize source folders."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import hashlib
import json
import re
import pandas as pd
from pyproj import Transformer
from shapely.geometry import shape,Point
from shapely.ops import transform,unary_union
from shapely import make_valid

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'\\TRUENAS\Storage\scrapped_data\Savannah')
OUT=ROOT/'processed_data/listing_matches'

def permits(value):return sorted({'SVR-'+str(int(n)).zfill(5) for n in re.findall(r'\bSVR[-\s]*(\d{1,5})\b',str(value),re.I)})

def run(rename=True):
    OUT.mkdir(exist_ok=True,parents=True)
    inventory=pd.read_csv(ROOT/'processed_data/licenses/licenses_normalized.csv',dtype=str).fillna('')
    lookup={p:g for p,g in inventory.groupby('Permit Number')}
    old=pd.read_csv(ROOT/'listing_screen_all.csv',dtype=str).fillna('')
    previous={r.listing_id:r for r in old.itertuples()}
    fixed=set(pd.read_csv(ROOT/'parcel_rates.csv',dtype=str).pin.str.replace(' ',''))
    licensed_pins=set(inventory.source_apn_key)
    by_pin=defaultdict(list)
    for feature in json.loads((ROOT/'raw_data/Parcel_Digest_2025.geojson').read_text(encoding='utf-8-sig'))['features']:
        pin=str(feature['properties']['PIN']).replace(' ','')
        if pin in licensed_pins and feature['geometry']:by_pin[pin].append(shape(feature['geometry']))
    project=Transformer.from_crs(4326,32617,always_xy=True).transform
    geoms={pin:transform(project,make_valid(unary_union(gs))) for pin,gs in by_pin.items()}
    def inspect(folder):
        found=re.match(r'\d+',folder.name);listing_id=found[0] if found else ''
        row=dict(listing_id=listing_id,original_folder=folder.name,source_path=str(folder/'details.txt'),status='missing_details',
            source_text_permits='',old_folder_permits='',matched_permits='',matched_pin='',approved_capacity='',licensed_bedrooms='',
            latitude='',longitude='',privacy_radius_m='',distance_to_parcel_m='',source_verified=False,rename_status='not_needed')
        if listing_id in previous:
            before=previous[listing_id]
            row.update(old_folder_permits=before.permit_numbers,old_matched_pin=before.parcel_PIN,old_scope_status=before.scope_status)
        try:raw=(folder/'details.txt').read_bytes();text=raw.decode('utf-8-sig',errors='replace')
        except OSError:return row
        row['details_sha256']=hashlib.sha256(raw).hexdigest()
        def header(label):
            m=re.search(r'^'+re.escape(label)+r':\s*(.*)$',text,re.M);return m[1].strip() if m else ''
        row.update(title=header('Title'),current_bedrooms=header('Bedrooms'),current_guests=header('Occupancy (maximum guests)'),
            latitude=header('Latitude'),longitude=header('Longitude'),privacy_radius_m=header('Privacy radius (meters)'))
        source_permits=permits(text);row['source_text_permits']=' | '.join(source_permits)
        if not source_permits:row['status']='no_source_text_permit';return row
        unknown=[p for p in source_permits if p not in lookup]
        row['unknown_permits']=' | '.join(unknown)
        if unknown:row['status']='unknown_source_permit_requires_review';return row
        lic=pd.concat([lookup[p] for p in source_permits],ignore_index=True)
        pins=set(lic.source_apn_key)
        if len(pins)!=1:row['status']='multiple_source_parcels_requires_review';return row
        pin=next(iter(pins));row['candidate_pin']=pin
        if pin not in geoms:row['status']='source_permit_parcel_missing_digest';return row
        try:
            lat=float(row['latitude']);lon=float(row['longitude']);radius=float(row['privacy_radius_m'] or 500)
            if not (-90<=lat<=90 and -180<=lon<=180) or (lat==0 and lon==0):raise ValueError()
            distance=float(geoms[pin].distance(Point(*project(lon,lat))))
            # Display coordinates are used only to reject contradictory joins, never to infer an address.
            tolerance=max(500.,radius)+250.
            row['distance_to_parcel_m']=distance;row['rejection_tolerance_m']=tolerance
            if distance>tolerance:row['status']='source_permit_location_conflict';return row
            row['location_check']='within_display_radius_plus_250m'
        except ValueError:row['location_check']='coordinates_unavailable_source_permit_only'
        row.update(status='source_supported_in_study' if pin in fixed else 'source_supported_outside_fixed_study',source_verified=True,
            matched_pin=pin,matched_permits=' | '.join(source_permits),approved_capacity=float(pd.to_numeric(lic['Max. occupancy']).sum()),
            licensed_bedrooms=float(pd.to_numeric(lic.Bedrooms).sum()))
        return row
    folders=[p for p in SOURCE.iterdir() if p.is_dir()]
    rows=[]
    with ThreadPoolExecutor(max_workers=12) as executor:
        jobs={executor.submit(inspect,p):p for p in folders}
        for future in as_completed(jobs):
            rows.append(future.result())
            if len(rows)%500==0:print(f'Checked {len(rows)}/{len(folders)} listing folders',flush=True)
    frame=pd.DataFrame(rows).fillna('');assert frame.listing_id.ne('').all()
    duplicate_ids=set(frame.loc[frame.listing_id.duplicated(keep=False),'listing_id'])
    source_root=SOURCE.resolve()
    rename_records=[]
    for index,row in frame.iterrows():
        suffix='-('+row.matched_permits.replace(' | ',', ')+')' if row.source_verified else ''
        desired=row.listing_id+suffix
        frame.loc[index,'proposed_folder']=desired
        frame.loc[index,'current_folder']=row.original_folder
        if row.listing_id in duplicate_ids:
            frame.loc[index,'source_verified']=False;frame.loc[index,'status']='duplicate_listing_folders_require_review';frame.loc[index,'rename_status']='skipped_duplicate_id';continue
        if row.original_folder==desired:continue
        source=(SOURCE/row.original_folder).resolve();target=(SOURCE/desired).resolve()
        assert source.parent==source_root and target.parent==source_root
        if target.exists():frame.loc[index,'rename_status']='skipped_destination_exists';continue
        record=dict(listing_id=row.listing_id,old_folder=row.original_folder,new_folder=desired,reason=row.status,details_sha256=row.get('details_sha256',''))
        if rename:
            source.rename(target)
            frame.loc[index,'current_folder']=desired;frame.loc[index,'source_path']=str(target/'details.txt');frame.loc[index,'rename_status']='renamed'
        else:frame.loc[index,'rename_status']='planned'
        rename_records.append(record)
    frame.to_csv(OUT/'source_match_audit.csv',index=False)
    pd.DataFrame(rename_records).to_csv(OUT/'folder_rename_log.csv',index=False)
    allowed=frame[frame.source_verified.eq(True)&frame.status.eq('source_supported_in_study')]
    allowed.to_csv(OUT/'verified_listing_matches.csv',index=False)
    frame[~frame.source_verified.eq(True)].to_csv(OUT/'quarantined_listing_matches.csv',index=False)
    # Keep the downstream inventory current after the reversible folder renames.
    refreshed=[]
    for row in frame.to_dict('records'):
        refreshed.append(dict(folder=row['current_folder'],listing_id=row['listing_id'],details_path=row['source_path'],
            read_status='error' if row['status']=='missing_details' else 'read',details_sha256=row.get('details_sha256',''),
            current_title=row.get('title',''),current_bedrooms=row.get('current_bedrooms',''),current_guests=row.get('current_guests',''),
            text_permit_candidates=row['source_text_permits'],error='missing details.txt' if row['status']=='missing_details' else ''))
    pd.DataFrame(refreshed).to_csv(ROOT/'processed_data/listing_details/current_detail_inventory.csv',index=False)
    summary=dict(checked_utc=datetime.now(timezone.utc).isoformat(),folders=len(frame),
        status_counts=frame.status.value_counts().to_dict(),renamed=int(frame.rename_status.eq('renamed').sum()),
        old_eligible_without_source_support=int(((frame.old_scope_status=='eligible_residential')&~frame.source_verified.eq(True)).sum()),
        source_supported_in_study=len(allowed),policy='Source-text SVR permits required. Folder names are never evidence. Location distances beyond max(privacy radius,500m)+250m quarantine the join. Display coordinates never assign an address.')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    validation=dict(validated_listing_ids=allowed.listing_id.tolist(),
        matches={r.listing_id:dict(pin=r.matched_pin,permits=permits(r.matched_permits)) for r in allowed.itertuples()},
        audit_sha256=hashlib.sha256((OUT/'source_match_audit.csv').read_bytes()).hexdigest(),summary=summary)
    (ROOT/'listing_match_validation.js').write_text('window.LISTING_MATCH_VALIDATION='+json.dumps(validation)+';',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
    return frame

if __name__=='__main__':run(rename=True)
