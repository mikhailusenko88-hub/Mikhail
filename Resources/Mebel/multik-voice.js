// «Альбина» прямо в телефоне: нейроголос Silero v5 CIS (MIT), разобранный на 4 части ONNX, + ударения silero-stress (MIT).
// Ничего не уходит в интернет: модели лежат в приложении (папка voice/), считаются в WebAssembly (onnxruntime-web).
// MKVoice.speak(text, {speaker, rate, pitch, soft}) → Float32Array 48 кГц.  MKStress.accent(text, lex) → текст с «+».
(function (global) {
  'use strict';
  const BASE = 'voice/', ORT = 'ort/';

  // ---------- ударения: n-граммная модель silero-stress (то же, что AccentorNgram) ----------
  const VOW = 'аоуыэиеяёю';
  const f16 = (() => { const t = new Float32Array(65536); for (let h = 0; h < 65536; h++) { const s = h & 0x8000 ? -1 : 1, e = (h >> 10) & 31, m = h & 1023;
    t[h] = e === 0 ? s * Math.pow(2, -14) * (m / 1024) : e === 31 ? (m ? NaN : s * Infinity) : s * Math.pow(2, e - 15) * (1 + m / 1024); } return t; })();
  const isLower = c => c === c.toLowerCase() && c !== c.toUpperCase();
  const MKStress = {
    ready: false, _p: null,
    load() { if (this._p) return this._p;
      return (this._p = (async () => {
        const d = await (await fetch(BASE + 'stress.json')).json(), raw = new Uint16Array(await (await fetch(BASE + 'stress_emb.f16')).arrayBuffer());
        const emb = new Float32Array(raw.length); for (let i = 0; i < raw.length; i++) emb[i] = f16[raw[i]];
        const G = new Map(); d.ngrams.split('\n').forEach((g, i) => G.set(g, i));
        const mlp = L => L.map(l => ({ w: Float32Array.from(l.w.flat()), b: Float32Array.from(l.b), o: l.w.length, i: l.w[0].length }));
        Object.assign(this, { d, emb, G, dim: d.emb_dim, ST: mlp(d.stress), YO: mlp(d.yo), EXC: d.exceptions, HOMO: d.homodict || {} }); this.ready = true; })()); },
    ngrams(w) { const t = '<' + w + '>', out = []; for (let n = 1; n <= w.length + 3; n++) for (let i = 0; i + n <= t.length; i++) out.push(t.slice(i, i + n)); return out; },
    run(L, x) { for (let k = 0; k < L.length; k++) { const l = L[k], y = new Float32Array(l.o);
        for (let o = 0; o < l.o; o++) { let s = l.b[o]; const r = o * l.i; for (let i = 0; i < l.i; i++) s += l.w[r + i] * x[i]; y[o] = k < L.length - 1 ? Math.max(0, s) : s; } x = y; } return x; },
    predict(w) { const D = this.dim, v = new Float32Array(D); let n = 0;
      const add = id => { const r = id * D; for (let j = 0; j < D; j++) v[j] += this.emb[r + j]; n++; };
      for (const g of this.ngrams(w)) { const id = this.G.get(g); if (id != null) add(id); } if (!n) add(this.G.get('UNK'));
      for (let j = 0; j < D; j++) v[j] /= n;
      const sm = a => { let mx = -1e9, k = 0; for (let i = 0; i < a.length; i++) if (a[i] > mx) { mx = a[i]; k = i; } let s = 0; for (let i = 0; i < a.length; i++) s += Math.exp(a[i] - mx); return [k, 1 / s]; };
      const [st, sp] = sm(this.run(this.ST, v)), [yo, yp] = sm(this.run(this.YO, v)); return { st, sp, yo, yp }; },
    tokenize(sentence) { const tokens = [], inputs = [], mask = [];
      for (const word of sentence.split(/([\s.,!?;:<>=()/\\]+)/)) { const parts = word.split('-');
        const cur = parts.length === 1 ? parts : parts.slice(0, -1).map(p => p + '-').concat([parts[parts.length - 1]]);
        const cm = parts.length === 1 ? [true] : parts.slice(0, -1).map(() => true).concat([parts[parts.length - 1] !== 'то']);
        cur.forEach((t, i) => { const x = t.toLowerCase().replace(/[^А-Яа-яёЁ]/g, ''); tokens.push(t); inputs.push(x); mask.push(x.length > 0 && cm[i]); }); }
      return { tokens, inputs, mask }; },
    /** Текст → текст с «+» перед ударной гласной в каждом слове (свои «+» и «ё» не трогает). lex.stress — словарь пользователя. */
    userMarks(sentence, lex) { const user = (lex && lex.stress) || {}, isH = global.MK && global.MK.isHomograph;
      return sentence.replace(/[А-Яа-яЁё+]+/g, w => { if (w.includes('+')) return w; const u = user[w.toLowerCase().replace(/ё/g, 'е')] || user[w.toLowerCase()]; if (!u || (isH && isH(w))) return w;
        let out = '', j = 0; for (const c of u) { if (c === '+') { out += '+'; continue; } const o = w[j++] || c; out += isLower(o) ? c : c.toUpperCase(); } return out; }); },
    accent(sentence, lex) { if (!this.ready) return sentence;
      if (lex) sentence = this.userMarks(sentence, lex);
      const { tokens, inputs, mask } = this.tokenize(sentence), res = [];
      for (let k = 0; k < tokens.length; k++) { let raw = tokens[k]; const clean = inputs[k], low = raw.toLowerCase();
        if (!mask[k]) { res.push(raw); continue; }
        const haveSt = low.includes('+'), haveYo = low.includes('ё');
        if (haveSt && haveYo) { res.push(raw); continue; }
        if (!haveSt && haveYo) { const pos = [...low].map((c, i) => c === 'ё' ? i : -1).filter(i => i >= 0); pos.forEach((p, i) => { raw = raw.slice(0, p + i) + '+' + raw.slice(p + i); }); res.push(raw); continue; }
        if (this.EXC[clean]) { const [es, ey] = this.EXC[clean];
          if (haveSt) { const tp = [...raw].map((c, i) => c === '+' ? i : -1).filter(i => i >= 0); let w = raw.replace(/\+/g, '');
            if (ey !== -1 && tp.includes(ey + 1)) w = w.slice(0, ey) + (isLower(w[ey]) ? 'ё' : 'Ё') + w.slice(ey + 1); for (const p of tp) w = w.slice(0, p) + '+' + w.slice(p); res.push(w); }
          else { if (ey !== -1) raw = raw.slice(0, ey) + (isLower(raw[ey]) ? 'ё' : 'Ё') + raw.slice(ey + 1); res.push(raw.slice(0, es) + '+' + raw.slice(es)); }
          continue; }
        const p = this.predict(clean); let stIds = [p.st];
        const setSt0 = p.sp > .5 && !haveSt, setYo = p.yp > .5;
        if (haveSt) stIds = low.split('+').map(part => [...part].filter(c => VOW.includes(c)).length);
        const vIds = [...low].map((c, i) => VOW.includes(c) ? i : -1).filter(i => i >= 0), eIds = [...low].map((c, i) => c === 'е' ? i : -1).filter(i => i >= 0);
        let stPos = stIds.filter(i => i < vIds.length && vIds.length > 0).map(i => vIds[i]);
        const yoPos = [p.yo].filter(i => i > 0 && i - 1 < eIds.length && eIds.length > 0).map(i => eIds[i - 1]);
        if (!vIds.length) { res.push(raw); continue; }
        for (const yp of yoPos) if (stPos.includes(yp) && setYo && low[yp] === 'е') raw = raw.slice(0, yp) + (isLower(raw[yp]) ? 'ё' : 'Ё') + raw.slice(yp + 1);
        let setSt = setSt0; if (vIds.length === 1) { stPos = [vIds[0]]; setSt = true; }
        if (!haveSt && setSt) stPos.forEach((sp, i) => { raw = raw.slice(0, sp + i) + '+' + raw.slice(sp + i); });
        res.push(raw); }
      return res.join(''); },
    /** Слова-омографы в тексте (з+амок/зам+ок): что поставил голос и какие есть варианты — для настройки ударений. */
    homographs(text) { const out = []; for (const w of (text.toLowerCase().match(/[а-яё]+/g) || [])) if (this.HOMO[w] && !out.some(o => o.w === w)) out.push({ w, v: this.HOMO[w] }); return out; },
  };

  // ---------- омографы (з+амок / зам+ок): фразы + маленький BERT из silero-stress, как HomoSolver ----------
  const MKHomo = {
    ready: false, _p: null, _pd: null, dictReady: false,
    /** Только словарь и фразы (homo.json, без нейросети): хватает для многих фраз и для списка омографов в сценарии. */
    loadDict() { if (this._pd) return this._pd;
      return (this._pd = (async () => {
        const d = await (await fetch(BASE + 'homo.json')).json(); this.d = d; this.H = d.H;
        this.vocab = new Map(); d.vocab.split('\n').forEach((t, i) => this.vocab.set(t, i)); this.never = new Set(d.never_split);
        this.re = {}; for (const [w, pat] of Object.entries(d.phrases)) { try { this.re[w] = new RegExp(pat.replace(/\(\?P</g, '(?<'), 'i'); } catch (e) {} }
        this.head = d.head.map(l => l.t === 'lin' ? { t: 'lin', w: Float32Array.from(l.w.flat()), b: Float32Array.from(l.b), o: l.w.length, i: l.w[0].length } : l);
        this.dictReady = true; })().catch(e => { this._pd = null; throw e; })); },
    /** Словарь + нейросеть (rubert-tiny) для фраз, которых нет среди типовых. */
    load(ort) { if (this._p) return this._p;
      return (this._p = (async () => {
        await this.loadDict(); const q = await (await fetch(BASE + 'homo_emb.q8')).arrayBuffer(); this.q = this.d.dtype === 'int8' ? new Int8Array(q) : new Uint8Array(q);
        this.sess = await ort.InferenceSession.create(BASE + 'homo.onnx', { executionProviders: ['wasm'], graphOptimizationLevel: 'all' });
        this.ready = true; })().catch(e => { this._p = null; throw e; })); },
    async unload() { if (this.sess) { try { await this.sess.release(); } catch (e) {} } this.sess = null; this.q = null; this.ready = false; this._p = null; this.d = null; this.re = null; this.vocab = null; this.dictReady = false; this._pd = null; },
    /** Есть ли в тексте омографы (по словарю, если загружен, иначе по встроенному списку MK.isHomograph). */
    has(text) { const isH = global.MK && global.MK.isHomograph; for (const w of (String(text || '').toLowerCase().match(/[а-яё]+/g) || [])) { if (this.d && this.d.homodict[w]) return true; if (!this.d && isH && isH(w)) return true; } return false; },
    // BERT-токенизатор (BasicTokenizer + WordPiece, без перевода в нижний регистр)
    basic(text) { let t = ''; for (const c of text) { const cp = c.codePointAt(0); if (cp === 0 || cp === 0xfffd || (/\p{C}/u.test(c) && !'\t\n\r'.includes(c))) continue; t += (/[ \t\n\r]/.test(c) || /\p{Zs}/u.test(c)) ? ' ' : c; }
      const out = []; for (const tok of t.trim().split(/\s+/).filter(Boolean)) { if (this.never.has(tok)) { out.push(tok); continue; }
        let cur = null; for (const c of tok) { const cp = c.codePointAt(0), pun = (cp >= 33 && cp <= 47) || (cp >= 58 && cp <= 64) || (cp >= 91 && cp <= 96) || (cp >= 123 && cp <= 126) || /\p{P}/u.test(c);
          if (pun) { out.push(c); cur = null; } else { if (cur === null) { out.push(''); cur = out.length - 1; } out[cur] += c; } } }
      return out; },
    wordpiece(tokens) { const out = []; for (const tok of tokens) { const ch = [...tok]; if (ch.length > 100) { out.push('[UNK]'); continue; } let st = 0, bad = false; const sub = [];
        while (st < ch.length) { let en = ch.length, cs = null; while (st < en) { let s = ch.slice(st, en).join(''); if (st > 0) s = '##' + s; if (this.vocab.has(s)) { cs = s; break; } en--; } if (cs === null) { bad = true; break; } sub.push(cs); st = en; }
        if (bad) out.push('[UNK]'); else out.push(...sub); } return out; },
    encode(text) { const I = this.d.ids; return [I.cls, ...this.wordpiece(this.basic(text)).map(t => this.vocab.has(t) ? this.vocab.get(t) : I.unk), I.sep]; },
    clean(text, isStart) { if (!text) return '';
      text = text.replace(/[^a-zA-Zа-яА-ЯёЁ0-9\s.!?,\-]/g, '').replace(/\s+/g, ' ').replace(/-{2,}/g, ' - ').replace(/([.!?])\1+/g, '$1').replace(/,{2,}/g, ',').replace(/\s+([.,!?])/g, '$1')
        .replace(/([.!?])\1+/g, '$1').replace(/,{2,}/g, ',').replace(/([.,!?])(?=\S)/g, '$1 ').replace(/\s+/g, ' ').trim();
      if (isStart) { text = text.replace(/^[ .,!?-]+/, ''); if (text) text = text[0].toUpperCase() + text.slice(1).toLowerCase(); }
      else { if (text) text = text[0] + text.slice(1).toLowerCase(); if (text && !'.!?'.includes(text[text.length - 1])) text += '.'; }
      return text; },
    decap(name) { for (let i = 0; i < name.length; i++) if (name[i] !== name[i].toLowerCase()) return name.slice(0, i) + '+' + name.slice(i).toLowerCase(); return name; },
    async predict(mark, wl) {
      const re = this.re[wl]; if (re) { const m = re.exec(mark); if (m && m.groups) for (const [k, v] of Object.entries(m.groups)) if (v != null) return this.decap(k); }
      const vars = this.d.homodict[wl]; if (!vars) return null;
      if (!this.ready) { // нейросеть не загружена: подгрузить (если можно), иначе оставить как есть — голос решит сам
        if (this.noModel) return null; try { const ort = global.MKVoice ? await global.MKVoice.loadOrt() : null; if (!ort) return null; await this.load(ort); } catch (e) { this.noModel = true; return null; } }
      const ids = this.encode(mark), I = this.d.ids, a = ids.indexOf(I.hs), b = ids.indexOf(I.he); if (a < 0 || b < 0) return null;
      const H = this.H, L = ids.length, E = new Float32Array(L * H), sc = this.d.scale, zp = this.d.zp;
      for (let i = 0; i < L; i++) { const r = ids[i] * H; for (let j = 0; j < H; j++) E[i * H + j] = (this.q[r + j] - zp) * sc; }
      const hid = (await this.sess.run({ emb: new global.ort.Tensor('float32', E, [1, L, H]) })).hidden.data;
      let x = new Float32Array(2 * H); for (let j = 0; j < H; j++) x[j] = hid[a * H + j];
      const n = Math.max(1, b - a - 1); for (let i = a + 1; i < b; i++) for (let j = 0; j < H; j++) x[H + j] += hid[i * H + j] / n;
      for (const l of this.head) { if (l.t === 'lin') { const y = new Float32Array(l.o); for (let o = 0; o < l.o; o++) { let s = l.b[o]; const r = o * l.i; for (let i = 0; i < l.i; i++) s += l.w[r + i] * x[i]; y[o] = s; } x = y; }
        else if (l.t === 'ReLU') x = x.map(v => Math.max(0, v)); else if (l.t === 'Tanh') x = x.map(Math.tanh); else if (l.t === 'GELU' || l.t === 'GELUActivation') x = x.map(v => .5 * v * (1 + erf(v / Math.SQRT2))); }
      return [...vars].sort()[x[0] > 0 ? 1 : 0]; },
    async solve(sentence) { if (!this.dictReady) return sentence; const hits = [];
      for (const m of sentence.matchAll(/(?=.*[а-яё])[а-яё+]+/gi)) { const w = m[0], wl = w.toLowerCase(); if (!(this.d.homodict[wl] || this.re[wl])) continue;
        let a0 = 0, b0 = sentence.length; if (global.__HOMO_SENT !== false) { // контекст для нейросети — только своё предложение: соседнее («У сестры есть кот. Старый замок…») сбивало её
          for (let k = m.index - 1; k >= 0; k--) if ('.!?…\n'.includes(sentence[k])) { a0 = k + 1; break; } for (let k = m.index + w.length; k < sentence.length; k++) if ('.!?…\n'.includes(sentence[k])) { b0 = k + 1; break; } }
        const st = this.clean(sentence.slice(a0, m.index), true).slice(-(this.d.window >> 1)), en = this.clean(sentence.slice(m.index + w.length, b0), false).slice(0, this.d.window >> 1);
        let p = null; const BR = global.BARSRech; if (BR && BR.rule && this.d.homodict[wl]) { try { p = BR.rule(sentence, m.index, wl, this.d.homodict[wl]); } catch (e) {} }   // БАРС-озвучка: сначала грамматика («у две́ри / на двери́»), потом нейросеть
        if (!p) p = await this.predict((st + ' [HOMO] ' + wl + ' [/HOMO] ' + en).trim(), wl); if (p) hits.push({ s: m.index, e: m.index + w.length, w, p }); }
      let out = sentence, off = 0;
      for (const h of hits) { const nv = [...h.p].filter(c => VOW.includes(c.toLowerCase())).length, si = h.p.indexOf('+'); let wp = h.p.replace('+', '');
        wp = [...h.w].map((c1, i) => wp[i] == null ? '' : (isLower(c1) ? wp[i].toLowerCase() : wp[i].toUpperCase())).join('');
        wp = wp.slice(0, si) + '+' + wp.slice(si); // stress_single_vowel = True: «+» ставится всегда
        out = out.slice(0, h.s + off) + wp + out.slice(h.e + off); off += wp.length - (h.e - h.s); }
      return out; },
  };
  function erf(x) { const t = 1 / (1 + .3275911 * Math.abs(x)), y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - .284496736) * t + .254829592) * t * Math.exp(-x * x); return x >= 0 ? y : -y; }

  // ---------- обратное БПФ любой длины из множителей 2,3,4,5 (n_fft = 2400) ----------
  function makeIFFT(N) {
    const fac = []; let n = N; for (const r of [4, 2, 3, 5]) while (n % r === 0) { fac.push(r); n /= r; } if (n !== 1) throw new Error('n_fft ' + N);
    const cs = new Float64Array(N), sn = new Float64Array(N); for (let k = 0; k < N; k++) { cs[k] = Math.cos(2 * Math.PI * k / N); sn[k] = Math.sin(2 * Math.PI * k / N); }
    function rec(iR, iI, off, stride, n, oR, oI, oo, fi) { // обратное (знак +), без деления на N
      if (n === 1) { oR[oo] = iR[off]; oI[oo] = iI[off]; return; }
      const r = fac[fi], m = n / r;
      for (let q = 0; q < r; q++) rec(iR, iI, off + q * stride, stride * r, m, oR, oI, oo + q * m, fi + 1);
      const tR = new Float64Array(r), tI = new Float64Array(r), step = N / n;
      for (let k = 0; k < m; k++) {
        for (let q = 0; q < r; q++) { const idx = (q * k * step) % N, a = oR[oo + q * m + k], b = oI[oo + q * m + k]; tR[q] = a * cs[idx] - b * sn[idx]; tI[q] = a * sn[idx] + b * cs[idx]; }
        for (let s = 0; s < r; s++) { let xr = 0, xi = 0; for (let q = 0; q < r; q++) { const idx = (q * s * m * step) % N; xr += tR[q] * cs[idx] - tI[q] * sn[idx]; xi += tR[q] * sn[idx] + tI[q] * cs[idx]; }
          oR[oo + s * m + k] = xr; oI[oo + s * m + k] = xi; } } }
    const xR = new Float64Array(N), xI = new Float64Array(N), yR = new Float64Array(N), yI = new Float64Array(N);
    return function irfft(re, im, out) { // re/im: N/2+1 значений → out: N действительных
      const H = N / 2; for (let k = 0; k <= H; k++) { xR[k] = re[k]; xI[k] = (k === 0 || k === H) ? 0 : im[k]; }
      for (let k = 1; k < H; k++) { xR[N - k] = re[k]; xI[N - k] = -im[k]; }
      rec(xR, xI, 0, 1, N, yR, yI, 0, 0); for (let i = 0; i < N; i++) out[i] = yR[i] / N; };
  }

  // ---------- синтез ----------
  const roundEven = x => { const f = Math.floor(x), d = x - f; return d > .5 ? f + 1 : d < .5 ? f : (f % 2 === 0 ? f : f + 1); };
  const MKVoice = {
    ready: false, _p: null, S: null, meta: null, error: null,
    available() { return !!(global.fetch && global.WebAssembly); },
    async loadOrt() { if (global.ort) return global.ort;
      await new Promise((res, rej) => { const s = document.createElement('script'); s.src = ORT + 'ort.wasm.min.js'; s.onload = res; s.onerror = () => rej(new Error('нет onnxruntime')); document.head.appendChild(s); });
      const o = global.ort; o.env.wasm.numThreads = 1; o.env.wasm.proxy = false; o.env.wasm.wasmPaths = new URL(ORT, location.href).href;
      try { o.env.wasm.wasmBinary = await (await fetch(ORT + 'ort-wasm-simd-threaded.wasm')).arrayBuffer(); } catch (e) {} /* сами отдаём wasm — не зависим от типа файла в WKWebView */ return o; },
    /** model: '' — «Альбина» и другие голоса v5 CIS (voice/), 'xenia' — голос Барсика (voice/xenia/, Silero v5_6_ru). В памяти одна модель голоса. */
    load(model) { model = model || ''; if (this._p && this._pm === model) return this._p;
      const prev = this._p; this._pm = model;
      return (this._p = (async () => { try { if (prev) { try { await prev; } catch (e) {} }
        const ort = await this.loadOrt(); const t0 = Date.now();
        if (this.S && this.cur !== model) { for (const s of Object.values(this.S)) { try { await s.release(); } catch (e) {} } this.S = null; this.ready = false; }
        if (!this.S) { const base = BASE + (model ? model + '/' : '');
          this.meta = await (await fetch(base + 'tts.json')).json();
          const M = this.meta; M.sym = new Map(Object.entries(M.symbol_to_id)); M.id2s = []; for (const [ch, id] of Object.entries(M.symbol_to_id)) M.id2s[id] = ch; M.keep = new Set([...M.symbols.slice(3), '^']); M.win = Float32Array.from(M.window);
          this.ifft = makeIFFT(M.istft.n_fft);
          const opt = { executionProviders: ['wasm'], graphOptimizationLevel: 'all' }, S = {};
          for (const k of ['front', 'enc', 'dec', 'voc']) S[k] = await ort.InferenceSession.create(base + k + '.onnx', opt);
          this.S = S; this.cur = model; this.typ = (S.front.inputNames || []).includes('typ'); }
        await MKStress.load(); try { await MKHomo.load(ort); } catch (e) { console.log('омографы не загрузились', e && e.message); } this.ready = true; this.loadMs = Date.now() - t0; return true;
      } catch (e) { this.error = e && e.message || String(e); this._p = null; throw e; } })()); },
    async unload() { if (this.S) for (const s of Object.values(this.S)) { try { await s.release(); } catch (e) {} } await MKHomo.unload(); this.S = null; this.cur = null; this.ready = false; this._p = null; },
    /** Есть ли в приложении файлы голоса этой модели (без загрузки сети). */
    async has(model) { try { const r = await fetch(BASE + (model ? model + '/' : '') + 'tts.json', { method: 'HEAD' }); return r.ok; } catch (e) { try { const r = await fetch(BASE + (model ? model + '/' : '') + 'tts.json'); return r.ok; } catch (e2) { return false; } } },
    /** Текст (уже с «+») → номера символов, как у Silero (prepare_text_input + preprocess_tacotron). */
    ids(text) { const M = this.meta;
      let t = String(text).trim().replace(/\n/g, '. ').toLowerCase().replace(/—/g, '–').replace(/‑/g, '-');
      t = [...t].filter(c => M.keep.has(c)).join('').replace(/\^/g, ' ^').replace(/\s+/g, ' ').trim().replace(/\^ /g, '^').replace(/\^+/g, '^').trim();
      if (t.endsWith('^')) t = t.slice(0, -1).trim();
      if (!/[а-яё]/.test(t)) return null;
      const s = M.sos + t + M.eos, out = []; for (const c of s) { const id = M.sym.get(c); if (id != null) out.push(id); } return out; },
    /** Один кусок (до ~800 знаков) → Float32Array 48 кГц. */
    async chunk(text, o) {
      const ort = global.ort, M = this.meta, S = this.S, ids = this.ids(text); if (!ids) return new Float32Array(0);
      const N = ids.length, spkId = M.speakers[o.speaker] != null ? M.speakers[o.speaker] : M.speakers.ru_albina != null ? M.speakers.ru_albina : Object.values(M.speakers)[0];
      const seq = new ort.Tensor('int64', BigInt64Array.from(ids.map(BigInt)), [1, N]), spk = new ort.Tensor('int64', BigInt64Array.from([BigInt(spkId)]), [1]);
      const fin = { seq, spk }; if (this.typ) { fin.typ = new ort.Tensor('int64', BigInt64Array.from(typeIds(ids, M, o.typeFix).map(BigInt)), [1, N]); fin.foc = new ort.Tensor('int64', new BigInt64Array(N), [1, N]); }
      const fo = await S.front.run(fin), ld = fo.logdur.data, pitch = new Float32Array(fo.pitch.data);
      // длительности — как в MultiTTSModel.forward
      const d = new Array(N); for (let i = 0; i < N; i++) d[i] = roundEven(Math.max(Math.exp(ld[i]) - 1, 0));
      if (d[0] > 5) d[0] = 5;
      const rate = o.rate || 1; if (rate !== 1) for (let i = 0; i < N; i++) d[i] = roundEven(d[i] / rate);
      if (d[0] > 5) d[0] = 5; if (d[N - 1] > 7) d[N - 1] = 7; d[N - 2] = 13; if (d[N - 3] > 13) d[N - 3] = 13;
      const pc = o.pitch || 1; if (pc !== 1) { const sh = (pc - 1) * (M.mean_std_coef[spkId] || 0); for (let i = 0; i < N; i++) { let v = Math.abs(pitch[i]) < .001 ? 0 : pitch[i] * pc; pitch[i] = v === 0 ? 0 : v + sh; } }
      // БАРС-озвучка: «режиссёр» правит длительности и высоту по символам (смех в ритме настоящего, «ура-а-а», пение, живость интонации)
      if (o.shape) { try { o.shape({ toks: ids.map(i => M.id2s[i]), d, pitch, coef: M.mean_std_coef[spkId] || 0, N, frame: M.istft.hop / 48000 }); } catch (e) { console.log('shape', e && e.message); } for (let i = 0; i < N; i++) d[i] = Math.max(0, Math.round(d[i])); }
      this.lastAlign = { toks: ids.map(i => M.id2s[i]), d: d.slice(), frame: M.istft.hop / 48000 };
      const eo = await S.enc.run({ seq, spk, pitch: new ort.Tensor('float32', pitch, [1, 1, N]) }), E = eo.enc.data, D = eo.enc.dims[2];
      let T = 0; for (const x of d) T += x; if (T < 3) return new Float32Array(0);
      const X = new Float32Array(T * D); let r = 0; for (let i = 0; i < N; i++) for (let k = 0; k < d[i]; k++) { X.set(E.subarray(i * D, (i + 1) * D), r * D); r++; }
      const mel = (await S.dec.run({ x: new ort.Tensor('float32', X, [1, T, D]) })).mel;
      const vo = await S.voc.run({ mel }), mag = vo.mag.data, ph = vo.phase.data, F = vo.mag.dims[1], TT = vo.mag.dims[2];
      // ISTFT («same»): обратное БПФ кадра × окно, сложение внахлёст, деление на огибающую окна
      const { n_fft, hop, win } = M.istft, W = M.win, pad = (win - hop) >> 1, L = (TT - 1) * hop + win;
      const out = new Float32Array(L), env = new Float32Array(L), re = new Float64Array(F), im = new Float64Array(F), fr = new Float64Array(n_fft);
      for (let t = 0; t < TT; t++) { for (let k = 0; k < F; k++) { const a = mag[k * TT + t], p = ph[k * TT + t]; re[k] = a * Math.cos(p); im[k] = a * Math.sin(p); }
        this.ifft(re, im, fr); const o0 = t * hop; for (let i = 0; i < win; i++) { out[o0 + i] += fr[i] * W[i]; env[o0 + i] += W[i] * W[i]; } }
      const y = new Float32Array(L - 2 * pad); for (let i = 0; i < y.length; i++) y[i] = out[pad + i] / Math.max(env[pad + i], 1e-11);
      return y; },
    /** Текст → текст с «+» у каждого слова: словарь пользователя → грамматика (БАРС) → омографы по смыслу → модель ударений. Один путь для всех нейроголосов. */
    async marks(text, lex) { await MKStress.load(); if (!MKHomo.ready && !MKHomo.dictReady) { try { await MKHomo.loadDict(); } catch (e) {} }
      if (global.BARSRech) global.BARSRech.yo = !!(lex && lex.yo);   // в серии автор ставит «ё» — значит «все» это «все», а не «всё»
      let t = MKStress.userMarks(String(text || ''), lex); if (global.BARSRech) { try { t = global.BARSRech.pre(t); } catch (e) {} }
      if (MKHomo.ready || MKHomo.dictReady) { try { t = await MKHomo.solve(t); } catch (e) { console.log('омографы', e && e.message); } } return MKStress.accent(t, null); },
    /** Текст → голос. o: {speaker:'ru_albina', rate:1, pitch:1, lex, accent:true}. Возвращает Float32Array 48 кГц. */
    async speak(text, o) { o = o || {};
      if (o.marksOnly) { // только ударения, без звука (голоса iPhone спрашивают отсюда, из отдельного процесса): 'homo' — словарь пользователя + грамматика + омографы, 'all' — «+» у каждого слова
        this.lastText = o.marksOnly === 'all' ? await this.marks(text, o.lex) : await this.homoMarks(text, o.lex);
        return new Float32Array(0); }
      if (o.bars && global.BARSGolos && global.BARSGolos.render) return global.BARSGolos.render(text, o);   // БАРС-озвучка: смех, звуки, протяжные слова, паспорт голоса
      await this.load(o.model);
      let t = String(text || '').replace(/[«»"“”]/g, '').replace(/\s+/g, ' ').trim(); if (!t) return new Float32Array(0);
      if (o.accent !== false) t = await this.marks(t, o.lex);
      this.lastText = t;
      const parts = [], cur = []; for (const s of t.split(/(?<=[.!?…])\s+/)) { if (cur.join(' ').length + s.length > 700 && cur.length) { parts.push(cur.join(' ')); cur.length = 0; } cur.push(s); } if (cur.length) parts.push(cur.join(' '));
      const bufs = []; for (const p of parts) { bufs.push(await this.chunk(p, o)); bufs.push(new Float32Array(Math.round(48000 * .22))); } bufs.pop();
      const n = bufs.reduce((a, b) => a + b.length, 0), y = new Float32Array(n); let k = 0; for (const b of bufs) { y.set(b, k); k += b.length; } return y; },
  };
  /** Для голосов iPhone: текст с «+» только у слов из словаря пользователя и у омографов по смыслу (остальное iPhone ставит сам).
      Свои «+» в тексте не трогаются. Нейросеть омографов подгружается только если словарь фраз не решил. */
  MKVoice.homoMarks = async function (text, lex) {
    let t = String(text || ''); if (!t.trim()) return t;
    if (global.BARSRech) global.BARSRech.yo = !!(lex && lex.yo);
    t = MKStress.userMarks(t, lex); if (global.BARSRech) { try { t = global.BARSRech.pre(t); } catch (e) {} }
    if (!MKHomo.dictReady && !(global.MK && global.MK.isHomograph)) { try { await MKHomo.loadDict(); } catch (e) { return t; } }   // в странице голоса встроенного списка омографов нет — нужен словарь
    if (!MKHomo.has(t)) return t;
    try { await MKHomo.loadDict(); t = await MKHomo.solve(t); } catch (e) { console.log('омографы', e && e.message); }
    return t;
  };
  /** «Мягкий тон» (как выбирали на слух): чуть теплее, без резкости, ровнее, с лёгким «воздухом». → AudioBuffer */
  MKVoice.soften = async function (y, sr) { sr = sr || 48000; const ac = new OfflineAudioContext(1, y.length + Math.round(sr * .1), sr);
    const b = ac.createBuffer(1, y.length, sr); b.getChannelData(0).set(y); const src = ac.createBufferSource(); src.buffer = b; let node = src;
    const add = n => { node.connect(n); node = n; };
    const hp = ac.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 70; add(hp);
    const ls = ac.createBiquadFilter(); ls.type = 'lowshelf'; ls.frequency.value = 160; ls.gain.value = 2.5; add(ls);
    const pk = ac.createBiquadFilter(); pk.type = 'peaking'; pk.frequency.value = 3200; pk.Q.value = 1.4; pk.gain.value = -2.5; add(pk);
    const ds = ac.createBiquadFilter(); ds.type = 'peaking'; ds.frequency.value = 6500; ds.Q.value = 2; ds.gain.value = -2; add(ds);
    const cp = ac.createDynamicsCompressor(); cp.threshold.value = -22; cp.ratio.value = 2.2; cp.attack.value = .012; cp.release.value = .22; cp.knee.value = 6; add(cp);
    const mix = ac.createGain(); node.connect(mix);
    for (const [ms, g] of [[28, .08], [47, .05]]) { const dl = ac.createDelay(.2); dl.delayTime.value = ms / 1000; const gg = ac.createGain(); gg.gain.value = g; node.connect(dl); dl.connect(gg); gg.connect(mix); }
    mix.connect(ac.destination); src.start(0); return ac.startRendering(); };
  // ---------- тип предложения для xenia (как classify_sentence / build_type_ids_tokens в Silero v5_6_ru) ----------
  const TYPE2ID = { st: 0, wh_q: 1, general_q: 2, alternative_q: 3, tag_q: 4, exclam: 5 };
  const WH = new Set('кто кого кому кем ком что чего чему чем чём чё чо где куда откуда когда почему зачем как почём отчего насколько сколько скольких скольким сколькими какой какая какое какие какого каких какому каким какими каком какую чей чья чьё чье чьи чьего чьей чьих чьему чьим чьими чьём чьем чью который которая которое которые которого которой которых которому которым которыми котором которую каков какова каково каковы'.split(' '));
  const FILL = new Set('а ну и так вот слышь слушай скажите скажи пожалуйста вобще вообще типа короче'.split(' '));
  const TAG_RE = /(?:[,\s]+(правда|верно|да)\s*\?$)|(?:[,\s]+(не\s+так\s+ли|не\s+правда\s+ли|разве\s+не\s+так|ведь\s+так)\s*\?$)|(?:[,\s]+ведь\s*\?$)|(?:[,\s]+а\s*\?$)/i;
  const QO = new Set(['"', '«', '“', '„']), QC = new Set(['"', '»', '”', '’']);
  const stripQ = s => { s = s.trim(); while (s && QO.has(s[0])) s = s.slice(1).trim(); while (s && QC.has(s[s.length - 1])) s = s.slice(0, -1).trim(); return s; };
  const normClf = s => stripQ(s).replace(/\+/g, '').replace(/ё/g, 'е').replace(/Ё/g, 'Е').replace(/\s+/g, ' ').trim();
  const hasWh = t => { const words = (t.toLowerCase().match(/[а-яёa-z]+/gi) || []).slice(0, 8), c = []; for (const w of words) { if (FILL.has(w)) continue; c.push(w); if (c.length >= 4) break; } return c.some(w => WH.has(w)); };
  function classifySentence(s) { s = String(s || '').trim(); if (!s) return 'st'; const sc = stripQ(s); if (!sc) return 'st'; let tail = sc;
    if (tail.endsWith('?!') || tail.endsWith('?..') || tail.endsWith('?...')) tail = tail.replace(/[.!]+$/, '');
    if (tail.endsWith('?')) { const q = normClf(tail); if (TAG_RE.test(q)) return 'tag_q'; if (hasWh(q)) return 'wh_q'; if (/(^|[^а-яёa-z0-9_])или([^а-яёa-z0-9_]|$)/i.test(q)) return 'alternative_q'; return 'general_q'; }
    return sc.endsWith('!') ? 'exclam' : 'st'; }
  function charSentIds(text) { const ids = [], re = /(?<=[.!?])\s+/g; let pos = 0, si = 0, m; while ((m = re.exec(text))) { const end = m.index + m[0].length; for (let i = pos; i < end; i++) ids.push(si); pos = end; si++; } for (let i = pos; i < text.length; i++) ids.push(si); return ids; }
  function typeIds(ids, M, fix) { const toks = ids.map(i => M.symbols[i]), N = toks.length, body = toks.slice(1, -1).join(''), sid = charSentIds(body);
    const nS = sid.length ? sid[sid.length - 1] + 1 : 0, tids = [];
    for (let k = 0; k < nS; k++) { let a = -1, b = -1; for (let i = 0; i < sid.length; i++) if (sid[i] === k) { if (a < 0) a = i + 1; b = i + 2; } while (b > a && toks[b - 1] === ' ') b--; tids.push(TYPE2ID[classifySentence(toks.slice(a, b).join('').replace(/\+/g, ''))] || 0); }
    const vals = sid.map(s => tids[Math.min(s, tids.length - 1)] || 0), out = new Array(N).fill(0); if (!vals.length) return out;
    for (let i = 0; i < vals.length; i++) { const j = i + 1; if (j < N - 1) out[j] = vals[i]; } out[0] = vals[0]; out[N - 1] = vals[vals.length - 1];
    if (fix) { // БАРС-озвучка: «…и шёпотом спросил: Пик, ты слышишь?» — рассказ до двоеточия остаётся рассказом, вопрос после двоеточия — вопросом
      // (без этого вся фраза считалась вопросом «когда…?» по первому слову, и «ты слышишь?» звучало ровно)
      for (let k = 0; k < nS; k++) { let a = -1, b = -1; for (let i = 0; i < sid.length; i++) if (sid[i] === k) { if (a < 0) a = i + 1; b = i + 2; } if (a < 0) continue;
        while (b > a && toks[b - 1] === ' ') b--; let c = -1; for (let j = b - 1; j >= a; j--) if (toks[j] === ':') { c = j; break; } if (c < 0) continue;
        const tail = toks.slice(c + 1, b).join('').replace(/\+/g, '').trim(), head = toks.slice(a, c).join('').replace(/\+/g, '');
        if (!/[?!]$/.test(stripQ(tail)) || (head.match(/[а-яё]+/gi) || []).length < 3) continue;
        const tt = /\?$/.test(stripQ(tail)) && /(^|[^а-яё])или([^а-яё]|$)/i.test(tail) ? TYPE2ID.alternative_q : (TYPE2ID[classifySentence(tail)] || 0);   // «кто это там — Рон или сова?» — выбор
        for (let j = a; j <= c; j++) out[j] = 0; for (let j = c + 1; j < Math.min(b + 1, N - 1); j++) out[j] = tt; }
      out[0] = out[1]; out[N - 1] = out[N - 2]; }
    return out; }
  MKVoice._typeIds = typeIds; MKVoice._classify = classifySentence;
  global.MKVoice = MKVoice; global.MKStress = MKStress; global.MKHomo = MKHomo;
})(typeof window !== 'undefined' ? window : globalThis);
