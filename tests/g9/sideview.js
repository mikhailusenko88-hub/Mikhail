// Грязь, вид сбоку — в настоящем браузере: «умный» водитель проходит рейс, по дороге снимаем кадры. Ошибок в консоли быть не должно.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/mud-side'), OUT = process.argv[2] || '/tmp/mudside';
const SIZES = { phone: [390, 844, true], land: [844, 390, true], desk: [1280, 720, false] };
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of process.argv.slice(3).length ? process.argv.slice(3) : ['phone']) {
    const [w, h, touch] = SIZES[name];
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
    await p.screenshot({ path: path.join(OUT, name + '-00start.png') });
    // водитель: включает нужное по участкам, в болоте застрял — лебёдка
    await p.evaluate(() => {
      const m = window.__mud, S = m.S, L = S.L;
      setInterval(() => {
        const x = S.truck.x, z = L.mud.find((q) => x > q.x0 - 150 && x < q.x1 + 60), deep = z && z.d > 60, stk = z && z.d > 50, mid = z && z.d > 40;
        const up = S.groundAt(x + 160) < S.groundAt(x - 40) - 25, steep = S.groundAt(x + 160) < S.groundAt(x - 40) - 70;
        m.sw.awd = !!(mid || up); m.sw.lock = !!stk; m.sw.low = !!(deep || steep); m.keys.ArrowRight = m.mode === 'play';
        m.keys.Space = window.__winch ? !!(deep && (S.rope || S.target)) : false;
      }, 30);
    });
    const shots = [[1500, 'shallow'], [2900, 'hill'], [4500, 'medium'], [6600, 'sticky'], [8300, 'steep'], [10700, 'ford'], [12400, 'swamp'], [13600, 'swamp2'], [15900, 'mill']]; let si = 0; const t0 = Date.now();
    while (si < shots.length && Date.now() - t0 < 260000) {
      const s = await p.evaluate(() => ({ x: window.__mud.S.truck.x, mode: window.__mud.mode, st: window.__mud.S.state }));
      if (shots[si][1] === 'swamp2') await p.evaluate(() => { window.__winch = true; });
      if (s.x >= shots[si][0]) { await p.screenshot({ path: path.join(OUT, `${name}-${String(si + 1).padStart(2, '0')}${shots[si][1]}.png`) }); si++; }
      if (s.mode === 'win') break; await p.waitForTimeout(250);
    }
    await p.waitForTimeout(2500); await p.screenshot({ path: path.join(OUT, name + '-99win.png') });
    const r = await p.evaluate(() => ({ mode: window.__mud.mode, x: Math.round(window.__mud.S.truck.x), t: +window.__mud.S.t.toFixed(0), fuel: Math.round(window.__mud.S.fuel), rescues: window.__mud.S.rescues }));
    console.log(name, JSON.stringify(r), errs.length ? errs.slice(0, 4) : 'без ошибок');
    await ctx.close();
  }
  await b.close();
})();
