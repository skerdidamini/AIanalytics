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
