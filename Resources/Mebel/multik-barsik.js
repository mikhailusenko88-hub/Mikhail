// Барсик «неоновая основа»: каждый волосок светится своим заранее посчитанным светом (запечён в данных barsik/barsik_data.js),
// вязаный шарф с петлями и шерстяными ворсинками, глаза, веки с мехом, рот под голос. В «Мультиках» заменяет обычного Барсика
// в режиме «как в кино»: старый герой остаётся невидимым скелетом (его поза, руки для предметов, тень), а рисуется этот.
(function (global) {
'use strict';
const MKB = global.MKBarsik = { ready: false, error: null, base: 'barsik/', D: null, shellK: 1, shellU: { value: 1 }, desatU: { value: 0.22 }, tintU: { value: null }, trimU: { value: .82 }, softU: { value: .6 }, glossU: { value: 1 }, /* вариант «Б»: подстрижен, гладкий блеск (просьба Михаила 4.11) */ K: { key: 1.4, expo: 0.74 } };   // сверено с кадром Blender: лоб (152,126,84)   // shellU — сила налёта (0 — выключен)
MKB.isBarsik = spec => !!spec && spec.kind === 'cat' && /^\s*барсик(?![а-яё])/i.test(String(spec.name || ''));

// ---------- константы модели (метры, z вверх, мордочка к −y) ----------
const sstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const sgn1 = x => Math.min(1, Math.max(0, x));
const SHS = [[-0.128, -0.035, 0.5], [0.128, -0.035, 0.5]], WRS = [[-0.19, -0.1, 0.34], [0.19, -0.1, 0.34]];
const PH = [0, -0.01, 0.6], HEAD_C = 0.76, HEAD_R = 0.21;
function zc(x) { const ax = Math.abs(x); if (ax <= 0.037) { const c = Math.min(1, Math.max(-1, 1 - ax / 0.0185)); return 0.671 - 0.011 * Math.sin(Math.acos(c)); } return 0.671; }
function extraW(p, reg) {   // веса костей: ноги, руки, нижняя челюсть, предплечье
  if (reg === 8 && p[2] < 0.42) reg = 5;   // розовые подушечки лап (образец 6.2) — часть лапы, а не уха
  let wl = 0, wa = 0, wj = 0, wf = 0;
  if (reg !== 7 && reg !== 5 && reg < 20) wl = sstep(0.27, 0.12, p[2]) * sstep(0.012, 0.05, Math.abs(p[0])) * Math.sign(p[0]);
  { const e = p[0] > 0 ? 1 : 0, S = SHS[e], Wr = WRS[e]; const d = [Wr[0] - S[0], Wr[1] - S[1], Wr[2] - S[2]]; const sg = e ? 1 : -1;
    const q = ((p[0] - S[0]) * d[0] + (p[1] - S[1]) * d[1] + (p[2] - S[2]) * d[2]) / (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]); const ds = Math.hypot(p[0] - S[0], p[1] - S[1], p[2] - S[2]);
    if (reg === 5) { wa = sg; wf = sstep(0.4, 0.52, q) * sg; } /* лапа — отдельная сетка (с плечом), идёт целиком; бок туловища под ней свой и за лапой не тянется */ }
  if (reg === 1 || reg === 2) wj = sstep(zc(p[0]) + 0.001, zc(p[0]) - 0.0045, p[2]) * sstep(-0.115, -0.15, p[1]) * sstep(0.05, 0.036, Math.abs(p[0]));
  return [Math.round(wl * 127), Math.round(wa * 127), Math.round(wj * 255), Math.round(wf * 127)];
}
function mulberry(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const nrm = a => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

// ---------- загрузка данных ----------
function loadScript(src) { return new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('нет ' + src)); document.head.appendChild(s); }); }
MKB.load = function () {
  if (MKB._p) return MKB._p;
  return (MKB._p = (async () => {
    try {
      if (!global.BARSIK_GZ) await loadScript(MKB.base + 'barsik_data.js');
      if (typeof DecompressionStream === 'undefined') throw new Error('нет DecompressionStream');
      const H = global.BARSIK_HDR, s = global.BARSIK_GZ; const bin = atob(s); const u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const ab = await new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
      try { delete global.BARSIK_GZ; } catch (e) { global.BARSIK_GZ = null; }
      MKB.D = decode(H, ab); MKB.ready = true;
      try { const rc = global.MK3D && MK3D.rigs && MK3D.rigs(); if (rc) for (const k in rc) { const r = rc[k]; if (r && !r.bars && MKB.isBarsik(r.spec)) { r.root.visible = false; if (r.root.parent) r.root.parent.remove(r.root); delete rc[k]; } } } catch (e) {}   // старый Барсик, построенный до загрузки, — заново
      return true;
    } catch (e) { MKB.error = e && e.message || String(e); console.log('Барсик (неон):', MKB.error); MKB._p = null; return false; }
  })());
};
function decode(H, ab) {
  const B = new Uint8Array(ab), dv = new DataView(ab); const nf = H.nfur, nsk = H.nskin, ntri = H.ntri, D = {};
  // волоски + усы + рот (усы и линия рта — тоже «волоски» из 5 точек)
  const lines = H.lines.map(l => { const P = l.p; const L = [0]; for (let i = 1; i < P.length; i++) L.push(L[i - 1] + Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1], P[i][2] - P[i - 1][2]));
    const out = []; for (let k = 0; k < 5; k++) { const tl = L[L.length - 1] * k / 4; let i = 1; while (i < P.length - 1 && L[i] < tl) i++; const a = (tl - L[i - 1]) / Math.max(1e-9, L[i] - L[i - 1]); out.push([0, 1, 2].map(j => P[i - 1][j] + (P[i][j] - P[i - 1][j]) * a)); }
    return { w: l.w, p: out, h: l.h[0] }; });
  const NS = nf + lines.length; D.NS = NS;
  const TW = 2048, rowsP = Math.ceil(NS * 5 / TW), rowsB = Math.ceil(NS * 6 / TW), rowsA = Math.ceil(NS * 3 / TW); D.TW = TW; D.rows = [rowsP, rowsB, rowsA];
  const pos = new Float32Array(TW * rowsP * 4), bake = new Uint8Array(TW * rowsB * 4), attr = new Uint8Array(TW * rowsA * 4);
  for (let s2 = 0; s2 < nf; s2++) { const o = s2 * 45; const rx = dv.getInt16(o, true) / 20000, ry = dv.getInt16(o + 2, true) / 20000, rz = dv.getInt16(o + 4, true) / 20000;
    const pb = s2 * 20; pos[pb] = rx; pos[pb + 1] = ry; pos[pb + 2] = rz; pos[pb + 3] = B[o + 39] / 100000;
    for (let k = 1; k < 5; k++) { const q = o + 6 + (k - 1) * 3; pos[pb + k * 4] = rx + dv.getInt8(q) / 1580; pos[pb + k * 4 + 1] = ry + dv.getInt8(q + 1) / 1580; pos[pb + k * 4 + 2] = rz + dv.getInt8(q + 2) / 1580; }
    pos[pb + 7] = B[o + 44];
    const bb = s2 * 24; for (let c = 0; c < 6; c++) { bake[bb + c * 4] = B[o + 18 + c]; bake[bb + c * 4 + 1] = B[o + 24 + c]; bake[bb + c * 4 + 2] = B[o + 30 + c]; }
    const ab2 = s2 * 12; { const w = extraW([rx, ry, rz], B[o + 44]); attr[ab2 + 8] = w[0] & 255; attr[ab2 + 9] = w[1] & 255; attr[ab2 + 10] = w[2]; attr[ab2 + 11] = w[3] & 255; }
    attr[ab2] = B[o + 36]; attr[ab2 + 1] = B[o + 37]; attr[ab2 + 2] = B[o + 38]; attr[ab2 + 3] = 255; attr[ab2 + 4] = B[o + 40]; attr[ab2 + 5] = B[o + 41]; attr[ab2 + 6] = B[o + 42]; attr[ab2 + 7] = B[o + 43]; }
  lines.forEach((l, i) => { const s2 = nf + i, pb = s2 * 20; for (let k = 0; k < 5; k++) { pos[pb + k * 4] = l.p[k][0]; pos[pb + k * 4 + 1] = l.p[k][1]; pos[pb + k * 4 + 2] = l.p[k][2]; }
    pos[pb + 3] = l.w ? 0.0017 : 0.0011; pos[pb + 7] = l.w ? 201 : 200; const bb = s2 * 24; const bv = [255, 255, 255, 255, 230, 170]; for (let c = 0; c < 6; c++) { bake[bb + c * 4] = bake[bb + c * 4 + 1] = bake[bb + c * 4 + 2] = bv[c]; }
    const al = l.w ? [0.12, 0.04, 0.03] : [0.92, 0.9, 0.86]; const ab2 = s2 * 12; for (let j = 0; j < 3; j++) attr[ab2 + j] = Math.round(Math.sqrt(al[j]) * 255); attr[ab2 + 4] = Math.round(Math.min(1, l.h) * 255); attr[ab2 + 5] = 255; attr[ab2 + 6] = 0; attr[ab2 + 7] = 0; });
  D.pos = pos; D.bake = bake; D.attr = attr;
  // кожа, нос, шарф: отдельные массивы (у three.js атрибут — один тип чисел)
  const skOff = nf * 45; const sk = new Uint8Array(ab, skOff, nsk * 24), sdv = new DataView(ab, skOff, nsk * 24);
  const P = new Float32Array(nsk * 3), N = new Float32Array(nsk * 3), A = new Float32Array(nsk * 3), B0 = new Float32Array(nsk * 3), B1 = new Float32Array(nsk * 3), W = new Float32Array(nsk * 4), X = new Float32Array(nsk * 4), M = new Float32Array(nsk);
  for (let i = 0; i < nsk; i++) { const o = i * 24; const p = [sdv.getInt16(o, true) / 20000, sdv.getInt16(o + 2, true) / 20000, sdv.getInt16(o + 4, true) / 20000]; P.set(p, i * 3);
    let ex = sdv.getInt8(o + 6) / 127, ey = sdv.getInt8(o + 7) / 127, ez = 1 - Math.abs(ex) - Math.abs(ey); if (ez < 0) { const tx = (1 - Math.abs(ey)) * Math.sign(ex), ty = (1 - Math.abs(ex)) * Math.sign(ey); ex = tx; ey = ty; } const nn = nrm([ex, ey, ez]); N.set(nn, i * 3);
    for (let c = 0; c < 3; c++) { const a = sk[o + 8 + c] / 255; A[i * 3 + c] = a * a; B0[i * 3 + c] = sk[o + 11 + c] / 255; B1[i * 3 + c] = sk[o + 14 + c] / 255; }
    const m = sk[o + 21]; M[i] = m; W[i * 4] = sk[o + 17] / 255; W[i * 4 + 1] = sk[o + 18] > 254.5 ? -1 : sk[o + 18] / 254; W[i * 4 + 2] = sdv.getInt8(o + 19) / 127; W[i * 4 + 3] = sk[o + 20] / 255;
    const w = extraW(p, m === 21 ? 2 : m === 22 ? 0 : m); X[i * 4] = w[0] / 127; X[i * 4 + 1] = w[1] / 127; X[i * 4 + 2] = w[2] / 255; X[i * 4 + 3] = w[3] / 127; }
  D.skin = { P, N, A, B0, B1, W, X, M, idx: new Uint32Array(ab.slice(skOff + nsk * 24, skOff + nsk * 24 + ntri * 12)) };
  const e = H.eyes; D.E0 = [[e[0], e[1], e[2]], [e[3], e[4], e[5]]]; D.LIDN0 = [[e[6], e[7], e[8]], [e[9], e[10], e[11]]]; D.LIDOFF = e[12]; D.RE = e[13]; D.LIDCOL = [0.62, 0.3, 0.075];
  // мех на веках
  { const R = D.RE + 0.0045, th0 = Math.acos(D.LIDOFF / R), th1 = Math.acos(-0.72 * D.RE / R); D.lidR = R; D.th0 = th0; D.LB1 = []; D.LB2 = []; const arr = [];
    for (let k2 = 0; k2 < 2; k2++) { const a = D.LIDN0[k2], b1 = nrm(cross(a, [1, 0, 0])), b2 = cross(a, b1); D.LB1.push(b1); D.LB2.push(b2); const r = mulberry(77 + k2);
      for (let k = 0; k < 14000; k++) { const lam = r() * 6.2832, u = (th1 - th0) * r(), th = th1 - u; const dy = a[1] * Math.cos(th) + (b1[1] * Math.cos(lam) + b2[1] * Math.sin(lam)) * Math.sin(th); if (dy > 0.2) continue;
        arr.push(k2, lam, u, (0.0055 + 0.003 * r()) * (u < 0.09 ? 1.35 : 1), 0.12 + 0.15 * r(), 0.85 + 0.3 * r(), 0, 0); } }
    D.lidFur = new Float32Array(arr); }
  // рот: полоска вдоль линии «ω»; низ уходит вместе с челюстью
  { const NX = 25, NV = 6, PP = [], UV = [], I = [];
    const surfY = (x, z) => { let best = 1; for (let i = 0; i < nsk; i++) { const vx = P[i * 3], vy = P[i * 3 + 1], vz = P[i * 3 + 2]; if (vy > -0.12 || Math.abs(vx - x) > 0.004 || Math.abs(vz - z) > 0.004) continue; if (vy < best) best = vy; } return best < 0.9 ? best : -0.2; };
    const ys = []; for (let i = 0; i < NX; i++) { const x = (i / (NX - 1) * 2 - 1) * 0.037; ys.push(surfY(x, zc(x) - 0.0004)); }
    for (let j = 0; j < NV; j++) for (let i = 0; i < NX; i++) { const x = (i / (NX - 1) * 2 - 1) * 0.037; PP.push(x, ys[i] - 0.0009, zc(x) - 0.0004); UV.push(x / 0.037, j / (NV - 1)); }
    for (let j = 0; j < NV - 1; j++) for (let i = 0; i < NX - 1; i++) { const a = j * NX + i; I.push(a, a + 1, a + NX, a + 1, a + NX + 1, a + NX); }
    D.mouth = { P: new Float32Array(PP), UV: new Float32Array(UV), I: new Uint32Array(I) }; }
  return D;
}

