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
    def test_enrichment_removes_recreated_name_without_changing_archives(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/'public/data/latest.json').read_text())
        current=copy.deepcopy(data['projects'][0])
        old=copy.deepcopy(current)
        old['id']=current['id']+10_000_000_000
        old['createdAt']='2000-01-01T00:00:00Z'
        old['fetchedAt']='2026-09-27T00:00:00Z'
        old['fullName']=old['fullName'].upper()
        current['history'].insert(0,{'date':'2000-01-02','stars':3})
        current['firstSeen']='2000-01-03'
        current['netSincePrevious']=-3
        current['netBaselineAt']='2000-01-04T00:00:00Z'
        current['readmeFetchedAt']='2000-01-04T00:00:00Z'
        data['projects']=[old,current]
        with tempfile.TemporaryDirectory() as directory:
            temporary=Path(directory)
            (temporary/'data').mkdir();(temporary/'public/data/snapshots').mkdir(parents=True)
            (temporary/'public/data/latest.json').write_text(json.dumps(data))
            (temporary/'data/editorial.json').write_text((root/'data/editorial.json').read_text())
            (temporary/'data/excluded.json').write_text('[]')
            (temporary/'data/discovery.json').write_text(json.dumps({'candidates':{}}))
            with patch.object(enrich,'ROOT',temporary),contextlib.redirect_stdout(io.StringIO()):
                enrich.main()
            published=json.loads((temporary/'public/data/latest.json').read_text())['projects']
            history=json.loads((temporary/'public/data/history.json').read_text())['projects']
            archives=list((temporary/'public/data/snapshots').glob('*.json'))
        self.assertEqual(len(published),1)
        self.assertEqual(published[0]['id'],current['id'])
        self.assertTrue(all(day['date']>=current['createdAt'][:10] for day in published[0]['history']))
        self.assertIsNone(published[0]['netSincePrevious'])
        self.assertIsNone(published[0]['readmeFetchedAt'])
        self.assertEqual([row['id'] for row in history],[current['id']])
        self.assertEqual(archives,[])

    def test_generated_profile_survives_enrichment_without_human_review_flag(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/'public/data/latest.json').read_text())
        data['projects']=copy.deepcopy(data['projects'][:1])
        project=data['projects'][0]
        profile={'profileStatus':'generated','category':project['category'],
                 'summary':'基于项目资料整理的中文摘要',
                 'overview':'基于项目资料整理的具体中文用途。',
                 'features':['文档中列出的功能'],'reviewedAt':'2026-09-26'}
        with tempfile.TemporaryDirectory() as directory:
            temporary=Path(directory)
            (temporary/'data').mkdir();(temporary/'public/data/snapshots').mkdir(parents=True)
            (temporary/'public/data/latest.json').write_text(json.dumps(data))
            (temporary/'data/editorial.json').write_text(json.dumps({project['fullName'].lower():profile}))
            (temporary/'data/excluded.json').write_text('[]')
            (temporary/'data/discovery.json').write_text(json.dumps({'candidates':{}}))
            with patch.object(enrich,'ROOT',temporary),contextlib.redirect_stdout(io.StringIO()):
                enrich.main()
            enriched=json.loads((temporary/'public/data/latest.json').read_text())['projects'][0]
        self.assertEqual(enriched['summary'],profile['summary'])
        self.assertEqual(enriched['features'],profile['features'])
        self.assertEqual(enriched['profileStatus'],'generated')
        self.assertFalse(enriched['editorial'])
        self.assertIsNone(enriched['reviewedAt'])

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
