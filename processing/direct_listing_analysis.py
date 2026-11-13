"""Direct recorded-address calls and listing evidence, with adjustable occupancy scenario."""
from pathlib import Path
import json
import hashlib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from processing.entire_call_period import load_calls
from processing.direct_report_controls import build as build_controls
from processing.build_capacity_pages import build as build_capacity_pages
from processing.citizen_only import select as citizen_only

ROOT=Path(__file__).resolve().parents[1]

def run(root=ROOT):
    root=Path(root);out=root/'direct_listing_calls';out.mkdir(exist_ok=True)
    study=json.loads((root/'data.js').read_text(encoding='utf-8-sig').split('=',1)[1].strip().rstrip(';'))
    occupancy=.59
    parcels=pd.read_csv(root/'parcel_rates.csv',dtype={'pin':str})
    calls,coverage=load_calls(root,study,parcels)
    years=coverage['exposure_years']
    parking_years=coverage['parking_exposure_years']
    parking_note=f"* Parking uses {coverage['parking_date_start']} to {coverage['parking_date_end']} ({parking_years:.3f} years); later parking coverage is unavailable."
    assert calls.number.is_unique
    listings=pd.read_csv(root/'listing_screen_all.csv',dtype=str).fillna('')
    inventory=pd.read_csv(root/'processed_data/listing_details/current_detail_inventory.csv',dtype=str).fillna('')
    duplicates=inventory[inventory.listing_id.duplicated(keep=False)]
    duplicates.to_csv(out/'duplicate_source_listing_ids.csv',index=False)
    inventory=inventory.sort_values('details_path').drop_duplicates('listing_id')
    merged=listings.merge(inventory,on='listing_id',how='outer',suffixes=('','_current'),indicator=True)
    merged.to_csv(out/'listing_coverage_audit.csv',index=False)
    new=merged[merged['_merge'].eq('right_only')|merged.scope_status.ne('eligible_residential')]
    new.to_csv(out/'unmatched_or_excluded_listings.csv',index=False)
    active=merged[merged.scope_status.eq('eligible_residential') & merged.read_status.eq('read')].copy()
    audit_path=root/'processed_data/listing_matches/verified_listing_matches.csv'
    if audit_path.exists():
        verified=pd.read_csv(audit_path,dtype=str).fillna('')
        active=active[active.listing_id.isin(set(verified.listing_id))].copy()
        assert active.permit_match_source.eq('source_text_validated').all(), 'Unvalidated historical folder match cannot enter active analysis'
        verified=verified.set_index('listing_id')
        unchanged=active.details_sha256_current.eq(active.listing_id.map(verified.details_sha256))
        same_pin=active.parcel_PIN.str.replace(' ','').eq(active.listing_id.map(verified.matched_pin))
        active.loc[~(unchanged&same_pin)].to_csv(out/'changed_sources_requiring_match_revalidation.csv',index=False)
        active=active[unchanged&same_pin].copy()
    assert active.listing_id.is_unique
    active['bedrooms']=pd.to_numeric(active.current_bedrooms,errors='coerce').fillna(pd.to_numeric(active.advertised_bedrooms,errors='coerce'))
    active['guests']=pd.to_numeric(active.current_guests,errors='coerce').fillna(pd.to_numeric(active.advertised_capacity,errors='coerce'))
    active['detail_changed_since_keyword_audit']=active.details_sha256.ne(active.details_sha256_current)
    assert set(active.parcel_PIN)<=set(parcels.pin)
    parcel_listings=active.groupby('parcel_PIN').agg(bedrooms=('bedrooms','max'),guests=('guests','max'),listing_count=('listing_id','size'))
    data=parcel_listings.merge(parcels,left_index=True,right_on='pin',validate='one_to_one')
    assert data.pin.is_unique
    # Only definitive original residential matches enter either numerator or denominator.
    assert set(calls.pin)<=set(parcels.pin)
    categories=['All calls','Parking complaints','Noise complaints','Loud party','Disturbance / nuisance']
    def category(t, original_category):
        t=t.upper()
        if 'PARKING COMPLAINT' in t:return 'Parking complaints'
        if 'LOUD PARTY' in t:return 'Loud party'
        if 'NOISE' in t:return 'Noise complaints'
        if original_category=='Disturbance / nuisance':return 'Disturbance / nuisance'
        return 'Other'
    calls['analysis_category']=[category(t,c) for t,c in zip(calls.type,calls.category)]
    evidence=pd.read_csv(root/'listing_keyword_evidence.csv',dtype=str).fillna('')
    features=['hot_tub','pool','grill','fire_pit','sound_system','bar','outdoor_dining','patio','yard','events','wedding','bachelorette','bachelor']
    summaries={};tables=[];all_group_tables=[];feature_tables=[]
    for measure in ['citizen']:
        selected=citizen_only(calls)
        baselines={}
        current=data.copy()
        for cat in categories:
            subset=selected if cat=='All calls' else selected[selected.analysis_category.eq(cat)]
            category_years=parking_years if cat=='Parking complaints' else years
            baselines[cat]=len(subset)/len(parcels)/category_years
            counts=subset.groupby('pin').size()
            current[cat+'_count']=current.pin.map(counts).fillna(0).astype(int)
            current[cat+'_calendar_rate']=current[cat+'_count']/category_years
            current[cat+'_adjusted_rate']=current[cat+'_calendar_rate']/occupancy
        assert int(current['All calls_count'].sum())==int(selected.pin.isin(current.pin).sum())
        assert selected.analysis_category.eq('Parking complaints').any(), 'Parking coverage must be checked before graphing'
        current['above_average']=current['All calls_adjusted_rate']>baselines['All calls']
        current.to_csv(out/f'{measure}_parcel_direct_rates.csv',index=False)
        listing_rates=active.merge(current[['pin','above_average']+[c+s for c in categories for s in ['_count','_calendar_rate','_adjusted_rate']]],left_on='parcel_PIN',right_on='pin',validate='many_to_one')
        listing_rates.to_csv(out/f'{measure}_all_listing_rates.csv',index=False)
        high=listing_rates[listing_rates.above_average].sort_values('All calls_adjusted_rate',ascending=False)
        high.to_csv(out/f'{measure}_above_average_listings.csv',index=False)
        selected[selected.pin.isin(current.loc[current.above_average,'pin'])].to_csv(out/f'{measure}_above_average_direct_calls.csv',index=False)
        evidence[evidence.folder_name.isin(high.folder_name)].to_csv(out/f'{measure}_above_average_keyword_evidence.csv',index=False)
        for size,label in [('bedrooms','Maximum advertised bedrooms on parcel'),('guests','Maximum advertised guest capacity on parcel')]:
            for cohort,frame in [('all_matched',current),('above_average',current[current.above_average])]:
                valid=frame.dropna(subset=[size])
                grouped=valid.groupby(size)
                mean=grouped[[c+'_adjusted_rate' for c in categories]].mean()
                mean['parcels']=grouped.size()
                mean.to_csv(out/f'{measure}_{size}_{cohort}_means.csv')
                all_group_tables.append(mean.reset_index().assign(measure=measure,size=size,cohort=cohort))
                fig,axs=plt.subplots(2,3,figsize=(15,9))
                for ax,cat in zip(axs.flat,categories):
                    if baselines[cat] is None:
                        ax.set_title(cat);ax.axis('off');ax.text(.05,.6,'Unavailable in the published call extract.\nDo not interpret as zero actual calls.',fontsize=11)
                        continue
                    ax.plot(mean.index,mean[cat+'_adjusted_rate'],'o-',label='Rentals at 59% scenario')
                    ax.axhline(baselines[cat],color='#b45309',linestyle='--',label='Study residential average')
                    for x,row in mean.iterrows():ax.annotate(str(int(row.parcels)),(x,row[cat+'_adjusted_rate']),xytext=(0,5),textcoords='offset points',ha='center',fontsize=7)
                    ax.set(title=cat+('*' if cat=='Parking complaints' else ''),xlabel=label,ylabel='Calls per estimated occupied year',ylim=(0,None));ax.grid(alpha=.2);ax.legend(fontsize=7)
                    if size=='guests':ax.set_xticks(range(2,int(valid[size].max())+1,2))
                axs.flat[-1].axis('off')
                axs.flat[-1].text(0,.9,f'{len(valid)} parcels; point labels are parcel counts.\nEach parcel counted once, including zeros.\nAbove-average selection uses overall calls.\n\nCalendar annual rate / 0.59 is a scenario.\nCalls are not assigned to occupied nights.\nNo neighbor calls or building-type filter.',va='top',fontsize=11)
                fig.suptitle(f'Direct property calls by {size}: {cohort.replace("_"," ")} ({measure})\n'+coverage['date_start']+' to '+coverage['date_end']+'; parking period exception*')
                fig.text(.04,.015,parking_note,fontsize=9)
                fig.tight_layout(rect=(0,.05,1,.96))
                for ext in ['png','svg']:fig.savefig(out/f'{measure}_{size}_{cohort}.{ext}',dpi=150)
                plt.close(fig)
                # A dedicated parking graph is always written, including valid zero-call groups.
                fig,ax=plt.subplots(figsize=(11,6))
                ax.plot(mean.index,mean['Parking complaints_adjusted_rate'],'o-',label='Rentals at 59% scenario')
                ax.axhline(baselines['Parking complaints'],color='#b45309',linestyle='--',label='Same-period residential average')
                for x,row in mean.iterrows():
                    ax.annotate(f'n={int(row.parcels)}',(x,row['Parking complaints_adjusted_rate']),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
                ax.set(title='Parking complaints* ('+cohort.replace('_',' ')+')',xlabel=label,ylabel='Calls per estimated occupied year',ylim=(0,None));ax.grid(alpha=.2);ax.legend()
                fig.text(.06,.025,parking_note+'\n* Cohort: '+cohort.replace('_',' ')+'. Initiation: '+measure+'. No positive-call-only filtering; zero-call parcels included.',fontsize=8)
                fig.tight_layout(rect=(0,.10,1,1))
                for ext in ['png','svg']:fig.savefig(out/f'{measure}_{size}_{cohort}_parking.{ext}',dpi=150)
                plt.close(fig)
            cumulative=[]
            for threshold in sorted(current[size].dropna().unique()):
                group=current[current[size].ge(threshold)]
                cumulative.append(dict(minimum_size=threshold,parcels=len(group),**{cat:group[cat+'_adjusted_rate'].mean() for cat in categories if baselines[cat] is not None}))
            cumulative=pd.DataFrame(cumulative).set_index('minimum_size')
            cumulative.to_csv(out/f'{measure}_{size}_minimum_threshold_means.csv')
            fig,axs=plt.subplots(2,3,figsize=(15,9))
            for ax,cat in zip(axs.flat,[c for c in categories if baselines[c] is not None]):
                ax.plot(cumulative.index,cumulative[cat],'o-',label='Rentals at or above size cutoff')
                ax.axhline(baselines[cat],color='#b45309',linestyle='--',label='Study residential average')
                for x,row in cumulative.iterrows():
                    if x%2==0:ax.annotate(f'n={int(row.parcels)}',(x,row[cat]),xytext=(0,6),textcoords='offset points',ha='center',fontsize=7)
                cutoff_label='Minimum advertised guest capacity' if size=='guests' else 'Minimum advertised bedrooms'
                ax.set(title=cat+('*' if cat=='Parking complaints' else ''),xlabel=cutoff_label,ylabel='Calls per estimated occupied year',ylim=(0,max(cumulative[cat].max(),baselines[cat],.001)*1.15));ax.grid(alpha=.2);ax.legend(fontsize=8)
            axs.flat[-1].axis('off')
            fig.suptitle('Minimum-size filters, matching the original map: '+size+' ('+measure+')\n'+coverage['date_start']+' to '+coverage['date_end']+'; parking period exception*')
            fig.text(.04,.015,parking_note,fontsize=9)
            fig.tight_layout(rect=(0,.05,1,.95))
            for ext in ['png','svg']:fig.savefig(out/f'{measure}_{size}_minimum_threshold.{ext}',dpi=150)
            plt.close(fig)
        for feature in features:
            for field,mode in [('on_site_feature_candidates','onsite'),('active_mention_features','mention')]:
                pins=set(active.loc[active[field].map(lambda s:feature in s.split(' | ')),'parcel_PIN'])
                for present in [True,False]:
                    group=current[current.pin.isin(pins).eq(present)]
                    feature_tables.append(dict(measure=measure,feature=feature,evidence_mode=mode,present=present,parcels=len(group),above_average_parcels=int(group.above_average.sum()),**{c:group[c+'_adjusted_rate'].mean() for c in categories}))
        summaries[measure]=dict(baselines=baselines,matched_parcels=len(current),above_average_parcels=int(current.above_average.sum()),above_average_listing_rows=len(high),all_parcel_rates=current.replace({np.nan:None}).to_dict('records'))
        tables.append(listing_rates.assign(measure=measure))
    pd.DataFrame(feature_tables).to_csv(out/'amenity_comparisons.csv',index=False)
    combined=pd.concat(tables,ignore_index=True)
    combined[combined.measure.eq('citizen')&combined.bedrooms.gt(6)].sort_values(['bedrooms','listing_id']).to_csv(out/'listings_over_6_bedrooms.csv',index=False)
    # JSON payload contains only report fields, avoiding full raw listing text.
    fields=['listing_id','listing_url','title','parcel_PIN','normalized_license_address','bedrooms','guests','active_mention_features','on_site_feature_candidates','restriction_mentions','detail_changed_since_keyword_audit','measure']+[c+s for c in categories for s in ['_count','_calendar_rate','_adjusted_rate']]
    payload=combined[fields].replace({np.nan:None}).to_dict('records')
    summary=dict(occupancy_scenario=occupancy,exposure_years=years,date_start=coverage['date_start'],date_end=coverage['date_end'],residential_baseline_parcels=len(parcels),matched_listing_rows=len(active),matched_parcels=len(data),network_folders=len(inventory),current_sources_changed=int(active.detail_changed_since_keyword_audit.sum()),coverage=merged.scope_status.fillna('not_in_old_audit').value_counts().to_dict(),measures={m:{k:v for k,v in s.items() if k!='all_parcel_rates'} for m,s in summaries.items()})
    summary['call_coverage']=coverage
    summary['category_coverage_note']=parking_note
    summary['parking_plot_settings']=dict(default='all_matched',alternative='follow_main_cohort',
        initiation='same as selected measure',occupancy=.59,period='entire supported parking window',
        zero_call_groups='included and graphed',exception_mark='*')
    summary['source_sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['data.js','listing_screen_all.csv','listing_keyword_evidence.csv','processed_data/listing_details/current_detail_inventory.csv']}
    controls=build_controls(root,out,parcels,calls,active,categories,years,parking_years)
    summary['license_controls']=controls['counts']
    for source in ['processed_data/licenses/licenses_normalized.csv','processing/direct_report_controls.py']:
        summary['source_sha256'][source]=hashlib.sha256((root/source).read_bytes()).hexdigest()
    (out/'analysis_summary.json').write_text(json.dumps(summary,indent=2))
    (out/'report_data.js').write_text('window.DIRECT_REPORT='+json.dumps(dict(rows=payload,summary=summary,controls=controls),allow_nan=False)+';',encoding='utf-8')
    build_capacity_pages(root,out,controls)
    from processing.collect_plots import collect
    collect(root)
    return summary

if __name__=='__main__':print(json.dumps(run(),indent=2))
