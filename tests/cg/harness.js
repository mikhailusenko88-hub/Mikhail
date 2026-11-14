// «Копия CrazyGames» для проверки сборки dist/flagball:
// игра открывается внутри страницы www.crazygames.com в iframe с адреса games.crazygames.com,
// вместо настоящего SDK — заглушка с теми же методами (пользователь, язык, реклама, комнаты, звук).
const { chromium } = require('/opt/npm-tools/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const DIST = process.env.DIST || path.join(__dirname, '../../dist/flagball');
const WSS = process.env.WSS || 'wss://localhost:8443/ws';
const GAME_URL = 'https://games.crazygames.com/en_US/flagball-arena/index.html';

function mockSdk(cfg) {
  return `(() => {
  const CFG = ${JSON.stringify(cfg)};
  const log = (window.__cgLog = []);
  const L = (n, a) => { log.push([Math.round(performance.now()), n, a === undefined ? null : JSON.parse(JSON.stringify(a))]); };
  const joinL = [], setL = [], authL = [];
  let store = {};
  try { store = JSON.parse(localStorage.getItem('__cgdata') || '{}'); } catch (e) {}
  const saveStore = () => { try { localStorage.setItem('__cgdata', JSON.stringify(store)); } catch (e) {} };
  const SDK = {
    environment: 'crazygames', isQaTool: false,
    init: () => { L('sdkInit'); return new Promise((r) => setTimeout(r, 30)); },
    user: {
      isUserAccountAvailable: true,
      systemInfo: { countryCode: CFG.country || 'US', locale: CFG.locale || 'en-US', device: { type: CFG.device || 'desktop' }, os: { name: 'Windows', version: '10' }, browser: { name: 'Chrome', version: '130' }, applicationType: CFG.app || 'web' },
      getUser: () => { L('getUser'); return Promise.resolve(CFG.user || null); },
      getUserToken: () => Promise.resolve('jwt'),
      showAuthPrompt: () => { L('showAuthPrompt'); return Promise.reject({ code: 'userCancelled' }); },
      addAuthListener: (f) => { L('addAuthListener'); authL.push(f); },
      removeAuthListener: () => {},
    },
    game: {
      settings: { muteAudio: !!CFG.muted, disableChat: false },
      addSettingsChangeListener: (f) => { L('addSettingsChangeListener'); setL.push(f); },
      removeSettingsChangeListener: () => {},
      gameplayStart: () => L('gameplayStart'), gameplayStop: () => L('gameplayStop'),
      loadingStart: () => L('loadingStart'), loadingStop: () => L('loadingStop'),
      happytime: () => L('happytime'),
      inviteParams: CFG.inviteParams || null,
      isInstantMultiplayer: !!CFG.instant,
      addJoinRoomListener: (f) => { L('addJoinRoomListener'); joinL.push(f); },
      removeJoinRoomListener: () => {},
      updateRoom: (o) => L('updateRoom', o),
      leftRoom: () => L('leftRoom'),
      inviteLink: (p) => { L('inviteLink', p); return 'https://www.crazygames.com/game/flagball-arena?' + new URLSearchParams(p).toString(); },
      showInviteButton: (p) => { L('showInviteButton', p); return 'https://www.crazygames.com/game/flagball-arena?' + new URLSearchParams(p).toString(); },
      hideInviteButton: () => L('hideInviteButton'),
    },
    ad: {
      requestAd: (type, cb) => {
        L('requestAd', type);
        const mode = (window.__cgAdMode || CFG.ads || 'disabled');
        if (mode === 'ok') { setTimeout(() => { L('adStarted', type); cb && cb.adStarted && cb.adStarted(); }, 300); setTimeout(() => { L('adFinished', type); cb && cb.adFinished && cb.adFinished(); }, 1500); }
        else setTimeout(() => { const err = { code: mode, message: mode }; L('adError', err); cb && cb.adError && cb.adError(err); }, 60);
      },
      hasAdblock: () => Promise.resolve(false),
    },
    banner: { requestBanner: () => Promise.resolve(), requestResponsiveBanner: () => { L('banner'); return Promise.resolve(); }, clearBanner: () => {}, clearAllBanners: () => {} },
    data: {
      getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); saveStore(); L('dataSet', k); },
      removeItem: (k) => { delete store[k]; saveStore(); }, clear: () => { store = {}; saveStore(); }, syncUnityGameData: () => {},
    },
    analytics: { trackOrder: () => {} },
  };
  window.CrazyGames = { SDK };
  window.__cg = { join: (p) => joinL.forEach((f) => f(p)), mute: (m) => { SDK.game.settings.muteAudio = m; setL.forEach((f) => f({ muteAudio: m, disableChat: false })); }, auth: (u) => { CFG.user = u; authL.forEach((f) => f(u)); } };
})();`;
}

const OUTER = (w, h, full) => `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
 body{margin:0;background:#0c0d14;font-family:Arial;color:#fff} #hdr{height:56px;display:flex;align-items:center;padding:0 16px;gap:12px}
 #wrap{display:flex;gap:12px;padding:0 12px} iframe{border:0;display:block;background:#000}
 #side{width:200px;background:#1b1c2a;padding:10px} #side button{width:100%;padding:12px;margin:6px 0}
 body.full #hdr,body.full #side{display:none} body.full #wrap{padding:0}
</style></head><body class="${full ? 'full' : ''}">
<div id="hdr">CrazyGames <input id="search" placeholder="Search games"></div>
<div id="wrap"><iframe id="game" allow="autoplay; fullscreen; clipboard-write; clipboard-read" style="width:${w}px;height:${h}px"></iframe><div id="side"><button id="like">Like</button><button id="other">Other</button></div></div>
<script>document.getElementById('game').src = ${JSON.stringify(GAME_URL)} + location.search;</script>
</body></html>`;

async function launch() {
  return chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--ignore-certificate-errors', '--autoplay-policy=no-user-gesture-required', '--disable-features=LocalNetworkAccessChecks,PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights'] });
}

// opts: {user, locale, country, device, app, ads, inviteParams, instant, muted, view:{width,height}, frame:{w,h}, mobile, full}
async function player(browser, opts = {}) {
  const mobile = !!opts.mobile;
  const view = opts.view || (mobile ? { width: 390, height: 844 } : { width: 1366, height: 768 });
  const ctx = await browser.newContext({ viewport: view, hasTouch: mobile, isMobile: mobile, deviceScaleFactor: opts.dpr || (mobile ? 2 : 1), locale: opts.browserLocale || 'en-US' });
  try { await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'https://games.crazygames.com' }); } catch (e) { /* */ }
  const ext = [], errs = [];
  const fw = opts.frame ? opts.frame.w : (mobile || opts.full ? view.width : 907), fh = opts.frame ? opts.frame.h : (mobile || opts.full ? view.height : 510);
  await ctx.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.hostname === 'www.crazygames.com') return route.fulfill({ contentType: 'text/html', body: OUTER(fw, fh, mobile || opts.full) });
    if (u.hostname === 'sdk.crazygames.com') return route.fulfill({ contentType: 'application/javascript', body: mockSdk(opts) });
    if (u.hostname === 'games.crazygames.com') {
      const f = path.join(opts.dist || DIST, path.basename(u.pathname));
      if (!fs.existsSync(f)) return route.fulfill({ status: 404, body: 'nf' });
      const ct = f.endsWith('.html') ? 'text/html' : f.endsWith('.json') ? 'application/json' : 'application/javascript';
      let body = fs.readFileSync(f);
      if (f.endsWith('index.html') && opts.adsOn) body = String(body).replace('window.GAME_ADS=false', 'window.GAME_ADS=true');
      return route.fulfill({ contentType: ct, body });
    }
    if (u.hostname === 'localhost' || u.hostname === '127.0.0.1') return route.continue();
    ext.push(u.href); return route.abort();
  });
  if (opts.initScript) await ctx.addInitScript(opts.initScript);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errs.push('PAGEERR ' + e.message + ' ' + String(e.stack || e).slice(0, 300) + ' ' + (typeof e === 'object' ? JSON.stringify(e).slice(0, 200) : '')));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon|ERR_FAILED|net::/.test(m.text())) errs.push(m.text()); });
  await page.goto('https://www.crazygames.com/game/flagball-arena?server=' + encodeURIComponent(WSS) + (opts.qs || ''));
  let frame = null;
  for (let i = 0; i < 50 && !frame; i++) { frame = page.frames().find((f) => f.url().startsWith('https://games.crazygames.com')); if (!frame) await page.waitForTimeout(100); }
  await frame.waitForFunction(() => window.Core && window.__dbgOnline, null, { timeout: 15000 });
  const p = { ctx, page, frame, ext, errs, opts, fw, fh };
  p.ev = (fn, a) => frame.evaluate(fn, a);
  p.st = () => frame.evaluate(() => { const d = __dbgOnline(); return { status: d.status, id: d.myId, alive: d.me.alive, m: Math.round(d.me.m), coins: d.coins, dead: d.dead && { offer: d.dead.offer, coins: d.dead.coins, best: d.dead.best }, cs: d.cs, rt: Math.round(d.rt), W: Math.round(Core.W), H: Math.round(Core.H), lang: Core.lang, platform: Core.platform, rew: Core.rewardedSupported, inter: Core.interSupported, paused: Core.paused, adPlaying: Core.adPlaying, shop: d.shop, balls: d.balls }; });
  p.cg = () => frame.evaluate(() => window.__cgLog);
  p.rect = (id) => frame.evaluate((id) => { const r = Core.UI.rects.find((q) => q.id === id); return r ? { x: (r.x + r.w / 2) * Core.scale, y: (r.y + r.h / 2) * Core.scale, w: r.w * Core.scale, h: r.h * Core.scale } : null; }, id);
  p.ids = () => frame.evaluate(() => Core.UI.rects.map((r) => r.id));
  p.tap = async (id) => {
    const r = await p.rect(id); if (!r) return false;
    const box = await (await page.$('#game')).boundingBox();
    if (mobile) await page.touchscreen.tap(box.x + r.x, box.y + r.y); else await page.mouse.click(box.x + r.x, box.y + r.y);
    return true;
  };
  p.shot = (name) => page.screenshot({ path: path.join(__dirname, 'shots', name + '.png') });
  p.close = () => ctx.close();
  return p;
}

// убить игрока victim руками hunter через отладочные команды тестового сервера
async function ensureAlive(p) {
  if (!(await p.ev(() => __dbgOnline().me.alive))) { await p.ev(() => { const d = __dbgOnline().dead; if (d) d.t = 9; __respawn(); }); await p.frame.waitForTimeout(2200); }
}
async function kill(victim, hunter, vm) {
  await ensureAlive(victim); await ensureAlive(hunter);
  await victim.ev((vm) => __send({ t: 'dbg', m: vm }), vm);
  await hunter.ev(() => __send({ t: 'dbg', m: 400 }));
  await victim.frame.waitForTimeout(4200);
  await victim.ev((vm) => __send({ t: 'dbg', m: vm }), vm);
  await victim.frame.waitForTimeout(400);
  const vp = await victim.ev(() => ({ x: __dbgOnline().me.x, y: __dbgOnline().me.y }));
  await hunter.ev((vp) => __send({ t: 'dbg', x: vp.x + 30, y: vp.y }), vp);
  for (let i = 0; i < 24; i++) { await victim.frame.waitForTimeout(250); if (!(await victim.ev(() => __dbgOnline().me.alive))) return true; }
  return false;
}

module.exports = { launch, player, kill, ensureAlive };
