"""Date-aligned descriptive daily comparisons; no clinical readiness inference."""
import html
from datetime import date


def summaries(sleep, wellness):
    health = {r['date']: r for r in wellness['daily_snapshots'] if r.get('source') == 'zepp'}
    nights = sorted((r for r in sleep['nights'] if r.get('source') == 'zepp'), key=lambda r: r['d'])
    result = []
    previous = None
    for n in nights:
        h = health.get(n['d'], {})
        metric = lambda k: h.get('metrics', {}).get(k, {}).get('value')
        row = dict(date=n['d'], sleep=n['t'], rhr=n.get('r'), stress=metric('stress'),
                   hrv=metric('sleep_hrv'), readiness=metric('readiness'), score=n.get('score'))
        parts = []
        adjacent = previous and (date.fromisoformat(n['d'])-date.fromisoformat(previous['d'])).days == 1
        if adjacent:
            diff = n['duration_minutes']-previous['duration_minutes']
            parts.append('นอนเท่าเดิม' if diff == 0 else f"นอน{'เพิ่ม' if diff > 0 else 'ลด'} {abs(diff):g} นาทีจากวันก่อน")
            if n.get('r') is not None and previous.get('r') is not None:
                d = n['r']-previous['r']
                parts.append('RHR เท่าเดิม' if d == 0 else f"RHR {'เพิ่ม' if d > 0 else 'ลด'} {abs(d):g} bpm")
            old_metrics = health.get(previous['d'], {}).get('metrics', {})
            for key, label, unit in [('stress','Stress','คะแนน'),('sleep_hrv','HRV','ms')]:
                v, old = metric(key), old_metrics.get(key, {}).get('value')
                if v is not None and old is not None:
                    d = v-old
                    parts.append(label+' เท่าเดิม' if d == 0 else f"{label} {'เพิ่ม' if d > 0 else 'ลด'} {abs(d):g} {unit}")
        else:
            parts.append('ไม่มีข้อมูลวันก่อนหน้าสำหรับเปรียบเทียบ')
        missing = [label for key,label in [('stress','Stress'),('sleep_hrv','HRV'),('readiness','Readiness')] if metric(key) is None]
        if missing: parts.append('ยังไม่มีค่าสรุปรายวัน '+', '.join(missing)+' ของวันนี้ (อาจมีตัวอย่างรายช่วงในกราฟด้านล่าง)')
        if any(v.get('retained_from_previous_sync') for v in h.get('metrics',{}).values()):
            parts.append('บางค่าเก็บจากการซิงค์ก่อนหน้า')
        row['analysis'] = ' · '.join(parts)
        result.append(row)
        previous = n
    return result


def render(sleep, wellness):
    rows = summaries(sleep, wellness)
    if not rows: return ''
    esc = lambda v: html.escape('—' if v is None else str(v))
    body = ''.join('<tr>'+''.join('<td>'+esc(r[k])+'</td>' for k in ['date','sleep','score','rhr','stress','hrv','readiness','analysis'])+'</tr>' for r in reversed(rows))
    return ('<h3>วิเคราะห์รายวัน · Zepp</h3><p>'+esc(rows[-1]['analysis'])+
            '</p><p>เทียบตามวันที่ที่ ZeppBridge บันทึก ไม่ย้ายค่าข้ามวัน; ข้อมูลวันนี้อาจยังไม่ครบ '
            'ระยะนอนและเวลาสิ้นสุดอาจเปลี่ยนหลังซิงค์เพิ่มเติม การเปลี่ยนแปลงเหล่านี้ยังไม่ยืนยันสาเหตุหรือความพร้อมซ้อมหนัก</p>'
            '<div style="max-height:360px;overflow:auto"><table><thead><tr><th>วันที่</th><th>Sleep</th><th>Sleep score</th>'
            '<th>RHR</th><th>Stress</th><th>HRV (ms)</th><th>Zepp Readiness</th><th>วิเคราะห์เทียบวันก่อน</th>'
            '</tr></thead><tbody>'+body+'</tbody></table></div>')
