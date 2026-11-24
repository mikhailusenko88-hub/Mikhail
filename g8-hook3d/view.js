'use strict';
/* Hook Truck — рисование, кнопки, звук. Логика — в sim.js. */
(function () {
  const P = window.TPhys, H = window.HookSim;
  let RU = /^(ru|uk|be|kk)/i.test(navigator.language || '');
  const TRU = {
    title: 'HOOK TRUCK', sub: 'Барсик и грузовик на тросе', solo: '1 игрок', duo: '2 игрока',
    touchSolo: 'Правый палец: газ и тормоз · Левый палец: держи КРЮК', touchDuo: 'Игрок 1 — газ справа · Игрок 2 — крюк и «тяни» слева',
    soloTxt: ['Правая рука: → газ, ← тормоз', 'Левая рука: Пробел или W — крюк (держать)'],
    duoTxt: ['Игрок 1 (справа): → газ, ← тормоз', 'Игрок 2 (слева): W или Пробел — крюк, S — тянуть'],
    one: 'Один палец', hand: 'Газ и крюк', two: 'Вдвоём', touchAuto: 'Газ сам. Держи палец — крюк, отпусти — летишь', keyAuto: 'Газ сам. Пробел или мышь: держи — крюк, отпусти — летишь',
    legendAuto: 'Пробел или мышь: держи — крюк, отпусти — летишь', hold: 'ДЕРЖИ', rel: 'ОТПУСТИ!', go: 'Нажми — поехали!', keyHint: 'мышь или Пробел', gasW: 'ГАЗ', space: 'Пробел', x2: '×2', noad: 'Реклама сейчас недоступна', series: 'Серия', opens: 'Откроется за', boing: 'Батут!',
    phone: 'На телефоне: справа газ и тормоз, слева крюк (вся левая половина экрана)',
    legend: '→ газ   ← тормоз   ·   Пробел / W — крюк', start: 'Играть', p1: 'ИГРОК 1', p2: 'ИГРОК 2',
    hook: 'КРЮК', pull: 'ТЯНИ', fell: 'Упал!', crash: 'Авария!', cp: 'Чекпоинт!', star: 'Звезда!',
    win: 'Уровень пройден!', time: 'Время', sec: 'с', tries: 'Попыток', again: 'Ещё раз', menu: 'Меню', got: 'Звезда собрана', nostar: 'Звезда — выше между кольцами',
    pump: 'Жми ГАЗ — раскачайся!', levels: 'Уровни', next: 'Дальше', retry: 'Ещё раз', lvl: 'Уровень', fin: 'Финиш', starW: 'Звезда', play: 'Играть', mode: 'Режим', snap: 'Хрусь!',
    garage: 'Гараж', tabs: ['Грузовик', 'Колёса', 'Цвет', 'Прокачка'], buy: 'Купить', take: 'Забрать', chosen: 'Выбрано', need: 'Не хватает', needStars: 'Нужно', have: 'у тебя',
    eng: 'Мотор', engD: 'Быстрее разгон', winch: 'Лебёдка', winchD: 'Тянет быстрее', max: 'МАКС', total: 'всего', test: 'проба: +500',
  }, TEN = {
    title: 'HOOK TRUCK', sub: 'A truck, a rope and a cat', solo: '1 player', duo: '2 players',
    touchSolo: 'Right thumb: gas & brake · Left thumb: hold HOOK', touchDuo: 'Player 1: gas on the right · Player 2: hook and pull on the left',
    soloTxt: ['Right hand: → gas, ← brake', 'Left hand: hold Space or W to hook'],
    duoTxt: ['Player 1 (right): → gas, ← brake', 'Player 2 (left): W or Space — hook, S — pull'],
    one: 'One finger', hand: 'Gas & hook', two: '2 players', touchAuto: 'Auto gas. Hold to hook, let go to fly', keyAuto: 'Auto gas. Space or mouse: hold to hook, let go to fly',
    legendAuto: 'Space or mouse: hold to hook, let go to fly', hold: 'HOLD', rel: 'LET GO!', go: 'Tap to go!', keyHint: 'mouse or Space', gasW: 'GAS', space: 'Space', x2: '×2', noad: 'No ad available right now', series: 'World', opens: 'Opens at', boing: 'Boing!',
    phone: 'On phones: gas and brake on the right, hook on the left (whole left half)',
    legend: '→ gas   ← brake   ·   Space / W — hook', start: 'Play', p1: 'PLAYER 1', p2: 'PLAYER 2',
    hook: 'HOOK', pull: 'PULL', fell: 'Fell down!', crash: 'Crash!', cp: 'Checkpoint!', star: 'Star!',
    win: 'Level complete!', time: 'Time', sec: 's', tries: 'Tries', again: 'Play again', menu: 'Menu', got: 'Star collected', nostar: 'The star is high between the rings',
    pump: 'Hold GAS to swing!', levels: 'Levels', next: 'Next', retry: 'Retry', lvl: 'Level', fin: 'Finish', starW: 'Star', play: 'Play', mode: 'Mode', snap: 'Snap!',
    garage: 'Garage', tabs: ['Truck', 'Wheels', 'Color', 'Upgrades'], buy: 'Buy', take: 'Unlock', chosen: 'Selected', need: 'Need', needStars: 'Need', have: 'you have',
    eng: 'Engine', engD: 'Faster start', winch: 'Winch', winchD: 'Pulls faster', max: 'MAX', total: 'total', test: 'test: +500',
  };
  let T = RU ? TRU : TEN;

  const cv = document.getElementById('c'), ctx = cv.getContext('2d');
  // объёмный вид (r3d.js): если WebGL нет или в адресе ?flat — остаётся плоский
  const R3 = window.Hook3D && !/[?&]flat\b/.test(location.search) ? window.Hook3D : null, glc = document.getElementById('gl');
  const use3d = !!(R3 && glc && R3.init(glc)); if (!use3d && glc) glc.style.display = 'none';
  let W = 0, H2 = 0, DPR = 1;
  function resize() { DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H2 = innerHeight; cv.width = W * DPR; cv.height = H2 * DPR; }
  addEventListener('resize', resize); resize();

  const rr = (x, y, w, h, r) => { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); };
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  // текст по словам в несколько строк, если не влезает в ширину
  function lines(text, maxW) { const out = []; let cur = ''; for (const w of text.split(' ')) { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { out.push(cur); cur = w; } else cur = t; } if (cur) out.push(cur); return out; }

  // ---------- площадка (Playgama Bridge): язык, пауза, звук, реклама, облачное сохранение ----------
  // Без моста (страница проверки) всё это выключено: рекламных кнопок нет, межстраничной нет.
  const PG = { on: false, rew: false, inter: false, ad: false, paused: false, mutedP: false, ready: false, t0: performance.now(), lastInter: -1e9, lastRew: -1e9, lastFree: -1e9, pend: null, got: false };
  const pgNow = () => performance.now() / 1000;
  const pgMsg = (m, d) => { if (!PG.on) return; try { window.bridge.platform.sendMessage(m, d); } catch (e) { /* */ } };
  function pgDone(v) { const p = PG.pend; PG.pend = null; PG.ad = false; if (p) { clearTimeout(p.tm); p.cb(v); } }
  // межстраничная: только в паузах между уровнями (после уровня или перед стартом уровня из меню), начиная с 3-го уровня,
  // не раньше минуты от запуска, не чаще раза в минуту и не сразу после ролика за награду; чаще не даст и сама площадка
  function pgCanInter(li) { const t = pgNow(); return PG.on && PG.inter && li >= 2 && t - PG.t0 / 1000 > 60 && t - PG.lastInter > 60 && t - PG.lastRew > 90 && !PG.pend; }
  function pgInter(cb, li = lvl) {
    if (!pgCanInter(li)) return cb();
    PG.lastInter = pgNow(); PG.pend = { type: 'inter', cb, tm: setTimeout(() => pgDone(false), 45000) };
    try { window.bridge.advertisement.showInterstitial('level_end'); } catch (e) { pgDone(false); }
  }
  function pgRewarded(place, cb) {
    if (!PG.on || !PG.rew || PG.pend) return cb(false);
    PG.got = false; PG.pend = { type: 'rew', cb, tm: setTimeout(() => pgDone(PG.got), 90000) };
    try { window.bridge.advertisement.showRewarded(place); } catch (e) { pgDone(false); }
  }
  if (window.bridge) {
    Promise.race([window.bridge.initialize(), new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 6000))]).then(() => {
      const B = window.bridge, id = B.platform.id || '';
      PG.on = id !== 'mock' && id !== '';
      // язык: мост отдаёт язык площадки; на CrazyGames там код страны — язык берём из их SDK
      try {
        let lg = String(B.platform.language || '').toLowerCase();
        if (id === 'crazy_games') { const si = (window.CrazyGames && window.CrazyGames.SDK && window.CrazyGames.SDK.user && window.CrazyGames.SDK.user.systemInfo) || {}; lg = String(si.locale || 'en').toLowerCase(); }
        if (lg) setLang(/^(ru|uk|be|kk)/.test(lg));
      } catch (e) { /* */ }
      try { PG.rew = !!B.advertisement.isRewardedSupported; PG.inter = !!B.advertisement.isInterstitialSupported; } catch (e) { /* */ }
      if (window.GAME_ADS === false) { PG.rew = false; PG.inter = false; }
      try { B.platform.on('pause_state_changed', (p) => { PG.paused = !!p; }); B.platform.on('audio_state_changed', (on) => { PG.mutedP = !on; }); PG.mutedP = B.platform.isAudioEnabled === false; } catch (e) { /* */ }
      B.advertisement.on('interstitial_state_changed', (st) => { if (!PG.pend || PG.pend.type !== 'inter') return; if (st === 'opened') PG.ad = true; else if (st === 'closed' || st === 'failed') pgDone(true); });
      B.advertisement.on('rewarded_state_changed', (st) => { if (!PG.pend || PG.pend.type !== 'rew') return; if (st === 'opened') PG.ad = true; else if (st === 'rewarded') PG.got = true; else if (st === 'closed' || st === 'failed') { PG.lastRew = pgNow(); pgDone(PG.got); } });
      // облачное сохранение площадки: берём его, если оно свежее браузерного и игрок ещё не начал заезд
      if (PG.on) B.storage.get('hooktruck_v1').then((v) => { try { const q = typeof v === 'string' ? JSON.parse(v) : v; if (q && Array.isArray(q.stars) && (q.ts || 0) > (save.ts || 0) && mode === 'menu') { adopt(q); duo = !!save.duo; ctl = save.ctl === 'auto' ? 'auto' : 'manual'; ser = H.levels[firstOpen()].ser; applyLook(curLook()); try { localStorage.setItem('hooktruck_v1', JSON.stringify(save)); } catch (e) { /* */ } } } catch (e) { /* */ } }).catch(() => {});
    }).catch(() => { PG.on = false; });
  }
  addEventListener('contextmenu', (e) => e.preventDefault()); // долгое нажатие и правый клик не открывают меню браузера

  // ---------- звук (всё синтезом, без файлов) ----------
  let AC = null, master = null, eng = null, muted = false;
  function audio() {
    if (AC) { if (AC.state === 'suspended') AC.resume(); return; }
    try { AC = new (window.AudioContext || window.webkitAudioContext)(); master = AC.createGain(); master.gain.value = 0.7; master.connect(AC.destination); } catch (e) { AC = null; }
  }
  function tone(f, d, type = 'sine', v = 0.2, f2) {
    if (!AC || muted) return; const t = AC.currentTime, o = AC.createOscillator(), g = AC.createGain();
    o.type = type; o.frequency.setValueAtTime(f, t); if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + d);
    g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t + d); o.connect(g); g.connect(master); o.start(t); o.stop(t + d + 0.02);
  }
  function noise(d, v = 0.3, f = 1200) {
    if (!AC || muted) return; const t = AC.currentTime, n = AC.sampleRate * d, b = AC.createBuffer(1, n, AC.sampleRate), a = b.getChannelData(0);
    for (let i = 0; i < n; i++) a[i] = (Math.random() * 2 - 1) * (1 - i / n);
    const s = AC.createBufferSource(), fl = AC.createBiquadFilter(), g = AC.createGain(); fl.type = 'lowpass'; fl.frequency.value = f; g.gain.value = v;
    s.buffer = b; s.connect(fl); fl.connect(g); g.connect(master); s.start(t);
  }
  const sfx = {
    hook: () => { tone(1400, 0.08, 'square', 0.08); tone(900, 0.12, 'triangle', 0.15); },
    unhook: () => { noise(0.25, 0.12, 2400); tone(500, 0.18, 'sine', 0.06, 900); },
    crash: () => { noise(0.5, 0.45, 700); tone(120, 0.4, 'sawtooth', 0.12, 50); },
    cp: () => { tone(660, 0.12, 'triangle', 0.15); setTimeout(() => tone(990, 0.18, 'triangle', 0.15), 110); },
    star: () => { [880, 1175, 1568].forEach((f, i) => setTimeout(() => tone(f, 0.2, 'triangle', 0.16), i * 90)); },
    snap: () => { noise(0.18, 0.4, 3000); tone(220, 0.25, 'square', 0.08, 90); },
    win: () => { [523, 659, 784, 1047].forEach((f, i) => setTimeout(() => tone(f, 0.28, 'triangle', 0.18), i * 130)); },
  };
  function engineSound(S, gas) {
    if (!AC) return;
    if (!eng) { try { const o = AC.createOscillator(), f = AC.createBiquadFilter(), g = AC.createGain(); o.type = 'sawtooth'; f.type = 'lowpass'; f.frequency.value = 420; g.gain.value = 0; o.connect(f); f.connect(g); g.connect(master); o.start(); eng = { o, g }; } catch (e) { return; } }
    const rpm = S && S.wheels.length ? Math.abs(S.wheels[0].w) : 0, on = !!S && mode === 'play' && S.state === 'play' && !muted, t = AC.currentTime;
    eng.o.frequency.setTargetAtTime(48 + rpm * 3.2 + (gas ? 14 : 0), t, 0.06);
    eng.g.gain.setTargetAtTime(on ? 0.04 + (gas ? 0.05 : 0) : 0, t, 0.08);
  }

  // ---------- состояние ----------
  let LANG = RU ? 1 : 0; const NL = H.levels.length;
  function setLang(ru) { RU = !!ru; T = RU ? TRU : TEN; LANG = RU ? 1 : 0; }
  // гараж: монеты дают за финиш и звёзды; на них — колёса, цвета, грузовик и прокачка. Звёзды не тратятся: за них открывается джип
  // три последних — дорогие, с блеском: хром, золото и «радуга» (переливается на ходу)
  const PAINT = [['#ff5a36', '#c63b1f'], ['#2f7df6', '#1c55b8'], ['#3fbf5a', '#2a8a3f'], ['#ffc928', '#d99a00'], ['#ff6fb1', '#d1437f'], ['#3a4047', '#22272c'], ['#bcc9d0', '#8496a0', 'chrome'], ['#f5b400', '#b97c00', 'gold'], ['#b36bff', '#7a3fd0', 'rainbow']];
  const SHOP = {
    truck: [{ n: ['Pickup', 'Пикап'] }, { n: ['Jeep', 'Джип'], stars: 12 }, { n: ['Big Rig', 'Тягач'], cost: 900 }],
    wheels: [{ n: ['Classic', 'Обычные'] }, { n: ['Monster', 'Монстр'], cost: 200 }, { n: ['Gold', 'Золотые'], cost: 350 }, { n: ['Spikes', 'Шипы'], cost: 500 }],
    color: [0, 80, 80, 80, 120, 150, 400, 600, 900].map((cost) => ({ cost })),
  };
  const TABS = ['truck', 'wheels', 'color', 'up'], OWN = { truck: 'own', wheels: 'ownW', color: 'ownC' }, UPC = [100, 150, 220, 300, 400];
  let save = { stars: [], best: [], duo: false, coins: 0, own: [0], ownW: [0], ownC: [0], truck: 0, wheels: 0, color: 0, up: { eng: 0, winch: 0 } };
  const SAVE0 = JSON.stringify(save);
  function adopt(q) { // принять сохранение (из браузера или из облака площадки), поправив старые и битые поля
    const s2 = JSON.parse(SAVE0);
    if (q && Array.isArray(q.stars)) { const old = q.coins === undefined; Object.assign(s2, q); if (old) s2.coins = s2.stars.reduce((a, n) => a + (n ? 20 + 40 * n : 0), 0); } // прошлые звёзды — в монеты
    s2.up = Object.assign({ eng: 0, winch: 0 }, s2.up); s2.coins = Math.max(0, s2.coins | 0);
    for (const k in OWN) { if (!Array.isArray(s2[OWN[k]]) || !s2[OWN[k]].includes(0)) s2[OWN[k]] = [0]; if (!s2[OWN[k]].includes(s2[k]) || !SHOP[k][s2[k]]) s2[k] = 0; }
    save = s2;
  }
  try { adopt(JSON.parse(localStorage.getItem('hooktruck_v1') || 'null')); } catch (e) { adopt(null); }
  const store = () => {
    save.ts = Date.now(); const js = JSON.stringify(save);
    try { localStorage.setItem('hooktruck_v1', js); } catch (e) { /* без сохранения */ }
    if (PG.on) { try { window.bridge.storage.set('hooktruck_v1', js).catch(() => {}); } catch (e) { /* */ } } // облако площадки (YouTube и др.)
  };
  const starsTotal = () => save.stars.reduce((a, n) => a + (n || 0), 0);
  const curLook = () => ({ truck: save.truck, wheels: save.wheels, color: save.color });
  function applyLook(l) { TR.main = PAINT[l.color][0]; TR.dark = PAINT[l.color][1]; if (use3d) R3.setLook({ truck: l.truck, wheels: l.wheels, paint: PAINT[l.color] }); }
  let gar = null, gcam = null;
  let lvl = 0, res = null; const dbg = { freeze: false, clean: false };
  let hangT = 0;
  // управление: 'manual' — газ, тормоз и крюк (по умолчанию: Михаилу так интереснее); 'auto' — газ сам, палец только на крюке; вдвоём — всегда ручное
  let ctl = save.ctl === 'auto' ? 'auto' : 'manual', wait = false, ts = 1, tut = null, hookT0 = 0;
  const isAuto = () => ctl === 'auto' && !duo;
  const SER = [{ n: ['Meadow', 'Луг'], need: 0 }, { n: ['Canyon', 'Каньон'], need: 16 }], NS = Math.ceil(NL / 12);
  let ser = 0;
  const serOpen = (k) => !!window.HOOK_TEST || starsTotal() >= (SER[k] ? SER[k].need : 999);
  const canNext = () => lvl < NL - 1 && serOpen(H.levels[lvl + 1].ser);
  function firstOpen() { for (let i = 0; i < NL; i++) if (!save.stars[i] && serOpen(H.levels[i].ser)) return i; return 0; }
  ser = H.levels[firstOpen()].ser;
  let mode = 'menu', duo = !!save.duo, S = null, acc = 0, last = performance.now(), Z = 0.6, camX = 0, camY = 0, toasts = [], parts = [], shake = 0, realT = 0, hintShown = {};
  const keys = {};
  addEventListener('keydown', (e) => { keys[e.code] = true; if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault(); audio(); if (e.code === 'Enter' && mode === 'win' && !PG.pend) pgInter(() => { if (canNext()) startGame(duo, lvl + 1); else mode = 'menu'; }); else if (e.code === 'KeyR' && mode === 'play') restart(); else if (e.code === 'Escape' && mode === 'garage') garClick('g:back'); });
  addEventListener('keyup', (e) => { keys[e.code] = false; });
  addEventListener('blur', () => { for (const k in keys) keys[k] = false; ptrs.clear(); });

  // кнопки на экране (и для мыши, и для пальцев)
  const ptrs = new Map(); // pointerId -> {x,y,btn}
  let buttons = [];
  function layout() {
    const s = Math.min(W, H2), b = clamp(s * 0.2, 74, 120), m = clamp(s * 0.04, 14, 30), y = H2 - b - m - (W < H2 ? 10 : 0);
    const gw = b * 1.15;
    buttons = (isAuto() ? [] : [ // «один палец»: кнопок нет, крюк — касание в любом месте
      { id: 'gas', x: W - gw - m, y: y - b * 0.15, w: gw, h: b * 1.15 },
      { id: 'brake', x: W - gw - m - b - m * 0.6, y: y + b * 0.05, w: b * 0.95, h: b * 0.95 },
      { id: 'hook', x: m, y: y - b * 0.35, w: b * 1.35, h: b * 1.35 },
    ]).concat(duo ? [{ id: 'pull', x: m + b * 0.25, y: y - b * 0.35 - b * 0.75 - m * 0.6, w: b * 0.85, h: b * 0.75 }] : []).concat([ // вдвоём: «тяни» над крюком — второй игрок сам тянет лебёдку
      { id: 'restart', x: W - 58, y: 12, w: 46, h: 46, ui: 1 },
      { id: 'menu', x: W - 112, y: 12, w: 46, h: 46, ui: 1 },
      { id: 'mute', x: W - 166, y: 12, w: 46, h: 46, ui: 1 },
    ]);
  }
  const hit = (x, y) => buttons.find((b) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
  const held = (id) => { for (const p of ptrs.values()) if (p.btn === id) return true; return false; };
  cv.addEventListener('pointerdown', (e) => {
    audio(); try { cv.setPointerCapture(e.pointerId); } catch (er) { /* синтетические касания */ }
    const x = e.clientX, y = e.clientY;
    if (PG.pend) return; // идёт реклама
    if (mode !== 'play') { menuClick(x, y); return; }
    const b = hit(x, y);
    if (b && b.ui) { if (b.id === 'restart') restart(); else if (b.id === 'menu') { mode = 'menu'; pgMsg('gameplay_stopped'); } else if (b.id === 'mute') muted = !muted; return; }
    ptrs.set(e.pointerId, { x, y, btn: b ? b.id : isAuto() || (e.pointerType !== 'mouse' && x < W / 2) ? 'hook' : null });
  });
  const up = (e) => ptrs.delete(e.pointerId);
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  cv.addEventListener('pointermove', (e) => { const p = ptrs.get(e.pointerId); if (!p || e.pointerType === 'mouse') return; const b = hit(e.clientX, e.clientY); if (b && !b.ui && b.id !== p.btn && (p.btn === 'gas' || p.btn === 'brake') && (b.id === 'gas' || b.id === 'brake')) p.btn = b.id; });

  function input() {
    const k = keys;
    const gas = !!(k.ArrowRight || k.ArrowUp) || held('gas');
    const brake = !!(k.ArrowLeft || k.ArrowDown) || held('brake');
    const hook = !!(k.Space || k.KeyW || k.ShiftLeft || (isAuto() && k.ArrowUp)) || held('hook');
    return isAuto() ? { gas: true, brake: false, hook, pull: false } : { gas, brake, hook, pull: duo && (!!k.KeyS || held('pull')) };
  }

  function startGame(d, li) { pgMsg('gameplay_started'); pgMsg('level_started', { level: (li !== undefined ? li : lvl) + 1 }); duo = d; if (li !== undefined) lvl = li; ser = H.levels[lvl].ser; S = H.create(lvl, { up: save.up }); mode = 'play'; acc = 0; toasts = []; parts = []; hintShown = {}; wait = isAuto(); ts = 1; tut = null; camX = S.truck.x + 300; camY = S.truck.y; ptrs.clear(); }
  function restart() { startGame(duo, lvl); }
  function finish() {
    const l = H.levels[lvl], got = !!S.L.star.got, fast = S.wonAt <= l.par, n = 1 + (got ? 1 : 0) + (fast ? 1 : 0);
    // монеты: 20 за финиш, по 10 за каждую звезду заезда и по 30 за каждую звезду, взятую на этом уровне впервые
    const fresh = Math.max(0, n - (save.stars[lvl] || 0)), earn = 20 + 10 * n + 30 * fresh;
    res = { n, got, fast, t: S.wonAt, tries: S.attempts, par: l.par, newBest: !(save.best[lvl] <= S.wonAt), earn };
    save.coins += earn; (save.tut = save.tut || [])[lvl] = 1; pgMsg('level_completed', { level: lvl + 1 }); pgMsg('gameplay_stopped');
    save.stars[lvl] = Math.max(save.stars[lvl] || 0, n); if (!(save.best[lvl] <= S.wonAt)) save.best[lvl] = +S.wonAt.toFixed(2); store();
  }

  // ---------- меню ----------
  let menuBtns = [];
  function menuClick(x, y) {
    const b = menuBtns.find((q) => x >= q.x && x <= q.x + q.w && y >= q.y && y <= q.y + q.h); if (!b) return;
    if (b.id.slice(0, 2) === 'g:') garClick(b.id);
    else if (b.id === 'garage') openGarage();
    else if (b.id.slice(0, 2) === 'm:') { const m = b.id.slice(2); duo = m === 'duo'; if (!duo) ctl = m; save.duo = duo; save.ctl = ctl; store(); }
    else if (b.id[0] === 'L') { const li = +b.id.slice(1); pgInter(() => startGame(duo, li), li); }
    else if (b.id === 'play') { const li = firstOpen(); pgInter(() => startGame(duo, li), li); }
    else if (b.id === 's:prev' || b.id === 's:next') { ser = clamp(ser + (b.id === 's:next' ? 1 : -1), 0, NS - 1); tone(700, 0.05, 'triangle', 0.08); }
    else if (b.id === 'x2') pgRewarded('double_coins', (ok) => { if (ok && res && !res.x2) { res.x2 = true; save.coins += res.earn; store(); sfx.star(); } else if (!ok && res) { res.noad = true; toasts.push({ t: 0, text: T.noad, col: '#ffcc80' }); } });
    else if (b.id === 'again') pgInter(() => restart()); else if (b.id === 'next') pgInter(() => { if (canNext()) startGame(duo, lvl + 1); else mode = 'menu'; }); else if (b.id === 'menu') { if (mode === 'win') pgInter(() => { mode = 'menu'; }); else mode = 'menu'; }
  }

  // ---------- обучение рукой ----------
  // Пока уровень 1 или 2 не пройден, игра показывает рукой «держи» и «отпусти» (моменты посчитал решатель, levels.js GUIDE).
  // На первом уровне она ещё и ждёт: замирает у ямы, пока не нажмёшь, и в точке отпускания, пока не отпустишь.
  // Возвращает скорость времени (1 — обычная, 0 — пауза); inp.hook гасит, если цепляться ещё рано.
  function tutor(inp) {
    tut = null;
    const G = H.levels[lvl].guide; if (!G || (save.tut && save.tut[lvl]) || S.state !== 'play') return 1; // обучение — пока уровень не пройден с ним хоть раз (у старых сохранений покажется заново)
    const tr = S.truck, slow = lvl === 0 && !save.up.eng && !save.up.winch;
    if (!isAuto() && !inp.gas && S.grounded && !S.rope && Math.abs(tr.vx) < 140) { tut = 'gas'; return 1; } // ручное управление: стоит — покажи, где газ
    if (!S.rope) {
      const a = S.target, g = a && G[a.i]; if (!g) return 1;
      if (g.climb) { if (S.wallTouch || tr.x > a.x - 300) tut = 'hold'; return 1; }
      if (tr.x > a.x + 40) return 1; // кольцо уже позади — после отпускания «держи» не показываем
      if (tr.x > a.x - g.att - (slow ? 170 : 340)) tut = 'hold'; // рука появляется заранее: нажать можно сразу, крюк сам выстрелит у края
      if (tr.x <= a.x - g.att) { const stop = slow && !inp.hook && tr.x > a.x - g.att - 60; inp.hook = false; return stop ? 0 : 1; } // цепляться ещё рано: учим делать это у края ямы
      return slow && !inp.hook ? 0 : 1;
    }
    const a = S.ropeA, g = G[a.i]; if (!g) return 1;
    if (g.climb) { if (S.grounded && tr.y < a.y + 300 && (tr.x > a.x - 80 || S.rope.len <= 160)) tut = 'rel'; return 1; }
    const rel = tr.x - a.x;
    if (tr.vx > 0 && rel >= g.lo && rel <= g.hi) { tut = 'rel'; if (!inp.hook) return 1; if (!slow) return 0.5; return a.i === 0 && rel >= (g.lo + g.hi) / 2 - 40 ? 0 : 0.22; } // первое кольцо — пауза в середине окна; дальше — сильное замедление, чтобы успеть отпустить
    if (rel < g.lo) tut = 'hold';
    return 1;
  }
  // рука-указатель: кончик пальца в точке (x, y); lift — насколько палец поднят над экраном
  function hand(x, y, sc, lift) {
    ctx.save(); ctx.translate(x, y - lift); ctx.scale(sc, sc); ctx.rotate(-0.22);
    const parts = [[-11, 0, 22, 66, 11], [9, 34, 17, 40, 8.5], [24, 38, 17, 38, 8.5], [39, 44, 16, 34, 8], [-13, 50, 68, 54, 18]];
    ctx.lineJoin = 'round'; ctx.strokeStyle = '#263238'; ctx.lineWidth = 7;
    for (const q of parts) { rr(q[0], q[1], q[2], q[3], q[4]); ctx.stroke(); }
    ctx.save(); ctx.translate(-22, 62); ctx.rotate(-0.7); rr(-9, -4, 18, 40, 9); ctx.stroke(); ctx.fillStyle = '#fff'; ctx.fill(); ctx.restore();
    ctx.fillStyle = '#fff'; for (const q of parts) { rr(q[0], q[1], q[2], q[3], q[4]); ctx.fill(); }
    ctx.restore();
  }
  // подсказка: рука и короткое слово. kind: 'go' — нажми, 'hold' — держи, 'rel' — отпусти
  function prompt(kind) {
    const port = W < H2, hk = !isAuto() && buttons.find((b) => b.id === (kind === 'gas' ? 'gas' : 'hook')), big = Math.min(1.25, Math.max(0.8, Math.min(W, H2) / 420));
    const x = hk ? hk.x + hk.w * 0.55 : W / 2, y = hk ? hk.y + hk.h * 0.45 : H2 * (port ? 0.85 : 0.76), ph = (realT * 1.6) % 1;
    const col = kind === 'rel' || kind === 'gas' ? '#43a047' : '#ff9800', keys2 = !isAuto() && !matchMedia('(pointer: coarse)').matches && !ptrs.size;
    const txt = kind === 'go' ? T.go : keys2 ? (kind === 'gas' ? '→  ' + T.gasW : kind === 'hold' ? T.space + ' — ' + T.hold : T.rel) : kind === 'hold' ? T.hold : kind === 'gas' ? T.gasW : T.rel;
    if (keys2) { // клавиатура: рука не нужна, пишем клавишу
      const fs = 34, pul = 1 + 0.05 * Math.sin(realT * 10); ctx.save(); ctx.translate(W / 2, H2 * 0.8); ctx.scale(pul, pul); ctx.font = `900 ${fs}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
      ctx.lineWidth = 8; ctx.strokeStyle = 'rgba(0,0,0,0.55)'; ctx.strokeText(txt, 0, 0); ctx.fillStyle = col; ctx.fillText(txt, 0, 0); ctx.restore(); return;
    }
    let lift = 0;
    if (kind === 'go') lift = 26 * Math.abs(Math.sin(realT * 4.2)); else if (kind === 'rel') lift = 18 + 30 * ((realT * 1.8) % 1);
    { // круги от нажатия (для «отпусти» — расходятся шире: палец ушёл)
      for (let i = 0; i < 2; i++) { const q = (ph + i * 0.5) % 1; ctx.globalAlpha = (1 - q) * (kind === 'go' && lift > 10 ? 0.15 : 0.7); ctx.strokeStyle = col; ctx.lineWidth = 5 * big; ctx.beginPath(); ctx.arc(x, y, (16 + q * (kind === 'rel' ? 52 : 34)) * big, 0, 7); ctx.stroke(); }
      ctx.globalAlpha = 1;
    }
    hand(x, y, big, lift * big);
    const fs = Math.round((kind === 'go' ? 26 : 40) * big), ty = y - (kind === 'go' ? 62 : 74) * big, pul = kind === 'go' ? 1 : 1 + 0.06 * Math.sin(realT * 10), tx = clamp(x, 110 * big, W - 110 * big);
    ctx.save(); ctx.translate(tx, ty); ctx.scale(pul, pul); ctx.font = `900 ${fs}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
    ctx.lineWidth = fs * 0.24; ctx.strokeStyle = 'rgba(0,0,0,0.55)'; ctx.strokeText(txt, 0, 0); ctx.fillStyle = kind === 'go' ? '#fff' : col; ctx.fillText(txt, 0, 0); ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(255,255,255,0.9)'; if (kind !== 'go') ctx.strokeText(txt, 0, 0);
    ctx.restore();
    if ((kind === 'go' || kind === 'hold') && isAuto() && !matchMedia('(pointer: coarse)').matches) { ctx.font = '800 16px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineWidth = 5; ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.strokeText(T.keyHint, tx, ty + fs * 0.85); ctx.fillStyle = '#fff'; ctx.fillText(T.keyHint, tx, ty + fs * 0.85); }
  }

  // ---------- гараж ----------
  // раскладка: на телефоне панель снизу (ровно под два ряда плиток), на широком экране — справа
  // гараж «столбиком» (грузовик сверху, панель снизу) — на телефоне стоя и в квадратном или узком окне; «рядом» — только на широком экране
  function garPort() { return W < H2 * 1.15 || W < 560; }
  function garLayout() {
    const port = garPort(), px = port ? 8 : Math.round(W * 0.5), pw = port ? W - 16 : W - px - 10;
    const ph = port ? Math.min(Math.round(H2 * 0.56), 134 + 2 * Math.min(124, (pw - 20) / 2, (pw - 20) / 3 + 6)) : H2 - 74, py = H2 - 8 - ph;
    return { port, px, py, pw, ph };
  }
  function openGarage() { gar = { tab: gar ? gar.tab : 0, pick: curLook(), deny: -9 }; lvl = 0; S = H.create(0, { up: save.up }); acc = 0; mode = 'garage'; toasts = []; ptrs.clear(); }
  function garClick(id) {
    const a = id.split(':'), kind = TABS[gar.tab], no = () => { gar.deny = realT; gar.denyK = a[1] === 'up' ? a[2] : ''; tone(160, 0.18, 'square', 0.08); };
    if (a[1] === 'back') { applyLook(curLook()); mode = 'menu'; tone(500, 0.06, 'triangle', 0.1); }
    else if (a[1] === 'tab') { if (kind !== 'up') gar.pick[kind] = save[kind]; gar.tab = +a[2]; applyLook(gar.pick); tone(700, 0.05, 'triangle', 0.08); }
    else if (a[1] === 'item') { const i = +a[2]; gar.pick[kind] = i; if (save[OWN[kind]].includes(i)) { save[kind] = i; store(); } applyLook(gar.pick); tone(880, 0.06, 'triangle', 0.1); } // тап — примерка; своё сразу надевается
    else if (a[1] === 'act') {
      const i = gar.pick[kind], it = SHOP[kind][i];
      if (it.stars ? starsTotal() < it.stars : save.coins < it.cost) return no();
      if (!it.stars) save.coins -= it.cost;
      save[OWN[kind]].push(i); save[kind] = i; store(); sfx.star();
    }
    else if (a[1] === 'up') { const lv = save.up[a[2]]; if (lv >= UPC.length) return; if (save.coins < UPC[lv]) return no(); save.coins -= UPC[lv]; save.up[a[2]] = lv + 1; store(); sfx.cp(); }
    else if (a[1] === 'test') { save.coins += 500; store(); sfx.cp(); }
    // монеты за ролик: по желанию игрока, не чаще раза в три минуты; всё в гараже покупается и без роликов
    else if (a[1] === 'ad') pgRewarded('garage_coins', (ok) => { if (ok) { save.coins += 100; PG.lastFree = pgNow(); store(); sfx.star(); } else PG.lastFree = pgNow() - 120; });
  }

  // ---------- камера ----------
  const oy = () => (mode !== 'garage' && W < H2 && isAuto() ? 0.13 : 0.05); // насколько ниже середины экрана стоит грузовик
  const sx = (x) => (x - camX) * Z + W * 0.42, sy = (y) => (y - camY) * Z + H2 * (0.5 + oy());
  function camera(dt) {
    const port = W < H2;
    gcam = null;
    if (mode === 'garage') { // грузовик крупно: на телефоне сверху, на широком экране слева; панель гаража — рядом
      const g = garLayout(), gp = g.port, free = g.py - 60; // место над панелью
      Z = gp ? Math.min(W / 430, free / 330) : Math.min((W * 0.5) / 430, H2 / 400); gcam = { px: gp ? W / 2 : W * 0.25, py: gp ? 60 + free * 0.5 : H2 * 0.56, yaw: 0.55 + 0.3 * Math.sin(realT * 0.5), tilt: 0.24 };
      camX = S.truck.x - (gcam.px - W * 0.42) / Z; camY = S.truck.y - 30 - (gcam.py - H2 * 0.55) / Z; return;
    }
    const zt = dbg.zoom || (port ? W / 1050 : Math.min(W / 1650, H2 / 980));
    Z += (zt - Z) * Math.min(1, dt * 3);
    const T = S.truck, look = clamp(T.vx * 0.35, -250, port ? Math.min(420, (0.2 * W) / Z) : 420); // в портрете грузовик не уезжает к самому левому краю
    if (dbg.zoom) { camX = T.x + dbg.cx; camY = (T.y + (S.rope ? S.rope.py : T.y - 300)) / 2 + dbg.cy; return; }
    if (S.state === 'dead') return;
    camX += (T.x + look - camX) * Math.min(1, dt * 4);
    let ty = T.y - 60; if (S.rope) ty = (T.y + S.rope.py) / 2 + 40;
    camY += (ty - camY) * Math.min(1, dt * 3.2);
  }

  // ---------- рисование мира ----------
  function drawSky() {
    const g = ctx.createLinearGradient(0, 0, 0, H2); g.addColorStop(0, '#5ec2ff'); g.addColorStop(0.7, '#c8eeff'); g.addColorStop(1, '#e8f8ff');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H2);
    ctx.fillStyle = 'rgba(255,245,180,0.9)'; ctx.beginPath(); ctx.arc(W * 0.82, H2 * 0.16, 50, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(255,245,180,0.25)'; ctx.beginPath(); ctx.arc(W * 0.82, H2 * 0.16, 84, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    for (let i = 0; i < 6; i++) {
      const cx = ((i * 520 - camX * 0.12 * Z) % (W + 600) + W + 600) % (W + 600) - 300, cy = H2 * (0.1 + (i % 3) * 0.08);
      for (const [dx, dy, r] of [[0, 0, 34], [36, -14, 42], [76, 0, 32], [38, 10, 30]]) { ctx.beginPath(); ctx.arc(cx + dx, cy + dy, r, 0, 7); ctx.fill(); }
    }
    for (const [k, col, base, amp] of [[0.15, '#9fd3c7', 0.62, 90], [0.3, '#7cc4a4', 0.72, 70]]) {
      ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(0, H2);
      for (let x = 0; x <= W + 20; x += 20) { const wx = x / Z + camX * k; ctx.lineTo(x, H2 * base - amp * (0.6 * Math.sin(wx * 0.0021) + 0.4 * Math.sin(wx * 0.0057 + 1.3)) + (camY - 500) * k * Z * 0.3); }
      ctx.lineTo(W, H2); ctx.closePath(); ctx.fill();
    }
  }
  function drawGround() {
    const L = S.L;
    { const y0 = sy(L.maxY + 300); if (y0 < H2) { const g = ctx.createLinearGradient(0, y0, 0, y0 + 500 * Z); g.addColorStop(0, 'rgba(40,24,16,0)'); g.addColorStop(1, 'rgba(40,24,16,0.92)'); ctx.fillStyle = g; ctx.fillRect(0, y0, W, H2 - y0); } }
    const vx0 = camX - (W * 0.42) / Z - 50, vx1 = camX + (W * 0.6) / Z + 50, bottom = H2 + 50;
    for (const poly of L.polys) {
      if (poly[poly.length - 1][0] < vx0 || poly[0][0] > vx1) continue;
      ctx.beginPath(); ctx.moveTo(sx(poly[0][0]), bottom);
      for (const p of poly) ctx.lineTo(sx(p[0]), sy(p[1]));
      ctx.lineTo(sx(poly[poly.length - 1][0]), bottom); ctx.closePath();
      const g = ctx.createLinearGradient(0, sy(L.minY), 0, sy(L.maxY + 500)); g.addColorStop(0, '#b07444'); g.addColorStop(1, '#6d4127');
      ctx.fillStyle = g; ctx.fill();
      ctx.save(); ctx.clip(); ctx.strokeStyle = 'rgba(0,0,0,0.08)'; ctx.lineWidth = 10 * Z;
      for (let k = 1; k < 7; k++) { ctx.beginPath(); for (let i = 0; i < poly.length; i++) { const p = poly[i]; const X = sx(p[0]), Y = sy(p[1] + k * 70 + 12 * Math.sin(p[0] * 0.01 + k)); if (i) ctx.lineTo(X, Y); else ctx.moveTo(X, Y); } ctx.stroke(); }
      ctx.restore();
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      ctx.strokeStyle = '#4caf50'; ctx.lineWidth = 22 * Z; ctx.beginPath(); poly.forEach((p, i) => (i ? ctx.lineTo(sx(p[0]), sy(p[1]) + 6 * Z) : ctx.moveTo(sx(p[0]), sy(p[1]) + 6 * Z))); ctx.stroke();
      ctx.strokeStyle = '#8bc34a'; ctx.lineWidth = 8 * Z; ctx.beginPath(); poly.forEach((p, i) => (i ? ctx.lineTo(sx(p[0]), sy(p[1])) : ctx.moveTo(sx(p[0]), sy(p[1])))); ctx.stroke();
    }
    // потолок пещеры: скала сверху с сосульками-сталактитами
    for (const c of L.ceils) {
      if (c.x1 < vx0 || c.x0 > vx1) continue;
      const g = ctx.createLinearGradient(0, sy(c.y - 600), 0, sy(c.y)); g.addColorStop(0, '#4e342e'); g.addColorStop(1, '#8d6e63');
      ctx.fillStyle = g; ctx.fillRect(sx(c.x0), -10, (c.x1 - c.x0) * Z, sy(c.y) + 10);
      ctx.fillStyle = '#795548';
      for (let x = c.x0 + 30; x < c.x1 - 30; x += 90) { const h = 26 + 22 * Math.abs(Math.sin(x * 0.013)); ctx.beginPath(); ctx.moveTo(sx(x - 18), sy(c.y)); ctx.lineTo(sx(x), sy(c.y + h)); ctx.lineTo(sx(x + 18), sy(c.y)); ctx.closePath(); ctx.fill(); }
      ctx.strokeStyle = '#3e2723'; ctx.lineWidth = 6 * Z; ctx.beginPath(); ctx.moveTo(sx(c.x0), sy(c.y)); ctx.lineTo(sx(c.x1), sy(c.y)); ctx.stroke();
    }
    for (const z of L.springs || []) { if (z.x1 < vx0 || z.x0 > vx1) continue; const gy = S.groundAt((z.x0 + z.x1) / 2); ctx.fillStyle = '#d81b60'; rr(sx(z.x0), sy(gy - 12), (z.x1 - z.x0) * Z, 12 * Z, 4 * Z); ctx.fill(); } // батуты
    // ускорители: бегущие оранжевые стрелки
    for (const z of L.boosts) {
      if (z.x1 < vx0 || z.x0 > vx1) continue;
      const ph = (realT * 2) % 1;
      for (let x = z.x0; x < z.x1 - 30; x += 60) {
        const gy = S.groundAt(x + 20), k = ((x - z.x0) / 60 + ph) % 3 < 1 ? 1 : 0.55;
        ctx.fillStyle = `rgba(255,${k > 0.9 ? 160 : 112},0,${k})`; ctx.beginPath();
        ctx.moveTo(sx(x), sy(gy - 4)); ctx.lineTo(sx(x + 22), sy(gy - 4)); ctx.lineTo(sx(x + 46), sy(gy - 22)); ctx.lineTo(sx(x + 22), sy(gy - 40)); ctx.lineTo(sx(x), sy(gy - 40)); ctx.lineTo(sx(x + 24), sy(gy - 22)); ctx.closePath(); ctx.fill();
      }
    }
  }
  // пропасть: книзу темнеет до черноты — упавший грузовик исчезает в темноте
  function drawPits() {
    for (const z of S.L.pits) {
      const X0 = sx(z.x0), X1 = sx(z.x1); if (X1 < -20 || X0 > W + 20) continue;
      const y0 = sy(z.y + 30), y1 = sy(z.y + 420);
      const g = ctx.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, 'rgba(20,12,8,0)'); g.addColorStop(0.55, 'rgba(20,12,8,0.75)'); g.addColorStop(1, 'rgba(10,6,4,1)');
      ctx.fillStyle = g; ctx.fillRect(X0, y0, X1 - X0, y1 - y0); ctx.fillStyle = 'rgb(10,6,4)'; if (y1 < H2) ctx.fillRect(X0, y1, X1 - X0, H2 - y1 + 10);
    }
  }
  function flagPole(x, gy, col, checker) {
    ctx.fillStyle = '#eceff1'; ctx.fillRect(sx(x) - 4 * Z, sy(gy - 230), 8 * Z, 230 * Z);
    if (!checker) { ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(sx(x) + 4 * Z, sy(gy - 228)); ctx.lineTo(sx(x + 80), sy(gy - 205)); ctx.lineTo(sx(x) + 4 * Z, sy(gy - 182)); ctx.closePath(); ctx.fill(); }
  }
  function star5(x, y, r, col) {
    ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, q = i % 2 ? r * 0.45 : r; ctx.lineTo(x + Math.cos(a) * q, y + Math.sin(a) * q); } ctx.closePath();
    ctx.fillStyle = col; ctx.fill(); ctx.lineWidth = Math.max(2, r * 0.12); ctx.strokeStyle = '#f57f17'; ctx.stroke();
  }
  function drawObjects() {
    const L = S.L;
    for (const c of L.cps) flagPole(c.x, S.groundAt(c.x), S.cp && S.cp.x >= c.x ? '#00e676' : '#b0bec5', false);
    const fy = S.groundAt(L.fin);
    flagPole(L.fin - 40, fy, '#fff', true); flagPole(L.fin + 260, S.groundAt(L.fin + 260), '#fff', true);
    ctx.save(); ctx.translate(sx(L.fin - 40), sy(fy - 230)); ctx.scale(Z, Z);
    for (let i = 0; i < 15; i++) for (let j = 0; j < 2; j++) { ctx.fillStyle = (i + j) % 2 ? '#212121' : '#fafafa'; ctx.fillRect(i * 20, j * 20, 20, 20); }
    ctx.restore();
    const st = L.star;
    if (st && !st.got) { const bob = Math.sin(realT * 3) * 8; ctx.save(); ctx.translate(sx(st.x), sy(st.y + bob)); ctx.rotate(Math.sin(realT * 2) * 0.15); star5(0, 0, 46 * Z, '#ffd54f'); ctx.restore(); }
    // кольца для крюка
    for (const a of L.anchors) {
      if (a.broken) continue;
      const X = sx(a.x), Y = sy(a.y), r = 30 * Z, tgt = S.target === a, on = S.ropeA === a;
      if (a.mv) { // путь ездящего кольца
        ctx.setLineDash([6 * Z, 10 * Z]); ctx.strokeStyle = 'rgba(255,255,255,0.6)'; ctx.lineWidth = 4 * Z; ctx.beginPath();
        ctx.moveTo(sx(a.x0 - (a.mv.dx || 0)), sy(a.y0 - (a.mv.dy || 0))); ctx.lineTo(sx(a.x0 + (a.mv.dx || 0)), sy(a.y0 + (a.mv.dy || 0))); ctx.stroke(); ctx.setLineDash([]);
      }
      const cave = L.ceils.find((c) => a.x > c.x0 && a.x < c.x1 && c.y < a.y);
      const sh = on && a.snap ? Math.sin(realT * 60) * 3 * Z * Math.min(1, a.hang / a.snap) : 0;
      if (cave) { ctx.strokeStyle = '#90a4ae'; ctx.lineWidth = 4 * Z; ctx.setLineDash([8 * Z, 5 * Z]); ctx.beginPath(); ctx.moveTo(X, Y - r); ctx.lineTo(X, sy(cave.y)); ctx.stroke(); ctx.setLineDash([]); }
      else {
        ctx.strokeStyle = 'rgba(55,71,79,0.55)'; ctx.lineWidth = 3 * Z; ctx.beginPath(); ctx.moveTo(X, Y - r); ctx.lineTo(X, Y - 300 * Z); ctx.stroke();
        ctx.fillStyle = '#ffffff'; for (const [dx, dy, rr2] of [[-40, -300, 34], [0, -318, 44], [42, -300, 34]]) { ctx.beginPath(); ctx.arc(X + dx * Z, Y + dy * Z, rr2 * Z, 0, 7); ctx.fill(); }
      }
      if (tgt) { const p = 1 + 0.18 * Math.sin(realT * 10); ctx.strokeStyle = 'rgba(255,235,59,0.9)'; ctx.lineWidth = 6 * Z; ctx.beginPath(); ctx.arc(X, Y, r * 1.9 * p, 0, 7); ctx.stroke(); }
      ctx.save(); ctx.translate(X + sh, Y);
      ctx.lineWidth = 12 * Z; ctx.strokeStyle = '#263238'; ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.stroke();
      ctx.lineWidth = 8 * Z; ctx.strokeStyle = a.snap ? (on ? '#ff5252' : '#ff8a65') : on ? '#ff7043' : tgt ? '#ffeb3b' : '#ffc107'; ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 3 * Z; ctx.beginPath(); ctx.arc(0, 0, r, -2.6, -1.6); ctx.stroke();
      if (a.snap) { // трещины
        ctx.strokeStyle = '#3e2723'; ctx.lineWidth = 3 * Z; ctx.beginPath();
        ctx.moveTo(r * 0.75, -r * 0.65); ctx.lineTo(r * 1.0, -r * 0.2); ctx.lineTo(r * 0.8, r * 0.1);
        ctx.moveTo(-r * 0.9, r * 0.4); ctx.lineTo(-r * 0.6, r * 0.75); ctx.stroke();
      }
      ctx.restore();
    }
    // куда зацепится крюк
    if (S.target && !S.rope && S.state === 'play') {
      const [mx, my] = S.mast(); ctx.setLineDash([10 * Z, 12 * Z]); ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 4 * Z;
      ctx.beginPath(); ctx.moveTo(sx(mx), sy(my)); ctx.lineTo(sx(S.target.x), sy(S.target.y)); ctx.stroke(); ctx.setLineDash([]);
    }
  }
  function drawRope() {
    if (!S.rope) return;
    const [mx, my] = S.mast(), ax = S.rope.px, ay = S.rope.py, d = Math.hypot(ax - mx, ay - my), sag = Math.max(0, S.rope.len - d) * 0.6;
    ctx.lineCap = 'round';
    for (const [w, c] of [[9, '#3e2723'], [4, '#a1887f']]) {
      ctx.strokeStyle = c; ctx.lineWidth = w * Z; ctx.beginPath(); ctx.moveTo(sx(mx), sy(my));
      ctx.quadraticCurveTo(sx((mx + ax) / 2), sy((my + ay) / 2 + sag), sx(ax), sy(ay)); ctx.stroke();
    }
    // крюк на кольце
    ctx.fillStyle = '#90a4ae'; ctx.beginPath(); ctx.arc(sx(ax), sy(ay + 18), 9 * Z, 0, 7); ctx.fill();
  }

  // ---------- грузовик ----------
  const TR = { main: '#ff5a36', dark: '#c63b1f', frame: '#37474f' };
  function part(fn) { const t = S.truck; ctx.save(); ctx.translate(sx(t.x), sy(t.y)); ctx.rotate(t.a); ctx.scale(Z, Z); fn(); ctx.restore(); }
  function drawWheel(w) {
    ctx.save(); ctx.translate(sx(w.x), sy(w.y)); ctx.rotate(w.a); ctx.scale(Z, Z);
    ctx.fillStyle = '#212121'; ctx.beginPath(); ctx.arc(0, 0, 28, 0, 7); ctx.fill();
    ctx.strokeStyle = '#424242'; ctx.lineWidth = 4; for (let i = 0; i < 12; i++) { const a = (i / 12) * 6.283; ctx.beginPath(); ctx.moveTo(Math.cos(a) * 22, Math.sin(a) * 22); ctx.lineTo(Math.cos(a) * 28, Math.sin(a) * 28); ctx.stroke(); }
    ctx.fillStyle = '#cfd8dc'; ctx.beginPath(); ctx.arc(0, 0, 15, 0, 7); ctx.fill();
    ctx.fillStyle = '#78909c'; for (let i = 0; i < 5; i++) { const a = (i / 5) * 6.283; ctx.beginPath(); ctx.arc(Math.cos(a) * 9, Math.sin(a) * 9, 2.6, 0, 7); ctx.fill(); }
    ctx.restore();
  }
  function drawTruck() {
    const t = S.truck, scared = S.state === 'dead' || (!S.grounded && Math.abs(t.vy) > 500), happy = S.state === 'win';
    part(() => {
      ctx.strokeStyle = '#607d8b'; ctx.lineWidth = 8;
      for (const w of S.wheels) { const [lx, ly] = P.local(t, w.x, w.y); ctx.beginPath(); ctx.moveTo(lx, 10); ctx.lineTo(lx, ly); ctx.stroke(); }
      ctx.fillStyle = TR.frame; rr(-114, -8, 230, 26, 8); ctx.fill();
      // кузов
      ctx.fillStyle = TR.dark; rr(-112, -44, 128, 40, 6); ctx.fill();
      if (duo) drawHelper(-52, -46, scared, happy);
      ctx.fillStyle = TR.main; rr(-114, -28, 132, 26, 6); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.25)'; ctx.fillRect(-108, -24, 120, 5);
      ctx.fillStyle = TR.dark; rr(-116, -48, 12, 48, 4); ctx.fill(); rr(8, -48, 12, 48, 4); ctx.fill();
      // кабина
      ctx.fillStyle = TR.main; ctx.beginPath(); ctx.moveTo(14, -2); ctx.lineTo(14, -70); ctx.quadraticCurveTo(14, -78, 22, -78); ctx.lineTo(64, -78); ctx.lineTo(90, -38); ctx.lineTo(112, -34); ctx.quadraticCurveTo(120, -32, 120, -24); ctx.lineTo(120, -2); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#b3e5fc'; ctx.beginPath(); ctx.moveTo(24, -70); ctx.lineTo(60, -70); ctx.lineTo(80, -40); ctx.lineTo(24, -40); ctx.closePath(); ctx.fill();
      ctx.save(); ctx.beginPath(); ctx.moveTo(24, -70); ctx.lineTo(60, -70); ctx.lineTo(80, -40); ctx.lineTo(24, -40); ctx.closePath(); ctx.clip(); drawCat(46, -50, scared, happy); ctx.restore();
      ctx.fillStyle = 'rgba(255,255,255,0.5)'; ctx.beginPath(); ctx.moveTo(56, -68); ctx.lineTo(64, -68); ctx.lineTo(74, -52); ctx.lineTo(68, -52); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#fff59d'; rr(110, -28, 10, 10, 3); ctx.fill();
      ctx.fillStyle = '#263238'; rr(100, -14, 22, 8, 3); ctx.fill();
      // лебёдка на крыше
      const [mx, my] = H.MAST;
      ctx.fillStyle = '#455a64'; rr(mx - 16, -84, 32, 8, 3); ctx.fill();
      ctx.fillStyle = '#607d8b'; ctx.fillRect(mx - 4, my + 8, 8, -84 - (my + 8));
      ctx.save(); ctx.translate(mx, my); ctx.rotate(S.pullOn ? realT * 18 : 0);
      ctx.fillStyle = '#ffb300'; ctx.beginPath(); ctx.arc(0, 0, 12, 0, 7); ctx.fill(); ctx.fillStyle = '#5d4037'; ctx.fillRect(-12, -3, 24, 6); ctx.fillStyle = '#ffe082'; ctx.beginPath(); ctx.arc(0, 0, 4, 0, 7); ctx.fill();
      ctx.restore();
      if (!S.rope) { ctx.strokeStyle = '#90a4ae'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(mx + 10, my + 14, 7, -1.2, 2.6); ctx.stroke(); }
    });
    for (const w of S.wheels) drawWheel(w);
  }
  // Барсик — рыжий кот в синем платке за рулём
  function drawCat(x, y, scared, happy) {
    const bob = Math.sin(realT * 18) * (S.grounded ? 0.8 : 0);
    ctx.save(); ctx.translate(x, y + bob);
    ctx.fillStyle = '#1e5fd6'; ctx.beginPath(); ctx.ellipse(1, 14, 13, 6, 0, 0, 7); ctx.fill();
    ctx.fillStyle = '#e08a35';
    ctx.beginPath(); ctx.moveTo(-11, -9); ctx.lineTo(-8, -24); ctx.lineTo(0, -12); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.moveTo(3, -12); ctx.lineTo(10, -25); ctx.lineTo(13, -8); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#f7b9a8'; ctx.beginPath(); ctx.moveTo(6, -12); ctx.lineTo(10, -20); ctx.lineTo(11, -10); ctx.closePath(); ctx.fill();
    const g = ctx.createRadialGradient(-3, -6, 2, 0, 0, 16); g.addColorStop(0, '#f5a854'); g.addColorStop(1, '#d97a2b');
    ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(0, 0, 14, 13, 0, 0, 7); ctx.fill();
    ctx.fillStyle = '#fbe0b8'; ctx.beginPath(); ctx.ellipse(9, 4, 8, 6.5, 0, 0, 7); ctx.fill();
    ctx.fillStyle = '#f48fb1'; ctx.beginPath(); ctx.ellipse(15, 1.5, 2.6, 2, 0, 0, 7); ctx.fill();
    const er = scared ? 5.2 : 4.4;
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(6, -3, er * 0.85, er, 0, 0, 7); ctx.fill();
    if (happy) { ctx.strokeStyle = '#3e2723'; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.arc(6, -2, 3, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); }
    else { ctx.fillStyle = '#43a047'; ctx.beginPath(); ctx.arc(7.2, -3, er * 0.55, 0, 7); ctx.fill(); ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(7.8, -3, er * (scared ? 0.22 : 0.3), 0, 7); ctx.fill(); }
    ctx.strokeStyle = '#6d3a1a'; ctx.lineWidth = 1.4;
    if (scared) { ctx.fillStyle = '#5d2a14'; ctx.beginPath(); ctx.ellipse(11, 8, 2, 2.6, 0, 0, 7); ctx.fill(); }
    else { ctx.beginPath(); ctx.arc(11, 5.5, happy ? 3.4 : 2.4, 0.1 * Math.PI, 0.8 * Math.PI); ctx.stroke(); }
    ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 0.8;
    for (const dy of [-1, 1.5]) { ctx.beginPath(); ctx.moveTo(14, 4 + dy); ctx.lineTo(23, 2 + dy * 2); ctx.stroke(); }
    ctx.strokeStyle = '#37474f'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(24, 12, 7, 0, 7); ctx.stroke();
    ctx.fillStyle = '#f0a050'; ctx.beginPath(); ctx.arc(20, 8, 3.4, 0, 7); ctx.fill();
    ctx.restore();
  }
  // напарник в кузове (режим «2 игрока»): серый кот у рычага лебёдки
  function drawHelper(x, y, scared, happy) {
    ctx.save(); ctx.translate(x, y);
    ctx.strokeStyle = '#37474f'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(26, 6); ctx.lineTo(34, S.pullOn ? -22 : -16); ctx.stroke();
    ctx.fillStyle = '#e53935'; ctx.beginPath(); ctx.arc(34, S.pullOn ? -24 : -18, 5, 0, 7); ctx.fill();
    ctx.fillStyle = '#8d9aa6'; ctx.beginPath(); ctx.ellipse(0, 4, 15, 13, 0, 0, 7); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-12, -6); ctx.lineTo(-9, -22); ctx.lineTo(-1, -9); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.moveTo(3, -9); ctx.lineTo(10, -22); ctx.lineTo(13, -5); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.ellipse(8, 8, 7, 5.5, 0, 0, 7); ctx.fill();
    const er = scared ? 5 : 4.2;
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(6, -1, er * 0.85, er, 0, 0, 7); ctx.fill();
    if (happy) { ctx.strokeStyle = '#263238'; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.arc(6, 0, 3, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); }
    else { ctx.fillStyle = '#ffb300'; ctx.beginPath(); ctx.arc(7, -1, er * 0.55, 0, 7); ctx.fill(); ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(7.5, -1, er * 0.28, 0, 7); ctx.fill(); }
    ctx.fillStyle = '#f48fb1'; ctx.beginPath(); ctx.ellipse(14, 5, 2.4, 1.8, 0, 0, 7); ctx.fill();
    ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(22, 6, 4, 0, 7); ctx.fill();
    ctx.restore();
  }

  // ---------- интерфейс ----------
  function button(b, label, col, on, sub) {
    ctx.save(); ctx.globalAlpha = on ? 0.95 : 0.72;
    ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(b.x, b.y + 6, b.w, b.h, b.w * 0.28); ctx.fill();
    ctx.fillStyle = col; rr(b.x, b.y + (on ? 3 : 0), b.w, b.h, b.w * 0.28); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.22)'; rr(b.x + 8, b.y + 8 + (on ? 3 : 0), b.w - 16, b.h * 0.36, b.w * 0.2); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = `900 ${Math.round(b.h * (sub ? 0.24 : 0.42))}px system-ui, sans-serif`; ctx.fillText(label, b.x + b.w / 2, b.y + b.h / 2 + (on ? 3 : 0) + (sub ? -b.h * 0.12 : 0));
    if (sub) { ctx.font = `800 ${Math.round(b.h * 0.15)}px system-ui, sans-serif`; ctx.fillText(sub, b.x + b.w / 2, b.y + b.h * 0.72 + (on ? 3 : 0)); }
    ctx.restore();
  }
  function drawHud(inp) {
    layout();
    const B = Object.fromEntries(buttons.map((b) => [b.id, b]));
    const touchy = matchMedia('(pointer: coarse)').matches;
    if (!isAuto() && (touchy || ptrs.size)) {
      button(B.brake, '◀', '#e53935', inp.brake); button(B.gas, '▶', '#43a047', inp.gas);
      button(B.hook, '⚓', S.target || S.rope ? '#ff9800' : '#8d6e63', inp.hook, T.hook);
      if (B.pull) button(B.pull, '⇡', '#5c6bc0', inp.pull, T.pull);
      if (duo) {
        ctx.fillStyle = 'rgba(0,0,0,0.45)'; ctx.font = '900 15px system-ui, sans-serif'; ctx.textAlign = 'right'; ctx.fillText(T.p1, B.gas.x + B.gas.w, B.gas.y - 14);
        ctx.textAlign = 'left'; ctx.fillText(T.p2, B.hook.x, B.hook.y - 14);
      }
    }
    for (const id of ['restart', 'menu', 'mute']) {
      const b = B[id]; ctx.fillStyle = 'rgba(0,0,0,0.28)'; rr(b.x, b.y, b.w, b.h, 12); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.font = '900 24px system-ui, sans-serif';
      ctx.fillText(id === 'restart' ? '↻' : id === 'menu' ? '☰' : muted ? '🔇' : '🔊', b.x + b.w / 2, b.y + b.h / 2 + 1);
    }
    const legend = isAuto() ? T.legendAuto : T.legend;
    if (!(touchy || ptrs.size) && S.t < 12 && !tut && !(wait && isAuto())) {
      ctx.globalAlpha = clamp(12 - S.t, 0, 1); ctx.font = '800 17px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      const tw = Math.min(ctx.measureText(legend).width + 40, W - 16); ctx.fillStyle = 'rgba(0,0,0,0.45)'; rr(W / 2 - tw / 2, H2 - 58, tw, 40, 20); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.fillText(legend, W / 2, H2 - 38, tw - 28); ctx.globalAlpha = 1;
    }
    // полоса пути: старт → финиш, чекпоинты
    const L = S.L, x0 = L.polys[0][0][0] + 320, x1 = L.fin, bw = Math.min(W - 200, 360), bx = 16, by = 22;
    ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(bx, by, bw, 12, 6); ctx.fill();
    const k = clamp((S.truck.x - x0) / (x1 - x0), 0, 1);
    ctx.fillStyle = '#ffca28'; rr(bx, by, Math.max(12, bw * k), 12, 6); ctx.fill();
    for (const c of L.cps) { const q = (c.x - x0) / (x1 - x0); ctx.fillStyle = S.cp && S.cp.x >= c.x ? '#00e676' : '#fff'; ctx.beginPath(); ctx.arc(bx + bw * q, by + 6, 6, 0, 7); ctx.fill(); }
    ctx.fillStyle = '#fff'; ctx.font = '800 15px system-ui, sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillText(W < 600 ? `${lvl + 1}   ⏱ ${S.t.toFixed(1)} / ${H.levels[lvl].par}   ${L.star.got ? '★' : '☆'}${duo ? '   👥' : ''}` : `${T.lvl} ${lvl + 1}${duo ? ' · ' + T.duo : ''}   ⏱ ${S.t.toFixed(1)} / ${H.levels[lvl].par} ${T.sec}   ${L.star.got ? '★' : '☆'}`, bx, by + 20);
    // название уровня и подсказка уровня — первые секунды; после возрождения подсказка снова
    const l = H.levels[lvl], hint = l.hint[LANG];
    if (hintShown._att !== S.attempts) { hintShown._att = S.attempts; hintShown.t0 = realT; }
    const hAl = hint ? clamp(8 - (realT - hintShown.t0), 0, 1) : 0; let hintB = 0;
    if (hint && hAl > 0 && S.state === 'play' && S.t > 0.4) {
      ctx.globalAlpha = hAl;
      const fs = W < 600 ? 17 : 22; ctx.font = `900 ${fs}px system-ui, sans-serif`; ctx.textAlign = 'center';
      const ls = lines(hint, W - 60), tw = Math.max(...ls.map((q) => ctx.measureText(q).width)) + 36, lh = fs * 1.3, hh = ls.length * lh + 18, hx = W / 2 - tw / 2, hy = W < H2 ? 96 : 70;
      ctx.fillStyle = 'rgba(0,0,0,0.45)'; rr(hx, hy, tw, hh, 20); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textBaseline = 'middle';
      ls.forEach((q, i) => ctx.fillText(q, W / 2, hy + 9 + lh * (i + 0.5)));
      ctx.globalAlpha = 1; hintB = hy + hh;
    }
    if (S.t < 1.4) { // название уровня: ниже подсказки, чтобы надписи не ложились друг на друга
      const fs = W < 600 || H2 < 480 ? 30 : 40; ctx.globalAlpha = clamp((1.4 - S.t) * 2, 0, 1); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.font = `900 ${fs}px system-ui, sans-serif`;
      const ty = Math.max(H2 * 0.3, hintB + fs * 0.9); ctx.lineWidth = 8; ctx.strokeStyle = 'rgba(0,0,0,0.45)'; const tt = `${T.lvl} ${lvl + 1} · ${l.name[LANG]}`; ctx.strokeText(tt, W / 2, ty, W - 24); ctx.fillStyle = '#fff'; ctx.fillText(tt, W / 2, ty, W - 24); ctx.globalAlpha = 1;
    }
    // обучение: «нажми — поехали», «держи», «отпусти»
    if (mode === 'play' && S.state === 'play') {
      if (wait && isAuto()) prompt('go'); else if (tut) prompt(tut);
      else if (isAuto() && S.rope && S.ropeA && !S.ropeA.climb && !S.grounded && S.t - hookT0 > 3.5) prompt('rel'); // долго висит и не отпускает — напомнить
    }
    // всплывающие надписи
    toasts.forEach((t, i) => {
      if (t.s === undefined) t.s = realT; t.t = realT - t.s; const al = clamp(1.6 - t.t, 0, 1), ty = H2 * 0.36 - t.t * 30 + i * 54;
      ctx.globalAlpha = al; ctx.font = '900 44px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.lineWidth = 8; ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.strokeText(t.text, W / 2, ty); ctx.fillStyle = t.col; ctx.fillText(t.text, W / 2, ty); ctx.globalAlpha = 1;
    });
    toasts = toasts.filter((t) => t.t < 1.6);
  }
  function panel(x, y, w, h) { ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(x, y + 8, w, h, 26); ctx.fill(); ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 26); ctx.fill(); }
  function bigBtn(id, x, y, w, h, label, col) { menuBtns.push({ id, x, y, w, h }); ctx.fillStyle = 'rgba(0,0,0,0.2)'; rr(x, y + 5, w, h, 18); ctx.fill(); ctx.fillStyle = col; rr(x, y, w, h, 18); ctx.fill(); ctx.fillStyle = '#fff'; ctx.font = `900 ${Math.round(h * 0.4)}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, x + w / 2, y + h / 2 + 1, w - 14); }
  function coinIcon(x, y, r) {
    ctx.fillStyle = '#f39c12'; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    ctx.fillStyle = '#ffd54f'; ctx.beginPath(); ctx.arc(x, y, r * 0.74, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.beginPath(); ctx.arc(x - r * 0.28, y - r * 0.28, r * 0.22, 0, 7); ctx.fill();
  }
  // строка из кусков — текст, монета, звезда: по центру точки x, слева или справа от неё; dry — только посчитать ширину
  function rich(parts, x, y, fs, align, dry) {
    const gap = fs * 0.28, ws = parts.map((q) => { if (q.coin || q.star) return fs; ctx.font = `${q.b || 900} ${fs}px system-ui, sans-serif`; return ctx.measureText(q.t).width; });
    const tot = ws.reduce((a, b) => a + b, 0) + gap * (parts.length - 1); if (dry) return tot;
    let cx = align === 'left' ? x : align === 'right' ? x - tot : x - tot / 2;
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    parts.forEach((q, i) => {
      if (q.coin) coinIcon(cx + ws[i] / 2, y, fs * 0.48); else if (q.star) star5(cx + ws[i] / 2, y - 1, fs * 0.5, '#ffd54f');
      else { ctx.font = `${q.b || 900} ${fs}px system-ui, sans-serif`; ctx.fillStyle = q.c || '#fff'; ctx.fillText(q.t, cx, y + 1); }
      cx += ws[i] + gap;
    });
    return tot;
  }
  // кошелёк: монеты и звёзды, прижат к правому краю xr
  const walletParts = () => [{ coin: 1 }, { t: String(save.coins) }, { t: ' ' }, { star: 1 }, { t: starsTotal() + '/' + NL * 3 }];
  function walletW() { return rich(walletParts(), 0, 0, 16, 'left', true) + 24; }
  function wallet(xr, y) {
    const parts = walletParts(), w = walletW();
    ctx.fillStyle = 'rgba(0,0,0,0.4)'; rr(xr - w, y, w, 32, 16); ctx.fill(); rich(parts, xr - 12, y + 16, 16, 'right'); return w;
  }
  // кружок краски; у дорогих — блеск: хром и золото с бликом и искрой, «радуга» — из цветных долек
  function swatch(cx, cy, r, i) {
    const pc = PAINT[i], sp = pc[2];
    ctx.fillStyle = pc[1]; ctx.beginPath(); ctx.arc(cx, cy + 2, r, 0, 7); ctx.fill();
    if (sp === 'rainbow') { for (let k = 0; k < 12; k++) { ctx.fillStyle = `hsl(${k * 30 + realT * 40},90%,58%)`; ctx.beginPath(); ctx.moveTo(cx, cy - 1); ctx.arc(cx, cy - 1, r * 0.94, (k / 12) * 6.2832 - 0.02, ((k + 1) / 12) * 6.2832 + 0.02); ctx.closePath(); ctx.fill(); } }
    else if (sp) { const g = ctx.createRadialGradient(cx - r * 0.35, cy - r * 0.45, r * 0.05, cx, cy, r); g.addColorStop(0, '#ffffff'); g.addColorStop(0.35, sp === 'gold' ? '#ffe27a' : '#eef3f5'); g.addColorStop(1, sp === 'gold' ? '#e89b00' : '#8fa1ab'); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy - 1, r * 0.94, 0, 7); ctx.fill(); }
    else { ctx.fillStyle = pc[0]; ctx.beginPath(); ctx.arc(cx, cy - 1, r * 0.94, 0, 7); ctx.fill(); }
    ctx.fillStyle = 'rgba(255,255,255,0.45)'; ctx.beginPath(); ctx.arc(cx - r * 0.32, cy - r * 0.38, r * 0.24, 0, 7); ctx.fill();
    if (sp) { const q = r * (0.3 + 0.08 * Math.sin(realT * 5 + i)), sx0 = cx + r * 0.62, sy0 = cy - r * 0.62; ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.moveTo(sx0, sy0 - q); ctx.quadraticCurveTo(sx0, sy0, sx0 + q, sy0); ctx.quadraticCurveTo(sx0, sy0, sx0, sy0 + q); ctx.quadraticCurveTo(sx0, sy0, sx0 - q, sy0); ctx.quadraticCurveTo(sx0, sy0, sx0, sy0 - q); ctx.fill(); }
  }
  function wheelIcon(cx, cy, r, k) {
    ctx.save(); ctx.translate(cx, cy);
    const disc = (q, col) => { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(0, 0, r * q, 0, 7); ctx.fill(); };
    if (k === 3) { ctx.fillStyle = '#90a4ae'; for (let i = 0; i < 12; i++) { ctx.save(); ctx.rotate((i / 12) * 6.283); ctx.beginPath(); ctx.moveTo(r * 0.9, -r * 0.14); ctx.lineTo(r * 1.3, 0); ctx.lineTo(r * 0.9, r * 0.14); ctx.closePath(); ctx.fill(); ctx.restore(); } }
    if (k === 1) { ctx.fillStyle = '#212121'; for (let i = 0; i < 8; i++) { ctx.save(); ctx.rotate((i / 8) * 6.283); ctx.fillRect(r * 0.82, -r * 0.21, r * 0.36, r * 0.42); ctx.restore(); } }
    disc(1, '#212121');
    if (k === 1) { disc(0.6, '#fdd835'); disc(0.5, '#e53935'); disc(0.14, '#212121'); }
    else if (k === 2) { disc(0.74, '#ffc107'); disc(0.6, '#263238'); ctx.strokeStyle = '#ffc107'; ctx.lineWidth = r * 0.16; for (let i = 0; i < 3; i++) { const a = (i / 3) * Math.PI; ctx.beginPath(); ctx.moveTo(-Math.cos(a) * r * 0.66, -Math.sin(a) * r * 0.66); ctx.lineTo(Math.cos(a) * r * 0.66, Math.sin(a) * r * 0.66); ctx.stroke(); } disc(0.24, '#ffd54f'); }
    else if (k === 3) { disc(0.56, '#455a64'); disc(0.22, '#e53935'); }
    else { ctx.strokeStyle = '#424242'; ctx.lineWidth = Math.max(1.5, r * 0.12); for (let i = 0; i < 12; i++) { const a = (i / 12) * 6.283; ctx.beginPath(); ctx.moveTo(Math.cos(a) * r * 0.8, Math.sin(a) * r * 0.8); ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r); ctx.stroke(); } disc(0.54, '#cfd8dc'); ctx.fillStyle = '#78909c'; for (let i = 0; i < 5; i++) { const a = (i / 5) * 6.283; ctx.beginPath(); ctx.arc(Math.cos(a) * r * 0.32, Math.sin(a) * r * 0.32, r * 0.09, 0, 7); ctx.fill(); } }
    ctx.restore();
  }
  // значок грузовика сбоку: 0 пикап, 1 джип, 2 тягач
  function truckIcon(cx, cy, sc, k, pc) {
    ctx.save(); ctx.translate(cx + 3 * sc, cy + 25 * sc); ctx.scale(sc, sc);
    const poly = (pts, col) => { ctx.fillStyle = col; ctx.beginPath(); pts.forEach((q, i) => (i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]))); ctx.closePath(); ctx.fill(); };
    ctx.fillStyle = '#37474f'; rr(-114, -6, 230, 24, 8); ctx.fill();
    if (k === 0) {
      ctx.fillStyle = pc[1]; rr(-112, -44, 128, 40, 6); ctx.fill(); ctx.fillStyle = pc[0]; rr(-114, -28, 132, 26, 6); ctx.fill();
      poly([[14, -2], [14, -74], [20, -78], [64, -78], [90, -38], [112, -34], [120, -26], [120, -2]], pc[0]); poly([[24, -70], [60, -70], [80, -40], [24, -40]], '#b3e5fc');
    } else if (k === 1) {
      poly([[-116, -2], [-116, -34], [-110, -42], [60, -42], [66, -46], [108, -43], [119, -34], [119, -2]], pc[0]);
      ctx.strokeStyle = '#37474f'; ctx.lineWidth = 7; ctx.lineJoin = 'round'; ctx.beginPath(); ctx.moveTo(-100, -43); ctx.lineTo(-18, -82); ctx.lineTo(66, -82); ctx.lineTo(77, -45); ctx.moveTo(-18, -82); ctx.lineTo(-18, -42); ctx.stroke();
      ctx.fillStyle = '#212121'; rr(-130, -56, 12, 48, 5); ctx.fill(); ctx.fillStyle = '#fff59d'; ctx.beginPath(); ctx.arc(70, -92, 7, 0, 7); ctx.fill();
    } else {
      poly([[62, -2], [62, -46], [104, -42], [117, -36], [119, -2]], pc[0]); ctx.fillStyle = pc[0]; rr(12, -92, 58, 90, 8); ctx.fill(); ctx.fillStyle = '#b3e5fc'; rr(30, -80, 34, 32, 4); ctx.fill();
      ctx.fillStyle = pc[1]; rr(-37, -76, 48, 74, 6); ctx.fill(); ctx.fillStyle = pc[0]; ctx.fillRect(-37, -26, 48, 10);
      ctx.fillStyle = '#cfd8dc'; rr(-49, -92, 9, 70, 4); ctx.fill(); ctx.fillRect(117, -38, 6, 34); ctx.fillStyle = '#20262a'; ctx.fillRect(-115, -15, 78, 9);
    }
    ctx.fillStyle = '#ffb300'; ctx.beginPath(); ctx.arc(30, -104, 11, 0, 7); ctx.fill();
    for (const wx of [-72, 72]) { ctx.fillStyle = '#212121'; ctx.beginPath(); ctx.arc(wx, 38, 28, 0, 7); ctx.fill(); ctx.fillStyle = '#cfd8dc'; ctx.beginPath(); ctx.arc(wx, 38, 13, 0, 7); ctx.fill(); }
    ctx.restore();
  }
  function drawUps(x, y, w, h) {
    const rh = Math.min(96, (h - 8) / 2);
    [['eng', '⚙', T.eng, T.engD, '#fb8c00'], ['winch', '⚓', T.winch, T.winchD, '#5c6bc0']].forEach(([k, ic, name, desc, col], r) => {
      const ry = y + r * (rh + 8), lv = save.up[k], max = lv >= UPC.length, cost = UPC[lv], ir = Math.min(24, rh * 0.28);
      ctx.fillStyle = '#f1f4f6'; rr(x, ry, w, rh, 14); ctx.fill();
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x + 14 + ir, ry + rh / 2, ir, 0, 7); ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = `900 ${Math.round(ir * 1.1)}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(ic, x + 14 + ir, ry + rh / 2 + 1);
      const tx = x + 14 + ir * 2 + 12, bw = 104, bh = Math.min(46, rh - 20), deny = k === gar.denyK ? Math.max(0, 0.3 - (realT - gar.deny)) : 0, bx = x + w - bw - 10 + Math.sin(deny * 60) * deny * 24, by = ry + (rh - bh) / 2, tw = x + w - bw - 20 - tx;
      ctx.textAlign = 'left'; ctx.fillStyle = '#263238'; ctx.font = '900 17px system-ui, sans-serif'; ctx.fillText(name, tx, ry + rh * 0.26, tw);
      ctx.fillStyle = '#78909c'; ctx.font = '700 13px system-ui, sans-serif'; ctx.fillText(desc, tx, ry + rh * 0.5, tw);
      const pw = Math.min(22, (tw - 16) / 5); for (let q = 0; q < UPC.length; q++) { ctx.fillStyle = q < lv ? '#43a047' : '#cfd8dc'; rr(tx + q * (pw + 4), ry + rh * 0.68, pw, 9, 4); ctx.fill(); }
      if (!max) menuBtns.push({ id: 'g:up:' + k, x: x + w - bw - 10, y: by, w: bw, h: bh });
      ctx.fillStyle = 'rgba(0,0,0,0.18)'; rr(bx, by + 4, bw, bh, 14); ctx.fill(); ctx.fillStyle = max ? '#a5d6a7' : save.coins >= cost ? '#43a047' : '#b0bec5'; rr(bx, by, bw, bh, 14); ctx.fill();
      if (max) rich([{ t: T.max }], bx + bw / 2, by + bh / 2, 17); else rich([{ t: '+' }, { coin: 1 }, { t: String(cost) }], bx + bw / 2, by + bh / 2, 17);
    });
  }
  function drawGarage() {
    menuBtns = [];
    const port = garPort(), kind = TABS[gar.tab];
    // верх: назад, название, кошелёк
    const bb = { id: 'g:back', x: 10, y: 10, w: 46, h: 46 }; menuBtns.push(bb);
    ctx.fillStyle = 'rgba(0,0,0,0.34)'; rr(bb.x, bb.y, bb.w, bb.h, 12); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.font = '900 30px system-ui, sans-serif'; ctx.fillText('‹', bb.x + bb.w / 2, bb.y + bb.h / 2 - 3);
    let wl = W - 10 - wallet(W - 10, 17);
    if (PG.on && PG.rew && !PG.pend && pgNow() - PG.lastFree > 180) { // «+100 монет за ролик»: на телефоне под кошельком, на широком экране — слева от него
      const aw = 128, ab = port ? { id: 'g:ad', x: W - 10 - aw, y: 56, w: aw, h: 36 } : { id: 'g:ad', x: wl - 8 - aw, y: 15, w: aw, h: 36 }; menuBtns.push(ab); if (!port) wl = ab.x;
      ctx.fillStyle = 'rgba(0,0,0,0.2)'; rr(ab.x, ab.y + 3, ab.w, ab.h, 14); ctx.fill(); ctx.fillStyle = '#7e57c2'; rr(ab.x, ab.y, ab.w, ab.h, 14); ctx.fill();
      rich([{ t: '🎬 +100' }, { coin: 1 }], ab.x + ab.w / 2, ab.y + ab.h / 2, 16);
    }
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.font = '900 24px system-ui, sans-serif'; ctx.lineWidth = 6; ctx.strokeStyle = 'rgba(0,0,0,0.4)';
    if (68 + ctx.measureText(T.garage).width + 10 < wl) { ctx.strokeText(T.garage, 68, 34); ctx.fillStyle = '#fff'; ctx.fillText(T.garage, 68, 34); }
    if (window.HOOK_TEST) { const tb = { id: 'g:test', x: W - 132, y: 56, w: 122, h: 30 }; menuBtns.push(tb); ctx.fillStyle = 'rgba(0,0,0,0.34)'; rr(tb.x, tb.y, tb.w, tb.h, 15); ctx.fill(); ctx.fillStyle = '#fff'; ctx.font = '800 14px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.fillText(T.test, tb.x + tb.w / 2, tb.y + tb.h / 2 + 1); }
    // панель: вкладки, плитки, кнопка
    const { px, py, pw, ph } = garLayout();
    panel(px, py, pw, ph);
    const tw = (pw - 20) / 4, th = 40, tx0 = px + 10, ty0 = py + 10, tfs = clamp(Math.floor(tw / 5.6), 12, 16);
    TABS.forEach((k, i) => {
      const x = tx0 + i * tw; menuBtns.push({ id: 'g:tab:' + i, x, y: ty0, w: tw, h: th });
      ctx.fillStyle = gar.tab === i ? '#ffca28' : '#eceff1'; rr(x + 2, ty0, tw - 4, th, 12); ctx.fill();
      ctx.fillStyle = gar.tab === i ? '#3e2723' : '#546e7a'; ctx.font = `900 ${tfs}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(T.tabs[i], x + tw / 2, ty0 + th / 2 + 1, tw - 12);
    });
    const cy0 = ty0 + th + 10, ah = 52, ay = py + ph - 12 - ah;
    if (kind === 'up') { drawUps(px + 12, cy0, pw - 24, py + ph - 12 - cy0); return; }
    const items = SHOP[kind], n = items.length, cH = ay - 10 - cy0, cap = port ? 124 : 170;
    let cols = n, cell = 0; for (let c = n; c >= 2; c--) { if (n % c) continue; const q = Math.min((pw - 20) / c, (cH * c) / n, cap); if (q > cell + 0.5) { cell = q; cols = c; } } // только ровные сетки: 3, 4 или 2×2, 6 или 3×2
    const rows = Math.ceil(n / cols), gx0 = px + (pw - cols * cell) / 2, gy0 = cy0 + Math.max(0, (cH - rows * cell) / 2), owned = save[OWN[kind]];
    items.forEach((it, i) => {
      const x = gx0 + (i % cols) * cell + 4, y = gy0 + Math.floor(i / cols) * cell + 4, w = cell - 8, pick = gar.pick[kind] === i, has = owned.includes(i), fs = clamp(Math.round(w * 0.15), 12, 15);
      menuBtns.push({ id: 'g:item:' + i, x, y, w, h: w });
      ctx.fillStyle = pick ? '#fff3c4' : '#f1f4f6'; rr(x, y, w, w, 14); ctx.fill();
      if (pick) { ctx.lineWidth = 3; ctx.strokeStyle = '#ffb300'; rr(x + 1.5, y + 1.5, w - 3, w - 3, 13); ctx.stroke(); }
      const icy = y + w * (kind === 'color' ? (has ? 0.5 : 0.42) : 0.35);
      if (kind === 'color') swatch(x + w / 2, icy, w * 0.26, i);
      else if (kind === 'wheels') wheelIcon(x + w / 2, icy, w * 0.2, i);
      else truckIcon(x + w / 2, icy, Math.min((w * 0.84) / 252, (w * 0.46) / 180), i, PAINT[gar.pick.color]);
      if (it.n) { ctx.fillStyle = '#37474f'; ctx.font = `800 ${fs}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(it.n[LANG], x + w / 2, y + w * 0.71, w - 8); }
      const ly = y + w * (it.n ? 0.88 : 0.82);
      if (!has) rich([it.stars ? { star: 1 } : { coin: 1 }, { t: String(it.stars || it.cost), c: '#8d6e00' }], x + w / 2, ly, fs);
      else if (save[kind] === i) { ctx.fillStyle = '#43a047'; ctx.beginPath(); ctx.arc(x + w - 14, y + 14, 10, 0, 7); ctx.fill(); ctx.fillStyle = '#fff'; ctx.font = '900 13px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('✓', x + w - 14, y + 15); }
    });
    // кнопка: своё — «выбрано», чужое — купить за монеты или забрать за звёзды
    const i = gar.pick[kind], it = items[i], has = owned.includes(i), deny = gar.denyK ? 0 : Math.max(0, 0.3 - (realT - gar.deny)), ax = px + 12 + Math.sin(deny * 60) * deny * 30, aw = pw - 24;
    let col = '#b0bec5', parts;
    if (has) { parts = [{ t: '✓ ' + T.chosen }]; col = '#a5d6a7'; }
    else if (it.stars) { const have = starsTotal(); if (have >= it.stars) { parts = [{ t: T.take + '  ·' }, { star: 1 }, { t: String(it.stars) }]; col = '#43a047'; } else parts = [{ t: T.needStars }, { star: 1 }, { t: it.stars + '  ·  ' + T.have + ' ' + have }]; }
    else if (save.coins >= it.cost) { parts = [{ t: T.buy + '  ·' }, { coin: 1 }, { t: String(it.cost) }]; col = '#43a047'; }
    else parts = [{ t: T.need }, { coin: 1 }, { t: String(it.cost - save.coins) }];
    if (!has) menuBtns.push({ id: 'g:act', x: px + 12, y: ay, w: aw, h: ah });
    ctx.fillStyle = 'rgba(0,0,0,0.18)'; rr(ax, ay + 4, aw, ah, 16); ctx.fill(); ctx.fillStyle = col; rr(ax, ay, aw, ah, 16); ctx.fill();
    rich(parts, ax + aw / 2, ay + ah / 2, 19);
  }
  function drawMenu() {
    menuBtns = [];
    ctx.fillStyle = 'rgba(10,40,70,0.5)'; ctx.fillRect(0, 0, W, H2);
    // sm — невысокое окно; tight — совсем низкое (телефон лёжа, маленький квадрат): без подзаголовка и подсказки; ws — низкое и широкое: «Гараж» и «Играть» встают по бокам от строки серии, плиткам уровней достаётся вся высота
    const port = W < H2, sm = H2 < 520, tight = H2 < 430, ws = sm && W >= 600;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    // название не должно залезать под кошелёк в правом углу: если по ширине не расходятся — опускаем название ниже кошелька
    let tf = tight ? 32 : sm ? 38 : port ? 46 : 64, ty = tight ? 30 : sm ? 40 : port ? 64 : Math.max(60, H2 * 0.1);
    const wl = W - 10 - walletW() - 8, fits = () => { ctx.font = `900 ${tf}px system-ui, sans-serif`; return W / 2 + Math.min(ctx.measureText(T.title).width, W - 30) / 2 + 5 <= wl; };
    if (!fits()) { ty = Math.max(ty, 46 + tf * 0.4 + 6); }
    ctx.font = `900 ${tf}px system-ui, sans-serif`; ctx.lineWidth = 10; ctx.strokeStyle = '#bf360c';
    ctx.strokeText(T.title, W / 2, ty, W - 30); ctx.fillStyle = '#ffca28'; ctx.fillText(T.title, W / 2, ty, W - 30);
    if (!tight) { ctx.font = '800 17px system-ui, sans-serif'; ctx.fillStyle = '#fff'; ctx.fillText(T.sub, W / 2, ty + (sm ? 30 : 40)); }
    // режим: 1 игрок / 2 игрока
    const mw = Math.min(W - 40, 440), mx = W / 2 - mw / 2, my = ty + (tight ? 26 : sm ? 52 : 66), mh = tight ? 40 : 46;
    ctx.fillStyle = 'rgba(0,0,0,0.3)'; rr(mx, my, mw, mh, 23); ctx.fill();
    const cur = duo ? 'duo' : ctl, sw = (mw - 8) / 3;
    [['auto', '👆 ' + T.one, '#43a047'], ['manual', '🎮 ' + T.hand, '#fb8c00'], ['duo', '👥 ' + T.two, '#1e88e5']].forEach(([id, lab, col], i) => {
      const x = mx + 4 + i * sw; menuBtns.push({ id: 'm:' + id, x, y: my, w: sw, h: mh });
      if (cur === id) { ctx.fillStyle = col; rr(x, my + 4, sw, mh - 8, 19); ctx.fill(); }
      ctx.fillStyle = '#fff'; ctx.font = `900 ${clamp(Math.floor(sw / 7.6), 12, 17)}px system-ui, sans-serif`; ctx.fillText(lab, x + sw / 2, my + mh / 2 + 1, sw - 10);
    });
    ctx.font = '700 14px system-ui, sans-serif'; ctx.fillStyle = 'rgba(255,255,255,0.92)';
    const coarse = matchMedia('(pointer: coarse)').matches, help = isAuto() ? (coarse ? T.touchAuto : T.keyAuto) : coarse ? (duo ? T.touchDuo : T.touchSolo) : (duo ? T.duoTxt : T.soloTxt).slice(0, 2).join('   ·   ');
    const cl = tight ? [] : lines(help, W - 40); cl.forEach((q, i) => ctx.fillText(q, W / 2, my + mh + 18 + i * 18)); // в низком окне подсказку не пишем — место нужно плиткам уровней
    // серия: стрелки и название; вторая открывается за звёзды
    const sy0 = my + mh + (cl.length ? 24 + cl.length * 18 : 10), open = serOpen(ser), sw2 = Math.min(W - 40, 360), sx0 = W / 2 - sw2 / 2;
    ctx.fillStyle = 'rgba(0,0,0,0.3)'; rr(sx0, sy0, sw2, 36, 18); ctx.fill();
    for (const [id, ch, x, on] of [['s:prev', '‹', sx0, ser > 0], ['s:next', '›', sx0 + sw2 - 44, ser < NS - 1]]) { if (on) menuBtns.push({ id, x, y: sy0 - 4, w: 44, h: 44 }); ctx.fillStyle = on ? '#fff' : 'rgba(255,255,255,0.3)'; ctx.font = '900 26px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(ch, x + 22, sy0 + 16); }
    if (open) { ctx.fillStyle = '#fff'; ctx.font = '900 17px system-ui, sans-serif'; ctx.textAlign = 'center'; ctx.fillText(`${T.series} ${ser + 1} · ${SER[ser].n[LANG]}`, W / 2, sy0 + 19, sw2 - 96); }
    else rich([{ t: `${SER[ser].n[LANG]} · ${T.opens}` }, { star: 1 }, { t: String(SER[ser].need) }], W / 2, sy0 + 18, 15);
    // сетка уровней этой серии
    const i0 = ser * 12, cnt = Math.min(12, NL - i0), gy0 = sy0 + 36 + 8, footer = ws ? 10 : 70;
    let cols = port ? 3 : 6, cell = 0; // стоя: 3 в ряд, а на коротком экране — 4 в ряд, если так плитки крупнее
    for (const c of port ? [3, 4] : [6]) { const q = Math.min((Math.min(W, 900) - 40) / c, (H2 - gy0 - footer) / Math.ceil(cnt / c), 130); if (q > cell + 0.5) { cell = q; cols = c; } }
    const rows = Math.ceil(cnt / cols), gw = cell * cols, gx0 = W / 2 - gw / 2;
    for (let q = 0; q < cnt; q++) {
      const i = i0 + q, c = q % cols, r = Math.floor(q / cols), x = gx0 + c * cell + 6, y = gy0 + r * cell + 6, w = cell - 12, st = save.stars[i] || 0;
      if (open) menuBtns.push({ id: 'L' + i, x, y, w, h: w });
      ctx.globalAlpha = open ? 1 : 0.45;
      const cr = Math.min(16, w * 0.26);
      ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(x, y + 5, w, w, cr); ctx.fill();
      ctx.fillStyle = st ? '#fffdf7' : ser ? '#fff3e0' : '#e3f2fd'; rr(x, y, w, w, cr); ctx.fill();
      ctx.fillStyle = '#263238'; ctx.font = `900 ${Math.round(w * 0.34)}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(i + 1), x + w / 2, y + w * 0.38);
      for (let k = 0; k < 3; k++) star5(x + w / 2 + (k - 1) * w * 0.24, y + w * 0.76, w * 0.1, k < st ? '#ffd54f' : '#cfd8dc');
      ctx.globalAlpha = 1;
    }
    if (!open) { const have = starsTotal(), cy = gy0 + rows * cell / 2; ctx.fillStyle = 'rgba(0,0,0,0.6)'; rr(W / 2 - 150, cy - 30, 300, 60, 18); ctx.fill(); rich([{ t: '🔒 ' + T.needStars }, { star: 1 }, { t: SER[ser].need + ' · ' + T.have + ' ' + have }], W / 2, cy, 18); }
    if (ws) { const bw = Math.min(150, sx0 - 30); bigBtn('garage', sx0 - 10 - bw, sy0 - 3, bw, 40, '🔧 ' + T.garage, '#fb8c00'); bigBtn('play', sx0 + sw2 + 10, sy0 - 3, bw, 40, '▶ ' + T.play, '#43a047'); }
    else {
      const by = Math.min(H2 - 60, gy0 + rows * cell + 10), bw = Math.min(172, (W - 46) / 2);
      bigBtn('garage', W / 2 - bw - 6, by, bw, 50, '🔧 ' + T.garage, '#fb8c00'); bigBtn('play', W / 2 + 6, by, bw, 50, '▶ ' + T.play, '#43a047');
    }
    wallet(W - 10, 8);
  }
  function drawWin() {
    menuBtns = [];
    ctx.fillStyle = 'rgba(10,40,70,0.4)'; ctx.fillRect(0, 0, W, H2);
    const w = Math.min(W - 32, 460), h = Math.min(H2 - 24, 374), x = W / 2 - w / 2, y = H2 / 2 - h / 2, tight = h < 352;
    panel(x, y, w, h);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#2e7d32'; ctx.font = '900 28px system-ui, sans-serif';
    ctx.fillText(T.win, W / 2, y + 40); ctx.fillStyle = '#78909c'; ctx.font = '800 16px system-ui, sans-serif'; ctx.fillText(`${T.lvl} ${lvl + 1} · ${H.levels[lvl].name[LANG]}`, W / 2, y + 70);
    const labs = [T.fin, T.starW, `≤ ${res.par} ${T.sec}`], on = [true, res.got, res.fast];
    for (let k = 0; k < 3; k++) {
      const cx = W / 2 + (k - 1) * Math.min(120, w * 0.28), cy = y + 132, big = k === 1 ? 38 : 32, pop = clamp((realT - (res.t0 || (res.t0 = realT)) - k * 0.25) * 4, 0, 1);
      star5(cx, cy, big * (on[k] ? 0.6 + 0.4 * pop : 1), on[k] && pop > 0 ? '#ffd54f' : '#cfd8dc');
      ctx.fillStyle = on[k] ? '#37474f' : '#90a4ae'; ctx.font = '800 15px system-ui, sans-serif'; ctx.fillText(labs[k], cx, cy + 52);
    }
    ctx.fillStyle = '#37474f'; ctx.font = '800 18px system-ui, sans-serif'; ctx.textAlign = 'center';
    if (!tight) ctx.fillText(`${T.time}: ${res.t.toFixed(1)} ${T.sec}   ·   ${T.tries}: ${res.tries}`, W / 2, y + 222);
    // монеты за заезд: счётчик набегает после звёзд
    const shown = Math.round(res.earn * clamp((realT - res.t0 - 0.9) * 1.6, 0, 1));
    const ry = y + (tight ? 224 : 256), canX2 = PG.on && PG.rew && !res.x2 && !res.noad, gain = res.x2 ? res.earn * 2 : shown;
    if (canX2) { // ролик за награду: по желанию игрока, со значком видео и точной наградой; без ролика монеты всё равно начислены
      const bw2 = Math.min(190, w * 0.44), bx2 = x + w - 24 - bw2; menuBtns.push({ id: 'x2', x: bx2, y: ry - 22, w: bw2, h: 44 });
      ctx.fillStyle = 'rgba(0,0,0,0.18)'; rr(bx2, ry - 19, bw2, 44, 14); ctx.fill(); ctx.fillStyle = '#7e57c2'; rr(bx2, ry - 22, bw2, 44, 14); ctx.fill();
      rich([{ t: '🎬 ' + T.x2 }, { t: '+' + res.earn }, { coin: 1 }], bx2 + bw2 / 2, ry, 18);
      rich([{ t: '+' + gain, c: '#ef6c00' }, { coin: 1 }], x + 24 + (w - 48 - bw2 - 12) / 2, ry, 22);
    } else rich([{ t: '+' + gain, c: '#ef6c00' }, { coin: 1 }, { t: ' ' }, { t: `${T.total} ${save.coins - (res.x2 ? 0 : res.earn - shown)}`, c: '#90a4ae', b: 800 }], W / 2, ry, 21);
    const bh = 54, bw = (w - 48 - 20) / 3, b0 = x + 24, byy = y + h - bh - 22;
    bigBtn('menu', b0, byy, bw, bh, '☰', '#78909c');
    bigBtn('again', b0 + bw + 10, byy, bw, bh, '↻', '#fb8c00');
    if (canNext()) bigBtn('next', b0 + 2 * (bw + 10), byy, bw, bh, T.next + ' ▶', '#43a047'); else bigBtn('menu', b0 + 2 * (bw + 10), byy, bw, bh, T.levels, '#43a047');
  }

  // ---------- главный цикл ----------
  function frame(now) {
    const hold = PG.ad || PG.paused || !!PG.pend || document.hidden; // реклама, пауза площадки, скрытая вкладка — мир стоит
    if (master) master.gain.value = hold || PG.mutedP ? 0 : 0.7;
    const dt = Math.min(0.05, (now - last) / 1000); last = now; realT += dt;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    if (!S) { S = H.create(0); camX = S.truck.x + 300; camY = S.truck.y; }
    let inp = { gas: false, brake: false, hook: false, pull: false };
    if (mode === 'play' && !dbg.freeze && !hold) {
      inp = input(); const auto = isAuto();
      if (auto && wait && inp.hook) wait = false; // «один палец»: уровень и каждая новая попытка начинаются с первого нажатия
      const want = auto && wait ? 0 : tutor(inp);
      ts = auto && wait ? 0 : want >= 1 ? Math.min(1, ts + dt * 6) : Math.max(want, ts - dt * 7);
      acc += dt * ts; let n = 0;
      while (acc >= P.DT && n < 10) {
        if (auto) { const q = H.assist(S); inp.gas = q.gas; inp.brake = q.brake; } // газ сам: ведёт то же правило, что и автопилот в тестах
        S.step(inp); acc -= P.DT; n++;
        for (const e of S.events) {
          if (e.e === 'hook') { sfx.hook(); hookT0 = S.t; } else if (e.e === 'unhook') sfx.unhook();
          else if (e.e === 'dead') { sfx.crash(); shake = 0.4; toasts.push({ t: 0, text: e.why === 'crash' ? T.crash : T.fell, col: '#ff8a80' }); }
          else if (e.e === 'cp') { sfx.cp(); toasts.push({ t: 0, text: T.cp, col: '#69f0ae' }); }
          else if (e.e === 'star') { sfx.star(); toasts.push({ t: 0, text: T.star, col: '#ffd54f' }); }
          else if (e.e === 'win') { sfx.win(); S.wonAt = S.t; }
          else if (e.e === 'respawn') { wait = auto; ts = 1; }
          else if (e.e === 'spring') { tone(260, 0.28, 'sine', 0.2, 880); shake = 0.12; toasts.push({ t: 0, text: T.boing, col: '#f48fb1' }); }
          else if (e.e === 'snap') { sfx.snap(); shake = 0.25; toasts.push({ t: 0, text: T.snap, col: '#ffab91' }); }
        }
        S.events.length = 0;
      }
      if (S.state === 'win' && S.wonT > 0.9) { finish(); mode = 'win'; }
    }
    if (mode === 'garage' && !hold) { acc += dt; let n = 0; while (acc >= P.DT && n < 10) { S.step(inp); acc -= P.DT; n++; } S.events.length = 0; } // в гараже грузовик просто стоит на подвеске
    engineSound(S, inp.gas);
    camera(dt);
    shake = Math.max(0, shake - dt);
    if (use3d) { ctx.clearRect(0, 0, W, H2); R3.draw(S, { camX, camY, Z, W, H: H2, DPR, t: realT, lvl, duo, shake, gas: inp.gas, g: gcam, oy: oy(), theme: mode === 'garage' ? 0 : H.levels[lvl].ser }); }
    else {
      ctx.save(); if (shake > 0) ctx.translate((Math.random() - 0.5) * shake * 30, (Math.random() - 0.5) * shake * 30);
      drawSky(); drawGround(); drawObjects(); drawRope(); drawTruck(); drawPits();
      ctx.restore();
    }
    if (use3d && !dbg.clean && mode !== 'menu') { const tg = ctx.createLinearGradient(0, 0, 0, 96); tg.addColorStop(0, 'rgba(8,38,70,0.34)'); tg.addColorStop(1, 'rgba(8,38,70,0)'); ctx.fillStyle = tg; ctx.fillRect(0, 0, W, 96); }
    hangT = mode === 'play' && S.state === 'play' && S.rope && S.hangSlow && !S.pump && !isAuto() ? hangT + dt : 0;
    if (!dbg.clean && hangT > 0.55) {
      const fs = W < 600 ? 20 : 26, pul = 1 + 0.05 * Math.sin(realT * 9); ctx.font = `900 ${fs}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      const tw = ctx.measureText(T.pump).width + 44, bx = W / 2, by = H2 * (W < H2 ? 0.52 : 0.62);
      ctx.save(); ctx.translate(bx, by); ctx.scale(pul, pul); ctx.fillStyle = 'rgba(46,125,50,0.92)'; rr(-tw / 2, -fs, tw, fs * 2, fs); ctx.fill(); ctx.fillStyle = '#fff'; ctx.fillText(T.pump, 0, 1); ctx.restore();
    }
    if (!dbg.clean) { if (mode === 'play' || mode === 'win') drawHud(inp); if (mode === 'menu') drawMenu(); else if (mode === 'win') drawWin(); else if (mode === 'garage') drawGarage(); }
    requestAnimationFrame(frame);
  }
  window.__hook = { dbg, use3d, pg: PG, get tut() { return tut; }, get wait() { return wait; }, get ts() { return ts; }, setCtl: (m) => { duo = m === 'duo'; if (!duo) ctl = m; }, get ctl() { return duo ? 'duo' : ctl; }, garage: openGarage, click: menuClick, get gar() { return gar; }, get btns() { return menuBtns; }, coins: (n) => { save.coins += n; store(); }, get mode() { return mode; }, get lvl() { return lvl; }, save: () => save, start: startGame, get S() { return S; }, keys, input, get buttons() { layout(); return buttons; } };
  applyLook(curLook());
  requestAnimationFrame(frame);
  // «игра готова»: после первых кадров, когда мост ответил (или сразу, если моста нет)
  (function ready() { if (PG.ready) return; if (PG.on) { PG.ready = true; pgMsg('game_ready'); } else if (performance.now() - PG.t0 < 7000) setTimeout(ready, 200); })();
})();
