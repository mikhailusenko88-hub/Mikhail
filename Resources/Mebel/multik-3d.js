/* 3D-движок мультиков (three.js): игрушечные герои из простых форм, тот же сценарий и таймлайн, что у 2D.
   Подключение: MK3D.init(THREE) после загрузки three.module.min.js. Рисует кадр в 2D-контекст (для записи видео). */
'use strict';
(function (global) {
const MK3D = { ready: false, hq: false }; // hq — «как в кино»: мягкая шерсть, мягкий свет и тени, живые глаза (дольше считает)
let THREE, R, GL, scene, cam, sun, hemi, grad, OL, texCache = {};
const XW = 10; // ширина сцены в метрах (x 0..1 → −5..+5)
const X = x => (x - .5) * XW;
const clamp = (v, a, b) => v < a ? a : v > b ? b : v, lerp = (a, b, t) => a + (b - a) * t;
const ease = t => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
function rng(seed) { let s = (seed >>> 0) || 0x9e3779b9; return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }
function col(c) { return new THREE.Color(c || '#888888'); }

MK3D.init = function (T) {
  THREE = T; tmpInit();
  GL = document.createElement('canvas'); GL.width = 1920; GL.height = 1080;
  try { R = new THREE.WebGLRenderer({ canvas: GL, antialias: true, preserveDrawingBuffer: true }); } catch (e) { console.log('WebGL нет', e); return false; }
  R.setPixelRatio(1); R.setSize(1920, 1080, false);
  R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap; R.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene();
  cam = new THREE.PerspectiveCamera(38, 16 / 9, .1, 200);
  hemi = new THREE.HemisphereLight(0xdff2ff, 0x6a9a50, 1.1); scene.add(hemi);
  sun = new THREE.DirectionalLight(0xfff1d6, 2.2); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 7, bottom: -5, near: 1, far: 40 }); sun.shadow.radius = 4; sun.shadow.bias = -.0005;
  scene.add(sun); scene.add(sun.target);
  const d = new Uint8Array([90, 170, 255]); grad = new THREE.DataTexture(d, 3, 1, THREE.RedFormat); grad.minFilter = grad.magFilter = THREE.NearestFilter; grad.needsUpdate = true;
  OL = new THREE.MeshBasicMaterial({ color: 0x2b1d16, side: THREE.BackSide });
  if (MK3D.hq) { setupHQ(); hqReady = true; }
  MK3D.ready = true; return true;
};
let rim = null;
function setupHQ() { // мягкий «киношный» свет без контуров
  OL.visible = false;
  R.toneMapping = THREE.NeutralToneMapping; R.toneMappingExposure = 1.0;
  R.shadowMap.type = THREE.VSMShadowMap; sun.shadow.radius = 9; sun.shadow.blurSamples = 16; sun.shadow.bias = -.0004; sun.shadow.mapSize.set(2048, 2048);
  const env = canvasTex(256, 128, (g) => { const gr = g.createLinearGradient(0, 0, 0, 128); gr.addColorStop(0, '#dfeaff'); gr.addColorStop(.48, '#ffffff'); gr.addColorStop(.52, '#d8d2c4'); gr.addColorStop(1, '#8a8478'); g.fillStyle = gr; g.fillRect(0, 0, 256, 128);
    const sp = g.createRadialGradient(70, 30, 2, 70, 30, 30); sp.addColorStop(0, 'rgba(255,255,255,1)'); sp.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = sp; g.fillRect(0, 0, 256, 128); });
  env.mapping = THREE.EquirectangularReflectionMapping; const pm = new THREE.PMREMGenerator(R); scene.environment = pm.fromEquirectangular(env).texture; scene.userData.env = scene.environment; scene.environmentIntensity = .45; pm.dispose();
  rim = new THREE.DirectionalLight(0xffffff, 1.4); rim.position.set(-3, 4, -6); scene.add(rim); scene.add(rim.target);
}
let hqReady = false;
MK3D.setQuality = function (q) { const hq = q === 'hq'; if (hq === MK3D.hq) return; MK3D.hq = hq; if (!MK3D.ready) return;
  if (hq && !hqReady) { setupHQ(); hqReady = true; }
  OL.visible = !hq; R.toneMapping = hq ? THREE.NeutralToneMapping : THREE.NoToneMapping; R.shadowMap.type = hq ? THREE.VSMShadowMap : THREE.PCFSoftShadowMap; scene.environment = hq ? scene.userData.env || null : null; if (rim) rim.visible = hq;
  // всё построенное — заново, с другими материалами
  for (const k in rigCache) { scene.remove(rigCache[k].root); delete rigCache[k]; } for (const k in propCache) { scene.remove(propCache[k]); delete propCache[k]; } for (const k in locCache) { scene.remove(locCache[k]); delete locCache[k]; } for (const k in themeCache) { scene.remove(themeCache[k]); delete themeCache[k]; }
  for (const k in matCache) delete matCache[k]; curLoc = null; curTheme = null; R.shadowMap.needsUpdate = true; };
function soft(c, map) { // бархатная шерсть-«игрушка»
  const k = 'hq' + (c || '') + (map ? map.uuid : ''); if (!map && matCache[k]) return matCache[k];
  const base = col(c), sh = base.clone().lerp(new THREE.Color(1, 1, 1), .55);
  const m = new THREE.MeshPhysicalMaterial({ color: map ? 0xffffff : base, map: map || null, roughness: .62, metalness: 0, sheen: .55, sheenRoughness: .35, envMapIntensity: .8, sheenColor: map ? new THREE.Color(1, .95, .9) : sh, clearcoat: 0 });
  if (!map) matCache[k] = m; return m;
}
function matte(c, map) { const k = 'mt' + (c || '') + (map ? map.uuid : ''); if (!map && matCache[k]) return matCache[k]; const m = new THREE.MeshStandardMaterial({ color: map ? 0xffffff : col(c), map: map || null, roughness: .92, metalness: 0, envMapIntensity: .6 }); if (!map) matCache[k] = m; return m; }
function glossy(c, rough) { const k = 'gl' + c + (rough || 0); if (matCache[k]) return matCache[k]; return (matCache[k] = new THREE.MeshPhysicalMaterial({ color: col(c), roughness: rough != null ? rough : .12, clearcoat: 1, clearcoatRoughness: .05 })); }
let blobTex = null;
function contactShadow(parent, r) { if (!blobTex) blobTex = canvasTex(128, 128, (g) => { const gr = g.createRadialGradient(64, 64, 4, 64, 64, 62); gr.addColorStop(0, 'rgba(20,16,12,.55)'); gr.addColorStop(.6, 'rgba(20,16,12,.18)'); gr.addColorStop(1, 'rgba(20,16,12,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(r * 2, r * 2), new THREE.MeshBasicMaterial({ map: blobTex, transparent: true, depthWrite: false })); m.rotation.x = -Math.PI / 2; m.position.y = .012; m.renderOrder = 1; parent.add(m); return m;
};

// ---------- материалы и формы ----------
const matCache = {};
let inRig = false;
function toon(c, map) { if (MK3D.hq) return inRig ? soft(c, map) : matte(c, map); const k = (c || '') + (map ? map.uuid : ''); if (!map && matCache[k]) return matCache[k]; const m = new THREE.MeshToonMaterial({ color: map ? 0xffffff : col(c), gradientMap: grad, map: map || null }); if (!map) matCache[k] = m; return m; }
function basic(c) { const k = 'b' + c; if (matCache[k]) return matCache[k]; return (matCache[k] = new THREE.MeshBasicMaterial({ color: col(c) })); }
function mesh(geo, mat, outline, parent) { const m = new THREE.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; if (outline) { const o = new THREE.Mesh(geo, OL); o.scale.setScalar(1 + outline); o.castShadow = false; m.add(o); } if (parent) parent.add(m); return m; }
const G = {
  sph: (r, w, h) => new THREE.SphereGeometry(r, w || 32, h || 24),
  cap: (r, l) => new THREE.CapsuleGeometry(r, l, 8, 16),
  cone: (r, h, s) => new THREE.ConeGeometry(r, h, s || 24),
  cyl: (a, b, h, s, open) => new THREE.CylinderGeometry(a, b, h, s || 24, 1, !!open),
  box: (x, y, z) => new THREE.BoxGeometry(x, y, z),
  tor: (r, t, arc) => new THREE.TorusGeometry(r, t, 12, 32, arc || Math.PI * 2),
};
function canvasTex(w, h, draw) { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; }
function stripeTex(base, stripe, n, y0, y1) { return canvasTex(256, 128, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 128); g.fillStyle = stripe; for (let i = 0; i < n; i++) { const x = i * 256 / n + 10, m = (y0 + y1) / 2; g.beginPath(); g.moveTo(x + 4, y0); g.quadraticCurveTo(x + 12, m, x + 5, y1); g.lineTo(x + 9, y1); g.quadraticCurveTo(x + 20, m, x + 12, y0); g.fill(); } }); }
function spotTex(base, spot, seed) { return canvasTex(256, 128, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 128); g.fillStyle = spot; const r = rng(seed); for (let i = 0; i < 14; i++) { g.beginPath(); g.ellipse(r() * 256, 20 + r() * 88, 8 + r() * 10, 6 + r() * 8, 0, 0, 7); g.fill(); } }); }

// ---------- персонаж ----------
const rigCache = {};
function buildRig(spec) { inRig = true; try { const r = buildRig0(spec); if (MK3D.hq) addFur(r); return r; } finally { inRig = false; } }
// ---------- шерсть (слои-«оболочки»: на каждом слое остаются только кончики шерстинок) ----------
const FEATHER_KINDS = new Set(['owl', 'bird', 'duck', 'chick']);
const FUR_KINDS = new Set(['cat', 'dog', 'bear', 'rabbit', 'mouse', 'fox', 'hedgehog', 'owl', 'bird', 'duck', 'chick', 'lion', 'squirrel', 'wolf', 'cow', 'pig', 'sheep']);
let furNoise = null;
function furTex() { // отдельные волоски: круглые сечения с яркой серединой → чем выше слой, тем тоньше волосок
  if (furNoise) return furNoise; const r = rng(77), S = 512;
  furNoise = canvasTex(S, S, (g) => { g.fillStyle = '#000'; g.fillRect(0, 0, S, S); g.globalCompositeOperation = 'lighten';
    for (let i = 0; i < 16000; i++) { const x = r() * S, y = r() * S, rad = 1.3 + r() * 1.1, top = .5 + r() * .5;
      for (const [dx, dy] of [[0, 0], [S, 0], [-S, 0], [0, S], [0, -S]]) { const cx = x + dx, cy = y + dy; if (cx < -8 || cx > S + 8 || cy < -8 || cy > S + 8) continue;
        const gr = g.createRadialGradient(cx, cy, 0, cx, cy, rad); const v = Math.round(255 * top); gr.addColorStop(0, `rgb(${v},${v},${v})`); gr.addColorStop(1, 'rgb(0,0,0)'); g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, rad, 0, 7); g.fill(); } } });
  furNoise.colorSpace = THREE.NoColorSpace; furNoise.wrapS = furNoise.wrapT = THREE.RepeatWrapping; furNoise.magFilter = THREE.LinearFilter; furNoise.minFilter = THREE.LinearFilter; furNoise.generateMipmaps = false; return furNoise; }
const furMatCache = {};
function furMat(src, k, N, dens) { const key = src.uuid + ':' + k + ':' + dens; if (furMatCache[key]) return furMatCache[key];
  const f = k / N, nz = furTex().clone(); nz.needsUpdate = true; nz.repeat.set(dens * 2, dens);
  const m = new THREE.MeshPhysicalMaterial({ color: src.color.clone().multiplyScalar(.55 + .6 * Math.pow(f, .8)), map: src.map || null, roughness: .8, sheen: .8 * f, sheenRoughness: .35, sheenColor: src.sheenColor, alphaMap: nz, alphaTest: .02 + f * .92, envMapIntensity: .75 });
  return (furMatCache[key] = m); }
