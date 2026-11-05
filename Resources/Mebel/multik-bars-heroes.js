// БАРС («Быстрый Анимационный Рендер на Сотах») — герои образца 6.2: Пик и Рон в сценах «Мультиков».
// Части движка образца (шейдеры, рост шерсти, сбор света) взяты из tools/multik/obrazec/page/engine6.js без изменений смысла;
// добавлено: свет места (диммеры прошитых каналов), туман места, ноги со своим весом, защита от NaN (iPhone).
(function (global) {
'use strict';
const H6 = global.BARSHeroes = { ready: {}, base: 'heroes6/', furK: .75 };
(global.BARS = global.BARS || {}).heroes = H6;
H6.DBG = null;
let THREE = null;
const now = () => performance.now();
const DBG = { value: 0 }; H6.DBG = DBG;
// ---------- текстуры данных ----------
const TW = 4096;
function dataTex(arr, n, type) { // n текселей RGBA
  const h = Math.max(1, Math.ceil(n / TW)); let a = arr; const need = TW * h * 4;
  if (a.length < need) { const b = new a.constructor(need); b.set(a); a = b; }
  const t = new THREE.DataTexture(a, TW, h, THREE.RGBAFormat, type || THREE.FloatType); t.minFilter = t.magFilter = THREE.NearestFilter; t.needsUpdate = true; t.generateMipmaps = false; return t; }
// ---------- общий кусок шейдеров ----------
const GL_HEAD = `precision highp float; precision highp int; precision highp sampler2D;
uniform mat4 projectionMatrix, viewMatrix; uniform vec3 cameraPosition; uniform bool isOrthographic;
vec4 TX(sampler2D t, int i) { return texelFetch(t, ivec2(i % ${TW}, i / ${TW}), 0); }
uniform float uMistS, uMistD, uMistK; uniform vec3 uMistC;
uniform vec3 uSunD, uSunC, uKeyD, uKeyC, uRimD, uRimC, uFillD, uFillC;
float coneV(float c, float ct) { return smoothstep(ct - .35, ct + .35, c); }
// v — видимость лампы в позе покоя (запечена), b0 — «куда открыта» точка в покое, b — сейчас; поправка, когда часть повернулась
float liveVis(float v, vec3 b0, vec3 b, float ct, vec3 L) { return clamp(v + coneV(dot(b, L), ct) - coneV(dot(b0, L), ct), 0.0, 1.0); }
float mistF(vec3 p) { if (uMistD <= 0.0) return 0.0; float d = length(p - cameraPosition); return uMistK * clamp((d - uMistS) / uMistD, 0.0, 1.0); }
uniform vec3 uSkyK; uniform float uExpo; uniform mat4 uLegM[2]; uniform vec3 uBkSun, uBkKey, uBkRim, uBkFill;
vec3 sane(vec3 c) { bvec3 bad = equal(floatBitsToUint(c) & uvec3(0x7f800000u), uvec3(0x7f800000u)); vec3 r = min(max(c, vec3(0.0)), vec3(300.0)); return any(bad) ? vec3(0.0) : r; }
float liveVis2(float v, vec3 bR, vec3 bN, float ct, vec3 L, vec3 Lb) { return clamp(v + coneV(dot(bN, L), ct) - coneV(dot(bR, Lb), ct), 0.0, 1.0); }
`;

function THREE_Color(r, g, b) { return { r, g, b, isColor: true, _lazy: [r, g, b] }; }
// ---------- нити: шерсть и трава, ленточки из текстуры точек (без атрибутов, по gl_VertexID) ----------
function strandVS(depth) { return GL_HEAD + `
uniform sampler2D uPts, uCol, uB0, uB1, uB2, uNrm; uniform int uK; uniform int uLive, uCull; uniform float uCullK, uKT; uniform float uRadK, uTaper, uPx, uMinPx; uniform vec4 uGR; uniform int uGrass; uniform vec3 uCamDir;
uniform float uTime, uWind; uniform mat4 uPartM[6]; uniform int uBlink, uDec, uHideArm; uniform vec4 uMouthC; uniform vec3 uMouthR; uniform int uPoseOn; uniform sampler2D uPA, uPB; uniform float uPW;
out vec3 vCol; out vec3 vE; out vec4 vVis; out vec3 vT; out vec3 vP; out float vCov; out float vTT; out float vMist;
vec3 P(int i) { return TX(uPts, i).xyz; }
void main() {
  int vid = gl_VertexID; int c = vid % 6; int q = vid / 6; int seg = q % (uK - 1); int s = q / (uK - 1);
  int kk = seg + ((c == 2 || c == 3 || c == 5) ? 1 : 0); float side = (c == 1 || c == 4 || c == 5) ? 1.0 : -1.0;
  int base = s * uK; int i = base + kk; vec4 q0 = TX(uPts, i); int ip = int(q0.w + .5); int part = ip & 7; float lw = float((ip >> 3) & 63) / 63.0; mat4 M = uPartM[part]; if (lw > 0.0) M = M + (uLegM[ip >> 9] - M) * lw;
  if (part == 5 && uBlink == 0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  if (part == 1 && uMouthC.w > 0.0) { vec3 dm = (TX(uPts, base).xyz - uMouthC.xyz) / uMouthR; if (dot(dm, dm) < 1.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; } }   // рот открыт — шерсть закрытых губ не закрывает его
  ${depth ? 'if (uDec > 1 && s % uDec != 0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }' : ''}
  ${depth ? 'if ((uHideArm == 1 && (part == 2 || part == 3)) || (uHideArm == 2 && part != 2 && part != 3)) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }' : ''}
  ${depth ? '' : `if (uCull == 1) { // шерсть за телом не рисуем (кроме длинных кисточек, они торчат за край)
    vec3 n0 = TX(uNrm, s).xyz * 2.0 - 1.0; vec3 r0 = TX(uPts, base).xyz, r4 = TX(uPts, base + uK - 1).xyz;
    vec3 rw = (M * vec4(r0, 1.0)).xyz; if (dot(normalize(mat3(M) * n0), normalize(cameraPosition - rw)) < uCullK && distance(r0, r4) < .018) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; } }`}
  vec3 p = (M * vec4(q0.xyz, 1.0)).xyz;
  vec3 tR = normalize(P(base + min(kk + 1, uK - 1)) - P(base + max(kk - 1, 0))); vec3 t = normalize(mat3(M) * tR);
  float tt = float(kk) / float(uK - 1);
  float rad;
  if (uGrass == 1) { rad = kk == 0 ? uGR.x : kk == 1 ? uGR.y : kk == 2 ? uGR.z : uGR.w; }
  else { vec4 sc = TX(uCol, s); rad = sc.a * uRadK * (1.0 - uTaper * pow(tt, 1.3)); vCol = sc.rgb; }
  ${depth ? 'rad *= float(max(uDec, 1));' : ''}
  // лёгкий ветер для травы
  if (uGrass == 1 && uWind > 0.0) { p.x += sin(uTime * 1.7 + p.x * 2.1 + p.z * 1.3) * uWind * tt * tt; p.z += sin(uTime * 1.3 + p.x * 1.1) * uWind * .6 * tt * tt; }
  vec3 V = isOrthographic ? -uCamDir : cameraPosition - p; float dist = length(V); vec3 vd = V / dist;
  vec3 bn = cross(t, vd); float bl = length(bn); bn = bl > 1e-5 ? bn / bl : normalize(cross(t, vec3(0.0, 1.0, 0.0)));
  float px = isOrthographic ? uPx : uPx * dist; float hw = max(rad, .5 * px * uMinPx); vCov = clamp(rad / hw, 0.0, 1.0);
  vec3 wp = p + bn * side * hw;
  gl_Position = projectionMatrix * viewMatrix * vec4(wp, 1.0);
  ${depth ? '' : `vec4 b0 = TX(uB0, i), b1 = TX(uB1, i); vE = b0.rgb * uSkyK; vVis = b1; vT = t; vP = wp; vTT = tt; vMist = mistF(wp);
  if (uGrass == 0 && uLive >= 1) { // солнце и лампы — по тому, как волосок лежит СЕЙЧАС
    vec4 b2 = TX(uB2, i); vec3 bR = length(b2.xyz) > 1e-6 ? normalize(b2.xyz) : vec3(0.0, 1.0, 0.0); float ct = 1.0 - 2.0 * clamp(b2.w, 0.0, 1.0);
    bool live = uLive == 1; vec3 bN = live ? normalize(mat3(M) * bR) : bR; vec3 Tn = live ? t : tR; vec3 ke = 1.0 - uKT * vCol; vec4 vn;
    vec4 pv = uPoseOn == 1 ? mix(TX(uPA, i), TX(uPB, i), uPW) : vec4(0.0);
    vec3 Ls[4] = vec3[4](uSunD, uKeyD, uRimD, uFillD); vec3 Cs[4] = vec3[4](uSunC, uKeyC, uRimC, uFillC); vec3 Lb[4] = vec3[4](uBkSun, uBkKey, uBkRim, uBkFill); vec3 E = vec3(0.0);
    for (int j = 0; j < 4; j++) { float v = live ? liveVis2(b1[j], bR, bN, ct, Ls[j], Lb[j]) : b1[j]; float c = dot(Tn, Ls[j]);
      E += Cs[j] * (.3 + .7 * sqrt(max(0.0, 1.0 - c * c))) * pow(vec3(max(v, 1e-4)), ke); vn[j] = v; }
    vE += E; vVis = vn; }
  if (uGrass == 1) vCol = mix(vec3(0.02, 0.06, 0.01), vec3(0.25, 0.45, 0.06), tt);
  else vCol *= mix(vec3(0.62, 0.55, 0.5), vec3(1.0), 1.0 - (1.0 - tt) * (1.0 - tt));`}
}`; }
const STRAND_FS = GL_HEAD + `
uniform int uGrass, uDbgS; uniform float uHairK, uMS, uSpec, uDesat, uGold; uniform vec3 uGoldT;
in vec3 vCol; in vec3 vE; in vec4 vVis; in vec3 vT; in vec3 vP; in float vCov; in float vTT; in float vMist;
out vec4 oc;
float kk(vec3 T, vec3 L, vec3 V, float sh) { vec3 H = normalize(L + V + vec3(1e-4, 2e-4, 3e-4)); float th = dot(T, H); return pow(max(0.0, sqrt(max(0.0, 1.0 - th * th))), sh); }
void main() {
  vec3 V = normalize(cameraPosition - vP); vec3 T = normalize(vT);
  float lum = dot(vCol, vec3(.2126, .7152, .0722)); float mx = max(vCol.r, max(vCol.g, vCol.b)), mn = min(vCol.r, min(vCol.g, vCol.b)); float st = (mx - mn) / max(mx, 1e-4);
  vec3 a = mix(vCol, uGoldT * (lum / dot(uGoldT, vec3(.2126, .7152, .0722))), uGold * st * (.45 + .55 * smoothstep(.05, .2, lum))); a = mix(a, vec3(dot(a, vec3(.2126, .7152, .0722))), uDesat); vec3 ae = a / (1.0 - uMS * a); // многократное рассеяние в шерсти — цвет глубже и светлее
  vec3 col = ae * vE * uHairK;
  // блики: основной (белый, чуть к корню) и вторичный (цветной); контровой свет просвечивает волоски
  vec3 Ts = normalize(T + vec3(0.0, 0.0, 0.0));
  vec3 sp = (uSunC * vVis.x * kk(Ts, uSunD, V, 60.0) + uKeyC * vVis.y * kk(Ts, uKeyD, V, 60.0) + uRimC * vVis.z * kk(Ts, uRimD, V, 40.0)) * uSpec;
  vec3 sp2 = (uSunC * vVis.x * kk(Ts, uSunD, V, 14.0) + uKeyC * vVis.y * kk(Ts, uKeyD, V, 14.0)) * uSpec * .5 * a;
  float back = pow(max(0.0, dot(-V, uRimD)), 3.0); vec3 tt = min(uRimC * vVis.z * back * .06 * vTT, vec3(1.5)) * mix(ae, vec3(dot(ae, vec3(.33))), .5);
  col += (uGrass == 1 ? .35 : 1.0) * (sp + sp2) + tt;
  if (uGrass == 1) col += ae * vec3(0.05, 0.09, 0.03) * .6;
  col = mix(col * uExpo, uMistC, vMist); if (any(isnan(col)) || any(isinf(col))) col = vec3(0.0); col = min(col, vec3(40.0));
  if (uDbgS == 2) col = mix(ae * .8, uMistC, vMist);
  float cv = vCov; if ((floatBitsToUint(cv) & 0x7f800000u) == 0x7f800000u) cv = 1.0; oc = vec4(sane(col), clamp(cv, 0.0, 1.0));
}`;
const DEPTH_FS = `precision highp float; out vec4 oc; void main() { oc = vec4(1.0); }`;
// ---------- поверхности (кожа, нос, шарф, глаза, земля, камни, стволы) ----------
const SURF_VS = GL_HEAD + `
uniform mat4 modelMatrix; uniform sampler2D uB0, uB1, uB2, uPA, uPB; uniform int uBase; uniform int uLiveS, uPoseOn; uniform float uPW; uniform mat3 uRestN;
in vec3 position; in vec3 normal; in vec4 color; in vec2 aLeg;
out vec3 vE; out vec4 vVis; out vec3 vN; out vec3 vP; out vec4 vC; out vec3 vL; out float vMist; out vec3 vDbg;
void main() { mat4 MM = modelMatrix; if (aLeg.x > 0.0) MM = MM + (uLegM[int(aLeg.y + .5)] - MM) * aLeg.x; vec4 w = MM * vec4(position, 1.0); vP = w.xyz; vN = normalize(mat3(MM) * normal); vL = position;
  int i = uBase + gl_VertexID; vE = TX(uB0, i).rgb * uSkyK; vDbg = vec3(float(gl_VertexID % 4096) / 4096.0, float(gl_VertexID / 4096) / 64.0, TX(uB0, 87915).g / 4.0); vVis = TX(uB1, i); vC = color; vMist = mistF(vP);
  if (uLiveS >= 1) { vec4 b1 = vVis, b2 = TX(uB2, i); vec3 nR = normalize(uRestN * normal); vec3 bR = length(b2.xyz) > 1e-6 ? normalize(b2.xyz) : nR; float ct = 1.0 - 2.0 * clamp(b2.w, 0.0, 1.0);
    bool live = uLiveS == 1; vec3 Nn = live ? vN : nR; vec3 bN = live ? normalize(mat3(MM) * (transpose(uRestN) * bR)) : bR;
    vec3 Ls[4] = vec3[4](uSunD, uKeyD, uRimD, uFillD); vec3 Cs[4] = vec3[4](uSunC, uKeyC, uRimC, uFillC); vec3 Lb[4] = vec3[4](uBkSun, uBkKey, uBkRim, uBkFill); vec3 E = vec3(0.0); vec4 vn; float sss = color.a;
    vec4 pv = uPoseOn == 1 ? mix(TX(uPA, i), TX(uPB, i), uPW) : vec4(0.0);
    for (int j = 0; j < 4; j++) { float v = live ? liveVis2(b1[j], bR, bN, ct, Ls[j], Lb[j]) : b1[j]; float g = dot(Nn, Ls[j]);
      E += Cs[j] * (max(g, 0.0) * v + max(-g, 0.0) * sss * .5 * (1.0 - v * .5)); vn[j] = v; }
    vE += E; vVis = vn; }
  gl_Position = projectionMatrix * viewMatrix * w; }`;
const SURF_DVS = `precision highp float; uniform mat4 projectionMatrix, viewMatrix, modelMatrix; in vec3 position; void main() { gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(position, 1.0); }`;
const NOISE = `float h3(vec3 p) { p = fract(p * .3183099 + .1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vn(vec3 x) { vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y), mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }
float fbm(vec3 p) { float s = 0.0, a = .5; for (int i = 0; i < 5; i++) { s += a * vn(p); p *= 2.03; a *= .5; } return s; }`;
const SURF_FS = GL_HEAD + NOISE + `
uniform int uMat; uniform vec3 uAlb; uniform vec4 uCapC; uniform vec3 uEyeD, uEyeC; uniform float uRough, uWet; uniform vec3 uIris0, uIris1, uIris2; uniform vec2 uEyeK; uniform float uIrisS;
uniform vec3 uSky, uGnd; uniform mat4 uEyeM; uniform int uDbg; uniform float uGndK;
in vec3 vE; in vec4 vVis; in vec3 vN; in vec3 vP; in vec4 vC; in vec3 vL; in float vMist; in vec3 vDbg;
out vec4 oc;
float ggx(vec3 N, vec3 L, vec3 V, float r) { vec3 H = normalize(L + V); float nh = max(dot(N, H), 0.0), a = r * r, a2 = a * a; float d = nh * nh * (a2 - 1.0) + 1.0; float nl = max(dot(N, L), 0.0); return a2 / (3.14159 * d * d) * nl * .25 / max(.05, dot(N, V) * nl + .05) * nl; }
void main() {
  vec3 N = normalize(vN); vec3 V = normalize(cameraPosition - vP); if (dot(N, V) < 0.0 && uMat != 5) N = -N;
  vec3 alb = uAlb; float spec = 0.0; vec3 extra = vec3(0.0);
  if (uMat == 1) alb = vC.rgb;                                   // кожа (цвет на вершинах)
  else if (uMat == 2) {                                           // земля
    float n = fbm(vP * vec3(1.5, 1.5, 1.5) * .9); alb = mix(vec3(0.04, 0.09, 0.02), vec3(0.16, 0.26, 0.05), smoothstep(.25, .75, n)); }
  else if (uMat == 3) {                                           // кора, внизу мох
    float n = fbm(vec3(vP.x * 6.0, vP.y * .6, vP.z * 6.0)); vec3 bark = mix(vec3(0.05, 0.035, 0.025), vec3(0.22, 0.17, 0.11), n);
    alb = vP.y < 7.9 ? mix(vec3(0.1, 0.2, 0.055), vec3(0.09, 0.1, 0.1), .45) : bark; alb *= .7 + .35 * n; }
  else if (uMat == 4) {                                           // шарф: полосы ткани
    float b = sin(vL.y * 2800.0) * .5 + .5; alb = vec3(0.015, 0.09, 0.45) * (.86 + .14 * b);
    float sh = pow(1.0 - max(dot(N, V), 0.0), 3.0); extra = vec3(0.1, 0.16, 0.42) * sh * .5 * (vE / 3.14159); }
  else if (uMat == 5) {                                           // глаз: белок -> радужка -> зрачок (как в render.py)
    vec3 q = (uEyeM * vec4(vP, 1.0)).xyz; float cz = -q.y;  // локально глаз смотрит в -Y
    float iris = smoothstep(uEyeK.x, uEyeK.x + .015, cz), pup = smoothstep(uEyeK.y, uEyeK.y + .007, cz), ring = smoothstep(uEyeK.x, uEyeK.x + .09, cz);
    float n = fbm(vec3(q.x * 9.0, q.y * .45, q.z * 9.0) * 1.0 + 3.0);
    vec3 ir;
    if (uIrisS > .5) {  // большая тёмно-карая радужка: сверху темнее, книзу светлее (свет снизу, как в мультфильмах), тёмный ободок, без лучиков
      float t = clamp((uEyeK.y - cz) / max(uEyeK.y - uEyeK.x, 1e-3), 0.0, 1.0); float up = q.z / max(sqrt(1.0 - uEyeK.x * uEyeK.x), .1);
      ir = mix(uIris1, uIris2, smoothstep(0.15, -0.85, up)); ir = mix(ir, uIris0, smoothstep(.8, .98, t));
      ir *= .94 + .1 * fbm(vec3(q.x * 5.0, q.z * 5.0, 4.0));
    } else {
      ir = n < .55 ? mix(uIris0, uIris1, smoothstep(.3, .55, n)) : mix(uIris1, uIris2, smoothstep(.55, .75, n));
      ir *= mix(vec3(0.2, 0.25, 0.16), vec3(1.0), ring); }
    alb = mix(mix(vec3(0.9, 0.88, 0.86), ir, iris), vec3(0.004, 0.003, 0.003), pup); }
  else if (uMat == 6) spec = .6;                                  // нос — влажный
  else if (uMat == 8) { alb = uAlb * .25; }                                                        // золото (жетон)
  else if (uMat == 9) { float sh = pow(1.0 - max(dot(N, V), 0.0), 2.0); extra = uAlb * sh * .35 * (vE / 3.14159); } // атлас (бантик, ошейник)
  else if (uMat == 10) {                                          // ткань кепки: шесть клиньев со швами и строчкой, пуговка, саржа, тень у края
    vec3 q = vL - uCapC.xyz; float a = atan(q.x, q.z), rr = length(q.xz), top = uCapC.y - vL.y;
    float wedge = abs(fract(a / 1.0472 + .5) - .5) * 1.0472 * max(rr, .004);                     // расстояние до шва (м)
    float seam = (1.0 - smoothstep(.0007, .0016, wedge)) * smoothstep(.006, .014, rr);
    float fs = clamp(1.5 - fwidth(top * 260.0) * 2.5, 0.0, 1.0), ft = clamp(1.5 - fwidth(vL.y * 1100.0) * 2.5, 0.0, 1.0);   // мелкое — только когда кепка крупно (без ряби)
    float stitch = (1.0 - smoothstep(.0008, .0014, abs(wedge - .0032))) * step(.5, fract(top * 260.0)) * smoothstep(.008, .016, rr) * fs;
    float twill = (.5 + .5 * sin((vL.x * .7 + vL.y + vL.z * .7) * 1100.0)) * ft, n = fbm(vP * 90.0);
    float rim = smoothstep(uCapC.w, uCapC.w + .014, vL.y), btn = 1.0 - smoothstep(.009, .012, rr);
    alb = uAlb * .76 * (.93 + .07 * n) * (.95 + .05 * twill) * (1.0 - .32 * seam) * (1.0 - .16 * stitch) * (.68 + .32 * rim) * (1.0 - .15 * btn * smoothstep(.007, .0095, rr));   // белая ткань, но не «лампа»: без пересвета и ореола
    float sh = pow(1.0 - max(dot(N, V), 0.0), 3.0); extra = uAlb * sh * .1 * (vE / 3.14159); }
  else if (uMat == 7) { float n = fbm(vP * 7.0), n2 = fbm(vP * 31.0); alb = mix(vec3(0.1, 0.2, 0.05), vec3(0.22, 0.36, 0.11), smoothstep(.3, .75, n)) * (.9 + .2 * n2);
    float fr = pow(1.0 - max(dot(N, V), 0.0), 2.5); extra = vec3(0.36, 0.5, 0.3) * fr * .45 * (vE / 3.14159); }
  vec3 col = alb / 3.14159 * vE + extra;
  if (uMat == 0 || uMat == 2 || uMat == 3 || uMat == 7) { float fr = .04 + .96 * pow(1.0 - max(dot(N, V), 0.0), 5.0); col += uSky * fr * .6 * (vE.g / 5.0) + uSky * .02; }
  // снизу — отражённый от земли зеленоватый свет (мягко, без теней)
  col += alb * uGnd * (.5 - .5 * N.y) * .5 * uGndK;
  if (uMat == 1) col += alb * pow(1.0 - max(dot(N, V), 0.0), 2.0) * .6 * vE / 3.14159;
  if (uMat == 6 || uMat == 1) col += (uKeyC * vVis.y * ggx(N, uKeyD, V, uMat == 6 ? .3 : .55) + uSunC * vVis.x * ggx(N, uSunD, V, uMat == 6 ? .3 : .55)) * (uMat == 6 ? .25 + .5 * uWet : .03);
  if (uMat == 8) { col += uAlb * (uKeyC * vVis.y * ggx(N, uKeyD, V, .28) + uSunC * vVis.x * ggx(N, uSunD, V, .28)) * .8; vec3 Rv = reflect(-V, N); col += uAlb * mix(vec3(0.05, 0.06, 0.04), uSky * 1.2, smoothstep(-.2, .6, Rv.y)) * .6; }
  if (uMat == 9) col += uAlb * .5 * (uKeyC * vVis.y * ggx(N, uKeyD, V, .4) + uSunC * vVis.x * ggx(N, uSunD, V, .4)) * .2;
  if (uDbg == 1) col = vE / 3.14159 * .5; if (uDbg == 2) col = alb; if (uDbg == 5) col = alb * (.3 + .9 * max(dot(N, uKeyD), 0.0) + .25 * max(dot(N, uFillD), 0.0)); if (uDbg == 3) col = N * .5 + .5; if (uDbg == 4) { oc = vec4(vDbg, 1.0); return; }
  col = mix(col * uExpo, uMistC, vMist); if (any(isnan(col)) || any(isinf(col))) col = vec3(0.0); col = min(col, vec3(40.0));
  oc = vec4(sane(col), 1.0);
}`;
// роговица: прозрачная линза — только отражения (окно-свет, небо) и блик
const CORNEA_FS = GL_HEAD + `
uniform vec3 uEyeD, uEyeC, uSky;
in vec3 vE; in vec4 vVis; in vec3 vN; in vec3 vP; in vec4 vC; in vec3 vL; in float vMist; out vec4 oc;
void main() { vec3 N = normalize(vN), V = normalize(cameraPosition - vP); float nv = max(dot(N, V), 0.0); float F = .02 + .98 * pow(1.0 - nv, 5.0);
  vec3 Rv = reflect(-V, N); vec3 env = mix(vec3(0.05, 0.07, 0.06), uSky * 1.4, smoothstep(-.1, .5, Rv.y));
  float hk = pow(max(dot(Rv, uKeyD), 0.0), 600.0) * 40.0, he = pow(max(dot(Rv, uEyeD), 0.0), 900.0) * 60.0, hs = pow(max(dot(Rv, uSunD), 0.0), 2000.0) * 40.0;
  vec3 col = env * F + uKeyC * hk + uEyeC * he + uSunC * hs;
  oc = vec4(sane(col * uExpo), 1.0); }`;
// ---------- запекание ----------
// Точки-приёмники: «нити» (тангенс из соседних точек) и «поверхности» (нормаль). Для каждого направления света:
// 1) глубина сцены из света (орто-камера по коробке группы), 2) для каждой точки: видна ли она свету / сколько шерсти перед ней.
const GATHER_FS = `precision highp float; precision highp int; precision highp sampler2D;
uniform sampler2D uPos, uDir, uDepth, uDepthArm, uFCol; uniform int uSplit; uniform mat4 uLVP; uniform vec3 uL, uCol, uBounce; uniform float uKT, uW; uniform int uGrassG, uDirect, uPosed, uOnlyVis; uniform mat4 uPartM[6]; uniform vec4 uMask; uniform float uTexel, uRange, uTauH, uTauS, uTauO, uAO; uniform int uKind, uK, uN;
layout(location = 0) out vec4 o0; layout(location = 1) out vec4 o1; layout(location = 2) out vec4 o2;
vec4 TX(sampler2D t, int i) { return texelFetch(t, ivec2(i % ${TW}, i / ${TW}), 0); }
void main() {
  ivec2 ij = ivec2(gl_FragCoord.xy); int i = ij.y * ${TW} + ij.x; if (i >= uN) discard;
  vec4 P0 = TX(uPos, i); int prt = int(P0.w + .5) & 7; bool armP = uSplit == 1 && (prt == 2 || prt == 3);   // лапу затеняет только лапа, туловище — всё, кроме лап
  vec3 p = P0.xyz; mat3 Mr = mat3(1.0); if (uPosed == 1) { mat4 Mp = uPartM[int(P0.w + .5)]; p = (Mp * vec4(p, 1.0)).xyz; Mr = mat3(Mp); }
  vec3 d; float g, sss = 0.0; bool hair = uKind == 1;
  if (hair) { int k = i % uK; int b = i - k; d = normalize(Mr * (TX(uPos, b + min(k + 1, uK - 1)).xyz - TX(uPos, b + max(k - 1, 0)).xyz)); float c = dot(d, uL); g = sqrt(max(0.0, 1.0 - c * c)); }
  else { vec4 D = TX(uDir, i); d = normalize(Mr * D.xyz); sss = D.w; g = dot(d, uL); }
  vec3 off = hair ? vec3(0.0) : d * uTexel * 1.2;
  vec4 lp = uLVP * vec4(p + off, 1.0); vec3 q = lp.xyz / lp.w * .5 + .5;
  float vis = 0.0, tr = 0.0; vec3 visC = vec3(0.0);
  vec3 alb = vec3(0.0); if (hair) { int k = i % uK; alb = uGrassG == 1 ? mix(vec3(0.02, 0.06, 0.01), vec3(0.25, 0.45, 0.06), float(k) / float(uK - 1)) : TX(uFCol, i / uK).rgb; }
  vec3 tauC = uTauH / max(vec3(.08), 1.0 - uKT * alb);
  if (q.x < 0.0 || q.y < 0.0 || q.x > 1.0 || q.y > 1.0) { vis = 1.0; tr = 1.0; visC = vec3(1.0); }
  else {
    vec2 ts = vec2(1.0) / vec2(textureSize(uDepth, 0)); float rot = fract(sin(float(i) * 12.9898) * 43758.5453) * 6.2832;
    for (int j = 0; j < 12; j++) { float a = float(j) * 2.39996 + rot, r = sqrt((float(j) + .5) / 12.0) * 1.9; vec2 o = vec2(cos(a), sin(a)) * r;
      vec2 uv = q.xy + o * ts; float zo = armP ? texture(uDepthArm, uv).r : texture(uDepth, uv).r; float dz = (q.z - zo) * uRange; // метры «за» первым препятствием
      if (hair) { float e = max(dz - uTexel, 0.0); vis += exp(-e / uTauH); visC += exp(-e / tauC); }
      else { vis += dz < uTexel * 2.0 ? 1.0 : exp(-(dz - uTexel * 2.0) / uTauO); tr += exp(-max(dz, 0.0) / uTauS); }
    }
    vis /= 12.0; tr /= 12.0; visC /= 12.0;
  }
  float geo = hair ? (0.3 + 0.7 * g) : max(g, 0.0);
  vec3 E = hair ? uCol * geo * visC : uCol * geo * vis;
  E += uBounce * geo * (1.0 - (hair ? visC : vec3(vis)));
  if (!hair && sss > 0.0) E += uCol * max(-g, 0.0) * tr * sss * .8 + uCol * max(g, 0.0) * (1.0 - vis) * tr * sss * .25;
  float vs = hair ? dot(visC, vec3(.2126, .7152, .0722)) : vis;
  if (uOnlyVis == 1) { o0 = uMask * vis; o1 = vec4(0.0); o2 = vec4(0.0); }
  else if (uDirect == 1) { o0 = vec4(0.0); o1 = uMask * vis; o2 = vec4(0.0); }
  else { o0 = vec4(E, uAO * vis); o1 = uMask * vis; o2 = vec4(uL * vs, vs) * uW; }
}`;

function fib(n, i) { const y = 1 - (i + .5) / n, r = Math.sqrt(Math.max(0, 1 - y * y)), a = i * 2.399963229728653; return new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r); }
// ---------- шерсть растит сам телефон: те же правила, что make_fur в Blender-версии ----------
function rng32(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
// skin: {p Float32 (xyz), n Int8, idx Uint32, fd Uint8 (rgb шерсти, можно ли, область)}; cfg: правила; src: точки (наши оси)
function growFur(skin, cfg, src, partId, out, seed, kScale) {
  const P = skin.p, Nn = skin.n, I = skin.idx, FD = skin.fd; if (!FD) return 0;
  const nt = I.length / 3, cum = new Float64Array(nt); let tot = 0, area = 0;
  for (let t = 0; t < nt; t++) { const a = I[t * 3], b = I[t * 3 + 1], c = I[t * 3 + 2];
    const ux = P[b * 3] - P[a * 3], uy = P[b * 3 + 1] - P[a * 3 + 1], uz = P[b * 3 + 2] - P[a * 3 + 2], vx = P[c * 3] - P[a * 3], vy = P[c * 3 + 1] - P[a * 3 + 1], vz = P[c * 3 + 2] - P[a * 3 + 2];
    const ar = .5 * Math.hypot(uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx); area += ar; const rg = FD[a * 5 + 4]; tot += ar * (cfg.dens[rg] || 0); cum[t] = tot; }
  const want = Math.round(area * cfg.K * kScale); if (want < 1 || tot <= 0) return 0;
  const r = rng32(seed), D = [0, -1, 0];
  const SH = src.should, WR = src.wrist, HI = src.hip, FO = src.foot, TL = src.tail, NO = src.nose, EO = src.earOff, NE = src.neck;
  const nrm3 = v => { const l = Math.hypot(v[0], v[1], v[2]) || 1; v[0] /= l; v[1] /= l; v[2] /= l; return v; };
  // бок под лапой: в данных там шерсти нет (вершина внутри лапы), но лапа поднимается — бок должен быть пушистым, а не голым
  // и внутренняя сторона лапы (в покое она в боку) — тоже: поднял лапу — снизу пушистая
  const segT = (R, A, B) => { const dx = B[0] - A[0], dy = B[1] - A[1], dz = B[2] - A[2]; const t = ((R[0] - A[0]) * dx + (R[1] - A[1]) * dy + (R[2] - A[2]) * dz) / (dx * dx + dy * dy + dz * dz || 1), tc = Math.max(0, Math.min(1, t));
    return [Math.hypot(R[0] - A[0] - dx * tc, R[1] - A[1] - dy * tc, R[2] - A[2] - dz * tc), t]; };
  const underOk = !(src.armR > 0 && SH && WR) ? null : (R, N, rg) => { const a = segT(R, SH[0], WR[0]), b = segT(R, SH[1], WR[1]); const [d, t] = a[0] < b[0] ? a : b;
    const sd = R[0] > 0 ? 1 : -1, nx = N[0] * sd; if (t < (partId === 0 ? .12 : .03) || d > src.armR + 0.004) return false;
    if (partId === 0) return (rg === 0 || rg === 5 || rg === 6) && t < .95 && nx > .3;         // бок туловища под лапой (в данных он там «лапа»)
    if (partId === 2 || partId === 3) return (rg === 5 || rg === 0 || rg === 6) && t < .85 && nx < .05;   // лапа изнутри (не кисть, не плечо; в данных она там «туловище»)
    return false; };
  const roots = [], rec = [];
  for (let s = 0; s < want; s++) {
    const x = r() * tot; let lo = 0, hi = nt - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (cum[m] < x) lo = m + 1; else hi = m; }
    const a = I[lo * 3], b = I[lo * 3 + 1], c = I[lo * 3 + 2]; let u1 = r(), u2 = r(); if (u1 + u2 > 1) { u1 = 1 - u1; u2 = 1 - u2; } const w0 = 1 - u1 - u2;
    const near = w0 >= u1 && w0 >= u2 ? a : u1 >= u2 ? b : c;
    let rg = FD[near * 5 + 4]; const R = [0, 1, 2].map(k => P[a * 3 + k] * w0 + P[b * 3 + k] * u1 + P[c * 3 + k] * u2);
    const N = nrm3([0, 1, 2].map(k => (Nn[a * 3 + k] * w0 + Nn[b * 3 + k] * u1 + Nn[c * 3 + k] * u2) / 127));
    let underArm = false;
    if (FD[near * 5 + 3] < 128) { // «можно ли расти» на ближайшей вершине; под лапой и на лапе изнутри — да, но короче
      if (!underOk || !underOk(R, N, rg)) continue; underArm = true; rg = partId === 0 ? (rg === 6 ? 6 : 0) : 5; }
    const col = [0, 1, 2].map(k => (FD[a * 5 + k] * w0 + FD[b * 5 + k] * u1 + FD[c * 5 + k] * u2) / 255);
    // откуда растёт
    let f; const side = R[0] > 0 ? 1 : 0; const sub = (p, q) => [p[0] - q[0], p[1] - q[1], p[2] - q[2]];
    if (rg === 1 || rg === 3 || rg === 2) f = sub(R, NO);
    else if (rg === 4) f = sub(R, [NO[0] + EO[0], NO[1] + EO[1], NO[2] + EO[2]]);
    else if (rg === 0) f = sub(R, NE);
    else if (rg === 5) f = sub(WR[side], SH[side]);
    else if (rg === 6) f = sub(FO[side], HI[side]);
    else if (rg === 7) { let bi = 0, bd = 1e9; for (let j = 0; j < TL.length - 1; j++) { const mx = (TL[j][0] + TL[j + 1][0]) / 2 - R[0], my = (TL[j][1] + TL[j + 1][1]) / 2 - R[1], mz = (TL[j][2] + TL[j + 1][2]) / 2 - R[2]; const d = mx * mx + my * my + mz * mz; if (d < bd) { bd = d; bi = j; } } f = sub(TL[bi + 1], TL[bi]); }
    else if (rg === 8) f = [0, 1, 0]; else f = sub(R, NE);
    nrm3(f); const dn = cfg.down[rg] || 0; f[0] += D[0] * dn; f[1] += D[1] * dn; f[2] += D[2] * dn;
    let fn = f[0] * N[0] + f[1] * N[1] + f[2] * N[2]; f[0] -= N[0] * fn; f[1] -= N[1] * fn; f[2] -= N[2] * fn; nrm3(f);
    let L = cfg.L[rg] || 0.01, lean = cfg.lean[rg] || 1.18; if (L <= 0) continue;
    const xB = R[0], yB = -R[2], zB = R[1]; // правила областей записаны в осях Blender
    if (rg === 1 && cfg.front) { const q = cfg.front; const fr = Math.min(1, Math.max(0, (-(yB - q[0]) / q[1] - q[2]) * q[3])) * Math.min(1, Math.max(0, (q[4] - zB) * q[5])); L *= 1 - q[6] * fr; lean += q[7] * fr; }
    if (rg === 1 && cfg.ruff) { const q = cfg.ruff; if (Math.abs(xB) > q[0] && zB < q[2] && zB > q[1]) { L *= 1 + Math.min(q[4], Math.max(0, (Math.abs(xB) - q[0]) * q[3])); lean += q[5]; } }
    if (rg === 0 && cfg.chest) { const q = cfg.chest; if (yB < q[0] && zB > q[1]) L *= q[2]; }
    if (rg === 4 && cfg.earTip) { const q = cfg.earTip; if (zB > q[0]) { L *= 1 + (zB - q[0]) * q[1]; lean = .5; } }
    if (rg === 7 && cfg.tailTip) { const q = cfg.tailTip; if (zB > q[0]) L *= q[1]; }
    L *= .82 + .36 * r(); const guard = r() < .12; if (guard && rg !== 3) L *= 1.35; if (underArm) L *= partId === 0 ? .7 : .85;
    // разброс
    let j = nrm3([r() * 2 - 1, r() * 2 - 1, r() * 2 - 1]); const jn = j[0] * N[0] + j[1] * N[1] + j[2] * N[2]; j = [j[0] - N[0] * jn, j[1] - N[1] * jn, j[2] - N[2] * jn];
    f = nrm3([f[0] + j[0] * .28, f[1] + j[1] * .28, f[2] + j[2] * .28]);
    const cl = Math.cos(lean), sl = Math.sin(lean); const d0 = nrm3([N[0] * cl + f[0] * sl, N[1] * cl + f[1] * sl, N[2] * cl + f[2] * sl]);
    const cr = [N[1] * f[2] - N[2] * f[1], N[2] * f[0] - N[0] * f[2], N[0] * f[1] - N[1] * f[0]]; nrm3(cr); const ck = (r() - .5) * .25;
    const shade = (1.04 - .08 * r()) * (guard ? .96 : 1);
    if (underArm) { out.under = (out.under || 0) + 1; if (H6.dbgUnder) col[0] = 1, col[1] = 0, col[2] = 0; }
    rec.push({ R, N, f, d0, L, cr: [cr[0] * ck, cr[1] * ck, cr[2] * ck], col: [col[0] * shade, col[1] * shade, col[2] * shade], rad: rg === 3 ? cfg.radLid : cfg.rad, lid: rg === 3 });
  }
  // пряди: кончики соседних волосков тянутся к общему центру
  const CELL = cfg.cell, cells = new Map();
  const key = R => { const ix = Math.floor((R[0] + .0057) / CELL), iy = Math.floor((R[1] + .0031) / CELL), iz = Math.floor((R[2] + .0043) / CELL); return ((ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791)) >>> 0; };
  for (const h of rec) { const k = key(h.R); let c = cells.get(k); if (!c) cells.set(k, c = [0, 0, 0, 0]); c[0] += h.R[0]; c[1] += h.R[1]; c[2] += h.R[2]; c[3]++; h.k = k; }
  const K = 5; let base = out.n;
  for (const h of rec) {
    const c = cells.get(h.k); const pull = [c[0] / c[3] - h.R[0], c[1] / c[3] - h.R[1], c[2] / c[3] - h.R[2]]; const pn = pull[0] * h.N[0] + pull[1] * h.N[1] + pull[2] * h.N[2];
    pull[0] -= h.N[0] * pn; pull[1] -= h.N[1] * pn; pull[2] -= h.N[2] * pn; const clump = h.lid ? 0 : cfg.clump;
    const o = out.n * K * 4;
    for (let k = 0; k < K; k++) { const t = k / (K - 1), t2 = t * t, tp = Math.pow(t, 1.6);
      for (let q = 0; q < 3; q++) { const bend = (h.f[q] * .35 + D[q] * .12 + h.cr[q]) * t2; let v = h.R[q] + (h.d0[q] * t + bend) * h.L + pull[q] * clump * tp; if (k === 0) v -= h.N[q] * .0015; out.pts[o + k * 4 + q] = v; }
      out.pts[o + k * 4 + 3] = partId; }
    const c4 = out.n * 4; out.col[c4] = Math.min(255, h.col[0] * 255); out.col[c4 + 1] = Math.min(255, h.col[1] * 255); out.col[c4 + 2] = Math.min(255, h.col[2] * 255); out.col[c4 + 3] = Math.min(255, h.rad / .001 * 255);
    out.nrm[c4] = Math.round(h.N[0] * 127 + 128); out.nrm[c4 + 1] = Math.round(h.N[1] * 127 + 128); out.nrm[c4 + 2] = Math.round(h.N[2] * 127 + 128); out.nrm[c4 + 3] = 255;
    out.n++; if (out.n >= out.cap) break;
  }
  return out.n - base;
}
function unpackPos(z, n, lo0, sc) { const p = new Float32Array(n * 3);
  for (let c = 0; c < 3; c++) { let v = 0; const lo = c * n, hi = 3 * n + c * n; for (let i = 0; i < n; i++) { const u = z[lo + i] | (z[hi + i] << 8); const d = (u >>> 1) ^ -(u & 1); v = (v + d) & 0xFFFF; p[i * 3 + c] = lo0[c] + v * sc[c]; } }
  return p; }
