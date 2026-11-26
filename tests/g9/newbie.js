// «Грязь», обучение: пять новичков с чистого листа проходят заказы 1–4. В меню все идут за жёлтым кольцом (так ведёт игра), в рейсе ведут себя по-разному:
// gas — только газ, кнопок не трогает; all — сразу включает всё, что есть; poke — тычет газ рывками и жмёт кнопки как попало; follow — жмёт кнопку, на которую показывает кольцо;
// awd — сам включает 4×4 в начале рейса, остальное не трогает. Пишет по каждому заказу: попытки, аварии и их причины, сколько раз помогла игра, деньги, хватило ли на деталь.
// node tests/g9/newbie.js [тип,тип] [минут на тип]
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const path = require('path');
const TYPES = (process.argv[2] || 'gas,all,poke,follow,awd').split(','), MIN = +(process.argv[3] || 5), PAGE = 'file://' + path.resolve(__dirname, '../../dist/mud-side/index.html') + '?ru';
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); let bad = 0;
  for (const type of TYPES) {
    const ctx = await b.newContext({ viewport: { width: 844, height: 390 }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: true, isMobile: true }), p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto(PAGE); await p.waitForFunction(() => window.__mud && window.__mud.S); await p.waitForTimeout(600);
    const st = () => p.evaluate(() => { const m = window.__mud, S = m.S; return { mode: m.mode, state: S.state, deadT: S.deadT, wonT: S.wonT, paused: m.paused, hold: m.hold, coach: m.coach, hint: m.hintNow, x: Math.round(S.truck.x / 54), t: S.t, sel: m.sel, cur: m.cur, coins: m.save.coins, stars: Object.assign({}, m.save.stars), asst: m.asst, ids: m.buttons.map((q) => q.id), have: ['awd', 'lock', 'low'].filter((k) => S.cfg.b[k]), sw: Object.assign({}, m.sw), adv: m.adv, fail: m.fail, res: m.res && { total: m.res.total, deliv: m.res.deliv, of: m.res.of } }; });
    const tap = async (id) => { const q = await p.evaluate((id) => { const b = window.__mud.buttons.find((q) => q.id === id); return b ? [b.x + b.w / 2, b.y + b.h / 2] : null; }, id); if (!q) return false; await p.touchscreen.tap(q[0], q[1]); await p.waitForTimeout(120); return true; };
    const key = async (k, on) => { await p.keyboard[on ? 'down' : 'up'](k); };
    const log = {}, L = (i) => (log[i] = log[i] || { tries: 0, deaths: [], asst: 0, holds: 0, short: '', coins0: null, got: '', tips: [] });
    let lastHint = '', gasOn = false, lastPoke = 0, runStarted = -1, lastHold = '', pokeT = 0, t0 = Date.now(), lastCur = -1, followAt = 0, backUntil = 0;
    while (Date.now() - t0 < MIN * 60000) {
      const s = await st();
      if (Object.keys(s.stars).length >= 4 && Object.values(s.stars).filter((v) => v > 0).length >= 4) break;
      if (s.mode === 'play' && s.state === 'play' && !s.paused) {
        if (s.cur !== lastCur || s.t < 0.3 && runStarted !== s.cur) { if (runStarted !== s.cur || s.t < 0.3) { L(s.cur).tries++; runStarted = s.cur; } lastCur = s.cur;
          if (type === 'all') for (const k of s.have) if (!s.sw[k]) await tap(k); if (type === 'awd' && s.have.includes('awd') && !s.sw.awd) await tap('awd'); }
        if (s.hold && s.hold !== lastHold) L(s.cur).holds++; lastHold = s.hold; if (s.hint) lastHint = s.hint;
        if (type === 'follow') { const k = s.coach && s.coach.replace('pre:', ''); if (k && s.have.includes(k) && !s.sw[k]) { if (!followAt) followAt = Date.now(); if (Date.now() - followAt > 600) { await tap(k); followAt = 0; } } else followAt = 0;
          if (/назад/.test(s.hint) && !backUntil) backUntil = Date.now() + 1500; }
        if (type === 'poke') { if (Date.now() - pokeT > (gasOn ? 400 : 200)) { gasOn = !gasOn; await key('ArrowRight', gasOn); pokeT = Date.now(); } if (Date.now() - lastPoke > 2500 && s.have.length) { await tap(s.have[Math.floor(Math.random() * s.have.length)]); lastPoke = Date.now(); } }
        else if (backUntil && Date.now() < backUntil) { await key('ArrowRight', false); await key('ArrowLeft', true); }
        else { if (backUntil) { backUntil = 0; await key('ArrowLeft', false); } await key('ArrowRight', true); }
        await p.waitForTimeout(80); continue;
      }
      await key('ArrowRight', false); await key('ArrowLeft', false); gasOn = false;
      if (s.mode === 'play' && s.state === 'dead' && s.deadT > 1) { L(s.cur).deaths.push(s.fail.split(' ').slice(0, 9).join(' ') + ' @' + s.x + 'м [перед этим: ' + lastHint.slice(0, 50) + ']'); lastHint = ''; if (!(await tap('towad'))) if (!(await tap('tow'))) await tap('quit'); await p.waitForTimeout(400); continue; }
      if (s.mode === 'win' && s.res) { const l = L(s.cur); l.asst += s.asst; l.got = `${s.res.deliv}/${s.res.of}, +${s.res.total}, на руках ${s.coins}`; if (!(await tap('nextc'))) await tap('menu'); runStarted = -1; await p.waitForTimeout(500); continue; }
      if (s.mode === 'menu' && s.sel >= 0) { const l = L(s.sel); if (l.coins0 === null) l.coins0 = s.coins; if (s.adv && !s.adv.opt) { if (s.ids.includes('adv')) { await tap('adv'); await p.waitForTimeout(300); continue; } l.short = `не хватает на ${s.adv.k}: ${s.adv.price} при ${s.coins}`; }
        if (!(await tap('go'))) await tap('unsel'); await p.waitForTimeout(500); continue; }
      if (s.mode === 'menu') { const gi = s.ids.find((id) => /^c:[0-3]$/.test(id) && !(Object.values(s.stars).length > +id.slice(2))); if (gi) await tap(gi); else await tap('reg:0'); await p.waitForTimeout(300); continue; }
      if (s.mode === 'garage') { await tap('menu'); continue; }
      await p.waitForTimeout(150);
    }
    const s = await st(), done = Object.values(s.stars).filter((v) => v > 0).length; await key('ArrowRight', false);
    console.log(`\n== ${type}: пройдено заказов ${done} из 4 за ${((Date.now() - t0) / 1000).toFixed(0)} с, монет ${s.coins}${errs.length ? ', ОШИБКИ: ' + errs[0] : ''}`);
    for (const i of Object.keys(log).sort()) { const l = log[i]; console.log(`  заказ ${+i + 1}: попыток ${l.tries}, помощь игры ${l.asst}, остановок у края ${l.holds}, ${l.got || 'не довёз'}${l.short ? ' | ' + l.short : ''}${l.deaths.length ? ' | аварии: ' + l.deaths.join(' ; ') : ''}`); }
    if (done < 4 || errs.length) bad++; await ctx.close();
  }
  await b.close(); console.log(bad ? `\nНЕ ДОШЛИ: ${bad}` : '\nвсе дошли'); process.exit(bad ? 1 : 0);
})();