function addFur(rig) {
  const n = rig.n; if (rig.human || !FUR_KINDS.has(rig.kind)) return;
  const fc = new Set([n.c.body, n.c.belly, n.c.stripe, n.c.mane].filter(Boolean).map(c => new THREE.Color(c).getHexString()));
  const eyeG = new Set(rig.eyes.map(e => e.g)); const list = [];
  rig.pose.traverse(o => { if (!o.isMesh || o.userData.shell || o.userData.noFur || !o.material || !o.material.isMeshPhysicalMaterial || o.material.clearcoat > 0) return; let p = o.parent; while (p) { if (eyeG.has(p)) return; p = p.parent; }
    const isFur = o.material.map ? true : fc.has(o.material.color.getHexString()); if (isFur) list.push(o); });
  if (rig.head && (!FEATHER_KINDS.has(rig.kind) || rig.kind === 'chick')) { const furSet = new Set(list); for (const ch of rig.head.children) { if (eyeG.has(ch) || furSet.has(ch) || !ch.position) continue; let anyFur = false; ch.traverse(o => { if (furSet.has(o)) anyFur = true; }); if (anyFur) continue; const v = ch.position.clone(); if (v.lengthSq() > 1e-6) ch.position.add(v.normalize().multiplyScalar(.042)); } }
  const L = .026; for (const e of rig.eyes) { e.g.position.z += L * .55; }
  rig.R0 = rig.root; rig.root.updateMatrixWorld(true);
  // запретные зоны (глаза, нос, рот, щёки) — волоски там не растут, чтобы не закрывать мордочку
  const keep = []; const furSet = new Set(list);
  for (const e of rig.eyes) { const w = new THREE.Vector3(); e.g.getWorldPosition(w); keep.push([w, e.eR * 1.45]); }
  if (rig.head) rig.head.traverse(o => { if (!o.isMesh || furSet.has(o) || o.userData.shell) return; let p = o.parent; while (p) { if (eyeG.has(p)) return; p = p.parent; } o.geometry.computeBoundingSphere(); const r = o.geometry.boundingSphere.radius * Math.max(o.scale.x, o.scale.y, o.scale.z); if (r > .12) return; const w = new THREE.Vector3(); o.getWorldPosition(w); const hc = new THREE.Vector3(); rig.head.getWorldPosition(hc); if (w.z < hc.z) return; keep.push([w, r + .02]); });
  rig.root.traverse(o => { if (!o.isMesh || !o.userData.noFur) return; o.geometry.computeBoundingSphere(); const ws = new THREE.Vector3(); o.getWorldScale(ws); const w = o.geometry.boundingSphere.center.clone().applyMatrix4(o.matrixWorld); keep.push([w, o.geometry.boundingSphere.radius * Math.max(ws.x, ws.y, ws.z) * .9]); });
  const O = rig.spec.outfit || {}; const clothed = !!(O.shirt || O.overalls || O.dress || O.pajamas || O.suit);
  const under = (o, g) => { let p = o.parent; while (p) { if (p === g) return true; p = p.parent; } return false; };
  if (FEATHER_KINDS.has(rig.kind)) { addBirdFeathers(rig, list, keep, under); rig.fur = []; rig.root.traverse(o => { if (o.userData.strands) rig.fur.push(o); }); return; }
  for (const o of list) { if (clothed && (under(o, rig.body) || rig.legs.some(g => under(o, g)) || (O.shirt || O.suit || O.pajamas || O.dress) && rig.arms.some(g => under(o, g)))) continue; { let fk = 1, pp = o; while (pp) { if (pp.userData.furK != null) { fk = Math.min(fk, pp.userData.furK); } pp = pp.parent; } const reg = under(o, rig.tail) ? 'tail' : rig.legs.some(g => under(o, g)) ? 'leg' : rig.arms.some(g => under(o, g)) ? 'arm' : under(o, rig.body) ? 'body' : 'head'; addStrands(rig, o, L, keep, fk, reg); } }
  rig.fur = []; rig.root.traverse(o => { if (o.userData.strands) rig.fur.push(o); });
}
// ---------- волоски-нити: каждый волосок — отдельная линия; блик вдоль волоска (Kajiya-Kay), качание от движения ----------
const FUR_VS = `
attribute vec3 aRoot; attribute vec3 aNorm; attribute vec2 aUv; attribute vec4 aRnd; attribute float aT; attribute vec3 aTilt;
uniform float uLen; uniform vec3 uLag; uniform float uGrav; uniform float uTime;
varying vec3 vT; varying vec3 vW; varying float vt; varying vec2 vUv; varying float vVar;
void main(){
  vec3 nW = normalize(mat3(modelMatrix) * aNorm);
  float sc = length(mat3(modelMatrix) * vec3(0.0,1.0,0.0)) / max(length(aNorm),1e-4);
  vec3 tan1 = normalize(cross(nW, abs(nW.y) < .95 ? vec3(0.,1.,0.) : vec3(1.,0.,0.))); vec3 tan2 = cross(nW, tan1);
  vec3 down = vec3(0.,-1.,0.) - nW * dot(vec3(0.,-1.,0.), nW); float dl = length(down); vec3 comb = dl > .05 ? down / dl : vec3(0.);
  vec3 tiltW = mat3(modelMatrix) * aTilt;
  vec3 dir = normalize(nW * .75 + comb * .45 + tiltW);
  float len = uLen * aRnd.x * sc;
  float t = aT;
  vec3 root = (modelMatrix * vec4(aRoot, 1.0)).xyz;
  float sway = sin(uTime * 2.3 + aRnd.w * 40.0) * .06;
  vec3 bend = (vec3(0.0, -uGrav, 0.0) + uLag + tan1 * sway) * len;
  vec3 wave = tan2 * sin(t * 6.0 + aRnd.w * 20.0) * len * .08 * t;
  vec3 p = root + dir * len * t + bend * t * t + wave;
  vec3 tg = normalize(dir * len + bend * 2.0 * t);
  vT = tg; vW = p; vt = t; vUv = aUv; vVar = aRnd.w;
  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
}`;
const FUR_FS = `
uniform vec3 uColor; uniform sampler2D uMap; uniform float uHasMap; uniform vec3 uSunDir; uniform vec3 uSunCol; uniform vec3 uSky; uniform vec3 uGround; uniform vec3 uRimDir; uniform vec3 uRimCol;
varying vec3 vT; varying vec3 vW; varying float vt; varying vec2 vUv; varying float vVar;
void main(){
  vec3 base = uHasMap > .5 ? texture2D(uMap, vUv).rgb : uColor;
  base *= .9 + vVar * .2; base = mix(base * .86, base * 1.06, smoothstep(0., 1., vt));
  vec3 T = normalize(vT); vec3 V = normalize(cameraPosition - vW); vec3 L = normalize(uSunDir);
  float TL = dot(T, L), TV = dot(T, V);
  float diff = sqrt(max(0., 1. - TL * TL));
  vec3 H = normalize(L + V); float TH = dot(T, H); float spec = pow(sqrt(max(0., 1. - TH * TH)), 80.0);
  float spec2 = pow(sqrt(max(0., 1. - TH * TH)), 18.0);
  float ao = mix(.8, 1.0, smoothstep(0., .9, vt));
  float rimT = dot(T, normalize(uRimDir)); float rim = sqrt(max(0., 1. - rimT * rimT));
  vec3 amb = mix(uGround, uSky, .5 + .5 * T.y) * .45; amb = mix(vec3(dot(amb, vec3(.333))), amb, .25);
  vec3 c = base * (amb + uSunCol * diff * .85) * ao + uSunCol * (spec * .16 + spec2 * base * .18) * ao + uRimCol * rim * .12 * vt;
  c = max(mix(vec3(dot(c, vec3(.299, .587, .114))), c, 1.15), 0.);
  gl_FragColor = vec4(c, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
const furMats = [];
function strandMat(src) {
  const m = new THREE.ShaderMaterial({ vertexShader: FUR_VS, fragmentShader: FUR_FS, toneMapped: true,
    uniforms: { uLen: { value: .05 }, uLag: { value: new THREE.Vector3() }, uGrav: { value: .2 }, uTime: { value: 0 }, uColor: { value: src.color.clone() }, uMap: { value: src.map || null }, uHasMap: { value: src.map ? 1 : 0 },
      uSunDir: { value: new THREE.Vector3(0, 1, 0) }, uSunCol: { value: new THREE.Color(1, 1, 1) }, uSky: { value: new THREE.Color(1, 1, 1) }, uGround: { value: new THREE.Color(.5, .5, .5) }, uRimDir: { value: new THREE.Vector3(0, 0, -1) }, uRimCol: { value: new THREE.Color(1, 1, 1) } } });
  furMats.push(m); return m;
}
function furFrame(rig, T) { // свет и качание шерсти на кадр
  if (!rig.fur || !rig.fur.length) return; const hp = new THREE.Vector3(); rig.head.getWorldPosition(hp);
  const st = rig._fs || (rig._fs = { t: T, p: hp.clone(), lag: new THREE.Vector3(), vel: new THREE.Vector3() }); const dt = T - st.t;
  if (dt > 0 && dt < .25) { const v = hp.clone().sub(st.p).divideScalar(dt); const target = v.multiplyScalar(-.18); target.clampLength(0, .9);
    const k = 1 - Math.exp(-dt * 9); st.vel.add(target.sub(st.lag).multiplyScalar(k * 1.6)); st.vel.multiplyScalar(Math.exp(-dt * 6)); st.lag.addScaledVector(st.vel, Math.min(1, dt * 8)); }
  else if (Math.abs(dt) >= .25) { st.lag.set(0, 0, 0); st.vel.set(0, 0, 0); }
  st.t = T; st.p.copy(hp);
  const sd = sun.position.clone().sub(sun.target.position).normalize(), rd = rim ? rim.position.clone().sub(rim.target.position).normalize() : new THREE.Vector3(0, 0, -1);
  for (const ls of rig.fur) { if (!ls.material.uniforms) continue; const u = ls.material.uniforms; u.uTime.value = T; u.uLag.value.copy(st.lag); u.uSunDir.value.copy(sd); u.uSunCol.value.copy(sun.color).multiplyScalar(sun.intensity * .3);
    u.uSky.value.copy(hemi.color).multiplyScalar(hemi.intensity * 1.6 + .35); u.uGround.value.copy(hemi.groundColor).multiplyScalar(hemi.intensity * 1.6 + .35); u.uRimDir.value.copy(rd); if (rim) u.uRimCol.value.copy(rim.color).multiplyScalar(rim.intensity); }
}
// ---------- перья (птицы): гладкое тело с рисунком перьев + настоящие перья на крыльях, хвосте и хохолке ----------
const featherCache = {};
function scaleTile(kind) { // одна ячейка «черепицы» перьев: верхние перья лежат поверх нижних, видна мягкая скруглённая кромка
  const key = 'st' + kind; if (featherCache[key]) return featherCache[key];
  const S = 128, W = 128, H = 64, Rr = 74, cv = document.createElement('canvas'); cv.width = cv.height = S; const g = cv.getContext('2d'), im = g.createImageData(S, S);
  for (let py = 0; py < S; py++) for (let px = 0; px < S; px++) {
    let best = null; const r0 = Math.floor(py / H);
    for (let r = r0 - 2; r <= r0 + 1; r++) { const off = (r & 1) ? W / 2 : 0; for (let j = -1; j <= 1; j++) { const cx = j * W + off + W / 2, cy = r * H; const dx = px - cx, dy = py - cy;
        let inside = false, edge = 0; if (Math.abs(dx) <= Rr) { if (dy <= 0) { inside = dy > -H * 2.2; edge = Rr - Math.abs(dx); } else { const d = Math.hypot(dx, dy); inside = d <= Rr; edge = Rr - d; } }
        if (inside && (!best || cy < best.cy)) best = { cy, edge, dx, dy }; } }
    let v = 1, h = 1; if (best) { const e = Math.max(0, best.edge), q = Math.min(1, e / 18); v = .9 + .1 * q * q * (3 - 2 * q); h = Math.min(1, e / 30); }
    const val = kind === 'bump' ? Math.round(h * 255) : Math.round(v * 255); const i = (py * S + px) * 4; im.data[i] = im.data[i + 1] = im.data[i + 2] = val; im.data[i + 3] = 255; }
  g.putImageData(im, 0, 0); return (featherCache[key] = cv);
}
function featherSkin(src, rep, chevron) { // карта цвета и рельефа для тела/головы: полоски героя сохраняются, поверх — рисунок перьев
  const key = 'sk' + (src.map ? src.map.uuid : '') + rep.join('x') + (chevron || '');
  if (featherCache[key]) return featherCache[key];
  const Wc = 1024, Hc = 512, tw = Wc / rep[0], th = Hc / rep[1];
  const mk = (bump) => { const cv = document.createElement('canvas'); cv.width = Wc; cv.height = Hc; const g = cv.getContext('2d');
    if (!bump && src.map && src.map.image) g.drawImage(src.map.image, 0, 0, Wc, Hc); else { g.fillStyle = '#fff'; g.fillRect(0, 0, Wc, Hc); }
    if (!bump && chevron) { g.strokeStyle = chevron; g.globalAlpha = .55; g.lineWidth = 5; g.lineCap = 'round'; const r = rng(31);
      for (let y = Hc * .22; y < Hc * .9; y += 34) for (let x = 0; x < Wc; x += 46) { const xx = x + ((y / 34) % 2) * 23 + (r() - .5) * 6, yy = y + (r() - .5) * 5, w2 = 9 + r() * 4; g.beginPath(); g.moveTo(xx - w2, yy - 5); g.lineTo(xx, yy + 4); g.lineTo(xx + w2, yy - 5); g.stroke(); }
      g.globalAlpha = 1; }
    g.globalCompositeOperation = bump ? 'source-over' : 'multiply'; const tile = scaleTile(bump ? 'bump' : 'col');
    for (let j = 0; j < rep[1]; j++) for (let i = 0; i < rep[0]; i++) g.drawImage(tile, i * tw, j * th, tw + .5, th + .5);
    const t = new THREE.CanvasTexture(cv); t.colorSpace = bump ? THREE.NoColorSpace : THREE.SRGBColorSpace; t.wrapS = THREE.RepeatWrapping; t.anisotropy = 4; return t; };
  return (featherCache[key] = { map: mk(false), bump: mk(true) });
}
function featherDetail() { if (featherCache.det) return featherCache.det; const t = canvasTex(64, 256, (g) => { g.fillStyle = '#fff'; g.fillRect(0, 0, 64, 256);
    const gr = g.createLinearGradient(0, 0, 64, 0); gr.addColorStop(0, 'rgba(0,0,0,.10)'); gr.addColorStop(.25, 'rgba(0,0,0,0)'); gr.addColorStop(.75, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,.10)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 256);
    g.strokeStyle = 'rgba(0,0,0,.05)'; g.lineWidth = 1; for (let y = 30; y < 260; y += 5) { g.beginPath(); g.moveTo(32, y); g.lineTo(4, y - 20); g.moveTo(32, y); g.lineTo(60, y - 20); g.stroke(); }
    g.strokeStyle = 'rgba(40,25,10,.28)'; g.lineWidth = 2.2; g.beginPath(); g.moveTo(32, 256); g.lineTo(32, 14); g.stroke(); }); return (featherCache.det = t); }
function featherGeo(len, wid, cup) { const key = 'fg' + len.toFixed(3) + wid.toFixed(3) + cup; if (featherCache[key]) return featherCache[key];
  const sh = new THREE.Shape(); sh.moveTo(-wid * .16, 0); sh.bezierCurveTo(-wid * .52, len * .22, -wid * .54, len * .68, -wid * .3, len * .92); sh.quadraticCurveTo(0, len * 1.05, wid * .3, len * .92); sh.bezierCurveTo(wid * .54, len * .68, wid * .52, len * .22, wid * .16, 0); sh.lineTo(-wid * .16, 0);
  const geo = new THREE.ShapeGeometry(sh, 18); const p = geo.attributes.position, uv = geo.attributes.uv;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), u = x / wid, v = y / len; p.setZ(i, cup * wid * u * u * .9 + len * .1 * v * v); uv.setXY(i, u + .5, v); }
  geo.computeVertexNormals(); return (featherCache[key] = geo); }
function featherMat(color) { const key = 'fm' + color; if (featherCache[key]) return featherCache[key]; const base = col(color);
  return (featherCache[key] = new THREE.MeshPhysicalMaterial({ color: base, map: featherDetail(), side: THREE.DoubleSide, roughness: .5, sheen: .55, sheenRoughness: .35, sheenColor: base.clone().lerp(new THREE.Color(1, 1, 1), .6), envMapIntensity: .8 })); }
function feather(par, len, wid, color, cup) { const m = new THREE.Mesh(featherGeo(len, wid, cup == null ? 1 : cup), featherMat(color)); m.castShadow = true; m.receiveShadow = true; m.userData.feather = true; par.add(m); return m; }
const shade = (c, k) => '#' + new THREE.Color(c).multiplyScalar(k).getHexString();
function buildWing(rig, g) { // крыло из перьев: маховые (длинные, веером назад) + кроющие (короткие, в два ряда сверху)
  const k = rig.kind, c = rig.n.c, s = g.userData.side || 1, P = rig.P, chick = k === 'chick';
  g.children.forEach(ch => { if (ch.isMesh) ch.visible = false; });
  const W = new THREE.Group(); W.position.set(s * .015, -.01, -.01); W.rotation.y = s * Math.PI / 4; W.scale.x = s; g.add(W);
  const L = (P.armL + P.armR) * (chick ? 1.25 : 1.75), wd = L * .3;
  const prim = k === 'owl' ? shade(c.body, .78) : k === 'duck' ? shade(c.body, .92) : chick ? c.body : c.stripe;
  const np = chick ? 3 : 5;
  for (let i = 0; i < np; i++) { const f = feather(W, L * (1 - Math.abs(i - 1.5) * .06), wd, i % 2 ? shade(prim, .96) : prim, 1); f.position.set(.008 + i * L * .055, -L * .2 - i * L * .02, -.004 * i); f.rotation.z = Math.PI + .08 + i * .17; }
  const cov = c.body;
  for (let i = 0; i < 4; i++) { const f = feather(W, L * .52, wd * .95, i % 2 ? shade(cov, .97) : cov, 1.2); f.position.set(.004 + i * L * .05, -L * .06, .006 + .002 * i); f.rotation.z = Math.PI + .12 + i * .16; }
  for (let i = 0; i < 3; i++) { const f = feather(W, L * .32, wd * .85, cov, 1.3); f.position.set(.008 + i * L * .05, L * .02, .014); f.rotation.z = Math.PI + .18 + i * .18; }
  const cap = mesh(G.sph(1, 20, 14), soft(c.body), 0, W); cap.scale.set(wd * .7, wd * .75, wd * .3); cap.position.set(L * .05, -L * .02, .01);
}
function buildTailFan(rig) { const k = rig.kind, c = rig.n.c, t = rig.tail; if (!t) return; t.children.forEach(ch => { if (ch.isMesh) ch.visible = false; });
  const n = k === 'bird' ? 5 : k === 'owl' ? 5 : 3, len = k === 'bird' ? .26 : k === 'owl' ? .2 : k === 'duck' ? .14 : .1, up = k === 'duck' ? -.5 : k === 'chick' ? -.2 : .25, colr = k === 'bird' ? c.stripe : k === 'owl' ? shade(c.body, .85) : c.body;
  for (let i = 0; i < n; i++) { const sp = (i - (n - 1) / 2) / Math.max(1, n - 1); const gq = new THREE.Group(); gq.rotation.order = 'YXZ'; gq.rotation.y = sp * .9; gq.rotation.x = -Math.PI / 2 + up; gq.position.set(sp * .03, .03, -.02); t.add(gq);
    const f = feather(gq, len * (1 - Math.abs(sp) * .2), len * .38, i % 2 ? shade(colr, .94) : colr, .8); f.rotation.y = Math.PI; } }
function buildTufts(rig) { const k = rig.kind, c = rig.n.c, hr = rig.P.head;
  if (k === 'owl') { rig.head.children.forEach(e => { if (e.isGroup && e.userData.furK != null) { e.children.forEach(ch => { if (ch.isMesh) ch.visible = false; }); for (let i = 0; i < 3; i++) { const f = feather(e, hr * (.42 - i * .07), hr * .16, i ? c.body : shade(c.body, .8), 1.2); f.rotation.z = (i - 1) * .28; f.position.set((i - 1) * hr * .04, 0, -.004 * i); } } }); return; }
  for (let i = 0; i < 3; i++) { const gq = new THREE.Group(); gq.position.set(0, hr * .92, hr * .1 - i * hr * .12); gq.rotation.x = -.35 - i * .25; rig.head.add(gq); feather(gq, hr * (k === 'chick' ? .28 : .38) * (1 - i * .15), hr * .14, k === 'bird' ? c.stripe : c.body, 1.4); } }
function addBirdFeathers(rig, list, keep, under) {
  const k = rig.kind, c = rig.n.c, regOf = o => rig.tail && under(o, rig.tail) ? 'tail' : rig.legs.some(g => under(o, g)) ? 'leg' : rig.arms.some(g => under(o, g)) ? 'arm' : under(o, rig.head) ? 'head' : 'body';
  const bellyHex = new THREE.Color(c.belly).getHexString();
  for (const o of list) { const reg = regOf(o); if (reg !== 'body' && reg !== 'head') continue;
    const belly = !o.material.map && o.material.color.getHexString() === bellyHex && reg === 'body';
    if (k !== 'chick') { const dk = k === 'duck' ? 1.25 : 1; const sk = featherSkin(o.material, (reg === 'head' ? [30, 15] : belly ? [26, 13] : [24, 12]).map(x => Math.round(x * dk)), belly && k === 'owl' ? shade(c.stripe, 1) : null);
      const m = o.material.clone(); m.map = sk.map; m.bumpMap = sk.bump; m.bumpScale = k === 'duck' ? .6 : reg === 'head' ? .7 : 1.1; m.sheen = .45; m.roughness = .55; o.material = m; }
    if (k === 'chick' || (k === 'owl' && belly)) addStrands(rig, o, k === 'chick' ? .015 : .011, keep, 1, reg); // пух у цыплёнка и на грудке совы
  }
  rig.arms.forEach(g => buildWing(rig, g)); buildTailFan(rig); buildTufts(rig);
}
function addStrands(rig, o, L, keep, furK, reg) { furK = (furK || 1) * ({ tail: 1.45, leg: .7, arm: .8, body: 1.05, head: 1 })[reg || 'body'];
  const headW = new THREE.Vector3(); rig.head.getWorldPosition(headW); const hr = rig.P.head; let inHead = false; { let pp = o; while (pp) { if (pp === rig.head) inHead = true; pp = pp.parent; } }
  const fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(rig.head.getWorldQuaternion(new THREE.Quaternion())).normalize();
  const g = o.geometry, pos = g.attributes.position, nor = g.attributes.normal, uv = g.attributes.uv; if (!pos || !nor) return;
  const idx = g.index ? g.index.array : null, triN = idx ? idx.length / 3 : pos.count / 3;
  const sx = o.scale.x, sy = o.scale.y, sz = o.scale.z; const wsc = new THREE.Vector3(); o.getWorldScale(wsc); const ws = (wsc.x + wsc.y + wsc.z) / 3;
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), areas = new Float32Array(triN); let tot = 0;
  for (let i = 0; i < triN; i++) { const i0 = idx ? idx[i * 3] : i * 3, i1 = idx ? idx[i * 3 + 1] : i * 3 + 1, i2 = idx ? idx[i * 3 + 2] : i * 3 + 2;
    a.fromBufferAttribute(pos, i0).multiply(wsc); b.fromBufferAttribute(pos, i1).multiply(wsc); c.fromBufferAttribute(pos, i2).multiply(wsc); const ar = b.sub(a).cross(c.sub(a)).length() / 2; tot += ar; areas[i] = tot; }
  const DENS = rig.kind === 'chick' ? 95000 : 64000; let count = Math.min(100000, Math.round(tot * DENS)); if (count < 50) return;
  const SEG = 4, r = rng(global.MK.hash32(rig.spec.name + o.uuid.slice(0, 4)) || 7);
  const aTilt = new Float32Array(count * SEG * 2 * 3); const aRoot = new Float32Array(count * SEG * 2 * 3), aNorm = new Float32Array(count * SEG * 2 * 3), aUv = new Float32Array(count * SEG * 2 * 2), aRnd = new Float32Array(count * SEG * 2 * 4), aT = new Float32Array(count * SEG * 2);
  const pa = new THREE.Vector3(), pb = new THREE.Vector3(), pc = new THREE.Vector3(), na = new THREE.Vector3(), nb = new THREE.Vector3(), nc = new THREE.Vector3(), P = new THREE.Vector3(), N = new THREE.Vector3(), Wp = new THREE.Vector3();
  let v = 0, made = 0;
  for (let s = 0; s < count; s++) {
    const x = r() * tot; let lo = 0, hi = triN - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (areas[m] < x) lo = m + 1; else hi = m; }
    const i0 = idx ? idx[lo * 3] : lo * 3, i1 = idx ? idx[lo * 3 + 1] : lo * 3 + 1, i2 = idx ? idx[lo * 3 + 2] : lo * 3 + 2;
    let u1 = r(), u2 = r(); if (u1 + u2 > 1) { u1 = 1 - u1; u2 = 1 - u2; } const w0 = 1 - u1 - u2;
    pa.fromBufferAttribute(pos, i0); pb.fromBufferAttribute(pos, i1); pc.fromBufferAttribute(pos, i2); P.set(0, 0, 0).addScaledVector(pa, w0).addScaledVector(pb, u1).addScaledVector(pc, u2);
    na.fromBufferAttribute(nor, i0); nb.fromBufferAttribute(nor, i1); nc.fromBufferAttribute(nor, i2); N.set(0, 0, 0).addScaledVector(na, w0).addScaledVector(nb, u1).addScaledVector(nc, u2).normalize();
    Wp.copy(P).applyMatrix4(o.matrixWorld); let skip = false, near = 9; for (const [kp, kr] of keep) { const d = Wp.distanceTo(kp) / kr; if (d < 1) { skip = true; break; } near = Math.min(near, d); } if (skip) continue;
    let U = 0, Vv = 0; if (uv) { U = uv.getX(i0) * w0 + uv.getX(i1) * u1 + uv.getX(i2) * u2; Vv = uv.getY(i0) * w0 + uv.getY(i1) * u1 + uv.getY(i2) * u2; }
    let faceK = 1; if (inHead) { const d = Wp.clone().sub(headW); const f = d.dot(fwd) / Math.max(1e-3, d.length()); // f=1 — самый перед мордочки
      faceK = f > .15 ? .3 + .7 * (1 - Math.min(1, (f - .15) / .55)) : 1; faceK = Math.max(.28, faceK); if (d.y < -hr * .15 && f > .3) faceK = Math.min(faceK, .32); }
    if (faceK < .4 && r() < .35) continue; // на мордочке шерсть ещё и реже
    let regK = 1; if (reg === 'body') { const d = Wp.clone().sub(headW); const f = d.dot(fwd); if (f > .05) regK *= 1 + Math.min(.35, f * 1.8); if (N.y > .5) regK *= 1.25; /* грудка и воротник — пышнее */ }
    if (reg === 'tail') { const tipK = .8 + Math.max(0, -P.z) * 2; regK *= Math.min(1.5, tipK); }
    const lenK = (.9 + r() * .15) * (near < 1.8 ? .45 + .55 * (near - 1) / .8 : 1) * faceK * furK * regK, ty = (r() - .5), tz = (r() - .5), vr = r();
    // пряди: волоски в одной ячейке тянутся к общему центру
    const CELL = .035 / ws, cx = Math.floor(P.x / CELL), cy = Math.floor(P.y / CELL), cz = Math.floor(P.z / CELL);
    const h = global.MK.hash32(cx + ',' + cy + ',' + cz + o.uuid.slice(0, 2)) / 4294967296, h2 = global.MK.hash32(cz + ';' + cy + ';' + cx) / 4294967296;
    const ctr = new THREE.Vector3((cx + .5) * CELL, (cy + .5) * CELL, (cz + .5) * CELL); const pull = ctr.sub(P); pull.addScaledVector(N, -pull.dot(N)); if (pull.lengthSq() > 1e-9) pull.normalize();
    const tan1 = new THREE.Vector3().crossVectors(N, Math.abs(N.y) < .95 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0)).normalize(), tan2 = new THREE.Vector3().crossVectors(N, tan1);
    const tilt = pull.multiplyScalar(.07 * (.5 + h)).addScaledVector(tan1, (h - .5) * .14 + ty * .08).addScaledVector(tan2, (h2 - .5) * .14 + tz * .08);
    P.addScaledVector(N, .002 / ws);
    for (let k = 0; k < SEG; k++) for (const tt of [k / SEG, (k + 1) / SEG]) {
      aRoot.set([P.x, P.y, P.z], v * 3); aNorm.set([N.x, N.y, N.z], v * 3); aTilt.set([tilt.x, tilt.y, tilt.z], v * 3); aUv.set([U, Vv], v * 2); aRnd.set([lenK, ty, tz, vr], v * 4); aT[v] = tt; v++; }
    made++;
  }
  if (!made) return;
  const geo = new THREE.BufferGeometry(); const n = v;
  geo.setAttribute('position', new THREE.BufferAttribute(aRoot.slice(0, n * 3), 3)); geo.setAttribute('aRoot', new THREE.BufferAttribute(aRoot.slice(0, n * 3), 3)); geo.setAttribute('aNorm', new THREE.BufferAttribute(aNorm.slice(0, n * 3), 3));
  geo.setAttribute('aUv', new THREE.BufferAttribute(aUv.slice(0, n * 2), 2)); geo.setAttribute('aRnd', new THREE.BufferAttribute(aRnd.slice(0, n * 4), 4)); geo.setAttribute('aT', new THREE.BufferAttribute(aT.slice(0, n), 1)); geo.setAttribute('aTilt', new THREE.BufferAttribute(aTilt.slice(0, n * 3), 3));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 10);
  const m = strandMat(o.material); m.uniforms.uLen.value = L / ws; const ls = new THREE.LineSegments(geo, m); ls.frustumCulled = false; ls.userData.strands = true; ls.castShadow = false; o.add(ls);
  // базовая поверхность чуть темнее — это «подшёрсток» у корней
  o.material = o.material.clone(); o.material.color.multiplyScalar(rig.kind === 'chick' ? 1 : .9); o.material.sheen = 0; if (rig.kind === 'chick') m.uniforms.uColor.value.multiplyScalar(.93);
}
function buildRig0(spec) {
  const n = global.MK.normChar(spec), c = n.c, k = n.kind, human = n.human, adult = n.adult, O = spec.outfit || {};
  const R0 = new THREE.Group(); // корень: позиция
  const yaw = new THREE.Group(); R0.add(yaw);
  const rollG = new THREE.Group(); yaw.add(rollG);
  const pose = new THREE.Group(); rollG.add(pose);
  const rig = { root: R0, yaw, rollG, pose, kind: k, human, eyes: [], lids: [], brows: [], arms: [], legs: [], spec, n };
  const P = human ? (adult ? { hip: .6, legL: .5, bodyY: .92, head: .2, headY: 1.33, shY: 1.12, shX: .24, armL: .44, legX: .1, legR: .075, armR: .06, torsoR: .2, torsoL: .38 }
                           : { hip: .38, legL: .3, bodyY: .62, head: .26, headY: 1.02, shY: .8, shX: .21, armL: .3, legX: .09, legR: .07, armR: .055, torsoR: .17, torsoL: .22 })
                   : (adult ? { hip: .26, legL: .17, bodyY: .54, head: .31, headY: 1.08, shY: .74, shX: .3, armL: .2, legX: .14, legR: .085, armR: .068, bx: .34, by: .42, bz: .3 }
                            : { hip: .24, legL: .13, bodyY: .45, head: .34, headY: .98, shY: .64, shX: .27, armL: .16, legX: .13, legR: .075, armR: .06, bx: .32, by: .36, bz: .29 });
  rig.P = P; const bodyC = human ? c.skin : c.body, pawC = human ? c.skin : (n.pattern.includes('socks') ? c.belly : c.body);
  const furMap = !human && n.pattern.includes('stripes') ? stripeTex(c.body, c.stripe, 7, 30, 92) : !human && n.pattern.includes('spots') ? spotTex(c.body, c.stripe, n.seed) : null;
  const headMap = !human && n.pattern.includes('stripes') ? stripeTex(c.body, c.stripe, 10, 4, 46) : null;
  const legC = O.overalls || O.pants || (human ? c.pants : null);
  // ноги
  for (const s of [-1, 1]) {
    const g = new THREE.Group(); g.position.set(s * P.legX, P.hip, 0); pose.add(g);
    const leg = mesh(G.cap(P.legR, P.legL), toon(legC || (human ? c.pants : c.body)), .06, g); leg.position.y = -P.legL / 2 - P.legR * .3;
    const foot = mesh(G.sph(P.legR * 1.35, 20, 14), toon(human ? (O.shoes || c.shoes) : (O.shoes || pawC)), .06, g); foot.position.set(0, -P.legL - P.legR * .6, P.legR * .5); foot.scale.set(1, .75, 1.3);
    rig.legs.push(g);
  }
  // тело
  const body = new THREE.Group(); body.position.y = P.bodyY; pose.add(body); rig.body = body;
  if (human) {
    const shirt = O.shirt || c.shirt; const torso = mesh(G.cap(P.torsoR, P.torsoL), toon(O.overalls && !O.shirt ? shirt : shirt), .05, body);
    if (O.stripe) { torso.material = toon(null, stripeTex(shirt, O.stripe, 1, 0, 0)); }
    if (O.skirt) { const sk = mesh(G.cyl(P.torsoR * 1.05, P.torsoR * 1.9, P.torsoL * .55, 28, true), toon(O.skirt), .03, body); sk.position.y = -P.torsoL * .55; sk.material.side = THREE.DoubleSide; }
    if (O.pants || O.overalls) { const pt = mesh(G.sph(1, 28, 16, 0), toon(O.overalls || O.pants), 0, body); pt.scale.set(P.torsoR * 1.04, P.torsoL * .45, P.torsoR * 1.04); pt.position.y = -P.torsoL * .38; }
  } else {
    const b = mesh(G.sph(1, 40, 30), furMap ? toon(null, furMap) : toon(c.body), .04, body); b.scale.set(P.bx, P.by, P.bz);
    if (!n.pattern.includes('nobelly')) { const be = mesh(G.sph(1, 28, 20), toon(c.belly), 0, body); be.scale.set(P.bx * .62, P.by * .7, P.bz * .45); be.position.set(0, -.03, P.bz * .62); }
    const shell = (th0, th1, color, sc) => { const g = new THREE.SphereGeometry(1, 36, 20, 0, Math.PI * 2, th0, th1 - th0); const m = mesh(g, toon(color), .02, body); m.scale.set(P.bx * sc, P.by * sc, P.bz * sc); m.material = toon(color); return m; };
    if (O.shirt) shell(0, Math.PI * .62, O.shirt, 1.035);
    if (O.pants || O.overalls) shell(Math.PI * .5, Math.PI, O.overalls || O.pants, 1.04);
    if (O.skirt) { const sk = mesh(new THREE.CylinderGeometry(P.bx * .95, P.bx * 1.45, P.by * .7, 28, 1, true), toon(O.skirt), .03, body); sk.position.y = -P.by * .45; sk.material = sk.material.clone(); sk.material.side = THREE.DoubleSide; }
  }
  // одежда-детали (общие)
  const top = human ? P.torsoL * .5 + P.torsoR * .4 : P.by * .7, frontZ = human ? P.torsoR * .98 : P.bz * .98, wB = human ? P.torsoR : P.bx;
  if (O.overalls) { const bib = mesh(G.box(wB * .9, (human ? P.torsoL : P.by) * .55, .03), toon(O.overalls), .05, body); bib.position.set(0, -.02, frontZ + .005);
    for (const s of [-1, 1]) { const st = mesh(G.box(.035, top * 1.1, .03), toon(O.overalls), 0, body); st.position.set(s * wB * .4, top * .55, frontZ * .82); st.rotation.x = -.35; const bt = new THREE.Mesh(G.sph(.022, 10, 8), toon('#ffd23f')); bt.position.set(s * wB * .35, .1, frontZ + .025); body.add(bt); }
    const pk = mesh(G.box(wB * .35, .06, .02), toon(new THREE.Color(O.overalls).multiplyScalar(.8).getStyle()), 0, body); pk.position.set(0, .0, frontZ + .025); }
  if (O.apron) { const a = mesh(G.box(wB * 1.1, (human ? P.torsoL : P.by) * 1.1, .02), toon(O.apron), .04, body); a.position.set(0, -.08, frontZ + .01); a.rotation.x = .12; }
  if (O.vest) for (const s of [-1, 1]) { const v = mesh(G.box(wB * .55, (human ? P.torsoL : P.by) * .9, .03), toon(O.vest), .04, body); v.position.set(s * wB * .48, .02, frontZ * .9); v.rotation.y = s * .45; }
  if (O.tie) { const t = mesh(G.box(.05, .2, .02), toon(O.tie), .06, body); t.position.set(0, top * .45, frontZ + .02); }
  if (O.bowtie) for (const s of [-1, 1]) { const b = mesh(G.cone(.04, .08, 12), toon(O.bowtie), .06, body); b.rotation.z = s * Math.PI / 2; b.position.set(s * .045, top * .85, frontZ * .85); }
  if (O.cape) { const cp = mesh(G.cyl(wB * .9, wB * 1.7, (human ? P.torsoL + .5 : .75), 24, true), toon(O.cape), 0, body); cp.material.side = THREE.DoubleSide; cp.geometry = new THREE.CylinderGeometry(wB * .9, wB * 1.7, human ? P.torsoL + .5 : .75, 24, 1, true, Math.PI * .6, Math.PI * .8); cp.position.set(0, -.08, -.03); rig.cape = cp; }
  if (O.backpack) { const bp = mesh(G.box(wB * 1.0, .32, .16), toon(O.backpack), .05, body); bp.position.set(0, .05, -(human ? P.torsoR : P.bz) - .06); }
  if (O.pajamas) for (let i = 0; i < 8; i++) { const d = new THREE.Mesh(G.sph(.018, 8, 6), toon('#ffffff')); const a = i * .8; d.position.set(Math.sin(a) * wB, (i % 4) * .08 - .12, Math.cos(a) * wB * .98); body.add(d); }
  // руки
  for (const s of [-1, 1]) {
    const g = new THREE.Group(); g.position.set(s * P.shX, P.shY, 0); pose.add(g);
    const sleeveC = human ? (O.shirt || c.shirt) : (O.shirt || c.body);
    const arm = mesh(G.cap(P.armR, P.armL), toon(sleeveC), .06, g); arm.position.y = -P.armL / 2 - P.armR * .3;
    const hand = mesh(G.sph(P.armR * 1.25, 18, 12), toon(pawC), .06, g); hand.position.y = -P.armL - P.armR * .8;
    const anchor = new THREE.Object3D(); anchor.position.set(0, -P.armL - P.armR * 1.6, .06); g.add(anchor);
    g.userData.side = s; rig.arms.push(g); if (s > 0) rig.hand = anchor;
  }
  // голова
  const head = new THREE.Group(); head.position.y = P.headY; pose.add(head); rig.head = head;
  const hr = P.head;
  if (human) { mesh(G.sph(hr, 36, 28), toon(c.skin), .035, head);
    for (const s of [-1, 1]) { const e = mesh(G.sph(hr * .18, 12, 10), toon(c.skin), .1, head); e.position.set(s * hr * .97, -.02, 0); }
    const ns = mesh(G.sph(hr * .1, 12, 10), toon(new THREE.Color(c.skin).multiplyScalar(.9).getStyle()), 0, head); ns.position.set(0, -hr * .12, hr * .98);
    buildHair(head, hr, n);
  } else {
    const sk = mesh(G.sph(hr, 40, 30), headMap ? toon(null, headMap) : toon(c.body), .035, head); sk.scale.set(1.08, .94, 1);
    buildAnimalFace(head, hr, n, rig);
  }
  // глаза
  const frog = k === 'frog', owlE = k === 'owl';
  const eyeY = human ? hr * .08 : frog ? hr * .75 : hr * .18, eyeX = human ? hr * .36 : frog ? hr * .45 : hr * .38, eyeZ = hr * (human ? .88 : frog ? .45 : .8), eR = hr * (human ? .2 : frog ? .3 : owlE ? .3 : .25);
  for (const s of [-1, 1]) {
    const g = new THREE.Group(); g.position.set(s * eyeX, eyeY, eyeZ); head.add(g);
    const w = mesh(G.sph(eR, 24, 18), toon('#ffffff'), .08, g); w.scale.set(1, 1.2, .6);
    const ir = new THREE.Mesh(G.sph(eR * .68, 20, 14), toon(c.eyes)); ir.position.z = eR * .42; ir.scale.set(1, 1.15, .5); g.add(ir);
    const pu = new THREE.Mesh(G.sph(eR * .38, 16, 12), basic('#16100c')); pu.position.z = eR * .65; pu.scale.set(1, 1.15, .5); g.add(pu);
    const hl = new THREE.Mesh(G.sph(eR * .16, 10, 8), basic('#ffffff')); hl.position.set(-eR * .2, eR * .3, eR * .82); g.add(hl);
    if (MK3D.hq) { w.material = glossy('#fbfbf8', .25); ir.material = glossy(c.eyes, .2); pu.material = basic('#120c08'); const h2 = new THREE.Mesh(G.sph(eR * .07, 8, 6), basic('#ffffff')); h2.position.set(eR * .18, -eR * .12, eR * .84); g.add(h2);
      const cor = new THREE.Mesh(G.sph(eR * .72, 20, 14), new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: .12, roughness: 0, clearcoat: 1, transmission: 0 })); cor.position.z = eR * .46; cor.scale.set(1, 1.15, .55); g.add(cor); }
    const heart = makeHeart(eR * .7); heart.position.z = eR * .5; heart.visible = false; g.add(heart);
    const lid = new THREE.Mesh(new THREE.SphereGeometry(eR * 1.08, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), toon(bodyC)); lid.scale.set(1, 1.2, .62); g.add(lid);
    const brow = new THREE.Mesh(G.cap(eR * .13, eR * .9), basic(human ? new THREE.Color(n.hair.color || c.hair).multiplyScalar(.7).getStyle() : new THREE.Color(c.body).multiplyScalar(.55).getStyle()));
    brow.rotation.z = Math.PI / 2; brow.position.set(0, eR * 1.55, eR * .2); g.add(brow);
    rig.eyes.push({ g, ir, pu, heart, lid, brow, s, eR });
  }
  // щёки
  for (const s of [-1, 1]) { const ch = new THREE.Mesh(G.sph(hr * .13, 14, 10), new THREE.MeshBasicMaterial({ color: 0xff8fa0, transparent: true, opacity: .45 })); ch.position.set(s * hr * .62, -hr * .18, hr * .75); ch.scale.set(1, .6, .3); head.add(ch); rig.cheeks = (rig.cheeks || []).concat(ch); }
  // рот
  const mY = human ? -hr * .42 : -hr * .42, mZ = hr * (human ? .9 : .9);
  const mouth = new THREE.Group(); mouth.position.set(0, mY, mZ); head.add(mouth); rig.mouth = mouth;
  rig.smile = new THREE.Mesh(G.tor(hr * .16, hr * .025, Math.PI), basic('#3a1d14')); rig.smile.rotation.z = Math.PI; mouth.add(rig.smile);
  rig.frown = new THREE.Mesh(G.tor(hr * .12, hr * .025, Math.PI), basic('#3a1d14')); rig.frown.position.y = -hr * .1; mouth.add(rig.frown);
  rig.open = new THREE.Group(); mouth.add(rig.open);
  const om = new THREE.Mesh(G.sph(hr * .17, 20, 14), basic('#6b1f24')); om.scale.set(1, 1, .35); rig.open.add(om);
  const tg = new THREE.Mesh(G.sph(hr * .1, 14, 10), basic('#f0788a')); tg.position.set(0, -hr * .07, hr * .03); tg.scale.set(1, .6, .4); rig.open.add(tg);
  // аксессуары
  { const before = new Set(); R0.traverse(o => before.add(o)); for (const a0 of n.acc) { const a = typeof a0 === 'string' ? { type: a0 } : a0; buildAcc(a, head, body, hr, rig, human); } R0.traverse(o => { if (!before.has(o)) o.userData.noFur = true; }); }
  // особенности видов
  if (k === 'hedgehog') { const sm = toon(c.stripe); const add = (par, R, y, cnt, rows, zMax) => { for (let r = 0; r < rows; r++) for (let i = 0; i < cnt; i++) { const a = (i / cnt - .5) * Math.PI * 1.5, el = r / rows * 1.1 + .1; const sp = new THREE.Mesh(G.cone(R * .1, R * .45, 6), sm); const dir = new THREE.Vector3(Math.sin(a) * Math.cos(el), Math.sin(el) * .9 + .1, -Math.abs(Math.cos(a)) * Math.cos(el) - .2).normalize(); sp.position.copy(dir.clone().multiplyScalar(R * .95)).add(new THREE.Vector3(0, y, 0)); sp.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir); sp.castShadow = true; par.add(sp); } };
    add(body, P.bx * 1.05, 0, 9, 4); add(head, hr * 1.02, hr * .1, 9, 3); }
  if (k === 'lion') { const mm = toon(c.stripe); for (let i = 0; i < 14; i++) { const a = i / 14 * Math.PI * 2; const b = mesh(G.sph(hr * .32, 14, 10), mm, .03, head); b.position.set(Math.cos(a) * hr * 1.0, Math.sin(a) * hr * .95, -hr * .2); } }
  if (k === 'owl' || k === 'bird' || k === 'duck' || k === 'chick' || k === 'dragon') { rig.arms.forEach(g => { g.children.forEach(ch => { if (ch.isMesh) ch.scale.set(1.5, 1.15, .45); }); }); }
  if (k === 'duck' || k === 'chick' || k === 'owl' || k === 'bird') rig.legs.forEach(g => g.children.forEach((ch, i) => { if (i === 1) ch.material = toon(c.nose); }));
  if (k === 'dragon') { for (let i = 0; i < 5; i++) { const sp = mesh(G.cone(.06, .16, 4), toon(c.stripe), .06, body); sp.position.set(0, P.by * (.75 - i * .32), -P.bz * (.75 + Math.sin(i / 4 * Math.PI) * .2)); sp.rotation.x = -.6 - i * .2; }
    for (const s of [-1, 1]) { const w = new THREE.Group(); w.position.set(s * P.bx * .55, P.by * .4, -P.bz * .7); w.rotation.set(-.3, s * .6, s * .5); body.add(w); const m = mesh(G.sph(.3, 16, 10), toon(c.stripe), .03, w); m.scale.set(1.3, 1, .12); m.position.x = s * .25; rig.wings = (rig.wings || []).concat(w); } }
  if (k === 'robot') { body.children.forEach(ch => { if (ch.isMesh && ch.geometry.type === 'SphereGeometry') { ch.geometry = new THREE.BoxGeometry(2, 2, 2); ch.children.forEach(o => o.geometry = ch.geometry); } }); const pn = mesh(G.box(P.bx * .9, P.by * .6, .04), toon('#2a3442'), 0, body); pn.position.set(0, .02, P.bz + .02); for (let i = 0; i < 3; i++) { const l = new THREE.Mesh(G.sph(.025, 8, 6), basic(['#ff4d6d', '#ffd23f', '#4cc38a'][i])); l.position.set(-.08 + i * .08, .05, P.bz + .05); body.add(l); rig.leds = (rig.leds || []).concat(l); } }
  // хвост
  buildTail(pose, n, rig, P);
  // шкала
  const sc = n.size * (adult && human ? 1 : 1); R0.scale.setScalar(sc); rig.scale = sc;
  if (MK3D.hq) rig.blob = contactShadow(R0, human ? .45 : .6);
  return rig;
}
function makeHeart(r) { const sh = new THREE.Shape(); sh.moveTo(0, -r * .9); sh.bezierCurveTo(-r * 1.4, -r * .1, -r * .6, r * 1.1, 0, r * .4); sh.bezierCurveTo(r * .6, r * 1.1, r * 1.4, -r * .1, 0, -r * .9); const g = new THREE.ExtrudeGeometry(sh, { depth: r * .2, bevelEnabled: false }); return new THREE.Mesh(g, basic('#e8344e')); }
function buildHair(head, hr, n) {
  const h = n.hair || {}, cl = h.color || (n.old ? '#d9d9d9' : n.c.hair), m = toon(cl), st = h.style || 'short';
  if (st === 'bald') { if (n.old) for (const s of [-1, 1]) { const p = mesh(G.sph(hr * .3, 14, 10), m, .05, head); p.position.set(s * hr * .85, hr * .1, -hr * .1); } return; }
  const capG = new THREE.SphereGeometry(hr * 1.06, 32, 16, 0, Math.PI * 2, 0, Math.PI * .45); const cap = mesh(capG, m, .03, head); cap.rotation.x = -.25; cap.position.z = -hr * .05;
  if (st === 'long') { const b = mesh(G.sph(hr * 1.05, 24, 16), m, .03, head); b.scale.set(1, 1.3, .7); b.position.set(0, -hr * .35, -hr * .35); }
  if (st === 'pigtails') for (const s of [-1, 1]) { const p = mesh(G.sph(hr * .32, 16, 12), m, .05, head); p.position.set(s * hr * 1.1, -hr * .05, -hr * .1); p.scale.set(.9, 1.2, .9); }
  if (st === 'bun') { const b = mesh(G.sph(hr * .35, 16, 12), m, .05, head); b.position.set(0, hr * 1.05, -hr * .3); }
  if (st === 'curly') for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; const p = mesh(G.sph(hr * .28, 12, 10), m, .04, head); p.position.set(Math.cos(a) * hr * .75, hr * .65 + Math.sin(a * 3) * hr * .08, Math.sin(a) * hr * .6 - hr * .1); }
}
function buildAnimalFace(head, hr, n, rig) {
  const c = n.c, k = n.kind;
  const ears = [];
  for (const s of [-1, 1]) {
    const e = new THREE.Group(); head.add(e); ears.push(e); e.userData.furK = .35;
    if (k === 'cat' || k === 'fox') { const big = k === 'fox' ? 1.3 : 1; e.position.set(s * hr * .58, hr * .72, 0); e.rotation.z = -s * .35;
      mesh(G.cone(hr * .34 * big, hr * .7 * big, 24), toon(c.body), .05, e).position.y = hr * .22 * big;
      const i = new THREE.Mesh(G.cone(hr * .2 * big, hr * .45 * big, 20), toon(k === 'fox' ? '#2b1d16' : c.inner)); i.position.set(0, hr * .18 * big, hr * .1); e.add(i); }
    else if (k === 'bear') { e.position.set(s * hr * .7, hr * .72, 0); mesh(G.sph(hr * .28, 20, 14), toon(c.body), .05, e); const i = new THREE.Mesh(G.sph(hr * .16, 16, 12), toon(c.inner)); i.position.z = hr * .14; i.scale.z = .5; e.add(i); }
    else if (k === 'mouse') { e.position.set(s * hr * .82, hr * .62, -hr * .05); const d = mesh(G.cyl(hr * .45, hr * .45, hr * .08, 28), toon(c.body), .04, e); d.rotation.x = Math.PI / 2; const i = new THREE.Mesh(G.cyl(hr * .3, hr * .3, hr * .09, 24), toon(c.inner)); i.rotation.x = Math.PI / 2; i.position.z = hr * .01; e.add(i); }
    else if (k === 'rabbit') { e.position.set(s * hr * .3, hr * .8, -hr * .05); e.rotation.z = -s * .12; mesh(G.cap(hr * .18, hr * 1.0), toon(c.body), .05, e).position.y = hr * .55; const i = new THREE.Mesh(G.cap(hr * .09, hr * .8), toon(c.inner)); i.position.set(0, hr * .55, hr * .1); e.add(i); }
    else if (k === 'dog') { e.position.set(s * hr * .92, hr * .25, 0); e.rotation.z = s * .25; const m = mesh(G.sph(hr * .26, 18, 14), toon(c.inner), .05, e); m.scale.set(.7, 1.6, .5); m.position.y = -hr * .25; }
    else if (k === 'pig') { e.position.set(s * hr * .6, hr * .72, hr * .05); e.rotation.set(.6, 0, -s * .4); mesh(G.cone(hr * .25, hr * .4, 4), toon(c.body), .05, e); }
    else if (k === 'hedgehog' || k === 'lion' || k === 'squirrel') { e.position.set(s * hr * .62, hr * .7, hr * .1); mesh(G.sph(hr * .17, 14, 10), toon(c.body), .06, e); if (k === 'squirrel') { const tf = mesh(G.cone(hr * .14, hr * .35, 12), toon(c.inner), .06, e); tf.position.y = hr * .2; } }
    else if (k === 'wolf') { const big = 1.15; e.position.set(s * hr * .55, hr * .74, 0); e.rotation.z = -s * .3; mesh(G.cone(hr * .3 * big, hr * .62 * big, 24), toon(c.body), .05, e).position.y = hr * .2; const i = new THREE.Mesh(G.cone(hr * .17, hr * .4, 20), toon(c.inner)); i.position.set(0, hr * .16, hr * .09); e.add(i); }
    else if (k === 'owl') { e.position.set(s * hr * .55, hr * .78, 0); e.rotation.z = -s * .4; mesh(G.cone(hr * .14, hr * .38, 12), toon(c.inner), .06, e).position.y = hr * .12; }
    else if (k === 'elephant') { e.position.set(s * hr * .95, hr * .05, -hr * .1); e.rotation.y = s * .4; const d = mesh(G.sph(hr * .62, 24, 16), toon(c.body), .03, e); d.scale.set(.25, 1, 1.05); const i = new THREE.Mesh(G.sph(hr * .48, 20, 14), toon(c.inner)); i.scale.set(.2, .9, .9); i.position.x = s * .02; e.add(i); }
    else if (k === 'cow') { e.position.set(s * hr * .92, hr * .35, 0); e.rotation.z = s * .5; const m = mesh(G.sph(hr * .2, 16, 12), toon(c.body), .05, e); m.scale.set(1.6, .6, .7); const h2 = mesh(G.cone(hr * .08, hr * .3, 12), toon('#f2eadf'), .08, head); h2.position.set(s * hr * .38, hr * .95, 0); h2.rotation.z = -s * .4; }
    else if (k === 'dragon') { const h2 = mesh(G.cone(hr * .1, hr * .45, 12), toon(c.stripe), .07, head); h2.position.set(s * hr * .4, hr * .95, -hr * .1); h2.rotation.set(-.4, 0, -s * .25); e.position.set(s * hr * .85, hr * .3, 0); const f = mesh(G.cone(hr * .14, hr * .3, 4), toon(c.body), .06, e); f.rotation.z = -s * Math.PI / 2; }
    else if (k === 'robot') { if (s > 0) { const an = mesh(G.cyl(.015, .015, hr * .5, 6), toon('#6a7a8a'), .08, head); an.position.y = hr * 1.15; const b = mesh(G.sph(hr * .1, 12, 10), toon(c.inner), .08, head); b.position.y = hr * 1.42; rig.antenna = b; } e.position.set(s * hr * 1.0, 0, 0); const d = mesh(G.cyl(hr * .2, hr * .2, hr * .15, 16), toon('#6a7a8a'), .05, e); d.rotation.z = Math.PI / 2; }
  }
  rig.ears = ears;
  // морда
  const nose = (cc, r, y, z) => { const m = mesh(G.sph(r, 16, 12), toon(cc), .1, head); m.position.set(0, y, z); m.scale.set(1.3, .9, .8); return m; };
  if (k === 'cat' || k === 'rabbit' || k === 'mouse') { for (const s of [-1, 1]) { const m = mesh(G.sph(hr * .32, 24, 16), toon(c.belly), 0, head); m.position.set(s * hr * .23, -hr * .3, hr * .85); m.scale.set(1, .8, .7); } nose(c.nose, hr * .1, -hr * .12, hr * 1.0); }
  if (k === 'fox') { const sn = mesh(G.cone(hr * .38, hr * .55, 24), toon(c.belly), .04, head); sn.rotation.x = Math.PI / 2; sn.position.set(0, -hr * .25, hr * 1.0); nose(c.nose, hr * .1, -hr * .25, hr * 1.27); }
  if (k === 'dog' || k === 'bear') { const sn = mesh(G.sph(hr * .42, 24, 16), toon(c.belly), .04, head); sn.position.set(0, -hr * .3, hr * .8); sn.scale.set(1, .72, .8); nose(c.nose, hr * .14, -hr * .17, hr * 1.12); }
  if (k === 'pig') { const sn = mesh(G.cyl(hr * .3, hr * .32, hr * .25, 24), toon(c.nose), .05, head); sn.rotation.x = Math.PI / 2; sn.position.set(0, -hr * .22, hr * 1.02); for (const s of [-1, 1]) { const ns = new THREE.Mesh(G.sph(hr * .07, 10, 8), basic('#7a3040')); ns.position.set(s * hr * .11, -hr * .22, hr * 1.15); ns.scale.z = .4; head.add(ns); } }
  if (k === 'hedgehog') { const sn = mesh(G.cone(hr * .3, hr * .55, 20), toon(c.belly), .04, head); sn.rotation.x = Math.PI / 2; sn.position.set(0, -hr * .25, hr * .95); nose(c.nose, hr * .1, -hr * .25, hr * 1.22); }
  if (k === 'wolf') { const sn = mesh(G.cone(hr * .36, hr * .55, 24), toon(c.belly), .04, head); sn.rotation.x = Math.PI / 2; sn.position.set(0, -hr * .28, hr * 1.0); nose(c.nose, hr * .11, -hr * .27, hr * 1.27); }
  if (k === 'lion' || k === 'squirrel') { const sn = mesh(G.sph(hr * .38, 24, 16), toon(c.belly), .04, head); sn.position.set(0, -hr * .3, hr * .78); sn.scale.set(1, .7, .7); nose(c.nose, hr * .1, -hr * .14, hr * 1.04); }
  if (k === 'cow') { const sn = mesh(G.sph(hr * .48, 24, 16), toon(c.nose), .04, head); sn.position.set(0, -hr * .35, hr * .78); sn.scale.set(1.1, .7, .7); for (const s of [-1, 1]) { const ns = new THREE.Mesh(G.sph(hr * .06, 10, 8), basic('#7a3040')); ns.position.set(s * hr * .15, -hr * .3, hr * 1.1); head.add(ns); } }
  if (k === 'owl' || k === 'bird' || k === 'chick') { const b = mesh(G.cone(hr * .14, hr * .32, 12), toon(c.nose), .06, head); b.rotation.x = k === 'owl' ? Math.PI * .85 : Math.PI / 2; b.position.set(0, -hr * .12, hr * 1.02); }
  if (k === 'duck') { const b = mesh(G.sph(hr * .32, 20, 12), toon(c.nose), .05, head); b.scale.set(1.1, .32, 1.1); b.position.set(0, -hr * .2, hr * .95); }
  if (k === 'frog') { rig.wideMouth = true; for (const s of [-1, 1]) { const n2 = new THREE.Mesh(G.sph(hr * .04, 8, 6), basic('#2f6a20')); n2.position.set(s * hr * .1, -hr * .05, hr * .97); head.add(n2); } }
  if (k === 'elephant') { const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -hr * .25, hr * .25), new THREE.Vector3(0, -hr * .65, hr * .35), new THREE.Vector3(0, -hr * .85, hr * .55)]; const tr = mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 20, hr * .14, 12), toon(c.body), .04, head); tr.position.set(0, -hr * .15, hr * .78); rig.trunk = tr; }
  if (k === 'dragon') { const sn = mesh(G.sph(hr * .45, 24, 16), toon(c.body), .04, head); sn.position.set(0, -hr * .28, hr * .72); sn.scale.set(1, .7, .9); for (const s of [-1, 1]) { const ns = new THREE.Mesh(G.sph(hr * .06, 10, 8), basic('#1f4a18')); ns.position.set(s * hr * .14, -hr * .2, hr * 1.1); head.add(ns); } }
  if (k === 'robot') { const vis = mesh(G.box(hr * 1.4, hr * .55, .05), toon('#2a3442'), 0, head); vis.position.set(0, hr * .12, hr * .93); }
  if (k === 'cat' || k === 'mouse' || k === 'rabbit') for (const s of [-1, 1]) for (let i = 0; i < 3; i++) { const w = new THREE.Mesh(G.cyl(.004, .004, hr * .75, 4), basic('#553a2a')); w.rotation.z = Math.PI / 2 + s * (i - 1) * .15; w.position.set(s * hr * .6, -hr * .25 - i * hr * .1, hr * .88); head.add(w); }
  if (n.pattern.includes('mask')) for (const s of [-1, 1]) { const m = new THREE.Mesh(G.sph(hr * .32, 16, 12), toon(c.stripe)); m.position.set(s * hr * .38, hr * .15, hr * .68); m.scale.set(1.2, .8, .4); head.add(m); }
  if (n.pattern.includes('patch')) { const m = new THREE.Mesh(G.sph(hr * .34, 16, 12), toon(c.stripe)); m.position.set(hr * .4, hr * .15, hr * .66); m.scale.set(1.1, 1, .4); head.add(m); }
}
function buildTail(pose, n, rig, P) {
  const c = n.c, k = n.kind; if (n.human) return;
  const t = new THREE.Group(); t.position.set(0, P.bodyY - .12, -P.bz * .85); pose.add(t); rig.tail = t;
  if (k === 'cat' || k === 'mouse') { const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), new THREE.Vector3(.08, .02, -.25), new THREE.Vector3(.2, .3, -.32), new THREE.Vector3(.12, .58, -.28)]);
    const map = k === 'cat' && n.pattern.includes('stripes') ? stripeTex(c.body, c.stripe, 6, 0, 128) : null;
    mesh(new THREE.TubeGeometry(curve, 30, k === 'cat' ? .052 : .02, 12), map ? toon(null, map) : toon(k === 'mouse' ? c.inner : c.body), .05, t);
    if (k === 'cat') { const tip = mesh(G.sph(.058, 14, 10), toon(n.pattern.includes('tailtip') ? c.belly : c.body), .05, t); tip.position.copy(curve.getPoint(1)); } }
  if (k === 'wolf' || k === 'squirrel') { const sq = k === 'squirrel'; const b = mesh(G.sph(sq ? .26 : .2, 24, 16), toon(c.body), .03, t); b.scale.set(.75, .75, sq ? 2.1 : 1.7); b.position.set(.05, sq ? .35 : .15, sq ? -.2 : -.28); b.rotation.x = sq ? 1.15 : .6; if (sq) { const cu = mesh(G.sph(.2, 20, 14), toon(c.body), .03, t); cu.position.set(.05, .78, -.12); } }
  else if (k === 'fox') { const b = mesh(G.sph(.2, 24, 16), toon(c.body), .03, t); b.scale.set(.75, .75, 1.7); b.position.set(.05, .18, -.28); b.rotation.x = .7; const tip = mesh(G.sph(.13, 18, 12), toon(c.belly), .03, t); tip.position.set(.07, .43, -.52); }
  else if (k === 'dog') { const m = mesh(G.cap(.045, .2), toon(c.body), .06, t); m.rotation.x = -.6; m.position.set(0, .1, -.08); }
  else if (k === 'bear') { mesh(G.sph(.07, 14, 10), toon(c.body), .06, t); }
  else if (k === 'rabbit') { mesh(G.sph(.1, 16, 12), toon('#ffffff'), .05, t); }
  else if (k === 'fox' || k === 'wolf' || k === 'squirrel') {}
  else if (k === 'lion' || k === 'cow') { const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, -.1, -.2), new THREE.Vector3(.05, -.05, -.4)]); mesh(new THREE.TubeGeometry(curve, 16, .025, 8), toon(c.body), .1, t); const tf = mesh(G.sph(.07, 12, 10), toon(k === 'lion' ? c.stripe : '#2a2a2a'), .06, t); tf.position.set(.05, -.05, -.42); }
  else if (k === 'elephant') { const m = mesh(G.cap(.02, .2), toon(c.body), .1, t); m.rotation.x = .5; m.position.set(0, -.08, -.08); }
  else if (k === 'dragon') { const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), new THREE.Vector3(.1, -.15, -.3), new THREE.Vector3(.3, -.25, -.55), new THREE.Vector3(.55, -.2, -.7)]); mesh(new THREE.TubeGeometry(curve, 24, .07, 12), toon(c.body), .05, t); const sp = mesh(G.cone(.08, .18, 4), toon(c.stripe), .06, t); sp.position.set(.6, -.2, -.72); sp.rotation.z = -Math.PI / 2; }
  else if (k === 'owl' || k === 'bird' || k === 'duck' || k === 'chick') { const f = mesh(G.cone(.09, .2, 4), toon(k === 'duck' || k === 'chick' ? c.body : c.inner), .06, t); f.rotation.x = -2.2; f.position.set(0, .02, -.05); }
  else if (k === 'pig') { const pts = []; for (let i = 0; i < 30; i++) { const a = i / 29 * Math.PI * 4; pts.push(new THREE.Vector3(Math.cos(a) * .05, i * .004, -Math.sin(a) * .05 - i * .006)); } mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, .015, 8), toon(c.body), .1, t); }
}
function buildAcc(a, head, body, hr, rig, human) {
  const t = a.type, cl = a.color || ({ scarf: '#3d8fe0', bow: '#e8344e', hat: '#e8344e', crown: '#ffd23f', glasses: '#2b1d16', flower: '#ff7ab8', collar: '#e8344e' })[t];
  if (t === 'scarf') { const s = mesh(G.tor(human ? .19 : .22, .055, 0), toon(cl), .06, rig.pose); s.rotation.x = Math.PI / 2; s.position.y = rig.P.headY - hr * .95; const e = mesh(G.cap(.05, .18), toon(cl), .08, rig.pose); e.position.set(-.1, rig.P.headY - hr * 1.3, .2); e.rotation.z = .3; }
  if (t === 'collar') { const s = mesh(G.tor(.2, .025, 0), toon(cl), .06, rig.pose); s.rotation.x = Math.PI / 2; s.position.y = rig.P.headY - hr * .95; const b = mesh(G.sph(.04, 12, 10), toon('#ffd23f'), .08, rig.pose); b.position.set(0, rig.P.headY - hr * 1.05, .2); }
  if (t === 'hat') { const cap = mesh(new THREE.SphereGeometry(hr * 1.08, 32, 16, 0, Math.PI * 2, 0, Math.PI * .42), toon(cl), .03, head); cap.position.y = hr * .08; cap.rotation.x = -.1;
    const br = mesh(G.cyl(hr * .55, hr * .55, .025, 24), toon(new THREE.Color(cl).multiplyScalar(.8).getStyle()), .05, head); br.position.set(0, hr * .62, hr * .72); br.scale.z = 1.1; br.rotation.x = .25; }
  if (t === 'crown') { const g = new THREE.Group(); g.position.y = hr * .85; head.add(g); mesh(G.cyl(hr * .45, hr * .45, hr * .2, 20, true), toon('#ffd23f'), .05, g).material.side = THREE.DoubleSide; for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; const c = mesh(G.cone(hr * .08, hr * .22, 8), toon('#ffd23f'), .08, g); c.position.set(Math.cos(a) * hr * .45, hr * .18, Math.sin(a) * hr * .45); } }
  if (t === 'glasses') { for (const s of [-1, 1]) { const r = mesh(G.tor(hr * .22, hr * .025, 0), basic(cl), 0, head); r.position.set(s * hr * .36, hr * .12, hr * .98); } const b = new THREE.Mesh(G.cyl(hr * .02, hr * .02, hr * .25, 6), basic(cl)); b.rotation.z = Math.PI / 2; b.position.set(0, hr * .14, hr * 1.0); head.add(b); }
  if (t === 'bow') { const g = new THREE.Group(); g.position.set(hr * .55, hr * .78, hr * .2); g.rotation.z = -.3; head.add(g); for (const s of [-1, 1]) { const c = mesh(G.cone(hr * .16, hr * .3, 4), toon(cl), .06, g); c.rotation.z = s * Math.PI / 2; c.position.x = s * hr * .14; } mesh(G.sph(hr * .07, 12, 10), toon(cl), .08, g); }
  if (t === 'flower') { const g = new THREE.Group(); g.position.set(-hr * .6, hr * .7, hr * .3); head.add(g); for (let i = 0; i < 5; i++) { const a = i * 1.256; const p = mesh(G.sph(hr * .09, 10, 8), toon(cl), .08, g); p.position.set(Math.cos(a) * hr * .12, Math.sin(a) * hr * .12, 0); } const c = new THREE.Mesh(G.sph(hr * .07, 10, 8), toon('#ffd23f')); g.add(c); }
}
function rigFor(lc) { const key = lc.code || global.MK.canon(lc.spec); let r = rigCache[key]; if (!r) { r = buildRig(lc.spec); rigCache[key] = r; } return r; }

// ---------- поза по состоянию ----------
function applyPose(rig, st, T) {
  const P = rig.P, act = st.act || {}, an = act.n, ap = act.p || 0, at = act.t || 0, wk = st.walk || {}, emo = st.emo || 'neutral';
  const sd = (rig.n.seed % 13) / 13;
  let lift = 0, bob = Math.sin(T * 2.2 + sd * 6) * .008, pitch = 0, lie = 0, rollA = 0, sq = 1, low = 0, hipYaw = 0, sideTilt = 0;
  const arm = [{ x: 0, z: .35 + Math.sin(T * 1.7 + sd) * .04 }, { x: 0, z: .35 + Math.sin(T * 1.7 + 2 + sd) * .04 }]; // [левая, правая]
  const leg = [0, 0]; const head = { x: 0, y: 0, z: Math.sin(T * 1.3 + sd * 5) * .04 };
  if (wk.on) { const ph = wk.ph, amp = wk.run ? .9 : .6; leg[0] = Math.sin(ph) * amp; leg[1] = Math.sin(ph + Math.PI) * amp; arm[0].x = -Math.sin(ph + Math.PI) * amp * .8; arm[1].x = -Math.sin(ph) * amp * .8; bob = Math.abs(Math.sin(ph)) * (wk.run ? .07 : .045); pitch = wk.run ? .18 : .05;
    if (wk.style === 'crawl') { pitch = .95; low = .12; arm[0].x = -1.6 + Math.sin(ph) * .4; arm[1].x = -1.6 + Math.sin(ph + Math.PI) * .4; arm[0].z = arm[1].z = .15; head.x = -.9; }
    if (wk.style === 'sneak') { pitch = .35; low = .1; bob *= .4; arm[0].x = arm[1].x = -.7; arm[0].z = arm[1].z = .6; } }
  const lsel = st.face < 0 ? 0 : 1; // «передняя» рука — правая (у развёрнутого героя тоже)
  const R_ = arm[1], L_ = arm[0];
  switch (an) {
    case 'jump': { lift = Math.sin(ap * Math.PI) * .75; const s = ap < .14 ? Math.sin(ap / .14 * Math.PI) : ap > .86 ? Math.sin((ap - .86) / .14 * Math.PI) : 0; sq = 1 - s * .15; L_.z = R_.z = .35 + Math.sin(ap * Math.PI) * 2.2; leg[0] = leg[1] = -Math.sin(ap * Math.PI) * .5; break; }
    case 'wave': R_.z = 2.6 + Math.sin(at * 11) * .35; R_.x = -.2; head.z = .12; break;
    case 'point': R_.x = -1.55; R_.z = .15; break;
    case 'think': R_.x = -2.3; R_.z = -.55; head.z = .15; head.x = -.1; break;
    case 'clap': { const k = Math.max(0, Math.sin(at * 14)); L_.x = R_.x = -1.3; L_.z = R_.z = -.15 + k * .4; break; }
    case 'laugh': bob = Math.abs(Math.sin(at * 16)) * .04; L_.x = R_.x = -.7; L_.z = R_.z = -.25; head.x = -.25; sideTilt = Math.sin(at * 8) * .06; break;
    case 'scared': L_.x = R_.x = -2.3; L_.z = R_.z = -.35; low = .08; break;
    case 'cry': L_.x = R_.x = -2.6; L_.z = R_.z = -.45; head.x = .2; break;
    case 'dance': { hipYaw = Math.sin(at * 3.5) * .35; bob = Math.abs(Math.sin(at * 7)) * .06; const up = Math.sin(at * 3.5) > 0; L_.z = up ? 2.6 : .9; R_.z = up ? .9 : 2.6; leg[0] = Math.max(0, Math.sin(at * 7)) * -.5; leg[1] = Math.max(0, Math.sin(at * 7 + Math.PI)) * -.5; head.z = Math.sin(at * 3.5) * .15; break; }
    case 'spin': hipYaw = ap * Math.PI * 2; L_.z = R_.z = 1.4; break;
    case 'nod': head.x = Math.max(0, Math.sin(at * 9)) * .35; break;
    case 'shake': head.y = Math.sin(at * 13) * .4; break;
    case 'bow': pitch = Math.sin(clamp(ap, 0, 1) * Math.PI) * .7; break;
    case 'hug': { const k = Math.sin(clamp(ap, 0, 1) * Math.PI); L_.x = R_.x = -1.35; L_.z = R_.z = .55 - k * .7; pitch = .12; break; }
    case 'scratch': R_.z = 2.5; R_.x = -.6 + Math.sin(at * 14) * .12; head.z = .2; break;
    case 'yawn': case 'stretch': L_.z = R_.z = 2.8 + Math.sin(at * 2) * .08; head.x = -.3; lift = .02; break;
    case 'sneeze': head.x = ap < .45 ? -.3 * ap / .45 : ap < .62 ? .45 : 0; pitch = ap > .45 && ap < .62 ? .2 : 0; break;
    case 'eat': R_.x = -2.1 + Math.max(0, Math.sin(at * 6)) * .3; R_.z = -.35; break;
    case 'stomp': { const ph = at * 9; leg[0] = Math.max(0, Math.sin(ph)) * -.9; leg[1] = Math.max(0, Math.sin(ph + Math.PI)) * -.9; bob = Math.abs(Math.sin(ph)) * .08; L_.z = R_.z = .6; break; }
    case 'sing': head.z = Math.sin(at * 3) * .15; L_.z = R_.z = 1.1 + Math.sin(at * 3) * .2; L_.x = R_.x = -.5; break;
    case 'kick': { const k = Math.sin(clamp((ap - .2) / .5, 0, 1) * Math.PI); leg[1] = -1.5 * k; pitch = -.15 * k; L_.z = .8 * k + .35; break; }
    case 'throw': if (ap < .4) { R_.z = 2.7; R_.x = .5; } else { R_.x = lerp(.5, -1.7, ease((ap - .4) / .2)); R_.z = lerp(2.7, .4, ease((ap - .4) / .2)); } break;
    case 'shout': pitch = .2; L_.z = R_.z = .8; L_.x = R_.x = .4; break;
    case 'give': R_.x = -1.3 * Math.sin(clamp(ap, 0, 1) * Math.PI) - .2; break;
    case 'somersault': lift = Math.sin(ap * Math.PI) * .55; rollA = -ap * Math.PI * 2; L_.z = R_.z = 1.2; leg[0] = leg[1] = -1.0; break;
    case 'roll': lie = ease(Math.min(ap, 1 - ap) * 8); rollA = Math.sin(at * 6) * 1.0; L_.x = R_.x = -.8; break;
  }
  if (st.prop && !['wave', 'throw', 'point', 'give', 'eat', 'hug'].includes(an)) { R_.x = -.95; R_.z = .2; }
  if (emo === 'scared') { L_.x = R_.x = -2.2; L_.z = R_.z = -.3; }
  // устойчивые позы
  const pers = st.persist, pk = ease((st.pt || 0) / .35), back = an === 'stand' ? 1 - ease(ap) : 0;
  const isP = (v) => pers === v ? pk : (an === 'stand' && st.prev === v ? back : 0);
  const fallen = Math.max(isP('fallen'), isP('lie'));
  const sit = Math.max(isP('sit'), isP('sleep'));
  const crouch = isP('crouch');
  if (fallen) lie = Math.max(lie, fallen);
  if (sit) { low = Math.max(low, (P.hip - .05) * sit); leg[0] = leg[1] = -1.45 * sit; if (pers === 'sleep') head.x = .35 * sit, head.z = .25 * sit; }
  if (crouch) { low = Math.max(low, .25 * crouch); leg[0] = leg[1] = -.8 * crouch; L_.x = R_.x = -2.6; L_.z = R_.z = -.6; pitch = .25 * crouch; }
  // применяем
  rig.legs[0].rotation.x = leg[0]; rig.legs[1].rotation.x = leg[1];
  rig.arms.forEach((g, i) => { const a = arm[i], s = g.userData.side; g.rotation.set(a.x, 0, s * a.z); });
  rig.head.rotation.set(head.x, head.y, head.z);
  rig.pose.rotation.set(pitch, hipYaw, sideTilt + lie * Math.PI / 2);
  const hgt = rig.P.headY + rig.P.head;
  rig.pose.position.set(lie * hgt * .45, lift + bob - low + (sq < 1 ? 0 : 0), 0);
  rig.pose.scale.set(1 / Math.sqrt(sq), sq, 1 / Math.sqrt(sq));
  // перекат/кувырок — вокруг центра тела
  if (rollA) { const cy = lie ? .22 : hgt * .5; rig.rollG.position.set(0, cy, 0); rig.rollG.rotation.x = rollA; rig.pose.position.y += -cy + (lie ? .22 * 0 : 0); }
  else { rig.rollG.position.set(0, 0, 0); rig.rollG.rotation.x = 0; }
  if (lie) rig.pose.position.y += .16 * lie;
  if (rig.tail) rig.tail.rotation.y = Math.sin(T * (rig.kind === 'dog' && (emo === 'happy' || emo === 'laugh') ? 14 : 2.4) + sd * 4) * .3;
  if (rig.antenna) rig.antenna.material = basic(Math.sin(T * 4) > 0 ? '#ff4d6d' : '#ffd23f');
  if (rig.leds) rig.leds.forEach((l, i) => l.visible = Math.sin(T * 5 + i * 2) > -.3);
  if (rig.wings) rig.wings.forEach((w, i) => w.rotation.z = (i ? 1 : -1) * (.5 + Math.sin(T * (an === 'jump' || wk.on ? 14 : 2)) * .2));
  if (rig.trunk) rig.trunk.rotation.x = Math.sin(T * 1.6) * .15 + (an === 'laugh' || an === 'shout' ? -.6 : 0);
  if (rig.cape) rig.cape.rotation.x = -(wk.on ? .35 : .08) - Math.sin(T * 2) * .03;
  // лицо
  const talk = clamp(st.talk || 0, 0, 1);
  const bp = 3.1 + (rig.n.seed % 17) / 10, bt = (T + (rig.n.seed % 7)) % bp; let blink = bt < .14 ? Math.sin(bt / .14 * Math.PI) : 0;
  let closed = pers === 'sleep' || emo === 'laugh' || an === 'laugh' || an === 'yawn' || (an === 'sneeze' && ap > .3 && ap < .62) || (an === 'roll' && emo === 'laugh');
  let lidOpen = -0.75, browY = 0, browRot = 0, eyeS = 1, pupS = 1;
  if (emo === 'sleepy') lidOpen = .15; if (emo === 'surprised') { eyeS = 1.15; pupS = .7; browY = .5; } if (emo === 'scared') { eyeS = 1.1; pupS = .55; browRot = .35; }
  if (emo === 'angry') { lidOpen = -.25; browRot = -.45; } if (emo === 'sad' || emo === 'cry') { lidOpen = -.3; browRot = .4; }
  rig.eyes.forEach(e => {
    const cl = closed ? 1 : blink; e.g.scale.set(eyeS, eyeS * (1 - cl * .92), eyeS);
    e.lid.rotation.x = lerp(lidOpen, 1.3, cl > .85 ? 1 : 0); e.lid.rotation.z = (emo === 'angry' ? -.35 : emo === 'sad' || emo === 'cry' ? .35 : 0) * -e.s;
    e.ir.visible = e.pu.visible = emo !== 'love'; e.heart.visible = emo === 'love'; e.pu.scale.set(pupS, pupS * 1.15, .5);
    const gx = Math.abs(st.face) > .1 ? .25 : 0; e.ir.position.x = e.pu.position.x = gx * e.eR * .5;
    e.brow.position.y = e.eR * (1.55 + browY); e.brow.rotation.z = Math.PI / 2 + browRot * e.s;
  });
  let open = talk;
  if (emo === 'laugh' || an === 'laugh' || (an === 'roll' && emo === 'laugh')) open = Math.max(open, .55 + Math.sin(at * 16) * .25);
  if (an === 'yawn') open = Math.max(open, Math.sin(clamp(at / 1.6, 0, 1) * Math.PI) * 1.1);
  if (an === 'shout') open = Math.max(open, .95); if (an === 'eat') open = Math.max(open, Math.max(0, Math.sin(at * 12)) * .4); if (an === 'sing') open = Math.max(open, .4 + Math.sin(at * 9) * .3);
  if (emo === 'surprised') open = Math.max(open, .4);
  const smile = ['happy', 'love', 'laugh', 'shy'].includes(emo), sad = ['sad', 'cry', 'scared'].includes(emo);
  rig.open.visible = open > .06; rig.open.scale.set(1 + (smile ? .2 : 0), .25 + open * 1.1, 1);
  rig.smile.visible = !rig.open.visible && !sad; rig.smile.scale.setScalar((smile ? 1.15 : .75) * (rig.wideMouth ? 2.2 : 1));
  rig.frown.visible = !rig.open.visible && sad;
  rig.cheeks.forEach(c => c.material.opacity = emo === 'shy' || emo === 'love' ? .8 : .4);
}

// ---------- значки эффектов (спрайты) ----------
function glyphTex(txt, color, stroke) { const k = txt + color; if (texCache[k]) return texCache[k]; const t = canvasTex(128, 128, (g) => { g.font = '900 96px -apple-system, "DejaVu Sans", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; if (stroke) { g.lineWidth = 12; g.strokeStyle = stroke; g.strokeText(txt, 64, 70); } g.fillStyle = color; g.fillText(txt, 64, 70); }); texCache[k] = t; return t; }
function bubbleTex(txt) { const k = 'b:' + txt; if (texCache[k]) return texCache[k]; const t = canvasTex(512, 256, (g) => { g.fillStyle = '#fff'; g.strokeStyle = '#2b1d16'; g.lineWidth = 10; g.beginPath(); g.ellipse(256, 110, 240, 95, 0, 0, 7); g.fill(); g.stroke(); g.beginPath(); g.ellipse(120, 215, 24, 18, 0, 0, 7); g.fill(); g.stroke(); g.fillStyle = '#2b1d16'; g.font = '800 64px -apple-system, "DejaVu Sans", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt.slice(0, 14), 256, 112); }); texCache[k] = t; return t; }
const spritePool = []; let spriteUsed = 0;
function sprite(tex, x, y, z, s, op) { let sp = spritePool[spriteUsed]; if (!sp) { sp = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthWrite: false })); spritePool.push(sp); scene.add(sp); } spriteUsed++; sp.material.map = tex; sp.material.opacity = op == null ? 1 : op; sp.material.needsUpdate = true; sp.position.set(x, y, z); sp.scale.set(s * (tex.image.width / tex.image.height), s, 1); sp.visible = true; return sp; }
function haloTex(c) { const k = 'halo' + c; if (texCache[k]) return texCache[k]; const t = canvasTex(128, 128, (g) => { const gr = g.createRadialGradient(64, 64, 4, 64, 64, 62); gr.addColorStop(0, c); gr.addColorStop(.35, c + 'aa'); gr.addColorStop(1, c + '00'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); }); texCache[k] = t; return t; }
const themeCache = {}; let curTheme = null;
function showTheme(seg, T) {
  if (curTheme) curTheme.visible = false; const th = seg.theme; if (!th) return; const L = seg.lspec || {}; const indoor = L.type === 'room' || L.type === 'kitchen';
  const key = th + ':' + (indoor ? 'in' : 'out'); let g = themeCache[key];
  if (!g) { g = new THREE.Group(); const add = (type, x, z, sc, extra) => { const o = Object.assign({ id: 'th' + key + x + z, type }, extra || {}); const pm = propMesh(o); delete propCache[o.id + o.type + (o.color || '')]; pm.position.set(x, 0, z); pm.scale.setScalar(sc || 1); pm.visible = true; g.add(pm); return pm; };
    if (th === 'halloween') { [[-4.2, -2.6, 1.3], [-2.4, -3.2, 1], [2.6, -3, 1.2], [4.4, -2.4, 1.4], [-5.2, -.6, 1.1], [5.3, -.4, 1]].forEach(([x, z, k]) => { const j = add('jack', x, z, k); j.userData.glowing = true; });
      g.userData.bats = [0, 1, 2].map(i => { const b = add('bat', -3 + i * 3, -4, 1.4); return b; }); add('garland', 0, -3.6, 1.5, { }); g.userData.halloween = true; }
    else if (th === 'newyear') { add('tree', -3.6, -2.8, 2.2, { color: '#2f8f4e' }); add('garland', 0, -3.6, 1.5); add('gift', -2.6, -2.2, 1.6); add('gift', -4.4, -1.9, 1.3, { color: '#3d8fe0' }); add('snowman', 4, -2.8, 1.3); }
    else if (th === 'birthday') { [-4, -2.6, 2.8, 4.2].forEach((x, i) => add('balloon', x, -2.4, 1.8, { color: ['#ff4d6d', '#3d8fe0', '#ffd23f', '#5fbf4a'][i] })); add('garland', 0, -3.6, 1.5); }
    themeCache[key] = g; scene.add(g); }
  g.visible = true; curTheme = g;
  if (g.userData.bats) g.userData.bats.forEach((b, i) => { b.position.x = ((T * .6 + i * 3.3) % 12) - 6; b.position.y = Math.sin(T * 2 + i) * .3 + .6; });
  if (g.userData.halloween) g.children.forEach(c => { if (c.userData.faceMat) { c.userData.faceMat.color.set(0xffc23a); sprite(haloTex('#ffb347'), c.position.x, c.position.y + .15 * c.scale.x, c.position.z + .05, .8 * c.scale.x * (1 + Math.sin(T * 4 + c.position.x) * .05), .7); } });
}
function fxFor(rig, st, T) {
  const hp = new THREE.Vector3(); rig.head.getWorldPosition(hp); const s = rig.scale, an = (st.act || {}).n, at = (st.act || {}).t || 0, emo = st.emo;
  if (st.persist === 'sleep') for (let i = 0; i < 3; i++) { const p = (T * .45 + i / 3) % 1; sprite(glyphTex('Z', '#ffffff', '#2b3a6a'), hp.x + .3 + p * .3, hp.y + .3 + p * .7, hp.z, .25 * s, Math.sin(p * Math.PI)); }
  if (st.persist === 'fallen' && (st.pt || 0) < 3.5) for (let i = 0; i < 4; i++) { const a = T * 4 + i * Math.PI / 2; sprite(glyphTex('★', '#ffd23f', '#2b1d16'), hp.x + Math.cos(a) * .35, hp.y + .25, hp.z + Math.sin(a) * .35, .18 * s); }
  if (emo === 'love') for (let i = 0; i < 3; i++) { const p = (T * .5 + i / 3) % 1; sprite(glyphTex('♥', '#ff4d6d'), hp.x + Math.sin(i * 2 + T) * .35, hp.y + .4 + p * .6, hp.z, .22 * s, Math.sin(p * Math.PI)); }
  if (emo === 'surprised' && (st.et || 9) < 1.2) sprite(glyphTex('!', '#ffd23f', '#2b1d16'), hp.x + .35 * s, hp.y + .55 * s, hp.z, .35 * s * clamp((st.et || 0) / .2, 0, 1));
  if (emo === 'scared' || an === 'scared') sprite(glyphTex('💧', '#7fc8ff'), hp.x + .38 * s, hp.y + .25 * s, hp.z + .1, .16 * s);
  if (emo === 'angry') sprite(glyphTex('✷', '#e8344e'), hp.x - .35 * s, hp.y + .45 * s, hp.z, .22 * s * (1 + Math.sin(T * 9) * .15));
  if (an === 'sing') for (let i = 0; i < 3; i++) { const p = (T * .6 + i / 3) % 1; sprite(glyphTex(i % 2 ? '♫' : '♪', ['#ff6fa8', '#3d8fe0', '#ffd23f'][i]), hp.x + .3 + p * .3, hp.y + .2 + p * .7, hp.z, .22 * s, Math.sin(p * Math.PI)); }
  if (an === 'think') sprite(bubbleTex(st.thinkText || '?'), hp.x + .65 * s, hp.y + .65 * s, hp.z, .55 * s, ease(at / .3));
  if (emo === 'cry') for (const sd of [-1, 1]) { const p = (T * 1.6 + (sd > 0 ? .5 : 0)) % 1; sprite(glyphTex('💧', '#7fc8ff'), hp.x + sd * .12 * s, hp.y - .05 - p * .3, hp.z + .3 * s, .08 * s, 1 - p); }
  if (an === 'sneeze' && st.act.p > .5 && st.act.p < .85) sprite(glyphTex('✺', '#cfe8ff'), hp.x + .3 * s, hp.y - .1, hp.z + .4, .25 * s, 1 - (st.act.p - .5) / .35);
}

// ---------- предметы ----------
const propCache = {};
function propMesh(p) {
  const key = p.id + p.type + (p.color || ''); if (propCache[key]) return propCache[key];
  const g = new THREE.Group(), t = p.type, cl = p.color;
  const m = (geo, c, o, par) => mesh(geo, toon(c), o == null ? .06 : o, par || g);
  switch (t) {
    case 'ball': { const b = m(G.sph(.17), cl || '#e8344e'); b.position.y = .17; const st = m(G.tor(.172, .025), '#ffffff', 0); st.position.y = .17; st.rotation.x = Math.PI / 2; break; }
    case 'apple': { m(G.sph(.12), cl || '#e23b3b').position.y = .12; const s = m(G.cyl(.01, .01, .06, 6), '#6b4a32', 0); s.position.y = .26; const l = m(G.sph(.04, 10, 8), '#5fbf4a', 0); l.position.set(.04, .27, 0); l.scale.set(1.4, .5, .8); break; }
    case 'fish': { const b = m(G.sph(.14), cl || '#7fb3ff'); b.scale.set(1.5, .7, .5); b.position.y = .12; const tl = m(G.cone(.08, .12, 4), cl || '#7fb3ff'); tl.rotation.z = Math.PI / 2; tl.position.set(-.25, .12, 0); break; }
    case 'box': m(G.box(.35, .3, .3), cl || '#c9944f').position.y = .15; break;
    case 'gift': { m(G.box(.32, .28, .32), cl || '#8d5cf6').position.y = .14; m(G.box(.34, .3, .07), '#ffd23f', 0).position.y = .14; m(G.box(.07, .3, .34), '#ffd23f', 0).position.y = .14; for (const s of [-1, 1]) { const b = m(G.sph(.06, 10, 8), '#ffd23f'); b.position.set(s * .05, .31, 0); b.scale.set(1.3, .7, .7); } break; }
    case 'flower': { m(G.cyl(.012, .012, .35, 6), '#3f9a3a', 0).position.y = .17; for (let i = 0; i < 6; i++) { const pe = m(G.sph(.045, 10, 8), cl || '#ff7ab8', .1); pe.position.set(Math.cos(i) * .06, .38, Math.sin(i) * .06); } m(G.sph(.04, 10, 8), '#ffd23f', 0).position.y = .38; break; }
    case 'book': m(G.box(.28, .06, .2), cl || '#2f7de1').position.y = .03; break;
    case 'star': { const sh = new THREE.Shape(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? .07 : .16; i ? sh.lineTo(Math.cos(a) * r, -Math.sin(a) * r) : sh.moveTo(Math.cos(a) * r, -Math.sin(a) * r); } m(new THREE.ExtrudeGeometry(sh, { depth: .05, bevelEnabled: false }), cl || '#ffd23f').position.y = .17; break; }
    case 'cake': { m(G.cyl(.18, .18, .15, 24), '#f7d6a8').position.y = .075; m(G.cyl(.185, .185, .04, 24), cl || '#ff8fb1').position.y = .16; m(G.cyl(.012, .012, .1, 6), '#7fb3ff', 0).position.y = .23; m(G.sph(.02, 8, 6), '#ffb703', 0).position.y = .29; break; }
    case 'bone': { m(G.cap(.03, .22), '#fff7e8').rotation.z = Math.PI / 2; for (const s of [-1, 1]) for (const d of [-1, 1]) { const b = m(G.sph(.045, 10, 8), '#fff7e8'); b.position.set(s * .14, d * .03, 0); } g.children.forEach(c => c.position.y += .05); break; }
    case 'carrot': { const c = m(G.cone(.05, .28, 12), cl || '#ff8a1f'); c.rotation.x = Math.PI; c.position.y = .14; for (const s of [-1, 1]) { const l = m(G.cone(.015, .1, 6), '#3f9a3a', 0); l.position.set(s * .02, .32, 0); l.rotation.z = s * .3; } break; }
    case 'cheese': { const c = m(G.cyl(.18, .18, .12, 3), cl || '#ffd23f'); c.position.y = .06; break; }
    case 'balloon': { const b = m(G.sph(.2), cl || '#ff4d6d'); b.scale.y = 1.2; b.position.y = .85; m(G.cyl(.004, .004, .6, 4), '#555555', 0).position.y = .35; break; }
    case 'key': { m(G.tor(.05, .015), cl || '#ffd23f').position.set(-.08, .05, 0); m(G.box(.16, .025, .02), cl || '#ffd23f').position.set(.04, .05, 0); break; }
    case 'cup': { m(G.cyl(.08, .065, .16, 20), cl || '#ffffff').position.y = .08; break; }
    case 'pumpkin': { for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; const sg = m(G.sph(.16, 16, 12), cl || '#ff8a1f', .04); sg.scale.set(.55, .85, 1); sg.position.set(Math.cos(a) * .1, .14, Math.sin(a) * .1); sg.rotation.y = -a; } const st = m(G.cyl(.025, .035, .1, 8), '#6b8a3a', .08); st.position.y = .3; st.rotation.z = .2; break; }
    case 'mushroom': { m(G.cyl(.05, .06, .16, 12), '#f2eadf').position.y = .08; const cp = m(new THREE.SphereGeometry(.16, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), cl || '#e8344e'); cp.position.y = .14; for (let i = 0; i < 5; i++) { const d = m(G.sph(.025, 8, 6), '#ffffff', 0); const a = i * 1.3; d.position.set(Math.cos(a) * .09, .26, Math.sin(a) * .09); } break; }
    case 'umbrella': { m(G.cyl(.012, .012, .7, 6), '#5a3a2a', 0).position.y = .35; const cp = m(G.cone(.38, .22, 10), cl || '#3d8fe0'); cp.position.y = .78; break; }
    case 'candy': { const b = m(G.sph(.07, 14, 10), cl || '#ff6fa8'); b.scale.x = 1.4; b.position.y = .07; for (const s2 of [-1, 1]) { const w = m(G.cone(.05, .07, 6), cl || '#ff6fa8'); w.rotation.z = s2 * Math.PI / 2; w.position.set(s2 * .13, .07, 0); } break; }
    case 'icecream': { const cn = m(G.cone(.07, .2, 12), '#e8b870'); cn.rotation.x = Math.PI; cn.position.y = .1; m(G.sph(.08, 14, 10), cl || '#ffb3c8').position.y = .23; m(G.sph(.065, 14, 10), '#fff3e0').position.y = .32; break; }
    case 'lollipop': { m(G.cyl(.01, .01, .3, 6), '#ffffff', 0).position.y = .15; const l = m(G.cyl(.1, .1, .03, 20), cl || '#ff4d6d'); l.rotation.x = Math.PI / 2; l.position.y = .36; break; }
    case 'banana': { const pts = [new THREE.Vector3(-.12, .1, 0), new THREE.Vector3(0, .04, 0), new THREE.Vector3(.12, .1, 0)]; m(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 12, .035, 8), cl || '#ffd23f'); break; }
    case 'pear': { m(G.sph(.11, 16, 12), cl || '#b8d84a').position.y = .1; m(G.sph(.075, 14, 10), cl || '#b8d84a').position.y = .22; m(G.cyl(.01, .01, .05, 6), '#6b4a32', 0).position.y = .3; break; }
    case 'watermelon': { const w = m(G.sph(.22, 24, 16), cl || '#3f9a3a'); w.scale.set(1.2, .9, .9); w.position.y = .2; break; }
    case 'honey': { m(G.cyl(.13, .11, .22, 20), '#c88a30').position.y = .11; m(G.cyl(.14, .14, .04, 20), '#ffd23f').position.y = .24; break; }
    case 'bucket': { const b = m(G.cyl(.15, .11, .22, 20, true), cl || '#3d8fe0'); b.material = b.material.clone(); b.material.side = THREE.DoubleSide; b.position.y = .11; m(G.tor(.15, .008, Math.PI), '#555555', 0).position.y = .22; break; }
    case 'shovel': { m(G.cyl(.012, .012, .4, 6), '#8a5a3a', 0).position.y = .3; const bl = m(G.box(.12, .14, .02), cl || '#e8344e'); bl.position.y = .06; break; }
    case 'car': { m(G.box(.36, .1, .18), cl || '#e8344e').position.y = .1; m(G.box(.2, .09, .16), cl || '#e8344e').position.set(-.02, .19, 0); for (const x of [-.11, .11]) for (const z of [-.09, .09]) { const w = m(G.cyl(.05, .05, .03, 14), '#2a2a2a'); w.rotation.x = Math.PI / 2; w.position.set(x, .05, z); } break; }
    case 'teddy': { m(G.sph(.12, 16, 12), cl || '#b07a4a').position.y = .12; m(G.sph(.09, 16, 12), cl || '#b07a4a').position.y = .3; for (const s2 of [-1, 1]) m(G.sph(.035, 10, 8), cl || '#b07a4a').position.set(s2 * .07, .38, 0); break; }
    case 'drum': { m(G.cyl(.15, .15, .14, 20), cl || '#e8344e').position.y = .07; m(G.cyl(.155, .155, .02, 20), '#fff7e8').position.y = .15; break; }
    case 'guitar': { const b = m(G.sph(.12, 16, 12), cl || '#c88a30'); b.scale.z = .35; b.position.y = .14; const b2 = m(G.sph(.09, 16, 12), cl || '#c88a30'); b2.scale.z = .35; b2.position.y = .3; m(G.box(.04, .3, .03), '#5a3a2a').position.y = .5; break; }
    case 'wand': { m(G.cyl(.01, .01, .32, 6), '#3a2a4a', 0).position.y = .16; const st = new THREE.Shape(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? .03 : .07; i ? st.lineTo(Math.cos(a) * r, -Math.sin(a) * r) : st.moveTo(Math.cos(a) * r, -Math.sin(a) * r); } m(new THREE.ExtrudeGeometry(st, { depth: .02, bevelEnabled: false }), cl || '#ffd23f').position.y = .34; break; }
    case 'lantern': { m(G.cyl(.08, .08, .18, 12), '#fff2a8', .04).position.y = .12; m(G.cyl(.09, .09, .03, 12), '#3a3f4a').position.y = .23; m(G.tor(.05, .008, Math.PI), '#3a3f4a', 0).position.y = .25; break; }
    case 'map': { const mp = m(G.box(.3, .01, .22), '#f2dfb0'); mp.position.y = .01; break; }
    case 'letter': { m(G.box(.24, .01, .16), cl || '#ffffff').position.y = .01; break; }
    case 'basket': { const b = m(G.cyl(.16, .12, .14, 16, true), cl || '#c9944f'); b.material = b.material.clone(); b.material.side = THREE.DoubleSide; b.position.y = .07; m(G.tor(.15, .012, Math.PI), cl || '#c9944f', 0).position.y = .14; break; }
    case 'chest': { m(G.box(.4, .22, .26), cl || '#8a5a3a').position.y = .11; const lid = m(G.cyl(.13, .13, .4, 16, false), cl || '#8a5a3a'); lid.rotation.z = Math.PI / 2; lid.scale.set(1, 1, 1); lid.position.y = .22; m(G.box(.06, .08, .02), '#ffd23f', 0).position.set(0, .2, .135); break; }
    case 'coin': { const c2 = m(G.cyl(.06, .06, .015, 20), '#ffd23f'); c2.rotation.x = Math.PI / 2; c2.position.y = .06; break; }
    case 'egg': { const e = m(G.sph(.07, 16, 12), cl || '#fff7e8'); e.scale.y = 1.3; e.position.y = .09; break; }
    case 'pie': { m(G.cyl(.18, .15, .08, 24), cl || '#e8b870').position.y = .04; break; }
    case 'cookie': { const c2 = m(G.cyl(.08, .08, .02, 20), cl || '#c88a50'); c2.position.y = .01; break; }
    case 'milk': { m(G.cyl(.06, .06, .22, 14), cl || '#ffffff').position.y = .11; m(G.cyl(.03, .05, .06, 12), '#ffffff').position.y = .25; m(G.cyl(.03, .03, .02, 12), '#3d8fe0', 0).position.y = .29; break; }
    case 'clock': { const c2 = m(G.cyl(.13, .13, .05, 24), cl || '#e8344e'); c2.rotation.x = Math.PI / 2; c2.position.y = .15; const f = m(G.cyl(.11, .11, .01, 24), '#ffffff', 0); f.rotation.x = Math.PI / 2; f.position.set(0, .15, .03); break; }
    case 'candle': { m(G.cyl(.04, .04, .18, 12), cl || '#fff3e0').position.y = .09; const fl = m(G.cone(.025, .07, 8), '#ffb703', 0); fl.position.y = .22; break; }
    case 'leaf': { const l = m(G.sph(.1, 12, 8), cl || '#5fbf4a'); l.scale.set(1.4, .1, .7); l.position.y = .02; break; }
    case 'rock': { const r2 = m(new THREE.IcosahedronGeometry(.13, 0), cl || '#8a8a92'); r2.position.y = .09; r2.scale.y = .7; break; }
    case 'stick': { const st = m(G.cyl(.015, .02, .5, 6), cl || '#7a4e30'); st.rotation.z = Math.PI / 2; st.position.y = .02; break; }
    case 'phone': { m(G.box(.08, .15, .015), cl || '#2a2a2a').position.y = .08; break; }
    case 'kite': { const k2 = m(G.cone(.2, .3, 4), cl || '#ff6fa8'); k2.scale.z = .1; k2.position.y = .9; m(G.cyl(.003, .003, .7, 4), '#555555', 0).position.y = .4; break; }
    case 'bag': { m(G.box(.25, .2, .1), cl || '#c0283c').position.y = .1; m(G.tor(.07, .01, Math.PI), '#5a3a2a', 0).position.y = .2; break; }
    case 'door': { const fr = m(G.box(.62, 1.12, .1), '#7a4e30'); fr.position.y = .56; const dr = m(G.box(.5, 1.02, .06), cl || '#a8673a'); dr.position.set(0, .53, .05); for (const y of [.3, .78]) m(G.box(.4, .02, .01), '#7a4e30', 0).position.set(0, y, .085); const kn = m(G.sph(.035, 10, 8), '#ffd23f', 0); kn.position.set(.17, .5, .1);
      const arc = m(G.tor(.31, .04, Math.PI), '#7a4e30'); arc.position.y = 1.12; g.userData.glowY = .6; g.userData.glowS = 1.6; g.userData.glowC = '#ffe08a'; break; }
    case 'jack': { for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; const sg = m(G.sph(.16, 16, 12), cl || '#ff8a1f', .04); sg.scale.set(.55, .85, 1); sg.position.set(Math.cos(a) * .1, .14, Math.sin(a) * .1); sg.rotation.y = -a; } const st = m(G.cyl(.025, .035, .1, 8), '#6b8a3a', .08); st.position.y = .3; st.rotation.z = .2;
      const fm = new THREE.MeshBasicMaterial({ color: 0x3a1a08 }); g.userData.faceMat = fm; const shp = (pts) => { const sh = new THREE.Shape(); pts.forEach((q, i) => i ? sh.lineTo(q[0], q[1]) : sh.moveTo(q[0], q[1])); return new THREE.ShapeGeometry(sh); };
      for (const sx of [-1, 1]) { const e = new THREE.Mesh(shp([[-.035, 0], [.035, 0], [0, .05]]), fm); e.position.set(sx * .06, .17, .175); g.add(e); }
      const mo = new THREE.Mesh(shp([[-.09, .02], [-.05, -.01], [-.03, .015], [0, -.02], [.03, .015], [.05, -.01], [.09, .02], [.06, -.04], [-.06, -.04]]), fm); mo.position.set(0, .1, .178); g.add(mo); g.userData.glowY = .15; g.userData.glowS = .7; g.userData.glowC = '#ffb347'; break; }
    case 'moon': { const mo = mesh(G.sph(.5, 24, 16), basic(cl || '#fff3c4'), 0, g); mo.position.y = 4.2; mo.castShadow = false; g.userData.glowY = 4.2; g.userData.glowS = 2.6; g.userData.glowC = '#fff3c4'; g.userData.alwaysGlow = true; break; }
    case 'ghost': { const b = m(G.sph(.25, 20, 14), '#ffffff', .05); b.position.y = .75; const sk = m(G.cone(.27, .5, 16, true), '#ffffff', .05); sk.position.y = .5; for (const sx of [-1, 1]) m(G.sph(.04, 10, 8), '#2b1d16', 0).position.set(sx * .08, .8, .22); g.userData.float = true; break; }
    case 'bat': { const b = m(G.sph(.07, 12, 10), '#3a2a4a', .06); b.position.y = 1.6; for (const sx of [-1, 1]) { const w = m(G.cone(.09, .2, 3), '#3a2a4a', .04); w.rotation.z = sx * Math.PI / 2; w.position.set(sx * .14, 1.6, 0); } g.userData.float = true; break; }
    case 'garland': { const pts = []; for (let i = 0; i <= 12; i++) { const k = i / 12; pts.push(new THREE.Vector3((k - .5) * 3, 1.9 - Math.sin(k * Math.PI) * .35, 0)); } const cv = new THREE.CatmullRomCurve3(pts); mesh(new THREE.TubeGeometry(cv, 30, .01, 4), basic('#2b2b2b'), 0, g);
      for (let i = 1; i < 12; i++) { const q = cv.getPoint(i / 12); const b = mesh(G.sph(.05, 10, 8), basic(['#ffd23f', '#ff4d6d', '#3d8fe0', '#5fbf4a', '#ff8a1f'][i % 5]), 0, g); b.position.copy(q).y -= .05; }
      for (const sx of [-1.55, 1.55]) m(G.cyl(.03, .03, 2, 8), '#7a4e30').position.set(sx, 1, 0); break; }
    case 'tree': { const tr = m(G.cyl(.08, .12, .6, 10), '#7a4e30'); tr.position.y = .3; for (let i = 0; i < 3; i++) { const c2 = m(G.cone(.5 - i * .12, .6, 14), cl || '#2f8f4e'); c2.position.y = .7 + i * .35; } break; }
    case 'snowman': { for (const [r2, y] of [[.3, .3], [.22, .75], [.16, 1.08]]) m(G.sph(r2, 18, 14), '#ffffff').position.y = y; const n2 = m(G.cone(.03, .14, 8), '#ff8a1f', 0); n2.rotation.x = Math.PI / 2; n2.position.set(0, 1.08, .2); for (const sx of [-1, 1]) m(G.sph(.025, 8, 6), '#2b1d16', 0).position.set(sx * .06, 1.13, .14); break; }
    case 'fire': { for (let i = 0; i < 5; i++) { const lg = m(G.cyl(.04, .04, .5, 8), '#7a4e30'); lg.rotation.set(Math.PI / 2, 0, i * Math.PI / 5); lg.position.y = .05; } const f1 = mesh(G.cone(.2, .5, 10), basic('#ff8a1f'), 0, g); f1.position.y = .3; const f2 = mesh(G.cone(.11, .32, 10), basic('#ffd23f'), 0, g); f2.position.y = .25; g.userData.glowY = .4; g.userData.glowS = 1.4; g.userData.glowC = '#ffb347'; g.userData.alwaysGlow = true; break; }
    case 'tent': { const t2 = m(G.cone(.7, 1, 4), cl || '#e8344e'); t2.position.y = .5; t2.rotation.y = Math.PI / 4; break; }
    case 'castle': { m(G.box(1.2, .8, .5), cl || '#c8c0d8').position.y = .4; for (const sx of [-.6, .6]) { m(G.cyl(.18, .18, 1.2, 12), cl || '#c8c0d8').position.set(sx, .6, 0); const r2 = m(G.cone(.24, .4, 12), '#e8344e'); r2.position.set(sx, 1.4, 0); } break; }
    case 'rainbow': { ['#e8344e', '#ff8a1f', '#ffd23f', '#5fbf4a', '#3d8fe0', '#8d5cf6'].forEach((c2, i) => { const a = mesh(G.tor(2.2 - i * .09, .05, Math.PI), basic(c2), 0, g); a.position.y = 0; a.castShadow = false; }); break; }
    default: m(G.sph(.12), cl || '#cccccc').position.y = .12;
  }
  g.traverse(o => { if (o.isMesh) o.castShadow = true; }); propCache[key] = g; return g;
}

// ---------- декорации ----------
const locCache = {};
const SKY = { day: ['#5aaef0', '#d8f0ff'], evening: ['#5a4fa8', '#ffb07a'], night: ['#08103a', '#2a3a7a'] };
function skyTex(time, type) { const k = 'sky' + time + type; if (texCache[k]) return texCache[k]; const s = type === 'space' ? ['#05051a', '#1b1450'] : type === 'room' || type === 'kitchen' ? ['#f7e3c4', '#f7e3c4'] : SKY[time] || SKY.day; const t = canvasTex(4, 256, (g) => { const gr = g.createLinearGradient(0, 0, 0, 256); gr.addColorStop(0, s[0]); gr.addColorStop(1, s[1]); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); }); texCache[k] = t; return t; }
function plane(w, d, c, map) { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), toon(c, map)); m.rotation.x = -Math.PI / 2; m.receiveShadow = true; return m; }
function tree(g, x, z, s, kind, cl, snow) { if (MK3D.hq) return treeHQ(g, x, z, s, kind, cl, snow); const t = new THREE.Group(); t.position.set(x, 0, z); t.scale.setScalar(s); g.add(t); mesh(G.cyl(.15, .22, 1.6, 10), toon('#7a4e30'), .04, t).position.y = .8;
  if (kind === 'fir') { for (let i = 0; i < 3; i++) { const c = mesh(G.cone(1.1 - i * .25, 1.2, 10), toon(cl || '#3d7a5a'), .03, t); c.position.y = 1.4 + i * .65; if (snow) { const sn = new THREE.Mesh(G.cone(.7 - i * .18, .5, 10), toon('#ffffff')); sn.position.y = 1.85 + i * .65; t.add(sn); } } return; }
  for (const [a, b, c, r] of [[0, 2.1, 0, .9], [-.5, 1.8, .2, .65], [.5, 1.85, -.1, .7], [.1, 2.6, 0, .6]]) { const l = mesh(new THREE.IcosahedronGeometry(r, 2), toon(cl || '#4e9a4a'), .03, t); l.position.set(a, b, c); } }
function bush(g, x, z, s, cl) { if (MK3D.hq) return bushHQ(g, x, z, s, cl); const b = mesh(new THREE.IcosahedronGeometry(.5 * s, 2), toon(cl || '#3c8f37'), .03, g); b.position.set(x, .3 * s, z); b.scale.y = .75; }
function flowers(g, r, n, x0, x1, z0, z1, skip) { if (MK3D.hq) return flowersHQ(g, r, n, x0, x1, z0, z1, skip); const cols = ['#ff6fa8', '#ffd23f', '#ffffff', '#a974ff', '#ff8a3d']; for (let i = 0; i < n; i++) { const f = new THREE.Mesh(G.sph(.05, 8, 6), toon(cols[i % 5])); f.position.set(lerp(x0, x1, r()), .05, lerp(z0, z1, r())); g.add(f); } }
function house(g, x, z, wall, roof) { const h = new THREE.Group(); h.position.set(x, 0, z); g.add(h); mesh(G.box(4, 2.6, 3), toon(wall), .01, h).position.y = 1.3; const rf = mesh(G.cone(3.2, 1.8, 4), toon(roof), .01, h); rf.position.y = 3.5; rf.rotation.y = Math.PI / 4; rf.scale.set(1, 1, .8);
  mesh(G.box(.8, 1.5, .1), toon('#8a5a3a'), .03, h).position.set(0, .75, 1.52); for (const xx of [-1.2, 1.2]) mesh(G.box(.8, .7, .08), toon('#9fd6ff'), .04, h).position.set(xx, 1.7, 1.52); mesh(G.box(.4, 1, .4), toon('#a04a3a'), .03, h).position.set(1, 3.8, 0);
  if (MK3D.hq) { h.children[0].material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: sidingTex(wall), roughness: .85 }); h.children[1].material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: shingleTex(roof), roughness: .8 }); }
  return h; }
function fence(g, z, cl, gapX) { if (MK3D.hq) return fenceHQ(g, z, cl, gapX); for (let x = -12; x <= 12; x += .5) { if (gapX != null && Math.abs(x - gapX) < .8) continue; mesh(G.box(.16, .9, .06), toon(cl), .06, g).position.set(x, .45, z); } for (const y of [.3, .65]) mesh(G.box(24, .1, .05), toon('#d9b070'), 0, g).position.set(0, y, z - .02); }

// ================= декорации «как в кино»: трава из травинок, листья, кора, доски забора, цветы, камни =================
// всё повторяющееся рисуется «пачкой» (InstancedMesh): тысячи травинок и листьев — один вызов видеокарты, поэтому быстро
const windU = { value: 0 }, envC = {};
function wind(mat, amp, mode) { mat.onBeforeCompile = (sh) => { sh.uniforms.uWind = windU; sh.vertexShader = 'uniform float uWind;\n' + sh.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>
  #ifdef USE_INSTANCING
  vec3 ip = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]);
  #else
  vec3 ip = vec3(0.0);
  #endif
  float ww = sin(uWind * 1.6 + ip.x * .8 + ip.z * .5) * .6 + sin(uWind * 2.9 + ip.x * 2.1 - ip.z) * .3;
  ${mode === 'blade' ? 'transformed.z += ww * ' + amp.toFixed(3) + ' * position.y * position.y;' : 'transformed.x += ww * ' + amp.toFixed(3) + ' * position.y; transformed.z += ww * ' + (amp * .6).toFixed(3) + ' * position.y;'}`); };
  mat.customProgramCacheKey = () => 'wind' + mode + amp; return mat; }
