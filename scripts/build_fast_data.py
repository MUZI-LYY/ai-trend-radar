"""Build a small first-page dataset and on-demand list/detail shards.

The assembled latest.json remains the input for publication. This script runs
before development and production builds, so each collection gets matching
lightweight files.
"""

import json
import math
import datetime as dt
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / 'public' / 'data'
MIN_DETAIL_SHARDS = 64
DETAIL_PROJECTS_PER_SHARD = 70
LIST_PROJECTS_PER_SHARD = 250
CHART_DAYS = 32
DETAIL_CHART_DAYS = 365
README_PARAGRAPHS = 12
READY_COVERAGE_RATIO = 0.98
LOOKBACK_DAYS = 14


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')


def period_starts(end):
    day = dt.date.fromisoformat(end)
    return {'daily': end, 'weekly': (day - dt.timedelta(days=day.weekday())).isoformat(),
            'monthly': end[:7] + '-01', 'yearly': end[:4] + '-01-01'}


def total_days(values, start, end, created):
    first = max(start, created[:10])
    if first > end:
        return 0
    total = 0
    day = dt.date.fromisoformat(first)
    last = dt.date.fromisoformat(end)
    while day <= last:
        value = values.get(day.isoformat())
        if value is None:
            return None
        total += value
        day += dt.timedelta(days=1)
    return total


def publishable_dataset(latest):
    """Keep the last well-covered source day while a new day is collecting."""
    end = dt.date.fromisoformat(latest['periodEnd'])
    days = [(end - dt.timedelta(days=offset)).isoformat() for offset in range(LOOKBACK_DAYS)]
    coverage = dict.fromkeys(days, 0)
    eligible = dict.fromkeys(days, 0)
    for project in latest['projects']:
        created = project['createdAt'][:10]
        observed = {row['date'] for row in project.get('history', [])}
        for day in days:
            if created <= day:
                eligible[day] += 1
                coverage[day] += day in observed
    ready = next((day for day in days if eligible[day] and
                  coverage[day] / eligible[day] >= READY_COVERAGE_RATIO), None)
    if ready is None:
        ready = max(days, key=lambda day: coverage[day] / eligible[day] if eligible[day] else 0)
    if ready == latest['periodEnd']:
        return latest

    starts = period_starts(ready)
    projects = []
    for project in latest['projects']:
        if project['createdAt'][:10] > ready:
            continue
        history = [row for row in project.get('history', []) if row['date'] <= ready]
        values = {row['date']: row['stars'] for row in history}
        metrics = {period: total_days(values, start, ready, project['createdAt'])
                   for period, start in starts.items()}
        stale = metrics['daily'] is None
        projects.append({**project, 'history': history, 'metrics': metrics,
                         'stale': stale, 'statsThrough': ready if not stale else None,
                         'historyStatus': 'ok' if not stale else project['historyStatus'],
                         'warnings': [] if not stale else project.get('warnings', [])})
    updated = sum(not project['stale'] and all(value is not None for value in project['metrics'].values())
                  for project in projects)
    count = len(projects)
    old_coverage = latest.get('coverage', {})
    warnings = [warning for warning in latest.get('warnings', [])
                if '个已收录项目待更新或暂缺完整本期数据' not in warning]
    if updated < count:
        warnings.append(f'{count - updated} 个项目缺少 {ready} 的完整日统计，未参与当日日榜。')
    return {**latest, 'periodEnd': ready, 'periodStarts': starts, 'projects': projects,
            'pendingDay': latest['periodEnd'], 'pendingDayCoverage': coverage[latest['periodEnd']],
            'pendingDayTotal': eligible[latest['periodEnd']],
            'status': 'partial' if updated < count else 'complete', 'warnings': warnings,
            'failedRepositories': [],
            'coverage': {**old_coverage, 'sourceDate': ready, 'trackedRepositories': count,
                         'updatedRepositories': updated,
                         'pendingUpdates': count - updated}}


