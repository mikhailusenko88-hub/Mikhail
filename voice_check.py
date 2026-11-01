#!/usr/bin/env python3
# «Слух» для озвучки: что сказано, где ударения, интонация, паузы, темп, естественность.
# Вход: in/<имя>.(wav|mp3|m4a|ogg) + in/<имя>.txt (эталонный текст, можно с «+» перед ударной гласной).
# Выход: out/<имя>.md (отчёт), out/<имя>.png (спектрограмма + высота голоса), out/<имя>.json, out/summary.md
import glob, hashlib, json, math, os, re, subprocess, sys, traceback, difflib
import numpy as np

IN, OUT = "in", "out"
os.makedirs(OUT, exist_ok=True)
SR = 16000
VOW = "аеёиоуыэюя"
IPAV = set("aɐəeɛiɪɨoɵuʊʉæɑɔyøœɤʌɒɜɞ")
# какие звуки распознавателя означают «полную» (ударную) гласную для данной буквы; безударные редуцируются
QFULL = {"о": set("oɔɵ"), "а": set("aɑæ"), "е": set("eɛ"), "э": set("eɛ"), "я": set("aɑæ")}
QW = {"о": 1.6, "е": 1.4, "э": 1.4, "я": 1.2, "а": 0.7}
WH = {"кто", "что", "где", "когда", "почему", "зачем", "как", "какой", "какая", "какое", "какие", "каких",
      "куда", "откуда", "сколько", "чей", "чья", "чьё", "чьи", "отчего", "каким", "какую", "кого", "чего", "кому", "чем"}
FORCE = os.path.exists("request.txt") and "force" in open("request.txt", encoding="utf-8").read().lower()

def log(*a):
    print(*a, flush=True)

