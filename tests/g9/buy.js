// Покупка в гараже на том же месте: первое нажатие — примерка, кнопка детали становится «Купить», второе нажатие по ней — покупка.
// Проверяет: обычную деталь, ступень мотора, краску, «добрать за рекламу», «не хватает», двойной тычок подряд, отмену примерки другой деталью. Стоя и лёжа.
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const OUT = process.argv[2] || '/tmp/mud4';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); let bad = 0;
  for (const [name, w, h] of [['390x844', 390, 844], ['812x335', 812, 335], ['667x300', 667, 300]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + require('path').resolve(__dirname, '../../dist/mud-side/index.html')); await p.waitForFunction(() => window.__mud); await p.evaluate(() => window.__mud.toMenu()); await p.waitForTimeout(800);
    const pos = (id) => p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2, b.w, b.h] : null; }, id);
    const tap = async (id, wait = 400) => { const q = await pos(id); if (!q) { console.log('  НЕТ КНОПКИ ' + id); bad++; return null; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(wait); return q; };
    const st = () => p.evaluate(() => { const m = window.__mud, bd = m.save.build; return { coins: m.save.coins, lift: bd.lift, eng: bd.eng, paint: bd.paint, skid: bd.skid, ids: m.buttons.map((q) => q.id).filter((q) => /^(buy|adcoins)$/.test(q)).join(',') }; });
    const check = (what, ok, extra) => { console.log(`  ${ok ? 'да ' : 'НЕТ'} ${what}${extra ? ' — ' + extra : ''}`); if (!ok) bad++; };
    console.log(name);
    await p.evaluate(() => { const m = window.__mud; m.save.coins = 1000; m.toMenu(); }); await tap('c:0'); await tap('gar'); await tap('tab:0');
    const q1 = await tap('p:lift:1'); let s = await st(); const qb = await pos('buy');
    check('после первого нажатия деталь не куплена, кнопка «Купить» на том же месте', s.lift === 0 && s.coins === 1000 && !!qb && Math.abs(qb[0] - q1[0]) < 2 && Math.abs(qb[1] - q1[1]) < 2, `кнопка ${Math.round(qb ? qb[2] : 0)}×${Math.round(qb ? qb[3] : 0)} px`);
    await p.screenshot({ path: `${OUT}/b-${name}-1preview.png` });
    await tap('buy'); s = await st(); check('второе нажатие там же — куплено', s.lift === 1 && s.coins === 750, JSON.stringify(s));
    // двойной тычок подряд (60 мс) не покупает
    const q2 = await pos('p:skid:1'); await p.touchscreen.tap(q2[0], q2[1]); await p.waitForTimeout(60); await p.touchscreen.tap(q2[0], q2[1]); await p.waitForTimeout(500); s = await st(); check('двойной тычок подряд не покупает', s.skid === 0 && s.coins === 750 && s.ids === 'buy', JSON.stringify(s));
    // передумал: нажал другую деталь — примерка переехала, деньги целы
    await tap('p:lift:2'); s = await st(); check('нажал другую деталь — ничего не куплено, «Купить» одна', s.skid === 0 && s.lift === 1 && s.coins === 750 && s.ids.split(',').length === 1, JSON.stringify(s));
    // ступень мотора
    await tap('tab:2'); const q3 = await tap('p:eng:1'); const qe = await pos('buy'); check('форсировка: «Купить» на месте плюса', !!qe && Math.abs(qe[0] - q3[0]) < 2 && Math.abs(qe[1] - q3[1]) < 2); await p.screenshot({ path: `${OUT}/b-${name}-2eng.png` });
    await tap('buy'); s = await st(); check('форсировка 1 куплена', s.eng === 1 && s.coins === 600, JSON.stringify(s));
    // не хватает, но больше половины: добрать за рекламу, потом купить
    await p.evaluate(() => { window.__mud.save.coins = 200; }); await tap('p:eng:2'); s = await st(); check('чуть не хватает — жёлтая «Добрать»', s.ids === 'adcoins', JSON.stringify(s)); await p.screenshot({ path: `${OUT}/b-${name}-3ad.png` });
    await tap('adcoins'); s = await st(); check('после рекламы — зелёная «Купить»', s.ids === 'buy' && s.coins === 350, JSON.stringify(s)); await tap('buy'); s = await st(); check('форсировка 2 куплена', s.eng === 2 && s.coins === 0, JSON.stringify(s));
    // совсем не хватает
    await tap('p:eng:3'); s = await st(); check('денег нет — кнопки покупки нет, деталь не куплена', s.ids === '' && s.eng === 2, JSON.stringify(s)); await p.screenshot({ path: `${OUT}/b-${name}-4poor.png` });
    // краска
    await p.evaluate(() => { window.__mud.save.coins = 300; }); await tap('tab:3'); await tap('p:paint:3'); await p.screenshot({ path: `${OUT}/b-${name}-5paint.png` }); await tap('buy'); s = await st(); check('краска куплена', s.paint === 3 && s.coins === 200, JSON.stringify(s));
    const off = await p.evaluate(() => window.__mud.buttons.filter((q) => q.x < 0 || q.y < 0 || q.x + q.w > innerWidth + 1 || q.y + q.h > innerHeight + 1).map((q) => q.id)); check('кнопки в экране', !off.length, off.join(','));
    console.log(errs.length ? '  ОШИБКИ: ' + errs.slice(0, 3).join(' | ') : '  без ошибок'); if (errs.length) bad++; await ctx.close();
  }
  console.log(bad ? 'ПРОВАЛОВ: ' + bad : 'всё в порядке'); await b.close();
})();
