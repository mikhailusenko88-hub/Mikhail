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
  // iPhone может отобрать видеокарту у свёрнутого приложения: пока её нет, кадры не рисуем (сборка ждёт)
  GL.addEventListener('webglcontextlost', () => { MK3D._lost = true; }, false);
  GL.addEventListener('webglcontextrestored', () => { MK3D._lost = false; R.shadowMap.needsUpdate = true; }, false);
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
  const env = canvasTex(512, 256, (g) => { g.scale(2, 2); const gr = g.createLinearGradient(0, 0, 0, 128); gr.addColorStop(0, '#dfeaff'); gr.addColorStop(.48, '#ffffff'); gr.addColorStop(.52, '#d8d2c4'); gr.addColorStop(1, '#8a8478'); g.fillStyle = gr; g.fillRect(0, 0, 256, 128);
    const sp = g.createRadialGradient(70, 30, 2, 70, 30, 30); sp.addColorStop(0, 'rgba(255,255,255,1)'); sp.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = sp; g.fillRect(0, 0, 256, 128); });
  env.mapping = THREE.EquirectangularReflectionMapping; const pm = new THREE.PMREMGenerator(R); scene.environment = pm.fromEquirectangular(env).texture; scene.userData.env = scene.environment; scene.environmentIntensity = .45; pm.dispose();
  rim = new THREE.DirectionalLight(0xffffff, 1.4); rim.position.set(-3, 4, -6); scene.add(rim); scene.add(rim.target);
}
let hqReady = false;
MK3D.lost = function () { try { return !!MK3D._lost || !!(R && R.getContext().isContextLost()); } catch (e) { return true; } };
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
  sph: (r, w, h, ...rest) => new THREE.SphereGeometry(r, w || 32, h || 24, ...rest),
  cap: (r, l, cs, rs) => new THREE.CapsuleGeometry(r, l, cs || 8, rs || 16),
  cone: (r, h, s) => new THREE.ConeGeometry(r, h, s || 24),
  cyl: (a, b, h, s, open) => new THREE.CylinderGeometry(a, b, h, s || 24, 1, !!open),
  box: (x, y, z) => new THREE.BoxGeometry(x, y, z),
  tor: (r, t, a, b, c) => b === undefined ? new THREE.TorusGeometry(r, t, 12, 32, a || Math.PI * 2) : new THREE.TorusGeometry(r, t, a, b, c || Math.PI * 2),
};
function canvasTex(w, h, draw) { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; }
function stripeTex(base, stripe, n, y0, y1) { return canvasTex(256, 128, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 128); g.fillStyle = stripe; for (let i = 0; i < n; i++) { const x = i * 256 / n + 10, m = (y0 + y1) / 2; g.beginPath(); g.moveTo(x + 4, y0); g.quadraticCurveTo(x + 12, m, x + 5, y1); g.lineTo(x + 9, y1); g.quadraticCurveTo(x + 20, m, x + 12, y0); g.fill(); } }); }
function spotTex(base, spot, seed) { return canvasTex(256, 128, (g) => { g.fillStyle = base; g.fillRect(0, 0, 256, 128); g.fillStyle = spot; const r = rng(seed); for (let i = 0; i < 14; i++) { g.beginPath(); g.ellipse(r() * 256, 20 + r() * 88, 8 + r() * 10, 6 + r() * 8, 0, 0, 7); g.fill(); } }); }

// ---------- персонаж ----------
const rigCache = {};
MK3D.rigs = () => rigCache; // для проверок
// Опорные точки тела: у каждой детали — крайние точки по 98 направлениям. По ним в любой позе (сидит, лежит, упал,
// кувыркается) находим самую нижнюю точку героя и ставим его на землю — сквозь пол и песок больше не проваливается.
const SUP_DIRS = (() => { const a = [], n = 98; for (let i = 0; i < n; i++) { const y = 1 - (i + .5) / n * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963; a.push([Math.cos(th) * r, y, Math.sin(th) * r]); } return a; })();
function groundPts(rig) {
  const list = [], skip = new Set(); if (rig.blob) skip.add(rig.blob);
  rig.root.traverse(o => { if (o.userData.strands || o.userData.groove || o.userData.carve || o.userData.noGround) o.traverse(c => skip.add(c)); });
  if (rig.tail) rig.tail.traverse(c => skip.add(c)); // хвост может лечь на пол — героя из-за него не поднимаем
  rig.root.traverse(o => {
    if (!o.isMesh || o.isInstancedMesh || skip.has(o) || o.material === OL || !o.geometry || !o.geometry.attributes.position) return;
    for (let v = o; v; v = v.parent) if (!v.visible) return;
    const pa = o.geometry.attributes.position, n = pa.count, st = Math.max(1, Math.floor(n / 6000)), idx = new Set();
    for (const d of SUP_DIRS) { let best = 0, bv = -Infinity; for (let i = 0; i < n; i += st) { const q = pa.getX(i) * d[0] + pa.getY(i) * d[1] + pa.getZ(i) * d[2]; if (q > bv) { bv = q; best = i; } } idx.add(best); }
    const pts = new Float32Array(idx.size * 3); let k = 0; for (const i of idx) { pts[k++] = pa.getX(i); pts[k++] = pa.getY(i); pts[k++] = pa.getZ(i); }
    list.push({ o, pts }); });
  return list;
}
/** Самая нижняя точка героя относительно его «земли» (в размерах героя). */
function lowPoint(rig) {
  const gp = rig._gp || (rig._gp = groundPts(rig)); let mn = Infinity;
  rig.root.updateMatrixWorld(true);
  for (const g of gp) { if (!g.o.visible) continue; const e = g.o.matrixWorld.elements, p = g.pts;
    for (let i = 0; i < p.length; i += 3) { const y = e[1] * p[i] + e[5] * p[i + 1] + e[9] * p[i + 2] + e[13]; if (y < mn) mn = y; } }
  return mn === Infinity ? 0 : (mn - rig.root.position.y) / (rig.scale || 1);
}
/** w = 0 — стоит/идёт: только не даём уйти под землю; w = 1 — сидит/лежит: ровно касается земли. */
function groundFix(rig, w) {
  rig.yaw.position.y = 0; const rel = lowPoint(rig);
  const lift = Math.max(0, -.015 - rel), touch = -.006 - rel;
  rig.yaw.position.y = lerp(lift, touch, clamp(w, 0, 1)); rig._low = rel;
}
function buildRig(spec) { inRig = true; try { const r = buildRig0(spec); try { sculptRig(r); } catch (e) { console.log('скульптор:', e && e.message); } if (MK3D.hq) addFur(r); return r; } finally { inRig = false; } }
// ---------- «Скульптор»: голова, тело, лапы и хвост — одна плавная поверхность вместо набора шаров ----------
// Берём те же формы, из которых собран герой (поэтому он остаётся узнаваемым), и сливаем их в «глину»:
// щёки перетекают в мордочку, пузико в тело, лапка в ладошку; цвет на стыках мягкий; полоски — по форме;
// мягкие тени в складках считаются один раз и запекаются в цвет. Всё — один раз на героя, потом из кэша.
let sculptM = null;
// рисунок (полоски, пятна) — прямо в шейдере по форме: чёткий край при любом приближении
const PAT_GLSL = `uniform float uMode; uniform float uN; uniform vec3 uRatio; varying vec4 vPat; varying vec3 vColB; varying float vMix;
float patW(vec4 P){
  if (P.w < .5 || uMode < .5) return 0.;
  if (uMode > 2.5 && uMode < 3.5) { float t = P.x * uN + .15, f = fract(t), aa = min(fwidth(t) * .8, .05); return smoothstep(.05 - aa, .1 + aa, f) * (1. - smoothstep(.36 - aa, .42 + aa, f)); }
  vec3 q = P.xyz; float lon = atan(q.x, q.z), lat = q.y, wob = sin(lat * 5.3 + uN) * .045 + sin(lat * 11.7) * .015;
  if (uMode < 1.5) { float t = lon / 6.28318 * uN + wob * 1.6, f = fract(t), aa = min(fwidth(t) * .7, .05); return (1. - smoothstep(.6, .85, abs(lat))) * smoothstep(0., .04 + aa, f) * (1. - smoothstep(.28 - aa, .35 + aa, f)); }
  if (uMode < 2.5) { float t = lon / 6.28318 * uN + .5 + wob, f = fract(t), aa = min(fwidth(t) * .7, .05); return smoothstep(.12, .34, lat) * smoothstep(0., .04 + aa, f) * (1. - smoothstep(.26 - aa, .33 + aa, f)); }
  float h = sin(q.x * 9.1 + q.y * 3.7) * sin(q.y * 8.3 - q.z * 5.1) * sin(q.z * 7.7 + q.x * 2.9); return smoothstep(.18, .3, h); }
`;
const SSS_FRAG = `#include <lights_fragment_end>
  #if NUM_DIR_LIGHTS > 0
  { vec3 nS = normal; float thk = exp(-clamp(vThick, 0.0, 1.0) * 26.0);
    for (int i = 0; i < NUM_DIR_LIGHTS; i++) { vec3 Ld = directionalLights[i].direction, Lc = directionalLights[i].color; float nl = dot(nS, Ld);
      float wrap = max(0., (nl + .45) / 1.45) - max(0., nl); // свет «затекает» за границу тени — мягкая тёплая кромка
      float tr = pow(max(0., dot(geometryViewDir, -normalize(Ld + nS * .3))), 3.0) * thk; // свет насквозь (уши на просвет)
      reflectedLight.directDiffuse += Lc * diffuseColor.rgb * uSss * (wrap * .32 + tr * 1.6); } }
  #endif`;
const SCULPT_FRAG = `#include <color_fragment>
  { float aw = max(fwidth(vMix) * .75, 1e-6), tm = smoothstep(-aw, aw, vMix); // граница цвета — на каждом пикселе
    diffuseColor.rgb = mix(diffuseColor.rgb, vColB, tm);
    float pw = vPat.w > 1.5 ? 1. - tm : 1.; diffuseColor.rgb *= mix(vec3(1.0), uRatio, patW(vPat) * pw); }`;
function sculptMat(pat) { const k = (MK3D.hq ? 'hq' : 'std') + (pat ? ':' + pat.mode + ':' + pat.n + ':' + pat.ratio.join(',') : ''); sculptM = sculptM || {}; if (sculptM[k]) return sculptM[k];
  const m = MK3D.hq ? new THREE.MeshPhysicalMaterial({ color: 0xffffff, vertexColors: true, roughness: .62, metalness: 0, sheen: .55, sheenRoughness: .35, sheenColor: new THREE.Color(1, .95, .9), envMapIntensity: .8 })
    : new THREE.MeshToonMaterial({ color: 0xffffff, vertexColors: true, gradientMap: grad });
  const u = { uSss: { value: new THREE.Vector3(1, .42, .3) }, uMode: { value: pat ? pat.mode : 0 }, uN: { value: pat ? pat.n : 0 }, uRatio: { value: new THREE.Vector3(...(pat ? pat.ratio : [1, 1, 1])) } }; m.userData.pat = pat || null;
  m.onBeforeCompile = (sh) => { Object.assign(sh.uniforms, u);
    sh.vertexShader = 'attribute vec4 aPat; attribute vec3 aColB; attribute float aMix; attribute float aThick; varying vec4 vPat; varying vec3 vColB; varying float vMix; varying float vThick;\n' + sh.vertexShader.replace('#include <color_vertex>', '#include <color_vertex>\n  vPat = aPat; vColB = aColB; vMix = aMix; vThick = aThick;');
    sh.fragmentShader = 'varying float vThick; uniform vec3 uSss;\n' + PAT_GLSL + sh.fragmentShader.replace('#include <color_fragment>', SCULPT_FRAG).replace('#include <lights_fragment_end>', MK3D.hq ? SSS_FRAG : '#include <lights_fragment_end>'); };
  m.customProgramCacheKey = () => 'sculpt' + (MK3D.hq ? 'hq' : '');
  return (sculptM[k] = m); }
// ---------- мебель из «глины»: мягкие скруглённые формы, складки между подушками, тени в стыках ----------
const I3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];
function rotY3(a) { const c = Math.cos(a), s = Math.sin(a); return [c, 0, -s, 0, 1, 0, s, 0, c]; }
function rotX3(a) { const c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, c, s, 0, -s, c]; }
const lin3 = c => { const q = new THREE.Color(c); return [q.r, q.g, q.b]; };
function rb(x, y, z, bx, by, bz, rr, col, k, inv) { return { type: 'rbox', t: [x, y, z], inv: inv || I3, b: [bx, by, bz], rr, col: lin3(col), op: 'add', k: k || 0, bc: [x, y, z], br: Math.hypot(bx, by, bz), minR: Math.min(bx, by, bz) }; }
function cy(x, y, z, r1, r2, h, rr, col, k) { return { type: 'cyl', t: [x, y, z], inv: I3, s: [1, 1, 1], r1, r2, h, rr, col: lin3(col), op: 'add', k: k || 0, bc: [x, y, z], br: Math.max(r1, r2, h / 2) + rr, minR: Math.min(r1, r2, h / 2) }; }
const DOG_NOSE = new Set(['dog', 'bear', 'wolf', 'fox']);
function noseMesh(kind, color, r) { const SC = global.MKSculpt; if (!SC) return null; const dog = DOG_NOSE.has(kind), mouse = kind === 'mouse';
  const k = r / (dog ? .13 : mouse ? .075 : .085), rz = a => { const c = Math.cos(a), s = Math.sin(a); return [c, s, 0, -s, c, 0, 0, 0, 1]; };
  const E = (x, y, z, rx, ry, rzz, op, kk, rot) => ({ type: 'ell', t: [x * k, y * k, z * k], inv: rot ? rz(rot) : I3, r: [rx * k, ry * k, rzz * k], col: [1, 1, 1], op: op || 'add', k: (kk || 0) * k, bc: [x * k, y * k, z * k], br: Math.max(rx, ry, rzz) * k, minR: Math.min(rx, ry, rzz) * k });
  const pr = dog ? [E(0, 0, 0, .16, .1, .11), E(0, -.04, .015, .1, .07, .09, 'add', .05), E(0, .05, -.02, .13, .05, .1, 'add', .04),
      E(-.07, -.022, .085, .04, .022, .06, 'sub', .015, .45), E(.07, -.022, .085, .04, .022, .06, 'sub', .015, -.45), E(0, -.085, .09, .011, .05, .05, 'sub', .01)]
    : mouse ? [E(0, 0, 0, .075, .058, .065), E(-.03, -.012, .05, .014, .01, .025, 'sub', .008, .4), E(.03, -.012, .05, .014, .01, .025, 'sub', .008, -.4)]
    : [E(0, .018, 0, .1, .052, .068), E(0, -.026, .012, .045, .05, .055, 'add', .035), E(-.042, -.006, .055, .02, .012, .03, 'sub', .012, .4), E(.042, -.006, .055, .02, .012, .03, 'sub', .012, -.4)];
  const m = SC.mesh(pr, { res: 40 }); if (!m.idx.length) return null;
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(m.pos, 3)); geo.setAttribute('normal', new THREE.BufferAttribute(m.nor, 3)); geo.setIndex(new THREE.BufferAttribute(m.idx, 1));
  let mat; if (!MK3D.hq) mat = toon(color); else { mat = new THREE.MeshPhysicalMaterial({ color: col(color), roughness: dog ? .36 : .5, clearcoat: dog ? .9 : .45, clearcoatRoughness: dog ? .2 : .35, sheen: .25, sheenColor: new THREE.Color(1, 1, 1) });
    if (dog) { const U = { uNS: { value: 1 / (r * .055) } }; mat.onBeforeCompile = sh => { Object.assign(sh.uniforms, U); sh.vertexShader = 'varying vec3 vNP;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n vNP = position;');
      sh.fragmentShader = 'varying vec3 vNP; uniform float uNS;\n' + sh.fragmentShader.replace('#include <normal_fragment_maps>', '#include <normal_fragment_maps>\n { vec3 q = vNP * uNS; vec3 b = vec3(sin(q.x * 1.3 + sin(q.y * 2.1)) * sin(q.z * 1.7 + q.y), sin(q.y * 1.5 + sin(q.z * 1.9)) * sin(q.x * 1.1 - q.z), 0.); normal = normalize(normal + b * .2); }'); };
      mat.customProgramCacheKey = () => 'nose-dog'; } }
  const ms = new THREE.Mesh(geo, mat); ms.castShadow = true; ms.userData.noPush = true; ms.userData.nose = { r, depth: (dog ? .11 : mouse ? .065 : .068) * k }; return ms; }
// усы: тонкие, сужаются к кончику, чуть провисают — растут из точек на подушечках
function whiskerGeo(L, r0, droop) { const N = 12, M = 5, pos = [], idx = [];
  for (let i = 0; i <= N; i++) { const t = i / N, cx = L * t, cy = -droop * L * t * t, rr = r0 * (1 - .9 * t); for (let j = 0; j < M; j++) { const a = j / M * Math.PI * 2; pos.push(cx, cy + Math.cos(a) * rr, Math.sin(a) * rr); } }
  for (let i = 0; i < N; i++) for (let j = 0; j < M; j++) { const a = i * M + j, b = i * M + (j + 1) % M; idx.push(a, a + M, b, b, a + M, b + M); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals(); return g; }
function whiskerMat(c) { const k = 'wh' + c + (MK3D.hq ? 'h' : ''); if (matCache[k]) return matCache[k]; return (matCache[k] = MK3D.hq ? new THREE.MeshStandardMaterial({ color: col(c), roughness: .35 }) : new THREE.MeshToonMaterial({ color: col(c), gradientMap: grad })); }
// кепка по форме головы: оболочка вокруг «глины» головы + козырёк + пуговка; при смехе подпрыгивает
function sculptCap(rig, part, SC, poseInv) { const hat = rig.hats && rig.hats[0]; if (!hat) return; const hr = rig.P.head, hp = part.prims;
  const CM = new THREE.Matrix4().multiplyMatrices(poseInv, hat.matrixWorld), a = new THREE.Vector3(0, 1, 0).transformDirection(CM), P0 = new THREE.Vector3(0, hat.userData.hatCut + hr * .015, 0).applyMatrix4(CM);
  const g = hr * (MK3D.hq ? .025 : .008), t = hr * .075, H = (x, y, z) => SC.field(hp, x, y, z), V = new THREE.Vector3();
  const fwd = new THREE.Vector3(0, 0, 1).transformDirection(new THREE.Matrix4().multiplyMatrices(poseInv, rig.head.matrixWorld)); const f = fwd.clone().addScaledVector(a, -fwd.dot(a)).normalize();
  // передний край кепки: от оси вперёд до поверхности
  const E = P0.clone(); for (let i = 0; i < 60; i++) { if (H(E.x, E.y, E.z) > g + t * .5) break; E.addScaledVector(f, hr * .03); }
  const side = new THREE.Vector3().crossVectors(a, f).normalize(), vf = f.clone().applyAxisAngle(side, .5).normalize(), vu = new THREE.Vector3().crossVectors(vf, side).normalize(); // козырёк чуть вниз
  const VC = E.clone().addScaledVector(vf, hr * .2).addScaledVector(vu, -t * .25), vr = [hr * .6, hr * .044, hr * .45];
  const top = P0.clone(); for (let i = 0; i < 80; i++) { if (H(top.x, top.y, top.z) > g + t) break; top.addScaledVector(a, hr * .02); }
  const smax = (x, y, k) => { const h = Math.max(0, Math.min(1, .5 - .5 * (y - x) / k)); return x * h + y * (1 - h) + k * h * (1 - h); }, smin = (x, y, k) => { const h = Math.max(0, Math.min(1, .5 + .5 * (y - x) / k)); return x * h + y * (1 - h) - k * h * (1 - h); };
  const sdE = (p) => { V.copy(p).sub(VC); const lx = V.dot(side) / vr[0], lz = V.dot(vf) / vr[2], ly = (V.dot(vu) + hr * .13 * lx * lx + hr * .04 * Math.max(0, lz) ** 2) / vr[1]; const k0 = Math.hypot(lx, ly, lz), k1 = Math.hypot(lx / vr[0], ly / vr[1], lz / vr[2]); return k0 * (k0 - 1) / Math.max(k1, 1e-6); };
  const Q = new THREE.Vector3(), fn = (x, y, z) => { Q.set(x, y, z); const shell = Math.abs(H(x, y, z) - g - t * .5) - t * .5, plane = -Q.clone().sub(P0).dot(a);
    const crown = smax(shell, plane, hr * .025), vis = Math.max(sdE(Q), -Q.clone().sub(E).dot(vf) - hr * .05), btn = Q.distanceTo(top) - hr * .055; return smin(smin(crown, vis, hr * .03), btn, hr * .02); };
  const cl = new THREE.Color(hat.material.color || '#ffffff'), c3 = [cl.r, cl.g, cl.b], cen = P0.clone().addScaledVector(a, hr * .45);
  const pr = [{ type: 'fn', f: fn, col: c3, op: 'add', k: 0, bc: [cen.x, cen.y, cen.z], br: hr * 1.35, minR: t }];
  const m = SC.mesh(pr, { cell: hr * .018 }); if (MK3D.debug) console.log('кепка: вершин ' + m.pos.length / 3 + ', край ' + E.toArray().map(v => (v / hr).toFixed(2)) + ', верх ' + top.toArray().map(v => (v / hr).toFixed(2)) + ', ось ' + a.toArray().map(v => v.toFixed(2))); if (!m.idx.length) return;
  const ao = SC.occlusion([pr, hp], m.pos, m.nor, hr * .6, 2); SC.bake(m.col, ao, .5); SC.bake(m.colB, ao, .5);
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(m.pos, 3)); geo.setAttribute('normal', new THREE.BufferAttribute(m.nor, 3)); geo.setAttribute('color', new THREE.BufferAttribute(m.col, 3));
  geo.setAttribute('aColB', new THREE.BufferAttribute(m.colB, 3)); geo.setAttribute('aMix', new THREE.BufferAttribute(m.mixS, 1)); geo.setAttribute('aPat', new THREE.BufferAttribute(m.pat, 4)); geo.setAttribute('aThick', new THREE.BufferAttribute(new Float32Array(m.mixS.length).fill(1), 1)); geo.setIndex(new THREE.BufferAttribute(m.idx, 1)); geo.applyMatrix4(part.toPart);
  const cm = new THREE.Mesh(geo, sculptMat(null)); cm.castShadow = true; cm.receiveShadow = true; cm.userData.shell = true; part.grp.add(cm); rig.capM = cm; rig.capAxis = a.clone().transformDirection(part.toPart);
  if (!MK3D.hq) { const og = geo.clone(), pa = og.attributes.position, na = og.attributes.normal; for (let i = 0; i < pa.count; i++) pa.setXYZ(i, pa.getX(i) + na.getX(i) * .0045, pa.getY(i) + na.getY(i) * .0045, pa.getZ(i) + na.getZ(i) * .0045); for (const q of ['color', 'aPat', 'aColB', 'aMix', 'aThick']) og.deleteAttribute(q); const ol = new THREE.Mesh(og, OL); ol.castShadow = false; cm.add(ol); }
  rig.head.traverse(o => { if (o.userData.capOld) o.visible = false; }); }
function sculptStatic(prims, res, aoS) { const SC = global.MKSculpt; prims.forEach((p, i) => { if (i === 0) p.k = 0; }); const m = SC.mesh(prims, { res }); if (!m.idx.length) return null;
  const ao = SC.occlusion([prims], m.pos, m.nor, aoS, 2.2); SC.bake(m.col, ao, .45); SC.bake(m.colB, ao, .45);
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(m.pos, 3)); geo.setAttribute('normal', new THREE.BufferAttribute(m.nor, 3)); geo.setAttribute('color', new THREE.BufferAttribute(m.col, 3));
  geo.setAttribute('aColB', new THREE.BufferAttribute(m.colB, 3)); geo.setAttribute('aMix', new THREE.BufferAttribute(m.mixS, 1)); geo.setAttribute('aPat', new THREE.BufferAttribute(m.pat, 4)); geo.setAttribute('aThick', new THREE.BufferAttribute(new Float32Array(m.mixS.length).fill(1), 1)); geo.setIndex(new THREE.BufferAttribute(m.idx, 1));
  const ms = new THREE.Mesh(geo, sculptMat(null)); ms.castShadow = true; ms.receiveShadow = true; ms.userData.keep = true; return ms; }
function furnitureHQ(g, kit) {
  if (!global.MKSculpt) return; const tagged = {}; g.traverse(o => { if (o.userData.tag) tagged[o.userData.tag] = o; });
  const hide = o => o && o.traverse(q => { if (q.isMesh) q.visible = false; });
  if (tagged.sofa) { const S = tagged.sofa, f = '#5f9e8f', cu = '#6fae9f'; hide(S);
    const pr = [rb(0, .26, 0, 1.5, .2, .5, .09, f), rb(-1.36, .47, 0, .16, .33, .52, .13, f, .05), rb(1.36, .47, 0, .16, .33, .52, .13, f, .05), rb(0, .76, -.38, 1.24, .34, .13, .12, f, .05),
      rb(-.6, .52, .07, .6, .11, .42, .1, cu, .012), rb(.6, .52, .07, .6, .11, .42, .1, cu, .012), rb(-.6, .82, -.2, .57, .25, .11, .13, cu, .012, rotX3(-.15)), rb(.6, .82, -.2, .57, .25, .11, .13, cu, .012, rotX3(-.15))];
    const m = sculptStatic(pr, 72, .5); if (m) { m.position.copy(S.position); g.add(m); }
    for (const [x, z] of [[-1.35, .4], [1.35, .4], [-1.35, -.42], [1.35, -.42]]) { const l = new THREE.Mesh(G.cyl(.04, .03, .1, 12), stdM('#4a3020', null, .5)); l.position.set(S.position.x + x, .05, S.position.z + z); g.add(l); } }
  if (tagged.table) { const T = tagged.table, w = '#a8703f'; hide(T);
    const m = sculptStatic([cy(0, .785, 0, .9, .9, .07, .028, w), cy(0, .42, 0, .075, .055, .7, .02, w, .05), cy(0, .03, 0, .34, .3, .06, .025, w, .06)], 64, .5); if (m) { m.position.copy(T.position); g.add(m); } }
  if (tagged.counter) { const C = tagged.counter, f = '#7fc4a4', top = '#e6d8bd'; hide(C);
    const pr = [rb(0, .47, 0, 2.5, .47, .45, .03, f)]; for (let i = 0; i < 5; i++) pr.push(Object.assign(rb(-2 + i, .5, .45, .44, .4, .025, .02, f), { op: 'sub', k: .012 })); // дверцы — канавки между ними
    pr.push(rb(0, .99, .02, 2.56, .04, .5, .03, top, .01)); pr.push(rb(0, 2.6, -.2, 2.5, .4, .25, .03, f, 0)); for (let i = 0; i < 5; i++) pr.push(Object.assign(rb(-2 + i, 2.6, .05, .44, .34, .02, .02, f), { op: 'sub', k: .01 }));
    const m = sculptStatic(pr, 110, .6); if (m) { m.position.copy(C.position); g.add(m); } }
}
// ---------- рот: живой рисунок прямо на коже мордочки (повторяет её изгибы). Форма — от звуков речи и настроения ----------
const MOUTH_GLSL = `uniform float uOpen, uWide, uSmile, uRound, uKind, uClose, uDots; uniform vec2 uPad; varying vec2 vM;
float mSeg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0., 1.); return length(pa - ba * h); }
vec4 mouthCol(vec2 p) {
  float aa = max(fwidth(p.x), fwidth(p.y)) * 1.1 + 1e-4, lw = max(.085, aa * 1.6);
  float o = clamp(uOpen, 0., 1.) * (1. - .9 * uClose), s = uSmile, rn = uRound, w = uWide, dog = step(.5, uKind), ok = smoothstep(.03, .14, o);
  // закрытый: «:3» у котика и мышки, мягкая «улыбка-якорь» у пса
  float Lc = mix(.95, 1.25, dog) * (1. + .25 * w - .3 * rn), tx = clamp(abs(p.x) / Lc, 0., 1.), lift = s * mix(.4, .55, dog);
  float droop = mix(.34, .26, dog) * (1. - .5 * max(s, 0.)), yl = -droop * sin(3.14159 * tx) + lift * tx * tx;
  float sl = droop * 3.14159 / Lc * cos(3.14159 * tx) - 2. * lift * tx / Lc, dC = abs(p.y - yl) / sqrt(1. + sl * sl);
  if (abs(p.x) > Lc) dC = length(vec2(abs(p.x) - Lc, p.y - lift));
  // открытый: «D» в улыбке, кружок на «о/у», щель на «и»
  float Lo = mix(.95, 1.25, dog) * (.72 + .55 * w) * (1. - .42 * rn) + .25 * o, xo = p.x / Lo, q = clamp(1. - xo * xo, 0., 1.), yc = s * .42 * xo * xo;
  float top = yc + o * (.22 + .25 * rn) * pow(q, .5), bot = yc - o * (1.75 + .5 * rn) * pow(q, .55 + .35 * rn);
  float dO = max((abs(xo) - 1.) * Lo, max(p.y - top, bot - p.y)), inside = (1. - smoothstep(-aa, aa, dO)) * ok;
  float yb0 = -o * (1.75 + .5 * rn); vec2 tq = (p - vec2(0., yb0 + o * .55)) / vec2(Lo * .62, max(.05, o * .7));
  float tongue = 1. - smoothstep(.92, 1.08, length(tq)), teeth = step(.3, o) * (1. - smoothstep(.48, .58, abs(xo))) * smoothstep(top - .2 * o - aa, top - .2 * o + aa, p.y);
  float depth = clamp((p.y - bot) / max(.05, top - bot), 0., 1.);
  vec3 inC = mix(vec3(.32, .05, .07), vec3(.09, .012, .025), depth); inC = mix(inC, vec3(.86, .36, .43), tongue * .95); inC = mix(inC, vec3(1., .97, .92), teeth);
  float lineA = max((1. - smoothstep(lw * .55 - aa, lw * .55 + aa, abs(dO))) * ok, (1. - smoothstep(lw * .5 - aa, lw * .5 + aa, dC)) * (1. - ok));
  lineA = max(lineA, 1. - smoothstep(lw * .45 - aa, lw * .45 + aa, mSeg(p, vec2(0., 1.02), vec2(0., mix(0., top, ok))))); // желобок от носика
  float dots = 0.; if (uDots > .5) { vec2 q = vec2(abs(p.x), p.y) - uPad; for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { vec2 c = vec2(float(i) - 1., float(j) - 1.) * vec2(.27, .24) + vec2(float(j) * .06, 0.); dots = max(dots, 1. - smoothstep(max(.045, aa) - aa, max(.045, aa) + aa, length(q - c))); } }
  vec3 lc = vec3(.2, .09, .06); return vec4(mix(mix(inC, lc, lineA), lc * 1.3, dots * (1. - inside) * .75), max(max(inside, lineA), dots * .75)); }`;
function mouthMat(kind, pad) { const U = { uOpen: { value: 0 }, uWide: { value: .5 }, uSmile: { value: .3 }, uRound: { value: 0 }, uKind: { value: kind || 0 }, uClose: { value: 0 }, uDots: { value: pad ? 1 : 0 }, uPad: { value: new THREE.Vector2(...(pad || [0, 0])) } };
  const o = { color: 0xffffff, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 };
  const m = MK3D.hq ? new THREE.MeshStandardMaterial(Object.assign(o, { roughness: .45 })) : new THREE.MeshToonMaterial(Object.assign(o, { gradientMap: grad }));
  m.onBeforeCompile = sh => { Object.assign(sh.uniforms, U); sh.vertexShader = 'attribute vec2 aM; varying vec2 vM;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n vM = aM;');
    sh.fragmentShader = MOUTH_GLSL + '\n' + sh.fragmentShader.replace('#include <color_fragment>', '#include <color_fragment>\n { vec4 mc = mouthCol(vM); diffuseColor = vec4(mc.rgb, mc.a * opacity); if (diffuseColor.a < .004) discard; }'); };
  m.customProgramCacheKey = () => 'mouth' + (MK3D.hq ? 'hq' : ''); m.userData.U = U; return m; }
function skinPatch(rig, part, SC, poseInv, at, HH, ext, mat, NU, NV) { // сетка, лежащая точно на коже (проекция на поле расстояний головы)
  const hr = rig.P.head, pr = part.prims, f = (x, y, z) => SC.field(pr, x, y, z), e = hr * .004, [X0, X1, Y0, Y1] = ext;
  const grd = p => new THREE.Vector3(f(p.x + e, p.y, p.z) - f(p.x - e, p.y, p.z), f(p.x, p.y + e, p.z) - f(p.x, p.y - e, p.z), f(p.x, p.y, p.z + e) - f(p.x, p.y, p.z - e)).normalize();
  const proj = p => { for (let i = 0; i < 8; i++) { const d = f(p.x, p.y, p.z); if (Math.abs(d) < hr * 2e-4) break; p.addScaledVector(grd(p), -d); } return p; };
  const HM = new THREE.Matrix4().multiplyMatrices(poseInv, rig.head.matrixWorld), c = new THREE.Vector3(at[0] * hr, at[1] * hr, at[2] * hr).applyMatrix4(HM); proj(c);
  const n = grd(c), up0 = new THREE.Vector3(0, 1, 0).transformDirection(HM), rt = new THREE.Vector3().crossVectors(up0, n).normalize(), up = new THREE.Vector3().crossVectors(n, rt).normalize();
  const pos = new Float32Array(NU * NV * 3), nor = new Float32Array(NU * NV * 3), am = new Float32Array(NU * NV * 2), idx = [];
  for (let j = 0; j < NV; j++) for (let i = 0; i < NU; i++) { const x = X0 + (X1 - X0) * i / (NU - 1), y = Y0 + (Y1 - Y0) * j / (NV - 1), k = j * NU + i;
    const p = c.clone().addScaledVector(rt, x * HH).addScaledVector(up, y * HH); proj(p); const nn = grd(p); p.addScaledVector(nn, hr * .006);
    pos.set([p.x, p.y, p.z], k * 3); nor.set([nn.x, nn.y, nn.z], k * 3); am.set([x, y], k * 2); if (i < NU - 1 && j < NV - 1) idx.push(k, k + 1, k + NU, k + 1, k + NU + 1, k + NU); }
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('normal', new THREE.BufferAttribute(nor, 3)); geo.setAttribute('aM', new THREE.BufferAttribute(am, 2)); geo.setIndex(idx); geo.applyMatrix4(part.toPart);
  const m = new THREE.Mesh(geo, mat); m.renderOrder = 2; m.userData.shell = true; m.userData.patchC = c.clone().applyMatrix4(part.toPart); part.grp.add(m); return m; }
function mouthPatch(rig, part, SC, poseInv) { const HN = Math.max(.09, rig.noseY - rig.mouthAt[0]), HH = HN * rig.P.head, pd = rig.padAt;
  rig.mouthPatch = skinPatch(rig, part, SC, poseInv, [0, rig.mouthAt[0], rig.mouthAt[1]], HH, [-2.1, 2.1, -2.8, 1.18], mouthMat(rig.mouthKind, pd ? [Math.min(1.75, pd[0] / HN), (pd[1] - rig.mouthAt[0]) / HN] : null), 26, 24);
  rig.mouthPatch.userData.keep = [new THREE.Vector3(0, -.7 * HH, 0), HH * 1.9];
  for (const q of [rig.smile, rig.frown, rig.open]) if (q) q.visible = false; }
// брови — мазок шерсти на коже над глазом: поднимаются (удивление), сводятся к носу (сердится), домиком (грусть)
const BROW_GLSL = `uniform float uLift, uTilt, uSide; uniform vec3 uBrowC; varying vec2 vM;
vec4 browCol(vec2 p) { float aa = max(fwidth(p.x), fwidth(p.y)) + 1e-4, x = p.x * uSide, y = p.y - uLift;
  float yc = .26 * (1. - x * x) + uTilt * x, t = clamp((x + 1.) * .5, 0., 1.), th = max(mix(.2, .075, t), aa * .8);
  float a = (1. - smoothstep(-aa, aa, abs(y - yc) - th)) * (1. - smoothstep(1. - aa * 2., 1. + aa, abs(x))); return vec4(uBrowC, a * .95); }`;
function browMat(col, side) { const U = { uLift: { value: 0 }, uTilt: { value: 0 }, uSide: { value: side }, uBrowC: { value: new THREE.Color(col) } };
  const o = { color: 0xffffff, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 };
  const m = MK3D.hq ? new THREE.MeshStandardMaterial(Object.assign(o, { roughness: .9 })) : new THREE.MeshToonMaterial(Object.assign(o, { gradientMap: grad }));
  m.onBeforeCompile = sh => { Object.assign(sh.uniforms, U); sh.vertexShader = 'attribute vec2 aM; varying vec2 vM;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n vM = aM;');
    sh.fragmentShader = BROW_GLSL + '\n' + sh.fragmentShader.replace('#include <color_fragment>', '#include <color_fragment>\n { vec4 bc = browCol(vM); diffuseColor = vec4(bc.rgb, bc.a * opacity); if (diffuseColor.a < .004) discard; }'); };
  m.customProgramCacheKey = () => 'brow' + (MK3D.hq ? 'hq' : ''); m.userData.U = U; return m; }
// румянец — мягкое пятно прямо на щеке (не торчит из-за мордочки сбоку)
function blushMat() { const U = { uAmt: { value: .4 } }; const m = new THREE.MeshBasicMaterial({ color: 0xff8fa0, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3 });
  m.onBeforeCompile = sh => { Object.assign(sh.uniforms, U); sh.vertexShader = 'attribute vec2 aM; varying vec2 vM;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n vM = aM;');
    sh.fragmentShader = 'uniform float uAmt; varying vec2 vM;\n' + sh.fragmentShader.replace('#include <color_fragment>', '#include <color_fragment>\n diffuseColor.a *= (1. - smoothstep(.15, 1., length(vM * vec2(1., 1.5)))) * uAmt; if (diffuseColor.a < .004) discard;'); };
  m.customProgramCacheKey = () => 'blush'; m.userData.U = U; return m; }
