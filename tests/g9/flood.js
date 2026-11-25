// Грязь 2D v2: обычный грузовик у брода 1,1 м — предупреждение заранее, после залива панель с объяснением, из неё в гараж, лифт, с отметки — и брод пройден.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const DIR = path.resolve(__dirname, '../../dist/mud-side'), OUT = process.argv[2] || '/tmp/mud2';
const SIZES = { phone: [390, 844, true], land: [844, 390, true], small: [360, 640, true] };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of process.argv.slice(3).length ? process.argv.slice(3) : ['phone']) {
    const [w, h, touch] = SIZES[name], log = [];
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForFunction(() => window.__mud, null, { timeout: 60000 }); await p.evaluate(() => window.__mud.toMenu()); // первый запуск теперь сразу в рейсе — проверки начинают с меню
    await p.waitForTimeout(1200); await p.evaluate(() => window.__mud.press('poly')); await p.waitForTimeout(600); // с пробы 4 игра открывается на заказах; эта проверка — про полигон
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { log.push('НЕТ КНОПКИ ' + id); return; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(500); };
    const st = () => p.evaluate(() => { const m = window.__mud, S = m.S; return { mode: m.mode, st: S.state, why: S.why, x: Math.round(S.truck.x), lift: m.build.lift }; });
    await tap('go');
    const fordX = await p.evaluate(() => { const m = window.__mud, S = m.S, wz = S.L.water[1]; m.dbg.freeze = true; S.cp = { x: wz.x0 - 700, y: S.groundAt(wz.x0 - 700), fuel: 60 }; S.respawn(); m.dbg.freeze = false; return wz.x1; });
    await p.waitForTimeout(900); await p.screenshot({ path: path.join(OUT, name + '-w1warn.png') });
    await p.evaluate(() => { window.__mud.sw.awd = true; window.__mud.keys.ArrowRight = true; });
    await p.waitForFunction(() => window.__mud.S.state === 'dead', null, { timeout: 60000 }).catch(() => log.push('не залило'));
    await p.waitForTimeout(4000); log.push('после залива (4 с): ' + JSON.stringify(await st())); await p.screenshot({ path: path.join(OUT, name + '-w2fail.png') });
    await tap('gar'); await p.waitForTimeout(700); await p.screenshot({ path: path.join(OUT, name + '-w3garage.png') }); await tap('tab:0'); await tap('p:lift:1'); await tap('cont');
    await p.waitForFunction((fx) => window.__mud.S.truck.x > fx + 100 || window.__mud.S.state === 'dead', fordX, { timeout: 90000 }).catch(() => log.push('не доехал'));
    log.push('с лифтом: ' + JSON.stringify(await st()) + ' конец брода ' + Math.round(fordX)); await p.screenshot({ path: path.join(OUT, name + '-w4pass.png') });
    console.log(name + '\n  ' + log.join('\n  ') + '\n  ' + (errs.length ? errs.slice(0, 4).join(' | ') : 'без ошибок'));
    await ctx.close();
  }
  await b.close();
})();
