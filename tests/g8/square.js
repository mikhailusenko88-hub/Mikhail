// Hook Truck в квадратном окне (проверка площадки «Scale test»): меню, гараж, заезд, победа — ничего не налезает
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg'), OUT = process.argv[2] || '/tmp/sq';
const SIZES = (process.env.SQ || '714x714,477x477,600x600,360x360,900x900').split(',').map((s) => s.split('x').map(Number));
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const [w, h] of SIZES) {
    for (const lang of ['ru', 'en']) {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'en-US' });
      await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
      const p = await ctx.newPage();
      await p.addInitScript((lang) => { window.__pgLang = lang; localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [3, 2, 1], best: [], duo: false, tut: [1, 1], coins: 12345, ts: 1 })); }, lang);
      await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
      const tag = `${w}x${h}-${lang}`;
      await p.screenshot({ path: path.join(OUT, tag + '-1menu.png') });
      if (lang === 'ru') {
        await p.evaluate(() => window.__hook.garage()); await p.waitForTimeout(700); await p.screenshot({ path: path.join(OUT, tag + '-2garage.png') });
        await p.evaluate(() => window.__hook.start(false, 2)); await p.waitForTimeout(900); await p.screenshot({ path: path.join(OUT, tag + '-3play.png') });
        await p.evaluate(() => { const S = window.__hook.S; S.L.star.got = true; S.state = 'win'; S.wonT = 1; S.wonAt = 5.2; }); await p.waitForTimeout(1800); await p.screenshot({ path: path.join(OUT, tag + '-4win.png') });
      }
      await ctx.close();
    }
  }
  await b.close(); console.log('done');
})();
