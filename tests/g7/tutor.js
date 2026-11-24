// Обучение: для каждого кольца — когда держать (att: за сколько до кольца) и где отпускать (окно lo..hi правее кольца).
// Берём самый широкий удачный кусок; из одинаково широких — тот, где цепляться ближе к яме (понятнее новичку).
globalThis.window = globalThis;
const { play } = require('./solve.js');
const H = globalThis.HookSim;
const out = {};
for (const li of (process.argv[2] || '0,1').split(',').map(Number)) {
  const R = H.create(li).L.anchors.slice().sort((a, b) => a.x0 - b.x0), params = [], g = [];
  for (let k = 0; k < R.length; k++) {
    if (R[k].climb) { params[k] = { climb: 1 }; g.push({ climb: 1 }); continue; }
    // «держи у края ямы»: если кольцо висит над ямой, цепляться учим за 60 до края — так понятнее, чем уже в полёте
    const L = H.create(li).L, pit = L.pits.find((z) => R[k].x0 > z.x0 && R[k].x0 < z.x1), edge = pit && !(k && R[k - 1].x0 > pit.x0) ? Math.round(R[k].x0 - (pit.x0 - 60)) : 0;
    let best = null;
    for (const att of (edge ? [edge] : []).concat([9999, 450, 300, 150])) {
      let run = [];
      const flush = () => { if (run.length && (!best || (best.att !== edge || best.n < 6) && run.length > best.n)) best = { att, lo: run[0], hi: run[run.length - 1], n: run.length }; run = []; };
      for (let rel = -200; rel <= 600; rel += 25) { params[k] = { att, rel }; if (play(li, params, k).win) run.push(rel); else flush(); }
      flush();
    }
    params[k] = { att: best.att, rel: Math.round((best.lo + best.hi) / 50) * 25 }; g.push({ att: best.att, lo: best.lo, hi: best.hi });
  }
  const fin = play(li, params);
  out[li] = g; console.error(`уровень ${li + 1}: ${JSON.stringify(g)} → ${fin.win ? 'проходится за ' + fin.t.toFixed(1) + ' с' : 'НЕ ПРОХОДИТСЯ'}`);
}
console.log(JSON.stringify(out));
