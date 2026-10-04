#!/usr/bin/env python3
"""Resume GitHub-wide Star history backfills without writing the source ledger.

Each stable ID shard writes one atomic patch per repository. Run shards in
separate processes, then merge their patch directories into a fresh ledger
copy. Only official daily values are stored; missing dates remain absent.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

import collect_github as github
from backfill_history import first_missing_page, missing_dates
from collect import atomic_json, flatten_history, period_total
from ranking import period_starts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/github-repositories.json'
START = '2025-01-01'


def read_ledger(path):
    ledger = json.loads(Path(path).read_text())
    if not isinstance(ledger.get('projects'), list):
        raise ValueError('Input must be a GitHub repository ledger')
    return ledger


def valid_days(entries, start, end):
    days = {}
    for item in entries:
        date, value = item['date'], item['stars']
        dt.date.fromisoformat(date)
        if type(value) is not int or value < 0:
            raise ValueError(f'Invalid official Star day: {date}')
        if start <= date <= end:
            days[date] = value
    return days


def patch_path(directory, identity):
    return Path(directory) / f'{identity}.json'


def read_patch(path, project, start, end):
    if not path.exists():
        return {'schemaVersion': 1, 'id': project['id'], 'fullName': project['fullName'],
                'createdAt': project['createdAt'], 'start': start, 'end': end,
                'days': [], 'nextPage': None, 'pageAnchor': None, 'complete': False}
    patch = json.loads(path.read_text())
    if (patch.get('schemaVersion'), patch.get('id'), patch.get('start'), patch.get('end')) != (1, project['id'], start, end):
        raise ValueError(f'Patch identity or date range differs: {path}')
    valid_days(patch['days'], max(start, project['createdAt'][:10]), end)
    return patch


def collect_one(project, start, end, output, api_get=None, max_requests=15, today=None):
    """Return (requests, missing, exhausted); save a checkpoint after each page."""
    api_get = api_get or github.api
    today = today or dt.datetime.now(dt.timezone.utc).date()
    path = patch_path(output, project['id'])
    patch = read_patch(path, project, start, end)
    first = max(start, project['createdAt'][:10])
    existing = valid_days(project.get('history', []), first, end)
    fetched = valid_days(patch['days'], first, end)
    days = {**existing, **fetched}
    missing = missing_dates(days, start, end, project['createdAt'])
    if not missing:
        if not patch['complete'] and path.exists():
            patch['complete'] = True
            atomic_json(path, patch)
        return 0, [], False
    if max_requests < 1:
        return 0, missing, False

    anchor = (today - dt.timedelta(days=(today.weekday() + 1) % 7)).isoformat()
    page = (patch.get('nextPage') if patch.get('pageAnchor') == anchor else None)
    page = page or first_missing_page(days, missing, today)
    requests = 0
    exhausted = False
    while requests < max_requests and page <= 100:
        try:
            weeks = api_get(f'repos/{project["fullName"]}/stargazers/history?per_page=30&page={page}')
        except github.RateLimitExceeded:
            raise
        requests += 1
        if not isinstance(weeks, list) or not weeks:
            exhausted = True
            break
        values = flatten_history(weeks, end)
        if not values:
            exhausted = True
            break
        fetched.update({date: value for date, value in values.items() if first <= date <= end})
        days = {**existing, **fetched}
        missing = missing_dates(days, start, end, project['createdAt'])
        patch.update(fullName=project['fullName'], createdAt=project['createdAt'],
                     days=[{'date': date, 'stars': value} for date, value in sorted(fetched.items())],
                     nextPage=page + 1, pageAnchor=anchor, complete=not missing,
                     collectedAt=dt.datetime.now(dt.timezone.utc).isoformat())
        atomic_json(path, patch)
        if not missing or len(weeks) < 30 or min(values) <= first:
            exhausted = bool(missing)
            break
        page += 1
    return requests, missing, exhausted


def collect_shard(source, output, start, end, shard_index=0, shard_count=1,
                  max_requests=1000, project_limit=None, api_get=None, today=None):
    if shard_count < 1 or not 0 <= shard_index < shard_count or max_requests < 1:
        raise ValueError('Invalid shard or request limit')
    ledger = read_ledger(source)
    chosen = sorted((p for p in ledger['projects'] if p['id'] % shard_count == shard_index),
                    key=lambda p: p['id'])
    requests = attempted = complete = incomplete = errors = 0
    limited = False
    for project in chosen:
        if project_limit is not None and attempted >= project_limit:
            break
        remaining = max_requests - requests
        if remaining <= 0:
            limited = True
            break
        attempted += 1
        try:
            used, missing, exhausted = collect_one(project, start, end, output, api_get,
                                                    min(15, remaining), today)
            requests += used
            complete += not missing
            incomplete += bool(missing)
            if missing:
                print(f'{project["fullName"]}: {len(missing)} dates missing' +
                      ('; source exhausted' if exhausted else ''), flush=True)
        except github.RateLimitExceeded as error:
            limited = True
            print(f'API budget reached at {project["fullName"]}: {error}', flush=True)
            break
        except github.AuthenticationError:
            raise
        except Exception as error:
            errors += 1
            print(f'{project["fullName"]}: {error}', flush=True)
    return {'shard': f'{shard_index}/{shard_count}', 'projects': len(chosen),
            'attempted': attempted, 'complete': complete, 'incomplete': incomplete,
            'requests': requests, 'rateLimited': limited, 'errors': errors}


def merge(source, output, patch_directories):
    """Fill missing ledger days by stable ID, preserving newer source values."""
    ledger = read_ledger(source)
    by_id = {project['id']: project for project in ledger['projects']}
    patched = set()
    for directory in patch_directories:
        for path in sorted(Path(directory).glob('*.json')):
            patch = json.loads(path.read_text())
            if patch.get('schemaVersion') != 1 or patch.get('id') not in by_id:
                raise ValueError(f'Unknown or invalid patch: {path}')
            identity = patch['id']
            project = by_id[identity]
            first = max(patch['start'], project['createdAt'][:10])
            incoming = valid_days(patch['days'], first, patch['end'])
            prior = valid_days(project.get('history', []), '0001-01-01', '9999-12-31')
            # A current ledger may contain later corrections to overlapping days.
            added = {date: value for date, value in incoming.items() if date not in prior}
            if not added:
                continue
            prior.update(added)
            project['history'] = [{'date': date, 'stars': value} for date, value in sorted(prior.items())]
            target = max(project.get('statsThrough') or '', patch['end'])
            if target:
                project['metrics'] = {period: period_total(prior, start, target, project['createdAt'])
                                      for period, start in period_starts(target).items()}
                project['statsThrough'] = target
                project['historyStatus'] = 'ok'
                if all(value is not None for value in project['metrics'].values()):
                    project['warnings'] = [warning for warning in project.get('warnings', [])
                                           if '历史' not in warning]
                elif '部分周期 Star 历史暂不可用' not in project.get('warnings', []):
                    project['warnings'] = [*project.get('warnings', []), '部分周期 Star 历史暂不可用']
            patched.add(identity)
    if Path(output).resolve() == Path(source).resolve():
        raise ValueError('Merge output must differ from source')
    if patched:
        ledger['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    atomic_json(Path(output), ledger)
    return {'repositoriesPatched': len(patched), 'projects': len(by_id), 'output': str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    collect = sub.add_parser('collect', help='Fetch one stable ID shard into a patch directory')
    collect.add_argument('--input', type=Path, default=SOURCE)
    collect.add_argument('--output', type=Path, required=True)
    collect.add_argument('--start', default=START)
    collect.add_argument('--end', required=True)
    collect.add_argument('--shard-index', type=int, default=0)
    collect.add_argument('--shard-count', type=int, default=1)
    collect.add_argument('--max-requests', type=int, default=1000)
    collect.add_argument('--project-limit', type=int)
    combine = sub.add_parser('merge', help='Apply patch directories to a fresh ledger copy')
    combine.add_argument('--input', type=Path, default=SOURCE)
    combine.add_argument('--output', type=Path, required=True)
    combine.add_argument('patch_directories', type=Path, nargs='+')
    args = parser.parse_args()
    if args.action == 'collect':
        if dt.date.fromisoformat(args.start) > dt.date.fromisoformat(args.end):
            parser.error('--start must not follow --end')
        result = collect_shard(args.input, args.output, args.start, args.end,
                               args.shard_index, args.shard_count,
                               args.max_requests, args.project_limit)
    else:
        result = merge(args.input, args.output, args.patch_directories)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
