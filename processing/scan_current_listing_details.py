"""Read listing headers from the user's source share without changing source files."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import re
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'\\TRUENAS\Storage\scrapped_data\Savannah')
OUT=ROOT/'processed_data/listing_details'
OUT.mkdir(parents=True,exist_ok=True)
def scan(folder):
    path=folder/'details.txt'
    identifier=re.match(r'\d+',folder.name)
    row={'folder':folder.name,'listing_id':identifier[0] if identifier else '', 'details_path':str(path),'read_status':'missing'}
    try:
        raw=path.read_bytes();text=raw.decode('utf-8-sig',errors='replace')
        row.update(read_status='read',details_sha256=hashlib.sha256(raw).hexdigest())
        def find(pattern):
            m=re.search(pattern,text,re.M|re.I);return m.group(1).strip() if m else ''
        row['listing_id']=find(r'^URL:\s*https?://(?:www\.)?airbnb\.[^/]+/rooms/(\d+)') or re.match(r'\d+',folder.name)[0]
        row['current_title']=find(r'^Title:\s*(.*)$')
        row['current_bedrooms']=find(r'^Bedrooms:\s*(\d+(?:\.\d+)?)\s*$')
        row['current_guests']=find(r'^Occupancy \(maximum guests\):\s*(\d+(?:\.\d+)?)\s*$')
        row['text_permit_candidates']=' | '.join(sorted({'SVR-'+str(int(p)).zfill(5) for p in re.findall(r'\bSVR[-\s]*(\d{1,5})\b',text,re.I)}))
    except (OSError,TypeError) as error:
        row.update(read_status='error',error=str(error))
    return row
folders=[p for p in SOURCE.iterdir() if p.is_dir()]
with ThreadPoolExecutor(max_workers=8) as pool:
    rows=list(pool.map(scan,folders))
data=pd.DataFrame(rows)
data.to_csv(OUT/'current_detail_inventory.csv',index=False)
print(f'Scanned {len(data)} folders: {data.read_status.value_counts().to_dict()}')
