'use strict';
/* Небольшой 2D-движок для «Шара в кузове»: тела-круги и тела-отрезки, подвеска колёс (как wheel joint в Box2D),
   шарнир к миру (качели), кинематические платформы. Последовательные импульсы, шаг 1/120 с. Ось Y — вниз. */
(function () {
  const P = (window.TPhys = {});
  P.G = 1750; P.DT = 1 / 120; P.ITER = 10;
  const BETA = 0.22, SLOP = 0.5;
  const cross = (ax, ay, bx, by) => ax * by - ay * bx;

  // тело: x,y,a — центр и угол; circles/segs — формы в своих координатах; dyn=false — кинематическое (скорость задаёт скрипт)
  P.body = (o) => {
    const b = Object.assign({ x: 0, y: 0, a: 0, vx: 0, vy: 0, w: 0, m: 1, I: 1, circles: [], segs: [], dyn: true, mu: 0.8, e: 0, group: '', lin: 0.9995, ang: 0.996 }, o);
    b.im = b.dyn ? 1 / b.m : 0; b.iI = b.dyn ? 1 / b.I : 0; return b;
  };
  P.wpt = (b, lx, ly) => { const c = Math.cos(b.a), s = Math.sin(b.a); return [b.x + c * lx - s * ly, b.y + s * lx + c * ly]; };
  P.wvec = (b, lx, ly) => { const c = Math.cos(b.a), s = Math.sin(b.a); return [c * lx - s * ly, s * lx + c * ly]; };
  P.local = (b, x, y) => { const c = Math.cos(b.a), s = Math.sin(b.a), dx = x - b.x, dy = y - b.y; return [c * dx + s * dy, -s * dx + c * dy]; };

  P.world = () => ({ bodies: [], statics: [], cells: new Map(), joints: [], contacts: [], qid: 0, touch: [] });
  const CELL = 240;
  // неподвижный отрезок мира (земля, стены, балки)
  P.addStatic = (W, ax, ay, bx, by, mu = 0.9) => {
    const s = { ax, ay, bx, by, mu, q: 0 };
    W.statics.push(s);
    const c0 = Math.floor(Math.min(ax, bx) / CELL), c1 = Math.floor(Math.max(ax, bx) / CELL);
    for (let c = c0; c <= c1; c++) { let a = W.cells.get(c); if (!a) W.cells.set(c, (a = [])); a.push(s); }
    return s;
  };
  P.addBody = (W, b) => { W.bodies.push(b); return b; };

  // круг против отрезка: точка касания на отрезке и нормаль от отрезка к центру круга
  function cseg(cx, cy, r, ax, ay, bx, by) {
    const ex = bx - ax, ey = by - ay, L2 = ex * ex + ey * ey;
    let t = L2 > 0 ? ((cx - ax) * ex + (cy - ay) * ey) / L2 : 0; t = t < 0 ? 0 : t > 1 ? 1 : t;
    const qx = ax + ex * t, qy = ay + ey * t; let dx = cx - qx, dy = cy - qy;
    const d2 = dx * dx + dy * dy; if (d2 >= r * r) return null;
    let d = Math.sqrt(d2);
    if (d < 1e-6) { const L = Math.sqrt(L2) || 1; dx = -ey / L; dy = ex / L; d = 0; } else { dx /= d; dy /= d; }
    return { nx: dx, ny: dy, pen: r - d, qx, qy };
  }

  function addContact(W, A, B, h, mu, e, tagA, tagB) {
    const k = { A, B, nx: h.nx, ny: h.ny, pen: h.pen, rax: h.qx - A.x, ray: h.qy - A.y, rbx: B ? h.qx - B.x : 0, rby: B ? h.qy - B.y : 0, mu, e, ln: 0, lt: 0, tagA, tagB };
    W.contacts.push(k); W.touch.push(k);
  }

  function collide(W) {
    W.contacts.length = 0; W.touch.length = 0;
    for (const A of W.bodies) {
      if (!A.dyn || !A.circles.length) continue;
      for (let ci = 0; ci < A.circles.length; ci++) {
        const c = A.circles[ci]; if (c.off) continue;
        const [cx, cy] = P.wpt(A, c.x, c.y), r = c.r;
        // неподвижный мир
        const q = ++W.qid, c0 = Math.floor((cx - r) / CELL), c1 = Math.floor((cx + r) / CELL);
        for (let cc = c0; cc <= c1; cc++) {
          const arr = W.cells.get(cc); if (!arr) continue;
          for (const s of arr) {
            if (s.q === q) continue; s.q = q;
            const h = cseg(cx, cy, r, s.ax, s.ay, s.bx, s.by);
            if (h) addContact(W, A, null, h, Math.sqrt((c.mu || A.mu) * s.mu), c.e !== undefined ? c.e : A.e, c, s);
          }
        }
        // отрезки других тел (кузов, качели, платформы)
        for (const B of W.bodies) {
          if (B === A || !B.segs.length) continue;
          if (A.group && A.group === B.group) continue;
          if (c.only && c.only !== B.kind) continue;
          if (B.only && B.only !== A.kind) continue;
          const dx = cx - B.x, dy = cy - B.y, R = (B.rad || 1e9) + r; if (dx * dx + dy * dy > R * R) continue;
          for (const sg of B.segs) {
            const [ax, ay] = P.wpt(B, sg[0], sg[1]), [bx, by] = P.wpt(B, sg[2], sg[3]);
            const h = cseg(cx, cy, r, ax, ay, bx, by);
            if (h) addContact(W, A, B, h, Math.sqrt((c.mu || A.mu) * (B.mu || 0.8)), Math.max(c.e !== undefined ? c.e : A.e, B.e || 0), c, sg);
          }
        }
      }
    }
  }

  const vel = (b, rx, ry) => [b.vx - b.w * ry, b.vy + b.w * rx];
  function imp(b, rx, ry, px, py) { if (!b || !b.dyn) return; b.vx += b.im * px; b.vy += b.im * py; b.w += b.iI * cross(rx, ry, px, py); }

  function prepContact(k) {
    const A = k.A, B = k.B;
    const ran = cross(k.rax, k.ray, k.nx, k.ny), rat = cross(k.rax, k.ray, -k.ny, k.nx);
    let kn = A.im + A.iI * ran * ran, kt = A.im + A.iI * rat * rat;
    if (B && B.dyn) { const rbn = cross(k.rbx, k.rby, k.nx, k.ny), rbt = cross(k.rbx, k.rby, -k.ny, k.nx); kn += B.im + B.iI * rbn * rbn; kt += B.im + B.iI * rbt * rbt; }
    k.kn = 1 / kn; k.kt = 1 / kt;
    const [vax, vay] = vel(A, k.rax, k.ray), [vbx, vby] = B ? vel(B, k.rbx, k.rby) : [0, 0];
    const vn = (vax - vbx) * k.nx + (vay - vby) * k.ny;
    k.bias = (BETA / P.DT) * Math.max(0, k.pen - SLOP);
    if (vn < -90 && k.e > 0) k.bias = Math.max(k.bias, -k.e * vn);
    k.vn0 = vn;
  }
  function solveContact(k) {
    const A = k.A, B = k.B;
    const [vax, vay] = vel(A, k.rax, k.ray), [vbx, vby] = B ? vel(B, k.rbx, k.rby) : [0, 0];
    const rvx = vax - vbx, rvy = vay - vby;
    const vn = rvx * k.nx + rvy * k.ny;
    let dl = (k.bias - vn) * k.kn; const o = k.ln; k.ln = Math.max(0, o + dl); dl = k.ln - o;
    imp(A, k.rax, k.ray, k.nx * dl, k.ny * dl); imp(B, k.rbx, k.rby, -k.nx * dl, -k.ny * dl);
    const tx = -k.ny, ty = k.nx;
    const [vax2, vay2] = vel(A, k.rax, k.ray), [vbx2, vby2] = B ? vel(B, k.rbx, k.rby) : [0, 0];
    const vt = (vax2 - vbx2) * tx + (vay2 - vby2) * ty;
    let dt = -vt * k.kt; const ot = k.lt, mx = k.mu * k.ln; k.lt = Math.max(-mx, Math.min(mx, ot + dt)); dt = k.lt - ot;
    imp(A, k.rax, k.ray, tx * dt, ty * dt); imp(B, k.rbx, k.rby, -tx * dt, -ty * dt);
  }

  // подвеска колеса: колесо ходит по оси шасси (вниз), пружина с амортизатором, упоры, мотор
  P.wheelJoint = (W, ch, wh, o) => { const j = Object.assign({ t: 'wheel', ch, wh, lx: 0, ly: 0, rest: 30, k: 900, c: 60, lo: 8, hi: 40, speed: 0, maxT: 0, brake: 0 }, o); W.joints.push(j); return j; };
  // шарнир тела к точке мира (качели, маятник)
  P.pinJoint = (W, b, lx, ly, px, py) => { const j = { t: 'pin', b, lx, ly, px, py }; W.joints.push(j); return j; };

  function prepJoint(j) {
    if (j.t === 'wheel') {
      const C = j.ch, Wh = j.wh;
      const [rax, ray] = P.wvec(C, j.lx, j.ly), [axx, axy] = P.wvec(C, 0, 1), ayx = -axy, ayy = axx;
      const dx = Wh.x - (C.x + rax), dy = Wh.y - (C.y + ray);
      j.axx = axx; j.axy = axy; j.ayx = ayx; j.ayy = ayy;
      j.sAy = cross(dx + rax, dy + ray, ayx, ayy); j.sAx = cross(dx + rax, dy + ray, axx, axy);
      j.my = 1 / (C.im + Wh.im + C.iI * j.sAy * j.sAy);
      j.mx = 1 / (C.im + Wh.im + C.iI * j.sAx * j.sAx);
      const cy = dx * ayx + dy * ayy; j.by = -(BETA / P.DT) * cy;
      const x = dx * axx + dy * axy; j.x = x;
      // пружина (явная сила)
      const xdot = (Wh.vx - C.vx) * axx + (Wh.vy - C.vy) * axy - C.w * j.sAx;
      const F = (-j.k * (x - j.rest) - j.c * xdot) * P.DT;
      Wh.vx += Wh.im * F * axx; Wh.vy += Wh.im * F * axy; C.vx -= C.im * F * axx; C.vy -= C.im * F * axy; C.w -= C.iI * F * j.sAx;
      j.lim = 0; j.ll = 0;
      if (x < j.lo) { j.lim = 1; j.lb = -(BETA / P.DT) * (x - j.lo); } else if (x > j.hi) { j.lim = -1; j.lb = -(BETA / P.DT) * (x - j.hi); }
      j.lm = 0; j.mm = 1 / (Wh.iI + C.iI);
    } else if (j.t === 'pin') {
      const b = j.b, [rx, ry] = P.wvec(b, j.lx, j.ly);
      j.rx = rx; j.ry = ry;
      const k11 = b.im + b.iI * ry * ry, k12 = -b.iI * rx * ry, k22 = b.im + b.iI * rx * rx, det = k11 * k22 - k12 * k12 || 1;
      j.i11 = k22 / det; j.i12 = -k12 / det; j.i22 = k11 / det;
      j.cx = b.x + rx - j.px; j.cy = b.y + ry - j.py;
    }
  }
  function solveJoint(j) {
    if (j.t === 'wheel') {
      const C = j.ch, Wh = j.wh;
      // поперёк оси — колесо не уходит вбок
      const cd = (Wh.vx - C.vx) * j.ayx + (Wh.vy - C.vy) * j.ayy - C.w * j.sAy;
      const l = (j.by - cd) * j.my;
      Wh.vx += Wh.im * l * j.ayx; Wh.vy += Wh.im * l * j.ayy; C.vx -= C.im * l * j.ayx; C.vy -= C.im * l * j.ayy; C.w -= C.iI * l * j.sAy;
      // упоры хода подвески
      if (j.lim) {
        const xd = (Wh.vx - C.vx) * j.axx + (Wh.vy - C.vy) * j.axy - C.w * j.sAx;
        let dl = (j.lb - xd) * j.mx; const o = j.ll;
        j.ll = j.lim > 0 ? Math.max(0, o + dl) : Math.min(0, o + dl); dl = j.ll - o;
        Wh.vx += Wh.im * dl * j.axx; Wh.vy += Wh.im * dl * j.axy; C.vx -= C.im * dl * j.axx; C.vy -= C.im * dl * j.axy; C.w -= C.iI * dl * j.sAx;
      }
      // мотор / тормоз
      const maxT = (j.brake || j.maxT) * P.DT;
      if (maxT > 0) {
        const target = j.brake ? 0 : j.speed;
        const cdw = Wh.w - C.w;
        // газ только разгоняет (быстрее нормы — катится сам, например после ускорителя); тормоз держит в обе стороны
        const lo = j.brake ? -maxT : j.speed > 0 ? 0 : -maxT, hi = j.brake ? maxT : j.speed < 0 ? 0 : maxT;
        let dl = (target - cdw) * j.mm; const o = j.lm; j.lm = Math.max(lo, Math.min(hi, o + dl)); dl = j.lm - o;
        Wh.w += Wh.iI * dl; C.w -= C.iI * dl;
      }
    } else if (j.t === 'pin') {
      const b = j.b, [vx, vy] = vel(b, j.rx, j.ry);
      const bx = -(BETA / P.DT) * j.cx - vx, by = -(BETA / P.DT) * j.cy - vy;
      const px = j.i11 * bx + j.i12 * by, py = j.i12 * bx + j.i22 * by;
      imp(b, j.rx, j.ry, px, py);
    }
  }

  // один шаг мира; before(dt) — силы и управление до решения, kin(dt) — движение кинематических тел
  P.step = (W, before) => {
    const dt = P.DT;
    for (const b of W.bodies) if (b.dyn) { b.vy += P.G * dt * (b.gk === undefined ? 1 : b.gk); }
    if (before) before(dt);
    collide(W);
    for (const j of W.joints) prepJoint(j);
    for (const k of W.contacts) prepContact(k);
    for (let it = 0; it < P.ITER; it++) {
      for (const j of W.joints) solveJoint(j);
      for (const k of W.contacts) solveContact(k);
    }
    for (const b of W.bodies) {
      if (b.dyn) {
        b.vx *= b.lin; b.vy *= b.lin; b.w *= b.ang;
        const sp = Math.hypot(b.vx, b.vy); if (sp > 3200) { b.vx *= 3200 / sp; b.vy *= 3200 / sp; }
        if (b.w > 60) b.w = 60; else if (b.w < -60) b.w = -60;
      }
      b.x += b.vx * dt; b.y += b.vy * dt; b.a += b.w * dt;
    }
  };
})();
