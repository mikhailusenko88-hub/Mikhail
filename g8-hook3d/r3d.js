// Hook Truck — объёмный вид (three.js r128). Физика и интерфейс прежние: этот файл рисует только мир.
// Мир физики плоский (x вправо, y вниз); здесь x тот же, высота = -y, глубина z — к камере.
(function (root) {
  'use strict';
  const R = { ok: false };
  let T = null, renderer, scene, cam, sun, lvlG = null, builtKey = null, vw = 0, vh = 0, vdpr = 0, lastT = 0, mob = false, warm = true;
  let truckG, catG, cat2G, drumM, idleHook, starM, hookM, tgtM, dustI = 0, dustAcc = 0;
  let look = { truck: 0, wheels: 0, paint: ['#ff5a36', '#c63b1f'] }, podium = null, viewOff = false, shine = null, sparks = [];
  const wheelG = [], ropeSeg = [], aimDots = [], dust = [];
  let rings = [], cps = [], boostM = [], clouds = [];
  const ZF = 130, ZB = -2600, ROAD = 78, DEEP = 1700, NROPE = 7;
  const _c = {}, C = (h) => _c[h] || (_c[h] = new T.Color(h).convertSRGBToLinear());
  const lam = (h, o) => new T.MeshLambertMaterial(Object.assign({ color: C(h) }, o || {}));
  const bas = (h, o) => new T.MeshBasicMaterial(Object.assign({ color: C(h) }, o || {}));

  // вид серии: 0 — луг, 1 — каньон (песок, красные скалы, тёплое небо)
  const TH = [
    { g: ['#86cf52', '#7ac448', '#e8c896', '#dfbc87', '#a8794a', '#96693d', '#58a332', '#b8824c', '#7a4e2a', '#3d2817'], tree: [['#4caf50', '#69c06d'], ['#2f8f57', '#3da56a'], '#8d5a2b'], treeP: 0.72, rocks: ['#9aa0a6', '#84898f'], tuft: '#4f9a2e', flw: ['#ffffff', '#ffeb3b', '#ff80ab'],
      ridge: [['#9cc0dc', '#bcd8ea'], ['#86b99a', '#acd3b8'], ['#69ab63', '#86c079']], sky: ['#3ea6f4', '#9fdafc', '#e9f8ff'], fog: '#d3ecfb' },
    { g: ['#e3a85c', '#d99b4f', '#f4e2bd', '#ecd6a8', '#b9683a', '#a65a30', '#c47f3d', '#c2703c', '#8e4a26', '#4a2414'], tree: [['#9aa33f', '#b6bb52'], ['#5f9148', '#77a85a'], '#7a5230'], treeP: 0.34, rocks: ['#c98a5a', '#b3744a'], tuft: '#b9a44a', flw: ['#fff3c4', '#ffb74d', '#ff8a65'],
      ridge: [['#e2a67c', '#f0c6a2'], ['#d18658', '#e3a57d'], ['#c06f41', '#d68d5f']], sky: ['#4aa3e8', '#ffd9a8', '#ffeede'], fog: '#f7dfc6' },
  ], skyC = {};
  function skyTex(k) {
    if (!skyC[k]) { const sk = document.createElement('canvas'); sk.width = 4; sk.height = 256; const g = sk.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 256), c = TH[k].sky; gr.addColorStop(0, c[0]); gr.addColorStop(0.55, c[1]); gr.addColorStop(1, c[2]); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); skyC[k] = new T.CanvasTexture(sk); skyC[k].encoding = T.sRGBEncoding; }
    return skyC[k];
  }

  // ---------- сборка геометрии из треугольников с цветом в вершинах ----------
  const Acc = () => ({ p: [], c: [] });
  function tri(A, a, b, c, ca, cb, cc) { A.p.push(a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]); A.c.push(ca.r, ca.g, ca.b, cb.r, cb.g, cb.b, cc.r, cc.g, cc.b); }
  function quad(A, a, b, c, d, ca, cb, cc, cd) { cb = cb || ca; cc = cc || ca; cd = cd || ca; tri(A, a, b, c, ca, cb, cc); tri(A, a, c, d, ca, cc, cd); }
  function mesh(A, mat) { const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(A.p, 3)); g.setAttribute('color', new T.Float32BufferAttribute(A.c, 3)); g.computeVertexNormals(); return new T.Mesh(g, mat); }
  const geoC = {};
  function GEO(k, f) { if (!geoC[k]) { const g = f(); geoC[k] = g.index ? g.toNonIndexed() : g; } return geoC[k]; }
  function addGeo(A, geo, x, y, z, sx, sy, sz, col) { const p = geo.attributes.position; for (let i = 0; i < p.count; i++) { A.p.push(x + p.getX(i) * sx, y + p.getY(i) * sy, z + p.getZ(i) * sz); A.c.push(col.r, col.g, col.b); } }
  function box(w, h, d, mat, x, y, z, par) { const m = new T.Mesh(new T.BoxGeometry(w, h, d), mat); m.position.set(x, y, z || 0); m.castShadow = true; par.add(m); return m; }
  function prof(pts, depth, mat, par) { const s = new T.Shape(); pts.forEach((p, i) => (i ? s.lineTo(p[0], p[1]) : s.moveTo(p[0], p[1]))); const g = new T.ExtrudeGeometry(s, { depth, bevelEnabled: false }); g.translate(0, 0, -depth / 2); const m = new T.Mesh(g, mat); m.castShadow = true; par.add(m); return m; }
  function cyl(r, h, seg, mat, x, y, z, par, alongZ) { const m = new T.Mesh(new T.CylinderGeometry(r, r, h, seg), mat); if (alongZ) m.rotation.x = Math.PI / 2; m.position.set(x, y, z || 0); m.castShadow = true; par.add(m); return m; }

  function cylX(r0, r1, h, seg, mat, x, y, z, par) { const m = new T.Mesh(new T.CylinderGeometry(r0, r1, h, seg), mat); m.rotation.z = Math.PI / 2; m.position.set(x, y, z || 0); m.castShadow = true; par.add(m); return m; }
  function drop(g) { if (!g) return; if (g.parent) g.parent.remove(g); g.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }

  R.init = function (canvas) {
    try {
      T = root.THREE; if (!T || !canvas) return false;
      renderer = new T.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
      renderer.outputEncoding = T.sRGBEncoding;
      mob = !!(root.matchMedia && matchMedia('(pointer: coarse)').matches);
      renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
      scene = new T.Scene();
      const sk = document.createElement('canvas'); sk.width = 4; sk.height = 256;
      const g = sk.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, '#3ea6f4'); gr.addColorStop(0.55, '#9fdafc'); gr.addColorStop(1, '#e9f8ff'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256);
      const skT = new T.CanvasTexture(sk); skT.encoding = T.sRGBEncoding; scene.background = skT;
      scene.fog = new T.Fog(C('#d3ecfb'), 3000, 12000);
      cam = new T.PerspectiveCamera(20, 1, 60, 40000);
      scene.add(new T.HemisphereLight(C('#ffffff'), C('#9dbb78'), 0.78));
      sun = new T.DirectionalLight(C('#fff1d2'), 0.92); sun.castShadow = true;
      const sm = mob ? 1024 : 2048; sun.shadow.mapSize.set(sm, sm);
      const sc = sun.shadow.camera; sc.left = -950; sc.right = 950; sc.top = 800; sc.bottom = -800; sc.near = 100; sc.far = 3400;
      sun.shadow.bias = -0.0008; sun.shadow.normalBias = 2.5;
      scene.add(sun); scene.add(sun.target);
      buildTruck(); buildDyn();
      R.ok = true;
    } catch (e) { R.ok = false; }
    return R.ok;
  };

  // ---------- Барсик и его помощник ----------
  function makeCat(fur, scarf) {
    const g = new T.Group(), f = lam(fur), wh = lam('#ffffff'), head = new T.Group(); g.add(head);
    const s = (r, mat, x, y, z, sx, sy, sz) => { const m = new T.Mesh(new T.SphereGeometry(r, 14, 10), mat); m.position.set(x, y, z); if (sx) m.scale.set(sx, sy, sz); m.castShadow = true; head.add(m); return m; };
    s(16, f, 0, 0, 0, 1, 0.92, 1);
    for (const z of [-9, 9]) { const e = new T.Mesh(new T.ConeGeometry(6.5, 14, 4), f); e.position.set(-1, 16.5, z); e.castShadow = true; head.add(e); }
    s(7, wh, 11, -4.5, 0, 0.8, 0.7, 1.15); s(2.1, lam('#f48fb1'), 16.6, -2.4, 0);
    const eyes = [];
    for (const z of [-6.2, 6.2]) {
      const eg = new T.Group(); eg.position.set(12.2, 3.8, z); head.add(eg); eyes.push(eg);
      eg.add(new T.Mesh(new T.SphereGeometry(4.5, 10, 8), wh));
      const ir = new T.Mesh(new T.SphereGeometry(3.1, 10, 8), bas('#2e9d43')); ir.position.x = 2.2; eg.add(ir);
      const pu = new T.Mesh(new T.SphereGeometry(1.8, 8, 6), bas('#111111')); pu.position.x = 3.8; eg.add(pu);
    }
    head.rotation.y = -0.62;
    const sc = new T.Mesh(new T.TorusGeometry(11, 4.3, 8, 16), lam(scarf)); sc.rotation.x = Math.PI / 2; sc.position.y = -14.5; g.add(sc);
    const body = new T.Mesh(new T.SphereGeometry(13, 10, 8), f); body.position.y = -27; g.add(body);
    g.userData = { head, eyes };
    return g;
  }

  // ---------- грузовик: рама, один из трёх кузовов, лебёдка на крыше, колёса ----------
  // Физика у всех одна (те же точки касания), поэтому кузова разные только на вид. Лебёдка всегда в точке (30, 104).
  // выбор из гаража: { truck: 0 пикап | 1 джип | 2 тягач, wheels: 0..3, paint: [цвет, тёмный цвет] }
  R.setLook = function (l) {
    if (!R.ok || !l) return;
    if (l.truck === look.truck && l.wheels === look.wheels && l.paint[0] === look.paint[0]) return;
    look = { truck: l.truck | 0, wheels: l.wheels | 0, paint: l.paint.slice() };
    buildTruck(); warm = true;
  };
  function bodyPickup(g, m) {
    box(132, 28, 100, m.main, -48, 16, 0, g);
    box(124, 14, 100, m.dark, -49, 37, 0, g);
    box(110, 3, 86, m.blk, -49, 44.5, 0, g);
    for (const z of [-50.5, 50.5]) box(118, 5, 1, m.stripe, -48, 22, z, g).castShadow = false;
    prof([[14, 2], [14, 40], [88, 40], [91, 37], [113, 33], [119, 20], [119, 2]], 96, m.main, g);
    box(8, 36, 96, m.main, 18, 57, 0, g);
    box(54, 7, 96, m.main, 41, 77, 0, g);
    for (const z of [-45.5, 45.5]) box(5, 44, 5, m.main, 77.5, 57.5, z, g).rotation.z = 0.58;
    const ws = box(2, 42, 84, m.glass, 77.5, 57.5, 0, g); ws.rotation.z = 0.58; ws.castShadow = false;
    box(20, 18, 104, m.blk, 114, -4, 0, g);
    for (const z of [-34, 34]) box(4, 10, 16, m.lamp, 120.5, 24, z, g).castShadow = false;
    cyl(4, 56, 8, m.grey, 6, 62, -40, g);
    return { roof: 80.5, cat: [47, 55], cat2: [-52, 60] };
  }
  // джип: открытый верх, дуги, запаска сзади, «кенгурятник» и прожекторы
  function bodyJeep(g, m) {
    prof([[-116, 2], [-116, 34], [-110, 42], [60, 42], [66, 46], [108, 43], [119, 34], [119, 2]], 96, m.main, g);
    box(150, 3, 80, m.blk, -36, 42.5, 0, g);
    for (const z of [-48.6, 48.6]) box(170, 5, 1, m.stripe, -28, 24, z, g).castShadow = false;
    box(8, 26, 76, m.dark, 29, 57, 0, g); box(8, 22, 80, m.dark, -58, 54, 0, g);
    for (const z of [-45.5, 45.5]) {
      box(5, 40, 5, m.frame, 72, 63, z, g).rotation.z = 0.26;
      box(6, 40, 6, m.frame, -18, 62, z, g);
      box(88, 5, 5, m.frame, 24, 81, z, g);
      box(92, 5, 5, m.frame, -60, 62, z, g).rotation.z = 0.46;
    }
    const ws = box(2, 36, 86, m.glass, 72, 63, 0, g); ws.rotation.z = 0.26; ws.castShadow = false;
    box(6, 6, 96, m.frame, 66.5, 82, 0, g); box(6, 6, 96, m.frame, -18, 81, 0, g);
    box(50, 4, 66, m.frame, 36, 82, 0, g);
    cylX(24, 24, 11, 18, m.tire, -121.5, 32, 0, g); cylX(11, 11, 13, 12, m.grey, -122, 32, 0, g);
    box(20, 18, 104, m.blk, 114, -4, 0, g);
    for (const z of [-28, 28]) box(4, 30, 4, m.chrome, 127, 13, z, g);
    for (const y of [9, 26]) box(4, 4, 62, m.chrome, 127, y, 0, g);
    for (const z of [-34, 34]) cylX(7, 7, 4, 12, m.lamp, 120.5, 30, z, g).castShadow = false;
    for (const z of [-30, -10, 10, 30]) { cylX(5.5, 5.5, 7, 10, m.blk, 68, 89, z, g); cylX(4.4, 4.4, 2, 10, m.lamp, 72, 89, z, g).castShadow = false; }
    box(16, 24, 7, lam('#2e7d32'), -94, 24, 51.5, g);
    for (const z of [-50, 50]) box(72, 4, 8, m.blk, 8, -2, z, g);
    return { roof: 84, cat: [47, 56], cat2: [-34, 58] };
  }
  // тягач: длинный капот, высокая кабина со спальником, хромированные трубы и баки
  function bodyRig(g, m) {
    prof([[62, 2], [62, 46], [104, 42], [117, 36], [119, 2]], 78, m.main, g);
    box(4, 30, 56, m.chrome, 120, 20, 0, g);
    for (const y of [10, 17, 24, 31]) box(5, 2, 50, m.blk, 120.4, y, 0, g).castShadow = false;
    for (const z of [-47, 47]) { box(58, 8, 14, m.dark, 90, 7, z, g); box(4, 9, 12, m.lamp, 120.5, 8, z, g).castShadow = false; }
    box(52, 42, 96, m.main, 38, 23, 0, g);
    box(8, 40, 96, m.main, 16, 64, 0, g);
    box(60, 8, 98, m.main, 41, 88, 0, g);
    for (const z of [-45.5, 45.5]) box(5, 42, 5, m.main, 66, 64, z, g).rotation.z = 0.1;
    const ws = box(2, 40, 84, m.glass, 66.5, 64, 0, g); ws.rotation.z = 0.1; ws.castShadow = false;
    box(16, 4, 98, m.dark, 76, 82, 0, g).rotation.z = -0.3;
    for (const z of [-36, -18, 0, 18, 36]) box(4, 4, 7, bas('#ffb300'), 70, 93.5, z, g).castShadow = false;
    box(48, 74, 98, m.dark, -13, 39, 0, g);
    box(48.6, 9, 98.6, m.main, -13, 20, 0, g);
    box(20, 14, 99.4, m.blk, -13, 56, 0, g);
    for (const z of [-40, 40]) { cyl(4.5, 66, 10, m.chrome, -44, 57, z, g); cyl(5.6, 5, 10, m.blk, -44, 91, z, g); }
    box(76, 6, 90, m.blk, -77, 11, 0, g);
    cyl(24, 5, 18, m.grey, -76, 16.5, 0, g);
    for (const z of [-38, 38]) { box(4, 7, 12, bas('#ff5252'), -116, 4, z, g).castShadow = false; box(3, 22, 22, m.blk, -112, -14, z, g); }
    for (const z of [-50, 50]) { cylX(10, 10, 44, 12, m.chrome, -8, -4, z, g); box(34, 4, 9, m.chrome, 38, -8, z, g); }
    box(14, 20, 108, m.chrome, 119, -6, 0, g);
    for (const z of [-22, 22]) cylX(4.6, 3, 24, 8, m.chrome, 52, 95, z, g);
    return { roof: 92, cat: [44, 58], cat2: [-76, 46] };
  }
  // колёса: 0 обычные, 1 «монстр» (широкие, крупный протектор), 2 золотые диски, 3 шипы
  function buildWheels(m) {
    const k = look.wheels, gold = new T.MeshPhongMaterial({ color: C('#ffc107'), specular: C('#fff8e1'), shininess: 90, emissive: C('#3d2a00') });
    for (let i = 0; i < 2; i++) {
      const g = new T.Group(); scene.add(g); wheelG.push(g);
      cyl(5, 104, 8, m.frame, 0, 0, 0, g, true);
      for (const z of [-56, 56]) {
        if (k === 1) {
          cyl(26.5, 36, 20, m.tire, 0, 0, z, g, true);
          for (let q = 0; q < 8; q++) { const a = (q / 8) * Math.PI * 2; box(8, 13, 38, m.tire, Math.cos(a) * 27.5, Math.sin(a) * 27.5, z, g).rotation.z = a; }
          cyl(17, 37, 16, lam('#fdd835'), 0, 0, z, g, true); cyl(14.5, 38, 16, lam('#e53935'), 0, 0, z, g, true);
          for (let q = 0; q < 6; q++) { const a = (q / 6) * Math.PI * 2; cyl(2.6, 40, 6, m.blk, Math.cos(a) * 9, Math.sin(a) * 9, z, g, true); }
        } else if (k === 2) {
          cyl(27.5, 22, 24, m.tire, 0, 0, z, g, true);
          cyl(20, 24, 20, gold, 0, 0, z, g, true); cyl(16, 25, 18, m.blk, 0, 0, z, g, true);
          for (let q = 0; q < 3; q++) box(36, 5, 26.5, gold, 0, 0, z, g).rotation.z = (q / 3) * Math.PI;
          cyl(6.5, 28.5, 12, gold, 0, 0, z, g, true);
        } else if (k === 3) {
          cyl(26.5, 26, 20, m.tire, 0, 0, z, g, true);
          for (let q = 0; q < 12; q++) { const a = (q / 12) * Math.PI * 2, c = new T.Mesh(new T.ConeGeometry(4.6, 10, 6), m.chrome); c.position.set(Math.cos(a) * 30, Math.sin(a) * 30, z); c.rotation.z = a - Math.PI / 2; c.castShadow = true; g.add(c); }
          cyl(15, 28, 14, lam('#455a64'), 0, 0, z, g, true); cyl(6, 31, 10, lam('#e53935'), 0, 0, z, g, true);
          for (let q = 0; q < 6; q++) { const a = (q / 6) * Math.PI * 2; cyl(2.2, 30, 6, m.chrome, Math.cos(a) * 10.5, Math.sin(a) * 10.5, z, g, true); }
        } else {
          cyl(27, 26, 20, m.tire, 0, 0, z, g, true);
          for (let q = 0; q < 10; q++) { const a = (q / 10) * Math.PI * 2; box(6, 9, 27, m.tire, Math.cos(a) * 27.5, Math.sin(a) * 27.5, z, g).rotation.z = a; }
          cyl(14, 28, 14, lam('#d5dde2'), 0, 0, z, g, true);
          for (let q = 0; q < 5; q++) { const a = (q / 5) * Math.PI * 2; cyl(2.5, 30, 6, lam('#607d8b'), Math.cos(a) * 8, Math.sin(a) * 8, z, g, true); }
        }
      }
    }
  }
  function buildTruck() {
    drop(truckG); wheelG.forEach(drop); wheelG.length = 0;
    truckG = new T.Group(); scene.add(truckG);
    // краска: обычная матовая; хром и золото — с бликом от солнца; «радуга» меняет цвет на ходу (см. R.draw)
    const sp = look.paint[2], paint = (h) => sp === 'gold' ? new T.MeshPhongMaterial({ color: C(h), specular: C('#fff1a8'), shininess: 60, emissive: C('#4a2e00') })
      : sp === 'chrome' ? new T.MeshPhongMaterial({ color: C(h), specular: C('#ffffff'), shininess: 120, emissive: C('#1d2327') })
      : sp === 'rainbow' ? new T.MeshPhongMaterial({ color: C(h), specular: C('#ffffff'), shininess: 50 }) : lam(h);
    const m = {
      main: paint(look.paint[0]), dark: paint(look.paint[1]), frame: lam('#37474f'), blk: lam('#20262a'), grey: lam('#90a4ae'), tire: lam('#1d1d1d'),
      chrome: new T.MeshPhongMaterial({ color: C('#dfe6ea'), specular: C('#ffffff'), shininess: 110 }),
      glass: new T.MeshLambertMaterial({ color: C('#b3e5fc'), transparent: true, opacity: 0.36 }),
      lamp: bas('#fff59d'), stripe: bas('#ffffff', { transparent: true, opacity: 0.6 }),
    };
    shine = sp === 'rainbow' ? [m.main, m.dark] : null;
    box(230, 26, 84, m.frame, 1, -5, 0, truckG);
    const b = [bodyPickup, bodyJeep, bodyRig][look.truck](truckG, m);
    // лебёдка на крыше: барабан всегда в одной точке — оттуда идёт трос
    box(32, 6, 40, m.frame, 30, b.roof + 3, 0, truckG);
    if (b.roof + 6 < 98) box(8, 98 - b.roof - 6, 8, m.grey, 30, (b.roof + 6 + 98) / 2, 0, truckG);
    drumM = new T.Group(); drumM.position.set(30, 104, 0); truckG.add(drumM);
    cyl(12, 26, 14, lam('#ffb300'), 0, 0, 0, drumM, true); box(26, 5, 28, lam('#5d4037'), 0, 0, 0, drumM);
    idleHook = new T.Mesh(new T.TorusGeometry(7, 2.2, 6, 14, 4.4), m.grey); idleHook.position.set(43, 92, 0); truckG.add(idleHook);
    // искры на дорогой краске: звёздочки вспыхивают на борту и крыше
    sparks = [];
    if (sp) {
      const sh = new T.Shape(); [[0, 10], [1.7, 1.7], [10, 0], [1.7, -1.7], [0, -10], [-1.7, -1.7], [-10, 0], [-1.7, 1.7]].forEach((q, i) => (i ? sh.lineTo(q[0], q[1]) : sh.moveTo(q[0], q[1])));
      const sg = new T.ShapeGeometry(sh), sm = new T.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95, depthWrite: false, side: T.DoubleSide, fog: false });
      for (const q of [[-84, 30, 53], [-22, 18, 53], [44, 30, 52], [104, 22, 51], [38, b.roof + 2, 30], [-58, 46, 40], [84, 42, 30]]) { const s2 = new T.Mesh(sg, sm); s2.position.set(q[0], q[1], q[2]); s2.renderOrder = 6; truckG.add(s2); sparks.push(s2); }
    }
    catG = makeCat('#e8892f', '#1e5fd6'); catG.position.set(b.cat[0], b.cat[1], 0); truckG.add(catG);
    cat2G = makeCat('#a7adb3', '#e53935'); cat2G.position.set(b.cat2[0], b.cat2[1], 0); truckG.add(cat2G);
    buildWheels(m);
  }

  // ---------- то, что двигается: трос, прицел, пыль, звезда ----------
  function buildDyn() {
    const rm = lam('#8d6e63');
    for (let i = 0; i < NROPE; i++) { const m = new T.Mesh(new T.CylinderGeometry(3.4, 3.4, 1, 6), rm); m.castShadow = true; m.visible = false; scene.add(m); ropeSeg.push(m); }
    hookM = new T.Mesh(new T.SphereGeometry(9, 10, 8), lam('#90a4ae')); hookM.visible = false; scene.add(hookM);
    const dm = bas('#ffffff', { transparent: true, opacity: 0.85 });
    for (let i = 0; i < 9; i++) { const m = new T.Mesh(new T.SphereGeometry(4, 8, 6), dm); m.visible = false; scene.add(m); aimDots.push(m); }
    tgtM = new T.Mesh(new T.TorusGeometry(54, 3.4, 6, 36), bas('#ffeb3b')); tgtM.visible = false; scene.add(tgtM);
    for (let i = 0; i < 40; i++) { const m = new T.Mesh(new T.IcosahedronGeometry(1, 0), new T.MeshBasicMaterial({ color: C('#ecdcbd'), transparent: true, opacity: 0.8, depthWrite: false })); m.visible = false; scene.add(m); dust.push({ m, life: 0, vx: 0, vy: 0, vz: 0, r: 1 }); }
    const sh = new T.Shape();
    for (let i = 0; i < 10; i++) { const r = i % 2 ? 20 : 46, a = (i / 10) * Math.PI * 2 + Math.PI / 2, x = Math.cos(a) * r, y = Math.sin(a) * r; if (i) sh.lineTo(x, y); else sh.moveTo(x, y); }
    const sg = new T.ExtrudeGeometry(sh, { depth: 14, bevelEnabled: true, bevelSize: 3, bevelThickness: 3, bevelSegments: 1 }); sg.translate(0, 0, -7);
    starM = new T.Mesh(sg, new T.MeshPhongMaterial({ color: C('#ffd54f'), emissive: C('#6b4a00'), shininess: 60 })); starM.castShadow = true; starM.visible = false; scene.add(starM);
    // подиум гаража: круглая площадка под грузовиком
    podium = new T.Group(); podium.visible = false; scene.add(podium);
    for (const [r, top, c] of [[182, 0, '#455a64'], [168, 0.7, '#78909c'], [118, 1.4, '#8fa1ab']]) { const q = cyl(r, 8, 48, lam(c), 0, top - 4, 0, podium); q.castShadow = false; q.receiveShadow = true; }
    const rim = new T.Mesh(new T.TorusGeometry(175, 3, 6, 56), bas('#ffca28')); rim.rotation.x = Math.PI / 2; rim.position.y = 1.2; podium.add(rim);
    podium.scale.z = 0.69; // овал: чтобы площадка не свисала с переднего края земли
  }

  function cloud(par, x, y, z, s, mat) {
    const g = new T.Group(); g.position.set(x, y, z); g.scale.set(s, s * 0.78, s);
    for (const [dx, dy, r] of [[-40, 0, 34], [0, 16, 46], [42, 0, 34], [10, -8, 36]]) { const m = new T.Mesh(GEO('puff', () => new T.IcosahedronGeometry(1, 1)), mat); m.position.set(dx, dy, 0); m.scale.setScalar(r); g.add(m); }
    par.add(g); return g;
  }
  function tree(A, x, y, z, s, rnd, P) {
    const round = rnd() < 0.42, tc = P.tree[round ? 0 : 1], g1 = C(tc[0]), g2 = C(tc[1]);
    addGeo(A, GEO('trunk', () => new T.CylinderGeometry(7, 9, 50, 6)), x, y + 25 * s, z, s, s, s, C(P.tree[2]));
    if (round) { const ico = GEO('ico', () => new T.IcosahedronGeometry(40, 0)); addGeo(A, ico, x, y + 82 * s, z, s, s, s, g1); addGeo(A, ico, x + 24 * s, y + 62 * s, z + 14 * s, s * 0.6, s * 0.6, s * 0.6, g2); }
    else { const cone = GEO('cone', () => new T.ConeGeometry(44, 84, 7)); addGeo(A, cone, x, y + 80 * s, z, s, s, s, g1); addGeo(A, cone, x, y + 124 * s, z, s * 0.72, s * 0.72, s * 0.72, g2); }
  }

  // ---------- уровень: земля, пропасти, пещеры, кольца, флаги, фон ----------
  function build(S, key, theme) {
    const P = TH[theme] || TH[0]; scene.background = skyTex(TH[theme] ? theme : 0); scene.fog.color.copy(C(P.fog));
    for (const k in geoC) geoC[k].userData.keep = true;
    if (lvlG) { scene.remove(lvlG); lvlG.traverse((o) => { if (o.geometry && !o.geometry.userData.keep) o.geometry.dispose(); }); }
    lvlG = new T.Group(); scene.add(lvlG); builtKey = key; warm = true; rings = []; cps = []; boostM = []; clouds = [];
    const L = S.L; let seed = 4321 + key * 977; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const G = Acc(), D = Acc();
    const [gA, gB, rA, rB, rock, rock2, lip, e1, e2, e3] = P.g.map(C), mudA = C('#5b3d27'), mudB = C('#4c321f');
    let lowY = 1e9, hiY = -1e9, n = 0;
    for (const p of L.polys) for (const q of p) { lowY = Math.min(lowY, -q[1]); hiY = Math.max(hiY, -q[1]); }
    const yb = lowY - DEEP, x0L = L.polys[0][0][0], lastP = L.polys[L.polys.length - 1], x1L = lastP[lastP.length - 1][0];
    const inCave = (x) => L.ceils.some((c) => x > c.x0 - 60 && x < c.x1 + 60);
    function piece(xa, ya, xb, yb1, steep, deco) {
      const alt = n++ & 1, md = L.mudAt ? L.mudAt((xa + xb) / 2) : 0; // md — мягкость грязи 0..1 (игра про бездорожье)
      const mix = (c, k) => (md > 0.01 ? c.clone().lerp(alt ? mudA : mudB, Math.min(1, md * k)) : c);
      if (steep) quad(G, [xa, ya, ZF], [xb, yb1, ZF], [xb, yb1, ZB], [xa, ya, ZB], alt ? rock : rock2);
      else {
        quad(G, [xa, ya, ZF], [xb, yb1, ZF], [xb, yb1, ROAD], [xa, ya, ROAD], mix(alt ? gA : gB, 0.75));
        quad(G, [xa, ya, ROAD], [xb, yb1, ROAD], [xb, yb1, -ROAD], [xa, ya, -ROAD], mix(alt ? rA : rB, 1.5));
        quad(G, [xa, ya, -ROAD], [xb, yb1, -ROAD], [xb, yb1, ZB], [xa, ya, ZB], mix(alt ? gB : gA, 0.35));
      }
      const l = steep ? 0 : 18;
      if (l) quad(G, [xa, ya, ZF], [xb, yb1, ZF], [xb, yb1 - l, ZF], [xa, ya - l, ZF], lip);
      quad(G, [xa, ya - l, ZF], [xb, yb1 - l, ZF], [xb, yb1 - 520, ZF], [xa, ya - 520, ZF], e1, e1, e2, e2);
      quad(G, [xa, ya - 520, ZF], [xb, yb1 - 520, ZF], [xb, yb, ZF], [xa, yb, ZF], e2, e2, e3, e3);
      if (deco && !steep && !inCave((xa + xb) / 2)) {
        const cnt = rnd() < 0.6 ? 1 + (rnd() < 0.35 ? 1 : 0) : 0;
        for (let q = 0; q < cnt; q++) {
          const t = rnd(), x = xa + (xb - xa) * t, y = ya + (yb1 - ya) * t, z = -170 - rnd() * rnd() * 2000, s = 0.85 + rnd() * 0.8 + (-z / 2600) * 0.9;
          if (rnd() < P.treeP) tree(D, x, y, z, s, rnd, P); else addGeo(D, GEO('rock', () => new T.DodecahedronGeometry(22, 0)), x, y + 8 * s, z, s * 1.3, s * 0.8, s, C(P.rocks[rnd() < 0.5 ? 0 : 1]));
        }
        if (rnd() < 0.55) { const t = rnd(), x = xa + (xb - xa) * t, y = ya + (yb1 - ya) * t, z = ROAD + 14 + rnd() * (ZF - ROAD - 22); addGeo(D, GEO('tuft', () => new T.ConeGeometry(7, 16, 5)), x, y + 8, z, 1, 1, 1, C(P.tuft)); if (rnd() < 0.6) addGeo(D, GEO('flw', () => new T.IcosahedronGeometry(4, 0)), x + 5, y + 15, z + 3, 1, 1, 1, C(P.flw[Math.floor(rnd() * 3)])); }
      }
    }
    const dk = C('#0e0906');
    function wall(x, y) {
      quad(G, [x, y, ZF], [x, y, ZB], [x, y - 90, ZB], [x, y - 90, ZF], e1, e1, e2, e2);
      quad(G, [x, y - 90, ZF], [x, y - 90, ZB], [x, y - 320, ZB], [x, y - 320, ZF], e2, e2, dk, dk);
      quad(G, [x, y - 320, ZF], [x, y - 320, ZB], [x, yb, ZB], [x, yb, ZF], dk);
    }
    // видимая земля до начала и после конца трассы (в физике там невидимые стены)
    for (let x = x0L - 3300; x < x0L - 1; x += 150) piece(x, -L.polys[0][0][1], x + 150, -L.polys[0][0][1], false, true);
    for (const poly of L.polys) {
      for (let i = 1; i < poly.length; i++) {
        const ax = poly[i - 1][0], ay = -poly[i - 1][1], bx = poly[i][0], by = -poly[i][1], steep = Math.abs(by - ay) > Math.abs(bx - ax) * 1.5, k = Math.max(1, Math.round(Math.hypot(bx - ax, by - ay) / 150));
        for (let j = 0; j < k; j++) piece(ax + ((bx - ax) * j) / k, ay + ((by - ay) * j) / k, ax + ((bx - ax) * (j + 1)) / k, ay + ((by - ay) * (j + 1)) / k, steep, true);
      }
      wall(poly[0][0], -poly[0][1]); wall(poly[poly.length - 1][0], -poly[poly.length - 1][1]);
    }
    for (let x = x1L; x < x1L + 3300; x += 150) piece(x, -lastP[lastP.length - 1][1], x + 150, -lastP[lastP.length - 1][1], false, true);
    // пещеры: каменный потолок с сосульками
    for (const c of L.ceils) {
      const y = -c.y, cA = C('#8a6a55'), cB = C('#5e4334'), cC = C('#3d2a20');
      quad(G, [c.x0, y, ZF], [c.x1, y, ZF], [c.x1, y, ZB], [c.x0, y, ZB], cB);
      quad(G, [c.x0, y, ZF], [c.x1, y, ZF], [c.x1, y + 900, ZF], [c.x0, y + 900, ZF], cA, cA, cC, cC);
      for (const x of [c.x0, c.x1]) quad(G, [x, y, ZF], [x, y, ZB], [x, y + 900, ZB], [x, y + 900, ZF], cA, cA, cC, cC);
      for (let x = c.x0 + 40; x < c.x1 - 40; x += 70 + rnd() * 80) { const h = 40 + rnd() * 70, z = rnd() < 0.5 ? -110 - rnd() * 500 : 96 + rnd() * 30; addGeo(D, GEO('stal', () => new T.ConeGeometry(18, 1, 6)), x, y - h / 2, z, 1, -h, 1, cB); }
    }
    // ускорители: оранжевая дорога и бегущие стрелки
    const chev = GEO('chev', () => { const s = new T.Shape(); [[0, -20], [18, -20], [40, 0], [18, 20], [0, 20], [22, 0]].forEach((p, i) => (i ? s.lineTo(p[0], p[1]) : s.moveTo(p[0], p[1]))); return new T.ShapeGeometry(s); });
    for (const z of L.boosts) {
      for (let x = z.x0; x < z.x1 - 30; x += 60) {
        const ya = -S.groundAt(x) + 1.5, yb1 = -S.groundAt(Math.min(z.x1, x + 60)) + 1.5, i = Math.round((x - z.x0) / 60);
        quad(G, [x, ya, ROAD], [x + 60, yb1, ROAD], [x + 60, yb1, -ROAD], [x, ya, -ROAD], C(i & 1 ? '#ff9800' : '#ffb74d'));
        const m = new T.Mesh(chev, new T.MeshBasicMaterial({ color: C('#ff6d00'), transparent: true, side: T.DoubleSide })); m.position.set(x + 8, (ya + yb1) / 2 + 40, -ROAD - 26); lvlG.add(m); boostM.push({ m, i });
      }
    }
    for (const z of L.springs || []) {
      const xm = (z.x0 + z.x1) / 2, w = z.x1 - z.x0, gy = -S.groundAt(xm);
      box(w, 9, ROAD * 2 - 14, lam('#d81b60'), xm, gy + 4.5, 0, lvlG).castShadow = false; box(w - 18, 3, ROAD * 2 - 30, lam('#f8bbd0'), xm, gy + 10.5, 0, lvlG).castShadow = false;
      for (let k = 0; k < 2; k++) { const m = new T.Mesh(chev, new T.MeshBasicMaterial({ color: C('#ec407a'), transparent: true, side: T.DoubleSide })); m.rotation.z = Math.PI / 2; m.position.set(xm, gy + 70 + k * 52, -ROAD - 26); lvlG.add(m); boostM.push({ m, i: -k }); }
    }
    const gm = mesh(G, new T.MeshLambertMaterial({ vertexColors: true, side: T.DoubleSide })); gm.receiveShadow = true; lvlG.add(gm);
    if (D.p.length) { const dm = mesh(D, new T.MeshLambertMaterial({ vertexColors: true })); dm.castShadow = true; lvlG.add(dm); }
    // пропасти: книзу темнеют до черноты (упавший грузовик уходит в темноту)
    const pc = document.createElement('canvas'); pc.width = 4; pc.height = 128;
    const pg = pc.getContext('2d'), pgr = pg.createLinearGradient(0, 0, 0, 128);
    pgr.addColorStop(0, 'rgba(14,9,6,0)'); pgr.addColorStop(0.6, 'rgba(14,9,6,0.85)'); pgr.addColorStop(1, 'rgba(14,9,6,1)'); pg.fillStyle = pgr; pg.fillRect(0, 0, 4, 128);
    const pt = new T.CanvasTexture(pc); pt.encoding = T.sRGBEncoding;
    const pm = new T.MeshBasicMaterial({ map: pt, transparent: true, depthWrite: false, fog: false }), pm2 = new T.MeshBasicMaterial({ color: C('#0e0906'), fog: false });
    for (const z of L.pits) {
      const w = z.x1 - z.x0, y = -z.y, xm = (z.x0 + z.x1) / 2;
      const a = new T.Mesh(new T.PlaneGeometry(w, 270), pm); a.position.set(xm, y - 165, ZF + 3); a.renderOrder = 5; lvlG.add(a);
      const f = new T.Mesh(new T.PlaneGeometry(w, ZF - ZB), pm2); f.rotation.x = -Math.PI / 2; f.position.set(xm, y - 300, (ZF + ZB) / 2); lvlG.add(f);
      const b = new T.Mesh(new T.PlaneGeometry(w, DEEP + 2000), pm2); b.position.set(xm, y - 300 - (DEEP + 2000) / 2, ZF + 3); lvlG.add(b);
    }
    // кольца: в поле висят под облачком, в пещере — на цепи; у ездящих виден путь
    const white = lam('#ffffff'), dotG = GEO('dot', () => new T.IcosahedronGeometry(4.5, 0)), dotM = bas('#ffffff', { transparent: true, opacity: 0.7 });
    L.anchors.forEach((a) => {
      const g = new T.Group(); g.position.set(a.x, -a.y, 0);
      const mat = new T.MeshPhongMaterial({ color: C(a.snap ? '#ff8a65' : '#ffc107'), shininess: 90, specular: C('#666666') });
      const t = new T.Mesh(new T.TorusGeometry(30, 7, 10, 28), mat); t.castShadow = true; g.add(t);
      if (a.snap) for (const [x, y, r] of [[26, 16, 0.55], [-25, -18, -0.45], [-8, 28.5, 1.3]]) { const b = new T.Mesh(new T.BoxGeometry(4, 16, 16), bas('#3e2723')); b.position.set(x, y, 0); b.rotation.z = r; g.add(b); }
      const cave = L.ceils.find((c) => a.x > c.x0 && a.x < c.x1 && c.y < a.y);
      if (cave) { const h = a.y - cave.y - 30; cyl(3, h, 6, lam('#90a4ae'), 0, 30 + h / 2, 0, g).castShadow = false; }
      else { cyl(1.6, 270, 5, lam('#546e7a'), 0, 165, 0, g).castShadow = false; cloud(g, 0, 318, 0, 1, white); }
      lvlG.add(g); rings.push({ g, mat, col: '' });
      if (a.mv) for (let k = -1; k <= 1.001; k += 0.2) { const d = new T.Mesh(dotG, dotM); d.position.set(a.x0 + (a.mv.dx || 0) * k, -(a.y0 + (a.mv.dy || 0) * k), 0); lvlG.add(d); }
    });
    // чекпоинты и финиш (стоят за дорогой, грузовик проезжает перед ними)
    const pole = lam('#eceff1');
    for (const c of L.cps) { const gy = -S.groundAt(c.x), m = lam('#b0bec5'); cyl(4, 160, 6, pole, c.x, gy + 80, -ROAD - 20, lvlG); box(52, 32, 3, m, c.x + 28, gy + 142, -ROAD - 20, lvlG); cps.push({ x: c.x, mat: m, on: null }); }
    const fy = -S.groundAt(L.fin), fy2 = -S.groundAt(L.fin + 260), ck = document.createElement('canvas'); ck.width = 150; ck.height = 20;
    const cg = ck.getContext('2d'); for (let i = 0; i < 15; i++) for (let j = 0; j < 2; j++) { cg.fillStyle = (i + j) % 2 ? '#212121' : '#fafafa'; cg.fillRect(i * 10, j * 10, 10, 10); }
    const ct = new T.CanvasTexture(ck); ct.magFilter = T.NearestFilter; ct.encoding = T.sRGBEncoding;
    cyl(5, 240, 6, pole, L.fin - 40, fy + 120, -ROAD - 24, lvlG); cyl(5, 240 + Math.max(0, fy - fy2), 6, pole, L.fin + 260, fy + 120 - Math.max(0, fy - fy2) / 2, -ROAD - 24, lvlG);
    const bn = new T.Mesh(new T.PlaneGeometry(300, 40), new T.MeshBasicMaterial({ map: ct, side: T.DoubleSide })); bn.position.set(L.fin + 110, fy + 212, -ROAD - 24); lvlG.add(bn);
    const fl = new T.Mesh(new T.PlaneGeometry(40, ROAD * 2), new T.MeshBasicMaterial({ map: ct })); fl.rotation.x = -Math.PI / 2; fl.position.set(L.fin, fy + 2, 0); lvlG.add(fl);
    // фон: три гряды холмов и облака
    const ridge = (z, base, h0, h1, col, col2, step) => {
      const A = Acc(); let px = x0L - 10000, py = base + h0 + rnd() * (h1 - h0);
      for (let x = px + step; x < x1L + 10000; x += step * (0.6 + rnd() * 0.8)) { const y = base + h0 + rnd() * (h1 - h0); quad(A, [px, py, z], [x, y, z], [x, base - 4000, z], [px, base - 4000, z], col, col, col2, col2); px = x; py = y; }
      lvlG.add(mesh(A, new T.MeshBasicMaterial({ vertexColors: true, side: T.DoubleSide })));
    };
    const gb = (lowY + hiY) / 2;
    ridge(-8200, gb - 200, 900, 2300, C(P.ridge[0][0]), C(P.ridge[0][1]), 950);
    ridge(-5600, gb - 300, 500, 1400, C(P.ridge[1][0]), C(P.ridge[1][1]), 720);
    ridge(ZB - 500, gb - 500, 150, 640, C(P.ridge[2][0]), C(P.ridge[2][1]), 520);
    for (let i = 0; i < 16; i++) { const c = cloud(lvlG, x0L - 2500 + rnd() * (x1L - x0L + 5000), hiY + 500 + rnd() * 1000, -1300 - rnd() * 3800, 2 + rnd() * 2.6, white); c.userData.v = 6 + rnd() * 10; clouds.push(c); }
    if (R.onBuild) R.onBuild({ T, lvlG, S, L, C, lam, bas, box, cyl, ROAD, ZF, ZB, DEEP, P, tree: (x, y, z, sc) => { const A = Acc(); tree(A, x, y, z, sc, rnd, P); const m = mesh(A, new T.MeshLambertMaterial({ vertexColors: true })); m.castShadow = true; lvlG.add(m); return m; } });
  }

  function seg(m, x0, y0, x1, y1) { m.visible = true; m.position.set((x0 + x1) / 2, (y0 + y1) / 2, 0); m.scale.set(1, Math.hypot(x1 - x0, y1 - y0) || 0.001, 1); m.rotation.z = Math.atan2(y1 - y0, x1 - x0) - Math.PI / 2; }

  // ---------- кадр ----------
  R.draw = function (S, v) {
    if (!R.ok) return;
    if (v.W !== vw || v.H !== vh || v.DPR !== vdpr) { vw = v.W; vh = v.H; vdpr = v.DPR; renderer.setPixelRatio(v.DPR); renderer.setSize(vw, vh, false); cam.aspect = vw / vh; }
    if (builtKey !== v.lvl || !lvlG) build(S, v.lvl, v.theme | 0);
    const L = S.L, t = v.t, dt = Math.min(0.05, Math.max(0, t - lastT)); lastT = t;
    // камера: тот же кадр, что у плоского вида (точка взгляда и масштаб), но с глубиной и небольшим наклоном сверху
    const d = v.H / v.Z / (2 * Math.tan((cam.fov * Math.PI) / 360)), sh = v.shake > 0 ? v.shake * 40 : 0;
    let tilt = 0.15, yaw = 0, cx, cy;
    if (v.g) { // гараж: смотрим на грузовик сбоку-спереди, сам он стоит в точке экрана (px, py)
      tilt = v.g.tilt; yaw = v.g.yaw; cx = S.truck.x; cy = -S.truck.y + 18;
      cam.setViewOffset(vw, vh, vw / 2 - v.g.px, vh / 2 - v.g.py, vw, vh); viewOff = true;
    } else {
      if (viewOff) { cam.clearViewOffset(); viewOff = false; }
      cx = v.camX + (0.08 * v.W) / v.Z + (Math.random() - 0.5) * sh; cy = -(v.camY - ((v.oy === undefined ? 0.05 : v.oy) * v.H) / v.Z) + (Math.random() - 0.5) * sh;
    }
    cam.position.set(cx + d * Math.sin(yaw) * Math.cos(tilt), cy + d * Math.sin(tilt), d * Math.cos(yaw) * Math.cos(tilt)); cam.lookAt(cx, cy, 0);
    podium.visible = !!v.g; if (v.g) podium.position.set(S.truck.x, -S.groundAt(S.truck.x) + 1, 0);
    cam.near = Math.max(40, d - 1000); cam.far = d + 16000; cam.updateProjectionMatrix();
    scene.fog.near = d + 1500; scene.fog.far = d + 11500;
    // грузовик и колёса
    const tr = S.truck; truckG.position.set(tr.x, -tr.y, 0); truckG.rotation.z = -tr.a;
    sparks.forEach((q, i) => { const k = Math.sin(t * 2.6 + i * 1.9), s2 = k > 0 ? k * k * 1.25 : 0; q.visible = s2 > 0.03; if (q.visible) { q.scale.set(s2, s2, s2); q.rotation.z = t * 0.8 + i; } });
    if (shine) { const h = (t * 0.12) % 1; shine[0].color.setHSL(h, 0.9, 0.56).convertSRGBToLinear(); shine[1].color.setHSL((h + 0.07) % 1, 0.9, 0.4).convertSRGBToLinear(); }
    S.wheels.forEach((w, i) => { const g = wheelG[i]; if (g) { g.position.set(w.x, -w.y, 0); g.rotation.z = -w.a; } }); // у игры про бездорожье мостов бывает три и колёса свои
    sun.target.position.set(tr.x, -tr.y, 0); sun.position.set(tr.x - 430, -tr.y + 1050, 640); sun.target.updateMatrixWorld();
    const scared = S.state === 'dead' || (!S.grounded && Math.abs(tr.vy) > 500), happy = S.state === 'win';
    for (const cg of [catG, cat2G]) { const es = scared ? 1.4 : 1; cg.userData.eyes.forEach((e) => e.scale.set(1, happy ? 0.35 : es, es)); cg.userData.head.rotation.z = scared ? 0.16 : Math.sin(t * 2) * 0.05; }
    cat2G.visible = !!v.duo; drumM.rotation.z = S.pullOn ? -t * 18 : 0; idleHook.visible = !S.rope;
    // трос (провисает, пока не натянут) и крюк на кольце
    if (S.rope) {
      const m = S.mast(), ax = S.rope.px, ay = S.rope.py, sag = Math.max(0, S.rope.len - Math.hypot(ax - m[0], ay - m[1])) * 0.6, qx = (m[0] + ax) / 2, qy = (m[1] + ay) / 2 + sag;
      let px = m[0], py = m[1];
      for (let i = 1; i <= NROPE; i++) { const k = i / NROPE, a = (1 - k) * (1 - k), b = 2 * k * (1 - k), c = k * k, x = a * m[0] + b * qx + c * ax, y = a * m[1] + b * qy + c * ay; seg(ropeSeg[i - 1], px, -py, x, -y); px = x; py = y; }
      hookM.visible = true; hookM.position.set(ax, -ay - 18, 0);
    } else { for (const m of ropeSeg) m.visible = false; hookM.visible = false; }
    // прицел: к какому кольцу уйдёт крюк
    const tg = S.target && !S.rope && S.state === 'play' ? S.target : null;
    tgtM.visible = !!tg;
    if (tg) { const p = 1 + 0.16 * Math.sin(t * 10), m = S.mast(); tgtM.position.set(tg.x, -tg.y, 0); tgtM.scale.set(p, p, 1); aimDots.forEach((dm, i) => { const k = (i + ((t * 2) % 1)) / aimDots.length; dm.visible = true; dm.position.set(m[0] + (tg.x - m[0]) * k, -(m[1] + (tg.y - m[1]) * k), 0); }); }
    else for (const dm of aimDots) dm.visible = false;
    // кольца
    L.anchors.forEach((a, i) => {
      const r = rings[i]; if (!r) return;
      r.g.visible = !a.broken; const on = S.ropeA === a;
      const ox = on && a.snap ? Math.sin(t * 60) * 3 * Math.min(1, (a.hang || 0) / a.snap) : 0;
      r.g.position.set(a.x + ox, -a.y, 0);
      const col = a.snap ? (on ? '#ff5252' : '#ff8a65') : on ? '#ff7043' : tg === a ? '#ffeb3b' : '#ffc107';
      if (r.col !== col) { r.col = col; r.mat.color.copy(C(col)); }
    });
    const st = L.star; starM.visible = !!(st && !st.got);
    if (starM.visible) { starM.position.set(st.x, -(st.y + Math.sin(t * 3) * 8), 0); starM.rotation.y = Math.sin(t * 2.2) * 0.9; starM.rotation.z = Math.sin(t * 2) * 0.12; }
    for (const c of cps) { const on = !!(S.cp && S.cp.x >= c.x); if (c.on !== on) { c.on = on; c.mat.color.copy(C(on ? '#00e676' : '#b0bec5')); } }
    for (const b of boostM) b.m.material.opacity = ((((t * 5 - b.i) % 3) + 3) % 3) < 1 ? 1 : 0.4;
    for (const c of clouds) c.position.x += dt * c.userData.v;
    // пыль из-под задних колёс
    dustAcc += dt;
    if (v.gas && S.grounded && S.state === 'play' && dustAcc > 0.045) {
      dustAcc = 0; const w = S.wheels[0], p = dust[dustI++ % dust.length];
      p.life = 0.55; p.r = 7 + Math.random() * 9; p.vx = -60 - Math.random() * 90; p.vy = 40 + Math.random() * 60; p.vz = (Math.random() - 0.5) * 120;
      p.m.position.set(w.x - 14, -w.y - 22, (Math.random() - 0.5) * 80); p.m.visible = true;
    }
    for (const p of dust) if (p.life > 0) {
      p.life -= dt; if (p.life <= 0) { p.m.visible = false; continue; }
      p.m.position.x += p.vx * dt; p.m.position.y += p.vy * dt; p.m.position.z += p.vz * dt;
      const k = p.life / 0.55, s = p.r * (1.6 - k * 0.6); p.m.scale.set(s, s, s); p.m.material.opacity = 0.75 * k;
    }
    if (R.onDraw) R.onDraw(S, v, dt);
    if (warm) {
      warm = false; const st = [];
      scene.traverse((o) => { st.push(o, o.visible, o.frustumCulled); o.visible = true; o.frustumCulled = false; });
      try { renderer.render(scene, cam); } catch (e) { /* */ }
      for (let i = 0; i < st.length; i += 3) { st[i].visible = st[i + 1]; st[i].frustumCulled = st[i + 2]; }
    }
    renderer.render(scene, cam);
  };

  // для проверки плавности: сколько вызовов отрисовки, треугольников и собранных шейдеров в кадре
  R.info = function () { const i = renderer ? renderer.info : null; return i ? { calls: i.render.calls, tris: i.render.triangles, programs: i.programs ? i.programs.length : 0 } : null; };

  R.api = { get T() { return T; }, get scene() { return scene; }, get truck() { return truckG; }, get wheels() { return wheelG; }, C: (h) => C(h), lam: (h, o) => lam(h, o), bas: (h, o) => bas(h, o), box, cyl };

  root.Hook3D = R;
})(window);