function bladeGeo() { if (envC.blade) return envC.blade; const S = 4, P = [], N = [], C = [], I = [];
  for (let i = 0; i <= S; i++) { const y = i / S, hw = i === S ? 0 : .5 * Math.pow(1 - y, .75), z = .22 * y * y, c = .38 + .72 * y; P.push(-hw, y, z, hw, y, z); N.push(0, 1, .25, 0, 1, .25); C.push(c * .95, c, c * .9, c * .95, c, c * .9); }
  for (let i = 0; i < S; i++) { const a = i * 2; I.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(C, 3)); g.setIndex(I); return (envC.blade = g); }
function leafGeo(narrow) { const k = 'leaf' + (narrow ? 'n' : ''); if (envC[k]) return envC[k]; const w = narrow ? .16 : .42, sh = new THREE.Shape(); sh.moveTo(0, 0); sh.quadraticCurveTo(w, .35, 0, 1); sh.quadraticCurveTo(-w, .35, 0, 0);
  const g = new THREE.ShapeGeometry(sh, 6); const p = g.attributes.position, uv = g.attributes.uv; for (let i = 0; i < p.count; i++) { uv.setXY(i, p.getX(i) / (2 * w) + .5, p.getY(i)); p.setZ(i, -Math.abs(p.getX(i)) * .25 + p.getY(i) * p.getY(i) * .08); } g.computeVertexNormals(); return (envC[k] = g); }
