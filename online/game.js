'use strict';
/* «Шарики.io — онлайн»: та же арена, но вместе с живыми игроками. Сервер считает ботов, точки, бонусы, пилы и кто кого съел;
   свой шарик двигается сразу на телефоне (без задержки), а сервер только проверяет его. */
(function () {
  const C = window.Core;
  const q = new URLSearchParams(location.search);
  const SERVER = q.get('server') || ((location.protocol === 'https:' ? 'wss://' : 'ws://') + (location.hostname || 'localhost') + ':8091/ws');
  const ROOM = (q.get('room') || 'main').replace(/[^a-z0-9_-]/gi, '').slice(0, 24) || 'main';
  const steer = { x: 0, y: 0, on: false };
  const LEASH = 26, DEAD = 7, TURN = 10, SAW_R = 50;
  const PCOL = ['#ff5252', '#ffca28', '#69f0ae', '#40c4ff', '#e040fb', '#ff9100', '#b2ff59', '#18ffff'];
  const POW = [{ icon: 'bolt', col: '#ffd600' }, { icon: 'magnet', col: '#ff4081' }, { icon: 'shield', col: '#40c4ff' }];
  const PREY = '#00e676', DANGER = '#ff1744';
  const rOf = (m) => 20 + 5 * Math.sqrt(m);
  const speedOf = (r) => 440 * Math.pow(40 / r, 0.32);
  const TX = {
    ru: { conn: 'Подключаюсь к арене…', att: 'попытка', slow: 'Долго? Проверь интернет или переключись Wi-Fi ↔ мобильный', ateBy: 'Тебя съел', again: 'Заново', players: 'Игроков', grow: 'Арена растёт!', joined: 'в игре', left: 'вышел', bolt: 'Ускорение!', magnet: 'Магнит!', shield: 'Щит!' },
    en: { conn: 'Connecting to the arena…', att: 'try', slow: 'Taking long? Check the internet or switch Wi-Fi / mobile', ateBy: 'You were eaten by', again: 'Play again', players: 'Players', grow: 'The arena grows!', joined: 'joined', left: 'left', bolt: 'Speed!', magnet: 'Magnet!', shield: 'Shield!' },
  };
  const T = TX[(C.lang || 'en').slice(0, 2)] || TX.en;

  let ws = null, status = 'idle', lostT = 0, connT = 0, attempt = 0, lastMsgT = 0, myId = 0, R = 1200, Rshow = 1200, joined = false, nick = '', skin = 'RU';
  const balls = new Map(), dots = new Map(), knownHumans = new Set();
  let powers = [], saws = [], sawSpin = 0;
  let me = { x: 0, y: 0, vx: 0, vy: 0, r: rOf(10), m: 10, alive: false, shield: 0, boost: 0, magnet: 0, ang: 0 };
  let cam = { x: 0, y: 0, z: 1 }, joy = null, feed = [], floats = [], toasts = [], dead = null, sendT = 0, pingMs = 0, pingT = 0, best = 10, growFx = 0, reT = 0;

  const nowS = () => performance.now() / 1000;
  function connect() {
    if (ws) { const o = ws; ws = null; o.onclose = null; o.onmessage = null; try { o.close(); } catch (e) { /* */ } }
    status = 'conn'; connT = 0; attempt++;
    let sock; try { sock = new WebSocket(SERVER); } catch (e) { status = 'lost'; lostT = 0; return; }
    ws = sock;
    sock.onopen = () => { if (ws === sock) sock.send(JSON.stringify({ t: 'hello', name: nick, skin, room: ROOM })); };
    sock.onmessage = (e) => { if (ws !== sock) return; lastMsgT = nowS(); let m; try { m = JSON.parse(e.data); } catch (er) { return; } onMsg(m); };
    sock.onclose = () => { if (ws !== sock) return; status = 'lost'; lostT = 0; };
    sock.onerror = () => { /* onclose сработает */ };
  }
  function send(o) { if (ws && ws.readyState === 1) { try { ws.send(JSON.stringify(o)); } catch (e) { /* */ } } }
  // телефон проснулся / вернулись во вкладку — если сервер давно молчит, переподключаемся сразу
  document.addEventListener('visibilitychange', () => { if (!document.hidden && joined && nowS() - lastMsgT > 2) connect(); });

  function setMeta(list) {
    for (const [id, name, sk, hum] of list) {
      let b = balls.get(id); if (!b) { b = mkB(id); balls.set(id, b); }
      b.name = name; b.skin = sk; b.human = !!hum;
      if (hum && !knownHumans.has(id)) { knownHumans.add(id); if (id !== myId && myId) toasts.push({ text: name + ' ' + T.joined + ' · ' + T.grow, t: 0, col: '#69f0ae' }); }
    }
  }
  function mkB(id) { return { id, x: 0, y: 0, sx: 0, sy: 0, pvx: 0, pvy: 0, st: 0, m: 10, r: rOf(10), alive: false, fl: 0, name: '', skin: 'US', human: false, ang: 0, fresh: true }; }

  function onMsg(m) {
    const now = nowS();
    if (m.t === 'w') {
      status = 'ok'; attempt = 0; myId = m.id; R = m.R; Rshow = m.R; balls.clear(); dots.clear(); knownHumans.clear();
      setMeta(m.mt);
      for (const [id, x, y, c] of m.dots) dots.set(id, { x, y, c: PCOL[c], r: 9 + (id % 5) });
      me = { x: m.x, y: m.y, vx: 0, vy: 0, r: rOf(18), m: 18, alive: true, shield: 4, boost: 0, magnet: 0, ang: 0 }; dead = null; best = 10; reT = 0;
      cam.x = me.x; cam.y = me.y; steer.on = false;
      return;
    }
    if (m.t === 's') {
      if (m.R > R + 30) growFx = 2.2;
      R = m.R;
      if (m.mt && m.mt.length) setMeta(m.mt);
      const seen = new Set();
      for (const [id, x, y, m10, al, fl] of m.b) {
        seen.add(id);
        let b = balls.get(id); if (!b) { b = mkB(id); balls.set(id, b); }
        const dts = Math.max(0.03, now - b.st);
        if (al && b.alive && !b.fresh) { b.pvx = C.clamp((x - b.sx) / dts, -1400, 1400); b.pvy = C.clamp((y - b.sy) / dts, -1400, 1400); }
        else { b.x = x; b.y = y; b.pvx = 0; b.pvy = 0; }
        b.fresh = false; b.sx = x; b.sy = y; b.st = now; b.m = m10 / 10; b.r = rOf(b.m); b.alive = !!al; b.fl = fl;
        if (id === myId) { me.m = b.m; me.r = b.r; me.shield = fl & 1; me.boost = fl & 2; me.magnet = fl & 4; if (al) best = Math.max(best, me.m); }
      }
      for (const id of Array.from(balls.keys())) if (!seen.has(id)) { const b = balls.get(id); if (b.human && id !== myId) toasts.push({ text: b.name + ' ' + T.left, t: 0, col: '#fff' }); balls.delete(id); }
      for (const [id, x, y, c] of m.da) dots.set(id, { x, y, c: PCOL[c], r: 9 + (id % 5) });
      for (const id of m.dd) dots.delete(id);
      if (m.pw) { const old = new Map(powers.map((p) => [p.id, p])); powers = m.pw.map(([id, x, y, k]) => ({ id, x, y, k, a: old.has(id) ? old.get(id).a : 0 })); }
      if (m.sw) { const prev = saws; saws = m.sw.map(([x, y], i) => ({ tx: x, ty: y, x: prev[i] ? prev[i].x : x, y: prev[i] ? prev[i].y : y })); }
      for (const [a, b, k] of m.ev) {
        if (k === 1) {
          const A = balls.get(a), B = balls.get(b);
          feed.unshift({ a: A ? A.skin : 'US', b: B ? B.skin : 'US', an: A && A.human ? A.name : '', bn: B && B.human ? B.name : '', t: 0, me: a === myId || b === myId }); feed.length = Math.min(feed.length, 4);
          if (a === myId && B) { C.sfx('pop'); floats.push({ x: me.x, y: me.y - me.r, text: '+' + Math.round(B.m * 0.85), t: 0, col: '#ffeb3b' }); C.burst(...toScr(B.x, B.y), '#ffd54f', 16, 380); }
          if (B && !B.alive) { B.eatenBy = a; B.eatK = 0; }
        } else if (k === 3) { // пила отрезала кусок
          const A = balls.get(a);
          if (a === myId) { C.sfx('crash', 0.6); floats.push({ x: me.x, y: me.y - me.r, text: '−' + b, t: 0, col: '#ff5252' }); C.burst(...toScr(me.x, me.y), '#b0bec5', 24, 520); }
          else if (A) C.burst(...toScr(A.x, A.y), '#b0bec5', 10, 300);
        } else if (k === 4 && a === myId) { // взял бонус
          C.sfx('buy'); const name = [T.bolt, T.magnet, T.shield][b] || ''; floats.push({ x: me.x, y: me.y - me.r - 20, text: name, t: 0, col: POW[b] ? POW[b].col : '#fff' });
        }
      }
      return;
    }
    if (m.t === 'fix') { me.x = m.x; me.y = m.y; me.vx = 0; me.vy = 0; if (m.re) { me.alive = true; me.m = 18; me.r = rOf(18); me.shield = 4; dead = null; best = 10; steer.on = false; reT = 0; cam.x = me.x; cam.y = me.y; } return; }
    if (m.t === 'dead') { me.alive = false; const k = balls.get(m.by); dead = { by: k ? (k.human ? k.name : k.skin) : '', skin: k ? k.skin : 'US', human: k && k.human, m: m.m, t: 0, killer: m.by }; C.sfx('crash', 0.6); return; }
    if (m.t === 'pong') { pingMs = Math.round(performance.now() - m.c); return; }
    if (m.t === 'full') { status = 'lost'; lostT = 0; return; }
  }

  function toScr(x, y) { return [(x - cam.x) * cam.z + C.W / 2, (y - cam.y) * cam.z + C.H / 2]; }
  const relOf = (b) => (!me.alive ? 0 : me.r > b.r * 1.12 ? 1 : b.r > me.r * 1.12 ? -1 : 0);
  function doRespawn() { if (reT > 0) return; send({ t: 're' }); reT = 1.6; }

  window.__join = (n, s) => { nick = n; skin = s; joined = true; try { localStorage.setItem('ballio_nick', n); localStorage.setItem('ballio_skin', s); } catch (e) { /* */ } connect(); };

  function drawSaw(ctx, x, y, r, spin, danger) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(spin);
    if (danger) { ctx.fillStyle = 'rgba(255,23,68,0.18)'; ctx.beginPath(); ctx.arc(0, 0, r * 1.35, 0, 7); ctx.fill(); }
    ctx.fillStyle = '#90a4ae'; ctx.strokeStyle = '#37474f'; ctx.lineWidth = 3; ctx.beginPath();
    const n = 16; for (let i = 0; i < n; i++) { const a0 = (i / n) * Math.PI * 2, a1 = ((i + 0.6) / n) * Math.PI * 2; ctx.lineTo(Math.cos(a0) * r * 0.82, Math.sin(a0) * r * 0.82); ctx.lineTo(Math.cos(a1) * r * 1.08, Math.sin(a1) * r * 1.08); }
    ctx.closePath(); ctx.fill(); ctx.stroke();
    const g = ctx.createRadialGradient(-r * 0.2, -r * 0.2, 2, 0, 0, r * 0.8); g.addColorStop(0, '#eceff1'); g.addColorStop(1, '#78909c');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r * 0.74, 0, 7); ctx.fill();
    ctx.fillStyle = '#455a64'; ctx.beginPath(); ctx.arc(0, 0, r * 0.2, 0, 7); ctx.fill();
    ctx.strokeStyle = 'rgba(55,71,79,0.6)'; ctx.lineWidth = 3; for (let i = 0; i < 3; i++) { const a = (i / 3) * Math.PI * 2; ctx.beginPath(); ctx.moveTo(Math.cos(a) * r * 0.28, Math.sin(a) * r * 0.28); ctx.lineTo(Math.cos(a) * r * 0.62, Math.sin(a) * r * 0.62); ctx.stroke(); }
    ctx.restore();
  }

  const game = {
    id: 'ballio_online', startState: 'play', noLevels: true, hasSkip: false, reviveIcon: null,
    init() {}, startLevel() {}, toHome() {}, revive() {},
    onDown(x, y) { if (dead && !me.alive) return; joy = { ax: x, ay: y, x, y, rx: 0, ry: 0 }; },
    onMove(x, y) {
      if (!joy) return;
      const mx = x - joy.x, my = y - joy.y, ml = Math.hypot(mx, my); joy.x = x; joy.y = y;
      if (ml < 0.01) return;
      if (steer.on) {
        if (mx * steer.x + my * steer.y < ml * 0.5) { joy.rx += mx; joy.ry += my; } else { joy.rx = 0; joy.ry = 0; }
        const rl = Math.hypot(joy.rx, joy.ry);
        if (rl > TURN && joy.rx * steer.x + joy.ry * steer.y < rl * 0.5) { steer.x = joy.rx / rl; steer.y = joy.ry / rl; joy.ax = x - steer.x * LEASH; joy.ay = y - steer.y * LEASH; joy.rx = joy.ry = 0; return; }
      }
      const vx = x - joy.ax, vy = y - joy.ay; let d = Math.hypot(vx, vy);
      if (d > LEASH) { joy.ax = x - (vx / d) * LEASH; joy.ay = y - (vy / d) * LEASH; d = LEASH; }
      if (d > DEAD) { const l = Math.hypot(vx, vy); steer.x = vx / l; steer.y = vy / l; steer.on = true; }
    },
    onUp() { joy = null; },
    onHover(x, y) {
      if (!me.alive) return;
      const [sx, sy] = toScr(me.x, me.y), vx = x - sx, vy = y - sy, d = Math.hypot(vx, vy);
      if (d > Math.max(16, me.r * cam.z * 0.4)) { steer.x = vx / d; steer.y = vy / d; steer.on = true; }
    },
    onKey(k, down) { if (down && (k === 'Space' || k === 'Enter') && dead && !me.alive && dead.t > 0.5) doRespawn(); },

    update(dt) {
      const now = nowS();
      for (const f of feed) f.t += dt; feed = feed.filter((f) => f.t < 3.5);
      for (const f of floats) f.t += dt; floats = floats.filter((f) => f.t < 1.1);
      for (const f of toasts) f.t += dt; toasts = toasts.filter((f) => f.t < 3); if (toasts.length > 3) toasts.splice(0, toasts.length - 3);
      growFx = Math.max(0, growFx - dt); Rshow += (R - Rshow) * Math.min(1, dt * 2);
      sawSpin += dt * 7; for (const p of powers) p.a += dt;
      for (const s of saws) { s.x += (s.tx - s.x) * Math.min(1, dt * 8); s.y += (s.ty - s.y) * Math.min(1, dt * 8); }
      if (dead) dead.t += dt;
      // связь: не дождались ответа — пробуем ещё; сервер замолчал — переподключаемся
      if (joined) {
        if (status === 'conn') { connT += dt; if (connT > 6) connect(); }
        else if (status === 'lost') { lostT += dt; if (lostT > 1.5) connect(); }
        else if (status === 'ok' && now - lastMsgT > 4) connect();
      }
      // «Заново» не сработало (связь подвисла) — заходим на арену заново
      if (reT > 0) { reT -= dt; if (reT <= 0 && !me.alive) connect(); }
      // свой шарик — сразу, без ожидания сервера
      if (me.alive && status === 'ok') {
        let dx = 0, dy = 0, pw = 0;
        if (steer.on) { dx = steer.x; dy = steer.y; pw = 1; }
        const kx = C.keyDir(), ky = C.keyDirY(); if (kx || ky) { const d = Math.hypot(kx, ky); dx = kx / d; dy = ky / d; pw = 1; }
        if (window.__bot) { const t = window.__bot(me, balls); dx = t[0]; dy = t[1]; pw = 1; }
        const sp = speedOf(me.r) * (me.boost ? 1.6 : 1), k = Math.min(1, dt * 30);
        me.vx += (dx * sp * pw - me.vx) * k; me.vy += (dy * sp * pw - me.vy) * k;
        me.x += me.vx * dt; me.y += me.vy * dt;
        const d = Math.hypot(me.x, me.y), lim = R - me.r * 0.6; if (d > lim) { me.x *= lim / d; me.y *= lim / d; }
        me.ang += (Math.hypot(me.vx, me.vy) / me.r) * dt * (me.vx >= 0 ? 1 : -1);
        // точки под своим шариком (и в радиусе магнита) прячем сразу — сервер подтвердит
        const pr = me.magnet ? me.r + 170 : me.r, rr = pr * pr;
        for (const p of dots.values()) { const ax = p.x - me.x, ay = p.y - me.y; if (ax * ax + ay * ay < rr && !p.hid) { p.hid = true; if (Math.random() < 0.25) C.sfx('coin'); } }
        sendT -= dt; if (sendT <= 0) { sendT = 0.05; send({ t: 'p', x: Math.round(me.x), y: Math.round(me.y) }); }
      }
      pingT -= dt; if (pingT <= 0 && status === 'ok') { pingT = 2; send({ t: 'ping', c: performance.now() }); }
      // чужие шарики — плавно к тому, что прислал сервер, с небольшим упреждением
      for (const b of balls.values()) {
        if (b.id === myId) { b.x = me.x; b.y = me.y; continue; }
        const age = Math.min(0.12, now - b.st), tx = b.sx + b.pvx * age, ty = b.sy + b.pvy * age, k = Math.min(1, dt * 14);
        b.x += (tx - b.x) * k; b.y += (ty - b.y) * k;
        b.ang += (Math.hypot(b.pvx, b.pvy) / b.r) * dt * (b.pvx >= 0 ? 1 : -1);
        if (!b.alive && b.eatenBy) b.eatK = Math.min(1, (b.eatK || 0) + dt * 5);
      }
      let tgt = me;
      if (!me.alive && dead) { const k = balls.get(dead.killer); if (k && k.alive) tgt = k; }
      cam.x += (tgt.x - cam.x) * Math.min(1, dt * 12); cam.y += (tgt.y - cam.y) * Math.min(1, dt * 12);
      const z = C.clamp(1.25 * Math.pow(40 / Math.max(40, me.r), 0.55), 0.3, 1.25); cam.z += (z - cam.z) * Math.min(1, dt * 2);
    },

    draw(ctx) {
      ctx.fillStyle = '#2b2d6e'; ctx.fillRect(0, 0, C.W, C.H);
      ctx.save(); ctx.translate(C.W / 2, C.H / 2); ctx.scale(cam.z, cam.z); ctx.translate(-cam.x, -cam.y);
      const vw = C.W / cam.z / 2 + 120, vh = C.H / cam.z / 2 + 120, x0 = cam.x - vw, x1 = cam.x + vw, y0 = cam.y - vh, y1 = cam.y + vh;
      const RR = Rshow;
      const fg = ctx.createRadialGradient(0, 0, RR * 0.1, 0, 0, RR); fg.addColorStop(0, '#e3fbff'); fg.addColorStop(1, '#c9ecff');
      ctx.fillStyle = fg; ctx.beginPath(); ctx.arc(0, 0, RR, 0, 7); ctx.fill();
      ctx.save(); ctx.beginPath(); ctx.arc(0, 0, RR, 0, 7); ctx.clip();
      ctx.strokeStyle = 'rgba(41,121,255,0.16)'; ctx.lineWidth = 4 / cam.z; const gs = 90; ctx.beginPath();
      for (let x = Math.floor(x0 / gs) * gs; x < x1; x += gs) { ctx.moveTo(x, y0); ctx.lineTo(x, y1); }
      for (let y = Math.floor(y0 / gs) * gs; y < y1; y += gs) { ctx.moveTo(x0, y); ctx.lineTo(x1, y); }
      ctx.stroke(); ctx.restore();
      // граница: когда арена растёт — светится зелёным и «дышит»
      const gk = Math.min(1, growFx), pul = gk * (0.5 + 0.5 * Math.sin(C.realT * 10));
      ctx.strokeStyle = gk > 0 ? 'rgba(0,230,118,' + (0.5 + 0.5 * pul) + ')' : '#7c4dff'; ctx.lineWidth = 28 + 30 * pul; ctx.beginPath(); ctx.arc(0, 0, RR + 14, 0, 7); ctx.stroke();
      ctx.strokeStyle = gk > 0 ? '#b9f6ca' : '#b388ff'; ctx.lineWidth = 8; ctx.stroke();
      for (const p of dots.values()) { if (p.hid || p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) continue; ctx.fillStyle = p.c; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.beginPath(); ctx.arc(p.x - p.r * 0.3, p.y - p.r * 0.3, p.r * 0.35, 0, 7); ctx.fill(); }
      for (const p of powers) {
        if (p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) continue;
        const s = 1 + Math.sin(p.a * 5) * 0.08, P = POW[p.k] || POW[0];
        ctx.fillStyle = 'rgba(255,255,255,0.5)'; ctx.beginPath(); ctx.arc(p.x, p.y, 40 * s, 0, 7); ctx.fill();
        ctx.fillStyle = P.col; ctx.beginPath(); ctx.arc(p.x, p.y, 32 * s, 0, 7); ctx.fill(); C.icon(P.icon, p.x, p.y, 42, '#fff');
      }
      const list = Array.from(balls.values()).filter((b) => b.alive || (b.eatenBy && b.eatK < 1)).sort((a, b) => a.r - b.r);
      for (const b of list) {
        let x = b.x, y = b.y, r = b.r; const mine = b.id === myId;
        if (!b.alive && b.eatenBy) { const k = balls.get(b.eatenBy); if (k) { x = C.lerp(b.x, k.x, b.eatK); y = C.lerp(b.y, k.y, b.eatK); } r = b.r * (1 - b.eatK); }
        if (mine && me.alive) { x = me.x; y = me.y; r = me.r; }
        if (x + r < x0 || x - r > x1 || y + r < y0 || y - r > y1 || r < 1) continue;
        const fl = mine ? (me.shield ? 1 : 0) | (me.boost ? 2 : 0) | (me.magnet ? 4 : 0) : b.fl;
        ctx.fillStyle = 'rgba(30,40,80,0.18)'; ctx.beginPath(); ctx.ellipse(x + r * 0.12, y + r * 0.2, r, r * 0.95, 0, 0, 7); ctx.fill();
        if (fl & 2) { const vx = mine ? me.vx : b.pvx, vy = mine ? me.vy : b.pvy; ctx.fillStyle = 'rgba(255,214,0,0.4)'; ctx.beginPath(); ctx.arc(x - vx * 0.07, y - vy * 0.07, r * 0.95, 0, 7); ctx.fill(); }
        C.drawBall(x, y, r, b.skin, (mine ? me.ang : b.ang) * 0.15, ctx, mine ? 'rgba(255,255,255,0.95)' : b.human ? 'rgba(255,235,59,0.85)' : null);
        if (!mine && b.alive) { const rl = relOf(b); if (rl) { ctx.strokeStyle = rl > 0 ? PREY : DANGER; ctx.lineWidth = 7 / cam.z; ctx.beginPath(); ctx.arc(x, y, r + 4 / cam.z, 0, 7); ctx.stroke(); } }
        if (b.alive && (fl & 1)) { ctx.strokeStyle = 'rgba(64,196,255,' + (0.5 + 0.4 * Math.sin(C.realT * 12)) + ')'; ctx.lineWidth = 8 / cam.z; ctx.beginPath(); ctx.arc(x, y, r + 10 / cam.z, 0, 7); ctx.stroke(); }
        if (b.alive && (fl & 4)) { ctx.strokeStyle = 'rgba(255,64,129,0.45)'; ctx.lineWidth = 4 / cam.z; ctx.setLineDash([12, 12]); ctx.beginPath(); ctx.arc(x, y, r + 170 - ((C.realT * 80) % 40), 0, 7); ctx.stroke(); ctx.setLineDash([]); }
      }
      // пилы — поверх шариков: большим опасны (красный ореол), маленьким нет
      for (const s of saws) { if (s.x < x0 - 60 || s.x > x1 + 60 || s.y < y0 - 60 || s.y > y1 + 60) continue; drawSaw(ctx, s.x, s.y, SAW_R, sawSpin, me.alive && me.r >= SAW_R * 1.15); }
      for (const f of floats) { ctx.globalAlpha = Math.max(0, 1 - f.t); C.text(f.text, f.x, f.y - f.t * 80, (34 / Math.max(0.5, cam.z)) * 0.8, f.col || '#ffeb3b'); ctx.globalAlpha = 1; }
      ctx.restore();
      for (const b of balls.values()) {
        if (!b.alive) continue;
        const mine = b.id === myId, [sx, sy] = mine ? toScr(me.x, me.y) : toScr(b.x, b.y), sr = (mine ? me.r : b.r) * cam.z;
        if (sx < -120 || sx > C.W + 120 || sy < -120 || sy > C.H + 120) continue;
        const rl = mine ? 2 : relOf(b), col = rl === 2 ? '#ffeb3b' : rl > 0 ? '#69f0ae' : rl < 0 ? '#ff5252' : '#ffffff';
        C.text(String(Math.round(b.m)), sx, sy + sr + 20, C.clamp(sr * 0.5, 24, 42), col, 'center', 'rgba(0,0,0,0.8)');
        if (b.human) C.text(b.name, sx, sy - sr - 22, C.clamp(sr * 0.42, 24, 38), mine ? '#ffeb3b' : '#fff', 'center', 'rgba(0,0,0,0.85)');
      }
      if (me.alive && (steer.on || C.keyDir() || C.keyDirY()) && Math.hypot(me.vx, me.vy) > 40) {
        const a = Math.atan2(me.vy, me.vx), [sx, sy] = toScr(me.x, me.y), rr = me.r * cam.z + 22;
        ctx.save(); ctx.translate(sx + Math.cos(a) * rr, sy + Math.sin(a) * rr); ctx.rotate(a);
        ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.strokeStyle = 'rgba(40,40,90,0.6)'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(16, 0); ctx.lineTo(-8, -13); ctx.lineTo(-3, 0); ctx.lineTo(-8, 13); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
      }
      if (joy) {
        ctx.fillStyle = 'rgba(40,40,110,0.16)'; ctx.strokeStyle = 'rgba(255,255,255,0.75)'; ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(joy.ax, joy.ay, 62, 0, 7); ctx.fill(); ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.strokeStyle = 'rgba(40,40,110,0.5)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(joy.x, joy.y, 30, 0, 7); ctx.fill(); ctx.stroke();
      }
    },

    hud(ctx) {
      if (!joined) return;
      let nh = 0; for (const b of balls.values()) if (b.human) nh++;
      ctx.fillStyle = 'rgba(0,0,0,0.45)'; C.rr(ctx, C.W / 2 - 120, 30, 240, 60, 30); ctx.fill();
      C.text(T.players + ': ' + nh, C.W / 2, 61, 32, '#fff');
      const all = Array.from(balls.values()).filter((b) => b.alive).sort((a, b) => b.m - a.m);
      const mine = balls.get(myId);
      const rows = all.slice(0, 6); if (mine && mine.alive && !rows.includes(mine)) rows.push(mine);
      const bx = C.W - 250, by = 130;
      ctx.fillStyle = 'rgba(0,0,0,0.38)'; C.rr(ctx, bx, by, 232, rows.length * 46 + 16, 20); ctx.fill();
      rows.forEach((b, i) => {
        const y = by + 31 + i * 46, rank = all.indexOf(b) + 1;
        if (b.id === myId) { ctx.fillStyle = 'rgba(255,235,59,0.35)'; C.rr(ctx, bx + 6, y - 21, 220, 42, 14); ctx.fill(); }
        C.text(String(rank), bx + 22, y, 24, rank === 1 ? '#ffc107' : '#fff', 'center', null);
        C.drawBall(bx + 56, y, 16, b.skin, 0, ctx);
        if (b.human) C.text(b.name.slice(0, 7), bx + 80, y, 22, '#ffeb3b', 'left', null);
        C.text(String(Math.round(b.m)), bx + 208, y, 24, '#fff', 'right', null);
      });
      if (mine && mine.alive) {
        const myRank = all.indexOf(mine) + 1, top = myRank <= 3;
        ctx.fillStyle = top ? 'rgba(255,179,0,0.92)' : 'rgba(0,0,0,0.45)'; C.rr(ctx, C.W / 2 - 70, 100, 140, 54, 27); ctx.fill();
        C.icon('trophy', C.W / 2 - 34, 127, 32, top ? '#fff' : '#ffd54f'); C.text('#' + myRank, C.W / 2 + 24, 129, 34, '#fff');
      }
      // мои бонусы
      let ix = C.W / 2 - 60; for (const [on, P] of [[me.boost, POW[0]], [me.magnet, POW[1]], [me.shield, POW[2]]]) { if (!on || !me.alive) continue; ctx.fillStyle = P.col; ctx.beginPath(); ctx.arc(ix, 190, 26, 0, 7); ctx.fill(); C.icon(P.icon, ix, 190, 30, '#fff'); ix += 60; }
      feed.forEach((f, i) => {
        const y = 150 + i * 46; ctx.globalAlpha = Math.min(1, (3.5 - f.t) * 2);
        ctx.fillStyle = f.me ? 'rgba(255,82,82,0.55)' : 'rgba(0,0,0,0.32)'; C.rr(ctx, 22, y - 20, 250, 40, 20); ctx.fill();
        C.drawBall(44, y, 14, f.a, 0, ctx); C.text(f.an.slice(0, 6), 62, y, 20, '#fff', 'left', null);
        C.icon('next', 150, y, 20, '#fff'); C.drawBall(178, y, 12, f.b, 0, ctx); C.text(f.bn.slice(0, 6), 194, y, 20, '#fff', 'left', null);
        ctx.globalAlpha = 1;
      });
      // мини-карта: видно всю арену, как она растёт, где ты и где остальные игроки
      const mR = C.clamp(95 * (Rshow / 2000), 55, 120), mx = 30 + mR, my = C.H - 40 - mR, k = mR / Rshow;
      ctx.fillStyle = 'rgba(10,12,50,0.55)'; ctx.beginPath(); ctx.arc(mx, my, mR + 8, 0, 7); ctx.fill();
      ctx.fillStyle = 'rgba(201,236,255,0.35)'; ctx.beginPath(); ctx.arc(mx, my, mR, 0, 7); ctx.fill();
      ctx.strokeStyle = growFx > 0 ? '#00e676' : '#b388ff'; ctx.lineWidth = growFx > 0 ? 5 : 3; ctx.stroke();
      ctx.fillStyle = '#90a4ae'; for (const s of saws) { ctx.beginPath(); ctx.arc(mx + s.x * k, my + s.y * k, 4, 0, 7); ctx.fill(); }
      for (const b of balls.values()) { if (!b.alive || b.id === myId) continue; ctx.fillStyle = b.human ? '#ffffff' : 'rgba(255,255,255,0.35)'; ctx.beginPath(); ctx.arc(mx + b.x * k, my + b.y * k, b.human ? 5 : 3, 0, 7); ctx.fill(); }
      if (me.alive) { ctx.fillStyle = '#ffeb3b'; ctx.beginPath(); ctx.arc(mx + me.x * k, my + me.y * k, 7, 0, 7); ctx.fill(); ctx.strokeStyle = '#000'; ctx.lineWidth = 2; ctx.stroke(); }
      // объявления: кто зашёл, арена растёт
      toasts.forEach((t, i) => { const y = C.H * 0.74 - i * 54; ctx.globalAlpha = Math.max(0, Math.min(1, (3 - t.t) * 2, t.t * 6)); ctx.fillStyle = 'rgba(0,0,0,0.55)'; C.rr(ctx, C.W / 2 - 310, y - 24, 620, 48, 24); ctx.fill(); C.text(t.text, C.W / 2, y, 28, t.col); ctx.globalAlpha = 1; });
      if (growFx > 0 && !toasts.length) { ctx.globalAlpha = Math.min(1, growFx); C.text(T.grow, C.W / 2, C.H * 0.74, 40, '#69f0ae', 'center', 'rgba(0,0,0,0.8)'); ctx.globalAlpha = 1; }
      if (pingMs) C.text(pingMs + ' ms', C.W - 24, C.H - 30, 22, 'rgba(255,255,255,0.6)', 'right', null);
      if (status === 'conn' || status === 'lost') {
        ctx.fillStyle = 'rgba(10,10,40,0.6)'; ctx.fillRect(0, 0, C.W, C.H);
        C.text(T.conn, C.W / 2, C.H * 0.42, 40, '#fff');
        if (attempt > 1) C.text(T.att + ' ' + attempt, C.W / 2, C.H * 0.47, 28, '#cfd8dc');
        const a = C.realT * 5; ctx.strokeStyle = '#fff'; ctx.lineWidth = 8; ctx.beginPath(); ctx.arc(C.W / 2, C.H * 0.55, 34, a, a + 4); ctx.stroke();
        if (attempt >= 3) { const w = Math.min(680, C.W - 30); ctx.fillStyle = 'rgba(0,0,0,0.4)'; C.rr(ctx, C.W / 2 - w / 2, C.H * 0.62, w, 60, 20); ctx.fill(); C.text(T.slow, C.W / 2, C.H * 0.62 + 30, 21, '#ffd54f'); }
      } else if (dead && !me.alive) {
        ctx.fillStyle = 'rgba(10,10,40,' + Math.min(0.55, dead.t) + ')'; ctx.fillRect(0, 0, C.W, C.H);
        if (dead.t > 0.5) {
          C.text(T.ateBy, C.W / 2, C.H * 0.36, 40, '#fff');
          C.drawBall(C.W / 2, C.H * 0.45, 46, dead.skin, 0, ctx);
          if (dead.human) C.text(dead.by, C.W / 2, C.H * 0.53, 40, '#ffeb3b');
          C.text('★ ' + Math.round(best), C.W / 2, C.H * 0.59, 36, '#ffd54f');
          // «Заново» — большая кнопка; нажатие в любом месте нижней половины экрана тоже работает
          const anyTap = C.UI.zone('againAny', 0, C.H * 0.62, C.W, C.H * 0.38);
          if (C.button('again', C.W / 2 - 190, C.H * 0.65, 380, 130, { color: reT > 0 ? '#2e7d32' : '#43a047', label: T.again, pulse: reT <= 0 }) || anyTap) doRespawn();
        }
      }
    },
  };

  window.__objs = () => ({ saws, powers });
  window.__respawn = doRespawn;
  window.__dbgOnline = () => ({ status, myId, me, R, balls: balls.size, dots: dots.size, powers: powers.length, saws: saws.length, pingMs, dead, attempt });
  C.run(game);
})();
