// Hook Truck: сигнал площадки «выключить звук» — общий регулятор громкости уходит в ноль и возвращается
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'] });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1, locale: 'en-US' });
  await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: 'window.__pgNoInter = true;' + fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
  const p = await ctx.newPage();
  await p.addInitScript(() => {
    window.__gains = [];
    const AC = window.AudioContext || window.webkitAudioContext; const cg = AC.prototype.createGain;
    AC.prototype.createGain = function () { const g = cg.call(this); window.__gains.push(g); return g; };
    localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [1, 1, 1], best: [], duo: false, tut: [1, 1], coins: 100, ts: 1 }));
  });
  await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(1500);
  await p.mouse.click(640, 100); await p.waitForTimeout(300);
  await p.evaluate(() => window.__hook.start(false, 0)); await p.waitForTimeout(600);
  await p.keyboard.down('ArrowRight'); await p.waitForTimeout(500);
  const g = () => p.evaluate(() => window.__gains.length ? window.__gains[0].gain.value : null);
  const a = await g();
  await p.evaluate(() => window.__pgEmit('audio_state_changed', false)); await p.waitForTimeout(300);
  const m = await g();
  await p.evaluate(() => window.__pgEmit('audio_state_changed', true)); await p.waitForTimeout(300);
  const c = await g();
  await p.evaluate(() => window.__pgEmit('pause_state_changed', true)); await p.waitForTimeout(300);
  const t0 = await p.evaluate(() => window.__hook.S.t); await p.waitForTimeout(500);
  const t1 = await p.evaluate(() => window.__hook.S.t); const pz = await g();
  await p.evaluate(() => window.__pgEmit('pause_state_changed', false)); await p.waitForTimeout(400);
  const t2 = await p.evaluate(() => window.__hook.S.t); const r = await g();
  console.log(JSON.stringify({ before: a, muted: m, back: c, pausedGain: pz, pausedDt: t1 - t0, resumedDt: t2 - t1, resumedGain: r }));
  await b.close();
})();