function leafTex() { if (envC.leafT) return envC.leafT; return (envC.leafT = canvasTex(64, 128, (g) => { const gr = g.createLinearGradient(0, 128, 0, 0); gr.addColorStop(0, '#c8c8c8'); gr.addColorStop(1, '#ffffff'); g.fillStyle = gr; g.fillRect(0, 0, 64, 128);
  g.strokeStyle = 'rgba(255,255,230,.55)'; g.lineWidth = 2; g.beginPath(); g.moveTo(32, 128); g.lineTo(32, 6); g.stroke(); g.lineWidth = 1; g.strokeStyle = 'rgba(255,255,230,.3)'; for (let y = 110; y > 16; y -= 16) { g.beginPath(); g.moveTo(32, y); g.lineTo(10, y - 14); g.moveTo(32, y); g.lineTo(54, y - 14); g.stroke(); } })); }
function barkTex() { if (envC.bark) return envC.bark; const r = rng(9); const t = canvasTex(128, 256, (g) => { g.fillStyle = '#7a5032'; g.fillRect(0, 0, 128, 256);
  for (let i = 0; i < 70; i++) { const x = r() * 128, w = 1 + r() * 4; g.strokeStyle = r() < .6 ? 'rgba(50,30,15,.45)' : 'rgba(160,120,80,.35)'; g.lineWidth = w; g.beginPath(); g.moveTo(x, 0); for (let y = 0; y <= 256; y += 16) g.lineTo(x + Math.sin(y * .05 + i) * 3, y); g.stroke(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 2); return (envC.bark = t); }
function grainTex(base) { const k = 'grain' + base; if (envC[k]) return envC[k]; const r = rng(17); const t = canvasTex(256, 256, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 90; i++) { const x = r() * 256; g.strokeStyle = r() < .55 ? 'rgba(90,55,25,.22)' : 'rgba(255,240,210,.25)'; g.lineWidth = .6 + r() * 1.8; g.beginPath(); g.moveTo(x, 0); for (let y = 0; y <= 256; y += 8) g.lineTo(x + Math.sin(y * .03 + i * 1.7) * 2.5, y); g.stroke(); }
  for (let i = 0; i < 3; i++) { const x = r() * 256, y = r() * 256; g.strokeStyle = 'rgba(90,55,25,.35)'; g.lineWidth = 1.2; for (let k2 = 1; k2 < 4; k2++) { g.beginPath(); g.ellipse(x, y, 3 * k2, 7 * k2, 0, 0, 7); g.stroke(); } } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; return (envC[k] = t); }
function groundTex(base) { const k = 'gr' + base; if (envC[k]) return envC[k]; const r = rng(23), b = new THREE.Color(base); const t = canvasTex(512, 512, (g) => { g.fillStyle = base; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 900; i++) { const x = r() * 512, y = r() * 512, rr = 4 + r() * 22, l = (r() - .5) * .22; const c = b.clone().offsetHSL((r() - .5) * .03, 0, l); g.fillStyle = '#' + c.getHexString(); g.globalAlpha = .35; g.beginPath(); g.ellipse(x, y, rr, rr * .7, r() * 3, 0, 7); g.fill(); } g.globalAlpha = 1; });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(36, 36); return (envC[k] = t); }
let _m4, _q, _q2, _v, _s, _c;
function tmpInit() { _m4 = new THREE.Matrix4(); _q = new THREE.Quaternion(); _q2 = new THREE.Quaternion(); _v = new THREE.Vector3(); _s = new THREE.Vector3(); _c = new THREE.Color(); }
function grassField(g, r, green, skip, opts) { // трава: ~150–200 тыс. отдельных травинок, гуще у камеры, качаются от ветра
  opts = opts || {}; const items = []; const base = new THREE.Color(green), dark = base.clone().multiplyScalar(.7), light = base.clone().lerp(new THREE.Color('#d8e86a'), .25);
  const band = (z0, z1, dens) => { for (let z = z0; z < z1; z += .25) { const half = 3 + (5.5 - z) * .78; const n = Math.round(dens * .25 * half * 2); for (let i = 0; i < n; i++) { const x = (r() - .5) * 2 * half, zz = z + r() * .25; if (skip && skip(x, zz)) continue; items.push([x, zz]); } } };
  band(-1.5, 5.6, 1500); band(-4, -1.5, 850); band(-7, -4, 420);
  const mat = wind(new THREE.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, side: THREE.DoubleSide, roughness: .85, metalness: 0, envMapIntensity: .5 }), .28, 'blade');
  const im = new THREE.InstancedMesh(bladeGeo(), mat, items.length); im.castShadow = false; im.receiveShadow = true; im.frustumCulled = false;
  items.forEach(([x, z], i) => { const nearRow = (Math.abs(z) < .55 || Math.abs(z + .9) < .4) && Math.abs(x) < 6; const h = (nearRow ? .045 + r() * .045 : .07 + r() * .07) * (r() < .04 ? 1.8 : 1);
    _q.setFromEuler(new THREE.Euler((r() - .5) * .35, r() * Math.PI * 2, (r() - .5) * .35)); _v.set(x, 0, z); _s.set(.012 + r() * .01, h, h); _m4.compose(_v, _q, _s); im.setMatrixAt(i, _m4);
    const k = r(); _c.copy(k < .5 ? dark : base).lerp(light, r() * .6); if (r() < .05) _c.lerp(new THREE.Color('#c8c070'), .35); im.setColorAt(i, _c); });
  im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true; g.add(im); return im; }
