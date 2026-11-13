"""Package ten ranked plots and their exact underlying property/call cohorts."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np
import pandas as pd
from processing.citizen_only import select as citizen_only
from processing.collect_plots import TYPES,SIZES

ROOT=Path(__file__).resolve().parents[1]

def build(root=ROOT):
    root=Path(root);out=root/'top_correlations';out.mkdir(exist_ok=True)
    for previous in out.iterdir():
        if previous.name[:2].isdigit() and previous.name[2:4]=='__' and previous.suffix in ['.png','.svg','.csv']:
            assert previous.resolve().is_relative_to(out.resolve())
            previous.unlink()
    source=root/'plots_with_trends_with_averages'
    ranked=pd.read_csv(source/'increasing_plot_rankings.csv')
    ranked=ranked[ranked.supported_increase & ranked.slope.gt(0)]
    picks=ranked.drop_duplicates('data_signature').drop_duplicates('plot').head(10).copy()
    assert len(picks)==10
    report=json.loads((root/'direct_listing_calls/report_data.js').read_text(encoding='utf-8').removeprefix('window.DIRECT_REPORT=').removesuffix(';'))
    assert set(report['summary']['measures'])=={'citizen'}
    data=report['controls'];summary=report['summary']
    calls=citizen_only(pd.read_csv(root/'processed_data/full_period_calls/combined_calls.csv',dtype=str).fillna(''))
    assert calls.number.is_unique
    def category(row):
        kind=row.type.upper()
        if 'PARKING COMPLAINT' in kind:return 'Parking complaints'
        if 'LOUD PARTY' in kind:return 'Loud party'
        if 'NOISE' in kind:return 'Noise complaints'
        if row.category=='Disturbance / nuisance':return 'Disturbance / nuisance'
        return 'Other'
    calls['analysis_category']=[category(r) for r in calls.itertuples()]
    categories=set(picks.category)
    call_map={}
    for r in calls[calls.analysis_category.isin(categories)].itertuples():
        call_map.setdefault(r.pin,[]).append(dict(number=r.number,date=r.date,type=r.type,category=r.analysis_category,
            address=r.address,source=r.source))
    reverse={v:k for k,v in TYPES.items()};factors=[];properties={};audit=[]
    for rank,(_,row) in enumerate(picks.iterrows(),1):
        parts=row['plot'].split('__');cohort=parts[1];size=parts[2];kind=reverse[row['series']]
        ids=[]
        for p in data['properties']:
            if p['permit_type']!=kind:continue
            ls=p['listings']
            if cohort=='matched_airbnb' and not ls:continue
            if size in ['guests','bedrooms']:
                known=[l[size] for l in ls if l[size] is not None]
                value=max(known) if known else None
            else:value=p[size]
            if value is None:continue
            ids.append(p['pin'])
            audit.append(dict(factor_rank=rank,pin=p['pin'],address=p['address'],size=value,
                category=row['category'],category_calls=p['counts']['citizen'][row['category']],
                adjusted_annual_rate=p['rates']['citizen'][row['category']]/.59,
                permit_type=p['permit_type'],listing_urls=' | '.join(l['url'] for l in ls)))
            if p['pin'] not in properties:
                properties[p['pin']]=dict(pin=p['pin'],address=p['address'],permit_type=p['permit_type'],
                    approved_guests=p['approved_guests'],licensed_bedrooms=p['licensed_bedrooms'],license_count=p['license_count'],
                    listings=ls,counts=p['counts']['citizen'],rates={c:v/.59 for c,v in p['rates']['citizen'].items()},
                    calls=sorted(call_map.get(p['pin'],[]),key=lambda c:(c['date'],c['number']),reverse=True))
        assert len(ids)==row['parcels'],(row['plot'],len(ids),row['parcels'])
        events=sum(properties[pin]['counts'][row['category']] for pin in ids)
        assert np.isclose(events,row['category_events'])
        for pin in ids:
            actual=sum(c['category']==row['category'] for c in properties[pin]['calls'])
            assert actual==properties[pin]['counts'][row['category']],(pin,row['category'],actual)
        base=f'{rank:02d}__'+row['plot']
        for extension in ['png','svg','csv']:shutil.copy2(source/(row['plot']+'.'+extension),out/(base+'.'+extension))
        factors.append(dict(id=str(rank),rank=rank,plot=row['plot'],size=size,size_label=SIZES[size],
            category=row['category'],permit_type=kind,series=row['series'],cohort=cohort,
            cohort_label='Matched Airbnb properties' if cohort=='matched_airbnb' else 'Every covered licensed property',
            parcels=len(ids),events=events,property_ids=ids,slope=float(row.slope),r2=float(row.r2_group_means),
            iqr_rise=float(row.fitted_iqr_rise),relative_rise=float(row.standardized_rise_fraction),
            png=base+'.png',svg=base+'.svg',csv=base+'.csv'))
    picks.insert(0,'rank',range(1,11));picks.to_csv(out/'top_10_rankings.csv',index=False)
    pd.DataFrame(audit).to_csv(out/'factor_property_calls.csv',index=False)
    payload=dict(factors=factors,properties=properties,features=data['features'],summary=dict(date_start=summary['date_start'],date_end=summary['date_end'],
        occupancy=.59,parking_note=summary['category_coverage_note'],citizen_only=True,proactive_excluded=True,
        unique_properties=len(properties),factor_property_memberships=len(audit),
        source_rankings_sha256=hashlib.sha256((source/'increasing_plot_rankings.csv').read_bytes()).hexdigest(),
        source_call_records_sha256=hashlib.sha256((root/'processed_data/full_period_calls/combined_calls.csv').read_bytes()).hexdigest(),
        source_match_audit_sha256=hashlib.sha256((root/'processed_data/listing_matches/source_match_audit.csv').read_bytes()).hexdigest()))
    (out/'data.js').write_text('window.TOP_CORRELATIONS='+json.dumps(payload,allow_nan=False)+';',encoding='utf-8')
    (out/'README.md').write_text('# Top 10 upward associations\n\nOpen [the interactive property explorer](index.html). This folder contains exactly ten plots in PNG and SVG, with the corresponding group CSVs. Plots include trends and averages; images are linked rather than embedded in the page.\n\nThe selection follows the existing exploratory ranking, removing duplicate series/data and duplicate plots. It ranks exact-size associations by fitted increase per one SD of size relative to mean rate, with parcel/event/size-level support limits. It is not a ranking by Pearson correlation, a causal effect, or a finding of violations. All ten currently involve non-owner-occupied properties. Some cohorts overlap.\n\nClick a factor to inspect its exact source cohort, including zero-call parcels. Use size/search and calls-only filters to narrow the list. Each property expands to matching category call records and Airbnb evidence. Counts match the ranked plot, count each parcel once, and exclude patrol/proactive records. Rates use the fixed 59% scenario and the stated category period.\n\nRebuild with `python -m processing.top_correlations`.\n\n'+ '\n'.join(f"- {f['rank']}. [{f['size_label']} / {f['category']} / {f['cohort_label']}]({f['png']})" for f in factors)+'\n',encoding='utf-8')
    print(f'Packaged 10 plots, {len(properties)} unique properties and {len(audit)} factor/property memberships.')
    return payload

if __name__=='__main__':build()
