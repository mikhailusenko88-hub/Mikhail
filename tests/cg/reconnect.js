// Обрыв связи: сервер перезапускается (как при обновлении) — игрок должен сам вернуться в игру.
// Плюс: долгая игра 3 минуты — растёт ли память страницы.
const H = require('./harness');
const { execSync } = require('child_process');
const start = () => execSync("cd /home/claude/games && (PORT=8091 TEST=1 ROUND_LEN=45 STATE_FILE=/tmp/cgt/day.json TLS_CERT=/tmp/cgt/cert.pem TLS_KEY=/tmp/cgt/key.pem TLS_PORT=8443 nohup node online/server.js >> /tmp/cgt/server.log 2>&1 &)");
const stop = () => { try { execSync("pkill -f 'node online/server.js'"); } catch (e) { /* */ } };
(async () => {
  const b = await H.launch();
  const p = await H.player(b, { user: { username: 'Stayer' }, mobile: true, device: 'mobile' });
  await p.frame.waitForTimeout(2500);
  console.log('before', JSON.stringify(await p.st()));
  stop(); await p.frame.waitForTimeout(3000);
  console.log('server down', JSON.stringify(await p.st()));
  await p.shot('rc_down');
  await p.frame.waitForTimeout(6000);
  console.log('still down after 9s', JSON.stringify(await p.ev(() => ({ status: __dbgOnline().status, attempt: __dbgOnline().attempt }))));
  start();
  let t = 0; for (; t < 40; t++) { await p.frame.waitForTimeout(500); if ((await p.st()).status === 'ok') break; }
  console.log('back after', (t + 1) * 0.5, 's', JSON.stringify(await p.st()));
  await p.shot('rc_back');
  // долгая игра: память
  await p.ev(() => { window.__bot = (me) => { const a = performance.now() / 2500; return [Math.cos(a), Math.sin(a)]; }; setInterval(() => { const d = __dbgOnline(); if (!d.me.alive && d.dead && d.dead.t > 1.5) { d.dead.t = 9; __respawn(); } }, 700); });
  const mem = async () => { const cdp = await p.ctx.newCDPSession(p.page); await cdp.send('HeapProfiler.collectGarbage').catch(() => {}); const m = await p.frame.evaluate(() => performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576 * 10) / 10 : -1); await cdp.detach(); return m; };
  const m0 = await mem(); const out = [m0];
  for (let i = 0; i < 6; i++) { await p.frame.waitForTimeout(30000); out.push(await mem()); }
  console.log('JS heap MB every 30s', out.join(' → '));
  console.log('cg log tail', JSON.stringify((await p.cg()).slice(-8).map((x) => x[1])), 'errs', p.errs.join(' | ') || 'none');
  await b.close();
})();
