import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import collect as c
from ranking import chart_entries, period_starts
from validate_data import validate_dataset


class CollectionGuardTests(unittest.TestCase):
 def test_missing_history_is_reported_and_empty_batch_cannot_publish(self):
  valid = {'fullName': 'o/valid', 'metrics': {'daily': 0, 'weekly': 0, 'monthly': 0, 'yearly': 0}}
  unavailable = {'fullName': 'o/missing', 'metrics': dict.fromkeys(valid['metrics'])}
  self.assertEqual(c.missing_period_history([valid, unavailable]), ['o/missing'])
  with self.assertRaisesRegex(ValueError, 'No usable fresh'):
   c.missing_period_history([unavailable, {**valid, 'stale': True}])

 def test_explicit_related_including_empty_overrides_automatic(self):
  repo = {'full_name': 'owner/agent', 'name': 'agent', 'topics': ['agent', 'training'], 'description': 'agent training framework'}
  for related in ([], ['knowledge', 'coding']):
   profile = c.classify(repo, '', {'owner/agent': {'category': 'agents', 'related': related}})
   self.assertEqual(profile['related'], related)

 def test_budget_keeps_tracked_and_limits_new(self):
  previous = {f'o/r{i}': {'fullName': f'o/r{i}'} for i in range(178)}
  candidates = {**{key: row['fullName'] for key, row in previous.items()}, **{f'n/r{i}': f'n/r{i}' for i in range(20)}}
  self.assertEqual(len(c.select_candidates(previous, candidates, 180, 8)), 180)
  self.assertEqual(len(c.select_candidates(previous, candidates, 170, 8)), 178)
  self.assertEqual(len(c.select_candidates(previous, candidates, 200, 8)), 186)

 def test_failure_retains_previous_without_old_period_rank(self):
  old = {'id': 1, 'fullName': 'o/old', 'metrics': {'daily': 99}, 'fetchedAt': '2026-09-01T00:00:00Z'}
  fresh = {'id': 2, 'fullName': 'o/fresh', 'fetchedAt': '2026-09-14T00:00:00Z'}
  rows = c.retain_previous([fresh], {'o/old': old}, '2026-09-13')
  stale = next(row for row in rows if row['id'] == 1)
  self.assertTrue(stale['stale'])
  self.assertEqual(stale['metrics'], dict.fromkeys(period_starts('2026-09-13')))
  self.assertEqual(old['metrics']['daily'], 99)

 def test_redirect_duplicates_prefer_most_recent_fresh_result(self):
  older = {'id': 1, 'fullName': 'o/old', 'fetchedAt': '2026-09-13T00:00:00Z'}
  fresh = {'id': 1, 'fullName': 'o/renamed', 'fetchedAt': '2026-09-14T00:00:00Z'}
  self.assertEqual(c.retain_previous([fresh, older], {'o/old': older}, '2026-09-13'), [fresh])

 def test_renamed_candidate_keeps_original_observation_baseline(self):
  old = {'id': 1, 'fullName': 'o/old', 'fetchedAt': '2026-09-13T00:00:00Z', 'stars': 100, 'firstSeen': '2026-01-01'}
  fresh = {'id': 1, 'fullName': 'o/renamed', 'fetchedAt': '2026-09-14T00:00:00Z', 'stars': 98, 'firstSeen': '2026-09-14'}
  row = c.retain_previous([fresh], {'o/old': old}, '2026-09-13')[0]
  self.assertEqual(row['firstSeen'], '2026-01-01')
  self.assertEqual(row['netSincePrevious'], -2)
  self.assertEqual(row['netBaselineAt'], old['fetchedAt'])

 def test_source_day_uses_first_archive_across_capture_dates(self):
  def payload(capture, project):
   return {'date': capture, 'periodEnd': '2026-09-13', 'projects': [{'id': project, 'fullName': f'o/{project}', 'stars': 1, 'metrics': {'daily': 1}}]}
  entries = chart_entries([payload('2026-09-15', 2), payload('2026-09-14', 1)])
  self.assertEqual(len(entries), 1)
  self.assertEqual(entries[0]['ids'], [1])

 def test_year_start_requests_previous_year_week(self):
  end = '2026-01-01'
  earliest = min(period_starts(end).values())
  daily = {'2025-12-29': 1, '2025-12-30': 2, '2025-12-31': 3, '2026-01-01': 4}
  self.assertEqual(earliest, '2025-12-29')
  self.assertEqual(c.period_total(daily, earliest, end, '2020-01-01'), 10)

 def test_validator_catches_wrong_period_aggregate(self):
  data = {'schemaVersion': 2, 'date': '2026-09-14', 'capturedAt': '2026-09-14T00:00:00+00:00', 'completedAt': '2026-09-14T00:01:00+00:00', 'periodEnd': '2026-09-13', 'periodStarts': period_starts('2026-09-13'), 'categories': [{'id': 'agents'}], 'projects': [{'id': 1, 'fullName': 'o/a', 'stars': 1, 'forks': 0, 'url': 'https://github.com/o/a', 'category': 'agents', 'related': [], 'summary': 's', 'overview': 'o', 'readmeUrl': 'r', 'metrics': {'daily': 1, 'weekly': 1, 'monthly': 1, 'yearly': 1}, 'historyStatus': 'ok', 'createdAt': '2026-09-13T00:00:00Z', 'history': [{'date': '2026-09-13', 'stars': 1}]}]}
  self.assertEqual(validate_dataset(data), 1)
  data['projects'][0]['metrics']['weekly'] = 7
  with self.assertRaisesRegex(AssertionError, 'weekly'):
   validate_dataset(data)
