'use strict';
/* Игра 5: «Шарики.io — битва стран». Арена: ешь мелочь и шарики меньше себя, убегай от больших. Раунд на время, в конце — таблица стран. */
(function () {
  const C = window.Core;
  const steer = { x: 0, y: 0, on: false };
  const LEASH = 26, DEAD = 7, TURN = 10; // в базовых единицах (720 по ширине): ~14, ~4 и ~5 px на телефоне
  let W = null, cam = { x: 0, y: 0, z: 1 }, joy = null, phase = 'ready', countdown = 0, endT = -1, endKind = null, feed = [], floats = [], startBoostUsed = false, extraUsed = false;
  const PCOL = ['#ff5252', '#ffca28', '#69f0ae', '#40c4ff', '#e040fb', '#ff9100', '#b2ff59', '#18ffff'];
  // Короткие подсказки на языке игрока (язык YouTube). Остальные языки — английский.
  const TX = {
    ru: { dots: 'Ешь точки — расти', eat: 'Меньше тебя — съешь', run: 'Больше тебя — беги', goal: 'Будь в топ-3 к концу', eatS: 'Съешь!', runS: 'Беги!', grow: 'Ешь точки!' },
    en: { dots: 'Eat dots to grow', eat: 'Smaller — eat it', run: 'Bigger — run away', goal: 'Be top 3 at the end', eatS: 'Eat!', runS: 'Run!', grow: 'Eat dots!' },
    es: { dots: 'Come puntos y crece', eat: 'Más pequeño: cómelo', run: 'Más grande: huye', goal: 'Acaba en el top 3', eatS: '¡Cómelo!', runS: '¡Huye!', grow: '¡Come puntos!' },
    pt: { dots: 'Coma pontos e cresça', eat: 'Menor: coma', run: 'Maior: fuja', goal: 'Fique no top 3 no fim', eatS: 'Coma!', runS: 'Fuja!', grow: 'Coma pontos!' },
    de: { dots: 'Friss Punkte, wachse', eat: 'Kleiner: fressen', run: 'Größer: flieh', goal: 'Am Ende Top 3', eatS: 'Fressen!', runS: 'Flieh!', grow: 'Friss Punkte!' },
    fr: { dots: 'Mange des points', eat: 'Plus petit : mange-le', run: 'Plus gros : fuis', goal: 'Finis dans le top 3', eatS: 'Mange !', runS: 'Fuis !', grow: 'Mange des points !' },
    tr: { dots: 'Nokta ye, büyü', eat: 'Küçükse ye', run: 'Büyükse kaç', goal: 'Sonda ilk 3’te ol', eatS: 'Ye!', runS: 'Kaç!', grow: 'Nokta ye!' },
  };
  const T = TX[(C.lang || 'en').slice(0, 2)] || TX.en;
  const PREY = '#00e676', DANGER = '#ff1744';
  // 1 — его можно съесть (зелёный), -1 — он может съесть тебя (красный), 0 — примерно равны
  const relOf = (p, b) => (!p.alive ? 0 : p.r > b.r * 1.12 ? 1 : b.r > p.r * 1.12 ? -1 : 0);
  const tut = () => W && (W.n === 1 || !C.save.extra.ioEat);
  const rOf = (m) => 20 + 5 * Math.sqrt(m);
  const speedOf = (r) => 440 * Math.pow(40 / r, 0.32);

  function newWorld(n) {
    const R = 1150 + Math.min(600, (n - 1) * 90);
    const w = { n, R, t: 0, time: 85 + Math.min(45, (n - 1) * 8), pellets: [], balls: [], mines: [], powers: [], powT: 6 };
    for (let i = 0; i < 420 + n * 20; i++) w.pellets.push(newPellet(R));
    for (let i = 0; i < 5 + Math.min(5, n); i++) { const p = randIn(R * 0.85); w.mines.push({ x: p.x, y: p.y, r: 46, a: Math.random() * 6 }); }
    const nb = 11 + Math.min(6, n);
    const rv = C.rivals(nb);
    w.balls.push(mkBall(0, 0, 16, C.mySkin(), true));
    for (let i = 0; i < nb; i++) { const p = randIn(R * 0.9); if (Math.hypot(p.x, p.y) < 350) { p.x += 400; } w.balls.push(mkBall(p.x, p.y, 6 + Math.random() * (14 + n * 4), rv[i], false)); }
    // первый раунд: рядом 3 маленькие страны — сразу есть кого съесть (учит правилу на деле)
    if (n === 1) for (let i = 1; i <= 3; i++) { const a = i * 2.1 + Math.random() * 0.5, d = 420 + i * 90; Object.assign(w.balls[i], { x: Math.cos(a) * d, y: Math.sin(a) * d, m: 3 + i, r: rOf(3 + i), lazy: 9 }); }
    return w;
  }
  function randIn(R) { const a = Math.random() * Math.PI * 2, d = Math.sqrt(Math.random()) * R; return { x: Math.cos(a) * d, y: Math.sin(a) * d }; }
  function newPellet(R) { const p = randIn(R * 0.97); return { x: p.x, y: p.y, c: C.pick(PCOL), r: 9 + Math.random() * 4 }; }
  function mkBall(x, y, m, skin, isPlayer) { return { x, y, vx: 0, vy: 0, m, r: rOf(m), skin, isPlayer, alive: true, ang: 0, aiT: 0, tx: x, ty: y, boost: 0, magnet: 0, respawn: 0, eatenBy: null, eatK: 0, shield: isPlayer ? 2.5 : 0 }; }

  function start(n) { W = newWorld(n); phase = 'ready'; countdown = tut() ? 5.6 : 3.2; endT = -1; endKind = null; feed = []; floats = []; startBoostUsed = false; extraUsed = false; joy = null; steer.on = false; const p = W.balls[0]; cam.x = p.x; cam.y = p.y; cam.z = 1; }

  // ---------- ИИ ----------
  function think(b) {
    let threat = null, td = 1e9, prey = null, pd = 1e9;
    for (const o of W.balls) {
      if (o === b || !o.alive) continue;
      const d = Math.hypot(o.x - b.x, o.y - b.y) - o.r - b.r;
      if (o.r > b.r * 1.12 && d < 260 + o.r && d < td) { threat = o; td = d; }
      if (b.r > o.r * 1.3 && d < (o.isPlayer ? 280 : 380) && d < pd && !(o.isPlayer && o.shield > 0)) { prey = o; pd = d; }
    }
    b.flee = false;
    if (b.lazy && W.t < b.lazy) threat = null; // учебные страны 1-го раунда сначала не убегают
    if (threat && (!prey || td < pd * 0.7)) { const a = Math.atan2(b.y - threat.y, b.x - threat.x) + (Math.random() - 0.5) * 0.6; b.tx = b.x + Math.cos(a) * 400; b.ty = b.y + Math.sin(a) * 400; b.flee = true; return; }
    if (prey) { b.tx = prey.x + prey.vx * 0.3; b.ty = prey.y + prey.vy * 0.3; return; }
    if (Math.random() < 0.15) { const q = randIn(W.R * 0.8); b.tx = q.x; b.ty = q.y; return; }
    // ближайшие точки
    let best = null, bd = 1e9; for (let i = 0; i < 40; i++) { const p = W.pellets[(Math.random() * W.pellets.length) | 0]; const d = Math.hypot(p.x - b.x, p.y - b.y); if (d < bd) { bd = d; best = p; } }
    if (best) { b.tx = best.x; b.ty = best.y; }
  }

  function moveBall(b, dt, dirx, diry, power) {
    const sp = speedOf(b.r) * (b.boost > 0 ? 1.6 : 1) * (b.isPlayer ? 1 : b.flee ? 0.76 : 0.85);
    const tvx = dirx * sp * power, tvy = diry * sp * power;
    const k = Math.min(1, dt * (b.isPlayer ? 30 : 10)); b.vx += (tvx - b.vx) * k; b.vy += (tvy - b.vy) * k;
    b.x += b.vx * dt; b.y += b.vy * dt;
    const d = Math.hypot(b.x, b.y), lim = W.R - b.r * 0.6; if (d > lim) { b.x *= lim / d; b.y *= lim / d; }
    b.ang += (Math.hypot(b.vx, b.vy) / b.r) * dt * (b.vx >= 0 ? 1 : -1);
  }

  function eat(a, b) {
    b.alive = false; b.eatenBy = a; b.eatK = 0; a.m += b.m * 0.85; a.r = rOf(a.m);
    feed.unshift({ a: a.skin, b: b.skin, t: 0, me: a.isPlayer || b.isPlayer }); feed.length = Math.min(feed.length, 4);
    if (a.isPlayer && !C.save.extra.ioEat) { C.save.extra.ioEat = 1; C.persist(); }
    if (a.isPlayer) { C.sfx('pop'); floats.push({ x: a.x, y: a.y - a.r, text: '+' + Math.round(b.m * 0.85), t: 0 }); C.burst(...toScr(b.x, b.y), '#ffd54f', 16, 380); }
    if (b.isPlayer) { C.sfx('crash', 0.6); }
    if (!b.isPlayer) b.respawn = 3 + Math.random() * 3;
  }

  function toScr(x, y) { return [(x - cam.x) * cam.z + C.W / 2, (y - cam.y) * cam.z + C.H / 2]; }

  const game = {
    id: 'ballio',
    hasSkip: false,
    init() { start(C.save.level); },
    startLevel(n) { start(n); },
    toHome() { start(C.save.level); },
    revive() {
      const p = W.balls[0];
      if (endKind === 'time') { W.time += 20; extraUsed = true; }
      else { let best = null, bd = -1; for (let i = 0; i < 20; i++) { const q = randIn(W.R * 0.8); let md = 1e9; for (const o of W.balls) if (o.alive && !o.isPlayer) md = Math.min(md, Math.hypot(o.x - q.x, o.y - q.y) - o.r); if (md > bd) { bd = md; best = q; } } p.x = best.x; p.y = best.y; p.m = Math.max(12, p.lastM * 0.6); p.r = rOf(p.m); p.alive = true; p.eatenBy = null; p.shield = 3; }
      phase = 'run'; endT = -1; endKind = null; steer.on = false; joy = null;
    },
    reviveIcon: null,
    // Управление как в Snake Clash / Paper.io: коснулся где угодно — под пальцем маленький джойстик.
    // Направление = от «якоря» к пальцу. Якорь тянется за пальцем на коротком поводке (LEASH),
    // поэтому дрожь пальца не сбивает курс, а резкий взмах в другую сторону разворачивает сразу.
    // Отпустил палец — шарик катится дальше в ту же сторону (перехват пальца не останавливает).
    onDown(x, y) { if (C.state !== 'play') return; joy = { ax: x, ay: y, x, y, rx: 0, ry: 0 }; },
    onMove(x, y) {
      if (!joy) return;
      const mx = x - joy.x, my = y - joy.y, ml = Math.hypot(mx, my); joy.x = x; joy.y = y;
      if (ml < 0.01) return;
      if (steer.on) {
        // палец пошёл в другую сторону (> 60° от курса) — копим этот путь; набралось ~5 px — разворот сразу
        if (mx * steer.x + my * steer.y < ml * 0.5) { joy.rx += mx; joy.ry += my; } else { joy.rx = 0; joy.ry = 0; }
        const rl = Math.hypot(joy.rx, joy.ry);
        if (rl > TURN && joy.rx * steer.x + joy.ry * steer.y < rl * 0.5) {
          steer.x = joy.rx / rl; steer.y = joy.ry / rl;
          joy.ax = x - steer.x * LEASH; joy.ay = y - steer.y * LEASH; joy.rx = joy.ry = 0; return;
        }
      }
      const vx = x - joy.ax, vy = y - joy.ay; let d = Math.hypot(vx, vy);
      if (d > LEASH) { joy.ax = x - (vx / d) * LEASH; joy.ay = y - (vy / d) * LEASH; d = LEASH; }
      if (d > DEAD) { const l = Math.hypot(vx, vy); steer.x = vx / l; steer.y = vy / l; steer.on = true; }
    },
    onUp() { joy = null; },
    // ПК: мышь без нажатия — шарик катится к курсору (как в agar.io)
    onHover(x, y) {
      if (C.state !== 'play' || !W) return;
      const p = W.balls[0], [sx, sy] = toScr(p.x, p.y), vx = x - sx, vy = y - sy, d = Math.hypot(vx, vy);
      if (d > Math.max(16, p.r * cam.z * 0.4)) { steer.x = vx / d; steer.y = vy / d; steer.on = true; }
    },
    onKey(k, down) { if (down && k === 'Space' && C.state === 'play' && phase === 'ready') countdown = Math.min(countdown, 0.01); },

    update(dt) {
      if (!W) return;
      for (const f of feed) f.t += dt; feed = feed.filter((f) => f.t < 3);
      for (const f of floats) f.t += dt; floats = floats.filter((f) => f.t < 0.9);
      for (const m of W.mines) m.a += dt * 0.8;
      const p = W.balls[0];
      if (C.state === 'home') { W.t += dt; botsStep(dt); camFollow(dt, p); return; }
      if (C.state !== 'play') { camFollow(dt, p); return; }
      if (phase === 'ready') {
        const b4 = Math.ceil(countdown); countdown -= dt; const a4 = Math.ceil(countdown);
        if (a4 !== b4 && a4 > 0) C.sfx('tap'); if (countdown <= 0) { phase = 'run'; C.sfx('gate'); }
        camFollow(dt, p); return;
      }
      W.t += dt;
      // игрок
      if (p.alive) {
        let dx = 0, dy = 0, pw = 0;
        if (steer.on) { dx = steer.x; dy = steer.y; pw = 1; }
        const kx = C.keyDir(), ky = C.keyDirY(); if (kx || ky) { const d = Math.hypot(kx, ky); dx = kx / d; dy = ky / d; pw = 1; }
        if (window.__chase) { let tg = null, td = 1e9, th = null, hd = 1e9; for (const o of W.balls) { if (o.isPlayer || !o.alive) continue; const d = Math.hypot(o.x - p.x, o.y - p.y) - o.r - p.r, rl = relOf(p, o); if (rl > 0 && d < td) { td = d; tg = o; } if (rl < 0 && d < hd) { hd = d; th = o; } } let vx, vy; if (th && hd < 220) { vx = p.x - th.x; vy = p.y - th.y; } else if (tg && td < 900) { vx = tg.x - p.x; vy = tg.y - p.y; } else { think(p); vx = p.tx - p.x; vy = p.ty - p.y; } const d = Math.hypot(vx, vy) || 1; dx = vx / d; dy = vy / d; pw = 1; }
        if (window.__auto) { think(p); const vx = p.tx - p.x, vy = p.ty - p.y, d = Math.hypot(vx, vy) || 1; dx = vx / d; dy = vy / d; pw = 1; }
        moveBall(p, dt, dx, dy, pw);
        p.boost = Math.max(0, p.boost - dt); p.magnet = Math.max(0, p.magnet - dt); p.shield = Math.max(0, p.shield - dt);
      }
      botsStep(dt);
      // точки
      for (const b of W.balls) {
        if (!b.alive) continue;
        for (let i = 0; i < W.pellets.length; i++) {
          const q = W.pellets[i]; const dx = q.x - b.x, dy = q.y - b.y;
          if (b.magnet > 0) { const d = Math.hypot(dx, dy); if (d < 320 && d > 1) { q.x -= (dx / d) * 500 * dt; q.y -= (dy / d) * 500 * dt; } }
          if (dx * dx + dy * dy < b.r * b.r) { b.m += 1; b.r = rOf(b.m); W.pellets[i] = newPellet(W.R); if (b.isPlayer && Math.random() < 0.35) C.sfx('coin'); }
        }
      }
      // бонусы
      W.powT -= dt; if (W.powT <= 0 && W.powers.length < 3) { W.powT = 9; const q = randIn(W.R * 0.8); W.powers.push({ x: q.x, y: q.y, k: Math.random() < 0.5 ? 'bolt' : 'magnet', a: 0 }); }
      for (let i = W.powers.length - 1; i >= 0; i--) { const pw = W.powers[i]; pw.a += dt; for (const b of W.balls) if (b.alive && Math.hypot(pw.x - b.x, pw.y - b.y) < b.r + 30) { if (pw.k === 'bolt') b.boost = 4; else b.magnet = 6; if (b.isPlayer) C.sfx('buy'); W.powers.splice(i, 1); break; } }
      // мины: большой шарик лопается на части
      for (const mn of W.mines) for (const b of W.balls) {
        if (!b.alive || b.r < mn.r * 1.2) continue;
        if (Math.hypot(mn.x - b.x, mn.y - b.y) < b.r * 0.85 + mn.r * 0.5) {
          if (b.isPlayer && b.shield > 0) continue;
          const lost = b.m * 0.35; b.m -= lost; b.r = rOf(b.m);
          for (let k = 0; k < Math.min(40, lost / 2); k++) { const a = Math.random() * 7, d = b.r + 30 + Math.random() * 120; W.pellets.push({ x: b.x + Math.cos(a) * d, y: b.y + Math.sin(a) * d, c: C.pick(PCOL), r: 9 }); }
          const a = Math.atan2(b.y - mn.y, b.x - mn.x); b.x += Math.cos(a) * 60; b.y += Math.sin(a) * 60;
          if (b.isPlayer) { C.sfx('crash', 0.5); C.burst(...toScr(b.x, b.y), '#76ff03', 20, 420); b.shield = 1; }
          const q = randIn(W.R * 0.85); mn.x = q.x; mn.y = q.y;
        }
      }
      if (W.pellets.length > 700) W.pellets.splice(0, W.pellets.length - 700);
      // поедание
      const bs = W.balls;
      for (let i = 0; i < bs.length; i++) for (let j = 0; j < bs.length; j++) {
        const a = bs[i], b = bs[j]; if (i === j || !a.alive || !b.alive) continue;
        if (a.r > b.r * 1.12 && Math.hypot(a.x - b.x, a.y - b.y) < a.r - b.r * 0.15) { if (b.isPlayer && b.shield > 0) continue; if (b.isPlayer) b.lastM = b.m; eat(a, b); }
      }
      for (const b of bs) { if (!b.alive && b.eatenBy) b.eatK = Math.min(1, b.eatK + dt * 5); if (!b.alive && !b.isPlayer) { b.respawn -= dt; if (b.respawn <= 0) { const q = randIn(W.R * 0.9); Object.assign(b, mkBall(q.x, q.y, 6 + Math.random() * 10, b.skin, false)); } } }
      camFollow(dt, p);
      // конец
      if (C.state === 'play' && endT < 0) {
        if (!p.alive) { endT = 0.9; endKind = 'eaten'; game.reviveIcon = 'heart'; }
        else if (W.t >= W.time) { const rank = ranking().indexOf(p) + 1; endT = 0.4; endKind = rank <= 3 ? 'win' : 'time'; game.reviveIcon = 'clock'; }
      }
      if (endT > 0) {
        endT -= dt;
        if (endT <= 0 && C.state === 'play') {
          if (endKind === 'win') { const rank = ranking().indexOf(p) + 1, st = 4 - rank; C.win({ stars: st, place: rank, coins: 15 + st * 10 + Math.round(p.m / 4) }); }
          else C.fail({ revive: endKind === 'eaten' || !extraUsed });
        }
      }
    },

    draw(ctx) {
      // пол
      ctx.fillStyle = '#2b2d6e'; ctx.fillRect(0, 0, C.W, C.H);
      if (!W) return;
      ctx.save(); ctx.translate(C.W / 2, C.H / 2); ctx.scale(cam.z, cam.z); ctx.translate(-cam.x, -cam.y);
      const vw = C.W / cam.z / 2 + 80, vh = C.H / cam.z / 2 + 80, x0 = cam.x - vw, x1 = cam.x + vw, y0 = cam.y - vh, y1 = cam.y + vh;
      // арена
      const fg = ctx.createRadialGradient(0, 0, W.R * 0.1, 0, 0, W.R); fg.addColorStop(0, '#e3fbff'); fg.addColorStop(1, '#c9ecff');
      ctx.fillStyle = fg; ctx.beginPath(); ctx.arc(0, 0, W.R, 0, 7); ctx.fill();
      ctx.save(); ctx.beginPath(); ctx.arc(0, 0, W.R, 0, 7); ctx.clip();
      ctx.strokeStyle = 'rgba(41,121,255,0.16)'; ctx.lineWidth = 4 / cam.z;
      const gs = 90; ctx.beginPath();
      for (let x = Math.floor(x0 / gs) * gs; x < x1; x += gs) { ctx.moveTo(x, y0); ctx.lineTo(x, y1); }
      for (let y = Math.floor(y0 / gs) * gs; y < y1; y += gs) { ctx.moveTo(x0, y); ctx.lineTo(x1, y); }
      ctx.stroke(); ctx.restore();
      ctx.strokeStyle = '#7c4dff'; ctx.lineWidth = 28; ctx.beginPath(); ctx.arc(0, 0, W.R + 14, 0, 7); ctx.stroke();
      ctx.strokeStyle = '#b388ff'; ctx.lineWidth = 8; ctx.stroke();
      // точки
      for (const q of W.pellets) { if (q.x < x0 || q.x > x1 || q.y < y0 || q.y > y1) continue; ctx.fillStyle = q.c; ctx.beginPath(); ctx.arc(q.x, q.y, q.r, 0, 7); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.beginPath(); ctx.arc(q.x - q.r * 0.3, q.y - q.r * 0.3, q.r * 0.35, 0, 7); ctx.fill(); }
      // бонусы
      for (const pw of W.powers) { if (pw.x < x0 || pw.x > x1 || pw.y < y0 || pw.y > y1) continue; const s = 1 + Math.sin(pw.a * 5) * 0.08; ctx.fillStyle = pw.k === 'bolt' ? '#ffd600' : '#ff4081'; ctx.beginPath(); ctx.arc(pw.x, pw.y, 30 * s, 0, 7); ctx.fill(); C.icon(pw.k, pw.x, pw.y, 40, '#fff'); }
      // шарики (маленькие снизу)
      const order = W.balls.filter((b) => b.alive || (b.eatenBy && b.eatK < 1)).sort((a, b) => a.r - b.r);
      for (const b of order) {
        let x = b.x, y = b.y, r = b.r;
        if (!b.alive && b.eatenBy) { x = C.lerp(b.x, b.eatenBy.x, b.eatK); y = C.lerp(b.y, b.eatenBy.y, b.eatK); r = b.r * (1 - b.eatK); }
        if (x + r < x0 || x - r > x1 || y + r < y0 || y - r > y1 || r < 1) continue;
        ctx.fillStyle = 'rgba(30,40,80,0.18)'; ctx.beginPath(); ctx.ellipse(x + r * 0.12, y + r * 0.2, r, r * 0.95, 0, 0, 7); ctx.fill();
        if (b.boost > 0) { ctx.fillStyle = 'rgba(255,214,0,0.35)'; ctx.beginPath(); ctx.arc(x - b.vx * 0.06, y - b.vy * 0.06, r * 0.95, 0, 7); ctx.fill(); }
        C.drawBall(x, y, r, b.skin, b.ang * 0.15, ctx, b.isPlayer ? 'rgba(255,255,255,0.95)' : null);
        if (!b.isPlayer && b.alive) {
          const rl = relOf(W.balls[0], b);
          if (rl) { ctx.strokeStyle = rl > 0 ? PREY : DANGER; ctx.lineWidth = 7 / cam.z; ctx.beginPath(); ctx.arc(x, y, r + 4 / cam.z, 0, 7); ctx.stroke(); }
        }
        if (b.isPlayer && b.shield > 0) { ctx.strokeStyle = 'rgba(64,196,255,' + (0.5 + 0.4 * Math.sin(C.realT * 12)) + ')'; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(x, y, r + 8, 0, 7); ctx.stroke(); }
        if (b.magnet > 0) { ctx.strokeStyle = 'rgba(255,64,129,0.4)'; ctx.lineWidth = 4; ctx.setLineDash([10, 10]); ctx.beginPath(); ctx.arc(x, y, r + 40 + ((C.realT * 60) % 30), 0, 7); ctx.stroke(); ctx.setLineDash([]); }
      }
      // мины
      for (const mn of W.mines) {
        if (mn.x < x0 || mn.x > x1 || mn.y < y0 || mn.y > y1) continue;
        ctx.save(); ctx.translate(mn.x, mn.y); ctx.rotate(mn.a); ctx.fillStyle = '#43a047'; ctx.strokeStyle = '#1b5e20'; ctx.lineWidth = 4; ctx.beginPath();
        for (let i = 0; i < 28; i++) { const a = (i / 28) * Math.PI * 2, rr = i % 2 ? mn.r : mn.r * 0.78; ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); }
        ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.beginPath(); ctx.arc(-10, -10, 10, 0, 7); ctx.fill(); ctx.restore();
      }
      for (const f of floats) { ctx.globalAlpha = 1 - f.t; C.text(f.text, f.x, f.y - f.t * 80, 34 / Math.max(0.5, cam.z) * 0.8, '#ffeb3b'); ctx.globalAlpha = 1; }
      ctx.restore();
      const pl = W.balls[0];
      // размер каждого шарика числом, цвет — можно ли его съесть
      for (const b of W.balls) {
        if (!b.alive) continue;
        const [sx, sy] = toScr(b.x, b.y), sr = b.r * cam.z;
        if (sx < -80 || sx > C.W + 80 || sy < -80 || sy > C.H + 80) continue;
        const rl = b.isPlayer ? 2 : relOf(pl, b);
        const col = rl === 2 ? '#ffeb3b' : rl > 0 ? '#69f0ae' : rl < 0 ? '#ff5252' : '#ffffff';
        C.text(String(Math.round(b.m)), sx, sy + sr + 20, C.clamp(sr * 0.5, 24, 42), col, 'center', 'rgba(0,0,0,0.8)');
      }
      if (C.state === 'play' && phase === 'run' && pl.alive && tut()) coach(ctx, pl);
      // джойстик
      if (C.state === 'play' && pl.alive && (steer.on || C.keyDir() || C.keyDirY()) && Math.hypot(pl.vx, pl.vy) > 40) {
        const a = Math.atan2(pl.vy, pl.vx), [sx, sy] = toScr(pl.x, pl.y), rr = pl.r * cam.z + 22;
        ctx.save(); ctx.translate(sx + Math.cos(a) * rr, sy + Math.sin(a) * rr); ctx.rotate(a);
        ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.strokeStyle = 'rgba(40,40,90,0.6)'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(16, 0); ctx.lineTo(-8, -13); ctx.lineTo(-3, 0); ctx.lineTo(-8, 13); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
      }
      if (joy && C.state === 'play') {
        // джойстик едет за пальцем: кольцо вокруг якоря, ручка под пальцем
        ctx.fillStyle = 'rgba(40,40,110,0.16)'; ctx.strokeStyle = 'rgba(255,255,255,0.75)'; ctx.lineWidth = 5;
        ctx.beginPath(); ctx.arc(joy.ax, joy.ay, 62, 0, 7); ctx.fill(); ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.strokeStyle = 'rgba(40,40,110,0.5)'; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.arc(joy.x, joy.y, 30, 0, 7); ctx.fill(); ctx.stroke();
      }
    },

    hud(ctx) {
      C.drawCoinsHud();
      const p = W.balls[0];
      // таймер
      const left = Math.max(0, Math.ceil(W.time - W.t));
      ctx.fillStyle = left <= 10 ? 'rgba(229,57,53,0.85)' : 'rgba(0,0,0,0.45)'; C.rr(ctx, C.W / 2 - 74, 30, 148, 64, 32); ctx.fill();
      C.icon('clock', C.W / 2 - 40, 62, 36, '#fff'); C.text(Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0'), C.W / 2 + 22, 64, 36);
      // таблица стран
      const rk = ranking(); const myRank = rk.indexOf(p) + 1;
      const rows = rk.slice(0, 5); if (!rows.includes(p)) rows.push(p);
      const bx = C.W - 214, by = 130;
      ctx.fillStyle = 'rgba(0,0,0,0.38)'; C.rr(ctx, bx, by, 196, rows.length * 48 + 16, 20); ctx.fill();
      rows.forEach((b, i) => {
        const y = by + 32 + i * 48, rank = rk.indexOf(b) + 1;
        if (b.isPlayer) { ctx.fillStyle = 'rgba(255,235,59,0.35)'; C.rr(ctx, bx + 6, y - 22, 184, 44, 14); ctx.fill(); }
        C.text(String(rank), bx + 24, y, 26, rank === 1 ? '#ffc107' : '#fff', 'center', null);
        C.drawBall(bx + 64, y, 17, b.skin, 0, ctx);
        C.text(String(Math.round(b.m)), bx + 150, y, 26, '#fff', 'center', null);
      });
      // твоё место крупно под таймером: золотое, когда ты в топ-3
      const top = myRank <= 3, pul = top ? 1 : 0.92 + 0.08 * Math.sin(C.realT * 4);
      ctx.fillStyle = top ? 'rgba(255,179,0,0.92)' : 'rgba(0,0,0,0.45)'; C.rr(ctx, C.W / 2 - 70, 104, 140, 56, 28); ctx.fill();
      C.icon('trophy', C.W / 2 - 34, 132, 34 * pul, top ? '#fff' : '#ffd54f'); C.text('#' + myRank, C.W / 2 + 24, 134, 36, '#fff');
      // лента: кто кого съел
      feed.forEach((f, i) => {
        const y = 140 + i * 46, a = Math.min(1, (3 - f.t) * 2); ctx.globalAlpha = a;
        ctx.fillStyle = f.me ? 'rgba(255,82,82,0.5)' : 'rgba(0,0,0,0.3)'; C.rr(ctx, 22, y - 20, 150, 40, 20); ctx.fill();
        C.drawBall(48, y, 15, f.a, 0, ctx); C.icon('next', 96, y, 22, '#fff'); C.drawBall(140, y, 12, f.b, 0, ctx); ctx.globalAlpha = 1;
      });
      if (C.state !== 'play') return;
      if (phase === 'ready') {
        const n = Math.ceil(countdown), f = countdown - Math.floor(countdown);
        if (n <= 3) { ctx.save(); ctx.translate(C.W / 2, C.H * 0.27); ctx.scale(1 + f * 0.4, 1 + f * 0.4); C.text(String(n), 0, 0, 150, '#7c4dff', 'center', '#fff'); ctx.restore(); }
        rulesCard(ctx);
        if (!startBoostUsed && C.rewardedSupported && C.button('bigStart', C.W / 2 - 170, C.H * 0.705, 340, 120, { color: '#43a047', pulse: true, draw: () => { C.icon('ad', -80, -2, 60); C.text('×3', 0, 0, 56); C.icon('shop', 80, -2, 50, '#ffeb3b'); } })) {
          countdown = Math.max(countdown, 1.5);
          C.ads.rewarded('start_big').then((ok) => { if (ok) { startBoostUsed = true; p.m *= 3; p.r = rOf(p.m); C.sfx('buy'); } });
        }
        // подсказка: такой же джойстик, как в игре — ручку ведут в сторону, куда катиться
        const k = (C.realT % 2) / 2, a = k * Math.PI * 2, jx = C.W / 2, jy = C.H * 0.88;
        ctx.fillStyle = 'rgba(40,40,110,0.16)'; ctx.strokeStyle = 'rgba(60,60,120,0.55)'; ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(jx, jy, 62, 0, 7); ctx.fill(); ctx.stroke();
        const kx = jx + Math.cos(a) * 30, ky = jy + Math.sin(a) * 30;
        ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.strokeStyle = 'rgba(40,40,110,0.6)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(kx, ky, 30, 0, 7); ctx.fill(); ctx.stroke();
      }
    },
  };

  // Живые подсказки в первом раунде: «Беги!» над красным рядом, стрелка «Съешь!» к ближайшему зелёному.
  function coach(ctx, p) {
    let prey = null, pd = 1e9, thr = null, td = 1e9;
    for (const b of W.balls) {
      if (b.isPlayer || !b.alive) continue;
      const d = Math.hypot(b.x - p.x, b.y - p.y) - b.r - p.r, rl = relOf(p, b);
      if (rl > 0 && d < pd) { pd = d; prey = b; }
      if (rl < 0 && d < td) { td = d; thr = b; }
    }
    const pulse = 0.5 + 0.5 * Math.sin(C.realT * 8), [px, py] = toScr(p.x, p.y);
    if (thr && td < 300) {
      const [tx, ty] = toScr(thr.x, thr.y);
      C.text(T.runS, tx, ty - thr.r * cam.z - 34, 46 + pulse * 8, '#ff5252', 'center', 'rgba(0,0,0,0.85)');
      return;
    }
    if (prey && pd < 900) {
      const [qx, qy] = toScr(prey.x, prey.y), a = Math.atan2(qy - py, qx - px), dist = Math.hypot(qx - px, qy - py);
      const r0 = p.r * cam.z + 18, len = Math.min(110, Math.max(0, dist - prey.r * cam.z - r0 - 10));
      if (len > 30) {
        ctx.save(); ctx.translate(px + Math.cos(a) * (r0 + pulse * 10), py + Math.sin(a) * (r0 + pulse * 10)); ctx.rotate(a);
        ctx.fillStyle = PREY; ctx.strokeStyle = 'rgba(0,60,20,0.8)'; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.moveTo(0, -9); ctx.lineTo(len - 26, -9); ctx.lineTo(len - 26, -22); ctx.lineTo(len, 0); ctx.lineTo(len - 26, 22); ctx.lineTo(len - 26, 9); ctx.lineTo(0, 9); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
      }
      const lx = C.clamp(qx, 90, C.W - 90), ly = C.clamp(qy - prey.r * cam.z - 36, 180, C.H - 60);
      C.text(T.eatS, lx, ly, 44 + pulse * 6, '#69f0ae', 'center', 'rgba(0,0,0,0.85)');
      return;
    }
    if (W.t < 8) C.text(T.grow, px, py - p.r * cam.z - 44, 40, '#fff', 'center', 'rgba(0,0,0,0.75)');
  }
  // Правила картинками (пока идёт отсчёт)
  function rulesCard(ctx) {
    const pw = Math.min(640, C.W - 40), x0 = C.W / 2 - pw / 2, y0 = C.H * 0.38, rh = 84;
    ctx.fillStyle = 'rgba(28,30,78,0.93)'; C.rr(ctx, x0, y0, pw, rh * 4 + 16, 28); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 3; ctx.stroke();
    const vx = x0 + 110, tx = x0 + 214, me = C.mySkin(), sA = W.balls[1].skin, sB = W.balls[2].skin, k = (C.realT % 2) / 2;
    const row = (i) => y0 + 8 + rh * i + rh / 2;
    const arrow = (x, y, len, col) => { ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(x - len / 2, y - 5); ctx.lineTo(x + len / 2 - 12, y - 5); ctx.lineTo(x + len / 2 - 12, y - 13); ctx.lineTo(x + len / 2, y); ctx.lineTo(x + len / 2 - 12, y + 13); ctx.lineTo(x + len / 2 - 12, y + 5); ctx.lineTo(x - len / 2, y + 5); ctx.closePath(); ctx.fill(); };
    // 1. точки → растёшь
    let y = row(0);
    ['#ff5252', '#ffca28', '#40c4ff'].forEach((c, j) => { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(vx - 82 + j * 22, y + (j % 2 ? -8 : 8), 8, 0, 7); ctx.fill(); });
    arrow(vx - 4, y, 36, '#fff'); C.drawBall(vx + 52, y, 18 + k * 12, me, 0, ctx);
    C.text(T.dots, tx, y, 32, '#fff', 'left', null);
    // 2. меньше тебя (зелёное кольцо) → съешь
    y = row(1);
    C.drawBall(vx - 56, y, 32, me, 0, ctx); arrow(vx + 2, y, 34, PREY);
    C.drawBall(vx + 50, y, 17, sA, 0, ctx); ctx.strokeStyle = PREY; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(vx + 50, y, 21, 0, 7); ctx.stroke();
    C.text(T.eat, tx, y, 32, '#69f0ae', 'left', null);
    // 3. больше тебя (красное кольцо) → беги
    y = row(2);
    C.drawBall(vx - 50, y, 33, sB, 0, ctx); ctx.strokeStyle = DANGER; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(vx - 50, y, 37, 0, 7); ctx.stroke();
    C.drawBall(vx + 30 + k * 20, y, 16, me, 0, ctx); arrow(vx + 74 + k * 20, y, 30, '#ff8a80');
    C.text(T.run, tx, y, 32, '#ff8a80', 'left', null);
    // 4. цель — топ-3, когда кончится время
    y = row(3);
    C.icon('clock', vx - 50, y, 40, '#fff'); C.icon('trophy', vx + 30, y, 46, '#ffc107');
    C.text(T.goal, tx, y, 32, '#ffd54f', 'left', null);
  }
  function ranking() { return W.balls.filter((b) => b.alive || b.isPlayer).sort((a, b) => b.m - a.m); }
  function botsStep(dt) {
    for (const b of W.balls) {
      if (b.isPlayer || !b.alive) continue;
      b.aiT -= dt; if (b.aiT <= 0) { b.aiT = 0.25 + Math.random() * 0.2; think(b); }
      const vx = b.tx - b.x, vy = b.ty - b.y, d = Math.hypot(vx, vy) || 1;
      moveBall(b, dt, vx / d, vy / d, d > 20 ? 1 : 0.3);
      b.boost = Math.max(0, b.boost - dt); b.magnet = Math.max(0, b.magnet - dt);
    }
  }
  function camFollow(dt, p) {
    const target = p.alive ? p : (p.eatenBy || p);
    cam.x += (target.x - cam.x) * Math.min(1, dt * 12); cam.y += (target.y - cam.y) * Math.min(1, dt * 12);
    const z = C.clamp(1.25 * Math.pow(40 / Math.max(40, p.r), 0.55), 0.3, 1.25);
    cam.z += (z - cam.z) * Math.min(1, dt * 2);
  }

  window.__dbg = () => ({ W, phase, endKind });
  C.run(game);
})();
