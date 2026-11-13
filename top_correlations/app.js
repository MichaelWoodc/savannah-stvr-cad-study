'use strict';
const DATA=window.TOP_CORRELATIONS;
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rate=value=>Number(value).toFixed(3);
const integer=value=>value===null||value===undefined?'unknown':String(Number(value));
const physical=new Set(['hot_tub','pool','grill','fire_pit','sound_system','bar','outdoor_dining','patio','yard']);
let active=DATA.factors[0],shown=[];

function propertySize(property,factor=active) {
  if(factor.size==='guests'||factor.size==='bedrooms') {
    const values=property.listings.map(l=>l[factor.size]).filter(v=>v!==null&&v!==undefined);
    return values.length?Math.max(...values):null;
  }
  return property[factor.size];
}

function selectFactor(id,updateHash=true) {
  active=DATA.factors.find(f=>f.id===String(id))||DATA.factors[0];
  document.querySelectorAll('.factor').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.factor===active.id)));
  $('factor-rank').textContent='Rank '+active.rank+' / 10';
  $('factor-title').textContent=active.size_label+' and '+active.category.toLowerCase();
  $('factor-cohort').textContent=active.series+' | '+active.cohort_label+' | exact-size groups';
  $('metrics').innerHTML=[['Properties',active.parcels],['Category calls',active.events],['Group-mean R²',active.r2.toFixed(2)],['Fitted middle-half rise',rate(active.iqr_rise)]].map(([label,value])=>`<div class="metric"><b>${esc(value)}</b><span>${label}</span></div>`).join('');
  $('png-link').href=active.png;$('svg-link').href=active.svg;$('group-link').href=active.csv;
  $('definition').textContent=`The fitted rise is ${rate(active.iqr_rise)} adjusted annual ${active.category.toLowerCase()} calls per parcel across the middle half of this cohort's size distribution. The list below is the exact ${active.parcels}-property cohort behind the selected ranked series, not both permit-type lines in the plot.`;
  const sizes=[...new Set(active.property_ids.map(pin=>propertySize(DATA.properties[pin])))].sort((a,b)=>a-b);
  $('exact-size').innerHTML='<option value="">Every size</option>'+sizes.map(size=>`<option value="${size}">${integer(size)}</option>`).join('');
  $('search').value='';$('calls-only').checked=false;$('sort').value='calls';
  if(updateHash)history.replaceState(null,'','#factor='+active.id);
  renderProperties();
}

function filteredProperties() {
  const query=$('search').value.trim().toLowerCase(),size=$('exact-size').value,onlyCalls=$('calls-only').checked;
  const rows=active.property_ids.map(pin=>DATA.properties[pin]).filter(p=>{
    if(onlyCalls&&p.counts[active.category]===0)return false;
    if(size!==''&&propertySize(p)!==Number(size))return false;
    if(query) {
      const text=[p.address,p.pin,...p.listings.flatMap(l=>[l.title,l.listing_id,l.url])].join(' ').toLowerCase();
      if(!text.includes(query))return false;
    }
    return true;
  });
  rows.sort((a,b)=>$('sort').value==='address'?a.address.localeCompare(b.address):$('sort').value==='size'?propertySize(b)-propertySize(a)||b.counts[active.category]-a.counts[active.category]:b.counts[active.category]-a.counts[active.category]||a.address.localeCompare(b.address));
  return rows;
}

function callDetails(property) {
  const calls=property.calls.filter(c=>c.category===active.category);
  if(!calls.length)return '<p>No matched calls in this category during its covered period.</p>';
  return '<div class="table-scroll"><table><thead><tr><th>Date / call number</th><th>Dispatch label</th><th>Recorded address</th><th>Source window</th></tr></thead><tbody>'+calls.map(c=>`<tr><td>${esc(c.date)}<br>${esc(c.number)}</td><td>${esc(c.type)}</td><td>${esc(c.address)}</td><td>${c.source==='raw_CAD'?'Early raw CAD':'Later published extract'}</td></tr>`).join('')+'</tbody></table></div>';
}

