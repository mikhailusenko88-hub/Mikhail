const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  p.on('pageerror', (e) => console.log('PAGEERR', e.message));
  await p.goto('http://localhost:8765/g3-cars/index.html'); await p.waitForTimeout(900);
  for (const style of ['careful', 'hold']) for (const n of [1, 2, 3, 4, 5, 6, 8]) {
    const r = await p.evaluate(async ({ n, style }) => {
      const C = Core; C.save.level = n; C.save.extra.up = { eng: Math.min(5, n - 1 >> 1), tire: Math.min(5, n - 1 >> 1), tank: Math.min(5, n - 1 >> 1) }; C.save.extra.carRel = 1; C.save.extra.carFlip = 1;
      await C.startLevel(); C.state = 'play';
      window.__autoDrive = (car, airT, airRot) => { if (style === 'hold') return true; return car.wheels.some((w) => w.contact); };
      let t = 0; const why = [];
      while (t < 150) { C.game.update(1 / 60); t += 1 / 60; if (C.state === 'fail') { why.push(__dbg().car.why || 'other'); if (why.length > 3) break; C.state = 'play'; C.game.revive(); } if (C.state === 'win') break; }
      const d = __dbg(); window.__autoDrive = null; const res = { st: C.state, t: Math.round(t), place: d.place, rivals: d.rivals.map((q) => q.finishT >= 0 ? Math.round(q.finishT) : Math.round(q.x / d.T.len * 100) + '%').join('/'), why, stunt: d.stunt };
      C.state = 'home'; return res;
    }, { n, style });
    console.log(style.padEnd(8), 'ур.', n, r.st, 't=' + r.t, 'место', r.place, 'соперники', r.rivals, 'трюки', r.stunt, 'аварии:', r.why.join(' | '));
  }
  await b.close();
})();
