// Проба 6.4: третий район «Перевал». Список района, карточки заказов (значки дороги, совет механика), таблички и строка «Впереди» без пустых подписей,
// связка канистр, валуны, осыпь — лёжа и стоя. Снимки складывает в папку из аргумента.
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const OUT = process.argv[2] || '/tmp/mud64'; require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); let bad = 0;
  for (const [name, w, h, lang] of [['844x390', 844, 390, 'ru'], ['390x844', 390, 844, 'ru'], ['740x360-en', 740, 360, 'en']]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: lang === 'ru' ? 'ru-RU' : 'en-US', hasTouch: true, isMobile: true });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.addInitScript(() => { window.__txt = []; const f = CanvasRenderingContext2D.prototype.fillText; CanvasRenderingContext2D.prototype.fillText = function (t, ...a) { const s = String(t); if (window.__txt.length < 4000 && !window.__txt.includes(s)) window.__txt.push(s); return f.call(this, t, ...a); }; });
    await p.goto('file://' + require('path').resolve(__dirname, '../../dist/mud-side/index.html') + '?' + lang); await p.waitForFunction(() => window.__mud); await p.evaluate(() => window.__mud.toMenu()); await p.waitForTimeout(800);
    const pos = (id) => p.evaluate((id) => { const b = window.__mud.buttons.find((b) => b.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2, b.w, b.h] : null; }, id);
    const tap = async (id, wait = 450) => { const q = await pos(id); if (!q) { console.log('  НЕТ КНОПКИ ' + id); bad++; return null; } await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(wait); return q; };
    const check = (what, ok, extra) => { console.log(`  ${ok ? 'да ' : 'НЕТ'} ${what}${extra ? ' — ' + extra : ''}`); if (!ok) bad++; };
    const texts = async () => { const t = await p.evaluate(() => { const r = window.__txt.slice(); window.__txt.length = 0; return r; }); return t; }, badT = (t) => t.filter((q) => /undefined|NaN|null|\[object/.test(q));
    console.log(name);
    await p.evaluate(() => { const m = window.__mud, M = window.MudSide; m.save.coins = 500; M.CONTRACTS.forEach((c) => { m.save.stars[c.id] = 1; }); Object.assign(m.save.own, { awd: [1], low: [1], lock: [1], tires: [1, 2], lift: [1], snorkel: [1], tank: [1], winch: [1], base: [1, 2], eng: [1, 2, 3, 4] }); Object.assign(m.save.build, { awd: 1, low: 1, lock: 1, tires: 1, lift: 0, snorkel: 1, tank: 1, winch: 0, base: 2, eng: 4, axles: 2, trailer: 0 }); m.toMenu(); });
    await texts(); await tap('reg:2'); await p.waitForTimeout(300); let t = await texts();
    const regs = await p.evaluate(() => window.__mud.buttons.filter((q) => /^reg:/.test(q.id)).map((q) => [Math.round(q.w), Math.round(q.h)])), rows = await p.evaluate(() => window.__mud.buttons.filter((q) => /^c:/.test(q.id)).map((q) => [q.id, Math.round(q.h)]));
    check('три района, кнопки не уже 80', regs.length === 3 && regs.every((q) => q[0] >= 80), JSON.stringify(regs)); check('в районе 6 заказов (13–18), строки не ниже 38', rows.length === 6 && rows[0][0] === 'c:12' && rows.every((q) => q[1] >= 38), JSON.stringify(rows.map((q) => q[1])));
    check('в списке района нет пустых подписей', !badT(t).length, badT(t).join(' | ')); await p.screenshot({ path: `${OUT}/v64-${name}-0list.png` });
    for (const i of [12, 13, 14, 15, 16, 17]) {
      await tap('c:' + i, 350); await texts(); await p.waitForTimeout(350); t = await texts(); const id = await p.evaluate((i) => window.MudSide.CONTRACTS[i].id, i);
      check(`заказ ${i + 1} (${id}): карточка без пустых подписей`, !badT(t).length, badT(t).join(' | '));
      const adv = t.filter((q) => /🔧/.test(q)).join(' ') + ' ' + t.filter((q) => /шин|tires|лебёдк|winch/i.test(q)).join(' ');
      if (id !== 'stones') check(`заказ ${i + 1}: механик говорит про шины для склона`, /универсальных|universal/.test(adv), adv.slice(0, 110));
      const go = await pos('go'), okIn = await p.evaluate(([W, H]) => window.__mud.buttons.every((q) => q.x >= -1 && q.y >= -1 && q.x + q.w <= W + 1 && q.y + q.h <= H + 1), [w, h]); check(`заказ ${i + 1}: кнопка «в рейс» есть, все кнопки в экране`, !!go && okIn);
      if (i === 17 || i === 12) await p.screenshot({ path: `${OUT}/v64-${name}-1card${i + 1}.png` });
      await tap('unsel', 300);
    }
    await p.evaluate(() => { const m = window.__mud; Object.assign(m.save.build, { tires: 2, base: 0, axles: 3 }); m.toMenu(); }); await tap('reg:2', 300); await tap('c:14', 350); await texts(); await p.waitForTimeout(350); t = await texts();
    check('короткая 6×6 на «Руднике»: механик заранее говорит про опрокидывание', t.some((q) => /опрокидывает|tips over/.test(q)) || /опрокидывает|tips over/.test(t.join(' ')), t.filter((q) => /🔧/.test(q)).join(' ').slice(0, 120)); await tap('unsel', 300);
    await tap('c:12', 350); await texts(); await p.waitForTimeout(350); t = await texts(); check('та же сборка на заказе с брёвнами: про опрокидывание не говорит', !/опрокидывает|tips over/.test(t.join(' '))); await tap('unsel', 300);
    await p.evaluate(() => { const m = window.__mud; Object.assign(m.save.build, { base: 2, axles: 2 }); m.toMenu(); });
    // рейс: грязевые шины и лебёдка стоят; по каждой трассе — с начала и с отметок, пять секунд газа, снимок
    await p.evaluate(() => { const m = window.__mud; Object.assign(m.save.build, { tires: 2, winch: 1, lift: 1 }); m.toMenu(); });
    for (const [i, cps] of [[12, [0, 2]], [13, [1]], [14, [1, 4]], [15, [0, 3]], [16, [0, 2]], [17, [0, 5, 6]]]) {
      await tap('reg:2', 300); await tap('c:' + i, 500); await tap('go', 900); await texts();
      const info = await p.evaluate(() => { const S = window.__mud.S; return { mode: window.__mud.mode, cps: S.L.cps.length, rocks: (S.L.rocks || []).length, cans: S.L.cans.map((c) => c.k) }; });
      check(`заказ ${i + 1}: рейс начался`, info.mode === 'play', JSON.stringify(info)); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(2500); await p.screenshot({ path: `${OUT}/v64-${name}-2run${i + 1}-start.png` });
      for (const k of cps) { await p.evaluate((k) => { const S = window.__mud.S; const c = S.L.cps[k]; S.cp = { x: c.x, y: c.y, fuel: S.cfg.tank }; S.respawn(); }, k); await p.waitForTimeout(lang === 'en' ? 2500 : 4500); await p.screenshot({ path: `${OUT}/v64-${name}-2run${i + 1}-cp${k}.png` }); }
      await p.keyboard.up('ArrowRight'); t = await texts(); check(`заказ ${i + 1}: в рейсе нет пустых подписей`, !badT(t).length, badT(t).join(' | '));
      if (i === 17) check('связка канистр: подобрал — «+60 л»', t.some((q) => /\+60/.test(q)), t.filter((q) => /\+\d+ /.test(q)).join(' | '));
      if (i === 15) check('строка «Впереди» называет осыпь', t.some((q) => /осыпь|scree/.test(q)), t.filter((q) => /Впереди|Ahead/.test(q)).slice(0, 4).join(' | '));
      await p.evaluate(() => window.__mud.toMenu()); await p.waitForTimeout(400);
    }
    if (lang === 'ru' && w > h) { // короткий грузовик без пониженной заклинивает между камнями: подсказка должна назвать камни и сказать, что делать
      await p.evaluate(() => { const m = window.__mud; Object.assign(m.save.build, { base: 0, eng: 3, axles: 2, trailer: 0 }); m.toMenu(); }); await tap('reg:2', 300); await tap('c:15', 500); await tap('go', 900);
      await p.evaluate(() => { const m = window.__mud, S = m.S; S.spawn(82.8 * 54, S.groundAt(82.8 * 54)); m.sw.awd = true; m.sw.lock = true; }); await texts(); await p.keyboard.down('ArrowRight'); let seen = '', x = 0;
      for (let k = 0; k < 40 && !seen; k++) { await p.waitForTimeout(500); t = await texts(); seen = t.find((q) => /^Камни:|^Качаешься/.test(q)) || ''; x = await p.evaluate(() => window.__mud.S.truck.x / 54); if (x > 97) break; }
      await p.keyboard.up('ArrowRight'); if (x > 97) console.log('  (грузовик проехал камни сам — подсказка не понадобилась)'); else check('заклинило на камнях — подсказка «сдай назад и бери с хода»', !!seen, seen || 'x=' + x.toFixed(1)); await p.screenshot({ path: `${OUT}/v64-${name}-3rock.png` });
    }
    check('ошибок в консоли нет', !errs.length, errs.slice(0, 3).join(' | ')); await ctx.close();
  }
  await b.close(); console.log(bad ? `ПРОВАЛОВ: ${bad}` : 'всё в порядке'); process.exit(bad ? 1 : 0);
})();
