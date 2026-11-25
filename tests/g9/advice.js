// Грязь 2D: совет механика в карточке заказа (готов / не хватает монет / купить одной кнопкой), подсказка про новую кнопку, предупреждение о топливе.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const OUT = process.argv[2] || '/tmp/mud4';
(async () => {
  require('fs').mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const [name, w, h] of [['small', 360, 640], ['land', 844, 390]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + require('path').resolve(__dirname, '../../dist/mud-side/index.html')); await p.waitForFunction(() => window.__mud); await p.waitForTimeout(1200);
    const log = [], st = () => p.evaluate(() => { const m = window.__mud; return m.mode + ' ¤' + m.save.coins + ' awd' + m.save.build.awd + ' low' + m.save.build.low + ' кнопки:' + m.buttons.map((b) => b.id).filter((q) => /adv|go|gar/.test(q)).join(','); });
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) { log.push('НЕТ КНОПКИ ' + id); return; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(400); };
    await tap('c:0'); await p.waitForTimeout(600); await p.screenshot({ path: `${OUT}/adv-${name}-1ready.png` }); log.push('заказ 1: ' + await st());
    await p.evaluate(() => { const m = window.__mud; m.save.stars.village = 1; m.save.coins = 90; m.toMenu(); }); await p.waitForTimeout(300);
    await tap('c:1'); await p.waitForTimeout(600); await p.screenshot({ path: `${OUT}/adv-${name}-2poor.png` }); log.push('заказ 2, монет 90: ' + await st());
    await p.evaluate(() => { window.__mud.save.coins = 400; }); await p.waitForTimeout(400); await p.screenshot({ path: `${OUT}/adv-${name}-3buy.png` }); log.push('заказ 2, монет 400: ' + await st());
    await tap('adv'); await p.waitForTimeout(600); await p.screenshot({ path: `${OUT}/adv-${name}-4bought.png` }); log.push('купил по совету: ' + await st());
    await tap('go'); await p.waitForTimeout(2500); await p.screenshot({ path: `${OUT}/adv-${name}-5newkey.png` }); log.push('в рейсе: ' + await st());
    await p.evaluate(() => { const S = window.__mud.S; S.fuel = S.cfg.tank * 0.2; }); await p.waitForTimeout(5200); await p.screenshot({ path: `${OUT}/adv-${name}-6lowfuel.png` });
    await p.evaluate(() => { const m = window.__mud; for (const c of ['village', 'farm', 'creek', 'pit', 'mill']) m.save.stars[c] = 1; Object.assign(m.save.build, { awd: 1, low: 1, lock: 1, tires: 1 }); m.save.coins = 500; m.toMenu(); }); await p.waitForTimeout(300);
    await tap('c:4'); await p.waitForTimeout(700); await p.screenshot({ path: `${OUT}/adv-${name}-7ford.png` }); log.push('заказ 5: ' + await st());
    await tap('adv'); await p.waitForTimeout(600); log.push('заказ 5 после покупки: ' + await st() + ' lift ' + await p.evaluate(() => window.__mud.save.build.lift));
    await p.evaluate(() => window.__mud.toMenu()); await p.waitForTimeout(300); await tap('c:5'); await p.waitForTimeout(700); await p.screenshot({ path: `${OUT}/adv-${name}-8bog.png` }); log.push('заказ 6: ' + await st());
    await tap('adv'); await p.waitForTimeout(500); await p.screenshot({ path: `${OUT}/adv-${name}-9bog-opt.png` }); log.push('заказ 6 после шноркеля: ' + await st() + ' snorkel ' + await p.evaluate(() => window.__mud.save.build.snorkel));
    console.log(name + '\n  ' + log.join('\n  ') + '\n  ' + (errs.length ? 'ОШИБКИ: ' + errs.slice(0, 3).join(' | ') : 'без ошибок')); await ctx.close();
  }
  await b.close();
})();
