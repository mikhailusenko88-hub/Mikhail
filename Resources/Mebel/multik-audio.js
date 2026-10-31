/* Звук мультиков: ударения и «ё» для озвучки, живые возгласы (смех, плач, зевок, чих, пение),
   музыка «как у настоящего мультсериала» (своя тема у сериала, инструменты, мелодия не мешает репликам),
   звуки места (птицы, сверчки, море, город, дождь), шаги. Подключается после multik-engine.js. */
'use strict';
(function (global) {
const MK = global.MK; if (!MK) return;
const rng = MK._rng, clamp = (v, a, b) => v < a ? a : v > b ? b : v, lerp = (a, b, t) => a + (b - a) * t;
const NOTE = n => 440 * Math.pow(2, (n - 69) / 12);

// =====================================================================================
// 1. УДАРЕНИЯ И «Ё»
// =====================================================================================
const ACUTE = '́', VOW = 'аеёиоуыэюя';
// слова, где «е» почти всегда читается как «ё»
const YO = {}; ('ещё её ёж ёжик ёжики ёжика ёлка ёлки ёлку ёлочка ёлочки пёс пёсик мёд лёд лёг легла лёгкий лёгкая лёгкое клён орёл щётка ребёнок котёнок утёнок лисёнок поросёнок цыплёнок телёнок слонёнок волчонок '
  + 'идёт идёшь идём пойдём найдём придём ждёт ждёшь живёт живёшь поёт поёшь даёт даёшь встаёт встаёшь берёт берёшь несёт несёшь зовёт зовёшь ведёт ведёшь растёт плывёт ползёт врёт врёшь '
  + 'твоё моё своё самолёт вертолёт полёт вперёд звёздочка звёздочки зелёный зелёная зелёное зелёные весёлый весёлая весёлое весёлые жёлтый жёлтая жёлтое жёлтые чёрный чёрная чёрное чёрные '
  + 'тёплый тёплая тёплое тёплые тёмный тёмная тёмное тёмные пчёлка пчёлы ёжиться ёрзать шёпотом шёл пришёл ушёл нашёл пошёл зашёл вошёл вышел подошёл прошёл чётко серьёзно серьёзный '
  + 'ёлочные звёзд берёза берёзка остриё бельё жильё питьё копьё').split(' ').forEach(w => { if (w) YO[w.replace(/ё/g, 'е')] = w; });
YO['вышел'] = 'вышел';
const VSE_YO = /^(хорошо|равно|ещё|еще|в|будет|понял|поняла|поняли|ясно|время|сделал|сделала|готово|кончилось|закончилось|получилось|прошло|узнаем|знаю|отлично|правильно|нормально|можно|верно|тихо|спокойно|позади|вместе|сразу|видно|слышно|это|такое|остальное|сам|сама)$/;
function lowBase(w) { return w.toLowerCase().replace(/[́]/g, ''); }
/** Русское слово с известным ударением → IPA (для iPhone: так он произносит именно так, как надо). */
function ruIPA(word, si) {
  let w = word.toLowerCase().replace(/ё/g, m => m);
  if (si < 0) { const yo = w.indexOf('ё'); if (yo >= 0) si = yo; else return null; }
  w = w.replace(/^что(?=$|бы|б$)/, 'што').replace(/^конечно$/, 'конешно').replace(/^скучно$/, 'скушно').replace(/^сегодня/, 'севодня').replace(/^нарочно$/, 'нарошно');
  if (/(ого|его)$/.test(w) && w.length > 3 && !/^(много|немного|строго|дорого|убого|полого|ого)$/.test(w) && si < w.length - 2) w = w.slice(0, -2) + 'во';
  if (/ть?ся$/.test(w) && si < w.length - 3) w = w.replace(/ть?ся$/, 'ца');
  const CONS = { б: 'b', в: 'v', г: 'ɡ', д: 'd', ж: 'ʐ', з: 'z', й: 'j', к: 'k', л: 'l', м: 'm', н: 'n', п: 'p', р: 'r', с: 's', т: 't', ф: 'f', х: 'x', ц: 'ts', ч: 'tɕ', ш: 'ʂ', щ: 'ɕː' };
  const DEV = { b: 'p', v: 'f', ɡ: 'k', d: 't', ʐ: 'ʂ', z: 's' }, VOI = { p: 'b', f: 'v', k: 'ɡ', t: 'd', ʂ: 'ʐ', s: 'z' }, VLESS = new Set(['p', 'f', 'k', 't', 'ʂ', 's', 'ts', 'tɕ', 'x', 'ɕː']);
  const T = []; // {c: true, base, soft} | {v: letter, src, iot, afterSoft, afterHardSib}
  for (let i = 0; i < w.length; i++) {
    const c = w[i], nx = w[i + 1] || '', pv = w[i - 1] || '';
    if (VOW.includes(c)) {
      const iot = 'еёюя'.includes(c) && (i === 0 || VOW.includes(pv) || pv === 'ь' || pv === 'ъ'), iotI = c === 'и' && pv === 'ь';
      if (iot || iotI) T.push({ c: true, base: 'j', soft: false, j: true });
      const prevC = T.length ? T[T.length - 1] : null;
      T.push({ v: c, src: i, afterSoft: iot || iotI || !!(prevC && prevC.c && (prevC.soft || prevC.j || /tɕ|ɕː/.test(prevC.base))), afterHard: !!(prevC && prevC.c && /^(ʐ|ʂ|ts)$/.test(prevC.base)) });
    } else if (CONS[c]) {
      const soft = !!nx && 'еёиюяь'.includes(nx) && !'жшц'.includes(c) && !'чщй'.includes(c);
      T.push({ c: true, base: CONS[c], soft, j: c === 'й' });
    }
  }
  // озвончение/оглушение
  for (let k = T.length - 1; k >= 0; k--) { const t = T[k]; if (!t.c || t.j) continue; const n = T[k + 1];
    if (!n) { if (DEV[t.base]) t.base = DEV[t.base]; continue; }
    if (n.c && !n.j) { if (DEV[n.base] && n.base !== 'v' && VOI[t.base]) t.base = VOI[t.base]; else if (VLESS.has(n.base) && DEV[t.base]) t.base = DEV[t.base]; } }
  const vIdx = T.map((t, k) => t.v ? k : -1).filter(k => k >= 0); const sk = vIdx.find(k => T[k].src === si); if (sk == null) return null;
  const sPos = vIdx.indexOf(sk), out = [];
  T.forEach((t, k) => {
    if (t.c) { let p = t.base; if (t.soft) p = p === 'l' ? 'lʲ' : p + 'ʲ'; else if (p === 'l') p = 'ɫ'; if (k + 1 < T.length && T[k + 1].c && !T[k + 1].j && T[k + 1].base === t.base && T[k + 1].soft === t.soft) return; if (k > 0 && T[k - 1].c && T[k - 1].base === t.base && T[k - 1].soft === t.soft && !t.j) p += 'ː';
      out.push({ p, c: true, k }); return; }
    const vp = vIdx.indexOf(k), stressed = k === sk, L = t.v; const fin = vp === vIdx.length - 1 && k === T.length - 1;
    const cls = 'аяа'.includes(L) ? 'a' : 'оё'.includes(L) ? 'o' : 'ую'.includes(L) ? 'u' : 'еэ'.includes(L) ? 'e' : L === 'ы' ? 'y' : 'i';
    let p;
    if (stressed) p = { a: 'a', o: 'o', u: 'u', e: t.afterHard ? 'ɛ' : 'e', y: 'ɨ', i: t.afterHard ? 'ɨ' : 'i' }[cls];
    else if (t.afterSoft) p = cls === 'u' ? 'ʊ' : cls === 'a' && fin ? 'ə' : cls === 'y' ? 'ɨ' : 'ɪ';
    else { const pre1 = vp === sPos - 1, init = k === 0; p = cls === 'a' || cls === 'o' ? (pre1 || init ? 'ɐ' : 'ə') : cls === 'u' ? 'ʊ' : cls === 'y' ? 'ɨ' : t.afterHard ? 'ɨ' : 'ɪ'; }
    out.push({ p, v: true, k, stressed });
  });
  const si2 = out.findIndex(o => o.stressed); let ins = si2, q = si2 - 1; while (q >= 0 && out[q].c) q--;
  const onset = out.slice(q + 1, si2); if (q < 0) ins = 0; else if (onset.length) { ins = si2 - 1; const a = onset[onset.length - 2], b = onset[onset.length - 1]; if (a && /^(p|b|t|d|k|ɡ|f|v)/.test(a.p) && /^(r|l|ɫ|n|m)/.test(b.p)) ins = si2 - 2; }
  out.splice(ins, 0, { p: 'ˈ' });
  return out.map(o => o.p).join('');
}
MK.ruIPA = ruIPA;
/** Готовит реплику к озвучке: «+» и заглавная гласная → ударение, словарь ударений, «ё». → {text, ipa:[[начало, длина, ipa]]} */
MK.prepSpeech = function (text, lex, mode) {
  lex = lex || {}; const dict = lex.stress || {}; mode = mode || 'ipa';
  let t = String(text || '').replace(/\+([аеёиоуыэюяАЕЁИОУЫЭЮЯ])/g, '$1' + ACUTE);
  const parts = t.split(/([А-Яа-яЁё́-]+)/); let out = '', ipa = [];
  for (let i = 0; i < parts.length; i++) {
    let w = parts[i]; if (!w || !/[А-Яа-яЁё]/.test(w)) { out += w; continue; }
    // заглавная гласная внутри слова = ударение («замОк»)
    if (!w.includes(ACUTE)) { const inner = w.slice(1); const ups = [...inner].map((c, j) => /[АЕЁИОУЫЭЮЯ]/.test(c) ? j + 1 : -1).filter(j => j > 0); const otherUp = /[БВГДЖЗЙКЛМНПРСТФХЦЧШЩЪЫЬЭЮЯ]/.test(inner.replace(/[АЕЁИОУЫЭЮЯ]/g, ''));
      if (ups.length === 1 && !otherUp && inner !== inner.toUpperCase()) { const j = ups[0]; w = w.slice(0, j) + w[j].toLowerCase() + ACUTE + w.slice(j + 1); } }
    const base = lowBase(w);
    if (!w.includes(ACUTE)) { const d = dict[base]; if (d) { let st = d.replace(/\+([аеёиоуыэюя])/gi, '$1' + ACUTE); w = matchCase(w, st); } }
    if (!w.includes(ACUTE) && !w.includes('ё') && !w.includes('Ё')) { const y = YO[base]; if (y && y !== base) w = matchCase(w, y);
      else if (base === 'все') { const nxt = (parts.slice(i + 1).join('').match(/^\s*([А-Яа-яЁё]+)/) || [])[1]; const end = /^\s*([.!?…,—]|$)/.test(parts.slice(i + 1).join('')); if (end || (nxt && VSE_YO.test(nxt.toLowerCase()))) w = matchCase(w, 'всё'); } }
    const ai = w.indexOf(ACUTE);
    if (ai > 0) { const plain = w.replace(/́/g, ''), si = ai - 1;
      if (mode === 'acute') { out += w; continue; }
      if (mode === 'respell') { out += [...plain].map((c, j) => j !== si && (c === 'о' || c === 'О') ? (c === 'о' ? 'а' : 'А') : c).join(''); continue; }
      const p = ruIPA(plain, si); if (p) ipa.push([out.length, plain.length, p]); out += plain; continue; }
    out += w;
  }
  return { text: out, ipa };
};
function matchCase(orig, target) { const o = orig.replace(/́/g, ''); if (o[0] && o[0] === o[0].toUpperCase() && o[0] !== o[0].toLowerCase()) return target[0].toUpperCase() + target.slice(1); return target; }
/** Слова с «+» из текста — в словарь (запоминаются навсегда). */
MK.learnStress = function (text, lex) { const found = []; String(text || '').replace(/[А-Яа-яЁё]*\+[аеёиоуыэюяАЕЁИОУЫЭЮЯ][А-Яа-яЁё]*/g, m => { const k = m.replace(/\+/g, '').toLowerCase(); lex.stress = lex.stress || {}; if (lex.stress[k] !== m.toLowerCase()) { lex.stress[k] = m.toLowerCase(); found.push(m.toLowerCase()); } }); return found; };

// =====================================================================================
// 2. ЖИВЫЕ ВОЗГЛАСЫ: формантный синтез голоса героя (смех, плач, зевок, чих, «ля-ля»)
// =====================================================================================
const VWL = { a: [800, 1200, 2600], o: [520, 880, 2500], u: [330, 780, 2400], i: [310, 2300, 3000], e: [500, 1850, 2600], y: [380, 1500, 2400], l: [360, 1100, 2600], h: [900, 1500, 2700] };
function bezierEnv(pts, t) { for (let i = 1; i < pts.length; i++) if (t <= pts[i][0]) { const a = pts[i - 1], b = pts[i], k = (t - a[0]) / Math.max(1e-6, b[0] - a[0]); return a[1] + (b[1] - a[1]) * (k * k * (3 - 2 * k)); } return pts[pts.length - 1][1]; }
/** Формантный голос: дыхание с «пульсирующим» шумом, мягкий наклон спектра, дрожание высоты и громкости — чтобы не звучало как зуммер.
    segs: [{d, f0:[a,b], vib:[Гц, глубина], v:[[t,amp]..] голос, n:[[t,amp]..] выдох, fA/fB форманты, bw, fry}] → Float32Array */
function fsynth(segs, sr, seed, fscale, breath) {
  const r = rng(seed || 7), total = segs.reduce((s, g) => s + g.d, 0), N = Math.ceil(total * sr) + 1, out = new Float32Array(N);
  let ph = 0, i0 = 0, cyc = { a: 1, j: 1 }, tilt = 0, prevD = 0, flowPrev = 0; const st = [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]; let nz1 = 0, nz2 = 0;
  const BW = [110, 140, 200, 280, 350], GN = [1, .6, .32, .16, .08];
  for (const g of segs) { const n = Math.round(g.d * sr); let co = null; const oq = g.oq || .72, ta = Math.exp(-2 * Math.PI * (g.tilt || 1800) / sr);
    for (let i = 0; i < n; i++) { const t = i / n, tt = (i0 + i) / sr;
      if (i % 32 === 0) { const A = g.fA || VWL.a, B = g.fB || A; const F = A.map((f, k) => lerp(f, B[k], t * t * (3 - 2 * t)) * (fscale || 1)); F.push(3600 * (fscale || 1), 4600 * (fscale || 1));
        co = F.map((f, k) => { const rr = Math.exp(-Math.PI * BW[k] * (g.bw || 1) * (fscale || 1) / sr); return [1 - rr, 2 * rr * Math.cos(2 * Math.PI * Math.min(f, sr * .45) / sr), -rr * rr]; }); }
      const vib = g.vib ? Math.sin(tt * 2 * Math.PI * g.vib[0]) * g.vib[1] : 0;
      let f0 = Math.max(35, lerp(g.f0[0], g.f0[1], g.curve ? Math.pow(t, g.curve) : t) * (1 + vib) * cyc.j);
      ph += f0 / sr; if (ph >= 1) { ph -= 1; cyc = { a: 1 + (r() - .5) * (g.fry ? .9 : .28), j: 1 + (r() - .5) * (g.fry ? .35 : .045) }; }
      const p = ph; const flow = p < oq * .8 ? .5 * (1 - Math.cos(Math.PI * p / (oq * .8))) : p < oq ? Math.cos(.5 * Math.PI * (p - oq * .8) / (oq * .2)) : 0;
      const d = (flow - flowPrev) * sr / f0 * .1; flowPrev = flow; tilt = tilt * ta + d * (1 - ta); // мягче вверху спектра
      const src = (tilt * 1.6 + flow * .18) * cyc.a;
      nz1 = nz1 * .25 + (r() * 2 - 1) * .75; nz2 = nz2 * .6 + (r() * 2 - 1) * .4;
      const va = g.v ? bezierEnv(g.v, t) : 0, na = g.n ? bezierEnv(g.n, t) : 0;
      const pulsed = nz1 * (.25 + flow * .75); // шум дыхания пульсирует вместе с голосом
      const exc = src * va + pulsed * va * (breath || .25) * 1.4 + nz1 * na * .9 + nz2 * na * .3;
      let y = 0; for (let k = 0; k < 5; k++) { const c = co[k], s2 = st[k]; const yy = c[0] * exc + c[1] * s2[0] + c[2] * s2[1]; s2[1] = s2[0]; s2[0] = yy; y += yy * GN[k]; }
      out[i0 + i] = y; }
    i0 += n; }
  // мягкая комната, чтобы голос «стоял» в пространстве
  const dl = [Math.round(sr * .019), Math.round(sr * .031), Math.round(sr * .047)]; for (let i = N - 1; i >= 0; i--) { let a = 0; for (let k = 0; k < 3; k++) if (i - dl[k] >= 0) a += out[i - dl[k]] * (.07 - k * .015); out[i] += a; }
  let pk = 0; for (let i = 0; i < N; i++) pk = Math.max(pk, Math.abs(out[i])); if (pk > 0) for (let i = 0; i < N; i++) out[i] *= .8 / pk;
  return out;
}
function vocalSegs(kind, f0, seed, variant) {
  const r = rng(seed * 7 + (variant || 0) * 131 + 1), S = [];
  const gap = (d, br) => S.push({ d, f0: [f0, f0], fA: VWL.h, v: [[0, 0], [1, 0]], n: [[0, br || 0], [1, br || 0]] });
  const style = seed % 3; // характер у героя всегда один и тот же: 0 хихиканье, 1 смех, 2 басистый смешок
  if (kind === 'laugh') {
    const giggle = style === 0 && f0 > 230, chuck = style === 2 || f0 < 160;
    const vw = giggle ? (r() < .5 ? 'i' : 'e') : chuck ? (r() < .6 ? 'o' : 'a') : 'a';
    const nSyl = (giggle ? 6 : chuck ? 4 : 5) + ((r() * 3) | 0), base = f0 * (giggle ? 1.45 : chuck ? 1.05 : 1.3), sd = giggle ? .085 : chuck ? .16 : .12;
    gap(.04, .15);
    for (let k = 0; k < nSyl; k++) { const last = k === nSyl - 1, prog = k / Math.max(1, nSyl - 1);
      const fk = base * (k < 2 ? 1 + k * .04 : 1.08 - prog * .22) * (1 + (r() - .5) * .08), a = (k < 2 ? .85 + k * .15 : 1 - prog * .45) * (.85 + r() * .3), d = sd * (1 + prog * .35) * (.85 + r() * .3);
      const hd = d * (giggle ? .45 : .35); // «х» в начале слога — выдох через тот же рот
      S.push({ d: hd, f0: [fk, fk], fA: VWL[vw], bw: 1.4, v: [[0, 0], [.7, 0], [1, a * .3]], n: [[0, .05], [.25, a * .9], [1, a * .55]] });
      S.push({ d, f0: [fk * 1.04, fk * .86], fA: VWL[vw], fB: VWL[vw === 'i' ? 'e' : vw], oq: .78, tilt: chuck ? 1400 : 2000, fry: last && !giggle, v: [[0, a * .3], [.12, a], [.55, a * .7], [1, 0]], n: [[0, a * .45], [.4, a * .18], [1, a * .1]] });
      gap((giggle ? .025 : .04) * (.7 + r() * .6), .06 * a); }
    // вдох после смеха: шумный, у детей с тонким «писком»
    const inh = giggle || f0 > 230;
    S.push({ d: .38 + r() * .12, f0: [f0 * 2.1, f0 * 2.4], fA: [420, 2200, 3100], fB: [380, 2500, 3200], bw: 2.2, v: inh ? [[0, 0], [.35, .12], [.7, .08], [1, 0]] : [[0, 0], [1, 0]], n: [[0, .05], [.3, .55], [.8, .45], [1, 0]] });
    if (r() < .6) { gap(.08, .03); const n2 = 2 + ((r() * 2) | 0); for (let k = 0; k < n2; k++) { const fk = base * (.92 - k * .06), a = .55 - k * .12, d = sd * 1.1;
      S.push({ d: d * .35, f0: [fk, fk], fA: VWL[vw], bw: 1.4, v: [[0, 0], [1, a * .3]], n: [[0, .05], [.3, a * .8], [1, a * .5]] });
      S.push({ d, f0: [fk * 1.03, fk * .85], fA: VWL[vw], oq: .78, tilt: 1800, v: [[0, a * .3], [.12, a], [1, 0]], n: [[0, a * .4], [1, .05]] }); gap(.05, .04); } }
  } else if (kind === 'cry') {
    S.push({ d: .14, f0: [f0 * 1.3, f0 * 1.45], fA: VWL.u, v: [[0, 0], [.4, .8], [1, .9]], n: [[0, .2], [1, .1]] });
    S.push({ d: 1.1, f0: [f0 * 1.6, f0 * 1.15], vib: [5.5, .04], fA: VWL.u, fB: VWL.a, oq: .7, v: [[0, .9], [.15, 1], [.5, .8], [.8, .55], [1, 0]], n: [[0, .15], [1, .2]], fry: false });
    for (let k = 0; k < 3; k++) { gap(.06, .02); S.push({ d: .11, f0: [f0 * 1.7, f0 * 1.8], fA: [400, 2200, 3000], bw: 2, v: [[0, 0], [.4, .3], [1, 0]], n: [[0, .5], [.3, .3], [1, 0]] }); }
  } else if (kind === 'yawn') {
    S.push({ d: 1.5, f0: [f0 * 1.35, f0 * .7], curve: .8, fA: [450, 1100, 2500], fB: [650, 950, 2400], oq: .8, tilt: 1300, v: [[0, 0], [.2, .7], [.55, 1], [.85, .5], [1, 0]], n: [[0, .3], [.5, .35], [1, .15]] });
    S.push({ d: .35, f0: [f0 * .7, f0 * .6], fA: [600, 1000, 2400], v: [[0, 0], [1, 0]], n: [[0, .45], [1, 0]] });
  } else if (kind === 'sneeze') {
    S.push({ d: .5, f0: [f0 * 1.1, f0 * 1.55], fA: VWL.a, fB: VWL.i, oq: .8, v: [[0, 0], [.3, .35], [.8, .5], [1, .2]], n: [[0, .4], [1, .35]] });
    gap(.22, 0);
    S.push({ d: .04, f0: [f0, f0], fA: [1500, 2500, 3500], bw: 3, v: [[0, 0], [1, 0]], n: [[0, 1], [1, .7]] });
    S.push({ d: .1, f0: [f0, f0], fA: [2600, 3400, 4200], bw: 2, v: [[0, 0], [1, 0]], n: [[0, .9], [1, .7]] });
    S.push({ d: .22, f0: [f0 * 1.7, f0 * 1.2], fA: VWL.i, oq: .75, v: [[0, 0], [.35, .7], [1, 0]], n: [[0, .7], [.5, .25], [1, 0]] });
  } else if (kind === 'sing') {
    const mel = [[0, .3], [2, .3], [4, .3], [2, .3], [7, .5]].map(([d, t]) => [f0 * 1.15 * Math.pow(2, [0, 2, 4, 5, 7, 9, 11, 12][d] / 12), t]);
    for (const [f, d] of mel) { S.push({ d: .05, f0: [f, f], fA: VWL.l, v: [[0, .1], [1, .5]], n: [[0, 0], [1, 0]] }); S.push({ d: d - .05, f0: [f, f], vib: [5.5, .02], fA: VWL.l, fB: VWL.a, oq: .65, v: [[0, .5], [.15, 1], [.8, .9], [1, 0]], n: [[0, .03], [1, .02]] }); gap(.03, .01); }
  }
  return S;
}
/** Возглас голосом героя. → AudioBuffer (дальше идёт через тот же «тембр», что и речь героя) */
MK.synthVocal = function (ln, sr) {
  sr = sr || 44100; const v = ln.voice || {}, fx = ln.fx || {}, k = fx.k || 1;
  const male = (v.base || 'female') === 'male', kid = ln.age === 'kid';
  let f0 = (male ? 120 : 205) * (kid ? 1.4 : 1) * (v.pitch || 1); f0 /= Math.pow(k, .75);
  const fs = (kid ? 1.17 : 1) * (male ? 1 : 1.1) / Math.pow(k, .4);
  const data = fsynth(vocalSegs(ln.synth, f0, ln.seed || 7, ln.variant || 0), sr, (ln.seed || 7) + (ln.variant || 0), fs, ln.synth === 'laugh' ? .35 : .2);
  const b = new AudioBuffer({ length: data.length, numberOfChannels: 1, sampleRate: sr }); b.copyToChannel(data, 0); return b;
};

// =====================================================================================
// 3. МУЗЫКА: инструменты
// =====================================================================================
const SMP = new WeakMap();
function cache(ac) { let c = SMP.get(ac); if (!c) { c = {}; SMP.set(ac, c); } return c; }
function toBuf(ac, d) { const b = ac.createBuffer(1, d.length, ac.sampleRate); b.copyToChannel(d, 0); return b; }
function ks(sr, f, dur, lossPerSec, soft, seed) { // струна (Карплус — Стронг)
  const n = Math.ceil(dur * sr), d = new Float32Array(n), N = Math.max(2, Math.round(sr / f)), buf = new Float32Array(N), r = rng(seed || 1);
  for (let i = 0; i < N; i++) buf[i] = r() * 2 - 1; for (let s = 0; s < soft; s++) for (let i = 0; i < N; i++) buf[i] = (buf[i] + buf[(i + 1) % N]) * .5;
  let m = 0; for (let i = 0; i < N; i++) m += buf[i]; m /= N; for (let i = 0; i < N; i++) buf[i] -= m;
  const g = Math.pow(lossPerSec, 1 / f); let idx = 0;
  for (let i = 0; i < n; i++) { const a = buf[idx], b = buf[(idx + 1) % N]; buf[idx] = g * (a + b) * .5; d[i] = a; idx = (idx + 1) % N; }
  const fade = Math.min(n, Math.round(.03 * sr)); for (let i = 0; i < fade; i++) d[n - 1 - i] *= i / fade; return d; }
function additive(sr, f, dur, parts, attack, seed) { // колокольчики, пианино, маримба
  const n = Math.ceil(dur * sr), d = new Float32Array(n), r = rng(seed || 3);
  for (const [ratio, amp, dec, det] of parts) { const fr = f * ratio; if (fr > sr * .45) continue; const w = 2 * Math.PI * fr / sr, ph = r() * 6.28, w2 = det ? 2 * Math.PI * fr * (1 + det) / sr : 0;
    for (let i = 0; i < n; i++) { const e = Math.exp(-i / sr / dec); if (e < 1e-4) break; d[i] += amp * e * (Math.sin(w * i + ph) + (det ? Math.sin(w2 * i) : 0) * .7); } }
  const at = Math.round((attack || .002) * sr); for (let i = 0; i < at && i < n; i++) d[i] *= i / at;
  const fade = Math.min(n, Math.round(.05 * sr)); for (let i = 0; i < fade; i++) d[n - 1 - i] *= i / fade;
  let pk = 0; for (let i = 0; i < n; i++) pk = Math.max(pk, Math.abs(d[i])); if (pk) for (let i = 0; i < n; i++) d[i] /= pk; return d; }
function inst(ac, name, midi) {
  const C = cache(ac), key = name + midi; if (C[key]) return C[key]; const sr = ac.sampleRate, f = NOTE(midi); let d;
  switch (name) {
    case 'uke': d = ks(sr, f, 1.6, .03, 1, midi); break;
    case 'harp': d = ks(sr, f, 2.2, .12, 2, midi + 5); break;
    case 'pizz': d = ks(sr, f, .55, .0004, 3, midi + 9); break;
    case 'bass': { d = ks(sr, f, 1.6, .2, 4, midi + 2); const w = 2 * Math.PI * f / sr; for (let i = 0; i < d.length; i++) d[i] = d[i] * .7 + Math.sin(w * i) * Math.exp(-i / sr / .7) * .5; break; }
    case 'piano': { const P = []; for (let h = 1; h <= 9; h++) P.push([h * Math.sqrt(1 + .0004 * h * h), Math.pow(h, -1.4) * (h === 1 ? 1 : .9), (midi < 60 ? 2.4 : 1.6) / Math.pow(h, .65), .0007]); d = additive(sr, f, midi < 60 ? 2.6 : 1.9, P, .003, midi);
      const r = rng(midi); for (let i = 0; i < sr * .006; i++) d[i] += (r() * 2 - 1) * .15 * (1 - i / (sr * .006)); break; }
    case 'glock': d = additive(sr, f, 1.6, [[1, 1, .9], [2.76, .35, .35], [5.4, .18, .18], [8.93, .08, .1]], .001, midi); break;
    case 'celesta': d = additive(sr, f, 1.4, [[1, 1, .8], [2, .3, .4], [3, .12, .25], [4.2, .08, .15]], .002, midi); break;
    case 'mbox': d = additive(sr, f, 1.8, [[1, 1, 1.2], [3, .3, .5], [4.1, .22, .35], [5.6, .1, .2]], .001, midi); break;
    case 'marimba': d = additive(sr, f, 1, [[1, 1, .45], [3.93, .3, .1], [9.2, .06, .04]], .002, midi); break;
    case 'kalimba': d = additive(sr, f, 1.3, [[1, 1, .7], [5.9, .2, .08], [9.1, .05, .05]], .001, midi); break;
    default: d = additive(sr, f, 1, [[1, 1, .5]], .005, midi);
  }
  return (C[key] = toBuf(ac, d)); }
function drum(ac, name) {
  const C = cache(ac), key = 'dr' + name; if (C[key]) return C[key]; const sr = ac.sampleRate, r = rng(name.length * 17 + 3); let n, d;
  const mk = s => { n = Math.ceil(s * sr); d = new Float32Array(n); };
  switch (name) {
    case 'kick': mk(.35); for (let i = 0, ph = 0; i < n; i++) { const t = i / sr, f = 45 + 95 * Math.exp(-t * 28); ph += 2 * Math.PI * f / sr; d[i] = Math.sin(ph) * Math.exp(-t * 9) + (i < 120 ? (r() - .5) * .3 : 0); } break;
    case 'snare': mk(.25); { let lp = 0; for (let i = 0, ph = 0; i < n; i++) { const t = i / sr; ph += 2 * Math.PI * 190 / sr; lp = lp * .35 + (r() * 2 - 1) * .65; d[i] = Math.sin(ph) * Math.exp(-t * 30) * .6 + lp * Math.exp(-t * 16) * .7; } } break;
    case 'clap': mk(.25); for (const o of [0, .011, .022, .034]) for (let i = 0; i < sr * .2; i++) { const j = Math.round(o * sr) + i; if (j >= n) break; d[j] += (r() * 2 - 1) * Math.exp(-i / sr * (o > .03 ? 22 : 90)) * .5; } break;
    case 'shaker': mk(.09); { let x1 = 0; for (let i = 0; i < n; i++) { const t = i / sr, x = r() * 2 - 1, hp = x - x1; x1 = x; d[i] = hp * Math.min(1, t * 120) * Math.exp(-t * 45); } } break;
    case 'tamb': mk(.3); { let x1 = 0; for (let i = 0; i < n; i++) { const t = i / sr, x = r() * 2 - 1, hp = x - x1; x1 = x; d[i] = hp * Math.exp(-t * 14) * .6 + Math.sin(2 * Math.PI * 7200 * t) * Math.exp(-t * 20) * .15; } } break;
    case 'wood': mk(.12); for (let i = 0; i < n; i++) { const t = i / sr; d[i] = (Math.sin(2 * Math.PI * 1050 * t) + Math.sin(2 * Math.PI * 2950 * t) * .4) * Math.exp(-t * 55); } break;
    case 'tick': mk(.04); for (let i = 0; i < n; i++) { const t = i / sr; d[i] = Math.sin(2 * Math.PI * 3200 * t) * Math.exp(-t * 160); } break;
    case 'tri': mk(1.8); for (let i = 0; i < n; i++) { const t = i / sr; d[i] = (Math.sin(2 * Math.PI * 3150 * t) + Math.sin(2 * Math.PI * 8650 * t) * .5 + Math.sin(2 * Math.PI * 5600 * t) * .3) * Math.exp(-t * 2.2) * .5; } break;
    case 'timp': mk(1.6); for (let i = 0, ph = 0; i < n; i++) { const t = i / sr, f = 98 * (1 + .04 * Math.exp(-t * 12)); ph += 2 * Math.PI * f / sr; d[i] = (Math.sin(ph) + Math.sin(ph * 1.5) * .4 + Math.sin(ph * 1.98) * .2) * Math.exp(-t * 2.4) + (i < 300 ? (r() - .5) * .4 : 0); } break;
    case 'chime': mk(2.5); for (let k = 0; k < 7; k++) { const f = 2400 + k * 330 + r() * 80, o = Math.round(k * .055 * sr); for (let i = 0; i + o < n; i++) d[i + o] += Math.sin(2 * Math.PI * f * i / sr) * Math.exp(-i / sr * 2.5) * .25; } break;
    default: mk(.1);
  }
  let pk = 0; for (let i = 0; i < n; i++) pk = Math.max(pk, Math.abs(d[i])); if (pk) for (let i = 0; i < n; i++) d[i] /= pk;
  return (C[key] = toBuf(ac, d)); }
function play(ac, out, buf, t, vol, rate) { if (t < 0) return; const s = ac.createBufferSource(); s.buffer = buf; if (rate) s.playbackRate.value = rate; const g = ac.createGain(); g.gain.value = vol; s.connect(g); g.connect(out); s.start(t); }
function playNote(ac, out, name, midi, t, vol, len) { // len — для обрезки длинных звуков (мягко)
  if (t < 0) return; const s = ac.createBufferSource(); s.buffer = inst(ac, name, midi); const g = ac.createGain(); g.gain.setValueAtTime(vol, t);
  if (len) { g.gain.setValueAtTime(vol, t + len); g.gain.exponentialRampToValueAtTime(.0005, t + len + .25); s.connect(g); g.connect(out); s.start(t); s.stop(t + len + .3); } else { s.connect(g); g.connect(out); s.start(t); } }
// живые «дыхательные» инструменты
function synthVoice(ac, out, kind, midi, t, len, vol, glideFrom) {
  const f = NOTE(midi), g = ac.createGain(); g.connect(out); const end = t + len;
  if (kind === 'pad' || kind === 'strings' || kind === 'brasspad') {
    const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = kind === 'brasspad' ? 1400 : kind === 'strings' ? 2200 : 900; lp.Q.value = .4; lp.connect(g);
    for (const det of [-7, 0, 7]) { const o = ac.createOscillator(); o.type = kind === 'pad' ? 'triangle' : 'sawtooth'; o.frequency.value = f; o.detune.value = det + (kind === 'strings' ? Math.sin(midi) * 3 : 0); const og = ac.createGain(); og.gain.value = det ? .3 : .4; o.connect(og); og.connect(lp); o.start(t); o.stop(end + .9); }
    const at = kind === 'brasspad' ? .12 : .5; g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + at); g.gain.setValueAtTime(vol, end); g.gain.linearRampToValueAtTime(0, end + .8); return; }
  const o = ac.createOscillator(), og = ac.createGain(); o.connect(og); let src = og;
  if (kind === 'flute') { o.type = 'sine'; const o2 = ac.createOscillator(); o2.type = 'triangle'; o2.frequency.value = f * 2; const g2 = ac.createGain(); g2.gain.value = .12; o2.connect(g2); g2.connect(og); o2.start(t); o2.stop(end + .3);
    const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = 5.3; lg.gain.setValueAtTime(0, t); lg.gain.linearRampToValueAtTime(f * .006, t + .35); l.connect(lg); lg.connect(o.frequency); l.start(t); l.stop(end + .3);
    const nb = ac.createBufferSource(); nb.buffer = MK._noise(ac); nb.loop = true; const bp = ac.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = f * 2; bp.Q.value = 3; const ng = ac.createGain(); ng.gain.setValueAtTime(.05, t); ng.gain.exponentialRampToValueAtTime(.01, t + .15); nb.connect(bp); bp.connect(ng); ng.connect(og); nb.start(t); nb.stop(end + .2); }
  else if (kind === 'brass') { o.type = 'sawtooth'; const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 1; lp.frequency.setValueAtTime(500, t); lp.frequency.linearRampToValueAtTime(2600, t + .07); lp.frequency.linearRampToValueAtTime(1500, t + .3); og.disconnect(); og.connect(lp); src = lp; }
  else if (kind === 'bassoon') { o.type = 'square'; const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 900; lp.Q.value = 2; og.disconnect(); og.connect(lp); src = lp; }
  else if (kind === 'theremin') { o.type = 'sine'; const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = 6.2; lg.gain.value = f * .02; l.connect(lg); lg.connect(o.frequency); l.start(t); l.stop(end + .5); }
  else if (kind === 'whistle') { o.type = 'sine'; const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = 6; lg.gain.value = f * .008; l.connect(lg); lg.connect(o.frequency); l.start(t); l.stop(end + .3); }
  if (glideFrom) { o.frequency.setValueAtTime(NOTE(glideFrom), t); o.frequency.exponentialRampToValueAtTime(f, t + .09); } else o.frequency.value = f;
  src.connect(g); const at = kind === 'bassoon' ? .015 : kind === 'brass' ? .04 : kind === 'theremin' ? .12 : .05, rel = kind === 'bassoon' ? .06 : .18;
  og.gain.value = 1; g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + at); g.gain.setValueAtTime(vol * .85, Math.max(t + at, end - rel)); g.gain.linearRampToValueAtTime(0, end + rel);
  o.start(t); o.stop(end + rel + .05);
}

