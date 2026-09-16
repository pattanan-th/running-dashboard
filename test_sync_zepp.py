import unittest
from unittest.mock import patch
import tempfile
import json
from pathlib import Path
import sync_zepp as z

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
                a=z.load('activities.json')
                runs=[r for b in z.BUCKETS for r in a[b] if r.get('source')=='zepp']
                self.assertEqual(s['lifetime']['runs'],base['lifetime']['runs']+len(runs))
                self.assertEqual(len(runs),len({r['id'] for r in runs}))
                for n in z.load('sleep.json')['nights']:
                    if n.get('source')=='zepp':
                        sessions=[r for r in data['sleep_sessions'] if z.local(r['end_time']).date().isoformat()==n['d']]
                        self.assertEqual(n['duration_minutes'],max(r['duration_minutes'] for r in sessions))
                        self.assertIsNone(n['bb'])

if __name__=='__main__': unittest.main()

