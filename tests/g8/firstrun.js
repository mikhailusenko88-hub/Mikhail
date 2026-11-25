// Hook Truck, сборка 10: самый первый запуск — без меню, сразу уровень 1 в режиме «один палец», и провалить его нельзя.
// Четыре новичка: смотрит и ничего не жмёт; зажал и не отпускает; тычет как попало; отпускает слишком рано. Плюс: кто уже играл — в меню; второй заход новичка — в меню;
// замер кадров performance_sample; закрыл игру посреди уровня — progression_failed (how: left). node tests/g8/firstrun.js
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const res = [], ok = (c, m) => res.push((c ? 'OK   ' : 'FAIL ') + m);
  const open = async (init, size) => {
    const ctx = await b.newContext({ viewport: size || { width: 844, height: 390 }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: true, isMobile: true });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
    const p = await ctx.newPage(); p.errs = []; p.on('pageerror', (e) => p.errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && p.errs.push(m.text().slice(0, 200)));
    await p.addInitScript(init || (() => { window.HOOK_FIRST = true; })); await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500); return [ctx, p];
  };
  const st = (p) => p.evaluate(() => { const h = window.__hook; return { mode: h.mode, lvl: h.lvl, ctl: h.ctl, wait: h.wait, x: Math.round(h.S.truck.x), state: h.S.state, msgs: window.__pg.msgs.join(','), ev: window.__pg.ev.map((q) => q[0]).join(',') }; });
  const ev = (p, name) => p.evaluate((name) => window.__pg.ev.filter((q) => q[0] === name).map((q) => q[1]), name);
  const untilWin = async (p, ms, act) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (act) await act(Date.now() - t0); else await p.waitForTimeout(250); if ((await p.evaluate(() => window.__hook.mode)) === 'win') return (Date.now() - t0) / 1000; } return -1; };
  { // 1) смотрит и ничего не жмёт
    const [ctx, p] = await open(); let s = await st(p);
    ok(s.mode === 'play' && s.lvl === 0 && s.ctl === 'auto' && s.wait, 'новичок: меню нет, сразу уровень 1, «один палец», ждёт первого нажатия — ' + JSON.stringify({ mode: s.mode, ctl: s.ctl, wait: s.wait }));
    ok(/game_ready.*gameplay_started.*level_started:1/.test(s.msgs), 'площадке: сначала game_ready, потом старт уровня — ' + s.msgs);
    const ps = await ev(p, 'progression_started'); ok(ps.length === 1 && ps[0].step_id === 'L01' && ps[0].step_index === 1 && ps[0].first_run === true && ps[0].control === 'auto', 'progression_started с отметкой первого запуска: ' + JSON.stringify(ps[0]));
    await p.screenshot({ path: '/tmp/pg/first-1wait.png' });
    await p.waitForTimeout(5200); s = await st(p); ok(!s.wait, 'не нажал за 5 секунд — поехали сами');
    await p.waitForTimeout(4000); await p.screenshot({ path: '/tmp/pg/first-2assist.png' });
    const t = await untilWin(p, 60000); const pc = await ev(p, 'progression_completed'), cr = await ev(p, 'crash');
    ok(t > 0 && pc.length === 1 && pc[0].deaths === 0 && cr.length === 0, `ничего не нажимал — уровень 1 пройден за ${t.toFixed(0)} с без аварий`); ok(pc[0] && pc[0].assists >= 3, 'игра сама показала, как цеплять и отпускать: подсказок ' + (pc[0] && pc[0].assists));
    ok(await p.evaluate(() => window.__hook.save().ctl === 'auto' && window.__hook.save().stars[0] > 0), '«один палец» и звёзды сохранены');
    await p.screenshot({ path: '/tmp/pg/first-3win.png' }); ok(p.errs.length === 0, 'ошибок нет' + (p.errs.length ? ': ' + p.errs[0] : ''));
    // второй заход того же игрока — меню, управление то же
    await p.reload(); await p.waitForTimeout(1500); s = await st(p); ok(s.mode === 'menu' && s.ctl === 'auto', 'второй заход — меню, управление «один палец» осталось');
    await ctx.close();
  }
  { // 2) зажал и не отпускает
    const [ctx, p] = await open(); await p.keyboard.down('Space'); const t = await untilWin(p, 60000); await p.keyboard.up('Space');
    const pc = await ev(p, 'progression_completed'); ok(t > 0 && pc[0] && pc[0].deaths === 0, `зажал и не отпускает — пройден за ${t.toFixed(0)} с, аварий 0, подсказок ${pc[0] && pc[0].assists}`); await ctx.close();
  }
  { // 3) тычет как попало: короткое нажатие каждые 0,45 с
    const [ctx, p] = await open(); const t = await untilWin(p, 70000, async () => { await p.keyboard.down('Space'); await p.waitForTimeout(90); await p.keyboard.up('Space'); await p.waitForTimeout(360); });
    const pc = await ev(p, 'progression_completed'), cr = await ev(p, 'crash'); ok(t > 0 && cr.length === 0, `тычет как попало — пройден за ${t.toFixed(0)} с, аварий ${cr.length}, подсказок ${pc[0] && pc[0].assists}`); await ctx.close();
  }
  { // 4) держит, но отпускает слишком рано: через 0,25 с после зацепа
    const [ctx, p] = await open(); let down = false, hookAt = 0;
    const t = await untilWin(p, 70000, async () => { const r = await p.evaluate(() => ({ rope: !!window.__hook.S.rope, tut: window.__hook.tut })); if (!down && !r.rope) { await p.keyboard.down('Space'); down = true; hookAt = 0; } else if (down && r.rope) { if (!hookAt) hookAt = Date.now(); else if (Date.now() - hookAt > 250) { await p.keyboard.up('Space'); down = false; } } else if (!r.rope && down && hookAt) { await p.keyboard.up('Space'); down = false; } await p.waitForTimeout(60); });
    const cr = await ev(p, 'crash'); ok(t > 0 && cr.length === 0, `отпускает слишком рано — пройден за ${t.toFixed(0)} с, аварий ${cr.length}`); await ctx.close();
  }
  { // 5) кто уже играл — как раньше: меню и ручное управление
    const [ctx, p] = await open(() => { window.HOOK_FIRST = true; localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [2, 1], best: [], duo: false, tut: [1, 1], coins: 100, ts: 1 })); });
    const s = await st(p); ok(s.mode === 'menu' && s.ctl === 'manual', 'кто уже играл — меню и ручное управление, как было'); ok((await ev(p, 'progression_started')).length === 0, 'у него в меню событий нет'); await ctx.close();
  }
  { // 5б) заходил, выбрал ручное, но ни одного уровня не прошёл — тоже сразу в игру, и управление его
    const [ctx, p] = await open(() => { window.HOOK_FIRST = true; localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [], best: [], duo: false, ctl: 'manual', coins: 0, ts: 1 })); });
    const s = await st(p); ok(s.mode === 'play' && s.lvl === 0 && s.ctl === 'manual', 'заходил раньше, уровней не прошёл, выбрал ручное — сразу уровень 1, управление осталось ручным'); await ctx.close();
  }
  { // 6) замер кадров и «закрыл игру посреди уровня»
    const [ctx, p] = await open(() => { window.HOOK_FIRST = true; window.HOOK_PERF_MS = 3000; }, { width: 390, height: 844 });
    await p.keyboard.down('Space'); await p.waitForTimeout(300); await p.keyboard.up('Space'); await p.waitForTimeout(7500);
    const sm = await ev(p, 'performance_sample'), q = sm[0] || {}, need = ['target_fps', 'window_ms', 'active_ms', 'frame_count', 'fps_avg', 'fps_p10', 'frame_time_p50_ms', 'frame_time_p95_ms', 'frame_time_p99_ms', 'frame_time_max_ms', 'frames_over_50ms', 'frames_over_100ms', 'frames_over_250ms', 'frames_over_500ms', 'frames_over_1000ms', 'build_version'];
    ok(sm.length >= 1 && need.every((k) => q[k] !== undefined && (typeof q[k] === 'number' ? isFinite(q[k]) : true)), `performance_sample пришёл (${sm.length} шт.), все обязательные поля на месте`);
    ok(q.frame_count > 10 && q.fps_avg > 1 && q.fps_p10 <= q.fps_avg + 0.11 && q.frame_time_p50_ms <= q.frame_time_p95_ms && q.frame_time_p95_ms <= q.frame_time_p99_ms && q.frame_time_p99_ms <= q.frame_time_max_ms && q.window_ms >= q.active_ms - 1 && q.build_version === '10', 'числа замера согласованы: ' + JSON.stringify(q));
    if ((await p.evaluate(() => window.__hook.mode)) !== 'play') await p.evaluate(() => window.__hook.start(false, 2)); await p.waitForTimeout(400);
    await p.evaluate(() => window.dispatchEvent(new Event('pagehide'))); const pf = await ev(p, 'progression_failed'); ok(pf.length === 1 && pf[0].how === 'left' && pf[0].step_id, 'закрыл игру посреди уровня — progression_failed (how: left): ' + JSON.stringify(pf[0]));
    ok(p.errs.length === 0, 'ошибок нет' + (p.errs.length ? ': ' + p.errs[0] : '')); await ctx.close();
  }
  await b.close(); console.log(res.join('\n')); console.log(res.some((q) => /^FAIL/.test(q)) ? 'ЕСТЬ ПРОВАЛЫ' : `все ${res.length} проверок прошли`);
})();
