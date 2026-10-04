#!/usr/bin/env python3
"""Keep daily observations and visible Star curves without repeated source text."""
import argparse
import json
from pathlib import Path

from pack_latest import write_json

DROP = {'sourceExcerpts', 'profileSource', 'readmeSha', 'readmeFetchedAt'}
HISTORY_DAYS = 365


def compact(data, latest=None):
    profiles = {project['id']: project for project in (latest or {}).get('projects', [])}

    def compact_project(project):
        profile = profiles.get(project['id'])
        hydrated = profile and not (project.get('editorial') and not profile.get('editorial'))
        removable = DROP | ({'readme'} if hydrated and profile.get('readme') else set())
        return {**{key: value for key, value in project.items() if key not in removable and key != 'history'},
                'history': project.get('history', [])[-HISTORY_DAYS:]}

    return {**data, 'projects': [
        compact_project(project)
        for project in data['projects']]}


def verify(full, reduced, latest=None):
    if reduced != compact(full, latest):
        raise ValueError('Compact snapshot differs from its complete source')
    return len(reduced['projects'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--latest', type=Path, help='Current profile data used by the website')
    args = parser.parse_args()
    full = json.loads(args.source.read_text())
    latest = json.loads(args.latest.read_text()) if args.latest else None
    reduced = compact(full, latest)
    verify(full, reduced, latest)
    write_json(args.output, reduced)
    print(json.dumps({'projects': len(reduced['projects']),
                      'sourceBytes': args.source.stat().st_size,
                      'compactBytes': args.output.stat().st_size}))
