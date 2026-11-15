// Решатель уровней Hook Truck: для каждого кольца ищет, когда цепляться и когда отпускать.
// Ширина «окна» отпускания — мера сложности (чем уже, тем сложнее). Проверяет звезду и считает время для третьей звезды.
globalThis.window = globalThis;
require('../../g7-hook/physics.js'); require('../../g7-hook/sim.js'); require('../../g7-hook/levels.js');
const H = globalThis.HookSim;

function play(li, params, upto, maxT = 70) {
  const S = H.create(li); const R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0); let idx = 0, okRing = -1, gT = 0, relAt = -1;
  while (S.t < maxT) {
    const T = S.truck; let a = R[idx]; let hook = false;
    if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
    if (S.state === 'play' && a) {
      const p = params[idx] || { att: 9999, rel: 150 };
      if (S.rope && S.ropeA === a) {
        hook = p.climb ? !(S.grounded && T.y < a.y + 300 && (T.x > a.x - 80 || S.rope.len <= 160)) : !(T.x > a.x + p.rel);
        if (!hook) { idx++; relAt = S.t; }
      } else hook = S.target === a && (p.climb || T.x > a.x - p.att);
    }
    // как живой игрок: в воздухе выравнивает нос газом/тормозом; на земле на «свечке» отпускает газ, на сильной — тормозит
    let gas = true, brake = false; const an = Math.atan2(Math.sin(T.a), Math.cos(T.a));
    if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; }
    else if (S.grounded && an < -0.55) { gas = false; brake = an < -0.85; }
    S.step({ gas, brake, hook, pull: !!(S.rope && a && a.climb && a.snap) }); // на треснутой стене тянем лебёдкой быстрее, как подсказывает игра
    for (const e of S.events) { if (e.e === 'dead') return { win: false, fail: idx, x: Math.round(T.x), t: S.t, why: e.why }; if (e.e === 'snap') idx++; }
    S.events.length = 0;
    // кольцо upto пройдено: зацепились за следующее или стоим на земле дальше кольца
    if (upto !== undefined && idx > upto) {
      const nxt = R[upto + 1];
      if (S.rope && nxt && S.ropeA === nxt) return { win: true, part: true, t: S.t };
      const an = Math.atan2(Math.sin(T.a), Math.cos(T.a));
      gT = S.grounded && !S.rope && Math.abs(an) < 0.4 && T.x > R[upto].x0 + 250 ? gT + 1 : 0;
      if (gT > 50) return { win: true, part: true, t: S.t };
    }
    if (S.state === 'win') return { win: true, t: S.t, star: S.L.star && S.L.star.got };
  }
  return { win: false, fail: idx, x: Math.round(S.truck.x), t: S.t, why: 'time' };
}

// кандидаты для кольца k (при уже выбранных предыдущих): все удачные (att, rel), лучшие — в середине длинного удачного куска
function cands(li, params, k, climb) {
  if (climb) { params[k] = { climb: 1 }; return play(li, params, k).win ? [{ p: { climb: 1 }, w: 'стена' }] : []; }
  const out = [];
  for (const att of [9999, 300, 150, 50]) {
    const ok = [];
    for (let rel = -200; rel <= 500; rel += 25) { params[k] = { att, rel }; ok.push([rel, play(li, params, k).win]); }
    let run = [];
    const flush = () => { run.forEach((rel, i) => out.push({ p: { att, rel }, score: Math.min(i, run.length - 1 - i), w: run.length * 25 })); run = []; };
    for (const [rel, w] of ok) { if (w) run.push(rel); else flush(); }
    flush();
  }
  out.sort((a, b) => b.score - a.score || b.w - a.w);
  return out;
}
function solve(li) {
  const R = H.create(li).L.anchors.slice().sort((a, b) => a.x0 - b.x0);
  const params = [], windows = []; let budget = 40, deepest = 0;
  function dfs(k) {
    if (k === R.length) return play(li, params).win;
    const cs = cands(li, params, k, R[k].climb); deepest = Math.max(deepest, k);
    for (const c of cs.slice(0, 5)) {
      if (--budget < 0) return false;
      params[k] = c.p; windows[k] = c.w;
      if (dfs(k + 1)) return true;
    }
    params.length = k; return false;
  }
  const ok = dfs(0);
  if (!ok) return { ok: false, k: deepest, params, windows };
  const fin = play(li, params);
  let star = !!fin.star, starP = null;
  if (!star) for (let k = 0; k < R.length && !star; k++) if (!params[k].climb) for (let rel = -200; rel <= 500 && !star; rel += 25) for (const att of [9999, 300, 150]) { const p = params.map((q) => Object.assign({}, q)); p[k] = { att, rel }; const r = play(li, p); if (r.win && r.star) { star = true; starP = k + ':' + att + '/' + rel; break; } }
  return { ok: true, t: fin.t, star, starP, windows, params };
}

if (require.main === module) {
  const only = process.argv[2] ? process.argv[2].split(',').map(Number) : H.levels.map((_, i) => i);
  for (const li of only) {
    const t0 = Date.now(); const r = solve(li);
    console.log(`${li + 1}. ${H.levels[li].name[1].padEnd(14)} ${r.ok ? 'ПРОХОДИТСЯ' : 'НЕТ'} время ${r.t ? r.t.toFixed(1) : '-'} звезда ${r.star ? 'да' + (r.starP ? ' (' + r.starP + ')' : '') : 'НЕТ'} окна ${r.windows.join(' ')}  [${Math.round((Date.now() - t0) / 1000)}с]`);
    if (!r.ok) console.log('   застрял на кольце', r.k, JSON.stringify(r.params));
  }
}
module.exports = { play, solve };
