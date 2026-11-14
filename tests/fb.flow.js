// Flagball: три игрока (телефон по-русски, ноутбук 907×510 по-английски, телефон по-английски)
// смерть → возрождение за рекламу → вторая смерть → x2 → магазин → раунд стран
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const OUT = '/home/claude/games/tests/shots/';
const URL = 'http://localhost:8770/index.html';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
  const errs = [];
  async function mk(view, locale, mobile, qs) {
    const ctx = await b.newContext({ viewport: view, locale, hasTouch: mobile, isMobile: mobile, deviceScaleFactor: mobile ? 2 : 1 });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => errs.push(locale + ' PAGEERR ' + e.message));
    p.on('console', (m) => { if (m.type() === 'error' && !/404|favicon/.test(m.text())) errs.push(locale + ' ' + m.text()); });
    await p.goto(URL + (qs || '')); await p.waitForTimeout(700);
    return p;
  }
  const A = await mk({ width: 390, height: 844 }, 'ru-RU', true, '');
  await A.screenshot({ path: OUT + 'fb_join_ru.png' });
  await A.fill('#nick', 'Миша'); await A.click('#flags img[alt="KZ"]'); await A.click('#go');
  const Bp = await mk({ width: 907, height: 510 }, 'en-US', false, '?auto');
  const Cp = await mk({ width: 390, height: 844 }, 'en-US', true, '?auto');
  await A.waitForTimeout(2500);
  for (const [p, n] of [[A, 'ru_play'], [Bp, 'en_land_play'], [Cp, 'en_play']]) await p.screenshot({ path: OUT + 'fb_' + n + '.png' });
  const st = async (p) => p.evaluate(() => { const d = __dbgOnline(); return { status: d.status, id: d.myId, alive: d.me.alive, m: Math.round(d.me.m), coins: d.coins, dead: d.dead && { offer: d.dead.offer, coins: d.dead.coins, best: d.dead.best }, cs: d.cs, rt: Math.round(d.rt), W: Math.round(Core.W), H: Math.round(Core.H), lang: Core.lang }; });
  console.log('A', JSON.stringify(await st(A))); console.log('B', JSON.stringify(await st(Bp)));

  // B — большой, едет на A; A — 60 (будет предложение «вернуться»)
  async function ensureAlive(p) { if (!(await p.evaluate(() => __dbgOnline().me.alive))) { await p.evaluate(() => { const d = __dbgOnline().dead; if (d) d.t = 9; __respawn(); }); await p.waitForTimeout(1800); } }
  async function kill(victim, hunter, vm) {
    await ensureAlive(victim); await ensureAlive(hunter);
    await victim.evaluate((vm) => __send({ t: 'dbg', m: vm }), vm);
    await hunter.evaluate(() => __send({ t: 'dbg', m: 400 }));
    await victim.waitForTimeout(4200); // щит после появления
    await victim.evaluate((vm) => __send({ t: 'dbg', m: vm }), vm);
    await victim.waitForTimeout(400);
    const vp = await victim.evaluate(() => ({ x: __dbgOnline().me.x, y: __dbgOnline().me.y }));
    await hunter.evaluate((vp) => __send({ t: 'dbg', x: vp.x + 30, y: vp.y }), vp);
    for (let i = 0; i < 20; i++) { await victim.waitForTimeout(250); if (!(await victim.evaluate(() => __dbgOnline().me.alive))) return true; }
    return false;
  }
  console.log('kill1', await kill(A, Bp, 60));
  await A.waitForTimeout(900);
  await A.screenshot({ path: OUT + 'fb_death_revive_ru.png' });
  console.log('A dead', JSON.stringify(await st(A)));
  const info = await A.evaluate(() => ({ s: Core.scale, W: Core.W, H: Core.H }));
  const rect = async (p, id) => p.evaluate((id) => { const r = Core.UI.rects.find((q) => q.id === id); return r ? { x: (r.x + r.w / 2) * Core.scale, y: (r.y + r.h / 2) * Core.scale } : null; }, id);
  const tap = async (p, id) => { const r = await rect(p, id); if (!r) return false; await p.mouse.click(r.x, r.y); return true; };
  console.log('tap revAd', await tap(A, 'revAd'));
  await A.waitForTimeout(600); await A.screenshot({ path: OUT + 'fb_mockad_ru.png' });
  await A.waitForTimeout(4500);
  console.log('A after revive', JSON.stringify(await st(A)));
  await A.screenshot({ path: OUT + 'fb_revived_ru.png' });

  // вторая смерть — теперь «x2»
  console.log('kill2', await kill(A, Bp, 80));
  await A.waitForTimeout(900);
  console.log('A dead2', JSON.stringify(await st(A)));
  await A.screenshot({ path: OUT + 'fb_death_x2_ru.png' });
  const c0 = (await st(A)).coins; console.log('tap dblAd', await tap(A, 'dblAd')); await A.waitForTimeout(5000);
  console.log('coins before/after x2', c0, (await st(A)).coins);
  await A.screenshot({ path: OUT + 'fb_after_x2_ru.png' });
  const g0 = (await st(A)).coins; console.log('tap gift', await tap(A, 'giftBtn')); await A.waitForTimeout(1500);
  console.log('gift coins', g0, (await st(A)).coins, JSON.stringify(await A.evaluate(() => __dbgOnline().fb)));
  await A.screenshot({ path: OUT + 'fb_gift_ru.png' });
  // магазин
  await A.evaluate(() => { Core.save.coins = 700; Core.coinsShown = 700; });
  console.log('tap shop', await tap(A, 'shopBtn')); await A.waitForTimeout(400);
  await tap(A, 'acc11'); await A.waitForTimeout(300); await tap(A, 'acc1'); await A.waitForTimeout(300);
  await A.screenshot({ path: OUT + 'fb_shop_ru.png' });
  console.log('fb', JSON.stringify(await A.evaluate(() => __dbgOnline().fb)), 'coins', await A.evaluate(() => Core.save.coins));
  await tap(A, 'acc11'); await A.waitForTimeout(200);
  await tap(A, 'shopClose'); await A.waitForTimeout(300);
  console.log('tap again', await tap(A, 'again')); await A.waitForTimeout(2500);
  console.log('A again', JSON.stringify(await st(A)));

  // смерть игрока на ноутбуке (альбом 907×510)
  console.log('kill3', await kill(Bp, Cp, 50)); await Bp.waitForTimeout(900);
  await Bp.screenshot({ path: OUT + 'fb_death_land_en.png' });
  console.log('B dead', JSON.stringify(await st(Bp)));
  await tap(Bp, 'shopBtn'); await Bp.waitForTimeout(400); await Bp.screenshot({ path: OUT + 'fb_shop_land_en.png' }); await tap(Bp, 'shopClose');
  await tap(Bp, 'again'); await Bp.waitForTimeout(1500);

  // ждём конец раунда (ROUND_LEN=25 на тестовом сервере)
  for (let i = 0; i < 60; i++) { await Cp.waitForTimeout(500); if (await Cp.evaluate(() => __dbgOnline().banner)) break; }
  await Cp.waitForTimeout(500);
  await Cp.screenshot({ path: OUT + 'fb_round_en.png' }); await A.screenshot({ path: OUT + 'fb_round_ru.png' }); await Bp.screenshot({ path: OUT + 'fb_round_land.png' });
  console.log('C', JSON.stringify(await st(Cp)));
  console.log('day', JSON.stringify(await Cp.evaluate(() => __dbgOnline().dayTopL)));
  console.log('ERRORS:', errs.join('\n') || 'none');
  await b.close();
})();
