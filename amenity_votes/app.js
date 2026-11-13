'use strict';
const DATA=window.AMENITY_VOTES,$=id=>document.getElementById(id);
if(window.LISTING_MATCH_VALIDATION) {
  const validation=window.LISTING_MATCH_VALIDATION;
  DATA.properties=DATA.properties.map(p=>({...p,listings:p.listings.filter(l=>{
    const match=validation.matches[l.listing_id];
    return match&&match.pin===p.pin.replaceAll(' ','')&&[...l.permits].sort().join('|')===[...match.permits].sort().join('|');
  })})).filter(p=>p.listings.length);
  if(DATA.summary.source_hashes?.['processed_data/listing_matches/source_match_audit.csv']!==validation.audit_sha256)DATA.models=[];
}
const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=value=>Number(value).toFixed(3),whole=value=>value===null||value===undefined?'unknown':String(Number(value));
let inspectedFeature=null,currentRankings=[],currentViews=[],shownViews=[];
const featureMap=new Map(DATA.features.map(f=>[f.id,f]));

function settings() {
  return {scope:$('scope').value,outcome:$('outcome').value,reference:$('reference').value,evidence:$('evidence').value,type:$('permit-type').value,
    metric:$('metric').value,booking:Math.min(100,Math.max(1,Number($('occupancy').value)||59))/100,
    minimumSupport:Math.max(1,Number($('min-support').value)||1),minimumGuests:Math.max(0,Number($('min-guests').value)||0),
    countMode:$('count-mode').value,subtract:$('subtract').checked,normalize:$('normalize').checked,
    signed:$('sign-only').checked,over:$('over-only').checked,
    selected:new Set([...document.querySelectorAll('[data-feature]:checked')].map(e=>e.dataset.feature))};
}

function baselineFor(s) {return DATA.baselines[s.reference==='all'?'All calls':s.outcome];}

function propertyView(property,s) {
  if(s.type!=='all'&&property.permit_type!==s.type)return null;
  const listings=property.listings.filter(l=>!s.over||l.over_limit);
  if(!listings.length)return null;
  const guests=listings.map(l=>l.guests).filter(v=>v!==null);
  const capacity=guests.length?Math.max(...guests):null;
  if(s.minimumGuests&&(capacity===null||capacity<s.minimumGuests))return null;
  const key=s.evidence==='advertised'?'mention':'onsite';
  const features=new Set(listings.flatMap(l=>l[key]));
  const counts=listings.map(l=>new Set(l[key].filter(k=>s.selected.has(k))).size);
  const selectedUnion=new Set([...features].filter(k=>s.selected.has(k)));
  const count=s.countMode==='union'?selectedUnion.size:Math.max(...counts);
  const opportunities=s.scope==='direct'?s.booking:s.scope==='neighbors'?property.neighbor_count:property.neighbor_count+s.booking;
  const exposure=DATA.years[s.outcome]*opportunities;
  if(exposure<=0)return {...property,capacity,listings,features,count,scored:false};
  const calls=property.counts[s.scope][s.outcome],baseline=baselineFor(s),expected=baseline*exposure;
  const rate=calls/exposure,excess=calls-expected,annualExcess=rate-baseline;
  const raw=s.metric==='annual'?rate:calls;
  let score=s.subtract?(s.metric==='annual'?annualExcess:excess):raw;
  if(s.signed)score=Math.abs(score)<1e-12?0:Math.sign(score);
  return {...property,callRecords:property.calls,capacity,listings,features,count,scored:true,exposure,calls,expected,rate,excess,annualExcess,score};
}

