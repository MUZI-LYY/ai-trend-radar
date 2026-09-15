import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import enrich
from backfill_history import save_history

class EnrichmentScopeTests(unittest.TestCase):
    def test_exclusion_updates_coverage_and_history_without_rewriting_retained_days(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/'public/data/latest.json').read_text())
        data['projects']=copy.deepcopy(data['projects'][:2])
        retained,removed=data['projects']
        original=json.loads((root/'public/data/history.json').read_text())
        ids={p['id'] for p in data['projects']}
        original['projects']=[p for p in original['projects'] if p['id'] in ids]
        original_days=next(p['days'] for p in original['projects'] if p['id']==retained['id'])
        with tempfile.TemporaryDirectory() as directory:
            temporary=Path(directory)
            (temporary/'data').mkdir();(temporary/'public/data/snapshots').mkdir(parents=True)
            def write(path,value):
                (temporary/path).write_text(json.dumps(value))
            write('public/data/latest.json',data)
            write('data/editorial.json',json.loads((root/'data/editorial.json').read_text()))
            write('data/excluded.json',[removed['fullName'].lower()])
            write('data/discovery.json',{'candidates':{}})
            save_history(original,temporary/'public/data')
            with patch.object(enrich,'ROOT',temporary),contextlib.redirect_stdout(io.StringIO()):
                enrich.main()
            latest=json.loads((temporary/'public/data/latest.json').read_text())
            history=json.loads((temporary/'public/data/history.json').read_text())
            self.assertEqual([p['id'] for p in latest['projects']],[retained['id']])
            self.assertEqual(latest['coverage']['trackedRepositories'],1)
            self.assertEqual(latest['projects'][0]['metrics'],retained['metrics'])
            self.assertEqual(latest['completedAt'],data['completedAt'])
            self.assertEqual([p['id'] for p in history['projects']],[retained['id']])
            self.assertEqual(history['projects'][0]['days'],original_days)
