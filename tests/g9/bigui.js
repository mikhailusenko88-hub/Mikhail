// большие заказы в меню и аренда детали за ролик: вкладка, минимум груза, совет механика, «Нужно от N», ролик за недорогую деталь
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const fs = require('fs');
const [W, H] = (process.argv[2] || '859x237').split('x').map(Number), OUT = '/tmp/bigui/' + W + 'x' + H; fs.mkdirSync(OUT, { recursive: true });
const R1 = { village: 3, farm: 3, creek: 2, pit: 3, mill: 2, bog: 2 };
(async () => { const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  let ok = 0, bad = 0; const chk = (c, m) => { if (c) ok++; else bad++; console.log((c ? 'OK  ' : 'FAIL') + ' ' + m); };
  const page = async (save) => { const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2, hasTouch: true, isMobile: true }); p.errs = []; p.on('pageerror', (e) => p.errs.push(e.message)); await p.addInitScript((sv) => localStorage.setItem('mud4.save', JSON.stringify(sv)), save); await p.goto('file://' + process.cwd() + '/dist/mud-side/index.html?ru'); await p.waitForFunction(() => window.__mud && window.__mud.S); await p.waitForTimeout(900); return p; };
  const own = { awd: [1], low: [1], lock: [1], tires: [1], snorkel: [1], tank: [1], lift: [1] }, build = { awd: 1, low: 1, lock: 1, tires: 1, snorkel: 1, tank: 1, lift: 1 };
  // 1) район 1 пройден: вкладка больших заказов, лесовоз требует длинную раму
  let p = await page({ coins: 900, own, build, stars: R1, seen: { first: 1, awd: 1, lock: 1, low: 1 }, tl: { awd: 2, lock: 2, low: 2 }, ts: 1 });
  const m = (f, a) => p.evaluate(f, a);
  const ring = await m(() => window.__mud.buttons.some((q) => q.id === 'reg:3')); chk(ring, 'вкладка «Большие заказы» есть');
  await p.screenshot({ path: OUT + '/1menu.png' });
  await m(() => window.__mud.press('reg:3')); await p.waitForTimeout(400); await p.screenshot({ path: OUT + '/2big-list.png' });
  const lk = await m(() => ['c:18', 'c:19', 'c:20', 'c:22'].map((id) => { const m = window.__mud; m.press(id); const r = m.sel; m.press('unsel'); return r; })); chk(lk[0] === 18 && lk[1] === 19 && lk[2] === -1 && lk[3] === -1, 'после 1-го района открыты 2 больших заказа, остальные закрыты: ' + lk);
  await m(() => window.__mud.press('c:18')); await p.waitForTimeout(500); await p.screenshot({ path: OUT + '/3sawmill.png' });
  const t1 = await m(() => { const m = window.__mud; return { go: m.buttons.some((q) => q.id === 'adv'), sel: m.sel }; }); chk(t1.go, 'механик предлагает деталь для вместимости');
  await m(() => window.__mud.press('go')); await p.waitForTimeout(300); chk((await m(() => window.__mud.mode)) === 'menu', 'с короткой рамой в большой заказ не пускает');
  await m(() => window.__mud.press('adv')); await p.waitForTimeout(400); await p.screenshot({ path: OUT + '/4sawmill-bought.png' });
  const t2 = await m(() => { const m = window.__mud; return { base: m.save.build.base, coins: m.save.coins, load: m.S.cargo0 }; }); chk(t2.base === 1 && t2.coins === 300 && t2.load >= 11, 'купил длинную раму за 600, груз ' + t2.load);
  await m(() => window.__mud.press('lg-')); chk((await m(() => window.__mud.S.cargo0)) >= 11, 'меньше минимума не убавить');
  await m(() => window.__mud.press('go')); await p.waitForTimeout(600); chk((await m(() => window.__mud.mode)) === 'play', 'с длинной рамой поехал');
  chk(p.errs.length === 0, 'ошибок нет ' + p.errs.join('; ')); await p.close();
  // 2) аренда: 4-й заказ, нет денег на блокировку — ролик ставит её на один рейс
  p = await page({ coins: 100, own: { awd: [1], low: [1] }, build: { awd: 1, low: 1 }, stars: { village: 3, farm: 3, creek: 2 }, seen: { first: 1, awd: 1, low: 1 }, tl: { awd: 2, low: 2 }, ts: 1 });
  const m2 = (f) => p.evaluate(f);
  await m2(() => window.__mud.press('c:3')); await p.waitForTimeout(500); await p.screenshot({ path: OUT + '/5rent-card.png' });
  chk(await m2(() => window.__mud.buttons.some((q) => q.id === 'rent')), 'есть кнопка «Ролик: деталь на один рейс»');
  await m2(() => window.__mud.press('rent')); await p.waitForTimeout(400);
  const r1 = await m2(() => ({ adv: window.__mud.buttons.some((q) => q.id === 'adv' || q.id === 'rent'), lock: window.__mud.S.cfg.b.lock, saved: window.__mud.save.build.lock || 0 })); chk(r1.lock === 1 && !r1.saved, 'после ролика блокировка стоит на грузовике, в сохранение не записана');
  await p.screenshot({ path: OUT + '/6rent-done.png' });
  await m2(() => window.__mud.press('go')); await p.waitForTimeout(200); await m2(() => window.__mud.press('go')); await p.waitForTimeout(800); const r2 = await m2(() => ({ mode: window.__mud.mode, lock: window.__mud.S.cfg.b.lock, btn: window.__mud.buttons.some((q) => q.id === 'lock') })); chk(r2.mode === 'play' && r2.lock === 1 && r2.btn, 'в рейсе кнопка БЛОК есть');
  await p.screenshot({ path: OUT + '/7rent-run.png' });
  await m2(() => { window.__mud.press('pause'); window.__mud.press('quit'); }); await p.waitForTimeout(500); await m2(() => window.__mud.press('c:3')); await p.waitForTimeout(300);
  chk((await m2(() => window.__mud.S.cfg.b.lock)) === 0, 'бросил рейс — аренда кончилась');
  chk(p.errs.length === 0, 'ошибок нет ' + p.errs.join('; '));
  console.log(`итог: ${ok} OK, ${bad} FAIL`); await b.close(); process.exit(bad ? 1 : 0); })();
