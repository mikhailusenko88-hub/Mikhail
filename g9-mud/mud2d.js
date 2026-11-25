'use strict';
/* Грязь, вид сбоку — логика без рисования (её же гоняют проверки в Node). Версия 2: грузовик собирается из деталей.
   База, лифт, колёса, мосты, шины, мотор, шноркель, бак, лебёдка — у каждой детали плюс и минус, и это настоящая физика, а не цифры.
   Препятствия: грязь (колея остаётся), брод (с илом), подъём, гребень, канава, ухаб. Единицы: пиксели, Y вниз, 54 px ≈ 1 м. */
(function (root) {
  const P = root.TPhys, PX = 54;
  const MIN_ROPE = 150;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const sst = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

  // ---------- сборка грузовика → числа ----------
  // base 0|1 — короткая/длинная база; lift 0..2; wheel 0..2 — размер колёс; axles 2|3; tires 0..2 — дорожные/универсальные/грязевые;
  // eng 0..2; snorkel 0|1; tank 0|1; winch 0|1 — длинный трос; awd, lock, low — есть ли в машине полный привод, блокировка, пониженная
  const DEF = { base: 0, lift: 0, wheel: 0, axles: 2, tires: 1, eng: 0, snorkel: 0, tank: 0, winch: 0, awd: 1, lock: 1, low: 1 };
  function spec(bd) {
    const b = Object.assign({}, DEF, bd);
    const WR = [27, 32, 38][b.wheel], hb = [72, 100][b.base], ly = 18 + [0, 9, 18][b.lift], rest = 34, hW = ly + rest - 6, BELLY = 43;
    // три моста: сзади тележка из двух; центр тяжести ближе к ней, как у настоящего грузовика с грузом
    const d3 = b.axles === 3 ? hb / 3 : 0, ax = b.axles === 3 ? [-hb + d3 - WR - 4, -hb + d3 + WR + 4, hb + d3] : [-hb, hb];
    const xr = ax[0] - WR - 12, xf = ax[ax.length - 1] + 44, len = xf - xr;
    const tire = [{ mud: 0.78, sp: 1.04, burn: 0.95 }, { mud: 1, sp: 1, burn: 1 }, { mud: 1.3, sp: 0.88, burn: 1.14 }][b.tires];
    const m = 8 + (b.base ? 1 : 0) + (b.axles === 3 ? 1.3 : 0) + 0.35 * b.eng + (b.tank ? 0.5 : 0) + 0.25 * b.wheel, tq = 1 + 0.25 * b.eng, intake = b.snorkel ? -62 : 19;
    return {
      b, WR, hb, ly, rest, hW, belly: BELLY, ax, xr, xf, len, m, I: m * (0.3 * len) * (0.3 * len), wm: 1.2 * (WR / 27) * (WR / 27), wI: 440 * Math.pow(WR / 27, 4),
      clear: hW + WR - BELLY,                      // клиренс, px
      ford: hW + WR - intake,                      // до какой глубины не зальёт мотор, px
      spHigh: 26 * (27 / WR) * tire.sp, spLow: 11 * (27 / WR), tqHigh: 95000 * tq, tqLow: 264000 * tq, // большие колёса: та же скорость, но тяга на земле меньше
      grip: tire.mud, float: (WR / 27) * (b.tires === 2 ? 1.12 : 1), // как колесо гребёт в грязи и как грязь его держит
      burn: 0.8 * (1 + 0.13 * b.eng) * tire.burn * Math.sqrt(WR / 27) * (b.axles === 3 ? 1.15 : 1) * Math.sqrt(m / 8),
      tank: 60 + 35 * b.tank, intake, mast: [xf - 2, 6], wrange: b.winch ? 1150 : 800, reel: b.winch ? 210 : 150,
    };
  }

  // ---------- построитель маршрута ----------
  function Route() {
    const S = { polys: [], anchors: [], pits: [], ceils: [], boosts: [], springs: [], star: null, cps: [], fin: 0, minY: 1e9, maxY: -1e9, mud: [], water: [], trees: [], cans: [], marks: [], signs: [] };
    let x = 0, y = 600; const cur = [];
    const push = (px, py) => { cur.push([px, py]); S.minY = Math.min(S.minY, py); S.maxY = Math.max(S.maxY, py); };
    const B = {
      S,
      get x() { return x; }, get y() { return y; },
      start(x0, y0) { x = x0; y = y0; push(x, y); return B; },
      flat(len) { const n = Math.max(1, Math.round(len / 130)); for (let i = 1; i <= n; i++) push(x + (len * i) / n, y); x += len; return B; },
      slope(len, up, n = 14) { const x0 = x, y0 = y; for (let i = 1; i <= n; i++) { const t = i / n, s = t * t * (3 - 2 * t); push(x0 + len * t, y0 - up * s); } x = x0 + len; y = y0 - up; return B; },
      hill(len, h, n = 14) { const x0 = x; for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y - h * (0.5 - 0.5 * Math.cos(t * Math.PI * 2))); } x = x0 + len; return B; },
      // грязь: d — глубина до твёрдого дна, k — как держит (меньше — глубже тонешь), res — сопротивление на колесо, mu — как гребут колёса
      mud(len, o) { S.mud.push(Object.assign({ x0: x, x1: x + len, d: 40, k: 500, res: 1500, mu: 0.75, coh: 700 }, o)); return B.flat(len); },
      // брод: depth — глубина воды посередине (вода стоит чуть ниже берега); silt — ил на дне (как грязь)
      ford(len, depth, silt, n = 16) {
        const x0 = x, y0 = y; S.water.push({ x0, x1: x + len, y: y0 + 6, depth });
        if (silt) S.mud.push(Object.assign({ x0: x0 + len * 0.22, x1: x0 + len * 0.78, d: 40, k: 500, res: 1500, mu: 0.75, coh: 700, wet: true }, silt));
        for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y0 + (depth + 6) * sst(0, 0.3, t) * sst(0, 0.3, 1 - t)); } x = x0 + len; y = y0; return B;
      },
      // гребень: короткий острый бугор — длинная база садится на него брюхом
      crest(len, h) { const x0 = x, y0 = y; for (const [t, k] of [[0.42, 0.9], [0.5, 1], [0.58, 0.9], [1, 0]]) push(x0 + len * t, y0 - h * k); x = x0 + len; return B; },
      // канава с отвесными стенками: маленькое колесо проваливается целиком
      ditch(w, d) { push(x + 5, y + d); push(x + w - 5, y + d); push(x + w, y); x += w; return B; },
      // уступ: отвесная ступенька вверх — маленькое колесо упирается
      step(h) { push(x + 5, y - h); x += 5; y -= h; return B; },
      // ухаб (бревно поперёк дороги)
      bump(len, h) { push(x + len * 0.3, y - h); push(x + len * 0.7, y - h); push(x + len, y); x += len; return B; },
      tree(dx = 0, h = 78) { S.trees.push({ x: x + dx, gy: y, y: y - h }); return B; },    // дерево для лебёдки
      can(dx = 0) { S.cans.push({ x: x + dx, y: y - 44, got: false }); return B; },        // канистра
      mark(dx, kind) { S.marks.push({ x: x + dx, y, kind }); return B; },                  // постройка у дороги: 'garage' | 'mill'
      sign(dx, kind, val) { S.signs.push({ x: x + dx, y, kind, val }); return B; },        // указатель перед препятствием: что впереди и сколько
      cp(dx = 0) { S.cps.push({ x: x + dx, y }); return B; },
      fin(dx = 150) { S.fin = x + dx; return B; },
      end(len = 1500) { B.flat(len); S.polys.push(cur); return B; },
    };
    return B;
  }
  const zoneAt = (L, x) => { for (const z of L.mud) if (x > z.x0 && x < z.x1) return z; return null; };
  const edge = (z, x) => sst(0, 170, x - z.x0) * sst(0, 170, z.x1 - x); // края грязи пологие: въезжаешь постепенно

  function create(routeFn, o) {
    const C = spec(o && o.build), b = C.b, WR = C.WR, NW = C.ax.length, manual = !!(o && o.manual); // manual — после аварии игра сама не возвращает: решает игрок
    const S = {
      L: null, W: null, truck: null, wheels: [], wj: [], rope: null, ropeA: null, target: null, cfg: C, WR,
      state: 'play', t: 0, deadT: 0, why: '', grounded: false, wallTouch: false, flipT: 0, wonT: 0, pullOn: false,
      cp: null, attempts: 1, rescues: 0, events: [], awd: false, lock: false, low: false, fuel: C.tank, range: 0,
      slip: new Array(NW).fill(0), sunk: new Array(NW).fill(0), depth: 0, inMud: 0, belly: false, hung: false, stuckT: 0, wetT: 0, wade: 0, dirt: 0, rutV: 0,
    };
    S.L = (typeof routeFn === 'number' ? root.MudSide.routes[routeFn].build : routeFn)();
    const L = S.L, poly = L.polys[0];
    L.mudAt = (x) => { const z = zoneAt(L, x); return z && !z.wet ? edge(z, x) * clamp(z.d / 60, 0.4, 1) : 0; };
    L.mud.forEach((z) => { const n = Math.ceil((z.x1 - z.x0) / 30) + 2; z.rut = new Float32Array(n); z.pack = new Float32Array(n); });

    S.groundAt = (x) => { // поверхность: то, что видно (в грязи — верх грязи)
      if (x <= poly[0][0]) return poly[0][1];
      for (let i = 1; i < poly.length; i++) { const a = poly[i - 1], q = poly[i]; if (x <= q[0]) return a[1] + ((q[1] - a[1]) * (x - a[0])) / (q[0] - a[0] || 1); }
      return poly[poly.length - 1][1];
    };
    const bedAt = (x) => { const z = zoneAt(L, x); return S.groundAt(x) + (z ? z.d * edge(z, x) : 0); }; // твёрдое дно
    S.bedAt = bedAt;
    const at = (A, z, x) => { const f = clamp((x - z.x0) / 30, 0, A.length - 1.001), i = Math.floor(f); return A[i] + (A[i + 1] - A[i]) * (f - i); };
    const rutMax = (z) => Math.max(0, z.d - 34), packMax = (z) => 0.32 * z.d;
    // буксуешь — колесо копает яму (rut): в ней глубже и тяжелее
    const dig = (z, x, v) => { const i = clamp(Math.round((x - z.x0) / 30), 0, z.rut.length - 1), m = rutMax(z); for (const [k, q] of [[i - 1, 0.5], [i, 1], [i + 1, 0.5]]) if (k >= 0 && k < z.rut.length) z.rut[k] = Math.min(m, z.rut[k] + v * q); S.rutV++; };
    // просто проехал — остался накатанный след (pack): следующему колесу по нему легче
    const press = (z, x, d) => { const i = clamp(Math.round((x - z.x0) / 30), 0, z.pack.length - 1), v = Math.min(packMax(z), d); if (z.pack[i] < v - 0.3) { z.pack[i] += (v - z.pack[i]) * 0.25; S.rutV++; } };
    S.rutAt = (x) => { const z = zoneAt(L, x); return z ? (at(z.rut, z, x) + at(z.pack, z, x)) * edge(z, x) : 0; }; // насколько продавлена поверхность (для картинки)
    const waterAt = (x) => L.water.find((w) => x > w.x0 && x < w.x1) || null;
    S.waterAt = waterAt;

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
      const W = S.W, y = gy - C.hW - WR - 2, circles = [];
      for (let cx = C.xr + 22; cx <= C.xf - 30; cx += 34) circles.push({ x: cx, y: C.belly - 12, r: 12, belly: true });           // низ рамы
      circles.push({ x: C.xf - 8, y: 12, r: 13 }, { x: C.xr + 8, y: 8, r: 13 });                                                    // бамперы
      const cabX = C.ax[NW - 1] - 22;
      circles.push({ x: cabX + 26, y: -64, r: 13, roof: true }, { x: cabX - 14, y: -68, r: 13, roof: true }, { x: C.xr + 16, y: -40, r: 11 }); // крыша кабины, задний борт
      S.truck = P.addBody(W, P.body({ x, y, m: C.m, I: C.I, group: 'truck', kind: 'truck', rad: C.len, mu: 0.6, lin: 0.9997, ang: 0.997, circles }));
      S.wheels = []; S.wj = [];
      const ks = (C.m / 8) * (2 / NW);
      for (const lx of C.ax) { // последнее — переднее
        const w = P.addBody(W, P.body({ x: x + lx, y: y + C.hW + 2, m: C.wm, I: C.wI, group: 'truck', kind: 'wheel', mu: 1.0, circles: [{ x: 0, y: 0, r: WR }], ang: 0.999 }));
        S.wheels.push(w); S.wj.push(P.wheelJoint(W, S.truck, w, { lx, ly: C.ly, rest: C.rest, k: 1150 * ks, c: 70 * ks, lo: 10, hi: 44 }));
      }
      S.rope = null; S.ropeA = null; S.state = 'play'; S.deadT = 0; S.flipT = 0; S.wonT = 0; S.grounded = false; S.stuckT = 0; S.wetT = 0;
    };
    const startX = poly[0][0] + 320;
    S.respawn = () => {
      const p = S.cp || { x: startX, fuel: C.tank };
      S.spawn(p.x, S.groundAt(p.x)); S.fuel = Math.max(p.fuel, 0.5 * C.tank); // после возврата в баке не меньше половины: застрять в круге «кончилось топливо» нельзя
      S.attempts++; S.events.push({ e: 'respawn' });
    };
    S.reset = () => { S.cp = null; S.attempts = 1; S.rescues = 0; S.t = 0; S.fuel = C.tank; S.dirt = 0; S.events.length = 0; for (const c of L.cans) c.got = false; for (const z of L.mud) { z.rut.fill(0); z.pack.fill(0); } S.rutV++; S.spawn(startX, poly[0][1]); };
    S.rescue = () => { if (S.state === 'play') { S.rescues++; S.respawn(); } }; // вернуться на последнюю отметку
    S.mast = () => P.wpt(S.truck, C.mast[0], C.mast[1]);

    // дерево, за которое зацепится лебёдка: ближайшее впереди в пределах троса
    S.findTree = () => {
      const [mx] = S.mast(); let best = null;
      for (const a of L.trees) { const dx = a.x - mx; if (dx > MIN_ROPE + 40 && dx < C.wrange && (!best || a.x < best.x)) best = a; }
      return best;
    };
    function hookOn(a) { const [mx, my] = S.mast(); S.rope = P.ropeJoint(S.W, S.truck, C.mast[0], C.mast[1], a.x, a.y, Math.max(MIN_ROPE, Math.hypot(a.x - mx, a.y - my))); S.ropeA = a; S.events.push({ e: 'hook' }); }
    function hookOff() { if (!S.rope) return; S.W.joints = S.W.joints.filter((j) => j !== S.rope); S.rope = null; S.ropeA = null; S.events.push({ e: 'unhook' }); }

    // силы грязи и воды — после тяжести, до решения контактов
    function soft(dt) {
      const T = S.truck, Mall = T.m + S.wheels.reduce((a, w) => a + w.m, 0); let R = 0; S.inMud = 0; S.belly = false; S.wade = 0;
      S.wheels.forEach((w, i) => {
        S.sunk[i] = 0; S.slip[i] = 0;
        const z = zoneAt(L, w.x); if (!z) return;
        const e = edge(z, w.x), rut = at(z.rut, z, w.x) * e, pk = at(z.pack, z, w.x) * e, sub = clamp(w.y + WR - (S.groundAt(w.x) + rut + pk), 0, 2 * WR);
        if (sub <= 0 || e < 0.02) return;
        S.inMud++; S.sunk[i] = sub + rut + pk;
        const Fs = z.k * C.float * e * sub;                          // грязь держит колесо: чем глубже, тем сильнее; большое колесо держит лучше
        w.vy -= (Fs / w.m) * dt; w.vy *= 1 - Math.min(0.9, 5 * dt * (sub / WR));
        // сколько тяги даёт грязь: трение под весом плюс «липкость» (её даёт каждое колесо — потому три моста гребут лучше двух); без блокировки одно колесо моста буксует впустую
        const cap = (z.mu * C.grip * Fs + z.coh * C.grip * C.float * e * Math.min(1, sub / 8)) * (S.lock ? 1 : 0.4);
        const sv = w.w * WR - w.vx, th = clamp(sv * 40, -cap, cap);  // колесо гребёт, пока не сорвётся
        w.vx += (th / w.m) * dt; w.w -= ((th * WR) / w.I) * dt;
        S.slip[i] = Math.abs(sv);
        if (S.state === 'play') { if (Math.abs(sv) > 150) dig(z, w.x, Math.min(0.012 * Math.abs(sv), 6) * dt); press(z, w.x, 0.4 * sub); } // буксуешь — закапываешься; просто проехал — остался след
        const q = clamp(sub / (0.5 * WR), 0, 1.6); R += z.res * e * q * q * (1 + rut / 70) * (1 - 0.5 * Math.min(1, pk / (0.35 * sub + 1))); // чем глубже сидит колесо, тем тяжелее (вдвое глубже — вчетверо); по следу переднего колеса заднему вдвое легче
      });
      // брюхо легло на грязь: кузов держит, колёса разгружены, тянет назад
      for (const c of T.circles) {
        if (!c.belly) continue;
        const [cx, cy] = P.wpt(T, c.x, c.y), z = zoneAt(L, cx); if (!z) continue;
        const e = edge(z, cx), sub = cy + c.r - S.groundAt(cx); if (sub <= 0 || e < 0.02) continue;
        const F = 420 * sub * e; T.vy -= (F / T.m) * dt; T.w += ((cx - T.x) * -F) / T.I * dt; T.vy *= 1 - Math.min(0.3, 1.2 * dt);
        R += 1200 * e * Math.min(1, sub / 12); S.belly = true;
      }
      if (R > 0) { // сопротивление грязи: как трение — может остановить совсем; на скорости грязь тормозит сильнее (с разгона далеко не уедешь)
        R *= 1 + Math.abs(T.vx) / 400;
        const dv = (R / Mall) * dt, k = Math.abs(T.vx) <= dv ? -T.vx : -Math.sign(T.vx) * dv;
        for (const q of [T, ...S.wheels]) q.vx += k;
        T.w -= (C.hW * T.m * k) / T.I; // грязь держит за колёса, а не за кузов: тормозит на уровне мостов, поэтому машину не задирает носом вверх
        S.dirt = Math.min(1, S.dirt + 0.05 * dt * (1 + S.inMud));
      }
      // вода: тормозит, чуть держит на плаву и отмывает
      for (const q of [T, ...S.wheels]) { const wz = waterAt(q.x); if (!wz) continue; const r = q === T ? 34 : WR, s = clamp((q.y + r - wz.y) / (2 * r), 0, 1); if (s > 0) { q.vx *= 1 - (q === T ? 4 : 2.2) * s * dt; q.vy *= 1 - 1.2 * s * dt; q.vy -= P.G * 0.22 * s * dt; if (q !== T) { S.wade = Math.max(S.wade, s); S.dirt = Math.max(0, S.dirt - 0.12 * s * dt); } } }
    }

    // один шаг 1/120 с; inp = { gas, brake, winch (держать), awd, lock, low (включено/выключено) }
    S.step = (inp) => {
      const dt = P.DT, T = S.truck;
      if (S.state === 'dead') { S.deadT += dt; if (!manual && S.deadT > 1.7) S.respawn(); }
      const play = S.state === 'play';
      S.awd = !!inp.awd && !!b.awd; S.lock = !!inp.lock && !!b.lock; S.low = !!inp.low && !!b.low;
      // лебёдка: держишь — трос цепляется за ближайшее дерево впереди и тянет; отпустил — отцепился
      S.target = play && !S.rope ? S.findTree() : null;
      if (play && inp.winch && !S.rope && S.target) hookOn(S.target);
      if (S.rope && (!inp.winch || !play)) hookOff();
      S.pullOn = false;
      if (S.rope) {
        const [mx, my] = S.mast(), d = Math.hypot(mx - S.rope.px, my - S.rope.py);
        if (d < S.rope.len) S.rope.len = Math.max(MIN_ROPE, d);
        if (S.rope.len > MIN_ROPE) { S.rope.len = Math.max(MIN_ROPE, S.rope.len - C.reel * dt); S.pullOn = true; }
        else hookOff(); // подтянулись к дереву — трос отцепляется сам; держишь кнопку дальше — цепляется за следующее
      }
      // мотор: задние мосты всегда, передний — с полным приводом; пониженная — больше тяги, меньше скорость
      const g = play && inp.gas && S.fuel > 0, br = play && !g && inp.brake;
      const [fx, fy] = P.wvec(T, 1, 0), fwd = T.vx * fx + T.vy * fy, sp = S.low ? C.spLow : C.spHigh, tq = S.low ? C.tqLow : C.tqHigh;
      S.wj.forEach((j, i) => {
        const drv = i < NW - 1 || S.awd; j.brake = 0;
        if (!play) { j.brake = S.state === 'win' ? 160000 : 0; j.maxT = 0; return; }
        if (g) { j.speed = sp; j.maxT = drv ? tq : 0; }
        else if (br) { if (fwd > 70) { j.brake = 230000; j.maxT = 0; } else { j.speed = -sp * 0.55; j.maxT = drv ? tq * 0.8 : 0; } }
        else { j.speed = 0; j.maxT = drv ? 7000 : 0; }
      });
      // топливо: полный привод, блокировка и пониженная жгут больше; буксуешь на месте — жжёшь впустую
      const rate = C.burn * (S.awd ? 1.35 : 1) * (S.lock ? 1.3 : 1) * (S.low ? 1.2 : 1);
      S.range = (S.fuel / (0.1 + rate)) * sp * WR * 0.8; // на сколько хватит в этом режиме, px
      if (play) {
        S.fuel = Math.max(0, S.fuel - (0.1 + (inp.gas && S.fuel > 0 ? rate : 0)) * dt);
        for (const c of L.cans) if (!c.got && Math.abs(c.x - T.x) < 90 && Math.abs(c.y - T.y) < 160) { c.got = true; S.fuel = Math.min(C.tank, S.fuel + 30); S.events.push({ e: 'can' }); }
      }
      P.step(S.W, soft);
      after(inp);
      S.t += dt;
    };

    function after(inp) {
      const T = S.truck;
      S.grounded = S.inMud > 0; S.wallTouch = false; let bel = false, wh = 0;
      for (const k of S.W.touch) { if (k.A.kind === 'wheel') { S.grounded = true; wh++; } else if (k.tagA && k.tagA.belly) bel = true; }
      S.hung = bel && !S.inMud; // сел брюхом на твёрдое (гребень, край канавы)
      if (S.state !== 'play') { if (S.state === 'win') S.wonT += P.DT; return; }
      S.flipT = Math.cos(T.a) < 0 ? S.flipT + P.DT : 0;
      // мотор заливает, когда передние колёса стоят в воде глубже, чем берёт грузовик («Брод до …» в гараже). Правило по глубине, а не по наклону:
      // указатель «брод 0,9 м» и число в гараже сравниваются напрямую, и клюнуть носом на въезде не страшно
      const fw = S.wheels[NW - 1], wz = waterAt(fw.x); S.depth = wz ? Math.max(0, fw.y + WR - wz.y) : 0;
      S.wetT = S.depth > C.ford ? S.wetT + P.DT : Math.max(0, S.wetT - 2 * P.DT);
      S.stuckT = inp.gas && S.fuel > 0 && Math.abs(T.vx) < 28 && (S.grounded || bel) && !S.rope ? S.stuckT + P.DT : Math.max(0, S.stuckT - 3 * P.DT);
      if (S.flipT > 1.6) die('flip'); else if (S.wetT > 0.4) die('water'); else if (S.fuel <= 0 && Math.abs(T.vx) < 30) die('fuel');
      for (const c of L.cps) if (T.x > c.x && (!S.cp || S.cp.x < c.x) && S.grounded) { S.cp = { x: c.x, y: c.y, fuel: S.fuel }; S.events.push({ e: 'cp' }); }
      if (T.x > L.fin && S.grounded) { S.state = 'win'; S.wonT = 0; hookOff(); S.events.push({ e: 'win' }); }
    }
    function die(why) { S.state = 'dead'; S.deadT = 0; S.why = why; S.rescues++; hookOff(); S.events.push({ e: 'dead', why }); }

    S.spawn(startX, poly[0][1]);
    return S;
  }

  // виды грязи
  const ZONES = { shallow: { d: 26, k: 700, res: 1000, coh: 400 }, soft: { d: 34, k: 600, res: 1750, coh: 500 }, medium: { d: 46, k: 480, res: 2550, coh: 900 }, sticky: { d: 56, k: 420, res: 3600, coh: 1400 }, swamp: { d: 72, k: 380, res: 5800, coh: 1800 }, silt: { d: 30, k: 560, res: 1500, coh: 500 } };

  // ---------- маршруты ----------
  // Полигон: по одному препятствию каждого вида, перед каждым — указатель и отметка. Одной сборкой всё не взять: что помогает в одном месте, мешает в другом, а топливо общее.
  function polygon() {
    const b = Route().start(-300, 600).mark(140, 'garage').flat(1000);
    b.sign(-190, 'mud', 1).mud(900, ZONES.soft).flat(500).cp(-400);                              // мягкая грязь: разминка
    b.sign(-170, 'crest', 0.55).crest(240, 55).flat(700).cp(-400);                               // гребень: длинная база садится брюхом
    b.sign(-170, 'ford', 0.9).ford(800, 49).flat(500).cp(-400);                                  // брод 0,9 м: проходят все
    b.sign(-190, 'mud', 2).mud(1300, ZONES.medium).flat(500).can(-120).cp(-420);                 // средняя грязь: привод и блокировка — или шины
    b.sign(-170, 'climb', 30).slope(1000, 560).flat(700).cp(-420);                               // крутой подъём: пониженная; большим колёсам не хватает тяги
    b.sign(-170, 'ford', 1.1).ford(800, 60).flat(500).cp(-400);                                  // брод 1,1 м: лифт, колёса или шноркель
    b.sign(-190, 'mud', 3).mud(1300, ZONES.sticky).flat(500).can(-120).cp(-420);                 // липкая грязь: всё включить
    b.sign(-170, 'crest', 0.8).crest(300, 80).flat(600).cp(-400);                                // высокий гребень
    b.slope(600, -200).flat(300).sign(-170, 'ford', 1.5).ford(900, 51, ZONES.silt).flat(300).slope(600, 200).flat(400).cp(-400); // брод с илом: воды метр и ила полметра — на указателе честные 1,5 м; шноркель или лифт +2 с большими колёсами
    b.sign(-190, 'mud', 4).tree(500).tree(1050).tree(1600).tree(2150).mud(1900, ZONES.swamp);    // болото: лебёдка или вездеход
    b.flat(500).mark(420, 'mill').flat(400).fin(0).end();
    return b.S;
  }

  root.MudSide = { create, spec, Route, DEF, PX, ZONES, routes: [{ name: ['Proving ground', 'Полигон'], build: polygon }] };
})(typeof window !== 'undefined' ? window : globalThis);