// ---------- шейдеры (как в пробной сцене, свет — от места мультика) ----------
const COMMON = `precision highp float; precision highp int; precision highp sampler2D;
uniform mat4 modelMatrix, viewMatrix, projectionMatrix; uniform vec3 cameraPosition;
uniform mat3 uHead, uEar0, uEar1, uLeg0, uLeg1, uArm0, uArm1, uFore0, uFore1, uJawM; uniform vec4 uArmQ0, uArmQ1; uniform vec2 uLift; uniform float uTailA, uTailPh, uBreath, uScale, uPix, uExpo, uDesat, uTrim, uSoft, uGloss; uniform vec3 uTint;
uniform vec3 uSunDir, uSunCol, uRimDir, uRimCol, uFillDir, uFillCol, uSky, uGnd, uUp, uFogCol; uniform vec2 uFog;
const float PI = 3.14159265;
vec3 sane(vec3 c) { bvec3 bad = equal(floatBitsToUint(c) & uvec3(0x7f800000u), uvec3(0x7f800000u)); vec3 r = min(max(c, vec3(0.0)), vec3(300.0)); return any(bad) ? vec3(0.0) : r; }
vec3 snrm(vec3 v, vec3 fb) { float l = dot(v, v); return l > 1e-14 ? v * inversesqrt(l) : fb; }
const vec3 PH = vec3(0.0, -0.01, 0.6), EARB0 = vec3(-0.122, 0.012, 0.893), EARB1 = vec3(0.122, 0.012, 0.893), TAIL0 = vec3(0.0, 0.13, 0.19);
const vec3 HIP0 = vec3(-0.088, -0.005, 0.17), HIP1 = vec3(0.088, -0.005, 0.17), SH0 = vec3(-0.128, -0.035, 0.5), SH1 = vec3(0.128, -0.035, 0.5), ELB0 = vec3(-0.156, -0.064, 0.428), ELB1 = vec3(0.156, -0.064, 0.428), JAWP = vec3(0.0, -0.1, 0.675);
mat3 rotAxis(vec3 a, float g) { a = normalize(a); float c = cos(g), s = sin(g), t = 1.0 - c;
  return mat3(t*a.x*a.x+c, t*a.x*a.y+s*a.z, t*a.x*a.z-s*a.y, t*a.x*a.y-s*a.z, t*a.y*a.y+c, t*a.y*a.z+s*a.x, t*a.x*a.z+s*a.y, t*a.y*a.z-s*a.x, t*a.z*a.z+c); }
vec3 poseP(vec3 p, float wh, float ts, float we, float wb, vec4 wx) {
  vec3 q = p;
  if (wb > 0.01) { float b = uBreath * wb; q.x *= 1.0 + b; q.y = (q.y + 0.02) * (1.0 + b * 0.9) - 0.02; }
  if (ts >= 0.0) { float a = uTailA * sin(uTailPh - 2.4 * ts) * pow(ts, 1.2); q = rotAxis(vec3(0.15, 0.0, 1.0), a) * (q - TAIL0) + TAIL0; }
  if (we > 0.001) q = mix(q, uEar1 * (q - EARB1) + EARB1, we); else if (we < -0.001) q = mix(q, uEar0 * (q - EARB0) + EARB0, -we);
  if (wx.x > 0.001) q = mix(q, uLeg1 * (q - HIP1) + HIP1 + vec3(0.0, 0.0, uLift.y), wx.x); else if (wx.x < -0.001) q = mix(q, uLeg0 * (q - HIP0) + HIP0 + vec3(0.0, 0.0, uLift.x), -wx.x);
  if (wx.w > 0.001) q = mix(q, uFore1 * (q - ELB1) + ELB1, wx.w); else if (wx.w < -0.001) q = mix(q, uFore0 * (q - ELB0) + ELB0, -wx.w);
  if (abs(wx.y) > 0.001) { bool r1 = wx.y > 0.0; float w = abs(wx.y); vec3 sh = r1 ? SH1 : SH0; vec4 aq = r1 ? uArmQ1 : uArmQ0; q = (w > 0.995 ? (r1 ? uArm1 : uArm0) : rotAxis(aq.xyz, aq.w * w)) * (q - sh) + sh; }
  if (wx.z > 0.001) q = mix(q, uJawM * (q - JAWP) + JAWP, wx.z);
  if (wh > 0.0) q = mix(q, uHead * (q - PH) + PH, wh);
  return q;
}
vec3 poseN(vec3 n, float wh, vec4 wx) { vec3 m = n;
  if (wx.w > 0.001) m = mix(m, uFore1 * m, wx.w); else if (wx.w < -0.001) m = mix(m, uFore0 * m, -wx.w);
  if (wx.x > 0.001) m = mix(m, uLeg1 * m, wx.x); else if (wx.x < -0.001) m = mix(m, uLeg0 * m, -wx.x);
  if (abs(wx.y) > 0.001) { bool r1 = wx.y > 0.0; float w = abs(wx.y); vec4 aq = r1 ? uArmQ1 : uArmQ0; m = (w > 0.995 ? (r1 ? uArm1 : uArm0) : rotAxis(aq.xyz, aq.w * w)) * m; }
  if (wx.z > 0.001) m = mix(m, uJawM * m, wx.z); return mix(m, uHead * m, wh); }
vec3 toW(vec3 p) { return (modelMatrix * vec4(p, 1.0)).xyz; }
vec3 toWN(vec3 n) { return normalize(mat3(modelMatrix) * n); }
void lightAt(int i, vec3 p, out vec3 L, out vec3 E) {   // 0 — солнце места, 1 — контровой, 2 — мягкий спереди, 3 — нет
  if (i == 0) { L = uSunDir; E = uSunCol; } else if (i == 1) { L = uRimDir; E = uRimCol; } else if (i == 2) { L = uFillDir; E = uFillCol; } else { L = uUp; E = vec3(0.0); } }
float hash13(vec3 p) { p = fract(p * 0.1031); p += dot(p, p.zyx + 31.32); return fract((p.x + p.y) * p.z); }
float vn(vec3 p) { vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash13(i), hash13(i + vec3(1,0,0)), f.x), mix(hash13(i + vec3(0,1,0)), hash13(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash13(i + vec3(0,0,1)), hash13(i + vec3(1,0,1)), f.x), mix(hash13(i + vec3(0,1,1)), hash13(i + vec3(1,1,1)), f.x), f.y), f.z); }
float fbm(vec3 p, int o) { float a = 0.0, w = 0.5, s = 0.0; for (int i = 0; i < 6; i++) { if (i >= o) break; a += w * vn(p); s += w; p = p * 2.03 + vec3(1.7, 9.2, 3.1); w *= 0.5; } return a / s; }
vec3 fogMix(vec3 c, float d) { if (uFog.y <= 0.0) return c; return mix(c, uFogCol, clamp((d - uFog.x) / max(uFog.y - uFog.x, 1e-3), 0.0, 1.0)); }
vec4 outC(vec3 c, float d) { c *= uExpo * uTint; float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); c = mix(c, vec3(l), uDesat * clamp(l * 1.4, 0.0, 1.0)); return vec4(sane(fogMix(c, d)), 1.0); }   // мягче рыжий в светах — как AgX у Blender
float gauss(float x, float b) { return exp(-x*x / (2.0*b*b)) / (2.5066 * b); }
vec3 hairSpec(vec3 T, vec3 L, vec3 V, vec3 alb, float k) {
  float si = clamp(dot(T, L), -1.0, 1.0), so = clamp(dot(T, V), -1.0, 1.0); float ti = asin(si), to = asin(so), th = 0.5 * (ti + to), td = 0.5 * (to - ti); float ci = sqrt(max(0.0, 1.0 - si*si));
  vec3 lp = L - T * si, vp = V - T * so; float ll = length(lp) * length(vp); float cphi = ll > 1e-8 ? clamp(dot(lp, vp) / ll, -1.0, 1.0) : 1.0; float phi = acos(cphi); float ch = cos(0.5 * phi); float cd2 = max(0.2, cos(td)*cos(td));
  float R = gauss(th + 0.06, 0.16) * 0.25 * ch * 0.09; float tt = gauss(th - 0.03, 0.09) * exp(-(PI - phi)*(PI - phi) / (2.0*0.32*0.32)) * 0.55; float trt = gauss(th - 0.12, 0.3) * 0.25 * ch * 0.35;
  return (vec3(R) + pow(max(alb, vec3(0.0)), vec3(0.6)) * tt + pow(max(alb, vec3(0.0)), vec3(1.3)) * trt) * (ci / cd2 * k); }
`;
const VS_FUR = COMMON + `
uniform sampler2D uPos; uniform sampler2D uBake; uniform sampler2D uAttr;
out vec3 vP; out vec3 vT; out float vt; out vec3 vB0; out vec3 vB1; out vec3 vAlb; flat out int vKind;
ivec2 ti(int i) { return ivec2(i & 2047, i >> 11); }
void main() {
  int s = gl_InstanceID, k = gl_VertexID >> 1; float side = (gl_VertexID & 1) == 0 ? -1.0 : 1.0;
  vec4 a0 = texelFetch(uAttr, ti(s * 3), 0), a1 = texelFetch(uAttr, ti(s * 3 + 1), 0), a2 = texelFetch(uAttr, ti(s * 3 + 2), 0);
  vec4 wx = vec4(a2.x * 255.0, a2.y * 255.0, a2.z, a2.w * 255.0); wx.x = (wx.x > 127.5 ? wx.x - 256.0 : wx.x) / 127.0; wx.y = (wx.y > 127.5 ? wx.y - 256.0 : wx.y) / 127.0; wx.w = (wx.w > 127.5 ? wx.w - 256.0 : wx.w) / 127.0;
  float wh = a1.x, ts = a1.y > 0.999 ? -1.0 : a1.y * 255.0 / 254.0, we = a1.z * 255.0; we = (we > 127.5 ? we - 256.0 : we) / 127.0; float wb = a1.w;
  vec4 r0 = texelFetch(uPos, ti(s * 5), 0); int kind = int(texelFetch(uPos, ti(s * 5 + 1), 0).w + 0.5);
  int ka = max(k - 1, 0), kb = min(k + 1, 4); float tr = (kind == 0 || kind == 5 || kind == 6 || kind == 7) ? uTrim : 1.0;   // «подстричь» тело, лапы, хвост
  vec3 p = toW(poseP(r0.xyz + (texelFetch(uPos, ti(s * 5 + k), 0).xyz - r0.xyz) * tr, wh, ts, we, wb, wx));
  vec3 pa = toW(poseP(r0.xyz + (texelFetch(uPos, ti(s * 5 + ka), 0).xyz - r0.xyz) * tr, wh, ts, we, wb, wx)), pb = toW(poseP(r0.xyz + (texelFetch(uPos, ti(s * 5 + kb), 0).xyz - r0.xyz) * tr, wh, ts, we, wb, wx));
  vec3 T = normalize(pb - pa + 1e-7); float t = float(k) / 4.0;
  float rad = r0.w * uScale * (kind == 201 ? 1.0 : (1.0 - 0.85 * pow(t, 1.3)));
  float dist = length(p - cameraPosition); float w = max(rad, uPix * dist * mix(0.55, 0.42, uGloss));
  vec3 sd = normalize(cross(T, p - cameraPosition) + 1e-7) * w * side;
  vec3 P = p + sd; gl_Position = projectionMatrix * viewMatrix * vec4(P, 1.0);
  vec3 c[6]; for (int j = 0; j < 6; j++) { vec3 b = texelFetch(uBake, ti(s * 6 + j), 0).rgb; float u = clamp((t - 0.5) * 4.0, 0.0, 2.0); float v = u < 1.0 ? mix(b.x, b.y, u) : mix(b.y, b.z, u - 1.0); if (t < 0.5) v = b.x * (0.45 + 1.1 * t); c[j] = vec3(v); }
  vB0 = vec3(c[0].x, c[1].x, c[2].x); vB1 = vec3(c[3].x, c[4].x, c[5].x);
  vec3 alb = a0.rgb * a0.rgb; if (kind < 200) alb *= mix(vec3(1.0), kind == 12 ? vec3(0.8) : mix(vec3(0.62, 0.55, 0.5), vec3(0.84, 0.8, 0.77), uSoft), (1.0 - t) * (1.0 - t));   // мягче: корни не такие тёмные
  vAlb = alb; vP = P; vT = T; vt = t; vKind = kind;
}`;
const FS_FUR = COMMON + `
in vec3 vP; in vec3 vT; in float vt; in vec3 vB0; in vec3 vB1; in vec3 vAlb; flat in int vKind; out vec4 o;
void main() {
  vec3 V = normalize(cameraPosition - vP), T = snrm(vT, V), alb = vAlb; float bk[6] = float[6](vB0.x, vB0.y, vB0.z, vB1.x, vB1.y, vB1.z);
  vec3 col = vec3(0.0), msc = vec3(0.0), sp = vec3(0.0); float sk = vKind == 200 ? 1.6 : 1.0;
  for (int i = 0; i < 3; i++) { vec3 L, E; lightAt(i, vP, L, E); float sl = sqrt(max(0.0, 1.0 - dot(T, L) * dot(T, L)));
    col += E * (bk[i] * (0.35 + 0.65 * sl)); msc += E * pow(max(bk[i], 0.0), 0.33); sp += hairSpec(T, L, V, alb, sk) * E * bk[i]; }
  vec3 c = alb * (col + uSky * (PI * bk[4] * 0.85) + uGnd * (PI * bk[5] * 0.6)) / PI;
  if (vKind < 200) c += alb * alb * msc * (0.32 / PI);
  sp *= mix(1.0, 1.8, uGloss); sp = mix(sp, sp * vec3(1.0, 0.8, 0.55) * 1.25, 0.5 * uGloss);   // гладкий блеск вдоль шерсти, тёплый, как в образце 6.2
  c += sp + hairSpec(T, normalize(uUp + V * 0.3), V, alb, 0.5) * uSky * (bk[4] * 1.2 * PI);
  if (vKind == 201) c = alb * (0.35 + 0.25 * min(1.0, dot(col, vec3(0.333))));   // линия рта «ω» — тёмная, без блеска (как в Blender)
  o = outC(c, length(vP - cameraPosition));
}`;
const VS_SKIN = COMMON + `
in vec3 position; in vec3 aN; in vec3 aA; in vec3 aB0; in vec3 aB1; in vec4 aW; in vec4 aX; in float aM;
out vec3 vP; out vec3 vN; out vec3 vA; out vec3 vB0; out vec3 vB1; out float vZ; out vec3 vQ; flat out int vM;
void main() { vec3 p = position; vec3 P = toW(poseP(p, aW.x, aW.y, aW.z, aW.w, aX)); vN = toWN(poseN(aN, aW.x, aX)); vP = P; vA = aA; vB0 = aB0; vB1 = aB1; vZ = p.z; vQ = p; vM = int(aM + 0.5);
  gl_Position = projectionMatrix * viewMatrix * vec4(P, 1.0); }`;
