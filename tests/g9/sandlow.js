// песок с ПОНИЖ: игра не включает ПОНИЖ сама, подсказка велит выключить; лебёдка без дерева скрыта и объясняет
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
(async () => { const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 859, height: 237 } }); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); let ok = 0, bad = 0; const chk = (c, m) => { if (c) ok++; else bad++; console.log((c ? 'OK  ' : 'FAIL') + ' ' + m); };
  await p.addInitScript(() => localStorage.setItem('mud4.save', JSON.stringify({ coins: 900, own: { awd: [1], low: [1] }, build: { awd: 1, low: 1 }, stars: { village: 3, farm: 2 }, seen: { first: 1, awd: 1, low: 1 }, tl: { awd: 2, low: 0 }, ts: 1 })));
  await p.goto('file://' + process.cwd() + '/dist/mud-side/index.html?ru'); await p.waitForFunction(() => window.__mud && window.__mud.S); await p.waitForTimeout(800);
  await p.evaluate(() => { const m = window.__mud; m.press('c:2'); m.press('go'); });
  await p.waitForFunction(() => window.__mud.mode === 'play'); await p.waitForTimeout(600);
  const z = await p.evaluate(() => { const S = window.__mud.S, z = S.L.mud.find((q) => q.z && q.z.t === 'sand' || q.t === 'sand'); return z ? { x0: z.x0, x1: z.x1 } : null; });
  chk(!!z, 'на трассе 3-го заказа есть песок ' + JSON.stringify(z));
  // въехать в песок медленно: поставить грузовик в середину песка, ПОНИЖ выключена
  await p.evaluate((z) => { const m = window.__mud, S = m.S; S.cp = { x: z.x0 + 150, fuel: S.cfg.tank }; S.respawn(); m.sw.low = false; m.sw.awd = true; }, z);
  await p.waitForTimeout(700); await p.keyboard.down('ArrowRight');
  let lowOn = false, txt = new Set(); for (let i = 0; i < 40; i++) { await p.waitForTimeout(250); const r = await p.evaluate(() => ({ low: window.__mud.sw.low, soil: window.__mud.S.soil, h: window.__mud.hintText ? window.__mud.hintText() : '' })); if (r.soil === 'sand' && r.low) lowOn = true; if (r.h) txt.add(r.h.slice(0, 40)); }
  await p.keyboard.up('ArrowRight');
  chk(!lowOn, 'в песке игра сама ПОНИЖ не включила');
  // ПОНИЖ включена в песке и буксует — подсказка про ПОНИЖ
  const h2 = await p.evaluate(() => { const m = window.__mud; m.sw.low = true; m.S.stuckT = 2; m.S.soil = 'sand'; return m.hintText(); });
  chk(/выключи ПОНИЖ/.test(h2), 'подсказка в песке с ПОНИЖ: ' + h2);
  // лебёдка: на старте 3-го заказа деревьев нет — кнопки нет, нажатие объясняет
  const wb = await p.evaluate(() => window.__mud.buttons.some((b) => b.id === 'winch'));
  console.log('подсказки по пути:', [...txt].join(' | '));
  chk(errs.length === 0, 'ошибок нет ' + errs.join('; '));
  console.log(`итог: ${ok} OK, ${bad} FAIL`); await b.close(); process.exit(bad ? 1 : 0); })();