function leafCloud(par, pts, cols, size, narrow) { // много листьев одной «пачкой»; pts: [pos, dir]
  const mat = wind(new THREE.MeshStandardMaterial({ color: 0xffffff, map: leafTex(), side: THREE.DoubleSide, roughness: .7, metalness: 0, envMapIntensity: .6 }), narrow ? .02 : .04, 'leaf');
  const im = new THREE.InstancedMesh(leafGeo(narrow), mat, pts.length); im.castShadow = true; im.receiveShadow = true; im.frustumCulled = false; const r = rng(pts.length * 7 + 3);
  pts.forEach(([p, d], i) => { _q.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d); _q2.setFromAxisAngle(d, r() * Math.PI * 2); _q.premultiply(_q2); const sz = size * (.75 + r() * .5); _s.set(sz, sz, sz); _m4.compose(p, _q, _s); im.setMatrixAt(i, _m4);
    _c.set(cols[(r() * cols.length) | 0]).offsetHSL((r() - .5) * .02, 0, (r() - .5) * .06 + (d.y > .3 ? .04 : d.y < -.3 ? -.05 : 0)); im.setColorAt(i, _c); });
  im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true; par.add(im); return im; }
function crown(t, cx, cy, cz, R, cols, r) { // крона-шар: тёмная серединка + листья по поверхности, кончиком наружу и чуть вниз
  const inner = new THREE.Mesh(G.sph(R * .9, 20, 14), matte(new THREE.Color(cols[0]).multiplyScalar(.55).getStyle())); inner.position.set(cx, cy, cz); inner.castShadow = true; inner.receiveShadow = true; t.add(inner);
  const n = Math.round(4 * Math.PI * R * R * 260), pts = [];
  for (let i = 0; i < n; i++) { const u = r() * 2 - 1, a = r() * Math.PI * 2, s2 = Math.sqrt(1 - u * u); const d = new THREE.Vector3(s2 * Math.cos(a), u, s2 * Math.sin(a)); const p = new THREE.Vector3(cx, cy, cz).addScaledVector(d, R * (.86 + r() * .16));
    const dir = d.clone().add(new THREE.Vector3((r() - .5) * .6, -.35, (r() - .5) * .6)).normalize(); pts.push([p, dir]); }
  leafCloud(t, pts, cols, .2, false); }
