// Сколько бочек увозит сборка: ищем наибольший груз, с которым проходит карьер и торфяник (водитель включает всё в грязи)
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide;
const NEED = { pit: { awd: 1, low: 1, lock: 1, tires: 1 }, bog: { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, tank: 1 }, mill: { awd: 1, low: 1, lock: 1, tires: 1, lift: 1 }, wetclay: { awd: 1, low: 1, lock: 1, tires: 1 }, twofords: { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1 } };
function drive(c, build, cargo) {
  const S = M.create(c.build, { build, cargo, kind: c.cargo }), L = S.L, b = S.cfg.b; let t = 0, back = 0, hx = 0, hangs = 0;
  while (t < 200 && S.state === 'play') {
    const x = S.truck.x, z = L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + 40), up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30;
    let inp = { gas: true, awd: !!b.awd, lock: !!b.lock, low: !!b.low && (up || !!z), winch: !!S.rope || !!S.target };
    if (S.hung && S.stuckT > 1 && !back && S.truck.a <= 0.06) { back = 1; hx = x; hangs++; }
    if (back === 1) { inp = { brake: true, awd: true }; if (x < hx - Math.min(900, 300 * hangs)) back = 2; } else if (back === 2) { inp = { gas: true, awd: true }; if (x > hx + 500 || (S.hung && S.stuckT > 1)) back = 0; }
    S.step(inp); t += 1 / 120; S.events.length = 0; if (S.stuckT > 8 || hangs > 4) break; }
  return S.state === 'win' ? Math.round(100 * S.fuel / S.cfg.tank) : -1;
}
const only = process.argv[2] ? process.argv[2].split(',') : ['pit', 'bog'];
for (const base of [0, 1, 2]) for (const axles of [2, 3]) { const row = [];
  for (const eng of [0, 1, 2, 3, 5]) { const res = [];
    for (const id of only) { const c = M.CONTRACTS.find((q) => q.id === id), bd = Object.assign({}, NEED[id], { base, axles, eng }), C = M.spec(bd), cap = M.capOf(C, c.cargo); let n = cap, f = -1;
      for (; n >= 1; n -= (n > 6 ? 2 : 1)) { f = drive(c, bd, n); if (f >= 0) break; }
      res.push(`${id} ${n}/${cap} (топл ${f}%)`); }
    row.push(`ф${eng}: ` + res.join(', ')); }
  console.log(`база ${base} ${axles === 3 ? '6×6' : '4×4'} масса ${M.spec({ base, axles }).m}  ` + row.join(' | ')); }
