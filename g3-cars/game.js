'use strict';
/* Игра 3: «Машины и аварии» — держишь палец = газ. Холмы, трамплины, ящики, топливо, перевороты. */
(function () {
  const C = window.Core;
  let Z = 0.72;              // масштаб мира (на телефоне крупнее)
  const GRAV = 1400, GAIR = 950, STEP = 10; // в полёте гравитация мягче — успеваешь сделать трюк
  let touchGas = false, T = null, car = null, camX = 0, camY = 0, gas = false, endT = -1, endKind = null, pickups = 0, crashFx = 0, startHint = 0, revived = false;
  // трюки: время в воздухе, накопленный поворот, серия, монеты за трюки, нитро, всплывашки
  let airT = 0, airRot = 0, combo = 0, stunt = 0, nitro = 0, pops = [], rivals = [], raceT = 0, finishT = -1, place = 1, hint = null, Zd = 0.98, curZ = 0.98, cxk = 0.3, cyk = 0.47, lastLandSpeed = 0;
  const TX = {
    ru: { rel: 'Отпусти — машина выровняется', hold: 'Держи — сальто!', go: 'Отпусти!' },
    en: { rel: 'Release to level out', hold: 'Hold to flip!', go: 'Release!' },
    es: { rel: 'Suelta para nivelar', hold: '¡Mantén para girar!', go: '¡Suelta!' },
    pt: { rel: 'Solte para nivelar', hold: 'Segure para girar!', go: 'Solte!' },
    de: { rel: 'Loslassen zum Ausrichten', hold: 'Halten für Salto!', go: 'Loslassen!' },
    fr: { rel: 'Relâche pour te redresser', hold: 'Maintiens pour un salto !', go: 'Relâche !' },
    tr: { rel: 'Bırak, düzelsin', hold: 'Takla için basılı tut!', go: 'Bırak!' },
  };
  const TT = TX[(C.lang || 'en').slice(0, 2)] || TX.en;
  const wrap = (a) => { a = (a + Math.PI) % (Math.PI * 2); if (a < 0) a += Math.PI * 2; return a - Math.PI; };
  const RIVAL_PAL = [['#64b5f6', '#1e88e5', '#0d47a1', '#0a2f6b'], ['#fff176', '#fdd835', '#c79a00', '#8a6a00']];
  const MY_PAL = ['#ff6f61', '#e53935', '#9e1c1c', '#7f1515'];
  const hills = Array.from({ length: 8 }, (_, i) => ({ x: i * 420, h: 120 + Math.random() * 160 }));

  const up = () => C.save.extra.up || (C.save.extra.up = { eng: 0, tire: 0, tank: 0 });
  const UPG = [{ k: 'eng', icon: 'bolt', col: '#ff7043' }, { k: 'tire', icon: 'tire', col: '#5c6bc0' }, { k: 'tank', icon: 'fuel', col: '#e53935' }];
  const price = (l) => Math.round(100 * Math.pow(l + 1, 1.5) / 10) * 10;

  // ---------- трасса ----------
  function makeTrack(n) {
    const rng = C.seeded(500 + n * 31);
    const len = 9000 + Math.min(9000, (n - 1) * 1500);
    const amp = 0.8 + (n - 1) * 0.12;
    const A = [120 * amp, 60 * amp, 22 * amp], F = [0.0016, 0.0041, 0.011], P = [rng() * 6, rng() * 6, rng() * 6];
    const jumps = []; let ji = 0;
    for (let x = 1300; x < len - 1600; ji++) {
      const big = n >= 2 && ji % 2 === 1;
      if (big) { jumps.push({ x, big, h: 110, w: 300, L: 1200, D: 460 + Math.min(220, n * 22) }); x += 1900 + rng() * 600; }
      else { jumps.push({ x, big, h: (n === 1 ? 60 : 85) + rng() * 40 + Math.min(60, n * 7), w: 240, L: 560, D: 0 }); x += 1000 + rng() * 800; }
    }
    const x0 = -600, N = Math.ceil((len + 1800 - x0) / STEP);
    const hs = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const x = x0 + i * STEP; const env = C.clamp(x / 1200, 0, 1);
      let y = 900; for (let k = 0; k < 3; k++) y -= A[k] * Math.sin(x * F[k] + P[k]) * env;
      // трамплин: вогнутый подъём (крутой край) и пологий спуск-приземление с ямой, как в Hill Climb
      for (const j of jumps) {
        const d = x - j.x;
        if (d > -j.w && d <= 0) { const t = 1 + d / j.w; y -= j.h * t * t; }
        else if (d > 0 && d < j.L) { const t = d / j.L, sm = t * t * (3 - 2 * t); y -= j.h * (1 - sm); y += j.big ? j.D * sm : j.h * 0.35 * Math.sin(Math.PI * t); }
        else if (d >= j.L && j.big) y += j.D; // после большого трамплина трасса идёт ниже — как спуск с горы
      }
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
    // монеты дугой над прыжком — подсказывают траекторию и награждают полёт
    for (const j of jumps) { const ly = groundY(tr, j.x), la = Math.atan(-2 * j.h / j.w), v = j.big ? 620 : 560, k = j.big ? 9 : 6; for (let i = 1; i <= k; i++) { const t = i * 0.12; tr.coins.push({ x: j.x + v * Math.cos(la) * t, y: ly + v * Math.sin(la) * t + 0.5 * GAIR * t * t - 60, taken: false }); } }
    // нитро — перед большими трамплинами (с ним дальше летишь и успеваешь сальто), на 1-м уровне — просто на трассе
    tr.nitro = jumps.filter((j) => j.big).map((j) => ({ x: j.x - j.w - 520, y: groundY(tr, j.x - j.w - 520) - 60, taken: false }));
    if (n === 1) tr.nitro.push({ x: 3000, y: groundY(tr, 3000) - 60, taken: false });
    // за финишем — пирамида ящиков, в которую машина влетает на победе
    const fb = groundY(tr, len + 260); for (let col = 0; col < 4; col++) for (let row = 0; row < 4 - col; row++) tr.crates.push({ x: len + 220 + col * 58 + row * 29, y: fb - 30 - row * 58 - col * 2, s: 56, broken: false, fin: true });
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
    const nk = nitro > 0 ? 1 : 0;
    const vmax = (620 + u.eng * 110) * (nk ? 1.4 : 1), acc = (1300 + u.eng * 180) * (nk ? 1.8 : 1), grip = 0.8 + u.tire * 0.08;
    for (let s = 0; s < sub; s++) {
      const gNow = airT > 0.08 ? GAIR : GRAV;
      c.vy += gNow * h;
      let anyContact = false;
      for (const wl of c.wheels) {
        wl.vy += gNow * h;
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
            // мощность плавно падает к максимальной скорости — разгон резкий со старта и без рывка на пределе
            if (vtb < vmax) { const kp = 1 - 0.65 * Math.pow(Math.max(0, vtb) / vmax, 2); const dv = acc * grip * kp * h * 0.5; c.vx += tx * dv; c.vy += ty * dv; wl.vx += tx * dv; wl.vy += ty * dv; }
          } else { const vt = wl.vx * tx + wl.vy * ty; const dv = -vt * 1.2 * h; wl.vx += tx * dv; wl.vy += ty * dv; c.vx += tx * dv * 0.5; c.vy += ty * dv * 0.5; }
          anyContact = true;
        }
        wl.spin += ((wl.vx * Math.cos(c.a) + wl.vy * Math.sin(c.a)) / wl.r) * h;
      }
      // управление наклоном
      if (anyContact) {
        if (gas && c.fuel > 0) c.w -= 0.6 * h;
        const da = wrap(c.a - Math.atan(slope(T, c.x)));
        if (Math.abs(da) < 1.1) c.w -= (da * (da > 0 ? 6 : 2.4) + c.w * 0.9) * h; // не болтается и не «почти переворачивается» на кочках, нос не клюёт
        if (c.w > 3.5) c.w = 3.5;
      } else if (gas && c.fuel > 0) c.w -= (airT < 0.3 ? 5 : T.n === 1 ? 10 : 22) * h;
      else { const tgt = Math.min(0.45, Math.atan(slope(T, c.x + c.vx * 0.25))), da = wrap(c.a - tgt); c.w -= (da * 8 + c.w * 2.6) * h; }
      c.w = C.clamp(c.w, -11, 11);
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
          if (ly === -48 && !c.crashed && invul <= 0) { c.crashed = true; c.why = 'roof ' + airT.toFixed(2) + ' a=' + wrap(c.a - Math.atan(slope(T, c.x))).toFixed(2); }
        }
      }
      // голова-шарик водителя
      const [hx, hy] = rot(c, -8, -56); if (groundY(T, hx) - hy < 20 && invul <= 0 && !c.crashed) { c.crashed = true; c.why = 'head ' + airT.toFixed(2) + ' a=' + wrap(c.a - Math.atan(slope(T, c.x))).toFixed(2) + ' x=' + Math.round(c.x); }
    }
    if (gas && c.fuel > 0) c.fuel = Math.max(0, c.fuel - dt * (7.5 - u.tank * 1.0));
  }
  let invul = 0;

  function newRun(n) {
    T = makeTrack(n); car = newCar(80); camX = car.x; camY = car.y; endT = -1; endKind = null; pickups = 0; crashFx = 0; startHint = 0; revived = false; invul = 0; gas = false;
    airT = 0; airRot = 0; combo = 0; stunt = 0; nitro = 0; pops = []; raceT = 0; finishT = -1; place = 1; hint = null;
    // соперники-страны: едут по той же трассе (призраки, не толкаются)
    const base = Math.min(780, 530 + (n - 1) * 30), sk = C.rivals(2);
    rivals = [0, 1].map((i) => ({ x: 80, y: groundY(T, 80), a: 0, v: 0, base: base * (i ? 0.93 : 1.06), air: false, vx: 0, vy: 0, spin: 0, skin: sk[i], pal: RIVAL_PAL[i], finishT: -1, wheels: [-56, 56].map((lx) => ({ lx, ly: 26, x: 0, y: 0, r: 25, spin: 0 })) }));
  }
  function rivalStep(r, dt) {
    if (!r.air) {
      const sl = slope(T, r.x), ang = Math.atan(sl);
      const vt = C.clamp(r.base * (1 + sl * (sl < 0 ? 0.45 : 0.3)), r.base * 0.5, r.base * 1.3);
      r.v += (vt - r.v) * Math.min(1, dt * 1.6);
      const nx = r.x + r.v * Math.cos(ang) * dt;
      const j = T.jumps.find((q) => r.x <= q.x && nx > q.x);
      if (j) { const la = Math.atan(slope(T, j.x - 8)); r.air = true; r.vx = r.v * Math.cos(la); r.vy = r.v * Math.sin(la); r.x = j.x; r.y = groundY(T, j.x); }
      else { r.x = nx; r.y = groundY(T, r.x); r.a += (ang - r.a) * Math.min(1, dt * 10); }
    } else {
      r.vy += GAIR * dt; r.x += r.vx * dt; r.y += r.vy * dt; r.a += (Math.atan2(r.vy, r.vx) * 0.6 - r.a) * Math.min(1, dt * 4);
      if (r.y >= groundY(T, r.x)) { r.air = false; r.y = groundY(T, r.x); r.v = Math.hypot(r.vx, r.vy) * 0.85; }
    }
    if (r.finishT < 0 && r.x >= T.len) r.finishT = raceT;
  }
  // кузов соперника над точкой касания + колёса для рисования
  function rivalBody(r) {
    const off = 50, b = { x: r.x + Math.sin(r.a) * off, y: r.y - Math.cos(r.a) * off, a: r.a, wheels: r.wheels };
    for (const wl of r.wheels) { const [wx, wy] = rot(b, wl.lx, wl.ly); wl.x = wx; wl.y = wy; wl.spin += (r.v / 25) * 0.016; }
    return b;
  }
  function pop(kind, n, add) { pops.push({ kind, n, add, t: 0, x: car.x, y: car.y - 120 }); }
  // приземление: сальто, «чисто», долгий полёт
  const landLog = [];
  function land() {
    landLog.push(Math.round(airT * 100) / 100 + (Math.abs(airRot) > 5.5 ? 'F' : ''));
    const da = Math.abs(wrap(car.a - Math.atan(slope(T, car.x))));
    const flips = Math.floor((Math.abs(airRot) + 0.9) / (Math.PI * 2));
    if (flips >= 1 && da < 0.9) { // сальто засчитывается только при приземлении на колёса
      combo++; const add = 10 * flips * combo; stunt += add; nitro = Math.max(nitro, 1.0 + 0.7 * flips);
      pop('flip', flips, add); C.sfx('win'); crashFx = 0.12;
      if (!C.save.extra.carFlip) { C.save.extra.carFlip = 1; C.persist(); }
    } else if (airT > 1.0 && da < 0.9) { stunt += 4; pop('air', 0, 4); C.sfx('star', 1); }
    if (da < 0.25 && airT > 0.45) { stunt += 3; nitro = Math.max(nitro, 0.7); pop('perfect', 0, 3); C.sfx('gate'); }
    if (lastLandSpeed > 700) crashFx = Math.max(crashFx, 0.18);
    for (let i = 0; i < 14; i++) { const wl = car.wheels[i % 2]; smoke.push({ x: wl.x + C.rnd(-20, 20), y: wl.y + wl.r - 4, vx: C.rnd(-160, 160) + car.vx * 0.2, vy: -C.rnd(60, 220), r: 7, life: 0.9, c: '161,120,92' }); }
  }

  const game = {
    id: 'cars',
    init() { newRun(C.save.level); },
    startLevel(n) { newRun(n); },
    toHome() { newRun(C.save.level); },
    revive() {
      revived = true; const x = car.x; const f = Math.max(car.fuel, 45); car = newCar(x); car.fuel = f; invul = 1.5; endT = -1; endKind = null; combo = 0; airT = 0; airRot = 0; hint = null;
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
      if (window.__autoDrive) gas = window.__autoDrive(car, airT, airRot);
      // подсказки в воздухе (замедление времени): 1-й уровень — «отпусти», дальше — «держи — сальто»
      const flying = airT > 0.12 && !car.crashed && endT < 0;
      hint = null;
      if (flying && C.save.level === 1 && gas && !C.save.extra.carRel) hint = 'rel';
      else if (flying && C.save.level >= 2 && !C.save.extra.carFlip && T.jumps.some((j) => j.big && car.x > j.x - 30 && car.x < j.x + j.L)) hint = Math.abs(airRot) < 4.6 ? 'hold' : 'go';
      const tdt = dt * (hint ? 0.4 : 1);
      if (!car.crashed && endT < 0) physics(tdt);
      raceT += tdt; for (const r of rivals) rivalStep(r, tdt);
      nitro = Math.max(0, nitro - tdt);
      // полёт и приземление
      const touching = car.wheels.some((w) => w.contact);
      if (!touching && !car.crashed) { airT += tdt; airRot += car.w * tdt; lastLandSpeed = Math.hypot(car.vx, car.vy); }
      else { if (airT > 0.3 && !car.crashed) land(); if (airT > 0.3 && C.save.level === 1 && !gas && !C.save.extra.carRel) { C.save.extra.carRel = 1; C.persist(); } airT = 0; airRot = 0; }
      for (const pp of pops) pp.t += dt; pops = pops.filter((pp) => pp.t < 1.4);
      for (const nb of T.nitro) if (!nb.taken && Math.hypot(nb.x - car.x, nb.y - car.y) < 90) { nb.taken = true; nitro = Math.max(nitro, 2.5); C.sfx('gate'); pop('nitro', 0, 0); }
      if (nitro > 0 && Math.random() < 0.9) { const [ex, ey] = rot(car, -96, 4); smoke.push({ x: ex, y: ey, vx: -200 + car.vx * 0.3, vy: C.rnd(-30, 30), r: 9, life: 0.5, c: '255,150,40' }); }
      // ящики, монеты, топливо
      const [hx, hy] = rot(car, 0, -10);
      for (const cr of T.crates) {
        if (cr.broken) continue;
        if (Math.abs(cr.x - hx) < 100 && Math.abs(cr.y - hy) < 70) {
          if (cr.fin) { for (const q of T.crates) if (q.fin && !q.broken) { q.broken = true; pickups += 1; for (let i = 0; i < 5; i++) debris.push({ x: q.x, y: q.y, vx: car.vx * 0.8 + C.rnd(-150, 450), vy: C.rnd(-800, -250), a: 0, va: C.rnd(-12, 12), life: 2 }); } C.sfx('crash', 1); crashFx = 0.3; C.confetti(C.W / 2, C.H * 0.35); continue; }
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
      if (car.still > 1.0 && Math.abs(wrap(car.a - Math.atan(slope(T, car.x)))) > 0.95 && invul <= 0) car.crashed = true;
      if (C.state === 'play' && endT < 0) {
        if (car.crashed) { endT = 0.9; endKind = 'crash'; C.sfx('crash', 1); crashFx = 0.4; combo = 0; }
        else if (car.x >= T.len) { endT = 1.6; endKind = 'win'; C.sfx('star', 2); finishT = raceT; place = 1 + rivals.filter((r) => r.finishT >= 0 && r.finishT <= finishT).length; }
        else if (car.fuel <= 0 && car.still > 1.2) { endT = 0.3; endKind = 'fuel'; }
        else if (car.y > groundY(T, car.x) + 400) { endT = 0.3; endKind = 'crash'; }
      }
      if (endT > 0 && C.state === 'play') {
        endT -= dt; if (endKind === 'win') { gas = true; physics(dt); }
        if (endT <= 0) {
          if (endKind === 'win') {
            const stars = 1 + (place === 1 ? 1 : 0) + (revived ? 0 : 1);
            C.win({ stars, place, coins: 20 + stars * 10 + pickups + stunt });
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
      const zb = C.W < C.H ? 0.98 : 0.8, spd0 = Math.hypot(car.vx, car.vy);
      Zd += (zb * (1 - 0.12 * Math.min(1, spd0 / 900) - (airT > 0.2 ? 0.08 : 0)) - Zd) * 0.04; Z = Zd; curZ = Z;
      cxk = C.W < C.H ? 0.3 : 0.32; cyk = C.W < C.H ? 0.47 : 0.52;
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
      for (const j of T.jumps) if (j.big && j.x + 40 > xL && j.x - j.w - 200 < xR) {
        ctx.lineWidth = 16; ctx.lineCap = 'butt';
        for (let x = j.x - j.w; x < j.x; x += 30) { ctx.strokeStyle = ((x - j.x) / 30 | 0) % 2 ? '#212121' : '#ffd600'; ctx.beginPath(); ctx.moveTo(x, groundY(T, x) + 2); ctx.lineTo(Math.min(j.x, x + 30), groundY(T, Math.min(j.x, x + 30)) + 2); ctx.stroke(); }
        const sx = j.x - j.w - 140, sy = groundY(T, sx); ctx.fillStyle = '#6d4c41'; ctx.fillRect(sx - 5, sy - 150, 10, 150);
        ctx.fillStyle = '#ffd600'; C.rr(ctx, sx - 60, sy - 250, 120, 100, 18); ctx.fill(); ctx.strokeStyle = '#212121'; ctx.lineWidth = 6; ctx.stroke(); flipIcon(ctx, sx, sy - 200, 38);
      }
      for (const nb of T.nitro) if (!nb.taken && nb.x > xL && nb.x < xR) { const yy = nb.y + Math.sin(C.realT * 4) * 6; ctx.fillStyle = '#ffd600'; ctx.beginPath(); ctx.arc(nb.x, yy, 40, 0, 7); ctx.fill(); ctx.strokeStyle = '#ff6d00'; ctx.lineWidth = 6; ctx.stroke(); C.icon('bolt', nb.x, yy, 50, '#ff3d00'); }
      for (const r of rivals) if (r.x > xL - 200 && r.x < xR + 200) { ctx.globalAlpha = 0.92; drawCar(ctx, rivalBody(r), r.skin, r.pal); ctx.globalAlpha = 1; }
      if (nitro > 0) { ctx.save(); ctx.translate(...rot(car, -92, 4)); ctx.rotate(car.a); const fl = 50 + Math.random() * 40; const fg = ctx.createLinearGradient(0, 0, -fl, 0); fg.addColorStop(0, '#fff59d'); fg.addColorStop(0.4, '#ff9100'); fg.addColorStop(1, 'rgba(255,61,0,0)'); ctx.fillStyle = fg; ctx.beginPath(); ctx.moveTo(0, -12); ctx.quadraticCurveTo(-fl * 0.6, -16, -fl, 0); ctx.quadraticCurveTo(-fl * 0.6, 16, 0, 12); ctx.fill(); ctx.restore(); }
      drawCar(ctx, car, C.mySkin(), MY_PAL);
      ctx.restore();
    },

    hud(ctx) {
      C.drawCoinsHud();
      // прогресс до финиша
      const bw = 250, bx = 262, by = 46;
      ctx.fillStyle = 'rgba(0,0,0,0.3)'; C.rr(ctx, bx, by, bw, 30, 15); ctx.fill();
      const k = C.clamp(car.x / T.len, 0, 1); ctx.fillStyle = '#ffca28'; C.rr(ctx, bx + 3, by + 3, (bw - 6) * k, 24, 12); ctx.fill();
      for (const r of rivals) { const rk = C.clamp(r.x / T.len, 0, 1); C.drawBall(bx + 3 + (bw - 6) * rk, by + 15, 14, r.skin, 0, ctx); }
      C.drawBall(bx + 3 + (bw - 6) * k, by + 15, 20, C.mySkin(), 0, ctx);
      // место в гонке и монеты заезда
      const myPlace = 1 + rivals.filter((r) => r.x > car.x).length;
      ctx.fillStyle = myPlace === 1 ? 'rgba(255,179,0,0.92)' : 'rgba(0,0,0,0.4)'; C.rr(ctx, bx + bw - 96, by + 42, 96, 46, 23); ctx.fill();
      C.icon('trophy', bx + bw - 70, by + 65, 28, myPlace === 1 ? '#fff' : '#ffd54f'); C.text('#' + myPlace, bx + bw - 30, by + 66, 30, '#fff');
      C.icon('coin', bx + 18, by + 64, 30); C.text('+' + (pickups + stunt), bx + 40, by + 66, 28, '#ffeb3b', 'left');
      if (nitro > 0) { ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 4; for (let i = 0; i < 10; i++) { const yy = Math.random() * C.H, xx = Math.random() * C.W; ctx.beginPath(); ctx.moveTo(xx, yy); ctx.lineTo(xx - 120 - Math.random() * 120, yy); ctx.stroke(); } }
      // всплывашки трюков
      for (const pp of pops) {
        const sx = C.W * cxk + (pp.x - camX) * curZ, sy = C.H * cyk + (pp.y - camY) * curZ - pp.t * 90, a = Math.min(1, (1.4 - pp.t) * 3), sc = 1 + Math.max(0, 0.25 - pp.t) * 2;
        ctx.save(); ctx.globalAlpha = a; ctx.translate(C.clamp(sx, 160, C.W - 160), C.clamp(sy, 220, C.H - 200)); ctx.scale(sc, sc);
        if (pp.kind === 'flip') { flipIcon(ctx, -70, 0, 44); C.text(pp.n > 1 ? '×' + pp.n : '', -70, 4, 30, '#fff'); C.icon('coin', 0, 0, 44); C.text('+' + pp.add, 58, 2, 46, '#ffeb3b'); if (combo > 1) C.text('x' + combo, 0, 52, 32, '#ff9100'); }
        else if (pp.kind === 'perfect') { C.icon('star', -46, 0, 52); C.text('+' + pp.add, 24, 2, 40, '#b9f6ca'); }
        else if (pp.kind === 'air') { C.icon('up', -46, 0, 46, '#fff'); C.text('+' + pp.add, 24, 2, 40, '#fff'); }
        else if (pp.kind === 'nitro') { C.icon('bolt', 0, 0, 70, '#ffd600'); }
        ctx.restore();
      }
      // подсказка в воздухе
      if (hint) {
        const hy = C.H * 0.3, txt = hint === 'rel' ? TT.rel : hint === 'hold' ? TT.hold : TT.go;
        ctx.fillStyle = 'rgba(0,0,0,0.55)'; C.rr(ctx, C.W / 2 - 300, hy - 60, 600, 120, 30); ctx.fill();
        if (hint === 'hold') flipIcon(ctx, C.W / 2 - 230, hy, 46); else { const k2 = (C.realT * 2) % 1; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(C.W / 2 - 230, hy + 10 - k2 * 30, 22, 30, 0, 0, 7); ctx.fill(); C.icon('up', C.W / 2 - 230, hy - 40 - k2 * 10, 26, '#ffeb3b'); }
        C.text(txt, C.W / 2 + 30, hy, txt.length > 18 ? 34 : 46, hint === 'hold' ? '#ffd54f' : '#fff');
      }
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

  function flipIcon(ctx, x, y, r) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(-C.realT * 6); ctx.strokeStyle = '#ffd54f'; ctx.lineWidth = r * 0.22; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.arc(0, 0, r * 0.7, 0.4, Math.PI * 1.7); ctx.stroke();
    const ax = Math.cos(Math.PI * 1.7) * r * 0.7, ay = Math.sin(Math.PI * 1.7) * r * 0.7; ctx.fillStyle = '#ffd54f'; ctx.beginPath(); ctx.moveTo(ax + r * 0.35, ay - r * 0.05); ctx.lineTo(ax - r * 0.1, ay - r * 0.35); ctx.lineTo(ax - r * 0.12, ay + r * 0.28); ctx.fill(); ctx.restore();
  }
  function drawCrate(ctx, x, y, s, a) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(a);
    ctx.fillStyle = '#c68642'; ctx.fillRect(-s / 2, -s / 2, s, s); ctx.strokeStyle = '#8d5524'; ctx.lineWidth = 6; ctx.strokeRect(-s / 2 + 3, -s / 2 + 3, s - 6, s - 6);
    ctx.beginPath(); ctx.moveTo(-s / 2 + 4, -s / 2 + 4); ctx.lineTo(s / 2 - 4, s / 2 - 4); ctx.moveTo(s / 2 - 4, -s / 2 + 4); ctx.lineTo(-s / 2 + 4, s / 2 - 4); ctx.stroke();
    ctx.restore();
  }
  function drawCar(ctx, c, skin, pal) {
    for (const wl of c.wheels) {
      const [ax, ay] = rot(c, wl.lx, wl.ly - 4);
      ctx.strokeStyle = '#555'; ctx.lineWidth = 10; ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(wl.x, wl.y); ctx.stroke();
    }
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(c.a);
    // водитель — шарик-страна, сидит в открытой машине
    ctx.strokeStyle = '#424242'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(30, -28); ctx.lineTo(18, -50); ctx.stroke();
    C.drawBall(-14, -46, 27, skin, 0, ctx);
    // кузов с арками колёс
    const bg = ctx.createLinearGradient(0, -34, 0, 22); bg.addColorStop(0, pal[0]); bg.addColorStop(0.5, pal[1]); bg.addColorStop(1, pal[2]);
    ctx.fillStyle = bg; ctx.beginPath();
    ctx.moveTo(-84, -6); ctx.lineTo(-80, -28); ctx.lineTo(-44, -30); ctx.lineTo(-38, -20); ctx.lineTo(20, -20); ctx.lineTo(34, -32); ctx.lineTo(62, -30); ctx.lineTo(86, -14); ctx.lineTo(86, 8);
    ctx.lineTo(82, 14); ctx.arc(56, 18, 30, 0, Math.PI, true); ctx.lineTo(-30, 14); ctx.arc(-56, 18, 30, 0, Math.PI, true); ctx.lineTo(-84, 14); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = pal[3]; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.fillRect(-74, -24, 30, 5); ctx.fillRect(38, -26, 22, 5);
    ctx.drawImage(C.flagTex(skin), -18, -12, 34, 22);
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

  window.__dbg = () => ({ landLog, car, T, gas, rivals, stunt, nitro, place, airT, airRot, combo, hint });
  window.__setGas = (v) => { touchGas = v; };
  C.run(game);
})();
