import json
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from promote_backfill import eligible_project


class PromoteBackfillTests(unittest.TestCase):
    def test_only_verified_matching_source_data_can_be_published(self):
        project = {
            'id': 42, 'stars': 10, 'historyStatus': 'ok',
            'statsThrough': '2026-10-03', 'createdAt': '2026-10-03T00:00:00Z',
            'history': [{'date': '2026-10-03', 'stars': 2}],
            'metrics': {'daily': 2, 'weekly': 2, 'monthly': 2, 'yearly': 2},
        }

        def packed(value):
            return zlib.compress(json.dumps(value).encode())

        self.assertEqual(eligible_project(42, packed(project), '2026-10-03'), project)
        self.assertIsNone(eligible_project(43, packed(project), '2026-10-03'))
        self.assertIsNone(eligible_project(42, packed(project), '2026-10-04'))
        self.assertIsNone(eligible_project(42, packed({**project, 'stars': 9}), '2026-10-03'))
        bad = {**project, 'metrics': {**project['metrics'], 'daily': 3}}
        self.assertIsNone(eligible_project(42, packed(bad), '2026-10-03'))


if __name__ == '__main__':
    unittest.main()
