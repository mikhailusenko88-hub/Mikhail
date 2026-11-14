const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const errs = []; page.on('console', m => { if (m.type() === 'error' || m.type()==='warning') errs.push(m.type()+': '+m.text()); }); page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g1-draw/index.html'); await page.waitForTimeout(1500);
  await page.screenshot({ path: 'shots/g1_home.png' });
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale, plat: Core.platform, mock: Core.mockAds, lang: Core.lang, home: Core.homeCountry() }));
  console.log(JSON.stringify(info));
  const V = (x, y) => [x * info.s, y * info.s];
  let [px, py] = V(info.W / 2, info.H * 0.62 + 115); await page.mouse.click(px, py); await page.waitForTimeout(900);
  await page.screenshot({ path: 'shots/g1_l1.png' });
  async function drawPath(hint) {
    const ox = (info.W - 720) / 2, oy = Math.max(0, (info.H - 1280) / 2);
    const pts = []; for (let i = 1; i < hint.length; i++) { const [a, b] = hint[i - 1], [c, d] = hint[i]; for (let k = 0; k < 12; k++) pts.push([a + (c - a) * k / 12, b + (d - b) * k / 12]); } pts.push(hint[hint.length - 1]);
    const [sx, sy] = V(pts[0][0] + ox, pts[0][1] + oy); await page.mouse.move(sx, sy); await page.mouse.down();
    for (const [x, y] of pts) { const [cx, cy] = V(x + ox, y + oy); await page.mouse.move(cx, cy); await page.waitForTimeout(8); }
    await page.mouse.up();
  }
  for (let lvl = 1; lvl <= 4; lvl++) {
    const hint = await page.evaluate((i) => DRSim.LEVELS[i]().hint, lvl - 1);
    await drawPath(hint); await page.waitForTimeout(700); await page.screenshot({ path: `shots/g1_l${lvl}_race.png` });
    await page.waitForTimeout(2600); await page.screenshot({ path: `shots/g1_l${lvl}_end.png` });
    const st = await page.evaluate(() => ({ state: Core.state, level: Core.save.level, coins: Core.save.coins }));
    console.log('level', lvl, JSON.stringify(st));
    if (st.state === 'win') { // нажать «дальше» (без рекламы)
      await page.waitForTimeout(1200);
      const py2 = info.H * 0.5 - 350 + 590 + 48; [px, py] = V(info.W / 2, py2); await page.mouse.click(px, py); await page.waitForTimeout(3500);
    } else if (st.state === 'fail') { await page.waitForTimeout(1500); await page.screenshot({ path: `shots/g1_l${lvl}_fail.png` }); break; }
  }
  await page.screenshot({ path: 'shots/g1_after.png' });
  console.log('ERRORS:', errs.slice(0, 10).join('\n'));
  await browser.close();
})();
