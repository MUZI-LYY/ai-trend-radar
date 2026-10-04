import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from build_tenure_index import cumulative_chart


class CumulativeChartTests(unittest.TestCase):
    def test_saved_days_override_replay_and_latest_counts_once(self):
        def project(identity, name, growth):
            return {'id': identity, 'fullName': name, 'stars': 100,
                    'metrics': {'daily': growth}, 'stale': False}

        latest = {'periodEnd': '2026-10-03', 'projects': [
            project(1, 'a/first', 10), project(2, 'b/second', 5)]}
        history = {'scope': '当前收录范围回溯', 'projects': [
            {'id': 1, 'days': [{'date': '2026-09-30', 'stars': 10},
                               {'date': '2026-10-01', 'stars': 10},
                               {'date': '2026-10-02', 'stars': 10}]},
            {'id': 2, 'days': [{'date': '2026-09-30', 'stars': 1},
                               {'date': '2026-10-01', 'stars': 1},
                               {'date': '2026-10-02', 'stars': 1}]}]}
        index = {'dates': ['2026-09-30', '2026-10-01', '2026-10-02',
                           '2026-10-03', '2026-10-04']}
        saved = {'entries': [{'date': '2026-10-01', 'capturedDate': '2026-10-02',
                              'ids': [2]},
                             {'date': '2026-10-01', 'capturedDate': '2026-10-03',
                              'ids': [1]},
                             {'date': '2026-10-03', 'capturedDate': '2026-10-04',
                              'ids': [2]}]}

        entries = cumulative_chart(latest, history, index, saved)['entries']
        self.assertEqual([entry['date'] for entry in entries],
                         ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03'])
        self.assertEqual(entries[0]['source'], 'retrospective')
        self.assertEqual(entries[1]['ids'], [2])
        self.assertEqual(entries[1]['source'], 'snapshot')
        self.assertEqual(entries[3]['ids'], [1, 2])
        self.assertEqual(entries[3]['source'], 'latest')


if __name__ == '__main__':
    unittest.main()
