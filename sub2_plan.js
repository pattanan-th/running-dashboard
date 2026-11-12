// ===== PLAN TAB: maintenance running + speedwork calculator + PPL =====
// Settings live in plan_settings.json in the GitHub repo so phone and PC share them.
// The Save button writes that file through the GitHub contents API with a
// fine-grained token kept only in this device's localStorage.
const SUB2_REPO = 'pattanan-th/running-dashboard', SUB2_FILE = 'plan_settings.json', SUB2_TOKEN_KEY = 'sub2_gh_token';
const SUB2_DEF = {start: '2026-11-20', bench: {type: 'hm', time: '2:23:17'}, weekly_km: 30, heat: 'warm', updated: ''};
const S2_DIST = {'5k': 5000, '10k': 10000, hm: 21097.5, fm: 42195};
const S2_HEAT = {cool: [1, 'เย็น ≤25°C'], warm: [1.03, 'อุ่น 26-29°C (+3%)'], hot: [1.06, 'ร้อน 30°C+ (+6%)']};
let sub2 = null, sub2Sha = null, sub2Dirty = false;

function s2Norm(s) {
  s = Object.assign({}, SUB2_DEF, s || {});
  s.bench = Object.assign({}, SUB2_DEF.bench, s.bench || {});
  return s;
}
const s2Clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const s2Fmt = s => { s = Math.round(s); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const s2FmtH = s => { s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };

// ----- VDOT (Daniels & Gilbert) -----
const s2Vo2 = v => -4.60 + 0.182258 * v + 0.000104 * v * v;           // v in m/min
const s2Pct = t => 0.8 + 0.1894393 * Math.exp(-0.012778 * t) + 0.2989558 * Math.exp(-0.1932605 * t);
const s2Vel = x => (-0.182258 + Math.sqrt(0.182258 * 0.182258 + 4 * 0.000104 * (x + 4.60))) / (2 * 0.000104);
const s2VdotOf = (d, sec) => s2Vo2(d / (sec / 60)) / s2Pct(sec / 60);
function s2RaceSec(vd, d) {
  let lo = d * 0.1, hi = d * 1.2;
  for (let i = 0; i < 60; i++) { const mid = (lo + hi) / 2; s2VdotOf(d, mid) > vd ? lo = mid : hi = mid; }
  return (lo + hi) / 2;
}
function s2BenchSec(st) {
  const d = S2_DIST[st.bench.type] || S2_DIST.hm;
  const p = String(st.bench.time || '').trim().split(':').map(Number);
  if (!p.length || p.some(x => isNaN(x))) return 0;
  let sec = p.reduce((a, b) => a * 60 + b, 0);
  if (p.length === 2 && d > 15000 && p[0] < 6) sec *= 60;   // "2:23" on a half = h:mm
  return sec;
}
// Paces in s/km with the heat factor applied; null when the result is unusable.
function s2Zones(st) {
  const d = S2_DIST[st.bench.type] || S2_DIST.hm, sec = s2BenchSec(st);
  if (!(sec > d / 1000 * 150)) return null;   // faster than 2:30/km = typo
  const vd = s2VdotOf(d, sec), f = (S2_HEAT[st.heat] || S2_HEAT.cool)[0];
  const pk = v => 60000 / v * f;
  const vI = s2Vel(0.98 * vd);
  const hmSec = s2RaceSec(vd, S2_DIST.hm);
  return {vd, f,
    E: [pk(s2Vel(0.70 * vd)), pk(s2Vel(0.62 * vd))],
    HM: hmSec / 21.0975 * f, T: pk(s2Vel(0.88 * vd)), I: pk(vI), R: pk(vI * 1.06),
    pred: {'5K': s2RaceSec(vd, 5000), '10K': s2RaceSec(vd, 10000), 'Half': hmSec, 'Full': s2RaceSec(vd, S2_DIST.fm)}};
}

const S2_HOW = [["Bulgarian", "วางหลังเท้าข้างหลังบนเก้าอี้/โซฟา ขาหน้าก้าวออกไป ~1 ก้าวยาว ถือดัมเบลข้างลำตัว → ย่อตัวลงตรงๆ จนต้นขาหน้าขนานพื้น เข่าหลังเกือบแตะพื้น → ดันส้นเท้าหน้ากลับขึ้น"], ["Single-Leg RDL", "ยืนขาเดียว ถือ DB มือตรงข้ามกับขาที่ยืน → ก้มตัวไปข้างหน้าพร้อมยกขาหลังไปด้านหลัง ให้ลำตัวกับขาเป็นเส้นตรง → ลงจนตึงหลังต้นขา แล้วบีบก้นยืดกลับ · เสียหลักแตะปลายเท้าหลังได้"], ["Single-Leg Calf", "ยืนขาเดียวบนขอบบันได ส้นเท้าลอย มือหนึ่งจับราว อีกมือถือ DB → เขย่งขึ้นสุด ค้าง 1 วิ → ลดส้นลงช้า 3 วิ จนต่ำกว่าขั้น"], ["KB Goblet", "ถือ KB แนบอกสองมือ เท้ากว้างกว่าไหล่เล็กน้อย ปลายเท้าแบะนิด → นั่งลงเหมือนนั่งเก้าอี้ต่ำ ศอกอยู่ระหว่างเข่า → ค้างล่าง 2 วิ แล้วดันขึ้น"], ["Pogo", "Pogo: กระโดดเบาๆ ต่อเนื่องด้วยปลายเท้า เข่าเกือบตึง เหมือนลูกบอลเด้ง · Jump squat: ย่อครึ่งทางแล้วกระโดดสูงสุด ลงปลายเท้าแล้วย่อซับแรง"], ["Single-Leg Glute", "นอนหงาย ชันเข่าข้างหนึ่ง อีกขาเหยียดลอย → ดันส้นเท้ายกสะโพกจนตัวตรงจากไหล่ถึงเข่า บีบก้นค้าง 1 วิ → ลงช้าๆ"], ["Side Plank", "นอนตะแคง ศอกอยู่ใต้ไหล่ → ยกสะโพกให้ตัวตรงจากศีรษะถึงเข่า (ระดับยาก: ถึงเท้า) → ค้างไว้"], ["Suitcase", "ถือ DB 7.5 ข้างเดียวเหมือนถือกระเป๋า → เดินปกติ ตัวตรง ไหล่เสมอกัน → ครบแล้วเปลี่ยนมือ"], ["Push-up", "มือกว้างกว่าไหล่เล็กน้อย ตัวตรงจากศีรษะถึงส้นเท้า → ลดอกลงจนเกือบแตะพื้น → ดันกลับขึ้น"], ["Single-arm DB Floor", "นอนหงายชันเข่า ถือ DB มือเดียว ต้นแขนวางพื้น → ดันขึ้นตรงเหนืออก → ลดลงจนศอกแตะพื้นเบาๆ · อีกมือวางพื้นช่วยทรงตัว"], ["Pike", "มือและเท้าวางพื้น สะโพกยกสูงเป็นรูปตัว V คว่ำ → งอศอกลดศีรษะลงหาพื้นตรงหน้ามือ → ดันกลับ"], ["Lateral Raise", "ยืนตรง ถือ DB ข้างลำตัว ศอกงอนิด → ยกแขนออกด้านข้างจนระดับไหล่ → ลงช้าๆ · ทำทีละข้างได้"], ["Chair Dip", "นั่งขอบเก้าอี้ที่มั่นคง มือจับขอบข้างสะโพก เลื่อนก้นออกมา เข่างอ → งอศอกลดตัวลงจนศอก 90° → ดันขึ้น · ยากขึ้น: เหยียดขาตรง"], ["Dead Bug", "นอนหงาย แขนชี้เพดาน เข่างอ 90° ลอยอยู่ → เหยียดแขนซ้ายไปเหนือศีรษะพร้อมขาขวาออกไปจนเกือบแตะพื้น → กลับ แล้วสลับข้าง"], ["Plank", "ศอกอยู่ใต้ไหล่ ปลายเท้ายันพื้น ตัวตรงจากศีรษะถึงส้นเท้า (ระดับง่าย: เข่าลง) → บีบก้นและท้อง ค้างไว้"], ["Bird Dog", "คุกเข่าสี่ขา มือใต้ไหล่ เข่าใต้สะโพก → เหยียดแขนซ้ายไปข้างหน้าพร้อมขาขวาไปข้างหลังจนขนานพื้น ค้าง 2 วิ → กลับ แล้วสลับ"], ["Negative", "เหยียบเก้าอี้ขึ้นไปให้คางอยู่เหนือบาร์ มือจับคว่ำกว้างกว่าไหล่ → ยกเท้าออก แล้วลดตัวลงช้า 3-5 วิ จนแขนตึง → เหยียบเก้าอี้ขึ้นใหม่"], ["Chair-assisted", "วางเก้าอี้ใต้บาร์ เท้าแตะเก้าอี้ → ดึงตัวขึ้นจนคางพ้นบาร์ ใช้ขาช่วยเท่าที่จำเป็น → ลงช้าๆ"], ["Single-arm DB Row", "มือกับเข่าข้างหนึ่งวางบนเก้าอี้/เตียง หลังขนานพื้น อีกมือถือ DB ห้อย → ดึงศอกขึ้นไปทางสะโพกจน DB ถึงข้างลำตัว ค้าง 1 วิ → ลงช้าๆ"], ["Reverse Fly", "ยืนก้มตัว ~45° เข่างอนิด ถือ DB ห้อยใต้อก → กางแขนออกด้านข้างจนระดับไหล่ บีบสะบักเข้าหากัน → ลงช้าๆ"], ["DB Curl", "ยืนตรง ถือ DB แขนเหยียด ฝ่ามือหันหน้า → งอศอกยกขึ้นถึงไหล่ → ลงช้าๆ ศอกอยู่กับที่"], ["Dead hang", "จับบาร์คว่ำมือ ห้อยตัวแขนตึง เท้าลอย → ดึงไหล่ลงเล็กน้อย ไม่ห้อยปล่อยสุด → ค้างนานที่สุด"], ["Hanging Knee", "ห้อยบาร์ ตัวนิ่ง → ยกเข่าขึ้นถึงระดับสะโพก → ลงช้าๆ ไม่แกว่ง · แทน (Lying Leg Raise): นอนหงาย มือวางข้างตัว ยกขาตรงขึ้น 90° แล้วลงช้าจนเกือบแตะพื้น"], ["KB Halo", "ยืนหรือคุกเข่า ถือ KB กลับหัวระดับอก → วน KB รอบศีรษะชิดๆ 5 รอบ แล้วกลับทิศ → ลำตัวนิ่ง ไม่แอ่น"], ["Superman", "นอนคว่ำ แขนเหยียดไปข้างหน้า → ยกแขน อก และขาลอยจากพื้นพร้อมกัน ค้าง 2 วิ → ลงช้าๆ"]];
function s2Name(r) {
  const ss = r[3] ? ` <span class="badge" title="superset">${r[3]}</span>` : '';
  const h = S2_HOW.find(([k]) => r[0].startsWith(k));
  return h ? `<details class="s2-how"><summary>${r[0]}${ss} <span style="color:var(--primary);font-size:11px">ℹ️ วิธีทำ</span></summary><div style="font-size:12px;line-height:1.6;margin:4px 0;padding:6px 8px;background:var(--card-bg-alt);border-radius:6px">${h[1]}</div></details>` : r[0] + ss;
}
function s2Gym(s) {
  const n = s.sets, c = s.core, cs = Math.max(2, n - 1);
  const row = r => r.sec
    ? `<tr><td colspan="3" style="padding-top:10px;font-size:12px;color:var(--accent)">${r.sec}</td></tr>`
    : `<tr><td>${s2Name(r)}${r[4] ? `<div class="cue">${r[4]}</div>` : ''}</td><td class="numeric">${r[1]}</td><td class="numeric" style="white-space:nowrap">${r[2]}</td></tr>`;
  const day = (t, rows) => `<h3>${t}</h3><table><thead><tr><th>ท่า</th><th class="numeric">Sets × Reps</th><th class="numeric">พัก</th></tr></thead><tbody>${rows.map(row).join('')}</tbody></table>`;
  const legRows = s.leg ? [
      ['Bulgarian Split Squat (DB 7.5 + KB 6) ลงช้า 3 วิ', `${n} × 10-12 /ขา`, '90-120 วิ', '', '🫁 ลงเข้า · ดันขึ้นออก · เข่าชี้ตามปลายเท้า ลำตัวตรง'],
      ['Single-Leg RDL (DB 7.5)', `${n} × 10 /ขา`, '60-90 วิ', 'SS', '🫁 ก้มเข้า · ยืดขึ้นออก · หลังตรง สะโพกไม่บิด เข่างอนิดๆ'],
      ['Single-Leg Calf Raise (DB 7.5) ลงช้า 3 วิ', `${n} × 12-15 /ขา`, '60-90 วิ', 'SS', '🫁 ขึ้นออก · ลงเข้า · ลงให้ส้นต่ำกว่าขั้น'],
      ['KB Goblet Squat ค้างล่าง 2 วิ', `${n} × 15-20`, '90 วิ', '', '🫁 ลงเข้า · ขึ้นออก · อกตั้ง เข่าไม่หุบ'],
      ...(s.plyo ? [['Pogo hops / Jump squat', `${n} × 10 / ${n} × 5`, '60-90 วิ', '', '🫁 หายใจเป็นจังหวะ ไม่กลั้น · ลงเท้าเบา เข่าไม่หุบ']] : []),
      {sec: '🧱 Core'},
      ['Single-Leg Glute Bridge', `${cs} × 10 /ข้าง`, '30-45 วิ', '', '🫁 ยกขึ้นออก · ลงเข้า · บีบก้น หลังไม่แอ่น'],
      ['Dead Bug (หลังล่างแนบพื้น ซี่โครงลง)', `${cs} × 8 /ข้าง`, '30-45 วิ', '', '🫁 เหยียดแขนขา = หายใจออกยาว ซี่โครงลง · ดึงกลับ = เข้า · หลังล่างแนบพื้นตลอด ถ้าแอ่นให้ลดระยะ'],
      [`Side Plank${c < 35 ? ' (คุกเข่า)' : ''}`, `${cs} × ${c} วิ /ข้าง`, '30-45 วิ', '', '🫁 หายใจสั้นสม่ำเสมอ (นับเลขออกเสียงได้) · สะโพกไม่ตก'],
      ['Suitcase Carry (DB 7.5 ข้างเดียว)', `${cs} × 30 ก้าว /ข้าง`, '30-45 วิ', '', '🫁 หายใจปกติ เกร็งท้องเบาๆ · ตัวตรง ไม่เอียงตามน้ำหนัก']] : null;
  return (legRows ? day('🦵 จันทร์ · Leg', legRows)
      : '<h3>🦵 จันทร์ · Leg</h3><div class="alert-box">สัปดาห์แข่ง งด Leg day</div>') +
    day('💪 อังคาร · Push', [
      ['Push-up (ง่ายไป → ยกเท้า · ยากไป → วางมือบนโต๊ะ)', `${n + 1} × เกือบหมดแรง`, '90-120 วิ', '', '🫁 ลงเข้า · ดันขึ้นออก · ตัวตรงเป็นแผ่นเดียว ศอกกาง ~45°'],
      ['Single-arm DB Floor Press 7.5', `${n} × 15 /ข้าง`, '60-90 วิ', '', '🫁 ลงเข้า · ดันออก · ศอกแตะพื้นเบาๆ'],
      ['Pike Push-up', `${n} × 8-12`, '90 วิ', '', '🫁 ลงเข้า · ดันออก · สะโพกสูง ศีรษะลงหน้ามือ'],
      ['Lateral Raise DB 5', `${n} × 15-20`, '45-60 วิ', 'SS', '🫁 ยกออก · ลงเข้า · ยกแค่ระดับไหล่ ไม่เหวี่ยง'],
      ['Chair Dip', `${n} × 12-15`, '45-60 วิ', 'SS', '🫁 ลงเข้า · ดันออก · ไหล่ไม่ห่อ ลงแค่ศอก 90°'],
      {sec: '🧱 Core'},
      ['Dead Bug (หลังล่างแนบพื้น)', `${cs} × 8 /ข้าง`, '30-45 วิ', '', '🫁 เหยียดแขนขา = หายใจออกยาว · ดึงกลับ = เข้า · หลังล่างแนบพื้นตลอด'],
      [`Plank${c < 35 ? ' (เข่าลงได้)' : ''}`, `${cs} × ${c} วิ`, '30-45 วิ', '', '🫁 หายใจสั้นสม่ำเสมอ · ก้นไม่โด่ง หลังไม่แอ่น'],
      ['Bird Dog ค้าง 2 วิ', `${cs} × 8 /ข้าง`, '30-45 วิ', '', '🫁 เหยียดออก · กลับเข้า · สะโพกไม่บิด']]) +
    day('🧗 พุธ · Pull', [
      ['Negative pull-up ลงช้า 3-5 วิ', `${n} × 3-5`, '2 นาที', '', '🫁 เข้าก่อนลง · ปล่อยออกช้าๆ ระหว่างลง · ห้ามปล่อยตัวกระแทก'],
      ['Chair-assisted pull-up', `${n} × 6-8`, '90-120 วิ', '', '🫁 ดึงขึ้นออก · ลงเข้า · ใช้ขาช่วยให้น้อยที่สุด'],
      ['Single-arm DB Row 7.5 ค้างบน 1 วิ', `${n} × 15 /ข้าง`, '60-90 วิ', '', '🫁 ดึงออก · ลงเข้า · ดึงศอกไปทางสะโพก หลังตรง'],
      ['Reverse Fly DB 5', `${n} × 15-20`, '45-60 วิ', 'SS', '🫁 กางออก · ลงเข้า · บีบสะบัก ไม่เหวี่ยง'],
      ['DB Curl 7.5', `${n} × 12-15`, '45-60 วิ', 'SS', '🫁 ยกออก · ลงเข้า · ศอกนิ่งข้างลำตัว'],
      ['Dead hang', '2 × นานสุด', '60 วิ', '', '🫁 หายใจปกติ · ไหล่ไม่ยกชิดหู'],
      {sec: '🧱 Core'},
      ['Hanging Knee Raise (ห้อยไม่ไหว → Lying Leg Raise)', `${cs} × 6-10`, '30-45 วิ', '', '🫁 ยกออก · ลงเข้า · ไม่แกว่งตัว'],
      ['KB Halo (KB 6)', `${cs} × 5 รอบ /ทิศ`, '30-45 วิ', '', '🫁 หายใจปกติ · ลำตัวนิ่ง หมุนแค่แขน'],
      ['Superman ค้าง 2 วิ', `${cs} × 10`, '30-45 วิ', '', '🫁 ยกออก · ลงเข้า · มองพื้น คอไม่เงย']]) +
    `<div style="font-size:12px;color:var(--text-muted);margin-top:6px;line-height:1.6">
      <span class="badge">SS</span> = superset ทำ 2 ท่านี้ต่อกันแล้วค่อยพัก (ประหยัดเวลา) · ท่าข้างเดียว: ซ้ายเสร็จเปลี่ยนขวาทันที พักหลังครบสองข้าง<br>
      ทำครบสบาย → เพิ่ม reps หรือลงช้าลง · เซ็ตถัดไป reps ตก &gt;2-3 = พักน้อยไป เพิ่ม 30 วิ · Plank/Side Plank เพิ่มเวลาอัตโนมัติทุก 2 สัปดาห์ (ตอนนี้ ${c} วิ)<br>
      🫁 หลักทั่วไป: ออกแรง = หายใจออก · คืนท่า = เข้า · ห้ามกลั้นหลาย reps · ก่อนแต่ละ rep หายใจเข้าให้ท้องขยาย แล้วเกร็งท้อง ~30-50%<br>3 × 12 = 3 เซ็ต เซ็ตละ 12 ครั้ง · /ขา /ข้าง = ต่อข้าง · เกือบหมดแรง = หยุดตอนเหลือแรงอีก 1-3 ครั้ง · ท่าเสีย = จบเซ็ต · เจ็บแปลบที่ข้อ = หยุดท่านั้น (เมื่อย 1-2 วัน = ปกติ)<br>ดึง pull-up ได้แล้ว → เปลี่ยน Negative เป็น pull-up จริง</div>`;
}


function s2CoreSec() {
  const [y, m, d] = String(sub2.start || SUB2_DEF.start).split('-').map(Number);
  const wk = Math.floor((Date.now() - new Date(y, m - 1, d).getTime()) / 864e5 / 7);
  return s2Clamp(20 + 5 * Math.floor(Math.max(0, wk) / 2), 20, 60);
}

function s2Fill() {
  const v = (id, x) => { const el = $('#' + id); if (el) el.value = x; };
  v('s2-btype', sub2.bench.type); v('s2-btime', sub2.bench.time); v('s2-km', sub2.weekly_km); v('s2-heat', sub2.heat);
  s2TokenState();
}

function s2Input() {
  const g = id => $('#' + id).value;
  sub2.bench = {type: g('s2-btype'), time: g('s2-btime').trim()};
  sub2.weekly_km = s2Clamp(+g('s2-km') || 30, 5, 200);
  sub2.heat = g('s2-heat');
  sub2Dirty = true;
  s2Status('มีการแก้ไข ยังไม่ได้ Save', 'warn');
  renderSub2Out();
}

function renderSub2Out() {
  const Z = s2Zones(sub2), km = +sub2.weekly_km || 30, P = k => Z ? s2Fmt(Z[k]) : '—';
  const E = Z ? `${s2Fmt(Z.E[0])}-${s2Fmt(Z.E[1])}` : '—';
  // --- maintenance week ---
  $('#s2-week').innerHTML = `<table><tbody>
      <tr><td style="white-space:nowrap">จ. อ. พ.</td><td>🏋️ Leg · Push · Pull (ตารางด้านล่าง)</td></tr>
      <tr><td>พฤ.</td><td>พัก</td></tr>
      <tr><td>ศ.</td><td><strong>Speedwork 1 ครั้ง</strong> เลือกจากเมนูด้านล่าง หมุนตามรอบ 4 สัปดาห์
        <div class="cue">warm-up 15 นาที + strides 4 × 20 วิ · cool-down 10 นาที · 🫁 ช่วงเร็ว 2:2</div></td></tr>
      <tr><td>ส.</td><td>Easy 40-50 นาที @${E}/km (HR ≤150) + 3-Minute Routine
        <div class="cue">🫁 หายใจ 3:3 พูดเป็นประโยคได้ · เกร็ง → หายใจออกยาว ปล่อยไหล่ คลายมือ</div></td></tr>
      <tr><td>อา.</td><td><strong>Long 12-16 km</strong> easy @${E}/km · บางสัปดาห์จบด้วย 3-4 km @${P('HM')}/km
        <div class="cue">ยาว ≥12 km ทุกสัปดาห์ = รักษาฟิต Half ไว้ได้ · 🫁 easy 3:3 · จุกเสียด → ชะลอ หายใจออกแรงยาว</div></td></tr>
    </tbody></table>
    <table style="margin-top:8px"><thead><tr><th>รอบ 4 สัปดาห์</th><th>ศ. Speedwork</th><th>อา. Long</th></tr></thead><tbody>
      <tr><td>สัปดาห์ 1</td><td>Threshold (T)</td><td>14 km easy</td></tr>
      <tr><td>สัปดาห์ 2</td><td>Interval (I)</td><td>14-16 km · 3 km ท้าย @HM</td></tr>
      <tr><td>สัปดาห์ 3</td><td>Threshold (T) หรือ HM pace</td><td>16 km easy</td></tr>
      <tr><td>สัปดาห์ 4 (เบา)</td><td>Fartlek หรือ 200s (R)</td><td>12 km easy</td></tr>
    </tbody></table>
    <div style="font-size:12px;color:var(--text-muted);margin-top:6px">เป้าคือรักษามาตรฐาน: ระยะรวม ~${km} km/สัปดาห์ · speedwork สัปดาห์ละครั้งเดียว · ทุก 4-6 สัปดาห์หรือหลังแข่ง อัปเดตผลล่าสุดให้เพซขยับตาม</div>`;
  $('#s2-gym').innerHTML = s2Gym({sets: 3, plyo: true, leg: true, core: s2CoreSec()});
  // --- calculator output ---
  if (!Z) { $('#s2-calc').innerHTML = '<div class="alert-box danger">ใส่เวลาผลล่าสุดให้ถูกรูปแบบ เช่น 2:23:36 หรือ 55:30</div>'; return; }
  const zr = (k, name, pace, hr, use) => `<tr><td><strong>${k}</strong> ${name}<div class="cue">${use}</div></td><td class="numeric" style="white-space:nowrap">${pace}</td><td class="numeric" style="white-space:nowrap">${hr}</td></tr>`;
  const rep = (sec, m) => s2Fmt(sec * m / 1000);
  const capT = Math.max(3, km * 0.10), capI = Math.min(10, Math.max(2.4, km * 0.08)), capR = Math.min(8, Math.max(1.6, km * 0.05));
  const ses = (title, what, total, note) => `<tr><td><strong>${title}</strong>${note ? `<div class="cue">${note}</div>` : ''}</td><td>${what}</td><td class="numeric" style="white-space:nowrap">${total}</td></tr>`;
  $('#s2-calc').innerHTML = `
    <div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><span style="font-size:22px;font-weight:700">VDOT ${Z.vd.toFixed(1)}</span>
      <span style="font-size:12px;color:var(--text-muted)">${(S2_HEAT[sub2.heat] || S2_HEAT.cool)[1]} · คาดการณ์ 5K ${s2FmtH(Z.pred['5K'])} · 10K ${s2FmtH(Z.pred['10K'])} · Half ${s2FmtH(Z.pred.Half)}</span></div>
    <h3>เพซแต่ละโซน (/km)</h3>
    <table><thead><tr><th>โซน</th><th class="numeric">Pace</th><th class="numeric">HR</th></tr></thead><tbody>
      ${zr('E', 'Easy / Long', E, '≤150', 'ฐานแอโรบิก · พูดเป็นประโยคได้ · ช้ากว่านี้ได้ ไม่ผิด')}
      ${zr('HM', 'Half pace', P('HM'), '160-166', 'ท้าย long run · ซ้อมความรู้สึกเพซแข่ง')}
      ${zr('T', 'Threshold', P('T'), '165-172', 'หนักแต่คุมได้ · พูดได้ 2-3 คำ')}
      ${zr('I', 'Interval', P('I'), '175+ ท้าย rep', 'VO₂max · หายใจแรง · rep ละ 2-5 นาที')}
      ${zr('R', 'Repetition', P('R'), 'ไม่ต้องดู', 'ความเร็ว + ฟอร์ม · สั้น 200-400 m พักให้หายเหนื่อย')}
    </tbody></table>
    <h3>เวลาต่อ rep</h3>
    <table><thead><tr><th>ระยะ</th><th class="numeric">T</th><th class="numeric">I</th><th class="numeric">R</th></tr></thead><tbody>
      ${[200, 400, 800, 1000, 1600].map(m => `<tr><td>${m} m</td><td class="numeric">${m >= 400 ? rep(Z.T, m) : '—'}</td><td class="numeric">${m >= 400 ? rep(Z.I, m) : '—'}</td><td class="numeric">${m <= 800 ? rep(Z.R, m) : '—'}</td></tr>`).join('')}
    </tbody></table>
    <h3>เมนู Speedwork (วันศุกร์)</h3>
    <table><thead><tr><th>แบบ</th><th>ทำยังไง</th><th class="numeric">รวม</th></tr></thead><tbody>
      ${ses('T · Cruise', `4-5 × 1 km @${P('T')} (${rep(Z.T, 1000)}) · jog 1 นาที`, '4-5 km', 'เริ่มง่ายสุด ใช้เป็นตัวหลัก')}
      ${ses('T · Tempo', `20 นาทีต่อเนื่อง @${P('T')}`, '~3 km', 'หลังทำ cruise ได้สบายแล้ว')}
      ${ses('T · 2 × 10 นาที', `2 × 10 นาที @${P('T')} · jog 2 นาที`, '~3 km', '')}
      ${ses('I · 800s', `5-6 × 800 m @${P('I')} (${rep(Z.I, 800)}) · jog เท่าเวลาวิ่ง`, '4-5 km', 'rep สุดท้ายต้องเร็วเท่า rep แรก ตก = หยุด')}
      ${ses('I · 1 km', `4-5 × 1 km @${P('I')} (${rep(Z.I, 1000)}) · jog 2-3 นาที`, '4-5 km', '')}
      ${ses('Fartlek', `8-10 × 1 นาทีเร็ว (~${P('I')}) · jog 1-2 นาที`, '~2 km เร็ว', 'สัปดาห์เบา · ไม่ต้องจ้องนาฬิกา')}
      ${ses('R · 200s', `8-10 × 200 m @${P('R')} (${rep(Z.R, 200)}) · เดิน/jog 200 m`, '1.6-2 km', 'เน้นฟอร์ม ผ่อนไหล่ ก้าวไว')}
      ${ses('HM pace', `3 × 3 km @${P('HM')} · jog 3 นาที`, '9 km', 'ช่วง 4-6 สัปดาห์ก่อนแข่ง Half')}
    </tbody></table>
    <div class="alert-box" style="margin-top:8px;font-size:12px">ลิมิตต่อครั้ง (${km} km/สัปดาห์): T ≤ ~${capT.toFixed(1)} km · I ≤ ~${capI.toFixed(1)} km · R ≤ ~${capR.toFixed(1)} km — เกินนี้ล้า/เสี่ยงเจ็บมากกว่าได้ผล (กฎ Daniels: T 10% · I 8% · R 5% ของระยะต่อสัปดาห์ ปัดขั้นต่ำให้ทำเซตพื้นฐานได้)</div>
    <details style="margin-top:8px"><summary style="cursor:pointer;font-weight:600">📘 วิธีคำนวณ + กฎการซ้อม speedwork</summary>
      <div style="font-size:13px;line-height:1.7;margin-top:6px">
        • <strong>VDOT</strong> = ค่าความฟิตที่คำนวณจากผลแข่ง/time trial (สูตร Daniels &amp; Gilbert) แล้วแปลงเป็นเพซแต่ละโซน · ใช้ผล<strong>เต็มแรงจริง</strong> ไม่ใช่ช่วงเร็วในวิ่งยาว<br>
        • <strong>ร้อน = ช้าลง:</strong> เลือก "อากาศ" แล้วเพซปรับให้ · วันร้อนจัดให้ยึดความรู้สึก/HR แทนเพซ<br>
        • <strong>เพซเป็นเพดาน ไม่ใช่เป้าให้เกิน:</strong> เร็วกว่าที่ตารางบอก = ได้ผลไม่เพิ่ม แต่ล้ามากขึ้น<br>
        • <strong>พักระหว่าง rep:</strong> T สั้น (jog 1 นาที) · I jog ≈ เวลาวิ่ง · R พักจนหายเหนื่อย<br>
        • <strong>ไม่ไหวกลางทาง:</strong> rep ช้าลงเกิน ~5 วิ/km 2 rep ติด = จบเซต วันนี้พอแล้ว<br>
        • <strong>Speedwork สัปดาห์ละครั้ง</strong> ที่เหลือ easy · ไม่ทำวันถัดจากวันเวทขาหนัก<br>
        • <strong>อัปเดตเพซ</strong> ทุก 4-6 สัปดาห์: วิ่ง time trial 5K หรือ 10K เต็มแรง → ใส่ผลด้านบน → Save<br>
        • <strong>Treadmill:</strong> ตั้งความชัน 1% ให้ใกล้วิ่งข้างนอก
      </div>
    </details>`;
}

function renderSub2() {
  if (!$('#page-sub2')) return;
  if (!sub2) sub2 = s2Norm(DATA.sub2_settings);
  s2Fill();
  renderSub2Out();
}

function s2Token() { try { return localStorage.getItem(SUB2_TOKEN_KEY) || ''; } catch (e) { return ''; } }
function s2TokenState() {
  const el = $('#s2-token-state'); if (!el) return;
  el.innerHTML = s2Token() ? '✅ เครื่องนี้ตั้ง token แล้ว กด Save ได้' : '⚠️ เครื่องนี้ยังไม่มี token (ดูค่าได้ แต่ Save ไม่ได้)';
}
function s2SetToken() {
  const v = $('#s2-token').value.trim();
  if (!v) return;
  try { localStorage.setItem(SUB2_TOKEN_KEY, v); } catch (e) { s2Status('เครื่องนี้เก็บ token ไม่ได้', 'err'); return; }
  $('#s2-token').value = '';
  s2TokenState(); s2Status('เก็บ token แล้ว');
}
function s2ClearToken() {
  try { localStorage.removeItem(SUB2_TOKEN_KEY); } catch (e) {}
  s2TokenState(); s2Status('ลบ token ออกจากเครื่องนี้แล้ว');
}
function s2Status(t, kind) {
  const el = $('#s2-status'); if (!el) return;
  el.textContent = t;
  el.style.color = kind === 'err' ? 'var(--danger)' : kind === 'warn' ? 'var(--warning)' : 'var(--text-muted)';
}
function s2B64(s) { return btoa(unescape(encodeURIComponent(s))); }
function s2Unb64(s) { return decodeURIComponent(escape(atob(String(s).replace(/\s/g, '')))); }
function s2Api() { return `https://api.github.com/repos/${SUB2_REPO}/contents/${SUB2_FILE}`; }
function s2Headers() {
  const h = {Accept: 'application/vnd.github+json'}, t = s2Token();
  if (t) h.Authorization = 'Bearer ' + t;
  return h;
}
async function s2Fetch(shaOnly) {
  try {
    const res = await fetch(s2Api() + '?ref=main', {headers: s2Headers(), cache: 'no-store'});
    if (!res.ok) return res.status === 404 ? 'missing' : false;
    const j = await res.json();
    sub2Sha = j.sha;
    if (shaOnly) return true;
    const remote = s2Norm(JSON.parse(s2Unb64(j.content)));
    if (!sub2Dirty) { sub2 = remote; s2Fill(); renderSub2Out(); }
    return true;
  } catch (e) { return false; }
}
async function s2Reload() {
  if (sub2Dirty && !confirm('ทิ้งค่าที่แก้ยังไม่ได้ Save แล้วโหลดจาก GitHub?')) return;
  sub2Dirty = false;
  s2Status('กำลังโหลด…');
  const ok = await s2Fetch(false);
  s2Status(ok === true ? 'โหลดค่าล่าสุดจาก GitHub แล้ว' : 'โหลดจาก GitHub ไม่ได้ ใช้ค่าที่ฝังในเว็บ', ok === true ? '' : 'warn');
}
async function s2Save() {
  const tok = s2Token();
  if (!tok) { s2Status('เครื่องนี้ยังไม่มี token → เปิด 🔑 ด้านล่าง', 'warn'); return; }
  sub2.updated = new Date().toISOString();
  const content = s2B64(JSON.stringify(sub2, null, 1) + '\n');
  s2Status('กำลังบันทึก…');
  for (let attempt = 0; attempt < 2; attempt++) {
    if (!sub2Sha) await s2Fetch(true);
    let res;
    try {
      res = await fetch(s2Api(), {method: 'PUT', headers: s2Headers(), body: JSON.stringify(
        Object.assign({message: 'Update Sub-2 plan settings from dashboard', content, branch: 'main'}, sub2Sha ? {sha: sub2Sha} : {}))});
    } catch (e) { s2Status('บันทึกไม่ได้ (เน็ต?)', 'err'); return; }
    if (res.ok) {
      const j = await res.json(); sub2Sha = j.content && j.content.sha; sub2Dirty = false;
      const d = new Date(); s2Status(`บันทึกแล้ว ✅ ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')} · เครื่องอื่นกด ⟳ หรือเปิดใหม่`);
      return;
    }
    if (res.status === 409 || res.status === 422) { sub2Sha = null; continue; }
    s2Status(`บันทึกไม่สำเร็จ (${res.status}) ` + (res.status === 401 ? 'token ใช้ไม่ได้/หมดอายุ' :
      (res.status === 403 || res.status === 404) ? 'token ไม่มีสิทธิ์เขียน repo นี้' : ''), 'err');
    return;
  }
  s2Status('บันทึกไม่สำเร็จ (ไฟล์ชนกัน) ลองกด Save อีกครั้ง', 'err');
}


renderSub2();
s2Fetch(false);