function browPatches(rig, part, SC, poseInv) {
  const hr0 = rig.P.head; rig.blushP = []; for (const ch of rig.cheeks || []) { const p = ch.position; const m = skinPatch(rig, part, SC, poseInv, [p.x / hr0, p.y / hr0, p.z / hr0 + .25], hr0 * .15, [-1.2, 1.2, -.9, .9], blushMat(), 10, 8); m.renderOrder = 1; rig.blushP.push(m); ch.visible = false; } const hr = rig.P.head, bc = new THREE.Color(rig.n.c.body).multiplyScalar(.48).getStyle();
  for (const e of rig.eyes) { const ex = e.g.position.x / hr, ey = e.g.position.y / hr, er = e.eR / hr, HB = e.eR * .82;
    e.browP = skinPatch(rig, part, SC, poseInv, [ex * .97, ey + er * 1.42, 1.05], HB, [-1.4, 1.4, -.8, 1.5], browMat(bc, e.s > 0 ? 1 : -1), 18, 12); e.brow.visible = false; e.browP.userData.keep = [new THREE.Vector3(0, HB * .2, 0), HB * 1.05]; } }
function sculptRig(rig) {
  const SC = global.MKSculpt; if (!SC || rig.human || rig.kind === 'robot' || (MK3D.hq && FEATHER_KINDS.has(rig.kind))) return;
  const n = rig.n, P = rig.P, hr = P.head, c = n.c, O = rig.spec.outfit || {};
  rig.root.updateMatrixWorld(true);
  const poseInv = new THREE.Matrix4().copy(rig.pose.matrixWorld).invert();
  const M = new THREE.Matrix4(), tp = new THREE.Vector3(), tq = new THREE.Quaternion(), ts = new THREE.Vector3(), RM = new THREE.Matrix4();
  const lin = x => { const q = x && x.isColor ? x : new THREE.Color(x || '#888888'); return [q.r, q.g, q.b]; };
  const noseHex = new THREE.Color(c.nose || '#000000').getHex(), stripeHex = new THREE.Color(c.stripe || '#000000').getHex();
  const stripes = n.pattern.includes('stripes'), spots = n.pattern.includes('spots');
  const frame = (mw) => { M.multiplyMatrices(poseInv, mw); M.decompose(tp, tq, ts); RM.makeRotationFromQuaternion(tq); const e = RM.elements; return { t: [tp.x, tp.y, tp.z], inv: [e[0], e[1], e[2], e[4], e[5], e[6], e[8], e[9], e[10]], s: [ts.x, ts.y, ts.z] }; };
  function primsOf(m, region) {
    const g = m.geometry, pa = g.parameters || {}, mat = m.material;
    if (m.userData.groove && g.type === 'SphereGeometry') { const f = frame(m.matrixWorld), r = [pa.radius * f.s[0], pa.radius * f.s[1], pa.radius * f.s[2]], rm = Math.min(...r); return [{ type: 'ell', t: f.t, inv: f.inv, r, col: [1, 1, 1], op: 'sub', k: rm * .7, bc: f.t, br: Math.max(...r), minR: rm }]; } // пальчики: бороздки между ними
    if (!mat || Array.isArray(mat) || mat.isMeshBasicMaterial || mat.transparent || mat.side === THREE.DoubleSide || m.userData.noFur || m.userData.shell || m.visible === false) return null;
    const f = frame(m.matrixWorld), sMax = Math.max(f.s[0], f.s[1], f.s[2]), mapped = !!mat.map, col0 = mapped ? lin(c.body) : lin(mat.color);
    const pat = mapped ? (stripes ? { mode: region === 'head' ? 'head' : region === 'tail' ? 'tail' : 'body', col: lin(c.stripe), n: region === 'head' ? 10 : 7, u0: 0, u1: 1 } : spots ? { mode: 'spots', col: lin(c.stripe) } : null) : null;
    const base = () => ({ t: f.t, inv: f.inv, col: col0, pat, op: 'add', bc: f.t });
    switch (g.type) {
      case 'SphereGeometry': { if ((pa.phiLength != null && pa.phiLength < 6.28) || (pa.thetaLength != null && pa.thetaLength < 3.14)) return null;
        const r = [pa.radius * f.s[0], pa.radius * f.s[1], pa.radius * f.s[2]], rMin = Math.min(...r);
        if (!mapped && mat.color.getHex() === noseHex && pa.radius * sMax < hr * .2) return null; // носик — отдельный, блестящий
        const pr = Object.assign(base(), { type: 'ell', r, br: pa.radius * sMax, minR: rMin });
        if (region === 'head' && !mapped && mat.color.getHex() === stripeHex && r[2] < r[0] * .6) { pr.op = 'paint'; pr.k = rMin * 1.6; } // маска/пятно — только цвет
        return [pr]; }
      case 'CapsuleGeometry': return [Object.assign(base(), { type: 'cap', r1: pa.radius, h: pa.length, s: f.s, br: (pa.length / 2 + pa.radius) * sMax, minR: pa.radius * Math.min(...f.s) })];
      case 'ConeGeometry': if ((pa.radialSegments || 0) < 8) return null;
        if (m.userData.carve) { const c0 = Object.assign(base(), { type: 'cone', r1: pa.radius * .9, r2: pa.radius * .12, h: pa.height, s: f.s, br: Math.max(pa.height / 2, pa.radius) * sMax, minR: pa.radius * .4 }); // ушко: выемка внутри, розовая
          return [Object.assign({}, c0, { op: 'sub', k: pa.radius * .25 }), Object.assign({}, c0, { op: 'paint', k: pa.radius * .35, r1: pa.radius * 1.02 })]; }
        return [Object.assign(base(), { type: 'cone', r1: pa.radius * .96, r2: pa.radius * .14, h: pa.height, s: f.s, br: Math.max(pa.height / 2, pa.radius) * sMax, minR: pa.radius * .5 })];
      case 'CylinderGeometry': if (pa.openEnded || Math.min(pa.radiusTop, pa.radiusBottom) < .02) return null;
        return [Object.assign(base(), { type: 'cyl', r1: pa.radiusBottom, r2: pa.radiusTop, h: pa.height, rr: Math.min(pa.radiusTop, pa.radiusBottom, pa.height / 2) * .4, s: f.s, br: Math.max(pa.height / 2, pa.radiusTop, pa.radiusBottom) * sMax, minR: Math.min(pa.radiusTop, pa.radiusBottom, pa.height / 2) })];
      case 'TubeGeometry': { // хвост, хобот: цепочка плавно сужающихся конусов
        const curve = pa.path, R0 = pa.radius, N = 8, pts = []; if (!curve) return null; for (let i = 0; i <= N; i++) pts.push(curve.getPoint(i / N).applyMatrix4(M));
        const out = [], up = new THREE.Vector3(0, 1, 0), q = new THREE.Quaternion(), rm = new THREE.Matrix4(), rad = u => R0 * (1.12 - .32 * u);
        for (let i = 0; i < N; i++) { const a = pts[i], b = pts[i + 1], dir = b.clone().sub(a), h = dir.length(); if (h < 1e-4) continue; dir.normalize(); q.setFromUnitVectors(up, dir); rm.makeRotationFromQuaternion(q); const e = rm.elements, mid = a.clone().add(b).multiplyScalar(.5);
          out.push({ type: 'cone', t: [mid.x, mid.y, mid.z], inv: [e[0], e[1], e[2], e[4], e[5], e[6], e[8], e[9], e[10]], s: [1, 1, 1], r1: rad(i / N), r2: rad((i + 1) / N), h, col: col0, pat: pat ? Object.assign({}, pat, { u0: i / N, u1: (i + 1) / N, n: 6 }) : null, op: 'add', bc: [mid.x, mid.y, mid.z], br: h / 2 + R0 * 1.2, minR: R0, kk: R0 * .5 }); }
        return out; }
    }
    return null;
  }
  const parts = [], dressed = !!(O.shirt || O.pants || O.overalls || O.dress || O.pajamas || O.suit);
  const take = (grp, region, k) => { if (!grp) return; const prims = [], fused = [];
    for (const m of grp.children.slice()) { if (!m.isMesh) continue; const ps = primsOf(m, region); if (!ps) continue; for (const p of ps) { if (p.op === 'add') p.k = prims.some(q => q.op === 'add') ? Math.min(p.kk != null ? p.kk : k, (p.minR || k) * .9) : 0; prims.push(p); } fused.push(m); }
    if (prims.some(q => q.op === 'add')) parts.push({ grp, region, prims, fused }); };
  take(rig.head, 'head', hr * .09); take(rig.body, 'body', Math.min(P.bx || .3, P.bz || .3) * (dressed ? .05 : .1));
  rig.legs.forEach(g => take(g, 'leg', P.legR * .55)); rig.arms.forEach(g => take(g, 'arm', P.armR * .55)); take(rig.tail, 'tail', .03); (rig.ears || []).forEach(e => take(e, 'ear', hr * .04));
  const head = parts.find(p => p.region === 'head');
  if (!parts.length) return;
  if (MK3D.debug) console.log('скульптор ' + rig.spec.name + ': ' + parts.map(p => p.region + '[' + p.prims.map(q => q.type + (q.pat ? '/' + q.pat.mode : '') + (q.op !== 'add' ? '/' + q.op : '')).join(',') + ']').join(' '));
  const groups = parts.map(p => p.prims.filter(q => q.op !== 'paint'));
  for (const p of parts) {
    const res = p.region === 'head' ? 46 : p.region === 'body' ? 40 : p.region === 'tail' ? 34 : p.region === 'ear' ? 28 : 24;
    const m = SC.mesh(p.prims, { res }); if (!m.idx.length) continue;
    { const ao = SC.occlusion(groups, m.pos, m.nor, hr * .9), fl = MK3D.hq ? .46 : .62; SC.bake(m.col, ao, fl); SC.bake(m.colB, ao, fl); }
    const thick = SC.thickness(p.prims, m.pos, m.nor, hr * .8, m.cell * .5); // до перевода в координаты части
    const toPart = new THREE.Matrix4().multiplyMatrices(poseInv, p.grp.matrixWorld).invert();
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(m.pos, 3)); geo.setAttribute('normal', new THREE.BufferAttribute(m.nor, 3)); geo.setAttribute('color', new THREE.BufferAttribute(m.col, 3)); geo.setIndex(new THREE.BufferAttribute(m.idx, 1)); geo.applyMatrix4(toPart);
    geo.setAttribute('aThick', new THREE.BufferAttribute(thick, 1)); geo.setAttribute('aColB', new THREE.BufferAttribute(m.colB, 3)); geo.setAttribute('aMix', new THREE.BufferAttribute(m.mixS, 1)); geo.setAttribute('aPat', new THREE.BufferAttribute(m.pat, 4));
    const pp = p.prims.find(q => q.pat); let patInfo = null; if (pp) { const b = pp.col, st = pp.pat.col; patInfo = { mode: SC.MODES[pp.pat.mode] || 0, n: pp.pat.n || 7, ratio: [0, 1, 2].map(i => +(Math.min(1.2, st[i] / Math.max(.02, b[i]))).toFixed(3)) }; }
    for (const f of p.fused) p.grp.remove(f);
    const sm = new THREE.Mesh(geo, sculptMat(patInfo)); sm.castShadow = true; sm.receiveShadow = true; sm.userData.sculpt = true; p.grp.add(sm); p.mesh = sm; p.toPart = toPart;
    if (!MK3D.hq) { const og = geo.clone(), pa = og.attributes.position, na = og.attributes.normal, w = p.region === 'head' || p.region === 'body' ? .011 : .008; for (let i = 0; i < pa.count; i++) pa.setXYZ(i, pa.getX(i) + na.getX(i) * w, pa.getY(i) + na.getY(i) * w, pa.getZ(i) + na.getZ(i) * w); for (const a of ['color', 'aPat', 'aColB', 'aMix', 'aThick']) if (og.attributes[a]) og.deleteAttribute(a);
      const ol = new THREE.Mesh(og, OL); ol.castShadow = false; sm.add(ol); }
  }
  // носик, рот, усы, румянец — на поверхность новой мордочки (чтобы не утонули в щёчках)
  if (head && head.mesh) { const hc = new THREE.Vector3().setFromMatrixPosition(M.multiplyMatrices(poseInv, rig.head.matrixWorld));
    for (const ch of rig.head.children.slice()) { if (ch === head.mesh || (rig.ears || []).includes(ch) || rig.eyes.some(e => e.g === ch)) continue;
      let acc = false; ch.traverse(o => { if (o.userData.noFur) acc = true; }); if (acc || ch.userData.noPush || ch.userData.whisker) continue; // шапки, бантики, нос, усы — отдельно
      if (ch !== rig.mouth) { if (!ch.isMesh) continue; ch.geometry.computeBoundingSphere(); if (ch.geometry.boundingSphere.radius * Math.max(ch.scale.x, ch.scale.y, ch.scale.z) > hr * .3) continue; }
      const w = new THREE.Vector3(); ch.getWorldPosition(w); w.applyMatrix4(poseInv); const dir = w.clone().sub(hc); if (dir.lengthSq() < 1e-8) continue; dir.normalize();
      const margin = ch === rig.mouth ? hr * .025 : hr * .012; let moved = false;
      for (let it = 0; it < 8; it++) { const d = SC.field(head.prims, w.x, w.y, w.z); if (d >= margin) break; w.addScaledVector(dir, margin - d + hr * .005); moved = true; }
      if (moved) ch.position.copy(w.applyMatrix4(head.toPart)); }
    { const HM = new THREE.Matrix4().multiplyMatrices(poseInv, rig.head.matrixWorld), P = new THREE.Vector3(); // где кожа по оси «вперёд» (для носа и корней усов)
      const surfZ = (x, y) => { let lo = 0, hi = hr * 2.4; const F = z => { P.set(x, y, z).applyMatrix4(HM); return SC.field(head.prims, P.x, P.y, P.z); }; if (F(hi) < 0) return hi; for (let i = 0; i < 26; i++) { const mid = (lo + hi) / 2; if (F(mid) < 0) lo = mid; else hi = mid; } return (lo + hi) / 2; };
      if (rig.noseM) { const nd = rig.noseM.userData.nose; rig.noseM.position.z = surfZ(0, rig.noseM.position.y) + nd.depth * .3; }
      rig.head.children.forEach(w => { if (w.userData.whisker) w.position.z = surfZ(w.position.x, w.position.y) - hr * .01; }); }
    if (rig.mouthAt) try { mouthPatch(rig, head, SC, poseInv); } catch (e) { console.log('рот', e.message); }
    if (rig.hats) try { sculptCap(rig, head, SC, poseInv); } catch (e) { console.log('кепка', e.message); }
    if (rig.mouthAt) try { browPatches(rig, head, SC, poseInv); } catch (e) { console.log('брови', e.message); }
  }
  rig.sculpted = true;
}
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
  const n = rig.n; if (rig.human) { addHairStrands(rig); return; } if (!FUR_KINDS.has(rig.kind)) return;
  const fc = new Set([n.c.body, n.c.belly, n.c.stripe, n.c.mane].filter(Boolean).map(c => new THREE.Color(c).getHexString()));
  const eyeG = new Set(rig.eyes.map(e => e.g)); const list = [];
  rig.pose.traverse(o => { if (!o.isMesh || o.userData.shell || o.userData.noFur || !o.material || !o.material.isMeshPhysicalMaterial || o.material.clearcoat > 0) return; let p = o.parent; while (p) { if (eyeG.has(p)) return; p = p.parent; }
    const isFur = o.userData.sculpt || (o.material.map ? true : fc.has(o.material.color.getHexString())); if (isFur) list.push(o); });
  if (rig.head && (!FEATHER_KINDS.has(rig.kind) || rig.kind === 'chick')) { const furSet = new Set(list); for (const ch of rig.head.children) { if (eyeG.has(ch) || furSet.has(ch) || !ch.position) continue; let anyFur = false; ch.traverse(o => { if (furSet.has(o)) anyFur = true; }); if (anyFur) continue; const v = ch.position.clone(); if (v.lengthSq() > 1e-6) ch.position.add(v.normalize().multiplyScalar(.042)); } }
  const L = .026; for (const e of rig.eyes) { e.g.position.z += L * .55; }
  rig.R0 = rig.root; rig.root.updateMatrixWorld(true);
  // запретные зоны (глаза, нос, рот, щёки) — волоски там не растут, чтобы не закрывать мордочку
  const keep = []; const furSet = new Set(list);
  for (const e of rig.eyes) { const w = new THREE.Vector3(); e.g.getWorldPosition(w); keep.push([w, e.eR * 1.45]); }
  if (rig.head) rig.head.traverse(o => { if (!o.isMesh || furSet.has(o) || o.userData.shell) return; let p = o.parent; while (p) { if (eyeG.has(p)) return; p = p.parent; } o.geometry.computeBoundingSphere(); const r = o.geometry.boundingSphere.radius * Math.max(o.scale.x, o.scale.y, o.scale.z); if (r > .12) return; const w = new THREE.Vector3(); o.getWorldPosition(w); const hc = new THREE.Vector3(); rig.head.getWorldPosition(hc); if (w.z < hc.z) return; keep.push([w, r + .02]); });
  rig.root.traverse(o => { if (o.userData.keep && o.userData.patchC) { const w = o.userData.patchC.clone().add(o.userData.keep[0]).applyMatrix4(o.matrixWorld); keep.push([w, o.userData.keep[1] * (rig.scale || 1)]); } });
  rig.root.traverse(o => { if (!o.isMesh || !o.userData.noFur) return; o.geometry.computeBoundingSphere(); const ws = new THREE.Vector3(); o.getWorldScale(ws); const w = o.geometry.boundingSphere.center.clone().applyMatrix4(o.matrixWorld); keep.push([w, o.geometry.boundingSphere.radius * Math.max(ws.x, ws.y, ws.z) * .9]); });
  const O = rig.spec.outfit || {}; const clothed = !!(O.shirt || O.overalls || O.dress || O.pajamas || O.suit);
  const under = (o, g) => { let p = o.parent; while (p) { if (p === g) return true; p = p.parent; } return false; };
  if (FEATHER_KINDS.has(rig.kind)) { addBirdFeathers(rig, list, keep, under); rig.fur = []; rig.root.traverse(o => { if (o.userData.strands) rig.fur.push(o); }); return; }
  for (const o of list) { if (clothed && (under(o, rig.body) || rig.legs.some(g => under(o, g)) || (O.shirt || O.suit || O.pajamas || O.dress) && rig.arms.some(g => under(o, g)))) continue; { let fk = 1, pp = o; while (pp) { if (pp.userData.furK != null) { fk = Math.min(fk, pp.userData.furK); } pp = pp.parent; } const reg = under(o, rig.tail) ? 'tail' : rig.legs.some(g => under(o, g)) ? 'leg' : rig.arms.some(g => under(o, g)) ? 'arm' : under(o, rig.body) ? 'body' : 'head'; addStrands(rig, o, L, keep, fk, reg); } }
  rig.fur = []; rig.root.traverse(o => { if (o.userData.strands) rig.fur.push(o); });
}
// ---------- волоски-нити: каждый волосок — отдельная линия; блик вдоль волоска (Kajiya-Kay), качание от движения ----------
const FUR_VS = `
attribute vec3 aRoot; attribute vec3 aNorm; attribute vec2 aUv; attribute vec4 aRnd; attribute float aT; attribute vec3 aTilt; attribute vec3 aCol; attribute vec4 aGroom; varying vec3 vCol; varying vec3 vN; varying float vGuard;
uniform float uLen; uniform vec3 uLag; uniform float uGrav; uniform float uTime; uniform float uNk; uniform float uCk;
varying vec3 vT; varying vec3 vW; varying float vt; varying vec2 vUv; varying float vVar;
void main(){
  vec3 nW = normalize(mat3(modelMatrix) * aNorm);
  float sc = length(mat3(modelMatrix) * vec3(0.0,1.0,0.0)) / max(length(aNorm),1e-4);
  vec3 tan1 = normalize(cross(nW, abs(nW.y) < .95 ? vec3(0.,1.,0.) : vec3(1.,0.,0.))); vec3 tan2 = cross(nW, tan1);
  vec3 down = vec3(0.,-1.,0.) - nW * dot(vec3(0.,-1.,0.), nW); float dl = length(down); vec3 comb = dl > .05 ? down / dl : vec3(0.);
  vec3 tiltW = mat3(modelMatrix) * aTilt;
  // направление роста: своё у каждого волоска (от носа назад, от шеи к хвосту, по лапам вниз); если не задано — вниз, как раньше
  vec3 gW = mat3(modelMatrix) * aGroom.xyz; gW -= nW * dot(gW, nW); float gL = length(gW);
  vec3 flow = gL > .02 ? gW / gL : comb; float lie = gL > .02 ? aGroom.w : 1.0;
  vec3 dir = normalize(nW * uNk + flow * uCk * lie + tiltW);
  float len = uLen * aRnd.x * sc;
  float t = aT;
  vec3 root = (modelMatrix * vec4(aRoot, 1.0)).xyz;
  float sway = sin(uTime * 2.3 + aRnd.w * 40.0) * .06;
  vec3 bend = (vec3(0.0, -uGrav, 0.0) + uLag + tan1 * sway) * len;
  vec3 wave = tan2 * sin(t * 6.0 + aRnd.w * 20.0) * len * .08 * t;
  vec3 p = root + dir * len * t + bend * t * t + wave;
  vec3 tg = normalize(dir * len + bend * 2.0 * t);
  vT = tg; vW = p; vt = t; vUv = aUv; vVar = aRnd.w; vCol = aCol; vN = nW; vGuard = aRnd.y;
  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
}`;
const FUR_FS = `
uniform vec3 uColor; uniform sampler2D uMap; uniform float uHasMap; uniform float uHasCol; varying vec3 vCol; uniform vec3 uSunDir; uniform vec3 uSunCol; uniform vec3 uSky; uniform vec3 uGround; uniform vec3 uRimDir; uniform vec3 uRimCol;
varying vec3 vT; varying vec3 vW; varying float vt; varying vec2 vUv; varying float vVar; varying vec3 vN; varying float vGuard;
void main(){
  vec3 base = uHasCol > .5 ? vCol : uHasMap > .5 ? texture2D(uMap, vUv).rgb : uColor;
  base *= .9 + vVar * .2; base = mix(base * .86, base * (1.06 + vGuard * .14), smoothstep(0., 1., vt)); // у ости кончик светлее
  vec3 T = normalize(vT); vec3 V = normalize(cameraPosition - vW); vec3 L = normalize(uSunDir), Lr = normalize(uRimDir);
  // волосок по модели Маршнера: R — белый блик (к корню), TRT — цветной блик (к кончику), TT — свет насквозь (контровой)
  float sTL = clamp(dot(T, L), -1., 1.), sTV = clamp(dot(T, V), -1., 1.), sTR = clamp(dot(T, Lr), -1., 1.);
  float diff = sqrt(max(0., 1. - sTL * sTL));
  float thH = .5 * (asin(sTL) + asin(sTV)), thR = .5 * (asin(sTR) + asin(sTV));
  float Rl = exp(-pow((thH + .07) / .1, 2.)), TRT = exp(-pow((thH - .14) / .2, 2.));
  vec3 Vp = V - T * sTV; float vl = length(Vp); Vp = vl > 1e-4 ? Vp / vl : vec3(0.);
  vec3 Lp = L - T * sTL; float ll = length(Lp); Lp = ll > 1e-4 ? Lp / ll : vec3(0.);
  vec3 Rp = Lr - T * sTR; float rl = length(Rp); Rp = rl > 1e-4 ? Rp / rl : vec3(0.);
  float TT = smoothstep(-.3, -.95, dot(Lp, Vp)) * exp(-pow(thH / .25, 2.)), TTr = smoothstep(-.2, -.95, dot(Rp, Vp)) * exp(-pow(thR / .3, 2.));
  // тень от самого тела: шерсть на стороне, отвёрнутой от солнца, темнее; у корней — глубже в шубке, темнее
  vec3 Nn = normalize(vN); float lit = mix(.42, 1., smoothstep(-.3, .45, dot(Nn, L))); float sil = smoothstep(.4, .95, 1. - abs(dot(Nn, V)));
  float ao = mix(.7, 1.0, smoothstep(0., .85, vt));
  vec3 amb = mix(uGround, uSky, .5 + .5 * mix(Nn.y, T.y, .3)) * .45; amb = mix(vec3(dot(amb, vec3(.333))), amb, .25);
  vec3 c = base * (amb + uSunCol * diff * .85 * lit) * ao
         + uSunCol * (Rl * .2 + TRT * base * .45) * ao * lit
         + uSunCol * base * TT * .9 * vt * max(lit - .3, sil) + uRimCol * base * TTr * .55 * vt * sil;
  c = max(mix(vec3(dot(c, vec3(.299, .587, .114))), c, 1.15), 0.);
  gl_FragColor = vec4(c, mix(.7, .36, vt)); // со сглаживанием ×4 волосок «тоньше пикселя»: прозрачность → доля покрытия
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
const furMats = [];
function strandMat(src) {
  const m = new THREE.ShaderMaterial({ vertexShader: FUR_VS, fragmentShader: FUR_FS, toneMapped: true, alphaToCoverage: !MK3D._noA2C,
    uniforms: { uNk: { value: .75 }, uCk: { value: .45 }, uLen: { value: .05 }, uLag: { value: new THREE.Vector3() }, uGrav: { value: .2 }, uTime: { value: 0 }, uColor: { value: src.color.clone() }, uMap: { value: src.map || null }, uHasMap: { value: src.map ? 1 : 0 }, uHasCol: { value: 0 },
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
function addHairStrands(rig) {
  const keep = []; for (const e of rig.eyes) { const w = new THREE.Vector3(); e.g.getWorldPosition(w); keep.push([w, e.eR * 1.6]); }
  rig.root.updateMatrixWorld(true); const st = (rig.n.hair || {}).style || 'short', male = rig.n.spec.gender !== 'f';
  rig.head.traverse(o => { if (!o.isMesh || !o.userData.hair) return; o.geometry.computeBoundingSphere(); const long = st === 'long' || st === 'bob' || st === 'ponytail' || st === 'pigtails';
    addStrands(rig, o, st === 'curly' ? .02 : long ? .045 : male ? .022 : .03, keep, 1, 'hair'); });
  rig.fur = []; rig.root.traverse(o => { if (o.userData.strands) rig.fur.push(o); });
}
function addStrands(rig, o, L, keep, furK, reg) { if (reg === 'tail' && (rig.kind === 'mouse' || rig.kind === 'pig')) return; /* хвостик у мышки и поросёнка голый */ furK = (furK || 1) * ({ tail: 1.45, leg: .7, arm: .8, body: 1.05, head: 1, hair: 1 })[reg || 'body'];
  const headW = new THREE.Vector3(); rig.head.getWorldPosition(headW); const hr = rig.P.head; let inHead = false; { let pp = o; while (pp) { if (pp === rig.head) inHead = true; pp = pp.parent; } }
  const fwd = new THREE.Vector3(0, 0, 1).applyQuaternion(rig.head.getWorldQuaternion(new THREE.Quaternion())).normalize();
  // откуда «растёт» шерсть: голова — от носа назад, тело — от шеи к хвосту и вниз, лапы — от плеча/бедра к пальчикам, хвост — к кончику
  const groomed = reg !== 'hair' && !FEATHER_KINDS.has(rig.kind); let src = null, dnK = .3;
  if (groomed) { const isIn = gg => { let pp = o; while (pp) { if (pp === gg) return true; pp = pp.parent; } return false; }; const hsW = rig.head.getWorldScale(new THREE.Vector3()).y;
    if (reg === 'head') src = rig.noseM ? rig.noseM.getWorldPosition(new THREE.Vector3()) : rig.head.localToWorld(new THREE.Vector3(0, -.15 * hr, 1.15 * hr));
    else if (reg === 'body') { src = headW.clone(); src.y -= hr * hsW * .8; dnK = .35; }
    else if (reg === 'tail' && rig.tail) { src = rig.tail.getWorldPosition(new THREE.Vector3()); dnK = .05; }
    else { const lg = (reg === 'leg' ? rig.legs : rig.arms).find(isIn); if (lg) { src = lg.getWorldPosition(new THREE.Vector3()); dnK = .15; } } }
  const mz = groomed && inHead ? (rig.muzzle || (rig.noseM ? { c: [0, rig.noseM.position.y / hr - .12, rig.noseM.position.z / hr - .24], r: [.33, .26, .38] } : null)) : null;
  const Minv = new THREE.Matrix3().setFromMatrix4(o.matrixWorld).invert(), Gd = new THREE.Vector3(), Nw = new THREE.Vector3(), DN = new THREE.Vector3(0, -1, 0);
  const g = o.geometry, pos = g.attributes.position, nor = g.attributes.normal, uv = g.attributes.uv, vc = g.attributes.color; if (!pos || !nor) return;
  const idx = g.index ? g.index.array : null, triN = idx ? idx.length / 3 : pos.count / 3;
  const sx = o.scale.x, sy = o.scale.y, sz = o.scale.z; const wsc = new THREE.Vector3(); o.getWorldScale(wsc); const ws = (wsc.x + wsc.y + wsc.z) / 3;
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), areas = new Float32Array(triN); let tot = 0;
  for (let i = 0; i < triN; i++) { const i0 = idx ? idx[i * 3] : i * 3, i1 = idx ? idx[i * 3 + 1] : i * 3 + 1, i2 = idx ? idx[i * 3 + 2] : i * 3 + 2;
    a.fromBufferAttribute(pos, i0).multiply(wsc); b.fromBufferAttribute(pos, i1).multiply(wsc); c.fromBufferAttribute(pos, i2).multiply(wsc); const ar = b.sub(a).cross(c.sub(a)).length() / 2; tot += ar; areas[i] = tot; }
  const DENS = rig.kind === 'chick' ? 95000 : 64000; let count = Math.min(100000, Math.round(tot * DENS)); if (count < 50) return;
  const SEG = 4, r = rng(global.MK.hash32(rig.spec.name + o.uuid.slice(0, 4)) || 7);
  const aGroom = new Float32Array(count * SEG * 2 * 4), aTilt = new Float32Array(count * SEG * 2 * 3), aCol = new Float32Array(count * SEG * 2 * 3); const aRoot = new Float32Array(count * SEG * 2 * 3), aNorm = new Float32Array(count * SEG * 2 * 3), aUv = new Float32Array(count * SEG * 2 * 2), aRnd = new Float32Array(count * SEG * 2 * 4), aT = new Float32Array(count * SEG * 2);
  const pa = new THREE.Vector3(), pb = new THREE.Vector3(), pc = new THREE.Vector3(), na = new THREE.Vector3(), nb = new THREE.Vector3(), nc = new THREE.Vector3(), P = new THREE.Vector3(), N = new THREE.Vector3(), Wp = new THREE.Vector3();
  let v = 0, made = 0;
  for (let s = 0; s < count; s++) {
    const x = r() * tot; let lo = 0, hi = triN - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (areas[m] < x) lo = m + 1; else hi = m; }
    const i0 = idx ? idx[lo * 3] : lo * 3, i1 = idx ? idx[lo * 3 + 1] : lo * 3 + 1, i2 = idx ? idx[lo * 3 + 2] : lo * 3 + 2;
    let u1 = r(), u2 = r(); if (u1 + u2 > 1) { u1 = 1 - u1; u2 = 1 - u2; } const w0 = 1 - u1 - u2;
    pa.fromBufferAttribute(pos, i0); pb.fromBufferAttribute(pos, i1); pc.fromBufferAttribute(pos, i2); P.set(0, 0, 0).addScaledVector(pa, w0).addScaledVector(pb, u1).addScaledVector(pc, u2);
    na.fromBufferAttribute(nor, i0); nb.fromBufferAttribute(nor, i1); nc.fromBufferAttribute(nor, i2); N.set(0, 0, 0).addScaledVector(na, w0).addScaledVector(nb, u1).addScaledVector(nc, u2).normalize();
    Wp.copy(P).applyMatrix4(o.matrixWorld); let skip = false, near = 9; for (const [kp, kr] of keep) { const d = Wp.distanceTo(kp) / kr; if (d < 1) { skip = true; break; } near = Math.min(near, d); } if (skip) continue;
    if (rig.hats) { let hid = false; for (const h of rig.hats) { const lp = h.worldToLocal(Wp.clone()); if (lp.y > h.userData.hatCut) { hid = true; break; } } if (hid) continue; } // под шапкой шерсть не растёт
    let cr = 0, cg = 0, cb = 0; if (vc) { cr = vc.getX(i0) * w0 + vc.getX(i1) * u1 + vc.getX(i2) * u2; cg = vc.getY(i0) * w0 + vc.getY(i1) * u1 + vc.getY(i2) * u2; cb = vc.getZ(i0) * w0 + vc.getZ(i1) * u1 + vc.getZ(i2) * u2;
      const cB = g.attributes.aColB, mx = g.attributes.aMix; let tm = 0; if (cB && mx) { const sv = mx.getX(i0) * w0 + mx.getX(i1) * u1 + mx.getX(i2) * u2; tm = sv > 0 ? 1 : 0; if (tm) { cr = cB.getX(i0) * w0 + cB.getX(i1) * u1 + cB.getX(i2) * u2; cg = cB.getY(i0) * w0 + cB.getY(i1) * u1 + cB.getY(i2) * u2; cb = cB.getZ(i0) * w0 + cB.getZ(i1) * u1 + cB.getZ(i2) * u2; } }
      const pa = g.attributes.aPat, pt = o.material.userData.pat; if (pa && pt && global.MKSculpt) { const qx = pa.getX(i0) * w0 + pa.getX(i1) * u1 + pa.getX(i2) * u2, qy = pa.getY(i0) * w0 + pa.getY(i1) * u1 + pa.getY(i2) * u2, qz = pa.getZ(i0) * w0 + pa.getZ(i1) * u1 + pa.getZ(i2) * u2, qw = Math.max(pa.getW(i0), pa.getW(i1), pa.getW(i2));
        const w = qw > .5 ? global.MKSculpt.patW(pt.mode, pt.n, qx, qy, qz) * (qw > 1.5 ? 1 - tm : 1) : 0; cr *= 1 + (pt.ratio[0] - 1) * w; cg *= 1 + (pt.ratio[1] - 1) * w; cb *= 1 + (pt.ratio[2] - 1) * w; } }
    let U = 0, Vv = 0; if (uv) { U = uv.getX(i0) * w0 + uv.getX(i1) * u1 + uv.getX(i2) * u2; Vv = uv.getY(i0) * w0 + uv.getY(i1) * u1 + uv.getY(i2) * u2; }
    let faceK = 1; if (inHead && reg !== 'hair') { const d = Wp.clone().sub(headW); const f = d.dot(fwd) / Math.max(1e-3, d.length()); // f=1 — самый перед мордочки
      faceK = f > .15 ? .3 + .7 * (1 - Math.min(1, (f - .15) / .55)) : 1; faceK = Math.max(.28, faceK); if (d.y < -hr * .15 && f > .3) faceK = Math.min(faceK, .32); }
    if (faceK < .4 && r() < .2) continue; // на мордочке шерсть ещё и реже
    // сама мордочка (нос, подушечки с усами, рот, подбородок) — гладкая, без волосков: иначе они выглядят как седая щетина
    const lp = groomed && inHead ? rig.head.worldToLocal(Wp.clone()).divideScalar(hr) : null;
    let lie = 1; if (mz) { const q = Math.hypot((lp.x - mz.c[0]) / mz.r[0], (lp.y - mz.c[1]) / mz.r[1], (lp.z - mz.c[2]) / mz.r[2]);
      if (q < 1) continue; if (q < 1.5) { const e = (q - 1) / .5; faceK = Math.min(faceK, .25 + .5 * e); lie = 2.6 - 1.2 * e; } }
    if (groomed && faceK < 1) lie = Math.max(lie, 1 + (1 - faceK) * 1.6); // на лице шерстка короткая и прижатая
    let ruff = 1; if (lp && rig.kind === 'cat') { const sd = Math.abs(lp.x); // кот: пушистые «бакенбарды» по бокам щёк и кисточки на кончиках ушей
      if (sd > .5 && lp.y < .15 && lp.y > -.62 && lp.z < .8) { ruff = 1 + Math.min(.85, (sd - .5) * 2.6) * Math.min(1, (lp.y + .62) * 3); lie = Math.min(lie, .75); }
      if (lp.y > 1.12) { ruff = 1 + Math.min(2.2, (lp.y - 1.12) * 9); lie = .6; } }
    let regK = 1; if (reg === 'body') { const d = Wp.clone().sub(headW); const f = d.dot(fwd); if (f > .05) regK *= 1 + Math.min(.35, f * 1.8); if (N.y > .5) regK *= 1.25; /* грудка и воротник — пышнее */ }
    if (reg === 'tail') { const tipK = .8 + Math.max(0, -P.z) * 2; regK *= Math.min(1.5, tipK); }
    const guard = groomed && faceK > .95 && r() < .12 ? 1 : 0; // ость: редкие волоски чуть длиннее и со светлым кончиком, под ними — густой подшёрсток
    const lenK = (.9 + r() * .15) * (near < 1.8 ? .45 + .55 * (near - 1) / .8 : 1) * faceK * furK * regK * ruff * (guard ? 1.32 : 1), ty = (r() - .5), tz = (r() - .5), vr = r();
    let gx = 0, gy = 0, gz = 0; if (src) { Gd.copy(Wp).sub(src); const gl0 = Gd.length(); if (gl0 > 1e-6) Gd.divideScalar(gl0); Gd.addScaledVector(DN, dnK); Nw.copy(N).transformDirection(o.matrixWorld); Gd.addScaledVector(Nw, -Gd.dot(Nw));
      if (Gd.lengthSq() > 1e-6) { Gd.applyMatrix3(Minv).normalize(); gx = Gd.x; gy = Gd.y; gz = Gd.z; } }
    if (guard) lie *= .8;
    // пряди: волоски в одной ячейке тянутся к общему центру
    const CELL = .035 / ws, cx = Math.floor(P.x / CELL), cy = Math.floor(P.y / CELL), cz = Math.floor(P.z / CELL);
    const h = global.MK.hash32(cx + ',' + cy + ',' + cz + o.uuid.slice(0, 2)) / 4294967296, h2 = global.MK.hash32(cz + ';' + cy + ';' + cx) / 4294967296;
    const ctr = new THREE.Vector3((cx + .5) * CELL, (cy + .5) * CELL, (cz + .5) * CELL); const pull = ctr.sub(P); pull.addScaledVector(N, -pull.dot(N)); if (pull.lengthSq() > 1e-9) pull.normalize();
    const tan1 = new THREE.Vector3().crossVectors(N, Math.abs(N.y) < .95 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0)).normalize(), tan2 = new THREE.Vector3().crossVectors(N, tan1);
    const tilt = pull.multiplyScalar(.07 * (.5 + h)).addScaledVector(tan1, (h - .5) * .14 + ty * .08).addScaledVector(tan2, (h2 - .5) * .14 + tz * .08);
    P.addScaledVector(N, .002 / ws);
    for (let k = 0; k < SEG; k++) for (const tt of [k / SEG, (k + 1) / SEG]) {
      aRoot.set([P.x, P.y, P.z], v * 3); aNorm.set([N.x, N.y, N.z], v * 3); aCol[v * 3] = cr; aCol[v * 3 + 1] = cg; aCol[v * 3 + 2] = cb; aTilt.set([tilt.x, tilt.y, tilt.z], v * 3); aUv.set([U, Vv], v * 2); aRnd.set([lenK, guard, tz, vr], v * 4); aGroom.set([gx, gy, gz, lie], v * 4); aT[v] = tt; v++; }
    made++;
  }
  if (!made) return;
  const geo = new THREE.BufferGeometry(); const n = v;
  geo.setAttribute('position', new THREE.BufferAttribute(aRoot.slice(0, n * 3), 3)); geo.setAttribute('aRoot', new THREE.BufferAttribute(aRoot.slice(0, n * 3), 3)); geo.setAttribute('aNorm', new THREE.BufferAttribute(aNorm.slice(0, n * 3), 3));
  geo.setAttribute('aUv', new THREE.BufferAttribute(aUv.slice(0, n * 2), 2)); geo.setAttribute('aRnd', new THREE.BufferAttribute(aRnd.slice(0, n * 4), 4)); geo.setAttribute('aT', new THREE.BufferAttribute(aT.slice(0, n), 1)); geo.setAttribute('aTilt', new THREE.BufferAttribute(aTilt.slice(0, n * 3), 3)); geo.setAttribute('aCol', new THREE.BufferAttribute(aCol.slice(0, n * 3), 3)); geo.setAttribute('aGroom', new THREE.BufferAttribute(aGroom.slice(0, n * 4), 4));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 10);
  const m = strandMat(o.material); m.uniforms.uHasCol.value = vc ? 1 : 0; m.uniforms.uLen.value = L / ws; if (reg === 'hair') { m.uniforms.uNk.value = .22; m.uniforms.uCk.value = 1.0; m.uniforms.uGrav.value = .5; } else if (groomed) { m.uniforms.uNk.value = .5; m.uniforms.uCk.value = .8; m.uniforms.uGrav.value = .1; } /* шёрстка лежит по телу, а не торчит */ const ls = new THREE.LineSegments(geo, m); ls.frustumCulled = false; ls.userData.strands = true; ls.castShadow = false; o.add(ls);
  // базовая поверхность чуть темнее — это «подшёрсток» у корней
  { const src0 = o.material; o.material = src0.clone(); if (src0.onBeforeCompile) { o.material.onBeforeCompile = src0.onBeforeCompile; o.material.customProgramCacheKey = src0.customProgramCacheKey; } } o.material.color.multiplyScalar(rig.kind === 'chick' || reg === 'hair' ? 1 : .9); o.material.sheen = 0; if (rig.kind === 'chick') m.uniforms.uColor.value.multiplyScalar(.93);
}
// телосложение: худенький / обычный / пухленький / высокий / крепкий / кругленький
const BUILD_K = { // ширина, глубина, высота тела, длина и толщина ног и рук, голова
  slim:   { bx: .7, bz: .74, by: 1.1, legL: 1.6, legR: .78, armL: 1.3, armR: .78, head: .96 },
  normal: { bx: .86, bz: .88, by: 1.04, legL: 1.25, legR: .92, armL: 1.12, armR: .92, head: 1 },
  chubby: { bx: 1.06, bz: 1.08, by: .98, legL: .95, legR: 1.08, armL: .98, armR: 1.06, head: 1 },
  tall:   { bx: .74, bz: .78, by: 1.22, legL: 1.95, legR: .84, armL: 1.5, armR: .84, head: .92 },
  stocky: { bx: .98, bz: .94, by: 1.06, legL: 1.1, legR: 1.18, armL: 1.15, armR: 1.22, head: .95 },
  round:  { bx: 1, bz: 1, by: 1, legL: 1, legR: 1, armL: 1, armR: 1, head: 1 } };
function applyBuild(P, b, human, kind) {
  if (human) { const h = { slim: [.8, .85], chubby: [1.28, 1.12], stocky: [1.12, 1.15], tall: [.88, .9] }[b]; if (h) { P.torsoR *= h[0]; P.armR *= h[1]; P.legR *= h[1]; P.legX *= Math.max(.85, h[0] * .95); P.shX *= Math.max(.9, h[0] * .92); } return; }
  const K = BUILD_K[b] || BUILD_K.normal, o = Object.assign({}, P);
  P.bx = o.bx * K.bx; P.bz = o.bz * K.bz; P.by = o.by * K.by; P.legL = o.legL * K.legL; P.legR = o.legR * K.legR; P.armL = o.armL * K.armL; P.armR = o.armR * K.armR; P.head = o.head * K.head;
  const dLeg = (P.legL - o.legL) + (P.legR - o.legR) * 1.45;
  P.hip = o.hip + dLeg; P.bodyY = o.bodyY + dLeg + (P.by - o.by); P.shY = P.bodyY + (o.shY - o.bodyY) * (P.by / o.by);
  P.headY = P.bodyY + (o.headY - o.bodyY) + (P.by - o.by) * .9 + (P.head - o.head);
  P.shX = o.shX * K.bx + (P.armR - o.armR); P.legX = Math.max(P.legR * 1.15, o.legX * K.bx);
}
function buildRig0(spec) {
  const n = global.MK.normChar(spec), c = n.c, k = n.kind, human = n.human, adult = n.adult, O = spec.outfit || {};
  const R0 = new THREE.Group(); // корень: позиция
  const yaw = new THREE.Group(); R0.add(yaw);
  const rollG = new THREE.Group(); yaw.add(rollG);
  const pose = new THREE.Group(); rollG.add(pose);
  const rig = { root: R0, yaw, rollG, pose, kind: k, human, eyes: [], lids: [], brows: [], arms: [], legs: [], spec, n };
  const P = human ? (adult ? { hip: .8, legL: .62, bodyY: 1.08, head: .175, headY: 1.6, shY: 1.34, shX: .215, armL: .5, legX: .09, legR: .068, armR: .052, torsoR: .18, torsoL: .5 }
                           : { hip: .42, legL: .3, bodyY: .62, head: .235, headY: 1.0, shY: .8, shX: .165, armL: .27, legX: .072, legR: .057, armR: .044, torsoR: .145, torsoL: .3 })
                   : (adult ? { hip: .26, legL: .17, bodyY: .54, head: .31, headY: 1.08, shY: .74, shX: .3, armL: .2, legX: .14, legR: .085, armR: .068, bx: .34, by: .42, bz: .3 }
                            : { hip: .24, legL: .13, bodyY: .45, head: .34, headY: .98, shY: .64, shX: .27, armL: .16, legX: .13, legR: .075, armR: .06, bx: .32, by: .36, bz: .29 });
  applyBuild(P, (spec.build || (global.MKMaker ? global.MKMaker.defaultBuild(spec) : 'normal')), human, k); rig.build = spec.build;
  rig.P = P; const bodyC = human ? c.skin : c.body, pawC = human ? c.skin : (n.pattern.includes('socks') ? c.belly : c.body);
  const furMap = !human && n.pattern.includes('stripes') ? stripeTex(c.body, c.stripe, 7, 30, 92) : !human && n.pattern.includes('spots') ? spotTex(c.body, c.stripe, n.seed) : null;
  const headMap = !human && n.pattern.includes('stripes') ? stripeTex(c.body, c.stripe, 10, 4, 46) : null;
  const legC = O.overalls || O.pants || (human ? c.pants : null);
  // ноги
  if (human) buildHumanLegs(rig, pose, P, n, O, c);
  else for (const s of [-1, 1]) {
    const g = new THREE.Group(); g.position.set(s * P.legX, P.hip, 0); pose.add(g);
    const leg = mesh(G.cap(P.legR, P.legL), toon(legC || (human ? c.pants : c.body)), .06, g); leg.position.y = -P.legL / 2 - P.legR * .3;
    const foot = mesh(G.sph(P.legR * 1.35, 20, 14), toon(human ? (O.shoes || c.shoes) : (O.shoes || pawC)), .06, g); foot.position.set(0, -P.legL - P.legR * .6, P.legR * .5); foot.scale.set(1, .75, 1.3);
    if (!human && !O.shoes && global.MKSculpt && FUR_KINDS.has(k) && !FEATHER_KINDS.has(k)) { const R = P.legR * 1.35; for (const sx of [-1, 1]) { const gr = new THREE.Mesh(G.sph(1, 8, 6), toon(pawC)); gr.visible = false; gr.userData.groove = true; gr.position.set(sx * R * .3, foot.position.y + R * .12, foot.position.z + R * 1.2); gr.scale.set(R * .05, R * .32, R * .26); g.add(gr); } }
    rig.legs.push(g);
  }
  // тело
  const body = new THREE.Group(); body.position.y = P.bodyY; pose.add(body); rig.body = body;
  if (human) buildHumanTorso(rig, body, P, n, O, c);
  else {
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
  if (human) buildHumanArms(rig, pose, P, n, O, c);
  else for (const s of [-1, 1]) {
    const g = new THREE.Group(); g.position.set(s * P.shX, P.shY, 0); pose.add(g);
    const sleeveC = human ? (O.shirt || c.shirt) : (O.shirt || c.body);
    const arm = mesh(G.cap(P.armR, P.armL), toon(sleeveC), .06, g); arm.position.y = -P.armL / 2 - P.armR * .3;
    const hand = mesh(G.sph(P.armR * 1.25, 18, 12), toon(pawC), .06, g); hand.position.y = -P.armL - P.armR * .8;
    if (!human && global.MKSculpt && FUR_KINDS.has(k) && !FEATHER_KINDS.has(k)) { const r = P.armR * 1.25; for (const sx of [-1, 1]) { const gr = new THREE.Mesh(G.sph(1, 8, 6), toon(pawC)); gr.visible = false; gr.userData.groove = true; gr.position.set(sx * r * .3, hand.position.y - r * .78, r * .5); gr.scale.set(r * .05, r * .3, r * .32); g.add(gr); } }
    const anchor = new THREE.Object3D(); anchor.position.set(0, -P.armL - P.armR * 1.6, .06); g.add(anchor);
    g.userData.side = s; rig.arms.push(g); if (s > 0) rig.hand = anchor;
  }
  // голова
  const head = new THREE.Group(); head.position.y = P.headY; pose.add(head); rig.head = head;
  const hr = P.head;
  if (human) buildHumanHead(rig, head, hr, n, c);
  else {
    const sk = mesh(G.sph(hr, 40, 30), headMap ? toon(null, headMap) : toon(c.body), .035, head); sk.scale.set(1.08, .94, 1);
    if (k === 'cat') { sk.scale.set(1.04, .9, .97); /* кошачья голова: широкие скулы и щёки внизу, лоб площе — силуэт «скруглённый треугольник», а не шар */
      for (const s of [-1, 1]) { const ck = mesh(G.sph(1, 28, 20), toon(c.body), .035, head); ck.scale.set(hr * .5, hr * .42, hr * .5); ck.position.set(s * hr * .6, -hr * .24, hr * .26); }
      const fh = mesh(G.sph(1, 28, 20), headMap ? toon(null, headMap) : toon(c.body), .035, head); /* лоб — с полосками */ fh.scale.set(hr * .78, hr * .5, hr * .6); fh.position.set(0, hr * .3, hr * .32); }
    buildAnimalFace(head, hr, n, rig);
  }
  // глаза
  const frog = k === 'frog', owlE = k === 'owl';
  const eyeY = human ? hr * .08 : frog ? hr * .75 : hr * .18, eyeX = human ? hr * .36 : frog ? hr * .45 : hr * .38, eyeZ = hr * (human ? .88 : frog ? .45 : .8), eR = hr * (human ? .2 : frog ? .3 : owlE ? .3 : .25);
  for (const s of [-1, 1]) {
    const g = new THREE.Group(); g.position.set(s * eyeX, eyeY, eyeZ); head.add(g);
    const catE = k === 'cat', iK = catE ? 1.12 : 1; // у кота радужка крупнее, но белок белый и виден
    const w = mesh(frontUV(G.sph(eR, 32, 24)), toon(null, scleraT()), .08, g); w.scale.set(1, 1.2, .6);
    const ir = new THREE.Mesh(frontUV(G.sph(eR * .68 * iK, 32, 24)), toon(null, irisT(c.eyes))); ir.position.z = eR * (catE ? .36 : .42); ir.scale.set(1, 1.15, .5); g.add(ir);
    const pu = new THREE.Mesh(G.sph(eR * (catE ? .4 : .38), 16, 12), basic('#16100c')); pu.position.z = eR * (catE ? .62 : .65); pu.scale.set(1, 1.15, .5); g.add(pu);
    const hl = new THREE.Mesh(G.sph(eR * .16, 10, 8), basic('#ffffff')); hl.position.set(-eR * .2, eR * .3, eR * .82); g.add(hl);
    if (MK3D.hq) { w.material = eyeGloss(scleraT(), .25); ir.material = eyeGloss(irisT(c.eyes), .2); pu.material = basic('#120c08'); const h2 = new THREE.Mesh(G.sph(eR * .07, 8, 6), basic('#ffffff')); h2.position.set(eR * .18, -eR * .12, eR * .84); g.add(h2);
      const cor = new THREE.Mesh(G.sph(eR * .72 * iK, 20, 14), new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: .12, roughness: .12, clearcoat: 1, clearcoatRoughness: .1, transmission: 0 })); cor.position.z = eR * (catE ? .4 : .46); cor.scale.set(1, 1.15, .55); g.add(cor); }
    const heart = makeHeart(eR * .7); heart.position.z = eR * .5; heart.visible = false; g.add(heart);
    const lid = new THREE.Mesh(new THREE.SphereGeometry(eR * 1.08, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), toon(bodyC)); lid.scale.set(1, 1.2, .62); g.add(lid);
    if (catE) { lid.scale.set(1.04, 1.2, 1.0); /* веко накрывает и выпуклую радужку */ lid.material = new THREE.MeshStandardMaterial({ color: new THREE.Color(bodyC).multiplyScalar(.9), roughness: .9 });
      if (MK3D.hq) w.material = new THREE.MeshPhysicalMaterial({ color: 0xffffff, emissive: 0x3a3836, roughness: .25, clearcoat: 1, clearcoatRoughness: .07 }); /* белок белый, не серый */ const lnC = new THREE.Color(c.stripe || c.body).multiplyScalar(.35).getStyle(); // тёмная «подводка» по краю века и снизу глаза
      const ln = new THREE.Mesh(new THREE.TorusGeometry(eR * 1.08, eR * .055, 8, 40, Math.PI), basic(lnC)); ln.rotation.x = Math.PI / 2; lid.add(ln);
      const lo = new THREE.Mesh(new THREE.TorusGeometry(eR * .99, eR * .045, 8, 40, Math.PI * .8), basic(lnC)); lo.rotation.z = Math.PI * 1.1; lo.scale.set(1.02, 1.22, 1); lo.position.z = -eR * .02; g.add(lo); g.userData.liner = lo; }
    const brow = new THREE.Mesh(G.cap(eR * .13, eR * .9), basic(human ? new THREE.Color(n.hair.color || c.hair).multiplyScalar(.7).getStyle() : new THREE.Color(c.body).multiplyScalar(.55).getStyle()));
    brow.rotation.z = Math.PI / 2; brow.position.set(0, eR * 1.55, eR * .2); g.add(brow);
    if (human && (spec.gender === 'f' || /(pigtails|long|ponytail|bun|bob)/.test((n.hair || {}).style || ''))) for (let q = 0; q < 3; q++) { const ls = new THREE.Mesh(G.cap(eR * .05, eR * .3, 2, 6), basic('#2a1a14')); ls.position.set((q - 1) * eR * .45 + s * eR * .15, eR * 1.12 - Math.abs(q - 1) * eR * .08, eR * .35); ls.rotation.z = (q - 1) * -.5 + s * .5; lid.add(ls); }
    rig.eyes.push({ g, ir, pu, heart, lid, brow, s, eR });
  }
  // щёки
  for (const s of [-1, 1]) { const ch = new THREE.Mesh(G.sph(hr * .13, 14, 10), new THREE.MeshBasicMaterial({ color: 0xff8fa0, transparent: true, opacity: .45 })); ch.position.set(s * hr * .62, -hr * .18, hr * .75); ch.scale.set(1, .6, .3); head.add(ch); rig.cheeks = (rig.cheeks || []).concat(ch); }
  // рот
  const mY = !human && rig.mouthAt ? hr * rig.mouthAt[0] : -hr * .42, mZ = !human && rig.mouthAt ? hr * rig.mouthAt[1] : hr * .9;
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
  const sc = n.size * (adult && human ? 1 : 1); R0.scale.setScalar(sc); rig.scale = sc; R0.updateMatrixWorld(true); rig.headH = new THREE.Vector3().setFromMatrixPosition(head.matrixWorld).y - R0.position.y; rig.headR = hr * sc;
  if (MK3D.hq) rig.blob = contactShadow(R0, human ? .45 : .6);
  return rig;
}
// ---------- живые глаза: радужка с волокнами, тёмный ободок, светлое кольцо у зрачка, тень от века; белок с мягкой тенью по краю ----------
function frontUV(geo) { const p = geo.attributes.position, uv = geo.attributes.uv; geo.computeBoundingSphere(); const r = geo.boundingSphere.radius; for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) / (2 * r) + .5, p.getY(i) / (2 * r) + .5); uv.needsUpdate = true; return geo; }
function irisT(c) { return ctex('iris' + c, 256, 256, (g) => { const C = new THREE.Color(c), hsl = {}; C.getHSL(hsl); const at = (l, s) => '#' + new THREE.Color().setHSL(hsl.h, Math.min(1, hsl.s * (s || 1)), Math.max(0, Math.min(1, l))).getHexString();
  const cx = 128, cy = 128, R = 92; g.fillStyle = at(hsl.l * .35); g.fillRect(0, 0, 256, 256);
  const gr = g.createRadialGradient(cx, cy, 6, cx, cy, R); gr.addColorStop(0, at(hsl.l * 1.25 + .12, .9)); gr.addColorStop(.38, at(hsl.l * 1.12 + .05)); gr.addColorStop(.7, at(hsl.l * .95, 1.1)); gr.addColorStop(.92, at(hsl.l * .6, 1.15)); gr.addColorStop(1, at(hsl.l * .28)); g.fillStyle = gr; g.beginPath(); g.arc(cx, cy, R, 0, 7); g.fill();
  const r = rng(global.MK.hash32(c)); g.lineCap = 'round';
  for (let i = 0; i < 220; i++) { const a = i / 220 * Math.PI * 2 + (r() - .5) * .03, r0 = R * (.22 + r() * .12), r1 = R * (.62 + r() * .33), bend = (r() - .5) * .25; g.strokeStyle = r() < .5 ? 'rgba(255,255,255,' + (.06 + r() * .1) + ')' : 'rgba(0,0,0,' + (.06 + r() * .12) + ')'; g.lineWidth = .8 + r() * 1.6;
    g.beginPath(); g.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0); g.quadraticCurveTo(cx + Math.cos(a + bend) * (r0 + r1) / 2, cy + Math.sin(a + bend) * (r0 + r1) / 2, cx + Math.cos(a) * r1, cy + Math.sin(a) * r1); g.stroke(); }
  for (let i = 0; i < 26; i++) { const a = r() * Math.PI * 2, rr = R * (.45 + r() * .38); g.fillStyle = 'rgba(0,0,0,' + (.08 + r() * .1) + ')'; g.beginPath(); g.ellipse(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, 2 + r() * 4, 1 + r() * 2, a, 0, 7); g.fill(); }
  const ring = g.createRadialGradient(cx, cy, R * .3, cx, cy, R * .48); ring.addColorStop(0, at(hsl.l * 1.3 + .15, .8) + 'cc'); ring.addColorStop(1, at(hsl.l * 1.3 + .15, .8) + '00'); g.fillStyle = ring; g.beginPath(); g.arc(cx, cy, R * .48, 0, 7); g.fill(); // светлое кольцо у зрачка
  g.lineWidth = 7; g.strokeStyle = at(hsl.l * .22) + 'dd'; g.beginPath(); g.arc(cx, cy, R - 3, 0, 7); g.stroke(); // тёмный ободок
  const sh = g.createLinearGradient(0, 0, 0, 190); sh.addColorStop(0, 'rgba(0,0,0,.45)'); sh.addColorStop(.45, 'rgba(0,0,0,.12)'); sh.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = sh; g.fillRect(0, 0, 256, 256); // тень от века сверху
}); }
function scleraT() { return ctex('sclera', 128, 128, (g) => { const gr = g.createRadialGradient(64, 64, 10, 64, 64, 64); gr.addColorStop(0, '#ffffff'); gr.addColorStop(.6, '#fbfaf8'); gr.addColorStop(.85, '#e9e6ec'); gr.addColorStop(1, '#cfcbd6'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const sh = g.createLinearGradient(0, 0, 0, 80); sh.addColorStop(0, 'rgba(90,80,100,.2)'); sh.addColorStop(1, 'rgba(90,80,100,0)'); g.fillStyle = sh; g.fillRect(0, 0, 128, 128); }); }
function eyeGloss(map, rough) { const k = 'eg' + map.uuid + rough; if (matCache[k]) return matCache[k]; return (matCache[k] = new THREE.MeshPhysicalMaterial({ color: 0xffffff, map, roughness: rough, clearcoat: 1, clearcoatRoughness: .07 })); }
function makeHeart(r) { const sh = new THREE.Shape(); sh.moveTo(0, -r * .9); sh.bezierCurveTo(-r * 1.4, -r * .1, -r * .6, r * 1.1, 0, r * .4); sh.bezierCurveTo(r * .6, r * 1.1, r * 1.4, -r * .1, 0, -r * .9); const g = new THREE.ExtrudeGeometry(sh, { depth: r * .2, bevelEnabled: false }); return new THREE.Mesh(g, basic('#e8344e')); }

// ---------- люди ----------
function cottonT(c) { return ctex('cot' + c, 128, 128, (g) => { g.fillStyle = c; g.fillRect(0, 0, 128, 128); const r = rng(31); for (let i = 0; i < 1600; i++) { g.fillStyle = r() < .5 ? 'rgba(0,0,0,.05)' : 'rgba(255,255,255,.06)'; g.fillRect(r() * 128, r() * 128, 1 + r() * 2, 1); } }, [4, 4]); }
function plaidT(c) { return ctex('plaid' + c, 256, 256, (g) => { g.fillStyle = c; g.fillRect(0, 0, 256, 256); const d = shadeC(c, .55), l = lightC(c, .5); g.globalAlpha = .55; g.fillStyle = d; for (let i = 0; i < 256; i += 64) { g.fillRect(i, 0, 22, 256); g.fillRect(0, i, 256, 22); } g.globalAlpha = .5; g.fillStyle = l; for (let i = 40; i < 256; i += 64) { g.fillRect(i, 0, 5, 256); g.fillRect(0, i, 256, 5); } g.globalAlpha = 1; }, [3, 2]); }
function dotsCloth(c) { return ctex('dc' + c, 128, 128, (g) => { g.fillStyle = c; g.fillRect(0, 0, 128, 128); g.fillStyle = '#ffffff'; for (let y = 8; y < 128; y += 32) for (let x = 8 + (y / 32 % 2) * 16; x < 128; x += 32) { g.beginPath(); g.arc(x, y, 5, 0, 7); g.fill(); } }, [4, 3]); }
function clothM(c, O, top) { if (top && O.plaid) return toon(null, plaidT(c)); if (top && O.dots) return toon(null, dotsCloth(c)); if (top && O.stripe) return toon(null, stripeTex(c, O.stripe, 1, 0, 0)); return MK3D.hq ? toon(null, cottonT(c)) : toon(c); }
function shoe(par, P, c, kid) { const g = new THREE.Group(); par.add(g); const L = P.legR * (kid ? 2.5 : 2.7), W = P.legR * 1.45, H = P.legR * 1.05;
  const up = mesh(G.sph(1, 24, 16), toon(c), .05, g); up.scale.set(W, H, L); up.position.set(0, H * .55, L * .25);
  const so = mesh(G.sph(1, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), toon('#f4f1ea'), .04, g); so.scale.set(W * 1.06, H * .45, L * 1.04); so.position.set(0, H * .5, L * .25);
  if (kid) { const t2 = mesh(G.sph(1, 16, 10), toon('#f4f1ea'), 0, g); t2.scale.set(W * .7, H * .5, L * .45); t2.position.set(0, H * .75, L * .78); } return g; }
function buildHumanLegs(rig, pose, P, n, O, c) {
  const kid = !n.adult, skirt = !!O.skirt && !O.pants, shorts = !!O.shorts, pc = O.overalls || O.pants || (skirt ? null : c.pants);
  for (const s of [-1, 1]) { const g = new THREE.Group(); g.position.set(s * P.legX, P.hip, 0); pose.add(g); const L = P.legL;
    if (pc && !shorts) { const lg = mesh(G.cap(P.legR * 1.05, L * .92), clothM(pc, O), .05, g); lg.position.y = -L / 2; const cf = mesh(G.cyl(P.legR * 1.18, P.legR * 1.12, L * .1, 16), clothM(pc, O), .04, g); cf.position.y = -L * .92; }
    else { const lg = mesh(G.cap(P.legR * .85, L * .9), toon(c.skin), .05, g); lg.position.y = -L / 2; if (pc) { const sh = mesh(G.cap(P.legR * 1.18, L * .38), clothM(pc, O), .05, g); sh.position.y = -L * .2; }
      const sk = mesh(G.cyl(P.legR * .95, P.legR * .92, L * .14, 16), toon(kid ? '#ffffff' : (skirt ? '#d8b8a8' : '#ffffff')), .04, g); sk.position.y = -L * .9; }
    const sh = shoe(g, P, O.shoes || c.shoes, kid); sh.position.y = -L - P.legR * .6; rig.legs.push(g); } }
function buildHumanTorso(rig, body, P, n, O, c) {
  const R0 = P.torsoR, L = P.torsoL, kid = !n.adult, male = n.spec.gender !== 'f', shirt = O.shirt || c.shirt;
  const ch = male && !kid ? 1.12 : 1, wa = kid ? .96 : male ? .9 : .78, hp = kid ? .98 : male ? .95 : 1.08;
  const prof = [[R0 * hp * .98, -L * .52], [R0 * hp, -L * .4], [R0 * wa, -L * .1], [R0 * ch, L * .22], [R0 * ch * .95, L * .38], [R0 * .7, L * .5], [R0 * .36, L * .56], [R0 * .3, L * .6]];
  const tor = mesh(lathe(prof, 32), clothM(shirt, O, true), .045, body); tor.scale.z = .78;
  const neck = mesh(G.cyl(R0 * .32, R0 * .36, L * .24, 16), toon(c.skin), .04, body); neck.position.y = L * .62;
  const col = mesh(G.tor(R0 * .38, R0 * .07, 10, 28), toon(shadeC(shirt, .88)), .03, body); col.rotation.x = Math.PI / 2; col.position.y = L * .56; col.scale.z = .85;
  if (!kid && male && !O.overalls && !O.suit) for (let i = 0; i < 3; i++) { const b = mesh(G.sph(R0 * .045, 10, 8), toon(shadeC(shirt, .7)), 0, body); b.position.set(0, L * (.3 - i * .2), R0 * ch * .8); b.scale.z = .5; }
  const pc = O.overalls || O.pants;
  if (pc && !O.skirt) { const pp = [[0, -L * .62], [R0 * hp * 1.01, -L * .6], [R0 * hp * 1.03, -L * .48], [R0 * wa * 1.03, -L * .2], [0, -L * .2]]; const pt = mesh(lathe(pp, 32), clothM(pc, O), .04, body); pt.scale.z = .8;
    if (!O.overalls) { const bl = mesh(G.tor(R0 * wa * 1.03, R0 * .05, 8, 32), toon('#3a2a20'), 0, body); bl.rotation.x = Math.PI / 2; bl.position.y = -L * .22; bl.scale.y = .8; const bk = mesh(G.box(R0 * .2, R0 * .14, R0 * .05), toon('#d8b03a'), 0, body); bk.position.set(0, -L * .22, R0 * wa * .82); } }
  if (O.skirt) { const sl = kid ? L * .62 : L * .95, flare = kid ? 1.75 : 1.5, N = 40, prof2 = [[R0 * hp * flare, -L * .12 - sl], [R0 * hp * 1.08, -L * .4], [R0 * wa * 1.02, -L * .12]];
    const geo = lathe(prof2, N * 2); const pa = geo.attributes.position; for (let i = 0; i < pa.count; i++) { const y = pa.getY(i); if (y < -L * .12 - sl * .9) { const a = Math.atan2(pa.getZ(i), pa.getX(i)); const k = 1 + Math.sin(a * 9) * .05; pa.setX(i, pa.getX(i) * k); pa.setZ(i, pa.getZ(i) * k); pa.setY(i, y + Math.cos(a * 9) * .01); } } geo.computeVertexNormals();
    const sk = mesh(geo, clothM(O.skirt, O, O.skirt === shirt), .035, body); sk.material = sk.material.clone(); sk.material.side = THREE.DoubleSide; sk.scale.z = .85; }
}
function buildHumanArms(rig, pose, P, n, O, c) {
  const kid = !n.adult, shirt = O.shirt || c.shirt, shortSl = kid && !O.suit && !O.pajamas;
  for (const s of [-1, 1]) { const g = new THREE.Group(); g.position.set(s * P.shX, P.shY, 0); pose.add(g); const L = P.armL;
    const sl = mesh(G.cap(P.armR * 1.25, shortSl ? L * .3 : L * .82), clothM(shirt, O, true), .05, g); sl.position.y = shortSl ? -L * .2 : -L * .45;
    if (shortSl) { const fa = mesh(G.cap(P.armR * .9, L * .72), toon(c.skin), .05, g); fa.position.y = -L * .58; }
    else { const cf = mesh(G.cyl(P.armR * 1.28, P.armR * 1.3, L * .08, 14), toon(shadeC(shirt, .88)), .04, g); cf.position.y = -L * .9; }
    const hand = new THREE.Group(); hand.position.y = -L - P.armR * .6; g.add(hand);
    const palm = mesh(G.sph(P.armR * 1.25, 18, 14), toon(c.skin), .05, hand); palm.scale.set(.85, 1.15, .65);
    const th = mesh(G.cap(P.armR * .38, P.armR * .7), toon(c.skin), .05, hand); th.position.set(-s * P.armR * .7, P.armR * .25, P.armR * .45); th.rotation.set(-.5, 0, s * .8);
    const anchor = new THREE.Object3D(); anchor.position.set(0, -L - P.armR * 1.6, .06); g.add(anchor);
    g.userData.side = s; rig.arms.push(g); if (s > 0) rig.hand = anchor; } }
function hairM(cl) { return MK3D.hq ? toon(null, ctex('hairT' + cl, 64, 256, (g) => { g.fillStyle = cl; g.fillRect(0, 0, 64, 256); const r = rng(5); for (let i = 0; i < 90; i++) { g.strokeStyle = r() < .5 ? shadeC(cl, .78) : lightC(cl, .18); g.globalAlpha = .5; g.lineWidth = 1 + r() * 2; const x = r() * 64; g.beginPath(); g.moveTo(x, 0); g.lineTo(x + (r() - .5) * 8, 256); g.stroke(); } g.globalAlpha = 1; }, [6, 1])) : toon(cl); }
function buildHumanHead(rig, head, hr, n, c) {
  const kid = !n.adult, male = n.spec.gender !== 'f';
  const sk = mesh(G.sph(hr, 40, 32), toon(c.skin), .035, head); sk.scale.set(kid ? 1 : .9, kid ? .98 : 1.1, kid ? .97 : .95);
  if (!kid) { const jw = mesh(G.sph(hr * .78, 28, 20), toon(c.skin), 0, head); jw.position.set(0, -hr * .38, hr * .12); jw.scale.set(male ? 1 : .9, .8, .9); }
  for (const s of [-1, 1]) { const e = new THREE.Group(); e.position.set(s * hr * (kid ? .97 : .88), -hr * .05, -hr * .02); e.rotation.y = s * .3; head.add(e);
    const o = mesh(G.sph(hr * .17, 16, 12), toon(c.skin), .06, e); o.scale.set(.45, 1, .75); const i = mesh(G.sph(hr * .1, 12, 8), toon(shadeC(c.skin, .85)), 0, e); i.position.x = s * hr * .03; i.scale.set(.3, .8, .6); }
  const ns = mesh(lathe([[0, 0], [hr * .085, hr * .02], [hr * .1, hr * .08], [hr * .06, hr * .16], [0, hr * .2]], 16), toon(shadeC(c.skin, .96)), .04, head); ns.rotation.x = Math.PI / 2 + .25; ns.position.set(0, -hr * .14, hr * (kid ? .9 : .86)); ns.scale.set(kid ? .9 : 1, kid ? .8 : 1.15, 1);
  buildHair2(head, hr, n, rig);
}
function buildHair2(head, hr, n, rig) {
  const h = n.hair || {}, st = h.style || 'short', cl = h.color || (n.old ? '#d9d9de' : n.c.hair), m = hairM(cl), kid = !n.adult, male = n.spec.gender !== 'f';
  const H = (geo, par, ol) => { const x = mesh(geo, m, ol == null ? .03 : ol, par || head); x.userData.hair = true; return x; };
  if (st === 'bald') { if (n.old) for (const s of [-1, 1]) { const p = H(G.sph(hr * .32, 16, 12)); p.position.set(s * hr * .82, hr * .05, -hr * .25); p.scale.set(.6, 1, 1.2); } return; }
  // «шапочка» волос: спереди линия роста выше, сзади ниже
  const capG = new THREE.Group(); head.add(capG); if (!kid) capG.scale.set(.9 * 1.02, 1.1 * 1.02, .95 * 1.02); else capG.scale.set(1.01, 1.0, 1.0);
  const cap = H(new THREE.SphereGeometry(hr * 1.05, 48, 24, 0, Math.PI * 2, 0, Math.PI * (st === 'short' && male ? .52 : .58)), capG); cap.rotation.x = -.42; cap.position.set(0, hr * .02, -hr * .04);
  // чёлка — несколько прядей
  const nl = st === 'short' && male ? 5 : 6; for (let i = 0; i < nl; i++) { const t = i / (nl - 1) - .5, a = t * 1.9;
    const lk = H(lathe([[0, 0], [hr * .09, hr * .05], [hr * .1, hr * .2], [hr * .05, hr * .34], [0, hr * .4]], 10), head, .02); lk.position.set(Math.sin(a) * hr * .92, hr * .58 - Math.abs(t) * hr * .1, Math.cos(a) * hr * .78);
    lk.rotation.set(Math.PI - .5 + Math.abs(t) * .2, a, -t * 1.2 + (male ? .35 : -.15)); lk.scale.set(1, male ? .75 : .9, .45); }
  if (st === 'short' && male) for (let i = 0; i < 5; i++) { const a = (i - 2) * .5; const tf = H(G.cone(hr * .12, hr * .32, 10), head, .02); tf.position.set(Math.sin(a) * hr * .45, hr * 1.0, Math.cos(a) * hr * .2 - hr * .1); tf.rotation.set(-.6, 0, -a * .7); }
  const curtain = (len, back) => { const g = new THREE.CylinderGeometry(hr * 1.02, hr * 1.18, len, 40, 6, true, back ? Math.PI * .55 : -Math.PI * .45, back ? Math.PI * .9 : Math.PI * 1.9); const x = H(g, head, .02); x.material = x.material.clone(); x.material.side = THREE.DoubleSide; x.position.set(0, -len / 2 + hr * .15, -hr * .06); return x; };
  if (st === 'long' || st === 'bob') { const len = st === 'bob' ? hr * 1.05 : hr * (kid ? 1.9 : 2.3); curtain(len, true);
    for (const s of [-1, 1]) { const sl = H(G.cap(hr * .16, len * .7), head, .02); sl.position.set(s * hr * .95, -len * .3 + hr * .1, hr * .25); sl.scale.set(.7, 1, .9); sl.rotation.z = s * .08; }
    const end = H(G.sph(hr * 1.12, 32, 12, 0, Math.PI * 2, Math.PI * .5, Math.PI * .5), head, .02); end.position.set(0, -len + hr * .2, -hr * .1); end.scale.set(1, .3, .78); }
  if (st === 'pigtails') for (const s of [-1, 1]) { const b = new THREE.Group(); b.position.set(s * hr * 1.0, hr * .1, -hr * .25); b.rotation.z = s * .5; head.add(b);
    const band = mesh(G.tor(hr * .1, hr * .04, 8, 16), toon('#ff4d6d'), .03, b); band.rotation.y = Math.PI / 2;
    for (let i = 0; i < 4; i++) { const p = H(G.sph(hr * (.2 - i * .03), 16, 12), b); p.position.set(s * hr * .05, -hr * (.14 + i * .2), 0); p.scale.set(.85, 1.15, .85); } }
  if (st === 'ponytail') { const cv = new THREE.CatmullRomCurve3([new THREE.Vector3(0, hr * .55, -hr * .85), new THREE.Vector3(0, hr * .3, -hr * 1.3), new THREE.Vector3(0, -hr * .3, -hr * 1.35), new THREE.Vector3(0, -hr * .9, -hr * 1.15)]);
    H(taperTube(cv, 24, t => hr * (.2 - t * .14 + Math.sin(t * Math.PI) * .07), 12), head, .02); const band = mesh(G.tor(hr * .14, hr * .045, 8, 16), toon('#ff4d6d'), .03, head); band.position.set(0, hr * .5, -hr * .92); band.rotation.x = .7; }
  if (st === 'bun') { const b = H(G.sph(hr * .36, 24, 16)); b.position.set(0, hr * (n.old ? .85 : 1.0), -hr * .45); const band = mesh(G.tor(hr * .27, hr * .04, 8, 20), toon(n.old ? '#8a6a8a' : '#ff4d6d'), 0, head); band.position.set(0, hr * (n.old ? .78 : .9), -hr * .38); band.rotation.x = -1.1; }
  if (st === 'curly') for (let i = 0; i < 22; i++) { const a = i / 22 * Math.PI * 2, el = .2 + (i % 3) * .35; const p = H(G.sph(hr * .26, 14, 10)); p.position.set(Math.cos(a) * Math.cos(el) * hr, hr * .35 + Math.sin(el) * hr * .7, Math.sin(a) * Math.cos(el) * hr * .9 - hr * .08); }
  for (const a0 of n.acc) { const a = typeof a0 === 'string' ? { type: a0 } : a0;
    if (a.type === 'beard') { const bd = H(new THREE.SphereGeometry(hr * 1.0, 40, 16, Math.PI / 2 - Math.PI * .5, Math.PI, Math.PI * .63, Math.PI * .3)); bd.position.set(0, -hr * .02, hr * .04); bd.scale.set(kid ? 1 : .94, 1.15, 1.02); bd.material = bd.material.clone(); bd.material.side = THREE.DoubleSide;
      for (const s of [-1, 1]) { const sb = H(G.cap(hr * .13, hr * .42, 4, 10)); sb.position.set(s * hr * .74, -hr * .28, hr * .2); sb.rotation.set(.15, 0, -s * .25); }
      const ch = H(G.sph(hr * .3, 20, 14)); ch.position.set(0, -hr * .78, hr * .48); ch.scale.set(1.25, .85, .8); }
    if (a.type === 'beard' || a.type === 'mustache') for (const s of [-1, 1]) { const ms = H(G.cap(hr * .07, hr * .22, 4, 8)); ms.position.set(s * hr * .14, -hr * .3, hr * .9); ms.rotation.z = s * (Math.PI / 2 - .35); } }
}
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
      const i = new THREE.Mesh(G.cone(hr * .2 * big, hr * .45 * big, 20), toon(k === 'fox' ? '#2b1d16' : c.inner)); i.position.set(0, hr * .18 * big, hr * .1); e.add(i); i.userData.carve = true; }
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
  const nose = (cc, r, y, z) => { const sm = noseMesh(k, cc, r); if (sm) { sm.position.set(0, y, z); sm.rotation.x = -.12; head.add(sm); rig.noseM = sm; return sm; } const m = mesh(G.sph(r, 16, 12), toon(cc), .1, head); m.position.set(0, y, z); m.scale.set(1.3, .9, .8); return m; };
  const ell = (cc, x, y, z, rx, ry, rz) => { const m = mesh(G.sph(1, 28, 20), toon(cc), 0, head); m.position.set(x * hr, y * hr, z * hr); m.scale.set(rx * hr, ry * hr, rz * hr); return m; };
  const SN = { // [переносица, морда, подушечки, подбородок, нос(y,z,r), рот(y,z), рот: 0 «:3» / 1 улыбка]
    cat:    { br: [0, -.03, .78, .15, .22, .3], mz: [0, -.27, .84, .36, .25, .38, 'body'], pd: [.155, -.31, 1.03, .19, .16, .16], ch: [0, -.47, .9, .16, .1, .13], no: [-.14, 1.2, .085], mo: [-.355, 1.15], mk: 0 },
    rabbit: { br: [0, -.03, .76, .16, .22, .27], mz: [0, -.26, .8, .34, .24, .33, 'body'], pd: [.16, -.3, .96, .21, .18, .17], ch: [0, -.46, .86, .15, .1, .12], no: [-.13, 1.12, .07], mo: [-.34, 1.08], mk: 0 },
    mouse:  { br: null, mz: [0, -.15, .88, .3, .25, .5, 'body'], pd: [.1, -.24, 1.18, .13, .11, .13], ch: [0, -.36, 1.06, .1, .07, .1], no: [-.13, 1.39, .075], mo: [-.305, 1.2], mk: 0 },
    dog:    { br: [0, -.02, .8, .17, .21, .31], mz: [0, -.27, .92, .33, .26, .45, 'belly'], pd: [.14, -.34, 1.12, .19, .15, .17], ch: [0, -.48, 1.0, .15, .09, .14], no: [-.12, 1.35, .13], mo: [-.42, 1.24], mk: 1 },
    bear:   { br: [0, -.02, .78, .17, .2, .28], mz: [0, -.28, .86, .36, .27, .38, 'belly'], pd: [.13, -.34, 1.03, .18, .14, .15], ch: [0, -.48, .93, .15, .09, .13], no: [-.15, 1.2, .13], mo: [-.41, 1.12], mk: 1 } };
  const sn = SN[k];
  if (sn) { const mc = sn.mz[6] === 'belly' ? c.belly : c.body;
    if (sn.br) ell(c.body, ...sn.br); ell(mc, ...sn.mz.slice(0, 6)); for (const s of [-1, 1]) ell(c.belly, s * sn.pd[0], ...sn.pd.slice(1)); ell(c.belly, ...sn.ch);
    nose(c.nose, hr * sn.no[2], hr * sn.no[0], hr * sn.no[1]); rig.mouthAt = sn.mo; rig.mouthKind = sn.mk; rig.noseY = sn.no[0] - sn.no[2] * .8; rig.muzzle = { c: [0, (sn.mz[1] + sn.ch[1]) / 2, sn.mz[2] + .04], r: [sn.mz[3] + .05, (sn.mz[1] - sn.ch[1]) / 2 + sn.ch[4] + .07, sn.mz[5] + .06] }; if (k === 'cat' || k === 'mouse' || k === 'rabbit') rig.padAt = [sn.pd[0] + sn.pd[3] * .3, sn.pd[1] + .02]; }
  if (k === 'fox') { const sn = mesh(G.cone(hr * .38, hr * .55, 24), toon(c.belly), .04, head); sn.rotation.x = Math.PI / 2; sn.position.set(0, -hr * .25, hr * 1.0); nose(c.nose, hr * .1, -hr * .25, hr * 1.27); }
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
  if (k === 'cat' || k === 'mouse' || k === 'rabbit') { const ms = k === 'mouse', sn2 = SN[k], ix = sn2 ? sn2.pd[0] + sn2.pd[3] * .35 : .2, iy = sn2 ? sn2.pd[1] + .03 : -.27, iz = sn2 ? sn2.pd[2] : 1.0, wl = ms ? .78 : .95; // из подушечек, назад вдоль щёк, кончики провисают
    const wc = new THREE.Color(c.body).getHSL({}).l > .6 ? '#e8e0d6' : '#fbf6ee';
    for (const s of [-1, 1]) for (let i = 0; i < 3; i++) { const L = hr * wl * (1 - Math.abs(i - 1) * .1), w = new THREE.Mesh(whiskerGeo(L, hr * .011, .16 + i * .05), whiskerMat(wc)); const a = .42 + (i - 1) * .06;
      w.rotation.set(0, s > 0 ? a : Math.PI - a, (1 - i) * .2); w.position.set(s * hr * (ix + (i - 1) * .025), hr * (iy - i * .055), hr * iz); w.userData.whisker = true; w.userData.shell = true; w.castShadow = false; head.add(w); } }
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
  const nr = human ? rig.P.torsoR * 1.08 : Math.max(.13, rig.P.bx * .68), nk = nr / .22; // шея — по телосложению
  if (t === 'scarf') { const s = mesh(G.tor(nr, .055 * Math.max(.75, nk), 0), toon(cl), .06, rig.pose); s.rotation.x = Math.PI / 2; s.position.y = rig.P.headY - hr * .95; const e = mesh(G.cap(.05 * Math.max(.8, nk), .18), toon(cl), .08, rig.pose); e.position.set(-nr * .45, rig.P.headY - hr * 1.3, nr * .9); e.rotation.z = .3; }
  if (t === 'collar') { const s = mesh(G.tor(nr * .92, .025, 0), toon(cl), .06, rig.pose); s.rotation.x = Math.PI / 2; s.position.y = rig.P.headY - hr * .95; const b = mesh(G.sph(.04, 12, 10), toon('#ffd23f'), .08, rig.pose); b.position.set(0, rig.P.headY - hr * 1.05, nr * .92); }
  if (t === 'hat') { const cap = mesh(new THREE.SphereGeometry(hr * 1.08, 40, 20, 0, Math.PI * 2, 0, Math.PI * .42), toon(cl), .03, head); cap.position.y = hr * .16; cap.rotation.x = -.32; cap.scale.set(1.1, 1.02, 1.06); cap.userData.hatCut = hr * 1.08 * Math.cos(Math.PI * .42) - hr * .06; rig.hats = (rig.hats || []).concat(cap); cap.userData.capOld = true;
    const vz = new THREE.Group(); vz.position.set(0, hr * .72, hr * .52); vz.rotation.x = .1; head.add(vz); vz.userData.capOld = true; // козырёк — вперёд над глазами
    const br = mesh(new THREE.CylinderGeometry(hr * .72, hr * .72, hr * .04, 32, 1, false, -Math.PI / 2, Math.PI), toon(new THREE.Color(cl).multiplyScalar(.9).getStyle()), .04, vz); br.scale.set(.95, 1, 1.05);
    const bt = new THREE.Mesh(new THREE.TorusGeometry(hr * .03, hr * .03, 6, 10), toon(cl)); bt.position.set(0, hr * 1.1, -hr * .2); cap.add(bt); }
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
  // жизнь в покое: дыхание, перенос веса, руки при разговоре
  const talk0 = clamp(st.talk || 0, 0, 1), dyn = rig._dyn || (rig._dyn = { t: T, y: 0, vy: 0, ear: 0, earV: 0, tl: 0, tlV: 0, yaw: 0, look: 0, lookT: 0, gest: 0 });
  if (!wk.on && !an) { sideTilt = Math.sin(T * .45 + sd * 9) * .025; head.y = Math.sin(T * .37 + sd * 4) * .12; }
  if (talk0 > .02 && !an && !wk.on) { const gp = Math.sin(T * 1.9 + sd * 3); R_.z = .45 + Math.max(0, gp) * .55 * (.4 + talk0); R_.x = -.35 - Math.max(0, gp) * .5; head.x += Math.sin(T * 7.5) * .05 * talk0; head.z += Math.sin(T * 2.3) * .05; }
  if (wk.on) { sideTilt = Math.sin(wk.ph) * (wk.run ? .07 : .05); head.z -= sideTilt * .6; }
  const base = { L: { x: L_.x, z: L_.z }, R: { x: R_.x, z: R_.z }, leg: leg.slice(), head: Object.assign({}, head), lift, pitch, sideTilt, hipYaw };
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
  if (an && !['jump', 'somersault', 'roll', 'spin', 'kick'].includes(an)) { const dur = ap > .02 ? at / ap : 9, bf = Math.min(ease(at / .22), ease((dur - at) / .25));
    if (bf < 1) { const L2 = (a, b) => lerp(a, b, bf); L_.x = L2(base.L.x, L_.x); L_.z = L2(base.L.z, L_.z); R_.x = L2(base.R.x, R_.x); R_.z = L2(base.R.z, R_.z); leg[0] = L2(base.leg[0], leg[0]); leg[1] = L2(base.leg[1], leg[1]);
      head.x = L2(base.head.x, head.x); head.y = L2(base.head.y, head.y); head.z = L2(base.head.z, head.z); pitch = L2(base.pitch, pitch); hipYaw = L2(base.hipYaw, hipYaw); sideTilt = L2(base.sideTilt, sideTilt); } }
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
  groundFix(rig, Math.max(fallen, sit, crouch, an === 'roll' ? lie : 0));
  { const dt = T - dyn.t; const y = rig.pose.position.y + rig.root.position.y, yaw = rig.yaw.rotation.y;
    if (dt > 0 && dt < .25) { const vy = (y - dyn.y) / dt, ay = (vy - dyn.vy) / dt, wy = (yaw - dyn.yaw) / dt;
      const spring = (x, v, target, k, d) => { const a = (target - x) * k - v * d; v += a * dt; x += v * dt; return [x, v]; };
      [dyn.ear, dyn.earV] = spring(dyn.ear, dyn.earV, clamp(-ay * .012, -.6, .6), 120, 9);
      [dyn.tl, dyn.tlV] = spring(dyn.tl, dyn.tlV, clamp(-wy * .25 - vy * .4, -.8, .8), 60, 6);
      dyn.vy = vy; } else { dyn.ear = dyn.earV = dyn.tl = dyn.tlV = 0; dyn.vy = 0; }
    dyn.t = T; dyn.y = y; dyn.yaw = yaw; }
  if (rig.ears) rig.ears.forEach((e, i) => { const s0 = e.userData.r0 || (e.userData.r0 = e.rotation.clone()); const tw = Math.max(0, Math.sin(T * .9 + sd * 20 + i * 1.7) - .97) * 8; e.rotation.x = s0.x + dyn.ear * .8 - tw * .15; e.rotation.z = s0.z + (i ? -1 : 1) * (dyn.ear * .4 + tw * .2); });
  if (rig.body) { const br = 1 + Math.sin(T * 1.7 + sd * 5) * .012 * (an ? .5 : 1); rig.body.scale.set(1 + (br - 1) * .5, br, 1 + (br - 1) * .8); }
  if (rig.tail) { rig.tail.rotation.y = Math.sin(T * (rig.kind === 'dog' && (emo === 'happy' || emo === 'laugh') ? 14 : 2.4) + sd * 4) * .3 + dyn.tl; rig.tail.rotation.x = (rig.tail.userData.rx0 != null ? rig.tail.userData.rx0 : (rig.tail.userData.rx0 = rig.tail.rotation.x)) + dyn.ear * .5; }
  if (rig.antenna) rig.antenna.material = basic(Math.sin(T * 4) > 0 ? '#ff4d6d' : '#ffd23f');
  if (rig.leds) rig.leds.forEach((l, i) => l.visible = Math.sin(T * 5 + i * 2) > -.3);
  if (rig.wings) rig.wings.forEach((w, i) => w.rotation.z = (i ? 1 : -1) * (.5 + Math.sin(T * (an === 'jump' || wk.on ? 14 : 2)) * .2));
  if (rig.trunk) rig.trunk.rotation.x = Math.sin(T * 1.6) * .15 + (an === 'laugh' || an === 'shout' ? -.6 : 0);
  if (rig.cape) rig.cape.rotation.x = -(wk.on ? .35 : .08) - Math.sin(T * 2) * .03;
  // лицо
  const talk = clamp(st.talk || 0, 0, 1);
  const bp = 3.1 + (rig.n.seed % 17) / 10, bt = (T + (rig.n.seed % 7)) % bp, dbl = Math.floor((T + (rig.n.seed % 7)) / bp) % 3 === 1; let blink = bt < .14 ? Math.sin(bt / .14 * Math.PI) : dbl && bt > .22 && bt < .36 ? Math.sin((bt - .22) / .14 * Math.PI) : 0;
  const speaking = talk > .02 && !!st.vz, laughing = (emo === 'laugh' && !speaking) || an === 'laugh' || (an === 'roll' && emo === 'laugh');
  let closed = pers === 'sleep' || laughing || an === 'yawn' || (an === 'sneeze' && ap > .3 && ap < .62) || (an === 'roll' && emo === 'laugh');
  let lidOpen = rig.kind === 'cat' ? -0.8 : -0.75, browY = 0, browRot = 0, eyeS = 1, pupS = 1;
  if (emo === 'sleepy') lidOpen = .15; if (emo === 'surprised') { eyeS = 1.15; pupS = .7; browY = .5; } if (emo === 'scared') { eyeS = 1.1; pupS = .55; browRot = .35; }
  if (emo === 'angry') { lidOpen = -.25; browRot = -.45; } if (emo === 'sad' || emo === 'cry') { lidOpen = -.3; browRot = .4; }
  rig.eyes.forEach(e => {
    const cl = closed ? 1 : blink; e.g.scale.set(eyeS, eyeS * (1 - cl * .92), eyeS);
    e.lid.rotation.x = lerp(lidOpen, 1.3, cl > .85 ? 1 : 0); e.lid.rotation.z = (emo === 'angry' ? -.35 : emo === 'sad' || emo === 'cry' ? .35 : 0) * -e.s;
    e.ir.visible = e.pu.visible = emo !== 'love'; e.heart.visible = emo === 'love'; e.pu.scale.set(pupS, pupS * 1.15, .5);
    const sacc = Math.floor(T / (1.7 + sd) + sd * 9), sx = ((global.MK.hash32('s' + sacc + rig.n.seed) % 100) / 100 - .5) * .35, sy = ((global.MK.hash32('y' + sacc + rig.n.seed) % 100) / 100 - .5) * .2;
    const gx = (Math.abs(st.face) > .1 ? .25 : 0) + (an || talk > .1 ? 0 : sx); e.ir.position.x = e.pu.position.x = gx * e.eR * .5; e.ir.position.y = e.pu.position.y = (an ? 0 : sy) * e.eR * .4;
    e.brow.position.y = e.eR * (1.55 + browY); e.brow.rotation.z = Math.PI / 2 + browRot * e.s; if (e.browP) { const U = e.browP.material.userData.U; U.uLift.value = browY * 1.1 + (an === 'think' ? .25 : 0); U.uTilt.value = -browRot * 1.1; }
  });
  let open = talk;
  if (laughing) open = Math.max(open, .55 + Math.sin((an === 'laugh' ? at : T) * 16) * .25);
  if (an === 'yawn') open = Math.max(open, Math.sin(clamp(at / 1.6, 0, 1) * Math.PI) * 1.1);
  if (an === 'shout') open = Math.max(open, .95); if (an === 'eat') open = Math.max(open, Math.max(0, Math.sin(at * 12)) * .4); if (an === 'sing') open = Math.max(open, .4 + Math.sin(at * 9) * .3);
  if (emo === 'surprised') open = Math.max(open, .4);
  const smile = ['happy', 'love', 'laugh', 'shy'].includes(emo), sad = ['sad', 'cry', 'scared'].includes(emo);
  rig.open.visible = open > .06; rig.open.scale.set(1 + (smile ? .2 : 0), .25 + open * 1.1, 1);
  rig.smile.visible = !rig.open.visible && !sad; rig.smile.scale.setScalar((smile ? 1.15 : .75) * (rig.wideMouth ? 2.2 : 1));
  rig.frown.visible = !rig.open.visible && sad;
  rig.cheeks.forEach(c => c.material.opacity = emo === 'shy' || emo === 'love' ? .8 : .4); if (rig.blushP) rig.blushP.forEach(b => b.material.userData.U.uAmt.value = emo === 'shy' || emo === 'love' ? .85 : smile ? .55 : .42);
  if (rig.mouthPatch) { const U = rig.mouthPatch.material.userData.U, vz = st.vz; let o = open, w = .5, r = .12, sm = .3, cz = 0;
    if (speaking && !laughing) { o = Math.max(an === 'shout' ? .95 : 0, talk * (.5 + .7 * vz.o)); w = vz.w; r = vz.r; cz = vz.c * clamp(1 - talk, 0, 1); }
    if (smile) sm = .9; if (sad) sm = -.7; if (emo === 'angry') { sm = -.4; w = Math.max(w, .7); } if (emo === 'surprised') { r = Math.max(r, .85); w = Math.min(w, .35); }
    if (laughing) { sm = 1; w = .9; r = 0; } if (an === 'yawn') { r = .75; w = .4; } if (an === 'sing') r = Math.max(r, .6); if (an === 'eat') { r = .3; sm = .5; }
    U.uOpen.value = clamp(o, 0, 1); U.uWide.value = w; U.uRound.value = r; U.uSmile.value = sm; U.uClose.value = cz;
    rig.smile.visible = rig.frown.visible = rig.open.visible = false; }
  if (rig.capM) { const hop = laughing ? Math.abs(Math.sin((an === 'laugh' ? at : T) * 16)) * rig.P.head * .08 : 0; rig.capM.position.copy(rig.capAxis).multiplyScalar(hop); }
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
// ---------- предметы: каждый собран из нескольких деталей и своих материалов (блеск, металл, дерево, бумага, ткань, воск, стекло) ----------
const V2 = (x, y) => new THREE.Vector2(x, y);
function lathe(pts, seg) { return new THREE.LatheGeometry(pts.map(([x, y]) => V2(Math.max(0, x), y)), seg || 32); }
function taperTube(curve, n, rfn, radial) { // трубка с переменной толщиной (банан, морковка, стебли)
  radial = radial || 10; const fr = curve.computeFrenetFrames(n, false), P = [], N = [], U = [], I = [];
  for (let i = 0; i <= n; i++) { const t = i / n, c = curve.getPointAt(t), r = rfn(t); for (let j = 0; j <= radial; j++) { const a = j / radial * Math.PI * 2, nx = Math.cos(a), ny = Math.sin(a);
      const nn = fr.normals[i].clone().multiplyScalar(nx).add(fr.binormals[i].clone().multiplyScalar(ny)); P.push(c.x + nn.x * r, c.y + nn.y * r, c.z + nn.z * r); N.push(nn.x, nn.y, nn.z); U.push(j / radial, t); } }
  for (let i = 0; i < n; i++) for (let j = 0; j < radial; j++) { const a = i * (radial + 1) + j, b = a + radial + 1; I.push(a, a + 1, b, b, a + 1, b + 1); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(N, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2)); g.setIndex(I); return g; }
function ext(shape, depth, bevel, curveSeg) { const b = bevel == null ? Math.min(.012, depth * .3) : bevel; const g = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: b > 0, bevelThickness: b, bevelSize: b, bevelSegments: 3, curveSegments: curveSeg || 12 }); g.translate(0, 0, -depth / 2); return g; }
function rrect(w, h, r) { const s = new THREE.Shape(), x = -w / 2, y = -h / 2; s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h); s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r); s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y); return s; }
function starShape(R, r, n) { const s = new THREE.Shape(); n = n || 5; for (let i = 0; i < n * 2; i++) { const a = Math.PI / 2 + i * Math.PI / n, q = i % 2 ? r : R; i ? s.lineTo(Math.cos(a) * q, Math.sin(a) * q) : s.moveTo(Math.cos(a) * q, Math.sin(a) * q); } s.closePath(); return s; }
const pmC = {};
function pmat(c, kind, map) { // материал предмета; в обычном режиме — мультяшный
  if (!MK3D.hq) return map ? toon(null, map) : toon(c);
  const key = (c || '') + kind + (map ? map.uuid : ''); if (pmC[key]) return pmC[key];
  const o = { color: map ? 0xffffff : col(c), map: map || null };
  let m;
  switch (kind) {
    case 'gloss': m = new THREE.MeshPhysicalMaterial(Object.assign(o, { roughness: .32, clearcoat: 1, clearcoatRoughness: .08, envMapIntensity: .9 })); break;
    case 'plastic': m = new THREE.MeshPhysicalMaterial(Object.assign(o, { roughness: .42, clearcoat: .6, clearcoatRoughness: .2 })); break;
    case 'metal': m = new THREE.MeshStandardMaterial(Object.assign(o, { metalness: 1, roughness: .3, envMapIntensity: 1.3 })); break;
    case 'wood': m = new THREE.MeshStandardMaterial(Object.assign(o, { roughness: .72 })); break;
    case 'paper': m = new THREE.MeshStandardMaterial(Object.assign(o, { roughness: .95 })); break;
    case 'cloth': m = new THREE.MeshPhysicalMaterial(Object.assign(o, { roughness: .9, sheen: 1, sheenRoughness: .5, sheenColor: (map ? new THREE.Color(1, 1, 1) : col(c).lerp(new THREE.Color(1, 1, 1), .5)) })); break;
    case 'wax': m = new THREE.MeshPhysicalMaterial(Object.assign(o, { roughness: .55, sheen: .5, sheenColor: new THREE.Color(1, .97, .9), clearcoat: .2 })); break;
    case 'food': m = new THREE.MeshPhysicalMaterial(Object.assign(o, { roughness: .6, sheen: .3, sheenColor: new THREE.Color(1, 1, .95) })); break;
    case 'glass': m = new THREE.MeshPhysicalMaterial(Object.assign(o, { roughness: .05, transparent: true, opacity: .3, clearcoat: 1, depthWrite: false })); break;
    case 'glow': m = new THREE.MeshBasicMaterial(o); m.color.multiplyScalar(1.8); break;
    case 'ceramic': m = new THREE.MeshPhysicalMaterial(Object.assign(o, { roughness: .25, clearcoat: 1, clearcoatRoughness: .05 })); break;
    default: m = new THREE.MeshStandardMaterial(Object.assign(o, { roughness: .6 }));
  }
  return (pmC[key] = m); }
// ---------- рисунки для предметов ----------
function ctex(key, w, h, draw, rep) { if (envC[key]) return envC[key]; const t = canvasTex(w, h, draw); t.wrapS = t.wrapT = THREE.RepeatWrapping; if (rep) t.repeat.set(rep[0], rep[1]); t.anisotropy = 4; return (envC[key] = t); }
const shadeC = (c, k) => '#' + new THREE.Color(c).multiplyScalar(k).getHexString();
const lightC = (c, k) => '#' + new THREE.Color(c).lerp(new THREE.Color(1, 1, 1), k).getHexString();
function stripesT(cols, vertical) { return ctex('stp' + cols.join() + vertical, 256, 256, (g) => { const n = cols.length; for (let i = 0; i < n; i++) { g.fillStyle = cols[i]; vertical ? g.fillRect(i * 256 / n, 0, 256 / n + 1, 256) : g.fillRect(0, i * 256 / n, 256, 256 / n + 1); } }); }
function appleT(c) { return ctex('apl' + c, 128, 128, (g) => { const gr = g.createLinearGradient(0, 0, 0, 128); gr.addColorStop(0, lightC(c, .1)); gr.addColorStop(.5, c); gr.addColorStop(1, shadeC(c, .8)); g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const r = rng(5); g.globalAlpha = .35; for (let i = 0; i < 70; i++) { g.fillStyle = r() < .5 ? '#ffe9a0' : shadeC(c, .7); g.fillRect(r() * 128, r() * 128, 1 + r() * 2, 3 + r() * 6); } g.globalAlpha = 1; }); }
function speckT(c, sp, n) { return ctex('spk' + c + sp + n, 128, 128, (g) => { g.fillStyle = c; g.fillRect(0, 0, 128, 128); const r = rng(13); g.fillStyle = sp; for (let i = 0; i < n; i++) { g.beginPath(); g.arc(r() * 128, r() * 128, .6 + r() * 1.4, 0, 7); g.fill(); } }); }
function melonT() { return ctex('melon', 256, 128, (g) => { g.fillStyle = '#5aa83f'; g.fillRect(0, 0, 256, 128); g.fillStyle = '#1f5e2a'; for (let i = 0; i < 12; i++) { const x0 = i * 256 / 12; g.beginPath(); g.moveTo(x0, 0); for (let y = 0; y <= 128; y += 4) g.lineTo(x0 + Math.sin(y * .2 + i) * 5 + 6, y); for (let y = 128; y >= 0; y -= 4) g.lineTo(x0 + Math.sin(y * .2 + i) * 5 - 6, y); g.fill(); } }); }
function waffleT() { return ctex('waffle', 128, 128, (g) => { g.fillStyle = '#e2b26a'; g.fillRect(0, 0, 128, 128); g.strokeStyle = '#a8742f'; g.lineWidth = 4; for (let i = -128; i < 256; i += 22) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 128, 128); g.stroke(); g.beginPath(); g.moveTo(i + 128, 0); g.lineTo(i, 128); g.stroke(); } }, [3, 2]); }
function swirlT(a, b) { return ctex('swirl' + a + b, 256, 256, (g) => { g.fillStyle = a; g.fillRect(0, 0, 256, 256); g.strokeStyle = b; g.lineWidth = 14; g.lineCap = 'round'; g.beginPath(); for (let t = 0; t < 30; t += .05) { const r = t * 4.2, x = 128 + Math.cos(t) * r, y = 128 + Math.sin(t) * r; t ? g.lineTo(x, y) : g.moveTo(x, y); } g.stroke(); }); }
function giftT(c) { return ctex('gift' + c, 256, 256, (g) => { g.fillStyle = c; g.fillRect(0, 0, 256, 256); g.fillStyle = lightC(c, .55); for (let y = 16; y < 256; y += 40) for (let x = 16 + (y / 40 % 2) * 20; x < 256; x += 40) { g.beginPath(); g.arc(x, y, 7, 0, 7); g.fill(); } }); }
function pagesT() { return ctex('pages', 64, 64, (g) => { g.fillStyle = '#fbf7ee'; g.fillRect(0, 0, 64, 64); g.strokeStyle = 'rgba(120,100,80,.25)'; for (let y = 2; y < 64; y += 3) { g.beginPath(); g.moveTo(0, y); g.lineTo(64, y); g.stroke(); } }); }
function cardboardT() { return ctex('cardb', 256, 256, (g) => { g.fillStyle = '#c99a5b'; g.fillRect(0, 0, 256, 256); const r = rng(3); for (let i = 0; i < 400; i++) { g.fillStyle = r() < .5 ? 'rgba(90,60,20,.12)' : 'rgba(255,230,180,.12)'; g.fillRect(r() * 256, r() * 256, 1 + r() * 3, 1 + r() * 3); } g.fillStyle = 'rgba(230,210,170,.85)'; g.fillRect(110, 0, 36, 256); }); }
function parchT(draw) { return ctex('parch' + (draw ? 'm' : ''), 256, 192, (g) => { g.fillStyle = '#efdcae'; g.fillRect(0, 0, 256, 192); const r = rng(8); for (let i = 0; i < 300; i++) { g.fillStyle = 'rgba(140,100,40,' + (r() * .12) + ')'; g.beginPath(); g.arc(r() * 256, r() * 192, 2 + r() * 10, 0, 7); g.fill(); }
  const ed = g.createRadialGradient(128, 96, 60, 128, 96, 150); ed.addColorStop(0, 'rgba(0,0,0,0)'); ed.addColorStop(1, 'rgba(110,70,20,.45)'); g.fillStyle = ed; g.fillRect(0, 0, 256, 192);
  if (draw) { g.fillStyle = 'rgba(90,150,90,.6)'; g.beginPath(); g.ellipse(80, 80, 50, 34, .4, 0, 7); g.fill(); g.beginPath(); g.ellipse(190, 120, 36, 24, -.3, 0, 7); g.fill(); g.strokeStyle = '#8a3a2a'; g.lineWidth = 3; g.setLineDash([8, 7]); g.beginPath(); g.moveTo(60, 150); g.bezierCurveTo(100, 110, 140, 160, 186, 116); g.stroke(); g.setLineDash([]);
    g.lineWidth = 5; g.beginPath(); g.moveTo(178, 108); g.lineTo(194, 124); g.moveTo(194, 108); g.lineTo(178, 124); g.stroke(); g.strokeStyle = 'rgba(60,40,20,.6)'; g.lineWidth = 2; g.beginPath(); g.arc(225, 40, 14, 0, 7); g.moveTo(225, 22); g.lineTo(225, 58); g.moveTo(207, 40); g.lineTo(243, 40); g.stroke(); } }); }
function clockT() { return ctex('clockf', 256, 256, (g) => { g.fillStyle = '#fffaf0'; g.fillRect(0, 0, 256, 256); g.fillStyle = '#2b1d16'; g.font = 'bold 30px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; for (let i = 1; i <= 12; i++) { const a = i / 12 * Math.PI * 2 - Math.PI / 2; if (i % 3 === 0) g.fillText(String(i), 128 + Math.cos(a) * 92, 128 + Math.sin(a) * 92); else { g.beginPath(); g.arc(128 + Math.cos(a) * 96, 128 + Math.sin(a) * 96, 4, 0, 7); g.fill(); } } }); }
function phoneT() { return ctex('phones', 128, 256, (g) => { const gr = g.createLinearGradient(0, 0, 128, 256); gr.addColorStop(0, '#5a7bff'); gr.addColorStop(1, '#c86bff'); g.fillStyle = gr; g.fillRect(0, 0, 128, 256); const cs = ['#ff6b6b', '#ffd23f', '#4cd964', '#5ac8fa', '#ff9f43', '#ffffff', '#a29bfe', '#fd79a8'];
  for (let i = 0; i < 16; i++) { const x = 14 + (i % 4) * 27, y = 40 + Math.floor(i / 4) * 34; g.fillStyle = cs[i % cs.length]; g.beginPath(); g.roundRect ? g.roundRect(x, y, 20, 20, 5) : g.rect(x, y, 20, 20); g.fill(); } g.fillStyle = 'rgba(255,255,255,.9)'; g.font = 'bold 22px sans-serif'; g.textAlign = 'center'; g.fillText('12:30', 64, 26); }); }
function weaveT(c) { return ctex('weave' + c, 128, 128, (g) => { g.fillStyle = shadeC(c, .7); g.fillRect(0, 0, 128, 128); for (let y = 0; y < 128; y += 16) for (let x = 0; x < 128; x += 16) { const o = ((x + y) / 16) % 2; const gr = o ? g.createLinearGradient(x, 0, x + 16, 0) : g.createLinearGradient(0, y, 0, y + 16); gr.addColorStop(0, shadeC(c, .8)); gr.addColorStop(.5, lightC(c, .2)); gr.addColorStop(1, shadeC(c, .8)); g.fillStyle = gr; g.beginPath(); g.roundRect ? g.roundRect(x + 1, y + 1, 14, 14, 4) : g.rect(x + 1, y + 1, 14, 14); g.fill(); } }, [6, 2]); }
function craterT() { return ctex('crater', 256, 128, (g) => { g.fillStyle = '#fff4cc'; g.fillRect(0, 0, 256, 128); const r = rng(77); for (let i = 0; i < 40; i++) { const x = r() * 256, y = r() * 128, rr = 3 + r() * 12; g.fillStyle = 'rgba(200,180,120,.35)'; g.beginPath(); g.arc(x, y, rr, 0, 7); g.fill(); g.strokeStyle = 'rgba(255,255,240,.5)'; g.beginPath(); g.arc(x - 1, y - 1, rr, Math.PI * 1.1, Math.PI * 1.8); g.stroke(); } }); }
function coinT() { return ctex('coin', 128, 128, (g) => { g.fillStyle = '#808080'; g.fillRect(0, 0, 128, 128); g.fillStyle = '#ffffff'; g.beginPath(); const s = 40; for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, q = i % 2 ? s * .45 : s; i ? g.lineTo(64 + Math.cos(a) * q, 64 + Math.sin(a) * q) : g.moveTo(64 + Math.cos(a) * q, 64 + Math.sin(a) * q); } g.fill(); g.strokeStyle = '#ffffff'; g.lineWidth = 5; g.beginPath(); g.arc(64, 64, 56, 0, 7); g.stroke(); }); }
function cheeseT() { return ctex('cheese', 256, 128, (g) => { g.fillStyle = '#ffd23f'; g.fillRect(0, 0, 256, 128); const r = rng(4); for (let i = 0; i < 22; i++) { const x = r() * 256, y = 12 + r() * 104, rr = 4 + r() * 11; const gr = g.createRadialGradient(x - rr * .3, y - rr * .3, 1, x, y, rr); gr.addColorStop(0, '#c99a14'); gr.addColorStop(1, '#e8b820'); g.fillStyle = gr; g.beginPath(); g.ellipse(x, y, rr, rr * .85, 0, 0, 7); g.fill(); } }); }
function stoneT() { return ctex('stone', 256, 256, (g) => { g.fillStyle = '#b8b2a8'; g.fillRect(0, 0, 256, 256); g.strokeStyle = 'rgba(80,70,60,.45)'; g.lineWidth = 3; for (let y = 0; y < 256; y += 32) { g.beginPath(); g.moveTo(0, y); g.lineTo(256, y); g.stroke(); for (let x = ((y / 32) % 2) * 32; x < 256; x += 64) { g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + 32); g.stroke(); } } const r = rng(6); for (let i = 0; i < 300; i++) { g.fillStyle = 'rgba(' + (r() < .5 ? '255,255,255' : '60,50,40') + ',.08)'; g.fillRect(r() * 256, r() * 256, 4, 4); } }, [2, 2]); }
function fabricT(a, b) { return ctex('fab' + a + b, 128, 128, (g) => { g.fillStyle = a; g.fillRect(0, 0, 128, 128); g.fillStyle = b; for (let i = 0; i < 4; i++) g.fillRect(i * 32, 0, 16, 128); }); }
function propMesh(p) {
  const key = p.id + p.type + (p.color || ''); if (propCache[key]) return propCache[key];
  const g = new THREE.Group(), t = p.type, cl = p.color;
  const A = (geo, mat, par, ol) => mesh(geo, mat, ol == null ? .04 : ol, par || g); // деталь
  const P = (c, k, map) => pmat(c, k, map);
  switch (t) {
    case 'ball': { const b = A(G.sph(.17, 40, 28), P(null, 'gloss', cl ? stripesT([cl, '#ffffff', cl, '#ffffff', cl, '#ffffff'], true) : stripesT(['#e8344e', '#ffffff', '#3d8fe0', '#ffd23f', '#ffffff', '#5fbf4a'], true))); b.position.y = .17; b.rotation.z = .4;
      const cap = A(G.sph(.03, 16, 10), P('#ffffff', 'gloss'), b, 0); cap.position.y = .168; cap.scale.y = .35; break; }
    case 'apple': { const c0 = cl || '#e23b3b'; const b = A(lathe([[0, .005], [.05, 0], [.1, .025], [.125, .075], [.122, .135], [.095, .19], [.05, .205], [.018, .19], [0, .175]], 36), P(null, 'gloss', appleT(c0)));
      const st = A(taperTube(new THREE.CatmullRomCurve3([new THREE.Vector3(0, .17, 0), new THREE.Vector3(.005, .22, 0), new THREE.Vector3(.02, .25, 0)]), 8, tt => .009 - tt * .003, 6), P('#5a3a22', 'wood'), g, 0);
      const lf = A(leafGeo(false), P('#5fbf4a', 'plastic'), g, 0); lf.scale.setScalar(.08); lf.position.set(.022, .235, 0); lf.rotation.set(.2, 0, -1.1); break; }
    case 'fish': { const c0 = cl || '#ff8a3d'; const body = new THREE.Group(); body.position.y = .1; g.add(body);
      const b = A(lathe([[0, -.16], [.03, -.14], [.06, -.08], [.07, 0], [.06, .07], [.035, .13], [0, .16]], 28), P(c0, 'gloss'), body); b.rotation.z = Math.PI / 2; b.scale.set(1, 1, .62);
      const tf = new THREE.Shape(); tf.moveTo(0, 0); tf.quadraticCurveTo(-.06, .07, -.1, .09); tf.quadraticCurveTo(-.08, 0, -.1, -.09); tf.quadraticCurveTo(-.06, -.07, 0, 0); const tl = A(ext(tf, .01, .003), P(shadeC(c0, .85), 'gloss'), body); tl.position.x = -.15;
      const df = new THREE.Shape(); df.moveTo(-.05, 0); df.quadraticCurveTo(0, .07, .06, 0); df.lineTo(-.05, 0); const d = A(ext(df, .008, .002), P(shadeC(c0, .85), 'gloss'), body); d.position.y = .055;
      for (const s of [-1, 1]) { const e = A(G.sph(.018, 14, 10), P('#ffffff', 'gloss'), body, 0); e.position.set(.1, .015, s * .036); const pu = A(G.sph(.01, 10, 8), P('#111111', 'gloss'), body, 0); pu.position.set(.112, .015, s * .044); } break; }
    case 'box': { const tx = cardboardT(); const b = A(G.box(.36, .26, .28), P(null, 'paper', tx)); b.position.y = .13;
      for (const s of [-1, 1]) { const f = new THREE.Group(); f.position.set(0, .26, s * .14); g.add(f); const fl = A(G.box(.36, .005, .13), P(null, 'paper', tx), f, .02); fl.position.z = s * .065; f.rotation.x = s * .55; } break; }
    case 'gift': { const c0 = cl || '#8d5cf6', rb = '#ffd23f'; const b = A(ext(rrect(.32, .32, .03), .28, .01), P(null, 'paper', giftT(c0))); b.rotation.x = -Math.PI / 2; b.position.y = .14 + .14 * 0; b.position.y = .14;
      A(G.box(.355, .305, .06), P(rb, 'gloss'), g, 0).position.y = .145; A(G.box(.06, .305, .355), P(rb, 'gloss'), g, 0).position.y = .145;
      for (const s of [-1, 1]) { const lp = A(new THREE.TorusGeometry(.055, .018, 12, 32), P(rb, 'gloss'), g, .03); lp.position.set(s * .055, .335, 0); lp.rotation.z = -s * .55; lp.scale.set(1, .62, .45); }
      A(G.sph(.026, 14, 10), P(rb, 'gloss'), g, 0).position.y = .31; for (const s of [-1, 1]) { const tl = A(G.box(.028, .1, .006), P(rb, 'gloss'), g, 0); tl.position.set(s * .025, .27, .182); tl.rotation.z = s * .35; } break; }
    case 'flower': { const c0 = cl || '#ff7ab8'; const cv = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), new THREE.Vector3(.02, .15, 0), new THREE.Vector3(-.01, .3, .01), new THREE.Vector3(0, .38, 0)]);
      A(taperTube(cv, 16, tt => .009 - tt * .003, 6), P('#3f9a3a', 'plastic'), g, 0);
      for (const s of [-1, 1]) { const lf = A(leafGeo(false), P('#4fae45', 'plastic'), g, 0); lf.scale.setScalar(.1); lf.position.set(s * .006, .12 + (s > 0 ? .05 : 0), 0); lf.rotation.set(0, s > 0 ? 0 : Math.PI, -1 + s * .2); }
      const hd = new THREE.Group(); hd.position.y = .38; hd.rotation.x = .5; g.add(hd);
      const bas = new THREE.Matrix4().makeBasis(new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0)); for (let i = 0; i < 9; i++) { const gq = new THREE.Group(); gq.rotation.y = i / 9 * Math.PI * 2; hd.add(gq); const pe = A(leafGeo(false), P(c0, 'plastic'), gq, 0); pe.quaternion.setFromRotationMatrix(bas); pe.rotateX(-.35); pe.scale.set(.11, .085, .11); pe.material = pe.material; }
      const ctr = A(G.sph(.025, 16, 10), P(null, 'food', speckT('#ffc21a', '#c47a08', 60)), hd, 0); ctr.scale.y = .55; ctr.position.y = .008; break; }
    case 'book': { const c0 = cl || '#2f7de1'; const bk = new THREE.Group(); bk.position.y = .03; g.add(bk);
      for (const y of [-.024, .024]) { const cv = A(ext(rrect(.28, .2, .012), .008, .002), P(c0, 'plastic'), bk, .02); cv.rotation.x = -Math.PI / 2; cv.position.y = y; }
      const pg = A(G.box(.27, .04, .19), P(null, 'paper', pagesT()), bk, 0); pg.position.x = .005; const sp = A(G.cyl(.028, .028, .2, 16, true), P(c0, 'plastic'), bk, 0); sp.rotation.x = Math.PI / 2; sp.position.x = -.135; sp.scale.x = .6;
      const lb = A(G.box(.12, .003, .05), P('#ffd23f', 'gloss'), bk, 0); lb.position.set(.01, .03, 0); break; }
    case 'star': { const s = A(ext(starShape(.16, .075), .05, .015), P(cl || '#ffd23f', MK3D.hq ? 'gloss' : 'gloss')); s.position.y = .17; break; }
    case 'cake': { const c0 = cl || '#ff8fb1'; A(lathe([[0, 0], [.19, 0], [.19, .12], [0, .12]], 40), P(null, 'food', speckT('#f7d6a8', '#e8b878', 140))).position.y = 0;
      A(lathe([[0, .12], [.192, .12], [.198, .16], [.18, .175], [0, .175]], 40), P(c0, 'gloss')); for (let i = 0; i < 14; i++) { const a = i / 14 * Math.PI * 2, dl = .03 + (i % 3) * .015; const d = A(G.cap(.014, dl), P(c0, 'gloss'), g, 0); d.position.set(Math.cos(a) * .195, .13 - dl / 2, Math.sin(a) * .195); }
      for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; const b = A(G.sph(.022, 12, 10), P('#d8213a', 'gloss'), g, 0); b.position.set(Math.cos(a) * .13, .19, Math.sin(a) * .13); }
      const cd = A(G.cyl(.01, .01, .1, 10), P(null, 'wax', stripesT(['#7fb3ff', '#ffffff'], false)), g, 0); cd.position.y = .225; const fl = A(G.sph(.016, 10, 8), P('#ffb703', 'glow'), g, 0); fl.position.y = .29; fl.scale.y = 1.7; g.userData.flames = [fl]; break; }
    case 'bone': { const c0 = cl || '#fff3dc'; A(G.cap(.032, .2, 6, 14), P(c0, 'food')).rotation.z = Math.PI / 2; for (const s of [-1, 1]) for (const d of [-1, 1]) { const b = A(G.sph(.045, 16, 12), P(c0, 'food'), g, .04); b.position.set(s * .13, d * .03, 0); } g.children.forEach(c => c.position.y += .05); break; }
    case 'carrot': { const c0 = cl || '#ff8a1f'; const pts = []; for (let i = 0; i <= 20; i++) { const y = i / 20 * .28; const r = .048 * Math.pow(i / 20, .55) * (1 + Math.sin(i * 2.2) * .04); pts.push([r, y]); } pts.push([0, .285]);
      const b = A(lathe(pts, 24), P(c0, 'food')); b.position.y = 0;
      for (let i = 0; i < 5; i++) { const lf = A(leafGeo(true), P('#3f9a3a', 'plastic'), g, 0); lf.scale.set(.14, .14, .14); lf.position.y = .28; lf.rotation.set((i - 2) * .25, i * 1.2, (i - 2) * .2); }
      g.rotation.z = 0; break; }
    case 'cheese': { const sh = new THREE.Shape(); sh.moveTo(0, 0); sh.lineTo(.32, -.09); sh.lineTo(.32, .09); sh.closePath(); const ctx2 = cheeseT(); ctx2.repeat.set(4, 4); const ch = A(ext(sh, .13, .008), P(null, 'wax', ctx2)); ch.rotation.x = -Math.PI / 2; ch.position.set(-.16, .065, 0); break; }
    case 'balloon': { const c0 = cl || '#ff4d6d'; const b = A(lathe([[0, 0], [.015, .005], [.08, .05], [.16, .16], [.18, .26], [.15, .36], [.08, .41], [0, .425]], 36), P(c0, 'gloss'), g, .03); b.position.y = .62;
      const kn = A(G.cone(.02, .03, 10), P(c0, 'gloss'), g, 0); kn.position.y = .61; const cv = new THREE.CatmullRomCurve3([new THREE.Vector3(0, .6, 0), new THREE.Vector3(.03, .4, 0), new THREE.Vector3(-.02, .2, 0), new THREE.Vector3(.01, 0, 0)]); A(new THREE.TubeGeometry(cv, 24, .003, 4), P('#666666', 'plastic'), g, 0);
      g.userData.float = true; break; }
    case 'key': { const c0 = cl || '#ffd23f'; const k = new THREE.Group(); k.position.y = .05; k.rotation.x = -Math.PI / 2 + .25; g.add(k);
      const bow = A(G.tor(.045, .014, 12, 32), P(c0, 'metal'), k, .03); bow.position.x = -.09; for (let i = 0; i < 4; i++) { const a = i / 4 * Math.PI * 2 + Math.PI / 4; const lb = A(G.sph(.016, 10, 8), P(c0, 'metal'), k, 0); lb.position.set(-.09 + Math.cos(a) * .058, Math.sin(a) * .058, 0); }
      const sh = A(G.cyl(.011, .011, .17, 12), P(c0, 'metal'), k, .03); sh.rotation.z = Math.PI / 2; sh.position.x = .03; A(G.tor(.016, .006, 8, 16), P(c0, 'metal'), k, 0).position.x = -.04;
      for (const [x, h] of [[.09, .045], [.065, .03]]) { const tb = A(G.box(.016, h, .01), P(c0, 'metal'), k, 0); tb.position.set(x, -h / 2 - .005, 0); } break; }
    case 'cup': { const c0 = cl || '#ffffff'; A(lathe([[0, 0], [.065, 0], [.07, .005], [.085, .15], [.083, .16], [.075, .16], [.068, .02], [0, .02]], 36), P(c0, 'ceramic'));
      const band = A(lathe([[.077, .1], [.083, .1], [.085, .125], [.079, .125]], 36), P('#e8344e', 'ceramic'), g, 0); const tea = A(G.cyl(.074, .074, .004, 32), P('#7a4a2a', 'gloss'), g, 0); tea.position.y = .13;
      const h = A(G.tor(.04, .011, 12, 24, Math.PI * 1.15), P(c0, 'ceramic'), g, .03); h.position.set(.09, .085, 0); h.rotation.z = -Math.PI / 2 - .1; break; }
    case 'pumpkin': case 'jack': { const c0 = cl || '#ff8a1f', jack = t === 'jack'; const geo = G.sph(.17, 48, 32); const pp = geo.attributes.position, v = new THREE.Vector3();
      for (let i = 0; i < pp.count; i++) { v.fromBufferAttribute(pp, i); const a = Math.atan2(v.z, v.x), rib = 1 - .1 * Math.pow(1 - Math.abs(Math.cos(a * 4)), 2.2), yy = v.y / .17; const dimple = 1 - .25 * Math.pow(Math.max(0, Math.abs(yy) - .75) / .25, 2);
        v.x *= rib; v.z *= rib; v.y *= .78 * (Math.abs(yy) > .85 ? dimple : 1); pp.setXYZ(i, v.x, v.y, v.z); } geo.computeVertexNormals();
      const b = A(geo, P(c0, 'food'), g, .03); b.position.y = .135; b.scale.set(1.12, 1, 1.12);
      A(taperTube(new THREE.CatmullRomCurve3([new THREE.Vector3(0, .24, 0), new THREE.Vector3(.005, .29, 0), new THREE.Vector3(.03, .32, .01)]), 10, tt => .022 - tt * .01, 8), P('#6b7a3a', 'wood'), g, .04);
      const cv = new THREE.CatmullRomCurve3(Array.from({ length: 12 }, (_, i) => new THREE.Vector3(.03 + Math.cos(i * .9) * .025 + i * .006, .26 + Math.sin(i * .9) * .02, .02 + Math.sin(i * .9) * .025))); A(new THREE.TubeGeometry(cv, 40, .003, 4), P('#5a8a3a', 'plastic'), g, 0);
      if (jack) { const fm = new THREE.MeshBasicMaterial({ color: 0x3a1a08 }); fm.toneMapped = false; g.userData.faceMat = fm; const shp = (pts) => { const sh = new THREE.Shape(); pts.forEach((q, i) => i ? sh.lineTo(q[0], q[1]) : sh.moveTo(q[0], q[1])); return new THREE.ShapeGeometry(sh); };
        for (const sx of [-1, 1]) { const e = new THREE.Mesh(shp([[-.035, 0], [.035, 0], [0, .05]]), fm); e.position.set(sx * .065, .165, .176); e.rotation.y = sx * .35; e.rotation.x = -.2; g.add(e); }
        const mo = new THREE.Mesh(shp([[-.09, .02], [-.05, -.01], [-.03, .015], [0, -.02], [.03, .015], [.05, -.01], [.09, .02], [.06, -.04], [-.06, -.04]]), fm); mo.position.set(0, .095, .18); g.add(mo); fm.polygonOffset = true; fm.polygonOffsetFactor = -2;
        g.updateMatrixWorld(true); const rc = new THREE.Raycaster(), wv = new THREE.Vector3(); for (const fmesh of g.children.filter(o => o.material === fm)) { fmesh.rotation.set(0, 0, 0); fmesh.updateMatrixWorld(true); const pa = fmesh.geometry.attributes.position;
          for (let i = 0; i < pa.count; i++) { wv.set(pa.getX(i), pa.getY(i), 0).applyMatrix4(fmesh.matrixWorld); rc.set(new THREE.Vector3(wv.x, wv.y, 1), new THREE.Vector3(0, 0, -1)); const hit = rc.intersectObject(b, false)[0]; if (hit) { const loc = fmesh.worldToLocal(hit.point.clone()); pa.setZ(i, loc.z + .003); } }
          pa.needsUpdate = true; fmesh.geometry.computeVertexNormals(); }
        g.userData.glowY = .14; g.userData.glowS = .75; g.userData.glowC = '#ffb347'; }
      break; }
    case 'mushroom': { const c0 = cl || '#e8344e'; A(lathe([[0, 0], [.06, 0], [.05, .02], [.042, .08], [.045, .14], [0, .14]], 24), P('#f6efe2', 'food'));
      A(lathe([[0, .13], [.12, .13], [.16, .125], [.17, .14], [.14, .19], [.08, .225], [0, .23]], 36), P(c0, 'gloss')); const gl3 = A(G.cyl(.15, .15, .003, 36), P('#f3e6d0', 'food'), g, 0); gl3.position.y = .128;
      const capM = g.children[g.children.length - 2]; g.updateMatrixWorld(true); const rc = new THREE.Raycaster(), ctr = new THREE.Vector3(0, .12, 0); const r = rng(11);
      for (let i = 0; i < 10; i++) { const a = r() * Math.PI * 2, el = .2 + r() * 1.1; const dir = new THREE.Vector3(Math.cos(a) * Math.cos(el), Math.sin(el), Math.sin(a) * Math.cos(el)).normalize(); rc.set(ctr.clone().addScaledVector(dir, 1), dir.clone().negate()); const hit = rc.intersectObject(capM, false)[0]; if (!hit) continue;
        const d = A(G.sph(.016 + r() * .009, 14, 10), P('#ffffff', 'food'), g, 0); d.position.copy(hit.point); d.lookAt(hit.point.clone().add(hit.face.normal)); d.scale.z = .3; }
      break; }
    case 'umbrella': { const c0 = cl || '#3d8fe0'; const cn = new THREE.Group(); cn.position.y = .62; g.add(cn); const N = 8, segs = 10, P2 = [], I2 = [], C2 = [];
      const ca = new THREE.Color(c0), cb = new THREE.Color(lightC(c0, .45));
      for (let i = 0; i <= N * segs; i++) { const a = i / (N * segs) * Math.PI * 2, f = (i % segs) / segs, sag = Math.sin(f * Math.PI) * .035; for (let k = 0; k <= 6; k++) { const rr = k / 6 * .4, y = .2 * (1 - Math.pow(k / 6, 1.6)) - (k === 6 ? sag : sag * k / 6 * .5); P2.push(Math.cos(a) * rr * (1 - sag * .3 * k / 6), y, Math.sin(a) * rr * (1 - sag * .3 * k / 6)); const cc = Math.floor(i / segs) % 2 ? ca : cb; C2.push(cc.r, cc.g, cc.b); } }
      for (let i = 0; i < N * segs; i++) for (let k = 0; k < 6; k++) { const a = i * 7 + k, b = a + 7; I2.push(a, b, a + 1, b, b + 1, a + 1); }
      const ug = new THREE.BufferGeometry(); ug.setAttribute('position', new THREE.Float32BufferAttribute(P2, 3)); ug.setAttribute('color', new THREE.Float32BufferAttribute(C2, 3)); ug.setIndex(I2); ug.computeVertexNormals();
      const um = MK3D.hq ? new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: .45, clearcoat: .5, side: THREE.DoubleSide, sheen: .3 }) : new THREE.MeshToonMaterial({ vertexColors: true, gradientMap: grad, side: THREE.DoubleSide }); A(ug, um, cn, .02);
      A(G.cyl(.008, .008, .62, 8), P('#3a3a3a', 'metal'), g, 0).position.y = .31 + .02; A(G.sph(.014, 10, 8), P('#3a3a3a', 'metal'), cn, 0).position.y = .22;
      const hv = new THREE.CatmullRomCurve3([new THREE.Vector3(0, .05, 0), new THREE.Vector3(0, 0, 0), new THREE.Vector3(.03, -.04, 0), new THREE.Vector3(.07, -.01, 0), new THREE.Vector3(.07, .03, 0)]); const hh = A(new THREE.TubeGeometry(hv, 16, .014, 8), P('#7a4e30', 'wood'), g, .03); hh.position.y = .04; break; }
    case 'candy': { const c0 = cl || '#ff6fa8'; const tx = stripesT([c0, '#ffffff'], true); tx.repeat.set(3, 1); const b = A(G.sph(.065, 28, 18), P(null, 'gloss', tx)); b.scale.set(1.35, 1, 1); b.position.y = .07; b.rotation.x = .6;
      for (const s of [-1, 1]) { const w = A(lathe([[0, 0], [.035, .01], [.05, .05], [.065, .08], [.03, .07], [0, .085]], 10), P(c0, 'gloss'), g, .02); w.rotation.z = -s * Math.PI / 2; w.position.set(s * .07, .07, 0); } break; }
    case 'icecream': { const c0 = cl || '#ffb3c8'; const cn = A(lathe([[0, 0], [.07, .2], [.075, .21], [0, .21]], 28), P(null, 'food', waffleT())); cn.position.y = 0;
      for (const [c1, y, r] of [[c0, .245, .078], ['#fff3e0', .33, .066]]) { const s = A(G.sph(r, 28, 20), P(c1, 'food'), g, .03); s.position.y = y; const rim = A(G.tor(r * .95, r * .22, 10, 28), P(c1, 'food'), g, 0); rim.rotation.x = Math.PI / 2; rim.position.y = y - r * .55; }
      const r = rng(2); const cols = ['#ff4d6d', '#3d8fe0', '#ffd23f', '#5fbf4a', '#ffffff']; for (let i = 0; i < 18; i++) { const u = r() * 2 - 1, a = r() * 6.28, s2 = Math.sqrt(1 - u * u); if (u < -.2) continue; const sp = A(G.cap(.004, .012, 2, 6), P(cols[i % 5], 'gloss'), g, 0); sp.position.set(s2 * Math.cos(a) * .067, .33 + u * .067, s2 * Math.sin(a) * .067); sp.rotation.set(r() * 3, r() * 3, r() * 3); }
      const ch = A(G.sph(.02, 14, 10), P('#d8213a', 'gloss'), g, 0); ch.position.y = .405; break; }
    case 'lollipop': { const c0 = cl || '#ff4d6d'; A(G.cyl(.008, .008, .3, 8), P('#ffffff', 'paper'), g, 0).position.y = .15; const l = A(new THREE.CylinderGeometry(.1, .1, .03, 40), P(null, 'gloss', swirlT(c0, '#ffffff')), g, .03); l.rotation.x = Math.PI / 2; l.position.y = .38;
      const rb = A(G.tor(.016, .006, 8, 16), P('#5fbf4a', 'gloss'), g, 0); rb.position.y = .285; rb.scale.x = 1.6; break; }
    case 'banana': { const c0 = cl || '#ffd23f'; const cv = new THREE.CatmullRomCurve3([new THREE.Vector3(-.13, .11, 0), new THREE.Vector3(-.06, .05, 0), new THREE.Vector3(.04, .04, 0), new THREE.Vector3(.13, .11, 0)]);
      const bgeo = taperTube(cv, 24, tt => .038 * Math.pow(Math.sin(Math.PI * Math.min(1, Math.max(0, tt * .96 + .02))), .55) + .004, 5); bgeo.computeBoundingBox(); const bc = bgeo.boundingBox.getCenter(new THREE.Vector3()); bgeo.translate(-bc.x, -bc.y, -bc.z); const b = A(bgeo, P(c0, 'food')); b.position.copy(bc); for (const [tt, c1] of [[0, '#5a3a22'], [1, '#6a7a2a']]) { const q = cv.getPointAt(tt); const e = A(G.sph(.01, 8, 6), P(c1, 'wood'), g, 0); e.position.copy(q); } break; }
    case 'pear': { const c0 = cl || '#b8d84a'; A(lathe([[0, 0], [.06, .005], [.105, .05], [.112, .1], [.085, .16], [.055, .21], [.045, .25], [.02, .275], [0, .28]], 36), P(null, 'gloss', speckT(c0, shadeC(c0, .7), 120)));
      A(taperTube(new THREE.CatmullRomCurve3([new THREE.Vector3(0, .27, 0), new THREE.Vector3(.01, .31, 0), new THREE.Vector3(.025, .33, 0)]), 8, tt => .007 - tt * .002, 6), P('#5a3a22', 'wood'), g, 0); break; }
    case 'watermelon': { const w = A(G.sph(.22, 40, 28), P(null, 'gloss', melonT())); w.scale.set(1.18, .92, .92); w.position.y = .2; w.rotation.z = Math.PI / 2; break; }
    case 'honey': { A(lathe([[0, 0], [.1, 0], [.13, .06], [.135, .13], [.11, .2], [.08, .22], [.085, .24], [.075, .25], [0, .25]], 36), P('#c88a30', 'ceramic'));
      const lab = A(lathe([[.133, .09], [.137, .09], [.137, .15], [.133, .15]], 36), P('#fff3d0', 'paper'), g, 0);
      A(lathe([[0, .245], [.075, .245], [.075, .255], [0, .26]], 24), P('#ffb514', 'gloss'), g, 0); for (let i = 0; i < 5; i++) { const a = i * 1.3, dl = .03 + (i % 3) * .02; const d = A(G.cap(.012, dl), P('#ffb514', 'gloss'), g, 0); d.position.set(Math.cos(a) * .088, .235 - dl / 2, Math.sin(a) * .088); }
      const dp = A(G.cyl(.006, .006, .22, 8), P('#a8743f', 'wood'), g, 0); dp.position.set(.03, .3, 0); dp.rotation.z = -.35; const dh = A(lathe([[0, 0], [.02, .005], [.022, .03], [.02, .045], [0, .05]], 12), P('#a8743f', 'wood'), g, 0); dh.position.set(-.005, .2, 0); dh.rotation.z = -.35; break; }
    case 'bucket': { const c0 = cl || '#3d8fe0'; const b = A(lathe([[0, 0], [.11, 0], [.15, .22], [.16, .225], [.155, .235], [.14, .23], [.1, .015], [0, .015]], 36), P(c0, 'plastic')); b.material.side = THREE.DoubleSide;
      for (const y of [.06, .16]) { const rr = .11 + (y / .22) * .04; const band = A(G.tor(rr + .004, .005, 8, 40), P(shadeC(c0, .85), 'plastic'), g, 0); band.rotation.x = Math.PI / 2; band.position.y = y; }
      const hd = A(G.tor(.155, .006, 8, 32, Math.PI), P('#9a9a9a', 'metal'), g, 0); hd.position.y = .225; hd.rotation.y = .3; break; }
    case 'shovel': { const c0 = cl || '#e8344e'; const hd = A(G.cyl(.012, .012, .36, 10), P('#d9a066', 'wood'), g, .03); hd.position.y = .3; const tg = A(G.cap(.014, .07, 4, 8), P(c0, 'plastic'), g, .03); tg.rotation.z = Math.PI / 2; tg.position.y = .49;
      const bs = new THREE.Shape(); bs.moveTo(-.06, 0); bs.lineTo(.06, 0); bs.lineTo(.065, -.1); bs.quadraticCurveTo(0, -.18, -.065, -.1); bs.closePath(); const bl = A(ext(bs, .01, .004), P(c0, 'plastic')); bl.position.y = .13; const pp = bl.geometry.attributes.position; for (let i = 0; i < pp.count; i++) pp.setZ(i, pp.getZ(i) + Math.pow(pp.getX(i) / .065, 2) * .02); bl.geometry.computeVertexNormals(); break; }
    case 'car': { const c0 = cl || '#e8344e'; const side = new THREE.Shape(); side.moveTo(-.19, .04); side.lineTo(.19, .04); side.quadraticCurveTo(.21, .04, .21, .07); side.lineTo(.2, .11); side.lineTo(.08, .12); side.lineTo(.04, .19); side.quadraticCurveTo(0, .2, -.08, .2); side.lineTo(-.13, .2); side.lineTo(-.17, .12); side.lineTo(-.2, .11); side.lineTo(-.21, .06); side.quadraticCurveTo(-.21, .04, -.19, .04);
      A(ext(side, .17, .02), P(c0, 'gloss'));
      const ws = new THREE.Shape(); ws.moveTo(.035, .125); ws.lineTo(.075, .125); ws.lineTo(.04, .182); ws.lineTo(.0, .186); ws.closePath(); for (const z of [-.096, .096]) { for (const dx of [0, -.15]) { const w = A(new THREE.ShapeGeometry(ws), P('#233040', 'glass'), g, 0); w.material = pmat('#6fa8d8', 'gloss'); w.position.set(dx, 0, z); if (dx) w.scale.x = -1, w.position.x = -.08; } }
      for (const x of [-.12, .12]) for (const z of [-.09, .09]) { const tw = A(G.tor(.034, .016, 12, 24), P('#2a2a2a', 'plastic'), g, .03); tw.position.set(x, .05, z); const hc = A(G.cyl(.022, .022, .03, 16), P('#d8d8d8', 'metal'), g, 0); hc.rotation.x = Math.PI / 2; hc.position.set(x, .05, z); }
      for (const z of [-.05, .05]) { const hl = A(G.sph(.018, 12, 8), P('#fff6c8', 'glow'), g, 0); hl.position.set(.205, .085, z); hl.scale.x = .5; } break; }
    case 'teddy': { const c0 = cl || '#b07a4a', m0 = P(c0, 'cloth'), mi = P(lightC(c0, .35), 'cloth'); const add = (geo, mat, x, y, z, sx, sy, sz) => { const e = A(geo, mat, g, .03); e.position.set(x, y, z); if (sx) e.scale.set(sx, sy, sz); return e; };
      add(G.sph(.11, 24, 18), m0, 0, .13, 0, 1, 1.1, .9); add(G.sph(.065, 18, 12), mi, 0, .12, .07, 1, 1.1, .5); add(G.sph(.09, 24, 18), m0, 0, .3, 0); for (const s of [-1, 1]) { add(G.sph(.035, 14, 10), m0, s * .07, .375, 0); add(G.sph(.02, 12, 8), mi, s * .07, .375, .015, 1, 1, .5); add(G.sph(.04, 14, 10), m0, s * .1, .16, .03, 1, 1.4, 1); add(G.sph(.045, 14, 10), m0, s * .06, .04, .03, 1, .8, 1.2); }
      add(G.sph(.04, 16, 12), mi, 0, .28, .07, 1.2, .9, .8); add(G.sph(.014, 10, 8), P('#2b1d16', 'gloss'), 0, .29, .105); for (const s of [-1, 1]) add(G.sph(.012, 10, 8), P('#111111', 'gloss'), s * .033, .32, .075);
      const bw = add(G.tor(.018, .008, 8, 16), P('#e8344e', 'gloss'), 0, .215, .08); bw.scale.set(1.8, 1, 1); break; }
    case 'drum': { const c0 = cl || '#e8344e'; A(G.cyl(.15, .15, .14, 40, true), P(c0, 'gloss')).position.y = .08; for (const y of [.012, .148]) { const rim = A(G.tor(.152, .009, 8, 40), P('#d8d8d8', 'metal'), g, 0); rim.rotation.x = Math.PI / 2; rim.position.y = y; }
      A(G.cyl(.15, .15, .004, 40), P('#fbf6ea', 'paper'), g, 0).position.y = .15; A(G.cyl(.15, .15, .004, 40), P('#fbf6ea', 'paper'), g, 0).position.y = .01;
      for (let i = 0; i < 10; i++) { const a = i / 10 * Math.PI * 2, a2 = (i + .5) / 10 * Math.PI * 2; const c1 = new THREE.LineCurve3(new THREE.Vector3(Math.cos(a) * .153, .018, Math.sin(a) * .153), new THREE.Vector3(Math.cos(a2) * .153, .142, Math.sin(a2) * .153)); A(new THREE.TubeGeometry(c1, 2, .003, 4), P('#ffffff', 'cloth'), g, 0); }
      for (const s of [-1, 1]) { const st = A(G.cyl(.006, .008, .26, 8), P('#d9a066', 'wood'), g, 0); st.position.set(s * .05, .2, .05); st.rotation.set(.3, 0, s * .9); const tip = A(G.sph(.013, 10, 8), P('#d9a066', 'wood'), st, 0); tip.position.y = .13; } break; }
    case 'guitar': { const c0 = cl || '#c88a30'; const gs = new THREE.Shape(); gs.moveTo(0, 0); gs.bezierCurveTo(.13, 0, .14, .12, .08, .16); gs.bezierCurveTo(.05, .18, .1, .25, .07, .29); gs.bezierCurveTo(.04, .33, -.04, .33, -.07, .29); gs.bezierCurveTo(-.1, .25, -.05, .18, -.08, .16); gs.bezierCurveTo(-.14, .12, -.13, 0, 0, 0);
      const bd = A(ext(gs, .06, .01), P(null, 'wood', grainTex(c0)), g, .03); const hole = A(G.cyl(.032, .032, .002, 24), P('#1c120a', 'paper'), g, 0); hole.rotation.x = Math.PI / 2; hole.position.set(0, .17, .041); const rr = A(G.tor(.036, .004, 6, 24), P('#3a2414', 'wood'), g, 0); rr.position.set(0, .17, .04);
      const nk = A(G.box(.03, .26, .02), P('#5a3a22', 'wood'), g, .02); nk.position.set(0, .44, .02); const hs = A(G.box(.05, .07, .018), P('#3a2414', 'wood'), g, .02); hs.position.set(0, .6, .02);
      for (let i = 0; i < 4; i++) { const sx = (i - 1.5) * .006; const sg = A(G.cyl(.0012, .0012, .5, 4), P('#e8e8e8', 'metal'), g, 0); sg.position.set(sx, .33, .043); } const br = A(G.box(.06, .01, .006), P('#3a2414', 'wood'), g, 0); br.position.set(0, .08, .043);
      g.rotation.x = -.1; g.position.y = 0; break; }
    case 'wand': { A(G.cyl(.008, .01, .3, 10), P('#2a1d33', 'gloss'), g, .03).position.y = .15; A(G.cyl(.0105, .0105, .05, 10), P('#ffffff', 'gloss'), g, 0).position.y = .045;
      const s = A(ext(starShape(.06, .027), .016, .006), P(cl || '#ffd23f', 'glow'), g, .03); s.position.y = .33; g.userData.glowY = .33; g.userData.glowS = .35; g.userData.glowC = '#fff2a8'; g.userData.alwaysGlow = true; break; }
    case 'lantern': { const fr = P('#3a3f4a', 'metal'); A(lathe([[0, 0], [.07, 0], [.07, .02], [.06, .025], [0, .025]], 24), fr); A(lathe([[0, .2], [.065, .2], [.075, .21], [.05, .25], [.02, .26], [0, .26]], 24), fr, g, .03);
      for (let i = 0; i < 4; i++) { const a = i / 4 * Math.PI * 2 + Math.PI / 4; const pst = A(G.cyl(.004, .004, .18, 6), fr, g, 0); pst.position.set(Math.cos(a) * .058, .11, Math.sin(a) * .058); }
      const gl = A(G.cyl(.056, .056, .17, 24, true), pmat('#fff4c8', 'glass'), g, 0); gl.position.y = .11; A(G.cyl(.016, .016, .06, 12), P('#fff7e0', 'wax'), g, 0).position.y = .055;
      const fl = A(G.sph(.014, 10, 8), P('#ffb703', 'glow'), g, 0); fl.position.y = .1; fl.scale.y = 1.8; g.userData.flames = [fl]; const rg = A(G.tor(.03, .004, 6, 16), fr, g, 0); rg.position.y = .28;
      g.userData.glowY = .11; g.userData.glowS = .45; g.userData.glowC = '#ffd27a'; g.userData.alwaysGlow = true; break; }
    case 'map': { const geo = new THREE.PlaneGeometry(.32, .22, 24, 2); const pp = geo.attributes.position; for (let i = 0; i < pp.count; i++) { const x = pp.getX(i); const u = (x + .16) / .32; pp.setZ(i, (Math.pow(Math.max(0, .15 - u) / .15, 2) + Math.pow(Math.max(0, u - .85) / .15, 2)) * .03); } geo.computeVertexNormals();
      const m0 = A(geo, P(null, 'paper', parchT(true)), g, 0); m0.material = m0.material.clone ? m0.material : m0.material; m0.material.side = THREE.DoubleSide; m0.rotation.x = -Math.PI / 2; m0.position.y = .005;
      for (const s of [-1, 1]) { const rl = A(G.cyl(.012, .012, .22, 16), P(null, 'paper', parchT(false)), g, 0); rl.rotation.x = Math.PI / 2; rl.position.set(s * .165, .016, 0); } break; }
    case 'letter': { const c0 = cl || '#fbf6ea'; const env = A(G.box(.24, .006, .16), P(c0, 'paper'), g, .02); env.position.y = .004; const fl = new THREE.Shape(); fl.moveTo(-.12, 0); fl.lineTo(.12, 0); fl.lineTo(0, -.09); fl.closePath();
      const f = A(new THREE.ShapeGeometry(fl), P(shadeC(c0, .93), 'paper'), g, 0); f.rotation.x = -Math.PI / 2; f.position.set(0, .0075, -.08); const sl = A(G.cyl(.022, .022, .006, 20), P('#c0283c', 'wax'), g, 0); sl.position.set(0, .01, .005); break; }
    case 'basket': { const c0 = cl || '#c9944f'; const tx = weaveT(c0); const b = A(lathe([[0, 0], [.12, 0], [.165, .14], [.172, .145], [.168, .155], [.155, .15], [.112, .012], [0, .012]], 32), P(null, 'wood', tx)); b.material.side = THREE.DoubleSide;
      const rim = A(G.tor(.168, .012, 8, 40), P(shadeC(c0, .9), 'wood'), g, 0); rim.rotation.x = Math.PI / 2; rim.position.y = .15; const hd = A(G.tor(.16, .012, 8, 32, Math.PI), P(shadeC(c0, .9), 'wood'), g, .02); hd.position.y = .15;
      const ap = [[.05, .02, '#e23b3b'], [-.04, -.04, '#e23b3b'], [-.03, .06, '#b8d84a']]; for (const [x, z, c1] of ap) { const a2 = A(G.sph(.045, 16, 12), P(c1, 'gloss'), g, 0); a2.position.set(x, .13, z); } break; }
    case 'chest': { const c0 = cl || '#8a5a3a', wd = P(null, 'wood', grainTex(c0)), mt = P('#d8a93a', 'metal'); A(G.box(.4, .2, .26), wd, g, .03).position.y = .1;
      const lidS = new THREE.Shape(); lidS.moveTo(-.13, 0); lidS.lineTo(.13, 0); lidS.absarc(0, 0, .13, 0, Math.PI, false); const lid = A(ext(lidS, .4, .006), wd, g, .03); lid.rotation.y = Math.PI / 2; lid.position.y = .2; lid.scale.y = .6;
      for (const x of [-.15, .15]) { const bd = A(G.box(.03, .205, .27), mt, g, 0); bd.position.set(x, .1, 0); const lb = new THREE.Mesh(new THREE.TorusGeometry(.131, .008, 6, 24, Math.PI), mt); lb.position.set(x, .2, 0); lb.rotation.y = Math.PI / 2; lb.scale.y = .62; g.add(lb); }
      const lk = A(G.box(.06, .07, .015), mt, g, .02); lk.position.set(0, .19, .135); const kh = A(G.cyl(.007, .007, .02, 8), P('#2a1a0a', 'paper'), g, 0); kh.rotation.x = Math.PI / 2; kh.position.set(0, .185, .14); break; }
    case 'coin': { const c0 = cl || '#ffd23f'; const c2 = A(lathe([[0, -.009], [.058, -.009], [.062, -.005], [.062, .005], [.058, .009], [0, .009]], 40), MK3D.hq ? (() => { const m = pmat(c0, 'metal').clone(); m.bumpMap = coinT(); m.bumpScale = 3; return m; })() : P(c0, 'metal'), g, .03); c2.rotation.x = Math.PI / 2 - .3; c2.position.y = .065; break; }
    case 'egg': { A(lathe(Array.from({ length: 25 }, (_, i) => { const a = i / 24 * Math.PI; const y = (1 - Math.cos(a)) / 2; return [Math.sin(a) * .064 * (1 - .16 * y), y * .165]; }), 40), P(null, 'gloss', speckT(cl || '#fff4e0', '#d8c0a0', 50))); break; }
    case 'pie': { A(lathe([[0, 0], [.15, 0], [.18, .05], [.19, .06], [.18, .065], [0, .065]], 40), P('#e8e2d6', 'ceramic'));
      A(lathe([[0, .07], [.17, .06], [.18, .075], [.17, .085], [0, .09]], 40), P(cl || '#e8b870', 'food')); for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2; const b = A(G.sph(.016, 10, 8), P('#d9a050', 'food'), g, 0); b.position.set(Math.cos(a) * .175, .075, Math.sin(a) * .175); b.scale.set(1, .8, 1.4); b.rotation.y = -a; }
      for (let i = -2; i <= 2; i++) for (const rot of [0, Math.PI / 2]) { const st = A(G.box(.3 * Math.cos(Math.asin(Math.min(.95, Math.abs(i) * .055 / .15))), .01, .022), P('#e0a858', 'food'), g, 0); st.position.set(rot ? 0 : 0, .092, 0); st.rotation.y = rot; st.translateZ(i * .055); }
      break; }
    case 'cookie': { const geo = G.cyl(.08, .08, .018, 40, false); const pp = geo.attributes.position; for (let i = 0; i < pp.count; i++) { if (pp.getY(i) > 0) pp.setY(i, pp.getY(i) + Math.sin(pp.getX(i) * 90) * Math.cos(pp.getZ(i) * 80) * .002); } geo.computeVertexNormals(); const ck = A(geo, P(null, 'food', speckT(cl || '#d9a066', '#b07a3a', 80))); ck.position.y = .01;
      const r = rng(21); for (let i = 0; i < 9; i++) { const a = r() * 6.28, rr = r() * .065; const ch = A(G.sph(.009, 8, 6), P('#3a2010', 'gloss'), g, 0); ch.position.set(Math.cos(a) * rr, .02, Math.sin(a) * rr); ch.scale.y = .7; } break; }
    case 'milk': { const gl = A(lathe([[0, 0], [.055, 0], [.06, .01], [.06, .17], [.045, .21], [.03, .24], [.032, .26], [0, .26]], 32), pmat('#e8f2ff', 'glass'), g, 0);
      A(lathe([[0, .005], [.054, .005], [.055, .015], [.055, .165], [.042, .2], [0, .2]], 32), P('#ffffff', 'food'), g, .03); A(G.cyl(.034, .034, .02, 20), P(cl || '#3d8fe0', 'gloss'), g, 0).position.y = .265;
      A(lathe([[.0605, .07], [.0625, .07], [.0625, .12], [.0605, .12]], 32), P('#3d8fe0', 'paper'), g, 0); break; }
    case 'clock': { const c0 = cl || '#e8344e'; const b = A(lathe([[0, -.03], [.11, -.03], [.125, -.015], [.125, .015], [.11, .03], [0, .03]], 40), P(c0, 'gloss'), g, .03); b.rotation.x = Math.PI / 2; b.position.y = .16;
      const f = A(new THREE.CircleGeometry(.1, 40), P(null, 'paper', clockT()), g, 0); f.position.set(0, .16, .031); const gl2 = A(G.sph(.1, 32, 16, 0, Math.PI * 2, 0, .5), pmat('#ffffff', 'glass'), g, 0); gl2.rotation.x = Math.PI / 2; gl2.position.set(0, .16, .012); gl2.scale.z = .25;
      const h1 = A(G.box(.008, .055, .003), P('#2b1d16', 'paper'), g, 0); h1.position.set(.014, .18, .034); h1.rotation.z = -.5; const h2 = A(G.box(.006, .08, .003), P('#2b1d16', 'paper'), g, 0); h2.position.set(-.02, .19, .035); h2.rotation.z = .5;
      for (const s of [-1, 1]) { const bl = A(G.sph(.04, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), P('#d8d8d8', 'metal'), g, .02); bl.position.set(s * .07, .27, 0); bl.rotation.z = -s * .5; const lg = A(G.cyl(.008, .01, .05, 8), P('#d8d8d8', 'metal'), g, 0); lg.position.set(s * .07, .03, 0); lg.rotation.z = s * .4; }
      const hm = A(G.cyl(.006, .006, .14, 8), P('#d8d8d8', 'metal'), g, 0); hm.rotation.z = Math.PI / 2; hm.position.y = .3; break; }
    case 'candle': { const c0 = cl || '#fff3e0'; A(lathe([[0, 0], [.09, 0], [.095, .012], [.03, .016], [0, .016]], 32), P('#d8a93a', 'metal'));
      A(lathe([[0, .016], [.035, .016], [.035, .17], [.03, .18], [0, .178]], 24), P(c0, 'wax')); for (let i = 0; i < 4; i++) { const a = i * 1.7, dl = .02 + i * .012; const d = A(G.cap(.006, dl), P(c0, 'wax'), g, 0); d.position.set(Math.cos(a) * .034, .17 - dl / 2, Math.sin(a) * .034); }
      A(G.cyl(.002, .002, .02, 4), P('#2b1d16', 'paper'), g, 0).position.y = .19; const fl = A(lathe([[0, 0], [.012, .008], [.014, .02], [.008, .04], [0, .055]], 16), P('#ffb703', 'glow'), g, 0); fl.position.y = .195; const fi = A(lathe([[0, 0], [.006, .006], [.006, .016], [0, .025]], 12), P('#fff6c8', 'glow'), g, 0); fi.position.y = .197;
      g.userData.flames = [fl]; g.userData.glowY = .22; g.userData.glowS = .3; g.userData.glowC = '#ffd27a'; g.userData.alwaysGlow = true; break; }
    case 'leaf': { const c0 = cl || '#e8842a'; const sh = new THREE.Shape(); const N0 = 60; for (let i = 0; i <= N0; i++) { const u = i / N0, side = u < .5 ? 1 : -1, v = u < .5 ? u * 2 : (1 - u) * 2; const y = v * .2, w = Math.sin(Math.PI * Math.pow(v, .8)) * .07 * (1 + .18 * Math.sin(v * Math.PI * 6)); const x = side * w; i ? sh.lineTo(x, y) : sh.moveTo(x, y); }
      const geo = new THREE.ShapeGeometry(sh, 4); const pp = geo.attributes.position, uv = geo.attributes.uv; for (let i = 0; i < pp.count; i++) { const x = pp.getX(i), y = pp.getY(i); pp.setZ(i, Math.pow(x / .07, 2) * .012 + Math.pow(y / .2, 2) * .025); uv.setXY(i, x / .14 + .5, y / .2); } geo.computeVertexNormals();
      const lt = ctex('leafT' + c0, 64, 128, (q) => { const gr = q.createLinearGradient(0, 128, 0, 0); gr.addColorStop(0, shadeC(c0, .85)); gr.addColorStop(1, lightC(c0, .15)); q.fillStyle = gr; q.fillRect(0, 0, 64, 128); q.strokeStyle = shadeC(c0, .65); q.lineWidth = 2.5; q.beginPath(); q.moveTo(32, 128); q.lineTo(32, 4); q.stroke(); q.lineWidth = 1.2; for (let y = 112; y > 16; y -= 14) { q.beginPath(); q.moveTo(32, y); q.lineTo(8, y - 16); q.moveTo(32, y); q.lineTo(56, y - 16); q.stroke(); } });
      const lf = A(geo, P(null, 'plastic', lt), g, 0); lf.material.side = THREE.DoubleSide; lf.rotation.x = -Math.PI / 2 + .12; lf.position.set(0, .012, .1); const st2 = A(G.cyl(.003, .002, .05, 5), P(shadeC(c0, .6), 'wood'), g, 0); st2.rotation.x = Math.PI / 2; st2.position.set(0, .01, .12); break; }
    case 'rock': { const geo = new THREE.IcosahedronGeometry(.13, 3); const pp = geo.attributes.position, v = new THREE.Vector3(); for (let i = 0; i < pp.count; i++) { v.fromBufferAttribute(pp, i); const k = 1 + Math.sin(v.x * 30 + v.y * 11) * .08 + Math.sin(v.z * 25) * .06 + Math.sin(v.y * 40) * .02; pp.setXYZ(i, v.x * k, v.y * k * .7, v.z * k); } geo.computeVertexNormals();
      const r2 = A(geo, P(null, 'wood', speckT(cl || '#9a968c', '#77736a', 300))); r2.position.y = .07; break; }
    case 'stick': { const cv = new THREE.CatmullRomCurve3([new THREE.Vector3(-.25, .02, 0), new THREE.Vector3(-.08, .03, .02), new THREE.Vector3(.08, .02, -.01), new THREE.Vector3(.25, .03, 0)]); A(taperTube(cv, 20, tt => .02 - tt * .008, 8), P(null, 'wood', barkTex()));
      for (const [tt, dir] of [[.35, 1], [.65, -1]]) { const q = cv.getPointAt(tt); const tw = new THREE.CatmullRomCurve3([q, q.clone().add(new THREE.Vector3(.04, .03, dir * .05)), q.clone().add(new THREE.Vector3(.08, .04, dir * .08))]); A(taperTube(tw, 8, x => .008 - x * .005, 6), P(null, 'wood', barkTex()), g, 0); const lf = A(leafGeo(false), P('#5fbf4a', 'plastic'), g, 0); lf.scale.setScalar(.06); lf.position.copy(tw.getPointAt(1)); lf.rotation.set(-1, 0, -1.2); } break; }
    case 'phone': { const c0 = cl || '#2a2a2a'; const ph = A(ext(rrect(.08, .16, .014), .012, .003), P(c0, 'gloss')); ph.position.y = .085; const sc = A(new THREE.PlaneGeometry(.07, .145), P(null, 'glow', phoneT()), g, 0); sc.position.set(0, .085, .0095); sc.material = MK3D.hq ? new THREE.MeshBasicMaterial({ map: phoneT() }) : toon(null, phoneT());
      const cm = A(G.cyl(.006, .006, .004, 12), P('#111', 'gloss'), g, 0); cm.rotation.x = Math.PI / 2; cm.position.set(-.022, .145, -.009); break; }
    case 'kite': { const c0 = cl || '#ff6fa8', top = new THREE.Group(); top.position.y = .95; g.add(top); const quad = (pts, c1) => { const sh = new THREE.Shape(); pts.forEach(([x, y], i) => i ? sh.lineTo(x, y) : sh.moveTo(x, y)); const q = A(new THREE.ShapeGeometry(sh), P(c1, 'cloth'), top, 0); q.material.side = THREE.DoubleSide; return q; };
      quad([[0, .2], [.13, .03], [0, .03]], c0); quad([[0, .2], [-.13, .03], [0, .03]], '#ffd23f'); quad([[0, -.24], [.13, .03], [0, .03]], '#3d8fe0'); quad([[0, -.24], [-.13, .03], [0, .03]], lightC(c0, .3));
      for (const [a, b] of [[[0, .2, .003], [0, -.24, .003]], [[-.13, .03, .003], [.13, .03, .003]]]) A(new THREE.TubeGeometry(new THREE.LineCurve3(new THREE.Vector3(...a), new THREE.Vector3(...b)), 2, .003, 5), P('#7a4e30', 'wood'), top, 0);
      const tail = new THREE.CatmullRomCurve3([new THREE.Vector3(0, -.24, 0), new THREE.Vector3(.04, -.35, 0), new THREE.Vector3(-.03, -.47, 0), new THREE.Vector3(.02, -.58, 0)]); A(new THREE.TubeGeometry(tail, 20, .002, 4), P('#555', 'plastic'), top, 0);
      for (let i = 1; i <= 3; i++) { const q = tail.getPointAt(i / 4); for (const s of [-1, 1]) { const bw = A(G.cone(.018, .035, 4), P(['#ff4d6d', '#ffd23f', '#5fbf4a'][i - 1], 'cloth'), top, 0); bw.position.copy(q).x += s * .017; bw.rotation.z = s * Math.PI / 2; } }
      A(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([new THREE.Vector3(0, .95, 0), new THREE.Vector3(.05, .5, .02), new THREE.Vector3(0, 0, 0)]), 20, .0015, 4), P('#ffffff', 'plastic'), g, 0); g.userData.float = true; break; }
    case 'bag': { const c0 = cl || '#c0283c'; const bs = new THREE.Shape(); bs.moveTo(-.14, 0); bs.lineTo(.14, 0); bs.quadraticCurveTo(.15, .0, .14, .03); bs.lineTo(.11, .19); bs.lineTo(-.11, .19); bs.lineTo(-.14, .03); bs.quadraticCurveTo(-.15, 0, -.14, 0);
      A(ext(bs, .09, .015), P(c0, 'gloss'), g, .03).position.y = .01; const fl = A(ext(rrect(.23, .08, .03), .01, .004), P(shadeC(c0, .88), 'gloss'), g, 0); fl.position.set(0, .16, .056); A(G.box(.03, .02, .01), P('#d8a93a', 'metal'), g, 0).position.set(0, .12, .064);
      const hd = A(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([new THREE.Vector3(-.08, .2, 0), new THREE.Vector3(-.06, .29, 0), new THREE.Vector3(.06, .29, 0), new THREE.Vector3(.08, .2, 0)]), 20, .009, 8), P('#5a3a2a', 'gloss'), g, .03); break; }
    case 'door': { const wd = P(null, 'wood', grainTex(cl || '#a8673a')), fr = P(null, 'wood', grainTex('#7a4e30')); const ds = new THREE.Shape(); ds.moveTo(-.26, 0); ds.lineTo(.26, 0); ds.lineTo(.26, .82); ds.absarc(0, .82, .26, 0, Math.PI, false); ds.lineTo(-.26, 0);
      const fs = new THREE.Shape(); fs.moveTo(-.33, 0); fs.lineTo(.33, 0); fs.lineTo(.33, .82); fs.absarc(0, .82, .33, 0, Math.PI, false); fs.lineTo(-.33, 0); fs.holes.push(ds);
      A(ext(fs, .1, .01), fr, g, .02); const leaf = new THREE.Group(); leaf.position.x = -.26; g.add(leaf); const lg = new THREE.Group(); lg.position.x = .26; leaf.add(lg); const d = A(ext(ds, .05, .008), wd, lg, .02); d.position.z = .0;
      for (const [x, y, w, h] of [[-.12, .15, .16, .3], [.12, .15, .16, .3], [-.12, .55, .16, .3], [.12, .55, .16, .3]]) { const pn = A(ext(rrect(w, h, .02), .01, .006), wd, lg, 0); pn.position.set(x, y + h / 2, .03); }
      const kn = A(G.sph(.025, 14, 10), P('#d8a93a', 'metal'), lg, 0); kn.position.set(.19, .5, .05); for (const y of [.15, .85]) { const hg = A(G.box(.08, .03, .01), P('#3a3a3a', 'metal'), lg, 0); hg.position.set(-.22, y, .03); }
      const light = new THREE.Mesh(new THREE.ShapeGeometry(ds, 24), new THREE.MeshBasicMaterial({ color: '#fff1b8', toneMapped: false, transparent: true, opacity: 0 })); light.position.z = .012; g.add(light); g.userData.leaf = leaf; g.userData.doorLight = light;
      const st = A(G.box(.8, .04, .18), P(null, 'wood', stoneT()), g, 0); st.position.y = .02; g.userData.glowY = .6; g.userData.glowS = 1.6; g.userData.glowC = '#ffe08a'; break; }
    case 'moon': { const mo = A(G.sph(.5, 40, 28), MK3D.hq ? new THREE.MeshBasicMaterial({ map: craterT(), toneMapped: false }) : basic(cl || '#fff3c4'), g, 0); mo.position.y = 4.2; mo.castShadow = false; g.userData.glowY = 4.2; g.userData.glowS = 2.6; g.userData.glowC = '#fff3c4'; g.userData.alwaysGlow = true; break; }
    case 'ghost': { const pts = [[.34, 0], [.32, .12], [.29, .3], [.275, .45]]; for (let i = 1; i <= 16; i++) { const a = i / 16 * Math.PI / 2; pts.push([Math.cos(a) * .275, .45 + Math.sin(a) * .3]); } pts.push([0, .75]);
      const geo = lathe(pts, 56); const pp = geo.attributes.position; for (let i = 0; i < pp.count; i++) { if (pp.getY(i) < .01) { const a = Math.atan2(pp.getZ(i), pp.getX(i)); pp.setY(i, pp.getY(i) + Math.sin(a * 7) * .035 + .035); } } geo.computeVertexNormals();
      const gm = MK3D.hq ? new THREE.MeshPhysicalMaterial({ color: '#ffffff', roughness: .6, transparent: true, opacity: .88, side: THREE.DoubleSide, sheen: .6, emissive: '#cfe0ff', emissiveIntensity: .25 }) : toon('#ffffff'); const b = A(geo, gm, g, .03); b.position.y = .25;
      for (const sx of [-1, 1]) { const e = A(G.sph(.035, 14, 10), P('#1b1428', 'gloss'), g, 0); e.position.set(sx * .08, .82, .262); e.scale.set(.8, 1.2, .5); const ar = A(G.sph(.06, 14, 10), gm, g, 0); ar.position.set(sx * .3, .62, .02); ar.scale.set(1.3, .7, .7); }
      const mo = A(G.sph(.026, 14, 10), P('#1b1428', 'gloss'), g, 0); mo.position.set(0, .7, .282); mo.scale.set(1.3, .8, .4); g.userData.float = true; break; }
    case 'bat': { const c0 = cl || '#3a2a4a'; const b = A(G.sph(.06, 16, 12), P(c0, 'cloth'), g, .04); b.position.y = 1.6; b.scale.y = 1.2; const hd = A(G.sph(.045, 16, 12), P(c0, 'cloth'), g, .04); hd.position.y = 1.68;
      for (const sx of [-1, 1]) { const ws = new THREE.Shape(); ws.moveTo(0, 0); ws.lineTo(.08, .05); ws.lineTo(.2, .04); ws.quadraticCurveTo(.17, -.01, .16, -.04); ws.quadraticCurveTo(.13, -.01, .11, -.04); ws.quadraticCurveTo(.08, -.01, .06, -.04); ws.quadraticCurveTo(.04, -.02, 0, -.03); ws.closePath();
        const w = A(new THREE.ShapeGeometry(ws), P(shadeC(c0, 1.1), 'cloth'), g, 0); w.material.side = THREE.DoubleSide; w.position.set(sx * .03, 1.62, 0); w.scale.x = sx; const ea = A(G.cone(.018, .04, 6), P(c0, 'cloth'), g, 0); ea.position.set(sx * .025, 1.73, 0); ea.rotation.z = -sx * .2;
        const ey = A(G.sph(.01, 8, 6), P('#ffd23f', 'glow'), g, 0); ey.position.set(sx * .018, 1.69, .038); } g.userData.float = true; break; }
    case 'garland': { const pts = []; for (let i = 0; i <= 12; i++) { const k = i / 12; pts.push(new THREE.Vector3((k - .5) * 3, 1.9 - Math.sin(k * Math.PI) * .35, 0)); } const cv = new THREE.CatmullRomCurve3(pts); A(new THREE.TubeGeometry(cv, 40, .008, 5), P('#2b2b2b', 'plastic'), g, 0);
      for (let i = 1; i < 16; i++) { const q = cv.getPoint(i / 16); const c1 = ['#ffd23f', '#ff4d6d', '#3d8fe0', '#5fbf4a', '#ff8a1f'][i % 5]; const bl = A(lathe([[0, 0], [.02, .01], [.026, .035], [.018, .055], [0, .06]], 12), P(c1, 'glow'), g, 0); bl.position.copy(q); bl.position.y -= .07; const cp = A(G.cyl(.01, .01, .015, 8), P('#555', 'metal'), g, 0); cp.position.copy(q); cp.position.y -= .012; }
      for (const sx of [-1.55, 1.55]) A(G.cyl(.03, .035, 2, 10), P(null, 'wood', barkTex()), g, .02).position.set(sx, 1, 0); g.userData.bulbs = true; break; }
    case 'tree': { if (MK3D.hq) { treeHQ(g, 0, 0, .55, 'fir', cl || '#2f8f4e'); const st = A(ext(starShape(.12, .05), .03, .01), P('#ffd23f', 'glow'), g, 0); st.position.y = 2.25 * .55 + .25; break; }
      const tr = A(G.cyl(.08, .12, .6, 10), toon('#7a4e30')); tr.position.y = .3; for (let i = 0; i < 3; i++) { const c2 = A(G.cone(.5 - i * .12, .6, 14), toon(cl || '#2f8f4e')); c2.position.y = .7 + i * .35; } break; }
    case 'snowman': { const sn = P(null, 'wax', speckT('#ffffff', '#e4ecf6', 200)); for (const [r2, y] of [[.3, .28], [.22, .72], [.16, 1.04]]) { const s = A(G.sph(r2, 32, 24), sn); s.position.y = y; s.scale.y = .92; }
      const n2 = A(lathe([[0, 0], [.03, .01], [.02, .1], [0, .15]], 12), P('#ff8a1f', 'food'), g, 0); n2.rotation.x = Math.PI / 2; n2.position.set(0, 1.04, .15);
      for (const sx of [-1, 1]) { A(G.sph(.018, 10, 8), P('#1b1b1b', 'gloss'), g, 0).position.set(sx * .055, 1.1, .14); const arm = new THREE.CatmullRomCurve3([new THREE.Vector3(sx * .2, .78, 0), new THREE.Vector3(sx * .35, .9, 0), new THREE.Vector3(sx * .45, 1.0, .02)]); A(taperTube(arm, 10, tt => .012 - tt * .007, 6), P(null, 'wood', barkTex()), g, 0); }
      for (let i = 0; i < 3; i++) A(G.sph(.02, 10, 8), P('#1b1b1b', 'gloss'), g, 0).position.set(0, .64 + i * .09, .21 - Math.abs(i - 1) * .01);
      const sc = A(G.tor(.15, .035, 10, 32), P(null, 'cloth', fabricT('#e8344e', '#ffffff')), g, .02); sc.rotation.x = Math.PI / 2; sc.position.y = .9; const hat = A(G.cyl(.11, .1, .14, 24), P('#2a2a2a', 'cloth'), g, .03); hat.position.y = 1.24; A(G.cyl(.16, .16, .015, 24), P('#2a2a2a', 'cloth'), g, .03).position.y = 1.17; break; }
    case 'fire': { for (let i = 0; i < 9; i++) { const a = i / 9 * Math.PI * 2; const st = A(new THREE.IcosahedronGeometry(.06, 1), P('#8a8680', 'wood'), g, 0); st.position.set(Math.cos(a) * .28, .03, Math.sin(a) * .28); st.scale.y = .7; }
      for (let i = 0; i < 4; i++) { const lg = A(G.cyl(.035, .04, .42, 10), P(null, 'wood', barkTex()), g, .02); lg.rotation.set(Math.PI / 2 - .5, 0, 0); lg.position.y = .1; const gq = new THREE.Group(); gq.rotation.y = i / 4 * Math.PI * 2; gq.add(lg); g.add(gq); lg.position.z = .08; }
      const fl = []; for (const [r2, h, c1, x, z] of [[.15, .45, '#ff6a00', 0, 0], [.1, .36, '#ffa514', .06, .03], [.09, .3, '#ffa514', -.06, -.02], [.06, .22, '#fff0a0', 0, .02]]) { const f = A(lathe([[0, 0], [r2, r2 * .5], [r2 * .8, h * .5], [r2 * .3, h * .8], [0, h]], 16), P(c1, 'glow'), g, 0); f.position.set(x, .08, z); fl.push(f); }
      g.userData.flames = fl; g.userData.glowY = .35; g.userData.glowS = 1.5; g.userData.glowC = '#ffb347'; g.userData.alwaysGlow = true; break; }
    case 'tent': { const c0 = cl || '#e8344e'; const ts = new THREE.Shape(); ts.moveTo(-.7, 0); ts.lineTo(.7, 0); ts.lineTo(0, 1); ts.closePath(); const tn = A(ext(ts, 1.4, .02), P(null, 'cloth', fabricT(c0, shadeC(c0, .9))), g, .02); tn.rotation.y = Math.PI / 2;
      const dr = new THREE.Shape(); dr.moveTo(-.28, 0); dr.lineTo(.28, 0); dr.lineTo(0, .6); dr.closePath(); const d = A(new THREE.ShapeGeometry(dr), P('#3a2a2a', 'cloth'), g, 0); d.position.set(.705, 0, 0); d.rotation.y = Math.PI / 2;
      const fl = A(new THREE.ShapeGeometry(dr), P(lightC(c0, .2), 'cloth'), g, 0); fl.material.side = THREE.DoubleSide; fl.position.set(.72, 0, -.05); fl.rotation.y = Math.PI / 2 + .9; fl.scale.set(.5, 1, 1);
      for (const sx of [-1, 1]) { const ln = A(new THREE.TubeGeometry(new THREE.LineCurve3(new THREE.Vector3(sx * .7, .98, 0), new THREE.Vector3(sx * 1.1, 0, 0)), 2, .004, 4), P('#e8e2d0', 'cloth'), g, 0); } break; }
    case 'castle': { const st = P(null, 'wood', stoneT()), rf = P(cl || '#e8344e', 'plastic'); A(G.box(1.2, .8, .5), st).position.y = .4;
      for (let i = 0; i < 6; i++) A(G.box(.12, .12, .52), st, g, 0).position.set(-.52 + i * .21, .86, 0);
      for (const sx of [-.66, .66]) { A(G.cyl(.2, .22, 1.25, 24), st).position.set(sx, .62, 0); const r2 = A(G.cone(.27, .5, 24), rf); r2.position.set(sx, 1.5, 0); const pl = A(G.cyl(.006, .006, .25, 6), P('#555', 'metal'), g, 0); pl.position.set(sx, 1.85, 0); const fg = A(new THREE.PlaneGeometry(.14, .08), P('#ffd23f', 'cloth'), g, 0); fg.material.side = THREE.DoubleSide; fg.position.set(sx + .07, 1.93, 0); }
      const gs2 = new THREE.Shape(); gs2.moveTo(-.16, 0); gs2.lineTo(.16, 0); gs2.lineTo(.16, .28); gs2.absarc(0, .28, .16, 0, Math.PI, false); gs2.closePath(); const gt = A(new THREE.ShapeGeometry(gs2), P('#5a3a22', 'wood'), g, 0); gt.position.set(0, 0, .252);
      for (const sx of [-.33, .33]) { const w = A(new THREE.PlaneGeometry(.08, .14), P('#2a3a5a', 'gloss'), g, 0); w.position.set(sx, .55, .252); } break; }
    case 'rainbow': { const cols = ['#e8344e', '#ff8a1f', '#ffd23f', '#5fbf4a', '#3d8fe0', '#8d5cf6']; cols.forEach((c2, i) => { const a = A(G.tor(2.2 - i * .1, .05, 8, 64, Math.PI), MK3D.hq ? new THREE.MeshBasicMaterial({ color: c2, transparent: true, opacity: .85, toneMapped: false }) : basic(c2), g, 0); a.castShadow = false; a.scale.z = .3; });
      if (MK3D.hq) for (const sx of [-1.95, 1.95]) { const cg = new THREE.Group(); cg.position.set(sx * 1.02, 0, 0); g.add(cg); cumulus(cg, rng(sx > 0 ? 3 : 4), false); cg.scale.setScalar(.17); } break; }
    default: A(G.sph(.12), P(cl || '#cccccc', 'plastic')).position.y = .12;
  }
  g.traverse(o => { if (o.isMesh && o.castShadow !== false && !(o.material && o.material.isMeshBasicMaterial)) o.castShadow = true; }); propCache[key] = g; return g;
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
function flowers(g, r, n, x0, x1, z0, z1, skip) { if (MK3D.hq) return flowersHQ(g, r, n, x0, x1, z0, z1, skip);
  // обычный режим: цветы кустиками (стебель, головка, серединка) вместо разноцветных бусин, плюс пучки травы
  const cols = ['#ff6fa8', '#ffd23f', '#ffffff', '#a974ff', '#ff8a3d']; const stemG = G.cyl(.007, .009, .13, 5), headG = G.sph(.05, 10, 6), midG = G.sph(.02, 8, 6), stemM = toon('#3f8f3a'), midM = toon('#ffd23f'), heads = cols.map(c => toon(c));
  let made = 0, guard = 0; const want = Math.round(n * .55);
  while (made < want && guard++ < want * 6) { const cx = lerp(x0, x1, r()), cz = lerp(z0, z1, r()); if (skip && skip(cx, cz)) continue; const k = 2 + ((r() * 4) | 0), ci = (r() * cols.length) | 0;
    for (let j = 0; j < k && made < want; j++) { const x = cx + (r() - .5) * .5, z = cz + (r() - .5) * .32; if (skip && skip(x, z)) continue; const f = new THREE.Group(); f.position.set(x, 0, z);
      const st = new THREE.Mesh(stemG, stemM); st.position.y = .065; f.add(st); const h = new THREE.Mesh(headG, heads[ci]); h.position.y = .14; h.scale.set(1, .38, 1); f.add(h); const m = new THREE.Mesh(midG, midM); m.position.y = .158; f.add(m); f.scale.setScalar(.8 + r() * .5); g.add(f); made++; } }
  const N = 900, tuft = new THREE.InstancedMesh(new THREE.ConeGeometry(.03, .16, 4), toon('#55a845'), N); const M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sc = new THREE.Vector3(), p = new THREE.Vector3(); let ti = 0;
  for (let i = 0; i < N; i++) { const x = lerp(x0 - 5, x1 + 5, r()), z = lerp(z0 - 5, z1 + 1, r()); if (skip && skip(x, z)) continue; e.set((r() - .5) * .5, r() * 3, (r() - .5) * .5); q.setFromEuler(e); const k = .6 + r() * .8; sc.set(k, k * (.7 + r() * .6), k); p.set(x, .055 * k, z); M.compose(p, q, sc); tuft.setMatrixAt(ti++, M); }
  tuft.count = ti; tuft.instanceMatrix.needsUpdate = true; tuft.castShadow = false; g.add(tuft); }
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
  items.forEach(([x, z], i) => { const nearRow = (Math.abs(z) < .55 || Math.abs(z + .9) < .4) && Math.abs(x) < 6; const h = (nearRow ? .028 + r() * .028 : .042 + r() * .042) * (r() < .04 ? 1.6 : 1);
    _q.setFromEuler(new THREE.Euler((r() - .5) * .35, r() * Math.PI * 2, (r() - .5) * .35)); _v.set(x, 0, z); _s.set(.009 + r() * .007, h, h); _m4.compose(_v, _q, _s); im.setMatrixAt(i, _m4);
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
  const n = Math.round(4 * Math.PI * R * R * 560), pts = [];
  for (let i = 0; i < n; i++) { const u = r() * 2 - 1, a = r() * Math.PI * 2, s2 = Math.sqrt(1 - u * u); const d = new THREE.Vector3(s2 * Math.cos(a), u, s2 * Math.sin(a)); const p = new THREE.Vector3(cx, cy, cz).addScaledVector(d, R * (.86 + r() * .16));
    const dir = d.clone().add(new THREE.Vector3((r() - .5) * .6, -.35, (r() - .5) * .6)).normalize(); pts.push([p, dir]); }
  leafCloud(t, pts, cols, .13, false); }
function treeHQ(g, x, z, s, kind, cl, snow) {
  const t = new THREE.Group(); t.position.set(x, 0, z); t.scale.setScalar(s); g.add(t); const r = rng(global.MK.hash32(x.toFixed(2) + ',' + z.toFixed(2)));
  const bark = new THREE.MeshStandardMaterial({ color: 0xffffff, map: barkTex(), roughness: .95, metalness: 0 });
  const tr = new THREE.Mesh(new THREE.CylinderGeometry(.12, .24, 1.9, 14, 4), bark); tr.position.y = .95; tr.castShadow = tr.receiveShadow = true; t.add(tr);
  for (let i = 0; i < 3; i++) { const sx = (r() < .5 ? -1 : 1); const cv = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 1.2 + i * .25, 0), new THREE.Vector3(sx * .25, 1.6 + i * .25, (r() - .5) * .3), new THREE.Vector3(sx * (.45 + r() * .2), 1.9 + i * .2, (r() - .5) * .4)]);
    const br = new THREE.Mesh(new THREE.TubeGeometry(cv, 8, .05 - i * .008, 8), bark); br.castShadow = true; t.add(br); }
  if (kind === 'fir') { const cols = snow ? ['#2f6a4c', '#3a7a58'] : [cl || '#2f6a4c', '#3d7a5a', '#2a5e44'];
    for (let i = 0; i < 4; i++) { const R = 1.15 - i * .24, H = 1.15, y = 1.25 + i * .58; const ic = new THREE.Mesh(G.cone(R * .85, H * .95, 14), matte(new THREE.Color(cols[0]).multiplyScalar(.6).getStyle())); ic.position.y = y; ic.castShadow = true; t.add(ic);
      const n = Math.round(Math.PI * R * Math.hypot(R, H) * 850), pts = [];
      for (let k = 0; k < n; k++) { const tt = Math.sqrt(r()), a = r() * Math.PI * 2, rad = R * tt; const p = new THREE.Vector3(Math.cos(a) * rad, y + H / 2 - tt * H, Math.sin(a) * rad); const dir = new THREE.Vector3(Math.cos(a), -.55 + (r() - .5) * .3, Math.sin(a)).normalize(); pts.push([p, dir]); }
      leafCloud(t, pts, cols, .18, true);
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
function cumulus(cg, r, eve) { // пушистое облако: плоское снизу, «кочки» сверху, светится изнутри — без серых пятен
  const m = new THREE.MeshStandardMaterial({ color: eve ? '#ffe2dc' : '#ffffff', roughness: 1, metalness: 0, emissive: eve ? '#f0b0a8' : '#d4e2f2', emissiveIntensity: .55, envMapIntensity: .4 });
  const w = 2.6 + r() * 1.6; for (let k = 0; k < 26; k++) { const t = r(), x = (t - .5) * w * 2, top = Math.cos((t - .5) * Math.PI); const rr = (.45 + r() * .55) * (.6 + top * .7); const y = rr * .55 + r() * top * .9;
    const b = new THREE.Mesh(G.sph(rr, 18, 14), m); b.position.set(x, y, (r() - .5) * 1.2); b.scale.y = .85; b.castShadow = false; b.receiveShadow = false; cg.add(b); }
  cg.scale.setScalar(.8 + r() * .35); }
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
    const gp = plane(120, 120, snow ? '#f2f6fc' : green); if (MK3D.hq && !snow) gp.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: groundTex(type === 'forest' && !night ? '#4d5c2f' : new THREE.Color(green).multiplyScalar(.8).getStyle()), roughness: .95 }); g.add(gp);
    const soft = (d, x, z) => d < -.1 ? false : d > .14 ? true : (global.MK.hash32(x.toFixed(3) + z.toFixed(3)) % 100) / 100 < (d + .1) / .24; // d — насколько глубоко внутри тропинки
    const skipG = (x, z) => (type === 'yard' && (soft(Math.min(.7 - Math.abs(x + 3.6), z + 6.2, 3.8 - z), x, z) || (x > -5.7 && x < -1.5 && z < -5.4))) || (type === 'forest' && soft(Math.min(z - .2, 1.6 - z), x, z)) || (type === 'playground' && Math.abs(x) < 1.3 && z > -5.3 && z < -2.7);
    for (let i = 0; i < 6; i++) { const hc = snow ? '#e8f0fa' : night ? '#24453a' : '#98d07a'; const h = new THREE.Mesh(G.sph(8 + r() * 6, 40, 20), MK3D.hq && !snow ? new THREE.MeshStandardMaterial({ color: 0xffffff, map: (() => { const t = groundTex(hc).clone(); t.needsUpdate = true; t.repeat.set(10, 5); return t; })(), roughness: .95 }) : toon(hc)); h.position.set(-40 + i * 16, -4, -35 - r() * 10); h.scale.y = .5; g.add(h); }
    if (type === 'yard') { house(g, -3.6, -7, '#f6d7a7', '#d9534f'); fence(g, -4.2, '#e8c48a', -3.6); const pth = plane(1.4, 10, '#d8c3a0'); if (MK3D.hq) pth.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: dirtTex('#d8c3a0', 1, 7), roughness: .95 }); pth.position.set(-3.6, .01, -1.2); g.add(pth); tree(g, 3.6, -6, 1.3); tree(g, 6, -9, 1.1); tree(g, -8.5, -8, 1.2); tree(g, 8.5, -5.5, .9); }
    if (type === 'forest' || type === 'winter') { const cine = MK3D.hq && type === 'forest' && !night; for (let i = 0; i < 26; i++) { const x = (r() - .5) * 30, z = -3 - r() * 16; if (Math.abs(x) < 1.5 && z > -5) continue; if (cine && (z > -12 || r() < .5)) continue; tree(g, x, z, (.9 + r() * .6) * (cine ? 1.6 : 1), snow || r() < .4 || cine ? 'fir' : 'round', snow ? '#2f6a4c' : null, snow); }
      if (!snow) { const pth = plane(40, 1.4, '#d9b77a'); if (MK3D.hq) pth.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: dirtTex(night ? '#d9b77a' : '#8f7a52', 28, 1), roughness: .95 }); pth.position.set(0, .01, .9); g.add(pth); for (let i = 0; i < 8; i++) { const mx = (r() - .5) * 14, mz = -1.5 - r() * 2; mesh(G.cyl(.04, .05, .14, 8), toon('#f2eadf'), .1, g).position.set(mx, .07, mz); const cp = mesh(new THREE.SphereGeometry(.12, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2), toon('#e8344e'), .08, g); cp.position.set(mx, .13, mz); } } }
    if (type === 'meadow') { for (let i = 0; i < 6; i++) tree(g, (r() - .5) * 34, -10 - r() * 10, 1 + r() * .4); fence(g, -6, '#e8c48a'); }
    if (type === 'playground') { const sw = new THREE.Group(); sw.position.set(-3.5, 0, -2.5); g.add(sw); for (const s of [-1, 1]) { const p = mesh(G.cyl(.06, .06, 2.4, 8), toon('#e8344e'), .05, sw); p.position.set(s * 1.2, 1.2, 0); } mesh(G.cyl(.06, .06, 2.5, 8), toon('#e8344e'), .05, sw).position.y = 2.4; sw.children[2].rotation.z = Math.PI / 2;
      for (const s of [-.5, .5]) { mesh(G.box(.5, .06, .3), toon('#ffd23f'), .05, sw).position.set(s, .6, 0); }
      const sl = new THREE.Group(); sl.position.set(3.5, 0, -2.8); g.add(sl); mesh(G.box(.8, .1, .8), toon('#3d8fe0'), .04, sl).position.y = 1.6; for (const s of [-1, 1]) mesh(G.cyl(.05, .05, 1.6, 8), toon('#2f6fb8'), .05, sl).position.set(s * .35, .8, -.35); const ramp = mesh(G.box(.7, .06, 2.2), toon('#ff8a1f'), .03, sl); ramp.position.set(0, .85, 1.3); ramp.rotation.x = .75;
      const sb = mesh(G.box(2.4, .2, 2.4), toon('#f1d38a'), .03, g); if (MK3D.hq) sb.material = new THREE.MeshStandardMaterial({ color: 0xffffff, map: dirtTex('#f1d38a', 1, 1), roughness: .95 }); sb.position.set(0, .1, -4); tree(g, 7, -7, 1.2); tree(g, -7.5, -7, 1.1); }
    if (snow) { const sm = new THREE.Group(); sm.position.set(3.8, 0, -2); g.add(sm); [[.6, .55], [.42, 1.4], [.3, 2.0]].forEach(([rr, y]) => mesh(G.sph(rr, 24, 18), toon('#ffffff'), .03, sm).position.y = y); const nose = mesh(G.cone(.06, .3, 10), toon('#ff8a1f'), .06, sm); nose.rotation.x = Math.PI / 2; nose.position.set(0, 2.0, .35); }
    if (!snow) flowers(g, r, type === 'meadow' ? 180 : 70, -9, 9, -3.5, 3, skipG);
    if (MK3D.hq && !snow) { const cine = type === 'forest' && !night; grassField(g, r, cine ? (time === 'evening' ? '#5f7a34' : '#4f7d33') : green, skipG); if (!cine) rocksHQ(g, r, 10); }
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
      const fr = mesh(G.box(1.1, 2.4, .9), toon('#fafafa'), .02, g); fr.position.set(5.3, 1.2, -3); const tb = new THREE.Group(); tb.position.set(4, 0, -1.4); g.add(tb); tb.userData.tag = 'table'; cnt.userData.tag = 'counter'; mesh(G.cyl(.9, .9, .08, 28), toon('#c88a55'), .03, tb).position.y = .78; mesh(G.cyl(.08, .12, .78, 10), toon('#8a5a3a'), .05, tb).position.y = .39; }
    else { const sofa = new THREE.Group(); sofa.position.set(5, 0, -2.8); g.add(sofa); sofa.userData.tag = 'sofa'; mesh(G.box(3, .5, 1), toon('#5f9e8f'), .03, sofa).position.y = .35; mesh(G.box(3, .8, .3), toon('#5f9e8f'), .03, sofa).position.set(0, .8, -.4); for (const s of [-1, 1]) mesh(G.box(.3, .6, 1), toon('#5f9e8f'), .03, sofa).position.set(s * 1.5, .5, 0);
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
  if (!['space', 'room', 'kitchen'].includes(type) && !night) { g.userData.clouds = []; for (let i = 0; i < 6; i++) { const cg = new THREE.Group(); if (MK3D.hq) cumulus(cg, r, time === 'evening'); else for (let k = 0; k < 5; k++) { const c = new THREE.Mesh(G.sph(.9 + r() * .7, 16, 12), toon(time === 'evening' ? '#ffd6d6' : '#ffffff')); c.position.set(k * 1.1 - 2.2, (r() - .5) * .6, 0); cg.add(c); } cg.position.set(-30 + i * 12, 9 + r() * 4, -30 - r() * 8); g.add(cg); g.userData.clouds.push(cg); } }
  // погода
  const weather = spec.weather || (type === 'winter' ? 'snow' : 'none');
  if (weather === 'rain' || weather === 'snow') { const N = weather === 'rain' ? 900 : 700, pts = new Float32Array(N * 3), seeds = []; for (let i = 0; i < N; i++) seeds.push([(r() - .5) * 26, r() * 12, -8 + r() * 14, .6 + r() * .4]); const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pts, 3));
    const pm = new THREE.Points(pg, new THREE.PointsMaterial({ color: weather === 'rain' ? 0xbcd4ff : 0xffffff, size: weather === 'rain' ? .06 : .09, transparent: true, opacity: .9 })); g.add(pm); g.userData.weather = { pm, seeds, rain: weather === 'rain' }; }
  g.userData.type = type; g.userData.time = time; g.userData.weather0 = weather;
  if (MK3D.hq) decorateHQ(g, spec, rng(global.MK.hash32('deco' + (spec.seed || 1) + type)));
  g.traverse(o => { if (o.isMesh && o.castShadow === false && !o.material.isMeshBasicMaterial) { o.castShadow = true; } });
  return g;
}

// ---------- места «как в кино»: текстуры и мелочи, из которых складывается настоящая декорация ----------
function brickT(c) { return ctex('brick' + c, 256, 256, (g) => { g.fillStyle = shadeC(c, .75); g.fillRect(0, 0, 256, 256); const r = rng(9); for (let y = 0; y < 256; y += 32) for (let x = -64 + ((y / 32) % 2) * 32; x < 256; x += 64) { g.fillStyle = shadeC(c, .9 + r() * .2); g.fillRect(x + 3, y + 3, 58, 26); g.fillStyle = 'rgba(255,255,255,.06)'; g.fillRect(x + 3, y + 3, 58, 4); } }, [2, 3]); }
function plasterT(c) { return ctex('pl' + c, 256, 256, (g) => { g.fillStyle = c; g.fillRect(0, 0, 256, 256); const r = rng(4); for (let i = 0; i < 2500; i++) { g.fillStyle = r() < .5 ? 'rgba(0,0,0,.035)' : 'rgba(255,255,255,.05)'; g.fillRect(r() * 256, r() * 256, 2, 2); } g.fillStyle = 'rgba(0,0,0,.08)'; g.fillRect(0, 248, 256, 8); }, [2, 2]); }
function asphaltT() { return ctex('asph', 256, 256, (g) => { g.fillStyle = '#4a4a52'; g.fillRect(0, 0, 256, 256); const r = rng(5); for (let i = 0; i < 4000; i++) { g.fillStyle = r() < .5 ? 'rgba(0,0,0,.18)' : 'rgba(255,255,255,.1)'; g.fillRect(r() * 256, r() * 256, 1 + r() * 2, 1 + r() * 2); } }, [30, 2]); }
function tilesT(c, n) { return ctex('tl' + c + n, 256, 256, (g) => { g.fillStyle = shadeC(c, .78); g.fillRect(0, 0, 256, 256); const s = 256 / n, r = rng(7); for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { g.fillStyle = shadeC(c, .94 + r() * .1); g.fillRect(x * s + 2, y * s + 2, s - 4, s - 4); } }); }
function sandT() { return ctex('sand', 512, 512, (g) => { g.fillStyle = '#ecd08e'; g.fillRect(0, 0, 512, 512); const r = rng(8); for (let i = 0; i < 14000; i++) { g.fillStyle = r() < .5 ? 'rgba(150,110,50,.18)' : 'rgba(255,250,230,.22)'; g.fillRect(r() * 512, r() * 512, 1.5, 1.5); }
  g.strokeStyle = 'rgba(160,120,60,.15)'; g.lineWidth = 3; for (let y = 10; y < 512; y += 22) { g.beginPath(); for (let x = 0; x <= 512; x += 16) g.lineTo(x, y + Math.sin(x * .03 + y) * 5); g.stroke(); } }, [24, 12]); }
function snowT() { return ctex('snow', 256, 256, (g) => { g.fillStyle = '#f4f8fd'; g.fillRect(0, 0, 256, 256); const r = rng(9); for (let i = 0; i < 900; i++) { g.fillStyle = r() < .6 ? 'rgba(170,190,220,.18)' : 'rgba(255,255,255,.9)'; g.beginPath(); g.arc(r() * 256, r() * 256, .6 + r() * 2.5, 0, 7); g.fill(); } }, [30, 30]); }
function moonGroundT() { return ctex('mground', 512, 512, (g) => { g.fillStyle = '#a3a3ae'; g.fillRect(0, 0, 512, 512); const r = rng(10); for (let i = 0; i < 60; i++) { const x = r() * 512, y = r() * 512, rr = 6 + r() * 30; g.fillStyle = 'rgba(70,70,85,.22)'; g.beginPath(); g.arc(x, y, rr, 0, 7); g.fill(); g.strokeStyle = 'rgba(230,230,240,.3)'; g.lineWidth = 2; g.beginPath(); g.arc(x - 1, y - 1, rr, Math.PI * 1.1, Math.PI * 1.9); g.stroke(); }
  for (let i = 0; i < 5000; i++) { g.fillStyle = r() < .5 ? 'rgba(0,0,0,.12)' : 'rgba(255,255,255,.12)'; g.fillRect(r() * 512, r() * 512, 1.5, 1.5); } }, [10, 10]); }
function wallpaperT(c) { return ctex('wp' + c, 256, 256, (g) => { g.fillStyle = c; g.fillRect(0, 0, 256, 256); g.fillStyle = shadeC(c, .93); for (let x = 0; x < 256; x += 32) g.fillRect(x, 0, 12, 256); g.fillStyle = lightC(c, .4); for (let y = 16; y < 256; y += 64) for (let x = 22; x < 256; x += 64) { g.beginPath(); for (let k = 0; k < 5; k++) { const a = k / 5 * Math.PI * 2; g.ellipse(x + Math.cos(a) * 6, y + Math.sin(a) * 6, 4, 4, 0, 0, 7); } g.fill(); } }, [6, 2]); }
function parquetT(c) { return ctex('pq' + c, 512, 512, (g) => { const r = rng(12); for (let y = 0; y < 512; y += 32) { let x = -((y / 32) % 3) * 70; while (x < 512) { const w = 120 + r() * 80; g.fillStyle = shadeC(c, .82 + r() * .3); g.fillRect(x, y, w, 32); g.strokeStyle = 'rgba(60,30,10,.25)'; g.lineWidth = 2; g.strokeRect(x, y, w, 32);
    g.strokeStyle = 'rgba(80,40,10,.12)'; g.lineWidth = 1; for (let k = 0; k < 4; k++) { g.beginPath(); g.moveTo(x, y + 6 + k * 7 + r() * 3); g.bezierCurveTo(x + w * .3, y + 4 + k * 7, x + w * .6, y + 9 + k * 7, x + w, y + 6 + k * 7); g.stroke(); } x += w; } } }, [4, 4]); }
function rugT(a, b) { return ctex('rug' + a + b, 256, 256, (g) => { g.fillStyle = a; g.fillRect(0, 0, 256, 256); g.strokeStyle = b; for (let k = 0; k < 6; k++) { g.lineWidth = 8 - k; g.beginPath(); g.arc(128, 128, 120 - k * 20, 0, 7); g.stroke(); } g.fillStyle = lightC(a, .4); for (let k = 0; k < 12; k++) { const t = k / 12 * Math.PI * 2; g.beginPath(); g.arc(128 + Math.cos(t) * 70, 128 + Math.sin(t) * 70, 8, 0, 7); g.fill(); } }); }
function stdM(c, map, rough) { return new THREE.MeshStandardMaterial({ color: map ? 0xffffff : c, map: map || null, roughness: rough == null ? .85 : rough }); }
function placeProp(g, type, x, y, z, sc, ry, extra) { const o = Object.assign({ id: 'deco' + type + x + z, type }, extra || {}); const m = propMesh(o); delete propCache[o.id + o.type + (o.color || '')]; m.position.set(x, y, z); m.scale.setScalar(sc || 1); m.rotation.y = ry || 0; m.visible = true; g.add(m); return m; }
// ================= лес «как в кино»: высокие стволы в дымке, полог листвы с пятнами солнца, мшистые камни, бревно, папоротники =================
const MOSS_GLSL = `varying vec3 vMW; varying vec3 vMN; uniform float uMossTop, uMossBase, uBaseH; uniform vec3 uMossCol;
float mh3(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float mnoise(vec3 p){ vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(mh3(i), mh3(i + vec3(1,0,0)), f.x), mix(mh3(i + vec3(0,1,0)), mh3(i + vec3(1,1,0)), f.x), f.y), mix(mix(mh3(i + vec3(0,0,1)), mh3(i + vec3(1,0,1)), f.x), mix(mh3(i + vec3(0,1,1)), mh3(i + vec3(1,1,1)), f.x), f.y), f.z); }
`;
function mossy(mat, top, base, baseH) { // мох сверху и у основания (по мировой нормали и высоте), пятнами
  const u = { uMossTop: { value: top }, uMossBase: { value: base }, uBaseH: { value: baseH || 1.2 }, uMossCol: { value: new THREE.Color('#5f8f3a') } };
  mat.onBeforeCompile = (sh) => { Object.assign(sh.uniforms, u);
    sh.vertexShader = 'varying vec3 vMW; varying vec3 vMN;\n' + sh.vertexShader.replace('#include <project_vertex>', `#include <project_vertex>
  { vec4 mw = vec4(transformed, 1.0); vec3 mn = objectNormal;
    #ifdef USE_INSTANCING
      mw = instanceMatrix * mw; mn = mat3(instanceMatrix) * mn;
    #endif
    vMW = (modelMatrix * mw).xyz; vMN = normalize(mat3(modelMatrix) * mn); }`);
    sh.fragmentShader = MOSS_GLSL + sh.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
  { float n = mnoise(vMW * 3.1) * .65 + mnoise(vMW * 9.3) * .35;
    float m = smoothstep(.25, .8, vMN.y + (n - .5) * .7) * uMossTop + smoothstep(uBaseH, 0.0, vMW.y) * uMossBase * (.5 + n);
    diffuseColor.rgb = mix(diffuseColor.rgb, uMossCol * (.7 + .6 * n), clamp(m, 0.0, 1.0)); }`); };
  mat.customProgramCacheKey = () => 'mossy'; return mat; }
