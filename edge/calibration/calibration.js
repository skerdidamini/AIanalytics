'use strict';
(() => {
  const roleNames={waiter:'Kamarier',bartender:'Banakier',customer:'Klient',unknown:'I panjohur'};
  const zoneColors={table:'#72bcff',service:'#d8a0ff',takeaway:'#ffce73',entrance:'#38edbd',exit:'#ffb86b',other:'#72bcff'};
  let media=null, samples=[], activeUrl=null, loadVersion=0, reviewed=null, trace=null;
  const video=$('camera-video');
  function invalidate(){reviewed=null;$('review-result').textContent='Draft: kontrolloje sërish pas ndryshimeve.';}
  function rectValid(rect){return Array.isArray(rect)&&rect.length===4&&rect.every((v)=>number(v)&&v>=0&&v<=1)&&rect[0]<rect[2]&&rect[1]<rect[3];}
  function validateConfig(c){
    if(!c.calibration)return;
    const k=c.calibration;
    if(k.schema_version!==1||!Array.isArray(k.role_samples)||k.role_samples.length>30)throw Error('Metadata e kalibrimit është e pavlefshme.');
    if(k.source!==null&&(!k.source||!['image','video'].includes(k.source.kind)||!Number.isInteger(k.source.width)||!Number.isInteger(k.source.height)||k.source.width<=0||k.source.height<=0))throw Error('Përmasat e pamjes janë të pavlefshme.');
    if(k.source?.kind==='video'&&(!number(k.source.frame_seconds)||!number(k.source.duration_seconds)||k.source.frame_seconds<0||k.source.duration_seconds<=0||k.source.frame_seconds>k.source.duration_seconds+.1))throw Error('Koha e videos është e pavlefshme.');
    if(typeof k.fixed_view_confirmed!=='boolean')throw Error('Konfirmimi i pamjes fikse mungon.');
    for(const s of k.role_samples){
      if(!s||!Object.hasOwn(roleNames,s.role)||!rectValid(s.rect)||!Array.isArray(s.rgb)||s.rgb.length!==3||!s.rgb.every((v)=>number(v)&&v>=0&&v<=255)||!s.hsv||!number(s.hsv.h)||s.hsv.h<0||s.hsv.h>=360||![s.hsv.s,s.hsv.v].every((v)=>number(v)&&v>=0&&v<=1))throw Error('Mostër uniforme e pavlefshme.');
      if(s.frame_seconds!==null&&(!number(s.frame_seconds)||s.frame_seconds<0))throw Error('Koha e mostrës është e pavlefshme.');
    }
    if(k.capabilities?.uniform_classifier_active!==false||k.capabilities?.table_service_active!==false)throw Error('Ky version mbështet vetëm mostra manuale, jo klasifikim automatik.');
    if(!k.review||!['draft','manual_review'].includes(k.review.status))throw Error('Status kontrolli i pavlefshëm.');
  }
  function pause(){video.pause();$('video-play').textContent='Luaj';}
  function source(){return media?{...media,...(media.kind==='video'?{frame_seconds:Number(video.currentTime.toFixed(3))}:{})}:config.calibration?.source||null;}
  function metadata(){return {schema_version:1,source:source(),fixed_view_confirmed:$('fixed-view').checked,role_samples:structuredClone(samples),capabilities:{uniform_classifier_active:false,table_service_active:false}};}
  function fingerprint(c,k){const value={...c,calibration:k};delete value.calibration.review;return JSON.stringify(value);}
  function attach(c){c.line.enabled=$('line-enabled').checked;const k=metadata();k.review={status:reviewed===fingerprint(c,k)?'manual_review':'draft'};c.calibration=k;}
  function onConfigLoaded(c){
    samples=structuredClone(c.calibration?.role_samples||[]);$('fixed-view').checked=false;
    reviewed=null;trace=null;renderSamples();$('review-result').textContent='Konfigurimi u importua. Ngarko pamjen e kamerës dhe kontrollo përputhjen.';
  }
  function drawDetails(){
    if(lineReady&&config.line.enabled!==false){const [a,b]=[config.line.start,config.line.end],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy),side=config.line.enter_side,x=(a[0]+b[0])*500,y=(a[1]+b[1])*500;
      svg('line',{x1:x,y1:y,x2:x+dy/length*90*side,y2:y-dx/length*90*side,stroke:'#ffb86b','stroke-width':3,'marker-end':'url(#exit-arrow)'});}
    samples.forEach((sample,index)=>{const [x1,y1,x2,y2]=sample.rect;svg('rect',{x:x1*1000,y:y1*1000,width:(x2-x1)*1000,height:(y2-y1)*1000,fill:'none',stroke:'#ffce73','stroke-width':2,'stroke-dasharray':'7 5','vector-effect':'non-scaling-stroke'});svg('text',{x:x1*1000+4,y:y1*1000+26,fill:'#ffce73','font-size':22,'paint-order':'stroke',stroke:'#08111d','stroke-width':4},`${index+1}. ${roleNames[sample.role]}`);});
    if(trace)svg('line',{x1:trace[0][0]*1000,y1:trace[0][1]*1000,x2:trace[1][0]*1000,y2:trace[1][1]*1000,stroke:'#fff','stroke-width':2,'stroke-dasharray':'8 5'});
  }
  function hsv(r,g,b){r/=255;g/=255;b/=255;const max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;let h=0;if(d){if(max===r)h=((g-b)/d)%6;else if(max===g)h=(b-r)/d+2;else h=(r-g)/d+4;h=(h*60+360)%360;}return {h,s:max?d/max:0,v:max};}
  function color(rect){
    if(!media)throw Error('Ngarko një foto ose video përpara marrjes së mostrës.');
    if(!rectValid(rect))throw Error('Mostra duhet të ketë koordinata të vlefshme.');
    pause();const element=media.kind==='video'?video:$('camera-image');
    if(media.kind==='video'&&(video.readyState<2||video.seeking))throw Error('Prit që frame-i i videos të ngarkohet.');
    const canvas=document.createElement('canvas'),scale=Math.min(1,960/media.width,960/media.height);
    canvas.width=Math.round(media.width*scale);canvas.height=Math.round(media.height*scale);
    const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(element,0,0,canvas.width,canvas.height);
    const x=Math.floor(rect[0]*canvas.width),y=Math.floor(rect[1]*canvas.height),w=Math.min(canvas.width-x,Math.ceil((rect[2]-rect[0])*canvas.width)),h=Math.min(canvas.height-y,Math.ceil((rect[3]-rect[1])*canvas.height));
    if(w*h<16)throw Error('Mostra është shumë e vogël; zgjidh një pjesë më të madhe të bluzës.');
    const pixels=context.getImageData(x,y,w,h).data,bins=Array(36).fill(0),values=[];
    for(let i=0;i<pixels.length;i+=16){if(pixels[i+3]<128)continue;const value=hsv(pixels[i],pixels[i+1],pixels[i+2]);values.push({rgb:[pixels[i],pixels[i+1],pixels[i+2]],...value});if(value.s>.15&&value.v>.1)bins[Math.floor(value.h/10)]++;}
    if(!values.length)throw Error('Mostra nuk ka pikselë të lexueshëm.');
    const best=bins.indexOf(Math.max(...bins)),hueDistance=(a,b)=>Math.min(Math.abs(a-b),360-Math.abs(a-b));
    const colored=values.filter((v)=>v.s>.15&&v.v>.1&&hueDistance(v.h,best*10+5)<=15);
    const grays=values.filter((v)=>v.s<=.15);
    const selected=colored.length/values.length>=.25?colored:(grays.length/values.length>=.5?grays:values),average=(get)=>selected.reduce((sum,v)=>sum+get(v),0)/selected.length;
    const rgb=[0,1,2].map((i)=>Math.round(average((v)=>v.rgb[i])));
    const angle=Math.atan2(average((v)=>Math.sin(v.h*Math.PI/180)),average((v)=>Math.cos(v.h*Math.PI/180)))*180/Math.PI;
    return {rgb,hsv:{h:Number(((angle+360)%360).toFixed(3))%360,s:Number(average((v)=>v.s).toFixed(4)),v:Number(average((v)=>v.v).toFixed(4))},coverage:Number((selected.length/values.length).toFixed(3))};
  }
  function renderSamples(){
    $('role-samples').replaceChildren();samples.forEach((sample,index)=>{
      const box=document.createElement('div');box.className='uniform-sample';const title=document.createElement('p');title.textContent=`${index+1}. ${roleNames[sample.role]} · RGB ${sample.rgb.join(', ')}${sample.frame_seconds!==null?' · '+sample.frame_seconds+' s':''}`;
      const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent=`Hiq mostrën ${index+1}`;remove.addEventListener('click',()=>{samples.splice(index,1);invalidate();renderSamples();draw();});box.append(title,remove);$('role-samples').append(box);
    });
  }
  function addSample(rect){
    if(samples.length>=30)throw Error('Maksimumi 30 mostra; hiq ndonjë përpara se të shtosh.');
    const value=color(rect);samples.push({role:$('sample-role').value,rect:rect.map((n)=>Number(n.toFixed(4))),rgb:value.rgb,hsv:value.hsv,frame_seconds:media.kind==='video'?Number(video.currentTime.toFixed(3)):null});
    invalidate();renderSamples();draw();status(`Mostra u ruajt lokalisht (${Math.round(value.coverage*100)}% ngjyrë dominuese). Nuk është trajnim apo njohje automatike e rolit.`);
  }
  function testCrossing(start,end){
    if(config.line.enabled===false){$('crossing-result').textContent='Numërimi i kalimeve është i çaktivizuar për këtë kamerë.';return;}
    if(!lineReady){$('crossing-result').textContent='Vendos vijën përpara provës.';return;}
    const [a,b]=[config.line.start,config.line.end],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy),cross=(p)=>dx*(p[1]-a[1])-dy*(p[0]-a[0]);
    const first=cross(start),last=cross(end);let text='Trajektorja nuk kalon vijën e numërimit.';
    if(Math.abs(first)/length<=config.line.margin||Math.abs(last)/length<=config.line.margin)text='Një pikë është në brezin e tolerancës. Zgjidh pika më larg vijës.';
    else if(first*last<0){const ratio=first/(first-last),hit=[start[0]+ratio*(end[0]-start[0]),start[1]+ratio*(end[1]-start[1])],projection=((hit[0]-a[0])*dx+(hit[1]-a[1])*dy)/length**2;
      text=projection>=0&&projection<=1?`Provë manuale: ${Math.sign(last)===config.line.enter_side?'HYRJE':'DALJE'}. Nuk u ruajt event analitik.`:'Kalimi është jashtë segmentit; nuk numërohet.';}
    trace=[start,end];$('crossing-result').textContent=text;draw();
  }
  function release(){pause();video.removeAttribute('src');video.load();$('camera-image').removeAttribute('src');if(activeUrl)URL.revokeObjectURL(activeUrl);activeUrl=null;}
  async function load(file,kind){
    if(!file)return;const version=++loadVersion;
    const valid=kind==='image'?['image/png','image/jpeg','image/webp'].includes(file.type):['video/mp4','video/webm','video/ogg'].includes(file.type);
    if(!valid||file.size>(kind==='image'?20:150)*1024*1024){status('Zgjidh foto deri 20 MB ose video MP4/WebM deri 150 MB.',true);return;}
    const url=URL.createObjectURL(file);let accepted=false;
    try{
      let width,height,duration;
      if(kind==='image'){const image=new Image();image.src=url;await image.decode();width=image.naturalWidth;height=image.naturalHeight;}
      else{const probe=document.createElement('video');probe.preload='metadata';await new Promise((resolve,reject)=>{probe.onloadedmetadata=resolve;probe.onerror=reject;probe.src=url;});width=probe.videoWidth;height=probe.videoHeight;duration=probe.duration;probe.removeAttribute('src');probe.load();if(!Number.isFinite(duration)||duration<=0||duration>120)throw Error('Përdor një klip deri në 2 minuta, me pamje fikse.');}
      if(version!==loadVersion)return;
      if(!width||!height||width*height>24000000)throw Error('Pamja ka përmasa të pavlefshme ose është më e madhe se 24 megapiksel.');
      release();activeUrl=url;accepted=true;media={kind,width,height,...(kind==='video'?{duration_seconds:duration}:{})};
      $('camera-image').hidden=kind!=='image';video.hidden=kind!=='video';$('video-controls').hidden=kind!=='video';
      if(kind==='image'){$('camera-image').src=url;await $('camera-image').decode();}
      else{await new Promise((resolve,reject)=>{video.onloadeddata=resolve;video.onerror=reject;video.src=url;video.load();});$('video-seek').max=duration;}
      $('stage').style.aspectRatio=`${width} / ${height}`;$('empty-label').hidden=true;
      $('image-name').textContent=`${file.name} · ${width} × ${height} px${duration?' · '+duration.toFixed(1)+' s':''}`;
      $('fixed-view').checked=false;pending=null;trace=null;invalidate();draw();status('Pamja u ngarkua. Kontrollo vijën, zonat dhe mostrat për këtë kamerë.');
    }catch(error){status(error instanceof Error?error.message:'Videoja nuk hapet. Provo MP4 H.264, WebM ose një foto.',true);}
    finally{if(!accepted)URL.revokeObjectURL(url);}
  }
  $('image-file').addEventListener('change',async(e)=>{await load(e.target.files[0],'image');e.target.value='';});
  $('video-file').addEventListener('change',async(e)=>{await load(e.target.files[0],'video');e.target.value='';});
  $('video-play').addEventListener('click',async()=>{if(video.paused){pending=null;try{await video.play();$('video-play').textContent='Pauzë';}catch{status('Videoja nuk mund të luhet në këtë shfletues.',true);}}else pause();});
  video.addEventListener('timeupdate',()=>{$('video-seek').value=video.currentTime;$('video-time').textContent=video.currentTime.toFixed(1)+' s';});
  video.addEventListener('ended',pause);
  $('video-seek').addEventListener('input',()=>{pause();video.currentTime=Number($('video-seek').value);pending=null;trace=null;invalidate();draw();});
  $('role-tool').addEventListener('click',()=>setMode('role'));$('trace-tool').addEventListener('click',()=>setMode('trace'));
  $('add-sample').addEventListener('click',()=>{try{addSample(['sample-x1','sample-y1','sample-x2','sample-y2'].map((id)=>$(id).valueAsNumber));}catch(e){status(e.message,true);}});
  $('compare-samples').addEventListener('click',()=>{try{if(!samples.length)throw Error('Shto të paktën një mostër.');const results=samples.map((sample,index)=>{const value=color(sample.rect),delta=Math.min(Math.abs(value.hsv.h-sample.hsv.h),360-Math.abs(value.hsv.h-sample.hsv.h));const similar=(value.hsv.s<.15&&sample.hsv.s<.15||delta<=25)&&Math.abs(value.hsv.s-sample.hsv.s)<=.35&&Math.abs(value.hsv.v-sample.hsv.v)<=.35;return `${index+1}. ${roleNames[sample.role]}: ${similar?'ngjyrë e ngjashme':'ngjyrë e ndryshme'}`;});$('sample-result').textContent=results.join(' · ')+'. Krahasim vetëm në drejtkëndëshat e zgjedhur, jo njohje automatike personi.';}catch(e){$('sample-result').textContent=e.message;}});
  $('review-config').addEventListener('click',()=>{try{const value=collectConfig();if(!media)throw Error('Ngarko pamjen e kamerës për kontrollin manual.');if(!$('fixed-view').checked)throw Error('Konfirmo që pamja është fikse.');reviewed=fingerprint(value,metadata());let ambiguous=false;for(let i=0;i<samples.length;i++)for(let j=i+1;j<samples.length;j++){const a=samples[i],b=samples[j],delta=Math.abs(a.hsv.h-b.hsv.h);if(a.role!==b.role&&(Math.min(delta,360-delta)<=25||a.hsv.s<.15&&b.hsv.s<.15)&&Math.abs(a.hsv.s-b.hsv.s)<.35&&Math.abs(a.hsv.v-b.hsv.v)<.35)ambiguous=true;}$('review-result').textContent='Kontroll manual: gjeometria dhe metadata janë të vlefshme. Kjo nuk provon saktësinë e modelit, dallimin e stafit ose matjen e shërbimit.'+(ambiguous?' Kujdes: disa role kanë ngjyra të ngjashme; ngjyra nuk mjafton për t’i dalluar.':'');}catch(e){$('review-result').textContent=e.message;}});
  $('line-enabled').addEventListener('change',()=>{config.line.enabled=$('line-enabled').checked;trace=null;draw();invalidate();});
  $('settings').addEventListener('input',invalidate);$('fixed-view').addEventListener('change',invalidate);
  window.CalibrationExtras={zoneColor:(kind)=>zoneColors[kind]||zoneColors.other,validateConfig,pause,attach,onConfigLoaded,drawDetails,addSample,testCrossing};
  renderSamples();draw();
})();
