// Кадры объёмной версии: автопилот играет в настоящем Chrome (WebGL программно), в нужный момент мир останавливается
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const { solve } = require('./solve.js');
const DIR = path.resolve(__dirname, '../../g8-hook3d'), OUT = process.argv[2] || '/tmp/h3d';
require('fs').mkdirSync(OUT, { recursive: true });
const ALL = {
  start: [0, 'S.t > 1.2 && S.grounded', [1280, 720]],
  swing: [0, 'S.rope && Math.abs(T.x - S.ropeA.x) < 70', [1280, 720]],
  climb: [1, 'S.rope && T.y < S.ropeA.y + 330', [1280, 720]],
  cave: [6, 'S.rope && S.ropeA === R[1] && T.x > S.ropeA.x - 120', [1280, 720]],
  snap: [7, 'S.rope && S.ropeA && S.ropeA.snap && S.ropeA.hang > 0.3', [1280, 720]],
  boost: [4, 'S.grounded && S.L.boosts.length && T.x > S.L.boosts[0].x0 + 120', [1280, 720]],
  phone: [2, 'S.rope && S.ropeA === R[0] && T.x > S.ropeA.x - 40', [390, 844]],
  land: [5, 'S.rope && T.x > S.ropeA.x - 60', [844, 390]],
};
(async () => {
  const names = process.argv.slice(3).length ? process.argv.slice(3) : Object.keys(ALL);
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of names) {
    const [li, cond, [w, h]] = ALL[name], plan = solve(li).params, touch = w < 900;
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => (m.type() === 'error' || m.type() === 'warning') && errs.push(m.type() + ': ' + m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(800);
    const is3d = await p.evaluate(() => window.__hook.use3d);
    await p.evaluate(([li, plan, cond]) => {
      const H = window.__hook; H.start(false, li); let idx = 0; const k = H.keys; const test = new Function('S', 'T', 'R', 'return ' + cond);
      window.__ap = setInterval(() => {
        const S = H.S, T = S.truck, R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0); let a = R[idx], hook = false;
        if (S.t > 0.5 && test(S, T, R)) { H.dbg.freeze = true; clearInterval(window.__ap); window.__got = true; return; }
        if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
        if (S.state === 'play' && a) { const q = plan[idx];
          if (S.rope && S.ropeA === a) { hook = q.climb ? !(S.grounded && T.y < a.y + 300 && (T.x > a.x - 80 || S.rope.len <= 160)) : !(T.x > a.x + q.rel); if (!hook) idx++; }
          else hook = S.target === a && (q.climb || T.x > a.x - q.att); }
        if (a && a.broken) idx++;
        let gas = true, brake = false; const an = Math.atan2(Math.sin(T.a), Math.cos(T.a));
        if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; } else if (S.grounded && an < -0.55) { gas = false; brake = an < -0.85; }
        k.ArrowRight = gas; k.ArrowLeft = brake; k.Space = hook; k.KeyS = !!(S.rope && a && a.climb && a.snap);
      }, 2);
    }, [li, plan, cond]);
    const ok = await p.waitForFunction(() => window.__got, null, { timeout: 90000 }).then(() => true).catch(() => false);
    await p.waitForTimeout(2600);
    await p.screenshot({ path: path.join(OUT, name + '.png') });
    console.log(name, '3d=' + is3d, ok ? 'ok' : 'НЕ ДОЖДАЛСЯ', errs.length ? errs.slice(0, 4) : '');
    await ctx.close();
  }
  await b.close();
})();
