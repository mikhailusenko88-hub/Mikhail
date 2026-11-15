// Скриншоты Hook Truck: меню, уровень у каждого кольца, режим вдвоём, телефон вертикально. Автопилот ведёт игру через __hook.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const url = 'file://' + path.resolve(__dirname, '../../g7-hook/index.html');
  const out = (n) => path.join(__dirname, 'shots', n + '.png');
  for (const [name, vw, vh, touch] of [['pc', 1280, 720, false], ['phone', 390, 844, true], ['land', 844, 390, true]]) {
    const ctx = await b.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 1, hasTouch: touch, isMobile: touch, locale: 'ru-RU' });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
    await p.goto(url); await p.waitForTimeout(600);
    await p.screenshot({ path: out(name + '_menu') });
    // автопилот в странице: тот же, что в тестах
    await p.evaluate((duo) => {
      window.__hook.start(duo);
      const plan = [[250, 200], 'top', [700, 200], [300, 100]]; let idx = 0;
      const k = window.__hook.keys;
      window.__ap = setInterval(() => {
        const S = window.__hook.S, T = S.truck, A = S.L.anchors, a = A[idx]; let hook = false;
        if (S.state === 'play' && a) { const q = plan[idx];
          if (S.rope && S.ropeA === a) { hook = q === 'top' ? !(S.grounded && T.y < a.y + 240 && T.x > a.x - 80) : !(T.x > a.x + q[1]); if (!hook) idx++; }
          else hook = S.target === a && (q === 'top' || T.x > a.x - q[0]); }
        let gas = true, brake = false; if (!S.grounded && !S.rope) { const an = Math.atan2(Math.sin(T.a), Math.cos(T.a)); gas = an > 0.15; brake = an < -0.15; }
        k.ArrowRight = gas; k.ArrowLeft = brake; k.Space = hook;
      }, 4);
    }, name === 'phone');
    const shotsAt = name === 'land' ? [[2.4, 'swing1'], [8.4, 'chasm']] : name === 'pc' ? [[1.0, 'start'], [2.4, 'swing1'], [4.4, 'cliff'], [8.0, 'chasm1'], [9.0, 'chasm2'], [11.5, 'end']] : [[2.4, 'swing1'], [4.6, 'cliff'], [8.4, 'chasm']];
    let t0 = Date.now();
    for (const [sec, tag] of shotsAt) {
      // ждём по игровому времени (в headless кадры могут идти медленнее)
      await p.waitForFunction((s) => window.__hook.S.t >= s || window.__hook.S.state === 'win', sec, { timeout: 60000 });
      await p.screenshot({ path: out(name + '_' + tag) });
    }
    await p.waitForFunction(() => window.__hook.S.state === 'win', null, { timeout: 60000 }).catch(() => {});
    await p.waitForTimeout(1500); await p.screenshot({ path: out(name + '_win') });
    const st = await p.evaluate(() => ({ t: window.__hook.S.t, state: window.__hook.S.state, att: window.__hook.S.attempts }));
    console.log(name, JSON.stringify(st), 'ошибки:', errs.length ? errs : 'нет', Math.round((Date.now() - t0) / 1000) + 'с');
    await ctx.close();
  }
  await b.close();
})();
