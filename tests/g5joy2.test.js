const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true });
  page.on('pageerror', e => console.log('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g5-io/index.html'); await page.waitForTimeout(1000);
  await page.evaluate(() => Core.startLevel()); await page.waitForTimeout(3600);
  const v = () => page.evaluate(() => { const p = __dbg().W.balls[0]; return { vx: Math.round(p.vx), vy: Math.round(p.vy) }; });
  const until = async (cond, label) => { const t0 = Date.now(); for (let i = 0; i < 40; i++) { const s = await v(); if (cond(s)) { console.log(label, Date.now() - t0, 'ms', JSON.stringify(s)); return; } await page.waitForTimeout(10); } console.log(label, 'НЕ УСПЕЛ', JSON.stringify(await v())); };
  await page.mouse.move(200, 600); await page.mouse.down();
  await page.mouse.move(230, 600, { steps: 3 }); await until(s => s.vx > 300, 'вправо за');
  await page.waitForTimeout(500); console.log('палец стоит, едет:', JSON.stringify(await v()));
  await page.mouse.move(218, 600, { steps: 2 }); await until(s => s.vx < -300, 'разворот влево (палец 12px) за');
  await page.mouse.move(218, 630, { steps: 2 }); await until(s => s.vy > 300, 'вниз за');
  await page.mouse.move(240, 610, { steps: 2 }); await until(s => s.vx > 200 && s.vy < 0, 'вправо-вверх за');
  await page.mouse.up(); await page.waitForTimeout(400); console.log('отпустил:', JSON.stringify(await v()));
  await page.screenshot({ path: 'shots/io_arrow.png' });
  await browser.close();
})();
