'use strict';
/*
  Онлайн-арена «Шарики.io» — сервер.
  Один процесс Node.js без внешних библиотек: HTTP + WebSocket (RFC 6455) на одном порту (по умолчанию 8091).
  Сервер считает всю арену: ботов, точки, бонусы, пилы, кто кого съел. Игрок присылает своё положение,
  сервер проверяет, что он не «телепортируется», и рассылает состояние всем 15 раз в секунду.
  Живых игроков больше — ботов меньше, а арена растёт.
  Если файл скрипта (WATCH) обновился — процесс сам завершается, systemd запускает новую версию.
*/
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const PORT = +process.env.PORT || 8091;
const VERSION = '1.3.0';
const ROUND_LEN = +process.env.ROUND_LEN || 180; // раунд стран, секунд
const MAX_ACC = 12;                               // номера украшений (шапки, очки…)
const STATE_FILE = process.env.STATE_FILE || path.join(os.tmpdir(), 'ballio-day.json');
// грубые слова в никах заменяем на «Player» (ник видят все игроки)
const BAD = /(fuck|shit|bitch|cunt|nigg|fag|dick|porn|hitler|nazi|хуй|хуе|хуё|пизд|ебл|ебa|еба|ёба|бляд|блят|сука|мудак|пидор|пидр|залуп|гандон|шлюх|чмо)/i;
const FLAGS = ['RU', 'KZ', 'UZ', 'KG', 'UA', 'BY', 'TR', 'US', 'GB', 'DE', 'FR', 'IT', 'ES', 'PT', 'BR', 'AR', 'MX', 'CN', 'JP', 'KR', 'IN', 'ID', 'VN', 'TH',
  'PL', 'NL', 'SE', 'NO', 'FI', 'CA', 'EG', 'AE', 'NG', 'PK', 'AZ', 'GE', 'AM', 'TJ', 'MN',
  'CO', 'PH', 'RO', 'HU', 'CZ', 'AT', 'BE', 'CH', 'DK', 'IE', 'GR', 'PE', 'CL', 'VE', 'EC', 'UY', 'AU', 'NZ', 'MY', 'SG', 'BD', 'SA', 'IR', 'MA', 'DZ', 'TN', 'ZA', 'KE', 'LT', 'LV', 'EE', 'BG', 'RS', 'HR', 'SK', 'MD', 'TM'];
const SAW_R = 50;
const rOf = (m) => 20 + 5 * Math.sqrt(m);
const speedOf = (r) => 440 * Math.pow(40 / r, 0.32);
const rnd = (a, b) => a + Math.random() * (b - a);
function randIn(R) { const a = Math.random() * Math.PI * 2, d = Math.sqrt(Math.random()) * R; return { x: Math.cos(a) * d, y: Math.sin(a) * d }; }

// ---------------- WebSocket ----------------
function wsAccept(req, socket) {
  const key = req.headers['sec-websocket-key'];
  if (!key) { socket.destroy(); return null; }
  const acc = crypto.createHash('sha1').update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
  socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + acc + '\r\n\r\n');
  socket.setNoDelay(true);
  try { socket.setKeepAlive(true, 10000); } catch (e) { /* */ }
  const ws = { socket, buf: Buffer.alloc(0), onmsg: null, onclose: null, closed: false, lastT: Date.now() };
  ws.send = (obj) => {
    if (ws.closed) return;
    const data = Buffer.from(typeof obj === 'string' ? obj : JSON.stringify(obj));
    const n = data.length; let head;
    if (n < 126) head = Buffer.from([0x81, n]);
    else if (n < 65536) { head = Buffer.alloc(4); head[0] = 0x81; head[1] = 126; head.writeUInt16BE(n, 2); }
    else { head = Buffer.alloc(10); head[0] = 0x81; head[1] = 127; head.writeUInt32BE(0, 2); head.writeUInt32BE(n, 6); }
    try { socket.write(Buffer.concat([head, data])); } catch (e) { /* */ }
  };
  const close = () => { if (ws.closed) return; ws.closed = true; try { socket.destroy(); } catch (e) { /* */ } if (ws.onclose) ws.onclose(); };
  ws.close = close;
  socket.on('data', (chunk) => {
    ws.lastT = Date.now();
    ws.buf = Buffer.concat([ws.buf, chunk]);
    if (ws.buf.length > 1 << 20) { close(); return; }
    for (;;) {
      if (ws.buf.length < 2) return;
      const b0 = ws.buf[0], b1 = ws.buf[1], op = b0 & 15, masked = b1 & 128;
      let len = b1 & 127, off = 2;
      if (len === 126) { if (ws.buf.length < 4) return; len = ws.buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (ws.buf.length < 10) return; len = ws.buf.readUInt32BE(6); off = 10; }
      const mOff = off; if (masked) off += 4;
      if (ws.buf.length < off + len) return;
      const payload = Buffer.from(ws.buf.slice(off, off + len));
      if (masked) { for (let i = 0; i < payload.length; i++) payload[i] ^= ws.buf[mOff + (i & 3)]; }
      ws.buf = ws.buf.slice(off + len);
      if (op === 8) { close(); return; }
      if (op === 9 && payload.length < 126) { try { socket.write(Buffer.concat([Buffer.from([0x8a, payload.length]), payload])); } catch (e) { /* */ } continue; }
      if (op === 1 && ws.onmsg) { let m = null; try { m = JSON.parse(payload.toString('utf8')); } catch (e) { continue; } if (m && typeof m === 'object' && !Array.isArray(m)) { try { ws.onmsg(m); } catch (e) { logErr('msg', e); } } }
    }
  });
  socket.on('close', close); socket.on('error', close);
  return ws;
}

