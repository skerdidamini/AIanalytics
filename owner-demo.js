'use strict';
// Entirely synthetic, browser-local preview. Never reads business APIs or sessions.
(() => {
  const t=(key)=>window.HomeLanguage?.translate(key)||key;
  const ns='http://www.w3.org/2000/svg';
  const seeds=[6,9,13,20,28,24,17,15,22,30,25,11];
  const rows=[];
  for(let day=0;day<7;day++)for(let camera=0;camera<2;camera++)seeds.forEach((n,index)=>{
    rows.push({day,camera,hour:index+9,entries:Math.max(2,n+camera*3-day),exits:Math.max(1,n+camera*3-day-2)});
  });
  document.querySelectorAll('[data-owner-demo]').forEach((root)=>{
    const compact=root.dataset.ownerDemo==='compact';
    const make=(tag,cls,text,parent=root)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;parent.append(el);return el;};
    const top=make('div','preview-top');make('strong','', 'ANALYTICA / DEMO',top);const badge=make('span','preview-badge','',top);
    const title=make('h3','preview-title','');
    const filters=make('div','preview-filters');
    function select(items){const label=make('label','','',filters);const caption=make('span','','',label);const control=make('select','','',label);items.forEach(([value,key])=>{const option=new Option('',value);option.dataset.key=key;control.add(option);});return {caption,control};}
    const period=select([['today','Sample day'],['yesterday','Previous sample day'],['week','Sample week']]);
    const camera=select([['all','All cameras'],['0','Entrance camera'],['1','Patio camera']]);
    const cards=make('div','preview-kpis');const values=[];
    for(let i=0;i<4;i++){const card=make('div','',undefined,cards);values.push({label:make('span','','',card),value:make('strong','','',card),note:make('small','','',card)});}
    const chartTitle=make('h4','','');const chart=document.createElementNS(ns,'svg');chart.setAttribute('viewBox','0 0 680 210');chart.setAttribute('role','img');chart.classList.add('preview-chart');root.append(chart);
    const legend=make('p','preview-legend','');
    const wrap=make('div','preview-table');const table=make('table','','',wrap);const caption=make('caption','','',table);const head=make('thead','','',table);const header=make('tr','','',head);const headers=['Zone','Observed visits','Average dwell'].map(()=>make('th','','',header));headers.forEach(el=>el.scope='col');const body=make('tbody','','',table);
    const planned=make('p','preview-planned','');const download=make('button','preview-download','');download.type='button';
    if(compact){filters.hidden=true;wrap.hidden=true;download.hidden=true;}
    let selection=[];
    function render(){
      title.textContent=t('Your venue, at a glance.');badge.textContent=t('Simulated data');
      period.caption.textContent=t('Period');camera.caption.textContent=t('Camera');
      for(const field of [period,camera])Array.from(field.control.options).forEach(option=>option.textContent=t(option.dataset.key));
      selection=rows.filter(row=>(period.control.value==='week'||row.day===(period.control.value==='yesterday'?1:0))&&(camera.control.value==='all'||row.camera===Number(camera.control.value)));
      const entries=selection.reduce((sum,r)=>sum+r.entries,0),exits=selection.reduce((sum,r)=>sum+r.exits,0);
      const groups=period.control.value==='week'?7:12;
      const buckets=Array.from({length:groups},(_,i)=>({label:period.control.value==='week'?`D${i+1}`:`${i+9}:00`,entries:0,exits:0}));
      selection.forEach(row=>{const bucket=buckets[period.control.value==='week'?row.day:row.hour-9];bucket.entries+=row.entries;bucket.exits+=row.exits;});
      const peak=buckets.reduce((best,bucket)=>bucket.entries>best.entries?bucket:best,buckets[0]);
      const zoneData=[['Zone1',18],['Zone2',26],['Takeaway',5]].map(([name,minutes],i)=>({name,minutes,visits:Math.max(1,Math.floor(entries/(6+i*2)))}));
      const visits=zoneData.reduce((n,z)=>n+z.visits,0);const average=zoneData.reduce((n,z)=>n+z.minutes*z.visits,0)/visits;
      const labels=['Recorded entries','Recorded exits','Observed average dwell','Busiest interval'];
      const display=[String(entries),String(exits),`${average.toLocaleString(document.documentElement.lang,{maximumFractionDigits:1})} min`,peak.label];
      values.forEach((card,i)=>{card.label.textContent=t(labels[i]);card.value.textContent=display[i];card.note.textContent=t(i===2?'Individual zone observations':'Illustrative sample');});
      chartTitle.textContent=t('Traffic over time');chart.setAttribute('aria-label',t('Entries and exits chart'));chart.replaceChildren();
      const max=Math.max(...buckets.map(b=>b.entries),1);
      function svg(tag,attrs,text){const node=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,value));if(text!==undefined)node.textContent=text;chart.append(node);return node;}
      for(let i=0;i<=3;i++){const y=170-i*48;svg('line',{x1:40,y1:y,x2:670,y2:y,stroke:'#dce5ec'});svg('text',{x:30,y:y+4,'text-anchor':'end',fill:'#60788b','font-size':10},Math.round(max*i/3));}
      const step=620/buckets.length;
      buckets.forEach((bucket,i)=>{for(const [j,key] of ['entries','exits'].entries()){const height=bucket[key]/max*144;const bar=svg('rect',{x:45+i*step+j*step*.32,y:170-height,width:step*.27,height,rx:3,fill:j?'#a7bfda':'#159b86'});const tip=document.createElementNS(ns,'title');tip.textContent=`${bucket.label}: ${bucket[key]} ${t(j?'Recorded exits':'Recorded entries')}`;bar.append(tip);}if(i%2===0||buckets.length===7)svg('text',{x:45+i*step+step*.3,y:192,'text-anchor':'middle',fill:'#60788b','font-size':10},bucket.label);});
      legend.textContent=`● ${t('Recorded entries')}  ·  ${t('Recorded exits')}`;
      caption.textContent=t('Zone activity — simulated');headers.forEach((el,i)=>el.textContent=t(['Zone','Observed visits','Average dwell'][i]));body.replaceChildren();
      zoneData.forEach(zone=>{const row=make('tr','','',body);[zone.name,zone.visits,`${zone.minutes} min`].forEach(value=>make('td','',String(value),row));});
      planned.textContent=t('Waiter waiting time, order delivery and group table sessions: planned features, not active measurements.');
      download.textContent=t('Download sample CSV');
    }
    period.control.addEventListener('change',render);camera.control.addEventListener('change',render);
    download.addEventListener('click',()=>{
      const csv=['sample_day,camera,hour,entries,exits',...selection.map(row=>[row.day+1,row.camera===0?'entrance':'patio',row.hour,row.entries,row.exits].join(','))].join('\r\n');
      const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='analytica-simulated-demo.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    window.addEventListener('home-language-change',render);render();
  });
})();
