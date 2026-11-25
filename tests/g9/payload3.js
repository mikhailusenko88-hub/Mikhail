// Обещание грузоподъёмности в горах: любая сборка с грязевыми шинами и полным разрешённым кузовом бочек довозит их на «Руднике» и в «Ущелье»
// хотя бы одним из двух стилей езды (аккуратно или всё включено). node tests/g9/payload3.js [база] — по одной базе, чтобы гонять параллельно
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide, drive = require('./_bot.js');
const A = { awd: 1, low: 1, lock: 1, tires: 2, snorkel: 1, lift: 1, tank: 1, winch: 1 };
const CT = ['mine', 'gorge'].map((id) => M.CONTRACTS.find((q) => q.id === id)); let bad = 0, all = 0, told = 0, seen = new Set();
for (const base of process.argv[2] ? [+process.argv[2]] : [0, 1, 2]) for (const axles of [2, 3]) for (const trailer of [0, 1, 2]) { const row = [];
  for (const eng of [0, 2, 4, 5, 6, 8]) { const bd = Object.assign({}, A, { base, axles, eng, trailer }), C = M.spec(bd), key = [base, axles, eng, C.tr ? trailer : 0].join(); if (seen.has(key)) continue; seen.add(key);
    const cap = M.capOf(C, 'barrel'), f = CT.map((c) => { const a = drive(M.create(c.build, { build: bd, cargo: cap, kind: 'barrel' }), 0); if (a.ok) return ''; const w = drive(M.create(c.build, { build: bd, cargo: cap, kind: 'barrel' }), 1); return w.ok ? '' : c.id + ':' + a.why + '/' + w.why; }).filter(Boolean); const warned = base === 0 && axles === 3; all++; if (f.length && !warned) bad++; if (f.length && warned) told++; // короткую трёхосную с бочками на грязном склоне опрокидывает — об этом механик говорит до рейса (совет tip6)
    row.push(`ф${eng}: ${cap} боч${f.length ? (warned ? ' ⚠ ' : ' ✗ ') + f.join(',') : ''}`); }
  if (row.length) console.log(`база ${base} ${axles === 3 ? '6×6' : '4×4'} прицеп ${trailer}  ` + row.join(' | ')); }
console.log(`сборок ${all}, не довезли полный кузов: ${bad}; из них с предупреждением механика до рейса (короткая 6×6): ${told}`.replace('; из них', ', ещё'));
