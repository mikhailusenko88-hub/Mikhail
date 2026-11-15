// Ролики-превью Flagball Arena в 3D: 16:9 (1920×1080) и 2:3 (1080×1620), ~18 с, без звука.
// В облаке нет видеокарты, 3D рисуется медленно, поэтому мир замедлен в 5 раз (сервер TIME_SCALE и часы страницы),
// пишем кадры как есть, а потом ускоряем видео обратно в 5 раз — получается ровные 30 кадров/с.
// node tests/fb.video3d.js land|port
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const fs = require('fs'), path = require('path');
const { execSync, spawn } = require('child_process');
const ROOT = path.join(__dirname, '..'), DIST = path.join(ROOT, 'dist/flagball-pg'), OUT = path.join(ROOT, 'art/out/');
const which = process.argv[2] || 'land', SLOW = 0.12, PORT = 8096, LEN = 18.5;
const CFG = which === 'land'
  ? { view: { width: 1920, height: 1080 }, dsf: 1, size: '1920x1080', cover: OUT + 'cover_1920x1080.png', out: 'preview_16x9_1920x1080.mp4' }
  : { view: { width: 720, height: 1080 }, dsf: 1.5, size: '1080x1620', cover: OUT + 'cover_v_1080x1620.png', out: 'preview_2x3_1080x1620.mp4' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const srv = spawn('node', [path.join(ROOT, 'online/server.js')], { env: { ...process.env, PORT: String(PORT), TEST: '1', TIME_SCALE: String(SLOW), STATE_FILE: '/tmp/fbvid-day.json', WATCH: '/dev/null' }, stdio: 'ignore' });
  await sleep(800);
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--hide-scrollbars', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights'] });
  const slowClock = (S) => { const p0 = performance.now(), rn = performance.now.bind(performance); performance.now = () => p0 + (rn() - p0) * S; const raf = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = (cb) => raf((t) => cb(p0 + (t - p0) * S)); };
  async function page(view, dsf, locale, room, flat) {
    const ctx = await b.newContext({ viewport: view, deviceScaleFactor: dsf, locale });
    await ctx.addInitScript(slowClock, SLOW);
    await ctx.route('http://pg.local/**', async (r) => {
      const f = path.join(DIST, new URL(r.request().url()).pathname);
      if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = fs.readFileSync(f);
      if (f.endsWith('index.html')) body = Buffer.from(body.toString().replace(/wss:\/\/[^']+/, 'ws://localhost:' + PORT + '/ws'));
      r.fulfill({ status: 200, body, contentType: f.endsWith('.js') ? 'application/javascript' : f.endsWith('.json') ? 'application/json' : 'text/html' });
    });
    const p = await ctx.newPage(); p.on('pageerror', (e) => console.log('PAGEERR', e.message));
    await p.goto('http://pg.local/index.html?auto&room=' + room + (flat ? '&flat=1' : ''));
    return p;
  }
  const room = 'main'; // свой сервер на время записи — общая арена без подписи «своя комната»
  const p = await page(CFG.view, CFG.dsf, 'en-US', room);
  const p2 = await page({ width: 400, height: 700 }, 1, 'de-DE', room, true); // второй живой игрок (в 2D — не грузит процессор)
  await sleep(4000);
  await p.evaluate(() => { const x = Core.save.extra.fb; x.on = 11; x.owned = [0, 11]; });
  await p.evaluate(() => __send({ t: 'dbg', m: 46 })); await p2.evaluate(() => __send({ t: 'dbg', m: 30 }));
  const bot = () => {
    window.__bot = (me, balls) => {
      let ax = 0, ay = 0, best = null, bd = 1e9; const my = __dbgOnline().myId;
      for (const b of balls.values()) {
        if (!b.alive || b.id === my) continue;
        const dx = b.x - me.x, dy = b.y - me.y, d = Math.hypot(dx, dy) || 1;
        if (b.r > me.r * 1.1 && d < b.r + me.r + 260) { ax -= (dx / d) * 3; ay -= (dy / d) * 3; }
        else if (me.r > b.r * 1.15 && d < 1100 && d < bd) { bd = d; best = b; }
      }
      const o = __objs();
      if (me.r > 55) for (const s of o.saws) { const dx = s.x - me.x, dy = s.y - me.y, d = Math.hypot(dx, dy) || 1; if (d < me.r + 170) { ax -= (dx / d) * 2; ay -= (dy / d) * 2; } }
      if (!best) { for (const d of o.dots.values()) { if (d.hid) continue; const dd = Math.hypot(d.x - me.x, d.y - me.y); if (dd < bd) { bd = dd; best = d; } } }
      if (best) { const dx = best.x - me.x, dy = best.y - me.y, d = Math.hypot(dx, dy) || 1; ax += dx / d; ay += dy / d; }
      const l = Math.hypot(ax, ay) || 1; return [ax / l, ay / l];
    };
  };
  await p.evaluate(bot); await p2.evaluate(bot);
  await sleep(6000);
  const dir = '/tmp/frames3d_' + which; fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir);
  const cdp = await p.context().newCDPSession(p);
  const frames = [];
  cdp.on('Page.screencastFrame', async (f) => { frames.push({ t: f.metadata.timestamp, data: f.data }); try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) { /* */ } });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, everyNthFrame: 1, maxWidth: CFG.view.width * CFG.dsf, maxHeight: CFG.view.height * CFG.dsf });
  await sleep((LEN / SLOW) * 1000);
  await cdp.send('Page.stopScreencast');
  console.log('frames', frames.length, 'fps(game time)', (frames.length / LEN).toFixed(1), JSON.stringify(await p.evaluate(() => { const d = __dbgOnline(); return { m: Math.round(d.me.m), alive: d.me.alive, r3d: window.FB3D && FB3D.ok }; })));
  const t0 = frames[0].t, list = [];
  frames.forEach((f, i) => { const fn = `${dir}/f${String(i).padStart(5, '0')}.jpg`; fs.writeFileSync(fn, Buffer.from(f.data, 'base64')); list.push({ fn, t: (f.t - t0) * SLOW }); });
  let txt = '';
  for (let i = 0; i < list.length; i++) { const dur = i + 1 < list.length ? list[i + 1].t - list[i].t : 1 / 30; txt += `file '${list[i].fn}'\nduration ${Math.max(0.001, dur).toFixed(4)}\n`; }
  txt += `file '${list[list.length - 1].fn}'\n`;
  fs.writeFileSync(dir + '/list.txt', txt);
  await b.close(); srv.kill();
  const [W, H] = CFG.size.split('x');
  const raw = `/tmp/raw3d_${which}.mp4`;
  execSync(`ffmpeg -y -loglevel error -f concat -safe 0 -i ${dir}/list.txt -vf "scale=${W}:${H}:flags=lanczos,fps=30" -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -an ${raw}`);
  const out = OUT + CFG.out;
  execSync(`ffmpeg -y -loglevel error -loop 1 -t 1.0 -i ${CFG.cover} -i ${raw} -filter_complex "[0:v]scale=${W}:${H},fps=30,format=yuv420p,settb=1/30[c];[1:v]trim=0:18,setpts=PTS-STARTPTS,fps=30,settb=1/30[g];[c][g]xfade=transition=fade:duration=0.5:offset=0.5,format=yuv420p" -c:v libx264 -preset veryfast -crf 18 -an -movflags +faststart ${out}`);
  console.log('saved', out, (fs.statSync(out).size / 1e6).toFixed(1) + ' MB');
})().catch((e) => { console.error(e); process.exit(1); });
