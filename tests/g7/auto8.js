// «Один палец» в настоящем браузере: газ даёт сама игра, тест только держит и отпускает крюк (пробел) по плану решателя.
// После падения игра ждёт нажатия; дальше идём по плану для этого флажка (кольца там всегда начинают одинаково).
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const { solve, solveCp } = require('./solve.js');
const H = globalThis.HookSim;
(async () => {
  const only = process.argv[3] ? process.argv[3].split(',').map(Number) : H.levels.map((_, i) => i);
  const b = await chromium.launch();
  const [vw, vh, touch] = process.argv[2] === 'phone' ? [390, 844, true] : [1280, 720, false];
  const ctx = await b.newContext({ viewport: { width: vw, height: vh }, hasTouch: touch, isMobile: touch, locale: 'ru-RU' });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await p.addInitScript(() => { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], best: [], duo: false })); }); // уровни «уже пройдены»: без обучения
  await p.goto('file://' + path.resolve(__dirname, '../../g8-hook3d/index.html') + '?flat'); await p.waitForTimeout(500);
  let bad = 0;
  for (const li of only) {
    const L = H.create(li).L, plans = { s: solve(li).params }; L.cps.forEach((c, i) => { plans[i] = solveCp(li, i).params; });
    const cps = L.cps.map((c) => c.x);
    await p.evaluate(([li, plans, cps, manual]) => {
      clearInterval(window.__ap); const Hk = window.__hook; Hk.setCtl(manual ? 'manual' : 'auto'); Hk.start(false, li);
      let idx = 0, plan = plans.s, att0 = 1; const k = Hk.keys;
      window.__ap = setInterval(() => {
        const S = Hk.S, T = S.truck, R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0);
        if (Hk.mode !== 'play') { k.Space = false; return; }
        // новая попытка: какой флажок — такой и план
        if (S.attempts !== att0 && S.state === 'play') { att0 = S.attempts; const ci = S.cp ? cps.findIndex((x) => x === S.cp.x) : -1; plan = ci >= 0 ? plans[ci] : plans.s; idx = Math.max(0, R.findIndex((q) => q.x0 > T.x - 50)); }
        if (Hk.wait) { k.Space = !k.Space; return; } // короткое нажатие «поехали»
        if (manual) { let gas = true, brake = false; const an = Math.atan2(Math.sin(T.a), Math.cos(T.a)); if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; } else if (S.grounded && an < -0.55) { gas = false; brake = an < -0.85; } k.ArrowRight = gas; k.ArrowLeft = brake; }
        let a = R[idx], hook = false;
        if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
        if (S.state === 'play' && a) { const q = plan[idx] || { att: 9999, rel: 150 };
          if (S.rope && S.ropeA === a) { hook = q.climb ? !(S.grounded && T.y < a.y + 300 && (T.x > a.x - 80 || S.rope.len <= 160)) : !(T.x > a.x + q.rel); if (!hook) idx++; }
          else hook = S.target === a && (q.climb || T.x > a.x - q.att); }
        if (a && a.broken) idx++;
        if (S.rope && !(a && a.climb)) { if (window.__hk === undefined) window.__hk = S.t; if (S.t - window.__hk > 6) { hook = false; idx = Math.max(idx, S.ropeA.i + 1); } } else window.__hk = undefined; // как человек: надоело висеть — отпустил
        k.Space = hook;
      }, 2);
    }, [li, plans, cps, process.env.HOOK_CTL === 'manual']);
    const r = await p.waitForFunction(() => window.__hook.mode === 'win' || window.__hook.S.attempts > 12, null, { timeout: 150000 }).then(() => p.evaluate(() => ({ win: window.__hook.mode === 'win', t: window.__hook.S.t, att: window.__hook.S.attempts }))).catch(() => ({ win: false, att: -1 }));
    if (!r.win) { bad++; console.log('   где застрял:', await p.evaluate(() => { const Hk = window.__hook, S = Hk.S; return JSON.stringify({ mode: Hk.mode, wait: Hk.wait, state: S.state, x: Math.round(S.truck.x), y: Math.round(S.truck.y), vx: Math.round(S.truck.vx), rope: S.ropeA ? S.ropeA.i : null, len: S.rope ? Math.round(S.rope.len) : null, cp: S.cp && S.cp.x, att: S.attempts, t: +S.t.toFixed(1), space: !!Hk.keys.Space }); })); }
    console.log(`уровень ${li + 1}: ${r.win ? 'пройден за ' + r.t.toFixed(1) + ' с' : 'НЕ ПРОЙДЕН'}, попыток ${r.att}`);
  }
  console.log('ошибки:', errs.length ? errs.slice(0, 5) : 'нет', '| не пройдено уровней:', bad);
  await b.close();
})();
