'use strict';
/* Игра 3: «Машины и аварии» — держишь палец = газ. Холмы, трамплины, ящики, топливо, перевороты. */
(function () {
  const C = window.Core;
  let Z = 0.72;              // масштаб мира (на телефоне крупнее)
  const GRAV = 1400, STEP = 10;
  let touchGas = false, T = null, car = null, camX = 0, camY = 0, gas = false, endT = -1, endKind = null, pickups = 0, crashFx = 0, startHint = 0, revived = false;
  const hills = Array.from({ length: 8 }, (_, i) => ({ x: i * 420, h: 120 + Math.random() * 160 }));

  const up = () => C.save.extra.up || (C.save.extra.up = { eng: 0, tire: 0, tank: 0 });
  const UPG = [{ k: 'eng', icon: 'bolt', col: '#ff7043' }, { k: 'tire', icon: 'tire', col: '#5c6bc0' }, { k: 'tank', icon: 'fuel', col: '#e53935' }];
  const price = (l) => Math.round(100 * Math.pow(l + 1, 1.5) / 10) * 10;

  // ---------- трасса ----------
  function makeTrack(n) {
    const rng = C.seeded(500 + n * 31);
    const len = 5000 + (n - 1) * 1200;
    const amp = 0.8 + (n - 1) * 0.12;
    const A = [120 * amp, 60 * amp, 22 * amp], F = [0.0016, 0.0041, 0.011], P = [rng() * 6, rng() * 6, rng() * 6];
    const jumps = []; for (let x = 1400; x < len - 600; x += 900 + rng() * 900) jumps.push({ x, h: 70 + rng() * 60 + n * 6, w: 260 });
    const x0 = -600, N = Math.ceil((len + 1800 - x0) / STEP);
    const hs = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const x = x0 + i * STEP; const env = C.clamp(x / 1200, 0, 1);
      let y = 900; for (let k = 0; k < 3; k++) y -= A[k] * Math.sin(x * F[k] + P[k]) * env;
      for (const j of jumps) { const d = x - j.x; if (d > -j.w && d < 0) y -= j.h * (1 + d / j.w); }
      if (x > len) y = Math.min(y, hs[i - 1] || y);
      hs[i] = y;
    }
    const tr = { n, len, x0, hs, crates: [], coins: [], fuel: [], jumps };
    for (let x = 700; x < len - 300; x += 380 + rng() * 420) {
      const k = 1 + Math.floor(rng() * 3); const base = groundY(tr, x);
      for (let i = 0; i < k; i++) tr.crates.push({ x: x + (i % 2) * 6, y: base - 30 - i * 58, s: 56, broken: false });
    }
    for (let x = 500; x < len - 200; x += 600 + rng() * 300) for (let i = 0; i < 5; i++) { const xx = x + i * 60; tr.coins.push({ x: xx, y: groundY(tr, xx) - 90 - Math.sin((i / 4) * Math.PI) * 60, taken: false }); }
    for (let x = 1600; x < len - 200; x += 1700) tr.fuel.push({ x, y: groundY(tr, x) - 50, taken: false });
    return tr;
  }
  function groundY(tr, x) { const f = (x - tr.x0) / STEP; const i = Math.floor(f); if (i < 0) return tr.hs[0]; if (i >= tr.hs.length - 1) return tr.hs[tr.hs.length - 1]; const t = f - i; return tr.hs[i] * (1 - t) + tr.hs[i + 1] * t; }
  function slope(tr, x) { return (groundY(tr, x + 4) - groundY(tr, x - 4)) / 8; }

  // ---------- машина: кузов (твёрдое тело) + 2 колеса на пружинах ----------
  function newCar(x) {
    const y = groundY(T, x) - 70;
    const c = { x, y, vx: 0, vy: 0, a: 0, w: 0, m: 2, I: 3600, fuel: 100, wheels: [], crashed: false, still: 0, dist: 0 };
    for (const lx of [-56, 56]) c.wheels.push({ lx, ly: 26, x: x + lx, y: y + 26, vx: 0, vy: 0, r: 25, spin: 0, contact: false, m: 0.5 });
    return c;
  }
  const rot = (c, lx, ly) => [c.x + lx * Math.cos(c.a) - ly * Math.sin(c.a), c.y + lx * Math.sin(c.a) + ly * Math.cos(c.a)];

  function physics(dt) {
    const c = car, sub = 8, h = dt / sub, u = up();
    const vmax = 620 + u.eng * 110, acc = 1300 + u.eng * 180, grip = 0.8 + u.tire * 0.08;
    for (let s = 0; s < sub; s++) {
      c.vy += GRAV * h;
      let anyContact = false;
      for (const wl of c.wheels) {
        wl.vy += GRAV * h;
        const [ax, ay] = rot(c, wl.lx, wl.ly);
        const avx = c.vx - c.w * (ay - c.y), avy = c.vy + c.w * (ax - c.x);
        const kx = 320 * (ax - wl.x) + 16 * (avx - wl.vx), ky = 320 * (ay - wl.y) + 16 * (avy - wl.vy);
        wl.vx += (kx / wl.m) * h; wl.vy += (ky / wl.m) * h;
        c.vx -= (kx / c.m) * h; c.vy -= (ky / c.m) * h;
        const rx = ax - c.x, ry = ay - c.y; c.w -= ((rx * ky - ry * kx) / c.I) * h;
        wl.x += wl.vx * h; wl.y += wl.vy * h;
        // земля
        const gy = groundY(T, wl.x), sl = slope(T, wl.x), nl = Math.hypot(sl, 1), nx = sl / nl, ny = -1 / nl;
        const pen = wl.r - (gy - wl.y) / nl;
        wl.contact = pen > -2;
        if (pen > 0) {
          wl.x += nx * pen; wl.y += ny * pen;
          const vn = wl.vx * nx + wl.vy * ny; if (vn < 0) { wl.vx -= vn * nx * 1.1; wl.vy -= vn * ny * 1.1; }
          const tx = -ny, ty = nx; // касательная вперёд
          const vtb = c.vx * tx + c.vy * ty;
          if (gas && c.fuel > 0) {
            if (vtb < vmax) { const dv = acc * grip * h * 0.5; c.vx += tx * dv; c.vy += ty * dv; wl.vx += tx * dv; wl.vy += ty * dv; }
          } else { const vt = wl.vx * tx + wl.vy * ty; const dv = -vt * 1.2 * h; wl.vx += tx * dv; wl.vy += ty * dv; c.vx += tx * dv * 0.5; c.vy += ty * dv * 0.5; }
          anyContact = true;
        }
        wl.spin += ((wl.vx * Math.cos(c.a) + wl.vy * Math.sin(c.a)) / wl.r) * h;
      }
      // управление наклоном
      if (gas && c.fuel > 0) c.w -= (anyContact ? 1.4 : 4.2) * h; else if (!anyContact) c.w *= 1 - 0.8 * h;
      c.w = C.clamp(c.w, -5, 5);
      c.x += c.vx * h; c.y += c.vy * h; c.a += c.w * h;
      // кузов о землю (углы)
      for (const [lx, ly] of [[-72, -22], [72, -22], [-72, 18], [72, 18], [-10, -48]]) {
        const [px, py] = rot(c, lx, ly); const gy = groundY(T, px);
        if (py > gy) {
          const sl = slope(T, px), nl = Math.hypot(sl, 1), nx = sl / nl, ny = -1 / nl, pen = (py - gy) / nl;
          c.x += nx * pen * 0.8; c.y += ny * pen * 0.8;
          const rx = px - c.x, ry = py - c.y; const vx = c.vx - c.w * ry, vy = c.vy + c.w * rx; const vn = vx * nx + vy * ny;
          if (vn < 0) { const rn = rx * ny - ry * nx; const j = (-1.2 * vn) / (1 / c.m + (rn * rn) / c.I); c.vx += (j * nx) / c.m; c.vy += (j * ny) / c.m; c.w += (rn * j) / c.I; }
          c.vx *= 1 - 2 * h;
          if (ly === -48 && !c.crashed && invul <= 0) { c.crashed = true; }
        }
      }
      // голова-шарик водителя
      const [hx, hy] = rot(c, -8, -56); if (groundY(T, hx) - hy < 20 && invul <= 0) c.crashed = true;
    }
    if (gas && c.fuel > 0) c.fuel = Math.max(0, c.fuel - dt * (7.5 - u.tank * 1.0));
  }
  let invul = 0;

  function newRun(n) {
    T = makeTrack(n); car = newCar(80); camX = car.x; camY = car.y; endT = -1; endKind = null; pickups = 0; crashFx = 0; startHint = 0; revived = false; invul = 0; gas = false;
  }

  const game = {
    id: 'cars',
    init() { newRun(C.save.level); },
    startLevel(n) { newRun(n); },
    toHome() { newRun(C.save.level); },
    revive() {
      revived = true; const x = car.x; const f = Math.max(car.fuel, 45); car = newCar(x); car.fuel = f; invul = 1.5; endT = -1; endKind = null;
    },
    resultToHome: true,
    onDown() { if (C.state === 'play') touchGas = true; },
    onUp() { touchGas = false; },
    update(dt) {
      for (const hl of hills) { if (hl.x - camX * 0.2 < -500) hl.x += 3360; }
      if (!T) return;
      if (C.state !== 'play') { if (C.state === 'home') { startHint += dt; } return; }
      startHint += dt; invul = Math.max(0, invul - dt);
      gas = touchGas || !!(C.keys.Space || C.keys.ArrowUp || C.keys.ArrowRight || C.keys.KeyW || C.keys.KeyD);
      if (!car.crashed && endT < 0) physics(dt);
      // ящики, монеты, топливо
      const [hx, hy] = rot(car, 0, -10);
      for (const cr of T.crates) {
        if (cr.broken) continue;
        if (Math.abs(cr.x - hx) < 100 && Math.abs(cr.y - hy) < 70) {
          cr.broken = true; C.sfx('crash', 0.5); pickups += 2; car.vx *= 0.9; crashFx = 0.15;
          for (let i = 0; i < 8; i++) debris.push({ x: cr.x, y: cr.y, vx: car.vx * 0.6 + C.rnd(-200, 300), vy: C.rnd(-600, -200), a: 0, va: C.rnd(-10, 10), life: 1.6 });
        }
      }
      for (const cn of T.coins) if (!cn.taken && Math.hypot(cn.x - hx, cn.y - hy) < 80) { cn.taken = true; pickups++; C.sfx('coin'); }
      for (const f of T.fuel) if (!f.taken && Math.hypot(f.x - hx, f.y - hy) < 90) { f.taken = true; car.fuel = 100; C.sfx('buy'); }
      for (let i = debris.length - 1; i >= 0; i--) { const d = debris[i]; d.vy += GRAV * dt; d.x += d.vx * dt; d.y += d.vy * dt; d.a += d.va * dt; d.life -= dt; if (d.y > groundY(T, d.x) - 10) { d.y = groundY(T, d.x) - 10; d.vy *= -0.3; d.vx *= 0.7; } if (d.life <= 0) debris.splice(i, 1); }
      crashFx = Math.max(0, crashFx - dt);
      if (gas && car.fuel > 0 && Math.random() < 0.6) { const [ex, ey] = rot(car, -92, 4); smoke.push({ x: ex, y: ey, vx: -60 + car.vx * 0.2, vy: -40, r: 6, life: 1, c: '200,200,200' }); }
      const spd = Math.hypot(car.vx, car.vy);
      for (const wl of car.wheels) if (wl.contact && spd > 160 && Math.random() < 0.5) smoke.push({ x: wl.x - 10, y: wl.y + wl.r - 6, vx: -car.vx * 0.15 + C.rnd(-30, 30), vy: -C.rnd(40, 120), r: 5, life: 0.8, c: '161,120,92' });
      for (let i = smoke.length - 1; i >= 0; i--) { const sm = smoke[i]; sm.x += sm.vx * dt; sm.y += sm.vy * dt; sm.r += 14 * dt; sm.life -= dt * 1.2; if (sm.life <= 0) smoke.splice(i, 1); }
      if (smoke.length > 120) smoke.splice(0, smoke.length - 120);
      camX += (car.x + 120 - camX) * Math.min(1, dt * 5); camY += (car.y - 60 - camY) * Math.min(1, dt * 4);
      car.dist = car.x;
      const speed = Math.hypot(car.vx, car.vy);
      car.still = speed < 30 ? car.still + dt : 0;
      if (car.still > 1.0 && Math.abs(car.a) > 0.95 && invul <= 0) car.crashed = true;
      if (C.state === 'play' && endT < 0) {
        if (car.crashed) { endT = 0.9; endKind = 'crash'; C.sfx('crash', 1); crashFx = 0.4; }
        else if (car.x >= T.len) { endT = 1.0; endKind = 'win'; C.sfx('star', 2); }
        else if (car.fuel <= 0 && car.still > 1.2) { endT = 0.3; endKind = 'fuel'; }
        else if (car.y > groundY(T, car.x) + 400) { endT = 0.3; endKind = 'crash'; }
      }
      if (endT > 0 && C.state === 'play') {
        endT -= dt; if (endKind === 'win') { gas = true; physics(dt); }
        if (endT <= 0) {
          if (endKind === 'win') {
            const broken = T.crates.filter((c) => c.broken).length;
            const stars = 1 + (broken >= T.crates.length * 0.5 ? 1 : 0) + (revived ? 0 : 1);
            C.win({ stars, coins: 20 + stars * 10 + pickups * 2 });
          } else C.fail({ revive: true });
        }
      }
    },

    draw(ctx) {
      const g = ctx.createLinearGradient(0, 0, 0, C.H); g.addColorStop(0, '#2f9cf0'); g.addColorStop(0.6, '#a8dcff'); g.addColorStop(1, '#fff1d6');
      ctx.fillStyle = g; ctx.fillRect(0, 0, C.W, C.H);
      const sx = C.W * 0.78, sy = C.H * 0.14; const sg = ctx.createRadialGradient(sx, sy, 20, sx, sy, 200); sg.addColorStop(0, 'rgba(255,250,220,1)'); sg.addColorStop(0.2, 'rgba(255,240,170,0.9)'); sg.addColorStop(1, 'rgba(255,240,170,0)'); ctx.fillStyle = sg; ctx.beginPath(); ctx.arc(sx, sy, 200, 0, 7); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      for (let i = 0; i < 6; i++) { const cx = ((i * 260 - camX * 0.05 * Z) % (C.W + 400) + C.W + 400) % (C.W + 400) - 200, cy = C.H * (0.12 + (i % 3) * 0.07); ctx.beginPath(); ctx.ellipse(cx, cy, 80, 26, 0, 0, 7); ctx.ellipse(cx + 40, cy - 16, 50, 30, 0, 0, 7); ctx.fill(); }
      // дальние горы со снегом
      for (const hl of hills) { const x = ((hl.x - camX * 0.12 * Z) % 3360 + 3360) % 3360 - 400; ctx.fillStyle = '#8fa6d6'; ctx.beginPath(); ctx.moveTo(x - 300, C.H * 0.6); ctx.lineTo(x, C.H * 0.6 - hl.h - 60); ctx.lineTo(x + 300, C.H * 0.6); ctx.fill(); ctx.fillStyle = '#f5f8ff'; ctx.beginPath(); ctx.moveTo(x - 60, C.H * 0.6 - hl.h + 2); ctx.lineTo(x, C.H * 0.6 - hl.h - 60); ctx.lineTo(x + 60, C.H * 0.6 - hl.h + 2); ctx.fill(); }
      // ближние холмы с деревьями
      ctx.fillStyle = '#7cc576'; ctx.beginPath(); ctx.moveTo(0, C.H);
      for (let x = 0; x <= C.W + 20; x += 20) { const wx = x + camX * 0.3 * Z; ctx.lineTo(x, C.H * 0.62 - 50 - Math.sin(wx * 0.006) * 40 - Math.sin(wx * 0.017) * 14); }
      ctx.lineTo(C.W, C.H); ctx.fill();
      for (let i = 0; i < 12; i++) { const wx = Math.floor((camX * 0.3 * Z) / 90) * 90 + i * 90, x = wx - camX * 0.3 * Z; if (((wx / 90) | 0) % 3 === 0) continue; const y = C.H * 0.62 - 50 - Math.sin(wx * 0.006) * 40 - Math.sin(wx * 0.017) * 14; ctx.fillStyle = '#5d4037'; ctx.fillRect(x - 3, y - 18, 6, 20); ctx.fillStyle = '#4c9a48'; ctx.beginPath(); ctx.moveTo(x - 18, y - 12); ctx.lineTo(x, y - 60); ctx.lineTo(x + 18, y - 12); ctx.fill(); }
      if (!T) return;
      const shake = crashFx > 0 ? (Math.random() - 0.5) * 16 * crashFx * 4 : 0;
      Z = C.W < C.H ? 0.98 : 0.8; const cxk = C.W < C.H ? 0.3 : 0.32, cyk = C.W < C.H ? 0.47 : 0.52;
      ctx.save(); ctx.translate(C.W * cxk + shake, C.H * cyk + shake); ctx.scale(Z, Z); ctx.translate(-camX, -camY);
      const xL = camX - (C.W * cxk) / Z - 40, xR = camX + (C.W * (1 - cxk)) / Z + 40;
      // земля
      ctx.beginPath(); ctx.moveTo(xL, camY + 3000);
      for (let x = xL; x <= xR; x += 12) ctx.lineTo(x, groundY(T, x));
      ctx.lineTo(xR, camY + 3000); ctx.closePath();
      const dg = ctx.createLinearGradient(0, camY - 200, 0, camY + 900); dg.addColorStop(0, '#a1785c'); dg.addColorStop(1, '#5d4037'); ctx.fillStyle = dg; ctx.fill();
      ctx.fillStyle = 'rgba(62,39,35,0.35)';
      for (let x = Math.floor(xL / 70) * 70; x <= xR; x += 70) { const h = Math.sin(x * 12.9898) * 43758.5453, f = h - Math.floor(h); const y = groundY(T, x) + 50 + f * 220; ctx.beginPath(); ctx.ellipse(x + f * 30, y, 10 + f * 14, 6 + f * 8, 0, 0, 7); ctx.fill(); }
      ctx.strokeStyle = '#43a047'; ctx.lineWidth = 26; ctx.lineJoin = 'round'; ctx.beginPath();
      for (let x = xL; x <= xR; x += 12) { const y = groundY(T, x); if (x === xL) ctx.moveTo(x, y + 6); else ctx.lineTo(x, y + 6); } ctx.stroke();
      ctx.strokeStyle = '#7ed957'; ctx.lineWidth = 8; ctx.stroke();
      ctx.fillStyle = '#4caf50';
      for (let x = Math.floor(xL / 26) * 26; x <= xR; x += 26) { const y = groundY(T, x) - 4; ctx.beginPath(); ctx.moveTo(x - 6, y); ctx.lineTo(x - 2, y - 14); ctx.lineTo(x + 2, y); ctx.lineTo(x + 6, y - 10); ctx.lineTo(x + 9, y); ctx.fill(); }
      for (const sm of smoke) { ctx.fillStyle = 'rgba(' + sm.c + ',' + Math.max(0, sm.life) * 0.5 + ')'; ctx.beginPath(); ctx.arc(sm.x, sm.y, sm.r, 0, 7); ctx.fill(); }
      // финиш
      if (T.len > xL && T.len < xR + 200) {
        const fy = groundY(T, T.len); ctx.fillStyle = '#5d4037'; ctx.fillRect(T.len - 5, fy - 260, 10, 260);
        for (let i = 0; i < 6; i++) for (let j = 0; j < 4; j++) { ctx.fillStyle = (i + j) % 2 ? '#000' : '#fff'; ctx.fillRect(T.len + 5 + i * 22, fy - 260 + j * 22 + Math.sin(C.realT * 5 + i) * 3, 22, 22); }
      }
      // монеты, топливо, ящики
      for (const cn of T.coins) if (!cn.taken && cn.x > xL && cn.x < xR) { ctx.save(); ctx.translate(cn.x, cn.y); ctx.scale(Math.abs(Math.cos(C.realT * 3 + cn.x)) * 0.8 + 0.2, 1); C.icon('coin', 0, 0, 56); ctx.restore(); }
      for (const f of T.fuel) if (!f.taken && f.x > xL && f.x < xR) C.icon('fuel', f.x, f.y + Math.sin(C.realT * 4) * 6, 80, '#e53935');
      for (const cr of T.crates) if (!cr.broken && cr.x > xL && cr.x < xR) drawCrate(ctx, cr.x, cr.y, cr.s, 0);
      for (const d of debris) { ctx.save(); ctx.translate(d.x, d.y); ctx.rotate(d.a); ctx.fillStyle = '#c68642'; ctx.fillRect(-14, -5, 28, 10); ctx.restore(); }
      drawCar(ctx, car);
      ctx.restore();
    },

    hud(ctx) {
      C.drawCoinsHud();
      // прогресс до финиша
      const bw = 250, bx = 262, by = 46;
      ctx.fillStyle = 'rgba(0,0,0,0.3)'; C.rr(ctx, bx, by, bw, 30, 15); ctx.fill();
      const k = C.clamp(car.x / T.len, 0, 1); ctx.fillStyle = '#ffca28'; C.rr(ctx, bx + 3, by + 3, (bw - 6) * k, 24, 12); ctx.fill();
      C.drawBall(bx + 3 + (bw - 6) * k, by + 15, 20, C.mySkin(), 0, ctx);
      for (let i = 0; i < 3; i++) { ctx.fillStyle = (i % 2) ? '#000' : '#fff'; ctx.fillRect(bx + bw + 6, by + i * 10, 10, 10); }
      // топливо
      const fx = 30, fy = C.H - 120;
      C.icon('fuel', fx + 30, fy + 30, 60, car.fuel < 25 && Math.sin(C.realT * 10) > 0 ? '#ff1744' : '#e53935');
      ctx.fillStyle = 'rgba(0,0,0,0.3)'; C.rr(ctx, fx + 70, fy + 14, 200, 30, 15); ctx.fill();
      ctx.fillStyle = car.fuel < 25 ? '#ff1744' : '#66bb6a'; C.rr(ctx, fx + 73, fy + 17, 194 * car.fuel / 100, 24, 12); ctx.fill();
      // педаль газа
      if (C.state === 'play') {
        const px = C.W - 190, py = C.H - 230;
        ctx.save(); ctx.globalAlpha = 0.85; ctx.fillStyle = gas ? '#2e7d32' : '#43a047'; C.rr(ctx, px, py + (gas ? 10 : 0), 150, 190, 26); ctx.fill();
        ctx.fillStyle = 'rgba(0,0,0,0.25)'; for (let i = 0; i < 4; i++) ctx.fillRect(px + 22, py + 30 + i * 38 + (gas ? 10 : 0), 106, 14); ctx.restore();
        if (startHint < 5 && car.x < 300) { const k = (C.realT * 1.5) % 1; ctx.strokeStyle = 'rgba(255,255,255,' + (1 - k) + ')'; ctx.lineWidth = 10; ctx.beginPath(); ctx.arc(px + 75, py + 95, 60 + k * 90, 0, 7); ctx.stroke(); const fy = py + 70 + Math.abs(Math.sin(C.realT * 4)) * 20; ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.strokeStyle = '#333'; ctx.lineWidth = 4; ctx.beginPath(); ctx.ellipse(px + 75, fy, 26, 36, 0, 0, 7); ctx.fill(); ctx.stroke(); }
      }
    },

    drawHome(ctx) {
      ctx.fillStyle = 'rgba(10,20,40,0.35)'; ctx.fillRect(0, 0, C.W, C.H);
      C.drawCoinsHud(); C.sideButtons(); C.soundButton(C.W - 106, 30);
      C.text(String(C.save.level), C.W / 2, C.H * 0.2, 100);
      // улучшения
      const u = up(), bw = 200, gap = 18, x0 = C.W / 2 - (bw * 3 + gap * 2) / 2, y = C.H * 0.6;
      UPG.forEach((g2, i) => {
        const lvl = u[g2.k], p = price(lvl), x = x0 + i * (bw + gap), max = lvl >= 5;
        const short = !max && C.save.coins < p, canAd = short && C.rewardedSupported && C.save.coins >= p / 2;
        const id = 'up_' + g2.k;
        if (C.button(id, x, y, bw, 210, { color: max ? '#9e9e9e' : g2.col, pulse: !max && (!short || canAd), draw: () => {
          if (g2.icon === 'tire') { ctx.fillStyle = '#222'; ctx.beginPath(); ctx.arc(0, -50, 38, 0, 7); ctx.fill(); ctx.fillStyle = '#9e9e9e'; ctx.beginPath(); ctx.arc(0, -50, 16, 0, 7); ctx.fill(); }
          else C.icon(g2.icon, 0, -50, 70, '#fff');
          for (let d = 0; d < 5; d++) { ctx.fillStyle = d < lvl ? '#ffeb3b' : 'rgba(255,255,255,0.3)'; ctx.fillRect(-70 + d * 29, 4, 24, 14); }
          if (max) C.icon('check', 0, 58, 44); else if (canAd) { C.icon('ad', -40, 58, 44); C.icon('up', 28, 58, 40); }
          else { C.icon('coin', -48, 58, 38); C.text(String(p), 14, 60, 32, short ? '#ffcdd2' : '#fff'); }
        } })) {
          if (max) return;
          if (C.spend(p)) { u[g2.k]++; C.persist(); C.sfx('buy'); }
          else if (canAd) C.ads.rewarded('upgrade').then((ok) => { if (ok) { u[g2.k]++; C.persist(); C.sfx('buy'); } });
          else { C.sfx('hit'); C.toast('coin', String(p - C.save.coins)); }
        }
      });
      if (C.button('playBtn', C.W / 2 - 170, C.H * 0.78, 340, 150, { color: '#43a047', icon: 'play', iconSize: 80, pulse: true })) C.startLevel();
    },
  };
  const debris = [], smoke = [];

  function drawCrate(ctx, x, y, s, a) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(a);
    ctx.fillStyle = '#c68642'; ctx.fillRect(-s / 2, -s / 2, s, s); ctx.strokeStyle = '#8d5524'; ctx.lineWidth = 6; ctx.strokeRect(-s / 2 + 3, -s / 2 + 3, s - 6, s - 6);
    ctx.beginPath(); ctx.moveTo(-s / 2 + 4, -s / 2 + 4); ctx.lineTo(s / 2 - 4, s / 2 - 4); ctx.moveTo(s / 2 - 4, -s / 2 + 4); ctx.lineTo(-s / 2 + 4, s / 2 - 4); ctx.stroke();
    ctx.restore();
  }
  function drawCar(ctx, c) {
    for (const wl of c.wheels) {
      const [ax, ay] = rot(c, wl.lx, wl.ly - 4);
      ctx.strokeStyle = '#555'; ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(wl.x, wl.y); ctx.stroke();
    }
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.a);
    // водитель — шарик-страна, сидит в открытой машине
    ctx.strokeStyle = '#424242'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(30, -28); ctx.lineTo(18, -50); ctx.stroke();
    C.drawBall(-14, -46, 27, C.mySkin(), 0, ctx);
    // кузов с арками колёс
    const bg = ctx.createLinearGradient(0, -34, 0, 22); bg.addColorStop(0, '#ff6f61'); bg.addColorStop(0.5, '#e53935'); bg.addColorStop(1, '#9e1c1c');
    ctx.fillStyle = bg; ctx.beginPath();
    ctx.moveTo(-84, -6); ctx.lineTo(-80, -28); ctx.lineTo(-44, -30); ctx.lineTo(-38, -20); ctx.lineTo(20, -20); ctx.lineTo(34, -32); ctx.lineTo(62, -30); ctx.lineTo(86, -14); ctx.lineTo(86, 8);
    ctx.lineTo(82, 14); ctx.arc(56, 18, 30, 0, Math.PI, true); ctx.lineTo(-30, 14); ctx.arc(-56, 18, 30, 0, Math.PI, true); ctx.lineTo(-84, 14); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = '#7f1515'; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.fillRect(-74, -24, 30, 5); ctx.fillRect(38, -26, 22, 5);
    ctx.drawImage(C.flagTex(C.mySkin()), -18, -12, 34, 22);
    ctx.fillStyle = '#b3e5fc'; ctx.beginPath(); ctx.moveTo(30, -30); ctx.lineTo(22, -54); ctx.lineTo(28, -54); ctx.lineTo(38, -31); ctx.fill();
    ctx.fillStyle = '#ffee58'; ctx.beginPath(); ctx.ellipse(83, -10, 5, 8, 0, 0, 7); ctx.fill();
    ctx.fillStyle = '#ff1744'; ctx.fillRect(-86, -22, 6, 10);
    ctx.fillStyle = '#616161'; ctx.fillRect(-92, 0, 12, 7);
    ctx.restore();
    for (const wl of c.wheels) {
      ctx.save(); ctx.translate(wl.x, wl.y); ctx.rotate(wl.spin);
      ctx.fillStyle = '#1b1b1b'; ctx.beginPath(); ctx.arc(0, 0, wl.r, 0, 7); ctx.fill();
      ctx.strokeStyle = '#3a3a3a'; ctx.lineWidth = 4; ctx.setLineDash([6, 5]); ctx.beginPath(); ctx.arc(0, 0, wl.r - 3, 0, 7); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#cfd8dc'; ctx.beginPath(); ctx.arc(0, 0, wl.r * 0.56, 0, 7); ctx.fill();
      ctx.strokeStyle = '#78909c'; ctx.lineWidth = 4; for (let k = 0; k < 5; k++) { const a = (k / 5) * Math.PI * 2; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a) * wl.r * 0.5, Math.sin(a) * wl.r * 0.5); ctx.stroke(); }
      ctx.fillStyle = '#455a64'; ctx.beginPath(); ctx.arc(0, 0, 5, 0, 7); ctx.fill();
      ctx.restore();
    }
  }

  window.__dbg = () => ({ car, T, gas });
  window.__setGas = (v) => { touchGas = v; };
  C.run(game);
})();
