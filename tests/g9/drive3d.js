// Грязь 3D: проверка физики в Node. Стоит ровно, разгоняется, поворачивает; таблица «участок × режим»; проезд карты по дороге и по колее.
require('../../g9-mud/mud3d.js');
const M = globalThis.MudSim, DT = M.DT;
const MODES = { 'задний': {}, 'задний+блок': { lock: 1 }, 'полный': { awd: 1 }, 'полный+блок': { awd: 1, lock: 1 }, 'полный+пониж': { awd: 1, low: 1 }, 'всё': { awd: 1, lock: 1, low: 1 } };
const up = (S) => { const q = S.q; return 1 - 2 * (q[0] * q[0] + q[2] * q[2]); };
function run(map, mode, sec, goalZ, inp0) {
  const S = M.create({ map }), inp = Object.assign({ drive: 1, steer: 0 }, mode, inp0); let t = 0;
  while (t < sec && S.state === 'play' && S.p[2] < goalZ) { S.step(inp); t += DT; }
  return { S, ok: S.p[2] >= goalZ, z: +S.p[2].toFixed(1), t: +t.toFixed(1) };
}
const only = process.argv[2];
if (!only || only === 'base') {
  let S = M.create({ map: M.testMap({}) }); for (let i = 0; i < 600; i++) S.step({});
  console.log('стоит 5 с: скорость', Math.hypot(...S.v).toFixed(3), 'высота', S.p[1].toFixed(3), 'вверх', up(S).toFixed(3));
  let r = run(M.testMap({}), {}, 12, 1e9); console.log('разгон 12 с: скорость', r.S.speed.toFixed(1), 'м/с, путь', r.z, 'м, вверх', up(r.S).toFixed(3));
  r = run(M.testMap({}), { low: 1 }, 8, 1e9); console.log('пониженная 8 с: скорость', r.S.speed.toFixed(1));
  S = M.create({ map: M.testMap({}) }); let t = 0, minX = 0, maxX = 0; while (t < 14) { S.step({ drive: S.speed < 4 ? 1 : 0.3, steer: 1 }); t += DT; minX = Math.min(minX, S.p[0]); maxX = Math.max(maxX, S.p[0]); }
  console.log('круг на 4 м/с: диаметр', (maxX - minX).toFixed(1), 'м, вверх', up(S).toFixed(3));
  S = M.create({ map: M.testMap({}) }); t = 0; while (t < 9) { S.step({ drive: 1, steer: t > 6 ? 1 : 0 }); t += DT; }
  console.log('резкий поворот на', S.speed.toFixed(1), 'м/с: вверх', up(S).toFixed(3), S.state);
}
if (!only || only === 'mud') {
  for (const m of [0.3, 0.42, 0.56, 0.7, 1.0]) { const map = M.testMap({ mud: (x, z) => (z > 25 && z < 75 ? m : 0) }), row = []; for (const mn in MODES) { const r = run(map, MODES[mn], 70, 80); row.push(mn + ':' + (r.ok ? 'да(' + r.t + 'с)' : 'нет@' + r.z)); } console.log(('грязь ' + m).padEnd(10), row.join('  ')); }
  for (const deg of [12, 20, 27]) { const k = Math.tan((deg * Math.PI) / 180), map = M.testMap({ h: (x, z) => k * Math.max(0, Math.min(40, z - 25)) }), row = []; for (const mn in MODES) { const r = run(map, MODES[mn], 40, 70); row.push(mn + ':' + (r.ok ? 'да(' + r.t + 'с)' : 'нет@' + r.z)); } console.log(('подъём ' + deg + '°').padEnd(10), row.join('  ')); }
}
// автопилот: едет по ломаной (смотрит на точку впереди)
function drivePath(path, mode, sec, smart) {
  const S = M.create({ seed: 7 }), map = S.map; let t = 0, seg = 1, log = [];
  while (t < sec && S.state === 'play') {
    while (seg < path.length - 1 && Math.hypot(path[seg][0] - S.p[0], path[seg][1] - S.p[2]) < 9) seg++;
    const tx = path[seg][0], tz = path[seg][1], yaw = S.yaw(), want = Math.atan2(tx - S.p[0], tz - S.p[2]); let d = want - yaw; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
    const m = S.mudNow, md = smart ? { awd: m > 0.12 || S.stuckT > 0.5, lock: m > 0.45, low: m > 0.25 || S.stuckT > 1 } : mode;
    const gd = Math.hypot(map.goal.x - S.p[0], map.goal.z - S.p[2]), wn = smart && (!!S.winch || (S.stuckT > 2 && !!S.target));
    S.step(Object.assign({ drive: gd < 11 ? 0 : wn ? 0 : Math.abs(d) > 0.5 && S.speed > 5 ? 0.3 : 1, hb: gd < 11, steer: Math.max(-1, Math.min(1, d * 2.2)), winch: wn }, md)); t += DT;
    if (Math.floor(t) !== Math.floor(t - DT) && Math.floor(t) % 20 === 0) log.push(Math.round(S.p[0]) + ',' + Math.round(S.p[2]) + ' v' + S.speed.toFixed(0) + ' m' + m.toFixed(2));
  }
  return { st: S.state, why: S.why, t: +t.toFixed(0), fuel: Math.round(S.fuel), at: [Math.round(S.p[0]), Math.round(S.p[2])], up: +up(S).toFixed(2), log: log.join(' | ') };
}
if (!only || only === 'map') {
  const S = M.create({ seed: 7 }), map = S.map;
  console.log('карта: деревьев', map.trees.length, 'из них сухих в болоте', map.trees.filter((t) => t.dead).length, 'высоты', Math.min(...map.H).toFixed(1), '…', Math.max(...map.H).toFixed(1));
  console.log('по дороге, задний привод:', JSON.stringify(drivePath(map.road, {}, 200)));
  console.log('по дороге, полный привод:', JSON.stringify(drivePath(map.road, { awd: 1 }, 200)));
  console.log('по дороге, умный:', JSON.stringify(drivePath(map.road, {}, 300, true)));
  console.log('по колее, задний привод:', JSON.stringify(drivePath(map.trail, {}, 200)));
  console.log('по колее, всё включено:', JSON.stringify(drivePath(map.trail, { awd: 1, lock: 1, low: 1 }, 300)));
  console.log('по колее, умный + лебёдка:', JSON.stringify(drivePath(map.trail, {}, 300, true)));
}
if (!only || only === 'winch') {
  // глубокая грязь (мягкость 1) с 15-го метра, дерево на 40-м: сам не проедет, лебёдкой — да
  const tree = { x: 0.6, z: 40, y: 0, r: 0.34, s: 1.1, dead: true }, map = M.testMap({ mud: (x, z) => (z > 15 ? 1 : 0), trees: [tree] });
  const S = M.create({ map }), all = { awd: 1, lock: 1, low: 1 }; let t = 0;
  while (t < 25) { S.step(Object.assign({ drive: 1, steer: 0 }, all)); t += DT; }
  const z0 = S.p[2]; console.log('в глубокой грязи встал на', z0.toFixed(1), 'м, цель лебёдки:', S.target ? 'есть, до неё ' + (tree.z - z0 - 2.3).toFixed(1) + ' м' : 'нет');
  let hooked = false, maxTilt = 1; while (t < 70) { S.step(Object.assign({ drive: 0, steer: 0, winch: true }, all)); t += DT; if (S.winch) hooked = true; maxTilt = Math.min(maxTilt, up(S)); if (hooked && !S.winch) break; }
  console.log('лебёдка: зацепилась', hooked, '— подтянула до', S.p[2].toFixed(1), 'м за', (t - 25).toFixed(0), 'с, сама отцепилась', hooked && !S.winch, ', наклон не меньше', maxTilt.toFixed(2), S.state);
}
if (!only || only === 'water') {
  const S = M.create({ seed: 7 }), map = S.map; S.place(290, 232, Math.atan2(300 - 290, 240 - 232)); let t = 0, ev = [];
  while (t < 20 && S.state === 'play') { S.step({ drive: 1, steer: 0 }); t += DT; }
  console.log('в ручей мимо брода:', S.state, S.why, 'через', t.toFixed(1), 'с, глубина там', (map.yW - map.h(S.p[0], S.p[2])).toFixed(1), 'м');
  S.rescue(); for (let i = 0; i < 240; i++) S.step({}); console.log('эвакуация: на дороге', Math.round(S.p[0]), Math.round(S.p[2]), 'состояние', S.state, 'вверх', up(S).toFixed(2), 'топливо', Math.round(S.fuel));
  // брод на дороге: проезжаем, не заливая мотор
  const S2 = M.create({ seed: 7 }); S2.place(338, 165, Math.atan2(352 - 335, 250 - 150)); t = 0; let deep = 0;
  while (t < 20 && S2.state === 'play' && S2.p[2] < 235) { S2.step({ drive: 1, steer: 0, awd: 1 }); t += DT; deep = Math.max(deep, S2.map.yW - S2.map.h(S2.p[0], S2.p[2])); }
  console.log('брод на дороге:', S2.state, 'доехал до', Math.round(S2.p[2]), 'самое глубокое', deep.toFixed(2), 'м');
}
