# Английские пробы голосов героев «Кот Барсик».
# Читает jobs.json, озвучивает реплики (Kokoro или Microsoft edge), подгоняет высоту и тембр
# под зверя (Praat «Change gender»), меряет высоту, чистоту тембра и разборчивость (Whisper),
# собирает по файлу на героя: «<Имя>. Вариант один.» + реплики, «Вариант два.» + ...
import asyncio, difflib, json, os, re, subprocess, traceback

import numpy as np
import parselmouth
import soundfile as sf
from parselmouth.praat import call

SR = 24000
OUT, TMP = "out", "tmp"
for d in (OUT, os.path.join(OUT, "v"), TMP):
    os.makedirs(d, exist_ok=True)

JOBS = json.load(open("jobs.json", encoding="utf-8"))
_kp = {}


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def kokoro_tts(text, voice, speed, path):
    from kokoro import KPipeline
    lang = voice[0]
    if lang not in _kp:
        _kp[lang] = KPipeline(lang_code=lang)
    parts = []
    for _, _, audio in _kp[lang](text, voice=voice, speed=speed):
        if audio is None:
            continue
        a = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
        parts.append(a.astype(np.float32))
    sf.write(path, np.concatenate(parts), SR)


def edge_tts(text, voice, path, rate="+0%"):
    import edge_tts as et
    mp3 = path[:-4] + ".mp3"
    asyncio.run(et.Communicate(text, voice, rate=rate).save(mp3))
    ff("-i", mp3, "-ac", "1", "-ar", str(SR), path)


def silence(sec):
    return np.zeros(int(SR * sec), dtype=np.float32)


def load(path):
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        tmp = path[:-4] + "_rs.wav"
        ff("-i", path, "-ac", "1", "-ar", str(SR), tmp)
        a, _ = sf.read(tmp, dtype="float32")
    return a


def pitch_values(snd):
    p = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=700)
    v = p.selected_array["frequency"]
    return v[v > 0]


def measure(arr):
    snd = parselmouth.Sound(arr.astype(np.float64), sampling_frequency=SR)
    v = pitch_values(snd)
    if len(v) < 5:
        return {"f0": None, "range_st": None, "hnr": None}
    p10, p90 = np.percentile(v, [10, 90])
    h = snd.to_harmonicity_cc(time_step=0.01, minimum_pitch=75).values
    h = h[h > -200]
    return {
        "f0": round(float(np.median(v)), 1),
        "range_st": round(float(12 * np.log2(p90 / p10)), 1),
        "hnr": round(float(np.mean(h)), 1) if len(h) else None,
    }


def transform(arr, v):
    f0, F, rng, dur = v.get("f0", 0), v.get("F", 1.0), v.get("range", 1.0), v.get("dur", 1.0)
    if not f0 and F == 1.0 and rng == 1.0 and dur == 1.0:
        return arr
    snd = parselmouth.Sound(arr.astype(np.float64), sampling_frequency=SR)
    out = call(snd, "Change gender", 75, 700, F, float(f0 or 0), rng, dur)
    a = np.asarray(out.values[0], dtype=np.float32)
    peak = float(np.max(np.abs(a))) or 1.0
    return a / peak * 0.9 if peak > 0.99 else a


def loudnorm_wav(arr, path):
    raw = path[:-4] + "_raw.wav"
    sf.write(raw, arr, SR)
    ff("-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "1", path)
    return load(path)


def words(t):
    return re.findall(r"[a-z']+", t.lower().replace("’", "'"))


_wh = None


def heard(path):
    global _wh
    import whisper
    if _wh is None:
        _wh = whisper.load_model("base.en")
    return _wh.transcribe(path, language="en", fp16=False)["text"].strip()


def clear_pct(ref, hyp):
    r, h = words(ref), words(hyp)
    sm = difflib.SequenceMatcher(a=r, b=h, autojunk=False)
    ok = sum(b.size for b in sm.get_matching_blocks())
    return round(100.0 * ok / max(1, len(r)), 1)


def label(text, path, n):
    try:
        edge_tts(text, JOBS.get("label_voice", "ru-RU-SvetlanaNeural"), path)
        return load(path)
    except Exception:
        traceback.print_exc()
        t = np.arange(int(SR * 0.12)) / SR
        beep = (0.3 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        return np.concatenate([np.concatenate([beep, silence(0.12)]) for _ in range(n)])


def plot(hero, rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        rows = [r for r in rows if r.get("audio") is not None]
        if not rows:
            return
        fig, axes = plt.subplots(len(rows), 1, figsize=(12, 3.0 * len(rows)), squeeze=False)
        for ax, r in zip(axes[:, 0], rows):
            snd = parselmouth.Sound(r["audio"].astype(np.float64), sampling_frequency=SR)
            sp = snd.to_spectrogram(window_length=0.025, maximum_frequency=6000)
            X, Y = sp.x_grid(), sp.y_grid()
            db = 10 * np.log10(np.maximum(sp.values, 1e-12))
            ax.pcolormesh(X, Y, db, vmin=db.max() - 70, cmap="Greys", shading="auto")
            p = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=700)
            f = p.selected_array["frequency"]
            f[f == 0] = np.nan
            ax2 = ax.twinx()
            ax2.plot(p.xs(), f, "b.", ms=2)
            ax2.set_ylim(0, 700)
            ax2.set_ylabel("Гц (высота)")
            ax.set_ylim(0, 6000)
            ax.set_title(f"{hero['name']} — вариант {r['n']}: {r['voice']}  f0 {r.get('f0')}  HNR {r.get('hnr')}")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, f"{hero['slug']}.png"), dpi=70)
        plt.close(fig)
    except Exception:
        traceback.print_exc()


