#!/usr/bin/env python3
"""Discover public AI repository candidates with official GitHub Search metadata.

This creates a reviewable candidate file only. It never changes published rankings.
"""
import calendar
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/candidates-2026.json'
TOPICS = ['llm', 'ai-agents', 'generative-ai', 'rag', 'large-language-models',
          'machine-learning', 'deep-learning', 'text-to-speech', 'diffusion',
          'computer-vision', 'mcp', 'llm-inference', 'ai', 'fine-tuning', 'speech-recognition']
GENERAL_TOOLS = {'snailclimb/javaguide', 'supabase/supabase', 'developer-y/cs-video-courses',
                 'thedaviddias/front-end-checklist', 'netdata/netdata', 'paperless-ngx/paperless-ngx',
                 'drawdb-io/drawdb', 'thealgorithms/c-plus-plus', 'alibaba/nacos', 'pingcap/tidb',
                 'fincept-corporation/finceptterminal', 'cloakhq/cloakbrowser', 'gitleaks/gitleaks',
                 'nautechsystems/nautilus_trader', 'go-kratos/kratos', 'd4vinci/scrapling',
                 'flipped-aurora/gin-vue-admin', 'dolthub/dolt', 'thealgorithms/c', 'qax-os/excelize',
                 'hummingbot/hummingbot', 'nukeop/nuclear', 'realsenseai/librealsense', 'amitness/learning'}
AI_TOPICS = {'llm', 'ai-agents', 'generative-ai', 'rag', 'large-language-models',
             'deep-learning', 'text-to-speech', 'diffusion', 'computer-vision', 'mcp',
             'llm-inference', 'fine-tuning', 'speech-recognition', 'artificial-intelligence',
             'neural-network', 'neural-networks', 'reinforcement-learning', 'nlp',
             'natural-language-processing', 'object-detection', 'text-to-image'}
AI_PATTERN = re.compile(r'\b(ai|llm|llms|gpt|mcp|rag|agentic|chatbot|chatbots|neural|transformer|transformers|diffusion)\b|artificial.intelligence|machine.learning|deep.learning|language.models?|speech.recognition|text.to.speech|computer.vision|reinforcement.learning|智能|大模型|人工智能|语音识别|机器学习|深度学习', re.I)


def api_search(query):
    endpoint = 'search/repositories?' + urlencode({'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': 100})
    for attempt in range(3):
        process = subprocess.run(['gh', 'api', '-X', 'GET', '-H', 'X-GitHub-Api-Version: 2026-03-10', endpoint],
                                 text=True, capture_output=True, timeout=50)
        if process.returncode == 0:
            return json.loads(process.stdout)
        if attempt == 2:
            raise RuntimeError(process.stderr.strip()[:300])
        time.sleep(10 * (attempt + 1))


def is_ai(repo):
    if repo['full_name'].lower() in GENERAL_TOOLS:
        return False
    topics = set(repo.get('topics', []))
    text = ' '.join([repo['full_name'], repo.get('description') or ''])
    return bool(topics & AI_TOPICS or AI_PATTERN.search(text))


def persist(repositories, reports, current_ids, finished=False):
    rows = sorted(repositories.values(), key=lambda r: (-r['stargazers_count'], r['full_name'].lower()))
    if finished:
        # Keep both established popular tools and a substantial 2026-born cohort.
        recent = [r for r in rows if r['created_at'][:4] == '2026'][:180]
        selected = {r['id']: r for r in recent}
        for row in rows:
            if len(selected) >= 650:
                break
            selected.setdefault(row['id'], row)
        rows = sorted(selected.values(), key=lambda r: (-r['stargazers_count'], r['full_name'].lower()))
    payload = {'schemaVersion': 1, 'generatedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
               'source': 'GitHub REST API search/repositories',
               'scope': '真实公开非 fork AI 相关候选仓库；当前已收录 ID 不重复列出。2026 创建月份检索用于补充新项目，历史回溯范围从 2026-01-01 起。',
               'status': 'complete' if finished else 'collecting', 'queries': reports,
               'existingProjectCount': len(current_ids), 'discoveredEligibleCount': len(repositories),
               'repositories': rows}
    temporary = OUT.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(OUT)


def main():
    latest = json.loads((ROOT / 'public/data/latest.json').read_text())
    current_ids = {r['id'] for r in latest['projects']}
    excluded = {r.lower() for r in json.loads((ROOT / 'data/excluded.json').read_text())}
    today = dt.datetime.now(dt.timezone.utc).date()
    queries = [f'topic:{topic} stars:>=150 fork:false archived:false' for topic in TOPICS]
    for month in range(1, min(today.month, 12) + 1):
        first = f'2026-{month:02d}-01'
        last = min(dt.date(2026, month, calendar.monthrange(2026, month)[1]), today).isoformat()
        queries.append(f'AI in:description created:{first}..{last} stars:>=30 fork:false archived:false')
    repositories, reports = {}, []
    for query in queries:
        start = time.monotonic()
        try:
            data = api_search(query)
            items = data.get('items', [])
            accepted = 0
            for repo in items:
                if repo.get('private') or repo.get('fork') or repo.get('disabled') or repo.get('archived'):
                    continue
                if repo['id'] in current_ids or repo['full_name'].lower() in excluded or not is_ai(repo):
                    continue
                if repo['id'] not in repositories:
                    repositories[repo['id']] = {**repo, '_discoveryQueries': []}
                    accepted += 1
                repositories[repo['id']]['_discoveryQueries'].append(query)
            reports.append({'query': query, 'totalCount': data.get('total_count'),
                            'returned': len(items), 'newEligible': accepted,
                            'incompleteResults': bool(data.get('incomplete_results'))})
            print(f'{query}: {accepted} new; {len(repositories)} eligible unique', flush=True)
        except Exception as error:
            reports.append({'query': query, 'error': str(error)})
            print(f'{query}: failed {error}', flush=True)
        persist(repositories, reports, current_ids)
        # GitHub Search has a separate 30 requests/minute quota.
        time.sleep(max(0, 2.3 - (time.monotonic() - start)))
    persist(repositories, reports, current_ids, finished=True)
    final = json.loads(OUT.read_text())
    print(json.dumps({'selected': len(final['repositories']), 'eligible': len(repositories),
                      'createdIn2026': sum(r['created_at'][:4] == '2026' for r in final['repositories']),
                      'queries': len(reports), 'errors': sum('error' in r for r in reports)}), flush=True)


if __name__ == '__main__':
    main()
