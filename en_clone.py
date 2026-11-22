# Голоса героев «Кот Барсик» на других языках: тот же голос, другой язык.
# A — Chatterbox Multilingual клонирует голос героя по образцу и говорит на нужном языке.
# B — Kokoro читает фразу с родным произношением, Chatterbox VC перекрашивает её в голос героя.
# Проверка: узнаётся ли герой (ECAPA — сходство голоса с образцом и с соседями), высота (Praat),
# разборчивость (Whisper base). Итог — out_klon/<герой>.mp3 и out_klon/report.md.
import asyncio, difflib, inspect, json, os, re, subprocess, time, traceback

import numpy as np
import soundfile as sf
import torch

_orig_load = torch.load


def _cpu_load(*a, **k):
    k.setdefault("map_location", "cpu")
    return _orig_load(*a, **k)


torch.load = _cpu_load
torch.set_num_threads(max(1, os.cpu_count() or 4))

import parselmouth  # noqa: E402
from parselmouth.praat import call  # noqa: E402

SR = 24000
J = json.load(open("clone.json", encoding="utf-8"))
OUT, TMP = J.get("out", "out_klon"), "tmp_klon"
for d in (OUT, os.path.join(OUT, "v"), TMP):
    os.makedirs(d, exist_ok=True)
NUM = ["один", "два", "три"]
METHODS = J.get("methods", ["A", "B"])


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def call_kw(fn, **kw):
    sig = inspect.signature(fn)
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        return fn(**kw)
    return fn(**{k: v for k, v in kw.items() if k in sig.parameters})


def to_np(wav):
    if hasattr(wav, "detach"):
        wav = wav.detach().cpu().numpy()
    a = np.asarray(wav, dtype=np.float32)
    return a.reshape(-1) if a.ndim > 1 else a


def save_any(arr, sr, path):
    if sr == SR:
        sf.write(path, arr, SR)
        return arr
    raw = path[:-4] + "_sr.wav"
    sf.write(raw, arr, sr)
    ff("-i", raw, "-ac", "1", "-ar", str(SR), path)
    return load(path)


def load(path):
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        tmp = path[:-4] + "_rs.wav"
        ff("-i", path, "-ac", "1", "-ar", str(SR), tmp)
        a, _ = sf.read(tmp, dtype="float32")
    return a


def silence(sec):
    return np.zeros(int(SR * sec), dtype=np.float32)


def measure(arr):
    snd = parselmouth.Sound(arr.astype(np.float64), sampling_frequency=SR)
    p = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=700).selected_array["frequency"]
    v = p[p > 0]
    if len(v) < 5:
        return {"f0": None, "range_st": None, "hnr": None}
    p10, p90 = np.percentile(v, [10, 90])
    h = snd.to_harmonicity_cc(time_step=0.01, minimum_pitch=75).values
    h = h[h > -200]
    return {"f0": round(float(np.median(v)), 1), "range_st": round(float(12 * np.log2(p90 / p10)), 1),
            "hnr": round(float(np.mean(h)), 1) if len(h) else None}


def match_pitch(arr, f0_out, f0_ref):
    if not f0_out or not f0_ref:
        return arr, 0.0
    st = 12 * np.log2(f0_ref / f0_out)
    if abs(st) <= 1.5:
        return arr, 0.0
    snd = parselmouth.Sound(arr.astype(np.float64), sampling_frequency=SR)
    out = call(snd, "Change gender", 75, 700, 1.0, float(f0_ref), 1.0, 1.0)
    a = np.asarray(out.values[0], dtype=np.float32)
    pk = float(np.max(np.abs(a))) or 1.0
    return (a / pk * 0.9 if pk > 0.99 else a), round(float(st), 1)


