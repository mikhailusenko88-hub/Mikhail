// Нагрузка и «хулиганы» без браузеров: 40 игроков-ботов на Node WebSocket, потом мусорные сообщения.
// Меряем: процессор сервера (мгновенный, по /proc), ровность тиков у клиента, размер трафика, живучесть.
const fs = require('fs');
const { execSync } = require('child_process');
const URL = process.env.URL || 'ws://localhost:8091/ws';
const pid = +execSync("pgrep -f 'node online/server.js' | head -1").toString().trim();
const ticks = () => { const a = fs.readFileSync(`/proc/${pid}/stat`, 'utf8').split(') ')[1].split(' '); return +a[11] + +a[12]; };
const rss = () => Math.round(+fs.readFileSync(`/proc/${pid}/status`, 'utf8').match(/VmRSS:\s+(\d+)/)[1] / 1024) + ' MB';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function cpuOver(ms) { const t0 = ticks(), w0 = Date.now(); await sleep(ms); return Math.round(((ticks() - t0) / 100) / ((Date.now() - w0) / 1000) * 100) + '%'; }
function bot(i, room, opts = {}) {
  return new Promise((res) => {
    const ws = new WebSocket(URL); const st = { ws, i, x: 0, y: 0, alive: false, id: 0, msgs: 0, bytes: 0, gaps: [], last: 0, w: 0, died: 0, full: false };
    ws.onopen = () => ws.send(JSON.stringify({ t: 'hello', name: opts.name || ('Bot' + i), skin: ['KZ', 'RU', 'US', 'DE', 'TR'][i % 5], room }));
    ws.onmessage = (e) => {
      st.msgs++; st.bytes += e.data.length; const now = Date.now(); if (st.last) st.gaps.push(now - st.last); st.last = now;
      let m; try { m = JSON.parse(e.data); } catch (er) { return; }
      if (m.t === 'w') { st.w++; st.id = m.id; st.x = m.x; st.y = m.y; st.alive = true; st.wBytes = e.data.length; res(st); }
      if (m.t === 'fix') { st.x = m.x; st.y = m.y; if (m.re) st.alive = true; }
      if (m.t === 'dead') { st.alive = false; st.died++; setTimeout(() => ws.readyState === 1 && ws.send(JSON.stringify({ t: 're' })), 1500); }
      if (m.t === 'full') { st.full = true; res(st); }
    };
    ws.onclose = (e) => { st.closed = true; st.code = e.code; res(st); };
    ws.onerror = (e) => { st.err = (e && e.message) || 'error'; };
    setTimeout(() => { st.timeout = true; res(st); }, 4000);
    let a = Math.random() * 7;
    st.timer = setInterval(() => { if (!st.alive || ws.readyState !== 1) return; a += (Math.random() - 0.5) * 0.5; st.x += Math.cos(a) * 14; st.y += Math.sin(a) * 14; const d = Math.hypot(st.x, st.y); if (d > 1500) { st.x *= 1500 / d; st.y *= 1500 / d; a += Math.PI; } ws.send(JSON.stringify({ t: 'p', x: Math.round(st.x), y: Math.round(st.y) })); }, 50);
  });
}
(async () => {
  console.log('idle cpu', await cpuOver(2000), 'rss', rss());
  const bs = [];
  for (let i = 0; i < 40; i++) { bs.push(await bot(i, 'load')); if (i === 19) console.log('20 players: cpu', await cpuOver(5000), 'rss', rss(), 'w bytes', bs[19].wBytes); }
  console.log('40 players: cpu', await cpuOver(5000), 'rss', rss(), 'w bytes of #40', bs[39].wBytes);
  const extra = await bot(99, 'load'); console.log('41st player full?', extra.full, 'closed', !!extra.closed, 'code', extra.code, 'err', extra.err, 'timeout', !!extra.timeout, 'readyState', extra.ws.readyState);
  for (const b of bs) { b.gaps = []; b.bytes = 0; b.msgs = 0; }
  await sleep(10000);
  const g = bs.flatMap((b) => b.gaps).sort((a, b) => a - b);
  const pct = (q) => g[Math.floor(g.length * q)];
  console.log('tick gaps ms p50/p90/p99/max', pct(0.5), pct(0.9), pct(0.99), g[g.length - 1], 'msgs/s per client', Math.round(bs[0].msgs / 10), 'KB/s per client', Math.round(bs[0].bytes / 10 / 1024 * 10) / 10);
  console.log('deaths during 10s', bs.reduce((a, b) => a + b.died, 0));
  const h = JSON.parse(execSync('curl -s http://localhost:8091/health').toString()); console.log('health', JSON.stringify(h));

  for (const b of bs.splice(10)) { clearInterval(b.timer); b.ws.close(); }
  await sleep(1000);
  // ---------- хулиганы ----------
  const bad = await bot(500, 'load', { name: '<script>alert(1)</script>🙂🙂🙂 very very long name indeed' });
  const send = (o) => bad.ws.send(typeof o === 'string' ? o : JSON.stringify(o));
  send('not json'); send('{"t":'); send(JSON.stringify({ t: 'p', x: 'NaN', y: null })); send({ t: 'p', x: 1e308, y: -1e308 }); send({ t: 'p', x: 99999999, y: 0 });
  send({ t: 're', skin: 'ZZ', name: 'x'.repeat(5000), acc: 1e9, keep: 1 }); send({ t: 'hello', room: 'other' }); send({ t: 'dbg', m: 1e9 }); send({ t: 'ping', c: 'x'.repeat(100) });
  send({ t: '__proto__', x: 1 }); send({ constructor: 1 }); send('[]'); send('null'); send('1');
  try { bad.ws.send(new Uint8Array([1, 2, 3, 4])); } catch (e) { /* */ }
  for (let i = 0; i < 2000; i++) send({ t: 'p', x: i, y: i });   // поток
  await sleep(1500);
  console.log('bad client still open', bad.ws.readyState === 1, 'server alive', JSON.parse(execSync('curl -s http://localhost:8091/health').toString()).ok === 1);
  // очень большое сообщение
  const big = await bot(501, 'load'); try { big.ws.send('{"t":"p","x":1,"y":1,"z":"' + 'a'.repeat(2 * 1024 * 1024) + '"}'); } catch (e) { /* */ }
  await sleep(1500); console.log('after 2MB frame: big open', big.ws.readyState === 1, 'server alive', JSON.parse(execSync('curl -s http://localhost:8091/health').toString()).ok === 1, 'rss', rss());
  // имя, как его видят другие
  const nm = await new Promise((res) => { const w = new WebSocket(URL); w.onopen = () => w.send(JSON.stringify({ t: 'hello', name: 'Watcher', room: 'load', skin: 'KZ' })); w.onmessage = (e) => { const m = JSON.parse(e.data); if (m.t === 'w') { const x = m.mt.find((q) => q[0] === bad.id); res(x && x[1]); w.close(); } }; });
  console.log('bad name shown to others as', JSON.stringify(nm));
  // плохие слова в имени
  const sw = await bot(502, 'load', { name: 'fuck' }); const nm2 = await new Promise((res) => { const w = new WebSocket(URL); w.onopen = () => w.send(JSON.stringify({ t: 'hello', name: 'W2', room: 'load', skin: 'KZ' })); w.onmessage = (e) => { const m = JSON.parse(e.data); if (m.t === 'w') { const x = m.mt.find((q) => q[0] === sw.id); res(x && x[1]); w.close(); } }; });
  console.log('profane name shown as', JSON.stringify(nm2));
  for (const b of [...bs, bad, big, sw]) { clearInterval(b.timer); try { b.ws.close(); } catch (e) { /* */ } }
  await sleep(1500);
  console.log('after all left', execSync('curl -s http://localhost:8091/health').toString(), 'cpu', await cpuOver(2000), 'rss', rss());
  process.exit(0);
})();
