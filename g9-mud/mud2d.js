'use strict';
/* Грязь, вид сбоку — логика без рисования (её же гоняют проверки в Node).
   Грузовик Hook Truck на бездорожье: грязь разной глубины, броды, подъёмы. Полный привод, блокировка, пониженная, лебёдка за деревья, топливо.
   Единицы — как в Hook Truck: пиксели, Y вниз, 54 px ≈ 1 м. */
(function (root) {
  const P = root.TPhys;
  const MAST = [112, 4];     // лебёдка на переднем бампере: тянет ровно вперёд, грузовик не клюёт носом
  const WR = 27;             // радиус колеса
  const WRANGE = 800;        // докуда достаёт трос
  const REEL = 150;          // лебёдка выбирает трос, px/с
  const MIN_ROPE = 150;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const sst = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

  // ---------- построитель маршрута ----------
  function Route() {
    const S = { polys: [], anchors: [], pits: [], ceils: [], boosts: [], springs: [], star: null, cps: [], fin: 0, minY: 1e9, maxY: -1e9, mud: [], water: [], trees: [], cans: [], marks: [] };
    let x = 0, y = 600; const cur = [];
    const push = (px, py) => { cur.push([px, py]); S.minY = Math.min(S.minY, py); S.maxY = Math.max(S.maxY, py); };
    const B = {
      S,
      get x() { return x; }, get y() { return y; },
      start(x0, y0) { x = x0; y = y0; push(x, y); return B; },
      flat(len) { const n = Math.max(1, Math.round(len / 130)); for (let i = 1; i <= n; i++) push(x + (len * i) / n, y); x += len; return B; },
      slope(len, up, n = 14) { const x0 = x, y0 = y; for (let i = 1; i <= n; i++) { const t = i / n, s = t * t * (3 - 2 * t); push(x0 + len * t, y0 - up * s); } x = x0 + len; y = y0 - up; return B; },
      hill(len, h, n = 14) { const x0 = x; for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y - h * (0.5 - 0.5 * Math.cos(t * Math.PI * 2))); } x = x0 + len; return B; },
      // грязь на ровном месте: d — глубина до твёрдого дна, k — как держит (меньше — глубже тонешь), res — сопротивление на колесо, mu — как гребут колёса
      mud(len, o) { S.mud.push(Object.assign({ x0: x, x1: x + len, d: 40, k: 500, res: 1500, mu: 0.75 }, o)); return B.flat(len); },
      // брод: дно уходит вниз на depth, вода стоит на прежней высоте
      ford(len, depth, n = 16) { const x0 = x, y0 = y; S.water.push({ x0, x1: x + len, y: y0 + 6, depth }); for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y0 + depth * sst(0, 0.3, t) * sst(0, 0.3, 1 - t)); } x = x0 + len; y = y0; return B; },
      tree(dx = 0, h = 78) { S.trees.push({ x: x + dx, gy: y, y: y - h }); return B; },    // дерево для лебёдки: трос цепляется на высоте бампера
      can(dx = 0) { S.cans.push({ x: x + dx, y: y - 44, got: false }); return B; },        // канистра
      mark(dx, kind) { S.marks.push({ x: x + dx, y, kind }); return B; },                  // постройка у дороги: 'garage' | 'mill'
      cp(dx = 0) { S.cps.push({ x: x + dx, y }); return B; },
      fin(dx = 150) { S.fin = x + dx; return B; },
      end(len = 1500) { B.flat(len); S.polys.push(cur); return B; },
    };
    return B;
  }
  const zoneAt = (L, x) => { for (const z of L.mud) if (x > z.x0 && x < z.x1) return z; return null; };
  const edge = (z, x) => sst(0, 170, x - z.x0) * sst(0, 170, z.x1 - x); // края грязи пологие: въезжаешь постепенно

  // o.up — улучшения из гаража: tires (грязевые шины), eng (мотор), snorkel (шноркель), tank (бак)
  function create(routeFn, o) {
    const up = Object.assign({ tires: 0, eng: 0, snorkel: 0, tank: 0 }, o && o.up);
    const CFG = { spHigh: 26, spLow: 11, tqHigh: 95000 * (1 + 0.08 * up.eng), tqLow: 264000 * (1 + 0.08 * up.eng), grip: 1 + 0.12 * up.tires, burn: 0.8, tank: 100 + 20 * up.tank, intake: -30 - 55 * up.snorkel };
    const S = {
      L: null, W: null, truck: null, wheels: [], wj: [], rope: null, ropeA: null, target: null, cfg: CFG,
      state: 'play', t: 0, deadT: 0, why: '', grounded: false, wallTouch: false, flipT: 0, wonT: 0, pullOn: false,
      cp: null, attempts: 1, rescues: 0, events: [], awd: false, lock: false, low: false, fuel: CFG.tank,
      slip: [0, 0], sunk: [0, 0], inMud: 0, belly: false, stuckT: 0, wetT: 0, wade: 0,
    };
    S.L = (typeof routeFn === 'number' ? root.MudSide.routes[routeFn].build : routeFn)();
    const L = S.L, poly = L.polys[0];
    L.mudAt = (x) => { const z = zoneAt(L, x); return z ? edge(z, x) * clamp(z.d / 60, 0.4, 1) : 0; };
    L.mud.forEach((z) => { z.rut = new Float32Array(Math.ceil((z.x1 - z.x0) / 30) + 2); });

    S.groundAt = (x) => { // поверхность: то, что видно (в грязи — верх грязи)
      if (x <= poly[0][0]) return poly[0][1];
      for (let i = 1; i < poly.length; i++) { const a = poly[i - 1], b = poly[i]; if (x <= b[0]) return a[1] + ((b[1] - a[1]) * (x - a[0])) / (b[0] - a[0] || 1); }
      return poly[poly.length - 1][1];
    };
    const bedAt = (x) => { const z = zoneAt(L, x); return S.groundAt(x) + (z ? z.d * edge(z, x) : 0); }; // твёрдое дно
    const rutAt = (z, x) => { const f = clamp((x - z.x0) / 30, 0, z.rut.length - 1.001), i = Math.floor(f); return z.rut[i] + (z.rut[i + 1] - z.rut[i]) * (f - i); };
    const dig = (z, x, v) => { const i = clamp(Math.round((x - z.x0) / 30), 0, z.rut.length - 1), m = Math.max(0, z.d - 34); for (const [k, q] of [[i - 1, 0.5], [i, 1], [i + 1, 0.5]]) if (k >= 0 && k < z.rut.length) z.rut[k] = Math.min(m, z.rut[k] + v * q); };
    S.rutAt = (x) => { const z = zoneAt(L, x); return z ? rutAt(z, x) * edge(z, x) : 0; };
    const waterAt = (x) => L.water.find((w) => x > w.x0 && x < w.x1) || null;

    function buildWorld() {
      const W = (S.W = P.world()), xs = new Set(poly.map((q) => q[0]));
      for (const z of L.mud) { for (let x = z.x0; x < z.x1; x += 45) xs.add(x); xs.add(z.x1); }
      const a = [...xs].sort((p, q) => p - q);
      for (let i = 1; i < a.length; i++) { const xm = (a[i - 1] + a[i]) / 2; P.addStatic(W, a[i - 1], bedAt(a[i - 1]), a[i], bedAt(a[i]), zoneAt(L, xm) ? 0.2 : waterAt(xm) ? 0.5 : 0.9); }
      const p0 = poly[0], p1 = poly[poly.length - 1];
      P.addStatic(W, p0[0], p0[1] + 400, p0[0], p0[1] - 3000); P.addStatic(W, p1[0], p1[1] + 400, p1[0], p1[1] - 3000);
    }

    S.spawn = (x, gy) => {
      buildWorld();
      const W = S.W, y = gy - 82;
      S.truck = P.addBody(W, P.body({
        x, y, m: 8, I: 34000, group: 'truck', kind: 'truck', rad: 190, mu: 0.6, lin: 0.9997, ang: 0.997,
        circles: [{ x: -100, y: 14, r: 13 }, { x: 102, y: 12, r: 13 }, { x: 110, y: -10, r: 10 }, { x: -106, y: -34, r: 10 }, { x: 30, y: -98, r: 10 }, { x: 70, y: -62, r: 13, roof: true }, { x: 30, y: -66, r: 13, roof: true }],
      }));
      S.wheels = []; S.wj = [];
      for (const lx of [-72, 72]) { // 0 — заднее, 1 — переднее
        const w = P.addBody(W, P.body({ x: x + lx, y: y + 48, m: 1.2, I: 440, group: 'truck', kind: 'wheel', mu: 1.0, circles: [{ x: 0, y: 0, r: WR }], ang: 0.999 }));
        S.wheels.push(w); S.wj.push(P.wheelJoint(W, S.truck, w, { lx, ly: 18, rest: 34, k: 1150, c: 70, lo: 10, hi: 44 }));
      }
      S.rope = null; S.ropeA = null; S.state = 'play'; S.deadT = 0; S.flipT = 0; S.wonT = 0; S.grounded = false; S.stuckT = 0; S.wetT = 0;
      for (const z of L.mud) z.rut.fill(0); // колея после возврата — заново: попытка честная
    };
    S.respawn = () => {
      const p = S.cp || { x: poly[0][0] + 320, fuel: CFG.tank };
      S.spawn(p.x, S.groundAt(p.x)); S.fuel = Math.max(p.fuel, 0.7 * CFG.tank); // после эвакуации в баке не меньше 70%: застрять в круге «кончилось топливо» нельзя S.attempts++; S.events.push({ e: 'respawn' });
    };
    S.reset = () => { S.cp = null; S.attempts = 1; S.rescues = 0; S.t = 0; S.fuel = CFG.tank; S.events.length = 0; for (const c of L.cans) c.got = false; S.spawn(poly[0][0] + 320, poly[0][1]); }; // рейс заново
    S.rescue = () => { if (S.state === 'play') { S.rescues++; S.respawn(); } }; // эвакуация: вернуться на последнюю отметку
    S.mast = () => P.wpt(S.truck, MAST[0], MAST[1]);

    // дерево, за которое зацепится лебёдка: ближайшее впереди в пределах троса
    S.findTree = () => {
      const [mx] = S.mast(); let best = null;
      for (const a of L.trees) { const dx = a.x - mx; if (dx > MIN_ROPE + 40 && dx < WRANGE && (!best || a.x < best.x)) best = a; } // слишком близкое дерево не берём: тянуть уже некуда
      return best;
    };
    function hookOn(a) { const [mx, my] = S.mast(); S.rope = P.ropeJoint(S.W, S.truck, MAST[0], MAST[1], a.x, a.y, Math.max(MIN_ROPE, Math.hypot(a.x - mx, a.y - my))); S.ropeA = a; S.events.push({ e: 'hook' }); }
    function hookOff() { if (!S.rope) return; S.W.joints = S.W.joints.filter((j) => j !== S.rope); S.rope = null; S.ropeA = null; S.events.push({ e: 'unhook' }); }

    // силы грязи и воды — после тяжести, до решения контактов
    function soft(dt) {
      const T = S.truck; let R = 0; S.inMud = 0; S.belly = false; S.wade = 0;
      S.wheels.forEach((w, i) => {
        S.sunk[i] = 0; S.slip[i] = 0;
        const z = zoneAt(L, w.x); if (!z) return;
        const e = edge(z, w.x), rut = rutAt(z, w.x) * e, sub = clamp(w.y + WR - (S.groundAt(w.x) + rut), 0, 2 * WR);
        if (sub <= 0 || e < 0.02) return;
        S.inMud++; S.sunk[i] = sub + rut;
        const Fs = z.k * e * sub;                                  // грязь держит колесо: чем глубже, тем сильнее
        w.vy -= (Fs / w.m) * dt; w.vy *= 1 - Math.min(0.9, 5 * dt * (sub / WR));
        const cap = z.mu * CFG.grip * Fs * (S.lock ? 1 : 0.4);       // сколько тяги даёт грязь; без блокировки одно колесо оси буксует впустую
        const sv = w.w * WR - w.vx, th = clamp(sv * 40, -cap, cap);  // колесо гребёт, пока не сорвётся
        w.vx += (th / w.m) * dt; w.w -= ((th * WR) / w.I) * dt;
        S.slip[i] = Math.abs(sv);
        if (Math.abs(sv) > 150 && S.state === 'play') dig(z, w.x, Math.min(0.012 * Math.abs(sv), 6) * dt); // буксуешь — закапываешься
        R += z.res * e * Math.min(1, sub / (0.45 * WR)) * (1 + rut / 70);
      });
      // брюхо легло на грязь: кузов держит, колёса разгружены, тянет назад
      for (const c of [T.circles[0], T.circles[1]]) {
        const [cx, cy] = P.wpt(T, c.x, c.y), z = zoneAt(L, cx); if (!z) continue;
        const e = edge(z, cx), sub = cy + c.r - S.groundAt(cx); if (sub <= 0 || e < 0.02) continue;
        const F = 1000 * sub * e; T.vy -= (F / T.m) * dt; T.w += ((cx - T.x) * -F) / T.I * dt; T.vy *= 1 - Math.min(0.5, 3 * dt);
        R += 3000 * e * Math.min(1, sub / 12); S.belly = true;
      }
      if (R > 0) { // сопротивление грязи: как трение — может остановить совсем; на скорости грязь тормозит сильнее (с разгона далеко не уедешь)
        R *= 1 + Math.abs(T.vx) / 400;
        const M = T.m + S.wheels.reduce((a, w) => a + w.m, 0), dv = (R / M) * dt, k = Math.abs(T.vx) <= dv ? -T.vx : -Math.sign(T.vx) * dv;
        for (const b of [T, ...S.wheels]) b.vx += k;
      }
      // вода: тормозит и чуть держит на плаву
      for (const b of [T, ...S.wheels]) { const wz = waterAt(b.x); if (!wz) continue; const r = b === T ? 34 : WR, s = clamp((b.y + r - wz.y) / (2 * r), 0, 1); if (s > 0) { b.vx *= 1 - 1.5 * s * dt; b.vy *= 1 - 1.2 * s * dt; b.vy -= P.G * 0.22 * s * dt; if (b !== T) S.wade = Math.max(S.wade, s); } }
    }

    // один шаг 1/120 с; inp = { gas, brake, winch (держать), awd, lock, low (включено/выключено) }
    S.step = (inp) => {
      const dt = P.DT, T = S.truck;
      if (S.state === 'dead') { S.deadT += dt; if (S.deadT > 1.7) S.respawn(); }
      const play = S.state === 'play';
      S.awd = !!inp.awd; S.lock = !!inp.lock; S.low = !!inp.low;
      // лебёдка: держишь — трос цепляется за ближайшее дерево впереди и тянет; отпустил — отцепился
      S.target = play && !S.rope ? S.findTree() : null;
      if (play && inp.winch && !S.rope && S.target) hookOn(S.target);
      if (S.rope && (!inp.winch || !play)) hookOff();
      S.pullOn = false;
      if (S.rope) {
        const [mx, my] = S.mast(), d = Math.hypot(mx - S.rope.px, my - S.rope.py);
        if (d < S.rope.len) S.rope.len = Math.max(MIN_ROPE, d);
        if (S.rope.len > MIN_ROPE) { S.rope.len = Math.max(MIN_ROPE, S.rope.len - REEL * dt); S.pullOn = true; }
        else hookOff(); // подтянулись к дереву — трос отцепляется сам; держишь кнопку дальше — цепляется за следующее
      }
      // мотор: задний мост всегда, передний — с полным приводом; пониженная — вдвое больше тяги, вдвое меньше скорость
      const g = play && inp.gas && S.fuel > 0, br = play && !g && inp.brake;
      const [fx, fy] = P.wvec(T, 1, 0), fwd = T.vx * fx + T.vy * fy, sp = S.low ? CFG.spLow : CFG.spHigh, tq = S.low ? CFG.tqLow : CFG.tqHigh;
      S.wj.forEach((j, i) => {
        const drv = i === 0 || S.awd; j.brake = 0;
        if (!play) { j.brake = S.state === 'win' ? 160000 : 0; j.maxT = 0; return; }
        if (g) { j.speed = sp; j.maxT = drv ? tq : 0; }
        else if (br) { if (fwd > 70) { j.brake = 230000; j.maxT = 0; } else { j.speed = -sp * 0.55; j.maxT = drv ? tq * 0.8 : 0; } }
        else { j.speed = 0; j.maxT = drv ? 7000 : 0; }
      });
      // топливо: полный привод, блокировка и пониженная жгут больше; буксуешь на месте — жжёшь впустую
      if (play) {
        S.fuel = Math.max(0, S.fuel - (0.1 + (inp.gas && S.fuel > 0 ? CFG.burn * (S.awd ? 1.35 : 1) * (S.lock ? 1.3 : 1) * (S.low ? 1.2 : 1) : 0)) * dt);
        for (const c of L.cans) if (!c.got && Math.abs(c.x - T.x) < 90 && Math.abs(c.y - T.y) < 160) { c.got = true; S.fuel = Math.min(CFG.tank, S.fuel + 30); S.events.push({ e: 'can' }); }
      }
      P.step(S.W, soft);
      after(inp);
      S.t += dt;
    };

    function after(inp) {
      const T = S.truck;
      S.grounded = S.inMud > 0; S.wallTouch = false;
      for (const k of S.W.touch) { if (k.A.kind === 'wheel') S.grounded = true; }
      if (S.state !== 'play') { if (S.state === 'win') S.wonT += P.DT; return; }
      S.flipT = Math.cos(T.a) < 0 ? S.flipT + P.DT : 0;
      // воздухозаборник под водой — мотор глохнет
      const [ix, iy] = P.wpt(T, 60, CFG.intake), wz = waterAt(ix);
      S.wetT = wz && iy > wz.y ? S.wetT + P.DT : 0;
      S.stuckT = inp.gas && S.fuel > 0 && Math.abs(T.vx) < 28 && S.grounded && !S.rope ? S.stuckT + P.DT : Math.max(0, S.stuckT - 3 * P.DT);
      if (S.flipT > 1.6) die('flip'); else if (S.wetT > 0.6) die('water'); else if (S.fuel <= 0 && Math.abs(T.vx) < 30) die('fuel');
      for (const c of L.cps) if (T.x > c.x && (!S.cp || S.cp.x < c.x) && S.grounded) { S.cp = { x: c.x, y: c.y, fuel: S.fuel }; S.events.push({ e: 'cp' }); }
      if (T.x > L.fin && S.grounded) { S.state = 'win'; S.wonT = 0; hookOff(); S.events.push({ e: 'win' }); }
    }
    function die(why) { S.state = 'dead'; S.deadT = 0; S.why = why; S.rescues++; hookOff(); S.events.push({ e: 'dead', why }); }

    S.spawn(poly[0][0] + 320, poly[0][1]);
    return S;
  }

  // виды грязи: мелкая — проедешь и так; средняя — нужен полный привод; вязкая — ещё и блокировка; болото — всё сразу (или лебёдка)
  const ZONES = { shallow: { d: 26, k: 700, res: 1000 }, medium: { d: 46, k: 480, res: 2200 }, sticky: { d: 56, k: 420, res: 3100 }, swamp: { d: 72, k: 380, res: 5000 } };

  // ---------- маршруты ----------
  // Рейс 1 «Первый рейс»: каждый участок учит одной кнопке. Мелкая грязь — проедешь и так; подъём — полный привод;
  // грязь поглубже — привод или блокировка; крутой подъём — пониженная; брод; глубокое болото — всё сразу или лебёдка.
  function route1() {
    const b = Route().start(-300, 600).mark(140, 'garage').flat(1300);
    b.mud(900, ZONES.shallow);                                   // мелкая грязь: едет и так, только медленнее
    b.flat(500).cp(-200).slope(1700, 520).flat(600);             // длинный подъём: полный привод
    b.mud(1500, ZONES.medium);                                   // средняя грязь: полный привод
    b.flat(500).cp(-200).mud(1500, ZONES.sticky).flat(400);      // вязкая: ещё и блокировка
    b.slope(1200, 620).flat(300).can(0).flat(300);               // крутой подъём: пониженная
    b.slope(700, -260).flat(150).ford(700, 62).flat(150).slope(500, 120); // спуск к броду
    b.flat(500).cp(-200).tree(600).tree(1200).tree(1800).tree(2400); // деревья для лебёдки — через каждые 600: трос достаёт до следующего
    b.mud(2200, ZONES.swamp);                                    // болото: всё сразу или лебёдка
    b.flat(500).mark(420, 'mill').flat(400).fin(0).end();
    return b.S;
  }

  root.MudSide = { create, Route, MAST, WR, WRANGE, ZONES, routes: [{ name: ['First Haul', 'Первый рейс'], build: route1 }] };
})(typeof window !== 'undefined' ? window : globalThis);
