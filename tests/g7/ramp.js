// Лесенка сложности: для каждого уровня — решается ли, и какая доля случайных вариантов (момент захвата и отпускания ±175) проходит
globalThis.window = globalThis;
const { play, solve } = require('./solve.js');
const H = globalThis.HookSim;
const ONLY = process.argv[2] ? process.argv[2].split(',').map(Number) : H.levels.map((_, i) => i);
for (const li of ONLY) {
  const t0 = Date.now(), sol = solve(li);
  if (!sol.ok) { console.log(`${li + 1}. ${H.levels[li].name[1].padEnd(15)} НЕ РЕШЁН (застрял на кольце ${sol.k + 1})`); continue; }
  let seed = 7 + li; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  let w = 0, N = 100; const F = {};
  for (let n = 0; n < N; n++) {
    const p = sol.params.map((q) => q.climb ? q : { att: [9999, 300, 150][Math.floor(rnd() * 3)], rel: q.rel + Math.round((rnd() * 2 - 1) * 175 / 25) * 25 });
    const r = play(li, p, undefined, 45); if (r.win) w++; else { const k = `к${r.fail + 1}:${r.why}`; F[k] = (F[k] || 0) + 1; }
  }
  const bad = Object.entries(F).filter(([k]) => !k.endsWith('time')).reduce((q, [, v]) => q + v, 0);
  console.log(`${li + 1}. ${H.levels[li].name[1].padEnd(15)} ЛЁГКОСТЬ ${String(Math.round((100 * w) / Math.max(1, w + bad))).padStart(3)}%  (прошло ${w}, упало ${bad})  время ${sol.t.toFixed(1)}  окна ${JSON.stringify(sol.windows)}  провалы ${JSON.stringify(F)}  (${((Date.now() - t0) / 1000).toFixed(0)} с)`);
}
