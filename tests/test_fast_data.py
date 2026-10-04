import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_fast_data import build, publishable_dataset


class FastDataTests(unittest.TestCase):
    def test_archived_bundle_keeps_only_covered_daily_charts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'snapshots').mkdir()
            project = {'id': 1, 'fullName': 'o/p1', 'createdAt': '2026-01-01',
                       'stars': 100, 'metrics': {'daily': 8}, 'stale': False,
                       'history': [{'date': '2026-10-02', 'stars': 8}], 'readme': 'Source'}
            latest = {'date': '2026-10-03', 'periodEnd': '2026-10-02',
                      'completedAt': 'v1', 'projects': [project]}
            (root / 'latest.json').write_text(json.dumps(latest))
            for captured, day in [('2026-10-02', '2026-10-01'),
                                  ('2026-10-03', '2026-10-02')]:
                (root / 'snapshots' / f'{captured}.json').write_text(json.dumps({
                    **latest, 'date': captured, 'periodEnd': day}))
            (root / 'board-history.json').write_text(json.dumps({'entries': [
                {'date': '2026-10-01', 'capturedDate': '2026-10-02', 'ids': [1],
                 'trackedRepositories': 100, 'updatedRepositories': 100},
                {'date': '2026-10-02', 'capturedDate': '2026-10-03', 'ids': [1],
                 'trackedRepositories': 100, 'updatedRepositories': 30},
            ]}))
            build(root)
            bundle = json.loads((root / 'snapshot-boards.json').read_text())
            self.assertEqual(bundle['completedAt'], 'v1')
            self.assertEqual([board['date'] for board in bundle['snapshots']], ['2026-10-02'])
            self.assertEqual([p['id'] for p in bundle['snapshots'][0]['projects']], [1])
            self.assertEqual(bundle['snapshots'][0]['projects'][0]['history'], [])

    def test_newest_well_covered_day_skips_partly_collected_intermediate_day(self):
        projects = []
        for i in range(10):
            history = [{'date': '2026-10-01', 'stars': i + 1}]
            if i < 9:
                history.append({'date': '2026-10-02', 'stars': i + 2})
            if i < 2:
                history.append({'date': '2026-10-03', 'stars': i + 3})
            projects.append({'id': i, 'fullName': f'o/p{i}', 'createdAt': '2026-10-01',
                             'stars': i, 'metrics': {}, 'history': history,
                             'historyStatus': 'ok', 'statsThrough': '2026-10-03'})
        result = publishable_dataset({'periodEnd': '2026-10-03', 'projects': projects})
        self.assertEqual(result['periodEnd'], '2026-10-01')
        self.assertEqual(result['pendingDayCoverage'], 2)
        self.assertEqual(result['pendingDayTotal'], 10)
        self.assertEqual(result['coverage']['updatedRepositories'], 10)
        self.assertTrue(all(p['statsThrough'] == '2026-10-01' for p in result['projects']))

    def test_incomplete_new_day_keeps_last_covered_daily_board(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = []
            for i in range(10):
                history = [{'date': '2026-10-02', 'stars': i + 1}] if i < 8 else []
                if i < 2:
                    history.append({'date': '2026-10-03', 'stars': 1})
                projects.append({'id': i, 'fullName': f'o/p{i}', 'createdAt': '2026-10-01',
                                 'stars': i, 'metrics': {'daily': 1 if i < 2 else None},
                                 'history': history, 'historyStatus': 'ok', 'readme': ''})
            (root / 'latest.json').write_text(json.dumps({
                'completedAt': 'v1', 'periodEnd': '2026-10-03', 'projects': projects,
            }))
            build(root)
            bootstrap = json.loads((root / 'latest-bootstrap.json').read_text())
            self.assertEqual(bootstrap['periodEnd'], '2026-10-02')
            self.assertEqual(bootstrap['pendingDay'], '2026-10-03')
            self.assertEqual(bootstrap['pendingDayCoverage'], 2)
            self.assertEqual([p['id'] for p in bootstrap['projects']], list(range(7, -1, -1)))

    def test_list_shards_grow_without_enlarging_each_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = [{'id': i, 'fullName': f'o/p{i}', 'createdAt': '2026-10-03', 'stars': i,
                         'metrics': {'daily': i}, 'history': [], 'readme': ''}
                        for i in range(501)]
            (root / 'latest.json').write_text(json.dumps({'completedAt': 'v1', 'periodEnd': '2026-10-03', 'projects': projects}))
            build(root)
            bootstrap = json.loads((root / 'latest-bootstrap.json').read_text())
            self.assertEqual(bootstrap['listShardCount'], 3)
            self.assertEqual([len(json.loads((root / 'latest-list' / f'{i}.json').read_text())['projects'])
                              for i in range(3)], [250, 250, 1])

    def test_bootstrap_and_shards_preserve_full_ranking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projects = [{
                'id': i, 'fullName': f'owner/repo-{i:02}', 'createdAt': '2026-10-03', 'stars': 100 + i,
                'metrics': {'daily': i, 'weekly': i, 'monthly': i, 'yearly': i},
                'history': [{'date': f'2026-09-{day:02}', 'stars': day} for day in range(1, 34)],
                'readme': '\n\n'.join(f'paragraph {n}' for n in range(15)),
                'overview': f'Overview {i}',
            } for i in range(35)]
            (root / 'latest.json').write_text(json.dumps({'completedAt': 'v1', 'periodEnd': '2026-10-03', 'projects': projects}))
            build(root)
            bootstrap = json.loads((root / 'latest-bootstrap.json').read_text())
            self.assertEqual([p['id'] for p in bootstrap['projects']], list(range(34, 4, -1)))
            self.assertEqual(bootstrap['bootstrapStats']['projectCount'], 35)
            self.assertEqual(bootstrap['bootstrapStats']['positiveDaily'], 34)
            self.assertFalse(bootstrap['listComplete'])
            rows = [project for i in range(bootstrap['listShardCount'])
                    for project in json.loads((root / 'latest-list' / f'{i}.json').read_text())['projects']]
            self.assertEqual({p['id'] for p in rows}, set(range(35)))
            self.assertTrue(all('readme' not in p and len(p['history']) == 32 for p in rows))
            details = [project for i in range(bootstrap['detailShardCount'])
                       for project in json.loads((root / 'project-details' / f'{i}.json').read_text())]
            self.assertEqual({p['id'] for p in details}, set(range(35)))
            self.assertEqual(len(details[0]['readme'].split('\n\n')), 12)


if __name__ == '__main__':
    unittest.main()
