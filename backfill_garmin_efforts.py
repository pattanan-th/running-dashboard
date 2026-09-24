"""Backfill lifetime Garmin time efforts from TCX, preserving the archive.

Only time/distance pairs are cached locally. Published output contains aggregate
efforts and coverage, never TCX routes, authentication or account identifiers.
Re-running resumes cached activities without re-downloading them.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from garminconnect import Garmin
from zepp_efforts import TIMES, furthest

HERE=Path(__file__).resolve().parent
CACHE=HERE/'.garmin_effort_cache'
NS={'t':'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}


def save(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    tmp.replace(path)


def read_tcx(raw,total_m):
    root=ET.fromstring(raw)
    points=[]
    first=None
    previous=-1.0
    for p in root.findall('.//t:Trackpoint',NS):
        ts=p.findtext('t:Time',namespaces=NS)
        metres=p.findtext('t:DistanceMeters',namespaces=NS)
        if ts is None or metres is None:
            continue
        moment=datetime.fromisoformat(ts.replace('Z','+00:00'))
        if moment.tzinfo is None:
            raise ValueError('Timestamp has no timezone')
        d=float(metres)
        if not math.isfinite(d) or d<0 or d<previous:
            raise ValueError('Invalid or decreasing distance')
        if first is None:
            first=moment
        t=(moment-first).total_seconds()
        if points and t<points[-1][0]:
            raise ValueError('Decreasing time')
        if points and t==points[-1][0]:
            points[-1]=[t,d]
        else:
            points.append([t,d])
        previous=d
    if len(points)<2:
        raise ValueError('No time/distance timeline')
    if abs(points[-1][1]-total_m)>max(2,total_m*.005):
        raise ValueError('Distance timeline differs from summary')
    return points


def compute(points):
    segments=[]; segment=[]
    for p in points:
        if segment and p[0]-segment[-1][0]>15:
            segments.append(segment);segment=[]
        segment.append(p)
    if segment:
        segments.append(segment)
    efforts={}
    for label,seconds in TIMES.items():
        vals=[v for seg in segments if (v:=furthest(seg,seconds)) is not None]
        if vals and max(vals)>0:
            efforts[label]=max(vals)
    return efforts,dict(points=len(points),
        longest_continuous_seconds=max((s[-1][0]-s[0][0] for s in segments),default=0),
        gap_count=max(0,len(segments)-1))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--local-only',action='store_true')
    args=ap.parse_args()
    base=json.loads((HERE/'garmin_stats_archive.json').read_text(encoding='utf-8'))
    cutoff=max(r['d'] for r in base['runs_list'])
    CACHE.mkdir(exist_ok=True)
    index=CACHE/'index.json'
    api=None
    if args.local_only:
        activities=json.loads(index.read_text(encoding='utf-8'))
    else:
        api=Garmin()
        api.login(str(HERE/'garmin_tokens'))
        acts=api.get_activities_by_date('2020-01-01',cutoff,'running')
        activities=[dict(id='garmin:'+str(a['activityId']),activity_id=str(a['activityId']),
            date=a['startTimeLocal'][:10],name=(a.get('activityName') or 'Run')[:80],
            distance_m=a.get('distance') or 0,duration_seconds=a.get('duration'),
            elapsed_seconds=a.get('elapsedDuration')) for a in acts]
        # Match the exact set already counted in lifetime totals. No new
        # activities can silently enter rankings while missing from totals.
        expected=Counter((r['d'],r['km'],r['min']) for r in base['runs_list'])
        got=Counter((r['date'],round(r['distance_m']/1000,2),round(r['duration_seconds']/60,1))
                    for r in activities)
        if got!=expected:
            raise SystemExit('Garmin cloud list differs from archive; reconcile before publishing')
        save(index,activities)
    output=[]
    for i,a in enumerate(activities,1):
        path=CACHE/(a['activity_id']+'.json')
        if path.exists():
            cache=json.loads(path.read_text(encoding='utf-8'))
        elif args.local_only:
            cache={'error':'Not downloaded'}
        else:
            try:
                raw=api.download_activity(a['activity_id'],Garmin.ActivityDownloadFormat.TCX)
                cache={'points':read_tcx(raw,a['distance_m'])}
            except (ValueError,ET.ParseError) as exc:
                cache={'error':str(exc)}
            except Exception as exc:
                # Stop on network/auth/rate-limit errors; keep successful local
                # downloads and do not overwrite the last published archive.
                raise SystemExit('Download stopped at '+str(i)+'/'+str(len(activities))+
                                 ' ('+type(exc).__name__+'); rerun to resume') from None
            save(path,cache)
        r={k:v for k,v in a.items() if k!='activity_id'}
        if 'points' in cache:
            r['best_time_efforts'],r['coverage']=compute(cache['points'])
            r['status']='available'
        else:
            r.update(best_time_efforts={},status='unavailable',reason=cache['error'])
        output.append(r)
        if i%10==0 or i==len(activities):
            print(f'Processed {i}/{len(activities)}',flush=True)
    available=sum(r['status']=='available' for r in output)
    result=dict(meta=dict(source='Garmin TCX recorded time/distance',
        archive_cutoff=cutoff,total_runs=len(output),available_runs=available,
        unavailable_runs=len(output)-available,
        method='Rolling elapsed-time distance, linear interpolation; gaps over 15s excluded',
        windows_minutes=[s//60 for s in TIMES.values()]),runs=sorted(output,key=lambda r:(r['date'],r['id'])))
    save(HERE/'garmin_time_efforts.json',result)
    print(json.dumps(dict(available=available,total=len(output),
        rankings={k:sum(k in r['best_time_efforts'] for r in output) for k in TIMES})))

if __name__=='__main__':
    main()

