const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const errs = []; page.on('console', m => { if (m.type() === 'error' && !m.text().includes('404')) errs.push(m.text()); }); page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g5-factory/index.html'); await page.waitForTimeout(1500);
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale }));
  const V = (x, y) => [x * info.s, y * info.s];
  await page.screenshot({ path: 'shots/g5_start.png' });
  // тапаем по станку
  const sc = Math.min(1.2, Math.max(0.6, Math.min(info.W / 740, (info.H - 660) / 620))), top = 205 + Math.max(0, (info.H - 450 - 205 - 640 * sc) / 2), ox = info.W / 2 - 360 * sc, oy = top - 250 * sc;
  for (let i = 0; i < 25; i++) { const [x, y] = V(130 * sc + ox, 380 * sc + oy); await page.mouse.click(x, y); await page.waitForTimeout(80); }
  await page.waitForTimeout(6000);
  await page.screenshot({ path: 'shots/g5_run.png' });
  console.log(JSON.stringify(await page.evaluate(() => { const d = __dbg(); return { S: d.S, rate: d.rate, balls: d.balls, truck: { x: Math.round(d.truck.x), st: d.truck.state, load: d.truck.load }, coins: Core.save.coins }; })));
  // купить улучшение станка
  const [ux, uy] = V(info.W / 2 - (210 * 3 + 30) / 2 + 105, info.H - 290 + 110); await page.mouse.click(ux, uy); await page.waitForTimeout(500);
  // ×2 за рекламу
  const [bx, by] = V(info.W / 2, info.H - 430 + 55); await page.mouse.click(bx, by); await page.waitForTimeout(3000);
  await page.screenshot({ path: 'shots/g5_after.png' });
  console.log(JSON.stringify(await page.evaluate(() => { const d = __dbg(); return { S: d.S, rate: d.rate, boost: Math.round(d.boostT), coins: Core.save.coins, level: Core.save.level }; })));
  // офлайн-доход: сдвинуть seen и перезагрузить
  await page.evaluate(() => { Core.save.extra.f.seen = Date.now() / 1000 - 3600; localStorage.setItem('pg_factory', JSON.stringify(Core.save)); });
  await page.reload(); await page.waitForTimeout(1500); await page.screenshot({ path: 'shots/g5_offline.png' });
  console.log('popup', JSON.stringify(await page.evaluate(() => __dbg().popup)));
  console.log('ERRORS:', errs.join('\n'));
  await browser.close();
})();