function unpackIdx(b, ni) { const idx = new Uint32Array(ni); let mx = -1, j = 0;
  for (let i = 0; i < b.length && j < ni;) { let v = 0, sh = 0, x; do { x = b[i++]; v += (x & 127) * Math.pow(2, sh); sh += 7; } while (x & 128); const back = (v & 1) ? -(v + 1) / 2 : v / 2; const I = mx + 1 - back; idx[j++] = I; if (I > mx) mx = I; }
  return idx; }
async function loadHero(base, name) {
  const man = await fetchJSON(base + name + '.json'); const files = {}, need = new Set();
  const walk = o => { if (o && typeof o === 'object') { if (o.file) need.add(o.file); for (const k in o) walk(o[k]); } }; walk(man.skins); walk(man.small);
  await Promise.all([...need].map(async f => { files[f] = await fetchBuf(base + f); }));
  const get = m => { if (!m) return null; const T = { float32: Float32Array, int8: Int8Array, uint8: Uint8Array, uint32: Uint32Array, uint16: Uint16Array, int32: Int32Array }[m.type]; return new T(files[m.file], m.off, m.n); };
  const undelta = d => { const o = new Uint32Array(d.length); let s = 0; for (let i = 0; i < d.length; i++) { s += d[i]; o[i] = s; } return o; };
  const skins = {}; for (const k in man.skins) { const s = man.skins[k]; let p, idx, nr;
    if (s.pz) { // v6.1: разности координат (байты отдельно) + номера «шаг назад» + нормали считаем сами
      const n = s.nv; p = unpackPos(get(s.pz), n, s.lo, s.sc);
      idx = unpackIdx(get(s.iv), s.ni);
      const acc = new Float32Array(n * 3), cut = s.cut;
      for (let t = 0; t < idx.length; t += 3) { const a = idx[t] * 3, bb = idx[t + 1] * 3, c = idx[t + 2] * 3;
        if (cut != null && Math.abs(p[a + 1] - cut) < 3e-5 && Math.abs(p[bb + 1] - cut) < 3e-5 && Math.abs(p[c + 1] - cut) < 3e-5) continue; // крышка среза
        const ux = p[bb] - p[a], uy = p[bb + 1] - p[a + 1], uz = p[bb + 2] - p[a + 2], vx = p[c] - p[a], vy = p[c + 1] - p[a + 1], vz = p[c + 2] - p[a + 2];
        const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx; for (const o of [a, bb, c]) { acc[o] += nx; acc[o + 1] += ny; acc[o + 2] += nz; } }
      nr = new Int8Array(n * 3); for (let i = 0; i < n; i++) { const x = acc[i * 3], y = acc[i * 3 + 1], w = acc[i * 3 + 2], l = Math.hypot(x, y, w) || 1; nr[i * 3] = Math.round(x / l * 127); nr[i * 3 + 1] = Math.round(y / l * 127); nr[i * 3 + 2] = Math.round(w / l * 127); }
    } else { const q = get(s.pq); p = new Float32Array(q.length);
      for (let i = 0; i < q.length; i += 3) { p[i] = s.lo[0] + q[i] * s.sc[0]; p[i + 1] = s.lo[1] + q[i + 1] * s.sc[1]; p[i + 2] = s.lo[2] + q[i + 2] * s.sc[2]; }
      idx = undelta(get(s.id)); nr = get(s.n); }
    skins[k] = { p, n: nr, idx, c: get(s.c), fd: get(s.f), part: s.part, nv: s.nv }; }
  const small = {}; for (const k in man.small) { const s = man.small[k];
    small[k] = s.pz ? { p: unpackPos(get(s.pz), s.nv, s.lo, s.sc), idx: unpackIdx(get(s.iv), s.ni), mat: s.mat, col: s.col, part: s.part } : { p: get(s.p), idx: undelta(get(s.id)), mat: s.mat, col: s.col, part: s.part }; }
  return { info: man.info, skins, small };
}
function furWant(skin, cfg, k) { if (!skin.fd) return 0; const P = skin.p, I = skin.idx, FD = skin.fd; let a = 0;
  for (let t = 0; t < I.length; t += 3) { const i0 = I[t], i1 = I[t + 1], i2 = I[t + 2]; const ux = P[i1 * 3] - P[i0 * 3], uy = P[i1 * 3 + 1] - P[i0 * 3 + 1], uz = P[i1 * 3 + 2] - P[i0 * 3 + 2], vx = P[i2 * 3] - P[i0 * 3], vy = P[i2 * 3 + 1] - P[i0 * 3 + 1], vz = P[i2 * 3 + 2] - P[i0 * 3 + 2];
    a += .5 * Math.hypot(uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx); } return Math.round(a * cfg.K * k); }