function rankFeatures(views,s) {
  const rows=[];
  for(const feature of DATA.features) {
    if(!s.selected.has(feature.id))continue;
    const advertisers=views.filter(p=>p.scored&&p.features.has(feature.id));
    if(advertisers.length<s.minimumSupport)continue;
    const sum=advertisers.reduce((total,p)=>total+p.score,0);
    rows.push({...feature,properties:advertisers.length,rawVotes:advertisers.reduce((n,p)=>n+p.calls,0),
      expected:advertisers.reduce((n,p)=>n+p.expected,0),meanRate:advertisers.reduce((n,p)=>n+p.rate,0)/advertisers.length,score:s.normalize?sum/advertisers.length:sum,
      above:advertisers.filter(p=>p.annualExcess>1e-12).length,below:advertisers.filter(p=>p.annualExcess< -1e-12).length,
      equal:advertisers.filter(p=>Math.abs(p.annualExcess)<=1e-12).length});
  }
  return rows.sort((a,b)=>b.score-a.score||b.properties-a.properties);
}

function scoreName(s) {
  if(s.signed)return (s.normalize?'Mean signed':'Net signed')+' property votes';
  return (s.normalize?'Mean ':'Total ')+(s.subtract?'excess ':'')+(s.metric==='annual'?'annual call-rate votes':'call-count votes')+(s.normalize?' per advertiser':'');
}

function drawScatter(views,s) {
  const points=views.filter(p=>p.scored),width=1000,height=410,left=78,right=25,top=25,bottom=70;
  const maxX=Math.max(1,...points.map(p=>p.count)),maxY=Math.max(.001,baselineFor(s),...points.map(p=>p.rate))*1.1;
  const x=value=>left+value/maxX*(width-left-right),y=value=>height-bottom-value/maxY*(height-top-bottom);
  let svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Amenity count versus citizen call rate"><defs><clipPath id="scatter-bounds"><rect x="${left}" y="${top}" width="${width-left-right}" height="${height-top-bottom}"/></clipPath></defs><rect width="1000" height="410" fill="white"/>`;
  for(let i=0;i<=4;i++) {
    const v=maxY*i/4,yy=y(v);svg+=`<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" stroke="#e2e9ef"/><text x="${left-8}" y="${yy+4}" text-anchor="end" font-size="12">${fmt(v)}</text>`;
  }
  const step=Math.max(1,Math.ceil(maxX/14));
  for(let i=0;i<=maxX;i+=step)svg+=`<text x="${x(i)}" y="${height-bottom+24}" text-anchor="middle" font-size="12">${i}</text>`;
  const baseline=baselineFor(s);svg+=`<line x1="${left}" y1="${y(baseline)}" x2="${width-right}" y2="${y(baseline)}" stroke="#64748b" stroke-dasharray="6 5"/><text x="${left+10}" y="${y(baseline)-6}" font-size="12" fill="#526b7d">All residential: ${s.reference==='all'?'ALL citizen call types':'same selected call types'} ${fmt(baseline)}/year</text>`;
  points.forEach(p=>{svg+=`<circle cx="${x(p.count)}" cy="${y(p.rate)}" r="4" opacity=".45" fill="${p.permit_type==='owner'?'#4169b2':'#21858c'}"><title>${escapeHTML(p.address)}: ${p.count} features, ${p.calls} calls, rate ${fmt(p.rate)}</title></circle>`;});
  const n=points.length,xbar=n?points.reduce((v,p)=>v+p.count,0)/n:0,ybar=n?points.reduce((v,p)=>v+p.rate,0)/n:0;
  const variance=points.reduce((v,p)=>v+(p.count-xbar)**2,0);
  if(n>1&&variance>0) {
    const slope=points.reduce((v,p)=>v+(p.count-xbar)*(p.rate-ybar),0)/variance,intercept=ybar-slope*xbar;
    const sst=points.reduce((v,p)=>v+(p.rate-ybar)**2,0),sse=points.reduce((v,p)=>v+(p.rate-intercept-slope*p.count)**2,0);
    const minObserved=Math.min(...points.map(p=>p.count));
    svg+=`<line x1="${x(minObserved)}" y1="${y(intercept+slope*minObserved)}" x2="${x(maxX)}" y2="${y(intercept+slope*maxX)}" clip-path="url(#scatter-bounds)" stroke="#163a51" stroke-width="2" stroke-dasharray="8 4"/>`;
    $('equation').textContent=`Descriptive current-cohort fit: annual calls per exposure property ≈ ${fmt(intercept)} + ${fmt(slope)} × selected amenity count. Property-level R²: ${sst?fmt(1-sse/sst):'undefined'}. This one-variable line does not control capacity or location. The saved model comparison below tests capacity and amenities together.`;
  } else $('equation').textContent='Not enough count variation to fit a descriptive line.';
  svg+=`<line x1="${left}" y1="${y(ybar)}" x2="${width-right}" y2="${y(ybar)}" stroke="#b77a36" stroke-dasharray="2 5"/><text x="500" y="393" text-anchor="middle" font-size="14">Selected feature count (${s.countMode==='union'?'parcel union':'maximum in one listing'})</text><text x="20" y="190" transform="rotate(-90 20 190)" text-anchor="middle" font-size="13">Citizen calls per exposure property-year</text></svg>`;
  $('scatter').innerHTML=svg;
}

