'use strict';
const $=(id)=>document.getElementById(id);
let inventory={locations:[],cameras:[]}, query=null, loading=false, revision=0, zoneRows=[], takeawayChoice='';
const format=new Intl.NumberFormat('sq-AL');
const dateFormat=new Intl.DateTimeFormat('sq-AL',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
function message(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
function loginView(){takeawayChoice='';revision++;loading=false;$('refresh').disabled=false;document.querySelectorAll('#filters input,#filters select').forEach((e)=>{e.disabled=false;});query=null;$('dashboard').hidden=true;$('login-view').hidden=false;$('password').value='';$('download').disabled=true;}
async function api(url,options={}){
  const response=await fetch(url,{...options,credentials:'same-origin',signal:AbortSignal.timeout(20000)});
  if(response.status===401){loginView();throw Error('Hyr përsëri në llogari.');}
  if(!response.ok)throw Error(response.status===429?'Shumë tentativa. Provo përsëri pas pesë minutash.':'Kërkesa dështoi. Kontrollo lidhjen dhe periudhën e zgjedhur.');
  return response;
}
function localDate(date){return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;}
function dates(){const end=new Date(),start=new Date();start.setDate(start.getDate()-6);$('start').value=localDate(start);$('end').value=localDate(end);}
function cameras(){
  $('camera').replaceChildren(new Option('Të gjitha kamerat',''));
  inventory.cameras.filter((c)=>!$('location').value||c.location_id===$('location').value).forEach((c)=>{
    $('camera').add(new Option(`${c.location_id} / ${c.id} (${c.node_id})`,JSON.stringify([c.location_id,c.node_id,c.id])));
  });
}
function selectedQuery(){
  if(!$('filters').reportValidity())throw Error('Zgjidh datat.');
  const start=new Date($('start').value+'T00:00:00'),end=new Date($('end').value+'T00:00:00');end.setDate(end.getDate()+1);
  if(!Number.isFinite(+start)||!Number.isFinite(+end)||end<=start||end-start>31*86400000)throw Error('Zgjidh një periudhë deri në 30 ditë dhe me data në rendin e duhur.');
  const params=new URLSearchParams({start:String(+start/1000),end:String(+end/1000)});
  if($('location').value)params.set('location_id',$('location').value);
  if($('camera').value){const [location,node,camera]=JSON.parse($('camera').value);params.set('location_id',location);params.set('node_id',node);params.set('camera_id',camera);}
  return params;
}
function element(tag,text){const e=document.createElement(tag);e.textContent=text;return e;}
function clear(){clearRestaurant();$('peak-note').textContent=$('camera').value?'Maksimumi i snapshot-eve të kamerës':'Zgjidh një kamerë për këtë matje';['entries','exits','dwell','peak'].forEach((id)=>{$(id).textContent='—';});$('rows').replaceChildren();$('chart').replaceChildren();$('chart').setAttribute('hidden','');$('chart-empty').hidden=false;$('row-count').textContent='';}
function svg(tag,attrs,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;$('chart').append(e);return e;}
function chart(rows){
  $('chart').replaceChildren();
  if(!rows.length)return;
  const hours=new Map();rows.forEach((r)=>{const value=hours.get(r.hour_utc)||{entries:0,exits:0};value.entries+=r.entries;value.exits+=r.exits;hours.set(r.hour_utc,value);});
  // Bound the chart to 60 chronological buckets; raw hourly rows remain in the table/CSV.
  const values=[...hours].sort((a,b)=>a[0].localeCompare(b[0]));
  const group=Math.ceil(values.length/60),buckets=[];
  for(let i=0;i<values.length;i+=group){const chunk=values.slice(i,i+group);buckets.push({time:chunk[0][0],end:chunk.at(-1)[0],entries:chunk.reduce((s,[,v])=>s+v.entries,0),exits:chunk.reduce((s,[,v])=>s+v.exits,0)});}
  const maximum=Math.max(4,Math.ceil(Math.max(...buckets.flatMap((b)=>[b.entries,b.exits]))/4)*4);
  for(let i=0;i<=4;i++){const y=230-i*190/4;svg('line',{x1:80,y1:y,x2:945,y2:y,stroke:'var(--chart-grid)'});svg('text',{x:68,y:y+4,class:'chart-y-label',fill:'var(--chart-text)','font-size':11,'text-anchor':'end'},format.format(maximum*i/4));}
  const width=860/buckets.length,labelEvery=Math.max(1,Math.ceil(buckets.length/5)),lastLabel=Math.floor((buckets.length-1)/labelEvery)*labelEvery;
  buckets.forEach((b,i)=>{
    ['entries','exits'].forEach((key,j)=>{
      const height=b[key]/maximum*190;
      const barWidth=Math.max(1,Math.min(18,width*.32)),center=80+(i+.5)*width;
      const bar=svg('rect',{x:j?center+2:center-barWidth-2,y:230-height,width:barWidth,height,rx:3,fill:j?'var(--chart-exit)':'var(--chart-entry)'});
      bar.append(Object.assign(document.createElementNS('http://www.w3.org/2000/svg','title'),{textContent:`${dateFormat.format(new Date(b.time))}–${dateFormat.format(new Date(b.end))}: ${b.entries} hyrje / ${b.exits} dalje`}));
    });
    if(i%labelEvery===0){
      const x=80+(i+.5)*width;
      svg('text',{x,y:255,class:'axis-label-desktop',fill:'var(--chart-text)','font-size':11,'text-anchor':'middle'},dateFormat.format(new Date(b.time)));
      if(i===0||i===lastLabel||i%(labelEvery*2)===0)svg('text',{x,y:263,class:'axis-label-mobile',fill:'var(--chart-text)','text-anchor':i===0&&lastLabel>0?'start':i===lastLabel&&lastLabel>0?'end':'middle'},new Intl.DateTimeFormat('sq-AL',{day:'2-digit',month:'2-digit'}).format(new Date(b.time)));
    }
  });
  $('chart').removeAttribute('hidden');$('chart-empty').hidden=true;
  $('chart').setAttribute('aria-label',`Grafiku me ${buckets.length} intervale; ${group>1?'disa orë janë bashkuar për lexueshmëri':'intervale orare'}. Detajet janë në tabelë.`);
}
function render(rows){
  clear();if(!rows.length)return;
  $('entries').textContent=format.format(rows.reduce((s,r)=>s+r.entries,0));
  $('exits').textContent=format.format(rows.reduce((s,r)=>s+r.exits,0));
  const sessions=rows.reduce((s,r)=>s+r.completed_zone_dwell_sessions,0),seconds=rows.reduce((s,r)=>s+r.completed_zone_dwell_seconds,0);
  $('dwell').textContent=sessions?`${(seconds/sessions/60).toLocaleString('sq-AL',{maximumFractionDigits:1})} min`:'—';
  const peaks=rows.map((r)=>r.peak_visible_persons).filter((v)=>v!==null);
  $('peak').textContent=$('camera').value&&peaks.length?format.format(Math.max(...peaks)):'—';
  $('peak-note').textContent=$('camera').value?'Maksimumi i snapshot-eve të kamerës':'Zgjidh një kamerë për këtë matje';
  const fragment=document.createDocumentFragment();
  rows.slice(0,200).forEach((r)=>{const tr=document.createElement('tr');[dateFormat.format(new Date(r.hour_utc)),`${r.location_id} / ${r.camera_id} (${r.node_id})`,r.entries,r.exits,r.completed_zone_dwell_sessions].forEach((v)=>tr.append(element('td',String(v))));fragment.append(tr);});
  $('rows').append(fragment);$('row-count').textContent=`${format.format(rows.length)} rreshta orarë${rows.length>200?' · Shfaqen 200 të parët; CSV përmban të gjithë.':''}`;chart(rows);
}
function clearRestaurant(){
  zoneRows=[];$('zone-rows').replaceChildren();$('zones-status').textContent='Nuk ka të dhëna zone të ngarkuara.';
  $('takeaway-zone').replaceChildren(new Option('Zgjidh zonën e takeaway',''));$('takeaway-dwell').textContent='—';$('download-zones').disabled=true;
  $('takeaway-note').textContent='Zgjidh zonën nga të dhënat e kamerës. Kjo zgjedhje vlen për pamjen aktuale; nuk ndryshon kalibrimin.';
}
function zoneKey(row){return JSON.stringify([row.location_id,row.node_id,row.camera_id,row.zone_id]);}
function duration(seconds){return `${(seconds/60).toLocaleString('sq-AL',{maximumFractionDigits:1})} min`;}
function takeaway(){
  const row=zoneRows.find((r)=>zoneKey(r)===$('takeaway-zone').value);
  takeawayChoice=$('takeaway-zone').value;
  $('takeaway-dwell').textContent=row&&row.completed_sessions?duration(row.observed_dwell_seconds/row.completed_sessions):'—';
  $('takeaway-note').textContent=row?`${row.location_id} / ${row.camera_id} / ${row.zone_id} · ${format.format(row.completed_sessions)} sesione të plota dhe ${format.format(row.interrupted_sessions)} të ndërprera. Pa dallim klient/staf.`:'Zgjidh zonën nga të dhënat e kamerës. Kjo zgjedhje vlen për pamjen aktuale; nuk ndryshon kalibrimin.';
}
function renderZones(rows){
  zoneRows=rows;$('zone-rows').replaceChildren();
  $('takeaway-zone').replaceChildren(new Option('Zgjidh zonën e takeaway',''));
  const fragment=document.createDocumentFragment();
  rows.forEach((r,index)=>{
    $('takeaway-zone').add(new Option(`${r.zone_id} · ${r.location_id} / ${r.camera_id} (${r.node_id})`,zoneKey(r)));
    if(index>=200)return;
    const tr=document.createElement('tr');
    [r.zone_id,`${r.location_id} / ${r.camera_id} (${r.node_id})`,r.completed_sessions?duration(r.observed_dwell_seconds/r.completed_sessions):'—',format.format(r.completed_sessions),format.format(r.interrupted_sessions)].forEach((value)=>tr.append(element('td',value)));
    fragment.append(tr);
  });
  $('zone-rows').append(fragment);
  $('zones-status').textContent=rows.length?`${format.format(rows.length)} zona me evente${rows.length>200?' · Shfaqen 200 të parat; CSV i përfshin të gjitha.':''}. Pritja e shërbimit dhe përqindja e përdorimit ende nuk maten.`:'Nuk ka evente zonash për këta filtra. Kjo nuk provon se tavolinat nuk janë përdorur.';
  $('takeaway-zone').value=rows.some((r)=>zoneKey(r)===takeawayChoice)?takeawayChoice:'';
  $('download-zones').disabled=!rows.length;takeaway();
}
$('takeaway-zone').addEventListener('change',takeaway);
$('download-zones').addEventListener('click',()=>{
  if(!zoneRows.length)return;
  const columns=['location_id','node_id','camera_id','zone_id','completed_sessions','interrupted_sessions','observed_dwell_seconds','average_observed_dwell_seconds'];
  function cell(value){let text=String(value??'');if(typeof value==='string'&&/^[\s]*[=+@-]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}
  const lines=[columns.map(cell).join(','),...zoneRows.map((r)=>columns.map((key)=>cell(key==='average_observed_dwell_seconds'?(r.completed_sessions?r.observed_dwell_seconds/r.completed_sessions:null):r[key])).join(','))];
  const url=URL.createObjectURL(new Blob(['\uFEFF'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='raporti-zonave.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
async function load(){
  if(loading)return;const version=++revision;loading=true;document.querySelectorAll('#filters input,#filters select').forEach((e)=>{e.disabled=true;});$('refresh').disabled=true;$('download').disabled=true;query=null;clear();message('Duke ngarkuar të dhënat…');
  try{const params=selectedQuery();const responses=await Promise.all([api('/v1/metrics/hourly?'+params),api('/v1/metrics/zones?'+params)]);const [data,zones]=await Promise.all(responses.map((r)=>r.json()));if(version!==revision)return;render(data.rows);renderZones(zones.rows);query=params;$('download').disabled=false;message(data.rows.length?'Të dhënat u përditësuan.':'Nuk ka evente për periudhën dhe filtrat e zgjedhur.');}
  catch(e){if(version===revision){message(e.message,true);$('zones-status').textContent='Nuk u ngarkuan të dhënat e zonave. Provo përsëri.';}}
  finally{if(version===revision){loading=false;$('refresh').disabled=false;document.querySelectorAll('#filters input,#filters select').forEach((e)=>{e.disabled=false;});}}
}
async function enter(){
  const me=await(await api('/v1/me')).json();inventory=await(await api('/v1/inventory')).json();
  $('demo-banner').hidden=!me.demo;
  $('identity').textContent=`Biznesi: ${me.organization_id}${me.email?' · '+me.email:''}`;
  $('location').replaceChildren(new Option('Të gjitha lokacionet',''));inventory.locations.forEach((id)=>$('location').add(new Option(id,id)));cameras();dates();
  $('timezone').textContent=`Datat dhe orët shfaqen sipas ${Intl.DateTimeFormat().resolvedOptions().timeZone}. Agregimet bazë në server janë në UTC.`;
  $('login-view').hidden=true;$('dashboard').hidden=false;$('password').value='';await load();
}
$('login-form').addEventListener('submit',async(event)=>{
  event.preventDefault();$('login-button').disabled=true;$('login-status').textContent='Duke hyrë…';
  try{const response=await fetch('/auth/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('email').value,password:$('password').value}),signal:AbortSignal.timeout(20000)});
    if(!response.ok)throw Error(response.status===429?'Shumë tentativa. Provo pas pesë minutash.':'Hyrja dështoi. Kontrollo emailin dhe fjalëkalimin.');
    $('login-status').textContent='';await enter();
  }catch(e){$('login-status').textContent=e.message;}finally{$('login-button').disabled=false;}
});
$('logout').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'});loginView();clear();}catch(e){message(e.message,true);}});
$('filters').addEventListener('submit',(event)=>{event.preventDefault();load();});
$('location').addEventListener('change',()=>{cameras();query=null;$('download').disabled=true;clear();message('Filtri ndryshoi. Shtyp “Shfaq të dhënat”.');});
['start','end','camera'].forEach((id)=>$(id).addEventListener('change',()=>{query=null;$('download').disabled=true;clear();message('Filtri ndryshoi. Shtyp “Shfaq të dhënat”.');}));
$('download').addEventListener('click',async()=>{
  if(!query)return;$('download').disabled=true;
  try{const response=await api('/v1/reports/hourly.csv?'+query);const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='raporti-orar.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  catch(e){message(e.message,true);}finally{$('download').disabled=!query;}
});
enter().catch((error)=>{loginView();if(error.message!=='Hyr përsëri në llogari.')$('login-status').textContent='Nuk mund të ngarkohet paneli. Kontrollo lidhjen dhe provo përsëri.';});
