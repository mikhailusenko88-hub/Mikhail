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
    accent(sentence, lex) { if (!this.ready) return sentence;
      const user = (lex && lex.stress) || {};
      sentence = sentence.replace(/[А-Яа-яЁё]+/g, w => { const u = user[w.toLowerCase().replace(/ё/g, 'е')] || user[w.toLowerCase()]; if (!u || w.includes('+')) return w;
        let out = '', j = 0; for (const c of u) { if (c === '+') { out += '+'; continue; } const o = w[j++] || c; out += isLower(o) ? c : c.toUpperCase(); } return out; });
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
    load() { if (this._p) return this._p;
      return (this._p = (async () => { try {
        const ort = await this.loadOrt(); const t0 = Date.now();
        this.meta = await (await fetch(BASE + 'tts.json')).json();
        const M = this.meta; M.sym = new Map(Object.entries(M.symbol_to_id)); M.keep = new Set([...M.symbols.slice(3), '^']); M.win = Float32Array.from(M.window);
        this.ifft = makeIFFT(M.istft.n_fft);
        const opt = { executionProviders: ['wasm'], graphOptimizationLevel: 'all' }, S = {};
        for (const k of ['front', 'enc', 'dec', 'voc']) S[k] = await ort.InferenceSession.create(BASE + k + '.onnx', opt);
        this.S = S; await MKStress.load(); this.ready = true; this.loadMs = Date.now() - t0; return true;
      } catch (e) { this.error = e && e.message || String(e); this._p = null; throw e; } })()); },
    async unload() { if (this.S) for (const s of Object.values(this.S)) { try { await s.release(); } catch (e) {} } this.S = null; this.ready = false; this._p = null; },
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
      const N = ids.length, spkId = M.speakers[o.speaker] != null ? M.speakers[o.speaker] : M.speakers.ru_albina;
      const seq = new ort.Tensor('int64', BigInt64Array.from(ids.map(BigInt)), [1, N]), spk = new ort.Tensor('int64', BigInt64Array.from([BigInt(spkId)]), [1]);
      const fo = await S.front.run({ seq, spk }), ld = fo.logdur.data, pitch = new Float32Array(fo.pitch.data);
      // длительности — как в MultiTTSModel.forward
      const d = new Array(N); for (let i = 0; i < N; i++) d[i] = roundEven(Math.max(Math.exp(ld[i]) - 1, 0));
      if (d[0] > 5) d[0] = 5;
      const rate = o.rate || 1; if (rate !== 1) for (let i = 0; i < N; i++) d[i] = roundEven(d[i] / rate);
      if (d[0] > 5) d[0] = 5; if (d[N - 1] > 7) d[N - 1] = 7; d[N - 2] = 13; if (d[N - 3] > 13) d[N - 3] = 13;
      const pc = o.pitch || 1; if (pc !== 1) { const sh = (pc - 1) * (M.mean_std_coef[spkId] || 0); for (let i = 0; i < N; i++) { let v = Math.abs(pitch[i]) < .001 ? 0 : pitch[i] * pc; pitch[i] = v === 0 ? 0 : v + sh; } }
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
    /** Текст → голос. o: {speaker:'ru_albina', rate:1, pitch:1, lex, accent:true}. Возвращает Float32Array 48 кГц. */
    async speak(text, o) { o = o || {}; await this.load();
      let t = String(text || '').replace(/[«»"“”]/g, '').replace(/\s+/g, ' ').trim(); if (!t) return new Float32Array(0);
      if (o.accent !== false) t = MKStress.accent(t, o.lex);
      const parts = [], cur = []; for (const s of t.split(/(?<=[.!?…])\s+/)) { if (cur.join(' ').length + s.length > 700 && cur.length) { parts.push(cur.join(' ')); cur.length = 0; } cur.push(s); } if (cur.length) parts.push(cur.join(' '));
      const bufs = []; for (const p of parts) { bufs.push(await this.chunk(p, o)); bufs.push(new Float32Array(Math.round(48000 * .22))); } bufs.pop();
      const n = bufs.reduce((a, b) => a + b.length, 0), y = new Float32Array(n); let k = 0; for (const b of bufs) { y.set(b, k); k += b.length; } return y; },
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
  global.MKVoice = MKVoice; global.MKStress = MKStress;
})(typeof window !== 'undefined' ? window : globalThis);