def loudnorm(arr, path):
    raw = path[:-4] + "_raw.wav"
    sf.write(raw, arr, SR)
    ff("-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "1", path)
    return load(path)


def edge(text, voice, path):
    import edge_tts
    mp3 = path[:-4] + ".mp3"
    asyncio.run(edge_tts.Communicate(text, voice).save(mp3))
    ff("-i", mp3, "-ac", "1", "-ar", str(SR), path)
    return load(path)


def label(text, path):
    try:
        return edge(text, J.get("label_voice", "ru-RU-SvetlanaNeural"), path)
    except Exception:
        traceback.print_exc()
        t = np.arange(int(SR * 0.15)) / SR
        return (0.3 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)


# ---------- синтез ----------
_kp = {}


def kokoro(text, lang, voice, path):
    from kokoro import KPipeline
    if lang not in _kp:
        _kp[lang] = KPipeline(lang_code=lang)
    parts = [to_np(a) for _, _, a in _kp[lang](text, voice=voice, speed=1.0) if a is not None]
    sf.write(path, np.concatenate(parts), SR)


def run_A(items):
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS as M
    try:
        model = call_kw(M.from_pretrained, device="cpu", t3_model="v3")
    except Exception:
        traceback.print_exc()
        model = M.from_pretrained(device="cpu")
    log("A: модель загружена, sr", model.sr)
    for it in items:
        try:
            t0 = time.time()
            pieces = []
            for k, line in enumerate(it["lines"]):
                wav = call_kw(model.generate, text=line, language_id=it["lang"], audio_prompt_path=it["ref"],
                              exaggeration=0.5, cfg_weight=0.0, temperature=0.8)
                a = save_any(to_np(wav), model.sr, os.path.join(TMP, f"A_{it['key']}_{k}.wav"))
                pieces += [a, silence(0.45)]
            it["A"] = {"audio": np.concatenate(pieces), "gen_sec": round(time.time() - t0, 1)}
            log("A", it["key"], it["A"]["gen_sec"], "с")
        except Exception as e:
            traceback.print_exc()
            it["A"] = {"error": f"{type(e).__name__}: {e}"[:300]}
    del model


def run_B(items):
    from chatterbox.vc import ChatterboxVC
    vc = call_kw(ChatterboxVC.from_pretrained, device="cpu")
    log("B: модель загружена, sr", vc.sr)
    for it in items:
        try:
            t0 = time.time()
            lang_code, voice = it["src"]
            pieces = []
            for k, line in enumerate(it["lines"]):
                src = os.path.join(TMP, f"Bsrc_{it['key']}_{k}.wav")
                kokoro(line, lang_code, voice, src)
                wav = call_kw(vc.generate, audio=src, target_voice_path=it["ref"])
                a = save_any(to_np(wav), vc.sr, os.path.join(TMP, f"B_{it['key']}_{k}.wav"))
                pieces += [a, silence(0.45)]
            it["B"] = {"audio": np.concatenate(pieces), "gen_sec": round(time.time() - t0, 1),
                       "src": f"kokoro:{voice}"}
            log("B", it["key"], it["B"]["gen_sec"], "с")
        except Exception as e:
            traceback.print_exc()
            it["B"] = {"error": f"{type(e).__name__}: {e}"[:300]}
    del vc


# ---------- проверка ----------
_enc = None


def embed(arr):
    global _enc
    import torchaudio
    if _enc is None:
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except Exception:
            from speechbrain.pretrained import EncoderClassifier
        _enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                              savedir=os.path.join(TMP, "ecapa"), run_opts={"device": "cpu"})
    x = torchaudio.functional.resample(torch.tensor(arr).unsqueeze(0), SR, 16000)
    with torch.no_grad():
        e = _enc.encode_batch(x).reshape(-1)
    return (e / e.norm()).numpy()


_wh = None


def heard(path, lang):
    global _wh
    import whisper
    if _wh is None:
        _wh = whisper.load_model("base")
    return _wh.transcribe(path, language=lang, fp16=False)["text"].strip()


def words(t):
    return re.findall(r"\w+", t.lower())


def clear_pct(ref, hyp):
    r, h = words(ref), words(hyp)
    sm = difflib.SequenceMatcher(a=r, b=h, autojunk=False)
    return round(100.0 * sum(b.size for b in sm.get_matching_blocks()) / max(1, len(r)), 1)


def check_one(it, m, r, E):
    raw = r["audio"]
    mr = measure(raw)
    fixed, shift = match_pitch(raw, mr["f0"], REF_F0[it["slug"]])
    arr = loudnorm(fixed, os.path.join(TMP, f"fin_{m}_{it['key']}.wav"))
    fin = measure(arr)
    sims = {}
    if E:
        e = embed(arr)
        sims = {t: float(e @ E[t]) for t in E}
    wavp = os.path.join(TMP, "h.wav")
    sf.write(wavp, arr, SR)
    txt = heard(wavp, it["lang"])
    ff("-i", wavp, "-codec:a", "libmp3lame", "-q:a", "3", os.path.join(OUT, "v", f"{it['key']}_{m}.mp3"))
    r.update(f0_raw=mr["f0"], f0=fin["f0"], shift_st=shift, range_st=fin["range_st"], hnr=fin["hnr"],
             sim_own=round(sims[it["slug"]], 3) if sims else None, nearest=max(sims, key=sims.get) if sims else it["slug"],
             sim_other=round(max(v for t, v in sims.items() if t != it["slug"]), 3) if sims else None,
             heard=txt, clear=clear_pct(" ".join(it["lines"]), txt), sec=round(len(arr) / SR, 1), audio=arr)
    log(m, it["key"], "сходство", r["sim_own"], "ближе всего", r["nearest"], "понято", r["clear"])


REF_F0 = {}


