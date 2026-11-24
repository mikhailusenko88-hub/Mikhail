'use strict';
/* Грязь, вид сбоку — рисование и управление. Картинку даёт объёмный вид Hook Truck (r3d.js), здесь — вода, деревья, канистры, брызги,
   кнопки привода и подсказки. Правая рука — газ и назад, левая — лебёдка и три переключателя. */
(function () {
  const P = window.TPhys, M = window.MudSide, R3 = window.Hook3D;
  const cv = document.getElementById('c'), ctx = cv.getContext('2d'), glc = document.getElementById('gl');
  const RU = /^(ru|uk|be|kk)/i.test(navigator.language || '') || /[?&]ru\b/.test(location.search);
  const T = RU ? {
    goal: 'Довези брёвна до лесопилки. Застрял — включай помощников слева', awd: '4×4', lock: 'БЛОК', low: 'ПОНИЖ', winch: 'ЛЕБЁДКА', fuel: 'Топливо',
    hAwd: 'Буксуешь? Включи 4×4 — полный привод', hLock: 'Не тянет? Включи БЛОК — блокировку', hLow: 'Мало тяги? Включи ПОНИЖ — пониженную', hWinch: 'Держи ЛЕБЁДКУ — подтянет к дереву', hBack: 'Сдай назад и попробуй с разгона',
    hFuel: 'Топлива мало: выключай лишнее на твёрдой дороге', hOff: 'Твёрдая дорога: выключи помощников — сбережёшь топливо',
    dFuel: 'Топливо кончилось', dWater: 'Мотор залило водой', dFlip: 'Перевернулся', back: 'Возврат на отметку…', cp: 'Отметка!', can: '+30 топлива',
    win: 'Груз доставлен!', s1: 'Доехал', s2: 'Без эвакуации', s3: 'Топлива ≥ 30%', time: 'Время', again: 'Ещё раз', rescue: 'Эвакуация',
    keys: '→ газ   ← назад   ·   1 — 4×4   2 — блок   3 — пониж   ·   Пробел — лебёдка', wheels: 'колёса', sec: 'с',
  } : {
    goal: 'Haul the logs to the sawmill. Stuck? Switch on the helpers on the left', awd: '4×4', lock: 'LOCK', low: 'LOW', winch: 'WINCH', fuel: 'Fuel',
    hAwd: 'Wheels spinning? Switch on 4×4', hLock: 'Not enough grip? Switch on LOCK', hLow: 'Not enough pull? Switch on LOW gear', hWinch: 'Hold WINCH — it pulls you to the tree', hBack: 'Back up and take a run at it',
    hFuel: 'Low fuel: switch helpers off on firm road', hOff: 'Firm road: switch the helpers off to save fuel',
    dFuel: 'Out of fuel', dWater: 'Engine flooded', dFlip: 'Rolled over', back: 'Back to the checkpoint…', cp: 'Checkpoint!', can: '+30 fuel',
    win: 'Cargo delivered!', s1: 'Delivered', s2: 'No rescue', s3: 'Fuel ≥ 30%', time: 'Time', again: 'Again', rescue: 'Rescue',
    keys: '→ gas   ← reverse   ·   1 — 4×4   2 — lock   3 — low   ·   Space — winch', wheels: 'wheels', sec: 's',
  };
  let W = 0, H2 = 0, DPR = 1;
  function resize() { DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H2 = innerHeight; cv.width = W * DPR; cv.height = H2 * DPR; }
  addEventListener('resize', resize); resize();
  const use3d = !!(R3 && R3.init(glc));
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const rr = (x, y, w, h, r) => { ctx.beginPath(); if (!(w > 0 && h > 0)) return; r = Math.max(0, Math.min(r, w / 2, h / 2)); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); };

  // ---------- состояние ----------
  const S = M.create(0), sw = { awd: false, lock: false, low: false }, keys = {}, ptrs = new Map();
  let mode = 'play', realT = 0, last = performance.now(), acc = 0, camX = S.truck.x + 300, camY = S.truck.y, Z = 0.5, buttons = [], toast = null, offT = 0, muted = false;
  const dbg = { freeze: false };

  // ---------- звук: мотор ----------
  let AC = null, eng = null;
  function audio() { if (AC) return; try { AC = new (window.AudioContext || window.webkitAudioContext)(); const o = AC.createOscillator(), f = AC.createBiquadFilter(), g = AC.createGain(); o.type = 'sawtooth'; f.type = 'lowpass'; f.frequency.value = 380; g.gain.value = 0; o.connect(f); f.connect(g); g.connect(AC.destination); o.start(); eng = { o, g }; } catch (e) { AC = null; } }
  function tone(fq, d, v) { if (!AC || muted) return; try { const t = AC.currentTime, o = AC.createOscillator(), g = AC.createGain(); o.type = 'triangle'; o.frequency.value = fq; g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t + d); o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + d + 0.02); } catch (e) { /* */ } }

  // ---------- управление ----------
  const TOG = ['awd', 'lock', 'low'];
  function flip(k) { if (mode !== 'play' || S.state !== 'play') return; sw[k] = !sw[k]; tone(sw[k] ? 760 : 420, 0.07, 0.12); }
  addEventListener('keydown', (e) => {
    if (e.repeat) return; keys[e.code] = true; audio();
    if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
    if (e.code === 'Digit1' || e.code === 'KeyQ') flip('awd'); else if (e.code === 'Digit2' || e.code === 'KeyE') flip('lock'); else if (e.code === 'Digit3' || e.code === 'ShiftLeft') flip('low');
    else if (e.code === 'KeyR') S.rescue(); else if (e.code === 'Enter' && mode === 'win') again();
  });
  addEventListener('keyup', (e) => { keys[e.code] = false; });
  const hit = (x, y) => buttons.find((b) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
  const held = (id) => { for (const p of ptrs.values()) if (p === id) return true; return false; };
  cv.addEventListener('pointerdown', (e) => {
    audio(); try { cv.setPointerCapture(e.pointerId); } catch (er) { /* */ }
    const b = hit(e.clientX, e.clientY); if (!b) return;
    if (TOG.includes(b.id)) flip(b.id); else if (b.id === 'rescue') S.rescue(); else if (b.id === 'mute') muted = !muted; else if (b.id === 'again') again(); else ptrs.set(e.pointerId, b.id);
  });
  const up = (e) => ptrs.delete(e.pointerId);
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  cv.addEventListener('contextmenu', (e) => e.preventDefault());
  function again() { S.reset(); sw.awd = sw.lock = sw.low = false; mode = 'play'; toast = null; }
  function input() {
    const k = keys;
    return { gas: !!(k.ArrowRight || k.KeyD || k.ArrowUp) || held('gas'), brake: !!(k.ArrowLeft || k.KeyA || k.ArrowDown) || held('brake'), winch: !!(k.Space || k.KeyW) || held('winch'), awd: sw.awd, lock: sw.lock, low: sw.low };
  }

  // ---------- кнопки ----------
  function layout() {
    const port = W < H2, sm = Math.min(W, H2) < 430, g = sm ? 8 : 12, bw = sm ? 76 : 92, bh = sm ? 74 : 88, by = H2 - bh - g - 4;
    buttons = [{ id: 'gas', x: W - bw - g, y: by, w: bw, h: bh }, { id: 'brake', x: W - bw * 2 - g * 2, y: by, w: bw, h: bh }, { id: 'rescue', x: W - 54, y: 10, w: 44, h: 44 }, { id: 'mute', x: W - 104, y: 10, w: 44, h: 44 }];
    if (port) { // стоя: лебёдка под левой рукой, три переключателя — рядом над ней
      const ww = Math.min(W - bw * 2 - g * 4, 236), tw = (ww - 12) / 3, th = sm ? 50 : 56;
      buttons.push({ id: 'winch', x: g, y: by, w: ww, h: bh });
      TOG.forEach((k, i) => buttons.push({ id: k, x: g + i * (tw + 6), y: by - th - 8, w: tw, h: th }));
    } else { // лёжа и на широком экране: всё в один нижний ряд — кнопки не закрывают грузовик
      const ww = sm ? 104 : 124, tw = Math.min(sm ? 66 : 80, (W - bw * 2 - ww - g * 5 - 18) / 3);
      buttons.push({ id: 'winch', x: g, y: by, w: ww, h: bh });
      TOG.forEach((k, i) => buttons.push({ id: k, x: g + ww + 8 + i * (tw + 6), y: by, w: tw, h: bh }));
    }
  }
  const B = (id) => buttons.find((b) => b.id === id);

  // ---------- свои предметы в объёмной сцене: вода, деревья для лебёдки, канистры, постройки, брёвна, брызги ----------
  let canM = [], blobs = [], blobI = 0, blobAcc = 0, logsOn = null;
  if (use3d) {
    R3.onBuild = (q) => {
      const { T: T3, lvlG, L, C, lam, box, cyl, ROAD, ZF, ZB } = q;
      for (const w of L.water) { // брод: вода стоит выше дна
        const m = new T3.Mesh(new T3.BoxGeometry(w.x1 - w.x0, w.depth + 8, ZF - ZB), new T3.MeshLambertMaterial({ color: C('#4fc3f7'), transparent: true, opacity: 0.62, depthWrite: false }));
        m.position.set((w.x0 + w.x1) / 2, -w.y - (w.depth + 8) / 2, (ZF + ZB) / 2); m.renderOrder = 3; lvlG.add(m);
      }
      for (const a of L.trees) { // дерево с жёлтой стропой: за него цепляется лебёдка
        const gy = -a.gy; q.tree(a.x, gy, -ROAD - 46, 2.1);
        cyl(13, 150, 7, lam('#6d4c33'), a.x, gy + 75, -ROAD - 46, lvlG); box(30, 10, 30, lam('#ffca28'), a.x, -a.y, -ROAD - 46, lvlG);
      }
      canM = L.cans.map((c) => { const g = new T3.Group(); box(26, 34, 16, lam('#e53935'), 0, 0, 0, g); box(10, 6, 10, lam('#ffeb3b'), 6, 20, 0, g); g.position.set(c.x, -c.y - 26, 0); lvlG.add(g); return g; });
      for (const k of L.marks) {
        const gy = -k.y, z = -ROAD - 150;
        if (k.kind === 'garage') { box(300, 150, 180, lam('#90a4ae'), k.x, gy + 75, z, lvlG); box(320, 16, 200, lam('#c62828'), k.x, gy + 158, z, lvlG); box(120, 110, 6, lam('#37474f'), k.x, gy + 55, z + 92, lvlG); }
        else { box(340, 130, 200, lam('#a1887f'), k.x, gy + 65, z, lvlG); box(360, 18, 220, lam('#5d4037'), k.x, gy + 139, z, lvlG); for (let i = 0; i < 5; i++) cyl(15, 170, 8, lam(i & 1 ? '#8d6e63' : '#795548'), k.x - 250 + (i % 3) * 32 + (i > 2 ? 16 : 0), gy + 15 + (i > 2 ? 27 : 0), z + 120, lvlG, true); }
      }
      if (!blobs.length) for (let i = 0; i < 40; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 0), lam('#4a2f1c')); m.visible = false; R3.api.scene.add(m); blobs.push({ m, life: 0, vx: 0, vy: 0, vz: 0, r: 1 }); }
    };
    R3.onDraw = (S2, v, dt) => {
      S2.L.cans.forEach((c, i) => { if (canM[i]) { canM[i].visible = !c.got; canM[i].rotation.y = v.t * 1.6; } });
      const tr = R3.api.truck; // брёвна в кузове
      if (tr && logsOn !== tr) { logsOn = tr; for (const [y, z] of [[52, -26], [52, 0], [52, 26], [70, -13], [70, 13]]) R3.api.cyl(9, 112, 7, R3.api.lam(y > 60 ? '#8d6e63' : '#795548'), -50, y, z, tr).rotation.z = Math.PI / 2; }
      // брызги грязи из-под буксующих колёс
      blobAcc += dt;
      if (blobAcc > 0.03) { blobAcc = 0; S2.wheels.forEach((w, i) => { if (S2.slip[i] > 150 && S2.sunk[i] > 4 && Math.random() < 0.7) { const p = blobs[blobI++ % blobs.length]; p.life = 0.7; p.r = 4 + Math.random() * 6; p.vx = -(120 + Math.random() * 260) * Math.sign(w.w || 1); p.vy = 180 + Math.random() * 260; p.vz = (Math.random() - 0.5) * 220; p.m.position.set(w.x - 18, -(w.y + 10), (Math.random() - 0.5) * 90); p.m.visible = true; } }); }
      for (const p of blobs) if (p.life > 0) { p.life -= dt; if (p.life <= 0) { p.m.visible = false; continue; } p.vy -= 900 * dt; p.m.position.x += p.vx * dt; p.m.position.y += p.vy * dt; p.m.position.z += p.vz * dt; p.m.scale.setScalar(p.r); }
    };
  }

  // ---------- рисование поверх: приборы, кнопки, подсказки ----------
  const font = (px, w = 900) => { ctx.font = `${w} ${px}px system-ui, sans-serif`; };
  function label(t, x, y, px, col = '#fff', mw) { font(px); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round'; ctx.lineWidth = Math.max(4, px * 0.22); ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.strokeText(t, x, y, mw); ctx.fillStyle = col; ctx.fillText(t, x, y, mw); }
  function lines(t, mw, px) { font(px, 800); const out = []; let cur = ''; for (const w of t.split(' ')) { const q = cur ? cur + ' ' + w : w; if (ctx.measureText(q).width > mw && cur) { out.push(cur); cur = w; } else cur = q; } if (cur) out.push(cur); return out; }
  function bubble(t, y, col = 'rgba(0,0,0,0.5)') { const px = W < 430 ? 15 : 18, L = lines(t, Math.min(W - 40, 620), px), w = Math.min(W - 16, Math.max(...L.map((q) => ctx.measureText(q).width)) + 34), h = L.length * (px + 6) + 16; ctx.fillStyle = col; rr(W / 2 - w / 2, y, w, h, 16); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; L.forEach((q, i) => ctx.fillText(q, W / 2, y + 8 + (px + 6) * (i + 0.5), w - 20)); return h; }
  function btn(b, txt, col, on, sub) {
    ctx.globalAlpha = on ? 0.97 : 0.74; ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(b.x, b.y + 5, b.w, b.h, 16); ctx.fill(); ctx.fillStyle = col; rr(b.x, b.y + (on ? 3 : 0), b.w, b.h, 16); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; font(Math.round(Math.min(b.h * (sub ? 0.3 : 0.44), b.w * 0.36)));
    ctx.fillText(txt, b.x + b.w / 2, b.y + b.h * (sub ? 0.4 : 0.5) + (on ? 3 : 0), b.w - 8);
    if (sub) { font(Math.round(Math.min(13, b.h * 0.2)), 800); ctx.fillText(sub, b.x + b.w / 2, b.y + b.h * 0.76 + (on ? 3 : 0), b.w - 8); }
  }
  function hint(inp) { // что подсказать прямо сейчас
    if (S.state === 'dead') return [S.why === 'fuel' ? T.dFuel : S.why === 'water' ? T.dWater : T.dFlip, 'rgba(183,28,28,0.85)'];
    if (S.t < 6 && S.attempts === 1) return [T.goal];
    if (S.stuckT > 1.1) { const mud = S.inMud > 0; return [!sw.awd ? T.hAwd : mud && !sw.lock ? T.hLock : !sw.low ? T.hLow : mud && S.target ? T.hWinch : T.hBack, 'rgba(230,81,0,0.9)']; }
    if (S.fuel < 22) return [T.hFuel, 'rgba(183,28,28,0.8)'];
    if (offT > 2.5) return [T.hOff];
    void inp; return null;
  }
  function drawHud(inp) {
    layout();
    // топливо
    const fw = Math.min(210, W * 0.44), fx = 12, fy = 14, k = S.fuel / S.cfg.tank;
    ctx.fillStyle = 'rgba(0,0,0,0.4)'; rr(fx, fy, fw, 24, 12); ctx.fill(); ctx.fillStyle = k < 0.22 ? '#e53935' : k < 0.45 ? '#ffb300' : '#7cb342'; rr(fx + 3, fy + 3, Math.max(8, (fw - 6) * k), 18, 9); ctx.fill();
    font(13); ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText('⛽ ' + Math.round(k * 100) + '%', fx + 10, fy + 13);
    // колёса: серое — не ведёт, зелёное — держит, красное — буксует
    const wy = fy + 44, wx = fx + 8; font(12, 800); ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.fillText(T.wheels, wx + 64, wy + 1);
    ctx.fillStyle = 'rgba(0,0,0,0.35)'; rr(wx - 6, wy - 9, 56, 18, 9); ctx.fill();
    [0, 1].forEach((i) => { const drv = i === 0 || sw.awd, c = !drv ? '#90a4ae' : S.slip[i] > 150 || (inp.gas && S.stuckT > 0.4) ? '#ff5252' : '#69f0ae'; ctx.fillStyle = c; ctx.beginPath(); ctx.arc(wx + 8 + i * 28, wy, 7, 0, 7); ctx.fill(); });
    font(13, 800); ctx.textAlign = 'left'; ctx.fillStyle = '#fff'; ctx.fillText(`⏱ ${S.t.toFixed(0)} ${T.sec}`, fx + fw + 10, fy + 13);
    // кнопки
    const tr = S.target || S.rope;
    btn(B('gas'), '▶', '#43a047', inp.gas); btn(B('brake'), '◀', '#e53935', inp.brake);
    btn(B('winch'), '⚓', tr ? '#5c6bc0' : '#78909c', inp.winch, T.winch);
    btn(B('awd'), T.awd, sw.awd ? '#fb8c00' : '#546e7a', sw.awd); btn(B('lock'), T.lock, sw.lock ? '#fb8c00' : '#546e7a', sw.lock); btn(B('low'), T.low, sw.low ? '#fb8c00' : '#546e7a', sw.low);
    for (const [id, ch] of [['rescue', '↺'], ['mute', muted ? '🔇' : '🔊']]) { const b = B(id); ctx.fillStyle = 'rgba(0,0,0,0.34)'; rr(b.x, b.y, b.w, b.h, 12); ctx.fill(); ctx.fillStyle = '#fff'; font(22); ctx.textAlign = 'center'; ctx.fillText(ch, b.x + b.w / 2, b.y + b.h / 2 + 1); }
    // подсказка и короткие сообщения
    const h = hint(inp); let y = 78; if (h) y += bubble(h[0], y, h[1]) + 8;
    if (toast && realT - toast.t < 1.6) label(toast.s, W / 2, y + 22, 26, '#fff59d', W - 30);
    if (!matchMedia('(pointer: coarse)').matches && !ptrs.size && S.t < 14 && S.attempts === 1) { font(15, 800); const tw = Math.min(ctx.measureText(T.keys).width + 36, W - 16), ky = B('gas').y - 46; ctx.fillStyle = 'rgba(0,0,0,0.45)'; rr(W / 2 - tw / 2, ky, tw, 34, 17); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.fillText(T.keys, W / 2, ky + 17, tw - 24); }
  }
  function star5(x, y, r, col) { ctx.fillStyle = col; ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, q = i & 1 ? r * 0.45 : r; ctx.lineTo(x + Math.cos(a) * q, y + Math.sin(a) * q); } ctx.closePath(); ctx.fill(); }
  function drawWin() {
    ctx.fillStyle = 'rgba(10,40,70,0.45)'; ctx.fillRect(0, 0, W, H2);
    const w = Math.min(W - 28, 440), h = Math.min(H2 - 24, 330), x = W / 2 - w / 2, y = H2 / 2 - h / 2, k = S.fuel / S.cfg.tank, st = [true, S.rescues === 0, S.rescues === 0 && k >= 0.3];
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 22); ctx.fill();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#2e7d32'; font(28); ctx.fillText(T.win, W / 2, y + 40, w - 24);
    [T.s1, T.s2, T.s3].forEach((s, i) => { const cx = W / 2 + (i - 1) * w * 0.3; star5(cx, y + 108, i === 1 ? 40 : 33, st[i] ? '#ffc107' : '#cfd8dc'); ctx.fillStyle = '#546e7a'; font(13, 800); ctx.fillText(s, cx, y + 162, w * 0.29); });
    ctx.fillStyle = '#37474f'; font(17, 800); ctx.fillText(`${T.time}: ${S.t.toFixed(0)} ${T.sec}   ·   ${T.fuel}: ${Math.round(k * 100)}%`, W / 2, y + 204, w - 24);
    const b = { id: 'again', x: W / 2 - 100, y: y + h - 78, w: 200, h: 56 }; buttons = [b]; btn(b, '↻ ' + T.again, '#43a047', false);
  }

  // ---------- кадр ----------
  function frame(now) { try { frame1(now); } catch (e) { if (!frame.err) { frame.err = 1; try { console.error(e); } catch (q) { /* */ } } } requestAnimationFrame(frame); }
  function frame1(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now; realT += dt;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    let inp = { gas: false, brake: false, winch: false, awd: sw.awd, lock: sw.lock, low: sw.low };
    if (!dbg.freeze && !document.hidden) {
      if (mode === 'play') inp = input();
      acc += dt; let n = 0;
      while (acc >= P.DT && n < 10) { S.step(inp); acc -= P.DT; n++; }
      for (const e of S.events) { if (e.e === 'cp') { toast = { s: T.cp, t: realT }; tone(880, 0.12, 0.12); } else if (e.e === 'can') { toast = { s: T.can, t: realT }; tone(1040, 0.15, 0.12); } else if (e.e === 'dead') tone(160, 0.4, 0.15); else if (e.e === 'hook') tone(620, 0.06, 0.1); else if (e.e === 'win') { mode = 'win'; tone(1200, 0.3, 0.14); } }
      S.events.length = 0;
      // «выключи лишнее»: на твёрдой дороге со включёнными помощниками
      offT = S.state === 'play' && (sw.lock || sw.low) && !S.inMud && inp.gas && Math.abs(S.truck.a) < 0.12 && S.stuckT < 0.2 ? offT + dt : 0;
    }
    if (eng) { const on = mode === 'play' && S.state === 'play' && !muted && !document.hidden, rpm = Math.abs(S.wheels[0].w), t = AC.currentTime; eng.o.frequency.setTargetAtTime(48 + rpm * (sw.low ? 5.2 : 2.4) + (inp.gas ? 26 : 0), t, 0.08); eng.g.gain.setTargetAtTime(on ? (inp.gas ? 0.06 : 0.025) : 0, t, 0.1); }
    // камера: грузовик слева от середины, смотрим вперёд
    const port = W < H2, tr = S.truck, zt = port ? W / 900 : Math.min(W / 1500, H2 / 860);
    Z += (zt - Z) * Math.min(1, dt * 3);
    camX += (tr.x + (port ? 130 : 260) - camX) * Math.min(1, dt * 4); camY += (tr.y - 70 - camY) * Math.min(1, dt * 3);
    ctx.clearRect(0, 0, W, H2);
    if (use3d) R3.draw(S, { camX, camY, Z, W, H: H2, DPR, t: realT, lvl: 0, duo: false, shake: 0, gas: inp.gas && !S.inMud, oy: port ? 0.12 : 0.1, theme: 0 });
    if (mode === 'win' && S.wonT > 0.9) drawWin(); else drawHud(inp);
  }
  window.__mud = { S, sw, keys, dbg, get mode() { return mode; }, get buttons() { layout(); return buttons; }, again, flip };
  requestAnimationFrame(frame);
})();
