#!/usr/bin/env python3
"""Store official daily Star history as a checked, reproducible gzip file."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'public/data/history.json'
PACKED = ROOT / 'public/data/history.json.gz'
MANIFEST = ROOT / 'public/data/history-pack.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pack(source=SOURCE, packed=PACKED, manifest=MANIFEST):
    source, packed, manifest = map(Path, (source, packed, manifest))
    raw = source.read_bytes()
    json.loads(raw)
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    temporary = packed.with_suffix(packed.suffix + '.tmp')
    temporary.write_bytes(compressed)
    temporary.replace(packed)
    info = {'schemaVersion': 1, 'sourceSha256': digest(raw),
            'packedSha256': digest(compressed), 'sourceBytes': len(raw),
            'packedBytes': len(compressed)}
    temporary = manifest.with_suffix(manifest.suffix + '.tmp')
    temporary.write_text(json.dumps(info, separators=(',', ':')) + '\n')
    temporary.replace(manifest)
    return info


def restore(source=PACKED, output=SOURCE, manifest=MANIFEST):
    source, output, manifest = map(Path, (source, output, manifest))
    info = json.loads(manifest.read_text())
    if info.get('schemaVersion') != 1:
        raise ValueError('Unsupported history pack')
    compressed = source.read_bytes()
    if digest(compressed) != info['packedSha256'] or len(compressed) != info['packedBytes']:
        raise ValueError('Packed history checksum mismatch')
    raw = gzip.decompress(compressed)
    if digest(raw) != info['sourceSha256'] or len(raw) != info['sourceBytes']:
        raise ValueError('Restored history checksum mismatch')
    json.loads(raw)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_bytes(raw)
    temporary.replace(output)
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    info = restore(output=args.source or SOURCE) if args.restore else pack(source=args.source or SOURCE)
    print(json.dumps(info))
