// Плавность чужих шариков при «рваной» сети телефона: пакеты задерживаются на 0–150 мс и приходят пачками.
// Меряем по кадрам: замирания (шарик почти стоит при движении) и рывки (скачок больше 2,5× обычного шага).
const H = require('./harness');
const JITTER = `(() => { if (location.hostname !== 'games.crazygames.com') return; const W = window.WebSocket; let last = 0;
  window.WebSocket = function (u, p) { const ws = new W(u, p); let h = null; const q = (e) => { const now = performance.now(); last = Math.max(last, now + Math.random() * 150); const at = last; setTimeout(() => h && h.call(ws, e), at - now); };
    ws.addEventListener('message', q); Object.defineProperty(ws, 'onmessage', { set(f) { h = f; }, get() { return h; } }); return ws; };
  window.WebSocket.prototype = W.prototype; Object.assign(window.WebSocket, { OPEN: 1, CLOSED: 3, CONNECTING: 0, CLOSING: 2 }); })();`;
async function measure(b, dist, name) {
  const p = await H.player(b, { user: { username: name }, dist, initScript: JITTER, mobile: true, device: 'mobile' });
  await p.frame.waitForTimeout(4000);
  const r = await p.ev(() => new Promise((res) => {
    const d = __dbgOnline(); const pick = () => { let best = null, bd = 1e9; for (const [, b] of Object.entries({})) {} return null; };
    // берём 4 ближайших к камере живых бота и пишем их положение каждый кадр 6 с
    const tracks = new Map(); const t0 = performance.now();
    (function f() {
      const o = window.__ballsDbg ? window.__ballsDbg() : null;
      if (performance.now() - t0 > 6000) { res(Array.from(tracks.values())); return; }
      requestAnimationFrame(f);
    })();
  }));
  await p.close();
  return r;
}
(async () => {
  const b = await H.launch();
  for (const [name, dist, jit] of (process.env.CASES === 'base' ? [['old-nojitter', '/tmp/cgt/old_dist', 0], ['new-nojitter', undefined, 0]] : [['old', '/tmp/cgt/old_dist', 1], ['new', undefined, 1]])) {
    const p = await H.player(b, { user: { username: 'Sm' + name }, dist, initScript: jit ? JITTER : null, mobile: true, device: 'mobile' });
    await p.frame.waitForTimeout(4000);
    const stats = await p.ev(() => new Promise((res) => {
      const pos = new Map(); const t0 = performance.now(); let frames = 0;
      const balls = () => window.__balls();
      (function f() {
        frames++;
        for (const b of balls()) { if (!b.alive || b.human) continue; if (!pos.has(b.id)) pos.set(b.id, []); pos.get(b.id).push([b.x, b.y]); }
        if (performance.now() - t0 < 6000) requestAnimationFrame(f); else {
          let stalls = 0, jumps = 0, n = 0;
          for (const arr of pos.values()) {
            if (arr.length < 60) continue;
            const st = []; for (let i = 1; i < arr.length; i++) st.push(Math.hypot(arr[i][0] - arr[i - 1][0], arr[i][1] - arr[i - 1][1]));
            const med = st.slice().sort((a, c) => a - c)[st.length >> 1]; if (med < 1) continue;
            for (const s of st) { n++; if (s < med * 0.15) stalls++; if (s > med * 2.5) jumps++; }
          }
          res({ frames, steps: n, stallsPct: Math.round(stalls / Math.max(1, n) * 1000) / 10, jumpsPct: Math.round(jumps / Math.max(1, n) * 1000) / 10 });
        }
      })();
    }));
    console.log(name, JSON.stringify(stats), 'errs', p.errs.join(' | ') || 'none');
    await p.close();
  }
  await b.close();
})();
