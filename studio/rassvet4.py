"""«Рассвет» — чистый движок и набор звучаний. Никаких источников шума: без дыхания, шейкера, тарелок, без
насыщения в мастере; струнные затемнены, реверберация с затуханием верхов; выход 24 бита.
Стили: main, epik, tihiy, sobor (орган и колокол), shkatulka (челеста), sovr (синт-подложка, суб-бас).
Планы: full (~65 с), kuplet (~26 с), raspev (~29 с).
python3 rassvet4.py <стиль> <план> <файл.wav>"""
import math
import subprocess
import sys
import wave

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import fftconvolve

import theme as th
from theme import SR, m, hz, legato_line, voice_lead, horn, timp, piano, compressor, strings
import cathedral as cat
from cathedral import line as cline, VOWEL_A, VOWEL_U, organ, bell
from svoboda import VOW

th.NOISE = 0.0          # смычок, молоточки, дыхание хора, «чифф» органа, шум литавр — выключены
rng = np.random.default_rng(76)
BEAT = 60 / 76
BAR = 4 * BEAT

H = {
    "F": ("F2", ["F3", "A3", "C4"]), "Bb/F": ("F2", ["F3", "Bb3", "D4"]), "C/E": ("E2", ["E3", "G3", "C4"]),
    "Dm": ("D2", ["D3", "F3", "A3"]), "Bb": ("Bb1", ["D3", "F3", "Bb3"]), "F/A": ("A1", ["F3", "A3", "C4"]),
    "Gm7": ("G1", ["F3", "Bb3", "D4"]), "C7": ("C2", ["E3", "Bb3", "C4"]),
}
PH = ["F", "C/E", "Dm", "Bb", "F/A", "Bb", "Gm7", "C7"]
VERSE = [
    [(0, 1, "C4", "o"), (1, 1, "F4", "a"), (2, 2, "A4", "o")],
    [(0, 1.5, "G4", "a"), (1.5, .5, "A4", "a"), (2, 1, "G4", "o"), (3, 1, "E4", "u")],
    [(0, 1, "F4", "o"), (1, 1, "A4", "a"), (2, 2, "D5", "o")],
    [(0, 1.5, "D5", "a"), (1.5, .5, "C5", "a"), (2, 2, "Bb4", "o")],
    [(0, 1.5, "A4", "o"), (1.5, .5, "Bb4", "a"), (2, 2, "C5", "a")],
    [(0, 2, "F5", "o"), (2, 1, "D5", "a"), (3, 1, "Bb4", "o")],
    [(0, 1.5, "C5", "a"), (1.5, .5, "Bb4", "a"), (2, 2, "G4", "o")],
    [(0, 1, "G4", "a"), (1, .5, "A4", "a"), (1.5, .5, "Bb4", "a"), (2, 2, "C5", "o")],
]
CAD = [(0, 1.5, "C5", "a"), (1.5, .5, "Bb4", "a"), (2, 1, "G4", "o"), (3, 1, "Bb4", "a")]
FIN = [(0, 4, "A4", "a")]
PHRASE_END = {3, 7, "cad"}

STY = {
    #          подложка      громкость подложки по разделам   перебор        ударные     спиккато  валторны  скрипки  хор   второй голос
    "main": dict(pad="str", pv=(0.07, 0.09, 0.14, 0.11), arp="harp", drums="frame", spic=1, horns=0.07, viol=0.18, choir=0.0, harm=True),
    "epik": dict(pad="str", pv=(0.08, 0.10, 0.15, 0.12), arp="harp", drums="taiko", spic=2, horns=0.11, viol=0.21, choir=0.45, harm=True),
    "tihiy": dict(pad="str", pv=(0.05, 0.06, 0.08, 0.08), arp="piano", drums=None, spic=0, horns=0.0, viol=0.10, choir=0.0, harm=False),
    "sobor": dict(pad="organ", pv=(0.05, 0.06, 0.085, 0.07), arp="harp_soft", drums="timp", spic=0, horns=0.05, viol=0.12, choir=0.5, harm=True),
    "shkatulka": dict(pad="str", pv=(0.04, 0.05, 0.065, 0.06), arp="celesta", drums=None, spic=0, horns=0.0, viol=0.0, choir=0.0, harm=False),
    "sovr": dict(pad="synth", pv=(0.05, 0.06, 0.085, 0.07), arp="pluck", drums="kick", spic=0, horns=0.0, viol=0.12, choir=0.0, harm=True),
}


