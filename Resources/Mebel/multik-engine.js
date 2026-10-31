/* Движок мультиков «Замер 3D»: персонажи по замороженному коду, декорации, действия, камера, звук.
   Всё рисуется кодом, кадр = функция времени → одинаковый результат при каждой сборке. */
'use strict';
(function (global) {
const W = 1920, H = 1080, GROUND = H * 0.86, UNIT = 400; // 1 ед. роста персонажа = 400 px при общем плане
const MK = { W, H, GROUND };

// ---------- утилиты ----------
function hash32(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h >>> 0; }
function canon(o) {
  if (Array.isArray(o)) return '[' + o.map(canon).join(',') + ']';
  if (o && typeof o === 'object') return '{' + Object.keys(o).sort().map(k => JSON.stringify(k) + ':' + canon(o[k])).join(',') + '}';
  return JSON.stringify(o);
}
function rng(seed) { let s = (seed >>> 0) || 0x9e3779b9; return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }; }
const clamp = (v, a, b) => v < a ? a : v > b ? b : v, lerp = (a, b, t) => a + (b - a) * t;
const ease = t => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
function rgb(h) { h = String(h || '#888').replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join(''); const n = parseInt(h, 16) || 0; return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function shade(h, a) { const c = rgb(h).map(v => a < 0 ? v * (1 + a) : v + (255 - v) * a); return 'rgb(' + c.map(v => Math.round(clamp(v, 0, 255))).join(',') + ')'; }
function rgba(h, a) { const c = rgb(h); return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }
MK.hash32 = hash32; MK.canon = canon;

// ---------- персонажи ----------
const KIND = {
  cat:    { body: '#f2a65a', belly: '#fff3e0', inner: '#f7b7c3', eyes: '#62b85a', nose: '#ee8a9e', stripe: '#c9692a' },
  dog:    { body: '#c8925c', belly: '#f6e6d0', inner: '#9c6438', eyes: '#4a2e1c', nose: '#2a1a12', stripe: '#9c6438' },
  bear:   { body: '#8f5d3b', belly: '#d9b48a', inner: '#d9b48a', eyes: '#2a1a12', nose: '#2a1a12', stripe: '#6d4329' },
  rabbit: { body: '#f4f1ee', belly: '#ffffff', inner: '#f7b7c3', eyes: '#6a3a2a', nose: '#f08ca0', stripe: '#d8d2cc' },
  mouse:  { body: '#a9a9b8', belly: '#ecebf2', inner: '#f6b2c0', eyes: '#2a2230', nose: '#f08ca0', stripe: '#8d8d9c' },
  fox:    { body: '#ea7a33', belly: '#fff6ea', inner: '#3a2418', eyes: '#7a4a1a', nose: '#2a1a12', stripe: '#3a2418' },
  pig:    { body: '#f7b9c4', belly: '#ffd6dd', inner: '#e58c9c', eyes: '#2a1a12', nose: '#ef97a8', stripe: '#e58c9c' },
  human:  { skin: '#f6c9a6', hair: '#5a3a22', shirt: '#3d8fe0', pants: '#33415c', shoes: '#2d2d2d', eyes: '#5a3a22' },
};
const NAME_KIND = { cat: 'кот', dog: 'пёс', bear: 'медведь', rabbit: 'заяц', mouse: 'мышь', fox: 'лиса', pig: 'поросёнок', human: 'человек' };
MK.KINDS = Object.keys(KIND);
MK.KIND_NAMES = NAME_KIND;

/** Внешность + голос → строгий код. Имя/описание в код не входят, остальное входит всё. */
function charLook(spec) {
  return { kind: spec.kind, age: spec.age || 'kid', height: spec.height || 1, colors: spec.colors || {},
    pattern: spec.pattern || [], acc: spec.acc || [], hair: spec.hair || null, outfit: spec.outfit || null, voice: spec.voice || {} };
}
MK.charCode = spec => spec.id + '-' + hash32(canon(charLook(spec))).toString(16).toUpperCase().padStart(8, '0').slice(0, 6);
MK.locCode = spec => spec.id + '-' + hash32(canon({ type: spec.type, time: spec.time || 'day', weather: spec.weather || 'none', seed: spec.seed || 1, opts: spec.opts || {} })).toString(16).toUpperCase().padStart(8, '0').slice(0, 6);

function normChar(spec) {
  const c = Object.assign({}, KIND[spec.kind] || KIND.cat, spec.colors || {});
  const human = spec.kind === 'human', adult = spec.age === 'adult' || spec.age === 'old';
  const P = human ? (adult
    ? { headR: .165, headCY: -.84, top: -.69, bot: -.37, tw: .125, hipY: -.37, legW: .075, shY: -.65, shX: .12, L1: .15, L2: .15, armW: .062 }
    : { headR: .235, headCY: -.75, top: -.53, bot: -.25, tw: .135, hipY: -.25, legW: .082, shY: -.5, shX: .115, L1: .1, L2: .1, armW: .066 })
    : (adult
    ? { headR: .25, headCY: -.73, bodyCY: -.34, rx: .17, ry: .2, hipY: -.2, legW: .09, shY: -.47, shX: .13, L1: .1, L2: .1, armW: .072 }
    : { headR: .27, headCY: -.69, bodyCY: -.31, rx: .155, ry: .165, hipY: -.19, legW: .085, shY: -.42, shX: .12, L1: .085, L2: .085, armW: .068 });
  return { spec, id: spec.id, name: spec.name || spec.id, kind: spec.kind || 'cat', human, adult, old: spec.age === 'old', c, P,
    pattern: spec.pattern || [], acc: spec.acc || [], hair: spec.hair || { style: 'short' }, outfit: spec.outfit || {},
    size: (spec.height || 1), seed: hash32(spec.id + (spec.kind || '')), ol: c.outline || '#2b1d16' };
}
MK.normChar = normChar;
MK.drawCharPublic = (ctx, spec, st, T) => drawChar(ctx, normChar(spec), st, T);

const LW = .013;
function ell(ctx, x, y, rx, ry, rot) { ctx.beginPath(); ctx.ellipse(x, y, Math.abs(rx), Math.abs(ry), rot || 0, 0, Math.PI * 2); }
function fillStroke(ctx, fill, ol, lw) { ctx.fillStyle = fill; ctx.fill(); if (ol) { ctx.lineWidth = lw || LW; ctx.strokeStyle = ol; ctx.stroke(); } }
function capsule(ctx, x1, y1, x2, y2, w, fill, ol) {
  ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
  ctx.strokeStyle = ol; ctx.lineWidth = w + LW * 2; ctx.stroke();
  ctx.strokeStyle = fill; ctx.lineWidth = w; ctx.stroke();
}
function limb(ctx, sx, sy, hx, hy, L1, L2, side, w, fill, ol, fill2) {
  let dx = hx - sx, dy = hy - sy, d = Math.hypot(dx, dy); const mx = (L1 + L2) * .995;
  if (d > mx) { hx = sx + dx / d * mx; hy = sy + dy / d * mx; d = mx; }
  const a = Math.atan2(dy, dx), b = Math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * Math.max(d, 1e-4)), -1, 1));
  const ex = sx + Math.cos(a - side * b) * L1, ey = sy + Math.sin(a - side * b) * L1;
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.lineTo(hx, hy);
  ctx.strokeStyle = ol; ctx.lineWidth = w + LW * 2; ctx.stroke();
  ctx.strokeStyle = fill; ctx.lineWidth = w; ctx.stroke();
  if (fill2) { ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.strokeStyle = fill2; ctx.lineWidth = w * 1.08; ctx.stroke(); }
  return [hx, hy];
}

/** Рисует персонажа. st: x,y(px), s(масштаб), face(-1..1), emo, act{n,p,t}, walk{ph,on}, talk, persist, prop, look */
function drawChar(ctx, ch, st, T) {
  const c = ch.c, P = ch.P, ol = ch.ol, S = UNIT * ch.size * (st.s || 1);
  const face = st.face, flip = face < 0 ? -1 : 1, fs = Math.abs(face) * .045; // сдвиг лица к направлению взгляда
  const act = st.act || {}, an = act.n, ap = act.p || 0, at = act.t || 0;
  const emo = st.emo || 'neutral';
  ctx.save();
  ctx.translate(st.x, st.y);
  // тень
  ctx.fillStyle = 'rgba(0,0,0,.18)'; ell(ctx, 0, 0, S * .2 * (1 - (st.lift || 0) * .5), S * .035); ctx.fill();
  ctx.scale(S, S);
  // общее движение тела
  let bob = Math.sin(T * 2.2 + ch.seed) * .006, lift = 0, rot = 0, sx = 1, sy = 1, jit = 0;
  const wk = st.walk || {};
  if (wk.on) { bob = -Math.abs(Math.sin(wk.ph)) * (wk.run ? .045 : .025); rot = (wk.run ? .1 : .045); }
  if (an === 'jump') { lift = Math.sin(ap * Math.PI) * .42; const sq = ap < .15 ? Math.sin(ap / .15 * Math.PI) : ap > .85 ? Math.sin((ap - .85) / .15 * Math.PI) : 0; sy = 1 - sq * .14 + (ap > .15 && ap < .85 ? .05 : 0); sx = 1 + sq * .1; }
  if (an === 'dance') { bob = -Math.abs(Math.sin(at * 7)) * .05; rot = Math.sin(at * 3.5) * .12; }
  if (an === 'laugh') { bob = -Math.abs(Math.sin(at * 16)) * .02; rot = Math.sin(at * 8) * .03; }
  if (an === 'scared' || emo === 'scared') jit = Math.sin(T * 63) * .006;
  if (an === 'spin') sx = Math.cos(ap * Math.PI * 2);
  if (an === 'bow') rot = 0;
  let fall = 0;
  if (st.persist === 'fallen') fall = ease((st.pt || 0) / .35);
  if (an === 'stand' && st.prev === 'fallen') fall = 1 - ease(ap);
  ctx.translate(jit, -lift);
  if (fall) ctx.rotate(-fall * 1.45 * 1);
  ctx.rotate(rot * (face === 0 ? 0 : 1) * .5);
  ctx.scale(flip * sx, sy);
  const sit = st.persist === 'sit' || st.persist === 'sleep' ? ease((st.pt || 0) / .4) : (an === 'stand' && (st.prev === 'sit' || st.prev === 'sleep') ? 1 - ease(ap) : 0);
  const down = sit * (-P.hipY * .62);
  ctx.translate(0, bob + down);

  // ----- хвост -----
  drawTail(ctx, ch, T, st, emo);
  // ----- ноги -----
  const legC = ch.human ? (ch.outfit.pants || c.pants) : c.body, footC = ch.human ? (ch.outfit.shoes || c.shoes) : (ch.pattern.includes('socks') ? c.belly : shade(c.body, -.05));
  for (let i = 0; i < 2; i++) {
    const side = i ? 1 : -1;
    let lx = side * (ch.human ? .062 : .068), fy = -P.hipY - down, fx = side * (ch.human ? .07 : .078), l = 0;
    if (wk.on) { const ph = wk.ph + i * Math.PI; l = Math.max(0, Math.sin(ph)) * (wk.run ? .1 : .065); fx += Math.cos(ph) * .02 * side; }
    if (an === 'dance') l = Math.max(0, Math.sin(at * 7 + i * Math.PI)) * .06;
    if (sit) { fy = -P.hipY * (1 - sit * .62) * 1 - down + sit * .0; fx = side * (.09 + sit * .03); }
    const hy = P.hipY;
    capsule(ctx, lx, hy, fx, hy + (fy - l) - .03, P.legW, legC, ol);
    ctx.save(); ell(ctx, fx + .015 * (face === 0 ? 0 : 1), hy + fy - l - .02, .06, .036); fillStroke(ctx, footC, ol); ctx.restore();
  }
  if (ch.human && ch.outfit.skirt) { ctx.beginPath(); ctx.moveTo(-P.tw * .95, P.bot - .02); ctx.lineTo(P.tw * .95, P.bot - .02); ctx.lineTo(P.tw * 1.4, P.bot + .1); ctx.lineTo(-P.tw * 1.4, P.bot + .1); ctx.closePath(); fillStroke(ctx, ch.outfit.skirt, ol); }

  // ----- тело -----
  if (ch.human) {
    const shirt = ch.outfit.shirt || c.shirt;
    ctx.beginPath(); ctx.moveTo(-P.tw * .82, P.top); ctx.quadraticCurveTo(0, P.top - .03, P.tw * .82, P.top);
    ctx.lineTo(P.tw, P.bot); ctx.quadraticCurveTo(0, P.bot + .025, -P.tw, P.bot); ctx.closePath(); fillStroke(ctx, shirt, ol);
    if (ch.outfit.stripe) { ctx.save(); ctx.clip(); ctx.fillStyle = ch.outfit.stripe; for (let k = 0; k < 4; k++) ctx.fillRect(-.3, P.top + .04 + k * .07, .6, .025); ctx.restore(); }
  } else {
    ctx.beginPath(); ctx.ellipse(0, P.bodyCY, P.rx, P.ry, 0, 0, Math.PI * 2); fillStroke(ctx, c.body, ol);
    ctx.save(); ctx.clip();
    if (ch.pattern.includes('stripes')) { ctx.strokeStyle = c.stripe; ctx.lineWidth = .028; ctx.lineCap = 'round';
      for (let k = 0; k < 3; k++) { const y = P.bodyCY - .1 + k * .07; ctx.beginPath(); ctx.moveTo(-P.rx - .01, y); ctx.quadraticCurveTo(-P.rx + .07, y + .02, -P.rx + .09, y + .045); ctx.stroke(); ctx.beginPath(); ctx.moveTo(P.rx + .01, y); ctx.quadraticCurveTo(P.rx - .07, y + .02, P.rx - .09, y + .045); ctx.stroke(); } }
    if (ch.pattern.includes('spots')) { const r = rng(ch.seed); ctx.fillStyle = c.stripe; for (let k = 0; k < 6; k++) { ell(ctx, (r() - .5) * P.rx * 2, P.bodyCY + (r() - .5) * P.ry * 1.6, .03 + r() * .025, .025 + r() * .02); ctx.fill(); } }
    if (!ch.pattern.includes('nobelly')) { ell(ctx, fs * .3, P.bodyCY + .03, P.rx * .62, P.ry * .7); ctx.fillStyle = c.belly; ctx.fill(); }
    ctx.restore();
  }
  // ----- руки -----
  const handC = ch.human ? c.skin : (ch.pattern.includes('socks') ? c.belly : c.body);
  const armC = ch.human ? (ch.outfit.shirt || c.shirt) : c.body;
  const reach = (P.L1 + P.L2) * .97;
  for (let i = 0; i < 2; i++) {
    const side = i ? 1 : -1, front = side === 1; // +x — сторона взгляда
    const sxp = side * P.shX, syp = P.shY;
    let a = .32 + Math.sin(T * 1.7 + i * 2 + ch.seed) * .04, hx, hy, bent = null;
    if (wk.on) a = .3 + Math.sin(wk.ph + (i ? 0 : Math.PI)) * (wk.run ? .55 : .3);
    if (an === 'wave' && front) a = 2.55 + Math.sin(at * 11) * .35;
    if (an === 'point' && front) a = 1.62;
    if (an === 'jump') a = .3 + Math.sin(ap * Math.PI) * 2.1;
    if (an === 'dance') a = (Math.sin(at * 3.5 + i * Math.PI) > 0 ? 2.6 : .8) + Math.sin(at * 7) * .15;
    if (an === 'spin') a = 1.4;
    if (an === 'scared' || emo === 'scared') bent = [side * .07, P.headCY + P.headR * .55];
    if (an === 'think' && front) bent = [fs + .03, P.headCY + P.headR * .78];
    if (an === 'clap') bent = [side * (.015 + Math.max(0, Math.sin(at * 14)) * .07), P.shY + .1];
    if (an === 'laugh') bent = [side * .1, P.bodyCY !== undefined ? P.bodyCY + .02 : P.bot - .06];
    if (an === 'cry' || emo === 'cry') bent = [side * .1, P.headCY + P.headR * .2];
    if (st.prop && front && !bent && an !== 'wave' && an !== 'point') { a = 1.0; }
    if (an === 'give' && front) a = lerp(1.0, 1.55, Math.sin(clamp(ap, 0, 1) * Math.PI));
    if (st.persist === 'sleep') a = .2;
    if (bent) { hx = bent[0]; hy = bent[1]; } else { hx = sxp + Math.sin(a) * reach * side; hy = syp + Math.cos(a) * reach; }
    const end = limb(ctx, sxp, syp, hx, hy, P.L1, P.L2, -side, P.armW, armC, ol, ch.human ? null : null);
    if (ch.human) { ell(ctx, end[0], end[1], .034, .034); fillStroke(ctx, handC, ol); }
    else { ell(ctx, end[0], end[1], .04, .036); fillStroke(ctx, handC, ol); }
    if (front) st._hand = end;
  }
  accBody(ctx, ch);
  // ----- голова -----
  ctx.save();
  let hdx = 0, hdy = 0, hrot = 0;
  if (an === 'nod') hdy = Math.max(0, Math.sin(at * 9)) * .03;
  if (an === 'shake') hdx = Math.sin(at * 13) * .03, hrot = Math.sin(at * 13) * .06;
  if (an === 'bow') hdy = Math.sin(clamp(ap, 0, 1) * Math.PI) * .07;
  if (st.persist === 'sleep') hrot = .25 * sit;
  if (an === 'dance') hrot = Math.sin(at * 3.5) * .1;
  ctx.translate(hdx, P.headCY + hdy); ctx.rotate(hrot);
  drawHead(ctx, ch, st, T, fs, emo, an, at);
  ctx.restore();
  // предмет в лапе
  if (st.prop && st._hand) drawProp(ctx, st.prop, st._hand[0] + .02, st._hand[1] + .02, .5, T, true);
  ctx.restore();
  // эффекты поверх (без зеркала)
  drawFx(ctx, ch, st, T, S, emo, an, at, P, lift, down, fall, flip, fs);
}

