#!/usr/bin/env python3
"""Build the isolated broad GitHub dataset from its own collection ledger."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path

from backfill_history import merge_projects, save_history
from build_fast_data import build as build_fast_data
from build_tenure_index import cumulative_chart
from collect import atomic_json, is_current
from pack_history import pack as pack_history
from ranking import chart_entries, period_starts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/github-repositories.json'
PROFILES = ROOT / 'data/github-profiles.json'
OUTPUT = ROOT / 'public/data/github'
SCOPE = 'GitHub 搜索和 Trending 发现并独立收录的公开仓库；不是 GitHub 全站所有仓库的穷尽榜单。'
CATEGORIES = [
    ('development', '开发工具', '编辑器、CLI、SDK 与开发辅助工具'),
    ('web', 'Web 与应用', '网站、客户端、服务端和应用框架'),
    ('data', '数据与 AI', '数据库、数据处理、机器学习和 AI'),
    ('infrastructure', '基础设施', '云原生、系统、运维与安全'),
    ('learning', '学习资源', '教程、文档、项目合集与示例'),
    ('other', '其他项目', '暂未明确归入以上方向的仓库'),
]


def category(project):
    text = ' '.join([project['fullName'], project.get('description', ''), *project.get('topics', [])]).lower()
    terms = {
        'learning': ('awesome-', 'tutorial', 'course', 'book', 'interview', 'learning', 'roadmap', 'exercises'),
        'data': ('database', 'analytics', 'machine-learning', 'artificial-intelligence', 'llm', 'data-science', 'deep-learning'),
        'infrastructure': ('kubernetes', 'docker', 'cloud-native', 'devops', 'operating-system', 'security', 'linux', 'terraform'),
        'development': ('developer-tools', 'compiler', 'editor', 'command-line', 'cli', 'sdk', 'programming-language', 'code-generation'),
        'web': ('web', 'frontend', 'react', 'vue', 'javascript', 'backend', 'mobile', 'android', 'ios', 'framework'),
    }
    for group, words in terms.items():
        if any(word in text for word in words):
            return group
    return 'other'


def localized_profile(project, group, profiles):
    """Keep original GitHub text in description; publish Chinese explanation separately."""
    profile = profiles.get(project['fullName']) or {}
    summary = profile.get('summary') if profile.get('sourceDescription') == project.get('description', '') else None
    if summary:
        return {
            **project, 'summary': summary, 'overview': summary,
            'profileStatus': 'generated',
            'classificationBasis': '中文简介根据 GitHub 仓库原始简介整理，尚待人工复核；方向分类依据仓库简介和 Topics。',
        }
    if any('\u3400' <= char <= '\u9fff' for char in project.get('description', '')):
        summary = project['description']
    else:
        label = next(label for key, label, _ in CATEGORIES if key == group)
        summary = f'这是本站收录的{label}方向仓库，具体用途尚待中文整理；请查看下方 GitHub 原始简介。'
    return {
        **project, 'summary': summary, 'overview': summary,
        'classificationBasis': '方向分类依据仓库简介和 Topics；具体用途尚待中文整理。',
    }


def build(archive=False, source=SOURCE, output=OUTPUT):
    if not source.exists():
        raise FileNotFoundError('GitHub 总榜尚无独立采集数据：' + str(source))
    ledger = json.loads(source.read_text())
    profiles = json.loads(PROFILES.read_text()) if PROFILES.exists() else {}
    if not ledger.get('projects'):
        raise ValueError('GitHub 总榜无已收录项目')
    now = dt.datetime.now(dt.timezone.utc)
    end = (now.date() - dt.timedelta(days=1)).isoformat()
    capture = now.astimezone(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
    projects = []
    for raw in ledger['projects']:
        if raw.get('metadataThrough') == end:
            project = {**raw, 'stale': False}
        else:
            project = {**raw, 'stale': True, 'metrics': {key: None for key in period_starts(end)},
                       'warnings': sorted(set(raw.get('warnings', []) + ['等待本期数据更新']))}
        project['category'] = category(project)
        projects.append(localized_profile(project, project['category'], profiles))
    projects.sort(key=lambda p: (-p['stars'], p['fullName'].lower()))
    current = sum(is_current(p, end) for p in projects)
    warnings = [] if current == len(projects) else [f'{len(projects)-current} 个仓库等待完整本期 Star 历史，暂不参与增长榜。']
    payload = {
        'schemaVersion': 2, 'date': capture, 'capturedAt': ledger.get('updatedAt', now.isoformat()),
        'completedAt': ledger.get('updatedAt', now.isoformat()),
        'periodEnd': end, 'periodStarts': period_starts(end),
        'source': 'GitHub REST API / Search API / Trending 候选发现',
        'metric': 'GitHub 官方 Star 历史日统计',
        'timezoneNote': '日期按 GitHub Star 历史 week 时间戳的 UTC 日期展开；来源统计日边界不保证与北京时间午夜一致。',
        'scope': SCOPE, 'categories': [{'id': key, 'label': label, 'description': description}
                                     for key, label, description in CATEGORIES],
        'status': 'complete' if current == len(projects) else 'partial',
        'warnings': warnings, 'failedRepositories': [], 'projects': projects,
        'coverage': {'discoveredRepositories': len(projects) + len(ledger.get('pending', [])),
                     'trackedRepositories': len(projects), 'updatedRepositories': current,
                     'pendingCandidates': len(ledger.get('pending', [])),
                     'pendingUpdates': len(projects)-current, 'sourceDate': end, 'totalLimit': None},
    }
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / 'latest.json', payload)
    snapshot_dir = output / 'snapshots'
    snapshot_dir.mkdir(exist_ok=True)
    daily_ready = sum(not p['stale'] and p['metrics']['daily'] is not None for p in projects)
    if archive and daily_ready >= math.ceil(len(projects) * 0.8) and end == (dt.date.fromisoformat(capture) - dt.timedelta(days=1)).isoformat():
        snapshot = snapshot_dir / (capture + '.json')
        if not snapshot.exists():
            atomic_json(snapshot, payload)
    snapshots = sorted(snapshot_dir.glob('*.json'), reverse=True)
    atomic_json(output / 'index.json', {'snapshots': [
        {'date': path.stem, 'file': 'snapshots/' + path.name} for path in snapshots]})
    entries = chart_entries(json.loads(path.read_text()) for path in snapshots)
    atomic_json(output / 'board-history.json', {'chartSize': 30, 'entries': entries})
    history_path = output / 'history.json'
    old = json.loads(history_path.read_text()) if history_path.exists() else {}
    history = merge_projects(old, projects, old.get('start', '2025-01-01'), end)
    history['scope'] = SCOPE
    save_history(history, output)
    pack_history(output / 'history.json', output / 'history.json.gz', output / 'history-pack.json')
    history_index = json.loads((output / 'history-index.json').read_text())
    chart = cumulative_chart(payload, history, history_index, {'entries': entries})
    atomic_json(output / 'cumulative-chart.json', chart)
    # The cumulative GitHub board must keep current repository metadata even
    # when most repositories still lack daily Star history.
    build_fast_data(output, hold_daily_until_covered=False)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    result = build(args.archive)
    print(f'Built independent GitHub dataset: {len(result["projects"])} repositories, {result["periodEnd"]}')
