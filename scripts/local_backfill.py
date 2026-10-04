#!/usr/bin/env python3
"""Checkpointed local review of the discovery backlog.

This staging database is deliberately separate from published rankings. A row is
only published after the site exporter has validated and incorporated it.
"""
import argparse
import concurrent.futures
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collect
from discover import MIN_STARS, TOPICS, load_state, pending_candidates
from github_metadata import batch_metadata
from ranking import period_starts

DEFAULT_DB = ROOT / 'data/local-backfill.sqlite3'
RELEVANCE = re.compile(r'\b(ai|llm|rag|gpt|ml|mcp)\b|artificial.intelligence|machine.learning|deep.learning|diffusion|neural|语音|智能|模型')


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, status TEXT NOT NULL,
        attempted_at TEXT NOT NULL, retry_after TEXT, project BLOB, error TEXT)''')
    db.commit()
    return db


def select_pending(discovery, tracked, excluded, db, limit, today):
    reviewed = {row[0]: (row[1], row[2]) for row in
                db.execute('SELECT id,status,retry_after FROM reviews')}
    result = []
    for candidate in pending_candidates(discovery, tracked=tracked, excluded=excluded, today=today):
        status, retry_after = reviewed.get(candidate['id'], (None, None))
        if status in ('admitted', 'rejected') or (retry_after or '') > today:
            continue
        result.append(candidate)
        if len(result) == limit:
            break
    return result


def save_review(db, candidate, status, project=None, error=None, today=None):
    if status not in ('admitted', 'rejected', 'retry'):
        raise ValueError('Invalid review status')
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    retry_after = (dt.date.fromisoformat(today) + dt.timedelta(days=1)).isoformat() if status == 'retry' else None
    payload = zlib.compress(json.dumps(project, ensure_ascii=False, separators=(',', ':')).encode(), 6) if project else None
    db.execute('''INSERT INTO reviews (id,full_name,status,attempted_at,retry_after,project,error)
                  VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                  full_name=excluded.full_name,status=excluded.status,
                  attempted_at=excluded.attempted_at,retry_after=excluded.retry_after,
                  project=excluded.project,error=excluded.error''',
               (candidate['id'], candidate['fullName'], status, today, retry_after, payload, error))
    db.commit()


def counts(db):
    return dict(db.execute('SELECT status,COUNT(*) FROM reviews GROUP BY status'))


def review_one(candidate, metadata, editorial, end, year_start):
    name = candidate['fullName']
    repo = metadata.get(name.lower()) or collect.api('repos/' + name)
    if (repo['id'] != candidate['id'] or repo['stargazers_count'] < MIN_STARS
            or repo.get('private') or repo.get('fork') or repo.get('disabled') or repo.get('archived')):
        return 'rejected', None
    content = ' '.join([repo['full_name'], repo.get('description') or '', *(repo.get('topics') or [])]).lower()
    if not set(repo.get('topics') or []) & set(TOPICS) and not RELEVANCE.search(content):
        return 'rejected', None
    project = collect.collect_one(name, None, editorial, end, year_start, repo=repo)
    if not project or project['historyStatus'] != 'ok':
        return 'retry', None
    project['statsThrough'] = end
    return 'admitted', project


def run(db_path=DEFAULT_DB, batch_size=200, rest_budget=4000, workers=4):
    if batch_size < 1 or rest_budget < 1 or workers < 1:
        raise ValueError('Batch size, REST budget and workers must be positive')
    db = connect(db_path)
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date().isoformat()
    end = (now.date() - dt.timedelta(days=1)).isoformat()
    year_start = min(period_starts(end).values())
    latest = json.loads((ROOT / 'public/data/latest.json').read_text())
    discovery = load_state()
    excluded_path = ROOT / 'data/excluded.json'
    excluded = json.loads(excluded_path.read_text()) if excluded_path.exists() else []
    editorial_path = ROOT / 'data/editorial.json'
    editorial = json.loads(editorial_path.read_text()) if editorial_path.exists() else {}
    selected = select_pending(discovery, latest['projects'], excluded, db, batch_size, today)
    if not selected:
        print(json.dumps({'selected': 0, 'staged': counts(db)}, ensure_ascii=False), flush=True)
        return
    collect.REST_REQUEST_LIMIT = rest_budget
    collect._rest_requests = 0
    names = [candidate['fullName'] for candidate in selected]
    metadata = batch_metadata(names)
    outcomes = {'admitted': 0, 'rejected': 0, 'retry': 0, 'deferred': 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(review_one, candidate, metadata, editorial, end, year_start): candidate
                   for candidate in selected}
        for future in concurrent.futures.as_completed(futures):
            candidate = futures[future]
            try:
                status, project = future.result()
                save_review(db, candidate, status, project, today=today)
            except collect.RequestBudgetExceeded:
                outcomes['deferred'] += 1
                continue
            except collect.RepositoryUnavailable:
                status = 'rejected'
                save_review(db, candidate, status, today=today)
            except Exception as error:
                status = 'retry'
                save_review(db, candidate, status, error=str(error)[:240], today=today)
            outcomes[status] += 1
    print(json.dumps({'selected': len(selected), 'outcomes': outcomes,
                      'staged': counts(db), 'restRequests': collect._rest_requests,
                      'sourceDate': end, 'database': str(db_path)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path(os.environ.get('RADAR_BACKFILL_DB', DEFAULT_DB)))
    parser.add_argument('--batch-size', type=int, default=200)
    parser.add_argument('--rest-budget', type=int, default=4000)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    run(args.db, args.batch_size, args.rest_budget, args.workers)
