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

  // ---------- эмоции: тон, темп, размах интонации, дрожь ----------
  G.EMO = { happy: { P: 1.03, T: 1.03, R: 1.2 }, laugh: { P: 1.04, T: 1.05, R: 1.25 }, sad: { P: .96, T: .9, R: .75 }, cry: { P: 1, T: .88, R: .9, trem: .7 },
    angry: { P: .97, T: 1.05, R: 1.15 }, surprised: { P: 1.06, T: 1, R: 1.4 }, scared: { P: 1.06, T: 1.08, R: 1.15, trem: .5 }, sleepy: { P: .95, T: .82, R: .7 },
    love: { P: 1, T: .93, R: 1 }, shy: { P: 1.02, T: .9, R: .8 }, shout: { P: 1.07, T: 1, R: 1.3 } };

  /** Живость: размах интонации вокруг средней высоты ×R (R > 1 — выразительнее), дрожь голоса trem (полутоны). */
  G.liveShape = (R, trem) => c => { let k = 0; for (let i = 0; i < c.N; i++) if (Math.abs(c.pitch[i]) > .001) { let s = p2st(c.pitch[i], c.coef) * R; if (trem && VOW.includes(c.toks[i])) s += (k++ % 2 ? -trem : trem); c.pitch[i] = st2p(s, c.coef); } };

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
  G.LAUGH_SETS = { laugh: ['F16', 'F9', 'B5'], giggle: ['F16', 'K8', 'F2'], belly: ['B5', 'F9', 'F16'] };
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
  async function say(text, o, b) { const F = b.F || 1, e = (b.emo && G.EMO[b.emo]) || {}, P = (b.P || 1) * (e.P || 1), T = (b.T || 1) * (e.T || 1), R = (b.R || 1) * (e.R || 1);
    const s = G.stretch(text); let marked = o.accent === false ? s.text : await MKVoice.marks(s.text, o.lex); marked = G.applyStretch(marked, s.cues); MKVoice.lastText = marked;
    const shapes = []; if (R !== 1 || e.trem) shapes.push(G.liveShape(R, e.trem)); if (s.cues.length) shapes.push(G.stretchShape(F));
    const y = await core(marked, o, { rate: T / F * (o.rate || 1), pitch: P / F * (o.pitch || 1), accent: false, shape: shapes.length ? c => shapes.forEach(f => f(c)) : null });
    return G.resample(y, F); }
  async function sound(name, o, b) { const F = b.F || 1, mk = G.SOUNDS[name]; if (!mk) return new Float32Array(0); const sc = G.score(mk());
    const y = await core(sc.text, o, { rate: 1, pitch: 1, accent: false, shape: G.scoreShape(sc.plan, (b.lift || 0) + 12 * Math.log2((b.P || 1) / F), (b.speed || 1) / F) });
    return G.resample(y, F); }
  async function laugh(o, b) { const F = b.F || 1, L = G.LAUGHS[b.tpl] || G.LAUGHS.F16; let T = L.t; const n = b.short ? Math.min(T.length, 4) : Math.min(T.length, b.n || 12); T = T.slice(0, n);
    const text = T.map(() => 'х+' + (b.vow || 'а')).join(b.sep == null ? ' ' : b.sep) + '!';
    const y = await core(text, o, { rate: 1, pitch: 1, accent: false, shape: G.laughShape(T, { lift: (b.lift == null ? 4 : b.lift) + 12 * Math.log2((b.P || 1) / F), speed: (b.speed || 1) / F, seed: b.seed }) });
    return G.resample(G.laughEnv(y, MKVoice.lastAlign, T), F); }
  const join = (bufs, gap) => { const g = Math.round(48000 * gap), n = bufs.reduce((a, x) => a + x.length, 0) + g * Math.max(0, bufs.length - 1), y = new Float32Array(n); let k = 0; for (const x of bufs) { y.set(x, k); k += x.length + g; } return y; };
  /** Главный вход: текст + описание bars → звук 48 кГц.
      bars: { P — тон, F — тембр, T — темп, R — живость, emo — эмоция; kind: 'say' (по умолчанию) | 'laugh' | 'sound'; … } */
  G.render = async function (text, o) { const b = o.bars || {};
    if (b.kind === 'laugh') return laugh(o, b);
    if (b.kind === 'sound') return sound(b.name, o, b);
    const parts = b.sounds === false ? [{ say: text }] : G.split(text); if (parts.length === 1 && parts[0].say) return say(text, o, b);
    const bufs = []; for (const p of parts) bufs.push(p.sound ? await sound(p.sound, o, b) : await say(p.say, o, b)); return join(bufs, .12); };
  global.BARSGolos = G;
})(typeof window !== 'undefined' ? window : globalThis);
