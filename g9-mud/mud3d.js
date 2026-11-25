'use strict';
/* Грязь 3D — логика без рисования (её же гоняют проверки в Node).
   Грузовик на четырёх колёсах с подвеской едет по карте высот: трава, дорога, грязевая колея, болото, ручей с бродом, лес.
   Полный привод, блокировка дифференциалов, пониженная передача, лебёдка за деревья, топливо.
   Единицы: метры, секунды, килограммы. Мир: Y вверх. Кузов: вперёд +Z, влево +X, вверх +Y. */
(function (root) {
  const DT = 1 / 120, G = 9.81;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v), lerp = (a, b, t) => a + (b - a) * t;
  const sst = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]], sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2], cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const len = (a) => Math.hypot(a[0], a[1], a[2]), norm = (a) => { const l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
  const qrot = (q, v) => { const u = [q[0], q[1], q[2]], t = mul(cross(u, v), 2); return add(add(v, mul(t, q[3])), cross(u, t)); };

  // ---------- местность ----------
  function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6d2b79f5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function noise2(seed) {
    const R = rng(seed), P = new Float32Array(4096); for (let i = 0; i < 4096; i++) P[i] = R();
    const at = (ix, iz) => P[((ix * 73856093) ^ (iz * 19349663)) & 4095];
    return (x, z) => { const ix = Math.floor(x), iz = Math.floor(z), fx = x - ix, fz = z - iz, ux = fx * fx * (3 - 2 * fx), uz = fz * fz * (3 - 2 * fz); return lerp(lerp(at(ix, iz), at(ix + 1, iz), ux), lerp(at(ix, iz + 1), at(ix + 1, iz + 1), ux), uz); };
  }
  function distPoly(pts, x, z) { // расстояние до ломаной
    let best = 1e9;
    for (let i = 1; i < pts.length; i++) { const ax = pts[i - 1][0], az = pts[i - 1][1], ex = pts[i][0] - ax, ez = pts[i][1] - az, t = clamp(((x - ax) * ex + (z - az) * ez) / (ex * ex + ez * ez), 0, 1), d = Math.hypot(x - ax - ex * t, z - az - ez * t); if (d < best) best = d; }
    return best;
  }

  // карта 400×400 м: старт (гараж) на северо-западе, лесопилка на юго-востоке. Сухая дорога идёт в объезд (длинно), грязевая колея — напрямик через болото (коротко).
  function makeMap(seed) {
    const N = 161, C = 2.5, SIZE = (N - 1) * C, yW = 2.6;
    const n1 = noise2(seed), n2 = noise2(seed + 7), n3 = noise2(seed + 13);
    const H = new Float32Array(N * N), M = new Float32Array(N * N), K = new Uint8Array(N * N); // высота, мягкость грязи 0..1, вид: 0 трава, 1 дорога, 2 колея, 3 площадка, 4 берег
    const start = { x: 60, z: 60 }, goal = { x: 330, z: 322, r: 13 }, swamp = { x: 190, z: 200 };
    const road = [[60, 60], [150, 55], [245, 85], [335, 150], [352, 250], [330, 322]];
    const trail = [[60, 60], [120, 115], [190, 200], [270, 275], [330, 322]];
    const washes = [[197, 70, 24], [343, 282, 22]]; // размытые места на дороге: без полного привода и пониженной не проехать
    const creek = [[400, 172], [345, 205], [300, 240], [268, 283], [235, 340], [205, 400]];
    const smooth = (x, z, dc, dr, dt) => lerp(5.5 + 10 * n1(x / 95, z / 95), yW + 0.7, 1 - sst(10, 42, dc)) - (dr < 9 ? 0.95 : dt < 9 ? 1.15 : 2.8) * (1 - sst(1.5, 8, dc));
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const x = i * C, z = j * C, k = j * N + i, dc = distPoly(creek, x, z), dr = distPoly(road, x, z), dt = distPoly(trail, x, z), ds = Math.hypot(x - swamp.x, z - swamp.z);
      let h = smooth(x, z, dc, dr, dt) + 3.0 * (n2(x / 37, z / 37) - 0.5) * sst(10, 42, dc) + 0.45 * (n3(x / 11, z / 11) - 0.5), m = 0, kind = 0;
      const wS = 1 - sst(48, 85, ds); // болото: ровная низина, чем ближе к середине — тем мягче
      if (wS > 0) { h = lerp(h, 4.3 + 0.22 * n3(x / 6, z / 6), wS); m = wS * (0.5 + 0.5 * n2(x / 11 + 3, z / 11 + 7)); }
      const wT = 1 - sst(4.5, 9, dt); // старая колея: грязно, но накатано — в болоте по ней мягкость не выше 0,56
      if (wT > 0) { h = lerp(h, wS > 0 ? h : smooth(x, z, dc, dr, dt), wT * 0.7); m = lerp(m, clamp(Math.max(m, 0.42), 0, 0.56), wT); if (wT > 0.5) kind = 2; }
      const wR = 1 - sst(3.5, 9, dr); // дорога: твёрдая и ровная
      if (wR > 0) { h = lerp(h, smooth(x, z, dc, dr, dt), wR); m *= 1 - wR; if (wR > 0.5) kind = 1; }
      for (const q of washes) { const wW = 1 - sst(q[2] * 0.55, q[2], Math.hypot(x - q[0], z - q[1])); if (wW > 0) { m = Math.max(m, 0.52 * wW); if (wW > 0.4) kind = 2; } }
      for (const p of [start, goal]) { const wP = 1 - sst(13, 24, Math.hypot(x - p.x, z - p.z)); if (wP > 0) { h = lerp(h, 5.5 + 10 * n1(p.x / 95, p.z / 95), wP); m *= 1 - wP; if (wP > 0.5) kind = 3; } }
      if (dc < 15 && kind === 0) kind = 4;
      H[k] = h; M[k] = m; K[k] = kind;
    }
    const bil = (A, x, z) => { const fx = clamp(x / C, 0, N - 1.001), fz = clamp(z / C, 0, N - 1.001), i = Math.floor(fx), j = Math.floor(fz), u = fx - i, v = fz - j, k = j * N + i; return lerp(lerp(A[k], A[k + 1], u), lerp(A[k + N], A[k + N + 1], u), v); };
    const h = (x, z) => bil(H, x, z), mud = (x, z) => bil(M, x, z);
    // деревья: лесом по шуму, редкие сухие стволы в болоте (за них цепляется лебёдка)
    const R = rng(seed + 99), trees = [], cell = 8, grid = new Map(), key = (x, z) => Math.floor(x / cell) * 1000 + Math.floor(z / cell);
    const near = (x, z, r, cb) => { for (let cx = Math.floor((x - r) / cell); cx <= Math.floor((x + r) / cell); cx++) for (let cz = Math.floor((z - r) / cell); cz <= Math.floor((z + r) / cell); cz++) { const a = grid.get(cx * 1000 + cz); if (a) for (const t of a) cb(t); } };
    for (let n = 0; n < 5200 && trees.length < 900; n++) {
      const x = 8 + R() * (SIZE - 16), z = 8 + R() * (SIZE - 16), m = mud(x, z), dead = m > 0.25;
      if (distPoly(road, x, z) < 7.5 || distPoly(trail, x, z) < 8.5 || distPoly(creek, x, z) < 7 || Math.hypot(x - start.x, z - start.z) < 25 || Math.hypot(x - goal.x, z - goal.z) < 25) continue;
      if (dead ? R() > 0.16 || m > 0.92 : n2(x / 60 + 5, z / 60 + 9) < 0.4 + 0.25 * R()) continue;
      let ok = true; near(x, z, 3.2, (t) => { if (Math.hypot(t.x - x, t.z - z) < 3.2) ok = false; }); if (!ok) continue;
      const t = { x, z, y: h(x, z), r: 0.28 + R() * 0.16, s: 0.8 + R() * 0.7, dead, kind: R() < 0.45 ? 1 : 0 };
      trees.push(t); const kk = key(x, z); let a = grid.get(kk); if (!a) grid.set(kk, (a = [])); a.push(t);
    }
    // вдоль колеи через болото — сухие стволы по обе стороны, шагом 14 м: всегда есть за что зацепить лебёдку
    for (let i = 1; i < trail.length; i++) { const ax = trail[i - 1][0], az = trail[i - 1][1], ex = trail[i][0] - ax, ez = trail[i][1] - az, L = Math.hypot(ex, ez); for (let d = 7, n = 0; d < L; d += 14, n++) { const x0 = ax + (ex * d) / L, z0 = az + (ez * d) / L; if (mud(x0, z0) < 0.45) continue; const sd = n & 1 ? 1 : -1, x = x0 + (-ez / L) * 7.5 * sd, z = z0 + (ex / L) * 7.5 * sd, t = { x, z, y: h(x, z), r: 0.34, s: 1.15, dead: true, kind: 1, post: true }; trees.push(t); const kk = key(x, z); let a = grid.get(kk); if (!a) grid.set(kk, (a = [])); a.push(t); } }
    const normal = (x, z) => { const e = 0.7; return norm([h(x - e, z) - h(x + e, z), 2 * e, h(x, z - e) - h(x, z + e)]); };
    return { N, C, SIZE, H, M, K, yW, h, mud, normal, trees, near, start: { x: start.x, z: start.z, yaw: Math.atan2(road[1][0] - road[0][0], road[1][1] - road[0][1]) }, goal, road, trail, creek, swamp, washes };
  }
  // проверочная площадка: высота и грязь — формулами
  function testMap(o) {
    const h = o.h || (() => 0), mud = o.mud || (() => 0), trees = o.trees || [];
    return { SIZE: 1e6, yW: o.yW === undefined ? -100 : o.yW, h, mud, trees, normal: (x, z) => { const e = 0.5; return norm([h(x - e, z) - h(x + e, z), 2 * e, h(x, z - e) - h(x, z + e)]); }, near: (x, z, r, cb) => trees.forEach(cb), start: { x: 0, z: 0, yaw: 0 }, goal: { x: 1e9, z: 0, r: 1 }, road: [[0, 0], [0, 1]] };
  }

  const TRUCKS = [
    // лёгкий 4×4: масса, база, колея, радиус колеса, ход подвески, жёсткость и амортизатор, тяга на обычной передаче (Н), множитель пониженной, мощность (Вт), скорости
    { id: 'scout', mass: 2600, wb: 3.0, track: 1.9, r: 0.55, rest: 0.45, k: 46000, c: 5200, my: -0.2, Fpk: 7500, lowMul: 2.2, P: 95000, vmax: 12, vLow: 6.5, steerMax: 0.6, tank: 80, len: 4.6, wid: 2.0, belly: -0.5, top: 1.25, grip: 1 },
  ];

  function create(o) {
    o = o || {};
    const map = o.map || makeMap(o.seed || 7), TR = Object.assign({}, TRUCKS[o.truck | 0], o.cfg);
    const M = TR.mass, N0 = (M * G) / 4, I = [(M / 12) * (1.4 * 1.4 + TR.len * TR.len), (M / 12) * (TR.wid * TR.wid + TR.len * TR.len), (M / 12) * (TR.wid * TR.wid + 1.4 * 1.4)];
    const S = { map, cfg: TR, t: 0, state: 'play', why: '', p: [0, 0, 0], q: [0, 0, 0, 1], v: [0, 0, 0], w: [0, 0, 0], thr: 0, steer: 0, speed: 0, fuel: TR.tank, awd: false, lock: false, low: false,
      wheels: [], winch: null, target: null, flood: 0, flipT: 0, stuckT: 0, rescues: 0, events: [], belly: false, flag: false, wonT: 0, deadT: 0, mudNow: 0 };
    const hw = TR.track / 2, hb = TR.wb / 2, H0 = TR.r + TR.rest - N0 / TR.k - TR.my; // высота центра масс над землёй в покое
    // колёса: 0 — переднее левое, 1 — переднее правое, 2 — заднее левое, 3 — заднее правое
    S.wheels = [[hw, TR.my, hb], [-hw, TR.my, hb], [hw, TR.my, -hb], [-hw, TR.my, -hb]].map((m, i) => ({ m, front: i < 2, comp: N0 / TR.k, sink: 0, dig: 0, slip: 0, air: false, N: N0, spin: 0, len: TR.rest - N0 / TR.k, mud: 0, wet: 0, pc: [0, 0, 0], drv: false }));
    const body = [[0.85, TR.belly, hb + 0.55], [-0.85, TR.belly, hb + 0.55], [0.85, TR.belly, -hb - 0.55], [-0.85, TR.belly, -hb - 0.55], [0, TR.belly, 0.75], [0, TR.belly, -0.75], [0, TR.belly, 0],
      [0.85, TR.top, 1.3], [-0.85, TR.top, 1.3], [0.85, TR.top, -1.9], [-0.85, TR.top, -1.9]]; // точки кузова: днище (первые 7) и крыша

    S.place = (x, z, yaw) => { S.p = [x, map.h(x, z) + H0 + 0.05, z]; S.q = [0, Math.sin(yaw / 2), 0, Math.cos(yaw / 2)]; S.v = [0, 0, 0]; S.w = [0, 0, 0]; S.thr = 0; S.steer = 0; S.winch = null; S.flood = 0; S.flipT = 0; S.stuckT = 0; for (const w of S.wheels) { w.sink = 0; w.dig = 0; w.comp = N0 / TR.k; } };
    S.yaw = () => { const f = qrot(S.q, [0, 0, 1]); return Math.atan2(f[0], f[2]); };
    // эвакуация: на ближайшую точку дороги, носом вдоль неё
    S.rescue = () => {
      let best = null, bd = 1e9; const R = map.road;
      for (let i = 1; i < R.length; i++) { const ax = R[i - 1][0], az = R[i - 1][1], ex = R[i][0] - ax, ez = R[i][1] - az, t = clamp(((S.p[0] - ax) * ex + (S.p[2] - az) * ez) / (ex * ex + ez * ez), 0, 1), x = ax + ex * t, z = az + ez * t, d = Math.hypot(S.p[0] - x, S.p[2] - z); if (d < bd) { bd = d; best = [x, z, Math.atan2(ex, ez)]; } }
      S.place(best[0], best[1], best[2]); S.state = 'play'; S.rescues++; S.fuel = Math.max(S.fuel, 0.35 * TR.tank); S.events.push({ e: 'rescue' });
    };
    // дерево для лебёдки: ближнее впереди, в пределах 24 м
    S.findTree = () => {
      const bz = qrot(S.q, [0, 0, 1]), hp = add(S.p, mul(bz, TR.len / 2)); let best = null, bs = 1e9;
      map.near(hp[0], hp[2], 24, (t) => { const dx = t.x - hp[0], dz = t.z - hp[2], d = Math.hypot(dx, dz); if (d < 4.5 || d > 24) return; const c = (dx * bz[0] + dz * bz[2]) / d; if (c < 0.25) return; const s = d - 9 * c; if (s < bs) { bs = s; best = t; } });
      return best;
    };

    // один шаг 1/120 с. inp = { drive: -1..1 (газ / назад), steer: -1..1 (+ влево), hb (ручник), winch (держать), awd, lock, low }
    S.step = (inp) => {
      const dt = DT, play = S.state === 'play';
      if (S.state === 'dead') { S.deadT += dt; } if (S.state === 'win') S.wonT += dt;
      S.awd = !!inp.awd; S.lock = !!inp.lock; S.low = !!inp.low;
      const bx = qrot(S.q, [1, 0, 0]), by = qrot(S.q, [0, 1, 0]), bz = qrot(S.q, [0, 0, 1]), vf = dot(S.v, bz);
      S.speed = vf;
      const toW = (m) => [S.p[0] + bx[0] * m[0] + by[0] * m[1] + bz[0] * m[2], S.p[1] + bx[1] * m[0] + by[1] * m[1] + bz[1] * m[2], S.p[2] + bx[2] * m[0] + by[2] * m[1] + bz[2] * m[2]];
      const velAt = (pt) => add(S.v, cross(S.w, sub(pt, S.p)));
      let F = [0, -M * G, 0], Tq = [0, 0, 0];
      const push = (pt, f) => { F = add(F, f); Tq = add(Tq, cross(sub(pt, S.p), f)); };
      // руль: на скорости поворачивает меньше
      const stT = clamp(play ? inp.steer || 0 : 0, -1, 1) * TR.steerMax * (1 - 0.55 * clamp(Math.abs(vf) / TR.vmax, 0, 1));
      S.steer += clamp(stT - S.steer, -2.4 * dt, 2.4 * dt);
      // газ, тормоз, задний ход
      let drive = play && S.fuel > 0 ? clamp(inp.drive || 0, -1, 1) : 0, brake = !play || inp.hb ? 1 : 0;
      if ((drive > 0 && vf < -0.6) || (drive < 0 && vf > 0.6)) { brake = 1; drive = 0; }
      S.thr += (drive - S.thr) * Math.min(1, dt * 5);
      const vTop = (S.low ? TR.vLow : TR.vmax) * (S.thr < 0 ? 0.45 : 1);
      const Fdem = S.thr * Math.min(S.low ? TR.Fpk * TR.lowMul : TR.Fpk, TR.P / Math.max(Math.abs(vf), 1.5)) * (1 - sst(0.88 * vTop, vTop, Math.abs(vf)));
      // колёса: где земля, как сжата подвеска, сколько держит
      const cap = [0, 0, 0, 0], maxT = TR.rest + TR.r; let mudSum = 0;
      S.wheels.forEach((wl, i) => {
        const W0 = toW(wl.m); let t = maxT;
        for (let it = 0; it < 2; it++) { const px = W0[0] - by[0] * t, pz = W0[2] - by[2] * t; t += (W0[1] - by[1] * t - (map.h(px, pz) - wl.sink)) / Math.max(0.35, by[1]); }
        wl.air = t >= maxT || by[1] < 0.2;
        const comp = wl.air ? 0 : Math.min(maxT - t, TR.rest + 0.12), cv = clamp((comp - wl.comp) / dt, -6, 6); wl.comp = comp;
        let N = wl.air ? 0 : Math.max(0, TR.k * comp + TR.c * cv);
        if (comp > TR.rest - 0.05) N += 250000 * (comp - (TR.rest - 0.05)); // отбойник
        wl.N = Math.min(N, N0 * 7); wl.len = Math.min(t, maxT) - TR.r;
        wl.pc = [W0[0] - by[0] * Math.min(t, maxT), W0[1] - by[1] * Math.min(t, maxT), W0[2] - by[2] * Math.min(t, maxT)];
        const m = wl.air ? 0 : map.mud(wl.pc[0], wl.pc[2]); wl.mud = m; mudSum += m;
        wl.wet = clamp(map.yW - (wl.pc[1] + wl.sink), 0, 2);
        cap[i] = (lerp(0.95, 0.4, m) * TR.grip * (wl.wet > 0.05 ? 0.8 : 1)) * wl.N;
        // в грязи колесо уходит вниз: чем мягче и чем больше на нём веса; буксовка закапывает ещё
        const sT = wl.air ? 0 : m * 0.34 * clamp(wl.N / N0, 0.4, 1.7) + wl.dig;
        wl.sink += (sT - wl.sink) * Math.min(1, (wl.air ? 8 : 3) * dt);
      });
      S.mudNow = mudSum / 4;
      // раздача тяги. Задний мост ведёт всегда, передний — с полным приводом (жёстко с задним). Без блокировки мост тянет не сильнее своего худшего колеса.
      // В грязи без блокировки ещё хуже: одно колесо моста буксует впустую.
      const axles = S.awd ? [[0, 1], [2, 3]] : [[2, 3]], capA = axles.map(([a, b]) => (S.lock ? cap[a] + cap[b] : 2 * Math.min(cap[a], cap[b]) * (1 - 0.45 * Math.max(S.wheels[a].mud, S.wheels[b].mud)))), capT = capA.reduce((s, c) => s + c, 0);
      const dem = Math.abs(Fdem), del = Math.min(dem, capT), Fx = [0, 0, 0, 0], sl = [0, 0, 0, 0], over = dem > capT * 0.97 ? clamp((dem - capT) / Math.max(capT, 3000), 0.15, 1.5) : 0;
      S.wheels.forEach((wl) => { wl.drv = false; });
      axles.forEach(([a, b], k) => {
        const FA = capT > 1 ? (del * capA[k]) / capT : 0, c = cap[a] + cap[b]; S.wheels[a].drv = S.wheels[b].drv = true;
        if (S.lock) { if (c > 1) { Fx[a] = (FA * cap[a]) / c; Fx[b] = (FA * cap[b]) / c; } if (over) sl[a] = sl[b] = over; }
        else { Fx[a] = Fx[b] = FA / 2; if (over) { if (cap[a] <= cap[b] * 1.1) sl[a] = over; if (cap[b] <= cap[a] * 1.1) sl[b] = over; } }
      });
      const sg = Math.sign(Fdem);
      // сопротивление грязи по колёсам; на месте сравниваем всю тягу со всем сопротивлением: не хватает — стоим намертво, а не ползём
      let rrT = 0, fxT = 0; const RR = S.wheels.map((wl, i) => { if (wl.air) return 0; const r = wl.N * 0.018 + wl.N * 0.16 * wl.mud + N0 * 1.3 * wl.sink * (0.5 + wl.mud) + N0 * 0.5 * wl.wet; rrT += r; fxT += Fx[i]; return r; });
      const slow = Math.abs(vf) < 0.15, kGo = fxT > rrT ? (fxT - rrT) / fxT : 0;
      S.wheels.forEach((wl, i) => {
        wl.slip = sl[i]; if (wl.air) { wl.spin += (wl.drv ? S.thr * 14 : 0) * dt; return; }
        const n = map.normal(wl.pc[0], wl.pc[2]), cs = Math.cos(wl.front ? S.steer : 0), sn = Math.sin(wl.front ? S.steer : 0);
        const f0 = [bz[0] * cs + bx[0] * sn, bz[1] * cs + bx[1] * sn, bz[2] * cs + bx[2] * sn], f = norm(sub(f0, mul(n, dot(f0, n)))), s = cross(n, f);
        const vc = velAt(wl.pc), vl = dot(vc, f), vs = dot(vc, s), m = wl.mud;
        // сопротивление качению: в грязи и тем более в колее оно растёт; под водой — ещё
        const Rr = RR[i] + (wl.N * 0.16 * m + N0 * 1.3 * wl.sink * (0.5 + m)) * (Math.abs(vl) / 5); // на скорости грязь тормозит сильнее: с разгона далеко не уедешь
        let Fl;
        if (brake) Fl = -clamp(vl * wl.N * 3, -cap[i], cap[i]);
        else if (slow) Fl = Fx[i] * sg * kGo - vl * (kGo > 0 ? 3000 : 45000);
        else Fl = Fx[i] * sg - Math.sign(vl) * Rr;
        if (!brake && Math.abs(S.thr) < 0.05) Fl -= clamp(vl * wl.N * (Math.abs(vf) < 0.6 ? 2.5 : 0.12), -cap[i], cap[i]); // без газа: мотор тормозит, на месте — держит
        const capL = Math.sqrt(Math.max(0, cap[i] * cap[i] - Fx[i] * Fx[i])), Fs = -clamp(vs * wl.N * 2.4, -capL, capL);
        const pa = add(wl.pc, mul(by, 0.3));
        push(pa, add(add(mul(by, wl.N), mul(f, Fl)), mul(s, Fs)));
        // буксуешь в грязи — закапываешься; покатился — колея позади
        if (sl[i] > 0.3 && m > 0.12) wl.dig = Math.min(0.3 * m + 0.04, wl.dig + 0.05 * (sl[i] - 0.3) * (0.4 + m) * dt); else wl.dig *= 1 - Math.min(1, (Math.abs(vl) * dt) / 1.2);
        wl.spin += (vl / TR.r + sl[i] * 9 * (sg || 1)) * dt;
      });
      // кузов: днище и крыша упираются в землю (сел на брюхо — тянет назад), в грязи днище вязнет
      S.belly = false;
      body.forEach((bp, k) => {
        const P = toW(bp), m = map.mud(P[0], P[2]), pen = map.h(P[0], P[2]) - 0.5 * m * 0.34 - P[1]; if (pen <= 0) return;
        const vp = velAt(P), Fn = Math.max(0, (150000 * pen - 9000 * vp[1]) * (1 - 0.6 * m)), vt = [vp[0], 0, vp[2]], sp = Math.hypot(vt[0], vt[2]);
        const fr = sp > 1e-3 ? Math.min((0.7 * Fn) / sp, 60000) + 9000 * m * clamp(pen / 0.2, 0, 1) : 0;
        push(P, [-vt[0] * Math.min(fr, 30000), Fn, -vt[2] * Math.min(fr, 30000)]); if (k < 7) S.belly = true;
      });
      // деревья: кузов (три круга вдоль) не проходит сквозь стволы
      for (const zo of [1.5, 0, -1.5]) { const c = toW([0, 0, zo]); map.near(c[0], c[2], 2, (t) => { const dx = c[0] - t.x, dz = c[2] - t.z, d = Math.hypot(dx, dz), pen = 1.05 + t.r - d; if (pen <= 0 || d < 1e-3) return; const nx = dx / d, nz = dz / d, vp = velAt(c), vn = vp[0] * nx + vp[2] * nz, f = Math.max(0, 260000 * pen - 14000 * vn); push([c[0], S.p[1], c[2]], [nx * f, 0, nz * f]); }); }
      // край карты — мягкая стена
      if (map.SIZE < 1e5) for (const k of [0, 2]) { if (S.p[k] < 6) F[k] += (6 - S.p[k]) * 60000; else if (S.p[k] > map.SIZE - 6) F[k] -= (S.p[k] - map.SIZE + 6) * 60000; }
      // лебёдка: держишь кнопку — трос цепляется за дерево впереди и выбирается; отпустил — отцепился
      S.target = play && !S.winch ? S.findTree() : null;
      if (play && inp.winch && !S.winch && S.target) { const hp = toW([0, -0.15, TR.len / 2]), a = [S.target.x, S.target.y + 1.0, S.target.z]; S.winch = { a, L: len(sub(a, hp)), t: S.target }; S.events.push({ e: 'hook' }); }
      if (S.winch && (!inp.winch || !play)) { S.winch = null; S.events.push({ e: 'unhook' }); }
      if (S.winch) {
        const hp = toW([0, -0.15, TR.len / 2]), d = sub(S.winch.a, hp), dist = len(d), dir = mul(d, 1 / (dist || 1));
        S.winch.L = Math.max(3, Math.min(S.winch.L, dist + 0.02) - 0.85 * dt); S.winch.hp = hp;
        const ext = dist - S.winch.L; if (ext > 0) push(hp, mul(dir, Math.min(75000, 160000 * ext + 12000 * Math.max(0, -dot(velAt(hp), dir)))));
        if (S.winch.L <= 3.01 && dist < 3.6) { S.winch = null; S.events.push({ e: 'unhook' }); }
      }
      // вода тормозит кузов
      const wd = clamp(map.yW - (S.p[1] - 0.6), 0, 1.2); if (wd > 0) { F = add(F, mul(S.v, -2600 * wd)); F[1] += 3500 * wd; }
      // движение
      S.v = add(S.v, mul(F, dt / M));
      const tb = [dot(Tq, bx) / I[0], dot(Tq, by) / I[1], dot(Tq, bz) / I[2]];
      S.w = add(S.w, mul(add(add(mul(bx, tb[0]), mul(by, tb[1])), mul(bz, tb[2])), dt));
      if (S.lock && Math.abs(vf) > 0.3) { const wy = dot(S.w, by), k = 1 - Math.min(0.5, 1.6 * dt * (1 - S.mudNow)); S.w = add(S.w, mul(by, wy * (k - 1))); } // с блокировкой на твёрдом хуже поворачивает
      S.v = mul(S.v, 1 - 0.03 * dt); S.w = mul(S.w, 1 - 1.4 * dt);
      S.p = add(S.p, mul(S.v, dt));
      const hq = [S.w[0] * dt * 0.5, S.w[1] * dt * 0.5, S.w[2] * dt * 0.5], q = S.q;
      const nq = [q[0] + hq[0] * q[3] + hq[1] * q[2] - hq[2] * q[1], q[1] + hq[1] * q[3] + hq[2] * q[0] - hq[0] * q[2], q[2] + hq[2] * q[3] + hq[0] * q[1] - hq[1] * q[0], q[3] - hq[0] * q[0] - hq[1] * q[1] - hq[2] * q[2]], ql = Math.hypot(nq[0], nq[1], nq[2], nq[3]);
      S.q = [nq[0] / ql, nq[1] / ql, nq[2] / ql, nq[3] / ql];
      S.t += dt;
      if (!play) return;
      // топливо: помощники жгут больше
      S.fuel = Math.max(0, S.fuel - (0.02 + Math.abs(S.thr) * 0.26 * (S.awd ? 1.3 : 1) * (S.lock ? 1.25 : 1) * (S.low ? 1.15 : 1)) * dt);
      S.stuckT = Math.abs(inp.drive || 0) > 0.5 && Math.abs(vf) < 0.35 && !S.winch ? S.stuckT + dt : Math.max(0, S.stuckT - 3 * dt);
      S.flipT = by[1] < 0.2 ? S.flipT + dt : 0;
      const ik = toW([0, 0.15 + (TR.snorkel || 0), 1.3]); S.flood = ik[1] < map.yW && map.h(ik[0], ik[2]) < map.yW ? S.flood + dt : 0; // воздухозаборник: глубже метра с небольшим — мотор зальёт
      if (!S.flag && map.swamp && Math.hypot(S.p[0] - map.swamp.x, S.p[2] - map.swamp.z) < 11) { S.flag = true; S.events.push({ e: 'flag' }); } // флажок посреди болота — для третьей звезды
      const die = (why) => { S.state = 'dead'; S.why = why; S.deadT = 0; S.winch = null; S.events.push({ e: 'dead', why }); };
      if (S.flipT > 2.2) die('flip'); else if (S.flood > 0.9) die('water'); else if (S.fuel <= 0 && Math.abs(vf) < 0.3) die('fuel');
      else if (Math.hypot(S.p[0] - map.goal.x, S.p[2] - map.goal.z) < map.goal.r && Math.abs(vf) < 2.5) { S.state = 'win'; S.wonT = 0; S.events.push({ e: 'win' }); }
    };

    S.place(map.start.x, map.start.z, map.start.yaw);
    return S;
  }

  root.MudSim = { create, makeMap, testMap, TRUCKS, DT };
})(typeof window !== 'undefined' ? window : globalThis);
