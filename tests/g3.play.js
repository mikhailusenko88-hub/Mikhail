const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const errs = []; page.on('console', m => { if (m.type() === 'error' && !m.text().includes('404')) errs.push(m.text()); }); page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g3-cars/index.html'); await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/g3_home.png' });
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale }));
  const V = (x, y) => [x * info.s, y * info.s];
  let [px, py] = V(info.W / 2, info.H * 0.78 + 75); await page.mouse.click(px, py); await page.waitForTimeout(800);
  await page.screenshot({ path: 'shots/g3_start.png' });
  const st = () => page.evaluate(() => { const d = __dbg(); const c = d.car; return { state: Core.state, x: Math.round(c.x), y: Math.round(c.y), a: +c.a.toFixed(2), vx: Math.round(c.vx), fuel: Math.round(c.fuel), crashed: c.crashed, len: d.T.len, wc: c.wheels.map(w=>w.contact) }; });
  console.log('t0', JSON.stringify(await st()));
  // простой автопилот: газ, но отпускать в воздухе при сильном наклоне назад
  const t0 = Date.now(); let shot = 0;
  while (Date.now() - t0 < 40000) {
    const s = await st(); if (s.state !== 'play') { console.log('END', JSON.stringify(s)); break; }
    const air = !s.wc[0] && !s.wc[1];
    const want = air ? s.a > -0.05 : true;
    await page.evaluate((v) => __setGas(v), want);
    await page.waitForTimeout(60);
    if (Date.now() - t0 > 4000 * (shot + 1) && shot < 3) { shot++; await page.screenshot({ path: `shots/g3_run${shot}.png` }); console.log('t', shot, JSON.stringify(s)); }
  }
  await page.waitForTimeout(1500); await page.screenshot({ path: 'shots/g3_end.png' });
  console.log('final', JSON.stringify(await st()));
  console.log('ERRORS:', errs.join('\n'));
  await browser.close();
})();