function drawTail(ctx, ch, T, st, emo) {
  const c = ch.c, ol = ch.ol, P = ch.P, k = ch.kind;
  if (ch.human || k === 'bear') { if (k === 'bear') { ell(ctx, -P.rx * .95, P.bodyCY + .08, .04, .04); fillStroke(ctx, c.body, ol); } return; }
  const happy = emo === 'happy' || emo === 'laugh' || emo === 'love';
  const sw = Math.sin(T * (k === 'dog' && happy ? 14 : 2.3) + ch.seed) * (k === 'dog' ? .5 : .25);
  const bx = -P.rx * .8, by = P.bodyCY + .1;
  ctx.save(); ctx.translate(bx, by); ctx.rotate(sw * .4);
  if (k === 'cat' || k === 'mouse') {
    const w = k === 'cat' ? .05 : .018, col = k === 'mouse' ? c.inner : c.body;
    ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(0, 0); ctx.bezierCurveTo(-.2, .02, -.24, -.18, -.16 + sw * .05, -.3);
    ctx.strokeStyle = ol; ctx.lineWidth = w + LW * 2; ctx.stroke(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke();
    if (k === 'cat' && ch.pattern.includes('stripes')) { ctx.setLineDash([.025, .035]); ctx.strokeStyle = c.stripe; ctx.lineWidth = w; ctx.stroke(); ctx.setLineDash([]); }
    if (k === 'cat' && ch.pattern.includes('tailtip')) { ell(ctx, -.16 + sw * .05, -.3, .03, .03); ctx.fillStyle = c.belly; ctx.fill(); }
  } else if (k === 'fox') {
    ctx.rotate(-.5); ell(ctx, -.16, -.06, .17, .075, -.4); fillStroke(ctx, c.body, ol);
    ctx.save(); ell(ctx, -.16, -.06, .17, .075, -.4); ctx.clip(); ell(ctx, -.31, -.12, .07, .07); ctx.fillStyle = c.belly; ctx.fill(); ctx.restore();
  } else if (k === 'dog') { ctx.rotate(-.9); capsule(ctx, 0, 0, -.13, -.05, .045, c.body, ol); }
  else if (k === 'rabbit') { ell(ctx, -.02, -.02, .055, .055); fillStroke(ctx, '#ffffff', ol); }
  else if (k === 'pig') { ctx.strokeStyle = ol; ctx.lineWidth = .014; ctx.beginPath(); for (let a = 0; a < 9; a++) { const r = .015 + a * .004; ctx.lineTo(-.03 - Math.cos(a) * r - a * .006, -Math.sin(a) * r); } ctx.stroke(); }
  ctx.restore();
}

function drawHead(ctx, ch, st, T, fs, emo, an, at) {
  const c = ch.c, ol = ch.ol, P = ch.P, R = P.headR, k = ch.kind;
  const skin = ch.human ? c.skin : c.body;
  // уши/волосы сзади
  if (ch.human) drawHairBack(ctx, ch, R);
  else drawEarsBack(ctx, ch, R, T);
  // голова
  if (ch.human) { ell(ctx, 0, 0, R * .98, R); fillStroke(ctx, skin, ol);
    ell(ctx, -R * .98 + fs * .3, R * .08, R * .13, R * .17); fillStroke(ctx, skin, ol); ell(ctx, R * .98 + fs * .3, R * .08, R * .13, R * .17); fillStroke(ctx, skin, ol);
    ell(ctx, 0, 0, R * .96, R * .98); ctx.fillStyle = skin; ctx.fill();
  } else { ell(ctx, 0, 0, R * 1.08, R * .94); fillStroke(ctx, skin, ol); }
  ctx.save(); ell(ctx, 0, 0, ch.human ? R * .98 : R * 1.08, ch.human ? R : R * .94); ctx.clip();
  if (!ch.human && ch.pattern.includes('stripes')) { ctx.fillStyle = c.stripe; for (let i = -1; i <= 1; i++) { ctx.beginPath(); ctx.moveTo(i * R * .22 - R * .05 + fs, -R * .95); ctx.lineTo(i * R * .22 + R * .05 + fs, -R * .95); ctx.lineTo(i * R * .16 + fs, -R * (.55 + (i === 0 ? -.05 : .08))); ctx.closePath(); ctx.fill(); }
    ctx.strokeStyle = c.stripe; ctx.lineWidth = R * .07; ctx.lineCap = 'round'; for (const s of [-1, 1]) for (let j = 0; j < 2; j++) { ctx.beginPath(); ctx.moveTo(s * R * 1.1, R * (.0 + j * .18)); ctx.lineTo(s * R * .82, R * (.04 + j * .18)); ctx.stroke(); } }
  if (!ch.human && ch.pattern.includes('mask')) { ctx.fillStyle = c.stripe; ell(ctx, -R * .36 + fs, -R * .02, R * .3, R * .22, .3); ctx.fill(); ell(ctx, R * .36 + fs, -R * .02, R * .3, R * .22, -.3); ctx.fill(); }
  if (!ch.human && ch.pattern.includes('patch')) { ctx.fillStyle = c.stripe; ell(ctx, R * .38 + fs, -R * .12, R * .3, R * .26); ctx.fill(); }
  ctx.restore();
  if (k === 'cat' || k === 'fox' || k === 'rabbit' || k === 'mouse') { ell(ctx, fs * 1.2, R * .45, R * .52, R * .34); ctx.fillStyle = k === 'cat' && !ch.pattern.includes('muzzle') ? rgba('#ffffff', 0) : c.belly; ctx.fill(); }
  if (k === 'cat' && ch.pattern.includes('muzzle')) { ell(ctx, fs * 1.2 - R * .17, R * .42, R * .22, R * .18); ctx.fillStyle = c.belly; ctx.fill(); ell(ctx, fs * 1.2 + R * .17, R * .42, R * .22, R * .18); ctx.fill(); }
  if (k === 'dog' || k === 'bear') { ell(ctx, fs * 1.2, R * .42, R * .42, R * .3); fillStroke(ctx, c.belly, ol, LW * .8); }
  if (k === 'pig') { ell(ctx, fs * 1.3, R * .36, R * .3, R * .21); fillStroke(ctx, c.nose, ol); ctx.fillStyle = shade(c.nose, -.45); ell(ctx, fs * 1.3 - R * .1, R * .36, R * .05, R * .08); ctx.fill(); ell(ctx, fs * 1.3 + R * .1, R * .36, R * .05, R * .08); ctx.fill(); }
  if (ch.human) drawHairFront(ctx, ch, R, fs);
  drawFace(ctx, ch, st, T, R, fs, emo, an, at);
  if (!ch.human) drawEarsFront(ctx, ch, R, T);
  drawAccHead(ctx, ch, R, fs);
}

function drawEarsBack(ctx, ch, R, T) {
  const c = ch.c, ol = ch.ol, k = ch.kind, tw = Math.sin(T * 1.3 + ch.seed) * .04;
  for (const s of [-1, 1]) {
    ctx.save();
    if (k === 'cat' || k === 'fox') {
      const big = k === 'fox' ? 1.25 : 1;
      ctx.translate(s * R * .62, -R * .62); ctx.rotate(s * (.32 + (s > 0 ? tw : 0)));
      ctx.beginPath(); ctx.moveTo(-R * .3 * big, R * .15); ctx.quadraticCurveTo(-R * .05, -R * .6 * big, 0, -R * .62 * big); ctx.quadraticCurveTo(R * .05, -R * .6 * big, R * .3 * big, R * .15); ctx.closePath(); fillStroke(ctx, c.body, ol);
      ctx.beginPath(); ctx.moveTo(-R * .16 * big, R * .05); ctx.quadraticCurveTo(0, -R * .42 * big, R * .16 * big, R * .05); ctx.closePath(); ctx.fillStyle = c.inner; ctx.fill();
    } else if (k === 'bear') { ell(ctx, s * R * .72, -R * .7, R * .26, R * .26); fillStroke(ctx, c.body, ol); ell(ctx, s * R * .72, -R * .68, R * .14, R * .14); ctx.fillStyle = c.inner; ctx.fill(); }
    else if (k === 'mouse') { ell(ctx, s * R * .85, -R * .62, R * .42, R * .42); fillStroke(ctx, c.body, ol); ell(ctx, s * R * .85, -R * .6, R * .27, R * .27); ctx.fillStyle = c.inner; ctx.fill(); }
    else if (k === 'rabbit') { ctx.translate(s * R * .33, -R * .7); ctx.rotate(s * (.12 + (s > 0 ? tw * 2 : 0))); ell(ctx, 0, -R * .6, R * .2, R * .66); fillStroke(ctx, c.body, ol); ell(ctx, 0, -R * .58, R * .1, R * .5); ctx.fillStyle = c.inner; ctx.fill(); }
    else if (k === 'pig') { ctx.translate(s * R * .6, -R * .7); ctx.rotate(s * .5); ctx.beginPath(); ctx.moveTo(-R * .22, R * .12); ctx.lineTo(0, -R * .32); ctx.lineTo(R * .22, R * .12); ctx.closePath(); fillStroke(ctx, c.body, ol); }
    ctx.restore();
  }
}
function drawEarsFront(ctx, ch, R, T) {
  if (ch.kind !== 'dog') return;
  const c = ch.c, ol = ch.ol, sw = Math.sin(T * 2 + ch.seed) * .05;
  for (const s of [-1, 1]) { ctx.save(); ctx.translate(s * R * .88, -R * .45); ctx.rotate(s * (.25 + sw)); ell(ctx, 0, R * .4, R * .2, R * .45); fillStroke(ctx, c.inner, ol); ctx.restore(); }
}
function drawHairBack(ctx, ch, R) {
  const h = ch.hair, col = h.color || (ch.old ? '#d9d9d9' : ch.c.hair), ol = ch.ol;
  if (h.style === 'long') { ell(ctx, 0, -R * .1, R * 1.06, R * .98); fillStroke(ctx, col, ol); for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(s * R * .7, -R * .4); ctx.quadraticCurveTo(s * R * 1.3, -R * .1, s * R * 1.15, R * 1.25); ctx.lineTo(s * R * .62, R * 1.2); ctx.quadraticCurveTo(s * R * .8, R * .5, s * R * .7, -R * .4); ctx.closePath(); fillStroke(ctx, col, ol); } }
  if (h.style === 'pigtails') for (const s of [-1, 1]) { ell(ctx, s * R * 1.12, R * .1, R * .3, R * .38, s * .3); fillStroke(ctx, col, ol); }
  if (h.style === 'bun') { ell(ctx, 0, -R * 1.08, R * .32, R * .28); fillStroke(ctx, col, ol); }
}
function drawHairFront(ctx, ch, R, fs) {
  const h = ch.hair, col = h.color || (ch.old ? '#d9d9d9' : ch.c.hair), ol = ch.ol;
  if (h.style === 'bald') { if (ch.old) { for (const s of [-1, 1]) { ell(ctx, s * R * .85, -R * .1, R * .2, R * .28); fillStroke(ctx, col, ol); } } return; }
  ctx.beginPath();
  if (h.style === 'curly') { for (let i = 0; i < 9; i++) { const a = Math.PI + i / 8 * Math.PI; ctx.moveTo(Math.cos(a) * R * .9 + R * .2, Math.sin(a) * R * .9); ctx.arc(Math.cos(a) * R * .9, Math.sin(a) * R * .9 - R * .05, R * .22, 0, Math.PI * 2); } fillStroke(ctx, col, ol); return; }
  ctx.moveTo(-R * 1.02, R * .05); ctx.quadraticCurveTo(-R * 1.08, -R * 1.12, 0, -R * 1.06); ctx.quadraticCurveTo(R * 1.08, -R * 1.12, R * 1.02, R * .05);
  ctx.quadraticCurveTo(R * .9, -R * .45, R * .35 + fs, -R * .52); ctx.quadraticCurveTo(R * .1 + fs, -R * .3, -R * .2 + fs, -R * .55); ctx.quadraticCurveTo(-R * .75, -R * .4, -R * 1.02, R * .05);
  fillStroke(ctx, col, ol);
}
function drawAccHead(ctx, ch, R, fs) {
  const ol = ch.ol;
  for (const a of ch.acc) {
    const t = typeof a === 'string' ? a : a.type, col = (a && a.color) || '#e8344e';
    if (t === 'bow') { ctx.save(); ctx.translate(R * .55, -R * .82); ctx.rotate(.3); for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(s * R * .3, -R * .16); ctx.lineTo(s * R * .3, R * .16); ctx.closePath(); fillStroke(ctx, col, ol); } ell(ctx, 0, 0, R * .07, R * .07); fillStroke(ctx, shade(col, -.15), ol); ctx.restore(); }
    if (t === 'hat') { ctx.beginPath(); ctx.moveTo(-R * .95, -R * .55); ctx.quadraticCurveTo(0, -R * 1.55, R * .95, -R * .55); ctx.closePath(); fillStroke(ctx, col, ol); ell(ctx, R * .55 + fs, -R * .55, R * .6, R * .12, -.08); fillStroke(ctx, shade(col, -.2), ol); }
    if (t === 'crown') { ctx.beginPath(); ctx.moveTo(-R * .45, -R * .8); for (let i = 0; i <= 4; i++) { ctx.lineTo(-R * .45 + i * R * .225, -R * (i % 2 ? 1.05 : 1.3)); } ctx.lineTo(R * .45, -R * .8); ctx.closePath(); fillStroke(ctx, '#ffd23f', ol); }
    if (t === 'glasses') { ctx.strokeStyle = ol; ctx.lineWidth = .014; for (const s of [-1, 1]) { ell(ctx, s * R * .36 + fs, -R * .02, R * .25, R * .22); ctx.stroke(); } ctx.beginPath(); ctx.moveTo(-R * .11 + fs, -R * .04); ctx.lineTo(R * .11 + fs, -R * .04); ctx.stroke(); }
    if (t === 'flower') { ctx.save(); ctx.translate(-R * .6, -R * .75); for (let i = 0; i < 5; i++) { ell(ctx, Math.cos(i * 1.256) * R * .12, Math.sin(i * 1.256) * R * .12, R * .09, R * .09); fillStroke(ctx, col, ol, LW * .6); } ell(ctx, 0, 0, R * .07, R * .07); ctx.fillStyle = '#ffd23f'; ctx.fill(); ctx.restore(); }
  }
}
function accBody(ctx, ch) {
  const ol = ch.ol, P = ch.P;
  for (const a of ch.acc) { const t = typeof a === 'string' ? a : a.type, col = (a && a.color) || '#e8344e';
    if (t === 'scarf') { const y = P.headCY + P.headR * .95; ctx.beginPath(); ell(ctx, 0, y, P.headR * .7, P.headR * .17); fillStroke(ctx, col, ol); capsule(ctx, -P.headR * .3, y, -P.headR * .42, y + .13, .05, col, ol); }
    if (t === 'collar') { const y = P.headCY + P.headR * .92; ell(ctx, 0, y, P.headR * .58, P.headR * .1); fillStroke(ctx, col, ol); ell(ctx, .02, y + P.headR * .14, P.headR * .1, P.headR * .1); fillStroke(ctx, '#ffd23f', ol); }
  }
}

