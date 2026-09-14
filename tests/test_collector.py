import importlib.util,datetime as dt,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('collector',Path(__file__).parents[1]/'scripts/collect.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class HistoryTests(unittest.TestCase):
 def test_excludes_unfinished_day(self):
  week=int(dt.datetime(2026,9,13,tzinfo=dt.timezone.utc).timestamp())
  self.assertEqual(c.flatten_history([{'week':week,'days':[3,4,0,0,0,0,0],'total':7}],'2026-09-13'),{'2026-09-13':3})
 def test_missing_is_not_zero(self):
  self.assertIsNone(c.period_total({'2026-09-01':1,'2026-09-03':2},'2026-09-01','2026-09-03','2025-01-01'))
 def test_created_mid_period(self):
  self.assertEqual(c.period_total({'2026-09-02':2,'2026-09-03':0},'2026-09-01','2026-09-03','2026-09-02T12:00:00Z'),2)
 def test_zero_is_valid(self):
  self.assertEqual(c.period_total({'2026-09-01':0},'2026-09-01','2026-09-01','2025-01-01'),0)
 def test_rejects_mismatched_total(self):
  with self.assertRaises(ValueError):c.flatten_history([{'week':0,'days':[1,0,0,0,0,0,0],'total':2}],'2026-01-01')
 def test_year_boundary(self):
  data={'2025-12-31':10,'2026-01-01':4};self.assertEqual(c.period_total(data,'2026-01-01','2026-01-01','2020-01-01'),4)
 def test_no_raw_html(self):
  value=c.strip_readme('<script>alert(1)</script>\n\n'+('A useful description. '*5));self.assertNotIn('<script>',value)
if __name__=='__main__':unittest.main()
