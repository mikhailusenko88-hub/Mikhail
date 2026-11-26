// Hook Truck, сборка 11: темп межстраничной рекламы. Первая — не раньше четырёх минут от запуска, следующая — не раньше чем через три минуты,
// после ролика за награду — полторы минуты тишины; на первых двух уровнях рекламы нет никогда. Время задаётся сдвигом отметок игры, ждать не нужно.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs'); const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); const res = []; const ok = (c, m) => res.push((c ? 'OK   ' : 'FAIL ') + m);
  for (const [name, w, h] of [['phone', 844, 390], ['desk', 1280, 720]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: w < 900, isMobile: w < 900 });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.addInitScript(() => { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [1, 1, 1, 1, 1, 1], best: [], duo: false, tut: [1, 1], coins: 100, ts: 1 })); });
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__hook.btns.find((q) => q.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) return false; if (w < 900) await p.touchscreen.tap(q[0], q[1]); else await p.mouse.click(q[0], q[1]); await p.waitForTimeout(150); return true; };
    const win = async () => { await p.evaluate(() => { const S = window.__hook.S; S.L.star.got = true; S.state = 'win'; S.wonT = 1; S.wonAt = 5.2; }); await p.waitForTimeout(1800); };
    // прошёл уровень li, когда от запуска прошло since секунд, от прошлой межстраничной — gap, от ролика за награду — rew; нажал «дальше» — была ли реклама
    const next = async (li, since, gap, rew) => { await p.evaluate(([li, since, gap, rew]) => { const g = window.__hook.pg, now = performance.now() / 1000; g.t0 = (now - since) * 1000; g.lastInter = now - gap; g.lastRew = now - rew; window.__pg.ads.length = 0; window.__hook.start(false, li); }, [li, since, gap, rew]); await p.waitForTimeout(400); await win();
      await tap('next'); await p.waitForTimeout(300); const ad = await p.evaluate(() => /inter:level_end/.test(window.__pg.ads.join(','))); await p.waitForTimeout(1300); return ad; };
    ok(await p.evaluate(() => window.__pg.ver) === '11', name + ': сборка 11');
    ok(!(await next(2, 100, 1e9, 1e9)), name + ': 1 мин 40 с от запуска, уровень 3 — рекламы нет (раньше была)');
    ok(!(await next(4, 230, 1e9, 1e9)), name + ': 3 мин 50 с от запуска — рекламы ещё нет');
    ok(await next(4, 250, 1e9, 1e9), name + ': 4 мин 10 с от запуска — первая реклама');
    ok(!(await next(5, 400, 100, 1e9)), name + ': 1 мин 40 с после прошлой — рекламы нет (раньше была)');
    ok(!(await next(5, 400, 170, 1e9)), name + ': 2 мин 50 с после прошлой — рекламы ещё нет');
    ok(await next(5, 400, 190, 1e9), name + ': 3 мин 10 с после прошлой — реклама');
    ok(!(await next(5, 400, 1e9, 60)), name + ': минута после ролика за награду — рекламы нет');
    ok(await next(5, 400, 1e9, 100), name + ': 1 мин 40 с после ролика за награду — реклама');
    ok(!(await next(1, 1e6, 1e9, 1e9)), name + ': уровень 2 — рекламы нет, сколько бы ни играл');
    ok(!(await next(0, 1e6, 1e9, 1e9)), name + ': уровень 1 — рекламы нет, сколько бы ни играл');
    // настоящее время: только что была реклама — сразу «дальше» ещё раз: второй подряд нет
    await next(5, 400, 1e9, 1e9); const again = await p.evaluate(() => { window.__pg.ads.length = 0; window.__hook.start(false, 6); return true; }); await p.waitForTimeout(400); await win(); await tap('next'); await p.waitForTimeout(300);
    ok(again && !(await p.evaluate(() => /inter/.test(window.__pg.ads.join(',')))), name + ': сразу после рекламы следующий уровень — без рекламы');
    ok(!errs.length, name + ': ошибок нет' + (errs.length ? ' — ' + errs[0] : '')); await ctx.close();
  }
  await b.close(); console.log(res.join('\n')); const f = res.filter((r) => r.startsWith('FAIL')).length; console.log(f ? `ПРОВАЛОВ: ${f}` : `всё в порядке (${res.length})`); process.exit(f ? 1 : 0);
})();
