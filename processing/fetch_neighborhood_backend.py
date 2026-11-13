"""Read-only assessor export over verified SSH. Credentials remain outside the repository."""
import json
import os
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
pins=json.loads((ROOT/'neighborhood_occupancy_plots/candidate_pins.json').read_text())
assert all(p.isalnum() for p in pins)
values=','.join("'"+p+"'" for p in pins)
query=f"""COPY (
SELECT DISTINCT ON (pin) pin,tax_year,checked_at,
 payload->>'verified_bedrooms' AS bedrooms,
 payload->>'reported_unit_count' AS reported_unit_count,
 payload->>'has_residential_building' AS has_residential_building,
 payload->>'location_address' AS location_address,
 payload->>'property_class' AS property_class,
 payload->>'source_url' AS source_url,
 payload->>'evidence_note' AS evidence_note,
 payload->>'assessor_cards_json' AS assessor_cards_json,
 (SELECT jsonb_agg(s) FROM jsonb_array_elements(COALESCE(NULLIF(payload->>'property_sections_json',''),'[]')::jsonb) s
 WHERE s->>'title' ILIKE '%residential building%') AS residential_building_sections
FROM county_chatham.assessor_records WHERE pin IN ({values}) ORDER BY pin,tax_year DESC
) TO STDOUT WITH CSV HEADER;"""
key=Path(os.environ.get('REGISTVR_SSH_KEY',str(Path.home()/'OneDrive/NETWORK/hosts_servers_and_services/proxmox/registvr-access-private/registvr_vm_management_ed25519')))
known=Path.home()/'OneDrive/NETWORK/hosts_servers_and_services/proxmox/registvr-access-private/registvr_backend_known_hosts'
cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-i',str(key),'-o','IdentitiesOnly=yes',
     '-o',f'UserKnownHostsFile={known}','-o','StrictHostKeyChecking=yes','registvr@192.168.1.231',
     'sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d registvr -q']
result=subprocess.run(cmd,input=query.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
dest=ROOT/'raw_data/registvr_neighborhood_assessor.csv'
dest.write_bytes(result.stdout)
print(f'Saved assessor evidence for candidate parcels to {dest.name}')
query=f"""COPY (SELECT key,pin,property_url,synced_at,payload->>'property_type' AS property_type,
payload->>'property_subtype' AS property_subtype,payload->>'bedrooms' AS bedrooms,
payload->>'features_json' AS features_json,payload->>'description_json' AS description_json
FROM county_chatham.realtor_property_records
WHERE replace(pin,' ','') IN ({values})) TO STDOUT WITH CSV HEADER;"""
result=subprocess.run(cmd,input=query.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
(ROOT/'raw_data/registvr_neighborhood_realtor.csv').write_bytes(result.stdout)
print('Saved realtor building-type evidence')
