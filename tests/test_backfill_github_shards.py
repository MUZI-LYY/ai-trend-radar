import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import backfill_github_shards as backfill
from collect_github import RateLimitExceeded


def project(identity, name='example/repo'):
    return {'id': identity, 'fullName': name, 'createdAt': '2025-01-01T00:00:00Z',
            'history': [], 'historyStatus': 'unavailable', 'statsThrough': None,
            'metrics': {'daily': None, 'weekly': None, 'monthly': None, 'yearly': None},
            'warnings': ['Star 历史暂不可用'], 'description': 'Preserve metadata'}


class GithubHistoryBackfillTests(unittest.TestCase):
    def test_page_checkpoint_resumes_and_missing_days_never_become_zero(self):
        first = dt.date(2024, 9, 1)
        weeks = [{'week': int(dt.datetime.combine(first + dt.timedelta(weeks=n),
                  dt.time(), dt.timezone.utc).timestamp()), 'total': 7, 'days': [1] * 7}
                 for n in range(60)]
        weeks.reverse()
        seen = []
        paused = False

        def api(endpoint):
            nonlocal paused
            page = int(endpoint.split('page=')[-1])
            seen.append(page)
            if page == 2 and not paused:
                paused = True
                raise RateLimitExceeded('quota')
            return weeks[(page - 1) * 30:page * 30]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            item = project(7)
            with self.assertRaises(RateLimitExceeded):
                backfill.collect_one(item, '2025-01-01', '2025-10-25', output, api,
                                     today=dt.date(2025, 10, 26))
            checkpoint = json.loads((output / '7.json').read_text())
            self.assertEqual(2, checkpoint['nextPage'])
            self.assertFalse(checkpoint['complete'])
            self.assertNotIn('2025-01-01', {day['date'] for day in checkpoint['days']})

            calls, missing, exhausted = backfill.collect_one(
                item, '2025-01-01', '2025-10-25', output, api,
                today=dt.date(2025, 10, 26))
            self.assertEqual([1, 2, 2], seen)
            self.assertEqual(1, calls)
            self.assertEqual([], missing)
            self.assertFalse(exhausted)
            self.assertTrue(json.loads((output / '7.json').read_text())['complete'])
            self.assertEqual((0, [], False), backfill.collect_one(
                item, '2025-01-01', '2025-10-25', output, api,
                today=dt.date(2025, 10, 26)))

    def test_stable_id_shards_and_merge_preserve_current_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, shard = root / 'source.json', root / 'merged.json', root / 'shard'
            source.write_text(json.dumps({'schemaVersion': 1, 'projects': [project(7), project(8)],
                                          'pending': [], 'updatedAt': '2025-01-03T00:00:00Z'}))
            week = {'week': int(dt.datetime(2024, 12, 29, tzinfo=dt.timezone.utc).timestamp()),
                    'total': 2, 'days': [0, 0, 0, 1, 1, 0, 0]}
            calls = []

            def api(endpoint):
                calls.append(endpoint)
                return [week]

            report = backfill.collect_shard(source, shard, '2025-01-01', '2025-01-02',
                                            shard_index=1, shard_count=2, api_get=api,
                                            today=dt.date(2025, 1, 3))
            self.assertEqual(1, report['projects'])
            self.assertEqual(1, report['complete'])
            self.assertEqual(1, len(calls))
            self.assertTrue((shard / '7.json').exists())
            self.assertFalse((shard / '8.json').exists())
            merged = backfill.merge(source, output, [shard])
            self.assertEqual(1, merged['repositoriesPatched'])
            self.assertEqual([], json.loads(source.read_text())['projects'][0]['history'])
            rows = {p['id']: p for p in json.loads(output.read_text())['projects']}
            self.assertEqual('Preserve metadata', rows[7]['description'])
            self.assertEqual(2, rows[7]['metrics']['yearly'])
            self.assertEqual(1, rows[7]['metrics']['daily'])
            self.assertEqual([], rows[8]['history'])

    def test_partial_merge_leaves_missing_metric_null_and_keeps_newer_days(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, shard = root / 'source.json', root / 'merged.json', root / 'shard'
            shard.mkdir()
            item = project(7)
            item['history'] = [{'date': '2025-01-02', 'stars': 3}]
            source.write_text(json.dumps({'schemaVersion': 1, 'projects': [item]}))
            patch = {'schemaVersion': 1, 'id': 7, 'start': '2025-01-01', 'end': '2025-01-03',
                     'days': [{'date': '2025-01-02', 'stars': 99},
                              {'date': '2025-01-03', 'stars': 2}]}
            (shard / '7.json').write_text(json.dumps(patch))
            backfill.merge(source, output, [shard])
            saved = json.loads(output.read_text())['projects'][0]
            self.assertEqual([{'date': '2025-01-02', 'stars': 3},
                              {'date': '2025-01-03', 'stars': 2}], saved['history'])
            self.assertIsNone(saved['metrics']['yearly'])
            self.assertEqual(2, saved['metrics']['daily'])


if __name__ == '__main__':
    unittest.main()
