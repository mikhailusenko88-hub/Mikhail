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
const VERSION = '1.2';
const ROUND_LEN = +process.env.ROUND_LEN || 180; // раунд стран, секунд
const MAX_ACC = 12;                               // номера украшений (шапки, очки…)
const STATE_FILE = process.env.STATE_FILE || path.join(os.tmpdir(), 'ballio-day.json');
// грубые слова в никах заменяем на «Player» (ник видят все игроки)
const BAD = /(fuck|shit|bitch|cunt|nigg|fag|dick|porn|hitler|nazi|хуй|хуе|хуё|пизд|ебл|ебa|еба|ёба|бляд|блят|сука|мудак|пидор|пидр|залуп|гандон|шлюх|чмо)/i;
const FLAGS = ['RU', 'KZ', 'UZ', 'KG', 'UA', 'BY', 'TR', 'US', 'GB', 'DE', 'FR', 'IT', 'ES', 'PT', 'BR', 'AR', 'MX', 'CN', 'JP', 'KR', 'IN', 'ID', 'VN', 'TH'];
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
      if (op === 1 && ws.onmsg) { let m = null; try { m = JSON.parse(payload.toString('utf8')); } catch (e) { continue; } if (m && typeof m === 'object') ws.onmsg(m); }
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
const rooms = new Map();
function getRoom(name) {
  let r = rooms.get(name);
  if (!r) { r = { name, R: 1180, balls: new Map(), dots: new Map(), powers: new Map(), saws: [], clients: new Set(), nid: 1, did: 1, pid: 1, powT: 0, dAdd: [], dDel: [], ev: [], meta: [], tickN: 0, emptyT: 0, rT: ROUND_LEN, sc: {} }; rooms.set(name, r); }
  return r;
}
function humans(r) { let n = 0; for (const b of r.balls.values()) if (b.human) n++; return n; }
function addDot(r, x, y) { if (x === undefined) { const p = randIn(r.R * 0.97); x = p.x; y = p.y; } const d = { id: r.did++, x: Math.round(x), y: Math.round(y), c: (Math.random() * 8) | 0 }; r.dots.set(d.id, d); r.dAdd.push([d.id, d.x, d.y, d.c]); }
const metaOf = (b) => [b.id, b.name, b.skin, b.human ? 1 : 0, b.acc | 0];
function newBall(r, o) {
  const b = Object.assign({ id: r.nid++, x: 0, y: 0, vx: 0, vy: 0, m: 10, alive: true, shield: 0, boost: 0, magnet: 0, sawCD: 0, tx: 0, ty: 0, aiT: 0, flee: false, respawnT: 0, human: false, name: '', skin: 'US', acc: 0, ws: null, cx: 0, cy: 0, lastM: 0, diedAt: 0, reviveAt: -1e12 }, o);
  b.r = rOf(b.m); b.cx = b.x; b.cy = b.y; r.balls.set(b.id, b); r.meta.push(metaOf(b)); return b;
}
// масса, набранная шариком, идёт в зачёт его стране: живым игрокам целиком, ботам — меньше
function gain(r, b, amt) {
  b.m += amt; b.r = rOf(b.m);
  r.sc[b.skin] = (r.sc[b.skin] || 0) + amt * (b.human ? 1 : 0.4);
  if (b.human) { checkDay(); day.pts[b.skin] = (day.pts[b.skin] || 0) + amt; }
}
const roundTop = (r, n) => Object.entries(r.sc).sort((a, b) => b[1] - a[1]).slice(0, n).map(([f, p]) => [f, Math.round(p)]);
function endRound(r) {
  const top = roundTop(r, 5);
  if (top.length) { checkDay(); day.wins[top[0][0]] = (day.wins[top[0][0]] || 0) + 1; }
  const msg = JSON.stringify({ t: 'rw', win: top.length ? top[0][0] : '', top, day: dayTop(10) });
  for (const ws of r.clients) ws.send(msg);
  r.sc = {}; r.rT = ROUND_LEN; saveDay();
}
function cleanName(s, fallback) {
  let n = String(s || '').replace(/[<>&"'`\u0000-\u001f]/g, '').trim().slice(0, 14);
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
  return best;
}
function freeSkin(r) { const used = new Set(); for (const b of r.balls.values()) used.add(b.skin); const free = FLAGS.filter((f) => !used.has(f)); const pool = free.length ? free : FLAGS; return pool[(Math.random() * pool.length) | 0]; }

function think(r, b) {
  let threat = null, td = 1e9, prey = null, pd = 1e9;
  for (const o of r.balls.values()) {
    if (o === b || !o.alive) continue;
    const d = Math.hypot(o.x - b.x, o.y - b.y) - o.r - b.r;
    if (o.r > b.r * 1.12 && d < 260 + o.r && d < td) { threat = o; td = d; }
    if (b.r > o.r * 1.3 && d < (o.human ? 240 : 380) && d < pd && o.shield <= 0 && !(o.human && b.lazyHuman)) { prey = o; pd = d; }
  }
  // большим ботам пилы опасны — объезжают
  if (b.r > SAW_R * 1.15) for (const s of r.saws) { const d = Math.hypot(s.x - b.x, s.y - b.y) - SAW_R - b.r; if (d < 120 && d < td) { threat = s; td = d; } }
  b.flee = false;
  if (threat && (!prey || td < pd * 0.7)) { const a = Math.atan2(b.y - threat.y, b.x - threat.x) + (Math.random() - 0.5) * 0.6; b.tx = b.x + Math.cos(a) * 400; b.ty = b.y + Math.sin(a) * 400; b.flee = true; return; }
  if (prey && Math.random() > 0.12) { b.tx = prey.x + prey.vx * 0.3; b.ty = prey.y + prey.vy * 0.3; return; }
  // бонус рядом — заберёт
  for (const p of r.powers.values()) if (Math.hypot(p.x - b.x, p.y - b.y) < 350 && Math.random() < 0.6) { b.tx = p.x; b.ty = p.y; return; }
  if (Math.random() < 0.15) { const q = randIn(r.R * 0.8); b.tx = q.x; b.ty = q.y; return; }
  let best = null, bd = 1e9; const n = r.dots.size;
  if (n) { const arr = Array.from(r.dots.values()); for (let i = 0; i < 40; i++) { const p = arr[(Math.random() * n) | 0]; const d = Math.hypot(p.x - b.x, p.y - b.y); if (d < bd) { bd = d; best = p; } } }
  if (best) { b.tx = best.x; b.ty = best.y; }
}

function step(r, dt) {
  const nh = humans(r);
  // каждый новый живой игрок — арена заметно больше; ботов меньше, но не меньше 6
  r.R += (900 + 280 * Math.max(1, nh) - r.R) * Math.min(1, dt * 0.5);
  const wantBots = Math.max(6, 12 - nh);
  const bots = []; for (const b of r.balls.values()) if (!b.human) bots.push(b);
  if (bots.length < wantBots) { const q = safeSpot(r); newBall(r, { x: q.x, y: q.y, m: rnd(4, 18), skin: freeSkin(r), acc: Math.random() < 0.3 ? 1 + ((Math.random() * 11) | 0) : 0 }); }
  else if (bots.length > wantBots) { bots.sort((a, c) => (a.alive - c.alive) || (a.m - c.m)); const b = bots[0]; r.balls.delete(b.id); r.ev.push([0, b.id, 2]); }
  const wantDots = Math.round(r.R * r.R * 0.00024);
  for (let i = 0; i < 12 && r.dots.size < wantDots; i++) addDot(r);
  // пилы ездят по кругам; их больше, когда игроков больше
  const wantSaws = 3 + nh;
  while (r.saws.length < wantSaws) r.saws.push(newSaw(r));
  if (r.saws.length > wantSaws) r.saws.length = wantSaws;
  for (const s of r.saws) { s.a += s.w * dt; s.x = Math.cos(s.a) * s.or; s.y = Math.sin(s.a) * s.or; }
  // бонусы: 0 — ускорение, 1 — магнит, 2 — щит
  r.powT -= dt;
  r.rT -= dt; if (r.rT <= 0) endRound(r);
  if (r.powT <= 0 && r.powers.size < 4 + 2 * nh) { r.powT = 2.5; const q = randIn(r.R * 0.85), p = { id: r.pid++, x: Math.round(q.x), y: Math.round(q.y), k: (Math.random() * 3) | 0 }; r.powers.set(p.id, p); }

  for (const b of r.balls.values()) {
    if (!b.alive) {
      if (!b.human) { b.respawnT -= dt; if (b.respawnT <= 0) { const q = safeSpot(r); Object.assign(b, { x: q.x, y: q.y, vx: 0, vy: 0, m: rnd(4, 16), alive: true, shield: 0, boost: 0, magnet: 0 }); b.r = rOf(b.m); } }
      continue;
    }
    b.shield = Math.max(0, b.shield - dt); b.boost = Math.max(0, b.boost - dt); b.magnet = Math.max(0, b.magnet - dt); b.sawCD = Math.max(0, b.sawCD - dt);
    const bk = b.boost > 0 ? 1.6 : 1;
    if (b.human) {
      // положение присылает игрок; сервер подтягивается к нему, но не быстрее, чем шарик может катиться
      let dx = b.cx - b.x, dy = b.cy - b.y; const d = Math.hypot(dx, dy), max = speedOf(b.r) * bk * 1.7 * dt + 3;
      if (d > 320 * bk) { b.cx = b.x; b.cy = b.y; dx = 0; dy = 0; if (b.ws) b.ws.send({ t: 'fix', x: Math.round(b.x), y: Math.round(b.y) }); }
      else if (d > max) { dx *= max / d; dy *= max / d; }
      b.vx = dx / dt; b.vy = dy / dt; b.x += dx; b.y += dy;
    } else {
      b.aiT -= dt; if (b.aiT <= 0) { b.aiT = 0.25 + Math.random() * 0.2; b.lazyHuman = Math.random() < 0.45; think(r, b); }
      const vx = b.tx - b.x, vy = b.ty - b.y, d = Math.hypot(vx, vy) || 1, pw = d > 20 ? 1 : 0.3;
      const sp = speedOf(b.r) * (b.flee ? 0.76 : 0.85) * bk, k = Math.min(1, dt * 10);
      b.vx += ((vx / d) * sp * pw - b.vx) * k; b.vy += ((vy / d) * sp * pw - b.vy) * k;
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
    if (a === b || !a.alive || !b.alive || b.shield > 0) continue;
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
  const o = { t: 's', R: Math.round(r.R), b, da: r.dAdd, dd: r.dDel, ev: r.ev, mt: r.meta, pw, sw };
  if (r.tickN % 30 === 0) { o.cs = roundTop(r, 5); o.rt = Math.ceil(r.rT); }
  const msg = JSON.stringify(o);
  r.dAdd = []; r.dDel = []; r.ev = []; r.meta = [];
  for (const ws of r.clients) ws.send(msg);
}

function join(ws, m) {
  if (ws.room) return;
  const roomName = String(m.room || 'main').replace(/[^a-z0-9_-]/gi, '').slice(0, 24) || 'main';
  const r = getRoom(roomName);
  if (r.clients.size >= 40) { ws.send({ t: 'full' }); ws.close(); return; }
  const name = cleanName(m.name, 'Player');
  const skin = FLAGS.indexOf(m.skin) >= 0 ? m.skin : 'US';
  const acc = Math.max(0, Math.min(MAX_ACC, m.acc | 0));
  // у ботов не должно быть того же флага, что у живого игрока
  for (const o of r.balls.values()) if (!o.human && o.skin === skin) { o.skin = freeSkin(r); if (o.skin === skin) o.skin = FLAGS[(FLAGS.indexOf(skin) + 7) % FLAGS.length]; r.meta.push(metaOf(o)); }
  if (!r.dots.size) for (let i = 0; i < 300; i++) addDot(r);
  const q = safeSpot(r);
  const b = newBall(r, { x: q.x, y: q.y, m: 18, human: true, name, skin, acc, ws, shield: 4 });
  ws.room = r; ws.ball = b; r.clients.add(ws);
  const meta = []; for (const x of r.balls.values()) meta.push(metaOf(x));
  const dots = []; for (const d of r.dots.values()) dots.push([d.id, d.x, d.y, d.c]);
  ws.send({ t: 'w', id: b.id, x: Math.round(b.x), y: Math.round(b.y), R: Math.round(r.R), mt: meta, dots, v: VERSION, cs: roundTop(r, 5), rt: Math.ceil(r.rT), rl: ROUND_LEN, day: dayTop(10) });
}

function respawn(ws, m) {
  const b = ws.ball, r = ws.room; if (!b || !r) return;
  if (!b.alive) {
    // смена страны / ника / украшения — между жизнями
    if (m && FLAGS.indexOf(m.skin) >= 0) b.skin = m.skin;
    if (m && m.name) b.name = cleanName(m.name, b.name);
    if (m && m.acc !== undefined) b.acc = Math.max(0, Math.min(MAX_ACC, m.acc | 0));
    r.meta.push(metaOf(b));
    // возрождение за рекламу или монеты: половина массы, не чаще раза в 200 с и только сразу после смерти
    let mass = 18; const now = Date.now();
    if (m && m.keep && b.lastM > 36 && now - b.diedAt < 120000 && now - b.reviveAt > 200000) { mass = Math.min(400, b.lastM * 0.5); b.reviveAt = now; }
    const q = safeSpot(r); Object.assign(b, { x: q.x, y: q.y, cx: q.x, cy: q.y, vx: 0, vy: 0, m: mass, alive: true, shield: 4, boost: 0, magnet: 0 }); b.r = rOf(b.m);
  }
  ws.send({ t: 'fix', x: Math.round(b.x), y: Math.round(b.y), re: 1, m: Math.round(b.m * 10) / 10 });
}

function onMsg(ws, m) {
  if (m.t === 'hello') return join(ws, m);
  const b = ws.ball; if (!b) return;
  if (m.t === 'p') { const x = +m.x, y = +m.y; if (isFinite(x) && isFinite(y)) { b.cx = x; b.cy = y; } return; }
  if (m.t === 're') return respawn(ws, m);
  if (m.t === 'dbg' && process.env.TEST === '1' && ws.ball) { const b = ws.ball; if (m.m) { b.m = +m.m; b.r = rOf(b.m); } if (m.x !== undefined) { b.x = b.cx = +m.x; b.y = b.cy = +m.y; ws.send({ t: 'fix', x: b.x, y: b.y }); } return; }
  if (m.t === 'ping') ws.send({ t: 'pong', c: m.c });
}
function onClose(ws) {
  const r = ws.room; if (!r) return;
  r.clients.delete(ws);
  if (ws.ball) { r.balls.delete(ws.ball.id); r.ev.push([0, ws.ball.id, 2]); }
}

// ---------------- HTTP ----------------
const perIp = new Map();
const allWs = new Set();
function httpHandler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.url.indexOf('/health') === 0) {
    let h = 0; for (const r of rooms.values()) h += r.clients.size;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.end(JSON.stringify({ ok: 1, v: VERSION, rooms: rooms.size, players: h, sockets: allWs.size }));
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
// Включается, только если есть сертификат: TLS_CERT / TLS_KEY. Сертификат на IP живёт ~6 дней,
// поэтому файл перечитываем каждые 6 часов без перезапуска.
const TLS_CERT = process.env.TLS_CERT || '', TLS_KEY = process.env.TLS_KEY || '', TLS_PORT = +process.env.TLS_PORT || 8443;
if (TLS_CERT && TLS_KEY) {
  try {
    const https = require('https');
    const opts = () => ({ cert: fs.readFileSync(TLS_CERT), key: fs.readFileSync(TLS_KEY) });
    const tlsServer = https.createServer(opts(), httpHandler);
    tlsServer.on('upgrade', onUpgrade);
    tlsServer.on('tlsClientError', () => { /* сканеры и обрывы — не шумим */ });
    tlsServer.listen(TLS_PORT, () => console.log('ballio wss on :' + TLS_PORT));
    setInterval(() => { try { tlsServer.setSecureContext(opts()); } catch (e) { console.log('tls reload failed', e.message); } }, 6 * 3600 * 1000);
  } catch (e) { console.log('tls off:', e.message); }
}

// ---------------- Игровой цикл ----------------
let last = Date.now();
setInterval(() => {
  const now = Date.now(), dt = Math.min(0.1, (now - last) / 1000); last = now;
  for (const r of rooms.values()) {
    if (!r.clients.size) { r.emptyT += dt; if (r.emptyT > 120) rooms.delete(r.name); continue; }
    r.emptyT = 0;
    step(r, dt);
    if (++r.tickN % 2 === 0) broadcast(r);
  }
}, 1000 / 30);
// «зависшие» подключения (телефон уснул, связь пропала) закрываем через 12 с тишины — место освобождается
setInterval(() => { const now = Date.now(); for (const ws of allWs) if (now - ws.lastT > 12000) ws.close(); }, 2000);

// обновился файл — перезапускаемся (systemd поднимет новую версию)
const WATCH = process.env.WATCH || __filename;
let myMtime = 0; try { myMtime = fs.statSync(WATCH).mtimeMs; } catch (e) { /* */ }
setInterval(() => { try { const t = fs.statSync(WATCH).mtimeMs; if (myMtime && t !== myMtime) { console.log('code updated, restarting'); saveDay(); process.exit(0); } } catch (e) { /* */ } }, 5000);

process.on('SIGTERM', () => { saveDay(); process.exit(0); });
