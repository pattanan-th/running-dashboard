/* All displayed values are text nodes; local data never becomes markup. */
(() => {
'use strict';
const root = document.getElementById('zepp-series-data');
if (!root) return;
const data = JSON.parse(root.textContent);
const charts = new Map();
const fmt = v => v == null ? '—' : typeof v === 'number' ? Number(v.toFixed(2)).toLocaleString() : String(v);
const km = v => v == null ? '—' : fmt(v/1000);
const time = s => { const n=Math.round(s); return Math.floor(n/60)+':'+String(n%60).padStart(2,'0'); };
const metricValue = (s,v) => v == null ? '—' : s.unit==='min/km' ? time(v*60) : fmt(v);
const el = (tag,text,cls) => {const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
function table(headers,rows){
 const wrap=el('div',null,'zepp-table-scroll'), t=el('table'),head=el('thead'),hr=el('tr'),body=el('tbody');
 headers.forEach(x=>hr.appendChild(el('th',x)));head.appendChild(hr);t.appendChild(head);
 rows.forEach(row=>{const tr=el('tr');row.forEach(x=>tr.appendChild(el('td',fmt(x))));body.appendChild(tr);});
 t.appendChild(body);wrap.appendChild(t);return wrap;
}
function list(parent,items){const ul=el('ul');items.forEach(s=>ul.appendChild(el('li',s)));parent.appendChild(ul);}
function clear(parent){parent.querySelectorAll('canvas').forEach(c=>{charts.get(c)?.destroy();charts.delete(c);});parent.replaceChildren();}
function button(text,fn){const b=el('button',text,'btn');b.type='button';b.addEventListener('click',fn);return b;}
function selectors(parent,items,onselect,label){
 parent.setAttribute('aria-label',label);parent.setAttribute('role','group');
 const buttons=items.map((item,i)=>{const b=button(item.label,()=>activate(i));parent.appendChild(b);return b;});
 function activate(i){buttons.forEach((b,j)=>{b.className='btn'+(i===j?' primary':'');b.setAttribute('aria-pressed',String(i===j));});onselect(items[i].value);}
 if(items.length)activate(0);else parent.appendChild(el('p','ยังไม่มีข้อมูล'));
}
function plot(parent,label,unit,bins,options={}){
 const details=el('details',null,'zepp-graph'),summary=el('summary',label+' · '+unit);
 details.appendChild(summary);details.open=!!options.open;
 if(options.note)details.appendChild(el('p',options.note,'zepp-note'));
 const holder=el('div',null,'zepp-canvas'),canvas=el('canvas');holder.appendChild(canvas);details.appendChild(holder);
 canvas.setAttribute('role','img');canvas.setAttribute('aria-label',label+' '+unit);
 parent.appendChild(details);
 function draw(){
  if(!details.open||charts.has(canvas))return;
  if(typeof Chart==='undefined'){holder.replaceChildren(el('p','โหลดกราฟไม่ได้ แต่ค่าตารางยังอ่านได้'));return;}
  const xfactor=options.xfactor||1;
  const toSeries=index=>bins.map(b=>({x:b[0]/xfactor,y:b[index]}));
  const datasets=options.simple?[{label,data:toSeries(1),borderColor:'#58a6ff',pointRadius:2,stepped:options.stepped||false}]:[
   {label:'ต่ำสุด',data:toSeries(2),borderWidth:0,pointRadius:0,backgroundColor:'rgba(88,166,255,.12)'},
   {label:'สูงสุด',data:toSeries(3),borderWidth:0,pointRadius:0,fill:'-1',backgroundColor:'rgba(88,166,255,.12)'},
   {label:'เฉลี่ย',data:toSeries(1),borderColor:'#58a6ff',borderWidth:2,pointRadius:options.pointRadius??0}
  ];
  const chart=new Chart(canvas,{type:'line',data:{datasets},options:{
   responsive:true,maintainAspectRatio:false,animation:false,spanGaps:false,
   interaction:{mode:'index',intersect:false},
   plugins:{legend:{display:false},tooltip:{callbacks:{
    title:items=>options.xtick?options.xtick(items[0].parsed.x):'นาที '+fmt(items[0].parsed.x),
    label:item=>item.dataset.label+': '+metricValue({unit},item.parsed.y)+' '+unit
   }}},
   scales:{x:{type:'linear',min:options.xmin??0,max:options.xmax,
      title:{display:true,text:options.xlabel||'นาทีหลังเริ่มกิจกรรม'},
      ticks:options.xtick?{callback:options.xtick,maxTicksLimit:8}:{}},
    y:{reverse:!!options.reverse,title:{display:true,text:unit},min:options.ymin,max:options.ymax,
       ticks:options.ytick?{callback:options.ytick}:unit==='min/km'?{callback:v=>time(v*60)}:{}}
   }
  }});
  charts.set(canvas,chart);
 }
 details.addEventListener('toggle',draw);draw();return details;
}
function graphTools(parent){
 const row=el('div',null,'zepp-buttons');
 row.appendChild(button('เปิดทุกกราฟ',()=>parent.querySelectorAll('details.zepp-graph').forEach(d=>d.open=true)));
 row.appendChild(button('พับกราฟ',()=>parent.querySelectorAll('details.zepp-graph').forEach(d=>d.open=false)));
 parent.appendChild(row);
}
function workout(r){
 const parent=document.getElementById('zepp-workout-content');clear(parent);
 parent.appendChild(el('h3',r.date+' · '+r.name+' · '+km(r.summary.distance_meters)+' km'));
 parent.appendChild(el('p',r.user_note));
 list(parent,r.findings);
 parent.appendChild(el('h3','ค่ารวมจากนาฬิกา'));
 const labels={distance_meters:'Distance (m)',calories:'Calories (kcal)',avg_hr:'HR เฉลี่ย (bpm)',max_hr:'HR สูงสุด (bpm)',min_hr:'HR ต่ำสุด (bpm)',total_steps:'Steps',moving_seconds:'Moving time (s)',elevation_gain_m:'Elevation gain (m)',elevation_loss_m:'Elevation loss (m)',max_altitude_m:'Altitude max (m)',min_altitude_m:'Altitude min (m)',training_load:'Training load',vo2max:'VO₂max estimate',training_effect:'Aerobic TE',anaerobic_training_effect:'Anaerobic TE',rpe:'RPE จาก Zepp',avg_cadence_spm:'Cadence เฉลี่ย (spm)',max_cadence_spm:'Cadence สูงสุด (spm)',avg_stride_cm:'Step length เฉลี่ย (cm)'};
 parent.appendChild(table(['ค่า','ผล'],Object.entries(r.summary).map(([k,v])=>[labels[k]||k,v])));
 parent.appendChild(el('h3','กราฟทุกช่องที่อ่านได้'));
 parent.appendChild(table(['กราฟ','เฉลี่ย','ต่ำสุด','สูงสุด','หน่วย','ข้อมูลที่ใช้ได้'],Object.values(r.series).map(s=>[s.label,metricValue(s,s.mean),metricValue(s,s.min),metricValue(s,s.max),s.unit,fmt(s.coverage_pct)+'%'])));
 list(parent,r.warnings);
 graphTools(parent);
 const grid=el('div',null,'zepp-graph-grid');parent.appendChild(grid);
 Object.entries(r.series).forEach(([key,s])=>{
  if(!s.bins.length)return;
  plot(grid,s.label,s.unit,s.bins,{open:['hr','pace','cadence'].includes(key),xfactor:60,xmax:r.elapsed_s/60,reverse:['pace','gap'].includes(key),note:'เส้น = เฉลี่ย 15 วินาที · แถบ = ต่ำสุดถึงสูงสุด · ข้อมูลที่ใช้ได้ '+fmt(s.coverage_pct)+'%'});
 });
 if(r.fastest_400m){
  const e=r.fastest_400m;parent.appendChild(el('h3','ช่วง 400 m เร็วที่สุด · '+time(e.start_s)+'–'+time(e.end_s)));
  parent.appendChild(table(['กราฟ','เฉลี่ยช่วงนี้','เฉลี่ยทั้งกิจกรรม','หน่วย'],Object.entries(e.metrics).map(([k,s])=>[r.series[k].label,metricValue(r.series[k],s.mean),metricValue(r.series[k],r.series[k].mean),r.series[k].unit])));
  parent.appendChild(el('p','HR เฉลี่ย 60 วินาทีก่อนช่วงนี้: '+fmt(e.before_hr?.mean)+' / หลังช่วงนี้: '+fmt(e.after_hr?.mean)+' bpm · '+e.after_note));
 }
 if(r.hr_peak_context){
  const p=r.hr_peak_context;parent.appendChild(el('h3','รอบจุด HR สูงสุด ±15 วินาที · '+time(p.time_s)));
  parent.appendChild(table(['กราฟ','เฉลี่ย','หน่วย'],Object.entries(p.metrics).map(([k,s])=>[r.series[k].label,metricValue(r.series[k],s.mean),r.series[k].unit])));
 }
 parent.appendChild(el('h3','Split ตามระยะ · คำนวณจากระยะสะสม'));
 parent.appendChild(table(['กม.','เวลา','Pace','HR','Cadence','Power','GCT','Step length'],r.splits.map(s=>[fmt(s.km_start)+'–'+fmt(s.km_end),time(s.duration_s),s.pace,s.metrics.hr.mean,s.metrics.cadence.mean,s.metrics.power.mean,s.metrics.gct.mean,s.metrics.stride.mean])));
 if(r.normalized_splits?.length)parent.appendChild(table(['Split Zepp','ระยะ m','เวลา s','HR'],r.normalized_splits.map(s=>[s.split_index,s.distance_m,s.duration_seconds,s.avg_hr])));
 parent.appendChild(el('h3','HR zones จาก Zepp · ไม่ใช้ขอบเขต Garmin'));
 parent.appendChild(el('p','รวม '+time(r.zone_seconds)+' · ต่างจากเวลาทั้งกิจกรรม '+fmt(r.zone_difference_s)+' วินาที; ช่วง bpm แสดงตามขอบที่ Zepp ส่งมา ไม่สมมติขอบบนเป็น max HR จริง'));
 parent.appendChild(table(['ช่วงขอบ bpm จาก Zepp','เวลา','% ของเวลาที่มี Zone'],r.hr_zones.map(z=>[(z.lower_bpm==null?'ต่ำกว่า ':z.lower_bpm+'–')+z.upper_bpm,time(z.seconds),z.pct])));
 parent.appendChild(el('h3','ครึ่งแรก / ครึ่งหลังตามเวลา'));
 parent.appendChild(table(['ค่า','ครึ่งแรก','ครึ่งหลัง'],['hr','speed','cadence','power'].map(k=>[r.series[k].label+' ('+r.series[k].unit+')',r.halves['1']?.[k].mean,r.halves['2']?.[k].mean])));
 parent.appendChild(el('h3','Laps และการหยุดที่บันทึก'));
 parent.appendChild(table(['Lap','เริ่ม','จบ','ระยะ m','HR'],r.laps.map(s=>[s.lap_index,time(s.start_s),time(s.end_s),s.distance_m,s.avg_hr])));
 if(r.pauses.length)parent.appendChild(table(['Pause','เริ่ม','จบ'],r.pauses.map(s=>[s.kind,time(s.start_s),time(s.end_s)])));
 else parent.appendChild(el('p','ไม่มี pause record ไม่ได้ยืนยันว่าไม่เคยหยุดหรือเดิน'));
 const audit=el('details');audit.appendChild(el('summary','ตรวจความพร้อมของช่องข้อมูล'));
 const used=new Set(['heart_rate','gait','speed','pace','altitude','time_delta_altitude','currentDistance','equivPace','power_meter','runPosture','pause','lap','kilo_pace','time']);
 audit.appendChild(table(['ช่องข้อมูล','สถานะ'],Object.entries(r.raw_fields).map(([k,v])=>[k,!v?'ไม่มีข้อมูล':used.has(k)?'มี · ใช้ช่องที่ตรวจหน่วยแล้ว/ข้อมูลสรุป':'มี · ยังไม่ยืนยันความหมาย จึงไม่นำมาตีความ'])));
 parent.appendChild(audit);
}
function health(h){
 const parent=document.getElementById('zepp-health-content');clear(parent);
 parent.appendChild(el('h3','สุขภาพ · '+h.date));list(parent,h.findings);
 parent.appendChild(el('p','ข้อมูลนาฬิกาเป็นค่าประเมิน ไม่ใช้ฟันธงว่าพร้อมซ้อมหรือวินิจฉัยโรค'));
 parent.appendChild(table(['ค่า','ผล','หน่วย','ผลต่าง','เทียบกับวันที่','หมายเหตุ'],Object.entries(h.daily).sort().map(([k,v])=>[k,v.value,v.unit,v.change,v.compared_with,v.retained_from_previous_sync?'เก็บจาก sync ก่อนหน้า':''])));
 graphTools(parent);
 const grid=el('div',null,'zepp-graph-grid');parent.appendChild(grid);
 Object.entries(h.series).forEach(([k,s])=>{
  parent.appendChild(el('p',s.label+': '+s.count+' ตัวอย่าง · '+s.first.slice(11,16)+'–'+s.last.slice(11,16)+' · เฉลี่ย '+fmt(s.mean)+' '+s.unit));
  plot(grid,s.label,s.unit,s.bins,{open:['heart_rate','hrv_rmssd','stress'].includes(k),pointRadius:2,xmax:1440,xlabel:'เวลาไทย',xtick:x=>Math.floor(x/60)+':'+String(Math.round(x%60)).padStart(2,'0'),note:s.note||'ค่าเฉลี่ยตัวอย่าง 30 นาที · ช่องว่างคือไม่มีข้อมูล'});
 });
 parent.appendChild(el('h3','ช่วงการนอน · แยกทุก session'));
 h.sleep.forEach(s=>{
  parent.appendChild(el('p',s.start.slice(0,16).replace('T',' ')+' → '+s.end.slice(0,16).replace('T',' ')+' · หลับ '+fmt(s.duration_minutes)+' นาที · คะแนน '+fmt(s.score)));
  parent.appendChild(table(['Deep min','Light min','REM min','Awake min','Wake count'],[[s.deep_minutes,s.light_minutes,s.rem_minutes,s.awake_minutes,s.wake_count]]));
  const stages={deep:0,light:1,rem:2,awake:3},bins=[];
  let last=null;
  s.stages.forEach(st=>{if(last!==null&&st.start_min>last)bins.push([last,null]);
    bins.push([st.start_min,stages[st.stage]??null],[st.end_min,stages[st.stage]??null]);last=st.end_min;});
  if(bins.length)plot(parent,'Sleep stages','stage',bins,{simple:true,stepped:'after',open:true,xlabel:'นาทีหลังเริ่ม session',ymin:0,ymax:3,ytick:v=>['Deep','Light','REM','Awake'][v]||'',note:'ช่วงการนอนเป็นค่าประเมินจากนาฬิกา; ช่องที่ขาดไม่ถือเป็น Awake'});
  else parent.appendChild(el('p','ไม่มีข้อมูลแบ่งช่วงการนอนของ session นี้'));
 });
}
const wselect=document.getElementById('zepp-workout-select');
const hselect=document.getElementById('zepp-health-select');
selectors(wselect,[...data.workouts].reverse().map(r=>({label:r.date+' · '+km(r.summary.distance_meters)+' km · '+r.name,value:r})),workout,'เลือกกิจกรรมเพื่อวิเคราะห์');
selectors(hselect,[...data.health].reverse().map(h=>({label:h.date,value:h})),health,'เลือกวันสุขภาพ');
const trendButtons=document.getElementById('zepp-trend-select'), trendBody=document.getElementById('zepp-trend-content');
const keys=[...new Set(data.health.flatMap(h=>Object.keys(h.daily)))].sort();
selectors(trendButtons,keys.map(k=>({label:k,value:k})),key=>{
 clear(trendBody);
 const latest=[...data.health].reverse().find(h=>h.daily[key])?.daily[key];
 const bins=data.health.map((h,i)=>[i,h.daily[key]?.value??null]);
 plot(trendBody,key,latest?.unit||'',bins,{simple:true,open:true,xlabel:'วันที่',xtick:x=>Number.isInteger(x)?data.health[x]?.date||'':'',note:'แสดงทุกวันที่มีข้อมูล ช่องว่างไม่แทนด้วยศูนย์'});
},'เลือกแนวโน้มสุขภาพ');
})();
