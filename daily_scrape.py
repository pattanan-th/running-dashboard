"""
Daily Garmin Connect scraper — Level 2 automation.

Pulls yesterday's sleep + any new activities, merges into sleep.json/activities.json.
Idempotent: won't duplicate entries that already exist.

Usage:
    python daily_scrape.py              # pull missing days up to yesterday
    python daily_scrape.py --days 7     # pull last 7 days
    python daily_scrape.py --date 2026-05-26
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError

HERE = Path(__file__).parent
TOKEN_DIR = HERE / 'garmin_tokens'
TOKEN_DIR.mkdir(exist_ok=True)

load_dotenv(HERE / '.env')
EMAIL = os.getenv('GARMIN_EMAIL')
PASSWORD = os.getenv('GARMIN_PASSWORD')

if not EMAIL or not PASSWORD:
    print('ERROR: Set GARMIN_EMAIL + GARMIN_PASSWORD in .env file')
    print('(Copy .env.example to .env and fill in your credentials)')
    sys.exit(1)


def login() -> Garmin:
    """Login to Garmin, using cached tokens when possible."""
    api = Garmin(EMAIL, PASSWORD)
    try:
        api.login(str(TOKEN_DIR))
        print(f'[auth] Using cached session for {EMAIL}')
    except (FileNotFoundError, GarminConnectAuthenticationError):
        print(f'[auth] Logging in fresh for {EMAIL}...')
        api.login()
        api.garth.dump(str(TOKEN_DIR))
        print('[auth] Token cached for next time')
    return api


def fmt_duration(seconds: int | float | None) -> str | None:
    if seconds is None:
        return None
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f'{h}h {m}m' if h else f'{m}m'


def load_json(name: str) -> dict:
    path = HERE / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(name: str, data: dict) -> None:
    path = HERE / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# ===== Sleep =====
def scrape_sleep(api: Garmin, day: date) -> dict | None:
    """Return a sleep entry matching sleep.json schema, or None if no data."""
    try:
        data = api.get_sleep_data(day.isoformat())
    except Exception as e:
        print(f'[sleep {day}] error: {e}')
        return None
    if not data or 'dailySleepDTO' not in data:
        return None
    s = data['dailySleepDTO']
    total = s.get('sleepTimeSeconds')
    if not total:
        return None

    # Try multiple paths for stage data
    deep = s.get('deepSleepSeconds') or 0
    light = s.get('lightSleepSeconds') or 0
    rem = s.get('remSleepSeconds') or 0
    awake = s.get('awakeSleepSeconds') or 0

    bed_ts = s.get('sleepStartTimestampLocal')
    wake_ts = s.get('sleepEndTimestampLocal')
    bed = datetime.fromtimestamp(bed_ts / 1000).strftime('%I:%M %p').lstrip('0') if bed_ts else None
    wake = datetime.fromtimestamp(wake_ts / 1000).strftime('%I:%M %p').lstrip('0') if wake_ts else None

    entry = {
        'd': day.isoformat(),
        't': fmt_duration(total),
        'dp': fmt_duration(deep) if deep else '--',
        'li': fmt_duration(light),
        'rm': fmt_duration(rem) if rem else '--',
        'aw': fmt_duration(awake) if awake else '--',
        'bd': bed,
        'wk': wake,
        'r': s.get('restingHeartRate'),
        'bb': s.get('bodyBatteryChange'),
    }
    return entry


def update_sleep(api: Garmin, dates: list[date]) -> int:
    sleep_file = load_json('sleep.json')
    if not sleep_file:
        print('[sleep] sleep.json missing or empty — abort')
        return 0
    nights = sleep_file.get('nights', [])
    existing = {n.get('d') for n in nights}
    added = 0
    for d in dates:
        if d.isoformat() in existing:
            continue
        entry = scrape_sleep(api, d)
        if entry:
            nights.append(entry)
            existing.add(entry['d'])
            print(f'[sleep] + {entry["d"]}: {entry.get("t","?")} sleep, RHR {entry.get("r","?")}')
            added += 1
        else:
            nights.append({'d': d.isoformat(), 't': None, 'note': 'no sleep data'})
            print(f'[sleep] {d}: no data')
    nights.sort(key=lambda x: x.get('d', ''))
    sleep_file['nights'] = nights
    sleep_file['meta']['nights_collected'] = len([n for n in nights if n.get('t')])
    sleep_file['meta']['date_range'] = f'{nights[0]["d"]} to {nights[-1]["d"]}'
    save_json('sleep.json', sleep_file)
    return added


# ===== Activities =====
def scrape_activities(api: Garmin, since: date) -> list[dict]:
    """Get activities since a given date."""
    try:
        activities = api.get_activities_by_date(
            since.isoformat(),
            date.today().isoformat(),
            'running',
        )
    except Exception as e:
        print(f'[activities] error: {e}')
        return []
    return activities


def normalize_pace(speed_mps: float | None) -> str | None:
    """Convert m/s to mm:ss/km string."""
    if not speed_mps or speed_mps <= 0:
        return None
    pace_sec_per_km = 1000.0 / speed_mps
    m = int(pace_sec_per_km // 60)
    s = int(pace_sec_per_km % 60)
    return f'{m}:{s:02d}'


def fmt_time(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f'{h}:{m:02d}:{sec:02d}'
    return f'{m}:{sec:02d}'


def activity_to_entry(act: dict) -> dict:
    """Convert Garmin activity dict to our schema."""
    name = act.get('activityName', '')
    start = (act.get('startTimeLocal') or '')[:10]
    dist_m = act.get('distance') or 0
    duration = act.get('duration') or 0
    avg_speed = act.get('averageSpeed')
    return {
        'wk': None,  # caller can derive from training plan week
        'date': start,
        'name': name,
        'id': str(act.get('activityId')),
        'dist': round(dist_m / 1000, 2),
        'time': fmt_time(duration),
        'pace': normalize_pace(avg_speed),
        'hr_avg': act.get('averageHR'),
        'hr_max': act.get('maxHR'),
        'cad': act.get('averageRunningCadenceInStepsPerMinute'),
        'cad_max': act.get('maxRunningCadenceInStepsPerMinute'),
        'stride': round((act.get('avgStrideLength') or 0) / 100, 2) if act.get('avgStrideLength') else None,
        'temp': act.get('averageTemperature'),
        'ascent': act.get('elevationGain'),
    }


def update_activities(api: Garmin, since_days: int = 14) -> int:
    """Pull recent activities. Append new ones (idempotent by activity id)."""
    activities_file = load_json('activities.json')
    if not activities_file:
        print('[activities] activities.json missing — abort')
        return 0
    since = date.today() - timedelta(days=since_days)
    acts = scrape_activities(api, since)
    if not acts:
        return 0

    # Index existing by id across all run categories
    existing_ids = set()
    for key in ('long_runs', 'tempos_intervals', 'easy_runs'):
        for e in activities_file.get(key, []):
            if e.get('id'):
                existing_ids.add(str(e['id']))

    added = 0
    for act in acts:
        aid = str(act.get('activityId'))
        if aid in existing_ids:
            continue
        entry = activity_to_entry(act)
        # Heuristic: classify by name + distance
        name_lower = (entry['name'] or '').lower()
        if 'long' in name_lower or entry['dist'] >= 13:
            bucket = 'long_runs'
        elif any(k in name_lower for k in ('tempo', 'interval', 'fartlek', 'progression')):
            bucket = 'tempos_intervals'
        else:
            bucket = 'easy_runs'
        activities_file.setdefault(bucket, []).append(entry)
        existing_ids.add(aid)
        print(f'[activity] + {entry["date"]} {entry["name"]} → {bucket} ({entry["dist"]}km @ {entry["pace"]})')
        added += 1

    # Sort each bucket by date desc
    for key in ('long_runs', 'tempos_intervals', 'easy_runs'):
        if key in activities_file:
            activities_file[key].sort(key=lambda x: x.get('date', ''), reverse=True)

    save_json('activities.json', activities_file)
    return added


# ===== Wellness daily snapshot =====
def update_wellness(api: Garmin, day: date) -> bool:
    wellness = load_json('wellness.json')
    if not wellness:
        return False
    try:
        stress = api.get_stress_data(day.isoformat())
        steps = api.get_steps_data(day.isoformat())
        hr = api.get_heart_rates(day.isoformat())
    except Exception as e:
        print(f'[wellness] error: {e}')
        return False

    snap = {
        'date': day.isoformat(),
        'stress': {
            'score': stress.get('avgStressLevel') if isinstance(stress, dict) else None,
        },
        'rhr': {
            'current': hr.get('restingHeartRate') if isinstance(hr, dict) else None,
        },
        'steps': {
            'count': sum(s.get('steps', 0) for s in steps) if isinstance(steps, list) else None,
        },
    }
    # Replace today's snapshot if exists, else append
    snaps = wellness.setdefault('daily_snapshots', [])
    snaps = [s for s in snaps if s.get('date') != day.isoformat()]
    snaps.append(snap)
    snaps.sort(key=lambda x: x.get('date', ''))
    wellness['daily_snapshots'] = snaps
    save_json('wellness.json', wellness)
    print(f'[wellness] {day}: stress={snap["stress"]["score"]}, RHR={snap["rhr"]["current"]}')
    return True


# ===== Main =====
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=3, help='Look back N days for sleep (default 3)')
    ap.add_argument('--date', help='Specific date YYYY-MM-DD (overrides --days)')
    ap.add_argument('--skip-activities', action='store_true')
    ap.add_argument('--skip-wellness', action='store_true')
    args = ap.parse_args()

    print('=' * 50)
    print(f'Garmin scraper — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 50)

    api = login()

    today = date.today()
    if args.date:
        dates = [date.fromisoformat(args.date)]
    else:
        dates = [today - timedelta(days=i) for i in range(args.days)]
        dates.reverse()

    sleep_added = update_sleep(api, dates)
    print(f'[sleep] {sleep_added} new entries')

    act_added = 0
    if not args.skip_activities:
        act_added = update_activities(api, since_days=14)
        print(f'[activities] {act_added} new entries')

    if not args.skip_wellness:
        update_wellness(api, today)

    print('=' * 50)
    print(f'Done. Sleep: +{sleep_added}, Activities: +{act_added}')
    print('Next: run "python build_dashboard.py" then git push')


if __name__ == '__main__':
    main()
