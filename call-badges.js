/* Close-zoom labels always show direct property calls, never neighbor totals. */
(() => {
  const badges=L.layerGroup().addTo(map),cache=new Map(),MIN_ZOOM=18;
  const centers=new Map();
  for(const f of [...features.values(),...excludedFeatures.values()])centers.set(f.id,L.geoJSON(f).getBounds().getCenter());
  function highlightHighCalls(){
    const allowed=c=>(!citizen()||c.initiation==='Cit Initiated')&&(!window.ListingScreen||window.ListingScreen.callAllowed(c));
    const average=D.calls.filter(allowed).length/features.size/S.exposure_years;
    licenseOutlines.eachLayer(layer=>{
      const count=(callsByPin.get(layer.feature.id)||[]).filter(allowed).length;
      const high=average>0&&count/S.exposure_years>=3*average;
      layer.getElement()?.classList.toggle('licensed-high-calls',high);
    });
    window.STVR_HIGH_CALL_REFERENCE={annualMean:average,multiplier:3};
  }
  function refresh(){
    highlightHighCalls();
    badges.clearLayers();
    if(map.getZoom()<MIN_ZOOM)return;
    const bounds=map.getBounds().pad(.08);
    for(const [id,center] of centers){
      const residential=features.has(id),f=features.get(id)||excludedFeatures.get(id);
      if(!bounds.contains(center)||(!residential&&!state.excluded))continue;
      const calls=((residential?callsByPin:contextCallsByPin).get(id)||[]).filter(c=>(!citizen()||c.initiation==='Cit Initiated')&&(!window.ListingScreen||window.ListingScreen.callAllowed(c)));
      const count=calls.length;if(!count)continue;const key=id+':'+count;
      let marker=cache.get(key);
      if(!marker){
        marker=L.marker(center,{icon:L.divIcon({className:'parcel-call-badge',html:`<span>${count}</span>`,iconSize:[26,26],iconAnchor:[13,13]}),title:`${f.properties.address}: ${count} calls on this property. Open call details.`,keyboard:true,zIndexOffset:100});
        marker.on('click',()=>{
          if(residential)selectParcel(f,center);else openContext(f,center);

        });
        cache.set(key,marker);
      }
      marker.addTo(badges);
    }
  }
  map.on('moveend zoomend',refresh);
  window.addEventListener('stvr-filters-changed',refresh);
  window.STVR_CALL_BADGES={refresh,minZoom:MIN_ZOOM,layer:badges};
  refresh();
})();