function rnd(i) { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
function jit(d, ang, i, n) { if (n === 1) return d.clone(); const a = i * 2.39996, r = Math.sqrt((i + .5) / n) * ang; const t1 = new THREE.Vector3(0, 1, 0).cross(d).normalize(), t2 = d.clone().cross(t1);
  return d.clone().addScaledVector(t1, Math.cos(a) * r).addScaledVector(t2, Math.sin(a) * r).normalize(); }

// ================= БАРС: герои образца 6.2 в сценах «Мультиков» =================
// Шерсть растит телефон (по правилам героя), свет запекается ОДИН раз в осях героя (как в образце: небо, земля, солнце,
// ключевой, заливной и контровой свет) — «неон»: в кадре свет места только приглушает/подсвечивает прошитые каналы.
function fetchBuf(url) {
  const E = global.BARS_H6_DATA, key = String(url).split('/').pop();   // данные, встроенные в страницу (артефакт без .wasm-файлов)
  if (E && E[key]) { const s = atob(E[key]); const u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); delete E[key];
    return Promise.resolve(u.buffer).then(async b => { H6.dl += b.byteLength; const h = new Uint8Array(b, 0, 2); if (h[0] === 0x1f && h[1] === 0x8b) b = await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer(); return b; }); }
  return new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', url, true); x.responseType = 'arraybuffer';
    x.onload = () => ((x.status === 200 || x.status === 0) && x.response && x.response.byteLength) ? res(x.response) : rej(new Error('нет ' + url)); x.onerror = () => rej(new Error('нет ' + url)); x.send(); })
    .then(async b => { H6.dl += b.byteLength; const u = new Uint8Array(b, 0, 2); if (u[0] === 0x1f && u[1] === 0x8b) b = await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer(); return b; });
}
const fetchJSON = url => fetchBuf(url).then(b => JSON.parse(new TextDecoder().decode(b)));
const yieldUI = () => new Promise(r => setTimeout(r, 0));

