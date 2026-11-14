// Онлайн v1.1: 4 игрока, бонусы и пилы, рост арены, «Заново» реальным касанием (в т.ч. после «потерянного» касания)
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const names = ['Папа', 'Мама', 'Сын', 'Дочка'], flags = ['RU', 'KZ', 'UZ', 'KG'];
  const pages = [];
  for (let i = 0; i < 4; i++) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU', hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    const p = await ctx.newPage(); p.on('pageerror', (e) => console.log('PAGEERR', i, e.message));
    await p.goto('http://localhost:8770/index.html'); await p.waitForTimeout(600);
    await p.fill('#nick', names[i]); await p.click(`#flags img[alt="${flags[i]}"]`); await p.click('#go');
    await p.waitForTimeout(900);
    const d = await p.evaluate(() => __dbgOnline()); console.log(names[i], 'зашёл:', d.status, 'R', d.R, 'пил', d.saws, 'бонусов', d.powers);
    pages.push(p);
  }
  await pages[0].waitForTimeout(3000);
  console.log('R после 4 игроков:', (await pages[0].evaluate(() => __dbgOnline())).R);
  await pages[0].screenshot({ path: 'tests/shots/onl2_play.png' });
  for (const p of pages) await p.evaluate(() => {
    window.__bot = (me, balls) => { let tx = null, ty = null, best = 1e9, flee = null, fd = 1e9;
      for (const b of balls.values()) { if (!b.alive || b.x === me.x) continue; const d = Math.hypot(b.x - me.x, b.y - me.y);
        if (b.r > me.r * 1.12 && d < fd && d < 350) { fd = d; flee = b; } if (me.r > b.r * 1.12 && d < best) { best = d; tx = b.x; ty = b.y; } }
      let vx, vy; if (flee) { vx = me.x - flee.x; vy = me.y - flee.y; } else if (tx !== null && best < 900) { vx = tx - me.x; vy = ty - me.y; } else { const t = performance.now() / 2000; vx = Math.cos(t); vy = Math.sin(t * 1.3); }
      const d = Math.hypot(vx, vy) || 1; return [vx / d, vy / d]; };
  });
  // ждём, пока кого-нибудь съедят; потом «Заново» настоящим касанием после «потерянного» касания
  let tested = false;
  for (let s = 0; s < 40 && !tested; s++) {
    await pages[0].waitForTimeout(1000);
    for (const [i, p] of pages.entries()) {
      const d = await p.evaluate(() => __dbgOnline());
      if (!d.me.alive && d.dead) {
        await p.waitForTimeout(800);
        await p.screenshot({ path: 'tests/shots/onl2_dead.png' });
        const cdp = await p.context().newCDPSession(p);
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 200, y: 300, id: 1 }] }); // касание без отпускания
        await p.evaluate(() => window.dispatchEvent(new Event('noop')));
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 200, y: 300, id: 1 }, { x: 195, y: 620, id: 2 }] });
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [{ x: 200, y: 300, id: 1 }] });
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
        await p.touchscreen.tap(195, 620);
        await p.waitForTimeout(700);
        const d2 = await p.evaluate(() => __dbgOnline());
        console.log(names[i], 'съели → нажал «Заново» →', d2.me.alive ? 'снова в игре ✔' : 'НЕ ВЕРНУЛСЯ ✘');
        tested = true; break;
      }
    }
  }
  const st = []; for (const p of pages) st.push(await p.evaluate(() => { const d = __dbgOnline(); return Math.round(d.me.m) + (d.me.alive ? '' : '✝'); }));
  console.log('массы:', st.join(' | '));
  // один выходит — арена сжимается, остальные получают сообщение
  await pages[3].context().close();
  await pages[0].waitForTimeout(4000);
  console.log('R после выхода одного:', (await pages[0].evaluate(() => __dbgOnline())).R);
  await pages[0].screenshot({ path: 'tests/shots/onl2_play_b.png' });
  console.log(await (await fetch('http://localhost:8091/health')).text());
  await b.close();
})();