function renderRankings(s) {
  const largest=Math.max(1e-12,...currentRankings.map(f=>Math.abs(f.score)));
  $('reference-column').textContent=s.metric==='annual'?'Mean annual rate / reference':'Expected call count';
  $('rankings').innerHTML=currentRankings.map(f=>`<tr class="${inspectedFeature===f.id?'selected-feature':''}"><td><button class="feature-link" type="button" data-inspect="${f.id}">${escapeHTML(f.label)}</button><small>${escapeHTML(f.family)}</small></td><td>${fmt(f.score)}</td><td class="bar-cell"><div class="bar-track"><span class="bar ${f.score<0?'negative':'positive'}" style="width:${Math.abs(f.score)/largest*49}%"></span></div></td><td>${f.properties}</td><td>${f.rawVotes}</td><td>${s.metric==='annual'?fmt(f.meanRate)+' / '+fmt(baselineFor(s)):fmt(f.expected)}</td><td>${f.above} / ${f.below}<small>${f.equal} at reference</small></td></tr>`).join('');
  document.querySelectorAll('[data-inspect]').forEach(button=>button.addEventListener('click',()=>{inspectedFeature=button.dataset.inspect;render();}));
  $('no-rankings').hidden=currentRankings.length>0;
  $('ranking-description').textContent=scoreName(s)+'. '+(s.subtract?'Below-reference advertisers contribute negative values. ':'No average subtraction: zero-call advertisers contribute zero. ')+(s.normalize?'Each feature is normalized by its scored advertiser count.':'Totals may favor common features; normalize per advertiser to compare more fairly.');
}

function categoryCalls(p,s) {
  return p.callRecords.filter(c=>s.scope==='combined'||c.side===s.scope).filter(c=>s.outcome==='All calls'||(s.outcome==='Noise-party-disturbance'?['Noise complaints','Loud party','Disturbance / nuisance'].includes(c.outcome):c.outcome===s.outcome));
}

