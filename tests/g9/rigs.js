// Автопоезда на всех заказах: сборки с тележкой и с большим прицепом везут свой полный разрешённый груз (тот, что в заказе) по всем 12 заказам.
// Плюс возврат на каждую отметку с прицепом: прицеп встаёт по земле, груз не разлетается. node tests/g9/rigs.js [часть 0|1] — пополам, чтобы гонять параллельно
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide;
const A = { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, lift: 1, tank: 1, winch: 1 };
const drive0 = require('./_bot.js');
function drive(S, waste) { const r = drive0(S, waste); S.minF = r.fuel; return r.ok ? '' : r.why; } // два стиля езды: аккуратный и «всё включено, газ в пол» — общий водитель _bot.js
const RIGS = [['длинная+ 6×6 м4 без прицепа', { base: 2, axles: 3, eng: 4, trailer: 0 }], ['длинная+ 4×4 м4 без прицепа', { base: 2, axles: 2, eng: 4, trailer: 0 }], ['длинная+ 6×6 м6 без прицепа', { base: 2, axles: 3, eng: 6, trailer: 0 }], ['длинная+ 6×6 м8 без прицепа', { base: 2, axles: 3, eng: 8, trailer: 0 }], ['длинная 4×4 м8 без прицепа', { base: 1, axles: 2, eng: 8, trailer: 0 }],
  ['длинная 6×6 м4 тележка', { base: 1, axles: 3, eng: 4, trailer: 1 }], ['длинная+ 6×6 м2 тележка', { base: 2, axles: 3, eng: 2, trailer: 1 }], ['длинная+ 6×6 м4 тележка', { base: 2, axles: 3, eng: 4, trailer: 1 }], ['длинная+ 6×6 м6 тележка', { base: 2, axles: 3, eng: 6, trailer: 1 }], ['длинная+ 6×6 м8 тележка', { base: 2, axles: 3, eng: 8, trailer: 1 }],
  ['длинная 6×6 м6 большой', { base: 1, axles: 3, eng: 6, trailer: 2 }], ['длинная 6×6 м8 большой', { base: 1, axles: 3, eng: 8, trailer: 2 }], ['длинная+ 6×6 м2 большой', { base: 2, axles: 3, eng: 2, trailer: 2 }], ['длинная+ 6×6 м4 большой', { base: 2, axles: 3, eng: 4, trailer: 2 }], ['длинная+ 6×6 м6 большой', { base: 2, axles: 3, eng: 6, trailer: 2 }], ['длинная+ 6×6 м7 большой', { base: 2, axles: 3, eng: 7, trailer: 2 }], ['длинная+ 6×6 м8 большой', { base: 2, axles: 3, eng: 8, trailer: 2 }]];
const part = process.argv[2] === undefined ? -1 : +process.argv[2], only = process.argv[3] || '', REG = process.argv[4] === undefined ? -1 : +process.argv[4]; const bad = [0, 0], all = [0, 0], lostAll = [0, 0], cargoAll = [0, 0]; let badCp = 0, cps = 0; // node rigs.js [часть 0|1|-1] [часть названия сборки|''] [район 0..2]
RIGS.forEach(([name, bd0], ri) => { if ((part >= 0 && ri % 2 !== part) || (only && !name.includes(only))) return; const row = [], cpBad = [];
  M.CONTRACTS.forEach((c, ci) => { if (REG >= 0 && (c.r || 0) !== REG) return; const bd = Object.assign({}, A, bd0); for (const [k, v] of c.need || []) bd[k] = Math.max(bd[k] || 0, v);
    const C = M.spec(bd), cap = M.capOf(C, c.cargo); let cell = `${ci + 1}:`;
    for (const waste of [0, 1]) { const S = M.create(c.build, { build: bd, cargo: cap, kind: c.cargo }); S.kindFragile = c.cargo === 'melon'; const r = drive(S, waste), lost = cap - S.cargo; all[waste]++; if (r) bad[waste]++; else { lostAll[waste] += lost; cargoAll[waste] += cap; } cell += (waste ? ' | ' : '') + (r ? '✗' + r : `${cap - lost}/${cap} т${S.minF}%`); }
    row.push(cell);
    // возврат на каждую отметку: 3 секунды покоя
    const S2 = M.create(c.build, { build: bd, cargo: cap, kind: c.cargo });
    for (const cp of bd.trailer ? S2.L.cps : []) { S2.cp = { x: cp.x, fuel: 50 }; S2.respawn(); const n0 = S2.cargo, x0 = S2.truck.x; let vmax = 0; for (let i = 0; i < 360; i++) { S2.step({}); vmax = Math.max(vmax, Math.hypot(S2.trailer.vx, S2.trailer.vy), Math.hypot(S2.truck.vx, S2.truck.vy)); }
      const ok = S2.state === 'play' && S2.cargo === n0 && vmax < 500 && Math.abs(S2.trailer.a - S2.truck.a) < 0.75 && Math.abs(S2.truck.x - x0) < 40; cps++; if (!ok) { badCp++; cpBad.push(`[заказ ${ci + 1}, отметка ${Math.round(cp.x / 54)} м: груз ${S2.cargo}/${n0}, рывок ${vmax.toFixed(0)}, ${S2.state}, излом ${(S2.trailer.a - S2.truck.a).toFixed(2)}, уехал на ${Math.round(S2.truck.x - x0)}]`); } }
  });
  console.log(name.padEnd(28) + row.join('   ') + (cpBad.length ? '\n    ' + cpBad.join('\n    ') : '')); });
console.log(`аккуратно: рейсов ${all[0]}, не доехали ${bad[0]}, потеряно ${lostAll[0]} из ${cargoAll[0]} | всё включено: рейсов ${all[1]}, не доехали ${bad[1]}, потеряно ${lostAll[1]} из ${cargoAll[1]} | возвратов на отметки ${cps}, плохих ${badCp}`);