// БАРС · налёт (из «неона» v4): кожа ещё 6 раз прозрачными слоями внутри шерсти — «молекулы» загораются, когда сквозь них идёт свет
const VS_SHELL = COMMON + `
in vec3 position; in vec3 aN; in vec3 aA; in vec3 aB0; in vec3 aB1; in vec4 aW; in vec4 aX; in float aM; uniform float uShellH;
out vec3 vP; out vec3 vN; out vec3 vA; out vec3 vB0; out vec3 vB1; out vec3 vQ; out float vF;
void main() { int m = int(aM + 0.5); float fr = (m != 2 && m != 8 && m < 10 && dot(aA, vec3(0.33)) > 0.06) ? 1.0 : 0.0; vec3 p = position + aN * (uShellH * fr);
  vec3 P = toW(poseP(p, aW.x, aW.y, aW.z, aW.w, aX)); vN = toWN(poseN(aN, aW.x, aX)); vP = P; vA = aA; vB0 = aB0; vB1 = aB1; vQ = position; vF = fr;
  gl_Position = projectionMatrix * viewMatrix * vec4(P, 1.0); }`;
const FS_SHELL = COMMON + `
in vec3 vP; in vec3 vN; in vec3 vA; in vec3 vB0; in vec3 vB1; in vec3 vQ; in float vF; uniform float uT, uShellK; out vec4 o;
void main() { if (vF < 0.5 || uShellK <= 0.0) discard; vec3 V = normalize(cameraPosition - vP), n = snrm(vN, V); if (dot(n, V) < 0.0) n = -n; float nv = max(dot(n, V), 0.0);
  float m = vn(vQ * 650.0) * 0.7 + vn(vQ * 1900.0) * 0.3; float cover = smoothstep(uT - 0.25, uT + 0.05, m); if (cover < 0.02) discard;
  vec3 alb = pow(vA, vec3(0.55)) * 0.9; float sun = max(vB0.x, 0.15), sky = max(vB1.y, 0.3);
  float ndl = dot(n, uSunDir), rim = pow(1.0 - nv, 1.3), back = clamp(dot(-uSunDir, V), 0.0, 1.0);
  vec3 warm = min(alb, vec3(0.75)) * vec3(1.15, 0.9, 0.6) + vec3(0.10, 0.06, 0.03);
  float through = rim * (0.35 + 0.65 * back) * clamp(1.0 - ndl * 0.6, 0.0, 1.0) * (0.3 + 0.7 * uT);
  vec3 c = uSunCol * sun * warm * through * 2.2;                                     // свет насквозь: край шерсти загорается тёплым
  c += uSunCol * sun * alb * clamp((ndl + 0.9) / 1.9, 0.0, 1.0) * 0.10 * uT;         // бархат от прямого света
  c += uRimCol * warm * rim * back * 0.6 * uT;                                        // контровой места
  c += alb * uSky * PI * sky * 0.35 * uT;                                             // пух на фоне светлого неба
  float a = cover * (0.12 + 0.30 * rim) * (0.4 + 0.6 * uT);
  vec4 r = outC(c, length(vP - cameraPosition)); o = vec4(r.rgb * cover * uShellK, a * uShellK); }`;
