// Hook Truck, сборка 12: уровень 2 для того, кто прошёл уровень 1 на подсказках. Первая яма прощает всё (ждёт у края, цепляет и отпускает за игрока),
// на остальных ямах игра начинает помогать после двух падений в одну и ту же. Пять новичков: коснулся раз и смотрит (так ушёл игрок с Android 26.11),
// тычет как попало, отпускает слишком рано, слушается руки везде, кроме последней ямы, зажал и не отпускает. node tests/g8/level2help.js
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs'); const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); const res = [], ok = (c, m) => res.push((c ? 'OK   ' : 'FAIL ') + m);
  const open = async () => { const ctx = await b.newContext({ viewport: { width: 844, height: 390 }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: true, isMobile: true });
    await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: 'window.__pgNoInter = true;' + fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
    const p = await ctx.newPage(); p.errs = []; p.on('pageerror', (e) => p.errs.push(e.message));
    await p.addInitScript(() => { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [2], best: [], duo: false, tut: [1], ctl: 'auto', coins: 30, ts: 1 })); }); // уровень 1 пройден, уровень 2 — впервые
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500); await p.evaluate(() => { window.__hook.setCtl('auto'); window.__hook.start(false, 1); }); await p.waitForTimeout(400); return [ctx, p]; };
  const st = (p) => p.evaluate(() => { const h = window.__hook, S = h.S; return { mode: h.mode, lvl: h.lvl, x: Math.round(S.truck.x), rope: !!S.rope, tut: h.tut, ts: h.ts, n: h.ta.n, fall: h.ta.fall.slice(), ri: h.ta.ri, wait: h.wait }; });
  const ev = (p, name) => p.evaluate((name) => window.__pg.ev.filter((q) => q[0] === name).map((q) => q[1]), name);
  const tapKey = async (p, ms = 120) => { await p.keyboard.down('Space'); await p.waitForTimeout(ms); await p.keyboard.up('Space'); };
  const run = async (p, ms, act) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { await act(Date.now() - t0); if ((await p.evaluate(() => window.__hook.mode)) === 'win') return (Date.now() - t0) / 1000; } return -1; };
  const pit1 = (cr) => cr.filter((q) => q.progress < 33).length, show = (cr) => cr.map((q) => q.progress + '%').join(', ') || 'нет';
  { // 1) коснулся раз (тронулся) и смотрит — так 26.11 трижды упал в первую яму и ушёл игрок с Android
    const [ctx, p] = await open(); await tapKey(p); let a = null; for (let k = 0; k < 60 && !a; k++) { await p.waitForTimeout(150); const q = await st(p); if (q.ts === 0 && q.x > 500 && q.x < 700) a = q; } await p.screenshot({ path: '/tmp/pg/l2-1edge.png' });
    ok(a && a.tut === 'hold', 'коснулся раз и смотрит: у края первой ямы игра остановилась и показывает «держи» — ' + JSON.stringify(a && { x: a.x, ts: a.ts, tut: a.tut }));
    const t = await run(p, 60000, async () => { await p.waitForTimeout(250); }), s = await st(p), cr = await ev(p, 'crash'), pc = (await ev(p, 'progression_completed'))[0]; await p.screenshot({ path: '/tmp/pg/l2-2after.png' });
    ok(cr.length === 0 && t > 0 && pc && pc.assists >= 4, `дальше ни одной аварии (было три падения в первую яму): игра у каждой ямы и у стены ждала его, потом показывала сама — ${t > 0 ? 'уровень пройден за ' + t.toFixed(0) + ' с, помощь ' + (pc && pc.assists) : 'НЕ пройден, x=' + s.x + ', рука: ' + s.tut}; аварии: ${show(cr)}`); ok(!p.errs.length, 'ошибок нет' + (p.errs[0] ? ': ' + p.errs[0] : '')); await ctx.close();
  }
  { // 2) тычет как попало: короткое нажатие каждые 0,45 с
    const [ctx, p] = await open(); const t = await run(p, 90000, async () => { await tapKey(p, 90); await p.waitForTimeout(360); }); const cr = await ev(p, 'crash'), pc = (await ev(p, 'progression_completed'))[0], s = await st(p);
    ok(cr.filter((q) => q.progress < 70).length === 0 && t > 0, `тычет как попало: в первую яму и со стены не упал; аварии: ${show(cr)}; уровень ${t > 0 ? 'пройден за ' + t.toFixed(0) + ' с' : 'не пройден за 90 с, x=' + s.x}${pc ? ', помощь ' + pc.assists : ''}`); await ctx.close();
  }
  { // 3) держит, но отпускает слишком рано — через четверть секунды после зацепа
    const [ctx, p] = await open(); let down = false, at = 0;
    const t = await run(p, 90000, async () => { const r = await p.evaluate(() => !!window.__hook.S.rope); if (!down && !r) { await p.keyboard.down('Space'); down = true; at = 0; } else if (down && r) { if (!at) at = Date.now(); else if (Date.now() - at > 250) { await p.keyboard.up('Space'); down = false; } } else if (!r && down && at) { await p.keyboard.up('Space'); down = false; } await p.waitForTimeout(60); });
    const cr = await ev(p, 'crash'), pc = (await ev(p, 'progression_completed'))[0], s = await st(p); ok(cr.filter((q) => q.progress < 70).length === 0 && t > 0, `отпускает слишком рано: в первую яму и со стены не упал (было шесть аварий у стены); аварии: ${show(cr)}; уровень ${t > 0 ? 'пройден за ' + t.toFixed(0) + ' с' : 'не пройден за 90 с, x=' + s.x}${pc ? ', помощь ' + pc.assists : ''}`); await ctx.close();
  }
  { // 4) слушается руки на первой яме и на стене, а на последней яме крюк не трогает: два падения — на третий раз игра помогает
    const [ctx, p] = await open(); let down = false; await tapKey(p);
    const t = await run(p, 150000, async () => { const q = await st(p), last = q.x > 2150 && !q.rope; if (q.wait) { if (down) { await p.keyboard.up('Space'); down = false; } await tapKey(p); return; }
      if (last) { if (down) { await p.keyboard.up('Space'); down = false; } } else if (q.tut === 'hold' && !down) { await p.waitForTimeout(250); await p.keyboard.down('Space'); down = true; } else if (q.tut === 'rel' && down) { await p.waitForTimeout(250); await p.keyboard.up('Space'); down = false; } await p.waitForTimeout(50); });
    const cr = await ev(p, 'crash'), pc = (await ev(p, 'progression_completed'))[0], late = cr.filter((q) => q.progress >= 70).length, s = await st(p);
    ok(t > 0 && late === 2 && cr.length === 2 && pc && pc.assists >= 2, `на последней яме крюк не трогает: упал ${late} раза, на третий игра остановила у края, зацепила и отпустила (помощь ${pc && pc.assists}), уровень ${t > 0 ? 'пройден за ' + t.toFixed(0) + ' с' : 'НЕ пройден, x=' + s.x}; аварии: ${show(cr)}`); await ctx.close();
  }
  { // 5) зажал и не отпускает
    const [ctx, p] = await open(); await p.keyboard.down('Space'); const t = await run(p, 120000, async () => { await p.waitForTimeout(250); }); await p.keyboard.up('Space'); const cr = await ev(p, 'crash'), s = await st(p), pc = (await ev(p, 'progression_completed'))[0];
    ok(cr.filter((q) => q.progress < 70).length === 0 && t > 0, `зажал и не отпускает: в первую яму и со стены не упал, под кольцом не повис; аварии: ${show(cr)}; уровень ${t > 0 ? 'пройден за ' + t.toFixed(0) + ' с' : 'не пройден за 120 с, x=' + s.x + ', рука: ' + s.tut}${pc ? ', помощь ' + pc.assists : ''}`); await ctx.close();
  }
  await b.close(); console.log(res.join('\n')); const f = res.filter((r) => r.startsWith('FAIL')).length; console.log(f ? `ПРОВАЛОВ: ${f}` : `всё в порядке (${res.length})`); process.exit(f ? 1 : 0);
})();
