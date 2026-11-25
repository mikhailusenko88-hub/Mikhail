// Районы в меню: переключение, замок на втором районе, заказ из второго района открывается и едет. Стоя и лёжа.
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const OUT = process.argv[2] || '/tmp/mud4';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); let bad = 0;
  for (const [name, w, h] of [['390x844', 390, 844], ['812x335', 812, 335], ['667x300', 667, 300]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + require('path').resolve(__dirname, '../../dist/mud-side/index.html')); await p.waitForFunction(() => window.__mud); await p.evaluate(() => window.__mud.toMenu()); await p.waitForTimeout(900);
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { console.log('  НЕТ КНОПКИ ' + id); bad++; return; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(350); };
    const ids = () => p.evaluate(() => window.__mud.buttons.map((q) => q.id).filter((q) => /^(c:|reg:)/.test(q)).join(' '));
    console.log(name, 'новичок:', await ids()); await p.screenshot({ path: `${OUT}/r-${name}-1new.png` });
    await tap('reg:1'); console.log('  район 2 у новичка:', await ids()); await p.screenshot({ path: `${OUT}/r-${name}-2locked.png` });
    await tap('c:6'); const m1 = await p.evaluate(() => window.__mud.S.kind + ' ' + window.__mud.mode + ' ' + (window.__mud.buttons.some((q) => q.id === 'go') ? 'карточка открылась — ОШИБКА' : 'закрыто')); console.log('  нажал закрытый заказ 7:', m1); if (/ОШИБКА/.test(m1)) bad++;
    await p.evaluate(() => { const m = window.__mud; for (const c of window.MudSide.CONTRACTS.slice(0, 8)) m.save.stars[c.id] = 2; Object.assign(m.save.build, { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, lift: 1 }); m.save.coins = 900; m.toMenu(); }); await p.waitForTimeout(400);
    console.log('  прошёл 8 заказов:', await ids()); await p.screenshot({ path: `${OUT}/r-${name}-3reg2.png` });
    await tap('c:8'); await p.waitForTimeout(500); await p.screenshot({ path: `${OUT}/r-${name}-4card.png` }); await tap('go'); await p.waitForTimeout(1200);
    const r = await p.evaluate(() => new Promise((res) => { const m = window.__mud, t0 = performance.now(); const id = setInterval(() => { const S = m.S; m.keys.ArrowRight = true; if (!m.sw.awd) m.flip('awd'); if (!m.sw.lock) m.flip('lock'); if (!m.sw.low) m.flip('low'); if (S.truck.x > 1500 || S.state !== 'play' || performance.now() - t0 > 20000) { clearInterval(id); m.keys.ArrowRight = false; res({ x: Math.round(S.truck.x), st: S.state, soil: S.soil, kind: S.kind, cargo: S.cargo + '/' + S.cargo0 }); } }, 30); }));
    await p.screenshot({ path: `${OUT}/r-${name}-5ride.png` }); console.log('  заказ 9 в рейсе:', JSON.stringify(r)); if (r.st !== 'play' || r.x < 1000) bad++;
    console.log(errs.length ? '  ОШИБКИ: ' + errs.slice(0, 3).join(' | ') : '  без ошибок'); if (errs.length) bad++; await ctx.close();
  }
  console.log(bad ? 'ПРОВАЛОВ: ' + bad : 'всё в порядке'); await b.close();
})();
