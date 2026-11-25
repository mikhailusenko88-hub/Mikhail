// Грязь 2D, версия 2: таблица «препятствие × сборка грузовика». Каждая деталь должна где-то помогать и где-то мешать.
global.window = global;
require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js');
const M = global.MudSide, Z = M.ZONES;
const BUILDS = { 'обычный': {}, 'длинный': { base: 1 }, 'оч.длин': { base: 2 }, 'оч.длин+лифт1': { base: 2, lift: 1 }, 'оч.длин+лифт2': { base: 2, lift: 2 }, 'оч.длин+6×6': { base: 2, axles: 3 }, 'оч.длин+кол2': { base: 2, wheel: 2 }, 'лифт1': { lift: 1 }, 'лифт2': { lift: 2 }, 'колёса1': { wheel: 1 }, 'колёса2': { wheel: 2 }, '6×6': { axles: 3 }, 'длин+лифт1': { base: 1, lift: 1 }, 'длин+6×6': { base: 1, axles: 3 }, 'грязевые': { tires: 2 }, 'дорожные': { tires: 0 }, 'мотор2': { eng: 4 }, 'шноркель': { snorkel: 1 }, 'всё': { base: 1, lift: 2, wheel: 2, axles: 3, tires: 2, eng: 4, snorkel: 1, tank: 1 } };
const MODES = { '2': {}, '4': { awd: 1 }, '4L': { awd: 1, low: 1 }, '4LB': { awd: 1, low: 1, lock: 1 } };
function run(route, build, mode, sec, goalX) {
  const S = M.create(route, { build }), inp = Object.assign({ gas: true }, mode); let t = 0, maxTilt = 0;
  while (t < sec && S.state === 'play') { S.step(inp); t += 1 / 120; maxTilt = Math.max(maxTilt, Math.abs(S.truck.a)); }
  return { ok: S.state === 'win', x: Math.round(S.truck.x), t: +t.toFixed(1), fuel: +(100 * S.fuel / S.cfg.tank).toFixed(0), st: S.state, why: S.why, hung: S.hung, tilt: +(maxTilt * 57.3).toFixed(0) };
}
const R = (f) => () => f(M.Route().start(-300, 600).flat(900)).flat(1500).fin(0).end().S;
const OBST = {
  'гребень 240×40': [R((b) => b.crest(240, 40)), 2700], 'гребень 240×55': [R((b) => b.crest(240, 55)), 2700], 'гребень 300×80': [R((b) => b.crest(300, 80)), 2700],
  'канава 70×60': [R((b) => b.ditch(70, 60)), 0], 'канава 90×60': [R((b) => b.ditch(90, 60)), 0], 'канава 110×60': [R((b) => b.ditch(110, 60)), 0], 'канава 110×34': [R((b) => b.ditch(110, 34)), 0], 'канава 140×45': [R((b) => b.ditch(140, 45)), 0],
  'брод 0,6 м': [R((b) => b.ford(700, 32)), 0], 'брод 0,9 м': [R((b) => b.ford(800, 49)), 0], 'брод 1,1 м': [R((b) => b.ford(800, 60)), 0], 'брод 1,5 м': [R((b) => b.ford(900, 81)), 0], 'брод 0,9 м с илом': [R((b) => b.ford(900, 49, Z.silt)), 0],
  'грязь мелкая': [R((b) => b.mud(1500, Z.shallow)), 0], 'грязь средняя': [R((b) => b.mud(1500, Z.medium)), 4000], 'грязь липкая': [R((b) => b.mud(1500, Z.sticky)), 4000], 'болото': [R((b) => b.mud(1500, Z.swamp)), 4000],
  'уступ 12': [R((b) => b.step(12)), 0], 'уступ 16': [R((b) => b.step(16)), 0], 'уступ 20': [R((b) => b.step(20)), 0], 'уступ 24': [R((b) => b.step(24)), 0], 'уступ 30': [R((b) => b.step(30)), 0],
  'склон 1000×560': [R((b) => b.slope(1000, 560)), 0], 'склон 900×540': [R((b) => b.slope(900, 540)), 0], 'склон 1400×620': [R((b) => b.slope(1400, 620)), 0],
  'подъём 1200×620': [R((b) => b.slope(1200, 620)), 3600], 'подъём 800×520': [R((b) => b.slope(800, 520)), 3200], 'спуск 700×500': [R((b) => b.slope(700, -500)), 3100],
};
const only = process.argv[2], modes = (process.argv[3] || '4L').split(',');
console.log('сборки: ' + Object.keys(BUILDS).map((n) => { const c = M.spec(BUILDS[n]); return `${n} [клиренс ${(c.clear / 54).toFixed(2)} м, брод ${(c.ford / 54).toFixed(2)} м, масса ${c.m.toFixed(1)}, расход ${c.burn.toFixed(2)}]`; }).join('\n        '));
for (const on in OBST) {
  if (only && only !== 'all' && !on.includes(only)) continue;
  for (const mn of modes) {
    const row = [];
    for (const bn in BUILDS) { const r = run(OBST[on][0], BUILDS[bn], MODES[mn], 40, OBST[on][1]); row.push(bn + ':' + (r.ok ? r.t + 'с' : 'НЕТ@' + r.x + (r.st === 'dead' ? '(' + ({ water: 'вода', fuel: 'топл', flip: 'перев' })[r.why] + ')' : r.hung ? '(брюхо)' : '')) + (r.tilt > 50 ? ' крен' + r.tilt : '')); }
    console.log((on + ' [' + mn + ']').padEnd(24), row.join(' | '));
  }
}
