// Где ставить звезду: гоняем много удачных вариантов прохождения, звезду — туда, куда долетает ~треть из них
globalThis.window = globalThis;
const { play, solve } = require('./solve.js');
const H = globalThis.HookSim;
function trace(li, params) {
  const pts = []; const S = H.create(li); const R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0); let idx = 0;
  while (S.t < 60) {
    const T = S.truck; let a = R[idx]; let hook = false;
    if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
    if (S.state === 'play' && a) { const p = params[idx];
      if (S.rope && S.ropeA === a) { hook = p.climb ? !(S.grounded && T.y < a.y + 300 && (T.x > a.x - 80 || S.rope.len <= 160)) : !(T.x > a.x + p.rel); if (!hook) idx++; }
      else hook = S.target === a && (p.climb || T.x > a.x - p.att); }
    let gas = true, brake = false; const an = Math.atan2(Math.sin(T.a), Math.cos(T.a));
    if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; } else if (S.grounded && an < -0.55) { gas = false; brake = an < -0.85; }
    S.step({ gas, brake, hook, pull: !!(S.rope && a && a.climb && a.snap) }); // на треснутой стене тянем лебёдкой быстрее, как подсказывает игра
    if (Math.round(S.t * 120) % 4 === 0) pts.push([T.x, T.y]);
    for (const e of S.events) { if (e.e === 'dead') return null; if (e.e === 'snap') idx++; } S.events.length = 0;
    if (S.state === 'win') return { pts, t: S.t, L: S.L };
  }
  return null;
}
let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const out = {};
const ONLY = process.argv[2] ? process.argv[2].split(',').map(Number) : H.levels.map((_, i) => i);
for (const li of ONLY) {
  const sol = solve(li); if (!sol.ok) { console.log(li + 1, 'не решён'); continue; }
  const wins = []; let best = Infinity, L0 = null;
  for (let n = 0; n < 160; n++) {
    const p = sol.params.map((q) => q.climb ? q : { att: [9999, 300, 150][Math.floor(rnd() * 3)], rel: q.rel + Math.round((rnd() * 2 - 1) * 175 / 25) * 25 });
    const r = trace(li, p); if (r) { wins.push(r.pts); best = Math.min(best, r.t); L0 = r.L; }
  }
  const base = trace(li, sol.params); if (base) { wins.push(base.pts); best = Math.min(best, base.t); L0 = base.L; }
  // кандидаты: над ямами, выше дороги
  const pits = L0.pits; let cand = [];
  for (const z of pits) for (let x = z.x0 + 60; x < z.x1 + 200; x += 40) for (let h = 220; h <= 760; h += 40) {
    const y = z.y - h; const k = wins.filter((pts) => pts.some(([px, py]) => Math.hypot(px - x, py - y) < 115)).length / wins.length;
    cand.push({ x, y, h, k });
  }
  cand = cand.filter((c) => c.k >= 0.2 && c.k <= 0.45).sort((a, b) => Math.abs(a.k - 0.3) - Math.abs(b.k - 0.3) || b.h - a.h);
  const c = cand[0];
  out[li] = c ? [Math.round(c.x), Math.round(c.y), +c.k.toFixed(2)] : null;
  console.log(`${li + 1}. ${H.levels[li].name[1].padEnd(14)} вариантов ${wins.length}/161, лучшее время ${best.toFixed(1)} → звезда ${c ? `(${c.x}, ${c.y}) берут ${Math.round(c.k * 100)}%` : 'НЕ НАШЁЛ'}`);
  out['t' + li] = +best.toFixed(1);
}
const f = '/tmp/stars.json'; let prev = {}; try { prev = JSON.parse(require('fs').readFileSync(f, 'utf8')); } catch (e) {} require('fs').writeFileSync(f, JSON.stringify(Object.assign(prev, out)));
