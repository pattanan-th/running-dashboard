"""Import normalized ZeppBridge data, preserving the Garmin archive. No credentials read."""
import argparse
import copy
import html
import json
import os
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=7))
BUCKETS = ('long_runs', 'tempos_intervals', 'easy_runs')

def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))

def save(name, value):
    p = HERE / name
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(p)

def local(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('Zepp timestamp must have an explicit timezone')
    return d.astimezone(TZ)

def duration(minutes):
    if minutes is None:
        return '--'
    h, m = divmod(round(minutes), 60)
    return f'{h}h {m}m' if h else f'{m}m'

def clock(seconds):
    m, s = divmod(round(seconds), 60)
    h, m = divmod(m, 60)
    return f'{h}:{m:02}:{s:02}' if h else f'{m}:{s:02}'

def pace(seconds, km):
    return clock(seconds / km) if km else '--'

def read_bridge(db):
    c = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('BEGIN')  # one consistent read snapshot while the app keeps syncing
    def rows(sql):
        return [dict(r) for r in c.execute(sql)]
    result = {name: rows('SELECT * FROM ' + name) for name in
              ('daily_metrics', 'sleep_sessions', 'workouts', 'stream_provenance')}
    c.close()
    return result

def merge_stats(base, runs):
    s = copy.deepcopy(base)
    extra = [dict(d=r['date'], km=r['dist'], min=round(r['duration_seconds']/60, 2),
                  cal=r.get('calories') or 0, gain=r.get('ascent') or 0,
                  source='zepp', id=r['id']) for r in runs]
    s['runs_list'] = sorted(base['runs_list'] + extra, key=lambda r:r['d'])
    lt = s['lifetime']
    for target, key, divisor in [('km','km',1),('hours','min',60),('calories','cal',1),('elevation_m','gain',1)]:
        lt[target] = round(base['lifetime'][target] + sum(r[key] for r in extra)/divisor, 2)
    lt['runs'] = base['lifetime']['runs'] + len(extra)
    months = defaultdict(float)
    years = defaultdict(lambda:dict(runs=0, km=0, hours=0))
    for r in s['runs_list']:
        months[r['d'][:7]] += r['km']
        y = years[r['d'][:4]]
        y['runs'] += 1; y['km'] += r['km']; y['hours'] += r['min']/60
    s['by_month'] = {k:round(v,2) for k,v in sorted(months.items())}
    s['by_year'] = {k:{n:round(v,2) for n,v in values.items()} for k,values in sorted(years.items())}
    s['rankings']['Longest'] += [dict(time=f"{r['dist']:.1f} km", pace=r['pace'], date=r['date'], name=r['name']) for r in runs]
    s['rankings']['Longest'].sort(key=lambda r:float(r['time'].split()[0]), reverse=True)
    for r in runs:
        if r['dist'] > s['best']['longest_run_km']:
            s['best'].update(longest_run_km=r['dist'], longest_run_date=r['date'])
    # Split rankings and HR zone totals are kept as Garmin-only until Zepp sample
    # units and zone boundaries are verified. Never equate whole-run pace to a split.
    s['meta'].update(generated=datetime.now(TZ).date().isoformat(), source='Garmin archive + Zepp',
                     split_rankings_source='Garmin archive', zones_source='Garmin archive',
                     coverage_note='Totals and Longest: Garmin + Zepp. Fastest splits and HR zones: Garmin archive only.')
    return s

def import_data(data):
    a, sleep, wellness = load('activities.json'), load('sleep.json'), load('wellness.json')
    metric_days = defaultdict(dict)
    # Prefer user-fused summaries when both fused and device records exist.
    for r in sorted(data['daily_metrics'], key=lambda r:(r['source_scope']=='user_fused', r['id'])):
        metric_days[r['date']][r['metric']] = dict(value=r['value'], unit=r['unit'])
    oldsnaps = {r['date']:r for r in wellness.get('daily_snapshots',[]) if r.get('source')!='zepp'}
    for day, metrics in metric_days.items():
        val = lambda key: metrics.get(key,{}).get('value')
        oldsnaps[day] = dict(date=day, source='zepp', stress={'score':val('stress')},
                            rhr={'current':val('resting_hr')}, steps={'count':val('steps')}, metrics=metrics)
    wellness['daily_snapshots'] = sorted(oldsnaps.values(), key=lambda r:r['date'])
    wellness['meta'].update(source='Garmin archive + Zepp / T-Rex 3')
    nights = {r['d']:r for r in sleep['nights'] if r.get('source')!='zepp'}
    grouped = defaultdict(list)
    for r in data['sleep_sessions']:
        grouped[local(r['end_time']).date().isoformat()].append(r)
    for day, sessions in grouped.items():
        r = max(sessions, key=lambda s:s['duration_minutes'])
        stage = lambda k: duration(r[k+'_minutes']) if r.get(k+'_available',1) else '--'
        nights[day] = dict(d=day, t=duration(r['duration_minutes']), dp=stage('deep'), li=stage('light'),
                          rm=stage('rem'), aw=stage('awake'), bd=local(r['start_time']).strftime('%I:%M %p'),
                          wk=local(r['end_time']).strftime('%I:%M %p'), r=metric_days[day].get('resting_hr',{}).get('value'),
                          bb=None, source='zepp', score=r['score'], duration_minutes=r['duration_minutes'],
                          session_count=len(sessions), other_sleep_minutes=sum(s['duration_minutes'] for s in sessions)-r['duration_minutes'])
    sleep['nights'] = sorted(nights.values(), key=lambda r:r['d'])
    sleep['meta'].update(device='Garmin archive / Amazfit T-Rex 3', nights_collected=len(nights),
                         date_range=f"{min(nights)} to {max(nights)}")
    previous = {r['id']:r for b in BUCKETS for r in a[b] if r.get('source')=='zepp'}
    for b in BUCKETS:
        a[b] = [r for r in a[b] if r.get('source')!='zepp']
    runs, other = [], []
    # The archive's lightweight stats have no start timestamps. Fail closed if
    # dates overlap instead of silently double-counting or dropping same-day runs.
    base = load('garmin_stats_archive.json')
    cutoff = max(r['d'] for r in base['runs_list'])
    for w in sorted(data['workouts'], key=lambda w:w['start_time']):
        typ = w.get('workout_type_override') or w['workout_type']
        day = local(w['start_time']).date().isoformat()
        sec = w['moving_seconds']
        if sec is None:
            sec = (local(w['end_time'])-local(w['start_time'])).total_seconds()
        km = (w['distance_meters'] or 0)/1000
        r = dict(id='zepp:'+w['workout_id'], source='zepp', date=day, start_time=w['start_time'],
                 name='Trail Run' if typ=='trail_running' else typ.replace('_',' ').title(), workout_type=typ,
                 wk=None, dist=round(km,3), time=clock(sec), duration_seconds=sec, pace=pace(sec,km),
                 hr_avg=w['avg_hr'], hr_max=w['max_hr'], cad=w.get('avg_cadence_spm'),
                 stride=w['avg_stride_cm']/100 if w.get('avg_stride_cm') else None,
                 ascent=w.get('elevation_gain_m'), calories=w['calories'], walk_pct=None)
        r['note'] = previous.get(r['id'],{}).get('note') or (
            'ข้อมูลจาก Zepp / T-Rex 3 · HR เป็นค่าเฉลี่ยทั้งกิจกรรม ไม่ยืนยันเวลาที่อยู่แต่ละ Zone '
            '· ยังไม่คำนวณ walk% จาก cadence เพราะต้องยืนยันหน่วยข้อมูลรายเวลาก่อน')
        if r['note'].startswith('ข้อมูลจาก Zepp / T-Rex 3'):
            r['note'] = (f"{r['name']} · {r['dist']:.2f} km · {r['time']} · HR เฉลี่ย {r['hr_avg']} / สูงสุด {r['hr_max']} bpm. "
                         + ('Trail: อ่าน pace ร่วมกับความชันและสภาพเส้นทาง ไม่เทียบกับถนนตรงๆ. ' if typ=='trail_running' else '')
                         + 'ค่ารวมไม่บอกความหนักของแต่ละช่วง; ยังไม่ยืนยันว่าเป็น Easy หรือ Tempo. '
                         + 'HR เฉลี่ยไม่ใช่เวลาที่อยู่แต่ละ Zone; walk% ยังไม่มีข้อมูลที่ยืนยันหน่วยได้.')
        if typ not in ('run','trail_running','treadmill','treadmill_running','outdoor_running'):
            other.append(r); continue
        if day <= cutoff:
            raise ValueError(f'Zepp run overlaps Garmin archive ({day}); reconcile before import')
        runs.append(r)
        a['long_runs' if km>=13 else 'easy_runs'].append(r)
    for b in BUCKETS:
        a[b].sort(key=lambda r:r['date'], reverse=True)
    a['other_activities'] = other
    a['meta']['source'] = 'Garmin archive + Zepp / T-Rex 3'
    health = {r['stream']:dict(fetch_ok=r['last_fetch_ok_at'], parse_ok=r['last_parse_ok_at'],
                             parse_error=r['last_parse_error_kind']) for r in data['stream_provenance']}
    save('activities.json',a); save('sleep.json',sleep); save('wellness.json',wellness)
    save('stats.json',merge_stats(base,runs))
    save('zepp_sync.json',dict(imported_at=datetime.now(TZ).isoformat(), sleep_sessions=len(data['sleep_sessions']),
                             runs=len(runs), other_activities=len(other), streams=health))
    return sleep, wellness, runs

def coach_card(sleep, wellness, runs):
    n = sleep['nights'][-1]
    snap = next((s for s in wellness['daily_snapshots'] if s['date']==n['d']), {})
    stress = snap.get('stress',{}).get('score')
    show = lambda x:'ไม่มีข้อมูล' if x is None or x=='--' else str(x)
    rows = [('RHR',show(n['r']),'ดูแนวโน้มภายใน Zepp'),('Sleep',n['t'],'ข้อมูลคืนล่าสุด'),
            ('Bed',n['bd'],'เวลาไทย'),('Deep',n['dp'],'ค่าประเมินจากนาฬิกา'),
            ('REM',n['rm'],'ค่าประเมินจากนาฬิกา'),('Awake',n['aw'],'ไม่แทนค่าที่ขาดด้วยศูนย์'),
            ('Stress',show(stress),'วันเดียวกับคืนที่แสดง')]
    trend = ' → '.join(f"{x['d'][5:]}: {show(x['r'])}" for x in sleep['nights'][-4:])
    return '<div class="card" id="coach-analysis-card"><h2>🧠 Coach\'s Analysis · '+n['d']+'</h2><table><thead><tr><th>Metric</th><th>ค่า</th><th>สถานะ</th></tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in row)+'</tr>' for row in rows)+'''</tbody></table>
    <p>🚦 Readiness: ข้อมูลประกอบการประเมิน — ไม่ตัดสินความพร้อมจาก RHR ค่าเดียว</p>
    <p style="font-family:var(--mono)">RHR '''+html.escape(trend)+'''</p>
    <p>เปลี่ยนจาก Garmin เป็น Zepp: วิธีประเมิน Sleep/Stress ต่างกัน จึงไม่ใช้ baseline เดิมสรุปว่าล้าหรือป่วย และไม่ยืนยันสาเหตุของ RHR จากเวลาเข้านอนอย่างเดียว</p>
    <p>🎯 วันนี้: ตรวจความรู้สึกจริงร่วมกับข้อมูลคืนล่าสุด แผนในแท็บ Plan เป็นแผนเดิมที่ยังไม่ได้ทบทวนหลังเปลี่ยนนาฬิกา</p>
    <p>👉 ต่อไป: sync นาฬิกากับ Zepp บน iPhone ก่อนอัปเดต dashboard หากข้อมูลขาดให้ตรวจวันที่ล่าสุดของแต่ละ metric</p></div>'''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--local-only',action='store_true',help='Import current local database without cloud sync')
    ap.add_argument('--db',type=Path,default=Path(os.environ.get('ZEPPBRIDGE_DATA_DIR',Path.home()/'AppData/Local/ZeppBridge/data'))/'zepp.db')
    args=ap.parse_args()
    if not args.db.exists():
        raise SystemExit('ZeppBridge database not found; connect and sync first')
    if not args.local_only:
        cli=Path(os.environ.get('ZEPPBRIDGE_CLI',str(args.db.parent.parent/'zeppbridge-cli.exe')))
        env=dict(os.environ,ZEPPBRIDGE_DATA_DIR=str(args.db.parent))
        p=subprocess.run([str(cli),'sync','--mode','incremental','--json'],env=env,capture_output=True,text=True,encoding='utf-8')
        if p.returncode:
            raise SystemExit(f'ZeppBridge sync failed/busy (exit {p.returncode}); data not published. Retry or use --local-only after reviewing app status.')
    data=read_bridge(args.db)
    if not data['sleep_sessions'] or not data['daily_metrics']:
        raise SystemExit('No sleep or daily health data; refusing empty migration')
    if not (HERE/'garmin_stats_archive.json').exists():
        original=load('stats.json')
        if original['meta'].get('source')!='Garmin (all running activities)':
            raise SystemExit('Expected unmodified Garmin stats archive')
        save('garmin_stats_archive.json',original)
    sleep,wellness,runs=import_data(data)
    (HERE/'coach_analysis.html').write_text(coach_card(sleep,wellness,runs),encoding='utf-8')
    print(json.dumps(dict(zepp_runs=len(runs),sleep_sessions=len(data['sleep_sessions']),latest_sleep=sleep['nights'][-1]['d'],latest_run=runs[-1]['date'] if runs else None)))

if __name__=='__main__':
    main()
