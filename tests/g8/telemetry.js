// Hook Truck: отметки для разбора (сборка 10: продвижение по образцу Playgama — progression_started / _completed / _failed). Каждое действие даёт ровно одно событие с нужными полями; данные плоские; номер сборки передан.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const res = [], ok = (c, m) => res.push((c ? 'OK   ' : 'FAIL ') + m);
  {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: true, isMobile: true });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: 'window.__pgNoInter = true;' + fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
    const ev = (name) => p.evaluate((name) => window.__pg.ev.filter((q) => !name || q[0] === name), name);
    const hud = async (id) => { const m = await p.evaluate((id) => { const b = window.__hook.buttons.find((q) => q.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!m) return false; await p.touchscreen.tap(m[0], m[1]); await p.waitForTimeout(400); return true; };
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__hook.btns.find((q) => q.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) return false; await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(300); return true; };
    const win = async () => { await p.evaluate(() => { const S = window.__hook.S; S.L.star.got = true; S.state = 'win'; S.wonT = 1; S.wonAt = 5.2; }); await p.waitForTimeout(1800); };
    ok(await p.evaluate(() => window.__pg.ver) === '13', 'номер сборки передан мосту: 13');
    ok((await ev()).length === 0, 'в меню событий нет');
    // уровень 1: две аварии, начал заново, доехал
    await p.evaluate(() => window.__hook.start(false, 0)); await p.waitForTimeout(600);
    await p.evaluate(() => window.__hook.S.events.push({ e: 'dead', why: 'fell' })); await p.waitForTimeout(300);
    await p.evaluate(() => window.__hook.S.events.push({ e: 'dead', why: 'crash' })); await p.waitForTimeout(300);
    let c = await ev('crash'); ok(c.length === 2 && c[0][1].reason === 'fell' && c[1][1].reason === 'crash' && c[0][1].deaths === 1 && c[1][1].deaths === 2 && c[0][1].level === 1, 'две аварии — два события crash с причиной, номером уровня и счётчиком: ' + JSON.stringify(c[1] && c[1][1]));
    ok(await hud('restart'), 'кнопка «заново» нажата'); let q = await ev('progression_failed'); ok(q.length === 1 && q[0][1].how === 'restart' && q[0][1].deaths === 2 && q[0][1].level === 1, 'начал заново — одно progression_failed (how: restart, аварий 2)');
    await p.waitForTimeout(700); await win();
    let w = await ev('progression_completed'); ok(w.length === 1 && w[0][1].level === 1 && w[0][1].stars >= 2 && w[0][1].first_time === true && w[0][1].deaths === 0 && w[0][1].time_sec === 5.2, 'доехал — одно progression_completed: ' + JSON.stringify(w[0] && w[0][1]));
    ok((await ev('tutorial_completed')).length === 0, 'обучение ещё не пройдено (нужны уровни 1 и 2)');
    ok((await ev('progression_failed')).length === 1, 'после победы лишнего progression_failed нет');
    // уровень 2: доехал — обучение пройдено
    await tap('next'); await p.waitForTimeout(500); await win();
    w = await ev('progression_completed'); ok(w.length === 2 && w[1][1].level === 2, 'уровень 2 — второе progression_completed'); ok((await ev('tutorial_completed')).length === 1, 'обучение пройдено — одно tutorial_completed');
    // повтор уровня 1: first_time = false, tutorial_completed не повторяется
    await p.evaluate(() => window.__hook.start(false, 0)); await p.waitForTimeout(500); await win();
    w = await ev('progression_completed'); ok(w.length === 3 && w[2][1].first_time === false, 'повторный проезд — first_time: false'); ok((await ev('tutorial_completed')).length === 1, 'tutorial_completed не повторился');
    // уровень 3: ушёл в меню
    await p.evaluate(() => window.__hook.start(false, 2)); await p.waitForTimeout(900); ok(await hud('menu'), 'кнопка «меню» нажата');
    q = await ev('progression_failed'); ok(q.length === 2 && q[1][1].how === 'menu' && q[1][1].level === 3 && q[1][1].progress >= 0 && q[1][1].progress <= 100, 'ушёл в меню — progression_failed (how: menu): ' + JSON.stringify(q[1] && q[1][1]));
    ok(q[1][1].fps > 0 && q[1][1].quality > 0 && q[1][1].duration_sec >= 0, `в итоге заезда есть кадры в секунду (${q[1][1].fps}) и качество картинки (${q[1][1].quality})`);
    { const st = await ev('progression_started'); ok(st.length === 5 && st[0][1].step_id === 'L01' && st[0][1].step_index === 1 && st[1][1].step_id === 'L01' && st[4][1].step_id === 'L03' && st[4][1].step_index === 3 && st[0][1].first_run === false && typeof st[0][1].control === 'string', 'каждый старт уровня (и «заново» тоже) — progression_started с шагом: ' + st.map((q) => q[1].step_id).join(' '));
      const f = await ev('progression_failed'), c2 = await ev('progression_completed'); ok(f.every((q) => q[1].step_id && q[1].step_index === q[1].level) && c2.every((q) => q[1].step_id && q[1].step_index === q[1].level && q[1].assists === 0), 'в итогах уровня есть шаг (step_id, step_index) и число подсказок игры'); }
    // управление и гараж
    const m0 = (await ev('settings_changed')).length; await tap('m:auto'); const sc = await ev('settings_changed'); ok(sc.length === m0 + 1 && sc[sc.length - 1][1].value === 'auto', 'смена управления — settings_changed');
    await p.evaluate(() => { window.__hook.save().coins = 9999; window.__hook.garage(); }); await p.waitForTimeout(600);
    let up; for (let i = 0; i < 6 && !up; i++) { up = await p.evaluate(() => (window.__hook.btns.find((q) => /^g:up:/.test(q.id)) || {}).id); if (!up) await tap('g:tab:' + i); } ok(!!up, 'в гараже есть кнопка улучшения: ' + up); // улучшения — на своей вкладке
    if (up) { await tap(up); const u = await ev('upgrade_purchased'); ok(u.length === 1 && u[0][1].level === 1 && u[0][1].price > 0 && typeof u[0][1].upgrade_id === 'string', 'покупка улучшения — upgrade_purchased: ' + JSON.stringify(u[0] && u[0][1])); }
    // все данные плоские: строки, числа, да/нет
    const all = await ev(); ok(all.every(([n, d]) => /^[a-z_]+$/.test(n) && Object.values(d).every((v) => ['string', 'number', 'boolean'].includes(typeof v) && !(typeof v === 'number' && !isFinite(v)))), `все ${all.length} событий: имена snake_case, данные плоские`);
    const msgs = await p.evaluate(() => window.__pg.msgs.join(',')); ok((msgs.match(/level_started/g) || []).length === 5 && (msgs.match(/level_completed/g) || []).length === 3, 'сообщения площадке не задвоены: level_started 5, level_completed 3 — ' + (msgs.match(/level_[a-z]+:\d+/g) || []).join(' '));
    ok(errs.length === 0, 'ошибок в консоли нет' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));
    await ctx.close();
  }
  { // настоящий мост вне площадки (платформа mock): отметки молчат, игра работает
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(2500);
    await p.evaluate(() => window.__hook.start(false, 0)); await p.waitForTimeout(600);
    await p.evaluate(() => window.__hook.S.events.push({ e: 'dead', why: 'fell' })); await p.waitForTimeout(300);
    await p.evaluate(() => { const S = window.__hook.S; S.state = 'win'; S.wonT = 1; S.wonAt = 5.2; }); await p.waitForTimeout(1800);
    ok(await p.evaluate(() => window.__hook.mode === 'win' && !window.__hook.pg.on), 'настоящий мост без площадки: уровень пройден, отметки выключены'); ok(errs.length === 0, 'настоящий мост: ошибок нет' + (errs.length ? ': ' + errs[0] : ''));
    ok(await p.evaluate(() => typeof window.bridge.analytics.send === 'function'), 'в настоящем мосте есть bridge.analytics.send');
    await ctx.close();
  }
  await b.close(); console.log(res.join('\n')); console.log(res.some((q) => q.startsWith('FAIL')) ? 'ЕСТЬ ПРОВАЛЫ' : `все ${res.length} проверок пройдены`);
})();
