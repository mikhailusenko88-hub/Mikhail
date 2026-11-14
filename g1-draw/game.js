'use strict';
/* Игра 1: «Нарисуй путь — гонка стран». Соперники летят через штырьки, ты рисуешь свою дорогу к кубку. */
(function () {
  const C = window.Core, S = window.DRSim;
  const R = S.R;
  let w = null, phase = 'draw', line = [], drawing = false, inkUsed = 0, inkMax = 1000, inkOut = false;
  let showHint = false, endTimer = -1, endKind = null, pickups = 0, padOpen = 0, tutorialT = 0, fx = [], placeFx = null;
  let ox = 0, oy = 0;
  const clouds = Array.from({ length: 6 }, (_, i) => ({ x: Math.random() * 1400, y: 60 + i * 120, s: 0.6 + Math.random() * 0.8, v: 8 + Math.random() * 14 }));

  function layout() { ox = (C.W - S.LW) / 2; oy = Math.max(0, (C.H - 1280) / 2); }

  function newLevel(n) {
    w = S.makeLevel(n, Math.random);
    const rv = C.rivals(3);
    w.balls[0].skin = C.mySkin();
    for (let i = 1; i < w.balls.length; i++) w.balls[i].skin = rv[i - 1];
    phase = 'draw'; line = []; drawing = false; inkUsed = 0; inkMax = w.ink; inkOut = false;
    showHint = false; endTimer = -1; endKind = null; pickups = 0; padOpen = 0; tutorialT = 0; fx = []; placeFx = null;
  }

  function release() {
    if (line.length < 2) return;
    w.line = S.densify(line, 12);
    w.released = true; phase = 'race'; C.sfx('whoosh');
  }

  const game = {
    id: 'drawrace',
    hasSkip: true,
    reviveIcon: 'hint',
    init() { layout(); newLevel(C.save.level); },
    resize() { layout(); },
    startLevel(n) { newLevel(n); },
    revive() { newLevel(C.save.level); showHint = true; },
    toHome() { newLevel(C.save.level); },

    onDown(x, y) {
      if (C.state !== 'play' || phase !== 'draw' || inkOut) return;
      const lx = x - ox, ly = y - oy;
      if (ly < 120) return;
      drawing = true;
      if (line.length) { pushPoint(lx, ly); } else line.push([lx, ly]);
    },
    onMove(x, y) { if (drawing) pushPoint(x - ox, y - oy); },
    onUp() {
      if (!drawing) return; drawing = false;
      if (S.lineLength(line) < 40) { line = []; inkUsed = 0; return; }
      if (inkOut) { phase = 'choice'; return; }
      release();
    },

    update(dt) {
      for (const c of clouds) { c.x += c.v * dt; if (c.x > C.W + 200) c.x = -200; }
      tutorialT += dt;
      if (!w) return;
      if (C.state !== 'play' && C.state !== 'win' && C.state !== 'fail') return;
      if (w.released) padOpen = Math.min(1, padOpen + dt * 4);
      if (phase !== 'race' && phase !== 'end') return;
      S.step(w, dt);
      const p = w.balls[0];
      for (const e of w.events) {
        if (e.e === 'coin') { pickups++; C.sfx('coin'); C.burst(e.cn.x + ox, e.cn.y + oy, '#ffcf2e', 12, 300); }
        else if (e.e === 'pop') { C.sfx('pop'); C.burst(e.b.x + ox, e.b.y + oy, '#ff5252', 22, 500); }
        else if (e.e === 'hit') { if (e.b === p) C.sfx('bounce', e.k); }
        else if (e.e === 'tramp') C.sfx('gate');
        else if (e.e === 'finish') { C.sfx(e.b === p ? 'star' : 'tap', 2); C.burst(e.b.x + ox, e.b.y + oy, e.b === p ? '#ffd54f' : '#90caf9', 14, 350); if (e.b === p) placeFx = { place: e.b.place, t: 0 }; }
      }
      w.events.length = 0;
      for (const b of w.balls) { if (b.done) { b.slot = b.slot === undefined ? b.place - 1 : b.slot; } if (!b.done && !b.dead && !b.out) { (b.trail || (b.trail = [])).push([b.x, b.y]); if (b.trail.length > 12) b.trail.shift(); } else if (b.trail) b.trail.length = 0; }
      if (placeFx) placeFx.t += dt;
      if (phase === 'race') {
        const rivalsDone = w.balls.slice(1).filter((b) => b.done).length;
        if (p.done) { phase = 'end'; endKind = p.place <= 3 ? 'win' : 'fail'; endTimer = 1.0; }
        else if (p.dead || p.out) { phase = 'end'; endKind = 'fail'; endTimer = 0.9; }
        else if (p.still > 1.4 || w.t > 12 || rivalsDone >= 3) { phase = 'end'; endKind = 'fail'; endTimer = 0.6; }
      }
      if (phase === 'end' && C.state === 'play') {
        endTimer -= dt;
        if (endTimer <= 0) {
          if (endKind === 'win') { const stars = 4 - p.place; C.win({ stars, place: p.place, coins: 15 + stars * 10 + pickups * 5 }); }
          else C.fail({ revive: true });
        }
      }
    },

    draw(ctx) {
      layout();
      // небо
      const g = ctx.createLinearGradient(0, 0, 0, C.H); g.addColorStop(0, '#6ec6ff'); g.addColorStop(0.7, '#c9ecff'); g.addColorStop(1, '#e8f7ff');
      ctx.fillStyle = g; ctx.fillRect(0, 0, C.W, C.H);
      const sx = C.W * 0.82, sy = C.H * 0.08; const sg = ctx.createRadialGradient(sx, sy, 10, sx, sy, 160); sg.addColorStop(0, 'rgba(255,248,200,1)'); sg.addColorStop(0.25, 'rgba(255,236,150,0.8)'); sg.addColorStop(1, 'rgba(255,236,150,0)'); ctx.fillStyle = sg; ctx.beginPath(); ctx.arc(sx, sy, 160, 0, 7); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.75)';
      for (const c of clouds) { ctx.beginPath(); ctx.ellipse(c.x, c.y, 70 * c.s, 26 * c.s, 0, 0, 7); ctx.ellipse(c.x + 40 * c.s, c.y - 14 * c.s, 46 * c.s, 30 * c.s, 0, 0, 7); ctx.fill(); }
      ctx.fillStyle = '#c5e8c7'; ctx.beginPath(); ctx.ellipse(C.W * 0.6, C.H + 10, C.W * 0.7, 260, 0, 0, 7); ctx.fill();
      ctx.fillStyle = '#9ed6a1'; ctx.beginPath(); ctx.ellipse(C.W * 0.2, C.H + 40, C.W * 0.5, 170, 0, 0, 7); ctx.ellipse(C.W * 0.85, C.H + 60, C.W * 0.5, 200, 0, 0, 7); ctx.fill();
      if (!w) return;
      ctx.save(); ctx.translate(ox, oy);
      // поле игрока чуть подсвечено
      ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(0, 140, S.LW, 1140);
      // монеты
      for (const cn of w.coins) if (!cn.taken) { ctx.save(); ctx.translate(cn.x, cn.y); ctx.scale(Math.abs(Math.cos(C.realT * 3 + cn.x)) * 0.8 + 0.2, 1); C.icon('coin', 0, 0, 44); ctx.restore(); }
      // кубок
      drawCup(ctx, w.cup);
      // сегменты
      for (const s of w.segs) drawSeg(ctx, s);
      // подсказка
      if (showHint || (C.save.level === 1 && phase === 'draw' && !line.length && C.state === 'play')) drawHint(ctx, C.save.level === 1 && !showHint);
      // линия игрока
      if (line.length > 1) {
        ctx.lineCap = 'round'; ctx.lineJoin = 'round';
        ctx.strokeStyle = 'rgba(255,45,120,0.22)'; ctx.lineWidth = 40; strokePts(ctx, line);
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 22; strokePts(ctx, line);
        ctx.strokeStyle = '#ff2d78'; ctx.lineWidth = 14; strokePts(ctx, line);
      }
      // следы
      for (const b of w.balls) if (b.trail && b.trail.length > 1) for (let i = 0; i < b.trail.length; i++) { const k = i / b.trail.length; ctx.fillStyle = b.isPlayer ? 'rgba(255,45,120,' + k * 0.35 + ')' : 'rgba(255,255,255,' + k * 0.4 + ')'; ctx.beginPath(); ctx.arc(b.trail[i][0], b.trail[i][1], b.r * (0.4 + 0.5 * k), 0, 7); ctx.fill(); }
      // шарики
      for (const b of w.balls) {
        if (b.dead || b.out) continue;
        let x = b.x, y = b.y, r = b.r;
        if (b.done) { const sl = b.slot || 0; const tx = w.cup.cx - w.cup.half + 30 + sl * ((w.cup.half * 2 - 60) / 3), ty = w.cup.top + w.cup.depth - 30; b.sx += (tx - b.sx) * 0.15; b.sy += (ty - b.sy) * 0.15; x = b.sx; y = b.sy; r = b.r * 0.82; }
        C.drawBall(x, y, r, b.skin, b.ang, ctx, b.isPlayer ? 'rgba(255,255,255,0.9)' : null);
        if (b.done) { ctx.fillStyle = b.place === 1 ? '#ffc107' : b.place === 2 ? '#b0bec5' : b.place === 3 ? '#d7955b' : '#78909c'; ctx.beginPath(); ctx.arc(x, y - r - 18, 17, 0, 7); ctx.fill(); C.text(String(b.place), x, y - r - 17, 22, '#fff', 'center', null); }
      }
      // стрелка над своим шариком и пунктир: куда он упадёт без линии
      if (phase === 'draw' || phase === 'choice') {
        const p = w.balls[0]; const bob = Math.sin(C.realT * 6) * 8;
        if (!line.length) { ctx.save(); ctx.setLineDash([6, 14]); ctx.lineDashOffset = -C.realT * 40; ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(p.x, p.y + p.r + 14); ctx.lineTo(p.x, p.y + 260); ctx.stroke(); ctx.restore(); }
        ctx.fillStyle = '#ffeb3b'; ctx.strokeStyle = '#000'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(p.x - 18, p.y - 70 + bob); ctx.lineTo(p.x + 18, p.y - 70 + bob); ctx.lineTo(p.x, p.y - 44 + bob); ctx.closePath(); ctx.fill(); ctx.stroke();
      }
      // место игрока
      if (placeFx) {
        const k = C.easeOutBack(Math.min(1, placeFx.t / 0.4));
        ctx.save(); ctx.translate(S.LW / 2, 640); ctx.scale(k, k);
        C.text('#' + placeFx.place, 0, 0, 150, placeFx.place === 1 ? '#ffc107' : placeFx.place <= 3 ? '#ffffff' : '#ff5252');
        ctx.restore();
      }
      ctx.restore();
    },

    hud(ctx) {
      C.drawCoinsHud();
      // уровень
      ctx.fillStyle = 'rgba(0,0,0,0.35)'; C.rr(ctx, C.W / 2 - 60, 30, 120, 64, 32); ctx.fill();
      C.text(String(C.save.level), C.W / 2, 64, 40);
      if (C.state !== 'play') return;
      // чернила
      if (phase === 'draw' || phase === 'choice') {
        const bw = 300, bx = C.W / 2 - bw / 2 + 20, by = 112;
        C.icon('ink', bx - 34, by + 14, 40, '#ff2d78');
        ctx.fillStyle = 'rgba(0,0,0,0.3)'; C.rr(ctx, bx, by, bw, 28, 14); ctx.fill();
        const k = Math.max(0, 1 - inkUsed / inkMax);
        ctx.fillStyle = k < 0.2 ? '#ff5252' : '#ff2d78'; C.rr(ctx, bx + 3, by + 3, Math.max(0, (bw - 6) * k), 22, 11); ctx.fill();
      }
      // подсказка
      if ((phase === 'draw') && !showHint) {
        const free = C.save.hintFree > 0;
        if (free || C.rewardedSupported) {
          if (C.button('hint', C.W - 106, 130, 84, 84, { color: '#ffb300', icon: 'hint', iconSize: 46, badge: free, draw: free ? null : (c) => { C.icon('hint', -8, -4, 44); C.icon('ad', 20, 22, 28); } })) {
            if (free) { C.save.hintFree--; C.persist(); showHint = true; }
            else C.ads.rewarded('hint').then((ok) => { if (ok) showHint = true; });
          }
        }
      }
      // кончились чернила: поехали или ещё чернил за рекламу
      if (phase === 'choice') {
        const y = C.H - 260;
        if (C.button('go', C.W / 2 - 250, y, 220, 130, { color: '#43a047', icon: 'play', iconSize: 64 })) release();
        if (C.rewardedSupported && C.button('moreInk', C.W / 2 + 30, y, 220, 130, { color: '#ff2d78', pulse: true, draw: () => { C.icon('ad', -50, -2, 56); C.icon('ink', 30, -4, 50); C.icon('plus', 64, -26, 26); } })) {
          C.ads.rewarded('more_ink').then((ok) => { if (ok) { inkMax += Math.round(w.ink * 0.6); inkOut = false; phase = 'draw'; } });
        }
      }
    },
  };

  function pushPoint(x, y) {
    const lp = line[line.length - 1];
    const d = Math.hypot(x - lp[0], y - lp[1]);
    if (d < 9) return;
    const left = inkMax - inkUsed;
    if (left <= 0) { inkOut = true; return; }
    if (d > left) { const k = left / d; x = lp[0] + (x - lp[0]) * k; y = lp[1] + (y - lp[1]) * k; inkUsed = inkMax; line.push([x, y]); inkOut = true; return; }
    inkUsed += d; line.push([x, y]);
    if (Math.random() < 0.3) C.sfx('draw', Math.random());
  }
  function strokePts(ctx, pts) { ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]); ctx.stroke(); }

  function drawSeg(ctx, s) {
    ctx.lineCap = 'round';
    if (s.k === 'peg') {
      const cols = ['#ff7043', '#ab47bc', '#29b6f6', '#66bb6a', '#ffca28'];
      ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.beginPath(); ctx.arc(s.ax + 3, s.ay + 4, s.th / 2 + 2, 0, 7); ctx.fill();
      ctx.fillStyle = cols[Math.floor(s.ax + s.ay) % cols.length]; ctx.beginPath(); ctx.arc(s.ax, s.ay, s.th / 2 + 2, 0, 7); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.beginPath(); ctx.arc(s.ax - 3, s.ay - 3, 4, 0, 7); ctx.fill();
      return;
    }
    if (s.k === 'pad') {
      const po = s.owner === 0 || !w.released ? padOpen : (w.t >= w.rivalDelay ? Math.min(1, (w.t - w.rivalDelay) * 4) : 0);
      if (po >= 1) return;
      const cx = (s.ax + s.bx) / 2, hw = (s.bx - s.ax) / 2;
      ctx.save(); ctx.translate(s.ax, s.ay); ctx.rotate(po * 1.4);
      ctx.strokeStyle = '#8d5524'; ctx.lineWidth = s.th; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(hw * 2, 0); ctx.stroke();
      ctx.restore();
      void cx; return;
    }
    if (s.k === 'spike') {
      const dx = s.bx - s.ax, dy = s.by - s.ay, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L; let nx = uy, ny = -ux; if (ny > 0) { nx = -nx; ny = -ny; }
      const n = Math.max(1, Math.floor(L / 22));
      ctx.fillStyle = '#cfd8dc'; ctx.strokeStyle = '#455a64'; ctx.lineWidth = 2;
      for (let i = 0; i < n; i++) {
        const t0 = (i / n) * L, t1 = ((i + 1) / n) * L, tm = (t0 + t1) / 2;
        ctx.beginPath(); ctx.moveTo(s.ax + ux * t0, s.ay + uy * t0); ctx.lineTo(s.ax + ux * tm + nx * 24, s.ay + uy * tm + ny * 24); ctx.lineTo(s.ax + ux * t1, s.ay + uy * t1); ctx.closePath(); ctx.fill(); ctx.stroke();
      }
      return;
    }
    const col = s.k === 'tramp' ? '#ff9800' : '#3f51b5';
    ctx.strokeStyle = 'rgba(0,0,0,0.15)'; ctx.lineWidth = s.th; ctx.beginPath(); ctx.moveTo(s.ax + 3, s.ay + 5); ctx.lineTo(s.bx + 3, s.by + 5); ctx.stroke();
    ctx.strokeStyle = col; ctx.lineWidth = s.th; ctx.beginPath(); ctx.moveTo(s.ax, s.ay); ctx.lineTo(s.bx, s.by); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = Math.max(2, s.th * 0.25); ctx.beginPath(); ctx.moveTo(s.ax, s.ay - s.th * 0.2); ctx.lineTo(s.bx, s.by - s.th * 0.2); ctx.stroke();
  }

  function drawCup(ctx, c) {
    const x0 = c.cx - c.half, x1 = c.cx + c.half, y0 = c.top, y1 = c.top + c.depth;
    const g = ctx.createLinearGradient(x0, 0, x1, 0); g.addColorStop(0, '#ffe082'); g.addColorStop(0.5, '#fff8e1'); g.addColorStop(1, '#ffca28');
    ctx.fillStyle = 'rgba(255,193,7,0.25)'; ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = '#ffb300'; ctx.lineWidth = 18; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0, y1); ctx.lineTo(x1, y1); ctx.lineTo(x1, y0); ctx.stroke();
    ctx.strokeStyle = g; ctx.lineWidth = 8; ctx.stroke();
    // клетчатый флаг финиша
    const fx0 = x1 + 14, fy0 = y0 - 110;
    ctx.strokeStyle = '#5d4037'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(fx0, y0 + 10); ctx.lineTo(fx0, fy0); ctx.stroke();
    const wave = Math.sin(C.realT * 5) * 4;
    for (let i = 0; i < 4; i++) for (let j = 0; j < 3; j++) { ctx.fillStyle = (i + j) % 2 ? '#000' : '#fff'; ctx.fillRect(fx0 + 3 + i * 14, fy0 + j * 14 + (i * wave) / 4, 14, 14); }
  }

  function drawHint(ctx, tutorial) {
    const pts = S.densify(w.hint, 10);
    ctx.save(); ctx.setLineDash([18, 16]); ctx.lineDashOffset = -C.realT * 60; ctx.lineCap = 'round';
    ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 10; strokePts(ctx, pts); ctx.restore();
    if (tutorial) { // палец рисует путь
      const k = (tutorialT % 2.2) / 1.6; if (k <= 1) {
        const i = Math.min(pts.length - 1, Math.floor(k * (pts.length - 1))); const [x, y] = pts[i];
        ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.strokeStyle = '#333'; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.ellipse(x + 14, y + 26, 18, 26, -0.4, 0, 7); ctx.fill(); ctx.stroke();
        ctx.beginPath(); ctx.arc(x, y, 12, 0, 7); ctx.fillStyle = 'rgba(255,45,120,0.8)'; ctx.fill();
      }
    }
  }

  C.run(game);
})();
