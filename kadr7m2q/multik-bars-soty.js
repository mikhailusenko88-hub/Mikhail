// БАРС · соты — трава «как в кино» из готовых ячеек-шестиугольников с прошитым светом.
// Мир «сшит из сот»: 4 образца ячейки (по ~700 травинок) повторяются по полю с поворотом на 60°, глазу швов не видно.
// Свет прошит «неоном»: каждая точка травинки знает, как глубоко она в траве (канал «глубина») — солнце и небо
// гаснут к корням сами (как в трассировке: тёмный низ, светлые кончики), в кадре это лишь «диммер» по высоте солнца.
// Тень героя, туман и тон кадра — как у всей сцены (обычные тени three.js).
(function (global) {
'use strict';
const S = global.BARSSoty = { on: true, TR: 0.42, NS: 4, stats: {} };
(global.BARS = global.BARS || {}).soty = S;
let THREE = null;
const SQ3 = Math.sqrt(3);
function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const inHex = (x, z, R) => { const ax = Math.abs(x), az = Math.abs(z); return az <= R * SQ3 / 2 && ax * SQ3 / 2 + az * .5 <= R * SQ3 / 2; };   // шестиугольник «остриём» по x

// ---------- образец ячейки: травинки, цвета, «глубина в траве» ----------
const cache = {};
function sampleGeo(si, green, dens) {
  const key = si + '|' + green + '|' + dens; if (cache[key]) return cache[key];
  const R = S.TR * 1.06, area = 3 * SQ3 / 2 * R * R, n = Math.round(area * dens), r = rng(7919 * (si + 1) + 17);
  const base = new THREE.Color(green), dark = base.clone().multiplyScalar(.7), light = base.clone().lerp(new THREE.Color('#d8e86a'), .25), straw = new THREE.Color('#c8c070');
  const SEG = 4, VB = (SEG + 1) * 2, IB = SEG * 6;
  const P = new Float32Array(n * VB * 3), N = new Float32Array(n * VB * 3), C = new Float32Array(n * VB * 3), RT = new Float32Array(n * VB * 3), BK = new Float32Array(n * VB * 2), I = new Uint32Array(n * IB);
  const blades = []; while (blades.length < n) { const x = (r() * 2 - 1) * R, z = (r() * 2 - 1) * R; if (!inHex(x, z, R)) continue; blades.push([x, z]); }
  const q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), nn = new THREE.Vector3(); let top = 0; const hs = [];
  for (let b = 0; b < n; b++) { const h = (.042 + r() * .042) * (r() < .04 ? 1.6 : 1); hs.push(h); top += h; }
  top = top / n * 1.05;   // верх «кроны» травы
  for (let b = 0; b < n; b++) {
    const [x, z] = blades[b], h = hs[b], w = .009 + r() * .007; e.set((r() - .5) * .35, r() * Math.PI * 2, (r() - .5) * .35); q.setFromEuler(e);
    const k = r(); const c = (k < .5 ? dark : base).clone().lerp(light, r() * .6); if (r() < .05) c.lerp(straw, .35);
    const clump = .82 + .36 * r();   // пятна гуще/реже — «глубина» чуть разная у соседних травинок
    for (let i = 0; i <= SEG; i++) { const y = i / SEG, hw = i === SEG ? 0 : .5 * Math.pow(1 - y, .75), zz = .22 * y * y, cc = .38 + .72 * y;
      for (let sd = 0; sd < 2; sd++) { const o = b * VB + i * 2 + sd;
        v.set(sd ? hw : -hw, y, zz).multiply(nn.set(w, h, h)).applyQuaternion(q); P[o * 3] = v.x + x; P[o * 3 + 1] = v.y; P[o * 3 + 2] = v.z + z;
        nn.set(0, 1, .25).normalize().applyQuaternion(q); N[o * 3] = nn.x; N[o * 3 + 1] = nn.y; N[o * 3 + 2] = nn.z;
        C[o * 3] = c.r * cc * .95; C[o * 3 + 1] = c.g * cc; C[o * 3 + 2] = c.b * cc * .9;
        RT[o * 3] = x; RT[o * 3 + 1] = z; RT[o * 3 + 2] = h;
        const depth = (Math.max(0, h - v.y) * .85 + Math.max(0, top - h) * .5) * clump; BK[o * 2] = depth; BK[o * 2 + 1] = r(); } }   // кончики открыты солнцу, низ — в глубине травы
    for (let i = 0; i < SEG; i++) { const a = b * VB + i * 2, o = b * IB + i * 6; I[o] = a; I[o + 1] = a + 1; I[o + 2] = a + 2; I[o + 3] = a + 1; I[o + 4] = a + 3; I[o + 5] = a + 2; }
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.BufferAttribute(N, 3)); g.setAttribute('color', new THREE.BufferAttribute(C, 3));
  g.setAttribute('aRoot', new THREE.BufferAttribute(RT, 3)); g.setAttribute('aBake', new THREE.BufferAttribute(BK, 2)); g.setIndex(new THREE.BufferAttribute(I, 1));
  g.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, .05, 0), R + .2); g.userData.n = n; g.userData.IB = IB;
  return (cache[key] = g);
}
// ярус густоты: тот же образец, но только первые травинки (порядок случайный) — общие буферы, своя длина
function tierGeo(g, k) { const t = new THREE.BufferGeometry(); for (const a in g.attributes) t.setAttribute(a, g.attributes[a]); t.setIndex(g.index); t.setDrawRange(0, Math.round(g.userData.n * k) * g.userData.IB); t.boundingSphere = g.boundingSphere; return t; }

