// Проба 6.3: прицеп только на длинную раму с тремя мостами; при примерке видно, сколько покупка прибавит к полному рейсу;
// большой прицеп с ведущими мостами в рейсе с полным грузом; «макс» — полный кузов одним нажатием. Лёжа и стоя.
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const OUT = process.argv[2] || '/tmp/mud4'; require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); let bad = 0;
  for (const [name, w, h] of [['844x390', 844, 390], ['390x844', 390, 844]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + require('path').resolve(__dirname, '../../dist/mud-side/index.html') + '?ru'); await p.waitForFunction(() => window.__mud); await p.evaluate(() => window.__mud.toMenu()); await p.waitForTimeout(800);
    const pos = (id) => p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2, b.w, b.h] : null; }, id);
    const tap = async (id, wait = 450) => { const q = await pos(id); if (!q) { console.log('  НЕТ КНОПКИ ' + id); bad++; return null; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(wait); return q; };
    const check = (what, ok, extra) => { console.log(`  ${ok ? 'да ' : 'НЕТ'} ${what}${extra ? ' — ' + extra : ''}`); if (!ok) bad++; };
    const st = () => p.evaluate(() => { const m = window.__mud, bd = m.save.build; return { coins: m.save.coins, axles: bd.axles, eng: bd.eng, trailer: bd.trailer, note: m.note, buy: !!m.buttons.find((q) => q.id === 'buy') }; });
    const best = (ch) => p.evaluate((ch) => { const m = window.__mud, M = window.MudSide, C = M.spec(Object.assign({}, m.save.build, ch || {})); let r = 0; M.CONTRACTS.forEach((c) => { r = Math.max(r, M.capOf(C, c.cargo) * c.pay); }); return r; }, ch);
    const tabOf = { axles: 0, base: 0, eng: 2, trailer: 3 }, part = async (k, v) => { await tap('tab:' + tabOf[k], 300); return tap(`p:${k}:${v}`); };
    console.log(name);
    await p.evaluate(() => { const m = window.__mud, M = window.MudSide; m.save.coins = 60000; M.CONTRACTS.forEach((c) => { m.save.stars[c.id] = 1; }); Object.assign(m.save.own, { awd: [1], low: [1], lock: [1], tires: [1], lift: [1], snorkel: [1], tank: [1], base: [1, 2], eng: [1, 2, 3, 4] }); Object.assign(m.save.build, { awd: 1, low: 1, lock: 1, tires: 1, lift: 1, snorkel: 1, tank: 1, base: 2, eng: 4, axles: 2, trailer: 0 }); m.toMenu(); });
    await tap('reg:1'); await tap('c:10'); await tap('gar');
    // 1) тележка на 4×4 — отказ с объяснением
    await part('trailer', 1); let s = await st(); check('тележка на 4×4 не ставится, подсказка говорит про три моста', s.trailer === 0 && !s.buy && /6×6/.test(s.note), s.note.slice(0, 70));
    // 2) 6×6: примерка честно говорит, что сам он заработка не прибавит (при полном кузове) или сколько прибавит
    let a = await best(), n = await best({ axles: 3 }); await part('axles', 3); s = await st(); check('примерка 6×6: в подсказке — что он даёт к рейсу', s.buy && (n > a ? s.note.includes(`${a} → ${n}`) : /прицеп/.test(s.note)), s.note.slice(0, 90)); await tap('buy'); s = await st(); check('6×6 куплен', s.axles === 3 && s.coins === 57000);
    // 3) тележка: «Полный рейс: было → стало», числа те же, что даёт правило груза
    a = await best(); n = await best({ trailer: 1 }); await part('trailer', 1); s = await st(); check(`примерка тележки: «${a} → ${n}» в подсказке`, s.buy && n > a && s.note.includes(`${a} → ${n}`) && s.note.includes(`+${n - a}`), s.note.slice(0, 60)); await p.screenshot({ path: `${OUT}/r63-${name}-1cart.png` });
    await tap('buy'); s = await st(); const tr1 = await p.evaluate(() => { const t = window.__mud.S.cfg.tr; return t ? [t.bed, !!t.drive] : null; }); check('тележка куплена и стоит на грузовике', s.trailer === 1 && tr1 && tr1[0] === 117 && !tr1[1], JSON.stringify(tr1));
    // 4) мотор 5 и 6 с тележкой прибавляют; мотор 7 с тележкой — уже нет, и подсказка говорит почему
    for (const e of [5, 6]) { a = await best(); n = await best({ eng: e }); await part('eng', e); s = await st(); check(`примерка мотора ${e}: «${a} → ${n}»`, n > a && s.note.includes(`${a} → ${n}`)); await tap('buy'); }
    a = await best(); n = await best({ eng: 7 }); await part('eng', 7); s = await st(); check('мотор 7 с тележкой: заработок не вырастет — подсказка про полный кузов', n === a && /кузов и так полон/.test(s.note), s.note.slice(0, 70)); await p.screenshot({ path: `${OUT}/r63-${name}-2eng7.png` });
    // 5) большой прицеп
    a = await best(); n = await best({ trailer: 2 }); await part('trailer', 2); s = await st(); check(`примерка большого прицепа: «${a} → ${n}»`, n > a && s.note.includes(`${a} → ${n}`), s.note.slice(0, 60)); await p.screenshot({ path: `${OUT}/r63-${name}-3big.png` });
    await tap('buy'); const tr2 = await p.evaluate(() => { const t = window.__mud.S.cfg.tr; return t ? [t.bed, t.drive, window.__mud.S.cfg.tank] : null; }); check('большой прицеп куплен: кузов 231, мосты ведущие, бак с запасом', tr2 && tr2[0] === 231 && tr2[1] === 0.25 && tr2[2] === 145, JSON.stringify(tr2));
    for (const e of [7, 8]) { a = await best(); n = await best({ eng: e }); await part('eng', e); s = await st(); check(`мотор ${e} с большим прицепом: «${a} → ${n}»`, n > a && s.note.includes(`${a} → ${n}`)); await tap('buy'); }
    s = await st(); check('всё куплено: мотор 8, большой прицеп', s.eng === 8 && s.trailer === 2, 'осталось монет ' + s.coins);
    // 6) заказ «два брода»: «макс» ставит полный кузов, рейс с 28 бочками
    await tap('menu'); if (!(await pos('lg='))) { await tap('reg:1'); await tap('c:10'); } await tap('lg='); const cg = await p.evaluate(() => ({ n: window.__mud.S.cargo, logs: window.__mud.S.logs.length, cap: window.MudSide.capOf(window.__mud.S.cfg, 'barrel') })); check('«макс»: полный кузов одним нажатием', cg.n === 28 && cg.logs === 28 && cg.cap === 28, JSON.stringify(cg)); await p.screenshot({ path: `${OUT}/r63-${name}-4contract.png` });
    await tap('go', 900); await p.screenshot({ path: `${OUT}/r63-${name}-5start.png` });
    await p.evaluate(() => { window.__mud.flip('awd'); }); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(9000);
    const tdMax = await p.evaluate(() => new Promise((res) => { let mx = 0, n = 0; const f = () => { mx = Math.max(mx, window.__mud.S.twj[0].maxT); if (++n < 40) requestAnimationFrame(f); else res(Math.round(mx)); }; requestAnimationFrame(f); }));
    const run = await p.evaluate(() => { const m = window.__mud, S = m.S; return { mode: m.mode, st: S.state, x: Math.round(S.truck.x), gap: (() => { const h = window.TPhys.wpt(S.truck, S.cfg.tr.hx, S.cfg.tr.hy); return Math.round(Math.hypot(S.trailer.x - h[0], S.trailer.y - h[1])); })(), cargo: S.cargo, lost: S.logs.filter((q) => q.lost).length, awd: S.awd,  fold: +(S.trailer.a - S.truck.a).toFixed(2) }; });
    check('в рейсе: едет, прицеп за грузовиком и не наезжает на него (от сцепки до середины прицепа 150–162), груз цел, мосты прицепа тянут', run.mode === 'play' && run.st === 'play' && run.x > 400 && run.gap >= 149 && run.gap <= 170 && run.cargo === 28 && run.lost === 0 && run.awd && tdMax > 0 && Math.abs(run.fold) < 0.6, JSON.stringify(run) + ' тяга на колесе прицепа до ' + tdMax);
    await p.screenshot({ path: `${OUT}/r63-${name}-6run.png` }); await p.keyboard.up('ArrowRight');
    check('ошибок нет', errs.length === 0, errs.slice(0, 2).join(' | ')); await ctx.close();
  }
  await b.close(); console.log(bad ? 'ЕСТЬ ПРОВАЛЫ: ' + bad : 'всё в порядке');
})();
