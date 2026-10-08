#!/usr/bin/env python3
"""Apply the minimum cumulative Star count to current and saved public data."""
import argparse
import datetime as dt
import json
import re
import sqlite3
import zlib
from pathlib import Path

from backfill_history import update_history
from build_fast_data import publishable_dataset
from build_tenure_index import cumulative_chart
from collect import atomic_json, collection_coverage, is_current
from discover import MIN_STARS, load_state, save_state
from export_backfill import export as export_backfill
from pack_latest import pack
from ranking import chart_entry
from snapshot_io import read_snapshot, snapshot_paths, write_snapshot

ROOT = Path(__file__).resolve().parents[1]


def promote_reviewed_candidates(state, db_path):
    """A verified current count supersedes an older discovery-search count."""
    if not db_path.exists():
        return 0
    promoted = 0
    with sqlite3.connect(db_path) as db:
        for identity, packed in db.execute('SELECT id,project FROM reviews WHERE project IS NOT NULL'):
            candidate = state['candidates'].get(str(identity))
            if not candidate:
                continue
            stars = json.loads(zlib.decompress(packed)).get('stars', 0)
            if stars >= MIN_STARS and candidate.get('stars', 0) < MIN_STARS:
                candidate['stars'] = stars
                promoted += 1
    return promoted


def prune_discovery(state):
    removed = {int(identity) for identity, candidate in state['candidates'].items()
               if candidate.get('stars', 0) < MIN_STARS}
    state['candidates'] = {identity: candidate for identity, candidate in state['candidates'].items()
                           if int(identity) not in removed}
    state['tasks'] = [task for task in state.get('tasks', [])
                      if task.get('maxStars') is None or task['maxStars'] >= MIN_STARS]
    if state.get('config'):
        state['config']['minStars'] = MIN_STARS
    state['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    return removed


def clean_dataset(data, removed_current_ids=()):
    before = len(data['projects'])
    data['projects'] = [project for project in data['projects']
                        if project['stars'] >= MIN_STARS and project['id'] not in removed_current_ids]
    names = {project['fullName'].lower() for project in data['projects']}
    data['missingHistoryRepositories'] = [name for name in data.get('missingHistoryRepositories', [])
                                          if name.lower() in names]
    data['warnings'] = [warning for warning in data.get('warnings', [])
                        if not re.match(r'^\d+ 个(?:已收录项目|项目)', warning)]
    stale = sum(not is_current(project, data['periodEnd']) for project in data['projects'])
    if stale:
        data['warnings'].append(f'{stale} 个已收录项目待更新或暂缺完整本期数据，后续批次继续处理；未更新指标不参榜。')
    if data['missingHistoryRepositories']:
        data['warnings'].append(f'{len(data["missingHistoryRepositories"])} 个项目的部分 Star 历史不可用，缺失指标不参与对应榜单。')
    data['warnings'] = sorted(set(data['warnings']))
    data['scope'] = f'本站收录累计至少 {MIN_STARS} Star 的 AI 相关公开仓库，并非 GitHub 全量项目。'
    return before - len(data['projects'])


def prune_local_reviews(db_path, removed_candidate_ids):
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as db:
        rows = db.execute('SELECT id,project FROM reviews').fetchall()
        drop = set()
        for identity, packed in rows:
            stars = json.loads(zlib.decompress(packed)).get('stars', 0) if packed else None
            if stars is not None and stars >= MIN_STARS:
                continue
            if identity in removed_candidate_ids or stars is not None and stars < MIN_STARS:
                drop.add(identity)
        db.executemany('DELETE FROM reviews WHERE id=?', ((identity,) for identity in drop))
        db.commit()
        remaining = db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
    export_backfill(db_path)
    return {'removed': len({identity for identity, _ in rows} & drop), 'remaining': remaining}


def run(root=ROOT, prune_local=False):
    data_dir = root / 'public/data'
    state_path = root / 'data/discovery.json'
    state = load_state(state_path)
    promoted = promote_reviewed_candidates(state, root / 'data/local-backfill.sqlite3') if prune_local else 0
    removed_candidates = prune_discovery(state)
    save_state(state, state_path)

    latest_path = data_dir / 'latest.json'
    latest = json.loads(latest_path.read_text())
    removed_current_ids = {project['id'] for project in latest['projects'] if project['stars'] < MIN_STARS}
    latest_removed = clean_dataset(latest)
    excluded_path = root / 'data/excluded.json'
    excluded = json.loads(excluded_path.read_text()) if excluded_path.exists() else []
    latest['coverage'] = collection_coverage(latest['projects'], state, excluded, latest['periodEnd'])
    atomic_json(latest_path, latest)

    entries = {}
    removed_archived = 0
    snapshots = snapshot_paths(data_dir / 'snapshots')
    for path in snapshots:
        snapshot = read_snapshot(path)
        removed_archived += clean_dataset(snapshot, removed_current_ids)
        # Preserve archive coverage for the saved-board completeness rule. Dated
        # discovery counts cannot be reconstructed after changing the threshold.
        updated = sum(is_current(project, snapshot['periodEnd']) for project in snapshot['projects'])
        count = len(snapshot['projects'])
        snapshot['coverage'] = {
            'discoveredRepositories': count, 'trackedRepositories': count,
            'updatedRepositories': updated, 'pendingCandidates': 0,
            'pendingUpdates': count - updated, 'sourceDate': snapshot['periodEnd'],
            'totalLimit': None,
        }
        write_snapshot(path, snapshot)
        entry = chart_entry(snapshot)
        entries.setdefault(entry['date'], entry)
    board = {'chartSize': 30, 'entries': [entries[day] for day in sorted(entries)]}
    atomic_json(data_dir / 'board-history.json', board)

    history = update_history(latest['projects'], latest['periodEnd'], data_dir)
    history_index = json.loads((data_dir / 'history-index.json').read_text())
    chart = cumulative_chart(publishable_dataset(latest), history, history_index, board)
    atomic_json(data_dir / 'cumulative-chart.json', chart)
    pack(latest_path, root / 'data/latest-shards')

    local = prune_local_reviews(root / 'data/local-backfill.sqlite3', removed_candidates) if prune_local else None
    return {'minimumStars': MIN_STARS, 'removedCandidates': len(removed_candidates),
            'promotedAfterVerification': promoted,
            'removedLatest': latest_removed, 'removedArchiveObservations': removed_archived,
            'latestProjects': len(latest['projects']), 'pendingCandidates': latest['coverage']['pendingCandidates'],
            'snapshots': len(snapshots), 'localReviews': local}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prune-local-backfill', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(prune_local=args.prune_local_backfill), ensure_ascii=False))
