// Прогон «Шара в кузове»: на каждом уровне держим газ (или простой автопилот) и смотрим, что происходит.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.join(__dirname, '../../dist-web/g6-truck');
const SHOTS = path.join(__dirname, 'shots'); fs.mkdirSync(SHOTS, { recursive: true });
const levels = (process.argv[2] || '1').split(',').map(Number), secs = +(process.argv[3] || 25), view = process.argv[4] === 'port' ? { width: 405, height: 720 } : { width: 1280, height: 720 };
const pilot = process.argv[5] || 'gas';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--allow-file-access-from-files'] });
  for (const n of levels) {
    const p = await (await b.newContext({ viewport: view, deviceScaleFactor: view.width < 500 ? 2 : 1 })).newPage();
    const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(600);
    await p.evaluate((n) => window.__lvl(n), n); await p.waitForTimeout(300);
    if (n === 5) await p.evaluate(() => { window.__waitX = 600; });
    // автопилот: газ; если шарик подлетает или нос задран — отпускаем; на крутом спуске тормозим
    await p.evaluate((mode) => {
      window.__autoGas = mode === 'gas';
      // «умный» пилот: на земле газ (на крутом спуске притормаживает), в воздухе выравнивает нос;
      // перед ямой с платформой ждёт, пока платформа подъедет к краю
      // пилот для всех препятствий: ждёт платформы и лифты, проскакивает под прессами, в воздухе выравнивается
      if (mode === 'smart2') setInterval(() => {
        const t = __truck(); let g = true, br = false; const stop = () => { g = false; br = t.vx > 25; };
        window.__commit = window.__commit || {};
        if (!t.grounded) { g = t.a > 0.12; br = t.a < -0.35; }
        else if (t.vx > 700 && t.a > 0.25) { g = false; br = true; }
        for (const m of t.movs) {
          const near = m.x0 - m.len / 2, far = m.lift ? near + m.len : m.x1 + m.len / 2;
          if (t.x > near - 520 && t.x < near - 150 && m.s > 0.02) stop();
          if (t.x >= near - 150 && t.x < far - 60 && t.x > near + 40 && m.s < 0.985) stop();
        }
        for (const c of t.crs) { if (t.x > c.x - 700 && t.x < c.x - 160) { if (c.u < 0.3) window.__commit[c.x] = 1; if (!window.__commit[c.x]) stop(); } if (t.x > c.x + 150) window.__commit[c.x] = 0; }
        window.__autoGas = g; window.__autoBrk = br;
      }, 30);
      if (mode === 'smart') setInterval(() => {
        const t = __truck(); let g = true, br = false;
        if (!t.grounded) { g = t.a > 0.12; br = t.a < -0.35; }
        else if (t.vx > 700 && t.a > 0.25) { g = false; br = true; }
        if (t.mov && t.mov.length) for (const mx of t.mov) { const edge = window.__edge = window.__edge || {}; }
        if (window.__waitX && t.x > window.__waitX - 700 && t.x < window.__waitX - 120 && !(t.mov[0] < window.__waitX + 25)) { g = false; br = true; }
        if (window.__waitX && t.x >= window.__waitX && t.x < window.__waitX + 700 && t.mov[0] + 330 < window.__waitX + 700 - 30) { g = false; br = true; }
        window.__autoGas = g; window.__autoBrk = br;
      }, 40);
    }, pilot);
    const log = [];
    for (let i = 0; i < secs * 2; i++) {
      await p.waitForTimeout(500);
      const t = await p.evaluate(() => window.__truck());
      log.push(t);
      if (i % 6 === 3) await p.screenshot({ path: `${SHOTS}/L${n}_${i}.png` });
      if (t.cs !== 'play' || t.state !== 'play') break;
    }
    const last = log[log.length - 1];
    console.log(`L${n}: ${last.state}/${last.cs} x=${last.x}/${last.fin} t=${last.tm} star=${last.star} cp=${last.cp} inBed=${last.inBed} a=${last.a}` + (errs.length ? ' ERR ' + errs.join('|') : ''));
    console.log('   ' + log.filter((_, i) => i % 4 === 0).map((t) => `${t.x}:${t.vx}:${t.a}${t.inBed ? '' : '!'}`).join(' '));
    await p.screenshot({ path: `${SHOTS}/L${n}_end.png` });
    await p.context().close();
  }
  await b.close();
})();
