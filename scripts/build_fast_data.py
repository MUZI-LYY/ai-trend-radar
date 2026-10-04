"""Build the small current-day page and archived daily charts from canonical data."""
import json
from pathlib import Path

if __package__:
    from .pack_latest import write_json
else:
    from pack_latest import write_json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'public/data'
DETAIL_SHARDS = 64


def daily_leaders(projects):
    return sorted((p for p in projects if not p.get('stale') and
                   (p['metrics'].get('daily') or 0) > 0),
                  key=lambda p: (-p['metrics']['daily'], -p['stars'],
                                 p['fullName'].lower()))[:30]


def build(directory=DATA):
    directory = Path(directory)
    latest = json.loads((directory / 'latest.json').read_text())
    bootstrap = {key: value for key, value in latest.items() if key != 'projects'}
    bootstrap['projects'] = daily_leaders(latest['projects'])
    bootstrap['bootstrapStats'] = {
        'projectCount': len(latest['projects']),
        'positiveDaily': sum(not p.get('stale') and (p['metrics'].get('daily') or 0) > 0
                             for p in latest['projects']),
        'zeroDaily': sum(not p.get('stale') and p['metrics'].get('daily') == 0
                         for p in latest['projects']),
        'missingDaily': sum(not p.get('stale') and p['metrics'].get('daily') is None
                            for p in latest['projects']),
    }
    write_json(directory / 'latest-bootstrap.json', bootstrap)

    compact = []
    detail_shards = [[] for _ in range(DETAIL_SHARDS)]
    for project in latest['projects']:
        compact.append({**{key: value for key, value in project.items()
                           if key not in ('readme', 'history', 'sourceExcerpts',
                                          'readmeSha', 'readmeFetchedAt', 'profileSource')},
                        'readme': '', 'history': project.get('history', [])[-32:]})
        detail_shards[project['id'] % DETAIL_SHARDS].append({
            'id': project['id'], 'readme': project.get('readme', ''),
            'history': project.get('history', [])[-365:]})
    slim = {**bootstrap, 'projects': compact, 'detailShardCount': DETAIL_SHARDS}
    write_json(directory / 'latest-slim.json', slim)
    for number, projects in enumerate(detail_shards):
        write_json(directory / 'project-details' / f'{number}.json', {
            'completedAt': latest['completedAt'], 'projects': projects})

    boards = []
    index = json.loads((directory / 'board-history.json').read_text())
    for entry in index['entries']:
        snapshot = json.loads((directory / 'snapshots' /
                               (entry['capturedDate'] + '.json')).read_text())
        leaders = daily_leaders(snapshot['projects'])
        if [p['id'] for p in leaders] != entry['ids']:
            raise ValueError('Archived daily chart changed: ' + entry['date'])
        board = {key: value for key, value in snapshot.items() if key != 'projects'}
        board['projects'] = [{**{key: value for key, value in project.items()
                                 if key != 'history' and key != 'readme'},
                              'history': [], 'readme': ''} for project in leaders]
        boards.append(board)
    write_json(directory / 'snapshot-boards.json', {
        'completedAt': latest['completedAt'], 'snapshots': boards})
    return {'bootstrapProjects': len(bootstrap['projects']),
            'listProjects': len(compact), 'snapshots': len(boards)}


if __name__ == '__main__':
    print(json.dumps(build()))