// =====================================================================================
// 4. МУЗЫКА: стили и сочинение
// =====================================================================================
const MAJ = [0, 2, 4, 5, 7, 9, 11], MIN = [0, 2, 3, 5, 7, 8, 10];
const STY = {
  happy:     { bpm: 112, minor: false, prog: [[0, 4, 5, 3], [0, 3, 4, 0], [5, 3, 0, 4]], acc: 'strum', lead: ['glock', 'marimba'], drums: 'pop', mel: [[2, 1, 1, 2, 2], [1, 1, 1, 1, 2, 2], [3, 1, 2, 2], [2, 2, 2, 1, 1]] },
  calm:      { bpm: 80, minor: false, prog: [[0, 5, 3, 4], [0, 3, 5, 4]], acc: 'arp', lead: ['flute', 'piano'], pad: 'pad', mel: [[4, 4], [2, 2, 4], [3, 1, 4], [6, 2]] },
  adventure: { bpm: 122, minor: true, prog: [[0, 5, 2, 6], [0, 3, 6, 4]], acc: 'ostinato', lead: ['brass', 'glock'], pad: 'brasspad', drums: 'march', mel: [[3, 1, 2, 2], [1, 1, 2, 4], [2, 1, 1, 2, 2], [6, 2]] },
  tense:     { bpm: 100, minor: true, prog: [[0, 0, 5, 4], [0, 1, 0, 4]], acc: 'tense', lead: [], pad: 'strings', drums: 'pulse', mel: [] },
  sad:       { bpm: 70, minor: true, prog: [[0, 5, 2, 6], [0, 3, 6, 4]], acc: 'slowarp', lead: ['piano'], pad: 'strings', mel: [[4, 4], [6, 2], [8], [2, 2, 4]] },
  magic:     { bpm: 88, minor: false, sev: true, prog: [[0, 2, 3, 4], [0, 5, 1, 4]], acc: 'sparkle', lead: ['mbox', 'celesta'], pad: 'pad', mel: [[2, 2, 4], [3, 1, 4], [2, 2, 2, 2], [8]] },
  night:     { bpm: 66, minor: false, sev: true, prog: [[0, 5, 1, 4], [0, 3, 0, 4]], acc: 'lullaby', lead: ['mbox'], pad: 'pad', mel: [[4, 4], [2, 2, 4], [8]] },
  funny:     { bpm: 128, minor: false, prog: [[0, 4, 0, 4], [3, 0, 4, 0]], acc: 'oompah', lead: ['bassoon', 'marimba'], drums: 'funny', mel: [[1, 1, 1, 1, 2, 2], [1, 1, 2, 1, 1, 2], [2, 2, 2, 2], [1, 1, 1, 1, 4]] },
  spooky:    { bpm: 84, minor: true, prog: [[0, 3, 0, 4], [0, 5, 3, 4]], acc: 'walk', lead: ['theremin'], pad: 'pad', mel: [[4, 4], [6, 2], [3, 3, 2]] },
};
MK.MOODS = Object.keys(STY).concat(['none']);
function seriesKey(series) { const h = MK.hash32('key' + (series || '')); return 57 + [0, 2, 3, 5, 7, -2][h % 6]; } // своя тональность у каждого сериала
function speechIndex(speech) { const iv = speech.filter(s => !s.vocal || s.dur > .4).map(s => [s.t - .2, s.t + s.dur + .15]).sort((a, b) => a[0] - b[0]); return t => { let lo = 0, hi = iv.length - 1; while (lo <= hi) { const m = (lo + hi) >> 1; if (iv[m][1] < t) lo = m + 1; else if (iv[m][0] > t) hi = m - 1; else return true; } return false; }; }
function scheduleMusic2(ac, out, m, seed, ctx) {
  const S = STY[m.mood] || STY.happy, r = rng(seed), beat = 60 / S.bpm, e8 = beat / 2, bar = beat * 4;
  const key = ctx.key, scale = S.minor ? MIN : MAJ;
  const deg = (dg, chordDeg) => { const o = Math.floor(dg / 7), i = ((dg % 7) + 7) % 7; let n = key + scale[i] + 12 * o; if (S.minor && chordDeg === 4 && i === 6) n += 1; return n; };
  const chordOf = cd => [cd, cd + 2, cd + 4].concat(S.sev ? [cd + 6] : []);
  const g = ac.createGain(); g.connect(out); const fadeIn = m.fadeIn != null ? m.fadeIn : .6;
  g.gain.setValueAtTime(0, m.t0); g.gain.linearRampToValueAtTime(1, m.t0 + fadeIn); g.gain.setValueAtTime(1, Math.max(m.t0 + fadeIn, m.t1 - .8)); g.gain.linearRampToValueAtTime(0, m.t1);
  const rv = ac.createConvolver(); rv.buffer = MK.roomIR(ac, 2.2); const rg = ac.createGain(); rg.gain.value = .28; rv.connect(rg); rg.connect(g);
  const dry = ac.createGain(); dry.connect(g); dry.connect(rv); const leadBus = ac.createGain(); leadBus.gain.value = 1; leadBus.connect(g); const lrv = ac.createGain(); lrv.gain.value = .5; leadBus.connect(lrv); lrv.connect(rv);
  const nb = Math.ceil((m.t1 - m.t0) / bar) + 1, progs = S.prog;
  // мелодия: фраза из 8 тактов — мотив, повтор мотива, новый мотив, каденция
  const phrase = (rr, prog) => { const rh = () => S.mel[(rr() * S.mel.length) | 0]; const A = [rh(), rh()], B = [rh(), rh()]; const rhy = [A[0], A[1], A[0], A[1], B[0], B[1], rh(), rr() < .5 ? [4, 4] : [2, 2, 4]];
    let cur = 7 + ((rr() * 3) | 0), dir = rr() < .5 ? 1 : -1; const bars = []; let motif = null;
    for (let b = 0; b < 8; b++) { const cd = prog[b % prog.length], ch = chordOf(cd).map(x => ((x % 7) + 7) % 7), notes = []; let pos = 0;
      const reuse = (b === 2 || b === 3) && motif ? motif[b - 2] : null;
      rhy[b].forEach((len, j) => { let d;
        if (reuse && reuse[j] != null) { d = reuse[j]; if (pos % 4 === 0) { let best = d, bd = 9; for (let q = d - 3; q <= d + 3; q++) if (ch.includes(((q % 7) + 7) % 7) && Math.abs(q - d) < bd) { bd = Math.abs(q - d); best = q; } d = best; } }
        else if (pos % 4 === 0 || len >= 4) { let best = cur, bd = 9; for (let q = cur - 3; q <= cur + 3; q++) if (ch.includes(((q % 7) + 7) % 7)) { const dd = Math.abs(q - cur) + (Math.sign(q - cur) === dir ? -.4 : 0) + rr() * .6; if (dd < bd) { bd = dd; best = q; } } d = best; }
        else { d = cur + (rr() < .75 ? dir : dir * 2); }
        if (d > 13) { d = 12; dir = -1; } if (d < 4) { d = 5; dir = 1; } if (rr() < .2) dir = -dir;
        if (b === 7 && j === rhy[b].length - 1) d = 7;
        const rest = len <= 2 && j > 0 && rr() < .08; notes.push({ pos, len, d, rest, cd }); cur = d; pos += len; });
      if (b === 0 || b === 1) { motif = motif || []; motif[b] = notes.map(n => n.d); }
      bars.push(notes); }
    return bars; };
  const themeR = rng(ctx.themeSeed || seed); const phA = S.mel.length ? phrase(themeR, progs[0]) : null, phB = S.mel.length ? phrase(rng(seed + 11), progs[(1 % progs.length)]) : null;
  const form = [phA, phA, phB, phA];
  const ac8 = (t, n) => t + n * e8, swing = 0;
  for (let b = 0; b < nb; b++) {
    const t = m.t0 + b * bar; if (t > m.t1) break; const sec = Math.floor(b / 8), ph = form[sec % form.length], pb = b % 8;
    const prog = sec % form.length === 2 ? progs[1 % progs.length] : progs[0]; const cd = prog[pb % prog.length], chord = chordOf(cd).map(x => deg(x, cd));
    const root = deg(cd, cd), five = deg(cd + 4, cd), low = n => { while (n > 52) n -= 12; while (n < 40) n += 12; return n; }, mid = n => { while (n > 71) n -= 12; while (n < 57) n += 12; return n; };
    const voic = chord.map(mid).sort((a, c) => a - c);
    const quiet = ctx.speaking(t + bar * .5); // под репликой аккомпанемент мягче
    const A = quiet ? .75 : 1;
    // аккомпанемент
    switch (S.acc) {
      case 'strum': [1, 0, 1, 1, 0, 1, 1, 1].forEach((on, i) => { if (!on) return; const down = i % 2 === 0, ns = down ? voic : voic.slice(1).reverse(); ns.forEach((n, j) => playNote(ac, dry, 'uke', n, ac8(t, i) + j * .014, (down ? .07 : .045) * A)); });
        playNote(ac, dry, 'bass', low(root), t, .32, beat * 1.8); playNote(ac, dry, 'bass', low(five), t + 2 * beat, .26, beat * 1.8); break;
      case 'arp': { const pat = [low(root) + 12, voic[0], voic[1], voic[2], voic[0] + 12, voic[2], voic[1], voic[0]]; pat.forEach((n, i) => playNote(ac, dry, 'piano', n, ac8(t, i), (i === 0 ? .2 : .13) * A));
        playNote(ac, dry, 'piano', low(root), t, .22); break; }
      case 'ostinato': { const pat = [0, 0, 2, 0, 0, 2, 1, 2]; pat.forEach((ix, i) => playNote(ac, dry, 'pizz', low(chord[ix]) + 12, ac8(t, i), (i % 2 ? .16 : .22) * A)); playNote(ac, dry, 'bass', low(root), t, .3, beat * 1.5); playNote(ac, dry, 'bass', low(root), t + beat * 2.5, .24, beat); break; }
      case 'tense': { for (let i = 0; i < 8; i++) playNote(ac, dry, 'pizz', low(root) + (i === 6 ? 1 : 0), ac8(t, i), (i % 4 === 0 ? .3 : .17)); if (b % 2 === 1 && r() < .7) playNote(ac, leadBus, 'celesta', mid(chord[(r() * 3) | 0]) + 24, t + beat * (1 + ((r() * 2) | 0)), .1); break; }
      case 'slowarp': { [low(root), voic[0], voic[2], voic[1]].forEach((n, i) => playNote(ac, dry, 'piano', n, t + i * beat, (i ? .12 : .17) * A)); break; }
      case 'sparkle': { const up = chord.map(n => mid(n) + 12).sort((a, c) => a - c), seq = up.concat(up.map(n => n + 12)).concat(up.slice().reverse().map(n => n + 12)).concat(up.slice().reverse()); for (let i = 0; i < 16; i++) playNote(ac, dry, 'celesta', seq[i % seq.length], t + i * e8 / 2, .055 * A); if (b % 4 === 0) play(ac, dry, drum(ac, 'chime'), t, .08); playNote(ac, dry, 'harp', low(root) + 12, t, .14); break; }
      case 'lullaby': { playNote(ac, dry, 'piano', low(root), t, .14); playNote(ac, dry, 'piano', low(five) + 12, t + 2 * beat, .09); [voic[0], voic[1], voic[2], voic[1]].forEach((n, i) => playNote(ac, dry, 'harp', n + 12, t + i * beat, .06 * A)); break; }
      case 'oompah': { synthVoice(ac, dry, 'bassoon', low(root), t, beat * .45, .16); synthVoice(ac, dry, 'bassoon', low(five), t + 2 * beat, beat * .45, .14); for (const bq of [1, 3]) voic.forEach((n, j) => playNote(ac, dry, 'pizz', n, t + bq * beat + j * .005, .1 * A)); break; }
      case 'walk': { const ln = [0, 2, 3, 4].map(x => low(deg(cd + x, cd))); ln.forEach((n, i) => playNote(ac, dry, 'pizz', n, t + i * beat, .26)); if (b % 2 === 0) playNote(ac, leadBus, 'celesta', mid(root) + 24 + 1, t + beat * 3.5, .05); break; }
    }
    if (S.pad && (b % 2 === 0)) for (const n of voic) synthVoice(ac, dry, S.pad, n - (S.pad === 'pad' ? 0 : 12), t, bar * 2 - .2, S.pad === 'brasspad' ? .025 : .03);
    // ударные
    const D = (nm, at, v) => play(ac, dry, drum(ac, nm), at, v * A);
    if (S.drums === 'pop') { D('kick', t, .32); D('kick', t + 2 * beat, .28); D('clap', t + beat, .14); D('clap', t + 3 * beat, .14); for (let i = 0; i < 8; i++) D('shaker', ac8(t, i), i % 2 ? .07 : .04); if (pb === 7) D('tamb', t + 3.5 * beat, .1); }
    if (S.drums === 'march') { D('kick', t, .32); D('kick', t + 1.5 * beat, .22); D('kick', t + 2 * beat, .28); D('snare', t + beat, .16); D('snare', t + 3 * beat, .16); for (let i = 0; i < 8; i++) D('tamb', ac8(t, i), .035); if (b % 4 === 0) D('timp', t, .3); if (pb === 7) for (let i = 0; i < 4; i++) D('snare', t + 3 * beat + i * e8 / 2, .08 + i * .03); }
    if (S.drums === 'pulse') { D('timp', t, .28); D('timp', t + 2 * beat, .16); for (let i = 0; i < 8; i++) D('tick', ac8(t, i), .05); }
    if (S.drums === 'funny') { D('kick', t, .22); D('kick', t + 2 * beat, .2); for (let i = 1; i < 8; i += 2) D('wood', ac8(t, i), .1); }
    if (pb === 0 && b > 0 && b % 8 === 0 && S.drums) play(ac, dry, drum(ac, 'chime'), t, .05);
    // мелодия — только там, где никто не говорит
    if (S.lead.length && ph) { const lead = S.lead[(sec + (ctx.leadShift || 0)) % S.lead.length]; let prev = null;
      for (const nt of ph[pb]) { if (nt.rest) continue; const at = ac8(t, nt.pos), len = nt.len * e8; if (at >= m.t1 - .3) continue; if (ctx.speaking(at) || ctx.speaking(at + Math.min(len, .4))) { prev = null; continue; }
        const midi = deg(nt.d, cd) + 12 * (lead === 'bassoon' ? -1 : lead === 'theremin' ? 0 : 0);
        if (['flute', 'brass', 'bassoon', 'theremin', 'whistle'].includes(lead)) synthVoice(ac, leadBus, lead, midi, at, Math.max(.12, len * (lead === 'bassoon' ? .5 : .92)), lead === 'brass' ? .07 : lead === 'bassoon' ? .11 : .09, lead === 'theremin' ? prev : null);
        else playNote(ac, leadBus, lead, midi + (lead === 'glock' || lead === 'mbox' || lead === 'celesta' ? 12 : 0), at, lead === 'piano' ? .2 : lead === 'marimba' ? .2 : .13);
        prev = midi; } }
  }
}

