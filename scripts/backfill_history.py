#!/usr/bin/env python3
"""Backfill aggregate Star days; never fabricate historical repository snapshots.

Existing validated daily values are reused. Each completed repository is persisted,
so rerunning resumes missing coverage without downloading completed histories again.
"""
import argparse
import concurrent.futures
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_START = '2025-01-01'
SOURCE = 'GitHub REST API /repos/{owner}/{repo}/stargazers/history'
SCOPE = '按当前收录项目回溯官方每日 Star 数；不是当时的全站榜单或当时的收录快照。'


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(path)


def missing_dates(days, start, end, created):
    cursor = dt.date.fromisoformat(max(start, created[:10]))
    last = dt.date.fromisoformat(end)
    result = []
    while cursor <= last:
        key = cursor.isoformat()
        if key not in days:
            result.append(key)
        cursor += dt.timedelta(days=1)
    return result


def merge_projects(previous, projects, start, end):
    """Keep past values for tracked IDs, overlay newly fetched valid aggregate days."""
    old = {p['id']: p for p in previous.get('projects', [])}
    merged = []
    for project in projects:
        project_start = max(start, project['createdAt'][:10])
        days = {d['date']: d['stars'] for d in old.get(project['id'], {}).get('days', [])
                if project_start <= d['date'] <= end}
        if project.get('historyStatus') == 'ok' and not project.get('stale'):
            for day in project.get('history', []):
                if project_start <= day['date'] <= end:
                    if type(day['stars']) is not int or day['stars'] < 0:
                        raise ValueError('Invalid aggregate daily count')
                    days[day['date']] = day['stars']
        merged.append({'id': project['id'], 'fullName': project['fullName'],
                       'createdAt': project['createdAt'],
                       'days': [{'date': date, 'stars': value} for date, value in sorted(days.items())]})
    return {'schemaVersion': 1, 'generatedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
            'source': SOURCE, 'scope': SCOPE, 'start': start, 'end': end, 'projects': merged}


def save_history(payload, directory):
    dates = sorted({day['date'] for p in payload['projects'] for day in p['days']})
    save_json(directory / 'history.json', payload)
    save_json(directory / 'history-index.json', {
        'start': dates[0] if dates else None, 'end': dates[-1] if dates else None,
        'dates': dates, 'source': payload['source'], 'scope': payload['scope'],
        'generatedAt': payload['generatedAt']})


def update_history(projects, end, directory=None):
    """Daily collection only merges days already fetched; no extra history API calls."""
    directory = Path(directory or ROOT / 'public/data')
    path = directory / 'history.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    payload = merge_projects(old, projects, old.get('start', DEFAULT_START), end)
    save_history(payload, directory)
    return payload


def first_missing_page(days, missing, today):
    """Newest-first 30-week pages. Start on the page containing the newest gap."""
    if not missing:
        return None
    target = dt.date.fromisoformat(max(missing))
    # GitHub weekly aggregate buckets start Sunday.
    latest_sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    target_sunday = target - dt.timedelta(days=(target.weekday() + 1) % 7)
    return max(1, (latest_sunday - target_sunday).days // 7 // 30 + 1)


def backfill_project(project, start, end, api_get=None):
    from collect import api, flatten_history
    api_get = api_get or api
    project_start = max(start, project['createdAt'][:10])
    days = {d['date']: d['stars'] for d in project['days'] if project_start <= d['date'] <= end}
    missing = missing_dates(days, start, end, project['createdAt'])
    page = first_missing_page(days, missing, dt.datetime.now(dt.timezone.utc).date())
    requests = 0
    errors = []
    if page is not None:
        # Hard bound prevents unexpected source pagination from exhausting Actions budgets.
        for number in range(page, min(page + 12, 100)):
            try:
                weeks = api_get(f'repos/{project["fullName"]}/stargazers/history?per_page=30&page={number}')
                requests += 1
                if not isinstance(weeks, list):
                    raise ValueError('Unexpected history response')
                if not weeks:
                    break
                values = flatten_history(weeks, end)  # Revalidates each weekly total.
                # Completed-source-day history is authoritative if GitHub corrects it.
                days.update({date: value for date, value in values.items() if project_start <= date <= end})
                missing = missing_dates(days, start, end, project['createdAt'])
                oldest = min(values) if values else end
                if not missing or len(weeks) < 30 or oldest <= max(start, project['createdAt'][:10]):
                    break
            except Exception as error:
                errors.append(str(error))
                break
    result = {**project, 'days': [{'date': date, 'stars': value} for date, value in sorted(days.items())]}
    return result, requests, missing_dates(days, start, end, project['createdAt']), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default=DEFAULT_START)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    dt.date.fromisoformat(args.start)
    directory = ROOT / 'public/data'
    latest = json.loads((directory / 'latest.json').read_text())
    end = min(latest['periodEnd'], (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat())
    path = directory / 'history.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    payload = merge_projects(old, latest['projects'], args.start, end)
    by_id = {p['id']: p for p in payload['projects']}
    requests = 0
    incomplete = []
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.workers, 6))) as pool:
        futures = [pool.submit(backfill_project, p, args.start, end) for p in payload['projects']]
        for future in concurrent.futures.as_completed(futures):
            project, count, missing, failures = future.result()
            by_id[project['id']] = project
            requests += count
            if missing:
                incomplete.append({'fullName': project['fullName'], 'missingCount': len(missing),
                                   'firstMissing': missing[0], 'lastMissing': missing[-1]})
            errors.extend({'fullName': project['fullName'], 'error': error} for error in failures)
            payload['projects'] = sorted(by_id.values(), key=lambda p: p['fullName'].lower())
            payload['generatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            save_history(payload, directory)
            print(f'{project["fullName"]}: {len(project["days"])} days; {count} requests; {len(missing)} missing', flush=True)
    print(json.dumps({'start': args.start, 'end': end, 'projects': len(by_id),
                      'calendarDays': (dt.date.fromisoformat(end) - dt.date.fromisoformat(args.start)).days + 1,
                      'requests': requests, 'incomplete': incomplete, 'errors': errors}, ensure_ascii=False), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
