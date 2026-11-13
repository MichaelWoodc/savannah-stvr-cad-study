"""Prepare direct shared-boundary parcel links before applying backend residential evidence."""
import json
from pathlib import Path
from collections import defaultdict
import pandas as pd
from shapely.geometry import shape
from shapely.ops import transform, unary_union
from shapely import make_valid
from shapely.strtree import STRtree
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'neighborhood_occupancy_plots'
OUT.mkdir(exist_ok=True)
features = json.loads((ROOT/'raw_data/Parcel_Digest_2025.geojson').read_text(encoding='utf-8-sig'))['features']
by_pin = defaultdict(list)
metadata = {}
for f in features:
    p = f['properties']; pin = str(p['PIN']).replace(' ','').upper()
    if f['geometry']:
        g = shape(f['geometry'])
        if not g.is_valid: g = make_valid(g)
        if not g.is_empty: by_pin[pin].append(g)
    metadata[pin] = {k:p.get(k) for k in ['PIN','PropAddress_Full','PropAddress_City','Property_Use','Commercial_Cat']}
pins = sorted(by_pin)
geoms = [unary_union(by_pin[p]) for p in pins]
del features, by_pin
tree = STRtree(geoms)
index = {p:i for i,p in enumerate(pins)}
licenses = pd.read_csv(ROOT/'processed_data/licenses/licenses_normalized.csv',dtype=str).fillna('')
excluded = set(pd.read_csv(ROOT/'excluded_properties.csv',dtype=str).PIN.str.replace(' ',''))
focal = sorted(set(licenses.source_apn_key) & set(pins) - excluded)
project = Transformer.from_crs(4326,32617,always_xy=True).transform
projected = {}
def meters(i):
    if i not in projected: projected[i] = transform(project,geoms[i])
    return projected[i]
rows=[]; candidates=set(focal)
for pin in focal:
    i=index[pin]; a=meters(i)
    for j in tree.query(geoms[i],predicate='intersects'):
        j=int(j)
        if i==j: continue
        b=meters(j)
        if a.intersection(b).area > 1e-6: continue
        length=a.boundary.intersection(b.boundary).length
        if length > .1:
            rows.append({'focal_pin':pin,'neighbor_pin':pins[j],'shared_boundary_m':length})
            candidates.add(pins[j])
pd.DataFrame(rows).to_csv(OUT/'all_direct_boundary_links.csv',index=False)
pd.DataFrame([dict(parcel_key=p,**metadata[p]) for p in pins]).to_csv(OUT/'digest_parcel_addresses.csv',index=False)
(OUT/'candidate_pins.json').write_text(json.dumps(sorted(candidates)))
print(f'{len(focal)} candidate rental parcels; {len(rows)} boundary links; {len(candidates)} parcels for backend lookup')
