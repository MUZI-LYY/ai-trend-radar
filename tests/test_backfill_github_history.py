import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import backfill_github_history as job


class GithubHistoryBackfillTests(unittest.TestCase):
    def test_never_attempted_repositories_run_before_prior_failures(self):
        end = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
        tried = {'id': 1, 'fullName': 'example/tried', 'stars': 100,
                 'createdAt': end + 'T00:00:00Z', 'history': [],
                 'historyAttemptedAt': '2026-01-01T00:00:00Z'}
        fresh = {**tried, 'id': 2, 'fullName': 'example/fresh',
                 'historyAttemptedAt': None}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'github-repositories.json'
            source.write_text(json.dumps({'projects': [tried, fresh], 'pending': []}))
            metrics = dict.fromkeys(('daily', 'weekly', 'monthly', 'yearly'), 3)
            with patch.object(job, 'collect_history', return_value=(
                    'ok', metrics, [{'date': end, 'stars': 3}])) as fetch:
                job.backfill(limit=1, source=source)
            self.assertEqual('example/fresh', fetch.call_args.args[0]['full_name'])

    def test_checkpoints_verified_history_without_touching_unrelated_metadata(self):
        end = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
        missing = {'id': 1, 'fullName': 'example/missing', 'stars': 100,
                   'createdAt': end + 'T00:00:00Z', 'description': 'Original description',
                   'history': [], 'metrics': {'daily': None}, 'statsThrough': None}
        excluded = {**missing, 'id': 2, 'fullName': 'example/below-floor', 'stars': 9}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'github-repositories.json'
            source.write_text(json.dumps({'projects': [missing, excluded], 'pending': []}))
            days = [{'date': end, 'stars': 3}]
            metrics = dict.fromkeys(('daily', 'weekly', 'monthly', 'yearly'), 3)
            with patch.object(job, 'collect_history', return_value=('ok', metrics, days)) as fetch:
                self.assertEqual((1, 1), job.backfill(checkpoint=1, source=source))
            fetch.assert_called_once()
            saved = json.loads(source.read_text())['projects']
            self.assertEqual('Original description', saved[0]['description'])
            self.assertEqual(end, saved[0]['statsThrough'])
            self.assertEqual(days, saved[0]['history'])
            self.assertEqual([], saved[1]['history'])


if __name__ == '__main__':
    unittest.main()
