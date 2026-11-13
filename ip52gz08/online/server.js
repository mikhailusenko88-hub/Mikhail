'use strict';
/*
  Онлайн-арена «Шарики.io» — сервер.
  Один процесс Node.js без внешних библиотек: HTTP + WebSocket (RFC 6455) на одном порту (по умолчанию 8091).
  Сервер считает всю арену: ботов, точки, кто кого съел. Игрок присылает своё положение,
  сервер проверяет, что он не «телепортируется», и рассылает состояние всем 15 раз в секунду.
  Живых игроков больше — ботов меньше, а арена растёт.
  Если файл этого скрипта обновился — процесс сам завершается, systemd запускает новую версию.
*/
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');

const PORT = +process.env.PORT || 8091;
const VERSION = '1.0';
const FLAGS = ['RU', 'KZ', 'UZ', 'KG', 'UA', 'BY', 'TR', 'US', 'GB', 'DE', 'FR', 'IT', 'ES', 'PT', 'BR', 'AR', 'MX', 'CN', 'JP', 'KR', 'IN', 'ID', 'VN', 'TH'];
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
  const ws = { socket, buf: Buffer.alloc(0), onmsg: null, onclose: null, closed: false, ip: req.socket.remoteAddress };
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
      let payload = Buffer.from(ws.buf.slice(off, off + len));
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

// ---------------- Комнаты ----------------
const rooms = new Map();
function getRoom(name) { let r = rooms.get(name); if (!r) { r = { name, R: 1170, balls: new Map(), dots: new Map(), clients: new Set(), nid: 1, did: 1, dAdd: [], dDel: [], ev: [], meta: [], tickN: 0, emptyT: 0 }; rooms.set(name, r); } return r; }
function humans(r) { let n = 0; for (const b of r.balls.values()) if (b.human) n++; return n; }
function addDot(r) { const p = randIn(r.R * 0.97); const d = { id: r.did++, x: Math.round(p.x), y: Math.round(p.y), c: (Math.random() * 8) | 0 }; r.dots.set(d.id, d); r.dAdd.push([d.id, d.x, d.y, d.c]); }
function newBall(r, o) {
  const b = Object.assign({ id: r.nid++, x: 0, y: 0, vx: 0, vy: 0, m: 10, alive: true, shield: 0, tx: 0, ty: 0, aiT: 0, flee: false, respawnT: 0, human: false, name: '', skin: 'US', ws: null, cx: 0, cy: 0 }, o);
  b.r = rOf(b.m); b.cx = b.x; b.cy = b.y; r.balls.set(b.id, b); r.meta.push([b.id, b.name, b.skin, b.human ? 1 : 0]); return b;
}
function safeSpot(r) {
  let best = null, bd = -1;
  for (let i = 0; i < 24; i++) { const q = randIn(r.R * 0.85); let md = 1e9; for (const o of r.balls.values()) if (o.alive) md = Math.min(md, Math.hypot(o.x - q.x, o.y - q.y) - o.r); if (md > bd) { bd = md; best = q; } }
  return best;
}
function freeSkin(r) { const used = new Set(); for (const b of r.balls.values()) used.add(b.skin); const free = FLAGS.filter((f) => !used.has(f)); const pool = free.length ? free : FLAGS; return pool[(Math.random() * pool.length) | 0]; }

function think(r, b) {
  let threat = null, td = 1e9, prey = null, pd = 1e9;
  for (const o of r.balls.values()) {
    if (o === b || !o.alive) continue;
    const d = Math.hypot(o.x - b.x, o.y - b.y) - o.r - b.r;
    if (o.r > b.r * 1.12 && d < 260 + o.r && d < td) { threat = o; td = d; }
    if (b.r > o.r * 1.3 && d < (o.human ? 300 : 380) && d < pd && o.shield <= 0) { prey = o; pd = d; }
  }
  b.flee = false;
  if (threat && (!prey || td < pd * 0.7)) { const a = Math.atan2(b.y - threat.y, b.x - threat.x) + (Math.random() - 0.5) * 0.6; b.tx = b.x + Math.cos(a) * 400; b.ty = b.y + Math.sin(a) * 400; b.flee = true; return; }
  if (prey && Math.random() > 0.12) { b.tx = prey.x + prey.vx * 0.3; b.ty = prey.y + prey.vy * 0.3; return; }
  if (Math.random() < 0.15) { const q = randIn(r.R * 0.8); b.tx = q.x; b.ty = q.y; return; }
  let best = null, bd = 1e9; const n = r.dots.size;
  if (n) { const arr = Array.from(r.dots.values()); for (let i = 0; i < 40; i++) { const p = arr[(Math.random() * n) | 0]; const d = Math.hypot(p.x - b.x, p.y - b.y); if (d < bd) { bd = d; best = p; } } }
  if (best) { b.tx = best.x; b.ty = best.y; }
}

