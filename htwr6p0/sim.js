'use strict';
/* Hook Truck — логика уровня без рисования (её же гоняет автопилот в тестах).
   Грузовик на подвеске + трос с крюком: держишь «крюк» — цепляешься за ближайшее кольцо сверху,
   отпустил — летишь. На земле натянутый трос подтягивает лебёдкой (так залезаем на обрыв). */
(function (root) {
  const P = root.TPhys;
  const RANGE = 700;        // докуда достаёт крюк (от лебёдки до кольца)
  const MAST = [30, -104];  // лебёдка на крыше кабины (локальные координаты грузовика): тянет нос вверх — грузовик лезет на стену колёсами
  const REEL_GROUND = 260;  // лебёдка сама тянет, пока колёса упираются
  const REEL_FAST = 520;    // кнопка «тянуть» (второй игрок)
  const MIN_ROPE = 150;

  // ---------- построитель трассы (как в Ball Truck) ----------
  function Track() {
    const S = { polys: [], anchors: [], spikes: [], star: null, cps: [], fin: 0, minY: 1e9, maxY: -1e9 };
    let x = 0, y = 600, cur = null;
    const push = (px, py) => { cur.push([px, py]); S.minY = Math.min(S.minY, py); S.maxY = Math.max(S.maxY, py); };
    const B = {
      S,
      get x() { return x; }, get y() { return y; },
      start(x0, y0) { x = x0; y = y0; cur = []; push(x, y); return B; },
      flat(len) { x += len; push(x, y); return B; },
      slope(len, up, n = 12) { const x0 = x, y0 = y; for (let i = 1; i <= n; i++) { const t = i / n, s = t * t * (3 - 2 * t); push(x0 + len * t, y0 - up * s); } x = x0 + len; y = y0 - up; return B; },
      hill(len, h, n = 14) { const x0 = x; for (let i = 1; i <= n; i++) { const t = i / n; push(x0 + len * t, y - h * (0.5 - 0.5 * Math.cos(t * Math.PI * 2))); } x = x0 + len; return B; },
      // яма (dx — ширина, dy — насколько выше/ниже другой край); на дне шипы
      gap(dx, dy = 0, spikes = true) { S.polys.push(cur); if (spikes && dx > 60) S.spikes.push({ x0: x + 10, x1: x + dx - 10, y: Math.max(y, y + dy) + 340 }); x += dx; y += dy; cur = []; push(x, y); return B; },
      // кольцо для крюка: dx от текущей точки, h — высота над дорогой
      ring(dx, h) { S.anchors.push({ x: x + dx, y: y - h }); return B; },
      star(dx, h) { S.star = { x: x + dx, y: y - h, got: false }; return B; },
      cp(dx = 0) { S.cps.push({ x: x + dx, y }); return B; },
      fin(dx = 150) { S.fin = x + dx; return B; },
      end(len = 1500) { B.flat(len); S.polys.push(cur); cur = null; return B; },
    };
    return B;
  }

  // Уровень «средний»: яма на одном крюке, обрыв (подтянуться лебёдкой), пропасть на двух крюках подряд
  function level1() {
    const b = Track().start(-300, 600).flat(1000).hill(520, 46).flat(420);
    b.ring(300, 430).gap(600);                 // яма 1: одно кольцо над серединой
    b.flat(260).cp(-80).flat(420);
    b.gap(0, -380, false).ring(130, 300);       // обрыв вверх на 380: кольцо над кромкой
    b.flat(80).cp(0).flat(820);                  // разгон перед пропастью
    b.ring(300, 450).ring(700, 450).star(740, 360).gap(1000); // пропасть: два кольца подряд; звезда — если отпустить второе поздно
    b.flat(700).slope(700, -160).flat(200).fin(100).end();
    return b.S;
  }

  function create(levelFn) {
    const S = {
      L: null, W: null, truck: null, wheels: [], wj: [], rope: null, ropeA: null, target: null,
      state: 'play', t: 0, deadT: 0, why: '', grounded: false, wallTouch: false, crashT: 0, flipT: 0,
      cp: null, attempts: 1, hooks: 0, events: [], wonT: 0, pullOn: false,
    };
    S.L = (levelFn || level1)();
    const L = S.L;

    function buildWorld() {
      const W = (S.W = P.world());
      for (const poly of L.polys) {
        for (let i = 1; i < poly.length; i++) P.addStatic(W, poly[i - 1][0], poly[i - 1][1], poly[i][0], poly[i][1], 0.9);
        const a = poly[0], z = poly[poly.length - 1];
        P.addStatic(W, a[0], a[1], a[0], a[1] + 1600); P.addStatic(W, z[0], z[1], z[0], z[1] + 1600);
      }
      const a = L.polys[0][0], lp = L.polys[L.polys.length - 1], z = lp[lp.length - 1];
      P.addStatic(W, a[0], a[1], a[0], a[1] - 3000); P.addStatic(W, z[0], z[1], z[0], z[1] - 3000);
    }

    S.groundAt = (x) => {
      let best = null;
      for (const poly of L.polys) for (let i = 1; i < poly.length; i++) { const a = poly[i - 1], b = poly[i]; if (x >= a[0] && x <= b[0]) { const t = (x - a[0]) / (b[0] - a[0] || 1), y = a[1] + (b[1] - a[1]) * t; if (best === null || y < best) best = y; } }
      return best === null ? 600 : best;
    };

    S.spawn = (x, gy) => {
      buildWorld();
      const W = S.W, y = gy - 82;
      S.truck = P.addBody(W, P.body({
        x, y, m: 8, I: 34000, group: 'truck', kind: 'truck', rad: 190, mu: 0.6, lin: 0.9997, ang: 0.997,
        circles: [
          { x: -100, y: 14, r: 13 }, { x: 102, y: 12, r: 13 }, { x: 110, y: -10, r: 10 },
          { x: -106, y: -34, r: 10 }, { x: MAST[0], y: MAST[1] + 6, r: 10 }, { x: 70, y: -62, r: 13, crash: true }, { x: 30, y: -66, r: 13, crash: true },
        ],
      }));
      S.wheels = []; S.wj = [];
      for (const lx of [-72, 72]) {
        const w = P.addBody(W, P.body({ x: x + lx, y: y + 48, m: 1.2, I: 440, group: 'truck', kind: 'wheel', mu: 1.0, circles: [{ x: 0, y: 0, r: 27 }], ang: 0.999 }));
        S.wheels.push(w);
        S.wj.push(P.wheelJoint(W, S.truck, w, { lx, ly: 18, rest: 34, k: 1150, c: 70, lo: 10, hi: 44 }));
      }
      S.rope = null; S.ropeA = null; S.state = 'play'; S.deadT = 0; S.crashT = 0; S.flipT = 0; S.wonT = 0; S.grounded = false;
    };
    S.respawn = () => {
      const p = S.cp || { x: L.polys[0][0][0] + 320, y: L.polys[0][0][1] };
      S.spawn(p.x, S.groundAt(p.x)); S.attempts++;
      S.events.push({ e: 'respawn' });
    };
    S.mast = () => P.wpt(S.truck, MAST[0], MAST[1]);

    // кольцо, за которое зацепится крюк, если нажать сейчас: в пределах троса, выше лебёдки; впереди — лучше
    S.findTarget = () => {
      const [mx, my] = S.mast(); let best = null, bs = 1e9;
      for (const a of L.anchors) {
        const dx = a.x - mx, dy = a.y - my, d = Math.hypot(dx, dy);
        if (d > RANGE || dy > -60) continue;
        const s = d - (dx > -120 ? 160 : 0);
        if (s < bs) { bs = s; best = a; }
      }
      return best;
    };

    function hookOn(a) {
      const [mx, my] = S.mast(), d = Math.hypot(a.x - mx, a.y - my);
      S.rope = P.ropeJoint(S.W, S.truck, MAST[0], MAST[1], a.x, a.y, Math.max(MIN_ROPE, d));
      S.ropeA = a; S.hooks++; S.events.push({ e: 'hook' });
    }
    function hookOff() {
      if (!S.rope) return;
      S.W.joints = S.W.joints.filter((j) => j !== S.rope); S.rope = null; S.ropeA = null; S.events.push({ e: 'unhook' });
      S.truck.w *= 0.5; // после отпускания меньше крутит — легче приземлиться на колёса
    }

    // один шаг 1/120 с; inp = { gas, brake, hook, pull }
    S.step = (inp) => {
      const dt = P.DT, T = S.truck;
      if (S.state === 'dead') { S.deadT += dt; if (S.deadT > 1.1) S.respawn(); }
      const play = S.state === 'play';
      // крюк: держишь — висишь; отпустил — летишь
      S.target = play && !S.rope ? S.findTarget() : null;
      if (play && inp.hook && !S.rope && S.target) hookOn(S.target);
      if (S.rope && (!inp.hook || !play)) hookOff();
      S.pullOn = false;
      if (S.rope) {
        // катушка выбирает слабину: трос не провисает, пока едешь к кольцу
        const [mx, my] = S.mast(), dNow = Math.hypot(mx - S.rope.px, my - S.rope.py);
        if (dNow < S.rope.len) S.rope.len = Math.max(MIN_ROPE, dNow);
        const tight = S.rope.d > S.rope.len - 6;
        let reel = 0;
        if (inp.pull) reel = REEL_FAST;
        else if (tight && (S.grounded || S.wallTouch || Math.hypot(S.truck.vx, S.truck.vy) < 220)) reel = REEL_GROUND;
        if (reel) { S.rope.len = Math.max(MIN_ROPE, S.rope.len - reel * dt); S.pullOn = true; }
      }
      // газ / тормоз — как в Ball Truck
      const g = play && inp.gas, br = play && !g && inp.brake;
      const [fx, fy] = P.wvec(T, 1, 0), fwd = T.vx * fx + T.vy * fy;
      for (const j of S.wj) {
        j.brake = 0;
        if (!play) { j.brake = S.state === 'win' ? 160000 : 0; j.maxT = 0; continue; }
        if (g) { j.speed = 37; j.maxT = S.grounded ? 225000 : 45000; }
        else if (br) { if (fwd > 70) { j.brake = 230000; j.maxT = 0; } else { j.speed = -16; j.maxT = 110000; } }
        else { j.speed = 0; j.maxT = 3500; }
      }
      if (!S.grounded && play && !S.rope) {
        const k = g ? -1 : br ? 1 : 0;
        if (k) { T.w += k * 4.2 * dt; T.w = Math.max(-3.2, Math.min(3.2, T.w)); } else T.w *= 1 - 2.2 * dt;
      }
      P.step(S.W);
      after();
      S.t += dt;
    };

    function after() {
      const T = S.truck;
      S.grounded = false; S.wallTouch = false; let roof = false;
      for (const k of S.W.touch) {
        if (k.A.kind === 'wheel') { S.grounded = true; if (Math.abs(k.nx) > 0.6) S.wallTouch = true; }
        if (k.A === T) { if (k.tagA && k.tagA.crash) roof = true; else S.wallTouch = true; }
      }
      if (S.state !== 'play') { if (S.state === 'win') S.wonT += P.DT; return; }
      S.crashT = roof && !S.rope ? S.crashT + P.DT : 0; // на тросе можно чиркнуть крышей о стену
      const up = Math.cos(T.a);
      S.flipT = up < 0 && !S.rope ? S.flipT + P.DT : 0;
      const sp = S.L.spikes.find((z) => T.x > z.x0 - 60 && T.x < z.x1 + 60 && T.y > z.y - 120);
      if (S.crashT > 0.12 || S.flipT > 1.6) die('crash');
      else if (sp || T.y > S.L.maxY + 700) die('fell');
      const st = S.L.star;
      if (st && !st.got && Math.hypot(st.x - T.x, st.y - T.y) < 130) { st.got = true; S.events.push({ e: 'star' }); }
      for (const c of S.L.cps) if (T.x > c.x && (!S.cp || S.cp.x < c.x) && S.grounded) { S.cp = { x: c.x, y: c.y }; S.events.push({ e: 'cp' }); }
      if (T.x > S.L.fin && S.grounded) { S.state = 'win'; S.wonT = 0; if (S.rope) hookOff(); S.events.push({ e: 'win' }); }
    }
    function die(why) {
      S.state = 'dead'; S.deadT = 0; S.why = why; if (S.rope) hookOff(); S.events.push({ e: 'dead', why });
    }

    S.spawn(L.polys[0][0][0] + 320, L.polys[0][0][1]);
    return S;
  }

  root.HookSim = { create, level1, RANGE, MAST };
})(typeof window !== 'undefined' ? window : globalThis);
