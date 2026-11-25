// Грязь 3D — в настоящем браузере: кадры на трёх размерах, скорость кадра, проезд автопилотом (шаги считаем прямо в странице), ошибок в консоли быть не должно.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/mud-3d'), OUT = process.argv[2] || '/tmp/mud3d';
const SIZES = { phone: [390, 844, true], land: [844, 390, true], desk: [1280, 720, false], sq: [600, 600, true] };
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const name of process.argv.slice(3).length ? process.argv.slice(3) : ['phone']) {
    const [w, h, touch] = SIZES[name];
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ru-RU', hasTouch: touch, isMobile: touch });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message)); p.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 200)));
    const t0 = Date.now(); await p.goto('file://' + DIR + '/index.html'); await p.waitForFunction(() => window.__mud3, null, { timeout: 60000 }); const load = Date.now() - t0;
    await p.waitForTimeout(2500); await p.screenshot({ path: path.join(OUT, name + '-0start.png') });
    const perf = await p.evaluate(() => new Promise((res) => { let n = 0; const t = performance.now(); const f = () => { n++; if (performance.now() - t < 3000) requestAnimationFrame(f); else { const i = window.__mud3.renderer.info; res({ ms: +((performance.now() - t) / n).toFixed(0), calls: i.render.calls, tris: i.render.triangles, progs: i.programs.length }); } }; requestAnimationFrame(f); }));
    // автопилот: едет по ломаной, сам включает помощников; шаги считаем сразу пачкой, игра в это время стоит
    const go = (pathName, smart, sec, stopAt) => p.evaluate(([pathName, smart, sec, stopAt]) => {
      const m = window.__mud3, S = m.S, map = S.map, P = map[pathName]; m.dbg.freeze = true; let seg = m._seg && m._path === pathName ? m._seg : 1; m._path = pathName; let t = 0;
      while (t < sec && S.state === 'play') {
        while (seg < P.length - 1 && Math.hypot(P[seg][0] - S.p[0], P[seg][1] - S.p[2]) < 9) seg++;
        let d = Math.atan2(P[seg][0] - S.p[0], P[seg][1] - S.p[2]) - S.yaw(); while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
        const mu = S.mudNow; if (smart) { m.sw.awd = mu > 0.12 || S.stuckT > 0.5; m.sw.lock = mu > 0.45; m.sw.low = mu > 0.25 || S.stuckT > 1; }
        const gd = Math.hypot(map.goal.x - S.p[0], map.goal.z - S.p[2]);
        S.step({ drive: gd < 11 ? 0 : 1, hb: gd < 11, steer: Math.max(-1, Math.min(1, d * 2.2)), awd: m.sw.awd, lock: m.sw.lock, low: m.sw.low }); t += 1 / 120;
        if (stopAt && stopAt(S)) break;
      }
      m._seg = seg; return { at: [Math.round(S.p[0]), Math.round(S.p[2])], st: S.state, t: +S.t.toFixed(0), mud: +S.mudNow.toFixed(2), stuck: +S.stuckT.toFixed(1), fuel: Math.round(S.fuel), flag: S.flag };
    }, [pathName, smart, sec, null]);
    const snap = async (tag) => { await p.evaluate(() => { const m = window.__mud3; m.keys.KeyW = true; }); await p.waitForTimeout(1600); await p.screenshot({ path: path.join(OUT, `${name}-${tag}.png`) }); await p.evaluate(() => { window.__mud3.keys.KeyW = false; }); };
    const log = [];
    if (name === 'land' || name === 'sq') { log.push(await go('road', false, 30)); await snap('1stuck'); log.push(await go('road', true, 6)); await snap('2aids'); }
    else if (name === 'desk') { log.push(await go('road', true, 14)); await snap('1wash'); log.push(await go('road', true, 22)); await snap('2ford'); log.push(await go('road', true, 60)); await p.evaluate(() => { window.__mud3.dbg.freeze = false; }); await p.waitForTimeout(2500); await p.screenshot({ path: path.join(OUT, name + '-9win.png') }); }
    else { log.push(await go('trail', true, 12)); await snap('1trail'); log.push(await go('trail', true, 22)); await snap('2swamp'); log.push(await go('trail', true, 30)); await snap('3creek'); log.push(await go('trail', true, 80)); await p.evaluate(() => { window.__mud3.dbg.freeze = false; }); await p.waitForTimeout(2500); await p.screenshot({ path: path.join(OUT, name + '-9win.png') }); }
    console.log(name, 'загрузка', load, 'мс, кадр', JSON.stringify(perf), '\n ', log.map((q) => JSON.stringify(q)).join('\n  '), '\n ', errs.length ? errs.slice(0, 4) : 'без ошибок');
    await ctx.close();
  }
  await b.close();
})();
