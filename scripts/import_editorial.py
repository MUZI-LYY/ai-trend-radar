"""Validate and merge independently written editorial batches without losing existing work.

Usage: python3 scripts/import_editorial.py work/full-editorial --require-complete --apply
The batch directory contains baseline.json and shard-*/{manifest,result-*}.json.
Without --apply this command only reports coverage and validates the drafts.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from collect import CATEGORIES, ROOT, atomic_json


def read_json(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'{path}: duplicate JSON key {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique_keys)


def validate_profile(name, profile):
    if not isinstance(profile, dict):
        raise ValueError(f'{name}: profile must be an object')
    for field in ('summary', 'overview', 'audience', 'kind', 'usage', 'caveat'):
        value = profile.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{name}: missing {field}')
        if not re.search(r'[\u4e00-\u9fff]', value):
            raise ValueError(f'{name}: {field} needs a Chinese explanation')
    if len(profile['overview']) < 120:
        raise ValueError(f'{name}: overview is too brief ({len(profile["overview"])} characters)')
    minima = {'related': 0, 'tags': 2, 'ways': 1, 'features': 3,
              'useCases': 2, 'gettingStarted': 3, 'requirements': 1, 'sourceUrls': 1}
    for field, minimum in minima.items():
        values = profile.get(field)
        if not isinstance(values, list) or len(values) < minimum:
            raise ValueError(f'{name}: {field} requires at least {minimum} entries')
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError(f'{name}: invalid {field} entry')
        if len(set(values)) != len(values):
            raise ValueError(f'{name}: duplicate {field} entries')
    if profile.get('category') not in CATEGORIES:
        raise ValueError(f'{name}: unknown category')
    if any(category not in CATEGORIES or category == profile['category']
           for category in profile['related']):
        raise ValueError(f'{name}: invalid related category')
    dt.date.fromisoformat(profile['reviewedAt'])
    for url in profile['sourceUrls']:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username:
            raise ValueError(f'{name}: invalid source URL {url}')


def load_batches(batch_root, registry, require_complete=False):
    baseline = read_json(batch_root / 'baseline.json')
    expected = {p['fullName'].lower() for p in baseline['projects'] if not p['editorial']}
    assigned, drafts = set(), {}
    texts = {'overview': {}, 'features': {}}
    for manifest_path in sorted(batch_root.glob('shard-*/manifest.json')):
        manifest = read_json(manifest_path)
        names = {name.lower() for name in manifest['names']}
        if len(names) != manifest['count'] or assigned & names:
            raise ValueError(f'{manifest_path}: duplicate or inconsistent assignment')
        assigned.update(names)
        for result_path in sorted(manifest_path.parent.glob('result-*.json')):
            batch = read_json(result_path)
            if not isinstance(batch, dict):
                raise ValueError(f'{result_path}: expected an object keyed by repository name')
            for name, profile in batch.items():
                if name != name.lower() or name not in names or name in drafts:
                    raise ValueError(f'{result_path}: unexpected or duplicate repository {name}')
                validate_profile(name, profile)
                if name in registry and registry[name] != profile:
                    raise ValueError(f'{name}: refusing to replace an existing different profile')
                for field in texts:
                    value = json.dumps(profile[field], ensure_ascii=False)
                    if value in texts[field]:
                        raise ValueError(f'{name}: identical {field} to {texts[field][value]}')
                    texts[field][value] = name
                drafts[name] = profile
    if assigned != expected:
        raise ValueError('Shard assignments differ from the unedited baseline projects')
    missing = sorted(expected - drafts.keys())
    if require_complete and missing:
        raise ValueError(f'{len(missing)} profiles still missing, including: {", ".join(missing[:8])}')
    return drafts, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch_root', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'data/editorial.json'
    registry = read_json(path)
    drafts, missing = load_batches(args.batch_root, registry, args.require_complete)
    print(f'Validated {len(drafts)} profiles; {len(missing)} missing from this batch assignment.')
    if args.apply:
        atomic_json(path, {**registry, **drafts})
        print(f'Merged into {path}; existing profiles preserved. Run scripts/enrich.py to publish data locally.')


if __name__ == '__main__':
    main()
