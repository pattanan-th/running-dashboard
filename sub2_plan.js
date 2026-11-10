// ===== SUB-2 LONG-TERM PLAN =====
// Settings live in plan_settings.json in the GitHub repo so phone and PC share them.
// The Save button writes that file through the GitHub contents API with a
// fine-grained token kept only in this device's localStorage.
const SUB2_REPO = 'pattanan-th/running-dashboard', SUB2_FILE = 'plan_settings.json', SUB2_TOKEN_KEY = 'sub2_gh_token';
const SUB2_DEF = {start: '2026-11-23', race_date: '', weeks: 52, intensity: 'normal',
                  bench: {type: 'hm', time: '2:23:36'}, feedback: {}, updated: ''};
const S2_DIST = {'5k': 5, '10k': 10, hm: 21.0975};
const S2_GOAL_HM = 2 * 3600;
const S2_MON = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const S2_PH = {base: ['Base', 'green'], speed: ['Speed', 'yellow'], spec: ['Race-specific', 'red'], taper: ['Taper', '']};
let sub2 = null, sub2Sha = null, sub2Dirty = false;

function s2Norm(s) {
  s = Object.assign({}, SUB2_DEF, s || {});
  s.bench = Object.assign({}, SUB2_DEF.bench, s.bench || {});
  s.feedback = Object.assign({}, s.feedback || {});
  return s;
}
function s2Date(s) { const [y, m, d] = String(s).split('-').map(Number); return new Date(y, m - 1, d); }
function s2Iso(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
function s2Add(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function s2Th(d) { return d.getDate() + ' ' + S2_MON[d.getMonth()]; }
const s2Clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const s2Fmt = s => { s = Math.round(s); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const s2FmtH = s => { s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };
const s2Esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

// Paces (s/km) from the latest result, Riegel exponent 1.06.
function s2Paces(st) {
  const km = S2_DIST[st.bench.type] || S2_DIST.hm;
  const parts = String(st.bench.time || '').trim().split(':').map(Number);
  if (!parts.length || parts.some(x => isNaN(x))) return null;
  let sec = parts.reduce((a, b) => a * 60 + b, 0);
  if (parts.length === 2 && km > 15 && parts[0] < 6) sec *= 60;  // "2:23" on a half = h:mm
  if (!(sec > 0)) return null;
  const at = d => sec * Math.pow(d / km, 1.06) / d;
  const hm = at(S2_DIST.hm), tenk = at(10), fivek = at(5);
  return {hm, tenk, fivek, thr: (hm + tenk) / 2, ezLo: hm + 60, ezHi: hm + 90, hmT: hm * S2_DIST.hm, tenkT: tenk * 10, fivekT: fivek * 5};
}

function s2Weeks(st) {
  const start = s2Date(st.start);
  let N = st.race_date ? Math.floor((s2Date(st.race_date) - start) / 864e5 / 7) + 1 : +st.weeks || 52;
  N = s2Clamp(N, 8, 104);
  const taper = 2, spec = s2Clamp(Math.round(N * 0.3), 4, 10);
  const rest = N - taper - spec, base = Math.ceil(rest / 2), speed = rest - base;
  const lv = {easy: -1, normal: 0, hard: 1}[st.intensity] || 0;
  const out = [];
  let i = 0, fb = 0;
  for (const [ph, len] of [['base', base], ['speed', speed], ['spec', spec], ['taper', taper]]) {
    for (let j = 0; j < len; j++, i++) {
      const ws = s2Add(start, 7 * i), key = s2Iso(ws);
      out.push({i, N, ph, j, len, p: len > 1 ? j / (len - 1) : 1, key, ws,
                down: (ph === 'base' || ph === 'speed') && j % 4 === 3 && j < len - 1,
                test: (ph === 'base' || ph === 'speed') && j === len - 1,
                last: i === N - 1, L: s2Clamp(lv + fb, -2, 2), fb: st.feedback[key] || 0});
      fb = s2Clamp(fb + (st.feedback[key] || 0), -3, 3);  // a week's feedback shifts the weeks after it
    }
  }
  return out;
}

function s2Sessions(w, P, st) {
  const r = Math.round, pc = k => P ? s2Fmt(P[k]) : '—';
  const {ph, p, down, L} = w;
  let fri, sun, satMin = 45, sets = w.i < 2 ? 2 : 3, plyo = w.i >= 2, leg = true;
  if (ph === 'base') {
    const reps = s2Clamp(r(6 + 4 * p) + L - (down ? 2 : 0), 4, 12);
    fri = `Fartlek ${reps} × (1 นาทีเร็ว @${pc('tenk')}/km + jog 2 นาที) + strides 4-6 × 20 วินาที`;
    let km = s2Clamp(r(12 + 6 * p) + L, 10, 20); if (down) km = r(km * 0.75);
    sun = `Long ${km} km easy (HR ≤150)`;
    satMin = 40 + r(15 * p);
  } else if (ph === 'speed') {
    const len = p < 0.34 ? 6 : p < 0.67 ? 8 : 10;
    const total = s2Clamp(18 + 12 * p + 4 * L - (down ? 8 : 0), 12, 36);
    fri = `Threshold ${Math.max(2, r(total / len))} × ${len} นาที @${pc('thr')}/km · jog 2 นาที`;
    let km = s2Clamp(r(16 + 3 * p) + L, 12, 21); if (down) km = r(km * 0.75);
    const steady = down ? 0 : s2Clamp(r(3 + 3 * p) + L, 2, 7);
    sun = `Long ${km} km` + (steady ? ` · กลางทาง ${steady} km steady @${pc('hm')}/km` : ' easy');
    satMin = 50;
  } else if (ph === 'spec') {
    const total = s2Clamp(r(5 + 4 * p) + L, 3, 10), rep = Math.max(1, r(total / 3 * 2) / 2);
    fri = `Race pace 3 × ${rep} km @${pc('hm')}/km (เป้า 5:41) · jog 3 นาที`;
    const km = s2Clamp(r(17 + 4 * p) + L, 14, 22), fast = s2Clamp(r(2 + 3 * p) + L, 1, 6);
    sun = `Long ${km} km · ${fast} km สุดท้าย @${pc('hm')}/km`;
    satMin = 50; sets = 2;
  } else if (!w.last) {
    fri = `Race pace 2 × 2 km @${pc('hm')}/km · jog 3 นาที`;
    sun = `Long 14 km easy · 2 km สุดท้าย @${pc('hm')}/km`;
    satMin = 40; sets = 2; plyo = false;
  } else {
    fri = 'Shakeout 20 นาที + strides 4 × 20 วินาที';
    sun = st.race_date ? '🏁 RACE DAY' : '🏁 HM Time Trial → ใส่ผลในช่อง "ผลล่าสุด"';
    satMin = 25; sets = 2; plyo = false; leg = false;
  }
  if (w.test) fri = '🧪 Time trial 10K (หรือ 5K) → ใส่ผลในช่อง "ผลล่าสุด" แล้ว Save';
  const satLo = Math.max(20, satMin + 5 * L);
  const sat = `Easy ${satLo}-${satLo + 10} นาที (HR ≤150${P ? ` · ~${s2Fmt(P.ezLo)}-${s2Fmt(P.ezHi)}/km` : ''}) + 3-Minute Routine`;
  const core = s2Clamp(20 + 5 * Math.floor(w.i / 2), 20, 60);
  return {fri, sat, sun, sets, plyo, leg, core};
}

function s2Gym(s) {
  const n = s.sets, c = s.core, cs = Math.max(2, n - 1);
  const row = r => r.sec
    ? `<tr><td colspan="3" style="padding-top:10px;font-size:12px;color:var(--accent)">${r.sec}</td></tr>`
    : `<tr><td>${r[0]}${r[3] ? ` <span class="badge" title="superset">${r[3]}</span>` : ''}</td><td class="numeric">${r[1]}</td><td class="numeric" style="white-space:nowrap">${r[2]}</td></tr>`;
  const day = (t, rows) => `<h3>${t}</h3><table><thead><tr><th>ท่า</th><th class="numeric">Sets × Reps</th><th class="numeric">พัก</th></tr></thead><tbody>${rows.map(row).join('')}</tbody></table>`;
  const legRows = s.leg ? [
      ['Bulgarian Split Squat (DB 7.5 + KB 6) ลงช้า 3 วิ', `${n} × 10-12 /ขา`, '90-120 วิ'],
      ['Single-Leg RDL (DB 7.5)', `${n} × 10 /ขา`, '60-90 วิ', 'SS'],
      ['Single-Leg Calf Raise (DB 7.5) ลงช้า 3 วิ', `${n} × 12-15 /ขา`, '60-90 วิ', 'SS'],
      ['KB Goblet Squat ค้างล่าง 2 วิ', `${n} × 15-20`, '90 วิ'],
      ...(s.plyo ? [['Pogo hops / Jump squat', `${n} × 10 / ${n} × 5`, '60-90 วิ']] : []),
      {sec: '🧱 Core'},
      ['Single-Leg Glute Bridge', `${cs} × 10 /ข้าง`, '30-45 วิ'],
      [`Side Plank${c < 35 ? ' (คุกเข่า)' : ''}`, `${cs} × ${c} วิ /ข้าง`, '30-45 วิ'],
      ['Suitcase Carry (DB 7.5 ข้างเดียว)', `${cs} × 30 ก้าว /ข้าง`, '30-45 วิ']] : null;
  return (legRows ? day('🦵 จันทร์ · Leg', legRows)
      : '<h3>🦵 จันทร์ · Leg</h3><div class="alert-box">สัปดาห์แข่ง งด Leg day</div>') +
    day('💪 อังคาร · Push', [
      ['Push-up (ง่ายไป → ยกเท้า · ยากไป → วางมือบนโต๊ะ)', `${n + 1} × เกือบหมดแรง`, '90-120 วิ'],
      ['Single-arm DB Floor Press 7.5', `${n} × 15 /ข้าง`, '60-90 วิ'],
      ['Pike Push-up', `${n} × 8-12`, '90 วิ'],
      ['Lateral Raise DB 5', `${n} × 15-20`, '45-60 วิ', 'SS'],
      ['Chair Dip', `${n} × 12-15`, '45-60 วิ', 'SS'],
      {sec: '🧱 Core'},
      ['Dead Bug (หลังล่างแนบพื้น)', `${cs} × 8 /ข้าง`, '30-45 วิ'],
      [`Plank${c < 35 ? ' (เข่าลงได้)' : ''}`, `${cs} × ${c} วิ`, '30-45 วิ'],
      ['Bird Dog ค้าง 2 วิ', `${cs} × 8 /ข้าง`, '30-45 วิ']]) +
    day('🧗 พุธ · Pull', [
      ['Negative pull-up ลงช้า 3-5 วิ', `${n} × 3-5`, '2 นาที'],
      ['Chair-assisted pull-up', `${n} × 6-8`, '90-120 วิ'],
      ['Single-arm DB Row 7.5 ค้างบน 1 วิ', `${n} × 15 /ข้าง`, '60-90 วิ'],
      ['Reverse Fly DB 5', `${n} × 15-20`, '45-60 วิ', 'SS'],
      ['DB Curl 7.5', `${n} × 12-15`, '45-60 วิ', 'SS'],
      ['Dead hang', '2 × นานสุด', '60 วิ'],
      {sec: '🧱 Core'},
      ['Hanging Knee Raise (ห้อยไม่ไหว → Lying Leg Raise)', `${cs} × 6-10`, '30-45 วิ'],
      ['KB Halo (KB 6)', `${cs} × 5 รอบ /ทิศ`, '30-45 วิ'],
      ['Superman ค้าง 2 วิ', `${cs} × 10`, '30-45 วิ']]) +
    `<div style="font-size:12px;color:var(--text-muted);margin-top:6px;line-height:1.6">
      <span class="badge">SS</span> = superset ทำ 2 ท่านี้ต่อกันแล้วค่อยพัก (ประหยัดเวลา) · ท่าข้างเดียว: ซ้ายเสร็จเปลี่ยนขวาทันที พักหลังครบสองข้าง<br>
      ทำครบสบาย → เพิ่ม reps หรือลงช้าลง · เซ็ตถัดไป reps ตก &gt;2-3 = พักน้อยไป เพิ่ม 30 วิ · Plank/Side Plank เพิ่มเวลาอัตโนมัติทุก 2 สัปดาห์ (ตอนนี้ ${c} วิ)<br>
      ดึง pull-up ได้แล้ว → เปลี่ยน Negative เป็น pull-up จริง · วิธีหายใจและคำศัพท์ → การ์ด 📘 ด้านล่าง</div>`;
}

function s2CurIdx(weeks) {
  const t = new Date(); t.setHours(0, 0, 0, 0);
  return Math.floor((t - weeks[0].ws) / 864e5 / 7);
}

function s2Fill() {
  const v = (id, x) => { const el = $('#' + id); if (el) el.value = x; };
  v('s2-start', sub2.start); v('s2-race', sub2.race_date || ''); v('s2-weeks', sub2.weeks);
  v('s2-int', sub2.intensity); v('s2-btype', sub2.bench.type); v('s2-btime', sub2.bench.time);
  const w = $('#s2-weeks'); if (w) w.disabled = !!sub2.race_date;
  s2TokenState();
}

function s2Input() {
  const g = id => $('#' + id).value;
  sub2.start = g('s2-start') || SUB2_DEF.start;
  sub2.race_date = g('s2-race') || '';
  sub2.weeks = s2Clamp(+g('s2-weeks') || 52, 8, 104);
  sub2.intensity = g('s2-int');
  sub2.bench = {type: g('s2-btype'), time: g('s2-btime').trim()};
  sub2Dirty = true;
  $('#s2-weeks').disabled = !!sub2.race_date;
  s2Status('มีการแก้ไข ยังไม่ได้ Save', 'warn');
  renderSub2Out();
}

function s2Feedback(key, v) {
  if (sub2.feedback[key] === v) delete sub2.feedback[key]; else sub2.feedback[key] = v;
  sub2Dirty = true;
  renderSub2Out();
  if (s2Token()) s2Save(); else s2Status('มีการแก้ไข ยังไม่ได้ Save', 'warn');
}

function renderSub2Out() {
  const P = s2Paces(sub2), weeks = s2Weeks(sub2), ci = s2CurIdx(weeks);
  // paces line
  $('#s2-paces').innerHTML = P
    ? `เพซจากผลล่าสุด: Fartlek ${s2Fmt(P.tenk)} · Threshold ${s2Fmt(P.thr)} · HM pace ${s2Fmt(P.hm)} · Easy ~${s2Fmt(P.ezLo)}-${s2Fmt(P.ezHi)} /km (ยึด HR ≤150 เป็นหลัก)`
    : '<span style="color:var(--danger)">ใส่เวลาผลล่าสุดให้ถูกรูปแบบ เช่น 2:23:36 หรือ 55:30</span>';
  // this week
  let wk = '';
  if (ci < 0) {
    wk = `<div class="alert-box success"><strong>Recovery</strong> ก่อนเริ่มแผน ${s2Th(weeks[0].ws)}<br>easy run สั้นๆ ตามสบาย + 3-Minute Routine · เวทเบา 2 sets ลองท่า ไม่ทำ plyo</div>`;
  } else if (ci >= weeks.length) {
    wk = `<div class="alert-box success">แผนจบแล้ว 🎉 ตั้งวันเริ่มรอบใหม่ด้านล่าง</div>`;
  } else {
    const w = weeks[ci], s = s2Sessions(w, P, sub2), [pn, pc] = S2_PH[w.ph];
    const fbBtn = (v, t) => `<button class="btn${w.fb === v ? ' primary' : ''}" onclick="s2Feedback('${w.key}',${v})">${t}</button>`;
    wk = `<div style="margin-bottom:8px"><span class="badge ${pc}">${pn}</span> สัปดาห์ ${w.i + 1}/${w.N} · ${s2Th(w.ws)} - ${s2Th(s2Add(w.ws, 6))}${w.down ? ' · <span class="badge">down week</span>' : ''}${w.L ? ` · ระดับ ${w.L > 0 ? '+' : ''}${w.L}` : ''}</div>
      <table><tbody>
        <tr><td>จ.</td><td>${s.leg ? '🦵 Leg' : 'พัก'}</td></tr>
        <tr><td>อ.</td><td>💪 Push</td></tr>
        <tr><td>พ.</td><td>🧗 Pull</td></tr>
        <tr><td>พฤ.</td><td>พัก</td></tr>
        <tr><td>ศ.</td><td><strong>${s.fri}</strong><div class="cue">warm-up 10-15 นาที · cool-down 10 นาที</div></td></tr>
        <tr><td>ส.</td><td>${s.sat}</td></tr>
        <tr><td>อา.</td><td><strong>${s.sun}</strong></td></tr>
      </tbody></table>
      <div style="margin-top:10px;font-size:12px;color:var(--text-muted)">จบสัปดาห์แล้วรู้สึกยังไง (ปรับสัปดาห์ถัดไป)</div>
      <div style="display:flex;gap:6px;margin-top:4px;flex-wrap:wrap">${fbBtn(1, '😌 ง่ายไป')}${fbBtn(0, '👍 พอดี')}${fbBtn(-1, '🥵 หนักไป')}</div>`;
  }
  $('#s2-week').innerHTML = wk;
  const gw = weeks[s2Clamp(ci, 0, weeks.length - 1)];
  $('#s2-gym').innerHTML = s2Gym(s2Sessions(gw, P, sub2));
  // milestones
  const goal10 = S2_GOAL_HM * Math.pow(10 / S2_DIST.hm, 1.06), goal5 = S2_GOAL_HM * Math.pow(5 / S2_DIST.hm, 1.06);
  $('#s2-miles').innerHTML = `<table><thead><tr><th></th><th class="numeric">ตอนนี้ (เทียบเท่า)</th><th class="numeric">เป้า sub-2</th></tr></thead><tbody>
      <tr><td>Half</td><td class="numeric">${P ? s2FmtH(P.hmT) : '—'}</td><td class="numeric">1:59:59</td></tr>
      <tr><td>10K</td><td class="numeric">${P ? s2FmtH(P.tenkT) : '—'}</td><td class="numeric">${s2FmtH(goal10)}</td></tr>
      <tr><td>5K</td><td class="numeric">${P ? s2FmtH(P.fivekT) : '—'}</td><td class="numeric">${s2FmtH(goal5)}</td></tr>
    </tbody></table>
    <div style="font-size:12px;color:var(--text-muted);margin-top:6px">จุดเช็คกลางทาง: HM ~2:10 หรือ 10K ~58 นาที · 10K ทำได้ ≤${s2FmtH(goal10)} = พร้อม sub-2 · เทียบเท่าคำนวณด้วย Riegel (ประมาณการ)</div>`;
  // full table
  $('#s2-table').innerHTML = `<table><thead><tr><th>#</th><th>สัปดาห์</th><th>ช่วง</th><th>ศ. Quality</th><th>ส. Easy</th><th>อา. Long</th></tr></thead><tbody>${
    weeks.map(w => { const s = s2Sessions(w, P, sub2), [pn, pc] = S2_PH[w.ph];
      return `<tr style="${w.i === ci ? 'background:rgba(88,166,255,0.15);' : ''}${w.down ? 'opacity:0.75;' : ''}">
        <td class="numeric">${w.i + 1}</td><td>${s2Th(w.ws)}</td><td><span class="badge ${pc}">${pn}</span>${w.fb ? (w.fb > 0 ? ' 😌' : ' 🥵') : ''}</td>
        <td style="font-size:12px">${s.fri}</td><td style="font-size:12px">${s.sat.replace(' + 3-Minute Routine', '')}</td><td style="font-size:12px">${s.sun}</td></tr>`; }).join('')}</tbody></table>
    <div style="font-size:12px;color:var(--text-muted);margin-top:6px">ส. easy ต่อด้วย 3-Minute Routine ทุกสัปดาห์ · ทุกสัปดาห์ที่ 4 ของช่วง = down week · ปุ่ม ง่ายไป/หนักไป ขยับระดับ ±1 ให้สัปดาห์ถัดๆ ไป</div>`;
}

function renderSub2() {
  if (!$('#page-sub2')) return;
  if (!sub2) sub2 = s2Norm(DATA.sub2_settings);
  s2Fill();
  renderSub2Out();
}

// ----- GitHub storage -----
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