function drawFace(ctx, ch, st, T, R, fs, emo, an, at) {
  const c = ch.c, ol = ch.ol, k = ch.kind, human = ch.human;
  const ex = R * (human ? .36 : .38), ey = human ? R * .02 : -R * .05, erx = R * (human ? .17 : .2), ery = R * (human ? .2 : .25);
  const ox = fs * 2.2; // лицо смещено к направлению
  // моргание
  const bp = 3.1 + (ch.seed % 17) / 10, bt = (T + (ch.seed % 7)) % bp; let blink = bt < .14 ? Math.sin(bt / .14 * Math.PI) : 0;
  let lid = 0, eyeS = 1, pup = 1, closedArc = false, look = st.lookY || 0;
  if (emo === 'sleepy') lid = .55;
  if (st.persist === 'sleep') closedArc = true;
  if (emo === 'laugh' || an === 'laugh') closedArc = true;
  if (emo === 'surprised') { eyeS = 1.15; pup = .7; blink = 0; }
  if (emo === 'scared') { eyeS = 1.1; pup = .55; }
  if (emo === 'shy') look = .35;
  if (emo === 'cry') lid = .25;
  if (emo === 'love') closedArc = false;
  const gx = (Math.abs(st.face) > .1 ? .28 : 0) * erx;
  for (const s of [-1, 1]) {
    const x = s * ex + ox, y = ey;
    if (closedArc || blink > .85) { ctx.strokeStyle = ol; ctx.lineWidth = .016; ctx.lineCap = 'round'; ctx.beginPath(); if (emo === 'laugh' || an === 'laugh') ctx.arc(x, y + ery * .3, erx * .8, Math.PI * 1.15, Math.PI * 1.85); else ctx.arc(x, y - ery * .2, erx * .8, Math.PI * .15, Math.PI * .85); ctx.stroke(); continue; }
    ctx.save(); ell(ctx, x, y, erx * eyeS, ery * eyeS * (1 - blink)); fillStroke(ctx, '#ffffff', ol, LW * .9); ctx.clip();
    if (emo === 'love') { drawHeart(ctx, x, y + ery * .1, erx * 1.1, '#e8344e'); }
    else {
      const ir = erx * .78 * pup, px = x + gx, py = y + ery * .12 + look * ery * .5;
      ell(ctx, px, py, ir, ir * 1.08); ctx.fillStyle = c.eyes; ctx.fill();
      ell(ctx, px, py, ir * .55, ir * .6); ctx.fillStyle = '#16100c'; ctx.fill();
      ell(ctx, px - ir * .35, py - ir * .4, ir * .3, ir * .3); ctx.fillStyle = '#fff'; ctx.fill();
      ell(ctx, px + ir * .3, py + ir * .3, ir * .14, ir * .14); ctx.fill();
    }
    if (lid > 0) { ctx.fillStyle = human ? c.skin : c.body; ctx.fillRect(x - erx * 1.3, y - ery * 1.3, erx * 2.6, ery * 2.6 * lid * .9); }
    if (emo === 'angry') { ctx.fillStyle = human ? c.skin : c.body; ctx.beginPath(); ctx.moveTo(x - s * erx * 1.3, y - ery * 1.3); ctx.lineTo(x + s * erx * 1.3, y - ery * 1.3); ctx.lineTo(x + s * erx * 1.3, y - ery * .1); ctx.closePath(); ctx.fill(); }
    if (emo === 'sad' || emo === 'cry') { ctx.fillStyle = human ? c.skin : c.body; ctx.beginPath(); ctx.moveTo(x - s * erx * 1.3, y - ery * 1.3); ctx.lineTo(x + s * erx * 1.3, y - ery * 1.3); ctx.lineTo(x - s * erx * 1.3, y - ery * .25); ctx.closePath(); ctx.fill(); }
    ctx.restore();
    if (lid > 0 || emo === 'angry' || emo === 'sad' || emo === 'cry') { ell(ctx, x, y, erx * eyeS, ery * eyeS); ctx.strokeStyle = ol; ctx.lineWidth = LW * .9; ctx.stroke(); }
  }
  // брови
  ctx.strokeStyle = human ? shade(ch.hair.color || c.hair, -.2) : shade(c.body, -.45); ctx.lineWidth = .017; ctx.lineCap = 'round';
  for (const s of [-1, 1]) {
    const x = s * ex + ox, y = ey - ery * 1.35; let d = 0, up = 0;
    if (emo === 'angry') d = ery * .32; if (emo === 'sad' || emo === 'cry' || emo === 'scared') d = -ery * .3; if (emo === 'surprised') up = ery * .35;
    ctx.beginPath(); ctx.moveTo(x - s * erx * .75, y - up + d); ctx.lineTo(x + s * erx * .75, y - up - d * .3);
    ctx.stroke();
  }
  // щёки
  ctx.fillStyle = emo === 'shy' || emo === 'love' ? 'rgba(240,90,110,.55)' : 'rgba(240,110,130,.28)';
  for (const s of [-1, 1]) { ell(ctx, s * R * .62 + ox * .8, R * .33, R * .14, R * .08); ctx.fill(); }
  // нос
  const ny = human ? R * .3 : R * .28, nx = ox * 1.1;
  if (human) { ctx.strokeStyle = shade(c.skin, -.35); ctx.lineWidth = .012; ctx.beginPath(); ctx.arc(nx, ny, R * .07, .3, Math.PI - .3); ctx.stroke(); }
  else if (k === 'dog' || k === 'bear' || k === 'fox') { ell(ctx, nx, ny + R * .02, R * .13, R * .09); fillStroke(ctx, c.nose, ol, LW * .7); ell(ctx, nx - R * .04, ny - R * .01, R * .04, R * .025); ctx.fillStyle = 'rgba(255,255,255,.6)'; ctx.fill(); }
  else if (k !== 'pig') { ctx.beginPath(); ctx.moveTo(nx - R * .085, ny - R * .03); ctx.lineTo(nx + R * .085, ny - R * .03); ctx.quadraticCurveTo(nx + R * .02, ny + R * .08, nx, ny + R * .08); ctx.quadraticCurveTo(nx - R * .02, ny + R * .08, nx - R * .085, ny - R * .03); fillStroke(ctx, c.nose, ol, LW * .7); }
  // усы
  if (k === 'cat' || k === 'mouse' || k === 'rabbit') { ctx.strokeStyle = rgba('#2b1d16', .55); ctx.lineWidth = .008; for (const s of [-1, 1]) for (let j = 0; j < 3; j++) { ctx.beginPath(); ctx.moveTo(nx + s * R * .3, ny + R * .1 + j * R * .07); ctx.lineTo(nx + s * R * (.85 + j * .03), ny + R * (.02 + j * .12)); ctx.stroke(); } }
  // рот
  const my = human ? R * .55 : R * .5, mx = ox * 1.1, talk = clamp(st.talk || 0, 0, 1);
  const smile = emo === 'happy' || emo === 'love' || emo === 'laugh' || emo === 'shy';
  const sad = emo === 'sad' || emo === 'cry' || emo === 'scared';
  ctx.strokeStyle = ol; ctx.lineWidth = .014; ctx.lineCap = 'round';
  let open = talk;
  if (emo === 'laugh' || an === 'laugh') open = Math.max(open, .55 + Math.sin(at * 16) * .25);
  if (emo === 'surprised') open = Math.max(open, .45);
  if (open > .06) {
    const w = R * (emo === 'surprised' ? .14 : .22 + (smile ? .06 : 0)), h = R * (.06 + open * .26);
    ctx.beginPath();
    if (smile) { ctx.moveTo(mx - w, my - h * .2); ctx.quadraticCurveTo(mx, my - h * .45, mx + w, my - h * .2); ctx.quadraticCurveTo(mx + w * .6, my + h * 1.1, mx, my + h * 1.05); ctx.quadraticCurveTo(mx - w * .6, my + h * 1.1, mx - w, my - h * .2); }
    else ctx.ellipse(mx, my + h * .3, w * .8, h * .75, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#6b1f24'; ctx.fill(); ctx.save(); ctx.clip(); ell(ctx, mx, my + h * 1.0, w * .55, h * .45); ctx.fillStyle = '#f0788a'; ctx.fill(); ctx.restore(); ctx.stroke();
  } else if (smile) { ctx.beginPath(); ctx.arc(mx, my - R * .1, R * .2, .35, Math.PI - .35); ctx.stroke(); }
  else if (sad) { ctx.beginPath(); ctx.arc(mx, my + R * .16, R * .14, Math.PI + .5, -.5); ctx.stroke(); }
  else if (emo === 'angry') { ctx.beginPath(); ctx.moveTo(mx - R * .12, my + R * .04); ctx.lineTo(mx + R * .12, my + R * .02); ctx.stroke(); }
  else if (k === 'cat' || k === 'mouse' || k === 'rabbit') { ctx.beginPath(); ctx.arc(mx - R * .07, my - R * .04, R * .07, .2, Math.PI - .2); ctx.moveTo(mx + R * .14, my - R * .04); ctx.arc(mx + R * .07, my - R * .04, R * .07, .2, Math.PI - .2); ctx.stroke(); }
  else { ctx.beginPath(); ctx.arc(mx, my - R * .06, R * .12, .5, Math.PI - .5); ctx.stroke(); }
  if (emo === 'cry') { ctx.fillStyle = 'rgba(110,180,255,.85)'; for (const s of [-1, 1]) { const ph = (T * 1.6 + (s > 0 ? .5 : 0)) % 1; drawDrop(ctx, s * ex + ox + s * erx * .4, ey + ery + ph * R * .7, R * .07); } }
}
function drawHeart(ctx, x, y, s, col) { ctx.beginPath(); ctx.moveTo(x, y + s * .55); ctx.bezierCurveTo(x - s * 1.1, y - s * .1, x - s * .55, y - s * .9, x, y - s * .35); ctx.bezierCurveTo(x + s * .55, y - s * .9, x + s * 1.1, y - s * .1, x, y + s * .55); ctx.fillStyle = col; ctx.fill(); }
function drawDrop(ctx, x, y, s) { ctx.beginPath(); ctx.moveTo(x, y - s); ctx.quadraticCurveTo(x + s * .8, y + s * .2, x, y + s * .6); ctx.quadraticCurveTo(x - s * .8, y + s * .2, x, y - s); ctx.fill(); }

function drawFx(ctx, ch, st, T, S, emo, an, at, P, lift, down, fall, flip, fs) {
  const hx = st.x + fs * S * flip, hy = st.y - lift * S + (P.headCY + down) * S, R = P.headR * S;
  ctx.save();
  ctx.font = `900 ${Math.round(R * .55)}px -apple-system, "SF Pro Rounded", "Arial Rounded MT Bold", "DejaVu Sans", sans-serif`; ctx.textAlign = 'center';
  if (st.persist === 'sleep') for (let i = 0; i < 3; i++) { const p = (T * .45 + i / 3) % 1; ctx.globalAlpha = Math.sin(p * Math.PI); ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#2b3a6a'; ctx.lineWidth = R * .06; const zx = hx + flip * R * (.7 + p * .8), zy = hy - R * (.6 + p * 1.6); ctx.strokeText('Z', zx, zy); ctx.fillText('Z', zx, zy); }
  if (st.persist === 'fallen' && (st.pt || 0) < 3.5) for (let i = 0; i < 4; i++) { const a = T * 4 + i * Math.PI / 2, cx = st.x - flip * S * .62 * fall, cy = st.y - S * .32 * (1 - fall) - S * .2; drawStar(ctx, cx + Math.cos(a) * R * .9, cy + Math.sin(a) * R * .3 - R * .3, R * .16, '#ffd23f'); }
  if (emo === 'love') for (let i = 0; i < 3; i++) { const p = (T * .5 + i / 3) % 1; ctx.globalAlpha = Math.sin(p * Math.PI); drawHeart(ctx, hx + Math.sin(i * 2 + T) * R * .9, hy - R * (1 + p * 1.5), R * .2, '#ff4d6d'); }
  ctx.globalAlpha = 1;
  if (emo === 'scared' || an === 'scared') { ctx.fillStyle = 'rgba(120,190,255,.9)'; drawDrop(ctx, hx + flip * R * 1.05, hy - R * .5, R * .14); }
  if (an === 'surprise' || (emo === 'surprised' && (st.et || 9) < 1.2)) { const k = clamp((st.et || 0) / .2, 0, 1); ctx.fillStyle = '#ffd23f'; ctx.strokeStyle = '#2b1d16'; ctx.lineWidth = R * .08; ctx.font = `900 ${Math.round(R * .9 * k)}px sans-serif`; ctx.strokeText('!', hx + flip * R * .9, hy - R * 1.1); ctx.fillText('!', hx + flip * R * .9, hy - R * 1.1); }
  if (emo === 'angry') { ctx.strokeStyle = '#e8344e'; ctx.lineWidth = R * .08; ctx.lineCap = 'round'; const ax = hx - flip * R * .8, ay = hy - R * .9, s = R * .14 * (1 + Math.sin(T * 9) * .15); for (const [a, b] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) { ctx.beginPath(); ctx.moveTo(ax + a * s * .4, ay + b * s * 1.2); ctx.quadraticCurveTo(ax + a * s * .4, ay + b * s * .4, ax + a * s * 1.2, ay + b * s * .4); ctx.stroke(); } }
  if (an === 'think') { const bx = hx + flip * R * 1.5, by = hy - R * 1.5, k = ease(at / .3);
    ctx.globalAlpha = k; ctx.fillStyle = '#fff'; ctx.strokeStyle = '#2b1d16'; ctx.lineWidth = R * .05;
    for (const [dx, dy, r] of [[.55, .9, .1], [.3, .55, .15]]) { ell(ctx, hx + flip * R * (1 + dx * .2), hy - R * dy, R * r, R * r); ctx.fill(); ctx.stroke(); }
    ell(ctx, bx, by, R * .9, R * .55); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#2b1d16'; ctx.font = `800 ${Math.round(R * .38)}px -apple-system, "DejaVu Sans", sans-serif`; ctx.textBaseline = 'middle'; ctx.fillText(st.thinkText || '?', bx, by + R * .02); ctx.globalAlpha = 1; }
  ctx.restore();
}
function drawStar(ctx, x, y, r, col) { ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * .45 : r; ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } ctx.closePath(); ctx.fillStyle = col; ctx.fill(); ctx.strokeStyle = '#2b1d16'; ctx.lineWidth = r * .15; ctx.stroke(); }

// ---------- предметы ----------
const PROPS = ['ball', 'apple', 'fish', 'box', 'gift', 'flower', 'book', 'star', 'cake', 'bone', 'carrot', 'cheese', 'balloon', 'key', 'cup'];
MK.PROPS = PROPS;
function drawProp(ctx, p, x, y, s, T, inHand) {
  const t = p.type || p, col = p.color, ol = '#2b1d16';
  ctx.save(); ctx.translate(x, y); ctx.scale(s * (inHand ? .22 : .42), s * (inHand ? .22 : .42)); ctx.lineWidth = .06; ctx.lineJoin = 'round';
  const F = (c) => { ctx.fillStyle = c; ctx.fill(); ctx.strokeStyle = ol; ctx.stroke(); };
  switch (t) {
    case 'ball': ell(ctx, 0, -.5, .5, .5); F(col || '#e8344e'); ctx.save(); ell(ctx, 0, -.5, .5, .5); ctx.clip(); ctx.fillStyle = '#fff'; ctx.fillRect(-.6, -.62, 1.2, .22); ctx.restore(); ell(ctx, -.18, -.72, .1, .07); ctx.fillStyle = 'rgba(255,255,255,.7)'; ctx.fill(); break;
    case 'apple': ell(ctx, 0, -.42, .42, .4); F(col || '#e23b3b'); ctx.beginPath(); ctx.moveTo(0, -.8); ctx.lineTo(.05, -1.0); ctx.strokeStyle = ol; ctx.lineWidth = .08; ctx.stroke(); ell(ctx, .17, -.95, .14, .07, -.5); F('#5fbf4a'); break;
    case 'fish': ell(ctx, 0, -.35, .5, .25); F(col || '#7fb3ff'); ctx.beginPath(); ctx.moveTo(.45, -.35); ctx.lineTo(.8, -.6); ctx.lineTo(.8, -.1); ctx.closePath(); F(col || '#7fb3ff'); ell(ctx, -.28, -.4, .06, .06); ctx.fillStyle = ol; ctx.fill(); break;
    case 'box': ctx.beginPath(); ctx.rect(-.5, -.9, 1, .9); F(col || '#c9944f'); ctx.beginPath(); ctx.moveTo(-.5, -.6); ctx.lineTo(.5, -.6); ctx.stroke(); break;
    case 'gift': ctx.beginPath(); ctx.rect(-.5, -.85, 1, .85); F(col || '#8d5cf6'); ctx.fillStyle = '#ffd23f'; ctx.fillRect(-.09, -.85, .18, .85); ctx.fillRect(-.5, -.55, 1, .16); for (const s2 of [-1, 1]) { ell(ctx, s2 * .18, -.98, .18, .12, s2 * .4); F('#ffd23f'); } break;
    case 'flower': ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -.9); ctx.strokeStyle = '#3f9a3a'; ctx.lineWidth = .1; ctx.stroke(); ctx.lineWidth = .06; for (let i = 0; i < 6; i++) { ell(ctx, Math.cos(i) * .2, -1 + Math.sin(i) * .2, .15, .15); F(col || '#ff7ab8'); } ell(ctx, 0, -1, .12, .12); F('#ffd23f'); break;
    case 'book': ctx.beginPath(); ctx.rect(-.45, -.75, .9, .65); F(col || '#2f7de1'); ctx.fillStyle = '#fff'; ctx.fillRect(-.4, -.18, .8, .07); break;
    case 'star': drawStar(ctx, 0, -.5, .5, col || '#ffd23f'); break;
    case 'cake': ctx.beginPath(); ctx.rect(-.5, -.6, 1, .6); F('#f7d6a8'); ctx.beginPath(); ctx.rect(-.5, -.7, 1, .2); F(col || '#ff8fb1'); ctx.beginPath(); ctx.rect(-.04, -1, .08, .3); F('#7fb3ff'); ell(ctx, 0, -1.08, .06, .1); ctx.fillStyle = '#ffb703'; ctx.fill(); break;
    case 'bone': ctx.beginPath(); ctx.rect(-.4, -.4, .8, .16); F('#fff7e8'); for (const s2 of [-1, 1]) for (const d of [-.1, .1]) { ell(ctx, s2 * .45, -.32 + d, .12, .12); F('#fff7e8'); } break;
    case 'carrot': ctx.beginPath(); ctx.moveTo(-.18, -.9); ctx.lineTo(.18, -.9); ctx.lineTo(0, 0); ctx.closePath(); F(col || '#ff8a1f'); ctx.beginPath(); ctx.moveTo(0, -.9); ctx.lineTo(-.15, -1.2); ctx.moveTo(0, -.9); ctx.lineTo(.15, -1.2); ctx.strokeStyle = '#3f9a3a'; ctx.lineWidth = .1; ctx.stroke(); break;
    case 'cheese': ctx.beginPath(); ctx.moveTo(-.5, 0); ctx.lineTo(.5, 0); ctx.lineTo(.5, -.45); ctx.lineTo(-.5, -.15); ctx.closePath(); F(col || '#ffd23f'); ell(ctx, .2, -.18, .08, .07); ctx.fillStyle = '#e0a800'; ctx.fill(); break;
    case 'balloon': { const sw = Math.sin(T * 1.5) * .1; ctx.beginPath(); ctx.moveTo(0, 0); ctx.quadraticCurveTo(sw, -1, sw * .5, -1.8); ctx.strokeStyle = ol; ctx.lineWidth = .04; ctx.stroke(); ctx.lineWidth = .06; ell(ctx, sw * .5, -2.3, .42, .52); F(col || '#ff4d6d'); break; }
    case 'key': ell(ctx, -.3, -.4, .2, .2); F(col || '#ffd23f'); ctx.beginPath(); ctx.rect(-.1, -.46, .6, .12); F(col || '#ffd23f'); break;
    case 'cup': ctx.beginPath(); ctx.moveTo(-.35, -.7); ctx.lineTo(.35, -.7); ctx.lineTo(.28, 0); ctx.lineTo(-.28, 0); ctx.closePath(); F(col || '#fff'); ctx.beginPath(); ctx.arc(.4, -.4, .15, -1.4, 1.4); ctx.stroke(); break;
    default: ell(ctx, 0, -.4, .4, .4); F(col || '#ccc');
  }
  ctx.restore();
}

// ---------- декорации ----------
const SKY = { day: ['#5fb2ee', '#cdeeff'], evening: ['#5a4fa8', '#ffb07a'], night: ['#08103a', '#2a3a7a'] };
MK.LOC_TYPES = ['forest', 'meadow', 'yard', 'room', 'kitchen', 'street', 'beach', 'winter', 'space', 'playground'];
MK.LOC_NAMES = { forest: 'лес', meadow: 'луг', yard: 'двор у дома', room: 'комната', kitchen: 'кухня', street: 'улица города', beach: 'пляж', winter: 'зимний лес', space: 'космос', playground: 'детская площадка' };
const X0 = -W * .25, XW = W * 1.5;

function tree(ctx, x, y, s, col, trunk, kind) {
  ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(30,40,20,.35)';
  ctx.fillStyle = trunk; ctx.beginPath(); ctx.moveTo(x - 12 * s, y); ctx.lineTo(x - 7 * s, y - 120 * s); ctx.lineTo(x + 7 * s, y - 120 * s); ctx.lineTo(x + 12 * s, y); ctx.closePath(); ctx.fill();
  if (kind === 'fir') { for (let i = 0; i < 3; i++) { ctx.beginPath(); const yy = y - 70 * s - i * 55 * s, w = (95 - i * 22) * s; ctx.moveTo(x - w, yy); ctx.lineTo(x, yy - 110 * s); ctx.lineTo(x + w, yy); ctx.closePath(); ctx.fillStyle = col; ctx.fill(); ctx.stroke(); } return; }
  const r = 70 * s; ctx.fillStyle = col;
  for (const [dx, dy, k] of [[-.6, -1.7, .8], [.6, -1.75, .8], [0, -2.3, 1], [-.2, -1.6, .9], [.35, -2.0, .85]]) { ell(ctx, x + dx * r, y + dy * r - 40 * s, r * k, r * k * .92); ctx.fill(); }
  ctx.fillStyle = 'rgba(255,255,255,.12)'; ell(ctx, x - .3 * r, y - 2.5 * r - 40 * s, r * .5, r * .35); ctx.fill();
}
function cloud(ctx, x, y, s, col) { ctx.fillStyle = col || 'rgba(255,255,255,.95)'; for (const [dx, dy, r] of [[0, 0, 50], [45, -18, 42], [90, 0, 46], [45, 12, 50], [-40, 8, 34], [130, 10, 30]]) { ell(ctx, x + dx * s, y + dy * s, r * s, r * s * .85); ctx.fill(); } }
function hills(ctx, r, y, amp, col, n) { ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(X0, H); ctx.lineTo(X0, y); const ph = r() * 10; for (let i = 0; i <= 60; i++) { const x = X0 + XW * i / 60; ctx.lineTo(x, y - Math.sin(i / 60 * Math.PI * n + ph) * amp - Math.sin(i / 60 * Math.PI * n * 2.3 + ph) * amp * .3); } ctx.lineTo(X0 + XW, H); ctx.closePath(); ctx.fill(); }
function grassGround(ctx, r, top, c1, c2) { const g = ctx.createLinearGradient(0, top, 0, H); g.addColorStop(0, c1); g.addColorStop(1, c2); ctx.fillStyle = g; ctx.fillRect(X0, top, XW, H - top); ctx.strokeStyle = shade(c1, -.15); ctx.lineWidth = 3; for (let i = 0; i < 260; i++) { const x = X0 + r() * XW, y = top + 10 + r() * (H - top); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 4, y - 10 - r() * 8); ctx.moveTo(x, y); ctx.lineTo(x + 4, y - 9 - r() * 8); ctx.stroke(); } }
function flowers(ctx, r, top, n) { const cols = ['#ff6fa8', '#ffd23f', '#ffffff', '#a974ff', '#ff8a3d']; for (let i = 0; i < n; i++) { const x = X0 + r() * XW, y = top + 15 + r() * (H - top - 20), c = cols[(r() * cols.length) | 0], s = 5 + r() * 4; ctx.fillStyle = c; for (let k = 0; k < 5; k++) { ell(ctx, x + Math.cos(k * 1.26) * s, y + Math.sin(k * 1.26) * s, s * .7, s * .7); ctx.fill(); } ctx.fillStyle = '#ffb703'; ell(ctx, x, y, s * .5, s * .5); ctx.fill(); } }
function house(ctx, x, y, s, wall, roof, lit) {
  const w = 420 * s, h = 300 * s; ctx.lineWidth = 6; ctx.strokeStyle = '#3a2a22';
  ctx.fillStyle = wall; ctx.fillRect(x - w / 2, y - h, w, h); ctx.strokeRect(x - w / 2, y - h, w, h);
  ctx.beginPath(); ctx.moveTo(x - w / 2 - 40 * s, y - h); ctx.lineTo(x, y - h - 210 * s); ctx.lineTo(x + w / 2 + 40 * s, y - h); ctx.closePath(); ctx.fillStyle = roof; ctx.fill(); ctx.stroke();
  ctx.fillStyle = shade(roof, -.2); ctx.fillRect(x + 90 * s, y - h - 170 * s, 50 * s, 90 * s); ctx.strokeRect(x + 90 * s, y - h - 170 * s, 50 * s, 90 * s);
  ctx.fillStyle = '#8a5a3a'; ctx.fillRect(x - 45 * s, y - 170 * s, 90 * s, 170 * s); ctx.strokeRect(x - 45 * s, y - 170 * s, 90 * s, 170 * s); ctx.fillStyle = '#ffd23f'; ell(ctx, x + 28 * s, y - 85 * s, 7 * s, 7 * s); ctx.fill();
  for (const dx of [-140, 140]) { ctx.fillStyle = lit ? '#ffe28a' : '#9fd6ff'; ctx.fillRect(x + dx * s - 50 * s, y - 220 * s, 100 * s, 90 * s); ctx.strokeRect(x + dx * s - 50 * s, y - 220 * s, 100 * s, 90 * s); ctx.beginPath(); ctx.moveTo(x + dx * s, y - 220 * s); ctx.lineTo(x + dx * s, y - 130 * s); ctx.moveTo(x + dx * s - 50 * s, y - 175 * s); ctx.lineTo(x + dx * s + 50 * s, y - 175 * s); ctx.stroke(); ctx.fillStyle = '#ff8fa3'; ctx.fillRect(x + dx * s - 56 * s, y - 228 * s, 112 * s, 16 * s); }
  ctx.fillStyle = 'rgba(0,0,0,.08)'; ctx.fillRect(x - w / 2, y - 20 * s, w, 20 * s);
}
function fence(ctx, y, col) { ctx.fillStyle = col; ctx.strokeStyle = shade(col, -.35); ctx.lineWidth = 3; ctx.fillRect(X0, y - 70, XW, 14); ctx.fillRect(X0, y - 30, XW, 14); for (let x = X0; x < X0 + XW; x += 46) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - 95); ctx.lineTo(x + 15, y - 110); ctx.lineTo(x + 30, y - 95); ctx.lineTo(x + 30, y); ctx.closePath(); ctx.fill(); ctx.stroke(); } }
function bush(ctx, x, y, s, col) { ctx.fillStyle = col; for (const [dx, dy, r] of [[-40, -20, 40], [0, -38, 48], [42, -22, 40]]) { ell(ctx, x + dx * s, y + dy * s, r * s, r * s * .9); ctx.fill(); } ctx.fillStyle = 'rgba(255,255,255,.1)'; ell(ctx, x - 10 * s, y - 60 * s, 22 * s, 12 * s); ctx.fill(); }

