import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from merge_github_history import merge


class MergeGithubHistoryTests(unittest.TestCase):
    def test_keeps_new_metadata_and_repositories_while_transferring_history(self):
        end = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
        original = {'id': 1, 'fullName': 'example/repo', 'createdAt': end + 'T00:00:00Z',
                    'stars': 20, 'description': 'old', 'history': [{'date': end, 'stars': 2}],
                    'statsThrough': end}
        updated = {**original, 'stars': 21, 'description': 'new', 'history': [],
                   'statsThrough': None}
        extra = {**updated, 'id': 2, 'fullName': 'example/extra'}
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'checkpoint.json'
            target = Path(directory) / 'target.json'
            checkpoint.write_text(json.dumps({'projects': [original]}))
            target.write_text(json.dumps({'projects': [updated, extra], 'pending': []}))
            self.assertEqual((1, 1), merge(checkpoint, target))
            projects = json.loads(target.read_text())['projects']
            self.assertEqual(2, len(projects))
            self.assertEqual(21, projects[0]['stars'])
            self.assertEqual('new', projects[0]['description'])
            self.assertEqual(original['history'], projects[0]['history'])
            self.assertEqual(end, projects[0]['statsThrough'])
            self.assertEqual([], projects[1]['history'])


if __name__ == '__main__':
    unittest.main()
