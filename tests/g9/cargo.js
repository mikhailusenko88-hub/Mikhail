// где и когда теряется груз: ровная дорога, ухабы, гребень, подъёмы — на полном газу и осторожно
global.window = global; require('../../g8-hook3d/physics.js'); require('../../g9-mud/mud2d.js'); const M = global.MudSide, P = global.TPhys || global.P;
const R = (f) => () => f(M.Route().start(-300, 600).flat(900)).flat(1500).fin(0).end().S;
const cases = { 'ровно': R((b) => b.flat(1500)), 'ухабы 60×12': R((b) => b.bump(60, 12).flat(260).bump(60, 12)), 'гребёнка 70×15': R((b) => b.bump(70, 15).flat(190).bump(70, 15).flat(190).bump(70, 15)), 'гребень 240×55': R((b) => b.crest(240, 55)), 'гребень 300×80': R((b) => b.crest(300, 80)), 'подъём 1400×620': R((b) => b.slope(1400, 620)), 'подъём 1000×560': R((b) => b.slope(1000, 560)), 'спуск 700×300': R((b) => b.slope(700, -300)) };
const kinds = process.argv[2] ? process.argv[2].split(',') : ['log', 'barrel', 'melon'];
const BASES = { 'обычная база': { awd: 1, low: 1, lock: 1, eng: 1 }, 'оч. длинная база': { awd: 1, low: 1, lock: 1, eng: 1, base: 2 } };
for (const bn in BASES) for (const kind of kinds) for (const [mn, slow] of [['газ в пол', 0], ['осторожно', 1]]) {
  const row = [];
  for (const cn in cases) { const S = M.create(cases[cn], { build: BASES[bn], cargo: 13, kind }); let t = 0, first = '';
    while (t < 45 && S.state === 'play') { S.fuel = 50; const up = S.groundAt(S.truck.x + 160) < S.groundAt(S.truck.x - 40) - 30, v = S.truck.vx; S.step({ gas: !slow || v < 170, brake: slow && v > 260, awd: true, low: up }); t += 1 / 120; for (const e of S.events) if (e.e === 'log' && !first) first = '@' + Math.round((S.truck.x - 600) / 54) + 'м'; S.events.length = 0; }
    row.push(`${cn}: ${S.state === 'win' ? '' : 'НЕ ДОЕХАЛ '}${S.cargo}/${S.cargo0}${first}`); }
  console.log((bn + ', ' + kind + ', ' + mn).padEnd(40), row.join(' | '));
}
