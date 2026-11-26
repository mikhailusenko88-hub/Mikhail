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
  // press 0..2 — давление в шинах (низкое/среднее/высокое); susp 0..2 — подвеска (мягкая/средняя/жёсткая); gear 0..2 — главная пара (тяговая/средняя/скоростная);
  // skid — защита днища; ctis — подкачка шин на ходу; paint — краска
  const DEF = { base: 0, lift: 0, wheel: 0, axles: 2, tires: 1, eng: 0, snorkel: 0, tank: 0, winch: 0, awd: 1, lock: 1, low: 1, press: 1, susp: 1, gear: 1, skid: 0, ctis: 0, paint: 0, trailer: 0 };
  // груз: у каждого свой характер. Брёвна — обычные; бочки — тяжёлые (машина хуже тянет); арбузы — лёгкие и прыгают на ухабах
  const CARGO = { log: { r: 10, m: 0.3, I: 16, mu: 0.9, e: 0 }, barrel: { r: 13, m: 0.7, I: 60, mu: 0.6, e: 0 }, melon: { r: 9, m: 0.16, I: 6, mu: 0.5, e: 0.62, sd: 0 } };
  const CAPMAX = [9, 11, 13], rowsOf = (len, kind) => 2 * Math.floor((len - 4) / (2 * (CARGO[kind] || CARGO.log).r + 1)) - 1; // сколько штук входит в кузов такой длины: два ряда, верхний на один короче
  const spaceTruck = (C, kind) => Math.min(CAPMAX[C.b.base], rowsOf(C.bed[1] - C.bed[0], kind)), spaceOf = (C, kind) => spaceTruck(C, kind) + (C.tr ? rowsOf(C.tr.bed, kind) : 0); // место: кузов грузовика плюс прицеп
  // грузоподъёмность, т — сколько сборка довозит через самые тяжёлые заказы (карьер, размокшая глина, два брода). Подобрано прогоном 90 сборок:
  // рама +1,4 т за шаг; форсировка +1 т за ступень (с 6-й — по 0,6); третий мост +0,7 / +4,2 / +6,3 т (короткая / длинная / длинная+); короткая рама больше 7,7 т не тянет — задирает нос;
  // прицеп места добавляет, а сам отнимает: тележка 2,1 т, большой 3,5 т (его колёса не ведущие, в гору и в грязи он обуза)
  const ENG_T = (e) => Math.min(e, 4) + 1.4 * Math.max(0, e - 4), TR_T = [0, +(root.__TR1 || 3.5), +(root.__TR2 || 1.2)]; // ступени 6–8 дают по 1,4 т: под них и сделан большой прицеп с ведущими мостами (см. spec)
  const payT = (C) => { const b = C.b, p = 2.1 + 1.4 * b.base + ENG_T(b.eng) + (b.axles === 3 ? [0.7, 4.2, 6.3][b.base] : 0); return Math.max(0.7, Math.round(10 * ((b.base ? p : Math.min(p, 7.7)) - (C.tr ? TR_T[b.trailer] : 0))) / 10); };
  const capOf = (C, kind) => Math.max(1, Math.min(spaceOf(C, kind), Math.floor(payT(C) / (CARGO[kind] || CARGO.log).m + 1e-6))); // сколько штук можно взять: по месту и по весу
  // топливо — настоящее ограничение: аккуратный рейс доезжает с небольшим запасом, буксование, лебёдка и всё включённое «на всякий случай» — нет
  const FUEL_K = (root.__FK || 1.15), CAN = 20, WINCH_BURN = 0.8, F_AWD = 1.25, F_LOCK = 1.15, F_LOW = 1.15; // л/с на газу у заводского грузовика; канистра, л; лебёдка под нагрузкой, л/с
  function spec(bd) {
    const b = Object.assign({}, DEF, bd);
    const WR = [27, 32, 38][b.wheel], hb = [72, 100, 132][b.base], ly = 18 + [0, 9, 18][b.lift], rest = 34, hW = ly + rest - 6, BELLY = 43;
    // три моста: сзади тележка из двух; центр тяжести ближе к ней, как у настоящего грузовика с грузом
    const d3 = b.axles === 3 ? hb / 3 : 0, ax = b.axles === 3 ? [-hb + d3 - WR - 4, -hb + d3 + WR + 4, hb + d3] : [-hb, hb];
    const xr = ax[0] - WR - 12, xf = ax[ax.length - 1] + 44, len = xf - xr;
    const tire = [{ mud: 0.78, sp: 1.04, burn: 0.95 }, { mud: 1, sp: 1, burn: 1 }, { mud: 1.3, sp: 0.88, burn: 1.14 }][b.tires];
    const m = 8 + b.base + (b.axles === 3 ? 1.3 : 0) + 0.15 * b.eng + (b.tank ? 0.5 : 0) + 0.25 * b.wheel + (b.skid ? 0.4 : 0) + (b.ctis ? 0.15 : 0), tq = 1 + 0.12 * Math.min(b.eng, 5) + 0.07 * Math.max(0, b.eng - 5), intake = b.snorkel ? -62 : 19;
    const gr = [{ t: 1.25, s: 0.8 }, { t: 1, s: 1 }, { t: 0.82, s: 1.2 }][b.gear]; // главная пара: тяга в обмен на скорость
    return {
      b, WR, hb, ly, rest, hW, belly: BELLY, ax, xr, xf, len, m, I: m * (0.3 * len) * (0.3 * len), wm: 1.2 * (WR / 27) * (WR / 27), wI: 440 * Math.pow(WR / 27, 4),
      clear: hW + WR - BELLY,                      // клиренс, px
      ford: hW + WR - intake,                      // до какой глубины не зальёт мотор, px
      spHigh: 26 * (27 / WR) * tire.sp * gr.s, spLow: 11 * (27 / WR) * gr.s, tqHigh: 95000 * tq * gr.t, tqLow: 264000 * tq * gr.t, // большие колёса: та же скорость, но тяга на земле меньше
      // давление в шинах: на спущенных колесо шире — меньше тонет и лучше гребёт, зато на твёрдом медленнее и прожорливее
      PR: [{ fl: 1.38, gr: 1.15, sp: 0.82, bn: 1.15 }, { fl: 1, gr: 1, sp: 1, bn: 1 }, { fl: 0.86, gr: 0.92, sp: 1.05, bn: 0.95 }],
      suspK: [0.68, 1, 1.5][b.susp], bellyMu: b.skid ? 0.12 : 0.6, bellyDrag: b.skid ? 0.45 : 1, clogK: [1.35, 1, 0.45][b.tires], // подвеска; защита днища скользит; как быстро забивается протектор
      bed: [xr + 6, xf - 132, BELLY - 16], cap: Math.min([9, 11, 13][b.base], 2 * Math.floor((xf - 132 - xr - 6 - 4) / 21) - 1), // кузов: задний край, передний край, пол; сколько брёвен входит (длинная база везёт больше)
      grip: tire.mud, float: (WR / 27) * (b.tires === 2 ? 1.12 : 1), // как колесо гребёт в грязи и как грязь его держит
      burn: FUEL_K * (1 + 0.06 * b.eng) * tire.burn * Math.sqrt(WR / 27) * (b.axles === 3 ? 1.15 : 1) * Math.sqrt(m / 8) * (1 + [0, 0.05, 0.15][b.trailer]),
      tank: 60 + 35 * b.tank + (b.base && b.axles === 3 ? [0, 30, 50][b.trailer] : 0), intake, /* на прицепе — запасной бак: автопоезд ест больше */ mast: [xf - 2, 6], wrange: b.winch ? 1150 : 800, reel: b.winch ? 210 : 150,
      // прицеп: своя рама на сцепке, свой кузов и свои колёса (не ведущие). Даёт место под груз, а тянуть его — мотору
      tr: b.trailer && b.base && b.axles === 3 ? Object.assign({ hx: xr - 2, hy: 34, ty: 34 }, [null, { bed: 117, m: 0.7, ax: [-10], tx: 104.5, len: 173, load: 3 }, { bed: 231, m: 1.3, ax: [-60, 60], tx: 161.5, len: 287, rod: 40, drive: 0.25, load: 8 }][b.trailer]) : null, // прицеп — только на длинную раму с тремя мостами: короткую он задирает на месте, а 4×4 с тележкой встаёт в липкой грязи с третью груза
    };
  }

  // ---------- построитель маршрута ----------
  function Route() {
    const S = { polys: [], anchors: [], pits: [], ceils: [], boosts: [], springs: [], star: null, cps: [], fin: 0, minY: 1e9, maxY: -1e9, mud: [], water: [], trees: [], cans: [], marks: [], signs: [], rough: [], rocks: [] };
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
      mud(len, o) { S.mud.push(Object.assign({ x0: x, x1: x + len, t: 'mud', d: 40, k: 500, res: 1500, mu: 0.75, coh: 700, stick: 0.6, heal: 0, digK: 1, spd: 1, lockK: 0.4 }, o)); return B.flat(len); },
      // грязь, глина или осыпь на уклоне: up > 0 — подъём, up < 0 — спуск. На уклоне грунт не только держит, но и тянет вниз по склону (inc)
      mudOn(len, up, o) { S.mud.push(Object.assign({ x0: x, x1: x + len, t: 'mud', d: 40, k: 500, res: 1500, mu: 0.75, coh: 700, stick: 0.6, heal: 0, digK: 1, spd: 1, lockK: 0.4, inc: true }, o)); return B.slope(len, up); },
      // каменная россыпь: камни разной высоты через неравные промежутки. Ряд задаётся числом seed — на каждом заезде он один и тот же
      rocks(len, hMax, seed = 1) { let r = (seed * 7919 + 104729) % 233280, left = len; const rnd = () => (r = (r * 9301 + 49297) % 233280) / 233280; S.rough.push({ x0: x, x1: x + len, h: hMax, t: 'rocks' });
        while (left > 170) { const gap = 60 + rnd() * 90, w = 50 + rnd() * 44, h = hMax * (0.5 + 0.5 * rnd()); B.flat(gap); S.rocks.push({ x: x + w / 2, y, w, h }); B.bump(w, h); left -= gap + w; } return B.flat(Math.max(40, left)); },
      // брод: depth — глубина воды посередине (вода стоит чуть ниже берега); silt — ил на дне (как грязь)
      ford(len, depth, silt, n = 16) {
        const x0 = x, y0 = y; S.water.push({ x0, x1: x + len, y: y0 + 6, depth });
        if (silt) S.mud.push(Object.assign({ x0: x0 + len * 0.22, x1: x0 + len * 0.78, t: 'mud', d: 40, k: 500, res: 1500, mu: 0.75, coh: 700, stick: 0, heal: 0, digK: 1, spd: 1, lockK: 0.4, wet: true }, silt));
        for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y0 + (depth + 6) * sst(0, 0.3, t) * sst(0, 0.3, 1 - t)); } x = x0 + len; y = y0; return B;
      },
      // гребень: короткий острый бугор — длинная база садится на него брюхом
      crest(len, h) { const x0 = x, y0 = y; for (const [t, k] of [[0.42, 0.9], [0.5, 1], [0.58, 0.9], [1, 0]]) push(x0 + len * t, y0 - h * k); x = x0 + len; return B; },
      // канава с отвесными стенками: маленькое колесо проваливается целиком
      ditch(w, d) { push(x + 5, y + d); push(x + w - 5, y + d); push(x + w, y); x += w; return B; },
      // уступ: отвесная ступенька вверх — маленькое колесо упирается
      step(h) { S.rough.push({ x0: x - 40, x1: x + 60, h, t: 'step' }); push(x + 5, y - h); x += 5; y -= h; return B; },
      // ухаб (бревно поперёк дороги)
      bump(len, h) { push(x + len * 0.3, y - h); push(x + len * 0.7, y - h); push(x + len, y); x += len; return B; },
      tree(dx = 0, h = 78) { S.trees.push({ x: x + dx, gy: y, y: y - h }); return B; },    // дерево для лебёдки
      can(dx = 0, k = 1) { S.cans.push({ x: x + dx, y: y - 44, got: false, l: CAN * k, k }); return B; }, // канистра 20 л (k — сколько их разом: на длинных горных трассах по две-три)
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
    const C = spec(o && o.build), b = C.b, WR = C.WR, NW = C.ax.length, TR = C.tr, NT = TR ? TR.ax.length : 0, manual = !!(o && o.manual), kind = (o && CARGO[o.kind] && o.kind) || 'log', CG = CARGO[kind], nLogs = Math.min(o && o.over ? spaceOf(C, kind) : capOf(C, kind), (o && o.cargo) | 0); // manual — после аварии игра сама не возвращает: решает игрок
    const S = {
      L: null, W: null, truck: null, wheels: [], wj: [], trailer: null, twheels: [], twj: [], allw: [], rope: null, ropeA: null, target: null, cfg: C, WR,
      state: 'play', t: 0, deadT: 0, why: '', grounded: false, wallTouch: false, flipT: 0, wonT: 0, pullOn: false,
      cp: null, attempts: 1, rescues: 0, events: [], awd: false, lock: false, low: false, fuel: C.tank, range: 0,
      logs: [], kind, stakeH: nLogs ? CG.r * 2.82 + (CG.sd === undefined ? 3 : CG.sd) : 30, cargo: nLogs, cargo0: nLogs, tows: 0, used: 0, slip: new Array(NW + NT).fill(0), sunk: new Array(NW + NT).fill(0), clog: new Array(NW + NT).fill(0), press: b.press, soil: '', depth: 0, inMud: 0, belly: false, hung: false, stuckT: 0, wetT: 0, wade: 0, dirt: 0, rutV: 0,
    };
    S.L = (typeof routeFn === 'number' ? root.MudSide.routes[routeFn].build : routeFn)();
    const L = S.L, poly = L.polys[0];
    L.mudAt = (x) => { const z = zoneAt(L, x); return z && !z.wet ? edge(z, x) * clamp(z.d / 60, 0.4, 1) : 0; };
    L.mud.forEach((z) => { const n = Math.ceil((z.x1 - z.x0) / 30) + 2; z.rut = new Float32Array(n); z.pack = new Float32Array(n); z.pile = new Float32Array(n); });

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
    // выкопанное колесо выбрасывает назад — там растёт вал (pile)
    const dig = (z, x, v, dir) => { const n = z.rut.length, i = clamp(Math.round((x - z.x0) / 30), 0, n - 1), m = rutMax(z); for (const [k, q] of [[i - 1, 0.5], [i, 1], [i + 1, 0.5]]) if (k >= 0 && k < n) z.rut[k] = Math.min(m, z.rut[k] + v * q); for (const [k, q] of [[i - 2 * dir, 0.5], [i - 3 * dir, 0.3]]) if (k >= 0 && k < n) z.pile[k] = Math.min(13, z.pile[k] + v * q); S.rutV++; };
    // просто проехал — остался накатанный след (pack): следующему колесу по нему легче
    const press = (z, x, d) => { const i = clamp(Math.round((x - z.x0) / 30), 0, z.pack.length - 1), v = Math.min(packMax(z), d); if (z.pack[i] < v - 0.3) { z.pack[i] += (v - z.pack[i]) * 0.25; S.rutV++; } };
    S.rutAt = (x) => { const z = zoneAt(L, x); return z ? (at(z.rut, z, x) + at(z.pack, z, x) - at(z.pile, z, x)) * edge(z, x) : 0; }; // насколько продавлена (или, с минусом, навалена) поверхность — для картинки
    S.dugAt = (x) => { const z = zoneAt(L, x); return z ? at(z.rut, z, x) * edge(z, x) : 0; };
    S.zoneAt = (x) => zoneAt(L, x);
    // песок осыпается, вал оплывает — раз в десятую секунды
    function slump() { for (const z of L.mud) { const h = z.heal * 0.1; let ch = false; for (let i = 0; i < z.rut.length; i++) { if (z.pile[i] > 0) { z.pile[i] = Math.max(0, z.pile[i] - 0.12 - h); ch = true; } if (h > 0) { if (z.rut[i] > 0) { z.rut[i] = Math.max(0, z.rut[i] - h); ch = true; } if (z.pack[i] > 0) { z.pack[i] = Math.max(0, z.pack[i] - h * 0.5); ch = true; } } } if (ch) S.rutV++; } }
    const waterAt = (x) => L.water.find((w) => x > w.x0 && x < w.x1) || null;
    S.waterAt = waterAt;

    let slumpN = 0;
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
      for (let cx = C.xr + 22; cx <= C.xf - 30; cx += 34) circles.push({ x: cx, y: C.belly - 12, r: 12, belly: true, mu: C.bellyMu });           // низ рамы
      circles.push({ x: C.xf - 8, y: 12, r: 13 }, { x: C.xr + 8, y: 8, r: 13 });                                                    // бамперы
      const cabX = C.ax[NW - 1] - 22;
      circles.push({ x: cabX + 26, y: -64, r: 13, roof: true }, { x: cabX - 14, y: -68, r: 13, roof: true }, { x: C.xr + 16, y: -40, r: 11 }); // крыша кабины, задний борт
      const [bx0, bx1, fy] = C.bed; // у кузова пол, передняя стенка и задние стойки — брёвна лежат в нём настоящими телами
      S.truck = P.addBody(W, P.body({ x, y, m: C.m, I: C.I, group: 'truck', kind: 'truck', rad: C.len, mu: 0.6, lin: 0.9997, ang: 0.997, circles, segs: nLogs ? [[bx0, fy, bx1, fy], [bx1, fy, bx1, fy - S.stakeH - 14], [bx0, fy, bx0, fy - S.stakeH]] : [] }));
      S.wheels = []; S.wj = [];
      const ks = (C.m / 8) * (2 / NW) * C.suspK;
      for (const lx of C.ax) { // последнее — переднее
        const w = P.addBody(W, P.body({ x: x + lx, y: y + C.hW + 2, m: C.wm, I: C.wI, group: 'truck', kind: 'wheel', mu: 1.0, circles: [{ x: 0, y: 0, r: WR }], ang: 0.999 }));
        S.wheels.push(w); S.wj.push(P.wheelJoint(W, S.truck, w, { lx, ly: C.ly, rest: C.rest, k: 1150 * ks, c: 70 * ks / Math.sqrt(C.suspK), lo: 10, hi: 44 }));
      }
      // прицеп: рама с кузовом на сцепке за грузовиком, колёса катятся свободно
      S.trailer = null; S.twheels = []; S.twj = [];
      if (TR) {
        const hb2 = TR.bed / 2, Hx = x + TR.hx, Hy = y + TR.hy, tc = [{ x: -hb2 - 2, y: 12, r: 11, mu: 0.05 }]; let ta = 0;
        for (let it = 0; it < 5; it++) { const cx = Hx - TR.tx * Math.cos(ta) + TR.ty * Math.sin(ta); ta = Math.asin(clamp((Hy - TR.ty * Math.cos(ta) - (S.groundAt(cx) - C.hW - WR - 2)) / TR.tx, -0.5, 0.5)); } // прицеп ставим по земле под ним: за отметкой может быть спуск, подъём или брод
        const tcs = Math.cos(ta), tsn = Math.sin(ta), tx0 = Hx - TR.tx * tcs + TR.ty * tsn, ty0 = Hy - TR.tx * tsn - TR.ty * tcs, tw = (lx, ly) => [tx0 + lx * tcs - ly * tsn, ty0 + lx * tsn + ly * tcs];
        for (let cx = -hb2 + 14; cx <= hb2 + 34; cx += 30) tc.push({ x: cx, y: C.belly - 12, r: 12, mu: 0.05 }); // низ рамы и дышло — скользкие: прицеп на гребне не держит
        S.trailer = P.addBody(W, P.body({ x: tx0, y: ty0, a: ta, m: TR.m, I: TR.m * (0.3 * TR.len) * (0.3 * TR.len), group: 'truck', kind: 'trailer', rad: TR.len, mu: 0.3, lin: 0.9997, ang: 0.997, circles: tc, segs: nLogs ? [[-hb2, fy, hb2, fy], [hb2, fy, hb2, fy - S.stakeH - 14], [-hb2, fy, -hb2, fy - S.stakeH]] : [] }));
        const tCargo = Math.max(0, (S.logs.length ? S.logs.filter((q) => !q.lost).length : S.cargo) - spaceTruck(C, kind)) * CG.m; // сколько тонн ляжет в прицеп
        const kt = ((TR.m + clamp(tCargo, 0.25 * TR.load, TR.load)) / 8) * (2 / NT) * C.suspK; // рессоры прицепа — под тот груз, что в нём: лёгкие арбузы не скачут на рессорах под бочки. Жёстче расчётных нельзя: лёгкое колесо на слишком жёсткой рессоре выбрасывает груз
        for (const lx of TR.ax) { const [wx, wy] = tw(lx, C.hW + 2), w = P.addBody(W, P.body({ x: wx, y: wy, m: 0.5 * C.wm, I: 0.5 * C.wI, group: 'truck', kind: 'twheel', mu: 1.0, circles: [{ x: 0, y: 0, r: WR }], ang: 0.999 }));
          S.twheels.push(w); S.twj.push(P.wheelJoint(W, S.trailer, w, { lx, ly: C.ly, rest: C.rest, k: 1150 * kt, c: 70 * kt / Math.sqrt(C.suspK), lo: 10, hi: 44 })); }
        if (TR.rod) P.rodJoint(W, S.truck, TR.hx, TR.hy, S.trailer, TR.tx - TR.rod, TR.ty, TR.rod); else P.hitchJoint(W, S.truck, TR.hx, TR.hy, S.trailer, TR.tx, TR.ty); // двухосный стоит на своих колёсах: дышло только тянет, на грузовик не давит
      }
      S.allw = S.wheels.concat(S.twheels);
      // груз: нижний ряд и верхний; сначала заполняется кузов грузовика, остальное — в прицеп. Потерянное не возвращается
      const cr = CG.r, st = 2 * cr + 1, nb = Math.floor((bx1 - bx0 - 4) / st), spT = spaceTruck(C, kind), nbt = TR ? Math.floor((TR.bed - 4) / st) : 0, keep = S.logs.length ? S.logs.filter((q) => !q.lost).length : S.cargo; S.logs = [];
      for (let i = 0; i < keep; i++) { const onT = i >= spT && !!TR, j = onT ? i - spT : i, n0 = onT ? nbt : nb, top = j >= n0, k = top ? j - n0 : j, lx = onT ? TR.bed / 2 - cr - 2.5 - k * st - (top ? st / 2 : 0) : bx0 + cr + 2.5 + k * st + (top ? st / 2 : 0), // прицеп грузим от дышла: неполный груз давит на сцепку, а не задирает грузовик
        ly = fy - cr - 0.2 - (top ? cr * 1.82 : 0);
        const [gx, gy2] = onT ? P.wpt(S.trailer, lx, ly) : [x + lx, y + ly];
        S.logs.push({ b: P.addBody(W, P.body({ x: gx, y: gy2, m: CG.m, I: CG.I, e: CG.e, group: 'log', kind: 'log', cc: true, mu: CG.mu, lin: 0.9995, ang: 0.98, circles: [{ x: 0, y: 0, r: cr }] })), lost: false, out: 0 }); }
      S.rope = null; S.ropeA = null; S.state = 'play'; S.deadT = 0; S.flipT = 0; S.wonT = 0; S.grounded = false; S.stuckT = 0; S.wetT = 0; S.clog.fill(0); S.park = true; // ручник: после старта и возврата стоим, пока игрок не тронул управление — гружёный автопоезд не скатывается назад в грязь
    };
    const startX = Math.max(poly[0][0] + 320 + (TR ? TR.len : 0), Math.min(20, L.mud.length ? L.mud[0].x0 - 560 : 20)); // грузовик стартует на одном и том же месте с прицепом и без: прицеп встаёт позади, разгон до первой грязи не съедается
    S.respawn = () => {
      const p = S.cp || { x: startX, fuel: C.tank };
      S.spawn(p.x, S.groundAt(p.x)); S.fuel = Math.max(p.fuel, 0.5 * C.tank); // после возврата в баке не меньше половины: застрять в круге «кончилось топливо» нельзя
      S.attempts++; S.events.push({ e: 'respawn' });
    };
    S.reset = () => { S.cp = null; S.attempts = 1; S.rescues = 0; S.tows = 0; S.used = 0; S.logs = []; S.cargo = nLogs; S.t = 0; S.fuel = C.tank; S.dirt = 0; S.events.length = 0; for (const c of L.cans) c.got = false; for (const z of L.mud) { z.rut.fill(0); z.pack.fill(0); z.pile.fill(0); } S.rutV++; S.spawn(startX, poly[0][1]); };
    S.rescue = () => { if (S.state === 'play') { S.rescues++; S.tows++; S.respawn(); } }; // тягач: вернуться на последнюю отметку (в заказах — за деньги)
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
      const T = S.truck, Mall = T.m + S.wheels.reduce((a, w) => a + w.m, 0), pr = C.PR[S.press]; let R = 0, Rt = 0; S.inMud = 0; S.belly = false; S.wade = 0; S.soil = '';
      if (++slumpN >= 12) { slumpN = 0; slump(); }
      S.allw.forEach((w, i) => {
        S.sunk[i] = 0; S.slip[i] = 0; w.mu = 1 - 0.8 * S.clog[i]; // забитые шины скользят и на твёрдом
        const z = zoneAt(L, w.x);
        if (!z) { const sp = Math.max(0, (Math.abs(w.w) * WR) / 650 - 0.55); S.clog[i] = Math.max(0, S.clog[i] - sp * sp * 2.4 * dt); return; } // на твёрдом грязь слетает с колёс, только если их раскрутить: на пониженной не слетит
        const e = edge(z, w.x), rut = at(z.rut, z, w.x) * e, pk = at(z.pack, z, w.x) * e, pl = at(z.pile, z, w.x) * e, sub = clamp(w.y + WR - (S.groundAt(w.x) + rut + pk - pl), 0, 2 * WR);
        if (sub <= 0 || e < 0.02) return;
        S.inMud++; S.sunk[i] = sub + rut + pk; S.soil = z.t;
        const Fs = z.k * C.float * pr.fl * e * sub;                  // грунт держит колесо: чем глубже, тем сильнее; большое и спущенное колесо держит лучше
        w.vy -= (Fs / w.m) * dt; w.vy *= 1 - Math.min(0.9, 5 * dt * (sub / WR));
        if (z.inc) w.vx += (Fs / w.m) * ((S.groundAt(w.x + 15) - S.groundAt(w.x - 15)) / 30) * dt; // опора в грунте перпендикулярна склону: на подъёме её часть толкает назад, на спуске — вперёд (у ровной грязи этой части нет)
        // сколько тяги даёт грязь: трение под весом плюс «липкость» (её даёт каждое колесо — потому три моста гребут лучше двух); без блокировки одно колесо моста буксует впустую
        const gk = C.grip * pr.gr * (1 - 0.35 * S.clog[i]);         // забитый протектор гребёт на треть хуже
        const cap = (z.mu * gk * Fs + z.coh * gk * C.float * e * Math.min(1, sub / 8)) * (S.lock ? 1 : z.lockK); // без блокировки одно колесо моста буксует впустую (в песке разница меньше: он одинаковый под обоими колёсами)
        const sv = w.w * WR - w.vx, th = clamp(sv * 40, -cap, cap);  // колесо гребёт, пока не сорвётся
        w.vx += (th / w.m) * dt; w.w -= ((th * WR) / w.I) * dt;
        S.slip[i] = Math.abs(sv);
        if (S.state === 'play') { if (Math.abs(sv) > 150) dig(z, w.x, Math.min(0.012 * Math.abs(sv), 6) * dt * z.digK, sv > 0 ? 1 : -1); press(z, w.x, 0.4 * sub); } // буксуешь — закапываешься; просто проехал — остался след
        S.clog[i] = Math.min(1, S.clog[i] + z.stick * C.clogK * e * (0.1 + 0.4 * Math.min(1, Math.abs(sv) / 300) + 0.25 * Math.min(1, Math.abs(w.vx) / 300)) * dt * 0.42); // липкий грунт забивает протектор
        // на скорости грязь тормозит сильнее (с разгона далеко не уедешь), а песок — слабее: по нему надо идти ходом
        const q = clamp(sub / (0.5 * WR), 0, 1.6), rw = z.res * e * q * q * (1 + rut / 70) * (1 - 0.5 * Math.min(1, pk / (0.35 * sub + 1))) * Math.max(0.5, 1 + (z.spd * Math.abs(w.vx)) / 400); if (i < NW) R += rw; else Rt += 0.6 * rw; // колёса прицепа катятся по следу грузовика и не гребут — тормозят слабее // чем глубже сидит колесо, тем тяжелее (вдвое глубже — вчетверо); по следу переднего колеса заднему вдвое легче
      });
      // брюхо легло на грязь: кузов держит, колёса разгружены, тянет назад
      for (const c of T.circles) {
        if (!c.belly) continue;
        const [cx, cy] = P.wpt(T, c.x, c.y), z = zoneAt(L, cx); if (!z) continue;
        const e = edge(z, cx), sub = cy + c.r - S.groundAt(cx); if (sub <= 0 || e < 0.02) continue;
        const F = 420 * sub * e; T.vy -= (F / T.m) * dt; T.w += ((cx - T.x) * -F) / T.I * dt; T.vy *= 1 - Math.min(0.3, 1.2 * dt);
        R += 1200 * C.bellyDrag * e * Math.min(1, sub / 12) * (1 + Math.abs(T.vx) / 400); S.belly = true;
      }
      if (R > 0) { // сопротивление грунта: как трение — может остановить совсем
        const dv = (R / Mall) * dt, k = Math.abs(T.vx) <= dv ? -T.vx : -Math.sign(T.vx) * dv;
        for (const q of [T, ...S.wheels]) q.vx += k;
        T.w -= (C.hW * T.m * k) / T.I; // грязь держит за колёса, а не за кузов: тормозит на уровне мостов, поэтому машину не задирает носом вверх
        S.dirt = Math.min(1, S.dirt + 0.05 * dt * (1 + S.inMud));
      }
      if (Rt > 0 && S.trailer) { const B = S.trailer, Mt = B.m + S.twheels.reduce((q, w) => q + w.m, 0) + 0.5 * S.logs.length * CG.m, dv = (Rt / Mt) * dt, k = Math.abs(B.vx) <= dv ? -B.vx : -Math.sign(B.vx) * dv; for (const q of [B, ...S.twheels]) q.vx += k; } // грязь держит прицеп за колёса
      // вода: тормозит, чуть держит на плаву и отмывает
      for (const q of [T, ...S.wheels].concat(S.trailer ? [S.trailer, ...S.twheels] : [])) { const wz = waterAt(q.x); if (!wz) continue; const body = q === T || q === S.trailer, r = body ? 34 : WR, s = clamp((q.y + r - wz.y) / (2 * r), 0, 1); if (s > 0) { q.vx *= 1 - (body ? 4 : 2.2) * s * dt; q.vy *= 1 - 1.2 * s * dt; q.vy -= P.G * 0.22 * s * dt; if (q.kind === 'wheel') { S.wade = Math.max(S.wade, s); S.dirt = Math.max(0, S.dirt - 0.12 * s * dt); } } }
      S.allw.forEach((w, i) => { const wz = waterAt(w.x); if (wz && w.y + WR > wz.y + 4) S.clog[i] = Math.max(0, S.clog[i] - 0.9 * dt); }); // в броду шины промываются
    }

    // один шаг 1/120 с; inp = { gas, brake, winch (держать), awd, lock, low (включено/выключено) }
    S.step = (inp) => {
      const dt = P.DT, T = S.truck;
      if (S.state === 'dead') { S.deadT += dt; if (!manual && S.deadT > 1.7) S.respawn(); }
      const play = S.state === 'play';
      S.awd = !!inp.awd && !!b.awd; S.lock = !!inp.lock && !!b.lock; S.low = !!inp.low && !!b.low;
      S.press = b.ctis && inp.soft ? 0 : b.press; const pr = C.PR[S.press]; // с подкачкой шины спускаются прямо на ходу
      // лебёдка: держишь — трос цепляется за ближайшее дерево впереди и тянет; отпустил — отцепился
      S.target = play && !S.rope ? S.findTree() : null;
      if (play && inp.winch && !S.rope && S.target && S.fuel > 0) hookOn(S.target);              // лебёдку крутит мотор: без топлива не работает
      if (S.rope && (!inp.winch || !play || S.fuel <= 0)) hookOff();
      S.pullOn = false;
      if (S.rope) {
        const [mx, my] = S.mast(), d = Math.hypot(mx - S.rope.px, my - S.rope.py);
        if (d < S.rope.len) S.rope.len = Math.max(MIN_ROPE, d);
        if (S.rope.len > MIN_ROPE) { S.rope.len = Math.max(MIN_ROPE, S.rope.len - C.reel * dt); S.pullOn = true; }
        else hookOff(); // подтянулись к дереву — трос отцепляется сам; держишь кнопку дальше — цепляется за следующее
      }
      // мотор: задние мосты всегда, передний — с полным приводом; пониженная — больше тяги, меньше скорость
      const g = play && inp.gas && S.fuel > 0, br = play && !g && inp.brake; if (inp.gas || inp.brake || inp.winch) S.park = false;
      const [fx, fy] = P.wvec(T, 1, 0), fwd = T.vx * fx + T.vy * fy, sp = (S.low ? C.spLow : C.spHigh) * pr.sp, tq = S.low ? C.tqLow : C.tqHigh;
      // сел на брюхо на твёрдом: назад съехать можно всегда, а вперёд — только если нос уже перевалил и смотрит вниз. Рама скользит, водитель раскачивает
      const offF = S.hung && g && T.a > 0.06, off = S.fuel > 0 && (offF || (S.hung && br && fwd <= 70)), offD = offF ? 1 : -1;
      for (const c of T.circles) if (c.belly) c.mu = off ? 0.01 : C.bellyMu;
      if (off && T.vx * offD < 110) { const k = offD * 0.3 * P.G * dt; for (const q of [T, ...S.wheels]) q.vx += k; }
      S.wj.forEach((j, i) => {
        const drv = i < NW - 1 || S.awd; j.brake = 0;
        if (!play) { j.brake = S.state === 'win' ? 160000 : 0; j.maxT = 0; return; }
        if (S.park) { j.brake = 160000; j.maxT = 0; return; }
        if (g) { j.speed = sp; j.maxT = drv ? tq : 0; }
        else if (br) { if (fwd > 70) { j.brake = 110000; j.maxT = 0; } else { j.speed = -sp * 0.55; j.maxT = drv ? (fwd > -40 ? Math.max(tq, C.tqLow) : tq) * 0.8 : 0; } } // задняя передача короткая: с места тянет как пониженная
        else { j.speed = 0; j.maxT = drv ? 7000 : 0; }
      });
      if (S.trailer) { // прицеп: тормозит вместе с грузовиком; сцепка не даёт сложиться больше чем на ~45°
        const B0 = S.trailer; let slack = 1; // дышло на двух шарнирах под толчком складывается, и прицеп наезжает на грузовик. Поэтому: упор (как буфер) и привод прицепа только пока дышло вытянуто — прицеп везёт себя сам, но грузовик не толкает
        if (TR.rod) { const [hxw, hyw] = P.wpt(T, TR.hx, TR.hy), dx = B0.x - hxw, dy = B0.y - hyw, d = Math.hypot(dx, dy) || 1, dmin = TR.tx - 8; slack = clamp((d - dmin) / 6, 0, 1);
          if (d < dmin) { const nx = dx / d, ny = dy / d, vr = (B0.vx - T.vx) * nx + (B0.vy - T.vy) * ny, jj = Math.max(0, (dmin - d) * 40 - vr), kb = T.m / (T.m + B0.m), kt2 = 1 - kb; B0.vx += nx * jj * kb; B0.vy += ny * jj * kb; T.vx -= nx * jj * kt2; T.vy -= ny * jj * kt2; } }
        const td = TR.drive && S.awd ? TR.drive * slack : 0; // большой прицеп — активный: с полным приводом его мосты тоже гребут (четверть тяги колеса грузовика на каждое колесо)
        for (const j of S.twj) { j.maxT = 0; if (td && g) { j.speed = sp; j.maxT = tq * td; } else if (td && br && fwd <= 70 && S.fuel > 0) { j.speed = -sp * 0.55; j.maxT = tq * td * 0.8; } j.brake = !play ? (S.state === 'win' ? 160000 : 0) : S.park ? 160000 : br && fwd > 70 ? 60000 : 0; }
        const B = S.trailer; let da = B.a - T.a; da -= Math.round(da / (2 * Math.PI)) * 2 * Math.PI; const ov = Math.abs(da) - 0.8;
        if (ov > 0) { const q = (Math.sign(da) * ov * 90 + (B.w - T.w) * 6) * dt; B.w -= q; T.w += q * (B.I / T.I); }
      }
      // топливо: полный привод, блокировка и пониженная жгут больше; буксуешь на месте — жжёшь впустую
      const rate = C.burn * pr.bn * (S.awd ? F_AWD : 1) * (S.lock ? F_LOCK : 1) * (S.low ? F_LOW : 1);
      S.range = (S.fuel / (0.1 + rate)) * sp * WR * 0.8; // на сколько хватит в этом режиме, px
      if (play) {
        const rev = br && fwd <= 70 && S.fuel > 0;                                                 // задний ход — тоже на моторе
        const bn = Math.min(S.fuel, (0.1 + (g ? rate : rev ? rate * 0.6 : 0) + (S.pullOn ? WINCH_BURN : 0)) * dt); S.fuel -= bn; S.used += bn; // сколько сожгли за рейс — в заказах топливо стоит денег
        for (const c of L.cans) if (!c.got && Math.abs(c.x - T.x) < 90 && Math.abs(c.y - T.y) < 160) { c.got = true; S.fuel = Math.min(C.tank, S.fuel + (c.l || CAN)); S.events.push({ e: 'can', l: c.l || CAN }); }
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
      // груз: бревно, которое вывалилось из кузова и не вернулось за секунду, потеряно
      if (S.logs.length) { const [bx0, bx1, fy] = C.bed; let n = 0; for (const q of S.logs) { if (q.lost) continue; const [lx, ly] = P.local(T, q.b.x, q.b.y); let inBed = lx > bx0 - 14 && lx < bx1 + 6 && ly < fy + 6 && ly > fy - 90; if (!inBed && S.trailer) { const [tx, ty] = P.local(S.trailer, q.b.x, q.b.y); inBed = tx > -TR.bed / 2 - 14 && tx < TR.bed / 2 + 6 && ty < fy + 6 && ty > fy - 90; } q.out = inBed ? 0 : q.out + P.DT; if (q.out > 1) { q.lost = true; S.events.push({ e: 'log' }); } else n++; } S.cargo = n; }
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
  // виды грунта. t — как выглядит и ведёт себя; stick — как забивает протектор; heal — как быстро осыпается колея; digK — как быстро закапываешься при буксовке; spd — как скорость меняет сопротивление
  const ZONES = {
    shallow: { d: 26, k: 700, res: 1000, coh: 400, stick: 0.4 }, soft: { d: 34, k: 600, res: 1750, coh: 500, stick: 0.5 }, medium: { d: 46, k: 480, res: 2550, coh: 900, stick: 0.6 },
    sticky: { d: 56, k: 420, res: 3300, coh: 1400, stick: 0.6 }, swamp: { d: 72, k: 380, res: 5800, coh: 1800, stick: 0.6 }, silt: { d: 30, k: 560, res: 1500, coh: 500 },
    sand: { t: 'sand', d: 46, k: 350, res: 1750, mu: 0.36, coh: 0, stick: 0, heal: 5, digK: 3.2, spd: -0.55, lockK: 0.75 },   // песок: не липнет, но буксанул — закопался; берётся с хода и на спущенных шинах
    clay: { t: 'clay', d: 20, k: 950, res: 800, mu: 0.52, coh: 1200, stick: 1.7 },                               // глина: мелкая и скользкая, забивает протектор
    peat: { t: 'peat', d: 88, k: 250, res: 3300, mu: 0.7, coh: 500, stick: 0.45 },                               // торф: глубокий и рыхлый — садишься на брюхо
    scree: { t: 'scree', d: 30, k: 520, res: 1200, mu: 0.42, coh: 0, stick: 0, heal: 6, digK: 2.6, spd: -0.4, lockK: 0.75 },    // осыпь: мелкий камень на склоне — не липнет, из-под колёс уходит; буксанул — закопался и пополз вниз
  };

  // ---------- маршруты ----------
  // Полигон: по одному препятствию каждого вида, перед каждым — указатель и отметка. Одной сборкой всё не взять: что помогает в одном месте, мешает в другом, а топливо общее.
  function polygon() {
    const b = Route().start(-700, 600).mark(540, 'garage').flat(1400);
    b.sign(-190, 'soil', 'soft').mud(900, ZONES.soft).flat(900).can(-350).cp(-400);                         // мягкая грязь: разминка
    b.sign(-170, 'crest', 0.55).crest(240, 55).flat(700).can(-350).cp(-400);                                // гребень: длинная база садится брюхом
    b.sign(-170, 'ford', 0.9).ford(800, 49).flat(500).can(-350).cp(-400);                                   // брод 0,9 м: проходят все
    b.sign(-190, 'soil', 'sand').mud(1400, ZONES.sand).flat(500).can(-370).cp(-420);              // песок: с хода или на спущенных; встал — закопался
    b.sign(-190, 'soil', 'medium').mud(1300, ZONES.medium).flat(500).can(-370).cp(-420);                    // средняя грязь: привод и блокировка — или шины
    b.sign(-190, 'soil', 'clay').mud(1100, ZONES.clay).flat(700).can(-510).cp(-560);                        // глина: забивает протектор; дальше ровное — раскрути колёса, иначе подъём не взять
    b.sign(-170, 'climb', 30).slope(1000, 560).flat(700).can(-370).cp(-420);                      // крутой подъём: пониженная; большим колёсам не хватает тяги
    b.sign(-170, 'ford', 1.1).ford(800, 60).flat(500).can(-350).cp(-400);                                   // брод 1,1 м: лифт, колёса или шноркель
    b.sign(-190, 'soil', 'sticky').mud(1300, ZONES.sticky).flat(900).can(-370).cp(-420);          // липкая грязь: всё включить
    b.sign(-170, 'crest', 0.8).crest(300, 80).flat(600).can(-350).cp(-400);                                 // высокий гребень
    b.slope(600, -200).flat(300).sign(-170, 'ford', 1.5).ford(900, 51, ZONES.silt).flat(300).slope(600, 200).flat(400).can(-350).cp(-400); // брод с илом: воды метр и ила полметра — на указателе честные 1,5 м
    b.sign(-190, 'soil', 'peat').tree(500).tree(1050).tree(1600).tree(2150).tree(2500).can(1100).mud(1900, ZONES.peat); // торфяник: широкие спущенные колёса или лебёдка
    b.flat(500).mark(420, 'mill').flat(400).fin(0).end();
    return b.S;
  }

  // ---------- заказы: от простого к трудному; каждый следующий требует новой детали ----------
  const mk = (f) => () => { const b = Route().start(-700, 600).mark(540, 'garage').flat(1300); f(b); b.flat(500).mark(420, 'mill').flat(400).fin(0).end(); return b.S; };
  const CONTRACTS = [
    { id: 'village', name: ['Firewood for the village', 'Дрова в деревню'], cargo: 'log', pay: 28, need: [], build: mk((b) => { // задний привод: мелкая грязь, пологий холм, мелкий брод, пара ухабов
      b.sign(-190, 'soil', 'shallow').mud(700, ZONES.shallow).flat(500).cp(-300).hill(900, 90).flat(400).cp(-250);
      b.sign(-170, 'ford', 0.5).ford(600, 27).flat(500).cp(-300).bump(60, 12).flat(260).bump(60, 12); }) },
    { id: 'farm', name: ['Logs to the farm', 'Брёвна на хутор'], cargo: 'log', pay: 40, need: [['awd', 1]], build: mk((b) => { // нужен полный привод: мягкая грязь подлиннее и затяжной подъём. Грязь 17 м: без 4×4 садишься, с 4×4 стартовый грузовик проходит её и с полным кузовом (при 22 м полный кузов застревал у самого выезда)
      b.sign(-190, 'soil', 'soft').mud(900, ZONES.soft).flat(500).cp(-300).sign(-170, 'climb', 20).slope(1400, 420).flat(500).cp(-300);
      b.sign(-170, 'ford', 0.7).ford(700, 38).flat(400).cp(-250).sign(-190, 'soil', 'soft').mud(800, ZONES.soft); }) },
    { id: 'creek', name: ['Melons across the creek', 'Арбузы через ручей'], cargo: 'melon', pay: 60, need: [['awd', 1], ['low', 1]], build: mk((b) => { // нужна пониженная: брод, песок с хода, гребёнка (арбузы прыгают), крутой подъём
      b.sign(-170, 'ford', 0.9).ford(800, 49).flat(500).cp(-300).sign(-190, 'soil', 'sand').mud(1300, ZONES.sand).flat(500).can(-150).cp(-300);
      b.bump(70, 15).flat(190).bump(70, 15).flat(190).bump(70, 15).flat(500).cp(-300).sign(-170, 'climb', 28).slope(1400, 620).flat(900).cp(-300).sign(-170, 'crest', 0.55).crest(240, 55); }) },
    { id: 'pit', name: ['Barrels to the clay pit', 'Бочки в карьер'], cargo: 'barrel', pay: 150, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1]], build: mk((b) => { // нужна блокировка: глина, подъём после неё, средняя грязь — а бочки тяжёлые
      b.sign(-190, 'soil', 'clay').mud(1000, ZONES.clay).flat(700).cp(-560).sign(-170, 'climb', 28).slope(1400, 620).flat(500).can(-150).cp(-300);
      b.sign(-190, 'soil', 'medium').mud(1200, ZONES.medium).flat(500).can(-150).cp(-300).slope(700, -300).flat(300).sign(-170, 'ford', 0.9).ford(700, 49); }) },
    { id: 'mill', name: ['Logs past the mill ford', 'Брёвна через брод у мельницы'], cargo: 'log', pay: 75, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['lift', 1, 'ford']], build: mk((b) => { // нужен лифт, колёса или шноркель: брод 1,1 м; потом липкая грязь
      b.sign(-190, 'soil', 'sand').mud(1000, ZONES.sand).flat(500).cp(-300).sign(-170, 'ford', 1.1).ford(800, 60).flat(500).can(-150).cp(-300);
      b.sign(-190, 'soil', 'sticky').mud(1200, ZONES.sticky).flat(900).cp(-300).sign(-170, 'crest', 0.8).crest(300, 80).flat(500).can(-150).sign(-170, 'climb', 28).slope(1400, 620); }) },
    { id: 'bog', name: ['Barrels across the peat bog', 'Бочки через торфяник'], cargo: 'barrel', pay: 260, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford'], ['tank', 1, 'opt']], build: mk((b) => { // торф с лебёдкой, глубокий брод с илом, глина перед подъёмом
      b.sign(-190, 'soil', 'clay').mud(900, ZONES.clay).flat(600).cp(-460).sign(-170, 'climb', 28).slope(1400, 620).flat(500).can(-150).cp(-300);
      b.slope(600, -200).flat(300).sign(-170, 'ford', 1.5).ford(900, 51, ZONES.silt).flat(300).slope(600, 200).flat(500).can(-150).cp(-300);
      b.sign(-190, 'soil', 'peat').tree(500).tree(1050).tree(1600).tree(2150).tree(2500).can(1100).mud(1900, ZONES.peat); }) },    // ---------- район 2, «Болота»: грунты идут слоями, без твёрдой дороги между ними. Проходится, но туго ----------
    { id: 'layers', r: 1, name: ['Logs through layered mud', 'Брёвна через слоёную грязь'], cargo: 'log', pay: 60, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1]], build: mk((b) => { // мягкая → вязкая → липкая подряд; потом глина вплотную к подъёму — протектор не успевает очиститься
      b.sign(-190, 'soil', 'soft').mud(600, ZONES.soft).sign(-30, 'soil', 'medium').mud(600, ZONES.medium).sign(-30, 'soil', 'sticky').mud(550, ZONES.sticky).flat(500).cp(-300);
      b.hill(900, 110).flat(400).cp(-250).sign(-190, 'soil', 'clay').mud(700, ZONES.clay).flat(300).sign(-170, 'climb', 28).slope(1400, 620).flat(500).can(-150).cp(-300);
      b.sign(-170, 'ford', 0.9).ford(700, 49); }) },
    { id: 'dunes', r: 1, name: ['Melons over sand and creeks', 'Арбузы через пески и ручьи'], cargo: 'melon', pay: 65, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford']], build: mk((b) => { // из брода сразу в песок, гребёнка между двумя песками, брод с илом
      b.sign(-170, 'ford', 0.7).ford(600, 38).sign(-30, 'soil', 'sand').mud(900, ZONES.sand).flat(260).bump(70, 15).flat(190).bump(70, 15).flat(190).bump(70, 15).flat(200).cp(-120);
      b.sign(-150, 'soil', 'sand').mud(700, ZONES.sand).flat(300).sign(-170, 'climb', 20).slope(1400, 420).flat(500).cp(-300);
      b.sign(-170, 'ford', 1.5).ford(800, 51, ZONES.silt).sign(-30, 'soil', 'soft').mud(600, ZONES.soft); }) },
    { id: 'wetclay', r: 1, name: ['Barrels over wet clay', 'Бочки по размокшей глине'], cargo: 'barrel', pay: 170, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1]], build: mk((b) => { // глина — липкая — глина, и после каждой глины подъём
      b.sign(-190, 'soil', 'clay').mud(600, ZONES.clay).sign(-30, 'soil', 'sticky').mud(600, ZONES.sticky).sign(-30, 'soil', 'clay').mud(500, ZONES.clay).flat(600).sign(-170, 'climb', 24).slope(1400, 520).flat(900).can(-600).cp(-700);
      b.sign(-170, 'crest', 0.55).crest(240, 55).flat(500).cp(-300).sign(-190, 'soil', 'medium').mud(700, ZONES.medium).sign(-30, 'soil', 'clay').mud(400, ZONES.clay).flat(300).can(-150).sign(-170, 'climb', 20).slope(1400, 420); }) },
    { id: 'windows', r: 1, name: ['Logs across the bog windows', 'Брёвна через топь с окнами'], cargo: 'log', pay: 80, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['winch', 1, 'opt']], build: mk((b) => { // торф — островок — болото — островок — торф: без лебёдки никак, а она жжёт топливо
      b.sign(-190, 'soil', 'peat').tree(280).tree(720).tree(980).mud(700, ZONES.peat).flat(280).can(-140).cp(-200);
      b.sign(-190, 'soil', 'swamp').tree(350).tree(800).tree(1080).mud(800, ZONES.swamp).flat(280).can(-140).cp(-200);
      b.sign(-190, 'soil', 'peat').tree(300).tree(750).tree(1150).tree(1500).mud(900, ZONES.peat).sign(-30, 'soil', 'sticky').mud(400, ZONES.sticky); }) },
    { id: 'twofords', r: 1, name: ['Barrels across two fords', 'Бочки через два брода'], cargo: 'barrel', pay: 200, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford']], build: mk((b) => { // из брода в вязкую грязь, второй брод — с вязким дном, за ним липкая и подъём
      b.sign(-170, 'ford', 1.1).ford(800, 60).sign(-30, 'soil', 'medium').mud(600, ZONES.medium).flat(400).cp(-250);
      b.sign(-170, 'ford', 1.3).ford(900, 38, ZONES.soft).sign(-30, 'soil', 'sticky').mud(700, ZONES.sticky).flat(600).can(-300).cp(-450).sign(-170, 'climb', 24).slope(1400, 520); }) },
    { id: 'longhaul', r: 1, name: ['The long haul to the sawmill', 'Большой рейс на лесопилку'], cargo: 'log', pay: 95, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford'], ['tank', 1, 'opt']], build: mk((b) => { // всё сразу и подряд: длинный рейс, топливо в обрез
      b.sign(-190, 'soil', 'soft').mud(500, ZONES.soft).sign(-30, 'soil', 'sand').mud(700, ZONES.sand).flat(350).cp(-250).sign(-170, 'ford', 0.9).ford(700, 49).sign(-30, 'soil', 'clay').mud(600, ZONES.clay).flat(350);
      b.sign(-170, 'climb', 28).slope(1400, 620).flat(900).can(-600).cp(-700).sign(-170, 'crest', 0.8).crest(300, 80).flat(450).cp(-300).sign(-190, 'soil', 'medium').mud(600, ZONES.medium).sign(-30, 'soil', 'sticky').mud(600, ZONES.sticky).flat(450).can(-150).cp(-300);
      b.slope(600, -200).flat(300).sign(-170, 'ford', 1.5).ford(900, 51, ZONES.silt).flat(300).slope(600, 200).flat(450).cp(-300);
      b.sign(-190, 'soil', 'peat').tree(450).tree(950).tree(1400).tree(1750).can(700).mud(1400, ZONES.peat); }) },
    // ---------- район 3, «Перевал»: трассы вдвое длиннее. Новое: камни, уступы, осыпь и глина на подъёмах и спусках. Нужны грязевые шины и лифт ----------
    { id: 'pass', r: 2, name: ['Logs to the mountain lodge', 'Брёвна на горную заимку'], cargo: 'log', pay: 80, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 2, 'clayUp']], build: mk((b) => { // знакомство с горами: камни, осыпь в гору, брод, глина в гору, спуск, липкая грязь и подъём
      b.sign(-170, 'rocks', 0.4).rocks(1200, 22, 1).flat(700).can(-250, 2).cp(-400).sign(-190, 'soil', 'screeUp').mudOn(1200, 280, ZONES.scree).flat(900).can(-600, 2).cp(-400);
      b.sign(-170, 'ford', 0.9).ford(700, 49).flat(300).sign(-170, 'rocks', 0.5).rocks(900, 26, 2).flat(700).can(-250, 2).cp(-400).sign(-190, 'soil', 'clayUp').mudOn(1200, 380, ZONES.clay).flat(900).can(-600, 2).cp(-400);
      b.sign(-170, 'crest', 0.55).crest(240, 55).flat(500).slope(900, -300).flat(700).can(-250, 2).cp(-400).sign(-190, 'soil', 'sticky').mud(700, ZONES.sticky).flat(500).can(-150).sign(-170, 'climb', 24).slope(1400, 520); }) },
    { id: 'stones', r: 2, name: ['Melons down the stone river', 'Арбузы по каменной реке'], cargo: 'melon', pay: 80, need: [['awd', 1], ['low', 1], ['lock', 1], ['snorkel', 1, 'ford']], build: mk((b) => { // камни и броды вперемежку, спуск по осыпи прямо в камни: гонишь — теряешь арбузы
      b.sign(-170, 'rocks', 0.45).rocks(1100, 24, 3).sign(-170, 'ford', 0.7).ford(600, 38).flat(250).sign(-170, 'rocks', 0.5).rocks(900, 28, 4).flat(700).can(-250, 2).cp(-400);
      b.hill(900, 110).flat(300).sign(-170, 'ford', 1.1).ford(800, 60).flat(250).sign(-170, 'rocks', 0.5).rocks(1000, 26, 5).flat(700).can(-250, 2).cp(-400);
      b.sign(-190, 'soil', 'screeDown').mudOn(900, -260, ZONES.scree).sign(-60, 'rocks', 0.45).rocks(700, 24, 6).flat(700).can(-250, 2).cp(-400).sign(-190, 'soil', 'sand').mud(800, ZONES.sand).flat(300);
      b.sign(-170, 'ford', 1.3).ford(900, 38, ZONES.soft).flat(300).sign(-190, 'soil', 'clay').mud(500, ZONES.clay).flat(700).can(-250, 2).cp(-400).sign(-170, 'climb', 20).slope(1400, 420); }) },
    { id: 'mine', r: 2, name: ['Barrels to the mine', 'Бочки на рудник'], cargo: 'barrel', pay: 170, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 2, 'clayUp'], ['base', 1, 'tip6'], ['winch', 1, 'opt'], ['tank', 1, 'opt']], build: mk((b) => { // грязь в гору, два уступа, крутая глина с разгона, камни, слоёная грязь, подъём, торф с лебёдкой и осыпь под конец
      b.sign(-190, 'soil', 'mediumUp').mudOn(900, 160, ZONES.medium).flat(700).can(-250, 3).cp(-400).sign(-170, 'step', 0.35).step(20).flat(450).sign(-170, 'step', 0.4).step(22).flat(900);
      b.sign(-190, 'soil', 'clayUp').mudOn(1200, 350, ZONES.clay).flat(900).can(-600, 3).cp(-400).sign(-170, 'rocks', 0.5).rocks(900, 28, 7).flat(600).sign(-190, 'soil', 'medium').mud(600, ZONES.medium).sign(-30, 'soil', 'clay').mud(400, ZONES.clay).flat(1000).can(-550, 3).cp(-700);
      b.sign(-170, 'climb', 24).slope(1400, 520).flat(900).can(-600, 3).cp(-400).sign(-190, 'soil', 'peat').tree(450).tree(900).tree(1300).tree(1650).mud(1200, ZONES.peat).flat(1100).can(-650, 3).cp(-800);
      b.sign(-190, 'soil', 'screeUp').mudOn(1100, 260, ZONES.scree); }) },
    { id: 'scree', r: 2, name: ['Logs across the scree slopes', 'Брёвна через осыпи'], cargo: 'log', pay: 100, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 2, 'screeUp'], ['snorkel', 1, 'ford'], ['tank', 1, 'opt']], build: mk((b) => { // три осыпи в гору, между ними осыпь и глина под гору, уступ, камни, песок, гребень и брод
      b.sign(-190, 'soil', 'screeUp').mudOn(1200, 300, ZONES.scree).flat(800).can(-300, 3).cp(-400).sign(-170, 'step', 0.4).step(22).flat(500).sign(-190, 'soil', 'screeDown').mudOn(900, -280, ZONES.scree).flat(300).sign(-170, 'rocks', 0.5).rocks(800, 26, 8).flat(700).can(-250, 3).cp(-400);
      b.sign(-190, 'soil', 'sand').mud(900, ZONES.sand).flat(700).sign(-190, 'soil', 'screeUp').mudOn(1200, 320, ZONES.scree).flat(900).can(-600, 3).cp(-400).flat(400).sign(-170, 'crest', 0.55).crest(240, 55).flat(700).can(-250, 3).cp(-400);
      b.sign(-190, 'soil', 'clayDown').mudOn(1000, -320, ZONES.clay).flat(300).sign(-170, 'ford', 1.1).ford(800, 60).flat(700).sign(-190, 'soil', 'screeUp').mudOn(1100, 310, ZONES.scree).flat(900).can(-600, 3).cp(-400);
      b.sign(-190, 'soil', 'sticky').mud(800, ZONES.sticky).flat(1000).can(-600).sign(-170, 'climb', 24).slope(1400, 520); }) },
    { id: 'gorge', r: 2, name: ['Barrels through the gorge', 'Бочки через ущелье'], cargo: 'barrel', pay: 210, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 2, 'clayUp'], ['base', 1, 'tip6'], ['snorkel', 1, 'ford'], ['winch', 1, 'opt'], ['tank', 1, 'opt']], build: mk((b) => { // спуск в ущелье, камни, глубокий брод с илом, из него сразу глина в гору; болото с лебёдкой, камни, подъём, слоёная грязь, осыпь и второй брод
      b.sign(-170, 'climb', -22).slope(1000, -380).flat(500).sign(-170, 'rocks', 0.4).rocks(700, 22, 9).flat(300).slope(700, -220).flat(400).sign(-170, 'ford', 1.5).ford(900, 51, ZONES.silt).flat(250);
      b.sign(-190, 'soil', 'clayUp').mudOn(1300, 400, ZONES.clay).flat(900).can(-600, 3).cp(-400).sign(-170, 'rocks', 0.5).rocks(1000, 28, 14).flat(700).sign(-190, 'soil', 'swamp').tree(350).tree(800).tree(1150).mud(800, ZONES.swamp).flat(1300).can(-850, 3).cp(-1000);
      b.sign(-170, 'climb', 24).slope(1400, 520).flat(900).can(-600, 3).cp(-400).sign(-190, 'soil', 'medium').mud(600, ZONES.medium).sign(-30, 'soil', 'sticky').mud(600, ZONES.sticky).flat(1000).can(-550, 3).cp(-700);
      b.sign(-190, 'soil', 'screeUp').mudOn(1100, 260, ZONES.scree).flat(900).can(-600, 3).cp(-400).sign(-170, 'ford', 1.3).ford(900, 38, ZONES.soft).sign(-30, 'soil', 'sticky').mud(700, ZONES.sticky).flat(1000).can(-600).sign(-170, 'climb', 24).slope(1400, 520); }) },
    { id: 'summit', r: 2, name: ['Expedition over the pass', 'Экспедиция через перевал'], cargo: 'log', pay: 120, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 2, 'clayUp'], ['snorkel', 1, 'ford'], ['tank', 1, 'opt'], ['winch', 1, 'opt']], build: mk((b) => { // самый длинный рейс: всё, что есть в горах, подряд — вверх до перевала и вниз на ту сторону
      b.sign(-190, 'soil', 'soft').mud(600, ZONES.soft).sign(-30, 'soil', 'sand').mud(700, ZONES.sand).flat(700).can(-250, 3).cp(-400).sign(-170, 'rocks', 0.5).rocks(1000, 26, 11).flat(300).sign(-170, 'ford', 1.1).ford(800, 60).flat(700);
      b.sign(-190, 'soil', 'screeUp').mudOn(1200, 310, ZONES.scree).flat(900).can(-600, 3).cp(-400).sign(-170, 'step', 0.4).step(22).flat(900).sign(-190, 'soil', 'clayUp').mudOn(1200, 370, ZONES.clay).flat(900).can(-600, 3).cp(-400);
      b.sign(-190, 'soil', 'peat').tree(450).tree(900).tree(1300).tree(1650).tree(2100).mud(1200, ZONES.peat).flat(1200).can(-750, 3).cp(-900).sign(-170, 'climb', 24).slope(1400, 520).flat(1300).can(-900, 3).cp(-700).sign(-170, 'crest', 0.8).crest(300, 80).flat(800).can(-300, 3).cp(-400);
      b.sign(-190, 'soil', 'screeDown').mudOn(1000, -300, ZONES.scree).flat(300).sign(-170, 'rocks', 0.55).rocks(900, 30, 12).flat(700).can(-250, 3).cp(-400).sign(-190, 'soil', 'clayDown').mudOn(900, -280, ZONES.clay).flat(300).sign(-170, 'ford', 1.5).ford(900, 51, ZONES.silt).flat(700);
      b.sign(-190, 'soil', 'medium').mud(600, ZONES.medium).sign(-30, 'soil', 'sticky').mud(600, ZONES.sticky).flat(1000).can(-550, 3).cp(-700).sign(-190, 'soil', 'screeUp').mudOn(1100, 300, ZONES.scree).flat(800).can(-300, 3).cp(-400).sign(-170, 'climb', 24).slope(1400, 520); }) },

    // ---------- большие заказы: минимум груза, который берёт только большая машина; платят в разы больше. Открываются после последнего заказа района ----------
    { id: 'sawmill', r: 3, big: 1, after: 'bog', min: 11, name: ['Full timber truck through the taiga', 'Полный лесовоз через тайгу'], cargo: 'log', pay: 110, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford']], build: mk((b) => { // длинная база: грязь, холм, вязкая, брод, долгий подъём
      b.sign(-190, 'soil', 'medium').mud(800, ZONES.medium).flat(600).can(-300).cp(-300).hill(1000, 120).flat(400).sign(-190, 'soil', 'sticky').mud(800, ZONES.sticky).flat(700).can(-250).cp(-300);
      b.sign(-170, 'ford', 1.1).ford(800, 60).flat(600).sign(-170, 'climb', 22).slope(1400, 520).flat(700).can(-300).cp(-300).sign(-190, 'soil', 'swamp').tree(350).tree(800).tree(1150).mud(800, ZONES.swamp).flat(1100).can(-600).cp(-700);
      b.hill(1100, 140).flat(400).sign(-190, 'soil', 'soft').mud(700, ZONES.soft).sign(-30, 'soil', 'medium').mud(900, ZONES.medium).flat(800).can(-300).cp(-400);
      b.sign(-170, 'ford', 0.9).ford(800, 49).flat(600).sign(-170, 'climb', 20).slope(1400, 480); }) },
    { id: 'depot', r: 3, big: 1, after: 'bog', min: 9, name: ['Barrels to the fuel depot', 'Бочки на нефтебазу'], cargo: 'barrel', pay: 260, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford']], build: mk((b) => { // тяжёлый кузов: вязкая грязь, глина, брод, подъём и торф у деревьев
      b.sign(-190, 'soil', 'medium').mud(700, ZONES.medium).flat(700).can(-300).cp(-300).sign(-190, 'soil', 'clay').mud(600, ZONES.clay).flat(800).sign(-170, 'climb', 18).slope(1300, 400).flat(700).can(-250).cp(-300);
      b.sign(-170, 'ford', 1.1).ford(800, 60).flat(600).sign(-190, 'soil', 'medium').mud(800, ZONES.medium).flat(900).can(-300).cp(-400).sign(-190, 'soil', 'peat').tree(400).tree(850).tree(1250).mud(900, ZONES.peat).flat(1000).can(-500).cp(-600);
      b.sign(-190, 'soil', 'clayUp').mudOn(1000, 220, ZONES.clay).flat(900).can(-300).cp(-400).sign(-190, 'soil', 'swamp').tree(350).tree(800).tree(1150).mud(800, ZONES.swamp).flat(1100).can(-600).cp(-700);
      b.sign(-170, 'climb', 20).slope(1400, 460); }) },
    { id: 'timber', r: 3, big: 1, after: 'longhaul', min: 20, name: ['Logs with a cart across the marshes', 'Брёвна с тележкой через болота'], cargo: 'log', pay: 130, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford'], ['tank', 1, 'opt']], build: mk((b) => { // автопоезд: торф, болото, брод 1,1, подъём, вязкая подряд
      b.sign(-190, 'soil', 'peat').tree(450).tree(950).tree(1400).mud(1000, ZONES.peat).flat(1000).can(-500, 2).cp(-600).sign(-170, 'ford', 1.1).ford(800, 60).flat(700).sign(-170, 'climb', 20).slope(1400, 460).flat(800).can(-300).cp(-400);
      b.sign(-190, 'soil', 'medium').mud(900, ZONES.medium).flat(1000).can(-500, 2).cp(-600).sign(-190, 'soil', 'clayUp').mudOn(1100, 240, ZONES.clay).flat(900).can(-300).cp(-400);
      b.sign(-190, 'soil', 'medium').mud(900, ZONES.medium).flat(900).can(-400, 2).cp(-500).sign(-170, 'ford', 1.3).ford(900, 38, ZONES.soft).flat(700);
      b.sign(-190, 'soil', 'peat').tree(450).tree(950).tree(1400).mud(1000, ZONES.peat).flat(1100).can(-600, 2).cp(-700).sign(-170, 'climb', 22).slope(1400, 500); }) },
    { id: 'swampoil', r: 3, big: 1, after: 'longhaul', min: 13, name: ['Barrels across the deep marsh', 'Бочки через глубокое болото'], cargo: 'barrel', pay: 240, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 1], ['snorkel', 1, 'ford'], ['tank', 1, 'opt']], build: mk((b) => { // тринадцать бочек: болото, глина в гору, брод с илом, торф и вязкая
      b.sign(-190, 'soil', 'peat').tree(450).tree(950).tree(1400).mud(1000, ZONES.peat).flat(1100).can(-600, 2).cp(-700).sign(-190, 'soil', 'clayUp').mudOn(1200, 300, ZONES.clay).flat(900).can(-500).cp(-500);
      b.sign(-170, 'ford', 1.3).ford(900, 51, ZONES.silt).flat(800).can(-300, 2).cp(-300).sign(-190, 'soil', 'peat').tree(450).tree(950).tree(1400).mud(1100, ZONES.peat).flat(1100).can(-600).cp(-700);
      b.sign(-170, 'climb', 22).slope(1400, 500).flat(900).can(-300, 2).cp(-400).sign(-190, 'soil', 'medium').mud(700, ZONES.medium).sign(-30, 'soil', 'sticky').mud(700, ZONES.sticky).flat(900).can(-400).cp(-500);
      b.sign(-190, 'soil', 'swamp').tree(350).tree(700).tree(1000).mud(700, ZONES.swamp).flat(1100).can(-600).cp(-700).sign(-170, 'climb', 18).slope(1300, 400); }) },
    { id: 'melonfest', r: 3, big: 1, after: 'summit', min: 30, name: ['Melon road train over the pass', 'Арбузная фура через перевал'], cargo: 'melon', pay: 140, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 2, 'clayUp'], ['snorkel', 1, 'ford'], ['tank', 1, 'opt']], build: mk((b) => { // тридцать арбузов на большом прицепе: подъёмы, мелкие камни, броды — гонишь, теряешь груз
      b.sign(-170, 'climb', 20).slope(1400, 460).flat(800).can(-300, 2).cp(-300).sign(-170, 'rocks', 0.3).rocks(1000, 18, 21).flat(800).can(-300, 2).cp(-400);
      b.sign(-170, 'ford', 1.3).ford(900, 38, ZONES.soft).flat(700).sign(-190, 'soil', 'clayUp').mudOn(1200, 320, ZONES.clay).flat(900).can(-500, 2).cp(-500).sign(-170, 'climb', -20).slope(1300, -400).flat(800);
      b.sign(-170, 'rocks', 0.35).rocks(900, 20, 22).flat(700).can(-300, 2).cp(-400).sign(-190, 'soil', 'sand').mud(800, ZONES.sand).flat(700).sign(-190, 'soil', 'screeUp').mudOn(1100, 260, ZONES.scree).flat(900).can(-500, 2).cp(-500);
      b.sign(-190, 'soil', 'medium').mud(700, ZONES.medium).flat(800).can(-300).cp(-400).sign(-170, 'climb', 22).slope(1400, 500); }) },
    { id: 'convoy', r: 3, big: 1, after: 'summit', min: 24, name: ['Barrel convoy to the mountain site', 'Колонна бочек на горную стройку'], cargo: 'barrel', pay: 330, need: [['awd', 1], ['low', 1], ['lock', 1], ['tires', 2, 'clayUp'], ['snorkel', 1, 'ford'], ['tank', 1, 'opt']], build: mk((b) => { // самый тяжёлый рейс игры: 24 бочки в гору — мотор, мосты и прицеп работают вместе
      b.sign(-190, 'soil', 'medium').mud(700, ZONES.medium).flat(800).can(-300, 2).cp(-300).sign(-170, 'climb', 22).slope(1400, 500).flat(900).can(-300, 2).cp(-400);
      b.sign(-190, 'soil', 'clayUp').mudOn(1300, 360, ZONES.clay).flat(900).can(-500, 2).cp(-500).sign(-170, 'ford', 1.5).ford(900, 51, ZONES.silt).flat(800).can(-300, 2).cp(-300);
      b.sign(-190, 'soil', 'peat').tree(450).tree(950).tree(1400).mud(1100, ZONES.peat).flat(1100).can(-600, 2).cp(-700).sign(-170, 'climb', 24).slope(1400, 520).flat(900).can(-300, 2).cp(-400);
      b.sign(-190, 'soil', 'screeUp').mudOn(1100, 260, ZONES.scree).flat(900).can(-500, 2).cp(-500).sign(-190, 'soil', 'swamp').tree(350).tree(800).tree(1150).mud(900, ZONES.swamp).flat(1100).can(-600).cp(-700);
      b.sign(-190, 'soil', 'sticky').mud(800, ZONES.sticky).flat(800).sign(-170, 'climb', 24).slope(1400, 520); }) },
  ];

  const REGIONS = [{ name: ['Taiga', 'Тайга'], from: 0, n: 6 }, { name: ['Marshes', 'Болота'], from: 6, n: 6 }, { name: ['High pass', 'Перевал'], from: 12, n: 6 }, { name: ['Big orders', 'Большие заказы'], from: 18, n: 6, big: 1 }];
  root.MudSide = { create, spec, capOf, spaceOf, spaceTruck, payT, ENG_T, TR_T, REGIONS, CARGO, CAN, F_AWD, Route, DEF, PX, ZONES, CONTRACTS, routes: [{ name: ['Proving ground', 'Полигон'], build: polygon }] };
})(typeof window !== 'undefined' ? window : globalThis);
