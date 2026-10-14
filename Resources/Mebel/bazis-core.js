// Разбор файлов Базис-Мебельщика (.b3d / .fr3d, контейнер BZ85) — общий для просмотрщика и конструктора.
// Без three.js: только данные. Проверено на файлах Базиса 8 (.fr3d) и Базиса 23 (.b3d).

const cp1251 = new TextDecoder('windows-1251'), u16 = new TextDecoder('utf-16le');

// ===== Блок: таблица ключей + записи =====
// Типы: 0 объект, 1/2 bool, 3 u8, 4 i32, 5 f64, 6 строка UTF-16, 7 blob, 9 дата-время (f64).
// Индекс ключа 0xFFFFFFFF — безымянный элемент массива.
export function parseBlock(bytes, start = 0, end = bytes.length) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let p = start;
  const u32 = () => { const v = dv.getUint32(p, true); p += 4; return v; };
  const nk = u32(), keys = [];
  for (let i = 0; i < nk; i++) { const l = u32(); keys.push(cp1251.decode(bytes.subarray(p, p + l))); p += l; }
  const entry = () => {
    const ki = u32(), k = ki < keys.length ? keys[ki] : '#', c = u32(), t = bytes[p++];
    let v = null;
    if (t === 0) { v = []; for (let i = 0; i < c; i++) v.push(entry()); }
    else if (t === 1) v = true;
    else if (t === 2) v = false;
    else if (t === 3) v = bytes[p++];
    else if (t === 4) { v = dv.getInt32(p, true); p += 4; }
    else if (t === 5 || t === 9) { v = dv.getFloat64(p, true); p += 8; }
    else if (t === 6) { const n = u32(); v = u16.decode(bytes.subarray(p, p + 2 * n)); p += 2 * n; }
    else if (t === 7) { const n = u32(); v = bytes.subarray(p, p + n); p += n; }
    else throw new Error('Неизвестный тип записи ' + t + ' в позиции ' + (p - 1));
    return { k, t, v };
  };
  const out = [];
  while (p < end) out.push(entry());
  return out;
}
export const kid = (n, name) => n && n.t === 0 ? n.v.find(e => e.k === name) : undefined;
export const val = (n, name, d) => { const e = kid(n, name); return e ? e.v : d; };
export function find(list, name) {
  for (const e of list) { if (e.k === name) return e; if (e.t === 0) { const r = find(e.v, name); if (r) return r; } }
}
async function inflate(bytes, fmt) {
  const ds = new DecompressionStream(fmt);
  return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(ds)).arrayBuffer());
}
function indexOf(b, pat, from) {
  outer: for (let i = from; i <= b.length - pat.length; i++) { for (let j = 0; j < pat.length; j++) if (b[i + j] !== pat[j]) continue outer; return i; }
  return -1;
}
export async function loadBZ(b) {
  if (!(b[0] === 0x42 && b[1] === 0x5A && b[2] === 0x38 && b[3] === 0x35)) throw new Error('Это не файл Базиса (нет BZ85)');
  const i = indexOf(b, [1, 0, 0, 0xFF, 1], 9);
  if (i < 0) throw new Error('Не найден блок с мебелью');
  let header = [];
  try { header = parseBlock(b, 9, i); } catch (e) { /* заголовок не обязателен */ }
  const body = await inflate(b.subarray(i + 5), 'deflate');
  return { header, body:parseBlock(body) };
}
/// ZIP с iPhone («Сжать» в «Файлах»): берём первый .b3d / .fr3d.
export async function fromZip(b) {
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  let p = 0;
  while (p + 30 < b.length && dv.getUint32(p, true) === 0x04034b50) {
    const flags = dv.getUint16(p + 6, true), method = dv.getUint16(p + 8, true);
    let csize = dv.getUint32(p + 18, true);
    const nlen = dv.getUint16(p + 26, true), xlen = dv.getUint16(p + 28, true);
    const name = new TextDecoder().decode(b.subarray(p + 30, p + 30 + nlen));
    const data0 = p + 30 + nlen + xlen;
    if (flags & 8 && csize === 0) {
      const cd = indexOf(b, [0x50, 0x4b, 0x01, 0x02], data0);
      for (let q = cd; q > 0 && q < b.length - 46 && dv.getUint32(q, true) === 0x02014b50;) {
        const n2 = dv.getUint16(q + 28, true), off = dv.getUint32(q + 42, true);
        if (off === p) { csize = dv.getUint32(q + 20, true); break; }
        q += 46 + n2 + dv.getUint16(q + 30, true) + dv.getUint16(q + 32, true);
      }
    }
    const data = b.subarray(data0, data0 + csize);
    if (/\.(b3d|fr3d)$/i.test(name) && !name.startsWith('__MACOSX')) {
      return { name:name.split('/').pop(), bytes: method === 8 ? await inflate(data, 'deflate-raw') : data };
    }
    p = data0 + csize + (flags & 8 ? (dv.getUint32(data0 + csize, true) === 0x08074b50 ? 16 : 12) : 0);
  }
  throw new Error('В архиве нет файла .b3d или .fr3d');
}
/// Открыть байты файла (.b3d/.fr3d или .zip с ним).
export async function openBytes(bytes, name = '') {
  if (bytes[0] === 0x50 && bytes[1] === 0x4B) { const z = await fromZip(bytes); name = z.name; bytes = z.bytes; }
  const { header, body } = await loadBZ(bytes);
  const art = find(header, 'Article');
  const title = (art && val(art, 'Name')) || name.replace(/\.(b3d|fr3d)$/i, '') || 'Мебель';
  return { title, header, body };
}

