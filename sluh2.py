#!/usr/bin/env python3
"""Слух 2 (25.11.2026). Михаил: «ищи вариант, чтобы ты слышал их… переведи звук в цифру… не попадаешь ты в их звук».

Прежние мерки (похожесть resemblyzer 0,80–0,86, «ритм 0,97») ни разу не были сверены с тем, как голос отличается САМ ОТ СЕБЯ
и как отличаются ДРУГИЕ голоса, — поэтому «похоже» по цифрам было «не попал» на слух. Здесь каждая мерка калибруется:
  свой разброс — тот же голос на разных фразах (случайные половины);  чужие — все остальные голоса набора.
Кандидат «попал» по мерке, только если отличается от образца не больше, чем образец отличается сам от себя.

Что меряется (то, что слышит человек):
  кто говорит   — три независимых «узнавателя голоса» (ECAPA, WavLM-SV, resemblyzer);
  высота        — медиана, размах, подвижность мелодии, конец фразы;
  размер голоса — форманты ударных гласных (по звукам, после выравнивания по фонемам);
  окраска       — спектр по полосам (яркость, «воздух», наклон), свистящие;
  качество      — шум в голосе (HNR), придыхание (CPPS), дрожание (jitter, shimmer);
  манера        — темп, паузы, чем выделено ударение (длина, высота, громкость), затягивание конца;
  произношение  — уверенность фонемного распознавателя и какие звуки он слышит на месте каждой фонемы;
  тембр звуков  — средний спектр каждого звука (а, о, с, ш…) у образца и у кандидата.
Самопроверка: слепой тест «тот же / другой» (ABX), проверка на подкрученных записях (тон +0,5 пт, форманты +4 % …),
контроль «тот же голос из другой сборки» и сверка с ухом Михаила (все отвергнутые им кандидаты должны выйти «не тот»).

  python sluh2.py feat <часть> <всего>   → sl/part_<часть>.pkl
  python sluh2.py final                   → sluh/itog.md, sluh/sluh.json, sluh/*.png
"""
import glob, json, math, os, pickle, random, re, subprocess, sys, traceback

import numpy as np

SR16, SR22, SRH = 16000, 22050, 44100
OUT, WK = "sluh", "sl"
VOWL = "аеёиоуыэюя"
VCLASS = {"а": "A", "я": "A", "о": "O", "ё": "O", "у": "U", "ю": "U", "и": "I", "ы": "Y", "э": "E", "е": "E"}
VNAME = {"A": "а", "O": "о", "U": "у", "I": "и", "Y": "ы", "E": "э"}
CEIL = [5000, 5500, 6000, 6500]
SMOKE = os.environ.get("SMOKE") == "1"
SYN = ["n4", "g03", "g03f", "manera1", "manera2", "nash3", "xenia", "kseniya", "eugene", "aidar", "baya"]
MODS = {"id": (1.0, 1.0, 1.0), "p+0.5": (2 ** (0.5 / 12), 1.0, 1.0), "p+1": (2 ** (1 / 12), 1.0, 1.0), "f+4": (1.0, 1.04, 1.0),
        "f+8": (1.0, 1.08, 1.0), "t+8": (1.0, 1.0, 1.08), "dark": None}
SAME = {"Барсик", "Рон", "Пик", "Филя", "Топа", "Пуся"}       # один и тот же голос во всех сборках
GROUPS = [  # (название, образец, кандидаты, откуда свой разброс)
    ("Барсик", "Барсик@g24", ["Мурзик@g24", "Васька@g24", "Мурзик@g23", "Рыжик@g23", "Васька@g23", "Тимка@g23"], "Барсик"),
    ("Рон", "Рон@g24", ["Тузик@g24", "Рекс@g24", "Тузик@g23", "Бобик@g23", "Рекс@g23", "Джек@g23"], "Рон"),
    ("Пик", "Пик@g24", ["Пуся@g24", "Пуша@g24"], "Пик"),
    ("№4", "n4@syn", ["g03@syn", "g03f@syn", "manera1@syn", "manera2@syn", "nash3@syn"], "n4@syn"),
]
NOTE = {"Мурзик@g24": "Барсик, свободный 1 (kermen)", "Васька@g24": "Барсик, свободный 2 (zhadyra)", "Тузик@g24": "Рон, свободный 1 (nurgul)",
        "Рекс@g24": "Рон, свободный 2 (aigul)", "Пуся@g24": "Пик, свободный 1 (zara)", "Пуша@g24": "Пик, свободный 2 (zara, выше и быстрее)",
        "g03@syn": "свободный спокойный (g03)", "g03f@syn": "свободный быстрый (g03)", "manera1@syn": "манера 1", "manera2@syn": "манера 2",
        "nash3@syn": "голос бота сейчас (nash3)"}


def log(*a):
    print(*a, flush=True)


def clean(t):
    return t.replace("́", "").replace("̀", "").replace("+", "")


def ident(voice):
    n = voice.split("@")[0]
    return n if n in SAME else voice


# ---------------------------------------------------------------- набор записей
def phrases24():
    import svoy2
    ph = [svoy2.PHRASES[k][0] for k in (0, 1, 2, 3, 4, 5, 6, 8, 9, 10)]
    try:
        B = json.load(open("bank/bank.json", encoding="utf-8"))
        ls = [l for s in B["scripts"] for l in s["lines"] if not re.search(r"\d", l) and 40 < len(l) < 95 and "—" not in l and ":" not in l]
        ph += ls[:70:5][:14]
    except Exception:
        traceback.print_exc()
    return ph


def manifest():
    M = []
    for b, tag, cap in (("38g", "ser", 60), ("39f", "ser", 60), ("golosa23", "g23", 20), ("golosa24", "g24", 20)):
        p = f"dubz/{b}/dub/lines.json"
        if not os.path.exists(p):
            log("нет сборки", b); continue
        cnt = {}
        for l in json.load(open(p, encoding="utf-8"))["lines"]:
            t = clean(l["text"])
            if l.get("vocal") or len(re.findall(r"[А-Яа-яЁё]+", t)) < 2 or l.get("bdur", 9) < 0.8 or t.startswith("Понравился"):
                continue
            n = l["name"]; cnt[n] = cnt.get(n, 0) + 1
            if cnt[n] > cap:
                continue
            M.append({"id": f"{b}_{l['i']:03d}", "voice": f"{n}@{tag}", "text": t, "path": f"dubz/{b}/dub/lines/{l['i']:03d}.wav",
                      "k": cnt[n] - 1, "src": "dub", "pic": tag == "g24" and cnt[n] - 1 in (2, 4)})
    ph = phrases24()
    for v in SYN:
        for k, t in enumerate(ph):
            M.append({"id": f"syn_{v}_{k:02d}", "voice": f"{v}@syn", "text": t, "syn": v, "k": k, "src": "syn", "pic": k in (0, 6)})
    import svoy_manera
    for s in svoy_manera.pool():
        for k, t in enumerate(ph[:10]):
            M.append({"id": f"cis_{s[3:]}_{k:02d}", "voice": f"cis:{s[3:]}@syn", "text": t, "syn": "cis:" + s, "k": k, "src": "syn", "pic": False})
    base = [m for m in M if m["voice"] == "Барсик@g24"]
    for mod in MODS:
        for m in base:
            M.append({"id": f"mod_{mod}_{m['k']:02d}", "voice": f"Барсик~{mod}@mod", "text": m["text"], "path": m["path"], "mod": mod,
                      "k": m["k"], "src": "mod", "pic": False})
    if SMOKE:
        lim = {"Барсик@g24": 7, "Мурзик@g24": 7, "Рон@g24": 7, "Барсик@ser": 4, "n4@syn": 6, "g03@syn": 6, "eugene@syn": 6, "cis:aigul@syn": 6,
               "cis:oksana@syn": 6, "Барсик~id@mod": 3, "Барсик~p+1@mod": 3, "Барсик~dark@mod": 3, "Барсик~f+8@mod": 3}
        M = [m for m in M if m["k"] < lim.get(m["voice"], 0)]
    return M


# ---------------------------------------------------------------- синтез (№4, свободные смеси, дикторы)
_net = {}


