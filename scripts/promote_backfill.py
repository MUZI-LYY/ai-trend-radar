#!/usr/bin/env python3
"""Publish verified local reviews without inventing repository metrics."""
import argparse
import datetime as dt
import json
import sqlite3
import zlib
from pathlib import Path

from backfill_history import update_history
from build_fast_data import publishable_dataset
from build_tenure_index import cumulative_chart
from collect import atomic_json, collection_coverage, period_total
from discover import MIN_STARS, load_state, save_state
from pack_latest import pack
from ranking import period_starts
from validate_data import validate_dataset, validate_history

ROOT = Path(__file__).resolve().parents[1]


def eligible_project(identity, packed, source_day):
    if not packed:
        return None
    project = json.loads(zlib.decompress(packed))
    if (project.get('id') != identity or project.get('stars', 0) < MIN_STARS
            or project.get('historyStatus') != 'ok'
            or project.get('statsThrough') != source_day):
        return None
    days = {item['date']: item['stars'] for item in project['history']}
    starts = period_starts(source_day)
    if any(project['metrics'].get(period) != period_total(
            days, start, source_day, project['createdAt'])
           for period, start in starts.items()):
        return None
    return project


def promote(root=ROOT, database=None):
    root = Path(root)
    database = Path(database or root / 'data/local-backfill.sqlite3')
    data_dir = root / 'public/data'
    latest_path = data_dir / 'latest.json'
    latest = json.loads(latest_path.read_text())
    state = load_state(root / 'data/discovery.json')
    source_day = latest['periodEnd']
    projects = {project['id']: project for project in latest['projects']}
    names = {project['fullName'].lower(): project['id'] for project in latest['projects']}
    admitted = rejected = deferred = 0
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
        rows = db.execute('SELECT id,full_name,status,project FROM reviews ORDER BY id')
        for identity, full_name, status, packed in rows:
            candidate = state['candidates'].get(str(identity))
            if candidate is None or candidate['fullName'].lower() != full_name.lower():
                deferred += 1
                continue
            if status == 'rejected':
                if candidate.get('status') != 'rejected':
                    candidate['status'] = 'rejected'
                    rejected += 1
                continue
            if status != 'admitted':
                continue
            project = eligible_project(identity, packed, source_day)
            if project is None or (project['fullName'].lower() in names
                    and names[project['fullName'].lower()] != identity):
                deferred += 1
                continue
            candidate['status'] = 'admitted'
            if identity not in projects:
                projects[identity] = project
                names[project['fullName'].lower()] = identity
                admitted += 1

    if not (admitted or rejected):
        return {'admitted': 0, 'rejected': 0, 'deferred': deferred,
                'projects': len(projects), 'pending': latest['coverage']['pendingCandidates']}

    latest['projects'] = sorted(projects.values(), key=lambda project:
                                (-project['stars'], project['fullName'].lower()))
    latest['completedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    excluded_path = root / 'data/excluded.json'
    excluded = json.loads(excluded_path.read_text()) if excluded_path.exists() else []
    latest['coverage'] = collection_coverage(latest['projects'], state, excluded, source_day)
    latest['warnings'] = [warning for warning in latest.get('warnings', [])
                          if '个已收录项目待更新或暂缺完整本期数据' not in warning]
    if latest['coverage']['pendingUpdates']:
        latest['warnings'].append(
            f"{latest['coverage']['pendingUpdates']} 个已收录项目待更新或暂缺完整本期数据，"
            '后续批次继续处理；未更新指标不参榜。')
    latest['warnings'] = sorted(set(latest['warnings']))
    validate_dataset(latest, current_taxonomy=True)

    save_state(state, root / 'data/discovery.json')
    atomic_json(latest_path, latest)
    history = update_history(latest['projects'], source_day, data_dir)
    history_index = json.loads((data_dir / 'history-index.json').read_text())
    validate_history(history, history_index, latest)
    board = json.loads((data_dir / 'board-history.json').read_text())
    chart = cumulative_chart(publishable_dataset(latest), history, history_index, board)
    atomic_json(data_dir / 'cumulative-chart.json', chart)
    pack(latest_path, root / 'data/latest-shards')
    return {'admitted': admitted, 'rejected': rejected, 'deferred': deferred,
            'projects': len(projects), 'pending': latest['coverage']['pendingCandidates']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    args = parser.parse_args()
    print(json.dumps(promote(database=args.database), ensure_ascii=False))