def main():
    heroes = J["heroes"]
    ALL = J.get("names") or {h["slug"]: h["name"] for h in heroes}
    refs = {s: load(f"refs/{s}_ref.wav") for s in ALL}
    ref_f0 = {s: measure(a)["f0"] for s, a in refs.items()}
    REF_F0.update(ref_f0)
    items = []
    for h in heroes:
        for lang, lines in h["texts"].items():
            items.append({"key": f"{h['slug']}_{lang}", "slug": h["slug"], "lang": lang, "lines": lines,
                          "ref": f"refs/{h['slug']}_ref.wav",
                          "src": h.get("src", {}).get(lang) or J["kokoro_src"][lang]})
    log("фраз:", sum(len(i["lines"]) for i in items), "наборов:", len(items))
    if "A" in METHODS:
        run_A(items)
    if "B" in METHODS:
        run_B(items)

    log("проверка: сходство голосов")
    E, base = {}, {}
    try:
        E = {s: embed(a) for s, a in refs.items()}
        held = {s: load(f"refs/{s}_held.wav") for s in ALL}
        for s, a in held.items():
            e = embed(a)
            sims = {t: float(e @ E[t]) for t in E}
            base[s] = {"own": round(sims[s], 3), "nearest": max(sims, key=sims.get),
                       "others": round(max(v for t, v in sims.items() if t != s), 3)}
    except Exception:
        traceback.print_exc()
        E, base = {}, {}

    for it in items:
        for m in METHODS:
            r = it.get(m) or {}
            if r.get("audio") is None:
                continue
            try:
                check_one(it, m, r, E)
            except Exception as e:
                traceback.print_exc()
                r["check_error"] = f"{type(e).__name__}: {e}"[:300]


    # файлы героев: по-русски как сейчас, потом языки и способы
    names = ALL
    for h in heroes:
        s = h["slug"]
        seq = [loudnorm(label("По-русски, как сейчас.", os.path.join(TMP, f"l_ru_{s}.wav")), os.path.join(TMP, f"ln_ru_{s}.wav")),
               silence(0.3), loudnorm(load(f"refs/{s}_ru.wav"), os.path.join(TMP, f"ru_{s}.wav")), silence(0.9)]
        for it in [i for i in items if i["slug"] == s]:
            for n, m in enumerate(METHODS):
                r = it.get(m) or {}
                if r.get("audio") is None:
                    continue
                lab_txt = f"{J['lang_name'][it['lang']]}." if len(METHODS) == 1 else f"{J['lang_name'][it['lang']]}, вариант {NUM[n]}."
                lab = label(lab_txt, os.path.join(TMP, f"l_{m}_{it['key']}.wav"))
                seq += [loudnorm(lab, os.path.join(TMP, f"ln_{m}_{it['key']}.wav")), silence(0.3), r["audio"], silence(0.9)]
        sf.write(os.path.join(TMP, "hero.wav"), np.concatenate(seq), SR)
        ff("-i", os.path.join(TMP, "hero.wav"), "-codec:a", "libmp3lame", "-q:a", "3", os.path.join(OUT, f"{s}.mp3"))

    rep = {"ref_f0": ref_f0, "baseline": base, "items": []}
    md = ["# Голоса героев на других языках", "",
          "Сходство — ECAPA, косинус с образцом героя (1 — тот же голос). «Ближе всего» — к чьему образцу ближе.", "",
          "## Проверка самой мерки: другие русские реплики того же героя", "",
          "| Герой | f0 образца | Сходство со своим | Ближе всего | Лучший чужой |", "|---|---|---|---|---|"]
    for s, b in base.items():
        md.append(f"| {names[s]} | {ref_f0[s]} | {b['own']} | {names[b['nearest']]} | {b['others']} |")
    md += ["", "## Пробы", "",
           "| Герой | Язык | Способ | Сходство | Ближе всего | Лучший чужой | f0 было → стало (сдвиг, пт) | HNR | Понято | Сек. синтеза | Услышано |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for it in items:
        for n, m in enumerate(METHODS):
            r = it.get(m) or {}
            r.pop("audio", None)
            row = {"key": it["key"], "lang": it["lang"], "method": m, **{k: v for k, v in r.items()}}
            rep["items"].append(row)
            if r.get("error"):
                md.append(f"| {names[it['slug']]} | {it['lang']} | {n + 1} ({m}) | ОШИБКА | | | | | | | {r['error']} |")
            elif r.get("check_error"):
                md.append(f"| {names[it['slug']]} | {it['lang']} | {n + 1} ({m}) | проверка не прошла | | | | | | {r.get('gen_sec')} | {r['check_error']} |")
            elif "f0" in r:
                md.append(f"| {names[it['slug']]} | {it['lang']} | {n + 1} ({m}) | {r['sim_own']} | {names[r['nearest']]} | "
                          f"{r['sim_other']} | {r['f0_raw']} → {r['f0']} ({r['shift_st']}) | {r['hnr']} | {r['clear']}% | "
                          f"{r.get('gen_sec')} | {r['heard']} |")
    json.dump(rep, open(os.path.join(OUT, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    log("готово")


if __name__ == "__main__":
    main()
