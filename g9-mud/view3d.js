'use strict';
/* Грязь 3D — рисование и управление. Камера за грузовиком; правая рука — газ и назад, левая — руль, лебёдка и три переключателя. */
(function () {
  const M = window.MudSim, T3 = window.THREE;
  const cv = document.getElementById('c'), ctx = cv.getContext('2d'), glc = document.getElementById('gl');
  const RU = /^(ru|uk|be|kk)/i.test(navigator.language || '') || /[?&]ru\b/.test(location.search);
  const T = RU ? {
    goal: 'Довези брёвна до лесопилки. По дороге проще. Через болото — за флажком и третьей звездой', awd: '4×4', lock: 'БЛОК', low: 'ПОНИЖ', winch: 'ЛЕБЁДКА', fuel: 'Топливо',
    hAwd: 'Буксуешь? Включи 4×4 — полный привод', hLock: 'Не тянет? Включи БЛОК — блокировку', hLow: 'Мало тяги? Включи ПОНИЖ — пониженную', hWinch: 'Держи ЛЕБЁДКУ — подтянет к дереву', hBack: 'Сдай назад и объезжай: тут слишком глубоко', hTree: 'Повернись носом к дереву — лебёдка достаёт на 24 м',
    dFuel: 'Топливо кончилось', dWater: 'Мотор залило водой', dFlip: 'Перевернулся', win: 'Груз доставлен!', s1: 'Доехал', s2: 'Без эвакуации', s3: 'Флажок с болота', flag: 'Флажок взят! Теперь на лесопилку', time: 'Время', again: 'Ещё раз',
    keys: 'W A S D — ехать   ·   1 — 4×4   2 — блок   3 — пониж   ·   F — лебёдка   ·   Пробел — тормоз   ·   R — эвакуация   ·   C — камера', kmh: 'км/ч', m: 'м', sec: 'с',
  } : {
    goal: 'Haul the logs to the sawmill. The road is easier. The swamp trail has a flag — and the third star', awd: '4×4', lock: 'LOCK', low: 'LOW', winch: 'WINCH', fuel: 'Fuel',
    hAwd: 'Wheels spinning? Switch on 4×4', hLock: 'Not enough grip? Switch on LOCK', hLow: 'Not enough pull? Switch on LOW gear', hWinch: 'Hold WINCH — it pulls you to the tree', hBack: 'Back up and go around: too deep here', hTree: 'Point the nose at a tree — the winch reaches 24 m',
    dFuel: 'Out of fuel', dWater: 'Engine flooded', dFlip: 'Rolled over', win: 'Cargo delivered!', s1: 'Delivered', s2: 'No rescue', s3: 'Swamp flag', flag: 'Flag taken! Now to the sawmill', time: 'Time', again: 'Again',
    keys: 'W A S D — drive   ·   1 — 4×4   2 — lock   3 — low   ·   F — winch   ·   Space — brake   ·   R — rescue   ·   C — camera', kmh: 'km/h', m: 'm', sec: 's',
  };
  let W = 0, H2 = 0, DPR = 1;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v), lerp = (a, b, t) => a + (b - a) * t;
  const C = (h) => new T3.Color(h).convertSRGBToLinear();
  const lam = (h, o) => new T3.MeshLambertMaterial(Object.assign({ color: C(h) }, o || {}));

  // ---------- состояние ----------
  const S = M.create({ seed: 7 }), map = S.map, sw = { awd: false, lock: false, low: false }, keys = {}, ptrs = new Map();
  let mode = 'play', flagT = -9, realT = 0, last = performance.now(), acc = 0, buttons = [], camFar = 0, camYaw = S.yaw(), muted = false;
  const dbg = { freeze: false };

  // ---------- сцена ----------
  const renderer = new T3.WebGLRenderer({ canvas: glc, antialias: true, powerPreference: 'high-performance' });
  renderer.outputEncoding = T3.sRGBEncoding; renderer.shadowMap.enabled = true; renderer.shadowMap.type = T3.PCFSoftShadowMap;
  const scene = new T3.Scene(), cam = new T3.PerspectiveCamera(55, 1, 0.4, 900);
  { const sk = document.createElement('canvas'); sk.width = 4; sk.height = 256; const g = sk.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 256); gr.addColorStop(0, '#3e9be8'); gr.addColorStop(0.6, '#a8dcfb'); gr.addColorStop(1, '#eaf7ff'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); const t = new T3.CanvasTexture(sk); t.encoding = T3.sRGBEncoding; scene.background = t; }
  scene.fog = new T3.Fog(C('#cfe8f7'), 90, 330);
  scene.add(new T3.HemisphereLight(C('#ffffff'), C('#8fb26d'), 0.8));
  const sun = new T3.DirectionalLight(C('#fff1d2'), 0.95); sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
  { const sc = sun.shadow.camera; sc.left = -42; sc.right = 42; sc.top = 42; sc.bottom = -42; sc.near = 5; sc.far = 190; sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.06; }
  scene.add(sun); scene.add(sun.target);
  let gq = 1; const PF = { n: 0, sum: 0, lock: false }, tall = () => W < H2 * 1.25; // стоячий и почти квадратный экран: камера смотрит дальше вперёд
  function resize() {
    DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H2 = innerHeight; cv.width = W * DPR; cv.height = H2 * DPR; renderer.setPixelRatio(DPR * gq); renderer.setSize(W, H2, false);
    const k = tall() ? 0.34 : 0.27; // кадр считаем выше экрана и показываем его низ: грузовик поднимается над кнопками
    cam.aspect = W / (H2 * (1 + k)); cam.fov = tall() ? 78 : 58; cam.setViewOffset(W, H2 * (1 + k), 0, H2 * k, W, H2); cam.updateProjectionMatrix();
  }
  // телефон не тянет (в среднем дольше 22,5 мс на кадр) — снижаем чёткость 3D ступенями, потом убираем тени; кнопки и надписи остаются чёткими
  function perfTick(raw) {
    if (PF.lock || raw <= 0 || raw > 0.1 || (navigator.webdriver && !dbg.adapt)) return;
    PF.sum += raw; if (++PF.n < 90) return; const avg = PF.sum / PF.n; PF.n = 0; PF.sum = 0; if (avg <= 0.0225) return;
    if (DPR * gq > 1.01) { gq = Math.max(1 / DPR, gq - 0.25); renderer.setPixelRatio(DPR * gq); renderer.setSize(W, H2, false); }
    else if (renderer.shadowMap.enabled) { renderer.shadowMap.enabled = false; sun.castShadow = false; scene.traverse((o) => { if (o.material) o.material.needsUpdate = true; }); }
    else PF.lock = true;
  }
  addEventListener('resize', resize); resize();

  // местность: грани с цветом по виду земли
  const KC = ['#7ac448', '#d9b98a', '#6b4a2f', '#b9ad9c', '#d8c690'].map(C), GR2 = C('#8ad356'), MUD = C('#5b3d27'), WET = C('#3f2a1a'), ROCK = C('#8d8d86');
  function groundColor(x, z, slope, out) {
    const N = map.N, i = clamp(Math.round(x / map.C), 0, N - 1), j = clamp(Math.round(z / map.C), 0, N - 1), k = map.K[j * N + i], m = map.mud(x, z);
    out.copy(KC[k]); if (k === 0) out.lerp(GR2, ((i * 7 + j * 13) % 5) / 5);
    if (m > 0.05 && k !== 1 && k !== 3) { out.lerp(MUD, clamp(m * 1.5, 0, 1)); if (m > 0.6) out.lerp(WET, (m - 0.6) * 2); }
    if (slope > 0.62 && k === 0) out.lerp(ROCK, clamp((slope - 0.62) * 4, 0, 1));
    return out;
  }
  {
    const N = map.N, Cc = map.C, n = (N - 1) * (N - 1) * 6, pos = new Float32Array(n * 3), col = new Float32Array(n * 3), c = new T3.Color(); let o = 0;
    const put = (x, z, cc) => { pos[o] = x; pos[o + 1] = map.H[Math.round(z / Cc) * N + Math.round(x / Cc)]; pos[o + 2] = z; col[o] = cc.r; col[o + 1] = cc.g; col[o + 2] = cc.b; o += 3; };
    for (let j = 0; j < N - 1; j++) for (let i = 0; i < N - 1; i++) {
      const x0 = i * Cc, z0 = j * Cc, x1 = x0 + Cc, z1 = z0 + Cc, hA = map.H[j * N + i], hB = map.H[j * N + i + 1], hC = map.H[(j + 1) * N + i], hD = map.H[(j + 1) * N + i + 1];
      const sl = Math.max(Math.abs(hA - hD), Math.abs(hB - hC)) / (Cc * 1.41), q = (i + j) & 1;
      groundColor(x0 + Cc * (q ? 0.3 : 0.6), z0 + Cc * 0.35, sl, c); const c1 = c.clone(); groundColor(x0 + Cc * (q ? 0.7 : 0.4), z0 + Cc * 0.65, sl, c);
      if (q) { put(x0, z0, c1); put(x0, z1, c1); put(x1, z0, c1); put(x1, z0, c); put(x0, z1, c); put(x1, z1, c); }
      else { put(x0, z0, c1); put(x0, z1, c1); put(x1, z1, c1); put(x0, z0, c); put(x1, z1, c); put(x1, z0, c); }
    }
    const g = new T3.BufferGeometry(); g.setAttribute('position', new T3.BufferAttribute(pos, 3)); g.setAttribute('color', new T3.BufferAttribute(col, 3)); g.computeVertexNormals();
    const m = new T3.Mesh(g, new T3.MeshLambertMaterial({ vertexColors: true })); m.receiveShadow = true; scene.add(m);
    const w = new T3.Mesh(new T3.PlaneGeometry(map.SIZE, map.SIZE), new T3.MeshLambertMaterial({ color: C('#4fb3e8'), transparent: true, opacity: 0.72, depthWrite: false })); w.rotation.x = -Math.PI / 2; w.position.set(map.SIZE / 2, map.yW, map.SIZE / 2); scene.add(w);
    // за краем карты — дальние холмы, чтобы мир не обрывался
    const far = new T3.Mesh(new T3.RingGeometry(map.SIZE * 0.72, map.SIZE * 3, 40, 1), lam('#6fb24a')); far.rotation.x = -Math.PI / 2; far.position.set(map.SIZE / 2, 3, map.SIZE / 2); scene.add(far);
  }
  // деревья: стволы и кроны — по одному объекту на вид (тысяча деревьев рисуется за пять вызовов)
  {
    const d = new T3.Object3D(), tr = map.trees, live = tr.filter((t) => !t.dead), dead = tr.filter((t) => t.dead), cone = live.filter((t) => t.kind === 0), round = live.filter((t) => t.kind === 1);
    const inst = (geo, mat, list, fn) => { const m = new T3.InstancedMesh(geo, mat, Math.max(1, list.length)); list.forEach((t, i) => { fn(t, d); d.updateMatrix(); m.setMatrixAt(i, d.matrix); }); m.count = list.length; m.castShadow = true; m.instanceMatrix.needsUpdate = true; scene.add(m); return m; };
    inst(new T3.CylinderGeometry(0.22, 0.32, 2.4, 6), lam('#8d5a2b'), live, (t, o) => { o.position.set(t.x, t.y + 1.2 * t.s, t.z); o.scale.setScalar(t.s); o.rotation.set(0, 0, 0); });
    inst(new T3.ConeGeometry(1.9, 4.2, 7), lam('#2f8f57'), cone, (t, o) => { o.position.set(t.x, t.y + 4.0 * t.s, t.z); o.scale.setScalar(t.s); o.rotation.set(0, t.x, 0); });
    inst(new T3.ConeGeometry(1.35, 3.0, 7), lam('#3da56a'), cone, (t, o) => { o.position.set(t.x, t.y + 6.1 * t.s, t.z); o.scale.setScalar(t.s); o.rotation.set(0, t.z, 0); });
    inst(new T3.IcosahedronGeometry(2.0, 0), lam('#4caf50'), round, (t, o) => { o.position.set(t.x, t.y + 4.0 * t.s, t.z); o.scale.set(t.s, t.s * 1.15, t.s); o.rotation.set(t.x, t.z, 0); });
    inst(new T3.CylinderGeometry(0.16, 0.34, 5.2, 6), lam('#7b6a58'), dead, (t, o) => { o.position.set(t.x, t.y + 2.6 * t.s, t.z); o.scale.setScalar(t.s); o.rotation.set(0.06 * Math.sin(t.x), 0, 0.06 * Math.cos(t.z)); });
    inst(new T3.CylinderGeometry(0.4, 0.4, 0.22, 8), lam('#ffca28'), dead.filter((t) => t.post), (t, o) => { o.position.set(t.x, t.y + 1.0, t.z); o.scale.setScalar(1); o.rotation.set(0, 0, 0); });
  }
  const box = (w, h, l, mat, x, y, z, par) => { const m = new T3.Mesh(new T3.BoxGeometry(w, h, l), mat); m.position.set(x, y, z); m.castShadow = true; par.add(m); return m; };
  // постройки и маяк цели
  let beacon;
  {
    const s = map.start, g = map.goal, ys = map.h(s.x - 14, s.z - 12), yg = map.h(g.x + 16, g.z + 6);
    box(12, 5, 9, lam('#90a4ae'), s.x - 14, ys + 2.5, s.z - 12, scene); box(13, 0.6, 10, lam('#c62828'), s.x - 14, ys + 5.3, s.z - 12, scene);
    box(14, 4.6, 9, lam('#a1887f'), g.x + 16, yg + 2.3, g.z + 6, scene); box(15, 0.6, 10, lam('#5d4037'), g.x + 16, yg + 4.9, g.z + 6, scene);
    for (let i = 0; i < 6; i++) { const l = new T3.Mesh(new T3.CylinderGeometry(0.3, 0.3, 5, 7), lam(i & 1 ? '#8d6e63' : '#795548')); l.rotation.z = Math.PI / 2; l.position.set(g.x + 4, map.h(g.x + 4, g.z + 13) + 0.3 + (i > 2 ? 0.55 : 0), g.z + 12 + (i % 3) * 0.62 + (i > 2 ? 0.3 : 0)); l.castShadow = true; scene.add(l); }
    beacon = new T3.Mesh(new T3.CylinderGeometry(g.r, g.r, 26, 28, 1, true), new T3.MeshBasicMaterial({ color: C('#ffeb3b'), transparent: true, opacity: 0.2, side: T3.FrontSide, depthWrite: false, fog: false })); beacon.position.set(g.x, map.h(g.x, g.z) + 13, g.z); scene.add(beacon);
  }
  // флажок посреди болота
  const flag = new T3.Group();
  { const f = map.swamp, y = map.h(f.x, f.z); flag.position.set(f.x, y, f.z); box(0.16, 6, 0.16, lam('#eceff1'), 0, 3, 0, flag); box(1.9, 1.2, 0.08, new T3.MeshBasicMaterial({ color: C('#ff6d00'), fog: false }), 1.0, 5.3, 0, flag); const r = new T3.Mesh(new T3.CylinderGeometry(11, 11, 10, 24, 1, true), new T3.MeshBasicMaterial({ color: C('#ff9100'), transparent: true, opacity: 0.13, side: T3.FrontSide, depthWrite: false, fog: false })); r.position.y = 5; flag.add(r); scene.add(flag); }
  // грузовик: рама, кабина с котом, капот, кузов с брёвнами
  const truck = new T3.Group(), wheelM = []; scene.add(truck);
  {
    const red = lam('#ff5a36'), dark = lam('#c63b1f'), blk = lam('#20262a'), grey = lam('#90a4ae'), R = S.cfg.r;
    box(1.5, 0.26, 4.5, lam('#37474f'), 0, -0.36, 0, truck);
    box(1.9, 0.62, 1.15, red, 0, 0.08, 1.72, truck); box(1.9, 0.5, 1.4, red, 0, 0.02, 0.62, truck);                   // капот и низ кабины
    for (const x of [-0.9, 0.9]) for (const z of [0.0, 1.22]) box(0.1, 0.72, 0.1, red, x, 0.62, z, truck);          // стойки
    box(1.9, 0.1, 1.4, red, 0, 1.02, 0.62, truck);                                                                // крыша
    const gl = new T3.MeshLambertMaterial({ color: C('#b3e5fc'), transparent: true, opacity: 0.35 }); box(1.8, 0.66, 0.05, gl, 0, 0.62, 1.24, truck).castShadow = false; for (const x of [-0.92, 0.92]) box(0.04, 0.66, 1.12, gl, x, 0.62, 0.62, truck).castShadow = false;
    box(1.9, 0.72, 0.08, dark, 0, 0.62, -0.04, truck);                                                            // задняя стенка кабины
    box(2.06, 0.26, 0.22, blk, 0, -0.3, 2.34, truck); for (const x of [-0.66, 0.66]) box(0.3, 0.2, 0.06, new T3.MeshBasicMaterial({ color: C('#fff59d') }), x, 0.18, 2.31, truck).castShadow = false;
    box(0.5, 0.24, 0.3, grey, 0, -0.12, 2.36, truck);                                                             // лебёдка
    box(1.96, 0.12, 2.3, dark, 0, -0.18, -1.22, truck); for (const x of [-0.95, 0.95]) box(0.07, 0.42, 2.3, dark, x, 0.06, -1.22, truck); box(1.96, 0.42, 0.07, dark, 0, 0.06, -2.36, truck);
    for (const [x, y] of [[-0.52, 0.06], [0, 0.06], [0.52, 0.06], [-0.26, 0.5], [0.26, 0.5]]) { const l = new T3.Mesh(new T3.CylinderGeometry(0.24, 0.24, 2.2, 7), lam(y > 0.3 ? '#8d6e63' : '#795548')); l.rotation.x = Math.PI / 2; l.position.set(x, y + 0.12, -1.22); l.castShadow = true; truck.add(l); }
    const ex = new T3.Mesh(new T3.CylinderGeometry(0.07, 0.07, 1.5, 6), grey); ex.position.set(-0.98, 0.72, -0.12); truck.add(ex);
    // Барсик за рулём
    const fur = lam('#e8892f'), head = new T3.Group(); head.position.set(0.42, 0.66, 0.66); truck.add(head);
    const hs = new T3.Mesh(new T3.SphereGeometry(0.27, 12, 9), fur); head.add(hs); for (const x of [-0.15, 0.15]) { const e = new T3.Mesh(new T3.ConeGeometry(0.1, 0.2, 4), fur); e.position.set(x, 0.27, 0); head.add(e); }
    const cap = new T3.Mesh(new T3.CylinderGeometry(0.2, 0.24, 0.12, 10), lam('#ffb300')); cap.position.set(0, 0.2, 0.02); head.add(cap);
    for (let i = 0; i < 4; i++) {
      const g = new T3.Group(), tire = new T3.Mesh(new T3.CylinderGeometry(R, R, 0.44, 14), lam('#1d1d1d')), hub = new T3.Mesh(new T3.CylinderGeometry(R * 0.5, R * 0.5, 0.46, 8), lam('#cfd8dc')); tire.rotation.z = hub.rotation.z = Math.PI / 2; tire.castShadow = true; g.add(tire); g.add(hub);
      for (let k = 0; k < 8; k++) { const a = (k / 8) * Math.PI * 2, b = new T3.Mesh(new T3.BoxGeometry(0.46, 0.1, 0.16), lam('#111111')); b.position.set(0, Math.cos(a) * (R + 0.02), Math.sin(a) * (R + 0.02)); b.rotation.x = a; g.add(b); }
      const pivot = new T3.Group(); pivot.add(g); scene.add(pivot); wheelM.push({ pivot, g });
    }
  }
  // следы, брызги, трос, прицел лебёдки
  const NQ = 240, trk = { pos: new Float32Array(4 * NQ * 18), i: [0, 0, 0, 0], last: [null, null, null, null] };
  const trkG = new T3.BufferGeometry(); trkG.setAttribute('position', new T3.BufferAttribute(trk.pos, 3));
  const trkM = new T3.Mesh(trkG, new T3.MeshBasicMaterial({ color: C('#33210f'), transparent: true, opacity: 0.5, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 })); trkM.frustumCulled = false; scene.add(trkM);
  const blobs = []; for (let i = 0; i < 44; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 0), lam('#4a2f1c')); m.visible = false; scene.add(m); blobs.push({ m, life: 0, v: [0, 0, 0], r: 0.1 }); }
  let blobI = 0, blobAcc = 0;
  const rope = new T3.Mesh(new T3.CylinderGeometry(0.04, 0.04, 1, 5), lam('#8d6e63')); rope.visible = false; scene.add(rope);
  const aim = new T3.Mesh(new T3.TorusGeometry(0.9, 0.09, 6, 24), new T3.MeshBasicMaterial({ color: C('#ffeb3b'), fog: false })); aim.rotation.x = Math.PI / 2; aim.visible = false; scene.add(aim);

  // ---------- звук: мотор ----------
  let AC = null, eng = null;
  function audio() { if (AC) return; try { AC = new (window.AudioContext || window.webkitAudioContext)(); const o = AC.createOscillator(), f = AC.createBiquadFilter(), g = AC.createGain(); o.type = 'sawtooth'; f.type = 'lowpass'; f.frequency.value = 360; g.gain.value = 0; o.connect(f); f.connect(g); g.connect(AC.destination); o.start(); eng = { o, g }; } catch (e) { AC = null; } }
  function tone(fq, d, v) { if (!AC || muted) return; try { const t = AC.currentTime, o = AC.createOscillator(), g = AC.createGain(); o.type = 'triangle'; o.frequency.value = fq; g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t + d); o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + d + 0.02); } catch (e) { /* */ } }

  // ---------- управление ----------
  const TOG = ['awd', 'lock', 'low'];
  function flip(k) { if (mode !== 'play' || S.state !== 'play') return; sw[k] = !sw[k]; tone(sw[k] ? 760 : 420, 0.07, 0.12); }
  function rescue() { if (S.state === 'play' || S.state === 'dead') { S.rescue(); trk.last.fill(null); } }
  function again() { location.reload(); }
  addEventListener('keydown', (e) => {
    if (e.repeat) return; keys[e.code] = true; audio();
    if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
    if (e.code === 'Digit1' || e.code === 'KeyQ') flip('awd'); else if (e.code === 'Digit2' || e.code === 'KeyE') flip('lock'); else if (e.code === 'Digit3' || e.code === 'ShiftLeft') flip('low');
    else if (e.code === 'KeyR') rescue(); else if (e.code === 'KeyC') camFar = (camFar + 1) % 3; else if (e.code === 'Enter' && mode === 'win') again();
  });
  addEventListener('keyup', (e) => { keys[e.code] = false; });
  const hit = (x, y) => buttons.find((b) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
  const held = (id) => { for (const p of ptrs.values()) if (p === id) return true; return false; };
  cv.addEventListener('pointerdown', (e) => {
    audio(); try { cv.setPointerCapture(e.pointerId); } catch (er) { /* */ }
    const b = hit(e.clientX, e.clientY); if (!b) return;
    if (TOG.includes(b.id)) flip(b.id); else if (b.id === 'rescue') rescue(); else if (b.id === 'mute') muted = !muted; else if (b.id === 'cam') camFar = (camFar + 1) % 3; else if (b.id === 'again') again(); else ptrs.set(e.pointerId, b.id);
  });
  cv.addEventListener('pointermove', (e) => { const p = ptrs.get(e.pointerId); if (!p) return; const b = hit(e.clientX, e.clientY); if (b && b.id !== p && ['left', 'right', 'gas', 'rev'].includes(b.id) && ['left', 'right', 'gas', 'rev'].includes(p)) ptrs.set(e.pointerId, b.id); }); // палец съехал на соседнюю кнопку
  const up = (e) => ptrs.delete(e.pointerId);
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up); cv.addEventListener('contextmenu', (e) => e.preventDefault());
  function input() {
    const k = keys, g = !!(k.KeyW || k.ArrowUp) || held('gas'), r = !!(k.KeyS || k.ArrowDown) || held('rev'), l = !!(k.KeyA || k.ArrowLeft) || held('left'), rt = !!(k.KeyD || k.ArrowRight) || held('right');
    return { drive: g ? 1 : r ? -1 : 0, steer: (l ? 1 : 0) - (rt ? 1 : 0), hb: !!k.Space, winch: !!(k.KeyF || k.KeyX) || held('winch'), awd: sw.awd, lock: sw.lock, low: sw.low };
  }
  function layout() {
    const port = W < H2, sm = Math.min(W, H2) < 430, g = sm ? 8 : 12, bw = sm ? 78 : 92, bh = sm ? 74 : 86, by = H2 - bh - g - 4;
    buttons = [{ id: 'left', x: g, y: by, w: bw, h: bh }, { id: 'right', x: g * 2 + bw, y: by, w: bw, h: bh }, { id: 'gas', x: W - bw - g, y: by, w: bw, h: bh }, { id: 'rev', x: W - bw * 2 - g * 2, y: by, w: bw, h: bh },
      { id: 'rescue', x: W - 54, y: 10, w: 44, h: 44 }, { id: 'mute', x: W - 104, y: 10, w: 44, h: 44 }, { id: 'cam', x: W - 154, y: 10, w: 44, h: 44 }];
    const x0 = g * 3 + bw * 2 + 6, ww0 = sm ? 96 : 116, tw0 = Math.min(sm ? 64 : 78, (W - x0 - ww0 - bw * 2 - g * 4 - 18) / 3);
    if (port || tw0 < 46) { // стоя и в узком окне: один ряд над рулём и газом — лебёдка и три переключателя во всю ширину
      const th = sm ? 50 : 56, ww = Math.round(Math.min(150, W * 0.31)), tw = Math.min(96, (W - g * 2 - ww - 18) / 3), y = by - th - 12;
      buttons.push({ id: 'winch', x: g, y, w: ww, h: th });
      TOG.forEach((k, i) => buttons.push({ id: k, x: W - g - (3 - i) * tw - (2 - i) * 6, y, w: tw, h: th }));
    } else { // лёжа и на широком экране: всё в один нижний ряд
      buttons.push({ id: 'winch', x: x0, y: by, w: ww0, h: bh });
      TOG.forEach((k, i) => buttons.push({ id: k, x: x0 + ww0 + 8 + i * (tw0 + 6), y: by, w: tw0, h: bh }));
    }
  }
  const B = (id) => buttons.find((b) => b.id === id);

  // ---------- карта в углу ----------
  const mini = document.createElement('canvas'); mini.width = mini.height = map.N;
  { const g = mini.getContext('2d'), im = g.createImageData(map.N, map.N), c = new T3.Color(); for (let j = 0; j < map.N; j++) for (let i = 0; i < map.N; i++) { const k = j * map.N + i, x = i * map.C, z = j * map.C; groundColor(x, z, 0, c); if (map.H[k] < map.yW) c.set('#4fb3e8').convertSRGBToLinear(); c.convertLinearToSRGB(); im.data[k * 4] = c.r * 255; im.data[k * 4 + 1] = c.g * 255; im.data[k * 4 + 2] = c.b * 255; im.data[k * 4 + 3] = 255; } g.putImageData(im, 0, 0); }

  // ---------- рисование поверх ----------
  const rr = (x, y, w, h, r) => { ctx.beginPath(); if (!(w > 0 && h > 0)) return; r = Math.max(0, Math.min(r, w / 2, h / 2)); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); };
  const font = (px, w = 900) => { ctx.font = `${w} ${px}px system-ui, sans-serif`; };
  function lines(t, mw, px) { font(px, 800); const out = []; let cur = ''; for (const w of t.split(' ')) { const q = cur ? cur + ' ' + w : w; if (ctx.measureText(q).width > mw && cur) { out.push(cur); cur = w; } else cur = q; } if (cur) out.push(cur); return out; }
  function bubble(t, y, col = 'rgba(0,0,0,0.5)', cx = W / 2, mw = Math.min(W - 40, 620)) { const px = Math.min(W, H2) < 430 ? 15 : 18, L = lines(t, mw - 30, px), w = Math.min(mw, Math.max(...L.map((q) => ctx.measureText(q).width)) + 34), h = L.length * (px + 6) + 16; ctx.fillStyle = col; rr(cx - w / 2, y, w, h, 16); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; L.forEach((q, i) => ctx.fillText(q, cx, y + 8 + (px + 6) * (i + 0.5), w - 20)); return h; }
  function btn(b, txt, col, on, sub) {
    ctx.globalAlpha = on ? 0.97 : 0.72; ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(b.x, b.y + 5, b.w, b.h, 16); ctx.fill(); ctx.fillStyle = col; rr(b.x, b.y + (on ? 3 : 0), b.w, b.h, 16); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; font(Math.round(Math.min(b.h * (sub ? 0.34 : 0.44), b.w * 0.34, (b.w * 1.45) / Math.max(3, txt.length))));
    ctx.fillText(txt, b.x + b.w / 2, b.y + b.h * (sub ? 0.38 : 0.5) + (on ? 3 : 0), b.w - 8);
    if (sub) { font(Math.round(Math.min(13, b.h * 0.22)), 800); ctx.fillText(sub, b.x + b.w / 2, b.y + b.h * 0.76 + (on ? 3 : 0), b.w - 8); }
  }
  function hint() {
    if (S.state === 'dead') return [S.why === 'fuel' ? T.dFuel : S.why === 'water' ? T.dWater : T.dFlip, 'rgba(183,28,28,0.85)'];
    if (realT - flagT < 4) return [T.flag, 'rgba(230,81,0,0.9)'];
    if (S.t < 8 && !S.rescues) return [T.goal];
    if (S.stuckT > 1.2) { const mud = S.mudNow > 0.12; return [!sw.awd ? T.hAwd : !sw.low ? T.hLow : mud && !sw.lock ? T.hLock : S.target ? T.hWinch : mud ? T.hTree : T.hBack, 'rgba(230,81,0,0.9)']; }
    return null;
  }
  function drawHud(inp) {
    layout();
    const fw = Math.min(190, W * 0.4), fx = 12, fy = 14, k = S.fuel / S.cfg.tank;
    ctx.fillStyle = 'rgba(0,0,0,0.4)'; rr(fx, fy, fw, 24, 12); ctx.fill(); ctx.fillStyle = k < 0.22 ? '#e53935' : k < 0.45 ? '#ffb300' : '#7cb342'; rr(fx + 3, fy + 3, Math.max(8, (fw - 6) * k), 18, 9); ctx.fill();
    font(13); ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText('⛽ ' + Math.round(k * 100) + '%', fx + 10, fy + 13);
    // колёса сверху: серое — не ведёт, зелёное — держит, красное — буксует, синее — висит в воздухе
    const wx = fx + 4, wy = fy + 36; ctx.fillStyle = 'rgba(0,0,0,0.35)'; rr(wx, wy, 44, 56, 10); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.5)'; rr(wx + 16, wy + 8, 12, 40, 4); ctx.fill();
    S.wheels.forEach((wl, i) => { ctx.fillStyle = wl.air ? '#64b5f6' : !wl.drv ? '#90a4ae' : wl.slip > 0 || (Math.abs(inp.drive) > 0 && S.stuckT > 0.4) ? '#ff5252' : '#69f0ae'; rr(wx + (i % 2 ? 31 : 5), wy + (i < 2 ? 7 : 35), 8, 14, 3); ctx.fill(); });
    font(22); ctx.fillStyle = '#fff'; ctx.fillText(String(Math.round(Math.abs(S.speed) * 3.6)), wx + 54, wy + 20); font(11, 800); ctx.fillText(T.kmh, wx + 54, wy + 40);
    // карта: дорога, колея, болото, цель и мы
    const ms = Math.min(W < H2 ? 104 : 132, W * 0.3), mx = W - ms - 10, my = 64, sc = ms / map.SIZE;
    ctx.fillStyle = 'rgba(0,0,0,0.4)'; rr(mx - 3, my - 3, ms + 6, ms + 6, 10); ctx.fill(); ctx.save(); rr(mx, my, ms, ms, 8); ctx.clip(); ctx.drawImage(mini, mx, my, ms, ms);
    ctx.fillStyle = '#ffeb3b'; ctx.beginPath(); ctx.arc(mx + map.goal.x * sc, my + map.goal.z * sc, 5 + Math.sin(realT * 5), 0, 7); ctx.fill();
    if (!S.flag) { ctx.fillStyle = '#ff6d00'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(mx + map.swamp.x * sc, my + map.swamp.z * sc, 4, 0, 7); ctx.fill(); ctx.stroke(); }
    const yaw = S.yaw(); ctx.translate(mx + S.p[0] * sc, my + S.p[2] * sc); ctx.rotate(-yaw); ctx.fillStyle = '#ff3d00'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(0, 7); ctx.lineTo(4.5, -5); ctx.lineTo(-4.5, -5); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
    font(13); ctx.textAlign = 'center'; ctx.fillStyle = '#fff'; ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.lineWidth = 4; const dg = Math.round(Math.hypot(map.goal.x - S.p[0], map.goal.z - S.p[2])) + ' ' + T.m; ctx.strokeText(dg, mx + ms / 2, my + ms + 14); ctx.fillText(dg, mx + ms / 2, my + ms + 14);
    // кнопки
    btn(B('gas'), '▲', '#43a047', inp.drive > 0); btn(B('rev'), '▼', '#e53935', inp.drive < 0); btn(B('left'), '◀', '#546e7a', inp.steer > 0); btn(B('right'), '▶', '#546e7a', inp.steer < 0);
    btn(B('winch'), '⚓ ' + T.winch, S.target || S.winch ? '#5c6bc0' : '#78909c', inp.winch);
    TOG.forEach((q) => btn(B(q), T[q], sw[q] ? '#fb8c00' : '#546e7a', sw[q]));
    for (const [id, ch] of [['rescue', '↺'], ['mute', muted ? '🔇' : '🔊'], ['cam', '🎥']]) { const b = B(id); ctx.fillStyle = 'rgba(0,0,0,0.34)'; rr(b.x, b.y, b.w, b.h, 12); ctx.fill(); ctx.fillStyle = '#fff'; font(21); ctx.textAlign = 'center'; ctx.fillText(ch, b.x + b.w / 2, b.y + b.h / 2 + 1); }
    const h = hint(); if (h) { const x1 = fx + fw + 10, x2 = W - 164; if (x2 - x1 >= 400) bubble(h[0], 10, h[1], (x1 + x2) / 2, x2 - x1); else bubble(h[0], my + ms + 30, h[1]); } // на широком экране — в верхней полосе между топливом и кнопками, на узком — под картой
    if (!matchMedia('(pointer: coarse)').matches && !ptrs.size && S.t < 16 && !S.rescues) { font(14, 800); const tw = Math.min(ctx.measureText(T.keys).width + 36, W - 16), ky = B('gas').y - 44; ctx.fillStyle = 'rgba(0,0,0,0.45)'; rr(W / 2 - tw / 2, ky, tw, 32, 16); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.fillText(T.keys, W / 2, ky + 16, tw - 24); }
  }
  function star5(x, y, r, col) { ctx.fillStyle = col; ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, q = i & 1 ? r * 0.45 : r; ctx.lineTo(x + Math.cos(a) * q, y + Math.sin(a) * q); } ctx.closePath(); ctx.fill(); }
  function drawWin() {
    ctx.fillStyle = 'rgba(10,40,70,0.45)'; ctx.fillRect(0, 0, W, H2);
    const w = Math.min(W - 28, 440), h = Math.min(H2 - 24, 330), x = W / 2 - w / 2, y = H2 / 2 - h / 2, k = S.fuel / S.cfg.tank, st = [true, S.rescues === 0, S.flag];
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 22); ctx.fill();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#2e7d32'; font(28); ctx.fillText(T.win, W / 2, y + 40, w - 24);
    [T.s1, T.s2, T.s3].forEach((s, i) => { const cx = W / 2 + (i - 1) * w * 0.3; star5(cx, y + 108, i === 1 ? 40 : 33, st[i] ? '#ffc107' : '#cfd8dc'); ctx.fillStyle = '#546e7a'; font(13, 800); ctx.fillText(s, cx, y + 162, w * 0.29); });
    ctx.fillStyle = '#37474f'; font(17, 800); ctx.fillText(`${T.time}: ${S.t.toFixed(0)} ${T.sec}   ·   ${T.fuel}: ${Math.round(k * 100)}%`, W / 2, y + 204, w - 24);
    const b = { id: 'again', x: W / 2 - 100, y: y + h - 78, w: 200, h: 56 }; buttons = [b]; btn(b, '↻ ' + T.again, '#43a047', false);
  }

  // ---------- кадр ----------
  const qT = new T3.Quaternion(), v3 = new T3.Vector3(), UP = new T3.Vector3(0, 1, 0);
  function drawScene(inp, dt) {
    const p = S.p; qT.set(S.q[0], S.q[1], S.q[2], S.q[3]); truck.position.set(p[0], p[1], p[2]); truck.quaternion.copy(qT);
    const bx = v3.set(1, 0, 0).applyQuaternion(qT).clone(), by = v3.set(0, 1, 0).applyQuaternion(qT).clone(), bz = v3.set(0, 0, 1).applyQuaternion(qT).clone();
    S.wheels.forEach((wl, i) => {
      const m = wl.m, q = wheelM[i]; q.pivot.position.set(p[0] + bx.x * m[0] + by.x * (m[1] - wl.len) + bz.x * m[2], p[1] + bx.y * m[0] + by.y * (m[1] - wl.len) + bz.y * m[2], p[2] + bx.z * m[0] + by.z * (m[1] - wl.len) + bz.z * m[2]);
      q.pivot.quaternion.copy(qT); q.pivot.rotateY(wl.front ? S.steer : 0); q.g.rotation.x = wl.spin;
      // след: тёмная полоса там, где колесо шло по мягкому или буксовало
      const on = !wl.air && (wl.mud > 0.08 || wl.slip > 0), c = wl.pc, L = trk.last[i];
      if (!on) { trk.last[i] = null; return; }
      const y = map.h(c[0], c[2]) + 0.05, a = [c[0] + bx.x * 0.23, y, c[2] + bx.z * 0.23], b = [c[0] - bx.x * 0.23, y, c[2] - bx.z * 0.23];
      if (!L) { trk.last[i] = [a, b]; return; }
      if (Math.hypot(a[0] - L[0][0], a[2] - L[0][2]) < 0.4) return;
      const o = (i * NQ + trk.i[i]) * 18, P = trk.pos; trk.i[i] = (trk.i[i] + 1) % NQ;
      [L[0], L[1], a, L[1], b, a].forEach((q2, k) => { P[o + k * 3] = q2[0]; P[o + k * 3 + 1] = q2[1]; P[o + k * 3 + 2] = q2[2]; });
      trk.last[i] = [a, b]; trkG.attributes.position.needsUpdate = true;
      blobAcc += dt; if (wl.slip > 0.3 && wl.mud > 0.12 && Math.random() < 0.5) { const bl = blobs[blobI++ % blobs.length]; bl.life = 0.8; bl.r = 0.07 + Math.random() * 0.1; const sg = Math.sign(S.thr) || 1; bl.v = [-bz.x * (2 + Math.random() * 4) * sg + (Math.random() - 0.5) * 2, 3 + Math.random() * 4, -bz.z * (2 + Math.random() * 4) * sg + (Math.random() - 0.5) * 2]; bl.m.position.set(c[0], y + 0.2, c[2]); bl.m.visible = true; }
    });
    for (const bl of blobs) if (bl.life > 0) { bl.life -= dt; if (bl.life <= 0) { bl.m.visible = false; continue; } bl.v[1] -= 14 * dt; bl.m.position.x += bl.v[0] * dt; bl.m.position.y += bl.v[1] * dt; bl.m.position.z += bl.v[2] * dt; bl.m.scale.setScalar(bl.r); }
    // трос и прицел лебёдки
    if (S.winch && S.winch.hp) { const a = S.winch.hp, b = S.winch.a, d = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]); rope.visible = true; rope.position.set((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2); rope.scale.set(1, d, 1); rope.quaternion.setFromUnitVectors(UP, v3.set(b[0] - a[0], b[1] - a[1], b[2] - a[2]).normalize()); } else rope.visible = false;
    const tg = S.target || (S.winch && S.winch.t); aim.visible = !!tg && S.state === 'play'; if (tg) { aim.position.set(tg.x, tg.y + 1.0, tg.z); const s = 1 + 0.15 * Math.sin(realT * 9); aim.scale.set(s, s, s); }
    beacon.material.opacity = 0.16 + 0.08 * Math.sin(realT * 3);
    // камера за грузовиком: плавно поворачивается следом, не уходит под землю
    const yaw = Math.atan2(bz.x, bz.z); let dy = yaw - camYaw; while (dy > Math.PI) dy -= 2 * Math.PI; while (dy < -Math.PI) dy += 2 * Math.PI; camYaw += dy * Math.min(1, dt * 2.6);
    // стоя камера смотрит далеко вперёд (горизонт в верхней четверти), лёжа — ближе; три расстояния по кнопке
    const port = tall(), kd = [1, 1.5, 0.72][camFar], kh = [1, 1.8, 0.75][camFar], dist = (port ? 11 : 9.5) * kd, hgt = (port ? 4.1 : 3.2) * kh, ah = port ? 13 : 5.4;
    const cx = p[0] - Math.sin(camYaw) * dist, cz = p[2] - Math.cos(camYaw) * dist, cy = Math.max(p[1] + hgt, map.h(cx, cz) + 1.6);
    cam.position.lerp(v3.set(cx, cy, cz), Math.min(1, dt * 6)); cam.lookAt(p[0] + Math.sin(camYaw) * ah, p[1] + 0.9, p[2] + Math.cos(camYaw) * ah);
    sun.target.position.set(p[0], p[1], p[2]); sun.position.set(p[0] - 38, p[1] + 78, p[2] + 30); sun.target.updateMatrixWorld();
    renderer.render(scene, cam);
  }
  function frame(now) { try { frame1(now); } catch (e) { if (!frame.err) { frame.err = 1; try { console.error(e); } catch (q) { /* */ } } } requestAnimationFrame(frame); }
  function frame1(now) {
    const raw = (now - last) / 1000, dt = Math.min(0.05, raw); last = now; realT += dt; perfTick(raw);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    let inp = { drive: 0, steer: 0, hb: true, winch: false, awd: sw.awd, lock: sw.lock, low: sw.low };
    if (!dbg.freeze && !document.hidden) {
      if (mode === 'play') inp = input();
      acc += dt; let n = 0; while (acc >= M.DT && n < 10) { S.step(inp); acc -= M.DT; n++; }
      for (const e of S.events) { if (e.e === 'dead') tone(160, 0.4, 0.15); else if (e.e === 'hook') tone(620, 0.06, 0.1); else if (e.e === 'flag') { flagT = realT; flag.visible = false; tone(990, 0.12, 0.14); tone(1320, 0.25, 0.12); } else if (e.e === 'win') { mode = 'win'; tone(1200, 0.3, 0.14); } }
      S.events.length = 0;
      if (S.state === 'dead' && S.deadT > 2) rescue();
    }
    if (eng) { const on = mode === 'play' && S.state === 'play' && !muted && !document.hidden, t = AC.currentTime; eng.o.frequency.setTargetAtTime(46 + Math.abs(S.speed) * (sw.low ? 16 : 7) + Math.abs(S.thr) * 34, t, 0.08); eng.g.gain.setTargetAtTime(on ? 0.025 + Math.abs(S.thr) * 0.04 : 0, t, 0.1); }
    ctx.clearRect(0, 0, W, H2);
    drawScene(inp, dt);
    if (mode === 'win' && S.wonT > 0.9) drawWin(); else drawHud(inp);
  }
  try { renderer.compile(scene, cam); } catch (e) { /* */ }
  window.__mud3 = { S, sw, keys, dbg, cam, renderer, get gq() { return gq; }, get mode() { return mode; }, get buttons() { layout(); return buttons; }, flip };
  requestAnimationFrame(frame);
})();
