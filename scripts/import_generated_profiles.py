"""Validate source-grounded Chinese profiles before merging them into the registry.

Default is a read-only check. Example:
  python3 scripts/import_generated_profiles.py work/editorial-2026-09-26
  python3 scripts/import_generated_profiles.py work/editorial-2026-09-26 --apply

The batch schema has no repository ID, so identity is checked through the
fullName -> ID mapping in manifest.json and the current latest.json. A changed
or missing mapping is rejected instead of silently assigning a profile.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from collect import CATEGORIES, ROOT
from taxonomy import KINDS, normalize_ways

PROFILE_FIELDS = frozenset({
    'fullName', 'relevance', 'relevanceReason', 'category', 'related', 'kind',
    'tags', 'ways', 'summary', 'overview', 'audience', 'features', 'useCases',
    'gettingStarted', 'requirements', 'usage', 'caveat', 'evidence',
})
TEXT_FIELDS = ('summary', 'overview', 'audience', 'usage', 'caveat')
LIST_FIELDS = ('related', 'tags', 'ways', 'features', 'useCases',
               'gettingStarted', 'requirements', 'evidence')
EXPLANATION_LISTS = ('features', 'useCases', 'gettingStarted', 'requirements')
RELEVANCE = frozenset(('ai', 'not-ai', 'uncertain'))
PLACEHOLDER = re.compile(r'待中文核对|尚未完成逐项中文解读|该项目暂归入|\bTODO\b|\bTBD\b|Lorem ipsum', re.I)
CHINESE = re.compile(r'[\u4e00-\u9fff]')
REPOSITORY = re.compile(r'^[^/\s]+/[^/\s]+$')


def read_json(path: Path) -> Any:
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f'{path}: duplicate JSON key {key}')
            value[key] = item
        return value
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     prefix=f'.{path.name}.', delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    os.replace(temporary, path)


def _text(value: Any, field: str, name: str, *, required: bool = False,
          chinese: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError(f'{name}: invalid {field}')
    if required and not value:
        raise ValueError(f'{name}: missing {field}')
    if value and chinese and not CHINESE.search(value):
        raise ValueError(f'{name}: {field} needs a Chinese explanation')
    if field != 'evidence' and PLACEHOLDER.search(value):
        raise ValueError(f'{name}: placeholder in {field}')
    return value


def _strings(value: Any, field: str, name: str, *, chinese: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f'{name}: {field} must be an array')
    for entry in value:
        _text(entry, field, name, required=True, chinese=chinese)
    if len(set(value)) != len(value):
        raise ValueError(f'{name}: duplicate {field}')
    return value


def _normalize_source(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip().casefold()


def validate_profile(profile: Any, project: dict[str, Any]) -> None:
    name = project['fullName']
    if not isinstance(profile, dict) or set(profile) != PROFILE_FIELDS:
        missing = PROFILE_FIELDS - set(profile) if isinstance(profile, dict) else PROFILE_FIELDS
        extra = set(profile) - PROFILE_FIELDS if isinstance(profile, dict) else set()
        raise ValueError(f'{name}: wrong fields; missing={sorted(missing)}, extra={sorted(extra)}')
    if profile['fullName'] != name or not REPOSITORY.fullmatch(profile['fullName']):
        raise ValueError(f'{name}: fullName does not match latest.json')
    relevance = profile['relevance']
    if not isinstance(relevance, str) or relevance not in RELEVANCE:
        raise ValueError(f'{name}: invalid relevance {relevance!r}')
    _text(profile['relevanceReason'], 'relevanceReason', name, required=True, chinese=True)
    for field in TEXT_FIELDS:
        _text(profile[field], field, name, required=relevance == 'ai' and field in ('summary', 'overview'), chinese=True)
    for field in LIST_FIELDS:
        _strings(profile[field], field, name, chinese=field in EXPLANATION_LISTS)
    if not isinstance(profile['category'], str) or profile['category'] not in CATEGORIES:
        raise ValueError(f'{name}: invalid category')
    if any(item not in CATEGORIES or item == profile['category'] for item in profile['related']):
        raise ValueError(f'{name}: invalid related category')
    if not isinstance(profile['kind'], str) or profile['kind'] not in KINDS:
        raise ValueError(f'{name}: invalid kind')
    if normalize_ways(profile['ways']) != profile['ways']:
        raise ValueError(f'{name}: ways must use canonical names')
    if relevance == 'ai':
        if len(profile['overview']) < 160 or len(CHINESE.findall(profile['overview'])) < 100:
            raise ValueError(f'{name}: overview needs substantial Chinese detail')
        if not profile['tags']:
            raise ValueError(f'{name}: at least one tag is required')
    elif any(profile[field] for field in TEXT_FIELDS + ('tags', 'ways') + EXPLANATION_LISTS):
        raise ValueError(f'{name}: {relevance} candidates cannot be imported as project explanations')
    if not 1 <= len(profile['evidence']) <= 8:
        raise ValueError(f'{name}: expected 1–8 source excerpts')
    source = _normalize_source('\n'.join([
        project.get('description') or '', project.get('readme') or '',
        *(item.get('text') or '' for item in project.get('sourceExcerpts') or []),
    ]))
    for evidence in profile['evidence']:
        if len(evidence) < 18 or len(evidence) > 500 or _normalize_source(evidence) not in source:
            raise ValueError(f'{name}: evidence is not a short quotation from README/description: {evidence[:80]!r}')


def _check_repeated(profiles: list[dict[str, Any]]) -> None:
    summaries: dict[str, str] = {}
    overviews: dict[str, str] = {}
    chunks: dict[str, set[str]] = {}
    for profile in profiles:
        if profile['relevance'] != 'ai':
            continue
        name = profile['fullName']
        summary = re.sub(r'\s+', '', profile['summary'])
        if summary in summaries:
            raise ValueError(f'{name}: summary duplicates {summaries[summary]}')
        summaries[summary] = name
        overview = re.sub(r'\s+', '', profile['overview'])
        # Very similar paragraphs share many 20-character spans. Index spans
        # before the slower similarity check so thousands of profiles remain cheap.
        spans = {overview[i:i + 20] for i in range(0, max(1, len(overview) - 19), 10)}
        possible: set[str] = set()
        for span in spans:
            possible.update(chunks.get(span, ()))
        for other_name in possible:
            other_text = overviews[other_name]
            if len(overview) > 100 and abs(len(overview) - len(other_text)) < max(len(overview), len(other_text)) * .1:
                if difflib.SequenceMatcher(None, overview, other_text).ratio() > .90:
                    raise ValueError(f'{name}: overview is a near-duplicate of {other_name}')
        overviews[name] = overview
        for span in spans:
            chunks.setdefault(span, set()).add(name)


def load_and_validate(batch_dir: Path, latest: dict[str, Any],
                      registry: dict[str, Any], *, require_complete: bool = False
                      ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    manifest = read_json(batch_dir / 'manifest.json')
    if not isinstance(manifest, list):
        raise ValueError('manifest.json must be an array')
    projects: dict[str, list[dict[str, Any]]] = {}
    for project in latest['projects']:
        projects.setdefault(project['fullName'].lower(), []).append(project)
    assignments: dict[str, list[dict[str, Any]]] = {}
    for item in manifest:
        if not isinstance(item, dict) or not isinstance(item.get('fullName'), str):
            raise ValueError('invalid manifest entry')
        key = item['fullName'].lower()
        if not REPOSITORY.fullmatch(item['fullName']) or not isinstance(item.get('id'), int):
            raise ValueError(f"invalid manifest identity: {item['fullName']}")
        assignments.setdefault(key, []).append(item)
    accepted: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    all_profiles: list[dict[str, Any]] = []
    paths = sorted(batch_dir.glob('result-batch-*.json'))
    if not paths:
        raise ValueError(f'{batch_dir}: no result-batch-*.json files')
    seen: set[str] = set()
    for path in paths:
        result = read_json(path)
        if not isinstance(result, dict) or set(result) != {'profiles'} or not isinstance(result['profiles'], list):
            raise ValueError(f'{path}: expected a profiles array')
        for profile in result['profiles']:
            if not isinstance(profile, dict) or not isinstance(profile.get('fullName'), str):
                raise ValueError(f'{path}: invalid profile identity')
            key = profile['fullName'].lower()
            if key in seen or key not in assignments:
                raise ValueError(f'{path}: duplicate or unassigned project {profile["fullName"]}')
            seen.add(key)
            matched = assignments[key]
            current = projects.get(key, [])
            if len(matched) != 1 or len(current) != 1:
                raise ValueError(f"ambiguous repository identity: {profile['fullName']}")
            item, project = matched[0], current[0]
            if project['fullName'] != item['fullName'] or project['id'] != item['id']:
                raise ValueError(f"manifest name/ID mismatch: {item['fullName']}")
            if project.get('editorial') or key in registry:
                raise ValueError(f"refusing to overwrite existing editorial profile: {item['fullName']}")
            if item.get('readmeSha') != project.get('readmeSha'):
                raise ValueError(f"manifest README changed: {item['fullName']}")
            validate_profile(profile, project)
            all_profiles.append(profile)
            if profile['relevance'] == 'ai':
                accepted[key] = {field: profile[field] for field in (
                    'category', 'related', 'kind', 'tags', 'ways', 'summary', 'overview',
                    'audience', 'features', 'useCases', 'gettingStarted',
                    'requirements', 'usage', 'caveat')}
                accepted[key]['profileStatus'] = 'generated'
                accepted[key]['sourceUrls'] = [project.get('readmeUrl') or project['url']]
                accepted[key]['sourceReadmeSha'] = project.get('readmeSha')
                accepted[key]['sourceEvidence'] = profile['evidence']
                accepted[key]['generationModel'] = 'gpt-6-astra'
                accepted[key]['generatedAt'] = dt.date.today().isoformat()
            else:
                candidates.append({'fullName': project['fullName'], 'id': project['id'],
                                   'relevance': profile['relevance'],
                                   'reason': profile['relevanceReason'],
                                   'evidence': profile['evidence']})
    _check_repeated(all_profiles)
    missing = sorted(assignments.keys() - seen)
    if require_complete and missing:
        raise ValueError(f'{len(missing)} profiles missing, including {", ".join(missing[:8])}')
    return accepted, candidates, missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch_dir', type=Path)
    parser.add_argument('--latest', type=Path, default=ROOT / 'public/data/latest.json')
    parser.add_argument('--registry', type=Path, default=ROOT / 'data/editorial.json')
    parser.add_argument('--candidates-out', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    latest = read_json(args.latest)
    registry = read_json(args.registry)
    accepted, candidates, missing = load_and_validate(
        args.batch_dir, latest, registry, require_complete=args.require_complete)
    print(f'Validated {len(accepted)} AI profiles, {len(candidates)} relevance candidates; '
          f'{len(missing)} manifest projects remain.')
    if args.apply:
        write_json(args.registry, {**registry, **accepted})
        out = args.candidates_out or args.batch_dir / 'relevance-candidates.json'
        write_json(out, candidates)
        print(f'Merged {len(accepted)} profiles into {args.registry}; candidates saved to {out}.')
    else:
        for candidate in candidates:
            print(f"CANDIDATE {candidate['relevance']} {candidate['fullName']}: {candidate['reason']}")


if __name__ == '__main__':
    main()