function treeHQ(g, x, z, s, kind, cl, snow) {
  const t = new THREE.Group(); t.position.set(x, 0, z); t.scale.setScalar(s); g.add(t); const r = rng(global.MK.hash32(x.toFixed(2) + ',' + z.toFixed(2)));
  const bark = new THREE.MeshStandardMaterial({ color: 0xffffff, map: barkTex(), roughness: .95, metalness: 0 });
  const tr = new THREE.Mesh(new THREE.CylinderGeometry(.12, .24, 1.9, 14, 4), bark); tr.position.y = .95; tr.castShadow = tr.receiveShadow = true; t.add(tr);
  for (let i = 0; i < 3; i++) { const sx = (r() < .5 ? -1 : 1); const cv = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 1.2 + i * .25, 0), new THREE.Vector3(sx * .25, 1.6 + i * .25, (r() - .5) * .3), new THREE.Vector3(sx * (.45 + r() * .2), 1.9 + i * .2, (r() - .5) * .4)]);
    const br = new THREE.Mesh(new THREE.TubeGeometry(cv, 8, .05 - i * .008, 8), bark); br.castShadow = true; t.add(br); }
  if (kind === 'fir') { const cols = snow ? ['#2f6a4c', '#3a7a58'] : [cl || '#2f6a4c', '#3d7a5a', '#2a5e44'];
    for (let i = 0; i < 4; i++) { const R = 1.15 - i * .24, H = 1.15, y = 1.25 + i * .58; const ic = new THREE.Mesh(G.cone(R * .85, H * .95, 14), matte(new THREE.Color(cols[0]).multiplyScalar(.6).getStyle())); ic.position.y = y; ic.castShadow = true; t.add(ic);
      const n = Math.round(Math.PI * R * Math.hypot(R, H) * 420), pts = [];
      for (let k = 0; k < n; k++) { const tt = Math.sqrt(r()), a = r() * Math.PI * 2, rad = R * tt; const p = new THREE.Vector3(Math.cos(a) * rad, y + H / 2 - tt * H, Math.sin(a) * rad); const dir = new THREE.Vector3(Math.cos(a), -.55 + (r() - .5) * .3, Math.sin(a)).normalize(); pts.push([p, dir]); }
      leafCloud(t, pts, cols, .26, true);
      if (snow) { const sn = new THREE.Mesh(G.cone(R * .75, .45, 14), matte('#ffffff')); sn.position.y = y + H * .32; t.add(sn); } }
    return t; }
  const cols = cl ? [cl] : ['#4e9a4a', '#5aa850', '#3f8a3e', '#6ab45a'];
  for (const [a, b, c, R] of [[0, 2.2, 0, .95], [-.55, 1.9, .2, .7], [.55, 1.95, -.1, .75], [.1, 2.75, 0, .62]]) crown(t, a, b, c, R, cols, r);
  return t; }
