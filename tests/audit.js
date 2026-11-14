// Снимки всех игр в 3 пропорциях: телефон, широкий (16:9), квадрат. Главный экран + 2 с после старта.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const games = ['g1-draw', 'g2-descent', 'g3-cars', 'g4-runner', 'g5-io'];
const sizes = { phone: [390, 844], wide: [1280, 720], square: [800, 800] };
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const g of games) for (const [name, [w, h]] of Object.entries(sizes)) {
    const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    const errs = []; page.on('pageerror', e => errs.push(e.message));
    await page.goto(`http://localhost:8765/${g}/index.html`); await page.waitForTimeout(1500);
    await page.screenshot({ path: `shots/audit_${g}_${name}_home.png` });
    await page.evaluate(() => { if (Core.state === 'home') Core.startLevel(); });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `shots/audit_${g}_${name}_play.png` });
    if (errs.length) console.log(g, name, 'ERR', errs.join(' | '));
    await page.close();
  }
  await browser.close();
  console.log('done');
})();
