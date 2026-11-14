'use strict';
/* Игра 2: «Спуск шариков» — гонка вниз по трассе, ведёшь свой шарик пальцем влево-вправо. */
(function () {
  const C = window.Core;
  const LW = 720, R = 26, SPACING = 330;
  let lastN = 0, world = null, ox = 0, camY = 0, countdown = 0, shield = false, shieldUsed = false, invul = 0, endT = -1, endKind = null, pickups = 0;
  let touchX = null, targetX = 360, placeFx = null, stars = [];
  for (let i = 0; i < 70; i++) stars.push({ x: Math.random() * 1600, y: Math.random() * 3000, s: Math.random() * 2 + 1, p: Math.random() * 0.5 + 0.2 });

  function layout() { ox = (C.W - LW) / 2; }

  // ---------- трасса ----------
  function genLevel(n) {
    const rng = C.seeded(1000 + n * 77);
    const rows = 10 + Math.min(16, (n - 1) * 3);
    const d = Math.min(1, (n - 1) / 8);
    const obs = [];
    const coins = [];
    let y = 600;
    for (let i = 0; i < rows; i++) {
      const r = rng();
      let type;
      if (i < (n === 1 ? 4 : 2)) type = 'gap';
      else if (r < 0.28) type = 'gap';
      else if (r < 0.28 + (n === 1 ? 0.1 : 0.18) + d * 0.1) type = 'spikegap';
      else if (r < 0.66) type = 'rot';
      else if (r < 0.82) type = 'pegs';
      else type = 'boost';
      const gw = 190 - d * 40 + rng() * 40;
      const gc = 120 + rng() * (LW - 240);
      const move = n >= 2 && rng() < 0.25 + d * 0.4 ? 60 + rng() * 120 : 0;
      const o = { type, y, gw, gc, move, ph: rng() * 6, sp: 0.8 + rng() * 1.2 };
      if (type === 'rot') { o.cx = 200 + rng() * 320; o.len = 300 + rng() * 120; o.w = (rng() < 0.5 ? -1 : 1) * (0.9 + d * 1.2 + rng() * 0.6); o.spike = rng() < d * 0.5; }
      if (type === 'pegs') { o.pegs = []; const sh = (rng() - 0.5) * 30; for (let k = 0; k < 5; k++) o.pegs.push([90 + k * 135 + sh, y - 40]); for (let k = 0; k < 4; k++) o.pegs.push([157 + k * 135 + sh, y + 40]); }
      obs.push(o);
      // монеты в проходе
      const cy = y + SPACING / 2;
      for (let k = -1; k <= 1; k++) coins.push({ x: C.clamp(gc + k * 50, 50, LW - 50), y: cy + k * 35, taken: false, follow: o });
      y += SPACING;
    }
    return { obs, coins, finishY: y + 200, length: y + 200, n };
  }

  function gapCenter(o, t) { return C.clamp(o.gc + (o.move ? Math.sin(t * o.sp + o.ph) * o.move : 0), o.gw / 2 + 10, LW - o.gw / 2 - 10); }

  // отрезки препятствий в момент t
  function segsOf(o, t) {
    const out = [];
    if (o.type === 'gap' || o.type === 'spikegap' || o.type === 'boost') {
      const gc = gapCenter(o, t), k = o.type === 'spikegap' ? 'spike' : 'wall';
      out.push({ k, ax: 0, ay: o.y, bx: gc - o.gw / 2, by: o.y, th: 18 });
      out.push({ k, ax: gc + o.gw / 2, ay: o.y, bx: LW, by: o.y, th: 18 });
    } else if (o.type === 'rot') {
      const a = t * o.w + o.ph; const hx = Math.cos(a) * o.len / 2, hy = Math.sin(a) * o.len / 2;
      out.push({ k: o.spike ? 'spike2' : 'wall', ax: o.cx - hx, ay: o.y - hy, bx: o.cx + hx, by: o.y + hy, th: 20 });
    } else if (o.type === 'pegs') {
      for (const [x, y] of o.pegs) out.push({ k: 'peg', ax: x, ay: y, bx: x, by: y, th: 34 });
    }
    return out;
  }

  function newRace(n) {
    world = genLevel(n);
    const rv = C.rivals(3);
    const xs = C.shuffle([150, 280, 440, 570]);
    world.balls = xs.map((x, i) => ({
      x, y: 300, vx: 0, vy: 0, r: R, ang: 0, isPlayer: i === 0, skin: i === 0 ? C.mySkin() : rv[i - 1], done: false, dead: false, place: 0,
      skill: i === 0 ? 1 : 0.5 + Math.random() * 0.2 + Math.min(0.25, (n - 1) * 0.04), aimOff: 0, aimFor: -1, boost: 0,
    }));
    world.t = 0; world.finished = 0; world.started = false;
    countdown = n === lastN ? 1.6 : 2.6; lastN = n; shield = false; shieldUsed = false; invul = 0; endT = -1; endKind = null; pickups = 0; placeFx = null;
    targetX = world.balls[0].x; touchX = null; camY = 0;
  }

  function collide(b, s, isPlayer) {
    const dx = s.bx - s.ax, dy = s.by - s.ay, L2 = dx * dx + dy * dy;
    let t = L2 > 0 ? ((b.x - s.ax) * dx + (b.y - s.ay) * dy) / L2 : 0; t = t < 0 ? 0 : t > 1 ? 1 : t;
    const px = s.ax + dx * t, py = s.ay + dy * t, ex = b.x - px, ey = b.y - py, d2 = ex * ex + ey * ey, rr = b.r + s.th / 2;
    if (d2 >= rr * rr || d2 < 1e-6) return null;
    const d = Math.sqrt(d2), nx = ex / d, ny = ey / d;
    b.x += nx * (rr - d); b.y += ny * (rr - d);
    const vn = b.vx * nx + b.vy * ny;
    if ((s.k === 'spike' && ny < 0.3) || s.k === 'spike2') return 'spike';
    if (vn < 0) { const e = s.k === 'peg' ? 0.7 : 0.35; b.vx -= (1 + e) * vn * nx; b.vy -= (1 + e) * vn * ny; if (vn < -150) return 'hit'; }
    return null;
  }

  function stepBall(b, dt) {
    const w = world;
    const base = 520 + Math.min(200, w.n * 18);
    const vmax = (b.isPlayer ? base + 50 : base * (0.82 + 0.1 * b.skill)) + (b.boost > 0 ? 380 : 0);
    b.boost = Math.max(0, b.boost - dt);
    // управление
    let tx;
    if (b.isPlayer && C.keyDir()) targetX = C.clamp(targetX + C.keyDir() * 900 * dt, R + 10, LW - R - 10);
    if (b.isPlayer && !window.__auto) tx = targetX;
    else {
      // ИИ: ищет проход в следующем препятствии
      const next = w.obs.find((o) => o.y > b.y + 10);
      if (next && next !== b.aimFor) { b.aimFor = next; b.aimOff = (Math.random() - 0.5) * (1 - b.skill) * 260; }
      if (next && next.y - b.y < 600) {
        if (next.type === 'rot') tx = next.cx < LW / 2 ? next.cx + next.len / 2 + 50 : next.cx - next.len / 2 - 50;
        else if (next.type === 'pegs') tx = b.x;
        else tx = gapCenter(next, w.t + (next.y - b.y) / 600) + b.aimOff;
      } else tx = b.x;
      tx = C.clamp(tx, 40, LW - 40);
    }
    if (b.isPlayer && window.__auto) b.aimOff = 0;
    const steer = b.isPlayer ? 16 : 6 * b.skill;
    const wantVx = C.clamp((tx - b.x) * steer, -950, 950);
    b.vx += (wantVx - b.vx) * Math.min(1, dt * (b.isPlayer ? 14 : 6));
    b.vy = Math.min(vmax, b.vy + 1500 * dt);
    b.x += b.vx * dt; b.y += b.vy * dt;
    b.ang += (b.vy / b.r) * dt * 0.6 + (b.vx / b.r) * dt * 0.4;
    if (b.x < R + 8) { b.x = R + 8; b.vx = Math.abs(b.vx) * 0.3; }
    if (b.x > LW - R - 8) { b.x = LW - R - 8; b.vx = -Math.abs(b.vx) * 0.3; }
    for (const o of w.obs) {
      if (Math.abs(o.y - b.y) > 240) continue;
      if (o.type === 'boost') { const gc = gapCenter(o, w.t); if (Math.abs(b.y - (o.y + 40)) < 30 && Math.abs(b.x - gc) < o.gw / 2) { if (b.boost <= 0 && b.isPlayer) C.sfx('gate'); b.boost = 1.0; } }
      for (const s of segsOf(o, w.t)) {
        const r = collide(b, s, b.isPlayer);
        if (r === 'spike') {
          if (b.isPlayer && (invul > 0)) continue;
          if (b.isPlayer && shield) { shield = false; invul = 1.2; b.vy = -300; C.sfx('hit'); C.burst(b.x + ox, b.y - camY, '#4fc3f7', 18, 400); continue; }
          if (b.isPlayer) { b.dead = true; C.sfx('pop'); C.burst(b.x + ox, b.y - camY, '#ff5252', 26, 520); return; }
          // соперник: откатывается вверх, теряет время
          b.vy = -380; b.vx = (Math.random() - 0.5) * 400; continue;
        }
        if (r === 'hit' && b.isPlayer) C.sfx('bounce', 0.6);
      }
    }
    b.stuckT = Math.abs(b.vy) < 40 ? (b.stuckT || 0) + dt : 0;
    if (b.stuckT > 1.2) { b.stuckT = 0; b.vy = -260; b.vx = (Math.random() < 0.5 ? -1 : 1) * 320; }
    if (b.y >= w.finishY && !b.done) { b.done = true; b.place = ++w.finished; if (b.isPlayer) { placeFx = { place: b.place, t: 0 }; C.sfx('star', 2); } }
  }

  function ballsCollide() {
    const bs = world.balls;
    for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) {
      const a = bs[i], b = bs[j]; if (a.dead || b.dead || a.done || b.done) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy, rr = a.r + b.r; if (d2 >= rr * rr || d2 < 1e-6) continue;
      const d = Math.sqrt(d2), nx = dx / d, ny = dy / d, pen = (rr - d) / 2;
      a.x -= nx * pen; a.y -= ny * pen; b.x += nx * pen; b.y += ny * pen;
      const rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny; if (rv < 0) { const j2 = -rv * 0.8; a.vx -= j2 * nx; a.vy -= j2 * ny; b.vx += j2 * nx; b.vy += j2 * ny; if (a.isPlayer || b.isPlayer) C.sfx('bounce', 0.4); }
    }
  }

  const game = {
    id: 'descent',
    init() { layout(); newRace(C.save.level); },
    resize() { layout(); },
    startLevel(n) { newRace(n); },
    toHome() { newRace(C.save.level); },
    revive() {
      const p = world.balls[0]; p.dead = false; p.vy = 0; p.vx = 0; p.y -= 140;
      const o = world.obs.find((q) => q.y > p.y - 200 && q.y < p.y + 200); if (o && o.type !== 'rot' && o.type !== 'pegs') p.x = gapCenter(o, world.t);
      targetX = p.x; invul = 2.5; endT = -1; endKind = null;
    },
    onDown(x) { touchX = x; },
    onMove(x) { if (touchX === null) return; targetX = C.clamp(targetX + (x - touchX) * 1.25, R + 10, LW - R - 10); touchX = x; },
    onUp() { touchX = null; },

    update(dt) {
      if (!world) return;
      for (const s of stars) { s.y -= (world.balls[0].vy || 120) * dt * s.p * 0.3; if (s.y < -10) s.y += 3000; }
      if (C.state === 'home') { world.t += dt; return; }
      if (C.state !== 'play' && C.state !== 'win' && C.state !== 'fail') return;
      const p = world.balls[0];
      if (countdown > 0) {
        const before = Math.ceil(countdown); countdown -= dt; const after = Math.ceil(countdown);
        if (after !== before && after > 0) C.sfx('tap'); if (countdown <= 0) { C.sfx('gate'); world.started = true; }
        world.t += dt; camY = p.y - C.H * 0.32; return;
      }
      if (C.state === 'fail' && p.dead) return;
      world.t += dt; invul = Math.max(0, invul - dt);
      for (const b of world.balls) if (!b.dead && !b.done) stepBall(b, dt);
      for (const b of world.balls) if (b.done) { const floor = world.finishY + 230; b.vy = Math.max(60, b.vy * 0.94); b.y = Math.min(floor, b.y + b.vy * dt); b.x += (360 + (b.place - 2.5) * 120 - b.x) * dt * 3; if (b.y >= floor) b.vy = 0; }
      ballsCollide();
      for (const b of world.balls) { if (!b.dead) { (b.trail || (b.trail = [])).push([b.x, b.y]); if (b.trail.length > 10) b.trail.shift(); } }
      for (const c of world.coins) {
        if (c.taken) continue; c.x = C.clamp(gapCenter(c.follow, world.t), 50, LW - 50);
        if (Math.hypot(c.x - p.x, c.y - p.y) < R + 26 && !p.dead) { c.taken = true; pickups++; C.sfx('coin'); C.burst(c.x + ox, c.y - camY, '#ffcf2e', 10, 260); }
      }
      if (placeFx) placeFx.t += dt;
      const camT = Math.min(p.y, world.finishY + 230) - C.H * 0.32; camY += (camT - camY) * Math.min(1, dt * 8);
      if (C.state === 'play' && endT < 0) {
        if (p.dead) { endT = 0.8; endKind = 'fail'; }
        else if (p.done) { endT = 1.2; endKind = p.place <= 3 ? 'win' : 'fail'; }
        else if (world.finished >= 3) { endT = 0.6; endKind = 'fail4'; }
      }
      if (endT > 0 && C.state === 'play') {
        endT -= dt;
        if (endT <= 0) {
          if (endKind === 'win') { const st = 4 - p.place; C.win({ stars: st, place: p.place, coins: 15 + st * 10 + pickups * 2 }); }
          else C.fail({ revive: endKind === 'fail' });
        }
      }
    },

    draw(ctx) {
      layout();
      const g = ctx.createLinearGradient(0, 0, 0, C.H); g.addColorStop(0, '#1a1446'); g.addColorStop(1, '#3b1b6e');
      ctx.fillStyle = g; ctx.fillRect(0, 0, C.W, C.H);
      for (let i = 0; i < 3; i++) { const nx = C.W * (0.2 + 0.35 * i) + Math.sin(C.realT * 0.2 + i) * 60, ny = (((i * 700 - camY * 0.15) % (C.H + 600)) + C.H + 600) % (C.H + 600) - 300; const ng = ctx.createRadialGradient(nx, ny, 10, nx, ny, 380); ng.addColorStop(0, ['rgba(255,64,129,0.28)', 'rgba(0,229,255,0.22)', 'rgba(124,77,255,0.3)'][i]); ng.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = ng; ctx.fillRect(nx - 380, ny - 380, 760, 760); }
      ctx.fillStyle = 'rgba(255,255,255,0.5)'; for (const s of stars) { const y = ((s.y % C.H) + C.H) % C.H; ctx.fillRect((s.x % C.W), y, s.s, s.s); }
      if (!world) return;
      ctx.save(); ctx.translate(ox, -camY);
      // трасса — труба
      const top = camY - 50, bot = camY + C.H + 50;
      ctx.fillStyle = 'rgba(255,255,255,0.06)'; ctx.fillRect(0, top, LW, bot - top);
      ctx.fillStyle = 'rgba(124,77,255,0.3)'; ctx.fillRect(-14, top, 30, bot - top); ctx.fillRect(LW - 16, top, 30, bot - top);
      ctx.fillStyle = '#b388ff'; ctx.fillRect(-4, top, 10, bot - top); ctx.fillRect(LW - 6, top, 10, bot - top);
      // линии разметки
      ctx.strokeStyle = 'rgba(255,255,255,0.05)'; ctx.lineWidth = 4;
      for (let yy = Math.floor(top / 120) * 120; yy < bot; yy += 120) { ctx.beginPath(); ctx.moveTo(20, yy); ctx.lineTo(LW - 20, yy + 60); ctx.stroke(); }
      // финиш
      if (world.finishY > top - 60 && world.finishY < bot + 60) {
        for (let i = 0; i < 24; i++) for (let j = 0; j < 2; j++) { ctx.fillStyle = (i + j) % 2 ? '#000' : '#fff'; ctx.fillRect(i * 30, world.finishY + j * 30, 30, 30); }
        ctx.fillStyle = '#ffb300'; ctx.fillRect(0, world.finishY + 256, LW, 24); ctx.fillStyle = '#ffe082'; ctx.fillRect(0, world.finishY + 256, LW, 6);
      }
      // препятствия
      for (const o of world.obs) {
        if (o.y < top - 300 || o.y > bot + 300) continue;
        if (o.type === 'boost') {
          const gc = gapCenter(o, world.t);
          ctx.fillStyle = 'rgba(0,230,118,0.25)'; ctx.fillRect(gc - o.gw / 2, o.y + 14, o.gw, 60);
          ctx.fillStyle = '#00e676'; for (let k = 0; k < 3; k++) { const yy = o.y + 24 + k * 18 + ((C.realT * 60) % 18); ctx.beginPath(); ctx.moveTo(gc - 20, yy); ctx.lineTo(gc, yy + 12); ctx.lineTo(gc + 20, yy); ctx.lineTo(gc + 20, yy + 6); ctx.lineTo(gc, yy + 18); ctx.lineTo(gc - 20, yy + 6); ctx.fill(); }
        }
        for (const s of segsOf(o, world.t)) drawSeg(ctx, s);
        if (o.type === 'rot') { ctx.fillStyle = '#ffd54f'; ctx.beginPath(); ctx.arc(o.cx, o.y, 14, 0, 7); ctx.fill(); }
      }
      for (const c of world.coins) if (!c.taken && c.y > top && c.y < bot) { ctx.save(); ctx.translate(c.x, c.y); ctx.scale(Math.abs(Math.cos(C.realT * 3 + c.y)) * 0.8 + 0.2, 1); C.icon('coin', 0, 0, 46); ctx.restore(); }
      // следы
      for (const b of world.balls) if (!b.dead && b.trail) for (let i = 0; i < b.trail.length; i++) { const k = i / b.trail.length; ctx.fillStyle = b.isPlayer ? 'rgba(255,255,255,' + k * 0.3 + ')' : 'rgba(0,229,255,' + k * 0.18 + ')'; ctx.beginPath(); ctx.arc(b.trail[i][0], b.trail[i][1], b.r * (0.3 + 0.6 * k), 0, 7); ctx.fill(); }
      // шарики
      for (const b of world.balls) {
        if (b.dead) continue;
        if (b.isPlayer && (shield || invul > 0)) { ctx.strokeStyle = shield ? 'rgba(79,195,247,0.9)' : 'rgba(255,255,255,' + (0.4 + 0.4 * Math.sin(C.realT * 20)) + ')'; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(b.x, b.y, b.r + 10, 0, 7); ctx.stroke(); }
        if (b.boost > 0) { ctx.fillStyle = 'rgba(0,230,118,0.35)'; ctx.beginPath(); ctx.moveTo(b.x - b.r, b.y); ctx.lineTo(b.x, b.y - b.r * 4); ctx.lineTo(b.x + b.r, b.y); ctx.fill(); }
        C.drawBall(b.x, b.y, b.r, b.skin, b.ang, ctx, b.isPlayer ? 'rgba(255,255,255,0.9)' : null);
        if (b.done) { ctx.fillStyle = b.place === 1 ? '#ffc107' : b.place === 2 ? '#b0bec5' : b.place === 3 ? '#d7955b' : '#78909c'; ctx.beginPath(); ctx.arc(b.x, b.y - b.r - 18, 17, 0, 7); ctx.fill(); C.text(String(b.place), b.x, b.y - b.r - 17, 22, '#fff', 'center', null); }
      }
      ctx.restore();
      if (placeFx) { const k = C.easeOutBack(Math.min(1, placeFx.t / 0.4)); ctx.save(); ctx.translate(C.W / 2, C.H * 0.45); ctx.scale(k, k); C.text('#' + placeFx.place, 0, 0, 150, placeFx.place === 1 ? '#ffc107' : placeFx.place <= 3 ? '#fff' : '#ff5252'); ctx.restore(); }
    },

    hud(ctx) {
      C.drawCoinsHud();
      const w = world, p = w.balls[0];
      // текущее место
      const order = w.balls.slice().sort((a, b) => (a.done && b.done ? a.place - b.place : a.done ? -1 : b.done ? 1 : b.y - a.y));
      const place = order.indexOf(p) + 1;
      ctx.fillStyle = 'rgba(0,0,0,0.35)'; C.rr(ctx, C.W / 2 - 70, 30, 140, 64, 32); ctx.fill();
      C.text('#' + place, C.W / 2, 64, 42, place === 1 ? '#ffc107' : '#fff');
      // полоса прогресса справа
      const x = C.W - 40, y0 = 150, y1 = C.H - 200;
      ctx.fillStyle = 'rgba(255,255,255,0.15)'; C.rr(ctx, x - 6, y0, 12, y1 - y0, 6); ctx.fill();
      for (const b of w.balls.slice().reverse()) { const k = C.clamp((b.y - 300) / (w.finishY - 300), 0, 1); C.drawBall(x, y0 + k * (y1 - y0), b.isPlayer ? 20 : 14, b.skin, 0, ctx); }
      if (C.state !== 'play') return;
      if (countdown > 0) {
        const n = Math.ceil(countdown); const f = countdown - Math.floor(countdown);
        ctx.save(); ctx.translate(C.W / 2, C.H * 0.42); ctx.scale(1 + f * 0.4, 1 + f * 0.4); C.text(String(n), 0, 0, 170, '#fff'); ctx.restore();
        if (!shield && !shieldUsed && C.rewardedSupported && C.button('shieldBtn', C.W / 2 - 170, C.H * 0.62, 340, 130, { color: '#039be5', pulse: true, draw: () => { C.icon('ad', -70, -2, 60); C.icon('shield', 40, -2, 70, '#b3e5fc'); } })) {
          countdown = Math.max(countdown, 1.5);
          C.ads.rewarded('start_shield').then((ok) => { if (ok) { shield = true; shieldUsed = true; C.sfx('buy'); } });
        }
        // подсказка управления: палец влево-вправо
        const hx = C.W / 2 + Math.sin(C.realT * 3) * 120, hy = C.H * 0.84;
        ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.beginPath(); ctx.ellipse(hx, hy, 26, 36, 0, 0, 7); ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(C.W / 2 - 160, hy + 60); ctx.lineTo(C.W / 2 + 160, hy + 60); ctx.stroke();
      }
    },
  };

  function drawSeg(ctx, s) {
    ctx.lineCap = 'round';
    if (s.k === 'peg') { ctx.fillStyle = 'rgba(255,64,129,0.25)'; ctx.beginPath(); ctx.arc(s.ax, s.ay, s.th / 2 + 10, 0, 7); ctx.fill(); ctx.fillStyle = '#ff4081'; ctx.beginPath(); ctx.arc(s.ax, s.ay, s.th / 2, 0, 7); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.5)'; ctx.beginPath(); ctx.arc(s.ax - 5, s.ay - 5, 6, 0, 7); ctx.fill(); return; }
    if (s.k === 'spike' || s.k === 'spike2') {
      const dx = s.bx - s.ax, dy = s.by - s.ay, L = Math.hypot(dx, dy); if (L < 2) return; const ux = dx / L, uy = dy / L;
      const n = Math.max(1, Math.floor(L / 24));
      ctx.strokeStyle = 'rgba(255,23,68,0.25)'; ctx.lineWidth = 34; ctx.beginPath(); ctx.moveTo(s.ax, s.ay); ctx.lineTo(s.bx, s.by); ctx.stroke();
      ctx.strokeStyle = '#ff1744'; ctx.lineWidth = 12; ctx.beginPath(); ctx.moveTo(s.ax, s.ay); ctx.lineTo(s.bx, s.by); ctx.stroke();
      ctx.fillStyle = '#eceff1';
      const sides = s.k === 'spike2' ? [1, -1] : [1];
      for (const sd of sides) { let nx = uy * sd, ny = -ux * sd; if (s.k === 'spike' && ny > 0) { nx = -nx; ny = -ny; }
        for (let i = 0; i < n; i++) { const t0 = (i / n) * L, t1 = ((i + 1) / n) * L, tm = (t0 + t1) / 2;
          ctx.beginPath(); ctx.moveTo(s.ax + ux * t0, s.ay + uy * t0); ctx.lineTo(s.ax + ux * tm + nx * 22, s.ay + uy * tm + ny * 22); ctx.lineTo(s.ax + ux * t1, s.ay + uy * t1); ctx.fill(); } }
      return;
    }
    ctx.strokeStyle = 'rgba(0,229,255,0.22)'; ctx.lineWidth = s.th + 22; ctx.beginPath(); ctx.moveTo(s.ax, s.ay); ctx.lineTo(s.bx, s.by); ctx.stroke();
    ctx.strokeStyle = '#00e5ff'; ctx.lineWidth = s.th; ctx.beginPath(); ctx.moveTo(s.ax, s.ay); ctx.lineTo(s.bx, s.by); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,0.4)'; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(s.ax, s.ay - 4); ctx.lineTo(s.bx, s.by - 4); ctx.stroke();
  }

  window.__dbg = () => ({ world, targetX });
  C.run(game);
})();
