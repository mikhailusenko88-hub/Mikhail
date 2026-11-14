const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const open = async (g, w = 1280, h = 720) => { const p = await browser.newPage({ viewport: { width: w, height: h } }); p.on('pageerror', e => console.log(g, 'PAGEERR', e.message)); await p.goto(`http://localhost:8765/${g}/index.html`); await p.waitForTimeout(1200); return p; };
  // G2: пауза кнопкой и Escape
  let p = await open('g2-descent', 390, 844);
  await p.keyboard.press('Space'); await p.waitForTimeout(400);
  const info = await p.evaluate(() => ({ W: Core.W, s: Core.scale }));
  await p.mouse.click((info.W - 64) * info.s, 72 * info.s); await p.waitForTimeout(400);
  console.log('G2 after pause click:', await p.evaluate(() => ({ st: Core.state, paused: Core.userPause })));
  await p.screenshot({ path: 'shots/ux_pause.png' });
  await p.keyboard.press('Escape'); await p.waitForTimeout(200);
  console.log('G2 after Esc:', await p.evaluate(() => Core.userPause));
  await p.waitForTimeout(3000); const x0 = await p.evaluate(() => __dbg().world.balls[0].x);
  await p.keyboard.down('ArrowRight'); await p.waitForTimeout(500); await p.keyboard.up('ArrowRight');
  console.log('G2 key steer dx:', Math.round(await p.evaluate(() => __dbg().world.balls[0].x) - x0)); await p.close();
  // G3: пробел — старт и газ; после проигрыша — в гараж
  p = await open('g3-cars');
  await p.keyboard.press('Space'); await p.waitForTimeout(300);
  await p.keyboard.down('Space'); await p.waitForTimeout(2500); await p.keyboard.up('Space');
  console.log('G3 key gas x:', await p.evaluate(() => Math.round(__dbg().car.x)), 'state', await p.evaluate(() => Core.state));
  await p.screenshot({ path: 'shots/ux_g3_wide.png' });
  await p.evaluate(() => Core.fail({ revive: false })); await p.waitForTimeout(800);
  const i3 = await p.evaluate(() => ({ W: Core.W, H: Core.H, s: Core.scale }));
  await p.mouse.click(i3.W / 2 * i3.s, (i3.H * 0.5 - 280 + 560 - 130 + 50) * i3.s); await p.waitForTimeout(800);
  console.log('G3 after fail->button:', await p.evaluate(() => Core.state)); await p.close();
  // G4: пробел — старт, стрелка — вправо
  p = await open('g4-runner');
  await p.keyboard.press('Space'); await p.waitForTimeout(500); await p.keyboard.press('Space'); await p.waitForTimeout(500);
  await p.keyboard.down('ArrowRight'); await p.waitForTimeout(600); await p.keyboard.up('ArrowRight');
  console.log('G4:', await p.evaluate(() => ({ ph: __dbg().phase, x: +__dbg().run.x.toFixed(2), z: Math.round(__dbg().run.z) })));
  await p.screenshot({ path: 'shots/ux_g4_ready.png' }); await p.close();
  // G5: стрелки
  p = await open('g5-io');
  await p.keyboard.press('Space'); await p.waitForTimeout(400); await p.keyboard.press('Space'); await p.waitForTimeout(300);
  const a = await p.evaluate(() => ({ x: __dbg().W.balls[0].x }));
  await p.keyboard.down('ArrowLeft'); await p.waitForTimeout(500); await p.keyboard.up('ArrowLeft');
  console.log('G5 key dx:', Math.round(await p.evaluate(() => __dbg().W.balls[0].x) - a.x)); await p.close();
  await browser.close();
})();
