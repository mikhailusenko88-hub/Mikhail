// быстрая сетка для настройки грязи: зона × режим × сборка; топливо не кончается
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js');
const M = global.MudSide, Z = M.ZONES;
const B = { 'обыч': {}, 'дорож': { tires: 0 }, 'грязев': { tires: 2 }, 'кол1': { wheel: 1 }, 'кол2': { wheel: 2 }, '6×6': { axles: 3 }, 'спущ': { press: 0 }, 'накач': { press: 2 }, 'кол1+спущ': { wheel: 1, press: 0 }, 'гряз+спущ': { tires: 2, press: 0 }, 'защита': { skid: 1 }, 'кол2+гряз+6×6': { wheel: 2, tires: 2, axles: 3 } };
const MO = { '2': {}, '4': { awd: 1 }, '4L': { awd: 1, low: 1 }, '4B': { awd: 1, lock: 1 }, '4LB': { awd: 1, low: 1, lock: 1 } };
const zones = (process.argv[2] || 'soft,medium,sticky,swamp,sand,clay,peat').split(','), len = +(process.argv[3] || 1500);
console.log(''.padEnd(13) + Object.keys(B).map((n) => n.padEnd(8)).join(''));
for (const zn of zones) for (const mn in MO) {
  let row = (zn + ' ' + mn).padEnd(13);
  for (const bn in B) {
    const S = M.create(() => M.Route().start(-300, 600).flat(900).mud(len, Z[zn]).flat(1200).fin(0).end().S, { build: B[bn] }), inp = Object.assign({ gas: true }, MO[mn]); let t = 0;
    while (t < 32 && S.state === 'play') { S.fuel = 50; S.step(inp); t += 1 / 120; }
    row += (S.state === 'win' ? '✓' + t.toFixed(0) : S.state === 'dead' ? '☠' + S.why[0] : '·' + Math.round((S.truck.x - 600) / len * 100) + '%').padEnd(8);
  }
  console.log(row);
}
