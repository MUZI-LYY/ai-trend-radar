import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect import collect_one
from source_profile import build_source_profile


class SourceProfileLanguageTests(unittest.TestCase):
    def test_english_source_stays_in_source_excerpts(self):
        repo = {'full_name': 'example/agent', 'name': 'agent', 'category': 'agents',
                'description': 'Run agents in isolated machines.'}
        readme = '# Features\n\nRun AI agents in isolated machines with their own filesystem.\n\n# Quick Start\n\nInstall this tool with the official package manager.'
        profile = build_source_profile(repo, readme)
        for field in ('summary', 'overview', 'audience', 'usage', 'caveat'):
            self.assertNotIn('Run AI agents', profile[field], field)
            self.assertRegex(profile[field], '[\u4e00-\u9fff]', field)
        for field in ('features', 'useCases', 'gettingStarted', 'requirements'):
            self.assertNotIn('Run AI agents', ' '.join(profile[field]), field)
        self.assertIn('Run AI agents', str(profile['sourceExcerpts']))
        self.assertIn('尚未完成逐项中文解读', profile['overview'])

    def test_daily_collection_rebuilds_old_english_cached_profile(self):
        repo = {'id': 42, 'full_name': 'example/agent', 'name': 'agent',
                'description': 'Run agents in isolated machines.', 'topics': ['agent'],
                'language': 'Rust', 'homepage': None, 'default_branch': 'main',
                'private': False, 'fork': False, 'disabled': False, 'archived': False,
                'created_at': '2026-09-25T00:00:00Z', 'pushed_at': '2026-09-25T00:00:00Z',
                'owner': {'login': 'example', 'avatar_url': 'https://example.com/avatar'},
                'html_url': 'https://github.com/example/agent', 'stargazers_count': 10,
                'forks_count': 1, 'license': {'spdx_id': 'MIT'}}
        previous = {'readme': '# Features\n\nRun AI agents in isolated machines with their own filesystem.',
                    'readmeUrl': 'https://github.com/example/agent/blob/main/README.md',
                    'readmeFetchedAt': '2026-09-25T00:00:00Z', 'profileSource': 'readme-extract',
                    'overview': '作者简介：Run agents in isolated machines.', 'stars': 9,
                    'firstSeen': '2026-09-25', 'fetchedAt': '2026-09-25T00:00:00Z'}
        week = int(dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc).timestamp())
        values = [0, 0, 0, 0, 0, 3, 0]
        with patch('collect.should_refresh_readme', return_value=False), patch('collect.api', return_value=[{'week': week, 'days': values, 'total': 3}]):
            result = collect_one('example/agent', previous, {}, '2026-09-25', '2026-01-01', repo=repo)
        self.assertEqual(result['metrics']['daily'], 3)
        self.assertIn('尚未完成逐项中文解读', result['overview'])
        self.assertNotIn('Run agents', result['overview'])
        self.assertIn('Run AI agents', str(result['sourceExcerpts']))


if __name__ == '__main__':
    unittest.main()