// ===== Геометрия =====
/// Контур: 0x10 отрезок, 0x12 дуга, 0x11/0x14 окружность (cx, cy, r). Возвращает петли точек.
export function contourLoops(blob) {
  const dv = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
  let p = 0; const n = dv.getUint32(p, true); p += 4;
  const f = () => { const v = dv.getFloat64(p, true); p += 8; return v; };
  const segs = [], circles = [];
  for (let i = 0; i < n && p < blob.length; i++) {
    const t = blob[p++];
    if (t === 0x10) { const x1 = f(), y1 = f(), x2 = f(), y2 = f(); segs.push([[x1, y1], [x2, y2]]); }
    else if (t === 0x12) {
      const cx = f(), cy = f(), sx = f(), sy = f(), ex = f(), ey = f(), ccw = blob[p++] === 1;
      const r = Math.hypot(sx - cx, sy - cy);
      let a0 = Math.atan2(sy - cy, sx - cx), a1 = Math.atan2(ey - cy, ex - cx);
      if (ccw) { while (a1 <= a0 + 1e-9) a1 += 2 * Math.PI; } else { while (a1 >= a0 - 1e-9) a1 -= 2 * Math.PI; }
      const steps = Math.max(4, Math.ceil(Math.abs(a1 - a0) / (Math.PI / 24)));
      const pts = []; for (let k = 0; k <= steps; k++) { const a = a0 + (a1 - a0) * k / steps; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
      segs.push(pts);
    } else if (t === 0x11 || t === 0x14) {
      const cx = f(), cy = f(), r = f(), pts = [];
      for (let k = 0; k < 32; k++) { const a = 2 * Math.PI * k / 32; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
      circles.push(pts);
    } else break;
  }
  const close = (a, b) => Math.abs(a[0] - b[0]) < 0.05 && Math.abs(a[1] - b[1]) < 0.05;
  const loops = [], left = segs.slice();
  while (left.length) {
    const loop = left.shift().slice();
    for (let guard = 0; guard < 10000 && left.length; guard++) {
      const end = loop[loop.length - 1];
      if (close(end, loop[0]) && loop.length > 2) break;
      const i = left.findIndex(s => close(s[0], end) || close(s[s.length - 1], end));
      if (i < 0) break;
      let s = left.splice(i, 1)[0]; if (!close(s[0], end)) s = s.slice().reverse();
      loop.push(...s.slice(1));
    }
    if (loop.length > 3 && close(loop[loop.length - 1], loop[0])) loop.pop();
    loops.push(loop);
  }
  return loops.concat(circles);
}
export const loopArea = l => l.reduce((s, p, i) => { const q = l[(i + 1) % l.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0) / 2;

/// TriData: сетки фурнитуры (материал, матрица 4×4, треугольники по 112 байт).
export function triMeshes(blob) {
  const dv = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
  let p = 0; const n = dv.getUint32(p, true); p += 4; const out = [];
  for (let i = 0; i < n && p < blob.length; i++) {
    const ml = dv.getUint32(p, true); p += 4 + ml * 2;
    const m = []; for (let k = 0; k < 16; k++) { m.push(dv.getFloat64(p, true)); p += 8; }
    p += 1;
    const nt = dv.getUint32(p, true); p += 4;
    const pos = new Float32Array(nt * 9);
    for (let t = 0; t < nt; t++) { for (let k = 0; k < 9; k++) pos[t * 9 + k] = dv.getFloat32(p + k * 4, true); p += 112; }
    out.push({ pos, m });
  }
  return out;
}

// ----- позиция: кватернион + сдвиг -----
const qmul = (a, b) => [a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1], a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],
                        a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3], a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];
function qrot(q, v) {
  const [x, y, z, w] = q, tx = 2*(y*v[2]-z*v[1]), ty = 2*(z*v[0]-x*v[2]), tz = 2*(x*v[1]-y*v[0]);
  return [v[0]+w*tx+(y*tz-z*ty), v[1]+w*ty+(z*tx-x*tz), v[2]+w*tz+(x*ty-y*tx)];
}
const ID = { q:[0, 0, 0, 1], t:[0, 0, 0] };
function compose(P, L) { const r = qrot(P.q, L.t); return { q:qmul(P.q, L.q), t:[r[0]+P.t[0], r[1]+P.t[1], r[2]+P.t[2]] }; }
export function trans(o) {
  const t = kid(o, 'Trans'); if (!t) return ID;
  let q = [val(t, 'Rx', 0), val(t, 'Ry', 0), val(t, 'Rz', 0), val(t, 'Rw', 1)];
  const l = Math.hypot(...q); q = l < 1e-9 ? [0, 0, 0, 1] : q.map(v => v / l);
  return { q, t:[val(t, 'X', 0), val(t, 'Y', 0), val(t, 'Z', 0)] };
}
const apply = (X, p) => { const r = qrot(X.q, p); return [r[0]+X.t[0], r[1]+X.t[1], r[2]+X.t[2]]; };
function box() { return { min:[Infinity, Infinity, Infinity], max:[-Infinity, -Infinity, -Infinity] }; }
function grow(b, p) { for (let i = 0; i < 3; i++) { b.min[i] = Math.min(b.min[i], p[i]); b.max[i] = Math.max(b.max[i], p[i]); } }
const center = b => b.min.map((v, i) => (v + b.max[i]) / 2);
const inside = (b, p, tol = 2) => p.every((v, i) => v >= b.min[i] - tol && v <= b.max[i] + tol);

// ===== Файл → модули конструктора =====
// Модуль = панели с кодом в имени («П1: Боковина левая»). Фасад модуля — сторона, противоположная задней стенке.
// Внутри модуля: полки (по высоте), ящики, корзины, брючницы (выдвигаются к фасаду).
const COLORS = [[/H1312|Уайт-Ривер/i, '#d8c8ab'], [/U211|Миндаль/i, '#dccab0'], [/W1100|W980|Белый/i, '#f4f3ef'],
  [/U702|Кашемир/i, '#d8cfc2'], [/U727/i, '#9c9890'], [/U638|шалфей/i, '#9aa58f'], [/U961|Графит/i, '#4a4c4e'],
  [/Кассела|H1180|табак/i, '#8a6646'], [/H3309|песочн/i, '#cfb38c'], [/H1145|натурал/i, '#b58a5c'], [/Дуб/i, '#b9976d']];
export const colorOf = mat => (COLORS.find(([re]) => re.test(mat || '')) || [0, '#e8e2d6'])[1];
const short = mat => String(mat || '').split('\r')[0].replace(/^ЛДСП\s?\d+\s*/i, '').trim();

export function toProject(body, title = 'Мебель') {
  const doc = find(body, 'Document') || { v:body };
  const model = find(doc.v, 'Model');
  if (!model) throw new Error('В файле нет модели');
  const panels = [], movers = [], meshes = [];
  const walk = (list, X, mover) => {
    for (const o of list) {
      if (o.k !== 'Obj' || o.t !== 0) continue;
      const type = val(o, 'Type', 0), name = String(val(o, 'Name', '') || '').split('\r')[0], L = compose(X, trans(o));
      let mv = mover;
      if (type === 1005 && /^(Ящик|Корзина|Брючница)/.test(name)) {
        const kind = name.startsWith('Ящик') ? 'drawer' : name.startsWith('Корзина') ? 'basket' : 'trousers';
        mv = { kind, name, fs:/FS|скрыт/i.test(name), b:box(), facade:box(), box:box(), bottom:Infinity, boxMat:'', faceMat:'', id:movers.length };
        movers.push(mv);
      }
      if (type === 4002 || type === 2004) {
        const blob = val(o, 'Contour'); if (!blob) continue;
        const th = type === 2004 ? val(o, 'Thickness', 0) : val(o, 'Thick', 16);
        const loops = contourLoops(blob).filter(l => l.length > 2).sort((a, b) => Math.abs(loopArea(b)) - Math.abs(loopArea(a)));
        if (!loops.length) continue;
        const b = box();
        for (const [x, y] of loops[0]) { grow(b, apply(L, [x, y, 0])); grow(b, apply(L, [x, y, th])); }
        const mat = String(val(o, 'Mat', '') || '');
        const m = /^([А-ЯЁA-Z]{1,3}\d+)\s*:\s*(.*)$/.exec(name);
        const p = { name, code:m ? m[1] : '', part:m ? m[2] : name, mat, th, b, prof:type === 2004, mv };
        panels.push(p);
        if (mv) { grow(mv.b, b.min); grow(mv.b, b.max);
          const isF = /Фасад/i.test(name), t = isF ? mv.facade : mv.box; grow(t, b.min); grow(t, b.max);
          if (type === 4002) { if (isF) mv.faceMat ||= mat; else mv.boxMat ||= mat; }
          if (!isF && b.max[1] - b.min[1] <= th + 0.5) mv.bottom = Math.min(mv.bottom, b.min[1]); }   // горизонтальная деталь короба — дно
      } else if (type === 10000 && mv) {
        const td = val(o, 'TriData');
        if (td) for (const t of triMeshes(td)) for (let i = 0; i < t.pos.length; i += 3)
          grow(mv.b, apply(L, [t.pos[i] + t.m[12], t.pos[i + 1] + t.m[13], t.pos[i + 2] + t.m[14]]));
      }
      const sub = kid(o, 'Objs');
      if (sub && type !== 4002) walk(sub.v, L, mv);
    }
  };
  walk(model.v, ID, null);

  // модули по коду
  const mods = new Map();
  for (const p of panels) if (p.code && !p.mv) {
    const m = mods.get(p.code) || { code:p.code, b:box(), panels:[] };
    grow(m.b, p.b.min); grow(m.b, p.b.max); m.panels.push(p); mods.set(p.code, m);
  }
  if (!mods.size) throw new Error('В файле нет модулей с кодом в имени («П1: Боковина…»)');
  const all = box(); for (const m of mods.values()) { grow(all, m.b.min); grow(all, m.b.max); }
  const mid = center(all);
  const walls = [];
  for (const p of panels) if (/^Стена/i.test(p.name)) walls.push(p);

  const out = [];
  for (const m of mods.values()) {
    const c = center(m.b), size = m.b.max.map((v, i) => v - m.b.min[i]);
    // фасад: от задней стенки к центру модуля, иначе — к центру всей мебели
    let n = null;
    const back = m.panels.find(p => /Задн/i.test(p.part));
    if (back) {
      const bc = center(back.b), dx = c[0] - bc[0], dz = c[2] - bc[2];
      n = Math.abs(dx) > Math.abs(dz) ? [Math.sign(dx), 0] : [0, Math.sign(dz)];
    }
    if (!n || (!n[0] && !n[1])) {
      const dx = mid[0] - c[0], dz = mid[2] - c[2];
      n = Math.abs(dx) > Math.abs(dz) ? [Math.sign(dx) || 1, 0] : [0, Math.sign(dz) || 1];
    }
    const alongX = n[0] !== 0;                       // фасад смотрит по X → ширина модуля вдоль Z
    const w = Math.round(alongX ? size[2] : size[0]), d = Math.round(alongX ? size[0] : size[2]), h = Math.round(size[1]);
    const rotY = Math.round(Math.atan2(n[0], n[1]) * 180 / Math.PI);
    const y0 = m.b.min[1];
    const side = m.panels.find(p => /Боков/i.test(p.part)) || m.panels[0];
    const thick = Math.round(side.th || 16);
    const shelves = m.panels.filter(p => /Полк/i.test(p.part)).map(p => Math.round(p.b.min[1] - y0)).sort((a, b) => a - b);
    const shelf = m.panels.find(p => /Полк/i.test(p.part));
    // по глубине: фасадная грань модуля и задняя; зазоры полки спереди/сзади; толщина задней стенки
    const ax = alongX ? 0 : 2, fwd = alongX ? n[0] : n[1];
    const frontC = fwd > 0 ? m.b.max[ax] : m.b.min[ax], backC = fwd > 0 ? m.b.min[ax] : m.b.max[ax];
    const shelfGap = shelf ? [Math.round(Math.abs(frontC - (fwd > 0 ? shelf.b.max[ax] : shelf.b.min[ax]))),
                              Math.round(Math.abs((fwd > 0 ? shelf.b.min[ax] : shelf.b.max[ax]) - backC))] : undefined;
    const backTh = back ? Math.round(back.th || 3) : 0;
    // выдвижные элементы этого модуля
    const items = [];
    for (const v of movers) {
      if (!isFinite(v.b.min[0]) || !inside(m.b, center(v.b))) continue;
      const fb = isFinite(v.facade.min[0]) ? v.facade : v.b, bb = isFinite(v.box.min[0]) ? v.box : v.b;
      const depth = Math.round(alongX ? bb.max[0] - bb.min[0] : bb.max[2] - bb.min[2]);
      const it = { kind:v.kind, y:Math.round(fb.min[1] - y0), h:Math.round(fb.max[1] - fb.min[1]),
        boxH:Math.round(bb.max[1] - bb.min[1]), boxY:Math.round(bb.min[1] - fb.min[1]),
        boxW:Math.round(alongX ? bb.max[2] - bb.min[2] : bb.max[0] - bb.min[0]),
        bottomY:isFinite(v.bottom) ? Math.round(v.bottom - bb.min[1]) : 0, depth, name:v.name,
        faceColor:v.faceMat ? colorOf(v.faceMat) : undefined, faceName:v.faceMat ? short(v.faceMat) : undefined,
        boxColor:v.boxMat ? colorOf(v.boxMat) : undefined, boxName:v.boxMat ? short(v.boxMat) : undefined };
      if (v.kind === 'drawer') it.travel = v.fs ? 440 : 400; else it.travel = 420;
      if (v.kind !== 'drawer') { it.y = Math.round(v.b.min[1] - y0); it.h = Math.round(v.b.max[1] - v.b.min[1]); }
      items.push(it);
    }
    items.sort((a, b) => a.y - b.y);
    const nd = items.filter(i => i.kind === 'drawer').length, nb = items.filter(i => i.kind === 'basket').length,
      nt = items.filter(i => i.kind === 'trousers').length;
    const parts = [`${shelves.length} полок`]; if (nd) parts.push(`${nd} ящ.`); if (nb) parts.push('корзина'); if (nt) parts.push('брючница');
    out.push({ code:m.code, name:'Секция: ' + parts.join(', '), type:'wardrobe', w, h, d,
      x:Math.round(c[0]), y:Math.round(c[1]), z:Math.round(c[2]), rotY,
      color:colorOf(side.mat), colorName:short(side.mat),
      opts:{ doors:0, drawers:nd, shelves:shelves.length, shelvesAt:shelves, front:'open', plinth:Math.round(y0), thick,
        shelfColor:shelf ? colorOf(shelf.mat) : undefined, shelfName:shelf ? short(shelf.mat) : undefined, shelfGap, backTh, items } });
  }
  out.sort((a, b) => a.code.localeCompare(b.code, 'ru'));

  // стены «для просмотра» → формат RoomPlan (метры, матрица 4×4 по столбцам)
  const wallOut = walls.map((p, i) => {
    const s = p.b.max.map((v, k) => v - p.b.min[k]), c = center(p.b);
    const thinX = s[0] < s[2], k = thinX ? 0 : 2;
    c[k] = mid[k] > c[k] ? p.b.max[k] : p.b.min[k];     // плоскость стены — внутренняя грань
    const T = thinX ? [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0] : [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0];
    return { kind:'wall', code:'С' + (i + 1), widthMm:Math.round(thinX ? s[2] : s[0]), heightMm:Math.round(s[1]),
      transform:[...T, c[0] / 1000, c[1] / 1000, c[2] / 1000, 1] };
  });
  return { name:title, modules:out, walls:wallOut };
}
