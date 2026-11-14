// Ролики-превью для CrazyGames: 16:9 (1920×1080) и 2:3 (1080×1620), 15–20 с, без звука и курсора.
// Игрок ведётся простым ботом: ест точки и тех, кто меньше, убегает от больших.
// Кадры — снимки экрана через CDP, потом ffmpeg (первый кадр — обложка).
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const fs = require('fs');
const { execSync } = require('child_process');
const OUT = '/home/claude/games/art/out/';
const which = process.argv[2] || 'land';
const CFG = which === 'land'
  ? { view: { width: 1920, height: 1080 }, dsf: 1, size: '1920x1080', cover: OUT + 'cover_1920x1080.png' }
  : { view: { width: 720, height: 1080 }, dsf: 1.5, size: '1080x1620', cover: null };
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--hide-scrollbars'] });
  const ctx = await b.newContext({ viewport: CFG.view, deviceScaleFactor: CFG.dsf, locale: 'en-US' });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => console.log('PAGEERR', e.message));
  // второй игрок — чтобы в таблице были живые
  const p2 = await (await b.newContext({ viewport: { width: 400, height: 700 }, locale: 'de-DE' })).newPage();
  const room = 'rec' + Date.now() % 100000;
  await p.goto(`http://localhost:8770/index.html?auto&room=${room}`);
  await p2.goto(`http://localhost:8770/index.html?auto&room=${room}`);
  await p.waitForTimeout(1500);
  await p.evaluate(() => { const x = Core.save.extra.fb; x.on = 11; x.owned = [0, 11]; });
  await p.evaluate(() => __send({ t: 'dbg', m: 46 }));
  await p2.evaluate(() => __send({ t: 'dbg', m: 30 }));
  const bot = () => {
    window.__bot = (me, balls) => {
      let ax = 0, ay = 0, best = null, bd = 1e9;
      const my = __dbgOnline().myId;
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
  await p.evaluate(bot);
  await p.waitForTimeout(1500);
  // запись кадров
  const dir = '/tmp/frames_' + which; fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir);
  const cdp = await ctx.newCDPSession(p);
  const frames = [];
  cdp.on('Page.screencastFrame', async (f) => { frames.push({ t: f.metadata.timestamp, data: f.data }); try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) { /* */ } });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, everyNthFrame: 1, maxWidth: CFG.view.width * CFG.dsf, maxHeight: CFG.view.height * CFG.dsf });
  await p.waitForTimeout(18500);
  await cdp.send('Page.stopScreencast');
  console.log('frames', frames.length, 'state', JSON.stringify(await p.evaluate(() => { const d = __dbgOnline(); return { m: Math.round(d.me.m), alive: d.me.alive, banner: d.banner, coins: d.coins }; })));
  // ровно 30 кадров/с: каждый момент — последний пришедший кадр
  const t0 = frames[0].t, list = [];
  frames.forEach((f, i) => { const fn = `${dir}/f${String(i).padStart(5, '0')}.jpg`; fs.writeFileSync(fn, Buffer.from(f.data, 'base64')); list.push({ fn, t: f.t - t0 }); });
  let txt = '';
  for (let i = 0; i < list.length; i++) { const dur = i + 1 < list.length ? list[i + 1].t - list[i].t : 1 / 30; txt += `file '${list[i].fn}'\nduration ${Math.max(0.001, dur).toFixed(4)}\n`; }
  txt += `file '${list[list.length - 1].fn}'\n`;
  fs.writeFileSync(dir + '/list.txt', txt);
  await b.close();
  const [W, H] = CFG.size.split('x');
  const raw = `/tmp/raw_${which}.mp4`;
  execSync(`ffmpeg -y -loglevel error -f concat -safe 0 -i ${dir}/list.txt -vf "scale=${W}:${H}:flags=lanczos,fps=30" -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -an ${raw}`);
  // обложка первым кадром (0,5 с) и плавный переход в игру
  const cover = CFG.cover || OUT + 'cover_v_1080x1620.png';
  const out = OUT + `preview_${which === 'land' ? '16x9_1920x1080' : '2x3_1080x1620'}.mp4`;
  execSync(`ffmpeg -y -loglevel error -loop 1 -t 1.0 -i ${cover} -i ${raw} -filter_complex "[0:v]scale=${W}:${H},fps=30,format=yuv420p,settb=1/30[c];[1:v]trim=0:18,setpts=PTS-STARTPTS,fps=30,settb=1/30[g];[c][g]xfade=transition=fade:duration=0.5:offset=0.5,format=yuv420p" -c:v libx264 -preset veryfast -crf 18 -an -movflags +faststart ${out}`);
  console.log('saved', out, (fs.statSync(out).size / 1e6).toFixed(1) + ' MB');
})();