/** Описание слоёв декорации: [{p, draw(ctx)}], p — глубина (0 — небо, 1 — земля с персонажами, >1 — передний план) */
function buildLocation(loc) {
  const type = loc.type || 'meadow', time = loc.time || 'day', seed = hash32(String(loc.seed || 1) + type), night = time === 'night', eve = time === 'evening';
  const L = []; const add = (p, fn) => L.push({ p, fn, seed: seed + L.length * 101 });
  const gTop = GROUND - 70;
  const green = night ? '#2f6b45' : eve ? '#6aa84f' : '#79c95a', green2 = night ? '#1f4a33' : eve ? '#4f8f3a' : '#4fa63f';
  if (type === 'forest' || type === 'meadow' || type === 'winter' || type === 'playground') {
    const snow = type === 'winter';
    add(.12, (c, r) => { hills(c, r, H * .55, 60, snow ? '#dfe9f5' : night ? '#24345f' : eve ? '#8a7fb8' : '#a8d4f0', 3); });
    add(.3, (c, r) => { hills(c, r, H * .62, 45, snow ? '#eef4fb' : night ? '#244a3f' : eve ? '#7aa36a' : '#98d07a', 4); if (type !== 'meadow') for (let i = 0; i < 22; i++) tree(c, X0 + r() * XW, H * .66 + r() * 20, .55 + r() * .3, snow ? '#3d7a5a' : night ? '#1f4a33' : '#4e9a4a', '#6b4a32', snow || r() < .3 ? 'fir' : 'round'); });
    if (type === 'forest' || type === 'winter') add(.6, (c, r) => { for (let i = 0; i < 9; i++) { const x = X0 + (i + .2 + r() * .6) * XW / 9; tree(c, x, gTop + 10, .95 + r() * .4, snow ? '#2f6a4c' : night ? '#1c4a30' : '#3f8f3f', '#5d3e2a', snow || r() < .3 ? 'fir' : 'round'); if (snow) { c.fillStyle = '#fff'; for (let k = 0; k < 3; k++) { ell(c, x - 20 + k * 20, gTop - 100 - k * 55, 40 - k * 9, 10); c.fill(); } } } });
    if (type === 'playground') add(.75, (c, r) => { // качели и горка
      c.lineWidth = 10; c.strokeStyle = '#e8344e'; c.lineCap = 'round'; const sx = W * .22, y = gTop + 20; c.beginPath(); c.moveTo(sx - 160, y); c.lineTo(sx - 110, y - 300); c.lineTo(sx + 110, y - 300); c.lineTo(sx + 160, y); c.stroke();
      c.lineWidth = 4; c.strokeStyle = '#555'; for (const d of [-55, 55]) { c.beginPath(); c.moveTo(sx + d - 25, y - 300); c.lineTo(sx + d - 25, y - 90); c.moveTo(sx + d + 25, y - 300); c.lineTo(sx + d + 25, y - 90); c.stroke(); c.fillStyle = '#ffd23f'; c.fillRect(sx + d - 35, y - 95, 70, 14); }
      const gx = W * .8; c.fillStyle = '#3d8fe0'; c.fillRect(gx - 120, y - 260, 120, 18); c.lineWidth = 8; c.strokeStyle = '#2f6fb8'; c.beginPath(); c.moveTo(gx - 120, y); c.lineTo(gx - 120, y - 260); c.moveTo(gx, y); c.lineTo(gx, y - 260); c.stroke(); for (let k = 0; k < 6; k++) { c.beginPath(); c.moveTo(gx - 120, y - 40 - k * 40); c.lineTo(gx - 100, y - 40 - k * 40); c.stroke(); }
      c.fillStyle = '#ff8a1f'; c.beginPath(); c.moveTo(gx, y - 260); c.quadraticCurveTo(gx + 140, y - 200, gx + 230, y); c.lineTo(gx + 190, y); c.quadraticCurveTo(gx + 110, y - 190, gx, y - 225); c.closePath(); c.fill(); c.strokeStyle = '#a5520c'; c.lineWidth = 4; c.stroke();
      c.fillStyle = '#f1d38a'; ell(c, W * .5, y + 40, 220, 40); c.fill(); });
    add(1, (c, r) => { if (snow) { const g = c.createLinearGradient(0, gTop, 0, H); g.addColorStop(0, '#f4f8ff'); g.addColorStop(1, '#d6e4f5'); c.fillStyle = g; c.fillRect(X0, gTop, XW, H - gTop); c.fillStyle = 'rgba(160,190,230,.35)'; for (let i = 0; i < 30; i++) { ell(c, X0 + r() * XW, gTop + 30 + r() * (H - gTop), 40 + r() * 60, 6); c.fill(); } }
      else { grassGround(c, r, gTop, green, green2); if (type === 'forest') { c.fillStyle = night ? '#6b5a3a' : '#d9b77a'; c.beginPath(); c.moveTo(X0, GROUND + 30); c.bezierCurveTo(W * .3, GROUND - 20, W * .7, GROUND + 60, X0 + XW, GROUND); c.lineTo(X0 + XW, GROUND + 60); c.bezierCurveTo(W * .7, GROUND + 120, W * .3, GROUND + 40, X0, GROUND + 90); c.closePath(); c.fill(); }
        flowers(c, r, gTop, type === 'meadow' ? 140 : 50);
        if (type === 'forest') for (let i = 0; i < 6; i++) { const x = X0 + r() * XW, y = gTop + 20 + r() * 60; c.fillStyle = '#f2eadf'; c.fillRect(x - 5, y - 18, 10, 18); c.fillStyle = '#e8344e'; ell(c, x, y - 20, 18, 11); c.fill(); c.fillStyle = '#fff'; ell(c, x - 5, y - 23, 3, 3); c.fill(); } } });
    if (type === 'winter') add(.92, (c) => { const x = W * .78, y = gTop + 30; c.fillStyle = '#fff'; c.strokeStyle = '#9fb7d8'; c.lineWidth = 4; for (const [dy, r] of [[-60, 70], [-170, 52], [-250, 38]]) { ell(c, x, y + dy, r, r); c.fill(); c.stroke(); } c.fillStyle = '#ff8a1f'; c.beginPath(); c.moveTo(x, y - 250); c.lineTo(x + 50, y - 244); c.lineTo(x, y - 238); c.fill(); c.fillStyle = '#222'; ell(c, x - 12, y - 262, 5, 5); c.fill(); ell(c, x + 12, y - 262, 5, 5); c.fill(); });
    add(1.25, (c, r) => { for (let i = 0; i < 5; i++) bush(c, X0 + r() * XW, H + 30, 1.4 + r() * .6, snow ? '#e8f0fa' : night ? '#173a27' : '#3c8f37'); });
  } else if (type === 'yard') {
    add(.25, (c, r) => { hills(c, r, H * .6, 30, night ? '#24345f' : '#a8d4f0', 3); for (let i = 0; i < 14; i++) tree(c, X0 + r() * XW, H * .64, .5 + r() * .2, night ? '#1f4a33' : '#5aa553', '#6b4a32'); });
    add(.7, (c) => { house(c, W * .3, gTop + 20, 1.15, '#f6d7a7', '#d9534f', night); tree(c, W * .78, gTop + 20, 1.2, night ? '#1f4a33' : '#4e9a4a', '#6b4a32'); });
    add(.85, (c) => fence(c, gTop + 40, night ? '#a08868' : '#e8c48a'));
    add(1, (c, r) => { grassGround(c, r, gTop + 30, green, green2); c.fillStyle = '#d8c3a0'; c.beginPath(); c.moveTo(W * .26, gTop + 30); c.lineTo(W * .34, gTop + 30); c.lineTo(W * .5, H); c.lineTo(W * .1, H); c.closePath(); c.fill(); flowers(c, r, gTop + 30, 40); });
    add(1.25, (c, r) => { bush(c, -60, H + 30, 1.8, night ? '#173a27' : '#3c8f37'); bush(c, W + 80, H + 40, 2, night ? '#173a27' : '#3c8f37'); });
  } else if (type === 'room' || type === 'kitchen') {
    const wallTop = GROUND - 120; const kit = type === 'kitchen';
    add(.85, (c, r) => {
      c.fillStyle = kit ? '#f3efe6' : (loc.opts && loc.opts.wall) || '#f7e3c4'; c.fillRect(X0, 0, XW, wallTop);
      if (kit) { c.strokeStyle = 'rgba(120,140,170,.35)'; c.lineWidth = 2; for (let y = wallTop - 360; y < wallTop; y += 40) { c.beginPath(); c.moveTo(X0, y); c.lineTo(X0 + XW, y); c.stroke(); } for (let x = X0; x < X0 + XW; x += 40) { c.beginPath(); c.moveTo(x, wallTop - 360); c.lineTo(x, wallTop); c.stroke(); } }
      else { c.fillStyle = 'rgba(214,150,110,.22)'; for (let y = 20; y < wallTop; y += 70) for (let x = X0 + ((y / 70) % 2) * 35; x < X0 + XW; x += 70) { ell(c, x, y, 9, 9); c.fill(); } }
      // окно
      const wx = W * (kit ? .5 : .62), wy = 160; const sky = SKY[time]; const g = c.createLinearGradient(0, wy, 0, wy + 330); g.addColorStop(0, sky[0]); g.addColorStop(1, sky[1]); c.fillStyle = g; c.fillRect(wx - 170, wy, 340, 330);
      if (night) { c.fillStyle = '#fff6c8'; ell(c, wx + 80, wy + 80, 32, 32); c.fill(); } else cloud(c, wx - 60, wy + 110, .7);
      c.strokeStyle = '#fff'; c.lineWidth = 22; c.strokeRect(wx - 170, wy, 340, 330); c.lineWidth = 12; c.beginPath(); c.moveTo(wx, wy); c.lineTo(wx, wy + 330); c.moveTo(wx - 170, wy + 160); c.lineTo(wx + 170, wy + 160); c.stroke();
      c.fillStyle = kit ? '#9ad0c2' : '#e86a5f'; c.fillRect(wx - 230, wy - 30, 80, 400); c.fillRect(wx + 150, wy - 30, 80, 400); c.fillStyle = shade(kit ? '#9ad0c2' : '#e86a5f', -.25); c.fillRect(wx - 245, wy - 40, 490, 18);
      if (kit) { // шкафы
        c.lineWidth = 5; c.strokeStyle = '#6b4a32'; for (const [x0, x1] of [[X0 + 100, wx - 270], [wx + 270, X0 + XW - 100]]) { c.fillStyle = '#7fc4a4'; c.fillRect(x0, 60, x1 - x0, 230); c.strokeRect(x0, 60, x1 - x0, 230); for (let x = x0; x < x1 - 10; x += 150) { c.strokeRect(x + 10, 72, 130, 206); c.fillStyle = '#e6e6e6'; ell(c, x + 120, 175, 6, 12); c.fill(); } }
        c.fillStyle = '#fafafa'; c.fillRect(W * .86, wallTop - 520, 220, 520); c.strokeRect(W * .86, wallTop - 520, 220, 520); c.beginPath(); c.moveTo(W * .86, wallTop - 330); c.lineTo(W * .86 + 220, wallTop - 330); c.stroke(); c.fillStyle = '#bbb'; c.fillRect(W * .86 + 20, wallTop - 470, 12, 90); c.fillRect(W * .86 + 20, wallTop - 300, 12, 120);
        c.fillStyle = '#7fc4a4'; c.fillRect(X0 + 100, wallTop - 230, W * .7 - X0 - 100 + 120, 230); c.strokeRect(X0 + 100, wallTop - 230, W * .7 - X0 - 100 + 120, 230); c.fillStyle = '#d9c7a8'; c.fillRect(X0 + 90, wallTop - 250, W * .7 - X0 - 100 + 140, 22); c.strokeRect(X0 + 90, wallTop - 250, W * .7 - X0 - 100 + 140, 22);
        c.fillStyle = '#333'; c.fillRect(W * .12, wallTop - 252, 200, 8); c.fillStyle = '#c0c0c0'; ell(c, W * .12 + 100, wallTop - 270, 70, 22); c.fill(); c.stroke();
      } else {
        c.lineWidth = 6; c.strokeStyle = '#6b4a32'; c.fillStyle = '#a8d8ff'; c.fillRect(W * .2, 170, 220, 160); c.strokeRect(W * .2, 170, 220, 160); c.fillStyle = '#79c95a'; c.beginPath(); c.moveTo(W * .2, 330); c.lineTo(W * .2 + 90, 250); c.lineTo(W * .2 + 220, 330); c.fill(); c.fillStyle = '#ffd23f'; ell(c, W * .2 + 170, 215, 22, 22); c.fill();
        c.fillStyle = '#8a5a3a'; c.fillRect(W * .02, 420, 300, 16); for (let i = 0; i < 8; i++) { c.fillStyle = ['#e8344e', '#3d8fe0', '#ffd23f', '#5fbf4a'][i % 4]; c.fillRect(W * .02 + 20 + i * 32, 420 - 70 - (i % 3) * 8, 26, 70 + (i % 3) * 8); }
      }
      c.fillStyle = '#8a5a3a'; c.fillRect(X0, wallTop - 20, XW, 22);
    });
    add(1, (c, r) => { const g = c.createLinearGradient(0, wallTop, 0, H); g.addColorStop(0, kit ? '#d8c4a0' : '#c88a55'); g.addColorStop(1, kit ? '#b9a07a' : '#a8683a'); c.fillStyle = g; c.fillRect(X0, wallTop, XW, H - wallTop);
      c.strokeStyle = 'rgba(70,40,20,.25)'; c.lineWidth = 3; for (let y = wallTop + 25; y < H; y += 32 + (y - wallTop) * .12) { c.beginPath(); c.moveTo(X0, y); c.lineTo(X0 + XW, y); c.stroke(); }
      if (!kit) { c.fillStyle = '#4e7fc9'; ell(c, W * .5, GROUND + 25, 520, 70); c.fill(); c.strokeStyle = '#f2c94c'; c.lineWidth = 8; ell(c, W * .5, GROUND + 25, 470, 55); c.stroke(); } });
    if (!kit) add(.93, (c) => { const x = W * .86, y = GROUND - 40; c.lineWidth = 6; c.strokeStyle = '#3a2a22'; c.fillStyle = '#5f9e8f'; c.beginPath(); c.roundRect ? c.roundRect(x - 230, y - 200, 460, 200, 40) : c.rect(x - 230, y - 200, 460, 200); c.fill(); c.stroke(); c.fillStyle = '#77b8a8'; c.beginPath(); c.roundRect ? c.roundRect(x - 200, y - 120, 400, 90, 26) : c.rect(x - 200, y - 120, 400, 90); c.fill(); c.stroke(); for (const s of [-1, 1]) { c.beginPath(); c.roundRect ? c.roundRect(x + s * 230 - 40, y - 150, 80, 150, 30) : c.rect(x + s * 230 - 40, y - 150, 80, 150); c.fillStyle = '#5f9e8f'; c.fill(); c.stroke(); }
      c.fillStyle = '#c96'; c.fillRect(W * .07, y - 60, 70, 60); c.fillStyle = '#4fa63f'; for (let i = 0; i < 6; i++) { ell(c, W * .07 + 35 + Math.cos(i) * 40, y - 100 + Math.sin(i) * 30, 30, 14, i); c.fill(); } });
    if (kit) add(1.08, (c) => { const x = W * .5, y = H - 40; c.lineWidth = 6; c.strokeStyle = '#3a2a22'; c.fillStyle = '#c88a55'; c.fillRect(x - 380, y - 230, 760, 30); c.strokeRect(x - 380, y - 230, 760, 30); c.fillRect(x - 350, y - 200, 26, 200); c.fillRect(x + 324, y - 200, 26, 200); });
  } else if (type === 'street') {
    add(.25, (c, r) => { for (let i = 0; i < 18; i++) { const w = 120 + r() * 120, h = 250 + r() * 300, x = X0 + i * XW / 18; c.fillStyle = night ? '#28345f' : '#bcd0e6'; c.fillRect(x, H * .66 - h, w, h); } });
    add(.7, (c, r) => { const cols = ['#e86a5f', '#f2c94c', '#7fc4a4', '#8d7ad9', '#f29e4c', '#5fa8e8']; let x = X0; while (x < X0 + XW) { const w = 260 + r() * 140, h = 380 + r() * 260, col = cols[(r() * cols.length) | 0]; c.fillStyle = col; c.fillRect(x, gTop - h, w - 10, h); c.strokeStyle = shade(col, -.35); c.lineWidth = 5; c.strokeRect(x, gTop - h, w - 10, h); for (let yy = gTop - h + 40; yy < gTop - 130; yy += 95) for (let xx = x + 30; xx < x + w - 80; xx += 80) { c.fillStyle = night ? (r() < .6 ? '#ffe28a' : '#2a3050') : '#cfeaff'; c.fillRect(xx, yy, 46, 60); c.strokeRect(xx, yy, 46, 60); } if (r() < .5) { c.fillStyle = '#fff'; c.fillRect(x + 30, gTop - 120, w - 70, 34); c.fillStyle = shade(col, -.4); c.fillRect(x + 40, gTop - 112, (w - 90) * .7, 18); } c.fillStyle = '#5a3a2a'; c.fillRect(x + w / 2 - 35, gTop - 120, 70, 120); x += w; } });
    add(1, (c, r) => { c.fillStyle = '#c9c4bb'; c.fillRect(X0, gTop, XW, H - gTop); c.strokeStyle = 'rgba(0,0,0,.12)'; c.lineWidth = 3; for (let x = X0; x < X0 + XW; x += 110) { c.beginPath(); c.moveTo(x, gTop); c.lineTo(x - 60, H - 90); c.stroke(); } c.fillStyle = '#8f8f8f'; c.fillRect(X0, H - 90, XW, 18); c.fillStyle = '#4a4a50'; c.fillRect(X0, H - 72, XW, 72); c.fillStyle = '#fff'; for (let x = X0; x < X0 + XW; x += 180) c.fillRect(x, H - 38, 90, 10);
      for (let i = 0; i < 4; i++) { const x = X0 + (i + .5) * XW / 4; c.fillStyle = '#3a3f4a'; c.fillRect(x - 6, gTop - 330, 12, 340); c.fillRect(x - 6, gTop - 330, 60, 10); c.fillStyle = night ? '#fff2a8' : '#e8e8e8'; ell(c, x + 52, gTop - 312, 16, 12); c.fill(); } });
  } else if (type === 'beach') {
    add(.4, (c, r) => { c.fillStyle = night ? '#173a6a' : '#2f8fd6'; c.fillRect(X0, H * .5, XW, H * .5); c.fillStyle = night ? '#1f4a7a' : '#62b6ee'; c.fillRect(X0, H * .5, XW, 14); c.fillStyle = night ? '#24345f' : '#7cc06a'; ell(c, W * .8, H * .5, 200, 40); c.fill(); });
    add(1, (c, r) => { const g = c.createLinearGradient(0, gTop - 60, 0, H); g.addColorStop(0, '#f6dc9c'); g.addColorStop(1, '#e8c477'); c.fillStyle = g; c.beginPath(); c.moveTo(X0, gTop - 40); for (let i = 0; i <= 30; i++) c.lineTo(X0 + XW * i / 30, gTop - 40 + Math.sin(i * .7) * 10); c.lineTo(X0 + XW, H); c.lineTo(X0, H); c.fill(); for (let i = 0; i < 14; i++) { c.fillStyle = ['#ff9fb2', '#fff', '#ffd23f'][i % 3]; ell(c, X0 + r() * XW, gTop + r() * (H - gTop), 9, 6); c.fill(); }
      const ux = W * .15, uy = GROUND + 10; c.strokeStyle = '#6b4a32'; c.lineWidth = 8; c.beginPath(); c.moveTo(ux, uy); c.lineTo(ux + 40, uy - 330); c.stroke(); for (let i = 0; i < 6; i++) { c.fillStyle = i % 2 ? '#fff' : '#e8344e'; c.beginPath(); c.moveTo(ux + 40, uy - 330); c.arc(ux + 40, uy - 330, 210, Math.PI + i * Math.PI / 6, Math.PI + (i + 1) * Math.PI / 6); c.fill(); } });
    add(.9, (c) => { const x = W * .82, y = gTop; c.strokeStyle = '#8a5a3a'; c.lineWidth = 26; c.beginPath(); c.moveTo(x, y); c.quadraticCurveTo(x + 60, y - 200, x + 20, y - 420); c.stroke(); c.fillStyle = '#3f9a3a'; for (let i = 0; i < 6; i++) { c.save(); c.translate(x + 20, y - 420); c.rotate(i * 1.05); ell(c, 120, 0, 130, 26, .3); c.fill(); c.restore(); } });
  } else if (type === 'space') {
    add(.05, (c, r) => { for (let i = 0; i < 260; i++) { c.fillStyle = `rgba(255,255,255,${.3 + r() * .7})`; ell(c, X0 + r() * XW, r() * H, r() * 2.4 + .5, r() * 2.4 + .5); c.fill(); } });
    add(.15, (c) => { const x = W * .75, y = H * .3; const g = c.createRadialGradient(x - 60, y - 60, 20, x, y, 190); g.addColorStop(0, '#ffcf8a'); g.addColorStop(1, '#d9673a'); c.fillStyle = g; ell(c, x, y, 180, 180); c.fill(); c.strokeStyle = 'rgba(255,230,190,.8)'; c.lineWidth = 16; ell(c, x, y, 300, 60, -.3); c.stroke(); c.fillStyle = '#8fd0ff'; ell(c, W * .2, H * .22, 60, 60); c.fill(); });
    add(.85, (c) => { const x = W * .15, y = gTop; c.fillStyle = '#eee'; c.strokeStyle = '#333'; c.lineWidth = 6; c.beginPath(); c.moveTo(x, y - 420); c.quadraticCurveTo(x + 90, y - 300, x + 70, y - 60); c.lineTo(x - 70, y - 60); c.quadraticCurveTo(x - 90, y - 300, x, y - 420); c.fill(); c.stroke(); c.fillStyle = '#7fd0ff'; ell(c, x, y - 260, 34, 34); c.fill(); c.stroke(); c.fillStyle = '#e8344e'; for (const s of [-1, 1]) { c.beginPath(); c.moveTo(x + s * 70, y - 160); c.lineTo(x + s * 130, y); c.lineTo(x + s * 60, y - 60); c.fill(); c.stroke(); } });
    add(1, (c, r) => { c.fillStyle = '#9a9aa8'; c.beginPath(); c.moveTo(X0, gTop); for (let i = 0; i <= 40; i++) c.lineTo(X0 + XW * i / 40, gTop + Math.sin(i * .9) * 12); c.lineTo(X0 + XW, H); c.lineTo(X0, H); c.fill(); for (let i = 0; i < 18; i++) { const x = X0 + r() * XW, y = gTop + 30 + r() * (H - gTop - 40), s = 20 + r() * 50; c.fillStyle = '#7d7d8a'; ell(c, x, y, s, s * .3); c.fill(); c.fillStyle = '#b4b4c0'; ell(c, x, y - s * .06, s * .8, s * .2); c.fill(); } });
  }
  return { loc, layers: L, type, time, weather: loc.weather || (type === 'winter' ? 'snow' : 'none'), night, eve };
}

