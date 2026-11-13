"""Match current license inventory to CAD addresses/parcel polygons and plot occupancy."""
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from processing.citizen_only import select as citizen_only
from processing.cad_normalization import normalize_cad_address

def run(root, exclude_commercial=False):
    root = Path(root)
    out = root / ('occupancy_plots_commercial_excluded' if exclude_commercial else 'occupancy_plots')
    out.mkdir(exist_ok=True)
    licenses = pd.read_csv(root/'processed_data/licenses/licenses_normalized.csv', dtype=str).fillna('')
    cad = pd.read_csv(root/'processed_data/cad/cad_normalized.csv', dtype=str).fillna('')
    features = json.loads((root/'raw_data/Parcel_Digest_2025.geojson').read_text(encoding='utf-8-sig'))['features']
    # Keep every digest parcel in the spatial index so coordinates at other properties
    # can contradict an address candidate. No nearest-point or buffer attribution.
    geoms, pins, props = [], [], {}
    for f in features:
        p = f['properties']; pin = str(p['PIN']).replace(' ', '').upper()
        props.setdefault(pin, []).append(p)
        if f['geometry']:
            g = shape(f['geometry'])
            if not g.is_empty:
                geoms.append(g); pins.append(pin)
    del features
    tree = STRtree(geoms)
    licenses['parcel_key'] = licenses.source_apn_key.str.upper()
    excluded_pins = set()
    if exclude_commercial:
        exclusion_table = pd.read_csv(root/'excluded_properties.csv', dtype=str).fillna('')
        excluded_pins = set(exclusion_table.PIN.str.replace(r'\s+', '', regex=True).str.upper())
        exclusion_table.to_csv(out/'applied_property_exclusions.csv', index=False)
    licenses['excluded_by_existing_property_list'] = licenses.parcel_key.isin(excluded_pins)
    licenses['parcel_found'] = licenses.parcel_key.isin(props)
    licenses['occupancy_numeric'] = pd.to_numeric(licenses['Max. occupancy'], errors='coerce')
    licenses.to_csv(out/'license_parcel_audit.csv', index=False)
    # A permit contributes capacity once; unresolved duplicate permits fail loudly.
    assert licenses['Permit Number'].ne('').all()
    repeated = licenses[licenses['Permit Number'].duplicated(keep=False)]
    assert repeated.empty, 'Duplicate permits require review before capacity aggregation'
    matched = licenses[licenses.parcel_found].copy()
    parcels = matched.groupby('parcel_key').agg(license_count=('Permit Number','size'),
        total_licensed_capacity=('occupancy_numeric','sum'),
        capacity_known=('occupancy_numeric',lambda s: s.notna().all() and s.gt(0).all()))
    addresses = defaultdict(set)
    for row in matched.itertuples():
        key = row.normalized_building_address
        if key and row.house_number and row.street_suffix:
            addresses[key].add(row.parcel_key)
    for pin in parcels.index:
        for p in props[pin]:
            a = normalize_cad_address(p.get('PropAddress_Full', ''))
            if a['street_building_candidate_key']:
                addresses[a['street_building_candidate_key']].add(pin)
    cache = {}
    def locate(lat, lon):
        key = (lat, lon)
        if key not in cache:
            try:
                y, x = float(lat), float(lon)
                if not (-90 <= y <= 90 and -180 <= x <= 180) or (x == 0 and y == 0):
                    raise ValueError()
                ids = tree.query(Point(x,y), predicate='intersects')
                cache[key] = sorted({pins[i] for i in ids})
            except ValueError:
                cache[key] = []
        return cache[key]
    assigned, methods, coordinate_pins = [], [], []
    for r in cad.itertuples():
        candidates = addresses.get(r.street_building_candidate_key, set()) if r.street_building_candidate_key else set()
        spatial = locate(r.Latitude, r.Longitude)
        pin, method = '', 'not_matched_to_rental'
        # Require an unambiguous rental address. Coordinates corroborate or flag it;
        # coordinate-only calls, intersections and block locations are not attributed.
        if len(candidates) > 1:
            method = 'ambiguous_rental_address'
        elif len(candidates) == 1:
            candidate = next(iter(candidates))
            if len(spatial) > 1:
                method = 'ambiguous_coordinate_parcels'
            elif spatial and spatial[0] != candidate:
                method = 'address_coordinate_conflict'
            else:
                pin = candidate
                method = 'address_and_coordinate' if spatial else 'address_only_no_coordinate_parcel'
        assigned.append(pin); methods.append(method); coordinate_pins.append('|'.join(spatial))
    cad['matched_rental_parcel'] = assigned
    cad['rental_match_method'] = methods
    cad['coordinate_parcel_candidates'] = coordinate_pins
    cad.to_csv(out/'cad_rental_match_audit.csv', index=False)
    calls = cad[cad.matched_rental_parcel.ne('') & cad['Call Number'].ne('')].copy()
    # Inconsistent repeated call numbers cannot silently enter several parcels/types.
    conflicts = calls.groupby('Call Number').agg(parcels=('matched_rental_parcel','nunique'),
        types=('Call Type','nunique'), initiations=('Initiation','nunique'))
    bad_numbers = conflicts.index[(conflicts > 1).any(axis=1)]
    calls[calls['Call Number'].isin(bad_numbers)].to_csv(out/'conflicting_call_numbers.csv',index=False)
    calls = calls[~calls['Call Number'].isin(bad_numbers)].drop_duplicates('Call Number')
    excluded_parcel_count = int(parcels.index.isin(excluded_pins).sum())
    excluded_call_count = int(calls.matched_rental_parcel.isin(excluded_pins).sum())
    if exclude_commercial:
        calls[calls.matched_rental_parcel.isin(excluded_pins)].to_csv(out/'excluded_rental_calls.csv', index=False)
        parcels[parcels.index.isin(excluded_pins)].to_csv(out/'excluded_rental_parcels.csv')
        calls = calls[~calls.matched_rental_parcel.isin(excluded_pins)].copy()
        parcels = parcels[~parcels.index.isin(excluded_pins)].copy()
        assert not calls.matched_rental_parcel.isin(excluded_pins).any()
        assert not parcels.index.isin(excluded_pins).any()
    calls=citizen_only(calls,'Initiation','Call Type')
    calls.to_csv(out/'matched_rental_calls.csv', index=False)
    citizen = calls
    top = citizen['Call Type'].value_counts().head(6).index.tolist()
    for name, frame in [('all_calls',calls), ('citizen_calls',citizen)]:
        parcels[name] = frame.groupby('matched_rental_parcel').size().reindex(parcels.index,fill_value=0)
    for i, t in enumerate(top):
        parcels[f'type_{i}'] = citizen[citizen['Call Type'].eq(t)].groupby('matched_rental_parcel').size().reindex(parcels.index,fill_value=0)
    assert calls['Call Number'].is_unique
    assert calls.matched_rental_parcel.isin(parcels.index).all()
    assert parcels.all_calls.sum() == len(calls)
    assert parcels.citizen_calls.sum() == len(citizen)
    assert (parcels.citizen_calls <= parcels.all_calls).all()
    parcels.to_csv(out/'parcel_occupancy_calls.csv')
    tables = []
    for cohort, frame, xlabel in [
        ('single_license',parcels[parcels.license_count.eq(1) & parcels.capacity_known], 'Licensed occupancy limit (one license per parcel)'),
        ('all_licensed',parcels[parcels.capacity_known], 'Total licensed occupancy on parcel (sum of license limits)')]:
        grouped = frame.groupby('total_licensed_capacity')
        means = grouped[['all_calls','citizen_calls']+[f'type_{i}' for i in range(len(top))]].mean()
        means['parcels'] = grouped.size()
        means.to_csv(out/f'{cohort}_group_means.csv')
        fig, ax = plt.subplots(figsize=(11,6))
        for col, label in [('all_calls','All recorded calls'),('citizen_calls','Citizen-initiated calls')]:
            ax.plot(means.index, means[col], 'o-', label=label)
        for x, row in means.iterrows():
            ax.annotate(f'n={int(row.parcels)}',(x,row.all_calls),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
        title = 'Calls at licensed rental properties (single license only)' if cohort == 'single_license' else 'Calls at licensed rental properties  -  '+cohort.replace('_',' ')
        ax.set(xlabel=xlabel,ylabel='Mean calls per parcel during CAD period',ylim=(0,None),title=title)
        occupancy_max = max(6, int(np.ceil(means.index.max() / 2) * 2))
        ax.set_xticks(np.arange(4, occupancy_max + 1, 2))
        ax.set_xlim(4, occupancy_max)
        ax.legend(); ax.grid(alpha=.2)
        fig.text(.08,.02,'January 1–September 20, 2024. Zero-call parcels included; no neighbor calls. Current license inventory, not verified 2024 status.',fontsize=9)
        fig.tight_layout(rect=(0,.06,1,1))
        for ext in ['png','svg']: fig.savefig(out/f'{cohort}_overall.{ext}',dpi=160)
        plt.close(fig)
        fig, axes = plt.subplots(2,3,figsize=(15,9),squeeze=False)
        for i, ax in enumerate(axes.flat):
            if i >= len(top): ax.set_visible(False); continue
            ax.plot(means.index,means[f'type_{i}'],'o-',color='#2563eb')
            ax.set(title=top[i], xlabel=xlabel, ylabel='Mean citizen-initiated calls / parcel',ylim=(0,None))
            ax.set_xticks(np.arange(4, occupancy_max + 1, 2))
            ax.set_xlim(4, occupancy_max)
            ax.grid(alpha=.2)
        fig.suptitle('Six most frequent citizen-initiated call types at matched rental parcels')
        fig.text(.04,.015,'Same CAD period and zero-call denominators as overall plot. Separate y-axis scales. Types selected across all matched rental parcels.',fontsize=10)
        fig.tight_layout(rect=(0,.05,1,.96))
        for ext in ['png','svg']: fig.savefig(out/f'{cohort}_categories.{ext}',dpi=160)
        plt.close(fig)
        tables.append(f'<h2>{cohort.replace("_"," ").title()}</h2><p>{len(frame)} parcels. <a href="{cohort}_group_means.csv">Group means and sample counts</a></p><img src="{cohort}_overall.svg" alt="Overall calls by licensed occupancy"><img src="{cohort}_categories.svg" alt="Call category subplots">')
    summary = dict(license_rows=len(licenses), unmatched_license_apns=int((~licenses.parcel_found).sum()),matched_license_parcels=len(parcels),
        single_license_parcels=int(parcels.license_count.eq(1).sum()),cad_rows=len(cad),matched_unique_calls=len(calls),
        matched_citizen_calls=len(citizen),conflicting_call_numbers=len(bad_numbers), match_methods=cad.rental_match_method.value_counts().to_dict(),
        top_citizen_call_types=top, source_sha256={str(p):hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['raw_data/CAD-log.xlsx','raw_data/Licensed Short-Term Rental Properties (1).xlsx','raw_data/Parcel_Digest_2025.geojson']})
    summary.update(commercial_exclusions_applied=exclude_commercial,
                   excluded_matched_parcels=excluded_parcel_count,
                   excluded_matched_unique_calls=excluded_call_count,
                   excluded_license_rows=int(licenses.excluded_by_existing_property_list.sum()))
    if exclude_commercial:
        summary['source_sha256']['excluded_properties.csv'] = hashlib.sha256((root/'excluded_properties.csv').read_bytes()).hexdigest()
    (out/'analysis_summary.json').write_text(json.dumps(summary,indent=2))
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Licensed occupancy and rental-property calls</title><style>body{font:17px system-ui;max-width:1250px;margin:35px auto;padding:20px;color:#172334}img{width:100%}p{line-height:1.6}</style><h1>Licensed occupancy and rental-property calls</h1><p>Recorded-address CAD calls, not confirmed rental-guest incidents or verified 911-origin calls. January 1–September 20, 2024. Current complete license inventory is used; historical license activity in 2024 is unknown. These are descriptive counts over the supplied period, with no occupancy or annual adjustment.</p><p>Single-license parcels support comparison by individual licensed occupancy. The second set includes all APN-matched licensed parcels and sums their license limits, a parcel capacity measure rather than an individual rental limit. Each parcel appears once; zero-call parcels remain included. Calls to shared parcels cannot be attributed to individual units. Different occupancy groups can differ in property use, number of units and other characteristics.</p><p>Exact normalized license or digest situs addresses generate candidates via license APNs. A unique coordinate parcel corroborates the address or excludes it if conflicting; address-only matches are retained when no coordinate parcel is found. Coordinate-only, intersection, block and ranged-address calls are not attributed. No nearby/neighbor calls are added. Duplicate call numbers count once; conflicting repetitions are excluded. No fuzzy matching. Unmatched license APNs and ambiguous calls remain in audit files.</p><p>The six subplots are the most frequent citizen-initiated call types across matched rentals, selected from this log rather than judged to be guest-related. Overall plots include all initiation types and a separate citizen-initiated series. Small groups can be unstable. Lines connect group means, not fitted relationships.</p>'''+'\n'.join(tables)+'<p>Local audit downloads: <a href="analysis_summary.json">Summary</a> - <a href="license_parcel_audit.csv">License matches</a> - <a href="matched_rental_calls.csv">Matched calls</a> - <a href="parcel_occupancy_calls.csv">Parcel counts</a> - <a href="cad_rental_match_audit.csv">Full CAD match audit</a></p></html>',encoding='utf-8')
    if exclude_commercial:
        page = out/'index.html'
        html = page.read_text(encoding='utf-8')
        banner = (f'<h2>Commercial and hotel exclusions applied</h2><p>Uses every PIN in the existing '
                  f'<a href="../excluded_properties.csv">excluded_properties.csv</a>, including commercial properties, '
                  f'hotels/lodging and the saved commercial-call-threshold exclusions. The threshold is not recalculated '
                  f'from this earlier CAD period. Removed {excluded_parcel_count} matched parcels and {excluded_call_count} '
                  f'unique matched calls from numerators and denominators. Call-type rankings are recomputed after exclusion. '
                  f'The full CAD match audit retains pre-exclusion assignments; the plotted matched-call export is filtered. '
                  f'<a href="../occupancy_plots/index.html">Original version</a> - '
                  f'<a href="excluded_rental_parcels.csv">Excluded rental parcels</a> - '
                  f'<a href="excluded_rental_calls.csv">Excluded calls</a></p>')
        html = html.replace('<h1>Licensed occupancy and rental-property calls</h1>', '<h1>Licensed occupancy and rental-property calls</h1>'+banner)
        page.write_text(html,encoding='utf-8')
    page=out/'index.html'
    page.write_text(page.read_text(encoding='utf-8').replace('</html>', '<p><a href="../neighborhood_occupancy_plots/index.html">New analysis: rentals and directly touching neighbors</a></p></html>'),encoding='utf-8')
    from processing.collect_plots import collect
    collect(root)
    return summary

if __name__ == '__main__':
    print(json.dumps(run(Path(__file__).resolve().parents[1]),indent=2))
