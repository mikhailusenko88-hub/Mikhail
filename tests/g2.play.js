const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const errs = []; page.on('console', m => { if (m.type() === 'error' && !m.text().includes('404')) errs.push(m.text()); }); page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  await page.goto('http://localhost:8765/g2-descent/index.html'); await page.waitForTimeout(1200);
  await page.screenshot({ path: 'shots/g2_home.png' });
  const info = await page.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale }));
  const V = (x, y) => [x * info.s, y * info.s];
  let [px, py] = V(info.W / 2, info.H * 0.62 + 115); await page.mouse.click(px, py); await page.waitForTimeout(800);
  await page.screenshot({ path: 'shots/g2_countdown.png' });
  await page.evaluate(() => { window.__auto = true; });
  for (let lvl = 1; lvl <= 4; lvl++) {
    await page.waitForTimeout(6000); await page.screenshot({ path: `shots/g2_l${lvl}_mid.png` });
    let st;
    for (let i = 0; i < 40; i++) { await page.waitForTimeout(500); st = await page.evaluate(() => ({ state: Core.state, level: Core.save.level, coins: Core.save.coins, p: (({x,y,dead,done,place})=>({x:Math.round(x),y:Math.round(y),dead,done,place}))(__dbg().world.balls[0]), fin: __dbg().world.finishY })); if (st.state !== 'play') break; }
    await page.waitForTimeout(1500); await page.screenshot({ path: `shots/g2_l${lvl}_end.png` });
    console.log('level', lvl, JSON.stringify(st));
    if (st.state === 'win') { [px, py] = V(info.W / 2, info.H * 0.5 - 350 + 590 + 48); await page.mouse.click(px, py); await page.waitForTimeout(1500); }
    else if (st.state === 'fail') { // оживление за рекламу (тест)
      [px, py] = V(info.W / 2, info.H * 0.5 - 280 + 230 + 60); await page.mouse.click(px, py); await page.waitForTimeout(3000);
      const s2 = await page.evaluate(() => Core.state); console.log(' after revive click:', s2); break; }
  }
  console.log('ERRORS:', errs.join('\n'));
  await browser.close();
})();
