#!/usr/bin/env python3
"""Keep daily observations for the website without repeated README and history."""
import argparse
import json
from pathlib import Path

from pack_latest import write_json

DROP = {'readme', 'sourceExcerpts', 'profileSource', 'readmeSha', 'readmeFetchedAt'}


def compact(data):
    return {**data, 'projects': [
        {**{key: value for key, value in project.items() if key not in DROP and key != 'history'},
         'history': []}
        for project in data['projects']]}


def verify(full, reduced):
    if reduced != compact(full):
        raise ValueError('Compact snapshot differs from its complete source')
    return len(reduced['projects'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    full = json.loads(args.source.read_text())
    reduced = compact(full)
    verify(full, reduced)
    write_json(args.output, reduced)
    print(json.dumps({'projects': len(reduced['projects']),
                      'sourceBytes': args.source.stat().st_size,
                      'compactBytes': args.output.stat().st_size}))
