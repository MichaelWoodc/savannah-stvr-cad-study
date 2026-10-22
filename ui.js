/* Panel and property-card state; persisted only through consented preferences. */
(() => {
  const panel=document.querySelector('.comparison-panel'),button=$('toggle-averages');
  let current=null,restoring=false;
  const changed=()=>{if(!restoring)window.dispatchEvent(new Event('stvr-ui-changed'));};
  function setAverages(visible){panel.hidden=!visible;button.textContent=visible?'Hide averages':'Show averages';button.setAttribute('aria-expanded',String(visible));changed();}
  function setSidebar(visible){const center=map.getCenter(),zoom=map.getZoom();document.body.classList.toggle('panel-hidden',!visible);$('toggle').textContent=visible?'Hide menu':'Show menu';$('toggle').setAttribute('aria-expanded',String(visible));map.invalidateSize({pan:false});map.setView(center,zoom,{animate:false});changed();}
  button.onclick=()=>setAverages(panel.hidden);
  $('toggle').onclick=()=>setSidebar(document.body.classList.contains('panel-hidden'));
  function popupState(){
    const root=current?.getElement();
    if(!root)return null;
    return {property:current.studyProperty,latlng:[current.getLatLng().lat,current.getLatLng().lng],open:[...root.querySelectorAll('details')].flatMap((e,i)=>e.open?[i]:[]),scroll:root.querySelector('.leaflet-popup-content')?.scrollTop||0,detailsScroll:[...root.querySelectorAll('details')].map(e=>e.scrollTop),focus:[...root.querySelectorAll('details')].findIndex(e=>e.classList.contains('card-focus'))};
  }
  function focusSection(section){
    const root=section.closest('.leaflet-popup-content');if(!root)return;
    root.querySelectorAll('.card-focus').forEach(e=>e.classList.remove('card-focus'));
    if(section.open){
      if(!root.classList.contains('focus-mode'))root.dataset.previousScroll=String(root.scrollTop);
      root.style.setProperty('--property-address-height',((root.querySelector('.popup-title')?.offsetHeight||20)+8)+'px');
      root.classList.add('focus-mode');section.classList.add('card-focus');root.scrollTop=0;section.scrollTop=0;
    }else{
      root.classList.remove('focus-mode');root.scrollTop=Number(root.dataset.previousScroll)||0;
    }
    changed();
  }
  document.addEventListener('toggle',event=>{
    const section=event.target;if(restoring||!section.matches('details')||!section.closest('.leaflet-popup-content'))return;
    if(section.open||section.classList.contains('card-focus'))focusSection(section);
  },true);
  map.on('popupopen',e=>{current=e.popup;if(!restoring)setAverages(false);changed();});
  map.on('popupclose',e=>{if(current===e.popup)current=null;changed();});
  document.addEventListener('click',event=>{const summary=event.target.closest('summary');if(!summary)return;if(summary.closest('.leaflet-popup-content'))return;const container=summary.closest('#panel');if(!container)return;const top=summary.getBoundingClientRect().top;requestAnimationFrame(()=>{container.scrollTop+=summary.getBoundingClientRect().top-top;});},true);
  document.addEventListener('toggle',changed,true);
  document.addEventListener('scroll',changed,true);
  function getPreferences(){return {averagesVisible:!panel.hidden,sidebarVisible:!document.body.classList.contains('panel-hidden'),property:popupState(),sidebarDetails:[...$('panel').querySelectorAll('details')].map(e=>e.open),sidebarScroll:$('panel').scrollTop,featureScroll:$('feature-filters').scrollTop,rankingScroll:($('listing-ranking').querySelector('.listing-rows')||$('listing-ranking')).scrollTop,panelScroll:panel.scrollTop};}
  function restorePopup(saved){
    if(!saved?.property)return;
    const {id,kind,listingId}=saved.property;
    if(window.ListingScreen&&!window.ListingScreen.propertyVisible(id))return;
    if(kind==='residential'&&features.has(id))selectParcel(features.get(id),saved.latlng,{autoPan:false,listingId});
    else if(kind==='context'&&excludedFeatures.has(id))openContext(excludedFeatures.get(id),saved.latlng,{autoPan:false});
    else return;
    const root=current?.getElement();if(!root)return;
    const opened=new Set(Array.isArray(saved.open)?saved.open:[]);
    root.querySelectorAll('details').forEach((e,i)=>{e.open=opened.has(i);e.scrollTop=Number(saved.detailsScroll?.[i])||0;});
    root.querySelector('.leaflet-popup-content').scrollTop=Number(saved.scroll)||0;
    const focused=root.querySelectorAll('details')[saved.focus];if(focused?.open)focusSection(focused);
  }
  function applyPreferences(saved={}){
    restoring=true;
    try{
      setSidebar(saved.sidebarVisible!==false);
      $('panel').querySelectorAll('details').forEach((e,i)=>{if(typeof saved.sidebarDetails?.[i]==='boolean')e.open=saved.sidebarDetails[i];});
      restorePopup(saved.property);
      setAverages(saved.averagesVisible!==false);
      $('panel').scrollTop=Number(saved.sidebarScroll)||0;$('feature-filters').scrollTop=Number(saved.featureScroll)||0;($('listing-ranking').querySelector('.listing-rows')||$('listing-ranking')).scrollTop=Number(saved.rankingScroll)||0;panel.scrollTop=Number(saved.panelScroll)||0;
    }finally{restoring=false;}
  }
  window.StudyUI={focusSection,getPreferences,applyPreferences,setAverages,popupState,restorePopup};
  setAverages(true);setSidebar(true);
})();
