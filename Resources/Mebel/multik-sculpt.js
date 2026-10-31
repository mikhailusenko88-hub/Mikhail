// «Скульптор»: герои из математической глины.
// Каждая часть героя (голова, тело, лапы, хвост) — не набор шаров, а одна поверхность,
// заданная полем расстояний (SDF). Формы плавно перетекают друг в друга (щёки в мордочку,
// пузико в тело, лапка в ладошку), цвет на стыках мягкий, полоски рисуются прямо по форме,
// а мягкие тени в складках (ambient occlusion) считаются один раз и запекаются в цвет вершин.
// Модуль — чистая математика (без three.js): на входе примитивы, на выходе массивы вершин.
(function (global) {
  'use strict';
  const S = {};
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const mix = (a, b, t) => a + (b - a) * t;
  const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const fract = x => x - Math.floor(x);

  // ---------- примитивы (в своих координатах) ----------
  function sdEll(x, y, z, rx, ry, rz) { // эллипсоид (оценка Иниго Килеса)
    const k0 = Math.sqrt((x / rx) ** 2 + (y / ry) ** 2 + (z / rz) ** 2), k1 = Math.sqrt((x / (rx * rx)) ** 2 + (y / (ry * ry)) ** 2 + (z / (rz * rz)) ** 2);
    return k1 > 1e-12 ? k0 * (k0 - 1) / k1 : -Math.min(rx, ry, rz);
  }
  function sdRoundCone(x, y, z, h, r1, r2) { // от y=0 (радиус r1) до y=h (радиус r2), скруглённые концы
    const q = Math.sqrt(x * x + z * z), b = (r1 - r2) / h, a = Math.sqrt(Math.max(1e-6, 1 - b * b)), k = -b * q + a * y;
    if (k < 0) return Math.sqrt(q * q + y * y) - r1;
    if (k > a * h) return Math.sqrt(q * q + (y - h) ** 2) - r2;
    return q * a + y * b - r1;
  }
  function sdCyl(x, y, z, rb, rt, h, rr) { // цилиндр/усечённый конус со скруглёнными краями
    const q = Math.sqrt(x * x + z * z), t = clamp((y + h / 2) / h, 0, 1), r = rb + (rt - rb) * t;
    const dx = q - r + rr, dy = Math.abs(y) - h / 2 + rr;
    return Math.min(Math.max(dx, dy), 0) + Math.sqrt(Math.max(dx, 0) ** 2 + Math.max(dy, 0) ** 2) - rr;
  }

  // ---------- один примитив: расстояние и цвет в точке ----------
  // pr: { type: 'ell'|'cap'|'cone'|'cyl', t:[x,y,z], inv:[9] (поворот в свои координаты, по строкам), r:[rx,ry,rz] | r1,r2,h,rr,s:[sx,sy,sz],
  //       col:[r,g,b] (линейный цвет), pat: {mode:'body'|'head'|'tail', col:[r,g,b], n, u0, u1} | null, k: мягкость стыка, op: 'add'|'sub' }
  function local(pr, x, y, z, out) {
    const dx = x - pr.t[0], dy = y - pr.t[1], dz = z - pr.t[2], m = pr.inv;
    out[0] = m[0] * dx + m[1] * dy + m[2] * dz; out[1] = m[3] * dx + m[4] * dy + m[5] * dz; out[2] = m[6] * dx + m[7] * dy + m[8] * dz; return out;
  }
  const L = [0, 0, 0];
  function dist(pr, x, y, z) {
    local(pr, x, y, z, L); const lx = L[0], ly = L[1], lz = L[2];
    if (pr.type === 'ell') return sdEll(lx, ly, lz, pr.r[0], pr.r[1], pr.r[2]);
    const s = pr.s, sm = Math.min(s[0], s[1], s[2]), X = lx / s[0], Y = ly / s[1], Z = lz / s[2];
    let d;
    if (pr.type === 'cap') d = sdRoundCone(X, Y + pr.h / 2, Z, Math.max(pr.h, 1e-4), pr.r1, pr.r1);
    else if (pr.type === 'cone') d = sdRoundCone(X, Y + pr.h / 2, Z, pr.h, pr.r1, pr.r2);
    else d = sdCyl(X, Y, Z, pr.r1, pr.r2, pr.h, pr.rr);
    return d * sm;
  }
  // рисунок (0..1): одна функция для поверхности (её повторяет шейдер) и для шерсти
  // q — точка в своих координатах примитива: для эллипсоида нормированная (x/rx, y/ry, z/rz), для хвоста q[0] = доля длины
  function patW(mode, n, qx, qy, qz) {
    if (mode === 3) { const f = fract(qx * n + .15); return sstep(.05, .1, f) * (1 - sstep(.36, .42, f)); }
    const lon = Math.atan2(qx, qz), lat = qy, wob = Math.sin(lat * 5.3 + n) * .045 + Math.sin(lat * 11.7) * .015;
    if (mode === 2) { const f = fract(lon / (2 * Math.PI) * n + .5 + wob); return sstep(.12, .34, lat) * sstep(0, .04, f) * (1 - sstep(.26, .33, f)); }
    if (mode === 1) { const f = fract(lon / (2 * Math.PI) * n + wob * 1.6); return (1 - sstep(.6, .85, Math.abs(lat))) * sstep(0, .04, f) * (1 - sstep(.28, .35, f)); }
    if (mode === 4) { const h = Math.sin(qx * 9.1 + qy * 3.7) * Math.sin(qy * 8.3 - qz * 5.1) * Math.sin(qz * 7.7 + qx * 2.9); return sstep(.18, .3, h); }
    return 0;
  }
  S.patW = patW; S.MODES = { body: 1, head: 2, tail: 3, spots: 4 };
  function patCoord(pr, x, y, z, out) { local(pr, x, y, z, out);
    if (pr.type === 'ell') { out[0] /= pr.r[0]; out[1] /= pr.r[1]; out[2] /= pr.r[2]; }
    else { const t = clamp((out[1] / pr.s[1] + pr.h / 2) / pr.h, 0, 1); out[0] = mix(pr.pat.u0, pr.pat.u1, t); out[1] = 0; out[2] = 0; } return out; }
  function paint(pr, x, y, z, out) { out[0] = pr.col[0]; out[1] = pr.col[1]; out[2] = pr.col[2]; return out; }

  // ---------- поле части: плавное объединение примитивов + выемки ----------
  const C1 = [0, 0, 0];
  function field(prims, x, y, z, col, info) {
    let d = 1e9, first = true; if (info) { info.pr = null; info.w = 0; }
    for (let i = 0; i < prims.length; i++) { const pr = prims[i]; if (pr.op === 'sub' || pr.op === 'paint') continue;
      const di = dist(pr, x, y, z);
      if (first) { d = di; if (col) paint(pr, x, y, z, col); if (info && pr.pat) { info.pr = pr; info.w = 1; } first = false; continue; }
      const k = pr.k || 0;
      const kc = Math.max(k * .12, pr.kcMin || 1e-4), hc = clamp(.5 + .5 * (d - di) / kc, 0, 1); // граница цвета — узкая
      if (col && hc > 0) { paint(pr, x, y, z, C1); col[0] = mix(col[0], C1[0], hc); col[1] = mix(col[1], C1[1], hc); col[2] = mix(col[2], C1[2], hc); }
      if (info) { if (pr.pat && hc > .5) { info.pr = pr; info.w = 1; } else if (!pr.pat || !info.pr || info.pr.pat.mode !== pr.pat.mode) info.w *= 1 - hc; }
      if (k > 0) { const h = clamp(.5 + .5 * (d - di) / k, 0, 1); if (h > 0) d = mix(d, di, h) - k * h * (1 - h); }
      else if (di < d) d = di;
    }
    if (col) for (let i = 0; i < prims.length; i++) { const pr = prims[i]; if (pr.op !== 'paint') continue;
      const w = 1 - sstep(-pr.k * .5, pr.k, dist(pr, x, y, z)); if (w > 0) { col[0] = mix(col[0], pr.col[0], w); col[1] = mix(col[1], pr.col[1], w); col[2] = mix(col[2], pr.col[2], w); } }
    for (let i = 0; i < prims.length; i++) { const pr = prims[i]; if (pr.op !== 'sub') continue;
      const ds = -dist(pr, x, y, z), k = pr.k || 1e-4, h = clamp(.5 - .5 * (d - ds) / k, 0, 1); d = mix(d, ds, h) + k * h * (1 - h); }
    return d;
  }
  S.field = (prims, x, y, z) => field(prims, x, y, z, null);

  // ---------- сетка: «поверхностные сети» (Surface Nets) ----------
  // groups — все части героя (для мягких теней друг от друга), prims — эта часть.
  S.mesh = function (prims, opts) {
    opts = opts || {};
    const res = opts.res || 56; let mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
    for (const pr of prims) { if (pr.op === 'sub' || pr.op === 'paint') continue; const R = pr.br + (pr.k || 0) * .5; for (let a = 0; a < 3; a++) { mn[a] = Math.min(mn[a], pr.bc[a] - R); mx[a] = Math.max(mx[a], pr.bc[a] + R); } }
    const ext = Math.max(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]), cell = opts.cell || ext / res;
    for (let a = 0; a < 3; a++) { mn[a] -= cell * 2; mx[a] += cell * 2; }
    for (const pr of prims) pr.kcMin = cell * 2.4; // край цвета — ровный, на 2–3 клетки
    const nx = Math.ceil((mx[0] - mn[0]) / cell) + 1, ny = Math.ceil((mx[1] - mn[1]) / cell) + 1, nz = Math.ceil((mx[2] - mn[2]) / cell) + 1;
    const F = new Float32Array(nx * ny * nz), I = (i, j, k) => i + nx * (j + ny * k);
    // быстро: пространство делим на кубики 4×4×4; если кубик далеко от поверхности — считаем одну точку на весь кубик
    const B = 4, half = B * cell * .5, reach = half * 1.75 + cell;
    for (let bk = 0; bk < nz; bk += B) for (let bj = 0; bj < ny; bj += B) for (let bi = 0; bi < nx; bi += B) {
      const i1 = Math.min(nx, bi + B + 1), j1 = Math.min(ny, bj + B + 1), k1 = Math.min(nz, bk + B + 1);
      const dc = field(prims, mn[0] + (bi + B / 2) * cell, mn[1] + (bj + B / 2) * cell, mn[2] + (bk + B / 2) * cell, null);
      if (Math.abs(dc) > reach) { for (let k = bk; k < k1; k++) for (let j = bj; j < j1; j++) for (let i = bi; i < i1; i++) F[I(i, j, k)] = dc; continue; }
      for (let k = bk; k < k1; k++) for (let j = bj; j < j1; j++) for (let i = bi; i < i1; i++) F[I(i, j, k)] = field(prims, mn[0] + i * cell, mn[1] + j * cell, mn[2] + k * cell, null);
    }
    // вершина в каждой клетке, через которую проходит поверхность
    const cnx = nx - 1, cny = ny - 1, cnz = nz - 1, vid = new Int32Array(cnx * cny * cnz).fill(-1), V = [];
    const CI = (i, j, k) => i + cnx * (j + cny * k);
    const corner = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]];
    const edges = [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]];
    const val = new Float32Array(8);
    for (let k = 0; k < cnz; k++) for (let j = 0; j < cny; j++) for (let i = 0; i < cnx; i++) {
      let neg = 0; for (let c = 0; c < 8; c++) { const v = F[I(i + corner[c][0], j + corner[c][1], k + corner[c][2])]; val[c] = v; if (v < 0) neg++; }
      if (neg === 0 || neg === 8) continue;
      let sx = 0, sy = 0, sz = 0, cnt = 0;
      for (const [a, b] of edges) { const va = val[a], vb = val[b]; if ((va < 0) === (vb < 0)) continue; const t = va / (va - vb);
        sx += corner[a][0] + (corner[b][0] - corner[a][0]) * t; sy += corner[a][1] + (corner[b][1] - corner[a][1]) * t; sz += corner[a][2] + (corner[b][2] - corner[a][2]) * t; cnt++; }
      vid[CI(i, j, k)] = V.length / 3; V.push(mn[0] + (i + sx / cnt) * cell, mn[1] + (j + sy / cnt) * cell, mn[2] + (k + sz / cnt) * cell);
    }
    // грани: на каждом ребре сетки со сменой знака — четырёхугольник из 4 соседних клеток
    const T = [];
    for (let k = 1; k < cnz; k++) for (let j = 1; j < cny; j++) for (let i = 1; i < cnx; i++) {
      const v0 = F[I(i, j, k)] < 0;
      if (v0 !== (F[I(i + 1, j, k)] < 0)) { const a = vid[CI(i, j - 1, k - 1)], b = vid[CI(i, j, k - 1)], c = vid[CI(i, j, k)], d = vid[CI(i, j - 1, k)]; if (a >= 0 && b >= 0 && c >= 0 && d >= 0) T.push(a, b, c, a, c, d); }
      if (v0 !== (F[I(i, j + 1, k)] < 0)) { const a = vid[CI(i - 1, j, k - 1)], b = vid[CI(i, j, k - 1)], c = vid[CI(i, j, k)], d = vid[CI(i - 1, j, k)]; if (a >= 0 && b >= 0 && c >= 0 && d >= 0) T.push(a, b, c, a, c, d); }
      if (v0 !== (F[I(i, j, k + 1)] < 0)) { const a = vid[CI(i - 1, j - 1, k)], b = vid[CI(i, j - 1, k)], c = vid[CI(i, j, k)], d = vid[CI(i - 1, j, k)]; if (a >= 0 && b >= 0 && c >= 0 && d >= 0) T.push(a, b, c, a, c, d); }
    }
    const nv = V.length / 3, pos = new Float32Array(V), nor = new Float32Array(nv * 3), col = new Float32Array(nv * 3), colB = new Float32Array(nv * 3), mixS = new Float32Array(nv), pat = new Float32Array(nv * 4), e = cell * .35, info = { pr: null, w: 0 }, q = [0, 0, 0];
    const main = prims.find(pr => pr.op === 'add'), others = prims.filter(pr => pr !== main && pr.op !== 'sub');
    const grad = (x, y, z, o) => { const a = field(prims, x + e, y - e, z - e), b = field(prims, x - e, y - e, z + e), c = field(prims, x - e, y + e, z - e), d = field(prims, x + e, y + e, z + e);
      o[0] = a - b - c + d; o[1] = -a - b + c + d; o[2] = -a + b - c + d; const l = Math.hypot(o[0], o[1], o[2]) || 1; o[0] /= l; o[1] /= l; o[2] /= l; return o; };
    const g = [0, 0, 0], c = [0, 0, 0];
    for (let v = 0; v < nv; v++) { let x = pos[v * 3], y = pos[v * 3 + 1], z = pos[v * 3 + 2];
      for (let it = 0; it < 2; it++) { const d = field(prims, x, y, z); grad(x, y, z, g); x -= g[0] * d; y -= g[1] * d; z -= g[2] * d; } // точно на поверхность
      grad(x, y, z, g); field(prims, x, y, z, c, info);
      if (info.pr) { patCoord(info.pr, x, y, z, q); pat[v * 4] = q[0]; pat[v * 4 + 1] = q[1]; pat[v * 4 + 2] = q[2]; pat[v * 4 + 3] = 1; }
      // два цвета и «кто ближе»: граница цвета рисуется шейдером на каждом пикселе — чёткая и ровная при любой сетке
      { const d0 = dist(main, x, y, z); let best = -1e9, bp = null; for (const pr of others) { const sj = pr.op === 'paint' ? -dist(pr, x, y, z) : d0 - dist(pr, x, y, z); if (sj > best) { best = sj; bp = pr; } }
        if (info.pr) pat[v * 4 + 3] = bp && !bp.pat ? 2 : 1; // 2 — рисунок только на основном цвете (не на пузике)
        const cb = bp ? bp.col : main.col; colB[v * 3] = cb[0]; colB[v * 3 + 1] = cb[1]; colB[v * 3 + 2] = cb[2]; mixS[v] = bp ? best : -1;
        c[0] = main.col[0]; c[1] = main.col[1]; c[2] = main.col[2]; }
      pos[v * 3] = x; pos[v * 3 + 1] = y; pos[v * 3 + 2] = z; nor[v * 3] = g[0]; nor[v * 3 + 1] = g[1]; nor[v * 3 + 2] = g[2]; col[v * 3] = c[0]; col[v * 3 + 1] = c[1]; col[v * 3 + 2] = c[2]; }
    // порядок обхода — по направлению поверхности (никаких «вывернутых» чёрных граней)
    const idx = new Uint32Array(T);
    for (let t = 0; t < idx.length; t += 3) { const a = idx[t] * 3, b = idx[t + 1] * 3, cc = idx[t + 2] * 3;
      const ux = pos[b] - pos[a], uy = pos[b + 1] - pos[a + 1], uz = pos[b + 2] - pos[a + 2], vx = pos[cc] - pos[a], vy = pos[cc + 1] - pos[a + 1], vz = pos[cc + 2] - pos[a + 2];
      const fx = uy * vz - uz * vy, fy = uz * vx - ux * vz, fz = ux * vy - uy * vx;
      if (fx * (nor[a] + nor[b] + nor[cc]) + fy * (nor[a + 1] + nor[b + 1] + nor[cc + 1]) + fz * (nor[a + 2] + nor[b + 2] + nor[cc + 2]) < 0) { const tmp = idx[t + 1]; idx[t + 1] = idx[t + 2]; idx[t + 2] = tmp; } }
    return { pos, nor, col, colB, mixS, pat, idx, cell };
  };

  // ---------- мягкие тени в складках: считаются один раз по всему герою ----------
  // groups: массив частей (у каждой свои примитивы); scale — характерный размер героя
  S.occlusion = function (groups, pos, nor, scale, strength) {
    const n = pos.length / 3, ao = new Float32Array(n), K = strength || 2.4;
    for (let v = 0; v < n; v++) { const x = pos[v * 3], y = pos[v * 3 + 1], z = pos[v * 3 + 2], nx = nor[v * 3], ny = nor[v * 3 + 1], nz = nor[v * 3 + 2];
      let occ = 0, sca = 1;
      for (let i = 1; i <= 5; i++) { const h = scale * (.03 + .16 * i / 5); let d = 1e9; for (const gp of groups) d = Math.min(d, field(gp, x + nx * h, y + ny * h, z + nz * h, null)); occ += Math.max(0, h - d) * sca; sca *= .72; }
      ao[v] = clamp(1 - K * occ / scale, 0, 1); }
    return ao;
  };
  // толщина в каждой точке (насквозь внутрь): тонкие места (уши, кончик носа) будут просвечивать на свету
  S.thickness = function (prims, pos, nor, maxT, minStep) {
    const n = pos.length / 3, th = new Float32Array(n);
    for (let v = 0; v < n; v++) { const x = pos[v * 3], y = pos[v * 3 + 1], z = pos[v * 3 + 2], nx = nor[v * 3], ny = nor[v * 3 + 1], nz = nor[v * 3 + 2];
      let t = minStep * 2; for (let i = 0; i < 40 && t < maxT; i++) { const d = field(prims, x - nx * t, y - ny * t, z - nz * t, null); if (d > 0) break; t += Math.max(-d * .8, minStep); }
      th[v] = Math.min(t, maxT); }
    return th;
  };
  // запечь тень в цвет: в складках темнее и чуть насыщеннее (как свет, прошедший сквозь шерсть)
  S.bake = function (col, ao, floor) {
    const f = floor == null ? .42 : floor;
    for (let v = 0; v < ao.length; v++) { const a = ao[v], k = f + (1 - f) * a, r = col[v * 3], g = col[v * 3 + 1], b = col[v * 3 + 2], l = (r + g + b) / 3, sat = 1 + (1 - a) * .35;
      col[v * 3] = Math.max(0, (l + (r - l) * sat) * k); col[v * 3 + 1] = Math.max(0, (l + (g - l) * sat) * k); col[v * 3 + 2] = Math.max(0, (l + (b - l) * sat) * k); }
  };

  global.MKSculpt = S;
})(typeof window !== 'undefined' ? window : globalThis);
