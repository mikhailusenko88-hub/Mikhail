const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.log('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g4-runner/index.html'); await page.waitForTimeout(1500);
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale }));
  await page.evaluate(() => Core.startLevel());
  await page.waitForTimeout(300);
  await page.mouse.click(195, 700);
  for (let i = 0; i < 40; i++) {
    const st = await page.evaluate(() => { const d = __dbg(); return { st: Core.state, t: +Core.t.toFixed(1), z: +d.run.z.toFixed(1), num: d.run.num, stopZ: d.run.stopZ, endT: +(+d.endT).toFixed(2), kind: d.endKind, ph: d.phase, x: d.run.x }; });
    console.log(JSON.stringify(st)); if (st.st !== 'play') break;
    await page.evaluate(() => { const r = __dbg().run; const g = r.objs.find(o => o.type === 'gate' && !o.done && o.z > r.z); if (g) __steer(g.L.f(r.num) >= g.R.f(r.num) ? -1.5 : 1.5); });
    await page.waitForTimeout(1500);
    if (i === 3) await page.screenshot({ path: 'shots/g4_dbg_run.png' });
    if (st.z > 99 && !globalThis.__s) { globalThis.__s = 1; await page.screenshot({ path: 'shots/g4_dbg_walls.png' }); }
  }
  await page.screenshot({ path: 'shots/g4_dbg.png' });
  await browser.close();
})();
