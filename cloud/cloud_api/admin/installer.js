'use strict';
(async()=>{
  const query=new URLSearchParams(location.search);let version=0,busy=false;
  const card=document.createElement('section');card.className='card installer-control';
  card.innerHTML='<h2>Instalimi i caktuar</h2><p id="assigned-scope"></p><div class="actions"><button id="save-draft" type="button">Ruaj draft</button><button id="save-review" type="button" class="secondary">Ruaj kontrollin manual</button><button id="download-active" type="button" class="secondary">Shkarko JSON aktiv</button><a href="/technician">Kthehu te instalimet</a></div><p id="server-status" role="status" aria-live="polite">Duke verifikuar autorizimin…</p><p class="hint">Vetëm Admin aktivizon versionin. Shkarkimi nuk e instalon automatikisht në Mini PC; instalimi konfirmohet veçmas nga pajisja.</p>';
  document.querySelector('.intro').after(card);
  const $=(id)=>document.getElementById(id);
  function message(text,error=false){$('server-status').textContent=text;$('server-status').classList.toggle('error',error);}
  const keys=['organization_id','location_id','node_id','camera_id'];const fixed={};for(const key of keys)fixed[key]=query.get(key)||'';
  const params=new URLSearchParams(fixed);
  async function api(path,value){const response=await fetch(path,value===undefined?{credentials:'same-origin'}:{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});if(response.status===401){location.replace('/');throw Error('Hyr përsëri.');}if(!response.ok){const body=await response.json();throw Error(typeof body.detail==='string'?body.detail:'Kërkesa dështoi.');}return response;}
  function disable(value){for(const id of ['save-draft','save-review','download-active'])$(id).disabled=value;}
  disable(true);$('export').hidden=true;
  $('settings').addEventListener('submit',(event)=>{event.preventDefault();event.stopImmediatePropagation();message('Përdor ruajtjen në platformë dhe shkarko versionin aktiv.',true);},true);
  try{const context=await(await api('/v1/installations/context?'+params)).json();version=context.latest_version;window.CameraCalibration.loadConfig(context.config);for(const key of keys){$(key).value=fixed[key];$(key).readOnly=true;}$('assigned-scope').textContent=keys.map((k)=>fixed[k]).join(' / ');message(`Identiteti u verifikua nga serveri. Versioni i fundit: ${version||'asnjë'}.`);disable(false);}
  catch(e){message(e.message,true);return;}
  async function save(status){if(busy)return;busy=true;disable(true);try{const config=window.CameraCalibration.collectConfig();for(const key of keys)if(config[key]!==fixed[key])throw Error('Identiteti i kamerës nuk mund të ndryshohet.');const result=await(await api('/v1/installations/calibrations?'+params,{config,expected_version:version,status})).json();version=result.version;message(`U ruajt v${version}: ${status==='draft'?'draft':'kontroll manual'}. Ende jo aktivizim ose instalim.`);}catch(e){message(e.message,true);}finally{busy=false;disable(false);}}
  $('save-draft').addEventListener('click',()=>save('draft'));
  $('save-review').addEventListener('click',()=>save('manual_review'));
  $('download-active').addEventListener('click',async()=>{try{const response=await api('/v1/installations/config?'+params);const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='config.local.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);message('JSON-i aktiv u shkarkua. Instaloje në pajisjen e përcaktuar; shkarkimi nuk konfirmon instalimin.');}catch(e){message(e.message,true);}});
})();
