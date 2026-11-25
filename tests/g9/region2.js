// Район 2 «Болота»: каждый заказ — разными сборками, тремя загрузками и двумя стилями езды. Цель: нужной сборкой проходится, но туго.
// node tests/g9/region2.js [id заказа]
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide;
const A = { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, lift: 1 };
const BUILDS = [['после района 1', A], ['+бак', Object.assign({}, A, { tank: 1 })], ['+грязевые', Object.assign({}, A, { tires: 2, tank: 1 })], ['+форс.2+бак', Object.assign({}, A, { eng: 2, tank: 1 })], ['длинная+форс.2+бак', Object.assign({}, A, { base: 1, eng: 2, tank: 1 })], ['длинная+ +форс.3+бак', Object.assign({}, A, { base: 2, eng: 3, tank: 1 })], ['6×6+форс.2+бак+лебёдка21', Object.assign({}, A, { axles: 3, eng: 2, tank: 1, winch: 1 })]];
function drive(c, build, cargo, waste) {
  const S = M.create(c.build, { build, cargo, kind: c.cargo }), L = S.L, b = S.cfg.b, tail = S.cfg.hb + 60; let t = 0, why = '', hangs = 0, back = 0, hx = 0, keep = false, minF = 1e9, wt = 0;
  while (t < 400 && S.state === 'play') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + tail), ty = z ? z.t : '', d = z && ty === 'mud' ? z.d : 0, up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30, wz = S.waterAt(x + 60), cr = L.signs.find((q) => q.kind === 'crest' && q.x > x - 500 && q.x < x + 700);
    let inp = waste ? { gas: true, awd: !!b.awd, lock: !!b.lock, low: !!b.low && (up || !!z), winch: !!S.rope || !!S.target }
      : { gas: true, awd: b.awd && (!!z || up || !!wz || !!cr || S.stuckT > 0.4), lock: b.lock && (d >= 46 || ty === 'peat' || S.stuckT > 1), low: b.low && !cr && (d >= 56 || ty === 'peat' || up || keep || !!(wz && wz.depth > 55)), winch: (d >= 72 || ty === 'peat') && (!!S.rope || (S.stuckT > 1.5 && !!S.target)) };
    if (!z) keep = false; else if (ty !== 'sand' && S.stuckT > 1.1) keep = true;
    if (S.hung && S.stuckT > 1 && !back && S.truck.a <= 0.06) { back = 1; hx = x; hangs++; }
    if (back === 1) { inp = { brake: true, awd: !!b.awd }; if (x < hx - Math.min(900, 300 * hangs)) back = 2; } else if (back === 2) { inp = { gas: true, awd: !!b.awd }; if (x > hx + 500 || (S.hung && S.stuckT > 1 && S.truck.a <= 0.06)) back = 0; }
    S.step(inp); t += 1 / 120; S.events.length = 0; minF = Math.min(minF, S.fuel); if (S.rope) wt += 1 / 120;
    if (S.stuckT > 10 || hangs > 4) { why = 'встал@' + Math.round(x / 54) + 'м' + (S.hung ? '(брюхо)' : ty ? '(' + (ty === 'mud' ? 'грязь' + d : ty) + ')' : up ? '(подъём)' : ''); break; }
  }
  if (S.state === 'dead') why = '☠' + S.why + '@' + Math.round(S.truck.x / 54) + 'м';
  return S.state === 'win' ? `ДА ${Math.round(t)}с ${S.cargo}/${S.cargo0} мин ${Math.round(100 * minF / S.cfg.tank)}%${wt > 0.5 ? ' леб ' + Math.round(wt) + 'с' : ''}` : 'нет ' + why;
}
for (const c of M.CONTRACTS) { if (!c.r || (process.argv[2] && c.id !== process.argv[2])) continue;
  console.log(`${M.CONTRACTS.indexOf(c) + 1}. ${c.name[1]} — ${Math.round((M.create(c.build, {}).L.fin) / 54)} м, ${c.cargo}, ${c.pay} за штуку`);
  for (const [bn, bd] of BUILDS) { const cap = M.capOf(M.spec(bd), c.cargo), half = Math.ceil(cap / 2);
    console.log('   ' + bn.padEnd(26) + `половина ×${half}: ${drive(c, bd, half, 0)} | всё вкл.: ${drive(c, bd, half, 1)} | полный ×${cap}: ${drive(c, bd, cap, 0)} | всё вкл.: ${drive(c, bd, cap, 1)}`); }
}
