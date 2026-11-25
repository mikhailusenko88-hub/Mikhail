// Новое в пробе 5.1 в настоящем браузере: пять чисел в гараже, грузоподъёмность в карточке заказа, посадка брюхом на гребне → задний ход → с разгона.
// node tests/g9/hung.js [папка для снимков]
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const OUT = process.argv[2] || '/tmp/mud4';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const [name, w, h] of [['phone', 390, 844], ['small', 320, 568], ['land', 844, 390]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + require('path').resolve(__dirname, '../../dist/mud-side/index.html')); await p.waitForFunction(() => window.__mud); await p.evaluate(() => window.__mud.toMenu()); // первый запуск теперь сразу в рейсе — проверки начинают с меню
    await p.waitForTimeout(1000);
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { console.log('  НЕТ КНОПКИ ' + id); return; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(350); };
    console.log(name);
    // 1) заказ с бочками на родном моторе: упёрся в вес
    await p.evaluate(() => { const m = window.__mud; for (const c of ['village', 'farm', 'creek', 'pit', 'mill']) m.save.stars[c] = 1; Object.assign(m.save.build, { awd: 1, low: 1, lock: 1, tires: 1 }); m.save.coins = 3000; m.toMenu(); }); await p.waitForTimeout(300);
    await tap('c:3'); for (let i = 0; i < 6; i++) await tap('lg+'); await p.waitForTimeout(500); await p.screenshot({ path: `${OUT}/h-${name}-1payload.png` });
    console.log('  бочки, родной мотор:', await p.evaluate(() => { const m = window.__mud; return m.S.cargo0 + ' шт, грузоподъёмность ' + window.MudSide.payT(m.S.cfg) + ' т, места ' + window.MudSide.spaceOf(m.S.cfg, 'barrel'); }));
    // 2) гараж: примерка форсировки — пятое число растёт
    await tap('gar'); await tap('tab:2'); await tap('p:eng:1'); await p.waitForTimeout(500); await p.screenshot({ path: `${OUT}/h-${name}-2garage.png` });
    await tap('buy'); await tap('menu'); for (let i = 0; i < 6; i++) await tap('lg+'); console.log('  после форсировки 1:', await p.evaluate(() => window.__mud.S.cargo0 + ' шт, мотор ' + window.__mud.save.build.eng));
    // 3) полигон, очень длинная база, на пониженной медленно на гребень: садится, подсказка, задний ход, с разгона
    await p.evaluate(() => window.__mud.toMenu()); await p.waitForTimeout(200); await tap('poly'); await p.evaluate(() => { const m = window.__mud; m.setPart('base', 2); m.setPart('lift', 0); m.setPart('wheel', 0); m.setPart('axles', 2); }); await p.waitForTimeout(300); await tap('go'); await p.waitForTimeout(600);
    const drive = (fn, ms) => p.evaluate(([f, ms]) => new Promise((res) => { const m = window.__mud, t0 = performance.now(), g = new Function('m', 'return (' + f + ')(m)'); const id = setInterval(() => { const r = g(m); if (r || performance.now() - t0 > ms) { clearInterval(id); for (const k in m.keys) m.keys[k] = false; res({ r: !!r, x: Math.round(m.S.truck.x), hung: m.S.hung, st: m.S.state }); } }, 30); }), [fn.toString(), ms]);
    const cx = await p.evaluate(() => window.__mud.S.L.signs.find((s) => s.kind === 'crest').x);
    let r = await drive((m) => { const S = m.S; m.keys.ArrowRight = S.truck.x < 1900 || S.truck.vx < 150; if (!m.sw.low) m.flip('low'); if (!m.sw.awd) m.flip('awd'); S.fuel = 50; return (S.hung && S.stuckT > 1.2) || S.truck.x > 3200; }, 60000);
    await p.evaluate(() => { window.__mud.keys.ArrowRight = true; }); await p.waitForTimeout(1300); await p.screenshot({ path: `${OUT}/h-${name}-3hung.png` }); await p.evaluate(() => { window.__mud.keys.ArrowRight = false; }); console.log('  сел на гребне:', JSON.stringify(r), 'указатель гребня', Math.round(cx));
    const hx = r.x; r = await drive((m) => { m.keys.ArrowRight = false; m.keys.ArrowLeft = true; return m.S.truck.x < 0; }, 2500); const backX = r.x; console.log('  задний ход 2,5 с:', hx, '→', backX, backX < hx - 150 ? 'съехал' : 'НЕ СЪЕХАЛ');
    r = await drive((m) => { m.keys.ArrowLeft = true; m.S.fuel = 50; return m.S.truck.x < 0; }, 600);
    r = await p.evaluate(([hx]) => new Promise((res) => { const m = window.__mud, t0 = performance.now(); const id = setInterval(() => { const S = m.S; S.fuel = 50; if (m.sw.low) m.flip('low'); m.keys.ArrowLeft = S.truck.x > hx - 700 && !m.__go; if (!m.keys.ArrowLeft) { m.__go = true; m.keys.ArrowRight = true; } if (S.truck.x > hx + 500 || performance.now() - t0 > 25000) { clearInterval(id); m.keys.ArrowRight = m.keys.ArrowLeft = false; res({ x: Math.round(S.truck.x), ok: S.truck.x > hx + 500, hung: S.hung }); } }, 30); }), [hx]);
    console.log('  с разгона без пониженной:', JSON.stringify(r), r.ok ? 'гребень взят' : 'НЕ ВЗЯТ'); await p.screenshot({ path: `${OUT}/h-${name}-4over.png` });
    console.log(errs.length ? '  ОШИБКИ: ' + errs.slice(0, 3).join(' | ') : '  без ошибок'); await ctx.close();
  }
  await b.close();
})();
