"""Descriptive size trends, amenity associations and recorded-call review priorities."""
from pathlib import Path
import hashlib
import json
import shutil
import textwrap
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import statsmodels.api as sm
from processing.plot_axes import discrete_axis
from processing.collect_plots import SIZES,slug,TYPES,COLORS

ROOT=Path(__file__).resolve().parents[1]
PHYSICAL=['hot_tub','pool','grill','fire_pit','sound_system','bar','outdoor_dining','patio','yard']
INTENT=['events','wedding','bachelorette','bachelor']

def weighted_quantile(x,w,q):
    order=np.argsort(x);x=x[order];w=w[order]
    return float(np.interp(q,np.cumsum(w)/w.sum(),x))

def fit_trend(frame,minimum=False):
    x=frame['size'].to_numpy(float);y=frame.rate.to_numpy(float)
    w=np.ones(len(frame)) if minimum else frame.parcels.to_numpy(float)
    valid=np.isfinite(x)&np.isfinite(y)&(w>0);x=x[valid];y=y[valid];w=w[valid]
    if len(x)<2 or np.ptp(x)==0:return None
    xm=np.average(x,weights=w);ym=np.average(y,weights=w)
    variance=np.average((x-xm)**2,weights=w)
    slope=np.average((x-xm)*(y-ym),weights=w)/variance;intercept=ym-slope*xm
    ss=np.sum(w*(y-ym)**2);r2=1-np.sum(w*(y-intercept-slope*x)**2)/ss if ss>1e-15 else np.nan
    q25=weighted_quantile(x,w,.25);q75=weighted_quantile(x,w,.75)
    return dict(slope=float(slope),intercept=float(intercept),r2_group_means=float(r2),
        mean_rate=float(frame.iloc[0].rate if minimum else ym),groups=len(x),
        parcels=int(frame.iloc[0].parcels if minimum else frame.parcels.sum()),
        x_min=float(x.min()),x_max=float(x.max()),x_q25=q25,x_q75=q75,
        fitted_iqr_rise=float(slope*(q75-q25)),
        standardized_rise_fraction=float(slope*np.sqrt(variance)/ym) if ym>0 else np.nan,
        method='unweighted descriptive fit to overlapping cutoffs' if minimum else 'parcel-count-weighted fit to exact-size group means')

