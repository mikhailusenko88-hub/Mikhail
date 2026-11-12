"""Слух, часть 3: сводит ответы сетей + свой разбор мелодии и звука в отчёт out/<имя>.md, картинку out/<имя>.png
и общую таблицу out/summary.md. Запуск: python ear_report.py todo.txt"""
import glob
import json
import math
import os
import subprocess
import sys

import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.family"] = "DejaVu Sans"
NOTE = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def nn(midi):
    midi = int(round(midi))
    return f"{NOTE[midi % 12]}{midi // 12 - 1}"


def load(path, sr=44100):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)
    return x


def runs(mask):
    """[(начало, конец)) непрерывных участков True"""
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


# ------------------------------------------------------------------ мелодия: подъезды, вибрато, «всхлипы»
def melody_stats(hz, hop):
    """hz — линия главной мелодии (0 = тишина), hop — шаг в секундах.
    Ноты ищутся округлением до полутона с гистерезисом 0,65: вибрато до ±0,5 и подъезды не дробят ноту."""
    from scipy.signal import butter, sosfiltfilt
    hz = np.asarray(hz, float)
    out = {}
    v = hz > 30
    if v.sum() * hop < 3:
        return {"voiced_s": round(float(v.sum() * hop), 1)}
    st = np.where(v, 12 * np.log2(np.maximum(hz, 1) / 440) + 69, np.nan)
    k60 = max(3, int(0.06 / hop) | 1)
    for a, b in runs(v):
        if (b - a) * hop < 0.12:
            v[a:b] = False
            continue
        st[a:b] = median_filter(st[a:b], k60, mode="nearest")      # срезать октавные срывы
    st = np.where(v, st, np.nan)
    sv = st[v]
    off = float(np.angle(np.mean(np.exp(2j * np.pi * (sv - np.round(sv))))) / (2 * np.pi))   # строй относительно 440
    out["tuning_cents"] = int(round(off * 100))
    q = np.full(len(st), np.nan)
    for a, b in runs(v):
        cur = round(st[a] - off)
        for i in range(a, b):
            if abs(st[i] - off - cur) > 0.65:
                cur = round(st[i] - off)
            q[i] = cur
    out["voiced_s"] = round(float(v.sum() * hop), 1)
    notes = []
    for a, b in runs(v):
        i = a
        while i < b:
            j = i
            while j < b and q[j] == q[i]:
                j += 1
            notes.append([i, j, float(q[i]) + off])
            i = j
    notes = [n for n in notes if (n[1] - n[0]) * hop >= 0.09]
    out["notes"] = len(notes)
    # вибрато: полоса 3–9 Гц на нотах длиннее 0,6 с
    sos = butter(2, [3.0, 9.0], btype="band", fs=1 / hop, output="sos")
    amps, rates = [], []
    for a, b, p in notes:
        a2, b2 = a + int(0.12 / hop), b - int(0.05 / hop)
        if (b2 - a2) * hop < 0.5:
            continue
        r = st[a2:b2] - p
        bp = sosfiltfilt(sos, r - np.polyval(np.polyfit(np.arange(len(r)), r, 1), np.arange(len(r))))
        amps.append(float(np.percentile(np.abs(bp), 90)))
        zc = np.sum(np.diff(np.sign(bp)) != 0) / 2 / ((b2 - a2) * hop)
        rates.append(float(zc))
    if amps:
        out["vibrato_st"] = round(float(np.median(amps)), 3)
        out["vibrato_max_st"] = round(float(np.percentile(amps, 90)), 3)
        out["vibrato_hz"] = round(float(np.median(rates)), 1)
        out["vibrato_notes"] = len(amps)
    if len(notes) < 3:
        return out
    pitches = np.array([n[2] for n in notes])
    lens = np.array([(n[1] - n[0]) * hop for n in notes])
    out["range"] = [nn(np.percentile(pitches, 10, method="nearest")), nn(np.median(pitches)), nn(np.percentile(pitches, 90, method="nearest"))]
    out["p90_midi"] = round(float(np.percentile(pitches, 90)), 1)
    out["median_note_s"] = round(float(np.median(lens)), 2)
    reach, scoops, n_sc, ups, downs, sighs, leaps_up = [], 0, 0, 0, 0, 0, 0
    W = int(0.25 / hop)
    for i in range(1, len(notes)):
        a0, b0, p0 = notes[i - 1]
        a1, b1, p1 = notes[i]
        iv = p1 - p0
        legato = (a1 - b0) * hop < 0.5 and bool(np.all(v[b0:a1 + 1]))
        if abs(iv) >= 0.6:
            ups += iv > 0
            downs += iv < 0
            sighs += (-2.6 < iv < -0.6)
            leaps_up += iv >= 4.5
        if legato and abs(iv) >= 0.6:
            # от ухода с прошлой ноты (дальше 0,3) до прихода на новую (ближе 0,2)
            k = a1 - 1
            while k > a0 and abs(st[k] - p0) > 0.3:
                k -= 1
            j = a1
            while j < b1 and abs(st[j] - p1) > 0.2:
                j += 1
            reach.append((j - k) * hop)
        # подъезд снизу: новая нота начинается ниже себя, хотя пришли сверху, с той же ноты или из тишины
        if not legato or iv < 0.6:
            n_sc += 1
            head = st[a1:min(b1, a1 + W)]
            if len(head) > 4 and np.nanmin(head[: max(3, len(head) * 3 // 4)]) < p1 - 0.25:
                scoops += 1
    n_iv = max(1, ups + downs)
    out["transition_ms"] = int(round(float(np.median(reach)) * 1000)) if reach else None
    out["slow_transitions"] = round(float(np.mean(np.array(reach) > 0.12)), 2) if reach else None
    out["scoop_share"] = round(scoops / max(1, n_sc), 2)
    out["up_share"] = round(ups / n_iv, 2)
    out["sigh_share"] = round(sighs / n_iv, 2)
    out["leap_up_share"] = round(leaps_up / n_iv, 2)
    dev = np.ones(len(st))
    for a, b, p in notes:
        dev[a:b] = np.abs(st[a:b] - p)
    out["glide_share"] = round(float(np.mean(dev[v] > 0.5)), 2)
    out["_notes"] = [[round(n[0] * hop, 2), round(n[1] * hop, 2), round(n[2], 2)] for n in notes]
    return out


# ------------------------------------------------------------------ звук: полосы, яркость, щелчки, стерео
def sound_stats(x, sr=44100):
    mono = x.mean(1)
    n = 4096
    hopn = 2048
    frames = np.lib.stride_tricks.sliding_window_view(mono, n)[::hopn] * np.hanning(n)
    S = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    tot = S.sum(1) + 1e-12
    loud = tot > np.percentile(tot, 30)
    bands = {"суб <60": (20, 60), "бас 60–250": (60, 250), "низ-сер 250–500": (250, 500), "середина 0,5–2к": (500, 2000),
             "присутствие 2–5к": (2000, 5000), "верх 5–10к": (5000, 10000), "воздух >10к": (10000, 20000)}
    B = {}
    for k, (lo, hi) in bands.items():
        e = S[:, (f >= lo) & (f < hi)].sum(1)
        B[k] = round(float(10 * np.log10(e[loud].sum() / tot[loud].sum() + 1e-12)), 1)
    cen = (S * f).sum(1) / tot
    out = {"bands_db": B, "centroid_hz": int(np.median(cen[loud]))}
    # щелчки: короткие всплески самых высоких частот
    hp = np.diff(mono, 2)
    e = uniform_filter1d(hp ** 2, 64)[::64]
    base = median_filter(e, 151) + 1e-12
    ratio = e / base
    iso = (ratio[:-3] > 40) & (ratio[3:] < 4) & (e[:-3] > 1e-8)
    out["clicks"] = int(np.sum(np.diff(iso.astype(int)) == 1))
    L, R = x[:, 0], x[:, 1]
    out["stereo_corr"] = round(float(np.corrcoef(L, R)[0, 1]), 2)
    out["clip_samples"] = int(np.sum(np.abs(x) > 0.999))
    return out, S, f, cen


def noise_stats(x, sr=44100):
    """шипение: «пол» спектра между гармониками (20-й перцентиль по частотам) в 6–16 кГц относительно всей энергии кадра;
    треск: короткие (≤3 мс) всплески высоких частот в 6+ раз выше местного фона"""
    mono = x.mean(1)
    n, hop = 2048, 1024
    fr = np.lib.stride_tricks.sliding_window_view(mono, n)[::hop] * np.hanning(n)
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    tot = S.sum(1) + 1e-15
    loud = 10 * np.log10(tot) > 10 * np.log10(tot.max()) - 35
    out = {}
    for lo, hi in ((3000, 6000), (6000, 16000)):
        b = (f >= lo) & (f < hi)
        fl = np.percentile(S[:, b], 20, axis=1) * b.sum()
        db = 10 * np.log10(fl / tot + 1e-15)
        out[f"floor_{lo // 1000}_{hi // 1000}k"] = round(float(np.median(db[loud])), 1)
        out[f"floor_{lo // 1000}_{hi // 1000}k_p90"] = round(float(np.percentile(db[loud], 90)), 1)
    hp = np.diff(mono, 2)
    e = uniform_filter1d(hp ** 2, 44)[::44]
    base = median_filter(e, 101) + 1e-15
    r = e / base
    tick = (r[1:-3] > 6) & (r[:-4] < 2.5) & (r[4:] < 2.5) & (e[1:-3] > 1e-9)
    out["ticks_per_s"] = round(float(tick.sum() / (len(mono) / sr)), 2)
    return out


def abs_noise(path, x, sr=44100):
    """шум, как его слышит человек на большой громкости: доля верхов 5–16 кГц (вступление и весь трек),
    абсолютный «пол» между гармониками 4–8 и 8–16 кГц в дБFS, тишина в начале, кодек файла"""
    db = lambda v: 10 * np.log10(v + 1e-20)  # noqa: E731
    mono = x.mean(1)
    on = np.where(np.abs(mono) > 1e-4)[0]
    s0 = int(on[0]) if len(on) else 0
    n, hop = 4096, 2048
    fr = np.lib.stride_tricks.sliding_window_view(mono[s0:], n)[::hop] * np.hanning(n)
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2 / (n * n / 4) * 2 / 1.5
    f = np.fft.rfftfreq(n, 1 / sr)
    tot = S.sum(1)
    hf = S[:, (f >= 5000) & (f < 16000)].sum(1)
    k6 = max(2, int(6 * sr / hop))
    loud = db(tot) > db(tot.max()) - 40
    out = {"hf_intro": round(float(db(hf[:k6].sum() / tot[:k6].sum())), 1), "hf_all": round(float(db(hf[loud].sum() / tot[loud].sum())), 1)}
    for lo, hi in ((4000, 8000), (8000, 16000)):
        b = (f >= lo) & (f < hi)
        fl = db(np.percentile(S[:, b], 20, axis=1) * b.sum())
        out[f"floor{lo // 1000}_{hi // 1000}_intro"] = round(float(np.median(fl[:k6])), 1)
        out[f"floor{lo // 1000}_{hi // 1000}_all"] = round(float(np.median(fl[loud])), 1)
    try:
        out["codec"] = subprocess.run(["ffprobe", "-v", "quiet", "-select_streams", "a:0", "-show_entries", "stream=codec_name,bits_per_raw_sample",
                                       "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        out["codec"] = "?"
    return out


def purity(x, sr=44100):
    """чистота тембров: «плотность» спектра 1–8 кГц (0 = редкие чистые линии; больше 0,0005 = каша из призвуков
    расстроенных голосов — слышна как треск и шипение), доли энергии ниже 60 Гц и в полосах 4–8 и 8–16 кГц"""
    mono = x.mean(1)
    n = 8192
    fr = np.lib.stride_tricks.sliding_window_view(mono, n)[::4096] * np.hanning(n)
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    P = S.mean(0)
    tot = P.sum() + 1e-30
    db = lambda lo, hi: round(float(10 * np.log10(P[(f >= lo) & (f < hi)].sum() / tot + 1e-20)), 1)  # noqa: E731
    b = (f >= 1000) & (f < 8000)
    act = S.sum(1) > 0.01 * S.sum(1).max()
    p = S[act][:, b] + 1e-20
    dens = float(np.median(np.exp(np.log(p).mean(1)) / p.mean(1)))
    return {"density": round(dens, 5), "sub60": db(20, 60), "b60_120": db(60, 120), "b4_8k": db(4000, 8000), "b8_16k": db(8000, 16000)}


def merge_chords(ch, hop):
    seq = []
    for i, c in enumerate(ch):
        if seq and seq[-1][0] == c:
            seq[-1][2] = (i + 1) * hop
        else:
            seq.append([c, i * hop, (i + 1) * hop])
    return seq


def minor_share(ch):
    if not ch:
        return None
    mi = sum(1 for c in ch if c.endswith("m"))
    return round(mi / len(ch), 2)


def top(classes, mean, k):
    o = np.argsort(mean)[::-1][:k]
    return [(classes[i], mean[i]) for i in o]


def pick(heads, name, cls):
    h = heads.get(name, {})
    if "classes" not in h:
        return None
    try:
        return h["mean"][h["classes"].index(cls)]
    except ValueError:
        return None


def clip01(x):
    return float(min(1.0, max(0.0, x)))


def indices(ml, cl, mel, mshare):
    heads = ml.get("heads", {})
    cry, light = [], []
    s = pick(heads, "mood_sad", "sad")
    if s is not None:
        cry.append(("сеть «грусть»", s))
    h = pick(heads, "mood_happy", "happy")
    if h is not None:
        light.append(("сеть «радость»", h))
    em = heads.get("emomusic", {})
    if "mean" in em:
        val = em["mean"][0]
        light.append(("валентность (1–9)", clip01((val - 3.5) / 3)))
        cry.append(("низкая валентность", clip01((5.5 - val) / 3)))
    if cl and cl["sets"]["настроение"].get("logit_spread", 1) > 0.05:
        mood = cl["sets"]["настроение"]
        d = dict(zip(mood["labels"], mood["mean"]))
        cry.append(("CLAP плач+меланхолия", clip01((d["плач, скорбь"] + d["меланхолия"]) / 0.45)))
        light.append(("CLAP надежда+радость+вдохн.+эпика",
                      clip01((d["надежда, светлое"] + d["радость"] + d["вдохновение"] + d["эпика, триумф"]) / 0.55)))
        vo = dict(zip(cl["sets"]["голос"]["labels"], cl["sets"]["голос"]["mean"]))
        cry.append(("CLAP голос плачет/воет", clip01(vo["голос плачет/воет"] / 0.4)))
    if mshare is not None:
        cry.append(("доля минорных аккордов", mshare))
        light.append(("доля мажорных аккордов", 1 - mshare))
    if mel.get("notes", 0) >= 3:
        cry.append(("подъезды к нотам", clip01(mel["scoop_share"] / 0.5)))
        cry.append(("скольжения (портаменто)", clip01(mel["glide_share"] / 0.3)))
        if "vibrato_st" in mel:
            cry.append(("глубина вибрато", clip01((mel["vibrato_st"] - 0.1) / 0.3)))
        if mel.get("slow_transitions") is not None:
            cry.append(("медленные переходы", mel["slow_transitions"]))
        cry.append(("«вздохи» вниз на 1–2 полутона", clip01(mel["sigh_share"] / 0.6)))
        light.append(("ходы мелодии вверх", clip01(mel["up_share"] / 0.6)))
    ci = round(100 * np.mean([v for _, v in cry])) if cry else None
    li = round(100 * np.mean([v for _, v in light])) if light else None
    return ci, li, cry, light


def report(path):
    name = os.path.splitext(os.path.basename(path))[0]
    ml = json.load(open(f"out/{name}.ml.json")) if os.path.exists(f"out/{name}.ml.json") else {}
    cl = json.load(open(f"out/{name}.clap.json")) if os.path.exists(f"out/{name}.clap.json") else None
    x = load(path)
    snd, S, f, cen = sound_stats(x)
    nz = noise_stats(x)
    an = abs_noise(path, x)
    pu = purity(x)
    mel = melody_stats(ml["melody_hz"], ml["melody_hop_s"]) if "melody_hz" in ml else {}
    chords = ml.get("chords", [])
    mshare = minor_share(chords)
    ci, li, cry, light = indices(ml, cl, mel, mshare)
    heads = ml.get("heads", {})
    L = [f"# {name}", ""]
    if "fatal" in ml:
        L += ["Сбой анализа сетями:", "```", ml["fatal"], "```"]
    L.append(f"Длина {ml.get('duration', round(len(x) / 44100, 1))} с · темп {ml.get('bpm')} уд/мин · громкость {ml.get('lufs')} LUFS "
             f"(разброс {ml.get('lra')} LU) · пик {ml.get('true_peak_dbfs')} дБFS")
    L.append("")
    L.append(f"**Плач-индекс: {ci}**  ·  **Свет-индекс: {li}**  (0–100; ориентир по уху Михаила: «Свобода» v1 «немного плачущий» — плач 34 / свет 56, «Рассвет A» — 21 / 61)")
    L.append("")
    L.append("| признак плача | 0–1 |   | признак света | 0–1 |")
    L.append("|---|---|---|---|---|")
    for i in range(max(len(cry), len(light))):
        a = cry[i] if i < len(cry) else ("", None)
        b = light[i] if i < len(light) else ("", None)
        fa = f"{a[1]:.2f}" if a[1] is not None else ""
        fb = f"{b[1]:.2f}" if b[1] is not None else ""
        L.append(f"| {a[0]} | {fa} |   | {b[0]} | {fb} |")
    L.append("")
    L.append("## Обученные сети (Essentia)")
    for nm, cls in (("mood_sad", "sad"), ("mood_happy", "happy"), ("mood_relaxed", "relaxed"), ("mood_aggressive", "aggressive"),
                    ("mood_acoustic", "acoustic"), ("mood_electronic", "electronic"), ("voice_instrumental", "voice"),
                    ("gender", "female"), ("tonal_atonal", "tonal")):
        p = pick(heads, nm, cls)
        if p is not None:
            L.append(f"- {nm} → {cls}: {p:.2f}")
        elif "error" in heads.get(nm, {}):
            L.append(f"- {nm}: ошибка {heads[nm]['error'][:120]}")
    for nm in ("emomusic", "deam"):
        h = heads.get(nm, {})
        if "mean" in h:
            L.append(f"- {nm}: валентность {h['mean'][0]:.2f}, возбуждение {h['mean'][1]:.2f} (шкала 1–9, середина 5)")
    for nm in ("approachability_regression", "engagement_regression"):
        h = heads.get(nm, {})
        if "mean" in h:
            L.append(f"- {nm.split('_')[0]}: {h['mean'][0]:.2f} (0–1)")
    for nm, k in (("mtg_jamendo_moodtheme", 10), ("mtg_jamendo_instrument", 8), ("mtg_jamendo_genre", 6)):
        h = heads.get(nm, {})
        if "mean" in h:
            L.append(f"- {nm.replace('mtg_jamendo_', '')}: " + ", ".join(f"{c} {p:.2f}" for c, p in top(h["classes"], h["mean"], k)))
    if cl:
        L.append("")
        L.append("## CLAP: на какое описание похоже (доли внутри набора)")
        for sname, d in cl["sets"].items():
            L.append(f"- {sname}: " + ", ".join(f"{c} {p:.2f}" for c, p in top(d["labels"], d["mean"], len(d["labels"]))))
        mood = cl["sets"]["настроение"]
        L.append("- по окнам (10 с): " + " | ".join(
            f"{int(t)}с {mood['labels'][int(np.argmax(p))]}" for t, p in zip(cl["win_start_s"], mood["series"])))
    L.append("")
    L.append("## Лад и аккорды")
    L.append("- тональность: " + ", ".join(f"{k}: {v[0]} {v[1]} ({v[2]})" for k, v in ml.get("key", {}).items()))
    if chords:
        hop = ml["chords_hop_s"]
        seq = [c for c in merge_chords(chords, hop) if c[2] - c[1] >= 1.0]
        L.append(f"- минорных аккордов по времени: {mshare:.0%}")
        L.append("- аккорды: " + " ".join(f"{c}({a:.0f})" for c, a, b in seq))
    if "dissonance" in ml:
        L.append(f"- шероховатость (диссонанс 0–0,5): {np.median(ml['dissonance']):.3f}")
    L.append("")
    L.append("## Главная мелодия (Melodia)")
    if mel:
        L.append(f"- звучит мелодия {mel.get('voiced_s')} с, нот {mel.get('notes')}, диапазон {mel.get('range')}, "
                 f"средняя нота {mel.get('median_note_s')} с")
        if mel.get("notes", 0) >= 3:
            L.append(f"- подъезды снизу: {mel['scoop_share']:.0%} нот (больше 30% — «всхлипывающая» манера)")
            L.append(f"- скольжения: {mel['glide_share']:.0%} времени мимо нот; приход на новую ноту {mel['transition_ms']} мс "
                     f"(медленных >120 мс: {mel['slow_transitions']}); строй {mel.get('tuning_cents')} центов")
            if "vibrato_st" in mel:
                L.append(f"- вибрато: ±{mel['vibrato_st']} полутона (у самых сильных нот ±{mel['vibrato_max_st']}), "
                         f"{mel['vibrato_hz']} Гц, нот с вибрато {mel['vibrato_notes']} (спокойное пение ±0,1–0,2; больше ±0,3 — дрожит, «плачет»)")
            L.append(f"- ходы вверх {mel['up_share']:.0%}, «вздохи» вниз на 1–2 полутона {mel['sigh_share']:.0%}, "
                     f"скачки вверх ≥ кварты {mel['leap_up_share']:.0%}")
    L.append("")
    L.append("## Звук")
    L.append("- полосы (дБ от общей энергии): " + ", ".join(f"{k} {v}" for k, v in snd["bands_db"].items()))
    L.append(f"- яркость (центроид): {snd['centroid_hz']} Гц · стерео-корреляция {snd['stereo_corr']} · "
             f"щелчков {snd['clicks']} · перегруз {snd['clip_samples']} сэмплов")
    L.append(f"- **шипение** (пол шума между гармониками, 6–16 кГц): {nz['floor_6_16k']} дБ, в громких местах до {nz['floor_6_16k_p90']} дБ; "
             f"3–6 кГц: {nz['floor_3_6k']} дБ · **треск**: {nz['ticks_per_s']} в секунду. Ориентир: Михаил услышал «шум как от пластинки» "
             f"при −53 дБ / до −29 дБ (шейкер, шум смычка, щелчки спиккато); чистый звук — ниже −60 дБ и до −45 дБ, треск < 0,05/с")
    L.append(f"- **чистота тембров**: плотность спектра 1–8 кГц {pu['density']:.5f}; ниже 60 Гц {pu['sub60']} дБ, 60–120 Гц {pu['b60_120']} дБ, "
             f"4–8 кГц {pu['b4_8k']} дБ, 8–16 кГц {pu['b8_16k']} дБ. Ориентир: Михаил слышал «треск» при плотности 0,0016–0,0024 и при 4–8 кГц −29 дБ "
             f"(яркий орган); чисто — плотность ≤ 0,0001, ниже 60 Гц ≤ −17 дБ, 4–8 кГц ≤ −33 дБ")
    L.append(f"- **шум на слух** (абсолютный): «пол» 4–8 кГц {an['floor4_8_intro']} дБFS во вступлении / {an['floor4_8_all']} весь трек; "
             f"8–16 кГц {an['floor8_16_intro']} / {an['floor8_16_all']}; доля верхов 5–16 кГц {an['hf_intro']} дБ во вступлении / {an['hf_all']} весь; "
             f"кодек {an['codec']}. Ориентир: при −65/−58 (4–8к) и −76/−79 (8–16к) Михаил слышал шипение на большой громкости; "
             f"чистый движок даёт −83/−77 и −116/−120. AAC сам добавляет шум около −65 дБFS — отдавать без потерь (ALAC)")
    open(f"out/{name}.md", "w").write("\n".join(L) + "\n")
    # ------------------------------------------------------------ картинка
    dur = len(x) / 44100
    fig, ax = plt.subplots(4, 1, figsize=(16, 13), sharex=True, gridspec_kw={"height_ratios": [3, 1.2, 1.3, 1.6]})
    tt = np.arange(S.shape[0]) * 2048 / 44100
    sel = (f > 40) & (f < 9000)
    ax[0].pcolormesh(tt, f[sel], 10 * np.log10(S[:, sel].T + 1e-10), shading="auto", cmap="magma",
                     vmin=10 * np.log10(S.max()) - 90)
    ax[0].set_yscale("log")
    ax[0].set_ylim(40, 9000)
    if "melody_hz" in ml:
        mh = np.array(ml["melody_hz"], float)
        mt = np.arange(len(mh)) * ml["melody_hop_s"]
        ax[0].plot(mt, np.where(mh > 30, mh, np.nan), color="cyan", lw=1.0)
    ax[0].set_title(f"{name} — {ml.get('key', {}).get('temperley', ['?', '?'])[:2]} · {ml.get('bpm')} уд/мин · "
                    f"{ml.get('lufs')} LUFS · плач {ci} / свет {li}")
    ax[0].set_ylabel("Гц (голубое — мелодия)")
    if "lufs_short" in ml:
        ls = np.array(ml["lufs_short"])
        ax[1].plot(np.arange(len(ls)) * 0.1, ls, color="k")
        ax[1].set_ylim(-40, -5)
    ax[1].set_ylabel("LUFS (3 с)")
    if chords:
        for c, a, b in merge_chords(chords, ml["chords_hop_s"]):
            if b - a >= 1.0:
                ax[1].text((a + b) / 2, -8, c, ha="center", fontsize=8, color="crimson" if c.endswith("m") else "navy")
    for nm, cls, col in (("mood_sad", "sad", "tab:blue"), ("mood_happy", "happy", "tab:orange"), ("mood_relaxed", "relaxed", "tab:green")):
        h = heads.get(nm, {})
        if "series" in h:
            s = np.array(h["series"])[:, h["classes"].index(cls)]
            ax[2].plot(np.linspace(0, dur, len(s)), uniform_filter1d(s, 3), color=col, label=cls)
    ax[2].set_ylim(0, 1)
    ax[2].legend(loc="upper right", fontsize=8)
    ax[2].set_ylabel("сети Essentia")
    if cl:
        mood = cl["sets"]["настроение"]
        ser = np.array(mood["series"])
        tc = np.array(cl["win_start_s"]) + 5
        for lab, col in (("плач, скорбь", "tab:blue"), ("меланхолия", "tab:purple"), ("надежда, светлое", "gold"),
                         ("эпика, триумф", "tab:red"), ("покой", "tab:green"), ("вдохновение", "tab:orange")):
            ax[3].plot(tc, ser[:, mood["labels"].index(lab)], "-o", ms=3, color=col, label=lab)
        ax[3].legend(loc="upper right", fontsize=8, ncol=3)
    ax[3].set_ylabel("CLAP настроение")
    ax[3].set_xlabel("секунды")
    ax[3].set_xlim(0, dur)
    plt.tight_layout()
    plt.savefig(f"out/{name}.png", dpi=70)
    plt.close(fig)
    J = {"cry_index": ci, "light_index": li, "noise": nz, "abs_noise": an, "purity": pu, "melody": {k: v for k, v in mel.items() if not k.startswith("_")},
         "sound": snd, "minor_share": mshare}
    json.dump(J, open(f"out/{name}.sum.json", "w"), ensure_ascii=False)
    return J


def summary():
    rows = ["| файл | с | лад | темп | LUFS | грусть | радость | валентн. | CLAP главное | плач | свет | подъезды | вибрато | шипение | треск/с | плотность | <60 Гц |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in sorted(glob.glob("out/*.ml.json")):
        name = os.path.basename(p)[:-8]
        ml = json.load(open(p))
        sm = json.load(open(f"out/{name}.sum.json")) if os.path.exists(f"out/{name}.sum.json") else {}
        cl = json.load(open(f"out/{name}.clap.json")) if os.path.exists(f"out/{name}.clap.json") else None
        heads = ml.get("heads", {})
        val = heads.get("emomusic", {}).get("mean", [None])[0]
        cm = ""
        if cl:
            mo = cl["sets"]["настроение"]
            cm = ", ".join(f"{c} {p:.2f}" for c, p in top(mo["labels"], mo["mean"], 2))
        key = ml.get("key", {}).get("temperley", ["?", "?"])
        mel = sm.get("melody", {})
        fmt = lambda v: "" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))  # noqa: E731
        rows.append(f"| {name} | {ml.get('duration')} | {key[0]} {key[1]} | {ml.get('bpm')} | {ml.get('lufs')} | "
                    f"{fmt(pick(heads, 'mood_sad', 'sad'))} | {fmt(pick(heads, 'mood_happy', 'happy'))} | {fmt(val)} | {cm} | "
                    f"{sm.get('cry_index')} | {sm.get('light_index')} | {fmt(mel.get('scoop_share'))} | {fmt(mel.get('vibrato_st'))} | "
                    f"{sm.get('noise', {}).get('floor_6_16k', '')} | {sm.get('noise', {}).get('ticks_per_s', '')} | "
                    f"{sm.get('purity', {}).get('density', '')} | {sm.get('purity', {}).get('sub60', '')} |")
    open("out/summary.md", "w").write("# Слух: сводка\n\n" + "\n".join(rows) + "\n")


def main():
    for line in open(sys.argv[1]):
        path = line.strip()
        if path:
            print("==", path, flush=True)
            try:
                report(path)
            except Exception:  # noqa: BLE001
                import traceback
                traceback.print_exc()
    summary()


if __name__ == "__main__":
    main()
