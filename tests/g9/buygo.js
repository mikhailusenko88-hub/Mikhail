// 27.11: новичок на втором заказе без 4×4 шесть раз завяз в грязи и ушёл — кнопка «В рейс» покупает нужную деталь, экран «Застрял» предлагает её и заново
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const fs = require('fs');
const [W, H] = (process.argv[2] || '859x237').split('x').map(Number), OUT = '/tmp/buygo/' + W + 'x' + H; fs.mkdirSync(OUT, { recursive: true });
(async () => { const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  let ok = 0, bad = 0; const chk = (c, m) => { if (c) ok++; else bad++; console.log((c ? 'OK  ' : 'FAIL') + ' ' + m); };
  const page = async (save, lang) => { const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2, hasTouch: true, isMobile: true }); p.errs = []; p.on('pageerror', (e) => p.errs.push(e.message)); await p.addInitScript((sv) => localStorage.setItem('mud4.save', JSON.stringify(sv)), save); await p.goto('file://' + process.cwd() + '/dist/mud-side/index.html?' + (lang || 'ru')); await p.waitForFunction(() => window.__mud && window.__mud.S); await p.waitForTimeout(900); return p; };
  const sv = { coins: 184, own: {}, build: {}, stars: { village: 3 }, seen: { first: 1 }, ts: 1 };
  // 1) карточка второго заказа: кнопка сама покупает 4×4 и едет
  let p = await page(sv); const m = (f, a) => p.evaluate(f, a);
  await m(() => window.__mud.press('c:1')); await p.waitForTimeout(400); await p.screenshot({ path: OUT + '/1card.png' });
  await m(() => window.__mud.press('go')); await p.waitForTimeout(700);
  const g = await m(() => ({ mode: window.__mud.mode, awd: window.__mud.save.build.awd, coins: window.__mud.save.coins, own: (window.__mud.save.own.awd || []).length, cfg: window.__mud.S.cfg.b.awd }));
  chk(g.mode === 'play' && g.awd === 1 && g.coins === 34 && g.own === 1 && g.cfg === 1, 'одно нажатие «Купить 4×4 и в рейс»: купил за 150 и поехал ' + JSON.stringify(g));
  await p.screenshot({ path: OUT + '/2run.png' }); chk(p.errs.length === 0, 'ошибок нет ' + p.errs.join('; ')); await p.close();
  // 2) денег мало — кнопка прежняя: предупреждение, потом «Всё равно в рейс»
  p = await page(Object.assign({}, sv, { coins: 100 }));
  await p.evaluate(() => window.__mud.press('c:1')); await p.waitForTimeout(300); await p.evaluate(() => window.__mud.press('go')); await p.waitForTimeout(200);
  chk((await p.evaluate(() => window.__mud.mode)) === 'menu', 'без денег первое нажатие только предупреждает');
  await p.evaluate(() => window.__mud.press('go')); await p.waitForTimeout(500); chk((await p.evaluate(() => window.__mud.mode)) === 'play' && (await p.evaluate(() => window.__mud.save.coins)) === 100, 'второе нажатие — едет без покупки');
  await p.close();
  // 3) поехал «всё равно» без 4×4 (денег не хватало), по дороге деньги нашлись (старое сохранение) — завяз в грязи, экран аварии предлагает купить и заново
  p = await page(Object.assign({}, sv, { coins: 100 }));
  await p.evaluate(() => { const m = window.__mud; m.press('c:1'); m.press('go'); m.press('go'); }); await p.waitForTimeout(500);
  let died = await p.evaluate(() => { const m = window.__mud, S = m.S; m.save.coins = 184; for (let i = 0; i < 60 * 40 && S.state === 'play'; i++) S.step({ gas: true }); return Math.round(S.truck.x); });
  await p.keyboard.down('ArrowRight'); await p.waitForFunction(() => window.__mud.S.state === 'dead', null, { timeout: 120000 }).catch(() => 0); await p.keyboard.up('ArrowRight');
  const dd = await p.evaluate(() => ({ st: window.__mud.S.state, why: window.__mud.S.why, x: Math.round(window.__mud.S.truck.x), at: 0 })); dd.at = died; died = dd;
  chk(died.st === 'dead' && died.why === 'stuck', 'газ в пол без 4×4 — завяз, как тот игрок ' + JSON.stringify(died));
  await p.waitForFunction(() => window.__mud.buttons.some((q) => q.id === 'quit'), null, { timeout: 30000 }).catch(() => 0); await p.waitForTimeout(300); await p.screenshot({ path: OUT + '/3fail.png' });
  const f = await p.evaluate(() => ({ ids: window.__mud.buttons.map((q) => q.id) }));
  chk(f.ids.includes('buyre') && !f.ids.includes('tow'), 'на экране «Застрял» — «4×4 за 150 — и заново», без тягача к той же грязи: ' + f.ids);
  const ev = await p.evaluate(() => { window.__mud.press('buyre'); return 1; }); await p.waitForTimeout(600);
  const r = await p.evaluate(() => ({ mode: window.__mud.mode, st: window.__mud.S.state, awd: window.__mud.S.cfg.b.awd, coins: window.__mud.save.coins, x: Math.round(window.__mud.S.truck.x) }));
  chk(r.mode === 'play' && r.st === 'play' && r.awd === 1 && r.coins === 34, 'купил 4×4 и начал заново с начала ' + JSON.stringify(r));
  const pass = await p.evaluate(() => { const S = window.__mud.S; for (let i = 0; i < 60 * 120 && S.state === 'play'; i++) S.step({ gas: true, awd: true }); return { st: S.state, why: S.why }; });
  chk(pass.st === 'win', 'с 4×4 то же место проходит ' + JSON.stringify(pass));
  chk(p.errs.length === 0, 'ошибок нет ' + p.errs.join('; ')); await p.close();
  // 4) длинные подписи на других языках
  for (const lg of ['es', 'de', 'tr', 'pl']) { p = await page(sv, lg); await p.evaluate(() => window.__mud.press('c:1')); await p.waitForTimeout(300); await p.screenshot({ path: OUT + '/4card-' + lg + '.png' }); chk(p.errs.length === 0, lg + ' без ошибок'); await p.close(); }
  console.log(`итог: ${ok} OK, ${bad} FAIL`); await b.close(); process.exit(bad ? 1 : 0); })();
