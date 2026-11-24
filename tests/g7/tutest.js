// Обучение на первом уровне «как новичок»: жмём только тогда, когда игра просит, и отпускаем, когда просит. Должны пройти уровень.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path');
const DIR = path.resolve(__dirname, '../../' + (process.env.HOOK_DIR || 'g8-hook3d')), OUT = process.argv[2] || '/tmp/tut';
require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const [name, w, h, lvl] of [['phone', 390, 844, 0], ['desk', 1280, 720, 0], ['phone2', 390, 844, 1]].filter((q) => !process.argv[3] || process.argv.slice(3).includes(q[0]))) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: w < 900, isMobile: w < 900 });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(900);
    await p.evaluate((lvl) => window.__hook.start(false, lvl), lvl); await p.waitForTimeout(700);
    const st = () => p.evaluate(() => { const H = window.__hook, S = H.S; return { mode: H.mode, wait: H.wait, tut: H.tut, ts: +H.ts.toFixed(2), rope: !!S.rope, x: Math.round(S.truck.x), state: S.state, t: +S.t.toFixed(2), att: S.attempts }; });
    const log = []; let shots = 0, down = false;
    const shot = async (n) => { await p.screenshot({ path: path.join(OUT, `${name}-${++shots}${n}.png`) }); };
    let q = await st(); log.push('старт: ' + JSON.stringify(q)); await shot('go');
    await p.mouse.move(w / 2, h * 0.6); await p.mouse.down(); await p.waitForTimeout(120); await p.mouse.up(); // «нажми — поехали»: короткое нажатие
    const seen = {}; const t0 = Date.now();
    let lastLog = 0;
    while (Date.now() - t0 < 40000) {
      if (Date.now() - lastLog > 4000) { lastLog = Date.now(); console.error(name, JSON.stringify(await st())); }
      q = await st(); if (q.mode === 'win') break;
      if (q.state !== 'play') { if (!seen['d' + q.att]) { seen['d' + q.att] = 1; console.error('  упал при x=' + q.x + ' попытка ' + q.att); } if (down) { await p.mouse.up(); down = false; } await p.waitForTimeout(60); continue; }
      if (q.wait) { await p.mouse.down(); await p.waitForTimeout(80); await p.mouse.up(); continue; }
      if (q.tut === 'hold' && !down) { const first = !seen['hold' + q.rope]; seen['hold' + q.rope] = 1; await p.waitForTimeout(lvl ? 300 : first ? 350 : 0); /* реакция человека */ if (first && !lvl) { log.push('просит держать: ' + JSON.stringify(await st())); await shot('hold'); } await p.mouse.down(); down = true; if (first && lvl) await shot('hold'); }
      else if (q.tut === 'rel' && down && (lvl > 0 || q.ts <= 0.45)) { if (!seen.rel) { seen.rel = 1; await p.waitForTimeout(lvl ? 300 : 450); if (!lvl) { log.push('просит отпустить: ' + JSON.stringify(await st())); await shot('rel'); } } else await p.waitForTimeout(lvl ? 300 : 350); /* как человек: треть секунды на реакцию */ if (lvl && !seen['r' + q.x]) { seen['r' + q.x] = 1; console.error('  отпускает при x=' + q.x + ' попытка ' + q.att); } await p.mouse.up(); down = false; }
      await p.waitForTimeout(25);
    }
    await p.waitForTimeout(1500); await shot('end');
    console.log(name, 'уровень', lvl + 1, q.mode === 'win' ? 'ПРОЙДЕН новичком, попыток ' + q.att : 'НЕ ПРОЙДЕН ' + JSON.stringify(q), errs.length ? errs.slice(0, 3) : 'без ошибок', '\n ' + log.join('\n '));
    await ctx.close();
  }
  await b.close();
})();
