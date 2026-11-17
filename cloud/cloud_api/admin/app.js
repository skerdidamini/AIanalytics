'use strict';
const $=(id)=>document.getElementById(id);
let data=null,loading=false;
function message(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
async function api(path,value){
  const response=await fetch(path,value===undefined?{credentials:'same-origin'}:{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});
  if(response.status===401){location.replace('/');throw Error('Hyr në llogari.');}
  if(response.status===204)return {};
  const body=await response.json();if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'Veprimi dështoi. Kontrollo fushat.');return body;
}
function text(tag,value){const e=document.createElement(tag);e.textContent=value;return e;}
function date(value){return value?new Date(value*1000).toLocaleString():'Pa të dhëna';}
function scope(row){return {organization_id:row.organization_id,location_id:row.location_id,node_id:row.node_id,camera_id:row.id};}
function chip(value,type=''){const e=text('span',value);e.className='status-chip '+type;return e;}
function row(table,values){const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');if(value instanceof Node)td.append(value);else td.textContent=value;tr.append(td);}$(table).append(tr);}
function options(selector,items){document.querySelectorAll(selector).forEach((select)=>{const previous=select.value;select.replaceChildren(new Option('Zgjidh…',''));for(const [label,value] of items)select.add(new Option(label,value));if(items.some(([,value])=>value===previous))select.value=previous;});}
function tab(name){for(const section of ['businesses','installations','users','activity'])$('tab-'+section).hidden=section!==name;document.querySelectorAll('[data-tab]').forEach((b)=>b.setAttribute('aria-pressed',String(b.dataset.tab===name)));}
function render(){
  for(const id of ['business-rows','node-rows','camera-rows','assignment-rows','audit-rows'])$(id).replaceChildren();
  $('demo').hidden=!data.demo;$('identity').textContent=data.email;$('role-label').textContent=data.role==='admin'?'PANELI ADMIN':'PANELI I TEKNIKUT';
  $('title').textContent=data.role==='admin'?'Bizneset dhe pajisjet':'Instalimet e mia';
  document.querySelectorAll('.admin-only').forEach((e)=>{e.hidden=data.role!=='admin';});
  options('.business-select',data.businesses.map((b)=>[`${b.name} (${b.id})`,b.id]));
  options('.location-select',data.locations.map((l)=>[`${l.organization_id} / ${l.name}`,JSON.stringify([l.organization_id,l.id])]));
  options('.node-select',data.nodes.map((n)=>[`${n.organization_id} / ${n.location_id} / ${n.id}`,JSON.stringify([n.organization_id,n.location_id,n.id])]));
  options('#technician-select',data.technicians.filter((t)=>t.enabled).map((t)=>[t.email,t.email]));
  for(const b of data.businesses)row('business-rows',[b.name,b.id,b.owners.length?b.owners.join(', '):'Pa llogari pronari']);
  for(const n of data.nodes){
    const controls=document.createElement('div');
    if(data.role==='admin'){
      const button=text('button','Kredencial i ri');button.type='button';button.addEventListener('click',async()=>{
        button.disabled=true;
        try{const response=await fetch('/v1/admin/node-credential',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({organization_id:n.organization_id,location_id:n.location_id,node_id:n.id})});if(!response.ok)throw Error('Kredenciali nuk u krijua.');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='device.token';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);await load();message('Kredenciali u shkarkua vetëm në skedar. Dorëzoje sigurt për këtë pajisje; kredencialet e vjetra nuk u revokuan.');}catch(e){message(e.message,true);}finally{button.disabled=false;}
      });controls.append(button);
    }
    row('node-rows',[`${n.organization_id} / ${n.location_id}`,n.id,chip(n.online===null?'Pa heartbeat':n.online?'Online':'Pa kontakt të freskët',n.online===null?'':n.online?'good':'warning'),date(n.last_heartbeat_at),n.credential_configured?'Konfiguruar':'Ende pa kredencial',controls]);
  }
  const labels={unknown:'Pa të dhëna',processing:'Frame po përpunohen',starting:'Duke nisur',reconnecting:'Po rilidhet',stopped:'Ndalur',unresponsive:'Pa përgjigje',stale:'Raport i vjetruar',stale_frames:'Frame të vjetruara'};
  for(const c of data.cameras){
    const controls=document.createElement('div');controls.className='actions';const params=new URLSearchParams(scope(c));
    const open=text('a','Kalibro');open.href='/installer/?'+params;controls.append(open);
    if(data.role==='admin'&&c.latest_calibration?.status==='manual_review'){
      const activate=text('button',`Aktivizo v${c.latest_calibration.version}`);activate.type='button';activate.addEventListener('click',()=>mutate(()=>api('/v1/admin/activate?'+params,{version:c.latest_calibration.version}),'Versioni u aktivizua. Prit instalimin dhe konfirmimin nga pajisja.'));controls.append(activate);
    }
    if(c.active_version){const download=text('a','JSON aktiv');download.href='/v1/installations/config?'+params;download.download='config.local.json';controls.append(download);}
    const receipt=text('div',date(c.last_event_received_at));receipt.append(text('small','Koha e eventit: '+date(c.last_event_at)));
    row('camera-rows',[`${c.organization_id} / ${c.location_id}`,`${c.id} / ${c.node_id}`,chip(labels[c.camera_status]||'Pa të dhëna',c.camera_status==='processing'?'good':c.camera_status==='unknown'?'':'warning'),date(c.last_frame_at),c.latest_calibration?`v${c.latest_calibration.version} · ${c.latest_calibration.status==='manual_review'?'kontroll manual':'draft'}`:'Pa filluar',c.active_version?`Aktiv v${c.active_version} · ${c.applied_version?'Konfirmuar v'+c.applied_version:'Pa konfirmim nga pajisja'}`:'Asnjë aktiv',String(c.event_count),receipt,controls]);
  }
  if(!data.cameras.length)row('camera-rows',[data.role==='admin'?'Ende nuk ka kamera. Regjistro biznesin, lokacionin, pajisjen dhe kamerën.':'Nuk ke kamera të caktuara. Administratori duhet të caktojë lokacionin.']);
  for(const assignment of data.assignments){const controls=document.createElement('div');if(data.role==='admin'){const button=text('button','Hiq caktimin');button.type='button';button.addEventListener('click',()=>mutate(()=>api('/v1/admin/unassign',assignment),'Caktimi u hoq.'));controls.append(button);}row('assignment-rows',[assignment.email,assignment.organization_id,assignment.location_id,controls]);}
  for(const item of data.audit)row('audit-rows',[date(item.created_at),item.actor,item.action,item.details]);
}
async function load(){if(loading)return;loading=true;$('refresh').disabled=true;try{data=await api('/v1/operations');render();message('Gjendja u përditësua. Statuset bazohen në raportimet e marra, jo në supozime.');}catch(e){message(e.message,true);}finally{loading=false;$('refresh').disabled=false;}}
async function mutate(work,success){try{await work();await load();message(success);}catch(e){message(e.message,true);}}
function form(id,endpoint,transform=(value)=>value){$(id).addEventListener('submit',async(event)=>{event.preventDefault();const button=$(id).querySelector('button');if(button.disabled)return;button.disabled=true;try{const values=Object.fromEntries(new FormData($(id)));for(const key of Object.keys(values))if(key!=='password')values[key]=values[key].trim();await api(endpoint,transform(values));$(id).reset();if(id==='account-form')$('account-form').elements.organization_id.disabled=false;await load();message('U ruajt me sukses.');}catch(e){message(e.message,true);}finally{button.disabled=false;const password=$(id).querySelector('[name=password]');if(password)password.value='';}});}
form('business-form','/v1/admin/businesses');form('location-form','/v1/admin/locations');
form('node-form','/v1/admin/nodes',(v)=>{const [organization_id,location_id]=JSON.parse(v.scope);return {organization_id,location_id,id:v.id};});
form('camera-form','/v1/admin/cameras',(v)=>{const [organization_id,location_id,node_id]=JSON.parse(v.scope);return {organization_id,location_id,node_id,id:v.id};});
form('assignment-form','/v1/admin/assignments',(v)=>{const [organization_id,location_id]=JSON.parse(v.scope);return {email:v.email,organization_id,location_id};});
form('account-form','/v1/admin/accounts',(v)=>({email:v.email,password:v.password,role:v.role,organization_id:v.role==='owner'?v.organization_id:null}));
$('account-form').elements.role.addEventListener('change',()=>{$('account-form').elements.organization_id.disabled=$('account-form').elements.role.value==='technician';});
$('refresh').addEventListener('click',load);
$('logout').addEventListener('click',async()=>{try{await api('/auth/logout',{});location.replace('/');}catch(e){message(e.message,true);}});
document.querySelectorAll('[data-tab]').forEach((button)=>button.addEventListener('click',()=>tab(button.dataset.tab)));
(async()=>{try{const me=await api('/v1/me');if(!['admin','technician'].includes(me.role)){location.replace('/');return;}await load();tab('installations');}catch(e){message(e.message,true);}})();

setInterval(()=>{if(document.visibilityState==='visible')load();},30000);
