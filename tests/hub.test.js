const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'ru-RU' });
  const errs = []; page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/index.html'); await page.waitForTimeout(500);
  await page.screenshot({ path: 'shots/hub.png', fullPage: true });
  const cards = await page.$$('.card');
  for (let i = 0; i < cards.length; i++) {
    await cards[i].click(); await page.waitForTimeout(1800);
    const f = page.frames().find(fr => fr.url().includes('/g'));
    const st = f ? await f.evaluate(() => ({ state: Core.state, plat: Core.platform, home: Core.homeCountry() })) : null;
    console.log(i + 1, JSON.stringify(st));
    if (i === 2) await page.screenshot({ path: 'shots/hub_game3.png' });
    await page.click('#back'); await page.waitForTimeout(300);
  }
  console.log('ERRORS:', errs.join('\n'));
  await browser.close();
})();
