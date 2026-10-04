#!/usr/bin/env python3
"""Collect an independent GitHub-wide candidate set and ranking dataset.

Search and Trending discover candidates; only repository metadata and GitHub's
aggregate Star history enter rankings. Work is bounded per run and resumable.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from collect import atomic_json, flatten_history, period_total, strip_readme
from ranking import period_starts

ROOT = Path(__file__).resolve().parents[1]
EXTRAS = ROOT / 'data/github-repositories.json'
HISTORY_START = '2025-01-01'


class RateLimitExceeded(RuntimeError):
    pass


class AuthenticationError(RuntimeError):
    pass


def header_value(headers, name):
    return next((value for key, value in headers.items() if key.lower() == name.lower()), None)


class RateBudget:
    """Keep room for other jobs sharing this token or anonymous egress IP."""

    def __init__(self, authenticated=False):
        self.remaining = {}
        self.reserve = {'core': 40 if authenticated else 5, 'search': 2}
        self.paused = False

    def resource(self, endpoint):
        return 'search' if endpoint.startswith('search/') else 'core'

    def before(self, endpoint):
        if self.paused:
            raise RateLimitExceeded('GitHub API secondary limit; continue in the next run')
        resource = self.resource(endpoint)
        if self.remaining.get(resource, self.reserve[resource] + 1) <= self.reserve[resource]:
            raise RateLimitExceeded(f'{resource} API reserve reached; continue in the next run')

    def after(self, endpoint, headers):
        resource = header_value(headers, 'X-RateLimit-Resource') or self.resource(endpoint)
        remaining = header_value(headers, 'X-RateLimit-Remaining')
        if resource in self.reserve and remaining is not None:
            self.remaining[resource] = int(remaining)


RATE_BUDGET = RateBudget(authenticated=True)
_gh_ready = False


def gh_response(endpoint, headers):
    """Use the same authenticated GitHub CLI path as the AI collector."""
    global _gh_ready
    if not _gh_ready:
        status = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True, timeout=15)
        if status.returncode:
            raise AuthenticationError('GitHub CLI 登录失效；请运行 gh auth login -h github.com，或设置 GITHUB_TOKEN。')
        _gh_ready = True
    command = ['gh', 'api', '-i', '-X', 'GET']
    for key, value in headers.items():
        command += ['-H', key + ': ' + value]
    result = subprocess.run(command + [endpoint], capture_output=True, text=True, timeout=40)
    match = re.search(r'\r?\n\r?\n', result.stdout)
    if not match:
        if result.returncode:
            raise RuntimeError('GitHub CLI 请求失败：' + result.stderr.strip()[:180])
        raise ValueError('GitHub CLI 响应缺少 HTTP 标头')
    header_text = result.stdout[:match.start()]
    body = result.stdout[match.end():]
    response_headers = {}
    for line in header_text.splitlines()[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            response_headers[key.strip()] = value.strip()
    RATE_BUDGET.after(endpoint, response_headers)
    if result.returncode:
        if re.search(r'\s401\s', header_text.splitlines()[0]):
            raise AuthenticationError('GitHub CLI 登录失效；请运行 gh auth login -h github.com。')
        if header_value(response_headers, 'X-RateLimit-Remaining') == '0':
            raise RateLimitExceeded('GitHub API rate limit exhausted')
        if header_value(response_headers, 'Retry-After') or 'secondary rate limit' in body.lower():
            RATE_BUDGET.paused = True
            raise RateLimitExceeded('GitHub API secondary limit; continue in the next run')
        raise RuntimeError('GitHub CLI 请求失败：' + result.stderr.strip()[:180])
    return response_headers, json.loads(body)


def api(endpoint):
    RATE_BUDGET.before(endpoint)
    headers = {'User-Agent': 'ai-trend-radar', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2026-03-10'}
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        _, value = gh_response(endpoint, headers)
        return value
    headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('https://api.github.com/' + endpoint, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            RATE_BUDGET.after(endpoint, response.headers)
            return json.load(response)
    except urllib.error.HTTPError as error:
        RATE_BUDGET.after(endpoint, error.headers)
        if error.code == 401:
            raise AuthenticationError('GITHUB_TOKEN 无效；请更换有效令牌。') from error
        if error.code == 403 and header_value(error.headers, 'X-RateLimit-Remaining') == '0':
            raise RateLimitExceeded('GitHub API rate limit exhausted') from error
        if error.code == 429 or (error.code == 403 and header_value(error.headers, 'Retry-After')):
            RATE_BUDGET.paused = True
            raise RateLimitExceeded('GitHub API secondary limit; continue in the next run') from error
        if error.code == 403 and 'secondary rate limit' in error.read(512).decode('utf-8', errors='replace').lower():
            RATE_BUDGET.paused = True
            raise RateLimitExceeded('GitHub API secondary limit; continue in the next run') from error
        raise


def search_candidates(end, pages=2, cursors=None, api_get=api):
    cursors = dict(cursors or {})
    queries = [
        ('stars:>10000 archived:false fork:false', 'stars'),
        ('stars:1000..10000 archived:false fork:false', 'stars'),
        ('stars:100..999 archived:false fork:false', 'stars'),
        (f'created:>={end[:4]}-01-01 stars:>200 archived:false fork:false', 'stars'),
        (f'pushed:>={end[:7]}-01 stars:>100 archived:false fork:false', 'updated'),
    ]
    found = {}
    from urllib.parse import urlencode
    for lane, (query, sort) in enumerate(queries):
        key = str(lane)
        page = cursors.get(key, 1)
        for _ in range(pages):
            try:
                result = api_get('search/repositories?' + urlencode({
                    'q': query, 'sort': sort, 'order': 'desc', 'per_page': 100, 'page': page}))
            except RateLimitExceeded as error:
                print(f'Search paused at lane {key}, page {page}: {error}', flush=True)
                cursors[key] = page
                return found, cursors
            except AuthenticationError:
                raise
            except Exception as error:
                print(f'Search lane {key}, page {page} unavailable: {error}', flush=True)
                break
            for repo in result.get('items', []):
                if not repo.get('private') and not repo.get('fork') and not repo.get('disabled'):
                    found[repo['id']] = repo
            page = 1 if len(result.get('items', [])) < 100 or page >= 10 else page + 1
        cursors[key] = page
    return found, cursors


def trending_names():
    request = urllib.request.Request('https://github.com/trending', headers={'User-Agent': 'ai-trend-radar'})
    with urllib.request.urlopen(request, timeout=25) as response:
        html = response.read().decode('utf-8', errors='replace')
    names = []
    for article in re.findall(r'<article\b.*?</article>', html, re.S):
        heading = re.search(r'<h2\b.*?</h2>', article, re.S)
        match = re.search(r'href="/([\w.-]+/[\w.-]+)"', heading.group(0) if heading else '')
        if match:
            names.append(match.group(1))
    return names


def collect_history(repo, previous, end):
    values = {day['date']: day['stars'] for day in (previous or {}).get('history', [])
              if day['date'] <= end and type(day['stars']) is int and day['stars'] >= 0}
    status = 'ok'
    latest_ok = False
    try:
        for page in range(1, 16):
            weeks = api(f'repos/{repo["full_name"]}/stargazers/history?per_page=30&page={page}')
            if not isinstance(weeks, list) or (page == 1 and not weeks):
                raise ValueError('Star history unavailable')
            if not weeks:
                break
            values.update(flatten_history(weeks, end))
            if page == 1:
                latest_ok = True
            if period_total(values, HISTORY_START, end, repo['created_at']) is not None or len(weeks) < 30:
                break
    except RateLimitExceeded:
        raise
    except Exception:
        status = 'ok' if latest_ok else 'unavailable'
    starts = period_starts(end)
    metrics = {period: period_total(values, start, end, repo['created_at']) if status == 'ok' else None
               for period, start in starts.items()}
    return status, metrics, [{'date': date, 'stars': count} for date, count in sorted(values.items())]


def needs_history(project, end):
    if project.get('statsThrough') != end or any(value is None for value in project.get('metrics', {}).values()):
        return True
    days = {day['date']: day['stars'] for day in project.get('history', [])}
    return period_total(days, HISTORY_START, end, project['createdAt']) is None


def readme_from_github(repo, previous, fetch):
    old = previous or {}
    if not fetch:
        return old.get('readme', ''), old.get('readmeUrl', repo['html_url']), old.get('readmeFetchedAt')
    fetched = old.get('readmeFetchedAt')
    if old.get('readme') and fetched:
        try:
            if dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(fetched) < dt.timedelta(days=7):
                return old['readme'], old['readmeUrl'], fetched
        except ValueError:
            pass
    root = 'https://raw.githubusercontent.com/' + quote(repo['full_name'], safe='/') + '/' + quote(repo.get('default_branch', 'main'), safe='') + '/'
    for filename in ('README.md', 'readme.md'):
        try:
            request = urllib.request.Request(root + filename, headers={'User-Agent': 'ai-trend-radar'})
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read(100000).decode('utf-8', errors='replace')
            excerpt = strip_readme(raw)
            if excerpt:
                return excerpt, repo['html_url'] + '/blob/' + quote(repo.get('default_branch', 'main'), safe='') + '/' + filename, dt.datetime.now(dt.timezone.utc).isoformat()
        except Exception:
            continue
    return old.get('readme', ''), old.get('readmeUrl', repo['html_url']), fetched


def project_from_repo(repo, previous, end, fetch_history=True):
    status, metrics, history = (collect_history(repo, previous, end) if fetch_history else
                                ('unavailable', {period: None for period in period_starts(end)}, []))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    description = repo.get('description') or ''
    topics = repo.get('topics') or []
    homepage = repo.get('homepage') or None
    if homepage and not homepage.startswith(('https://', 'http://')):
        homepage = None
    readme, readme_url, readme_fetched = readme_from_github(repo, previous, fetch_history)
    return {
        'id': repo['id'], 'fullName': repo['full_name'], 'name': repo['name'],
        'owner': repo['owner']['login'], 'avatar': repo['owner']['avatar_url'],
        'url': repo['html_url'], 'homepage': homepage,
        'stars': repo['stargazers_count'], 'forks': repo['forks_count'],
        'language': repo.get('language') or '未标注',
        'license': (repo.get('license') or {}).get('spdx_id') or '未明确',
        'topics': topics, 'description': description,
        'archived': repo['archived'], 'createdAt': repo['created_at'],
        'pushedAt': repo['pushed_at'], 'fetchedAt': now,
        'firstSeen': (previous or {}).get('firstSeen', now[:10]),
        'category': 'other', 'related': [], 'kind': '开源仓库',
        'tags': topics[:4], 'ways': [],
        'summary': description or '仓库作者未提供简介，请阅读官方 README。',
        'overview': description or '仓库作者未提供简介，请阅读官方 README 了解项目用途。',
        'audience': '请根据仓库文档判断是否适合你的工作。', 'features': [],
        'usage': '请阅读仓库 README 中的安装和使用说明。',
        'caveat': '具体功能、使用条件和许可范围以仓库当前文档为准。',
        'editorial': False, 'readme': readme, 'readmeFetchedAt': readme_fetched,
        'readmeUrl': readme_url,
        'classificationBasis': 'GitHub 仓库简介和 Topics；未进行人工用途分类。',
        'metrics': metrics, 'historyStatus': status, 'history': history,
        'warnings': ([] if all(value is not None for value in metrics.values()) else
                     ['部分周期 Star 历史暂不可用'] if status == 'ok' else ['Star 历史暂不可用']),
        'netSincePrevious': repo['stargazers_count'] - previous['stars'] if previous else None,
        'netBaselineAt': previous['fetchedAt'] if previous else None,
        'statsThrough': end if status == 'ok' else None,
        'metadataThrough': end, 'stale': False,
    }


def collect(limit=40, pages=2, discover=True):
    now = dt.datetime.now(dt.timezone.utc)
    end = (now.date() - dt.timedelta(days=1)).isoformat()
    previous = json.loads(EXTRAS.read_text()) if EXTRAS.exists() else {'projects': [], 'pending': []}
    by_id = {project['id']: project for project in previous['projects']}
    candidates = {repo['id']: repo for repo in previous.get('pending', [])}
    discovered, cursors = search_candidates(end, pages, previous.get('searchCursor', {})) if discover else ({}, previous.get('searchCursor', {}))
    candidates.update(discovered)
    if discover:
        try:
            for name in trending_names()[:8]:
                repo = api('repos/' + name)
                candidates[repo['id']] = repo
        except RateLimitExceeded as error:
            print(f'Trending lookup paused: {error}', flush=True)
        except Exception as error:
            print(f'Trending discovery incomplete: {error}', flush=True)
    # Refresh tracked projects first, then add highest-Star and recent candidates.
    due = sorted((p for p in by_id.values() if needs_history(p, end)),
                 key=lambda p: (p.get('statsThrough') == end, p.get('fetchedAt', '')))
    fresh = sorted((r for r in candidates.values() if r['id'] not in by_id),
                   key=lambda r: (-r.get('stargazers_count', 0), r['full_name'].lower()))
    selected = [('refresh', p) for p in due[:limit if not fresh else max(1, limit // 2)]]
    selected += [('new', p) for p in fresh[:max(0, limit - len(selected))]]
    changed = 0
    for kind, item in selected:
        try:
            repo = api('repos/' + item['fullName']) if kind == 'refresh' else item
            result = project_from_repo(repo, by_id.get(repo['id']), end)
            by_id[result['id']] = result
            changed += 1
            candidates.pop(result['id'], None)
            print(f'{result["fullName"]}: {result["stars"]} stars; history={result["historyStatus"]}', flush=True)
        except RateLimitExceeded as error:
            print(f'Collection paused: {error}', flush=True)
            break
        except AuthenticationError:
            raise
        except Exception as error:
            print(f'{item.get("fullName", item.get("full_name"))}: {error}', flush=True)
    # Search already returned official repository metadata. Admit it for the
    # cumulative board; period ranks wait for independently fetched history.
    for repo in candidates.values():
        if repo['id'] not in by_id:
            by_id[repo['id']] = project_from_repo(repo, None, end, fetch_history=False)
            changed += 1
    pending = []
    atomic_json(EXTRAS, {'schemaVersion': 1, 'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat() if changed else previous.get('updatedAt', now.isoformat()),
                         'projects': sorted(by_id.values(), key=lambda p: (-p['stars'], p['fullName'].lower())),
                         'pending': pending, 'searchCursor': cursors})
    return len(by_id), len(pending)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=40)
    parser.add_argument('--pages', type=int, default=2)
    parser.add_argument('--no-discover', action='store_true')
    args = parser.parse_args()
    if args.limit < 1 or args.pages < 0:
        parser.error('limit must be positive and pages nonnegative')
    try:
        print(collect(args.limit, args.pages, not args.no_discover))
    except AuthenticationError as error:
        parser.exit(2, str(error) + '\n')
