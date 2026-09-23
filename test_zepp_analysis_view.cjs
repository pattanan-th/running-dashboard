const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Node {
 constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.attributes={};this.textContent='';this.className='';}
 appendChild(n){this.children.push(n);return n;}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this.attributes[k]=v;}
 addEventListener(k,fn){this.listeners[k]=fn;}
 set open(v){this._open=v;this.listeners.toggle?.();}
 get open(){return this._open;}
 querySelectorAll(selector){const match=n=>selector==='canvas'?n.tagName==='canvas':selector==='details.zepp-graph'?n.tagName==='details'&&n.className==='zepp-graph':false;
  return this.children.flatMap(n=>[...(match(n)?[n]:[]),...n.querySelectorAll(selector)]);}
 click(){this.listeners.click?.();}
}
const ids={};
for(const id of ['zepp-series-data','zepp-workout-content','zepp-health-content','zepp-workout-select','zepp-health-select','zepp-trend-select','zepp-trend-content'])ids[id]=new Node('div');
const report=JSON.parse(fs.readFileSync('zepp_analysis.json','utf8'));
ids['zepp-series-data'].textContent=JSON.stringify(report);
let made=0,destroyed=0;
class Chart {
 constructor(canvas,config){this.config=config;made++;
  for(const dataset of config.data.datasets)for(const p of dataset.data){assert(Number.isFinite(p.x));assert(p.y===null||Number.isFinite(p.y));}
  assert.strictEqual(config.options.spanGaps,false);
 }
 destroy(){destroyed++;}
}
const document={getElementById:id=>ids[id],createElement:tag=>new Node(tag)};
vm.runInNewContext(fs.readFileSync('zepp_analysis_view.js','utf8'),{document,Chart,console});
assert.strictEqual(ids['zepp-workout-select'].children.length,report.workouts.length);
assert.strictEqual(ids['zepp-health-select'].children.length,report.health.length);
for(const id of ['zepp-workout-select','zepp-health-select','zepp-trend-select']){
 const group=ids[id];
 for(const b of group.children){b.click();assert.strictEqual(b.attributes['aria-pressed'],'true');assert.strictEqual(group.children.filter(x=>x.attributes['aria-pressed']==='true').length,1);}
}
for(const id of ['zepp-workout-content','zepp-health-content','zepp-trend-content']){
 for(const d of ids[id].querySelectorAll('details.zepp-graph'))d.open=true;
}
assert(made>100);assert(destroyed>50);
console.log('UI smoke passed:',report.workouts.length,'workouts,',report.health.length,'health days,',ids['zepp-trend-select'].children.length,'daily metrics;',made,'charts with finite axes and preserved null gaps.');

