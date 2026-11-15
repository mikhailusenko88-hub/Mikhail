// Скриншоты 1920×1080 и кадр для обложки: автопилот играет, в нужный момент останавливаем мир
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const { solve } = require('./solve.js');
const OUT = process.argv[2] || '/tmp/poki';
const SHOTS = [
  // [имя, уровень, условие (в странице), чистый кадр, размер]
  ['shot1_swing', 0, 'S.rope && Math.abs(T.x - S.ropeA.x) < 60', false, [1920, 1080]],
  ['shot2_cave', 6, 'S.rope && S.ropeA === R[1] && T.x > S.ropeA.x - 120', false, [1920, 1080]],
  ['shot3_tower', 9, 'S.rope && S.ropeA === R[2] && T.y < S.ropeA.y + 420 && !S.grounded', false, [1920, 1080]],
  ['shot4_finale', 11, 'S.rope && S.ropeA === R[3] && T.x > S.ropeA.x - 250', false, [1920, 1080]],
  ['cover_raw', 2, 'S.rope && S.ropeA === R[0] && T.x > S.ropeA.x + 60', true, [1024, 1024], { zoom: 1.35, cx: -40, cy: 60 }],
  ['cover_rawT', 2, 'S.rope && S.ropeA === R[0] && T.x > S.ropeA.x + 60', true, [1024, 1024], { zoom: 1.25, cx: -40, cy: 230 }],
];
(async () => {
  const b = await chromium.launch();
  for (const [name, li, cond, clean, [w, h], cam] of SHOTS.filter((q) => !process.argv[3] || q[0].startsWith(process.argv[3]))) {
    const plan = solve(li).params;
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'en-US' });
    await p.goto('file://' + path.resolve(__dirname, '../../g7-hook/index.html')); await p.waitForTimeout(300);
    await p.evaluate(([li, plan, cond, clean, cam]) => {
      const H = window.__hook; H.start(false, li); H.dbg.clean = clean; let idx = 0; const k = H.keys; const test = new Function('S', 'T', 'R', 'return ' + cond);
      window.__ap = setInterval(() => {
        const S = H.S, T = S.truck, R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0); let a = R[idx], hook = false;
        if (S.t > 1 && test(S, T, R)) { H.dbg.freeze = true; clearInterval(window.__ap); window.__got = true; return; }
        if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
        if (S.state === 'play' && a) { const q = plan[idx];
          if (S.rope && S.ropeA === a) { hook = q.climb ? !(S.grounded && T.y < a.y + 300 && (T.x > a.x - 80 || S.rope.len <= 160)) : !(T.x > a.x + q.rel); if (!hook) idx++; }
          else hook = S.target === a && (q.climb || T.x > a.x - q.att); }
        if (a && a.broken) idx++;
        let gas = true, brake = false; const an = Math.atan2(Math.sin(T.a), Math.cos(T.a));
        if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; } else if (S.grounded && an < -0.55) { gas = false; brake = an < -0.85; }
        k.ArrowRight = gas; k.ArrowLeft = brake; k.Space = hook; k.KeyS = !!(S.rope && a && a.climb && a.snap);
      }, 2);
      if (cam) Object.assign(H.dbg, cam);
    }, [li, plan, cond, clean, cam]);
    const ok = await p.waitForFunction(() => window.__got, null, { timeout: 40000 }).then(() => true).catch(() => false);
    await p.waitForTimeout(1800); // камера догоняет, надписи гаснут
    await p.screenshot({ path: path.join(OUT, name + '.png') }); console.log(name, ok ? 'ok' : 'НЕ ДОЖДАЛСЯ');
    await p.close();
  }
  if (process.argv[3]) { await b.close(); return; }
  // меню (выбор уровня) с частью звёзд
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, locale: 'en-US' });
  await p.addInitScript(() => { try { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [3, 3, 2, 3, 1, 2], best: [], duo: false })); } catch (e) {} });
  await p.goto('file://' + path.resolve(__dirname, '../../g7-hook/index.html')); await p.waitForTimeout(600);
  await p.screenshot({ path: path.join(OUT, 'shot5_levels.png') }); console.log('shot5_levels ok');
  await b.close();
})();
