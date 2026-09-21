"""Zepp health presentation shared by the local dashboard builder."""
import html
import json
from pathlib import Path

def time_efforts_card(root):
    rankings = json.loads((root/'stats.json').read_text(encoding='utf8')).get('time_rankings', {})
    esc = lambda v: html.escape(str(v))
    parts = ['<div class="card" id="stats-time-efforts"><h2>⏱ Best Efforts by Time</h2>',
             '<p>5–60 นาที: ระยะไกลที่สุดจาก Zepp · Longest duration: เวลากิจกรรมยาวที่สุด รวม Garmin + Zepp</p>',
             '<p>ค่าประมาณจากระยะนาฬิกา รวมเวลาหยุดภายในช่วง ไม่ข้ามช่วงข้อมูลขาดเกิน 15 วินาที</p>',
             '<style>#stats-time-efforts .time-tabs{display:flex;flex-wrap:wrap;gap:6px}',
             '#stats-time-efforts .time-panel{display:none;flex-basis:100%}',
             '#stats-time-efforts input:focus-visible+label{outline:2px solid currentColor}',
             '#stats-time-efforts input:checked+label{background:var(--accent);color:var(--bg)}']
    for i in range(len(rankings)):
        parts.append(f'#time-effort-{i}:checked~#time-panel-{i}'+'{display:block}')
    parts.append('</style><div class="time-tabs">')
    for i, label in enumerate(rankings):
        checked = ' checked' if i == 0 else ''
        parts.append(f'<input style="position:absolute;opacity:0;width:1px;height:1px" type="radio" name="time-effort" id="time-effort-{i}"{checked}><label class="btn" for="time-effort-{i}">{esc(label)}</label>')
    for i, (label, entries) in enumerate(rankings.items()):
        parts.append(f'<div class="time-panel" id="time-panel-{i}" aria-label="{esc(label)}"><p>ทั้งหมด {len(entries)} รัน · เลื่อนดูประวัติได้</p>')
        longest = label == 'Longest duration'
        if longest:
            parts.append('<p>เรียงตามเวลากิจกรรมที่บันทึก ไม่ใช่เวลาเร็วที่สุดหรือเวลาเคลื่อนไหวที่ยืนยันเหมือนกันทุกอุปกรณ์; Garmin เดิมปัดเป็น 0.1 นาที ส่วน Zepp ใช้ moving time เมื่อมีข้อมูล</p>')
        if entries:
            parts.append('<div style="max-height:300px;overflow:auto"><table><thead><tr><th>อันดับ</th>'+('<th>เวลา</th>' if longest else '')+'<th>ระยะ</th><th>Pace /km</th><th>วันที่</th><th>กิจกรรม</th></tr></thead><tbody>')
            for position, e in enumerate(entries, 1):
                values = [position]+([e['time']] if longest else [])+[f"{e['distance_m']/1000:.3f} km", e['pace'], e['date'], e['name']+' · '+('Garmin' if e['source']=='garmin' else 'Zepp')]
                parts.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in values)+'</tr>')
            parts.append('</tbody></table></div>')
        else:
            parts.append('<p>ยังไม่มีรันที่มีข้อมูลต่อเนื่องครบช่วงเวลานี้</p>')
        parts.append('</div>')
    parts.append('</div></div>')
    return ''.join(parts)

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
    page = page.replace(marker, time_efforts_card(root)+marker)
    return page