const NAMES = { pik: { kind: 'mouse', re: /^\s*пик(?![а-яё])/i, k: .56, bounce: [0.36, 0.35, 0.33] }, ron: { kind: 'dog', re: /^\s*рон(?![а-яё])/i, k: .82, bounce: [0.34, 0.35, 0.36] }, barsik: { kind: 'cat', re: /^\s*барсик(?![а-яё])/i, k: 1, bounce: [0.5, 0.36, 0.24], opt: true } };
H6.useBarsik = false;   // Барсик образца 6.2 (шерсть растит телефон, свет как в Blender) вместо «неонового»
H6.whoIs = spec => { if (!spec) return null; const nm = String(spec.name || ''); for (const k in NAMES) if ((!NAMES[k].opt || H6.useBarsik) && spec.kind === NAMES[k].kind && NAMES[k].re.test(nm)) return k; return null; };
H6.isHero = spec => !!H6.whoIs(spec);
H6.wantFor = lib => { const out = new Set(); for (const c0 of Object.values((lib && lib.characters) || {})) { const c = (c0 && c0.spec) || c0 || {}; const nm = String(c.name || c.title || ''); for (const k in NAMES) if ((!NAMES[k].opt || H6.useBarsik) && NAMES[k].re.test(nm) && (!c.kind || c.kind === NAMES[k].kind)) out.add(k); } return [...out]; };   // по имени: вид героя в библиотеке может появиться позже