class Analysis:
    def __init__(self,root):
        self.root=Path(root);self.source=self.root/'plots'
        self.out=self.root/'plots_with_trends';self.avg=self.root/'plots_with_trends_with_averages'
        self.out.mkdir(exist_ok=True);self.avg.mkdir(exist_ok=True)
        self.report=json.loads((self.root/'direct_listing_calls/report_data.js').read_text(encoding='utf-8').removeprefix('window.DIRECT_REPORT=').removesuffix(';'))
        self.summary=self.report['summary'];self.data=self.report['controls'];self.fits=[];self.plot_count=0
        assert set(self.summary['measures'])=={'citizen'}
        self.before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir() if p.is_file()}

    def metadata(self,name):
        parts=name.split('__');kind=parts[0];minimum='minimum' in name
        categories={slug(c):c for c in self.data['categories']}
        category=categories.get(parts[-1],parts[-1].replace('_',' '))
        key=parts[2] if kind=='current_direct' else ('guests' if 'guests' in name else 'bedrooms' if 'bedrooms' in name else 'approved_guests')
        xlabel=SIZES[key];baseline=None
        note='Citizen-initiated only; proactive patrol/stop labels excluded. A fitted association is not a causal effect.'
        if kind in ['current_direct','saved_direct']:
            note+=f" Available span {self.summary['date_start']} to {self.summary['date_end']}; annual rates / 0.59."
            if category in self.summary['measures']['citizen']['baselines']:baseline=self.summary['measures']['citizen']['baselines'][category]
            if category=='Parking complaints':note+=' '+self.summary['category_coverage_note']
        elif kind=='original_size':
            note+=' Original published span 2024-09-21 to 2026-10-16; calendar-year rates without booking adjustment. Neighbor totals are per focal property, not per neighbor.'
        else:
            note+=' Historical 2024-01-01 to 2024-09-20 snapshot; no annual or booking adjustment. Keep its own denominator and category rules.'
        if minimum:note+=' Cutoff groups overlap; their fits are descriptive and are excluded from the primary ranking.'
        title=category.title()+' | '+(' / '.join(parts[1:-1]).replace('_',' ') if len(parts)>2 else name.replace('_',' '))
        return dict(kind=kind,key=key,category=category,minimum=minimum,xlabel=('Minimum ' if minimum else '')+xlabel,title=title,note=note,baseline=baseline)

    def save_variants(self,fig,ax,name,note,averages=(),baseline=None,horizontal=False):
        assert len(fig.axes)==1
        ax.grid(alpha=.18);ax.legend(fontsize=8)
        fig.text(.07,.02,'\n'.join(textwrap.wrap(note,width=145)),fontsize=8,va='bottom')
        fig.tight_layout(rect=(0,.15,1,1))
        for ext in ['png','svg']:fig.savefig(self.out/(name+'.'+ext),dpi=140)
        if baseline is not None:
            if horizontal:ax.axvline(baseline,color='#6b7280',linestyle='--',label=f'Residential reference {baseline:.3f}')
            else:ax.axhline(baseline,color='#6b7280',linestyle='--',label=f'Residential reference {baseline:.3f}')
        for label,value,color in averages:
            if not np.isfinite(value):continue
            if horizontal:ax.axvline(value,color=color,linestyle=':',linewidth=1.8,label=f'{label} mean {value:.3f}')
            else:ax.axhline(value,color=color,linestyle=':',linewidth=1.8,label=f'{label} mean {value:.3f}')
        references=[value for _,value,_ in averages if np.isfinite(value)]
        if baseline is not None:references.append(baseline)
        if references:
            if horizontal:
                lo,hi=ax.get_xlim();ax.set_xlim(min(0,lo),max(hi,max(references)*1.15))
            else:
                lo,hi=ax.get_ylim();ax.set_ylim(min(0,lo),max(hi,max(references)*1.15))
        ax.legend(fontsize=8);fig.tight_layout(rect=(0,.15,1,1))
        for ext in ['png','svg']:fig.savefig(self.avg/(name+'.'+ext),dpi=140)
        plt.close(fig);self.plot_count+=1
        if self.plot_count%20==0:print(f'Exported {self.plot_count} individual trend plots into both folders',flush=True)

    def existing(self):
        for source in sorted(self.source.glob('*.csv')):
            if source.name=='manifest.csv':continue
            frame=pd.read_csv(source)
            if not {'series','size','rate','parcels'}<=set(frame.columns):continue
            meta=self.metadata(source.stem);fig,ax=plt.subplots(figsize=(12,8));averages=[]
            for index,(label,part) in enumerate(frame.groupby('series',sort=False)):
                part=part.sort_values('size');color=COLORS.get(next((k for k,v in TYPES.items() if v==label),''),plt.get_cmap('tab10')(index))
                ax.plot(part['size'],part.rate,'o-',color=color,label=label,markersize=4,alpha=.7)
                fit=fit_trend(part,meta['minimum'])
                if fit:
                    xx=np.array([fit['x_min'],fit['x_max']]);ax.plot(xx,fit['intercept']+fit['slope']*xx,color=color,linestyle='--',linewidth=2,label=f"{label} trend: slope {fit['slope']:.3f}; group R² {fit['r2_group_means']:.2f}")
                    events=np.nan
                    if meta['kind']=='current_direct' and not meta['minimum']:
                        exposure=self.summary['call_coverage']['parking_exposure_years'] if meta['category']=='Parking complaints' else self.summary['exposure_years']
                        events=float((part.rate*part.parcels).sum()*.59*exposure)
                    primary=meta['kind']=='current_direct' and source.stem.split('__')[1] in ['every_licensed_address','matched_airbnb'] and not meta['minimum'] and meta['key']!='capacity_difference'
                    supported=primary and fit['slope']>1e-10 and fit['parcels']>=30 and fit['groups']>=4 and fit['r2_group_means']>=.2 and events>=10 and fit['x_q75']>fit['x_q25']
                    signature=hashlib.sha256(part[['size','rate','parcels']].to_csv(index=False).encode()).hexdigest()
                    self.fits.append(dict(plot=source.stem,series=label,data_signature=signature,category=meta['category'],size_measure=meta['key'],grouping='minimum' if meta['minimum'] else 'exact',category_events=events,primary_candidate=primary,supported_increase=supported,**fit))
                    averages.append((label,fit['mean_rate'],color))
                elif len(part):averages.append((label,float(part.iloc[0].rate),color))
            ax.set(title=meta['title'],xlabel=meta['xlabel'],ylabel='Citizen-initiated call rate (source denominator)',ylim=(0,None));discrete_axis(ax,meta['xlabel'])
            self.save_variants(fig,ax,source.stem,meta['note']+' R² describes group means, not individual-property variance. Mean lines in the averages folder use unique-parcel weights for exact groups, or the first cutoff for overlapping minimum groups.',averages,meta['baseline'])
            for folder in [self.out,self.avg]:frame.to_csv(folder/source.name,index=False)

    def property_data(self):
        rows=[]
        for p in self.data['properties']:
            ls=p['listings']
            if not ls:continue
            values=lambda key:[r[key] for r in ls if r[key] is not None]
            onsite=max(len(set(r['onsite'])&set(PHYSICAL)) for r in ls)
            mention=max(len(set(r['mention'])&set(PHYSICAL)) for r in ls)
            intent=max(len(set(r['mention'])&set(INTENT)) for r in ls)
            row=dict(pin=p['pin'],address=p['address'],permit_type=p['permit_type'],license_count=p['license_count'],
                approved_guests=p['approved_guests'],licensed_bedrooms=p['licensed_bedrooms'],
                guests=max(values('guests')) if values('guests') else np.nan,bedrooms=max(values('bedrooms')) if values('bedrooms') else np.nan,
                onsite_amenity_count=onsite,mentioned_amenity_count=mention,event_language_count=intent,
                listing_count=len(ls),advertised_over_limit=any(r['over_limit'] for r in ls),
                listing_urls=' | '.join(r['url'] for r in ls),listing_titles=' | '.join(r['title'] for r in ls))
            for feature in PHYSICAL:row[feature]=int(any(feature in r['onsite'] for r in ls))
            for category in self.data['categories']:
                row[category+'_count']=p['counts']['citizen'][category];row[category+'_rate']=p['rates']['citizen'][category]/.59
            row['Noise-party-disturbance_count']=sum(row[c+'_count'] for c in ['Noise complaints','Loud party','Disturbance / nuisance'])
            row['Noise-party-disturbance_rate']=row['Noise-party-disturbance_count']/self.summary['exposure_years']/.59
            rows.append(row)
        frame=pd.DataFrame(rows);assert frame.pin.is_unique
        for folder in [self.out,self.avg]:frame.to_csv(folder/'property_amenity_call_audit.csv',index=False)
        return frame

    def amenities(self,frame):
        categories=self.data['categories']+['Noise-party-disturbance'];models=[]
        for count,label in [('mentioned_amenity_count','General amenity mentions'),('event_language_count','Event / group language')]:
            for category in categories:
                fig,ax=plt.subplots(figsize=(12,8));averages=[];points=[]
                for kind,title in TYPES.items():
                    data=frame[frame.permit_type.eq(kind)]
                    if data.empty:continue
                    grouped=data.groupby(count)[category+'_rate'].agg(['mean','size']).reset_index()
                    part=pd.DataFrame(dict(size=grouped[count],rate=grouped['mean'],parcels=grouped['size']))
                    ax.plot(part['size'],part.rate,'o-',label=title,color=COLORS[kind]);fit=fit_trend(part)
                    if fit:
                        xx=np.array([fit['x_min'],fit['x_max']]);ax.plot(xx,fit['intercept']+fit['slope']*xx,'--',color=COLORS[kind],label=f"{title} trend {fit['slope']:.3f} / item")
                    averages.append((title,float(data[category+'_rate'].mean()),COLORS[kind]))
                    points.extend(dict(permit_type=kind,count=int(r['size']),parcels=int(r.parcels),rate=r.rate) for _,r in part.iterrows())
                ax.set(title=category+' versus '+label.lower(),xlabel='Distinct '+label.lower()+' in one listing (maximum per parcel)',ylabel='Citizen calls per estimated occupied year',ylim=(0,None));discrete_axis(ax,count)
                note='59% scenario; matched rental parcels including zeros. The physical score uses '+', '.join(PHYSICAL)+'. Count is the maximum in one listing, not a union across units. Event/group language is separate, not a physical amenity. Recorded evidence absence is not verified absence. Descriptive association; size/location can confound.'
                if category=='Parking complaints':note+=' '+self.summary['category_coverage_note']
                baseline=self.baseline(category)
                name=f'amenities__{count}__{slug(category)}';self.save_variants(fig,ax,name,note,averages,baseline)
                for folder in [self.out,self.avg]:pd.DataFrame(points).to_csv(folder/(name+'.csv'),index=False)
        # Adjusted associations, one feature per model; every model includes the same size/type controls.
        for category in categories:
            for feature in PHYSICAL:
                data=frame.dropna(subset=['guests','approved_guests']).copy()
                y=data[category+'_count'].astype(float)
                exposure=self.summary['call_coverage']['parking_exposure_years'] if category=='Parking complaints' else self.summary['exposure_years']
                record=dict(category=category,feature=feature,parcels=len(data),events=int(y.sum()),status='insufficient event/support count')
                present=data[feature].gt(0)
                if y.sum()>=20 and present.sum()>=10 and (~present).sum()>=10 and y[present].sum()>=3 and y[~present].sum()>=3:
                    x=pd.DataFrame(dict(intercept=1.,feature=data[feature].astype(float),log_guests=np.log1p(data.guests),owner=data.permit_type.eq('owner').astype(float),log_license_count=np.log1p(data.license_count)))
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore')
                            model=sm.GLM(y,x,family=sm.families.Poisson(),offset=np.repeat(np.log(exposure*.59),len(data))).fit(cov_type='HC3',maxiter=100)
                        beta=float(model.params['feature']);se=float(model.bse['feature'])
                        if not model.converged or not np.isfinite(beta+se) or se>5:raise ValueError('unstable estimate')
                        record.update(status='estimated',adjusted_rate_ratio=float(np.exp(beta)),ci_low=float(np.exp(beta-1.96*se)),ci_high=float(np.exp(beta+1.96*se)))
                    except Exception as error:record['status']='model failed: '+str(error)
                models.append(record)
        model_table=pd.DataFrame(models)
        for folder in [self.out,self.avg]:model_table.to_csv(folder/'size_adjusted_amenity_associations.csv',index=False)
        for category in categories:
            part=model_table[model_table.category.eq(category)&model_table.status.eq('estimated')].copy()
            if part.empty:continue
            part=part.sort_values('adjusted_rate_ratio');fig,ax=plt.subplots(figsize=(12,8))
            yy=np.arange(len(part));ax.errorbar(part.adjusted_rate_ratio,yy,xerr=[part.adjusted_rate_ratio-part.ci_low,part.ci_high-part.adjusted_rate_ratio],fmt='o',color='#2563eb',capsize=4,label='Adjusted association and robust 95% interval')
            ax.axvline(1,color='#64748b',linestyle='--',label='No modeled association (ratio 1)');ax.set_yticks(yy,part.feature.str.replace('_',' '));ax.set_xscale('log');ax.set(xlabel='Adjusted call-rate ratio',title=category+' | size-adjusted amenity associations')
            from matplotlib.ticker import MaxNLocator,StrMethodFormatter
            ax.set_xscale('linear');ax.set_xlim(0,max(2,float(part.ci_high.max())*1.05));ax.xaxis.set_major_locator(MaxNLocator(nbins=8,integer=True));ax.xaxis.set_major_formatter(StrMethodFormatter('{x:.0f}'));ax.set_xlabel('Adjusted call-rate ratio')
            for folder in [self.out,self.avg]:
                for ext in ['png','svg']:fig.savefig(folder/('amenities__adjusted_associations__'+slug(category)+'__linear.'+ext),dpi=140)
            ax.set_xscale('log');ax.set_xlim(max(.001,float(part.ci_low.min())*.9),float(part.ci_high.max())*1.1);ax.set_xlabel('Adjusted call-rate ratio')
            self.save_variants(fig,ax,'amenities__adjusted_associations__'+slug(category),'Exploratory Poisson models with robust covariance. Each feature is fitted separately, controlling log advertised guests, owner-occupied type and log license count. Counts/periods are matched. Multiple comparisons are uncorrected; location and other confounding remain. Intervals are not causal effects; low-support models are omitted.')
        self.review(frame)
        return model_table

    def baseline(self,category):
        base=self.summary['measures']['citizen']['baselines']
        return sum(base[c] for c in ['Noise complaints','Loud party','Disturbance / nuisance']) if category=='Noise-party-disturbance' else base[category]

    def review(self,frame):
        for column,tag in [('All calls','all_calls'),('Noise-party-disturbance','noise_party_disturbance'),('Parking complaints','parking')]:
            ranked=frame.sort_values([column+'_count','address'],ascending=[False,True]).copy()
            ranked.insert(0,'review_rank',np.arange(1,len(ranked)+1))
            for folder in [self.out,self.avg]:ranked.to_csv(folder/f'highest_call_properties__{tag}.csv',index=False)
            top=ranked.head(15).iloc[::-1];fig,ax=plt.subplots(figsize=(12,9))
            ax.barh(top.address,top[column+'_rate'],color=[COLORS.get(t,'#64748b') for t in top.permit_type],label='Recorded-address rate; color denotes permit type')
            ax.set(title='Highest recorded '+column.lower()+' rates | review priorities',xlabel='Citizen calls per estimated occupied year')
            for i,(_,r) in enumerate(top.iterrows()):ax.annotate(f"{r[column+'_count']} calls",(r[column+'_rate'],i),xytext=(4,0),textcoords='offset points',va='center',fontsize=8)
            ax.margins(x=.35)
            note='59% occupancy scenario. One row per parcel; URLs and all listing evidence are in the paired review CSV. Calls are not confirmed violations or proof of rental-guest involvement. Review ranking uses counts, not amenity score, with address used to break count ties.'
            if column=='Parking complaints':note+=' '+self.summary['category_coverage_note']
            self.save_variants(fig,ax,'review_priorities__'+tag,note,[('Matched rental cohort',frame[column+'_rate'].mean(),'#15803d')],self.baseline(column),horizontal=True)

    def finish(self,models):
        trends=pd.DataFrame(self.fits);ranked=trends[trends.supported_increase].sort_values(['standardized_rise_fraction','r2_group_means'],ascending=False)
        picks=ranked.drop_duplicates('data_signature').drop_duplicates('plot').head(15)
        for folder in [self.out,self.avg]:
            trends.to_csv(folder/'all_trend_fits.csv',index=False);ranked.to_csv(folder/'increasing_plot_rankings.csv',index=False)
            pickdir=folder/'strongest_increases';pickdir.mkdir(exist_ok=True)
            for previous in pickdir.iterdir():
                if previous.suffix in ['.png','.svg']:
                    assert previous.resolve().is_relative_to(folder.resolve())
                    previous.unlink()
            for index,(_,r) in enumerate(picks.iterrows(),1):
                for ext in ['png','svg']:
                    shutil.copy2(folder/(r['plot']+'.'+ext),pickdir/(f'{index:02d}__'+r['plot']+'.'+ext))
            lines=['# Individual citizen-only plots with trends'+(' and averages' if folder==self.avg else ''),'',
                f'{self.plot_count} individual charts, each as PNG and SVG. Original plots/ is unchanged. Only citizen-initiated records are included; patrol/proactive-stop labels are excluded. No subplot sheets. Guest/bedroom/amenity-count axes use integer ticks; approved-capacity ticks are even numbers.','',
                '## Strongest supported upward associations','',
                'Ranking is exploratory: positive parcel-weighted slope in exact-size current full/matched cohorts, at least 30 parcels, 4 size levels, 10 category calls and group-mean R² >= 0.20. The middle-half size range must be nonzero. Rank uses fitted rise per one SD of size, divided by cohort mean rate, so bedrooms and guests are comparable. It does not establish causality or statistical significance. Overlapping minimum-cutoff curves and capacity-selected cohorts are plotted but excluded from this primary ranking. R² describes group means, not individual-property variance. Multiple comparisons are not corrected.','',
                '| Plot | Series | Parcels | Calls | Group R² | Fitted middle-half rise |','|---|---|---:|---:|---:|---:|']
            for _,r in picks.iterrows():lines.append(f"| [{r['plot']}]({r['plot']}.png) | {r['series']} | {r.parcels} | {r.category_events:.0f} | {r.r2_group_means:.2f} | {r.fitted_iqr_rise:.3f} |")
            lines+=['','Copies of these plots are in strongest_increases/. Full results are in increasing_plot_rankings.csv and all_trend_fits.csv.','',
                '## Amenities and review priorities','',
                'Physical evidence count uses hot tub, pool, grill, fire pit, sound system, bar, outdoor dining, patio and yard. It is a broad screening score, not proof of party use. The count is the largest single-listing score on each parcel, not an inflated union across listings. General mentions and event/group language are separate. No captured evidence is not proof of absence.','',
                'Adjusted feature associations use exploratory Poisson models with robust covariance, controlling advertised guest capacity, owner-occupied type and license count. Each feature is fitted separately. Models require minimum support; sparse outcomes are flagged rather than forced. This is not a causal amenity effect and does not control all location confounding.','',
                '- [Expanded adjusted associations, log and linear scales](../adjusted_association_plots/index.html)',
                
                '- [Highest noise/party/disturbance review priorities](review_priorities__noise_party_disturbance.png)',
                '- [Highest overall-call review priorities](review_priorities__all_calls.png)',
                '- [Property evidence, counts and listing URLs](property_amenity_call_audit.csv)',
                '- [Size-adjusted amenity associations and support flags](size_adjusted_amenity_associations.csv)','',
                'Highest-call lists are review priorities, not findings of violations or guest involvement. The primary nuisance ranking combines noise, loud-party and disturbance categories over the full available span. Parking stays separate because its covered period is only January 1-September 20, 2024. Main span: January 1, 2024-October 16, 2026. 59% is a scenario, not observed property occupancy.','',
                '## Average lines','',
                'In the _with_averages folder, dotted colored lines show each selected series/cohort average. Exact-group averages weight each parcel once. For overlapping minimum-cutoff groups the first cutoff gives the cohort mean; overlapping groups are not averaged together. Where categories and denominators align, a separate dashed gray residential calendar-year reference is included. Legacy denominators are kept separate. Adjusted-rate-ratio forest plots use ratio 1 as the comparison reference, not a misleading raw-rate mean.','',
                'Rebuild: python -m processing.trend_analysis. All chart data, support limits and source hashes are included.']
            (folder/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
            images=sorted(folder.glob('*.png'))
            pd.DataFrame([dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in images]).to_csv(folder/'manifest.csv',index=False)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir() if p.is_file()}
        assert self.before==after,'Original collection must remain unchanged'
        estimated=models[models.status.eq('estimated')]
        summary=dict(charts_per_folder=self.plot_count,original_charts=len(list(self.source.glob('*.svg'))),original_unchanged=True,
            increasing_series=len(ranked),selected_increasing_plots=len(picks),matched_properties=len(self.property_data_cache),
            estimated_amenity_models=len(estimated),source_manifest_sha256=hashlib.sha256((self.source/'manifest.csv').read_bytes()).hexdigest(),
            report_data_sha256=hashlib.sha256((self.root/'direct_listing_calls/report_data.js').read_bytes()).hexdigest())
        for folder in [self.out,self.avg]:(folder/'analysis_summary.json').write_text(json.dumps(summary,indent=2))
        from processing.top_correlations import build as build_top_correlations
        build_top_correlations(self.root)
        print(json.dumps(summary,indent=2),flush=True)
        return summary

def run(root=ROOT):
    analysis=Analysis(root)
    # Withdraw superseded generated outputs so a newly unsupported model cannot survive a rebuild.
    for folder in [analysis.out,analysis.avg]:
        for previous in folder.iterdir():
            if previous.is_file() and previous.suffix in ['.png','.svg','.csv','.json','.md']:
                assert previous.resolve().is_relative_to(folder.resolve())
                previous.unlink()
    analysis.existing();frame=analysis.property_data();analysis.property_data_cache=frame
    models=analysis.amenities(frame);return analysis.finish(models)

if __name__=='__main__':run()
