'use strict';
const DATA = DIRECT_REPORT.controls;
const PAGE = window.CAPACITY_PAGE || null;
const TYPE_LABELS={owner:'Owner-occupied',non_owner:'Non-owner-occupied',mixed:'Mixed permit types',unknown:'Unknown permit type'};
const TYPE_COLORS={owner:'#2563eb',non_owner:'#d97706',mixed:'#7c3aed',unknown:'#64748b'};
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const formatRate = n => n === null || n === undefined ? 'unavailable' : Number(n).toFixed(3);
const sizeLabels = {guests:'Advertised guest capacity', bedrooms:'Advertised bedrooms', approved_guests:'Approved guest capacity', licensed_bedrooms:'Licensed bedrooms',capacity_difference:'Advertised guests minus approved limit'};
const propertyMap = new Map(DATA.properties.map(p => [p.pin, p]));
let graphCSV = [], addressCSV = [];

function state() {
  return {cohort:$('cohort').value, permitType:$('permit-type').value,size:$('size').value, grouping:$('plot-mode').value,
    measure:$('measure').value, occupancy:Math.min(100,Math.max(1,Number($('occupancy').value)||59))/100,
    minimum:Math.max(0,Number($('min-size').value)||0), above:$('above').checked,
    over:$('over-limit').checked, capacityFloor:PAGE?.mode || 'none', evidence:$('evidence').value, featureMode:$('feature-mode').value,
    features:[...document.querySelectorAll('input[data-feature]:checked')].map(e=>e.dataset.feature)};
}

function listingPasses(listing, settings) {
  if(settings.capacityFloor && settings.capacityFloor!=='none') {
    if(!Number.isFinite(listing.guests)||!Number.isFinite(listing.approved_guests)) return false;
    if(settings.capacityFloor==='at_or_above' && listing.guests<listing.approved_guests) return false;
    if(settings.capacityFloor==='above' && listing.guests<=listing.approved_guests) return false;
  }
  if(settings.over && !listing.over_limit) return false;
  if(!settings.features.length) return true;
  const keys = listing[settings.evidence] || [];
  return settings.featureMode === 'all' ? settings.features.every(k=>keys.includes(k)) : settings.features.some(k=>keys.includes(k));
}

function selectProperties(settings) {
  const baseline = DIRECT_REPORT.summary.measures[settings.measure].baselines['All calls'];
  const needsListing = settings.cohort === 'matched' || settings.over || settings.features.length > 0 || (settings.capacityFloor && settings.capacityFloor!=='none');
  const result = [];
  for(const property of DATA.properties) {
    if(settings.permitType!=='all' && property.permit_type!==settings.permitType) continue;
    const matchingListings = property.listings.filter(l=>listingPasses(l,settings));
    if(needsListing && !matchingListings.length) continue;
    if(settings.above && !(property.rates[settings.measure]['All calls']/settings.occupancy > baseline)) continue;
    let value = property[settings.size];
    if(settings.size === 'guests' || settings.size === 'bedrooms' || settings.size==='capacity_difference') {
      const known = matchingListings.map(l=>settings.size==='capacity_difference'?l.overage:l[settings.size]).filter(x=>x!==null && x!==undefined && Number.isFinite(x));
      value = known.length ? Math.max(...known) : null;
    }
    if(settings.minimum>0 && (value===null || value===undefined || value<settings.minimum)) continue;
    result.push({...property, sizeValue:value ?? null, matchingListings});
  }
  return result;
}

function groupsFor(properties, settings) {
  const known = properties.filter(p=>p.sizeValue!==null && Number.isFinite(p.sizeValue));
  const values = [...new Set(known.map(p=>p.sizeValue))].sort((a,b)=>a-b);
  return values.map(x=>{
    const members = known.filter(p=>settings.grouping==='minimum' ? p.sizeValue>=x : p.sizeValue===x);
    const row = {size:x,parcels:members.length};
    for(const category of DATA.categories) row[category] = members.reduce((total,p)=>total+p.rates[settings.measure][category]/settings.occupancy,0)/members.length;
    row.series={};
    for(const type of Object.keys(TYPE_LABELS)) {
      const part=members.filter(p=>p.permit_type===type);
      if(!part.length)continue;
      row.series[type]={parcels:part.length};
      for(const category of DATA.categories)row.series[type][category]=part.reduce((total,p)=>total+p.rates[settings.measure][category]/settings.occupancy,0)/part.length;
    }
    return row;
  });
}

