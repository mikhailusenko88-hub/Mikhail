// Hook Truck: проверка плавности. «Умелый игрок» проходит уровни; пишем по каждому:
//  - сколько времени мир шёл замедленно (обучение) — для умелого игрока должно быть 0;
//  - когда появлялись новые шейдеры (каждое появление посреди заезда = рывок на телефоне) — должны быть все до первого кадра заезда;
//  - вызовы отрисовки и треугольники; рывки (кадр дольше 2,5 медиан).
// Кадры здесь рисует программный рендер, так что сами миллисекунды с телефоном не сравнивать — сравнивать уровни между собой.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const path = require('path'), fs = require('fs');
const DIR = path.resolve(__dirname, '../../dist/hook-truck-pg');
const LV = (process.env.LV || '0,1,4').split(',').map(Number), SEC = +(process.env.SEC || 14);
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, locale: 'en-US', hasTouch: true, isMobile: true });
  await ctx.route('**/playgama-bridge.js', (r) => r.fulfill({ contentType: 'text/javascript', body: 'window.__pgNoInter = true;' + fs.readFileSync(path.join(__dirname, 'pgstub.js'), 'utf8') }));
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.addInitScript(() => { localStorage.setItem('hooktruck_v1', JSON.stringify({ stars: [], best: [], duo: false, coins: 0, ts: 1 })); });
  await p.goto('file://' + DIR + '/index.html'); await p.waitForTimeout(2500);
  const menuProg = await p.evaluate(() => window.Hook3D.info().programs);
  console.log('шейдеров после меню:', menuProg);
  for (const li of LV) {
    const r = await p.evaluate(async ([li, SEC]) => {
      const h = window.__hook, G = (window.HookSim.levels[li].guide) || null;
      h.setCtl('manual'); h.start(false, li);
      const k = h.keys, fr = []; let prev = performance.now(), t0 = prev, slow = 0, play = 0, progLog = [], lastProg = window.Hook3D.info().programs, wins = 0;
      k.ArrowRight = true;
      await new Promise((res) => {
        const tick = () => {
          const now = performance.now(), dt = now - prev; prev = now; fr.push(dt);
          const S = h.S, tr = S.truck;
          // умелый игрок: крюк зажат заранее, отпускает в первой половине «окна»
          let hook = false;
          if (S.state === 'play') {
            if (!S.rope) { const a = S.target; if (a) { const g = G && G[a.i]; hook = g && g.climb ? true : tr.x > a.x - ((g && g.att) || 300) - 140 && tr.x < a.x + 40; } }
            else { const a = S.ropeA, g = G && G[a.i], rel = tr.x - a.x; if (g && g.climb) hook = !(S.grounded && tr.y < a.y + 300 && (tr.x > a.x - 80 || S.rope.len <= 160)); else { const lo = g ? g.lo : 120, hi = g ? g.hi : 320; hook = !(tr.vx > 0 && rel >= lo + (hi - lo) * 0.3); } }
            play += dt; if (h.ts < 0.95) slow += dt;
          } else if (S.state === 'win') wins++;
          k.Space = hook;
          const pr = window.Hook3D.info().programs; if (pr !== lastProg) { progLog.push([+((now - t0) / 1000).toFixed(1), pr]); lastProg = pr; }
          if (now - t0 > SEC * 1000 || h.mode === 'win') return res();
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      k.ArrowRight = false; k.Space = false;
      const s = fr.slice(3).sort((a, b) => a - b), med = s[s.length >> 1], hitch = fr.slice(3).filter((d) => d > med * 2.5).length, inf = window.Hook3D.info();
      return { lvl: li + 1, won: h.mode === 'win', sec: +((prev - t0) / 1000).toFixed(1), frames: fr.length, medMs: +med.toFixed(1), maxMs: +s[s.length - 1].toFixed(0), hitch, slowSec: +(slow / 1000).toFixed(2), slowPct: Math.round((100 * slow) / Math.max(1, play)), newShaders: progLog, calls: inf.calls, tris: inf.tris };
    }, [li, SEC]);
    console.log(JSON.stringify(r));
    await p.evaluate(() => { const b = window.__hook.buttons.find((q) => q.id === 'menu'); }); await p.waitForTimeout(300);
  }
  console.log(errs.length ? errs.slice(0, 5) : 'без ошибок'); await b.close();
})();
