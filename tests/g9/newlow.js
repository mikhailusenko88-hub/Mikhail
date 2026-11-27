// 3-й заказ: подсказка «Новая кнопка ПОНИЖ» не на старте (там дальше песок), а перед подъёмом; в песке ПОНИЖ не подсвечивается. Так застрял игрок 27.11
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => { const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 859, height: 237 } }); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); let ok = 0, bad = 0; const chk = (c, m) => { if (c) ok++; else bad++; console.log((c ? 'OK  ' : 'FAIL') + ' ' + m); };
  await p.addInitScript(() => localStorage.setItem('mud4.save', JSON.stringify({ coins: 94, own: { awd: [1], low: [1] }, build: { awd: 1, low: 1 }, stars: { village: 3, farm: 3 }, seen: { first: 1, awd: 1 }, tl: { awd: 1 }, ts: 1 })));
  await p.goto('file://' + process.cwd() + '/dist/mud-side/index.html?ru'); await p.waitForFunction(() => window.__mud && window.__mud.S); await p.waitForTimeout(800);
  await p.evaluate(() => { const m = window.__mud; m.press('c:2'); m.press('go'); m.press('go'); }); await p.waitForFunction(() => window.__mud.mode === 'play'); await p.waitForTimeout(1500);
  const h0 = await p.evaluate(() => window.__mud.hintText()); chk(!/Новая кнопка ПОНИЖ/.test(h0), 'на старте нет «Новая кнопка ПОНИЖ»: ' + h0);
  const up = await p.evaluate(() => { const S = window.__mud.S; const q = S.L.signs.find((s) => s.kind === 'climb' && s.val > 0); return q && q.x; });
  await p.evaluate((x) => { const S = window.__mud.S; S.cp = { x: x - 450, fuel: S.cfg.tank }; S.respawn(); window.__mud.sw.awd = true; }, up); await p.waitForTimeout(900);
  const h1 = await p.evaluate(() => window.__mud.hintText()); chk(/ПОНИЖ/.test(h1), 'перед подъёмом подсказка про ПОНИЖ: ' + h1);
  chk(errs.length === 0, 'ошибок нет ' + errs.join('; ')); console.log(`итог: ${ok} OK, ${bad} FAIL`); await b.close(); process.exit(bad ? 1 : 0); })();
