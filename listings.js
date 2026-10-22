/* Listing text evidence and live parcel-level filters. No call is attributed to guests. */
(() => {
  'use strict';
  if(!D.listingScreen)return;
  const screen=D.listingScreen;
  const featureInfo=new Map(screen.features.map(f=>[f.id,f]));
  const listByPin=new Map();for(const l of screen.listings){if(!listByPin.has(l.pin))listByPin.set(l.pin,[]);listByPin.get(l.pin).push(l);}
  const filter={features:new Set(),overCapacity:false,minOverage:0,minCalls:0,minBedrooms:0,minGuests:0,callsBasis:'neighbors',evidence:'mention',mode:'any',categories:new Set(),rank:'combined',occupancy:59,aboveAverage:true};
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
  const categoryLabel=name=>`${emoji[name]||'📋'} ${esc(name)}`;
  const allLicensed=[...features.keys()].filter(k=>features.get(k).properties.licensed);
  const draw=D.neighborComparison.sample_draw_order||D.neighborComparison.sample_PINs;
  let cacheCategory=null,props=new Map(),directCategory=new Map(),currentListings=[],selectedPins=new Set(allLicensed),currentControls=draw;
  const active=()=>filter.overCapacity||filter.features.size>0||filter.minCalls>0||filter.minBedrooms>0||filter.minGuests>0;
  const callAllowed=c=>!filter.categories.size||filter.categories.has(c.category);
  function matches(l,chosen=filter.features){
    if(filter.minBedrooms>0&&(l.advertised_bedrooms===''||l.advertised_bedrooms===undefined||Number(l.advertised_bedrooms)<filter.minBedrooms))return false;
    if(filter.minGuests>0&&(l.advertised_capacity===''||l.advertised_capacity===undefined||Number(l.advertised_capacity)<filter.minGuests))return false;
    if(filter.overCapacity&&(!String(l.capacity_status).startsWith('advertised_exceeds')||Number(l.capacity_overage)<filter.minOverage))return false;
    if(filter.minCalls>0){const p=propsFor(l.pin),prefix=citizen()?'citizen_':'';const field=filter.callsBasis==='direct'?'direct_per_year':filter.callsBasis==='combined'?'combined_per_year':'neighbor_only_per_year';if(!p||p[prefix+field]+1e-12<filter.minCalls)return false;}
    const available=new Set(filter.evidence==='onsite'?l.onSiteFeatures:filter.evidence==='restriction'?l.restrictionFeatures:l.activeFeatures);
    return !chosen.size||(filter.mode==='all'?[...chosen].every(k=>available.has(k)):[...chosen].some(k=>available.has(k)));
  }
  function renderFeatureCounts(){
    const facets={};
    for(const f of screen.features){const toggled=new Set(filter.features);if(toggled.has(f.id))toggled.delete(f.id);else toggled.add(f.id);
      const enabled=filter.overCapacity||filter.minCalls>0||filter.minBedrooms>0||filter.minGuests>0||toggled.size>0;
      const next=enabled?new Set(screen.listings.filter(l=>l.scope_status==='eligible_residential'&&matches(l,toggled)&&propertyVisible(l.pin)).map(l=>l.pin)).size:allLicensed.filter(propertyVisible).length;
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
    if(!filter.categories.size)return true;
    const p=propsFor(pin);if(p)return p[(citizen()?'citizen_':'')+'direct_calls']>0;
    return (contextCallsByPin.get(pin)||[]).some(c=>callAllowed(c)&&(!citizen()||c.initiation==='Cit Initiated'));
  }
  function flagReasons(pin){const ls=listByPin.get(pin)||[];return {overCapacity:ls.some(l=>String(l.capacity_status).startsWith('advertised_exceeds')),amenities:[...new Set(ls.flatMap(l=>l.onSiteFeatures))]};}
  function group(members,fixed=false){let direct=0,neighbors=0,links=0,zeros=0;const categories=new Map();const prefix=citizen()?'citizen_':'';
    for(const pin of members){const p=fixed?features.get(pin).properties:propsFor(pin);direct+=p[prefix+'direct_calls'];neighbors+=p[prefix+'neighbor_only_calls'];links+=p.residential_neighbor_count;if(!p[prefix+'neighbor_only_calls'])zeros++;
      for(const other of p.neighbor_pins.map(x=>x.replace(/[^A-Z0-9]/gi,''))){for(const c of (fixed?callsByPin:directCategory).get(other)||[]){if(citizen()&&c.initiation!=='Cit Initiated')continue;categories.set(c.category,(categories.get(c.category)||0)+1);}}}
    const n=members.length;return{n,direct,neighbors,links,zeros,categories,rate:links?neighbors/links/S.exposure_years:null,
      combinedPerParcel:n+links?(direct+neighbors)/(n+links)/S.exposure_years:null,perFocal:n?neighbors/n/S.exposure_years:null,directRate:n?direct/n/S.exposure_years:null,combined:n?(direct+neighbors)/n/S.exposure_years:null};
  }
  const metric=(l)=>{const p=propsFor(l.pin),prefix=citizen()?'citizen_':'';return p?p[prefix+(filter.rank==='direct'?'direct_calls':filter.rank==='combined'?'combined_calls':'neighbor_only_calls')]:0;};
  const featureChips=l=>l.activeFeatures.map(k=>{const f=featureInfo.get(k);return f?`${f.emoji} ${esc(f.label)}`:'';}).join(' · ');
  function capacityHTML(l){const advertised=l.advertised_capacity===''?'unknown':esc(l.advertised_capacity)+(l.advertised_capacity_is_lower_bound?'+':'');
    const allowed=l.matched_approved_capacity===''?'unknown':esc(l.matched_approved_capacity);const above=String(l.capacity_status).startsWith('advertised_exceeds');
    return `<div class="${above?'capacity-flag':''}">👥 Advertised ${advertised} · matched allowance ${allowed}${above?` · +${esc(l.capacity_overage)} advertised`:''}</div><div class="source-line">${esc(l.capacity_basis.replaceAll('_',' '))} · ${esc(l.capacity_status.replaceAll('_',' '))}</div>`;}
  function evidenceHTML(l){const chosen=l.evidence.filter(e=>!filter.features.size||filter.features.has(e.feature));return `<details><summary>Quoted feature evidence (${chosen.length})</summary>${chosen.map(e=>{const f=featureInfo.get(e.feature);return `<div class="listing-evidence"><b>${f?.emoji||''} ${esc(f?.label||e.feature)}</b> · ${esc(e.status.replaceAll('_',' '))}<p>“${esc(e.excerpt)}”</p><div class="source-line">${esc(e.section)} · source line ${e.source_line} · matched “${esc(e.matched_text)}”</div></div>`;}).join('')}</details>`;}
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
    $('min-calls-value').textContent=filter.minCalls?`≥ ${fmt(filter.minCalls,1)} calls/year`:'Any call count';
    $('min-bedrooms-value').textContent=filter.minBedrooms?`${filter.minBedrooms}+ bedrooms`:'Any bedroom count';
    $('min-guests-value').textContent=filter.minGuests?`${filter.minGuests}+ guests`:'Any guest capacity';
    $('min-overage-value').textContent=filter.overCapacity?`+${filter.minOverage} or more guests`:'Any occupancy';
    currentListings=screen.listings.filter(l=>l.scope_status==='eligible_residential'&&matches(l));
    selectedPins=active()?new Set(currentListings.map(l=>l.pin)):new Set(allLicensed);
    const featureCounts=renderFeatureCounts();
    currentControls=draw;
    const a=group([...selectedPins]),b=group(currentControls,true),overallSTVR=group(allLicensed,true),allResidential=group([...features.keys()],true),occupancy=filter.occupancy/100;
    $('stvr-occupancy-value').textContent=`${filter.occupancy}%`;
    for(const [id,r] of [['residential',b],['stvr',a]]){
      for(const [key,value] of [['house',r.directRate],['combined',r.combinedPerParcel],['neighbors',r.rate]]){const cell=$(`comparison-${id}-${key}`);cell.textContent=value===null?'—':fmt(id==='stvr'?value/occupancy:value);cell.dataset.calendarRate=value===null?'':String(value);cell.title=value===null?'No qualifying parcels':`Unadjusted calendar-year rate: ${fmt(value,4)}${id==='stvr'?`; divided by ${filter.occupancy}% occupancy`:''}`;}
      $(`comparison-${id}-count`).textContent=`${fmt(r.n,0)} focal parcels`;
    }
    $('comparison-all-house').textContent=fmt(allResidential.directRate);
    $('comparison-all-house').title='Full-population average: unique residential calls / all eligible residential parcels / calendar years. Neighborhood rows are not repeated for this column.';
    $('comparison-all-count').textContent=`${fmt(allResidential.n,0)} residential parcels`;
    $('comparison-all-overall').textContent=fmt(allResidential.directRate);
    $('comparison-all-count').title='All eligible residential parcels in the study area, including licensed residential STVR parcels. Hotels and commercial parcels excluded.';
    $('comparison-residential-overall').textContent=fmt(b.combinedPerParcel);
    $('comparison-stvr-overall').textContent=fmt(overallSTVR.combinedPerParcel/occupancy);
    $('comparison-stvr-overall').title=`All ${allLicensed.length} eligible STVR parcels; unadjusted ${fmt(overallSTVR.combinedPerParcel,4)} calls per calendar year. No listing or call filters.`;
    $('occupancy-explanation').textContent=`All residential = calls / all residential parcels / year. House + neighbors = calls / (focal parcels + neighbor parcel memberships) / year; neighbors only divides by neighbor memberships. Shared neighbors can count in multiple focal neighborhoods. Zero-call parcels count; groups with no neighbors add no neighbor memberships. STVR rates are also divided by ${filter.occupancy}% occupancy. Unfiltered average ignores listing and call filters; it matches house + neighbors when no filters apply. Residential baselines ignore listing and category filters; the selected initiation measure applies to all cohorts.`;
    $('category-body').innerHTML=Object.keys(emoji).map(name=>{const x=a.categories.get(name)||0,y=b.categories.get(name)||0,z=allResidential.categories.get(name)||0;return `<tr><td><label class="category-choice"><input type="checkbox" data-call-category="${esc(name)}" ${filter.categories.has(name)?'checked':''}>${categoryLabel(name)}</label></td><td>${a.links?fmt(x/a.links/S.exposure_years/occupancy,3):'\u2014'} <small>(${x})</small></td><td>${b.links?fmt(y/b.links/S.exposure_years,3):'—'} <small>(${y})</small></td><td>${allResidential.links?fmt(z/allResidential.links/S.exposure_years,3):'\u2014'} <small>(${z})</small></td></tr>`;}).join('');
    const mapMatches=new Set(screen.listings.filter(l=>matches(l)).map(l=>l.pin));
    licenseOutlines.setStyle(f=>{const flags=flagReasons(f.id),flagged=flags.overCapacity||flags.amenities.length>0,visible=propertyVisible(f.id);return {opacity:!visible?0:!active()||selectedPins.has(f.id)?1:.08,fillOpacity:!visible?0:!active()||selectedPins.has(f.id)?0.55:0.04,fillColor:flagged?'url(#licensed-parcel-crosshatch)':'url(#licensed-parcel-hatch)'};});
    dots.eachLayer(marker=>{const visible=propertyVisible(marker.studyPin);marker.setStyle({opacity:!visible?0:!active()||mapMatches.has(marker.studyPin)?1:.05,fillOpacity:!visible?0:!active()||mapMatches.has(marker.studyPin)?1:.05});});
    const controls=new Set(currentControls);controlOutlines.setStyle(f=>({opacity:controls.has(f.id)&&propertyVisible(f.id)?1:0}));
    excludedLayer.setStyle(f=>({opacity:propertyVisible(f.id)?1:0,fillOpacity:propertyVisible(f.id)?0.24:0}));
    parcelLayer.setStyle(f=>{const base=parcelStyle(f);if(!propertyVisible(f.id))return {...base,opacity:0,fillOpacity:0};return active()&&f.properties.licensed&&!selectedPins.has(f.id)?{...base,fillOpacity:.15}:base;});
    currentListings.sort((a,b)=>metric(b)-metric(a)||Number(b.capacity_overage||0)-Number(a.capacity_overage||0)||a.folder_name.localeCompare(b.folder_name));
    const reference=filter.rank==='direct'?b.directRate:filter.rank==='combined'?b.combinedPerParcel:b.rate;
    const rankedListings=currentListings.filter(l=>propertyVisible(l.pin)&&(!filter.aboveAverage||(listingRate(l)!==null&&listingRate(l)>reference)));
    $('above-average-note').textContent=`Ranked list only; statistics unchanged. ${filter.rank==='direct'?'House':filter.rank==='combined'?'House + neighbors':'Neighbors only'} calls per parcel/year, STVR adjusted to ${filter.occupancy}% occupancy; fixed random reference ${fmt(reference,3)}.`;
    $('listing-match-status').textContent=`${rankedListings.length.toLocaleString()} listing rows | ${new Set(rankedListings.map(l=>l.pin)).size.toLocaleString()} parcels | top 40`;
    $('listing-ranking').innerHTML=rankedListings.length?`<div class="listing-rows">${rankedListings.slice(0,40).map(listingSummaryHTML).join('')}</div>`:'<p class="filter-empty">No listings match the ranked-list settings.</p>';
    const nActive=D.calls.filter(c=>callAllowed(c)&&(!citizen()||c.initiation==='Cit Initiated')).length;
    $('map-status').textContent=`${fmt(nActive,0)} residential calls in selected category · ${fmt(selectedPins.size,0)} STVR focal parcels · ${fmt(b.n,0)} random controls`;
    window.STVR_VIEW={...window.STVR_VIEW,activeCalls:nActive,selectedSTVRParcels:selectedPins.size,randomControls:b.n,listingFilterActive:active(),categories:[...filter.categories]};
    window.STVR_LISTING_STATE={matchingListings:currentListings.length,selectedPINs:[...selectedPins],controlPINs:[...currentControls],features:[...filter.features],featureCounts,evidence:filter.evidence,overCapacity:filter.overCapacity,minOverage:filter.minOverage,minCalls:filter.minCalls,minBedrooms:filter.minBedrooms,minGuests:filter.minGuests,callsBasis:filter.callsBasis,categories:[...filter.categories],occupancy:filter.occupancy,aboveAverage:filter.aboveAverage,rankedListingCount:rankedListings.length,rankReference:reference,overallSTVR,allResidential,STVR:a,control:b};
    refreshClearButton();
    window.dispatchEvent(new Event('stvr-filters-changed'));
  }
  window.ListingScreen={propertyVisible,flagReasons,propertyLinksHTML,detectedPermits:(pin,listingId)=>new Set((listByPin.get(pin)||[]).filter(l=>!listingId||String(l.listing_id)===String(listingId)).flatMap(l=>l.permit_numbers.match(/SVR-[0-9]+/g)||[])),propsFor,callAllowed,categoryLabel,parcelHTML,render};
  window.contextPopup=function(f){const p=f.properties,cs=(contextCallsByPin.get(f.id)||[]).filter(c=>(!citizen()||c.initiation==='Cit Initiated')&&callAllowed(c));return `<div class="popup-title">${esc(p.address)}</div><p class="popup-warning">Exploration only. Excluded from both averages: ${esc(p.exclusion.replaceAll('_',' '))}</p><div>PIN ${esc(p.pin)}</div><p><span class="popup-count">${cs.length}</span> retained directly matched calls · ${fmt(cs.length/S.exposure_years)}/year</p><div>${p.permits.map(esc).join(', ')}</div><p class="popup-muted">STVR border neighbors: ${p.neighboring_STVR_PINs.map(esc).join(', ')||'none'}. No commercial or hotel call enters either statistical average.</p><details class="popup-calls"><summary>Explore ${cs.length} calls</summary><table><tbody>${cs.map(c=>`<tr data-call-number="${esc(c.number)}"><td>${esc(c.date)}<br>${esc(c.number)}</td><td>${categoryLabel(c.category)}<br>${esc(c.type)}<br>${esc(c.address)}</td></tr>`).join('')}</tbody></table></details>${parcelHTML(f.id)}`;};
  $('feature-filters').innerHTML=screen.features.map(f=>`<label><input type="checkbox" value="${esc(f.id)}"><span>${f.emoji} ${esc(f.label)} <span class="feature-count" data-feature-count="${esc(f.id)}"></span></span></label>`).join('');
  $('listing-coverage').textContent=`${screen.summary.details_read.toLocaleString()} local details files screened; ${screen.summary.text_covered_residential_licensed_parcels.toLocaleString()} residential licensed parcels have matched local listing text. Unmatched/out-of-area folders stay in the all-listings audit.`;
  $('category-body').onchange=e=>{const name=e.target.dataset.callCategory;if(!name)return;if(e.target.checked)filter.categories.add(name);else filter.categories.delete(name);update();};
  $('clear-call-categories').onclick=()=>{filter.categories.clear();update();};
  $('jump-call-categories').onclick=()=>{$('category-section').open=true;$('category-section').scrollIntoView({block:'start'});};
  $('stvr-occupancy').oninput=e=>{filter.occupancy=Number(e.target.value);render();};
  $('min-calls').max=Math.max(1,Math.ceil(Math.max(...allLicensed.map(k=>features.get(k).properties.combined_per_year))));
  $('min-overage').max=Math.max(1,Math.ceil(Math.max(...screen.listings.map(l=>Number(l.capacity_overage)||0))));
  $('min-bedrooms').max=Math.max(1,Math.ceil(Math.max(...screen.listings.map(l=>Number(l.advertised_bedrooms)||0))));
  $('min-guests').max=Math.max(1,Math.ceil(Math.max(...screen.listings.map(l=>Number(l.advertised_capacity)||0))));
  for(const [id,key] of [['min-bedrooms','minBedrooms'],['min-guests','minGuests']])$(id).oninput=e=>{filter[key]=Number(e.target.value);update();};
  $('min-calls').oninput=e=>{filter.minCalls=Number(e.target.value);update();};
  $('calls-basis').onchange=e=>{filter.callsBasis=e.target.value;update();};
  $('over-capacity').onchange=e=>{filter.overCapacity=e.target.checked;filter.minOverage=filter.overCapacity?Math.max(1,filter.minOverage):0;$('min-overage').value=filter.minOverage;update();};
  $('min-overage').oninput=e=>{filter.minOverage=Number(e.target.value);filter.overCapacity=filter.minOverage>0;$('over-capacity').checked=filter.overCapacity;update();};
  $('feature-evidence').onchange=e=>{filter.evidence=e.target.value;update();};
  $('feature-mode').onchange=e=>{filter.mode=e.target.value;update();};
  $('feature-filters').onchange=e=>{if(e.target.checked)filter.features.add(e.target.value);else filter.features.delete(e.target.value);update();};
  $('above-average').onchange=e=>{filter.aboveAverage=e.target.checked;render();};
  $('listing-rank').onchange=e=>{filter.rank=e.target.value;render();};
  function refreshClearButton(){
    const changed=active()||!filter.aboveAverage||filter.occupancy!==59||filter.callsBasis!=='neighbors'||filter.evidence!=='mention'||filter.mode!=='any'||filter.categories.size>0||filter.rank!=='combined'||state.measure!=='citizen_initiated'||state.colorBy!=='neighbors'||!state.licenses||!state.excluded||state.points||state.controls||$('search').value.trim()!=='';
    const button=$('clear-listing-filters');button.classList.toggle('filters-adjusted',Boolean(changed));button.textContent=changed?'Clear all filters (adjusted)':'Clear all filters';
    button.title=changed?'Reset all filters and display settings to defaults; keep the current map area.':'All filters are at their defaults.';
  }
  $('search').addEventListener('input',refreshClearButton);
  function applyPreferences(saved={}){
    const choice=(v,allowed,fallback)=>allowed.includes(v)?v:fallback;
    filter.aboveAverage=typeof saved.aboveAverage==='boolean'?saved.aboveAverage:true;$('above-average').checked=filter.aboveAverage;
    filter.features=new Set((Array.isArray(saved.features)?saved.features:[]).filter(k=>featureInfo.has(k)));
    filter.minOverage=Math.min(Number($('min-overage').max),Math.max(0,Number(saved.minOverage)||0));filter.overCapacity=filter.minOverage>0;
    for(const [id,key] of [['min-bedrooms','minBedrooms'],['min-guests','minGuests']]){filter[key]=Math.min(Number($(id).max),Math.max(0,Number(saved[key])||0));$(id).value=filter[key];}
    filter.minCalls=Math.min(Number($('min-calls').max),Math.max(0,Number(saved.minCalls)||0));
    filter.occupancy=Math.min(100,Math.max(1,Number(saved.occupancy)||59));$('stvr-occupancy').value=filter.occupancy;
    filter.callsBasis=choice(saved.callsBasis,['neighbors','direct','combined'],'neighbors');
    filter.categories=new Set((Array.isArray(saved.categories)?saved.categories:saved.category&&saved.category!=='*'?[saved.category]:[]).filter(k=>k in emoji));filter.evidence=choice(saved.evidence,['mention','onsite','restriction'],'mention');filter.mode=choice(saved.mode,['any','all'],'any');filter.rank=saved.rankDefaultVersion===2?choice(saved.rank,['neighbors','direct','combined'],'combined'):'combined';
    state.measure=saved.callDefaultVersion===2?choice(saved.measure,['all_retained','citizen_initiated'],'citizen_initiated'):'citizen_initiated';state.colorBy=choice(saved.colorBy,['neighbors','direct','residential'],'neighbors');
    for(const [key,fallback] of [['licenses',true],['excluded',true],['points',false],['controls',false]])state[key]=typeof saved[key]==='boolean'?saved[key]:fallback;
    for(const [id,key] of [['measure','measure'],['color-by','colorBy']])$(id).value=state[key];
    for(const key of ['licenses','excluded','points','controls'])$(key).checked=state[key];
    $('over-capacity').checked=filter.overCapacity;$('min-overage').value=filter.minOverage;$('min-calls').value=filter.minCalls;$('calls-basis').value=filter.callsBasis;$('feature-evidence').value=filter.evidence;$('feature-mode').value=filter.mode;$('listing-rank').value=filter.rank;
    $('feature-filters').querySelectorAll('input').forEach(e=>e.checked=filter.features.has(e.value));$('search').value=typeof saved.search==='string'?saved.search.slice(0,200):'';$('search-result').textContent='';update();
  }
  window.ListingScreen.getPreferences=()=>({...filter,callDefaultVersion:2,rankDefaultVersion:2,categories:[...filter.categories],features:[...filter.features],...state,search:$('search').value});
  window.ListingScreen.applyPreferences=applyPreferences;
  $('clear-listing-filters').onclick=()=>applyPreferences();
  $('listing-ranking').onclick=e=>{const button=e.target.closest('[data-parcel]');if(!button)return;const f=features.get(button.dataset.parcel);map.fitBounds(L.geoJSON(f).getBounds(),{maxZoom:18,padding:[40,40]});selectParcel(f,undefined,{listingId:button.dataset.listing});
  };
  $('download-listing-view').onclick=()=>{const fields=['folder_name','title','listing_url','permit_numbers','parcel_PIN','normalized_license_address','advertised_bedrooms','advertised_capacity','matched_approved_capacity','capacity_overage','capacity_status','active_mention_features','on_site_feature_candidates','restriction_mentions','direct_calls_filtered','neighbor_calls_filtered','neighbor_calls_per_focal_year_filtered','call_category_filter','call_measure','stvr_occupancy_percent','direct_calls_per_estimated_occupied_year','neighbor_calls_per_neighbor_parcel_estimated_occupied_year','combined_calls_per_parcel_estimated_occupied_year','residential_neighbor_count'];
    const csv=fields.join(',')+'\r\n'+currentListings.map(l=>{const p=propsFor(l.pin),prefix=citizen()?'citizen_':'';const row={...l,direct_calls_filtered:p[prefix+'direct_calls'],neighbor_calls_filtered:p[prefix+'neighbor_only_calls'],neighbor_calls_per_focal_year_filtered:p[prefix+'neighbor_only_per_year'],call_category_filter:[...filter.categories].join(' | ')||'All categories',call_measure:state.measure,stvr_occupancy_percent:filter.occupancy,direct_calls_per_estimated_occupied_year:p[prefix+'direct_per_year']/(filter.occupancy/100),neighbor_calls_per_neighbor_parcel_estimated_occupied_year:p.residential_neighbor_count?p[prefix+'neighbor_only_calls']/p.residential_neighbor_count/S.exposure_years/(filter.occupancy/100):'',combined_calls_per_parcel_estimated_occupied_year:p[prefix+'combined_calls']/(1+p.residential_neighbor_count)/S.exposure_years/(filter.occupancy/100),residential_neighbor_count:p.residential_neighbor_count};return fields.map(k=>'"'+String(row[k]??'').replaceAll('"','""')+'"').join(',');}).join('\r\n');
    const a=document.createElement('a'),url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));a.href=url;a.download='filtered_listing_screen.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  update();
})();
