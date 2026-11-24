// Обложки и скриншоты объёмной Hook Truck: автопилот играет, в нужный момент мир замирает; заголовок — поверх кадра
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const { solve } = require('../g7/solve.js');
const DIR = path.resolve(__dirname, '../../g8-hook3d'), OUT = process.argv[2] || '/tmp/promo3d';
fs.mkdirSync(OUT, { recursive: true });
// [имя, уровень, условие, размер, камера, вид грузовика, заголовок, чистый кадр]
const LOOK_RED = { truck: 0, wheels: 1, color: 0 }, LOOK_GOLD = { truck: 2, wheels: 2, color: 7 }, LOOK_BLUE = { truck: 1, wheels: 3, color: 1 };
const SHOTS = [
  ['cover_16x9', 12, 'S.rope && S.ropeA === R[0] && T.x > S.ropeA.x - 120', [1920, 1080], { zoom: 1.45, cx: 120, cy: 150 }, LOOK_RED, 'land', true],
  ['cover_9x16', 12, 'S.rope && S.ropeA === R[0] && T.x > S.ropeA.x - 120', [1080, 1920], { zoom: 2.05, cx: -15, cy: 45 }, LOOK_RED, 'port', true],
  ['cover_1x1', 12, 'S.rope && S.ropeA === R[0] && T.x > S.ropeA.x - 120', [800, 800], { zoom: 0.95, cx: -10, cy: 92 }, LOOK_RED, 'sq1', true],
  ['shot1_meadow', 2, 'S.rope && S.ropeA === R[1] && T.x > S.ropeA.x - 30', [1920, 1080], null, LOOK_RED, null, false],
  ['shot2_canyon', 15, 'S.rope && S.ropeA === R[1] && T.x > S.ropeA.x - 150', [1920, 1080], null, LOOK_GOLD, null, false],
  ['shot3_cave', 6, 'S.rope && S.ropeA === R[1] && T.x > S.ropeA.x - 120', [1920, 1080], null, LOOK_BLUE, null, false],
  ['shot4_wall', 1, 'S.rope && T.y < S.ropeA.y + 330', [1920, 1080], null, LOOK_RED, null, false],
  ['shot5_port', 12, 'S.rope && T.x > S.ropeA.x - 40', [1080, 1920], null, LOOK_GOLD, null, false],
];
// заголовок: [кегль, верх, левый край, ширина блока] — доли кадра
const TITLE = { land: [190, 0.2, 0.5, 0.5], port: [200, 0.05, 0, 1], sq1: [92, 0.035, 0, 1] };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const [name, li, cond, [w, h], cam, look, title, clean] of SHOTS.filter((q) => !process.argv[3] || process.argv.slice(3).includes(q[0]))) {
    const plan = solve(li).params;
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'en-US' });
    await p.addInitScript((look) => { localStorage.setItem('hooktruck_v1', JSON.stringify(Object.assign({ stars: [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2], best: [], duo: false, tut: [1, 1], coins: 0, own: [0, 1, 2], ownW: [0, 1, 2, 3], ownC: [0, 1, 2, 3, 4, 5, 6, 7, 8], ctl: 'manual' }, look))); }, look);
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(800);
    await p.evaluate(([li, plan, cond, cam, clean]) => {
      const H = window.__hook; H.start(false, li); let idx = 0; const k = H.keys; const test = new Function('S', 'T', 'R', 'return ' + cond);
      window.__ap = setInterval(() => {
        const S = H.S, T = S.truck, R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0); let a = R[idx], hook = false;
        if (S.t > 0.8 && test(S, T, R)) { H.dbg.freeze = true; H.dbg.clean = clean; if (cam) Object.assign(H.dbg, cam); clearInterval(window.__ap); window.__got = true; return; }
        if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
        if (S.state === 'play' && a) { const q = plan[idx];
          if (S.rope && S.ropeA === a) { hook = q.climb ? !(S.grounded && T.y < a.y + 300 && (T.x > a.x - 80 || S.rope.len <= 160)) : !(T.x > a.x + q.rel); if (!hook) idx++; }
          else hook = S.target === a && (q.climb || T.x > a.x - q.att); }
        if (a && a.broken) idx++;
        let gas = true, brake = false; const an = Math.atan2(Math.sin(T.a), Math.cos(T.a));
        if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; } else if (S.grounded && an < -0.55) { gas = false; brake = an < -0.85; }
        k.ArrowRight = gas; k.ArrowLeft = brake; k.Space = hook;
      }, 2);
    }, [li, plan, cond, cam, clean]);
    const ok = await p.waitForFunction(() => window.__got, null, { timeout: 30000 }).then(() => true).catch(() => false);
    await p.waitForTimeout(3000);
    if (title) {
      const [fs2, top, lx, bw] = TITLE[title];
      await p.evaluate(([fs2, top, lx, bw, w, h]) => {
        const d = document.createElement('div');
        d.style.cssText = `position:fixed;left:${Math.round(lx * w)}px;width:${Math.round(bw * w)}px;top:${Math.round(top * h)}px;text-align:center;z-index:9;font:900 ${fs2}px/0.95 system-ui,sans-serif;letter-spacing:2px;color:#ffca28;-webkit-text-stroke:${Math.round(fs2 * 0.1)}px #bf360c;paint-order:stroke fill;text-shadow:0 ${Math.round(fs2 * 0.07)}px 0 rgba(90,20,0,.55)`;
        d.innerHTML = fs2 < 100 ? 'HOOK TRUCK' : 'HOOK<br>TRUCK'; document.body.appendChild(d);
      }, [fs2, top, lx, bw, w, h]);
      await p.waitForTimeout(200);
    }
    await p.screenshot({ path: path.join(OUT, name + '.png') }); console.log(name, ok ? 'ok' : 'НЕ ДОЖДАЛСЯ');
    await p.close();
  }
  // гараж и меню
  if (!process.argv[3] || process.argv.slice(3).includes('shot6_garage')) {
    const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, locale: 'en-US' });
    await p.addInitScript(() => { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [3, 3, 2, 3, 1, 2, 3, 2, 1, 3, 2, 1, 3], best: [], duo: false, tut: [1, 1], coins: 1240, own: [0, 1, 2], ownW: [0, 1, 2], ownC: [0, 1, 7], truck: 2, wheels: 2, color: 7, up: { eng: 2, winch: 1 }, ctl: 'manual' })); });
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(800);
    await p.evaluate(() => window.__hook.garage()); await p.waitForTimeout(2500);
    await p.screenshot({ path: path.join(OUT, 'shot6_garage.png') }); console.log('shot6_garage ok');
    await p.evaluate(() => window.__hook.click(30, 30)); await p.waitForTimeout(1500);
    await p.screenshot({ path: path.join(OUT, 'shot7_menu.png') }); console.log('shot7_menu ok');
    await p.close();
  }
  await b.close();
})();
