#!/usr/bin/env python3
"""Export local review checkpoints as small, verifiable Git-friendly shards."""
import argparse
import gzip
import hashlib
import json
import sqlite3
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data/local-backfill.sqlite3'
DEFAULT_OUTPUT = ROOT / 'data/backfill-shards'
SHARDS = 64


def export(db_path=DEFAULT_DB, output=DEFAULT_OUTPUT):
    db = sqlite3.connect(f'file:{Path(db_path)}?mode=ro', uri=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    handles = [gzip.open(output / f'{index:02x}.jsonl.gz.tmp', 'wt', encoding='utf-8',
                         compresslevel=6) for index in range(SHARDS)]
    counts = [0] * SHARDS
    status_counts = {}
    try:
        for row in db.execute('SELECT id,full_name,status,attempted_at,retry_after,project,error FROM reviews ORDER BY id'):
            repo_id, name, status, attempted, retry_after, packed, error = row
            entry = {'id': repo_id, 'fullName': name, 'status': status,
                     'attemptedAt': attempted, 'retryAfter': retry_after}
            if packed is not None:
                entry['project'] = json.loads(zlib.decompress(packed))
            if error:
                entry['error'] = error
            index = repo_id % SHARDS
            handles[index].write(json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + '\n')
            counts[index] += 1
            status_counts[status] = status_counts.get(status, 0) + 1
    finally:
        for handle in handles:
            handle.close()
        db.close()
    files = []
    for index, count in enumerate(counts):
        temporary = output / f'{index:02x}.jsonl.gz.tmp'
        destination = output / f'{index:02x}.jsonl.gz'
        temporary.replace(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        files.append({'file': destination.name, 'count': count, 'sha256': digest})
    manifest = {'schemaVersion': 1, 'shardCount': SHARDS, 'reviews': sum(counts),
                'statuses': status_counts, 'files': files}
    temporary = output / 'manifest.json.tmp'
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(output / 'manifest.json')
    return manifest


def verify(output=DEFAULT_OUTPUT):
    output = Path(output)
    manifest = json.loads((output / 'manifest.json').read_text())
    if manifest.get('shardCount') != SHARDS or len(manifest.get('files', [])) != SHARDS:
        raise ValueError('Invalid shard manifest')
    total = 0
    seen = set()
    for index, item in enumerate(manifest['files']):
        if item['file'] != f'{index:02x}.jsonl.gz':
            raise ValueError('Shard order mismatch')
        path = output / item['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Shard checksum mismatch: ' + item['file'])
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream]
        if len(rows) != item['count'] or any(row['id'] % SHARDS != index for row in rows):
            raise ValueError('Shard contents mismatch: ' + item['file'])
        for row in rows:
            if row['id'] in seen:
                raise ValueError('Duplicate repository ID: ' + str(row['id']))
            seen.add(row['id'])
            if row['status'] == 'admitted' and (
                    row.get('project', {}).get('id') != row['id']
                    or row['project'].get('historyStatus') != 'ok'):
                raise ValueError('Invalid admitted project: ' + str(row['id']))
        total += len(rows)
    if total != manifest['reviews']:
        raise ValueError('Review count mismatch')
    return manifest


def restore(output, db_path):
    manifest = verify(output)
    from local_backfill import connect
    db = connect(db_path)
    if db.execute('SELECT 1 FROM reviews LIMIT 1').fetchone():
        db.close()
        raise ValueError('Restore requires an empty review database')
    for item in manifest['files']:
        with gzip.open(Path(output) / item['file'], 'rt', encoding='utf-8') as stream:
            rows = []
            for line in stream:
                entry = json.loads(line)
                project = entry.get('project')
                packed = zlib.compress(json.dumps(project, ensure_ascii=False, separators=(',', ':')).encode(), 6) if project else None
                rows.append((entry['id'], entry['fullName'], entry['status'], entry['attemptedAt'],
                             entry.get('retryAfter'), packed, entry.get('error')))
        db.executemany('''INSERT INTO reviews
                         (id,full_name,status,attempted_at,retry_after,project,error)
                         VALUES (?,?,?,?,?,?,?)''', rows)
        db.commit()
    db.close()
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--restore-to', type=Path)
    args = parser.parse_args()
    if args.verify_only and args.restore_to:
        parser.error('--verify-only and --restore-to are mutually exclusive')
    result = (restore(args.output, args.restore_to) if args.restore_to else
              verify(args.output) if args.verify_only else export(args.db, args.output))
    print(json.dumps(result,
                     ensure_ascii=False, separators=(',', ':')))