function canopyTex() { if (envC.canopy) return envC.canopy; const r = rng(77); const t = canvasTex(512, 512, (g) => { g.fillStyle = '#ffffff'; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 95; i++) { const x = r() * 512, y = r() * 512, R = 8 + r() * 34; const gr = g.createRadialGradient(x, y, 0, x, y, R); gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(.7, 'rgba(0,0,0,.9)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.beginPath(); g.ellipse(x, y, R, R * (.6 + r() * .6), r() * 3, 0, 7); g.fill(); } });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 3); t.colorSpace = THREE.NoColorSpace; return (envC.canopy = t); }
function mistTex(time) { const k = 'mist' + time; if (texCache[k]) return texCache[k]; const s = time === 'evening' ? ['#f3dcc0', '#cdb79c'] : ['#dcebe3', '#a9cbbd'];
  const t = canvasTex(4, 256, (g) => { const gr = g.createLinearGradient(0, 0, 0, 256); gr.addColorStop(0, s[0]); gr.addColorStop(1, s[1]); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); }); texCache[k] = t; return t; }
function noise3(x, y, z) { const h = (a, b, c) => { const v = Math.sin(a * 127.1 + b * 311.7 + c * 74.7) * 43758.5453; return v - Math.floor(v); }; const ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z), fx = x - ix, fy = y - iy, fz = z - iz, sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy), sz = fz * fz * (3 - 2 * fz);
  const L = (a, b, t) => a + (b - a) * t; return L(L(L(h(ix, iy, iz), h(ix + 1, iy, iz), sx), L(h(ix, iy + 1, iz), h(ix + 1, iy + 1, iz), sx), sy), L(L(h(ix, iy, iz + 1), h(ix + 1, iy, iz + 1), sx), L(h(ix, iy + 1, iz + 1), h(ix + 1, iy + 1, iz + 1), sx), sy), sz); }
function frondGeo() { if (envC.frond) return envC.frond; const P = [], C = [], I = []; const N = 16, base = new THREE.Color('#2f5e22'), tip = new THREE.Color('#79b047');
  const spine = t => new THREE.Vector3(0, Math.sin(t * Math.PI * .62) * .5, t * .95);
  for (let i = 0; i < N; i++) { const t0 = i / N, t1 = (i + 1) / N, a = spine(t0), b = spine(t1), len = .2 * (1 - t0 * .78) * (i < 2 ? .5 : 1);
    for (const sd of [-1, 1]) { const o = P.length / 3, tipP = a.clone().lerp(b, .5).add(new THREE.Vector3(sd * len, -len * .25, len * .15));
      P.push(a.x, a.y, a.z, b.x, b.y, b.z, tipP.x, tipP.y, tipP.z); for (const tt of [t0, t1, (t0 + t1) / 2]) { const c = base.clone().lerp(tip, tt); C.push(c.r, c.g, c.b); } I.push(o, o + 1, o + 2); } }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(C, 3)); g.setIndex(I); g.computeVertexNormals(); return (envC.frond = g); }
