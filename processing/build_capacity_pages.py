"""Create two occupancy-screen report pages while retaining the shared live controls."""
import json
from pathlib import Path
import pandas as pd

def build(root,out,controls):
    root=Path(root);out=Path(out)
    template=(out/'index.html').read_text(encoding='utf-8')
    listings=[dict(r,parcel_permit_type=p['permit_type']) for p in controls['properties'] for r in p['listings']]
    assert len({r['listing_id'] for r in listings})==len(listings)
    known=[r for r in listings if r['guests'] is not None and r['approved_guests'] is not None]
    summary={}
    for mode,filename,title in [
        ('at_or_above','at_or_above_approved.html','Listings at or above approved occupancy'),
        ('above','above_approved.html','Listings advertising above approved occupancy')]:
        selected=[r for r in known if r['guests']>=r['approved_guests']] if mode=='at_or_above' else [r for r in known if r['guests']>r['approved_guests']]
        summary[mode]=dict(listings=len(selected),parcels=len({r['pin'] for r in selected}),
            exactly_at_limit=sum(r['guests']==r['approved_guests'] for r in selected),
            above_limit=sum(r['guests']>r['approved_guests'] for r in selected),
            odd_advertised_capacity=sum(float(r['guests']).is_integer() and r['guests']%2!=0 for r in selected))
        summary[mode]['by_permit_type']={kind:dict(listings=sum(r['parcel_permit_type']==kind for r in selected),
            parcels=len({r['pin'] for r in selected if r['parcel_permit_type']==kind})) for kind in ['owner','non_owner','mixed','unknown']}
        rule='Advertised guests >= recorded approved limit. Equality is included.' if mode=='at_or_above' else 'Advertised guests > recorded approved limit, including an overage of just one guest. Listings exactly at the limit are excluded.'
        note=f'''<section><h2>Page occupancy rule</h2><p><strong>{rule}</strong> This rule stays active for every graph, table, export and the parking fallback.</p><p>The current snapshot contains {len(selected)} qualifying listings across {summary[mode]['parcels']} parcels; {summary[mode]['odd_advertised_capacity']} advertise an odd guest capacity. Amenity and other controls can narrow this cohort further.</p><p>For an integer bedroom count, both two per bedroom and two per bedroom plus two produce an even limit. An odd advertised capacity is retained as written: five guests under an approved limit of six is within that recorded limit, while seven is above it. Oddness alone is not an over-limit finding. Recorded approved capacities are authoritative.</p><p>The default plot groups by <strong>advertised guests minus approved limit</strong>. Zero means exactly at the limit; one means one advertised guest above it. Each parcel counts once, using its largest qualifying listing difference. Above-limit advertising is a screening flag, not proof of actual occupancy or a verified legal violation.</p><p><a href="{mode}_approved_listings.csv">Download the page's full qualifying listing snapshot</a></p></section>'''
        page=template.replace('<title>Calls at licensed rentals</title>',f'<title>{title}</title>')
        page=page.replace('<h1>Calls at licensed rentals</h1>',f'<h1>{title}</h1>'+note)
        page=page.replace('<script src="report_data.js">','<script>window.CAPACITY_PAGE='+json.dumps({'mode':mode})+';</script><script src="report_data.js">')
        page=page.replace('Always graph all matched properties*','Always graph the page occupancy cohort*')
        page=page.replace('while using the full matched property cohort','while using the full page occupancy cohort')
        (out/filename).write_text(page,encoding='utf-8')
        pd.DataFrame([dict(listing_id=r['listing_id'],url=r['url'],title=r['title'],pin=r['pin'],
            advertised_guests=r['guests'],approved_guests=r['approved_guests'],difference=r['overage'],
            odd_advertised_capacity=bool(r['guests']%2),advertised_bedrooms=r['bedrooms'],
            matched_licensed_bedrooms=r['licensed_bedrooms'],permits=' | '.join(r['permits']),
            matched_certificate_types=' | '.join(r['permit_types']),parcel_permit_type=r['parcel_permit_type'],
            onsite_evidence=' | '.join(r['onsite']),mention_evidence=' | '.join(r['mention'])) for r in selected]).to_csv(out/f'{mode}_approved_listings.csv',index=False)
    assert summary['at_or_above']['above_limit']==summary['above']['listings']
    (out/'capacity_page_summary.json').write_text(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];out=root/'direct_listing_calls'
    data=json.loads((out/'report_data.js').read_text(encoding='utf-8').removeprefix('window.DIRECT_REPORT=').removesuffix(';'))
    print(json.dumps(build(root,out,data['controls']),indent=2))
