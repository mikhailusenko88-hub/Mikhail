// node render.js [test|full] [w] [h]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path');
const mode = process.argv[2] || 'test', W = +(process.argv[3] || 1920), H = +(process.argv[4] || 1080);
const FPS = 30, DUR = 10;
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: W, height: H } });
  p.on('pageerror', e => console.error('PAGE ERROR', e.message));
  p.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
  await p.goto('file://' + path.resolve('scene.html') + `?w=${W}&h=${H}`);
  await p.waitForFunction(() => window.ready, null, { timeout: 60000 });
  fs.writeFileSync('landings.json', await p.evaluate(() => window.landings));
  if (mode === 'test') {
    fs.mkdirSync('test', { recursive: true });
    for (const t of [0.3, 2.0, 4.5, 7.8, 8.6, 9.8]) {
      const t0 = Date.now();
      const d = await p.evaluate(([i, q]) => window.renderFrame(i, q), [Math.round(t * FPS), 0.95]);
      fs.writeFileSync(`test/f_${t.toFixed(1)}.jpg`, Buffer.from(d.split(',')[1], 'base64'));
      console.log(`t=${t}s: ${Date.now() - t0} ms`);
    }
  } else {
    const out = 'honey_tmp.mp4';
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-', '-vf', 'scale=1920:1080:flags=lanczos+accurate_rnd+full_chroma_int:out_color_matrix=bt709:out_range=tv,format=yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-c:v', 'libx264', '-preset', 'medium', '-b:v', '9000k', '-maxrate', '12000k', '-bufsize', '18000k', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const N = FPS * DUR, t0 = Date.now();
    for (let i = 0; i < N; i++) {
      const d = await p.evaluate(([i, q]) => window.renderFrame(i, q), [i, 0.95]);
      const buf = Buffer.from(d.split(',')[1], 'base64');
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 30 === 0) console.log(`frame ${i}/${N}, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    fs.renameSync(out, 'honey_video.mp4');
    console.log('done', ((Date.now() - t0) / 1000).toFixed(0), 's');
  }
  await b.close();
})();
