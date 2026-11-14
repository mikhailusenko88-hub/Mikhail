const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  for (const [w, h, tag] of [[390, 844, 'phone'], [1280, 720, 'pc'], [800, 800, 'sq']]) {
    const p = await b.newPage({ viewport: { width: w, height: h }, locale: 'ru-RU' }); p.on('pageerror', (e) => console.log('PAGEERR', tag, e.message));
    await p.goto('http://localhost:8765/g3-cars/index.html'); await p.waitForTimeout(800);
    await p.evaluate(async () => { localStorage.clear(); Core.save.level = 3; await Core.startLevel(); window.__autoDrive = (car) => car.wheels.some((w2) => w2.contact); });
    await p.waitForTimeout(5200); await p.screenshot({ path: `tests/shots/car_${tag}.png` }); await p.close();
  }
  await b.close();
})();
