#!/usr/bin/env python3
"""Merge a local Star-history checkpoint into a newer GitHub repository ledger.

Keep the newer ledger's discovered repositories and metadata. Only transfer
official daily Star observations for matching immutable GitHub repository IDs.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from collect import atomic_json, period_total
from collect_github import HISTORY_START
from ranking import period_starts


def merge(checkpoint, target):
    old = json.loads(checkpoint.read_text())
    new = json.loads(target.read_text())
    by_id = {project['id']: project for project in old['projects']}
    end = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    changed = completed = 0
    for project in new['projects']:
        source = by_id.get(project['id'])
        if not source or source.get('createdAt') != project.get('createdAt'):
            continue
        current = {day['date']: day['stars'] for day in project.get('history', [])}
        incoming = {day['date']: day['stars'] for day in source.get('history', [])}
        if not incoming:
            continue
        # The newer upstream ledger takes precedence if a date was refreshed
        # there while this checkpoint was being collected.
        combined = {**incoming, **current}
        if combined == current and project.get('statsThrough') == end:
            continue
        project['history'] = [{'date': date, 'stars': stars}
                              for date, stars in sorted(combined.items())]
        starts = period_starts(end)
        metrics = {period: period_total(combined, start, end, project['createdAt'])
                   for period, start in starts.items()}
        project['metrics'] = metrics
        complete = (period_total(combined, HISTORY_START, end, project['createdAt']) is not None
                    and all(value is not None for value in metrics.values()))
        project['historyStatus'] = 'ok'
        project['statsThrough'] = end if complete else None
        project['warnings'] = [] if complete else ['早期 Star 历史未补齐']
        changed += 1
        completed += complete
    if changed:
        new['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
        atomic_json(target, new)
    print(f'merged history for {changed} repositories; {completed} now complete through {end}')
    return changed, completed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    merge(args.checkpoint, args.target)