def load16(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()

# ---------------- текст ----------------
def tokenize(text):
    text = re.sub(r"([" + VOW + VOW.upper() + r"])́", r"+\1", text)  # знак ударения → «+» перед гласной
    out = []
    for m in re.finditer(r"[А-Яа-яЁё+]+(?:-[А-Яа-яЁё+]+)*|[.!?…,;:—–]", text):
        t = m.group(0)
        if re.match(r"[.!?…,;:—–]", t):
            if out:
                out[-1]["punct"] += t
            continue
        plain = t.replace("+", "").lower()
        vows = [c for c in plain if c in VOW]
        exp = None
        if "+" in t:
            low = t.lower()
            i = low.index("+")
            exp = sum(1 for c in low[:i] if c in VOW)
        elif "ё" in plain:
            exp = [i for i, c in enumerate(vows) if c == "ё"][0]
        elif len(vows) == 1:
            exp = 0
        out.append({"raw": t, "w": plain, "vows": vows, "exp": exp, "punct": ""})
    s = 0
    for w in out:
        w["sent"] = s
        if re.search(r"[.!?…]", w["punct"]):
            s += 1
    return out

def accentize(text, words):
    need = [w for w in words if w["exp"] is None and len(w["vows"]) > 1]
    if not need:
        return "дано в тексте"
    try:
        from ruaccent import RUAccent
        acc = RUAccent()
        ok = False
        for size in ["turbo3.1", "turbo3", "turbo2", "turbo", "tiny2", "tiny"]:
            try:
                acc.load(omograph_model_size=size, use_dictionary=True)
                ok = True
                break
            except Exception:
                continue
        if not ok:
            acc.load()
        plain = " ".join(w["w"] + w["punct"] for w in words)
        res = acc.process_all(plain)
        rw = tokenize(res)
        if len(rw) == len(words):
            for w, r in zip(words, rw):
                if w["exp"] is None and r["exp"] is not None:
                    w["exp"] = r["exp"]; w["auto"] = True
            return "ruaccent"
        log("ruaccent: число слов не совпало", len(rw), len(words))
    except Exception:
        log("ruaccent FAIL", traceback.format_exc())
    return "нет"

def mark(word, idx):
    if idx is None:
        return word
    k = -1
    s = []
    for c in word:
        if c in VOW:
            k += 1
            s.append(c.upper() if k == idx else c)
        else:
            s.append(c)
    return "".join(s)

def norm_words(t):
    t = t.lower().replace("ё", "е").replace("+", "")
    return re.sub(r"[^а-я0-9 -]+", " ", t).split()

# ---------------- модели (ленивая загрузка) ----------------
_m = {}
def phon_model():
    if "ph" not in _m:
        import torch
        from transformers import AutoProcessor, Wav2Vec2ForCTC
        name = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
        _m["ph"] = (AutoProcessor.from_pretrained(name), Wav2Vec2ForCTC.from_pretrained(name).eval())
    return _m["ph"]

def whisper_model():
    if "wh" not in _m:
        import whisper
        _m["wh"] = whisper.load_model(os.environ.get("WHISPER", "small"))
    return _m["wh"]

def utmos_model():
    if "mos" not in _m:
        import torch
        _m["mos"] = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
    return _m["mos"]

def phonemize_words(words):
    from phonemizer import phonemize
    from phonemizer.separator import Separator
    ph = phonemize([w["w"] for w in words], language="ru", backend="espeak",
                   separator=Separator(phone=" ", word="", syllable=""), strip=True, njobs=1)
    return [p.split() for p in ph]

# ---------------- выравнивание по фонемам ----------------
def align(audio, words):
    import torch, torchaudio.functional as AF
    proc, model = phon_model()
    tok = proc.tokenizer
    vocab = tok.get_vocab()
    inv = {i: t for t, i in vocab.items()}
    blank = tok.pad_token_id
    special = {blank, tok.unk_token_id, getattr(tok, "bos_token_id", None), getattr(tok, "eos_token_id", None)}
    vowel_ids = [i for t, i in vocab.items() if t and t[0] in IPAV and i not in special]
    qids = {L: [i for i in vowel_ids if inv[i][0] in S] for L, S in QFULL.items()}
    with torch.no_grad():
        x = proc(audio, sampling_rate=SR, return_tensors="pt").input_values
        lp = torch.log_softmax(model(x).logits[0], -1)  # (T, V)
    T = lp.shape[0]
    fps = T / (len(audio) / SR)
    phs = phonemize_words(words)
    cols, tgt, meta = [blank], [], []
    colmap = {}
    for wi, (w, pl) in enumerate(zip(words, phs)):
        vk = 0
        nv = sum(1 for p in pl if p[0] in IPAV)
        w["ph"] = " ".join(pl)
        w["map_ok"] = nv == len(w["vows"])
        for p in pl:
            if p[0] in IPAV:
                key = "V"; meta.append((wi, vk)); vk += 1
            else:
                cand = [p, p.replace("ʲ", ""), p.replace("ː", ""), p[0]]
                key = next((c for c in cand if c in vocab and vocab[c] not in special), None)
                if key is None:
                    continue
                meta.append((wi, None))
            if key not in colmap:
                colmap[key] = len(cols); cols.append(key)
            tgt.append(colmap[key])
    em = torch.empty(T, len(cols))
    em[:, 0] = lp[:, blank]
    for key, c in colmap.items():
        em[:, c] = torch.logsumexp(lp[:, vowel_ids], -1) if key == "V" else lp[:, vocab[key]]
    ali, sc = AF.forced_align(em[None], torch.tensor([tgt], dtype=torch.int32), blank=0)
    spans = AF.merge_tokens(ali[0], sc[0].exp())
    probs = lp.exp()
    vowels = []
    for sp, (wi, vk) in zip(spans, meta):
        words[wi].setdefault("t0", sp.start / fps)
        words[wi]["t1"] = sp.end / fps
        if vk is None:
            continue
        f0, f1 = max(0, sp.start - 1), min(T, max(sp.end, sp.start + 1) + 1)
        pv = probs[f0:f1]
        PV = float(pv[:, vowel_ids].sum(1).mean())
        L = words[wi]["vows"][vk] if words[wi]["map_ok"] and vk < len(words[wi]["vows"]) else ""
        q = float(pv[:, qids[L]].sum(1).mean()) / (PV + 1e-6) if L in qids else None
        top = int(pv[:, vowel_ids].mean(0).argmax())
        vowels.append({"w": wi, "k": vk, "t0": sp.start / fps, "t1": sp.end / fps,
                       "c": (sp.start + sp.end) / 2 / fps, "q": q, "L": L, "ph": inv[vowel_ids[top]]})
    return vowels

# ---------------- просодия ----------------
def st(f):
    return 12 * math.log2(f / 100.0)

def prosody(audio):
    import parselmouth
    snd = parselmouth.Sound(audio.astype(np.float64), SR)
    p = snd.to_pitch_ac(time_step=0.01, pitch_floor=70, pitch_ceiling=500)
    f0 = p.selected_array["frequency"]; pt = p.xs()
    it = snd.to_intensity(minimum_pitch=70, time_step=0.01)
    return snd, pt, f0, it.xs(), it.values[0]

def feats(v, prev_c, next_c, P):
    _, pt, f0, itx, iv = P
    a = max(v["c"] - 0.12, (prev_c + v["c"]) / 2 if prev_c is not None else v["c"] - 0.08)
    b = min(v["c"] + 0.12, (next_c + v["c"]) / 2 if next_c is not None else v["c"] + 0.08)
    m = (itx >= a) & (itx <= b)
    if m.sum() == 0:
        return dict(I=np.nan, F=np.nan, D=np.nan)
    seg = iv[m]; k = int(seg.argmax()); peak = seg[k]
    l = k
    while l > 0 and seg[l - 1] >= peak - 3: l -= 1
    r = k
    while r < len(seg) - 1 and seg[r + 1] >= peak - 3: r += 1
    fm = (pt >= a) & (pt <= b) & (f0 > 0)
    F = float(np.median([st(x) for x in f0[fm]])) if fm.sum() else np.nan
    return dict(I=float(peak), F=F, D=(r - l + 1) * 0.01)

def z(x):
    x = np.array(x, float)
    if np.all(np.isnan(x)):
        return np.zeros_like(x)
    x = np.where(np.isnan(x), np.nanmean(x), x)
    s = x.std()
    return (x - x.mean()) / s if s > 1e-6 else np.zeros_like(x)

W = dict(I=1.0, F=0.8, D=0.8)

def stress(words, vowels, P):
    for i, v in enumerate(vowels):
        pc = vowels[i - 1]["c"] if i > 0 else None
        nc = vowels[i + 1]["c"] if i + 1 < len(vowels) else None
        v.update(feats(v, pc, nc, P))
    for wi, w in enumerate(words):
        vs = [v for v in vowels if v["w"] == wi]
        w["vf"] = vs
        if len(vs) < 2 or not w.get("map_ok"):
            w["det"] = 0 if len(vs) == 1 else None
            continue
        qterm = np.array([QW[v["L"]] * 2 * (v["q"] - 0.5) if v.get("q") is not None else 0.0 for v in vs])
        S = W["I"] * z([v["I"] for v in vs]) + W["F"] * z([v["F"] for v in vs]) + W["D"] * z([v["D"] for v in vs]) + qterm
        order = np.argsort(-S)
        w["det"] = int(vs[order[0]]["k"])
        w["margin"] = float(S[order[0]] - S[order[1]])
        w["S"] = [round(float(s), 2) for s in S]

# ---------------- интонация, паузы, темп ----------------
def intonation(words, vowels, P):
    _, pt, f0, _, _ = P
    res = []
    for s in sorted({w["sent"] for w in words}):
        ws = [w for w in words if w["sent"] == s and "t0" in w]
        if not ws:
            continue
        allf = [v["F"] for w in ws for v in w.get("vf", []) if not np.isnan(v.get("F", np.nan))]
        strs = []
        for w in ws:
            k = w["exp"] if w["exp"] is not None else w.get("det")
            vv = [v for v in w.get("vf", []) if v["k"] == k]
            if vv and not np.isnan(vv[0].get("F", np.nan)):
                strs.append((w, vv[0]["F"]))
        if len(allf) < 3 or not strs:
            continue
        med = float(np.median(allf))
        last_w, last_f = strs[-1]
        peak_w, peak_f = max(strs, key=lambda x: x[1])
        end = ws[-1]["t1"]
        fm = (pt >= end - 0.2) & (pt <= end) & (f0 > 0)
        endf = float(np.median([st(x) for x in f0[fm]])) if fm.sum() else np.nan
        p = ws[-1]["punct"]
        typ = "?" if "?" in p else ("!" if "!" in p else ".")
        PREP = {"в", "во", "на", "о", "об", "обо", "с", "со", "к", "ко", "по", "за", "из", "от", "до", "у", "для", "про"}
        first = [w["w"] for w in ws[:2]]
        wh = bool(first) and (first[0] in WH or (first[0] in PREP and len(first) > 1 and first[1] in WH))
        names = [w["w"] for w in ws]
        if "ли" in names and names.index("ли") > 0:
            fw = ws[names.index("ли") - 1]; wh = False
        else:
            cont = [x for x, _ in strs if len(x["vows"]) > 1] or [strs[-1][0]]
            fw = cont[-1]
        ff = next((f for x, f in strs if x is fw), None)
        before = [f for x, f in strs if x is not fw and ws.index(x) < ws.index(fw)]
        d = dict(text=" ".join(w["w"] for w in ws) + p, type=typ, final=round(last_f - med, 1),
                 peak=round(peak_f - med, 1), peak_word=peak_w["w"], end=round(endf - med, 1) if not np.isnan(endf) else None)
        if typ == "." or (typ == "?" and wh):
            d["ok"] = d["final"] <= -0.5
            d["note"] = "конец фразы понижается — звучит законченно" if d["ok"] else "конец фразы не понижается — звучит незаконченно / как перечисление"
        elif typ == "?":
            rise = (ff - med) if ff is not None else -99
            over = (ff - max(before)) if (ff is not None and before) else rise
            d["focus"] = fw["w"]; d["rise"] = round(rise, 1)
            d["ok"] = rise >= 2.0 and over >= 0.5
            d["note"] = (f"вопросительный подъём на слове «{fw['w']}» (+{rise:.1f} пт)" if d["ok"]
                         else f"нет вопросительного подъёма на «{fw['w']}» (самое высокое место — «{peak_w['w']}») — звучит как утверждение")
        else:
            d["ok"] = d["peak"] >= 2.0
            d["note"] = f"выделено слово «{peak_w['w']}» (+{d['peak']} пт)" if d["ok"] else "восклицание звучит ровно, без эмоции"
        res.append(d)
    return res

def pauses(words):
    out = []
    for a, b in zip(words, words[1:]):
        if "t1" not in a or "t0" not in b:
            continue
        g = b["t0"] - a["t1"]
        p = a["punct"]
        if re.search(r"[.!?…]", p) and g < 0.2:
            out.append(f"после «{a['w']}{p}» пауза всего {g:.2f} с — фразы слипаются")
        elif re.search(r"[,;:—–]", p) and g < 0.05:
            out.append(f"после «{a['w']}{p}» нет паузы ({g:.2f} с)")
        elif not p and g > 0.35:
            out.append(f"лишняя пауза {g:.2f} с между «{a['w']}» и «{b['w']}»")
    return out

# ---------------- картинка ----------------
def plot(name, audio, words, vowels, P, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    snd, pt, f0, _, _ = P
    spec = snd.to_spectrogram(window_length=0.025, maximum_frequency=5000)
    X, Y = spec.x_grid(), spec.y_grid()
    S = 10 * np.log10(np.maximum(spec.values, 1e-12))
    dur = len(audio) / SR
    fig, ax = plt.subplots(figsize=(max(10, dur * 2.2), 5.2))
    ax.pcolormesh(X, Y, S, vmin=S.max() - 70, cmap="Greys", shading="auto")
    ax.set_ylim(0, 5000); ax.set_ylabel("Гц (спектр)"); ax.set_xlim(0, dur)
    ax2 = ax.twinx()
    fv = np.where(f0 > 0, f0, np.nan)
    ax2.plot(pt, fv, color="tab:blue", lw=2.5)
    ax2.set_ylabel("высота голоса, Гц", color="tab:blue")
    ok_f = fv[~np.isnan(fv)]
    if len(ok_f):
        ax2.set_ylim(max(50, ok_f.min() * 0.8), ok_f.max() * 1.25)
    for v in vowels:
        ax.axvline(v["c"], color="orange", lw=0.6, alpha=0.6)
    for w in words:
        if "t0" not in w:
            continue
        x = (w["t0"] + w["t1"]) / 2
        e, d = w.get("exp"), w.get("det")
        col = "gray" if e is None or d is None or len(w["vows"]) < 2 else ("green" if e == d else "red")
        lab = mark(w["w"], e) if col != "red" else f"{mark(w['w'], e)}\n≠{mark(w['w'], d)}"
        ax.text(x, 4700, lab, ha="center", va="top", fontsize=11, color=col, fontweight="bold",
                bbox=dict(facecolor="white", alpha=0.75, edgecolor="none", pad=1))
        ax.axvspan(w["t0"], w["t1"], ymin=0, ymax=0.03, color=col, alpha=0.8)
    ax.set_xlabel("секунды"); ax.set_title(name)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)

# ---------------- главный цикл ----------------
def analyze(name, apath, tpath):
    text = open(tpath, encoding="utf-8").read().strip()
    voice = open(f"{IN}/{name}.voice", encoding="utf-8").read().strip() if os.path.exists(f"{IN}/{name}.voice") else ""
    audio = load16(apath)
    dur = len(audio) / SR
    words = tokenize(text)
    acc_src = accentize(text, words)
    rep = {"name": name, "voice": voice, "text": text, "dur": round(dur, 2), "accent_source": acc_src}
    # что сказано
    try:
        r = whisper_model().transcribe(apath, language="ru", fp16=False)
        heard = r["text"].strip(); rep["heard"] = heard
        a, b = norm_words(text), norm_words(heard)
        sm = difflib.SequenceMatcher(None, a, b)
        rep["match"] = round(sm.ratio(), 3)
        rep["diff"] = [(" ".join(a[i1:i2]), " ".join(b[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    except Exception:
        log("whisper FAIL", traceback.format_exc())
    try:
        import torch
        with torch.no_grad():
            rep["utmos"] = round(float(utmos_model()(torch.from_numpy(audio)[None], SR)), 2)
    except Exception:
        log("utmos FAIL", traceback.format_exc())
    P = prosody(audio)
    vowels = []
    try:
        vowels = align(audio, words)
        stress(words, vowels, P)
    except Exception:
        log("align FAIL", traceback.format_exc()); rep["align_error"] = True
    fv = P[2][P[2] > 0]
    if len(fv) > 10:
        sts = np.array([st(x) for x in fv])
        rep["f0_range"] = round(float(np.percentile(sts, 95) - np.percentile(sts, 5)), 1)
        rep["f0_median_hz"] = round(float(np.median(fv)))
    rep["intonation"] = intonation(words, vowels, P) if vowels else []
    rep["pauses"] = pauses(words) if vowels else []
    if vowels:
        sp = sum(max(0, w["t1"] - w["t0"]) for w in words if "t0" in w)
        rep["rate"] = round(len(vowels) / sp, 1) if sp > 0 else None
    rep["words"] = [{k: w.get(k) for k in ("w", "exp", "det", "margin", "auto", "map_ok", "ph", "S", "t0", "t1")} for w in words]
    rep["vowels"] = [{k: (round(v[k], 3) if isinstance(v[k], float) else v[k]) for k in v} for v in vowels]
    try:
        plot(name, audio, words, vowels, P, f"{OUT}/{name}.png")
    except Exception:
        log("plot FAIL", traceback.format_exc())
    # отчёт
    L = [f"# {name}", ""]
    if voice: L.append(f"Голос: **{voice}** · длительность {dur:.1f} с")
    if "utmos" in rep: L.append(f"Естественность (UTMOS): **{rep['utmos']} из 5** (живой диктор ≈ 4–4.5)")
    L.append(f"Эталон: {text}")
    if "heard" in rep:
        L.append(f"Распознано: {rep['heard']}")
        L.append("Слова: все совпали" if not rep["diff"] else "Расхождения в словах: " + "; ".join(f"«{x}» → «{y}»" for x, y in rep["diff"]))
    L += ["", "## Ударения", f"(где нужно: {acc_src})", "", "| слово | нужно | у голоса | |", "|---|---|---|---|"]
    bad = 0
    for w in words:
        if len(w["vows"]) < 2:
            continue
        e, d = w.get("exp"), w.get("det")
        if e is None or d is None:
            flag = "?" if d is None else "нет эталона"
        elif e == d:
            flag = "✓" if w.get("margin", 9) >= 0.6 else "✓ (неуверенно)"
        else:
            bad += 1
            flag = "✗ ОШИБКА" if w.get("margin", 9) >= 0.6 else "✗? (неуверенно)"
        L.append(f"| {w['w']} | {mark(w['w'], e)} | {mark(w['w'], d) if d is not None else '—'} | {flag} |")
    rep["stress_errors"] = bad
    L += ["", "## Интонация"]
    for s in rep["intonation"]:
        L.append(f"- {'✓' if s['ok'] else '✗'} «{s['text']}» — {s['note']}")
    if "f0_range" in rep:
        r_ = rep["f0_range"]
        L.append(f"- Диапазон голоса {r_} полутонов ({'живо' if r_ >= 7 else 'нормально' if r_ >= 4.5 else 'монотонно, как робот'}), средняя высота {rep['f0_median_hz']} Гц")
    L += ["", "## Паузы и темп"]
    L += [f"- {p}" for p in rep["pauses"]] or ["- паузы на своих местах"]
    if rep.get("rate"):
        L.append(f"- Темп {rep['rate']} слога/с ({'быстро' if rep['rate'] > 6.5 else 'медленно' if rep['rate'] < 4 else 'нормально'})")
    L += ["", f"![график]({name}.png)", "", "_Синяя линия — высота голоса. Над словами: заглавная буква — где ударение должно быть; красным — где голос его поставил не туда._"]
    open(f"{OUT}/{name}.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(rep, open(f"{OUT}/{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    return rep

def main():
    items = []
    for t in sorted(glob.glob(f"{IN}/*.txt")):
        name = os.path.basename(t)[:-4]
        aud = [p for p in glob.glob(f"{IN}/{name}.*") if p.split(".")[-1].lower() in ("wav", "mp3", "m4a", "ogg", "flac", "aac", "mp4")]
        if not aud:
            continue
        h = hashlib.md5(open(aud[0], "rb").read() + open(t, "rb").read()).hexdigest()
        jp = f"{OUT}/{name}.json"
        if not FORCE and os.path.exists(jp):
            try:
                if json.load(open(jp, encoding="utf-8")).get("hash") == h:
                    continue
            except Exception:
                pass
        items.append((name, aud[0], t, h))
    log("к проверке:", [i[0] for i in items])
    for name, a, t, h in items:
        try:
            rep = analyze(name, a, t)
            rep["hash"] = h
            json.dump(rep, open(f"{OUT}/{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
            log("готово", name)
        except Exception:
            log("FAIL", name, traceback.format_exc())
    rows = ["| файл | голос | UTMOS | слова | ошибки ударений | интонация |", "|---|---|---|---|---|---|"]
    for jp in sorted(glob.glob(f"{OUT}/*.json")):
        try:
            r = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        it = r.get("intonation", [])
        rows.append(f"| {r['name']} | {r.get('voice', '')} | {r.get('utmos', '—')} | {r.get('match', '—')} | {r.get('stress_errors', '—')} | {sum(1 for s in it if s['ok'])}/{len(it)} |")
    open(f"{OUT}/summary.md", "w", encoding="utf-8").write("\n".join(rows) + "\n")

if __name__ == "__main__":
    main()
