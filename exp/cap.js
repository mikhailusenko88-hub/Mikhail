// Снимок кадра движка «Мультиков» для Blender: геометрия всех героев и комнаты в мировых координатах.
// Подключается в странице frame.html после загрузки движка. Движок не меняет: только читает сцену
// и прогоняет те же шейдеры героев «в точки», чтобы получить позы, как их считает движок.
(function () {
  const CAP = window.CAP = { log: [] };
  const L = (...a) => { const s = a.join(' '); CAP.log.push(s); console.log('CAP', s); };
  let RT = null, RTW = 0, RTH = 0;
  function rt(THREE, w, h) { if (RT && RTW === w && RTH >= h) return RT; if (RT) RT.dispose();
    RT = new THREE.WebGLRenderTarget(w, h, { type: THREE.FloatType, format: THREE.RGBAFormat, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, depthBuffer: false, stencilBuffer: false, generateMipmaps: false });
    RTW = w; RTH = h; return RT; }
  function wvis(o) { for (let x = o; x; x = x.parent) if (!x.visible) return false; return true; }

  // прогнать шейдер объекта «в точки»: каждая вершина пишет в свой пиксель vCapA и vCapB
  function gpu(THREE, R, cam, o, A, B, opts) {
    const m = o.material, g = o.geometry, glsl3 = m.glslVersion === THREE.GLSL3;
    const inst = g.isInstancedBufferGeometry ? (g.instanceCount === Infinity ? 1 : g.instanceCount) : 1;
    const pos = g.attributes.position; const nv = pos ? pos.count : (g.drawRange.count === Infinity ? 0 : g.drawRange.count);
    const dr = g.drawRange; if (dr && dr.count === 0) return null;
    const N = nv * inst; if (!N) return null;
    const W = 2048, H = Math.ceil(N / W); if (H > 8192) { L('слишком много вершин', o.name, N); return null; }
    let vs = m.vertexShader; const im = vs.indexOf('void main');
    const io = glsl3 ? 'out' : 'varying';
    vs = vs.slice(0, im) + `\n${io} highp vec4 vCapA; ${io} highp vec4 vCapB; uniform highp vec2 uCapRes; uniform int uCapNV;\n` + vs.slice(im);
    const k = vs.lastIndexOf('}');
    vs = vs.slice(0, k) + `\n  vCapA = ${A}; vCapB = ${B || 'vec4(0.0)'};\n  { int cid = gl_InstanceID * uCapNV + gl_VertexID; float cx = float(cid % int(uCapRes.x)), cy = float(cid / int(uCapRes.x));\n    gl_Position = vec4((cx + .5) / uCapRes.x * 2. - 1., (cy + .5) / uCapRes.y * 2. - 1., 0., 1.); gl_PointSize = 1.0; }\n` + vs.slice(k);
    const fs = glsl3 ? `precision highp float; precision highp int; in highp vec4 vCapA; in highp vec4 vCapB; uniform int uCapWhich; out highp vec4 oCap; void main() { oCap = uCapWhich == 0 ? vCapA : vCapB; }`
      : `varying highp vec4 vCapA; varying highp vec4 vCapB; uniform int uCapWhich; void main() { gl_FragColor = uCapWhich == 0 ? vCapA : vCapB; }`;
    const U = m.uniforms; const T = rt(THREE, W, H); U.uCapRes = { value: new THREE.Vector2(W, T.height) }; U.uCapNV = { value: nv }; U.uCapWhich = { value: 0 };
    const save = {}; for (const [n, v] of Object.entries(opts && opts.set || {})) if (U[n]) { save[n] = U[n].value; U[n].value = v; }
    const Cls = m.isRawShaderMaterial ? THREE.RawShaderMaterial : THREE.ShaderMaterial;
    const cm = new Cls({ vertexShader: vs, fragmentShader: fs, uniforms: U, glslVersion: m.glslVersion, defines: Object.assign({}, m.defines || {}), depthTest: false, depthWrite: false, blending: THREE.NoBlending, transparent: false });
    if (m.extensions) cm.extensions = Object.assign({}, m.extensions);
    const P = new THREE.Points(g, cm); P.matrixAutoUpdate = false; P.matrix.copy(o.matrixWorld); P.matrixWorld.copy(o.matrixWorld); P.frustumCulled = false; P.userData = o.userData;
    if (o.onBeforeRender) P.onBeforeRender = function (r, s, c, gg, mm, gr) { try { o.onBeforeRender.call(o, r, s, c, gg, mm, gr); } catch (e) {} };
    const sc = new THREE.Scene(); sc.add(P); sc.matrixWorldAutoUpdate = false;
    const C = new THREE.Camera(); C.matrixWorldAutoUpdate = false; C.matrixAutoUpdate = false;   // вид и проекция — единичные: gl_Position = мировая точка
    const out = [];
    const prevRT = R.getRenderTarget(), prevAC = R.autoClear, cc = new THREE.Color(), ca = R.getClearAlpha(); R.getClearColor(cc);
    for (const which of B ? [0, 1] : [0]) {
      U.uCapWhich.value = which; R.setRenderTarget(T); R.setClearColor(0x000000, 0); R.autoClear = true; R.clear(); R.render(sc, C);
      const buf = new Float32Array(W * H * 4); R.readRenderTargetPixels(T, 0, 0, W, H, buf); out.push(buf.subarray(0, N * 4)); }
    R.setRenderTarget(prevRT); R.autoClear = prevAC; R.setClearColor(cc, ca);
    for (const n in save) U[n].value = save[n]; delete U.uCapRes; delete U.uCapNV; delete U.uCapWhich; cm.dispose();
    return { N, nv, inst, A: out[0], B: out[1] };
  }

  const lin = x => x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
  // текстура → png (dataURL) один раз на серию
  const texDone = new Map();
  function texPng(THREE, tex) {
    if (!tex || !tex.image) return null; if (texDone.has(tex.uuid)) return texDone.get(tex.uuid);
    let url = null; const im = tex.image;
    try { const c = document.createElement('canvas');
      if (im.data && im.width) { c.width = im.width; c.height = im.height; const x = c.getContext('2d'), d = x.createImageData(im.width, im.height); const s = im.data, n = im.width * im.height, ch = s.length / n;
        for (let i = 0; i < n; i++) { for (let j = 0; j < 3; j++) { let v = s[i * ch + Math.min(j, ch - 1)]; if (s instanceof Float32Array) v = Math.round(Math.min(1, v) * 255); d.data[i * 4 + j] = v; } d.data[i * 4 + 3] = ch === 4 ? (s instanceof Float32Array ? Math.round(s[i * 4 + 3] * 255) : s[i * 4 + 3]) : 255; }
        x.putImageData(d, 0, 0); }
      else { c.width = im.width || im.videoWidth; c.height = im.height || im.videoHeight; c.getContext('2d').drawImage(im, 0, 0); }
      url = c.toDataURL('image/png'); } catch (e) { L('текстура не снята', e.message); }
    const r = url ? { id: 'tex_' + texDone.size, url, repeat: tex.repeat.toArray(), offset: tex.offset.toArray(), rotation: tex.rotation, center: tex.center.toArray(), flipY: tex.flipY, srgb: tex.colorSpace === THREE.SRGBColorSpace } : null;
    texDone.set(tex.uuid, r); return r;
  }

  // главный вход: снять текущую сцену (после frame(t))
  CAP.capture = function (opts) {
    opts = opts || {}; const t0 = performance.now();
    const D = MK3D._dbg(), S = D.scene, R = D.R, cam = D.cam, THREE = D.THREE;
    S.updateMatrixWorld(true); cam.updateMatrixWorld(true);
    const objs = [], bins = []; let off = 0; const put = (arr) => { const b = arr.buffer.slice(arr.byteOffset, arr.byteOffset + arr.byteLength); bins.push(b); const o = off; off += b.byteLength; return [o, arr.length, arr.constructor.name]; };
    const camW = cam.matrixWorld; const v = new THREE.Vector3();
    const camToW = (A, N, stride) => { const out = new Float32Array(N * 3), e = camW.elements; for (let i = 0; i < N; i++) { const x = A[i * stride], y = A[i * stride + 1], z = A[i * stride + 2];
        out[i * 3] = e[0] * x + e[4] * y + e[8] * z + e[12]; out[i * 3 + 1] = e[1] * x + e[5] * y + e[9] * z + e[13]; out[i * 3 + 2] = e[2] * x + e[6] * y + e[10] * z + e[14]; } return out; };
    const stat = {}; const cnt = (k, n) => { stat[k] = (stat[k] || 0) + n; };
    const idxOf = g => { if (g.index) return Uint32Array.from(g.index.array); const n = g.attributes.position.count, a = new Uint32Array(n); for (let i = 0; i < n; i++) a[i] = i; return a; };
    const list = []; S.traverse(o => { if ((o.isMesh || o.isLineSegments || o.isLine || o.isPoints) && wvis(o) && o.material) list.push(o); });
    let ni = 0;
    for (const o of list) {
      const m = o.material, g = o.geometry, U = m.uniforms || {}, ud = o.userData || {}, at = g.attributes; const name = (o.parent && o.parent.name || '') + '/' + (o.name || o.type) + '#' + (ni++);
      const custom = !!m.vertexShader && (m.isShaderMaterial || m.isRawShaderMaterial);
      try {
        if (custom) {
          if (U.uPts && U.uCol && U.uK) {   // шерсть героев БАРС (Пик, Рон…): ленты по 6 вершин на отрезок, uK точек на волосок
            const K = U.uK.value; const r = gpu(THREE, R, cam, o, 'vec4(p, max(rad, 1e-6))', 'vec4(vCol, float(kk))', { set: { uCull: 0, uDecC: 1 } }); if (!r) continue;
            const segs = r.N / 6, ns = Math.floor(segs / (K - 1)); const P = new Float32Array(ns * K * 3), Rr = new Float32Array(ns * K), Cc = new Float32Array(ns * 3); let n = 0;
            for (let s = 0; s < ns; s++) { const v0 = (s * (K - 1)) * 6; if (!(r.A[v0 * 4 + 3] > 0)) continue; let ok = true;
              for (let kk = 0; kk < K; kk++) { const vid = kk < K - 1 ? (s * (K - 1) + kk) * 6 : (s * (K - 1) + K - 2) * 6 + 2; const a = vid * 4; if (!(r.A[a + 3] > 0)) { ok = false; break; }
                P[(n * K + kk) * 3] = r.A[a]; P[(n * K + kk) * 3 + 1] = r.A[a + 1]; P[(n * K + kk) * 3 + 2] = r.A[a + 2]; Rr[n * K + kk] = r.A[a + 3]; }
              if (!ok) continue; const c = ((s * (K - 1) + K - 2) * 6 + 2) * 4; Cc[n * 3] = r.B[c]; Cc[n * 3 + 1] = r.B[c + 1]; Cc[n * 3 + 2] = r.B[c + 2]; n++; }
            objs.push({ k: 'curves', name, kind: 'bars', K, n, pos: put(P.subarray(0, n * K * 3)), rad: put(Rr.subarray(0, n * K)), col: put(Cc.subarray(0, n * 3)) }); cnt('волосков БАРС', n); continue; }
          if (g.isInstancedBufferGeometry && ud.barsik) {   // шерсть Барсика: 5 точек на волосок, по 2 вершины на точку
            const lash = /float\s+rad0\s*=/.test(o.material.vertexShader || '');   // ресницы: rad там — вектор, ширина — rad0, скрытые (hid=0) не берём
            const r = gpu(THREE, R, cam, o, lash ? 'vec4(p, hid > 0.5 ? max(rad0, 1e-6) : 0.0)' : 'vec4(p, max(rad, 1e-6))', 'vec4(vAlb, float(vKind))', { set: { uDecC: 1 } }); if (!r) continue;
            const K = 5, ns = r.inst; const P = new Float32Array(ns * K * 3), Rr = new Float32Array(ns * K), Cc = new Float32Array(ns * 3), Kd = new Float32Array(ns); let n = 0;
            for (let s = 0; s < ns; s++) { let ok = true; for (let kk = 0; kk < K; kk++) { const a = (s * r.nv + kk * 2) * 4; if (!(r.A[a + 3] > 0)) { ok = false; break; }
                P[(n * K + kk) * 3] = r.A[a]; P[(n * K + kk) * 3 + 1] = r.A[a + 1]; P[(n * K + kk) * 3 + 2] = r.A[a + 2]; Rr[n * K + kk] = r.A[a + 3]; }
              if (!ok) continue; const c = (s * r.nv) * 4; Cc[n * 3] = r.B[c]; Cc[n * 3 + 1] = r.B[c + 1]; Cc[n * 3 + 2] = r.B[c + 2]; Kd[n] = r.B[c + 3]; n++; }
            objs.push({ k: 'curves', name, kind: 'neon', K, n, pos: put(P.subarray(0, n * K * 3)), rad: put(Rr.subarray(0, n * K)), col: put(Cc.subarray(0, n * 3)), kd: put(Kd.subarray(0, n)) }); cnt('волосков Барсика', n); continue; }
          if (o.isLineSegments && U.uLen) {   // шерсть «глиняных» героев (Топа, Филя): отрезки линий, aT — место на волоске
            const r = gpu(THREE, R, cam, o, 'vec4(p, 1.0)', 'vec4(vCol, t)'); if (!r) continue;
            const N = r.N; let SEG = 0; for (let i = 0; i < N; i += 2) { if (r.B[i * 4 + 3] > 0.0001) SEG++; else if (SEG) break; } SEG = Math.max(1, SEG + (r.B[3] > 0.0001 ? 0 : 0)); SEG = SEG || 1;
            // проверка: в начале волоска t = 0; число отрезков на волосок — до следующего t = 0
            let seg = 1; for (let i = 2; i < N; i += 2) { if (r.B[i * 4 + 3] < 1e-5) { seg = i / 2; break; } } const K = seg + 1, ns = Math.floor(N / 2 / seg);
            const hasCol = U.uHasCol ? !!U.uHasCol.value : true, uc = U.uColor && U.uColor.value;
            const P = new Float32Array(ns * K * 3), Cc = new Float32Array(ns * 3); let n = 0;
            for (let s = 0; s < ns; s++) { let ok = true; for (let kk = 0; kk < K; kk++) { const vi = kk < seg ? (s * seg + kk) * 2 : (s * seg + seg - 1) * 2 + 1, a = vi * 4; if (!(r.A[a + 3] > 0)) { ok = false; break; }
                P[(n * K + kk) * 3] = r.A[a]; P[(n * K + kk) * 3 + 1] = r.A[a + 1]; P[(n * K + kk) * 3 + 2] = r.A[a + 2]; }
              if (!ok) continue; const c = (s * seg * 2) * 4; if (hasCol) { Cc[n * 3] = r.B[c]; Cc[n * 3 + 1] = r.B[c + 1]; Cc[n * 3 + 2] = r.B[c + 2]; } else if (uc) { Cc[n * 3] = uc.r; Cc[n * 3 + 1] = uc.g; Cc[n * 3 + 2] = uc.b; } n++; }
            const len = U.uLen.value;
            objs.push({ k: 'curves', name, kind: 'clay', K, n, len, map: U.uHasMap && U.uHasMap.value ? 1 : 0, pos: put(P.subarray(0, n * K * 3)), col: put(Cc.subarray(0, n * 3)) }); cnt('волосков глины', n); continue; }
          if (U.uShellH) continue;   // «налёт» Барсика — в Blender не нужен (там настоящий свет сквозь шерсть)
          // кожа, глаза, рот, усы: позиция — общим способом (камера без перспективы), цвет — из атрибутов
          const r = gpu(THREE, R, cam, o, 'vec4(gl_Position.xyz / gl_Position.w, 1.0)', null); if (!r) continue;
          const N = r.N; const P = new Float32Array(N * 3); for (let i = 0; i < N; i++) { P[i * 3] = r.A[i * 4]; P[i * 3 + 1] = r.A[i * 4 + 1]; P[i * 3 + 2] = r.A[i * 4 + 2]; } let col = null, kind = 'skin';
          if (at.color && !ud.cornea) { const c = at.color, n = c.count; col = new Float32Array(n * 3); for (let i = 0; i < n; i++) { col[i * 3] = c.getX(i); col[i * 3 + 1] = c.getY(i); col[i * 3 + 2] = c.getZ(i); } }
          else if (at.aA) { const c = at.aA, n = c.count; col = new Float32Array(n * 3); for (let i = 0; i < n; i++) { col[i * 3] = c.getX(i) ** 2; col[i * 3 + 1] = c.getY(i) ** 2; col[i * 3 + 2] = c.getZ(i) ** 2; } }
          if (ud.cornea || at.uv || at.aUV || (ud.barsik && !at.aA)) kind = 'eye';
          if (U.uAlb && U.uAlb.value && !col) { const a = U.uAlb.value; kind = kind === 'eye' ? 'eye' : 'skin'; col = new Float32Array(3); col[0] = a.x != null ? a.x : a.r; col[1] = a.y != null ? a.y : a.g; col[2] = a.z != null ? a.z : a.b; }
          let idx = g.index ? Uint32Array.from(g.index.array) : (() => { const a = new Uint32Array(N); for (let i = 0; i < N; i++) a[i] = i; return a; })();
          { const ok = i => r.A[i * 4 + 3] > 0; let bad = 0; const keep = []; for (let i = 0; i + 2 < idx.length; i += 3) { if (ok(idx[i]) && ok(idx[i + 1]) && ok(idx[i + 2])) keep.push(idx[i], idx[i + 1], idx[i + 2]); else bad++; }
            if (!keep.length) continue; if (bad) idx = Uint32Array.from(keep); }
          objs.push({ k: 'mesh', name, kind, n: N, pos: put(P), idx: put(idx), col: col ? put(col) : null, colN: col ? col.length / 3 : 0, tag: Object.keys(ud).join(',') }); cnt('вершин ' + kind, N); continue;
        }
        // обычные материалы three.js (комната, вещи, «глиняные» герои)
        if (!o.isMesh || !at.position) continue;
        const mats = Array.isArray(m) ? m : [m]; const groups = Array.isArray(m) && g.groups.length ? g.groups : [{ start: 0, count: Infinity, materialIndex: 0 }];
        const ninst = o.isInstancedMesh ? o.count : 1; const pa = at.position, N1 = pa.count, sk = o.isSkinnedMesh; const IM = new THREE.Matrix4(), WM = new THREE.Matrix4(), ic = new THREE.Color();
        const P = new Float32Array(N1 * ninst * 3); for (let k = 0; k < ninst; k++) { if (o.isInstancedMesh) { o.getMatrixAt(k, IM); WM.multiplyMatrices(o.matrixWorld, IM); } else WM.copy(o.matrixWorld);
          for (let i = 0; i < N1; i++) { if (sk) o.getVertexPosition(i, v); else v.fromBufferAttribute(pa, i); v.applyMatrix4(WM); const j = (k * N1 + i) * 3; P[j] = v.x; P[j + 1] = v.y; P[j + 2] = v.z; } }
        const N = N1 * ninst; const full = idxOf(g);
        let col = null; if (at.color || o.instanceColor) { col = new Float32Array(N * 3); for (let k = 0; k < ninst; k++) { if (o.instanceColor) o.getColorAt(k, ic); else ic.setRGB(1, 1, 1);
            for (let i = 0; i < N1; i++) { const j = (k * N1 + i) * 3; const cr = at.color ? at.color.getX(i) : 1, cg = at.color ? at.color.getY(i) : 1, cb = at.color ? at.color.getZ(i) : 1; col[j] = cr * ic.r; col[j + 1] = cg * ic.g; col[j + 2] = cb * ic.b; } } }
        let colB = null, mix = null; if (at.aColB && at.aMix) { colB = new Float32Array(N * 3); mix = new Float32Array(N); for (let k = 0; k < ninst; k++) for (let i = 0; i < N1; i++) { const j = k * N1 + i; colB[j * 3] = at.aColB.getX(i); colB[j * 3 + 1] = at.aColB.getY(i); colB[j * 3 + 2] = at.aColB.getZ(i); mix[j] = at.aMix.getX(i); } }
        let uv = null; if (at.uv) { const u = at.uv; uv = new Float32Array(N * 2); for (let k = 0; k < ninst; k++) for (let i = 0; i < N1; i++) { const j = k * N1 + i; uv[j * 2] = u.getX(i); uv[j * 2 + 1] = u.getY(i); } }
        const pP = put(P), pUv = uv ? put(uv) : null, pCol = col ? put(col) : null, pB = colB ? put(colB) : null, pM = mix ? put(mix) : null;
        for (const gr of groups) { const mm0 = mats[gr.materialIndex || 0]; if (!mm0 || mm0.visible === false || mm0.colorWrite === false) continue;
          if (mm0.isMeshBasicMaterial && mm0.side === THREE.BackSide) continue;   // обводка героев — в Blender не нужна
          if (('blob' in ud) || ('patchC' in ud)) continue;                                       // пятно-тень под героем и румянец-наклейка — в Blender настоящие тени
          const st = gr.start || 0, en = Math.min(full.length, st + (gr.count === Infinity ? full.length : gr.count)); const sub = full.subarray(st, en);
          const idx = new Uint32Array(sub.length * ninst); for (let k = 0; k < ninst; k++) for (let i = 0; i < sub.length; i++) idx[k * sub.length + i] = sub[i] + k * N1;
          const mm = { t: mm0.type, c: mm0.color ? [mm0.color.r, mm0.color.g, mm0.color.b] : [1, 1, 1], rough: mm0.roughness != null ? mm0.roughness : .8, metal: mm0.metalness || 0, op: mm0.transparent ? mm0.opacity : 1,
            em: mm0.emissive ? [mm0.emissive.r * (mm0.emissiveIntensity || 1), mm0.emissive.g * (mm0.emissiveIntensity || 1), mm0.emissive.b * (mm0.emissiveIntensity || 1)] : [0, 0, 0], tr: mm0.transmission || 0, side: mm0.side, basic: !!mm0.isMeshBasicMaterial,
            map: texPng(THREE, mm0.map), emap: texPng(THREE, mm0.emissiveMap), amap: mm0.alphaMap ? texPng(THREE, mm0.alphaMap) : null, sheen: mm0.sheen || 0, cc: mm0.clearcoat || 0, ior: mm0.ior || 1.5, vc: !!mm0.vertexColors, ic: !!o.instanceColor, tp: !!mm0.transparent };
          objs.push({ k: 'mesh', name: name + (groups.length > 1 ? '.' + (gr.materialIndex || 0) : ''), kind: o.parent && /bars|barsik|hero/i.test(o.parent.name) ? 'part' : 'std', n: N, pos: pP, idx: put(idx), uv: pUv, col: pCol, colN: col ? N : 0, colB: pB, mix: pM, mat: mm, tag: Object.keys(ud).join(','), shadow: o.castShadow ? 1 : 0, ro: o.renderOrder || 0 }); }
        cnt('вершин обычных', N);
      } catch (e) { L('сбой', name, e.message); }
    }
    const camInfo = { pos: cam.position.toArray(), quat: cam.quaternion.toArray(), fov: cam.fov, aspect: cam.aspect, near: cam.near, far: cam.far, mw: cam.matrixWorld.toArray() };
    let cine = null; try { const loc = S.children.find(c => c.userData && c.userData.cine); cine = loc ? loc.userData.cine : null; if (!cine) S.traverse(x => { if (!cine && x.userData && x.userData.cine) cine = x.userData.cine; });
      cine = cine ? JSON.parse(JSON.stringify(cine, (k, val) => (val && val.isColor) ? [val.r, val.g, val.b] : (val && val.isVector3) ? val.toArray() : (val && (val.isTexture || val.isObject3D)) ? undefined : val)) : null; } catch (e) { cine = { err: e.message }; }
    const lights = []; S.traverse(o => { if (o.isLight && wvis(o)) { const p = new THREE.Vector3(); o.getWorldPosition(p); const tg = o.target ? o.target.getWorldPosition(new THREE.Vector3()).toArray() : null; lights.push({ t: o.type, c: [o.color.r, o.color.g, o.color.b], i: o.intensity, p: p.toArray(), tg, gc: o.groundColor ? [o.groundColor.r, o.groundColor.g, o.groundColor.b] : null, d: o.distance || 0, ang: o.angle || 0 }); } });
    L('снято объектов', objs.length, 'за', Math.round(performance.now() - t0), 'мс', JSON.stringify(stat));
    return { objs, bins, size: off, cam: camInfo, cine, lights, stat, fog: S.fog ? { c: [S.fog.color.r, S.fog.color.g, S.fog.color.b], d: S.fog.density || 0 } : null };
  };
})();
