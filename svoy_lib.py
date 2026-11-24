#!/usr/bin/env python3
"""Общие замеры для подбора свободных голосов (25.11.2026).
  ali(a16, text)        — слова с временем + «чистота произношения» (GOP): насколько уверенно фонемный распознаватель
                          слышит ожидаемые звуки. У русских дикторов (Ксения) выше, у голоса с акцентом — ниже.
  manner(wc, pc, wt, pt) — похожесть манеры двух записей одной фразы: ритм (относительные длины слов) и мелодия (высота по словам).
  emb(list16), feats(a16, text), load(path, sr), save(x, path, sr)
"""
import subprocess
import numpy as np

SR16 = 16000
VOW = "аеёиоуыэюя"
_m = {}


def load(path, sr):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def save(x, path, sr):
    import wave
    x = (np.asarray(x) * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())


def ali(a16, plain):
    """→ (слова с t0/t1, {"gop": средняя уверенность по всем звукам, "gop_c": по согласным})."""
    import torch, torchaudio.functional as AF, voice_check as vc
    proc, model = vc.phon_model()
    tok = proc.tokenizer
    vocab = tok.get_vocab()
    blank = tok.pad_token_id
    special = {blank, tok.unk_token_id, getattr(tok, "bos_token_id", None), getattr(tok, "eos_token_id", None)}
    vowel_ids = [i for t, i in vocab.items() if t and t[0] in vc.IPAV and i not in special]
    with torch.no_grad():
        x = proc(a16, sampling_rate=vc.SR, return_tensors="pt").input_values
        lp = torch.log_softmax(model(x).logits[0], -1)
    T = lp.shape[0]
    fps = T / (len(a16) / vc.SR)
    words = vc.tokenize(plain)
    phs = vc.phonemize_words(words)
    cols, tgt, meta, colmap = [blank], [], [], {}
    for wi, (w, pl) in enumerate(zip(words, phs)):
        for p in pl:
            if p[0] in vc.IPAV:
                key = "V"
            else:
                cand = [p, p.replace("ʲ", ""), p.replace("ː", ""), p[0]]
                key = next((c for c in cand if c in vocab and vocab[c] not in special), None)
                if key is None:
                    continue
            meta.append((wi, key))
            if key not in colmap:
                colmap[key] = len(cols); cols.append(key)
            tgt.append(colmap[key])
    if not tgt or T < len(tgt) + 2:
        return words, {"gop": 0.0, "gop_c": 0.0}
    em = torch.empty(T, len(cols))
    em[:, 0] = lp[:, blank]
    for key, c in colmap.items():
        em[:, c] = torch.logsumexp(lp[:, vowel_ids], -1) if key == "V" else lp[:, vocab[key]]
    al, sc = AF.forced_align(em[None], torch.tensor([tgt], dtype=torch.int32), blank=0)
    spans = list(AF.merge_tokens(al[0], sc[0].exp()))
    for sp, (wi, key) in zip(spans, meta):
        words[wi].setdefault("t0", sp.start / fps)
        words[wi]["t1"] = sp.end / fps
    g = [float(sp.score) for sp in spans]
    gc = [float(sp.score) for sp, (wi, key) in zip(spans, meta) if key != "V"]
    return words, {"gop": float(np.mean(g)) if g else 0.0, "gop_c": float(np.mean(gc)) if gc else 0.0}


def pitch(a16):
    """→ (времена, f0) Praat, пол 60 Гц (низкие мужские смеси)."""
    import parselmouth
    snd = parselmouth.Sound(a16.astype(np.float64), SR16)
    p = snd.to_pitch_ac(time_step=0.01, pitch_floor=60, pitch_ceiling=600)
    return p.xs(), p.selected_array["frequency"]


def word_vecs(words, pt, f0):
    """По словам: длина (с) и средняя высота (полутоны от средней по фразе); None, где слова нет или оно глухое."""
    fv = f0[f0 > 0]
    med = float(np.median(12 * np.log2(fv))) if len(fv) > 5 else 0.0
    D, M = [], []
    for w in words:
        if "t0" not in w:
            D.append(None); M.append(None); continue
        D.append(max(w["t1"] - w["t0"], 0.02))
        ff = f0[(pt >= w["t0"] - 0.02) & (pt <= w["t1"] + 0.02) & (f0 > 0)]
        M.append(float(np.median(12 * np.log2(ff))) - med if len(ff) >= 2 else None)
    return D, M


def corr(a, b):
    ok = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(ok) < 4:
        return None
    x, y = np.array([o[0] for o in ok]), np.array([o[1] for o in ok])
    if x.std() < 1e-6 or y.std() < 1e-6:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def manner(Dc, Mc, Dt, Mt):
    """Ритм: корреляция логарифмов относительных длин слов; мелодия: корреляция высоты по словам. −1…1, None если мало слов."""
    lc = [np.log(d) if d else None for d in Dc]
    lt = [np.log(d) if d else None for d in Dt]
    return {"rhythm": corr(lc, lt), "melody": corr(Mc, Mt)}


def feats(a16, text=None):
    pt, f0 = pitch(a16)
    fv = f0[f0 > 0]
    fr = a16[: len(a16) // 320 * 320].reshape(-1, 320)
    rms = np.sqrt((fr ** 2).mean(1) + 1e-12)
    act = rms > rms.max() * 10 ** (-35 / 20)
    X = np.abs(np.fft.rfft(fr * np.hanning(320), axis=1)); fq = np.fft.rfftfreq(320, 1 / SR16)
    cen = float(np.median((X[act] * fq).sum(1) / (X[act].sum(1) + 1e-9))) if act.any() else 0.0
    r = {"f0": float(np.median(fv)) if len(fv) > 10 else 0.0, "cen": cen,
         "range": float(np.percentile(12 * np.log2(fv), 95) - np.percentile(12 * np.log2(fv), 5)) if len(fv) > 10 else 0.0}
    if text:
        r["rate"] = sum(1 for c in text.lower() if c in VOW) / max(act.sum() * 0.02, 0.1)
    return r


def emb(list16):
    if "e" not in _m:
        from resemblyzer import VoiceEncoder
        _m["e"] = VoiceEncoder("cpu")
    from resemblyzer import preprocess_wav
    E = [_m["e"].embed_utterance(preprocess_wav(a, source_sr=SR16)) for a in list16 if len(a) > SR16 * 0.4]
    m = np.mean(E, 0)
    return m / np.linalg.norm(m)


def heard_match(path, plain):
    import difflib, voice_check as vc
    heard = vc.whisper_model().transcribe(path, language="ru", fp16=False)["text"]
    nw = lambda t: vc.norm_words(t.replace("-", " "))
    return heard.strip(), difflib.SequenceMatcher(None, nw(plain), nw(heard)).ratio()


def utmos(a16):
    import torch, voice_check as vc
    torch.hub._validate_not_a_forked_repo = lambda *a, **k: True
    with torch.no_grad():
        return float(vc.utmos_model()(torch.from_numpy(a16)[None], SR16))