// =====================================================================================
// 5. ЗВУКИ МЕСТА И УЛУЧШЕННЫЕ ЭФФЕКТЫ
// =====================================================================================
function loopNoise(ac, out, t0, t1, type, freq, q, vol, lfo) { const s = ac.createBufferSource(); s.buffer = MK._noise(ac); s.loop = true; const f = ac.createBiquadFilter(); f.type = type; f.frequency.value = freq; if (q) f.Q.value = q; const g = ac.createGain(); s.connect(f); f.connect(g); g.connect(out);
  g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(vol, t0 + 1); g.gain.setValueAtTime(vol, Math.max(t0 + 1, t1 - 1)); g.gain.linearRampToValueAtTime(0, t1);
  if (lfo) { const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = lfo[0]; lg.gain.value = vol * lfo[1]; l.connect(lg); lg.connect(g.gain); l.start(t0); l.stop(t1); }
  s.start(t0, (t0 * 7.3) % .9); s.stop(t1); return { s, f, g }; }
function chirp(ac, out, t, f0, f1, d, v) { const o = ac.createOscillator(), g = ac.createGain(); o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + d); const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = 38; lg.gain.value = f0 * .04; l.connect(lg); lg.connect(o.frequency);
  g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t + d * .2); g.gain.exponentialRampToValueAtTime(.0005, t + d); o.connect(g); g.connect(out); o.start(t); o.stop(t + d + .02); l.start(t); l.stop(t + d + .02); }