def plan(name):
    if name == "full":
        return ([("F", None, "intro"), ("Bb/F", None, "intro")] + [(PH[i], i, "verse") for i in range(8)]
                + [(PH[i], i, "climax") for i in range(8)] + [("F", "fin", "end")])
    if name == "kuplet":
        return ([(PH[i], i, "verse") for i in range(3)] + [(PH[4], 4, "climax"), (PH[5], 5, "climax"),
                (("Gm7", "C7"), "cad", "climax"), ("F", "fin", "end")])
    if name == "raspev":
        return [(PH[i], i, "climax") for i in range(6)] + [(("Gm7", "C7"), "cad", "climax"), ("F", "fin", "end")]
    raise ValueError(name)


def mel_of(k):
    return FIN if k == "fin" else CAD if k == "cad" else VERSE[k] if k is not None else []


def halves(ch):
    return [(ch[0], 0, 2), (ch[1], 2, 2)] if isinstance(ch, tuple) else [(ch, 0, 4)]


F_SCALE = [5, 7, 9, 10, 0, 2, 4]


def third_below(mi):
    pc = mi % 12
    if pc not in F_SCALE:
        return mi - 3
    t = F_SCALE[(F_SCALE.index(pc) - 2) % 7]
    return mi - (pc - t) % 12


# ---------------------------------------------------------------- голос: чистые гармоники, без дыхания
def voice(notes, vowels, vib=0.0055, vib_rate=5.0, vib_delay=0.45, glide=0.022, detune=0.0, seed=1):
    r = np.random.default_rng(seed)
    CR = 500
    t0 = notes[0][0] - 0.1
    t1 = notes[-1][1] + 1.2
    n = int((t1 - t0) * SR)
    nc = int((t1 - t0) * CR) + 2
    pitch = np.full(nc, float(notes[0][2]))
    amp = np.zeros(nc)
    since = np.zeros(nc)
    vix = np.zeros(nc, dtype=int)
    names = list(VOW)
    for i, (a, b, mi, v) in enumerate(notes):
        s0 = int((a - t0) * CR)
        nxt = notes[i + 1][0] if i + 1 < len(notes) else b
        s1 = int((nxt - t0) * CR)
        se = int((b - t0) * CR) if nxt - b > 0.04 else s1
        pitch[s0:s1] = mi
        amp[s0:se] = v
        since[s0:s1] = np.arange(s1 - s0) / CR
        vix[s0:s1] = names.index(vowels[i])
    sl = int((notes[-1][1] - t0) * CR)
    pitch[sl:] = notes[-1][2]
    since[sl:] = since[sl - 1] + np.arange(nc - sl) / CR
    lp = gaussian_filter1d(pitch, glide * CR) + detune / 100
    lp += gaussian_filter1d(r.normal(0, 1, nc), 0.25 * CR) * 0.6
    tc = np.arange(nc) / CR + t0
    vibr = vib * np.clip((since - vib_delay) / 0.6, 0, 1) * np.sin(2 * np.pi * vib_rate * tc + r.uniform(0, 6.28) + 0.2 * np.sin(2 * np.pi * 0.3 * tc))
    f0c = 440.0 * 2 ** ((lp - 69) / 12) * np.exp(vibr)
    amp = gaussian_filter1d(amp, 0.06 * CR)
    env = np.clip((tc - notes[0][0] + 0.1) / 0.3, 0, 1) * np.clip((t1 - tc) / 1.1, 0, 1) ** 1.3
    amp = amp * env * (0.92 + 0.08 * np.clip(since / 0.8, 0, 1))
    W = np.zeros((len(names), nc))
    W[vix, np.arange(nc)] = 1
    W = gaussian_filter1d(W, 0.09 * CR, axis=1)
    W /= W.sum(0, keepdims=True) + 1e-9
    xa = np.arange(n) / SR * CR
    # управляющие кривые растягиваются гладко (кубически), чтобы не было «ступенек» 500 Гц
    from scipy.interpolate import CubicSpline
    xc = np.arange(nc)
    up = lambda c: CubicSpline(xc, c)(xa)  # noqa: E731
    ph = 2 * np.pi * np.cumsum(up(f0c)) / SR
    AH = []
    for h in range(1, 31):
        fh = f0c * h
        g = np.zeros(nc)
        for k, nm in enumerate(names):
            g += W[k] * (0.03 + sum(a * np.exp(-((fh - c) / w) ** 2) for c, a, w in VOW[nm]))
        tilt = 1.25 + 0.6 * np.clip((f0c - 500) / 300, 0, 1)
        AH.append(g * (1.0 / h ** tilt) * np.exp(-fh / 6000) * np.clip((9000 - fh) / 1500, 0, 1))
    P = gaussian_filter1d(np.sqrt(sum(a * a for a in AH)) + 1e-9, 0.05 * CR)
    out = np.zeros(n)
    for h, a_h in enumerate(AH, start=1):
        if a_h.any():
            out += up(a_h / P * 0.6) * np.sin(h * ph + 0.5 * h + r.uniform(0, 0.3))
    return np.maximum(up(amp), 0) * out / 2.2, t0


