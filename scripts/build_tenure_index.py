"""Build the cumulative daily TOP 30 index used by the website.

Saved daily charts take precedence. Earlier dates are reconstructed from the
official per-repository Star history for the currently tracked collection.
"""
import json
from collections import defaultdict
from pathlib import Path

from ranking import daily_leaders

ROOT = Path(__file__).resolve().parents[1] / 'public' / 'data'


def cumulative_chart(latest, history, history_index, saved):
    end = latest['periodEnd']
    dates = {day for day in history_index['dates'] if day <= end}
    current = {project['id']: project for project in latest['projects']}
    candidates = defaultdict(list)
    for record in history['projects']:
        project = current.get(record['id'])
        if project is None:
            continue
        name = project['fullName'].lower()
        for day in record['days']:
            date, growth = day['date'], day['stars']
            if date in dates and growth > 0:
                candidates[date].append((-growth, name, project['id']))

    archived = {}
    for entry in sorted(saved['entries'], key=lambda item: (item['capturedDate'], item['date'])):
        if entry['date'] <= end:
            archived.setdefault(entry['date'], entry['ids'])

    dates.update(archived)
    dates.add(end)
    entries = []
    for date in sorted(dates):
        if date == end:
            ids, source = daily_leaders(latest['projects']), 'latest'
        elif date in archived:
            ids, source = archived[date], 'snapshot'
        else:
            ids = [identity for _, _, identity in sorted(candidates[date])[:30]]
            source = 'retrospective'
        entries.append({'date': date, 'ids': ids, 'source': source})
    return {'chartSize': 30, 'start': entries[0]['date'], 'end': end,
            'scope': history['scope'], 'entries': entries}


def main():
    def read(name):
        return json.loads((ROOT / name).read_text())

    chart = cumulative_chart(read('latest.json'), read('history.json'),
                             read('history-index.json'), read('board-history.json'))
    target = ROOT / 'cumulative-chart.json'
    target.write_text(json.dumps(chart, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Built {len(chart["entries"])} cumulative daily charts: {chart["start"]} — {chart["end"]}')


if __name__ == '__main__':
    main()
