const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, locale: 'kk-KZ' });
  const errs = []; page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g5-io/index.html'); await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/io_home.png' });
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale }));
  const V = (x, y) => [x * info.s, y * info.s];
  let [px, py] = V(info.W / 2, info.H * 0.62 + 115); await page.mouse.click(px, py); await page.waitForTimeout(900);
  await page.screenshot({ path: 'shots/io_ready.png' });
  await page.evaluate(() => { window.__auto = true; });
  let shots = 0; const t0 = Date.now(); let st;
  while (Date.now() - t0 < 130000) {
    st = await page.evaluate(() => { const d = __dbg(), p = d.W.balls[0]; return { state: Core.state, t: Math.round(d.W.t), time: d.W.time, m: Math.round(p.m), alive: p.alive, kind: d.endKind, rank: d.W.balls.filter(b => b.alive || b.isPlayer).sort((a, b) => b.m - a.m).indexOf(p) + 1 }; });
    if (st.state !== 'play') break;
    if (Date.now() - t0 > 12000 * (shots + 1) && shots < 3) { shots++; await page.screenshot({ path: `shots/io_run${shots}.png` }); console.log(JSON.stringify(st)); }
    await page.waitForTimeout(500);
  }
  await page.waitForTimeout(1500); await page.screenshot({ path: 'shots/io_end.png' });
  console.log('END', JSON.stringify(st));
  console.log('ERRORS:', errs.join('\n'));
  await browser.close();
})();
