import datetime as dt
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('scale_collector', Path(__file__).parents[1]/'scripts/collect.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
from github_metadata import batch_metadata


def node(name='org/example'):
    return {'databaseId': 1, 'name': name.split('/')[1], 'nameWithOwner': name,
            'url': 'https://github.com/'+name, 'stargazerCount': 42, 'forkCount': 3,
            'isArchived': False, 'isFork': False, 'isPrivate': False, 'isDisabled': False,
            'createdAt': '2025-01-01T00:00:00Z', 'pushedAt': '2026-01-01T00:00:00Z',
            'owner': {'login': 'org', 'avatarUrl': 'https://example.com/avatar'},
            'primaryLanguage': {'name': 'Python'}, 'licenseInfo': {'spdxId': 'MIT'},
            'defaultBranchRef': {'name': 'dev'},
            'repositoryTopics': {'nodes': [{'topic': {'name': 'llm'}}]}}


def week(day, value=1):
    date = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
    return {'week': int(date.timestamp()), 'total': value*7, 'days': [value]*7}


class ScaleCollectorTests(unittest.TestCase):
    def repo(self):
        return batch_metadata(['org/example'], request=lambda q: {'data': {'r0': node()}})['org/example']

    def old(self, dates):
        return {'readme': 'A previously sanitized README excerpt with useful installation details.',
                'readmeUrl': 'https://github.com/org/example/blob/dev/docs/README.en.md',
                'readmeSha': 'abc', 'readmeFetchedAt': dt.datetime.now(c.UTC).isoformat(),
                'fetchedAt': '2026-01-01T00:00:00Z', 'firstSeen': '2026-01-01', 'stars': 40,
                'history': [{'date': d, 'stars': 2} for d in dates]}

    def test_batch_maps_redirect_and_nullable_fields(self):
        mapped = batch_metadata(['Old/Name', 'org/deleted'], request=lambda q: {
            'data': {'r0': node('org/example'), 'r1': None}, 'errors': [{'message': 'Not found'}]})
        repo = mapped['old/name']
        self.assertEqual(repo['full_name'], 'org/example')
        self.assertEqual(repo['owner']['avatar_url'], 'https://example.com/avatar')
        self.assertEqual(repo['default_branch'], 'dev')
        self.assertEqual(repo['topics'], ['llm'])
        self.assertEqual(repo['license']['spdx_id'], 'MIT')
        self.assertNotIn('org/deleted', mapped)

    def test_failed_batch_keeps_other_batches(self):
        calls = []
        def request(query):
            calls.append(query)
            if len(calls) == 1: raise RuntimeError('temporary failure')
            return {'data': {'r0': node('org/second')}}
        result = batch_metadata(['org/first', 'org/second'], batch_size=1, request=request)
        self.assertEqual(list(result), ['org/second'])

    def test_readme_refreshes_exactly_one_slot_per_week(self):
        old = {'readme': 'cached text', 'readmeFetchedAt': '2025-01-01T00:00:00Z'}
        start = dt.datetime(2026, 9, 14, tzinfo=c.UTC)
        due = [c.should_refresh_readme('org/example', old, start+dt.timedelta(days=i)) for i in range(7)]
        self.assertEqual(sum(due), 1)
        self.assertTrue(c.should_refresh_readme('org/new', None, start))
        self.assertTrue(c.should_refresh_readme('org/new', {'readme': ''}, start))

    def test_cached_history_spans_year_boundary_with_one_request(self):
        old = self.old(['2025-12-29', '2025-12-30', '2025-12-31', '2026-01-01'])
        with patch.object(c, 'api', return_value=[week('2026-01-01', 3)]) as api:
            result = c.collect_one('org/example', old, {}, '2026-01-03', '2025-12-29', repo=self.repo())
        self.assertEqual(api.call_count, 1)
        self.assertEqual(result['metrics']['yearly'], 9)
        self.assertEqual(result['metrics']['weekly'], 15)
        self.assertEqual(result['readme'], old['readme'])
        self.assertEqual(result['readmeUrl'], old['readmeUrl'])
        self.assertEqual(result['readmeFetchedAt'], old['readmeFetchedAt'])

    def test_missing_old_history_fetches_page_two(self):
        # A normal full page ends just after Jan 1. The missing boundary is on page 2.
        recent = [week((dt.date(2026, 7, 26)-dt.timedelta(weeks=i)).isoformat()) for i in range(30)]
        old = self.old([])
        with patch.object(c, 'api', side_effect=[recent, [week('2025-12-28')]]) as api:
            result = c.collect_one('org/example', old, {}, '2026-08-01', '2026-01-01', repo=self.repo())
        self.assertEqual(api.call_count, 2)
        self.assertIsNotNone(result['metrics']['yearly'])

    def test_missing_source_day_remains_null(self):
        with patch.object(c, 'api', return_value=[week('2026-01-02')]):
            result = c.collect_one('org/example', self.old([]), {}, '2026-01-03', '2026-01-01', repo=self.repo())
        self.assertIsNone(result['metrics']['yearly'])
        self.assertEqual(result['metrics']['daily'], 1)

    def test_new_readme_has_content_and_is_not_editorially_reviewed(self):
        import base64
        text = 'This project provides useful model tooling and practical setup instructions.'
        response = {'content': base64.b64encode(text.encode()).decode(), 'sha': 'new-sha',
                    'html_url': 'https://github.com/org/example/blob/dev/README.md'}
        with patch.object(c, 'api', side_effect=[response, [week('2026-01-01')]]) as api:
            result = c.collect_one('org/example', None, {}, '2026-01-03', '2026-01-01', repo=self.repo())
        self.assertEqual(api.call_count, 2)
        self.assertEqual(result['readme'], text)
        self.assertTrue(result['readmeFetchedAt'])
        self.assertFalse(result['editorial'])
        self.assertIsNone(result['reviewedAt'])

    def test_failed_latest_page_cannot_publish_cached_values_as_fresh(self):
        with patch.object(c, 'api', side_effect=RuntimeError('unavailable')):
            result = c.collect_one('org/example', self.old(['2026-01-03']), {}, '2026-01-03', '2026-01-01', repo=self.repo())
        self.assertEqual(result['historyStatus'], 'unavailable')
        self.assertIsNone(result['metrics']['daily'])
        self.assertEqual(result['history'], [{'date': '2026-01-03', 'stars': 2}])

    def test_budget_is_reserved_before_request(self):
        with patch.object(c, 'REST_REQUEST_LIMIT', 1), patch.object(c, '_rest_requests', 0):
            c.reserve_rest_request()
            with self.assertRaises(c.RequestBudgetExceeded):c.reserve_rest_request()

    def test_large_readme_uses_raw_source_without_fabricating_content(self):
        raw = '# Features\n\nThis project provides local inference and model comparison.\n'
        with patch.object(c, 'api', side_effect=[{'encoding': 'none', 'size': 1500000}, raw, [week('2026-01-01')]]) as api:
            result = c.collect_one('org/example', None, {}, '2026-01-03', '2026-01-01', repo=self.repo())
        self.assertEqual(api.call_args_list[1].kwargs, {'raw': True})
        self.assertIn('local inference', result['readme'])
        self.assertNotIn('README 获取失败', result['warnings'])

    def test_reviewed_classification_does_not_claim_reviewed_description(self):
        with patch.object(c, 'CLASSIFICATION_OVERRIDES', {'org/example': {'category': 'visual', 'related': []}}):
            result = c.classify(self.repo(), '', {})
        self.assertEqual(result['category'], 'visual')
        self.assertFalse(result['editorial'])


if __name__ == '__main__':
    unittest.main()
