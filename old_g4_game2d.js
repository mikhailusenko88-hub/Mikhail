'use strict';
/* Игра 4: «Растущий шарик» — раннер. Ведёшь шарик через ворота +/×/−/÷, в конце пробиваешь стены-множители. */
(function () {
  const C = window.Core;
  const ROAD = 300, SPEED = 950, F = 620, CAMH = 420, CAMBACK = 520;
  let run = null, phase = 'ready', touchX = null, popups = [], endT = -1, endKind = null, boostUsed = false;

  const radius = (n) => Math.min(95, 26 + 6.5 * Math.sqrt(Math.max(1, n)));
  const OPS = {
    add: (v) => ({ t: '+' + v, good: true, f: (n) => n + v }),
    mul: (v) => ({ t: '×' + v, good: true, f: (n) => n * v }),
    sub: (v) => ({ t: '−' + v, good: false, f: (n) => n - v }),
    div: (v) => ({ t: '÷' + v, good: false, f: (n) => Math.floor(n / v) }),
  };

  function makeRun(n) {
    const rng = C.seeded(300 + n * 13);
    const len = 9000 + (n - 1) * 2500;
    const objs = [];
    const d = Math.min(1, (n - 1) / 6);
    let z = 1400;
    while (z < len - 600) {
      // ворота
      const r = rng();
      let L, Rr;
      const good = () => (rng() < 0.6 ? OPS.add(5 + Math.floor(rng() * 4) * 5) : OPS.mul(2 + (rng() < 0.2 ? 1 : 0)));
      const bad = () => (rng() < 0.65 ? OPS.sub(5 + Math.floor(rng() * (3 + d * 4)) * 5) : OPS.div(2));
      if (r < 0.35 - d * 0.15) { L = good(); Rr = good(); } else { L = good(); Rr = bad(); }
      if (rng() < 0.5) [L, Rr] = [Rr, L];
      objs.push({ type: 'gate', z, L, R: Rr, done: false });
      // монеты
      const cx = (rng() - 0.5) * 400;
      for (let k = 0; k < 6; k++) objs.push({ type: 'coin', z: z + 260 + k * 70, x: cx, taken: false });
      // препятствие
      if (rng() < 0.45 + d * 0.4) objs.push({ type: 'saw', z: z + 600, x0: (rng() - 0.5) * 300, amp: 120 + rng() * 120, w: 1.5 + rng() * 1.5 + d, ph: rng() * 6, done: false });
      z += 900 + rng() * 300;
    }
    // финал: стены-множители
    const vals = []; let v = 20 + n * 10;
    for (let i = 0; i < 10; i++) { vals.push(Math.round(v / 5) * 5); v *= 1.6; }
    vals.forEach((val, i) => objs.push({ type: 'wall', z: len + i * 260, val, mult: [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 7, 10][i], idx: i, broken: false }));
    objs.sort((a, b) => a.z - b.z);
    return { n, len, objs, z: 0, x: 0, num: 10, ang: 0, coins: 0, inv: 0, mult: 1, finale: false, stopZ: null, squash: 0 };
  }

  function proj(x, y, z) { // мир → экран
    const dz = z - (run.z - CAMBACK); if (dz <= 10) return null;
    const s = F / dz; const camX = run.x * 0.55;
    return { x: C.W / 2 + (x - camX) * s, y: C.H * 0.3 + (CAMH - y) * s, s };
  }

  function pop(text, good) { popups.push({ text, good, t: 0 }); }

  const game = {
    id: 'runner',
    init() { run = makeRun(C.save.level); phase = 'ready'; },
    startLevel(n) { run = makeRun(n); phase = 'ready'; popups = []; endT = -1; endKind = null; boostUsed = false; },
    toHome() { run = makeRun(C.save.level); phase = 'ready'; },
    revive() { run.num = 15; run.inv = 1.5; phase = 'run'; endT = -1; endKind = null; pop('+15', true); },
    onDown(x) { touchX = x; if (C.state === 'play' && phase === 'ready') { phase = 'run'; C.sfx('whoosh'); } },
    onMove(x) { if (touchX === null) return; if (phase === 'run') run.x = C.clamp(run.x + (x - touchX) * 1.1, -ROAD + 40, ROAD - 40); touchX = x; },
    onUp() { touchX = null; },

    update(dt) {
      if (!run) return;
      for (const p of popups) p.t += dt; popups = popups.filter((p) => p.t < 1);
      if (C.state !== 'play') return;
      if (phase !== 'run') return;
      run.inv = Math.max(0, run.inv - dt); run.squash = Math.max(0, run.squash - dt * 4);
      const r = radius(run.num);
      const z0 = run.z;
      let speed = SPEED;
      if (run.stopZ !== null) speed = 0;
      run.z += speed * dt; run.ang += (speed / r) * dt;
      for (const o of run.objs) {
        if (o.z < z0 - 200 || o.z > run.z + 200) continue;
        if (o.type === 'gate' && !o.done && z0 < o.z && run.z >= o.z) {
          o.done = true; const op = run.x < 0 ? o.L : o.R; const before = run.num; run.num = Math.max(0, Math.round(op.f(run.num)));
          pop(op.t, op.good); C.sfx(op.good ? 'gate' : 'hit'); run.squash = 1;
          C.burst(C.W / 2, C.H * 0.7, op.good ? '#69f0ae' : '#ff5252', 18, 380); void before;
        }
        if (o.type === 'coin' && !o.taken && Math.abs(o.z - run.z) < 50 && Math.abs(o.x - run.x) < r + 30) { o.taken = true; run.coins++; C.sfx('coin'); }
        if (o.type === 'saw' && !o.done && Math.abs(o.z - run.z) < 40) {
          const sx = o.x0 + Math.sin(C.t * o.w + o.ph) * o.amp;
          if (Math.abs(sx - run.x) < r + 45 && run.inv <= 0) { o.done = true; run.num = Math.max(0, run.num - 15); pop('−15', false); C.sfx('hit'); run.inv = 0.5; C.burst(C.W / 2, C.H * 0.72, '#ffd54f', 20, 420); }
        }
        if (o.type === 'wall' && !o.broken && run.z + r * 0.5 >= o.z && run.stopZ === null) {
          run.finale = true;
          if (run.num >= o.val) { o.broken = true; run.num -= Math.ceil(o.val * 0.5); run.mult = o.mult; C.sfx('crash', 0.6); C.burst(C.W / 2, C.H * 0.6, '#90caf9', 26, 600); pop('×' + o.mult, true); }
          else { run.stopZ = run.z; C.sfx('hit'); endT = 1.0; endKind = 'win'; }
        }
      }
      // кончились стены
      const lastWall = run.objs.filter((o) => o.type === 'wall').pop();
      if (run.z > lastWall.z + 200 && endT < 0) { run.stopZ = run.z; endT = 1.0; endKind = 'win'; }
      if (run.num <= 0 && endT < 0) { endT = 0.6; endKind = 'fail'; C.sfx('pop'); C.burst(C.W / 2, C.H * 0.72, '#ff5252', 30, 520); }
      if (endT > 0 && C.state === 'play') {
        endT -= dt;
        if (endT <= 0) {
          if (endKind === 'win') { const st = run.mult >= 3 ? 3 : run.mult >= 1.5 ? 2 : 1; C.win({ stars: st, coins: Math.round((20 + run.coins * 2) * run.mult) }); }
          else C.fail({ revive: true });
        }
      }
    },

    draw(ctx) {
      const g = ctx.createLinearGradient(0, 0, 0, C.H * 0.32); g.addColorStop(0, '#ff9a8b'); g.addColorStop(1, '#ffd3a5');
      ctx.fillStyle = g; ctx.fillRect(0, 0, C.W, C.H * 0.3 + 2);
      ctx.fillStyle = '#81c784'; ctx.fillRect(0, C.H * 0.3, C.W, C.H);
      ctx.fillStyle = '#a5d6a7'; for (let i = 0; i < 6; i++) { ctx.beginPath(); ctx.ellipse(i * C.W / 5, C.H * 0.3, 120, 40, 0, Math.PI, 0); ctx.fill(); }
      if (!run) return;
      // дорога: полосы от дальних к ближним
      const segL = 220, zStart = Math.floor((run.z - CAMBACK + 40) / segL) * segL, zEnd = run.z + 7000;
      for (let z = zEnd; z >= zStart; z -= segL) {
        const a = proj(-ROAD, 0, z), b = proj(ROAD, 0, z), c2 = proj(ROAD, 0, z - segL), d2 = proj(-ROAD, 0, z - segL);
        if (!a || !c2) continue;
        const stripe = Math.floor(z / segL) % 2;
        const fin = z > run.len - 100;
        ctx.fillStyle = fin ? (stripe ? '#ce93d8' : '#ba68c8') : stripe ? '#90a4ae' : '#78909c';
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(c2.x, c2.y); ctx.lineTo(d2.x, d2.y); ctx.closePath(); ctx.fill();
        ctx.fillStyle = stripe ? '#fff' : '#e53935'; const e1 = proj(-ROAD - 30, 0, z), e2 = proj(-ROAD - 30, 0, z - segL), f1 = proj(ROAD + 30, 0, z), f2 = proj(ROAD + 30, 0, z - segL);
        ctx.beginPath(); ctx.moveTo(e1.x, e1.y); ctx.lineTo(a.x, a.y); ctx.lineTo(d2.x, d2.y); ctx.lineTo(e2.x, e2.y); ctx.fill();
        ctx.beginPath(); ctx.moveTo(b.x, b.y); ctx.lineTo(f1.x, f1.y); ctx.lineTo(f2.x, f2.y); ctx.lineTo(c2.x, c2.y); ctx.fill();
      }
      // объекты (дальние сначала), шарик вставляем по глубине
      const r = radius(run.num);
      const list = run.objs.filter((o) => o.z > run.z - CAMBACK + 60 && o.z < zEnd);
      let ballDrawn = false;
      for (let i = list.length - 1; i >= 0; i--) {
        const o = list[i];
        if (!ballDrawn && o.z < run.z) { drawBall(ctx, r); ballDrawn = true; }
        drawObj(ctx, o);
      }
      if (!ballDrawn) drawBall(ctx, r);
      // всплывающие числа
      for (const p of popups) { ctx.save(); ctx.globalAlpha = 1 - p.t; C.text(p.text, C.W / 2, C.H * 0.5 - p.t * 120, 90, p.good ? '#69f0ae' : '#ff5252'); ctx.restore(); }
    },

    hud(ctx) {
      C.drawCoinsHud();
      ctx.fillStyle = 'rgba(0,0,0,0.35)'; C.rr(ctx, C.W / 2 - 60, 30, 120, 64, 32); ctx.fill(); C.text(String(C.save.level), C.W / 2, 64, 40);
      const bw = 360, bx = C.W / 2 - bw / 2, by = 112;
      ctx.fillStyle = 'rgba(0,0,0,0.25)'; C.rr(ctx, bx, by, bw, 18, 9); ctx.fill();
      ctx.fillStyle = '#ffeb3b'; C.rr(ctx, bx + 2, by + 2, (bw - 4) * C.clamp(run.z / run.len, 0, 1), 14, 7); ctx.fill();
      if (C.state !== 'play' || phase !== 'ready') return;
      // старт: буст за рекламу и подсказка «веди пальцем»
      if (!boostUsed && C.rewardedSupported && C.button('boost', C.W / 2 - 170, C.H * 0.42, 340, 130, { color: '#43a047', pulse: true, draw: () => { C.icon('ad', -70, -2, 60); C.text('+30', 50, 0, 56); } })) {
        C.ads.rewarded('start_boost').then((ok) => { if (ok) { boostUsed = true; run.num += 30; pop('+30', true); C.sfx('buy'); } });
      }
      const hx = C.W / 2 + Math.sin(C.realT * 3) * 140, hy = C.H * 0.88;
      ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(C.W / 2 - 170, hy + 50); ctx.lineTo(C.W / 2 + 170, hy + 50); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.strokeStyle = '#333'; ctx.lineWidth = 4; ctx.beginPath(); ctx.ellipse(hx, hy, 28, 38, 0, 0, 7); ctx.fill(); ctx.stroke();
    },
  };

  function drawBall(ctx, r) {
    const p = proj(run.x, r, run.z); if (!p) return;
    const sq = 1 + run.squash * 0.15;
    const rr = r * p.s;
    ctx.fillStyle = 'rgba(0,0,0,0.25)'; const sh = proj(run.x, 0, run.z); ctx.beginPath(); ctx.ellipse(sh.x, sh.y, rr * 0.9, rr * 0.25, 0, 0, 7); ctx.fill();
    if (run.inv > 0 && Math.sin(C.realT * 30) > 0) ctx.globalAlpha = 0.5;
    ctx.save(); ctx.translate(p.x, p.y); ctx.scale(sq, 1 / sq); C.drawBall(0, 0, rr, C.mySkin(), run.ang, ctx); ctx.restore();
    ctx.globalAlpha = 1;
    ctx.fillStyle = 'rgba(0,0,0,0.55)'; C.rr(ctx, p.x - 60, p.y - rr - 70, 120, 56, 28); ctx.fill();
    C.text(String(run.num), p.x, p.y - rr - 41, 42, '#fff', 'center', null);
  }

  function drawObj(ctx, o) {
    if (o.type === 'gate') {
      if (o.done) return;
      for (const side of [-1, 1]) {
        const op = side < 0 ? o.L : o.R;
        const x0 = side < 0 ? -ROAD : 0, x1 = side < 0 ? 0 : ROAD;
        const a = proj(x0 + 10, 260, o.z), b = proj(x1 - 10, 0, o.z); if (!a || !b) continue;
        ctx.fillStyle = op.good ? 'rgba(0,200,83,0.55)' : 'rgba(229,57,53,0.55)'; ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
        ctx.strokeStyle = op.good ? '#00e676' : '#ff1744'; ctx.lineWidth = Math.max(2, 10 * a.s); ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
        C.text(op.t, (a.x + b.x) / 2, (a.y + b.y) / 2, Math.max(10, 120 * a.s), '#fff');
      }
    } else if (o.type === 'coin') {
      if (o.taken) return; const p = proj(o.x, 50, o.z); if (!p) return;
      ctx.save(); ctx.translate(p.x, p.y); ctx.scale(Math.abs(Math.cos(C.realT * 4 + o.z)) * 0.8 + 0.2, 1); C.icon('coin', 0, 0, 90 * p.s); ctx.restore();
    } else if (o.type === 'saw') {
      const sx = o.x0 + Math.sin(C.t * o.w + o.ph) * o.amp; const p = proj(sx, 60, o.z); if (!p) return;
      const rr = 60 * p.s; ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(C.realT * 12);
      ctx.fillStyle = '#b0bec5'; ctx.beginPath(); for (let i = 0; i < 24; i++) { const a = (i / 24) * Math.PI * 2, R2 = i % 2 ? rr : rr * 0.8; ctx.lineTo(Math.cos(a) * R2, Math.sin(a) * R2); } ctx.fill();
      ctx.fillStyle = '#546e7a'; ctx.beginPath(); ctx.arc(0, 0, rr * 0.3, 0, 7); ctx.fill(); ctx.restore();
      const rail1 = proj(-ROAD, 60, o.z), rail2 = proj(ROAD, 60, o.z); ctx.strokeStyle = 'rgba(55,71,79,0.6)'; ctx.lineWidth = Math.max(2, 8 * p.s); ctx.beginPath(); ctx.moveTo(rail1.x, rail1.y); ctx.lineTo(rail2.x, rail2.y); ctx.stroke();
    } else if (o.type === 'wall') {
      if (o.broken) return;
      const a = proj(-ROAD, 70 + o.idx * 26, o.z), b = proj(ROAD, 0, o.z); if (!a || !b) return;
      const hue = 200 - o.idx * 18; ctx.fillStyle = 'hsl(' + hue + ',70%,55%)'; ctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
      ctx.strokeStyle = 'rgba(0,0,0,0.25)'; ctx.lineWidth = Math.max(1, 6 * a.s); ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
      C.text(String(o.val), (a.x + b.x) / 2, a.y + (b.y - a.y) * 0.4, Math.max(10, 70 * a.s), '#fff');
      C.text('×' + o.mult, (a.x + b.x) / 2, a.y + (b.y - a.y) * 0.8, Math.max(8, 44 * a.s), '#ffeb3b');
    }
  }

  window.__dbg = () => ({ run, phase });
  window.__steer = (x) => { if (run) run.x = x; };
  C.run(game);
})();
