// Полигон: «умный» водитель (режимы по участку, в болоте — лебёдка) на разных сборках. Что проходит, где встаёт, сколько топлива.
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js');
const M = global.MudSide;
const BUILDS = { 'обычный': {}, 'лифт1+шноркель': { lift: 1, snorkel: 1 }, 'лифт1+шноркель+подкачка': { lift: 1, snorkel: 1, ctis: 1 }, 'лифт1+шноркель+спущенные': { lift: 1, snorkel: 1, press: 0 }, 'грязевые+лифт1+шноркель': { tires: 2, lift: 1, snorkel: 1 }, 'колёса1+грязевые+шноркель+мотор1': { wheel: 1, tires: 2, snorkel: 1, eng: 2 }, '6×6+шноркель': { axles: 3, snorkel: 1 }, 'всё': { base: 1, lift: 2, wheel: 2, axles: 3, tires: 2, eng: 4, snorkel: 1, tank: 1 } };
function drive(build, noRespawn) {
  const S = M.create(0, { build }), L = S.L, log = []; let t = 0, lastCp = 0;
  while (t < 400 && S.state !== 'win') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + 40), ty = z ? z.t : '', d = z && ty === 'mud' ? z.d : 0, up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30, wz = S.waterAt(x + 60);
    const inp = { gas: true, awd: !!z || up || !!wz || S.stuckT > 0.4, lock: d >= 46 || ty === 'peat' || S.stuckT > 1, low: d >= 56 || ty === 'peat' || up || (ty !== 'sand' && S.stuckT > 0.8) || (wz && wz.depth > 55), winch: (d >= 72 || ty === 'peat') && (!!S.rope || (S.stuckT > 1.5 && !!S.target)), soft: ty === 'sand' || ty === 'peat' };
    if (S.hung && S.stuckT > 1) { inp.gas = false; inp.brake = true; }
    S.step(inp); t += 1 / 120;
    for (const e of S.events) { if (e.e === 'dead') log.push(`☠ ${e.why}@${Math.round(x)}`); if (e.e === 'cp') lastCp = S.cp.x; }
    S.events.length = 0;
    if (S.state === 'play' && S.stuckT > 9) { log.push(`встал@${Math.round(x)}${S.hung ? '(брюхо)' : ''}`); if (noRespawn) break; const nx = L.cps.find((c) => c.x > x + 50); if (!nx) break; S.cp = { x: nx.x, y: nx.y, fuel: S.fuel }; S.respawn(); S.stuckT = 0; } // застрял — переставляем за препятствие, чтобы увидеть остальное
    if (log.length > 14) break;
  }
  return `${S.state === 'win' ? 'ФИНИШ' : 'нет'} за ${t.toFixed(0)} с, топливо ${Math.round(100 * S.fuel / S.cfg.tank)}%, возвратов ${S.rescues} | ${log.join(', ')}`;
}
const L0 = M.create(0).L; console.log('длина полигона', Math.round(L0.fin / 54), 'м; отметок', L0.cps.length);
for (const n in BUILDS) if (!process.argv[2] || n.includes(process.argv[2])) console.log(n.padEnd(34), drive(BUILDS[n]));
