'use strict';
/* Грязь, вид сбоку — рисование и управление, версия 2. Мир рисует объёмный вид Hook Truck (r3d.js); здесь — гараж-конструктор, свой грузовик
   (каждая деталь видна), живая грязь (колея остаётся), вода с вешками, указатели, брызги и дым, кнопки. Правая рука — газ и назад, левая — остальное. */
(function () {
  const P = window.TPhys, M = window.MudSide, R3 = window.Hook3D, PX = M.PX;
  const cv = document.getElementById('c'), ctx = cv.getContext('2d'), glc = document.getElementById('gl');
  const RU = /^(ru|uk|be|kk)/i.test(navigator.language || '') || /[?&]ru\b/.test(location.search);
  const T = RU ? {
    garage: 'Гараж', go: 'В рейс', cont: 'С отметки', anew: 'С начала', intro: 'Собери грузовик под полигон. Что помогает в грязи, мешает в гору — а топливо общее.',
    p: { base: 'База', lift: 'Лифт', wheel: 'Колёса', axles: 'Мосты', tires: 'Шины', eng: 'Мотор', snorkel: 'Шноркель', tank: 'Бак' },
    o: { base: ['короткая', 'длинная'], lift: ['нет', '+1', '+2'], wheel: ['малые', 'средние', 'большие'], axles: ['4×4', '6×6'], tires: ['дорожные', 'универс.', 'грязевые'], eng: ['I', 'II', 'III'], snorkel: ['нет', 'есть'], tank: ['60 л', '95 л'] },
    n: {
      base: ['Короткая база: легко переваливает гребни, но на крутом подъёме задирает нос.', 'Длинная база: в гору устойчива, но садится брюхом на гребне и тяжелее в грязи.'],
      lift: ['Без лифта: устойчив, но брюхо низко и брод мелкий.', 'Лифт +1: брюхо и брод выше на 17 см.', 'Лифт +2: ещё выше — но на самом крутом подъёме опрокидывает.'],
      wheel: ['Малые колёса: вся тяга на земле, но тонут в грязи.', 'Средние: тонут меньше, брод глубже; в гору тяги меньше.', 'Большие: почти не тонут, но в гору без мотора не идут и жгут топливо.'],
      axles: ['4×4: легче и экономнее.', '6×6: гребёт тремя мостами и не встаёт на дыбы; тяжелее и прожорливее.'],
      tires: ['Дорожные шины: быстрее и экономнее, в грязи скользят.', 'Универсальные шины: середина.', 'Грязевые шины: цепляют в грязи; на твёрдом медленнее, расход больше.'],
      eng: ['Мотор I: экономный.', 'Мотор II: тяга +25%, расход +13%.', 'Мотор III: тяга +50%, расход +26%.'],
      snorkel: ['Без шноркеля: вода выше капота — мотор заглохнет.', 'Шноркель: воздух берётся с крыши, глубокий брод не страшен.'],
      tank: ['Бак 60 л.', 'Бак 95 л: дальше едешь, чуть тяжелее.'],
    },
    sClear: 'Клиренс', sFord: 'Брод до', sPull: 'Тяга', sRange: 'Запас хода', m: 'м',
    awd: '4×4', lock: 'БЛОК', low: 'ПОНИЖ', winch: 'ЛЕБЁДКА', ahead: 'Впереди', mud: ['мягкая грязь', 'грязь', 'липкая грязь', 'болото'], crest: 'гребень', ford: 'брод', climb: 'подъём',
    hAwd: 'Буксуешь? Включи 4×4', hLock: 'Не гребёт? Включи БЛОК', hLow: 'Закапываешься или мало тяги? Включи ПОНИЖ', hWinch: 'Держи ЛЕБЁДКУ — подтянет к дереву', hBack: 'Сдай назад и возьми с разгона', hHung: 'Сел брюхом. Назад и с разгона — или нужен клиренс: в гараж', hGar: 'Не проходит? Загляни в гараж: продолжишь с отметки',
    hFuel: 'Топлива мало: выключай лишнее на твёрдой дороге', dFuel: 'Топливо кончилось', dWater: 'Мотор залило: брод глубже, чем берёт грузовик', dFlip: 'Перевернулся', cp: 'Отметка', can: '+30 топлива',
    win: 'Полигон пройден!', s1: 'Доехал', s2: 'Без возвратов', s3: 'Топлива ≥ 20%', time: 'Время', fuel: 'Топливо', again: 'Ещё раз', toGar: 'В гараж',
    keys: '→ газ   ← назад   ·   1 — 4×4   2 — блок   3 — пониж   ·   Пробел — лебёдка   ·   R — на отметку   ·   G — гараж', sec: 'с',
  } : {
    garage: 'Garage', go: 'Drive', cont: 'From checkpoint', anew: 'From start', intro: 'Build a truck for the proving ground. What helps in mud hurts on hills — and the fuel is shared.',
    p: { base: 'Wheelbase', lift: 'Lift', wheel: 'Wheels', axles: 'Axles', tires: 'Tires', eng: 'Engine', snorkel: 'Snorkel', tank: 'Tank' },
    o: { base: ['short', 'long'], lift: ['none', '+1', '+2'], wheel: ['small', 'medium', 'large'], axles: ['4×4', '6×6'], tires: ['road', 'all-terrain', 'mud'], eng: ['I', 'II', 'III'], snorkel: ['no', 'yes'], tank: ['60 L', '95 L'] },
    n: {
      base: ['Short wheelbase: rolls over crests, but lifts its nose on steep climbs.', 'Long wheelbase: steady uphill, but high-centers on crests and is heavier in mud.'],
      lift: ['No lift: stable, but low belly and shallow fording.', 'Lift +1: belly and fording depth 17 cm higher.', 'Lift +2: higher still — but tips over on the steepest climb.'],
      wheel: ['Small wheels: all the pull reaches the ground, but they sink in mud.', 'Medium: sink less, ford deeper; less pull uphill.', 'Large: barely sink, but need a bigger engine uphill and burn fuel.'],
      axles: ['4×4: lighter and thriftier.', '6×6: three axles dig in and it never rears up; heavier and thirstier.'],
      tires: ['Road tires: faster and thriftier, slippery in mud.', 'All-terrain tires: the middle ground.', 'Mud tires: bite in mud; slower on firm ground, thirstier.'],
      eng: ['Engine I: thrifty.', 'Engine II: pull +25%, fuel use +13%.', 'Engine III: pull +50%, fuel use +26%.'],
      snorkel: ['No snorkel: water above the hood stalls the engine.', 'Snorkel: air comes from the roof, deep fords are fine.'],
      tank: ['60 L tank.', '95 L tank: more range, a bit heavier.'],
    },
    sClear: 'Clearance', sFord: 'Fords up to', sPull: 'Pull', sRange: 'Range', m: 'm',
    awd: '4×4', lock: 'LOCK', low: 'LOW', winch: 'WINCH', ahead: 'Ahead', mud: ['soft mud', 'mud', 'sticky mud', 'swamp'], crest: 'crest', ford: 'ford', climb: 'climb',
    hAwd: 'Wheels spinning? Switch on 4×4', hLock: 'No bite? Switch on LOCK', hLow: 'Digging in or no pull? Switch on LOW', hWinch: 'Hold WINCH — it pulls you to the tree', hBack: 'Back up and take a run at it', hHung: 'High-centered. Back up and take a run — or get more clearance in the garage', hGar: 'No way through? Visit the garage: you continue from the checkpoint',
    hFuel: 'Low fuel: switch helpers off on firm road', dFuel: 'Out of fuel', dWater: 'Engine flooded: the ford is deeper than the truck can take', dFlip: 'Rolled over', cp: 'Checkpoint', can: '+30 fuel',
    win: 'Proving ground cleared!', s1: 'Finished', s2: 'No returns', s3: 'Fuel ≥ 20%', time: 'Time', fuel: 'Fuel', again: 'Again', toGar: 'Garage',
    keys: '→ gas   ← reverse   ·   1 — 4×4   2 — lock   3 — low   ·   Space — winch   ·   R — checkpoint   ·   G — garage', sec: 's',
  };
  const PARTS = [['base', [0, 1]], ['lift', [0, 1, 2]], ['wheel', [0, 1, 2]], ['axles', [2, 3]], ['tires', [0, 1, 2]], ['eng', [0, 1, 2]], ['snorkel', [0, 1]], ['tank', [0, 1]]];
  let W = 0, H2 = 0, DPR = 1;
  function resize() { DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H2 = innerHeight; cv.width = W * DPR; cv.height = H2 * DPR; }
  addEventListener('resize', resize); resize();
  const use3d = !!(R3 && R3.init(glc));
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const rr = (x, y, w, h, r) => { ctx.beginPath(); if (!(w > 0 && h > 0)) return; r = Math.max(0, Math.min(r, w / 2, h / 2)); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); };
  const font = (px, w = 900) => { ctx.font = `${w} ${px}px system-ui, sans-serif`; };
  const fmt = (v, d = 1) => (RU ? v.toFixed(d).replace('.', ',') : v.toFixed(d));

  // ---------- состояние ----------
  let build = Object.assign({}, M.DEF);
  try { const q = JSON.parse(localStorage.getItem('mud2.build') || 'null'); if (q) for (const [k, vals] of PARTS) if (vals.includes(q[k])) build[k] = q[k]; } catch (e) { /* */ }
  let S = null, SV = null, mode = 'garage', resume = null, rebuilds = 0, note = T.intro, buildKey = 1;
  const sw = { awd: false, lock: false, low: false }, keys = {}, ptrs = new Map(), dbg = { freeze: false };
  let realT = 0, last = performance.now(), acc = 0, camX = 0, camY = 0, Z = 0.5, buttons = [], toast = null, muted = false;
  function newSim() {
    S = M.create(0, { build }); buildKey++;
    // для картинки земля в грязи рисуется по твёрдому дну — сверху лежит живая грязь, которую продавливают колёса
    const L = S.L, xs = new Set(L.polys[0].map((q) => q[0])); for (const z of L.mud) { for (let x = z.x0; x <= z.x1; x += 45) xs.add(x); xs.add(z.x1); }
    SV = Object.create(S); SV.L = Object.assign({}, L, { polys: [[...xs].sort((a, b) => a - b).map((x) => [x, S.bedAt(x)])] });
  }
  function toGarage(keep) { resume = keep && S.cp ? { x: S.cp.x, y: S.cp.y } : null; mode = 'garage'; newSim(); camX = S.truck.x; camY = S.truck.y; ptrs.clear(); }
  function start(fromCp) {
    newSim(); sw.awd = sw.lock = sw.low = false;
    if (fromCp && resume) { S.cp = { x: resume.x, y: resume.y, fuel: S.cfg.tank }; S.respawn(); rebuilds++; } else rebuilds = 0;
    S.events.length = 0; mode = 'play'; camX = S.truck.x + 200; camY = S.truck.y - 70; ptrs.clear(); toast = null;
  }
  newSim(); camX = S.truck.x; camY = S.truck.y;

  // ---------- объёмная сцена: свои предметы поверх мира Hook Truck ----------
  let truckM = null, wheelsM = [], axM = [], paint = [], truckKey = 0, lastDirt = -1, mudM = [], lastRut = -1, canM = [], waterTop = [], blobs = [], drops = [], smoke = [], pAcc = 0, stackL = [0, 0];
  if (use3d) {
    const A = R3.api, lam = (h, o) => A.lam(h, o);
    const mk = (geo, mat, x, y, z, par, sh = true) => { const m = new A.T.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = sh; par.add(m); return m; };
    // много мелких деталей одного цвета склеиваем в один объект: грузовик рисуется за десяток вызовов, а не за сотню
    function merge(T3, geos) {
      let n = 0; const gs = geos.map((g) => { const q = g.index ? g.toNonIndexed() : g; n += q.attributes.position.count; return q; }), pos = new Float32Array(n * 3), nor = new Float32Array(n * 3); let o = 0;
      for (const g of gs) { pos.set(g.attributes.position.array, o); nor.set(g.attributes.normal.array, o); o += g.attributes.position.count * 3; g.dispose(); }
      const out = new T3.BufferGeometry(); out.setAttribute('position', new T3.BufferAttribute(pos, 3)); out.setAttribute('normal', new T3.BufferAttribute(nor, 3)); return out;
    }
    function buildTruck() {
      const T3 = A.T, sc = A.scene, c = S.cfg, b = c.b, WR = c.WR, old = [truckM, ...wheelsM, ...axM.map((q) => q.G)];
      for (const o of old) if (o) { sc.remove(o); o.traverse((q) => { if (q.geometry) q.geometry.dispose(); }); }
      paint = []; lastDirt = -1; truckKey = buildKey;
      const pm = (h) => { const m = lam(h); paint.push({ m, base: m.color.clone() }); return m; };
      const red = pm('#ff5a36'), dark = pm('#c63b1f'), fr = pm('#455a64'), blk = pm('#263238'), grey = pm('#90a4ae'), woodA = pm('#8d6e63'), woodB = pm('#795548'), fur = lam('#e8892f'), capM = lam('#ffb300');
      const gl = new T3.MeshLambertMaterial({ color: A.C('#b3e5fc'), transparent: true, opacity: 0.32 }), lamp = new T3.MeshBasicMaterial({ color: A.C('#fff59d') });
      const bk = new Map(), put = (geo, mat, x, y, z, rx, rz) => { if (rx) geo.rotateX(rx); if (rz) geo.rotateZ(rz); geo.translate(x, y, z); let q = bk.get(mat); if (!q) bk.set(mat, (q = [])); q.push(geo); };
      const flush = (par) => { for (const [mat, geos] of bk) { const m = new T3.Mesh(merge(T3, geos), mat); m.castShadow = mat !== gl && mat !== lamp; par.add(m); } bk.clear(); };
      const bx = (w, h, d, mat, x, y, z) => put(new T3.BoxGeometry(w, h, d), mat, x, y, z);
      const g = (truckM = new T3.Group()); sc.add(g);
      const yF = -(c.belly - 10), xf = c.xf, cabX1 = xf - 64, cabX0 = cabX1 - 60, cm = (cabX0 + cabX1) / 2, fa = c.ax[c.ax.length - 1];
      bx(c.len - 14, 10, 62, fr, (c.xr + xf) / 2, yF - 5, 0);                                               // рама
      bx(58, 38, 86, red, xf - 35, yF + 19, 0); bx(60, 30, 90, red, cm, yF + 15, 0);                        // капот, низ кабины
      for (const x of [cabX0 + 3, cabX1 - 3]) for (const z of [-42, 42]) bx(6, 40, 6, red, x, yF + 50, z);  // стойки
      bx(64, 6, 94, red, cm, yF + 73, 0); bx(4, 44, 90, dark, cabX0 + 2, yF + 50, 0);                       // крыша, задняя стенка
      bx(2, 38, 82, gl, cabX1 - 1, yF + 50, 0); for (const z of [-45, 45]) bx(50, 38, 2, gl, cm, yF + 50, z);
      bx(12, 16, 96, blk, xf - 3, yF + 4, 0); put(new T3.CylinderGeometry(7, 7, 30, 8), grey, xf + 3, yF + 12, 0, Math.PI / 2); // бампер, лебёдка
      for (const z of [-30, 30]) bx(4, 10, 16, lamp, xf - 5, yF + 26, z);
      for (const z of [-50, 50]) bx(2 * WR + 14, 5, 22, dark, fa, -(c.hW - WR - 11), z);                    // крылья
      const bx0 = c.xr + 6, bx1 = cabX0 - 8, bl = bx1 - bx0, bm = (bx0 + bx1) / 2;                          // кузов с брёвнами
      bx(bl, 6, 92, dark, bm, yF + 3, 0); for (const z of [-45, 45]) bx(bl, 18, 4, dark, bm, yF + 15, z); bx(4, 18, 92, dark, bx0 + 2, yF + 15, 0);
      for (const x of [bx0 + 4, bx1 - 4]) for (const z of [-45, 45]) bx(5, 44, 5, fr, x, yF + 28, z);
      [[16, -27], [16, 0], [16, 27], [35, -14], [35, 14]].forEach(([y, z], i) => put(new T3.CylinderGeometry(10, 10, bl - 12, 7), i > 2 ? woodA : woodB, bm, yF + y, z, 0, Math.PI / 2));
      put(new T3.CylinderGeometry(4, 4, 56, 6), grey, cabX0 - 4, yF + 62, -40); stackL = [cabX0 - 4, -(yF + 92)];   // выхлопная труба
      if (b.snorkel) { put(new T3.CylinderGeometry(4.5, 4.5, 72, 6), blk, cabX1 + 3, yF + 56, 46); bx(12, 9, 10, blk, cabX1 + 1, yF + 94, 46); }
      put(new T3.CylinderGeometry(11, 11, b.tank ? 76 : 46, 8), grey, (c.ax[0] + fa) / 2 - 10, yF - 16, 40, 0, Math.PI / 2); // бак под рамой
      const hx = cm + 4, hy = yF + 52;                                                                                       // Барсик за рулём
      put(new T3.SphereGeometry(14, 12, 9), fur, hx, hy, 12); for (const z of [4, 20]) put(new T3.ConeGeometry(5, 10, 4), fur, hx - 2, hy + 14, z); put(new T3.CylinderGeometry(10, 12, 6, 10), capM, hx, hy + 11, 12);
      flush(g);
      // колёса: шина с грунтозацепами по виду шин — одной «шестернёй», диск; мост и стойка (с лифтом её видно)
      const lug = [0, 8, 10][b.tires], lh = [0, 4, 7][b.tires], sh = new T3.Shape();
      if (lug) for (let k = 0; k < lug * 4; k++) { const a = (k / (lug * 4)) * Math.PI * 2, r = WR + ((k & 3) < 2 ? lh : 0); if (k) sh.lineTo(Math.cos(a) * r, Math.sin(a) * r); else sh.moveTo(r, 0); }
      wheelsM = S.wheels.map(() => {
        const G = new T3.Group(); sc.add(G);
        for (const z of [-50, 50]) {
          if (lug) put(new T3.ExtrudeGeometry(sh, { depth: 26, bevelEnabled: false, curveSegments: 1 }), blk, 0, 0, z - 13); else put(new T3.CylinderGeometry(WR, WR, 26, 18), blk, 0, 0, z, Math.PI / 2);
          put(new T3.CylinderGeometry(WR * 0.48, WR * 0.48, 29, 8), grey, 0, 0, z, Math.PI / 2);
        }
        flush(G); return G;
      });
      axM = S.wheels.map(() => { const G = new T3.Group(); sc.add(G); mk(new T3.BoxGeometry(11, 11, 96), fr, 0, 0, 0, G, false); return { G, st: mk(new T3.BoxGeometry(9, 1, 9), fr, 0, 0, 0, G, false) }; });
    }
    function sign(q, s) { // указатель: что впереди
      const T3 = A.T, cn = document.createElement('canvas'); cn.width = 192; cn.height = 128; const g = cn.getContext('2d');
      g.fillStyle = '#fff8e1'; g.fillRect(0, 0, 192, 128); g.lineWidth = 8; g.strokeStyle = '#37474f'; g.strokeRect(4, 4, 184, 120); g.lineCap = 'round'; g.lineJoin = 'round';
      if (s.kind === 'ford') { g.strokeStyle = '#1e88e5'; g.lineWidth = 7; for (let k = 0; k < 2; k++) { g.beginPath(); for (let x = 30; x <= 162; x += 6) g.lineTo(x, 34 + k * 18 + Math.sin(x / 9) * 6); g.stroke(); } }
      else if (s.kind === 'mud') { g.fillStyle = '#5d4037'; for (let k = 0; k < 4; k++) { g.globalAlpha = k < s.val ? 1 : 0.18; g.beginPath(); g.arc(42 + k * 36, 44, 13, 0, 7); g.fill(); } g.globalAlpha = 1; }
      else { g.strokeStyle = '#37474f'; g.lineWidth = 9; g.beginPath(); if (s.kind === 'crest') { g.moveTo(40, 66); g.lineTo(96, 22); g.lineTo(152, 66); } else { g.moveTo(40, 66); g.lineTo(152, 24); } g.stroke(); }
      g.fillStyle = '#263238'; g.font = '900 34px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(s.kind === 'ford' ? fmt(s.val) + ' ' + T.m : s.kind === 'mud' ? T.mud[s.val - 1] : s.kind === 'crest' ? T.crest : T.climb, 96, 98, 170);
      const tx = new T3.CanvasTexture(cn); tx.encoding = T3.sRGBEncoding; const gy = -S.groundAt(s.x), z = -q.ROAD - 30;
      q.cyl(5, 150, 6, lam('#6d4c41'), s.x, gy + 75, z, q.lvlG); const m = new T3.Mesh(new T3.PlaneGeometry(132, 88), new T3.MeshBasicMaterial({ map: tx })); m.position.set(s.x, gy + 150, z + 6); q.lvlG.add(m);
    }
    R3.onBuild = (q) => {
      const T3 = q.T, L = S.L, lvlG = q.lvlG, box = q.box, cyl = q.cyl, ROAD = q.ROAD, ZF = q.ZF, ZB = q.ZB;
      waterTop = [];
      for (const w of L.water) { // брод: вода поперёк всей сцены, у дороги — мерная вешка с полосами по полметра
        const h = w.depth + 16, m = new T3.Mesh(new T3.BoxGeometry(w.x1 - w.x0, h, ZF - ZB), new T3.MeshLambertMaterial({ color: q.C('#4fc3f7'), transparent: true, opacity: 0.58, depthWrite: false }));
        m.position.set((w.x0 + w.x1) / 2, -w.y - h / 2, (ZF + ZB) / 2); m.renderOrder = 3; lvlG.add(m); waterTop.push({ m, y: m.position.y });
        const px = (w.x0 + w.x1) / 2, by = -(w.y + w.depth), n = Math.ceil((w.depth + 60) / 27);
        for (let k = 0; k < n; k++) box(9, 27, 9, lam(k & 1 ? '#fafafa' : '#e53935'), px, by + 13.5 + k * 27, -ROAD - 14, lvlG);
      }
      for (const a of L.trees) { const gy = -a.gy; q.tree(a.x, gy, -ROAD - 46, 2.1); cyl(13, 150, 7, lam('#6d4c33'), a.x, gy + 75, -ROAD - 46, lvlG); box(30, 10, 30, lam('#ffca28'), a.x, -a.y, -ROAD - 46, lvlG); } // дерево со стропой для лебёдки
      canM = L.cans.map((c) => { const g = new T3.Group(); box(26, 34, 16, lam('#e53935'), 0, 0, 0, g); box(10, 6, 10, lam('#ffeb3b'), 6, 20, 0, g); g.position.set(c.x, -c.y - 26, 0); lvlG.add(g); return g; });
      for (const k of L.marks) {
        const gy = -k.y, z = -ROAD - 150;
        if (k.kind === 'garage') { box(300, 150, 180, lam('#90a4ae'), k.x, gy + 75, z, lvlG); box(320, 16, 200, lam('#c62828'), k.x, gy + 158, z, lvlG); box(120, 110, 6, lam('#37474f'), k.x, gy + 55, z + 92, lvlG); }
        else { box(340, 130, 200, lam('#a1887f'), k.x, gy + 65, z, lvlG); box(360, 18, 220, lam('#5d4037'), k.x, gy + 139, z, lvlG); for (let i = 0; i < 5; i++) cyl(15, 170, 8, lam(i & 1 ? '#8d6e63' : '#795548'), k.x - 250 + (i % 3) * 32 + (i > 2 ? 16 : 0), gy + 15 + (i > 2 ? 27 : 0), z + 120, lvlG, true); }
      }
      for (const s of L.signs) sign(q, s);
      // живая грязь: лента от твёрдого дна до поверхности; поверхность опускается там, где прошли колёса
      mudM = L.mud.map((z, zi) => {
        const n = z.rut.length, pos = new Float32Array(n * 12), col = new Float32Array(n * 12), nor = new Float32Array(n * 12), idx = [];
        for (let i = 0; i < n; i++) { nor[i * 12 + 1] = nor[i * 12 + 4] = 1; nor[i * 12 + 8] = nor[i * 12 + 11] = 1; if (i < n - 1) { const a = i * 4, b = a + 4; idx.push(a, b + 1, a + 1, a, b, b + 1, a + 2, a + 3, b + 3, a + 2, b + 3, b + 2); } }
        const g = new T3.BufferGeometry(); g.setAttribute('position', new T3.BufferAttribute(pos, 3)); g.setAttribute('color', new T3.BufferAttribute(col, 3)); g.setAttribute('normal', new T3.BufferAttribute(nor, 3)); g.setIndex(idx);
        const m = new T3.Mesh(g, new T3.MeshLambertMaterial({ vertexColors: true, side: T3.DoubleSide })); m.receiveShadow = true; m.frustumCulled = false; lvlG.add(m);
        return { zi, n, pos, col, g, zf: ZF + 2, zb: -ROAD - 8 }; // чуть ближе передней стенки земли, чтобы они не мерцали друг сквозь друга
      });
      lastRut = -1;
      const sc = A.scene;
      if (!blobs.length) {
        for (let i = 0; i < 30; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 0), lam('#4a2f1c')); m.visible = false; sc.add(m); blobs.push({ m, life: 0, v: [0, 0, 0], r: 1 }); }
        for (let i = 0; i < 18; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 0), new T3.MeshBasicMaterial({ color: q.C('#e1f5fe'), transparent: true, opacity: 0.8 })); m.visible = false; sc.add(m); drops.push({ m, life: 0, v: [0, 0, 0], r: 1 }); }
        for (let i = 0; i < 12; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 1), new T3.MeshBasicMaterial({ color: q.C('#78909c'), transparent: true, opacity: 0.5, depthWrite: false })); m.visible = false; sc.add(m); smoke.push({ m, life: 0, v: [0, 0, 0], r: 1 }); }
      }
    };
    const MUD_A = [0.125, 0.06, 0.028], MUD_B = [0.04, 0.02, 0.01]; // свежая грязь и продавленная, мокрая (цвета — до освещения)
    function updMud() {
      const L = S.L;
      for (const q of mudM) {
        const z = L.mud[q.zi], P3 = q.pos, Cc = q.col;
        for (let i = 0; i < q.n; i++) {
          const x = Math.min(z.x0 + 30 * i, z.x1), r = S.rutAt(x), yT = -(S.groundAt(x) + r), yB = -S.bedAt(x) - 3, k = clamp(r / (0.5 * z.d), 0, 1), o = i * 12, sh = z.wet ? 0.75 : 1;
          P3[o] = P3[o + 3] = P3[o + 6] = P3[o + 9] = x; P3[o + 1] = P3[o + 4] = P3[o + 7] = yT; P3[o + 10] = Math.min(yB, yT - 2); P3[o + 2] = P3[o + 8] = P3[o + 11] = q.zf; P3[o + 5] = q.zb;
          for (let c = 0; c < 3; c++) { const top = (MUD_A[c] + (MUD_B[c] - MUD_A[c]) * k) * sh; Cc[o + c] = top * 1.15; Cc[o + 3 + c] = top * 0.8; Cc[o + 6 + c] = top * 0.55; Cc[o + 9 + c] = MUD_B[c] * 0.7 * sh; } // продавленное место темнее и мокрее
        }
        q.g.attributes.position.needsUpdate = true; q.g.attributes.color.needsUpdate = true;
      }
    }
    const emit = (pool, x, y, z, v, r, life) => { const p = pool[(pool.i = ((pool.i | 0) + 1) % pool.length)]; p.life = p.L = life; p.r = r; p.v = v; p.m.position.set(x, y, z); p.m.visible = true; };
    function fly(pool, dt, grav, grow) { for (const p of pool) if (p.life > 0) { p.life -= dt; if (p.life <= 0) { p.m.visible = false; continue; } p.v[1] -= grav * dt; p.m.position.x += p.v[0] * dt; p.m.position.y += p.v[1] * dt; p.m.position.z += p.v[2] * dt; const s = p.r * (1 + grow * (1 - p.life / p.L)); p.m.scale.set(s, s, s); if (grow) p.m.material.opacity = 0.5 * (p.life / p.L); } }
    R3.onDraw = (S2, v, dt) => {
      A.truck.visible = false; for (const g of A.wheels) g.visible = false;
      if (truckKey !== buildKey) buildTruck();
      const tr = S.truck, c = S.cfg, WR = c.WR; truckM.position.set(tr.x, -tr.y, 0); truckM.rotation.z = -tr.a;
      S.wheels.forEach((w, i) => {
        wheelsM[i].position.set(w.x, -w.y, 0); wheelsM[i].rotation.z = -w.a;
        const ly = P.local(tr, w.x, w.y)[1], gap = Math.max(2, ly - (c.belly - 10)), q = axM[i]; q.G.position.set(w.x, -w.y, 0); q.G.rotation.z = -tr.a; q.st.scale.y = gap; q.st.position.y = gap / 2;
      });
      if (Math.abs(S.dirt - lastDirt) > 0.02) { lastDirt = S.dirt; const mc = A.C('#5b3d27'); for (const q of paint) q.m.color.copy(q.base).lerp(mc, S.dirt * 0.72); } // грязь налипает, вода смывает
      if (lastRut !== S.rutV + buildKey * 1e6) { lastRut = S.rutV + buildKey * 1e6; updMud(); }
      S.L.cans.forEach((cn, i) => { if (canM[i]) { canM[i].visible = !cn.got; canM[i].rotation.y = realT * 2; } });
      for (const wt of waterTop) wt.m.position.y = wt.y + Math.sin(realT * 1.7 + wt.y) * 1.2;
      // брызги грязи, воды и дым из трубы
      pAcc += dt; const play = mode === 'play' && S.state === 'play';
      if (play && pAcc > 0.03) {
        pAcc = 0;
        S.wheels.forEach((w, i) => {
          if (S.slip[i] > 110 && S.sunk[i] > 3 && Math.random() < 0.6) emit(blobs, w.x - 10, -w.y - WR * 0.4, (Math.random() < 0.5 ? -50 : 50) + (Math.random() - 0.5) * 20, [-110 - Math.random() * 240, 150 + Math.random() * 280, (Math.random() - 0.5) * 150], 4 + Math.random() * 6, 0.7);
          const wz = S.waterAt(w.x); if (wz && w.y + WR > wz.y + 4 && Math.abs(w.vx) > 50 && Math.random() < 0.5) emit(drops, w.x + (Math.random() - 0.5) * WR, -wz.y, (Math.random() < 0.5 ? -50 : 50), [-w.vx * 0.3 + (Math.random() - 0.5) * 120, 120 + Math.random() * 200, (Math.random() - 0.5) * 160], 3 + Math.random() * 5, 0.55);
        });
        if (v.gasOn && Math.random() < (S.stuckT > 0.3 || sw.low ? 0.9 : 0.35)) { const e = P.wpt(tr, stackL[0], stackL[1]); emit(smoke, e[0], -e[1], -40, [-30 - Math.random() * 40 - tr.vx * 0.1, 60 + Math.random() * 50, (Math.random() - 0.5) * 30], 5 + Math.random() * 4, 0.9); }
      }
      fly(blobs, dt, 900, 0); fly(drops, dt, 900, 0); fly(smoke, dt, -40, 2.2);
    };
  }

  // ---------- звук ----------
  let AC = null, eng = null;
  function audio() { if (AC) return; try { AC = new (window.AudioContext || window.webkitAudioContext)(); const o = AC.createOscillator(), f = AC.createBiquadFilter(), g = AC.createGain(); o.type = 'sawtooth'; f.type = 'lowpass'; f.frequency.value = 380; g.gain.value = 0; o.connect(f); f.connect(g); g.connect(AC.destination); o.start(); eng = { o, g }; } catch (e) { AC = null; } }
  function tone(fq, d, v) { if (!AC || muted) return; try { const t = AC.currentTime, o = AC.createOscillator(), g = AC.createGain(); o.type = 'triangle'; o.frequency.value = fq; g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t + d); o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + d + 0.02); } catch (e) { /* */ } }

  // ---------- управление ----------
  const TOG = ['awd', 'lock', 'low'];
  function flip(k) { if (mode !== 'play' || S.state !== 'play') return; sw[k] = !sw[k]; tone(sw[k] ? 760 : 420, 0.07, 0.12); }
  function setPart(k, v) { if (build[k] === v) { note = T.n[k][PARTS.find((q) => q[0] === k)[1].indexOf(v)]; return; } build[k] = v; note = T.n[k][PARTS.find((q) => q[0] === k)[1].indexOf(v)]; try { localStorage.setItem('mud2.build', JSON.stringify(build)); } catch (e) { /* */ } newSim(); tone(660, 0.06, 0.1); }
  function press(id) {
    if (id === 'go') start(false); else if (id === 'cont') start(true); else if (id === 'gar') toGarage(mode === 'play'); else if (id === 'again') start(false);
    else if (id === 'rescue') { if (mode === 'play') S.rescue(); } else if (id === 'mute') muted = !muted;
    else if (id[0] === 'p') { const [, k, v] = id.split(':'); setPart(k, +v); } else if (TOG.includes(id)) flip(id); else return false;
    return true;
  }
  addEventListener('keydown', (e) => {
    if (e.repeat) return; keys[e.code] = true; audio();
    if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
    if (mode === 'play') { if (e.code === 'Digit1' || e.code === 'KeyQ') flip('awd'); else if (e.code === 'Digit2' || e.code === 'KeyE') flip('lock'); else if (e.code === 'Digit3' || e.code === 'ShiftLeft') flip('low'); else if (e.code === 'KeyR') S.rescue(); else if (e.code === 'KeyG') toGarage(true); }
    else if (e.code === 'Enter') { if (mode === 'garage') start(!!resume); else start(false); }
  });
  addEventListener('keyup', (e) => { keys[e.code] = false; });
  const hit = (x, y) => buttons.find((b) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
  const held = (id) => { for (const p of ptrs.values()) if (p === id) return true; return false; };
  cv.addEventListener('pointerdown', (e) => { audio(); try { cv.setPointerCapture(e.pointerId); } catch (er) { /* */ } const b = hit(e.clientX, e.clientY); if (b && !press(b.id)) ptrs.set(e.pointerId, b.id); });
  const up = (e) => ptrs.delete(e.pointerId);
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up); cv.addEventListener('contextmenu', (e) => e.preventDefault());
  function input() {
    const k = keys;
    return { gas: !!(k.ArrowRight || k.KeyD) || held('gas'), brake: !!(k.ArrowLeft || k.KeyA) || held('brake'), winch: !!(k.Space || k.KeyW || k.ArrowUp) || held('winch'), awd: sw.awd, lock: sw.lock, low: sw.low };
  }

  // ---------- рисование поверх ----------
  function lines(t, mw, px, wt = 800) { font(px, wt); const out = []; let cur = ''; for (const w of t.split(' ')) { const q = cur ? cur + ' ' + w : w; if (ctx.measureText(q).width > mw && cur) { out.push(cur); cur = w; } else cur = q; } if (cur) out.push(cur); return out; }
  function bubble(t, y, col = 'rgba(0,0,0,0.5)', cx = W / 2, mw = Math.min(W - 40, 620)) { const px = Math.min(W, H2) < 430 ? 15 : 18, L = lines(t, mw - 30, px), w = Math.min(mw, Math.max(...L.map((q) => ctx.measureText(q).width)) + 34), h = L.length * (px + 6) + 16; ctx.fillStyle = col; rr(cx - w / 2, y, w, h, 16); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; L.forEach((q, i) => ctx.fillText(q, cx, y + 8 + (px + 6) * (i + 0.5), w - 20)); return h; }
  function btn(b, txt, col, on, px) {
    ctx.globalAlpha = on ? 0.97 : 0.78; ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(b.x, b.y + 4, b.w, b.h, 14); ctx.fill(); ctx.fillStyle = col; rr(b.x, b.y + (on ? 3 : 0), b.w, b.h, 14); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; font(px || Math.round(Math.min(b.h * 0.44, b.w * 0.34, (b.w * 1.45) / Math.max(3, txt.length))));
    ctx.fillText(txt, b.x + b.w / 2, b.y + b.h / 2 + (on ? 3 : 0) + 1, b.w - 8);
  }
  const B = (id) => buttons.find((b) => b.id === id);
  const land = () => W > H2 * 1.15;

  function drawGarage() {
    // слева (или сверху) грузовик, справа (или снизу) детали; у каждой детали — что она даёт и чем за неё платишь
    const L = land(), px = L ? Math.max(300, W * 0.52) : 0, pw = W - px - 10, top = L ? 8 : Math.round(H2 * 0.33), c = S.cfg;
    ctx.fillStyle = 'rgba(255,253,247,0.94)'; rr(px + (L ? 0 : 8), top, L ? pw : W - 16, H2 - top - 8, 18); ctx.fill();
    const x0 = px + (L ? 12 : 20), ww = (L ? pw : W - 16) - 24, small = H2 - top < 500;
    buttons = [{ id: 'mute', x: 10, y: 10, w: 44, h: 44 }];
    // сводка: четыре числа, которые сравниваешь с указателями на дороге
    const stats = [[T.sClear, fmt(c.clear / PX, 2) + ' ' + T.m], [T.sFord, fmt(c.ford / PX, 2) + ' ' + T.m], [T.sPull, Math.round((100 * c.tqLow / c.WR) / (264000 / 27)) + '%'], [T.sRange, Math.round(((c.tank / (0.1 + c.burn * 1.35)) * c.spHigh * c.WR * 0.8) / PX) + ' ' + T.m]];
    let y = top + 10; const sw4 = ww / 4;
    stats.forEach(([n, v], i) => { ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#78909c'; font(small ? 10 : 12, 800); ctx.fillText(n, x0 + sw4 * (i + 0.5), y + 8, sw4 - 6); ctx.fillStyle = '#263238'; font(small ? 16 : 19); ctx.fillText(v, x0 + sw4 * (i + 0.5), y + (small ? 26 : 30), sw4 - 6); });
    y += small ? 40 : 48;
    const goH = small ? 46 : 56, noteH = small ? 34 : 44, rh = Math.min(48, (H2 - 8 - y - goH - noteH - 22) / PARTS.length), lw = Math.min(110, ww * 0.27);
    for (const [k, vals] of PARTS) {
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#37474f'; font(Math.min(16, rh * 0.4), 900); ctx.fillText(T.p[k], x0, y + rh / 2, lw - 6);
      const bw = (ww - lw - (vals.length - 1) * 6) / vals.length;
      vals.forEach((v, i) => { const b = { id: `p:${k}:${v}`, x: x0 + lw + i * (bw + 6), y: y + 3, w: bw, h: rh - 6 }, on = build[k] === v; buttons.push(b); ctx.fillStyle = on ? '#fb8c00' : '#cfd8dc'; rr(b.x, b.y, b.w, b.h, 10); ctx.fill(); ctx.fillStyle = on ? '#fff' : '#455a64'; ctx.textAlign = 'center'; font(Math.min(15, rh * 0.36, (bw * 1.6) / Math.max(3, T.o[k][i].length)), 900); ctx.fillText(T.o[k][i], b.x + b.w / 2, b.y + b.h / 2 + 1, b.w - 6); });
      y += rh;
    }
    const nl = lines(note, ww - 8, small ? 12 : 14, 700).slice(0, 2); ctx.fillStyle = '#546e7a'; ctx.textAlign = 'left'; nl.forEach((q, i) => ctx.fillText(q, x0, y + 12 + i * (small ? 15 : 18), ww));
    const gy = H2 - 8 - goH - 10;
    if (resume) { const hw = (ww - 8) / 2, b1 = { id: 'cont', x: x0, y: gy, w: hw, h: goH }, b2 = { id: 'go', x: x0 + hw + 8, y: gy, w: hw, h: goH }; buttons.push(b1, b2); btn(b1, '▶ ' + T.cont, '#43a047', false, small ? 15 : 18); btn(b2, '↺ ' + T.anew, '#78909c', false, small ? 15 : 18); }
    else { const b1 = { id: 'go', x: x0, y: gy, w: ww, h: goH }; buttons.push(b1); btn(b1, '▶ ' + T.go, '#43a047', false, small ? 20 : 24); }
    const mb = B('mute'); ctx.fillStyle = 'rgba(0,0,0,0.34)'; rr(mb.x, mb.y, mb.w, mb.h, 12); ctx.fill(); ctx.fillStyle = '#fff'; font(21); ctx.textAlign = 'center'; ctx.fillText(muted ? '🔇' : '🔊', mb.x + 22, mb.y + 23);
    ctx.fillStyle = '#fff'; ctx.strokeStyle = 'rgba(0,0,0,0.35)'; ctx.lineWidth = 4; font(small ? 20 : 26); ctx.textAlign = 'left'; ctx.strokeText(T.garage, 64, 33); ctx.fillText(T.garage, 64, 33);
    return { px: L ? px / 2 : W / 2, py: L ? H2 * 0.56 : top * 0.62, zw: L ? px : W, zh: L ? H2 : top };
  }

  function layout() {
    const sm = Math.min(W, H2) < 430, g = sm ? 8 : 12, bw = sm ? 86 : 104, bh = sm ? 74 : 86, by = H2 - bh - g - 4, th = sm ? 50 : 56, c = S.cfg.b;
    buttons = [{ id: 'gas', x: W - bw - g, y: by, w: bw, h: bh }, { id: 'brake', x: W - bw * 2 - g * 2, y: by, w: bw, h: bh }, { id: 'gar', x: W - 58, y: 10, w: 48, h: 44 }, { id: 'rescue', x: W - 112, y: 10, w: 48, h: 44 }, { id: 'mute', x: W - 166, y: 10, w: 48, h: 44 }];
    const tg = TOG.filter((k) => c[k]), one = W - (bw * 2 + g * 3) - g >= 130 + tg.length * 70;               // лёжа всё в один ряд слева, стоя — лебёдка внизу, переключатели над ней
    if (one) { const ww = sm ? 112 : 130, tw = Math.min(sm ? 70 : 86, (W - (bw * 2 + g * 3) - g - ww - 8 - tg.length * 6) / Math.max(1, tg.length)); buttons.push({ id: 'winch', x: g, y: by, w: ww, h: bh }); tg.forEach((k, i) => buttons.push({ id: k, x: g + ww + 8 + i * (tw + 6), y: by, w: tw, h: bh })); }
    else { const ww = W - (bw * 2 + g * 3) - g, tw = (W - g * 2 - (tg.length - 1) * 6) / Math.max(1, tg.length); buttons.push({ id: 'winch', x: g, y: by, w: ww, h: bh }); tg.forEach((k, i) => buttons.push({ id: k, x: g + i * (tw + 6), y: by - th - 10, w: tw, h: th })); }
  }
  function hint() {
    if (S.state === 'dead') return [S.why === 'fuel' ? T.dFuel : S.why === 'water' ? T.dWater : T.dFlip, 'rgba(183,28,28,0.88)'];
    if (toast && realT - toast.t < 1.6) return [toast.s, 'rgba(46,125,50,0.88)'];
    if (S.hung && S.stuckT > 0.8) return [T.hHung, 'rgba(230,81,0,0.92)'];
    if (S.stuckT > 1.1) { const c = S.cfg.b, mud = S.inMud > 0; return [c.awd && !sw.awd ? T.hAwd : mud && c.lock && !sw.lock ? T.hLock : c.low && !sw.low ? T.hLow : S.target ? T.hWinch : S.stuckT > 5 ? T.hGar : T.hBack, 'rgba(230,81,0,0.92)']; }
    if (S.fuel < 0.22 * S.cfg.tank && S.inMud === 0 && (sw.awd || sw.lock || sw.low)) return [T.hFuel, 'rgba(0,0,0,0.5)'];
    return null;
  }
  function drawHud(inp) {
    layout();
    const fw = Math.min(190, W * 0.4), fx = 12, fy = 14, k = S.fuel / S.cfg.tank, c = S.cfg;
    ctx.fillStyle = 'rgba(0,0,0,0.4)'; rr(fx, fy, fw, 24, 12); ctx.fill(); ctx.fillStyle = k < 0.22 ? '#e53935' : k < 0.45 ? '#ffb300' : '#7cb342'; rr(fx + 3, fy + 3, Math.max(8, (fw - 6) * k), 18, 9); ctx.fill();
    font(13); ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText('⛽ ' + Math.round(k * 100) + '%  ≈ ' + Math.round(S.range / PX) + ' ' + T.m, fx + 10, fy + 13); // запас хода в этом режиме: включил привод — цифра упала
    // мосты: серое — не ведёт, зелёное — держит, красное — буксует
    const n = S.wheels.length, wx = fx + 4, wy = fy + 34, wl = 30 + n * 20; ctx.fillStyle = 'rgba(0,0,0,0.35)'; rr(wx, wy, wl, 30, 10); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.5)'; rr(wx + 8, wy + 5, wl - 16, 8, 3); ctx.fill();
    S.wheels.forEach((w, i) => { const drv = i < n - 1 || S.awd; ctx.fillStyle = !drv ? '#90a4ae' : S.slip[i] > 150 || (inp.gas && S.stuckT > 0.4) ? '#ff5252' : '#69f0ae'; ctx.beginPath(); ctx.arc(wx + 18 + (i * (wl - 36)) / Math.max(1, n - 1), wy + 19, 7, 0, 7); ctx.fill(); });
    // что впереди: ближайший указатель и сколько до него
    const nx = S.L.signs.find((s) => s.x > S.truck.x - 60 && s.x < S.truck.x + 2200);
    if (nx) { const d = Math.max(0, Math.round((nx.x + 200 - S.truck.x) / PX)), t = `${T.ahead}: ${nx.kind === 'ford' ? T.ford + ' ' + fmt(nx.val) + ' ' + T.m : nx.kind === 'mud' ? T.mud[nx.val - 1] : nx.kind === 'crest' ? T.crest : T.climb}${d > 2 ? ' · ' + d + ' ' + T.m : ''}`; font(13, 800); const tw = ctx.measureText(t).width + 22, tx = wx + wl + 8; ctx.fillStyle = 'rgba(0,0,0,0.4)'; rr(tx, wy + 2, Math.min(tw, W - tx - 8), 26, 13); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.fillText(t, tx + 11, wy + 16, W - tx - 30); }
    btn(B('gas'), '▶', '#43a047', inp.gas); btn(B('brake'), '◀', '#e53935', inp.brake);
    btn(B('winch'), '⚓ ' + T.winch, S.target || S.rope ? '#5c6bc0' : '#78909c', inp.winch);
    TOG.forEach((q) => { const b = B(q); if (b) btn(b, T[q], sw[q] ? '#fb8c00' : '#546e7a', sw[q]); });
    for (const [id, ch] of [['gar', '🔧'], ['rescue', '↺'], ['mute', muted ? '🔇' : '🔊']]) { const b = B(id); ctx.fillStyle = 'rgba(0,0,0,0.34)'; rr(b.x, b.y, b.w, b.h, 12); ctx.fill(); ctx.fillStyle = '#fff'; font(21); ctx.textAlign = 'center'; ctx.fillText(ch, b.x + b.w / 2, b.y + b.h / 2 + 1); }
    const h = hint(); if (h) bubble(h[0], wy + 40, h[1]);
    if (!matchMedia('(pointer: coarse)').matches && !ptrs.size && S.t < 14 && !rebuilds) { font(13, 800); const tw = Math.min(ctx.measureText(T.keys).width + 36, W - 16), ky = h ? wy + 96 : wy + 40; ctx.fillStyle = 'rgba(0,0,0,0.45)'; rr(W / 2 - tw / 2, ky, tw, 30, 15); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.fillText(T.keys, W / 2, ky + 15, tw - 24); }
  }
  function star5(x, y, r, col) { ctx.fillStyle = col; ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, q = i & 1 ? r * 0.45 : r; ctx.lineTo(x + Math.cos(a) * q, y + Math.sin(a) * q); } ctx.closePath(); ctx.fill(); }
  function drawWin() {
    ctx.fillStyle = 'rgba(10,40,70,0.45)'; ctx.fillRect(0, 0, W, H2);
    const w = Math.min(W - 28, 460), h = Math.min(H2 - 24, 330), x = W / 2 - w / 2, y = H2 / 2 - h / 2, k = S.fuel / S.cfg.tank, clean = S.rescues === 0 && rebuilds === 0, st = [true, clean, clean && k >= 0.2];
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 22); ctx.fill();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#2e7d32'; font(26); ctx.fillText(T.win, W / 2, y + 38, w - 24);
    [T.s1, T.s2, T.s3].forEach((s, i) => { const cx = W / 2 + (i - 1) * w * 0.3; star5(cx, y + 104, i === 1 ? 40 : 33, st[i] ? '#ffc107' : '#cfd8dc'); ctx.fillStyle = '#546e7a'; font(13, 800); ctx.fillText(s, cx, y + 158, w * 0.29); });
    ctx.fillStyle = '#37474f'; font(17, 800); ctx.fillText(`${T.time}: ${S.t.toFixed(0)} ${T.sec}   ·   ${T.fuel}: ${Math.round(k * 100)}%`, W / 2, y + 198, w - 24);
    const bw = (w - 60) / 2, b1 = { id: 'gar', x: x + 24, y: y + h - 78, w: bw, h: 56 }, b2 = { id: 'again', x: x + 36 + bw, y: y + h - 78, w: bw, h: 56 }; buttons = [b1, b2]; btn(b1, '🔧 ' + T.toGar, '#fb8c00', false, 18); btn(b2, '↻ ' + T.again, '#43a047', false, 18);
  }

  // ---------- кадр ----------
  function frame(now) { try { frame1(now); } catch (e) { if (!frame.err) { frame.err = 1; try { console.error(e); } catch (q) { /* */ } } } requestAnimationFrame(frame); }
  function frame1(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now; realT += dt;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.clearRect(0, 0, W, H2);
    let inp = { gas: false, brake: false, winch: false, awd: sw.awd, lock: sw.lock, low: sw.low };
    if (!dbg.freeze && !document.hidden) {
      if (mode === 'play') inp = input();
      acc += dt; let n = 0; while (acc >= P.DT && n < 8) { S.step(mode === 'garage' ? {} : inp); acc -= P.DT; n++; }
      if (mode === 'garage') S.fuel = S.cfg.tank;
      for (const e of S.events) {
        if (mode === 'garage') continue;
        if (e.e === 'cp') { toast = { s: T.cp, t: realT }; tone(880, 0.1, 0.1); } else if (e.e === 'can') { toast = { s: T.can, t: realT }; tone(990, 0.14, 0.12); }
        else if (e.e === 'dead') tone(160, 0.4, 0.15); else if (e.e === 'hook') tone(620, 0.06, 0.1); else if (e.e === 'win') { mode = 'win'; tone(1200, 0.3, 0.14); }
      }
      S.events.length = 0;
    }
    if (eng) { const on = mode === 'play' && S.state === 'play' && !muted && !document.hidden, t = AC.currentTime, wsp = Math.abs(S.wheels[0].w) * S.WR; eng.o.frequency.setTargetAtTime(48 + wsp * (sw.low ? 0.22 : 0.1) + (inp.gas ? 26 : 0), t, 0.08); eng.g.gain.setTargetAtTime(on ? 0.025 + (inp.gas ? 0.04 : 0) : 0, t, 0.1); }
    const tr = S.truck, port = !land();
    if (mode === 'garage') {
      const g = drawGarage(), zg = Math.min(g.zw / (S.cfg.len + 190), g.zh / 330); camX = tr.x; camY = tr.y;
      if (use3d) R3.draw(SV, { camX, camY, Z: zg, W, H: H2, DPR, t: realT, lvl: 1, duo: false, shake: 0, gas: false, gasOn: false, theme: 0, g: { tilt: 0.14, yaw: 0.42, px: g.px, py: g.py } });
      return;
    }
    // камера: ближе, когда ползёшь в грязи; дальше на скорости
    const zb = clamp(port ? W / 700 : W / 1500, 0.46, 0.82), zt = zb * (S.inMud && Math.abs(tr.vx) < 200 ? 1.1 : Math.abs(tr.vx) > 520 ? 0.92 : 1); Z += (zt - Z) * Math.min(1, dt * 1.5);
    camX += (tr.x + (port ? 110 : 240) - camX) * Math.min(1, dt * 4); camY += (tr.y - 70 - camY) * Math.min(1, dt * 3);
    // земля под колёсами встаёт чуть выше кнопок — на любом экране грузовик виден целиком
    layout(); const yb = Math.min(...buttons.filter((q) => q.y > H2 / 2).map((q) => q.y)), oy = clamp((yb - 30 - (S.cfg.hW + S.WR) * Z) / H2 - 0.5 - (70 * Z) / H2, -0.2, 0.3);
    if (use3d) R3.draw(SV, { camX, camY, Z, W, H: H2, DPR, t: realT, lvl: 1, duo: false, shake: 0, gas: inp.gas && !S.inMud && !S.wade, gasOn: inp.gas && S.fuel > 0, oy, theme: 0 });
    if (mode === 'win' && S.wonT > 0.9) drawWin(); else drawHud(inp);
  }
  window.__mud = { get S() { return S; }, sw, keys, dbg, get mode() { return mode; }, get buttons() { return buttons; }, get build() { return build; }, press, setPart, start, toGarage, flip };
  requestAnimationFrame(frame);
})();