function svgChart(groups, category, settings) {
  const baseline = DIRECT_REPORT.summary.measures[settings.measure].baselines[category];
  const title = category + (category==='Parking complaints'?'*':'');
  const width=700,height=410,left=72,right=24,top=76,bottom=78,plotW=width-left-right,plotH=height-top-bottom;
  const heading = `<title>${escapeHTML(title)}</title><rect width="700" height="410" fill="white"/><text x="350" y="25" text-anchor="middle" font-size="19">${escapeHTML(title)}</text>`;
  if(!groups.length) return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 410" role="img">${heading}<text x="350" y="180" text-anchor="middle">No properties have a known size under these filters.</text><text x="350" y="210" text-anchor="middle">Clear filters or select approved guest capacity / licensed bedrooms.</text></svg>`;
  const minX=Math.min(...groups.map(g=>g.size)),maxX=Math.max(...groups.map(g=>g.size));
  const span=Math.max(1,maxX-minX),x=v=>left+((v-minX)/(span))*(plotW-20)+10;
  const maxY=Math.max(.001,baseline,...groups.flatMap(g=>Object.values(g.series).map(s=>s[category])))*1.22,y=v=>top+plotH-(v/maxY)*plotH;
  let drawing=heading;
  for(let i=0;i<=4;i++) {
    const value=maxY*i/4,yy=y(value);
    drawing+=`<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" stroke="#dfe6ef"/><text x="${left-9}" y="${yy+5}" text-anchor="end" font-size="12">${value.toFixed(maxY<.02?4:3)}</text>`;
  }
  const guestAxis=settings.size==='approved_guests'||(settings.size==='guests'&&groups.every(g=>g.size%2===0));
  const step=guestAxis?2*Math.max(1,Math.ceil(span/24)):Math.max(1,Math.ceil(span/12));
  const first=guestAxis?Math.ceil(minX/2)*2:Math.ceil(minX);
  for(let tick=first;tick<=maxX;tick+=step) {
    const xx=x(tick);drawing+=`<line x1="${xx}" y1="${top+plotH}" x2="${xx}" y2="${top+plotH+5}" stroke="#64748b"/><text x="${xx}" y="${top+plotH+22}" text-anchor="middle" font-size="12">${tick}</text>`;
  }
  drawing+=`<line x1="${left}" y1="${y(baseline)}" x2="${width-right}" y2="${y(baseline)}" stroke="#b45309" stroke-width="2" stroke-dasharray="7 5"/>`;
  const types=Object.keys(TYPE_LABELS).filter(type=>groups.some(g=>g.series[type]));
  types.forEach((type,index)=>{
    const series=groups.filter(g=>g.series[type]),color=TYPE_COLORS[type];
    const legendX=left+(index%3)*202,legendY=46+Math.floor(index/3)*17;
    drawing+=`<line x1="${legendX}" y1="${legendY-4}" x2="${legendX+20}" y2="${legendY-4}" stroke="${color}" stroke-width="3"/><text x="${legendX+25}" y="${legendY}" font-size="12">${TYPE_LABELS[type]}</text>`;
    const points=series.map(g=>`${x(g.size)},${y(g.series[type][category])}`).join(' ');
    drawing+=`<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5"/>`;
    series.forEach((g,i)=>{
      const part=g.series[type],xx=x(g.size),yy=y(part[category]);
      drawing+=`<circle cx="${xx}" cy="${yy}" r="4" fill="${color}"><title>${TYPE_LABELS[type]}; size ${escapeHTML(g.size)}: ${part.parcels} parcels; ${formatRate(part[category])} calls/year</title></circle>`;
      if(types.length===1&&(series.length<=12||i%2===0))drawing+=`<text x="${xx}" y="${yy-10}" text-anchor="middle" font-size="11">n=${part.parcels}</text>`;
    });
  });
  drawing+=`<text x="${left}" y="${height-16}" font-size="11" fill="#b45309">Dashed line: residential calendar-year reference (${formatRate(baseline)})</text><text x="350" y="${height-43}" text-anchor="middle" font-size="13">${settings.grouping==='minimum'?'Minimum ':''}${escapeHTML(sizeLabels[settings.size])}</text><text x="18" y="190" transform="rotate(-90 18 190)" text-anchor="middle" font-size="12">Calls per estimated occupied year</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 410" role="img" style="font-family:system-ui">${drawing}</svg>`;
}