# ---------------------------------------------------------------- чистые инструменты
def _att(t, ms):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(t / (ms / 1000), 0, 1))       # плавный вход без ступеньки


def harp(midi, vel):
    f0 = hz(midi)
    n = int(3.2 * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for h in range(1, 9):
        fh = f0 * h
        if fh > 7000:
            break
        s += (1 / h ** 1.2) * np.sin(2 * np.pi * fh * t + (rng.uniform(0, 6.28) if h > 1 else 0)) * np.exp(-t * (0.9 + 1.4 * h) * (f0 / 300) ** 0.3)
    return vel * s * _att(t, 6) * np.clip((3.2 - t) / 0.3, 0, 1)


def celesta(midi, vel):
    f0 = hz(midi)
    n = int(3.5 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f0 * t) * np.exp(-t * 1.3)
    if f0 * 4.01 < 9000:
        s += 0.35 * np.sin(2 * np.pi * f0 * 4.01 * t + 1.0) * np.exp(-t * 5)
    if f0 * 6.8 < 9000:
        s += 0.12 * np.sin(2 * np.pi * f0 * 6.8 * t + 2.0) * np.exp(-t * 9)
    return vel * s * _att(t, 4) * np.clip((3.5 - t) / 0.3, 0, 1)


def short(midi, vel, dur=0.16):
    return strings(midi, dur, vel, voices=2, att=0.014, rel=0.09, bright=0.6, vib=0.0)


def fdrum(vel, low=True):
    """рамочный барабан без шумовой «кожи»: тон с быстрым спадом высоты и два призвука мембраны"""
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = (68 if low else 120) * (1 + 0.35 * np.exp(-t / 0.03))
    ph = 2 * np.pi * np.cumsum(f) / SR
    d = 0.32 if low else 0.15
    s = np.sin(ph) * np.exp(-t / d) + 0.22 * np.sin(1.59 * ph + 1) * np.exp(-t / (d * 0.35)) + 0.10 * np.sin(2.14 * ph + 2) * np.exp(-t / (d * 0.2))
    return vel * s * _att(t, 4)


def taiko(vel):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    f = 52 * (1 + 0.6 * np.exp(-t / 0.025))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t / 0.45) + 0.3 * np.sin(1.59 * ph + 1) * np.exp(-t / 0.12) + 0.15 * np.sin(2.3 * ph) * np.exp(-t / 0.06)
    return vel * s * _att(t, 5)


def kick(vel):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 46 + 70 * np.exp(-t / 0.035)
    return vel * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16) * _att(t, 4)


def sub(midi, dur, vel):
    n = int((dur + 0.25) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    s = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t) + 0.06 * np.sin(6 * np.pi * f * t)
    return vel * s * np.minimum(1, t / 0.03) * np.clip((dur + 0.25 - t) / 0.25, 0, 1)


def pluck(midi, vel):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    s = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.22) + 0.4 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.12) + 0.15 * np.sin(6 * np.pi * f * t) * np.exp(-t / 0.07)
    return vel * s * _att(t, 6)


