'use strict';
(() => {
  const scene=document.querySelector('.camera-demo');
  if(!scene)return;
  const people=[document.getElementById('demo-person-1'),document.getElementById('demo-person-2')];
  const count=document.getElementById('demo-count');
  const button=document.getElementById('demo-toggle');
  const line=document.querySelector('.demo-count-line');
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused=reduced.matches,elapsed=paused?7:0,last=null,frame=null;
  function label(){
    button.textContent=window.HomeLanguage?.translate(paused?'Play animation':'Pause animation') || (paused?'Luaj animimin':'Ndalo animimin');
    button.setAttribute('aria-pressed',String(paused));
  }
  function render(){
    const cycle=elapsed%13;
    let entries=0,flash=false;
    people.forEach((person,index)=>{
      const progress=(cycle-index*3)/6;
      const visible=progress>=0&&progress<=1;
      const x=70+580*Math.max(0,Math.min(1,progress));
      person.setAttribute('transform',`translate(${x.toFixed(2)} ${index?235:160})`);
      person.setAttribute('visibility',visible?'visible':'hidden');
      if(progress>=.5)entries++;
      if(progress>=.5&&progress<.58)flash=true;
    });
    count.textContent=String(entries);
    line.setAttribute('stroke-width',flash?'7':'3');
    scene.dataset.entries=String(entries);
  }
  function tick(now){
    frame=null;
    if(paused||document.hidden){last=null;return;}
    if(last!==null)elapsed+=Math.min((now-last)/1000,.1);
    last=now;render();frame=requestAnimationFrame(tick);
  }
  function schedule(){if(frame===null&&!paused&&!document.hidden)frame=requestAnimationFrame(tick);}
  function setPaused(value){paused=value;last=null;if(frame!==null)cancelAnimationFrame(frame);frame=null;label();schedule();}
  button.addEventListener('click',()=>setPaused(!paused));
  reduced.addEventListener('change',(event)=>{if(event.matches)setPaused(true);});
  document.addEventListener('visibilitychange',()=>{last=null;schedule();});
  window.addEventListener('home-language-change',label);
  render();label();schedule();
})();

