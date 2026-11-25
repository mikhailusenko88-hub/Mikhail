// Форсировка двигателя: сколько груза довозит грузовик на каждом заказе при ступенях 0..5 (автопилот). Должно расти — иначе форсировку покупать незачем.
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js');
const M = global.MudSide;
const BASE = { village: { awd: 0, lock: 0, low: 0, tires: 0 }, farm: { awd: 1, lock: 0, low: 0, tires: 0 }, creek: { awd: 1, lock: 0, low: 1, tires: 0 }, pit: { awd: 1, lock: 1, low: 1, tires: 1 }, mill: { awd: 1, lock: 1, low: 1, tires: 1, lift: 1 }, bog: { awd: 1, lock: 1, low: 1, tires: 1, lift: 1, snorkel: 1 } }; // сборка, с которой игрок приходит на заказ
function drive(route, build, cargo, kind) {
  const S = M.create(route, { build, cargo, kind }), L = S.L; let t = 0, why = '';
  while (t < 300 && S.state === 'play') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + 40), ty = z ? z.t : '', d = z && ty === 'mud' ? z.d : 0, up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30, wz = S.waterAt(x + 60), b = S.cfg.b;
    const inp = { gas: true, awd: b.awd && (!!z || up || !!wz || S.stuckT > 0.4), lock: b.lock && (d >= 46 || ty === 'peat' || S.stuckT > 1), low: b.low && (d >= 56 || ty === 'peat' || up || (ty !== 'sand' && S.stuckT > 0.8) || !!(wz && wz.depth > 55)), winch: (d >= 72 || ty === 'peat') && (!!S.rope || (S.stuckT > 1.5 && !!S.target)) };
    S.step(inp); t += 1 / 120; S.events.length = 0;
    if (S.stuckT > 8) { why = 'встал@' + Math.round(x / 54) + (ty ? '(' + (ty === 'mud' ? 'грязь' + d : ty) + ')' : up ? '(подъём)' : ''); break; }
  }
  if (S.state === 'dead') why = '☠' + S.why + '@' + Math.round(S.truck.x / 54);
  return { ok: S.state === 'win', deliv: S.cargo, why, fuel: Math.round(S.used), t: Math.round(t) };
}
const only = process.argv[2];
for (const c of M.CONTRACTS) {
  if (only && !only.split(',').includes(c.id)) continue;
  console.log(`${c.name[1]} (${c.cargo}, ${c.pay} за штуку) — сборка: ${JSON.stringify(BASE[c.id])}`);
  for (let e = 0; e <= 5; e++) {
    const bd = Object.assign({}, BASE[c.id], { eng: e }), cap = M.capOf(M.spec(bd), c.cargo), row = []; let best = 0, bestPay = 0;
    for (let n = 1; n <= cap; n++) { const r = drive(c.build, bd, n, c.cargo); row.push(r.ok ? `${n}:${r.deliv}` : `${n}:✗`); if (r.ok) { const pay = r.deliv * c.pay - r.fuel; if (pay > bestPay) { bestPay = pay; best = n; } } else if (n === cap) row.push(r.why); }
    console.log(`   ступень ${e}: ${row.join(' ').padEnd(54)} лучший рейс: ${best} шт → ${bestPay} монет`);
  }
}
