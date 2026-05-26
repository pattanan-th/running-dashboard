# 📱 Dashboard — วิธีใช้บนมือถือ

## ไฟล์ที่สร้าง
- `dashboard.html` — Single file ~50KB (ไม่ต้องมี internet ตอนใช้)
- `build_dashboard.py` — Script รวม JSON → HTML (รัน `python build_dashboard.py` เพื่ออัพเดต)

## 🎯 มี 4 วิธี deploy เลือกตามสะดวก

### 1. ⭐ ง่ายสุด: Send to phone + open
**Mac/iPhone**: AirDrop ส่ง `dashboard.html` → เปิดใน Safari
**Android**: ส่งทาง LINE/Email → เปิดใน Chrome

✅ ใช้ได้เลย ไม่ต้อง setup
❌ ทุกครั้งที่ update → ต้องส่งใหม่

---

### 2. ⚡ Local Wi-Fi (เปิดบนคอม, เข้าจากมือถือ)
บนคอม:
```bash
cd C:/Users/iTon/garmin_korat21
python -m http.server 8000
```
ดู IP address คอม (เช่น `ipconfig` → 192.168.1.X) → บนมือถือเปิด:
```
http://192.168.1.X:8000/dashboard.html
```

✅ Update ใน real-time (refresh มือถือ = ดูค่าใหม่)
❌ ต้องอยู่ Wi-Fi เดียวกัน + คอมต้องเปิด

---

### 3. ⭐⭐ **Recommended**: GitHub Pages (ฟรี, ออนไลน์ตลอด)
1. ติดตั้ง git (ถ้ายังไม่มี)
2. สร้าง repo ที่ github.com (เช่น `korat21-dashboard`) → Private OK
3. รันใน folder:
```bash
cd C:/Users/iTon/garmin_korat21
git init
git add dashboard.html
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/USERNAME/korat21-dashboard.git
git push -u origin main
```
4. ใน GitHub repo → Settings → Pages → Source = `main` branch
5. รอ 1-2 นาที → ได้ URL: `https://USERNAME.github.io/korat21-dashboard/dashboard.html`
6. เปิดบนมือถือ → "Add to Home Screen" → ใช้ได้เลย

✅ Online ตลอด, update ง่าย (`git push`)
✅ มี URL ส่งคนอื่นได้
❌ ต้อง setup git ครั้งแรก

---

### 4. ⭐⭐⭐ Auto-update GitHub (best for daily tracking)
Setup script ที่จะ:
1. Pull Garmin data ใหม่
2. Build dashboard
3. Push GitHub auto
→ มือถือเปิด URL = data ล่าสุดเสมอ

ขอ implement ทีหลังถ้าอยากได้

---

## 📲 Add to Home Screen (ทำให้เป็น "แอป")

### iPhone (Safari)
1. เปิด URL ใน Safari
2. กดปุ่ม Share (กล่องลูกศรขึ้น)
3. เลื่อนหา "Add to Home Screen"
4. ตั้งชื่อ "Korat 21" → Add
5. มี icon บนหน้า home แล้ว — เปิดเต็มจอเหมือนแอป

### Android (Chrome)
1. เปิด URL ใน Chrome
2. กดเมนู ⋮ ขวาบน
3. "Install app" หรือ "Add to Home screen"
4. ตั้งชื่อ → Install

---

## 🔄 Update workflow

ทุกครั้งที่อัพเดตข้อมูลใน JSON:
```bash
cd C:/Users/iTon/garmin_korat21
python build_dashboard.py     # rebuild HTML
git add dashboard.html         # ถ้าใช้ GitHub
git commit -m "update $(date)"
git push                       # มือถือ refresh เห็นค่าใหม่
```

---

## 📊 Dashboard features

| Tab | ดูอะไรได้ |
|-----|----------|
| 📊 **Status** | Readiness score (RED/YELLOW/GREEN), เมื่อคืน sleep, PRs, รองเท้า |
| 🏃 **Runs** | Chart Long Runs progression, Cadence จริง vs display, Zone bars |
| 💤 **Sleep** | Chart 30 วันล่าสุด: sleep hours / RHR / Body Battery |
| 🏁 **Race Plan** | KM-by-KM pacing, fueling, decision tree |
| ✅ **Checklist** | Race morning timeline, pack list (กดทำเครื่องหมายได้) |

### Special features
- **Race countdown** ด้านบน — เหลือกี่วันถึง 21 มิ.ย.
- **Live readiness** — คำนวณจาก RHR + Sleep ของคืนล่าสุด
- **Offline-ready** — เปิดครั้งแรกแล้ว ใช้บนเครื่องบินได้
- **Interactive checklist** — แตะเพื่อทำเครื่องหมาย

---

## 🎨 ที่ปรับได้

ใน `build_dashboard.py` ถ้าอยาก customize:
- เปลี่ยนสี: ดู `:root { --primary: #1F4E78; }`
- เพิ่ม tab: ก๊อป pattern `<section class="page" id="page-XXX">`
- เพิ่ม chart: ใช้ Chart.js syntax เหมือนเดิม

ขอใช้ผมช่วยปรับได้ตลอดครับ
