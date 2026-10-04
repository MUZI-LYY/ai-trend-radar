#!/usr/bin/env python3
"""Fill missing official Star histories without refetching known repository metadata.

This is a resumable maintenance command for the independent GitHub board. It
checkpoints the ledger between small batches and stops before the API reserve.
Set GITHUB_TOKEN or use a GitHub CLI authenticated session to make requests.
"""
import argparse
import datetime as dt
import json

from collect import atomic_json
from collect_github import EXTRAS, RATE_BUDGET, RateLimitExceeded, collect_history, needs_history


def backfill(limit=0, checkpoint=25, source=EXTRAS):
    ledger = json.loads(source.read_text())
    end = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    projects = ledger['projects']
    # Missing histories first; newer repositories need fewer history pages.
    due = [project for project in projects if project['stars'] >= 10 and needs_history(project, end)]
    empty = [project for project in due if not project.get('history')]
    empty.sort(key=lambda project: project['createdAt'], reverse=True)
    # An unavailable endpoint should not consume every later run before
    # repositories that have never had a history request.
    empty.sort(key=lambda project: bool(project.get('historyAttemptedAt')))
    due = empty + [project for project in due if project.get('history')]
    if limit:
        due = due[:limit]
    print(f'{len(due)} repositories due for Star history through {end}', flush=True)

    attempted = complete = changed = 0

    def save():
        ledger['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
        atomic_json(source, ledger)
        print(f'checkpoint attempted={attempted} complete={complete} '
              f'history_remaining={RATE_BUDGET.remaining.get("history", "unknown")}', flush=True)

    try:
        for project in due:
            repo = {'full_name': project['fullName'], 'created_at': project['createdAt']}
            try:
                status, metrics, history = collect_history(repo, project, end)
            except RateLimitExceeded as error:
                print(f'paused: {error}', flush=True)
                break
            project['historyStatus'] = status
            project['metrics'] = metrics
            project['history'] = history
            project['historyAttemptedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            project['statsThrough'] = end if status == 'ok' else None
            valid = status == 'ok' and all(value is not None for value in metrics.values())
            verified = valid and not needs_history(project, end)
            project['warnings'] = ([] if verified else
                                   ['早期 Star 历史未补齐'] if valid else
                                   ['部分周期 Star 历史暂不可用'] if status == 'ok' else
                                   ['Star 历史暂不可用'])
            attempted += 1
            complete += verified
            if not verified:
                print(f'incomplete history: {project["fullName"]} ({status})', flush=True)
            changed += 1
            if changed >= checkpoint:
                save()
                changed = 0
    finally:
        if changed:
            save()
    print(f'finished attempted={attempted} complete={complete} '
          f'remaining_due={sum(p["stars"] >= 10 and needs_history(p, end) for p in projects)}', flush=True)
    return attempted, complete


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Maximum repositories, 0 means until quota reserve')
    parser.add_argument('--checkpoint', type=int, default=25)
    args = parser.parse_args()
    if args.limit < 0 or args.checkpoint < 1:
        parser.error('limit must be nonnegative and checkpoint positive')
    backfill(args.limit, args.checkpoint)