const KNIT = `
const float ROWH = 0.0075, COLW = 0.0105;
const vec3 RC[2] = vec3[2](vec3(0.0, -0.012, 0.582), vec3(0.0, -0.004, 0.614)); const float RR[2] = float[2](0.106, 0.1), RT[2] = float[2](0.044, 0.034), RZ[2] = float[2](0.84, 0.84), RX[2] = float[2](0.05, 0.12), NR[2] = float[2](89.0, 84.0), NC[2] = float[2](24.0, 19.0);
const vec3 KC = vec3(0.066, -0.128, 0.547), KR = vec3(0.046, 0.037, 0.041);
const vec3 TA[2] = vec3[2](vec3(0.052, -0.141, 0.53), vec3(0.08, -0.137, 0.525)), TU[2] = vec3[2](vec3(-0.14973, -0.06125, -0.98683), vec3(0.22274, -0.02784, -0.97448)),
  TN[2] = vec3[2](vec3(0.00919, -0.99812, 0.06056), vec3(-0.0062, -0.99961, 0.02714)), TW[2] = vec3[2](vec3(-0.98868, 0.0, 0.15001), vec3(-0.97486, 0.0, -0.22282));
const float TL[2] = float[2](0.14694, 0.10775), THW0[2] = float[2](0.027, 0.025), THW1[2] = float[2](0.034, 0.031);
const vec3 SA_[8] = vec3[8](vec3(0.05682, -0.14976, 0.38497), vec3(0.03934, -0.14976, 0.38762), vec3(0.02186, -0.14976, 0.39027), vec3(0.00438, -0.14976, 0.39293), vec3(0.12668, -0.13989, 0.42929), vec3(0.11097, -0.13989, 0.42569), vec3(0.09525, -0.13989, 0.4221), vec3(0.07954, -0.13989, 0.41851));
const vec3 SB_[8] = vec3[8](vec3(0.05543, -0.15662, 0.35682), vec3(0.03816, -0.15432, 0.36127), vec3(0.01726, -0.15266, 0.36227), vec3(-0.00697, -0.15317, 0.36084), vec3(0.13573, -0.14515, 0.40449), vec3(0.11722, -0.14313, 0.39968), vec3(0.10153, -0.14328, 0.38817), vec3(0.08042, -0.14371, 0.39244));
vec3 knitUV(vec3 q) { float best = 1e9; vec3 res = vec3(0.0);
  for (int i = 0; i < 2; i++) { vec3 d = q - RC[i]; float cs = cos(RX[i]), sn = sin(RX[i]); float y = d.y * cs - d.z * sn, z = d.y * sn + d.z * cs; float a = length(vec2(d.x, y)) - RR[i];
    float sd = length(vec2(a, z / RZ[i])) - RT[i]; if (sd < best) { best = sd; res = vec3(atan(z / RZ[i], a) / 6.2832 * NC[i], atan(y, d.x) / 6.2832 * NR[i], 0.0); } }
  { vec3 d = q - KC; float sd = (length(d / KR) - 1.0) * 0.037; if (sd < best) { best = sd; res = vec3(atan(d.y, d.x) / 6.2832 * 25.0, atan(d.z, length(d.xy)) * 0.042 / ROWH, 0.0); } }
  for (int i = 0; i < 2; i++) { vec3 d = q - TA[i]; float s = dot(d, TU[i]), dn = dot(d, TN[i]), dw = dot(d, TW[i]); float sc = clamp(s, 0.0, TL[i]); float hw = mix(THW0[i], THW1[i], sc / TL[i]);
    float sd = max(max(abs(dn) - 0.0098, abs(dw) - hw), max(-s, s - TL[i])); if (sd < best) { best = sd; res = vec3(dw / COLW + (dn > 0.0 ? 0.5 : 0.0), s / ROWH, 0.0); } }
  for (int i = 0; i < 8; i++) { vec3 pa = q - SA_[i], ba = SB_[i] - SA_[i]; float hh = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); vec3 rr = pa - ba * hh; float sd = length(rr) - 0.0038;
    if (sd < best) { best = sd; vec3 bn = normalize(ba), e1 = normalize(cross(bn, vec3(1.0, 0.0, 0.0))), e2 = cross(bn, e1); res = vec3(atan(dot(rr, e2), dot(rr, e1)) / 6.2832, hh * length(ba) / 0.0045, 1.0); } }
  return res; }
float knitLegs(vec2 c) { float h = 0.0;
  for (int k = -1; k <= 1; k++) { float y = c.y - float(k) - 0.5;
    for (int s = 0; s < 2; s++) { float sx = s == 0 ? -1.0 : 1.0; vec2 d = vec2(c.x - sx * 0.235, y); float an = sx * 0.52, ca = cos(an), sa = sin(an);
      vec2 r = vec2(ca * d.x - sa * d.y, sa * d.x + ca * d.y); float e = length(r / vec2(0.2, 0.56)); h = max(h, sqrt(max(0.0, 1.0 - e * e)) * (0.9 + 0.1 * cos(r.y * 11.0))); } }
  return h; }
`;
const FS_SKIN = COMMON + KNIT + `
in vec3 vP; in vec3 vN; in vec3 vA; in vec3 vB0; in vec3 vB1; in float vZ; in vec3 vQ; flat in int vM; out vec4 o;
void main() {
  vec3 V = normalize(cameraPosition - vP), n = snrm(vN, V); int mat = vM == 21 ? 1 : vM == 22 ? 2 : 0; if (mat != 0 && dot(n, V) < 0.0) n = -n;
  float bk[6] = float[6](vB0.x, vB0.y, vB0.z, vB1.x, vB1.y, vB1.z); vec3 alb = vA;
  bool furred = mat == 0 && vM != 2 && vM != 8 && dot(alb, vec3(0.33)) > 0.06;
  if (furred) { alb = pow(alb, vec3(0.55)) * 0.9; for (int i = 0; i < 6; i++) bk[i] = max(bk[i], 0.5); if (dot(n, V) < 0.0) n = -n; }
  if (vM == 2) { alb = vec3(0.93, 0.89, 0.84); for (int i = 0; i < 6; i++) bk[i] = max(bk[i], 0.62); }   // белая мордочка, как в Blender
  float wrap = mat == 0 ? 0.35 : mat == 2 ? 0.2 : 0.25;
  float knit = 1.0; if (mat == 2) { vec3 kv = knitUV(vQ);
    float fw = max(min(fwidth(kv.x), fwidth(fract(kv.x + 0.5))), min(fwidth(kv.y), fwidth(fract(kv.y + 0.5)))); float aa = 1.0 - smoothstep(0.3, 0.75, fw);
    float h = kv.z > 0.5 ? 0.5 + 0.5 * sin(6.2832 * (kv.y + kv.x * 2.0)) : knitLegs(vec2(fract(kv.x) - 0.5, fract(kv.y))); h = mix(kv.z > 0.5 ? 0.5 : 0.45, h, aa);
    vec3 dpx = dFdx(vP), dpy = dFdy(vP); float hx = dFdx(h), hy = dFdy(h); vec3 r1 = cross(dpy, n), r2 = cross(n, dpx); float det = dot(dpx, r1);
    vec3 g = sign(det) * (hx * r1 + hy * r2) * (0.0022 * uScale); n = snrm(abs(det) * n - g, n); knit = h; alb *= mix(0.42, 1.15, h); }
  vec3 dif = vec3(0.0), spec = vec3(0.0);
  for (int i = 0; i < 3; i++) { vec3 L, E; lightAt(i, vP, L, E); float nl = (dot(n, L) + wrap) / (1.0 + wrap); if (nl <= 0.0) continue; dif += E * (nl * bk[i]);
    vec3 h = snrm(L + V, n); float nh = max(0.0, dot(n, h)); float ex = mat == 1 ? 60.0 : mat == 2 ? 6.0 : 14.0; float ks = mat == 1 ? 0.35 : mat == 2 ? 0.02 : 0.05; spec += E * (pow(nh, ex) * ks * (ex + 2.0) / 25.0 * bk[i] * nl); }
  float nu = dot(n, uUp); dif += uSky * (PI * bk[4] * (0.6 + 0.4 * nu)) + uGnd * (PI * bk[5] * (0.5 - 0.4 * nu));
  vec3 c = alb * dif / PI + spec;
  if (mat == 2) { float nv = abs(dot(n, V)); c += 0.35 * (0.25 + 0.75 * pow(1.0 - nv, 1.6)) * knit * mix(vec3(dot(dif, vec3(0.33))), dif, 0.5) / PI; }
  float sheenK = mat == 2 ? 0.0 : (vM == 2 ? 0.5 : 0.15); float sh = pow(max(0.0, 1.0 - abs(dot(n, V))), 3.0) * sheenK;
  c += alb * (sh * (bk[4] * 0.6 + bk[2] * 0.25));
  if (vM == 8) c += vec3(0.9, 0.25, 0.2) * (0.06 * bk[1] + 0.03);
  o = outC(c, length(vP - cameraPosition));
}`;
const VS_EYE = COMMON + `
in vec3 position; uniform vec3 uE; uniform float uR; out vec3 vP; out vec3 vU;
void main() { vU = position; vec3 P = uE + position * uR; vP = P; gl_Position = projectionMatrix * viewMatrix * vec4(P, 1.0); }`;
const FS_EYE = COMMON + `
in vec3 vP; in vec3 vU; uniform vec3 uE; uniform float uR; uniform vec3 uF; uniform vec3 uLidN; uniform vec3 uEyeL; uniform vec3 uEyeLC; uniform int uSide; out vec4 o;
vec3 envRefl(vec3 d) { float u = dot(d, uUp); return mix(uGnd * 2.2, uSky * 2.6, smoothstep(-0.25, 0.45, u)); }
void main() {
  vec3 n = normalize(vP - uE), f = uF; float c = dot(n, f); vec3 ax1 = normalize(cross(f, uUp) + vec3(1e-5, 0.0, 0.0)), ax2 = cross(ax1, f); float ang = atan(dot(n, ax2), dot(n, ax1)); float rr = acos(clamp(c, -1.0, 1.0));
  float iris = smoothstep(0.70, 0.715, c), pup = smoothstep(0.915, 0.922, c), ring = smoothstep(0.70, 0.79, c);
  float nz = fbm(vec3(cos(ang) * 4.0, sin(ang) * 4.0, rr * 6.0 + float(uSide) * 7.0), 5); float fib = 0.5 + 0.5 * sin(ang * 37.0 + nz * 9.0); float k = clamp(nz * 1.1 + fib * 0.25 - 0.15, 0.0, 1.0);
  vec3 ic = k < 0.55 ? mix(vec3(0.06, 0.2, 0.05), vec3(0.16, 0.42, 0.08), smoothstep(0.3, 0.55, k)) : mix(vec3(0.16, 0.42, 0.08), vec3(0.35, 0.62, 0.12), smoothstep(0.55, 0.75, k));
  ic = mix(ic * vec3(0.2, 0.25, 0.16), ic, ring); ic *= 0.85 + 0.5 * smoothstep(0.75, 0.95, c) * (0.6 + 0.4 * smoothstep(0.2, -0.6, dot(n, uUp) - 0.3));
  vec3 alb = mix(mix(vec3(0.9, 0.88, 0.86), ic, iris), vec3(0.004, 0.003, 0.003), pup);
  float under = smoothstep(0.8, 0.35, dot(n, uLidN)); float cl[6] = float[6](under, 0.6 * under + 0.1, under, under, 0.25 + 0.6 * under, 0.6);
  vec3 col = vec3(0.0); for (int i = 0; i < 3; i++) { vec3 L, E; lightAt(i, vP, L, E); col += E * (cl[i] * max(0.0, dot(n, L) * 0.8 + 0.2)); }
  col += uSky * (PI * cl[4] * 0.8) + uGnd * (PI * cl[5] * 0.5);
  vec3 outc = alb * col / PI;
  vec3 d = normalize(vP - cameraPosition); vec3 cc = uE + f * (0.208 * uR); vec3 oc = cameraPosition - cc; float b = dot(oc, d), q = dot(oc, oc) - 0.76 * uR * uR, D = b*b - q; vec3 cn = n;
  if (D > 0.0) { float tt = -b - sqrt(D); cn = normalize(cameraPosition + d * tt - cc); }
  float cv = max(0.0, dot(cn, -d)); float F = 0.04 + 0.96 * pow(max(0.0, 1.0 - cv), 5.0); vec3 R = reflect(d, cn); float occl = cl[4] * 0.85 + 0.15;
  vec3 refl = envRefl(R) * (F * occl * 0.9);
  for (int i = 1; i < 3; i++) { vec3 L, E; lightAt(i, vP, L, E); float a = dot(R, L); float sz = i == 2 ? 0.93 : 0.97; refl += E * (smoothstep(sz, sz + 0.02, a) * 0.6 * cl[i]); }
  { vec3 L = normalize(uEyeL - vP); refl += uEyeLC * smoothstep(0.988, 0.993, dot(R, L)) * 3.5; }
  refl += uSunCol * (smoothstep(0.9985, 0.9995, dot(R, uSunDir)) * 1.5 * cl[0]);
  o = outC(outc + refl, length(vP - cameraPosition));
}`;
const FS_LID = COMMON + `
in vec3 vP; in vec3 vU; uniform vec3 uE; uniform float uR; uniform vec3 uLidN; uniform vec3 uHeadF; uniform float uOffL, uRE; uniform vec3 uLidCol; uniform int uSide; out vec4 o;
void main() {
  vec3 q = vP - uE; vec3 n = normalize(q); if (dot(q, uHeadF) < -0.35 * uRE || dot(q, uLidN) <= uOffL) discard;
  float edge = (dot(q, uLidN) - uOffL) / uScale; vec3 rn = normalize(vU); vec3 rq = rn * (uR / uScale);
  float lon = atan(dot(rn, cross(uLidN, uHeadF)), dot(rn, uHeadF)) * 60.0 + fbm(rq * 300.0, 2) * 4.0; float streak = 0.5 + 0.5 * sin(lon * 3.1) * sin(lon * 1.7 + 1.3); float fz = fbm(vec3(lon * 0.6, dot(rq, uUp) * 900.0, float(uSide) * 5.0), 3);
  vec3 alb = uLidCol * (0.55 + 0.22 * streak + 0.15 * (fz - 0.5)); float lin = smoothstep(0.0042, 0.0012, edge + (fz - 0.5) * 0.0012); alb = mix(alb, vec3(0.07, 0.035, 0.02), lin);
  float top = smoothstep(-0.2, 0.75, dot(rn, uLidN));
  vec3 V = normalize(cameraPosition - vP); vec3 col = vec3(0.0); for (int i = 0; i < 3; i++) { vec3 L, E; lightAt(i, vP, L, E); col += E * (0.55 * max(0.0, (dot(n, L) + 0.5) / 1.5)); }
  col += uSky * (PI * 0.55) + uGnd * (PI * 0.35); col *= 0.62 + 0.38 * (1.0 - top * 0.6);
  float sh = pow(max(0.0, 1.0 - abs(dot(n, V))), 2.0) * 0.4; vec3 c = alb * col / PI + alb * uSky * (sh * (1.0 - lin) * PI);
  o = outC(c, length(vP - cameraPosition));
}`;
const VS_LIDFUR = COMMON + `
in vec3 position; in vec4 aL0; in vec4 aL1; uniform vec3 uLE[2]; uniform vec3 uLA[2]; uniform vec3 uLB1[2]; uniform vec3 uLB2[2]; uniform vec2 uLid; uniform float uLOFF, uRE0, uLR, uTh0; uniform vec3 uLidCol;
out vec3 vP; out vec3 vT; out float vt; out vec3 vB0; out vec3 vB1; out vec3 vAlb; flat out int vKind;
vec3 pt(float tt, vec3 root, vec3 dir, vec3 m, float L, float lift) { return root + normalize(m * cos(lift * (1.0 - tt)) + dir * sin(lift * (1.0 - tt))) * (L * tt) - dir * (0.0009 * tt * tt); }
void main() {
  int k = gl_VertexID >> 1; float side = (gl_VertexID & 1) == 0 ? -1.0 : 1.0; int e = int(aL0.x + 0.5); vec3 a = uLA[e], E = uLE[e]; float lid = e == 0 ? uLid.x : uLid.y;
  float off = -0.72 * uRE0 + (uLOFF + 0.72 * uRE0) * lid; float thm = acos(clamp(off / uLR, -1.0, 1.0)), th = thm - aL0.z; vec3 rad = uLB1[e] * cos(aL0.y) + uLB2[e] * sin(aL0.y);
  float hid = th < uTh0 - 0.01 ? 0.0 : 1.0; vec3 dir = a * cos(th) + rad * sin(th), m = -a * sin(th) + rad * cos(th); vec3 root = E + dir * (uLR - 0.0004);
  float t = float(k) / 4.0; vec3 p = toW(poseP(pt(t, root, dir, m, aL0.w, aL1.x), 1.0, -1.0, 0.0, 0.0, vec4(0.0)));
  vec3 pa = toW(poseP(pt(max(t - 0.25, 0.0), root, dir, m, aL0.w, aL1.x), 1.0, -1.0, 0.0, 0.0, vec4(0.0))), pb = toW(poseP(pt(min(t + 0.25, 1.0), root, dir, m, aL0.w, aL1.x), 1.0, -1.0, 0.0, 0.0, vec4(0.0)));
  vec3 T = normalize(pb - pa + 1e-7); float rad0 = 0.00095 * uScale * (1.0 - 0.8 * pow(t, 1.3)); float w = hid * max(rad0, uPix * length(p - cameraPosition) * 0.55);
  vec3 P = p + normalize(cross(T, p - cameraPosition) + 1e-7) * w * side; gl_Position = projectionMatrix * viewMatrix * vec4(P, 1.0);
  float top = smoothstep(-0.2, 0.75, dot(dir, a)); vB0 = vec3(0.62, 0.42, 0.62) * (1.0 - 0.35 * top); vB1 = vec3(0.62, 0.6, 0.42);
  vec3 c = uLidCol * aL1.y; if (aL0.z < 0.07) c = mix(vec3(0.08, 0.04, 0.02), c, smoothstep(0.03, 0.07, aL0.z));
  vAlb = c * mix(vec3(1.0), vec3(0.62, 0.55, 0.5), (1.0 - t) * (1.0 - t)); vP = P; vT = T; vt = t; vKind = 0;
}`;
const VS_MOUTH = COMMON + `
in vec3 position; in vec2 aUV; out vec3 vP; out vec2 vUV;
void main() { vUV = aUV; vec3 P = toW(poseP(position, 1.0, -1.0, 0.0, 0.0, vec4(0.0, 0.0, aUV.y, 0.0))); vP = P; gl_Position = projectionMatrix * viewMatrix * vec4(P, 1.0); }`;
const FS_MOUTH = COMMON + `
in vec3 vP; in vec2 vUV; uniform float uOpen; out vec4 o;
void main() {
  float x = vUV.x, v = vUV.y; float W = 0.62 + 0.38 * uOpen; if (uOpen < 0.03 || abs(x) > W) discard;
  float edge = 1.0 - smoothstep(W - 0.12, W, abs(x));
  vec3 c = mix(vec3(0.16, 0.035, 0.035), vec3(0.06, 0.01, 0.012), smoothstep(0.0, 0.5, v) * (1.0 - abs(x)));
  float tongue = smoothstep(0.5, 0.75, v) * smoothstep(0.55, 0.3, abs(x)); c = mix(c, vec3(0.8, 0.33, 0.37), tongue * 0.95);
  float fh = 0.22 * smoothstep(0.3, 0.8, uOpen); float fx = abs(abs(x) - 0.36); float fang = (1.0 - smoothstep(0.02, 0.045, fx + 0.06 * v / max(fh, 0.01))) * step(v, fh) * step(0.3, uOpen); c = mix(c, vec3(0.93, 0.91, 0.87), fang);
  c = mix(c, vec3(0.3, 0.09, 0.08), (1.0 - edge) * 0.5);
  vec3 L, E; lightAt(2, vP, L, E); c *= (uSky * PI * 0.55 + E * 0.5 + uSunCol * 0.15) / PI;
  o = outC(c, length(vP - cameraPosition));
}`;

