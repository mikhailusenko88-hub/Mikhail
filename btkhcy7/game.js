'use strict';
/* Игра 6 (под Poki): «Шар в кузове» — довези шарик своей страны до финиша. Газ / тормоз, физика, короткие уровни. */
(function () {
  const C = window.Core, P = window.TPhys;
  const L10N = {
    en: { lv: 'Level', hint: 'Hold ▶ to drive, ◀ to brake', hint2: "Don't drop the ball!", cp: 'Checkpoint!', lost: 'The ball fell out!', crash: 'Crash!', fell: 'Fell down!', star: 'Star!' },
    ru: { lv: 'Уровень', hint: 'Держи ▶ — газ, ◀ — тормоз', hint2: 'Не урони шарик!', cp: 'Чекпоинт!', lost: 'Шарик выпал!', crash: 'Авария!', fell: 'Упал!', star: 'Звезда!' },
    es: { lv: 'Nivel', hint: 'Mantén ▶ para avanzar, ◀ para frenar', hint2: '¡No dejes caer la pelota!', cp: '¡Control!', lost: '¡Se cayó la pelota!', crash: '¡Choque!', fell: '¡Caíste!', star: '¡Estrella!' },
    pt: { lv: 'Nível', hint: 'Segure ▶ para acelerar, ◀ para frear', hint2: 'Não deixe a bola cair!', cp: 'Checkpoint!', lost: 'A bola caiu!', crash: 'Batida!', fell: 'Caiu!', star: 'Estrela!' },
    de: { lv: 'Level', hint: '▶ halten = Gas, ◀ = Bremse', hint2: 'Lass den Ball nicht fallen!', cp: 'Checkpoint!', lost: 'Der Ball ist rausgefallen!', crash: 'Unfall!', fell: 'Abgestürzt!', star: 'Stern!' },
    fr: { lv: 'Niveau', hint: 'Maintiens ▶ pour avancer, ◀ pour freiner', hint2: 'Ne fais pas tomber la balle !', cp: 'Checkpoint !', lost: 'La balle est tombée !', crash: 'Accident !', fell: 'Chute !', star: 'Étoile !' },
    tr: { lv: 'Seviye', hint: 'Gaz için ▶, fren için ◀ basılı tut', hint2: 'Topu düşürme!', cp: 'Kontrol noktası!', lost: 'Top düştü!', crash: 'Kaza!', fell: 'Düştün!', star: 'Yıldız!' },
  };
  let T = L10N.en;

  // ---------- трассы ----------
  function Track() {
    const S = { polys: [], planks: [], movers: [], seesaws: [], star: null, cp: null, fin: 0, minY: 1e9, maxY: -1e9 };
    let x = 0, y = 600, cur = null;
    const push = (px, py) => { cur.push([px, py]); S.minY = Math.min(S.minY, py); S.maxY = Math.max(S.maxY, py); };
    const B = {
      S,
      get x() { return x; }, get y() { return y; },
      start(x0, y0) { x = x0; y = y0; cur = []; push(x, y); return B; },
      flat(len) { x += len; push(x, y); return B; },
      line(dx, dy) { x += dx; y += dy; push(x, y); return B; },
      slope(len, up, n = 12) { const x0 = x, y0 = y; for (let i = 1; i <= n; i++) { const t = i / n, s = t * t * (3 - 2 * t); push(x0 + len * t, y0 - up * s); } x = x0 + len; y = y0 - up; return B; },
      hill(len, h, n = 14) { const x0 = x; for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y - h * (0.5 - 0.5 * Math.cos(t * Math.PI * 2))); } x = x0 + len; return B; },
      bumps(len, k, h) { for (let i = 0; i < k; i++) B.hill(len / k, h, 8); return B; },
      // трамплин: изгиб, потом прямой край по касательной — машина уходит в прыжок без закрутки
      ramp(len, h, n = 10) { const x0 = x, y0 = y; for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y0 - h * t * t); } const k = (2 * h) / len, L = 80; x = x0 + len + L; y = y0 - h - k * L; push(x, y); return B; },
      gap(dx, dy = 0) { S.polys.push(cur); x += dx; y += dy; cur = []; push(x, y); return B; },
      star(dx, dy) { S.star = { x: x + dx, y: y + dy, got: false }; return B; },
      cp(dx = 0) { S.cp = { x: x + dx, y }; return B; },
      plank(x0, y0, x1, y1) { S.planks.push([x0, y0, x1, y1]); S.minY = Math.min(S.minY, y0, y1); S.maxY = Math.max(S.maxY, y0, y1); return B; },
      mover(o) { S.movers.push(o); return B; },
      seesaw(o) { S.seesaws.push(o); return B; },
      fin(dx = 150) { S.fin = x + dx; return B; },
      end(len = 1700) { B.flat(len); S.polys.push(cur); cur = null; return B; },
    };
    return B;
  }

  const LEVELS = [
    // 1 — знакомство: холмы
    () => { const b = Track().start(-300, 600).flat(800).hill(520, 60).flat(220); b.cp(0).star(350, -230).hill(700, 120).flat(300).bumps(600, 3, 22).flat(300).fin().end(); return b.S; },
    // 2 — первый прыжок
    () => { const b = Track().start(-300, 600).flat(900).slope(500, 90).flat(160).ramp(240, 50); b.gap(300, 60).star(-150, -250).slope(500, -110).flat(300).cp(0).hill(500, 70).flat(300).fin().end(); return b.S; },
    // 3 — кочки: шарик подпрыгивает
    () => { const b = Track().start(-300, 600).flat(700).bumps(1500, 10, 26).flat(260).cp(0).star(450, -200).bumps(900, 4, 56).flat(300).fin().end(); return b.S; },
    // 4 — крутой подъём и спуск: тормози
    () => { const b = Track().start(-300, 600).flat(700).slope(820, 260).flat(260).star(130, -150).cp(0).slope(950, -400).flat(350).hill(420, 50).flat(260).fin().end(); return b.S; },
    // 5 — платформа над ямой
    () => {
      const b = Track().start(-300, 600).flat(900); const ex = b.x, ey = b.y;
      b.gap(700, 0).cp(80).flat(500).star(200, -170).hill(480, 70).flat(300).fin().end();
      b.mover({ len: 330, x0: ex + 10 + 165, y0: ey, x1: ex + 700 - 10 - 165, y1: ey, T: 4.2 });
      b.S.star.x = ex + 350; b.S.star.y = ey - 200;
      return b.S;
    },
    // 6 — качели
    () => {
      const b = Track().start(-300, 600).flat(800).slope(300, 60).flat(200); const ex = b.x, ey = b.y;
      b.gap(620, 0).cp(60).flat(500).star(250, -160).bumps(500, 3, 30).flat(250).fin().end();
      b.seesaw({ x: ex + 310, lip: ey, len: 740, tilt: 0.2 });
      return b.S;
    },
    // 7 — мостик из досок
    () => {
      const b = Track().start(-300, 600).flat(800); const ex = b.x, ey = b.y;
      b.gap(980, -40).cp(60).flat(500).hill(500, 90).flat(300).fin().end();
      const pts = [[ex + 8, ey], [ex + 210, ey - 34], [ex + 420, ey - 52], [ex + 630, ey - 52], [ex + 840, ey - 34], [ex + 972, ey - 40]];
      for (let i = 1; i < pts.length; i++) b.plank(pts[i - 1][0] + (i > 1 ? 14 : 0), pts[i - 1][1], pts[i][0] - 14, pts[i][1]);
      b.S.star = { x: ex + 525, y: ey - 200, got: false };
      return b.S;
    },
    // 8 — большой прыжок с горы
    () => {
      const b = Track().start(-300, 300).flat(600).slope(900, -320).flat(220).ramp(300, 90);
      b.star(220, -200).gap(380, 90).slope(600, -160).flat(300).cp(0).hill(520, 80).flat(300).fin().end();
      return b.S;
    },
  ];
  // уровни после ручных: собираются из кусков, сложность растёт
  function procLevel(n) {
    const r = C.seeded(1000 + n * 77), d = Math.min(1, (n - 8) / 22);
    const b = Track().start(-300, 600).flat(800);
    const parts = 5 + Math.floor(r() * 3) + Math.floor(d * 3);
    for (let i = 0; i < parts; i++) {
      const k = Math.floor(r() * 7);
      if (i === Math.floor(parts / 2)) b.cp(0);
      if (k === 0) b.hill(450 + r() * 300, 50 + r() * (60 + 80 * d));
      else if (k === 1) b.bumps(600 + r() * 500, 3 + Math.floor(r() * 4), 20 + r() * (20 + 30 * d));
      else if (k === 2) b.slope(500 + r() * 300, 120 + r() * 160 * (0.5 + d)).flat(150);
      else if (k === 3) b.slope(600 + r() * 300, -(150 + r() * 200 * (0.5 + d))).flat(200);
      else if (k === 4) { b.flat(200).ramp(240, 50 + r() * 30); const w = 260 + r() * 200 * (0.4 + d); if (i === 1 && !b.S.star) b.star(w / 2, -220); b.gap(w, 40 + r() * 40).slope(400, -90).flat(200); }
      else if (k === 5) { const ex = b.x, ey = b.y, w = 600 + r() * 200; b.gap(w, 0).flat(250); b.mover({ len: 320, x0: ex + 170, y0: ey, x1: ex + w - 170, y1: ey, T: 3.6 + r() * 1.5 }); }
      else { const ex = b.x, ey = b.y, w = 560 + r() * 120; b.gap(w, 0).flat(250); b.seesaw({ x: ex + w / 2, lip: ey, len: w + 120, tilt: 0.2 }); }
      b.flat(150);
    }
    if (!b.S.star) b.star(-300, -200);
    b.flat(200).fin().end();
    return b.S;
  }

  // ---------- мир уровня ----------
  let W = null, L = null, truck = null, ball = null, wheels = [], wj = [], movers = [], seesaws = [];
  let tm = 0, state = 'play', failT = 0, failWhy = '', crashT = 0, flipT = 0, outT = 0, inBed = true, grounded = false, wonT = 0;
  let gasIn = false, brkIn = false, touch = null, camX = 0, camY = 0, Z = 0.8, shake = 0, toastL = [], hintT = 0, cpReached = null, startX = 0, startY = 0, partsFx = [];
  let lastLevel = 1, parT = 30, simAcc = 0;

  function build(n) {
    lastLevel = n;
    L = (n <= LEVELS.length ? LEVELS[n - 1] : () => procLevel(n))();
    W = P.world(); movers = []; seesaws = [];
    for (const poly of L.polys) {
      for (let i = 1; i < poly.length; i++) P.addStatic(W, poly[i - 1][0], poly[i - 1][1], poly[i][0], poly[i][1]);
      // стенки ям: край обрыва — твёрдый
      const a = poly[0], z = poly[poly.length - 1];
      P.addStatic(W, a[0], a[1], a[0], a[1] + 1600); P.addStatic(W, z[0], z[1], z[0], z[1] + 1600);
    }
    // невидимые стены в начале и в конце уровня — назад с трассы не уехать
    { const a = L.polys[0][0], lp = L.polys[L.polys.length - 1], z = lp[lp.length - 1]; P.addStatic(W, a[0], a[1], a[0], a[1] - 3000); P.addStatic(W, z[0], z[1], z[0], z[1] - 3000); }
    for (const p of L.planks) { P.addStatic(W, p[0], p[1], p[2], p[3], 0.95); P.addStatic(W, p[0], p[1] + 20, p[2], p[3] + 20); P.addStatic(W, p[0], p[1], p[0], p[1] + 20); P.addStatic(W, p[2], p[3], p[2], p[3] + 20); }
    for (const m of L.movers) {
      const b = P.addBody(W, P.body({ dyn: false, x: m.x0, y: m.y0, segs: [[-m.len / 2, 0, m.len / 2, 0], [-m.len / 2, 22, m.len / 2, 22], [-m.len / 2, 0, -m.len / 2, 22], [m.len / 2, 0, m.len / 2, 22]], rad: m.len / 2 + 40, mu: 0.95, group: 'obj', kind: 'mover' }));
      b.m0 = m; movers.push(b);
    }
    for (const s of L.seesaws) {
      // ось над ямой; в начале доска лежит левым концом на краю ямы (наклон tilt), правый конец поднят
      const h = s.len / 2, m = 5, th = 11, py = s.lip - th - h * Math.sin(s.tilt);
      const b = P.addBody(W, P.body({ x: s.x, y: py, a: -s.tilt, m, I: (m * s.len * s.len) / 12, segs: [[-h, -th, h, -th], [-h, th, h, th], [-h, -th, -h, th], [h, -th, h, th]], circles: [{ x: -h + th, y: 0, r: th }, { x: h - th, y: 0, r: th }], rad: h + 60, mu: 0.95, group: 'obj', kind: 'seesaw', ang: 0.995 }));
      P.pinJoint(W, b, 0, 0, s.x, py); b.pivotY = py;
      seesaws.push(b);
    }
    parT = Math.round(L.fin / 520 + 4);
    const sp = L.polys[0][0]; startX = sp[0] + 300; startY = sp[1];
    cpReached = null; tm = 0;
    spawn(startX, startY);
  }

  function groundAt(x) {
    let best = null;
    for (const poly of L.polys) for (let i = 1; i < poly.length; i++) { const a = poly[i - 1], b = poly[i]; if (x >= a[0] && x <= b[0]) { const t = (x - a[0]) / (b[0] - a[0] || 1), y = a[1] + (b[1] - a[1]) * t; if (best === null || y < best) best = y; } }
    return best === null ? 600 : best;
  }

  function spawn(x, gy) {
    // убрать старые тела грузовика и шарика
    W.bodies = W.bodies.filter((b) => b.kind === 'mover' || b.kind === 'seesaw');
    W.joints = W.joints.filter((j) => j.t === 'pin');
    const y = gy - 82;
    truck = P.addBody(W, P.body({
      x, y, m: 8, I: 34000, group: 'truck', kind: 'truck', only: 'ball', rad: 190, mu: 0.6, lin: 0.9997, ang: 0.997,
      circles: [
        { x: -100, y: 14, r: 13 }, { x: 102, y: 12, r: 13 }, { x: 110, y: -10, r: 10 },
        { x: -106, y: -34, r: 8 }, { x: 70, y: -62, r: 13, crash: true }, { x: 30, y: -66, r: 13, crash: true },
      ],
      segs: [[-106, -6, 14, -6], [-111, -6, -111, -46], [16, -6, 16, -74], [16, -74, 70, -74]],
    }));
    wheels = []; wj = [];
    for (const [lx, side] of [[-72, 0], [72, 1]]) {
      const w = P.addBody(W, P.body({ x: x + lx, y: y + 18 + 30, m: 1.2, I: 440, group: 'truck', kind: 'wheel', mu: 1.0, circles: [{ x: 0, y: 0, r: 27, wheel: side }], ang: 0.999 }));
      wheels.push(w);
      wj.push(P.wheelJoint(W, truck, w, { lx, ly: 18, rest: 34, k: 1150, c: 70, lo: 10, hi: 44 }));
    }
    ball = P.addBody(W, P.body({ x: x - 48, y: y - 46, m: 1.0, I: 580, kind: 'ball', group: 'ball', mu: 0.7, e: 0.32, circles: [{ x: 0, y: 0, r: BR }], ang: 0.998 }));
    state = 'play'; failT = 0; crashT = 0; flipT = 0; outT = 0; inBed = true; wonT = 0; shake = 0;
    camX = x + 200; camY = y;
  }

  // ---------- управление ----------
  const keyGas = () => !!(C.keys.ArrowRight || C.keys.KeyD || C.keys.ArrowUp || C.keys.KeyW);
  const keyBrk = () => !!(C.keys.ArrowLeft || C.keys.KeyA || C.keys.ArrowDown || C.keys.KeyS);

  function control(dt) {
    const g = state === 'play' && (gasIn || keyGas() || touch === 'gas' || window.__autoGas);
    const br = state === 'play' && !g && (brkIn || keyBrk() || touch === 'brake' || window.__autoBrk);
    const [fx, fy] = P.wvec(truck, 1, 0), fwd = truck.vx * fx + truck.vy * fy;
    const up = C.save.extra.tu || {};
    const top = 36 + (up.eng || 0) * 2.5, tq = 215000 + (up.eng || 0) * 15000;
    for (const j of wj) {
      j.brake = 0;
      if (state !== 'play') { j.brake = state === 'win' ? 160000 : 0; j.maxT = 0; continue; }
      if (g) { j.speed = top; j.maxT = grounded ? tq : tq * 0.2; }
      else if (br) { if (fwd > 70) { j.brake = 230000; j.maxT = 0; } else { j.speed = -16; j.maxT = 110000; } }
      else { j.speed = 0; j.maxT = 3500; }
    }
    // в воздухе газ поднимает нос, тормоз опускает
    if (!grounded && state === 'play') {
      const k = g ? -1 : br ? 1 : 0;
      if (k) { truck.w += k * 4.2 * dt; truck.w = C.clamp(truck.w, -3.2, 3.2); }
      else truck.w *= 1 - 2.2 * dt; // отпустил — вращение гаснет: прощает новичку
    }
    // кинематические платформы
    for (const m of movers) {
      const o = m.m0, ph = (tm % o.T) / o.T, s = 0.5 - 0.5 * Math.cos(ph * Math.PI * 2);
      const nx = o.x0 + (o.x1 - o.x0) * s, ny = o.y0 + (o.y1 - o.y0) * s;
      const ph2 = ((tm + dt) % o.T) / o.T, s2 = 0.5 - 0.5 * Math.cos(ph2 * Math.PI * 2);
      const tx = o.x0 + (o.x1 - o.x0) * s2, ty = o.y0 + (o.y1 - o.y0) * s2;
      m.x = nx; m.y = ny; m.vx = (tx - nx) / dt; m.vy = (ty - ny) / dt;
    }
  }

  let bumpCD = 0;
  function afterStep() {
    bumpCD -= P.DT;
    if (bumpCD <= 0) for (const k of W.touch) {
      const hard = k.vn0 < -260;
      if (hard && (k.A.kind === 'ball' || k.A.kind === 'wheel')) { C.sfx(k.A.kind === 'ball' ? 'bounce' : 'hit', 0.5); bumpCD = 0.18; if (k.A.kind === 'wheel' && k.vn0 < -700) shake = Math.max(shake, 0.15); break; }
    }
    // касания: колёса на земле, крыша об землю
    grounded = false; let roof = false;
    for (const k of W.touch) {
      if (k.A.kind === 'wheel') grounded = true;
      if (k.A === truck && k.tagA && k.tagA.crash) roof = true;
    }
    if (state !== 'play') return;
    crashT = roof ? crashT + P.DT : 0;
    const up = Math.cos(truck.a);
    flipT = up < -0.2 && !grounded ? flipT + P.DT : up < 0 ? flipT + P.DT : 0;
    const [lx, ly] = P.local(truck, ball.x, ball.y);
    inBed = lx > -128 && lx < 34 && ly > -175 && ly < 14;
    outT = inBed ? 0 : outT + P.DT;
    if (crashT > 0.12 || flipT > 1.6) fail('crash');
    else if (outT > 0.7 || ball.y > L.maxY + 900) fail('lost');
    else if (truck.y > L.maxY + 800) fail('fell');
    // звезда, чекпоинт, финиш
    const st = L.star;
    if (st && !st.got && (Math.hypot(st.x - truck.x, st.y - truck.y) < 110 || Math.hypot(st.x - ball.x, st.y - ball.y) < 70)) { st.got = true; C.sfx('star', 2); toastL.push({ t: 0, text: T.star, col: '#ffd54f' }); fxBurst(st.x, st.y, '#ffd54f'); }
    if (L.cp && !cpReached && truck.x > L.cp.x) { cpReached = { x: L.cp.x, y: groundAt(L.cp.x) }; C.sfx('coin'); toastL.push({ t: 0, text: T.cp, col: '#69f0ae' }); }
    if (truck.x > L.fin && inBed) win();
  }

  function fail(why) {
    if (state !== 'play') return;
    state = 'dead'; failWhy = why; failT = 0; shake = why === 'crash' ? 0.5 : 0.2;
    C.sfx('crash'); toastL.push({ t: 0, text: why === 'lost' ? T.lost : why === 'fell' ? T.fell : T.crash, col: '#ff8a80' });
    if (why === 'crash') fxBurst(truck.x, truck.y - 40, '#ffab40');
  }
  function win() {
    state = 'win'; wonT = 0;
    const stars = 1 + (L.star && L.star.got ? 1 : 0) + (tm <= parT ? 1 : 0);
    fxBurst(L.fin, groundAt(L.fin) - 140, '#fff176');
    setTimeout(() => { if (C.state === 'play') C.win({ stars, coins: 10 + stars * 10 }); }, 700);
  }
  function fxBurst(x, y, col) { for (let i = 0; i < 18; i++) { const a = Math.random() * 6.28, s = 150 + Math.random() * 380; partsFx.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 200, t: 0, col, r: 5 + Math.random() * 6 }); } }

  // ---------- рисование ----------
  const BR = 35; // радиус шарика
  const TRUCK = { main: '#ff5a36', dark: '#c63b1f', light: '#ff8a65', frame: '#37474f' };
  const sx = (x) => (x - camX) * Z + C.W * (C.W > C.H ? 0.4 : 0.36), sy = (y) => (y - camY) * Z + C.H * (C.W > C.H ? 0.56 : 0.5);

  function drawSky(ctx) {
    const g = ctx.createLinearGradient(0, 0, 0, C.H); g.addColorStop(0, '#5ec2ff'); g.addColorStop(0.7, '#c8eeff'); g.addColorStop(1, '#e8f8ff');
    ctx.fillStyle = g; ctx.fillRect(0, 0, C.W, C.H);
    // солнце
    ctx.fillStyle = 'rgba(255,245,180,0.9)'; ctx.beginPath(); ctx.arc(C.W * 0.82, C.H * 0.16, 54, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(255,245,180,0.25)'; ctx.beginPath(); ctx.arc(C.W * 0.82, C.H * 0.16, 90, 0, 7); ctx.fill();
    // облака
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    for (let i = 0; i < 6; i++) {
      const cx = ((i * 520 - camX * 0.12 * Z) % (C.W + 600) + C.W + 600) % (C.W + 600) - 300, cy = C.H * (0.1 + (i % 3) * 0.08);
      for (const [dx, dy, r] of [[0, 0, 34], [36, -14, 42], [76, 0, 32], [38, 10, 30]]) { ctx.beginPath(); ctx.arc(cx + dx, cy + dy, r, 0, 7); ctx.fill(); }
    }
    // горы: два слоя с параллаксом
    for (const [k, col, base, amp] of [[0.15, '#9fd3c7', 0.62, 90], [0.3, '#7cc4a4', 0.72, 70]]) {
      ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(0, C.H);
      for (let x = 0; x <= C.W + 20; x += 20) { const wx = x / Z + camX * k; ctx.lineTo(x, C.H * base - amp * (0.6 * Math.sin(wx * 0.0021) + 0.4 * Math.sin(wx * 0.0057 + 1.3)) + (camY - 500) * k * Z * 0.3); }
      ctx.lineTo(C.W, C.H); ctx.closePath(); ctx.fill();
    }
  }
  function drawGround(ctx) {
    // дно пропастей — темнеет книзу
    { const y0 = sy(L.maxY + 260); if (y0 < C.H) { const g = ctx.createLinearGradient(0, y0, 0, y0 + 500 * Z); g.addColorStop(0, 'rgba(40,24,16,0)'); g.addColorStop(1, 'rgba(40,24,16,0.92)'); ctx.fillStyle = g; ctx.fillRect(0, y0, C.W, C.H - y0); } }
    const vx0 = camX - (C.W * 0.4) / Z - 50, vx1 = camX + (C.W * 0.6) / Z + 50, bottom = C.H + 50;
    for (const poly of L.polys) {
      if (poly[poly.length - 1][0] < vx0 || poly[0][0] > vx1) continue;
      ctx.beginPath(); ctx.moveTo(sx(poly[0][0]), bottom);
      for (const p of poly) ctx.lineTo(sx(p[0]), sy(p[1]));
      ctx.lineTo(sx(poly[poly.length - 1][0]), bottom); ctx.closePath();
      const g = ctx.createLinearGradient(0, sy(L.minY), 0, sy(L.maxY + 500)); g.addColorStop(0, '#b07444'); g.addColorStop(1, '#6d4127');
      ctx.fillStyle = g; ctx.fill();
      // полосы породы
      ctx.save(); ctx.clip(); ctx.strokeStyle = 'rgba(0,0,0,0.08)'; ctx.lineWidth = 10 * Z;
      for (let k = 1; k < 6; k++) { ctx.beginPath(); for (let i = 0; i < poly.length; i++) { const p = poly[i]; const X = sx(p[0]), Y = sy(p[1] + k * 70 + 12 * Math.sin(p[0] * 0.01 + k)); if (i) ctx.lineTo(X, Y); else ctx.moveTo(X, Y); } ctx.stroke(); }
      ctx.restore();
      // трава
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      ctx.strokeStyle = '#4caf50'; ctx.lineWidth = 22 * Z; ctx.beginPath(); poly.forEach((p, i) => (i ? ctx.lineTo(sx(p[0]), sy(p[1]) + 6 * Z) : ctx.moveTo(sx(p[0]), sy(p[1]) + 6 * Z))); ctx.stroke();
      ctx.strokeStyle = '#8bc34a'; ctx.lineWidth = 8 * Z; ctx.beginPath(); poly.forEach((p, i) => (i ? ctx.lineTo(sx(p[0]), sy(p[1])) : ctx.moveTo(sx(p[0]), sy(p[1])))); ctx.stroke();
    }
    for (const p of L.planks) plank(ctx, p[0], p[1], p[2], p[3], 20, '#c58b4f', '#8d5a2b');
  }
  function plank(ctx, x0, y0, x1, y1, th, col, edge) {
    const a = Math.atan2(y1 - y0, x1 - x0), len = Math.hypot(x1 - x0, y1 - y0);
    ctx.save(); ctx.translate(sx(x0), sy(y0)); ctx.rotate(a); ctx.scale(Z, Z);
    ctx.fillStyle = edge; C.rr(ctx, -2, -2, len + 4, th + 4, 6); ctx.fill();
    ctx.fillStyle = col; C.rr(ctx, 0, 0, len, th, 5); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(4, 3, len - 8, 4);
    ctx.fillStyle = edge; for (let x = 22; x < len - 10; x += 60) { ctx.beginPath(); ctx.arc(x, th / 2, 3, 0, 7); ctx.fill(); }
    ctx.restore();
  }
  function drawObjects(ctx) {
    for (const m of movers) {
      const h = m.m0.len / 2;
      ctx.save(); ctx.translate(sx(m.x), sy(m.y)); ctx.scale(Z, Z);
      ctx.fillStyle = '#455a64'; C.rr(ctx, -h - 2, -2, h * 2 + 4, 26, 8); ctx.fill();
      ctx.fillStyle = '#90a4ae'; C.rr(ctx, -h, 0, h * 2, 22, 7); ctx.fill();
      ctx.save(); C.rr(ctx, -h, 12, h * 2, 10, 4); ctx.clip(); ctx.fillStyle = '#ffca28'; ctx.fillRect(-h, 12, h * 2, 10); ctx.fillStyle = '#263238'; for (let x = -h; x < h; x += 28) { ctx.beginPath(); ctx.moveTo(x, 22); ctx.lineTo(x + 12, 12); ctx.lineTo(x + 24, 12); ctx.lineTo(x + 12, 22); ctx.fill(); } ctx.restore();
      ctx.restore();
    }
    for (const s of seesaws) {
      const pin = W.joints.find((j) => j.t === 'pin' && j.b === s);
      // опора
      ctx.fillStyle = '#e53935'; ctx.beginPath(); ctx.moveTo(sx(pin.px), sy(pin.py)); ctx.lineTo(sx(pin.px - 60), sy(pin.py + 700)); ctx.lineTo(sx(pin.px + 60), sy(pin.py + 700)); ctx.closePath(); ctx.fill();
      const h = s.segs[0][2];
      ctx.save(); ctx.translate(sx(s.x), sy(s.y)); ctx.rotate(s.a); ctx.scale(Z, Z);
      ctx.fillStyle = '#8d5a2b'; C.rr(ctx, -h - 2, -13, h * 2 + 4, 26, 8); ctx.fill();
      ctx.fillStyle = '#d39a5e'; C.rr(ctx, -h, -11, h * 2, 22, 7); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.2)'; ctx.fillRect(-h + 6, -8, h * 2 - 12, 4);
      ctx.fillStyle = '#8d5a2b'; for (let x = -h + 40; x < h - 20; x += 80) ctx.fillRect(x, -11, 3, 22);
      ctx.restore();
      ctx.fillStyle = '#b71c1c'; ctx.beginPath(); ctx.arc(sx(pin.px), sy(pin.py), 10 * Z, 0, 7); ctx.fill();
    }
    // чекпоинт и финиш
    if (L.cp) flagPole(ctx, L.cp.x, groundAt(L.cp.x), cpReached ? '#00e676' : '#b0bec5', false);
    const fy = groundAt(L.fin);
    flagPole(ctx, L.fin - 40, fy, '#fff', true); flagPole(ctx, L.fin + 260, groundAt(L.fin + 260), '#fff', true);
    // арка финиша
    ctx.save(); ctx.translate(sx(L.fin - 40), sy(fy - 230)); ctx.scale(Z, Z);
    const w = 300, cell = 20;
    for (let i = 0; i < w / cell; i++) for (let j = 0; j < 2; j++) { ctx.fillStyle = (i + j) % 2 ? '#212121' : '#fafafa'; ctx.fillRect(i * cell, j * cell, cell, cell); }
    ctx.restore();
    // звезда
    const st = L.star;
    if (st && !st.got) { const bob = Math.sin(C.realT * 3) * 8; ctx.save(); ctx.translate(sx(st.x), sy(st.y + bob)); ctx.rotate(Math.sin(C.realT * 2) * 0.15); C.icon('star', 0, 0, 110 * Z); ctx.restore(); }
  }
  function flagPole(ctx, x, gy, col, checker) {
    ctx.fillStyle = '#eceff1'; ctx.fillRect(sx(x) - 4 * Z, sy(gy - 230), 8 * Z, 230 * Z);
    if (!checker) { ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(sx(x) + 4 * Z, sy(gy - 228)); ctx.lineTo(sx(x + 80), sy(gy - 205)); ctx.lineTo(sx(x) + 4 * Z, sy(gy - 182)); ctx.closePath(); ctx.fill(); }
  }
  function drawWheel(ctx, w) {
    ctx.save(); ctx.translate(sx(w.x), sy(w.y)); ctx.rotate(w.a); ctx.scale(Z, Z);
    ctx.fillStyle = '#212121'; ctx.beginPath(); ctx.arc(0, 0, 28, 0, 7); ctx.fill();
    ctx.strokeStyle = '#424242'; ctx.lineWidth = 4; for (let i = 0; i < 12; i++) { const a = (i / 12) * 6.283; ctx.beginPath(); ctx.moveTo(Math.cos(a) * 22, Math.sin(a) * 22); ctx.lineTo(Math.cos(a) * 28, Math.sin(a) * 28); ctx.stroke(); }
    ctx.fillStyle = '#cfd8dc'; ctx.beginPath(); ctx.arc(0, 0, 15, 0, 7); ctx.fill();
    ctx.fillStyle = '#78909c'; for (let i = 0; i < 5; i++) { const a = (i / 5) * 6.283; ctx.beginPath(); ctx.arc(Math.cos(a) * 9, Math.sin(a) * 9, 2.6, 0, 7); ctx.fill(); }
    ctx.fillStyle = '#546e7a'; ctx.beginPath(); ctx.arc(0, 0, 4, 0, 7); ctx.fill();
    ctx.restore();
  }
  function truckPart(ctx, fn) { ctx.save(); ctx.translate(sx(truck.x), sy(truck.y)); ctx.rotate(truck.a); ctx.scale(Z, Z); fn(); ctx.restore(); }
  function drawTruckBack(ctx) {
    truckPart(ctx, () => {
      // подвеска
      ctx.strokeStyle = '#607d8b'; ctx.lineWidth = 8;
      for (const w of wheels) { const [lx, ly] = P.local(truck, w.x, w.y); ctx.beginPath(); ctx.moveTo(lx, 10); ctx.lineTo(lx, ly); ctx.stroke(); }
      ctx.fillStyle = TRUCK.frame; C.rr(ctx, -114, -8, 230, 26, 8); ctx.fill();
      // дальний борт кузова
      ctx.fillStyle = TRUCK.dark; C.rr(ctx, -112, -44, 128, 40, 6); ctx.fill();
    });
  }
  function drawTruckFront(ctx) {
    truckPart(ctx, () => {
      const M = TRUCK.main;
      // ближний борт (ниже, чтобы шарик было видно)
      ctx.fillStyle = M; C.rr(ctx, -114, -28, 132, 26, 6); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.25)'; ctx.fillRect(-108, -24, 120, 5);
      ctx.fillStyle = TRUCK.dark; C.rr(ctx, -116, -48, 12, 48, 4); ctx.fill(); C.rr(ctx, 8, -48, 12, 48, 4); ctx.fill();
      // кабина
      ctx.fillStyle = M; ctx.beginPath(); ctx.moveTo(14, -2); ctx.lineTo(14, -70); ctx.quadraticCurveTo(14, -78, 22, -78); ctx.lineTo(64, -78); ctx.lineTo(90, -38); ctx.lineTo(112, -34); ctx.quadraticCurveTo(120, -32, 120, -24); ctx.lineTo(120, -2); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#b3e5fc'; ctx.beginPath(); ctx.moveTo(24, -70); ctx.lineTo(60, -70); ctx.lineTo(80, -40); ctx.lineTo(24, -40); ctx.closePath(); ctx.fill();
      ctx.save(); ctx.beginPath(); ctx.moveTo(24, -70); ctx.lineTo(60, -70); ctx.lineTo(80, -40); ctx.lineTo(24, -40); ctx.closePath(); ctx.clip(); drawCat(ctx, 46, -50); ctx.restore();
      ctx.fillStyle = 'rgba(255,255,255,0.5)'; ctx.beginPath(); ctx.moveTo(56, -68); ctx.lineTo(64, -68); ctx.lineTo(74, -52); ctx.lineTo(68, -52); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = TRUCK.dark; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(84, -34); ctx.lineTo(84, -6); ctx.stroke();
      ctx.fillStyle = '#fff59d'; C.rr(ctx, 110, -28, 10, 10, 3); ctx.fill();
      ctx.fillStyle = '#263238'; C.rr(ctx, 100, -14, 22, 8, 3); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.22)'; ctx.fillRect(18, -74, 40, 4);
    });
  }
  // водитель — кот Барсик (вид сбоку, смотрит вперёд); пугается, когда шарик подлетает
  function drawCat(ctx, x, y) {
    const scared = state === 'dead' || !inBed || Math.abs(ball.vy - truck.vy) > 420, happy = state === 'win';
    const bob = Math.sin(tm * 18) * (grounded ? 0.8 : 0);
    ctx.save(); ctx.translate(x, y + bob);
    // платок
    ctx.fillStyle = '#1e5fd6'; ctx.beginPath(); ctx.ellipse(1, 14, 13, 6, 0, 0, 7); ctx.fill();
    // уши
    ctx.fillStyle = '#e08a35';
    ctx.beginPath(); ctx.moveTo(-11, -9); ctx.lineTo(-8, -24); ctx.lineTo(0, -12); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.moveTo(3, -12); ctx.lineTo(10, -25); ctx.lineTo(13, -8); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#f7b9a8'; ctx.beginPath(); ctx.moveTo(6, -12); ctx.lineTo(10, -20); ctx.lineTo(11, -10); ctx.closePath(); ctx.fill();
    // голова
    const g = ctx.createRadialGradient(-3, -6, 2, 0, 0, 16); g.addColorStop(0, '#f5a854'); g.addColorStop(1, '#d97a2b');
    ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(0, 0, 14, 13, 0, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(160,80,20,0.35)'; ctx.fillRect(-3, -13, 2, 6); ctx.fillRect(2, -13, 2, 5);
    // мордочка вперёд
    ctx.fillStyle = '#fbe0b8'; ctx.beginPath(); ctx.ellipse(9, 4, 8, 6.5, 0, 0, 7); ctx.fill();
    ctx.fillStyle = '#f48fb1'; ctx.beginPath(); ctx.ellipse(15, 1.5, 2.6, 2, 0, 0, 7); ctx.fill();
    // глаз (белок, зелёная радужка, зрачок)
    const er = scared ? 5.2 : 4.4;
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(6, -3, er * 0.85, er, 0, 0, 7); ctx.fill();
    if (happy) { ctx.strokeStyle = '#3e2723'; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.arc(6, -2, 3, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); }
    else { ctx.fillStyle = '#43a047'; ctx.beginPath(); ctx.arc(7.2, -3, er * 0.55, 0, 7); ctx.fill(); ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(7.8, -3, er * (scared ? 0.22 : 0.3), 0, 7); ctx.fill(); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(6.6, -4.4, 0.9, 0, 7); ctx.fill(); }
    // рот
    ctx.strokeStyle = '#6d3a1a'; ctx.lineWidth = 1.4;
    if (scared) { ctx.fillStyle = '#5d2a14'; ctx.beginPath(); ctx.ellipse(11, 8, 2, 2.6, 0, 0, 7); ctx.fill(); }
    else { ctx.beginPath(); ctx.arc(11, 5.5, happy ? 3.4 : 2.4, 0.1 * Math.PI, 0.8 * Math.PI); ctx.stroke(); }
    // усы
    ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 0.8;
    for (const dy of [-1, 1.5]) { ctx.beginPath(); ctx.moveTo(14, 4 + dy); ctx.lineTo(23, 2 + dy * 2); ctx.stroke(); }
    // лапы на руле
    ctx.fillStyle = '#37474f'; ctx.beginPath(); ctx.arc(24, 12, 7, 0, 7); ctx.lineWidth = 2.5; ctx.strokeStyle = '#37474f'; ctx.stroke();
    ctx.fillStyle = '#f0a050'; ctx.beginPath(); ctx.arc(20, 8, 3.4, 0, 7); ctx.fill();
    ctx.restore();
  }
  function drawBall(ctx) {
    const r = BR * Z, X = sx(ball.x), Y = sy(ball.y);
    C.drawBall(X, Y, r, C.mySkin(), ball.a, ctx);
    // лицо: глаза смотрят по скорости; в полёте — испуг, на финише — радость
    const scared = state === 'dead' || (!inBed) || Math.abs(ball.vy - truck.vy) > 420, happy = state === 'win';
    const lx = C.clamp(ball.vx / 900, -1, 1) * 4 * Z, ly = C.clamp(ball.vy / 900, -1, 1) * 4 * Z;
    const er = (scared ? 9.5 : 8) * Z;
    for (const s of [-1, 1]) {
      const ex = X + s * 11.5 * Z, ey = Y - 7 * Z;
      ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(ex, ey, er, er * 1.15, 0, 0, 7); ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.lineWidth = 1.5 * Z; ctx.stroke();
      if (happy) { ctx.strokeStyle = '#212121'; ctx.lineWidth = 2.5 * Z; ctx.beginPath(); ctx.arc(ex, ey + 2 * Z, er * 0.6, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); }
      else { ctx.fillStyle = '#212121'; ctx.beginPath(); ctx.arc(ex + lx, ey + ly, er * (scared ? 0.38 : 0.5), 0, 7); ctx.fill(); }
    }
    ctx.fillStyle = '#4e342e';
    if (scared) { ctx.beginPath(); ctx.ellipse(X, Y + 10 * Z, 5 * Z, 7 * Z, 0, 0, 7); ctx.fill(); }
    else { ctx.strokeStyle = '#4e342e'; ctx.lineWidth = 2.5 * Z; ctx.beginPath(); ctx.arc(X, Y + 5 * Z, (happy ? 9 : 6) * Z, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke(); }
  }

  // ---------- звук мотора ----------
  const eng = { o: null, g: null, f: null };
  function engineSound() {
    const A = C.audio; if (!A || !A.ctx) return;
    if (!eng.o) {
      try {
        eng.o = A.ctx.createOscillator(); eng.o.type = 'sawtooth'; eng.f = A.ctx.createBiquadFilter(); eng.f.type = 'lowpass'; eng.f.frequency.value = 420;
        eng.g = A.ctx.createGain(); eng.g.gain.value = 0; eng.o.connect(eng.f); eng.f.connect(eng.g); eng.g.connect(A.master); eng.o.start();
      } catch (e) { eng.o = null; return; }
    }
    const rpm = wheels.length ? Math.abs(wheels[0].w) : 0, on = C.state === 'play' && state === 'play';
    const thr = on && (keyGas() || touch === 'gas' || window.__autoGas) ? 1 : 0;
    const t = A.ctx.currentTime;
    eng.o.frequency.setTargetAtTime(48 + rpm * 3.2 + thr * 14, t, 0.06);
    eng.g.gain.setTargetAtTime(on ? 0.05 + thr * 0.06 : 0, t, 0.08);
  }

  // ---------- HUD и педали ----------
  function pedal(ctx, id, x, y, s, gas) {
    const on = gas ? (touch === 'gas' || keyGas()) : (touch === 'brake' || keyBrk());
    ctx.save(); ctx.translate(x + s / 2, y + s / 2); ctx.scale(on ? 0.93 : 1, on ? 0.93 : 1);
    ctx.globalAlpha = on ? 0.95 : 0.7;
    ctx.fillStyle = 'rgba(0,0,0,0.25)'; C.rr(ctx, -s / 2, -s / 2 + 8, s, s, 30); ctx.fill();
    ctx.fillStyle = gas ? '#43a047' : '#e53935'; C.rr(ctx, -s / 2, -s / 2, s, s, 30); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.2)'; C.rr(ctx, -s / 2 + 10, -s / 2 + 8, s - 20, s * 0.38, 22); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath();
    const d = gas ? 1 : -1; ctx.moveTo(-s * 0.16 * d, -s * 0.24); ctx.lineTo(s * 0.24 * d, 0); ctx.lineTo(-s * 0.16 * d, s * 0.24); ctx.closePath(); ctx.fill();
    ctx.restore(); ctx.globalAlpha = 1;
  }

  const game = {
    id: 'g6truck', landscapeBase: true, startState: 'home', hasSkip: true, reviveIcon: 'play', manualGameplay: false,
    init() { const lg = (C.lang || 'en').slice(0, 2); T = L10N[lg] || L10N.en; build(C.save.level || 1); },
    resize() { Z = C.W > C.H ? C.H / 760 : C.W / 800; },
    startLevel(n) { build(n); hintT = n === 1 ? 6 : n === 2 ? 3 : 0; toastL = []; partsFx = []; touch = null; },
    drawHome(ctx) {
      const land = C.W > C.H, sf = C.safeU();
      ctx.fillStyle = 'rgba(10,20,40,0.12)'; ctx.fillRect(0, 0, C.W, C.H);
      C.drawCoinsHud(); if (land) C.sideButtons(); else C.sideButtons(22 + sf.l, 110 + sf.t, true); C.soundButton(C.W - 106 - sf.r, 30 + sf.t);
      // название и уровень
      // название не шире 88% экрана
      let big = land ? 104 : 116; ctx.font = C.font(big); const tw = ctx.measureText('BALL TRUCK').width; if (tw > C.W * 0.84) big *= (C.W * 0.84) / tw;
      const ty = (land ? 118 : 360) + sf.t;
      ctx.save(); ctx.translate(C.W / 2, ty + Math.sin(C.realT * 2) * 4); ctx.rotate(-0.035);
      C.text('BALL TRUCK', 0, 0, big, '#ffca28', 'center', '#7a2e0e');
      ctx.restore();
      ctx.fillStyle = 'rgba(0,0,0,0.32)'; C.rr(ctx, C.W / 2 - 120, ty + big * 0.62, 240, 58, 29); ctx.fill();
      C.text(T.lv + ' ' + (C.save.level || 1), C.W / 2, ty + big * 0.62 + 30, 32, '#fff');
      const bw = 320, bh = 132, by = land ? C.H * 0.72 - sf.b : C.H * 0.68 - sf.b;
      if (C.button('playBtn', C.W / 2 - bw / 2, by, bw, bh, { color: '#43a047', icon: 'play', iconSize: 76, pulse: true })) C.startLevel();
    },
    revive() { const p = cpReached || { x: startX, y: startY }; L.star && (L.star.got = L.star.got); spawn(p.x, groundAt(p.x)); },
    onDown(x, y) { if (C.state !== 'play') return; touch = x > C.W / 2 ? 'gas' : 'brake'; },
    onMove(x, y) { if (touch) touch = x > C.W / 2 ? 'gas' : 'brake'; },
    onUp() { touch = null; },
    update(dt) {
      if (!W) return;
      // фиксированный шаг 1/120 с накоплением — одинаковая физика на 60, 144 и 165 Гц
      simAcc = Math.min(simAcc + dt, 1 / 15);
      while (simAcc >= P.DT) {
        P.step(W, (d) => control(d)); afterStep(); simAcc -= P.DT;
        if (state === 'play' && C.state === 'play') tm += P.DT;
      }
      if (state === 'dead') { failT += dt; if (failT > 0.9 && C.state === 'play') C.fail({ revive: !!cpReached }); }
      if (state === 'win') wonT += dt;
      // камера: впереди по ходу
      const [fx] = P.wvec(truck, 1, 0), look = C.clamp(truck.vx * 0.35, -150, 380);
      camX += (truck.x + look - camX) * Math.min(1, dt * 3); camY += (truck.y - 40 - camY) * Math.min(1, dt * 3);
      shake = Math.max(0, shake - dt);
      for (const p of partsFx) { p.t += dt; p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 900 * dt; }
      partsFx = partsFx.filter((p) => p.t < 1.2);
      for (const t of toastL) t.t += dt; toastL = toastL.filter((t) => t.t < 1.8);
      if (hintT > 0 && (keyGas() || touch === 'gas')) hintT = Math.min(hintT, 2.5);
      hintT -= dt;
      engineSound();
    },
    draw(ctx) {
      if (!W) { drawSky(ctx); return; }
      ctx.save();
      if (shake > 0) ctx.translate((Math.random() - 0.5) * 18 * shake, (Math.random() - 0.5) * 18 * shake);
      drawSky(ctx); drawGround(ctx); drawObjects(ctx);
      drawTruckBack(ctx); drawBall(ctx); drawTruckFront(ctx);
      for (const w of wheels) drawWheel(ctx, w);
      for (const p of partsFx) { ctx.globalAlpha = Math.max(0, 1 - p.t / 1.2); ctx.fillStyle = p.col; ctx.beginPath(); ctx.arc(sx(p.x), sy(p.y), p.r * Z, 0, 7); ctx.fill(); }
      ctx.globalAlpha = 1;
      ctx.restore();
    },
    hud(ctx) {
      const sf = C.safeU();
      // уровень, время, звезда
      ctx.fillStyle = 'rgba(0,0,0,0.3)'; C.rr(ctx, 20 + sf.l, 22 + sf.t, 210, 64, 32); ctx.fill();
      C.text(T.lv + ' ' + lastLevel, 125 + sf.l, 55 + sf.t, 30, '#fff');
      const tx = C.W / 2;
      ctx.fillStyle = 'rgba(0,0,0,0.3)'; C.rr(ctx, tx - 120, 22 + sf.t, 240, 64, 32); ctx.fill();
      C.text(tm.toFixed(1), tx - 30, 55 + sf.t, 32, tm <= parT ? '#fff' : '#ffab91');
      C.icon(L.star && L.star.got ? 'star' : 'starEmpty', tx + 70, 54 + sf.t, 44);
      // перезапуск
      if (C.state === 'play' && C.button('restartBtn', C.W - 206 - sf.r, 30 + sf.t, 84, 84, { color: '#455a64', icon: 'retry', iconSize: 44 })) { C.sfx('tap'); C.startLevel('retry'); }
      // педали
      if (C.state === 'play') {
        const s = C.W > C.H ? 150 : 170, by = C.H - s - 30 - sf.b;
        pedal(ctx, 'brk', 30 + sf.l, by, s, false); pedal(ctx, 'gas', C.W - s - 30 - sf.r, by, s, true);
      }
      // подсказка
      if (hintT > 0 && C.state === 'play') {
        ctx.globalAlpha = Math.min(1, hintT);
        ctx.fillStyle = 'rgba(20,30,60,0.78)'; C.rr(ctx, C.W / 2 - 330, C.H * 0.24 - 36, 660, 112, 30); ctx.fill();
        C.text(T.hint, C.W / 2, C.H * 0.24, 32, '#fff'); C.text(T.hint2, C.W / 2, C.H * 0.24 + 44, 28, '#ffe082');
        ctx.globalAlpha = 1;
      }
      toastL.forEach((t, i) => { ctx.globalAlpha = Math.max(0, Math.min(1, (1.8 - t.t) * 3)); C.text(t.text, C.W / 2, C.H * 0.38 - i * 56 - t.t * 30, 46, t.col); ctx.globalAlpha = 1; });
    },
  };
  // тестовые крючки
  window.__truck = () => ({ x: Math.round(truck.x), y: Math.round(truck.y), a: +truck.a.toFixed(2), vx: Math.round(truck.vx), ball: [Math.round(ball.x), Math.round(ball.y)], inBed, grounded, state, tm: +tm.toFixed(2), fin: L.fin, star: L.star && L.star.got, cp: !!cpReached, lvl: lastLevel, cs: C.state, mov: movers.map((m) => Math.round(m.x - m.m0.len / 2)), see: seesaws.map((q) => +q.a.toFixed(2)) });
  window.__lvl = (n) => { C.save.level = n; C.startLevel(); };
  window.__levels = () => LEVELS.length;
  C.run(game);
})();
