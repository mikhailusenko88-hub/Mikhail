const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const p = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'ru-RU' });
  p.on('pageerror', (e) => console.log('PAGEERR', e.message));
  await p.goto('http://localhost:8765/g3-cars/index.html'); await p.waitForTimeout(900);
  await p.evaluate(async () => { localStorage.clear(); Core.save.level = 3; Core.save.extra = {}; await Core.startLevel(); });
  await p.evaluate(() => { window.__autoDrive = (car, airT, airRot) => car.wheels.some((w) => w.contact) || (Math.abs(airRot) < 5.0 && airT < 1.6); });
  let got = { air: 0, hint: 0, pop: 0 }; const t0 = Date.now();
  while (Date.now() - t0 < 45000) {
    const d = await p.evaluate(() => { const d = __dbg(); return { air: d.airT, hint: d.hint, pops: d.stunt, st: Core.state, x: Math.round(d.car.x), rot: d.airRot }; }); if (d.hint === 'go' && !got.go) { got.go = 1; await p.screenshot({ path: 'tests/shots/car_go.png' }); console.log('отпусти', d.x); }
    if (d.hint && !got.hint) { got.hint = 1; await p.screenshot({ path: 'tests/shots/car_hint.png' }); console.log('подсказка', d.hint, d.x); }
    if (d.pops >= 10 && !got.pop) { got.pop = 1; await p.waitForTimeout(150); await p.screenshot({ path: 'tests/shots/car_pop.png' }); console.log('трюк', d.pops); }
    if (d.st !== 'play') { console.log('состояние', d.st); await p.waitForTimeout(400); await p.screenshot({ path: 'tests/shots/car_end.png' }); if (d.st === 'fail') { await p.evaluate(() => { Core.state = 'play'; Core.game.revive(); }); continue; } break; }
    await p.waitForTimeout(80);
  }
  await p.evaluate(() => { window.__autoDrive = null; });
  await b.close();
})();
