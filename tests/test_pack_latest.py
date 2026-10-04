import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pack_latest import pack, restore


class LatestShardTests(unittest.TestCase):
    def test_exact_roundtrip_and_corrupt_shard_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, recovered, shards = root / 'latest.json', root / 'restored.json', root / 'shards'
            payload = {'date': '2026-10-04', 'projects': [
                {'id': 65, 'fullName': 'owner/one', 'history': [{'date': '2026-10-03', 'stars': 2}]},
                {'id': 1, 'fullName': 'owner/two', 'readme': '真实项目'}],
                'coverage': {'pendingCandidates': 10}}
            source.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n')
            manifest = pack(source, shards)
            first_bytes = [(shards / item['file']).read_bytes() for item in manifest['files']]
            self.assertEqual(manifest, pack(source, shards))
            self.assertEqual(first_bytes,
                             [(shards / item['file']).read_bytes() for item in manifest['files']])
            self.assertEqual(manifest['projectCount'], 2)
            restore(shards, recovered)
            self.assertEqual(recovered.read_bytes(), source.read_bytes())
            path = shards / '01.jsonl.gz'
            path.write_bytes(path.read_bytes() + b'broken')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                restore(shards, recovered)


if __name__ == '__main__':
    unittest.main()
