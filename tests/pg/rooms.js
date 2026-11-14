// Проверка сборки для Playgama (dist/flagball-pg): «Играть с друзьями» — комната по коду.
// Свой сервер на ws://localhost:8097, страница игры — http://pg.local (мост видит неизвестную площадку → mock).
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const DIST = path.join(__dirname, '../../dist/flagball-pg');
const PORT = 8097, SHOTS = path.join(__dirname, 'shots');
fs.mkdirSync(SHOTS, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const srv = spawn('node', [path.join(__dirname, '../../online/server.js')], { env: { ...process.env, PORT: String(PORT), TEST: '1', STATE_FILE: '/tmp/pg-day.json', WATCH: '/dev/null' }, stdio: 'ignore' });
  await sleep(800);
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--autoplay-policy=no-user-gesture-required', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights'] });
  const res = []; const ok = (name, cond, extra) => { res.push((cond ? 'OK  ' : 'FAIL') + ' ' + name + (extra ? ' — ' + extra : '')); };
  async function page(locale, noBridge) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, locale });
    await ctx.route('http://pg.local/**', async (r) => {
      const f = path.join(DIST, new URL(r.request().url()).pathname.replace(/^\/$/, '/index.html'));
      if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' });
      let body = fs.readFileSync(f);
      if (f.endsWith('index.html')) body = Buffer.from(body.toString().replace(/wss:\/\/[^']+/, 'ws://localhost:' + PORT + '/ws'));
      if (noBridge && f.endsWith('playgama-bridge.js')) body = Buffer.from('');
      r.fulfill({ status: 200, body, contentType: f.endsWith('.js') ? 'application/javascript' : f.endsWith('.json') ? 'application/json' : 'text/html' });
    });
    const p = await ctx.newPage(); p.errs = []; p.on('pageerror', (e) => p.errs.push(e.message));
    await p.goto('http://pg.local/index.html');
    return p;
  }
  const humans = (p) => p.evaluate(() => window.__balls().filter((x) => x.human).length);
  const inGame = (p) => p.waitForFunction(() => window.__balls && window.__balls().some((x) => x.human), null, { timeout: 15000 });
  // кнопка «Позвать» на холсте справа внизу — кликаем по её месту, как человек
  async function clickInvite(p) {
    const pt = await p.evaluate(() => { const C = window.Core, L = C.H < 1000, S = L ? 72 : 86; return { x: (C.W - 20 - S / 2) * C.scale, y: (C.H - 58 - S / 2) * C.scale }; });
    await p.mouse.click(pt.x, pt.y); await sleep(200);
  }
  const A = await page('en-US'), B = await page('ru-RU');
  await inGame(A); await inGame(B); await sleep(1500);
  ok('на площадке сразу в игре, A и B в общей арене', (await humans(A)) === 2 && (await humans(B)) === 2, (await humans(A)) + '/' + (await humans(B)));
  await A.screenshot({ path: SHOTS + '/0-A-main-hud.png' });
  await clickInvite(A);
  ok('кнопка «Invite» на холсте открывает окно', await A.isVisible('#rbox'));
  await A.screenshot({ path: SHOTS + '/1-box-main.png' });
  await A.click('#rbMine button'); await sleep(250);
  const code = (await A.evaluate(() => document.querySelector('#rbMine div div:nth-child(2)').textContent)).trim();
  ok('код из 5 знаков', /^[A-Z0-9]{5}$/.test(code), code);
  await A.screenshot({ path: SHOTS + '/2-box-code.png' });
  await A.click('#rbX'); await sleep(2500);
  ok('A в своей комнате один', (await humans(A)) === 1, String(await humans(A)));
  ok('B в общей арене один', (await humans(B)) === 1, String(await humans(B)));
  await A.screenshot({ path: SHOTS + '/3-A-in-room.png' });
  await clickInvite(B);
  ok('у B окно по-русски', /друзьями/.test(await B.textContent('#rbT')), await B.textContent('#rbT'));
  await B.fill('#rbI', 'ab'); await B.click('#rbGo');
  ok('неверный код — подсказка', /5/.test(await B.textContent('#rbE')), await B.textContent('#rbE'));
  await B.fill('#rbI', code.toLowerCase()); await B.click('#rbGo'); await sleep(250);
  ok('B видит тот же код', (await B.textContent('#rbMine')).indexOf(code) >= 0);
  await B.screenshot({ path: SHOTS + '/4-B-box-in-room.png' });
  await B.click('#rbX'); await sleep(2500);
  ok('A видит 2 живых', (await humans(A)) === 2, String(await humans(A)));
  ok('B видит 2 живых', (await humans(B)) === 2, String(await humans(B)));
  await B.screenshot({ path: SHOTS + '/5-B-in-room.png' });
  await clickInvite(B); const btns = await B.$$('#rbMine button'); await btns[btns.length - 1].click(); await sleep(2500);
  ok('B вернулся в общую арену, у A снова 1', (await humans(A)) === 1 && (await humans(B)) === 1, (await humans(A)) + '/' + (await humans(B)));
  // свой сайт без моста: окно страны с кнопкой «Играть с друзьями»
  const Cp = await page('ru-RU', true); await Cp.waitForSelector('#join', { state: 'visible', timeout: 15000 });
  ok('свой сайт: в окне страны есть «Играть с друзьями»', await Cp.isVisible('#fr'), await Cp.textContent('#fr'));
  await Cp.click('#fr'); await Cp.fill('#rbI', code); await Cp.click('#rbGo'); await sleep(200);
  const pb = await Cp.$$('#rbMine button'); await pb[pb.length - 1].click(); await sleep(2500);
  ok('свой сайт: вошёл по коду прямо из окна страны, у A 2 живых', (await humans(A)) === 2, String(await humans(A)));
  ok('без ошибок на странице', !A.errs.length && !B.errs.length && !Cp.errs.length, A.errs.concat(B.errs, Cp.errs).join(' | '));
  console.log(res.join('\n'));
  await b.close(); srv.kill();
})().catch((e) => { console.error(e); process.exit(1); });
