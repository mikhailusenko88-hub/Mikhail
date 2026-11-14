// Покадрово: уровень n, автопилот smart, снимки каждые dt секунд с from до to
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.join(__dirname, '../../dist-web/g6-truck');
const [n, from, to, step] = [+process.argv[2], +process.argv[3], +process.argv[4], +(process.argv[5] || 0.2)];
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--allow-file-access-from-files'] });
  const p = await (await b.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
  await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(600);
  await p.evaluate((n) => window.__lvl(n), n); await p.waitForTimeout(200);
  if (n === 5) await p.evaluate(() => { window.__waitX = 600; });
  await p.evaluate(() => setInterval(() => {
    const t = __truck(); let g = true, br = false;
    if (!t.grounded) { g = t.a > 0.12; br = t.a < -0.35; }
    else if (t.vx > 700 && t.a > 0.25) { g = false; br = true; }
    if (window.__waitX && t.x > window.__waitX - 700 && t.x < window.__waitX - 120 && !(t.mov[0] < window.__waitX + 25)) { g = false; br = true; }
    if (window.__waitX && t.x >= window.__waitX && t.x < window.__waitX + 700 && t.mov[0] + 330 < window.__waitX + 700 - 30) { g = false; br = true; }
    window.__autoGas = g; window.__autoBrk = br;
  }, 40));
  const t0 = Date.now(); const frames = [];
  while ((Date.now() - t0) / 1000 < to) {
    const t = (Date.now() - t0) / 1000;
    if (t >= from) { const f = '/tmp/seq_' + frames.length + '.png'; await p.screenshot({ path: f }); frames.push(f); console.log(frames.length - 1, t.toFixed(2), JSON.stringify(await p.evaluate(() => { const t = __truck(); return [t.x, t.y, t.a, t.vx, t.grounded, t.inBed, t.state, t.mov]; }))); }
    await p.waitForTimeout(step * 1000);
  }
  await b.close();
})();