const layerCache = new Map();
function layerCanvas(locKey, i, layer) {
  const key = locKey + ':' + i; let cv = layerCache.get(key); if (cv) return cv;
  const p = layer.p, ext = p > 1 ? 1.2 : 1;
  cv = (typeof OffscreenCanvas !== 'undefined') ? new OffscreenCanvas(XW * ext | 0, H) : Object.assign(document.createElement('canvas'), { width: XW * ext | 0, height: H });
  const c = cv.getContext('2d'); c.translate(-X0, 0); layer.fn(c, rng(layer.seed));
  cv._x0 = X0; layerCache.set(key, cv); return cv;
}
MK.clearCache = () => layerCache.clear();

function drawSky(ctx, L, T) {
  const s = SKY[L.time] || SKY.day; if (L.type === 'space') { const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#05051a'); g.addColorStop(1, '#1b1450'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); return; }
  if (L.type === 'room' || L.type === 'kitchen') { ctx.fillStyle = '#f7e3c4'; ctx.fillRect(0, 0, W, H); return; }
  const g = ctx.createLinearGradient(0, 0, 0, H * .7); g.addColorStop(0, L.weather === 'rain' ? '#7b8796' : s[0]); g.addColorStop(1, L.weather === 'rain' ? '#b9c2cc' : s[1]); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  if (L.night) { const r = rng(7); for (let i = 0; i < 120; i++) { ctx.fillStyle = `rgba(255,255,255,${.4 + .5 * Math.sin(T * 2 + i)})`; ell(ctx, r() * W, r() * H * .5, 1.8, 1.8); ctx.fill(); } ctx.fillStyle = '#fff6c8'; ell(ctx, W * .82, H * .15, 55, 55); ctx.fill(); ctx.fillStyle = 'rgba(255,246,200,.15)'; ell(ctx, W * .82, H * .15, 100, 100); ctx.fill(); }
  else if (L.weather !== 'rain') { ctx.fillStyle = L.eve ? '#ffcf7a' : '#fff3a0'; ell(ctx, W * .85, H * (L.eve ? .4 : .14), 70, 70); ctx.fill(); ctx.fillStyle = 'rgba(255,240,160,.25)'; ell(ctx, W * .85, H * (L.eve ? .4 : .14), 120, 120); ctx.fill(); }
}
function drawClouds(ctx, L, T, cam) {
  if (L.type === 'space' || L.type === 'room' || L.type === 'kitchen' || L.night) return;
  const r = rng(hash32(L.type + 'cl')); const col = L.weather === 'rain' ? 'rgba(150,160,175,.95)' : L.eve ? 'rgba(255,220,220,.9)' : 'rgba(255,255,255,.95)';
  for (let i = 0; i < 6; i++) { const x = ((r() * W * 1.4 + T * (8 + r() * 10) - cam.cx * .08) % (W * 1.4)) - W * .2, y = 70 + r() * 220; cloud(ctx, x, y, .8 + r() * .7, col); }
}
function drawWeather(ctx, L, T) {
  if (L.weather === 'rain') { ctx.strokeStyle = 'rgba(200,220,255,.55)'; ctx.lineWidth = 3; const r = rng(3); ctx.beginPath(); for (let i = 0; i < 260; i++) { const x = r() * W * 1.2, sp = 1400 + r() * 500, y = ((r() * H + T * sp) % (H + 60)) - 60; ctx.moveTo(x - y * .12, y); ctx.lineTo(x - y * .12 - 8, y + 34); } ctx.stroke(); }
  if (L.weather === 'snow') { ctx.fillStyle = 'rgba(255,255,255,.9)'; const r = rng(5); for (let i = 0; i < 220; i++) { const x = (r() * W + Math.sin(T + i) * 30) % W, sp = 50 + r() * 70, y = ((r() * H + T * sp) % (H + 20)) - 10, s = 2 + r() * 4; ell(ctx, x, y, s, s); ctx.fill(); } }
  if (L.type === 'beach') { /* блики на воде */ }
}

// ---------- сборка таймлайна ----------
const DUR = { jump: .9, wave: 1.6, dance: 3, spin: .8, nod: .9, shake: 1, clap: 1.6, point: 1.4, think: 2.2, laugh: 1.8, scared: 1.4, fall: 1.0, sit: .6, stand: .6, sleep: .8, wake: .8, take: .6, give: 1.1, drop: .5, turn: .25, look: .25, bow: 1.0, cry: 2, surprise: .8 };
const AUTO_SFX = { jump: 'boing', fall: 'thud', spin: 'whoosh', take: 'pop', give: 'pop', clap: 'clap', surprise: 'ding' };
const OFF = .14;
MK.ACTIONS = Object.keys(DUR).concat(['walk', 'run', 'enter', 'exit', 'say']);

function estSpeech(text) { return .35 + text.length * .062; }

/** Список всех реплик эпизода (для озвучки до сборки). */
MK.collectLines = function (ep, lib) {
  const out = [];
  for (const sc of ep.scenes || []) for (const st of sc.steps || []) if (st.say) {
    const who = st.who || 'Р'; const ch = who === 'Р' ? { voice: (ep.narrator && ep.narrator.voice) || lib.narrator || { base: 'male', pitch: 1, rate: .47 } } : (lib.characters[who] && lib.characters[who].spec);
    if (!ch) continue;
    const v = Object.assign({}, ch.voice || {}, lib.characters[who] && lib.characters[who].voiceId ? { id: lib.characters[who].voiceId } : {});
    out.push({ key: hash32(canon(v) + '|' + st.say).toString(36), who, text: st.say, voice: v });
  }
  return out;
};

/** Проверка сценария против замороженной библиотеки. Возвращает {errors, warnings, newChars, newLocs} */
MK.validate = function (ep, lib) {
  const errors = [], warnings = [], newChars = [], newLocs = [];
  for (const c of ep.characters || []) {
    if (!c.id) { errors.push('У персонажа нет id'); continue; }
    const code = MK.charCode(c), have = lib.characters[c.id];
    if (have && have.code !== code) errors.push(`Персонаж ${c.id} «${have.spec.name}» уже создан с кодом ${have.code}. Его нельзя менять. Новый вид — новый персонаж с новым id.`);
    else if (!have) newChars.push(Object.assign({}, c, { _code: code }));
  }
  for (const l of ep.locations || []) {
    const code = MK.locCode(l), have = lib.locations[l.id];
    if (have && have.code !== code) errors.push(`Локация ${l.id} уже создана с кодом ${have.code}, менять нельзя.`);
    else if (!have) newLocs.push(Object.assign({}, l, { _code: code }));
  }
  const chars = new Set(Object.keys(lib.characters).concat(newChars.map(c => c.id)).concat(['Р']));
  const locs = new Set(Object.keys(lib.locations).concat(newLocs.map(l => l.id)));
  (ep.scenes || []).forEach((sc, i) => {
    const lid = typeof sc.location === 'string' ? sc.location : sc.location && sc.location.id;
    if (!locs.has(lid)) errors.push(`Сцена ${sc.id || i + 1}: нет локации ${lid}`);
    for (const c of sc.cast || []) if (!chars.has(c.who)) errors.push(`Сцена ${sc.id || i + 1}: нет персонажа ${c.who}`);
    for (const st of sc.steps || []) { if (st.who && !chars.has(st.who)) errors.push(`Сцена ${sc.id || i + 1}: нет персонажа ${st.who}`); if (st.do && !MK.ACTIONS.includes(st.do)) warnings.push(`Неизвестное действие «${st.do}» — пропущу`); }
  });
  return { errors, warnings, newChars, newLocs };
};

/** Собирает эпизод: audio — {key:{dur, env:Float32Array(50/с)}} */
MK.compile = function (ep, lib, audio) {
  audio = audio || {};
  const segs = []; let t = 0; const sfx = [], speech = [], music = [];
  const TITLE = ep.titleCard === false ? 0 : 4.5, END = ep.endCard === false ? 0 : 4;
  if (TITLE) { segs.push({ kind: 'title', t0: 0, t1: TITLE }); music.push({ t0: 0, t1: TITLE, mood: 'happy' }); sfx.push({ t: .3, n: 'sparkle' }); t = TITLE; }
  const lines = MK.collectLines(ep, lib); let li = 0;
  for (const [si, sc] of (ep.scenes || []).entries()) {
    const lid = typeof sc.location === 'string' ? sc.location : sc.location.id;
    const lspec = Object.assign({}, (lib.locations[lid] || {}).spec || {}, typeof sc.location === 'object' ? sc.location : {}, sc.time ? { time: sc.time } : {}, sc.weather ? { weather: sc.weather } : {});
    const C = {}; // состояние персонажей при сборке
    for (const cs of sc.cast || []) { const lc = lib.characters[cs.who]; if (!lc) continue; C[cs.who] = { x: cs.x != null ? cs.x : .5, z: cs.z || 0, face: cs.face === 'left' ? -1 : cs.face === 'camera' ? 0 : 1, vis: cs.hidden ? false : true, ev: [], prop: cs.prop ? { type: cs.prop } : null }; }
    const props = (sc.props || []).map(p => ({ id: p.id, type: p.type, color: p.color, x: p.x != null ? p.x : .5, holder: null, ev: [] }));
    const cam = [{ t: 0, mode: sc.camera || 'wide', on: sc.cameraOn || null }];
    let cur = .6, prevStart = .6; const st0 = t;
    for (const step of sc.steps || []) {
      const start = step.with ? prevStart : cur + (step.after || 0); let dur = 0;
      const who = step.who, ch = who && C[who];
      if (step.camera) { cam.push({ t: start, mode: step.camera, on: step.on || null, zoom: step.zoom }); }
      if (step.shake) cam.push({ t: start, shake: step.shake === true ? .6 : step.shake });
      if (step.wait) dur = Math.max(dur, +step.wait);
      if (step.sfx) sfx.push({ t: st0 + start, n: step.sfx });
      if (step.music) music.push({ t0: st0 + start, mood: step.music });
      if (ch) {
        if (step.emotion) ch.ev.push({ t: start, k: 'emo', v: step.emotion });
        if (step.face) ch.ev.push({ t: start, k: 'face', v: faceVal(step.face, ch, C) });
        const d = step.do;
        if (d === 'walk' || d === 'run' || d === 'enter' || d === 'exit') {
          let x0 = ch.x, x1 = step.to != null ? (typeof step.to === 'string' ? (C[step.to] ? C[step.to].x + (C[step.to].x > ch.x ? -.12 : .12) : ch.x) : +step.to) : ch.x;
          if (d === 'enter') { const from = step.from || (x1 > .5 ? 'right' : 'left'); x0 = from === 'right' ? 1 + OFF : -OFF; ch.ev.push({ t: start, k: 'vis', v: true }); if (step.to == null) x1 = from === 'right' ? .75 : .25; }
          if (d === 'exit') { const side = step.side || (ch.x > .5 ? 'right' : 'left'); x1 = side === 'right' ? 1 + OFF : -OFF; }
          const run = d === 'run' || step.run; const sp = (run ? .42 : .2) * (lib.characters[who].spec.speed || 1);
          dur = Math.max(.3, Math.abs(x1 - x0) / sp);
          ch.ev.push({ t: start, k: 'move', x0, x1, t1: start + dur, run });
          ch.ev.push({ t: start, k: 'face', v: x1 >= x0 ? 1 : -1 });
          if (d === 'exit') ch.ev.push({ t: start + dur, k: 'vis', v: false });
          ch.x = x1;
          if (step.face) ch.ev.push({ t: start + dur, k: 'face', v: faceVal(step.face, ch, C) });
        } else if (d && DUR[d] != null) {
          dur = step.dur || DUR[d];
          if (['sit', 'sleep', 'fall'].includes(d)) ch.ev.push({ t: start, k: 'persist', v: d === 'fall' ? 'fallen' : d });
          if (d === 'stand' || d === 'wake') { ch.ev.push({ t: start, k: 'act', n: 'stand', t1: start + dur }); ch.ev.push({ t: start + dur, k: 'persist', v: 'none' }); }
          else if (d === 'turn' || d === 'look') ch.ev.push({ t: start, k: 'face', v: faceVal(step.to || step.face || 'camera', ch, C) });
          else ch.ev.push({ t: start, k: 'act', n: d, t1: start + dur, text: step.text });
          if (AUTO_SFX[d] && step.sfx !== false) sfx.push({ t: st0 + start + (d === 'fall' ? .3 : d === 'clap' ? 0 : .05), n: AUTO_SFX[d], rep: d === 'clap' ? 4 : 1 });
          if (d === 'take') { const p = props.find(p => p.id === step.prop) || props.find(p => !p.holder); if (p) { p.ev.push({ t: start + .3, holder: who }); p.holder = who; } }
          if (d === 'drop') { const p = props.find(p => p.holder === who); if (p) { p.ev.push({ t: start + .3, holder: null, x: ch.x + .03 * (ch.face || 1) }); p.holder = null; } }
          if (d === 'give' && step.to && C[step.to]) { const p = props.find(p => p.holder === who); if (p) { p.ev.push({ t: start + .5, holder: step.to, from: who }); p.holder = step.to; } ch.ev.push({ t: start, k: 'face', v: C[step.to].x >= ch.x ? 1 : -1 }); C[step.to].ev.push({ t: start, k: 'face', v: C[step.to].x >= ch.x ? -1 : 1 }); }
        }
        if (step.to && step.say && C[step.to]) ch.ev.push({ t: start, k: 'face', v: C[step.to].x >= ch.x ? 1 : -1 });
      }
      if (step.say) {
        const ln = lines[li++]; const a = ln && audio[ln.key]; const sd = a ? a.dur : estSpeech(step.say);
        speech.push({ t: st0 + start, dur: sd, key: ln && ln.key, who: who || 'Р', text: step.say });
        if (ch) ch.ev.push({ t: start, k: 'say', t1: start + sd, key: ln && ln.key, text: step.say });
        dur = Math.max(dur, sd + (step.pause != null ? step.pause : .3));
      }
      if (!step.say && !step.do && !step.wait && step.emotion && !step.with) dur = Math.max(dur, .4);
      prevStart = start; cur = Math.max(cur, start + dur);
    }
    const sdur = Math.max(1.5, cur + (sc.tail != null ? sc.tail : .8));
    segs.push({ kind: 'scene', t0: t, t1: t + sdur, sc, loc: buildLocation(lspec), lkey: canon(lspec), C, props, cam, idx: si });
    music.push({ t0: t, t1: t + sdur, mood: sc.music || ep.music || 'happy' });
    t += sdur;
  }
  if (END) { segs.push({ kind: 'end', t0: t, t1: t + END }); music.push({ t0: t, t1: t + END, mood: 'happy' }); t += END; }
  // музыка: склеиваем подряд одинаковые
  const mus = []; for (const m of music) { if (m.t1 == null) { const s = segs.find(s => s.t0 <= m.t0 && s.t1 > m.t0); m.t1 = s ? s.t1 : t; } const last = mus[mus.length - 1]; if (last && last.mood === m.mood && Math.abs(last.t1 - m.t0) < .01) last.t1 = m.t1; else mus.push(Object.assign({}, m)); }
  return { ep, lib, segs, dur: t, sfx, speech, music: mus, audio };
};
function faceVal(v, ch, C) { if (v === 'left') return -1; if (v === 'right') return 1; if (v === 'camera' || v === 'front') return 0; if (C[v]) return C[v].x >= ch.x ? 1 : -1; return ch.face; }

// состояние персонажа в момент t (время сцены)
function charState(cdef, t) {
  const s = { x: cdef.x0 !== undefined ? cdef.x0 : 0, face: 1, emo: 'neutral', vis: true, persist: 'none', pt: 0, act: null, walk: { on: false }, talk: 0, et: 9 };
  return s;
}
function evalChar(init, ev, t, audio, T) {
  let x = init.x0, face = init.face0, faceFrom = init.face0, faceT = -9, emo = 'neutral', emoT = -9, vis = init.vis0, persist = 'none', prev = 'none', pT = 0, act = null, walk = { on: false }, talk = 0, thinkText = null;
  for (const e of ev) {
    if (e.t > t) break;
    switch (e.k) {
      case 'move': { const p = clamp((t - e.t) / (e.t1 - e.t), 0, 1); x = lerp(e.x0, e.x1, p); if (p < 1) { walk = { on: true, run: e.run, ph: (t - e.t) * (e.run ? 15 : 9.5) }; } else walk = { on: false }; break; }
      case 'face': if (e.v !== face) { faceFrom = face; face = e.v; faceT = e.t; } break;
      case 'emo': emo = e.v; emoT = e.t; break;
      case 'vis': vis = e.v; break;
      case 'persist': prev = persist; persist = e.v; pT = e.t; break;
      case 'act': if (t < e.t1) act = { n: e.n, p: (t - e.t) / (e.t1 - e.t), t: t - e.t }, thinkText = e.text; break;
      case 'say': if (t < e.t1) { const a = audio[e.key]; if (a && a.env) { const i = Math.floor((t - e.t) * 50); talk = clamp((a.env[i] || 0) * 3.2, 0, 1); } else { const k = t - e.t; talk = (Math.sin(k * 21) * .5 + .5) * (Math.sin(k * 5.3) * .3 + .7) * (k > e.t1 - e.t - .15 ? 0 : 1); } } break;
    }
  }
  const fk = ease((t - faceT) / .22); const fv = lerp(faceFrom, face, fk);
  return { x, face: fv, emo, et: t - emoT, vis, persist, prev, pt: t - pT, act, walk, talk, thinkText };
}

function camTarget(c, seg, t, S) {
  const pos = id => { const cd = seg.C[id]; if (!cd) return null; const st = S[id]; return st ? { x: st.x * W, y: GROUND - (seg._h[id] || .9) * UNIT * .55, h: seg._h[id] || .9 } : null; };
  let cx = W / 2, cy = H / 2, z = 1;
  if (c.mode === 'close' || c.mode === 'medium') { const p = pos(c.on || Object.keys(seg.C)[0]); if (p) { z = c.zoom || (c.mode === 'close' ? 2.3 : 1.55); cx = p.x; cy = c.mode === 'close' ? GROUND - p.h * UNIT * .75 : GROUND - p.h * UNIT * .55; } }
  else if (c.mode === 'two') { const ids = Array.isArray(c.on) ? c.on : Object.keys(seg.C).slice(0, 2); const a = pos(ids[0]), b = pos(ids[1]); if (a && b) { cx = (a.x + b.x) / 2; z = c.zoom || clamp(W * .62 / (Math.abs(a.x - b.x) + 300), 1, 1.9); cy = GROUND - Math.max(a.h, b.h) * UNIT * .6; } }
  else if (c.mode === 'pan') { cx = (c.on != null ? +c.on : .5) * W; z = c.zoom || 1.3; cy = GROUND - UNIT * .5; }
  const hw = W / (2 * z), hh = H / (2 * z); cx = clamp(cx, hw, W - hw); cy = clamp(cy, hh, H - hh);
  return { cx, cy, z };
}

// ---------- рендер кадра ----------
MK.render = function (ctx, tl, T) {
  const seg = tl.segs.find(s => T >= s.t0 && T < s.t1) || tl.segs[tl.segs.length - 1];
  if (!seg) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); return; }
  const t = T - seg.t0;
  ctx.save();
  if (seg.kind === 'title' || seg.kind === 'end') drawCard(ctx, tl, seg, t, T);
  else drawScene(ctx, tl, seg, t, T);
  // переходы
  const fin = clamp(t / .4, 0, 1), fout = clamp((seg.t1 - T) / .4, 0, 1), a = 1 - Math.min(fin, fout);
  if (a > 0 && !(seg === tl.segs[0] && t < .4 && seg.kind === 'title')) { ctx.fillStyle = `rgba(0,0,0,${a})`; ctx.fillRect(0, 0, W, H); }
  // субтитры
  if (tl.ep.subtitles) { const sp = tl.speech.find(s => T >= s.t && T < s.t + s.dur); if (sp) drawSubtitle(ctx, sp, tl.lib); }
  ctx.restore();
};
function drawSubtitle(ctx, sp, lib) {
  ctx.font = '700 46px -apple-system, "SF Pro Rounded", "DejaVu Sans", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  const words = sp.text.split(' '), lines = []; let ln = ''; for (const w of words) { if (ctx.measureText(ln + ' ' + w).width > W * .7 && ln) { lines.push(ln); ln = w; } else ln = ln ? ln + ' ' + w : w; } lines.push(ln);
  lines.forEach((l, i) => { const y = H - 60 - (lines.length - 1 - i) * 58; ctx.lineWidth = 10; ctx.strokeStyle = 'rgba(0,0,0,.75)'; ctx.strokeText(l, W / 2, y); ctx.fillStyle = '#fff'; ctx.fillText(l, W / 2, y); });
}
function drawCard(ctx, tl, seg, t, T) {
  const ep = tl.ep, title = seg.kind === 'title';
  const g = ctx.createRadialGradient(W / 2, H * .45, 50, W / 2, H / 2, W * .7); g.addColorStop(0, title ? '#ffd56b' : '#9ad0ff'); g.addColorStop(1, title ? '#ff7a59' : '#5a6fd8'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.translate(W / 2, H / 2); ctx.rotate(T * .1); ctx.fillStyle = 'rgba(255,255,255,.1)'; for (let i = 0; i < 16; i++) { ctx.rotate(Math.PI / 8); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(W, -120); ctx.lineTo(W, 120); ctx.fill(); } ctx.restore();
  const r = rng(11); for (let i = 0; i < 40; i++) { const x = r() * W, y = ((r() * H + T * (60 + r() * 80)) % H); ctx.fillStyle = ['#fff', '#ffd23f', '#ff6fa8', '#7fe0ff'][i % 4]; ctx.save(); ctx.translate(x, y); ctx.rotate(T * 2 + i); ctx.fillRect(-8, -4, 16, 8); ctx.restore(); }
  const k = ease(t / .6), bounce = 1 + Math.sin(clamp(t / .6, 0, 1) * Math.PI) * .08;
  ctx.save(); ctx.translate(W / 2, H * (title ? .27 : .35)); ctx.scale(k * bounce, k * bounce); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const big = title ? (ep.series || ep.title || '') : (ep.endText || 'Продолжение следует…');
  ctx.font = `900 ${big.length > 18 ? 104 : 132}px -apple-system, "SF Pro Rounded", "Arial Rounded MT Bold", "DejaVu Sans", sans-serif`; ctx.lineJoin = 'round';
  ctx.lineWidth = 26; ctx.strokeStyle = '#3a1d10'; ctx.strokeText(big, 0, 0); ctx.fillStyle = '#fff'; ctx.fillText(big, 0, 0);
  if (title && ep.title) { ctx.font = '800 62px -apple-system, "SF Pro Rounded", "DejaVu Sans", sans-serif'; const sub = (ep.episode ? `Серия ${ep.episode}. ` : '') + ep.title; ctx.lineWidth = 14; ctx.strokeText(sub, 0, 125); ctx.fillStyle = '#ffe36b'; ctx.fillText(sub, 0, 125); }
  if (!title && ep.endSub) { ctx.font = '800 56px -apple-system, "DejaVu Sans", sans-serif'; ctx.lineWidth = 12; ctx.strokeText(ep.endSub, 0, 120); ctx.fillStyle = '#ffe36b'; ctx.fillText(ep.endSub, 0, 120); }
  ctx.restore();
  // персонажи серии машут
  const ids = (ep.cardCast || Object.keys(tl.lib.characters).filter(id => (ep.scenes || []).some(s => (s.cast || []).some(c => c.who === id)))).slice(0, 5);
  ids.forEach((id, i) => { const lc = tl.lib.characters[id]; if (!lc) return; const ch = lc._n || (lc._n = normChar(lc.spec)); const x = W / 2 + (i - (ids.length - 1) / 2) * 330, appear = ease((t - .4 - i * .15) / .5);
    drawChar(ctx, ch, { x, y: H + 40 - appear * (H * .02 + 40) + (1 - appear) * 300, s: 1.05, face: 0, emo: 'happy', act: { n: i % 2 ? 'wave' : 'jump', p: ((t * .7 + i * .3) % 1), t: t + i }, walk: {}, talk: 0, persist: 'none' }, T); });
}
function drawScene(ctx, tl, seg, t, T) {
  const B = ctx.getTransform();
  const L = seg.loc;
  // состояния персонажей
  const S = {}; seg._h = seg._h || {};
  for (const id in seg.C) { const cd = seg.C[id]; if (!cd._init) { cd._init = { x0: cd.ev.length ? null : cd.x, face0: null, vis0: null }; } }
  for (const id in seg.C) {
    const cd = seg.C[id], cs = (seg.sc.cast || []).find(c => c.who === id) || {};
    const init = { x0: cs.x != null ? cs.x : .5, face0: cs.face === 'left' ? -1 : cs.face === 'camera' ? 0 : 1, vis0: !cs.hidden };
    if (!cd._sorted) { cd.ev.sort((a, b) => a.t - b.t); cd._sorted = true; }
    S[id] = evalChar(init, cd.ev, t, tl.audio, T);
    const lc = tl.lib.characters[id]; if (lc) { lc._n = lc._n || normChar(lc.spec); seg._h[id] = lc._n.size * (lc._n.adult ? 1.15 : 1); }
  }
  // камера
  let ci = 0; const cams = seg.cam.filter(c => !c.shake); for (let i = 0; i < cams.length; i++) if (cams[i].t <= t) ci = i;
  const cur = camTarget(cams[ci], seg, t, S), prevC = ci > 0 ? camTarget(cams[ci - 1], seg, t, S) : cur, k = ease((t - cams[ci].t) / .9);
  const cam = { cx: lerp(prevC.cx, cur.cx, k), cy: lerp(prevC.cy, cur.cy, k), z: lerp(prevC.z, cur.z, k) };
  for (const c of seg.cam) if (c.shake && t >= c.t && t < c.t + c.shake) { const a = (1 - (t - c.t) / c.shake) * 14; cam.cx += Math.sin(t * 61) * a; cam.cy += Math.cos(t * 53) * a; }
  const apply = p => { const zz = 1 + (cam.z - 1) * Math.min(p, 1.3); ctx.setTransform(B); ctx.translate(W / 2, H / 2); ctx.scale(zz, zz); ctx.translate(-(W / 2 + (cam.cx - W / 2) * p), -(H / 2 + (cam.cy - H / 2) * p)); };
  const base = ctx.getTransform ? ctx.getTransform() : null;
  ctx.setTransform(B); drawSky(ctx, L, T); apply(.08); drawClouds(ctx, L, T, cam);
  L.layers.forEach((ly, i) => {
    if (ly.p > 1) return; apply(ly.p); const cv = layerCanvas(seg.lkey, i, ly); ctx.drawImage(cv, X0, 0);
    if (L.type === 'beach' && ly.p === .4) { ctx.strokeStyle = 'rgba(255,255,255,.6)'; ctx.lineWidth = 4; for (let j = 0; j < 7; j++) { ctx.beginPath(); const y = H * .53 + j * 26; for (let x = X0; x < X0 + XW; x += 40) ctx.lineTo(x, y + Math.sin(x * .01 + T * 2 + j) * 5); ctx.stroke(); } }
  });
  apply(1);
  // предметы на земле
  for (const p of seg.props) { let holder = null, x = p.x; for (const e of p.ev) if (e.t <= t) { holder = e.holder; if (e.x != null) x = e.x; } p._holder = holder; if (!holder) drawProp(ctx, p, x * W, GROUND + 6, UNIT * .55, T); }
  // персонажи по глубине
  const order = Object.keys(S).filter(id => S[id].vis && tl.lib.characters[id]).sort((a, b) => (seg.C[b].z - seg.C[a].z) || 0);
  for (const id of order) {
    const st = S[id], cd = seg.C[id]; const ch = tl.lib.characters[id]._n;
    const held = seg.props.find(p => p._holder === id) || null;
    drawChar(ctx, ch, Object.assign(st, { x: st.x * W, y: GROUND - cd.z * 70, s: 1 - cd.z * .18, prop: held || (cd.prop && !seg.props.length ? cd.prop : null), thinkText: st.thinkText }), T);
  }
  L.layers.forEach((ly, i) => { if (ly.p <= 1) return; apply(ly.p); ctx.drawImage(layerCanvas(seg.lkey, i, ly), X0, 0); });
  ctx.setTransform(B);
  drawWeather(ctx, L, T);
  if (L.night && L.type !== 'space') { ctx.globalCompositeOperation = 'multiply'; ctx.fillStyle = L.type === 'room' || L.type === 'kitchen' ? '#9aa0c8' : '#7d88c0'; ctx.fillRect(0, 0, W, H); ctx.globalCompositeOperation = 'source-over'; }
  if (L.eve) { ctx.fillStyle = 'rgba(255,150,80,.08)'; ctx.fillRect(0, 0, W, H); }
  if (L.weather === 'rain') { ctx.fillStyle = 'rgba(40,60,90,.12)'; ctx.fillRect(0, 0, W, H); }
  // лёгкая виньетка
  const vg = ctx.createRadialGradient(W / 2, H / 2, H * .45, W / 2, H / 2, H * 1.05); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.22)'); ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
}

