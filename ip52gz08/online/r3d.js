'use strict';
/* Flagball Arena — 3D-картинка арены (three.js r128, лежит рядом, без внешних запросов).
   Правила и сервер прежние: мир — плоскость (x, y), здесь он рисуется как стадион (x, высота, y).
   Подписи, иконки и кнопки остаются на 2D-холсте поверх (FB3D.project переводит точку мира в экран).
   Нет WebGL — игра рисует по-старому, в 2D. */
(function () {
  const C = window.Core;
  const R3 = (window.FB3D = { ok: false });
  if (!window.THREE) return;
  const TH = window.THREE;
  // цвета из CSS-строк — в линейное пространство (иначе при выводе в sRGB всё бледнеет)
  { const ss = TH.Color.prototype.setStyle; TH.Color.prototype.setStyle = function (st) { ss.call(this, st); return this.convertSRGBToLinear(); }; }
  const TILT = (33 * Math.PI) / 180, FOV = 40;
  let R, S, cam, glc, pr = 1, slowT = 0, frames = 0;
  const v3 = new TH.Vector3(), v3b = new TH.Vector3(), q4 = new TH.Quaternion(), e3 = new TH.Euler(), m4 = new TH.Matrix4(), s3 = new TH.Vector3();
  const camUp = new TH.Vector3(0, 1, 0);

  function tex(w, h, f) { const c = document.createElement('canvas'); c.width = w; c.height = h; f(c.getContext('2d'), w, h); const t = new TH.CanvasTexture(c); t.encoding = TH.sRGBEncoding; return t; }

  // ---------- общие заготовки ----------
  let field, grass, lineMat, centerRing, halfLine, edgeRing, edgeR = 0, wall, wallMat, boards, stands, outer;
  let gems, GEM_CAP = 2600;
  const colCache = {};
  const colOf = (s) => colCache[s] || (colCache[s] = new TH.Color(s));
  let sphereG, eyeG, flagG, eyeW, eyeB, shadowMat, ringG, planeG, magG, bubbleMat, boostMat, magnetMat;
  const flagMats = {}, accTex = {};
  const balls = new Map(); // id → объекты сцены шарика
  const saws = [], pows = [];
  let sawG = null;

  R3.init = (canvas) => {
    try {
      // на экранах с плотностью 2× и выше сглаживание почти не видно, а стоит дорого — включаем только на обычных
      R = new TH.WebGLRenderer({ canvas, antialias: (window.devicePixelRatio || 1) < 1.6, powerPreference: 'high-performance' });
    } catch (e) { return false; }
    if (!R || !R.getContext()) return false;
    glc = canvas;
    R.outputEncoding = TH.sRGBEncoding; R.toneMapping = TH.NoToneMapping;
    S = new TH.Scene(); S.background = new TH.Color('#243064');
    cam = new TH.PerspectiveCamera(FOV, 1, 20, 40000);
    S.add(new TH.HemisphereLight('#e6f4ff', '#3a6a28', 0.75));
    const sun = new TH.DirectionalLight('#fff6e8', 1.05); sun.position.set(-0.45, 1, 0.55); S.add(sun);

    // газон полосами, как на стадионе
    grass = tex(512, 512, (g, w, h) => {
      for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? '#3fa535' : '#4cb83f'; g.fillRect(0, (i * h) / 8, w, h / 8); }
      const r = C.seeded(7); for (let i = 0; i < 2600; i++) { g.fillStyle = 'rgba(' + (r() < 0.5 ? '255,255,255,' : '0,60,0,') + (0.03 + r() * 0.05) + ')'; g.fillRect(r() * w, r() * h, 2, 3); }
    });
    grass.wrapS = grass.wrapT = TH.RepeatWrapping; grass.anisotropy = 4;
    field = new TH.Mesh(new TH.CircleGeometry(1, 128), new TH.MeshLambertMaterial({ map: grass }));
    field.rotation.x = -Math.PI / 2; S.add(field);
    lineMat = new TH.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0.75, depthWrite: false });
    centerRing = new TH.Mesh(new TH.RingGeometry(410, 420, 96), lineMat); centerRing.rotation.x = -Math.PI / 2; centerRing.position.y = 0.6; S.add(centerRing);
    const dot = new TH.Mesh(new TH.CircleGeometry(40, 32), lineMat); dot.rotation.x = -Math.PI / 2; dot.position.y = 0.6; S.add(dot);
    halfLine = new TH.Mesh(new TH.PlaneGeometry(10, 2), lineMat); halfLine.rotation.x = -Math.PI / 2; halfLine.position.y = 0.6; S.add(halfLine);
    // бортик: щиты цветами флагов
    const cols = ['#e53935', '#1e88e5', '#fdd835', '#43a047', '#8e24aa', '#fb8c00', '#00acc1', '#ffffff'];
    boards = tex(1024, 64, (g, w, h) => { const n = 8; for (let i = 0; i < n; i++) { g.fillStyle = cols[i % cols.length]; g.fillRect((i * w) / n, 0, w / n + 1, h); g.fillStyle = i % 8 === 7 ? 'rgba(30,40,90,0.9)' : 'rgba(255,255,255,0.92)'; g.font = 'bold 34px sans-serif'; g.textAlign = 'center'; g.fillText('★ FLAGBALL ★', ((i + 0.5) * w) / n, h * 0.68); } });
    boards.wrapS = TH.RepeatWrapping;
    wallMat = new TH.MeshLambertMaterial({ map: boards, side: TH.DoubleSide, emissive: new TH.Color('#00e676'), emissiveIntensity: 0 });
    wall = new TH.Mesh(new TH.CylinderGeometry(1, 1, 70, 128, 1, true), wallMat); wall.position.y = 35; S.add(wall);
    // за бортиком — трибуны с болельщиками
    const crowd = tex(1024, 256, (g, w, h) => { g.fillStyle = '#2b3a67'; g.fillRect(0, 0, w, h); const r = C.seeded(3); const cc = ['#e53935', '#fdd835', '#ffffff', '#1e88e5', '#43a047', '#ff7043', '#ab47bc']; for (let y = 6; y < h; y += 14) for (let x = 4; x < w; x += 10) { g.fillStyle = cc[(r() * cc.length) | 0]; g.beginPath(); g.arc(x + r() * 3, y + r() * 3, 3.6, 0, 7); g.fill(); } });
    crowd.wrapS = TH.RepeatWrapping;
    stands = new TH.Mesh(new TH.CylinderGeometry(1.35, 1.03, 1, 128, 1, true), new TH.MeshLambertMaterial({ map: crowd, side: TH.BackSide })); S.add(stands);
    outer = new TH.Mesh(new TH.RingGeometry(1, 1.4, 128), new TH.MeshLambertMaterial({ color: '#33427a' })); outer.rotation.x = -Math.PI / 2; outer.position.y = 0.2; S.add(outer);

    // кристаллы вместо точек
    gems = new TH.InstancedMesh(new TH.OctahedronGeometry(1, 0), new TH.MeshStandardMaterial({ roughness: 0.2, metalness: 0, flatShading: true, emissive: new TH.Color('#1a1a1a') }), GEM_CAP);
    gems.instanceMatrix.setUsage(TH.DynamicDrawUsage); gems.frustumCulled = false; S.add(gems);
    { const wc = new TH.Color('#ffffff'); for (let i = 0; i < GEM_CAP; i++) gems.setColorAt(i, wc); gems.instanceColor.setUsage(TH.DynamicDrawUsage); } // цвет у каждого кристалла (нужен до первой отрисовки)
    gems.count = 0;

    // шарик-флаг: флаг спереди (как у Countryballs) — проекция по взгляду камеры, без шва и полюсов
    sphereG = new TH.SphereGeometry(1, 40, 28); eyeG = new TH.SphereGeometry(1, 14, 10); // глазам хватает простой сферы
    flagG = sphereG.clone();
    {
      const D = new TH.Vector3(0, Math.cos(TILT), Math.sin(TILT)).normalize(), RX = new TH.Vector3(1, 0, 0), UP = new TH.Vector3().crossVectors(D, RX).normalize();
      const pos = flagG.attributes.position, uv = flagG.attributes.uv, v = new TH.Vector3();
      for (let i = 0; i < pos.count; i++) { v.fromBufferAttribute(pos, i); uv.setXY(i, 0.5 + 0.49 * v.dot(RX), 0.5 + 0.49 * v.dot(UP)); }
      uv.needsUpdate = true;
    }
    eyeW = new TH.MeshStandardMaterial({ color: '#ffffff', roughness: 0.3 });
    eyeB = new TH.MeshStandardMaterial({ color: '#111111', roughness: 0.2 });
    const sh = tex(128, 128, (g) => { const gr = g.createRadialGradient(64, 64, 4, 64, 64, 62); gr.addColorStop(0, 'rgba(0,30,0,0.55)'); gr.addColorStop(0.6, 'rgba(0,30,0,0.28)'); gr.addColorStop(1, 'rgba(0,30,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); });
    shadowMat = new TH.MeshBasicMaterial({ map: sh, transparent: true, depthWrite: false });
    ringG = new TH.RingGeometry(1.1, 1.24, 64); planeG = new TH.PlaneGeometry(1, 1); magG = new TH.RingGeometry(0.97, 1, 64);
    bubbleMat = new TH.MeshStandardMaterial({ color: '#40c4ff', transparent: true, opacity: 0.25, roughness: 0.05, emissive: new TH.Color('#40c4ff'), emissiveIntensity: 0.25, depthWrite: false });
    boostMat = new TH.MeshBasicMaterial({ color: '#ffd600', transparent: true, opacity: 0.35, depthWrite: false });
    magnetMat = new TH.MeshBasicMaterial({ color: '#ff4081', transparent: true, opacity: 0.45, depthWrite: false });
    R3.ok = true;
    R3.resize();
    return true;
  };

  R3.resize = () => {
    if (!R) return;
    const w = window.innerWidth || 360, h = window.innerHeight || 640;
    pr = Math.min(window.devicePixelRatio || 1, R3.lowRes ? 1 : 2);
    R.setPixelRatio(pr); R.setSize(w, h, false);
    cam.aspect = w / h; cam.updateProjectionMatrix();
  };
  window.addEventListener('resize', () => R3.resize());

  // ---------- шарики ----------
  function flagMat(id) {
    if (flagMats[id]) return flagMats[id];
    const t = new TH.CanvasTexture(C.skinTex(id)); t.encoding = TH.sRGBEncoding; t.anisotropy = 4;
    return (flagMats[id] = new TH.MeshStandardMaterial({ map: t, roughness: 0.32, metalness: 0.05 }));
  }
  const EYE_ACC = { 5: 1, 7: 1, 9: 1 }; // украшения, у которых свои глаза (очки, сердечки, повязка) — 3D-глаза прячем; «глазки» (1) теперь у всех
  function accSprite(id) {
    if (!R3.drawAcc) return null;
    if (!accTex[id]) {
      const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
      R3.drawAcc(g, id, 128, 150, 64);
      const t = new TH.CanvasTexture(c); t.encoding = TH.sRGBEncoding; accTex[id] = new TH.SpriteMaterial({ map: t, transparent: true });
    }
    const sp = new TH.Sprite(accTex[id]); return sp;
  }
  function mkBall(id) {
    const g = new TH.Group();
    const body = new TH.Mesh(flagG, flagMat('US')); g.add(body);
    const eyes = new TH.Group(); body.add(eyes);
    for (const s of [-1, 1]) {
      const e = new TH.Mesh(eyeG, eyeW); e.scale.set(0.2, 0.26, 0.12); e.position.set(s * 0.3, 0.32, 0.88); eyes.add(e);
      const p = new TH.Mesh(eyeG, eyeB); p.scale.set(0.1, 0.13, 0.06); p.position.set(s * 0.3 + 0.04, 0.32, 0.99); eyes.add(p); (eyes.pupils || (eyes.pupils = [])).push(p);
    }
    const shadow = new TH.Mesh(planeG, shadowMat); shadow.rotation.x = -Math.PI / 2; S.add(shadow);
    const ring = new TH.Mesh(ringG, new TH.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0.9, depthWrite: false })); ring.rotation.x = -Math.PI / 2; S.add(ring);
    const bubble = new TH.Mesh(sphereG, bubbleMat); bubble.visible = false; g.add(bubble);
    const ghost = new TH.Mesh(sphereG, boostMat); ghost.visible = false; S.add(ghost);
    const mag = new TH.Mesh(magG, magnetMat); mag.rotation.x = -Math.PI / 2; mag.visible = false; S.add(mag);
    S.add(g);
    const o = { g, body, eyes, shadow, ring, bubble, ghost, mag, skin: '', acc: -1, accSp: null, seen: 0, bob: Math.random() * 6 };
    balls.set(id, o); return o;
  }
  function dropBall(id, o) { o.ring.material.dispose(); S.remove(o.g); S.remove(o.shadow); S.remove(o.ring); S.remove(o.ghost); S.remove(o.mag); if (o.accSp) S.remove(o.accSp); balls.delete(id); }

  // ---------- пилы и бонусы ----------
  function mkSaw() {
    if (!sawG) {
      sawG = { disk: new TH.CylinderGeometry(1, 1, 0.2, 40), tooth: new TH.ConeGeometry(0.15, 0.36, 4), hub: new TH.CylinderGeometry(0.3, 0.3, 0.32, 24),
        m1: new TH.MeshStandardMaterial({ color: '#cfd8dc', metalness: 0.8, roughness: 0.3 }), m2: new TH.MeshStandardMaterial({ color: '#eceff1', metalness: 0.85, roughness: 0.25 }), m3: new TH.MeshStandardMaterial({ color: '#d32f2f', roughness: 0.4 }),
        warn: new TH.MeshBasicMaterial({ color: '#ff1744', transparent: true, opacity: 0.5, depthWrite: false }) };
    }
    const g = new TH.Group(), sp = new TH.Group(); g.add(sp);
    sp.add(new TH.Mesh(sawG.disk, sawG.m1));
    for (let i = 0; i < 16; i++) { const t = new TH.Mesh(sawG.tooth, sawG.m2), a = (i / 16) * Math.PI * 2; t.position.set(Math.cos(a) * 1.12, 0, Math.sin(a) * 1.12); t.rotation.z = -Math.PI / 2; t.rotation.y = -a; sp.add(t); }
    sp.add(new TH.Mesh(sawG.hub, sawG.m3));
    const warn = new TH.Mesh(new TH.RingGeometry(1.45, 1.75, 48), sawG.warn); warn.rotation.x = -Math.PI / 2; warn.position.y = -0.45; g.add(warn);
    g.userData = { sp, warn }; S.add(g); return g;
  }
  const POWC = ['#ffd600', '#ff4081', '#40c4ff'];
  function mkPow() {
    const g = new TH.Group();
    const b = new TH.Mesh(sphereG, new TH.MeshStandardMaterial({ color: '#ffffff', transparent: true, opacity: 0.85, roughness: 0.1, emissiveIntensity: 0.35 }));
    g.add(b); g.userData = { b }; S.add(g); return g;
  }

  // ---------- камера: как 2D-камера (центр и масштаб), только сверху-сзади под углом ----------
  function placeCam(cx, cy, z) {
    const Hw = C.H / Math.max(0.05, z);                  // сколько мира по высоте экрана видно в 2D
    const D = Hw / (2 * Math.tan((FOV * Math.PI) / 360));
    cam.position.set(cx, D * Math.cos(TILT), cy + D * Math.sin(TILT));
    cam.lookAt(cx, 0, cy);
    cam.near = Math.max(10, D * 0.05); cam.far = D * 4 + 4000; cam.updateProjectionMatrix();
    camUp.set(0, 1, 0).applyQuaternion(cam.quaternion);
  }
  // точка мира → экран (логические единицы игры C.W × C.H); [x, y, пикселей на единицу мира]
  R3.project = (x, h, y) => {
    v3.set(x, h, y).project(cam);
    const sx = (v3.x * 0.5 + 0.5) * C.W, sy = (-v3.y * 0.5 + 0.5) * C.H;
    v3b.set(x, h, y).sub(cam.position); const dist = v3b.length();
    const k = C.H / (2 * Math.tan((FOV * Math.PI) / 360) * dist);
    return [sx, sy, k, v3.z < 1];
  };

  // ---------- кадр ----------
  // v: { cam:{x,y,z}, R, grow, balls:[{id,x,y,r,skin,acc,vx,vy,ring,rk,fl,alpha}], dots, powers, saws, sawSpin, sawDanger, t }
  R3.render = (v) => {
    if (!R3.ok) return;
    frames++;
    const t = v.t;
    placeCam(v.cam.x, v.cam.y, v.cam.z);
    const RR = v.R;
    field.scale.set(RR, RR, 1); grass.repeat.set(RR / 360, RR / 360);
    halfLine.scale.set(1, RR - 30, 1);
    if (Math.abs(edgeR - RR) > 12) { edgeR = RR; if (edgeRing) { S.remove(edgeRing); edgeRing.geometry.dispose(); } edgeRing = new TH.Mesh(new TH.RingGeometry(RR - 44, RR - 30, 128), lineMat); edgeRing.rotation.x = -Math.PI / 2; edgeRing.position.y = 0.6; S.add(edgeRing); }
    wall.scale.set(RR + 10, 1, RR + 10); boards.repeat.set(-Math.max(4, Math.round(RR / 120)), 1); // минус — надписи на щитах читаются изнутри арены
    wallMat.emissiveIntensity = v.grow > 0 ? 0.35 + 0.35 * Math.sin(t * 10) : 0;
    stands.scale.set(RR + 60, 520, RR + 60); stands.position.y = 260; stands.material.map.repeat.set(Math.max(6, Math.round(RR / 200)), 1);
    outer.scale.set(RR + 10, RR + 10, 1);

    // что видно: прямоугольник вокруг камеры (дальний край экрана шире из-за перспективы)
    const vw = (C.W / v.cam.z) * 0.75 + 260, vhN = (C.H / v.cam.z) * 0.6 + 200, vhF = (C.H / v.cam.z) * 1.1 + 400;
    const x0 = v.cam.x - vw, x1 = v.cam.x + vw, y0 = v.cam.y - vhF, y1 = v.cam.y + vhN;

    // кристаллы
    let n = 0;
    for (const p of v.dots.values()) {
      if (p.hid || p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) continue;
      if (n >= GEM_CAP) break;
      const s = p.r, ph = (p.x * 0.013 + p.y * 0.007);
      e3.set(0.3, t * 1.4 + ph, 0); q4.setFromEuler(e3);
      v3.set(p.x, s * 1.35 + Math.sin(t * 2.5 + ph) * 4, p.y); s3.set(s * 0.85, s * 1.25, s * 0.85);
      m4.compose(v3, q4, s3); gems.setMatrixAt(n, m4); gems.setColorAt(n, colOf(p.c)); n++;
    }
    gems.count = n; gems.instanceMatrix.needsUpdate = true; if (gems.instanceColor) gems.instanceColor.needsUpdate = true;

    // шарики
    for (const o of balls.values()) o.seen = 0;
    for (const b of v.balls) {
      let o = balls.get(b.id); if (!o) o = mkBall(b.id);
      o.seen = 1;
      const r = Math.max(0.5, b.r), vis = r > 1 && b.x + r * 2 > x0 && b.x - r * 2 < x1 && b.y + r * 2 > y0 && b.y - r * 2 < y1;
      o.g.visible = o.shadow.visible = vis; o.ring.visible = vis && !!b.ring;
      if (!vis) { o.ghost.visible = o.mag.visible = false; if (o.accSp) o.accSp.visible = false; continue; }
      if (o.skin !== b.skin) { o.skin = b.skin; o.body.material = flagMat(b.skin); }
      const sp = Math.hypot(b.vx || 0, b.vy || 0), bob = 1 + Math.sin(t * 6 + o.bob) * 0.025;
      o.g.position.set(b.x, r * bob, b.y); o.g.scale.set(r, r * bob, r);
      // наклон по ходу движения и взгляд туда, куда едет
      const lx = C.clamp((b.vx || 0) / 900, -0.3, 0.3), ly = C.clamp((b.vy || 0) / 900, -0.3, 0.3);
      o.body.rotation.set(ly * 0.6, 0, -lx * 0.6);
      o.eyes.rotation.set(-0.72 - ly * 0.6, lx * 1.3, 0); // глаза — на видной камере стороне, чуть смотрят по ходу
      o.eyes.visible = !EYE_ACC[b.acc];
      o.shadow.position.set(b.x + r * 0.22, 0.4, b.y + r * 0.12); o.shadow.scale.set(r * 2.5, r * 2.3, 1);
      if (b.ring) { o.ring.position.set(b.x, 0.8, b.y); o.ring.scale.set(r, r, 1); o.ring.material.color.copy(colOf(b.ring)); o.ring.material.opacity = b.rk || 0.9; }
      // украшение — плоская наклейка к камере (рисуется тем же кодом, что в 2D)
      if (o.acc !== b.acc) { o.acc = b.acc; if (o.accSp) { S.remove(o.accSp); o.accSp = null; } if (b.acc && !(b.acc === 1)) { o.accSp = accSprite(b.acc); if (o.accSp) S.add(o.accSp); } }
      if (o.accSp) {
        o.accSp.visible = true;
        v3.copy(cam.position).sub(o.g.position).normalize();
        o.accSp.position.copy(o.g.position).addScaledVector(v3, r * 1.05).addScaledVector(camUp, r * 0.344);
        o.accSp.scale.set(r * 4, r * 4, 1);
      }
      // щит, ускорение, магнит
      o.bubble.visible = !!(b.fl & 1); if (o.bubble.visible) { const k = 1.2 + Math.sin(t * 8) * 0.03; o.bubble.scale.set(k, k / bob, k); }
      o.ghost.visible = !!(b.fl & 2) && sp > 50; if (o.ghost.visible) { o.ghost.position.set(b.x - (b.vx || 0) * 0.08, r, b.y - (b.vy || 0) * 0.08); o.ghost.scale.setScalar(r * 0.96); }
      o.mag.visible = !!(b.fl & 4); if (o.mag.visible) { const mr = r + 170 - ((t * 80) % 40); o.mag.position.set(b.x, 1, b.y); o.mag.scale.set(mr, mr, 1); }
      if (b.alpha !== undefined && b.alpha < 1) { o.g.visible = b.alpha > 0.05; }
    }
    for (const [id, o] of balls) if (!o.seen) dropBall(id, o);

    // пилы
    while (saws.length < v.saws.length) saws.push(mkSaw());
    saws.forEach((g, i) => {
      const s = v.saws[i]; g.visible = !!s; if (!s) return;
      g.position.set(s.x, 26, s.y); g.scale.setScalar(v.sawR); g.userData.sp.rotation.y = v.sawSpin;
      g.userData.warn.visible = !!v.sawDanger;
    });
    // бонусы
    while (pows.length < v.powers.length) pows.push(mkPow());
    pows.forEach((g, i) => {
      const p = v.powers[i]; g.visible = !!p; if (!p) return;
      const s = 1 + Math.sin(p.a * 5) * 0.08, col = colOf(POWC[p.k] || POWC[0]);
      g.position.set(p.x, 62 + Math.sin(p.a * 3) * 8, p.y); g.scale.setScalar(36 * s);
      g.userData.b.material.color.copy(col); g.userData.b.material.emissive.copy(col);
    });

    R.render(S, cam);
    // слабое устройство: если долго медленно — рисуем в меньшем разрешении
    if (!R3.lowRes && v.dt > 0) { slowT = v.dt > 0.028 ? slowT + v.dt : Math.max(0, slowT - v.dt * 0.5); if (slowT > 3 && frames > 120) { R3.lowRes = true; R3.resize(); } }
  };
  R3.info = () => ({ ok: R3.ok, lowRes: !!R3.lowRes, pr, calls: R ? R.info.render.calls : 0, tris: R ? R.info.render.triangles : 0, balls: balls.size, gems: gems ? gems.count : 0 });
})();