function forestHQ(g, spec, r) {
  const eve = (spec.time || 'day') === 'evening';
  // стволы: высокие, уходят за кадр, корни расширяются у земли, мох у основания
  const barkM = mossy(new THREE.MeshStandardMaterial({ color: 0xffffff, map: barkTex(), roughness: .95, metalness: 0 }), .45, .85, 1.5);
  const trunk = (x, z, R, H) => { const geo = new THREE.CylinderGeometry(R * .72, R, H, 20, 14); geo.translate(0, H / 2, 0); const p = geo.attributes.position, uv = geo.attributes.uv;
    for (let i = 0; i < p.count; i++) { const y = p.getY(i), a = Math.atan2(p.getZ(i), p.getX(i)), k = 1 + .6 * Math.exp(-y / (R * 1.2)) * (.6 + .4 * Math.sin(a * 5)) + .03 * Math.sin(a * 9 + y * 1.7); p.setX(i, p.getX(i) * k); p.setZ(i, p.getZ(i) * k); uv.setXY(i, uv.getX(i) * Math.max(1, Math.round(R * 6)), uv.getY(i) * H / 2.2); }
    geo.computeVertexNormals(); const m = new THREE.Mesh(geo, barkM); m.position.set(x, 0, z); m.rotation.y = r() * 6; m.castShadow = true; m.receiveShadow = true; g.add(m); return m; };
  for (let i = 0; i < 48; i++) { const z = -3 - Math.pow(r(), .85) * 32, x = (r() - .5) * (14 + (-z) * 1.5); if (Math.abs(x) < 2.4 && z > -10) continue; trunk(x, z, .2 + r() * .32 + (-z) * .005, 15 + r() * 8); }
  trunk(-4.4, -2.6, .5, 20); trunk(4.6, -3.2, .44, 20); trunk(-7.2, .6, .62, 20); trunk(7.8, 1.2, .58, 20); // по краям кадра — как кулисы
  // мшистые валуны
  const rockM = mossy(new THREE.MeshStandardMaterial({ color: '#86837a', roughness: .92 }), 1.0, .3, .5);
  const boulder = (x, z, sx, sy, sz, seed) => { const geo = new THREE.SphereGeometry(1, 72, 48), p = geo.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); const n = noise3(v.x * 1.6 + seed, v.y * 1.6, v.z * 1.6) * .32 + noise3(v.x * 4 + seed, v.y * 4, v.z * 4) * .1; v.multiplyScalar(.82 + n); if (v.y < -.25) v.y = -.25 + (v.y + .25) * .3; p.setXYZ(i, v.x, v.y, v.z); }
    geo.computeVertexNormals(); const m = new THREE.Mesh(geo, rockM); m.scale.set(sx, sy, sz); m.position.set(x, sy * .22, z); m.rotation.y = seed; m.castShadow = true; m.receiveShadow = true; g.add(m); };
  boulder(3.6, -4.2, 1.4, 1.25, 1.1, 1.3); boulder(-5.2, -6.8, 1.0, .75, .9, 4.1); boulder(6.5, -10, 1.3, 1, 1.2, 2.2); boulder(-2.6, -11, .7, .5, .7, 5.5);
  // поваленное бревно во мху
  { const geo = new THREE.CylinderGeometry(.34, .4, 5.2, 18, 8); const m = new THREE.Mesh(geo, mossy(new THREE.MeshStandardMaterial({ color: 0xffffff, map: barkTex(), roughness: .95 }), .9, 0, .1)); m.rotation.set(0, .35, Math.PI / 2); m.position.set(-3.8, .32, -4.6); m.castShadow = true; m.receiveShadow = true; g.add(m); }
  // папоротники кустами: у стволов и камней, не там, где стоят герои
  { const spots = []; for (let i = 0; i < 46; i++) { const z = -1.6 - r() * 12, x = (r() - .5) * 18; if (Math.abs(x) < 2.6 && z > -4) continue; if (z > .2 && z < 1.6) continue; spots.push([x, z]); } spots.push([2.6, -3.2], [4.8, -4.6], [-4.6, -3.4], [-2.8, -5.4], [5.5, -2.4]);
    const fm = new THREE.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, side: THREE.DoubleSide, roughness: .7, emissive: new THREE.Color('#1c3a10'), emissiveIntensity: .25 });
    const per = 9, im = new THREE.InstancedMesh(frondGeo(), wind(fm, .18, 'blade'), spots.length * per); im.castShadow = true; im.receiveShadow = true; let k = 0;
    for (const [x, z] of spots) { const sc = .7 + r() * .7; for (let j = 0; j < per; j++) { _q.setFromEuler(new THREE.Euler(-.15 + r() * .25, j / per * Math.PI * 2 + r() * .4, 0, 'YXZ')); _v.set(x, 0, z); _s.setScalar(sc * (.8 + r() * .4)); _m4.compose(_v, _q, _s); im.setMatrixAt(k++, _m4); } }
    im.instanceMatrix.needsUpdate = true; g.add(im); }
  // полог листвы над кадром: его не видно, но он отбрасывает на землю и героев пятна солнца
  { const ceil = new THREE.Mesh(new THREE.PlaneGeometry(90, 70), new THREE.MeshStandardMaterial({ color: eve ? '#3a4a24' : '#2c4a26', alphaMap: canopyTex(), alphaTest: .5, side: THREE.DoubleSide, roughness: 1 })); ceil.rotation.x = -Math.PI / 2; ceil.position.set(0, 7.6, -22); ceil.userData.keep = true; g.add(ceil); }
  { const can = new THREE.Mesh(new THREE.PlaneGeometry(46, 46), new THREE.MeshBasicMaterial({ alphaMap: canopyTex(), alphaTest: .5, colorWrite: false, depthWrite: false, side: THREE.DoubleSide })); can.rotation.x = -Math.PI / 2; can.position.set(0, 6.4, -4); can.castShadow = true; can.receiveShadow = false; can.userData.keep = true; g.add(can); }
}
function decorateHQ(g, spec, r) {
  const type = spec.type || 'meadow', time = spec.time || 'day', night = time === 'night';
  if (type === 'forest' && !night) forestHQ(g, spec, r);
  const swapMat = (fn) => g.traverse(o => { if (o.isMesh && o.material && !o.userData.keep) { const nm = fn(o); if (nm) o.material = nm; } });
  if (type === 'street') {
    const PAL = ['#e86a5f', '#f2c94c', '#7fc4a4', '#8d7ad9', '#f29e4c', '#5fa8e8']; let bi = 0;
    swapMat(o => { const geo = o.geometry.parameters || {};
      if (o.geometry.type === 'PlaneGeometry' && geo.width === 120 && geo.height === 5) return stdM(null, asphaltT(), .9);
      if (o.geometry.type === 'PlaneGeometry' && geo.width === 120) return stdM(null, tilesT('#c9c4bb', 4), .9);
      if (o.geometry.type === 'BoxGeometry' && geo.height > 3 && geo.depth === 3) { const k = bi++; return stdM(null, k % 3 === 1 ? brickT('#c8644a') : plasterT(PAL[(k * 2 + 1) % PAL.length]), .9); }
      return null; });
    g.children.filter(b => b.isGroup && b.position.z === -5.5).forEach((b, i) => { const box = b.children[0]; if (!box) return; const w = box.geometry.parameters.width, h = box.geometry.parameters.height;
      if (i % 2 === 0) { const aw = new THREE.Mesh(new THREE.BoxGeometry(1.3, .04, .6), stdM(null, stripesT(['#e8344e', '#ffffff'], true), .8)); aw.position.set(0, 1.62, 1.75); aw.rotation.x = .45; aw.castShadow = true; b.add(aw);
        const val = new THREE.Mesh(new THREE.BoxGeometry(1.3, .12, .02), stdM(null, stripesT(['#e8344e', '#ffffff'], true), .8)); val.position.set(0, 1.46, 2.02); b.add(val); }
      for (let yy = 1.4; yy < h - .6; yy += 1.2) for (let xx = -w / 2 + .6; xx < w / 2 - .4; xx += .9) { const sill = new THREE.Mesh(new THREE.BoxGeometry(.62, .06, .14), stdM('#f4f1ea')); sill.position.set(xx, yy - .4, 1.58); sill.castShadow = true; b.add(sill);
        if (r() < .25 && yy < 3) { const bx = new THREE.Mesh(new THREE.BoxGeometry(.56, .14, .16), stdM('#8a5a3a')); bx.position.set(xx, yy - .3, 1.62); b.add(bx); for (let k = 0; k < 4; k++) { const f = new THREE.Mesh(G.sph(.05, 8, 6), stdM(['#ff4d6d', '#ffd23f', '#ff8fb1', '#ffffff'][k], null, .6)); f.position.set(xx - .2 + k * .13, yy - .18, 1.64); b.add(f); } } } });
    for (const x of [-7, 2, 9]) { const t = treeHQ(g, x, -3.4, .65); }
    placeProp(g, 'car', -6.2, 0, -3.3, 4.2, 0, { color: '#3d8fe0' }); placeProp(g, 'car', 7.4, 0, -3.3, 4.2, Math.PI, { color: '#ffd23f' });
    const bench = new THREE.Group(); bench.position.set(4.5, 0, -3.2); g.add(bench); for (let k = 0; k < 3; k++) { const sl = new THREE.Mesh(new THREE.BoxGeometry(1.6, .05, .12), stdM(null, grainTex('#a8673a'))); sl.position.set(0, .45, -.15 + k * .14); sl.castShadow = true; bench.add(sl); } for (const x of [-.7, .7]) { const lg = new THREE.Mesh(new THREE.BoxGeometry(.06, .45, .45), stdM('#3a3f4a', null, .4)); lg.position.set(x, .22, 0); bench.add(lg); }
    const hy = new THREE.Group(); hy.position.set(-1.5, 0, -3.1); g.add(hy); const hb = new THREE.Mesh(G.cyl(.09, .1, .45, 14), stdM('#e8344e', null, .4)); hb.position.y = .22; hy.add(hb); const ht = new THREE.Mesh(G.sph(.1, 14, 8), stdM('#e8344e', null, .4)); ht.position.y = .45; hy.add(ht);
    const curb = new THREE.Mesh(new THREE.BoxGeometry(120, .12, .25), stdM('#b8b2a8')); curb.position.set(0, .06, 2.62); curb.receiveShadow = true; g.add(curb); }
  if (type === 'beach') {
    swapMat(o => { const geo = o.geometry.parameters || {}; if (o.geometry.type === 'PlaneGeometry' && geo.width === 120) return stdM(null, sandT(), .95); return null; });
    if (g.userData.sea) { const sea = g.userData.sea; sea.geometry = new THREE.PlaneGeometry(200, 80, 120, 40); sea.position.y = .25; sea.material = new THREE.MeshPhysicalMaterial({ color: night ? 0x123060 : 0x1278c0, roughness: .55, clearcoat: 0, envMapIntensity: .2, fog: false, transparent: true, opacity: .96 });
      sea.material.onBeforeCompile = sh => { sh.uniforms.uWind = windU; sh.vertexShader = 'uniform float uWind;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n transformed.z += sin(position.x * .35 + uWind * 1.3) * .04 + sin(position.y * .5 + uWind * 1.7) * .03;');
        sh.fragmentShader = sh.fragmentShader.replace('#include <dithering_fragment>', '#include <dithering_fragment>\n'); }; sea.material.customProgramCacheKey = () => 'sea';
      const foam = new THREE.Mesh(new THREE.PlaneGeometry(200, .5), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: .7 })); foam.rotation.x = -Math.PI / 2; foam.position.set(0, .28, -4.1); g.add(foam); g.userData.foam = foam; }
    const palm = g.children.find(o => o.isGroup && o.position.x === 5.5); if (palm) { palm.children.filter(c => c.geometry && c.geometry.type === 'SphereGeometry').forEach(c => c.visible = false); const pts = [];
      for (let k = 0; k < 7; k++) { const a = k / 7 * Math.PI * 2, cv = new THREE.QuadraticBezierCurve3(new THREE.Vector3(.5, 3.9, 0), new THREE.Vector3(.5 + Math.cos(a) * 1, 4.3, Math.sin(a) * 1), new THREE.Vector3(.5 + Math.cos(a) * 1.9, 3.3, Math.sin(a) * 1.9));
        for (let q = 0; q < 34; q++) { const t = q / 34, p = cv.getPoint(t), tg = cv.getTangent(t), sd = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a)); for (const s2 of [-1, 1]) pts.push([p.clone(), sd.clone().multiplyScalar(s2).add(tg.clone().multiplyScalar(.35)).add(new THREE.Vector3(0, -.45, 0)).normalize()]); } }
      leafCloud(palm, pts, ['#3f9a3a', '#4fae45', '#358a32'], .42, true); for (let k = 0; k < 3; k++) { const cn = new THREE.Mesh(G.sph(.13, 14, 10), stdM('#6b4a2a', null, .6)); cn.position.set(.5 + Math.cos(k * 2) * .18, 3.75, Math.sin(k * 2) * .18); palm.add(cn); } }
    placeProp(g, 'bucket', -2.4, 0, -.9, 1.3, .4, { color: '#ff8a3d' }); placeProp(g, 'shovel', -2.0, 0, -.7, 1.3, -.6, { color: '#3d8fe0' }); placeProp(g, 'ball', 2.8, 0, -1.4, 1.6, 0);
    const sc = placeProp(g, 'castle', -6, 0, -1.6, .55, .3, { color: '#e8c88a' }); sc.traverse(o => { if (o.isMesh && o.material && o.material.map) o.material = stdM('#e2c584', sandT(), .95); });
    const tw = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 2), stdM(null, stripesT(['#3d8fe0', '#ffffff', '#ffd23f', '#ffffff'], true), .9)); tw.rotation.set(-Math.PI / 2, 0, .3); tw.position.set(-4.3, .015, 1.2); tw.receiveShadow = true; g.add(tw);
    for (let k = 0; k < 3; k++) { const st = placeProp(g, 'star', -1 + k * 3.7, 0, 1.5 + k * .3, .5, k); st.rotation.x = -Math.PI / 2; st.position.y = .02; st.traverse(o => { if (o.isMesh) o.material = stdM('#ff8a3d', null, .6); }); } }
  if (type === 'room' || type === 'kitchen') {
    const kit = type === 'kitchen';
    swapMat(o => { const geo = o.geometry.parameters || {}; if (o.geometry.type === 'PlaneGeometry' && geo.width === 30 && geo.height === 20) return stdM(null, parquetT(kit ? '#d8c4a0' : '#b8784a'), .7);
      if (o.geometry.type === 'PlaneGeometry' && geo.height === 6) return stdM(null, kit ? tilesT('#f3efe6', 8) : wallpaperT((spec.opts && spec.opts.wall) || '#f2dcb8'), .9); return null; });
    if (!kit) { furnitureHQ(g, false); const lamp = new THREE.Group(); lamp.position.set(6.8, 0, -2.6); g.add(lamp); const pole = new THREE.Mesh(G.cyl(.025, .025, 1.7, 10), stdM('#3a3a3a', null, .3)); pole.position.y = .85; lamp.add(pole); const base = new THREE.Mesh(G.cyl(.22, .25, .05, 20), stdM('#3a3a3a', null, .3)); lamp.add(base);
        const shade = new THREE.Mesh(new THREE.CylinderGeometry(.18, .32, .36, 24, 1, true), new THREE.MeshStandardMaterial({ color: '#fff0d0', emissive: '#ffd890', emissiveIntensity: night || time === 'evening' ? 1.2 : .25, side: THREE.DoubleSide })); shade.position.y = 1.8; lamp.add(shade);
        if (night || time === 'evening') { const pl = new THREE.PointLight(0xffd8a0, 4, 7, 1.5); pl.position.y = 1.7; lamp.add(pl); }
      for (const [x, y, c] of [[-1.8, 2.6, '#ff8a3d'], [-.6, 2.3, '#3d8fe0'], [4.6, 2.7, '#5fbf4a']]) { const fr = new THREE.Mesh(new THREE.BoxGeometry(.7, .55, .05), stdM('#8a5a3a', null, .5)); fr.position.set(x, y, -3.55); g.add(fr); const pic = new THREE.Mesh(new THREE.PlaneGeometry(.58, .43), stdM(null, ctex('pic' + c, 128, 96, (q) => { q.fillStyle = '#cfeaff'; q.fillRect(0, 0, 128, 96); q.fillStyle = '#7cc06a'; q.beginPath(); q.ellipse(64, 96, 90, 34, 0, 0, 7); q.fill(); q.fillStyle = c; q.beginPath(); q.arc(96, 26, 13, 0, 7); q.fill(); q.fillStyle = '#3f8a3e'; q.beginPath(); q.arc(36, 56, 16, 0, 7); q.fill(); }))); pic.position.set(x, y, -3.52); g.add(pic); }
      placeProp(g, 'teddy', 5.6, .55, -2.6, 1.3, -.3); placeProp(g, 'car', -2.5, 0, 1.6, 1.4, .8, { color: '#e8344e' }); placeProp(g, 'ball', 2.2, 0, 1.9, 1.1, 0); placeProp(g, 'book', -3.6, 0, 2.2, 1.4, .5, { color: '#ffd23f' });
      g.traverse(o => { if (o.isMesh && o.geometry.type === 'CylinderGeometry' && (o.geometry.parameters.radiusTop === 2.2)) o.material = stdM(null, rugT('#4e7fc9', '#ffd23f'), .95); }); }
    else { furnitureHQ(g, true); for (const [x, z] of [[2.8, -1.4], [5.2, -1.4]]) { if (global.MKSculpt) { const w = '#c88a55', pr = [rb(0, .48, 0, .25, .035, .25, .02, w), rb(0, .78, .22, .25, .27, .03, .025, w, .02)]; for (const [lx, lz] of [[-.2, -.2], [.2, -.2], [-.2, .2], [.2, .2]]) pr.push(cy(lx, .23, lz, .022, .028, .46, .01, w, .02)); const m = sculptStatic(pr, 56, .3); if (m) { m.position.set(x, 0, z + .9); g.add(m); } continue; } const ch = new THREE.Group(); ch.position.set(x, 0, z + .9); g.add(ch); const seat = new THREE.Mesh(new THREE.BoxGeometry(.5, .06, .5), stdM(null, grainTex('#c88a55'))); seat.position.y = .48; ch.add(seat); const bk = new THREE.Mesh(new THREE.BoxGeometry(.5, .5, .06), stdM(null, grainTex('#c88a55'))); bk.position.set(0, .75, .22); ch.add(bk); for (const [lx, lz] of [[-.2, -.2], [.2, -.2], [-.2, .2], [.2, .2]]) { const lg = new THREE.Mesh(G.cyl(.025, .025, .48, 8), stdM('#8a5a3a')); lg.position.set(lx, .24, lz); ch.add(lg); } ch.traverse(o => { if (o.isMesh) o.castShadow = true; }); }
      const cloth = new THREE.Mesh(G.cyl(.95, .98, .06, 32), stdM(null, plaidT('#e8344e'), .9)); cloth.position.set(4, .8, -1.4); g.add(cloth); placeProp(g, 'basket', 4, .83, -1.4, 1.1, 0); placeProp(g, 'cup', 4.5, .83, -1.1, 1, .5); placeProp(g, 'pie', 3.4, .83, -1.2, .8, 0);
      for (let k = 0; k < 5; k++) { const hd = new THREE.Mesh(G.box(.2, .03, .03), stdM('#c8c8c8', null, .2)); hd.material.metalness = .8; hd.position.set(-5.8 + k * 1, .75, -2.63); g.add(hd); }
      const stove = new THREE.Group(); stove.position.set(-1.2, .99, -3.1); g.add(stove); for (const [x, z] of [[-.25, -.15], [.25, -.15], [-.25, .2], [.25, .2]]) { const bn = new THREE.Mesh(G.cyl(.14, .14, .02, 20), stdM('#2a2a2a', null, .4)); bn.position.set(x, .02, z); stove.add(bn); }
      const pot = placeProp(stove, 'bucket', -.25, .03, -.15, 1, 0, { color: '#c8c8c8' }); pot.traverse(o => { if (o.isMesh) { o.material = stdM('#d8d8de', null, .25); o.material.metalness = .9; } });
      const mg = [['#e8344e', 5.1, 1.6], ['#ffd23f', 5.4, 1.3], ['#3d8fe0', 5.2, 1.0]]; for (const [c, x, y] of mg) { const m = new THREE.Mesh(G.sph(.05, 10, 8), stdM(c, null, .4)); m.position.set(x, y, -2.53); g.add(m); }
      const fh = new THREE.Mesh(G.box(.04, .6, .05), stdM('#c8c8c8', null, .2)); fh.position.set(4.85, 1.35, -2.52); g.add(fh); } }
  if (type === 'winter') { swapMat(o => { const geo = o.geometry.parameters || {}; if (o.geometry.type === 'PlaneGeometry' && geo.width === 120) return new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: snowT(), roughness: .7, sheen: 1, sheenColor: new THREE.Color('#dfefff') }); return null; });
    for (let k = 0; k < 9; k++) { const d = new THREE.Mesh(G.sph(1, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshPhysicalMaterial({ color: 0xffffff, map: snowT(), roughness: .7, sheen: 1, sheenColor: new THREE.Color('#dfefff') })); const x = (r() - .5) * 22; if (Math.abs(x) < 4) continue; d.position.set(x, -.05, -2.5 - r() * 6); d.scale.set(1 + r() * 1.5, .25 + r() * .3, .8 + r()); d.receiveShadow = true; g.add(d); }
    const sled = new THREE.Group(); sled.position.set(-4.5, 0, .8); sled.rotation.y = .6; g.add(sled); for (const z of [-.18, .18]) { const run = new THREE.Mesh(new THREE.TorusGeometry(.1, .015, 6, 16, Math.PI / 2), stdM('#c8c8c8', null, .3)); run.position.set(.45, .1, z); run.rotation.z = -Math.PI / 2; sled.add(run); const rl = new THREE.Mesh(G.box(.9, .02, .03), stdM('#c8c8c8', null, .3)); rl.position.set(0, .01, z); sled.add(rl); } for (let k = 0; k < 5; k++) { const sl = new THREE.Mesh(G.box(.14, .03, .46), stdM('#e8344e', null, .6)); sl.position.set(-.36 + k * .18, .14, 0); sled.add(sl); } }
  if (type === 'space') { swapMat(o => { const geo = o.geometry.parameters || {}; if (o.geometry.type === 'PlaneGeometry' && geo.width === 120) return stdM(null, moonGroundT(), .95); if (o.geometry.type === 'CylinderGeometry' && o.position.y < .1 && o.position.y > 0) return stdM('#8e8e9a', null, .95); return null; });
    const earth = new THREE.Mesh(G.sph(3, 40, 30), new THREE.MeshBasicMaterial({ map: ctex('earth', 256, 128, (q) => { q.fillStyle = '#2f6fd0'; q.fillRect(0, 0, 256, 128); const rr = rng(3); q.fillStyle = '#4fae45'; for (let k = 0; k < 9; k++) { q.beginPath(); q.ellipse(rr() * 256, 20 + rr() * 88, 14 + rr() * 30, 8 + rr() * 18, rr() * 3, 0, 7); q.fill(); } q.fillStyle = 'rgba(255,255,255,.7)'; for (let k = 0; k < 14; k++) { q.beginPath(); q.ellipse(rr() * 256, rr() * 128, 10 + rr() * 26, 3 + rr() * 5, 0, 0, 7); q.fill(); } }) }));
    earth.position.set(-6, 24, -75); earth.material.toneMapped = false; g.add(earth); g.traverse(o => { if (o.isMesh && o.geometry.type === 'SphereGeometry' && o.geometry.parameters.radius === 2 && o.position.z === -55) o.visible = false; }); const fl = new THREE.Group(); fl.position.set(3.2, 0, -2.4); g.add(fl); const pole = new THREE.Mesh(G.cyl(.02, .02, 1.6, 8), stdM('#d8d8d8', null, .3)); pole.position.y = .8; fl.add(pole); const fg = new THREE.Mesh(new THREE.PlaneGeometry(.6, .4), stdM('#e8344e', null, .7)); fg.material.side = THREE.DoubleSide; fg.position.set(.31, 1.38, 0); fl.add(fg); }
  g.traverse(o => { if (o.isMesh && o.castShadow === undefined) o.castShadow = true; });
}
function animateLoc(g, T) { windU.value = T;
  if (g.userData.clouds) g.userData.clouds.forEach((c, i) => c.position.x = -30 + i * 12 + ((T * .4) % 12));
  const w = g.userData.weather; if (w) { const a = w.pm.geometry.attributes.position.array; w.seeds.forEach((s, i) => { const sp = w.rain ? 9 : 1.1; let y = 12 - ((s[1] + T * sp * s[3]) % 12); a[i * 3] = s[0] + (w.rain ? 0 : Math.sin(T + i) * .3); a[i * 3 + 1] = y; a[i * 3 + 2] = s[2]; }); w.pm.geometry.attributes.position.needsUpdate = true; }
  if (g.userData.sea) g.userData.sea.position.y = (MK3D.hq ? .25 : .02) + Math.sin(T * 1.5) * .02;
  if (g.userData.foam) { g.userData.foam.position.z = -4.1 + Math.sin(T * .9) * .25; g.userData.foam.position.y = .28; g.userData.foam.material.opacity = .45 + Math.sin(T * .9 + 1) * .25; }
}
function lightFor(type, time) { lightBase(type, time); if (MK3D.hq) { hemi.intensity *= .35; sun.intensity *= 1.25; if (rim) { rim.intensity = time === 'night' || type === 'space' ? 1.8 : 1.3; rim.color.set(time === 'night' || type === 'space' ? 0xc8d4ff : 0xfff4e6); } } }
function lightBase(type, time) { // свет всегда почти белый: герой выглядит одинаково днём, вечером и ночью; настроение даёт небо
  const night = time === 'night', eve = time === 'evening', indoor = type === 'room' || type === 'kitchen';
  { const big = MK3D.hq && type === 'forest' && !night, sc = sun.shadow.camera; Object.assign(sc, big ? { left: -15, right: 15, top: 13, bottom: -11 } : { left: -9, right: 9, top: 7, bottom: -5 }); sc.updateProjectionMatrix(); }
  if (MK3D.hq && type === 'forest' && !night) { hemi.color.set(eve ? 0xffe8d0 : 0xd6f0ff); hemi.groundColor.set(0x56703a); hemi.intensity = 1.25; sun.color.set(eve ? 0xffd9a8 : 0xfff0d4); sun.intensity = eve ? 2.7 : 2.9; sun.position.set(6, 9.5, 1.5); return; }
  hemi.groundColor.set(0x8a8a80);
  if (type === 'space') { hemi.color.set(0xf0f2ff); hemi.intensity = 1.15; sun.color.set(0xffffff); sun.intensity = 2.2; sun.position.set(6, 9, 5); return; }
  if (indoor) { hemi.color.set(0xfffcf6); hemi.intensity = 1.2; sun.color.set(0xffffff); sun.intensity = night ? 1.7 : 1.9; sun.position.set(2, 7, 6); return; }
  if (night) { hemi.color.set(0xe6ebff); hemi.intensity = 1.05; sun.color.set(0xf0f3ff); sun.intensity = 1.8; sun.position.set(-5, 8, 5); return; }
  if (eve) { hemi.color.set(0xfffaf4); hemi.intensity = 1.1; sun.color.set(0xfff6ec); sun.intensity = 2.0; sun.position.set(-6, 6, 6); return; }
  hemi.color.set(0xf4f8ff); hemi.intensity = 1.15; sun.color.set(0xffffff); sun.intensity = 2.2; sun.position.set(4, 8, 6);
}

