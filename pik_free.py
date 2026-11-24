#!/usr/bin/env python3
"""Свободный голос Пика (24.11.2026). Михаил: голоса с некоммерческой лицензией не ставим; Пику — ближе к нынешнему (голос iPhone), можно своё.
Мерка — 35 реплик Пика голосом iPhone из серий 34–37 (pik/target/, только для сравнения, в звук не идёт).
Кандидат = диктор Silero v5_cis (MIT) + обработка как в движке (multik-bars-golos.js, say()):
  модель читает с тоном ×P/F и темпом ×T/F, потом звук ускоряется в F раз (resample) → итог: тон ×P, темп ×T, тембр (форманты) ×F.
  Тон и темп внутри модели здесь заменены WORLD (pyworld) — для сравнения похожести этого хватает; итоговую пробу считает сам движок.
Оценка: похожесть тембра на мерку (resemblyzer), высота, «яркость» (центроид спектра), темп, разборчивость (whisper), естественность (UTMOS).
  python pik_free.py r1 <part> <n>
  python pik_free.py final       → pik/itog.md, pik/pik_free.json, pik/proba.mp4 (мерка + 3 лучших)
"""
import difflib, glob, json, math, os, subprocess, sys
import numpy as np

PH = ["Смотрите, вот миска. Что в ней?", "Помните, как солнце выпило лужу?",
      "Это потому, что ты медвежонок. Медведи спят всю зиму!", "У ёлки иголки. Тонкие и крепкие. Им мороз не страшен.",
      "Нет. Но спит он, как медведь.", "Спокойной ночи, сторож.", "Мороз делает лёд. А тепло делает воду.",
      "Снег тает понемногу. Вода уходит в землю."]
# женские дикторы v5_cis с хорошей разборчивостью (cast/kasting.json); ru_alfia — Филя, ru_albina — рассказчица: не берём
SPK = {"ru_zinaida": 182, "ru_kermen": 216, "ru_zara": 210, "ru_nurgul": 194, "ru_aigul": 203, "ru_zhadyra": 190,
       "ru_vika": 198, "ru_ekaterina": 229, "ru_zhazira": 228, "ru_saida": 202}
F0T = [340, 380]
FF = [1.0, 1.12, 1.25]
TT = [1.15, 1.35]
SR16 = 16000


def log(*a):
    print(*a, flush=True)


def cands():
    C = []
    for s, b in SPK.items():
        for f0 in F0T:
            for F in FF:
                for T in TT:
                    C.append({"id": f"{s[3:]}_{f0}_{F}_{T}", "spk": s, "P": round(f0 / b, 3), "F": F, "T": T})
    return C


def load(path, sr):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def save(x, path, sr):
    import wave
    x = (np.asarray(x) * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())


def engine(x, sr, P, F, T):
    """Как движок: тон ×P/F и темп ×T/F (здесь WORLD), потом resample в F раз (как G.resample)."""
    import pyworld as pw
    x = x.astype(np.float64)
    f0, t = pw.harvest(x, sr, f0_floor=80, f0_ceil=600, frame_period=5.0)
    sp = pw.cheaptrick(x, f0, t, sr); ap = pw.d4c(x, f0, t, sr)
    k = T / F                                   # во столько раз быстрее читает модель
    n = max(2, int(round(len(f0) / k)))
    idx = np.linspace(0, len(f0) - 1, n)
    i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, len(f0) - 1); w = (idx - i0)[:, None]
    f0n = np.where((f0[i0] > 0) & (f0[i1] > 0), f0[i0] * (1 - w[:, 0]) + f0[i1] * w[:, 0], 0) * (P / F)
    spn = np.exp(np.log(sp[i0] + 1e-12) * (1 - w) + np.log(sp[i1] + 1e-12) * w)
    apn = ap[i0] * (1 - w) + ap[i1] * w
    y = pw.synthesize(np.ascontiguousarray(f0n), np.ascontiguousarray(spn), np.ascontiguousarray(apn), sr, 5.0)
    if abs(F - 1) > .004:                        # G.resample: читаем быстрее в F раз
        m = int(np.floor((len(y) - 2) / F)); y = np.interp(np.arange(m) * F, np.arange(len(y)), y)
    y = y / (np.abs(y).max() + 1e-9) * 0.9
    return y.astype(np.float32)


