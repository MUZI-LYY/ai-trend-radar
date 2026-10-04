import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_fast_data import build


class FastDataTests(unittest.TestCase):
    def test_bootstrap_and_archived_boards_keep_daily_order(self):
        def project(identity, growth, stale=False):
            return {'id': identity, 'fullName': f'owner/repo-{identity}',
                    'createdAt': '2026-01-01', 'stars': 100 + identity,
                    'stale': stale, 'metrics': {'daily': growth},
                    'history': [{'date': '2026-10-01', 'stars': growth or 0}],
                    'readme': 'Source text'}

        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            (data / 'snapshots').mkdir()
            metadata = {'date': '2026-10-02', 'periodEnd': '2026-10-01',
                        'completedAt': '2026-10-02T12:00:00Z',
                        'capturedAt': '2026-10-02T11:00:00Z'}
            projects = [project(1, 8), project(2, 10), project(3, 10),
                        project(4, 100, True), project(5, None)]
            latest = {**metadata, 'projects': projects}
            (data / 'latest.json').write_text(json.dumps(latest))
            (data / 'snapshots/2026-10-02.json').write_text(json.dumps(latest))
            (data / 'board-history.json').write_text(json.dumps({
                'entries': [{'date': '2026-10-01', 'capturedDate': '2026-10-02',
                             'ids': [3, 2, 1]}]}))

            build(data)
            bootstrap = json.loads((data / 'latest-bootstrap.json').read_text())
            slim = json.loads((data / 'latest-slim.json').read_text())
            boards = json.loads((data / 'snapshot-boards.json').read_text())
            detail = json.loads((data / 'project-details/1.json').read_text())

            self.assertEqual([p['id'] for p in bootstrap['projects']], [3, 2, 1])
            self.assertEqual(bootstrap['bootstrapStats']['projectCount'], 5)
            self.assertEqual(bootstrap['bootstrapStats']['positiveDaily'], 3)
            self.assertEqual([p['id'] for p in boards['snapshots'][0]['projects']], [3, 2, 1])
            self.assertEqual(len(slim['projects']), 5)
            self.assertEqual(slim['projects'][0]['readme'], '')
            self.assertEqual(detail['projects'][0]['readme'], 'Source text')


if __name__ == '__main__':
    unittest.main()
