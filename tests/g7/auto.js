// Автопилот для Hook Truck: проверяем, что уровень проходится и насколько широкое «окно» у каждого крюка.
globalThis.window = globalThis;
require('../../g7-hook/physics.js'); require('../../g7-hook/sim.js');
const H = globalThis.HookSim;
// plan: для каждого кольца [за сколько px до кольца цепляться, через сколько px после кольца отпускать]
function run(plan, opt = {}) {
  const S = H.create(); const A = S.L.anchors; const maxT = opt.maxT || 90; let log = []; let trace = opt.trace;
  let idx = 0, deaths = 0, lastDeadX = 0;
  while (S.t < maxT && S.state !== 'win') {
    const T = S.truck; const a = A[idx]; const p = plan[idx] || [250, 150];
    let hook = false;
    if (S.state === 'play' && a) {
      if (S.rope && S.ropeA === a) {
        if (p === 'top') hook = !(S.grounded && T.y < a.y + 240 && T.x > a.x - 200);
        else hook = !(T.x > a.x + p[1]);
        if (!hook) idx++;
      } else hook = S.target === a && (p === 'top' ? true : T.x > a.x - p[0]);
    }
    // как живой игрок: на земле газ, в воздухе (без троса) выравниваем нос газом/тормозом
    let gas = true, brake = false;
    if (!S.grounded && !S.rope) { const an = Math.atan2(Math.sin(T.a), Math.cos(T.a)); gas = an > 0.15; brake = an < -0.15; }
    const inp = { gas, brake, hook, pull: false };
    S.step(inp);
    if (trace && Math.round(S.t * 120) % 12 === 0) console.log(S.t.toFixed(2), idx, Math.round(T.x), Math.round(T.y), S.rope ? Math.round(S.rope.len) : '-', Math.round(T.vx), Math.round(T.vy), T.a.toFixed(2), S.grounded ? 'G' : '', S.wallTouch ? 'W' : '');
    for (const e of S.events) { if (e.e === 'dead') { deaths++; lastDeadX = Math.round(S.truck.x); log.push(`dead(${e.why})@${lastDeadX} t=${S.t.toFixed(1)}`); } if (e.e === 'respawn') { idx = A.findIndex((q) => q.x > S.truck.x); } if (e.e === 'cp' || e.e === 'star' || e.e === 'win') log.push(e.e + '@' + Math.round(S.truck.x)); }
    S.events.length = 0;
    if (deaths > (opt.maxDeaths || 3)) break;
  }
  return { win: S.state === 'win', t: +S.t.toFixed(1), deaths, star: S.L.star.got, log };
}
module.exports = { run, H };
if (require.main === module) {
  const S0 = H.create(); console.log('anchors', S0.L.anchors.map((a) => [a.x, a.y]), 'fin', S0.L.fin, 'cps', S0.L.cps.map((c) => c.x));
  const r = run([[260, 200], 'top', [300, +process.argv[2] || 200], [300, +process.argv[3] || 200]], { trace: process.argv[4] === 't' });
  console.log(JSON.stringify(r));
}
