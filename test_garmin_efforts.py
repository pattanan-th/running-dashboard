import copy
import unittest
from backfill_garmin_efforts import read_tcx,compute
from sync_zepp import merge_stats,load

def tcx(records):
    rows=''.join(f'<Trackpoint><Time>{t}</Time><DistanceMeters>{d}</DistanceMeters></Trackpoint>' for t,d in records)
    return ('<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Activities><Activity><Lap><Track>'+rows+'</Track></Lap></Activity></Activities></TrainingCenterDatabase>').encode()

class GarminEffortTests(unittest.TestCase):
    def test_tcx_units_time_and_duplicate_timestamp(self):
        raw=tcx([('2026-01-01T00:00:00Z',0),('2026-01-01T00:00:00Z',1),
                 ('2026-01-01T00:00:10Z',21)])
        self.assertEqual(read_tcx(raw,21),[[0,1],[10,21]])

    def test_reject_corruption_and_wrong_distance(self):
        with self.assertRaises(ValueError):
            read_tcx(tcx([('2026-01-01T00:00:00Z',10),('2026-01-01T00:00:10Z',9)]),9)
        with self.assertRaises(ValueError):
            read_tcx(tcx([('2026-01-01T00:00:00Z',0),('2026-01-01T00:00:10Z',21)]),200)

    def test_long_windows_and_missing_pause_data(self):
        points=[[t,t*2] for t in range(0,7201,10)]
        e,c=compute(points)
        self.assertEqual(e['90 min'],10800)
        self.assertEqual(e['120 min'],14400)
        self.assertEqual(c['gap_count'],0)
        e,c=compute(points[:300]+points[400:])
        self.assertNotIn('90 min',e)
        self.assertNotIn('120 min',e)
        self.assertEqual(c['gap_count'],1)

    def test_merge_keeps_totals_archive_and_sources_without_duplicates(self):
        base=load('garmin_stats_archive.json')
        before=copy.deepcopy(base)
        z=dict(id='zepp:test',date='2026-09-23',dist=2,duration_seconds=600,
               calories=10,ascent=0,pace='5:00',name='Run',
               best_time_efforts={'5 min':1000})
        g=dict(meta={'total_runs':143,'available_runs':1},
               runs=[dict(id='garmin:test',date='2026-01-01',name='Old run',
                          best_time_efforts={'5 min':1500})])
        first=merge_stats(base,[z],g);second=merge_stats(base,[z],g)
        self.assertEqual(first,second)
        self.assertEqual(base,before)
        self.assertEqual(first['lifetime']['runs'],base['lifetime']['runs']+1)
        self.assertEqual([r['source'] for r in first['time_rankings']['5 min']],['garmin','zepp'])
        self.assertEqual(len(first['time_rankings']['5 min']),2)

if __name__=='__main__':
    unittest.main()