function saveFile(name,content,type) {
  const url=URL.createObjectURL(new Blob([content],{type}));
  const anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function csvText(rows) {
  if(!rows.length) return 'No matching records\n';
  const keys=Object.keys(rows[0]),quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  return [keys.map(quote).join(','),...rows.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\n');
}
function graphCard(groups,category,settings,target) {
  const svg=svgChart(groups,category,settings);
  const wrapper=document.createElement('div');wrapper.className='plot';wrapper.innerHTML=svg;
  const button=document.createElement('button');button.type='button';button.textContent='Download SVG';
  button.addEventListener('click',()=>{
    const isParking=category==='Parking complaints';
    const coverage=DIRECT_REPORT.summary;
    const note=(isParking?coverage.category_coverage_note+' ':'')+`Cohort: ${settings.cohort}; permit type: ${settings.permitType}; occupancy rule: ${settings.capacityFloor||'none'}; measure: ${settings.measure}; occupancy: ${settings.occupancy*100}%; size: ${sizeLabels[settings.size]}; grouping: ${settings.grouping}; over limit: ${settings.over}; above average: ${settings.above}; evidence: ${settings.evidence}; features: ${settings.features.join(', ')||'any'}. Main period ${coverage.date_start} to ${coverage.date_end}.`;
    // Put date and settings notes inside the downloaded artifact as well as on the page.
    const exported=svg.replace('0 0 700 410','0 0 700 510').replace('</svg>',`<foreignObject x="30" y="420" width="640" height="90"><div xmlns="http://www.w3.org/1999/xhtml" style="font:12px system-ui;color:#475b73">${escapeHTML(note)}</div></foreignObject></svg>`);
    saveFile(category.replaceAll('/','-')+'_'+settings.size+'.svg',exported,'image/svg+xml');
  });
  wrapper.appendChild(button);target.appendChild(wrapper);
}

function renderAddresses(properties, settings) {
  const selectedMap=new Map(properties.map(p=>[p.pin,p]));
  const requiresListing=settings.cohort==='matched'||settings.over||settings.features.length>0||(settings.capacityFloor&&settings.capacityFloor!=='none');
  const rows=[];
  for(const address of DATA.license_addresses) {
    if(settings.permitType!=='all'&&address.call_coverage_available&&propertyMap.get(address.pin)?.permit_type!==settings.permitType)continue;
    if(settings.permitType!=='all'&&!address.call_coverage_available&&address.permit_type!==settings.permitType)continue;
    const property=selectedMap.get(address.pin);
    if(!property) {
      if(address.call_coverage_available||requiresListing||settings.above) continue;
      // Unknown call coverage stays visible for complete-address review, never in graph denominators.
      if(settings.minimum>0 && (address[settings.size]===null || address[settings.size]===undefined || address[settings.size]<settings.minimum)) continue;
      rows.push({address,property:null,listings:[]});continue;
    }
    const matching=property.matchingListings.filter(l=>l.permits.includes(address.permit));
    if(requiresListing&&!matching.length) continue;
    rows.push({address,property,listings:matching});
  }
  rows.sort((a,b)=>(b.property?.rates[settings.measure]['All calls']??-1)-(a.property?.rates[settings.measure]['All calls']??-1));
  $('address-summary').textContent=`${rows.length} licensed address rows; ${rows.filter(r=>!r.property).length} outside established call coverage. Shared-parcel totals repeat in this table.`;
  addressCSV=rows.map(({address,property,listings})=>({permit:address.permit,permit_type:address.permit_type,parcel_permit_group:property?.permit_type??null,address:address.address,unit:address.unit,pin:address.pin||address.source_apn,
    approved_guests:address.approved_guests,licensed_bedrooms:address.licensed_bedrooms,capacity_rule:address.capacity_rule,
    listing_urls:listings.map(l=>l.url).join(' | '),advertised_guests:listings.map(l=>l.guests??'unknown').join(' | '),
    advertised_over_limit:listings.some(l=>l.over_limit),
    advertised_odd_capacity:listings.some(l=>Number.isInteger(l.guests)&&l.guests%2!==0),
    direct_calls:property?property.counts[settings.measure]['All calls']:null,
    adjusted_annual_rate:property?property.rates[settings.measure]['All calls']/settings.occupancy:null,
    call_coverage:!!property,measure:settings.measure,occupancy:settings.occupancy,page_occupancy_rule:settings.capacityFloor}));
  $('rows').innerHTML=rows.map(({address,property,listings})=>{
    const rate=property?property.rates[settings.measure]['All calls']/settings.occupancy:null;
    const listingHTML=listings.length?listings.map(l=>`<a href="${escapeHTML(l.url)}" target="_blank" rel="noopener">${escapeHTML(l.title)}</a><small>Advertised: ${l.guests??'unknown'} guests / ${l.bedrooms??'unknown'} bedrooms. Matched approved: ${l.approved_guests??'unknown'} guests.${l.over_limit?' Above matched allowance by '+l.overage+'.':''}${Number.isInteger(l.guests)&&l.guests%2!==0?' Odd advertised capacity.':''}</small>`).join('<br>'):'No corresponding matched Airbnb listing';
    const evidence=[...new Set(listings.flatMap(l=>l[settings.evidence]))].map(k=>DATA.features[k]||k).join(', ');
    return `<tr><td>${escapeHTML(address.address)}<small>${escapeHTML(address.permit)} | ${escapeHTML(address.pin||address.source_apn)}${address.unit?' | '+escapeHTML(address.unit):''}</small><small>${TYPE_LABELS[address.permit_type]}${property?.permit_type==='mixed'?' (mixed-type parcel)':''}</small></td><td>${address.approved_guests??'unknown'} / ${address.licensed_bedrooms??'unknown'}<small>${escapeHTML(address.capacity_rule)}</small></td><td>${listingHTML}</td><td>${property?property.counts[settings.measure]['All calls']:'unavailable'} / ${formatRate(rate)}</td><td>${DATA.categories.slice(1).map(c=>formatRate(property?property.rates[settings.measure][c]/settings.occupancy:null)).join(' / ')}</td><td>${escapeHTML(evidence||'No matched evidence recorded')}</td></tr>`;
  }).join('');
}

function render() {
  const settings=state(),summary=DIRECT_REPORT.summary,counts=DATA.counts;
  const properties=selectProperties(settings),groups=groupsFor(properties,settings);
  const known=properties.filter(p=>p.sizeValue!==null).length;
  const baseline=summary.measures[settings.measure].baselines['All calls'];
  $('coverage').textContent=`${properties.length} covered rental parcels pass the filters; ${properties.reduce((n,p)=>n+p.matchingListings.length,0)} matching Airbnb listings.`;
  $('selection-note').textContent=`${counts.complete_license_rows} total license records; ${counts.covered_license_rows} have established residential call coverage across ${counts.covered_license_parcels} parcels. ${counts.matched_listing_parcels} covered parcels have matched Airbnb details. ${settings.over||settings.features.length?'The active listing-evidence filters require a corresponding matched listing. ':''}Properties without advertised sizes remain available under approved capacity and licensed bedrooms.`;
  $('baseline').textContent=`Residential reference: ${formatRate(baseline)} direct calls per parcel / calendar year. Rental rates use ${(settings.occupancy*100).toFixed(0)}% occupancy.`;
  $('threshold').textContent=`Above-average threshold: ${Math.floor(baseline*summary.exposure_years*settings.occupancy)+1} direct calls during ${summary.date_start} to ${summary.date_end}.`;
  $('graph-summary').textContent=`${known} unique parcels have a known ${sizeLabels[settings.size].toLowerCase()}; ${properties.length-known} have unknown selected size and are omitted. `+Object.entries(TYPE_LABELS).map(([key,label])=>label+': '+properties.filter(p=>p.permit_type===key&&p.sizeValue!==null).length).join('; ')+'.';
  if(!window.PLOTS_IN_DIRECTORY) {
    $('charts').innerHTML='';
    for(const category of DATA.categories) graphCard(groups,category,settings,$('charts'));
  }
  graphCSV=groups.flatMap(g=>Object.entries(g.series).map(([permitType,series])=>({size_measure:settings.size,grouping:settings.grouping,size:g.size,permit_type:permitType,...series,measure:settings.measure,occupancy:settings.occupancy,
    main_period:summary.date_start+' to '+summary.date_end,parking_period:summary.call_coverage.parking_date_start+' to '+summary.call_coverage.parking_date_end,
    address_cohort:settings.cohort,capacity_rule:settings.capacityFloor,above_average:settings.above,over_licensed_limit:settings.over,evidence:settings.evidence,features:settings.features.join(' | '),feature_mode:settings.featureMode})));
  const override=$('parking-cohort').value==='always_all';
  const parkingSettings=override?{...settings,cohort:'matched',minimum:0,above:false,over:false,features:[]}:settings;
  const parkingGroups=groupsFor(selectProperties(parkingSettings),parkingSettings);
  if(!window.PLOTS_IN_DIRECTORY) { $('parking-chart').innerHTML='';graphCard(parkingGroups,'Parking complaints',parkingSettings,$('parking-chart')); }
  $('parking-footnote').textContent=summary.category_coverage_note+' Dedicated parking graph: '+(override?'all matched properties within this page occupancy rule, including zeros; additional above-average, over-limit, amenity and minimum-size filters are ignored for this graph only.':'current filters are retained; an empty selection is explicitly labelled.')+' The page occupancy rule and selected permit type are never relaxed. Initiation, size measure, grouping and occupancy follow your controls. Main panels retain all current filters. Missing later parking coverage is never treated as zero.';
  $('license-coverage').textContent=`The complete workbook has ${counts.complete_license_rows} records. ${counts.complete_license_rows-counts.covered_license_rows} lack eligible call coverage or are excluded under the existing commercial/hotel rules. They remain in the complete audit and all-address review table, without invented zero-call rates.`;
  renderAddresses(properties,settings);
}

function init() {
  if(PAGE) {
    $('cohort').value='matched';$('cohort').disabled=true;
    $('size').value='capacity_difference';$('plot-mode').value='exact';
    $('over-limit').checked=PAGE.mode==='above';$('over-limit').disabled=PAGE.mode==='above';
  }
  $('feature-checkboxes').innerHTML=Object.entries(DATA.features).map(([key,label])=>`<label><input type="checkbox" data-feature="${key}"> ${escapeHTML(label)}</label>`).join('');
  document.querySelectorAll('input,select').forEach(e=>e.addEventListener('input',render));
  $('reset').addEventListener('click',()=>{
    $('above').checked=false;$('over-limit').checked=PAGE?.mode==='above';$('min-size').value=0;
    document.querySelectorAll('input[data-feature]').forEach(e=>e.checked=false);render();
  });
  $('download-groups').addEventListener('click',()=>saveFile('current_graph_groups.csv',csvText(graphCSV),'text/csv'));
  $('download-addresses').addEventListener('click',()=>saveFile('current_licensed_addresses.csv',csvText(addressCSV),'text/csv'));
  render();
}
init();