/** Портрет персонажа для карточки (canvas w×h) */
MK.portrait = function (canvas, spec, T, act) {
  const ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height; ctx.clearRect(0, 0, w, h);
  const g = ctx.createLinearGradient(0, 0, 0, h); g.addColorStop(0, '#cdeeff'); g.addColorStop(1, '#a8e08a'); ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  const ch = normChar(spec); const k = h / (UNIT * 1.25 * ch.size * (ch.adult && ch.human ? 1 : 1));
  ctx.save(); ctx.scale(k, k); drawChar(ctx, ch, { x: w / 2 / k, y: h / k - 18 / k, s: 1, face: .6, emo: 'happy', act: act || { n: 'wave', p: 0, t: T || 0 }, walk: {}, talk: 0, persist: 'none' }, T || 0); ctx.restore();
};
MK.locPreview = function (canvas, spec, T) {
  const ctx = canvas.getContext('2d'); const k = canvas.width / W; ctx.save(); ctx.scale(k, k);
  const tl = { ep: {}, lib: { characters: {} }, audio: {}, speech: [], segs: [{ kind: 'scene', t0: 0, t1: 10, sc: { cast: [] }, loc: buildLocation(spec), lkey: canon(spec), C: {}, props: [], cam: [{ t: 0, mode: 'wide' }] }] };
  drawScene(ctx, tl, tl.segs[0], 2, T || 2); ctx.restore();
};

