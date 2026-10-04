import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from enforce_star_floor import clean_dataset, promote_reviewed_candidates, prune_discovery
from local_backfill import connect, save_review


class StarFloorTests(unittest.TestCase):
    def test_historical_cleanup_removes_subten_projects_and_stale_counts(self):
        data = {
            'periodEnd': '2026-10-03', 'projects': [
                {'id': 1, 'fullName': 'owner/small', 'stars': 9},
                {'id': 2, 'fullName': 'owner/eligible', 'stars': 10,
                 'statsThrough': '2026-10-03', 'stale': False, 'historyStatus': 'ok',
                 'metrics': {'daily': 0, 'weekly': 0, 'monthly': 0, 'yearly': 0}},
                {'id': 3, 'fullName': 'owner/no-longer-eligible', 'stars': 15},
            ],
            'missingHistoryRepositories': ['owner/small'],
            'warnings': ['3 个已收录项目待更新或暂缺完整本期数据，后续批次继续处理；未更新指标不参榜。'],
        }
        self.assertEqual(clean_dataset(data, {3}), 2)
        self.assertEqual([p['id'] for p in data['projects']], [2])
        self.assertEqual(data['missingHistoryRepositories'], [])
        self.assertEqual(data['warnings'], [])
        self.assertIn('至少 10 Star', data['scope'])

    def test_discovery_cleanup_keeps_ten_star_boundary_and_search_progress(self):
        state = {'candidates': {
            '1': {'id': 1, 'stars': 9}, '2': {'id': 2, 'stars': 10}},
            'tasks': [{'minStars': 0, 'maxStars': 9},
                      {'minStars': 10, 'maxStars': 99, 'page': 3}],
            'config': {'minStars': 0},
        }
        self.assertEqual(prune_discovery(state), {1})
        self.assertEqual(list(state['candidates']), ['2'])
        self.assertEqual(state['tasks'], [{'minStars': 10, 'maxStars': 99, 'page': 3}])
        self.assertEqual(state['config']['minStars'], 10)

    def test_verified_ten_stars_overrides_old_search_count(self):
        state = {'candidates': {'1': {'id': 1, 'stars': 9}}}
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / 'reviews.sqlite3'
            db = connect(db_path)
            save_review(db, {'id': 1, 'fullName': 'owner/growing'}, 'admitted',
                        {'id': 1, 'stars': 10, 'historyStatus': 'ok'})
            db.close()
            self.assertEqual(promote_reviewed_candidates(state, db_path), 1)
        self.assertEqual(prune_discovery(state), set())
        self.assertEqual(state['candidates']['1']['stars'], 10)


if __name__ == '__main__':
    unittest.main()
