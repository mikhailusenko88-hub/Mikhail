// Топливо по заказам: сколько сжигает аккуратный рейс (приводы только где нужны) и расточительный (всё включено всегда), сколько остаётся в баке.
// Цель: аккуратный доезжает с запасом, расточительный на средних и дальних заказах — нет. Плюс цена лебёдки в топливе.
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js');
const M = global.MudSide;
const BASE = { village: { awd: 0, lock: 0, low: 0, tires: 0 }, farm: { awd: 1, lock: 0, low: 0, tires: 0 }, creek: { awd: 1, lock: 0, low: 1, tires: 0 }, pit: { awd: 1, lock: 1, low: 1, tires: 1 }, mill: { awd: 1, lock: 1, low: 1, tires: 1, lift: 1 }, bog: { awd: 1, lock: 1, low: 1, tires: 1, lift: 1, snorkel: 1 } };
function drive(c, build, cargo, waste) {
  const S = M.create(c.build, { build, cargo, kind: c.cargo }), L = S.L; let t = 0, wt = 0, minF = 1e9, cans = 0;
  while (t < 300 && S.state === 'play') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + 40), ty = z ? z.t : '', d = z && ty === 'mud' ? z.d : 0, up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30, wz = S.waterAt(x + 60), b = S.cfg.b;
    const inp = waste ? { gas: true, awd: !!b.awd, lock: !!b.lock, low: !!b.low && (up || !!z), winch: !!S.rope || !!S.target }
      : { gas: true, awd: b.awd && (!!z || up || !!wz || S.stuckT > 0.4), lock: b.lock && (d >= 46 || ty === 'peat' || S.stuckT > 1), low: b.low && (d >= 56 || ty === 'peat' || up || (ty !== 'sand' && S.stuckT > 0.8) || !!(wz && wz.depth > 55)), winch: (d >= 72 || ty === 'peat') && (!!S.rope || (S.stuckT > 1.5 && !!S.target)) };
    S.step(inp); t += 1 / 120; if (S.rope) wt += 1 / 120; minF = Math.min(minF, S.fuel);
    for (const e of S.events) if (e.e === 'can') cans++; S.events.length = 0;
    if (S.stuckT > 8) break;
  }
  const end = S.state === 'win' ? 'доехал' : S.state === 'dead' ? '☠' + S.why + '@' + Math.round(S.truck.x / 54) + 'м' : 'встал@' + Math.round(S.truck.x / 54) + 'м';
  return `${end.padEnd(13)} ${String(Math.round(t)).padStart(3)}с  сжёг ${String(Math.round(S.used)).padStart(3)} л  осталось ${String(Math.round(100 * S.fuel / S.cfg.tank)).padStart(3)}%  мин ${String(Math.round(100 * minF / S.cfg.tank)).padStart(3)}%  канистр ${cans}  лебёдка ${wt.toFixed(1)}с`;
}
for (const c of M.CONTRACTS) {
  const bd = BASE[c.id], cap = M.capOf(M.spec(bd), c.cargo), n = Math.ceil(cap / 2), len = Math.round(M.create(c.build).L.fin / 54);
  console.log(`${c.name[1]} — ${len} м, груз ${n} из ${cap}, бак ${M.spec(bd).tank} л`);
  console.log('   аккуратно:      ' + drive(c, bd, n, false));
  console.log('   всё включено:   ' + drive(c, bd, n, true));
  if (c.id === 'bog' || c.id === 'mill') console.log('   + большой бак:  ' + drive(c, Object.assign({}, bd, { tank: 1 }), n, false) + '  | всё включено: ' + drive(c, Object.assign({}, bd, { tank: 1 }), n, true));
}
// лебёдка: жжёт топливо под нагрузкой и не работает с пустым баком
{
  const c = M.CONTRACTS.find((q) => q.id === 'bog'), mk = (fuel) => { const S = M.create(c.build, { build: BASE.bog, cargo: 0, manual: true }), z = S.L.mud.find((q) => q.t === 'peat'); S.cp = { x: z.x0 + 150, y: S.groundAt(z.x0 + 150), fuel }; S.respawn(); S.fuel = fuel; return S; };
  let S = mk(40), t = 0, wt = 0; const u0 = S.used; while (t < 6) { S.step({ winch: true }); t += 1 / 120; if (S.pullOn) wt += 1 / 120; }
  console.log(`лебёдка без газа, 6 с: тянула ${wt.toFixed(1)} с, сожгла ${(S.used - u0).toFixed(1)} л (из них холостой ход ${(0.1 * t).toFixed(1)} л)`);
  S = mk(0); t = 0; let hooked = false; while (t < 4) { S.step({ winch: true }); t += 1 / 120; if (S.rope) hooked = true; }
  console.log('лебёдка с пустым баком: ' + (hooked ? 'ЗАЦЕПИЛАСЬ — ПЛОХО' : 'не работает, как и задумано'));
}
