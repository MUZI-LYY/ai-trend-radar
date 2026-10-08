import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from ranking import archive_ready,period_starts,daily_leaders,observed_tenure
from collect import save_daily_archive
from snapshot_io import SnapshotTooLarge, read_snapshot, snapshot_date, snapshot_paths
class RankingTests(unittest.TestCase):
 def test_partial_archive_cannot_be_frozen_as_a_daily_board(self):
  self.assertFalse(archive_ready({}))
  self.assertFalse(archive_ready({'coverage':{'trackedRepositories':100,'updatedRepositories':97}}))
  self.assertTrue(archive_ready({'coverage':{'trackedRepositories':100,'updatedRepositories':98}}))

 def test_partial_daily_capture_updates_until_first_complete_observation(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'2026-10-08.json'
   def capture(updated,end='2026-10-07'):
    return {'periodEnd':end,'coverage':{'trackedRepositories':100,'updatedRepositories':updated}}
   self.assertFalse(save_daily_archive(path,capture(10),'2026-10-08'))
   self.assertFalse(path.exists())
   self.assertTrue(save_daily_archive(path,capture(50),'2026-10-07'))
   self.assertTrue(save_daily_archive(path,capture(90),'2026-10-07'))
   self.assertFalse(save_daily_archive(path,capture(70),'2026-10-07'))
   self.assertEqual(json.loads(path.read_text())['coverage']['updatedRepositories'],90)
   self.assertTrue(save_daily_archive(path,capture(98),'2026-10-07'))
   self.assertFalse(save_daily_archive(path,capture(100),'2026-10-07'))
   self.assertEqual(json.loads(path.read_text())['coverage']['updatedRepositories'],98)

 def test_large_daily_capture_uses_git_safe_gzip_archive(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'2026-10-08.json.gz'
   capture={'periodEnd':'2026-10-07','coverage':{'trackedRepositories':100,'updatedRepositories':80}}
   self.assertTrue(save_daily_archive(path,capture,'2026-10-07'))
   self.assertEqual(path.read_bytes()[:2],b'\x1f\x8b')
   self.assertEqual(read_snapshot(path),capture)
   self.assertEqual([snapshot_date(p) for p in snapshot_paths(directory)],['2026-10-08'])

 def test_oversize_archive_is_rejected_before_it_reaches_git(self):
  with tempfile.TemporaryDirectory() as directory, patch('snapshot_io.MAX_GIT_BLOB_BYTES',10):
   path=Path(directory)/'2026-10-08.json.gz'
   capture={'periodEnd':'2026-10-07','coverage':{'trackedRepositories':100,'updatedRepositories':80}}
   with self.assertRaises(SnapshotTooLarge):save_daily_archive(path,capture,'2026-10-07')
   self.assertFalse(path.exists())

 def test_week_starts_monday(self):
  self.assertEqual(period_starts('2026-09-13')['weekly'],'2026-09-07')
  self.assertEqual(period_starts('2026-09-14')['weekly'],'2026-09-14')
 def test_week_crosses_year(self):
  self.assertEqual(period_starts('2026-01-01')['weekly'],'2025-12-29')
 def test_week_crosses_month(self):
  self.assertEqual(period_starts('2026-09-01')['weekly'],'2026-08-31')
 def test_tenure_counts_observed_days(self):
  history=[{'date':'2026-09-11','ids':[1]},{'date':'2026-09-12','ids':[1]}]
  self.assertEqual(observed_tenure(1,'2026-09-13',[1],history),{'days':3,'since':'2026-09-11'})
 def test_same_day_refresh_does_not_double_count(self):
  history=[{'date':'2026-09-12','ids':[1]},{'date':'2026-09-13','ids':[1]}]
  self.assertEqual(observed_tenure(1,'2026-09-13',[1],history)['days'],2)
 def test_cross_month_and_reentry_keep_earlier_days(self):
  history=[{'date':'2026-09-29','ids':[1]},{'date':'2026-09-30','ids':[1]},
           {'date':'2026-10-01','ids':[2]},{'date':'2026-10-02','ids':[1]}]
  self.assertEqual(observed_tenure(1,'2026-10-03',[1],history),{'days':4,'since':'2026-09-29'})
  self.assertEqual(observed_tenure(1,'2026-10-03',[2],history),{'days':3,'since':'2026-09-29'})
  self.assertEqual(observed_tenure(2,'2026-10-03',[1],history),{'days':1,'since':'2026-10-01'})
  self.assertEqual(observed_tenure(3,'2026-10-03',[1],history),{'days':0,'since':''})
 def test_global_top_30_excludes_stale_and_null(self):
  projects=[{'id':i,'fullName':f'o/r{i}','stars':100-i,'metrics':{'daily':i}} for i in range(35)]
  projects[34]['stale']=True;projects[33]['metrics']['daily']=None
  result=daily_leaders(projects)
  self.assertEqual(len(result),30);self.assertEqual(result[0],32);self.assertNotIn(34,result);self.assertNotIn(33,result)

 def test_zero_growth_does_not_enter_daily_chart(self):
  project={'id':1,'fullName':'o/zero','stars':999,'metrics':{'daily':0}}
  self.assertEqual(daily_leaders([project]),[])
