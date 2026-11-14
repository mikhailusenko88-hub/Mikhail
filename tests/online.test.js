// 4 игрока на одной арене: подключение, видят друг друга, едят точки, кто-то кого-то съедает, задержки
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const names = ['Папа', 'Мама', 'Сын', 'Дочка'], flags = ['RU', 'KZ', 'UZ', 'KG'];
  const pages = [];
  for (let i = 0; i < 4; i++) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU', hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    const p = await ctx.newPage(); p.on('pageerror', (e) => console.log('PAGEERR', i, e.message));
    await p.goto('http://localhost:8770/index.html'); await p.waitForTimeout(700);
    if (i === 0) await p.screenshot({ path: 'tests/shots/onl_join.png' });
    await p.fill('#nick', names[i]); await p.click(`#flags img[alt="${flags[i]}"]`); await p.click('#go');
    pages.push(p);
  }
  await pages[0].waitForTimeout(1500);
  for (const [i, p] of pages.entries()) { const d = await p.evaluate(() => __dbgOnline()); console.log(names[i], 'статус', d.status, 'id', d.myId, 'шариков', d.balls, 'точек', d.dots, 'R', d.R); }
  // все бегут «как человек»: к меньшим, от больших, иначе к точкам
  for (const p of pages) await p.evaluate(() => {
    window.__bot = (me, balls) => { let tx = null, ty = null, best = 1e9, flee = null, fd = 1e9;
      for (const b of balls.values()) { if (!b.alive || b.x === me.x) continue; const d = Math.hypot(b.x - me.x, b.y - me.y);
        if (b.r > me.r * 1.12 && d < fd && d < 350) { fd = d; flee = b; }
        if (me.r > b.r * 1.12 && d < best) { best = d; tx = b.x; ty = b.y; } }
      let vx, vy; if (flee) { vx = me.x - flee.x; vy = me.y - flee.y; } else if (tx !== null && best < 900) { vx = tx - me.x; vy = ty - me.y; } else { const t = performance.now() / 2000; vx = Math.cos(t); vy = Math.sin(t * 1.3); }
      const d = Math.hypot(vx, vy) || 1; return [vx / d, vy / d]; };
  });
  for (let s = 0; s < 4; s++) {
    await pages[0].waitForTimeout(5000);
    const st = []; for (const p of pages) st.push(await p.evaluate(() => { const d = __dbgOnline(); return Math.round(d.me.m) + (d.me.alive ? '' : '✝') + ' ' + d.pingMs + 'ms'; }));
    console.log('через', (s + 1) * 5, 'с:', st.join(' | '));
    for (const p of pages) await p.evaluate(() => { if (!__dbgOnline().me.alive) window.__respawn(); });
    await pages[0].waitForTimeout(400); const al = []; for (const p of pages) al.push(await p.evaluate(() => __dbgOnline().me.alive)); console.log('   после «Заново» живы:', al.join(' '));
  }
  // проверка, что чужие видят меня примерно там же, где я
  const my = await pages[1].evaluate(() => { const d = __dbgOnline(); return { id: d.myId, x: d.me.x, y: d.me.y }; });
  const seen = await pages[0].evaluate((id) => { return window.__seen ? null : null; }, my.id);
  await pages[0].screenshot({ path: 'tests/shots/onl_play.png' });
  await pages[2].screenshot({ path: 'tests/shots/onl_play2.png' });
  console.log(await (await fetch('http://localhost:8091/health')).text());
  await b.close();
})();
