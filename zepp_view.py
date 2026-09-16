"""Zepp health presentation shared by the local dashboard builder."""
import html
from pathlib import Path

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
    page=page.replace('<h2>🏅 Best Efforts</h2>','<h2>🏅 Best Efforts</h2><p>Fastest splits / fastest average: Garmin archive; Longest และยอดรวม: Garmin + Zepp</p>')
    page=page.replace('<div id="stats-zones"></div>','<p>HR zones: Garmin archive เท่านั้น ยังไม่รวม Zepp เพราะขอบเขต Zone ต่างกัน</p><div id="stats-zones"></div>')
    page=page.replace('min: 48, max: 70, title:','suggestedMin: 48, title:')
    page=page.replace('อ่านจาก Garmin app แล้วกรอก','อ่านจาก Zepp app แล้วกรอก')
    return page

