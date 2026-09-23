"""Descriptive analysis of all available Zepp series, without routes or identifiers.

Units verified against ZeppBridge v2.4.0 (ff5e2d9), decoder/workout_detail.rs
and storage/mod.rs. Calculations use full-resolution local samples; published
charts contain 15-second aggregates, not raw GPS or account data.
"""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import math
import statistics

TZ = timezone(timedelta(hours=7))
# key: label, unit, source column, multiplier, inclusive bounds, raw channel
SPECS = {
    'hr': ('Heart rate', 'bpm', 'heart_rate', 1, 1, 250, 'heart_rate'),
    'pace': ('Pace', 'min/km', 'pace', 1000/60, 1, 60, 'speed'),
    'speed': ('Speed', 'km/h', 'speed', 3.6, 0, 100, 'speed'),
    'cadence': ('Cadence', 'spm', 'cadence', 1, 0, 300, 'gait'),
    'stride': ('Step length', 'm', 'stride', .01, 0, 5, 'gait'),
    'altitude': ('Altitude', 'm', 'altitude', 1, -500, 9000, 'time_delta_altitude'),
    'power': ('Running power', 'W', 'power_watts', 1, 0, 3000, 'power_meter'),
    'gct': ('Ground contact time', 'ms', 'ground_contact_ms', 1, 1, 2000, 'runPosture'),
    'vo': ('Vertical oscillation', 'mm', 'vertical_oscillation_mm', 1, 0, 500, 'runPosture'),
    'vr': ('Vertical ratio', '%', 'vertical_ratio_pct', 1, 0, 100, 'runPosture'),
    'gap': ('Grade-adjusted pace', 'min/km', 'equivalent_pace_s', 1/60, 1, 60, 'equivPace'),
}
RAW_CHANNELS = {s[6] for s in SPECS.values()} | {'currentDistance'}
SUMMARY_KEYS = ('distance_meters', 'calories', 'avg_hr', 'max_hr', 'min_hr',
                'total_steps', 'moving_seconds', 'elevation_gain_m', 'elevation_loss_m',
                'max_altitude_m', 'min_altitude_m', 'training_load', 'vo2max',
                'training_effect', 'anaerobic_training_effect', 'rpe',
                'avg_cadence_spm', 'max_cadence_spm', 'avg_stride_cm')
HEALTH_LABELS = {
    'heart_rate': 'Heart rate', 'hrv': 'HRV (spot)', 'hrv_rmssd': 'HRV RMSSD',
    'stress': 'Stress', 'spo2_apnea_low': 'SpO₂ low-event readings',
    'weight': 'Weight', 'height': 'Height', 'bmi': 'BMI',
    'body_balance_score': 'Body balance score',
}


