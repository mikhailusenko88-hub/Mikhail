// Банк настоящих смехов (Resources/Mebel/laugh/): готовые записи смеха, сгенерированные нейросетью Bark (MIT), без чужих прав.
// Герой смеётся записью из банка, пропущенной через свой тембр (MK.voiceFx — как и речь), с короткой/полной версией
// и лёгкой случайной вариацией, чтобы один и тот же смех не повторялся нота в ноту.
(function (global) {
  const L = { bank: null, _bufs: {}, _loading: null, base: 'laugh/' };
  const hash32 = s => { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h; };

  /** Прочитать файл банка: fetch (в приложении — схема mebel://), а на file:// в тестах — XMLHttpRequest. */
  L._read = async function (url, bin) {
    try { const r = await fetch(url); if (!r.ok) return null; return bin ? r.arrayBuffer() : r.text(); } catch (e) {}
    return new Promise(res => { try { const x = new XMLHttpRequest(); x.open('GET', url); if (bin) x.responseType = 'arraybuffer'; x.onload = () => res(x.status && x.status !== 200 && x.status !== 0 ? null : x.response); x.onerror = () => res(null); x.send(); } catch (e) { res(null); } });
  };
  /** Загрузить описание банка (один раз). */
  L.load = async function () {
    if (L.bank) return L.bank;
    if (!L._loading) L._loading = L._read(L.base + 'bank.json').then(t => { let b = null; try { b = t && JSON.parse(t); } catch (e) {} L.bank = b && b.laughs ? b : { laughs: [] }; return L.bank; }).catch(() => { L.bank = { laughs: [] }; return L.bank; });
    return L._loading;
  };
  L.list = () => (L.bank && L.bank.laughs) || [];
  L.byId = id => L.list().find(x => x.id === id) || null;

  /** Высота голоса героя до обработки тембром (тембр k потом одинаково сдвигает и речь, и смех):
      голос iPhone ≈ 205 Гц женский / 115 Гц мужской, умноженный на pitch. */
  L.targetF0 = function (spec) { const v = (spec && spec.voice) || {}; return (v.base === 'male' ? 115 : 205) * (v.pitch || 1); };
  /** Какой смех у героя: выбранный в настройках (c.laughId) или автоматически — ближайший по высоте к его голосу,
      хихиканье для писклявых, басистый для великанов; всегда один и тот же для героя (по имени). */
  L.idFor = function (ln, lib) {
    const list = L.list().filter(x => !/\+$/.test(x.id)); if (!list.length) return null;
    const c = (lib.characters || {})[ln.who] || {};
    const pk = typeof MK !== 'undefined' && MK.laughPick ? MK.laughPick(lib, ln.who) : c.laughId; // 'voice' — своим голосом (Барсик, Пик по умолчанию)
    if (pk === 'voice') return 'voice'; if (pk && L.byId(pk)) return pk;
    const nm = String((c.spec && c.spec.name) || '').trim().toLowerCase(), hd = (L.bank && L.bank.heroes) || {}; // выбранные на пробах (Барсик — F9, Рон — M4)
    if (nm && hd[nm] && L.byId(hd[nm])) return hd[nm];
    if (ln.who === '?') { const K = list.filter(x => x.group === 'K' && x.style === 'giggle'); return (K[0] || list[0]).id; }
    const fx = ln.fx || {}, id = fx.id, t = L.targetF0(c.spec);
    const want = id === 'squeaky' || id === 'chipmunk' || id === 'baby' ? 'giggle' : (id === 'giant' || id === 'monster' || id === 'dragon' || id === 'deep') ? 'belly' : null;
    const sc = list.map(x => { let d = Math.abs(Math.log((x.f0 || t) / t)); if (want && x.style !== want) d += .25; if (!want && x.style === 'belly' && t > 150) d += .3; if (x.dur < 1.2) d += .1; return [d, x]; }).sort((a, b) => a[0] - b[0]);
    const top = sc.slice(0, 3).filter(a => a[0] <= sc[0][0] + .22).map(a => a[1]);
    const seed = hash32(String(ln.who) + ((c.spec && c.spec.name) || ''));
    return top[seed % top.length].id;
  };

  /** Раскодировать wav → AudioBuffer (кэш по id). */
  L.get = async function (id) {
    if (L._bufs[id]) return L._bufs[id];
    const e = L.byId(id); if (!e) return null;
    const ab = await L._read(L.base + e.file, true); if (!ab) return null;
    const ac = new OfflineAudioContext(1, 1, 44100);
    const buf = await new Promise((res, rej) => { const p = ac.decodeAudioData(ab, res, rej); if (p && p.then) p.then(res, rej); });
    L._bufs[id] = buf; return buf;
  };

  /** Растянуть/сжать по времени без смены высоты (WSOLA): тембр героя k ускоряет запись в k раз,
      поэтому смех заранее растягиваем в k раз — ритм «ха-ха» остаётся естественным, меняется только высота. */
  function wsola(x, sr, f) {
    if (Math.abs(f - 1) < .02) return x;
    const N = Math.round(sr * .032), H = N >> 1, tol = Math.round(sr * .006), n = x.length, outLen = Math.round(n * f);
    const out = new Float32Array(outLen + N), wsum = new Float32Array(outLen + N), win = new Float32Array(N);
    for (let i = 0; i < N; i++) win[i] = .5 - .5 * Math.cos(2 * Math.PI * i / N);
    let prev = -1;
    for (let o = 0; o < outLen; o += H) {
      const ideal = Math.round(o / f); let best = ideal;
      if (prev >= 0) { const nat = prev + H; let bc = -Infinity;
        for (let d = -tol; d <= tol; d += 2) { const c0 = ideal + d; if (c0 < 0 || c0 + N > n || nat + N > n) continue; let c = 0; for (let i = 0; i < N; i += 2) c += x[c0 + i] * x[nat + i]; if (c > bc) { bc = c; best = c0; } } }
      if (best + N > n) best = Math.max(0, n - N); if (best < 0) best = 0;
      for (let i = 0; i < N; i++) { out[o + i] += x[best + i] * win[i]; wsum[o + i] += win[i]; }
      prev = best;
    }
    for (let i = 0; i < outLen; i++) if (wsum[i] > 1e-3) out[i] /= wsum[i];
    return out.subarray(0, outLen);
  }
  L.wsola = wsola;

  /** Готовый смех: полный или короткий (первые 3–4 слога), растянут под тембр k, чуть другой темп по variant. → AudioBuffer 44.1 кГц */
  L.render = async function (id, opt) {
    opt = opt || {}; const e = L.byId(id), raw = await L.get(id); if (!e || !raw) return null;
    const sr = raw.sampleRate, d = raw.getChannelData(0); let a = 0, b = d.length;
    const syl = e.syl || [];
    if (opt.short && syl.length > 4) { // короткий смешок: до начала 4-го (или 5-го, если слоги быстрые) слога
      const n = syl[3] - syl[0] < .45 ? 4 : 3; const tEnd = syl[n] - .02;
      b = Math.min(b, Math.round(tEnd * sr));
    } else if (opt.short && raw.duration > 1.6) b = Math.round(1.45 * sr);
    const v = (opt.variant || 0) % 3, rate = [1, 1.035, .97][v];
    let out = new Float32Array(b - a); out.set(d.subarray(a, b));
    { const n = out.length, f = Math.min(n >> 2, Math.round(sr * .04)); for (let i = 0; i < f; i++) { const g = i / f; out[n - 1 - i] *= g; out[i] *= Math.min(1, g * 4); } }
    const k = opt.k || 1; if (k !== 1) out = wsola(out, sr, Math.min(1.8, Math.max(.6, k)));
    const n = out.length, ac = new OfflineAudioContext(1, Math.ceil(n / rate) + 64, 44100);
    const src = ac.createBufferSource(), bb = ac.createBuffer(1, n, sr); bb.copyToChannel(out, 0); src.buffer = bb; src.playbackRate.value = rate; src.connect(ac.destination); src.start(0);
    return ac.startRendering();
  };
  global.MKLaugh = L;
})(typeof window !== 'undefined' ? window : globalThis);
