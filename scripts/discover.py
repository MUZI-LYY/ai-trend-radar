#!/usr/bin/env python3
"""Discover AI repositories into a resumable queue, independently of collection.

Only repository-level metadata is stored. Search/Trending numbers are candidate
signals and never become ranking metrics. Completed searches rotate across topics,
star bands and sort orders; oversized searches are split before further paging.
"""
import argparse
import datetime as dt
import json
import math
import re
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / 'data/discovery.json'
TOPICS = (
    'llm', 'ai-agents', 'generative-ai', 'machine-learning', 'rag',
    'mcp', 'text-to-speech', 'computer-vision', 'deep-learning',
    'large-language-models', 'diffusion', 'reinforcement-learning',
    'nlp', 'speech-recognition', 'ai-tools', 'ai-coding',
    'text-to-image', 'video-generation', 'fine-tuning', 'llm-inference',
    'multimodal', 'ai-assistant', 'agentic-ai', 'retrieval-augmented-generation',
)
PAGE_SIZE = 100
MIN_DATE = '2008-01-01'


def save_state(state, path=STATE_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(path)


def load_state(path=STATE_PATH):
    if not Path(path).exists():
        return {'schemaVersion': 1, 'candidates': {}, 'tasks': [], 'cycle': 0}
    state = json.loads(Path(path).read_text())
    if state.get('schemaVersion') != 1:
        raise ValueError('Unsupported discovery queue schema')
    return state


def initial_tasks(today, created_start=None, created_end=None):
    # Topics rotate before going deeper into any one subject. The lower band also
    # gives emerging repositories space instead of filling every slot with giants.
    return [dict(topic=topic, minStars=low, maxStars=high, sort=sort, page=1,
                 createdStart=created_start or MIN_DATE, createdEnd=created_end or today)
            for low, high in ((1000, 10000000), (100, 999), (10, 99))
            for sort in ('stars', 'updated') for topic in TOPICS]


def search_query(task):
    return (f'topic:{task["topic"]} stars:{task["minStars"]}..{task["maxStars"]} '
            f'created:{task["createdStart"]}..{task["createdEnd"]} '
            'archived:false fork:false')


def split_task(task):
    """Keep search result windows below GitHub's 1,000-result ceiling."""
    low, high = task['minStars'], task['maxStars']
    if low < high:
        # Star counts are strongly skewed; geometric splits reach useful ranges
        # without spending many whole cycles probing millions of nonexistent stars.
        middle = math.isqrt(low * high)
        return [{**task, 'maxStars': middle, 'page': 1},
                {**task, 'minStars': middle + 1, 'page': 1}]
    start, end = map(dt.date.fromisoformat, (task['createdStart'], task['createdEnd']))
    if start < end:
        middle = start + (end - start) // 2
        return [{**task, 'createdEnd': middle.isoformat(), 'datePartitioned': True, 'page': 1},
                {**task, 'createdStart': (middle + dt.timedelta(days=1)).isoformat(),
                 'datePartitioned': True, 'page': 1}]
    return []  # A single star value and creation day cannot be split further.


def merge_candidate(state, repo, source, today):
    name = repo.get('full_name', '')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', name) or type(repo.get('id')) is not int:
        return False
    if repo.get('private') or repo.get('fork') or repo.get('disabled') or repo.get('archived'):
        return False
    key = str(repo['id'])
    old = state['candidates'].get(key, {})
    sources = sorted(set(old.get('sources', []) + [source]))
    state['candidates'][key] = {
        **old, 'id': repo['id'], 'fullName': name,
        'stars': repo.get('stargazers_count', 0),
        'description': repo.get('description') or '', 'topics': repo.get('topics', []),
        'createdAt': repo.get('created_at'), 'pushedAt': repo.get('pushed_at'),
        'firstDiscovered': old.get('firstDiscovered', today), 'lastDiscovered': today,
        'sources': sources, 'status': old.get('status', 'pending'),
    }
    return not old


def pending_candidates(state, tracked=(), excluded=(), today=None):
    """Fair topic lanes, mixing established projects and recent small projects.

    Exclude known repository IDs too, so renamed repositories do not repeatedly
    consume admission slots. A failed candidate waits before another attempt.
    """
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    names = {p['fullName'].lower() for p in tracked}
    ids = {p['id'] for p in tracked}
    excluded = {name.lower() for name in excluded}
    lanes = {}
    for candidate in state['candidates'].values():
        if (candidate['id'] in ids or candidate['fullName'].lower() in names | excluded
                or candidate.get('status') == 'rejected'
                or candidate.get('retryAfter', '') > today):
            continue
        # A source lane remains stable even if a later search finds more topics.
        topic = next((t for t in TOPICS if 'topic:' + t in candidate['sources']), 'other')
        band = 'emerging' if candidate.get('stars', 0) < 1000 else 'established'
        lanes.setdefault((band, topic), []).append(candidate)
    for (band, _), items in lanes.items():
        items.sort(key=lambda c: (c.get('createdAt') or '', c.get('stars', 0), c['fullName'])
                   if band == 'emerging' else (c.get('stars', 0), c['fullName']), reverse=True)
    result = []
    while any(lanes.values()):
        for key in sorted(lanes):
            if lanes[key]:
                result.append(lanes[key].pop(0))
    return result


def record_attempt(state, name, outcome, today=None):
    if outcome not in ('admitted', 'rejected', 'retry'):
        raise ValueError('Unknown candidate outcome')
    date = dt.date.fromisoformat(today) if today else dt.datetime.now(dt.timezone.utc).date()
    for candidate in state['candidates'].values():
        if candidate['fullName'].lower() == name.lower():
            candidate.update(status=outcome, lastAttempt=date.isoformat(),
                             attempts=candidate.get('attempts', 0) + 1)
            candidate.pop('retryAfter', None)
            if outcome == 'retry':
                candidate['retryAfter'] = (date + dt.timedelta(days=7)).isoformat()


def discover(state, request, max_requests=24, today=None, persist=None,
             pause=time.sleep, interval=2.2, created_start=None, created_end=None):
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    config = {'createdStart': created_start, 'createdEnd': created_end, 'topics': list(TOPICS)}
    if state.get('config') != config or not state['tasks']:
        state.update(config=config, tasks=initial_tasks(today, created_start, created_end),
                     cycle=state.get('cycle', 0) + 1)
    report = {'date': today, 'requests': 0, 'added': 0, 'splits': 0, 'completed': 0,
              'errors': [], 'truncated': []}
    for _ in range(max_requests):
        if not state['tasks']:
            break
        if report['requests']:
            pause(interval)
        task = state['tasks'].pop(0)
        if not created_end and not task.get('datePartitioned'):
            # A long pagination cycle must not freeze every query to its first day.
            # Explicit historical bounds and split date intervals remain fixed.
            task['createdEnd'] = today
        query = search_query(task)
        report['requests'] += 1
        try:
            response = request('search/repositories?' + urlencode({
                'q': query, 'sort': task['sort'], 'order': 'desc',
                'per_page': PAGE_SIZE, 'page': task['page']}))
            if (not isinstance(response.get('items'), list)
                    or type(response.get('total_count')) is not int or response['total_count'] < 0):
                raise ValueError('Unexpected repository search response')
            for repo in response['items']:
                report['added'] += merge_candidate(state, repo, 'topic:' + task['topic'], today)
            if response.get('incomplete_results'):
                # Retain the cursor; partial search results cannot prove completion.
                state['tasks'].append(task)
                report['errors'].append({'query': query, 'error': 'incomplete_results'})
            elif response['total_count'] > 1000:
                children = split_task(task)
                if children:
                    state['tasks'].extend(children)
                    report['splits'] += 1
                elif task['page'] < 10 and len(response['items']) == PAGE_SIZE:
                    state['tasks'].append({**task, 'page': task['page'] + 1})
                else:
                    report['truncated'].append(query)
                    state.setdefault('coverageWarnings', {})[query] = today
            elif task['page'] * PAGE_SIZE < response['total_count']:
                if not response['items']:
                    raise ValueError('Empty search page before reported end')
                state['tasks'].append({**task, 'page': task['page'] + 1})
            else:
                report['completed'] += 1
        except Exception as error:
            state['tasks'].append(task)
            report['errors'].append({'query': query, 'error': str(error)[:240]})
            # Stop after transport/rate failures; preserve the queue for next run.
            break
        finally:
            state['lastRun'] = report
            state['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            if persist:
                persist(state)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-requests', type=int, default=24)
    parser.add_argument('--state', type=Path, default=STATE_PATH)
    parser.add_argument('--created-start')
    parser.add_argument('--created-end')
    args = parser.parse_args()
    for date in (args.created_start, args.created_end):
        if date:
            dt.date.fromisoformat(date)
    if args.max_requests < 1:
        parser.error('--max-requests must be positive')
    if args.created_start and args.created_end and args.created_start > args.created_end:
        parser.error('Creation date range is reversed')
    from collect import api
    state = load_state(args.state)
    report = discover(state, api, args.max_requests, persist=lambda s: save_state(s, args.state),
                      created_start=args.created_start, created_end=args.created_end)
    print(json.dumps({**report, 'candidates': len(state['candidates']),
                      'pendingSearchPages': len(state['tasks'])}, ensure_ascii=False), flush=True)
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
