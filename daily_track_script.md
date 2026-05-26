# Daily Garmin Tracking Script

ใช้เมื่อต้องการอัพเดตข้อมูลรายวัน — ผู้ใช้พูดคำสั่ง "อัพเดต Garmin วันนี้" หรือ "track วันนี้"

## Pages to scrape per day

```
DATE=2026-MM-DD (today's date)

1. https://connect.garmin.com/app/sleep/{DATE}
   → total, deep, light, rem, awake, bed, wake, rhr, bb

2. https://connect.garmin.com/app/stress/{DATE}/0
   → stress_score, rest_min, low_min, medium_min, high_min

3. https://connect.garmin.com/app/body-battery
   → current BB, charged, drained, sleep_charge

4. https://connect.garmin.com/app/heart-rate/{DATE}
   → resting current, 7-day avg, high

5. https://connect.garmin.com/app/steps
   → count, distance_km, calories

6. https://connect.garmin.com/app/activities (top entry)
   → check for new activities since last update
```

## JS extraction templates

### Sleep
```javascript
var t=document.body.innerText;
var ex={d:'YYYY-MM-DD'};
var m;
m=t.match(/(\d+h \d+m)Total Sleep/);
ex.t=m?m[1]:null;
m=t.match(/\n([\w: -]+)\nDeep\n([\w: -]+)\nLight\n([\w: -]+)\nREM\n([\w: -]+)\nAwake/);
if(m){ex.dp=m[1].trim();ex.li=m[2].trim();ex.rm=m[3].trim();ex.aw=m[4].trim()}
m=t.match(/(\d+:\d+ [AP]M)\nBed Time\n(\d+:\d+ [AP]M)\nWake Time/);
if(m){ex.bd=m[1];ex.wk=m[2]}
m=t.match(/(\d+) bpm\nResting Heart Rate/);
ex.r=m?parseInt(m[1]):null;
m=t.match(/([+-]?\d+)\nBody Battery Change/);
ex.bb=m?parseInt(m[1]):null;
JSON.stringify(ex)
```

### Stress
```javascript
var t=document.body.innerText;
var m=t.match(/(\d+)Stress Level/);
var score=m?parseInt(m[1]):null;
m=t.match(/(\d+h \d+min|\d+min)\nRest\n(\d+h \d+min|\d+min)\nLow\n(\d+h \d+min|\d+min)\nMedium\n(\d+h \d+min|\d+min)\nHigh/);
JSON.stringify({score, rest:m?m[1]:null, low:m?m[2]:null, med:m?m[3]:null, high:m?m[4]:null})
```

### Heart Rate
```javascript
var t=document.body.innerText;
var m1=t.match(/(\d+) bpm\n7-Day Avg Resting/);
var m2=t.match(/(\d+) bpm\nResting(?!\sHeart)/);
var m3=t.match(/(\d+) bpm\nHigh/);
JSON.stringify({avg7:m1?parseInt(m1[1]):null, current:m2?parseInt(m2[1]):null, high:m3?parseInt(m3[1]):null})
```

## Output files
- Sleep entry → append to `sleep.json` nights[]
- Stress + HR + BB + Steps → append to `wellness.json` daily_snapshots[]
- New activity → append to `activities.json`

## Validation flags to set
- `rhr_alert`: true if RHR ≥ 60
- `sleep_alert`: true if total < 6h OR deep < 30m
- `stress_alert`: true if stress_score > 50
- `bb_alert`: true if max BB < 50

## Race countdown
- W12: 29 May - 1 Jun (Peak)
- W13: 5-7 Jun (Taper 1)
- W14: 12-14 Jun (Taper 2 + 5K fun run)
- W15: 21 Jun (Race day)