// лампы как в Blender-версии (render.py): в осях героя, герой стоит в начале координат
function lamps() { return {
  sunD: new THREE.Vector3(-0.55, 0.67, 0.5).normalize(), sunC: new THREE.Color(1.0, 0.85, 0.66).multiplyScalar(3.6),
  key: { pos: new THREE.Vector3(-1.3, 1.55, 1.5), size: 1.6, P: 70, col: new THREE.Color(1.0, 0.95, 0.88) },
  fill: { pos: new THREE.Vector3(1.6, 0.6, 1.0), size: 2.0, P: 45, col: new THREE.Color(0.75, 0.9, 1.0) },
  rim: { pos: new THREE.Vector3(-0.7, 1.35, -1.1), size: 0.8, P: 260, col: new THREE.Color(1.0, 0.9, 0.75) },
  eye: { pos: new THREE.Vector3(0.25, 1.05, 2.0), P: 8, col: new THREE.Color(1, .97, .93) },
  sky: new THREE.Color(0.42, 0.62, 0.6).multiplyScalar(0.9), gnd: new THREE.Color(0.05, 0.09, 0.03), gndR: new THREE.Color(0.075, 0.085, 0.05), areaK: 1 / Math.PI }; }
function lightsFor(L, c) {
  const E = l => { const d2 = Math.max(.6, l.pos.distanceToSquared(c)); return l.col.clone().multiplyScalar(l.P * L.areaK / d2); }, D = l => l.pos.clone().sub(c).normalize();
  return { uSunD: { value: L.sunD.clone() }, uSunC: { value: L.sunC.clone() }, uKeyD: { value: D(L.key) }, uKeyC: { value: E(L.key) }, uRimD: { value: D(L.rim) }, uRimC: { value: E(L.rim).multiplyScalar(.35) },
    uFillD: { value: D(L.fill) }, uFillC: { value: E(L.fill) }, uEyeD: { value: D(L.eye) }, uEyeC: { value: E(L.eye) }, uSky: { value: L.sky.clone() }, uGnd: { value: L.gnd.clone() } }; }
// общие ручки каждого героя: туман места, «неба больше/меньше», выдержка, ноги, направления, под которые прошит свет
function commonU(bakeL) { return { uMistS: { value: 0 }, uMistD: { value: 0 }, uMistK: { value: 0 }, uMistC: { value: new THREE.Color(0.6, 0.7, 0.7) },
  uSkyK: { value: new THREE.Vector3(1, 1, 1) }, uExpo: { value: 1 }, uLegM: { value: [new THREE.Matrix4(), new THREE.Matrix4()] },
  uBkSun: { value: bakeL.uSunD.value.clone() }, uBkKey: { value: bakeL.uKeyD.value.clone() }, uBkRim: { value: bakeL.uRimD.value.clone() }, uBkFill: { value: bakeL.uFillD.value.clone() } }; }

H6.dl = 0; H6.T = {}; H6.log = [];
const hlog = (...a) => { const s = a.join(' '); H6.log.push(s); try { console.log('BARS ' + s); } catch (e) {} };

// ---------- сборка героя: данные → шаблон (сетки, текстуры шерсти, рецепты материалов) ----------
async function buildTemplate(name) {
  const t0 = now(); const D = await loadHero(H6.base, name); const info = D.info, NM = NAMES[name];
  const T = { name, info, items: [], t: {} }; T.t.load = now() - t0;
  // голова: середина головы по коже — по ней приложение кадрирует «крупно» и подбирает размер
  { const s = D.skins.head; let y0 = 1e9, y1 = -1e9, x0 = 1e9, x1 = -1e9; for (let i = 0; i < s.nv; i++) { const x = s.p[i * 3], y = s.p[i * 3 + 1]; if (y < y0) y0 = y; if (y > y1) y1 = y; if (x < x0) x0 = x; if (x > x1) x1 = x; }
    T.headC = (y0 + y1) / 2; T.headR = (x1 - x0) / 2; T.headTop = y1; }
  T.center = new THREE.Vector3(0, 0.55 * NM.k, 0);
  const L = T.L = lamps(); T.bakeU = lightsFor(L, T.center);
  const V3 = a => new THREE.Vector3(a[0], a[1], a[2]);
  T.PIV = {}; for (const k in info.piv) T.PIV[k] = V3(info.piv[k]);
  T.hip = info.src.hip.map(V3); T.ankleY = Math.max(info.src.foot[0][1], 0) + 0.02;
  // ---- шерсть: растит телефон ----
  const cfg = info.fur, src = info.src, kS = H6.furK; let cap = 0;
  if (src.should && src.wrist && !(src.armR > 0)) { const ds = []; for (const sk of ['armL', 'armR']) { const s = D.skins[sk]; if (!s) continue; const P = s.p, n = P.length / 3;   // толщина лапы — по её коже
      for (let i = 0; i < n; i += 5) { const R = [P[i * 3], P[i * 3 + 1], P[i * 3 + 2]]; let d = 1e9; for (let j = 0; j < 2; j++) { const A = src.should[j], B = src.wrist[j]; const dx = B[0] - A[0], dy = B[1] - A[1], dz = B[2] - A[2];
        const t = Math.max(0, Math.min(1, ((R[0] - A[0]) * dx + (R[1] - A[1]) * dy + (R[2] - A[2]) * dz) / (dx * dx + dy * dy + dz * dz || 1))); d = Math.min(d, Math.hypot(R[0] - A[0] - dx * t, R[1] - A[1] - dy * t, R[2] - A[2] - dz * t)); } ds.push(d); } }
    if (ds.length) { ds.sort((x, y) => x - y); src.armR = ds[Math.floor(ds.length * .8)]; } }
  for (const sk of ['body', 'feet', 'head', 'armL', 'armR', 'tail', 'head_blink']) if (D.skins[sk]) cap += furWant(D.skins[sk], cfg, kS);
  cap = Math.ceil(cap * 1.05) + 100; const out = { pts: new Float32Array(cap * 5 * 4), col: new Uint8Array(cap * 4), nrm: new Uint8Array(cap * 4), n: 0, cap };
  const tf = now(); let si = 0; const seedH = name === 'pik' ? 2 : 3;
  for (const [sk, pid] of [['body', 0], ['feet', 0], ['head', 1], ['armL', 2], ['armR', 3], ['tail', 4], ['head_blink', 5]]) if (D.skins[sk]) { growFur(D.skins[sk], cfg, src, pid, out, seedH * 1000 + (si++) * 17 + 3, kS); await yieldUI(); }
  // ноги: волоски тела ниже бедра идут за ногой (вес по высоте корня), сторона — по x
  for (let i = 0; i < out.n; i++) { const o = i * 20; if (out.pts[o + 3] !== 0) continue; const w = legW(T, out.pts[o], out.pts[o + 1]); if (w <= 0) continue;
    const code = legCode(0, w, out.pts[o]); for (let k = 0; k < 5; k++) out.pts[o + k * 4 + 3] = code; }
  T.t.fur = now() - tf; T.nFur = out.n;
  T.fur = { ptsTex: dataTex(out.pts.subarray(0, out.n * 5 * 4), out.n * 5), colTex: (() => { const t = dataTex(out.col.subarray(0, out.n * 4), out.n, THREE.UnsignedByteType); t.colorSpace = THREE.NoColorSpace; return t; })(),
    nrmTex: dataTex(out.nrm.subarray(0, out.n * 4), out.n, THREE.UnsignedByteType), n: out.n, k: 5 };
  T.fur.posTex = T.fur.ptsTex;
  // ---- кожа частей ----
  const PART = { body: 0, head: 1, armL: 2, armR: 3, tail: 4 }; let base = 0;
  const geoOf = (sk) => { const s = D.skins[sk]; const n = s.nv, P = new Float32Array(n * 3), Nn = new Float32Array(n * 3), C = new Float32Array(n * 4), LG = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) { P[i * 3] = s.p[i * 3]; P[i * 3 + 1] = s.p[i * 3 + 1]; P[i * 3 + 2] = s.p[i * 3 + 2]; Nn[i * 3] = s.n[i * 3] / 127; Nn[i * 3 + 1] = s.n[i * 3 + 1] / 127; Nn[i * 3 + 2] = s.n[i * 3 + 2] / 127;
      for (let c = 0; c < 4; c++) C[i * 4 + c] = s.c[i * 4 + c] / 255;
      if (s.part === 'body' || s.part === 'feet') { const w = legW(T, P[i * 3], P[i * 3 + 1]); LG[i * 2] = w; LG[i * 2 + 1] = P[i * 3] > 0 ? 1 : 0; } }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.BufferAttribute(Nn, 3)); g.setAttribute('color', new THREE.BufferAttribute(C, 4)); g.setAttribute('aLeg', new THREE.BufferAttribute(LG, 2)); g.setIndex(new THREE.BufferAttribute(s.idx, 1)); return g; };
  const item = (geo, matId, alb, o) => { if (!geo.attributes.normal) geo.computeVertexNormals(); const n = geo.attributes.position.count;
    if (!geo.attributes.color) { const c = new Float32Array(n * 4).fill(1); for (let i = 3; i < c.length; i += 4) c[i] = 0; geo.setAttribute('color', new THREE.BufferAttribute(c, 4)); }
    if (!geo.attributes.aLeg) geo.setAttribute('aLeg', new THREE.BufferAttribute(new Float32Array(n * 2), 2));
    const it = Object.assign({ geo, matId, alb: alb || [1, 1, 1], base, group: 'body', part: 0 }, o || {}); base += n; T.items.push(it); return it; };
  for (const sk of ['body', 'feet', 'armL', 'armR', 'tail']) if (D.skins[sk]) item(geoOf(sk), 1, null, { sss: true, name: sk, group: sk === 'feet' ? 'body' : sk, part: PART[sk === 'feet' ? 'body' : sk] });
  for (const [k, sk] of [['base', 'head'], ['a', 'head_a'], ['o', 'head_o'], ['blink', 'head_blink']]) if (D.skins[sk]) item(geoOf(sk), 1, null, { sss: true, name: sk, group: 'head', part: 1, head: k, noOcc: k !== 'base' });
  const MAT = { nose: 6, tooth: 6, scarf: 4, satin: 9, cloth: 10, gold: 8 };
  for (const k in D.small) { const s = D.small[k];
 const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(s.p, 3)); g.setIndex(new THREE.BufferAttribute(s.idx, 1));
    const isNose = s.mat === 'nose'; item(g, MAT[s.mat] || 0, isNose ? info.nose.col : s.col, { name: k, group: s.part, part: PART[s.part], wet: isNose && info.nose.wet }); }
  // ---- глаза: стоят по осям головы, радужка повёрнута отдельно (v6.2) ----
  const RE = info.re; T.eyes = [];
  for (let ei = 0; ei < info.eyes.length; ei++) { const cv = V3(info.eyes[ei]); const eS = new THREE.Vector3(...(info.eyeS || [1, 1, 1]));
    const dL = new THREE.Vector3(...(info.eyeDirs ? info.eyeDirs[ei] : [0, 0, 1])).normalize(), iq = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), dL);
    const it = item(new THREE.SphereGeometry(RE, 48, 36), 5, null, { pos: cv, quat: new THREE.Quaternion(), scale: eS, name: 'eye', group: 'head', part: 1, iris: info.iris, eyeK: info.eyeK, irisS: info.irisS || 0, eye: ei });
    it.irisInv = new THREE.Matrix4().makeRotationFromQuaternion(iq).invert();
    T.eyes.push({ it, c: cv, dL, iq, co: { geo: new THREE.SphereGeometry(RE * .872, 40, 28), pos: dL.clone().multiplyScalar(RE * 0.208), quat: iq.clone() } }); }
  // ---- рот, складки век, усы ----
  const tube = (pts, r0, r1, alb, name, o2) => { const cv = new THREE.CatmullRomCurve3(pts.map(V3)); const g = new THREE.TubeGeometry(cv, 24, 1, 6, false);
    const pa = g.attributes.position, na = g.attributes.normal; for (let i = 0; i < pa.count; i++) { const t = Math.floor(i / 7) / 24; const P0 = cv.getPointAt(Math.min(1, t)); const r = r0 + (r1 - r0) * t;
      pa.setXYZ(i, P0.x + na.getX(i) * r, P0.y + na.getY(i) * r, P0.z + na.getZ(i) * r); } return item(g, 0, alb, Object.assign({ name, group: 'head', part: 1 }, o2 || {})); };
  const sc = RE / 0.061;
  if (info.mouth) { const pad = (info.fur && info.fur.L ? info.fur.L[2] || .005 : .005) + .002; T.mouthZ = {}; for (const k in info.mouth) { const z = info.mouth[k]; T.mouthZ[k] = { c: z.c, r: z.r.map(x => x + pad) }; } }   // где шерсть прячется, пока рот открыт
  T.mouthB = info.lines.mouth_base.map(l => tube(l, .0017 * sc, .0015 * sc, [0.12, 0.04, 0.03], 'mouth'));
  T.mouthO = info.lines.mouth_open.map(l => tube(l, .0017 * sc, .0015 * sc, [0.12, 0.04, 0.03], 'mouthO', { noOcc: true }));
  T.creases = info.lines.creases.map(l => tube(l, .0012 * sc, .0024 * sc, [0.07, 0.035, 0.02], 'crease', { noOcc: true }));
  info.lines.whisk.forEach(l => tube(l, info.whisk.r[0], info.whisk.r[1], info.whisk.col, 'whisk'));
  T.nSurf = base;
  // ---- приёмники света кожи (поза покоя, оси героя) ----
  const P = new Float32Array(base * 4), Dd = new Float32Array(base * 4); const v = new THREE.Vector3(), nn = new THREE.Vector3(), M = new THREE.Matrix4(), NMx = new THREE.Matrix3();
  for (const it of T.items) { const g = it.geo, pa = g.attributes.position, na = g.attributes.normal, ca = g.attributes.color;
    M.compose(it.pos || new THREE.Vector3(), it.quat || new THREE.Quaternion(), it.scale || new THREE.Vector3(1, 1, 1)); NMx.getNormalMatrix(M); it.restN = NMx.clone();
    for (let i = 0; i < pa.count; i++) { v.fromBufferAttribute(pa, i).applyMatrix4(M); nn.fromBufferAttribute(na, i).applyMatrix3(NMx).normalize(); const o = (it.base + i) * 4;
      P[o] = v.x; P[o + 1] = v.y; P[o + 2] = v.z; P[o + 3] = it.part || 0; Dd[o] = nn.x; Dd[o + 1] = nn.y; Dd[o + 2] = nn.z; Dd[o + 3] = it.sss && ca.itemSize === 4 ? ca.getW(i) : 0; } }
  T.set = { posTex: dataTex(P, base), dirTex: dataTex(Dd, base), n: base, kind: 0, tauO: .002 };
  T.t.build = now() - t0 - T.t.load;
  hlog(name, ': шерсть', out.n, 'волосков за', Math.round(T.t.fur), 'мс; сборка', Math.round(T.t.build), 'мс; под лапами', out.under || 0, '(толщина лапы', Math.round((src.armR || 0) * 1000), 'мм)');
  return T;
}
// вес «ноги» для точки покоя: ниже бедра — за ногой, у самого паха — с телом
function legW(T, x, y) { const hy = T.hip[0].y; if (y >= hy) return 0; const a = Math.min(1, (hy - y) / Math.max(.02, hy - T.ankleY));
  const side = Math.min(1, Math.max(0, (Math.abs(x) - .004) / Math.max(.008, Math.abs(T.hip[0].x) * .6))); const w = a * a * (3 - 2 * a) * side; return w < .02 ? 0 : Math.min(1, w); }
