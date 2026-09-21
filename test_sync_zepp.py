import unittest
from unittest.mock import patch
import tempfile
import json
from pathlib import Path
import sync_zepp as z

class EffortTests(unittest.TestCase):
    def test_time_efforts_rolling_and_interpolation(self):
        from zepp_efforts import furthest
        points = [(0,0),(100,100),(150,400),(250,500)]
        self.assertAlmostEqual(furthest(points,100),350)
        self.assertEqual(furthest(points,250),500)
        self.assertIsNone(furthest(points,251))
        self.assertEqual(furthest([(0,0),(50,100),(100,100),(150,200)],150),200)

    def test_time_efforts_skip_gaps(self):
        from zepp_efforts import time_efforts
        result = time_efforts({'currentDistance':'0,0;150,100000;150,200000;'},
                              {'distance_meters':2000,'elapsed_seconds':300})
        self.assertEqual(result,{})

    def test_rolling_crosses_lap_boundary(self):
        from zepp_efforts import fastest
        self.assertEqual(fastest([(0,0),(300,500),(400,1000),(500,1500),(800,2000)],1000),200)
        self.assertIsNone(fastest([(0,0),(300,999)],1000))

    def test_fractional_finish_and_pauses(self):
        from zepp_efforts import fastest
        self.assertAlmostEqual(fastest([(0,0),(100,600),(300,1600)],1000),180)
        self.assertEqual(fastest([(0,0),(50,0),(100,500),(150,500),(200,1000)],1000),150)
        self.assertEqual(fastest([(0,0),(100,1000),(150,1000)],1000),100)

    def test_validation_and_gaps(self):
        from zepp_efforts import distance_segments
        with self.assertRaises(ValueError): distance_segments('0,0;1,100;1,50;',1,2)
        with self.assertRaises(ValueError): distance_segments('0,0;1,100;',1000,1)
        with self.assertRaises(ValueError): distance_segments('0,0;1,nan;',1,1)
        self.assertEqual(len(distance_segments('0,0;1,100;50,200;1,300;',3,52)),2)
        self.assertEqual(distance_segments('0,0;1,100;0,110;1,200;',2,2),[[(0,0),(1,1.1),(2,2)]])

class ImportTests(unittest.TestCase):
    def test_timezone_and_duration(self):
        self.assertEqual(z.local('2026-09-11T22:46:48+00:00').date().isoformat(),'2026-09-12')
        self.assertEqual(z.duration(None),'--')
        self.assertEqual(z.duration(0),'0m')
        self.assertEqual(z.duration(487),'8h 7m')

    def test_real_import_is_idempotent_and_preserves_archive(self):
        db=Path.home()/'AppData/Local/ZeppBridge/data/zepp.db'
        if not db.exists(): self.skipTest("Local ZeppBridge database not available")
        data=z.read_bridge(db)
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            for name in ['activities.json','sleep.json','wellness.json','garmin_stats_archive.json']:
                (dest/name).write_bytes((z.HERE/name).read_bytes())
            with patch.object(z,'HERE',dest):
                z.import_data(data)
                files=['activities.json','sleep.json','wellness.json','stats.json']
                first={n:(dest/n).read_bytes() for n in files}
                z.import_data(data)
                self.assertEqual(first,{n:(dest/n).read_bytes() for n in files})
                s=z.load('stats.json'); base=z.load('garmin_stats_archive.json')
                self.assertTrue(all(r in s['runs_list'] for r in base['runs_list']))
                for label in z.DISTANCES:
                    ranks=s['rankings'][label]
                    self.assertEqual(sum(e.get('source')=='garmin' for e in ranks),len(base['rankings'].get(label,[])))
                self.assertGreater(sum(e.get('source')=='zepp' for e in s['rankings']['1 km']),0)
                a=z.load('activities.json')
                runs=[r for b in z.BUCKETS for r in a[b] if r.get('source')=='zepp']
                self.assertEqual(s['lifetime']['runs'],base['lifetime']['runs']+len(runs))
                self.assertEqual(len(runs),len({r['id'] for r in runs}))
                # A partial cloud refresh must retain historical metrics, then
                # replace the cached value when the metric returns next sync.
                health=z.load('wellness.json')
                day=next(r for r in health['daily_snapshots'] if r.get('source')=='zepp')
                day['metrics']['retention_test']={'value':12,'unit':'test'}
                z.save('wellness.json',health)
                z.import_data(data)
                cached=next(r for r in z.load('wellness.json')['daily_snapshots'] if r['date']==day['date'])
                self.assertEqual(cached['metrics']['retention_test'],{'value':12,'unit':'test','retained_from_previous_sync':True})
                for n in z.load('sleep.json')['nights']:

                    if n.get('source')=='zepp':
                        sessions=[r for r in data['sleep_sessions'] if z.local(r['end_time']).date().isoformat()==n['d']]
                        self.assertEqual(n['duration_minutes'],max(r['duration_minutes'] for r in sessions))
                        self.assertIsNone(n['bb'])

if __name__=='__main__': unittest.main()

