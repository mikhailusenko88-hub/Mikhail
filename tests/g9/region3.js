// Район 3 «Перевал»: каждый заказ — разными сборками, половиной и полным грузом, двумя стилями езды. Цель: нужной сборкой проходится, но туго; без грязевых шин — нет.
// node tests/g9/region3.js [id заказа]
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide, drive = require('./_bot.js');
const A = { awd: 1, low: 1, lock: 1, tires: 2, lift: 1, snorkel: 1, tank: 1, winch: 1 };
const BUILDS = [['из района 2, универс. шины', Object.assign({}, A, { tires: 1, base: 1, eng: 2 })], ['короткая м3', Object.assign({}, A, { base: 0, eng: 3 })], ['длинная м2', Object.assign({}, A, { base: 1, eng: 2 })], ['длинная+ м4', Object.assign({}, A, { base: 2, eng: 4 })], ['6×6 м5 тележка', Object.assign({}, A, { base: 2, eng: 5, axles: 3, trailer: 1 })], ['6×6 м8 большой прицеп', Object.assign({}, A, { base: 2, eng: 8, axles: 3, trailer: 2 })]];
const show = (r) => (r.ok ? `ДА ${r.t}с ${r.cargo}/${r.of} т${r.fuel}%${r.winch ? ' леб' + r.winch : ''}` : 'нет ' + r.why);
let runs = 0, ok = 0;
for (const c of M.CONTRACTS) { if (c.r !== 2 || (process.argv[2] && c.id !== process.argv[2])) continue;
  console.log(`${M.CONTRACTS.indexOf(c) + 1}. ${c.name[1]} — ${Math.round(M.create(c.build, {}).L.fin / 54)} м, ${c.cargo}, ${c.pay} за штуку`);
  for (const [bn, bd] of BUILDS) { const cap = M.capOf(M.spec(bd), c.cargo), half = Math.ceil(cap / 2), r = [[half, 0], [half, 1], [cap, 0], [cap, 1]].map(([n, w]) => { const S = M.create(c.build, { build: bd, cargo: n, kind: c.cargo }); S.kindFragile = c.cargo === 'melon'; return drive(S, w); }); runs += 4; ok += r.filter((q) => q.ok).length;
    console.log('   ' + bn.padEnd(27) + `половина ×${half}: ${show(r[0])} | всё вкл.: ${show(r[1])} | полный ×${cap}: ${show(r[2])} | всё вкл.: ${show(r[3])}`); }
}
console.log(`рейсов ${runs}, доехали ${ok}`);
