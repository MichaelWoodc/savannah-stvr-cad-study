"""Build a separate, auditable collection of rising capacity curves and amenity analyses."""
from pathlib import Path
import csv
import hashlib
import html
import json
import shutil
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from processing.plot_axes import discrete_axis

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'key_plots'
CATEGORIES={'all_calls':'All calls','parking_complaints':'Parking complaints','noise_complaints':'Noise complaints','loud_party':'Loud party','disturbance_nuisance':'Disturbance / nuisance'}
COLORS={'Owner-occupied':'#245db7','Non-owner-occupied':'#d6751a','Mixed permit types':'#7b3cb5','Unknown':'#666','Citizen-initiated calls':'#245db7'}

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def jsdata(path,prefix): return json.loads(path.read_text(encoding='utf-8-sig').removeprefix(prefix).strip().removesuffix(';'))

def generate():
    OUT.mkdir(exist_ok=True)
    report=jsdata(ROOT/'direct_listing_calls/report_data.js','window.DIRECT_REPORT=')
    baseline=report['summary']['measures']['citizen']['baselines']
    sources=list((ROOT/'plots').glob('saved_direct__citizen_*_minimum_threshold__*.csv'))
    sources+=list((ROOT/'plots').glob('current_direct__*__minimum__*.csv'))
    audit=[]; kept=[]
    for path in sorted(sources):
        category=next((label for key,label in CATEGORIES.items() if path.stem.endswith('__'+key)),None)
        if not category: continue
        frame=pd.read_csv(path)
        good=[]
        for name,group in frame.groupby('series',sort=False):
            x=group[pd.to_numeric(group['parcels'],errors='coerce')>=10].dropna(subset=['size','rate']).sort_values('size')
            if len(x)>=4 and x['size'].nunique()>=4:
                slope=float(np.polyfit(x['size'],x['rate'],1,w=np.sqrt(x['parcels']))[0])
                if slope>0 and float(x['rate'].iloc[-1])>float(x['rate'].iloc[0]):good.append(name)
        selected=bool(good)
        audit.append({'source':str(path.relative_to(ROOT)),'category':category,'selected':selected,'qualifying_series':' | '.join(good),'selection_rule':'At least one series: >=4 distinct size thresholds with n>=10, positive parcel-count-weighted slope, last supported group > first; unfiltered points remain visible','sha256':digest(path)})
        if not selected:continue
        shutil.copy2(path,OUT/(path.stem+'.csv'))
        saved=path.stem.startswith('saved_direct__')
        if saved:
            measure='advertised guests' if 'guests_' in path.stem else 'advertised bedrooms'
            cohort='Historical matched listing cohort'
        else:
            parts=path.stem.split('__');cohort=parts[1].replace('_',' ');measure={'approved_guests':'approved guests (parcel total)','licensed_bedrooms':'licensed bedrooms (parcel total)','capacity_difference':'advertised minus approved guests','bedrooms':'advertised bedrooms','guests':'advertised guests'}.get(parts[2],parts[2])
        note='Period 2024-01-01–2026-10-16; parking ends 2024-09-20. STVR rates divided by 0.59; residential reference per calendar year. Threshold groups overlap. Zero-call parcels included. Line connects observed means. No causal attribution.'
        for variant in ['same_category','all_calls_context']:
            fig,ax=plt.subplots(figsize=(11,7))
            for name,g in frame.groupby('series',sort=False):
                g=g.sort_values('size');ax.plot(g['size'],g['rate'],'o-',ms=3,lw=1.8,label=name,color=COLORS.get(name,'#444'))
                for i,row in enumerate(g.itertuples()):
                    if len(g)<=12 or i%2==0 or row.parcels<10:ax.annotate(f'n={row.parcels}',(row.size,row.rate),xytext=(0,7),textcoords='offset points',fontsize=7,ha='center')
            ax.axhline(baseline[category],ls='--',color='#8a5626',label=f'All residential, same call category: {baseline[category]:.3f}/calendar year')
            if variant=='all_calls_context' and category!='All calls':ax.axhline(baseline['All calls'],ls=':',color='#555',label=f'All residential, ALL calls: {baseline["All calls"]:.3f}/calendar year (context)')
            ax.set(title=f'{category}: minimum {measure}\n{cohort}',xlabel='Minimum '+measure,ylabel='Direct citizen-initiated calls per estimated occupied year',ylim=(0,None));ax.grid(alpha=.2);ax.legend(fontsize=8);ax.margins(y=.15);discrete_axis(ax,measure)
            fig.text(.07,.02,'\n'.join(textwrap.wrap(note,145)),fontsize=8);fig.tight_layout(rect=(0,.12,1,1))
            for ext in ['png','svg']:fig.savefig(OUT/f'{path.stem}__{variant}.{ext}',dpi=120)
            plt.close(fig)
        kept.append({'stem':path.stem,'cohort':cohort,'measure':measure,'category':category,'series':' | '.join(good),'source':str(path.relative_to(ROOT)),'n_min':int(frame.parcels.min()),'n_max':int(frame.parcels.max())})
    pd.DataFrame(audit).to_csv(OUT/'selection_audit.csv',index=False)
    pd.DataFrame(kept).to_csv(OUT/'plot_manifest.csv',index=False)
    combo=OUT/'amenity_combinations';combo.mkdir(exist_ok=True)
    candidates=ROOT/'party_combination_analysis'
    for name in ['top_10_direct_candidates.csv','all_adjusted_combinations.csv','candidate_properties_and_calls.csv','insufficient_support_or_failed.csv','pair_synergy_support.csv']:
        if (candidates/name).exists():shutil.copy2(candidates/name,combo/name)
    top=pd.read_csv(candidates/'top_10_direct_candidates.csv')
    for rank in top['review_rank']:
        for ext in ['png','svg']:
            src=candidates/'plots'/f'{rank:02d}__candidate.{ext}'
            if src.exists():shutil.copy2(src,combo/src.name)
    note='These are exploratory recorded-address associations, not proof that a property, guests, size, or amenities caused an incident. The selection deliberately finds rising series in these same data and is not independent validation. Overlapping minimum-threshold groups are not independent; small end groups can be unstable. Zeros are included. STVR rates use a 59% occupancy scenario, whereas residential reference lines use calendar years; see both rates before comparing. A same-category baseline is the meaningful like-for-like call outcome; the all-calls line is context only. The parking period is shorter. Existing plots and evidence remain untouched.'
    text=['# Key capacity and amenity plots','',note,'',f'{len(kept)} rising minimum-threshold charts; selection audit includes all {len(audit)} scanned candidates. For each plot, open same-category for legibility or all-calls-context for the requested full residential total. Curves retain all original points, even those with fewer than 10 parcels. Selection requires at least four n>=10 groups with positive weighted slope and last supported mean above first; it does not require a smooth or monotonic rise.','', '## Amenity combinations','', 'The ten copied review candidates come from an adjusted search across many combinations. None passed the 5% false-discovery screen in the supplied results; these are not established causal effects or evidence of interaction. Conditions apply within one listing. The original analysis, data, and uncertainty details are in ../party_combination_analysis/. All 10 plots include same-category and all-call residential references.','', '## Curves','']
    text += [f"- [{x['cohort']} / {x['measure']} / {x['category']}]({x['stem']}__same_category.png) | [all-calls context]({x['stem']}__all_calls_context.png) | [data]({x['stem']}.csv)" for x in kept]
    text+=['','Rebuild: python -m processing.key_plots','']
    (OUT/'README.md').write_text('\n'.join(text),encoding='utf-8')
    e=html.escape
    rows='\n'.join(f"<tr><td>{e(x['cohort'])}</td><td>{e(x['measure'])}</td><td>{e(x['category'])}</td><td>{e(x['series'])}</td><td><a href='{e(x['stem'])}__same_category.png'>Plot</a> · <a href='{e(x['stem'])}__all_calls_context.png'>All-call reference</a> · <a href='{e(x['stem'])}.csv'>Data</a></td></tr>" for x in kept)
    combos='\n'.join(f"<li><a href='amenity_combinations/{int(r.review_rank):02d}__candidate.png'>{e(r.label)}</a> — {r.properties} parcels, {r.calls} calls, q={r.q_fdr:.3f}</li>" for r in top.itertuples())
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Key capacity and amenity plots</title><style>body{{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#152438}}table{{border-collapse:collapse;width:100%}}td,th{{padding:.5rem;border:1px solid #ccd;text-align:left}}a{{color:#124f88}}.note{{background:#fff5d8;padding:1rem}}</style><h1>Key capacity and amenity plots</h1><p class="note">{e(note)}</p><p>Each curve connects original minimum-threshold group means. Threshold groups overlap and small end groups are unstable. These plots were selected for an upward pattern in the same data; other directions appear in the <a href="selection_audit.csv">selection audit</a>. Click the all-call reference for the full residential total; that line is context for specific-category plots.</p><p><a href="README.md">Methods and complete index</a> · <a href="plot_manifest.csv">Plot manifest</a> · <a href="../index.html">Study map</a></p><h2>Capacity curves ({len(kept)})</h2><table><thead><tr><th>Cohort</th><th>Minimum size</th><th>Call type</th><th>Series meeting selection rule</th><th>Files</th></tr></thead><tbody>{rows}</tbody></table><h2>Amenity combination review candidates</h2><p>Search results are exploratory: none passed the 5% false-discovery threshold. Higher joint rates do not establish that amenities cause calls or interact. Each candidate plot includes the requested all-call residential reference and a same-category reference.</p><ol>{combos}</ol><p><a href="amenity_combinations/top_10_direct_candidates.csv">Candidate estimates and uncertainty</a> · <a href="amenity_combinations/candidate_properties_and_calls.csv">Parcel evidence</a> · <a href="../party_combination_analysis/README.md">Full analysis and methodology</a></p></html>'''
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(f'Created {len(kept)} capacity charts from {len(audit)} candidates; {len(top)} amenity candidates in {OUT}')

if __name__=='__main__':generate()