function legCode(part, w, x) { return part + 8 * Math.round(w * 63) + 512 * (x > 0 ? 1 : 0); }

// ---------- экземпляр героя (сетки + материалы) — для запекания и для каждого героя в сцене ----------
function instance(T, U, baked) {
  const raw = (vs, fs, uni, extra) => new THREE.RawShaderMaterial(Object.assign({ vertexShader: vs, fragmentShader: fs, uniforms: Object.assign({}, U, uni), glslVersion: THREE.GLSL3 }, extra || {}));
  const root = new THREE.Group(); root.name = 'bars-hero-' + T.name;
  const grp = () => { const g = new THREE.Group(); g.matrixAutoUpdate = false; return g; };
  const G = { body: grp() }; root.add(G.body); for (const nm of ['head', 'armL', 'armR', 'tail']) { G[nm] = grp(); G.body.add(G[nm]); }
  G.legs = [grp(), grp()]; G.legs.forEach(g => G.body.add(g));
  const I = { T, U, root, G, meshes: [], heads: {}, eyes: [], mouthB: [], mouthO: [], creases: [], corn: [] };
  // шерсть
  const fu = { uPts: { value: T.fur.ptsTex }, uCol: { value: T.fur.colTex }, uB0: { value: baked ? T.fur.B[0] : null }, uB1: { value: baked ? T.fur.B[1] : null }, uB2: { value: baked ? T.fur.B[2] : null }, uK: { value: 5 }, uRadK: { value: 0.001 }, uTaper: { value: .85 },
    uPx: { value: .001 }, uMinPx: { value: .6 }, uGR: { value: new THREE.Vector4() }, uGrass: { value: 0 }, uCamDir: { value: new THREE.Vector3() }, uTime: { value: 0 }, uWind: { value: 0 }, uHairK: { value: .095 }, uMS: { value: .25 }, uSpec: { value: .2 }, uDesat: { value: 0 },
    uGold: { value: .85 }, uGoldT: { value: new THREE.Vector3(1, .66, .25) }, uPartM: { value: [0, 1, 2, 3, 4, 5].map(() => new THREE.Matrix4()) }, uBlink: { value: 0 }, uNrm: { value: T.fur.nrmTex }, uLive: { value: baked ? 1 : 0 }, uCull: { value: baked ? 1 : 0 }, uCullK: { value: -.3 }, uKT: { value: .5 }, uDec: { value: 2 },
    uPoseOn: { value: 0 }, uPA: { value: null }, uPB: { value: null }, uPW: { value: 0 }, uDbgS: { value: 0 }, uHideArm: { value: 0 }, uMouthC: { value: new THREE.Vector4() }, uMouthR: { value: new THREE.Vector3(1, 1, 1) } };
  const fmat = raw(strandVS(false), STRAND_FS, fu, { side: THREE.DoubleSide, alphaToCoverage: false });   // alpha-to-coverage на iPhone рисует сетку тёмных точек — шерсть сплошная, сглаживает MSAA
  const fd = raw(strandVS(true), DEPTH_FS, fu, { side: THREE.DoubleSide, colorWrite: false });
  const fg = new THREE.BufferGeometry(); fg.setDrawRange(0, T.fur.n * 4 * 6); fg.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e4);
  const fm = new THREE.Mesh(fg, fmat); fm.frustumCulled = false; fm.userData = { dmat: fd, mat: fmat, strands: true, bars: true }; root.add(fm); I.fur = fm; I.fu = fu; I.meshes.push(fm);
  // кожа и вещи
  const dmat = raw(SURF_DVS, DEPTH_FS, {}, { colorWrite: false, side: THREE.DoubleSide });
  const coMat = () => raw(SURF_VS, CORNEA_FS, { uB0: { value: null }, uB1: { value: null }, uBase: { value: 0 }, uB2: { value: null }, uLiveS: { value: 0 }, uRestN: { value: new THREE.Matrix3() }, uPoseOn: { value: 0 }, uPA: { value: null }, uPB: { value: null }, uPW: { value: 0 } }, { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
  for (const it of T.items) { const ir = it.iris || [[0.06, 0.2, 0.05], [0.16, 0.42, 0.08], [0.35, 0.62, 0.12]];
    const uni = { uB0: { value: baked ? T.set.B[0] : null }, uB1: { value: baked ? T.set.B[1] : null }, uB2: { value: baked ? T.set.B[2] : null }, uBase: { value: it.base }, uMat: { value: it.matId }, uAlb: { value: new THREE.Color().setRGB(...it.alb) }, uCapC: { value: capC(it) }, uRough: { value: .5 }, uEyeM: { value: new THREE.Matrix4() }, uDbg: DBG,
      uGndK: { value: 0 }, uLiveS: { value: baked ? 1 : 0 }, uRestN: { value: it.restN }, uPoseOn: { value: 0 }, uPA: { value: null }, uPB: { value: null }, uPW: { value: 0 },
      uWet: { value: it.wet ? 1 : 0 }, uEyeK: { value: new THREE.Vector2(...(it.eyeK || [.70, .915])) }, uIrisS: { value: it.irisS || 0 }, uIris0: { value: new THREE.Vector3(...ir[0]) }, uIris1: { value: new THREE.Vector3(...ir[1]) }, uIris2: { value: new THREE.Vector3(...ir[2]) } };
    const m = new THREE.Mesh(it.geo, raw(SURF_VS, SURF_FS, uni)); m.frustumCulled = false; m.userData = { dmat, mat: m.material, noOcc: !!it.noOcc, bars: true, it };
    if (it.pos) m.position.copy(it.pos); if (it.quat) m.quaternion.copy(it.quat); if (it.scale) m.scale.copy(it.scale);
    G[it.group].add(m); I.meshes.push(m);
    if (it.head) I.heads[it.head] = m;
    if (it.eye != null) { const e = T.eyes[it.eye]; const co = new THREE.Mesh(e.co.geo, coMat()); co.position.copy(e.co.pos); co.quaternion.copy(e.co.quat); co.userData = { cornea: true, bars: true }; co.frustumCulled = false; m.add(co); I.eyes.push({ e: m, co, irisInv: it.irisInv }); I.corn.push(co); I.meshes.push(co); }
  }
  const byIt = new Map(I.meshes.filter(m => m.userData.it).map(m => [m.userData.it, m]));
  I.mouthB = T.mouthB.map(it => byIt.get(it)); I.mouthO = T.mouthO.map(it => byIt.get(it)); I.creases = T.creases.map(it => byIt.get(it));
  I.restPose = () => { for (const k of ['head', 'armL', 'armR', 'tail', 'body']) G[k].matrix.identity(); G.legs.forEach(g => g.matrix.identity()); setFace(I, 'base', false); root.updateMatrixWorld(true); partMats(I); };
  I.restPose();
  return I;
}
function partMats(I) { const G = I.G, pm = I.fu.uPartM.value; pm[0].copy(G.body.matrixWorld); pm[1].copy(G.head.matrixWorld); pm[2].copy(G.armL.matrixWorld); pm[3].copy(G.armR.matrixWorld); pm[4].copy(G.tail.matrixWorld); pm[5].copy(G.head.matrixWorld);
  I.U.uLegM.value[0].copy(G.legs[0].matrixWorld); I.U.uLegM.value[1].copy(G.legs[1].matrixWorld); }
function setFace(I, m, closed) { for (const k in I.heads) I.heads[k].visible = k === (closed ? 'blink' : m); for (const e of I.eyes) { e.e.visible = !closed; e.co.visible = !closed; }
  for (const o of I.mouthB) o.visible = !closed && m === 'base'; for (const o of I.mouthO) o.visible = !closed && m !== 'base'; for (const o of I.creases) o.visible = closed; I.fu.uBlink.value = closed ? 1 : 0;
  const mz = I.T.mouthZ && !closed && I.T.mouthZ[m]; I.fu.uMouthC.value.set(mz ? mz.c[0] : 0, mz ? mz.c[1] : 0, mz ? mz.c[2] : 0, mz ? 1 : 0); if (mz) I.fu.uMouthR.value.set(mz.r[0], mz.r[1], mz.r[2]); }
const _toB = () => new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
function eyeMats(I) { const r = I.T.info.re, toB = _toB(); for (const e of I.eyes) { const sc = new THREE.Matrix4().makeScale(1 / r, 1 / r, 1 / r); const M = e.e.material.uniforms.uEyeM.value.multiplyMatrices(sc, e.e.matrixWorld.clone().invert()); if (e.irisInv) M.premultiply(e.irisInv); M.premultiply(toB); } }

// ---------- запекание света: один раз на героя, в его осях ----------
function capC(it) {   // кепка: верхушка (пуговка) и нижний край — для швов-клиньев и тени у края
  const v = new THREE.Vector4(0, 0, 0, 0); if (it.matId !== 10 || !it.geo) return v; const p = it.geo.attributes.position; let ty = -1e9, ti = 0, my = 1e9;
  for (let i = 0; i < p.count; i++) { const y = p.getY(i); if (y > ty) { ty = y; ti = i; } if (y < my) my = y; }
  return v.set(p.getX(ti), ty, p.getZ(ti), my); }
async function bakeTemplate(T, R, o) {
  o = o || {}; const t0 = now(); const L = T.L, NM = NAMES[T.name]; const ZERO = new THREE.Color(0, 0, 0);
  const U = Object.assign({}, T.bakeU, commonU(T.bakeU)); const I = instance(T, U, false); const scene = new THREE.Scene(); scene.add(I.root); scene.updateMatrixWorld(true); partMats(I); eyeMats(I);
  const nSky = o.sky || 30, nSun = o.sun || 8, nArea = o.area || 6, res = o.res || 2048;
  const bb = new THREE.Box3(); for (const m of I.meshes) { if (m.userData.cornea) continue; m.geometry.computeBoundingBox && m.geometry.computeBoundingBox(); if (m.geometry.boundingBox && !m.userData.strands) bb.union(m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld)); }
  bb.expandByScalar(0.02);
  const sets = [Object.assign({ name: 'fur', kind: 1, k: 5, tauH: .004 }, T.fur), Object.assign({ name: 'skin' }, T.set)];
  const accOf = set => new THREE.WebGLRenderTarget(TW, Math.max(1, Math.ceil(set.n * (set.kind === 1 ? 5 : 1) / TW)), { type: THREE.HalfFloatType, count: 3, depthBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, generateMipmaps: false });
  const gMat = new THREE.RawShaderMaterial({ vertexShader: 'in vec3 position; void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }', fragmentShader: GATHER_FS, glslVersion: THREE.GLSL3,
    uniforms: { uW: { value: 0 }, uDirect: { value: 0 }, uPosed: { value: 0 }, uOnlyVis: { value: 0 }, uSplit: { value: 0 }, uDepthArm: { value: null }, uPartM: { value: [0, 1, 2, 3, 4, 5].map(() => new THREE.Matrix4()) }, uPos: { value: null }, uDir: { value: null }, uDepth: { value: null }, uFCol: { value: null }, uBounce: { value: new THREE.Color() }, uKT: { value: .85 }, uGrassG: { value: 0 }, uLVP: { value: new THREE.Matrix4() }, uL: { value: new THREE.Vector3() }, uCol: { value: new THREE.Color() }, uMask: { value: new THREE.Vector4() },
      uTexel: { value: .001 }, uRange: { value: 1 }, uTauH: { value: .004 }, uTauS: { value: .006 }, uTauO: { value: .002 }, uAO: { value: 0 }, uKind: { value: 0 }, uK: { value: 1 }, uN: { value: 0 } },
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor, depthTest: false, depthWrite: false });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), gMat); quad.frustumCulled = false; const qScene = new THREE.Scene(); qScene.add(quad); const qCam = new THREE.Camera();
  const prevRT = R.getRenderTarget(), prevCC = R.getClearColor(new THREE.Color()), prevCA = R.getClearAlpha(), prevAC = R.autoClear; R.autoClear = false;
  for (const s of sets) { s.acc = accOf(s); R.setRenderTarget(s.acc); R.setClearColor(0x000000, 0); R.clear(true, false, false); }
  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 200);
  const rt = new THREE.WebGLRenderTarget(res, res, { depthBuffer: true, type: THREE.UnsignedByteType }); rt.depthTexture = new THREE.DepthTexture(res, res, THREE.UnsignedIntType); rt.depthTexture.minFilter = rt.depthTexture.magFilter = THREE.NearestFilter;
  const split = H6.K.splitBake !== false, rtA = split ? new THREE.WebGLRenderTarget(res, res, { depthBuffer: true, type: THREE.UnsignedByteType }) : null;   // тень от лап — отдельно: лапа в покое не затемняет бок
  if (rtA) { rtA.depthTexture = new THREE.DepthTexture(res, res, THREE.UnsignedIntType); rtA.depthTexture.minFilter = rtA.depthTexture.magFilter = THREE.NearestFilter; }
  const armOf = m => !!(m.userData.it && (m.userData.it.part === 2 || m.userData.it.part === 3));
  const bounce = new THREE.Color(...NM.bounce), skyW = 2 * Math.PI / nSky, passes = [];
  for (let i = 0; i < 2 * nSky; i++) { const d = fib(2 * nSky, i);
    if (d.y > 0.02) passes.push([d, L.sky.clone().multiplyScalar(skyW), new THREE.Vector4(0, 0, 0, 0), 1 / nSky, bounce.clone().multiplyScalar(skyW * .5)]);
    else if (d.y < -0.02) passes.push([d, L.gndR.clone().multiplyScalar(skyW), new THREE.Vector4(0, 0, 0, 0), 0, bounce.clone().multiplyScalar(skyW)]); }
  for (let i = 0; i < nSun; i++) passes.push([jit(L.sunD, Math.PI / 180 * 2, i, nSun), L.sunC.clone().multiplyScalar(1 / nSun), new THREE.Vector4(1 / nSun, 0, 0, 0), 0, ZERO]);
  for (const [nm, mk] of [['key', new THREE.Vector4(0, 1, 0, 0)], ['fill', new THREE.Vector4(0, 0, 0, 1)], ['rim', new THREE.Vector4(0, 0, 1, 0)]]) { const l = L[nm], c = T.bakeU['u' + nm[0].toUpperCase() + nm.slice(1) + 'C'].value;
    for (let i = 0; i < nArea; i++) { const sp = l.pos.clone().add(new THREE.Vector3((rnd(i * 3 + 1) - .5) * l.size, (rnd(i * 3 + 2) - .5) * l.size, (rnd(i * 3 + 3) - .5) * l.size)); passes.push([sp.sub(T.center).normalize(), c.clone().multiplyScalar(1 / nArea), mk.clone().multiplyScalar(1 / nArea), 0, ZERO]); } }
  const c = bb.min.clone().add(bb.max).multiplyScalar(.5), ext = bb.max.clone().sub(bb.min).length() * .5; let pi = 0, tY = now();
  for (const [dir, col, mask, ao, bnc] of passes) {
    if (pi > 0 && pi % 4 === 0 && now() - tY > 60) { if (H6.onProgress) try { H6.onProgress(T.name, pi / passes.length); } catch (e) {} await yieldUI(); tY = now(); }
    pi++;
    cam.position.copy(c).addScaledVector(dir, 100); const up = Math.abs(dir.y) > .95 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(0, 1, 0); cam.up.copy(up); cam.lookAt(c); cam.updateMatrixWorld(true);
    const inv = cam.matrixWorldInverse; let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (let k = 0; k < 8; k++) { const p = new THREE.Vector3(k & 1 ? bb.max.x : bb.min.x, k & 2 ? bb.max.y : bb.min.y, k & 4 ? bb.max.z : bb.min.z).applyMatrix4(inv); x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); }
    cam.left = x0; cam.right = x1; cam.bottom = y0; cam.top = y1; cam.near = 100 - ext - 1; cam.far = 100 + ext + 1; cam.updateProjectionMatrix();
    const texel = Math.max(x1 - x0, y1 - y0) / res;
    for (const m of I.meshes) { m.material = m.userData.dmat || m.material; if (m.userData.strands) { const u = m.userData.dmat.uniforms; u.uPx.value = texel; u.uMinPx.value = 0.0; u.uCamDir.value.copy(dir).negate(); } }
    for (const m of I.corn) m.visible = false; for (const m of I.meshes) if (m.userData.noOcc) m.visible = false;
    if (rtA) { const hid = []; for (const m of I.meshes) if (!m.userData.strands && m.visible && armOf(m)) { m.visible = false; hid.push(m); } I.fu.uHideArm.value = 1;
      R.setRenderTarget(rt); R.setClearColor(0xffffff, 1); R.clear(true, true, false); R.render(scene, cam); hid.forEach(m => m.visible = true); hid.length = 0;
      for (const m of I.meshes) if (!m.userData.strands && m.visible && !armOf(m)) { m.visible = false; hid.push(m); } I.fu.uHideArm.value = 2;
      R.setRenderTarget(rtA); R.setClearColor(0xffffff, 1); R.clear(true, true, false); R.render(scene, cam); hid.forEach(m => m.visible = true); I.fu.uHideArm.value = 0;
    } else { R.setRenderTarget(rt); R.setClearColor(0xffffff, 1); R.clear(true, true, false); R.render(scene, cam); }
    for (const m of I.meshes) { if (m.userData.mat) m.material = m.userData.mat; } for (const m of I.corn) m.visible = true; for (const m of I.meshes) if (m.userData.noOcc) m.visible = true;
    const lvp = new THREE.Matrix4().multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    for (const s of sets) { const u = gMat.uniforms; u.uPos.value = s.posTex; u.uDir.value = s.dirTex || s.posTex; u.uDepth.value = rt.depthTexture; u.uDepthArm.value = rtA ? rtA.depthTexture : rt.depthTexture; u.uSplit.value = rtA ? 1 : 0; u.uLVP.value.copy(lvp); u.uL.value.copy(dir); u.uCol.value.copy(col); u.uMask.value.copy(mask);
      u.uDirect.value = mask.lengthSq() > 0 ? 1 : 0; u.uW.value = 1 / (2 * nSky); u.uBounce.value.copy(bnc); u.uFCol.value = s.colTex || s.posTex; u.uGrassG.value = 0; u.uKT.value = o.kt == null ? .5 : o.kt; u.uTexel.value = texel; u.uRange.value = cam.far - cam.near;
      u.uTauH.value = s.tauH || .004; u.uTauO.value = s.tauO || .002; u.uAO.value = ao; u.uKind.value = s.kind; u.uK.value = s.k || 1; u.uN.value = s.n * (s.kind === 1 ? 5 : 1);
      R.setRenderTarget(s.acc); R.render(qScene, qCam); }
  }
  T.fur.B = sets[0].acc.textures; T.set.B = sets[1].acc.textures; T.fur.acc = sets[0].acc; T.set.acc = sets[1].acc;
  rt.dispose(); rt.depthTexture.dispose(); if (rtA) { rtA.dispose(); rtA.depthTexture.dispose(); } gMat.dispose(); quad.geometry.dispose();
  for (const m of I.meshes) { if (m.userData.mat && m.userData.mat !== m.material) m.userData.mat.dispose(); m.material.dispose && m.material.dispose(); }
  R.setRenderTarget(prevRT); R.setClearColor(prevCC, prevCA); R.autoClear = prevAC;
  T.t.bake = now() - t0; T.t.passes = passes.length; hlog(T.name, ': свет запечён за', Math.round(T.t.bake), 'мс,', passes.length, 'проходов');
}