function propertyHTML(property) {
  const n=property.counts[active.category],annual=property.rates[active.category];
  const listings=property.listings;
  const amenityCount=listings.length?Math.max(...listings.map(l=>l.onsite.filter(k=>physical.has(k)).length)):null;
  const listingHTML=listings.length?listings.map(l=>`<div class="listing"><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a><div class="subline">Listing ${esc(l.listing_id)} | ${integer(l.guests)} advertised guests / ${integer(l.bedrooms)} bedrooms | ${integer(l.approved_guests)} matched approved guests${l.over_limit?' | Advertised '+integer(l.overage)+' above matched limit':''}</div><div class="subline">On-site candidates: ${esc(l.onsite.map(k=>DATA.features[k]||k).join(', ')||'None captured')}<br>Other mentions: ${esc(l.mention.map(k=>DATA.features[k]||k).join(', ')||'None captured')}</div></div>`).join(''):'<p>No corresponding matched Airbnb details. Advertised size and amenity evidence are unknown.</p>';
  return `<details class="property" data-pin="${esc(property.pin)}"><summary><div><div class="address">${esc(property.address)}</div><div class="subline">PIN ${esc(property.pin)} | ${esc(active.size_label)}: ${integer(propertySize(property))} | ${listings.length} matched listing${listings.length===1?'':'s'}</div></div><div class="call-badge"><strong>${n} call${n===1?'':'s'}</strong>${rate(annual)} / estimated occupied year</div></summary><div class="property-content"><p>${esc(active.category)}: <strong>${n}</strong> recorded citizen-initiated calls. Overall direct citizen calls: <strong>${property.counts['All calls']}</strong>.</p><div class="evidence">Parcel totals: ${integer(property.approved_guests)} approved guests / ${integer(property.licensed_bedrooms)} licensed bedrooms across ${property.license_count} certificate${property.license_count===1?'':'s'}.<br>Largest single-listing physical amenity count: ${amenityCount===null?'unknown':amenityCount}. Evidence labels are not findings of incidents.</div><h3>Matched Airbnb listings</h3>${listingHTML}<h3>Matching category call records</h3>${callDetails(property)}</div></details>`;
}

function renderProperties() {
  shown=filteredProperties();const events=shown.reduce((n,p)=>n+p.counts[active.category],0);
  const positives=shown.filter(p=>p.counts[active.category]>0).length;
  $('result-summary').textContent=`${shown.length} properties · ${events} category calls · ${positives} properties with calls`;
  $('properties').innerHTML=shown.map(propertyHTML).join('');$('empty').hidden=shown.length>0;
}

function downloadRows() {
  const rows=shown.map(p=>({factor_rank:active.rank,factor_size:active.size_label,call_category:active.category,cohort:active.cohort_label,
    address:p.address,pin:p.pin,permit_type:p.permit_type,size_value:propertySize(p),category_calls:p.counts[active.category],
    adjusted_annual_rate:p.rates[active.category],all_direct_citizen_calls:p.counts['All calls'],approved_guests:p.approved_guests,
    licensed_bedrooms:p.licensed_bedrooms,listing_urls:p.listings.map(l=>l.url).join(' | ')}));
  const keys=['factor_rank','factor_size','call_category','cohort','address','pin','permit_type','size_value','category_calls','adjusted_annual_rate','all_direct_citizen_calls','approved_guests','licensed_bedrooms','listing_urls'];
  const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';
  const csv=[keys.map(quote).join(','),...rows.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='factor_'+active.rank+'_properties.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

$('factors').innerHTML=DATA.factors.map(f=>`<button class="factor" type="button" data-factor="${f.id}" aria-pressed="false"><b>${f.rank}. ${esc(f.size_label)}</b><span>${esc(f.category)}</span><small>${esc(f.cohort_label)} · ${f.parcels} properties</small></button>`).join('');
document.querySelectorAll('.factor').forEach(button=>button.addEventListener('click',()=>selectFactor(button.dataset.factor)));
['search','exact-size','calls-only','sort'].forEach(id=>$(id).addEventListener('input',renderProperties));
$('clear').addEventListener('click',()=>{$('search').value='';$('exact-size').value='';$('calls-only').checked=false;renderProperties();});
$('download').addEventListener('click',downloadRows);
$('period-note').textContent=`Main period: ${DATA.summary.date_start} to ${DATA.summary.date_end}. ${DATA.summary.parking_note} Property lists and call details use only citizen initiation and exclude proactive patrol/stop dispatch labels.`;
if(!window.LISTING_MATCH_VALIDATION||DATA.summary.source_match_audit_sha256===window.LISTING_MATCH_VALIDATION.audit_sha256) {
  selectFactor(new URLSearchParams(location.hash.slice(1)).get('factor')||'1',false);
} else {
  $('factors').innerHTML='<p>Ranking rebuild in progress after source-match validation.</p>';
  document.querySelector('main').innerHTML='<section><h2>Previous ranking withdrawn</h2><p>Some historical folder-name matches lacked source-text support. The top ten is being rebuilt from verified joins; the old ranking is not shown.</p></section>';
}
