/* Local-only study viewer. Inputs are precomputed and audited by build_study.py. */
'use strict';
const D=window.STVR_STUDY,S=D.summary;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(n,d=2)=>Number(n).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
const map=L.map('map',{preferCanvas:true,zoomControl:true});
const tiles=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'© OpenStreetMap contributors'}).addTo(map);
tiles.on('tileerror',()=>{$('map-status').textContent='Basemap unavailable. Parcel shapes and statistics remain available.';});
map.createPane('licenses');map.getPane('licenses').style.zIndex=450;
map.createPane('boundary');map.getPane('boundary').style.zIndex=460;map.getPane('boundary').style.pointerEvents='none';
const boundary=L.geoJSON(D.boundary,{pane:'boundary',interactive:false,style:{color:'#5d4a76',weight:4,fill:false,dashArray:'9 5'}}).addTo(map);
map.fitBounds(boundary.getBounds(),{padding:[25,25]});
const features=new Map(D.parcels.features.map(f=>[f.id,f]));
const excludedFeatures=new Map(D.excludedParcels.features.filter(f=>!f.properties.licensed&&f.properties.exclusion!=='hotel_or_lodging').map(f=>[f.id,f]));
const licensesByPin=new Map();
for(const r of D.licenses){const k=r.parcel_pin.replace(/[^A-Z0-9]/gi,'');if(!features.has(k))continue;if(!licensesByPin.has(k))licensesByPin.set(k,[]);licensesByPin.get(k).push(r);}
const callsByPin=new Map();for(const c of D.calls){if(!callsByPin.has(c.pin))callsByPin.set(c.pin,[]);callsByPin.get(c.pin).push(c);}
const contextCallsByPin=new Map();for(const c of D.contextCalls){if(!contextCallsByPin.has(c.pin))contextCallsByPin.set(c.pin,[]);contextCallsByPin.get(c.pin).push(c);}
const state={measure:'citizen_initiated',colorBy:'neighbors',licenses:true,excluded:true,points:false,controls:false};
const color=value=>value===0?'#f1f1e9':value<1?'#e5e7ad':value<3?'#d9b96f':value<10?'#c97744':'#9e3d35';
const citizen=()=>state.measure==='citizen_initiated';
function value(p){p=window.ListingScreen?.propsFor(p.pin.replace(/[^A-Z0-9]/gi,''))||p;const prefix=citizen()?'citizen_':'';return p[prefix+(state.colorBy==='direct'?'direct_per_year':state.colorBy==='neighbors'?'neighbor_only_per_year':state.colorBy==='residential'?'residential_combined_per_year':'combined_per_year')];}
function parcelStyle(f){const p=f.properties;return{opacity:1,weight:.7,color:'#8f9c92',fillOpacity:.75,fillColor:state.colorBy==='residential'&&!['residential','inferred_multifamily'].includes(p.classification)?'#e4e4df':color(value(p))};}
let highlight=L.layerGroup().addTo(map);
let selected=null;
function neighborhoodCalls(f,residentialOnly,neighborsOnly=false){
  const p=f.properties,keys=[...(neighborsOnly?[]:[f.id]),...p.neighbor_pins.map(x=>x.replace(/[^A-Z0-9]/gi,''))];
  const found=new Map();for(const key of keys){const feature=features.get(key);if(!feature)continue;
    if(residentialOnly&&!['residential','inferred_multifamily'].includes(feature.properties.classification))continue;
    for(const call of callsByPin.get(key)||[]){if((!citizen()||call.initiation==='Cit Initiated')&&(!window.ListingScreen||window.ListingScreen.callAllowed(call)))found.set(call.number,call);}}
  return [...found.values()].sort((a,b)=>b.date.localeCompare(a.date)||a.number.localeCompare(b.number));
}
function licenseRecordHTML(r,detected=false,related=false,label='Detected in this listing'){
  const capacity=r.approved_capacity_display;
  return `<div class="license-record${detected?' detected-license':''}${related?' related-license':''}"><strong>${esc(r.permit_number)}</strong> | approved occupancy: <b>${capacity===null||capacity===undefined||capacity===''?'unknown':esc(capacity)}</b>${r.unit_number_display?` | unit ${esc(r.unit_number_display)}`:''}<br><small>Expires ${esc(r.expiration_date)}${r.expiration_before_analysis_date===true?' (past date in inventory)':''}${detected?' | '+esc(label):related?' | Same address; not detected in this listing':''}</small></div>`;
}
function callDetails(calls,label,kind){return `<details class="popup-calls" data-call-scope="${kind}"><summary>${esc(label)}</summary><table><tbody>${calls.map(c=>`<tr data-call-number="${esc(c.number)}"><td>${esc(c.date)}<br>${esc(c.number)}</td><td><b>${window.ListingScreen?window.ListingScreen.categoryLabel(c.category):esc(c.category)}</b><br>${esc(c.type)}<br>${esc(c.address)}</td></tr>`).join('')}</tbody></table></details>`;}
function popup(f,listingId){const p=window.ListingScreen?.propsFor(f.id)||f.properties,prefix=citizen()?'citizen_':'',residentialOnly=true,neighborsOnly=state.colorBy==='neighbors';
  const calls=neighborhoodCalls(f,residentialOnly,neighborsOnly);const licenses=licensesByPin.get(f.id)||[];
  let html=`<div class="popup-title">${esc(p.address)}</div><div class="popup-muted">PIN ${esc(p.pin)} · ${esc(p.classification.replaceAll('_',' '))}</div>`;
  if(window.ListingScreen)html+=window.ListingScreen.propertyLinksHTML(f.id);
  html+=`<p><span class="popup-count">${p[prefix+'direct_calls']}</span> calls on STVR parcel · ${fmt(p[prefix+'direct_per_year'])}/year<br><span class="popup-count">${calls.length}</span> calls ${neighborsOnly?'on residential neighbors only':'on stvr parcel + residential neighbors'} · ${fmt(calls.length/S.exposure_years)}/year</p>`;
  if(p.random_control)html+='<p class="popup-muted">Selected random residential control parcel.</p>';
  html+=`<div>${p.residential_neighbor_count} residential / ${p.neighbor_count} total eligible border neighbors</div>`;
  if(licenses.length)html+=`<details class="property-licenses"><summary>${licenses.length} local license record${licenses.length===1?'':'s'}</summary>${licenses.map(r=>{const detected=window.ListingScreen?.detectedPermits(f.id,listingId).has(r.permit_number);return licenseRecordHTML(r,detected,Boolean(listingId&&!detected),listingId?'Detected in this listing':'Detected in local listings');}).join('')}</details>`;
  html+='<p class="popup-muted">Clicking highlights the immediate eligible border neighbors. A call association does not establish incident involvement.</p>';
  const direct=(callsByPin.get(f.id)||[]).filter(c=>(!citizen()||c.initiation==='Cit Initiated')&&(!window.ListingScreen||window.ListingScreen.callAllowed(c))).sort((a,b)=>b.date.localeCompare(a.date));
  html+=callDetails(direct,`View ${direct.length} calls on this property / recorded address`,'direct');
  html+=callDetails(calls,`View ${calls.length} unique ${neighborsOnly?'neighbor-only':'neighborhood'} calls`,'neighbors');
  if(window.ListingScreen)html+=window.ListingScreen.parcelHTML(f.id);
  return html;
}
function selectParcel(f,latlng,options={}){if(window.ListingScreen&&!window.ListingScreen.propertyVisible(f.id))return;selected=f.id;highlight.clearLayers();const resOnly=state.colorBy==='residential';
  for(const pin of f.properties.neighbor_pins){const other=features.get(pin.replace(/[^A-Z0-9]/gi,''));if(!other||window.ListingScreen&&!window.ListingScreen.propertyVisible(other.id))continue;if(resOnly&&!['residential','inferred_multifamily'].includes(other.properties.classification))continue;
    L.geoJSON(other,{interactive:false,style:{color:'#338389',weight:2,fillOpacity:.13,fillColor:'#338389'}}).addTo(highlight);}
  if(f.properties.licensed&&state.excluded)for(const other of excludedFeatures.values()){if((!window.ListingScreen||window.ListingScreen.propertyVisible(other.id))&&other.properties.neighboring_STVR_PINs.includes(f.properties.pin))L.geoJSON(other,{interactive:false,style:{color:'#9a672b',dashArray:'5 4',weight:2.5,fillOpacity:.12,fillColor:'#9a672b'}}).addTo(highlight);}
  const card=L.popup({maxWidth:350,...options}).setLatLng(latlng||L.geoJSON(f).getBounds().getCenter()).setContent(popup(f,options.listingId));card.studyProperty={listingId:options.listingId,kind:'residential',id:f.id};card.openOn(map);
}
const parcelLayer=L.geoJSON(D.parcels,{style:parcelStyle,onEachFeature:(f,l)=>{l.on('click',e=>selectParcel(f,e.latlng));l.bindTooltip(()=>window.ListingScreen&&!window.ListingScreen.propertyVisible(f.id)?'':`${f.properties.address} · ${f.properties.pin}`,{sticky:true});}}).addTo(map);
const licenseRenderer=L.svg({pane:'licenses'}).addTo(map);
const hatchDefs=document.createElementNS('http://www.w3.org/2000/svg','defs');
hatchDefs.innerHTML='<pattern id="licensed-parcel-hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="#163b65" stroke-width="2"/></pattern>';
hatchDefs.innerHTML+='<pattern id="licensed-parcel-crosshatch" width="7" height="7" patternUnits="userSpaceOnUse"><path d="M-1 1L1 -1M0 7L7 0M6 8L8 6" stroke="#163b65" stroke-width="1.3"/><path d="M-1 6L1 8M0 0L7 7M6 -1L8 1" stroke="#b51525" stroke-width="1.5"/></pattern>';
licenseRenderer._container.prepend(hatchDefs);
const licenseOutlines=L.geoJSON({type:'FeatureCollection',features:D.parcels.features.filter(f=>f.properties.licensed)},{pane:'licenses',renderer:licenseRenderer,interactive:false,style:{color:'#12365f',weight:4.5,fill:true,fillColor:'url(#licensed-parcel-hatch)',fillOpacity:.4}}).addTo(map);
const controlOutlines=L.geoJSON({type:'FeatureCollection',features:D.parcels.features.filter(f=>f.properties.random_control)},{interactive:false,style:{color:'#148579',weight:2,dashArray:'4 2',fill:false}});
function contextPopup(f){const p=f.properties,calls=(contextCallsByPin.get(f.id)||[]).filter(c=>!citizen()||c.initiation==='Cit Initiated');return `<div class="popup-title">${esc(p.address)}</div><p class="popup-warning">Exploration only. Excluded from both averages: ${esc(p.exclusion.replaceAll('_',' '))}</p><div>PIN ${esc(p.pin)}</div><p><span class="popup-count">${calls.length}</span> directly matched calls · ${fmt(calls.length/S.exposure_years)}/year</p><div>${p.permits.map(esc).join(', ')}</div><p class="popup-muted">STVR border neighbors: ${p.neighboring_STVR_PINs.map(esc).join(', ')||'none'}. Commercial ≥25 calls/year is flagged separately; all commercial calls are excluded regardless of volume.</p><details class="popup-calls"><summary>Explore ${calls.length} calls</summary><table><tbody>${calls.map(c=>`<tr data-call-number="${esc(c.number)}"><td>${esc(c.date)}<br>${esc(c.number)}</td><td>${esc(c.type)}<br>${esc(c.address)}</td></tr>`).join('')}</tbody></table></details>`;}
function openContext(f,latlng,options={}){if(window.ListingScreen&&!window.ListingScreen.propertyVisible(f.id))return;const card=L.popup({maxWidth:350,...options}).setLatLng(latlng||L.geoJSON(f).getBounds().getCenter()).setContent(contextPopup(f));card.studyProperty={kind:'context',id:f.id};card.openOn(map);}
const excludedLayer=L.geoJSON({type:'FeatureCollection',features:[...excludedFeatures.values()]},{style:{color:'#737574',weight:1.5,dashArray:'4 3',fillColor:'#a8a9a7',fillOpacity:.24},onEachFeature:(f,l)=>l.on('click',e=>openContext(f,e.latlng))}).addTo(map);
const dots=L.layerGroup();
for(const [pin,rows] of licensesByPin){const r=rows[0];const marker=L.circleMarker([r.latitude,r.longitude],{pane:'licenses',radius:2.6,color:'#fff',weight:.8,fillColor:'#193b63',fillOpacity:1});marker.studyPin=pin;
  marker.on('click',e=>{const f=features.get(pin);if(f)selectParcel(f,e.latlng);else{const ex=excludedFeatures.get(pin);L.popup({maxWidth:350}).setLatLng(e.latlng).setContent(contextPopup(ex)).openOn(map);}});dots.addLayer(marker);}
