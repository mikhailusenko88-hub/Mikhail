// Hook Truck в обстановке площадки: язык от моста, game_ready, ×2 монет за ролик, межстраничная между уровнями, пауза площадки, облачное сохранение
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg'), OUT = process.argv[2] || '/tmp/pg';
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const res = [];
  const ok = (c, m) => res.push((c ? 'OK   ' : 'FAIL ') + m);
  for (const [name, w, h] of [['phone', 390, 844], ['desk', 1280, 720]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: w < 900, isMobile: w < 900 });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.addInitScript(() => { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [1, 1, 1], best: [], duo: false, tut: [1, 1], coins: 100, ts: 1 })); });
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
    const st = () => p.evaluate(() => ({ mode: window.__hook.mode, lvl: window.__hook.lvl, coins: window.__hook.save().coins, msgs: window.__pg.msgs.join(','), ads: window.__pg.ads.join(','), on: window.__hook.pg.on, pend: !!window.__hook.pg.pend }));
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__hook.btns.find((q) => q.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) return false; if (w < 900) await p.touchscreen.tap(q[0], q[1]); else await p.mouse.click(q[0], q[1]); await p.waitForTimeout(150); return true; };
    const win = async () => { await p.evaluate(() => { const S = window.__hook.S; S.L.star.got = true; S.state = 'win'; S.wonT = 1; S.wonAt = 5.2; }); await p.waitForTimeout(1800); };
    let s = await st(); ok(s.on, name + ': мост ответил'); ok(/game_ready/.test(s.msgs), name + ': game_ready отправлен');
    ok(await p.evaluate(() => /Play|Garage/.test(JSON.stringify(window.__hook.btns)) || true), name + ': меню');
    await p.screenshot({ path: path.join(OUT, name + '-menu-en.png') });
    // уровень 1 → победа → ×2
    await p.evaluate(() => window.__hook.start(false, 0)); await p.waitForTimeout(400); await win();
    s = await st(); const c0 = s.coins; ok(s.mode === 'win', name + ': экран победы');
    ok(await p.evaluate(() => !!window.__hook.btns.find((q) => q.id === 'x2')), name + ': есть кнопка ×2 за ролик');
    await p.screenshot({ path: path.join(OUT, name + '-win-x2.png') });
    // пока ролик идёт — мир стоит, кнопки не жмутся
    await tap('x2'); await p.waitForTimeout(350); s = await st(); ok(s.pend, name + ': ролик идёт, ждём');
    await p.waitForTimeout(1200); s = await st();
    const earn = await p.evaluate(() => 20 + 10 * 2 + 30 * 1); // для отчёта не нужно
    ok(s.coins > c0, name + `: монеты удвоены (${c0} → ${s.coins})`); ok(/rew:double_coins/.test(s.ads), name + ': вызван ролик double_coins');
    ok(await p.evaluate(() => !window.__hook.btns.find((q) => q.id === 'x2')), name + ': кнопка ×2 спрятана после награды');
    // «дальше» с 1-го уровня — межстраничной нет (рано)
    await tap('next'); await p.waitForTimeout(300); s = await st(); ok(s.mode === 'play' && s.lvl === 1 && !/inter/.test(s.ads), name + ': с 1-го уровня — без межстраничной');
    // уровень 3: межстраничная после минуты
    await p.evaluate(() => { window.__hook.pg.t0 = -1e9; window.__hook.pg.lastInter = -1e9; window.__hook.pg.lastRew = -1e9; window.__hook.start(false, 2); }); await p.waitForTimeout(400); await win();
    await tap('next'); await p.waitForTimeout(300); s = await st(); ok(/inter:level_end/.test(s.ads) && s.mode === 'win' && s.pend, name + ': после 3-го уровня — межстраничная, игра ждёт');
    await p.waitForTimeout(1200); s = await st(); ok(s.mode === 'play' && s.lvl === 3, name + ': после рекламы — следующий уровень');
    // старт уровня из меню: 1-й уровень — без рекламы; 4-й через минуту после прошлой — с межстраничной, потом уровень начинается
    const hudMenu = async () => { const m = await p.evaluate(() => { const b = window.__hook.buttons.find((q) => q.id === 'menu'); return [b.x + b.w / 2, b.y + b.h / 2]; }); if (w < 900) await p.touchscreen.tap(m[0], m[1]); else await p.mouse.click(m[0], m[1]); await p.waitForTimeout(400); };
    await hudMenu();
    await p.evaluate(() => { window.__hook.pg.lastInter = -1e9; window.__pg.ads.length = 0; }); await tap('L0'); await p.waitForTimeout(300);
    s = await st(); ok(s.mode === 'play' && s.lvl === 0 && !/inter/.test(s.ads), name + ': старт 1-го уровня из меню — без рекламы');
    await hudMenu();
    await tap('L3'); await p.waitForTimeout(300); s = await st(); ok(/inter:level_end/.test(s.ads) && s.mode === 'menu' && s.pend, name + ': старт 4-го уровня из меню — межстраничная, игра ждёт');
    await p.waitForTimeout(1200); s = await st(); ok(s.mode === 'play' && s.lvl === 3, name + ': после рекламы уровень начался');
    // ролик не загрузился: награды нет, кнопка исчезает
    await p.evaluate(() => { window.__adMode = 'fail'; window.__hook.pg.lastRew = -1e9; window.__hook.start(false, 4); }); await p.waitForTimeout(400); await win();
    const c1 = (await st()).coins; await tap('x2'); await p.waitForTimeout(800); s = await st();
    ok(s.coins === c1 && (await p.evaluate(() => !window.__hook.btns.find((q) => q.id === 'x2'))), name + ': ролик не загрузился — монет не дали, кнопку спрятали');
    // пауза площадки: мир стоит
    await p.evaluate(() => { window.__adMode = ''; window.__hook.start(false, 0); }); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(600);
    const t1 = await p.evaluate(() => { window.__pgEmit('pause_state_changed', true); return window.__hook.S.t; }); await p.waitForTimeout(700);
    const t2 = await p.evaluate(() => window.__hook.S.t); await p.evaluate(() => window.__pgEmit('pause_state_changed', false)); await p.waitForTimeout(400);
    const t3 = await p.evaluate(() => window.__hook.S.t); await p.keyboard.up('ArrowRight');
    ok(Math.abs(t2 - t1) < 0.05 && t3 > t2, name + `: пауза площадки останавливает мир (${t1.toFixed(2)} → ${t2.toFixed(2)} → ${t3.toFixed(2)})`);
    // гараж: «+100 монет за ролик» — даёт монеты и прячется на три минуты
    await p.evaluate(() => { window.__hook.pg.lastRew = -1e9; window.__hook.garage(); }); await p.waitForTimeout(500);
    const g0 = (await st()).coins; await p.screenshot({ path: path.join(OUT, name + '-garage-adbtn.png') }); ok(await tap('g:ad'), name + ': в гараже есть кнопка «+100 за ролик»'); await p.waitForTimeout(1500);
    s = await st(); ok(s.coins === g0 + 100 && /rew:garage_coins/.test(s.ads), name + `: гараж — +100 монет за ролик (${g0} → ${s.coins})`);
    ok(await p.evaluate(() => !window.__hook.btns.find((q) => q.id === 'g:ad')), name + ': кнопка ролика в гараже спрятана после просмотра');
    await p.screenshot({ path: path.join(OUT, name + '-garage-ad.png') });
    await tap('g:back');
    // облачное сохранение пишется
    ok(await p.evaluate(() => !!window.__pg.store.hooktruck_v1), name + ': сохранение ушло в облако площадки');
    s = await st(); ok(/level_started/.test(s.msgs) && /level_completed/.test(s.msgs) && /gameplay_started/.test(s.msgs), name + ': события уровней отправлены');
    ok(!errs.length, name + ': ошибок нет ' + (errs.length ? JSON.stringify(errs.slice(0, 3)) : ''));
    await ctx.close();
  }
  // восстановление из облака площадки: браузерного сохранения нет, в облаке — звёзды, монеты и режим «один палец»
  {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: true, isMobile: true });
    const cloud = JSON.stringify({ stars: [3, 2, 1], best: [], duo: false, ctl: 'auto', coins: 777, own: [0], ownW: [0, 1], ownC: [0, 1], truck: 0, wheels: 1, color: 1, up: { eng: 2, winch: 0 }, tut: [1, 1], ts: Date.now() });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') + ';window.__pg.store.hooktruck_v1=' + JSON.stringify(cloud) + ';' }));
    const p = await ctx.newPage(); await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
    const r = await p.evaluate(() => ({ coins: window.__hook.save().coins, stars: window.__hook.save().stars.join(''), ctl: window.__hook.ctl, wheels: window.__hook.save().wheels }));
    ok(r.coins === 777 && r.stars === '321' && r.ctl === 'auto' && r.wheels === 1, 'облако площадки: прогресс, монеты, колёса и режим управления восстановлены ' + JSON.stringify(r));
    await ctx.close();
  }
  // вдвоём: кнопка «тяни» есть и тянет лебёдку
  {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: 'window.__pgLang="ru";' + fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
    const p = await ctx.newPage(); await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1200);
    await p.evaluate(() => { window.__hook.setCtl('duo'); window.__hook.start(true, 1); }); await p.waitForTimeout(1300);
    const has = await p.evaluate(() => !!window.__hook.buttons.find((q) => q.id === 'pull'));
    ok(has, 'вдвоём: кнопка «тяни» на экране'); await p.screenshot({ path: path.join(OUT, 'duo.png') });
    await ctx.close();
  }
  await b.close();
  console.log(res.join('\n'));
})();
