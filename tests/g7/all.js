// Все уровни в настоящем браузере: решатель находит, как пройти, автопилот проходит в странице, снимаем кадры и проверяем ошибки
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const { solve } = require('./solve.js');
const H = globalThis.HookSim;
(async () => {
  const plans = H.levels.map((_, i) => solve(i).params);
  const b = await chromium.launch();
  const [vw, vh, touch] = process.argv[2] === 'phone' ? [390, 844, true] : [1280, 720, false];
  const ctx = await b.newContext({ viewport: { width: vw, height: vh }, hasTouch: touch, isMobile: touch, locale: process.argv[3] || 'ru-RU' });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await p.goto('file://' + path.resolve(__dirname, '../../g7-hook/index.html')); await p.waitForTimeout(500);
  await p.screenshot({ path: path.join(__dirname, 'shots', `all_${vw}_menu.png`) });
  for (let li = 0; li < H.levels.length; li++) {
    await p.evaluate(([li, plan]) => {
      clearInterval(window.__ap); window.__hook.start(false, li);
      let idx = 0; const k = window.__hook.keys;
      window.__ap = setInterval(() => {
        const S = window.__hook.S, T = S.truck, R = S.L.anchors.slice().sort((a, b) => a.x0 - b.x0); let a = R[idx], hook = false;
        if (a && !S.rope && !a.broken && T.x > a.x + 500) { idx++; a = R[idx]; }
        if (S.state === 'play' && a) { const q = plan[idx];
          if (S.rope && S.ropeA === a) { hook = q.climb ? !(S.grounded && T.y < a.y + 300 && (T.x > a.x - 80 || S.rope.len <= 160)) : !(T.x > a.x + q.rel); if (!hook) idx++; }
          else hook = S.target === a && (q.climb || T.x > a.x - q.att); }
        if (S.state === 'dead') idx = Math.max(0, R.findIndex((q) => q.x0 > T.x - 50));
        if (a && a.broken) idx++;
        let gas = true, brake = false; const an = Math.atan2(Math.sin(T.a), Math.cos(T.a));
        if (!S.grounded && !S.rope) { gas = an > 0.25; brake = an < -0.25; } else if (S.grounded && an < -0.55) { gas = false; brake = an < -0.85; }
        k.ArrowRight = gas; k.ArrowLeft = brake; k.Space = hook; k.KeyS = !!(S.rope && a && a.climb && a.snap);
      }, 2);
    }, [li, plans[li]]);
    await p.waitForFunction(() => window.__hook.S.t > 3, null, { timeout: 30000 });
    await p.screenshot({ path: path.join(__dirname, 'shots', `all_${vw}_L${li + 1}.png`) });
    const ok = await p.waitForFunction(() => window.__hook.mode === 'win', null, { timeout: 60000 }).then(() => true).catch(() => false);
    await p.waitForTimeout(1300);
    if (li === 0 || li === 11) await p.screenshot({ path: path.join(__dirname, 'shots', `all_${vw}_win${li + 1}.png`) });
    const st = await p.evaluate(() => ({ t: window.__hook.S.wonAt, tries: window.__hook.S.attempts, stars: window.__hook.save().stars }));
    console.log(`уровень ${li + 1}: ${ok ? 'пройден' : 'НЕ ПРОЙДЕН'} за ${st.t ? st.t.toFixed(1) : '-'} с, попыток ${st.tries}`);
  }
  await p.evaluate(() => { clearInterval(window.__ap); }); await p.keyboard.press('Escape');
  await p.evaluate(() => { for (const k in window.__hook.keys) window.__hook.keys[k] = false; });
  // назад в меню — видно звёзды
  await p.mouse.click(vw - 85, 35); await p.waitForTimeout(400); await p.screenshot({ path: path.join(__dirname, 'shots', `all_${vw}_menu_after.png`) });
  console.log('ошибки:', errs.length ? errs.slice(0, 5) : 'нет');
  await b.close();
})();
