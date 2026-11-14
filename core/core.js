'use strict';
/* Общее ядро для пяти игр: экран, ввод, Playgama Bridge, реклама, звук, флаги, магазин, окна. */
(function () {
  const C = (window.Core = {});
  const cv = document.getElementById('c');
  const ctx = cv.getContext('2d');
  C.cv = cv; C.ctx = ctx;
  C.BASE = { w: 720, h: 1280 };
  C.W = 720; C.H = 1280; C.scale = 1; C.dpr = 1;
  C.t = 0; C.dt = 0;
  C.state = 'boot'; // boot | home | play | win | fail | shop
  C.popup = null;   // gift | chest | adMock | reward
  C.paused = false; C.hidden = false; C.adPlaying = false; C.platformMuted = false;
  const now = () => performance.now() / 1000;
  C.now = now;
  const sessionStart = now();

  // ---------- утилиты ----------
  C.clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  C.lerp = (a, b, t) => a + (b - a) * t;
  C.easeOutBack = (t) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
  C.easeOut = (t) => 1 - Math.pow(1 - t, 3);
  C.rnd = (a, b) => a + Math.random() * (b - a);
  C.rint = (a, b) => Math.floor(a + Math.random() * (b - a + 1));
  C.pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  C.shuffle = (arr) => { for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; } return arr; };
  C.seeded = (seed) => { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; };
  C.today = () => { const d = new Date(); return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); };

  // ---------- размер экрана ----------
  function resize() {
    const w = window.innerWidth || 360, h = window.innerHeight || 640;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    const b = (C.game && C.game.landscapeBase && w > h) ? { w: 1280, h: 720 } : C.BASE;
    if (w / h >= b.w / b.h) { C.H = b.h; C.W = (b.h * w) / h; } else { C.W = b.w; C.H = (b.w * h) / w; }
    C.scale = w / C.W; C.dpr = dpr;
    if (C.game && C.game.resize) C.game.resize();
  }
  window.addEventListener('resize', resize);
  resize();

  // ---------- сохранение ----------
  const defaultSave = () => ({
    coins: 0, level: 1, skin: null, owned: {}, adProg: {}, sound: true,
    day: { last: '', streak: 0 }, chestAt: 0, hintFree: 1, fails: {}, stars: {}, extra: {}, plays: 0,
  });
  C.save = defaultSave();
  let saveTimer = null;
  C.persist = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      const data = JSON.stringify(C.save);
      try { localStorage.setItem(C.key(), data); } catch (e) { /* ignore */ }
      if (C.bridgeOk) { try { window.bridge.storage.set(C.key(), data).catch(() => {}); } catch (e) { /* ignore */ } }
    }, 250);
  };
  C.key = () => 'pg_' + (C.game ? C.game.id : 'game');
  async function loadSave() {
    let raw = null;
    if (C.bridgeOk) { try { raw = await window.bridge.storage.get(C.key()); } catch (e) { raw = null; } }
    if (!raw) { try { raw = localStorage.getItem(C.key()); } catch (e) { raw = null; } }
    if (raw) {
      try { const obj = typeof raw === 'string' ? JSON.parse(raw) : raw; C.save = Object.assign(defaultSave(), obj); } catch (e) { /* bad save */ }
    }
  }

  // ---------- Playgama Bridge ----------
  C.bridgeOk = false; C.platform = 'none'; C.lang = (navigator.language || 'en').toLowerCase();
  C.rewardedSupported = true; C.interSupported = true; C.mockAds = true;
  async function initBridge() {
    if (!window.bridge) return;
    try {
      await Promise.race([window.bridge.initialize(), new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 6000))]);
      C.bridgeOk = true;
      C.platform = window.bridge.platform.id || 'unknown';
      try { if (window.bridge.platform.language) C.lang = String(window.bridge.platform.language).toLowerCase() + '-' + (navigator.language || '').split('-')[1]; } catch (e) { /* */ }
      C.mockAds = C.platform === 'mock' || C.platform === 'unknown';
      if (!C.mockAds) {
        C.rewardedSupported = !!window.bridge.advertisement.isRewardedSupported;
        C.interSupported = !!window.bridge.advertisement.isInterstitialSupported;
      }
      const P = window.bridge.platform;
      // онлайн-игре нельзя замирать, когда окно просто потеряло фокус (сервер-то идёт дальше): звук глушим, игру не морозим
      P.on('pause_state_changed', (p) => { C.platformPaused = !!p; C.paused = C.platformPaused && !(C.game && C.game.noPlatformPause); C.audio.update(); });
      P.on('audio_state_changed', (on) => { C.platformMuted = !on; C.audio.update(); });
      try { C.platformMuted = P.isAudioEnabled === false; } catch (e) { /* */ }
      window.bridge.advertisement.on('rewarded_state_changed', (s) => C.ads._onRewarded(s));
      window.bridge.advertisement.on('interstitial_state_changed', (s) => C.ads._onInter(s));
    } catch (e) {
      C.bridgeOk = false; C.mockAds = true;
    }
  }
  C.msg = (name, data) => { if (!C.bridgeOk) return; try { window.bridge.platform.sendMessage(name, data); } catch (e) { /* */ } };

  // ---------- реклама ----------
  const ads = (C.ads = { lastInter: -1e9, lastRewardEnd: -1e9, _pending: null, _rewarded: false, count: 0 });
  ads.canInter = () => {
    const t = now();
    if (C.game && C.game.canInter) return C.interSupported && C.game.canInter(t - sessionStart, t - ads.lastInter, t - ads.lastRewardEnd);
    return C.interSupported && C.save.level >= 3 && t - sessionStart > 60 && t - ads.lastInter > 60 && t - ads.lastRewardEnd > 90;
  };
  ads._finish = (val) => {
    const p = ads._pending; ads._pending = null; C.adPlaying = false; C.audio.update();
    if (p) { clearTimeout(p.timer); p.resolve(val); }
  };
  ads._onRewarded = (s) => {
    if (!ads._pending || ads._pending.type !== 'rewarded') return;
    if (s === 'opened') { C.adPlaying = true; C.audio.update(); }
    else if (s === 'rewarded') ads._rewarded = true;
    else if (s === 'closed' || s === 'failed') { ads.lastRewardEnd = now(); ads._finish(ads._rewarded); if (s === 'failed' && !ads._rewarded) C.toast('noad'); }
  };
  ads._onInter = (s) => {
    if (!ads._pending || ads._pending.type !== 'inter') return;
    if (s === 'opened') { C.adPlaying = true; C.audio.update(); }
    else if (s === 'closed' || s === 'failed') ads._finish(true);
  };
  ads.rewarded = (placement) => new Promise((resolve) => {
    if (ads._pending) return resolve(false);
    ads._rewarded = false;
    ads._pending = { type: 'rewarded', resolve, timer: setTimeout(() => ads._finish(ads._rewarded), 90000) };
    ads.count++;
    if (C.mockAds) { C.adPlaying = true; C.audio.update(); C.popupPush({ kind: 'adMock', rewarded: true, t0: now(), dur: 2.2, placement }); return; }
    try { window.bridge.advertisement.showRewarded(placement); } catch (e) { ads._finish(false); }
  });
  ads.interstitial = (placement) => new Promise((resolve) => {
    if (ads._pending || !ads.canInter()) return resolve(false);
    ads.lastInter = now();
    ads._pending = { type: 'inter', resolve, timer: setTimeout(() => ads._finish(false), 45000) };
    if (C.mockAds) { C.adPlaying = true; C.audio.update(); C.popupPush({ kind: 'adMock', rewarded: false, t0: now(), dur: 1.4, placement }); return; }
    try { window.bridge.advertisement.showInterstitial(placement); } catch (e) { ads._finish(false); }
  });

  // ---------- звук (синтез, без файлов) ----------
  const A = (C.audio = { ctx: null, master: null, musicOn: false });
  A.init = () => {
    if (A.ctx) { if (A.ctx.state === 'suspended') A.ctx.resume().catch(() => {}); return; }
    try {
      A.ctx = new (window.AudioContext || window.webkitAudioContext)();
      A.master = A.ctx.createGain(); A.master.gain.value = 0; A.master.connect(A.ctx.destination);
      A.music = A.ctx.createGain(); A.music.gain.value = 0.16; A.music.connect(A.master);
      A.update(); A.startMusic();
    } catch (e) { A.ctx = null; }
  };
  A.update = () => {
    if (!A.ctx) return;
    const on = C.save.sound && !C.platformMuted && !C.adPlaying && !C.hidden && !C.paused && !C.platformPaused;
    A.master.gain.setTargetAtTime(on ? 0.7 : 0, A.ctx.currentTime, 0.03);
  };
  A.tone = (f, dur, type = 'square', vol = 0.15, slide = 0, delay = 0, dest) => {
    if (!A.ctx) return;
    const t = A.ctx.currentTime + delay;
    const o = A.ctx.createOscillator(), g = A.ctx.createGain();
    o.type = type; o.frequency.setValueAtTime(f, t);
    if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(30, slide), t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(dest || A.master); o.start(t); o.stop(t + dur + 0.02);
  };
  A.noise = (dur, vol = 0.2, freq = 1200, delay = 0) => {
    if (!A.ctx) return;
    const t = A.ctx.currentTime + delay;
    const len = Math.floor(A.ctx.sampleRate * dur), buf = A.ctx.createBuffer(1, len, A.ctx.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const s = A.ctx.createBufferSource(), f = A.ctx.createBiquadFilter(), g = A.ctx.createGain();
    s.buffer = buf; f.type = 'lowpass'; f.frequency.value = freq; g.gain.value = vol;
    s.connect(f); f.connect(g); g.connect(A.master); s.start(t);
  };
  C.sfx = (name, k = 1) => {
    switch (name) {
      case 'tap': A.tone(660, 0.07, 'triangle', 0.12); break;
      case 'coin': A.tone(1320, 0.06, 'square', 0.06); A.tone(1760, 0.12, 'square', 0.06, 0, 0.05); break;
      case 'win': [523, 659, 784, 1047].forEach((f, i) => A.tone(f, 0.22, 'triangle', 0.16, 0, i * 0.11)); break;
      case 'fail': A.tone(392, 0.25, 'sawtooth', 0.08, 196); A.tone(262, 0.4, 'sawtooth', 0.07, 130, 0.2); break;
      case 'bounce': A.tone(220 + 200 * Math.random(), 0.08, 'sine', 0.12 * k, 120); break;
      case 'pop': A.tone(900, 0.08, 'square', 0.08, 300); A.noise(0.12, 0.15, 3000); break;
      case 'crash': A.noise(0.35 * k, 0.35, 900); A.tone(110, 0.3, 'sawtooth', 0.1, 50); break;
      case 'whoosh': A.noise(0.25, 0.12, 2400); break;
      case 'buy': [784, 988, 1319].forEach((f, i) => A.tone(f, 0.12, 'square', 0.07, 0, i * 0.06)); break;
      case 'star': A.tone(1047 + 260 * k, 0.15, 'triangle', 0.14); break;
      case 'gate': A.tone(880, 0.09, 'triangle', 0.12, 1320); break;
      case 'hit': A.tone(160, 0.15, 'square', 0.1, 80); break;
      case 'draw': A.tone(500 + 400 * k, 0.03, 'sine', 0.03); break;
      default: break;
    }
  };
  // Тихая фоновая мелодия (пентатоника), генерируется на лету
  A.startMusic = () => {
    if (!A.ctx || A.musicOn) return; A.musicOn = true;
    const scale = [0, 2, 4, 7, 9, 12, 14, 16];
    const root = 392; let step = 0; let next = A.ctx.currentTime + 0.1; const bpm = 104, beat = 60 / bpm / 2;
    const prog = [0, 0, 5, 5, 3, 3, 4, 4];
    const rng = C.seeded(7);
    const pattern = []; for (let i = 0; i < 32; i++) pattern.push(rng() < 0.7 ? scale[Math.floor(rng() * scale.length)] : null);
    setInterval(() => {
      if (!A.ctx) return;
      while (next < A.ctx.currentTime + 0.3) {
        const bar = Math.floor(step / 8) % prog.length; const chord = [0, 5, 7, -3, 2][prog[bar] % 5];
        const n = pattern[step % 32];
        if (n !== null) A.tone(root * Math.pow(2, (n + chord) / 12), beat * 1.6, 'triangle', 0.09, 0, next - A.ctx.currentTime, A.music);
        if (step % 4 === 0) A.tone((root / 4) * Math.pow(2, chord / 12), beat * 3.5, 'sine', 0.16, 0, next - A.ctx.currentTime, A.music);
        if (step % 2 === 1) { /* лёгкий хэт */ }
        next += beat; step++;
      }
    }, 100);
  };

  document.addEventListener('visibilitychange', () => { C.hidden = document.hidden; A.update(); });

  // ---------- рисование: текст, кнопки, иконки ----------
  const FONT = "800 {s}px system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif";
  C.font = (s) => FONT.replace('{s}', Math.round(s));
  C.text = (str, x, y, size, color = '#fff', align = 'center', stroke = 'rgba(0,0,0,0.55)', c = ctx) => {
    c.font = C.font(size); c.textAlign = align; c.textBaseline = 'middle';
    if (stroke) { c.lineJoin = 'round'; c.lineWidth = Math.max(3, size * 0.16); c.strokeStyle = stroke; c.strokeText(str, x, y); }
    c.fillStyle = color; c.fillText(str, x, y);
  };
  C.rr = (c, x, y, w, h, r) => {
    r = Math.min(r, w / 2, h / 2);
    c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  };
  const shade = (hex, k) => {
    const n = parseInt(hex.slice(1), 16); let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    r = C.clamp(Math.round(r * k), 0, 255); g = C.clamp(Math.round(g * k), 0, 255); b = C.clamp(Math.round(b * k), 0, 255);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
  };
  C.shade = shade;
  C.panel = (x, y, w, h, color = '#ffffff', r = 36, c = ctx) => {
    c.save(); c.fillStyle = 'rgba(0,0,0,0.25)'; C.rr(c, x, y + 10, w, h, r); c.fill();
    c.fillStyle = color; C.rr(c, x, y, w, h, r); c.fill(); c.restore();
  };

  // Иконки — только рисунок, без слов
  C.icon = (name, x, y, s, color = '#fff', c = ctx) => {
    c.save(); c.translate(x, y); c.scale(s / 100, s / 100);
    c.fillStyle = color; c.strokeStyle = color; c.lineCap = 'round'; c.lineJoin = 'round';
    const P = (pts) => { c.beginPath(); c.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) c.lineTo(pts[i], pts[i + 1]); c.closePath(); c.fill(); };
    switch (name) {
      case 'play': P([-28, -38, 40, 0, -28, 38]); break;
      case 'next': P([-30, -36, 18, 0, -30, 36]); c.fillRect(22, -36, 14, 72); break;
      case 'retry':
        c.lineWidth = 16; c.beginPath(); c.arc(0, 0, 32, -Math.PI * 0.35, Math.PI * 1.45); c.stroke();
        P([10, -58, 44, -36, 8, -10]); break;
      case 'home': P([0, -44, 44, 0, 30, 0, 30, 40, -30, 40, -30, 0, -44, 0]); c.fillStyle = 'rgba(0,0,0,0.25)'; c.fillRect(-10, 12, 20, 28); break;
      case 'close': c.lineWidth = 18; c.beginPath(); c.moveTo(-28, -28); c.lineTo(28, 28); c.moveTo(28, -28); c.lineTo(-28, 28); c.stroke(); break;
      case 'check': c.lineWidth = 18; c.beginPath(); c.moveTo(-34, 2); c.lineTo(-10, 28); c.lineTo(36, -26); c.stroke(); break;
      case 'coin': {
        const g = c.createLinearGradient(0, -46, 0, 46); g.addColorStop(0, '#ffe36b'); g.addColorStop(1, '#f7a600');
        c.fillStyle = '#c47a00'; c.beginPath(); c.arc(0, 5, 46, 0, 7); c.fill();
        c.fillStyle = g; c.beginPath(); c.arc(0, 0, 46, 0, 7); c.fill();
        c.strokeStyle = 'rgba(255,255,255,0.7)'; c.lineWidth = 7; c.beginPath(); c.arc(0, 0, 32, 0, 7); c.stroke();
        c.fillStyle = '#e08b00'; c.fillRect(-8, -20, 16, 40); break;
      }
      case 'star': case 'starEmpty': {
        c.beginPath();
        for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, r = i % 2 ? 22 : 48; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); }
        c.closePath();
        if (name === 'star') { c.fillStyle = '#ffcf2e'; c.fill(); c.lineWidth = 6; c.strokeStyle = '#d98b00'; c.stroke(); }
        else { c.fillStyle = 'rgba(0,0,0,0.18)'; c.fill(); }
        break;
      }
      case 'lock': c.lineWidth = 12; c.beginPath(); c.arc(0, -12, 22, Math.PI, 0); c.stroke(); C.rr(c, -32, -12, 64, 50, 10); c.fill(); break;
      case 'ad': { // экран с треугольником «смотреть видео»
        C.rr(c, -46, -34, 92, 68, 14); c.fill();
        c.fillStyle = '#1fb34a'; c.beginPath(); c.moveTo(-14, -18); c.lineTo(20, 0); c.lineTo(-14, 18); c.closePath(); c.fill();
        break;
      }
      case 'gift':
        c.fillStyle = '#ff4d6d'; c.fillRect(-40, -10, 80, 50); c.fillStyle = '#ff7a90'; c.fillRect(-46, -26, 92, 20);
        c.fillStyle = '#ffd23f'; c.fillRect(-8, -26, 16, 66);
        c.strokeStyle = '#ffd23f'; c.lineWidth = 9; c.beginPath(); c.ellipse(-16, -36, 16, 10, -0.4, 0, 7); c.stroke(); c.beginPath(); c.ellipse(16, -36, 16, 10, 0.4, 0, 7); c.stroke(); break;
      case 'chest':
        c.fillStyle = '#9c5a2b'; C.rr(c, -46, -14, 92, 54, 8); c.fill(); c.fillStyle = '#c47a3a'; C.rr(c, -46, -40, 92, 32, 18); c.fill();
        c.fillStyle = '#ffd23f'; c.fillRect(-46, -12, 92, 8); c.fillRect(-9, -18, 18, 26); break;
      case 'sound':
        P([-40, -14, -20, -14, 4, -36, 4, 36, -20, 14, -40, 14]);
        c.lineWidth = 9; c.beginPath(); c.arc(8, 0, 22, -0.8, 0.8); c.stroke(); c.beginPath(); c.arc(8, 0, 38, -0.8, 0.8); c.stroke(); break;
      case 'mute':
        P([-40, -14, -20, -14, 4, -36, 4, 36, -20, 14, -40, 14]);
        c.lineWidth = 9; c.beginPath(); c.moveTo(16, -16); c.lineTo(44, 16); c.moveTo(44, -16); c.lineTo(16, 16); c.stroke(); break;
      case 'shop': // шарик с блеском
        c.beginPath(); c.arc(0, 4, 38, 0, 7); c.fill(); c.fillStyle = 'rgba(0,0,0,0.25)'; c.beginPath(); c.arc(10, 14, 26, 0, 7); c.fill();
        c.fillStyle = '#fff'; c.beginPath(); c.arc(-12, -10, 10, 0, 7); c.fill(); break;
      case 'hint':
        c.beginPath(); c.arc(0, -10, 32, 0, 7); c.fill(); c.fillRect(-16, 16, 32, 22); c.fillStyle = 'rgba(0,0,0,0.25)'; c.fillRect(-16, 26, 32, 5); break;
      case 'skip': P([-44, -32, -4, 0, -44, 32]); P([-4, -32, 36, 0, -4, 32]); c.fillRect(36, -32, 10, 64); break;
      case 'heart':
        c.beginPath(); c.moveTo(0, 40); c.bezierCurveTo(-60, 0, -40, -50, 0, -18); c.bezierCurveTo(40, -50, 60, 0, 0, 40); c.fill(); break;
      case 'shield': c.beginPath(); c.moveTo(0, -46); c.lineTo(38, -30); c.lineTo(34, 10); c.quadraticCurveTo(26, 34, 0, 46); c.quadraticCurveTo(-26, 34, -34, 10); c.lineTo(-38, -30); c.closePath(); c.fill(); break;
      case 'magnet':
        c.lineWidth = 22; c.lineCap = 'butt'; c.beginPath(); c.arc(0, 0, 30, Math.PI, 0); c.lineTo(30, 34); c.moveTo(-30, 0); c.lineTo(-30, 34); c.stroke();
        c.fillStyle = '#fff'; c.fillRect(-41, 24, 22, 16); c.fillRect(19, 24, 22, 16); break;
      case 'bolt': P([10, -48, -30, 6, -4, 6, -12, 48, 30, -8, 4, -8]); break;
      case 'ink': c.beginPath(); c.moveTo(0, -46); c.quadraticCurveTo(36, 0, 30, 18); c.arc(0, 18, 30, 0, Math.PI); c.quadraticCurveTo(-36, 0, 0, -46); c.fill(); break;
      case 'plus': c.lineWidth = 18; c.beginPath(); c.moveTo(0, -32); c.lineTo(0, 32); c.moveTo(-32, 0); c.lineTo(32, 0); c.stroke(); break;
      case 'noad': c.globalAlpha = 0.9; C.rr(c, -46, -34, 92, 68, 14); c.fill(); c.strokeStyle = '#e63946'; c.lineWidth = 12; c.beginPath(); c.moveTo(-36, 30); c.lineTo(36, -30); c.stroke(); break;
      case 'pause': c.fillRect(-26, -34, 18, 68); c.fillRect(8, -34, 18, 68); break;
      case 'trophy':
        c.fillStyle = '#ffcf2e'; c.beginPath(); c.moveTo(-34, -40); c.lineTo(34, -40); c.quadraticCurveTo(34, 14, 0, 18); c.quadraticCurveTo(-34, 14, -34, -40); c.fill();
        c.fillRect(-8, 14, 16, 18); c.fillRect(-26, 30, 52, 12); c.lineWidth = 8; c.strokeStyle = '#ffcf2e';
        c.beginPath(); c.arc(-38, -22, 14, Math.PI * 0.5, Math.PI * 1.5); c.stroke(); c.beginPath(); c.arc(38, -22, 14, -Math.PI * 0.5, Math.PI * 0.5); c.stroke(); break;
      case 'truck':
        c.fillRect(-48, -26, 60, 40); C.rr(c, 14, -14, 34, 28, 6); c.fill(); c.fillStyle = '#222';
        c.beginPath(); c.arc(-30, 18, 11, 0, 7); c.fill(); c.beginPath(); c.arc(30, 18, 11, 0, 7); c.fill(); break;
      case 'clock': c.lineWidth = 10; c.beginPath(); c.arc(0, 0, 38, 0, 7); c.stroke(); c.beginPath(); c.moveTo(0, -24); c.lineTo(0, 0); c.lineTo(18, 10); c.stroke(); break;
      case 'up': P([0, -44, 40, 4, 14, 4, 14, 40, -14, 40, -14, 4, -40, 4]); break;
      case 'fuel': C.rr(c, -30, -40, 52, 80, 8); c.fill(); c.fillRect(22, -24, 16, 10); c.fillRect(32, -24, 8, 50); c.fillStyle = 'rgba(255,255,255,0.6)'; c.fillRect(-20, -30, 32, 20); break;
      default: break;
    }
    c.restore();
  };

  // ---------- немедленный интерфейс (кнопки) ----------
  const UI = (C.UI = { rects: [], next: [], pressId: null, clicked: null, downX: 0, downY: 0, scroll: null });
  UI.hit = (x, y) => { for (let i = UI.rects.length - 1; i >= 0; i--) { const r = UI.rects[i]; if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return r; } return null; };
  UI.block = (id = 'block') => UI.next.push({ id, x: -1e5, y: -1e5, w: 2e5, h: 2e5, block: true });
  UI.zone = (id, x, y, w, h, opts = {}) => { UI.next.push({ id, x, y, w, h, scroll: opts.scroll }); if (UI.clicked === id) { UI.clicked = null; return true; } return false; };
  // Кнопка с объёмом: color, icon, label (число), ad (значок рекламы)
  C.button = (id, x, y, w, h, o = {}) => {
    const pressed = UI.pressId === id;
    const col = o.color || '#29b6f6';
    const pulse = o.pulse ? 1 + Math.sin(C.realT * 6) * 0.04 : 1;
    ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.scale(pulse * (pressed ? 0.94 : 1), pulse * (pressed ? 0.94 : 1));
    if (o.alpha !== undefined) ctx.globalAlpha = o.alpha;
    const r = o.round ? h / 2 : Math.min(28, h * 0.35);
    ctx.fillStyle = shade(col, 0.68); C.rr(ctx, -w / 2, -h / 2 + 8, w, h, r); ctx.fill();
    ctx.fillStyle = col; C.rr(ctx, -w / 2, -h / 2, w, h - 4, r); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.22)'; C.rr(ctx, -w / 2 + 8, -h / 2 + 6, w - 16, (h - 4) * 0.42, r * 0.8); ctx.fill();
    const s = o.iconSize || h * 0.5;
    if (o.draw) o.draw(ctx, 0, -2);
    else if (o.ad && o.label) { C.icon('ad', -w * 0.22, -2, s * 0.9, '#fff'); C.text(o.label, w * 0.16, 0, h * 0.42); }
    else if (o.ad && o.icon) { C.icon('ad', -w * 0.2, -2, s * 0.85, '#fff'); C.icon(o.icon, w * 0.2, -2, s * 0.9, o.iconColor || '#fff'); }
    else if (o.icon && o.label) { C.icon(o.icon, -w * 0.2, -2, s * 0.85, o.iconColor || '#fff'); C.text(o.label, w * 0.14, 0, h * 0.4, '#fff', 'center'); }
    else if (o.icon) C.icon(o.icon, 0, -2, s, o.iconColor || '#fff');
    else if (o.label) C.text(o.label, 0, 0, h * 0.42);
    if (o.badge) { ctx.fillStyle = '#ff3b30'; ctx.beginPath(); ctx.arc(w / 2 - 6, -h / 2 + 6, 13, 0, 7); ctx.fill(); }
    ctx.restore();
    return UI.zone(id, x, y, w, h);
  };

  // ---------- ввод ----------
  const toV = (e) => ({ x: e.clientX / C.scale, y: e.clientY / C.scale });
  let activePointer = null; let gameCapture = false;
  cv.addEventListener('pointerdown', (e) => {
    e.preventDefault(); A.init();
    if (activePointer !== null) {
      // прежнее касание «потерялось» (телефон не прислал отпускание) — новое касание забирает управление, кнопки снова жмутся
      if (!e.isPrimary && e.pointerType !== 'mouse') return;
      if (gameCapture) { gameCapture = false; if (C.game && C.game.onUp) C.game.onUp(UI.downX, UI.downY); }
      UI.pressId = null; UI.scroll = null;
    }
    activePointer = e.pointerId;
    try { cv.setPointerCapture(e.pointerId); } catch (er) { /* */ }
    const p = toV(e); UI.downX = p.x; UI.downY = p.y;
    const r = UI.hit(p.x, p.y);
    if (r) {
      if (r.block) return; // модальное окно: игра не получает касание
      UI.pressId = r.id; UI.pressRect = r;
      const sr = r.scroll ? r : UI.rects.find((q) => q.scroll && p.x >= q.x && p.x <= q.x + q.w && p.y >= q.y && p.y <= q.y + q.h);
      if (sr) UI.scroll = { y0: p.y, base: sr.scroll.get(), set: sr.scroll.set, moved: false };
      return;
    }
    gameCapture = true;
    if (C.game && C.game.onDown) C.game.onDown(p.x, p.y);
  }, { passive: false });
  cv.addEventListener('pointermove', (e) => {
    if (activePointer === null && e.pointerType === 'mouse') { if (C.game && C.game.onHover) { const q = toV(e); C.game.onHover(q.x, q.y); } return; }
    if (e.pointerId !== activePointer) return;
    const p = toV(e);
    if (UI.scroll) {
      const dy = p.y - UI.scroll.y0;
      if (Math.abs(dy) > 14) { UI.scroll.moved = true; UI.pressId = null; }
      if (UI.scroll.moved) UI.scroll.set(UI.scroll.base + dy);
      return;
    }
    if (gameCapture && C.game && C.game.onMove) C.game.onMove(p.x, p.y);
  });
  const up = (e) => {
    if (e.pointerId !== activePointer) return; activePointer = null;
    const p = toV(e);
    if (UI.pressId) {
      const r = UI.pressRect;
      if (r && p.x >= r.x - 20 && p.x <= r.x + r.w + 20 && p.y >= r.y - 20 && p.y <= r.y + r.h + 20) { UI.clicked = UI.pressId; C.sfx('tap'); }
      UI.pressId = null;
    }
    UI.scroll = null;
    if (gameCapture) { gameCapture = false; if (C.game && C.game.onUp) C.game.onUp(p.x, p.y); }
  };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  window.addEventListener('blur', () => { activePointer = null; UI.pressId = null; UI.scroll = null; if (gameCapture) { gameCapture = false; if (C.game && C.game.onUp) C.game.onUp(UI.downX, UI.downY); } });
  cv.addEventListener('contextmenu', (e) => e.preventDefault());

  // ---------- флаги и скины ----------
  const H3 = (a, b, c2) => (g, w, h) => { g.fillStyle = a; g.fillRect(0, 0, w, h / 3 + 1); g.fillStyle = b; g.fillRect(0, h / 3, w, h / 3 + 1); g.fillStyle = c2; g.fillRect(0, (2 * h) / 3, w, h / 3 + 1); };
  const V3 = (a, b, c2) => (g, w, h) => { g.fillStyle = a; g.fillRect(0, 0, w / 3 + 1, h); g.fillStyle = b; g.fillRect(w / 3, 0, w / 3 + 1, h); g.fillStyle = c2; g.fillRect((2 * w) / 3, 0, w / 3 + 1, h); };
  const H2 = (a, b) => (g, w, h) => { g.fillStyle = a; g.fillRect(0, 0, w, h / 2 + 1); g.fillStyle = b; g.fillRect(0, h / 2, w, h / 2); };
  const star5 = (g, x, y, r, rot = 0) => { g.beginPath(); for (let i = 0; i < 10; i++) { const a = rot - Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.4 : r; g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } g.closePath(); g.fill(); };
  const crescent = (g, x, y, r, bg, fg, dx = 0.28) => { g.fillStyle = fg; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); g.fillStyle = bg; g.beginPath(); g.arc(x + r * dx, y, r * 0.8, 0, 7); g.fill(); };
  const sun = (g, x, y, r, col, rays = 16) => {
    g.fillStyle = col; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill();
    g.strokeStyle = col; g.lineWidth = r * 0.18; for (let i = 0; i < rays; i++) { const a = (i / rays) * Math.PI * 2; g.beginPath(); g.moveTo(x + Math.cos(a) * r * 1.25, y + Math.sin(a) * r * 1.25); g.lineTo(x + Math.cos(a) * r * 1.7, y + Math.sin(a) * r * 1.7); g.stroke(); }
  };
  const nordic = (bg, cross, inner) => (g, w, h) => {
    g.fillStyle = bg; g.fillRect(0, 0, w, h); g.fillStyle = cross; g.fillRect(w * 0.3, 0, w * 0.16, h); g.fillRect(0, h * 0.42, w, h * 0.16);
    if (inner) { g.fillStyle = inner; g.fillRect(w * 0.34, 0, w * 0.08, h); g.fillRect(0, h * 0.46, w, h * 0.08); }
  };
  C.FLAGS = [
    { id: 'RU', d: H3('#ffffff', '#0039a6', '#d52b1e') },
    { id: 'KZ', d: (g, w, h) => { g.fillStyle = '#00afca'; g.fillRect(0, 0, w, h); sun(g, w * 0.55, h * 0.45, h * 0.16, '#fec50c'); g.fillStyle = '#fec50c'; g.fillRect(w * 0.06, 0, w * 0.06, h); } },
    { id: 'UZ', d: (g, w, h) => { g.fillStyle = '#0099b5'; g.fillRect(0, 0, w, h / 3); g.fillStyle = '#fff'; g.fillRect(0, h / 3, w, h / 3); g.fillStyle = '#1eb53a'; g.fillRect(0, (2 * h) / 3, w, h / 3); g.fillStyle = '#ce1126'; g.fillRect(0, h / 3 - 3, w, 6); g.fillRect(0, (2 * h) / 3 - 3, w, 6); crescent(g, w * 0.2, h * 0.17, h * 0.11, '#0099b5', '#fff'); } },
    { id: 'KG', d: (g, w, h) => { g.fillStyle = '#e8112d'; g.fillRect(0, 0, w, h); sun(g, w / 2, h / 2, h * 0.17, '#ffef00', 20); g.fillStyle = '#e8112d'; g.beginPath(); g.arc(w / 2, h / 2, h * 0.1, 0, 7); g.fill(); } },
    { id: 'UA', d: H2('#0057b7', '#ffd700') },
    { id: 'BY', d: (g, w, h) => { g.fillStyle = '#c8313e'; g.fillRect(0, 0, w, h * 0.67); g.fillStyle = '#4aa657'; g.fillRect(0, h * 0.67, w, h); g.fillStyle = '#fff'; g.fillRect(0, 0, w * 0.12, h); g.fillStyle = '#c8313e'; for (let i = 0; i < 8; i++) g.fillRect(w * 0.03, i * (h / 8) + 3, w * 0.06, h / 16); } },
    { id: 'TR', d: (g, w, h) => { g.fillStyle = '#e30a17'; g.fillRect(0, 0, w, h); crescent(g, w * 0.4, h / 2, h * 0.25, '#e30a17', '#fff', 0.25); g.fillStyle = '#fff'; star5(g, w * 0.6, h / 2, h * 0.1, 0.3); } },
    { id: 'US', d: (g, w, h) => { for (let i = 0; i < 13; i++) { g.fillStyle = i % 2 ? '#fff' : '#b22234'; g.fillRect(0, (i * h) / 13, w, h / 13 + 1); } g.fillStyle = '#3c3b6e'; g.fillRect(0, 0, w * 0.45, h * 0.54); g.fillStyle = '#fff'; for (let r = 0; r < 5; r++) for (let c2 = 0; c2 < 6; c2++) { g.beginPath(); g.arc(w * 0.04 + c2 * w * 0.072, h * 0.06 + r * h * 0.1, h * 0.022, 0, 7); g.fill(); } } },
    { id: 'GB', d: (g, w, h) => { g.fillStyle = '#012169'; g.fillRect(0, 0, w, h); g.strokeStyle = '#fff'; g.lineWidth = h * 0.2; g.beginPath(); g.moveTo(0, 0); g.lineTo(w, h); g.moveTo(w, 0); g.lineTo(0, h); g.stroke(); g.strokeStyle = '#c8102e'; g.lineWidth = h * 0.07; g.stroke(); g.fillStyle = '#fff'; g.fillRect(w * 0.42, 0, w * 0.16, h); g.fillRect(0, h * 0.38, w, h * 0.24); g.fillStyle = '#c8102e'; g.fillRect(w * 0.45, 0, w * 0.1, h); g.fillRect(0, h * 0.42, w, h * 0.16); } },
    { id: 'DE', d: H3('#000000', '#dd0000', '#ffce00') },
    { id: 'FR', d: V3('#0055a4', '#ffffff', '#ef4135') },
    { id: 'IT', d: V3('#009246', '#ffffff', '#ce2b37') },
    { id: 'ES', d: (g, w, h) => { g.fillStyle = '#aa151b'; g.fillRect(0, 0, w, h); g.fillStyle = '#f1bf00'; g.fillRect(0, h / 4, w, h / 2); } },
    { id: 'PT', d: (g, w, h) => { g.fillStyle = '#006600'; g.fillRect(0, 0, w * 0.4, h); g.fillStyle = '#ff0000'; g.fillRect(w * 0.4, 0, w, h); g.fillStyle = '#ffcc00'; g.beginPath(); g.arc(w * 0.4, h / 2, h * 0.2, 0, 7); g.fill(); g.fillStyle = '#fff'; g.beginPath(); g.arc(w * 0.4, h / 2, h * 0.11, 0, 7); g.fill(); } },
    { id: 'BR', d: (g, w, h) => { g.fillStyle = '#009c3b'; g.fillRect(0, 0, w, h); g.fillStyle = '#ffdf00'; g.beginPath(); g.moveTo(w / 2, h * 0.1); g.lineTo(w * 0.92, h / 2); g.lineTo(w / 2, h * 0.9); g.lineTo(w * 0.08, h / 2); g.closePath(); g.fill(); g.fillStyle = '#002776'; g.beginPath(); g.arc(w / 2, h / 2, h * 0.22, 0, 7); g.fill(); g.strokeStyle = '#fff'; g.lineWidth = h * 0.04; g.beginPath(); g.arc(w / 2, h * 0.9, h * 0.45, -2.1, -1.05); g.stroke(); } },
    { id: 'AR', d: (g, w, h) => { H3('#74acdf', '#ffffff', '#74acdf')(g, w, h); sun(g, w / 2, h / 2, h * 0.08, '#f6b40e', 16); } },
    { id: 'MX', d: (g, w, h) => { V3('#006847', '#ffffff', '#ce1126')(g, w, h); g.fillStyle = '#8c5a2b'; g.beginPath(); g.ellipse(w / 2, h / 2, w * 0.08, h * 0.12, 0, 0, 7); g.fill(); g.fillStyle = '#006847'; g.beginPath(); g.arc(w / 2, h * 0.6, w * 0.07, 0, Math.PI); g.fill(); } },
    { id: 'CN', d: (g, w, h) => { g.fillStyle = '#de2910'; g.fillRect(0, 0, w, h); g.fillStyle = '#ffde00'; star5(g, w * 0.17, h * 0.27, h * 0.15); star5(g, w * 0.33, h * 0.1, h * 0.05, 0.4); star5(g, w * 0.4, h * 0.2, h * 0.05, 0.8); star5(g, w * 0.4, h * 0.35, h * 0.05); star5(g, w * 0.33, h * 0.45, h * 0.05, 0.4); } },
    { id: 'JP', d: (g, w, h) => { g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.fillStyle = '#bc002d'; g.beginPath(); g.arc(w / 2, h / 2, h * 0.3, 0, 7); g.fill(); } },
    { id: 'KR', d: (g, w, h) => { g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); const r = h * 0.25, x = w / 2, y = h / 2; g.fillStyle = '#cd2e3a'; g.beginPath(); g.arc(x, y, r, Math.PI, 0); g.fill(); g.fillStyle = '#0047a0'; g.beginPath(); g.arc(x, y, r, 0, Math.PI); g.fill(); g.fillStyle = '#cd2e3a'; g.beginPath(); g.arc(x - r / 2, y, r / 2, 0, 7); g.fill(); g.fillStyle = '#0047a0'; g.beginPath(); g.arc(x + r / 2, y, r / 2, 0, 7); g.fill(); g.fillStyle = '#000'; [[0.17, 0.2], [0.83, 0.2], [0.17, 0.8], [0.83, 0.8]].forEach(([a, b]) => { for (let i = 0; i < 3; i++) g.fillRect(w * a - w * 0.06, h * b - h * 0.08 + i * h * 0.06, w * 0.12, h * 0.035); }); } },
    { id: 'IN', d: (g, w, h) => { H3('#ff9933', '#ffffff', '#138808')(g, w, h); g.strokeStyle = '#000080'; g.lineWidth = h * 0.025; g.beginPath(); g.arc(w / 2, h / 2, h * 0.13, 0, 7); g.stroke(); for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; g.beginPath(); g.moveTo(w / 2, h / 2); g.lineTo(w / 2 + Math.cos(a) * h * 0.13, h / 2 + Math.sin(a) * h * 0.13); g.stroke(); } } },
    { id: 'ID', d: H2('#ce1126', '#ffffff') },
    { id: 'VN', d: (g, w, h) => { g.fillStyle = '#da251d'; g.fillRect(0, 0, w, h); g.fillStyle = '#ffff00'; star5(g, w / 2, h / 2, h * 0.3); } },
    { id: 'TH', d: (g, w, h) => { const cols = ['#a51931', '#f4f5f8', '#2d2a4a', '#2d2a4a', '#f4f5f8', '#a51931']; cols.forEach((c2, i) => { g.fillStyle = c2; g.fillRect(0, (i * h) / 6, w, h / 6 + 1); }); } },
    { id: 'PL', d: H2('#ffffff', '#dc143c') },
    { id: 'NL', d: H3('#ae1c28', '#ffffff', '#21468b') },
    { id: 'SE', d: nordic('#006aa7', '#fecc00') },
    { id: 'NO', d: nordic('#ba0c2f', '#ffffff', '#00205b') },
    { id: 'FI', d: nordic('#ffffff', '#002f6c') },
    { id: 'CA', d: (g, w, h) => { g.fillStyle = '#d80621'; g.fillRect(0, 0, w, h); g.fillStyle = '#fff'; g.fillRect(w / 4, 0, w / 2, h); g.fillStyle = '#d80621'; const x = w / 2, y = h / 2, s = h * 0.3; g.beginPath(); const pts = [0, -1, 0.15, -0.6, 0.35, -0.7, 0.3, -0.25, 0.65, -0.45, 0.55, -0.15, 0.8, 0, 0.45, 0.25, 0.5, 0.45, 0.05, 0.35, 0.05, 0.8, -0.05, 0.8, -0.05, 0.35, -0.5, 0.45, -0.45, 0.25, -0.8, 0, -0.55, -0.15, -0.65, -0.45, -0.3, -0.25, -0.35, -0.7, -0.15, -0.6]; for (let i = 0; i < pts.length; i += 2) g.lineTo(x + pts[i] * s, y + pts[i + 1] * s); g.closePath(); g.fill(); } },
    { id: 'EG', d: (g, w, h) => { H3('#ce1126', '#ffffff', '#000000')(g, w, h); g.fillStyle = '#c09300'; g.beginPath(); g.ellipse(w / 2, h / 2, w * 0.06, h * 0.12, 0, 0, 7); g.fill(); } },
    { id: 'AE', d: (g, w, h) => { H3('#00732f', '#ffffff', '#000000')(g, w, h); g.fillStyle = '#ff0000'; g.fillRect(0, 0, w * 0.25, h); } },
    { id: 'NG', d: V3('#008751', '#ffffff', '#008751') },
    { id: 'PK', d: (g, w, h) => { g.fillStyle = '#fff'; g.fillRect(0, 0, w * 0.25, h); g.fillStyle = '#01411c'; g.fillRect(w * 0.25, 0, w, h); crescent(g, w * 0.62, h / 2, h * 0.27, '#01411c', '#fff', -0.25); g.fillStyle = '#fff'; star5(g, w * 0.72, h * 0.36, h * 0.09, -0.6); } },
    { id: 'AZ', d: (g, w, h) => { H3('#0092bc', '#e4002b', '#00af66')(g, w, h); crescent(g, w * 0.47, h / 2, h * 0.12, '#e4002b', '#fff', 0.25); g.fillStyle = '#fff'; star5(g, w * 0.56, h / 2, h * 0.06); } },
    { id: 'GE', d: (g, w, h) => { g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.fillStyle = '#ff0000'; g.fillRect(w * 0.43, 0, w * 0.14, h); g.fillRect(0, h * 0.4, w, h * 0.2); [[0.2, 0.2], [0.8, 0.2], [0.2, 0.8], [0.8, 0.8]].forEach(([a, b]) => { g.fillRect(w * a - w * 0.06, h * b - h * 0.02, w * 0.12, h * 0.04); g.fillRect(w * a - w * 0.02, h * b - h * 0.08, w * 0.04, h * 0.16); }); } },
    { id: 'AM', d: H3('#d90012', '#0033a0', '#f2a800') },
    { id: 'TJ', d: (g, w, h) => { g.fillStyle = '#cc0000'; g.fillRect(0, 0, w, h * 0.28); g.fillStyle = '#fff'; g.fillRect(0, h * 0.28, w, h * 0.44); g.fillStyle = '#006600'; g.fillRect(0, h * 0.72, w, h); g.fillStyle = '#f8c300'; g.beginPath(); g.arc(w / 2, h * 0.5, h * 0.09, Math.PI, 0); g.fill(); for (let i = 0; i < 7; i++) { const a = Math.PI + (i / 6) * Math.PI; star5(g, w / 2 + Math.cos(a) * h * 0.17, h * 0.52 + Math.sin(a) * h * 0.15, h * 0.03); } } },
    { id: 'MN', d: (g, w, h) => { V3('#c4272f', '#015197', '#c4272f')(g, w, h); g.fillStyle = '#f9cf02'; g.beginPath(); g.arc(w / 6, h * 0.3, h * 0.06, 0, 7); g.fill(); g.fillRect(w / 6 - w * 0.04, h * 0.4, w * 0.08, h * 0.35); } },
  ];
  const SPECIAL = [
    { id: 'gold', ads: 3, coins: 2000, d: (g, w, h) => { const gr = g.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#fff3b0'); gr.addColorStop(0.4, '#ffcf2e'); gr.addColorStop(0.7, '#e09b00'); gr.addColorStop(1, '#fff0a0'); g.fillStyle = gr; g.fillRect(0, 0, w, h); g.fillStyle = 'rgba(255,255,255,0.8)'; star5(g, w * 0.3, h * 0.3, h * 0.1); } },
    { id: 'rainbow', ads: 3, coins: 2000, d: (g, w, h) => { const cols = ['#ff3b30', '#ff9500', '#ffcc00', '#34c759', '#0a84ff', '#5e5ce6', '#bf5af2']; cols.forEach((c2, i) => { g.fillStyle = c2; g.fillRect(0, (i * h) / 7, w, h / 7 + 1); }); } },
    { id: 'earth', ads: 3, coins: 2000, d: (g, w, h) => { g.fillStyle = '#1e88e5'; g.fillRect(0, 0, w, h); g.fillStyle = '#43a047'; const r = C.seeded(3); for (let i = 0; i < 9; i++) { g.beginPath(); g.ellipse(r() * w, r() * h, 10 + r() * 22, 8 + r() * 16, r() * 3, 0, 7); g.fill(); } g.fillStyle = 'rgba(255,255,255,0.85)'; g.fillRect(0, 0, w, h * 0.07); g.fillRect(0, h * 0.93, w, h * 0.07); } },
    { id: 'football', ads: 3, coins: 2000, d: (g, w, h) => { g.fillStyle = '#fff'; g.fillRect(0, 0, w, h); g.fillStyle = '#111'; const pent = (x, y, r) => { g.beginPath(); for (let i = 0; i < 5; i++) { const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5; g.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); } g.closePath(); g.fill(); }; pent(w / 2, h / 2, 18); [[0.12, 0.2], [0.88, 0.2], [0.12, 0.85], [0.88, 0.85], [0.5, 0.02], [0.5, 1]].forEach(([a, b]) => pent(w * a, h * b, 15)); } },
    { id: 'neon', ads: 3, coins: 2000, d: (g, w, h) => { g.fillStyle = '#12002b'; g.fillRect(0, 0, w, h); g.strokeStyle = '#00f5ff'; g.lineWidth = 6; for (let i = 0; i < 4; i++) { g.beginPath(); g.arc(w / 2, h / 2, 14 + i * 18, 0, 7); g.stroke(); } g.strokeStyle = '#ff2bd6'; g.lineWidth = 4; g.beginPath(); g.moveTo(0, h / 2); g.lineTo(w, h / 2); g.stroke(); } },
    { id: 'galaxy', ads: 3, coins: 2000, d: (g, w, h) => { const gr = g.createRadialGradient(w * 0.4, h * 0.4, 5, w / 2, h / 2, w * 0.7); gr.addColorStop(0, '#ff7ad9'); gr.addColorStop(0.4, '#5b2bd9'); gr.addColorStop(1, '#0b0630'); g.fillStyle = gr; g.fillRect(0, 0, w, h); g.fillStyle = '#fff'; const r = C.seeded(9); for (let i = 0; i < 40; i++) { g.globalAlpha = 0.4 + r() * 0.6; g.fillRect(r() * w, r() * h, 2 + r() * 2, 2 + r() * 2); } g.globalAlpha = 1; } },
  ];
  C.SKINS = C.FLAGS.map((f) => ({ id: f.id, d: f.d, price: 300 })).concat(SPECIAL.map((s) => ({ id: s.id, d: s.d, special: true, ads: s.ads, coins: s.coins })));
  C.skinById = (id) => C.SKINS.find((s) => s.id === id) || C.SKINS[0];
  const texCache = {};
  C.skinTex = (id) => {
    if (texCache[id]) return texCache[id];
    const S = C.TEX || 256; // размер текстуры шарика (крупные шарики не мылятся)
    const t = document.createElement('canvas'); t.width = t.height = S; const g = t.getContext('2d');
    if (id === 'white') { g.fillStyle = '#eceff1'; g.fillRect(0, 0, S, S); g.fillStyle = '#cfd8dc'; g.fillRect(0, S * 0.47, S, S / 16); } else C.skinById(id).d(g, S, S);
    texCache[id] = t; return t;
  };
  C.flagTex = (id) => { // прямоугольный флаг 3:2 для подписей
    const k = 'f_' + id; if (texCache[k]) return texCache[k];
    const t = document.createElement('canvas'); t.width = 96; t.height = 64; C.skinById(id).d(t.getContext('2d'), 96, 64); texCache[k] = t; return t;
  };
  C.drawBall = (x, y, r, id, ang = 0, c = ctx, glow) => {
    c.save();
    if (glow) { c.shadowColor = glow; c.shadowBlur = r * 0.8; }
    c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fillStyle = '#fff'; c.fill();
    c.shadowBlur = 0; c.clip();
    c.translate(x, y); c.rotate(ang); c.drawImage(C.skinTex(id), -r * 1.08, -r * 1.08, r * 2.16, r * 2.16);
    c.restore();
    const g = c.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.05, x, y, r * 1.02);
    g.addColorStop(0, 'rgba(255,255,255,0.65)'); g.addColorStop(0.3, 'rgba(255,255,255,0.05)'); g.addColorStop(0.75, 'rgba(0,0,0,0.05)'); g.addColorStop(1, 'rgba(0,0,0,0.38)');
    c.fillStyle = g; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill();
    c.lineWidth = Math.max(1.5, r * 0.07); c.strokeStyle = 'rgba(0,0,0,0.35)'; c.stroke();
  };
  // Страна игрока — по языку/региону
  const LANG2C = { ru: 'RU', kk: 'KZ', uz: 'UZ', ky: 'KG', uk: 'UA', be: 'BY', tr: 'TR', en: 'US', de: 'DE', fr: 'FR', it: 'IT', es: 'ES', pt: 'BR', zh: 'CN', ja: 'JP', ko: 'KR', hi: 'IN', id: 'ID', in: 'ID', vi: 'VN', th: 'TH', pl: 'PL', nl: 'NL', sv: 'SE', no: 'NO', nb: 'NO', fi: 'FI', ar: 'EG', az: 'AZ', ka: 'GE', hy: 'AM', tg: 'TJ', mn: 'MN', ur: 'PK' };
  C.homeCountry = () => {
    const parts = (C.lang || 'en').replace('_', '-').split('-');
    const region = (parts[1] || '').toUpperCase();
    if (region && C.FLAGS.some((f) => f.id === region)) return region;
    return LANG2C[parts[0]] || 'US';
  };
  C.mySkin = () => C.save.skin || C.homeCountry();
  C.rivals = (n, avoid = []) => {
    const pool = C.FLAGS.map((f) => f.id).filter((id) => id !== C.mySkin() && !avoid.includes(id));
    return C.shuffle(pool).slice(0, n);
  };

  // ---------- монеты, частицы, всплывашки ----------
  C.coinsShown = 0;
  C.coinHud = { x: 70, y: 62 };
  const parts = []; const flyers = []; const toasts = [];
  C.addCoins = (n, fromX, fromY) => {
    C.save.coins += n; C.persist();
    if (fromX === undefined) { C.coinsShown = C.save.coins; return; }
    const k = Math.min(14, Math.max(4, Math.round(n / 10)));
    for (let i = 0; i < k; i++) flyers.push({ x: fromX + C.rnd(-30, 30), y: fromY + C.rnd(-30, 30), t: -i * 0.05, v: n / k });
  };
  C.spend = (n) => { if (C.save.coins < n) return false; C.save.coins -= n; C.coinsShown = C.save.coins; C.persist(); return true; };
  C.confetti = (x, y, n = 80) => {
    const cols = ['#ff3b30', '#ffcc00', '#34c759', '#0a84ff', '#bf5af2', '#ff9500'];
    for (let i = 0; i < n; i++) parts.push({ x, y, vx: C.rnd(-500, 500), vy: C.rnd(-1100, -300), r: C.rnd(6, 12), c: C.pick(cols), a: C.rnd(0, 6), va: C.rnd(-10, 10), life: C.rnd(1.6, 2.6) });
  };
  C.burst = (x, y, color, n = 16, speed = 400) => {
    for (let i = 0; i < n; i++) { const a = C.rnd(0, Math.PI * 2), s = C.rnd(speed * 0.3, speed); parts.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, r: C.rnd(4, 9), c: color, a: 0, va: 0, life: C.rnd(0.4, 0.8), round: true }); }
  };
  C.toast = (icon, label) => { toasts.push({ icon, label, t: 0 }); };

  function drawParticles(dt) {
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i]; p.life -= dt; if (p.life <= 0) { parts.splice(i, 1); continue; }
      p.vy += 1600 * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.vx *= 0.99; p.a += p.va * dt;
      ctx.save(); ctx.globalAlpha = Math.min(1, p.life * 2); ctx.fillStyle = p.c; ctx.translate(p.x, p.y); ctx.rotate(p.a);
      if (p.round) { ctx.beginPath(); ctx.arc(0, 0, p.r, 0, 7); ctx.fill(); } else ctx.fillRect(-p.r, -p.r * 0.5, p.r * 2, p.r);
      ctx.restore();
    }
    for (let i = flyers.length - 1; i >= 0; i--) {
      const f = flyers[i]; f.t += dt; if (f.t < 0) continue;
      const k = C.easeOut(Math.min(1, f.t / 0.6));
      const x = C.lerp(f.x, C.coinHud.x, k), y = C.lerp(f.y, C.coinHud.y, k) - Math.sin(k * Math.PI) * 120;
      C.icon('coin', x, y, 44);
      if (f.t >= 0.6) { flyers.splice(i, 1); C.coinsShown = Math.min(C.save.coins, C.coinsShown + f.v); C.sfx('coin'); }
    }
    if (!flyers.length) C.coinsShown = C.save.coins;
    for (let i = toasts.length - 1; i >= 0; i--) {
      const t = toasts[i]; t.t += dt; if (t.t > 1.6) { toasts.splice(i, 1); continue; }
      const a = t.t < 0.2 ? t.t / 0.2 : t.t > 1.3 ? (1.6 - t.t) / 0.3 : 1;
      ctx.save(); ctx.globalAlpha = a; const y = C.H * 0.32 - t.t * 30;
      ctx.fillStyle = 'rgba(0,0,0,0.6)'; C.rr(ctx, C.W / 2 - 110, y - 50, 220, 100, 50); ctx.fill();
      if (t.icon) C.icon(t.icon, C.W / 2 - (t.label ? 40 : 0), y, 60, t.icon === 'noad' ? '#fff' : '#fff');
      if (t.label) C.text(t.label, C.W / 2 + 40, y, 44);
      ctx.restore();
    }
  }

  // ---------- HUD монет ----------
  C.drawCoinsHud = () => {
    const x = 22, y = 30, w = 210, h = 64;
    ctx.fillStyle = 'rgba(0,0,0,0.35)'; C.rr(ctx, x, y, w, h, 32); ctx.fill();
    C.icon('coin', x + 34, y + h / 2, 52);
    C.text(String(Math.floor(C.coinsShown)), x + 70, y + h / 2 + 2, 38, '#fff', 'left');
    C.coinHud.x = x + 34; C.coinHud.y = y + h / 2;
  };

  // ---------- ежедневный подарок и сундук ----------
  const GIFTS = [50, 80, 120, 160, 200, 300, 'skin'];
  C.giftReady = () => C.save.day.last !== C.today();
  const CHEST_EVERY = 8 * 60;
  C.chestLeft = () => Math.max(0, CHEST_EVERY - (Date.now() / 1000 - (C.save.chestAt || 0)));
  C.unownedFlags = () => C.FLAGS.map((f) => f.id).filter((id) => !C.save.owned[id] && id !== C.homeCountry());
  C.grantSkin = (id) => { C.save.owned[id] = true; C.save.skin = id; C.persist(); C.sfx('buy'); C.confetti(C.W / 2, C.H * 0.45, 60); };

  C.popupPush = (p) => { C.popup = p; };
  C.openGift = () => { C.popup = { kind: 'gift', t0: now() }; };
  C.openChest = () => { C.popup = { kind: 'chest', t0: now() }; };
  C.showReward = (rw) => { C.popup = { kind: 'reward', t0: now(), rw }; };

  // Боковые кнопки (магазин, подарок, сундук, звук)
  C.sideButtons = (x0 = 22, y0 = 120, horiz = false) => {
    const s = horiz ? 86 : 96;
    const pos = (i) => (horiz ? [x0 + i * (s + 14), y0] : [x0, y0 + i * (s + 18)]);
    if (C.button('shop', pos(0)[0], pos(0)[1], s, s, { color: '#7c4dff', icon: 'shop', iconColor: '#ffcf2e' })) { C.shopFrom = C.state; C.state = 'shop'; }
    if (C.button('giftBtn', pos(1)[0], pos(1)[1], s, s, { color: '#ff7a90', draw: (c) => C.icon('gift', 0, 0, 56), badge: C.giftReady(), pulse: C.giftReady() })) C.openGift();
    const left = C.chestLeft();
    if (C.rewardedSupported) {
      if (C.button('chestBtn', pos(2)[0], pos(2)[1], s, s, { color: left <= 0 ? '#ffb300' : '#8d6e63', pulse: left <= 0, draw: (c) => { C.icon('chest', 0, left <= 0 ? -4 : -10, 54); if (left > 0) C.text(Math.floor(left / 60) + ':' + String(Math.floor(left % 60)).padStart(2, '0'), 0, 28, 22); else C.icon('ad', 24, 26, 30); } }) && left <= 0) C.openChest();
    }
  };
  C.soundButton = (x, y) => {
    if (C.button('sound', x, y, 84, 84, { color: '#455a64', icon: C.save.sound ? 'sound' : 'mute', iconSize: 46 })) { C.save.sound = !C.save.sound; C.persist(); A.update(); }
  };

  // ---------- магазин ----------
  let shopScroll = 0;
  function drawShop() {
    ctx.fillStyle = 'rgba(10,10,30,0.82)'; ctx.fillRect(0, 0, C.W, C.H); UI.block();
    const pw = Math.min(680, C.W - 30), px = (C.W - pw) / 2, py = 110, ph = C.H - 150;
    C.panel(px, py, pw, ph, '#fff4e0');
    const cols = 4, cw = (pw - 40) / cols, chh = cw * 1.18;
    const items = C.SKINS.slice().sort((a, b) => (a.id === C.homeCountry() ? -1 : b.id === C.homeCountry() ? 1 : 0));
    const rows = Math.ceil(items.length / cols);
    const viewTop = py + 30, viewH = ph - 60;
    const maxScroll = Math.max(0, rows * chh - viewH);
    shopScroll = C.clamp(shopScroll, -maxScroll, 0);
    UI.next.push({ id: 'shopArea', x: px, y: viewTop, w: pw, h: viewH, scroll: { get: () => shopScroll, set: (v) => { shopScroll = C.clamp(v, -maxScroll, 0); } } });
    ctx.save(); ctx.beginPath(); ctx.rect(px, viewTop, pw, viewH); ctx.clip();
    items.forEach((s, i) => {
      const cx = px + 20 + (i % cols) * cw, cy = viewTop + Math.floor(i / cols) * chh + shopScroll;
      if (cy + chh < viewTop - 10 || cy > viewTop + viewH + 10) return;
      const owned = C.save.owned[s.id] || s.id === C.homeCountry();
      const sel = C.mySkin() === s.id;
      const id = 'skin_' + s.id;
      const pressed = UI.pressId === id;
      ctx.fillStyle = sel ? '#ffe082' : '#ffffff'; C.rr(ctx, cx + 6, cy + 6, cw - 12, chh - 12, 22); ctx.fill();
      if (sel) { ctx.strokeStyle = '#ff9800'; ctx.lineWidth = 6; ctx.stroke(); }
      const r = cw * 0.3 * (pressed ? 0.92 : 1);
      C.drawBall(cx + cw / 2, cy + chh * 0.4, r, s.id, 0, ctx, s.special ? '#ffd54f' : null);
      const ly = cy + chh * 0.8;
      if (owned) { if (sel) C.icon('check', cx + cw / 2, ly, 40, '#2e7d32'); }
      else if (s.special) {
        const pr = C.save.adProg[s.id] || 0;
        if (C.rewardedSupported) { C.icon('ad', cx + cw / 2 - 26, ly, 36, '#455a64'); C.text(pr + '/' + s.ads, cx + cw / 2 + 22, ly, 30, '#333', 'center', null); }
        else { C.icon('coin', cx + cw / 2 - 34, ly, 32); C.text(String(s.coins), cx + cw / 2 + 14, ly, 28, '#333', 'center', null); }
      } else { C.icon('coin', cx + cw / 2 - 30, ly, 34); C.text(String(s.price), cx + cw / 2 + 14, ly, 30, C.save.coins >= s.price ? '#333' : '#c62828', 'center', null); }
      if (UI.zone(id, cx, Math.max(cy, viewTop), cw, Math.min(chh, viewTop + viewH - Math.max(cy, viewTop)))) shopTap(s, owned);
    });
    ctx.restore();
    if (C.button('shopClose', px + pw - 90, py - 40, 100, 100, { color: '#e53935', icon: 'close', round: true, iconSize: 44 })) { C.state = C.shopFrom || 'home'; }
    C.drawCoinsHud();
  }
  async function shopTap(s, owned) {
    if (owned) { C.save.skin = s.id; C.persist(); C.sfx('tap'); return; }
    if (s.special) {
      if (!C.rewardedSupported) { if (C.spend(s.coins)) C.grantSkin(s.id); else { C.sfx('hit'); C.toast('coin', String(s.coins - C.save.coins)); } return; }
      const ok = await ads.rewarded('exclusive_skin');
      if (ok) { C.save.adProg[s.id] = (C.save.adProg[s.id] || 0) + 1; C.persist(); C.sfx('star', 1); if (C.save.adProg[s.id] >= s.ads) C.grantSkin(s.id); }
      return;
    }
    if (C.spend(s.price)) { C.grantSkin(s.id); return; }
    if (C.rewardedSupported && C.save.coins >= s.price / 2) { const ok = await ads.rewarded('unlock_skin'); if (ok) C.grantSkin(s.id); return; }
    C.sfx('hit'); C.toast('coin', String(s.price - C.save.coins));
  }

  // ---------- окна победы и проигрыша ----------
  C.result = null;
  C.win = (r) => { // r: {stars, place, coins}
    if (C.state !== 'play') return;
    C.state = 'win'; C.result = Object.assign({ t0: now(), stars: 3, place: 0, coins: 20, taken: false }, r);
    C.save.stars[C.save.level] = Math.max(C.save.stars[C.save.level] || 0, C.result.stars); C.save.fails[C.save.level] = 0; C.persist();
    C.msg('level_completed'); C.msg('gameplay_stopped'); C.sfx('win'); C.confetti(C.W / 2, C.H * 0.35, 90);
  };
  C.fail = (r = {}) => {
    if (C.state !== 'play') return;
    C.state = 'fail'; C.result = Object.assign({ t0: now(), revive: true }, r);
    C.save.fails[C.save.level] = (C.save.fails[C.save.level] || 0) + 1; C.persist();
    C.msg('level_failed'); C.msg('gameplay_stopped'); C.sfx('fail');
  };
  C.revivedThisTry = false;
  C.startLevel = async (fromRetry) => {
    if (fromRetry === 'next' || fromRetry === 'retry') await ads.interstitial(fromRetry === 'next' ? 'next_level' : 'retry');
    C.state = 'play'; C.result = null; C.revivedThisTry = false; C.save.plays++; C.persist();
    if (C.game.startLevel) C.game.startLevel(C.save.level);
    C.msg('level_started'); C.msg('gameplay_started');
  };
  function drawWin() {
    const r = C.result, t = now() - r.t0;
    ctx.fillStyle = 'rgba(0,0,0,' + Math.min(0.45, t) + ')'; ctx.fillRect(0, 0, C.W, C.H); UI.block();
    const k = C.easeOutBack(Math.min(1, t / 0.4));
    const pw = 600, ph = 700, px = C.W / 2 - pw / 2, py = C.H * 0.5 - ph / 2;
    ctx.save(); ctx.translate(C.W / 2, C.H / 2); ctx.scale(k, k); ctx.translate(-C.W / 2, -C.H / 2);
    C.panel(px, py, pw, ph, '#fffaf0');
    C.icon('trophy', C.W / 2, py - 10, 150);
    for (let i = 0; i < 3; i++) {
      const st = Math.min(1, Math.max(0, (t - 0.4 - i * 0.2) / 0.3));
      const got = i < r.stars;
      const sx = C.W / 2 + (i - 1) * 150, sy = py + 150 - (i === 1 ? 24 : 0);
      C.icon('starEmpty', sx, sy, 120);
      if (got && st > 0) { C.icon('star', sx, sy, 120 * C.easeOutBack(st)); if (st >= 1 && !r['s' + i]) { r['s' + i] = 1; C.sfx('star', i); } }
    }
    if (r.place) { C.text('#' + r.place, C.W / 2, py + 270, 64, r.place === 1 ? '#ffb300' : '#78909c'); }
    C.icon('coin', C.W / 2 - 60, py + 360, 70); C.text('+' + r.coins, C.W / 2 + 30, py + 362, 60, '#ff9800');
    ctx.restore();
    if (r.taken) return;
    if (t > 0.6 && C.rewardedSupported) {
      if (C.button('x3', C.W / 2 - 220, py + 430, 440, 120, { color: '#43a047', ad: true, label: '×3', pulse: true })) {
        r.taken = true; ads.rewarded('win_x3').then((ok) => {
          if (ok) { C.addCoins(r.coins * 3, C.W / 2, py + 360); setTimeout(() => goNext(), 900); }
          else { r.taken = false; }
        });
      }
    }
    const nextDelay = C.rewardedSupported ? 1.6 : 0.6;
    if (t > nextDelay) {
      if (C.button('nextBtn', C.W / 2 - 70, py + 570 + (C.rewardedSupported ? 20 : -100), 140, 96, { color: '#90a4ae', icon: 'next', iconSize: 46, alpha: C.clamp((t - nextDelay) * 3, 0, 1) })) {
        r.taken = true; C.addCoins(r.coins, C.W / 2, py + 360); setTimeout(() => goNext(), 700);
      }
    }
  }
  function goNext() { C.save.level++; C.persist(); if (C.game.resultToHome) toHomeAfter('next_level'); else C.startLevel('next'); }
  async function toHomeAfter(pl) { await ads.interstitial(pl); C.state = 'home'; C.result = null; if (C.game.toHome) C.game.toHome(); }
  function drawFail() {
    const r = C.result, t = now() - r.t0;
    ctx.fillStyle = 'rgba(0,0,0,' + Math.min(0.5, t) + ')'; ctx.fillRect(0, 0, C.W, C.H); UI.block();
    const k = C.easeOutBack(Math.min(1, t / 0.35));
    const pw = 560, ph = 560, px = C.W / 2 - pw / 2, py = C.H * 0.5 - ph / 2;
    ctx.save(); ctx.translate(C.W / 2, C.H / 2); ctx.scale(k, k); ctx.translate(-C.W / 2, -C.H / 2);
    C.panel(px, py, pw, ph, '#fff0f0');
    C.icon('retry', C.W / 2, py + 110, 120, '#e53935');
    ctx.restore();
    if (r.busy) return;
    const canRevive = r.revive && !C.revivedThisTry && C.rewardedSupported && C.game.revive;
    let y = py + 230;
    if (canRevive) {
      const left = Math.max(0, 6 - t);
      if (left > 0) {
        if (C.button('revive', C.W / 2 - 220, y, 440, 120, { color: '#43a047', pulse: true, draw: (c) => { C.icon('ad', -110, -2, 64); C.icon(C.game.reviveIcon || 'heart', 10, 0, 64, C.game.reviveIcon ? '#ffe082' : '#ff5252'); C.text(String(Math.ceil(left)), 120, 0, 50); } })) {
          r.busy = true; ads.rewarded('revive').then((ok) => {
            r.busy = false;
            if (ok) { C.revivedThisTry = true; C.state = 'play'; C.result = null; C.game.revive(); C.msg('gameplay_started'); }
          });
        }
        y += 150;
      }
    }
    const fails = C.save.fails[C.save.level] || 0;
    if (C.game.hasSkip && fails >= 2 && C.rewardedSupported) {
      if (C.button('skip', C.W / 2 - 220, y, 440, 110, { color: '#fb8c00', ad: true, icon: 'skip' })) {
        r.busy = true; ads.rewarded('skip_level').then((ok) => { r.busy = false; if (ok) { C.save.level++; C.persist(); C.startLevel(); } });
      }
      y += 140;
    }
    if (t > (canRevive ? 1.4 : 0.4)) {
      if (C.button('retryBtn', C.W / 2 - 70, Math.max(y, py + ph - 130), 140, 100, { color: '#90a4ae', icon: C.game.resultToHome ? 'home' : 'retry', iconSize: 50 })) { if (C.game.resultToHome) toHomeAfter('retry'); else C.startLevel('retry'); }
    }
  }

  // ---------- главный экран ----------
  function drawHome() {
    ctx.fillStyle = 'rgba(10,20,40,0.35)'; ctx.fillRect(0, 0, C.W, C.H);
    C.drawCoinsHud();
    C.sideButtons();
    C.soundButton(C.W - 106, 30);
    const cy = C.H * 0.62;
    C.text(String(C.save.level), C.W / 2, cy - 250, 110, '#fff');
    C.drawBall(C.W / 2, cy - 90, 80 + Math.sin(C.realT * 3) * 4, C.mySkin(), Math.sin(C.realT) * 0.3);
    if (C.button('playBtn', C.W / 2 - 170, cy + 40, 340, 150, { color: '#43a047', icon: 'play', iconSize: 80, pulse: true })) { C.startLevel(); }
  }
  C.homeOverlay = drawHome;

  // ---------- всплывающие окна ----------
  function drawPopup() {
    const p = C.popup; if (!p) return;
    const t = now() - p.t0;
    if (p.kind === 'adMock') {
      ctx.fillStyle = '#111'; ctx.fillRect(0, 0, C.W, C.H); UI.block('adblock');
      const k = Math.min(1, t / p.dur);
      C.icon('ad', C.W / 2, C.H / 2 - 40, 200, p.rewarded ? '#ffffff' : '#90a4ae');
      ctx.strokeStyle = '#43a047'; ctx.lineWidth = 14; ctx.beginPath(); ctx.arc(C.W / 2, C.H / 2 - 40, 150, -Math.PI / 2, -Math.PI / 2 + k * Math.PI * 2); ctx.stroke();
      ctx.font = C.font(30); ctx.fillStyle = '#9e9e9e'; ctx.textAlign = 'center';
      const ru = (C.lang || '').slice(0, 2) === 'ru';
      ctx.fillText(p.rewarded ? (ru ? 'реклама за награду (тест)' : 'rewarded ad (test)') : (ru ? 'межстраничная реклама (тест)' : 'midgame ad (test)'), C.W / 2, C.H / 2 + 170);
      if (t >= p.dur) { C.popup = null; if (p.rewarded) { ads._rewarded = true; ads.lastRewardEnd = now(); } ads._finish(p.rewarded ? true : true); }
      return;
    }
    ctx.fillStyle = 'rgba(0,0,0,0.55)'; ctx.fillRect(0, 0, C.W, C.H); UI.block();
    const k = C.easeOutBack(Math.min(1, t / 0.35));
    const pw = 620, ph = 640, px = C.W / 2 - pw / 2, py = C.H / 2 - ph / 2;
    ctx.save(); ctx.translate(C.W / 2, C.H / 2); ctx.scale(k, k); ctx.translate(-C.W / 2, -C.H / 2);
    C.panel(px, py, pw, ph, '#fff8e1');
    if (p.kind === 'gift') {
      const ready = C.giftReady();
      const streak = ready ? (C.save.day.streak % 7) : ((C.save.day.streak - 1 + 7) % 7);
      C.icon('gift', C.W / 2, py + 110, 150);
      for (let i = 0; i < 7; i++) {
        const bx = px + 30 + i * ((pw - 60) / 7), bw = (pw - 60) / 7 - 8, by = py + 220;
        ctx.fillStyle = i < streak ? '#c8e6c9' : i === streak ? '#ffe082' : '#eeeeee'; C.rr(ctx, bx, by, bw, 110, 14); ctx.fill();
        if (GIFTS[i] === 'skin') C.icon('shop', bx + bw / 2, by + 55, 56, '#7c4dff'); else { C.icon('coin', bx + bw / 2, by + 38, 34); C.text(String(GIFTS[i]), bx + bw / 2, by + 82, 24, '#333', 'center', null); }
        if (i < streak) C.icon('check', bx + bw / 2, by + 55, 40, '#2e7d32');
      }
      ctx.restore();
      if (ready) {
        const g = GIFTS[streak];
        const claim = (mult) => {
          C.save.day.last = C.today(); C.save.day.streak = streak + 1; C.persist();
          if (g === 'skin') { const pool = C.unownedFlags(); if (pool.length) C.grantSkin(C.pick(pool)); else C.addCoins(500 * mult, C.W / 2, py + 270); }
          else C.addCoins(g * mult, C.W / 2, py + 270);
          C.popup = null;
        };
        if (C.rewardedSupported && g !== 'skin') {
          if (C.button('gift2', C.W / 2 - 200, py + 380, 400, 116, { color: '#43a047', ad: true, label: '×2', pulse: true })) { p.busy = true; ads.rewarded('daily_x2').then((ok) => { p.busy = false; if (ok) claim(2); }); }
        }
        if (t > 1 && !p.busy) { if (C.button('gift1', C.W / 2 - 80, py + 520, 160, 90, { color: '#90a4ae', icon: 'check', iconSize: 44 })) claim(1); }
      } else {
        C.icon('clock', C.W / 2, py + 440, 90, '#90a4ae');
        if (C.button('giftClose', C.W / 2 - 80, py + 520, 160, 90, { color: '#90a4ae', icon: 'close', iconSize: 40 })) C.popup = null;
      }
      return;
    }
    if (p.kind === 'chest') {
      C.icon('chest', C.W / 2, py + 200, 220 + Math.sin(t * 8) * 6);
      ctx.restore();
      if (!p.busy && C.button('chestOpen', C.W / 2 - 200, py + 380, 400, 120, { color: '#43a047', ad: true, icon: 'chest', pulse: true })) {
        p.busy = true; ads.rewarded('chest').then((ok) => {
          p.busy = false; if (!ok) return;
          C.save.chestAt = Date.now() / 1000; C.persist();
          const pool = C.unownedFlags();
          if (Math.random() < 0.3 && pool.length) { const id = C.pick(pool); C.grantSkin(id); C.showReward({ skin: id }); }
          else { const n = C.pick([80, 100, 150, 200, 250]); C.showReward({ coins: n }); }
        });
      }
      if (!p.busy && C.button('chestClose', C.W / 2 - 70, py + 530, 140, 90, { color: '#90a4ae', icon: 'close', iconSize: 40 })) C.popup = null;
      return;
    }
    if (p.kind === 'reward') {
      if (p.rw.skin) C.drawBall(C.W / 2, py + 230, 120, p.rw.skin, 0, ctx, '#ffd54f');
      if (p.rw.coins) { C.icon('coin', C.W / 2, py + 200, 160); C.text('+' + p.rw.coins, C.W / 2, py + 360, 80, '#ff9800'); }
      if (p.rw.label) C.text(p.rw.label, C.W / 2, py + 360, 70, '#ff9800');
      ctx.restore();
      if (t > 0.5 && C.button('rwOk', C.W / 2 - 110, py + 480, 220, 110, { color: '#43a047', icon: 'check', iconSize: 50 })) {
        if (p.rw.coins) C.addCoins(p.rw.coins, C.W / 2, py + 200);
        if (p.rw.onOk) p.rw.onOk();
        C.popup = null;
      }
      return;
    }
    ctx.restore();
  }

  // ---------- пауза ----------
  C.userPause = false;
  function drawPause() {
    ctx.fillStyle = 'rgba(10,10,30,0.6)'; ctx.fillRect(0, 0, C.W, C.H); UI.block();
    C.panel(C.W / 2 - 230, C.H / 2 - 230, 460, 460, '#fff8e1');
    C.icon('pause', C.W / 2, C.H / 2 - 150, 80, '#90a4ae');
    if (C.button('resume', C.W / 2 - 170, C.H / 2 - 70, 340, 130, { color: '#43a047', icon: 'play', iconSize: 70, pulse: true })) { C.userPause = false; C.msg('gameplay_started'); C.audio.update(); }
    if (C.button('pSound', C.W / 2 - 170, C.H / 2 + 90, 150, 100, { color: '#455a64', icon: C.save.sound ? 'sound' : 'mute', iconSize: 50 })) { C.save.sound = !C.save.sound; C.persist(); C.audio.update(); }
    if (C.button('pHome', C.W / 2 + 20, C.H / 2 + 90, 150, 100, { color: '#e57373', icon: 'home', iconSize: 50 })) { C.userPause = false; C.state = 'home'; if (C.game.toHome) C.game.toHome(); C.audio.update(); }
  }

  // ---------- клавиатура (для ПК) ----------
  C.keys = {};
  window.addEventListener('keydown', (e) => {
    const k = e.code; C.keys[k] = true; A.init();
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space'].includes(k)) e.preventDefault();
    if ((k === 'Escape' || k === 'KeyP') && C.state === 'play' && !C.game.noPauseBtn) { C.userPause = !C.userPause; C.audio.update(); }
    if ((k === 'Space' || k === 'Enter') && C.state === 'home' && !C.popup && !C.userPause) C.startLevel();
    if (C.game.onKey) C.game.onKey(k, true);
  });
  window.addEventListener('keyup', (e) => { C.keys[e.code] = false; if (C.game && C.game.onKey) C.game.onKey(e.code, false); });
  C.keyDir = () => ((C.keys.ArrowRight || C.keys.KeyD ? 1 : 0) - (C.keys.ArrowLeft || C.keys.KeyA ? 1 : 0));
  C.keyDirY = () => ((C.keys.ArrowDown || C.keys.KeyS ? 1 : 0) - (C.keys.ArrowUp || C.keys.KeyW ? 1 : 0));

  // ---------- главный цикл ----------
  let last = now(); C.realT = 0;
  function frame() {
    const tn = now(); let dt = Math.min(1 / 30, tn - last); last = tn; C.realT += dt;
    const frozen = C.paused || C.adPlaying || C.hidden || C.userPause;
    C.dt = frozen ? 0 : dt;
    if (!frozen) C.t += dt;
    ctx.setTransform(C.scale * C.dpr, 0, 0, C.scale * C.dpr, 0, 0);
    UI.next = [];
    if (C.game) {
      if (!frozen && C.game.update) C.game.update(C.dt);
      C.game.draw(ctx);
      if (C.state === 'home') { if (C.game.drawHome) C.game.drawHome(ctx); else drawHome(); }
      else if (C.state === 'play' || C.state === 'win' || C.state === 'fail') {
        if (C.game.hud) C.game.hud(ctx);
        if (C.state === 'play' && !C.game.noPauseBtn) {
          if (C.button('pauseBtn', C.W - 106, 30, 84, 84, { color: '#455a64', icon: 'pause', iconSize: 44 })) { C.userPause = true; C.msg('gameplay_stopped'); C.audio.update(); }
        }
        if (C.state === 'win') drawWin();
        if (C.state === 'fail') drawFail();
      } else if (C.state === 'shop') { if (C.game.drawShopBg) C.game.drawShopBg(ctx); drawShop(); }
    }
    drawPopup();
    if (C.userPause) drawPause();
    drawParticles(dt);
    if (C.state === 'boot') { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, C.W, C.H); }
    UI.rects = UI.next;
    requestAnimationFrame(frame);
  }

  // ---------- запуск ----------
  C.run = async (game) => {
    C.game = game; resize();
    await initBridge();
    await loadSave();
    C.coinsShown = C.save.coins;
    if (!C.save.chestAt) { C.save.chestAt = Date.now() / 1000 - CHEST_EVERY + 180; C.persist(); }
    if (game.init) game.init();
    C.state = game.startState || 'home';
    if (C.state === 'play') { if (game.startLevel) game.startLevel(C.save.level); }
    requestAnimationFrame(frame);
    setTimeout(() => { C.msg('game_ready'); if (C.state === 'play' && !game.manualGameplay) C.msg('gameplay_started'); }, 50);
    if (!game.noGift && C.giftReady() && C.save.plays > 0) setTimeout(() => { if (!C.popup && (C.state === 'home' || game.noLevels)) C.openGift(); }, 800);
  };
})();
