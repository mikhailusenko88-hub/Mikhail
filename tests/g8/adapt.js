// Hook Truck: подстройка разрешения под скорость. А) медленный телефон: разрешение объёмной картинки должно снизиться и остаться; Б) кадры режет сам браузер (как в энергосбережении): пробует, не помогло — возвращает чёткость и больше не трогает.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const [name, w, h, cap] of [['A медленный', 240, 400, 0], ['Б потолок кадров', 150, 220, 45]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, locale: 'en-US' });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
    const p = await ctx.newPage();
    await p.addInitScript((cap) => {
      localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [1, 1, 1, 1, 1], best: [], duo: false, tut: [1, 1], coins: 0, ts: 1 }));
      if (cap) window.requestAnimationFrame = (f) => setTimeout(() => f(performance.now()), cap); // кадр не чаще, чем раз в cap мс — как бы быстро ни рисовалось
    }, cap);
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
    await p.evaluate(() => { const h = window.__hook; h.dbg.adapt = true; h.setCtl('auto'); h.start(false, 4); }); await p.mouse.click(w / 2, h / 2);
    const log = [];
    for (let i = 0; i < 16; i++) { await p.waitForTimeout(2500); const s = await p.evaluate(() => ({ gq: window.__hook.gq, lock: window.__hook.pf.lock, test: window.__hook.pf.test, base: +(window.__hook.pf.base * 1000).toFixed(0) })); log.push(s.gq + (s.test ? '?' : '') + (s.lock ? '!' : '')); if (s.lock) break; }
    console.log(name, '— ступени качества:', log.join(' → '));
    await ctx.close();
  }
  await b.close();
})();
