// Обложки и скриншоты «Mud Haul» для Playgama: грузовик едет сам (газ и все кнопки), в нужном месте мир замирает; заголовок — поверх кадра.
// node tests/g9/promo.js [папка] [имена кадров через пробел]
const { chromium } = require('/opt/npm-tools/node_modules/playwright'); const path = require('path'), fs = require('fs');
const PAGE = 'file://' + path.resolve(__dirname, '../../dist/mud-side/index.html') + '?en', OUT = process.argv[2] || '/tmp/promo9'; fs.mkdirSync(OUT, { recursive: true });
const ALL = ['village', 'farm', 'creek', 'pit', 'mill', 'bog', 'layers', 'dunes', 'wetclay', 'windows', 'twofords', 'longhaul', 'pass', 'stones', 'mine', 'scree', 'gorge'];
const own = { awd: [1], lock: [1], low: [1], base: [1, 2], lift: [1, 2], wheel: [1, 2], axles: [3], tires: [1, 2], eng: [1, 2, 3, 4, 5], snorkel: [1], tank: [1], winch: [1], ctis: [1], skid: [1], trailer: [1, 2] };
const SAVE = (b, coins = 3460, n = 17) => ({ coins, own, build: Object.assign({ awd: 1, lock: 1, low: 1, base: 1, lift: 1, wheel: 2, axles: 3, tires: 2, eng: 4, snorkel: 1, tank: 1, winch: 1, skid: 1 }, b || {}), stars: Object.fromEntries(ALL.slice(0, n).map((k, i) => [k, 1 + (i % 3)])), seen: { first: 1, awd: 1, lock: 1, low: 1 }, tl: { awd: 3, lock: 3, low: 3 }, ts: 1 });
// [имя, размер, заказ, условие замирания, камера, заголовок, чистый кадр, сборка]
const SHOTS = [
  ['cover_16x9', [1920, 1080], 6, 'S.inMud > 0 && T.x > 1300 && Math.abs(T.vx) > 30', { Z: 2.1, dx: 200, oy: 0.04 }, 'land', true],
  ['cover_9x16', [1080, 1920], 6, 'S.inMud > 0 && T.x > 1300 && Math.abs(T.vx) > 30', { Z: 2.5, dx: 20, oy: 0.17 }, 'port', true],
  ['cover_1x1', [800, 800], 6, 'S.inMud > 0 && T.x > 1300 && Math.abs(T.vx) > 30', { Z: 1.35, dx: 30, oy: 0.06 }, 'sq', true],
  ['shot1_taiga', [1920, 1080], 4, 'S.inMud > 0 && T.x > 900 && Math.abs(T.vx) > 30', { Z: 1.25 }, null, false],
  ['shot2_ford', [1920, 1080], 10, 'S.wade > 0 && T.x > 600', { Z: 1.25 }, null, false],
  ['shot3_pass', [1920, 1080], 12, 'T.x > 1500 && Math.sin(T.a) > 0.12 && S.grounded', { Z: 1.25 }, null, false, { trailer: 0 }],
  ['shot4_dunes', [1920, 1080], 7, "S.soil === 'sand' && T.x > 900", { Z: 1.25 }, null, false],
];
const TITLE = { land: [210, 0.07, 0.5, 0.48], port: [230, 0.06, 0, 1], sq: [118, 0.05, 0, 1] };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] }); const only = process.argv.slice(3);
  const open = async ([w, h], save) => { const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'en-US' }); await p.addInitScript((s) => localStorage.setItem('mud4.save', JSON.stringify(s)), save);
    await p.goto(PAGE); await p.waitForFunction(() => window.__mud && window.__mud.S); await p.waitForTimeout(1200); return p; };
  for (const [name, size, ci, cond, cam, title, clean, bld] of SHOTS.filter((q) => !only.length || only.includes(q[0]))) {
    const p = await open(size, SAVE(bld));
    await p.evaluate(([ci, cond]) => { const m = window.__mud; m.press('c:' + ci); m.press('lg='); m.press('go'); const test = new Function('S', 'T', 'return ' + cond);
      window.__ap = setInterval(() => { const S = m.S, T = S.truck; if (m.mode !== 'play') return; for (const k of ['awd', 'lock', 'low']) if (S.cfg.b[k] && !m.sw[k]) m.sw[k] = true; m.keys.ArrowRight = true;
        if (S.t > 1 && test(S, T)) { m.dbg.freeze = true; clearInterval(window.__ap); window.__got = true; } }, 5); }, [ci, cond]);
    const ok = await p.waitForFunction(() => window.__got, null, { timeout: 240000 }).then(() => true).catch(() => false);
    await p.evaluate(([cam, clean]) => { const m = window.__mud; m.keys.ArrowRight = false; if (cam) Object.assign(m.dbg, cam); m.dbg.clean = clean; }, [cam, clean]); await p.waitForTimeout(3500);
    if (title) { const [fs2, top, lx, bw] = TITLE[title], [w, h] = size;
      await p.evaluate(([fs2, top, lx, bw, w, h]) => { const d = document.createElement('div');
        d.style.cssText = `position:fixed;left:${Math.round(lx * w)}px;width:${Math.round(bw * w)}px;top:${Math.round(top * h)}px;text-align:center;z-index:9;font:900 ${fs2}px/0.92 Inter,system-ui,sans-serif;letter-spacing:3px;color:#ffca28;-webkit-text-stroke:${Math.round(fs2 / 14)}px #4e2a12;paint-order:stroke fill;text-shadow:0 ${Math.round(fs2 / 18)}px 0 #3b1f0c`;
        d.innerHTML = 'MUD<br>HAUL'; document.body.appendChild(d); }, [fs2, top, lx, bw, w, h]); await p.waitForTimeout(200); }
    await p.screenshot({ path: path.join(OUT, name + '.png') }); console.log(name, ok ? 'ok' : 'НЕ ДОЖДАЛСЯ'); await p.close();
  }
  if (!only.length || only.includes('shot5_garage')) { const p = await open([1920, 1080], SAVE({ base: 2, trailer: 2, axles: 3, eng: 5, paint: 2 })); await p.evaluate(() => window.__mud.press('gar')); await p.waitForTimeout(2500); await p.screenshot({ path: path.join(OUT, 'shot5_garage.png') }); console.log('shot5_garage ok'); await p.close(); }
  if (!only.length || only.includes('shot6_contracts')) { const p = await open([1920, 1080], SAVE(null, 3460, 14)); await p.evaluate(() => window.__mud.press('reg:2')); await p.waitForTimeout(400); await p.evaluate(() => window.__mud.press('c:17')); await p.waitForTimeout(2200); await p.screenshot({ path: path.join(OUT, 'shot6_contracts.png') }); console.log('shot6_contracts ok'); await p.close(); }
  await b.close();
})();
