// Заказы: каждый проходится «своей» сборкой (той, что игрок может купить к этому моменту) и не проходится предыдущей. Автопилот; груз, топливо, время.
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js');
const M = global.MudSide;
const B0 = { awd: 0, lock: 0, low: 0, tires: 0 };
const STEPS = [['старт', B0], ['+4×4', { awd: 1, lock: 0, low: 0, tires: 0 }], ['+пониж', { awd: 1, lock: 0, low: 1, tires: 0 }], ['+блок', { awd: 1, lock: 1, low: 1, tires: 0 }], ['+лифт1+универс.', { awd: 1, lock: 1, low: 1, tires: 1, lift: 1 }], ['+шноркель+грязевые+тяговая пара', { awd: 1, lock: 1, low: 1, tires: 2, lift: 1, snorkel: 1, gear: 0 }], ['+мотор II+средние колёса', { awd: 1, lock: 1, low: 1, tires: 2, lift: 1, snorkel: 1, gear: 0, eng: 1, wheel: 1 }]];
function drive(route, build, cargo, kind) {
  const S = M.create(route, { build, cargo, kind }), L = S.L; let t = 0; const log = [];
  while (t < 300 && S.state !== 'win') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + 40), ty = z ? z.t : '', d = z && ty === 'mud' ? z.d : 0, up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30, wz = S.waterAt(x + 60);
    const inp = { gas: true, awd: !!z || up || !!wz || S.stuckT > 0.4, lock: d >= 46 || ty === 'peat' || S.stuckT > 1, low: d >= 56 || ty === 'peat' || up || (ty !== 'sand' && S.stuckT > 0.8) || !!(wz && wz.depth > 55), winch: (d >= 72 || ty === 'peat') && (!!S.rope || (S.stuckT > 1.5 && !!S.target)) };
    if (S.hung && S.stuckT > 1) { inp.gas = false; inp.brake = true; }
    S.step(inp); t += 1 / 120;
    for (const e of S.events) if (e.e === 'dead') { log.push(`☠${e.why}@${Math.round(x / 54)}м`); } S.events.length = 0;
    if (S.state === 'dead' || (S.state === 'play' && S.stuckT > 8)) { if (S.state !== 'dead') log.push(`встал@${Math.round(x / 54)}м` + (ty ? '(' + (ty === 'mud' ? 'грязь' + d : ty) + ')' : up ? '(подъём)' : '')); break; }
  }
  return `${S.state === 'win' ? 'ДА' : 'нет'} ${t.toFixed(0)}с бр ${S.cargo}/${S.cargo0} топл ${Math.round(100 * S.fuel / S.cfg.tank)}%${log.length ? ' ' + log.join(',') : ''}`;
}
M.CONTRACTS.forEach((c, i) => {
  if (process.argv[2] && +process.argv[2] > i + 1) return;
  const len = Math.round(M.create(c.build).L.fin / 54);
  console.log(`${i + 1}. ${c.name[1]} — ${len} м, ${c.cargo}, ${c.pay} за штуку`);
  for (const k of [i - 1, i, i + 1]) if (k >= 0 && k < STEPS.length) { const cap = M.capOf(M.spec(STEPS[k][1]), c.cargo); for (const n of [...new Set([1, Math.ceil(cap / 2), cap])]) console.log('     ' + (STEPS[k][0] + ' ×' + n).padEnd(36) + drive(c.build, STEPS[k][1], n, c.cargo)); }
});