function bushHQ(g, x, z, s, cl) { const t = new THREE.Group(); t.position.set(x, 0, z); g.add(t); const r = rng(global.MK.hash32('b' + x + z)); const cols = [cl || '#3c8f37', '#4a9e42', '#357f33'];
  for (const [a, b, c, R] of [[0, .32, 0, .5], [-.35, .24, .1, .36], [.38, .26, -.05, .38]]) crown(t, a * s, b * s, c * s, R * s, cols, r); }
function flowersHQ(g, r, n, x0, x1, z0, z1, skip) { const cols = ['#ff6fa8', '#ffd23f', '#ffffff', '#a974ff', '#ff8a3d', '#ff4d6d', '#7fc8ff'];
  if (!envC.petal) { const sh = new THREE.Shape(); for (let i = 0; i <= 60; i++) { const a = i / 60 * Math.PI * 2, rr = .55 + .45 * Math.abs(Math.cos(a * 2.5)); const px = Math.cos(a) * rr, py = Math.sin(a) * rr; i ? sh.lineTo(px, py) : sh.moveTo(px, py); } const pg = new THREE.ShapeGeometry(sh, 2); pg.rotateX(-Math.PI / 2); const pp = pg.attributes.position; for (let i = 0; i < pp.count; i++) { const d = Math.hypot(pp.getX(i), pp.getZ(i)); pp.setY(i, d * d * .18); } pg.computeVertexNormals(); envC.petal = pg; }
  const ok = []; for (let i = 0; i < n; i++) { const x = lerp(x0, x1, r()), z = lerp(z0, z1, r()); if (skip && skip(x, z)) continue; if (Math.abs(z) < .5 && Math.abs(x) < 6) continue; ok.push([x, z]); }
  const stem = new THREE.InstancedMesh(new THREE.CylinderGeometry(.5, .5, 1, 5).translate(0, .5, 0), new THREE.MeshStandardMaterial({ color: '#4a8f3a', roughness: .8 }), ok.length);
  const head = new THREE.InstancedMesh(envC.petal, new THREE.MeshStandardMaterial({ color: 0xffffff, side: THREE.DoubleSide, roughness: .55 }), ok.length);
  const mid = new THREE.InstancedMesh(G.sph(1, 8, 6), new THREE.MeshStandardMaterial({ color: '#ffc21a', roughness: .6 }), ok.length);
  ok.forEach(([x, z], i) => { const h = .1 + r() * .12, sz = .035 + r() * .025; _q.setFromEuler(new THREE.Euler((r() - .5) * .2, 0, (r() - .5) * .2)); _v.set(x, 0, z); _s.set(.006, h, .006); _m4.compose(_v, _q, _s); stem.setMatrixAt(i, _m4);
    _v.set(x, h, z); _q.setFromEuler(new THREE.Euler(.35 + (r() - .5) * .4, r() * 6.28, (r() - .5) * .3)); _s.set(sz, sz, sz); _m4.compose(_v, _q, _s); head.setMatrixAt(i, _m4); _s.set(sz * .3, sz * .2, sz * .3); _v.y += .004; _m4.compose(_v, _q, _s); mid.setMatrixAt(i, _m4);
    head.setColorAt(i, _c.set(cols[i % cols.length])); });
  for (const im of [stem, head, mid]) { im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true; im.castShadow = false; im.receiveShadow = true; im.frustumCulled = false; g.add(im); } }
function rocksHQ(g, r, n) { const geo = new THREE.IcosahedronGeometry(1, 2); const p = geo.attributes.position; for (let i = 0; i < p.count; i++) { _v.fromBufferAttribute(p, i); const k = 1 + (Math.sin(_v.x * 5.1 + _v.y * 3.3) * .08 + Math.sin(_v.z * 7.7) * .06); p.setXYZ(i, _v.x * k, _v.y * k * .7, _v.z * k); } geo.computeVertexNormals();
  const im = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .9 }), n);
  for (let i = 0; i < n; i++) { const sd = r() < .5 ? -1 : 1, x = sd * (4.5 + r() * 5), z = -3 + r() * 6, sz = .06 + r() * .16; _v.set(x, sz * .25, z); _q.setFromEuler(new THREE.Euler(0, r() * 6, 0)); _s.set(sz * (1 + r() * .4), sz, sz); _m4.compose(_v, _q, _s); im.setMatrixAt(i, _m4); im.setColorAt(i, _c.set('#9a968c').offsetHSL(0, 0, (r() - .5) * .15)); }
  im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true; im.castShadow = im.receiveShadow = true; g.add(im); }
function fenceHQ(g, z, cl, gapX) { const r = rng(global.MK.hash32('f' + z)); const w = .15, h = .9;
  if (!envC.picket) { const sh = new THREE.Shape(); sh.moveTo(-w / 2, 0); sh.lineTo(-w / 2, h - w * .55); sh.lineTo(0, h); sh.lineTo(w / 2, h - w * .55); sh.lineTo(w / 2, 0); sh.lineTo(-w / 2, 0);
    const eg = new THREE.ExtrudeGeometry(sh, { depth: .035, bevelEnabled: true, bevelThickness: .006, bevelSize: .007, bevelSegments: 2, curveSegments: 2 }); const uv = eg.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 3, uv.getY(i) * .9); envC.picket = eg; }
  const xs = []; for (let x = -12; x <= 12; x += .5) { if (gapX != null && Math.abs(x - gapX) < .8) continue; xs.push(x); }
  const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, map: grainTex(cl), roughness: .85 }); const im = new THREE.InstancedMesh(envC.picket, mat, xs.length);
  xs.forEach((x, i) => { _v.set(x + (r() - .5) * .02, -.02 + r() * .03, z); _q.setFromEuler(new THREE.Euler((r() - .5) * .03, (r() - .5) * .04, (r() - .5) * .05)); _s.set(1, .96 + r() * .08, 1); _m4.compose(_v, _q, _s); im.setMatrixAt(i, _m4); im.setColorAt(i, _c.set(0xffffff).multiplyScalar(.88 + r() * .14)); });
  im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true; im.castShadow = im.receiveShadow = true; g.add(im);
  const rt = grainTex('#d9b070').clone(); rt.needsUpdate = true; rt.rotation = Math.PI / 2; rt.repeat.set(1, 30);
  for (const y of [.3, .65]) { const rail = new THREE.Mesh(new THREE.BoxGeometry(24.4, .09, .04), new THREE.MeshStandardMaterial({ color: 0xffffff, map: rt, roughness: .85 })); rail.position.set(0, y, z - .025); rail.castShadow = rail.receiveShadow = true; g.add(rail); }
  const nails = new THREE.InstancedMesh(G.sph(.008, 6, 4), new THREE.MeshStandardMaterial({ color: '#555', roughness: .4, metalness: .6 }), xs.length * 2); let ni = 0;
  xs.forEach(x => { for (const y of [.3, .65]) { _v.set(x, y, z + .042); _q.identity(); _s.set(1, 1, 1); _m4.compose(_v, _q, _s); nails.setMatrixAt(ni++, _m4); } }); nails.instanceMatrix.needsUpdate = true; g.add(nails); }
function dirtTex(c, rx, ry) { const k = 'dt' + c + rx + ry; if (envC[k]) return envC[k]; const r = rng(41), b = new THREE.Color(c); const t = canvasTex(512, 512, (g) => { g.fillStyle = c; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 1400; i++) { const x = r() * 512, y = r() * 512, rr = 3 + r() * 16; g.fillStyle = '#' + b.clone().offsetHSL(0, -.05, (r() - .5) * .14).getHexString(); g.globalAlpha = .4; g.beginPath(); g.ellipse(x, y, rr, rr * .6, r() * 3, 0, 7); g.fill(); }
  g.globalAlpha = 1; for (let i = 0; i < 260; i++) { const x = r() * 512, y = r() * 512, rr = 1.5 + r() * 3.5; g.fillStyle = '#' + b.clone().offsetHSL(0, -.15, -.12 + r() * .25).getHexString(); g.beginPath(); g.ellipse(x, y, rr, rr * .75, r() * 3, 0, 7); g.fill(); g.fillStyle = 'rgba(0,0,0,.18)'; g.beginPath(); g.ellipse(x + 1, y + 1.2, rr, rr * .5, 0, 0, Math.PI); g.fill(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry); return (envC[k] = t); }
function sidingTex(c) { const k = 'sd' + c; if (envC[k]) return envC[k]; const t = canvasTex(256, 256, (g) => { g.fillStyle = c; g.fillRect(0, 0, 256, 256); for (let y = 0; y < 256; y += 21) { g.fillStyle = 'rgba(0,0,0,.10)'; g.fillRect(0, y, 256, 3); g.fillStyle = 'rgba(255,255,255,.12)'; g.fillRect(0, y + 3, 256, 2); } }); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(2, 2); return (envC[k] = t); }
function shingleTex(c) { const k = 'sh' + c; if (envC[k]) return envC[k]; const cv = document.createElement('canvas'); cv.width = cv.height = 512; const g = cv.getContext('2d'); g.fillStyle = c; g.fillRect(0, 0, 512, 512); g.globalCompositeOperation = 'multiply'; const tile = scaleTile('col'); for (let j = 0; j < 8; j++) for (let i = 0; i < 8; i++) g.drawImage(tile, i * 64, j * 64, 64.5, 64.5); g.globalCompositeOperation = 'multiply'; g.drawImage(tile, 0, 0, 0, 0);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 3); return (envC[k] = t); }
function woodTex(base) { return canvasTex(256, 256, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 256); g.strokeStyle = 'rgba(70,40,20,.3)'; g.lineWidth = 3; for (let y = 0; y < 256; y += 32) { g.beginPath(); g.moveTo(0, y); g.lineTo(256, y); g.stroke(); } }); }
function tileTex(base, line, n) { return canvasTex(256, 256, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 256); g.strokeStyle = line; g.lineWidth = 3; for (let i = 0; i <= n; i++) { const p = i * 256 / n; g.beginPath(); g.moveTo(p, 0); g.lineTo(p, 256); g.moveTo(0, p); g.lineTo(256, p); g.stroke(); } }); }
function dotsTex(base, dot) { return canvasTex(256, 256, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 256); g.fillStyle = dot; for (let y = 16; y < 256; y += 48) for (let x = 16 + (y / 48 % 2) * 24; x < 256; x += 48) { g.beginPath(); g.arc(x, y, 7, 0, 7); g.fill(); } }); }
function buildLoc(spec) {
  const g = new THREE.Group(), type = spec.type || 'meadow', time = spec.time || 'day', r = rng(global.MK.hash32(String(spec.seed || 1) + type)), night = time === 'night';
  const green = night ? '#2f6b45' : time === 'evening' ? '#6aa84f' : '#79c95a';
  const rep = (t, n) => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(n, n); return t; };
  if (['forest', 'meadow', 'yard', 'playground', 'winter'].includes(type)) {
    const snow = type === 'winter';
    const gp = plane(120, 120, snow ? '#f2f6fc' : green); if (MK3D.hq && !snow) gp.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: groundTex(new THREE.Color(green).multiplyScalar(.8).getStyle()), roughness: .95 }); g.add(gp);
    const soft = (d, x, z) => d < -.1 ? false : d > .14 ? true : (global.MK.hash32(x.toFixed(3) + z.toFixed(3)) % 100) / 100 < (d + .1) / .24; // d — насколько глубоко внутри тропинки
    const skipG = (x, z) => (type === 'yard' && (soft(Math.min(.7 - Math.abs(x + 3.6), z + 6.2, 3.8 - z), x, z) || (x > -5.7 && x < -1.5 && z < -5.4))) || (type === 'forest' && soft(Math.min(z - .2, 1.6 - z), x, z)) || (type === 'playground' && Math.abs(x) < 1.3 && z > -5.3 && z < -2.7);
    for (let i = 0; i < 6; i++) { const h = new THREE.Mesh(G.sph(8 + r() * 6, 24, 12), toon(snow ? '#e8f0fa' : night ? '#24453a' : '#98d07a')); h.position.set(-40 + i * 16, -4, -35 - r() * 10); h.scale.y = .5; g.add(h); }
    if (type === 'yard') { house(g, -3.6, -7, '#f6d7a7', '#d9534f'); fence(g, -4.2, '#e8c48a', -3.6); const pth = plane(1.4, 10, '#d8c3a0'); if (MK3D.hq) pth.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: dirtTex('#d8c3a0', 1, 7), roughness: .95 }); pth.position.set(-3.6, .01, -1.2); g.add(pth); tree(g, 3.6, -6, 1.3); tree(g, 6, -9, 1.1); tree(g, -8.5, -8, 1.2); tree(g, 8.5, -5.5, .9); }
    if (type === 'forest' || type === 'winter') { for (let i = 0; i < 26; i++) { const x = (r() - .5) * 30, z = -3 - r() * 16; if (Math.abs(x) < 1.5 && z > -5) continue; tree(g, x, z, .9 + r() * .6, snow || r() < .4 ? 'fir' : 'round', snow ? '#2f6a4c' : null, snow); }
      if (!snow) { const pth = plane(40, 1.4, '#d9b77a'); if (MK3D.hq) pth.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: dirtTex('#d9b77a', 28, 1), roughness: .95 }); pth.position.set(0, .01, .9); g.add(pth); for (let i = 0; i < 8; i++) { const mx = (r() - .5) * 14, mz = -1.5 - r() * 2; mesh(G.cyl(.04, .05, .14, 8), toon('#f2eadf'), .1, g).position.set(mx, .07, mz); const cp = mesh(new THREE.SphereGeometry(.12, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2), toon('#e8344e'), .08, g); cp.position.set(mx, .13, mz); } } }
    if (type === 'meadow') { for (let i = 0; i < 6; i++) tree(g, (r() - .5) * 34, -10 - r() * 10, 1 + r() * .4); fence(g, -6, '#e8c48a'); }
    if (type === 'playground') { const sw = new THREE.Group(); sw.position.set(-3.5, 0, -2.5); g.add(sw); for (const s of [-1, 1]) { const p = mesh(G.cyl(.06, .06, 2.4, 8), toon('#e8344e'), .05, sw); p.position.set(s * 1.2, 1.2, 0); } mesh(G.cyl(.06, .06, 2.5, 8), toon('#e8344e'), .05, sw).position.y = 2.4; sw.children[2].rotation.z = Math.PI / 2;
      for (const s of [-.5, .5]) { mesh(G.box(.5, .06, .3), toon('#ffd23f'), .05, sw).position.set(s, .6, 0); }
      const sl = new THREE.Group(); sl.position.set(3.5, 0, -2.8); g.add(sl); mesh(G.box(.8, .1, .8), toon('#3d8fe0'), .04, sl).position.y = 1.6; for (const s of [-1, 1]) mesh(G.cyl(.05, .05, 1.6, 8), toon('#2f6fb8'), .05, sl).position.set(s * .35, .8, -.35); const ramp = mesh(G.box(.7, .06, 2.2), toon('#ff8a1f'), .03, sl); ramp.position.set(0, .85, 1.3); ramp.rotation.x = .75;
      const sb = mesh(G.box(2.4, .2, 2.4), toon('#f1d38a'), .03, g); if (MK3D.hq) sb.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: dirtTex('#f1d38a', 1, 1), roughness: .95 }); sb.position.set(0, .1, -4); tree(g, 7, -7, 1.2); tree(g, -7.5, -7, 1.1); }
    if (snow) { const sm = new THREE.Group(); sm.position.set(3.8, 0, -2); g.add(sm); [[.6, .55], [.42, 1.4], [.3, 2.0]].forEach(([rr, y]) => mesh(G.sph(rr, 24, 18), toon('#ffffff'), .03, sm).position.y = y); const nose = mesh(G.cone(.06, .3, 10), toon('#ff8a1f'), .06, sm); nose.rotation.x = Math.PI / 2; nose.position.set(0, 2.0, .35); }
    if (!snow) flowers(g, r, type === 'meadow' ? 180 : 70, -9, 9, -3.5, 3, skipG);
    if (MK3D.hq && !snow) { grassField(g, r, green, skipG); rocksHQ(g, r, 10); }
    for (const [x, z] of [[-6.5, 2.5], [6.5, 2.8], [-8, -1], [8, -1.5]]) bush(g, x, z, 1 + r() * .4, snow ? '#e8f0fa' : night ? '#173a27' : '#3c8f37');
  } else if (type === 'room' || type === 'kitchen') {
    const kit = type === 'kitchen';
    g.add(Object.assign(plane(30, 20, '#ffffff', rep(woodTex(kit ? '#d8c4a0' : '#c88a55'), 6)), {}));
    const wallMap = kit ? rep(tileTex('#f3efe6', 'rgba(120,140,170,.35)', 4), 6) : rep(dotsTex((spec.opts && spec.opts.wall) || '#f7e3c4', 'rgba(214,150,110,.35)'), 6);
    const back = new THREE.Mesh(new THREE.PlaneGeometry(30, 6), toon('#ffffff', wallMap)); back.position.set(0, 3, -3.6); back.receiveShadow = true; g.add(back);
    const side = new THREE.Mesh(new THREE.PlaneGeometry(14, 6), toon('#ffffff', wallMap)); side.position.set(-7.5, 3, 3); side.rotation.y = Math.PI / 2; g.add(side);
    mesh(G.box(30, .2, .1), toon('#8a5a3a'), 0, g).position.set(0, .1, -3.55);
    const win = new THREE.Group(); win.position.set(kit ? 0 : 2.2, 2.3, -3.55); g.add(win); const sky = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.8), basic(SKY[time] ? SKY[time][1] : '#cfeaff')); sky.position.z = .01; win.add(sky);
    for (const [w, h, x, y] of [[2.4, .14, 0, .95], [2.4, .14, 0, -.95], [.14, 2, -1.15, 0], [.14, 2, 1.15, 0], [.08, 1.8, 0, 0], [2.2, .08, 0, 0]]) mesh(G.box(w, h, .08), toon('#ffffff'), .04, win).position.set(x, y, .05);
    for (const s of [-1, 1]) mesh(G.box(.5, 2.4, .08), toon(kit ? '#9ad0c2' : '#e86a5f'), .03, win).position.set(s * 1.45, -.05, .1);
    if (kit) { const cnt = new THREE.Group(); cnt.position.set(-4, 0, -3.1); g.add(cnt); mesh(G.box(5, .95, .9), toon('#7fc4a4'), .02, cnt).position.y = .475; mesh(G.box(5.1, .08, 1), toon('#d9c7a8'), .02, cnt).position.y = .99; mesh(G.box(5, .8, .5), toon('#7fc4a4'), .02, cnt).position.set(0, 2.6, -.2);
      const fr = mesh(G.box(1.1, 2.4, .9), toon('#fafafa'), .02, g); fr.position.set(5.3, 1.2, -3); const tb = new THREE.Group(); tb.position.set(4, 0, -1.4); g.add(tb); mesh(G.cyl(.9, .9, .08, 28), toon('#c88a55'), .03, tb).position.y = .78; mesh(G.cyl(.08, .12, .78, 10), toon('#8a5a3a'), .05, tb).position.y = .39; }
    else { const sofa = new THREE.Group(); sofa.position.set(5, 0, -2.8); g.add(sofa); mesh(G.box(3, .5, 1), toon('#5f9e8f'), .03, sofa).position.y = .35; mesh(G.box(3, .8, .3), toon('#5f9e8f'), .03, sofa).position.set(0, .8, -.4); for (const s of [-1, 1]) mesh(G.box(.3, .6, 1), toon('#5f9e8f'), .03, sofa).position.set(s * 1.5, .5, 0);
      const rug = new THREE.Mesh(G.cyl(2.2, 2.2, .02, 40), toon('#4e7fc9')); rug.position.set(0, .01, .2); rug.receiveShadow = true; g.add(rug);
      const sh = new THREE.Group(); sh.position.set(-4, 2.2, -3.45); g.add(sh); mesh(G.box(2, .08, .3), toon('#8a5a3a'), .03, sh); for (let i = 0; i < 7; i++) mesh(G.box(.2, .45 + (i % 3) * .08, .25), toon(['#e8344e', '#3d8fe0', '#ffd23f', '#5fbf4a'][i % 4]), .04, sh).position.set(-.8 + i * .26, .27, 0);
      const pl = new THREE.Group(); pl.position.set(-6.3, 0, -2.6); g.add(pl); mesh(G.cyl(.3, .22, .5, 12), toon('#c96'), .04, pl).position.y = .25; for (let i = 0; i < 6; i++) { const l = mesh(G.sph(.25, 10, 8), toon('#4fa63f'), .04, pl); l.position.set(Math.cos(i) * .25, .75 + (i % 2) * .2, Math.sin(i) * .25); l.scale.set(.6, 1.3, .4); } }
  } else if (type === 'street') {
    g.add(plane(120, 120, '#c9c4bb')); const road = plane(120, 5, '#4a4a50'); road.position.set(0, .01, 5.2); g.add(road); for (let x = -40; x < 40; x += 3) { const l = plane(1.4, .15, '#ffffff'); l.position.set(x, .02, 5.2); g.add(l); }
    const cols = ['#e86a5f', '#f2c94c', '#7fc4a4', '#8d7ad9', '#f29e4c', '#5fa8e8']; let x = -22;
    while (x < 22) { const w = 3 + r() * 2, h = 4 + r() * 5, cl = cols[(r() * cols.length) | 0]; const b = new THREE.Group(); b.position.set(x + w / 2, 0, -5.5); g.add(b); mesh(G.box(w - .1, h, 3), toon(cl), .01, b).position.y = h / 2;
      for (let yy = 1.4; yy < h - .6; yy += 1.2) for (let xx = -w / 2 + .6; xx < w / 2 - .4; xx += .9) mesh(G.box(.5, .7, .05), toon(night && r() < .6 ? '#ffe28a' : '#cfeaff'), .05, b).position.set(xx, yy, 1.52); mesh(G.box(.8, 1.4, .05), toon('#5a3a2a'), .04, b).position.set(0, .7, 1.52); x += w; }
    for (let i = -2; i <= 2; i++) { const lp = new THREE.Group(); lp.position.set(i * 5 + 2.5, 0, -3.3); g.add(lp); mesh(G.cyl(.06, .08, 3.2, 8), toon('#3a3f4a'), .04, lp).position.y = 1.6; const lmp = mesh(G.sph(.18, 12, 10), toon(night ? '#fff2a8' : '#eeeeee'), .05, lp); lmp.position.y = 3.25; if (night) { const pl = new THREE.PointLight(0xfff2a8, 3, 6); pl.position.y = 3; lp.add(pl); } }
  } else if (type === 'beach') {
    g.add(plane(120, 60, '#f0d38f')); const sea = new THREE.Mesh(new THREE.PlaneGeometry(200, 80), new THREE.MeshToonMaterial({ color: night ? 0x173a6a : 0x2f8fd6, gradientMap: grad })); sea.rotation.x = -Math.PI / 2; sea.position.set(0, .02, -44); g.add(sea); g.userData.sea = sea;
    const isl = new THREE.Mesh(G.sph(6, 24, 12), toon('#7cc06a')); isl.position.set(20, -3.5, -60); isl.scale.y = .6; g.add(isl);
    const palm = new THREE.Group(); palm.position.set(5.5, 0, -2.5); g.add(palm); for (let i = 0; i < 8; i++) { const sgm = mesh(G.cyl(.16 - i * .01, .18 - i * .01, .5, 10), toon('#8a5a3a'), .03, palm); sgm.position.set(Math.sin(i * .25) * i * .08, .25 + i * .48, 0); } for (let i = 0; i < 6; i++) { const l = mesh(G.sph(.9, 12, 8), toon('#3f9a3a'), .02, palm); l.scale.set(1.4, .12, .4); const a = i / 6 * Math.PI * 2; l.position.set(.5 + Math.cos(a) * .9, 3.9, Math.sin(a) * .9); l.rotation.y = -a; l.rotation.z = -.3; }
    const um = new THREE.Group(); um.position.set(-4.5, 0, -1.8); g.add(um); mesh(G.cyl(.04, .04, 2.6, 8), toon('#6b4a32'), .05, um).position.y = 1.3; const top = mesh(G.cone(1.5, .7, 12), toon(null, canvasTex(256, 16, (c) => { for (let i = 0; i < 12; i++) { c.fillStyle = i % 2 ? '#ffffff' : '#e8344e'; c.fillRect(i * 256 / 12, 0, 256 / 12 + 1, 16); } })), .03, um); top.position.y = 2.7;
    for (let i = 0; i < 10; i++) { const sh = new THREE.Mesh(G.sph(.07, 8, 6), toon(['#ff9fb2', '#ffffff', '#ffd23f'][i % 3])); sh.position.set((r() - .5) * 14, .03, (r() - .5) * 5); sh.scale.y = .5; g.add(sh); }
  } else if (type === 'space') {
    const gr = plane(120, 120, '#9a9aa8'); g.add(gr); for (let i = 0; i < 18; i++) { const c = new THREE.Mesh(G.cyl(.5 + r() * 1.2, .7 + r() * 1.3, .12, 20), toon('#b4b4c0')); c.position.set((r() - .5) * 30, .03, -2 - r() * 18); c.receiveShadow = true; g.add(c); }
    const pl = new THREE.Mesh(G.sph(6, 32, 24), toon('#d9673a')); pl.position.set(18, 14, -60); g.add(pl); const ring = new THREE.Mesh(G.tor(10, .4), basic('#ffe0b0')); ring.position.copy(pl.position); ring.rotation.x = 1.2; g.add(ring);
    const sm = new THREE.Mesh(G.sph(2, 24, 16), toon('#8fd0ff')); sm.position.set(-20, 12, -55); g.add(sm);
    const rk = new THREE.Group(); rk.position.set(-5.5, 0, -3); g.add(rk); mesh(G.cap(.55, 2.2), toon('#eeeeee'), .03, rk).position.y = 1.7; const nz = mesh(G.cone(.55, .9, 20), toon('#e8344e'), .03, rk); nz.position.y = 3.45; const wd = mesh(G.sph(.22, 16, 12), toon('#7fd0ff'), .06, rk); wd.position.set(0, 2.1, .5); for (let i = 0; i < 3; i++) { const fn = mesh(G.box(.06, .8, .6), toon('#e8344e'), .04, rk); const a = i / 3 * Math.PI * 2; fn.position.set(Math.cos(a) * .55, .45, Math.sin(a) * .55); fn.rotation.y = -a; }
    const pts = new Float32Array(1500 * 3); for (let i = 0; i < 1500; i++) { const th = r() * Math.PI * 2, ph = r() * Math.PI * .45; pts[i * 3] = Math.cos(th) * Math.cos(ph) * 90; pts[i * 3 + 1] = Math.sin(ph) * 90 + 3; pts[i * 3 + 2] = Math.sin(th) * Math.cos(ph) * 90; } const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(pts, 3)); g.add(new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: .25 })));
  }
  if (night && type !== 'space' && type !== 'room' && type !== 'kitchen') { const pts = new Float32Array(600 * 3); for (let i = 0; i < 600; i++) { const th = r() * Math.PI, ph = .15 + r() * Math.PI * .4; pts[i * 3] = Math.cos(th) * 80; pts[i * 3 + 1] = Math.sin(ph) * 60 + 8; pts[i * 3 + 2] = -Math.abs(Math.sin(th) * 80) - 10; } const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(pts, 3)); g.add(new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: .3 }))); const moon = new THREE.Mesh(G.sph(3, 24, 16), basic('#fff6c8')); moon.position.set(25, 30, -70); g.add(moon); }
  // облака
  if (!['space', 'room', 'kitchen'].includes(type) && !night) { g.userData.clouds = []; for (let i = 0; i < 6; i++) { const cg = new THREE.Group(); for (let k = 0; k < 5; k++) { const c = new THREE.Mesh(G.sph(.9 + r() * .7, 16, 12), toon(time === 'evening' ? '#ffd6d6' : '#ffffff')); c.position.set(k * 1.1 - 2.2, (r() - .5) * .6, 0); cg.add(c); } cg.position.set(-30 + i * 12, 9 + r() * 4, -30 - r() * 8); g.add(cg); g.userData.clouds.push(cg); } }
  // погода
  const weather = spec.weather || (type === 'winter' ? 'snow' : 'none');
  if (weather === 'rain' || weather === 'snow') { const N = weather === 'rain' ? 900 : 700, pts = new Float32Array(N * 3), seeds = []; for (let i = 0; i < N; i++) seeds.push([(r() - .5) * 26, r() * 12, -8 + r() * 14, .6 + r() * .4]); const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pts, 3));
    const pm = new THREE.Points(pg, new THREE.PointsMaterial({ color: weather === 'rain' ? 0xbcd4ff : 0xffffff, size: weather === 'rain' ? .06 : .09, transparent: true, opacity: .9 })); g.add(pm); g.userData.weather = { pm, seeds, rain: weather === 'rain' }; }
  g.userData.type = type; g.userData.time = time; g.userData.weather0 = weather;
  g.traverse(o => { if (o.isMesh && o.castShadow === false && !o.material.isMeshBasicMaterial) { o.castShadow = true; } });
  return g;
}
function animateLoc(g, T) { windU.value = T;
  if (g.userData.clouds) g.userData.clouds.forEach((c, i) => c.position.x = -30 + i * 12 + ((T * .4) % 12));
  const w = g.userData.weather; if (w) { const a = w.pm.geometry.attributes.position.array; w.seeds.forEach((s, i) => { const sp = w.rain ? 9 : 1.1; let y = 12 - ((s[1] + T * sp * s[3]) % 12); a[i * 3] = s[0] + (w.rain ? 0 : Math.sin(T + i) * .3); a[i * 3 + 1] = y; a[i * 3 + 2] = s[2]; }); w.pm.geometry.attributes.position.needsUpdate = true; }
  if (g.userData.sea) g.userData.sea.position.y = .02 + Math.sin(T * 1.5) * .02;
}
function lightFor(type, time) { lightBase(type, time); if (MK3D.hq) { hemi.intensity *= .35; sun.intensity *= 1.25; if (rim) { rim.intensity = time === 'night' || type === 'space' ? 1.8 : 1.3; rim.color.set(time === 'night' || type === 'space' ? 0xc8d4ff : 0xfff4e6); } } }
function lightBase(type, time) { // свет всегда почти белый: герой выглядит одинаково днём, вечером и ночью; настроение даёт небо
  const night = time === 'night', eve = time === 'evening', indoor = type === 'room' || type === 'kitchen';
  hemi.groundColor.set(0x8a8a80);
  if (type === 'space') { hemi.color.set(0xf0f2ff); hemi.intensity = 1.15; sun.color.set(0xffffff); sun.intensity = 2.2; sun.position.set(6, 9, 5); return; }
  if (indoor) { hemi.color.set(0xfffcf6); hemi.intensity = 1.2; sun.color.set(0xffffff); sun.intensity = night ? 1.7 : 1.9; sun.position.set(2, 7, 6); return; }
  if (night) { hemi.color.set(0xe6ebff); hemi.intensity = 1.05; sun.color.set(0xf0f3ff); sun.intensity = 1.8; sun.position.set(-5, 8, 5); return; }
  if (eve) { hemi.color.set(0xfffaf4); hemi.intensity = 1.1; sun.color.set(0xfff6ec); sun.intensity = 2.0; sun.position.set(-6, 6, 6); return; }
  hemi.color.set(0xf4f8ff); hemi.intensity = 1.15; sun.color.set(0xffffff); sun.intensity = 2.2; sun.position.set(4, 8, 6);
}

