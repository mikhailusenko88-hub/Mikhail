// Hook Truck: кадры на каждом языке (телефон стоя + широкий экран) — подписи помещаются, ничего не налезает
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg'), OUT = process.argv[2] || '/tmp/langs';
const LANGS = (process.env.LANGS || 'es,pt,tr,de,fr,it,pl,id').split(',');
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const errs = [];
  for (const lang of LANGS) {
    for (const [name, w, h] of [['phone', 390, 844], ['desk', 900, 506]]) {
      const touch = name === 'phone';
      const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: touch, isMobile: touch });
      await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
      const p = await ctx.newPage(); p.on('pageerror', (e) => errs.push(lang + ' ' + name + ': ' + e.message));
      await p.addInitScript((lang) => { window.__pgLang = lang; localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [3, 2, 1], best: [], duo: false, coins: 640, ts: 1 })); }, lang);
      await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
      const shot = (k) => p.screenshot({ path: path.join(OUT, `${lang}-${name}-${k}.png`) });
      await shot('1menu');
      await p.evaluate(() => window.__hook.garage()); await p.waitForTimeout(600); await shot('2garage');
      await p.evaluate(() => window.__hook.click && 0); // вкладка «прокачка»
      const tab = await p.evaluate(() => { const q = window.__hook.btns.find((x) => x.id === 'g:tab:3'); return [q.x + q.w / 2, q.y + q.h / 2]; });
      if (touch) await p.touchscreen.tap(tab[0], tab[1]); else await p.mouse.click(tab[0], tab[1]); await p.waitForTimeout(400); await shot('3ups');
      // один палец: «нажми — поехали», потом «держи» у ямы
      await p.evaluate(() => { window.__hook.setCtl('auto'); window.__hook.start(false, 0); }); await p.waitForTimeout(700); await shot('4go');
      if (touch) await p.touchscreen.tap(w / 2, h / 2); else await p.mouse.click(w / 2, h / 2); await p.waitForTimeout(3200); await shot('5hold');
      // газ и крюк: кнопки и подсказка уровня 2; вдвоём — кнопка «тяни»
      await p.evaluate(() => { window.__hook.setCtl('manual'); window.__hook.start(false, 1); }); await p.waitForTimeout(900); await shot('6manual');
      await p.evaluate(() => { window.__hook.setCtl('duo'); window.__hook.start(true, 7); }); await p.waitForTimeout(900); await shot('7duo');
      await p.evaluate(() => { window.__hook.setCtl('manual'); window.__hook.start(false, 12); }); await p.waitForTimeout(500);
      await p.evaluate(() => { const S = window.__hook.S; S.L.star.got = true; S.state = 'win'; S.wonT = 1; S.wonAt = 5.2; }); await p.waitForTimeout(1900); await shot('8win');
      await ctx.close();
    }
  }
  await b.close(); console.log(errs.length ? errs.slice(0, 8) : 'без ошибок');
})();
