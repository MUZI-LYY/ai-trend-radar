import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect import select_candidates, retain_previous, collection_coverage, is_current

END='2026-09-13'


def project(number, current=False, **values):
    return {'id':number,'fullName':f'org/p{number}',
            'fetchedAt':'2026-09-01T00:00:00Z','stars':10,
            'statsThrough':END if current else '2026-08-31',
            'historyStatus':'ok','metrics':dict(daily=1,weekly=7,monthly=13,yearly=100),**values}


class CollectionBatchTests(unittest.TestCase):
    def test_second_batch_skips_current_and_reaches_rest_of_existing_collection(self):
        previous={p['fullName'].lower():p for p in [project(i) for i in range(1000)]}
        candidates={key:p['fullName'] for key,p in previous.items()}
        first=select_candidates(previous,candidates,600,40,END)
        self.assertEqual(len(first),600)
        for name in first:previous[name]['statsThrough']=END
        second=select_candidates(previous,candidates,600,40,END)
        self.assertEqual(len(second),400)
        self.assertFalse(set(first)&set(second))

    def test_new_candidates_get_slots_even_with_large_overdue_collection(self):
        previous={f'org/p{i}':project(i) for i in range(2000)}
        candidates={f'new/p{i}':f'new/p{i}' for i in range(50)}
        selected=select_candidates(previous,candidates,600,40,END)
        self.assertEqual(len(selected),600)
        self.assertEqual(sum(n.startswith('new/') for n in selected),40)

    def test_failed_repository_rotates_behind_unattempted_ones(self):
        failed=project(1,lastAttemptAt='2026-09-14T12:00:00Z')
        waiting=project(2)
        previous={p['fullName']:p for p in (failed,waiting)}
        self.assertEqual(select_candidates(previous,{},1,0,END),['org/p2'])

    def test_same_source_day_completed_records_keep_their_verified_metrics(self):
        old=project(1,current=True)
        actual=retain_previous([],{'org/p1':old},END)
        self.assertEqual(actual,[old])
        self.assertTrue(is_current(actual[0],END))

    def test_unattempted_old_day_is_kept_but_cannot_rank_as_current(self):
        old=project(1)
        actual=retain_previous([],{'org/p1':old},END)[0]
        self.assertTrue(actual['stale'])
        self.assertTrue(all(v is None for v in actual['metrics'].values()))
        self.assertNotIn('lastAttemptAt',actual)
        self.assertEqual(actual['statsThrough'],'2026-08-31')

    def test_failed_attempt_updates_rotation_timestamp(self):
        actual=retain_previous([],{'org/p1':project(1)},END,{'org/p1'},'2026-09-14T12:00:00Z')[0]
        self.assertEqual(actual['lastAttemptAt'],'2026-09-14T12:00:00Z')

    def test_coverage_distinguishes_discovery_collection_and_valid_current_metrics(self):
        candidates={'1':{'id':1,'fullName':'org/p1'},'2':{'id':3,'fullName':'org/p3','status':'retry'},
                    '3':{'id':4,'fullName':'org/p4','status':'rejected'}}
        report=collection_coverage([project(1,True),project(2)],{'candidates':candidates},[],END)
        self.assertEqual(report['discoveredRepositories'],4)
        self.assertEqual(report['trackedRepositories'],2)
        self.assertEqual(report['updatedRepositories'],1)
        self.assertEqual(report['pendingCandidates'],1)
        self.assertEqual(report['pendingUpdates'],1)
        self.assertIsNone(report['totalLimit'])

    def test_incomplete_year_must_remain_due_and_force_refresh_is_explicit(self):
        complete=project(1,True)
        missing=project(2,True,metrics=dict(daily=1,weekly=7,monthly=13,yearly=None))
        previous={p['fullName']:p for p in (complete,missing)}
        self.assertEqual(select_candidates(previous,{},600,0,END),['org/p2'])
        self.assertEqual(len(select_candidates(previous,{},600,0,END,force=True)),2)


if __name__=='__main__':unittest.main()
