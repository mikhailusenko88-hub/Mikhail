'use strict';
/* Игра 4: «Растущий шарик 3D» — раннер на three.js. Ворота +/×/−/÷, пилы, молоты, в финале кирпичные стены-множители. */
(function () {
  const C = window.Core, T3 = window.THREE;
  const ROAD = 3, SPEED = 10.5, SEG = 4;
  const glCanvas = document.getElementById('gl');
  let renderer, scene, camera, sun, ball, ballMat, levelGroup, water, clouds = [];
  let run = null, phase = 'ready', touchX = null, popups = [], endT = -1, endKind = null, boostUsed = false, shake = 0, hitFlash = 0, idleT = 0, flash = 0, slowT = 0;
  const camPos = new T3.Vector3(0, 5, 8), camLook = new T3.Vector3(0, 0.5, -6), tmpV = new T3.Vector3();

  const radius = (n) => Math.min(1.35, 0.42 + 0.062 * Math.sqrt(Math.max(1, n)));
  const OPS = {
    add: (v) => ({ t: '+' + v, good: true, f: (n) => n + v }),
    mul: (v) => ({ t: '×' + v, good: true, f: (n) => n * v }),
    sub: (v) => ({ t: '−' + v, good: false, f: (n) => n - v }),
    div: (v) => ({ t: '÷' + v, good: false, f: (n) => Math.floor(n / v) }),
  };

  // ---------- общие материалы и геометрии ----------
  const MAT = {}, GEO = {};
  const mat = (key, make) => MAT[key] || (MAT[key] = make());
  const lin = (c) => new T3.Color(c).convertSRGBToLinear();
  function std(color, o = {}) { if (o.emissive !== undefined) o.emissive = lin(o.emissive); return new T3.MeshStandardMaterial(Object.assign({ roughness: 0.6, metalness: 0.05 }, o, { color: lin(color) })); }

  function textTexture(text, bg, border, w = 256, h = 192, size = 104) {
    const cv = document.createElement('canvas'); cv.width = w; cv.height = h; const g = cv.getContext('2d');
    if (bg) { g.fillStyle = bg; C.rr(g, 6, 6, w - 12, h - 12, 26); g.fill(); }
    if (border) { g.strokeStyle = border; g.lineWidth = 10; C.rr(g, 6, 6, w - 12, h - 12, 26); g.stroke(); }
    g.font = C.font(size); g.textAlign = 'center'; g.textBaseline = 'middle';
    g.lineWidth = size * 0.14; g.strokeStyle = 'rgba(0,0,0,0.45)'; g.lineJoin = 'round'; g.strokeText(text, w / 2, h / 2 + 4);
    g.fillStyle = '#fff'; g.fillText(text, w / 2, h / 2 + 4);
    const t = new T3.CanvasTexture(cv); t.encoding = T3.sRGBEncoding; t.anisotropy = 4; return t;
  }
  function skyTexture() {
    const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256; const g = cv.getContext('2d');
    const gr = g.createLinearGradient(0, 0, 0, 256); gr.addColorStop(0, '#3a8dde'); gr.addColorStop(0.55, '#9fd4ff'); gr.addColorStop(1, '#e6f6ff');
    g.fillStyle = gr; g.fillRect(0, 0, 4, 256); const t = new T3.CanvasTexture(cv); t.encoding = T3.sRGBEncoding; return t;
  }
  function flagTexture(id) {
    const cv = document.createElement('canvas'); cv.width = 512; cv.height = 256; const g = cv.getContext('2d');
    for (let k = 0; k < 2; k++) { g.save(); g.translate(k * 256, 0); C.skinById(id).d(g, 256, 256); g.restore(); }
    const t = new T3.CanvasTexture(cv); t.encoding = T3.sRGBEncoding; t.anisotropy = 4; return t;
  }

  // ---------- сцена ----------
  function initThree() {
    renderer = new T3.WebGLRenderer({ canvas: glCanvas, antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = T3.PCFSoftShadowMap;
    renderer.outputEncoding = T3.sRGBEncoding;
    scene = new T3.Scene();
    scene.background = skyTexture();
    scene.fog = new T3.Fog(0xcdeaff, 45, 150);
    camera = new T3.PerspectiveCamera(58, 1, 0.1, 400);
    scene.add(new T3.HemisphereLight(lin(0xe8f6ff), lin(0x2a6fb0), 0.9));
    sun = new T3.DirectionalLight(0xfff1d8, 1.05); sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024); Object.assign(sun.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 1, far: 60 }); sun.shadow.bias = -0.0008;
    scene.add(sun, sun.target);
    const wg = new T3.PlaneGeometry(800, 800, 1, 1); wg.rotateX(-Math.PI / 2);
    water = new T3.Mesh(wg, std(0x1ea3e6, { roughness: 0.18, metalness: 0.25 })); water.position.y = -4; water.receiveShadow = true; scene.add(water);
    const cg = new T3.SphereGeometry(1, 12, 10), cm = std(0xffffff, { roughness: 1, emissive: 0xffffff, emissiveIntensity: 0.35 });
    for (let i = 0; i < 14; i++) {
      const grp = new T3.Group();
      for (let k = 0; k < 4; k++) { const m = new T3.Mesh(cg, cm); m.scale.set(3 + Math.random() * 3, 1.6 + Math.random(), 2 + Math.random() * 2); m.position.set(k * 3.2 - 5, Math.random(), Math.random() * 2); grp.add(m); }
      grp.position.set((Math.random() < 0.5 ? -1 : 1) * (25 + Math.random() * 40), 14 + Math.random() * 12, -Math.random() * 300); scene.add(grp); clouds.push(grp);
    }
    ballMat = std(0xffffff, { roughness: 0.32, metalness: 0.06 });
    ball = new T3.Mesh(new T3.SphereGeometry(1, 48, 32), ballMat); ball.castShadow = true; scene.add(ball);
    GEO.tile = new T3.BoxGeometry(ROAD * 2, 0.5, SEG); GEO.curb = new T3.BoxGeometry(0.35, 0.35, SEG / 2);
    GEO.pillar = new T3.CylinderGeometry(0.45, 0.6, 4, 10); GEO.coin = new T3.CylinderGeometry(0.3, 0.3, 0.07, 22); GEO.coin.rotateX(Math.PI / 2);
    GEO.post = new T3.CylinderGeometry(0.09, 0.09, 2.6, 10); GEO.bar = new T3.BoxGeometry(ROAD * 2 + 0.3, 0.16, 0.16);
    GEO.panel = new T3.PlaneGeometry(ROAD - 0.15, 2.2); GEO.brick = new T3.BoxGeometry(0.96, 0.56, 0.7);
    GEO.trunk = new T3.CylinderGeometry(0.15, 0.22, 1.6, 6); GEO.crown = new T3.IcosahedronGeometry(1, 0);
    GEO.island = new T3.CylinderGeometry(1, 1.3, 1, 12);
    const sh = new T3.Shape(); for (let i = 0; i < 32; i++) { const a = (i / 32) * Math.PI * 2, r = i % 2 ? 0.62 : 0.5; if (i === 0) sh.moveTo(Math.cos(a) * r, Math.sin(a) * r); else sh.lineTo(Math.cos(a) * r, Math.sin(a) * r); }
    const hole = new T3.Path(); hole.absarc(0, 0, 0.12, 0, Math.PI * 2, true); sh.holes.push(hole);
    GEO.saw = new T3.ExtrudeGeometry(sh, { depth: 0.08, bevelEnabled: false });
    GEO.hammerHead = new T3.BoxGeometry(1.3, 0.9, 0.9); GEO.hammerArm = new T3.CylinderGeometry(0.07, 0.07, 3.6, 8);
    resize3();
  }
  function resize3() { if (!renderer) return; const w = window.innerWidth, h = window.innerHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.fov = w / h > 1 ? 50 : 62; camera.updateProjectionMatrix(); }
  window.addEventListener('resize', resize3);

  function disposeLevel() {
    if (!levelGroup) return;
    levelGroup.traverse((o) => { if (o.userData.ownTex) o.userData.ownTex.dispose(); if (o.userData.ownMat) o.userData.ownMat.dispose(); if (o.userData.ownGeo) o.geometry.dispose(); if (o.isInstancedMesh && o.dispose) o.dispose(); });
    scene.remove(levelGroup); levelGroup = null;
  }

  // ---------- уровень ----------
  function makeRun(n) {
    const rng = C.seeded(300 + n * 13);
    const len = 95 + (n - 1) * 25;
    const objs = [];
    const d = n === 1 ? 0 : Math.min(1, 0.35 + (n - 2) * 0.12);
    let z = 14;
    while (z < len - 6) {
      let L, Rr;
      const good = () => (rng() < 0.62 ? OPS.add(5 + Math.floor(rng() * 4) * 5) : OPS.mul(2 + (rng() < 0.2 ? 1 : 0)));
      const bad = () => (rng() < 0.65 ? OPS.sub(5 + Math.floor(rng() * (3 + d * 4)) * 5) : OPS.div(2));
      if (rng() < 0.35 - d * 0.15) { L = good(); Rr = good(); } else { L = good(); Rr = bad(); }
      if (rng() < 0.5) [L, Rr] = [Rr, L];
      objs.push({ type: 'gate', z, L, R: Rr, done: false });
      const cx = (rng() - 0.5) * 4;
      for (let k = 0; k < 6; k++) objs.push({ type: 'coin', z: z + 2.6 + k * 0.7, x: cx, taken: false });
      const r = rng();
      if (r < (n === 1 ? 0.25 : 0.45 + d * 0.3)) objs.push({ type: 'saw', z: z + 6, x0: (rng() - 0.5) * 3, amp: 1.2 + rng() * 1.2, w: 1.4 + rng() * 1.4 + d, ph: rng() * 6, done: false });
      else if (n >= 2 && r < 0.75 + d * 0.2) objs.push({ type: 'hammer', z: z + 6, w: 1.6 + rng() * 1.0 + d, ph: rng() * 6, done: false });
      z += 9 + rng() * 3;
    }
    // стены считаются от лучшего возможного числа: хорошая игра пробивает почти все, средняя — половину, первые 2 — всегда
    let best = 10; for (const o of objs) if (o.type === 'gate') best = Math.max(0, Math.round(Math.max(o.L.f(best), o.R.f(best))));
    // 1-й заезд: все 10 стен пробиваются гарантированно (×10, чтобы зацепить). Со 2-го — намного тяжелее и дальше растёт.
    const K = [0.05, 0.12, 0.22, 0.34, 0.47, 0.6, 0.72, 0.84, 0.95, 1.08];
    const hard = 1 + Math.max(0, n - 2) * 0.06;
    K.forEach((k, i) => {
      const val = n === 1 ? 1 + i : Math.max(10 + i * 5, Math.round((best * k * hard) / 5) * 5);
      objs.push({ type: 'wall', z: len + 3 + i * 2.8, val, mult: [1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10][i], idx: i, broken: false });
    });
    objs.sort((a, b) => a.z - b.z);
    const R = { n, len, objs, z: 0, x: 0, vx: 0, num: 10, roll: 0, coins: 0, inv: 0, mult: 1, finaleOn: false, stopZ: null, squash: 0, debris: [], end: len + 3 + 10 * 2.8 + 6 };
    build3D(R, rng);
    return R;
  }

  function build3D(R, rng) {
    disposeLevel();
    levelGroup = new T3.Group(); scene.add(levelGroup);
    const nTiles = Math.ceil((R.end + 10) / SEG) + 4;
    const tA = new T3.InstancedMesh(GEO.tile, mat('tileA', () => std(0x5b9bff, { roughness: 0.55 })), nTiles), tB = new T3.InstancedMesh(GEO.tile, mat('tileB', () => std(0x86b6ff, { roughness: 0.55 })), nTiles);
    const cR = new T3.InstancedMesh(GEO.curb, mat('curbR', () => std(0xff4d5e)), nTiles * 4), cW = new T3.InstancedMesh(GEO.curb, mat('curbW', () => std(0xffffff)), nTiles * 4);
    const pil = new T3.InstancedMesh(GEO.pillar, mat('pillar', () => std(0xe0e7ef, { roughness: 0.8 })), nTiles);
    const m4 = new T3.Matrix4(); let ia = 0, ib = 0, ir = 0, iw = 0, ip = 0;
    for (let i = -2; i < nTiles - 2; i++) {
      const zc = -(i * SEG + SEG / 2);
      if (zc < -R.len) { /* финишная зона рисуется отдельно */ } else { m4.makeTranslation(0, -0.25, zc); if (i % 2) tA.setMatrixAt(ia++, m4); else tB.setMatrixAt(ib++, m4); }
      for (const s of [-1, 1]) for (let k = 0; k < 2; k++) { m4.makeTranslation(s * (ROAD + 0.17), 0.1, zc - SEG / 4 + k * SEG / 2); if ((i * 2 + k) % 2) cR.setMatrixAt(ir++, m4); else cW.setMatrixAt(iw++, m4); }
      if (i % 3 === 0) { m4.makeTranslation(0, -2.4, zc); pil.setMatrixAt(ip++, m4); }
    }
    tA.count = ia; tB.count = ib; cR.count = ir; cW.count = iw; pil.count = ip;
    tA.receiveShadow = true; tB.receiveShadow = true;
    for (const m of [tA, tB, cR, cW, pil]) levelGroup.add(m);
    const fin = new T3.Mesh(new T3.BoxGeometry(ROAD * 2, 0.52, R.end - R.len + 8), mat('finTile', () => std(0xb57ee6, { roughness: 0.55 })));
    fin.position.set(0, -0.24, -(R.len + (R.end - R.len) / 2)); fin.receiveShadow = true; fin.userData.ownGeo = true; levelGroup.add(fin);
    // острова с деревьями
    const nIsl = Math.ceil(R.end / 14) + 4;
    const trunks = new T3.InstancedMesh(GEO.trunk, mat('trunk', () => std(0x8d5524)), nIsl * 4), crowns = new T3.InstancedMesh(GEO.crown, mat('crown', () => std(0x4caf50, { flatShading: true })), nIsl * 4);
    const isl = new T3.InstancedMesh(GEO.island, mat('sand', () => std(0xffe0a3, { roughness: 0.9 })), nIsl), grass = new T3.InstancedMesh(GEO.island, mat('grass', () => std(0x7cd36b, { roughness: 0.9 })), nIsl);
    let it = 0;
    const q = new T3.Quaternion(), sc = new T3.Vector3(), pos = new T3.Vector3();
    for (let i = 0; i < nIsl; i++) {
      const side = i % 2 ? 1 : -1, x = side * (11 + rng() * 22), z = -(i * 14 + rng() * 8 - 10), s = 3 + rng() * 4;
      pos.set(x, -3.8, z); sc.set(s, 1.2, s); m4.compose(pos, q.identity(), sc); isl.setMatrixAt(i, m4);
      pos.set(x, -3.15, z); sc.set(s * 0.82, 0.3, s * 0.82); m4.compose(pos, q, sc); grass.setMatrixAt(i, m4);
      const k = 1 + Math.floor(rng() * 3);
      for (let j = 0; j < k; j++) {
        const tx = x + (rng() - 0.5) * s, tz = z + (rng() - 0.5) * s, h = 0.8 + rng() * 0.6;
        pos.set(tx, -2.2, tz); sc.set(1, h, 1); m4.compose(pos, q, sc); trunks.setMatrixAt(it, m4);
        pos.set(tx, -1.3 + h * 0.5, tz); sc.set(0.9 + rng() * 0.6, 1.1 + rng() * 0.5, 0.9 + rng() * 0.6); m4.compose(pos, q, sc); crowns.setMatrixAt(it, m4); it++;
      }
    }
    trunks.count = it; crowns.count = it; for (const m of [isl, grass, trunks, crowns]) levelGroup.add(m);
    // объекты
    for (const o of R.objs) {
      if (o.type === 'gate') {
        const g = new T3.Group(); g.position.z = -o.z;
        for (const x of [-ROAD - 0.05, 0, ROAD + 0.05]) { const p = new T3.Mesh(GEO.post, mat('post', () => std(0xffffff, { metalness: 0.3, roughness: 0.3 }))); p.position.set(x, 1.3, 0); p.castShadow = true; g.add(p); }
        const bar = new T3.Mesh(GEO.bar, MAT.post); bar.position.y = 2.6; g.add(bar);
        o.panels = [];
        for (const side of [-1, 1]) {
          const op = side < 0 ? o.L : o.R;
          const tex = textTexture(op.t, op.good ? 'rgba(0,200,120,0.55)' : 'rgba(240,60,70,0.55)', op.good ? '#69f0ae' : '#ff8a80');
          const m = new T3.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, side: T3.DoubleSide });
          const pl = new T3.Mesh(GEO.panel, m); pl.position.set(side * ROAD / 2, 1.3, 0); pl.userData.ownTex = tex; pl.userData.ownMat = m; g.add(pl); o.panels.push(pl);
        }
        o.mesh = g; levelGroup.add(g);
      } else if (o.type === 'coin') {
        const m = new T3.Mesh(GEO.coin, mat('coin', () => std(0xffc928, { metalness: 0.7, roughness: 0.25, emissive: 0x6b4a00, emissiveIntensity: 0.5 })));
        m.position.set(o.x, 0.55, -o.z); m.castShadow = true; o.mesh = m; levelGroup.add(m);
      } else if (o.type === 'saw') {
        const g = new T3.Group(); g.position.z = -o.z;
        const rail = new T3.Mesh(GEO.bar, mat('rail', () => std(0x546e7a, { metalness: 0.5 }))); rail.position.y = 0.75; rail.scale.set(1, 0.6, 0.6); g.add(rail);
        const saw = new T3.Mesh(GEO.saw, mat('saw', () => std(0xcfd8dc, { metalness: 0.85, roughness: 0.25 }))); saw.scale.setScalar(1.25); saw.castShadow = true; saw.position.y = 0.78; g.add(saw);
        o.mesh = g; o.saw = saw; o.cx = o.x0; levelGroup.add(g);
      } else if (o.type === 'hammer') {
        const g = new T3.Group(); g.position.set(0, 4.6, -o.z);
        const top = new T3.Mesh(GEO.bar, mat('rail', () => std(0x546e7a, { metalness: 0.5 }))); top.scale.set(0.3, 1, 1); g.add(top);
        const piv = new T3.Group(); g.add(piv);
        const arm = new T3.Mesh(GEO.hammerArm, mat('arm', () => std(0x8d6e63))); arm.position.y = -1.8; piv.add(arm);
        const head = new T3.Mesh(GEO.hammerHead, mat('hammer', () => std(0xff7043, { roughness: 0.4 }))); head.position.y = -3.6; head.castShadow = true; piv.add(head);
        o.mesh = g; o.piv = piv; o.ang = 0; levelGroup.add(g);
      } else if (o.type === 'wall') {
        const g = new T3.Group(); g.position.z = -o.z; o.bricks = [];
        const col = new T3.Color().setHSL((200 - o.idx * 20) / 360, 0.7, 0.55).getHex();
        const bm = std(col, { roughness: 0.55 }); g.userData.ownMat = bm;
        const rows = 3 + Math.floor(o.idx / 3);
        for (let r = 0; r < rows; r++) for (let c = 0; c < 6; c++) {
          const b = new T3.Mesh(GEO.brick, bm); b.position.set(-ROAD + 0.5 + c, 0.28 + r * 0.58, 0); b.castShadow = true; b.receiveShadow = true; g.add(b); o.bricks.push(b);
        }
        const tex = textTexture(String(o.val), null, null, 256, 128, 92), lm = new T3.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false });
        const lab = new T3.Mesh(new T3.PlaneGeometry(2.4, 1.2), lm); lab.position.set(0, rows * 0.58 * 0.5 + 0.1, 0.42); lab.userData.ownTex = tex; lab.userData.ownMat = lm; lab.userData.ownGeo = true; g.add(lab);
        const tex2 = textTexture('×' + o.mult, 'rgba(255,193,7,0.9)', null, 192, 96, 64), lm2 = new T3.MeshBasicMaterial({ map: tex2, transparent: true, depthWrite: false });
        const lab2 = new T3.Mesh(new T3.PlaneGeometry(1.3, 0.65), lm2); lab2.position.set(ROAD + 1.2, 1.2, 0); lab2.userData.ownTex = tex2; lab2.userData.ownMat = lm2; lab2.userData.ownGeo = true; g.add(lab2);
        o.mesh = g; o.label = lab; levelGroup.add(g);
      }
    }
    if (ballMat.map) ballMat.map.dispose();
    ballMat.map = flagTexture(C.mySkin()); ballMat.needsUpdate = true;
  }

  function toScreen(x, y, z) { tmpV.set(x, y, z).project(camera); return { x: (tmpV.x * 0.5 + 0.5) * C.W, y: (-tmpV.y * 0.5 + 0.5) * C.H }; }
  function pop(text, good, mult) { for (const p of popups) p.t = Math.max(p.t, 0.7); popups.push({ text, good, t: 0, mult }); }
  function burstAtBall(color, n, sp) { const r = radius(run.num); const p = toScreen(run.x, r, -run.z); C.burst(p.x, p.y, color, n, sp); }

  const game = {
    id: 'runner',
    init() { initThree(); run = makeRun(C.save.level); phase = 'ready'; },
    resize() { resize3(); },
    startLevel(n) { run = makeRun(n); phase = 'ready'; popups = []; endT = -1; endKind = null; boostUsed = false; ball.visible = true; },
    toHome() { run = makeRun(C.save.level); phase = 'ready'; ball.visible = true; },
    revive() { run.num = 15; run.inv = 1.5; phase = 'run'; endT = -1; endKind = null; ball.visible = true; pop('+15', true); },
    onDown(x) { touchX = x; if (C.state === 'play' && phase === 'ready') { phase = 'run'; C.sfx('whoosh'); } },
    onMove(x) { if (touchX === null) return; if (phase === 'run') run.x = C.clamp(run.x + (x - touchX) * 0.016, -ROAD + 0.45, ROAD - 0.45); touchX = x; },
    onUp() { touchX = null; },
    onKey(k, down) { if (down && C.state === 'play' && phase === 'ready' && ['ArrowLeft', 'ArrowRight', 'KeyA', 'KeyD', 'Space', 'ArrowUp'].includes(k)) { phase = 'run'; C.sfx('whoosh'); } },

    update(dt) {
      if (!run) return;
      idleT += dt; flash = Math.max(0, flash - dt * 2.5);
      if (slowT > 0) { slowT -= dt; dt *= 0.3; }
      for (const p of popups) p.t += dt; popups = popups.filter((p) => p.t < 1);
      shake = Math.max(0, shake - dt * 3); hitFlash = Math.max(0, hitFlash - dt * 3);
      for (const o of run.objs) {
        if (o.z < run.z - 10 || o.z > run.z + 90) continue;
        if (o.type === 'coin' && o.mesh) o.mesh.rotation.y += dt * 4;
        if (o.type === 'saw') { o.cx = o.x0 + Math.sin(C.t * o.w + o.ph) * o.amp; o.saw.position.x = o.cx; o.saw.rotation.z -= dt * 14; }
        if (o.type === 'hammer') { o.ang = Math.sin(C.t * o.w + o.ph) * 1.05; o.piv.rotation.z = o.ang; }
        if ((o.type === 'gate' || o.type === 'saw' || o.type === 'hammer') && o.mesh && o.mesh.visible && run.z > o.z + 1.4) o.mesh.visible = false;
        if (o.type === 'gate' && o.done && o.panels) for (const p of o.panels) if (p.userData.fade !== undefined) { p.userData.fade = Math.min(1, p.userData.fade + dt * 4); p.scale.setScalar(1 + p.userData.fade * 0.6); p.material.opacity = 1 - p.userData.fade; }
      }
      for (let i = run.debris.length - 1; i >= 0; i--) {
        const d = run.debris[i]; d.vy -= 22 * dt; d.m.position.x += d.vx * dt; d.m.position.y += d.vy * dt; d.m.position.z += d.vz * dt;
        d.m.rotation.x += d.rx * dt; d.m.rotation.y += d.ry * dt; d.life -= dt; if (d.life <= 0 || d.m.position.y < -6) { d.m.visible = false; run.debris.splice(i, 1); }
      }
      if (C.state !== 'play' || phase !== 'run') return;
      run.inv = Math.max(0, run.inv - dt); run.squash = Math.max(0, run.squash - dt * 4);
      if (C.keyDir()) run.x = C.clamp(run.x + C.keyDir() * 7.5 * dt, -ROAD + 0.45, ROAD - 0.45);
      const r = radius(run.num), z0 = run.z, speed = run.stopZ !== null ? 0 : SPEED;
      run.z += speed * dt; run.roll += (speed / r) * dt;
      for (const o of run.objs) {
        if (o.z < z0 - 3 || o.z > run.z + 3) continue;
        if (o.type === 'gate' && !o.done && z0 < o.z && run.z >= o.z) {
          o.done = true; const left = run.x < 0, op = left ? o.L : o.R; run.num = Math.max(0, Math.round(op.f(run.num)));
          const p = o.panels[left ? 0 : 1]; p.userData.fade = 0; o.panels[left ? 1 : 0].visible = false;
          pop(op.t, op.good); C.sfx(op.good ? 'gate' : 'hit'); run.squash = 1; burstAtBall(op.good ? '#69f0ae' : '#ff5252', 18, 380);
        }
        if (o.type === 'coin' && !o.taken && Math.abs(o.z - run.z) < 0.6 && Math.abs(o.x - run.x) < r + 0.35) { o.taken = true; o.mesh.visible = false; run.coins++; C.sfx('coin'); }
        if (o.type === 'saw' && !o.done && Math.abs(o.z - run.z) < 0.5 && Math.abs(o.cx - run.x) < r + 0.55 && run.inv <= 0) { o.done = true; hit(); }
        if (o.type === 'hammer' && !o.done && Math.abs(o.z - run.z) < 0.6 && run.inv <= 0) {
          const hx = Math.sin(o.ang) * 3.6, hy = 4.6 - Math.cos(o.ang) * 3.6;
          if (Math.abs(hx - run.x) < r + 0.65 && hy < r * 2 + 0.45) { o.done = true; hit(); run.vx = Math.sign(run.x - hx || 1) * 6; }
        }
        if (o.type === 'wall' && !o.broken && run.z + r >= o.z && run.stopZ === null) {
          if (run.num >= o.val) { o.broken = true; run.mult = o.mult; smash(o); }
          else { run.stopZ = run.z; run.z -= 0.6; run.squash = 1; C.sfx('hit'); endT = 1.4; endKind = 'win'; shake = 0.8; flash = 0.5; o.mesh.position.x = 0; o.wobble = 1; }
        }
      }
      if (run.z > run.len) run.x += (0 - run.x) * Math.min(1, dt * 3);
      if (run.vx) { run.x = C.clamp(run.x + run.vx * dt, -ROAD + 0.45, ROAD - 0.45); run.vx *= 1 - dt * 6; if (Math.abs(run.vx) < 0.05) run.vx = 0; }
      if (run.z > run.end - 4 && endT < 0) { run.stopZ = run.z; endT = 1.0; endKind = 'win'; }
      if (run.num <= 0 && endT < 0) { endT = 0.7; endKind = 'fail'; C.sfx('pop'); burstAtBall('#ff5252', 30, 520); ball.visible = false; }
      if (endT > 0 && C.state === 'play') {
        endT -= dt;
        if (endT <= 0) {
          if (endKind === 'win') { const st = run.mult >= 3 ? 3 : run.mult >= 1.5 ? 2 : 1; C.win({ stars: st, coins: Math.round((20 + run.coins * 2) * run.mult) }); }
          else C.fail({ revive: true });
        }
      }
    },

    draw(ctx) {
      ctx.clearRect(0, 0, C.W, C.H);
      if (!run || !renderer) return;
      const r = radius(run.num), sq = 1 + run.squash * 0.18;
      ball.scale.set(r * sq, r / sq, r * sq);
      ball.position.set(run.x, r / sq, -run.z);
      ball.rotation.set(-run.roll, 0, -run.vx * 0.04);
      ballMat.emissive.setRGB(hitFlash * 0.8, 0, 0);
      if (run.inv > 0 && Math.sin(C.realT * 30) > 0.3) ballMat.emissive.setRGB(0.4, 0.4, 0.4);
      const homeOrbit = C.state === 'home' ? Math.sin(idleT * 0.4) * 1.5 : 0;
      const fz = run.finaleOn ? 1.6 : 0;
      const tp = new T3.Vector3(run.x * 0.55 + homeOrbit, 3.4 + r * 1.7 + fz * 0.6, -run.z + 6.4 + r * 2.4 + fz);
      const tl = new T3.Vector3(run.x * 0.75, r * 0.9, -run.z - 6);
      camPos.lerp(tp, 0.12); camLook.lerp(tl, 0.15);
      camera.position.copy(camPos); if (shake > 0) camera.position.x += (Math.random() - 0.5) * shake * 0.6;
      camera.lookAt(camLook);
      sun.position.set(run.x + 7, 16, -run.z + 7); sun.target.position.set(run.x, 0, -run.z - 3);
      water.position.z = -run.z;
      for (const c of clouds) if (c.position.z > -run.z + 30) c.position.z -= 330;
      renderer.render(scene, camera);
      if (ball.visible) {
        const p = toScreen(run.x, r * 2 + 0.25, -run.z);
        ctx.fillStyle = 'rgba(0,0,0,0.55)'; C.rr(ctx, p.x - 64, p.y - 70, 128, 60, 30); ctx.fill();
        C.text(String(run.num), p.x, p.y - 39, 44, '#fff', 'center', null);
      }
      for (const p of popups) { ctx.save(); ctx.globalAlpha = 1 - p.t;
        if (p.mult) { const k = C.easeOutBack(Math.min(1, p.t / 0.25)); ctx.translate(C.W / 2, C.H * 0.3); ctx.scale(k * 1.3, k * 1.3); C.text(p.text, 0, 0, 120, '#ffd600', 'center', '#5d2e00'); }
        else C.text(p.text, C.W / 2, C.H * 0.42 - p.t * 120, 100, p.good ? '#69f0ae' : '#ff5252');
        ctx.restore(); }
      if (flash > 0) { ctx.fillStyle = 'rgba(255,255,255,' + flash * 0.6 + ')'; ctx.fillRect(0, 0, C.W, C.H); }
      if (run.finaleOn && C.state === 'play') { ctx.save(); const k = 1 + Math.sin(C.realT * 10) * 0.05; ctx.translate(C.W - 110, 200); ctx.scale(k, k); ctx.fillStyle = 'rgba(0,0,0,0.45)'; C.rr(ctx, -90, -44, 180, 88, 30); ctx.fill(); C.text('×' + run.mult, 0, 2, 60, '#ffd600'); ctx.restore(); }
    },

    hud(ctx) {
      C.drawCoinsHud();
      ctx.fillStyle = 'rgba(0,0,0,0.35)'; C.rr(ctx, C.W / 2 - 60, 30, 120, 64, 32); ctx.fill(); C.text(String(C.save.level), C.W / 2, 64, 40);
      const bw = 360, bx = C.W / 2 - bw / 2, by = 112;
      ctx.fillStyle = 'rgba(0,0,0,0.25)'; C.rr(ctx, bx, by, bw, 18, 9); ctx.fill();
      ctx.fillStyle = '#ffeb3b'; C.rr(ctx, bx + 2, by + 2, (bw - 4) * C.clamp(run.z / run.len, 0, 1), 14, 7); ctx.fill();
      if (C.state !== 'play' || phase !== 'ready') return;
      if (!boostUsed && C.rewardedSupported && C.button('boost', C.W / 2 - 170, C.H * 0.75, 340, 120, { color: '#43a047', pulse: true, draw: () => { C.icon('ad', -70, -2, 60); C.text('+30', 50, 0, 56); } })) {
        C.ads.rewarded('start_boost').then((ok) => { if (ok) { boostUsed = true; run.num += 30; pop('+30', true); C.sfx('buy'); run.squash = 1; } });
      }
      const hx = C.W / 2 + Math.sin(C.realT * 3) * 140, hy = C.H * 0.88;
      ctx.strokeStyle = 'rgba(255,255,255,0.8)'; ctx.lineWidth = 8; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(C.W / 2 - 170, hy + 50); ctx.lineTo(C.W / 2 + 170, hy + 50); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.strokeStyle = '#333'; ctx.lineWidth = 4; ctx.beginPath(); ctx.ellipse(hx, hy, 28, 38, 0, 0, 7); ctx.fill(); ctx.stroke();
    },
  };

  function hit() { const dmg = run.n === 1 ? 15 : Math.max(15, Math.round(run.num * (0.22 + Math.min(0.13, (run.n - 2) * 0.03)))); run.num = Math.max(0, run.num - dmg); pop('−' + dmg, false); C.sfx('crash', 0.5); run.inv = 0.6; hitFlash = 1; shake = 0.5; burstAtBall('#ffd54f', 20, 420); }
  function smash(o) {
    C.sfx('crash', 0.8); C.sfx('star', o.idx * 0.6); shake = 0.45 + o.idx * 0.04; flash = 0.35; slowT = 0.14; run.finaleOn = true; pop('×' + o.mult, true, true); run.squash = 1;
    o.label.visible = false;
    for (const b of o.bricks) {
      const wp = new T3.Vector3(); b.getWorldPosition(wp); o.mesh.remove(b); b.position.copy(wp); levelGroup.add(b);
      run.debris.push({ m: b, vx: (b.position.x - run.x) * 3.2 + (Math.random() - 0.5) * 5, vy: 4 + Math.random() * 8, vz: -(6 + Math.random() * 9), rx: (Math.random() - 0.5) * 16, ry: (Math.random() - 0.5) * 16, life: 2.4 });
    }
    burstAtBall('#ffd600', 26, 700); burstAtBall('#90caf9', 18, 500);
  }

  window.__dbg = () => ({ run, phase, endT, endKind });
  window.__steer = (x) => { if (run) run.x = x; };
  C.run(game);
})();
