"""Zepp health presentation shared by the local dashboard builder."""
import html
import json
from pathlib import Path

def best_efforts_card(root):
    stats = json.loads((root/'stats.json').read_text(encoding='utf8'))
    groups = []
    for title, rankings in [('ตามระยะ', stats.get('rankings', {})), ('ตามเวลา', stats.get('time_rankings', {}))]:
        for label, entries in rankings.items():
            longest = label == 'Longest duration'
            timed = title == 'ตามเวลา' and not longest
            display = {'Longest':'ระยะไกลที่สุด', 'Longest duration':'ใช้เวลานานที่สุด'}.get(label, label)
            note = ('เวลารวมกิจกรรม · Garmin + Zepp; Garmin ปัดเป็น 0.1 นาที ส่วน Zepp ใช้ moving time เมื่อมี' if longest else
                    'ระยะไกลที่สุดในเวลาที่เลือก · Zepp เท่านั้น; ประวัติ Garmin ยังไม่มีระยะรายเวลา' if timed else
                    'ระยะรวมกิจกรรม · Garmin + Zepp' if label == 'Longest' else
                    'เวลาที่เร็วที่สุดตามระยะ · Garmin + Zepp')
            if label not in ('Longest','Longest duration'):
                note += ' · Zepp เป็นค่าประมาณ รวมเวลาหยุดในช่วง และไม่ข้ามข้อมูลขาดเกิน 15 วินาที'
            headers = ['อันดับ']+(['เวลา'] if longest else [])+['ระยะ' if timed or label=='Longest' or longest else 'เวลา', 'Pace /km', 'วันที่', 'กิจกรรม / แหล่งข้อมูล']
            rows = []
            for rank, e in enumerate(entries, 1):
                value = f"{e['distance_m']/1000:.2f} km" if timed or longest else e['time']
                if label == 'Longest':
                    value = f"{float(e['time'].split()[0]):.2f} km"
                rows.append([rank]+([e['time']] if longest else [])+[value, e['pace'], e['date'], e.get('name','Run')+' · '+('Zepp' if e.get('source')=='zepp' else 'Garmin')])
            groups.append(dict(headers=headers, rows=rows, note=note, label=display,
                               kind='distance' if title=='ตามระยะ' else 'time'))
    data = json.dumps(groups, ensure_ascii=False).replace('<', '\\u003c')
    return ('<div class="card" id="best-efforts-card"><h2>🏅 Best Efforts</h2>'
            '<div id="best-effort-types" role="group" aria-label="ประเภทสถิติ" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px"></div>'
            '<div id="best-effort-options" role="group" aria-label="ระยะหรือช่วงเวลา" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px"></div>'
            '<p id="best-effort-note"></p><p id="best-effort-count" aria-live="polite"></p>'
            '<div id="best-effort-scroll" style="max-height:360px;overflow:auto"><table id="best-effort-table"><thead></thead><tbody></tbody></table></div></div>'
            '<script>(()=>{const groups='+data+''';
const table=document.getElementById('best-effort-table');
const types=document.getElementById('best-effort-types');
const options=document.getElementById('best-effort-options');
let kind='distance';
const selected={distance:groups.findIndex(g=>g.kind==='distance'),time:groups.findIndex(g=>g.kind==='time')};
function button(label,active,action){
 const b=document.createElement('button');b.type='button';b.className='btn'+(active?' primary':'');
 b.textContent=label;b.setAttribute('aria-pressed',String(active));b.addEventListener('click',action);return b;
}
function renderTypes(){
 types.replaceChildren();
 [['distance','Distance'],['time','Time']].forEach(([key,label])=>{
  types.appendChild(button(label,kind===key,()=>{kind=key;renderTypes();renderOptions();show();}));
 });
}
function renderOptions(){
 options.replaceChildren();
 groups.forEach((g,i)=>{if(g.kind===kind)options.appendChild(button(g.label,selected[kind]===i,()=>{
  selected[kind]=i;renderOptions();show();
 }));});
}
function show(){
 const group=groups[selected[kind]]; if(!group)return;
 document.getElementById('best-effort-note').textContent=group.note;
 document.getElementById('best-effort-count').textContent=group.rows.length ? 'ทั้งหมด '+group.rows.length+' รัน · เลื่อนดูได้' : 'ยังไม่มีข้อมูลสำหรับสถิตินี้';
 table.tHead.replaceChildren(); table.tBodies[0].replaceChildren();
 const head=document.createElement('tr');
 group.headers.forEach(text=>{const cell=document.createElement('th');cell.scope='col';cell.textContent=text;head.appendChild(cell);});
 table.tHead.appendChild(head);
 group.rows.forEach(values=>{const row=document.createElement('tr');values.forEach(text=>{const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);});table.tBodies[0].appendChild(row);});
 document.getElementById('best-effort-scroll').scrollTop=0;
}
renderTypes();renderOptions();show();})();</script>''')