// ---------------- Зачёт стран за день (переживает перезапуск: лежит в файле) ----------------
const dayKey = () => new Date().toISOString().slice(0, 10);
let day = { d: dayKey(), pts: {}, wins: {} };
try { const s = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); if (s && s.d === dayKey() && s.pts) day = s; } catch (e) { /* нет файла — новый день */ }
function checkDay() { const k = dayKey(); if (day.d !== k) day = { d: k, pts: {}, wins: {} }; }
function saveDay() { try { fs.writeFileSync(STATE_FILE, JSON.stringify(day)); } catch (e) { /* нет прав — живём в памяти */ } }
function dayTop(n) { checkDay(); return Object.entries(day.pts).sort((a, b) => b[1] - a[1]).slice(0, n).map(([f, p]) => [f, Math.round(p), day.wins[f] || 0]); }
setInterval(saveDay, 60000);

// ---------------- Комнаты ----------------
// Настройки своей комнаты (меняет хозяин — первый вошедший живой игрок). В общей арене main — всегда по умолчанию.
//   mode: 0 — каждый сам за себя, 1 — две команды (синие/красные), 2 — друзья против ботов
//   sp: скорость ×1 / ×1,5 / ×2;  bots: 0 — нет, 1 — мало, 2 — обычно, 3 — много;  diff: 0 — лёгкие, 1 — обычные, 2 — сильные
//   saws: 0 — нет, 1 — обычно, 2 — много;  rl: длина раунда, с
const CFG0 = { mode: 0, sp: 1, bots: 2, diff: 1, saws: 1, rl: ROUND_LEN };
function cleanCfg(o, old) {
  const c = Object.assign({}, old || CFG0), pick = (v, list) => (list.indexOf(+v) >= 0 ? +v : undefined);
  if (o && typeof o === 'object') {
    const m = pick(o.mode, [0, 1, 2]); if (m !== undefined) c.mode = m;
    const sp = pick(o.sp, [1, 1.5, 2]); if (sp !== undefined) c.sp = sp;
    const b = pick(o.bots, [0, 1, 2, 3]); if (b !== undefined) c.bots = b;
    const d = pick(o.diff, [0, 1, 2]); if (d !== undefined) c.diff = d;
    const w = pick(o.saws, [0, 1, 2]); if (w !== undefined) c.saws = w;
    const rl = pick(o.rl, [120, 180, 300]); if (rl !== undefined) c.rl = rl;
  }
  return c;
}
const rooms = new Map();
function getRoom(name) {
  let r = rooms.get(name);
  if (!r) { r = { name, R: 1180, balls: new Map(), dots: new Map(), powers: new Map(), saws: [], clients: new Set(), nid: 1, did: 1, pid: 1, powT: 0, dAdd: [], dDel: [], ev: [], meta: [], tickN: 0, emptyT: 0, rT: ROUND_LEN, sc: {}, scAll: {}, ts: [0, 0, 0], cfg: Object.assign({}, CFG0), host: 0 }; rooms.set(name, r); }
  return r;
}
const sameTeam = (a, b) => a.team > 0 && a.team === b.team;
const plainRoom = (r) => { const c = r.cfg; return c.mode === 0 && c.sp === 1 && c.bots >= 2 && c.diff >= 1 && c.saws >= 1; };
// в какую команду поставить новенького: где меньше живых игроков (а при равенстве — где меньше шариков)
function balanceTeam(r, human) {
  const n = [0, 0, 0], all = [0, 0, 0];
  for (const b of r.balls.values()) if (b.team) { all[b.team]++; if (b.human) n[b.team]++; }
  if (human) return n[1] < n[2] ? 1 : n[2] < n[1] ? 2 : all[1] <= all[2] ? 1 : 2;
  return all[1] <= all[2] ? 1 : 2;
}
function teamFor(r, b) { const m = r.cfg.mode; if (m === 2) return b.human ? 1 : 2; if (m === 1) return b.wantTeam === 1 || b.wantTeam === 2 ? b.wantTeam : balanceTeam(r, b.human); return 0; }
function retag(r) { // режим сменился — заново раздаём команды
  for (const b of r.balls.values()) b.team = 0;
  const list = Array.from(r.balls.values()).sort((a, c) => (c.human - a.human));
  for (const b of list) { b.team = teamFor(r, b); r.meta.push(metaOf(b)); }
}
function sendCfg(r) { const msg = JSON.stringify({ t: 'cfg', cfg: r.cfg, host: r.host }); for (const ws of r.clients) ws.send(msg); }
function humans(r) { let n = 0; for (const b of r.balls.values()) if (b.human) n++; return n; }
function addDot(r, x, y) { if (x === undefined) { const p = randIn(r.R * 0.97); x = p.x; y = p.y; } const d = { id: r.did++, x: Math.round(x), y: Math.round(y), c: (Math.random() * 8) | 0 }; r.dots.set(d.id, d); r.dAdd.push([d.id, d.x, d.y, d.c]); }
const metaOf = (b) => [b.id, b.name, b.skin, b.human ? 1 : 0, b.acc | 0, b.team | 0];
function newBall(r, o) {
  const b = Object.assign({ id: r.nid++, x: 0, y: 0, vx: 0, vy: 0, m: 10, alive: true, shield: 0, boost: 0, magnet: 0, sawCD: 0, tx: 0, ty: 0, aiT: 0, flee: false, respawnT: 0, human: false, name: '', skin: 'US', acc: 0, ws: null, cx: 0, cy: 0, lastM: 0, diedAt: 0, reviveAt: -1e12, team: 0, wantTeam: 0, preyId: 0 }, o);
  b.team = teamFor(r, b); b.r = rOf(b.m); b.cx = b.x; b.cy = b.y; r.balls.set(b.id, b); r.meta.push(metaOf(b)); return b;
}
// масса, набранная шариком, идёт в зачёт его стране: живым игрокам целиком, ботам — меньше
function gain(r, b, amt) {
  b.m += amt; b.r = rOf(b.m);
  // зачёт стран — только живые игроки (боты в таблицу стран не попадают: раньше там первым шёл «Bots», выглядело странно).
  // Для камеры роликов — отдельный счёт по флагам вместе с ботами. В командах — счёт команд.
  if (b.human) r.sc[b.skin] = (r.sc[b.skin] || 0) + amt;
  if (b.team) r.ts[b.team] += amt * (b.human ? 1 : r.cfg.mode === 2 ? BOT_COOP : BOT_TEAM);
  r.scAll[b.skin] = (r.scAll[b.skin] || 0) + amt * (b.human ? 1 : 0.4);
  if (b.human && plainRoom(r)) { checkDay(); day.pts[b.skin] = (day.pts[b.skin] || 0) + amt; } // в комнатах со своими правилами (скорость ×2, без ботов…) очки дня не копим
}
const BOT_TEAM = 0.5;  // в двух командах боты есть у обеих сторон — их очки идут в зачёт наполовину (решают живые)
const BOT_COOP = 0.25; // «друзья против ботов»: у ботов шариков больше, поэтому их очки весят меньше
const roundTop = (r, n, all) => Object.entries(all ? r.scAll : r.sc).sort((a, b) => b[1] - a[1]).slice(0, n).map(([f, p]) => [f, Math.round(p)]);
function endRound(r) {
  const top = roundTop(r, 5), topAll = roundTop(r, 5, true);
  if (top.length && r.name === 'main') { checkDay(); day.wins[top[0][0]] = (day.wins[top[0][0]] || 0) + 1; }
  const dt10 = dayTop(10);
  const o = { t: 'rw', win: top.length ? top[0][0] : '', top, day: dt10 };
  if (r.cfg.mode) { o.ts = [Math.round(r.ts[1]), Math.round(r.ts[2])]; o.tw = r.ts[1] > r.ts[2] ? 1 : r.ts[2] > r.ts[1] ? 2 : 0; }
  const msg = JSON.stringify(o);
  const msgSpec = JSON.stringify({ t: 'rw', win: topAll.length ? topAll[0][0] : '', top: topAll, day: dt10 });
  for (const ws of r.clients) ws.send(ws.spec ? msgSpec : msg);
  r.sc = {}; r.scAll = {}; r.ts = [0, 0, 0]; r.rT = r.cfg.rl; saveDay();
}
function cleanName(s, fallback) {
  let n = Array.from(String(s || '').replace(/[<>&"'`\u0000-\u001f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g, '').trim()).slice(0, 14).join('').trim(); // по символам, не режем эмодзи пополам; без невидимых и «переворачивающих» знаков
  if (!n || BAD.test(n.replace(/[\s._\-*0-9]/g, ''))) n = fallback;
  return n;
}
function newSaw(r) { const or = rnd(0.25, 0.82) * r.R, a = rnd(0, 6.283); return { or, a, w: rnd(0.05, 0.11) * (Math.random() < 0.5 ? -1 : 1), x: Math.cos(a) * or, y: Math.sin(a) * or }; }
function safeSpot(r) {
  let best = null, bd = -1;
  for (let i = 0; i < 24; i++) {
    const q = randIn(r.R * 0.85); let md = 1e9;
    for (const o of r.balls.values()) if (o.alive) md = Math.min(md, Math.hypot(o.x - q.x, o.y - q.y) - o.r);
    for (const s of r.saws) md = Math.min(md, Math.hypot(s.x - q.x, s.y - q.y) - SAW_R);
    if (md > bd) { bd = md; best = q; }
  }
  return best || randIn(r.R * 0.5); // на всякий случай: никогда не возвращаем пустое место
}
function freeSkin(r) { const used = new Set(); for (const b of r.balls.values()) used.add(b.skin); const free = FLAGS.filter((f) => !used.has(f)); const pool = free.length ? free : FLAGS; return pool[(Math.random() * pool.length) | 0]; }

// новичка первые секунды после появления боты не преследуют (первые секунды решают, останется ли игрок)
const FRESH_MS = [15000, 12000, 6000];
// сложность ботов: [лёгкие, обычные, сильные]
const AI = {
  react: [[0.5, 0.35], [0.25, 0.2], [0.12, 0.08]],   // как часто думают: база + случайная добавка, с
  lazy: [0.7, 0.45, 0.12],                            // доля «раздумий», когда бот не трогает живого игрока
  huntH: [180, 240, 420], huntB: [300, 380, 520],     // с какого расстояния охотится на игрока / на бота
  lead: [0, 0.3, 1],                                  // упреждение: 0 — едет в шарик, 1 — считает точку встречи
  speed: [0.78, 0.85, 0.93],                          // доля от максимальной скорости
  turn: [3.2, 5, 7.5],                                // как быстро поворачивает, рад/с (плавно, без рывков)
  sawSee: [70, 120, 220],                             // за сколько видит пилу
};
// точка встречи с целью: где цель будет через t, если бот поедет туда со своей скоростью
function intercept(b, o, sp, k) {
  if (!k) return [o.x, o.y];
  let t = Math.hypot(o.x - b.x, o.y - b.y) / Math.max(60, sp);
  for (let i = 0; i < 3; i++) { const px = o.x + o.vx * t, py = o.y + o.vy * t; t = Math.hypot(px - b.x, py - b.y) / Math.max(60, sp); }
  t = Math.min(1.4, t) * k;
  return [o.x + o.vx * t, o.y + o.vy * t];
}
function think(r, b) {
  const D = r.cfg.diff, now = Date.now();
  let threat = null, td = 1e9, prey = null, pd = 1e9;
  for (const o of r.balls.values()) {
    if (o === b || !o.alive || sameTeam(o, b)) continue;
    const d = Math.hypot(o.x - b.x, o.y - b.y) - o.r - b.r;
    if (o.r > b.r * 1.12 && d < 260 + o.r && d < td) { threat = o; td = d; }
    if (b.r > o.r * 1.3 && d < (o.human ? AI.huntH[D] : AI.huntB[D]) && d < pd && o.shield <= 0 && !(o.human && b.lazyHuman) && !(o.human && now - (o.spawnAt || 0) < FRESH_MS[D])) { prey = o; pd = d; }
  }
  // большим ботам пилы опасны — объезжают (сильные видят пилу раньше и учитывают, куда она едет)
  if (b.r > SAW_R * 1.15) for (const s of r.saws) {
    const ahead = D === 2 ? 0.5 : 0, sx = s.x - Math.sin(s.a) * s.or * s.w * ahead, sy = s.y + Math.cos(s.a) * s.or * s.w * ahead;
    const d = Math.min(Math.hypot(s.x - b.x, s.y - b.y), Math.hypot(sx - b.x, sy - b.y)) - SAW_R - b.r;
    if (d < AI.sawSee[D] && d < td) { threat = { x: s.x, y: s.y }; td = d; }
  }
  b.flee = false; b.preyId = 0;
  if (threat && (!prey || td < pd * 0.7)) {
    // убегает от угрозы; сильные — не строго назад, а вбок от её хода и подальше от края арены
    let a = Math.atan2(b.y - threat.y, b.x - threat.x);
    if (D === 2 && threat.vx !== undefined) { const ta = Math.atan2(threat.vy, threat.vx); const side = Math.sin(a - ta) >= 0 ? 1 : -1; a += side * 0.5; }
    else a += (Math.random() - 0.5) * 0.6;
    let tx = b.x + Math.cos(a) * 400, ty = b.y + Math.sin(a) * 400;
    const dd = Math.hypot(tx, ty); if (dd > r.R * 0.85) { tx *= (r.R * 0.85) / dd; ty *= (r.R * 0.85) / dd; }
    b.tx = tx; b.ty = ty; b.flee = true; return;
  }
  if (prey && Math.random() > (D === 2 ? 0.03 : 0.12)) {
    const sp = speedOf(b.r) * r.cfg.sp * AI.speed[D];
    let [tx, ty] = intercept(b, prey, sp, AI.lead[D]);
    // сильные заходят вдвоём с разных сторон: второй охотник целится наперерез сбоку
    if (D === 2) {
      let mates = 0; for (const o of r.balls.values()) if (o !== b && !o.human && o.alive && o.preyId === prey.id && sameTeamOrFfa(o, b)) mates++;
      if (mates % 2 === 1) { const pa = Math.atan2(prey.vy, prey.vx) + (b.id % 2 ? 1.2 : -1.2), off = prey.r + b.r + 120; tx += Math.cos(pa) * off; ty += Math.sin(pa) * off; }
    }
    b.tx = tx; b.ty = ty; b.preyId = prey.id; return;
  }
  // бонус рядом — заберёт
  for (const p of r.powers.values()) if (Math.hypot(p.x - b.x, p.y - b.y) < (D === 2 ? 500 : 350) && Math.random() < 0.6) { b.tx = p.x; b.ty = p.y; return; }
  if (Math.random() < (D === 0 ? 0.25 : 0.15)) { const q = randIn(r.R * 0.8); b.tx = q.x; b.ty = q.y; return; }
  let best = null, bd = 1e9; const n = r.dots.size;
  if (n) { const arr = Array.from(r.dots.values()); for (let i = 0; i < (D === 2 ? 60 : 40); i++) { const p = arr[(Math.random() * n) | 0]; const d = Math.hypot(p.x - b.x, p.y - b.y); if (d < bd) { bd = d; best = p; } } }
  if (best) { b.tx = best.x; b.ty = best.y; }
}
const sameTeamOrFfa = (a, b) => !a.team || a.team === b.team;

function arenaR(nh) {
  const n = Math.max(1, nh);
  if (n <= 3) return 900 + 280 * n;
  return Math.sqrt(0.8e6 * (n + Math.max(6, 12 - n)) / Math.PI); // ~0,8 млн кв. единиц на шарик (как при 3 игроках)
}
function step(r, dt) {
  const nh = humans(r);
  // до 3 живых игроков арена заметно растёт с каждым; дальше — по числу шариков, чтобы на 20 игроков не было пусто
  // (раньше росла на 280 за каждого: при 20 игроках радиус 6500 — в 5,5 раза шире, и игроки почти не встречались)
  r.R += (arenaR(nh) - r.R) * Math.min(1, dt * 0.5);
  const bc = r.cfg.bots, wantBots = bc === 0 ? 0 : bc === 1 ? 4 : bc === 3 ? Math.max(14, 20 - nh) : Math.max(6, 12 - nh);
  const bots = []; for (const b of r.balls.values()) if (!b.human) bots.push(b);
  if (bots.length < wantBots) { const q = safeSpot(r); newBall(r, { x: q.x, y: q.y, m: rnd(4, 18), skin: freeSkin(r), acc: Math.random() < 0.3 ? 2 + ((Math.random() * 10) | 0) : 0 }); }
  else if (bots.length > wantBots) { bots.sort((a, c) => (a.alive - c.alive) || (a.m - c.m)); const b = bots[0]; r.balls.delete(b.id); r.ev.push([0, b.id, 2]); }
  const wantDots = Math.round(r.R * r.R * 0.00024);
  for (let i = 0; i < 12 && r.dots.size < wantDots; i++) addDot(r);
  // пилы ездят по кругам; их больше, когда игроков больше
  const wantSaws = r.cfg.saws === 0 ? 0 : r.cfg.saws === 2 ? 6 + 2 * nh : 3 + nh;
  while (r.saws.length < wantSaws) r.saws.push(newSaw(r));
  if (r.saws.length > wantSaws) r.saws.length = wantSaws;
  for (const s of r.saws) { s.a += s.w * dt; s.x = Math.cos(s.a) * s.or; s.y = Math.sin(s.a) * s.or; }
  // бонусы: 0 — ускорение, 1 — магнит, 2 — щит
  r.powT -= dt;
  r.rT -= dt; if (r.rT <= 0) endRound(r);
  if (r.powT <= 0 && r.powers.size < 4 + 2 * Math.min(nh, 10)) { r.powT = 2.5; const q = randIn(r.R * 0.85), p = { id: r.pid++, x: Math.round(q.x), y: Math.round(q.y), k: (Math.random() * 3) | 0 }; r.powers.set(p.id, p); }

  for (const b of r.balls.values()) {
    if (!b.alive) {
      if (!b.human) { b.respawnT -= dt; if (b.respawnT <= 0) { const q = safeSpot(r); Object.assign(b, { x: q.x, y: q.y, vx: 0, vy: 0, m: rnd(4, 16), alive: true, shield: 0, boost: 0, magnet: 0 }); b.r = rOf(b.m); if (r.cfg.mode === 1) { b.team = 0; b.team = balanceTeam(r, false); r.meta.push(metaOf(b)); } } }
      continue;
    }
    b.shield = Math.max(0, b.shield - dt); b.boost = Math.max(0, b.boost - dt); b.magnet = Math.max(0, b.magnet - dt); b.sawCD = Math.max(0, b.sawCD - dt);
    const bk = (b.boost > 0 ? 1.6 : 1) * r.cfg.sp;
    if (b.human) {
      // положение присылает игрок; сервер подтягивается к нему, но не быстрее, чем шарик может катиться
      let dx = b.cx - b.x, dy = b.cy - b.y; const d = Math.hypot(dx, dy), max = speedOf(b.r) * bk * 1.7 * dt + 3;
      if (d > 320 * bk) { b.cx = b.x; b.cy = b.y; dx = 0; dy = 0; if (b.ws) b.ws.send({ t: 'fix', x: Math.round(b.x), y: Math.round(b.y) }); }
      else if (d > max) { dx *= max / d; dy *= max / d; }
      b.vx = dx / dt; b.vy = dy / dt; b.x += dx; b.y += dy;
    } else {
      const D = r.cfg.diff;
      b.aiT -= dt; if (b.aiT <= 0) { b.aiT = AI.react[D][0] + Math.random() * AI.react[D][1]; b.lazyHuman = Math.random() < AI.lazy[D]; think(r, b); }
      const vx = b.tx - b.x, vy = b.ty - b.y, d = Math.hypot(vx, vy) || 1, pw = d > 20 ? 1 : 0.3;
      const sp = speedOf(b.r) * (b.flee ? AI.speed[D] - 0.08 : AI.speed[D]) * bk * pw;
      // плавный поворот: направление скорости поворачивается к цели не быстрее turn рад/с, скорость меняется мягко
      const cur = Math.hypot(b.vx, b.vy), want = Math.atan2(vy, vx);
      let ang = cur > 5 ? Math.atan2(b.vy, b.vx) : want, da = want - ang;
      while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
      const mt = AI.turn[D] * dt; ang += Math.max(-mt, Math.min(mt, da));
      const ns = cur + (sp * (Math.abs(da) > 2.2 ? 0.6 : 1) - cur) * Math.min(1, dt * 4);
      b.vx = Math.cos(ang) * ns; b.vy = Math.sin(ang) * ns;
      b.x += b.vx * dt; b.y += b.vy * dt;
    }
    const dd = Math.hypot(b.x, b.y), lim = r.R - b.r * 0.6; if (dd > lim) { b.x *= lim / dd; b.y *= lim / dd; }
    // очень большие понемногу худеют (боты — заметнее), чтобы арену не захватывали боты и не было вечного чемпиона
    if (!b.human && b.m > 45) { b.m -= b.m * 0.02 * dt; b.r = rOf(b.m); }
    else if (b.m > 150) { b.m -= b.m * 0.003 * dt; b.r = rOf(b.m); }
    for (const p of r.powers.values()) if (Math.hypot(p.x - b.x, p.y - b.y) < b.r + 32) {
      r.powers.delete(p.id);
      if (p.k === 0) b.boost = 4; else if (p.k === 1) b.magnet = 7; else b.shield = Math.max(b.shield, 5);
      r.ev.push([b.id, p.k, 4]); break;
    }
  }
  // точки (магнит — собирает издалека)
  for (const b of r.balls.values()) {
    if (!b.alive) continue;
    const pr = b.magnet > 0 ? b.r + 170 : b.r, rr = pr * pr;
    for (const d of r.dots.values()) { const dx = d.x - b.x, dy = d.y - b.y; if (dx * dx + dy * dy < rr) { r.dots.delete(d.id); r.dDel.push(d.id); gain(r, b, 1); } }
  }
  // пилы режут большие шарики: минус 30% массы, кусочки рассыпаются точками. Маленьким пилы не страшны.
  for (const s of r.saws) for (const b of r.balls.values()) {
    if (!b.alive || b.r < SAW_R * 1.15 || b.sawCD > 0 || b.shield > 0) continue;
    if (Math.hypot(s.x - b.x, s.y - b.y) < b.r * 0.85 + SAW_R * 0.5) {
      const lost = b.m * 0.3; b.m -= lost; b.r = rOf(b.m); b.sawCD = 1.5;
      for (let k = 0; k < Math.min(36, lost / 2); k++) { const a = Math.random() * 6.283, d = b.r + 40 + Math.random() * 150; addDot(r, b.x + Math.cos(a) * d, b.y + Math.sin(a) * d); }
      if (!b.human) { const a = Math.atan2(b.y - s.y, b.x - s.x); b.x += Math.cos(a) * 70; b.y += Math.sin(a) * 70; }
      r.ev.push([b.id, Math.round(lost), 3]);
    }
  }
  // кто кого съел
  const arr = []; for (const b of r.balls.values()) if (b.alive) arr.push(b);
  for (const a of arr) for (const b of arr) {
    if (a === b || !a.alive || !b.alive || b.shield > 0 || sameTeam(a, b)) continue;
    if (a.r > b.r * 1.12 && Math.hypot(a.x - b.x, a.y - b.y) < a.r - b.r * 0.15) {
      b.alive = false; b.lastM = b.m; b.diedAt = Date.now(); gain(r, a, b.m * 0.85); r.ev.push([a.id, b.id, 1]);
      if (b.human) { if (b.ws) b.ws.send({ t: 'dead', by: a.id, m: Math.round(b.m), day: dayTop(10) }); }
      else b.respawnT = rnd(3, 6);
    }
  }
}

function broadcast(r) {
  const b = [];
  for (const x of r.balls.values()) b.push([x.id, Math.round(x.x), Math.round(x.y), Math.round(x.m * 10), x.alive ? 1 : 0, (x.shield > 0 ? 1 : 0) | (x.boost > 0 ? 2 : 0) | (x.magnet > 0 ? 4 : 0)]);
  const pw = []; for (const p of r.powers.values()) pw.push([p.id, p.x, p.y, p.k]);
  const sw = r.saws.map((s) => [Math.round(s.x), Math.round(s.y)]);
  const o = { t: 's', T: Math.round(performance.now()), R: Math.round(r.R), b, da: r.dAdd, dd: r.dDel, ev: r.ev, mt: r.meta, pw, sw }; // T — часы сервера: клиент плавно проигрывает снимки
  let msgSpec = null;
  if (r.tickN % 30 === 0) {
    o.rt = Math.ceil(r.rT);
    o.cs = roundTop(r, 5, true); msgSpec = JSON.stringify(o); // зрителю (ролики) — битва флагов вместе с ботами
    o.cs = roundTop(r, 5);
    if (r.cfg.mode) o.ts = [Math.round(r.ts[1]), Math.round(r.ts[2])];
  }
  const msg = JSON.stringify(o);
  r.dAdd = []; r.dDel = []; r.ev = []; r.meta = [];
  for (const ws of r.clients) ws.send(ws.spec && msgSpec ? msgSpec : msg);
}

function join(ws, m) {
  if (ws.room) return;
  const roomName = String(m.room || 'main').replace(/[^a-z0-9_-]/gi, '').slice(0, 24) || 'main';
  const r = getRoom(roomName);
  if (r.clients.size >= 40) { ws.send({ t: 'full' }); ws.close(); return; }
  if (!r.dots.size) for (let i = 0; i < 300; i++) addDot(r);
  if (m.spec) {
    // зритель (камера для роликов): без своего шарика, в игроки не считается, не больше 3 на комнату
    let n = 0; for (const c of r.clients) if (c.spec) n++;
    if (n >= 3) { ws.send({ t: 'full' }); ws.close(); return; }
    ws.room = r; ws.spec = true; r.clients.add(ws);
    const meta = []; for (const x of r.balls.values()) meta.push(metaOf(x));
    const dots = []; for (const d of r.dots.values()) dots.push([d.id, d.x, d.y, d.c]);
    ws.send({ t: 'w', id: 0, spec: 1, x: 0, y: 0, R: Math.round(r.R), mt: meta, dots, v: VERSION, cs: roundTop(r, 5, true), rt: Math.ceil(r.rT), rl: r.cfg.rl, day: dayTop(10), cfg: r.cfg, host: r.host });
    return;
  }
  const name = cleanName(m.name, 'Player');
  const skin = FLAGS.indexOf(m.skin) >= 0 ? m.skin : 'US';
  const acc = Math.max(0, Math.min(MAX_ACC, m.acc | 0));
  // у ботов не должно быть того же флага, что у живого игрока
  for (const o of r.balls.values()) if (!o.human && o.skin === skin) { o.skin = freeSkin(r); if (o.skin === skin) o.skin = FLAGS[(FLAGS.indexOf(skin) + 7) % FLAGS.length]; r.meta.push(metaOf(o)); }
  const q = safeSpot(r);
  const wt = m.team === 1 || m.team === 2 ? m.team : 0;
  const b = newBall(r, { x: q.x, y: q.y, m: 18, human: true, name, skin, acc, ws, shield: 4, wantTeam: wt }); b.spawnAt = Date.now();
  ws.room = r; ws.ball = b; r.clients.add(ws);
  // хозяин своей комнаты — первый вошедший; в общей арене хозяина нет
  let newHost = false;
  if (r.name !== 'main' && !hostAlive(r)) { r.host = b.id; newHost = true; }
  const meta = []; for (const x of r.balls.values()) meta.push(metaOf(x));
  const dots = []; for (const d of r.dots.values()) dots.push([d.id, d.x, d.y, d.c]);
  const o = { t: 'w', id: b.id, x: Math.round(b.x), y: Math.round(b.y), R: Math.round(r.R), mt: meta, dots, v: VERSION, cs: roundTop(r, 5), rt: Math.ceil(r.rT), rl: r.cfg.rl, day: dayTop(10), cfg: r.cfg, host: r.host };
  if (r.cfg.mode) o.ts = [Math.round(r.ts[1]), Math.round(r.ts[2])];
  ws.send(o);
  if (newHost) sendCfg(r);
}

function hostAlive(r) { if (!r.host) return false; const h = r.balls.get(r.host); return !!(h && h.human); }
function respawn(ws, m) {
  const b = ws.ball, r = ws.room; if (!b || !r) return;
  if (!b.alive) {
    if (r.cfg.mode === 1 && b.wantTeam && b.wantTeam !== b.team) b.team = b.wantTeam;
    // смена страны / ника / украшения — между жизнями
    if (m && FLAGS.indexOf(m.skin) >= 0) b.skin = m.skin;
    if (m && m.name) b.name = cleanName(m.name, b.name);
    if (m && m.acc !== undefined) b.acc = Math.max(0, Math.min(MAX_ACC, m.acc | 0));
    r.meta.push(metaOf(b));
    // возрождение за рекламу или монеты: половина массы, не чаще раза в 200 с и только сразу после смерти
    let mass = 18; const now = Date.now();
    if (m && m.keep && b.lastM > 36 && now - b.diedAt < 120000 && now - b.reviveAt > 200000) { mass = Math.min(400, b.lastM * 0.5); b.reviveAt = now; }
    const q = safeSpot(r); Object.assign(b, { x: q.x, y: q.y, cx: q.x, cy: q.y, vx: 0, vy: 0, m: mass, alive: true, shield: 4, boost: 0, magnet: 0, spawnAt: Date.now() }); b.r = rOf(b.m);
  }
  ws.send({ t: 'fix', x: Math.round(b.x), y: Math.round(b.y), re: 1, m: Math.round(b.m * 10) / 10 });
}

function onMsg(ws, m) {
  if (m.t === 'hello') return join(ws, m);
  if (m.t === 'ping') { ws.send({ t: 'pong', c: m.c }); return; }
  const b = ws.ball; if (!b) return;
  if (m.t === 'p') { const x = +m.x, y = +m.y; if (isFinite(x) && isFinite(y)) { b.cx = x; b.cy = y; } return; }
  if (m.t === 're') return respawn(ws, m);
  if (m.t === 'cfg') { // хозяин меняет правила своей комнаты
    const r = ws.room; if (!r || r.name === 'main' || r.host !== b.id) return;
    const old = r.cfg, c = cleanCfg(m.cfg, old); r.cfg = c;
    if (c.mode !== old.mode) { retag(r); r.sc = {}; r.ts = [0, 0, 0]; r.rT = c.rl; }
    else if (c.rl !== old.rl) r.rT = Math.min(r.rT, c.rl);
    sendCfg(r); return;
  }
  if (m.t === 'team') { // игрок выбрал команду (в режиме двух команд)
    const r = ws.room; if (!r || r.cfg.mode !== 1 || (m.team !== 1 && m.team !== 2)) return;
    b.wantTeam = m.team;
    if (!b.alive || b.m <= 40 || Date.now() - (b.spawnAt || 0) < 5000) { b.team = m.team; r.meta.push(metaOf(b)); }
    return;
  }
  if (m.t === 'dbg' && process.env.TEST === '1' && ws.ball) { const b = ws.ball; if (m.m) { b.m = Math.max(5, Math.min(3000, +m.m || 18)); b.r = rOf(b.m); } if (m.x !== undefined) { b.x = b.cx = +m.x; b.y = b.cy = +m.y; ws.send({ t: 'fix', x: b.x, y: b.y }); } return; }
}
function onClose(ws) {
  const r = ws.room; if (!r) return;
  r.clients.delete(ws);
  if (ws.ball) {
    r.balls.delete(ws.ball.id); r.ev.push([0, ws.ball.id, 2]);
    if (r.host === ws.ball.id) { r.host = 0; for (const c of r.clients) if (c.ball) { r.host = c.ball.id; break; } sendCfg(r); }
  }
}

// ---------------- HTTP ----------------
const perIp = new Map();
const allWs = new Set();
function httpHandler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.url.indexOf('/health') === 0) {
    let h = 0; for (const r of rooms.values()) h += r.clients.size;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.end(JSON.stringify({ ok: 1, v: VERSION, rooms: rooms.size, players: h, sockets: allWs.size, tls: tlsUntil || undefined }));
    return;
  }
  if (req.url.indexOf('/day') === 0) {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.end(JSON.stringify({ d: day.d, top: dayTop(40) }));
    return;
  }
  res.statusCode = 404; res.end('ballio');
}
function onUpgrade(req, socket) {
  if (req.url.indexOf('/ws') !== 0) { socket.destroy(); return; }
  const ip = req.socket.remoteAddress || '';
  const n = perIp.get(ip) || 0; if (n >= 40) { socket.destroy(); return; }
  const ws = wsAccept(req, socket); if (!ws) return;
  perIp.set(ip, n + 1); allWs.add(ws);
  ws.onmsg = (m) => onMsg(ws, m);
  ws.onclose = () => { allWs.delete(ws); perIp.set(ip, Math.max(0, (perIp.get(ip) || 1) - 1)); onClose(ws); };
}
const server = http.createServer(httpHandler);
server.on('upgrade', onUpgrade);
server.listen(PORT, () => console.log('ballio ' + VERSION + ' on :' + PORT));

// защищённое подключение (wss) — нужно площадкам на https (CrazyGames и др.).
// Включается, только если есть сертификат: TLS_CERT / TLS_KEY (порт TLS_PORT, на сервере — 443).
// Сертификат на IP живёт ~6 дней: продлевает lego, файл перечитываем без перезапуска.
// ACME_ALPN_PORT: проверочные подключения Let's Encrypt (ALPN «acme-tls/1») передаём lego на этот порт,
// чтобы продление шло, пока игра работает на 443.
const TLS_CERT = process.env.TLS_CERT || '', TLS_KEY = process.env.TLS_KEY || '', TLS_PORT = +process.env.TLS_PORT || 8443;
const ACME_PORT = +process.env.ACME_ALPN_PORT || 0;
let tlsUntil = '';
// есть ли в первом пакете TLS (ClientHello) протокол acme-tls/1
function isAcmeHello(b) {
  try {
    if (b[0] !== 0x16 || b[5] !== 0x01) return false;
    let p = 43; p += 1 + b[p];               // session id
    p += 2 + b.readUInt16BE(p);              // шифры
    p += 1 + b[p];                           // сжатие
    const end = Math.min(b.length, p + 2 + b.readUInt16BE(p)); p += 2;
    while (p + 4 <= end) {
      const type = b.readUInt16BE(p), len = b.readUInt16BE(p + 2); p += 4;
      if (type === 16) { // ALPN
        let q = p + 2; const qe = Math.min(end, p + 2 + b.readUInt16BE(p));
        while (q < qe) { const l = b[q]; if (b.toString('latin1', q + 1, q + 1 + l) === 'acme-tls/1') return true; q += 1 + l; }
        return false;
      }
      p += len;
    }
  } catch (e) { /* битый пакет — обычное подключение */ }
  return false;
}
if (TLS_CERT && TLS_KEY) {
  try {
    const tls = require('tls'), net = require('net'), { Duplex } = require('stream');
    const opts = () => ({ cert: fs.readFileSync(TLS_CERT), key: fs.readFileSync(TLS_KEY) });
    const readUntil = () => { try { tlsUntil = new crypto.X509Certificate(fs.readFileSync(TLS_CERT)).validTo; } catch (e) { tlsUntil = '?'; } };
    let secureContext = tls.createSecureContext(opts()); readUntil();
    // http-сервер без своего порта: в него отдаём уже расшифрованные подключения
    const inner = http.createServer(httpHandler); inner.on('upgrade', onUpgrade);
    const serveTls = (sock, first) => {
      // обёртка над сокетом: возвращаем прочитанный первый пакет и дальше передаём всё как есть
      const d = new Duplex({
        read() { sock.resume(); },
        write(c, e, cb) { if (sock.destroyed) return cb(); sock.write(c, e, cb); },
        final(cb) { sock.end(); cb(); },
        destroy(err, cb) { sock.destroy(); cb(err); },
      });
      sock.on('data', (c) => { if (!d.push(c)) sock.pause(); });
      sock.on('end', () => d.push(null));
      sock.on('close', () => d.destroy());
      d.push(first);
      const ts = new tls.TLSSocket(d, { isServer: true, secureContext, ALPNProtocols: ['http/1.1'] });
      Object.defineProperty(ts, 'remoteAddress', { value: sock.remoteAddress });
      ts.on('error', () => ts.destroy());
      inner.emit('connection', ts);
      sock.resume();
    };
    // перед TLS смотрим первый пакет: проверку Let's Encrypt — в lego, всё остальное — в игру
    const front = net.createServer((sock) => {
      let buf = Buffer.alloc(0), done = false;
      sock.on('error', () => { /* */ });
      const route = (acme) => {
        if (done) return; done = true; clearTimeout(timer); sock.removeListener('data', onData); sock.pause();
        if (acme && ACME_PORT) {
          const up = net.connect(ACME_PORT, '127.0.0.1', () => { up.write(buf); sock.pipe(up); up.pipe(sock); sock.resume(); });
          up.on('error', () => sock.destroy()); sock.on('close', () => up.destroy());
          return;
        }
        serveTls(sock, buf);
      };
      const onData = (d) => {
        buf = Buffer.concat([buf, d]);
        if (buf.length < 5) return;
        if (buf[0] !== 0x16) return route(false);
        if (buf.length >= 5 + buf.readUInt16BE(3) || buf.length > 16384) route(isAcmeHello(buf));
      };
      const timer = setTimeout(() => route(false), 4000);
      sock.on('data', onData);
    });
    front.on('error', (e) => console.log('wss port error:', e.message));
    front.listen(TLS_PORT, () => console.log('ballio wss on :' + TLS_PORT + (ACME_PORT ? ' (acme → ' + ACME_PORT + ')' : '')));
    let certM = 0; try { certM = fs.statSync(TLS_CERT).mtimeMs; } catch (e) { /* */ }
    setInterval(() => {
      try { const m = fs.statSync(TLS_CERT).mtimeMs; if (m !== certM) { certM = m; secureContext = tls.createSecureContext(opts()); readUntil(); console.log('tls cert reloaded, until', tlsUntil); } } catch (e) { console.log('tls reload failed', e.message); }
    }, 5 * 60 * 1000);
  } catch (e) { console.log('tls off:', e.message); }
}

// ---------------- Игровой цикл ----------------
// ошибка в одном сообщении или комнате не должна ронять весь сервер (раньше падал целиком — у всех обрыв)
const errAt = new Map();
function logErr(where, e) { const now = Date.now(); if (now - (errAt.get(where) || 0) < 60000) return; errAt.set(where, now); console.error(new Date().toISOString(), where, e && e.stack ? e.stack.split('\n').slice(0, 3).join(' | ') : e); }
// шарик с испорченными числами (NaN/бесконечность) — возвращаем на арену
function heal(r) {
  for (const b of r.balls.values()) {
    if (![b.x, b.y, b.m, b.r, b.vx, b.vy].every(Number.isFinite)) {
      const q = randIn(r.R * 0.5); Object.assign(b, { x: q.x, y: q.y, cx: q.x, cy: q.y, vx: 0, vy: 0, m: 18 }); b.r = rOf(b.m);
    }
  }
}
let last = Date.now();
setInterval(() => {
  const now = Date.now(), dt = Math.min(0.1, (now - last) / 1000); last = now;
  for (const r of rooms.values()) {
    if (!r.clients.size) { r.emptyT += dt; if (r.emptyT > 120) rooms.delete(r.name); continue; }
    r.emptyT = 0;
    try { step(r, dt); if (++r.tickN % 2 === 0) broadcast(r); if (r.tickN % 30 === 0) heal(r); } catch (e) { logErr('tick ' + r.name, e); heal(r); }
  }
}, 1000 / 30);
// «зависшие» подключения (телефон уснул, связь пропала) закрываем через 12 с тишины — место освобождается
setInterval(() => { const now = Date.now(); for (const ws of allWs) if (now - ws.lastT > 12000) ws.close(); }, 2000);

// обновился файл — перезапускаемся (systemd поднимет новую версию)
const WATCH = process.env.WATCH || __filename;
let myMtime = 0; try { myMtime = fs.statSync(WATCH).mtimeMs; } catch (e) { /* */ }
setInterval(() => { try { const t = fs.statSync(WATCH).mtimeMs; if (myMtime && t !== myMtime) { console.log('code updated, restarting'); saveDay(); process.exit(0); } } catch (e) { /* */ } }, 5000);

process.on('SIGTERM', () => { saveDay(); process.exit(0); });