// ---------- материал: обычный «стандартный» (тени, туман, тон), плюс диммеры прошитого света ----------
function soMat(windU, maskTex, maskB, wide, dapK) {
  const m = new THREE.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, side: THREE.DoubleSide, roughness: .85, metalness: 0, envMapIntensity: .5 });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uWind = windU; sh.uniforms.uMask = { value: maskTex }; sh.uniforms.uMaskB = { value: maskB }; sh.uniforms.uWide = { value: wide }; sh.uniforms.uSunY = S.sunY; sh.uniforms.uKt = S.kt; sh.uniforms.uDew = S.dew; sh.uniforms.uDapK = { value: dapK || 0 };
    sh.vertexShader = 'uniform float uWind, uWide, uSunY, uKt, uDapK; uniform sampler2D uMask; uniform vec4 uMaskB; attribute vec3 aRoot; attribute vec2 aBake; varying float vSun, vSky, vTip, vFleck; varying vec3 vWp;\n' + NOISE + sh.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>
  vec3 cp = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]); mat3 cr = mat3(instanceMatrix);
  vec2 rw = cp.xz + (cr * vec3(aRoot.x, 0.0, aRoot.y)).xz;               // корень травинки в мире
  float ok = texture2D(uMask, (rw - uMaskB.xy) / uMaskB.zw).r;           // дорожки, вещи, края луга — травы нет
  bool row = (abs(rw.y) < .55 || abs(rw.y + .9) < .4) && abs(rw.x) < 6.0;  // там, где стоят герои, — газон пониже
  float hk = row ? .62 : 1.0;
  vec2 lo = transformed.xz - aRoot.xy; transformed.xz = aRoot.xy + lo * uWide; transformed.y *= hk;
  float yu = transformed.y / max(aRoot.z * hk, 1e-3);
  float ww = sin(uWind * 1.6 + rw.x * .8 + rw.y * .5) * .6 + sin(uWind * 2.9 + rw.x * 2.1 - rw.y) * .3;
  transformed.z += ww * .28 * yu * yu * aRoot.z * hk;
  if (ok < .5) transformed = vec3(aRoot.x, -2.0, aRoot.y);
  float d = aBake.x * hk;                                                // «глубина в траве» — прошита в образце
  vSun = .08 + .92 * exp(-uKt * 21.0 * d / max(.22, uSunY)) * (.9 + .2 * aBake.y);   // солнце гаснет к корням тем быстрее, чем ниже солнце
  vSky = .42 + .58 * exp(-uKt * 16.0 * d);                               // небо — мягче
  vTip = yu; vWp = (modelMatrix * instanceMatrix * vec4(transformed, 1.0)).xyz;
  vFleck = 0.0; if (uDapK > 0.0) {   // зайчики (неон v4.3): окна солнца в листве плывут по ветру
    float ph = .35 * rw.x + .22 * rw.y, w = sin(1.7 * uWind + ph) + .5 * sin(3.1 * uWind + 1.3 * ph), w2 = sin(2.3 * uWind + .7 * ph + 1.1);
    vec2 q = rw * 1.2 + vec2(.6 * w + .2 * w2, .45 * w - .3 * w2) * .35;
    float f1 = vnz(vec3(q, .45 * uWind)), f2 = vnz(vec3(q * 2.7 + 3.1, .8 * uWind + 5.0));
    vFleck = smoothstep(.56, .70, f1) * smoothstep(.40, .62, f2) * min(uDapK, 1.5) * .75; }`);
    sh.fragmentShader = 'uniform float uDew; varying float vSun, vSky, vTip, vFleck; varying vec3 vWp;\n' + sh.fragmentShader.replace('#include <lights_fragment_end>', `#include <lights_fragment_end>
  reflectedLight.directDiffuse *= vSun; reflectedLight.directSpecular *= vSun; reflectedLight.indirectDiffuse *= vSky * (1.0 + .3 * vTip); reflectedLight.indirectSpecular *= vSky;
  #if NUM_DIR_LIGHTS > 0
  { float shf = 1.0;
    #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
    { DirectionalLightShadow dls = directionalLightShadows[ 0 ]; shf = receiveShadow ? getShadow( directionalShadowMap[ 0 ], dls.shadowMapSize, dls.shadowIntensity, dls.shadowBias, dls.shadowRadius, vDirectionalShadowCoord[ 0 ] ) : 1.0; }
    #endif
    float shW = shf, auV = 1.0;   // тень мира (кроны) — для зайчиков; дальше в shf добавляется тень героев (аура)
    #ifdef BARS_AURA
    auV = auSunV; shf *= auV;
    #endif
    vec3 Ls = directionalLights[0].direction, Lc = directionalLights[0].color; float bk = max(0.0, -dot(Ls, geometryViewDir));
    reflectedLight.directDiffuse += diffuseColor.rgb * Lc * shf * vSun * (.12 + .55 * bk * bk) * (.35 + .65 * vTip) * vec3(.85, 1.0, .55);   // просвет: солнце за травинкой — она светится зелёным
    reflectedLight.directDiffuse += diffuseColor.rgb * Lc * vFleck * (1.0 - shW) * auV * (.45 + .55 * vSun);                                // зайчики в тени крон (герой их заслоняет)
    if (uDew > 0.0 && vTip > .55) { vec3 cell = floor(vWp * 420.0); float hr = fract(sin(dot(cell, vec3(12.9898, 78.233, 37.719))) * 43758.5453);   // роса на кончиках
      if (hr > .975) { float dr = length(vWp - (cell + .5) / 420.0) * 420.0; float drop = 1.0 - smoothstep(.25, .5, dr); vec3 rf = reflect(-Ls, normal); float nv = abs(dot(normal, geometryViewDir));
        float gl = pow(max(dot(rf, geometryViewDir), 0.0), 60.0) + .6 * pow(max(dot(-Ls, geometryViewDir), 0.0), 8.0) * (1.0 - nv); reflectedLight.directSpecular += Lc * vec3(1.0, .98, .9) * gl * drop * uDew * .9 * vTip * shf * vSun; } } }
  #endif`).replace('#include <dithering_fragment>', '#include <dithering_fragment>\n  { if (any(equal(floatBitsToUint(gl_FragColor) & uvec4(0x7f800000u), uvec4(0x7f800000u)))) gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0); }');   // без NaN (iPhone)
  };
  m.customProgramCacheKey = () => 'bars-soty'; return m;
}
S.sunY = { value: .6 }; S.kt = { value: 1 }; S.dew = { value: 1 };
const NOISE = 'float hz3(vec3 p) { p = fract(p * .3183099 + .1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }\n' +
  'float vnz(vec3 x) { vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f); return mix(mix(mix(hz3(i), hz3(i + vec3(1, 0, 0)), f.x), mix(hz3(i + vec3(0, 1, 0)), hz3(i + vec3(1, 1, 0)), f.x), f.y), mix(mix(hz3(i + vec3(0, 0, 1)), hz3(i + vec3(1, 0, 1)), f.x), mix(hz3(i + vec3(0, 1, 1)), hz3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }\n';