// ---------- three.js: общие геометрии и текстуры ----------
let THREE = null, S = null;
function stripIndex(nSeg) { const I = []; for (let k = 0; k < nSeg; k++) { const a = 2 * k; I.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } return I; }
function shared() {
  if (S) return S; const D = MKB.D; S = {};
  const tex = (data, w, h, type) => { const t = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, type); t.minFilter = t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true; return t; };
  S.tPos = tex(D.pos, D.TW, D.rows[0], THREE.FloatType); S.tBake = tex(D.bake, D.TW, D.rows[1], THREE.UnsignedByteType); S.tAttr = tex(D.attr, D.TW, D.rows[2], THREE.UnsignedByteType);
  const fg = new THREE.InstancedBufferGeometry(); fg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(30), 3)); fg.setIndex(stripIndex(4)); fg.instanceCount = D.NS; S.furGeo = fg;
  const sk = D.skin, g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(sk.P, 3)); g.setAttribute('aN', new THREE.BufferAttribute(sk.N, 3)); g.setAttribute('aA', new THREE.BufferAttribute(sk.A, 3));
  g.setAttribute('aB0', new THREE.BufferAttribute(sk.B0, 3)); g.setAttribute('aB1', new THREE.BufferAttribute(sk.B1, 3)); g.setAttribute('aW', new THREE.BufferAttribute(sk.W, 4)); g.setAttribute('aX', new THREE.BufferAttribute(sk.X, 4)); g.setAttribute('aM', new THREE.BufferAttribute(sk.M, 1));
  g.setIndex(new THREE.BufferAttribute(sk.idx, 1)); S.skinGeo = g;
  S.eyeGeo = new THREE.SphereGeometry(1, 64, 40);
  const lg = new THREE.InstancedBufferGeometry(); lg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(30), 3)); lg.setIndex(stripIndex(4));
  const LF = D.lidFur, ib = new THREE.InstancedInterleavedBuffer(LF, 8, 1); lg.setAttribute('aL0', new THREE.InterleavedBufferAttribute(ib, 4, 0)); lg.setAttribute('aL1', new THREE.InterleavedBufferAttribute(ib, 4, 4)); lg.instanceCount = LF.length / 8; S.lidGeo = lg;
  const mg = new THREE.BufferGeometry(); mg.setAttribute('position', new THREE.BufferAttribute(D.mouth.P, 3)); mg.setAttribute('aUV', new THREE.BufferAttribute(D.mouth.UV, 2)); mg.setIndex(new THREE.BufferAttribute(D.mouth.I, 1)); S.mouthGeo = mg;
  S.hideMat = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false });
  return S;
}
const M3 = () => new THREE.Matrix3();
function uniformsNew() {
  const v3 = (x, y, z) => ({ value: new THREE.Vector3(x || 0, y || 0, z || 0) });
  return { uHead: { value: M3() }, uEar0: { value: M3() }, uEar1: { value: M3() }, uLeg0: { value: M3() }, uLeg1: { value: M3() }, uArm0: { value: M3() }, uArm1: { value: M3() }, uArmQ0: { value: new THREE.Vector4(1, 0, 0, 0) }, uArmQ1: { value: new THREE.Vector4(1, 0, 0, 0) }, uFore0: { value: M3() }, uFore1: { value: M3() }, uJawM: { value: M3() },
    uLift: { value: new THREE.Vector2() }, uTailA: { value: 0.25 }, uTailPh: { value: 0 }, uBreath: { value: 0 }, uScale: { value: 1 }, uPix: { value: 0.001 }, uExpo: { value: 1 }, uDesat: MKB.desatU, uTint: MKB.tintU, uTrim: MKB.trimU, uSoft: MKB.softU, uGloss: MKB.glossU,
    uSunDir: v3(0, 1, 0), uSunCol: v3(2, 2, 2), uRimDir: v3(0, 0.5, -1), uRimCol: v3(0, 0, 0), uFillDir: v3(0, 0.3, 1), uFillCol: v3(0.2, 0.2, 0.2), uSky: v3(0.4, 0.45, 0.5), uGnd: v3(0.15, 0.15, 0.12), uUp: v3(0, 1, 0), uFogCol: v3(1, 1, 1), uFog: { value: new THREE.Vector2(0, 0) },
    uPos: { value: null }, uBake: { value: null }, uAttr: { value: null } };
}
function mat(U, vs, fs, extra, opts) { const u = Object.assign({}, U, extra || {}); return new THREE.RawShaderMaterial(Object.assign({ uniforms: u, vertexShader: vs, fragmentShader: fs, glslVersion: THREE.GLSL3, side: THREE.DoubleSide }, opts || {})); }

