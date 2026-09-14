import copy
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import discover as d

TODAY = '2026-09-14'


def repo(number, **values):
    return {'id': number, 'full_name': f'owner/project{number}',
            'stargazers_count': 5000, 'created_at': '2026-01-01T00:00:00Z',
            'topics': ['llm'], **values}


def state_with_tasks(tasks):
    return {'schemaVersion': 1, 'candidates': {}, 'tasks': tasks, 'cycle': 1,
            'config': {'createdStart': None, 'createdEnd': None, 'topics': list(d.TOPICS), 'minStars': 0}}


class DiscoveryTests(unittest.TestCase):
    def task(self, **changes):
        return {**d.initial_tasks(TODAY)[0], **changes}

    def run_discovery(self, state, request, count=1, **kwargs):
        return d.discover(state, request, count, TODAY, pause=lambda _: None, **kwargs)

    def test_topic_and_sort_rotation_includes_small_projects(self):
        tasks = d.initial_tasks(TODAY)
        self.assertEqual({t['topic'] for t in tasks[:len(d.TOPICS)]}, set(d.TOPICS))
        self.assertEqual({t['sort'] for t in tasks}, {'stars', 'updated'})
        self.assertEqual({t['minStars'] for t in tasks}, {0, 10, 100, 1000})

    def test_full_page_resumes_after_restart_without_dropping_candidates(self):
        state = state_with_tasks([self.task()])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'queue.json'
            report = self.run_discovery(state, lambda _: {
                'total_count': 150, 'items': [repo(i) for i in range(100)]},
                persist=lambda s: d.save_state(s, path))
            self.assertEqual(report['added'], 100)
            restored = d.load_state(path)
            self.assertEqual(restored['tasks'][0]['page'], 2)
            calls = []
            def request(endpoint):
                calls.append(parse_qs(urlsplit(endpoint).query))
                return {'total_count': 150, 'items': [repo(i) for i in range(100, 150)]}
            self.run_discovery(restored, request)
            self.assertEqual(calls[0]['page'], ['2'])
            self.assertEqual(calls[0]['per_page'], ['100'])
            self.assertEqual(len(restored['candidates']), 150)
            self.assertEqual(restored['tasks'], [])

    def test_oversized_query_splits_without_skipping_boundary(self):
        task = self.task(minStars=100, maxStars=10000, page=1)
        state = state_with_tasks([task])
        report = self.run_discovery(state, lambda _: {'total_count': 2500, 'items': [repo(1)]})
        self.assertEqual(report['splits'], 1)
        left, right = state['tasks']
        self.assertEqual(left['minStars'], 100)
        self.assertEqual(right['maxStars'], 10000)
        self.assertEqual(left['maxStars'] + 1, right['minStars'])
        self.assertEqual((left['page'], right['page']), (1, 1))
        self.assertEqual(len(state['candidates']), 1)

    def test_same_star_value_splits_creation_dates(self):
        task = self.task(minStars=100, maxStars=100,
                         createdStart='2026-01-01', createdEnd='2026-01-31')
        left, right = d.split_task(task)
        self.assertEqual(left['createdStart'], task['createdStart'])
        self.assertEqual(right['createdEnd'], task['createdEnd'])
        self.assertEqual(dt.date.fromisoformat(left['createdEnd']) + dt.timedelta(days=1),
                         dt.date.fromisoformat(right['createdStart']))

    def test_unbounded_star_search_keeps_open_upper_partition(self):
        task=self.task()
        self.assertIn('stars:>=1000', d.search_query(task))
        left,right=d.split_task(task,[20000,18000])
        self.assertEqual(left['maxStars']+1,right['minStars'])
        self.assertIsNone(right['maxStars'])

    def test_zero_star_partition_and_repositories_are_not_excluded(self):
        task=self.task(minStars=0,maxStars=9)
        left,right=d.split_task(task)
        self.assertEqual(left['minStars'],0)
        self.assertEqual(left['maxStars']+1,right['minStars'])
        state=state_with_tasks([])
        self.assertTrue(d.merge_candidate(state,repo(1,stargazers_count=0),'topic:llm',TODAY))
        self.assertEqual(len(d.pending_candidates(state)),1)

    def test_unsplittable_limit_is_reported_and_never_requests_page_eleven(self):
        task = self.task(minStars=100, maxStars=100, page=10,
                         createdStart=TODAY, createdEnd=TODAY)
        state = state_with_tasks([task])
        report = self.run_discovery(state, lambda _: {
            'total_count': 1500, 'items': [repo(i) for i in range(100)]})
        self.assertEqual(report['truncated'], [d.search_query(task)])
        self.assertIn(d.search_query(task), state['coverageWarnings'])
        self.assertFalse(state['tasks'])

    def test_partial_search_retries_cursor_but_keeps_useful_results(self):
        task = self.task(page=2)
        state = state_with_tasks([task])
        report = self.run_discovery(state, lambda _: {
            'total_count': 120, 'items': [repo(1)], 'incomplete_results': True})
        self.assertEqual(state['tasks'], [task])
        self.assertEqual(len(state['candidates']), 1)
        self.assertEqual(report['errors'][0]['error'], 'incomplete_results')

    def test_failure_stops_requests_persists_cursor_and_preserves_prior_state(self):
        tasks = [self.task(), self.task(topic='rag')]
        state = state_with_tasks(copy.deepcopy(tasks))
        d.merge_candidate(state, repo(1), 'topic:llm', TODAY)
        saved = []
        calls = []
        def request(endpoint):
            calls.append(endpoint)
            raise RuntimeError('rate limit')
        report = self.run_discovery(state, request, 24, persist=lambda s: saved.append(copy.deepcopy(s)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(state['tasks'], [tasks[1], tasks[0]])
        self.assertEqual(len(saved[-1]['candidates']), 1)
        self.assertTrue(report['errors'])

    def test_renames_dedupe_by_id_preserving_review_and_discovery(self):
        state = state_with_tasks([])
        d.merge_candidate(state, repo(1), 'topic:llm', '2026-09-01')
        d.record_attempt(state, 'owner/project1', 'rejected', TODAY)
        added = d.merge_candidate(state, repo(1, full_name='new/name'), 'topic:rag', TODAY)
        self.assertFalse(added)
        candidate = state['candidates']['1']
        self.assertEqual(candidate['status'], 'rejected')
        self.assertEqual(candidate['firstDiscovered'], '2026-09-01')
        self.assertEqual(candidate['fullName'], 'new/name')
        self.assertEqual(candidate['sources'], ['topic:llm', 'topic:rag'])

    def test_forks_archived_private_and_invalid_ids_cannot_enter_queue(self):
        state = state_with_tasks([])
        for values in ({'fork': True}, {'archived': True}, {'private': True},
                       {'disabled': True}, {'id': None}, {'full_name': 'not/a/repo'}):
            self.assertFalse(d.merge_candidate(state, repo(1, **values), 'topic:llm', TODAY))
        self.assertFalse(state['candidates'])

    def test_tracked_alias_exclusions_and_retry_do_not_starve_next_candidates(self):
        state = state_with_tasks([])
        for i in range(1, 6):
            d.merge_candidate(state, repo(i), 'topic:llm', TODAY)
        d.record_attempt(state, 'owner/project2', 'retry', TODAY)
        d.record_attempt(state, 'owner/project3', 'rejected', TODAY)
        available = d.pending_candidates(state, tracked=[{'id': 1, 'fullName': 'old/name'}],
                                         excluded=['OWNER/PROJECT4'], today=TODAY)
        self.assertEqual([c['id'] for c in available], [5])
        self.assertIn(2, [c['id'] for c in d.pending_candidates(state, today='2026-09-21')])

    def test_fair_lanes_include_emerging_and_different_topics(self):
        state = state_with_tasks([])
        for i in range(10):
            d.merge_candidate(state, repo(i, stargazers_count=100000), 'topic:llm', TODAY)
        d.merge_candidate(state, repo(10, stargazers_count=50), 'topic:llm', TODAY)
        d.merge_candidate(state, repo(11, stargazers_count=2000), 'topic:rag', TODAY)
        first = d.pending_candidates(state, today=TODAY)[:3]
        self.assertTrue({10, 11} <= {c['id'] for c in first})

    def test_completed_cycle_refreshes_dates_and_retains_candidate_reviews(self):
        state = state_with_tasks([])
        d.merge_candidate(state, repo(1), 'topic:llm', TODAY)
        d.record_attempt(state, 'owner/project1', 'rejected', TODAY)
        self.run_discovery(state, lambda _: {'total_count': 0, 'items': []})
        self.assertEqual(state['cycle'], 2)
        self.assertEqual(state['candidates']['1']['status'], 'rejected')
        self.assertTrue(all(task['createdEnd'] == TODAY for task in state['tasks']))

    def test_long_cycle_includes_newly_created_repositories_without_changing_date_splits(self):
        state = state_with_tasks([self.task(createdEnd='2026-09-01'),
                                 self.task(createdEnd='2026-09-01', datePartitioned=True)])
        queries = []
        def request(endpoint):
            queries.append(parse_qs(urlsplit(endpoint).query)['q'][0])
            return {'total_count': 0, 'items': []}
        self.run_discovery(state, request, 2)
        self.assertIn('..2026-09-14', queries[0])
        self.assertIn('..2026-09-01', queries[1])


if __name__ == '__main__':
    unittest.main()