function renderProperties(s) {
  const search=$('search').value.trim().toLowerCase();
  shownViews=currentViews.filter(p=>p.scored&&(!inspectedFeature||p.features.has(inspectedFeature))&&(!search||[p.address,p.pin,...p.listings.map(l=>l.title)].join(' ').toLowerCase().includes(search)));
  const sort=$('property-sort').value;shownViews.sort((a,b)=>sort==='amenities'?b.count-a.count||b.calls-a.calls:sort==='calls'?b.calls-a.calls:b.score-a.score||b.calls-a.calls);
  $('property-heading').textContent=inspectedFeature?'Properties advertising '+featureMap.get(inspectedFeature).label:'Property scores';
  $('property-summary').textContent=`${shownViews.length} properties · ${shownViews.reduce((n,p)=>n+p.calls,0)} call memberships · ${shownViews.filter(p=>p.annualExcess<0).length} below the reference`;
  $('properties').innerHTML=shownViews.map(p=>{
    const calls=categoryCalls(p,s);
    const callTable=calls.length?'<div class="scroll"><table><thead><tr><th>Date / call</th><th>Dispatch label</th><th>Property / neighbor</th></tr></thead><tbody>'+calls.map(c=>`<tr><td>${escapeHTML(c.date)}<br>${escapeHTML(c.number)}</td><td>${escapeHTML(c.type)}</td><td>${escapeHTML(c.recorded_address)}<small>${c.side}</small></td></tr>`).join('')+'</tbody></table></div>':'<p>No matching calls; this property still contributes to baseline-adjusted scores.</p>';
    return `<details class="property"><summary><div><strong>${escapeHTML(p.address)}</strong><small>${escapeHTML(p.pin)} · ${p.count} selected features · ${p.neighbor_count} eligible neighbors</small></div><div><strong>${fmt(p.score)} vote score</strong><small>${p.calls} observed / ${fmt(p.expected)} expected calls</small></div></summary><div class="property-body"><div class="property-values"><span class="pill">Annual rate ${fmt(p.rate)}</span><span class="pill">Residential reference ${fmt(baselineFor(s))}</span><span class="pill">Excess calls ${fmt(p.excess)}</span><span class="pill">Advertised guests ${whole(p.capacity)}</span><span class="pill">Approved guests ${whole(p.approved_guests)}</span></div>${p.listings.map(l=>`<div class="listing"><a href="${escapeHTML(l.url)}" target="_blank" rel="noopener">${escapeHTML(l.title)}</a><br><small>${whole(l.guests)} advertised guests; ${whole(l.approved_guests)} matched approved guests. Features: ${escapeHTML((s.evidence==='advertised'?l.mention:l.onsite).map(k=>featureMap.get(k)?.label||k).join(', ')||'none captured')}</small></div>`).join('')}${callTable}</div></details>`;
  }).join('');
}

function renderModels(s) {
  const names={size_only:'Capacity only (+ permit type / license count)',amenity_count_only:'Amenity count only (+ permit type / licenses)',size_plus_amenities:'Capacity + amenity count',size_amenities_interaction:'Capacity + amenities + interaction',rough_capacity_times_amenities:'k × capacity × amenities',rough_capacity_times_one_plus_amenities:'k × capacity × (1 + amenities)'};
  const rows=DATA.models.filter(m=>m.scope===s.scope&&m.outcome===s.outcome).sort((a,b)=>(a.held_out_deviance??Infinity)-(b.held_out_deviance??Infinity));
  $('models').innerHTML=rows.map(m=>`<tr><td>${names[m.model]||m.model}</td><td>${m.status==='estimated'?fmt(m.held_out_deviance):escapeHTML(m.status)}</td><td>${m.status==='estimated'?fmt(m.held_out_mean_absolute_error):'unavailable'}</td><td>${m.properties??''} / ${m.events??''}</td></tr>`).join('');
  const best=rows.find(m=>m.status==='estimated');
  $('model-result').textContent=best?`Lowest held-out deviance here: ${names[best.model]}. Validation keeps overlapping neighborhoods together. A better predictive score does not prove an amenity effect. Feature-count-only and product models can still be confounded by location. ${best.validation_groups} neighborhood groups were used.`:'Saved model comparison is available for rental-only or combined locations with All calls or Noise-party-disturbance. Other combinations still update the live votes and property scores.';
}