// ---------- камера ----------
function camFor(c, S, seg, lib) {
  const h = id => { const lc = lib.characters[id]; return lc ? (lc.spec.height || 1) * (lc.spec.kind === 'human' && (lc.spec.age === 'adult' || lc.spec.age === 'old') ? 1.62 : lc.spec.kind === 'human' ? 1.02 : 1) : 1; };
  const px = id => S[id] ? X(S[id].x) : 0, pz = id => S[id] ? -(S[id].z || 0) * 1.5 : 0;
  const ids = Object.keys(seg.C);
  const topOf = id => { const lc = lib.characters[id], rg = lc && rigFor(lc); return rg && rg.headH ? rg.headH + rg.headR * 1.75 : 1.1 * h(id); }; // макушка с ушками — всегда в кадре
  if (c.mode === 'close' || c.mode === 'medium') { const id = c.on || ids[0], hh = h(id), x = px(id), z = pz(id); const close = c.mode === 'close', side = S[id] && S[id].face < 0 ? -1 : 1;
    const lc = lib.characters[id], rg = lc && rigFor(lc); if (rg && rg.headH) { const hy = rg.headH, hr = rg.headR, zk = c.zoom ? c.zoom / (close ? 2.3 : 1.55) : 1; // кадр по голове героя: крупно — лицо и плечи, средний — во весь рост
      return close ? { pos: new THREE.Vector3(x + side * hr * .9, hy - hr * .05, z + hr * 6.4 / zk), look: new THREE.Vector3(x + side * hr * .2, hy - hr * .32, z) }
        : { pos: new THREE.Vector3(x + side * hr * 1.6, hy * .78, z + Math.max(hr * 11.5, hy * 1.9) / zk), look: new THREE.Vector3(x + side * hr * .4, hy * .6, z) }; }
    return { pos: new THREE.Vector3(x + side * (close ? .13 : .3), (close ? .78 : .8) * hh + (close ? .02 : .06), z + (close ? 1.15 : 2.15) * Math.max(.8, hh) / (c.zoom ? c.zoom / (close ? 2.3 : 1.55) : 1)), look: new THREE.Vector3(x + side * (close ? .03 : .08), (close ? .7 : .56) * hh, z) }; }
  if (c.mode === 'group') { const list = (c.ids || ids).filter(id => S[id] && S[id].vis !== false); let lo = 1e9, hi = -1e9, hh = .9;
    for (const id of list) { const x = px(id), w = .5 * h(id); lo = Math.min(lo, x - w); hi = Math.max(hi, x + w); hh = Math.max(hh, h(id)); } for (const q of c.px || []) { lo = Math.min(lo, X(q) - .45); hi = Math.max(hi, X(q) + .45); }
    if (lo <= hi) { const mid = (lo + hi) / 2, d = clamp((hi - lo + 1.1) / 2 / .612, 3.3, 8.4), tp = Math.max(...list.map(topOf)), ly = Math.max(.52 * hh + d * .035, tp - .28 * d); return { pos: new THREE.Vector3(mid, ly + .08 * hh + d * .095, d), look: new THREE.Vector3(mid, ly, 0) }; } }
  if (c.mode === 'two') { const pair = Array.isArray(c.on) ? c.on : ids.slice(0, 2); const a = px(pair[0]), b = px(pair[1] || pair[0]), hh = Math.max(h(pair[0]), h(pair[1] || pair[0])), wa = .5 * h(pair[0]), wb = .5 * h(pair[1] || pair[0]);
    const lo = Math.min(a - wa, b - wb), hi = Math.max(a + wa, b + wb), mid = (lo + hi) / 2, d = clamp((hi - lo + .9) / 2 / .612, 2.9, 7);
    const tp = Math.max(topOf(pair[0]), topOf(pair[1] || pair[0])), ly = Math.max(.55 * hh + d * .03, tp - .28 * d); return { pos: new THREE.Vector3(mid, ly + .05 * hh + d * .09, d), look: new THREE.Vector3(mid, ly, 0) }; }
  if (c.mode === 'pan') { const x = X(c.on != null ? +c.on : .5); return { pos: new THREE.Vector3(x, 1.5, 6 / (c.zoom || 1.3) * 1.3), look: new THREE.Vector3(x, .8, 0) }; }
  return { pos: new THREE.Vector3(0, 1.75, 8.4), look: new THREE.Vector3(0, .85, 0) };
}

