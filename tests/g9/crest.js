// Сел на брюхо на гребне → сдал назад (сколько нужно) → с разгона. Разные сборки, груз, режим заднего хода, длина разгона.
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide;
const R = (f) => () => f(M.Route().start(-300, 600).flat(1500)).flat(1500).fin(0).end().S;
const A = { awd: 1, low: 1, lock: 1, tires: 1 };
const crests = { '240×55': (b) => b.crest(240, 55), '300×80': (b) => b.crest(300, 80) };
const BU = [['длинная', { base: 1 }, 'log'], ['длинная+кол.большие', { base: 1, wheel: 2 }, 'log'], ['оч.длинная', { base: 2 }, 'log'], ['оч.длинная бочки', { base: 2 }, 'barrel'], ['оч.длинная+лифт2', { base: 2, lift: 2 }, 'log'], ['оч.длинная+защита', { base: 2, skid: 1 }, 'log'], ['оч.длинная+6×6', { base: 2, axles: 3 }, 'log'], ['оч.длинная+кол.большие', { base: 2, wheel: 2 }, 'log'], ['оч.длинная+форс.2', { base: 2, eng: 2 }, 'log'], ['оч.длинная+форс.2 бочки', { base: 2, eng: 2 }, 'barrel'], ['оч.длинная+кол.большие+форс.3', { base: 2, wheel: 2, eng: 3 }, 'log']];
let bad = 0;
for (const cn in crests) for (const [bn, bd, kind] of BU) { const row = [];
  for (const n of [0, 13]) for (const rv of [{}, { low: true }]) {
    const S = M.create(R(crests[cn]), { build: Object.assign({}, A, bd), cargo: n, kind }); let t = 0, ph = 0, hx = 0, t1 = 0, run = 300, need = 0, offT = 0, fail = '';
    while (t < 150 && S.state === 'play') { S.fuel = 50; let inp;
      if (ph === 0) { inp = { gas: S.truck.vx < 150, awd: true, low: true }; if (S.hung && S.stuckT > 1) { ph = 1; hx = S.truck.x; t1 = t; } }
      else if (ph === 1) { inp = Object.assign({ brake: true, awd: true }, rv); if (S.truck.x < hx - run) { ph = 2; if (!offT) offT = t - t1; need = run; t1 = t; } else if (t - t1 > 12) { fail = 'НЕ СЪЕХАЛ'; break; } }
      else { inp = { gas: true, awd: true }; if (S.hung && S.stuckT > 1.2 && S.truck.a <= 0.06) { if (run >= 1200) { fail = 'НЕ ХВАТИЛО 1200'; break; } run += 300; ph = 1; hx = S.truck.x; t1 = t; } }
      S.step(inp); t += 1 / 120; S.events.length = 0; }
    if (ph === 0) row.push(S.state === 'win' ? 'переполз' : '?'); else if (fail || S.state !== 'win') { row.push(fail || 'нет'); bad++; } else row.push(`съехал за ${offT.toFixed(1)}с, разгон ${Math.round(need / 54)} м`);
  }
  console.log(`${cn} ${bn.padEnd(30)} пустой: ${row[0]} / ${row[1]} | 13 шт: ${row[2]} / ${row[3]}`); }
console.log('первое — задний ход на повышенной, второе — на пониженной. Провалов: ' + bad);