function render() {
  const s=settings();if(inspectedFeature&&!s.selected.has(inspectedFeature))inspectedFeature=null;
  currentViews=DATA.properties.map(p=>propertyView(p,s)).filter(Boolean);
  currentRankings=rankFeatures(currentViews,s);
  const exposure=s.scope==='direct'?`${Math.round(s.booking*100)}% of one rental property`:s.scope==='neighbors'?'the eligible neighbor count':`eligible neighbor count + ${s.booking.toFixed(2)} rental property`;
  $('score-definition').textContent=scoreName(s)+': '+(s.signed?'the sign of ':'')+(s.metric==='annual'?'observed calls / exposure property-years':'observed calls')+(s.subtract?(s.metric==='annual'?' minus the residential annual category reference':' minus expected residential-average calls'):'')+'. '+(s.normalize?'Average the property scores among advertisers of each feature.':'Sum the property scores among advertisers of each feature.')+' Exposure uses '+exposure+'.';
  $('coverage').textContent=`${currentViews.length} matched properties in the cohort; ${currentViews.filter(p=>p.scored).length} have positive exposure for this scope. Citizen initiation only; patrol/proactive calls excluded.`;
  $('period').textContent=`Reference across ALL ${DATA.summary.residential_baseline_properties} eligible residential parcels: ${fmt(baselineFor(s))} ${s.reference==='all'?'ALL citizen call types':s.outcome.toLowerCase()} calls / property calendar year. All-call reference: ${fmt(DATA.baselines['All calls'])}. Same-category reference: ${fmt(DATA.baselines[s.outcome])}. ${s.reference==='all'&&s.outcome!=='All calls'?'This is a different-call-type comparison; it is not a like-for-like category excess.':''} Full span ${DATA.summary.date_start} to ${DATA.summary.date_end}. ${s.outcome==='Parking complaints'?DATA.summary.parking_note:''} Neighbors keep calendar-year exposure; only the focal rental receives the booking scenario.`;
  renderRankings(s);drawScatter(currentViews,s);renderProperties(s);renderModels(s);
}

function download(filename,rows) {
  const keys=rows.length?Object.keys(rows[0]):['no_matching_records'],quote=value=>'"'+String(value??'').replaceAll('"','""')+'"';
  const csv=[keys.map(quote).join(','),...rows.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

$('outcome').innerHTML=DATA.outcomes.map(k=>`<option>${escapeHTML(k)}</option>`).join('');
$('feature-controls').innerHTML=DATA.features.map(f=>`<label><input type="checkbox" data-feature="${f.id}" checked> ${escapeHTML(f.label)} <small>(${escapeHTML(f.family)})</small></label>`).join('');
document.querySelectorAll('input,select').forEach(e=>e.addEventListener('input',render));
for(const [id,rule] of [['all-features',()=>true],['physical-features',key=>featureMap.get(key).family==='physical candidate'],['no-features',()=>false]])$(id).addEventListener('click',()=>{document.querySelectorAll('[data-feature]').forEach(e=>e.checked=rule(e.dataset.feature));render();});
$('clear-feature').addEventListener('click',()=>{inspectedFeature=null;render();});
$('download-rankings').addEventListener('click',()=>{const s=settings();download('current_amenity_votes.csv',currentRankings.map(f=>({...f,scope:s.scope,outcome:s.outcome,metric:s.metric,reference:s.reference,subtract_average:s.subtract,normalize_per_advertiser:s.normalize,signed_votes:s.signed,evidence:s.evidence,booking:s.booking})));});
$('download-properties').addEventListener('click',()=>{const s=settings();download('current_property_scores.csv',shownViews.map(p=>({pin:p.pin,address:p.address,permit_type:p.permit_type,feature_count:p.count,observed_calls:p.calls,expected_calls:p.expected,excess_calls:p.excess,annual_rate:p.rate,vote_score:p.score,neighbors:p.neighbor_count,advertised_guests:p.capacity,scope:s.scope,outcome:s.outcome,booking:s.booking,metric:s.metric,reference:s.reference,subtract_average:s.subtract,normalize_per_advertiser:s.normalize,signed_votes:s.signed,evidence:s.evidence,listing_urls:p.listings.map(l=>l.url).join(' | ')})));});
render();