/** Подменить обычного Барсика: rig — скелет из multik-3d.js (его поза, руки для предметов и тень остаются). */
MKB.attach = function (T, rig) {
  if (!MKB.ready) return false; THREE = T; const s = shared(), D = MKB.D;
  if (!MKB.tintU.value) MKB.tintU.value = new THREE.Vector3(0.95, 1.0, 1.0);   // рыжий ближе к золотистому (Blender)
  const U = uniformsNew(); U.uPos.value = s.tPos; U.uBake.value = s.tBake; U.uAttr.value = s.tAttr;
  const bg = new THREE.Group(); bg.name = 'barsik-neon'; bg.userData.noGround = true; bg.rotation.x = -Math.PI / 2; const k = rig.P.headY / HEAD_C; bg.scale.setScalar(k); rig.pose.add(bg);
  const add = (geo, m, order) => { const o = new THREE.Mesh(geo, m); o.frustumCulled = false; o.castShadow = false; o.receiveShadow = false; o.userData.barsik = true; if (order != null) o.renderOrder = order; bg.add(o); return o; };
  const skin = add(s.skinGeo, mat(U, VS_SKIN, FS_SKIN));
  const fur = add(s.furGeo, mat(U, VS_FUR, FS_FUR));
  const mouth = add(s.mouthGeo, mat(U, VS_MOUTH, FS_MOUTH, { uOpen: { value: 0 } }, { polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 }));
  const eyes = [], lids = [];
  for (let i = 0; i < 2; i++) {
    const eu = { uE: { value: new THREE.Vector3() }, uR: { value: D.RE }, uF: { value: new THREE.Vector3(0, 0, 1) }, uLidN: { value: new THREE.Vector3(0, 1, 0) }, uEyeL: { value: new THREE.Vector3() }, uEyeLC: { value: new THREE.Vector3() }, uSide: { value: i } };
    const em = add(s.eyeGeo, mat(U, VS_EYE, FS_EYE, eu)); eyes.push(em);
    const lu = { uE: eu.uE, uR: { value: D.RE + 0.0045 }, uLidN: eu.uLidN, uHeadF: { value: new THREE.Vector3(0, 0, 1) }, uOffL: { value: 0 }, uRE: { value: D.RE }, uLidCol: { value: new THREE.Vector3(...D.LIDCOL) }, uSide: { value: i } };
    const lm = add(s.eyeGeo, mat(U, VS_EYE, FS_LID, lu)); lids.push(lm);
  }
  const lidFur = add(s.lidGeo, mat(U, VS_LIDFUR, FS_FUR, { uLE: { value: D.E0.map(e => new THREE.Vector3(...e)) }, uLA: { value: D.LIDN0.map(e => new THREE.Vector3(...e)) }, uLB1: { value: D.LB1.map(e => new THREE.Vector3(...e)) }, uLB2: { value: D.LB2.map(e => new THREE.Vector3(...e)) },
    uLid: { value: new THREE.Vector2(1, 1) }, uLOFF: { value: D.LIDOFF }, uRE0: { value: D.RE }, uLR: { value: D.lidR }, uTh0: { value: D.th0 }, uLidCol: { value: new THREE.Vector3(...D.LIDCOL) } }));
  const shells = []; if (MKB.shellK > 0) for (let i = 0; i < 6; i++) { const t = (i + 1) / 6; const sm = add(s.skinGeo, mat(U, VS_SHELL, FS_SHELL, { uT: { value: t }, uShellH: { value: 0.016 * t }, uShellK: MKB.shellU },
      { transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor }), 10 + i); shells.push(sm); }   // БАРС · налёт
  // старый Барсик: только тень и «кости» (поза, руки для предметов), сам не рисуется
  rig.root.traverse(o => { if (!o.isMesh || o.userData.barsik || o.userData.blob) return; if (o.userData.strands) { o.visible = false; return; } o.layers.set(1); });   // слой 1 видит только камера теней
  rig.fur = []; rig.bars = { U, bg, k, skin, fur, mouth, eyes, lids, lidFur, shells, lid: 1, open: 0 };
  rig.headH = HEAD_C * k * (rig.scale || 1); rig.headR = HEAD_R * k * (rig.scale || 1);
  const pre = function (R, scene, cam) { const f = R.info.render.frame; if (rig.bars._f === f && rig.bars._cam === cam) return; rig.bars._f = f; rig.bars._cam = cam; eyeFrame(rig, R, cam); };
  bg.children.forEach(o => { o.onBeforeRender = pre; });
  return true;
};

