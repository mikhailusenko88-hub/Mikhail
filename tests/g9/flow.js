// Грязь 2D v2: переходы — рейс → гараж с отметки → продолжить; финиш → панель → гараж. Нажатия — настоящие касания по кнопкам.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/mud-side'), OUT = process.argv[2] || '/tmp/mud2';
const SIZES = { phone: [390, 844, true], land: [844, 390, true], desk: [1280, 720, false], sq: [600, 600, true], small: [360, 640, true] };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of process.argv.slice(3).length ? process.argv.slice(3) : ['phone']) {
    const [w, h, touch] = SIZES[name], log = [];
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForFunction(() => window.__mud, null, { timeout: 60000 }); await p.waitForTimeout(1500);
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { log.push('нет кнопки ' + id); return; } if (touch) await p.touchscreen.tap(q[0], q[1]); else await p.mouse.click(q[0], q[1]); await p.waitForTimeout(500); };
    const st = () => p.evaluate(() => { const m = window.__mud, S = m.S; return { mode: m.mode, x: Math.round(S.truck.x), cp: S.cp ? Math.round(S.cp.x) : 0, fuel: Math.round(S.fuel), b: [m.build.base, m.build.lift, m.build.wheel, m.build.axles, m.build.tires, m.build.snorkel].join('') }; });
    await tap('p:lift:1'); await tap('tab:1'); await tap('p:tires:2'); await tap('tab:2'); await tap('p:snorkel:1'); log.push('детали: ' + JSON.stringify(await st()));
    await tap('go'); log.push('в рейс: ' + JSON.stringify(await st()));
    // доезжаем до первой отметки без кадров ожидания: шаги считаем в странице
    await p.evaluate(() => { const m = window.__mud, S = m.S; m.dbg.freeze = true; let n = 0; while (!S.cp && n++ < 120 * 40) S.step({ gas: true, awd: true }); m.dbg.freeze = false; });
    await p.waitForTimeout(1200); await p.screenshot({ path: path.join(OUT, name + '-f1cp.png') }); log.push('отметка: ' + JSON.stringify(await st()));
    await tap('gar'); await p.waitForTimeout(800); await p.screenshot({ path: path.join(OUT, name + '-f2garage-resume.png') }); log.push('гараж: ' + JSON.stringify(await st()));
    await tap('tab:1'); await tap('p:wheel:1'); await tap('cont'); await p.waitForTimeout(900); log.push('с отметки: ' + JSON.stringify(await st()));
    // к финишу: ставим отметку перед лесопилкой и едем
    await p.evaluate(() => { const m = window.__mud, S = m.S; m.dbg.freeze = true; S.cp = { x: S.L.fin - 700, y: S.groundAt(S.L.fin - 700), fuel: 20 }; S.respawn(); m.dbg.freeze = false; m.keys.ArrowRight = true; });
    await p.waitForFunction(() => window.__mud.mode === 'win', null, { timeout: 90000 }).catch(() => log.push('не дождался финиша'));
    await p.evaluate(() => { window.__mud.keys.ArrowRight = false; }); await p.waitForTimeout(2500); await p.screenshot({ path: path.join(OUT, name + '-f3win.png') }); log.push('финиш: ' + JSON.stringify(await st()));
    await tap('gar'); await p.waitForTimeout(800); log.push('в гараж после финиша: ' + JSON.stringify(await st())); await p.screenshot({ path: path.join(OUT, name + '-f4garage.png') });
    console.log(name + '\n  ' + log.join('\n  ') + '\n  ' + (errs.length ? errs.slice(0, 4).join(' | ') : 'без ошибок'));
    await ctx.close();
  }
  await b.close();
})();
