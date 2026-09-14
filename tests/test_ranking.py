import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from ranking import period_starts,daily_leaders,observed_tenure
class RankingTests(unittest.TestCase):
 def test_week_starts_monday(self):
  self.assertEqual(period_starts('2026-09-13')['weekly'],'2026-09-07')
  self.assertEqual(period_starts('2026-09-14')['weekly'],'2026-09-14')
 def test_week_crosses_year(self):
  self.assertEqual(period_starts('2026-01-01')['weekly'],'2025-12-29')
 def test_week_crosses_month(self):
  self.assertEqual(period_starts('2026-09-01')['weekly'],'2026-08-31')
 def test_tenure_counts_consecutive_observed_days(self):
  history=[{'date':'2026-09-11','ids':[1]},{'date':'2026-09-12','ids':[1]}]
  self.assertEqual(observed_tenure(1,'2026-09-13',[1],history),{'days':3,'since':'2026-09-11'})
 def test_same_day_refresh_does_not_double_count(self):
  history=[{'date':'2026-09-12','ids':[1]},{'date':'2026-09-13','ids':[1]}]
  self.assertEqual(observed_tenure(1,'2026-09-13',[1],history)['days'],2)
 def test_gap_or_leaving_chart_restarts(self):
  for history in [[{'date':'2026-09-11','ids':[1]}],[{'date':'2026-09-12','ids':[2]}]]:
   self.assertEqual(observed_tenure(1,'2026-09-13',[1],history)['days'],1)
  self.assertIsNone(observed_tenure(1,'2026-09-13',[2],[]))
 def test_global_top_30_excludes_stale_and_null(self):
  projects=[{'id':i,'fullName':f'o/r{i}','stars':100-i,'metrics':{'daily':i}} for i in range(35)]
  projects[34]['stale']=True;projects[33]['metrics']['daily']=None
  result=daily_leaders(projects)
  self.assertEqual(len(result),30);self.assertEqual(result[0],32);self.assertNotIn(34,result);self.assertNotIn(33,result)

 def test_zero_growth_does_not_enter_daily_chart(self):
  project={'id':1,'fullName':'o/zero','stars':999,'metrics':{'daily':0}}
  self.assertEqual(daily_leaders([project]),[])