// ---------- кадр ----------
let curLoc = null;
function showLoc(key, spec) { let g = locCache[key]; if (!g) { g = buildLoc(spec); locCache[key] = g; scene.add(g); } if (curLoc && curLoc !== g) curLoc.visible = false; g.visible = true; curLoc = g; return g; }
function hideAllRigs() { if (curTheme) curTheme.visible = false; for (const k in rigCache) rigCache[k].root.visible = false; for (const k in propCache) propCache[k].visible = false; for (let i = 0; i < spriteUsed; i++) spritePool[i].visible = false; spriteUsed = 0; }
function ensureIn(obj) { if (obj.parent !== scene) scene.add(obj); }

// ---------- «киношная» обработка кадра: свечение, размытый фон на крупных планах, цвет, виньетка ----------
let PP = null;
const PP_VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';
function ppMat(fs, uniforms, final) { return new THREE.ShaderMaterial({ vertexShader: PP_VS, fragmentShader: fs, uniforms, depthTest: false, depthWrite: false, toneMapped: !!final }); }
function ppInit(w, h) {
  const rt = (ww, hh, depth) => { const r = new THREE.WebGLRenderTarget(Math.max(1, ww | 0), Math.max(1, hh | 0), { type: THREE.HalfFloatType, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: !!depth, samples: depth ? msaaN() : 0 }); if (depth) r.depthTexture = new THREE.DepthTexture(Math.max(1, ww | 0), Math.max(1, hh | 0)); return r; };
  const P = { w, h, main: rt(w, h, true), h1: rt(w / 2, h / 2), h2: rt(w / 2, h / 2), q1: rt(w / 4, h / 4), q2: rt(w / 4, h / 4), b1: rt(w / 4, h / 4), b2: rt(w / 4, h / 4), e1: rt(w / 8, h / 8), e2: rt(w / 8, h / 8) };
  P.scene = new THREE.Scene(); P.cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1); P.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2)); P.quad.frustumCulled = false; P.scene.add(P.quad);
  P.copy = ppMat('uniform sampler2D t; varying vec2 vUv; void main(){ vec4 c = texture2D(t, vUv); gl_FragColor = (any(isnan(c)) || any(isinf(c))) ? vec4(0.0, 0.0, 0.0, 1.0) : min(c, vec4(48.0)); }', { t: { value: null } });
  P.bright = ppMat('uniform sampler2D t; uniform float thr; varying vec2 vUv; void main(){ vec3 c = texture2D(t, vUv).rgb; c = (any(isnan(c)) || any(isinf(c))) ? vec3(0.0) : min(c, vec3(24.0)); float l = max(c.r, max(c.g, c.b)); float k = clamp((l - thr) / (l + 1e-4), 0.0, 1.0); gl_FragColor = vec4(c * k * k, 1.0); }', { t: { value: null }, thr: { value: .92 } });
  P.blur = ppMat('uniform sampler2D t; uniform vec2 d; varying vec2 vUv; void main(){ vec3 c = texture2D(t, vUv).rgb * .2270; c += (texture2D(t, vUv + d * 1.3846).rgb + texture2D(t, vUv - d * 1.3846).rgb) * .3162; c += (texture2D(t, vUv + d * 3.2308).rgb + texture2D(t, vUv - d * 3.2308).rgb) * .0703; gl_FragColor = vec4(c, 1.0); }', { t: { value: null }, d: { value: new THREE.Vector2() } });
  P.r1 = rt(w / 4, h / 4); P.r2 = rt(w / 4, h / 4);
  P.rays = ppMat(`uniform sampler2D tMain, tDepth; uniform vec2 src; varying vec2 vUv;
    void main(){ vec2 uv = vUv, d = (vUv - src) / 56.0; float decay = 1.0; vec3 acc = vec3(0.0);
      for (int i = 0; i < 56; i++) { uv -= d; vec2 u = clamp(uv, 0.001, .999); float sky = step(.99995, texture2D(tDepth, u).x); vec3 c = texture2D(tMain, u).rgb; float l = max(c.r, max(c.g, c.b)); acc += c * sky * smoothstep(.45, 1.0, l) * decay; decay *= .955; }
      gl_FragColor = vec4(acc / 22.0, 1.0); }`, { tMain: { value: null }, tDepth: { value: null }, src: { value: new THREE.Vector2(.7, 1.25) } });
  P.comp = ppMat(`#include <packing>
    uniform sampler2D tMain, tHalf, tQuart, tB1, tB2, tDepth, tRays; uniform float near, far, focus, ap, bloom, sat, con, vig, rays; uniform vec3 tintH, tintS, rayCol; varying vec2 vUv;
    void main(){
      vec3 c = texture2D(tMain, vUv).rgb; c = (any(isnan(c)) || any(isinf(c))) ? vec3(0.0) : min(c, vec3(48.0));
      if (ap > 0.0) { float z = -perspectiveDepthToViewZ(texture2D(tDepth, vUv).x, near, far); float coc = clamp(ap * abs(1.0 - focus / max(z, .01)) * 2.4, 0.0, 1.0);
        vec3 hb = texture2D(tHalf, vUv).rgb, qb = texture2D(tQuart, vUv).rgb; c = coc < .5 ? mix(c, hb, coc * 2.0) : mix(hb, qb, (coc - .5) * 2.0); }
      c += texture2D(tB1, vUv).rgb * bloom * .7 + texture2D(tB2, vUv).rgb * bloom;
      if (rays > 0.0) { vec3 r = texture2D(tRays, vUv).rgb; c += r * rayCol * rays * .8; } // лучи света сквозь кроны
      float l = dot(c, vec3(.2126, .7152, .0722)); c = mix(vec3(l), c, sat);
      c *= mix(tintS, tintH, smoothstep(.05, .7, l));
      c = (c - .18) * con + .18; c = max(c, 0.0);
      vec2 q = vUv - .5; c *= 1.0 - vig * smoothstep(.25, .85, dot(q, q) * 2.2);
      gl_FragColor = vec4(c, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`, { tMain: { value: null }, tHalf: { value: null }, tQuart: { value: null }, tB1: { value: null }, tB2: { value: null }, tDepth: { value: null }, tRays: { value: null }, rays: { value: 0 }, rayCol: { value: new THREE.Vector3(1, .95, .82) }, near: { value: .1 }, far: { value: 200 }, focus: { value: 5 }, ap: { value: 0 }, bloom: { value: .5 }, sat: { value: 1.06 }, con: { value: 1.05 }, vig: { value: .22 }, tintH: { value: new THREE.Vector3(1, 1, 1) }, tintS: { value: new THREE.Vector3(1, 1, 1) } }, true);
  return P; }
