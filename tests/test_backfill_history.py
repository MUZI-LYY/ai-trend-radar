import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from backfill_history import backfill_project, first_missing_page, merge_projects, missing_dates, update_history


class HistoryBackfillTests(unittest.TestCase):
    def project(self, **updates):
        return {'id': 7, 'fullName': 'example/project', 'createdAt': '2020-01-01T00:00:00Z',
                'historyStatus': 'ok', 'history': [], **updates}

    def test_daily_update_preserves_backfilled_days_and_overlays_corrections(self):
        previous = {'projects': [{'id': 7, 'days': [{'date': '2025-01-01', 'stars': 5},
                                                  {'date': '2025-01-02', 'stars': 3}]}]}
        fresh = self.project(history=[{'date': '2025-01-02', 'stars': 4},
                                      {'date': '2025-01-03', 'stars': 8}])
        result = merge_projects(previous, [fresh], '2025-01-01', '2025-01-03')
        self.assertEqual(result['projects'][0]['days'], [{'date': '2025-01-01', 'stars': 5},
                                                        {'date': '2025-01-02', 'stars': 4},
                                                        {'date': '2025-01-03', 'stars': 8}])
        self.assertNotIn('stars', result['projects'][0])  # Never invent historical total metadata.

    def test_missing_day_stays_missing_and_before_creation_is_not_required(self):
        self.assertEqual(missing_dates({'2025-01-03': 0}, '2025-01-01', '2025-01-04',
                                       '2025-01-03T12:00:00Z'), ['2025-01-04'])

    def test_2026_backfill_does_not_truncate_existing_2025_days(self):
        previous = {'start': '2025-01-01', 'projects': [{'id': 7, 'days': [
            {'date': '2025-01-01', 'stars': 5}, {'date': '2026-01-01', 'stars': 2}]}]}
        merged = merge_projects(previous, [self.project()], '2026-01-01', '2026-01-01')
        self.assertEqual(merged['start'], '2025-01-01')
        result, requests, missing, errors = backfill_project(merged['projects'][0], '2026-01-01', '2026-01-01',
                                                            lambda _: self.fail('No missing 2026 data'))
        self.assertEqual(len(result['days']), 2)
        self.assertEqual((requests, missing, errors), (0, [], []))

    def test_missing_interval_selects_correct_newest_first_api_page(self):
        self.assertEqual(first_missing_page({}, ['2025-01-01', '2025-07-26'],
                                           dt.date(2026, 9, 14)), 3)
        self.assertIsNone(first_missing_page({}, [], dt.date(2026, 9, 14)))

    def test_complete_project_resumes_without_api_requests(self):
        def forbidden(endpoint):
            self.fail('Complete coverage should not be fetched again')
        project = self.project(days=[{'date': '2025-01-01', 'stars': 0}])
        result, count, missing, errors = backfill_project(project, '2025-01-01', '2025-01-01', forbidden)
        self.assertEqual((count, missing, errors), (0, [], []))

    def test_corrupt_week_does_not_write_daily_values(self):
        week = int(dt.datetime(2024, 12, 29, tzinfo=dt.timezone.utc).timestamp())
        project = self.project(days=[])
        result, count, missing, errors = backfill_project(project, '2025-01-01', '2025-01-01',
                   lambda _: [{'week': week, 'days': [1] * 7, 'total': 8}])
        self.assertEqual(result['days'], [])
        self.assertEqual(missing, ['2025-01-01'])
        self.assertIn('Weekly total mismatch', errors[0])

    def test_future_and_stale_values_not_published_and_index_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            projects = [self.project(history=[{'date': '2025-01-01', 'stars': 0},
                                               {'date': '2025-01-03', 'stars': 100}]),
                        self.project(id=8, stale=True, history=[{'date': '2025-01-02', 'stars': 6}])]
            result = update_history(projects, '2025-01-02', directory)
            index = json.loads((directory / 'history-index.json').read_text())
            self.assertEqual(index['dates'], ['2025-01-01'])
            self.assertEqual(result['projects'][1]['days'], [])
            self.assertIn('不是当时', index['scope'])


class HistoricalValidationTests(unittest.TestCase):
    def setUp(self):
        self.fresh = {'id': 7, 'fullName': 'example/project', 'createdAt': '2020-01-01T00:00:00Z',
                      'historyStatus': 'ok', 'history': [{'date': '2025-01-02', 'stars': 2}]}
        self.latest = {'periodEnd': '2025-01-02', 'projects': [self.fresh]}
        self.history = merge_projects({}, [self.fresh], '2025-01-01', '2025-01-02')
        self.index = {'dates': ['2025-01-02'], 'start': '2025-01-02', 'end': '2025-01-02',
                      **{key: self.history[key] for key in ('source', 'scope', 'generatedAt')}}

    def test_gaps_remain_valid_but_not_indexed(self):
        from validate_data import validate_history
        self.assertEqual(validate_history(self.history, self.index, self.latest), 1)

    def test_index_cannot_claim_unavailable_day(self):
        from validate_data import validate_history
        self.index['dates'].insert(0, '2025-01-01')
        with self.assertRaisesRegex(AssertionError, 'index dates'):
            validate_history(self.history, self.index, self.latest)

    def test_history_must_match_current_official_day(self):
        from validate_data import validate_history
        self.history['projects'][0]['days'][0]['stars'] = 3
        with self.assertRaisesRegex(AssertionError, 'differs from latest'):
            validate_history(self.history, self.index, self.latest)

    def test_future_day_cannot_enter_history(self):
        from validate_data import validate_history
        self.history['projects'][0]['days'].append({'date': '2025-01-03', 'stars': 3})
        with self.assertRaisesRegex(AssertionError, 'outside repository lifetime'):
            validate_history(self.history, self.index, self.latest)

    def test_editorial_detail_fields_survive_classification(self):
        from collect import classify
        fields = {'useCases': ['场景'], 'gettingStarted': ['开始'], 'requirements': ['环境']}
        repo = {'full_name': 'o/r', 'name': 'r', 'topics': [], 'description': ''}
        profile = classify(repo, '', {'o/r': fields})
        self.assertTrue(all(profile[key] == value for key, value in fields.items()))
        automatic = classify(repo, '', {})
        self.assertTrue(all(automatic[key] == [] for key in fields))


if __name__ == '__main__':
    unittest.main()