function step(r, dt) {
  const nh = humans(r);
  // каждый новый живой игрок — арена чуть больше; ботов меньше, но не меньше 6
  r.R += (1000 + 170 * Math.max(1, nh) - r.R) * Math.min(1, dt * 0.4);
  const wantBots = Math.max(6, 12 - nh);
  const bots = []; for (const b of r.balls.values()) if (!b.human) bots.push(b);
  if (bots.length < wantBots) { const q = safeSpot(r); newBall(r, { x: q.x, y: q.y, m: rnd(4, 18), skin: freeSkin(r) }); }
  else if (bots.length > wantBots) { bots.sort((a, c) => (a.alive - c.alive) || (a.m - c.m)); const b = bots[0]; r.balls.delete(b.id); r.ev.push([0, b.id, 2]); }
  const wantDots = Math.round(r.R * r.R * 0.00024);
  for (let i = 0; i < 12 && r.dots.size < wantDots; i++) addDot(r);

  for (const b of r.balls.values()) {
    if (!b.alive) {
      if (!b.human) { b.respawnT -= dt; if (b.respawnT <= 0) { const q = safeSpot(r); Object.assign(b, { x: q.x, y: q.y, vx: 0, vy: 0, m: rnd(4, 16), alive: true, shield: 0 }); b.r = rOf(b.m); } }
      continue;
    }
    b.shield = Math.max(0, b.shield - dt);
    if (b.human) {
      // положение присылает игрок; сервер подтягивается к нему, но не быстрее, чем шарик может катиться
      let dx = b.cx - b.x, dy = b.cy - b.y; const d = Math.hypot(dx, dy), max = speedOf(b.r) * 1.7 * dt + 3;
      if (d > 320) { b.cx = b.x; b.cy = b.y; dx = 0; dy = 0; if (b.ws) b.ws.send({ t: 'fix', x: Math.round(b.x), y: Math.round(b.y) }); }
      else if (d > max) { dx *= max / d; dy *= max / d; }
      b.vx = dx / dt; b.vy = dy / dt; b.x += dx; b.y += dy;
    } else {
      b.aiT -= dt; if (b.aiT <= 0) { b.aiT = 0.25 + Math.random() * 0.2; think(r, b); }
      const vx = b.tx - b.x, vy = b.ty - b.y, d = Math.hypot(vx, vy) || 1, pw = d > 20 ? 1 : 0.3;
      const sp = speedOf(b.r) * (b.flee ? 0.76 : 0.85), k = Math.min(1, dt * 10);
      b.vx += ((vx / d) * sp * pw - b.vx) * k; b.vy += ((vy / d) * sp * pw - b.vy) * k;
      b.x += b.vx * dt; b.y += b.vy * dt;
    }
    const dd = Math.hypot(b.x, b.y), lim = r.R - b.r * 0.6; if (dd > lim) { b.x *= lim / dd; b.y *= lim / dd; }
    // очень большие понемногу худеют (боты — заметнее), чтобы арену не захватывали боты и не было вечного чемпиона
    if (!b.human && b.m > 60) { b.m -= b.m * 0.012 * dt; b.r = rOf(b.m); }
    else if (b.m > 150) { b.m -= b.m * 0.003 * dt; b.r = rOf(b.m); }
  }
  // точки
  for (const b of r.balls.values()) {
    if (!b.alive) continue;
    const rr = b.r * b.r;
    for (const d of r.dots.values()) { const dx = d.x - b.x, dy = d.y - b.y; if (dx * dx + dy * dy < rr) { r.dots.delete(d.id); r.dDel.push(d.id); b.m += 1; b.r = rOf(b.m); } }
  }
  // кто кого съел
  const arr = []; for (const b of r.balls.values()) if (b.alive) arr.push(b);
  for (const a of arr) for (const b of arr) {
    if (a === b || !a.alive || !b.alive || b.shield > 0) continue;
    if (a.r > b.r * 1.12 && Math.hypot(a.x - b.x, a.y - b.y) < a.r - b.r * 0.15) {
      b.alive = false; a.m += b.m * 0.85; a.r = rOf(a.m); r.ev.push([a.id, b.id, 1]);
      if (b.human) { if (b.ws) b.ws.send({ t: 'dead', by: a.id, m: Math.round(b.m) }); }
      else b.respawnT = rnd(3, 6);
    }
  }
}

