// Управление в «Шарики.io»: джойстик на поводке (палец), взмах-разворот, катится после отпускания, мышь-наведение на ПК.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g5-io/index.html'); await page.waitForTimeout(1000);
  await page.evaluate(() => { localStorage.clear(); Core.startLevel(); }); await page.waitForTimeout(1500);
  await page.screenshot({ path: 'shots/io_rules.png' });
  await page.waitForTimeout(4600);
  const cdp = await ctx.newCDPSession(page);
  const touch = (type, x, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] });
  const v = () => page.evaluate(() => { const p = __dbg().W.balls[0]; return { vx: Math.round(p.vx), vy: Math.round(p.vy), ph: __dbg().phase }; });
  const until = async (cond, label) => { const t0 = Date.now(); for (let i = 0; i < 40; i++) { const s = await v(); if (cond(s)) { console.log('OK ', label, Date.now() - t0, 'ms', JSON.stringify(s)); return true; } await page.waitForTimeout(10); } console.log('BAD', label, JSON.stringify(await v())); return false; };
  const drag = async (x0, y0, x1, y1, n) => { for (let i = 1; i <= n; i++) await touch('touchMove', x0 + ((x1 - x0) * i) / n, y0 + ((y1 - y0) * i) / n); };
  console.log('фаза', JSON.stringify(await v()));
  await touch('touchStart', 200, 600);
  await drag(200, 600, 214, 600, 3); await until((s) => s.vx > 300, 'вправо (палец 14px)');
  await page.waitForTimeout(400); const s1 = await v(); console.log(s1.vx > 300 ? 'OK ' : 'BAD', 'палец стоит — едет вправо', JSON.stringify(s1));
  // дрожь пальца ±2px не должна сбивать курс
  for (const [x, y] of [[215, 602], [213, 598], [216, 601], [214, 599]]) await touch('touchMove', x, y);
  await page.waitForTimeout(150); const s2 = await v(); console.log(s2.vx > 300 && Math.abs(s2.vy) < 120 ? 'OK ' : 'BAD', 'дрожь не сбивает', JSON.stringify(s2));
  // резкий взмах назад на 10px — разворот сразу
  await drag(214, 600, 204, 600, 2); await until((s) => s.vx < -300, 'взмах-разворот влево (10px)');
  // медленно вниз по 2px — поворот через поводок
  for (let i = 1; i <= 16; i++) await touch('touchMove', 204, 600 + i * 2);
  await until((s) => s.vy > 300, 'медленно вниз (32px шагами по 2)');
  await touch('touchEnd'); await page.waitForTimeout(400); const s3 = await v(); console.log(s3.vy > 300 ? 'OK ' : 'BAD', 'отпустил — катится дальше', JSON.stringify(s3));
  // перехват пальца (тап) не меняет курс
  await touch('touchStart', 300, 400); await touch('touchEnd'); await page.waitForTimeout(150);
  const s4 = await v(); console.log(s4.vy > 300 ? 'OK ' : 'BAD', 'тап не сбивает курс', JSON.stringify(s4));
  await touch('touchStart', 200, 600); await drag(200, 600, 230, 585, 4); await page.waitForTimeout(60);
  await page.screenshot({ path: 'shots/io_joy.png' }); await touch('touchEnd');
  await browser.close();

  // ПК: мышь без нажатия
  const b2 = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const p2 = await b2.newPage({ viewport: { width: 1280, height: 720 } });
  p2.on('pageerror', (e) => console.log('PAGEERR ' + e.message));
  await p2.goto('http://localhost:8765/g5-io/index.html'); await p2.waitForTimeout(1000);
  await p2.evaluate(() => { localStorage.setItem('x', '1'); Core.startLevel(); }); await p2.waitForTimeout(6200);
  const v2 = () => p2.evaluate(() => { const p = __dbg().W.balls[0]; return { vx: Math.round(p.vx), vy: Math.round(p.vy) }; });
  await p2.mouse.move(200, 360); await p2.waitForTimeout(200); let m = await v2(); console.log(m.vx < -300 ? 'OK ' : 'BAD', 'мышь слева — катится влево', JSON.stringify(m));
  await p2.mouse.move(640, 650); await p2.waitForTimeout(200); m = await v2(); console.log(m.vy > 300 ? 'OK ' : 'BAD', 'мышь снизу — катится вниз', JSON.stringify(m));
  await p2.waitForTimeout(1500); await p2.screenshot({ path: 'shots/io_pc.png' });
  await b2.close();
})();