// ---------- звук ----------
const NOTE = n => 440 * Math.pow(2, (n - 69) / 12);
const MOODS = {
  happy: { bpm: 112, prog: [[60, 64, 67], [67, 71, 74], [69, 72, 76], [65, 69, 72]], drums: true, lead: 'square' },
  calm: { bpm: 78, prog: [[65, 69, 72], [60, 64, 67], [62, 65, 69], [58, 62, 65]], drums: false, lead: 'triangle' },
  tense: { bpm: 124, prog: [[57, 60, 64], [62, 65, 69], [64, 68, 71], [57, 60, 64]], drums: true, lead: 'sawtooth' },
  sad: { bpm: 68, prog: [[57, 60, 64], [53, 57, 60], [60, 64, 67], [55, 59, 62]], drums: false, lead: 'triangle' },
  adventure: { bpm: 128, prog: [[62, 66, 69], [57, 61, 64], [59, 62, 66], [55, 59, 62]], drums: true, lead: 'square' },
  magic: { bpm: 90, prog: [[60, 64, 67, 71], [57, 60, 64, 67], [65, 69, 72, 76], [67, 71, 74, 77]], drums: false, lead: 'sine' },
  night: { bpm: 64, prog: [[60, 63, 67], [56, 60, 63], [58, 62, 65], [55, 58, 62]], drums: false, lead: 'sine' },
};
MK.MOODS = Object.keys(MOODS).concat(['none']);

