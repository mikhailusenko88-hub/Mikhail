// Грязь 2D, версия 2 — в настоящем браузере: гараж на трёх размерах, смена деталей, проезд полигона автопилотом, кадры, ошибок в консоли быть не должно.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/mud-side'), OUT = process.argv[2] || '/tmp/mud2';
const SIZES = { phone: [390, 844, true], land: [844, 390, true], desk: [1280, 720, false], sq: [600, 600, true] };
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of process.argv.slice(3).length ? process.argv.slice(3) : ['phone']) {
    const [w, h, touch] = SIZES[name];
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForFunction(() => window.__mud, null, { timeout: 60000 }); await p.evaluate(() => window.__mud.toMenu()); // первый запуск теперь сразу в рейсе — проверки начинают с меню
    await p.waitForTimeout(2500);
    await p.screenshot({ path: path.join(OUT, name + '-0garage.png') });
    await p.evaluate(() => { const m = window.__mud; m.setPart('base', 1); m.setPart('lift', 2); m.setPart('wheel', 2); m.setPart('axles', 3); m.setPart('tires', 2); m.setPart('snorkel', 1); m.setPart('tank', 1); }); await p.waitForTimeout(1800);
    await p.screenshot({ path: path.join(OUT, name + '-1garage-all.png') });
    await p.evaluate(() => { const m = window.__mud; m.setPart('base', 0); m.setPart('lift', 1); m.setPart('wheel', 0); m.setPart('axles', 2); m.setPart('tires', 2); m.setPart('snorkel', 1); m.setPart('tank', 0); m.start(false); });
    // водитель: режимы по участку, в болоте — лебёдка
    await p.evaluate(() => { const m = window.__mud; setInterval(() => { const S = m.S, L = S.L, x = S.truck.x, z = L.mud.find((q) => x > q.x0 - 120 && x < q.x1 + 40), d = z ? z.d : 0, up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30, wz = S.waterAt(x + 60);
      m.sw.awd = d >= 34 || up || !!wz || S.stuckT > 0.4; m.sw.lock = d >= 46 || S.stuckT > 1; m.sw.low = d >= 56 || up || S.stuckT > 0.8 || !!(wz && wz.depth > 55); m.keys.ArrowRight = m.mode === 'play'; m.keys.Space = d >= 72 && (!!S.rope || (S.stuckT > 1.5 && !!S.target)); }, 30); });
    const shots = [[1400, 'softmud'], [2760, 'crest'], [3900, 'ford09'], [5300, 'mud'], [6900, 'climb'], [8300, 'ford11'], [9700, 'sticky'], [13100, 'ford15'], [15500, 'swamp'], [16300, 'swamp2']]; let si = 0; const t0 = Date.now();
    while (si < shots.length && Date.now() - t0 < 230000) {
      const s = await p.evaluate(() => ({ x: window.__mud.S.truck.x, mode: window.__mud.mode }));
      if (s.x >= shots[si][0]) { await p.screenshot({ path: path.join(OUT, `${name}-${String(si + 2)}${shots[si][1]}.png`) }); si++; }
      if (s.mode === 'win') break; await p.waitForTimeout(200);
    }
    await p.waitForTimeout(2500); await p.screenshot({ path: path.join(OUT, name + '-99end.png') });
    const r = await p.evaluate(() => { const m = window.__mud, S = m.S; return { mode: m.mode, x: Math.round(S.truck.x), t: +S.t.toFixed(0), fuel: Math.round(100 * S.fuel / S.cfg.tank), rescues: S.rescues, dirt: +S.dirt.toFixed(2) }; });
    console.log(name, JSON.stringify(r), errs.length ? errs.slice(0, 4) : 'без ошибок');
    await ctx.close();
  }
  await b.close();
})();