def feats(a16, text=None):
    import parselmouth
    snd = parselmouth.Sound(a16.astype(np.float64), SR16)
    p = snd.to_pitch_ac(time_step=0.01, pitch_floor=80, pitch_ceiling=650).selected_array["frequency"]
    fv = p[p > 0]
    fr = a16[: len(a16) // 320 * 320].reshape(-1, 320)
    rms = np.sqrt((fr ** 2).mean(1) + 1e-12)
    act = rms > rms.max() * 10 ** (-35 / 20)
    X = np.abs(np.fft.rfft(fr * np.hanning(320), axis=1)); fq = np.fft.rfftfreq(320, 1 / SR16)
    cen = float(np.median((X[act] * fq).sum(1) / (X[act].sum(1) + 1e-9))) if act.any() else 0.0
    r = {"f0": float(np.median(fv)) if len(fv) > 10 else 0.0, "cen": cen,
         "range": float(np.percentile(12 * np.log2(fv), 95) - np.percentile(12 * np.log2(fv), 5)) if len(fv) > 10 else 0.0}
    if text:
        r["rate"] = sum(1 for c in text.lower() if c in "аеёиоуыэюя") / max(act.sum() * 0.02, 0.1)
    return r


_m = {}


def emb(list16):
    if "e" not in _m:
        from resemblyzer import VoiceEncoder
        _m["e"] = VoiceEncoder("cpu")
    from resemblyzer import preprocess_wav
    E = [_m["e"].embed_utterance(preprocess_wav(a, source_sr=SR16)) for a in list16]
    m = np.mean(E, 0); return m / np.linalg.norm(m)


def target():
    A, Fs = [], []
    for f in sorted(glob.glob("pik/target/*.flac")):
        t = open(f[:-5] + ".txt", encoding="utf-8").read().strip()
        a = load(f, SR16); A.append(a); Fs.append(feats(a, t))
    T = {k: float(np.median([x[k] for x in Fs])) for k in ("f0", "cen", "range", "rate")}
    T["emb"] = emb(A).tolist()
    return T


def J(r, T):
    dst = abs(12 * math.log2(max(r["f0"], 1) / T["f0"]))
    return round(3 * r["sim"] + 2 * r["match"] + 0.6 * r["utmos"] - 0.2 * dst - 0.3 * abs(r["rate"] - T["rate"])
                 - 0.0006 * abs(r["cen"] - T["cen"]) - 0.03 * abs(r["range"] - T["range"]), 3)


def evaluate(C):
    import torch, gen, svoy_free, svoy_omo, svoy2, voice_check as vc
    torch.hub._validate_not_a_forked_repo = lambda *a, **k: True   # проверка через api.github.com без токена падает (KeyError 'Authorization')
    os.makedirs("pack", exist_ok=True); os.makedirs("tmp", exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    T = target(); json.dump(T, open("pack/target.json", "w"))
    log("мерка (iPhone):", {k: round(T[k], 2) for k in ("f0", "cen", "range", "rate")})
    marks = {t: svoy_free.mark_full(t) for t in PH}
    log("разметка:", marks[PH[2]])
    m = gen.silero_model("v5_cis_base")
    base = {}
    for s in sorted({c["spk"] for c in C}):
        for k, t in enumerate(PH):
            a = m.apply_tts(text=marks[t], speaker=s, sample_rate=48000)
            a = a.numpy() if hasattr(a, "numpy") else np.asarray(a)
            p = f"tmp/{s}_{k}.wav"; save(a, p, 48000)
            base[(s, k)] = load(p, 24000)
    temb = np.array(T["emb"])
    for c in C:
        try:
            outs, res = [], []
            for k, t in enumerate(PH):
                y = engine(base[(c["spk"], k)], 24000, c["P"], c["F"], c["T"])
                p = f"tmp/{c['id']}_{k}.wav"; save(y, p, 24000)
                a16 = load(p, SR16); outs.append(a16)
                with torch.no_grad():
                    ut = float(vc.utmos_model()(torch.from_numpy(a16)[None], SR16))
                heard = vc.whisper_model().transcribe(p, language="ru", fp16=False)["text"]
                res.append((ut, difflib.SequenceMatcher(None, vc.norm_words(t), vc.norm_words(heard)).ratio(), heard, feats(a16, t)))
                if k in (0, 2, 6):
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, f"pack/{c['id']}__{k}.flac"], check=True)
            r = dict(c, sim=round(float(np.dot(emb(outs), temb)), 4), utmos=round(float(np.mean([x[0] for x in res])), 3),
                     match=round(float(np.mean([x[1] for x in res])), 3),
                     **{q: round(float(np.median([x[3][q] for x in res])), 2) for q in ("f0", "cen", "range", "rate")},
                     bad=[(PH[k], x[2]) for k, x in enumerate(res) if x[1] < 0.85])
            r["J"] = J(r, T)
            json.dump(r, open(f"pack/L_{c['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
            log(c["id"], "J", r["J"], "похожесть", r["sim"], "Гц", r["f0"], "центроид", r["cen"], "темп", r["rate"],
                "UTMOS", r["utmos"], "слова", r["match"])
        except Exception as e:
            import traceback
            log("ОШИБКА", c["id"], repr(e)); traceback.print_exc()


def final():
    L = [json.load(open(j, encoding="utf-8")) for j in glob.glob("pack/L_*.json")]
    T = json.load(open("pack/target.json"))
    top = sorted(L, key=lambda r: -r["J"])
    os.makedirs("pik", exist_ok=True)
    Lm = ["# Свободный голос Пика (Silero v5_cis, MIT) — ближе к нынешнему голосу iPhone", "",
          f"Мерка — Пик голосом iPhone (35 реплик серий 34–37): {T['f0']:.0f} Гц, центроид {T['cen']:.0f} Гц, "
          f"темп {T['rate']:.1f} слога/с, живость {T['range']:.1f} полутона.",
          "J = 3·похожесть + 2·слова + 0,6·UTMOS − 0,2·разница высоты (полутоны) − 0,3·разница темпа − 0,0006·разница центроида − 0,03·разница живости.",
          "Строка для движка: `Пик:girl:speaker=<диктор>:P=<P>:F=<F>:T=<T>:R=1.2`.", "",
          "| | кандидат | J | похожесть | Гц | центроид | темп | живость | UTMOS | слова | P | F | T |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top[:30], 1):
        Lm.append(f"| {i} | {r['id']} | {r['J']} | {r['sim']} | {r['f0']:.0f} | {r['cen']:.0f} | {r['rate']} | {r['range']} | "
                  f"{r['utmos']} | {r['match']} | {r['P']} | {r['F']} | {r['T']} |")
    # лучший у каждого диктора — чтобы видеть, кто ближе по тембру
    seen, by = set(), []
    for r in top:
        if r["spk"] not in seen:
            seen.add(r["spk"]); by.append(r)
    Lm += ["", "## Лучший вариант каждого диктора", "", "| диктор | J | похожесть | Гц | центроид | темп | UTMOS | слова | P/F/T |", "|---|---|---|---|---|---|---|---|---|"]
    for r in by:
        Lm.append(f"| {r['spk']} | {r['J']} | {r['sim']} | {r['f0']:.0f} | {r['cen']:.0f} | {r['rate']} | {r['utmos']} | {r['match']} | {r['P']}/{r['F']}/{r['T']} |")
    open("pik/itog.md", "w", encoding="utf-8").write("\n".join(Lm) + "\n")
    log("\n".join(Lm[:20]))
    # три лучших разных дикторов
    best = by[:3]
    json.dump({"made": "2026-11-24", "model": "v5_cis_base (MIT)", "target": {k: T[k] for k in ("f0", "cen", "range", "rate")},
               "voices": [{"id": r["id"], "golos": f"girl:speaker={r['spk']}:P={r['P']}:F={r['F']}:T={r['T']}:R=1.2",
                           "J": r["J"], "sim": r["sim"], "f0": r["f0"], "utmos": r["utmos"], "match": r["match"]} for r in best]},
              open("pik/pik_free.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "r1":
        p, n = int(sys.argv[2]), int(sys.argv[3]); evaluate(cands()[p::n])
    elif cmd == "final":
        final()