def stamp(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('Timestamp has no timezone')
    return d.astimezone(TZ)


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def rounded(v):
    return round(v, 3) if v is not None else None


def mmss(sec):
    if sec is None:
        return '—'
    m, s = divmod(round(sec), 60)
    return f'{m}:{s:02}'


def source_support(encoded, elapsed):
    """Match upstream timed_fill intervals, rejecting long manufactured fills.

    Upstream's dt spans the interval assigned to the current sample. First
    interval has dt+1 seconds; later intervals have dt seconds. A long span
    is not evidence of second-by-second measurement. No extrapolated tail.
    """
    supported, cursor = set(), 0
    try:
        for i, item in enumerate(x for x in encoded.split(';') if x):
            raw = item.split(',')[0].strip()
            dt = int(raw) if raw else 1
            if dt < 0:
                break
            span = dt + (1 if i == 0 else 0)
            if span <= 15:
                supported.update(range(cursor, min(cursor+span, math.ceil(elapsed))))
            cursor += span
            if cursor >= elapsed:
                break
    except (TypeError, ValueError):
        pass  # A broken delta chain cannot safely be resumed.
    return supported


def clean_samples(workout, samples, detail):
    start, end = stamp(workout['start_time']), stamp(workout['end_time'])
    elapsed = (end-start).total_seconds()
    support = {k: source_support(detail[k], elapsed)
               for k in RAW_CHANNELS if isinstance(detail.get(k), str) and detail[k]}
    points, rejected = {}, defaultdict(int)
    for row in samples:
        try:
            t = (stamp(row['timestamp'])-start).total_seconds()
        except (ValueError, TypeError):
            continue
        if not 0 <= t < elapsed:
            continue
        p = {'t': t}
        for key, (_, unit, column, factor, low, high, raw) in SPECS.items():
            v = row.get(column)
            v = v*factor if finite(v) else None
            valid = v is not None and low <= v <= high
            if raw in support and int(t) not in support[raw]:
                valid = False
            if v is not None and not valid:
                rejected[key] += 1
            p[key] = v if valid else None
        points[t] = p  # duplicate timestamps must not count twice
    points = [points[t] for t in sorted(points)]
    for i, p in enumerate(points):
        # Normalized data is 1 Hz: never assume the time to a distant next row
        # is observed. Endpoints at workout end carry no extra second.
        next_t = points[i+1]['t'] if i+1 < len(points) else elapsed
        p['dt'] = min(1.0, next_t-p['t'], elapsed-p['t'])
    return points, elapsed, dict(rejected)


def window_stats(points, key, start, end):
    usable = []
    for p in points:
        overlap = max(0, min(end, p['t']+p['dt'])-max(start, p['t']))
        if overlap and p.get(key) is not None:
            usable.append((p[key], overlap, p['t']))
    if not usable:
        return dict(mean=None, min=None, max=None, seconds=0, coverage_pct=0, peak_s=None)
    seconds = sum(w for _, w, _ in usable)
    peak = max(usable, key=lambda x: x[0])
    return dict(mean=rounded(sum(v*w for v,w,_ in usable)/seconds),
                min=rounded(min(v for v,_,_ in usable)), max=rounded(peak[0]),
                seconds=rounded(seconds), coverage_pct=rounded(100*seconds/(end-start)),
                peak_s=rounded(peak[2]))


def graph_bins(points, key, elapsed, width=15):
    groups = defaultdict(list)
    for p in points:
        groups[int(p['t']//width)].append(p)
    result = []
    for i in range(math.ceil(elapsed/width)):
        a, b = i*width, min(elapsed, (i+1)*width)
        s = window_stats(groups[i], key, a, b)
        # [start seconds, mean, min, max, observed seconds]
        result.append([a, s['mean'], s['min'], s['max'], s['seconds']])
    return result


def distance_at(segments, t):
    for seg in segments:
        if seg and seg[0][0] <= t <= seg[-1][0]:
            ts = [p[0] for p in seg]
            i = bisect_left(ts, t)
            if ts[i] == t:
                return seg[i][1]
            a, b = seg[i-1], seg[i]
            return a[1]+(t-a[0])/(b[0]-a[0])*(b[1]-a[1])
    return None


def crossing(seg, d, departure=False):
    ds = [p[1] for p in seg]
    if not ds or not ds[0] <= d <= ds[-1]:
        return None
    i = bisect_right(ds, d)-1 if departure else bisect_left(ds, d)
    if ds[i] == d:
        return seg[i][0]
    if departure:
        i += 1
    a,b = seg[i-1],seg[i]
    return a[0]+(d-a[1])/(b[1]-a[1])*(b[0]-a[0])


def interval_report(points, start, end, metres):
    return dict(start_s=rounded(start), end_s=rounded(end), distance_m=rounded(metres),
                duration_s=rounded(end-start), pace=mmss((end-start)*1000/metres),
                metrics={k: window_stats(points, k, start, end) for k in SPECS})


def fastest_window(segments, metres):
    best = None
    for seg in segments:
        if len(seg)<2 or seg[-1][1]-seg[0][1]<metres:
            continue
        ts, ds = zip(*seg)
        def at(d, departure=False):
            i=bisect_right(ds,d)-1 if departure else bisect_left(ds,d)
            if ds[i]==d:
                return ts[i]
            if departure:
                i+=1
            return ts[i-1]+(d-ds[i-1])/(ds[i]-ds[i-1])*(ts[i]-ts[i-1])
        candidates = {d for _, d in seg} | {d-metres for _,d in seg}
        for d in sorted(candidates):
            if not seg[0][1] <= d <= seg[-1][1]-metres:
                continue
            a,b = at(d,True),at(d+metres)
            if b>a and (best is None or b-a<best[1]-best[0]):
                best=(a,b)
    return best


def workout_analysis(w, samples, detail, zones, pauses, laps, normalized_splits):
    from zepp_efforts import distance_segments
    points, elapsed, rejected = clean_samples(w, samples, detail)
    result = dict(id='zepp:'+w['workout_id'], date=stamp(w['start_time']).date().isoformat(),
                  name=w['workout_type'], elapsed_s=elapsed, summary={k:w.get(k) for k in SUMMARY_KEYS},
                  series={}, splits=[], fastest_400m=None, warnings=[], findings=[],
                  pauses=[], laps=[], hr_zones=[], raw_fields=detail.get('_fields', {}))
    for key, (label,unit,*_) in SPECS.items():
        s = window_stats(points,key,0,elapsed) if elapsed>0 else window_stats([],key,0,1)
        result['series'][key] = dict(label=label, unit=unit, **s,
                                    excluded_samples=rejected.get(key,0),
                                    bins=graph_bins(points,key,elapsed) if s['seconds'] else [])
    segments = []
    try:
        segments = distance_segments(detail.get('currentDistance',''), w['distance_meters'],elapsed)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        result['warnings'].append('ระยะรายเวลาใช้ไม่ได้: '+str(exc))
    # Derived splits cannot bridge gaps. The tiny initial distance (< 2 m) is
    # assigned to start only when the validated timeline starts at t=0.
    if segments:
        for seg in segments:
            if seg[0][0]==0 and seg[0][1]<=2:
                seg[0]=(0,0)
        total = w['distance_meters']
        bounds = list(range(0,int(total)//1000*1000+1,1000))
        if bounds[-1]<total:
            bounds.append(total)
        for a,b in zip(bounds,bounds[1:]):
            for seg in segments:
                if seg[0][1]<=a and b<=seg[-1][1]:
                    t0,t1=crossing(seg,a,True),crossing(seg,b)
                    if t1>t0:
                        result['splits'].append(dict(km_start=a/1000, km_end=b/1000,
                            **interval_report(points,t0,t1,b-a)))
                    break
        best = fastest_window(segments,400)
        if best:
            a,b=best
            event=interval_report(points,a,b,400)
            event['start_km']=rounded(distance_at(segments,a)/1000)
            event['end_km']=rounded(distance_at(segments,b)/1000)
            event['before_hr']=window_stats(points,'hr',max(0,a-60),a) if a>0 else None
            event['after_hr']=window_stats(points,'hr',b,min(elapsed,b+60)) if b<elapsed else None
            event['after_note']='HR หลังช่วงเร็วขณะยังทำกิจกรรม ไม่ใช่การทดสอบ HR recovery มาตรฐาน'
            result['fastest_400m']=event
            result['findings'].append(f"ช่วง 400 m เร็วที่สุด: กม. {event['start_km']}–{event['end_km']} เวลา {mmss(b-a)} (pace {event['pace']}/km); ไม่ยืนยันว่าเป็นช่วงที่ผู้ใช้เล่า")
    # Fallback to already decoded splits, without geohashes from raw kilo_pace.
    if not result['splits'] and normalized_splits:
        result['normalized_splits']=[{k:v for k,v in s.items() if k not in ('id','workout_id')}
                                     for s in normalized_splits]
    if result['splits']:
        covered=sum(s['distance_m'] for s in result['splits'])
        result['split_distance_m']=rounded(covered)
        if w['distance_meters']-covered>2:
            result['warnings'].append(f"Split ครอบคลุม {covered:g} จาก {w['distance_meters']:g} m; ไม่เติมช่วงท้ายหรือช่วงขาดที่ไม่มีจุดระยะรองรับ")
    for name, rows in [('pauses',pauses),('laps',laps)]:
        for row in rows:
            try:
                a=max(0,(stamp(row['start_time'])-stamp(w['start_time'])).total_seconds())
                b=min(elapsed,(stamp(row['end_time'])-stamp(w['start_time'])).total_seconds())
                if b>a:
                    result[name].append(dict(start_s=a,end_s=b,
                        **{k:row[k] for k in ('kind','lap_index','distance_m','duration_seconds','avg_hr','max_hr') if k in row}))
            except (TypeError,ValueError):
                result['warnings'].append('ข้าม pause/lap ที่เวลาไม่ถูกต้อง')
    zone_total=sum(z['seconds'] for z in zones if finite(z.get('seconds')) and z['seconds']>=0)
    previous=None
    for z in sorted(zones,key=lambda z:z['zone_index']):
        upper=z['upper_bound_bpm']
        result['hr_zones'].append(dict(index=z['zone_index'],lower_bpm=previous,upper_bpm=upper,
                                       seconds=z['seconds'],pct=rounded(z['seconds']/zone_total*100) if zone_total else None))
        previous=upper
    result['zone_seconds']=zone_total
    result['zone_difference_s']=rounded(elapsed-zone_total)
    if zones and abs(elapsed-zone_total)>5:
        result['warnings'].append(f'เวลา HR zone จาก Zepp รวม {zone_total:g} s ต่างจาก elapsed {elapsed:g} s; ไม่เติมส่วนต่างเข้า Zone ใด')
    result['halves']={str(i+1): {k:window_stats(points,k,i*elapsed/2,(i+1)*elapsed/2)
                                for k in ('hr','speed','cadence','power')}
                      for i in range(2)} if elapsed>0 else {}
    result['warnings'].append('กราฟสรุปทุก 15 วินาที (เฉลี่ย/ต่ำสุด/สูงสุด); วิเคราะห์จากรายวินาทีก่อนย่อ ไม่เติมช่วงขาดเกิน 15 วินาที')
    result['warnings'].append('ครึ่งแรก/หลังต่างกันอาจเกิดจากเพซ ความชัน อากาศ หรือช่วงเร่ง จึงไม่สรุป cardiac drift หรือความล้าจาก HR เพียงอย่างเดียว')
    for key, summary_key, tolerance in [('hr','avg_hr',5),('cadence','avg_cadence_spm',5)]:
        v=result['series'][key]['mean']; ref=w.get(summary_key)
        if v is not None and ref is not None and abs(v-ref)>tolerance:
            result['warnings'].append(f'{key}: ค่าเฉลี่ยกราฟต่างจากสรุปนาฬิกา ({v} vs {ref}); วิธีนับช่วงอาจต่างกัน')
    hr=result['series']['hr']
    if hr['max'] is not None:
        t=hr['peak_s']; d=distance_at(segments,t)
        peak=dict(time_s=t, km=rounded(d/1000) if d is not None else None,
                  **interval_report(points,max(0,t-15),min(elapsed,t+15),1))
        # Not a distance interval: remove misleading synthetic distance/pace.
        for key in ('distance_m','pace'):
            peak.pop(key,None)
        result['hr_peak_context']=peak
        result['findings'].append(f"HR สูงสุดจากกราฟ {hr['max']:g} bpm ที่ {mmss(t)}"+
                                  (f" / กม. {d/1000:.2f}" if d is not None else ''))
    available=[s['label'] for s in result['series'].values() if s['seconds']]
    missing=[s['label'] for s in result['series'].values() if not s['seconds']]
    result['findings'].append('อ่านกราฟได้: '+', '.join(available))
    if missing:
        result['warnings'].append('ไม่มีค่าที่ใช้ได้: '+', '.join(missing))
    result['warnings'].append('ค่าเฉลี่ย Pace ในตารางกราฟถ่วงตามเวลา ไม่เท่ากับ elapsed/ระยะรวม; Power และ running dynamics เป็นค่าจากนาฬิกา ไม่วินิจฉัยฟอร์มหรืออาการบาดเจ็บ')
    if result.get('hr_peak_context') and result['series']['speed']['peak_s'] is not None:
        delta=hr['peak_s']-result['series']['speed']['peak_s']
        result['findings'].append(f"จุด HR สูงสุดห่างจากจุดความเร็วสูงสุด {delta:g} วินาที (เครื่องหมายบวก = HR สูงสุดเกิดทีหลัง); เป็นลำดับเวลาของข้อมูล ไม่ยืนยันสาเหตุ")
    event=result['fastest_400m']
    if event:
        for key in ('hr','cadence','stride','power','gct','vo','vr','gap'):
            m=event['metrics'][key]; whole=result['series'][key]
            if m['mean'] is not None and m['coverage_pct']>=80:
                result['findings'].append(f"ช่วง 400 m: {whole['label']} เฉลี่ย {m['mean']:g} {whole['unit']} เทียบทั้งกิจกรรม {whole['mean']:g}; เป็นการเทียบคนละความเร็ว")
    return result


def health_analysis(data, wellness, sleep):
    # Fused samples take precedence at identical metric/time, not an average
    # of duplicate devices. Different timestamps remain distinct observations.
    chosen={}
    for row in data.get('metric_samples',[]):
        if not finite(row.get('value')):
            continue
        k=(row['metric'],row['timestamp'])
        old=chosen.get(k)
        if old is None or row.get('source_scope')=='user_fused':
            chosen[k]=row
    grouped=defaultdict(list)
    for r in chosen.values():
        d=stamp(r['timestamp']); grouped[(d.date().isoformat(),r['metric'])].append((d,r))
    days={r['date']:dict(date=r['date'],daily=r.get('metrics',{}),series={},sleep=[],findings=[])
          for r in wellness['daily_snapshots'] if r.get('source')=='zepp'}
    for (day,key),rows in sorted(grouped.items()):
        out=days.setdefault(day,dict(date=day,daily={},series={},sleep=[],findings=[]))
        rows.sort(key=lambda x:x[0])
        vals=[r['value'] for _,r in rows]; bins=defaultdict(list)
        for t,r in rows:
            bins[(t.hour*60+t.minute)//30].append(r['value'])
        out['series'][key]=dict(label=HEALTH_LABELS.get(key,key),unit=rows[0][1]['unit'],
            mean=rounded(statistics.mean(vals)), min=min(vals),max=max(vals),count=len(vals),
            first=rows[0][0].isoformat(),last=rows[-1][0].isoformat(),
            bins=[[i*30,rounded(statistics.mean(bins[i])),min(bins[i]),max(bins[i]),len(bins[i])]
                  if bins[i] else [i*30,None,None,None,0] for i in range(48)])
        if key=='spo2_apnea_low':
            out['series'][key]['note']='บันทึกเฉพาะเหตุการณ์ค่าต่ำ ไม่ใช่ SpO₂ ต่อเนื่องทั้งคืนหรือการวินิจฉัย apnea'
        elif key in ('hrv','hrv_rmssd'):
            out['series'][key]['note']='ชนิดการวัดนี้แยกจาก Sleep HRV; ไม่รวมเป็นค่าเดียวกัน'
    stages=defaultdict(list)
    for s in data.get('sleep_stages',[]):
        stages[s['sleep_id']].append(s)
    for s in data['sleep_sessions']:
        a,b=stamp(s['start_time']),stamp(s['end_time']); day=b.date().isoformat()
        out=days.setdefault(day,dict(date=day,daily={},series={},sleep=[],findings=[]))
        record={k:s.get(k) for k in ('score','duration_minutes','deep_minutes','light_minutes','rem_minutes','awake_minutes','wake_count')}
        for stage in ('deep','light','rem','awake'):
            if s.get(stage+'_available') == 0:
                record[stage+'_minutes']=None
        record.update(start=a.isoformat(),end=b.isoformat(),stages=[])
        for st in sorted(stages[s['sleep_id']],key=lambda x:x['start_time']):
            sa,sb=max(a,stamp(st['start_time'])),min(b,stamp(st['end_time']))
            if sb>sa:
                record['stages'].append(dict(stage=st['stage'],start_min=(sa-a).total_seconds()/60,
                                            end_min=(sb-a).total_seconds()/60))
        out['sleep'].append(record)
    previous={}
    for day,out in sorted(days.items()):
        out['sleep'].sort(key=lambda s:s['start'])
        for key,v in out['daily'].items():
            if not finite(v.get('value')):
                continue
            old=previous.get(key)
            if old:
                v=dict(v,change=rounded(v['value']-old[1]),compared_with=old[0])
                out['daily'][key]=v
            previous[key]=(day,v['value'])
        if out['series']:
            out['findings'].append('ข้อมูลรายช่วง: '+', '.join(v['label'] for v in out['series'].values()))
        out['findings'].append('กราฟสุขภาพเป็นค่าเฉลี่ยตัวอย่างในช่วง 30 นาที ไม่ใช่ค่าเฉลี่ยถ่วงเวลาทั้งวัน; ช่องว่างคือไม่มีข้อมูล')
    return [days[day] for day in sorted(days)]


def analyze(data, wellness, sleep, activities):
    grouped={}
    for table in ('workout_samples','workout_pauses','workout_laps','workout_hr_zones','workout_splits'):
        g=defaultdict(list)
        for r in data.get(table,[]):
            g[r['workout_id']].append(r)
        grouped[table]=g
    notes={r['id']:r.get('note','') for bucket in ('long_runs','tempos_intervals','easy_runs','other_activities')
           for r in activities.get(bucket,[]) if r.get('id')}
    workouts=[]
    for w in sorted(data['workouts'],key=lambda w:w['start_time']):
        wid=w['workout_id']
        if (stamp(w['end_time'])-stamp(w['start_time'])).total_seconds()<=0:
            continue
        r=workout_analysis(w,grouped['workout_samples'][wid],data.get('workout_details',{}).get(wid,{}),
                           grouped['workout_hr_zones'][wid],grouped['workout_pauses'][wid],
                           grouped['workout_laps'][wid],grouped['workout_splits'][wid])
        r['user_note']=notes.get(r['id'],'')
        workouts.append(r)
    health=health_analysis(data,wellness,sleep)
    for h in health:
        run_m=sum(w['summary']['distance_meters'] or 0 for w in workouts
                  if w['date']==h['date'] and w['name'] in ('run','outdoor_running','trail_running','treadmill','treadmill_running'))
        daily_m=h['daily'].get('distance',{}).get('value')
        if run_m and daily_m is not None and daily_m+100<run_m:
            h['findings'].append(f'ยอดระยะรายวัน {daily_m:g} m ยังน้อยกว่ากิจกรรมวิ่ง {run_m:g} m; ข้อมูลคนละชุดยังไม่ตรงกัน ห้ามใช้สรุปว่าทั้งวันเคลื่อนไหวน้อย')
    return dict(version=1,source='ZeppBridge normalized SQLite + validated distance timeline',
                methodology='zepp_analysis.py; descriptive observations, not diagnosis or clearance',
                workouts=workouts,health=health)


def report(result):
    workouts=result['workouts']
    if not workouts:
        return '# Zepp analysis\n\nยังไม่มีกิจกรรม\n'
    r=workouts[-1]
    lines=[f"# Zepp analysis · {r['date']}",'',r['user_note'],'',
           '| กราฟ | เฉลี่ย | ต่ำสุด | สูงสุด | หน่วย | ครอบคลุมเวลา |',
           '|---|---:|---:|---:|---|---:|']
    for s in r['series'].values():
        show=lambda x:'—' if x is None else f'{x:g}'
        lines.append(f"| {s['label']} | {show(s['mean'])} | {show(s['min'])} | {show(s['max'])} | {s['unit']} | {s['coverage_pct']:g}% |")
    lines+=['']+['- '+x for x in r['findings']]+['']+['- '+x for x in r['warnings']]
    lines+=['','## ค่ารวมจากนาฬิกา','']
    lines+=['- '+k+': '+str(v) for k,v in r['summary'].items() if v is not None]
    if r['hr_zones']:
        lines+=['','| ขอบ bpm จาก Zepp | เวลา | % ของเวลาที่จัด Zone |','|---|---|---:|']
        for z in r['hr_zones']:
            label=('ต่ำกว่า ' if z['lower_bpm'] is None else str(z['lower_bpm'])+'–')+str(z['upper_bpm'])
            lines.append(f"| {label} | {mmss(z['seconds'])} | {z['pct']} |")
        lines.append(f"\nเวลา Zone ต่างจาก elapsed {r['zone_difference_s']} วินาที; ไม่เติมส่วนต่าง")
    if r['splits']:
        lines+=['','| กม. | Pace | HR เฉลี่ย | Cadence | Power |','|---|---|---:|---:|---:|']
        for s in r['splits']:
            m=s['metrics']
            lines.append(f"| {s['km_start']:g}–{s['km_end']:g} | {s['pace']} | {m['hr']['mean']} | {m['cadence']['mean']} | {m['power']['mean']} |")
    if result['health']:
        h=result['health'][-1]
        lines+=['',f"## สุขภาพ · {h['date']}",'','| ค่า | ล่าสุด | หน่วย | เปลี่ยนจาก | ผลต่าง |','|---|---:|---|---|---:|']
        for key,v in sorted(h['daily'].items()):
            lines.append(f"| {key} | {v['value']} | {v['unit']} | {v.get('compared_with','—')} | {v.get('change','—')} |")
        lines+=['','ค่ารายวันอาจยังไม่ครบ; วันที่ที่ใช้เทียบแสดงแยก ไม่ถือว่าค่าที่หายเป็นศูนย์']
        lines+=['']+['- '+x for x in h['findings']]
        lines+=['','| กราฟสุขภาพ | เฉลี่ยตัวอย่าง | ต่ำสุด | สูงสุด | หน่วย | จำนวน | ตัวอย่างล่าสุด |','|---|---:|---:|---:|---|---:|---|']
        for s in h['series'].values():
            lines.append(f"| {s['label']} | {s['mean']} | {s['min']} | {s['max']} | {s['unit']} | {s['count']} | {s['last']} |")
            if s.get('note'):
                lines.append('\n'+s['note']+'\n')
        for s in h['sleep']:
            lines.append(f"\nSleep {s['start']} → {s['end']} · {s['duration_minutes']} นาที · score {s['score']} · stages {len(s['stages'])} ช่วง")
    return '\n'.join(lines)+'\n'
