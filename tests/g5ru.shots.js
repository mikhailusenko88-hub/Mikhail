const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  for (const [w, h, tag] of [[390, 844, 'phone'], [1280, 720, 'pc'], [800, 800, 'sq']]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, locale: 'ru-RU', hasTouch: tag === 'phone' });
    const p = await ctx.newPage(); p.on('pageerror', (e) => console.log('PAGEERR', tag, e.message));
    await p.goto('http://localhost:8765/g5-io/index.html'); await p.waitForTimeout(900);
    await p.evaluate(() => { localStorage.clear(); Core.startLevel(); }); await p.waitForTimeout(1200);
    await p.screenshot({ path: `tests/shots/io_ru_rules_${tag}.png` });
    await p.waitForTimeout(4800);
    // шарик сам едет к ближайшей добыче — проверяем подсказки и что первая страна съедается
    await p.evaluate(() => { window.__auto = true; }); await p.waitForTimeout(1500);
    await p.screenshot({ path: `tests/shots/io_ru_coach_${tag}.png` });
    const r = await p.evaluate(() => new Promise((res) => { const t0 = performance.now(); const iv = setInterval(() => { if (Core.save.extra.ioEat || performance.now() - t0 > 20000) { clearInterval(iv); res({ ate: !!Core.save.extra.ioEat, s: Math.round((performance.now() - t0) / 1000) }); } }, 200); }));
    console.log(tag, 'первая съеденная страна:', JSON.stringify(r));
    await ctx.close();
  }
  await b.close();
})();
