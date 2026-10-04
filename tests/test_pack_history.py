import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pack_history import pack, restore


class PackedHistoryTests(unittest.TestCase):
    def test_round_trip_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'history.json'
            packed = root / 'history.json.gz'
            manifest = root / 'history-pack.json'
            payload = {'projects': [{'id': 1, 'days': [{'date': '2026-10-03', 'stars': 2}]}]}
            source.write_text(json.dumps(payload) + '\n')
            first = pack(source, packed, manifest)
            self.assertEqual(pack(source, packed, manifest), first)
            source.unlink()
            restore(packed, source, manifest)
            self.assertEqual(json.loads(source.read_text()), payload)
            packed.write_bytes(packed.read_bytes() + b'bad')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                restore(packed, source, manifest)


if __name__ == '__main__':
    unittest.main()
