'use strict';
(async () => {
  const card = document.createElement('section');
  card.className = 'card runtime';
  card.setAttribute('aria-label', 'Kontrolli i analizës lokale');
  card.innerHTML = `<h2>Analiza në këtë pajisje</h2>
    <p id="runtime-state" role="status" aria-live="polite">Duke lidhur panelin…</p>
    <p id="runtime-details" class="hint"></p>
    <div class="tools"><button type="button" id="save-device" disabled>Ruaj në pajisje</button><button type="button" id="start-worker" disabled>Ruaj dhe nis analizën</button><button type="button" id="stop-worker" class="secondary" disabled>Ndalo analizën</button></div>
    <p id="runtime-message" role="status" aria-live="polite"></p>
    <p class="hint">Vetëm një kamerë për këtë panel. Gjatë analizës, ndryshimet mbeten në formular; ndalo procesin para ruajtjes. Pamja e ngarkuar nuk dërgohet në pajisje.</p>`;
  document.querySelector('.intro').after(card);
  const get=(id)=>document.getElementById(id);
  let token=null, busy=false, current=null;
  function message(text,error=false){get('runtime-message').textContent=text;get('runtime-message').classList.toggle('error',error);}
  function controls(){
    get('save-device').disabled=busy||!token||!current||current.running;
    get('start-worker').disabled=busy||!token||!current||current.running||!current.source_configured;
    get('stop-worker').disabled=busy||!token||!current||!current.running;
  }
  async function request(path,value){
    const options=value===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Panel-Token':token},body:JSON.stringify(value)};
    const response=await fetch(path,{...options,signal:AbortSignal.timeout(25000)});
    const body=await response.json();
    if(!response.ok)throw Error(body.error||'Kërkesa dështoi.');
    return body;
  }
  function display(value){
    current=value;
    const labels={starting:'Procesi po niset; ende pa frame të konfirmuar.',processing:'Videoja po përpunohet.',reconnecting:'Burimi i videos nuk është i disponueshëm; po rilidhet.',unresponsive:'Procesi është aktiv, por statusi është i vjetruar.',stopped:'Analiza është e ndalur.'};
    get('runtime-state').textContent=labels[value.state]||'Gjendje e panjohur.';
    const last=value.last_frame_at?new Date(value.last_frame_at*1000).toLocaleTimeString():'ende asnjë';
    get('runtime-details').textContent=`Burimi: ${value.source_type==='video'?'video prove':'kamera RTSP'} · Frame të përpunuara: ${value.processed_frames} · Frame i fundit: ${last} · Evente në pritje: ${value.pending_events??'—'}${value.last_exit!==null&&!value.running?` · Kodi i daljes: ${value.last_exit}`:''}`;
    if(!value.source_configured)message('Konfiguro EDGE_RTSP_URL në ambientin e Mini PC dhe rinis panelin, ose nise panelin me --video për provë.',true);
    controls();
  }
  async function action(work){
    if(busy)return;busy=true;controls();
    try{await work();}catch(error){message(error.message,true);}
    finally{busy=false;try{display(await request('/api/status'));}catch{current=null;get('runtime-state').textContent='Nuk ka lidhje me panelin lokal.';}controls();}
  }
  async function save(){
    const config=window.CameraCalibration.collectConfig();
    const result=await request('/api/config',config);
    message('Konfigurimi u ruajt në pajisje. Databaza lokale është events.sqlite3 pranë konfigurimit.');
    return result;
  }
  get('save-device').addEventListener('click',()=>action(save));
  get('start-worker').addEventListener('click',()=>action(async()=>{
    await save();display(await request('/api/start',{}));message('Procesi u nis. Prit konfirmimin e frame-ve; nisja nuk garanton saktësinë e numërimit.');
  }));
  get('stop-worker').addEventListener('click',()=>action(async()=>{display(await request('/api/stop',{}));message('Analiza u ndal. Eventet e ruajtura mbeten në databazë.');}));
  try{
    const bootstrap=await request('/api/bootstrap');token=bootstrap.token;
    if(bootstrap.config)window.CameraCalibration.loadConfig(bootstrap.config);
    if(bootstrap.warning)message(bootstrap.warning,true);
    display(await request('/api/status'));
  }catch(error){message(`Lidhja dështoi: ${error.message}`,true);controls();return;}
  async function poll(){
    if(!busy){try{display(await request('/api/status'));}catch{current=null;controls();get('runtime-state').textContent='Nuk ka lidhje me panelin lokal.';}}
    setTimeout(poll,2000);
  }
  setTimeout(poll,2000);
})();