def spad(midi, dur, vel):
    """мягкая синт-подложка: 4 расстроенных голоса, 6 гармоник, медленная атака"""
    n = int((dur + 1.6) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    s = np.zeros(n)
    for det in (-9, -3, 4, 8):
        fd = f * 2 ** (det / 1200)
        p0 = rng.uniform(0, 6.28)
        for h in range(1, 7):
            s += np.sin(2 * np.pi * fd * h * t + p0 * h) / h ** 1.7
    e = np.clip(t / 0.7, 0, 1) ** 1.3 * np.clip((dur + 1.6 - t) / 1.6, 0, 1) ** 1.3
    return vel * s * e / 4


def shimmer(dur, vel):
    """взлёт перед кульминацией: высокие ноты фа мажора нарастают и гаснут (вместо шумовой тарелки)"""
    n = int((dur + 1.2) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k, nt in enumerate(("F5", "C6", "F6", "A6", "C7")):
        f = hz(m(nt))
        for det in (-4, 4):
            s += np.sin(2 * np.pi * f * 2 ** (det / 1200) * t + k) / (1 + 0.4 * k)
    e = np.where(t < dur, (t / dur) ** 3, np.exp(-(t - dur) / 0.35))
    return vel * 0.35 * s * e


# ---------------------------------------------------------------- мастеринг без искажений
def hall_dark(seed, rt_low=2.7, rt_high=1.0, pre=0.022, length=3.6):
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    nz = r.normal(0, 1, n)
    low = gaussian_filter1d(nz, 3.0)
    high = gaussian_filter1d(nz - low, 1.3)                  # поглощение верхов в воздухе
    tail = low * 2.2 * np.exp(-t * 6.9 / rt_low) + high * 0.75 * np.exp(-t * 6.9 / rt_high)
    tail *= np.clip((t - pre) / 0.04, 0, 1)
    tail *= np.clip((length - t) / 0.5, 0, 1)                  # хвост сходит в ноль без обрыва
    er = np.zeros(n)
    for d, g in ((0.011, .5), (0.019, .42), (0.027, .35), (0.036, .3), (0.049, .26), (0.061, .22), (0.077, .18)):
        er[int((d + r.uniform(-0.002, 0.002)) * SR)] += g * r.choice([-1, 1])
    ir = tail + gaussian_filter1d(er, 1.0) * 3
    return ir / np.sqrt(np.sum(ir ** 2))


def master(bus, air=0.3):
    irL, irR = hall_dark(11), hall_dark(23)
    L = bus.L + 0.55 * fftconvolve(bus.sL + 0.35 * bus.sR, irL)[:len(bus.L)]
    R = bus.R + 0.55 * fftconvolve(bus.sR + 0.35 * bus.sL, irR)[:len(bus.R)]
    out = []
    for ch in (L, R):
        ch = ch - gaussian_filter1d(ch, SR / (2 * math.pi * 30))
        band = gaussian_filter1d(ch, SR / (2 * math.pi * 450)) - gaussian_filter1d(ch, SR / (2 * math.pi * 150))
        ch = ch - 0.22 * band
        hi = ch - gaussian_filter1d(ch, SR / (2 * math.pi * 4500))
        out.append(ch + air * hi)
    L, R = out
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = compressor(L / pk, R / pk, thr_db=-15, ratio=1.8)      # плавное усиление, без насыщения
    fi = int(0.03 * SR)
    for ch in (L, R):
        ch[:fi] *= np.linspace(0, 1, fi)
    return L, R


def lufs(path):
    o = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = [float(x.split("I:")[1].split()[0]) for x in o.splitlines() if x.strip().startswith("I:")][-1]
    return I


def write24(path, L, R):
    st = np.empty(2 * len(L))
    st[0::2], st[1::2] = L, R
    a = np.round(np.clip(st, -1, 1) * 8388607).astype("<i4")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(3)
        wf.setframerate(SR)
        wf.writeframes(a.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())


# ---------------------------------------------------------------- аранжировка
def compose(style, plan_name):
    S = STY[style]
    P = plan(plan_name)
    pre = 0.8 if plan_name == "raspev" else 0.3
    nb = len(P)

    def bt(b, x=0.0):
        return pre + b * BAR + x * BEAT

    fin_b = nb - 1
    hold = 1.15 * BAR if plan_name == "full" else 1.25 * BAR
    end_t = bt(fin_b) + hold
    th.TOTAL = end_t + 6
    bus = th.Bus()
    LV = {"intro": 0, "verse": 1, "climax": 2, "end": 3}
    secs = [s for _, _, s in P]
    # ---------- мелодия: голос двумя дублями
    lead = []
    for b, (ch, mk, sec) in enumerate(P):
        for x, d, nt, vw in mel_of(mk):
            lead.append([bt(b, x) - 0.02, end_t if mk == "fin" else bt(b, x + d), m(nt), vw, b, sec])
    for i in range(len(lead) - 1):
        b0, b1 = lead[i][4], lead[i + 1][4]
        if b1 != b0 and (P[b0][1] in PHRASE_END or P[b0][2] != P[b1][2]):
            lead[i][1] -= 0.30
    lv = {"verse": 0.42, "climax": 0.58, "end": 0.48}
    if style in ("tihiy", "shkatulka"):
        lv = {"verse": 0.44, "climax": 0.52, "end": 0.46}
    notes = [(a, e, mi, lv[sec]) for a, e, mi, vw, b, sec in lead]
    vows = [vw for a, e, mi, vw, b, sec in lead]
    sig, ts = voice(notes, vows, seed=11)
    bus.add(sig, ts, pan=-0.08, send=0.34, gain=1.2)
    sig, ts = voice(notes, vows, seed=29, detune=6, vib=0.005)
    bus.add(sig, ts + 0.019, pan=0.1, send=0.38, gain=0.62)
    harm = [(a, e, third_below(mi), lv[sec] * 0.62) for a, e, mi, vw, b, sec in lead if sec == "climax"]
    if harm and S["harm"]:
        sig, ts = voice(harm, ["o"] * len(harm), seed=47, vib=0.004)
        bus.add(sig, ts + 0.01, pan=0.22, send=0.42, gain=0.75)
    vc = [(a, e, mi - 12, 0.09) for a, e, mi, vw, b, sec in lead if sec == "verse"]
    if vc and style != "sovr":
        sig, ts = legato_line(vc, voices=3, att=0.4, rel=1.0, bright=0.55, vib=0.004, glide=0.03, noise=0)
        bus.add(sig, ts, pan=0.25, send=0.3)
    # ---------- кульминация: скрипки октавой выше, валторны, челеста в «Шкатулке»
    vn = [(a, e, mi + 12, S["viol"]) for a, e, mi, vw, b, sec in lead if sec == "climax"]
    if vn and S["viol"]:
        sig, ts = legato_line(vn, voices=8, att=0.3, rel=2.0, bright=0.62, vib=0.0038, glide=0.022, noise=0)
        bus.add(sig, ts, pan=-0.3, send=0.34)
    for a, e, mi, vw, b, sec in lead:
        if sec == "climax" and S["horns"]:
            bus.add(horn(mi, e - a + 0.05, S["horns"]), a + 0.01, pan=0.25, send=0.45)
            if style == "epik":
                bus.add(horn(mi - 12, e - a + 0.05, S["horns"] * 0.7), a + 0.01, pan=0.3, send=0.45)
        if style == "shkatulka" and sec in ("climax", "end"):
            bus.add(celesta(mi + 24, 0.045), a + 0.02, pan=0.3, send=0.5)
    # ---------- гармония
    segs = []
    for b, (ch, mk, sec) in enumerate(P):
        for c, x, d in halves(ch):
            segs.append([bt(b, x), bt(b, x + d), c, sec, b, x])
    segs[-1][1] = end_t
    bv = {0: 0.19, 1: 0.21, 2: 0.27, 3: 0.20}
    if style == "sovr":
        for a, e, c, sec, b, x in segs:
            bus.add(sub(m(H[c][0]) + (12 if m(H[c][0]) < m("C2") else 0), e - a, bv[LV[sec]] * 1.1), a, pan=0.0, send=0.05)
    elif S["pad"] == "organ":
        for a, e, c, sec, b, x in segs:
            bus.add(organ(m(H[c][0]) + 12, e - a + 0.1, bv[LV[sec]] * 0.55, stops=("16", "8"), rel=0.6), a, pan=0.0, send=0.5)
    else:
        bl = [(a, e, m(H[c][0]) + 12, bv[LV[sec]]) for a, e, c, sec, b, x in segs]
        sig, ts = legato_line(bl, voices=5, att=0.9, rel=2.5, bright=0.42, vib=0.003, glide=0.05, noise=0)
        bus.add(sig, ts, pan=0.25, send=0.3)
        bl2 = [(a, e, mi - 12, v * (0.8 if style != "epik" else 1.0)) for (a, e, mi, v), s in zip(bl, segs) if s[3] in ("climax", "end")]
        if bl2 and style not in ("tihiy", "shkatulka"):
            sig, ts = legato_line(bl2, voices=4, att=0.8, rel=2.5, bright=0.4, vib=0.002, glide=0.05, noise=0)
            bus.add(sig, ts, pan=0.2, send=0.25)
    voicing = [m("A3"), m("C4"), m("F4")]
    lines = [[], [], []]
    for a, e, c, sec, b, x in segs:
        voicing = voice_lead(voicing, H[c][1], m("E3"), m("D5"))
        for k in range(3):
            lines[k].append((a, e, voicing[k], S["pv"][LV[sec]]))
    for k in range(3):
        if S["pad"] == "str":
            sig, ts = legato_line(lines[k], voices=5, att=1.3, rel=2.5, bright=0.32, vib=0.004, glide=0.07, noise=0)
            bus.add(sig, ts + 0.04 * k, pan=-0.35 + 0.3 * k, send=0.34)
        elif S["pad"] == "organ":
            for (a, e, mi, v), sg in zip(lines[k], segs):
                stops = ("8", "fl", "4") if sg[3] in ("climax", "end") else ("8", "fl")
                bus.add(organ(mi, e - a + 0.1, v * 1.5, stops=stops, rel=0.7), a, pan=-0.3 + 0.3 * k, send=0.6)
        else:
            for a, e, mi, v in lines[k]:
                bus.add(spad(mi, e - a, v * 1.3), a - 0.1, pan=-0.4 + 0.4 * k, send=0.4)
                if k == 2:
                    bus.add(spad(mi + 12, e - a, v * 0.5), a - 0.1, pan=0.3, send=0.45)
    if S["pad"] == "str":
        sig, ts = legato_line([(bt(fin_b), end_t, m("G4"), 0.06)], voices=5, att=1.5, rel=2.5, bright=0.35, vib=0.004, noise=0)
        bus.add(sig, ts, pan=-0.2, send=0.5)
    # ---------- перебор восьмыми
    for a, e, c, sec, b, x in segs:
        if sec == "end":
            continue
        bass, tones = H[c]
        nst = int(round((e - a) / (BEAT / 2)))
        off = int(x * 2)
        arp = "piano" if (sec == "intro" and S["arp"] in ("harp", "harp_soft")) else S["arp"]
        if arp == "piano":
            r_ = m(bass) + 12
            while r_ < m("F3"):
                r_ += 12
            pcs = [m(t) % 12 for t in tones]
            up_ = sorted({t for t in range(m("C4"), m("C6")) if t % 12 in pcs})
            pat = [r_, up_[0], up_[1], up_[2], up_[3], up_[2], up_[1], up_[0]]
            vel = 0.15 if sec == "intro" else 0.12 if sec == "verse" else 0.14
            for j in range(nst):
                jj = (j + off) % 8
                acc = 1.0 if jj == 0 else 0.85 if jj == 4 else 0.68
                bus.add(piano(pat[jj], BEAT * 1.2, vel * acc), a + j * BEAT / 2 + rng.uniform(0, 0.006), pan=-0.2 + 0.06 * (jj % 4), send=0.32)
        elif arp in ("harp", "harp_soft"):
            mids = [m(t) + 12 for t in tones]
            pat = [mids[0], mids[1], mids[2], mids[0] + 12, mids[1] + 12, mids[2], mids[1], mids[0] + 12]
            v = (0.085 if sec == "verse" else 0.10) * (0.7 if arp == "harp_soft" else 1.0)
            for j in range(nst):
                jj = (j + off) % 8
                bus.add(harp(pat[jj], v * (1.0 if jj % 4 == 0 else 0.75)), a + j * BEAT / 2 + rng.uniform(0, 0.008), pan=-0.45 + 0.08 * (jj % 4), send=0.35)
        elif arp == "celesta":
            pcs = [m(t) % 12 for t in tones]
            up_ = sorted({t for t in range(m("C5"), m("D7")) if t % 12 in pcs})
            pat = [up_[0], up_[2], up_[1], up_[3], up_[2], up_[4], up_[3], up_[1]]
            v = 0.05 if sec == "intro" else 0.042 if sec == "verse" else 0.05
            for j in range(nst):
                jj = (j + off) % 8
                bus.add(celesta(pat[jj], v * (1.0 if jj % 4 == 0 else 0.7)), a + j * BEAT / 2 + rng.uniform(0, 0.006), pan=-0.3 + 0.15 * (jj % 4), send=0.45)
            if x == 0:
                bus.add(harp(m(bass) + 12, 0.10), a, pan=0.1, send=0.35)
                bus.add(harp(m(bass) + 19, 0.06), a + 2 * BEAT, pan=0.15, send=0.35)
        elif arp == "pluck":
            mids = [m(t) + 12 for t in tones]
            pat = [mids[0], mids[2], mids[1] + 12, mids[2], mids[0] + 12, mids[2], mids[1] + 12, mids[2]]
            v = 0.07 if sec == "intro" else 0.06 if sec == "verse" else 0.075
            for j in range(nst):
                jj = (j + off) % 8
                tt = a + j * BEAT / 2
                vv = v * (1.0 if jj % 4 == 0 else 0.75)
                bus.add(pluck(pat[jj], vv), tt, pan=-0.35, send=0.3)
                bus.add(pluck(pat[jj], vv * 0.33), tt + 0.75 * BEAT, pan=0.4, send=0.4)        # эхо
                bus.add(pluck(pat[jj], vv * 0.14), tt + 1.5 * BEAT, pan=-0.1, send=0.5)
    # ---------- отрывистые струнные
    for a, e, c, sec, b, x in segs:
        if not S["spic"] or sec in ("intro", "end"):
            continue
        r_ = m(H[c][0]) + 12
        sb = 4 if (S["spic"] == 2 and sec == "climax") else 2
        for j in range(int(round((e - a) / (BEAT / sb)))):
            nt = [r_, r_ + 7, r_ + 12, r_ + 7][j % 4] if sb == 4 else (r_ if j % 2 == 0 else r_ + 7)
            v = (0.10 if sec == "verse" else 0.13) * (1.0 if j % sb == 0 else 0.7)
            bus.add(short(nt, v), a + j * BEAT / sb, pan=0.35, send=0.22)
    # ---------- хор
    if S["choir"]:
        ch = [(a, e, m(H[c][1][2]) + 12, 0.24) for a, e, c, sec, b, x in segs if sec == "climax"]
        if ch:
            sig, ts = cline(ch, "choir", voices=10, att=1.2, rel=2.0, vowel=VOWEL_U if style == "sobor" else VOWEL_A)
            bus.add(sig, ts, pan=0.0, send=0.55, gain=S["choir"])
    # ---------- колокол (Собор): в начале фраз и в финале
    if style == "sobor":
        for b, (ch, mk, sec) in enumerate(P):
            if mk in (0, 4) or mk == "fin":
                bus.add(bell(m("F4") if mk != 4 else m("C5"), 0.16 if sec != "verse" else 0.11), bt(b), pan=0.15, send=0.6)
    # ---------- ударные
    for b, (ch, mk, sec) in enumerate(P):
        if sec == "end":
            break
        k = LV[sec]
        if S["drums"] in ("frame", "taiko"):
            v = (0.10, 0.115, 0.19)[k]
            bus.add(fdrum(v), bt(b, 0), pan=0.0, send=0.25)
            bus.add(fdrum(v * 0.6), bt(b, 1.5), pan=0.0, send=0.25)
            bus.add(fdrum(v * 0.5, low=False), bt(b, 2.5), pan=0.15, send=0.25)
            if sec == "climax":
                bus.add(fdrum(v * 0.75), bt(b, 2), pan=0.0, send=0.25)
                bus.add(fdrum(v * 0.35, low=False), bt(b, 3.5), pan=-0.15, send=0.25)
                if S["drums"] == "taiko":
                    for x_, tv in ((0, 0.30), (0.75, 0.16), (1.5, 0.2), (2, 0.26), (3, 0.2), (3.5, 0.14)):
                        bus.add(taiko(tv), bt(b, x_), pan=0.0, send=0.35)
            elif S["drums"] == "taiko" and sec == "verse":
                bus.add(taiko(0.14), bt(b, 0), pan=0.0, send=0.35)
                bus.add(taiko(0.10), bt(b, 2), pan=0.0, send=0.35)
        elif S["drums"] == "kick":
            if sec == "verse":
                bus.add(kick(0.22), bt(b, 0), pan=0.0, send=0.05)
                bus.add(kick(0.13), bt(b, 2.5), pan=0.0, send=0.05)
            elif sec == "climax":
                for x_ in (0, 1, 2, 3):
                    bus.add(kick(0.26 if x_ in (0, 2) else 0.2), bt(b, x_), pan=0.0, send=0.05)
                bus.add(fdrum(0.10, low=False), bt(b, 1), pan=0.2, send=0.3)
                bus.add(fdrum(0.10, low=False), bt(b, 3), pan=0.2, send=0.3)
        elif S["drums"] is None and sec == "climax" and style == "tihiy":
            bus.add(fdrum(0.08), bt(b), pan=0.0, send=0.35)
    # ---------- подводки, литавры, финал
    big = S["drums"] in ("frame", "taiko", "kick", "timp")
    for b in range(1, nb):
        if secs[b] == "climax" and secs[b - 1] != "climax":
            if big:
                bus.add(shimmer(BAR * 0.95, 0.10), bt(b - 1) + BAR * 0.05, pan=0.0, send=0.4)
            if S["drums"] in ("frame", "taiko", "timp"):
                for k in range(12):
                    bus.add(timp(m("C2"), 0.02 + 0.05 * k / 11, 0.6), bt(b - 1, 2) + k * BEAT * 2 / 12, pan=0.0, send=0.4)
            bus.add(timp(m("F2"), 0.15 if big else 0.07, 4.0), bt(b), pan=0.0, send=0.4)
    if secs[0] == "climax":
        if big:
            bus.add(shimmer(0.7, 0.09), 0.05, pan=0.0, send=0.4)
        bus.add(timp(m("F2"), 0.16 if big else 0.08, 4.0), bt(0), pan=0.0, send=0.4)
    cb = [b for b in range(nb) if secs[b] == "climax"]
    if len(cb) >= 5 and big:
        bus.add(timp(m("F2"), 0.13, 4.0), bt(cb[4]), pan=0.0, send=0.4)
    if big and secs[-2] == "climax":
        bus.add(shimmer(BAR * 0.95, 0.08), bt(fin_b - 1) + BAR * 0.05, pan=0.0, send=0.4)
    bus.add(timp(m("F2"), 0.12 if big else 0.06, 4.5), bt(fin_b), pan=0.0, send=0.45)
    if S["drums"] in ("frame", "taiko"):
        bus.add(fdrum(0.15), bt(fin_b), pan=0.0, send=0.35)
    if style == "sovr":
        bus.add(kick(0.24), bt(fin_b), pan=0.0, send=0.1)
    fin_inst = celesta if style == "shkatulka" else pluck if style == "sovr" else piano
    for k, nt in enumerate(["F4", "C5", "G5", "A5", "C6", "F6"]):
        tt = bt(fin_b, 0.5 * k + 0.5)
        if fin_inst is piano:
            bus.add(piano(m(nt), 4.0, 0.15 - 0.012 * k), tt, pan=0.15, send=0.55)
        elif fin_inst is celesta:
            bus.add(celesta(m(nt) + 12, 0.06 - 0.004 * k), tt, pan=0.15, send=0.55)
        else:
            bus.add(pluck(m(nt), 0.09 - 0.008 * k), tt, pan=0.15, send=0.55)
    for k, nt in enumerate(["C7", "A6", "F6"]):
        bus.add(celesta(m(nt), 0.05), bt(fin_b, 4.2 + k * 0.5), pan=-0.2, send=0.6)
    return bus, end_t


if __name__ == "__main__":
    import os
    import time
    style, pl, out = sys.argv[1], sys.argv[2], sys.argv[3]
    air = float(sys.argv[4]) if len(sys.argv) > 4 else 0.3
    t = time.time()
    bus, end_t = compose(style, pl)
    L, R = master(bus, air)
    cut = int((end_t + (4.5 if pl == "full" else 2.6)) * SR)
    L, R = L[:cut].copy(), R[:cut].copy()
    fo = int(1.5 * SR)
    w = (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo)))
    L[-fo:] *= w
    R[-fo:] *= w
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.5, R / pk * 0.5
    tmp = out + ".tmp.wav"
    write24(tmp, L, R)
    g = 10 ** ((-14.0 - lufs(tmp)) / 20)
    g = min(g, 0.89 / 0.5)                                    # пик не выше −1 дБFS; насыщения нет вообще
    write24(out, L * g, R * g)
    os.remove(tmp)
    print(out, "готово", round(len(L) / SR, 1), "с; пик", round(20 * math.log10(0.5 * g), 1), "дБFS;", f"{time.time() - t:.0f} с")
