import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compact_snapshot import compact, verify
from ranking import daily_leaders


class CompactSnapshotTests(unittest.TestCase):
    def test_daily_order_and_observations_survive_compaction(self):
        projects = [
            {'id': 1, 'fullName': 'o/one', 'stars': 10, 'createdAt': '2026-01-01',
             'stale': False, 'metrics': {'daily': 3}, 'history': [{'date': '2026-10-03', 'stars': 3}],
             'readme': 'source text', 'summary': 'reviewed description'},
            {'id': 2, 'fullName': 'o/two', 'stars': 20, 'createdAt': '2026-01-01',
             'stale': False, 'metrics': {'daily': 4}, 'history': [{'date': '2026-10-03', 'stars': 4}],
             'readme': 'other source text', 'summary': 'another description'},
        ]
        original = {'date': '2026-10-04', 'periodEnd': '2026-10-03', 'projects': projects}
        reduced = compact(original)
        self.assertEqual(verify(original, reduced), 2)
        self.assertEqual(daily_leaders(reduced['projects']), daily_leaders(original['projects']))
        self.assertEqual(reduced['projects'][0]['summary'], 'reviewed description')
        self.assertEqual(reduced['projects'][0]['history'], [])
        self.assertNotIn('readme', reduced['projects'][0])


if __name__ == '__main__':
    unittest.main()