def synth(item, path):
    import gen as g, svoy2, svoy_bars, svoy_kot3 as K3
    v = item["syn"]
    if v in ("n4", "xenia", "kseniya", "eugene", "aidar", "baya"):
        if "ru" not in _net:
            _net["ru"] = svoy2.Net(svoy2.RU); _net["ru_on"] = None
        net = _net["ru"]
        if v == "n4":
            if _net["ru_on"] != "n4":
                net.put(net.build(svoy_bars.W4)); _net["ru_on"] = "n4"
            spk = svoy2.SLOT[svoy2.RU]
        else:
            spk = v
            if v == "baya" and _net["ru_on"] == "n4":       # место baya занято смесью №4 — вернуть нельзя, читаем до смеси
                raise RuntimeError("baya после №4")
        a = net.m.apply_tts(ssml_text=K3.text_for({"model": "ru", "pitch": "medium", "rate": "medium"}, item["text"]), speaker=spk,
                            sample_rate=48000, put_accent=True, put_yo=True)
    else:
        if "cis" not in _net:
            _net["cis"] = svoy2.Net(svoy2.CIS); _net["cis_on"] = None
        net = _net["cis"]
        pitch, rate = "low", "medium"
        if v.startswith("cis:"):
            s = v[4:]; w = {r: {s: 1.0} for r in ("dp", "pp", "spe")}; pitch = "medium"
        elif v in ("g03", "g03f"):
            w = json.load(open("cast7/golos_free.json", encoding="utf-8"))["voices"]["ru_svoy1"]["w"]; rate = "fast" if v == "g03f" else "medium"
        elif v in ("manera1", "manera2"):
            w = json.load(open("cast9/golos_manera.json", encoding="utf-8"))["voices"]["ru_" + v]["w"]
        elif v == "nash3":
            w = {r: {"ru_nash3": 1.0} for r in ("dp", "pp", "spe")}; pitch = "medium"
        else:
            raise RuntimeError("неизвестный голос " + v)
        if _net["cis_on"] != v:
            net.put(net.build(w)); _net["cis_on"] = v
        a = net.m.apply_tts(ssml_text=K3.text_for({"model": "cis", "pitch": pitch, "rate": rate}, item["text"]), speaker=svoy2.SLOT[svoy2.CIS],
                            sample_rate=48000)
    g.save_wav(a.numpy() if hasattr(a, "numpy") else a, path)


def modded(item, path):
    import hero_free, svoy_lib as SL
    if item["mod"] == "dark":
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", item["path"], "-af", "highshelf=f=3000:g=-4", path], check=True)
        return
    x = SL.load(item["path"], SRH)
    P, F, T = MODS[item["mod"]]
    SL.save(hero_free.engine(x, SRH, P, F, T), path, SRH)


# ---------------------------------------------------------------- замеры одной записи
def bounds(a, sr, db=-38):
    hop = int(sr * 0.01); n = len(a) // hop
    if n < 8:
        return 0.0, len(a) / sr
    e = np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    idx = np.where(e > e.max() * 10 ** (db / 20))[0]
    return max(0, idx[0] - 3) * hop / sr, min(n, idx[-1] + 4) * hop / sr


_models = {}


def embeds(a16):
    import torch
    E = {}
    x = torch.tensor(a16)[None]
    try:
        if "ecapa" not in _models:
            try:
                from speechbrain.inference.speaker import EncoderClassifier
            except Exception:
                from speechbrain.pretrained import EncoderClassifier
            _models["ecapa"] = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="models/ecapa",
                                                              run_opts={"device": "cpu"})
        with torch.no_grad():
            e = _models["ecapa"].encode_batch(x).reshape(-1)
        E["ecapa"] = (e / e.norm()).numpy().astype(np.float32)
    except Exception:
        traceback.print_exc()
    try:
        if "wavlm" not in _models:
            from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
            n = "microsoft/wavlm-base-plus-sv"
            _models["wavlm"] = (Wav2Vec2FeatureExtractor.from_pretrained(n), WavLMForXVector.from_pretrained(n).eval())
        fe, m = _models["wavlm"]
        with torch.no_grad():
            e = m(**fe(a16, sampling_rate=SR16, return_tensors="pt")).embeddings[0]
        E["wavlm"] = (e / e.norm()).numpy().astype(np.float32)
    except Exception:
        traceback.print_exc()
    try:
        if "resem" not in _models:
            from resemblyzer import VoiceEncoder
            _models["resem"] = VoiceEncoder("cpu")
        from resemblyzer import preprocess_wav
        e = _models["resem"].embed_utterance(preprocess_wav(a16, source_sr=SR16))
        E["resem"] = (e / (np.linalg.norm(e) + 1e-9)).astype(np.float32)
    except Exception:
        traceback.print_exc()
    return E


RUSSET = set("aɐəeɛiɪɨoɵuʊʉæjpbtdkɡgfvszʃʒɕxmnrlʲːɫ")


def phones(a16, plain):
    """Фонемы с временем: [{p, v, cls, st, wi, t0, t1, sc, post}], слова. Границы — середины между соседними метками выравнивания."""
    import torch, torchaudio.functional as AF, voice_check as vc, svoy
    proc, model = vc.phon_model()
    tok = proc.tokenizer
    vocab = tok.get_vocab(); blank = tok.pad_token_id
    special = {blank, tok.unk_token_id, getattr(tok, "bos_token_id", None), getattr(tok, "eos_token_id", None)}
    vowel_ids = [i for t, i in vocab.items() if t and t[0] in vc.IPAV and i not in special]
    if "pcols" not in _models:
        _models["pcols"] = sorted(i for t, i in vocab.items() if t and i not in special and all(ch in RUSSET for ch in t))
    pcols = _models["pcols"]
    with torch.no_grad():
        x = proc(a16, sampling_rate=SR16, return_tensors="pt").input_values
        lp = torch.log_softmax(model(x).logits[0], -1)
    T = lp.shape[0]; fps = T / (len(a16) / SR16)
    words = vc.tokenize(plain)
    vc.accentize(plain, words)
    for w in words:
        if len(w["vows"]) == 1:
            w["exp"] = None if w["w"] in svoy.CLIT else 0
    phs = vc.phonemize_words(words)
    cols, tgt, meta, colmap = [blank], [], [], {}
    for wi, (w, pl) in enumerate(zip(words, phs)):
        ok = sum(1 for p in pl if p[0] in vc.IPAV) == len(w["vows"])
        vk = 0
        for p in pl:
            if p[0] in vc.IPAV:
                key = "V"
                if not ok:
                    st = None
                elif w["exp"] is None:
                    st = False if len(w["vows"]) == 1 else None
                else:
                    st = w["exp"] == vk
                meta.append({"wi": wi, "p": p, "v": 1, "cls": VCLASS.get(w["vows"][vk]) if ok else None, "st": st, "last": ok and vk == len(w["vows"]) - 1})
                vk += 1
            else:
                cand = [p, p.replace("ʲ", ""), p.replace("ː", ""), p[0]]
                key = next((c for c in cand if c in vocab and vocab[c] not in special), None)
                if key is None:
                    continue
                meta.append({"wi": wi, "p": key, "v": 0})
            if key not in colmap:
                colmap[key] = len(cols); cols.append(key)
            tgt.append(colmap[key])
    if not tgt or T < len(tgt) + 2:
        return [], words
    em = torch.empty(T, len(cols))
    em[:, 0] = lp[:, blank]
    for key, c in colmap.items():
        em[:, c] = torch.logsumexp(lp[:, vowel_ids], -1) if key == "V" else lp[:, vocab[key]]
    al, sc = AF.forced_align(em[None], torch.tensor([tgt], dtype=torch.int32), blank=0)
    spans = list(AF.merge_tokens(al[0], sc[0].exp()))
    P = lp.exp()[:, pcols]
    out = []
    for sp, m in zip(spans, meta):
        d = dict(m, a0=sp.start / fps, a1=sp.end / fps, sc=float(sp.score))
        pv = P[sp.start:max(sp.end, sp.start + 1)].mean(0).numpy()
        d["post"] = (pv / (pv.sum() + 1e-9)).astype(np.float32)
        out.append(d)
    for i, d in enumerate(out):            # границы звука: до середины промежутка с соседом, но не дальше 0,08 с от метки
        if i == 0:
            d["t0"] = max(0.0, d["a0"] - 0.03)
        else:
            gap = d["a0"] - out[i - 1]["a1"]
            d["t0"] = d["a0"] - min(gap / 2, 0.08)
        if i == len(out) - 1:
            d["t1"] = d["a1"] + 0.04
        else:
            gap = out[i + 1]["a0"] - d["a1"]
            d["t1"] = d["a1"] + min(gap / 2, 0.08)
    return out, words


