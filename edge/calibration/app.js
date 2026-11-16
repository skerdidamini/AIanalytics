'use strict';
const $ = (id) => document.getElementById(id);
const defaults = {
  organization_id: 'pilot-organization', location_id: 'pilot-location', node_id: 'edge-001', camera_id: 'entrance-001',
  database: 'events.sqlite3', sample_fps: 5, max_width: 960, track_distance: 0.15, track_timeout: 2,
  line: { start: [0.1, 0.5], end: [0.9, 0.5], enter_side: 1, margin: 0.02 }, zones: [],
  occupancy_interval: 30, queue_max_events: 100000, cloud_url_env: 'EDGE_CLOUD_URL', cloud_token_env: 'EDGE_CLOUD_TOKEN',
};
let config = structuredClone(defaults);
let lineReady = false;
let mode = 'line';
let pending = null;
const ids = ['organization_id', 'location_id', 'node_id', 'camera_id'];
const coordinateIds = ['start-x', 'start-y', 'end-x', 'end-y'];
function status(message, error = false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function number(value) { return typeof value === 'number' && Number.isFinite(value); }
function point(value) { return Array.isArray(value) && value.length === 2 && value.every((v) => number(v) && v >= 0 && v <= 1); }
function validate(c) {
  if (!c || typeof c !== 'object' || Array.isArray(c)) throw Error('Konfigurimi duhet të jetë objekt JSON.');
  for (const key of [...ids, 'database']) if (typeof c[key] !== 'string' || !c[key].trim()) throw Error(`Mungon fusha ${key}.`);
  for (const key of ['sample_fps', 'max_width', 'track_distance', 'track_timeout', 'occupancy_interval', 'queue_max_events']) {
    if (!number(c[key]) || c[key] <= 0) throw Error(`Parametër i pavlefshëm: ${key}.`);
  }
  if (!Number.isInteger(c.queue_max_events) || c.max_width < 64) throw Error('Kufiri i radhës ose gjerësia e videos është e pavlefshme.');
  const l = c.line;
  if (!l || !point(l.start) || !point(l.end) || (l.start[0] === l.end[0] && l.start[1] === l.end[1]) ||
      ![1, -1].includes(l.enter_side) || !number(l.margin) || l.margin <= 0 || l.margin >= 1) throw Error('Vija duhet të ketë dy pika të ndryshme dhe tolerancë midis 0 dhe 1.');
  if(l.enabled!==undefined&&typeof l.enabled!=='boolean')throw Error('Statusi i vijës duhet të jetë boolean.');
  if (!Array.isArray(c.zones)) throw Error('Lista e zonave është e pavlefshme.');
  const names = new Set();
  for (const z of c.zones) {
    if (!z || typeof z.id !== 'string' || !z.id.trim() || names.has(z.id.trim()) || !Array.isArray(z.rect) || z.rect.length !== 4 ||
        !z.rect.every((v) => number(v) && v >= 0 && v <= 1) || z.rect[0] >= z.rect[2] || z.rect[1] >= z.rect[3]) throw Error('Zonat duan emra unikë dhe koordinata të vlefshme: X1 < X2, Y1 < Y2.');
    if(z.kind!==undefined&&!['table','service','takeaway','entrance','exit','other'].includes(z.kind))throw Error('Lloj zone i pavlefshëm.');
    names.add(z.id.trim());
  }
  for(const z of c.zones)if(z.kind==='service'&&!c.zones.some((t)=>t.kind==='table'&&t.id===z.table_id))throw Error('Çdo zonë shërbimi duhet lidhur me një tavolinë ekzistuese.');
  window.CalibrationExtras?.validateConfig(c);
}
function svg(tag, attributes, text) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attributes)) el.setAttribute(key, value);
  if (text !== undefined) el.textContent = text;
  $('geometry').append(el);
  return el;
}
function draw() {
  $('geometry').replaceChildren();
  config.zones.forEach((z, index) => {
    const [x1, y1, x2, y2] = z.rect;
    if (![x1,y1,x2,y2].every(number)) return;
    const zoneColor=window.CalibrationExtras?.zoneColor(z.kind)||'#72bcff';
    svg('rect', {x:x1*1000,y:y1*1000,width:Math.max(0,x2-x1)*1000,height:Math.max(0,y2-y1)*1000,fill:zoneColor+'22',stroke:zoneColor,'stroke-width':2,'vector-effect':'non-scaling-stroke'});
    svg('text', {x:x1*1000+8,y:y1*1000+32,fill:'#fff','font-size':24,'paint-order':'stroke',stroke:'#08111d','stroke-width':4}, `${index+1}. ${z.id}`);
  });
  if (lineReady && config.line.enabled!==false) {
    const [a,b] = [config.line.start,config.line.end];
    svg('line',{x1:a[0]*1000,y1:a[1]*1000,x2:b[0]*1000,y2:b[1]*1000,stroke:'#38edbd','stroke-width':3,'vector-effect':'non-scaling-stroke'});
    for (const p of [a,b]) svg('circle',{cx:p[0]*1000,cy:p[1]*1000,r:7,fill:'#38edbd'});
    const dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy),side=config.line.enter_side;
    const x=(a[0]+b[0])*500,y=(a[1]+b[1])*500;
    svg('line',{x1:x,y1:y,x2:x-dy/length*90*side,y2:y+dx/length*90*side,stroke:'#38edbd','stroke-width':3,'marker-end':'url(#arrow)'});
  }
  window.CalibrationExtras?.drawDetails();
  if (pending) svg('circle',{cx:pending[0]*1000,cy:pending[1]*1000,r:9,fill:'#ffce73'});
}
function setMode(value) {
  mode = value; pending = null;
  $('line-tool').setAttribute('aria-pressed', String(mode === 'line'));
  $('zone-tool').setAttribute('aria-pressed', String(mode === 'zone'));
  $('role-tool').setAttribute('aria-pressed',String(mode==='role'));$('trace-tool').setAttribute('aria-pressed',String(mode==='trace'));
  window.CalibrationExtras?.pause();
  $('instruction').textContent = ({line:'Kliko pikën e parë dhe pastaj të dytën të vijës.',zone:'Kliko dy cepat e kundërt të zonës drejtkëndore.',role:'Vizato dy cepat e pjesës së bluzës për rolin e zgjedhur.',trace:'Kliko pikën e nisjes dhe pikën e mbërritjes së personit.'})[mode];
  draw();
}
function syncLineInputs() {
  const values = [...config.line.start,...config.line.end];
  coordinateIds.forEach((id,i) => { $(id).value = values[i]; });
  $('enter-side').value = config.line.enter_side;
  $('margin').value = config.line.margin;
  $('line-enabled').checked=config.line.enabled!==false;
}
function newZone(rect) {
  let index=1;
  while (config.zones.some((z) => z.id === `Zone${index}`)) index++;
  config.zones.push({id:`Zone${index}`,kind:'table',rect});
  renderZones(); draw();
}
function renderZones() {
  $('zones').replaceChildren(); $('zone-count').textContent = config.zones.length;
  config.zones.forEach((zone, index) => {
    const box=document.createElement('div');box.className='zone';
    const label=document.createElement('label');label.textContent=`Emri i zonës ${index+1}`;
    const input=document.createElement('input');input.value=zone.id;input.required=true;
    input.addEventListener('input',()=>{zone.id=input.value;draw();});label.append(input);box.append(label);
    const kindLabel=document.createElement('label');kindLabel.textContent='Funksioni i zonës';
    const kind=document.createElement('select');
    for(const [key,text] of Object.entries({table:'Tavolinë',service:'Afrimi i shërbimit',takeaway:'Takeaway',entrance:'Hyrje',exit:'Dalje',other:'Zonë tjetër'}))kind.add(new Option(text,key));
    kind.value=zone.kind||'other';kind.addEventListener('change',()=>{zone.kind=kind.value;if(kind.value!=='service')delete zone.table_id;renderZones();draw();});kindLabel.append(kind);box.append(kindLabel);
    if(zone.kind==='service'){
      const l=document.createElement('label');l.textContent='Tavolina e lidhur';const select=document.createElement('select');select.add(new Option('Zgjidh tavolinën',''));
      config.zones.filter((z)=>z.kind==='table').forEach((z)=>select.add(new Option(z.id,z.id)));select.value=zone.table_id||'';select.required=true;
      select.addEventListener('change',()=>{zone.table_id=select.value;draw();});l.append(select);box.append(l);
    }
    const coordinates=document.createElement('div');coordinates.className='coordinates';
    ['X1','Y1','X2','Y2'].forEach((name,i)=>{
      const l=document.createElement('label');l.textContent=`Zona ${index+1} · ${name}`;
      const field=document.createElement('input');Object.assign(field,{type:'number',min:'0',max:'1',step:'any',required:true,value:zone.rect[i]});
      field.addEventListener('input',()=>{zone.rect[i]=field.valueAsNumber;draw();});l.append(field);coordinates.append(l);
    });
    box.append(coordinates);
    const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent=`Hiq zonën ${index+1}`;
    remove.addEventListener('click',()=>{config.zones.splice(index,1);renderZones();draw();$('add-zone').focus();});box.append(remove);$('zones').append(box);
  });
}
$('line-tool').addEventListener('click',()=>setMode('line'));
$('zone-tool').addEventListener('click',()=>setMode('zone'));
$('cancel').addEventListener('click',()=>{pending=null;draw();status('Pika e papërfunduar u anulua.');});
window.addEventListener('keydown',(event)=>{if(event.key==='Escape'){pending=null;draw();}});
$('drawing').addEventListener('click',(event)=>{
  window.CalibrationExtras?.pause();
  const rect=$('drawing').getBoundingClientRect();
  const p=[(event.clientX-rect.left)/rect.width,(event.clientY-rect.top)/rect.height].map((v)=>Math.round(Math.min(1,Math.max(0,v))*10000)/10000);
  if (!pending) {pending=p;draw();status('Pika e parë u vendos. Zgjidh pikën e dytë.');return;}
  if (mode === 'line') {
    if (Math.hypot(p[0]-pending[0],p[1]-pending[1])<0.005) {status('Zgjidh një pikë të dytë më larg.',true);return;}
    config.line.start=pending;config.line.end=p;lineReady=true;syncLineInputs();status('Vija u vendos. Kontrollo shigjetën e hyrjes.');
  } else if(mode==='trace'){window.CalibrationExtras?.testCrossing(pending,p);
  } else {
    const coords=[Math.min(pending[0],p[0]),Math.min(pending[1],p[1]),Math.max(pending[0],p[0]),Math.max(pending[1],p[1])];
    if(coords[2]-coords[0]<0.005||coords[3]-coords[1]<0.005){status('Zona duhet të ketë gjerësi dhe lartësi.',true);return;}
    if(mode==='role'){try{window.CalibrationExtras.addSample(coords);}catch(e){status(e.message,true);pending=null;draw();return;}}
    else{newZone(coords);status('Zona u shtua. Mund ta riemërtosh ose rregullosh koordinatat.');}
  }
  pending=null;draw();
});
function applyLine() {
  const values=coordinateIds.map((id)=>$(id).valueAsNumber);
  const line={...config.line,start:values.slice(0,2),end:values.slice(2),margin:$('margin').valueAsNumber,enter_side:Number($('enter-side').value)};
  validate({...config,line,zones:[]});config.line=line;lineReady=true;pending=null;draw();
}
$('apply-line').addEventListener('click',()=>{try{applyLine();status('Koordinatat e vijës u vendosën.');}catch(e){status(e.message,true);}});
$('enter-side').addEventListener('change',()=>{config.line.enter_side=Number($('enter-side').value);draw();});
$('add-zone').addEventListener('click',()=>{newZone([0.1,0.1,0.9,0.9]);$('zones').lastElementChild.querySelector('input').focus();});
$('config-file').addEventListener('change',async(event)=>{
  const file=event.target.files[0];if(!file)return;
  try{
    if(file.size>1024*1024)throw Error('Konfigurimi duhet të jetë më i vogël se 1 MB.');
    const candidate=JSON.parse(await file.text());if(candidate.zones===undefined)candidate.zones=[];validate(candidate);
    loadConfig(candidate);status('Konfigurimi u importua. Verifiko që pamja i përket kësaj kamere.');
  }catch(e){status(`Importi dështoi: ${e.message}`,true);}
  finally{event.target.value='';}
});
function collectConfig() {
  if (!$('settings').reportValidity()) throw Error('Plotëso të gjitha fushat me vlera të vlefshme.');
  if (pending) throw Error('Përfundo vizatimin ose anulo pikën përpara ruajtjes.');
  applyLine();ids.forEach((id)=>{config[id]=$(id).value.trim();});
  config.zones.forEach((z)=>{z.id=z.id.trim();});window.CalibrationExtras?.attach(config);validate(config);
  return structuredClone(config);
}
function loadConfig(candidate) {
  const value=structuredClone(candidate);
  if(value.zones===undefined)value.zones=[];
  validate(value);config=value;ids.forEach((id)=>{$(id).value=config[id];});
  lineReady=true;pending=null;window.CalibrationExtras?.onConfigLoaded(config);syncLineInputs();renderZones();draw();
}
window.CameraCalibration = { collectConfig, loadConfig };
$('settings').addEventListener('submit',(event)=>{
  event.preventDefault();
  try{
    const value=collectConfig();
    const blob=new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'});
    const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='config.local.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    status('Konfigurimi u përgatit për shkarkim. Ruaje te edge dhe rinis procesin me këtë skedar.');
  }catch(e){status(e.message,true);}
});
syncLineInputs();renderZones();draw();