function broadcast(r) {
  const b = [];
  for (const x of r.balls.values()) b.push([x.id, Math.round(x.x), Math.round(x.y), Math.round(x.m * 10), x.alive ? 1 : 0, x.shield > 0 ? 1 : 0]);
  const msg = JSON.stringify({ t: 's', R: Math.round(r.R), b, da: r.dAdd, dd: r.dDel, ev: r.ev, mt: r.meta });
  r.dAdd = []; r.dDel = []; r.ev = []; r.meta = [];
  for (const ws of r.clients) ws.send(msg);
}

function join(ws, m) {
  if (ws.room) return;
  const roomName = String(m.room || 'main').replace(/[^a-z0-9_-]/gi, '').slice(0, 24) || 'main';
  const r = getRoom(roomName);
  if (r.clients.size >= 30) { ws.send({ t: 'full' }); ws.close(); return; }
  const name = String(m.name || '').replace(/[<>&"'`]/g, '').trim().slice(0, 14) || 'Игрок';
  const skin = FLAGS.indexOf(m.skin) >= 0 ? m.skin : 'RU';
  // у ботов не должно быть того же флага, что у живого игрока
  for (const o of r.balls.values()) if (!o.human && o.skin === skin) { o.skin = freeSkin(r); if (o.skin === skin) o.skin = FLAGS[(FLAGS.indexOf(skin) + 7) % FLAGS.length]; r.meta.push([o.id, o.name, o.skin, 0]); }
  // первому в комнате — честный старт: пусть точки и боты будут на месте
  if (!r.dots.size) for (let i = 0; i < 300; i++) addDot(r);
  const q = safeSpot(r);
  const b = newBall(r, { x: q.x, y: q.y, m: 10, human: true, name, skin, ws, shield: 3 });
  ws.room = r; ws.ball = b; r.clients.add(ws);
  const meta = []; for (const x of r.balls.values()) meta.push([x.id, x.name, x.skin, x.human ? 1 : 0]);
  const dots = []; for (const d of r.dots.values()) dots.push([d.id, d.x, d.y, d.c]);
  ws.send({ t: 'w', id: b.id, x: Math.round(b.x), y: Math.round(b.y), R: Math.round(r.R), mt: meta, dots, v: VERSION });
}

function onMsg(ws, m) {
  if (m.t === 'hello') return join(ws, m);
  const b = ws.ball; if (!b) return;
  if (m.t === 'p') { const x = +m.x, y = +m.y; if (isFinite(x) && isFinite(y)) { b.cx = x; b.cy = y; } return; }
  if (m.t === 're' && !b.alive) { const r = ws.room, q = safeSpot(r); Object.assign(b, { x: q.x, y: q.y, cx: q.x, cy: q.y, vx: 0, vy: 0, m: 10, alive: true, shield: 3 }); b.r = rOf(b.m); ws.send({ t: 'fix', x: Math.round(b.x), y: Math.round(b.y), re: 1 }); return; }
  if (m.t === 'ping') ws.send({ t: 'pong', c: m.c });
}
function onClose(ws) {
  const r = ws.room; if (!r) return;
  r.clients.delete(ws);
  if (ws.ball) { r.balls.delete(ws.ball.id); r.ev.push([0, ws.ball.id, 2]); }
}

// ---------------- HTTP ----------------
const perIp = new Map();
const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.url.indexOf('/health') === 0) {
    let h = 0; for (const r of rooms.values()) h += r.clients.size;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.end(JSON.stringify({ ok: 1, v: VERSION, rooms: rooms.size, players: h }));
    return;
  }
  res.statusCode = 404; res.end('ballio');
});
server.on('upgrade', (req, socket) => {
  if (req.url.indexOf('/ws') !== 0) { socket.destroy(); return; }
  const ip = req.socket.remoteAddress || '';
  const n = perIp.get(ip) || 0; if (n >= 12) { socket.destroy(); return; }
  const ws = wsAccept(req, socket); if (!ws) return;
  perIp.set(ip, n + 1);
  ws.onmsg = (m) => onMsg(ws, m);
  ws.onclose = () => { perIp.set(ip, Math.max(0, (perIp.get(ip) || 1) - 1)); onClose(ws); };
});
server.listen(PORT, () => console.log('ballio ' + VERSION + ' on :' + PORT));

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

// обновился файл — перезапускаемся (systemd поднимет новую версию)
const WATCH = process.env.WATCH || __filename;
let myMtime = 0; try { myMtime = fs.statSync(WATCH).mtimeMs; } catch (e) { /* */ }
setInterval(() => { try { const t = fs.statSync(WATCH).mtimeMs; if (myMtime && t !== myMtime) { console.log('code updated, restarting'); process.exit(0); } } catch (e) { /* */ } }, 5000);
