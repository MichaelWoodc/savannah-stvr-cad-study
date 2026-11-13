"""Neighborhood mean nuisance calls by licensed parcel capacity, with backend type evidence."""
from pathlib import Path
from collections import defaultdict
import json
import re
import hashlib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from processing.cad_normalization import normalize_cad_address
from processing.citizen_only import select as citizen_only

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'neighborhood_occupancy_plots'

def run(root=ROOT):
    root=Path(root); out=root/'neighborhood_occupancy_plots'
    assessor=pd.read_csv(root/'raw_data/registvr_neighborhood_assessor.csv',dtype=str).fillna('')
    realtor=pd.read_csv(root/'raw_data/registvr_neighborhood_realtor.csv',dtype=str).fillna('')
    licenses=pd.read_csv(root/'processed_data/licenses/licenses_normalized.csv',dtype=str).fillna('')
    excluded=set(pd.read_csv(root/'excluded_properties.csv',dtype=str).PIN.str.replace(' ',''))
    realtor['pin']=realtor.pin.str.replace(' ','')
    real_groups={p:g for p,g in realtor.groupby('pin')}
    type_rows=[]
    for r in assessor.itertuples():
        sections=json.loads(r.residential_building_sections or '[]')
        types=[]
        for s in sections:
            types += [row[1] for row in s.get('table_rows',[]) if len(row)>1 and row[0]=='Type']
        group=real_groups.get(r.pin)
        descriptions=[]; unit_counts=[]; duplex=False; duplex_carriage=False
        if group is not None:
            for rr in group.itertuples():
                d=json.loads(rr.description_json or '{}')
                text=str(d.get('text') or '')
                units=d.get('units')
                descriptions.append(text)
                if units is not None: unit_counts.append(str(units))
                if rr.property_type=='multi_family' and str(units)=='2': duplex=True
                if rr.property_subtype.lower() in ('duplex','two_family','two-family'): duplex=True
                if rr.property_type=='multi_family' and str(units)=='3' and re.search(r'\bduplex\b',text,re.I) and re.search(r'\bcarriage\s+house\b',text,re.I): duplex_carriage=True
        bedrooms=pd.to_numeric(r.bedrooms,errors='coerce')
        residential=bool(pd.notna(bedrooms) and bedrooms>0 and r.pin not in excluded)
        classification='unresolved_or_other_building_type'
        evidence='No explicit supported property-type evidence'
        if duplex_carriage:
            classification='duplex_with_carriage_house'; evidence='Realtor multi_family, 3 units, explicit duplex and carriage house description'
        elif duplex:
            classification='duplex'; evidence='Realtor multi_family with 2 units or explicit duplex subtype'
        elif types==['1 - Single Family Residence'] and not any(float(u)>1 for u in unit_counts if u.replace('.','',1).isdigit()):
            classification='single_family'; evidence='One assessor Residential Building section, Type 1 - Single Family Residence'
        numeric_units={float(u) for u in unit_counts if u.replace('.','',1).isdigit()}
        if len(numeric_units)>1 or any(u>3 for u in numeric_units):
            classification='unresolved_or_other_building_type';evidence='Conflicting unit counts or more than three reported units'
        if not residential:
            classification='excluded_no_positive_bedrooms_or_saved_exclusion'
        type_rows.append(dict(parcel_key=r.pin,bedrooms=bedrooms,bedroom_residential=residential,
            property_type=classification,type_evidence=evidence,assessor_building_types=' | '.join(types),
            reported_unit_count=r.reported_unit_count,realtor_unit_counts=' | '.join(unit_counts),
            assessor_source_url=r.source_url,assessor_checked_at=r.checked_at))
    evidence=pd.DataFrame(type_rows).set_index('parcel_key')
    evidence.to_csv(out/'property_type_evidence.csv')
    residential=set(evidence.index[evidence.bedroom_residential])
    eligible=set(evidence.index[evidence.property_type.isin(['single_family','duplex','duplex_with_carriage_house'])])
    licenses['capacity']=pd.to_numeric(licenses['Max. occupancy'],errors='coerce')
    assert licenses['Permit Number'].is_unique
    capacity=licenses.groupby('source_apn_key').agg(capacity=('capacity','sum'),license_count=('Permit Number','size'))
    focal=sorted(set(capacity.index)&eligible)
    assert focal, 'No supported focal properties'
    links=pd.read_csv(out/'all_direct_boundary_links.csv',dtype={'focal_pin':str,'neighbor_pin':str})
    links=links[links.focal_pin.isin(focal)&links.neighbor_pin.isin(residential)].copy()
    assert not (links.focal_pin==links.neighbor_pin).any()
    assert not links.duplicated(['focal_pin','neighbor_pin']).any()
    links.to_csv(out/'included_neighbor_links.csv',index=False)
    neighborhoods={p:{p}|set(links.loc[links.focal_pin.eq(p),'neighbor_pin']) for p in focal}
    target=set().union(*neighborhoods.values())
    # Address candidates include the entire county, preventing false uniqueness in a selected subset.
    digest=pd.read_csv(out/'digest_parcel_addresses.csv',dtype=str).fillna('')
    address_pins=defaultdict(set)
    for r in digest.itertuples():
        a=normalize_cad_address(r.PropAddress_Full)
        if a['street_building_candidate_key']: address_pins[a['street_building_candidate_key']].add(r.parcel_key)
    for r in licenses.itertuples():
        if r.house_number and r.street_suffix: address_pins[r.normalized_building_address].add(r.source_apn_key)
    cad=pd.read_csv(root/'occupancy_plots/cad_rental_match_audit.csv',dtype=str).fillna('')
    def category(t):
        t=t.upper()
        if 'PARKING COMPLAINT' in t: return 'Parking complaints'
        if 'LOUD PARTY' in t: return 'Loud party'
        if 'NOISE' in t: return 'Noise complaints'
        if 'NUISANCE' in t and 'WPN' not in t: return 'Nuisance'
        return ''
    cad['selected_category']=cad['Call Type'].map(category)
    calls=cad[cad.selected_category.ne('')].copy()
    assignments=[]; methods=[]
    for r in calls.itertuples():
        candidates=address_pins.get(r.street_building_candidate_key,set()) if r.street_building_candidate_key else set()
        spatial=r.coordinate_parcel_candidates.split('|') if r.coordinate_parcel_candidates else []
        pin=''; method='no_unique_address'
        if len(candidates)==1:
            candidate=next(iter(candidates))
            if len(spatial)>1: method='ambiguous_coordinate_parcels'
            elif spatial and spatial[0]!=candidate: method='address_coordinate_conflict'
            else: pin=candidate; method='address_and_coordinate' if spatial else 'address_only'
        assignments.append(pin); methods.append(method)
    calls['assigned_parcel']=assignments; calls['neighborhood_match_method']=methods
    calls.to_csv(out/'selected_call_match_audit.csv',index=False)
    assigned=calls[calls.assigned_parcel.isin(target)&calls['Call Number'].ne('')].copy()
    ambiguity=assigned.groupby('Call Number')[['assigned_parcel','Call Type','Initiation']].nunique().gt(1).any(axis=1)
    bad=set(ambiguity.index[ambiguity])
    assigned[assigned['Call Number'].isin(bad)].to_csv(out/'conflicting_call_numbers.csv',index=False)
    assigned=assigned[~assigned['Call Number'].isin(bad)].drop_duplicates('Call Number')
    assigned=citizen_only(assigned,'Initiation','Call Type')
    assigned.to_csv(out/'matched_neighborhood_calls.csv',index=False)
    categories=['Parking complaints','Noise complaints','Loud party','Nuisance']
    rows=[]
    for pin, members in neighborhoods.items():
        c=assigned[assigned.assigned_parcel.isin(members)]
        row=dict(focal_pin=pin,property_type=evidence.loc[pin,'property_type'],
            licensed_capacity=capacity.loc[pin,'capacity'],license_count=capacity.loc[pin,'license_count'],
            neighbor_count=len(members)-1,property_count=len(members),selected_calls=len(c),
            calls_per_property=len(c)/len(members),citizen_calls=int(c.Initiation.eq('Cit Initiated').sum()))
        row['citizen_calls_per_property']=row['citizen_calls']/len(members)
        for cat in categories:
            row[cat]=int(c.selected_category.eq(cat).sum())
            row[cat+'_per_property']=row[cat]/len(members)
        rows.append(row)
    metrics=pd.DataFrame(rows)
    assert metrics.property_count.eq(metrics.neighbor_count+1).all()
    assert np.allclose(metrics.calls_per_property*metrics.property_count,metrics.selected_calls)
    assert not set(metrics.focal_pin)&excluded
    metrics.to_csv(out/'neighborhood_metrics.csv',index=False)
    # Membership audit uses named CSV columns instead of tuple-renamed call-number fields.
    membership_frames=[]
    for pin,members in neighborhoods.items():
        part=assigned[assigned.assigned_parcel.isin(members)].copy(); part.insert(0,'focal_pin',pin);membership_frames.append(part)
    pd.concat(membership_frames,ignore_index=True).to_csv(out/'neighborhood_call_memberships.csv',index=False)
    pages=[]
    for name,frame in [('single_license',metrics[metrics.license_count.eq(1)]),('all_licensed',metrics)]:
        if frame.empty: continue
        mean_cols=['calls_per_property','citizen_calls_per_property']+[cat+'_per_property' for cat in categories]
        means=frame.groupby('licensed_capacity')[mean_cols].mean()
        means['rental_parcels']=frame.groupby('licensed_capacity').size()
        means.to_csv(out/f'{name}_group_means.csv')
        xmax=max(6,int(np.ceil(means.index.max()/2)*2))
        xlabel='Licensed occupancy limit' if name=='single_license' else 'Total licensed occupancy on rental parcel'
        def axes_style(ax):
            ax.set_xticks(range(4,xmax+1,2)); ax.set_xlim(3.8,xmax+.2)
            ax.set(xlabel=xlabel,ylabel='Mean neighborhood calls per property',ylim=(0,None));ax.grid(alpha=.2)
        fig,ax=plt.subplots(figsize=(11,6))
        ax.plot(means.index,means.calls_per_property,'o-',label='All selected calls')
        ax.plot(means.index,means.citizen_calls_per_property,'o-',label='Citizen-initiated selected calls')
        for x,r in means.iterrows(): ax.annotate(f'n={int(r.rental_parcels)}',(x,r.calls_per_property),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
        axes_style(ax); ax.set_ylim(0,max(.01,means.calls_per_property.max()*1.25));ax.legend()
        ax.set_title('Rental and directly touching residential neighbors ('+name.replace('_',' ')+')')
        fig.text(.08,.02,'Parking, noise, loud party and nuisance calls, Jan 1-Sep 20, 2024. Each neighborhood: unique calls / parcel count.',fontsize=9)
        fig.tight_layout(rect=(0,.06,1,1))
        for ext in ['png','svg']:fig.savefig(out/f'{name}_overall.{ext}',dpi=160)
        plt.close(fig)
        fig,axs=plt.subplots(2,2,figsize=(13,9))
        for ax,cat in zip(axs.flat,categories):
            ax.plot(means.index,means[cat+'_per_property'],'o-');axes_style(ax);ax.set_title(cat)
        fig.suptitle('Selected call types: rental + directly touching residential neighbors')
        fig.tight_layout(rect=(0,.03,1,.96))
        for ext in ['png','svg']:fig.savefig(out/f'{name}_categories.{ext}',dpi=160)
        plt.close(fig)
        pages.append(f'<h2>{name.replace("_"," ").title()}</h2><p>{len(frame)} rental parcels. <a href="{name}_group_means.csv">Data and sample counts</a></p><img src="{name}_overall.svg" alt="Neighborhood means by occupancy"><img src="{name}_categories.svg" alt="Parking, noise, party, nuisance subplots">')
    evidence.loc[evidence.index.isin(capacity.index)&~evidence.index.isin(focal)].to_csv(out/'excluded_or_unresolved_rental_types.csv')
    call_types=calls.groupby(['selected_category','Call Type']).size().rename('full_cad_rows').reset_index()
    call_types.to_csv(out/'included_call_type_definitions.csv',index=False)
    summary=dict(focal_rental_parcels=len(metrics),focal_types=metrics.property_type.value_counts().to_dict(),
        residential_neighbor_links=len(links),zero_neighbor_rentals=int(metrics.neighbor_count.eq(0).sum()),
        unique_calls_in_included_neighborhoods=len(assigned),call_memberships=int(metrics.selected_calls.sum()),
        conflicting_call_numbers=len(bad), formula='For each focal parcel: unique selected neighborhood calls / (1 + eligible touching neighbors); plots show arithmetic mean of these ratios within occupancy groups.',
        source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['raw_data/registvr_neighborhood_assessor.csv','raw_data/registvr_neighborhood_realtor.csv','excluded_properties.csv','raw_data/CAD-log.xlsx','raw_data/Parcel_Digest_2025.geojson']})
    (out/'analysis_summary.json').write_text(json.dumps(summary,indent=2))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rentals and touching neighbors</title><style>body{font:17px system-ui;max-width:1200px;margin:35px auto;padding:20px;color:#172334}img{width:100%}p{line-height:1.6}</style><h1>Rental and directly touching neighbors</h1>
<p>For each rental: add unique selected calls on the rental parcel and its directly touching residential neighbors, then divide by the total number of parcels in that group. Plotted points are the arithmetic mean of those individual neighborhood ratios at each licensed occupancy. Zero-call parcels remain included. Rentals without eligible neighbors use a denominator of one. Shared neighbors can belong to multiple neighborhoods, so points are not independent.</p>
<p>Focal rentals require positive assessor bedrooms and explicit evidence for single-family, duplex, or duplex with carriage house. A single assessor Type 1 building section supports single-family; a Realtor multi-family record with two units or explicit duplex subtype supports duplex; three units plus explicit duplex and carriage-house text supports the third category. Building-card count and rental-license count are not used as dwelling counts. Unknown or conflicting configurations stay out of the focal cohort. Neighbors can be any positive-bedroom residential parcel; they need not be rentals or the same building type. All saved commercial/hotel exclusions apply to focal parcels and neighbors.</p>
<p>A neighbor shares more than 0.1 m of parcel boundary, measured in UTM zone 17N. Corners, across-road parcels and overlapping interiors do not qualify. Parcels, not buildings or rental units, are the denominator. The all-licensed view sums license occupancy limits per focal parcel; single-license view uses the individual license limit.</p>
<p>Selected calls: parking complaints, all noise complaints including past/phone/online variants, loud party, and non-weapon nuisance. Private parking tows and weapon nuisance are excluded. Overall includes all initiation types plus a citizen-only series. Subplots use all initiation types. Exact call types are in the linked definition file. Calls need a unique normalized recorded-address parcel; coordinate agreement corroborates, coordinate conflicts exclude, and missing coordinate matches permit address-only attribution. Intersections and ranged addresses are not assigned. Calls are deduplicated by call number in each neighborhood.</p>
<p>CAD period: January 1-September 20, 2024. Current licenses and later assessor/property snapshots do not establish historical 2024 configuration or license activity. These are recorded calls for service, not verified 911-origin records or proof of guest involvement. Types and missing bedroom data can limit coverage.</p>'''
    coverage='<p>Included focal property types: '+', '.join(f'{k.replace("_"," ")}: {v}' for k,v in summary['focal_types'].items())+'.'
    if not summary['focal_types'].get('duplex_with_carriage_house'):
        coverage+=' No duplex-with-carriage-house record met the stated evidence rules in this export.'
    coverage+='</p>'
    (out/'index.html').write_text(html+coverage+'\n'.join(pages)+'''<h2>Audits</h2><p><a href="analysis_summary.json">Summary</a> | <a href="neighborhood_metrics.csv">Per-rental calculations</a> | <a href="included_neighbor_links.csv">Touching-neighbor links</a> | <a href="property_type_evidence.csv">Backend property-type evidence</a> | <a href="excluded_or_unresolved_rental_types.csv">Excluded/unresolved rental types</a> | <a href="included_call_type_definitions.csv">Included call types</a> | <a href="neighborhood_call_memberships.csv">Call memberships</a></p></html>''',encoding='utf-8')
    from processing.collect_plots import collect
    collect(root)
    return summary

if __name__=='__main__': print(json.dumps(run(),indent=2))
