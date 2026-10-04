import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from build_tenure_index import cumulative_chart


class CumulativeChartTests(unittest.TestCase):
    def test_latest_partial_day_uses_only_fresh_daily_leaders(self):
        latest = {'periodEnd': '2026-10-03', 'projects': [
            {'id': 1, 'fullName': 'a/fresh', 'createdAt': '2026-01-01',
             'stars': 100, 'metrics': {'daily': 5}, 'stale': False},
            {'id': 2, 'fullName': 'b/stale', 'createdAt': '2026-01-01',
             'stars': 100, 'metrics': {'daily': None}, 'stale': True},
        ]}
        chart = cumulative_chart(latest, {'scope': 'verified', 'projects': []},
                                 {'dates': []}, {'entries': []})
        self.assertEqual(chart['end'], '2026-10-03')
        self.assertEqual(chart['entries'], [
            {'date': '2026-10-03', 'ids': [1], 'source': 'latest'}])

    def test_saved_days_override_replay_and_latest_counts_once(self):
        def project(identity, name, growth):
            return {'id': identity, 'fullName': name, 'createdAt': '2026-09-01', 'stars': 100,
                    'metrics': {'daily': growth}, 'stale': False}

        latest = {'periodEnd': '2026-10-03', 'projects': [
            project(1, 'a/first', 10), project(2, 'b/second', 5)]}
        history = {'scope': '当前收录范围回溯', 'projects': [
            {'id': 1, 'days': [{'date': '2026-09-29', 'stars': 10},
                               {'date': '2026-09-30', 'stars': 10},
                               {'date': '2026-10-01', 'stars': 10},
                               {'date': '2026-10-02', 'stars': 10}]},
            {'id': 2, 'days': [{'date': '2026-09-30', 'stars': 1},
                               {'date': '2026-10-01', 'stars': 1},
                               {'date': '2026-10-02', 'stars': 1}]}]}
        index = {'dates': ['2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02',
                           '2026-10-03', '2026-10-04']}
        saved = {'entries': [{'date': '2026-09-30', 'capturedDate': '2026-10-01',
                              'ids': [2], 'trackedRepositories': 10, 'updatedRepositories': 1},
                             {'date': '2026-10-01', 'capturedDate': '2026-10-02',
                              'ids': [2], 'trackedRepositories': 10, 'updatedRepositories': 10},
                             {'date': '2026-10-01', 'capturedDate': '2026-10-03',
                              'ids': [1], 'trackedRepositories': 10, 'updatedRepositories': 10},
                             {'date': '2026-10-03', 'capturedDate': '2026-10-04',
                              'ids': [2], 'trackedRepositories': 10, 'updatedRepositories': 10}]}

        entries = cumulative_chart(latest, history, index, saved)['entries']
        self.assertEqual([entry['date'] for entry in entries],
                         ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03'])
        self.assertEqual(entries[0]['source'], 'retrospective')
        self.assertEqual(entries[0]['ids'], [1, 2])
        self.assertEqual(entries[1]['ids'], [2])
        self.assertEqual(entries[1]['source'], 'snapshot')
        self.assertEqual(entries[3]['ids'], [1, 2])
        self.assertEqual(entries[3]['source'], 'latest')


if __name__ == '__main__':
    unittest.main()
