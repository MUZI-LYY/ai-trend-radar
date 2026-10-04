import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from local_backfill import connect, save_review, select_pending
from export_backfill import export, verify, restore


class LocalBackfillTests(unittest.TestCase):
    def test_completed_rows_are_checkpointed_and_not_selected_again(self):
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / 'backfill.sqlite3')
            state = {'candidates': {
                str(i): {'id': i, 'fullName': f'owner/ai-{i}', 'status': 'pending',
                         'sources': ['topic:llm'], 'stars': i,
                         'createdAt': '2026-01-01T00:00:00Z'}
                for i in range(1, 4)}}
            first = select_pending(state, [], [], db, 3, '2026-10-04')
            self.assertEqual(len(first), 3)
            save_review(db, first[0], 'admitted', {'id': first[0]['id'], 'history': []}, today='2026-10-04')
            save_review(db, first[1], 'retry', today='2026-10-04')
            db.close()
            db = connect(Path(directory) / 'backfill.sqlite3')
            self.assertEqual([row['id'] for row in select_pending(state, [], [], db, 3, '2026-10-04')],
                             [first[2]['id']])
            self.assertEqual(len(select_pending(state, [], [], db, 3, '2026-10-05')), 2)
            payload = db.execute('SELECT project FROM reviews WHERE id=?', (first[0]['id'],)).fetchone()[0]
            self.assertEqual(json.loads(zlib.decompress(payload))['id'], first[0]['id'])
            db.close()

    def test_exported_shards_preserve_review_result_and_detect_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'backfill.sqlite3'
            output = Path(directory) / 'shards'
            db = connect(database)
            candidate = {'id': 65, 'fullName': 'owner/real'}
            save_review(db, candidate, 'admitted', {'id': 65, 'stars': 42, 'historyStatus': 'ok'},
                        today='2026-10-04')
            db.close()
            manifest = export(database, output)
            self.assertEqual(manifest['reviews'], 1)
            self.assertEqual(verify(output)['statuses'], {'admitted': 1})
            restored = Path(directory) / 'restored.sqlite3'
            restore(output, restored)
            reopened = connect(restored)
            self.assertEqual(reopened.execute('SELECT status FROM reviews').fetchone()[0], 'admitted')
            reopened.close()
            shard = output / '01.jsonl.gz'
            shard.write_bytes(shard.read_bytes() + b'broken')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                verify(output)


if __name__ == '__main__':
    unittest.main()
