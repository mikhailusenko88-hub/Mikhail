// Грязь 2D, заказы: список → карточка → рейс → итог с монетами → гараж → примерка и покупка → следующий заказ; пауза, тягач, авария. Нажатия — настоящие касания.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/mud-side'), OUT = process.argv[2] || '/tmp/mud4';
const SIZES = { phone: [390, 844, true], land: [844, 390, true], desk: [1280, 720, false], sq: [600, 600, true], small: [360, 640, true] };
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of process.argv.slice(3).length ? process.argv.slice(3) : ['phone']) {
    const [w, h, touch] = SIZES[name], log = [];
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForFunction(() => window.__mud, null, { timeout: 60000 }); await p.waitForTimeout(1500);
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { log.push('НЕТ КНОПКИ ' + id); return; } if (touch) await p.touchscreen.tap(q[0], q[1]); else await p.mouse.click(q[0], q[1]); await p.waitForTimeout(350); };
    const st = () => p.evaluate(() => { const m = window.__mud, S = m.S; return { mode: m.mode, coins: m.save.coins, cargo: S.cargo + '/' + S.cargo0 + ' ' + S.kind, stars: JSON.stringify(m.save.stars), b: 'awd' + m.build.awd + ' eng' + m.build.eng, paused: m.paused }; });
    const shot = async (n) => { await p.waitForTimeout(700); await p.screenshot({ path: path.join(OUT, `${name}-${n}.png`) }); };
    // автопилот в странице: едет до финиша или аварии
    const drive = (lim = 80) => p.evaluate((lim) => { const m = window.__mud, S = m.S; m.dbg.freeze = true; let n = 0; while (S.state === 'play' && n++ < 120 * lim) { const x = S.truck.x, z = S.L.mud.find((q) => !q.wet && x > q.x0 - 120 && x < q.x1 + 40), up = S.groundAt(x + 160) < S.groundAt(x - 40) - 30; S.step({ gas: true, awd: !!z || up || S.stuckT > 0.4, lock: S.stuckT > 1, low: up || S.stuckT > 0.8 }); } m.dbg.freeze = false; return S.state + ' x=' + Math.round(S.truck.x / 54) + 'м'; }, lim);
    await shot('1menu'); log.push('список: ' + JSON.stringify(await st()));
    await tap('c:1'); log.push('закрытый заказ: ' + JSON.stringify(await st()));
    await tap('c:0'); await shot('2brief'); log.push('карточка: ' + JSON.stringify(await st()));
    await tap('lg+'); await tap('lg+'); await tap('lg+'); await tap('lg+'); log.push('полный кузов: ' + JSON.stringify(await st()));
    await tap('go'); await p.waitForTimeout(1200); await shot('3ride'); log.push('в рейс: ' + JSON.stringify(await st()));
    await tap('pause'); await shot('4pause'); log.push('пауза: ' + JSON.stringify(await st())); await tap('resume');
    log.push('автопилот: ' + await drive()); await p.waitForFunction(() => window.__mud.mode === 'win', null, { timeout: 20000 }).catch(() => log.push('не дождался финиша'));
    await p.waitForTimeout(1800); await shot('5win'); log.push('итог: ' + JSON.stringify(await st()) + ' ' + JSON.stringify(await p.evaluate(() => window.__mud.res)));
    await tap('x2'); log.push('×2: ' + JSON.stringify(await st()));
    await tap('menu'); await tap('gar'); await tap('tab:2'); await shot('6garage'); log.push('гараж: ' + JSON.stringify(await st()));
    await tap('p:awd:1'); await shot('7preview'); log.push('примерка 4×4: ' + JSON.stringify(await st()));
    await tap('buy'); log.push('куплено: ' + JSON.stringify(await st()));
    await tap('p:eng:1'); await shot('8eng'); log.push('примерка форсировки: ' + JSON.stringify(await st())); await tap('buy'); log.push('после «купить»: ' + JSON.stringify(await st()));
    await tap('menu'); await tap('c:1'); await shot('9brief2'); await tap('go'); await p.waitForTimeout(800);
    log.push('заказ 2, автопилот: ' + await drive()); await p.waitForTimeout(2200); await shot('10end2'); log.push('заказ 2: ' + JSON.stringify(await st()));
    // авария: топим мотор в заказе 5 (нужен лифт) — открываем его для теста
    await p.evaluate(() => { const m = window.__mud; for (const c of ['village', 'farm', 'creek', 'pit']) m.save.stars[c] = Math.max(1, m.save.stars[c] || 0); m.toMenu(); });
    await p.waitForTimeout(500); await shot('11menu-open'); await tap('c:4'); await shot('11b-brief-deep'); await tap('go'); await p.waitForTimeout(1500); await shot('11c-ride-warn'); await p.waitForTimeout(800);
    log.push('заказ 5 без лифта: ' + await drive(40)); await p.waitForTimeout(1800); await shot('12fail'); log.push('авария: ' + JSON.stringify(await st()));
    await tap('gar'); await shot('13garage-after-flood'); log.push('в гараж после залива: ' + JSON.stringify(await st()) + ' вкладка ' + await p.evaluate(() => window.__mud.buttons.filter((b) => b.id.startsWith('p:lift')).length ? 'Шасси' : 'другая'));
    await tap('p:lift:1'); await shot('13b-lift-preview'); await tap('adcoins'); await tap('buy'); log.push('лифт куплен: ' + JSON.stringify(await st()) + ' lift ' + await p.evaluate(() => window.__mud.build.lift));
    await tap('menu'); await shot('14brief-ok'); await tap('go'); await p.waitForTimeout(800);
    log.push('с лифтом: ' + await p.evaluate(() => { const m = window.__mud, S = m.S, w = S.L.water[0]; m.dbg.freeze = true; let n = 0; while (S.state === 'play' && S.truck.x < w.x1 + 200 && n++ < 120 * 30) S.step({ gas: true, awd: true }); m.dbg.freeze = false; return S.state + (S.truck.x > w.x1 ? ', брод пройден' : ', НЕ ПРОЙДЕН'); }));
    await tap('pause'); await tap('tow'); await p.waitForTimeout(500); log.push('тягач из паузы: ' + await p.evaluate(() => window.__mud.S.state + ' tows ' + window.__mud.S.tows + ' paused ' + window.__mud.paused));
    await tap('pause'); await tap('quit'); log.push('бросил рейс: ' + JSON.stringify(await st()));
    await tap('unsel'); await tap('poly'); await shot('15poly'); log.push('полигон: ' + JSON.stringify(await st())); await tap('go'); await p.waitForTimeout(1500); await shot('16poly-ride'); log.push('полигон, рейс: ' + JSON.stringify(await st()));
    console.log(name + '\n  ' + log.join('\n  ') + '\n  ' + (errs.length ? 'ОШИБКИ: ' + errs.slice(0, 4).join(' | ') : 'без ошибок'));
    await ctx.close();
  }
  await b.close();
})();
