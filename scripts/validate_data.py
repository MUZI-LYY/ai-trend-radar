"""Validate both current data and immutable archives against their source day counts."""
import json
import datetime as dt
from pathlib import Path
from collect import period_total
from ranking import period_starts, chart_entries


def validate_dataset(data):
 assert data['projects'], 'No projects'
 dt.date.fromisoformat(data['date'])
 for key in ('capturedAt', 'completedAt'):
  assert dt.datetime.fromisoformat(data[key]).tzinfo is not None, f'Missing timezone: {key}'
 assert data['capturedAt'] <= data['completedAt'], 'Collection completed before capture'
 starts = period_starts(data['periodEnd'])
 required = set(starts) if data['schemaVersion'] >= 2 else {'daily', 'monthly', 'yearly'}
 assert required <= data['periodStarts'].keys(), 'Missing period boundaries'
 assert all(start == starts[period] for period, start in data['periodStarts'].items()), 'Incorrect period boundary'
 ids = set()
 categories = {category['id'] for category in data['categories']}
 for project in data['projects']:
  label = project['fullName']
  assert project['id'] not in ids, f'Duplicate repository ID: {label}'
  ids.add(project['id'])
  assert type(project['stars']) is int and project['stars'] >= 0, label
  assert type(project['forks']) is int and project['forks'] >= 0, label
  assert project['url'].startswith('https://github.com/'), label
  assert project['category'] in categories, label
  assert all(category in categories for category in project['related']), label
  assert project['category'] not in project['related'], label
  assert project['summary'] and project['overview'] and project['readmeUrl'], label
  for field in ('useCases', 'gettingStarted', 'requirements'):
   assert isinstance(project.get(field, []), list) and all(isinstance(value, str) and value.strip() for value in project.get(field, [])), f'Invalid {field}: {label}'
  assert required <= project['metrics'].keys(), f'Missing metrics: {label}'
  assert all(value is None or type(value) is int and value >= 0 for value in project['metrics'].values()), label
  history = {}
  for entry in project['history']:
   dt.date.fromisoformat(entry['date'])
   assert entry['date'] <= data['periodEnd'], f'Unfinished future day: {label}'
   assert entry['date'] not in history, f'Duplicate history day: {label}'
   assert type(entry['stars']) is int and entry['stars'] >= 0, label
   history[entry['date']] = entry['stars']
  for period, actual in project['metrics'].items():
   expected = None if project.get('stale') or project['historyStatus'] != 'ok' else period_total(history, starts[period], data['periodEnd'], project['createdAt'])
   assert actual == expected, f'{label} {period}: published {actual}, source history {expected}'
 return len(ids)


def validate_history(history, index, latest):
 assert history['schemaVersion'] == 1, 'Unexpected backfill schema'
 assert dt.datetime.fromisoformat(history['generatedAt']).tzinfo is not None, 'Missing history generation timezone'
 assert history['source'] and history['scope'], 'Missing historical source or scope'
 start, end = history['start'], history['end']
 dt.date.fromisoformat(start)
 dt.date.fromisoformat(end)
 assert start <= end <= latest['periodEnd'], 'Invalid historical date boundaries'
 current = {project['id']: project for project in latest['projects']}
 ids, dates = set(), set()
 for project in history['projects']:
  label = project['fullName']
  assert project['id'] not in ids, f'Duplicate historical repository: {label}'
  ids.add(project['id'])
  assert project['id'] in current, f'Untracked historical repository: {label}'
  fresh = current[project['id']]
  assert label == fresh['fullName'] and project['createdAt'] == fresh['createdAt'], f'Historical identity mismatch: {label}'
  days = {}
  for entry in project['days']:
   date = entry['date']
   dt.date.fromisoformat(date)
   assert max(start, project['createdAt'][:10]) <= date <= end, f'Historical day outside repository lifetime: {label}'
   assert date not in days, f'Duplicate backfilled day: {label}'
   assert type(entry['stars']) is int and entry['stars'] >= 0, f'Invalid backfilled count: {label}'
   days[date] = entry['stars']
   dates.add(date)
  if fresh.get('historyStatus') == 'ok' and not fresh.get('stale'):
   for entry in fresh['history']:
    if max(start, project['createdAt'][:10]) <= entry['date'] <= end:
     assert days.get(entry['date']) == entry['stars'], f'Backfill differs from latest official daily value: {label}'
 assert ids == set(current), 'Historical project scope differs from current collection'
 expected = sorted(dates)
 assert index['dates'] == expected, 'Historical index dates differ from stored days'
 assert index['start'] == (expected[0] if expected else None), 'Historical index start differs'
 assert index['end'] == (expected[-1] if expected else None), 'Historical index end differs'
 assert all(index[key] == history[key] for key in ('source', 'scope', 'generatedAt')), 'Historical index metadata mismatch'
 return len(expected)


def main():
 root = Path(__file__).resolve().parents[1] / 'public/data'
 latest = json.loads((root / 'latest.json').read_text())
 count = validate_dataset(latest)
 index = json.loads((root / 'index.json').read_text())
 archives = []
 for snapshot in index['snapshots']:
  path = root / snapshot['file']
  assert path.resolve().is_relative_to(root.resolve()), 'Archive path outside data directory'
  assert path.exists(), 'Missing archive'
  archived = json.loads(path.read_text())
  assert archived['date'] == snapshot['date'], 'Archive date mismatch'
  validate_dataset(archived)
  archives.append(archived)
 board = json.loads((root / 'board-history.json').read_text())
 assert board['chartSize'] == 30, 'Unexpected daily board size'
 assert board['entries'] == chart_entries(archives), 'Board history differs from first archived daily rankings'
 history_days = validate_history(json.loads((root / 'history.json').read_text()), json.loads((root / 'history-index.json').read_text()), latest)
 print(f'Validated {count} projects and {len(archives)} archives; {history_days} historical source dates; all period totals match source histories.')


if __name__ == '__main__':
 main()
