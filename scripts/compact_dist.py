#!/usr/bin/env python3
"""Replace deployed daily snapshots with equivalent compact observations."""
import argparse
import json
from pathlib import Path

from compact_snapshot import compact
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
    return {'snapshots': len(snapshots), 'originalBytes': before, 'deployedBytes': after}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'dist')
    args = parser.parse_args()
    print(json.dumps(compact_dist(args.directory)))