// ---------- загрузка: данные + шерсть + свет (в prepare, до картинки) ----------
H6.need = {};
H6.prepare = async function (T3, R, names, opts) {
  THREE = T3; if (!R) return false; H6._R = R; H6._opts = opts; const list = (names || Object.keys(NAMES)).filter(n => NAMES[n]); let ok = true;
  for (const n of list) { if (H6.ready[n]) continue;
    if (!H6.need[n]) H6.need[n] = (async () => { const T = await buildTemplate(n); await bakeTemplate(T, R, opts); H6.T[n] = T; H6.ready[n] = true; return T; })().catch(e => { hlog(n, 'не загрузился:', e && e.message); H6.need[n] = null; ok = false; });
    await H6.need[n]; }
  // герои, построенные до загрузки, — заново (старая версия из кэша)
  try { const rc = global.MK3D && MK3D.rigs && MK3D.rigs(); if (rc) for (const k in rc) { const r = rc[k]; const w = r && H6.whoIs(r.spec); if (r && w && H6.ready[w] && !r.h6) { r.root.visible = false; if (r.root.parent) r.root.parent.remove(r.root); delete rc[k]; } } } catch (e) {}
  return ok;
};
H6.lost = function () { const was = Object.keys(H6.ready).filter(k => H6.ready[k]); for (const k in H6.ready) { H6.ready[k] = false; H6.need[k] = null; delete H6.T[k]; }
  // видеокарту вернули (приложение сворачивали, экран гас) — шерсть и свет растим заново сами, иначе до конца серии были бы старые Пик и Рон
  if (was.length && H6._R) setTimeout(() => { H6.prepare(THREE, H6._R, was, H6._opts).then(ok => hlog('видеокарта вернулась — герои снова готовы:', was.join(', '), ok ? '' : '(не все)')).catch(e => hlog('после видеокарты:', e && e.message)); }, 300); };