// ---------- поза: из скелета «Мультиков» в кости модели ----------
const AX = () => new THREE.Matrix4().makeRotationX(-Math.PI / 2);   // модель (z вверх) → three (y вверх)
let _ax = null, _axi = null, _m4 = null, _m4b = null, _e = null, _q = null;
function conj(R4, out) { /* поворот в осях three → в осях модели */ _m4b.copy(_axi).multiply(R4).multiply(_ax); out.setFromMatrix4(_m4b); return out; }
const _qt = { x: 0, y: 0, z: 0, w: 1 };
function armQ(R4, out) { /* поворот плеча → ось и угол (для доли поворота у кожи плеча) */ const q = (_qt.q || (_qt.q = new THREE.Quaternion())).setFromRotationMatrix(R4); const w = Math.min(1, Math.max(-1, q.w)); let a = 2 * Math.acos(w); const sn = Math.sqrt(Math.max(0, 1 - w * w)); if (sn < 1e-5 || !isFinite(a)) { out.set(1, 0, 0, 0); return; } if (a > Math.PI) a -= 2 * Math.PI; out.set(q.x / sn, q.y / sn, q.z / sn, a); }
function eulerM(x, y, z, out) { _e.set(x, y, z, 'XYZ'); return out.makeRotationFromEuler(_e); }
const REST_X = -0.39, REST_Z = 0.345;   // лапы модели в покое — в углах скелета (x — вперёд/назад, z — в сторону)
MKB.frame = function (rig, st, T, L) {
  const B = rig.bars; if (!B) return; const U = B.U;
  if (!_ax) { _ax = AX(); _axi = _ax.clone().invert(); _m4 = new THREE.Matrix4(); _m4b = new THREE.Matrix4(); _e = new THREE.Euler(); _q = new THREE.Matrix4(); }
  // голова
  conj(_m4.makeRotationFromEuler(rig.head.rotation), U.uHead.value);
  // руки: от покоя модели к углам скелета
  rig.arms.forEach((g, i) => { const s = g.userData.side || (i ? 1 : -1), j = s < 0 ? 0 : 1; const ax = g.rotation.x; let az = g.rotation.z * s;
    az = REST_Z + (az - REST_Z) * 0.85; /* в сторону — чуть мягче: плечо модели не растягивается */
    eulerM(ax, 0, s * az, _m4); const tw = (g.userData.tw || 0) * (MKB.K.twist || 0); if (tw) _m4.multiply((MKB._tw || (MKB._tw = new THREE.Matrix4())).makeRotationY(tw)); /* «привет»: кисть подушечками вперёд */ eulerM(REST_X, 0, s * REST_Z, _q); _m4.multiply(_q.invert()); conj(_m4, j ? U.uArm1.value : U.uArm0.value); armQ(_m4b, (j ? U.uArmQ1 : U.uArmQ0).value);
    const up = Math.max(0, az - 1.2); (j ? U.uFore1 : U.uFore0).value.setFromMatrix4(eulerM(0, 0, 0, _q)); if (up > 0) { conj(eulerM(-Math.min(1.1, up * 0.8), 0, 0, _q), (j ? U.uFore1 : U.uFore0).value); } });
  rig.legs.forEach((g, i) => { const j = g.position.x < 0 ? 0 : 1; conj(eulerM(g.rotation.x, 0, 0, _m4), j ? U.uLeg1.value : U.uLeg0.value); });
  if (rig.ears) rig.ears.forEach((e, i) => { const r0 = e.userData.r0; if (!r0) return; const j = (e.getWorldPosition ? (e.position.x < 0 ? 0 : 1) : i);
    eulerM(e.rotation.x - r0.x, e.rotation.y - r0.y, e.rotation.z - r0.z, _m4); conj(_m4, j ? U.uEar1.value : U.uEar0.value); });
  U.uBreath.value = rig.body ? (rig.body.scale.y - 1) * 1.2 : 0;
  const tr = rig.tail ? rig.tail.rotation.y : 0; U.uTailA.value = 0.22 + Math.min(0.35, Math.abs(tr) * 0.8); U.uTailPh.value = T * 2.4;
  // рот: как у обычного героя (реплика, смех, крик)
  let open = 0; if (rig.mouthPatch && rig.mouthPatch.material.userData.U) open = rig.mouthPatch.material.userData.U.uOpen.value; else if (rig.open) open = rig.open.visible ? Math.min(1, (rig.open.scale.y - 0.25) / 1.1) : 0;
  open = Math.max(0, Math.min(1, open)); B.open = open; B.mouth.material.uniforms.uOpen.value = open; conj(eulerM(0.3 * open, 0, 0, _m4), U.uJawM.value);
  // веки: моргание и настроение — из глаз скелета
  const e0 = rig.eyes && rig.eyes[0]; let lid = 1; if (e0 && e0.g) { const sx = e0.g.scale.x || 1, sy = e0.g.scale.y; const cl = Math.min(1, Math.max(0, (1 - sy / sx) / 0.92)); lid = 1 - cl; }
  const emo = st.emo || 'neutral'; if (emo === 'sleepy') lid *= 0.45; else if (emo === 'angry' || emo === 'sad' || emo === 'cry') lid *= 0.78;
  B.lid = lid; B.lidFur.material.uniforms.uLid.value.set(lid, lid); B.lidFur.visible = lid < 0.999; B.lids.forEach(l => l.visible = lid < 0.999);
  B.gx = (Math.abs(st.face || 0) > 0.1 ? 0.25 : 0); B.T = T;
  // свет места
  if (L) { const sun = L.sun, hemi = L.hemi, rim = L.rim; if (sun && sun.shadow && !sun.shadow.camera.layers.isEnabled(1)) sun.shadow.camera.layers.enable(1);
    if (sun) { U.uSunDir.value.copy(sun.position).sub(sun.target.position).normalize(); U.uSunCol.value.set(sun.color.r, sun.color.g, sun.color.b).multiplyScalar(sun.intensity); }
    if (rim && rim.visible !== false) { U.uRimDir.value.copy(rim.position).sub(rim.target.position).normalize(); U.uRimCol.value.set(rim.color.r, rim.color.g, rim.color.b).multiplyScalar(rim.intensity * 1.1); } else U.uRimCol.value.set(0, 0, 0);
    if (hemi) { const env = (L.envI || 0) * 0.8; U.uSky.value.set(hemi.color.r * hemi.intensity + env, hemi.color.g * hemi.intensity + env, hemi.color.b * hemi.intensity + env).multiplyScalar(1 / Math.PI);
      U.uGnd.value.set(hemi.groundColor.r, hemi.groundColor.g, hemi.groundColor.b).multiplyScalar(hemi.intensity / Math.PI); U.uFillCol.value.copy(U.uSky.value).multiplyScalar(0.55 * Math.PI); const lb = Math.max(.25, Math.min(1.6, (hemi.color.r + hemi.color.g + hemi.color.b) / 3 * hemi.intensity + env)); U.uFillCol.value.add(new THREE.Vector3(1.0, 0.96, 0.9).multiplyScalar(MKB.K.key * lb)); }   // БАРС: студийный свет на героя
    const f = L.fog; if (f && f.isFog) { U.uFogCol.value.set(f.color.r, f.color.g, f.color.b); U.uFog.value.set(f.near, f.far); } else U.uFog.value.set(0, 0);
    U.uExpo.value = (L.expo != null ? L.expo : 1) * MKB.K.expo; }
};
const _v = [], _mw = { m: null };
function eyeFrame(rig, R, cam) {   // перед глазами: мир уже посчитан — центры глаз, взгляд, веки
  const B = rig.bars, U = B.U, D = MKB.D; if (!_v.length) for (let i = 0; i < 8; i++) _v.push(new THREE.Vector3());
  const MW = B.bg.matrixWorld, sc = new THREE.Vector3().setFromMatrixColumn(MW, 0).length(); U.uScale.value = sc;
  const h = R.getRenderTarget() ? R.getRenderTarget().height : R.getContext().drawingBufferHeight; U.uPix.value = 2 * Math.tan((cam.fov || 38) * Math.PI / 360) / Math.max(1, h);
  // мягкий свет спереди — со стороны камеры
  const hc = _v[0].set(0, -0.01, HEAD_C).applyMatrix4(MW); U.uFillDir.value.copy(cam.position).sub(hc).normalize().add(_v[1].set(0, 0.35, 0)).normalize();
  const Hm = U.uHead.value.elements; const head = (p) => { const q = [p[0] - PH[0], p[1] - PH[1], p[2] - PH[2]]; return [Hm[0] * q[0] + Hm[3] * q[1] + Hm[6] * q[2] + PH[0], Hm[1] * q[0] + Hm[4] * q[1] + Hm[7] * q[2] + PH[1], Hm[2] * q[0] + Hm[5] * q[1] + Hm[8] * q[2] + PH[2]]; };
  const headN = (n) => [Hm[0] * n[0] + Hm[3] * n[1] + Hm[6] * n[2], Hm[1] * n[0] + Hm[4] * n[1] + Hm[7] * n[2], Hm[2] * n[0] + Hm[5] * n[1] + Hm[8] * n[2]];
  const N3 = new THREE.Matrix3().setFromMatrix4(MW);
  const HF = _v[2].set(...headN([0, -1, 0])).applyMatrix3(N3).normalize();
  // взгляд: вперёд по голове, к зрителю, с мелкими «перебежками» как у остальных героев
  const T = B.T || 0, sd = ((rig.n && rig.n.seed) || 0) % 13 / 13, sacc = Math.floor(T / (1.7 + sd) + sd * 9);
  const hs = (s) => { let h2 = 2166136261; for (let i = 0; i < s.length; i++) { h2 ^= s.charCodeAt(i); h2 = Math.imul(h2, 16777619); } return (h2 >>> 0) % 100 / 100; };
  const sx = (hs('s' + sacc) - 0.5) * 0.3, sy = (hs('y' + sacc) - 0.5) * 0.16;
  const toCam = _v[3].copy(cam.position).sub(hc).normalize(); const gz = _v[4].copy(HF).lerp(toCam, 0.75).normalize();   // смотрит в камеру, как в Blender
  const rt = _v[5].crossVectors(gz, _v[6].set(0, 1, 0)).normalize(), upv = _v[6].crossVectors(rt, gz).normalize(); gz.addScaledVector(rt, sx).addScaledVector(upv, sy).normalize();
  const c = gz.dot(HF), lim = 0.5; if (c < Math.cos(lim)) { const pp = _v[7].copy(gz).addScaledVector(HF, -c).normalize(); gz.copy(HF).multiplyScalar(Math.cos(lim)).addScaledVector(pp, Math.sin(lim)); }
  const offL = (-0.72 * D.RE + (D.LIDOFF + 0.72 * D.RE) * B.lid) * sc;
  const camR = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), camU = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1), camF = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 2).negate();
  const eyeL = cam.position.clone().addScaledVector(camU, 0.35 * sc).addScaledVector(camR, -0.25 * sc).addScaledVector(camF, 0.4 * sc);
  for (let i = 0; i < 2; i++) { const E = new THREE.Vector3(...head(D.E0[i])).applyMatrix4(MW); const eu = B.eyes[i].material.uniforms, lu = B.lids[i].material.uniforms;
    eu.uE.value.copy(E); eu.uR.value = D.RE * sc; eu.uF.value.copy(gz); eu.uLidN.value.set(...headN(D.LIDN0[i])).applyMatrix3(N3).normalize(); eu.uEyeL.value.copy(eyeL);
    const de2 = eyeL.distanceToSquared(E) / (sc * sc); eu.uEyeLC.value.set(1, 0.97, 0.93).multiplyScalar(6 * 0.08 / Math.max(0.1, de2) * 0.7);
    lu.uR.value = (D.RE + 0.0045) * sc; lu.uHeadF.value.copy(HF); lu.uOffL.value = offL; lu.uRE.value = D.RE * sc; }
}
})(window);
