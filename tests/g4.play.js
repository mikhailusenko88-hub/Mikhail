const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const errs = []; page.on('console', m => { if (m.type() === 'error' && !m.text().includes('404')) errs.push(m.text()); }); page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g4-runner/index.html'); await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/g4_home.png' });
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale }));
  const V = (x, y) => [x * info.s, y * info.s];
  let [px, py] = V(info.W / 2, info.H * 0.62 + 115); await page.mouse.click(px, py); await page.waitForTimeout(800);
  await page.screenshot({ path: 'shots/g4_ready.png' });
  for (let lvl = 1; lvl <= 1; lvl++) {
    [px, py] = V(info.W / 2, info.H * 0.85); await page.mouse.click(px, py); // старт касанием
    let shots = 0; const t0 = Date.now(); let st;
    while (Date.now() - t0 < 90000) {
      st = await page.evaluate(() => { const d = __dbg(), r = d.run; const g = r.objs.find(o => o.type === 'gate' && !o.done && o.z > r.z); let tx = r.x;
        if (g) { const l = g.L.f(r.num), rr = g.R.f(r.num); tx = l >= rr ? -1.5 : 1.5; }
        __steer(tx); return { state: Core.state, z: Math.round(r.z), len: r.len, num: r.num, mult: r.mult, phase: d.phase }; });
      if (st.state !== 'play') break;
      if (Date.now() - t0 > 6000 * (shots + 1) && shots < 3) { shots++; await page.screenshot({ path: `shots/g4_l${lvl}_run${shots}.png` }); }
      await page.waitForTimeout(100);
    }
    await page.waitForTimeout(1500); await page.screenshot({ path: `shots/g4_l${lvl}_end.png` });
    console.log('level', lvl, JSON.stringify(st), 'coins', await page.evaluate(() => Core.save.coins));
    if (st.state !== 'win') break;
    [px, py] = V(info.W / 2, info.H * 0.5 - 350 + 590 + 48); await page.mouse.click(px, py); await page.waitForTimeout(1500);
  }
  console.log('ERRORS:', errs.join('\n'));
  await browser.close();
})();