def enrich(page, root, wellness, activities):
    card=root/'coach_analysis.html'
    if not (root/'zepp_sync.json').exists(): return page
    if card.exists():
        start=page.index('  <div class="card" id="coach-analysis-card">')
        end=page.index('  <div class="card">\n    <h2>📈 Last Night',start)
        page=page[:start]+card.read_text(encoding='utf8')+'\n'+page[end:]
    def esc(v): return html.escape(str(v if v is not None else '—'))
    def row(values): return '<tr>'+''.join('<td>'+esc(v)+'</td>' for v in values)+'</tr>'
    days=[s for s in wellness['daily_snapshots'] if s.get('source')=='zepp']
    latest={}
    for s in days:
        for k,v in s.get('metrics',{}).items(): latest[k]=(v['value'],v['unit'],s['date'])
    keys=[('resting_hr','RHR'),('stress','Stress'),('sleep_hrv','Sleep HRV'),('readiness','Zepp Readiness'),('hybrid_charge','Zepp Hybrid Charge'),('steps','Steps'),('training_load','Training Load'),('vo2max','VO₂max')]
    block='<div class="card"><h2>🌿 Zepp Health · T-Rex 3</h2><p>ค่าล่าสุดที่มีข้อมูล — ตรวจวันที่แต่ละรายการ; Hybrid Charge ไม่ใช่ Garmin Body Battery</p><table><thead><tr><th>Metric</th><th>ค่า</th><th>หน่วย</th><th>วันที่</th></tr></thead><tbody>'
    block+=''.join(row([label,*latest[k]]) for k,label in keys if k in latest)
    block+='</tbody></table><p>HR รายเวลา: มีข้อมูลย้อนหลัง แต่การดึงบางช่วงรายงานข้อมูลว่าง ยังไม่ยืนยันความครบถ้วน</p><h3>ประวัติสุขภาพ</h3><div style="max-height:300px;overflow:auto"><table><thead><tr><th>วันที่</th><th>RHR</th><th>Stress</th><th>HRV</th></tr></thead><tbody>'
    block+=''.join(row([s['date'],s['rhr']['current'],s['stress']['score'],s['metrics'].get('sleep_hrv',{}).get('value')]) for s in reversed(days))
    block+='</tbody></table></div></div>'
    page=page.replace('<div id="coach-analysis-sleep-mirror"></div>','<div id="coach-analysis-sleep-mirror"></div>'+block)
    other='<div class="card"><h2>กิจกรรมอื่นจาก Zepp</h2><div style="max-height:300px;overflow:auto"><table><thead><tr><th>วันที่</th><th>กิจกรรม</th><th>เวลา</th><th>HR เฉลี่ย</th></tr></thead><tbody>'
    other+=''.join(row([r['date'],r['name'],r['time'],r['hr_avg']]) for r in reversed(activities.get('other_activities',[])))
    other+='</tbody></table></div></div>'
    page=page.replace('<div id="runs-list"></div>','<div id="runs-list"></div>'+other)
    page=page.replace("${emoji} ${bucketLabel}", "${emoji} ${r.source==='zepp' ? 'ZEPP · '+r.name : bucketLabel}")
    page=page.replace('Built from Garmin Connect data','Garmin archive + Zepp / T-Rex 3')
    page=page.replace('<h2>🏅 Best Efforts</h2>','<h2>🏅 Best Efforts</h2><p>Best Efforts by Distance และ Longest: Garmin + Zepp · Fastest average: Garmin archive</p>')
    page=page.replace('${e.date}</td></tr>', "${e.date}<br>${e.source==='zepp'?'Zepp · คำนวณจากระยะสะสม':'Garmin'}</td></tr>")
    page=page.replace('<div id="stats-rankings"></div>', '<p style="font-size:12px;color:var(--text-muted)">Zepp: ช่วงระยะที่เร็วที่สุดต่อรัน คำนวณโดยประมาณจากระยะสะสมรายวินาที รวมเวลาหยุดภายในช่วง; ไม่ใช้ช่วงข้อมูลขาดเกิน 15 วินาที จึงอาจต่างจาก Best Effort ในแอป และยังขึ้นกับความแม่นยำระยะนาฬิกา</p><div id="stats-rankings"></div>')
    page=page.replace('<div id="stats-zones"></div>','<p>HR zones: Garmin archive เท่านั้น ยังไม่รวม Zepp เพราะขอบเขต Zone ต่างกัน</p><div id="stats-zones"></div>')
    page=page.replace('min: 48, max: 70, title:','suggestedMin: 48, title:')
    page=page.replace('อ่านจาก Garmin app แล้วกรอก','อ่านจาก Zepp app แล้วกรอก')
    marker = '<div class="card">\n    <h2>❤️ HR Zone Distribution (all time)</h2>'
    if marker not in page:
        raise ValueError('Best Efforts insertion point missing')
    start = page.rfind('<div class="card">', 0, page.index('<h2>🏅 Best Efforts</h2>'))
    end = page.index(marker, start)
    page = page[:start] + best_efforts_card(root) + page[end:]
    analysis_path = root/'zepp_analysis.json'
    if analysis_path.exists():
        payload = analysis_path.read_text(encoding='utf8').replace('<', '\\u003c')
        styles = '''<style>
        #zepp-workout-analysis,#zepp-health-analysis{column-span:all;width:100%;box-sizing:border-box}
        .zepp-buttons{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
        .zepp-select{display:flex;gap:6px;overflow:auto;padding:10px 0;max-height:180px;flex-wrap:wrap}
        .zepp-select button{white-space:nowrap}
        .zepp-table-scroll{overflow:auto;max-height:420px;margin:12px 0}
        .zepp-graph-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:12px}
        .zepp-graph{border:1px solid var(--border,#444);border-radius:10px;padding:12px;margin:8px 0;min-width:0}
        .zepp-graph summary{cursor:pointer;font-weight:600}
        .zepp-canvas{position:relative;height:220px;margin-top:12px}
        .zepp-note{font-size:12px;color:var(--text-muted)}
        </style>'''
        run_card = ('<div class="card" id="zepp-workout-analysis"><h2>📈 วิเคราะห์จากกราฟ · Zepp</h2>'
                    '<p>อ่านข้อมูลทุกช่องที่ตรวจหน่วยได้ พร้อมเลือกดูทุกกิจกรรมย้อนหลัง</p>'
                    '<div id="zepp-workout-select" class="zepp-select"></div><div id="zepp-workout-content"></div></div>')
        health_card = ('<div class="card" id="zepp-health-analysis"><h2>🌿 กราฟสุขภาพและการนอน · Zepp</h2>'
                       '<div id="zepp-health-select" class="zepp-select"></div><div id="zepp-health-content"></div>'
                       '<h3>แนวโน้มทุกค่ารายวัน</h3><div id="zepp-trend-select" class="zepp-select"></div>'
                       '<div id="zepp-trend-content"></div></div>')
        page=page.replace('<section class="page" id="page-runs">',
                          '<section class="page" id="page-runs">'+run_card)
        page=page.replace('<div id="coach-analysis-sleep-mirror"></div>',
                          '<div id="coach-analysis-sleep-mirror"></div>'+health_card)
        script=(root/'zepp_analysis_view.js').read_text(encoding='utf8')
        page=page.replace('</body>',styles+'<script id="zepp-series-data" type="application/json">'+payload+
                          '</script><script>'+script+'</script></body>')
    return page
