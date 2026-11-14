'use strict';
/* Игра 5: «Фабрика шариков» — тайкун. Станок делает шарики, покраска во флаги, грузовик увозит и платит. */
(function () {
  const C = window.Core;
  const LW = 720;
  let ox = 0, oy = 0, sc = 1, top = 210, balls = [], spawnT = 0, tapCd = 0, truck = null, gearA = 0, boostT = 0, popup = null, golden = null, goldenT = 90, interT = 0, sinceInter = 0;
  const S = () => C.save.extra.f || (C.save.extra.f = { mach: 0, paint: 0, truck: 0, seen: 0, earned: 0 });

  // ---------- экономика ----------
  const interval = () => Math.max(0.22, 1.6 * Math.pow(0.86, S().mach));
  const collection = () => 1 + 0.05 * Object.keys(C.save.owned).length;
  const ballValue = () => Math.round(2 * Math.pow(1.38, S().paint) * collection() * 10) / 10;
  const beltSpeed = () => 170 * Math.pow(1.12, S().truck);
  const capacity = () => 8 + 2 * S().truck;
  const mult = () => (boostT > 0 ? 2 : 1);
  const rate = () => (ballValue() * mult()) / interval();
  const UPG = [
    { k: 'mach', icon: 'bolt', col: '#ff7043', base: 30, g: 1.55 },
    { k: 'paint', icon: 'coin', col: '#7e57c2', base: 50, g: 1.6 },
    { k: 'truck', icon: 'truck', col: '#26a69a', base: 40, g: 1.5 },
  ];
  const price = (u) => Math.round(u.base * Math.pow(u.g, S()[u.k]));
  const fmt = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e4 ? (n / 1e3).toFixed(1) + 'K' : n < 10 ? String(Math.round(n * 10) / 10) : String(Math.floor(n)));

  // ---------- сцена ----------
  const P = { mx: 130, my: 420, beltY: 470, beltX0: 190, beltX1: 560, painterX: 380, dropX: 585, truckY: 760 };
  function layout() { sc = C.clamp(Math.min(C.W / 740, (C.H - 660) / 620), 0.6, 1.2); top = 205 + Math.max(0, (C.H - 450 - 205 - 640 * sc) / 2); ox = C.W / 2 - 360 * sc; oy = top - 250 * sc; }
  const toL = (x, y) => [(x - C.W / 2) / sc + 360, (y - top) / sc + 250];

  function newTruck() { truck = { x: -260, state: 'arrive', load: 0, loadV: 0, t: 0 }; }
  function spawnBall() { balls.push({ x: P.mx + 40, y: P.beltY - 26, vy: 0, painted: false, skin: null, ang: 0, state: 'belt' }); }
  function flagPool() { const own = Object.keys(C.save.owned).filter((k) => C.FLAGS.some((f) => f.id === k)); return [C.mySkin(), C.homeCountry(), ...own, ...C.FLAGS.slice(0, 8 + S().paint * 2).map((f) => f.id)]; }

  function progressLevel() { const s = S(); C.save.level = 1 + Math.floor((s.mach + s.paint + s.truck) / 3); }

  const game = {
    id: 'factory',
    noPauseBtn: true,
    startState: 'play',
    init() {
      layout(); newTruck(); progressLevel();
      const s = S(), now = Date.now() / 1000;
      if (s.seen && now - s.seen > 60) {
        const away = Math.min(7200, now - s.seen); const amount = Math.floor(rate() * away * 0.25);
        if (amount > 0) popup = { kind: 'offline', amount, t0: C.now() };
      }
      s.seen = now; C.persist();
      setInterval(() => { S().seen = Date.now() / 1000; C.persist(); }, 15000);
    },
    resize() { layout(); },
    startLevel() {},
    onDown(x, y) {
      const [lx, ly] = toL(x, y);
      if (golden && Math.hypot(lx - golden.x, ly - golden.y) < 90) { const g = golden; golden = null; popup = { kind: 'golden', amount: Math.max(50, Math.floor(rate() * 60)), t0: C.now() }; void g; return; }
      if (Math.abs(lx - P.mx) < 140 && Math.abs(ly - P.my) < 160 && tapCd <= 0) { spawnBall(); tapCd = 0.12; C.sfx('pop'); C.burst(x, y, '#ffffff', 6, 200); }
    },

    update(dt) {
      gearA += dt * (2 + 3 / interval());
      if (C.state !== 'play') return;
      tapCd -= dt; boostT = Math.max(0, boostT - dt); sinceInter += dt;
      spawnT += dt; if (spawnT >= interval()) { spawnT = 0; spawnBall(); }
      // золотой грузовик-бонус
      goldenT -= dt;
      if (goldenT <= 0 && !golden && C.rewardedSupported) { golden = { x: -120, y: 250, t: 0 }; goldenT = 150; }
      if (golden) { golden.t += dt; golden.x += 110 * dt; golden.y = 250 + Math.sin(golden.t * 3) * 20; if (golden.x > LW + 150) golden = null; }
      // грузовик
      truck.t += dt;
      if (truck.state === 'arrive') { truck.x += (P.dropX - 150 - truck.x) * Math.min(1, dt * 4); if (Math.abs(truck.x - (P.dropX - 150)) < 3) truck.state = 'load'; }
      else if (truck.state === 'leave') {
        truck.x += 900 * dt;
        if (truck.x > LW + 300) { const pay = Math.round(truck.loadV); C.addCoins(pay, C.W - 120, C.H * 0.4); S().earned += pay; C.persist(); newTruck(); }
      }
      const sp = beltSpeed();
      for (let i = balls.length - 1; i >= 0; i--) {
        const b = balls[i];
        if (b.state === 'belt') {
          b.x += sp * dt; b.ang += (sp / 24) * dt;
          if (!b.painted && b.x >= P.painterX) { b.painted = true; b.skin = C.pick(flagPool()); C.burst(b.x * sc + ox, b.y * sc + oy, '#e1bee7', 6, 160); }
          const ahead = balls.find((q) => q !== b && q.state === 'belt' && q.x > b.x && q.x - b.x < 50); if (ahead) b.x = ahead.x - 50;
          if (b.x >= P.beltX1) { if (truck.state === 'load' && truck.load < capacity()) { b.state = 'fall'; b.vy = 0; } else b.x = P.beltX1; }
        } else if (b.state === 'fall') {
          b.vy += 2200 * dt; b.y += b.vy * dt; b.x += 60 * dt;
          if (b.y > P.truckY - 40) {
            balls.splice(i, 1); truck.load++; truck.loadV += ballValue() * mult(); C.sfx('coin');
            if (truck.load >= capacity()) { truck.state = 'leave'; C.sfx('whoosh'); }
          }
        }
      }
      if (balls.length > 60) balls.splice(0, balls.length - 60);
    },

    draw(ctx) {
      layout();
      const g = ctx.createLinearGradient(0, 0, 0, C.H); g.addColorStop(0, '#455a64'); g.addColorStop(0.55, '#607d8b'); g.addColorStop(0.56, '#8d6e63'); g.addColorStop(1, '#6d4c41');
      ctx.fillStyle = g; ctx.fillRect(0, 0, C.W, C.H);
      ctx.save(); ctx.translate(ox, oy); ctx.scale(sc, sc);
      // окна цеха
      for (let i = 0; i < 4; i++) { ctx.fillStyle = 'rgba(178,235,242,0.25)'; ctx.fillRect(40 + i * 170, 170, 120, 110); ctx.strokeStyle = 'rgba(255,255,255,0.3)'; ctx.lineWidth = 4; ctx.strokeRect(40 + i * 170, 170, 120, 110); }
      // вывеска с флагом игрока
      ctx.fillStyle = '#263238'; C.rr(ctx, LW / 2 - 110, 186, 220, 76, 18); ctx.fill();
      C.drawBall(LW / 2 - 60, 224, 28, C.mySkin(), 0, ctx); C.icon('coin', LW / 2 + 10, 224, 40); C.text(fmt(rate()) + '/s', LW / 2 + 70, 226, 30, '#ffeb3b', 'center', null);
      // конвейер
      ctx.fillStyle = '#37474f'; C.rr(ctx, P.beltX0 - 30, P.beltY, P.beltX1 - P.beltX0 + 60, 40, 20); ctx.fill();
      ctx.strokeStyle = '#90a4ae'; ctx.lineWidth = 4;
      const off = (C.realT * beltSpeed()) % 40;
      for (let x = P.beltX0 - 20 + off; x < P.beltX1 + 20; x += 40) { ctx.beginPath(); ctx.moveTo(x, P.beltY + 6); ctx.lineTo(x - 10, P.beltY + 34); ctx.stroke(); }
      for (let x = P.beltX0 - 10; x <= P.beltX1 + 10; x += 70) { ctx.fillStyle = '#263238'; ctx.beginPath(); ctx.arc(x, P.beltY + 52, 12, 0, 7); ctx.fill(); }
      // покрасочная арка
      ctx.fillStyle = '#7e57c2'; C.rr(ctx, P.painterX - 50, P.beltY - 130, 100, 30, 10); ctx.fill(); ctx.fillRect(P.painterX - 50, P.beltY - 110, 14, 110); ctx.fillRect(P.painterX + 36, P.beltY - 110, 14, 110);
      for (let i = 0; i < 5; i++) { ctx.fillStyle = ['#e53935', '#fdd835', '#1e88e5', '#43a047', '#fff'][i]; ctx.beginPath(); ctx.arc(P.painterX - 30 + i * 15 + Math.sin(C.realT * 9 + i) * 3, P.beltY - 90 + ((C.realT * 120 + i * 17) % 60), 4, 0, 7); ctx.fill(); }
      // станок
      ctx.save(); ctx.translate(P.mx, P.my);
      ctx.fillStyle = '#ff7043'; C.rr(ctx, -80, -110, 160, 170, 22); ctx.fill(); ctx.fillStyle = '#d84315'; C.rr(ctx, -80, 30, 160, 30, 10); ctx.fill();
      ctx.fillStyle = '#ffccbc'; ctx.beginPath(); ctx.moveTo(-60, -110); ctx.lineTo(60, -110); ctx.lineTo(30, -150); ctx.lineTo(-30, -150); ctx.fill();
      ctx.save(); ctx.translate(0, -40); ctx.rotate(gearA); ctx.fillStyle = '#ffe0b2'; for (let i = 0; i < 8; i++) { ctx.rotate(Math.PI / 4); ctx.fillRect(-8, -42, 16, 18); } ctx.beginPath(); ctx.arc(0, 0, 30, 0, 7); ctx.fill(); ctx.fillStyle = '#ff7043'; ctx.beginPath(); ctx.arc(0, 0, 12, 0, 7); ctx.fill(); ctx.restore();
      ctx.restore();
      // подсказка «тапай по станку»
      if (S().earned < 30) { const k = (C.realT * 1.5) % 1; ctx.strokeStyle = 'rgba(255,255,255,' + (1 - k) + ')'; ctx.lineWidth = 8; ctx.beginPath(); ctx.arc(P.mx, P.my - 40, 70 + k * 70, 0, 7); ctx.stroke(); }
      // шарики
      for (const b of balls) C.drawBall(b.x, b.y, 24, b.painted ? b.skin : 'white', b.ang, ctx);
      // грузовик
      drawTruck(ctx, truck.x, P.truckY);
      // золотой бонус
      if (golden) { ctx.save(); ctx.translate(golden.x, golden.y); ctx.shadowColor = '#ffd54f'; ctx.shadowBlur = 30; ctx.fillStyle = '#ffca28'; C.rr(ctx, -70, -40, 140, 70, 16); ctx.fill(); ctx.shadowBlur = 0; C.icon('truck', 0, -4, 90, '#fff8e1'); C.icon('ad', 50, -40, 40); ctx.restore(); }
      ctx.restore();
    },

    hud(ctx) {
      C.drawCoinsHud(); C.sideButtons(22, 112, true); C.soundButton(C.W - 106, 30);
      // ×2 дохода за рекламу
      const by = C.H - 430;
      if (C.rewardedSupported) {
        const label = boostT > 0 ? Math.floor(boostT / 60) + ':' + String(Math.floor(boostT % 60)).padStart(2, '0') : '';
        if (C.button('x2', C.W / 2 - 170, by, 340, 110, { color: boostT > 0 ? '#2e7d32' : '#43a047', pulse: boostT <= 0, draw: () => { C.icon('ad', -100, -2, 56); C.text('×2', -10, 0, 50); C.icon('clock', 70, -2, 40); if (label) C.text(label, 70, 34, 22); } })) {
          if (boostT < 1800) C.ads.rewarded('income_x2').then((ok) => { if (ok) { boostT = Math.min(1800, boostT + 180); C.sfx('buy'); } });
        }
      }
      // улучшения
      const bw = 210, gap = 15, x0 = C.W / 2 - (bw * 3 + gap * 2) / 2, y = C.H - 290;
      UPG.forEach((u, i) => {
        const p = price(u), short = C.save.coins < p, canAd = short && C.rewardedSupported && C.save.coins >= p * 0.5;
        if (C.button('fu_' + u.k, x0 + i * (bw + gap), y, bw, 220, { color: short && !canAd ? C.shade(u.col, 0.75) : u.col, draw: () => {
          C.icon(u.icon, 0, -56, 70, '#fff'); C.text(String(S()[u.k] + 1), 0, 0, 40);
          if (canAd) { C.icon('ad', -40, 60, 44); C.icon('up', 30, 60, 40); } else { C.icon('coin', -56, 60, 38); C.text(fmt(p), 16, 62, 34, short ? '#ffcdd2' : '#fff'); }
        } })) {
          if (C.spend(p)) { S()[u.k]++; progressLevel(); C.persist(); C.sfx('buy'); }
          else if (canAd) C.ads.rewarded('upgrade').then((ok) => { if (ok) { S()[u.k]++; progressLevel(); C.persist(); C.sfx('buy'); } });
          else { C.sfx('hit'); C.toast('coin', fmt(p - C.save.coins)); }
          maybeInter();
        }
      });
      // свои окна: офлайн-доход и золотой грузовик
      if (popup) drawPopup(ctx);
    },
    drawShopBg() {},
  };

  function maybeInter() { if (sinceInter > 180 && C.ads.canInter()) { sinceInter = 0; C.ads.interstitial('upgrade_pause'); } }

  function drawPopup(ctx) {
    const t = C.now() - popup.t0;
    ctx.fillStyle = 'rgba(0,0,0,0.55)'; ctx.fillRect(0, 0, C.W, C.H); C.UI.block();
    const k = C.easeOutBack(Math.min(1, t / 0.35)), pw = 600, ph = 560, px = C.W / 2 - pw / 2, py = C.H / 2 - ph / 2;
    ctx.save(); ctx.translate(C.W / 2, C.H / 2); ctx.scale(k, k); ctx.translate(-C.W / 2, -C.H / 2);
    C.panel(px, py, pw, ph, '#fff8e1');
    if (popup.kind === 'offline') { C.icon('clock', C.W / 2 - 80, py + 110, 110, '#8d6e63'); C.icon('coin', C.W / 2 + 60, py + 110, 110); }
    else { C.icon('truck', C.W / 2, py + 110, 160, '#ffb300'); }
    C.icon('coin', C.W / 2 - 90, py + 250, 70); C.text('+' + fmt(popup.amount), C.W / 2 + 30, py + 252, 64, '#ff9800');
    ctx.restore();
    const take = (m) => { C.addCoins(popup.amount * m, C.W / 2, py + 250); popup = null; };
    const m = popup.kind === 'offline' ? 3 : 5;
    if (C.rewardedSupported && !popup.busy && C.button('pmul', C.W / 2 - 200, py + 320, 400, 116, { color: '#43a047', ad: true, label: '×' + m, pulse: true })) {
      popup.busy = true; C.ads.rewarded(popup.kind === 'offline' ? 'offline_x3' : 'golden_x5').then((ok) => { if (popup) popup.busy = false; if (ok) take(m); });
    }
    if (popup && !popup.busy && t > 1.2 && popup.kind === 'offline' && C.button('p1', C.W / 2 - 80, py + 455, 160, 90, { color: '#90a4ae', icon: 'check', iconSize: 44 })) take(1);
    if (popup && !popup.busy && t > 1.2 && popup.kind === 'golden' && C.button('p0', C.W / 2 - 80, py + 455, 160, 90, { color: '#90a4ae', icon: 'close', iconSize: 40 })) popup = null;
  }

  function drawTruck(ctx, x, y) {
    ctx.save(); ctx.translate(x, y);
    ctx.fillStyle = '#26a69a'; C.rr(ctx, 0, -70, 200, 90, 12); ctx.fill();
    ctx.fillStyle = '#00796b'; C.rr(ctx, 196, -50, 80, 70, 14); ctx.fill();
    ctx.fillStyle = '#b2ebf2'; C.rr(ctx, 230, -40, 36, 28, 6); ctx.fill();
    const cap = capacity(), k = truck.load / cap;
    ctx.fillStyle = 'rgba(0,0,0,0.25)'; C.rr(ctx, 14, -56, 172, 18, 9); ctx.fill(); ctx.fillStyle = '#ffeb3b'; C.rr(ctx, 16, -54, 168 * k, 14, 7); ctx.fill();
    for (let i = 0; i < Math.min(truck.load, 12); i++) C.drawBall(30 + (i % 6) * 28, -18 - Math.floor(i / 6) * 22, 13, C.FLAGS[(i * 7) % C.FLAGS.length].id, 0, ctx);
    ctx.fillStyle = '#212121'; for (const wx of [40, 150, 240]) { ctx.beginPath(); ctx.arc(wx, 24, 22, 0, 7); ctx.fill(); ctx.fillStyle = '#9e9e9e'; ctx.beginPath(); ctx.arc(wx, 24, 9, 0, 7); ctx.fill(); ctx.fillStyle = '#212121'; }
    ctx.restore();
  }

  window.__dbg = () => ({ S: S(), rate: rate(), balls: balls.length, truck, boostT, popup });
  C.run(game);
})();
