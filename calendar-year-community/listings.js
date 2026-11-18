/* Listing text evidence and live parcel-level filters. No call is attributed to guests. */
(() => {
  'use strict';
  if(!D.listingScreen)return;
  const screen=D.listingScreen;
  const featureInfo=new Map(screen.features.map(f=>[f.id,f]));
  const listByPin=new Map();for(const l of screen.listings){if(!listByPin.has(l.pin))listByPin.set(l.pin,[]);listByPin.get(l.pin).push(l);}
  const filter={permitTypes:new Set(),maxThreePermits:false,features:new Set(),overCapacity:false,minOverage:0,minCalls:0,minTotalCalls:0,minApproved:0,comparisonMode:'none',minBedrooms:0,minGuests:0,callsBasis:'combined',evidence:'mention',mode:'any',categories:new Set(),rank:'combined',occupancy:100,aboveAverage:false};
  const emoji={
    'Noise / loud parties':'🎉','Domestic disturbances':'🏠','Sexual offenses':'⚠️',
    'Fights / physical disturbances':'🥊','Assaults / stabbings':'⚠️','Disturbance / nuisance':'📢',
    'Gunfire / shooting reports':'💥','Robbery / holdup / abduction':'🚨','Burglary':'🔓',
    'Theft / vehicle theft':'🕵️','Property damage / vandalism':'🧱','Mental health / suicide':'🧠',
    'Threats / harassment / stalking':'⚠️','Trespass / unwanted person':'🚷',
    'Suspicious activity / person / vehicle':'👀','Animal calls (excluding barking)':'🐾',
    'Welfare / missing person':'🔎','Fire / hazardous conditions / rescue':'🚒','Medical / EMS':'🩺',
    'Property checks / alarms':'🔔','Civil / service / public request':'📋','Other / unclear':'❔'
  };
  const allCategories=Object.keys(emoji);
  // Exploratory data-selected comparison; see category_selection.csv.
  // These differences do not establish causation.
  const defaultExcluded=new Set(["Animal calls (excluding barking)", "Assaults / stabbings", "Burglary", "Civil / service / public request", "Domestic disturbances", "Fire / hazardous conditions / rescue", "Gunfire / shooting reports", "Mental health / suicide", "Robbery / holdup / abduction", "Theft / vehicle theft", "Trespass / unwanted person"]);
  const exploratoryCategories=["Noise / loud parties", "Property checks / alarms", "Property damage / vandalism", "Sexual offenses", "Suspicious activity / person / vehicle"];
  const defaultCategories=["Noise / loud parties", "Property checks / alarms", "Property damage / vandalism", "Sexual offenses", "Suspicious activity / person / vehicle"];
  window.STVR_DEFAULT_CATEGORIES=[...defaultCategories];
  const categorySelectionActive=()=>filter.categories.size!==allCategories.length;
  const categoryLabel=name=>`${emoji[name]||'📋'} ${esc(name)}`;
  const allLicensed=[...features.keys()].filter(k=>features.get(k).properties.licensed);
  const draw=D.neighborComparison.sample_draw_order||D.neighborComparison.sample_PINs;
  let cacheCategory=null,residentialAverage=0,props=new Map(),directCategory=new Map(),currentListings=[],selectedPins=new Set(allLicensed),currentControls=draw;
  const listingActive=()=>filter.overCapacity||filter.features.size>0||filter.minBedrooms>0||filter.minGuests>0;
  const active=()=>listingActive()||filter.permitTypes.size>0||filter.maxThreePermits||filter.minTotalCalls>0||filter.minCalls>0||filter.minApproved>0||filter.comparisonMode!=='none';
  const permitMatches=pin=>{const rows=licensesByPin.get(pin)||[];return (!filter.maxThreePermits||(rows.length>0&&rows.length<=3))&&(!filter.permitTypes.size||rows.some(r=>filter.permitTypes.has((window.STVR_PERMIT_TYPES||{})[r.permit_number])));};
  const callAllowed=c=>filter.categories.has(c.category);
  const approvedCapacity=pin=>{const values=(licensesByPin.get(pin)||[]).map(r=>r.approved_capacity_display).filter(v=>v!==null&&v!==undefined&&String(v).trim()!==''&&Number.isFinite(Number(v))).map(Number);return values.length?Math.max(...values):null;};
  const residentialDirectAverage=()=>{rebuildCounts();return residentialAverage;};
  const parcelMatches=pin=>{if(!permitMatches(pin))return false;const capacity=approvedCapacity(pin);if(filter.minApproved&&(capacity===null||capacity<filter.minApproved))return false;const p=propsFor(pin);if(filter.comparisonMode!=='none'&&(!p||p.citizen_direct_per_year/(filter.comparisonMode==='occupied'?filter.occupancy/100:1)<=residentialDirectAverage()))return false;if(filter.minTotalCalls&&(!p||p.citizen_direct_calls<filter.minTotalCalls))return false;if(filter.minCalls){const field=filter.callsBasis==='direct'?'citizen_direct_per_year':filter.callsBasis==='combined'?'citizen_combined_per_year':'citizen_neighbor_only_per_year';if(!p||p[field]+1e-12<filter.minCalls)return false;}return true;};
  function matches(l,chosen=filter.features){
    if(!features.get(l.pin)?.properties.licensed||!parcelMatches(l.pin))return false;
    if(filter.minBedrooms>0&&(l.advertised_bedrooms===''||l.advertised_bedrooms===undefined||Number(l.advertised_bedrooms)<filter.minBedrooms))return false;
    if(filter.minGuests>0&&(l.advertised_capacity===''||l.advertised_capacity===undefined||l.advertised_capacity===null||!Number.isFinite(Number(l.advertised_capacity))||Number(l.advertised_capacity)<filter.minGuests))return false;
    if(filter.overCapacity&&(!String(l.capacity_status).startsWith('advertised_exceeds')||Number(l.capacity_overage)<filter.minOverage))return false;
    const available=new Set(filter.evidence==='onsite'?l.onSiteFeatures:filter.evidence==='restriction'?l.restrictionFeatures:l.activeFeatures);
    return !chosen.size||(filter.mode==='all'?[...chosen].every(k=>available.has(k)):[...chosen].some(k=>available.has(k)));
  }
  function renderFeatureCounts(){
    const facets={};
    for(const f of screen.features){const toggled=new Set(filter.features);if(toggled.has(f.id))toggled.delete(f.id);else toggled.add(f.id);
      const enabled=filter.comparisonMode!=='none'||filter.minApproved>0||filter.minTotalCalls>0||filter.maxThreePermits||filter.permitTypes.size>0||filter.overCapacity||filter.minCalls>0||filter.minBedrooms>0||filter.minGuests>0||toggled.size>0;
      const next=enabled?(filter.overCapacity||filter.minBedrooms>0||filter.minGuests>0||toggled.size?new Set(screen.listings.filter(l=>l.scope_status==='eligible_residential'&&matches(l,toggled)&&propertyVisible(l.pin)).map(l=>l.pin)).size:allLicensed.filter(pin=>parcelMatches(pin)&&propertyVisible(pin)).length):allLicensed.filter(propertyVisible).length;
      const visibleSelected=[...selectedPins].filter(propertyVisible).length;const delta=next-visibleSelected;facets[f.id]={next,delta};
      const badge=$('feature-filters').querySelector(`[data-feature-count="${f.id}"]`);badge.textContent=`(→${fmt(next,0)}, ${delta>0?'+':''}${fmt(delta,0)})`;
      badge.dataset.direction=delta>0?'increase':delta<0?'decrease':'same';badge.parentElement.title=`Click to ${filter.features.has(f.id)?'remove':'add'} this filter: ${fmt(next,0)} unique STVR parcels (${delta>0?'+':''}${delta} from ${visibleSelected}). Current sliders and other filters included.`;
    }
    return facets;
  }
  function rebuildCounts(){
    const categoryKey=[...filter.categories].sort().join('|');if(cacheCategory===categoryKey)return;
    cacheCategory=categoryKey;props=new Map();directCategory=new Map();
    const own=new Map(),cit=new Map();
    for(const c of D.calls){if(!callAllowed(c))continue;own.set(c.pin,(own.get(c.pin)||0)+1);if(c.initiation==='Cit Initiated')cit.set(c.pin,(cit.get(c.pin)||0)+1);
      if(!directCategory.has(c.pin))directCategory.set(c.pin,[]);directCategory.get(c.pin).push(c);}
    const residentialPins=[...features.keys()].filter(k=>!features.get(k).properties.licensed);residentialAverage=residentialPins.reduce((n,k)=>n+(cit.get(k)||0),0)/residentialPins.length/S.exposure_years;
    for(const [pin,f] of features){const p=f.properties,ns=p.neighbor_pins.map(x=>x.replace(/[^A-Z0-9]/gi,''));const a=own.get(pin)||0,b=cit.get(pin)||0;
      const n=ns.reduce((sum,k)=>sum+(own.get(k)||0),0),nc=ns.reduce((sum,k)=>sum+(cit.get(k)||0),0);
      props.set(pin,{...p,direct_calls:a,direct_per_year:a/S.exposure_years,citizen_direct_calls:b,citizen_direct_per_year:b/S.exposure_years,
        neighbor_only_calls:n,neighbor_only_per_year:n/S.exposure_years,citizen_neighbor_only_calls:nc,citizen_neighbor_only_per_year:nc/S.exposure_years,
        combined_calls:a+n,combined_per_year:(a+n)/S.exposure_years,citizen_combined_calls:b+nc,citizen_combined_per_year:(b+nc)/S.exposure_years,
        residential_combined_calls:a+n,residential_combined_per_year:(a+n)/S.exposure_years,
        citizen_residential_combined_calls:b+nc,citizen_residential_combined_per_year:(b+nc)/S.exposure_years});}
  }
  const propsFor=pin=>{rebuildCounts();return props.get(pin);};
  function propertyVisible(pin){
    if(features.get(pin)?.properties.licensed)return true;
    if(!categorySelectionActive())return true;
    const p=propsFor(pin);if(p)return p[(citizen()?'citizen_':'')+'direct_calls']>0;
    return (contextCallsByPin.get(pin)||[]).some(c=>callAllowed(c)&&(!citizen()||c.initiation==='Cit Initiated'));
  }
  function flagReasons(pin){const ls=listByPin.get(pin)||[];return {overCapacity:ls.some(l=>String(l.capacity_status).startsWith('advertised_exceeds')),amenities:[...new Set(ls.flatMap(l=>l.onSiteFeatures))]};}
  function group(members){let direct=0,neighbors=0,links=0,zeros=0;const categories=new Map();const prefix=citizen()?'citizen_':'';
    for(const pin of members){const p=propsFor(pin);direct+=p[prefix+'direct_calls'];neighbors+=p[prefix+'neighbor_only_calls'];links+=p.residential_neighbor_count;if(!p[prefix+'neighbor_only_calls'])zeros++;
      for(const other of p.neighbor_pins.map(x=>x.replace(/[^A-Z0-9]/gi,''))){for(const c of directCategory.get(other)||[]){if(citizen()&&c.initiation!=='Cit Initiated')continue;categories.set(c.category,(categories.get(c.category)||0)+1);}}}
    const n=members.length;return{n,direct,neighbors,links,zeros,categories,rate:links?neighbors/links/S.exposure_years:null,
      combinedPerParcel:n+links?(direct+neighbors)/(n+links)/S.exposure_years:null,perstvr:n?neighbors/n/S.exposure_years:null,directRate:n?direct/n/S.exposure_years:null,combined:n?(direct+neighbors)/n/S.exposure_years:null};
  }
  const metric=(l)=>{const p=propsFor(l.pin),prefix=citizen()?'citizen_':'';return p?p[prefix+(filter.rank==='direct'?'direct_calls':filter.rank==='combined'?'combined_calls':'neighbor_only_calls')]:0;};
  const featureChips=l=>l.activeFeatures.map(k=>{const f=featureInfo.get(k);return f?`${f.emoji} ${esc(f.label)}`:'';}).join(' - ');
  function capacityHTML(l){const advertised=l.advertised_capacity===''?'unknown':esc(l.advertised_capacity)+(l.advertised_capacity_is_lower_bound?'+':'');
    const allowed=l.matched_approved_capacity===''?'unknown':esc(l.matched_approved_capacity);const above=String(l.capacity_status).startsWith('advertised_exceeds');
    return `<div class="${above?'capacity-flag':''}">👥 Advertised ${advertised} - matched allowance ${allowed}${above?` - +${esc(l.capacity_overage)} advertised`:''}</div><div class="source-line">${esc(l.capacity_basis.replaceAll('_',' '))} - ${esc(l.capacity_status.replaceAll('_',' '))}</div>`;}
  function evidenceHTML(l){const chosen=l.evidence.filter(e=>!filter.features.size||filter.features.has(e.feature));return `<details><summary>Quoted feature evidence (${chosen.length})</summary>${chosen.map(e=>{const f=featureInfo.get(e.feature);return `<div class="listing-evidence"><b>${f?.emoji||''} ${esc(f?.label||e.feature)}</b> - ${esc(e.status.replaceAll('_',' '))}<p>“${esc(e.excerpt)}”</p><div class="source-line">${esc(e.section)} - source line ${e.source_line} - matched “${esc(e.matched_text)}”</div></div>`;}).join('')}</details>`;}
  function listingLicensesHTML(l){
    const detected=new Set((l.permit_numbers.match(/SVR-[0-9]+/g)||[]));
    const related=(licensesByPin.get(l.pin)||[]).filter(r=>detected.has(r.permit_number)||r.normalized_address===l.normalized_license_address);
    return `<div class="listing-license-records">${related.map(r=>licenseRecordHTML(r,detected.has(r.permit_number),!detected.has(r.permit_number))).join('')}${related.some(r=>!detected.has(r.permit_number))?'<p class="related-license"><em>Other licenses at this address may be separate units; their capacity is not added.</em></p>':''}</div>`;
  }
  function safeLink(value){try{const u=new URL(value);return u.protocol==='https:'&&(/(^|\.)airbnb\.com$/i).test(u.hostname)?u.href:'';}catch{return '';}}
  function hostLinks(l){const host=safeLink(l.host_profile_url),url=safeLink(l.listing_url);return `<span class="host-links">${host?`<a href="${esc(host)}" target="_blank" rel="noopener noreferrer">${esc(l.host_name||'Host profile')}</a>`:esc(l.host_name||'Host not recorded')}${url?` | <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Airbnb</a>`:''}</span>`;}
  function propertyLinksHTML(pin){
    const listings=listByPin.get(pin)||[];
    if(!listings.length)return features.get(pin)?.properties.licensed?'<div class="property-airbnb-links popup-muted">No matched Airbnb listing in the local files for these permits.</div>':'';
    return `<div class="property-airbnb-links"><strong>Airbnb listings</strong>${listings.map(l=>`<div>${hostLinks(l)} <small>${esc(l.permit_numbers)}</small></div>`).join('')}</div>`;
  }
  function callCountsHTML(l){const p=propsFor(l.pin);if(!p)return '';const prefix=citizen()?'citizen_':'';return `<span class="compact-calls">House <b>${p[prefix+'direct_calls']}</b> | Neighbors <b>${p[prefix+'neighbor_only_calls']}</b> | Both <b>${p[prefix+'combined_calls']}</b></span>`;}
  function sizeHTML(l){const bedrooms=l.advertised_bedrooms===''||l.advertised_bedrooms===undefined?'?':fmt(l.advertised_bedrooms,Number.isInteger(Number(l.advertised_bedrooms))?0:1);const guests=l.advertised_capacity===''?'?':esc(l.advertised_capacity)+(l.advertised_capacity_is_lower_bound?'+':'');const allowed=l.matched_approved_capacity===''?'?':esc(l.matched_approved_capacity);return `<span class="listing-size">${bedrooms} bedrooms | ${guests} guests / ${allowed} approved</span>`;}
  function overageHTML(l){return String(l.capacity_status).startsWith('advertised_exceeds')?`<span class="capacity-flag">+${esc(l.capacity_overage)} over matched allowance</span>`:'';}
  function listingRate(l){const p=propsFor(l.pin),prefix=citizen()?'citizen_':'';const calls=p[prefix+(filter.rank==='direct'?'direct_calls':filter.rank==='combined'?'combined_calls':'neighbor_only_calls')];const n=filter.rank==='direct'?1:filter.rank==='combined'?1+p.residential_neighbor_count:p.residential_neighbor_count;return n?calls/n/S.exposure_years/(filter.occupancy/100):null;}
  function listingSummaryHTML(l){const address=features.get(l.pin)?.properties.address||l.normalized_license_address;
    return `<article class="listing-summary"><button type="button" class="property-link" data-parcel="${esc(l.pin)}" data-listing="${esc(l.listing_id)}">${esc(address)}</button>${hostLinks(l)}${sizeHTML(l)}${overageHTML(l)}${callCountsHTML(l)}</article>`;
  }
  function listingHTML(l){return `<article class="listing-card">${hostLinks(l)}${sizeHTML(l)}${overageHTML(l)}${callCountsHTML(l)}${listingLicensesHTML(l)}<div class="listing-chips">${featureChips(l)}</div>${evidenceHTML(l)}</article>`;}
  function parcelHTML(pin){const ls=(listByPin.get(pin)||[]).filter(l=>!active()||matches(l));if(!ls.length)return '';
    return `<details><summary>🏡 Listing occupancy & amenity evidence (${ls.length})</summary><p class="popup-muted">Advertised capacity is not observed occupancy. Parcel calls can include other units and do not identify who caused an issue.</p>${ls.slice(0,12).map(l=>listingHTML(l,false)).join('')}${ls.length>12?'<p>Additional listings are in the CSV.</p>':''}</details>`;}
  function render(){
    rebuildCounts();
    $('min-approved-value').textContent=filter.minApproved?`${filter.minApproved}+ approved guests on one permit`:'Any approved capacity';
    $('min-calls-value').textContent=filter.minCalls?`≥ ${fmt(filter.minCalls,1)} calls/year`:'Any call count';
    $('min-bedrooms-value').textContent=filter.minBedrooms?`${filter.minBedrooms}+ bedrooms`:'Any bedroom count';
    $('min-guests-value').textContent=filter.minGuests?`${filter.minGuests}+ guests`:'Any guest capacity';
    $('min-overage-value').textContent=filter.overCapacity?`+${filter.minOverage} or more guests`:'Any occupancy';
    currentListings=screen.listings.filter(l=>l.scope_status==='eligible_residential'&&matches(l));
    selectedPins=listingActive()?new Set(currentListings.map(l=>l.pin)):new Set(allLicensed.filter(parcelMatches));
    const featureCounts=renderFeatureCounts();
    currentControls=draw;
    const a=group([...selectedPins]),b=group(currentControls),overallSTVR=group(allLicensed),allResidential=group([...features.keys()].filter(k=>!features.get(k).properties.licensed)),occupancy=filter.occupancy/100;
    $('stvr-occupancy-value').textContent=`${filter.occupancy}%`;
    const residentialAverage=allResidential.directRate;for(const [mode,id] of [['calendar','above-average-calendar'],['occupied','above-average-occupied']]){const count=allLicensed.filter(pin=>propsFor(pin).citizen_direct_per_year/(mode==='occupied'?occupancy:1)>residentialAverage).length;const pct=allLicensed.length?100*count/allLicensed.length:0;$(id).dataset.parcelCount=String(count);$(id).textContent=mode==='calendar'?`${fmt(pct,1)}% of eligible STVR parcels (${count} of ${allLicensed.length}) had direct calls above the non-STVR residential average per calendar year.`:`${fmt(pct,1)}% of eligible STVR parcels (${count} of ${allLicensed.length}) exceeded the all-residential calendar-year average per calendar year.`;}
    $('above-average-baseline').textContent=`Direct calls only; all ${allLicensed.length} eligible STVR parcels, including zero-call parcels. The non-STVR residential comparison is ${fmt(residentialAverage,3)} calls per parcel per calendar year for the selected call categories. Click a statement to show those parcels.`;
    for(const [id,r] of [['residential',b],['stvr',a]]){
      for(const [key,value] of [['house',r.directRate],['combined',r.combinedPerParcel],['neighbors',r.rate]]){const cell=$(`comparison-${id}-${key}`);cell.textContent=value===null?' - ':fmt(id==='stvr'?value/occupancy:value);cell.dataset.calendarRate=value===null?'':String(value);cell.title=value===null?'No qualifying parcels':`Unadjusted calendar-year rate: ${fmt(value,4)}${id==='stvr'?`; calendar-year rate`:''}`;}
      $(`comparison-${id}-count`).textContent=id==='stvr'?`${fmt(r.n,0)} of ${fmt(allLicensed.length,0)} eligible STVR parcels`:`${fmt(r.n,0)} random parcels`;
    }
    $('comparison-all-house').textContent=fmt(allResidential.directRate);
    $('comparison-all-house').title='Non-STVR residential average: direct calls / non-STVR residential parcels / calendar years. Neighborhood rows are not repeated for this column.';
    $('comparison-all-count').textContent=`${fmt(allResidential.n,0)} non-STVR\nparcels`;
    $('comparison-all-overall').textContent=fmt(allResidential.directRate);
    $('comparison-all-count').title='Eligible residential parcels without an STVR license in the historical study inventory. Hotels and commercial parcels excluded.';
    $('comparison-residential-overall').textContent=fmt(b.combinedPerParcel);
    $('comparison-stvr-overall').textContent=fmt(overallSTVR.combinedPerParcel/occupancy);
    $('comparison-stvr-overall').title=`All ${allLicensed.length} eligible STVR parcels; unadjusted ${fmt(overallSTVR.combinedPerParcel,4)} calls per calendar year. No listing filters; selected call categories and initiation measure apply.`;
    $('occupancy-explanation').textContent=`Rates count calls recorded directly on each parcel per calendar year. Non-STVR residential excludes eligible licensed STVR parcels. STVR reflects the selected property filters. Both use the selected call categories and include zero-call parcels. These are descriptive associations, not evidence of causation.`;
    $('category-body').innerHTML=Object.keys(emoji).map(name=>{
      const x=a.categories.get(name)||0,y=b.categories.get(name)||0,z=allResidential.categories.get(name)||0;
      if(!filter.categories.has(name))return `<tr><td><label class="category-choice"><input type="checkbox" data-call-category="${esc(name)}">${categoryLabel(name)}</label></td><td colspan="3">Excluded</td></tr>`;
      const stvrRate=a.links?x/a.links/S.exposure_years/occupancy:null;
      const averageRate=allResidential.links?z/allResidential.links/S.exposure_years:null;
      const difference=stvrRate!==null&&averageRate>0?(stvrRate/averageRate-1)*100:null;
      const rounded=difference===null?null:Math.round(difference);
      const percent=rounded===null?' - ':`${rounded<0?'−':'+'}${fmt(Math.abs(rounded),0)}%`;
      return `<tr><td><label class="category-choice"><input type="checkbox" data-call-category="${esc(name)}" ${filter.categories.has(name)?'checked':''}>${categoryLabel(name)}</label></td><td>${stvrRate===null?' - ':fmt(stvrRate,3)} <small class="category-difference" title="STVR rate compared with the non-STVR residential rate for this category; both rates use calendar years">${percent}</small><small>(${x})</small></td><td class="random-category-column">${b.links?fmt(y/b.links/S.exposure_years,3):' - '} <small>(${y})</small></td><td>${averageRate===null?' - ':fmt(averageRate,3)} <small>(${z})</small></td></tr>`;
    }).join('');
        const mapMatch=pin=>selectedPins.has(pin)&&(!categorySelectionActive()||(propsFor(pin)?.citizen_direct_calls||0)>0);
    licenseOutlines.setStyle(f=>{const flags=flagReasons(f.id),flagged=flags.overCapacity||flags.amenities.length>0,match=mapMatch(f.id);return {color:match?'#12365f':'#8494a6',weight:match?4.5:2.5,opacity:match?1:.7,fillOpacity:match?0.55:0.15,fillColor:flagged?'url(#licensed-parcel-crosshatch)':'url(#licensed-parcel-hatch)'};});
    dots.eachLayer(marker=>{const match=mapMatch(marker.studyPin);marker.setStyle({color:match?'#fff':'#e3e7eb',fillColor:match?'#193b63':'#a5b0bd',opacity:1,fillOpacity:match?1:.8});});
    const controls=new Set(currentControls);controlOutlines.setStyle(f=>({opacity:controls.has(f.id)&&propertyVisible(f.id)?1:0}));
    excludedLayer.setStyle(f=>({opacity:propertyVisible(f.id)?1:0,fillOpacity:propertyVisible(f.id)?0.24:0}));
    parcelLayer.setStyle(f=>{const base=parcelStyle(f);if(f.properties.licensed&&!mapMatch(f.id))return {...base,color:'#aeb8c2',fillColor:'#dce2e8',opacity:.85,fillOpacity:.55};if(!propertyVisible(f.id))return {...base,opacity:0,fillOpacity:0};return base;});
    currentListings.sort((a,b)=>metric(b)-metric(a)||Number(b.capacity_overage||0)-Number(a.capacity_overage||0)||a.folder_name.localeCompare(b.folder_name));
    const reference=filter.rank==='direct'?b.directRate:filter.rank==='combined'?b.combinedPerParcel:b.rate;
    const rankedListings=currentListings.filter(l=>(!categorySelectionActive()||(propsFor(l.pin)?.citizen_direct_calls||0)>0)&&(!filter.aboveAverage||(listingRate(l)!==null&&listingRate(l)>reference)));
    $('above-average-note').textContent=`Ranked list only; statistics unchanged. ${filter.rank==='direct'?'House':filter.rank==='combined'?'House + neighbors':'Neighbors only'} calls per parcel/year, STVR uses calendar-year rates; random reference for selected call types ${fmt(reference,3)}.`;
    const qualifyingParcels=(filter.comparisonMode!=='none'||filter.minApproved||filter.minTotalCalls||filter.minCalls)?[...selectedPins].filter(pin=>!categorySelectionActive()||(propsFor(pin)?.citizen_direct_calls||0)>0).sort((a,b)=>propsFor(b).citizen_direct_calls-propsFor(a).citizen_direct_calls):[];
    $('direct-call-parcels').innerHTML=(filter.comparisonMode!=='none'||filter.minApproved||filter.minTotalCalls||filter.minCalls)?`<details open><summary>${fmt(qualifyingParcels.length,0)} matching licensed parcels</summary><p class="note">Includes parcels without a matched listing. Counts are for the study period and selected call categories.</p>${qualifyingParcels.map(pin=>`<div class="listing-summary"><button type="button" class="property-link" data-direct-parcel="${esc(pin)}">${esc(features.get(pin).properties.address)}</button>${fmt(propsFor(pin).citizen_direct_calls,0)} direct calls | largest recorded permit: ${approvedCapacity(pin)===null?'unknown':esc(approvedCapacity(pin))+' guests'}</div>`).join('')}</details>`:'';
    $('listing-match-status').textContent=`${rankedListings.length.toLocaleString()} listing rows | ${new Set(rankedListings.map(l=>l.pin)).size.toLocaleString()} parcels | top 40`;
    $('listing-ranking').innerHTML=rankedListings.length?`<div class="listing-rows">${rankedListings.slice(0,40).map(listingSummaryHTML).join('')}</div>`:'<p class="filter-empty">No listings match the ranked-list settings.</p>';
    const nActive=D.calls.filter(c=>callAllowed(c)&&(!citizen()||c.initiation==='Cit Initiated')).length;
    $('map-status').textContent=`${fmt(nActive,0)} residential calls in selected category - ${fmt(selectedPins.size,0)} matching STVR parcels of ${fmt(allLicensed.length,0)} - ${fmt(b.n,0)} random controls`;
    window.STVR_VIEW={...window.STVR_VIEW,activeCalls:nActive,selectedSTVRParcels:selectedPins.size,randomControls:b.n,listingFilterActive:active(),categories:[...filter.categories]};
    window.STVR_LISTING_STATE={matchingListings:currentListings.length,selectedPINs:[...selectedPins],controlPINs:[...currentControls],features:[...filter.features],featureCounts,evidence:filter.evidence,overCapacity:filter.overCapacity,minOverage:filter.minOverage,minCalls:filter.minCalls,minTotalCalls:filter.minTotalCalls,minApproved:filter.minApproved,comparisonMode:filter.comparisonMode,minBedrooms:filter.minBedrooms,minGuests:filter.minGuests,callsBasis:filter.callsBasis,categories:[...filter.categories],occupancy:filter.occupancy,aboveAverage:filter.aboveAverage,rankedListingCount:rankedListings.length,rankReference:reference,overallSTVR,allResidential,STVR:a,control:b};
    refreshClearButton();
    window.dispatchEvent(new Event('stvr-filters-changed'));
  }
  window.ListingScreen={propertyVisible,mapMatches:pin=>selectedPins.has(pin)&&(!categorySelectionActive()||(propsFor(pin)?.citizen_direct_calls||0)>0),flagReasons,propertyLinksHTML,detectedPermits:(pin,listingId)=>new Set((listByPin.get(pin)||[]).filter(l=>!listingId||String(l.listing_id)===String(listingId)).flatMap(l=>l.permit_numbers.match(/SVR-[0-9]+/g)||[])),propsFor,callAllowed,categoryLabel,parcelHTML,render};
  window.contextPopup=function(f){const p=f.properties,cs=(contextCallsByPin.get(f.id)||[]).filter(c=>(!citizen()||c.initiation==='Cit Initiated')&&callAllowed(c));return `<div class="popup-title">${esc(p.address)}</div><p class="popup-warning">Exploration only. Excluded from both averages: ${esc(p.exclusion.replaceAll('_',' '))}</p><div>PIN ${esc(p.pin)}</div><p><span class="popup-count">${cs.length}</span> retained directly matched calls - ${fmt(cs.length/S.exposure_years)}/year</p><div>${p.permits.map(esc).join(', ')}</div><p class="popup-muted">STVR border neighbors: ${p.neighboring_STVR_PINs.map(esc).join(', ')||'none'}. No commercial or hotel call enters either statistical average.</p><details class="popup-calls"><summary>Explore ${cs.length} calls</summary><table><tbody>${cs.map(c=>`<tr data-call-number="${esc(c.number)}"><td>${esc(c.date)}<br>${esc(c.number)}</td><td>${categoryLabel(c.category)}<br>${esc(c.type)}<br>${esc(c.address)}</td></tr>`).join('')}</tbody></table></details>${parcelHTML(f.id)}`;};
  $('feature-filters').innerHTML=screen.features.map(f=>`<label><input type="checkbox" value="${esc(f.id)}" ${filter.features.has(f.id)?'checked':''}><span>${f.emoji} ${esc(f.label)} <span class="feature-count" data-feature-count="${esc(f.id)}"></span></span></label>`).join('');
  $('listing-coverage').textContent=`${screen.summary.text_covered_residential_licensed_parcels.toLocaleString()} residential licensed parcels have matched numbers in Airbnb listings. Unmatched/out-of-area listings stay in the all-listings audit.`;
  $('category-body').onchange=e=>{const name=e.target.dataset.callCategory;if(!name)return;if(e.target.checked)filter.categories.add(name);else filter.categories.delete(name);update();};
  $('exploratory-call-categories').onclick=()=>{filter.categories=new Set(exploratoryCategories);update();};
  $('clear-call-categories').onclick=()=>{filter.categories=new Set(allCategories);update();};
  $('jump-call-categories').onclick=()=>{$('category-section').open=true;$('category-section').scrollIntoView({block:'start'});};
  $('stvr-occupancy').oninput=e=>{filter.occupancy=Number(e.target.value);render();};
  $('min-calls').max=Math.max(1,Math.ceil(Math.max(...allLicensed.map(k=>features.get(k).properties.combined_per_year))));
  $('min-overage').max=Math.max(1,Math.ceil(Math.max(...screen.listings.map(l=>Number(l.capacity_overage)||0))));
  $('min-bedrooms').max=12;
  $('min-guests').max=Math.max(1,Math.ceil(Math.max(...screen.listings.map(l=>Number(l.advertised_capacity)||0))));
  for(const [id,key] of [['min-bedrooms','minBedrooms'],['min-guests','minGuests']])$(id).oninput=e=>{filter[key]=Number(e.target.value);update();};
  $('comparison-mode').onchange=e=>{filter.comparisonMode=e.target.value;update();};
  $('min-approved').oninput=e=>{filter.minApproved=Math.max(0,Math.floor(Number(e.target.value)||0));update();};
  $('min-total-calls').oninput=e=>{filter.minTotalCalls=Math.max(0,Math.floor(Number(e.target.value)||0));update();};
  $('min-calls').oninput=e=>{filter.minCalls=Number(e.target.value);update();};
  $('calls-basis').onchange=e=>{filter.callsBasis=e.target.value;update();};
  $('over-capacity').onchange=e=>{filter.overCapacity=e.target.checked;filter.minOverage=filter.overCapacity?Math.max(1,filter.minOverage):0;$('min-overage').value=filter.minOverage;update();};
  $('min-overage').oninput=e=>{filter.minOverage=Number(e.target.value);filter.overCapacity=filter.minOverage>0;$('over-capacity').checked=filter.overCapacity;update();};
  $('feature-evidence').onchange=e=>{filter.evidence=e.target.value;update();};
  $('feature-mode').onchange=e=>{filter.mode=e.target.value;update();};
  $('max-three-permits').onchange=e=>{filter.maxThreePermits=e.target.checked;update();};
  for(const [id,type] of [['permit-owner','owner'],['permit-non-owner','non_owner']])$(id).onchange=e=>{if(e.target.checked)filter.permitTypes.add(type);else filter.permitTypes.delete(type);update();};
  $('feature-filters').onchange=e=>{if(e.target.checked)filter.features.add(e.target.value);else filter.features.delete(e.target.value);update();};
  $('above-average').onchange=e=>{filter.aboveAverage=e.target.checked;render();};
  $('listing-rank').onchange=e=>{filter.rank=e.target.value;render();};
  function refreshClearButton(){
    const changed=filter.comparisonMode!=='none'||filter.minApproved>0||filter.minTotalCalls>0||filter.overCapacity||filter.minCalls>0||filter.minBedrooms>0||filter.minGuests!==6||filter.features.size!==1||!filter.features.has('pool')||filter.maxThreePermits||filter.permitTypes.size>0||filter.aboveAverage||filter.occupancy!==100||filter.callsBasis!=='direct'||filter.evidence!=='onsite'||filter.mode!=='any'||(filter.categories.size!==defaultCategories.length||defaultCategories.some(x=>!filter.categories.has(x)))||filter.rank!=='direct'||state.measure!=='citizen_initiated'||state.colorBy!=='direct'||!state.licenses||state.excluded||state.points||state.controls||$('search').value.trim()!=='';
    const button=$('clear-listing-filters');button.classList.toggle('filters-adjusted',Boolean(changed));button.textContent=changed?'Clear all filters (adjusted)':'Clear all filters';
    button.title=changed?'Reset all filters and display settings to defaults; keep the current map area.':'All filters are at their defaults.';
  }
  $('search').addEventListener('input',refreshClearButton);
  function applyPreferences(saved={}){
    const choice=(v,allowed,fallback)=>allowed.includes(v)?v:fallback;
    filter.permitTypes=new Set((Array.isArray(saved.permitTypes)?saved.permitTypes:[]).filter(x=>x==='owner'||x==='non_owner'));
    filter.maxThreePermits=typeof saved.maxThreePermits==='boolean'?saved.maxThreePermits:false;$('max-three-permits').checked=filter.maxThreePermits;
    $('permit-owner').checked=filter.permitTypes.has('owner');$('permit-non-owner').checked=filter.permitTypes.has('non_owner');
    filter.aboveAverage=typeof saved.aboveAverage==='boolean'?saved.aboveAverage:false;$('above-average').checked=filter.aboveAverage;
    filter.features=new Set((Array.isArray(saved.features)?saved.features:[]).filter(k=>featureInfo.has(k)));
    filter.minOverage=Math.min(Number($('min-overage').max),Math.max(0,Number(saved.minOverage)||0));filter.overCapacity=filter.minOverage>0;
    for(const [id,key] of [['min-bedrooms','minBedrooms'],['min-guests','minGuests']]){filter[key]=Math.min(Number($(id).max),Math.max(0,Number(saved[key])||0));$(id).value=filter[key];}
    filter.comparisonMode=choice(saved.comparisonMode,['none','calendar'],'none');$('comparison-mode').value=filter.comparisonMode;
    filter.minApproved=Math.min(100,Math.max(0,Math.floor(Number(saved.minApproved)||0)));$('min-approved').value=filter.minApproved;
    filter.minTotalCalls=Math.min(10000,Math.max(0,Math.floor(Number(saved.minTotalCalls)||0)));$('min-total-calls').value=filter.minTotalCalls;
    filter.minCalls=Math.min(Number($('min-calls').max),Math.max(0,Number(saved.minCalls)||0));
    filter.occupancy=100;$('stvr-occupancy').value=filter.occupancy;
    filter.callsBasis=choice(saved.callsBasis,['neighbors','direct','combined'],'combined');
    const previousDefault=Array.isArray(saved.categories)&&saved.categories.length===allCategories.length-1&&allCategories.filter(x=>x!=='Mental health / suicide').every(x=>saved.categories.includes(x));
    const savedCategories=Array.isArray(saved.categories)?((saved.categorySelectionVersion===2&&previousDefault)||(!saved.categorySelectionVersion&&!saved.categories.length)?defaultCategories:saved.categories):saved.category&&saved.category!=='*'?[saved.category]:defaultCategories;
    filter.categories=new Set(savedCategories.filter(k=>k in emoji));filter.evidence=choice(saved.evidence,['mention','onsite','restriction'],'mention');filter.mode=choice(saved.mode,['any','all'],'any');filter.rank=saved.rankDefaultVersion===2?choice(saved.rank,['neighbors','direct','combined'],'combined'):'combined';
    state.measure='citizen_initiated';state.colorBy=choice(saved.colorBy,['neighbors','direct','residential'],'neighbors');
    for(const [key,fallback] of [['licenses',true],['excluded',false],['points',false],['controls',false]])state[key]=typeof saved[key]==='boolean'?saved[key]:fallback;
    for(const [id,key] of [['color-by','colorBy']])$(id).value=state[key];
    for(const key of ['licenses','excluded','points','controls'])$(key).checked=state[key];
    $('over-capacity').checked=filter.overCapacity;$('min-overage').value=filter.minOverage;$('min-calls').value=filter.minCalls;$('calls-basis').value=filter.callsBasis;$('feature-evidence').value=filter.evidence;$('feature-mode').value=filter.mode;$('listing-rank').value=filter.rank;
    $('feature-filters').querySelectorAll('input').forEach(e=>e.checked=filter.features.has(e.value));$('search').value=typeof saved.search==='string'?saved.search.slice(0,200):'';$('search-result').textContent='';update();
  }
  window.ListingScreen.getPreferences=()=>({...filter,startupDefaultsVersion:4,callDefaultVersion:2,rankDefaultVersion:2,categorySelectionVersion:3,categories:[...filter.categories],features:[...filter.features],permitTypes:[...filter.permitTypes],...state,search:$('search').value});
  window.ListingScreen.applyPreferences=applyPreferences;
  const resetDefaults=()=>applyPreferences({permitTypes:[],maxThreePermits:false,features:['pool'],evidence:'onsite',comparisonMode:'none',minGuests:6,categories:defaultCategories,categorySelectionVersion:3,aboveAverage:false,rank:'direct',rankDefaultVersion:2,callsBasis:'direct',colorBy:'direct'});
  $('clear-listing-filters').onclick=()=>applyPreferences({permitTypes:[],maxThreePermits:false,features:[],comparisonMode:'none',minGuests:0,categories:allCategories,categorySelectionVersion:3,aboveAverage:false,rank:'direct',rankDefaultVersion:2,callsBasis:'direct',colorBy:'direct'});
  $('direct-call-parcels').onclick=e=>{const button=e.target.closest('[data-direct-parcel]');if(!button)return;const f=features.get(button.dataset.directParcel);map.fitBounds(L.geoJSON(f).getBounds(),{maxZoom:18,padding:[40,40]});selectParcel(f);};
  $('listing-ranking').onclick=e=>{const button=e.target.closest('[data-parcel]');if(!button)return;const f=features.get(button.dataset.parcel);map.fitBounds(L.geoJSON(f).getBounds(),{maxZoom:18,padding:[40,40]});selectParcel(f,undefined,{listingId:button.dataset.listing});
  };
  $('download-listing-view').onclick=()=>{const fields=['folder_name','title','listing_url','permit_numbers','parcel_PIN','normalized_license_address','advertised_bedrooms','advertised_capacity','matched_approved_capacity','capacity_overage','capacity_status','active_mention_features','on_site_feature_candidates','restriction_mentions','direct_calls_filtered','neighbor_calls_filtered','neighbor_calls_per_stvr_year_filtered','call_category_filter','call_measure','stvr_occupancy_percent','direct_calls_per_calendar_year','neighbor_calls_per_neighbor_parcel_calendar_year','combined_calls_per_parcel_calendar_year','residential_neighbor_count'];
    const csv=fields.join(',')+'\r\n'+currentListings.map(l=>{const p=propsFor(l.pin),prefix=citizen()?'citizen_':'';const row={...l,direct_calls_filtered:p[prefix+'direct_calls'],neighbor_calls_filtered:p[prefix+'neighbor_only_calls'],neighbor_calls_per_stvr_year_filtered:p[prefix+'neighbor_only_per_year'],call_category_filter:filter.categories.size===allCategories.length?'All categories':[...filter.categories].join(' | ')||'No categories',call_measure:state.measure,stvr_occupancy_percent:filter.occupancy,direct_calls_per_calendar_year:p[prefix+'direct_per_year']/(filter.occupancy/100),neighbor_calls_per_neighbor_parcel_calendar_year:p.residential_neighbor_count?p[prefix+'neighbor_only_calls']/p.residential_neighbor_count/S.exposure_years/(filter.occupancy/100):'',combined_calls_per_parcel_calendar_year:p[prefix+'combined_calls']/(1+p.residential_neighbor_count)/S.exposure_years/(filter.occupancy/100),residential_neighbor_count:p.residential_neighbor_count};return fields.map(k=>'"'+String(row[k]??'').replaceAll('"','""')+'"').join(',');}).join('\r\n');
    const a=document.createElement('a'),url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));a.href=url;a.download='filtered_listing_screen.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  resetDefaults();
})();
