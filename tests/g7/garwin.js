// Экран победы с монетами и вид грузовика в заезде
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const DIR = path.resolve(__dirname, '../../' + (process.env.HOOK_DIR || 'g8-hook3d')), OUT = process.argv[2] || '/tmp/gar';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const [name, w, h, look] of [['phone', 390, 844, [1, 3, 2]], ['land', 844, 390, [2, 2, 5]], ['low', 640, 340, [0, 1, 3]], ['desk', 1280, 720, [1, 1, 4]]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: w < 900, isMobile: w < 900 });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.addInitScript((look) => { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [2, 1], best: [6, 9], duo: false, coins: 345, own: [0, 1, 2], ownW: [0, 1, 2, 3], ownC: [0, 1, 2, 3, 4, 5], truck: look[0], wheels: look[1], color: look[2], up: { eng: 1, winch: 0 } })); }, look);
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1000);
    await p.evaluate(() => window.__hook.start(false, 0)); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(1400); await p.keyboard.up('ArrowRight');
    await p.evaluate(() => { window.__hook.dbg.freeze = true; }); await p.waitForTimeout(1500); await p.screenshot({ path: path.join(OUT, name + '-play.png') });
    await p.evaluate(() => { const H = window.__hook, S = H.S; H.dbg.freeze = false; S.L.star.got = true; S.state = 'win'; S.wonT = 1; S.wonAt = 5.2; });
    await p.waitForTimeout(2600); await p.screenshot({ path: path.join(OUT, name + '-win.png') });
    console.log(name, errs.length ? errs : 'без ошибок', await p.evaluate(() => JSON.stringify(window.__hook.save())));
    await ctx.close();
  }
  await b.close();
})();
