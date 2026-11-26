// Большие заказы: каждую трассу — самой дешёвой сборкой, которая берёт минимум груза, и сборкой побольше; минимум и полный груз, два стиля езды.
// Цель: нужной вместимостью проходится, но туго. node tests/g9/big.js [id заказа]
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide, drive = require('./_bot.js');
const G1 = { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, tank: 1, winch: 1 }, G2 = Object.assign({}, G1, { tires: 2, lift: 1 });
const B = {
  sawmill: [['длинная', { base: 1 }], ['длинная+ м2', { base: 2, eng: 2 }]],
  depot: [['длинная м3', { base: 1, eng: 3 }], ['длинная 6×6', { base: 1, axles: 3 }], ['длинная+ м3', { base: 2, eng: 3 }]],
  timber: [['длинная 6×6 тележка м3', { base: 1, axles: 3, trailer: 1, eng: 3 }], ['длинная+ 6×6 тележка', { base: 2, axles: 3, trailer: 1 }], ['длинная+ 6×6 прицеп м3', { base: 2, axles: 3, trailer: 2, eng: 3 }]],
  swampoil: [['длинная+ 6×6', { base: 2, axles: 3 }], ['длинная+ 6×6 м4', { base: 2, axles: 3, eng: 4 }], ['длинная 6×6 тележка м6', { base: 1, axles: 3, trailer: 1, eng: 6 }]],
  melonfest: [['длинная 6×6 прицеп', { base: 1, axles: 3, trailer: 2 }], ['длинная+ 6×6 прицеп м4', { base: 2, axles: 3, trailer: 2, eng: 4 }]],
  convoy: [['длинная+ 6×6 прицеп м6', { base: 2, axles: 3, trailer: 2, eng: 6 }], ['длинная+ 6×6 прицеп м8', { base: 2, axles: 3, trailer: 2, eng: 8 }]],
};
const show = (r) => (r.ok ? `ДА ${r.t}с ${r.cargo}/${r.of} т${r.fuel}%${r.winch ? ' леб' + r.winch : ''}` : 'нет ' + r.why);
let runs = 0, ok = 0;
for (const c of M.CONTRACTS) { if (!c.big || (process.argv[2] && c.id !== process.argv[2])) continue;
  console.log(`${M.CONTRACTS.indexOf(c) + 1}. ${c.name[1]} — ${Math.round(M.create(c.build, {}).L.fin / 54)} м, ${c.cargo} от ${c.min}, ${c.pay} за штуку`);
  for (const [bn, b0] of B[c.id]) { const bd = Object.assign({}, c.r === 3 && /melon|convoy/.test(c.id) ? G2 : G1, b0), cap = M.capOf(M.spec(bd), c.cargo);
    if (cap < c.min) { console.log('   ' + bn.padEnd(27) + `вмещает ${cap} < ${c.min}`); continue; }
    const r = [[c.min, 0], [c.min, 1], [cap, 0], [cap, 1]].map(([n, w]) => { const S = M.create(c.build, { build: bd, cargo: n, kind: c.cargo }); S.kindFragile = c.cargo === 'melon'; return drive(S, w, 900); }); r.forEach((q) => { runs++; if (q.ok) ok++; });
    console.log('   ' + bn.padEnd(27) + `минимум ×${c.min}: ${show(r[0])} | всё вкл.: ${show(r[1])} | полный ×${cap}: ${show(r[2])} | всё вкл.: ${show(r[3])}`); }
}
console.log(`рейсов ${runs}, доехали ${ok}`);
