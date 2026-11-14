// 20 живых игроков в одной комнате (половина — телефоны), каждый управляется простым ботом в браузере.
// Смотрим: все видят 20, сервер не захлёбывается, сколько трафика на игрока, плавность у клиента.
const H = require('./harness');
const { execSync } = require('child_process');
const N = +process.env.N || 20;
const BOT = () => {
  window.__bot = (me, balls) => {
    let fx = 0, fy = 0, tx = null, td = 1e9;
    for (const b of balls.values()) {
      if (!b.alive || b.id === __dbgOnline().myId) continue;
      const dx = b.x - me.x, dy = b.y - me.y, d = Math.hypot(dx, dy) || 1;
      if (b.r > me.r * 1.12 && d < 500) { fx -= dx / d * (500 - d); fy -= dy / d * (500 - d); }
      else if (me.r > b.r * 1.12 && d < td) { td = d; tx = b; }
    }
    if (fx || fy) { const l = Math.hypot(fx, fy); return [fx / l, fy / l]; }
    if (tx && td < 700) { const l = Math.hypot(tx.x - me.x, tx.y - me.y) || 1; return [(tx.x - me.x) / l, (tx.y - me.y) / l]; }
    const t = performance.now() / 3000 + (window.__seed || 0); return [Math.cos(t), Math.sin(t)];
  };
  setInterval(() => { const d = __dbgOnline(); if (!d.me.alive && d.dead && d.dead.t > 1.5) { d.dead.t = 9; __respawn(); } }, 700);
  // кадры в секунду
  window.__fps = []; let n = 0, t0 = performance.now();
  (function f() { n++; const t = performance.now(); if (t - t0 >= 1000) { window.__fps.push(n); n = 0; t0 = t; } requestAnimationFrame(f); })();
};
const health = () => JSON.parse(execSync('curl -sk https://localhost:8443/health').toString());
const cpu = () => { try { return execSync("ps -o %cpu=,rss= -p $(pgrep -f 'online/server.js' | head -1)").toString().trim(); } catch (e) { return '?'; } };
(async () => {
  const b = await H.launch();
  const ps = [];
  const names = ['Aru', 'Борис', 'Chen', 'Dana', 'Erlan', 'Fatima', 'Gosha', 'Hiro', 'Ivan', 'Juan', 'Kemal', 'Lena', 'Maks', 'Nurlan', 'Olga', 'Pablo', 'Qadir', 'Rita', 'Sven', 'Timur'];
  const countries = ['KZ', 'RU', 'CN', 'DE', 'KZ', 'TR', 'RU', 'JP', 'UA', 'ES', 'TR', 'BY', 'UZ', 'KZ', 'KG', 'MX', 'IN', 'IT', 'SE', 'UZ'];
  for (let i = 0; i < N; i++) {
    const mobile = i % 2 === 1;
    const p = await H.player(b, { user: { username: names[i] }, country: countries[i], locale: i % 3 ? 'en-US' : 'ru-RU', mobile, device: mobile ? 'mobile' : 'desktop', view: mobile ? { width: 360, height: 740 } : { width: 1366, height: 768 }, dpr: 1 });
    await p.ev(BOT); await p.ev((s) => { window.__seed = s; }, i * 1.7);
    ps.push(p);
    if (i % 5 === 4) console.log('joined', i + 1, JSON.stringify(health()), 'cpu/rss', cpu());
  }
  // трафик одного игрока
  const cdp = await ps[0].ctx.newCDPSession(ps[0].page); await cdp.send('Network.enable');
  let rx = 0, rxN = 0, tx = 0; cdp.on('Network.webSocketFrameReceived', (e) => { rx += e.response.payloadData.length; rxN++; }); cdp.on('Network.webSocketFrameSent', (e) => { tx += e.response.payloadData.length; });
  const samples = [];
  for (let s = 0; s < 6; s++) { await ps[0].frame.waitForTimeout(5000); samples.push(cpu()); }
  console.log('server cpu%/rss samples', samples.join(' | '));
  console.log('player0 traffic over 30s: in', Math.round(rx / 1024) + ' KB', rxN + ' frames', 'out', Math.round(tx / 1024) + ' KB', '→ in', Math.round(rx / 30 / 1024 * 10) / 10 + ' KB/s');
  const H0 = health(); console.log('health', JSON.stringify(H0));
  for (const [i, p] of ps.entries()) {
    const r = await p.ev(() => { const d = __dir(); const o = __dbgOnline(); const f = window.__fps.slice(-10); return { humans: d.humans, R: Math.round(o.R), dots: o.dots, balls: o.balls, ping: o.pingMs, status: o.status, fps: Math.round(f.reduce((a, b) => a + b, 0) / Math.max(1, f.length)), m: Math.round(o.me.m) }; });
    if (i < 4 || i % 5 === 0) console.log('p' + i, JSON.stringify(r), 'errs', p.errs.length ? p.errs.slice(0, 2).join(' | ') : 'none');
  }
  const allSee = await Promise.all(ps.map((p) => p.ev(() => __dir().humansMax)));
  console.log('max humans seen per client', allSee.join(','));
  await ps[0].shot('t20_desktop'); await ps[1].shot('t20_mobile'); await ps[6].shot('t20_desktop_b');
  const errs = ps.flatMap((p) => p.errs); console.log('total client errors', errs.length, errs.slice(0, 3).join(' | '));
  for (const p of ps) await p.close();
  await b.close();
})();
