// «Кисть» 2: Барсик из БАРС (свет каждого волоска посчитан заранее трассировщиком), но шерсть не «лепится» волосками —
// каждый кадр она заново рисуется мазками: мазок кисти шириной 1,5–3 пикселя, число мазков под камеру, цвет мазка —
// из того же готового света (солнце, небо, контровой, блеск шерсти). Кожа, глаза, веки, рот, «налёт» — как в приложении.
(function () {
'use strict';
const K2 = window.KIST2 = { t: {}, stats: {}, mode: 'strokes' };
const now = () => performance.now();
function rng32(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---------- мазки шерсти с готовым светом ----------
const STROKE_VS = `
uniform sampler2D uPos; uniform sampler2D uBake; uniform sampler2D uAttr; uniform sampler2D uNrm;
uniform int uN; uniform float uJit, uSeed, uSeedA, uCov, uWmin, uWmax, uWk, uBias, uAlpha, uLenCap, uNdvMin; uniform vec2 uView;
out vec3 vP; out vec3 vT; out float vt; out vec3 vB0; out vec3 vB1; out vec3 vAlb; flat out int vKind; out vec2 vUV; out float vA; out vec3 vDbg;
ivec2 ti(int i) { return ivec2(i & 2047, i >> 11); }
float h1(float n) { return fract(sin(n * 12.9898 + 4.1414) * 43758.5453); }
void main() {
  int vid = gl_VertexID; int c = vid % 6; int q = vid / 6; int seg = q & 1; int sid = q >> 1; int m = sid / uN; int s = sid - m * uN; float fm = float(m);
  vec4 a0 = texelFetch(uAttr, ti(s * 3), 0), a1 = texelFetch(uAttr, ti(s * 3 + 1), 0), a2 = texelFetch(uAttr, ti(s * 3 + 2), 0);
  vec4 wx = vec4(a2.x * 255.0, a2.y * 255.0, a2.z, a2.w * 255.0); wx.x = (wx.x > 127.5 ? wx.x - 256.0 : wx.x) / 127.0; wx.y = (wx.y > 127.5 ? wx.y - 256.0 : wx.y) / 127.0; wx.w = (wx.w > 127.5 ? wx.w - 256.0 : wx.w) / 127.0;
  float wh = a1.x, ts = a1.y > 0.999 ? -1.0 : a1.y * 255.0 / 254.0, we = a1.z * 255.0; we = (we > 127.5 ? we - 256.0 : we) / 127.0; float wb = a1.w;
  vec4 r0 = texelFetch(uPos, ti(s * 5), 0); int kind = int(texelFetch(uPos, ti(s * 5 + 1), 0).w + 0.5); bool line = kind >= 200;
  float tr = (kind == 0 || kind == 5 || kind == 6 || kind == 7) ? uTrim : 1.0;
  vec3 m0 = r0.xyz, m2 = r0.xyz + (texelFetch(uPos, ti(s * 5 + 2), 0).xyz - r0.xyz) * tr, m4 = r0.xyz + (texelFetch(uPos, ti(s * 5 + 4), 0).xyz - r0.xyz) * tr;
  float rank = h1(float(s) * .6131 + uSeed * 7.193);
  if ((m > 0 || uSeed > 0.0) && !line) {   // вблизи одно зерно даёт несколько мазков рядом — кисть мельчит; в каждом проходе накопления мазки ложатся заново
    vec3 d = normalize(m4 - m0 + 1e-7), a = normalize(cross(d, abs(d.z) < .9 ? vec3(0, 0, 1) : vec3(1, 0, 0))), b = cross(d, a); float amp = m > 0 ? 1.1 : uJit;
    vec3 off = (a * (h1(float(s) * 1.7 + fm * 3.1 + uSeed * 5.31) - .5) + b * (h1(float(s) * 2.3 + fm * 5.7 + uSeed * 9.13) - .5)) * sqrt(uSeedA) * amp; m0 += off; m2 += off; m4 += off; if (m > 0) rank = h1(float(s) * .913 + fm * 7.77 + uSeed * 3.71); }
  vec3 p0 = toW(poseP(m0, wh, ts, we, wb, wx)), p2 = toW(poseP(m2, wh, ts, we, wb, wx)), p4 = toW(poseP(m4, wh, ts, we, wb, wx));
  vec4 v0 = viewMatrix * vec4(p0, 1.0), v2 = viewMatrix * vec4(p2, 1.0), v4 = viewMatrix * vec4(p4, 1.0); float z = -v0.z;
  vec4 nr = texelFetch(uNrm, ti(s), 0); vec3 nW = toWN(poseN(nr.xyz * 2.0 - 1.0, wh, wx)); float ndv = nr.w > .5 ? dot(nW, normalize(cameraPosition - p0)) : .5;
  v0.xyz += normalize(-v0.xyz) * uBias; v2.xyz += normalize(-v2.xyz) * uBias; v4.xyz += normalize(-v4.xyz) * uBias;
  vec4 c0 = projectionMatrix * v0, c2 = projectionMatrix * v2, c4 = projectionMatrix * v4;
  if (z < .03 || c0.w <= 0.0 || c4.w <= 0.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec2 s0 = c0.xy / c0.w * uView * .5, s2 = c2.xy / c2.w * uView * .5, s4 = c4.xy / c4.w * uView * .5;
  float F = uView.y * .5 * projectionMatrix[1][1];
  float lpx = length(s2 - s0) + length(s4 - s2);
  float w = clamp(r0.w * uScale * uWk * F / z, uWmin, uWmax); if (line) w = clamp(r0.w * uScale * 2.0 * F / z, 1.0, 5.0);
  float apx = uSeedA * (F / z) * (F / z) * max(abs(ndv), .3);
  float p = uCov * apx / (max(min(lpx, uLenCap * uView.y / 1080.0), w) * w);   // сколько мазков нужно этому месту (длинные пряди и кисточки не прореживаем)
  if (kind == 4 || kind == 8) p = max(p, 1.0);
  bool keep = line ? m == 0 : ((fm + rank) < p && ndv > uNdvMin);   // широкие мазки — только внутри формы, край рисуют тонкие   // мазки с обратной стороны головы не кладём
  if (!keep) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec2 A = seg == 0 ? s0 : s2, B = seg == 0 ? s2 : s4; vec4 CA = seg == 0 ? c0 : c2, CB = seg == 0 ? c2 : c4;
  vec2 dd = B - A; float dl = length(dd); vec2 dir = dl > 1e-4 ? dd / dl : vec2(1.0, 0.0); vec2 nrm2 = vec2(-dir.y, dir.x);
  int e = int[6](0, 1, 0, 0, 1, 1)[c]; float sd = float[6](-1.0, -1.0, 1.0, 1.0, -1.0, 1.0)[c];
  float t = seg == 0 ? (e == 0 ? 0.0 : .5) : (e == 0 ? .5 : 1.0); vec2 P = e == 0 ? A : B; vec4 CP = e == 0 ? CA : CB;
  float hw = line ? w * .5 : w * (1.0 - .7 * t * t) * .5; float wt = hw + .7;
  float ext = (seg == 0 && e == 0) ? -.4 : ((seg == 1 && e == 1) ? .4 : 0.0);
  P += nrm2 * sd * wt + dir * ext; gl_Position = vec4(P / (uView * .5), CP.z / CP.w, 1.0);
  vUV = vec2(sd * wt / max(hw, .01), 0.0);
  // то же, что у волоска в приложении: точка, направление, готовый свет по длине, цвет с тёмным корнем
  vP = t < .25 ? p0 : (t < .75 ? p2 : p4); vT = normalize(seg == 0 ? p2 - p0 : p4 - p2); vt = t;
  float tc = line ? t : .42 + .58 * t;   // видимая часть мазка — верх шерсти
  vec3 cc[6]; for (int j = 0; j < 6; j++) { vec3 b = texelFetch(uBake, ti(s * 6 + j), 0).rgb; float u = clamp((tc - 0.5) * 4.0, 0.0, 2.0); float v = u < 1.0 ? mix(b.x, b.y, u) : mix(b.y, b.z, u - 1.0); if (tc < 0.5) v = b.x * (0.45 + 1.1 * tc); cc[j] = vec3(v); }
  vB0 = vec3(cc[0].x, cc[1].x, cc[2].x); vB1 = vec3(cc[3].x, cc[4].x, cc[5].x);
  vec3 alb = a0.rgb * a0.rgb; if (kind < 200) alb *= mix(vec3(1.0), kind == 12 ? vec3(0.8) : mix(vec3(0.62, 0.55, 0.5), vec3(0.84, 0.8, 0.77), uSoft), (1.0 - tc) * (1.0 - tc));
  vAlb = alb; vKind = kind; vA = line ? 1.0 : uAlpha * mix(.45, 1.0, smoothstep(-.05, .4, ndv)); vt = tc;   // на краю силуэта мазок прозрачнее — край пушистый, а не тёмный
  vDbg = vec3(h1(float(s) * .37 + fm), h1(float(s) * .71 + fm * 2.0), h1(float(s) * 1.13 + fm * 3.0)) * .9;
}`;

// ---------- лес и трава (мазки, как в первой пробе) ----------
const HEAD = `precision highp float; precision highp int; uniform mat4 projectionMatrix, viewMatrix, modelMatrix;
`;
const PCOMMON = `
const vec3 KEY = vec3(-0.46, 0.62, 0.64);
uniform vec3 uFogC; uniform float uFogK; uniform float uSat;
uniform sampler2D uShT; uniform mat4 uShM; uniform float uShOn, uShR, uShSeed; uniform vec3 uShC, uShD;
float shadowAt(vec3 wp) {   // ТЕНЬ МАЗКАМИ: мазки Барсика, нарисованные со стороны солнца, — сколько света они забирают
  if (uShOn < .5) return 0.0;
  vec4 c = uShM * vec4(wp, 1.0); vec2 uv = c.xy / c.w * .5 + .5;
  if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return 0.0;
  float a = 0.0, r0 = uShSeed * 6.2832;
  for (int i = 0; i < 6; i++) { float an = r0 + float(i) * 2.39996, rr = uShR * sqrt((float(i) + .5) / 6.0); a += textureLod(uShT, uv + vec2(cos(an), sin(an)) * rr, 0.0).a; }
  return clamp(a / 6.0, 0.0, 1.0) * smoothstep(.24, .06, dot(wp - uShC, uShD)); }   // со стороны солнца от Барсика тени нет
vec3 shTint(float o) { return mix(vec3(1.0), vec3(.34, .39, .5), o); }   // в тени остаётся голубоватое небо
vec3 painter(vec3 alb, vec3 nv, vec3 vv, float ao) {
  float k = clamp((dot(nv, normalize(KEY)) + .18) / 1.18, 0.0, 1.0); k = k * k * (3.0 - 2.0 * k);
  vec3 c = alb * mix(vec3(.47, .5, .6), vec3(1.22, 1.12, 1.0), k) * mix(.5, 1.0, ao);
  float ndv = clamp(dot(nv, vv), 0.0, 1.0); c += alb * pow(1.0 - ndv, 3.0) * .25 * ao; return c; }
vec3 fogged(vec3 c, vec3 wp) { float dd = max(-wp.z - 1.6, 0.0) + max(length(wp.xz) - 3.5, 0.0) * .3; return mix(c, uFogC, 1.0 - exp(-dd * uFogK)); }
`;
const GRASS_VS = HEAD + `
uniform highp sampler2D uG; uniform vec3 uGrassK; uniform int uN; uniform float uSeed, uSeedA, uCov, uWmin, uWmax, uTime; uniform vec2 uView; uniform vec3 uHero; uniform int uDbg;
out vec3 vCol; out vec2 vUV; out float vT; out float vA;
${PCOMMON}
ivec2 tx(int i) { return ivec2(i & 4095, i >> 12); }
float h1(float n) { return fract(sin(n * 12.9898 + 1.234) * 43758.5453); }
void main() {
  int vid = gl_VertexID; int c = vid % 6; int q = vid / 6; int seg = q & 1; int sid = q >> 1; int m = sid / uN; int s = sid - m * uN; float fm = float(m);
  vec4 g0 = texelFetch(uG, tx(s * 2), 0), g1 = texelFetch(uG, tx(s * 2 + 1), 0);
  vec3 b = g0.xyz; float h = g0.w; vec2 ln = g1.xy; float rank = g1.z, cv = g1.w;
  if (m > 0 || uSeed > 0.0) { float amp = m > 0 ? 1.2 : .6; vec2 j = vec2(h1(float(s) + fm * 3.3 + uSeed * 4.7) - .5, h1(float(s) * 1.9 + fm * 7.1 + uSeed * 8.3) - .5) * sqrt(uSeedA) * amp; b.xz += j; if (m > 0) { rank = h1(float(s) * .77 + fm * 2.9 + uSeed * 2.3); h *= .8 + .4 * h1(float(s) * 3.1 + fm); } }
  float sway = sin(uTime * 1.3 + b.x * 2.0 + b.z * 1.3) * .012;
  vec3 mi = b + vec3(ln.x * .25 * h + sway * .3, h * .55, ln.y * .25 * h), tp = b + vec3(ln.x * h + sway, h * .95, ln.y * h);
  vec4 rv = viewMatrix * vec4(b, 1.0), mv = viewMatrix * vec4(mi, 1.0), tv = viewMatrix * vec4(tp, 1.0); float z = -rv.z;
  vec4 c0 = projectionMatrix * rv, c1 = projectionMatrix * mv, c2 = projectionMatrix * tv;
  if (z < .05 || c0.w <= 0.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec2 s0 = c0.xy / c0.w * uView * .5, s1 = c1.xy / c1.w * uView * .5, s2 = c2.xy / c2.w * uView * .5;
  float F = uView.y * .5 * projectionMatrix[1][1];
  float lpx = length(s1 - s0) + length(s2 - s1); float w = clamp(.0028 * F / z, uWmin, uWmax);
  float gnd = abs(dot(normalize(mat3(viewMatrix) * vec3(0, 1, 0)), normalize(-rv.xyz)));
  float p = uCov * uSeedA * (F / z) * (F / z) * max(gnd, .12) / (max(lpx, w) * w);
  if ((fm + rank) >= p || abs(s0.x) > uView.x * .6 || abs(s0.y) > uView.y * .7) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec2 A = seg == 0 ? s0 : s1, B = seg == 0 ? s1 : s2; vec4 CA = seg == 0 ? c0 : c1, CB = seg == 0 ? c1 : c2; float tA = seg == 0 ? 0.0 : .5, tB = seg == 0 ? .5 : 1.0;
  vec2 d = B - A; float dl = length(d); vec2 dir = dl > 1e-4 ? d / dl : vec2(0, 1); vec2 nrm = vec2(-dir.y, dir.x);
  int e = int[6](0, 1, 0, 0, 1, 1)[c]; float sd = float[6](-1.0, -1.0, 1.0, 1.0, -1.0, 1.0)[c];
  float t = e == 0 ? tA : tB; vec2 P = e == 0 ? A : B; vec4 CP = e == 0 ? CA : CB; float wt = w * (1.0 - .8 * t) * .5 + .6;
  vec3 wv = t < .25 ? b : (t < .75 ? mi : tp); float occ = shadowAt(wv);
  P += nrm * sd * wt; gl_Position = vec4(P / (uView * .5), CP.z / CP.w, 1.0);
  vUV = vec2(sd * wt / max(w * (1.0 - .8 * t) * .5, .01), 0.0); vT = t;
  vec3 base = mix(vec3(.035, .09, .025), vec3(.06, .15, .04), cv), tip = mix(vec3(.38, .62, .19), vec3(.52, .76, .27), cv);
  float br = .7 + .55 * h1(float(s) * 2.71 + fm);                        // травинки разной яркости
  float hd = length(b.xz - uHero.xz - vec2(.05, -.03)); float contact = mix(.35, 1.0, smoothstep(.1, .55, hd));
  vCol = fogged(mix(base, tip, pow(t, .65)) * br * contact * shTint(occ) * uGrassK, b); vA = .95;
  if (uDbg == 1) vCol = vec3(h1(float(s) * .37), h1(float(s) * .71), h1(float(s) * 1.13)) * .9;
}`;
const GRASS_FS = `precision highp float;
in vec3 vCol; in vec2 vUV; in float vT; in float vA; out vec4 o;
void main() { float a = smoothstep(1.0, .35, abs(vUV.x)) * vA * smoothstep(0.0, .06, vT) * (1.0 - .5 * smoothstep(.55, 1.0, vT)); o = vec4(vCol * a, a); }`;
const MESH_VS = HEAD + `in vec3 position; in vec3 normal; out vec3 vN; out vec3 vV; out vec3 vP;
void main() { vec4 wp = modelMatrix * vec4(position, 1.0); vec4 vp = viewMatrix * wp; vN = normalize(mat3(viewMatrix) * mat3(modelMatrix) * normal); vV = normalize(-vp.xyz); vP = wp.xyz; gl_Position = projectionMatrix * vp; }`;
const MESH_FS = HEAD + `in vec3 vN; in vec3 vV; in vec3 vP; out vec4 o; uniform vec3 uAlb; uniform float uAo;
${PCOMMON}
void main() { vec3 n = normalize(vN); if (dot(n, vV) < 0.0) n = -n; vec3 sh = uShOn > .5 ? shTint(shadowAt(vP)) : vec3(1.0 - .55 * exp(-length(vP.xz) * 4.0) * step(vP.y, .01));   // тень Барсика (или старое пятно)
  o = vec4(fogged(painter(uAlb, n, vV, uAo) * sh, vP), 1.0); }`;
const BG_FS = `precision highp float; in vec2 vUv; out vec4 o; uniform vec3 uTop, uHor; void main() { o = vec4(mix(uHor, uTop, smoothstep(.35, 1.0, vUv.y)), 1.0); }`;
const QUAD_VS = `precision highp float; in vec3 position; out vec2 vUv; void main() { vUv = position.xy * .5 + .5; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const ADD_FS = `precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uT; void main() { o = texture(uT, vUv); }`;
const POST_FS = `precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uT; uniform float uExpo, uInv; uniform int uTone;
// AgX — «плёнка» Blender 4+ (по умолчанию с 4.0): яркое и насыщенное уходит к белому, рыжий в светах не кричит
vec3 agxC(vec3 x) { vec3 x2 = x * x, x4 = x2 * x2; return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + .4298 * x2 + .1191 * x - .00232; }
vec3 agx(vec3 c) {
  const mat3 S2R = mat3(vec3(.6274, .0691, .0164), vec3(.3293, .9195, .0880), vec3(.0433, .0113, .8956));
  const mat3 R2S = mat3(vec3(1.6605, -.1246, -.0182), vec3(-.5876, 1.1329, -.1006), vec3(-.0728, -.0083, 1.1187));
  const mat3 INS = mat3(vec3(.856627153315983, .137318972929847, .11189821299995), vec3(.0951212405381588, .761241990602591, .0767994186031903), vec3(.0482516061458583, .101439036467562, .811302368396859));
  const mat3 OUTS = mat3(vec3(1.1271005818144368, -.1413297634984383, -.14132976349843826), vec3(-.11060664309660323, 1.157823702216272, -.11060664309660294), vec3(-.016493938717834573, -.016493938717834257, 1.2519364065950405));
  c = INS * (S2R * c); c = clamp((log2(max(c, vec3(1e-10))) + 12.47393) / 16.499999, 0.0, 1.0); c = OUTS * agxC(c); c = pow(max(c, vec3(0.0)), vec3(2.2)); return clamp(R2S * c, 0.0, 1.0); }
vec3 neutral(vec3 color) { const float startCompression = 0.8 - 0.04; const float desaturation = 0.15;
  float x = min(color.r, min(color.g, color.b)); float offset = x < 0.08 ? x - 6.25 * x * x : 0.04; color -= offset;
  float peak = max(color.r, max(color.g, color.b)); if (peak < startCompression) return color;
  const float d = 1.0 - startCompression; float newPeak = 1.0 - d * d / (peak + d - startCompression); color *= newPeak / peak;
  float g = 1.0 - 1.0 / (desaturation * (peak - newPeak) + 1.0); return mix(color, newPeak * vec3(1, 1, 1), g); }
vec3 srgb(vec3 c) { return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - .055, step(.0031308, c)); }
void main() { vec3 c = texture(uT, vUv).rgb * uExpo * uInv; c = uTone == 1 ? agx(max(c, vec3(0.0))) : neutral(max(c, vec3(0.0))); vec2 d = vUv - .5; c *= 1.0 - .2 * dot(d, d) * 2.0; o = vec4(srgb(clamp(c, 0.0, 1.0)), 1.0); }`;

K2.boot = async function (THREE, canvas, opts) {
  opts = opts || {}; const t0 = now(); K2.THREE = THREE;
  const R = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' }); R.autoClear = false; K2.R = R;
  const MKB = window.MKBarsik; MKB.base = opts.base || './data/';
  if (K2.onProgress) K2.onProgress('load', 0);
  const ok = await MKB.load(); if (!ok) throw new Error('Барсик не загрузился: ' + MKB.error); K2.t.load = now() - t0;
  const scene = new THREE.Scene(); const cam = new THREE.PerspectiveCamera(30, 16 / 9, .05, 60); K2.cam = cam; K2.scene = scene;
  // «скелет» для модуля Барсика (в приложении его даёт multik-3d.js): голова, лапы, ноги, хвост
  const G = () => new THREE.Group();
  const rig = { P: { headY: MKB._k.HEAD_C }, pose: G(), root: G(), head: G(), arms: [G(), G()], legs: [G(), G()], ears: [], tail: G(), body: null, eyes: [], n: { seed: 3 }, scale: 1 };
  rig.arms[0].userData.side = -1; rig.arms[1].userData.side = 1; rig.legs[0].position.x = -1; rig.legs[1].position.x = 1;
  rig.arms.forEach((a, i) => { a.rotation.x = -0.39; a.rotation.z = (i ? 1 : -1) * 0.345; });
  rig.root.add(rig.pose); scene.add(rig.root);
  if (!MKB.attach(THREE, rig)) throw new Error('Барсик не прикрепился');
  const B = rig.bars; K2.rig = rig; K2.B = B; const D = MKB.D; const S = MKB._k.shared();
  // свет места: лес в дымке, мягкое солнце сверху-слева, небо, контровой
  const sun = new THREE.DirectionalLight(0xfff3e4, 2.3); sun.position.set(-1.6, 3.2, 2.2); sun.target.position.set(0, .5, 0);
  const rim = new THREE.DirectionalLight(0xffe6c8, 1.2); rim.position.set(1.4, 2.0, -2.5); rim.target.position.set(0, .5, 0);
  const hemi = new THREE.HemisphereLight(0xc8d6e0, 0x4a5a32, 1.25);
  K2.L = { sun, hemi, rim, fog: null, expo: 1.0, envI: .35 };
  // площадь кожи под шерстью — на неё приходится одно зерно мазка
  { const P = D.skin.P, I = D.skin.idx, M = D.skin.M; let a = 0; for (let t = 0; t < I.length; t += 3) { const i0 = I[t], i1 = I[t + 1], i2 = I[t + 2]; if (M[i0] >= 20) continue;
      const ux = P[i1 * 3] - P[i0 * 3], uy = P[i1 * 3 + 1] - P[i0 * 3 + 1], uz = P[i1 * 3 + 2] - P[i0 * 3 + 2], vx = P[i2 * 3] - P[i0 * 3], vy = P[i2 * 3 + 1] - P[i0 * 3 + 1], vz = P[i2 * 3 + 2] - P[i0 * 3 + 2];
      a += .5 * Math.hypot(uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx); } K2.furArea = a; }
  // нормаль кожи у корня каждого волоска (ближайшая вершина кожи) — чтобы не рисовать мазки с обратной стороны головы
  { const t1 = now(); const P = D.skin.P, N = D.skin.N, M = D.skin.M, cs = .012, grid = new Map(); const key = (x, y, z) => ((Math.floor(x / cs) * 73856093) ^ (Math.floor(y / cs) * 19349663) ^ (Math.floor(z / cs) * 83492791)) >>> 0;
    for (let i = 0; i < P.length / 3; i++) { if (M[i] >= 20) continue; const k = key(P[i * 3], P[i * 3 + 1], P[i * 3 + 2]); let a = grid.get(k); if (!a) grid.set(k, a = []); a.push(i); }
    const TW = D.TW, rows = Math.ceil(D.NS / TW), nt = new Uint8Array(TW * rows * 4); const pos = D.pos;
    for (let s = 0; s < D.NS; s++) { const x = pos[s * 20], y = pos[s * 20 + 1], z = pos[s * 20 + 2]; let best = -1, bd = 1e9;
      for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) { const a = grid.get(key(x + dx * cs, y + dy * cs, z + dz * cs)); if (!a) continue;
        for (const i of a) { const d = (P[i * 3] - x) ** 2 + (P[i * 3 + 1] - y) ** 2 + (P[i * 3 + 2] - z) ** 2; if (d < bd) { bd = d; best = i; } } }
      if (best < 0) { nt[s * 4 + 3] = 0; continue; } for (let c = 0; c < 3; c++) nt[s * 4 + c] = Math.round(N[best * 3 + c] * 127 + 128); nt[s * 4 + 3] = 255; }
    const tN = new THREE.DataTexture(nt, TW, rows, THREE.RGBAFormat, THREE.UnsignedByteType); tN.needsUpdate = true; tN.minFilter = tN.magFilter = THREE.NearestFilter; K2.tN = tN; K2._nt = nt; K2.t.norm = now() - t1; }
  // шейдер мазка = общие функции Барсика (поза, свет места, блеск шерсти) + мазок кисти
  const FS = MKB._k.FS_FUR.replace('flat in int vKind; out vec4 o;', 'flat in int vKind; in vec2 vUV; in float vA; in vec3 vDbg; uniform int uDbgS; out vec4 o;')
    .replace('flat in int vKind; in vec2 vUV;', 'flat in int vKind; uniform float uEdge; in vec2 vUV;')
    .replace('  o = outC(c, length(vP - cameraPosition));\n}', '  o = outC(c, length(vP - cameraPosition)); if (uDbgS == 1) o.rgb = vDbg;\n  float a = smoothstep(1.0, uEdge, abs(vUV.x)) * vA * (vKind >= 200 ? 1.0 : smoothstep(0.0, .06, vt) * (1.0 - .45 * smoothstep(.6, 1.0, vt)));\n  o = vec4(o.rgb * a, a);\n}');
  if (FS === MKB._k.FS_FUR || !FS.includes('vDbg')) throw new Error('шейдер мазка не собрался');
  const MMAX = 3; const NS = D.NS; K2.NS = NS; K2.MMAX = MMAX;
  const blend = { side: THREE.DoubleSide, transparent: true, depthWrite: false, blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor };
  // ПИРАМИДА МАЗКОВ: крупные мягкие мазки несут усреднённый готовый свет всех волосков под собой (как уменьшенная картинка),
  // средние — прядки, мелкие — сами волоски. Мягкость, как у сотен лучей Blender, но за один проход.
  const tex = (data, w, h, type) => { const t = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, type); t.minFilter = t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true; return t; };
  const mkLevel = (cell) => {
    const pos = D.pos, bake = D.bake, attr = D.attr, nt = K2._nt, map = new Map(), C = [];
    for (let s = 0; s < D.NS; s++) { const kind = pos[s * 20 + 7]; if (kind >= 200) continue;
      const key = Math.floor(pos[s * 20] / cell) + ',' + Math.floor(pos[s * 20 + 1] / cell) + ',' + Math.floor(pos[s * 20 + 2] / cell) + ',' + kind + ',' + (attr[s * 12 + 4] > 127 ? 1 : 0) + ',' + attr[s * 12 + 9] + ',' + (attr[s * 12 + 5] > 254 ? 1 : 0);
      let c = map.get(key); if (!c) { c = { rep: s, n: 0, p: new Float64Array(15), b: new Float64Array(18), a: [0, 0, 0], nn: [0, 0, 0] }; map.set(key, c); C.push(c); }
      c.n++; for (let k = 0; k < 5; k++) for (let q = 0; q < 3; q++) c.p[k * 3 + q] += pos[s * 20 + k * 4 + q];
      for (let j = 0; j < 6; j++) for (let q = 0; q < 3; q++) c.b[j * 3 + q] += bake[s * 24 + j * 4 + q];
      for (let q = 0; q < 3; q++) { c.a[q] += attr[s * 12 + q] * attr[s * 12 + q]; c.nn[q] += nt[s * 4 + q] - 128; } }
    const n = C.length, TW = 2048, P = new Float32Array(TW * Math.ceil(n * 5 / TW) * 4), Bk = new Uint8Array(TW * Math.ceil(n * 6 / TW) * 4), At = new Uint8Array(TW * Math.ceil(n * 3 / TW) * 4), Nt = new Uint8Array(TW * Math.ceil(n / TW) * 4);
    C.forEach((c, i) => { const r = c.rep, k = c.n; const pp = [...Array(15)].map((_, j) => c.p[j] / k);
      // кончик — в среднюю сторону волосков, но не короче половины ячейки
      const d = [pp[12] - pp[0], pp[13] - pp[1], pp[14] - pp[2]], dl = Math.hypot(d[0], d[1], d[2]) || 1e-6, L = Math.max(dl, cell * .6) / dl;
      for (let kk = 1; kk < 5; kk++) for (let q = 0; q < 3; q++) pp[kk * 3 + q] = pp[q] + (pp[kk * 3 + q] - pp[q]) * L;
      for (let kk = 0; kk < 5; kk++) { P[(i * 5 + kk) * 4] = pp[kk * 3]; P[(i * 5 + kk) * 4 + 1] = pp[kk * 3 + 1]; P[(i * 5 + kk) * 4 + 2] = pp[kk * 3 + 2]; }
      P[i * 20 + 3] = cell * .5; P[i * 20 + 7] = D.pos[r * 20 + 7];
      for (let j = 0; j < 6; j++) for (let q = 0; q < 3; q++) Bk[i * 24 + j * 4 + q] = Math.round(c.b[j * 3 + q] / k);
      for (let q = 0; q < 12; q++) At[i * 12 + q] = D.attr[r * 12 + q]; for (let q = 0; q < 3; q++) At[i * 12 + q] = Math.round(Math.sqrt(c.a[q] / k));
      const nl = Math.hypot(c.nn[0], c.nn[1], c.nn[2]) || 1; for (let q = 0; q < 3; q++) Nt[i * 4 + q] = Math.round(c.nn[q] / nl * 127 + 128); Nt[i * 4 + 3] = 255; });
    return { n, tP: tex(P, TW, P.length / 4 / TW, THREE.FloatType), tB: tex(Bk, TW, Bk.length / 4 / TW, THREE.UnsignedByteType), tA: tex(At, TW, At.length / 4 / TW, THREE.UnsignedByteType), tN: tex(Nt, TW, Nt.length / 4 / TW, THREE.UnsignedByteType), pos: P };
  };
  const t2 = now(); const L1 = mkLevel(.006), L2 = mkLevel(.014); K2.t.pyr = now() - t2;
  K2.levels = [];
  const mkSet = (name, data, prm, order) => {
    const U2 = Object.assign({}, B.U, { uPos: { value: data.tP }, uBake: { value: data.tB }, uAttr: { value: data.tA }, uNrm: { value: data.tN }, uN: { value: data.n }, uSeedA: { value: K2.furArea / data.n }, uCov: { value: prm.cov },
      uWmin: { value: prm.wmin }, uWmax: { value: prm.wmax }, uWk: { value: 2.0 }, uBias: { value: prm.bias }, uAlpha: { value: prm.alpha }, uEdge: { value: prm.edge }, uLenCap: { value: prm.lenCap }, uNdvMin: { value: prm.ndv }, uView: { value: new THREE.Vector2(1280, 720) }, uDbgS: { value: 0 }, uSeed: { value: 0 }, uJit: { value: prm.jit == null ? .6 : prm.jit } });
    const m = new THREE.RawShaderMaterial(Object.assign({ uniforms: U2, vertexShader: MKB._k.COMMON + STROKE_VS, fragmentShader: FS, glslVersion: THREE.GLSL3 }, blend));
    const g = new THREE.BufferGeometry(); g.setDrawRange(0, data.n * MMAX * 12); g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e4);
    const mesh = new THREE.Mesh(g, m); mesh.frustumCulled = false; mesh.renderOrder = order; B.bg.add(mesh); mesh.onBeforeRender = B.fur.onBeforeRender;
    const L = { name, mesh, U: U2, n: data.n, pos: data.pos, prm }; K2.levels.push(L); return L; };
  mkSet('мягкие', L2, { cov: 1.25, wmin: 3.0, wmax: 24, alpha: .42, edge: 0.0, bias: .004, lenCap: 40, ndv: .32 }, 27);
  mkSet('прядки', L1, { cov: 1.5, wmin: 2.0, wmax: 10, alpha: .5, edge: .1, bias: .003, lenCap: 24, ndv: .12 }, 28);
  const fine = mkSet('волоски', { n: NS, tP: S.tPos, tB: S.tBake, tA: S.tAttr, tN: K2.tN, pos: D.pos }, { cov: 2.2, wmin: 1.0, wmax: 2.2, alpha: .62, edge: .35, bias: .002, lenCap: 14, ndv: -.12, jit: .12 }, 30);
  const strokes = fine.mesh; K2.strokes = strokes; K2.SU = fine.U;
  // фон, лес, земля
  const fogC = new THREE.Color(.37, .42, .41); const U = { uFogC: { value: new THREE.Vector3(fogC.r, fogC.g, fogC.b) }, uFogK: { value: .32 }, uSat: { value: 1 },
    uShT: { value: null }, uShM: { value: new THREE.Matrix4() }, uShOn: { value: 0 }, uShR: { value: .008 }, uShSeed: { value: 0 }, uShC: { value: new THREE.Vector3(0, .42, 0) }, uShD: { value: new THREE.Vector3(0, 1, 0) } };
  const quad = new THREE.BufferGeometry(); quad.setAttribute('position', new THREE.BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3));
  const bgScene = new THREE.Scene(); { const m = new THREE.Mesh(quad, new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: QUAD_VS, fragmentShader: BG_FS, depthTest: false, depthWrite: false, uniforms: { uTop: { value: new THREE.Vector3(.47, .53, .55) }, uHor: { value: new THREE.Vector3(.37, .42, .41) } } })); m.frustumCulled = false; bgScene.add(m); }
  const meshMat = (alb, ao) => new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: MESH_VS, fragmentShader: MESH_FS, uniforms: Object.assign({ uAlb: { value: new THREE.Vector3(...alb) }, uAo: { value: ao == null ? 1 : ao } }, U) });
  const world = new THREE.Scene();
  world.add(new THREE.Mesh(new THREE.PlaneGeometry(40, 40).rotateX(-Math.PI / 2), meshMat([.09, .2, .06])));
  for (const [x, z, r] of [[-1.9, -3.2, .22], [-.8, -4.2, .2], [.25, -5.0, .2], [1.45, -3.6, .22], [2.9, -4.6, .25], [-3.2, -5.4, .25], [3.9, -2.2, .2], [-3.9, -1.5, .22]]) { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 1.12, 9, 24, 1, true), meshMat([.09, .13, .1])); m.position.set(x, 4.5, z); world.add(m); }
  for (const [x, z, sx, sz] of [[-.9, -.9, .38, .3], [-.55, -1.6, .3, .25], [1.6, -.4, .42, .3], [2.4, -1.9, .5, .4]]) { const m = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), meshMat([.3, .5, .17])); m.scale.set(sx, .16, sz); m.position.set(x, 0, z); world.add(m); }
  // трава — мазки
  const NG = opts.grassN || 700000, gr = rng32(77), gd = new Float32Array(NG * 8); const GR = 4.2;
  for (let i = 0; i < NG; i++) { const rr = Math.sqrt(gr()) * GR, a = gr() * 6.2832; const x = Math.cos(a) * rr, z = Math.sin(a) * rr * 1.25 - .8; const h = .045 + gr() * .075, la = gr() * 6.2832, ls = gr() * .5; gd.set([x, 0, z, h, Math.cos(la) * ls, Math.sin(la) * ls, gr(), gr()], i * 8); }
  const gh = Math.ceil(NG * 2 / 4096), gfull = new Float32Array(4096 * gh * 4); gfull.set(gd); const gtex = new THREE.DataTexture(gfull, 4096, gh, THREE.RGBAFormat, THREE.FloatType); gtex.needsUpdate = true; gtex.minFilter = gtex.magFilter = THREE.NearestFilter;
  const GU = Object.assign({ uG: { value: gtex }, uN: { value: NG }, uSeedA: { value: Math.PI * GR * GR * 1.25 / NG }, uCov: { value: 2.6 }, uWmin: { value: 1.2 }, uWmax: { value: 3.4 }, uTime: { value: 0 }, uView: { value: new THREE.Vector2(1280, 720) }, uHero: { value: new THREE.Vector3() }, uDbg: { value: 0 }, uSeed: { value: 0 }, uGrassK: { value: new THREE.Vector3(1, 1, 1) } }, U);
  const gG = new THREE.BufferGeometry(); gG.setDrawRange(0, NG * 2 * 12); gG.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e4);
  const grass = new THREE.Mesh(gG, new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: GRASS_VS, fragmentShader: GRASS_FS, uniforms: GU, transparent: true, depthWrite: false,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor }));
  grass.frustumCulled = false; const grassScene = new THREE.Scene(); grassScene.add(grass); K2._gd = gd;
  const postMat = new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: QUAD_VS, fragmentShader: POST_FS, depthTest: false, depthWrite: false, uniforms: { uT: { value: null }, uExpo: { value: 1.0 }, uInv: { value: 1.0 }, uTone: { value: 1 } } });
  const postScene = new THREE.Scene(); { const m = new THREE.Mesh(quad, postMat); m.frustumCulled = false; postScene.add(m); }
  let RT = null; const getRT = (w, h) => { if (!RT || RT.width !== w || RT.height !== h) { if (RT) RT.dispose(); RT = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: 4 }); } return RT; };
  // НАКОПИТЕЛЬ: кадр = сумма многих проходов (как сэмплы у Blender): каждый раз мазки ложатся заново, камера сдвинута на долю пикселя,
  // солнце — в другой точке своего диска (мягкая тень), объектив — в другой точке линзы (размытие), время — внутри выдержки (смаз движения)
  let ACC = null; const getACC = (w, h) => { if (!ACC || ACC.width !== w || ACC.height !== h) { if (ACC) ACC.dispose(); ACC = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, depthBuffer: false }); } return ACC; };
  const addMat = new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: QUAD_VS, fragmentShader: ADD_FS, depthTest: false, depthWrite: false, transparent: true,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneFactor, uniforms: { uT: { value: null } } });
  const addScene = new THREE.Scene(); { const m = new THREE.Mesh(quad, addMat); m.frustumCulled = false; addScene.add(m); }
  // ТЕНЬ МАЗКАМИ: те же мазки Барсика рисуются со стороны солнца в маску «сколько света забрали»
  const SHS = 1024, shRT = new THREE.WebGLRenderTarget(SHS, SHS, { type: THREE.UnsignedByteType, samples: 4 });
  const shCam = new THREE.PerspectiveCamera(2 * Math.atan(1.0 / 30) * 180 / Math.PI, 1, 24, 37);
  Object.assign(K2, { D, S, world, grassScene, grass, GU, NG, bgScene, postMat, postScene, getRT, getACC, addMat, addScene, shRT, shCam, SHS, WU: U });
  K2.t.boot = now() - t0;
  return K2;
};

// ---------- движение (петля 5 с): машет лапой, вертит головой, хвост ходит ----------
const ss = (a, b, t) => { const x = Math.min(1, Math.max(0, (t - a) / (b - a))); return x * x * (3 - 2 * x); };
K2.pose = function (t) {
  const rig = K2.rig; t = ((t % 5) + 5) % 5;
  const up = ss(.5, 1.0, t) * (1 - ss(2.7, 3.2, t)), wave = Math.sin(t * 9) * .22 * up;
  rig.head.rotation.set(-.04 + .05 * Math.sin(t * 2.1), .3 * Math.sin(t * 1.25) * ss(.2, 1, t), .06 * Math.sin(t * 1.6 + .5));
  rig.arms[0].rotation.set(-0.39, 0, -0.345 - .04 * Math.sin(t * 2));
  rig.arms[1].rotation.set(-0.39 - .5 * up, 0, 0.345 + 1.9 * up + wave);
  rig.legs[0].rotation.set(0, 0, 0); rig.legs[1].rotation.set(0, 0, 0); rig.tail.rotation.y = .35 * Math.sin(t * 1.9);
  window.MKBarsik.frame(rig, { emo: 'neutral', face: 0 }, t, K2.L);
};

K2.SHOTS = {
  photo: { pos: [0, .55, 2.35], look: [0, .44, 0], fov: 30 },
  medium: { pos: [.35, .72, 1.45], look: [0, .58, 0], fov: 30 },
  close: { pos: [.18, .82, .82], look: [0, .72, .05], fov: 30 },
  macro: { pos: [.06, .76, .46], look: [0, .73, .1], fov: 28 } };
K2.setShot = function (sh, orbit) {
  const THREE = K2.THREE, cam = K2.cam; const p = new THREE.Vector3(...sh.pos), l = new THREE.Vector3(...sh.look);
  if (orbit) { const d = p.clone().sub(l); const r = d.length() * orbit.zoom; const yaw = Math.atan2(d.x, d.z) + orbit.yaw, pit = Math.asin(d.y / d.length()) + orbit.pitch;
    p.set(l.x + Math.sin(yaw) * Math.cos(pit) * r, l.y + Math.sin(pit) * r, l.z + Math.cos(yaw) * Math.cos(pit) * r); }
  cam.fov = sh.fov; cam.position.copy(p); cam.lookAt(l); cam.updateProjectionMatrix(); cam.updateMatrixWorld(); K2.focus = l.clone();
};

// оценка числа мазков в кадре (та же формула, что в шейдере, по выборке; поза не учитывается)
K2.count = function (w, h) {
  const THREE = K2.THREE, cam = K2.cam, V = cam.matrixWorldInverse, f = h / (2 * Math.tan(cam.fov * Math.PI / 360)); const a = new THREE.Vector3(), b = new THREE.Vector3(), c2 = new THREE.Vector3(); const toW = (x, y, z, v) => v.set(x, z, -y).applyMatrix4(V);
  let hero = 0; const passes = [];
  for (const L of K2.levels) { const P = L.pos, U = L.U, rk = h / 1080; const step = Math.max(1, Math.floor(L.n / 4000)); let sum = 0, pmax = 0, n = 0;
    for (let s = 0; s < L.n; s += step) { n++; const o = s * 20; if (P[o + 7] >= 200) { sum += 1; continue; } toW(P[o], P[o + 1], P[o + 2], a); const z = -a.z; if (z < .03) continue;
      const sx = a.x / z * f, sy = a.y / z * f; if (Math.abs(sx) > w * .55 || Math.abs(sy) > h * .55) continue;
      toW(P[o + 8], P[o + 9], P[o + 10], b); toW(P[o + 16], P[o + 17], P[o + 18], c2);
      const lpx = Math.hypot(sx - b.x / -b.z * f, sy - b.y / -b.z * f) + Math.hypot(b.x / -b.z * f - c2.x / -c2.z * f, b.y / -b.z * f - c2.y / -c2.z * f);
      const wpx = Math.min(U.uWmax.value, Math.max(U.uWmin.value, P[o + 3] * 2 * f / z)); const p = U.uCov.value * U.uSeedA.value * (f / z) * (f / z) * .6 / (Math.max(Math.min(lpx, U.uLenCap.value * rk), wpx) * wpx);
      sum += Math.min(p, K2.MMAX); if (p > pmax) pmax = p; }
    const cnt = Math.round(sum * L.n / n); hero += cnt; passes.push(Math.max(1, Math.min(K2.MMAX, Math.ceil(pmax * 1.15)))); L.cnt = cnt; }
  const GU = K2.GU, gd = K2._gd, gn = K2.NG, gs = Math.max(1, Math.floor(gn / 5000)); let gsum = 0, gpm = 0, gc = 0; const upv = new THREE.Vector3(0, 1, 0).transformDirection(V);
  for (let i = 0; i < gn; i += gs) { gc++; const o = i * 8; a.set(gd[o], gd[o + 1], gd[o + 2]).applyMatrix4(V); const z = -a.z; if (z < .05) continue; const sx = a.x / z * f, sy = a.y / z * f; if (Math.abs(sx) > w * .6 || Math.abs(sy) > h * .7) continue;
    const hh = gd[o + 3]; b.set(gd[o] + gd[o + 4] * hh, hh * .95, gd[o + 2] + gd[o + 5] * hh).applyMatrix4(V); const lpx = Math.hypot(sx - b.x / -b.z * f, sy - b.y / -b.z * f);
    const wpx = Math.min(GU.uWmax.value, Math.max(GU.uWmin.value, .0028 * f / z)); const gnd = Math.abs(upv.dot(a.clone().negate().normalize()));
    const gp = GU.uCov.value * GU.uSeedA.value * (f / z) * (f / z) * Math.max(gnd, .12) / (Math.max(lpx, wpx) * wpx); gsum += Math.min(gp, 2); if (gp > gpm) gpm = gp; }
  return { hero, passes, grass: Math.round(gsum * gn / gc), grassPass: Math.max(1, Math.min(2, Math.ceil(gpm * 1.1))) };
};

const halton = (i, b) => { let f = 1, r = 0; while (i > 0) { f /= b; r += f * (i % b); i = Math.floor(i / b); } return r; };
Object.assign(K2, { spp: 1, tone: 1, shadowOn: true, dof: 0, shutter: 0, sunAng: .035, accN: 0, focus: null });

// пресеты света: «приложение» — как сейчас в Мультиках; «Blender» — солнце и небо сильнее студийной подсветки, плёнка AgX
K2.PRESETS = {
  app: { sun: 2.3, rim: 1.2, hemi: 1.25, env: .35, expo: 1.0, key: 1.4, desat: .22, tint: [.95, 1, 1], tone: 0, grass: [1, 1, 1] },
  // подобрано по цифрам кадра Blender (лоб, грудка, лапа, трава): нет студийной подсветки спереди, солнце главнее, трава светлее и желтее
  blender: { sun: 2.6, rim: 1.1, hemi: 1.0, env: .25, expo: .76, key: .45, desat: .7, tint: [1.0, 1.12, .9], tone: 0, grass: [2.0, 1.3, 1.6] } };
K2.lightPreset = function (name) {
  const L = K2.L, MKB = window.MKBarsik; K2.preset = name;
  const P = K2.PRESETS[name] || K2.PRESETS.app; L.sun.intensity = P.sun; L.rim.intensity = P.rim; L.hemi.intensity = P.hemi; L.envI = P.env; L.expo = P.expo; MKB.K.key = P.key; MKB.desatU.value = P.desat; K2.tone = P.tone; if (MKB.tintU.value && MKB.tintU.value.set) MKB.tintU.value.set(...(P.tint || [1, 1, 1])); K2.GU.uGrassK.value.set(...P.grass);
};

K2.shadowPass = function (i, seed) {
  const THREE = K2.THREE, R = K2.R, L = K2.L, sc = K2.shCam, S = K2.SHS, WU = K2.WU;
  const sd = L.sun.position.clone().sub(L.sun.target.position).normalize();
  if (i) { const a = halton(i, 3) * 6.2832, r = Math.sqrt(halton(i, 2)) * K2.sunAng;   // солнце не точка — каждый проход из другой точки диска
    const e1 = new THREE.Vector3().crossVectors(sd, new THREE.Vector3(0, 1, 0)).normalize(), e2 = new THREE.Vector3().crossVectors(e1, sd);
    sd.addScaledVector(e1, Math.cos(a) * r).addScaledVector(e2, Math.sin(a) * r).normalize(); }
  const C = WU.uShC.value; sc.position.copy(C).addScaledVector(sd, 30); sc.up.set(0, 1, 0); sc.lookAt(C); sc.updateMatrixWorld();
  for (const Lv of K2.levels) { Lv._vis = Lv.mesh.visible; if (Lv.name === 'волоски') Lv.mesh.visible = false; Lv.U.uView.value.set(S, S); }
  R.setRenderTarget(K2.shRT); R.setViewport(0, 0, S, S); R.setClearColor(0x000000, 0); R.clear(true, true, true); R.setClearColor(0x000000, 1);
  R.render(K2.scene, sc);
  for (const Lv of K2.levels) Lv.mesh.visible = Lv._vis;
  WU.uShM.value.multiplyMatrices(sc.projectionMatrix, sc.matrixWorldInverse); WU.uShT.value = K2.shRT.texture; WU.uShD.value.copy(sd); WU.uShSeed.value = seed;
};

// один проход накопления
K2.sub = function (w, h, t, i, opt) {
  opt = opt || {}; const THREE = K2.THREE, R = K2.R, cam = K2.cam;
  const p0 = cam.position.clone(), q0 = cam.quaternion.clone();
  const seed = i === 0 ? 0 : .05 + .9 * halton(i, 5);
  if (i && K2.dof > 0 && K2.focus) { const r = Math.sqrt(halton(i, 7)) * K2.dof, a = halton(i, 11) * 6.2832;   // точка на линзе, фокус — на Барсике
    const rv = new THREE.Vector3(1, 0, 0).applyQuaternion(q0), uv = new THREE.Vector3(0, 1, 0).applyQuaternion(q0); cam.position.addScaledVector(rv, Math.cos(a) * r).addScaledVector(uv, Math.sin(a) * r); cam.lookAt(K2.focus); }
  cam.aspect = w / h; if (i) cam.setViewOffset(w, h, halton(i + 1, 2) - .5, halton(i + 1, 3) - .5, w, h); else cam.clearViewOffset();
  cam.updateProjectionMatrix(); cam.updateMatrixWorld();
  const tt = i && K2.shutter ? t + (halton(i, 13) - .5) * K2.shutter : t;
  K2.pose(tt); const rk = Math.max(.75, h / 1080);
  const strokesOn = K2.mode !== 'hair'; K2.B.fur.visible = !strokesOn;
  for (const L of K2.levels) { L.mesh.visible = strokesOn && !(K2.onlyFine && L.name !== 'волоски'); L.U.uWmin.value = L.prm.wmin * rk; L.U.uWmax.value = L.prm.wmax * rk; L.U.uDbgS.value = opt.dbg ? 1 : 0; L.U.uSeed.value = seed; }
  K2.GU.uView.value.set(w, h); K2.GU.uTime.value = tt; K2.GU.uWmin.value = 1.1 * rk; K2.GU.uWmax.value = 3.2 * rk; K2.GU.uDbg.value = opt.dbg ? 1 : 0; K2.GU.uSeed.value = seed;
  const st = K2.stats.last = K2.count(w, h); if (!strokesOn) st.hero = 0;
  K2.levels.forEach((L, j) => L.mesh.geometry.setDrawRange(0, L.n * st.passes[j] * 12)); K2.grass.geometry.setDrawRange(0, K2.NG * st.grassPass * 12);
  K2.WU.uShOn.value = K2.shadowOn ? 1 : 0; if (K2.shadowOn) K2.shadowPass(i, seed);
  for (const L of K2.levels) L.U.uView.value.set(w, h);
  const RT = K2.getRT(w, h); R.setRenderTarget(RT); R.setViewport(0, 0, w, h); R.clear(true, true, true);
  R.render(K2.bgScene, cam); R.render(K2.world, cam);
  R.render(K2.scene, cam);          // Барсик: кожа, налёт, глаза, веки, рот + шерсть (мазки или волоски)
  if (K2.grassOn !== false) R.render(K2.grassScene, cam);
  const ACC = K2.getACC(w, h); K2.addMat.uniforms.uT.value = RT.texture; R.setRenderTarget(ACC); R.setViewport(0, 0, w, h); R.render(K2.addScene, cam); K2.accN++;
  cam.clearViewOffset(); cam.position.copy(p0); cam.quaternion.copy(q0); cam.updateProjectionMatrix(); cam.updateMatrixWorld();
  return st;
};
K2.accReset = function (w, h) { const R = K2.R, A = K2.getACC(w, h); R.setRenderTarget(A); R.setClearColor(0x000000, 0); R.clear(true, false, false); R.setClearColor(0x000000, 1); K2.accN = 0; };
K2.resolve = function (w, h, target) { const R = K2.R, pm = K2.postMat.uniforms; pm.uT.value = K2.getACC(w, h).texture; pm.uInv.value = 1 / Math.max(1, K2.accN); pm.uTone.value = K2.tone;
  R.setRenderTarget(target || null); R.setViewport(0, 0, w, h); R.render(K2.postScene, K2.cam); };
// кадр целиком: spp проходов
K2.frame = function (w, h, t, opt) {
  opt = opt || {}; const n = Math.max(1, opt.spp || K2.spp || 1); K2.accReset(w, h); let st;
  for (let i = 0; i < n; i++) st = K2.sub(w, h, t, i, opt);
  K2.resolve(w, h, opt.target); return st;
};
})();
