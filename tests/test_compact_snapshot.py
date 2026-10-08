import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compact_snapshot import HISTORY_DAYS, compact, verify
from compact_dist import compact_dist
from pack_history import pack as pack_history
from ranking import daily_leaders
from snapshot_io import read_snapshot, write_snapshot


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
        self.assertEqual(reduced['projects'][0]['history'], projects[0]['history'])
        self.assertEqual(reduced['projects'][0]['readme'], 'source text')

    def test_readme_is_removed_only_when_current_profile_can_restore_it(self):
        historical = {'projects': [
            {'id': 1, 'editorial': False, 'readme': 'historical source'},
            {'id': 2, 'editorial': True, 'readme': 'reviewed source'},
            {'id': 3, 'editorial': False, 'readme': 'removed project source'},
        ]}
        latest = {'projects': [
            {'id': 1, 'editorial': False, 'readme': 'current source'},
            {'id': 2, 'editorial': False, 'readme': 'unreviewed source'},
        ]}
        reduced = compact(historical, latest)
        self.assertNotIn('readme', reduced['projects'][0])
        self.assertEqual(reduced['projects'][1]['readme'], 'reviewed source')
        self.assertEqual(reduced['projects'][2]['readme'], 'removed project source')
        self.assertEqual(verify(historical, reduced, latest), 3)

    def test_visible_history_spans_survive_compaction(self):
        history = [{'date': str(index), 'stars': index} for index in range(400)]
        original = {'projects': [{'id': 1, 'history': history, 'readme': 'source text'}]}
        reduced = compact(original)
        for span in (14, 30, 90, 365):
            self.assertEqual(reduced['projects'][0]['history'][-span:], history[-span:])
        self.assertEqual(len(reduced['projects'][0]['history']), HISTORY_DAYS)

    def test_only_deployment_copy_is_compacted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / 'data/snapshots/2026-10-04.json.gz'
            snapshot.parent.mkdir(parents=True)
            data = {'date': '2026-10-04', 'periodEnd': '2026-10-03',
                    'capturedAt': '2026-10-04T00:00:00Z', 'projects': [
                        {'id': 1, 'fullName': 'o/r', 'stars': 5, 'metrics': {'daily': 2},
                         'history': [{'date': '2026-10-03', 'stars': 2}], 'readme': 'large text'}]}
            write_snapshot(snapshot, data)
            (root / 'data/latest.json').write_text(json.dumps({'projects': [
                {'id': 1, 'editorial': False, 'readme': 'current source'}]}))
            history_path = root / 'data/history.json'
            history_path.write_text(json.dumps({'projects': [{'id': 1, 'days': data['projects'][0]['history']}]}))
            pack_history(history_path, root / 'data/history.json.gz', root / 'data/history-pack.json')
            (root / 'data/latest-bootstrap.json').write_text('{}')
            (root / 'data/latest-list').mkdir()
            (root / 'data/latest-list/0.json').write_text('{}')
            result = compact_dist(root)
            self.assertEqual(result['snapshots'], 1)
            project = read_snapshot(snapshot)['projects'][0]
            self.assertEqual(project['history'], data['projects'][0]['history'])
            self.assertNotIn('readme', project)
            self.assertFalse(history_path.exists())
            self.assertFalse((root / 'data/latest.json').exists())


if __name__ == '__main__':
    unittest.main()