// ---------- луг из сот ----------
S.grassField = function (T, g, r0, green, skip, opts, ctx) {
  THREE = T; opts = opts || {}; const t0 = performance.now();
  // маска «где трава»: та же полоса, что у прежнего луга (шире вдаль), минус дорожки и вещи
  const X0 = -15, Z0 = -7.6, W = 30, H = 13.8, MW = 384, MH = 192, M = new Uint8Array(MW * MH);
  for (let j = 0; j < MH; j++) { const z = Z0 + (j + .5) / MH * H; if (z < -7 || z > 5.78) continue; const half = 3 + (5.5 - z) * .78;
    for (let i = 0; i < MW; i++) { const x = X0 + (i + .5) / MW * W; if (Math.abs(x) > half) continue; if (skip && skip(x, z)) continue; M[j * MW + i] = 255; } }
  const mt = new THREE.DataTexture(M, MW, MH, THREE.RedFormat, THREE.UnsignedByteType); mt.magFilter = mt.minFilter = THREE.NearestFilter; mt.needsUpdate = true;
  const maskB = new THREE.Vector4(X0, Z0, W, H);
  // ячейки по шестиугольной сетке: ярус по дальности (как раньше: 1500 / 850 / 420 травинок на м²)
  const R = S.TR, dx = 1.5 * R, dz = SQ3 * R, tiers = [[-1.5, 99, 1, 1], [-4, -1.5, .57, 1.18], [-99, -4, .29, 1.55]];
  const cells = tiers.map(() => []); const rr = rng(1234 + Math.round((r0 ? r0() : .5) * 1e6));
  for (let ix = -Math.ceil(16 / dx); ix <= Math.ceil(16 / dx); ix++) for (let iz = -Math.ceil(8 / dz) - 1; iz <= Math.ceil(8 / dz) + 1; iz++) {
    const x = ix * dx, z = iz * dz + (ix & 1 ? dz / 2 : 0); if (z < -7.4 || z > 6.25) continue; const half = 3 + (5.5 - z) * .78; if (Math.abs(x) > half + R) continue;
    // есть ли в ячейке хоть одна точка травы
    let any = false; for (let a = 0; a < 13 && !any; a++) { const ang = (a - 1) * Math.PI / 6, rr2 = a ? (a & 1 ? .95 : .8) * R : 0; const px = x + Math.cos(ang) * rr2, pz = z + Math.sin(ang) * rr2; const mi = Math.floor((px - X0) / W * MW), mj = Math.floor((pz - Z0) / H * MH); if (mi >= 0 && mj >= 0 && mi < MW && mj < MH && M[mj * MW + mi]) any = true; }
    if (!any) continue; const t = z >= -1.5 ? 0 : z >= -4 ? 1 : 2; cells[t].push([x, z, Math.floor(rr() * S.NS), Math.floor(rr() * 6)]); }
  const grp = new THREE.Group(); grp.name = 'bars-soty'; const mats = {}; let nb = 0, nc = 0;
  const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _s = new THREE.Vector3(1, 1, 1), up = new THREE.Vector3(0, 1, 0);
  tiers.forEach(([, , k, wide], t) => { for (let si = 0; si < S.NS; si++) { const list = cells[t].filter(c => c[2] === si); if (!list.length) continue;
      const geo = tierGeo(sampleGeo(si, green, 1500), k); const mat = mats[t] || (mats[t] = soMat(ctx.windU, mt, maskB, wide, opts.forest ? 1.0 : 0));
      const im = new THREE.InstancedMesh(geo, mat, list.length); im.castShadow = false; im.receiveShadow = true; im.frustumCulled = false; im.userData.keep = true; im.userData.soty = true;
      list.forEach(([x, z, , rot], i) => { _q.setFromAxisAngle(up, rot * Math.PI / 3); _p.set(x, 0, z); _m.compose(_p, _q, _s); im.setMatrixAt(i, _m); });
      im.instanceMatrix.needsUpdate = true; grp.add(im); nc += list.length; nb += list.length * Math.round(geo.attributes.aRoot.count / 10 * k); } });
  g.add(grp); S.stats = { cells: nc, blades: nb, ms: Math.round(performance.now() - t0) };
  return grp;
};
// ---------- налёт на мир (неон v4.1): мох, камни, стволы — прозрачные оболочки «молекул», светятся, когда сквозь них идёт свет ----------
S.naletOn = true;
S.nalet = function (T, mesh, o) {
  THREE = T; if (!S.naletOn || !mesh || !mesh.geometry || !mesh.geometry.attributes.normal) return; o = o || {}; mesh.userData.noMerge = true; /* склейка неподвижных деталей забрала бы оболочки */ const n = o.n || 3, base = mesh.material || {};
  for (let i = 0; i < n; i++) { const t = (i + 1) / n;
    const m = new THREE.MeshStandardMaterial({ color: base.color ? base.color.clone() : 0xffffff, map: base.map || null, roughness: 1, metalness: 0, transparent: true, depthWrite: false,
      blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor });
    m.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, { uT: { value: t }, uH: { value: (o.h || .02) * t }, uFreq: { value: o.freq || 220 }, uFar: { value: o.far || 14 }, uFuzz: { value: new THREE.Vector3(...(o.fuzz || [1, 1.1, .8])) }, uRimK: { value: o.rimK == null ? .8 : o.rimK }, uTopY: { value: o.topY == null ? 1e4 : o.topY }, uUp: { value: o.up ? 1 : 0 } });
      sh.vertexShader = 'uniform float uH; varying vec3 vWp, vWn;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n  transformed += normalize(objectNormal) * uH; vWp = (modelMatrix * vec4(transformed, 1.0)).xyz; vWn = normalize(mat3(modelMatrix) * objectNormal);');
      sh.fragmentShader = 'uniform float uT, uFreq, uFar, uRimK, uTopY, uUp; uniform vec3 uFuzz; varying vec3 vWp, vWn;\n' + NOISE + sh.fragmentShader.replace('#include <opaque_fragment>', `
  { vec3 nn = normal, V = geometryViewDir; if (dot(nn, V) < 0.0) nn = -nn; float nv = max(dot(nn, V), 0.0);
    float df = 1.0 - smoothstep(uFar * .6, uFar, length(vViewPosition)); float mm = vnz(vWp * uFreq) * .65 + vnz(vWp * uFreq * 3.1) * .35;
    float cover = smoothstep(uT - .22, uT + .06, mm) * df * (1.0 - smoothstep(uTopY - .8, uTopY, vWp.y)) * (uUp > .5 ? smoothstep(.05, .55, vWn.y) : 1.0); if (cover < .02) discard;
    vec3 alb = diffuseColor.rgb * uFuzz; vec3 col = vec3(0.0); float rim = pow(1.0 - nv, 1.4);
    #if NUM_DIR_LIGHTS > 0
    { float shf = 1.0;
      #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
      { DirectionalLightShadow dls = directionalLightShadows[ 0 ]; shf = receiveShadow ? getShadow( directionalShadowMap[ 0 ], dls.shadowMapSize, dls.shadowIntensity, dls.shadowBias, dls.shadowRadius, vDirectionalShadowCoord[ 0 ] ) : 1.0; }
      #endif
      vec3 Ls = directionalLights[0].direction, Lc = directionalLights[0].color; float ndl = dot(nn, Ls), back = clamp(dot(-Ls, V), 0.0, 1.0);
      float through = rim * (.3 + .7 * back) * (.3 + .7 * uT) * uRimK;
      col += Lc * shf * (min(alb, vec3(.7)) * vec3(1.1, .95, .6) + vec3(.05, .04, .02)) * through * 1.8 + Lc * shf * alb * clamp((ndl + .9) / 1.9, 0.0, 1.0) * .12 * uT; }
    #endif
    #if NUM_HEMI_LIGHTS > 0
    col += alb * hemisphereLights[0].skyColor * .15 * uT;
    #endif
    float a = cover * (.04 + .2 * rim * uRimK) * (.4 + .6 * uT); gl_FragColor = vec4(col * cover, a);
    if (any(equal(floatBitsToUint(gl_FragColor) & uvec4(0x7f800000u), uvec4(0x7f800000u)))) discard; }`);
    };
    m.customProgramCacheKey = () => 'bars-nalet';
    const c = new THREE.Mesh(mesh.geometry, m); c.castShadow = false; c.receiveShadow = true; c.renderOrder = 5 + i; c.userData.nalet = true; c.userData.noMerge = true; c.frustumCulled = mesh.frustumCulled; mesh.add(c); }
};
// высота солнца места (для «диммера»): ставит сцена перед кадром
S.setSun = function (sun) { if (!sun) return; const d = sun.position.clone().sub(sun.target.position).normalize(); S.sunY.value = Math.max(.05, d.y); };
})(typeof window !== 'undefined' ? window : globalThis);