def analyze(item, wav):
    import parselmouth, torch, torchaudio
    from parselmouth.praat import call
    import svoy_lib as SL
    aH = SL.load(wav, SRH)
    b0, b1 = bounds(aH, SRH)
    aH = aH[int(b0 * SRH):int(b1 * SRH)]
    tmp = f"tmp/_u{os.getpid()}.wav"
    SL.save(aH / (np.abs(aH).max() + 1e-9) * 0.9, tmp, SRH)
    aH = SL.load(tmp, SRH); a16 = SL.load(tmp, SR16); a22 = SL.load(tmp, SR22)
    dur = len(a16) / SR16
    U = {"id": item["id"], "voice": item["voice"], "text": item["text"], "k": item["k"], "src": item["src"], "dur": dur}
    S = {}
    # ---- высота (два прохода: сначала широко, потом вокруг найденной медианы)
    snd = parselmouth.Sound(a16.astype(np.float64), SR16)
    p0 = snd.to_pitch_ac(time_step=0.01, pitch_floor=60, pitch_ceiling=700).selected_array["frequency"]
    med0 = float(np.median(p0[p0 > 0])) if (p0 > 0).sum() > 5 else 200.0
    lo, hi = max(50.0, med0 / 1.9), min(900.0, med0 * 2.2)
    pit = snd.to_pitch_ac(time_step=0.005, pitch_floor=lo, pitch_ceiling=hi)
    pt, f0 = pit.xs(), pit.selected_array["frequency"]
    vo = f0 > 0
    if vo.sum() < 10:
        raise RuntimeError("нет голоса")
    st = 12 * np.log2(f0[vo] / 100.0)
    med = float(np.median(f0[vo])); medst = float(np.median(st))
    S["f0"] = medst; S["f0_hz"] = med
    S["range"] = float(np.percentile(st, 90) - np.percentile(st, 10)); S["f0_sd"] = float(st.std())
    stf = np.where(vo, 12 * np.log2(np.maximum(f0, 1) / 100.0), np.nan)
    d = np.abs(np.diff(stf)) / 0.005
    d = d[np.isfinite(d) & (d < 400)]
    S["mob"] = float(np.mean(d)) if len(d) else np.nan
    tail = st[pt[vo] > pt[vo][-1] - 0.25]
    S["fin"] = float(np.median(tail) - medst) if len(tail) >= 3 else np.nan
    # ---- громкость, паузы, темп
    inten = snd.to_intensity(minimum_pitch=max(60.0, lo), time_step=0.005)
    it, iv = inten.xs(), inten.values[0]
    sp = iv > iv.max() - 30
    S["int_range"] = float(np.percentile(iv[sp], 90) - np.percentile(iv[sp], 10)) if sp.sum() > 5 else np.nan
    ptime, npause, run = 0.0, 0, 0
    i0, i1 = np.where(sp)[0][0], np.where(sp)[0][-1]
    for x in list(~sp[i0:i1 + 1]) + [False]:
        if x:
            run += 1
        else:
            if run * 0.005 >= 0.12:
                ptime += run * 0.005; npause += 1
            run = 0
    syl = sum(c in VOWL for c in item["text"].lower())
    stime = max((i1 - i0 + 1) * 0.005 - ptime, 0.2)
    S["rate"] = syl / stime; S["pause_share"] = 100 * ptime / max((i1 - i0 + 1) * 0.005, 0.2); S["n_pause"] = npause
    # ---- качество голоса
    try:
        hr = snd.to_harmonicity_cc(time_step=0.01, minimum_pitch=lo).values[0]
        S["hnr"] = float(np.mean(hr[hr > -100]))
    except Exception:
        S["hnr"] = np.nan
    try:
        pp = call(snd, "To PointProcess (periodic, cc)", lo, hi)
        S["jitter"] = 100 * call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        S["shimmer"] = 100 * call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    except Exception:
        S["jitter"] = S["shimmer"] = np.nan
    try:
        pc = call(snd, "To PowerCepstrogram", 60, 0.002, 5000, 50)
        S["cpps"] = float(call(pc, "Get CPPS", "no", 0.02, 0.0005, lo, hi, 0.05, "Parabolic", 0.001, 0.05, "Exponential decay", "Robust slow"))
    except Exception as e:
        if "cpps_err" not in _models:
            _models["cpps_err"] = 1; log("CPPS не посчитан:", repr(e)[:200])
        S["cpps"] = np.nan
    # ---- окраска: долгий спектр по речевым кадрам (44,1 кГц)
    n, hop = 2048, 512
    k = max(1, (len(aH) - n) // hop)
    fr = np.stack([aH[i * hop:i * hop + n] for i in range(k)]) * np.hanning(n)
    pw = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    en = pw.sum(1); pw = pw[en > en.max() * 10 ** (-3.5)].mean(0)
    fq = np.fft.rfftfreq(n, 1 / SRH)
    tot = pw[(fq > 60)].sum() + 1e-20
    band = lambda a, b: 10 * np.log10(pw[(fq >= a) & (fq < b)].sum() / tot + 1e-12)
    S["bright"] = float(band(2000, 5000) - band(100, 1000)); S["air"] = float(band(8000, 16000) - band(100, 8000))
    S["low"] = float(band(60, 400) - band(400, 4000))
    edges = np.geomspace(80, 20000, 41)
    curve = np.array([10 * np.log10(pw[(fq >= edges[i]) & (fq < edges[i + 1])].mean() / (tot / len(fq)) + 1e-12) if ((fq >= edges[i]) & (fq < edges[i + 1])).any()
                      else np.nan for i in range(40)], dtype=np.float32)
    U["ltas"] = curve
    cen = np.sqrt(edges[:-1] * edges[1:])
    m = (cen > 300) & (cen < 5000) & np.isfinite(curve)
    S["tilt"] = float(np.polyfit(np.log2(cen[m]), curve[m], 1)[0]) if m.sum() > 4 else np.nan
    top = cen[np.isfinite(curve) & (curve > np.nanmax(curve) - 50)]
    S["top"] = float(top.max() / 1000) if len(top) else np.nan
    # ---- фонемы
    ph, words = phones(a16, item["text"])
    S["gop"] = float(np.mean([p["sc"] for p in ph])) if ph else np.nan
    fm = {c: snd.to_formant_burg(time_step=0.005, max_number_of_formants=5.0, maximum_formant=float(c), window_length=0.025, pre_emphasis_from=50.0)
          for c in CEIL}
    mel = torchaudio.transforms.MelSpectrogram(sample_rate=SR22, n_fft=1024, win_length=551, hop_length=220, n_mels=64, f_min=60, f_max=11000, power=2.0)
    Mm = 10 * np.log10(mel(torch.tensor(a22)[None])[0].numpy().T + 1e-10)          # кадры × 64
    me = Mm.mean(1); Mm = Mm - Mm[me > me.max() - 35].mean()
    mfps = SR22 / 220
    vow, sib, pcs, mels, pps, gops = [], [], [], {}, {}, {}

    def f0at(a, b):
        ff = f0[(pt >= a) & (pt <= b) & vo]
        return float(np.median(12 * np.log2(ff / 100.0))) if len(ff) >= 2 else None

    def intat(a, b):
        x = iv[(it >= a) & (it <= b)]
        return float(x.mean()) if len(x) else None

    for p in ph:
        t0, t1 = p["t0"], min(p["t1"], dur)
        dd = max(t1 - t0, 0.01); c = (t0 + t1) / 2
        key = None
        if p["v"]:
            if p["cls"] and p["st"] is not None:
                key = "V" + p["cls"] + ("1" if p["st"] else "0")
            F = None
            if p["st"] and dd >= 0.04:
                F = []
                for cl in CEIL:
                    row = []
                    for kf in (1, 2, 3):
                        xs = [fm[cl].get_value_at_time(kf, c + o * dd) for o in (-0.15, -0.07, 0, 0.07, 0.15)]
                        xs = [x for x in xs if x == x]
                        row.append(float(np.median(xs)) if xs else np.nan)
                    F.append(row)
            vow.append({"cls": p["cls"], "st": p["st"], "d": dd, "f0": f0at(t0, t1), "i": intat(t0, t1), "F": F, "wi": p["wi"], "last": p.get("last")})
        else:
            key = "C" + p["p"]
            if p["p"][0] in "sʃɕzʒ":
                seg = aH[int(t0 * SRH):int(t1 * SRH)]
                if len(seg) > 256:
                    sp_ = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; fx = np.fft.rfftfreq(len(seg), 1 / SRH)
                    mm = (fx > 1000) & (fx < 16000)
                    sib.append([p["p"], dd, float((sp_[mm] * fx[mm]).sum() / (sp_[mm].sum() + 1e-20))])
        pcs.append([p["p"], dd, f0at(t0, t1), p["wi"]])
        if key:
            a, b = int((t0 + 0.2 * dd) * mfps), max(int((t0 + 0.8 * dd) * mfps), int((t0 + 0.2 * dd) * mfps) + 1)
            seg = Mm[a:b]
            if len(seg):
                s0 = mels.setdefault(key, [np.zeros(64, np.float32), 0]); s0[0] += seg.mean(0); s0[1] += 1
            s1 = pps.setdefault(key, [np.zeros(len(p["post"]), np.float32), 0]); s1[0] += p["post"]; s1[1] += 1
            s2 = gops.setdefault(key, [0.0, 0]); s2[0] += p["sc"]; s2[1] += 1
    # чем выделено ударение: в словах, где есть и ударный, и безударные
    sw = []
    for wi in set(v["wi"] for v in vow):
        a = [v for v in vow if v["wi"] == wi and v["st"] is True]; b = [v for v in vow if v["wi"] == wi and v["st"] is False]
        if len(a) == 1 and b:
            sw.append([a[0]["d"] / np.mean([x["d"] for x in b]),
                       (a[0]["f0"] - np.mean([x["f0"] for x in b if x["f0"] is not None])) if a[0]["f0"] is not None and any(x["f0"] is not None for x in b) else None,
                       (a[0]["i"] - np.mean([x["i"] for x in b if x["i"] is not None])) if a[0]["i"] is not None and any(x["i"] is not None for x in b) else None])
    vd = [v["d"] for v in vow]
    S["finlen"] = float(vow[-1]["d"] / np.median(vd)) if len(vd) >= 3 else np.nan
    U.update(sc={k: (float(v) if v is not None else np.nan) for k, v in S.items()}, vow=vow, sw=sw, pc=pcs, sib=sib, mel=mels, pp=pps, gopc=gops,
             emb=embeds(a16))
    if item.get("pic"):
        U["pic"] = {"mel": Mm[:, :56].astype(np.float16), "f0": np.where(vo, f0, 0).astype(np.float32), "pt": pt.astype(np.float32), "fps": mfps}
    return U


def feat(part, n):
    import svoy_omo, svoy2
    for d in (WK, "tmp", "models"):
        os.makedirs(d, exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    M = manifest()
    mine = [m for i, m in enumerate(M) if i % n == part]
    # baya читаем раньше №4 (смесь №4 занимает её место в модели)
    mine.sort(key=lambda m: (0 if m.get("syn") == "baya" else 1, m.get("syn") or "", m["id"]))
    log("записей всего", len(M), "моих", len(mine))
    out = []
    for j, m in enumerate(mine):
        try:
            wav = m.get("path")
            if m["src"] == "syn":
                wav = f"tmp/{m['id']}.wav"; synth(m, wav)
            elif m["src"] == "mod":
                wav = f"tmp/{m['id']}.wav"; modded(m, wav)
            out.append(analyze(m, wav))
            if j % 10 == 0:
                s = out[-1]["sc"]
                log(j, "/", len(mine), m["id"], m["voice"], f"{s['f0_hz']:.0f} Гц", f"темп {s['rate']:.1f}", f"gop {s['gop']:.2f}", list(out[-1]["emb"]))
        except Exception as e:
            log("ОШИБКА", m["id"], repr(e)); traceback.print_exc()
    pickle.dump(out, open(f"{WK}/part_{part}.pkl", "wb"))
    log("готово", part, len(out))


# ================================================================ итог: калибровка, самопроверка, отчёт
SC = [  # (ключ, как назвать, единица, «больше — это…», «меньше — это…»)
    ("f0", "высота голоса", "пт", "выше", "ниже"),
    ("range", "размах мелодии", "пт", "мелодия шире (живее)", "мелодия у́же (ровнее)"),
    ("mob", "подвижность мелодии", "пт/с", "мелодия подвижнее", "мелодия спокойнее"),
    ("fin", "конец фразы", "пт", "конец фразы выше", "конец фразы ниже"),
    ("rate", "темп речи", "слог/с", "быстрее", "медленнее"),
    ("pause_share", "доля пауз", "%", "пауз больше", "пауз меньше"),
    ("int_range", "перепады громкости", "дБ", "громкость гуляет сильнее", "громкость ровнее"),
    ("hnr", "чистота голоса (HNR)", "дБ", "чище, звонче", "больше шума, сипловатее"),
    ("cpps", "плотность голоса (CPPS)", "дБ", "плотнее", "с придыханием"),
    ("jitter", "дрожание высоты", "%", "высота дрожит сильнее", "высота ровнее"),
    ("shimmer", "дрожание громкости", "%", "громкость дрожит сильнее", "громкость ровнее"),
    ("bright", "яркость (2–5 кГц)", "дБ", "ярче, резче", "глуше, мягче"),
    ("air", "«воздух» (8–16 кГц)", "дБ", "больше верхов", "меньше верхов"),
    ("low", "низ (до 400 Гц)", "дБ", "больше низа, гуще", "меньше низа, тоньше"),
    ("tilt", "наклон спектра", "дБ/окт", "спектр ровнее (звонче)", "спектр круче падает (мягче)"),
    ("top", "верхняя граница звука", "кГц", "звук шире по частоте", "звук обрезан сверху"),
    ("gop", "чёткость звуков", "", "звуки чётче", "звуки смазаннее"),
    ("finlen", "затягивание конца", "×", "конец фразы тянется сильнее", "конец фразы короче"),
    ("s_dur", "ударение длиной", "×", "ударный слог тянет сильнее", "ударный слог короче"),
    ("s_f0", "ударение высотой", "пт", "ударный слог выше", "ударный слог ниже (ровнее)"),
    ("s_int", "ударение громкостью", "дБ", "ударный слог громче", "ударный слог тише"),
    ("sib", "свистящие и шипящие", "Гц", "с, ш острее", "с, ш глуше"),
    ("fscale", "размер голоса (форманты)", "%", "голос «мельче» (форманты выше)", "голос «крупнее» (форманты ниже)"),
]
# меньше этого отличие не считаем слышным, даже если сам образец на своих фразах отличается ещё меньше
MINFL = {"f0": .5, "range": 1.0, "mob": 3.0, "fin": 1.0, "rate": .3, "pause_share": 4.0, "int_range": 1.5, "hnr": 1.5, "cpps": 1.0, "jitter": .3, "shimmer": 1.0,
         "bright": 2.0, "air": 3.0, "low": 1.5, "tilt": .8, "top": 1.5, "gop": .04, "finlen": .25, "s_dur": .2, "s_f0": .8, "s_int": 1.5, "sib": 500.0, "fscale": 3.0}
VEC = [("ecapa", "узнаватель 1 (ECAPA)", 1), ("wavlm", "узнаватель 2 (WavLM)", 1), ("resem", "узнаватель 3 (resemblyzer)", 1),
       ("mel", "тембр по звукам", -1), ("ppg", "произношение звуков", -1), ("ltas", "общий спектр", -1), ("vsp", "гласные (F1–F2)", -1)]


def nanmed(x):
    x = [v for v in x if v is not None and v == v]
    return float(np.median(x)) if x else float("nan")


def bark(f):
    return 26.81 * f / (1960 + f) - 0.53


def profile(utts):
    """Портрет голоса по набору записей."""
    P = {"n": len(utts)}
    for k in ("f0", "range", "mob", "fin", "rate", "pause_share", "int_range", "hnr", "cpps", "jitter", "shimmer", "bright", "air", "low", "tilt", "top",
              "gop", "finlen", "f0_hz"):
        P[k] = nanmed([u["sc"].get(k) for u in utts])
    sw = [s for u in utts for s in u["sw"]]
    P["s_dur"] = nanmed([s[0] for s in sw]); P["s_f0"] = nanmed([s[1] for s in sw]); P["s_int"] = nanmed([s[2] for s in sw])
    P["sib"] = nanmed([s[2] for u in utts for s in u["sib"]])
    ci = min(range(4), key=lambda i: abs(CEIL[i] - (5000 if P["f0_hz"] < 140 else 5500 if P["f0_hz"] < 250 else 6000 if P["f0_hz"] < 330 else 6500)))
    P["ceil_i"] = ci
    F = {}
    for u in utts:
        for v in u["vow"]:
            if v["F"] is not None and v["cls"]:
                F.setdefault(v["cls"], []).append(v["F"])
    P["F"] = {c: np.nanmedian(np.array(x, dtype=float), axis=0) for c, x in F.items() if len(x) >= 2}      # класс → 4 потолка × 3 форманты
    P["Fn"] = {c: len(x) for c, x in F.items()}
    for name in ("ecapa", "wavlm", "resem"):
        E = [u["emb"][name] for u in utts if name in u["emb"]]
        if E:
            m = np.mean(E, 0); P["e_" + name] = m / (np.linalg.norm(m) + 1e-9)
    for fld in ("mel", "pp"):
        acc = {}
        for u in utts:
            for k, (s, n) in u[fld].items():
                a = acc.setdefault(k, [np.zeros_like(s, dtype=np.float64), 0]); a[0] += s; a[1] += n
        P[fld] = {k: (s / n, n) for k, (s, n) in acc.items()}
    L = np.array([u["ltas"] for u in utts], dtype=float)
    P["ltas"] = np.nanmean(L, 0)
    return P


def _mel_centers():
    m = lambda f: 2595 * np.log10(1 + f / 700.0)
    pts = np.linspace(m(60), m(11000), 66)
    return 700 * (10 ** (pts[1:-1] / 2595) - 1)


MC = _mel_centers()
LG = np.log(np.geomspace(600, 7500, 140))
SHIFTS = np.arange(-0.25, 0.2501, 0.005)


def warp(A, B):
    """Во сколько раз огибающая гласных B растянута по частоте относительно A (в %, + — форманты B выше, голос «мельче»).
    Огибающие ударных гласных на логарифмической оси частот, без наклона; ищем сдвиг с лучшим совпадением по всем гласным."""
    acc, tot = np.zeros(len(SHIFTS)), 0
    lmc = np.log(MC)

    def detr(v):
        return v - np.polyval(np.polyfit(LG, v, 1), LG)

    for k, (va, na) in A["mel"].items():
        if not k.startswith("V") or k not in B["mel"]:
            continue
        vb, nb = B["mel"][k]
        if na < 2 or nb < 2:
            continue
        x = detr(np.interp(LG, lmc, va))
        nx = np.linalg.norm(x) + 1e-9
        w = min(na, nb)
        for j, sft in enumerate(SHIFTS):
            y = detr(np.interp(LG + sft, lmc, vb))
            acc[j] += w * float(x @ y) / (nx * (np.linalg.norm(y) + 1e-9))
        tot += w
    j = int(np.argmax(acc))
    if not tot or j in (0, len(SHIFTS) - 1):          # упёрлось в край поиска — огибающие слишком разные, сдвигом не описать
        return float("nan")
    return 100 * (math.exp(float(SHIFTS[j])) - 1)


def bands(A, B):
    """Спектр по полосам: кандидат минус образец, дБ (общая громкость убрана) — готовая подсказка для эквалайзера."""
    edges = np.geomspace(80, 20000, 41); cen = np.sqrt(edges[:-1] * edges[1:])
    d = B["ltas"] - A["ltas"]
    ok = np.isfinite(d) & (cen > 100) & (cen < 16000)
    d = d - np.mean(d[ok & (cen > 200) & (cen < 4000)])
    out = {}
    for name, a, b in (("0,1–0,3", 100, 300), ("0,3–0,8", 300, 800), ("0,8–2", 800, 2000), ("2–4", 2000, 4000), ("4–7", 4000, 7000), ("7–11", 7000, 11000),
                       ("11–16", 11000, 16000)):
        m = ok & (cen >= a) & (cen < b)
        out[name] = float(np.mean(d[m])) if m.any() else float("nan")
    return out


def pair(A, B, ci=None):
    """Чем B (кандидат) отличается от A (образец): скаляры — разность B−A; векторы — похожесть или расстояние."""
    D = {}
    for k, *_ in SC:
        if k in A and k in B:
            D[k] = B[k] - A[k]
    ci = A["ceil_i"] if ci is None else ci
    r, v = [], []
    for c in A["F"]:
        if c in B["F"]:
            fa, fb = A["F"][c][ci], B["F"][c][ci]
            for kf in (1, 2):
                if fa[kf] == fa[kf] and fb[kf] == fb[kf] and fa[kf] > 0 and fb[kf] > 0:
                    r.append(math.log(fb[kf] / fa[kf]))
            if all(x == x for x in (fa[0], fa[1], fb[0], fb[1])):
                v.append(math.hypot(bark(fb[0]) - bark(fa[0]), bark(fb[1]) - bark(fa[1])))
    D["fscale_praat"] = 100 * (math.exp(float(np.mean(r))) - 1) if r else float("nan")
    D["fscale"] = warp(A, B)
    D["vsp"] = float(np.mean(v)) if v else float("nan")
    for name in ("ecapa", "wavlm", "resem"):
        D[name] = float(A["e_" + name] @ B["e_" + name]) if ("e_" + name in A and "e_" + name in B) else float("nan")
    m, w = [], []
    for k, (va, na) in A["mel"].items():
        if k in B["mel"] and na >= 2 and B["mel"][k][1] >= 2:
            dv = B["mel"][k][0] - va
            dv = dv - dv.mean()                                  # форма спектра, без общей громкости звука
            m.append(float(np.sqrt((dv ** 2).mean()))); w.append(min(na, B["mel"][k][1]))
    D["mel"] = float(np.average(m, weights=w)) if m else float("nan")
    m, w = [], []
    for k, (va, na) in A["pp"].items():
        if k in B["pp"] and na >= 2 and B["pp"][k][1] >= 2:
            p, q = va / (va.sum() + 1e-9), B["pp"][k][0] / (B["pp"][k][0].sum() + 1e-9)
            mm = 0.5 * (p + q)
            js = 0.5 * np.sum(p * np.log((p + 1e-9) / (mm + 1e-9))) + 0.5 * np.sum(q * np.log((q + 1e-9) / (mm + 1e-9)))
            m.append(float(js)); w.append(min(na, B["pp"][k][1]))
    D["ppg"] = float(np.average(m, weights=w)) if m else float("nan")
    d = B["ltas"] - A["ltas"]; ok = np.isfinite(d)
    ok[:2] = False
    D["ltas"] = float(np.sqrt(np.mean((d[ok] - d[ok].mean()) ** 2))) if ok.sum() > 5 else float("nan")
    return D


def contour(ua, ub):
    """Одна и та же фраза двумя голосами: совпадение мелодии и ритма по звукам (−1…1)."""
    pa, pb = ua["pc"], ub["pc"]
    if len(pa) != len(pb) or len(pa) < 6:
        return None, None
    fa = [(x[2], y[2]) for x, y in zip(pa, pb) if x[2] is not None and y[2] is not None]
    mel = None
    if len(fa) >= 6:
        x, y = np.array(fa).T
        x, y = x - np.median(x), y - np.median(y)
        if x.std() > 1e-6 and y.std() > 1e-6:
            mel = float(np.corrcoef(x, y)[0, 1])
    # ритм: длины звуков, из которых убрана средняя длина этого звука по всем голосам, нельзя — берём длины слов в долях фразы
    wa, wb = {}, {}
    for x, y in zip(pa, pb):
        wa[x[3]] = wa.get(x[3], 0) + x[1]; wb[y[3]] = wb.get(y[3], 0) + y[1]
    ks = sorted(wa)
    da = np.array([wa[k] for k in ks]); db = np.array([wb[k] for k in ks])
    rh = None
    if len(ks) >= 4:
        la, lb = np.log(da / da.sum()), np.log(db / db.sum())
        rh = float(np.mean(np.abs(la - lb)))                    # средняя разница долей слова (логарифм): 0 — ритм тот же
    return mel, rh


def subsets(utts, n, rnd):
    idx = list(range(len(utts))); rnd.shuffle(idx)
    return [utts[i] for i in idx[:n]], [utts[i] for i in idx[n:2 * n]]


def final():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(OUT, exist_ok=True)
    U = []
    for f in sorted(glob.glob(f"{WK}/part_*.pkl")):
        U += pickle.load(open(f, "rb"))
    log("записей", len(U))
    byv, byi = {}, {}
    for u in U:
        byv.setdefault(u["voice"], []).append(u)
        if u["src"] != "mod":
            byi.setdefault(ident(u["voice"]), []).append(u)
    for v in byv:
        byv[v].sort(key=lambda u: u["k"])
    rnd = random.Random(7)
    PR = {v: profile(us) for v, us in byv.items()}
    PI = {i: profile(us) for i, us in byi.items()}
    keys = [k for k, *_ in SC] + [k for k, *_ in VEC]
    md = ["# Слух 2 — проверка слуха и разбор голосов (25.11.2026)", "",
          "Каждая мерка сверена с тем, как образец отличается сам от себя на разных фразах («свой разброс», 95 % случаев). "
          "«×» — во сколько раз отличие кандидата больше своего разброса: до 1 — как тот же голос, 1–2 — заметно, больше 2 — сильно.", ""]
    RES = {"voices": {v: {k: PR[v].get(k) for k in ("n", "f0_hz", "f0", "range", "mob", "fin", "rate", "pause_share", "int_range", "hnr", "cpps", "jitter",
                                                    "shimmer", "bright", "air", "low", "tilt", "top", "gop", "finlen", "s_dur", "s_f0", "s_int", "sib")} for v in PR}}

    # ---------- 1. слепая проверка: тот же голос или другой (ABX)
    ids = [i for i, us in byi.items() if len(us) >= 6]
    fam = ["ecapa", "wavlm", "resem", "mel", "ppg", "ltas", "скаляры", "вместе"]
    sig = {}
    for k, *_ in SC:
        x = [PI[i].get(k) for i in ids if PI[i].get(k) is not None and PI[i].get(k) == PI[i].get(k)]
        sig[k] = float(np.std(x)) if len(x) > 3 and np.std(x) > 0 else 1.0
    SCAL = ["f0", "range", "mob", "rate", "pause_share", "int_range", "hnr", "cpps", "jitter", "shimmer", "bright", "air", "low", "tilt", "gop", "s_dur", "s_f0", "s_int", "sib"]

    def dist(D):
        """Расстояния по семействам из результата pair()."""
        z = [abs(D[k]) / sig[k] for k in SCAL if k in D and D[k] == D[k]]
        fs = D.get("fscale")
        if fs == fs:
            z.append(abs(fs) / 4.0)
        return {"ecapa": 1 - D["ecapa"], "wavlm": 1 - D["wavlm"], "resem": 1 - D["resem"], "mel": D["mel"], "ppg": D["ppg"], "ltas": D["ltas"],
                "скаляры": float(np.sqrt(np.mean(np.square(z)))) if z else float("nan")}

    # масштаб каждого семейства — по случайным парам разных голосов
    scale = {f: [] for f in fam[:-1]}
    for _ in range(120 if not SMOKE else 10):
        a, b = rnd.sample(ids, 2) if len(ids) >= 2 else (ids[0], ids[0])
        d = dist(pair(profile(subsets(byi[a], 3, rnd)[0]), profile(subsets(byi[b], 3, rnd)[0])))
        for f in scale:
            if d[f] == d[f]:
                scale[f].append(d[f])
    scale = {f: (float(np.median(v)) if v else 1.0) for f, v in scale.items()}

    def together(d):
        x = [d[f] / scale[f] for f in scale if f != "ppg" and d[f] == d[f] and scale[f] > 0]
        return float(np.mean(x)) if x else float("nan")

    f0i = {i: PI[i]["f0"] for i in ids}
    ok = {f: [0, 0] for f in fam}; okh = {f: [0, 0] for f in fam}
    NT = 500 if not SMOKE else 12
    for t in range(NT):
        v = rnd.choice(ids)
        hard = t % 2 == 1
        others = [i for i in ids if i != v]
        if not others:
            break
        if hard:
            others = sorted(others, key=lambda i: abs(f0i[i] - f0i[v]))[:3]
        u = rnd.choice(others)
        A, X = subsets(byi[v], 3, rnd); B = subsets(byi[u], 3, rnd)[0]
        pa, px, pb = profile(A), profile(X), profile(B)
        dA, dB = dist(pair(pa, px)), dist(pair(pb, px, ci=pa["ceil_i"]))
        dA["вместе"], dB["вместе"] = together(dA), together(dB)
        for f in fam:
            if dA[f] == dA[f] and dB[f] == dB[f]:
                tgt = okh if hard else ok
                tgt[f][1] += 1; tgt[f][0] += dA[f] < dB[f]
    md += ["## 1. Слепая проверка: «тот же голос или другой»", "",
           f"Голосов в наборе: {len(ids)}. В каждой пробе три фразы голоса, три ДРУГИЕ фразы того же голоса и три фразы чужого голоса; "
           "нужно сказать, какая тройка — тот же голос. «Трудные» — чужой голос взят из трёх самых близких по высоте.", "",
           "| чем слушаю | обычные пробы | трудные пробы |", "|---|---|---|"]
    RES["abx"] = {}
    for f in fam:
        a = 100 * ok[f][0] / max(ok[f][1], 1); b = 100 * okh[f][0] / max(okh[f][1], 1)
        nm = dict([(k, n) for k, n, _ in VEC] + [("скаляры", "высота, темп, окраска, качество (вместе)"), ("вместе", "ВСЁ ВМЕСТЕ")])[f]
        md.append(f"| {nm} | {a:.0f} % из {ok[f][1]} | {b:.0f} % из {okh[f][1]} |")
        RES["abx"][f] = [round(a, 1), ok[f][1], round(b, 1), okh[f][1]]
    md.append("")
    bt = {}
    for u in U:
        if u["src"] == "syn":
            bt.setdefault(u["text"], []).append(u)
    cm, cr = [], []
    for t, us in bt.items():
        for _ in range(12):
            if len(us) < 2:
                break
            a, b = rnd.sample(us, 2)
            if ident(a["voice"]) == ident(b["voice"]):
                continue
            m_, r_ = contour(a, b)
            if m_ is not None:
                cm.append(m_)
            if r_ is not None:
                cr.append(r_)
    BASE = {"mel": float(np.mean(cm)) if cm else float("nan"), "mel90": float(np.percentile(cm, 90)) if cm else float("nan"),
            "rh": float(np.mean(cr)) if cr else float("nan"), "rh10": float(np.percentile(cr, 10)) if cr else float("nan")}
    RES["contour_base"] = BASE
    md += [f"Точка отсчёта для «одной фразы двумя голосами»: два РАЗНЫХ диктора на одной фразе совпадают по мелодии в среднем на {BASE['mel']:.2f} "
           f"(лучшие 10 % пар — от {BASE['mel90']:.2f}), по ритму расходятся на {100 * (math.exp(BASE['rh']) - 1):.0f} % длины слова "
           f"(лучшие 10 % — до {100 * (math.exp(BASE['rh10']) - 1):.0f} %). Совпадение на этом уровне — это текст, а не манера.", ""]

    # ---------- 2. слышу ли малые сдвиги (подкрученные записи Барсика)
    if "Барсик~id@mod" in PR:
        base = PR["Барсик~id@mod"]
        md += ["## 2. Слышу ли малые сдвиги", "", "Записи Барсика, в которых изменено только одно (через тот же вокодер, что и «без изменений»).", "",
               "| что изменено | высота, пт | размер голоса, % | темп, % | яркость, дБ | узнаватели (1 / 2 / 3) | тембр по звукам, дБ |", "|---|---|---|---|---|---|---|"]
        exp = {"p+0.5": "тон +0,5 пт", "p+1": "тон +1 пт", "f+4": "форманты +4 %", "f+8": "форманты +8 %", "t+8": "темп +8 %", "dark": "верх −4 дБ"}
        RES["mods"] = {}
        for mod, name in exp.items():
            v = f"Барсик~{mod}@mod"
            if v not in PR:
                continue
            D = pair(base, PR[v])
            md.append(f"| {name} | {D['f0']:+.2f} | {D['fscale']:+.1f} | {100 * D['rate'] / base['rate']:+.1f} | {D['bright']:+.1f} | "
                      f"{D['ecapa']:.2f} / {D['wavlm']:.2f} / {D['resem']:.2f} | {D['mel']:.1f} |")
            RES["mods"][mod] = {k: D[k] for k in ("f0", "fscale", "rate", "bright", "ecapa", "wavlm", "resem", "mel")}
        if "Барсик@g24" in PR:
            D = pair(PR["Барсик@g24"], base)
            md.append(f"| сам вокодер (без изменений против оригинала) | {D['f0']:+.2f} | {D['fscale']:+.1f} | {100 * D['rate'] / PR['Барсик@g24']['rate']:+.1f} | "
                      f"{D['bright']:+.1f} | {D['ecapa']:.2f} / {D['wavlm']:.2f} / {D['resem']:.2f} | {D['mel']:.1f} |")
        md.append("")

    # ---------- 3. разбор по образцам
    def floor(src, n, ci, reps=40):
        """Свой разброс образца: пары непересекающихся наборов по n фраз."""
        us = byi.get(src) or byv.get(src) or []
        n = max(2, min(n, len(us) // 2))
        if len(us) < 4:
            return None, n
        R = {k: [] for k in keys}
        for _ in range(reps if not SMOKE else 4):
            a, b = subsets(us, n, rnd)
            D = pair(profile(a), profile(b), ci=ci)
            for k in keys:
                if k in D and D[k] == D[k]:
                    R[k].append(D[k])
        fl = {}
        for k, *_ in SC:
            fl[k] = max(float(np.percentile(np.abs(R[k]), 95)), MINFL.get(k, 0.0)) if len(R[k]) >= 4 else MINFL.get(k, float("nan"))
        for k, _, sgn in VEC:
            if len(R[k]) >= 4:
                fl[k] = float(np.percentile(R[k], 5 if sgn > 0 else 95)); fl[k + "_m"] = float(np.mean(R[k]))
            else:
                fl[k] = fl[k + "_m"] = float("nan")
        return fl, n

    def others(tv, n, ci):
        """Образец против всех чужих голосов (каждый — n фраз): где лежат «другие дикторы»."""
        R = {k: [] for k, *_ in VEC}
        ti = ident(tv)
        cands = set(c for g in GROUPS for c in g[2])
        for i, us in byi.items():
            if i == ti or len(us) < 3 or any(u["voice"] in cands for u in us):
                continue
            D = pair(PR[tv], profile(us[:max(n, 3)]), ci=ci)
            for k in R:
                if D[k] == D[k]:
                    R[k].append((D[k], i))
        return R

    RES["groups"] = {}
    verdicts = []
    for gname, tv, cands, src in GROUPS:
        if tv not in PR:
            continue
        T = PR[tv]; ci = T["ceil_i"]
        fl, nfl = floor(src, max(T["n"], 5), ci)
        oth = others(tv, T["n"], ci)
        md += [f"## 3. {gname}: образец {tv.split('@')[0]} — {T['f0_hz']:.0f} Гц, размах {T['range']:.1f} пт, темп {T['rate']:.1f} слог/с", ""]
        if fl is None:
            md += ["Свой разброс не посчитан (мало фраз).", ""]; continue
        RES["groups"][gname] = {"target": tv, "floor": fl, "cands": {},
                                "others": {k: sorted([[i, round(v, 4)] for v, i in oth[k]], key=lambda x: -x[1] if k in ("ecapa", "wavlm", "resem") else x[1])
                                           for k in oth},
                                "profile": {k: T.get(k) for k in ("f0", "f0_hz", "range", "mob", "rate", "pause_share", "hnr", "cpps", "bright", "air", "tilt",
                                                                    "s_dur", "s_f0", "s_int", "gop")}}
        line = "Узнаватели голоса — похожесть образца с самим собой (в среднем / худший случай) и с ближайшим чужим голосом: "
        bits = []
        for k, nm, sgn in VEC[:3]:
            o = sorted(oth[k], reverse=True)
            bits.append(f"{nm}: сам с собой {fl[k + '_m']:.2f} / {fl[k]:.2f}, ближайший чужой {o[0][0]:.2f} ({o[0][1].split('@')[0]})" if o else f"{nm}: нет чужих")
        md += [line + "; ".join(bits) + ".", ""]
        # контроль: тот же голос из сериала
        ctrl = [v for v in byv if ident(v) == ident(tv) and v != tv and len(byv[v]) >= 5]
        for cv in ctrl:
            D = pair(T, PR[cv], ci=ci)
            same = sum(1 for k, _, sgn in VEC[:3] if D[k] == D[k] and D[k] >= fl[k])
            md.append(f"Контроль — тот же голос из другой сборки ({cv}): узнаватели {D['ecapa']:.2f} / {D['wavlm']:.2f} / {D['resem']:.2f} → "
                      f"«тот же» по {same} из 3; тембр по звукам {D['mel']:.1f} дБ (свой разброс {fl['mel']:.1f}).")
            RES["groups"][gname].setdefault("control", {})[cv] = {k: D[k] for k in ("ecapa", "wavlm", "resem", "mel", "ppg")}
        md.append("")
        for cv in cands:
            if cv not in PR:
                continue
            C = PR[cv]; D = pair(T, C, ci=ci)
            # одна и та же фраза: мелодия и ритм
            tu = {u["text"]: u for u in byv[tv]}
            cc = [contour(tu[u["text"]], u) for u in byv[cv] if u["text"] in tu]
            mel = nanmed([c[0] for c in cc]); rh = nanmed([c[1] for c in cc])
            D["c_mel"], D["c_rh"] = mel, rh
            rows = []
            for k, nm, unit, more, less in SC:
                if k not in D or D[k] != D[k] or fl.get(k) != fl.get(k) or fl[k] <= 0:
                    continue
                x = abs(D[k]) / fl[k]
                rows.append((x, k, nm, unit, more if D[k] > 0 else less, D[k], fl[k]))
            rows.sort(reverse=True)
            idv = []
            for k, nm, sgn in VEC[:3]:
                if D[k] != D[k]:
                    continue
                o = sorted(x[0] for x in oth[k])
                om = float(np.mean(o)) if o else float("nan")
                pos = (D[k] - om) / (fl[k + "_m"] - om) if (fl[k + "_m"] - om) > 1e-6 else float("nan")
                rank = sum(1 for x in o if x > D[k])
                idv.append((k, nm, D[k], fl[k], pos, rank, len(o)))
            n_same = sum(1 for x in idv if x[2] >= x[3])
            big = [r for r in rows if r[0] >= 2]; mid = [r for r in rows if 1 <= r[0] < 2]
            tim = D["mel"] / fl["mel"] if fl["mel"] == fl["mel"] and fl["mel"] > 0 else float("nan")
            pro = D["ppg"] / fl["ppg"] if fl["ppg"] == fl["ppg"] and fl["ppg"] > 0 else float("nan")
            verdict = "ТОТ ЖЕ ГОЛОС" if (n_same == len(idv) and not big and tim <= 1.2) else ("близко, но слышно отличие" if (n_same >= 2 and len(big) <= 2 and tim <= 2) else "ДРУГОЙ ГОЛОС")
            verdicts.append((gname, cv, verdict, n_same, len(idv), len(big), tim))
            md += [f"### {NOTE.get(cv, cv)} — {verdict}", "",
                   "Узнаватели: " + "; ".join(f"{nm.split(' (')[0]} {v:.2f} (нужно ≥ {f_:.2f}; {100 * pos:.0f} % пути от «чужого» к «тому же»; "
                                               f"ближе него {rank} из {tot} чужих)" for _, nm, v, f_, pos, rank, tot in idv) + ".",
                   f"Тембр по звукам: {D['mel']:.1f} дБ — в {tim:.1f} раза больше своего разброса ({fl['mel']:.1f}). "
                   f"Произношение звуков: в {pro:.1f} раза больше своего разброса. Гласные (F1–F2): {D['vsp']:.2f} барк (свой разброс {fl.get('vsp', float('nan')):.2f}).",
                   (f"Одна и та же фраза: мелодия совпадает на {mel:.2f}, ритм расходится на {100 * (math.exp(rh) - 1):.0f} % длины слова." if mel == mel and rh == rh else ""),
                   "Спектр по полосам (кандидат минус образец, дБ): " + ", ".join(f"{k} кГц {v:+.1f}" for k, v in bands(T, C).items()) + ".",
                   "", "| что слышно | насколько | свой разброс | × |", "|---|---|---|---|"]
            for x, k, nm, unit, word, dv, f_ in rows[:12]:
                md.append(f"| {word} | {dv:+.2f} {unit} | {f_:.2f} | {x:.1f} |")
            md.append("")
            RES["groups"][gname]["cands"][cv] = {"verdict": verdict, "bands": bands(T, C), "D": {k: (None if (isinstance(v, float) and v != v) else v) for k, v in D.items()},
                                                 "rows": [[k, round(dv, 3), round(f_, 3), round(x, 2)] for x, k, nm, unit, word, dv, f_ in rows],
                                                 "ident": [[k, round(v, 3), round(f_, 3), round(pos, 3), rank, tot] for k, nm, v, f_, pos, rank, tot in idv]}
        # кто из всего набора ближе всего к образцу (по «всё вместе»)
        near = []
        for i, us in byi.items():
            if i == ident(tv) or len(us) < 5:
                continue
            d = dist(pair(T, PI[i], ci=ci)); near.append((together(d), i, d))
        near.sort(key=lambda x: (x[0] != x[0], x[0]))
        md += ["Ближайшие к образцу из всего набора (всё вместе; меньше — ближе): " +
               ", ".join(f"{i.split('@')[0]} {v:.2f}" for v, i, _ in near[:8]) + ".", ""]
        RES["groups"][gname]["nearest"] = [[i, round(v, 3)] for v, i, _ in near[:15]]

    # ---------- дикторы модели Барсика: кто из свободных к ним ближе всего (как есть, без движка мультика)
    raw = [tv for tv in ("xenia@syn", "kseniya@syn", "eugene@syn", "baya@syn", "aidar@syn") if tv in PR]
    if raw:
        md += ["## Дикторы модели Барсика и самые близкие к ним свободные дикторы (как есть, одни и те же фразы)", "",
               "Узнаватель 1 (ECAPA); в скобках — узнаватель 3 и тембр по звукам, дБ.", ""]
        RES["raw_near"] = {}
        for tv in raw:
            T = PR[tv]; fl, _ = floor(tv, 10, T["ceil_i"], reps=20)
            rows = []
            for i in byi:
                if i.startswith("cis:") and len(byi[i]) >= 5:
                    D = pair(T, PI[i], ci=T["ceil_i"])
                    rows.append((D["ecapa"], D["resem"], D["wavlm"], D["mel"], i))
            rows.sort(reverse=True)
            md.append(f"- **{tv.split('@')[0]}** ({T['f0_hz']:.0f} Гц; сам с собой {fl['ecapa_m']:.2f}, тембр {fl['mel']:.1f} дБ): " +
                      ", ".join(f"{i[4:].split('@')[0]} {e:.2f} ({r:.2f}; {m:.1f})" for e, r, w, m, i in rows[:6]))
            RES["raw_near"][tv] = [[i, round(e, 3), round(r, 3), round(w, 3), round(m, 2)] for e, r, w, m, i in rows]
        md.append("")

    # ---------- произношение: модель Барсика (v5_ru) против свободной (v5_cis) на одних и тех же фразах
    ru = [v for v in PR if v.split("@")[0] in ("xenia", "kseniya", "eugene", "aidar", "baya")]
    cs = [v for v in PR if v.startswith("cis:")]
    if ru and cs:
        g1 = [PR[v]["gop"] for v in ru]; g2 = sorted((PR[v]["gop"], v.split("@")[0][4:]) for v in cs)
        md += ["## Чёткость звуков: дикторы модели Барсика и дикторы свободной модели", "",
               f"Одни и те же фразы. Модель Барсика (v5_ru): {', '.join(f'{v.split(chr(64))[0]} {PR[v][chr(103) + chr(111) + chr(112)]:.2f}' for v in ru)} — в среднем {np.mean(g1):.2f}. "
               f"Свободная (v5_cis), 32 диктора: от {g2[0][0]:.2f} ({g2[0][1]}) до {g2[-1][0]:.2f} ({g2[-1][1]}), в среднем {np.mean([x[0] for x in g2]):.2f}. "
               f"Лучшие по чёткости: {', '.join(f'{n} {g:.2f}' for g, n in g2[::-1][:8])}.", ""]
        RES["gop"] = {"ru": {v: PR[v]["gop"] for v in ru}, "cis": {n: g for g, n in g2}}

    # ---------- 4. сверка с ухом Михаила
    md += ["## 4. Сверка с ухом Михаила", "", "Михаил 25.11: «не попадаешь ты в их звук» — про все отправленные пробы.", ""]
    for g, cv, verdict, ns, ni, nb, tim in verdicts:
        md.append(f"- {g} → {NOTE.get(cv, cv)}: **{verdict}** (узнаватели «тот же» {ns} из {ni}; сильных отличий {nb}; тембр ×{tim:.1f})")
    md.append("")
    open(f"{OUT}/itog.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(RES, open(f"{OUT}/sluh.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              default=lambda o: (None if (isinstance(o, float) and o != o) else float(o)) if isinstance(o, (float, np.floating)) else str(o))
    log("\n".join(md))

    # ---------- картинки: спектр фразы, долгий спектр, гласные
    edges = np.geomspace(80, 20000, 41); cen = np.sqrt(edges[:-1] * edges[1:])
    for gname, tv, cands, src in GROUPS:
        vs = [v for v in [tv] + cands if v in byv and (v == tv or v.endswith("@g24") or v.endswith("@syn"))]
        if len(vs) < 2:
            continue
        slug = {"Барсик": "barsik", "Рон": "ron", "Пик": "pik", "№4": "n4"}[gname]
        try:
            pics = [[u for u in byv[v] if u.get("pic")] for v in vs]
            ncol = min(2, min(len(p) for p in pics))
            if ncol:
                fig, ax = plt.subplots(len(vs), ncol, figsize=(7.5 * ncol, 2.3 * len(vs)), squeeze=False)
                for r, (v, ps) in enumerate(zip(vs, pics)):
                    for c in range(ncol):
                        u = ps[c]; m = u["pic"]["mel"].astype(float).T
                        ax[r][c].imshow(m, origin="lower", aspect="auto", cmap="magma", vmin=np.percentile(m, 30), vmax=np.percentile(m, 99.5),
                                        extent=[0, m.shape[1] / u["pic"]["fps"], 0, 56])
                        f0 = u["pic"]["f0"].astype(float); f0[f0 <= 0] = np.nan
                        a2 = ax[r][c].twinx(); a2.plot(u["pic"]["pt"], f0, color="cyan", lw=1.6); a2.set_ylim(50, 600 if gname != "№4" else 250)
                        ax[r][c].set_title(f"{NOTE.get(v, v)} — {u['text'][:60]}", fontsize=8); ax[r][c].set_yticks([])
                fig.tight_layout(); fig.savefig(f"{OUT}/spec_{slug}.png", dpi=85); plt.close(fig)
            fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
            for v in vs:
                ax[0].semilogx(cen, PR[v]["ltas"], lw=3 if v == tv else 1.4, color="black" if v == tv else None, label=NOTE.get(v, v.split("@")[0]))
                ci = PR[tv]["ceil_i"]
                xs = [(PR[v]["F"][c][ci][1], PR[v]["F"][c][ci][0], c) for c in PR[v]["F"]]
                if xs:
                    ax[1].scatter([x[0] for x in xs], [x[1] for x in xs], s=70 if v == tv else 30, color="black" if v == tv else None, label=NOTE.get(v, v.split("@")[0]))
                    for x in xs:
                        ax[1].annotate(VNAME.get(x[2], x[2]), (x[0], x[1]), fontsize=11 if v == tv else 8)
            ax[0].set_xlim(80, 20000); ax[0].set_title("Долгий спектр (дБ к среднему)"); ax[0].legend(fontsize=7); ax[0].grid(alpha=.3)
            ax[1].invert_xaxis(); ax[1].invert_yaxis(); ax[1].set_xlabel("F2, Гц"); ax[1].set_ylabel("F1, Гц"); ax[1].set_title("Ударные гласные"); ax[1].grid(alpha=.3)
            fig.tight_layout(); fig.savefig(f"{OUT}/tembr_{slug}.png", dpi=85); plt.close(fig)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    if sys.argv[1] == "feat":
        feat(int(sys.argv[2]), int(sys.argv[3]))
    else:
        final()
