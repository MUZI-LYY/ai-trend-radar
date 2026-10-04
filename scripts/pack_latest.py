#!/usr/bin/env python3
"""Losslessly store the canonical latest dataset in small compressed shards."""
import argparse
from contextlib import ExitStack
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / 'public/data/latest.json'
SHARDS_DIR = ROOT / 'data/latest-shards'
SHARDS = 64


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    temporary.replace(path)


def pack(source=LATEST, output=SHARDS_DIR):
    source, output = Path(source), Path(output)
    dataset = json.loads(source.read_text())
    if not isinstance(dataset.get('projects'), list):
        raise ValueError('Latest dataset has no project list')
    output.mkdir(parents=True, exist_ok=True)
    metadata = {key: value for key, value in dataset.items() if key != 'projects'}
    write_json(output / 'metadata.json', metadata)
    counts = [0] * SHARDS
    with ExitStack() as stack:
        handles = []
        for index in range(SHARDS):
            raw = stack.enter_context((output / f'{index:02x}.jsonl.gz.tmp').open('wb'))
            compressed = stack.enter_context(gzip.GzipFile(
                filename='', mode='wb', fileobj=raw, compresslevel=6, mtime=0))
            handles.append(stack.enter_context(io.TextIOWrapper(compressed, encoding='utf-8')))
        seen = set()
        for order, project in enumerate(dataset['projects']):
            identity = project['id']
            if identity in seen:
                raise ValueError('Duplicate project ID: ' + str(identity))
            seen.add(identity)
            index = identity % SHARDS
            handles[index].write(json.dumps({'order': order, 'project': project},
                                            ensure_ascii=False, separators=(',', ':')) + '\n')
            counts[index] += 1
    files = []
    for index, count in enumerate(counts):
        temporary = output / f'{index:02x}.jsonl.gz.tmp'
        destination = output / f'{index:02x}.jsonl.gz'
        temporary.replace(destination)
        files.append({'file': destination.name, 'count': count, 'sha256': sha256(destination)})
    manifest = {'schemaVersion': 1, 'shardCount': SHARDS, 'fieldOrder': list(dataset),
                'projectCount': len(dataset['projects']), 'sourceSha256': sha256(source),
                'metadataSha256': sha256(output / 'metadata.json'), 'files': files}
    write_json(output / 'manifest.json', manifest)
    return manifest


def restore(source=SHARDS_DIR, output=LATEST):
    source, output = Path(source), Path(output)
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest.get('schemaVersion') != 1 or manifest.get('shardCount') != SHARDS \
            or len(manifest.get('files', [])) != SHARDS:
        raise ValueError('Unsupported latest shard manifest')
    if sha256(source / 'metadata.json') != manifest['metadataSha256']:
        raise ValueError('Latest metadata checksum mismatch')
    metadata = json.loads((source / 'metadata.json').read_text())
    ordered = {}
    ids = set()
    for index, item in enumerate(manifest['files']):
        if item['file'] != f'{index:02x}.jsonl.gz':
            raise ValueError('Latest shard order mismatch')
        path = source / item['file']
        if sha256(path) != item['sha256']:
            raise ValueError('Latest shard checksum mismatch: ' + item['file'])
        count = 0
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                order, project = row['order'], row['project']
                if project['id'] % SHARDS != index or order in ordered or project['id'] in ids:
                    raise ValueError('Invalid latest shard entry: ' + item['file'])
                ordered[order] = project
                ids.add(project['id'])
                count += 1
        if count != item['count']:
            raise ValueError('Latest shard count mismatch: ' + item['file'])
    if len(ordered) != manifest['projectCount'] or set(ordered) != set(range(len(ordered))):
        raise ValueError('Latest project order incomplete')
    projects = [ordered[index] for index in range(len(ordered))]
    if set(manifest['fieldOrder']) != set(metadata) | {'projects'}:
        raise ValueError('Latest metadata fields differ from manifest')
    restored = {key: projects if key == 'projects' else metadata[key]
                for key in manifest['fieldOrder']}
    write_json(output, restored)
    if sha256(output) != manifest['sourceSha256']:
        raise ValueError('Reconstructed latest dataset differs from source')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=LATEST)
    parser.add_argument('--output', type=Path, default=SHARDS_DIR)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    result = restore(args.output, args.source) if args.restore else pack(args.source, args.output)
    print(json.dumps({'projects': result['projectCount'], 'shards': result['shardCount'],
                      'sourceSha256': result['sourceSha256']}))
