'use strict';
/* «Нарисуй путь — гонка стран»: физика и уровни (работает и в браузере, и в node для проверки). */
(function (root) {
  const G = 1500, R = 28, SUB = 6;
  const LW = 720;
  const CUP = (cx, top = 1060, half = 76, depth = 100) => ({ cx, top, half, depth });

  // ---------- уровни ----------
  // seg: {k:'wall'|'spike'|'tramp'|'pad'|'peg'|'ink', ax,ay,bx,by, th}
  // Поле штырьков: штырьки не ближе 56 px к стенкам и друг к другу (шарик не застревает)
  function plinko(y0, rows, dy = 62) {
    const out = [];
    for (let r = 0; r < rows; r++) {
      const xs = r % 2 ? [510, 590] : [470, 550, 630];
      for (const x of xs) out.push({ k: 'peg', ax: x, ay: y0 + r * dy, bx: x, by: y0 + r * dy, th: 18 });
    }
    return out;
  }
  const W = (ax, ay, bx, by, th = 16, k = 'wall') => ({ k, ax, ay, bx, by, th });
  const SP = (ax, ay, bx, by) => ({ k: 'spike', ax, ay, bx, by, th: 14 });
  const SHELF = (x0, x1, y) => [SP(x0, y, x1, y), W(x0, y + 12, x1, y + 12, 10)];
  function cupSegs(c) {
    return [W(c.cx - c.half, c.top, c.cx - c.half, c.top + c.depth, 14), W(c.cx - c.half, c.top + c.depth, c.cx + c.half, c.top + c.depth, 14), W(c.cx + c.half, c.top, c.cx + c.half, c.top + c.depth, 14)];
  }
  const FRAME = [W(8, 0, 8, 1280), W(712, 0, 712, 1280)];
  const LEVELS = [
    // 1: открытое поле — рисуешь горку к финишу
    () => ({
      player: 180, rivals: [470, 560, 650], ink: 1150, cup: CUP(360),
      segs: [...FRAME, W(390, 290, 390, 760), ...plinko(330, 6, 72), W(712, 760, 470, 1000), SP(20, 1250, 270, 1250)],
      coins: [[215, 520], [255, 720], [300, 900]],
      hint: [[170, 300], [215, 520], [262, 730], [315, 1000]],
    }),
    // 2: шипы посередине — обойди справа у стенки
    () => ({
      player: 150, rivals: [470, 560, 650], ink: 1250, cup: CUP(360),
      segs: [...FRAME, W(390, 290, 390, 700), ...plinko(330, 5, 74), W(712, 700, 470, 990), ...SHELF(30, 300, 620), SP(20, 1250, 270, 1250)],
      coins: [[250, 470], [345, 700], [330, 900]],
      hint: [[125, 290], [300, 540]],
    }),
    // 3: финиш на стороне соперников — пройди под стенкой
    () => ({
      player: 160, rivals: [470, 560, 650], ink: 1450, cup: CUP(560, 1090, 90), rivalDelay: 0.7,
      segs: [...FRAME, W(390, 290, 390, 920), ...plinko(330, 7, 74), W(712, 840, 660, 930), W(650, 930, 650, 1090, 14), W(410, 860, 470, 930), SP(20, 1250, 400, 1250)],
      coins: [[200, 600], [280, 950], [400, 1030]],
      hint: [[150, 300], [175, 700], [240, 960], [360, 1040], [450, 1050]],
    }),
    // 4: вниз вдоль стенки, потом вправо — между двумя полками шипов
    () => ({
      player: 100, rivals: [470, 560, 650], ink: 1500, cup: CUP(360),
      segs: [...FRAME, W(390, 290, 390, 700), ...plinko(330, 5, 74), W(712, 700, 470, 990), ...SHELF(170, 382, 430), ...SHELF(10, 240, 900), SP(20, 1250, 270, 1250)],
      coins: [[90, 620], [170, 830], [290, 950]],
      hint: [[60, 290], [95, 620], [120, 760], [180, 840], [270, 880], [330, 990]],
    }),
  ];

  function makeLevel(n, rng) {
    const idx = (n - 1) % LEVELS.length, cycle = Math.floor((n - 1) / LEVELS.length);
    const L = LEVELS[idx]();
    const mirror = cycle % 2 === 1;
    const mx = (x) => (mirror ? LW - x : x);
    const segs = L.segs.concat(cupSegs(L.cup)).map((s) => ({ ...s, ax: mx(s.ax), bx: mx(s.bx) }));
    const balls = [];
    const pad = (x, isPlayer, skin) => {
      const px = mx(x);
      segs.push({ k: 'pad', ax: px - 34, ay: 210 + R + 8, bx: px + 34, by: 210 + R + 8, th: 12, owner: balls.length });
      balls.push({ x: px + (isPlayer ? 0 : (rng() - 0.5) * 6), y: 210, vx: 0, vy: 0, r: R, ang: 0, isPlayer, skin, done: false, dead: false, out: false, place: 0, still: 0 });
    };
    pad(L.player, true, null);
    L.rivals.forEach((x) => pad(x, false, null));
    return {
      n, cycle, segs, balls, rivalDelay: Math.max(0, (L.rivalDelay || 0) - cycle * 0.2), ink: Math.round(L.ink * Math.pow(0.88, cycle)), cup: { ...L.cup, cx: mx(L.cup.cx) },
      coins: L.coins.map(([x, y]) => ({ x: mx(x), y, taken: false })), hint: L.hint.map(([x, y]) => [mx(x), y]),
      line: [], released: false, t: 0, finished: 0, events: [],
    };
  }

  function collideSeg(b, s, ev) {
    const dx = s.bx - s.ax, dy = s.by - s.ay, L2 = dx * dx + dy * dy;
    let t = L2 > 0 ? ((b.x - s.ax) * dx + (b.y - s.ay) * dy) / L2 : 0; t = t < 0 ? 0 : t > 1 ? 1 : t;
    const px = s.ax + dx * t, py = s.ay + dy * t; const ex = b.x - px, ey = b.y - py; const d2 = ex * ex + ey * ey; const rr = b.r + s.th / 2;
    if (d2 >= rr * rr || d2 < 1e-6) return;
    const d = Math.sqrt(d2), nx = ex / d, ny = ey / d;
    b.x += nx * (rr - d); b.y += ny * (rr - d);
    const vn = b.vx * nx + b.vy * ny;
    if (s.k === 'spike' && ny < 0.2) { b.dead = true; ev.push({ e: 'pop', b }); return; }
    if (s.k === 'peg' && ny < -0.85) b.vx += (Math.random() - 0.5) * 90 + (nx >= 0 ? 25 : -25);
    if (vn < 0) {
      let e = s.k === 'peg' ? 0.45 : 0.18;
      if (s.k === 'tramp') e = 1.0;
      b.vx -= (1 + e) * vn * nx; b.vy -= (1 + e) * vn * ny;
      if (s.k === 'tramp') { const vn2 = b.vx * nx + b.vy * ny; if (vn2 < 1150) { b.vx += (1150 - vn2) * nx; b.vy += (1150 - vn2) * ny; } ev.push({ e: 'tramp', b }); }
      if (vn < -260) ev.push({ e: 'hit', b, k: Math.min(1, -vn / 1200) });
    }
  }

  function step(w, dt, cupSensor = true) {
    const h = dt / SUB; const ev = w.events;
    for (let s = 0; s < SUB; s++) {
      if (w.released) w.t += h;
      for (const b of w.balls) {
        if (b.done || b.dead || b.out) continue;
        if (!w.released) continue;
        if (!b.isPlayer && w.t < w.rivalDelay) continue;
        b.vy += G * h;
        const sp = Math.hypot(b.vx, b.vy); if (sp > 2300) { b.vx *= 2300 / sp; b.vy *= 2300 / sp; }
        b.vx *= 1 - 0.05 * h; b.vy *= 1 - 0.02 * h;
        b.x += b.vx * h; b.y += b.vy * h;
        for (const sg of w.segs) { if (sg.k === 'pad' && w.released && (w.t >= w.rivalDelay || sg.owner === 0)) continue; collideSeg(b, sg, ev); if (b.dead) break; }
        if (b.dead) continue;
        if (w.line.length > 1) for (let i = 1; i < w.line.length; i++) collideSeg(b, { k: 'ink', ax: w.line[i - 1][0], ay: w.line[i - 1][1], bx: w.line[i][0], by: w.line[i][1], th: 14 }, ev);
        b.ang += (b.vx / b.r) * h;
        const c = w.cup;
        if (cupSensor && b.x > c.cx - c.half + 4 && b.x < c.cx + c.half - 4 && b.y > c.top - 4 && b.y < c.top + c.depth) {
          b.done = true; b.place = ++w.finished; b.finishT = w.t; b.vx = 0; b.vy = 0; b.sx = b.x; b.sy = b.y; ev.push({ e: 'finish', b });
        }
        if (b.y > 1400 || b.x < -80 || b.x > LW + 80) { b.out = true; ev.push({ e: 'out', b }); }
        if (b.isPlayer) for (const cn of w.coins) if (!cn.taken && Math.hypot(cn.x - b.x, cn.y - b.y) < b.r + 22) { cn.taken = true; ev.push({ e: 'coin', cn }); }
      }
      // столкновения шариков
      const bs = w.balls;
      for (let i = 0; i < bs.length; i++) for (let j = i + 1; j < bs.length; j++) {
        const a = bs[i], b = bs[j]; if (a.dead || b.dead || a.out || b.out || a.done || b.done) continue;
        const dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy, rr = a.r + b.r;
        if (d2 >= rr * rr || d2 < 1e-6) continue;
        const d = Math.sqrt(d2), nx = dx / d, ny = dy / d, pen = (rr - d) / 2;
        const ma = 1, mb = 1;
        const sa = ma && mb ? 0.5 : ma ? 1 : 0, sb = ma && mb ? 0.5 : mb ? 1 : 0;
        a.x -= nx * pen * 2 * sa; a.y -= ny * pen * 2 * sa; b.x += nx * pen * 2 * sb; b.y += ny * pen * 2 * sb;
        const rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
        if (rv < 0) { const j2 = -(1 + 0.5) * rv; if (ma && mb) { a.vx -= (j2 / 2) * nx; a.vy -= (j2 / 2) * ny; b.vx += (j2 / 2) * nx; b.vy += (j2 / 2) * ny; } else if (ma) { a.vx -= j2 * nx; a.vy -= j2 * ny; } else { b.vx += j2 * nx; b.vy += j2 * ny; } }
      }
    }
    for (const b of w.balls) { if (b.done || b.dead || b.out || !w.released) continue; const sp = Math.hypot(b.vx, b.vy); b.still = sp < 12 ? b.still + dt : 0; }
  }

  // линия: проредить точки, посчитать длину
  function lineLength(pts) { let L = 0; for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return L; }
  function densify(pts, stepLen = 14) {
    const out = [pts[0]];
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i]; const L = Math.hypot(x1 - x0, y1 - y0); const n = Math.max(1, Math.round(L / stepLen));
      for (let k = 1; k <= n; k++) out.push([x0 + ((x1 - x0) * k) / n, y0 + ((y1 - y0) * k) / n]);
    }
    return out;
  }

  const api = { G, R, LW, LEVELS, makeLevel, step, lineLength, densify, count: LEVELS.length };
  if (typeof module !== 'undefined') module.exports = api; else root.DRSim = api;
})(typeof window !== 'undefined' ? window : globalThis);