def build_archived_boards(source, completed_at):
    """Keep covered archived TOP 30s in one small request for week/month views."""
    index_path = source / 'board-history.json'
    entries = json.loads(index_path.read_text())['entries'] if index_path.exists() else []
    boards = []
    for entry in entries:
        tracked = entry.get('trackedRepositories', 0)
        if not tracked or entry.get('updatedRepositories', 0) / tracked < READY_COVERAGE_RATIO:
            continue
        snapshot = json.loads((source / 'snapshots' / (entry['capturedDate'] + '.json')).read_text())
        leaders = sorted((project for project in snapshot['projects']
                          if not project.get('stale') and (project['metrics'].get('daily') or 0) > 0),
                         key=lambda project: (-project['metrics']['daily'], -project['stars'],
                                              project['fullName'].lower()))[:30]
        if [project['id'] for project in leaders] != entry['ids']:
            raise ValueError('Archived daily chart changed: ' + entry['date'])
        board = {key: value for key, value in snapshot.items() if key != 'projects'}
        board['projects'] = [{**{key: value for key, value in project.items()
                                 if key not in ('history', 'readme')},
                              'history': [], 'readme': ''} for project in leaders]
        boards.append(board)
    write_json(source / 'snapshot-boards.json', {'completedAt': completed_at, 'snapshots': boards})


def build(source=DATA):
    latest = publishable_dataset(json.loads((source / 'latest.json').read_text()))
    bootstrap = {key: value for key, value in latest.items() if key != 'projects'}
    detail_count = max(MIN_DETAIL_SHARDS, math.ceil(len(latest['projects']) / DETAIL_PROJECTS_PER_SHARD))
    detail_shards = [[] for _ in range(detail_count)]
    projects = []
    for project in latest['projects']:
        # The list needs recent points for its sparkline and up to a full month
        # for daily-board aggregation. Longer charts and the README excerpt
        # load only when someone opens a project.
        compact = {key: value for key, value in project.items()
                   if key not in ('readme', 'sourceExcerpts', 'readmeSha',
                                  'readmeFetchedAt', 'profileSource', 'history')}
        compact['history'] = project.get('history', [])[-CHART_DAYS:]
        projects.append(compact)
        detail_shards[project['id'] % detail_count].append({
            'id': project['id'],
            'history': project.get('history', [])[-DETAIL_CHART_DAYS:],
            'readme': '\n\n'.join(project.get('readme', '').split('\n\n')[:README_PARAGRAPHS]),
        })
    leaders = [p for p in projects if not p.get('stale') and (p['metrics'].get('daily') or 0) > 0]
    leaders.sort(key=lambda p: (-p['metrics']['daily'], -p['stars'], p['fullName'].lower()))
    bootstrap['projects'] = leaders[:30]
    bootstrap['listComplete'] = False
    list_shards = [projects[i:i + LIST_PROJECTS_PER_SHARD]
                   for i in range(0, len(projects), LIST_PROJECTS_PER_SHARD)]
    bootstrap['listShardCount'] = len(list_shards)
    bootstrap['detailShardCount'] = detail_count
    bootstrap['bootstrapStats'] = {
        'projectCount': len(projects),
        'positiveDaily': len(leaders),
        'zeroDaily': sum(not p.get('stale') and p['metrics'].get('daily') == 0 for p in projects),
        'missingDaily': sum(not p.get('stale') and p['metrics'].get('daily') is None for p in projects),
        'rankedDaily': sum(not p.get('stale') and p['metrics'].get('daily') is not None for p in projects),
    }
    write_json(source / 'latest-bootstrap.json', bootstrap)
    for index, rows in enumerate(list_shards):
        write_json(source / 'latest-list' / f'{index}.json', {
            'completedAt': latest['completedAt'], 'projects': rows})
    for index, rows in enumerate(detail_shards):
        write_json(source / 'project-details' / f'{index}.json', rows)
    for directory, count in ((source / 'latest-list', len(list_shards)),
                             (source / 'project-details', detail_count)):
        for path in directory.glob('*.json'):
            if path.stem.isdecimal() and int(path.stem) >= count:
                path.unlink()
    build_archived_boards(source, latest['completedAt'])
    # This file was used by the previous unsplit client build.
    (source / 'latest-summary.json').unlink(missing_ok=True)


if __name__ == '__main__':
    build()
