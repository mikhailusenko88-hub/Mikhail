// «Mud Haul» как на площадке: заглушка моста Playgama (tests/g8/pgstub.js) вместо настоящего. Проверяет: game_ready и сразу рейс у новичка;
// язык с площадки (8 языков + запасной английский); облачное сохранение; отметки progression_* / crash / assist / part_bought / performance_sample;
// межстраничная — не после обучающих заказов, не раньше 4 минут, не чаще раза в 3 минуты; награда только после «досмотрел»; пауза площадки останавливает мир;
// без поддержки роликов кнопок «за ролик» нет. node tests/g9/pgmud.js
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/mud-pg'), STUB = fs.readFileSync(path.resolve(__dirname, '../g8/pgstub.js'), 'utf8');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); const res = []; const ok = (c, m) => res.push((c ? 'OK   ' : 'FAIL ') + m);
  const open = async (o = {}) => { const ctx = await b.newContext({ viewport: { width: 844, height: 390 }, deviceScaleFactor: 1, locale: o.locale || 'en-US', hasTouch: true, isMobile: true });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: STUB }));
    const p = await ctx.newPage(); p.errs = []; p.reqs = []; p.on('pageerror', (e) => p.errs.push(e.message)); p.on('request', (r) => p.reqs.push(r.url().split('/').pop()));
    await p.addInitScript((o) => { if (o.lang) window.__pgLang = o.lang; if (o.audioOff) window.__pgAudio = false; const sv = o.save || o.cloud; if (sv) window.__pgStore0 = { 'mud4.save': JSON.stringify(sv) }; if (o.local) localStorage.setItem('mud4.save', JSON.stringify(o.local)); if (o.noRew) { const t = setInterval(() => { if (window.bridge) { window.bridge.advertisement.isRewardedSupported = false; clearInterval(t); } }, 1); } }, o);
    await p.goto('file://' + DIR + '/index.html'); await p.waitForFunction(() => window.__mud && window.__mud.S); await p.waitForTimeout(1500); return [ctx, p]; };
  const ev = (p, n) => p.evaluate((n) => window.__pg.ev.filter((q) => q[0] === n).map((q) => q[1]), n);
  const DONE4 = { coins: 900, own: { awd: [1], low: [1], lock: [1], tires: [1], lift: [1] }, build: { awd: 1, low: 1, lock: 1, tires: 1, lift: 1 }, stars: { village: 3, farm: 3, creek: 3, pit: 3 }, seen: { first: 1, awd: 1, low: 1, lock: 1 }, tl: { awd: 2, low: 2, lock: 2 }, ts: 1 };
  { // новичок
    const [ctx, p] = await open(); const s = await p.evaluate(() => ({ mode: window.__mud.mode, msgs: window.__pg.msgs.slice(), ver: window.__pg.ver, cur: window.__mud.cur, load: window.__mud.S.cargo0 }));
    ok(s.msgs.includes('game_ready') && s.mode === 'play' && s.cur === 0, 'новичок: game_ready и сразу рейс 1 — ' + JSON.stringify(s)); ok(s.ver === '6.5', 'номер сборки передан мосту: ' + s.ver); ok(s.load === 7, 'первый рейс — полный кузов: ' + s.load);
    const st = (await ev(p, 'progression_started'))[0]; ok(st && st.step_id === 'C01' && st.first_run === true, 'progression_started C01, first_run — ' + JSON.stringify(st));
    await p.keyboard.down('ArrowRight'); await p.waitForFunction(() => window.__mud.mode === 'win', null, { timeout: 60000 }); await p.keyboard.up('ArrowRight'); await p.waitForFunction(() => window.__mud.buttons.some((q) => q.id === 'menu'), null, { timeout: 20000 }); await p.waitForTimeout(300);
    const pc = (await ev(p, 'progression_completed'))[0]; ok(pc && pc.step_id === 'C01' && pc.delivered === 7 && pc.first_time === true, 'progression_completed C01 — ' + JSON.stringify(pc && { d: pc.delivered, e: pc.earned, a: pc.assists, t: pc.duration_sec }));
    const ids = await p.evaluate(() => window.__mud.buttons.map((q) => q.id)); ok(ids.includes('nextc') && !ids.includes('x2'), 'итог первого заказа: «Дальше», без «×2 за ролик» — ' + ids.join(','));
    await p.evaluate(() => window.__mud.press('nextc')); await p.waitForTimeout(400); const mid = await p.evaluate(() => ({ mode: window.__mud.mode, ad: window.__mud.pg.ad })); await p.waitForTimeout(1200);
    const s2 = await p.evaluate(() => ({ mode: window.__mud.mode, sel: window.__mud.sel, ads: window.__pg.ads.slice() })); ok(mid.mode === 'win' && mid.ad && s2.mode === 'menu' && s2.sel === 1 && s2.ads.join() === 'inter:contract_end', '«Дальше»: межстраничную решает мост, игра ждёт её конца, потом карточка заказа 2 — ' + JSON.stringify([mid, s2]));
    ok((await p.evaluate(() => localStorage.getItem('mud4.save'))) === null, 'в память браузера ничего не пишет — только облако площадки');
    await p.evaluate(() => window.__mud.press('adv')); await p.waitForTimeout(200); const pb = (await ev(p, 'part_bought'))[0]; ok(pb && pb.part === 'awd' && pb.where === 'mechanic' && pb.step_id === 'C02', 'покупка у механика — part_bought ' + JSON.stringify(pb));
    const cloud = await p.evaluate(() => JSON.parse(window.__pg.store['mud4.save'] || '{}')); ok(cloud.stars && cloud.stars.village > 0 && cloud.own && cloud.own.awd, 'сохранение ушло в облако площадки');
    ok(!p.errs.length, 'ошибок нет' + (p.errs[0] ? ': ' + p.errs[0] : '')); await ctx.close();
  }
  { // прогресс в облаке площадки; в памяти браузера — чужое старое сохранение, его не трогаем; звук площадка выключила; язык браузера немецкий, площадки — испанский
    const [ctx, p] = await open({ cloud: DONE4, local: { coins: 5, build: {}, stars: {} }, audioOff: true, lang: 'es' }); const s = await p.evaluate(() => ({ mode: window.__mud.mode, coins: window.__mud.save.coins, stars: Object.keys(window.__mud.save.stars).length, muted: window.__mud.pg.mutedP }));
    ok(s.mode === 'menu' && s.coins === 900 && s.stars === 4, 'прогресс из облака площадки, не из памяти браузера — ' + JSON.stringify(s)); ok(s.muted, 'площадка выключила звук при запуске — игра молчит');
    const order = p.reqs.filter((n) => /\.js$/.test(n)); ok(order[0] === 'playgama-bridge.js' && order.indexOf('view2d.js') > order.indexOf('boot-pg.js'), 'мост грузится первым, игра — после него: ' + order.join(','));
    await p.evaluate(() => { window.__mud.press('c:4'); window.__mud.press('go'); }); await p.waitForTimeout(300); await p.keyboard.press('Escape'); await p.waitForTimeout(200); ok(!(await p.evaluate(() => window.__mud.paused)), 'Esc не ставит паузу (им браузер выходит из полного экрана)'); await ctx.close();
  }
  { // языки
    for (const [lg, want] of [['es', 'Encargos'], ['pt-BR', 'Pedidos'], ['tr', 'Siparişler'], ['de', 'Aufträge'], ['fr', 'Commandes'], ['it', 'Incarichi'], ['pl', 'Zlecenia'], ['id', 'Pesanan'], ['ru', 'Заказы'], ['ja', 'Contracts']]) {
      const [ctx, p] = await open({ lang: lg, save: DONE4 }); await p.addInitScript(() => {}); const t = await p.evaluate(() => { const out = []; const f = CanvasRenderingContext2D.prototype.fillText; CanvasRenderingContext2D.prototype.fillText = function (s, ...a) { out.push(String(s)); return f.call(this, s, ...a); }; return new Promise((r) => setTimeout(() => { CanvasRenderingContext2D.prototype.fillText = f; r(out); }, 600)); });
      const bad = t.filter((q) => /undefined|NaN|\[object/.test(q)); ok(t.some((q) => q.includes(want)) && !bad.length, `язык ${lg}: «${want}» в меню${bad.length ? ', ПУСТЫЕ: ' + bad.slice(0, 3).join(' | ') : ''}`);
      if (lg === 'de') { await p.evaluate(() => window.__mud.press('c:4')); await p.waitForTimeout(500); await p.screenshot({ path: '/tmp/pgmud-de-card.png' }); }
      await ctx.close(); }
  }
  { // межстраничная и награды: прогресс после обучения
    const [ctx, p] = await open({ save: DONE4 });
    const run = async (ci, since, gap) => { await p.evaluate(([ci, since, gap]) => { const g = window.__mud.pg, now = performance.now() / 1000; g.t0 = (now - since) * 1000; g.lastInter = now - gap; g.lastRew = -1e9; window.__pg.ads.length = 0; window.__mud.press('c:' + ci); window.__mud.press('go'); }, [ci, since, gap]); await p.waitForTimeout(300);
      await p.evaluate(() => { const S = window.__mud.S; S.truck.x = S.L.fin + 200; }); await p.waitForFunction(() => window.__mud.mode === 'win' && window.__mud.res, null, { timeout: 15000 }).catch(() => {}); await p.waitForTimeout(1500);
      await p.evaluate(() => window.__mud.press('menu')); await p.waitForTimeout(300); const a = await p.evaluate(() => window.__pg.ads.join(',')); await p.waitForTimeout(1200); return a; };
    const a1 = await run(4, 100, 1e9); ok(/inter:contract_end/.test(a1), 'после заказа — просьба мосту о межстраничной: ' + a1);
    await p.evaluate(() => { window.__silent = window.bridge.advertisement.showInterstitial; window.bridge.advertisement.showInterstitial = (q) => { window.__pg.ads.push('inter-silent:' + q); }; });
    await run(4, 100, 1e9); const st = await p.waitForFunction(() => window.__mud.mode === 'menu', null, { timeout: 4000 }).then(() => 'menu').catch(() => p.evaluate(() => window.__mud.mode)); ok(st === 'menu', 'мост промолчал (рано для рекламы) — игра не зависает, уходит в меню');
    await p.evaluate(() => { window.bridge.advertisement.showInterstitial = window.__silent; });
    // ×2 за ролик: досмотрел — двойная оплата; не загрузился — ничего
    await p.evaluate(() => { const g = window.__mud.pg; g.t0 = performance.now(); window.__mud.press('c:4'); window.__mud.press('go'); }); await p.waitForTimeout(300); await p.evaluate(() => { const S = window.__mud.S; S.truck.x = S.L.fin + 200; }); await p.waitForFunction(() => window.__mud.mode === 'win' && window.__mud.res, null, { timeout: 15000 }); await p.waitForTimeout(1500);
    const c0 = await p.evaluate(() => window.__mud.save.coins), tot = await p.evaluate(() => window.__mud.res.total); await p.evaluate(() => { window.__adMode = 'fail'; window.__mud.press('x2'); }); await p.waitForTimeout(800); const c1 = await p.evaluate(() => window.__mud.save.coins);
    await p.evaluate(() => { window.__adMode = ''; window.__mud.press('x2'); }); await p.waitForTimeout(400); const mid = await p.evaluate(() => ({ ad: window.__mud.pg.ad, t: window.__mud.S.t })); await p.waitForTimeout(1200); const c2 = await p.evaluate(() => window.__mud.save.coins);
    ok(c1 === c0 && c2 === c0 + tot && mid.ad, `×2: ролик не загрузился — монет столько же (${c0}→${c1}); досмотрел — +${tot} (${c2}); во время ролика игра знает, что идёт реклама`);
    // пауза площадки: мир стоит
    await p.evaluate(() => window.__mud.press('again')); await p.waitForTimeout(300); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(700); const x0 = await p.evaluate(() => { window.__pgEmit('pause_state_changed', true); return window.__mud.S.truck.x; }); await p.waitForTimeout(800);
    const x1 = await p.evaluate(() => window.__mud.S.truck.x); await p.evaluate(() => window.__pgEmit('pause_state_changed', false)); await p.waitForFunction((x1) => window.__mud.S.truck.x > x1 + 20, x1, { timeout: 8000 }).catch(() => {}); const x2 = await p.evaluate(() => window.__mud.S.truck.x); await p.keyboard.up('ArrowRight');
    ok(Math.abs(x1 - x0) < 25 && x2 > x1 + 20, `пауза площадки останавливает рейс: ${Math.round(x0)} → ${Math.round(x1)} → после паузы ${Math.round(x2)}`);
    // авария: отметка crash, бросил рейс: progression_failed
    await p.evaluate(() => { window.__mud.S.fuel = 0; }); await p.waitForFunction(() => window.__mud.S.state === 'dead' && window.__mud.S.deadT > 1, null, { timeout: 30000 }); await p.waitForTimeout(300); await p.evaluate(() => window.__mud.press('quit')); await p.waitForTimeout(300);
    const cr = (await ev(p, 'crash')).pop(), pf = (await ev(p, 'progression_failed')).pop(); ok(cr && cr.reason === 'fuel' && cr.step_id === 'C05', 'crash с причиной и шагом — ' + JSON.stringify(cr && { r: cr.reason, s: cr.step_id, x: cr.x_m })); ok(pf && pf.how === 'menu' && pf.step_id === 'C05', 'бросил рейс — progression_failed how=menu');
    ok(!p.errs.length, 'ошибок нет' + (p.errs[0] ? ': ' + p.errs[0] : '')); await ctx.close();
  }
  { // площадка не показывает ролики — кнопок «за ролик» нет
    const [ctx, p] = await open({ save: DONE4, noRew: true }); await p.evaluate(() => { window.__mud.press('c:4'); window.__mud.press('go'); }); await p.waitForTimeout(300); await p.evaluate(() => { window.__mud.S.fuel = 0; }); await p.waitForFunction(() => window.__mud.S.state === 'dead' && window.__mud.S.deadT > 1, null, { timeout: 30000 }); await p.waitForTimeout(300);
    const ids = await p.evaluate(() => window.__mud.buttons.map((q) => q.id)); ok(!ids.includes('towad') && ids.includes('tow'), 'без роликов: на экране аварии нет «бесплатного тягача за ролик» — ' + ids.join(',')); await ctx.close();
  }
  await b.close(); console.log(res.join('\n')); const f = res.filter((r) => r.startsWith('FAIL')).length; console.log(f ? `ПРОВАЛОВ: ${f}` : `всё в порядке (${res.length})`); process.exit(f ? 1 : 0);
})();
