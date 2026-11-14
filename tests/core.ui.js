const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'ru-RU' });
  const errs = []; page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g4-runner/index.html'); await page.waitForTimeout(1200);
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale, home: Core.homeCountry() }));
  console.log(JSON.stringify(info));
  const V = (x, y) => [x * info.s, y * info.s];
  let [x, y] = V(22 + 48, 120 + 48); await page.mouse.click(x, y); await page.waitForTimeout(500);
  await page.screenshot({ path: 'shots/core_shop.png' });
  // особый шарик: найти «gold» — прокрутить вниз
  await page.mouse.move(...V(360, 1000)); await page.mouse.down(); await page.mouse.move(...V(360, 300), { steps: 8 }); await page.mouse.up(); await page.waitForTimeout(400);
  await page.screenshot({ path: 'shots/core_shop2.png' });
  [x, y] = V(info.W - 15 - 40, 110 - 40 + 50); await page.mouse.click(x, y); await page.waitForTimeout(400); // закрыть
  [x, y] = V(22 + 48, 120 + 96 + 18 + 48); await page.mouse.click(x, y); await page.waitForTimeout(700);
  await page.screenshot({ path: 'shots/core_gift.png' });
  [x, y] = V(info.W / 2, info.H / 2 - 320 + 380 + 58); await page.mouse.click(x, y); await page.waitForTimeout(800);
  await page.screenshot({ path: 'shots/core_admock.png' });
  await page.waitForTimeout(2500);
  console.log('coins after gift x2:', await page.evaluate(() => Core.save.coins), 'streak', await page.evaluate(() => Core.save.day.streak));
  console.log('ERRORS:', errs.join('\n'));
  await browser.close();
})();
