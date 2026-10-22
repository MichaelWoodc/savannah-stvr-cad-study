/* Opt-in, local map preferences. No listing data or call records are stored. */
(() => {
  'use strict';
  const CONSENT='stvr_study_consent_v1',STATE='stvr_study_state_v1';
  const fileMode=location.protocol==='file:';
  const localGet=key=>{try{return localStorage.getItem(key);}catch{return null;}};
  function read(key){const cookie=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith(key+'='));if(cookie){try{return decodeURIComponent(cookie.slice(key.length+1));}catch{return null;}}return fileMode?localGet(key):null;}
  function write(key,value){try{document.cookie=key+'='+encodeURIComponent(value)+'; Max-Age=31536000; Path=/; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'');}catch{}
    if(fileMode)try{localStorage.setItem(key,value);}catch{}
  }
  function remove(key){try{document.cookie=key+'=; Max-Age=0; Path=/; SameSite=Lax';localStorage.removeItem(key);}catch{}}
  let consent=read(CONSENT),restoring=false,timer;
  const banner=document.getElementById('cookie-consent');
  function save(){if(consent!=='yes'||restoring)return;const center=window.STVR_MAP.getCenter();write(STATE,JSON.stringify({version:1,filters:window.ListingScreen.getPreferences(),center:[center.lat,center.lng],zoom:window.STVR_MAP.getZoom(),ui:window.StudyUI.getPreferences()}));}
  function queueSave(){clearTimeout(timer);timer=setTimeout(save,200);}
  if(consent==='yes'){
    try{const saved=JSON.parse(read(STATE)||'null');if(saved?.version===1){restoring=true;window.ListingScreen.applyPreferences(saved.filters);
      if(Array.isArray(saved.center)&&saved.center.length===2&&saved.center.every(Number.isFinite)&&Math.abs(saved.center[0])<=85&&Math.abs(saved.center[1])<=180&&Number.isFinite(saved.zoom)&&saved.zoom>=1&&saved.zoom<=20)window.STVR_MAP.setView(saved.center,saved.zoom,{animate:false});
      window.StudyUI.applyPreferences(saved.ui);
    }}catch{}finally{restoring=false;}
  }
  banner.hidden=consent==='yes'||consent==='no';
  document.getElementById('accept-cookies').onclick=()=>{consent='yes';write(CONSENT,'yes');banner.hidden=true;save();};
  document.getElementById('decline-cookies').onclick=()=>{consent='no';clearTimeout(timer);remove(STATE);write(CONSENT,'no');banner.hidden=true;};
  document.getElementById('cookie-settings').onclick=()=>{banner.hidden=false;document.getElementById('accept-cookies').focus();};
  window.addEventListener('stvr-ui-changed',queueSave);window.addEventListener('stvr-filters-changed',queueSave);window.STVR_MAP.on('moveend zoomend',queueSave);
  document.getElementById('search').addEventListener('input',queueSave);window.addEventListener('pagehide',save);
})();
