// Наибольший вес бочек, который сборка довозит до финиша на самых трудных заказах (только «доехал», потери не считаем). node trcal2.js base axles
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide;
const A = { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, lift: 1, tank: 1 }, base = +process.argv[2], axles = +process.argv[3];
function drive(c, build, cargo) {
  const S = M.create(c.build, { build, cargo, kind: 'barrel', over: true }), L = S.L; let t = 0, back = 0, hx = 0, hangs = 0;
  while (t < 200 && S.state === 'play') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + 300), up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30;
    let inp = { gas: true, awd: true, lock: true, low: up || !!z, winch: !!S.rope || !!S.target };
    if (S.hung && S.stuckT > 1 && !back && S.truck.a <= 0.06) { back = 1; hx = x; hangs++; }
    if (back === 1) { inp = { brake: true, awd: true }; if (x < hx - Math.min(900, 300 * hangs)) back = 2; } else if (back === 2) { inp = { gas: true, awd: true }; if (x > hx + 500 || (S.hung && S.stuckT > 1)) back = 0; }
    S.step(inp); t += 1 / 120; S.events.length = 0; if (S.stuckT > 8 || hangs > 4) break; }
  return S.state === 'win';
}
const CT = ['pit', 'wetclay', 'twofords'].map((id) => M.CONTRACTS.find((q) => q.id === id));
for (const trailer of [0, 1, 2]) { const row = [];
  for (const eng of [0, 2, 4, 6, 8]) { const bd = Object.assign({}, A, { base, axles, eng, trailer }), C = M.spec(bd), sp = M.spaceOf(C, 'barrel'); let best = sp;
    for (const c of CT) { let lo = 0, hi = best; if (drive(c, bd, hi)) continue; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (drive(c, bd, m)) lo = m; else hi = m; } best = lo; }
    row.push(`ф${eng}:${best}/${sp}`); }
  console.log(`база ${base} ${axles === 3 ? '6×6' : '4×4'} прицеп ${trailer}  ` + row.join('  ')); }
