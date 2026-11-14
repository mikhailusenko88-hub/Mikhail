// Скриншоты для Playgama из текущей сборки dist/flagball-pg: 3 альбомных 1920×1080 и 2 вертикальных 1080×1920.
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const DIST = path.join(__dirname, '../../dist/flagball-pg'), PORT = 8098;
const OUT = process.argv[2] || '/tmp/pgm/shots/'; fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const BOT = () => {
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
  setInterval(() => { const d = __dbgOnline(); if (!d.me.alive && d.dead && d.dead.t > 1.5) { d.dead.t = 9; __respawn(); } }, 700);
};
(async () => {
  const srv = spawn('node', [path.join(__dirname, '../../online/server.js')], { env: { ...process.env, PORT: String(PORT), TEST: '1', STATE_FILE: '/tmp/pg-shots-day.json', WATCH: '/dev/null' }, stdio: 'ignore' });
  await sleep(800);
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--hide-scrollbars', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights'] });
  async function page(view, dsf, locale, room) {
    const ctx = await b.newContext({ viewport: view, deviceScaleFactor: dsf, locale });
    await ctx.route('http://pg.local/**', async (r) => {
      const f = path.join(DIST, new URL(r.request().url()).pathname);
      if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = fs.readFileSync(f);
      if (f.endsWith('index.html')) body = Buffer.from(body.toString().replace(/wss:\/\/[^']+/, 'ws://localhost:' + PORT + '/ws'));
      r.fulfill({ status: 200, body, contentType: f.endsWith('.js') ? 'application/javascript' : f.endsWith('.json') ? 'application/json' : 'text/html' });
    });
    const p = await ctx.newPage(); p.on('pageerror', (e) => console.log('PAGEERR', e.message));
    await p.goto('http://pg.local/index.html?auto' + (room === 'main' ? '' : '&room=' + room)); await sleep(1500);
    return p;
  }
  for (const [kind, view, dsf, times] of [['land', { width: 1920, height: 1080 }, 1, [7, 12, 17]], ['port', { width: 540, height: 960 }, 2, [8, 14]]]) {
    const room = 'main';
    const p = await page(view, dsf, 'en-US', room);
    const others = [await page({ width: 400, height: 700 }, 1, 'de-DE', room), await page({ width: 400, height: 700 }, 1, 'pt-BR', room)];
    await p.evaluate(() => { const x = Core.save.extra.fb; x.on = 11; x.owned = [0, 11]; });
    await p.evaluate(() => __send({ t: 'dbg', m: 46 }));
    for (const o of others) await o.evaluate(() => __send({ t: 'dbg', m: 34 }));
    for (const q of [p, ...others]) await q.evaluate(BOT);
    let t0 = Date.now(), i = 0;
    for (const t of times) { await sleep(Math.max(0, t * 1000 - (Date.now() - t0))); await p.screenshot({ path: OUT + `${kind}_${++i}.png` }); console.log(kind, i, JSON.stringify(await p.evaluate(() => ({ m: Math.round(__dbgOnline().me.m), alive: __dbgOnline().me.alive })))); }
    await p.context().close(); for (const o of others) await o.context().close();
  }
  await b.close(); srv.kill();
})().catch((e) => { console.error(e); process.exit(1); });