function ppPass(mat, uni, target) { const P = PP; P.quad.material = mat; for (const k in uni) mat.uniforms[k].value = uni[k]; R.setRenderTarget(target); R.render(P.scene, P.cam); }
const GRADE = { forest: [[1.07, 1.01, .9], [.86, .99, 1.05], 1.1, 1.09], day: [[1.03, 1.01, .97], [.97, .99, 1.04], 1.08, 1.05], evening: [[1.08, .99, .9], [.94, .9, 1.06], 1.08, 1.06], night: [[.96, .99, 1.06], [.84, .9, 1.12], .92, 1.08], indoor: [[1.05, 1.0, .94], [.97, .97, 1.0], 1.05, 1.04], space: [[1, 1, 1.02], [.9, .92, 1.1], 1.05, 1.1] };
// Сглаживание: раньше кадр считался в 4 раза крупнее (3840×2160) — телефон грелся. Теперь кадр 1920×1080 с аппаратным сглаживанием ×4 (MSAA):
// края и волоски такие же гладкие, а работы видеокарте в 3–4 раза меньше. Если телефон не умеет — запасной путь: кадр в 1.5 раза крупнее.
let MSAA = null;
function msaaN() { if (MSAA !== null) return MSAA; MSAA = 0; if (MK3D._noMsaa) return 0; try { const caps = R.capabilities, n = caps.isWebGL2 ? Math.min(4, caps.maxSamples || 0) : 0; if (n < 2) return MSAA;
    const a = new THREE.WebGLRenderTarget(32, 32, { type: THREE.HalfFloatType, depthBuffer: true, samples: n }); a.depthTexture = new THREE.DepthTexture(32, 32);
    const b = new THREE.WebGLRenderTarget(4, 4), ts = new THREE.Scene(), tc = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1), q = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial({ color: 0xff0000 })); ts.add(q);
    R.setRenderTarget(a); R.render(ts, tc); q.material = new THREE.MeshBasicMaterial({ map: a.texture }); R.setRenderTarget(b); R.render(ts, tc); const px = new Uint8Array(4 * 4 * 4); R.readRenderTargetPixels(b, 0, 0, 4, 4, px); R.setRenderTarget(null);
    if (px[0] > 150 && px[1] < 80) MSAA = n; a.dispose(); b.dispose(); } catch (e) { MSAA = 0; } return MSAA; }
