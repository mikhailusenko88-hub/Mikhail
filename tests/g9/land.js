// Телефон лёжа: первый запуск сразу в рейс, гараж с крупными кнопками, заказы. Размеры — как у телефонов в браузере с панелями.
// node tests/g9/land.js [папка для снимков]
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const OUT = process.argv[2] || '/tmp/mud4';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); let bad = 0;
  for (const [name, w, h] of [['844x390', 844, 390], ['812x335', 812, 335], ['740x320', 740, 320], ['667x300', 667, 300], ['390x844', 390, 844]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + require('path').resolve(__dirname, '../../dist/mud-side/index.html')); await p.waitForFunction(() => window.__mud); await p.waitForTimeout(1500);
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { console.log('  НЕТ КНОПКИ ' + id); bad++; return; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(350); };
    const first = await p.evaluate(() => { const m = window.__mud; return { mode: m.mode, cargo: m.S.cargo0, kind: m.S.kind, seen: JSON.stringify(m.save.seen || {}) }; });
    await p.screenshot({ path: `${OUT}/l-${name}-0first.png` }); if (first.mode !== 'play') bad++;
    console.log(name, 'первый запуск:', JSON.stringify(first), first.mode === 'play' ? 'сразу в рейсе' : 'НЕ В РЕЙСЕ');
    await p.reload(); await p.waitForFunction(() => window.__mud); await p.waitForTimeout(800); const second = await p.evaluate(() => window.__mud.mode); console.log('  второй запуск:', second, second === 'menu' ? '' : 'ОЖИДАЛОСЬ МЕНЮ'); if (second !== 'menu') bad++;
    await p.evaluate(() => { const m = window.__mud; for (const c of ['village', 'farm', 'creek']) m.save.stars[c] = 1; m.save.coins = 2500; m.toMenu(); }); await p.waitForTimeout(300);
    await p.screenshot({ path: `${OUT}/l-${name}-1list.png` }); await tap('c:1'); await p.waitForTimeout(400); await p.screenshot({ path: `${OUT}/l-${name}-2card.png` }); await tap('gar'); await p.waitForTimeout(500);
    for (let t = 0; t < 4; t++) { await tap('tab:' + t); await p.waitForTimeout(300); await p.screenshot({ path: `${OUT}/l-${name}-g${t}.png` });
      const m = await p.evaluate(() => { const bs = window.__mud.buttons.filter((q) => /^(p:|tab:|buy|menu)/.test(q.id)), ps = bs.filter((q) => /^p:/.test(q.id) && !/paint/.test(q.id)); return { n: ps.length, minH: Math.round(Math.min(...ps.map((q) => q.h))), minW: Math.round(Math.min(...ps.map((q) => q.w))), tabH: Math.round(Math.min(...bs.filter((q) => /^tab/.test(q.id)).map((q) => q.h))), off: bs.filter((q) => q.x < 0 || q.y < 0 || q.x + q.w > innerWidth + 1 || q.y + q.h > innerHeight + 1).map((q) => q.id) }; });
      const small = m.minH < 34 || m.minW < 44 || m.off.length; if (small) bad++; console.log(`  вкладка ${t}: кнопок деталей ${m.n}, самая низкая ${m.minH} px, самая узкая ${m.minW} px, вкладки ${m.tabH} px${m.off.length ? ', ЗА ЭКРАНОМ: ' + m.off.join(',') : ''}${small ? '  ← МЕЛКО' : ''}`); }
    await tap('tab:0'); await tap('p:lift:1'); await p.waitForTimeout(400); await p.screenshot({ path: `${OUT}/l-${name}-g-preview.png` }); await tap('buy'); const lift = await p.evaluate(() => window.__mud.save.build.lift + ' монет ' + window.__mud.save.coins); console.log('  купил лифт пальцем:', lift); if (!/^1 /.test(lift)) bad++;
    console.log(errs.length ? '  ОШИБКИ: ' + errs.slice(0, 3).join(' | ') : '  без ошибок'); if (errs.length) bad++; await ctx.close();
  }
  console.log(bad ? 'ПРОВАЛОВ: ' + bad : 'всё в порядке'); await b.close();
})();