// Restaurant scenes are illustrative only. No camera, detector or API is used.
(() => {
  const toggle=document.getElementById('restaurant-demo-toggle');
  if(!toggle)return;
  const ns='http://www.w3.org/2000/svg';
  const t=(key)=>window.HomeLanguage?.translate(key)||key;
  function shape(parent,tag,attrs,text){const node=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,v));if(text!==undefined)node.textContent=text;parent.append(node);return node;}
  function text(parent,x,y,size=12,color='#a8bdcf'){return shape(parent,'text',{x,y,'text-anchor':'middle','font-size':size,fill:color,'font-family':'inherit'});}
  function dot(parent,color='#38edbd'){return shape(parent,'circle',{r:8,fill:color,stroke:'#071321','stroke-width':3});}
  function place(node,x,y,visible=true){node.setAttribute('cx',x);node.setAttribute('cy',y);node.setAttribute('visibility',visible?'visible':'hidden');}
  function floor(id){const svg=document.getElementById(id);shape(svg,'rect',{x:1,y:1,width:338,height:278,rx:16,fill:'#0a1928',stroke:'#24394c'});return svg;}
  function table(svg,x,y,id){const rect=shape(svg,'rect',{x:x-37,y:y-25,width:74,height:50,rx:12,fill:'#20394a',stroke:'#456076'});text(svg,x,y+4,13,'#e3eef6').textContent=id;return rect;}
  const tables=floor('tables-demo');
  const tableNodes=[85,255,170].map((x,i)=>{const y=i===2?195:80;return {x,y,rect:table(tables,x,y,'T0'+(i+1)),people:[dot(tables),dot(tables)],label:text(tables,x,y+53)};});
  const service=floor('service-demo');table(service,205,130,'T01');
  const guests=[dot(service),dot(service)];const waiter=dot(service,'#ffca78');
  const waiterLabel=text(service,65,214,11,'#ffca78');const phaseLabel=text(service,170,34,13,'#e3eef6');
  const waitLabel=text(service,170,239,12,'#ffca78');const dineLabel=text(service,170,260,12,'#8de9d0');
  shape(service,'path',{d:'M40 195 Q70 105 150 130',fill:'none',stroke:'#ffca7850','stroke-dasharray':'4 6'});
  const takeaway=floor('takeaway-demo');
  shape(takeaway,'rect',{x:30,y:35,width:280,height:58,rx:12,fill:'#243d4d',stroke:'#496476'});
  const counterLabel=text(takeaway,170,70,14,'#e3eef6');
  shape(takeaway,'rect',{x:105,y:104,width:130,height:98,rx:15,fill:'#38edbd09',stroke:'#38edbd60','stroke-dasharray':'5 5'});
  const customer=dot(takeaway);const counterTime=text(takeaway,170,244,14,'#8de9d0');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let paused=reduced.matches,elapsed=paused?8:0,last=null,frame=null;
  function label(){toggle.textContent=t(paused?'Play animation':'Pause animation');toggle.setAttribute('aria-pressed',String(paused));}
  function render(){
    const cycle=elapsed%16;
    let occupied=0;
    tableNodes.forEach((item,i)=>{
      const start=i===2?7:i*2,end=i===0?12:15;
      const active=cycle>=start&&cycle<end;
      const age=Math.max(0,Math.floor((Math.min(cycle,end)-start)*3));
      item.rect.setAttribute('stroke',active?'#38edbd':'#456076');
      item.people.forEach((node,j)=>place(node,item.x+(j?-50:50),item.y,active));
      item.label.textContent=active?`${age} min · ${t('Occupied')}`:t('Free');
      if(active)occupied+=2;
    });
    document.getElementById('tables-demo-status').textContent=`${t('Customers at tables')}: ${occupied} · ${t('Simulated dwell')}`;
    const seated=cycle>=1,served=cycle>=5,departed=cycle>=13;
    guests.forEach((node,i)=>place(node,205+(i?-51:51),130,seated&&!departed));
    const approach=Math.max(0,Math.min(1,(cycle-3)/2));
    place(waiter,45+105*approach,195-65*approach,cycle>=3&&cycle<7);
    waiterLabel.textContent=t('Waiter');
    const wait=seated?Math.min(4,Math.floor(cycle-1)):0;
    const dining=served?Math.min(28,Math.floor((cycle-5)*3.5)):0;
    phaseLabel.textContent=t(departed?'Visit complete':served?'Dining':seated?'Waiting':'Arrival');
    waitLabel.textContent=`${t('Waiting')}: ${wait} min`;
    dineLabel.textContent=`${t('Dining')}: ${dining} min`;
    document.getElementById('service-demo-status').textContent=`${t('Time at table')}: ${wait+dining} min · ${t('Illustrative simulation')}`;
    let x=170,y=150;
    if(cycle<3){x=40+(130*cycle/3);y=250-(100*cycle/3);}
    else if(cycle>=9){x=170+Math.min(140,(cycle-9)*45);y=150+Math.min(100,(cycle-9)*30);}
    place(customer,x,y,cycle<13);
    counterLabel.textContent=t('Counter');
    counterTime.textContent=`${t('Waiting')}: ${Math.min(6,Math.max(0,Math.floor(cycle-3)))} min`;
    document.getElementById('takeaway-demo-status').textContent=t(cycle>=9?'Waiting complete':'Simulated wait');
  }
  function tick(now){frame=null;if(paused||document.hidden){last=null;return;}if(last!==null)elapsed+=Math.min((now-last)/1000,.1);last=now;render();frame=requestAnimationFrame(tick);}
  function schedule(){if(frame===null&&!paused&&!document.hidden)frame=requestAnimationFrame(tick);}
  function pause(value){paused=value;last=null;if(frame!==null)cancelAnimationFrame(frame);frame=null;label();schedule();}
  toggle.addEventListener('click',()=>pause(!paused));
  reduced.addEventListener('change',(event)=>{if(event.matches)pause(true);});
  document.addEventListener('visibilitychange',()=>{last=null;schedule();});
  window.addEventListener('home-language-change',()=>{label();render();});
  label();render();schedule();
})();
