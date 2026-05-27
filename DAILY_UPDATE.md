# 📱 Daily Update Workflow

## 🎯 ปัจจุบัน: ขั้นตอนที่เร็วที่สุด

### หลังตื่นนอนทุกเช้า (3 นาที):

**Option A — ผ่าน Claude Code (แนะนำ):**
```
1. เปิด Claude Code
2. พิมพ์: "อัพเดต Garmin วันนี้"
3. รอผม scrape + update + push (~2 นาที)
4. รอ 1 นาที → refresh มือถือ → เห็นค่าใหม่
```

**Option B — Manual หลังเปิด JSON ด้วยมือ:**
```
1. เปิด Garmin Connect app → จดเลข sleep + RHR + BB
2. แก้ sleep.json เพิ่มคืนล่าสุด
3. Double-click update_and_deploy.bat
4. รอ 1 นาที → refresh มือถือ
```

---

## 📂 ไฟล์ที่ต้อง update บ่อย

| ไฟล์ | ความถี่ | อะไรเปลี่ยน |
|------|---------|-------------|
| `sleep.json` | ทุกวัน | เพิ่ม entry คืนล่าสุดใน `nights[]` |
| `activities.json` | หลังวิ่ง | เพิ่ม entry ใน `long_runs[]`/`tempos_intervals[]`/`easy_runs[]` |
| `wellness.json` | optional | อัพเดต `daily_snapshots[]` ของวันนี้ |
| `plan.json` | เมื่อแก้แผน | เซ็ต `actual_km` หลังจบสัปดาห์ |

---

## ⚡ Quick Command Reference

```bash
# จาก folder garmin_korat21/

# Build dashboard
python build_dashboard.py

# Push to GitHub (auto-deploy)
git add . && git commit -m "update" && git push

# All-in-one
update_and_deploy.bat
```

---

## 🤖 Auto-deploy ทำงานยังไง

```
Local edit JSON  →  python build  →  git push
                                         ↓
            GitHub Pages auto-rebuilds (~30-60 sec)
                                         ↓
                  Phone refreshes dashboard
                                         ↓
                  Latest data visible
```

URL ของ dashboard:
**https://pattanan-th.github.io/running-dashboard/dashboard.html**

---

## 📊 ข้อมูลที่ควรเก็บ/อัพเดตทุกวัน

### Morning routine (5 นาที):
1. ดู Garmin sleep stats → บอกผม หรือ paste มาให้
2. ดู RHR + Body Battery → บอกผมว่าวันนี้พร้อมแค่ไหน
3. ผมประเมิน readiness (RED/YELLOW/GREEN) ตาม baseline
4. ผม update + push ให้

### หลังจบ run (5 นาที):
1. รอ Garmin sync เสร็จ (~1 นาที)
2. บอกผม URL กิจกรรมหรือชื่อ
3. ผม scrape ดึง stats + zones + cadence + walking %
4. ผม update activities.json + plan.json (actual_km)

### Weekly review (10 นาที วันจันทร์):
- ดู total km ของสัปดาห์ที่ผ่าน
- เทียบ planned vs actual
- ผมเตือนถ้ามี trend แปลก (เช่น RHR ค้าง 60 หลายวัน)

---

## 🥇 Level 3 (อนาคต): Full Auto

ถ้าวันหลังอยากให้ทำงานเองโดยไม่ต้องสั่ง:

### ต้องมี:
1. **Python garmin-connect library** — ดึงข้อมูลผ่าน API ตรง (ไม่ผ่าน browser)
2. **Garmin email + password** ใน `.env` file (encrypted)
3. **Windows Task Scheduler** — รัน script ตอนเปิดคอมตอนเช้า

### Script จะทำ:
```
1. Login Garmin API
2. Download yesterday's sleep + any new activity
3. Update JSON files
4. Build dashboard
5. Git commit + push
6. (optional) Notification "Update done"
```

ขอ implement ได้ตอนหลัง ถ้าสะดวกให้ลง Python lib

---

## ❓ FAQ

**Q: ถ้าลืม update 3-4 วันจะอย่างไร?**
A: บอกผม "อัพเดต Garmin ย้อนหลัง 4 วัน" → ผม scrape ทั้งหมดทีเดียว

**Q: แก้ plan ในมือถือแล้ว ทำยังไงให้คอม sync?**
A: ในมือถือกด **⬇️ Export** → ส่งไฟล์ `plan.json` มาคอม → ทับไฟล์เดิมใน `garmin_korat21/` → run `update_and_deploy.bat`

**Q: รับ notification ตอน race day ได้ไหม?**
A: ถ้าใช้ Add to Home Screen แล้ว → ดูใน dashboard เอง (race countdown ที่หัวบอก "0 days left")

**Q: ข้อมูลใน mobile cache เก่าไป?**
A: Pull down to refresh ใน Safari/Chrome → หรือปิดเปิดแอป → หรือ hard refresh

---

## 🎯 ทำขั้นต่ำ (busy day, 1 นาที)

แค่บอกผม:
```
อัพเดต Garmin
```

ผมทำที่เหลือเอง 👍
