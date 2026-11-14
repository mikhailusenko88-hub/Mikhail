// Прогон машин тремя «игроками»: осторожный (в воздухе отпускает), трюкач (сальто), «держит всё время»
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  p.on('pageerror', (e) => console.log('PAGEERR', e.message));
  await p.goto('http://localhost:8765/g3-cars/index.html'); await p.waitForTimeout(900);
  for (const style of ['careful', 'stunt', 'hold']) {
    for (const n of [1, 2, 3, 5, 8]) {
      const res = [];
      for (let k = 0; k < 1; k++) {
        res.push(await p.evaluate(async ({ n, style }) => {
          const C = Core; C.save.level = n; C.save.extra.up = { eng: Math.min(5, n - 1 >> 1), tire: Math.min(5, n - 1 >> 1), tank: Math.min(5, n - 1 >> 1) }; C.save.extra.carRel = 1; C.save.extra.carFlip = 1;
          await C.startLevel(); C.state = 'play';
          window.__autoDrive = (car, airT, airRot) => {
            const touching = car.wheels.some((w) => w.contact);
            if (style === 'hold') return true;
            if (touching) return true;
            if (style === 'careful') return false;
            return Math.abs(airRot) < 5.0 && airT < 1.6; // трюкач: держит до почти полного сальто
          };
          let t = 0, crashes = 0;
          while (t < 140) {
            C.game.update(1 / 60); t += 1 / 60;
            if (C.state === 'fail') { crashes++; if (crashes > 3) break; C.state = 'play'; C.game.revive(); }
            if (C.state === 'win') break;
          }
          const d = __dbg(); window.__autoDrive = null;
          const r = { st: C.state, t: Math.round(t), place: d.place, stunt: d.stunt, crashes, x: Math.round(d.car.x / d.T.len * 100), log: d.landLog.slice(-40).join(',') }; d.landLog.length = 0;
          C.state = 'home'; return r;
        }, { n, style }));
      }
      const wins = res.filter((r) => r.st === 'win').length;
      console.log(style.padEnd(8), 'ур.', n, '| финиш', wins + '/1', '| места', res.map((r) => r.st === 'win' ? r.place : '-').join(' '), '| аварий', res.map((r) => r.crashes).join(' '), '| трюки', res.map((r) => r.stunt).join(' '), '| время', res.map((r) => r.t).join(' '), '| полёты', res[0].log);
    }
  }
  await b.close();
})();
