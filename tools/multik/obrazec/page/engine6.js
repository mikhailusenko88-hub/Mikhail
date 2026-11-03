// Образец: Барсик «как в Blender» в нашем движке (three.js r169, WebGL2).
// Свет считается ОДИН раз (запекание): небо, солнце, ключевой/заливной/контровой свет, мягкие тени, просвет сквозь шерсть и уши —
// и записывается в цвет каждой точки кожи, каждого волоска и каждой травинки. На кадре видеокарта только достаёт готовый цвет,
// добавляет блики (они зависят от взгляда камеры), туман, размытие фона и «киношный» цвет.
(function () {
'use strict';
const OB = window.OB = { log: [], t: {} }; const DBG = { value: 0 }; OB.DBG = DBG;
let THREE, R;
const now = () => performance.now();
function log(...a) { const s = a.join(' '); OB.log.push(s); console.log('OB ' + s); }

// ---------- загрузка ----------
const H2F = (() => { const t = new Float32Array(65536); for (let h = 0; h < 65536; h++) { const s = h >> 15, e = (h >> 10) & 31, m = h & 1023; let v;
  if (e === 0) v = m * Math.pow(2, -24); else if (e === 31) v = m ? NaN : Infinity; else v = (1 + m / 1024) * Math.pow(2, e - 15); t[h] = s ? -v : v; } return t; })();
async function loadPack(base) {
  const man = await (await fetch(base + 'barsik.json')).json(); const files = {};
  for (const k in man) if (man[k].file && !files[man[k].file]) files[man[k].file] = await (await fetch(base + man[k].file)).arrayBuffer();
  const get = k => { const m = man[k], b = files[m.file]; const T = { float32: Float32Array, int8: Int8Array, uint8: Uint8Array, uint32: Uint32Array, float16: Uint16Array, int32: Int32Array }[m.type]; return new T(b, m.off, m.n); };
  const env = await (await fetch(base + 'env.json')).json(); const grass = new Float32Array(await (await fetch(base + (man.info.grass || 'grass.bin'))).arrayBuffer());
  return { man, get, info: man.info, env, grass };
}

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
float mistF(vec3 p) { float d = length(p - cameraPosition); float m = clamp((d - uMistS) / uMistD, 0.0, 1.0); return uMistK * m * m; }
`;
const MIST = { uMistS: { value: 3 }, uMistD: { value: 10 }, uMistK: { value: .72 }, uMistC: { value: new THREE_Color(0.56, 0.74, 0.7) } };
function THREE_Color(r, g, b) { return { r, g, b, isColor: true, _lazy: [r, g, b] }; }

// ---------- нити: шерсть и трава, ленточки из текстуры точек (без атрибутов, по gl_VertexID) ----------
function strandVS(depth) { return GL_HEAD + `
uniform sampler2D uPts, uCol, uB0, uB1, uB2, uNrm; uniform int uK; uniform int uLive, uCull; uniform float uCullK, uKT; uniform float uRadK, uTaper, uPx, uMinPx; uniform vec4 uGR; uniform int uGrass; uniform vec3 uCamDir;
uniform float uTime, uWind; uniform mat4 uPartM[6]; uniform int uBlink, uDec; uniform int uPoseOn; uniform sampler2D uPA, uPB; uniform float uPW;
out vec3 vCol; out vec3 vE; out vec4 vVis; out vec3 vT; out vec3 vP; out float vCov; out float vTT; out float vMist;
vec3 P(int i) { return TX(uPts, i).xyz; }
void main() {
  int vid = gl_VertexID; int c = vid % 6; int q = vid / 6; int seg = q % (uK - 1); int s = q / (uK - 1);
  int kk = seg + ((c == 2 || c == 3 || c == 5) ? 1 : 0); float side = (c == 1 || c == 4 || c == 5) ? 1.0 : -1.0;
  int base = s * uK; int i = base + kk; vec4 q0 = TX(uPts, i); int part = int(q0.w + .5); mat4 M = uPartM[part];
  if (part == 5 && uBlink == 0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  ${depth ? 'if (uDec > 1 && s % uDec != 0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }' : ''}
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
  ${depth ? '' : `vec4 b0 = TX(uB0, i), b1 = TX(uB1, i); vE = b0.rgb; vVis = b1; vT = t; vP = wp; vTT = tt; vMist = mistF(wp);
  if (uGrass == 0 && uLive >= 1) { // солнце и лампы — по тому, как волосок лежит СЕЙЧАС
    vec4 b2 = TX(uB2, i); vec3 bR = length(b2.xyz) > 1e-6 ? normalize(b2.xyz) : vec3(0.0, 1.0, 0.0); float ct = 1.0 - 2.0 * clamp(b2.w, 0.0, 1.0);
    bool live = uLive == 1; vec3 bN = live ? normalize(mat3(M) * bR) : bR; vec3 Tn = live ? t : tR; vec3 ke = 1.0 - uKT * vCol; vec4 vn;
    vec4 pv = uPoseOn == 1 ? mix(TX(uPA, i), TX(uPB, i), uPW) : vec4(0.0);
    vec3 Ls[4] = vec3[4](uSunD, uKeyD, uRimD, uFillD); vec3 Cs[4] = vec3[4](uSunC, uKeyC, uRimC, uFillC); vec3 E = vec3(0.0);
    for (int j = 0; j < 4; j++) { float v = uPoseOn == 1 ? pv[j] : (live ? liveVis(b1[j], bR, bN, ct, Ls[j]) : b1[j]); float c = dot(Tn, Ls[j]);
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
  col = mix(col, uMistC, vMist); if (any(isnan(col)) || any(isinf(col))) col = vec3(0.0); col = min(col, vec3(40.0));
  if (uDbgS == 2) col = mix(ae * .8, uMistC, vMist);
  oc = vec4(col, vCov);
}`;
const DEPTH_FS = `precision highp float; out vec4 oc; void main() { oc = vec4(1.0); }`;

// ---------- поверхности (кожа, нос, шарф, глаза, земля, камни, стволы) ----------
const SURF_VS = GL_HEAD + `
uniform mat4 modelMatrix; uniform sampler2D uB0, uB1, uB2, uPA, uPB; uniform int uBase; uniform int uLiveS, uPoseOn; uniform float uPW; uniform mat3 uRestN;
in vec3 position; in vec3 normal; in vec4 color;
out vec3 vE; out vec4 vVis; out vec3 vN; out vec3 vP; out vec4 vC; out vec3 vL; out float vMist; out vec3 vDbg;
void main() { vec4 w = modelMatrix * vec4(position, 1.0); vP = w.xyz; vN = normalize(mat3(modelMatrix) * normal); vL = position;
  int i = uBase + gl_VertexID; vE = TX(uB0, i).rgb; vDbg = vec3(float(gl_VertexID % 4096) / 4096.0, float(gl_VertexID / 4096) / 64.0, TX(uB0, 87915).g / 4.0); vVis = TX(uB1, i); vC = color; vMist = mistF(vP);
  if (uLiveS >= 1) { vec4 b1 = vVis, b2 = TX(uB2, i); vec3 nR = normalize(uRestN * normal); vec3 bR = length(b2.xyz) > 1e-6 ? normalize(b2.xyz) : nR; float ct = 1.0 - 2.0 * clamp(b2.w, 0.0, 1.0);
    bool live = uLiveS == 1; vec3 Nn = live ? vN : nR; vec3 bN = live ? normalize(mat3(modelMatrix) * (transpose(uRestN) * bR)) : bR;
    vec3 Ls[4] = vec3[4](uSunD, uKeyD, uRimD, uFillD); vec3 Cs[4] = vec3[4](uSunC, uKeyC, uRimC, uFillC); vec3 E = vec3(0.0); vec4 vn; float sss = color.a;
    vec4 pv = uPoseOn == 1 ? mix(TX(uPA, i), TX(uPB, i), uPW) : vec4(0.0);
    for (int j = 0; j < 4; j++) { float v = uPoseOn == 1 ? pv[j] : (live ? liveVis(b1[j], bR, bN, ct, Ls[j]) : b1[j]); float g = dot(Nn, Ls[j]);
      E += Cs[j] * (max(g, 0.0) * v + max(-g, 0.0) * sss * .5 * (1.0 - v * .5)); vn[j] = v; }
    vE += E; vVis = vn; }
  gl_Position = projectionMatrix * viewMatrix * w; }`;
const SURF_DVS = `precision highp float; uniform mat4 projectionMatrix, viewMatrix, modelMatrix; in vec3 position; void main() { gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(position, 1.0); }`;
const NOISE = `float h3(vec3 p) { p = fract(p * .3183099 + .1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vn(vec3 x) { vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y), mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z); }
float fbm(vec3 p) { float s = 0.0, a = .5; for (int i = 0; i < 5; i++) { s += a * vn(p); p *= 2.03; a *= .5; } return s; }`;
const SURF_FS = GL_HEAD + NOISE + `
uniform int uMat; uniform vec3 uAlb; uniform vec3 uEyeD, uEyeC; uniform float uRough, uWet; uniform vec3 uIris0, uIris1, uIris2; uniform vec2 uEyeK; uniform float uIrisS;
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
  else if (uMat == 10) { float n = fbm(vP * 90.0); alb = uAlb * (.93 + .07 * n); float sh = pow(1.0 - max(dot(N, V), 0.0), 3.0); extra = uAlb * sh * .25 * (vE / 3.14159); } // ткань кепки
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
  col = mix(col, uMistC, vMist); if (any(isnan(col)) || any(isinf(col))) col = vec3(0.0); col = min(col, vec3(40.0));
  oc = vec4(col, 1.0);
}`;
// роговица: прозрачная линза — только отражения (окно-свет, небо) и блик
const CORNEA_FS = GL_HEAD + `
uniform vec3 uEyeD, uEyeC, uSky;
in vec3 vE; in vec4 vVis; in vec3 vN; in vec3 vP; in vec4 vC; in vec3 vL; in float vMist; out vec4 oc;
void main() { vec3 N = normalize(vN), V = normalize(cameraPosition - vP); float nv = max(dot(N, V), 0.0); float F = .02 + .98 * pow(1.0 - nv, 5.0);
  vec3 Rv = reflect(-V, N); vec3 env = mix(vec3(0.05, 0.07, 0.06), uSky * 1.4, smoothstep(-.1, .5, Rv.y));
  float hk = pow(max(dot(Rv, uKeyD), 0.0), 600.0) * 40.0, he = pow(max(dot(Rv, uEyeD), 0.0), 900.0) * 60.0, hs = pow(max(dot(Rv, uSunD), 0.0), 2000.0) * 40.0;
  vec3 col = env * F + uKeyC * hk + uEyeC * he + uSunC * hs;
  oc = vec4(col, 1.0); }`;

// ---------- запекание ----------
// Точки-приёмники: «нити» (тангенс из соседних точек) и «поверхности» (нормаль). Для каждого направления света:
// 1) глубина сцены из света (орто-камера по коробке группы), 2) для каждой точки: видна ли она свету / сколько шерсти перед ней.
const GATHER_FS = `precision highp float; precision highp int; precision highp sampler2D;
uniform sampler2D uPos, uDir, uDepth, uFCol; uniform mat4 uLVP; uniform vec3 uL, uCol, uBounce; uniform float uKT, uW; uniform int uGrassG, uDirect, uPosed, uOnlyVis; uniform mat4 uPartM[6]; uniform vec4 uMask; uniform float uTexel, uRange, uTauH, uTauS, uTauO, uAO; uniform int uKind, uK, uN;
layout(location = 0) out vec4 o0; layout(location = 1) out vec4 o1; layout(location = 2) out vec4 o2;
vec4 TX(sampler2D t, int i) { return texelFetch(t, ivec2(i % ${TW}, i / ${TW}), 0); }
void main() {
  ivec2 ij = ivec2(gl_FragCoord.xy); int i = ij.y * ${TW} + ij.x; if (i >= uN) discard;
  vec4 P0 = TX(uPos, i); vec3 p = P0.xyz; mat3 Mr = mat3(1.0); if (uPosed == 1) { mat4 Mp = uPartM[int(P0.w + .5)]; p = (Mp * vec4(p, 1.0)).xyz; Mr = mat3(Mp); }
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
      float zo = texture(uDepth, q.xy + o * ts).r; float dz = (q.z - zo) * uRange; // метры «за» первым препятствием
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
  const roots = [], rec = [];
  for (let s = 0; s < want; s++) {
    const x = r() * tot; let lo = 0, hi = nt - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (cum[m] < x) lo = m + 1; else hi = m; }
    const a = I[lo * 3], b = I[lo * 3 + 1], c = I[lo * 3 + 2]; let u1 = r(), u2 = r(); if (u1 + u2 > 1) { u1 = 1 - u1; u2 = 1 - u2; } const w0 = 1 - u1 - u2;
    const near = w0 >= u1 && w0 >= u2 ? a : u1 >= u2 ? b : c; if (FD[near * 5 + 3] < 128) continue; // «можно ли расти» на ближайшей вершине
    const rg = FD[near * 5 + 4]; const R = [0, 1, 2].map(k => P[a * 3 + k] * w0 + P[b * 3 + k] * u1 + P[c * 3 + k] * u2);
    const N = nrm3([0, 1, 2].map(k => (Nn[a * 3 + k] * w0 + Nn[b * 3 + k] * u1 + Nn[c * 3 + k] * u2) / 127));
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
    L *= .82 + .36 * r(); const guard = r() < .12; if (guard && rg !== 3) L *= 1.35;
    // разброс
    let j = nrm3([r() * 2 - 1, r() * 2 - 1, r() * 2 - 1]); const jn = j[0] * N[0] + j[1] * N[1] + j[2] * N[2]; j = [j[0] - N[0] * jn, j[1] - N[1] * jn, j[2] - N[2] * jn];
    f = nrm3([f[0] + j[0] * .28, f[1] + j[1] * .28, f[2] + j[2] * .28]);
    const cl = Math.cos(lean), sl = Math.sin(lean); const d0 = nrm3([N[0] * cl + f[0] * sl, N[1] * cl + f[1] * sl, N[2] * cl + f[2] * sl]);
    const cr = [N[1] * f[2] - N[2] * f[1], N[2] * f[0] - N[0] * f[2], N[0] * f[1] - N[1] * f[0]]; nrm3(cr); const ck = (r() - .5) * .25;
    const shade = (1.04 - .08 * r()) * (guard ? .96 : 1);
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


// ---------- загрузка героя (сжатые файлы, кожа по частям, правила шерсти) ----------
const yieldUI = () => new Promise(r => setTimeout(r, 0));
const prog = (stage, k, text) => { if (OB.onProgress) try { OB.onProgress(stage, Math.max(0, Math.min(1, k)), text || ''); } catch (e) {} };
OB.dl = 0;
// файлы героев сохраняются в памяти телефона (Cache Storage): второй раз та же версия открывается без скачивания
let CACHE = undefined; OB.fromCache = 0; OB.fromNet = 0;
function openCache() { if (CACHE !== undefined) return CACHE;   // одно открытие на все файлы (они качаются одновременно)
  CACHE = (async () => { try { if (!self.caches) return null; const ck = 'ob-' + (OB.ver || 'v'); const c = await caches.open(ck);
    (await caches.keys()).forEach(k => { if (k.startsWith('ob-') && k !== ck) caches.delete(k); }); return c; } catch (e) { return null; } })();
  return CACHE; }
async function fetchBuf(url) { const cache = await openCache(); let r = null, net = false;
  if (cache) try { r = await cache.match(url); } catch (e) { r = null; }
  if (!r) { r = await fetch(url); net = true; if (!r.ok) throw new Error('нет файла ' + url); if (cache) try { cache.put(url, r.clone()).catch(() => {}); } catch (e) {} }
  let b;
  if (r.body && r.body.getReader) { const rd = r.body.getReader(), parts = []; let n = 0;
    for (;;) { const { done, value } = await rd.read(); if (done) break; parts.push(value); n += value.length; OB.dl += value.length; prog('load', 0, ''); }
    const all = new Uint8Array(n); let o = 0; for (const p of parts) { all.set(p, o); o += p.length; } b = all.buffer; }
  else { b = await r.arrayBuffer(); OB.dl += b.byteLength; prog('load', 0, ''); }
  if (net) OB.fromNet += b.byteLength; else OB.fromCache += b.byteLength;
  const u = new Uint8Array(b, 0, 2);
  if (u[0] === 0x1f && u[1] === 0x8b) b = await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer(); return b; }
// трава как в env.py: круг R 3.2 м (вытянут вперёд), травинка 4–11 см, наклон — нормальный разброс; оси Blender -> наши
function growGrass(g) { const r = rng32(g.seed || 11), n0 = g.n || 90000, out = new Float32Array(n0 * 12); let m = 0;
  const gauss = () => { let u = 0, v = 0; while (u === 0) u = r(); v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(6.283185 * v); };
  for (let i = 0; i < n0; i++) { const R = Math.sqrt(r()) * (g.R || 3.2), A = r() * 6.283185; const x = Math.cos(A) * R, y = Math.sin(A) * R * 1.6 + 0.6;
    const h = 0.04 + r() * 0.07, l0 = gauss() * 0.35, l1 = gauss() * 0.35; if (Math.abs(x) < 0.12 && Math.abs(y + 0.03) < 0.1) continue;
    for (let k = 0; k < 4; k++) { const t = k / 3, o = (m * 4 + k) * 3; const bx = x + l0 * t * t * h, by = y + l1 * t * t * h, bz = h * t; out[o] = bx; out[o + 1] = bz; out[o + 2] = -by; } m++; }
  return out.subarray(0, m * 12); }
function unpackPos(z, n, lo0, sc) { const p = new Float32Array(n * 3);
  for (let c = 0; c < 3; c++) { let v = 0; const lo = c * n, hi = 3 * n + c * n; for (let i = 0; i < n; i++) { const u = z[lo + i] | (z[hi + i] << 8); const d = (u >>> 1) ^ -(u & 1); v = (v + d) & 0xFFFF; p[i * 3 + c] = lo0[c] + v * sc[c]; } }
  return p; }
function unpackIdx(b, ni) { const idx = new Uint32Array(ni); let mx = -1, j = 0;
  for (let i = 0; i < b.length && j < ni;) { let v = 0, sh = 0, x; do { x = b[i++]; v += (x & 127) * Math.pow(2, sh); sh += 7; } while (x & 128); const back = (v & 1) ? -(v + 1) / 2 : v / 2; const I = mx + 1 - back; idx[j++] = I; if (I > mx) mx = I; }
  return idx; }
async function loadHero(base, name) {
  const man = await (await fetch(base + name + '.json')).json(); const files = {}, need = new Set();
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

// ---------- движение героев: у каждого своя роль в 5-секундной сцене ----------
const ss = (a, b, t) => { const x = Math.min(1, Math.max(0, (t - a) / (b - a))); return x * x * (3 - 2 * x); };
const env = (t, a, b, f) => { f = f == null ? .25 : f; return ss(a, a + f, t) * (1 - ss(b - f, b, t)); };
const mouthOf = (SYL, t) => { for (const [a, d, v] of SYL) if (a <= t && t < a + d) { const ph = (t - a) / d; return ph > .15 && ph < .8 ? v : (ph > .08 && ph < .9 ? (v === 'a' && (ph < .3 || ph > .7) ? 'o' : 'base') : 'base'); } return 'base'; };
const ANIM = {
  barsik: { syl: [[1.05, .18, 'a'], [1.23, .22, 'a'], [1.62, .2, 'a'], [1.85, .2, 'a'], [2.05, .2, 'a'], [5.85, .2, 'o'], [6.05, .26, 'o'], [6.45, .18, 'o'], [6.63, .3, 'a']], blinks: [0.5, 3.95, 7.75],
    pose: (t, S) => { const yaw = -0.5 * ss(2.7, 3.3, t) * (1 - ss(5.0, 5.6, t)) + 0.06 * S(t * 0.9);
      const pitch = 0.05 * S(t * 7.5) * env(t, 1.0, 2.5) + 0.04 * S(t * 6.5) * env(t, 5.8, 7.0); const roll = 0.17 * env(t, 5.6, 7.7, 0.4) + 0.03 * S(t * 1.3);
      const up = ss(0.95, 1.3, t) * (1 - ss(2.55, 3.0, t)), wave = S((t - 1.3) * 11) * 0.28 * env(t, 1.3, 2.55, 0.15);
      return { head: [pitch, roll, yaw], armR: [-2.2 * up, 0, 0.75 * up + wave], armL: [0.04 * S(t * 1.7), 0.05 * S(t * 1.3 + 1), 0], tail: [0, 0, 0.28 * S(t * 2.6)], body: [0.003 * S(t * 2 * Math.PI / 2.8), 0.015 * S(t * 1.1)] }; } },
  pik: { syl: [[2.75, .16, 'a'], [2.93, .18, 'o'], [3.14, .16, 'a'], [3.33, .22, 'a'], [3.6, .18, 'o']], blinks: [1.55, 4.55],
    pose: (t, S) => { const look = 0.42 * env(t, 0.8, 2.55, 0.35); const yaw = look + 0.05 * S(t * 1.2);
      const pitch = 0.06 * S(t * 8) * env(t, 2.7, 3.8) - 0.05 * look; const roll = 0.1 * S(t * 3.1) * env(t, 3.9, 4.8, .2) + 0.04 * S(t * 1.7);
      const hop = Math.abs(S((t - 3.95) * 9.4)) * env(t, 3.95, 4.65, .1); const joy = env(t, 3.85, 4.75, .2);
      return { head: [pitch, roll, yaw], armR: [-0.4 * joy, -0.9 * joy + 0.1 * S(t * 9) * joy, 0], armL: [-0.4 * joy, 0.9 * joy - 0.1 * S(t * 9) * joy, 0], tail: [0.05 * S(t * 1.9), 0, 0.22 * S(t * 2.1)], body: [0.002 * S(t * 2.4) + 0.025 * hop, 0.02 * S(t * 1.3)] }; } },
  ron: { syl: [[4.05, .2, 'o'], [4.27, .2, 'a'], [4.5, .18, 'a'], [4.72, .26, 'o']], blinks: [2.2, 4.95],
    pose: (t, S) => { const look = -0.36 * env(t, 0.9, 2.6, 0.35); const tilt = 0.24 * env(t, 2.9, 3.9, 0.3);
      const yaw = look + 0.05 * S(t * 0.8); const pitch = 0.05 * S(t * 7) * env(t, 4.0, 5.0) + 0.04 * env(t, 2.9, 3.9, .3); const roll = tilt + 0.03 * S(t * 1.1);
      const paw = env(t, 4.0, 4.9, 0.2), pw = S((t - 4.1) * 10) * 0.18 * paw;
      return { head: [pitch, roll, yaw], armR: [-1.75 * paw + pw, -0.3 * paw, 0], armL: [0.03 * S(t * 1.5), 0.04 * S(t * 1.2 + 1), 0], tail: [0, 0.1 * S(t * 9), 0.42 * S(t * 9)], body: [0.003 * S(t * 2 * Math.PI / 2.4), 0.012 * S(t * 1.4)] }; } } };

OB.boot = async function (T, canvas, base, opts) {
  THREE = T; opts = opts || {}; const t0 = now(); OB.t = {}; OB.build = [];
  MIST.uMistC.value = new THREE.Color(0.56, 0.74, 0.7);
  R = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  R.setPixelRatio(1); R.autoClear = false;
  const gl = R.getContext(); log('gl', gl.getParameter(gl.VERSION), 'cbf', !!gl.getExtension('EXT_color_buffer_float'));
  const LIST = opts.heroes || [{ name: 'barsik', x: 0, z: 0, yaw: 0, k: 1 }, { name: 'pik', x: -0.66, z: 0.16, yaw: 0.38, k: .56 }, { name: 'ron', x: 0.8, z: 0.06, yaw: -0.32, k: .82 }];
  const env0 = await fetch(base + 'env.json').then(r => r.json());
  const [grassBuf, ...HD] = await Promise.all([env0.grass_gen ? Promise.resolve(null) : fetchBuf(base + 'grass.wasm'), ...LIST.map(h => loadHero(base, h.name))]);
  OB.t.load = now() - t0; log('загрузка', (OB.t.load / 1000).toFixed(1), 'с'); prog('fur', 0, LIST[0].name); await yieldUI();
  const scene = new THREE.Scene(); OB.scene = scene;
  // ---- свет как в Blender (render.py), оси: (x, y, z)_B -> (x, z, -y); лампы стоят в мире, у каждого героя свои направления на них ----
  const L = OB.L = {
    sunD: new THREE.Vector3(-0.55, 0.67, 0.5).normalize(), sunC: new THREE.Color(1.0, 0.85, 0.66).multiplyScalar(3.6),
    key: { pos: new THREE.Vector3(-1.3, 1.55, 1.5), size: 1.6, P: 70, col: new THREE.Color(1.0, 0.95, 0.88) },
    fill: { pos: new THREE.Vector3(1.6, 0.6, 1.0), size: 2.0, P: 45, col: new THREE.Color(0.75, 0.9, 1.0) },
    rim: { pos: new THREE.Vector3(-0.7, 1.35, -1.1), size: 0.8, P: 260, col: new THREE.Color(1.0, 0.9, 0.75) },
    eye: { pos: new THREE.Vector3(0.25, 1.05, 2.0), P: 8, col: new THREE.Color(1, .97, .93) },
    sky: new THREE.Color(0.42, 0.62, 0.6).multiplyScalar(0.9), gnd: new THREE.Color(0.05, 0.09, 0.03), gndR: new THREE.Color(0.075, 0.085, 0.05), areaK: 1 / Math.PI };
  const lightsFor = (c) => { // направления и сила ламп из центра героя
    const E = l => { const d2 = Math.max(.6, l.pos.distanceToSquared(c)); return l.col.clone().multiplyScalar(l.P * L.areaK / d2); }, D = l => l.pos.clone().sub(c).normalize();
    return { uSunD: { value: L.sunD }, uSunC: { value: L.sunC }, uKeyD: { value: D(L.key) }, uKeyC: { value: E(L.key) }, uRimD: { value: D(L.rim) }, uRimC: { value: E(L.rim).multiplyScalar(.35) },
      uFillD: { value: D(L.fill) }, uFillC: { value: E(L.fill) }, uEyeD: { value: D(L.eye) }, uEyeC: { value: E(L.eye) }, uSky: { value: L.sky }, uGnd: { value: L.gnd } }; };
  OB.U = lightsFor(new THREE.Vector3(0, 0.6, 0));
  const raw = (vs, fs, uni, extra, U) => new THREE.RawShaderMaterial(Object.assign({ vertexShader: vs, fragmentShader: fs, uniforms: Object.assign({}, MIST, U || OB.U, uni), glslVersion: THREE.GLSL3 }, extra || {}));
  const ident6 = () => [0, 1, 2, 3, 4, 5].map(() => new THREE.Matrix4());
  const DBGS = OB.DBGS = { value: 0 };
  const strandSet = (name, ptsTex, colTex, nrmTex, n, k, grass, U) => {
    const uni = { uPts: { value: ptsTex }, uCol: { value: colTex || ptsTex }, uB0: { value: null }, uB1: { value: null }, uK: { value: k }, uRadK: { value: 0.001 }, uTaper: { value: .85 },
      uPx: { value: .001 }, uMinPx: { value: 1.0 }, uGR: { value: new THREE.Vector4(.0028, .0022, .0014, .0004) }, uGrass: { value: grass ? 1 : 0 }, uCamDir: { value: new THREE.Vector3() },
      uTime: { value: 0 }, uWind: { value: grass ? .004 : 0 }, uHairK: { value: grass ? .24 : .095 }, uMS: { value: grass ? .2 : .25 }, uSpec: { value: grass ? .25 : .2 }, uDesat: { value: 0 },
      uGold: { value: grass ? .45 : .85 }, uGoldT: { value: grass ? new THREE.Vector3(.8, 1, .3) : new THREE.Vector3(1, .66, .25) }, uPartM: { value: ident6() }, uBlink: { value: 0 },
      uB2: { value: null }, uNrm: { value: nrmTex || ptsTex }, uLive: { value: grass ? 0 : 1 }, uCull: { value: 0 }, uCullK: { value: -.3 }, uKT: { value: .5 }, uDec: { value: grass ? 1 : 2 },
      uPoseOn: { value: 0 }, uPA: { value: null }, uPB: { value: null }, uPW: { value: 0 }, uDbgS: DBGS };
    const mat = raw(strandVS(false), STRAND_FS, uni, { side: THREE.DoubleSide, alphaToCoverage: true }, U);
    const dmat = raw(strandVS(true), DEPTH_FS, uni, { side: THREE.DoubleSide, colorWrite: false }, U);
    const g = new THREE.BufferGeometry(); g.setDrawRange(0, n * (k - 1) * 6); g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e4);
    const m = new THREE.Mesh(g, mat); m.frustumCulled = false; m.userData = { dmat, mat, strands: true, name, hero: !grass }; scene.add(m);
    return { name, mesh: m, uni, n: n * k, k, kind: 1, posTex: ptsTex, colTex };
  };
  const meshSets = {}; OB.meshSets = meshSets;
  const surf = (setName, geo, matId, alb, opt) => {
    opt = opt || {}; const S = meshSets[setName] || (meshSets[setName] = { name: setName, list: [], n: 0, kind: 0 });
    if (!geo.attributes.normal) geo.computeVertexNormals();
    if (!geo.attributes.color) { const c = new Float32Array(geo.attributes.position.count * 4).fill(1); for (let i = 3; i < c.length; i += 4) c[i] = 0; geo.setAttribute('color', new THREE.BufferAttribute(c, 4)); }
    const ir = opt.iris || [[0.06, 0.2, 0.05], [0.16, 0.42, 0.08], [0.35, 0.62, 0.12]];
    const uni = { uB0: { value: null }, uB1: { value: null }, uBase: { value: S.n }, uMat: { value: matId }, uAlb: { value: new THREE.Color().setRGB(...(alb || [1, 1, 1])) }, uRough: { value: .5 }, uEyeM: { value: new THREE.Matrix4() }, uDbg: DBG,
      uGndK: { value: opt.hero ? 0 : 1 }, uB2: { value: null }, uLiveS: { value: 0 }, uRestN: { value: new THREE.Matrix3() }, uPoseOn: { value: 0 }, uPA: { value: null }, uPB: { value: null }, uPW: { value: 0 },
      uWet: { value: opt.wet ? 1 : 0 }, uEyeK: { value: new THREE.Vector2(...(opt.eyeK || [.70, .915])) }, uIrisS: { value: opt.irisS || 0 }, uIris0: { value: new THREE.Vector3(...ir[0]) }, uIris1: { value: new THREE.Vector3(...ir[1]) }, uIris2: { value: new THREE.Vector3(...ir[2]) } };
    const mat = raw(SURF_VS, opt.fs || SURF_FS, uni, opt.extra, opt.U);
    const dmat = raw(SURF_DVS, DEPTH_FS, {}, { colorWrite: false, side: THREE.DoubleSide });
    const m = new THREE.Mesh(geo, mat); m.userData = { dmat, mat, set: S, name: opt.name, hero: !!opt.hero, noOcc: !!opt.noOcc }; m.frustumCulled = false;
    (opt.parent || scene).add(m); if (opt.pos) m.position.copy(opt.pos); if (opt.scale) m.scale.copy(opt.scale); if (opt.quat) m.quaternion.copy(opt.quat);
    m.updateMatrixWorld(true); uni.uRestN.value.getNormalMatrix(m.matrixWorld);
    S.list.push({ m, base: S.n, sss: opt.sss, part: opt.part || 0 }); S.n += geo.attributes.position.count; return m;
  };
  OB.heroes = [];
  for (let hi = 0; hi < LIST.length; hi++) {
    if (hi > 0) { prog('fur', hi / LIST.length, LIST[hi].name); await yieldUI(); }
    const h = LIST[hi], D = HD[hi], info = D.info, tb = now(); const cs = Math.cos(h.yaw), sn = Math.sin(h.yaw);
    const xfP = (x, y, z) => [x * cs + z * sn + h.x, y, -x * sn + z * cs + h.z], xfN = (x, y, z) => [x * cs + z * sn, y, -x * sn + z * cs];
    const V3 = a => new THREE.Vector3(...xfP(...a));
    const H = { name: h.name, k: h.k, x: h.x, z: h.z, yaw: h.yaw, info, anim: ANIM[h.name] }; OB.heroes.push(H);
    const grp = () => { const g = new THREE.Group(); g.matrixAutoUpdate = false; return g; };
    const G = H.G = {}; G.body = grp(); scene.add(G.body); for (const nm of ['head', 'armL', 'armR', 'tail']) { G[nm] = grp(); G.body.add(G[nm]); }
    const PART = { body: 0, head: 1, armL: 2, armR: 3, tail: 4 }; H.PIV = {}; for (const k in info.piv) H.PIV[k] = V3(info.piv[k]);
    H.center = new THREE.Vector3(h.x, 0.55 * h.k, h.z); const U = H.U = lightsFor(H.center);
    // ---- шерсть: растит телефон ----
    const cfg = info.fur, src = info.src, kS = opts.furK == null ? .8 : opts.furK; let cap = 0;
    for (const sk of ['body', 'feet', 'head', 'armL', 'armR', 'tail', 'head_blink']) if (D.skins[sk]) cap += furWant(D.skins[sk], cfg, kS);
    cap = Math.ceil(cap * 1.05) + 100; const out = { pts: new Float32Array(cap * 5 * 4), col: new Uint8Array(cap * 4), nrm: new Uint8Array(cap * 4), n: 0, cap };
    const tf = now(); let si = 0;
    for (const [sk, pid] of [['body', 0], ['feet', 0], ['head', 1], ['armL', 2], ['armR', 3], ['tail', 4], ['head_blink', 5]]) if (D.skins[sk]) growFur(D.skins[sk], cfg, src, pid, out, (hi + 1) * 1000 + (si++) * 17 + 3, kS);
    for (let i = 0; i < out.n * 5; i++) { const o = i * 4; const w = xfP(out.pts[o], out.pts[o + 1], out.pts[o + 2]); out.pts[o] = w[0]; out.pts[o + 1] = w[1]; out.pts[o + 2] = w[2]; }
    for (let i = 0; i < out.n; i++) { const o = i * 4; const w = xfN((out.nrm[o] - 128) / 127, (out.nrm[o + 1] - 128) / 127, (out.nrm[o + 2] - 128) / 127); out.nrm[o] = Math.round(w[0] * 127 + 128); out.nrm[o + 1] = Math.round(w[1] * 127 + 128); out.nrm[o + 2] = Math.round(w[2] * 127 + 128); }
    const tFur = now() - tf;
    const fur = strandSet('fur_' + h.name, dataTex(out.pts.subarray(0, out.n * 5 * 4), out.n * 5), (() => { const t = dataTex(out.col.subarray(0, out.n * 4), out.n, THREE.UnsignedByteType); t.colorSpace = THREE.NoColorSpace; return t; })(),
      dataTex(out.nrm.subarray(0, out.n * 4), out.n, THREE.UnsignedByteType), out.n, 5, false, U);
    fur.tauH = .004; H.fur = fur; H.nFur = out.n;
    // ---- кожа частей ----
    const ts = now(); const setName = 'hero_' + h.name;
    const mk = (sk) => { const s = D.skins[sk]; const n = s.nv, P = new Float32Array(n * 3), Nn = new Float32Array(n * 3), C = new Float32Array(n * 4);
      for (let i = 0; i < n; i++) { const w = xfP(s.p[i * 3], s.p[i * 3 + 1], s.p[i * 3 + 2]); P.set(w, i * 3); const q = xfN(s.n[i * 3] / 127, s.n[i * 3 + 1] / 127, s.n[i * 3 + 2] / 127); Nn.set(q, i * 3); for (let c = 0; c < 4; c++) C[i * 4 + c] = s.c[i * 4 + c] / 255; }
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setAttribute('normal', new THREE.BufferAttribute(Nn, 3)); g.setAttribute('color', new THREE.BufferAttribute(C, 4)); g.setIndex(new THREE.BufferAttribute(s.idx, 1)); return g; };
    for (const sk of ['body', 'feet', 'armL', 'armR', 'tail']) if (D.skins[sk]) surf(setName, mk(sk), 1, null, { sss: true, name: sk, parent: G[sk === 'feet' ? 'body' : sk], part: PART[sk === 'feet' ? 'body' : sk], hero: true, U });
    H.heads = {}; for (const [k, sk] of [['base', 'head'], ['a', 'head_a'], ['o', 'head_o'], ['blink', 'head_blink']]) H.heads[k] = surf(setName, mk(sk), 1, null, { sss: true, name: sk, parent: G.head, part: 1, hero: true, noOcc: k !== 'base', U });
    const tSkin = now() - ts;
    // ---- нос и вещи ----
    const MAT = { nose: 6, tooth: 6, scarf: 4, satin: 9, cloth: 10, gold: 8 };
    for (const k in D.small) { const s = D.small[k]; const n = s.p.length / 3, P = new Float32Array(n * 3); for (let i = 0; i < n; i++) P.set(xfP(s.p[i * 3], s.p[i * 3 + 1], s.p[i * 3 + 2]), i * 3);
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setIndex(new THREE.BufferAttribute(s.idx, 1));
      const isNose = s.mat === 'nose'; surf(setName, g, MAT[s.mat] || 0, isNose ? info.nose.col : s.col, { name: k, parent: G[s.part], part: PART[s.part], hero: true, wet: isNose && info.nose.wet, U }); }
    // ---- глаза + роговица: смотрят в камеру общего плана, дальше двигаются с головой ----
    const RE = info.re; H.eyes = []; const CAM0 = new THREE.Vector3(0.3, 0.75, 3.2);
    const AIM = info.eyeAim ? V3(info.eyeAim) : CAM0;
    const coMat = () => raw(SURF_VS, CORNEA_FS, { uB0: { value: null }, uB1: { value: null }, uBase: { value: 0 } }, { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }, U);
    for (let ei = 0; ei < info.eyes.length; ei++) { const c = info.eyes[ei]; const cv = V3(c);
      if (info.eyeDirs) { // v6.2: глаз (и овал) стоит по осям головы, а радужка повёрнута отдельно — в середину видимой части глаза
        const Yq = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), h.yaw), eS = new THREE.Vector3(...(info.eyeS || [1, 1, 1]));
        const dL = new THREE.Vector3(...info.eyeDirs[ei]).normalize(), iq = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), dL);
        const e = surf(setName, new THREE.SphereGeometry(RE, 48, 36), 5, null, { pos: cv, quat: Yq, scale: eS, name: 'eye', parent: G.head, part: 1, hero: true, iris: info.iris, eyeK: info.eyeK, irisS: info.irisS || 0, U });
        e.userData.irisInv = new THREE.Matrix4().makeRotationFromQuaternion(iq).invert();
        const co = new THREE.Mesh(new THREE.SphereGeometry(RE * .872, 40, 28), coMat()); co.position.copy(dL).multiplyScalar(RE * 0.208); co.quaternion.copy(iq);
        co.userData = { cornea: true }; co.frustumCulled = false; e.add(co); e.updateMatrixWorld(true); H.eyes.push({ e, co, c: cv }); continue; }
      const fwd = (info.eyeAims ? V3(info.eyeAims[ei]) : AIM).clone().sub(cv).normalize(), q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), fwd);
      const eS = info.eyeS ? new THREE.Vector3(...info.eyeS) : null; const e = surf(setName, new THREE.SphereGeometry(RE, 48, 36), 5, null, { pos: cv, quat: q, scale: eS, name: 'eye', parent: G.head, part: 1, hero: true, iris: info.iris, eyeK: info.eyeK, irisS: info.irisS || 0, U });
      const co = new THREE.Mesh(new THREE.SphereGeometry(RE * .872, 40, 28), coMat());
      co.position.copy(cv).addScaledVector(fwd, RE * 0.208 * (eS ? eS.z : 1)); co.quaternion.copy(q); if (eS) co.scale.copy(eS); co.userData = { cornea: true }; co.frustumCulled = false; G.head.add(co); H.eyes.push({ e, co, c: cv }); }
    // ---- рот, веки, усы ----
    const tube = (pts, r0, r1, alb, name, opt2) => { const cv = new THREE.CatmullRomCurve3(pts.map(p => V3(p))); const g = new THREE.TubeGeometry(cv, 24, 1, 6, false);
      const pa = g.attributes.position, na = g.attributes.normal; for (let i = 0; i < pa.count; i++) { const t = Math.floor(i / 7) / 24; const P0 = cv.getPointAt(Math.min(1, t)); const r = r0 + (r1 - r0) * t;
        pa.setXYZ(i, P0.x + na.getX(i) * r, P0.y + na.getY(i) * r, P0.z + na.getZ(i) * r); } return surf(setName, g, 0, alb, Object.assign({ name, parent: G.head, part: 1, hero: true, U }, opt2 || {})); };
    const sc = RE / 0.061; H.mouthB = info.lines.mouth_base.map(l => tube(l, .0017 * sc, .0015 * sc, [0.12, 0.04, 0.03], 'mouth'));
    H.mouthO = info.lines.mouth_open.map(l => tube(l, .0017 * sc, .0015 * sc, [0.12, 0.04, 0.03], 'mouthO', { noOcc: true }));
    H.creases = info.lines.creases.map(l => tube(l, .0012 * sc, .0024 * sc, [0.07, 0.035, 0.02], 'crease', { noOcc: true }));
    info.lines.whisk.forEach(l => tube(l, info.whisk.r[0], info.whisk.r[1], info.whisk.col, 'whisk'));
    H.set = meshSets[setName];
    OB.build.push({ name: h.name, fur: out.n, tFur, tSkin, tAll: now() - tb });
    log(h.name, ': шерсть', out.n, 'волосков за', Math.round(tFur), 'мс; кожа', Math.round(tSkin), 'мс');
  }
  prog('build', 0, ''); await yieldUI();
  // ---- трава ----
  let NG = env0.grass_n, KG = env0.grass_k, gr; if (env0.grass_gen) { gr = growGrass(env0.grass_gen); KG = 4; NG = gr.length / (KG * 3); } else gr = new Float32Array(grassBuf); const gp = new Float32Array(NG * KG * 4);
  for (let i = 0; i < NG * KG; i++) { gp[i * 4] = gr[i * 3]; gp[i * 4 + 1] = gr[i * 3 + 1]; gp[i * 4 + 2] = gr[i * 3 + 2]; gp[i * 4 + 3] = 0; }
  const grass = strandSet('grass', dataTex(gp, NG * KG), null, null, NG, KG, true); grass.tauH = .02;
  // ---- лес ----
  { const g = new THREE.PlaneGeometry(14, 20, 280, 400); g.rotateX(-Math.PI / 2); g.translate(0, 0, -5); surf('field', g, 2, null, { name: 'ground' }); }
  { const g = new THREE.PlaneGeometry(80, 80, 40, 40); g.rotateX(-Math.PI / 2); g.translate(0, -0.002, -20); surf('far', g, 2, null, { name: 'groundFar' }); }
  for (const [x, z, r] of env0.trunks) { const g = new THREE.CylinderGeometry(r, r, 14, 32, 56); g.translate(0, 7, 0); surf('far', g, 3, null, { pos: new THREE.Vector3(x, 0, z), name: 'trunk' }); }
  for (const [x, z, r] of env0.stones) { const g = new THREE.SphereGeometry(r, 64, 40); const p = g.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); const k = 1 + .06 * Math.sin(v.x * 23 + v.z * 17) * Math.cos(v.y * 19) + .03 * Math.sin(v.x * 61 - v.y * 47); v.multiplyScalar(k); p.setXYZ(i, v.x, v.y, v.z); } g.computeVertexNormals();
    surf('field', g, 7, null, { pos: new THREE.Vector3(x, 0.05, z), scale: new THREE.Vector3(1.3, 0.6, 1.0), name: 'stone' }); }
  // ---- приёмники поверхностей (в позе покоя) ----
  scene.updateMatrixWorld(true);
  for (const k in meshSets) { const S = meshSets[k]; const P = new Float32Array(S.n * 4), Dd = new Float32Array(S.n * 4); const v = new THREE.Vector3(), nn = new THREE.Vector3();
    for (const it of S.list) { const g = it.m.geometry, pa = g.attributes.position, na = g.attributes.normal, ca = g.attributes.color; const nm = new THREE.Matrix3().getNormalMatrix(it.m.matrixWorld);
      for (let i = 0; i < pa.count; i++) { v.fromBufferAttribute(pa, i).applyMatrix4(it.m.matrixWorld); nn.fromBufferAttribute(na, i).applyMatrix3(nm).normalize(); const o = (it.base + i) * 4;
        P[o] = v.x; P[o + 1] = v.y; P[o + 2] = v.z; P[o + 3] = it.part || 0; Dd[o] = nn.x; Dd[o + 1] = nn.y; Dd[o + 2] = nn.z; Dd[o + 3] = it.sss && ca.itemSize === 4 ? ca.getW(i) : 0; } }
    S.posTex = dataTex(P, S.n); S.dirTex = dataTex(Dd, S.n); S.tauO = k.startsWith('hero') ? .002 : k === 'field' ? .012 : .01; }
  OB.sets = { grass, field: meshSets.field, far: meshSets.far };
  OB.setLive = on => { for (const H of OB.heroes) { H.fur.uni.uLive.value = on ? 1 : 2; for (const it of H.set.list) it.m.material.uniforms.uLiveS.value = on ? 1 : 2; } };
  OB.setCull = on => { for (const H of OB.heroes) H.fur.uni.uCull.value = on ? 1 : 0; };
  OB.showFur = on => { for (const H of OB.heroes) H.fur.mesh.visible = on; OB.furHidden = !on; };
  OB.t.build = now() - t0 - OB.t.load; log('сборка', (OB.t.build / 1000).toFixed(1), 'с');
  prog('bake', 0, ''); await yieldUI();
  await OB.bake(opts.bake || {});
  prog('done', 1, '');
  OB.setLive(true); OB.setCull(opts.cull !== false);
  OB.pose(0);
  return OB;
};

// ---------- движение ----------
{ let C, Ci; const rotB = (a, b, c) => { if (!C) { C = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1); Ci = C.clone().invert(); }
    return C.clone().multiply(new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(a, b, c, 'ZYX'))).multiply(Ci); };
  const about = (P, M) => new THREE.Matrix4().makeTranslation(P.x, P.y, P.z).multiply(M).multiply(new THREE.Matrix4().makeTranslation(-P.x, -P.y, -P.z));
  OB.pose = function (t) {
    if (!OB.heroes) return;
    for (const H of OB.heroes) {
      const G = H.G, P = H.PIV, A = H.anim, q = A.pose(t, Math.sin);
      // повороты частей заданы в осях героя (Blender) — поворачиваем их вместе с разворотом героя
      const Y = new THREE.Matrix4().makeRotationY(H.yaw), Yi = new THREE.Matrix4().makeRotationY(-H.yaw), R3 = (e) => Y.clone().multiply(rotB(...e)).multiply(Yi);
      G.head.matrix.copy(about(P.head, R3(q.head))); G.armR.matrix.copy(about(P.armR, R3(q.armR))); G.armL.matrix.copy(about(P.armL, R3(q.armL))); G.tail.matrix.copy(about(P.tail, R3(q.tail)));
      G.body.matrix.copy(about(H.center, new THREE.Matrix4().makeTranslation(0, q.body[0], 0).multiply(R3([0, q.body[1], 0]))));
    }
    OB.scene.updateMatrixWorld(true);
    for (const H of OB.heroes) {
      const A = H.anim, G = H.G; const closed = A.blinks.some(b => t >= b && t < b + .12), m = closed ? 'base' : mouthOf(A.syl, t);
      for (const k in H.heads) H.heads[k].visible = k === (closed ? 'blink' : m);
      for (const e of H.eyes) e.e.visible = e.co.visible = !closed;
      for (const o of H.mouthB) o.visible = !closed && m === 'base'; for (const o of H.mouthO) o.visible = !closed && m !== 'base'; for (const o of H.creases) o.visible = closed;
      const fu = H.fur.uni; fu.uBlink.value = closed ? 1 : 0; const pm = fu.uPartM.value; pm[0].copy(G.body.matrixWorld); pm[1].copy(G.head.matrixWorld); pm[2].copy(G.armL.matrixWorld); pm[3].copy(G.armR.matrixWorld); pm[4].copy(G.tail.matrixWorld); pm[5].copy(G.head.matrixWorld);
      const toB = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1), r = H.info.re, sc = new THREE.Matrix4().makeScale(1 / r, 1 / r, 1 / r);
      for (const e of H.eyes) { const M = e.e.material.uniforms.uEyeM.value.multiplyMatrices(sc, e.e.matrixWorld.clone().invert()); if (e.e.userData.irisInv) M.premultiply(e.e.userData.irisInv); M.premultiply(toB); }
    }
  };
}

// ---------- запекание света ----------
OB.bake = async function (o) {
  const t0 = now(); const S = OB.sets, U = OB.U, L = OB.L, scene = OB.scene; const ZERO = new THREE.Color(0, 0, 0);
  const nSky = o.sky || 30, nSun = o.sun || 8, nArea = o.area || 6; if (o.kt == null) o.kt = .5;
  const boxes = {};
  for (const H of OB.heroes) { const bb = new THREE.Box3(); for (const it of H.set.list) { it.m.geometry.computeBoundingBox(); bb.union(it.m.geometry.boundingBox.clone().applyMatrix4(it.m.matrixWorld)); } bb.expandByScalar(.06);
    boxes['hero_' + H.name] = { min: bb.min, max: bb.max, res: o.heroRes || 2048, sets: [H.fur, H.set], area: true, hero: H, bounce: new THREE.Color(...(H.name === 'barsik' ? [0.5, 0.36, 0.24] : H.name === 'pik' ? [0.36, 0.35, 0.33] : [0.34, 0.35, 0.36])), bounceUp: .5 }; }
  Object.assign(boxes, {
    field: { min: new THREE.Vector3(-6.6, -.05, -14.5), max: new THREE.Vector3(6.6, .5, 4.8), res: o.fieldRes || 2048, sets: [S.grass, S.field], bounce: new THREE.Color(...(o.grassBounce || [0.11, 0.2, 0.035])), bounceUp: 1 },
    far: { min: new THREE.Vector3(-30, -.05, -55), max: new THREE.Vector3(30, 14.2, 2), res: o.farRes || 1024, sets: [S.far], bounce: new THREE.Color(0.03, 0.05, 0.02), bounceUp: 1 } });
  // накопители
  const accOf = set => { const h = Math.max(1, Math.ceil(set.n / TW)); const rt = new THREE.WebGLRenderTarget(TW, h, { type: THREE.HalfFloatType, count: 3, depthBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, generateMipmaps: false });
    return rt; };
  const gMat = new THREE.RawShaderMaterial({ vertexShader: 'in vec3 position; void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }', fragmentShader: GATHER_FS, glslVersion: THREE.GLSL3,
    uniforms: { uW: { value: 0 }, uDirect: { value: 0 }, uPosed: { value: 0 }, uOnlyVis: { value: 0 }, uPartM: { value: [0, 1, 2, 3, 4, 5].map(() => new THREE.Matrix4()) }, uPos: { value: null }, uDir: { value: null }, uDepth: { value: null }, uFCol: { value: null }, uBounce: { value: new THREE.Color() }, uKT: { value: .85 }, uGrassG: { value: 0 }, uLVP: { value: new THREE.Matrix4() }, uL: { value: new THREE.Vector3() }, uCol: { value: new THREE.Color() }, uMask: { value: new THREE.Vector4() },
      uTexel: { value: .001 }, uRange: { value: 1 }, uTauH: { value: .004 }, uTauS: { value: .006 }, uTauO: { value: .002 }, uAO: { value: 0 }, uKind: { value: 0 }, uK: { value: 1 }, uN: { value: 0 } },
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor, depthTest: false, depthWrite: false });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), gMat); quad.frustumCulled = false; const qScene = new THREE.Scene(); qScene.add(quad); const qCam = new THREE.Camera();
  const allSets = [S.grass, S.field, S.far, ...OB.heroes.flatMap(H => [H.fur, H.set])];
  for (const s of allSets) { s.acc = accOf(s); R.setRenderTarget(s.acc); R.setClearColor(0x000000, 0); R.clear(true, false, false); }
  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 200);
  const depthRT = {};
  const passes = []; // [box, dir, color(irradiance), mask, ao]
  const skyW = 2 * Math.PI / nSky; // равномерно по верхней полусфере
  for (const bk in boxes) {
    const B = boxes[bk];
    for (let i = 0; i < 2 * nSky; i++) { const d = fib(2 * nSky, i);
      if (d.y > 0.02) passes.push([bk, d, L.sky.clone().multiplyScalar(skyW), new THREE.Vector4(0, 0, 0, 0), 1 / nSky, B.bounce.clone().multiplyScalar(skyW * B.bounceUp), false]);
      else if (B.area && d.y < -0.02) passes.push([bk, d, L.gndR.clone().multiplyScalar(skyW), new THREE.Vector4(0, 0, 0, 0), 0, B.bounce.clone().multiplyScalar(skyW), true]); }
    for (let i = 0; i < nSun; i++) { const j = jit(L.sunD, Math.PI / 180 * 2, i, nSun); passes.push([bk, j, L.sunC.clone().multiplyScalar(1 / nSun), new THREE.Vector4(1 / nSun, 0, 0, 0), 0, ZERO, false]); }
    if (B.area) for (const [nm, mk] of [['key', new THREE.Vector4(0, 1, 0, 0)], ['fill', new THREE.Vector4(0, 0, 0, 1)], ['rim', new THREE.Vector4(0, 0, 1, 0)]]) {
      const l = L[nm], hc = B.hero.center, U = B.hero.U, c = U['u' + nm[0].toUpperCase() + nm.slice(1) + 'C'].value; for (let i = 0; i < nArea; i++) { const sp = l.pos.clone().add(new THREE.Vector3((rnd(i * 3 + 1) - .5) * l.size, (rnd(i * 3 + 2) - .5) * l.size, (rnd(i * 3 + 3) - .5) * l.size));
        passes.push([bk, sp.sub(hc).normalize(), c.clone().multiplyScalar(1 / nArea), mk.clone().multiplyScalar(1 / nArea), 0, ZERO, false]); } }
  }
  log('проходов света', passes.length);
  // глубина из света
  const objs = []; scene.traverse(m => { if (m.isMesh && m.userData.dmat) objs.push(m); });
  const corn = []; scene.traverse(m => { if (m.isMesh && m.userData.cornea) corn.push(m); });
  let tDepth = 0, tGather = 0, pi = 0, tY = now();
  for (const [bk, dir, col, mask, ao, bounce, heroOnly] of passes) {
    if (pi > 0 && pi % 6 === 0) { OB.sync(); if (now() - tY > 90) { prog('bake', pi / passes.length, pi + ' из ' + passes.length); await yieldUI(); tY = now(); } }
    pi++;
    const B = boxes[bk]; const c = B.min.clone().add(B.max).multiplyScalar(.5); const ext = B.max.clone().sub(B.min).length() * .5;
    cam.position.copy(c).addScaledVector(dir, 100); const up = Math.abs(dir.y) > .95 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(0, 1, 0); cam.up.copy(up); cam.lookAt(c); cam.updateMatrixWorld(true);
    // плотные границы по 8 углам коробки
    const inv = cam.matrixWorldInverse; let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (let k = 0; k < 8; k++) { const p = new THREE.Vector3(k & 1 ? B.max.x : B.min.x, k & 2 ? B.max.y : B.min.y, k & 4 ? B.max.z : B.min.z).applyMatrix4(inv); x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); }
    cam.left = x0; cam.right = x1; cam.bottom = y0; cam.top = y1; cam.near = 100 - ext - 60; cam.far = 100 + ext + 1; cam.updateProjectionMatrix();
    const texel = Math.max(x1 - x0, y1 - y0) / B.res;
    let rt = depthRT[bk]; if (!rt) { rt = depthRT[bk] = new THREE.WebGLRenderTarget(B.res, B.res, { depthBuffer: true, type: THREE.UnsignedByteType }); rt.depthTexture = new THREE.DepthTexture(B.res, B.res, THREE.UnsignedIntType); rt.depthTexture.minFilter = rt.depthTexture.magFilter = THREE.NearestFilter; }
    let ta = now();
    for (const m of objs) { m.material = m.userData.dmat; if (m.userData.strands) { const u = m.userData.dmat.uniforms; u.uPx.value = texel; u.uMinPx.value = 0.0; u.uCamDir.value.copy(dir).negate(); } }
    for (const m of corn) m.visible = false; for (const m of objs) if (m.userData.noOcc) m.visible = false; if (heroOnly) for (const m of objs) if (!m.userData.hero) m.visible = false; 
    R.setRenderTarget(rt); R.setClearColor(0xffffff, 1); R.clear(true, true, false); R.render(scene, cam);
    for (const m of objs) { m.material = m.userData.mat; m.visible = true; } for (const m of corn) m.visible = true;
    const lvp = new THREE.Matrix4().multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    if (o.sync) OB.sync(); let tb = now(); tDepth += tb - ta;
    for (const s of B.sets) {
      const u = gMat.uniforms; u.uPos.value = s.posTex; u.uDir.value = s.dirTex || s.posTex; u.uDepth.value = rt.depthTexture; u.uLVP.value.copy(lvp); u.uL.value.copy(dir); u.uCol.value.copy(col); u.uMask.value.copy(mask);
      u.uDirect.value = (B.area && mask.lengthSq() > 0) ? 1 : 0; u.uW.value = 1 / (2 * nSky); u.uBounce.value.copy(bounce); u.uFCol.value = s.colTex || s.posTex; u.uGrassG.value = s.name === 'grass' ? 1 : 0; u.uKT.value = s.kt == null ? (o.kt == null ? .85 : o.kt) : s.kt; u.uTexel.value = texel; u.uRange.value = cam.far - cam.near; u.uTauH.value = s.tauH || .004; u.uTauO.value = s.tauO || .002; u.uAO.value = ao; u.uKind.value = s.kind; u.uK.value = s.k || 1; u.uN.value = s.n;
      R.setRenderTarget(s.acc); R.render(qScene, qCam); }
    if (o.sync) OB.sync(); tGather += now() - tb;
  }
  { const gl = R.getContext(); const b = new Float32Array(4); for (const s of allSets) { R.setRenderTarget(s.acc); gl.readBuffer(gl.COLOR_ATTACHMENT0); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.FLOAT, b); } R.setRenderTarget(null); }
  // подключаем запечённое к материалам
  for (const s of [S.grass, ...OB.heroes.map(H => H.fur)]) { s.uni.uB0.value = s.acc.textures[0]; s.uni.uB1.value = s.acc.textures[1]; s.uni.uB2.value = s.acc.textures[2]; }
  for (const S2 of [S.field, S.far, ...OB.heroes.map(H => H.set)]) for (const it of S2.list) { const u = it.m.material.uniforms; u.uB0.value = S2.acc.textures[0]; u.uB1.value = S2.acc.textures[1]; u.uB2.value = S2.acc.textures[2]; if (S2.name.startsWith('hero')) u.uLiveS.value = 1; }
  // у роговицы своя сетка — берём запечённое по ближайшей вершине глаза нельзя; даём видимость = 1
  OB.t.bake = now() - t0; OB.t.bakeDepth = tDepth; OB.t.bakeGather = tGather; OB.t.passes = passes.length;
  log('запекание', (OB.t.bake / 1000).toFixed(1), 'с; проходов', passes.length, 'глубина', (tDepth / 1000).toFixed(1), 'сбор', (tGather / 1000).toFixed(1));
};
function rnd(i) { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
function jit(d, ang, i, n) { if (n === 1) return d.clone(); const a = i * 2.39996, r = Math.sqrt((i + .5) / n) * ang; const t1 = new THREE.Vector3(0, 1, 0).cross(d).normalize(), t2 = d.clone().cross(t1);
  return d.clone().addScaledVector(t1, Math.cos(a) * r).addScaledVector(t2, Math.sin(a) * r).normalize(); }

// ---------- кадр ----------
let PP = null;
const PVS = 'in vec3 position; out vec2 vUv; void main() { vUv = position.xy * .5 + .5; gl_Position = vec4(position.xy, 0.0, 1.0); }';
function ppMat(fs, uni) { return new THREE.RawShaderMaterial({ vertexShader: PVS, fragmentShader: 'precision highp float; precision highp sampler2D;\n' + fs, uniforms: uni, glslVersion: THREE.GLSL3, depthTest: false, depthWrite: false }); }
function ppInit(w, h, samples) {
  const P = { w, h };
  P.main = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples, depthBuffer: true });
  P.main.depthTexture = new THREE.DepthTexture(w, h, THREE.UnsignedIntType);
  P.dof = new THREE.WebGLRenderTarget(w >> 1, h >> 1, { type: THREE.HalfFloatType, depthBuffer: false }); // размытие — на половинном размере
  P.b = [1, 2, 3, 4].map(k => [new THREE.WebGLRenderTarget(w >> k, h >> k, { type: THREE.HalfFloatType, depthBuffer: false }), new THREE.WebGLRenderTarget(w >> k, h >> k, { type: THREE.HalfFloatType, depthBuffer: false })]);
  P.scene = new THREE.Scene(); P.cam = new THREE.Camera(); P.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2)); P.quad.frustumCulled = false; P.scene.add(P.quad);
  // размытие по глубине: кружок нерезкости как у объектива (фокус, диафрагма, фокусное), сбор по спирали
  P.dofM = ppMat(`uniform sampler2D tC, tD; uniform float near, far, focus, coK, maxR; uniform vec2 px; in vec2 vUv; out vec4 oc;
    float lin(float d) { float z = d * 2.0 - 1.0; return 2.0 * near * far / (far + near - z * (far - near)); }
    float coc(float z) { return min(maxR, abs(coK * (z - focus) / max(z, 1e-3))); }
    void main() { float z0 = lin(texture(tD, vUv).r); float c0 = coc(z0); vec3 acc = texture(tC, vUv).rgb; float wsum = 1.0;
      if (c0 > .5 || true) { const int N = 48; for (int i = 1; i < N; i++) { float r = sqrt(float(i) / float(N)) * maxR; float a = float(i) * 2.39996; vec2 o = vec2(cos(a), sin(a)) * r;
        vec2 uv = vUv + o * px; float zs = lin(texture(tD, uv).r); float cs = coc(zs); float cc = zs < z0 ? cs : min(cs, c0); float w = smoothstep(r - 1.0, r + .5, cc); acc += texture(tC, uv).rgb * w; wsum += w; } }
      oc = vec4(acc / wsum, 1.0); }`, { tC: { value: null }, tD: { value: null }, near: { value: .1 }, far: { value: 100 }, focus: { value: 2 }, coK: { value: 10 }, maxR: { value: 16 }, px: { value: new THREE.Vector2() } });
  P.brM = ppMat(`uniform sampler2D t; uniform float thr; in vec2 vUv; out vec4 oc; void main() { vec3 c = texture(t, vUv).rgb; float l = max(c.r, max(c.g, c.b)); oc = vec4(c * max(0.0, l - thr) / max(l, 1e-4), 1.0); }`, { t: { value: null }, thr: { value: .85 } });
  P.blM = ppMat(`uniform sampler2D t; uniform vec2 d; in vec2 vUv; out vec4 oc; void main() { vec3 c = texture(t, vUv).rgb * .227; c += (texture(t, vUv + d * 1.385).rgb + texture(t, vUv - d * 1.385).rgb) * .316; c += (texture(t, vUv + d * 3.231).rgb + texture(t, vUv - d * 3.231).rgb) * .0703; oc = vec4(c, 1.0); }`, { t: { value: null }, d: { value: new THREE.Vector2() } });
  // AgX + «Punchy», как в Blender
  P.fin = ppMat(`uniform sampler2D tC, b1, b2, b3, b4, tDof, tD; uniform float glow, sat, con, expo, useDof, near, far, focus, coK, maxR; in vec2 vUv; out vec4 oc;
    float linz(float d) { float z = d * 2.0 - 1.0; return 2.0 * near * far / (far + near - z * (far - near)); }
    vec3 agx(vec3 c) {
      const mat3 toR = mat3(vec3(0.6274, 0.0691, 0.0164), vec3(0.3293, 0.9195, 0.0880), vec3(0.0433, 0.0113, 0.8956));
      const mat3 fromR = mat3(vec3(1.6605, -0.1246, -0.0182), vec3(-0.5876, 1.1329, -0.1006), vec3(-0.0728, -0.0083, 1.1187));
      const mat3 ins = mat3(vec3(0.856627153315983, 0.137318972929847, 0.11189821299995), vec3(0.0951212405381588, 0.761241990602591, 0.0767994186031903), vec3(0.0482516061458583, 0.101439036467562, 0.811302368396859));
      const mat3 outs = mat3(vec3(1.1271005818144368, -0.1413297634984383, -0.14132976349843826), vec3(-0.11060664309660323, 1.157823702216272, -0.11060664309660294), vec3(-0.016493938717834573, -0.016493938717834257, 1.2519364065950405));
      c = ins * (toR * c); c = max(c, 1e-10); c = log2(c); c = clamp((c + 12.47393) / (4.026069 + 12.47393), 0.0, 1.0);
      vec3 x2 = c * c, x4 = x2 * x2; c = 15.5 * x4 * x2 - 40.14 * x4 * c + 31.96 * x4 - 6.868 * x2 * c + 0.4298 * x2 + 0.1191 * c - 0.00232;
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); c = pow(max(c, 0.0), vec3(con)); c = l + sat * (c - l); // Punchy
      c = outs * c; c = pow(max(vec3(0.0), c), vec3(2.2)); c = fromR * c; return clamp(c, 0.0, 1.0); }
    vec3 srgb(vec3 c) { return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - .055, step(.0031308, c)); }
    void main() { vec3 c = texture(tC, vUv).rgb; if (useDof > .5) { float z = linz(texture(tD, vUv).r); float c0 = min(maxR, abs(coK * (z - focus) / max(z, 1e-3))); c = mix(c, texture(tDof, vUv).rgb, smoothstep(.5, 1.6, c0)); }
      vec3 g = texture(b1, vUv).rgb + texture(b2, vUv).rgb + texture(b3, vUv).rgb + texture(b4, vUv).rgb;
      c = mix(c, c + g * .25, glow); c *= expo; oc = vec4(srgb(agx(c)), 1.0); }`, { tC: { value: null }, b1: { value: null }, b2: { value: null }, b3: { value: null }, b4: { value: null }, glow: { value: .15 }, sat: { value: 1.4 }, con: { value: 1.35 }, expo: { value: 1 }, tDof: { value: null }, tD: { value: null }, useDof: { value: 0 }, near: { value: .1 }, far: { value: 100 }, focus: { value: 2 }, coK: { value: 1 }, maxR: { value: 16 } });
  return P; }
function pp(mat, uni, target) { PP.quad.material = mat; for (const k in uni) mat.uniforms[k].value = uni[k]; R.setRenderTarget(target); R.render(PP.scene, PP.cam); }

OB.SHOTS = { // камеры из render.py (Blender -> наши оси) — для Барсика в центре; для других героев — сдвиг и масштаб
  all: { pos: [0.3, 0.62, 2.75], look: [0.05, 0.47, 0], lens: 34, fstop: 4, focus: [0, 0.5, 0.1] },
  full: { pos: [0.9, 0.75, 2.9], look: [0, 0.5, 0], lens: 50, fstop: 3.2, focus: [0, 0.6, 0.1], eyes: [0.5, 0.75, 2.8] },
  medium: { pos: [0.62, 0.82, 2.4], look: [0, 0.6, 0.03], lens: 55, fstop: 3.2, focus: [0, 0.6, 0.1], eyes: [0.45, 0.8, 2.3] },
  close: { pos: [0.62, 0.9, 1.95], look: [0, 0.74, 0.04], lens: 55, fstop: 2.2, focus: 'eye', eyes: [0.36, 0.84, 1.6] },
  face: { pos: [0.3, 0.8, 1.25], look: [0, 0.72, 0.1], lens: 70, fstop: 3, focus: 'eye' },
  paw: { pos: [-0.42, 0.46, 0.8], look: [-0.17, 0.3, 0.1], lens: 70, fstop: 5, focus: [-0.18, 0.3, 0.12] },
  feet: { pos: [0.4, 0.28, 0.85], look: [0.06, 0.05, 0.1], lens: 60, fstop: 5, focus: [0.09, 0.04, 0.12] } };
OB.clipShot = function (t, dur) { dur = dur || 5; const k = t / dur, e = k * k * (3 - 2 * k); const A = OB.SHOTS.full, B = OB.SHOTS.medium;
  const L3 = (a, b) => a.map((x, i) => x + (b[i] - x) * e); const pos = L3(A.pos, B.pos), look = L3(A.look, B.look);
  const ang = (e - .5) * .22, c = Math.cos(ang), s2 = Math.sin(ang); const px = pos[0] * c - pos[2] * s2, pz = pos[0] * s2 + pos[2] * c;
  return { pos: [px, pos[1], pz], look, lens: A.lens + (B.lens - A.lens) * e, fstop: 3.2, focus: [0, 0.62, 0.1], eyes: [px * .55, 0.78, pz * .95] }; };
OB.heroShot = function (name, kind) { const H = OB.heroes.find(h => h.name === name); const S = OB.SHOTS[kind]; if (!H) return S;
  const c = Math.cos(H.yaw), s = Math.sin(H.yaw), k = H.k; const xf = p => { const x = p[0] * k, y = p[1] * k, z = p[2] * k; return [x * c + z * s + H.x, y, -x * s + z * c + H.z]; };
  const sh = { pos: xf(S.pos), look: xf(S.look), lens: S.lens, fstop: S.fstop }; sh.focus = S.focus === 'eye' ? 'eye:' + name : xf(S.focus); return sh; };
// ролик: все трое, медленный наезд
OB.animShot = function (t) { const ss = (a, b, x) => { x = Math.min(1, Math.max(0, (x - a) / (b - a))); return x * x * (3 - 2 * x); }; const k = ss(0, 6, t);
  const L3 = (a, b) => a.map((x, i) => x + (b[i] - x) * k);
  return { pos: L3([0.3, 0.62, 2.95], [0.24, 0.6, 2.45]), look: L3([0.05, 0.47, 0], [0.05, 0.48, 0]), lens: 34, fstop: 4, focus: [0, 0.5, 0.1] }; };
OB.frame = function (shotName, W, Hh, tsec, opt) {
  opt = opt || {}; const sh = typeof shotName === 'string' ? OB.SHOTS[shotName] : shotName; const samples = opt.msaa == null ? 4 : opt.msaa;
  if (!PP || PP.w !== W || PP.h !== Hh || PP.s !== samples) { PP = ppInit(W, Hh, samples); PP.s = samples; }
  R.setSize(W, Hh, false);
  const cam = OB.cam || (OB.cam = new THREE.PerspectiveCamera(20, W / Hh, .05, 120)); cam.aspect = W / Hh;
  const vf = 2 * Math.atan(18 / sh.lens * Hh / W) * 180 / Math.PI; cam.fov = vf; cam.position.set(...sh.pos); cam.lookAt(new THREE.Vector3(...sh.look)); cam.updateProjectionMatrix(); cam.updateMatrixWorld(true);
  if (opt.dolly) { cam.position.lerp(new THREE.Vector3(...sh.look).lerp(new THREE.Vector3(...sh.pos), .9), opt.dolly); cam.lookAt(new THREE.Vector3(...sh.look)); cam.updateMatrixWorld(true); }
  if (opt.anim != null) OB.pose(opt.anim);
  const pxK = 2 * Math.tan(vf * Math.PI / 360) / Hh;
  OB.scene.traverse(m => { if (m.userData && m.userData.strands) { const u = m.userData.mat.uniforms; u.uPx.value = pxK; u.uMinPx.value = 0.75; u.uTime.value = tsec || 0; } });
  if (OB.furHidden) for (const H of OB.heroes) H.fur.mesh.visible = false;
  const t0 = now();
  R.setRenderTarget(PP.main); R.setClearColor(new THREE.Color(0.378, 0.558, 0.54).lerp(new THREE.Color(0.56, 0.74, 0.7), .72), 1); R.clear(true, true, false);
  R.render(OB.scene, cam);
  // размытие фона
  let focus; if (typeof sh.focus === 'string' && sh.focus.startsWith('eye')) { const H = OB.heroes.find(h => h.name === (sh.focus.split(':')[1] || 'barsik')) || OB.heroes[0]; const e = H.eyes.reduce((a, b) => (b.c.x > a.c.x ? b : a)); focus = cam.position.distanceTo(e.e.getWorldPosition(new THREE.Vector3())); } else focus = cam.position.distanceTo(new THREE.Vector3(...sh.focus));
  const f = sh.lens / 1000, A = f / sh.fstop, coK = A * f / (focus - f) / (0.036 / W) * .5; // радиус кружка в пикселях = coK*|z-focus|/z
  const src = PP.main.texture, dofOn = opt.dof !== false, maxR = Math.min(24, W / 60);
  if (dofOn) pp(PP.dofM, { tC: PP.main.texture, tD: PP.main.depthTexture, near: cam.near, far: cam.far, focus, coK: coK / 2, maxR: maxR / 2, px: new THREE.Vector2(2 / W, 2 / Hh) }, PP.dof);
  // свечение
  pp(PP.brM, { t: src, thr: .85 }, PP.b[0][0]);
  for (let k = 0; k < 4; k++) { const [a, b] = PP.b[k]; if (k > 0) pp(PP.blM, { t: PP.b[k - 1][0].texture, d: new THREE.Vector2(0, 0) }, a);
    pp(PP.blM, { t: a.texture, d: new THREE.Vector2(1 / a.width, 0) }, b); pp(PP.blM, { t: b.texture, d: new THREE.Vector2(0, 1 / a.height) }, a); }
  pp(PP.fin, { tC: src, b1: PP.b[0][0].texture, b2: PP.b[1][0].texture, b3: PP.b[2][0].texture, b4: PP.b[3][0].texture, expo: opt.expo || 1, sat: opt.sat || 1.25, con: opt.con || 1.4,
    tDof: PP.dof.texture, tD: PP.main.depthTexture, useDof: dofOn ? 1 : 0, near: cam.near, far: cam.far, focus, coK, maxR }, null);
  if (opt.sync !== false) OB.sync();
  return now() - t0;
};
OB.sync = () => { R.setRenderTarget(null); const gl = R.getContext(); const px = new Uint8Array(4); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); return px[0]; };
OB.readSet = (name, ids) => { const st = OB.sets[name]; const gl = R.getContext(); const out = []; R.setRenderTarget(st.acc);
  for (const i of ids) { const r = [i]; for (let k = 0; k < 2; k++) { gl.readBuffer(gl.COLOR_ATTACHMENT0 + k); const b = new Float32Array(4); gl.readPixels(i % TW, Math.floor(i / TW), 1, 1, gl.RGBA, gl.FLOAT, b); r.push([...b].map(x => +x.toFixed(3))); } out.push(r); }
  gl.readBuffer(gl.COLOR_ATTACHMENT0); R.setRenderTarget(null); return out; };
OB.info = () => ({ log: OB.log, t: OB.t });
})();