// ---------- герой в сцене ----------
H6.attach = function (T3, rig) {
  THREE = T3; const who = H6.whoIs(rig.spec || rig.n); if (!who || !H6.ready[who]) return false; const T = H6.T[who];
  const U = Object.assign({}, lightsFor(T.L, T.center), commonU(T.bakeU)); const I = instance(T, U, true);
  const k = (rig.P && rig.P.headY ? rig.P.headY : T.headC) / T.headC; I.root.scale.setScalar(k); I.root.userData.noGround = true; rig.pose.add(I.root);
  I.k = k; rig.h6 = I; rig.fur = []; I.rest = { arms: rig.arms.map(g => new THREE.Euler(0, 0, (g.userData.side || (g.position.x < 0 ? -1 : 1)) * .35)), legs: rig.legs.map(g => g.rotation.clone()) };   // покой скелета: лапы отведены на .35 рад — у героя образца они висят вдоль тела (иначе плечи заходят в ошейник)
  rig.root.traverse(o => { if (!o.isMesh || o.userData.bars || o.userData.blob) return; if (o.userData.strands) { o.visible = false; return; } o.layers.set(1); });   // старый герой: только тень и «кости»
  rig.headH = T.headC * k * (rig.scale || 1); rig.headR = T.headR * k * (rig.scale || 1);
  const pre = function (R, scene, cam) { const f = R.info.render.frame; if (I._f === f && I._cam === cam) return; I._f = f; I._cam = cam; camFrame(I, R, cam); };
  I.meshes.forEach(m => { m.onBeforeRender = pre; });
  return true;
};

// поза: из скелета «Мультиков» в части героя
let _m4 = null, _m4b = null, _e = null, _v3 = null;
const about = (P, M, out) => out.makeTranslation(P.x, P.y, P.z).multiply(M).multiply(_m4b.makeTranslation(-P.x, -P.y, -P.z));
H6.frame = function (rig, st, T, L) {
  const I = rig.h6; if (!I) return; const TT = I.T, G = I.G, U = I.U;
  if (!_m4) { _m4 = new THREE.Matrix4(); _m4b = new THREE.Matrix4(); _e = new THREE.Euler(); _v3 = new THREE.Vector3(); }
  // голова
  _e.set(rig.head.rotation.x * .75, rig.head.rotation.y, rig.head.rotation.z * .8, 'XYZ'); G.head.matrix.copy(about(TT.PIV.head, new THREE.Matrix4().makeRotationFromEuler(_e), new THREE.Matrix4()));
  // лапы: разница с покоем скелета, вокруг плеч
  const hc = new THREE.Vector3(0, TT.headC, 0.02), hr = TT.headR * 1.08, wv = new THREE.Vector3();
  rig.arms.forEach((g, i) => { const s = g.position.x < 0 ? 'armL' : 'armR', sg = s === 'armL' ? -1 : 1, wr = TT.info.src.wrist[s === 'armL' ? 0 : 1]; const r0 = I.rest.arms[i];
    const tw = g.userData.tw || 0, twM = tw ? new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(wr[0] - TT.PIV[s].x, wr[1] - TT.PIV[s].y, wr[2] - TT.PIV[s].z).normalize(), tw) : null;   // «привет»: кисть вокруг самой лапы
    const put = (ex) => { _e.set(g.rotation.x - r0.x, tw ? 0 : g.rotation.y - r0.y, (g.rotation.z - r0.z) * .9 + ex, 'XYZ'); const Rm = new THREE.Matrix4().makeRotationFromEuler(_e); if (twM) Rm.multiply(twM); G[s].matrix.copy(about(TT.PIV[s], Rm, new THREE.Matrix4())); wv.set(wr[0], wr[1], wr[2]).applyMatrix4(G[s].matrix);
      const dx = wv.x - hc.x, dy = (wv.y - hc.y) * .9, dz = wv.z - hc.z; return dx * dx + dy * dy + dz * dz > hr * hr || wv.y < hc.y - hr; };
    if (!put(0)) { let done = false; for (let it = 1; it <= 14 && !done; it++) for (const sgn of [-sg, sg]) if (put(sgn * it * .08)) { done = true; break; } if (!done) put(0); } });   // лапа не проваливается в морду
  rig.legs.forEach((g, i) => { const j = g.position.x < 0 ? 0 : 1; const r0 = I.rest.legs[i]; _e.set((g.rotation.x - r0.x) * .8, 0, (g.rotation.z - r0.z) * .5, 'XYZ');
    G.legs[j].matrix.copy(about(TT.hip[j], new THREE.Matrix4().makeRotationFromEuler(_e), new THREE.Matrix4())); });
  // хвост
  if (rig.tail) { _e.set(rig.tail.rotation.x * .5, rig.tail.rotation.y * .8, rig.tail.rotation.z * .5, 'XYZ'); G.tail.matrix.copy(about(TT.PIV.tail, new THREE.Matrix4().makeRotationFromEuler(_e), new THREE.Matrix4())); }
  // дыхание
  const br = rig.body ? (rig.body.scale.y - 1) : 0; G.body.matrix.makeScale(1 + br * .5, 1 + br * .3, 1 + br * .5);
  // рот и моргание
  let open = 0; if (rig.mouthPatch && rig.mouthPatch.material.userData.U) open = rig.mouthPatch.material.userData.U.uOpen.value; else if (rig.open) open = rig.open.visible ? Math.min(1, (rig.open.scale.y - 0.25) / 1.1) : 0;
  const vz = st.vz || {}; let m = 'base'; if (open > .22) m = (vz.o || 0) > (vz.w || 0) * 1.1 ? 'o' : 'a';
  const e0 = rig.eyes && rig.eyes[0]; let lid = 1; if (e0 && e0.g) { const sx = e0.g.scale.x || 1, sy = e0.g.scale.y; lid = 1 - Math.min(1, Math.max(0, (1 - sy / sx) / 0.92)); }
  const emo = st.emo || 'neutral'; if (emo === 'sleepy') lid *= .45;
  setFace(I, m, lid < .25);   /* закрыты только при моргании и сне; прищур от улыбки — глаза открыты */
  I.L = L; I.T3 = T;
  I.fu.uTime.value = T || 0;
};
function camFrame(I, R, cam) {
  const U = I.U, L = I.L || {}, TT = I.T; I.root.updateMatrixWorld(true); partMats(I); eyeMats(I);
  const h = R.getRenderTarget() ? R.getRenderTarget().height : R.getContext().drawingBufferHeight; I.fu.uPx.value = 2 * Math.tan((cam.fov || 38) * Math.PI / 360) / Math.max(1, h);
  const MW = I.root.matrixWorld, hc = _v3.set(0, TT.headC, 0).applyMatrix4(MW).clone();
  const toCam = cam.position.clone().sub(hc).normalize(); const camR = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), camU = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
  const K = H6.K;
  // солнце места
  const sun = L.sun, hemi = L.hemi, rim = L.rim;
  if (sun && sun.shadow && !sun.shadow.camera.layers.isEnabled(1)) sun.shadow.camera.layers.enable(1);
  if (sun) { U.uSunD.value.copy(sun.position).sub(sun.target.position).normalize(); U.uSunC.value.setRGB(sun.color.r, sun.color.g, sun.color.b).multiplyScalar(sun.intensity * K.sun); }
  // ключевой и заливной — как в студии, от камеры; сила — от неба места
  let sk = 1, skyC = new THREE.Color(1, 1, 1); if (hemi) { const env = (L.envI || 0) * .8; skyC.setRGB(hemi.color.r * hemi.intensity + env, hemi.color.g * hemi.intensity + env, hemi.color.b * hemi.intensity + env); sk = (skyC.r + skyC.g + skyC.b) / 3; }
  const skL = Math.max(sk, K.skMin != null ? K.skMin : .72);   // вечером небо тусклое — но мордочки героев не темнеют (ключевой и заливной — как днём)
  U.uKeyD.value.copy(toCam).addScaledVector(camR, -.75).addScaledVector(camU, .8).normalize(); U.uKeyC.value.copy(I.T.bakeU.uKeyC.value).multiplyScalar(K.key * skL);
  U.uFillD.value.copy(toCam).addScaledVector(camR, .9).addScaledVector(camU, .1).normalize(); U.uFillC.value.copy(I.T.bakeU.uFillC.value).multiplyScalar(K.fill * skL);
  if (rim && rim.visible !== false) { U.uRimD.value.copy(rim.position).sub(rim.target.position).normalize(); U.uRimC.value.setRGB(rim.color.r, rim.color.g, rim.color.b).multiplyScalar(rim.intensity * K.rim); }
  else { U.uRimD.value.copy(toCam).negate().addScaledVector(camU, .9).normalize(); U.uRimC.value.copy(I.T.bakeU.uRimC.value).multiplyScalar(K.rim0 * sk); }
  U.uEyeD.value.copy(toCam).addScaledVector(camU, .35).addScaledVector(camR, -.25).normalize(); U.uEyeC.value.copy(I.T.bakeU.uEyeC.value).multiplyScalar(K.eye);
  // небо: прошито под небо образца — пересчитываем под небо места
  const s0 = I.T.L.sky; let kr = skyC.r / s0.r, kg = skyC.g / s0.g, kb = skyC.b / s0.b; const km = (kr + kg + kb) / 3;
  { const t = Math.min(1, Math.max(0, (1.3 - km) / .5)), kd = 1 - .5 * t, kf = Math.max(km, K.skyMin != null ? K.skyMin : 1.15) / Math.max(km, 1e-3); // вечер: небо тусклое и синее — на героях синевы вполовину, свет неба не тусклее ~80% дневного (днём и ночью без изменений)
    kr = (km + (kr - km) * kd) * kf; kg = (km + (kg - km) * kd) * kf; kb = (km + (kb - km) * kd) * kf; }
  U.uSkyK.value.set(kr, kg, kb).multiplyScalar(K.sky);
  U.uSky.value.copy(skyC).multiplyScalar(K.sky * .45); if (hemi) U.uGnd.value.setRGB(hemi.groundColor.r, hemi.groundColor.g, hemi.groundColor.b).multiplyScalar(hemi.intensity * .3);
  const f = L.fog; if (f && f.isFog) { U.uMistS.value = f.near; U.uMistD.value = Math.max(1e-3, f.far - f.near); U.uMistK.value = 1; U.uMistC.value.copy(f.color); } else { U.uMistK.value = 0; U.uMistD.value = 0; }
  U.uExpo.value = K.expo;
  H6.dbgL = { sun: sun ? [sun.intensity, sun.color.getHexString()] : null, hemi: hemi ? [hemi.intensity, hemi.color.getHexString(), hemi.groundColor.getHexString()] : null, rim: rim ? [rim.visible, rim.intensity] : null, envI: L.envI, fog: f ? [f.near, f.far] : null, sk };
}
H6.K = { sun: 1.0, key: 1.0, fill: 1.0, rim: 1.0, rim0: .7, eye: 1.0, sky: 1.0, expo: .62 };   // сверено по кадрам: Пик серый, кепка Рона не «горит»

})(typeof window !== "undefined" ? window : globalThis);
