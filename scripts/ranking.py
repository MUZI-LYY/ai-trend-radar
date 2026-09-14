"""Period boundaries and observed daily chart tenure, shared by collection and tests."""
import datetime as dt

DAILY_CHART_SIZE = 30

def period_starts(end):
 date = dt.date.fromisoformat(end)
 return {'daily': end, 'weekly': (date-dt.timedelta(days=date.weekday())).isoformat(),
         'monthly': end[:7]+'-01', 'yearly': end[:4]+'-01-01'}

def daily_leaders(projects):
 valid = [p for p in projects if not p.get('stale') and p['metrics'].get('daily') is not None and p['metrics']['daily'] > 0]
 return [p['id'] for p in sorted(valid, key=lambda p: (-p['metrics']['daily'], -p['stars'], p['fullName'].lower()))[:DAILY_CHART_SIZE]]

def chart_entry(payload):
 return {'date': payload['periodEnd'], 'capturedDate': payload['date'], 'ids': daily_leaders(payload['projects'])}

def chart_entries(payloads):
 """Use the first archived observation of a source day, even across capture dates."""
 entries={}
 for payload in sorted(payloads,key=lambda p:(p['date'],p.get('capturedAt',''))):
  entry=chart_entry(payload)
  entries.setdefault(entry['date'],entry)
 return [entries[date] for date in sorted(entries)]

def observed_tenure(project_id, end, current_ids, entries):
 if project_id not in current_ids: return None
 by_date = {}
 for entry in sorted(entries,key=lambda e:e.get('capturedDate',e['date'])):
  if entry['date'] < end:by_date.setdefault(entry['date'],set(entry['ids']))
 date = dt.date.fromisoformat(end); days = 1
 while project_id in by_date.get((date-dt.timedelta(days=1)).isoformat(), set()):
  date -= dt.timedelta(days=1); days += 1
 return {'days': days, 'since': date.isoformat()}