MK3D.ss = () => MK3D._ssOverride || (msaaN() ? 1 : 1.5);
function renderHQ(w, h) {
  if (!PP || PP.w !== w || PP.h !== h) { if (PP) for (const k of ['main', 'h1', 'h2', 'q1', 'q2', 'b1', 'b2', 'e1', 'e2', 'r1', 'r2']) PP[k].dispose(); PP = ppInit(w, h); }
  const P = PP, f = Math.max(.5, w / 3840); R.setRenderTarget(P.main); R.clear(); R.render(scene, cam); // f: размытия задуманы для кадра 3840 — тот же размер на экране
  const ap = MK3D._ap || 0;
  ppPass(P.copy, { t: P.main.texture }, P.h1);
  if (ap > 0) { ppPass(P.blur, { t: P.h1.texture, d: new THREE.Vector2(1.6 * f / P.h1.width, 0) }, P.h2); ppPass(P.blur, { t: P.h2.texture, d: new THREE.Vector2(0, 1.6 * f / P.h1.height) }, P.h1);
    ppPass(P.copy, { t: P.h1.texture }, P.q1); ppPass(P.blur, { t: P.q1.texture, d: new THREE.Vector2(2.2 * f / P.q1.width, 0) }, P.q2); ppPass(P.blur, { t: P.q2.texture, d: new THREE.Vector2(0, 2.2 * f / P.q1.height) }, P.q1); }
  ppPass(P.bright, { t: P.main.texture, thr: .9 }, P.h2); ppPass(P.copy, { t: P.h2.texture }, P.b1); // яркое — сначала в половинном размере, потом мягко вниз (без «квадратиков»)
  for (const r of [1.5, 3]) { ppPass(P.blur, { t: P.b1.texture, d: new THREE.Vector2(r * f / P.b1.width, 0) }, P.b2); ppPass(P.blur, { t: P.b2.texture, d: new THREE.Vector2(0, r * f / P.b1.height) }, P.b1); }
  ppPass(P.copy, { t: P.b1.texture }, P.e1); ppPass(P.blur, { t: P.e1.texture, d: new THREE.Vector2(2 * f / P.e1.width, 0) }, P.e2); ppPass(P.blur, { t: P.e2.texture, d: new THREE.Vector2(0, 2 * f / P.e1.height) }, P.e1);
  const rs = MK3D._rays || 0; if (rs > 0) { ppPass(P.rays, { tMain: P.main.texture, tDepth: P.main.depthTexture, src: MK3D._raySrc || new THREE.Vector2(.7, 1.25) }, P.r1); ppPass(P.blur, { t: P.r1.texture, d: new THREE.Vector2(1.2 * f / P.r1.width, 0) }, P.r2); ppPass(P.blur, { t: P.r2.texture, d: new THREE.Vector2(0, 1.2 * f / P.r1.height) }, P.r1); }
  const gr = GRADE[MK3D._grade || 'day'] || GRADE.day;
  ppPass(P.comp, { tRays: P.r1.texture, rays: rs, rayCol: MK3D._rayCol || new THREE.Vector3(1, .95, .82), tMain: P.main.texture, tHalf: P.h1.texture, tQuart: P.q1.texture, tB1: P.b1.texture, tB2: P.e1.texture, tDepth: P.main.depthTexture, near: cam.near, far: cam.far, focus: MK3D._focus || 5, ap, bloom: .55, sat: gr[2], con: gr[3], vig: MK3D._vig != null ? MK3D._vig : .22, tintH: new THREE.Vector3(...gr[0]), tintS: new THREE.Vector3(...gr[1]) }, null);
}
let shN = 0, shT = -9, shLoc = null, shP = null;
function render(ctx) {
  const w = ctx.canvas.width, h = ctx.canvas.height;
  const ss = MK3D.hq ? MK3D.ss() : 1, W = Math.round(w * ss), H = Math.round(h * ss);
  { // тени пересчитываем через кадр (герои за 1/25 с почти не сдвигаются), а при смене места или скачке времени — сразу
    const T = MK3D._T || 0; shN++; if (!shP) shP = new THREE.Vector3(1e9, 0, 0); R.shadowMap.autoUpdate = false; if (shN % 2 === 1 || curLoc !== shLoc || Math.abs(T - shT) > .09 || sun.target.position.distanceTo(shP) > .25) { R.shadowMap.needsUpdate = true; shT = T; shLoc = curLoc; shP.copy(sun.target.position); } }
  if (GL.width !== W || GL.height !== H) { GL.width = W; GL.height = H; R.setSize(W, H, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
  if (MK3D.hq) { scene.updateMatrixWorld(true); for (const k in rigCache) { const rg = rigCache[k]; if (rg.root.visible && rg.fur) furFrame(rg, MK3D._T || 0); } renderHQ(W, H); }
  else R.render(scene, cam);
  MK3D._ap = 0; MK3D._vig = null; MK3D._rays = 0;
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high'; ctx.drawImage(GL, 0, 0, w, h); ctx.restore();
}
MK3D.draw = function (ctx, tl, seg, t, T) {
  hideAllRigs();
  if (seg.kind === 'title' || seg.kind === 'end') return drawCard3D(ctx, tl, seg, t, T);
  const L = seg.lspec || {}; const g = showLoc(seg.lkey, L); animateLoc(g, T);
  const cineF = MK3D.hq && L.type === 'forest' && L.time !== 'night';
  scene.background = cineF ? mistTex(L.time || 'day') : skyTex(L.time || 'day', L.type); scene.fog = ['room', 'kitchen', 'space'].includes(L.type) ? null : cineF ? new THREE.Fog(new THREE.Color(L.time === 'evening' ? '#cdb79c' : '#a9cbbd'), 4.5, 30) : new THREE.Fog(new THREE.Color(SKY[L.time || 'day'][1]), 18, 70);
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
    else if (p._tb && L.type === 'kitchen') { m.position.set(clamp(X(p._x), 3.35, 4.45), .83, -.95); m.scale.setScalar(1.15 * sc); m.rotation.z = 0; }
    else { const zz = p.decor && big > 1.5 ? -1.9 : p.decor ? -.5 : .35; m.position.set(X(p._x), (p._air || 0) * 1.2 + (m.userData.float ? Math.sin(T * 2 + p._x * 9) * .08 : 0), zz); m.scale.setScalar(big * (p.decor && big < 1.5 ? 1.6 : 1) * sc); m.rotation.z = -(p._air || 0) * 3; }
    if (m.userData.leaf) { const ok = p._open || 0; m.userData.leaf.rotation.y = -ok * 1.75; m.userData.doorLight.material.opacity = Math.min(1, ok * 1.6); if (ok > .05 && m.visible) sprite(haloTex('#ffe6a0'), m.position.x, m.position.y + .55 * m.scale.x, m.position.z + .1, 1.6 * m.scale.x * (.6 + ok * .4), .7 * ok); }
    if (m.userData.flames) m.userData.flames.forEach((f, i) => { const s0 = f.userData.s0 || (f.userData.s0 = f.scale.clone()); const k = 1 + Math.sin(T * 13 + i * 2.1) * .08 + Math.sin(T * 7.3 + i) * .06; f.scale.set(s0.x * (2 - k), s0.y * k, s0.z * (2 - k)); });
    const gl = m.userData.alwaysGlow ? 1 : (p._glow || 0); if (m.userData.faceMat) m.userData.faceMat.color.set(gl > 0 ? 0xffc23a : 0x3a1a08);
    if (gl > 0 && m.visible) { const gy = m.userData.glowY != null ? m.userData.glowY : .2, gs = Math.max(p._holder ? .6 : .5, (m.userData.glowS || .7) * m.scale.x), pulse = 1 + Math.sin(T * 3 + p._x * 7) * .08;
      sprite(haloTex(m.userData.glowC || '#ffe27a'), m.position.x, m.position.y + gy * m.scale.x, m.position.z + .12, gs * pulse * (.5 + gl * .5), (p._holder ? .95 : .8) * gl);
      if (!m.userData.alwaysGlow) for (let i = 0; i < 3; i++) { const q = (T * .5 + i / 3) % 1; sprite(glyphTex('✦', '#fff4b0'), m.position.x + Math.sin(i * 2.3 + T) * gs * .45, m.position.y + gy * m.scale.x + (q - .3) * gs * .7, m.position.z + .2, .12 * Math.max(1, m.scale.x * .5), Math.sin(q * Math.PI) * gl); } }
    if (p._fx === 'appear' && fa < 1.1) for (let i = 0; i < 10; i++) { const a = i / 10 * Math.PI * 2, r = .2 + fa * 1.1 * Math.max(1, big * .6); sprite(glyphTex('★', '#ffd23f', '#ffffff'), m.position.x + Math.cos(a) * r, m.position.y + .3 * big + Math.sin(a) * r, m.position.z + .3, .16, 1 - fa / 1.1); }
    if (p._fx === 'vanish' && fa < 1.1) poof(p, fa, m);
  }
  function poof(p, fa, m) { if (fa > 1.1 || p._fx !== 'vanish') return; const onT = !m && p.tb0 && L.type === 'kitchen'; const x = m ? m.position.x : onT ? clamp(X(p._x), 3.35, 4.45) : X(p._x), y = m ? m.position.y + .25 * (p.big || 1) : onT ? 1.05 : .3, z = m ? m.position.z + .3 : onT ? -.7 : .4;
    for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2, r = .15 + fa * .7 * Math.max(1, (p.big || 1) * .6); sprite(haloTex('#ffffff'), x + Math.cos(a) * r, y + Math.sin(a) * r * .7, z, (.35 + fa * .4) * Math.max(1, (p.big || 1) * .5), (1 - fa / 1.1) * .9); } }
  showTheme(seg, T);
  // камера
  let ci = 0; const cams = seg.cam.filter(c => !c.shake); for (let i = 0; i < cams.length; i++) if (cams[i].t <= t) ci = i;
  const cur = camFor(cams[ci], S, seg, tl.lib), prev = ci > 0 ? camFor(cams[ci - 1], S, seg, tl.lib) : cur, k = cams[ci].cut ? 1 : ease((t - cams[ci].t) / .9);
  cam.position.lerpVectors(prev.pos, cur.pos, k); const look = new THREE.Vector3().lerpVectors(prev.look, cur.look, k);
  for (const c of seg.cam) if (c.shake && t >= c.t && t < c.t + c.shake) { const a = (1 - (t - c.t) / c.shake) * .08; cam.position.x += Math.sin(t * 61) * a; cam.position.y += Math.cos(t * 53) * a; }
  cam.fov = 38; cam.updateProjectionMatrix(); cam.lookAt(look);
  { const mode = cams[ci].mode || 'wide', AP = { close: .38, medium: .3, two: .22, group: .14, pan: .12 }, ap0 = AP[mode] || .08, apP = ci > 0 && !cams[ci].cut ? (AP[cams[ci - 1].mode] || .08) : ap0; MK3D._ap = lerp(apP, ap0, k); MK3D._focus = cam.position.distanceTo(look) * .95; // резкость — на лице героя, фон мягко размыт
    MK3D._grade = ['room', 'kitchen'].includes(L.type) ? 'indoor' : L.type === 'space' ? 'space' : cineF && L.time !== 'evening' ? 'forest' : (L.time || 'day');
    { const tm = L.time || 'day', ty = L.type || 'yard'; MK3D._rays = tm === 'night' || ['space', 'room', 'kitchen'].includes(ty) || L.weather === 'rain' ? 0 : (ty === 'forest' ? .7 : .3) * (tm === 'evening' ? 1.25 : 1); MK3D._rayCol = tm === 'evening' ? new THREE.Vector3(1, .78, .55) : new THREE.Vector3(1, .95, .82); MK3D._raySrc = new THREE.Vector2(.5 + Math.sin((L.seed || 3) * 1.7) * .25, 1.28); } }
  sun.target.position.copy(look); sun.position.add(look); MK3D._T = t; if (rim) { rim.target.position.copy(look); rim.position.set(look.x - 3, 4, look.z - 6); }
  render(ctx);
};
function drawCard3D(ctx, tl, seg, t, T) { MK3D._T = t + 1000;
  const title = seg.kind === 'title';
  if (curLoc) curLoc.visible = false;
  { const ck = title ? 'cardT' : 'cardE'; scene.background = texCache[ck] || (texCache[ck] = canvasTex(4, 256, (g) => { const gr = g.createLinearGradient(0, 0, 0, 256); gr.addColorStop(0, title ? '#ff9a5c' : '#5a6fd8'); gr.addColorStop(1, title ? '#ffd56b' : '#9ad0ff'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); })); } // один раз, а не новый холст на каждый кадр; scene.fog = null;
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
/** Сборка серии: выгрузить места, которые дальше в серии не встретятся (память телефона не копится от сцены к сцене). */
MK3D.keepLocs = function (keys) { for (const k in locCache) { if (k === '__stage' || keys.has(k) || locCache[k] === curLoc) continue; const g = locCache[k]; scene.remove(g);
  g.traverse(o => { if (o.geometry && o.geometry.dispose) o.geometry.dispose(); }); delete locCache[k]; } };
/** Облегчённый режим (если телефону не хватило памяти на сцене): без сглаживания ×4 — меньше видеопамяти. */
MK3D.lowMem = function (on) { on = !!on; if (!!MK3D._noMsaa === on) return; MK3D._noMsaa = on; MK3D._ssOverride = on ? 1 : 0; MSAA = null;
  if (PP) { for (const k of ['main', 'h1', 'h2', 'q1', 'q2', 'b1', 'b2', 'e1', 'e2', 'r1', 'r2']) PP[k].dispose(); PP = null; } };
MK3D.locPreview = function (canvas, spec, T) {
  if (!MK3D.ready) return false; hideAllRigs(); const key = global.MK.canon(spec); const g = showLoc(key, spec); animateLoc(g, T || 2);
  const cineF = MK3D.hq && spec.type === 'forest' && spec.time !== 'night'; // лес «как в кино» — с тем же туманом, что в серии (иначе сверху видны тёмные полосы крон на голом небе)
  scene.background = cineF ? mistTex(spec.time || 'day') : skyTex(spec.time || 'day', spec.type); scene.fog = cineF ? new THREE.Fog(new THREE.Color(spec.time === 'evening' ? '#cdb79c' : '#a9cbbd'), 4.5, 30) : null; lightFor(spec.type, spec.time || 'day');
  cam.fov = 38; cam.position.set(0, cineF ? 1.5 : 2.1, cineF ? 9.5 : 10.5); cam.updateProjectionMatrix(); cam.lookAt(0, .95, 0); sun.target.position.set(0, 0, 0);
  render(canvas.getContext('2d')); return true;
};
MK3D.propSheet = function (canvas, types, cols) { // лист предметов для проверки: каждый в своей клетке
  if (!MK3D.ready) return false; hideAllRigs(); if (curLoc) curLoc.visible = false; scene.fog = null; scene.background = col('#e9eef3'); lightFor('meadow', 'day');
  const ctx = canvas.getContext('2d'), rows = Math.ceil(types.length / cols), tw = canvas.width / cols, th = canvas.height / rows; const tc = document.createElement('canvas'); tc.width = Math.round(tw); tc.height = Math.round(th); const tctx = tc.getContext('2d');
  let st0 = envC.__floor; if (!st0) { st0 = new THREE.Mesh(new THREE.CircleGeometry(3, 48), new THREE.MeshStandardMaterial({ color: '#f4f1ec', roughness: .9 })); st0.rotation.x = -Math.PI / 2; st0.receiveShadow = true; envC.__floor = st0; scene.add(st0); } st0.visible = true;
  types.forEach((ty, i) => { const pm = propMesh({ id: 'sheet' + i, type: ty }); ensureIn(pm); pm.visible = true; pm.position.set(0, 0, 0); pm.scale.setScalar(1); pm.rotation.set(0, -.5, 0); scene.updateMatrixWorld(true);
    const bb = new THREE.Box3().setFromObject(pm), c = bb.getCenter(new THREE.Vector3()), sz = bb.getSize(new THREE.Vector3()), R0 = Math.max(sz.x, sz.y, sz.z) * .5 + .02;
    cam.fov = 30; cam.aspect = tw / th; cam.position.set(c.x + R0 * 1.6, c.y + R0 * 1.5, c.z + R0 * 3.4); cam.updateProjectionMatrix(); cam.lookAt(c); sun.position.set(c.x + 3, c.y + 6, c.z + 5); sun.target.position.copy(c);
    render(tctx); ctx.drawImage(tc, (i % cols) * tw, Math.floor(i / cols) * th, tw, th); ctx.fillStyle = '#333'; ctx.font = '14px sans-serif'; ctx.fillText(ty, (i % cols) * tw + 6, Math.floor(i / cols) * th + 16); pm.visible = false; });
  st0.visible = false; return true;
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
