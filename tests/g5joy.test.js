const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.log('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g5-io/index.html'); await page.waitForTimeout(1000);
  await page.evaluate(() => Core.startLevel()); await page.waitForTimeout(3600); // отсчёт
  const v = () => page.evaluate(() => { const p = __dbg().W.balls[0]; return { vx: Math.round(p.vx), vy: Math.round(p.vy) }; });
  await page.mouse.move(195, 600); await page.mouse.down(); await page.mouse.move(240, 600, { steps: 3 });
  await page.waitForTimeout(400); console.log('right', JSON.stringify(await v()));
  const t0 = Date.now(); await page.mouse.move(150, 600, { steps: 2 });
  for (let i = 0; i < 20; i++) { const s = await v(); if (s.vx < -200) { console.log('turned left after', Date.now() - t0, 'ms', JSON.stringify(s)); break; } await page.waitForTimeout(20); }
  await page.mouse.move(150, 680, { steps: 2 }); await page.waitForTimeout(150); console.log('down-left', JSON.stringify(await v()));
  await page.mouse.up(); await browser.close();
})();