function scheduleAmbience(ac, out, seg, seed) {
  const L = seg.lspec || {}, type = L.type || 'meadow', time = L.time || 'day', night = time === 'night', r = rng(seed), t0 = seg.t0, t1 = seg.t1, outdoor = !/^(room|kitchen|space)$/.test(type);
  const weather = L.weather || (type === 'winter' ? 'snow' : 'none');
  if (outdoor && type !== 'street' && type !== 'beach') loopNoise(ac, out, t0, t1, 'bandpass', 500, .6, .012, [.11, .5]); // лёгкий ветерок
  if (outdoor && !night && type !== 'street' && type !== 'winter' && weather !== 'rain') { // птицы
    for (let t = t0 + .5 + r() * 2; t < t1 - 1; t += 1.6 + r() * 3.2) { const bird = (r() * 3) | 0, n = 2 + ((r() * 5) | 0), base = [2600, 3400, 4300][bird] * (.9 + r() * .2);
      for (let k = 0; k < n; k++) { const tt = t + k * (bird === 2 ? .09 : .14), up = r() < .5; chirp(ac, out, tt, base * (up ? .85 : 1.15), base * (up ? 1.25 : .8), bird === 2 ? .06 : .1, .012 + r() * .01); } } }
  if (outdoor && (night || time === 'evening') && type !== 'winter' && type !== 'street') { // сверчки
    for (let t = t0 + r(); t < t1 - .5; t += .7 + r() * 1.1) { const f = 4200 + r() * 600, n = 3 + ((r() * 4) | 0); for (let k = 0; k < n; k++) { const tt = t + k * .045, o = ac.createOscillator(), g = ac.createGain(); o.frequency.value = f; g.gain.setValueAtTime(0, tt); g.gain.linearRampToValueAtTime(night ? .012 : .006, tt + .008); g.gain.linearRampToValueAtTime(0, tt + .03); o.connect(g); g.connect(out); o.start(tt); o.stop(tt + .035); } }
    if (night && (seg.theme === 'halloween' || r() < .5)) for (let t = t0 + 3 + r() * 4; t < t1 - 2; t += 9 + r() * 8) for (const [dt, f] of [[0, 380], [.45, 360], [.62, 340]]) { const o = ac.createOscillator(), g = ac.createGain(); o.frequency.setValueAtTime(f * 1.05, t + dt); o.frequency.linearRampToValueAtTime(f, t + dt + .25); g.gain.setValueAtTime(0, t + dt); g.gain.linearRampToValueAtTime(.025, t + dt + .06); g.gain.linearRampToValueAtTime(0, t + dt + .3); o.connect(g); g.connect(out); o.start(t + dt); o.stop(t + dt + .32); } }
  if (type === 'beach') { for (let t = t0; t < t1; t += 6.5 + r() * 2) { const w = loopNoise(ac, out, t, Math.min(t1, t + 7), 'lowpass', 700, .5, .0001); w.g.gain.cancelScheduledValues(t); w.g.gain.setValueAtTime(.002, t); w.g.gain.linearRampToValueAtTime(.06, t + 3); w.g.gain.linearRampToValueAtTime(.09, t + 3.4); w.g.gain.linearRampToValueAtTime(.002, Math.min(t1, t + 7)); w.f.frequency.setValueAtTime(400, t); w.f.frequency.linearRampToValueAtTime(1600, t + 3.4); w.f.frequency.linearRampToValueAtTime(500, t + 7); }
    for (let t = t0 + 4 + r() * 5; t < t1 - 1; t += 10 + r() * 10) for (let k = 0; k < 3; k++) chirp(ac, out, t + k * .35, 1500, 1100, .3, .015); }
  if (type === 'street') { loopNoise(ac, out, t0, t1, 'lowpass', 220, .5, .05); for (let t = t0 + 2 + r() * 4; t < t1 - 3; t += 6 + r() * 8) { const c = loopNoise(ac, out, t, t + 3.2, 'bandpass', 300, 1.2, .0001); c.g.gain.cancelScheduledValues(t); c.g.gain.setValueAtTime(.0001, t); c.g.gain.linearRampToValueAtTime(.05, t + 1.6); c.g.gain.linearRampToValueAtTime(.0001, t + 3.2); c.f.frequency.setValueAtTime(260, t); c.f.frequency.linearRampToValueAtTime(700, t + 1.6); c.f.frequency.linearRampToValueAtTime(300, t + 3.2); } }
  if (type === 'room') { loopNoise(ac, out, t0, t1, 'lowpass', 160, .5, .01); for (let t = t0 + .3; t < t1; t += 1) play(ac, out, drum(ac, 'tick'), t, .012); }
  if (type === 'kitchen') { loopNoise(ac, out, t0, t1, 'lowpass', 160, .5, .01); const o = ac.createOscillator(), g = ac.createGain(); o.frequency.value = 100; g.gain.value = .004; o.connect(g); g.connect(out); o.start(t0); o.stop(t1); }
  if (type === 'space') { for (const f of [55, 82.4, 110.6]) { const o = ac.createOscillator(), g = ac.createGain(); o.frequency.value = f; g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(.012, t0 + 2); g.gain.setValueAtTime(.012, Math.max(t0 + 2, t1 - 1)); g.gain.linearRampToValueAtTime(0, t1); o.connect(g); g.connect(out); o.start(t0); o.stop(t1); } }
  if (weather === 'rain') { loopNoise(ac, out, t0, t1, 'bandpass', 2600, .4, .05); for (let t = t0; t < t1; t += .03 + r() * .12) { const s = ac.createBufferSource(); s.buffer = drum(ac, 'tick'); s.playbackRate.value = .4 + r() * .5; const g = ac.createGain(); g.gain.value = .006 + r() * .01; s.connect(g); g.connect(out); s.start(t); } }
  if (weather === 'snow' || type === 'winter') loopNoise(ac, out, t0, t1, 'bandpass', 700, .8, .03, [.08, .6]);
}
const SFX2 = Object.assign({}, MK._SFX, {
  step: (ac, o, t) => { MK._noiseHit(ac, o, t, .07, .22, 'lowpass', 800); MK._tone(ac, o, t, 110, 70, .05, .1); },
  tap: (ac, o, t) => { MK._noiseHit(ac, o, t, .04, .2, 'bandpass', 2200, 1.5); MK._tone(ac, o, t, 420, 260, .03, .12, 'triangle'); },
  crunch: (ac, o, t) => { for (let i = 0; i < 4; i++) MK._noiseHit(ac, o, t + i * .012, .05, .12, 'bandpass', 1800 + i * 600, 1); },
  laugh: (ac, o, t) => { for (const [seed, pitch, dt] of [[3, 1.1, 0], [7, .95, .12], [12, 1.05, .2]]) { const b = MK.synthVocal({ synth: 'laugh', voice: { base: seed === 7 ? 'male' : 'female', pitch }, fx: {}, age: seed === 7 ? 'adult' : 'kid', seed }, ac.sampleRate); play(ac, o, b, t + dt, .45); } },
  meow: (ac, o, t) => {
    const segs = [{ d: .12, f0: [520, 680], fA: VWL.i, fB: VWL.e, v: [[0, 0], [.4, .8], [1, 1]], n: [[0, .05], [1, .02]] }, { d: .32, f0: [700, 480], fA: VWL.e, fB: VWL.u, v: [[0, 1], [.7, .7], [1, 0]], n: [[0, .02], [1, .02]] }];
    play(ac, o, toBuf(ac, fsynth(segs, ac.sampleRate, 5, 1.3, .08)), t, .7); },
  bark: (ac, o, t) => { for (let k = 0; k < 2; k++) { const segs = [{ d: .03, f0: [300, 320], fA: VWL.h, v: [[0, 0], [1, .2]], n: [[0, .9], [1, .4]] }, { d: .13, f0: [330, 240], fA: VWL.a, fB: VWL.o, v: [[0, .6], [.2, 1], [1, 0]], n: [[0, .5], [1, .1]], bw: 1.8 }];
    play(ac, o, toBuf(ac, fsynth(segs, ac.sampleRate, 7 + k, 1, .4)), t + k * .28, .8); } },
});
MK.SFX = Object.keys(SFX2);