dots.addTo(map);
let points=L.layerGroup();
function drawPoints(){points.clearLayers();if(!state.points){map.removeLayer(points);return;}
  for(const c of D.calls){if(citizen()&&c.initiation!=='Cit Initiated')continue;if(window.ListingScreen&&!window.ListingScreen.callAllowed(c))continue;const lat=Number(c.latitude),lon=Number(c.longitude);if(!Number.isFinite(lat)||!Number.isFinite(lon)||lat<31.5||lat>33||lon<-82||lon>-80.5)continue;
    // Scope is determined by definitive recorded-address parcel, not by potentially offset point coordinates.
    const point=L.latLng(lat,lon);if(!boundary.getBounds().contains(point)||!pointInScope(lon,lat))continue;
    L.circleMarker(point,{radius:2,color:'#bb503b',weight:.5,fillOpacity:.55}).bindPopup(`${esc(c.date)} · ${esc(c.number)}<br>${esc(c.type)}<br>${esc(c.address)}`).addTo(points);}
  points.addTo(map);
}
function pointInScope(x,y){const ringContains=ring=>{let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])inside=!inside;}return inside;};const geometry=D.boundary.features[0].geometry;const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;return polygons.some(rings=>ringContains(rings[0])&&!rings.slice(1).some(ringContains));}
function update(){
  const savedUI=window.StudyUI?.getPreferences();
  parcelLayer.setStyle(parcelStyle);highlight.clearLayers();map.closePopup();selected=null;
  for(const layer of [licenseOutlines,dots]){state.licenses?layer.addTo(map):map.removeLayer(layer);}
  state.controls?controlOutlines.addTo(map):map.removeLayer(controlOutlines);
  if(state.excluded)excludedLayer.addTo(map);else map.removeLayer(excludedLayer);
  // License markings on excluded shapes follow the license toggle without removing their exclusion shading.
  excludedLayer.setStyle(f=>({color:state.licenses&&f.properties.licensed?'#193b63':'#737574',weight:state.licenses&&f.properties.licensed?3:1.5}));
  drawPoints();
  const active=D.calls.filter(c=>!citizen()||c.initiation==='Cit Initiated').length;
  $('map-status').textContent=`${fmt(active,0)} unique eligible calls · ${fmt(S.eligible_parcels,0)} eligible parcels · ${fmt(licensesByPin.size,0)} mapped licensed locations`;
  window.STVR_VIEW={state:{...state},activeCalls:active,licensedLocations:licensesByPin.size,eligibleParcels:S.eligible_parcels};
  if(window.ListingScreen)window.ListingScreen.render();
  if(savedUI)window.StudyUI.applyPreferences(savedUI);
}
$('coverage').textContent=`${S.date_start} to ${S.date_end} · ${S.exposure_days} days · ~2 years`;
$('legend').innerHTML=[[0,'0'],[.5,'<1'],[2,'1–<3'],[5,'3–<10'],[15,'10+']].map(([n,label])=>`<span><i class="swatch" style="background:${color(n)}"></i>${label}/year</span>`).join('');
for(const [id,key] of [['color-by','colorBy']])$(id).addEventListener('change',e=>{state[key]=e.target.value;update();});
for(const id of ['licenses','excluded','points','controls'])$(id).addEventListener('change',e=>{state[id]=e.target.checked;update();});
$('reset').onclick=()=>map.fitBounds(boundary.getBounds(),{padding:[25,25]});
$('toggle').onclick=()=>{document.body.classList.toggle('panel-hidden');$('toggle').setAttribute('aria-expanded',String(!document.body.classList.contains('panel-hidden')));setTimeout(()=>map.invalidateSize(),50);};
$('search-form').onsubmit=e=>{e.preventDefault();const term=$('search').value.trim().toUpperCase();if(!term){$('search-result').textContent='Enter an address, PIN, or permit.';return;}
  const found=[...features.values(),...excludedFeatures.values()].find(f=>[f.properties.address,f.properties.pin,...f.properties.permits].some(v=>String(v).toUpperCase().includes(term)));
  if(!found){$('search-result').textContent='No match among in-scope parcels.';return;}
  const bounds=L.geoJSON(found).getBounds();map.fitBounds(bounds,{maxZoom:18,padding:[50,50]});$('search-result').textContent=found.properties.address;
  if(features.has(found.id))selectParcel(found);else openContext(found,bounds.getCenter());
};
window.STVR_MAP=map;window.STVR_SELECT=id=>selectParcel(features.get(id));window.STVR_NEIGHBORHOOD_CALLS=neighborhoodCalls;
window.STVR_CONTEXT_POPUP=id=>contextPopup(excludedFeatures.get(id));
update();
