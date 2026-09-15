"""Apply edited repository profiles and new schema fields to latest; archives stay immutable."""
import json
from collect import ROOT, atomic_json, classify, period_total, collection_coverage
from ranking import period_starts, chart_entries

def main():
 path=ROOT/'public/data/latest.json';d=json.loads(path.read_text())
 editorial=json.loads((ROOT/'data/editorial.json').read_text());excluded=json.loads((ROOT/'data/excluded.json').read_text())
 before_ids={p['id'] for p in d['projects']}
 d['projects']=[p for p in d['projects'] if p['fullName'].lower() not in excluded]
 d['schemaVersion']=2;d['periodStarts']=period_starts(d['periodEnd'])
 for p in d['projects']:
  repo={'full_name':p['fullName'],'name':p['name'],'description':p['description'],'topics':p['topics'],'language':p['language'],'homepage':p['homepage']}
  original={k:p[k] for k in ('readme','readmeUrl')}
  if p['fullName'].lower() not in editorial and p.get('profileSource'):
   from source_profile import build_source_profile
   original.update({k:p[k] for k in build_source_profile(p,p['readme']) if k in p})
  p.update(classify(repo,p['readme'],editorial));p.update(original)
  daily={x['date']:x['stars'] for x in p['history']}
  p['metrics']['weekly']=None if p.get('stale') or p['historyStatus']!='ok' else period_total(daily,d['periodStarts']['weekly'],d['periodEnd'],p['createdAt'])
 if 'coverage' in d:
  discovery=json.loads((ROOT/'data/discovery.json').read_text())
  d['coverage']=collection_coverage(d['projects'],discovery,excluded,d['periodEnd'])
 atomic_json(path,d)
 if before_ids!={p['id'] for p in d['projects']}:
  from backfill_history import update_history
  update_history(d['projects'],d['periodEnd'],ROOT/'public/data')
 entries=chart_entries([json.loads(p.read_text()) for p in sorted((ROOT/'public/data/snapshots').glob('*.json'))])
 atomic_json(ROOT/'public/data/board-history.json',{'chartSize':30,'entries':entries})
 print(f'Enriched {len(d["projects"])} projects; {sum(p["editorial"] for p in d["projects"])} edited profiles. Archives preserved.')
if __name__=='__main__':main()
