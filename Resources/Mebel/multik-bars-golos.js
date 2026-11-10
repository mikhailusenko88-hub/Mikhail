// БАРС-озвучка · голоса. Управляемый нейроголос: «режиссёр» задаёт длительность и высоту каждого звука модели.
// Что умеет: паспорт голоса (тон и тембр раздельно, без «бурундука»), живость интонации и эмоции,
// смех голосом героя в ритме и мелодии настоящего смеха, звуки зверей и возгласы тем же голосом («мяу», «гав», «ку-ку»),
// протяжные слова («Ура-а-а!»), пение по нотам. Работает там же, где нейроголос (страница voice.html), звук 48 кГц.
// Вызов: MKVoice.speak(text, { model, speaker, lex, bars: {…} }) — всё описание в bars (обычный JSON, проходит через мост iPhone).
(function (global) {
  'use strict';
  const VOW = 'аеёиоуыэюя', G = { v: 1 };
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  const st2p = (st, coef) => coef * (Math.pow(2, st / 12) - 1);            // полутоны от средней высоты голоса → значение для модели
  const p2st = (p, coef) => 12 * Math.log2(Math.max(.05, (p + coef) / coef));
  const hash32 = s => { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h; };
  G.st2p = st2p; G.p2st = p2st; G.hash32 = hash32;

  /** Тон и тембр раздельно: модель говорит медленнее и ниже в F раз, потом запись проигрывается в F раз быстрее —
      «трубка» голоса короче в F раз (детский, звериный тембр), а высота и темп остаются какими заданы. Без растяжки звука. */
  G.resample = function (y, F) { if (Math.abs(F - 1) < .004) return y; const n = Math.floor((y.length - 2) / F), out = new Float32Array(n);
    for (let i = 0; i < n; i++) { const x = i * F, j = Math.floor(x), f = x - j, a = y[Math.max(0, j - 1)], b = y[j], c = y[j + 1], d = y[Math.min(y.length - 1, j + 2)];
      out[i] = b + .5 * f * (c - a + f * (2 * a - 5 * b + 4 * c - d + f * (3 * (b - c) + d - a))); } return out; };

  // ---------- каталог голосов: люди и звери ----------
  // Все голоса — свободные (Silero v5 CIS, MIT). P — тон, F — тембр («трубка» голоса), T — темп, R — живость интонации.
  // Оценки естественности (UTMOS) и распознавание слов — в tools/multik/OZVUCHKA.md. Голос герою назначается явно (c.golos), сам ни у кого не меняется.
  G.CATALOG = {
    girl:    { name: 'девочка', speaker: 'ru_aigul', F: 1.12, P: 1.12, R: 1.15 },
    boy:     { name: 'мальчик', speaker: 'ru_zara', F: 1.07, P: .96, R: 1.15 },
    mom:     { name: 'мама', speaker: 'ru_alfia', R: 1.1 },
    dad:     { name: 'папа', speaker: 'ru_miyau', R: 1.1 },
    granny:  { name: 'бабушка', speaker: 'ru_zinaida', F: .97, P: .92, T: .9 },
    grandpa: { name: 'дедушка', speaker: 'ru_kejilgan', F: .96, P: .9, T: .92 },
    bear:    { name: 'медведь', speaker: 'ru_alexandr', F: .88, P: .84, T: .92 },
    fox:     { name: 'лиса', speaker: 'ru_zara', P: 1.02, R: 1.3 },
    tiny:    { name: 'крошка (птенчик, ёжик, белочка)', speaker: 'ru_alfia', F: 1.2, P: 1.4, R: 1.1 },
    owl:     { name: 'сова', speaker: 'ru_nurgul', P: .95, T: .97, pause: .6 },   // у этого голоса запятая тянется больше секунды — паузы укорачиваем
    wolf:    { name: 'волк', speaker: 'ru_kejilgan', F: .94, P: .9 },
    giant:   { name: 'великан', speaker: 'ru_safarhuja', F: .84, P: .78, T: .9 },
  };
  /** Какой голос каталога подходит герою по виду, возрасту и полу — подсказка для выбора в «🎙 Голос». */
  G.typeFor = function (spec) { spec = spec || {}; const k = spec.kind, male = (spec.voice || {}).base === 'male', age = spec.age || 'kid';
    if (k === 'human' || !k) return age === 'old' ? (male ? 'grandpa' : 'granny') : age === 'adult' ? (male ? 'dad' : 'mom') : (male ? 'boy' : 'girl');
    if (/^(mouse|chick|squirrel|hedgehog|bird|frog|bee|bug)$/.test(k)) return 'tiny'; if (/^(bear|elephant|lion|hippo)$/.test(k)) return 'bear'; if (/^(dragon|giant|monster)$/.test(k)) return 'giant';
    if (k === 'owl') return 'owl'; if (k === 'fox') return 'fox'; if (k === 'wolf') return 'wolf';
    return age === 'old' ? (male ? 'grandpa' : 'granny') : age === 'adult' ? (male ? 'dad' : 'mom') : (male ? 'boy' : 'girl'); };

  // ---------- эмоции: тон, темп, размах интонации, дрожь ----------
  G.EMO = { happy: { P: 1.03, T: 1.03, R: 1.2 }, laugh: { P: 1.04, T: 1.05, R: 1.25 }, sad: { P: .96, T: .9, R: .75 }, cry: { P: 1, T: .88, R: .9, trem: .7 },
    angry: { P: .97, T: 1.05, R: 1.15 }, surprised: { P: 1.06, T: 1, R: 1.4 }, scared: { P: 1.06, T: 1.08, R: 1.15, trem: .5 }, sleepy: { P: .95, T: .82, R: .7 },
    love: { P: 1, T: .93, R: 1 }, shy: { P: 1.02, T: .9, R: .8 }, shout: { P: 1.07, T: 1, R: 1.3 } };

  /** Живость: размах интонации вокруг средней высоты ×R (R > 1 — выразительнее), дрожь голоса trem (полутоны). */
  G.liveShape = (R, trem) => c => { let k = 0; for (let i = 0; i < c.N; i++) if (Math.abs(c.pitch[i]) > .001) { let s = p2st(c.pitch[i], c.coef) * R; if (trem && VOW.includes(c.toks[i])) s += (k++ % 2 ? -trem : trem); c.pitch[i] = st2p(s, c.coef); } };

  /** Паузы на знаках не длиннее sec секунд (на «?», «!», «…» внутри реплики — в полтора раза длиннее). Нужно голосам, у которых запятая тянется больше секунды. */
  G.pauseShape = (sec, F) => c => { const cap = Math.max(4, Math.round(sec * (F || 1) / c.frame)), cap2 = Math.round(cap * 1.5);
    for (let i = 1; i < c.N - 3; i++) { const t = c.toks[i]; if (',;:—–-'.includes(t)) { if (c.d[i] > cap) c.d[i] = cap; } else if ('.!?…'.includes(t)) { if (c.d[i] > cap2) c.d[i] = cap2; } } };

  // ================= БАРС-актёр: эмоция реплики → игра голосом =================
  // Раньше эмоция только сдвигала весь голос выше-ниже и быстрее-медленнее. Теперь у каждой эмоции свой рисунок:
  // высота (reg, полутоны) и размах мелодии (R), наклон фразы (decl), высокий вход (onset), удар на ударных слогах (acc, accDur) и на главном слове (key, keyDur),
  // конец фразы (fin), темп (T), паузы (pause), безударные слоги (unstr); тембр и подача (fx): светлее/глуше (tilt, дБ), дыхание (breath), дрожь голоса (vib),
  // дрожание громкости (tremolo), надрыв (sat), шёпот (whisper: 1 — полный, меньше — пополам с голосом; настройки w2), рот в улыбке (F), громкость относительно обычной реплики (level).
  // k — сила игры (1 — как записано, 0 — ровно). Числа подобраны по распознавателю эмоций, распознаванию слов и естественности — см. OZVUCHKA.md.
  G.ACT = {
    happy:     { reg: 2.5, R: 1.6, span: 10, acc: .5, key: 2.5, keyDur: 1.14, T: 1.07, pause: .88, fx: { tilt: 3, F: 1.03 } },   // F обязателен: без него модель поёт слишком высоко и смазывает слова («нашли клад» → «наш веклад»)
    surprised: { reg: 2.5, R: 1.75, span: 12, onset: 2.5, key: 3, keyDur: 1.3, fin: 1, T: .97, fx: { tilt: 2 } },
    scared:    { reg: 4.5, R: .75, span: 5, key: 1, T: 1.15, pause: .7, fx: { vib: .04, tremolo: .22, breath: .08 } },
    sad:       { reg: -3, R: .5, span: 4, decl: 3, fin: -2, T: .8, pause: 1.6, unstr: 1.08, fx: { tilt: -7, level: .85 } },
    cry:       { reg: 1.5, R: .65, span: 5, decl: 3, fin: -2, T: .8, pause: 1.6, fx: { vib: .055, tremolo: .4, tilt: -2 } },
    angry:     { reg: -2, R: 1.2, span: 9, decl: 3, fin: -2.5, accDur: 1.2, unstr: .85, T: 1.1, pause: .7, fx: { tilt: 6, sat: .45, level: 1.1 } },
    sleepy:    { reg: -2.5, R: .55, span: 4, decl: 2, T: .82, pause: 1.6, fx: { tilt: -5, level: .85 } },
    love:      { reg: .5, R: .9, T: .9, pause: 1.15, fx: { tilt: -2, breath: .08 } },
    shy:       { reg: 1, R: .7, span: 4.5, T: .9, pause: 1.3, fx: { tilt: -3, breath: .1, level: .85 } },
    shout:     { reg: 3, R: 1.2, span: 8, accDur: 1.2, key: 1.5, T: .97, fx: { tilt: 3, level: 1.25 } },
    // «(шёпотом)»: пока Михаил не выбрал на слух — просто тихий мягкий голос (безопасно). Варианты настоящего шёпота — пробы Э8в–Э8д:
    //   полушёпот { reg: -3, R: .6, T: .88, pause: 1.2, fx: { whisper: .65, tilt: -4 } }; шёпот { reg: -6, R: .5, T: .88, pause: 1.2, fx: { whisper: 1, w2: { gu: .55 } } };
    //   шёпот глуше — w2: { tilt: 0, lp: 4500, gv: .4, gu: .55 }. Исходник для шёпота нарочно низкий (reg −6): у высокого голоса «форма рта» снимается хуже.
    whisper:   { reg: -2.5, R: .55, T: .88, pause: 1.25, fx: { tilt: -7, level: .6 } },
    laugh:     { reg: 2.5, R: 1.4, span: 9, T: 1.06, fx: { tilt: 3, tremolo: .25, vib: .025 } },
  };
  const A_STOP = new Set('и а но да не ни же бы ли то вот ну это я ты он она оно мы вы они мне тебе его её ее их нас вас в во на с со к ко у о об по за из от до для под над при без про что как где когда там тут здесь уже ещё еще тоже только был была было были есть'.split(' '));
  const A_BOOST = new Set('очень совсем так такой такая такое такие какой какая какое какие самый самая самое самые никогда всегда ничего никто никого вообще совершенно ужасно страшно'.split(' '));
  const A_WH = new Set('кто что где куда откуда когда почему зачем как какой какая какое какие чей сколько'.split(' '));
  /** Главное слово фразы (на него голос «нажимает»): вопросительное слово, слово после «не», усилитель («очень», «какой»), в вопросе — глагол, иначе последнее полнозначное. */
  G.keyWord = function (ws, q) { if (q) { const k = ws.findIndex(w => A_WH.has(w)); if (k >= 0 && k < 3) return k; }
    for (let i = 0; i < ws.length - 1; i++) if (ws[i] === 'не' && !A_STOP.has(ws[i + 1])) return i + 1;
    const b = ws.findIndex(w => A_BOOST.has(w)); if (b >= 0) return b;
    if (q) { const v = ws.findIndex(w => w.length > 3 && !A_STOP.has(w) && /(ешь|ёшь|ишь|ете|ёте|ите|ет|ёт|ит|ут|ют|ат|ят|ал|ял|ил|ел|ла|ли|ло)$/.test(w)); if (v >= 0) return v; }
    for (let i = ws.length - 1; i >= 0; i--) if (!A_STOP.has(ws[i]) && ws[i].length > 2) return i; return ws.length - 1; };
  /** «Режиссёр» эмоции: правит высоту и длительность звуков модели по рисунку a (из G.ACT), k — сила. */
  G.actShape = (a, k) => c => { const { toks, pitch, d, coef, N } = c, fr = c.frame, K = k == null ? 1 : k, mul = x => 1 + ((x == null ? 1 : x) - 1) * K, add = x => (x || 0) * K;
    const voiced = i => Math.abs(pitch[i]) > .001, isV = i => VOW.includes(toks[i]), isL = i => /[а-яё+]/.test(toks[i] || '');
    const t = new Float64Array(N + 1); for (let i = 0; i < N; i++) t[i + 1] = t[i] + d[i] * fr;         // когда начинается каждый звук, секунды
    const sents = []; let a0 = 1; for (let i = 1; i < N; i++) if ('.!?…'.includes(toks[i]) || i === N - 1) { if (i > a0) sents.push([a0, i, toks[i]]); a0 = i + 1; }
    for (const [sa, sb, end] of sents) {
      const words = []; let w0 = -1; for (let i = sa; i <= sb; i++) { const L = i < sb && (isL(i) || (toks[i] === '-' && w0 >= 0 && isL(i + 1)));
        if (L) { if (w0 < 0) w0 = i; } else if (w0 >= 0) { words.push([w0, i]); w0 = -1; } }
      if (!words.length) continue;
      const sv = w => { for (let i = w[0]; i < w[1] - 1; i++) if (toks[i] === '+') return i + 1; for (let i = w[0]; i < w[1]; i++) if (isV(i)) return i; return -1; };   // ударная гласная слова
      const ws = words.map(w => toks.slice(w[0], w[1]).join('').replace(/\+/g, '')), kw = G.keyWord(ws, end === '?'), kv = sv(words[kw]), lastV = sv(words[words.length - 1]);
      let m = 0, n = 0; const sts = []; for (let i = sa; i < sb; i++) if (voiced(i)) { const v = p2st(pitch[i], coef); sts.push(v); m += v; n++; } if (!n) continue; m /= n;
      // Модель сама читает восклицания живее, чем ровный текст. Поэтому рисунок — это цель, а не прибавка: если фраза уже высокая и размашистая, почти не трогаем
      // (иначе выходит переигрывание: размах 16 полутонов, голос ломается).
      sts.sort((x, y) => x - y); const span = sts[Math.round((n - 1) * .95)] - sts[Math.round((n - 1) * .05)];
      let Rr = a.R == null ? 1 : a.R; if (a.span && span > .5) Rr = Rr >= 1 ? clamp(a.span / span, 1, Rr) : clamp(a.span / span, Rr, 1);
      const T0 = t[sa], T1 = Math.max(t[sb], T0 + .2), R = 1 + (Rr - 1) * K, shift = a.reg == null ? 0 : (a.reg - .7 * m) * K;
      const kAdd = a.key && kv >= 0 ? Math.max(0, a.key - .6 * Math.max(0, (voiced(kv) ? p2st(pitch[kv], coef) : m) - m)) * K : 0;   // главное слово и так выделено — не добавляем
      for (let i = sa; i < sb; i++) { if (!voiced(i)) continue; const u = (t[i] - T0) / (T1 - T0);
        let s = m + (p2st(pitch[i], coef) - m) * R + shift + add(a.decl) * (.5 - u) + add(a.onset) * Math.exp(-(t[i] - T0) / .35);
        if (toks[i - 1] === '+') s += add(a.acc);
        if (kAdd && i >= words[kw][0] && i < words[kw][1]) s += kAdd * (i === kv ? 1 : .5);
        if (lastV >= 0 && i >= lastV) s += add(a.fin);
        s = s >= 0 ? 10 * Math.tanh(s / 10) : -8 * Math.tanh(-s / 8);                // мягкий предел: не выше +10 и не ниже −8 полутонов от обычной высоты голоса
        pitch[i] = st2p(s, coef); }
      for (let i = sa; i < sb; i++) if (isV(i)) { d[i] *= toks[i - 1] === '+' ? mul(a.accDur) : mul(a.unstr); if (i === kv) d[i] *= mul(a.keyDur); } }
    if (a.pause != null) { const pm = mul(a.pause); for (let i = 1; i < N - 2; i++) if (',;:–—.!?…'.includes(toks[i])) d[i] = Math.max(2, d[i] * pm); } };

  // ---------- тембр и подача: обработка готового звука (48 кГц) ----------
  const rnd = seed => { let s = (seed >>> 0) || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 2147483648 - 1; }; };
  const biq = (y, type, f, db, Q) => { const A = Math.pow(10, (db || 0) / 40), w = 2 * Math.PI * f / 48000, cs = Math.cos(w), al = Math.sin(w) / (2 * (Q || .707)); let b0, b1, b2, a0, a1, a2;
    if (type === 'hs') { const r = 2 * Math.sqrt(A) * al; b0 = A * ((A + 1) + (A - 1) * cs + r); b1 = -2 * A * ((A - 1) + (A + 1) * cs); b2 = A * ((A + 1) + (A - 1) * cs - r); a0 = (A + 1) - (A - 1) * cs + r; a1 = 2 * ((A - 1) - (A + 1) * cs); a2 = (A + 1) - (A - 1) * cs - r; }
    else if (type === 'hp') { b0 = (1 + cs) / 2; b1 = -(1 + cs); b2 = b0; a0 = 1 + al; a1 = -2 * cs; a2 = 1 - al; }
    else { b0 = (1 - cs) / 2; b1 = 1 - cs; b2 = b0; a0 = 1 + al; a1 = -2 * cs; a2 = 1 - al; }
    const o = new Float32Array(y.length); let x1 = 0, x2 = 0, y1 = 0, y2 = 0; b0 /= a0; b1 /= a0; b2 /= a0; a1 /= a0; a2 /= a0;
    for (let i = 0; i < y.length; i++) { const x = y[i], v = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2; x2 = x1; x1 = x; y2 = y1; y1 = v; o[i] = v; } return o; };
  const envelope = (y, win) => { const o = new Float32Array(y.length); let acc = 0; for (let i = 0; i < y.length; i++) { acc += y[i] * y[i]; if (i >= win) acc -= y[i - win] * y[i - win]; o[i] = Math.sqrt(Math.max(0, acc) / win); } return o; };
  // --- Шёпот ---
  // Первая версия (шум через фильтр линейного предсказания) Михаилу на слух — «ужасно»: гласные оставались громкими, как в речи, и всё шипело. Удалена 10.11.2026.
  const fftMake = N => { const bits = Math.round(Math.log2(N)), rev = new Uint16Array(N), cs = new Float64Array(N / 2), sn = new Float64Array(N / 2);
    for (let i = 0; i < N; i++) { let r = 0; for (let b = 0; b < bits; b++) r |= ((i >> b) & 1) << (bits - 1 - b); rev[i] = r; }
    for (let i = 0; i < N / 2; i++) { cs[i] = Math.cos(2 * Math.PI * i / N); sn[i] = Math.sin(2 * Math.PI * i / N); }
    return (re, im, inv) => { for (let i = 0; i < N; i++) { const j = rev[i]; if (j > i) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
      for (let len = 2; len <= N; len <<= 1) { const half = len >> 1, step = N / len; for (let s = 0; s < N; s += len) for (let k = 0; k < half; k++) { const c = cs[k * step], d = inv ? sn[k * step] : -sn[k * step], a = s + k, b = a + half, xr = re[b] * c - im[b] * d, xi = re[b] * d + im[b] * c; re[b] = re[a] - xr; im[b] = im[a] - xi; re[a] += xr; im[a] += xi; } }
      if (inv) for (let i = 0; i < N; i++) { re[i] /= N; im[i] /= N; } }; };
  /** Где в записи голос (гласные, звонкие), а где глухие согласные и тишина: волна повторяется с периодом 2,5–12,5 мс. → маска 0…1 по отсчётам, края плавные. */
  G.voicedMask = function (y) { const D = 6, n8 = Math.floor(y.length / D), lo = new Float32Array(n8); for (let i = 0; i < n8; i++) { let a = 0; for (let j = 0; j < D; j++) a += y[i * D + j]; lo[i] = a / D; }
    const FR = 240, HP = 80, nV = Math.max(1, Math.floor((n8 - FR) / HP) + 1), vo = new Uint8Array(nV); let emax = 0; const en = new Float32Array(nV);
    for (let f = 0; f < nV; f++) { let e = 0; for (let i = 0; i < FR; i++) { const v = lo[f * HP + i] || 0; e += v * v; } en[f] = e; if (e > emax) emax = e; }
    for (let f = 0; f < nV; f++) { if (en[f] < emax * .002) continue; const s = f * HP; let best = 0;
      for (let L = 20; L <= 100; L += 2) { let c = 0, e1 = 0, e2 = 0; for (let i = 0; i + L < FR; i++) { const a = lo[s + i], b = lo[s + i + L]; c += a * b; e1 += a * a; e2 += b * b; } const r = c / Math.sqrt(e1 * e2 + 1e-12); if (r > best) best = r; }
      vo[f] = best > .5 ? 1 : 0; }
    const m = new Float32Array(y.length), step = HP * D, ramp = 480; for (let f = 0; f < nV; f++) if (vo[f]) { const a = f * step, b = Math.min(y.length, a + FR * D * .5 + step); for (let i = a; i < b; i++) m[i] = 1; }
    const o = new Float32Array(y.length); let acc = 0; for (let i = 0; i < y.length + ramp; i++) { if (i < y.length) acc += m[i]; if (i - 2 * ramp - 1 >= 0) acc -= m[i - 2 * ramp - 1]; const c = i - ramp; if (c >= 0 && c < y.length) o[c] = acc / (2 * ramp + 1); } return o; };
  /** Шёпот-2. Там, где звучал голос: спектр короткими окнами (короче периода голоса — тон в него не попадает, остаётся «форма рта»), сглаженный по времени, со случайной фазой.
      Выходит мягкий шум с формантами — тихий, без верхнего шипения. Глухие согласные (с, ш, т, к…) остаются как были: они и так шёпот.
      o: n — окно, smooth — сглаживание (с), shift — форманты выше, tilt (дБ/окт), lp/hp — полоса (Гц), gv — громкость бывших гласных, gu — согласных, keep — оставлять ли согласные. */
  G.whisper2 = function (y, o) { o = o || {}; const N = o.n || 256, hop = N >> 3, H = N >> 1, W1 = H + 1, fft = fftMake(N), win = new Float64Array(N); for (let i = 0; i < N; i++) win[i] = .5 - .5 * Math.cos(2 * Math.PI * i / N);
    if (y.length < N * 2) return y; const nF = Math.floor((y.length - N) / hop) + 1, mag = new Float32Array(nF * W1), re = new Float64Array(N), im = new Float64Array(N);
    for (let f = 0; f < nF; f++) { const s = f * hop; for (let i = 0; i < N; i++) { re[i] = y[s + i] * win[i]; im[i] = 0; } fft(re, im, false); for (let k = 0; k <= H; k++) mag[f * W1 + k] = re[k] * re[k] + im[k] * im[k]; }
    const sm = Math.max(1, Math.round((o.smooth || .016) * 48000 / hop / 2)), pw = new Float32Array(nF * W1);
    for (let k = 0; k <= H; k++) { let acc = 0; for (let f = 0; f < nF + sm; f++) { if (f < nF) acc += mag[f * W1 + k]; if (f - 2 * sm - 1 >= 0) acc -= mag[(f - 2 * sm - 1) * W1 + k]; const c = f - sm; if (c >= 0 && c < nF) pw[c * W1 + k] = Math.max(0, acc) / (Math.min(nF - 1, c + sm) - Math.max(0, c - sm) + 1); } }
    const sh = o.shift || 1.06, hpF = o.hp || 350, lpF = o.lp || 6000, tl = (o.tilt == null ? 3 : o.tilt) / 6.02, wgt = new Float64Array(W1), w = new Float32Array(y.length), nrm = new Float32Array(y.length), r = rnd(4242);
    for (let k = 0; k <= H; k++) { const fz = k * 48000 / N; wgt[k] = fz * fz / (fz * fz + hpF * hpF) / Math.sqrt(1 + Math.pow(fz / lpF, 4)) * Math.pow(Math.max(fz, 300) / 1000, tl); }
    for (let f = 0; f < nF; f++) { const s = f * hop, b0 = f * W1; for (let k = 0; k <= H; k++) { const x = k / sh, j = Math.floor(x), q = x - j, p = j >= H ? pw[b0 + H] : pw[b0 + j] * (1 - q) + pw[b0 + j + 1] * q, a = Math.sqrt(p) * wgt[k], ph = (r() + 1) * Math.PI; re[k] = a * Math.cos(ph); im[k] = a * Math.sin(ph); }
      im[0] = 0; im[H] = 0; for (let k = 1; k < H; k++) { re[N - k] = re[k]; im[N - k] = -im[k]; } fft(re, im, true); for (let i = 0; i < N; i++) { w[s + i] += re[i] * win[i]; nrm[s + i] += win[i] * win[i]; } }
    for (let i = 0; i < w.length; i++) w[i] /= Math.max(nrm[i], .1);
    const m = o.keep === false ? null : G.voicedMask(y); let ey = 0, ew = 0; for (let i = 0; i < y.length; i++) { const q = m ? m[i] : 1; ey += y[i] * y[i] * q; ew += w[i] * w[i] * q; }
    const g = Math.sqrt(ey / Math.max(ew, 1e-12)) * (o.gv == null ? .45 : o.gv), gu = o.gu == null ? .9 : o.gu, out = new Float32Array(y.length);
    for (let i = 0; i < y.length; i++) { const q = m ? m[i] : 1; out[i] = w[i] * g * q + y[i] * gu * (1 - q); } return out; };
  /** Обработка по рисунку fx (из G.ACT), k — сила. Громкость level здесь не трогаем: её ставит сведение после выравнивания реплик. */
  G.fx = function (y, fx, k) { if (!fx) return y; const K = k == null ? 1 : k; let o = y;
    if (fx.whisper && K > .5) { const w = G.whisper2(o, fx.w2), m = Math.min(1, fx.whisper); if (m >= .99) o = w; else { const z = new Float32Array(o.length); for (let i = 0; i < o.length; i++) z[i] = o[i] * (1 - m) + w[i] * m * 1.6; o = z; } }   // whisper < 1 — полушёпот: голос пополам с шёпотом
    if (fx.vib) { const dep = fx.vib * K, w = new Float32Array(o.length), k1 = dep * .7 / (2 * Math.PI * 6.3) * 48000, k2 = dep * .5 / (2 * Math.PI * 9.1) * 48000;
      for (let i = 0; i < o.length; i++) { const x = i + k1 * Math.sin(2 * Math.PI * 6.3 * i / 48000) + k2 * Math.sin(2 * Math.PI * 9.1 * i / 48000 + 1), j = Math.floor(x), f = x - j; w[i] = j >= 0 && j + 1 < o.length ? o[j] * (1 - f) + o[j + 1] * f : 0; } o = w; }
    if (fx.tilt) o = biq(o, 'hs', 2500, fx.tilt * K);
    if (fx.breath) { const e = envelope(o, 480), r = rnd(777); let nz = new Float32Array(o.length); for (let i = 0; i < nz.length; i++) nz[i] = r(); nz = biq(nz, 'hp', 2500); const b = fx.breath * K * 1.5, w = new Float32Array(o.length); for (let i = 0; i < o.length; i++) w[i] = o[i] + nz[i] * e[i] * b; o = w; }
    if (fx.tremolo) { const dp = fx.tremolo * K, w = new Float32Array(o.length); for (let i = 0; i < o.length; i++) w[i] = o[i] * (1 - dp / 2 + dp / 2 * Math.sin(2 * Math.PI * 6 * i / 48000)); o = w; }
    if (fx.rough) { const dp = fx.rough * K, w = new Float32Array(o.length); for (let i = 0; i < o.length; i++) w[i] = o[i] * (1 - dp / 2 + dp / 2 * Math.sin(2 * Math.PI * 38 * i / 48000)); o = w; }   // хрипотца: частая дрожь громкости
    if (fx.sat) { let pk = 0; for (let i = 0; i < o.length; i++) pk = Math.max(pk, Math.abs(o[i])); if (pk > 0) { const a = 1 + fx.sat * K * 6, th = Math.tanh(a), w = new Float32Array(o.length); for (let i = 0; i < o.length; i++) w[i] = Math.tanh(o[i] / pk * a) / th * pk; o = w; } }
    return o; };

  // ---------- протяжные слова: «Ура-а-а!», «Не-е-ет», «Приве-е-ет» ----------
  /** → {text: обычные слова, cues: [{w — номер слова, v — номер гласной в нём, n — сколько раз её повторили}]} */
  G.stretch = function (text) { const cues = []; let wi = -1;
    const out = String(text).replace(/[А-Яа-яЁё+]+(?:-[А-Яа-яЁё+]+)*/g, w => { wi++; if (!/([аеёиоуыэюя])(?:-\1)+/i.test(w)) return w;
      let clean = '', vc = 0, i = 0; while (i < w.length) { const c = w[i]; if (VOW.includes(c.toLowerCase())) { let j = i + 1, n = 0; while (w[j] === '-' && w[j + 1] && w[j + 1].toLowerCase() === c.toLowerCase()) { n++; j += 2; }
            if (n) cues.push({ w: wi, v: vc, n }); vc++; clean += c; i = j; } else { clean += c; i++; } }
      return clean; });
    return { text: out, cues }; };
  /** В тексте с ударениями повторить протяжную гласную: «Ур+а!» → «Ур+ааааааа!» (каждая буква — отдельный звук модели, поэтому голос тянется, а не шипит). */
  G.applyStretch = function (marked, cues) { if (!cues.length) return marked; let wi = -1;
    return marked.replace(/[А-Яа-яЁё+]+(?:-[А-Яа-яЁё+]+)*/g, w => { wi++; const cs = cues.filter(q => q.w === wi); if (!cs.length) return w; let vc = -1, out = '';
      for (const c of w) { if (VOW.includes(c.toLowerCase())) { vc++; const q = cs.find(x => x.v === vc); out += q ? c.repeat(Math.min(9, 3 + 2 * q.n)) : c; } else out += c; } return out; }); };
  /** Длительность и высота протяжных гласных (три и больше одинаковых гласных подряд): ровно тянем, к концу голос опускается. */
  G.stretchShape = F => c => { let i = 1; while (i < c.N) { const t = c.toks[i]; if (!VOW.includes(t)) { i++; continue; } let j = i; while (j + 1 < c.N && c.toks[j + 1] === t) j++; const n = j - i + 1;
      if (n >= 3) { let p0 = 0; for (let k = i; k >= Math.max(0, i - 3) && !p0; k--) if (Math.abs(c.pitch[k]) > .001) p0 = p2st(c.pitch[k], c.coef); for (let k = i; k <= j; k++) { const f = (k - i) / (n - 1); c.d[k] = Math.round(5 * (F || 1)); c.pitch[k] = st2p(p0 + 3 * Math.sin(Math.PI / 2 * Math.min(1, f / .45)) - 5 * Math.max(0, f - .7) / .3, c.coef); } }   // голос поднимается, держится и к концу падает — как живое «Ура-а-а!»
      i = j + 1; } };

  // ---------- «партитура»: звук за звуком ----------
  /** notes: [[буква, длительность (с), высота (полутоны от обычного голоса; null — глухой звук или как у модели), высота в конце]].
      Долгий звук режется на кусочки по ~55 мс — высота идёт плавно. Пробел, дефис и знаки — паузы. */
  G.score = function (notes) { let text = ''; const plan = [];
    for (const n of notes) { const ch = n[0], dur = n[1], a = n[2], b = n[3]; if (' -!,.?'.includes(ch)) { text += ch; plan.push({ d: dur, st: null, raw: true }); continue; }
      const k = (VOW.includes(ch) || 'рлмнзжшсвй'.includes(ch)) ? Math.max(1, Math.round(dur / .055)) : 1;
      for (let i = 0; i < k; i++) { text += ch; const f = k > 1 ? i / (k - 1) : 0; plan.push({ d: dur / k, st: a == null ? null : (b == null ? a : a + (b - a) * f) }); } }
    return { text, plan }; };
  G.scoreShape = (plan, lift, sp) => c => { let k = 0; for (let i = 1; i < c.N - 1 && k < plan.length; i++) { if (c.toks[i] === '+') { c.d[i] = 0; continue; } const p = plan[k++];
      c.d[i] = Math.max(p.raw ? 0 : 1, Math.round(p.d / sp / c.frame)); c.pitch[i] = p.st == null ? (p.raw ? 0 : c.pitch[i]) : st2p(p.st + lift, c.coef); } };

  // ---------- смех ----------
  // Ритм, мелодия и громкость настоящих смехов из банка (по слогам): [шаг до следующего слога, с; высота, полутоны от середины смеха; громкость, дБ]
  G.LAUGHS = {"F16":{"g":"F","s":"laugh","t":[[0.11,3.5,0],[0.14,2.1,-1],[0.14,1.3,-6],[0.25,0.6,-9],[0.11,0.4,-12],[0.12,0.3,-13],[0.14,-0.1,-14],[0.13,-0.2,-14],[0.17,-0.8,-14],[0.14,-1.0,-14],[0.12,-0.9,-14],[0.14,-1.5,-14],[0.15,-1.4,-14],[0.17,-2.1,-14],[0.11,-1.8,-14]]},"F9":{"g":"F","s":"laugh","t":[[0.16,4.2,0],[0.16,4.7,-1],[0.16,2.1,-2],[0.16,1.7,-5],[0.16,0.5,-3],[0.17,0.6,-3],[0.2,-0.2,-5],[0.16,-0.2,-5],[0.18,-0.3,-4],[0.18,-0.3,-4],[0.21,-0.8,-5],[0.17,-1.3,-4],[0.19,-0.4,-4],[0.21,-0.9,-5],[0.2,-1.4,-6],[0.19,-1.9,-6],[0.2,-0.3,-6]]},"B5":{"g":"B","s":"laugh","t":[[0.19,0.3,0],[0.16,1.6,0],[0.14,1.2,0],[0.18,0.9,-1],[0.13,0.1,-2],[0.15,-0.4,-3],[0.11,-0.7,-4]]},"K8":{"g":"K","s":"laugh","t":[[0.29,-0.4,0],[0.22,0.5,-6],[0.22,0.2,-9],[0.21,0.0,-10],[0.16,-1.1,-10]]},"F11":{"g":"F","s":"chuckle","t":[[0.2,4.0,0],[0.21,2.4,-3],[0.11,-0.0,-5],[0.15,0.1,-5],[0.11,0.7,-5],[0.22,0.2,-5],[0.23,-0.3,-6],[0.21,-1.1,-11],[0.13,-1.2,-11]]},"F2":{"g":"F","s":"giggle","t":[[0.2,1.3,0],[0.15,0.1,-2],[0.2,0.6,-4],[0.2,-1.3,-8],[0.2,-1.3,-14],[0.21,-0.7,-14],[0.11,-0.5,-14]]},"K7":{"g":"K","s":"belly","t":[[0.28,1.2,0],[0.24,1.4,0],[0.24,0.2,-2],[0.32,-2.2,-7],[0.18,-3.2,-7],[0.21,-3.2,-2],[0.21,-0.7,-2],[0.11,-0.7,-6]]},"F22":{"g":"F","s":"laugh","t":[[0.36,-2.2,0],[0.23,5.4,0],[0.16,4.5,-2],[0.19,4.0,-2],[0.18,1.4,-2],[0.19,0.8,-2],[0.18,0.5,-2],[0.21,-0.3,-4],[0.18,-0.2,-3],[0.23,-0.3,-3],[0.11,-0.6,-4]]},"F4":{"g":"F","s":"laugh","t":[[0.35,0.2,0],[0.32,-0.2,-1],[0.23,0.4,-3],[0.11,0.9,-8],[0.14,-0.7,-10],[0.11,-0.3,-14]]},"F21":{"g":"F","s":"laugh","t":[[0.17,5.0,0],[0.2,3.1,0],[0.19,2.4,-2],[0.22,0.0,-2],[0.22,0.2,-3],[0.22,-1.3,-6],[0.2,-1.7,-11],[0.21,-1.8,-13],[0.2,-1.3,-11],[0.18,-1.1,-11]]}};
  // Проверено распознавателем звуков (AST AudioSet): в голосе героя как смех слышатся быстрые образцы (шаг слога до 0,2 с) на «ха»;
  // медленные «ха… ха… ха» и «хе-хе» слышатся как речь, поэтому их тут нет. Первый в списке — основной, остальные — чтобы смех не повторялся нота в ноту.
  // У чужих голосов (не Барсик) надёжно слышится смехом только F16; у низких и старых голосов (ниже ~130 Гц) смех этим способом пока не получается — им оставлять смех из банка.
  G.LAUGH_SETS = { laugh: ['F16', 'F9', 'B5'], giggle: ['F16', 'F16', 'F9'], belly: ['F16', 'F9', 'B5'] };
  G.HERO_LAUGH = { 'барсик': ['F16', 'F9', 'B5'] };
  /** Какой смех у героя: свой список (по имени) или по складу голоса; variant — какой по счёту смех в серии. */
  G.laughFor = function (name, style, variant) { const nm = String(name || '').trim().toLowerCase().replace(/^(кот|пёс|пес|мышонок|щенок)\s+/, ''); const set = G.HERO_LAUGH[nm] || G.LAUGH_SETS[style] || G.LAUGH_SETS.laugh; return set[(variant || 0) % set.length]; };
  G.laughShape = function (tpl, o) { const lift = o.lift, hk = o.hk == null ? .42 : o.hk, vk = o.vk == null ? .5 : o.vk, sp = o.speed || 1, jit = o.seed == null ? null : o.seed;
    return c => { let k = -1, last = 0; const fr = c.frame;
      for (let i = 0; i < c.N; i++) { const t = c.toks[i];
        if (t === 'х') { k++; const s = tpl[Math.min(k, tpl.length - 1)], j = jit == null ? 1 : 1 + ((hash32(jit + ':' + k) % 17) - 8) / 100; c.d[i] = Math.max(2, Math.round(s[0] * j * hk / sp / fr)); c.pitch[i] = 0; continue; }
        if (k < 0) continue; const s = tpl[Math.min(k, tpl.length - 1)], stv = s[1] + lift;
        if (t === '+') { c.d[i] = 1; c.pitch[i] = st2p(stv + .6, c.coef); }
        else if (VOW.includes(t)) { c.d[i] = Math.max(3, Math.round(s[0] * vk / sp / fr) - 1); c.pitch[i] = st2p(stv, c.coef); }
        else if (t === ' ' || t === '-') { c.d[i] = Math.max(0, Math.round(s[0] * (1 - hk - vk) / sp / fr)); c.pitch[i] = 0; } } }; };
  /** Громкость по слогам (как затухает настоящий смех). */
  G.laughEnv = function (y, al, tpl) { const fr = al.frame * 48000; let pos = 0, k = -1, cur = 1; const g = new Float32Array(y.length).fill(1);
    for (let i = 0; i < al.toks.length; i++) { const a = Math.round(pos), b = Math.round(pos + al.d[i] * fr); if (al.toks[i] === 'х') { k++; cur = Math.pow(10, clamp(tpl[Math.min(k, tpl.length - 1)][2], -14, 0) / 20); }
      if (k >= 0) for (let j = a; j < Math.min(b, y.length); j++) g[j] = cur; pos += al.d[i] * fr; }
    let acc = 1; const out = new Float32Array(y.length); for (let i = 0; i < y.length; i++) { acc += (g[i] - acc) / 480; out[i] = y[i] * acc; } return out; };

  // ---------- звуки зверей и возгласы голосом героя ----------
  // Ключ → ноты «партитуры». Высота — в полутонах от обычного голоса героя, так что кот мяукает своим голосом, а медведь — своим.
  const rep = (n, f) => { const a = []; for (let i = 0; i < n; i++) a.push(...f(i)); return a; };
  G.SOUNDS = {
    meow: () => [['м', .07, 1], ['я', .28, 3, 10], ['у', .42, 9, -2], ['!', .1]],
    meow2: () => [['м', .06, 2], ['я', .18, 4, 9], ['у', .25, 8, 1], [' ', .12], ['м', .06, 1], ['я', .2, 3, 10], ['у', .4, 9, -3], ['!', .1]],
    purr: () => [['м', .08, -4], ['у', .12, -4, -5], ['р', 1.0, -6, -7], ['.', .1]],
    bark: () => [['г', .04, null], ['а', .12, -2, -4], ['в', .05, -5], ['!', .12]],
    bark2: () => [['г', .04, null], ['а', .12, -2, -4], ['в', .05, -5], ['!', .12], [' ', .1], ['г', .04, null], ['а', .12, -1, -4], ['в', .05, -5], ['!', .1]],
    growl: () => [['р', 1.1, -6, -8], ['!', .1]],
    howl: () => [['а', .12, -3, -1], ['у', 1.3, -1, 8], ['у', .7, 8, 5], ['!', .1]],
    squeak: () => rep(3, i => [['п', .03, null], ['и', i === 2 ? .12 : .09, 12 + i, i === 2 ? 10 : 13 + i], i === 2 ? ['!', .1] : [' ', .06]]),
    cuckoo: () => [['к', .04, null], ['у', .22, 7, 7], ['-', .05], ['к', .04, null], ['у', .3, 3, 3], ['!', .1]],
    moo: () => [['м', .2, -5, -4], ['у', 1.0, -4, -7], ['!', .1]],
    baa: () => rep(8, i => i === 0 ? [['б', .04, null], ['е', .1, 2 + (i % 2 ? -.8 : .8)]] : [['е', .1, 2 - i * .3 + (i % 2 ? -.8 : .8)]]).concat([['!', .1]]),
    maa: () => rep(8, i => i === 0 ? [['м', .06, 3], ['е', .1, 4 + (i % 2 ? -.8 : .8)]] : [['е', .1, 4 - i * .3 + (i % 2 ? -.8 : .8)]]).concat([['!', .1]]),
    frog: () => rep(2, i => [['к', .03, null], ['в', .04, -3], ['а', .14, -2, -5], i ? ['!', .1] : [' ', .1]]),
    duck: () => rep(2, i => [['к', .03, null], ['р', .04, 1], ['я', .13, 3, 0], i ? ['!', .1] : [' ', .09]]),
    oink: () => rep(2, i => [['х', .05, null], ['р', .07, -5], ['ю', .14, -4, -6], i ? ['!', .1] : [' ', .1]]),
    crow: () => [['к', .04, null], ['а', .2, 1, -1], ['р', .45, -1, -3], ['!', .1]],
    rooster: () => [['к', .03, null], ['у', .12, 3], ['-', .02], ['к', .03, null], ['а', .12, 6], ['-', .02], ['р', .04, 8], ['е', .2, 9, 10], ['-', .02], ['к', .03, null], ['у', .9, 10, 3], ['!', .1]],
    neigh: () => [['и', .5, 10, 4], ['-', .03], ['г', .03, null], ['о', .14, 2], ['-', .03], ['г', .03, null], ['о', .3, 1, -2], ['!', .1]],
    buzz: () => [['ж', 1.1, 0, 1], ['!', .1]],
    hiss: () => [['ш', .9, null], ['!', .1]],
    shh: () => [['т', .04, null], ['с', .8, null], ['!', .1]],
    hmm: () => [['м', .9, 2, 5], ['!', .1]],
    aaa: () => [['а', 1.2, 6, 9], ['!', .1]],
    ooo: () => [['о', 1.0, 6, 2], ['!', .1]],
    uuu: () => [['у', 1.2, 2, 5], ['!', .1]],
    brr: () => [['б', .04, null], ['р', .8, -2, -3], ['!', .1]],
    yawn: () => [['а', .9, 2, 7], ['а', .7, 7, -4], ['х', .3, null], ['.', .1]],
    cry: () => rep(4, i => [['у', .1, 5 - i], ['а', .34, 7 - i, 3 - i], i === 3 ? ['!', .1] : [' ', .12]]),
    sing: () => rep(10, i => { const mel = [0, 2, 4, 5, 7, 7, 5, 4, 2, 0], n = mel[i]; return [['л', .05, n], ['я', i % 5 === 4 ? .5 : .28, n, n], i === 9 ? ['!', .1] : [' ', .03]]; }),
    ahchoo: () => [['а', .5, 2, 8], ['п', .05, null], ['ч', .08, null], ['х', .06, null], ['и', .25, 10, 2], ['!', .1]],
  };
  // слова в реплике → звук: «Мяу!», «Гав-гав», «Пи-пи-пи», «Ку-ку», «Му-у-у»…
  G.SOUND_WORDS = [[/^мя+у+(?:[-\s]+мя+у+)+$/, 'meow2'], [/^мя+у+$/, 'meow'], [/^му+р+(?:[-\s]*р+)*(?:[-\s]+му+р+)*$/, 'purr'], [/^гав(?:[-\s]+гав)+$/, 'bark2'], [/^гав$/, 'bark'], [/^р(?:-?р)+$/, 'growl'],
    [/^а?у(?:-?у){2,}$/, 'howl'], [/^пи(?:[-\s]+пи)+$/, 'squeak'], [/^ку[-\s]+ку$/, 'cuckoo'], [/^му(?:-?у)+$/, 'moo'], [/^бе(?:-?е)+$/, 'baa'], [/^ме(?:-?е)+$/, 'maa'], [/^ква(?:[-\s]+ква)+$/, 'frog'],
    [/^кря(?:[-\s]+кря)+$/, 'duck'], [/^хрю(?:[-\s]+хрю)+$/, 'oink'], [/^кар(?:-?р)*$/, 'crow'], [/^ку[-\s]*ка[-\s]*ре[-\s]*ку$/, 'rooster'], [/^и[-\s]*го[-\s]*го$/, 'neigh'], [/^ж(?:-?ж){2,}$/, 'buzz'], [/^ш(?:-?ш){2,}$/, 'hiss'],
    [/^т+с(?:-?с)+$/, 'shh'], [/^х?м(?:-?м){2,}$/, 'hmm'], [/^а(?:-?а){2,}$/, 'aaa'], [/^о(?:-?о){2,}$/, 'ooo'], [/^бр(?:-?р)+$/, 'brr'], [/^ля(?:[-\s]+ля){2,}$/, 'sing'], [/^а+п+чхи$/, 'ahchoo']];
  G.soundOf = w => { const s = String(w || '').toLowerCase().replace(/ё/g, 'е').replace(/[!?.,…]+$/, '').trim(); for (const [re, k] of G.SOUND_WORDS) if (re.test(s)) return k; return null; };
  /** Разбить реплику на куски: обычная речь и звуки («Мяу! Я поймал бабочку!» → звук + речь). */
  G.split = function (text) { const parts = []; let buf = '';
    for (const seg of String(text).split(/(?<=[.!?…])\s+/)) { const k = G.soundOf(seg); if (k) { if (buf.trim()) parts.push({ say: buf.trim() }); buf = ''; parts.push({ sound: k }); } else buf += (buf ? ' ' : '') + seg; }
    if (buf.trim()) parts.push({ say: buf.trim() }); return parts; };

  /** Есть ли в реплике то, что обычный голос читает плохо: протяжные слова («Ура-а-а!») или звуки («Мяу!», «Гав-гав»). */
  G.needs = text => { const t = String(text || ''); return /([аеёиоуыэюя])(?:-\1)+/i.test(t) || G.split(t).some(p => p.sound); };
  // ---------- сборка звука ----------
  const core = (text, o, extra) => MKVoice.speak(text, Object.assign({ model: o.model || '', speaker: o.speaker, lex: o.lex }, extra));
  async function say(text, o, b) { const act = b.actx || (b.emo && b.act !== false && G.ACT[b.emo]) || null, K = b.k == null ? 1 : b.k, mk = x => 1 + ((x == null ? 1 : x) - 1) * K;   // act — игра эмоции (БАРС-актёр); без неё — прежние G.EMO
    const fx = (act && act.fx) || null, e = act ? {} : ((b.emo && G.EMO[b.emo]) || {}), F = (b.F || 1) * (fx ? mk(fx.F) : 1), P = (b.P || 1) * (e.P || 1), T = (b.T || 1) * (act ? mk(act.T) : (e.T || 1)), R = (b.R || 1) * (e.R || 1);
    const s = G.stretch(text); let marked = o.accent === false ? s.text : await MKVoice.marks(s.text, o.lex); marked = G.applyStretch(marked, s.cues); MKVoice.lastText = marked;
    const shapes = []; if (R !== 1 || e.trem) shapes.push(G.liveShape(R, e.trem)); if (act) shapes.push(G.actShape(act, K)); if (s.cues.length) shapes.push(G.stretchShape(F)); if (b.pause) shapes.push(G.pauseShape(b.pause, F));
    const y = await core(marked, o, { rate: T / F * (o.rate || 1), pitch: P / F * (o.pitch || 1), accent: false, typeFix: !!b.typeFix, shape: shapes.length ? c => shapes.forEach(f => f(c)) : null });
    return fx ? G.fx(G.resample(y, F), fx, K) : G.resample(y, F); }
  async function sound(name, o, b) { const F = b.F || 1, mk = G.SOUNDS[name]; if (!mk) return new Float32Array(0); const sc = G.score(mk());
    const y = await core(sc.text, o, { rate: 1, pitch: 1, accent: false, shape: G.scoreShape(sc.plan, (b.lift || 0) + 12 * Math.log2((b.P || 1) / F), (b.speed || 1) / F) });
    return G.resample(y, F); }
  async function laugh(o, b) { const F = b.F || 1, L = G.LAUGHS[b.tpl] || G.LAUGHS.F16; let T = L.t; const n = b.short ? Math.min(T.length, 4) : Math.min(T.length, b.n || 12); T = T.slice(0, n);
    const text = T.map(() => 'х+' + (b.vow || 'а')).join(b.sep == null ? ' ' : b.sep) + '!';
    const y = await core(text, o, { rate: 1, pitch: 1, accent: false, shape: G.laughShape(T, { lift: (b.lift == null ? 4 : b.lift) + 12 * Math.log2((b.P || 1) / F), speed: (b.speed || 1) / F, seed: b.seed }) });
    return G.resample(G.laughEnv(y, MKVoice.lastAlign, T), F); }
  const join = (bufs, gap) => { const g = Math.round(48000 * gap), n = bufs.reduce((a, x) => a + x.length, 0) + g * Math.max(0, bufs.length - 1), y = new Float32Array(n); let k = 0; for (const x of bufs) { y.set(x, k); k += x.length + g; } return y; };
  /** Главный вход: текст + описание bars → звук 48 кГц.
      bars: { P — тон, F — тембр, T — темп, R — живость, emo — эмоция, pause — паузы на знаках не длиннее стольких секунд; kind: 'say' (по умолчанию) | 'laugh' | 'sound'; … } */
  G.render = async function (text, o) { const b = o.bars || {};
    if (b.kind === 'laugh') return laugh(o, b);
    if (b.kind === 'sound') return sound(b.name, o, b);
    const parts = b.sounds === false ? [{ say: text }] : G.split(text); if (parts.length === 1 && parts[0].say) return say(text, o, b);
    const bufs = []; for (const p of parts) bufs.push(p.sound ? await sound(p.sound, o, b) : await say(p.say, o, b)); return join(bufs, .12); };
  global.BARSGolos = G;
})(typeof window !== 'undefined' ? window : globalThis);