function scheduleMusic(ac, out, m, seed) {
  const md = MOODS[m.mood]; if (!md) return; const beat = 60 / md.bpm, r = rng(seed);
  const g = ac.createGain(); g.connect(out); g.gain.setValueAtTime(0, m.t0); g.gain.linearRampToValueAtTime(1, m.t0 + .6); g.gain.setValueAtTime(1, Math.max(m.t0 + .6, m.t1 - .6)); g.gain.linearRampToValueAtTime(0, m.t1);
  const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2400; lp.connect(g);
  const melody = []; for (let i = 0; i < 16; i++) melody.push(r() < .25 ? null : (r() * 4) | 0);
  for (let bt = m.t0, n = 0; bt < m.t1 - .05; bt += beat, n++) {
    const bar = Math.floor(n / 4), ch = md.prog[bar % md.prog.length];
    if (n % 4 === 0) for (const nn of ch) { const o = ac.createOscillator(), og = ac.createGain(); o.type = 'triangle'; o.frequency.value = NOTE(nn - 12); o.detune.value = (r() - .5) * 8; og.gain.setValueAtTime(0, bt); og.gain.linearRampToValueAtTime(.05, bt + .25); og.gain.setValueAtTime(.05, bt + beat * 3.4); og.gain.linearRampToValueAtTime(0, bt + beat * 4); o.connect(og); og.connect(lp); o.start(bt); o.stop(Math.min(m.t1, bt + beat * 4 + .05)); }
    { const o = ac.createOscillator(), og = ac.createGain(); o.type = 'sine'; o.frequency.value = NOTE(ch[0] - 24 + (n % 2 ? 7 : 0)); og.gain.setValueAtTime(.16, bt); og.gain.exponentialRampToValueAtTime(.001, bt + beat * .9); o.connect(og); og.connect(lp); o.start(bt); o.stop(bt + beat); }
    for (let h = 0; h < 2; h++) { const mi = melody[(n * 2 + h) % 16]; if (mi == null) continue; const tt = bt + h * beat / 2, f = NOTE(ch[mi % ch.length] + (mi === 3 ? 12 : 0) + 12); const o = ac.createOscillator(), og = ac.createGain(); o.type = md.lead; o.frequency.value = f; const v = md.lead === 'square' || md.lead === 'sawtooth' ? .025 : .055; og.gain.setValueAtTime(v, tt); og.gain.exponentialRampToValueAtTime(.0008, tt + beat * .45); o.connect(og); og.connect(lp); o.start(tt); o.stop(tt + beat * .5); }
    if (md.drums) { if (n % 2 === 0) kick(ac, lp, bt); if (n % 4 === 2) snare(ac, lp, bt, .08); hat(ac, lp, bt + beat / 2, .03); }
  }
}
let noiseBuf = null; function noise(ac) { if (noiseBuf && noiseBuf.sampleRate === ac.sampleRate) return noiseBuf; const b = ac.createBuffer(1, ac.sampleRate, ac.sampleRate), d = b.getChannelData(0), r = rng(99); for (let i = 0; i < d.length; i++) d[i] = r() * 2 - 1; noiseBuf = b; return b; }
function kick(ac, out, t) { const o = ac.createOscillator(), g = ac.createGain(); o.frequency.setValueAtTime(140, t); o.frequency.exponentialRampToValueAtTime(45, t + .12); g.gain.setValueAtTime(.35, t); g.gain.exponentialRampToValueAtTime(.001, t + .25); o.connect(g); g.connect(out); o.start(t); o.stop(t + .26); }
function noiseHit(ac, out, t, dur, vol, type, freq, q) { const s = ac.createBufferSource(); s.buffer = noise(ac); const f = ac.createBiquadFilter(); f.type = type; f.frequency.value = freq; if (q) f.Q.value = q; const g = ac.createGain(); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.001, t + dur); s.connect(f); f.connect(g); g.connect(out); s.start(t, Math.random() * 0 + (t * 7919 % .5)); s.stop(t + dur + .02); return { f, g }; }
function snare(ac, out, t, v) { noiseHit(ac, out, t, .16, v, 'bandpass', 1800, .7); }
function hat(ac, out, t, v) { noiseHit(ac, out, t, .05, v, 'highpass', 7000); }
function tone(ac, out, t, f0, f1, dur, vol, type) { const o = ac.createOscillator(), g = ac.createGain(); o.type = type || 'sine'; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.001, t + dur); o.connect(g); g.connect(out); o.start(t); o.stop(t + dur + .02); return o; }
const SFX = {
  boing: (ac, o, t) => { const x = tone(ac, o, t, 180, 520, .35, .35, 'sine'); const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = 22; lg.gain.value = 40; l.connect(lg); lg.connect(x.frequency); l.start(t); l.stop(t + .36); },
  thud: (ac, o, t) => { tone(ac, o, t, 120, 40, .3, .5); noiseHit(ac, o, t, .2, .3, 'lowpass', 500); },
  whoosh: (ac, o, t) => { const h = noiseHit(ac, o, t, .45, .25, 'bandpass', 400, 1.5); h.f.frequency.exponentialRampToValueAtTime(3000, t + .4); },
  pop: (ac, o, t) => tone(ac, o, t, 600, 1400, .08, .3),
  clap: (ac, o, t) => noiseHit(ac, o, t, .09, .35, 'bandpass', 1500, .8),
  ding: (ac, o, t) => { for (const [f, v] of [[1320, .2], [2640, .08], [3960, .04]]) tone(ac, o, t, f, f * .999, 1.2, v); },
  sparkle: (ac, o, t) => { for (let i = 0; i < 6; i++) tone(ac, o, t + i * .07, 1500 + i * 300, 1500 + i * 300, .3, .08); },
  magic: (ac, o, t) => { for (let i = 0; i < 10; i++) tone(ac, o, t + i * .05, 800 + i * 180, 900 + i * 180, .4, .06, 'triangle'); },
  splash: (ac, o, t) => noiseHit(ac, o, t, .6, .4, 'lowpass', 1800),
  knock: (ac, o, t) => { for (let i = 0; i < 3; i++) { tone(ac, o, t + i * .18, 220, 120, .08, .5); noiseHit(ac, o, t + i * .18, .05, .2, 'lowpass', 900); } },
  bell: (ac, o, t) => { for (let i = 0; i < 2; i++) for (const [f, v] of [[880, .15], [1760, .06]]) tone(ac, o, t + i * .4, f, f, 1, v); },
  step: (ac, o, t) => noiseHit(ac, o, t, .05, .12, 'lowpass', 700),
  drum: (ac, o, t) => { for (let i = 0; i < 12; i++) snare(ac, o, t + i * .06, .05 + i * .01); },
  meow: (ac, o, t) => { const x = tone(ac, o, t, 500, 700, .5, .18, 'sawtooth'); x.frequency.setValueAtTime(500, t); x.frequency.linearRampToValueAtTime(820, t + .2); x.frequency.linearRampToValueAtTime(420, t + .5); },
  bark: (ac, o, t) => { for (let i = 0; i < 2; i++) { tone(ac, o, t + i * .25, 400, 180, .15, .3, 'sawtooth'); } },
  laugh: (ac, o, t) => { for (let i = 0; i < 5; i++) tone(ac, o, t + i * .13, 520 - i * 20, 380 - i * 20, .1, .14, 'triangle'); },
};
MK.SFX = Object.keys(SFX);

/** Сводит всю дорожку: речь (AudioBuffer по ключу) + музыка + эффекты. → AudioBuffer (моно 44.1 кГц) */
MK.mixAudio = async function (tl, buffers) {
  const sr = 44100, len = Math.ceil((tl.dur + .5) * sr);
  const ac = new OfflineAudioContext(1, len, sr);
  const master = ac.createDynamicsCompressor(); master.threshold.value = -12; master.ratio.value = 3; master.connect(ac.destination);
  const musicBus = ac.createGain(); musicBus.gain.value = (tl.ep.musicVolume != null ? tl.ep.musicVolume : .5); musicBus.connect(master);
  const duck = ac.createGain(); duck.connect(musicBus); duck.gain.setValueAtTime(1, 0);
  for (const s of tl.speech) { duck.gain.setValueAtTime(1, Math.max(0, s.t - .15)); duck.gain.linearRampToValueAtTime(.35, s.t); duck.gain.setValueAtTime(.35, s.t + s.dur); duck.gain.linearRampToValueAtTime(1, s.t + s.dur + .3); }
  tl.music.forEach((m, i) => { if (m.mood !== 'none') scheduleMusic(ac, duck, m, hash32((tl.ep.series || '') + (tl.ep.episode || 0) + i + m.mood)); });
  const fx = ac.createGain(); fx.gain.value = .55; fx.connect(master);
  for (const s of tl.sfx) { const f = SFX[s.n]; if (!f) continue; for (let i = 0; i < (s.rep || 1); i++) f(ac, fx, s.t + i * .22); }
  const vo = ac.createGain(); vo.gain.value = 1.0; vo.connect(master);
  for (const s of tl.speech) { const b = buffers && buffers[s.key]; if (!b) continue; const src = ac.createBufferSource(); src.buffer = b; src.connect(vo); src.start(s.t); }
  const out = await ac.startRendering(); const d = out.getChannelData(0); let pk = 0; for (let i = 0; i < d.length; i++) { const a = Math.abs(d[i]); if (a > pk) pk = a; }
  if (pk > 0) { const g = .89 / pk; for (let i = 0; i < d.length; i++) d[i] *= g; }
  return out;
};
MK.envelope = function (buf) { const d = buf.getChannelData(0), step = Math.floor(buf.sampleRate / 50), env = new Float32Array(Math.ceil(d.length / step)); for (let i = 0; i < env.length; i++) { let s = 0; for (let j = i * step; j < Math.min(d.length, (i + 1) * step); j++) s += d[j] * d[j]; env[i] = Math.sqrt(s / step); } return env; };
MK.wav = function (buf) {
  const d = buf.getChannelData(0), n = d.length, b = new ArrayBuffer(44 + n * 2), v = new DataView(b), w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); w(8, 'WAVE'); w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, buf.sampleRate, true); v.setUint32(28, buf.sampleRate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, clamp(d[i], -1, 1) * 32767, true);
  return new Uint8Array(b);
};

global.MK = MK;
})(typeof window !== 'undefined' ? window : globalThis);
