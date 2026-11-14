const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const ps = [];
  for (let i = 0; i < 2; i++) { const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, locale: 'ru-RU', hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    const p = await ctx.newPage(); p.on('pageerror', (e) => console.log('PAGEERR', e.message)); await p.goto('http://localhost:8770/index.html'); await p.waitForTimeout(500);
    await p.fill('#nick', ['Папа', 'Мама'][i]); await p.click('#go'); ps.push(p); await p.waitForTimeout(i ? 700 : 300); }
  await ps[0].screenshot({ path: 'tests/shots/onl3_grow.png' });
  // едем к ближайшему бонусу, потом к пиле
  for (const what of ['powers', 'saws']) {
    await ps[0].evaluate((what) => { window.__bot = (me) => { const o = __objs()[what]; let best = null, bd = 1e9; for (const s of o) { const d = Math.hypot(s.x - me.x, s.y - me.y); if (d < bd) { bd = d; best = s; } } if (!best) return [0, 0]; const vx = best.x - me.x, vy = best.y - me.y, d = Math.hypot(vx, vy) || 1; return d < 200 ? [0, 0] : [vx / d, vy / d]; }; }, what);
    for (let s = 0; s < 30; s++) { await ps[0].waitForTimeout(400); const near = await ps[0].evaluate((what) => { const d = __dbgOnline(), o = __objs()[what]; return Math.min(...o.map((s) => Math.hypot(s.x - d.me.x, s.y - d.me.y))); }, what); if (near < 260) break; }
    await ps[0].screenshot({ path: `tests/shots/onl3_${what}.png` });
  }
  const st = await ps[0].evaluate(() => { const d = __dbgOnline(); return { m: Math.round(d.me.m), alive: d.me.alive, pw: d.powers, sw: d.saws, R: d.R }; });
  console.log(JSON.stringify(st));
  await b.close();
})();