def main():
    nums = JOBS["numbers"]
    report = []
    for hero in JOBS["heroes"]:
        ref = " ".join(hero["lines"])
        rows = []
        for i, v in enumerate(hero["variants"]):
            n = i + 1
            row = {"n": n, "engine": v["engine"], "voice": v["voice"], "target": v}
            try:
                pieces, raws = [silence(0.15)], []
                for k, line in enumerate(hero["lines"]):
                    p = os.path.join(TMP, f"{hero['slug']}_{n}_{k}.wav")
                    if v["engine"] == "kokoro":
                        kokoro_tts(line, v["voice"], v.get("speed", 1.0), p)
                    else:
                        edge_tts(line, v["voice"], p, v.get("rate", "+0%"))
                    a = load(p)
                    raws.append(a)
                    pieces += [transform(a, v), silence(0.45)]
                raw_m = measure(np.concatenate(raws))
                arr = loudnorm_wav(np.concatenate(pieces), os.path.join(TMP, f"{hero['slug']}_{n}.wav"))
                m = measure(arr)
                vpath = os.path.join(OUT, "v", f"{hero['slug']}_{n}.mp3")
                sf.write(os.path.join(TMP, "v.wav"), arr, SR)
                ff("-i", os.path.join(TMP, "v.wav"), "-codec:a", "libmp3lame", "-q:a", "3", vpath)
                txt = heard(os.path.join(TMP, "v.wav"))
                row.update(m, f0_raw=raw_m["f0"], heard=txt, clear=clear_pct(ref, txt),
                           sec=round(len(arr) / SR, 2), audio=arr)
            except Exception as e:
                traceback.print_exc()
                row["error"] = f"{type(e).__name__}: {e}"[:300]
            rows.append(row)
        # общий файл героя
        seq = []
        for r in rows:
            if r.get("audio") is None:
                continue
            lab = label(f"{hero['name']}. Вариант {nums[r['n'] - 1]}.", os.path.join(TMP, f"lab_{hero['slug']}_{r['n']}.wav"), r["n"])
            lab = loudnorm_wav(lab, os.path.join(TMP, f"labn_{hero['slug']}_{r['n']}.wav"))
            seq += [lab, silence(0.35), r["audio"], silence(0.9)]
        if seq:
            sf.write(os.path.join(TMP, "hero.wav"), np.concatenate(seq), SR)
            ff("-i", os.path.join(TMP, "hero.wav"), "-codec:a", "libmp3lame", "-q:a", "3",
               os.path.join(OUT, f"{hero['slug']}.mp3"))
        plot(hero, rows)
        for r in rows:
            r.pop("audio", None)
        report.append({"slug": hero["slug"], "name": hero["name"], "who": hero["who"], "ref": ref, "variants": rows})
        print(hero["name"], [(r["n"], r.get("f0"), r.get("clear"), r.get("error")) for r in rows], flush=True)

    json.dump(report, open(os.path.join(OUT, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = ["# Английские пробы голосов", ""]
    for h in report:
        md += [f"## {h['name']} — {h['who']}", f"Текст: {h['ref']}", "",
               "| Вар. | Голос | f0 было → стало | Размах, пт | HNR | Понято слов | Услышано |",
               "|---|---|---|---|---|---|---|"]
        for r in h["variants"]:
            if r.get("error"):
                md.append(f"| {r['n']} | {r['engine']}:{r['voice']} | ОШИБКА | | | | {r['error']} |")
            else:
                md.append(f"| {r['n']} | {r['engine']}:{r['voice']} | {r.get('f0_raw')} → {r.get('f0')} | "
                          f"{r.get('range_st')} | {r.get('hnr')} | {r.get('clear')}% | {r.get('heard')} |")
        md.append("")
    open(os.path.join(OUT, "report.md"), "w", encoding="utf-8").write("\n".join(md))


if __name__ == "__main__":
    main()
