// Грязь, вид сбоку: проверка, что кнопки значат то, что написано. Таблица «участок × режим привода»: проехал или застрял.
global.window = global;
require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js');
const M = global.MudSide;
const MODES = { 'задний': {}, 'задний+блок': { lock: 1 }, 'задний+пониж': { low: 1 }, 'полный': { awd: 1 }, 'полный+блок': { awd: 1, lock: 1 }, 'полный+пониж': { awd: 1, low: 1 }, 'всё': { awd: 1, lock: 1, low: 1 } };
function run(build, mode, sec = 45, goalX) {
  const S = M.create(build), inp = Object.assign({ gas: true }, mode); let t = 0;
  while (t < sec && S.state === 'play' && S.truck.x < goalX) { S.step(inp); t += 1 / 120; }
  return { ok: S.truck.x >= goalX, x: Math.round(S.truck.x), t: +t.toFixed(1), fuel: Math.round(S.fuel), st: S.state, why: S.why };
}
const zone = (o, len = 1700) => () => M.Route().start(-300, 600).flat(900).mud(len, o).flat(1500).fin(0).end().S;
const hill = (len, up) => () => M.Route().start(-300, 600).flat(900).slope(len, up).flat(1500).fin(0).end().S;
const ZN = M.ZONES;
const Z = { 'мелкая грязь': [zone(ZN.shallow, 900), 1900], 'средняя грязь': [zone(ZN.medium), 2700], 'вязкая грязь': [zone(ZN.sticky), 2700], 'болото': [zone(ZN.swamp, 2200), 3200], 'длинный подъём': [hill(1700, 520), 2500], 'крутой подъём': [hill(1200, 620), 2000] };
if (!process.argv[2]) {
  for (const zn in Z) { const row = []; for (const mn in MODES) { const r = run(Z[zn][0], MODES[mn], 45, Z[zn][1]); row.push(mn + ':' + (r.ok ? 'да(' + r.t + 'с)' : 'нет@' + r.x)); } console.log(zn.padEnd(16), row.join('  ')); }
}
// весь рейс: «умный» водитель включает нужное по участкам; «всё включено» — с самого старта
function trip(smart) {
  const S = M.create(0), L = S.L; let t = 0; const log = [];
  while (t < 240 && S.state !== 'win') {
    const x = S.truck.x, z = L.mud.find((q) => x > q.x0 - 150 && x < q.x1 + 60), deep = z && z.d > 60, stk = z && z.d > 50, mid = z && z.d > 40;
    const up = S.groundAt(x + 160) < S.groundAt(x - 40) - 25, steep = S.groundAt(x + 160) < S.groundAt(x - 40) - 70;
    const inp = smart ? { gas: true, awd: !!(mid || up), lock: !!stk, low: !!(deep || steep), winch: !!(deep && S.stuckT > 1.2) || (!!S.rope && S.stuckT < 0.1 && S.truck.vx < 60) } : { gas: true, awd: true, lock: true, low: true };
    const st0 = S.state; S.step(inp); t += 1 / 120;
    if (S.state !== st0) log.push(S.state + (S.why ? ':' + S.why : '') + '@' + Math.round(S.truck.x) + ' t=' + t.toFixed(0));
  }
  return { win: S.state === 'win', t: +t.toFixed(1), fuel: Math.round(S.fuel), rescues: S.rescues, log: log.join(' | ') };
}
console.log('умный рейс:', JSON.stringify(trip(true)));
console.log('всё включено:', JSON.stringify(trip(false)));

// лебёдка: в болоте на одном полном приводе не проехать, а с лебёдкой за деревья — да
{
  const build = () => M.Route().start(-300, 600).flat(900).tree(600).tree(1200).tree(1800).tree(2400).mud(2200, ZN.swamp).flat(1500).fin(0).end().S;
  const S = M.create(build); let t = 0;
  while (t < 90 && S.truck.x < 3200 && S.state === 'play') { const w = !!S.rope || (!!S.target && S.truck.x > 800 && S.truck.vx < 80); S.step({ gas: !w, awd: true, winch: w }); t += 1 / 120; }
  console.log('болото на лебёдке:', S.truck.x >= 3200 ? 'да' : 'нет', 'за', t.toFixed(1), 'с, x =', Math.round(S.truck.x), 'топливо', Math.round(S.fuel));
}
