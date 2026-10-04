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
from collect_github import RateBudget, RateLimitExceeded, collect_history, needs_history, project_from_repo, search_candidates
from ranking import period_starts


class GithubBoardTests(unittest.TestCase):
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

    def test_budget_reserves_core_and_search_calls_separately(self):
        budget = RateBudget(authenticated=True)
        budget.after('repos/example/repo', {'X-RateLimit-Resource': 'core', 'X-RateLimit-Remaining': '40'})
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

        def repo(identity, name, stars):
            return {'id': identity, 'full_name': name, 'name': name.split('/')[1],
                    'owner': {'login': name.split('/')[0], 'avatar_url': ''},
                    'html_url': 'https://github.com/' + name, 'stargazers_count': stars,
                    'forks_count': 3, 'language': 'TypeScript', 'license': None,
                    'topics': ['web'], 'description': 'A web project', 'archived': False,
                    'created_at': previous_day + 'T00:00:00Z', 'pushed_at': end + 'T00:00:00Z',
                    'default_branch': 'main', 'homepage': ''}

        ranked = project_from_repo(repo(1, 'example/first', 50), None, end, fetch_history=False)
        ranked.update(historyStatus='ok', statsThrough=end, metrics={'daily': 5, 'weekly': 8,
                      'monthly': 8, 'yearly': 8}, history=[{'date': previous_day, 'stars': 3},
                                                          {'date': end, 'stars': 5}], warnings=[])
        missing = project_from_repo(repo(2, 'example/second', 100), None, end, fetch_history=False)
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
            self.assertEqual(5, next(p for p in history['projects'] if p['id'] == 1)['days'][-1]['stars'])
            self.assertEqual([], next(p for p in history['projects'] if p['id'] == 2)['days'])
            chart = json.loads((output / 'cumulative-chart.json').read_text())
            self.assertEqual([1], chart['entries'][-1]['ids'])
            bootstrap = json.loads((output / 'latest-bootstrap.json').read_text())
            self.assertEqual(2, bootstrap['bootstrapStats']['projectCount'])
            self.assertEqual(1, bootstrap['bootstrapStats']['positiveDaily'])


if __name__ == '__main__':
    unittest.main()
