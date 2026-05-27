# 🚀 Level 2 Setup — One-Time Configuration

## ✅ What's installed
- `garminconnect` Python library ✅
- `python-dotenv` for credential management ✅
- `daily_scrape.py` — Garmin API scraper
- `update_and_deploy.bat` — full pipeline (scrape → build → push)
- `.gitignore` updated (won't commit credentials)

---

## 🔑 Step 1: Create `.env` with your Garmin credentials (30 sec)

```bash
cd C:\Users\iTon\garmin_korat21
copy .env.example .env
notepad .env
```

In `.env`, replace placeholders:
```
GARMIN_EMAIL=your_actual_email@gmail.com
GARMIN_PASSWORD=your_actual_password
```

Save & close.

⚠️ **Security**: `.env` is gitignored — credentials stay on your computer only.

---

## 🧪 Step 2: Test the scraper (first run = full login)

```bash
python daily_scrape.py
```

**First run** will:
- Prompt nothing (uses .env)
- Login to Garmin
- Cache token in `garmin_tokens/` folder (also gitignored)
- Pull last 3 days of sleep + last 14 days of activities

**Subsequent runs** reuse the cached token (no re-login).

Expected output:
```
==================================================
Garmin scraper — 2026-05-27 06:15
==================================================
[auth] Logging in fresh for you@example.com...
[auth] Token cached for next time
[sleep] + 2026-05-26: 8h 3m sleep, RHR 55
[sleep] + 2026-05-27: 7h 12m sleep, RHR 54
[sleep] 2 new entries
[activities] 0 new entries
[wellness] 2026-05-27: stress=18, RHR=54
==================================================
Done. Sleep: +2, Activities: +0
```

---

## 🌅 Step 3: Daily workflow (1 click)

**Every morning** (after Garmin watch syncs):

1. **Double-click `update_and_deploy.bat`**
2. รอ ~30 วินาที
3. รอ 1 นาทีให้ GitHub Pages rebuild
4. Refresh dashboard บนมือถือ → เห็นค่าใหม่

หรือ command line:
```bash
update_and_deploy.bat
```

---

## ⚙️ Command Reference

### Scrape options
```bash
# ปกติ — ดึง 3 วันย้อนหลัง
python daily_scrape.py

# ดึง 7 วันย้อนหลัง (ถ้าลืมหลายวัน)
python daily_scrape.py --days 7

# ดึงเฉพาะวันเดียว
python daily_scrape.py --date 2026-05-26

# ดึงแค่ sleep ไม่ดึง activity
python daily_scrape.py --skip-activities

# ดึงแค่ activity ไม่ดึง sleep
python daily_scrape.py --skip-wellness
```

### Manual steps (ถ้าอยากแยก)
```bash
# 1. Scrape only
python daily_scrape.py

# 2. Build only (after manual JSON edits)
python build_dashboard.py

# 3. Push only
git add . && git commit -m "update" && git push
```

---

## 🤖 Step 4 (Optional): Auto-run at Windows startup

หลังจาก setup เสร็จและทดสอบแล้ว ถ้าอยากให้รันอัตโนมัติทุกเช้า:

### Windows Task Scheduler:
1. เปิด Task Scheduler (Start → "Task Scheduler")
2. **Create Basic Task**:
   - Name: `Korat21 Daily Update`
   - Trigger: **When I log on**
   - Action: **Start a program**
   - Program: `C:\Users\iTon\garmin_korat21\update_and_deploy.bat`
3. ติ๊ก "Open properties..." → tab Conditions → uncheck "Start only on AC power" (สำหรับ laptop)
4. OK

→ จะรันอัตโนมัติทุกครั้งที่ login Windows

---

## 🆘 Troubleshooting

### ❌ "ERROR: Set GARMIN_EMAIL..."
ยังไม่ได้สร้าง `.env` หรือใส่ credentials ผิด
```bash
copy .env.example .env
notepad .env
```

### ❌ "GarminConnectAuthenticationError"
- Password ผิด → แก้ `.env`
- Garmin บล็อค IP → login ผ่าน browser ก่อน 1 ครั้ง
- ลบ `garmin_tokens/` folder แล้วลองใหม่

### ❌ "MFA required"
- Disable MFA ใน Garmin → Account Settings (เฉพาะ device นี้)
- หรือใช้ password-only login

### ⚠️ "no sleep data" สำหรับวันใหม่
- รอ ~6 ชม. หลังตื่นนอน Garmin ค่อย sync ข้อมูล sleep
- ลองสั่งใหม่ตอนสายๆ

### ⚠️ Activity ไม่มา
- รอ Garmin watch sync เสร็จ (เปิดแอป Garmin Connect บนมือถือ)
- รัน `python daily_scrape.py --days 1`

---

## 📂 ไฟล์ใหม่ที่สร้าง

| ไฟล์ | หน้าที่ | Git status |
|------|---------|-----------|
| `.env.example` | Template credentials | ✅ committed |
| `.env` | Your real credentials | ❌ gitignored |
| `garmin_tokens/` | Login session cache | ❌ gitignored |
| `daily_scrape.py` | Main scraper | ✅ committed |
| `update_and_deploy.bat` | Full pipeline | ✅ committed |
| `SETUP_LEVEL2.md` | This file | ✅ committed |

---

## 🎯 Compare Levels

| Level | Effort | Speed | Network needed |
|-------|--------|-------|----------------|
| 1 — Ask me | 30s/day | Slowest (browser scrape) | Yes |
| **2 — Local script** | 5s/day (1 click) | Fast (Garmin API) | Yes |
| 3 — Auto on boot | 0s/day | Same as L2 | Yes |

Level 2 = perfect spot ของคุณตอนนี้
