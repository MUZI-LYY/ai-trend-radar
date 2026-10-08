"""Read and write dated snapshots in plain JSON or Git-safe gzip form."""
import gzip
import json
from pathlib import Path

MAX_GIT_BLOB_BYTES = 95_000_000


class SnapshotTooLarge(ValueError):
    pass


def snapshot_date(path):
    name = Path(path).name
    if name.endswith('.json.gz'):
        return name[:-8]
    if name.endswith('.json'):
        return name[:-5]
    raise ValueError('Unsupported snapshot: ' + name)


def snapshot_paths(directory):
    directory = Path(directory)
    return sorted((*directory.glob('*.json'), *directory.glob('*.json.gz')))


def find_snapshot(directory, date):
    directory = Path(directory)
    for suffix in ('.json.gz', '.json'):
        path = directory / (date + suffix)
        if path.exists():
            return path
    raise FileNotFoundError(date)


def read_snapshot(path):
    path = Path(path)
    if path.name.endswith('.json.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as source:
            return json.load(source)
    return json.loads(path.read_text())


def write_snapshot(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    if path.name.endswith('.json.gz'):
        encoded = gzip.compress(encoded, compresslevel=4, mtime=0)
    if len(encoded) > MAX_GIT_BLOB_BYTES:
        raise SnapshotTooLarge(f'{path.name} is {len(encoded)} bytes')
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(encoded)
    temp.replace(path)
