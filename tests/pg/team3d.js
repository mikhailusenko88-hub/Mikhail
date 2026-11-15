// команды и окно правил в 3D: хозяин включает «2 команды», сильных ботов; второй игрок заходит в ту же комнату
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const DIST = path.join(__dirname, '../../dist/flagball-pg'), PORT = 8097, OUT = '/tmp/fb3d/team/';
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const srv = spawn('node', [path.join(__dirname, '../../online/server.js')], { env: { ...process.env, PORT: String(PORT), TEST: '1', STATE_FILE: '/tmp/fb3d/day.json', WATCH: '/dev/null' }, stdio: 'ignore' });
  await sleep(800);
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights'] });
  async function page(view, dsf, locale, room) {
    const ctx = await b.newContext({ viewport: view, deviceScaleFactor: dsf, locale });
    await ctx.route('http://pg.local/**', async (r) => {
      const f = path.join(DIST, new URL(r.request().url()).pathname);
      if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = fs.readFileSync(f);
      if (f.endsWith('index.html')) body = Buffer.from(body.toString().replace(/wss:\/\/[^']+/, 'ws://localhost:' + PORT + '/ws'));
      r.fulfill({ status: 200, body, contentType: f.endsWith('.js') ? 'application/javascript' : f.endsWith('.json') ? 'application/json' : 'text/html' });
    });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', (e) => { errs.push(e.message); console.log('PAGEERR', e.message); });
    await p.goto('http://pg.local/index.html?auto&room=' + room); await sleep(1500); p.errs = errs;
    return p;
  }
  const A = await page({ width: 1280, height: 720 }, 1.5, 'ru-RU', 'tm123');
  const B = await page({ width: 400, height: 760 }, 2, 'en-US', 'tm123');
  const Cp = await page({ width: 400, height: 760 }, 1, 'de-DE', 'tm123');
  await A.evaluate(() => { const x = Core.save.extra.fb; x.on = 3; });
  await A.evaluate(() => __send({ t: 'cfg', cfg: { mode: 1, diff: 2, bots: 3 } }));
  await sleep(1500);
  await A.evaluate(() => __send({ t: 'dbg', m: 60 })); await B.evaluate(() => __send({ t: 'dbg', m: 45 }));
  await sleep(2500);
  await A.screenshot({ path: OUT + 'host_land.png' });
  await B.screenshot({ path: OUT + 'guest_port.png' });
  await A.evaluate(() => __cfgBox()); await sleep(400); await A.screenshot({ path: OUT + 'cfg_host.png' });
  await B.evaluate(() => __cfgBox()); await sleep(400); await B.screenshot({ path: OUT + 'cfg_guest.png' });
  const info = await A.evaluate(() => ({ r3d: window.FB3D && FB3D.info(), me: __dbgOnline().me.alive, cfg: null }));
  console.log(JSON.stringify(info), 'errors', A.errs.length + B.errs.length + Cp.errs.length);
  await b.close(); srv.kill();
})().catch((e) => { console.error(e); process.exit(1); });
