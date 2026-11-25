// Очень длинная база на всех заказах с полным кузовом: какой нужен мотор. Два стиля езды: аккуратный (приводы где нужны, гребень с хода)
// (как человек по подсказкам: встал — включил пониженную и держит, пока вся машина не выедет из грязи) и «всё включено» (пониженная и на гребне — садится брюхом, сдаёт назад и берёт с разгона). node tests/g9/base2.js [id заказа]
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide;
const NEED = { village: {}, farm: { awd: 1 }, creek: { awd: 1, low: 1 }, pit: { awd: 1, low: 1, lock: 1, tires: 1 }, mill: { awd: 1, low: 1, lock: 1, tires: 1, lift: 1 }, bog: { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, tank: 1, lift: 1 } };
function drive(c, build, cargo, waste) {
  const S = M.create(c.build, { build, cargo, kind: c.cargo }), L = S.L, b = S.cfg.b, tail = S.cfg.hb + 60; let t = 0, why = '', hangs = 0, back = 0, hx = 0, run = 0, keep = false;
  while (t < 300 && S.state === 'play') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + tail), ty = z ? z.t : '', d = z && ty === 'mud' ? z.d : 0, up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30, wz = S.waterAt(x + 60), cr = L.signs.find((q) => q.kind === 'crest' && q.x > x - 500 && q.x < x + 700);
    let inp = waste ? { gas: true, awd: !!b.awd, lock: !!b.lock, low: !!b.low && (up || !!z), winch: !!S.rope || !!S.target }
      : { gas: true, awd: b.awd && (!!z || up || !!wz || !!cr || S.stuckT > 0.4), lock: b.lock && (d >= 46 || ty === 'peat' || S.stuckT > 1), low: b.low && !cr && (d >= 56 || ty === 'peat' || up || keep || !!(wz && wz.depth > 55)), winch: (d >= 72 || ty === 'peat') && (!!S.rope || (S.stuckT > 1.5 && !!S.target)) };
    if (!z) keep = false; else if (ty !== 'sand' && S.stuckT > 1.1) keep = true; // подсказка «мало тяги? включи ПОНИЖ» — включил и держит до конца грязи
    if (S.hung && S.stuckT > 1 && !back && S.truck.a <= 0.06) { back = 1; hx = x; hangs++; run = Math.min(900, 300 * hangs); }   // сел брюхом: как велит подсказка — назад и с разгона
    if (back === 1) { inp = { brake: true, awd: !!b.awd }; if (x < hx - run) back = 2; }
    else if (back === 2) { inp = { gas: true, awd: !!b.awd }; if (x > hx + 500) back = 0; else if (S.hung && S.stuckT > 1 && S.truck.a <= 0.06) back = 0; }
    S.step(inp); t += 1 / 120; S.events.length = 0;
    if (S.stuckT > 10 || hangs > 4) { why = 'встал@' + Math.round(x / 54) + 'м' + (S.hung ? '(на брюхе)' : ty ? '(' + (ty === 'mud' ? 'грязь' + d : ty) + ')' : up ? '(подъём)' : ''); break; }
  }
  if (S.state === 'dead') why = '☠' + S.why + '@' + Math.round(S.truck.x / 54) + 'м';
  return (S.state === 'win' ? `ДА ${Math.round(t)}с ${S.cargo}/${S.cargo0} топл ${Math.round(100 * S.fuel / S.cfg.tank)}%` : 'нет ' + why) + (hangs ? ` (сел ${hangs}×)` : '');
}
for (const c of M.CONTRACTS) { if (process.argv[2] && c.id !== process.argv[2]) continue;
  const cap = M.capOf(M.spec(Object.assign({}, NEED[c.id], { base: 2 })), c.cargo);
  console.log(`${c.name[1]} (${c.cargo}, полный кузов ${cap})`);
  for (const eng of [0, 1, 2, 3, 5]) { const bd = Object.assign({}, NEED[c.id], { base: 2, eng });
    console.log(`   форс.${eng}`.padEnd(11) + `полный аккуратно: ${drive(c, bd, cap, 0)} | полный всё вкл.: ${drive(c, bd, cap, 1)} | половина аккуратно: ${drive(c, bd, Math.ceil(cap / 2), 0)}`); }
}
