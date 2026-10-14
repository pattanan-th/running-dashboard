"""Recompute shoe mileage from the gear each Zepp workout was logged with -> shoes.json.

Zepp tags every workout with a gearId, but ZeppBridge only keeps it inside the
compressed raw workout payloads and never fetches the shoe names. shoes.json
maps each shoe to its gear_ids; this script adds every Zepp run after the shoe's
base_date to its base_km. Runs where the user swapped shoes mid-run are split
by `manual_splits`. GearIds nobody has named yet are listed under `unassigned`
so mileage is never silently attributed to the wrong shoe.

Run after sync_zepp.py (it needs the ZeppBridge database for the gearIds).
"""
import json
import sqlite3
import sys
import zlib
from datetime import date
from pathlib import Path

from sync_zepp import default_data_dir

HERE = Path(__file__).parent


def gear_by_workout(db):
    con = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    out = {}
    for (blob,) in con.execute("select payload_zip from raw_records where stream='workouts' and payload_zip is not null"):
        stack = [json.loads(zlib.decompress(blob))]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if x.get('gearId') and x.get('trackid'):
                    out[f"zepp:{x['trackid']}"] = x['gearId']
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    db = default_data_dir() / 'zepp.db'
    if not db.exists():
        print('[shoes] ZeppBridge database not found — shoe mileage not refreshed')
        return
    gear = gear_by_workout(db)
    acts = json.loads((HERE / 'activities.json').read_text(encoding='utf-8'))
    runs = [x for v in acts.values() if isinstance(v, list) for x in v
            if isinstance(x, dict) and str(x.get('id', '')).startswith('zepp:') and x.get('dist')]
    shoes_path = HERE / 'shoes.json'
    data = json.loads(shoes_path.read_text(encoding='utf-8'))
    shoes = data['shoes']
    owner = {g: s for s in shoes for g in s.get('gear_ids', [])}
    splits = {m['workout']: m['parts'] for m in data.get('manual_splits', [])}

    for s in shoes:
        s['zepp_km'], s['zepp_runs'], s['last_used'] = 0.0, 0, s.get('last_used')
    unassigned = {}

    def credit(shoe, km, day):
        if shoe.get('base_date') and day <= shoe['base_date']:
            return  # already inside base_km
        shoe['zepp_km'] += km
        shoe['zepp_runs'] += 1
        shoe['last_used'] = max(shoe['last_used'] or day, day)

    by_id = {s['id']: s for s in shoes}
    for r in runs:
        day, km = r['date'], float(r['dist'])
        if r['id'] in splits:
            rest = km - sum(p['km'] for p in splits[r['id']] if p['km'] != 'rest')
            for p in splits[r['id']]:
                credit(by_id[p['shoe']], rest if p['km'] == 'rest' else p['km'], day)
            continue
        g = gear.get(r['id'])
        if g in owner:
            credit(owner[g], km, day)
        else:
            u = unassigned.setdefault(g or 'none', {'gear_id': g, 'runs': 0, 'km': 0.0, 'dates': []})
            u['runs'] += 1
            u['km'] += km
            u['dates'].append(day)

    for s in shoes:
        s['zepp_km'] = round(s['zepp_km'], 1)
        s['km'] = round(s.get('base_km', 0) + s['zepp_km'])
    data['unassigned'] = [dict(u, km=round(u['km'], 1), dates=sorted(u['dates'])) for u in unassigned.values()]
    data['meta']['last_updated'] = date.today().isoformat()
    shoes_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    for s in shoes:
        print(f"[shoes] {s['nick']}: {s['km']} km (+{s['zepp_km']} km / {s['zepp_runs']} Zepp runs)")
    for u in data['unassigned']:
        print(f"[shoes] unassigned {str(u['gear_id'])[:8]}: {u['runs']} runs · {u['km']} km")


if __name__ == '__main__':
    main()
