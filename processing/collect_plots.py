"""Export individual citizen-only charts; no subplot sheets or non-citizen series."""
from pathlib import Path
import csv
import hashlib
import json
import re
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from processing.citizen_only import select as citizen_only
from processing.plot_axes import discrete_axis

ROOT=Path(__file__).resolve().parents[1]
TYPES={'owner':'Owner-occupied','non_owner':'Non-owner-occupied','mixed':'Mixed permit types','unknown':'Unknown'}
COLORS={'owner':'#2563eb','non_owner':'#d97706','mixed':'#7c3aed','unknown':'#64748b'}
SIZES={'guests':'Advertised guest capacity','bedrooms':'Advertised bedrooms','approved_guests':'Approved guest capacity (parcel total)','licensed_bedrooms':'Licensed bedrooms (parcel total)','capacity_difference':'Advertised guests minus approved limit'}
COUNTER=0

def slug(value):return re.sub(r'[^a-z0-9]+','_',str(value).lower()).strip('_')

def curve(root,name,title,xlabel,series,note,baseline=None):
    global COUNTER
    out=root/'plots';fig,ax=plt.subplots(figsize=(11,7))
    table=[]
    for label,points,color in series:
        if not points:continue
        ax.plot([p[0] for p in points],[p[1] for p in points],'o-',label=label,color=color,markersize=4)
        for i,(x,y,n) in enumerate(points):
            if len(series)==1 and (len(points)<=12 or i%2==0):ax.annotate(f'n={n}',(x,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
            table.append(dict(series=label,size=x,rate=y,parcels=n))
    if baseline is not None:ax.axhline(baseline,linestyle='--',color='#7c4a15',label='Residential calendar-year reference')
    if not table:ax.text(.5,.5,'No properties with a known size under these settings',transform=ax.transAxes,ha='center')
    ax.set(title=title,xlabel=xlabel,ylabel='Citizen-initiated calls: '+('per estimated occupied year' if '59%' in note else 'mean per property'),ylim=(0,None))
    ax.grid(alpha=.2);ax.legend(fontsize=9)
    ax.margins(y=.15)
    discrete_axis(ax,xlabel)
    fig.text(.08,.02,'\n'.join(textwrap.wrap('Citizen initiated only; patrol and proactive-stop labels excluded. '+note,width=150)),fontsize=8,va='bottom')
    fig.tight_layout(rect=(0,.13,1,1))
    assert len(fig.axes)==1
    for extension in ['png','svg']:fig.savefig(out/(name+'.'+extension),dpi=140)
    plt.close(fig)
    pd.DataFrame(table,columns=['series','size','rate','parcels']).to_csv(out/(name+'.csv'),index=False)
    COUNTER+=1
    if COUNTER%20==0:print(f'Exported {COUNTER} individual citizen-only charts',flush=True)

def current_reports(root):
    report=json.loads((root/'direct_listing_calls/report_data.js').read_text(encoding='utf-8').removeprefix('window.DIRECT_REPORT=').removesuffix(';'))
    data=report['controls'];summary=report['summary']
    for cohort in ['every_licensed_address','matched_airbnb','at_or_above_approved','above_approved']:
        for size,label in SIZES.items():
            rows=[]
            for p in data['properties']:
                ls=p['listings']
                if cohort in ['at_or_above_approved','above_approved']:
                    ls=[l for l in ls if l['guests'] is not None and l['approved_guests'] is not None and (l['guests']>=l['approved_guests'] if cohort=='at_or_above_approved' else l['guests']>l['approved_guests'])]
                if cohort!='every_licensed_address' and not ls:continue
                if size in ['guests','bedrooms','capacity_difference']:
                    values=[l['overage' if size=='capacity_difference' else size] for l in ls]
                    values=[v for v in values if v is not None];value=max(values) if values else None
                else:value=p[size]
                if value is not None:rows.append(dict(size=value,permit_type=p['permit_type'],rates=p['rates']['citizen']))
            for grouping in ['exact','minimum']:
                thresholds=sorted({r['size'] for r in rows})
                for category in data['categories']:
                    lines=[]
                    for kind,title in TYPES.items():
                        points=[]
                        for x in thresholds:
                            members=[r for r in rows if r['permit_type']==kind and (r['size']>=x if grouping=='minimum' else r['size']==x)]
                            if members:points.append((x,float(np.mean([r['rates'][category]/.59 for r in members])),len(members)))
                        if points:lines.append((title,points,COLORS[kind]))
                    parking=category=='Parking complaints'
                    note=f"Period {summary['date_start']} to {summary['date_end']}. 59% booking-occupancy scenario. Each parcel counted once per group; zeros included. No amenity or above-average filter. Unknown sizes omitted."
                    if parking:note+=' '+summary['category_coverage_note']
                    name=f'current_direct__{cohort}__{size}__{grouping}__{slug(category)}'
                    title=('All citizen-initiated calls' if category=='All calls' else category)
                    curve(root,name,title+('*' if parking else '')+' | '+cohort.replace('_',' '),('Minimum ' if grouping=='minimum' else '')+label,lines,note,summary['measures']['citizen']['baselines'][category])

def historical_size(root):
    study=json.loads((root/'data.js').read_text(encoding='utf-8-sig').split('=',1)[1].strip().rstrip(';'))
    calls=citizen_only(pd.DataFrame(study['calls']));calls['pin']=calls.pin.str.replace(' ','')
    counts=calls.groupby('pin').size().to_dict();years=study['summary']['exposure_years']
    data=pd.read_csv(root/'size_plots/parcel_size_calls.csv').fillna('')
    eligible=set(pd.read_csv(root/'parcel_rates.csv',dtype=str).pin.str.replace(' ',''))
    data['direct']=data.pin.map(lambda p:counts.get(p.replace(' ',''),0))/years
    data['neighbors']=data.neighbor_pins.map(lambda s:sum(counts.get(p.replace(' ',''),0) for p in s.split(' | ') if p.replace(' ','') in eligible))/years
    data['combined']=data.direct+data.neighbors
    for size in ['bedrooms','guests']:
        data[size]=pd.to_numeric(data[size],errors='coerce');g=data.dropna(subset=[size]).groupby(size)
        series=[(label,[(x,float(part[col].mean()),len(part)) for x,part in g],color) for col,label,color in [('direct','Property','#2563eb'),('neighbors','Touching residential neighbors','#d97706'),('combined','Property + neighbors','#15803d')]]
        curve(root,'original_size__'+size,'Listing size and property/neighbor calls',SIZES[size],series,'Original published period 2024-09-21 to 2026-10-16. Calendar-year rates; no booking-occupancy adjustment. Each parcel once per size group.')

def historical_occupancy(root):
    for folder in ['occupancy_plots','occupancy_plots_commercial_excluded']:
        parcels=pd.read_csv(root/folder/'parcel_occupancy_calls.csv',dtype={'parcel_key':str})
        calls=citizen_only(pd.read_csv(root/folder/'matched_rental_calls.csv',dtype=str).fillna(''),'Initiation','Call Type').drop_duplicates('Call Number')
        categories=['Citizen calls overall']+calls['Call Type'].value_counts().head(6).index.tolist()
        for cohort in ['single_license','all_licensed']:
            frame=parcels[parcels.license_count.eq(1)].copy() if cohort=='single_license' else parcels.copy()
            for category in categories:
                selected=calls if category=='Citizen calls overall' else calls[calls['Call Type'].eq(category)]
                counts=selected.groupby('matched_rental_parcel').size()
                frame['selected_count']=frame.parcel_key.map(counts).fillna(0)
                points=[(x,float(part.selected_count.mean()),len(part)) for x,part in frame.groupby('total_licensed_capacity')]
                curve(root,f'{folder}__{cohort}__{slug(category)}',category+' | '+cohort.replace('_',' '),'Licensed guest capacity'+(' (parcel total)' if cohort=='all_licensed' else ''),[('Citizen-initiated calls',points,'#2563eb')],'Raw CAD period 2024-01-01 to 2024-09-20. Counts per parcel over that period; no annual or booking adjustment. '+('Saved commercial/hotel exclusions applied.' if 'excluded' in folder else 'Original complete matched license cohort.'))

def historical_neighbors(root):
    frame=pd.read_csv(root/'neighborhood_occupancy_plots/neighborhood_metrics.csv',dtype={'focal_pin':str})
    members=citizen_only(pd.read_csv(root/'neighborhood_occupancy_plots/neighborhood_call_memberships.csv',dtype=str).fillna(''),'Initiation','Call Type').drop_duplicates(['focal_pin','Call Number'])
    for cohort in ['single_license','all_licensed']:
        data=frame[frame.license_count.eq(1)].copy() if cohort=='single_license' else frame.copy()
        for category in ['All selected calls','Parking complaints','Noise complaints','Loud party','Nuisance']:
            selected=members if category=='All selected calls' else members[members.selected_category.eq(category)]
            counts=selected.groupby('focal_pin').size();data['rate']=data.focal_pin.map(counts).fillna(0)/data.property_count
            points=[(x,float(g.rate.mean()),len(g)) for x,g in data.groupby('licensed_capacity')]
            curve(root,f'neighborhood__{cohort}__{slug(category)}',category+' | rental and touching neighbors','Licensed guest capacity',[('Neighborhood calls / neighborhood parcels',points,'#2563eb')],'Raw CAD period 2024-01-01 to 2024-09-20. Supported single-family/duplex focal cohort. Each neighborhood: unique selected calls / (1 + eligible touching neighbors). Saved exclusions applied.')

def historical_direct(root):
    for source in sorted((root/'direct_listing_calls').glob('citizen_*_means.csv')):
        if not any(key in source.name for key in ['all_matched','above_average','minimum_threshold']):continue
        frame=pd.read_csv(source);xcolumn=frame.columns[0]
        for category in ['All calls','Parking complaints','Noise complaints','Loud party','Disturbance / nuisance']:
            col=category+'_adjusted_rate' if category+'_adjusted_rate' in frame else category
            if col not in frame:continue
            points=[(row[xcolumn],row[col],int(row.parcels)) for _,row in frame.iterrows() if pd.notna(row[col])]
            curve(root,'saved_direct__'+source.stem.removesuffix('_means')+'__'+slug(category),('All citizen-initiated calls' if category=='All calls' else category)+' | saved listing cohort',('Minimum ' if 'minimum' in source.name else '')+('Advertised guest capacity' if 'guests' in source.name else 'Advertised bedrooms'),[('Citizen-initiated calls',points,'#2563eb')],'2024-01-01 to 2026-10-16. 59% booking-occupancy scenario. Original saved listing coverage. '+('* Parking period 2024-01-01 to 2024-09-20; later parking unavailable.' if category=='Parking complaints' else ''))

def update_pages(root):
    for page in root.rglob('*.html'):
        if any(p in page.parts for p in ['.git','vendor','plots']):continue
        soup=BeautifulSoup(page.read_text(encoding='utf-8'),'html.parser');changed=False
        for image in list(soup.find_all('img')):
            href='../plots/README.md' if page.parent!=root else 'plots/README.md'
            link=soup.new_tag('a',href=href);link.string='Individual plots in plots/';image.replace_with(link);changed=True
        for anchor in soup.find_all(href=True):
            href=anchor['href']
            if href.endswith(('.svg','.png')) and 'study_map' not in href:
                anchor['href']='../plots/README.md' if page.parent!=root else 'plots/README.md';changed=True
        if changed:page.write_text(str(soup),encoding='utf-8')

def collect(root=ROOT):
    global COUNTER
    COUNTER=0;root=Path(root).resolve();out=root/'plots';out.mkdir(exist_ok=True)
    # This directory was created for generated figures only. Remove superseded sheets
    # and all-call exports, not original input logs or tabular source audits.
    for directory in [out]+[root/x for x in ['size_plots','occupancy_plots','occupancy_plots_commercial_excluded','neighborhood_occupancy_plots','direct_listing_calls']]:
        for path in directory.glob('*'):
            if path.suffix.lower() in ['.png','.svg'] or (directory==out and path.suffix=='.csv'):
                assert path.resolve().is_relative_to(root)
                if path.name=='study_map.png':continue
                path.unlink()
    current_reports(root)
    historical_size(root)
    historical_occupancy(root)
    historical_neighbors(root)
    historical_direct(root)
    update_pages(root)
    files=sorted(p for p in out.iterdir() if p.suffix.lower() in ['.png','.svg'])
    with (out/'manifest.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['file','series','bytes','sha256']);writer.writeheader()
        for p in files:writer.writerow(dict(file=p.name,series=p.name.split('__')[0],bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    pngs=[p for p in files if p.suffix=='.png']
    (out/'README.md').write_text('# Individual plot collection\n\nEvery chart is a separate PNG and SVG, with matching data CSVs. There are no subplot sheets. All call charts use citizen initiation only, with patrol, crime-hot-spot, traffic/subject-stop, park/walk/talk and community-engagement dispatch labels excluded. Original raw logs and audit records are preserved outside this collection. `manifest.csv` lists all image files.\n\n`current_direct__` exports the current address and occupancy cohorts across all five size options and exact/minimum-size groups. Owner/non-owner permit types remain separate lines on each chart; initiation is never split. These presets use 59% booking occupancy and no amenity or above-average filter. `original_size__`, `occupancy_plots__`, `occupancy_plots_commercial_excluded__`, `neighborhood__` and `saved_direct__` reproduce the earlier analysis families using citizen-only records and their stated periods/denominators.\n\nCurrent full span: January 1, 2024-October 16, 2026. Parking uses the supported January 1-September 20, 2024 period and is marked with *. Earlier snapshots retain their own labeled periods. A reference parcel map, if present, is not a call-rate chart. Arbitrary browser filter combinations were not recorded as historical artifacts.\n\n## PNG files\n\n'+'\n'.join(f'- [{p.name}]({p.name})' for p in pngs)+'\n',encoding='utf-8')
    print(f'Complete: {COUNTER} individual citizen-only charts, PNG and SVG plus data CSVs.',flush=True)
    return COUNTER

if __name__=='__main__':collect()
