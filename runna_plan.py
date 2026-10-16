"""Fetch the upcoming Runna plan from its calendar feed -> runna_plan.json.

The feed URL is a private token: it lives in .env as RUNNA_ICS_URL and is never
written to any output. Only UPCOMING_PLAN_WORKOUT events are kept — completed
events carry GEO/LOCATION, which must not reach the public dashboard. The
per-workout "View in the Runna app" deep link is stripped for the same reason.

On a fetch/parse failure the previous runna_plan.json is left untouched and the
script exits 0, so a Runna outage never blocks the Zepp sync or the deploy.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
OUT = HERE / 'runna_plan.json'

# UID suffix -> display bucket used by the dashboard colours
KINDS = {
    'EASY_RUN': 'easy', 'LONG_RUN': 'long', 'TEMPO': 'tempo', 'INTERVALS': 'intervals',
    'TAPER_INTERVALS': 'intervals', 'RACE': 'race',
}


def unescape(v):
    return v.replace('\\n', '\n').replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\')


def parse(ics):
    ics = re.sub(r'\r?\n[ \t]', '', ics.replace('\r\n', '\n'))  # unfold continuation lines
    events = []
    for block in re.findall(r'BEGIN:VEVENT\n(.*?)END:VEVENT', ics, re.S):
        ev = {}
        for line in block.strip().split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                ev[k.split(';')[0]] = v
        if not ev.get('UID', '').startswith('UPCOMING_PLAN_WORKOUT'):
            continue
        m = re.search(r'_plan_week_(\d+)_([A-Z_]+?)_\d+$', ev['UID'])
        week, kind = (int(m.group(1)), m.group(2)) if m else (None, 'OTHER')
        desc = unescape(ev.get('DESCRIPTION', ''))
        desc = re.sub(r'\n*📲 View in the Runna app:.*$', '', desc, flags=re.S).strip()
        head, _, body = desc.partition('\n\n')
        # head looks like "Tempo • 11km • 1h0m - 1h20m"
        parts = [p.strip() for p in head.split('•')]
        d = ev['DTSTART'][:8]
        events.append({
            'date': f'{d[:4]}-{d[4:6]}-{d[6:]}',
            'week': week,
            'kind': KINDS.get(kind, 'other'),
            'title': re.sub(r'^\W+\s*', '', unescape(ev.get('SUMMARY', ''))).split(' • ')[0],
            'category': parts[0] if parts else '',
            'distance': parts[1] if len(parts) > 1 else '',
            'duration': parts[2] if len(parts) > 2 else '',
            'est_min': round(int(ev['X-WORKOUT-ESTIMATED-DURATION']) / 60) if ev.get('X-WORKOUT-ESTIMATED-DURATION', '').isdigit() else None,
            'details': body.strip(),
        })
    apply_overrides(events)
    events.sort(key=lambda e: e['date'])
    return events


def apply_overrides(events):
    """Re-date workouts the user moved on their own schedule (plan_overrides.json).
    An override only fires while the feed still carries the `from` date, so once the
    move is also made in the Runna app it becomes a harmless no-op, never a double shift."""
    path = HERE / 'plan_overrides.json'
    if not path.exists():
        return
    for o in json.loads(path.read_text(encoding='utf-8')).get('moves', []):
        for e in events:
            if e['week'] == o['week'] and e['kind'] == o['kind'] and e['date'] == o['from']:
                e['date'], e['moved_from'] = o['to'], o['from']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    load_dotenv(HERE / '.env')
    url = os.getenv('RUNNA_ICS_URL')
    if not url:
        print('[runna] RUNNA_ICS_URL not set in .env — plan not refreshed')
        return
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            ics = r.read().decode('utf-8')
        events = parse(ics)
    except Exception as e:
        print(f'[runna] fetch failed, keeping previous runna_plan.json: {e}')
        return
    if not events:
        print('[runna] feed had no upcoming workouts — keeping previous runna_plan.json')
        return
    OUT.write_text(json.dumps({
        'meta': {'source': 'Runna calendar feed', 'fetched': datetime.now().strftime('%Y-%m-%d %H:%M')},
        'workouts': events,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[runna] {len(events)} upcoming workouts · {events[0]["date"]} → {events[-1]["date"]}')


if __name__ == '__main__':
    main()
