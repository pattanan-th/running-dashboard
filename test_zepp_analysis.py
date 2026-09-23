"""Boundary and integration tests for time-aligned Zepp analysis."""
import copy
import json
import math
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zepp_analysis import (source_support, clean_samples, window_stats,
    fastest_window, workout_analysis, health_analysis, analyze)
import sync_zepp as z

START = datetime(2026,9,23,10,tzinfo=timezone.utc)
def iso(sec):
    return (START+timedelta(seconds=sec)).isoformat()

def workout(seconds=100,distance=200):
    return dict(workout_id='test',workout_type='run',start_time=iso(0),end_time=iso(seconds),
                distance_meters=distance,avg_hr=140,max_hr=150,avg_cadence_spm=170)

class SeriesTests(unittest.TestCase):
    def test_upstream_intervals_do_not_extend_across_gaps_or_tail(self):
        self.assertEqual(source_support('0,100;1,101;20,102;1,103;',30),{0,1,22})
        self.assertEqual(source_support('0,100;,101;bad,102;1,103;',10),{0,1})
        self.assertEqual(source_support('0,100;0,101;1,102;',3),{0,1})

    def test_units_sentinels_duplicate_and_end_exclusion(self):
        rows=[dict(timestamp=iso(0),heart_rate=140,pace=.5,speed=2,cadence=170,
                   stride=80,altitude=75,power_watts=200,ground_contact_ms=250,
                   vertical_oscillation_mm=70,vertical_ratio_pct=255,equivalent_pace_s=480),
              dict(timestamp=iso(0),heart_rate=141,pace=.5,speed=2,cadence=170,stride=80),
              dict(timestamp=iso(1),heart_rate=math.nan),
              dict(timestamp=iso(2),heart_rate=250)]
        points,elapsed,_=clean_samples(workout(2),rows,{})
        self.assertEqual(len(points),2)
        self.assertEqual(points[0]['pace'],.5*1000/60)
        self.assertEqual(points[0]['speed'],7.2)
        self.assertEqual(points[0]['stride'],.8)
        self.assertIsNone(points[1]['hr'])
        self.assertEqual(window_stats(points,'hr',0,2)['coverage_pct'],50)
        self.assertEqual(window_stats(points,'hr',0,2)['mean'],141)

    def test_no_false_coverage_across_missing_seconds(self):
        rows=[dict(timestamp=iso(0),heart_rate=100),dict(timestamp=iso(50),heart_rate=200)]
        p,_,_=clean_samples(workout(100),rows,{})
        s=window_stats(p,'hr',0,100)
        self.assertEqual(s['seconds'],2)
        self.assertEqual(s['mean'],150)
        self.assertEqual(s['coverage_pct'],2)

    def test_fractional_interval_weights(self):
        p=[dict(t=0,dt=1,hr=100),dict(t=1,dt=1,hr=200)]
        s=window_stats(p,'hr',.5,2)
        self.assertAlmostEqual(s['mean'],166.667)
        self.assertEqual(s['seconds'],1.5)

    def test_fastest_window_plateau_and_gaps(self):
        self.assertEqual(fastest_window([[(0,0),(50,0),(100,100),(150,100),(200,200)]],100),(50,100))
        self.assertIsNone(fastest_window([[(0,0),(10,50)],[(50,100),(60,150)]],100))
        a,b=fastest_window([[(0,0),(100,600),(300,1600)]],1000)
        self.assertAlmostEqual(b-a,180)

    def test_absent_stream_is_missing_not_zero(self):
        r=workout_analysis(workout(),[],{},[],[],[],[])
        self.assertIsNone(r['series']['hr']['mean'])
        self.assertEqual(r['series']['hr']['bins'],[])
        self.assertIsNone(r['fastest_400m'])
        self.assertEqual(r['hr_zones'],[])

    def test_zone_total_does_not_fabricate_unclassified_time(self):
        zones=[dict(zone_index=0,upper_bound_bpm=110,seconds=20)]
        r=workout_analysis(workout(),[],{},zones,[],[],[])
        self.assertEqual(r['zone_seconds'],20)
        self.assertEqual(r['zone_difference_s'],80)
        self.assertEqual(r['hr_zones'][0]['pct'],100)

class HealthTests(unittest.TestCase):
    def test_local_day_fused_priority_missing_days_and_measurement_types(self):
        metrics=[
            dict(metric='hrv_rmssd',timestamp='2026-09-22T18:00:00Z',value=40,unit='ms',source_scope='device'),
            dict(metric='hrv_rmssd',timestamp='2026-09-22T18:00:00Z',value=50,unit='ms',source_scope='user_fused'),
            dict(metric='hrv',timestamp='2026-09-22T18:00:00Z',value=70,unit='ms',source_scope='device'),
        ]
        w=dict(daily_snapshots=[
            dict(date='2026-09-21',source='zepp',metrics={'sleep_hrv':dict(value=45,unit='ms')}),
            dict(date='2026-09-23',source='zepp',metrics={})])
        result=health_analysis(dict(metric_samples=metrics,sleep_sessions=[]),w,{})
        h=result[-1]
        self.assertEqual(h['date'],'2026-09-23')
        self.assertNotIn('sleep_hrv',h['daily'])
        self.assertEqual(h['series']['hrv_rmssd']['count'],1)
        self.assertEqual(h['series']['hrv_rmssd']['mean'],50)
        self.assertEqual(h['series']['hrv']['mean'],70)
        self.assertIsNone(h['series']['hrv']['bins'][0][1])
        self.assertEqual(h['series']['hrv']['bins'][2][1],70)

class RealDataTests(unittest.TestCase):
    def test_all_history_latest_units_totals_and_no_identifiers(self):
        db=Path.home()/'AppData/Local/ZeppBridge/data/zepp.db'
        if not db.exists():
            self.skipTest('Local database not available')
        d=z.read_bridge(db)
        a=analyze(d,z.load('wellness.json'),z.load('sleep.json'),z.load('activities.json'))
        latest=next(r for r in a['workouts'] if r['id']=='zepp:1790158711')
        self.assertEqual(len([s for s in latest['series'].values() if s['seconds']]),11)
        self.assertEqual(latest['series']['hr']['max'],180)
        self.assertAlmostEqual(latest['series']['hr']['mean'],latest['summary']['avg_hr'],delta=2)
        self.assertAlmostEqual(latest['series']['cadence']['mean'],latest['summary']['avg_cadence_spm'],delta=3)
        self.assertAlmostEqual(latest['series']['stride']['mean'],.71,delta=.05)
        self.assertTrue(120<latest['fastest_400m']['duration_s']<140)
        self.assertTrue(5<latest['fastest_400m']['start_km']<5.2)
        encoded=json.dumps(a,allow_nan=False)
        for forbidden in ('device_id','latitude','longitude','payload_zip','access_token','raw_record_id'):
            self.assertNotIn(forbidden,encoded)
        for r in a['workouts']:
            for s in r['series'].values():
                self.assertLessEqual(s['coverage_pct'],100)
                if s['mean'] is not None:
                    self.assertLessEqual(s['min'],s['mean'])
                    self.assertLessEqual(s['mean'],s['max'])
            for p in r['pauses']:
                self.assertLessEqual(p['end_s'],r['elapsed_s'])

if __name__=='__main__':
    unittest.main()

