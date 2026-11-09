// БАРС · аура — тень и отсвет не считаются лучами и картой, а «живут» вокруг тела.
// Герой — это мягкие «капли» по костям (тело, голова, лапы, хвост). У каждой капли три поля:
//   1) тень от солнца — вытянута от солнца; у самой лапы резкая, вдали мягкая;
//   2) тень от неба — темнота там, где тела касаются земли и друг друга;
//   3) свой цвет — закрытое телом небо заменяется светом, отражённым от этого тела (рыжий греет траву).
// Земля, трава, вещи спрашивают у капель формулой — без второй отрисовки мира и без карты теней для героев.
// Мир (деревья, дома) остаётся в обычной карте теней; героев в ней при включённой ауре нет.
// ПРОБА: отдельная ветка, в приложение не ставится, пока Михаил не скажет «ставь».
(function (global) {
'use strict';
const N = 32;                                   // капель в кадре (3–4 героя по 7–9)
const A = global.BARSAura = { on: true, N, stats: {},
  K: { soft: .11, sky: .8, bounce: 1.0, sunPart: .5, grow: 1.0 } };   // soft — как быстро тень мягчеет с расстоянием; sky — сила тени от неба; bounce — сила отсвета
(global.BARS = global.BARS || {}).aura = A;
let THREE = null, installed = false;
// общие данные для всех материалов: типизированные массивы передаются по ссылке — обновил раз, видят все
const U = A.U = { uAuA: { value: new Float32Array(N * 4) }, uAuB: { value: new Float32Array(N * 4) }, uAuC: { value: new Float32Array(N * 3) }, uAuP: { value: new Float32Array(4) }, uAuSun: { value: new Float32Array([0, 1, 0]) } };

// ---------- формулы (GLSL) ----------
A.GLSL = `
#define BARS_AURA
#define AU_N ${N}
uniform vec4 uAuA[AU_N]; uniform vec4 uAuB[AU_N]; uniform vec3 uAuC[AU_N]; uniform vec4 uAuP; uniform vec3 uAuSun;
// тень от солнца: ближайшее расстояние от луча «точка → солнце» до оси капли; полутень шире с расстоянием до тела
float auraSun(vec3 p, float self) { int n = int(uAuP.x); float vis = 1.0;
  for (int i = 0; i < AU_N; i++) { if (i >= n) break; if (uAuB[i].w == self) continue;
    vec3 a = uAuA[i].xyz, ba = uAuB[i].xyz - a, oa = p - a; float r = uAuA[i].w;
    float oad = dot(oa, uAuSun), dba = dot(uAuSun, ba), baba = dot(ba, ba), oaba = dot(oa, ba), den = baba - dba * dba;
    float h = den > 1e-7 ? clamp((oaba - oad * dba) / den, 0.0, 1.0) : 0.0;
    vec3 c = a + ba * h; float t = dot(c - p, uAuSun); if (t < -r) continue;
    float tt = max(t, 0.0), d = length(c - (p + uAuSun * tt)) - r;
    float w = uAuP.y * tt + .006, s = clamp(d / w * .5 + .5, 0.0, 1.0);
    vis = min(vis, s * s * (3.0 - 2.0 * s)); }
  return vis; }
// тень от неба и отсвет: какую долю неба закрывает капля и каким цветом она светит взамен (rgb — отсвет, a — закрытая доля)
vec4 auraSky(vec3 p, vec3 n, float self) { int cnt = int(uAuP.x); float open = 1.0; vec3 bc = vec3(0.0);
  for (int i = 0; i < AU_N; i++) { if (i >= cnt) break; if (uAuB[i].w == self) continue;
    vec3 a = uAuA[i].xyz, ba = uAuB[i].xyz - a; float r = uAuA[i].w;
    float h = clamp(dot(p - a, ba) / max(dot(ba, ba), 1e-7), 0.0, 1.0); vec3 dv = a + ba * h - p; float d2 = max(dot(dv, dv), 1e-6);
    if (d2 > r * r * 30.0) continue;
    float nl = dot(n, dv) * inversesqrt(d2), o = clamp((nl * .6 + .4), 0.0, 1.0) * min(r * r / d2, 1.0);
    o *= 1.0 - smoothstep(r * r * 16.0, r * r * 30.0, d2);
    open *= 1.0 - o; bc += uAuC[i] * o; }
  return vec4(bc, 1.0 - open); }
`;
const HEAD = '\n#if defined( STANDARD ) || defined( LAMBERT ) || defined( PHONG ) || defined( TOON )\n';

A.install = function (T) {
  THREE = T; if (installed) return true; const C = THREE.ShaderChunk, L = THREE.ShaderLib; if (!C || !L) return false;
  const src = C.lights_fragment_begin, key = /getDirectionalLightInfo\(\s*directionalLight\s*,\s*directLight\s*\);/;
  if (!key.test(src) || C.lights_pars_begin.indexOf('BARS_AURA') >= 0) { A.error = 'шейдеры three.js другие — аура не подключена'; return false; }
  C.lights_pars_begin += A.GLSL;
  // мир: точка и нормаль — из положения относительно камеры (есть у всех освещаемых материалов)
  C.lights_fragment_begin = HEAD + 'vec3 auWp = ( vec4( - vViewPosition, 0.0 ) * viewMatrix ).xyz + cameraPosition; vec3 auWn = inverseTransformDirection( normal, viewMatrix );\nfloat auSunV = receiveShadow && uAuP.x > 0.5 ? auraSun( auWp + auWn * .004, -1.0 ) : 1.0;\n#else\nfloat auSunV = 1.0;\n#endif\n' +
    src.replace(key, m => m + '\n#if UNROLLED_LOOP_INDEX == 0\n directLight.color *= auSunV;\n#endif\n');
  C.aomap_fragment += HEAD + 'if ( receiveShadow && uAuP.x > 0.5 ) { vec4 au = auraSky( auWp, auWn, -1.0 ); float ak = au.a * uAuP.z;\n reflectedLight.indirectDiffuse *= 1.0 - ak; reflectedLight.indirectSpecular *= 1.0 - ak;\n reflectedLight.indirectDiffuse += diffuseColor.rgb * RECIPROCAL_PI * au.rgb * uAuP.w; }\n#endif\n';
  for (const k of ['physical', 'standard', 'lambert', 'phong', 'toon']) if (L[k]) Object.assign(L[k].uniforms, U);
  installed = true; return true;
};

// ---------- капли героя: по деталям его «скелета» ----------
const _a = [], cols = new WeakMap();
function meanColor(o) { const g = o.geometry, ca = g.attributes.color; let c = cols.get(g); if (c) return c; c = [1, 1, 1];
  if (ca) { let r = 0, gg = 0, b = 0; const n = ca.count, st = Math.max(1, Math.floor(n / 400)); let k = 0; for (let i = 0; i < n; i += st) { r += ca.getX(i); gg += ca.getY(i); b += ca.getZ(i); k++; } c = [r / k, gg / k, b / k]; }
  if (o.material && o.material.color && !o.material.map) { c[0] *= o.material.color.r; c[1] *= o.material.color.g; c[2] *= o.material.color.b; }
  cols.set(g, c); return c; }
function partsOf(rig) { if (rig._auParts) return rig._auParts; const list = rig._auParts = [], skip = new Set();
  if (rig.h6) for (const e of (rig.ears || []).concat(rig.hats || [])) if (e) e.traverse(c => skip.add(c));   // у Пика и Рона уши и кепка «глины» не такие, как у настоящей модели
  rig.root.traverse(o => { if (!o.isMesh || !o.userData.sculpt || skip.has(o) || !o.geometry || !o.geometry.attributes.position) return; const g = o.geometry; if (!g.boundingBox) g.computeBoundingBox();
    const bb = g.boundingBox, c = bb.getCenter(new THREE.Vector3()), s = bb.getSize(new THREE.Vector3()).multiplyScalar(.5), e = [s.x, s.y, s.z], ax = e[0] >= e[1] && e[0] >= e[2] ? 0 : e[1] >= e[2] ? 1 : 2;
    const o2 = e.filter((v, i) => i !== ax), r = Math.sqrt(Math.max(1e-6, o2[0] * o2[1])) * .9, hl = Math.max(0, e[ax] * .95 - r), a = c.clone(), b = c.clone(); a.setComponent(ax, c.getComponent(ax) - hl); b.setComponent(ax, c.getComponent(ax) + hl);
    list.push({ o, a, b, r, col: meanColor(o) }); });
  return list; }

/** Перед кадром: собрать капли всех видимых героев образца. lights = { sun, hemi }. */
A.frame = function (rigs, lights, hq) {
  const P = U.uAuP.value; let n = 0; const st = { heroes: 0, caps: 0 };
  if (!installed || !A.on || !hq) { P[0] = 0; for (const k in rigs) { const rg = rigs[k]; if (rg.blob && rg._auBlob) { rg.blob.visible = true; rg._auBlob = false; } } A.active = false; A.stats = st; return; }
  if (!_a.length) for (let i = 0; i < 4; i++) _a.push(new THREE.Vector3());
  const sun = lights.sun, hemi = lights.hemi, A4 = U.uAuA.value, B4 = U.uAuB.value, C3 = U.uAuC.value, K = A.K;
  const sd = _a[2].copy(sun.position).sub(sun.target.position).normalize(); U.uAuSun.value[0] = sd.x; U.uAuSun.value[1] = sd.y; U.uAuSun.value[2] = sd.z;
  // свет, которым тело светит обратно: часть солнца + небо и земля
  const E = [0, 1, 2].map(i => { const sc = [sun.color.r, sun.color.g, sun.color.b][i] * sun.intensity * K.sunPart, hc = hemi ? ([hemi.color.r, hemi.color.g, hemi.color.b][i] + [hemi.groundColor.r, hemi.groundColor.g, hemi.groundColor.b][i]) * .5 * hemi.intensity : 0; return sc + hc; });
  let id = 0;
  for (const k in rigs) { const rg = rigs[k]; if (!rg.root.visible || !(rg.bars || rg.h6 || A.all)) continue; id++; st.heroes++; rg._auId = id;
    if (rg.blob) { rg.blob.visible = false; rg._auBlob = true; }   // круглое пятно под героем больше не нужно
    for (const p of partsOf(rg)) { if (n >= N) break; let vis = true; for (let v = p.o; v; v = v.parent) if (!v.visible) { vis = false; break; } if (!vis) continue;
      const m = p.o.matrixWorld, s = Math.cbrt(Math.abs(m.determinant())), a = _a[0].copy(p.a).applyMatrix4(m), b = _a[1].copy(p.b).applyMatrix4(m), o = n * 4;
      A4[o] = a.x; A4[o + 1] = a.y; A4[o + 2] = a.z; A4[o + 3] = p.r * s * K.grow; B4[o] = b.x; B4[o + 1] = b.y; B4[o + 2] = b.z; B4[o + 3] = id;
      for (let i = 0; i < 3; i++) C3[n * 3 + i] = Math.pow(p.col[i], 1.15) * E[i]; n++; } }
  P[0] = n; P[1] = K.soft; P[2] = K.sky; P[3] = K.bounce; st.caps = n; A.stats = st; A.active = n > 0;
  if (A.active && sun.shadow) sun.shadow.camera.layers.disable(1);   // героев в карте теней нет — их тень теперь аура
};
})(typeof window !== 'undefined' ? window : globalThis);
