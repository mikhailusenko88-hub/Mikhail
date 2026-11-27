// Запуск: node tests/g7/holdprobe.js <номер уровня с 0> <кольца через запятую> '[отпускание прочих колец, px]'. ✓ — долетел, · — отпустил и упал, x — упал на кольце (порвалось)
// как живой игрок: держит кольцо k ровно hold секунд и отпускает; остальные кольца — удачно (по позиции). Что получится: долетел / упал / порвалось
globalThis.window = globalThis; const D = require('path').join(__dirname, '../../g8-hook3d/'); require(D + 'physics.js'); require(D + 'sim.js'); require(D + 'levels.js'); const H = globalThis.HookSim;
const li = +(process.argv[2] || 7), K = (process.argv[3] || '0,1,2').split(',').map(Number), BASE = JSON.parse(process.argv[4] || '[150,300,150]');
function run(k, hold) { const S = H.create(li); const R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0); let idx = 0, t0 = -1;
  while (S.t < 40) { const T = S.truck; let a = R[idx]; let hook = false;
    if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
    if (S.state === 'play' && a) { if (S.rope && S.ropeA === a) { if (t0 < 0) t0 = S.t; hook = idx === k ? S.t - t0 < hold : !(T.x > a.x + (BASE[idx] ?? 150)); if (!hook) { idx++; t0 = -1; } } else hook = S.target === a; }
    const an = Math.atan2(Math.sin(T.a), Math.cos(T.a)); let gas = true, brake = false; if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; }
    S.step({ gas, brake, hook, pull: false }); let r = null; for (const e of S.events) { if (e.e === 'dead') r = 'x'; if (e.e === 'snap' && idx === k) r = r || null; } S.events.length = 0; if (r) return idx > k ? '·' : 'x';
    if (idx > k + 1 || S.state === 'win') return '✓'; if (idx === k + 1 && S.grounded && T.x > R[k].x + 200) return '✓'; }
  return '?'; }
for (const k of K) { let s = ''; for (let h = 0.1; h <= 2.6; h += 0.1) s += run(k, h); console.log(`кольцо ${k + 1}: держать 0,1…2,6 с → ${s}`); }
