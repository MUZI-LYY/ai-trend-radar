#!/usr/bin/env python3
"""Resume a curated candidate import, requiring complete 2026 daily coverage.

Search metadata is reused. Per-repository checkpoints live in ignored work/;
publication happens only with --publish, after validating the combined dataset.
"""
import argparse
import concurrent.futures
import datetime as dt
import json
from pathlib import Path

from collect import ROOT, atomic_json, collect_one, period_total
from backfill_history import merge_projects, missing_dates, save_history
from ranking import period_starts
from validate_data import validate_dataset, validate_history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=int, default=600)
    parser.add_argument('--workers', type=int, default=5)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    latest_path = ROOT / 'public/data/latest.json'
    latest = json.loads(latest_path.read_text())
    candidates = json.loads((ROOT / 'data/candidates-2026.json').read_text())['repositories']
    editorial = json.loads((ROOT / 'data/editorial.json').read_text())
    end = latest['periodEnd']
    start = '2026-01-01'
    existing = {p['id']: p for p in latest['projects']}
    excluded = set(json.loads((ROOT / 'data/excluded.json').read_text()))
    selected = [r for r in candidates if r['id'] not in existing and r['full_name'].lower() not in excluded][:max(0, args.target - len(existing))]
    directory = ROOT / 'work/expansion-2026' / end
    directory.mkdir(parents=True, exist_ok=True)

    def work(repo):
        path = directory / f'{repo["id"]}.json'
        if path.exists():
            project = json.loads(path.read_text())
            if not project.get('editorial') and not project.get('profileSource'):
                from source_profile import build_source_profile
                project.update(build_source_profile(project, project.get('readme', '')))
                atomic_json(path, project)
            return project
        project = collect_one(repo['full_name'], None, editorial, end, min(period_starts(end).values()), repo=repo)
        if not project:
            raise ValueError('Repository is not eligible')
        project['history'] = [d for d in project['history'] if max(start, project['createdAt'][:10]) <= d['date'] <= end]
        days = {d['date']: d['stars'] for d in project['history']}
        missing = missing_dates(days, start, end, project['createdAt'])
        if missing or project['historyStatus'] != 'ok':
            raise ValueError(f'{len(missing)} missing source days')
        project['metrics'] = {period: period_total(days, first, end, project['createdAt']) for period, first in period_starts(end).items()}
        atomic_json(path, project)
        return project

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(work, repo): repo for repo in selected}
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            try:
                project = future.result()
                existing[project['id']] = project
                print(f'{len(existing)} projects: {project["fullName"]}; {len(project["history"])} days', flush=True)
            except Exception as error:
                failures.append({'fullName': repo['full_name'], 'error': str(error)})
                print(f'Failed {repo["full_name"]}: {error}', flush=True)
    print(json.dumps({'projects': len(existing), 'failures': failures}, ensure_ascii=False), flush=True)
    if not args.publish:
        return
    if failures or len(existing) < args.target:
        raise SystemExit('Target not complete; checkpoints retained and published data untouched')
    projects = sorted(existing.values(), key=lambda p: (-p['stars'], p['fullName'].lower()))
    payload = {**latest, 'projects': projects, 'completedAt': dt.datetime.now(dt.timezone.utc).isoformat()}
    validate_dataset(payload)
    history = json.loads((ROOT / 'public/data/history.json').read_text())
    history = merge_projects(history, projects, start, end)
    for project in history['projects']:
        if missing_dates({d['date']: d['stars'] for d in project['days']}, start, end, project['createdAt']):
            raise SystemExit('Incomplete 2026 coverage: ' + project['fullName'])
    dates = sorted({d['date'] for p in history['projects'] for d in p['days']})
    validate_history(history, {'dates': dates, 'start': dates[0], 'end': dates[-1],
                               **{k: history[k] for k in ('source', 'scope', 'generatedAt')}}, payload)
    save_history(history, ROOT / 'public/data')
    atomic_json(latest_path, payload)


if __name__ == '__main__':
    main()
