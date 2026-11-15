// 3D-обложки: node tests/cover3d.render.js <папка> [lz]
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..'), OUT = process.argv[2] || path.join(ROOT, 'art/out3d'), LZ = process.argv[3] === 'lz';
fs.mkdirSync(OUT, { recursive: true });
const FILES = { '/cover3d.html': 'art/cover3d.html', '/core.js': 'core/core.js', '/three.min.js': 'vendor/three.min.js', '/r3d.js': 'online/r3d.js', '/game.js': 'online/game.js' };
const srv = http.createServer((q, r) => { const f = FILES[q.url.split('?')[0]]; if (!f) { r.writeHead(404); return r.end(); } r.writeHead(200, { 'Content-Type': f.endsWith('.html') ? 'text/html' : 'application/javascript' }); r.end(fs.readFileSync(path.join(ROOT, f))); }).listen(8124);
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--hide-scrollbars'] });
  const jobs = [['cover_1920x1080', 1920, 1080, ''], ['cover_800x1200', 800, 1200, ''], ['cover_800x800', 800, 800, ''], ['cover_v_1080x1620', 1080, 1620, ''], ['icon_512x512', 512, 512, '&icon=1']];
  for (const [name, w, h, extra] of jobs) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    p.on('pageerror', (e) => console.log('PAGEERR', name, e.message));
    await p.goto('http://localhost:8124/cover3d.html?art=1' + extra + (LZ ? '&lz=1' : ''));
    await p.waitForFunction(() => window.__done, null, { timeout: 120000 });
    await p.screenshot({ path: path.join(OUT, name + (LZ ? '_lz' : '') + '.png') });
    console.log('ok', name);
    await p.close();
  }
  await b.close(); srv.close();
})().catch((e) => { console.error(e); process.exit(1); });
