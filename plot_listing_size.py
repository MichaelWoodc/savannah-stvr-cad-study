"""Rebuild size/call plots and auditable CSVs from the published study."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'size_plots'
OUT.mkdir(exist_ok=True)
study = json.loads((ROOT / 'data.js').read_text(encoding='utf-8-sig').split('=', 1)[1].strip().rstrip(';'))
pd.DataFrame(study['calls']).to_csv(OUT / 'normalized_residential_calls.csv', index=False)
listings = pd.read_csv(ROOT / 'ranked_listings_with_calls.csv', dtype={'parcel_PIN': str})
parcels = pd.read_csv(ROOT / 'parcel_rates.csv', dtype={'pin': str})
assert parcels.pin.is_unique
sizes = listings.groupby('parcel_PIN').agg(
    bedrooms=('advertised_bedrooms', 'max'),
    guests=('advertised_capacity', 'max'),
    listing_rows=('listing_id', 'size'))
data = sizes.merge(parcels, left_index=True, right_on='pin', validate='one_to_one')
assert len(data) == len(sizes), 'Missing listing parcels in call export'
assert data.licensed.astype(str).str.lower().eq('true').all()
series = [('citizen_direct_calls', 'Property', '#2563eb'),
          ('citizen_neighbor_only_calls', 'Immediate residential neighbors', '#d97706'),
          ('citizen_residential_combined_calls', 'Property + neighbors', '#15803d')]
assert (data.citizen_direct_calls + data.citizen_neighbor_only_calls == data.citizen_residential_combined_calls).all()
for column, _, _ in series:
    data[column + '_annual'] = data[column] / data.exposure_years
data.to_csv(OUT / 'parcel_size_calls.csv', index=False)
tables = []
for size, label in [('bedrooms', 'Maximum advertised bedrooms on parcel'), ('guests', 'Maximum advertised guest capacity on parcel')]:
    known = data.dropna(subset=[size])
    groups = known.groupby(size)
    table = groups.size().rename('parcels').to_frame()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for column, name, color in series:
        table[column + '_annual_mean'] = groups[column + '_annual'].mean()
        ax.plot(table.index, table[column + '_annual_mean'], marker='o', label=name, color=color)
    for x, row in table.iterrows():
        ax.annotate(f"n={int(row.parcels)}", (x, row['citizen_residential_combined_calls_annual_mean']),
                    xytext=(0, 9), textcoords='offset points', ha='center', fontsize=8)
    ax.set(xlabel=label, ylabel='Mean citizen-initiated calls per parcel / calendar year',
           title=f'Listing size and calls for service: {size}', ylim=(0, None))
    ax.grid(alpha=.2)
    ax.legend(loc='upper left')
    fig.text(.08, .025, f'{len(known)} parcels; {len(data)-len(known)} with unknown size excluded. Labels show parcel counts.\n'
             '2024-09-21 to 2026-10-16. Shared-border residential neighbors only. Lines connect size-group means; no causal inference.', fontsize=9)
    fig.tight_layout(rect=(0, .09, 1, 1))
    for ext in ['png', 'svg']:
        fig.savefig(OUT / f'{size}_vs_calls.{ext}', dpi=170)
    plt.close(fig)
    table.index.name = size
    table.to_csv(OUT / f'{size}_group_means.csv')
    tables.append(f'<h2>{label}</h2><img src="{size}_vs_calls.svg" alt="{size} versus annual calls"><p><a href="{size}_vs_calls.png">PNG</a> - <a href="{size}_vs_calls.svg">SVG</a> - <a href="{size}_group_means.csv">Group data CSV</a></p>')
html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Listing size and calls for service</title><style>body{font:17px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#172334}img{width:100%;height:auto}p{line-height:1.6}a{color:#185abc}</style>
<a href="../index.html">Back to study map</a><h1>Listing size and calls for service</h1>
<p>Citizen-initiated recorded-address calls, not verified 911-origin records. Each parcel counts once, including zero-call parcels. Size is the largest known listing size on that parcel, not the sum of units or observed occupancy. Bedroom and guest maxima can come from different listings. Calls belong to the parcel and cannot be assigned to an individual rental unit.</p>
<p>Each point is the mean annual call count for parcels of exactly that size. Neighbor calls are totals across immediate residential neighbors sharing more than 0.1 m of boundary; across-street and corner-only properties are excluded. Combined totals are deduplicated within each focal neighborhood. Shared neighbors can appear in several neighborhoods. These rates are per focal parcel, not per neighbor parcel, and have no booking-occupancy adjustment. Groups with few parcels are unstable; connecting lines are descriptive, not fitted trends.</p>
'''
(OUT / 'index.html').write_text(html + '\n'.join(tables) + '<h2>Source data</h2><p><a href="parcel_size_calls.csv">Parcel size and call totals</a> - <a href="normalized_residential_calls.csv">Normalized residential call records</a> - <a href="../neighbor_call_membership.csv">Neighbor call memberships</a></p><p>The original dispatch export is absent from this publication. Normalized residential call records are extracted from data.js; they omit excluded and unresolved source records. Study period: September 21, 2024–October 16, 2026. Rebuild with python plot_listing_size.py (pandas and matplotlib required).</p></html>', encoding='utf-8')
print(f'Built plots for {len(data)} unique parcels from {len(listings)} listing rows; exported {len(study["calls"])} normalized calls.')
