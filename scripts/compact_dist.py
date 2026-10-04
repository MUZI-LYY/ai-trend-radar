#!/usr/bin/env python3
"""Replace deployed daily snapshots with equivalent compact observations."""
import argparse
import json
from pathlib import Path

from compact_snapshot import compact
from pack_history import unpack as unpack_history
from pack_latest import write_json
from ranking import chart_entries


def compact_dist(directory):
    directory = Path(directory)
    snapshots = sorted((directory / 'data/snapshots').glob('*.json'))
    latest = json.loads((directory / 'data/latest.json').read_text())
    before = after = 0
    for path in snapshots:
        full = json.loads(path.read_text())
        reduced = compact(full, latest)
        if chart_entries([full]) != chart_entries([reduced]):
            raise ValueError('Daily chart changed during compaction: ' + path.name)
        before += path.stat().st_size
        write_json(path, reduced)
        after += path.stat().st_size
    history_path = directory / 'data/history.json'
    recovered, _ = unpack_history(directory / 'data/history.json.gz',
                                  directory / 'data/history-pack.json')
    if recovered != history_path.read_bytes():
        raise ValueError('Packed deployment history differs from the complete source')
    if not (directory / 'data/latest-bootstrap.json').exists() or not list(
            (directory / 'data/latest-list').glob('*.json')):
        raise ValueError('Current list shards missing from deployment')
    history_path.unlink()
    (directory / 'data/latest.json').unlink()
    github_dir = directory / 'data/github'
    if github_dir.exists():
        github_history = github_dir / 'history.json'
        github_recovered, _ = unpack_history(github_dir / 'history.json.gz',
                                             github_dir / 'history-pack.json')
        if github_recovered != github_history.read_bytes():
            raise ValueError('Packed GitHub history differs from the complete source')
        github_history.unlink()
    return {'snapshots': len(snapshots), 'originalBytes': before, 'deployedBytes': after}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'dist')
    args = parser.parse_args()
    print(json.dumps(compact_dist(args.directory)))
