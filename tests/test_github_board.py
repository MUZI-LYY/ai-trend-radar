import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_github as github
from build_github_data import ROOT, build, category, localized_profile
from collect import period_total
from collect_github import RateBudget, RateLimitExceeded, collect_history, needs_history, project_from_repo, search_candidates, select_work
from pack_history import unpack as unpack_history
from ranking import period_starts
from validate_data import validate_dataset


class GithubBoardTests(unittest.TestCase):
    def test_hourly_selection_covers_large_board_and_reserves_new_slots(self):
        end = '2026-10-03'
        projects = {identity: {'id': identity, 'fullName': f'owner/repo-{identity:04}',
                               'createdAt': '2025-01-01T00:00:00Z',
                               'fetchedAt': f'2026-10-02T{identity % 24:02}:00:00+00:00',
                               'statsThrough': '2026-10-02', 'metrics': {}, 'history': []}
                    for identity in range(1, 5078)}
        candidates = {identity: {'id': identity, 'full_name': f'new/repo-{identity}',
                                 'stargazers_count': identity}
                      for identity in range(6000, 6040)}
        selected = select_work(projects, candidates, end, 260, 20)
        self.assertEqual(260, len(selected))
        self.assertEqual(240, sum(kind == 'refresh' for kind, _ in selected))
        self.assertEqual(20, sum(kind == 'new' for kind, _ in selected))
        self.assertEqual(6039, selected[240][1]['id'])
        self.assertGreaterEqual(240 * 24, len(projects))
        # Failed attempts rotate behind untouched projects on the next run.
        first = selected[0][1]
        projects[first['id']] = {**first, 'lastAttemptAt': '2026-10-04T00:00:00+00:00'}
        self.assertNotEqual(first['id'], select_work(projects, {}, end, 260, 20)[0][1]['id'])
        self.assertEqual(260, len(select_work(projects, {}, end, 260, 20)))

    def test_hourly_collection_saves_completed_work_at_time_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'github-repositories.json'
            old = [{'id': identity, 'fullName': f'owner/repo-{identity}',
                    'createdAt': '2025-01-01T00:00:00Z', 'fetchedAt': '2026-10-01T00:00:00+00:00',
                    'stars': 100, 'statsThrough': None, 'metrics': {}, 'history': []}
                   for identity in (1, 2)]
            ledger.write_text(json.dumps({'projects': old, 'pending': [], 'updatedAt': old[0]['fetchedAt']}))
            metadata = {p['fullName'].lower(): {'id': p['id'], 'full_name': p['fullName'],
                                                'created_at': p['createdAt'], 'pushed_at': None}
                        for p in old}

            def refreshed(repo, previous, end):
                return {**previous, 'fetchedAt': '2026-10-04T01:00:00+00:00',
                        'statsThrough': end, 'historyStatus': 'ok', 'metrics': {'daily': 1},
                        'history': [{'date': end, 'stars': 1}]}

            with patch.object(github, 'EXTRAS', ledger), \
                 patch.object(github, 'batch_metadata', return_value=metadata), \
                 patch.object(github, 'project_from_repo', side_effect=refreshed), \
                 patch.object(github.time, 'monotonic', side_effect=[0, 0, 601]):
                github.collect(limit=2, pages=0, discover=False, new_limit=0, max_seconds=600)
            saved = {p['id']: p for p in json.loads(ledger.read_text())['projects']}
            self.assertIsNotNone(saved[1]['statsThrough'])
            self.assertIsNone(saved[2]['statsThrough'])

    def test_new_candidates_wait_for_complete_history_before_admission(self):
        end = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
        existing = {'id': 1, 'fullName': 'owner/existing', 'createdAt': end + 'T00:00:00Z',
                    'fetchedAt': '2026-10-04T00:00:00+00:00', 'stars': 100,
                    'statsThrough': end, 'historyStatus': 'ok',
                    'metrics': {period: 1 for period in period_starts(end)},
                    'history': [{'date': end, 'stars': 1}]}
        candidates = [{'id': identity, 'full_name': f'owner/new-{identity}',
                       'stargazers_count': stars, 'created_at': end + 'T00:00:00Z',
                       'pushed_at': end + 'T00:00:00Z'}
                      for identity, stars in ((2, 300), (3, 200), (4, 100))]

        def collected(repo, previous, date):
            self.assertIsNone(previous)
            complete = repo['id'] == 2
            return {'id': repo['id'], 'fullName': repo['full_name'],
                    'createdAt': repo['created_at'], 'fetchedAt': '2026-10-04T01:00:00+00:00',
                    'stars': repo['stargazers_count'], 'historyStatus': 'ok',
                    'statsThrough': date, 'metrics': {period: 1 if complete else None
                                                      for period in period_starts(date)},
                    'history': [{'date': date, 'stars': 1}] if complete else []}

        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'github-repositories.json'
            ledger.write_text(json.dumps({'projects': [existing], 'pending': candidates,
                                          'updatedAt': existing['fetchedAt']}))
            with patch.object(github, 'EXTRAS', ledger), \
                 patch.object(github, 'batch_metadata', return_value={}), \
                 patch.object(github, 'project_from_repo', side_effect=collected):
                github.collect(limit=2, pages=0, discover=False, new_limit=2)
            saved = json.loads(ledger.read_text())
            self.assertEqual({1, 2}, {project['id'] for project in saved['projects']})
            self.assertEqual({3, 4}, {repo['id'] for repo in saved['pending']})
            self.assertIn('lastAttemptAt', next(repo for repo in saved['pending'] if repo['id'] == 3))
            selected = select_work({p['id']: p for p in saved['projects']},
                                   {p['id']: p for p in saved['pending']}, end, 1, 1)
            self.assertEqual(4, selected[0][1]['id'])

    def test_history_backfills_2025_and_schedules_existing_short_histories(self):
        end = '2025-12-31'
        first = dt.date(2024, 12, 29)
        weeks = [{'week': int(dt.datetime.combine(first + dt.timedelta(weeks=offset),
                  dt.time(), dt.timezone.utc).timestamp()), 'total': 0, 'days': [0] * 7}
                 for offset in range(53)]
        weeks.reverse()
        calls = []

        def historical_page(endpoint):
            page = int(endpoint.split('page=')[-1])
            calls.append(page)
            return weeks[(page - 1) * 30:page * 30]

        repo = {'full_name': 'example/repo', 'created_at': '2025-01-01T00:00:00Z'}
        with patch.object(github, 'api', side_effect=historical_page):
            status, metrics, history = collect_history(repo, None, end)
        self.assertEqual('ok', status)
        self.assertEqual([1, 2], calls)
        self.assertEqual(0, metrics['yearly'])
        self.assertEqual('2025-01-01', history[3]['date'])
        complete = {'statsThrough': end, 'createdAt': repo['created_at'],
                    'metrics': metrics, 'history': history}
        self.assertFalse(needs_history(complete, end))
        self.assertTrue(needs_history({**complete, 'history': history[210:]}, end))

    def test_curated_chinese_explanations_and_new_project_fallback(self):
        ledger = json.loads((ROOT / 'data/github-repositories.json').read_text())
        profiles = json.loads((ROOT / 'data/github-profiles.json').read_text())
        names = {project['fullName'] for project in ledger['projects']}
        self.assertLessEqual(set(profiles), names)
        for original in ledger['projects']:
            localized = localized_profile(original, category(original), profiles)
            self.assertEqual(original['description'], localized['description'])
            profile = profiles.get(original['fullName'])
            if profile and profile['sourceDescription'] == original['description']:
                self.assertEqual(profile['summary'], localized['summary'])
            elif not any('\u3400' <= char <= '\u9fff' for char in original['description']):
                self.assertIn('尚待中文整理', localized['summary'])
            self.assertRegex(localized['summary'], '[\u3400-\u9fff]')
        changed = {**ledger['projects'][0], 'description': 'Changed upstream description'}
        self.assertIn('尚待中文整理', localized_profile(changed, category(changed), profiles)['summary'])

    def test_cli_auth_path_reads_rate_headers_without_exposing_token(self):
        budget = RateBudget(authenticated=True)
        response = 'HTTP/2.0 200 OK\r\nx-ratelimit-resource: core\r\nx-ratelimit-remaining: 39\r\n\r\n{"ok":true}'
        with patch.object(github, '_gh_ready', False), patch.object(github, 'RATE_BUDGET', budget), \
             patch.object(github.subprocess, 'run', side_effect=[
                 CompletedProcess(['gh', 'auth', 'status'], 0, '', ''),
                 CompletedProcess(['gh', 'api'], 0, response, '')]) as run:
            _, value = github.gh_response('repos/example/repo', {'Accept': 'application/vnd.github+json'})
        self.assertEqual({'ok': True}, value)
        self.assertEqual(39, budget.remaining['core'])
        self.assertEqual('gh', run.call_args_list[1].args[0][0])

    def test_budget_reserves_core_history_and_search_calls_separately(self):
        budget = RateBudget(authenticated=True)
        budget.after('repos/example/repo', {'X-RateLimit-Resource': 'core', 'X-RateLimit-Remaining': '40'})
        with self.assertRaises(RateLimitExceeded):
            budget.before('repos/example/repo')
        budget.after('repos/example/repo/stargazers/history',
                     {'X-RateLimit-Resource': 'core', 'X-RateLimit-Remaining': '6'})
        budget.before('repos/example/repo/stargazers/history')
        with self.assertRaises(RateLimitExceeded):
            budget.before('repos/example/repo')
        budget.after('repos/example/repo/stargazers/history',
                     {'X-RateLimit-Resource': 'core', 'X-RateLimit-Remaining': '5'})
        with self.assertRaises(RateLimitExceeded):
            budget.before('repos/example/repo/stargazers/history')
        budget.before('search/repositories?q=stars%3A%3E100')
        budget.after('search/repositories?q=stars%3A%3E100', {'X-RateLimit-Resource': 'search',
                                                               'X-RateLimit-Remaining': '2'})
        with self.assertRaises(RateLimitExceeded):
            budget.before('search/repositories?q=stars%3A%3E100')
        budget.paused = True
        with self.assertRaises(RateLimitExceeded):
            budget.before('repos/example/other')

    def test_discovery_stops_on_rate_limit_without_advancing_cursor(self):
        calls = []

        def limited(endpoint):
            calls.append(endpoint)
            raise RateLimitExceeded('quota exhausted')

        found, cursors = search_candidates('2026-10-03', pages=2, cursors={'0': 4}, api_get=limited)
        self.assertEqual({}, found)
        self.assertEqual({'0': 4}, cursors)
        self.assertEqual(1, len(calls))

    def test_independent_dataset_preserves_missing_growth_and_replays_real_days(self):
        end = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
        previous_day = (dt.date.fromisoformat(end) - dt.timedelta(days=1)).isoformat()

        def repo(identity, name, stars, created=previous_day):
            return {'id': identity, 'full_name': name, 'name': name.split('/')[1],
                    'owner': {'login': name.split('/')[0], 'avatar_url': ''},
                    'html_url': 'https://github.com/' + name, 'stargazers_count': stars,
                    'forks_count': 3, 'language': 'TypeScript', 'license': None,
                    'topics': ['web'], 'description': 'A web project', 'archived': False,
                    'created_at': created + 'T00:00:00Z', 'pushed_at': end + 'T00:00:00Z',
                    'default_branch': 'main', 'homepage': ''}

        ranked = project_from_repo(repo(1, 'example/first', 50), None, end, fetch_history=False)
        ranked.update(historyStatus='ok', statsThrough=end, metrics={'daily': 5, 'weekly': 8,
                      'monthly': 8, 'yearly': 8}, history=[{'date': previous_day, 'stars': 3},
                                                          {'date': end, 'stars': 5}], warnings=[])
        # The older day was fully covered before this repository existed. The
        # current cumulative board must still include the newly discovered repo.
        missing = project_from_repo(repo(2, 'example/second', 100, end), None, end, fetch_history=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'github-repositories.json', root / 'public/data/github'
            source.write_text(json.dumps({'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                                          'projects': [ranked, missing], 'pending': []}))
            result = build(source=source, output=output)
            self.assertEqual(2, len(result['projects']))
            self.assertEqual(period_starts(end), result['periodStarts'])
            self.assertEqual('GitHub 搜索和 Trending 发现并独立收录的公开仓库；不是 GitHub 全站所有仓库的穷尽榜单。', result['scope'])
            self.assertFalse(next(p for p in result['projects'] if p['id'] == 2)['stale'])
            self.assertIsNone(next(p for p in result['projects'] if p['id'] == 2)['metrics']['daily'])
            history = json.loads((output / 'history.json').read_text())
            packed, _ = unpack_history(output / 'history.json.gz', output / 'history-pack.json')
            self.assertEqual((output / 'history.json').read_bytes(), packed)
            self.assertEqual(5, next(p for p in history['projects'] if p['id'] == 1)['days'][-1]['stars'])
            self.assertEqual([], next(p for p in history['projects'] if p['id'] == 2)['days'])
            chart = json.loads((output / 'cumulative-chart.json').read_text())
            self.assertEqual([1], chart['entries'][-1]['ids'])
            bootstrap = json.loads((output / 'latest-bootstrap.json').read_text())
            self.assertEqual(end, bootstrap['periodEnd'])
            self.assertEqual(2, bootstrap['bootstrapStats']['projectCount'])
            self.assertEqual(1, bootstrap['bootstrapStats']['positiveDaily'])
            self.assertEqual(1, bootstrap['coverage']['updatedRepositories'])
            self.assertEqual(1, bootstrap['coverage']['pendingUpdates'])
            rows = [project for i in range(bootstrap['listShardCount'])
                    for project in json.loads((output / 'latest-list' / f'{i}.json').read_text())['projects']]
            self.assertEqual({1, 2}, {project['id'] for project in rows})

            # Current daily/yearly metrics must not hide missing early 2025
            # history in the published coverage count.
            old_creation = {**ranked, 'createdAt': '2025-01-01T00:00:00Z'}
            first_current_year = dt.date.fromisoformat(end).replace(month=1, day=1)
            history = [{'date': (first_current_year + dt.timedelta(days=offset)).isoformat(),
                        'stars': 1}
                       for offset in range((dt.date.fromisoformat(end) - first_current_year).days + 1)]
            days = {entry['date']: entry['stars'] for entry in history}
            old_creation['history'] = history
            old_creation['metrics'] = {period: period_total(days, start, end,
                                                             old_creation['createdAt'])
                                       for period, start in period_starts(end).items()}
            source.write_text(json.dumps({'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                                          'projects': [old_creation], 'pending': []}))
            incomplete = build(source=source, output=output)
            self.assertEqual(0, incomplete['coverage']['updatedRepositories'])
            self.assertEqual(1, incomplete['coverage']['pendingUpdates'])
            self.assertEqual('2025-01-01', incomplete['coverage']['historyStart'])
            validate_dataset(incomplete)


if __name__ == '__main__':
    unittest.main()
