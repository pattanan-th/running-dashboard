# 📱 Deploy Guide — Private Repo + Cloudflare Pages

## ✅ Status
- Local git repo: ✅ initialized + committed
- Files: 13 files (dashboard.html, JSON data, MD docs)
- Next: Push to GitHub (private) → connect Cloudflare Pages → get URL

---

## Phase 1: Create Private GitHub Repo (3 min)

### 1. ที่ github.com
- ไปที่ https://github.com/new
- **Repository name**: `korat21-dashboard` (หรือชื่ออื่น)
- **Description**: `Personal HM training dashboard` (optional)
- ⚠️ **Privacy**: เลือก **🔒 Private**
- ❌ อย่าติ๊ก "Add README", "Add .gitignore", "Add license" (เรามีอยู่แล้ว)
- กด **Create repository**

### 2. คัดลอก URL ที่ github แสดงให้
จะได้ลิงค์ประมาณนี้:
```
https://github.com/YOUR_USERNAME/korat21-dashboard.git
```

### 3. รันใน terminal (แทน YOUR_USERNAME)

```bash
cd C:/Users/iTon/garmin_korat21
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/korat21-dashboard.git
git push -u origin main
```

ถ้าถาม login → ใช้ **Personal Access Token** ไม่ใช่ password:
- ที่ github → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)
- Scopes: ติ๊ก `repo` (full control of private repositories)
- Copy token → paste แทน password ตอน push

✅ Done — code ขึ้น GitHub private repo แล้ว

---

## Phase 2: Cloudflare Pages Setup (5 min)

### 1. สมัคร Cloudflare (ถ้ายังไม่มี)
- https://dash.cloudflare.com/sign-up
- ฟรี ไม่ต้องใส่ credit card

### 2. สร้าง Pages project
- เข้า dashboard → ฝั่งซ้ายเลือก **Workers & Pages**
- กด **Create application** → tab **Pages** → **Connect to Git**
- เลือก **GitHub** → authorize Cloudflare access
- **เลือก "Only select repositories"** → ติ๊กเฉพาะ `korat21-dashboard`
- กลับมา Cloudflare → เห็น repo แล้ว → **Begin setup**

### 3. Build settings
- **Production branch**: `main`
- **Framework preset**: `None`
- **Build command**: (เว้นว่าง)
- **Build output directory**: `/` (root) หรือเว้นว่าง
- กด **Save and Deploy**

### 4. รอ ~30 วินาที
ได้ URL ประมาณ:
```
https://korat21-dashboard.pages.dev
```
หรือชื่อสุ่มแบบ `https://abc123.korat21-dashboard.pages.dev`

### 5. เข้าใช้
URL คือ:
```
https://YOUR-PROJECT.pages.dev/dashboard.html
```

✅ Online เลย!

---

## Phase 3: Add to Home Screen (มือถือ)

### iPhone (Safari)
1. เปิด URL ใน Safari
2. กดปุ่ม Share (กล่องลูกศรขึ้น)
3. เลื่อนหา "Add to Home Screen"
4. ตั้งชื่อ "Korat 21" → Add

### Android (Chrome)
1. เปิด URL ใน Chrome
2. กดเมนู ⋮ ขวาบน
3. "Install app" หรือ "Add to Home screen"

---

## 🔄 Daily Update Workflow

ทุกครั้งที่ update ข้อมูลใหม่:

```bash
cd C:/Users/iTon/garmin_korat21

# 1. (Claude Code ดึง Garmin data → update JSON)

# 2. Rebuild dashboard
python build_dashboard.py

# 3. Commit + push
git add .
git commit -m "update $(date +%Y-%m-%d)"
git push
```

→ Cloudflare auto-detect → rebuild + deploy ใน ~30 วินาที
→ refresh dashboard บนมือถือ = data ใหม่

---

## 🔒 ความปลอดภัย

| สิ่งที่ Private | สิ่งที่ Public |
|----------------|---------------|
| GitHub repo (source code, JSON files) | Dashboard URL (.pages.dev) |
| ✅ ใครเข้า repo ไม่ได้ ถ้าไม่ใช่คุณ | ⚠️ ใครได้ URL ก็เปิดได้ |

URL `*.pages.dev` ของ Cloudflare:
- **Discoverable**: ⚠️ ใครเดา URL ถูกก็เข้าได้
- **Indexed by Google**: ❌ ไม่ index (Cloudflare default `noindex`)
- **Realistic risk**: ต่ำมาก ถ้าใช้ชื่อ project unique

### ถ้าอยาก secure เพิ่ม
**Cloudflare Access** (ฟรี 50 users) → เพิ่ม email login gate:
1. ใน Cloudflare → Zero Trust → Access → Applications
2. Add application → Self-hosted
3. URL: `your-project.pages.dev`
4. Add policy: Email = `your@email.com`
→ เปิด URL จะให้ login email ก่อน

---

## 🎯 Quick Reference

| Command | Purpose |
|---------|---------|
| `python build_dashboard.py` | Rebuild HTML from JSON |
| `git add . && git commit -m "X" && git push` | Deploy to Cloudflare |
| `git status` | ดู file ที่เปลี่ยน |
| Cloudflare dashboard | ดู build logs ถ้า deploy fail |

---

## ⚠️ Troubleshooting

### Push fail "authentication required"
→ ใช้ Personal Access Token แทน password (ดูข้อ 3 ใน Phase 1)

### Cloudflare ไม่เห็น repo
→ Settings → Authorize → Edit access → ติ๊ก repo ที่ต้องการ

### Build fail บน Cloudflare
→ build output ต้องเป็น `/` หรือ root (เพราะไม่ build อะไร — แค่ serve static HTML)

### Dashboard เปลี่ยนไม่ติด
→ Hard refresh: Ctrl+Shift+R / มือถือ: ปิดเปิดแอป
→ Cloudflare cache อาจ TTL 5 นาที