// ---------- камера ----------
function camFor(c, S, seg, lib) {
  const h = id => { const lc = lib.characters[id]; return lc ? (lc.spec.height || 1) * (lc.spec.kind === 'human' && (lc.spec.age === 'adult' || lc.spec.age === 'old') ? 1.4 : 1) : 1; };
  const px = id => S[id] ? X(S[id].x) : 0, pz = id => S[id] ? -(S[id].z || 0) * 1.5 : 0;
  const ids = Object.keys(seg.C);
  if (c.mode === 'close' || c.mode === 'medium') { const id = c.on || ids[0], hh = h(id), x = px(id), z = pz(id); const close = c.mode === 'close';
    return { pos: new THREE.Vector3(x + (close ? .15 : .4), (close ? .95 : 1.1) * hh + .1, z + (close ? 2.3 : 3.8) * Math.max(.8, hh) / (c.zoom ? c.zoom / (close ? 2.3 : 1.55) : 1)), look: new THREE.Vector3(x, (close ? .92 : .75) * hh, z) }; }
  if (c.mode === 'two') { const pair = Array.isArray(c.on) ? c.on : ids.slice(0, 2); const a = px(pair[0]), b = px(pair[1] || pair[0]), mid = (a + b) / 2, d = Math.abs(a - b), hh = Math.max(h(pair[0]), h(pair[1] || pair[0]));
    return { pos: new THREE.Vector3(mid, 1.15 * hh + .15, Math.max(3.3, d * 1.05 + 2.3)), look: new THREE.Vector3(mid, .72 * hh, 0) }; }
  if (c.mode === 'pan') { const x = X(c.on != null ? +c.on : .5); return { pos: new THREE.Vector3(x, 1.5, 6 / (c.zoom || 1.3) * 1.3), look: new THREE.Vector3(x, .8, 0) }; }
  return { pos: new THREE.Vector3(0, 1.75, 8.4), look: new THREE.Vector3(0, .85, 0) };
}

// ---------- кадр ----------
let curLoc = null;
function showLoc(key, spec) { let g = locCache[key]; if (!g) { g = buildLoc(spec); locCache[key] = g; scene.add(g); } if (curLoc && curLoc !== g) curLoc.visible = false; g.visible = true; curLoc = g; return g; }
function hideAllRigs() { if (curTheme) curTheme.visible = false; for (const k in rigCache) rigCache[k].root.visible = false; for (const k in propCache) propCache[k].visible = false; for (let i = 0; i < spriteUsed; i++) spritePool[i].visible = false; spriteUsed = 0; }
function ensureIn(obj) { if (obj.parent !== scene) scene.add(obj); }
function render(ctx) {
  const w = ctx.canvas.width, h = ctx.canvas.height;
  const ss = MK3D.hq ? 2 : 1; // «как в кино»: считаем кадр вдвое крупнее и уменьшаем — тонкие волоски получаются гладкими
  if (GL.width !== w * ss || GL.height !== h * ss) { GL.width = w * ss; GL.height = h * ss; R.setSize(w * ss, h * ss, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
  if (MK3D.hq) { scene.updateMatrixWorld(true); for (const k in rigCache) { const rg = rigCache[k]; if (rg.root.visible && rg.fur) furFrame(rg, MK3D._T || 0); } }
  R.render(scene, cam);
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high'; ctx.drawImage(GL, 0, 0, w, h); ctx.restore();
}
MK3D.draw = function (ctx, tl, seg, t, T) {
  hideAllRigs();
  if (seg.kind === 'title' || seg.kind === 'end') return drawCard3D(ctx, tl, seg, t, T);
  const L = seg.lspec || {}; const g = showLoc(seg.lkey, L); animateLoc(g, T);
  scene.background = skyTex(L.time || 'day', L.type); scene.fog = ['room', 'kitchen', 'space'].includes(L.type) ? null : new THREE.Fog(new THREE.Color(SKY[L.time || 'day'][1]), 18, 70);
  lightFor(L.type, L.time || 'day');
  const S = global.MK._sceneState(tl, seg, t, T);
  for (const id in S) {
    const st = S[id], lc = tl.lib.characters[id]; if (!lc || !st.vis) continue;
    const rig = rigFor(lc); ensureIn(rig.root); rig.root.visible = true;
    rig.root.position.set(X(st.x), 0, -(st.z || 0) * 1.5);
    rig.yaw.rotation.y = st.face * (st.walk && st.walk.on ? 1.35 : .72);
    const held = seg.props.find(p => p._holder === id && p._vis !== false); st.prop = held || null;
    applyPose(rig, st, T); fxFor(rig, st, T); rig._held = held; rig._needFur = true;
  }
  scene.updateMatrixWorld(true);
  for (const p of seg.props) { const m = propMesh(p); ensureIn(m); const fa = p._fxAge;
    let sc = 1; if (!p._vis) { if (p._fx === 'vanish' && fa < .45) sc = 1 - ease(fa / .45); else { m.visible = false; poof(p, fa); continue; } } else if (p._fx === 'appear' && fa < .6) sc = ease(fa / .6) * (1 + Math.sin(Math.min(1, fa / .6) * Math.PI) * .25);
    m.visible = sc > .01; const big = p.big || 1;
    if (p._holder && S[p._holder] && S[p._holder].vis) { const lc = tl.lib.characters[p._holder]; const rig = rigFor(lc); const v = new THREE.Vector3(); rig.hand.getWorldPosition(v); m.position.set(v.x, v.y - .12 * rig.scale, v.z); m.scale.setScalar(.7 * rig.scale * sc); }
    else { const zz = p.decor && big > 1.5 ? -1.9 : p.decor ? -.5 : .35; m.position.set(X(p._x), (p._air || 0) * 1.2 + (m.userData.float ? Math.sin(T * 2 + p._x * 9) * .08 : 0), zz); m.scale.setScalar(big * (p.decor && big < 1.5 ? 1.6 : 1) * sc); m.rotation.z = -(p._air || 0) * 3; }
    const gl = m.userData.alwaysGlow ? 1 : (p._glow || 0); if (m.userData.faceMat) m.userData.faceMat.color.set(gl > 0 ? 0xffc23a : 0x3a1a08);
    if (gl > 0 && m.visible) { const gy = m.userData.glowY != null ? m.userData.glowY : .2, gs = (m.userData.glowS || .7) * m.scale.x, pulse = 1 + Math.sin(T * 3 + p._x * 7) * .06;
      sprite(haloTex(m.userData.glowC || '#ffe27a'), m.position.x, m.position.y + gy * m.scale.x, m.position.z + .05, gs * pulse * (.5 + gl * .5), .75 * gl);
      if (!m.userData.alwaysGlow) for (let i = 0; i < 3; i++) { const q = (T * .5 + i / 3) % 1; sprite(glyphTex('✦', '#fff4b0'), m.position.x + Math.sin(i * 2.3 + T) * gs * .45, m.position.y + gy * m.scale.x + (q - .3) * gs * .7, m.position.z + .2, .12 * Math.max(1, m.scale.x * .5), Math.sin(q * Math.PI) * gl); } }
    if (p._fx === 'appear' && fa < 1.1) for (let i = 0; i < 10; i++) { const a = i / 10 * Math.PI * 2, r = .2 + fa * 1.1 * Math.max(1, big * .6); sprite(glyphTex('★', '#ffd23f', '#ffffff'), m.position.x + Math.cos(a) * r, m.position.y + .3 * big + Math.sin(a) * r, m.position.z + .3, .16, 1 - fa / 1.1); }
    if (p._fx === 'vanish' && fa < 1.1) poof(p, fa, m);
  }
  function poof(p, fa, m) { if (fa > 1.1 || p._fx !== 'vanish') return; const x = m ? m.position.x : X(p._x), y = m ? m.position.y + .25 * (p.big || 1) : .3, z = m ? m.position.z + .3 : .4;
    for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2, r = .15 + fa * .7 * Math.max(1, (p.big || 1) * .6); sprite(haloTex('#ffffff'), x + Math.cos(a) * r, y + Math.sin(a) * r * .7, z, (.35 + fa * .4) * Math.max(1, (p.big || 1) * .5), (1 - fa / 1.1) * .9); } }
  showTheme(seg, T);
  // камера
  let ci = 0; const cams = seg.cam.filter(c => !c.shake); for (let i = 0; i < cams.length; i++) if (cams[i].t <= t) ci = i;
  const cur = camFor(cams[ci], S, seg, tl.lib), prev = ci > 0 ? camFor(cams[ci - 1], S, seg, tl.lib) : cur, k = ease((t - cams[ci].t) / .9);
  cam.position.lerpVectors(prev.pos, cur.pos, k); const look = new THREE.Vector3().lerpVectors(prev.look, cur.look, k);
  for (const c of seg.cam) if (c.shake && t >= c.t && t < c.t + c.shake) { const a = (1 - (t - c.t) / c.shake) * .08; cam.position.x += Math.sin(t * 61) * a; cam.position.y += Math.cos(t * 53) * a; }
  cam.fov = 38; cam.updateProjectionMatrix(); cam.lookAt(look);
  sun.target.position.copy(look); sun.position.add(look); MK3D._T = t; if (rim) { rim.target.position.copy(look); rim.position.set(look.x - 3, 4, look.z - 6); }
  render(ctx);
};
function drawCard3D(ctx, tl, seg, t, T) { MK3D._T = t + 1000;
  const title = seg.kind === 'title';
  if (curLoc) curLoc.visible = false;
  scene.background = canvasTex(4, 256, (g) => { const gr = g.createLinearGradient(0, 0, 0, 256); gr.addColorStop(0, title ? '#ff9a5c' : '#5a6fd8'); gr.addColorStop(1, title ? '#ffd56b' : '#9ad0ff'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); }); scene.fog = null;
  lightFor('meadow', 'day');
  let st0 = locCache['__stage']; if (!st0) { st0 = new THREE.Group(); const p = new THREE.Mesh(G.cyl(3.4, 3.6, .3, 48), toon('#fff4e0')); p.position.y = -.15; p.receiveShadow = true; st0.add(p); scene.add(st0); locCache['__stage'] = st0; } st0.visible = true; curLoc = st0;
  const ids = global.MK._cardCast(tl);
  ids.forEach((id, i) => { const lc = tl.lib.characters[id]; if (!lc) return; const rig = rigFor(lc); ensureIn(rig.root); rig.root.visible = true; const x = (i - (ids.length - 1) / 2) * 1.25, appear = ease((t - .4 - i * .15) / .5);
    rig.root.position.set(x, -(1 - appear) * 3, 0); rig.yaw.rotation.y = 0;
    applyPose(rig, { x: 0, face: 0, emo: 'happy', act: { n: i % 2 ? 'wave' : 'jump', p: ((t * .7 + i * .3) % 1), t: t + i }, walk: {}, talk: 0, persist: 'none' }, T); });
  cam.fov = 40; cam.position.set(0, 1.25, 6.2); cam.updateProjectionMatrix(); cam.lookAt(0, 1.55, 0); sun.position.set(4, 8, 6); sun.target.position.set(0, 0, 0);
  render(ctx);
}
MK3D.portrait = function (canvas, spec, T, opts) {
  if (!MK3D.ready) return false; hideAllRigs();
  if (curLoc) curLoc.visible = false;
  scene.background = canvasTex(4, 64, (g) => { const gr = g.createLinearGradient(0, 0, 0, 64); gr.addColorStop(0, '#cdeeff'); gr.addColorStop(1, '#a8e08a'); g.fillStyle = gr; g.fillRect(0, 0, 4, 64); }); scene.fog = null; lightFor('meadow', 'day');
  const key = 'pt:' + global.MK.canon(spec); let rig = rigCache[key]; if (!rig) { rig = buildRig(spec); rigCache[key] = rig; }
  ensureIn(rig.root); rig.root.visible = true; rig.root.position.set(0, 0, 0); rig.yaw.rotation.y = Math.sin((T || 0) * .4) * .5 + .2;
  applyPose(rig, opts && opts.state || { x: 0, face: 0, emo: 'happy', act: { n: 'wave', p: .3, t: T || 1.2 }, walk: {}, talk: 0, persist: 'none' }, T || 1.2);
  const hh = (spec.height || 1) * (spec.kind === 'human' && spec.age !== 'kid' ? 1.45 : 1.15);
  cam.fov = 30; cam.aspect = canvas.width / canvas.height; cam.position.set(0, hh * .6, hh * 3.4); cam.updateProjectionMatrix(); cam.lookAt(0, hh * .5, 0); sun.position.set(3, 6, 6); sun.target.position.set(0, 0, 0);
  const ctx = canvas.getContext('2d'); render(ctx); rig.root.visible = false; return true;
};
MK3D.locPreview = function (canvas, spec, T) {
  if (!MK3D.ready) return false; hideAllRigs(); const key = global.MK.canon(spec); const g = showLoc(key, spec); animateLoc(g, T || 2);
  scene.background = skyTex(spec.time || 'day', spec.type); scene.fog = null; lightFor(spec.type, spec.time || 'day');
  cam.fov = 38; cam.position.set(0, 2.1, 10.5); cam.updateProjectionMatrix(); cam.lookAt(0, .95, 0); sun.target.position.set(0, 0, 0);
  render(canvas.getContext('2d')); return true;
};
MK3D.propPreview = function (canvas, types) {
  if (!MK3D.ready) return false; hideAllRigs(); if (curLoc) curLoc.visible = false; scene.fog = null; scene.background = col('#dff3ff'); lightFor('meadow', 'day');
  const grp = new THREE.Group(); scene.add(grp); const n = types.length, cols = Math.ceil(Math.sqrt(n * 1.8));
  types.forEach((ty, i) => { const pm = propMesh({ id: 'pv' + i, type: ty }).clone(); pm.position.set((i % cols - (cols - 1) / 2) * .62, 0, Math.floor(i / cols) * -.7); grp.add(pm); });
  cam.fov = 30; cam.aspect = canvas.width / canvas.height; cam.position.set(0, 2.6, 4.4); cam.updateProjectionMatrix(); cam.lookAt(0, .1, -1); sun.position.set(3, 6, 6);
  render(canvas.getContext('2d')); scene.remove(grp); return true;
};
global.MK3D = MK3D;
})(typeof window !== 'undefined' ? window : globalThis);
