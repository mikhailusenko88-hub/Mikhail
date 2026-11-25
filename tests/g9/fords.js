// Число на указателе и правило залива — одно и то же. Каждый брод каждого заказа и полигона × сборки × манеры езды × груз:
//   настоящая глубина (вода + ил) ≤ «Брод до» грузовика → не заливает никогда;  глубже и без ила → заливает всегда, на любой скорости.
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide, PX = M.PX;
const A = { awd: 1, lock: 1, low: 1, tires: 1 };
const BUILDS = { 'старт': { awd: 0, lock: 0, low: 0, tires: 0 }, '4×4+пониж': { awd: 1, lock: 0, low: 1, tires: 0 }, 'мягк.подв+спущ.': Object.assign({}, A, { susp: 0, press: 0 }), 'форс.5+скоростная': Object.assign({}, A, { eng: 5, gear: 2 }), 'колёса средние': Object.assign({}, A, { wheel: 1 }), 'колёса большие': Object.assign({}, A, { wheel: 2 }), 'лифт1': Object.assign({}, A, { lift: 1 }), 'лифт2': Object.assign({}, A, { lift: 2 }), 'шноркель': Object.assign({}, A, { snorkel: 1 }) };
const STYLES = { 'газ в пол': () => ({ gas: true, awd: true }), 'пониженная': () => ({ gas: true, awd: true, low: true }), 'встал в воде на 3 с': (S, t, st) => { if (S.depth > 20 && !st.w) st.w = t; const hold = st.w && t - st.w < 3; return { gas: !hold, brake: !!hold, awd: true }; }, 'туда-сюда': (S, t, st) => { if (S.depth > 20 && !st.w) st.w = t; const back = st.w && t - st.w < 2.5 && ((t - st.w) % 1) < 0.5; return { gas: !back, brake: back, awd: true, low: true }; } };
const routes = M.CONTRACTS.map((c) => [c.name[1], c.build, c.cargo]).concat([['Полигон', M.routes[0].build, 'log']]);
let bad = 0, n = 0;
for (const [rn, rb, kind] of routes) {
  const L0 = M.create(rb).L, row = [];
  for (const f of L0.signs.filter((s) => s.kind === 'ford')) {
    const w = L0.water.find((q) => q.x1 > f.x), z = L0.mud.find((q) => q.wet && q.x0 > w.x0 && q.x1 < w.x1), dpx = w.depth + (z ? z.d : 0);
    for (const bn in BUILDS) {
      const C = M.spec(BUILDS[bn]), pass = dpx <= C.ford; if (!pass && z) continue; // в илистом броде колесо может утонуть не до дна — там предупреждение с запасом
      for (const sn in STYLES) for (const cargo of [0, 9]) {
        const S = M.create(rb, { build: BUILDS[bn], cargo, kind, manual: true }), st = {}; let t = 0;
        S.cp = { x: f.x - 500, y: S.groundAt(f.x - 500), fuel: C.tank }; S.respawn();
        while (t < 30 && S.state === 'play' && S.truck.x < w.x1 + 150) { S.fuel = C.tank; S.step(STYLES[sn](S, t, st)); t += 1 / 120; S.events.length = 0; }
        const flooded = S.state === 'dead' && S.why === 'water', crossed = S.truck.x >= w.x1 + 150; n++;
        if (pass && flooded) { bad++; console.log(`ЗАЛИЛО ЗРЯ: ${rn}, брод ${f.val} м, «${bn}» (берёт ${(C.ford / PX).toFixed(2)} м), ${sn}, груз ${S.cargo0}`); }
        if (!pass && crossed) { bad++; console.log(`ПРОСКОЧИЛ: ${rn}, брод ${f.val} м, «${bn}» (берёт ${(C.ford / PX).toFixed(2)} м), ${sn}, груз ${S.cargo0}`); }
      }
    }
    row.push(`${f.val} м (${dpx} px${z ? ', с илом' : ''})`);
  }
  console.log(`${rn}: ${row.join(', ') || 'бродов нет'}`);
}
console.log(bad ? `ПЛОХО: ${bad} из ${n}` : `${n} проездов: число на указателе и правило совпадают — мельче предела не заливает, глубже не проскочить`);
