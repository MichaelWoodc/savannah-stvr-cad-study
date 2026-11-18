/* Per-page preferences only. Cookies with local-storage fallback for file previews. */
(() => {
  'use strict';
  // The map has its own richer preference adapter, including map position.
  if (window.ListingScreen && window.StudyUI) return;
  const prefix='stvr_page_v1_'+encodeURIComponent(location.pathname);
  const controls=()=>[...document.querySelectorAll('input,select,textarea')].filter(e=>e.type!=='file'&&e.type!=='password'&&e.type!=='hidden');
  const key=e=>e.id?'id:'+e.id:e.dataset.feature?'feature:'+e.dataset.feature:e.name?'name:'+e.name+':'+e.value:null;
  let restoring=false,choice=null;
  function readCookie(name){try{return document.cookie.split(';').map(s=>s.trim()).find(s=>s.startsWith(name+'='))?.slice(name.length+1)??null;}catch{return null;}}
  function cookie(name,value,age=31536000){try{document.cookie=name+'='+value+'; Max-Age='+age+'; Path=/; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'');}catch{}}
  function write(state){
    const json=JSON.stringify(state),encoded=encodeURIComponent(json),old=Number(readCookie(prefix+'_count'))||0;
    const count=Math.ceil(encoded.length/3200);
    for(let i=0;i<count;i++)cookie(prefix+'_'+i,encoded.slice(i*3200,(i+1)*3200));
    cookie(prefix+'_count',String(count));for(let i=count;i<old;i++)cookie(prefix+'_'+i,'',0);
    try{localStorage.setItem(prefix,json);}catch{}
  }
  function read(){
    try{const count=Number(readCookie(prefix+'_count'));if(count>0&&count<30){let text='';for(let i=0;i<count;i++){const part=readCookie(prefix+'_'+i);if(part===null)throw Error('Incomplete cookie');text+=part;}return JSON.parse(decodeURIComponent(text));}}catch{}
    try{return JSON.parse(localStorage.getItem(prefix)||'null');}catch{return null;}
  }
  function save(){if(restoring)return;const values={};for(const e of controls()){const k=key(e);if(k)values[k]=e.type==='checkbox'||e.type==='radio'?e.checked:e.multiple?[...e.selectedOptions].map(o=>o.value):e.value;}write({version:1,values,choice});}
  function restore(){
    const saved=read();if(!saved||saved.version!==1||!saved.values)return;
    restoring=true;
    try{
      choice=saved.choice||null;
      // Factor selection can rebuild size options and reset other controls, so restore it first.
      if(choice?.attribute==='data-factor')findChoice()?.click();
      const changed=[];
      for(const e of controls()){
        const k=key(e);if(!k||!Object.hasOwn(saved.values,k))continue;const value=saved.values[k];
        if(e.type==='checkbox'||e.type==='radio'){if(typeof value!=='boolean')continue;e.checked=value;}
        else if(e.tagName==='SELECT'){
          if(e.multiple&&Array.isArray(value)){for(const option of e.options)option.selected=value.includes(option.value);}
          else {if(![...e.options].some(o=>o.value===value))continue;e.value=value;}
        }else if(typeof value==='string'){e.value=value;if(e.type==='number'&&!e.validity.valid){e.value=e.defaultValue;continue;}}
        else continue;
        changed.push(e);
      }
      // All values are in place before existing page handlers recompute results.
      for(const e of changed){e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}
      if(choice&&choice.attribute!=='data-factor')findChoice()?.click();
    }finally{restoring=false;}
  }
  function findChoice(){if(!choice)return null;if(choice.attribute==='data-rank')return [...document.querySelectorAll('[data-rank]')].find(e=>e.textContent===choice.value);return [...document.querySelectorAll('['+choice.attribute+']')].find(e=>e.getAttribute(choice.attribute)===choice.value);}
  document.addEventListener('input',save);document.addEventListener('change',save);
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button)return;
    for(const attribute of ['data-factor','data-inspect'])if(button.hasAttribute(attribute))choice={attribute,value:button.getAttribute(attribute)};
    if(button.hasAttribute('data-rank'))choice={attribute:'data-rank',value:button.textContent};
    if(button.id==='clear-feature')choice=null;
    // Button handlers may change multiple checkboxes or reset filters.
    queueMicrotask(save);
  });
  window.addEventListener('pagehide',save);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',restore,{once:true});else restore();
})();