// =====================================================================================
// 6. СВЕДЕНИЕ
// =====================================================================================
MK.mixAudio = async function (tl, buffers) {
  const sr = 44100, len = Math.ceil((tl.dur + .5) * sr);
  const ac = new OfflineAudioContext(1, len, sr);
  const master = ac.createDynamicsCompressor(); master.threshold.value = -14; master.ratio.value = 3; master.attack.value = .01; master.release.value = .2; master.connect(ac.destination);
  const speaking = speechIndex(tl.speech || []);
  const musicBus = ac.createGain(); musicBus.gain.value = (tl.ep.musicVolume != null ? tl.ep.musicVolume : .5); musicBus.connect(master);
  const duck = ac.createGain(); duck.connect(musicBus); duck.gain.setValueAtTime(1, 0);
  const ambOn = ac.createGain(); ambOn.gain.value = tl.ep.ambience === false ? 0 : 1; ambOn.connect(master); const amb = ac.createGain(); amb.connect(ambOn);
  for (const s of tl.speech) { for (const g of [duck.gain, amb.gain]) { const lo = g === duck.gain ? .38 : .6; g.setValueAtTime(g === duck.gain ? 1 : 1, Math.max(0, s.t - .2)); g.linearRampToValueAtTime(lo, s.t); g.setValueAtTime(lo, s.t + s.dur); g.linearRampToValueAtTime(1, s.t + s.dur + .4); } }
  const key = seriesKey(tl.ep.series), themeSeed = MK.hash32('theme' + (tl.ep.series || ''));
  const endSeg = tl.segs.find(sg => sg.kind === 'end');
  tl.music.forEach((m, i) => { if (m.mood === 'none') return; const isTheme = (i === 0 && m.t0 < .1) || (endSeg && m.t0 >= endSeg.t0 - .1);
    scheduleMusic2(ac, duck, m, MK.hash32((tl.ep.series || '') + (tl.ep.episode || 0) + i + m.mood), { key, speaking, themeSeed: isTheme ? themeSeed : null, leadShift: i }); });
  for (const sg of tl.segs) if (sg.kind === 'scene') scheduleAmbience(ac, amb, sg, MK.hash32('amb' + sg.t0));
  const fx = ac.createGain(); fx.gain.value = .45; const fxlp = ac.createBiquadFilter(); fxlp.type = 'lowpass'; fxlp.frequency.value = 7000; fx.connect(fxlp); fxlp.connect(master);
  for (const s of tl.sfx) { const f = SFX2[s.n]; if (!f) continue; let o = fx; if (s.v != null) { o = ac.createGain(); o.gain.value = s.v; o.connect(fx); } for (let i = 0; i < (s.rep || 1); i++) f(ac, o, s.t + i * (s.gap || .22)); }
  const vo = ac.createGain(); vo.gain.value = 1.0; vo.connect(master);
  for (const s of tl.speech) { const b = buffers && buffers[s.key]; if (!b) continue; const src = ac.createBufferSource(); src.buffer = b; src.connect(vo); src.start(s.t); }
  const out = await ac.startRendering(); const d = out.getChannelData(0); let pk = 0; for (let i = 0; i < d.length; i++) { const a = Math.abs(d[i]); if (a > pk) pk = a; }
  if (pk > 0) { const g = .89 / pk; for (let i = 0; i < d.length; i++) d[i] *= g; }
  return out;
};
MK._audioTest = { scheduleMusic2, scheduleAmbience, STY, fsynth, vocalSegs, seriesKey };
})(typeof window !== 'undefined' ? window : globalThis);
