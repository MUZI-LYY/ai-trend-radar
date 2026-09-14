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
 print(f'Validated {count} projects and {len(archives)} archives; all period totals match source histories.')


if __name__ == '__main__':
 main()
