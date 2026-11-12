"""«Живые строки» — оркестровая тема (~1 мин). Сочинено по нотам, сведено в стерео.
ре мажор, 74 уд/мин. Форма: вступление (1 такт) — тема на фортепиано (8) — кульминация, струнные (8) — финал (2).
Инструменты синтезируются: «войлочное» фортепиано с педалью, струнные секции (волновые таблицы, ансамбль голосов),
валторны, хор, арфа, челеста, литавры, тарелка; стерео-зал, шина-компрессор, лимитер.
python3 theme.py out.wav
"""
import math
import sys

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import fftconvolve

SR = 44100
BPM = 74
BEAT = 60 / BPM
BAR = 4 * BEAT
T0 = 0.35
N_BARS = 19
TOTAL = T0 + N_BARS * BAR + 5.5
rng = np.random.default_rng(2027)

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def m(name):
    """'F#5' -> midi"""
    p = NOTE[name[0]]
    i = 1
    while i < len(name) and name[i] in "#b":
        p += 1 if name[i] == "#" else -1
        i += 1
    return p + 12 * (int(name[i:]) + 1)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def bar_t(b, beat=0.0):
    return T0 + b * BAR + beat * BEAT


# ============================================================== шина: стерео + посыл в зал
class Bus:
    def __init__(self):
        n = int(TOTAL * SR)
        self.L = np.zeros(n)
        self.R = np.zeros(n)
        self.sL = np.zeros(n)
        self.sR = np.zeros(n)

    def add(self, sig, t, pan=0.0, send=0.25, gain=1.0, haas=0.0):
        s = int(t * SR)
        if s >= len(self.L) or s + len(sig) <= 0:
            return
        if s < 0:
            sig = sig[-s:]
            s = 0
        sig = sig[:len(self.L) - s] * gain
        # страховка от щелчков: 1 мс на вход, 8 мс на выход каждого звука
        ki, ko = min(len(sig), int(0.001 * SR)), min(len(sig), int(0.008 * SR))
        if ki > 1 and ko > 1:
            sig = sig.copy()
            sig[:ki] *= np.linspace(0, 1, ki)
            sig[-ko:] *= np.linspace(1, 0, ko)
        a = (pan + 1) * math.pi / 4
        gl, gr = math.cos(a), math.sin(a)
        d = int(abs(haas) * SR)
        e = s + len(sig)
        if d and haas > 0:     # правый канал чуть позже — ширина
            self.L[s:e] += sig * gl
            self.R[s + d:e + d if e + d <= len(self.R) else len(self.R)] += (sig * gr)[:len(self.R) - s - d]
        else:
            self.L[s:e] += sig * gl
            self.R[s:e] += sig * gr
        self.sL[s:e] += sig * gl * send
        self.sR[s:e] += sig * gr * send


NOISE = 1.0   # общий множитель шумов (смычок, молоточки, дыхание хора); 0 — чистый звук
AIR = 0.7     # подъём «воздуха» выше 4,5 кГц в мастеринге


def env_ar(n, att, rel, curve=1.5):
    t = np.arange(n) / SR
    dur = n / SR
    a = np.minimum(1, t / max(att, 1e-3)) ** curve
    r = np.clip((dur - t) / max(rel, 1e-3), 0, 1) ** 1.2
    return a * r


def drift(n, cents, speed=0.6):
    """медленный случайный уход высоты (в долях частоты)"""
    k = max(2, int(n / SR * speed * 4) + 2)
    pts = rng.normal(0, 1, k)
    x = np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
    return x * cents / 1200 * math.log(2)


# ============================================================== волновой осциллятор
def table(freq, amp_fn, nmax=60, fmax=14000):
    N = 4096
    ph = np.arange(N) / N * 2 * np.pi
    w = np.zeros(N)
    for h in range(1, nmax + 1):
        fh = freq * h
        if fh > fmax:
            break
        w += amp_fn(h, fh) * np.sin(h * ph + rng.uniform(0, 6.28))
    w /= np.max(np.abs(w)) + 1e-9
    return np.append(w, w[0])


def play(tab, fcurve):
    phase = np.cumsum(fcurve) / SR
    phase -= np.floor(phase)
    idx = phase * (len(tab) - 1)
    return np.interp(idx, np.arange(len(tab)), tab)


def body_string(fh):
    return 0.55 + 1.0 * math.exp(-((fh - 290) / 90) ** 2) + 0.7 * math.exp(-((fh - 470) / 130) ** 2) + 0.5 * math.exp(-((fh - 1050) / 300) ** 2) + \
        0.55 * math.exp(-((fh - 2600) / 700) ** 2)


def strings(midi, dur, vel, voices=6, att=0.35, rel=0.6, bright=1.0, vib=0.0045, legato_pre=0.0):
    f0 = hz(midi)
    tab = table(f0, lambda h, fh: body_string(fh) / h * math.exp(-fh / (6500 * bright)))
    n = int((dur + rel) * SR)
    out = np.zeros(n)
    t = np.arange(n) / SR
    for v in range(voices):
        det = 2 ** (rng.uniform(-7, 7) / 1200)
        rate = rng.uniform(4.6, 6.0)
        onset = rng.uniform(0.25, 0.5)
        vibr = vib * np.sin(2 * np.pi * rate * t + rng.uniform(0, 6.28)) * np.clip((t - onset) / 0.5, 0, 1)
        fc = f0 * det * np.exp(vibr + drift(n, 4))
        sig = play(tab, fc)
        lag = int(rng.uniform(0, 0.035) * SR)
        sig = np.roll(sig, lag)
        sig[:lag] = 0
        kf = min(len(sig) - lag, int(0.006 * SR))   # вход голоса без щелчка
        sig[lag:lag + kf] *= np.linspace(0, 1, kf)
        out += sig
    # смычок: шум в верхней середине, сильнее на атаке
    nz = rng.normal(0, 1, n)
    nz = gaussian_filter1d(nz, 1.2) - gaussian_filter1d(nz, 6)
    e = env_ar(n, att * 0.7, rel, 1.2)
    bow = nz * (0.012 + 0.07 * np.exp(-t / 0.15)) * NOISE
    swell = 0.85 + 0.15 * np.sin(np.pi * np.clip(t / max(dur, 0.1), 0, 1))
    return vel * e * swell * (out / voices * 0.9 + bow * 0.25)


def legato_line(notes, voices=6, att=0.3, rel=0.7, bright=1.0, vib=0.005, glide=0.035, noise=0.6):
    """Связная линия струнных: notes = [(t_start, t_end, midi, vel)], переходы портаменто, без провалов между нотами.
    Управляющие кривые считаются с частотой 1 кГц и растягиваются до звуковой. Возвращает (сигнал, время начала)."""
    CR = 1000
    t0 = notes[0][0] - 0.05
    t1 = notes[-1][1] + rel
    n = int((t1 - t0) * SR)
    nc = int((t1 - t0) * CR) + 2
    pitch = np.full(nc, float(notes[0][2]))
    amp = np.zeros(nc)
    since = np.zeros(nc)
    for i, (a, b, mi, v) in enumerate(notes):
        s0 = int((a - t0) * CR)
        s1 = int(((notes[i + 1][0] if i + 1 < len(notes) else b) - t0) * CR)
        pitch[s0:s1] = mi
        amp[s0:s1] = v
        since[s0:s1] = np.arange(s1 - s0) / CR
    s_last = int((notes[-1][1] - t0) * CR)
    pitch[s_last:] = notes[-1][2]
    since[s_last:] = since[s_last - 1] + np.arange(nc - s_last) / CR
    amp = gaussian_filter1d(amp, 0.06 * CR)
    amp *= 1 - 0.08 * np.exp(-since / 0.05)
    xa = np.arange(n) / SR * CR
    up = lambda c: np.interp(xa, np.arange(nc), c)
    tt = np.arange(n) / SR + t0
    env = np.clip((tt - notes[0][0] + 0.05) / att, 0, 1) ** 1.4 * np.clip((t1 - tt) / rel, 0, 1) ** 1.2
    since_a = up(since)
    mid = float(np.median([x[2] for x in notes]))
    tab = table(hz(mid), lambda h, fh: body_string(fh) / h * math.exp(-fh / (6500 * bright)))
    out = np.zeros(n)
    for v in range(voices):
        lp = up(gaussian_filter1d(pitch, rng.uniform(0.6, 1.3) * glide * CR))
        det = rng.uniform(-7, 7) / 1200
        rate = rng.uniform(4.7, 6.0)
        vdep = vib * np.clip((since_a - rng.uniform(0.15, 0.3)) / 0.4, 0, 1)
        lf = (lp - 69) / 12 + det + vdep * np.sin(2 * np.pi * rate * tt + rng.uniform(0, 6.28)) / math.log(2) + drift(n, 3) / math.log(2)
        sig = play(tab, 440.0 * 2 ** lf)
        lag = int(rng.uniform(0, 0.025) * SR)
        sig = np.roll(sig, lag)
        sig[:lag] = 0
        kf = min(len(sig) - lag, int(0.006 * SR))   # вход голоса без щелчка
        sig[lag:lag + kf] *= np.linspace(0, 1, kf)
        out += sig
    nz = rng.normal(0, 1, n)
    nz = gaussian_filter1d(nz, 1.2) - gaussian_filter1d(nz, 6)
    bow = nz * (0.01 + 0.05 * np.exp(-since_a / 0.12)) * noise * NOISE
    return up(amp) * env * (out / voices * 0.9 + bow * 0.25), t0


def voice_lead(prev, tones, lo, hi):
    pcs = sorted({m(x) % 12 for x in tones})
    cands = [x for x in range(lo, hi + 1) if x % 12 in pcs]
    out = []
    for p in prev:
        best = min((c for c in cands if c not in out), key=lambda c: abs(c - p), default=p)
        out.append(best)
    return out


def choir(midi, dur, vel, voices=8):
    f0 = hz(midi)
    fm = [(780, 1.0, 120), (1150, 0.55, 140), (2700, 0.25, 260), (3300, 0.15, 300)]
    tab = table(f0, lambda h, fh: (0.06 + sum(a * math.exp(-((fh - c) / w) ** 2) for c, a, w in fm)) / h ** 0.25, fmax=8000)
    n = int((dur + 1.2) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for v in range(voices):
        det = 2 ** (rng.uniform(-11, 11) / 1200)
        vibr = 0.004 * np.sin(2 * np.pi * rng.uniform(4.6, 5.6) * t + rng.uniform(0, 6.28)) * np.clip((t - 0.6) / 0.8, 0, 1)
        out += play(tab, f0 * det * np.exp(vibr + drift(n, 6)))
    nz = rng.normal(0, 1, n)
    br = (gaussian_filter1d(nz, 2) - gaussian_filter1d(nz, 10)) * 0.04 * NOISE
    return vel * env_ar(n, 0.9, 1.2, 1.6) * (out / voices + br)


def horn(midi, dur, vel):
    f0 = hz(midi)
    tab = table(f0, lambda h, fh: (0.3 + math.exp(-((fh - 480) / 260) ** 2) + 0.5 * math.exp(-((fh - 1150) / 380) ** 2)) / h ** 1.1 * math.exp(-fh / 2600), fmax=7000)
    n = int((dur + 0.9) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for v in range(3):
        det = 2 ** (rng.uniform(-5, 5) / 1200)
        vibr = 0.0018 * np.sin(2 * np.pi * 4.6 * t + rng.uniform(0, 6.28)) * np.clip((t - 0.7) / 0.6, 0, 1)
        out += play(tab, f0 * det * np.exp(vibr + drift(n, 3)))
    return vel * env_ar(n, 0.45, 0.9, 1.4) * out / 3


def piano(midi, dur, vel, rel=0.35):
    """«войлочное» фортепиано: 2 струны, негармоничность, частичные затухают по-разному; dur — пока держит педаль"""
    f0 = hz(midi)
    n = int((dur + rel + 0.05) * SR)
    t = np.arange(n) / SR
    B = 0.00012 * (f0 / 262) ** 0.7
    T = 7.0 * (262 / f0) ** 0.55
    nh = int(min(16, 9000 / f0))
    s = np.zeros(n)
    soft = 0.55 - 0.30 * vel
    for det in (2 ** (-0.6 / 1200), 2 ** (0.6 / 1200)):
        for h in range(1, nh + 1):
            fh = f0 * det * h * math.sqrt(1 + B * h * h)
            a = math.exp(-h * soft) / h ** 0.7 * math.exp(-fh / 5200)
            tau1 = 0.35 * T / (1 + 0.5 * h)
            tau2 = T / (1 + 0.25 * h)
            dec = 0.55 * np.exp(-t / tau1) + 0.45 * np.exp(-t / tau2)
            s += a * np.sin(2 * np.pi * fh * t + rng.uniform(0, 6.28)) * dec
    s /= 2.2
    att = np.minimum(1, t / 0.004)
    off = np.where(t > dur, np.exp(-(t - dur) / 0.11), 1.0)
    k = min(n, int(0.02 * SR))
    th = np.zeros(n)
    th[:k] = (gaussian_filter1d(rng.normal(0, 1, k), 5) * np.exp(-np.arange(k) / (0.004 * SR))) * 0.5
    return vel * (s * att * off + th * vel * NOISE)


def harp(midi, vel):
    f0 = hz(midi)
    n = int(3.2 * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for h in range(1, 9):
        fh = f0 * h
        if fh > 9000:
            break
        s += (1 / h ** 1.2) * np.sin(2 * np.pi * fh * t) * np.exp(-t * (0.9 + 1.4 * h) * (f0 / 300) ** 0.3)
    return vel * s * np.minimum(1, t / 0.003)


def celesta(midi, vel):
    f0 = hz(midi)
    n = int(3.5 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f0 * t) * np.exp(-t * 1.3) + 0.35 * np.sin(2 * np.pi * f0 * 4.01 * t) * np.exp(-t * 5) + 0.12 * np.sin(2 * np.pi * f0 * 6.8 * t) * np.exp(-t * 9)
    return vel * s * np.minimum(1, t / 0.002)


def timp(midi, vel, dur=3.0):
    f0 = hz(midi)
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for r, a, d in ((1.0, 1.0, 1.3), (1.5, 0.5, 2.0), (1.98, 0.3, 2.8), (2.44, 0.18, 3.5)):
        s += a * np.sin(2 * np.pi * f0 * r * t * (1 + 0.01 * np.exp(-t * 20))) * np.exp(-t * d)
    k = int(0.03 * SR)
    nz = np.zeros(n)
    nz[:k] = gaussian_filter1d(rng.normal(0, 1, k), 3) * np.exp(-np.arange(k) / (0.008 * SR))
    return vel * (s * np.minimum(1, t / 0.004) + 0.4 * nz)


def cymbal_swell(dur, vel):
    n = int((dur + 1.2) * SR)
    t = np.arange(n) / SR
    nz = rng.normal(0, 1, n)
    hi = gaussian_filter1d(nz, 0.7) - gaussian_filter1d(nz, 2.5)
    shimmer = hi * (1 + 0.3 * np.sin(2 * np.pi * 7 * t))
    e = np.where(t < dur, (t / dur) ** 3, np.exp(-(t - dur) / 0.35))
    return vel * shimmer * e


# ============================================================== ПАРТИТУРА
# аккорды по тактам: (бас, звуки аккорда); такт 8 и 16 — по два аккорда
D, A_Cs, Bm, G, Em7, A, Asus, Fsm, D_Fs, Dmaj9 = (
    ("D2", ["D3", "F#3", "A3"]), ("C#2", ["A2", "C#3", "E3"]), ("B1", ["B2", "D3", "F#3"]), ("G1", ["G2", "B2", "D3"]),
    ("E2", ["E3", "G3", "B3", "D4"]), ("A1", ["A2", "C#3", "E3"]), ("A1", ["A2", "D3", "E3"]), ("F#1", ["F#2", "A2", "C#3"]),
    ("F#1", ["D3", "F#3", "A3"]), ("D2", ["D3", "F#3", "A3", "C#4", "E4"]))
HARM = {0: [(0, D)],
        1: [(0, D)], 2: [(0, A_Cs)], 3: [(0, Bm)], 4: [(0, G)], 5: [(0, D)], 6: [(0, A_Cs)], 7: [(0, Bm)], 8: [(0, Em7), (2, A)],
        9: [(0, G)], 10: [(0, A)], 11: [(0, Fsm)], 12: [(0, Bm)], 13: [(0, G)], 14: [(0, A)], 15: [(0, D_Fs)], 16: [(0, G), (2, Asus), (3, A)],
        17: [(0, D)], 18: [(0, Dmaj9)]}

# тема (фортепиано): (такт, доля, длительность в долях, нота, сила)
THEME = [
    (1, 0, 1, "A4", .55), (1, 1, 1, "D5", .62), (1, 2, 1.5, "F#5", .72), (1, 3.5, .5, "E5", .55),
    (2, 0, 2, "E5", .66), (2, 2, 1, "C#5", .55), (2, 3, 1, "A4", .5),
    (3, 0, 1, "D5", .6), (3, 1, 1, "F#5", .66), (3, 2, 1.5, "B5", .78), (3, 3.5, .5, "A5", .58),
    (4, 0, 1, "A5", .7), (4, 1, 1, "G5", .62), (4, 2, 1, "F#5", .6), (4, 3, 1, "E5", .55),
    (5, 0, 1.5, "F#5", .72), (5, 1.5, .5, "E5", .55), (5, 2, 1, "D5", .6), (5, 3, 1, "A4", .52),
    (6, 0, 1, "B4", .55), (6, 1, 1, "C#5", .6), (6, 2, 2, "E5", .7),
    (7, 0, 1, "D5", .62), (7, 1, 1, "C#5", .56), (7, 2, 1, "B4", .54), (7, 3, 1, "F#5", .68),
    (8, 0, 2, "E5", .66), (8, 2, 1, "A4", .55), (8, 3, 1, "C#5", .6),
    (17, 0, 1, "A4", .5), (17, 1, 1, "D5", .55), (17, 2, 1.5, "F#5", .62), (17, 3.5, .5, "E5", .48),
    (18, 0, 6, "D5", .6),
]
# кульминация — первые скрипки
VIOLINS = [
    (9, 0, 2, "B5"), (9, 2, 1, "A5"), (9, 3, 1, "G5"),
    (10, 0, 1.5, "A5"), (10, 1.5, .5, "G5"), (10, 2, 1, "F#5"), (10, 3, 1, "E5"),
    (11, 0, 2, "F#5"), (11, 2, 1, "E5"), (11, 3, 1, "C#5"),
    (12, 0, 1, "D5"), (12, 1, 1, "F#5"), (12, 2, 2, "B5"),
    (13, 0, 2, "D6"), (13, 2, 1, "C#6"), (13, 3, 1, "B5"),
    (14, 0, 1.5, "C#6"), (14, 1.5, .5, "B5"), (14, 2, 2, "A5"),
    (15, 0, 1, "A5"), (15, 1, 1, "F#5"), (15, 2, 1.5, "D6"), (15, 3.5, .5, "C#6"),
    (16, 0, 2, "B5"), (16, 2, 2, "A5"),
]
# виолончели — встречный голос в кульминации
CELLOS = [
    (9, 0, 2, "D4"), (9, 2, 2, "B3"), (10, 0, 2, "C#4"), (10, 2, 2, "E4"), (11, 0, 2, "F#4"), (11, 2, 1, "E4"), (11, 3, 1, "C#4"),
    (12, 0, 4, "D4"), (13, 0, 2, "B3"), (13, 2, 2, "D4"), (14, 0, 2, "E4"), (14, 2, 2, "C#4"), (15, 0, 2, "D4"), (15, 2, 2, "A3"),
    (16, 0, 2, "B3"), (16, 2, 2, "C#4"),
]


def chord_at(b, beat):
    cur = HARM[b][0][1]
    for bt, ch in HARM[b]:
        if beat >= bt:
            cur = ch
    return cur


def compose():
    bus = Bus()
    # ---------------------------------------------------------- фортепиано: перебор восьмыми, педаль меняется с аккордом
    for b in range(0, 19):
        segs = HARM[b]
        for i, (bt, (bass, tones)) in enumerate(segs):
            end_bt = segs[i + 1][0] if i + 1 < len(segs) else 4
            t_ch = bar_t(b, bt)
            ped = (end_bt - bt) * BEAT
            if b == 18:
                ped = 5.0
            mids = [m(x) for x in tones]
            r = mids[0]
            third = [x for x in mids if (x - r) % 12 in (3, 4, 5)]
            third = third[0] if third else r + 4
            fifth = [x for x in mids if (x - r) % 12 in (7, 6, 8)]
            fifth = fifth[0] if fifth else r + 7
            low = m(bass) + 12 if m(bass) < m("C2") + 12 else m(bass)
            pat = [low, fifth, r + 12, third + 12, fifth + 12, third + 12, r + 12, fifth]
            if b == 18:
                pat = [low, fifth, r + 12, third + 12, m("C#5"), m("E5")]
            nsteps = int((end_bt - bt) * 2)
            dyn = {0: .30, 17: .22, 18: .20}.get(b, .21 if b < 9 else .12)
            for j in range(min(nsteps, len(pat)) if b == 18 else nsteps):
                note = pat[j % len(pat)]
                at = t_ch + j * BEAT / 2 + rng.uniform(0, 0.012)
                held = ped - j * BEAT / 2
                acc = 1.0 if j == 0 else (0.82 if j % 2 == 0 else 0.7)
                bus.add(piano(note, held, dyn * acc), at, pan=float(np.clip((note - 62) / 40, -0.45, 0.45)), send=0.22, gain=0.9)
    # ---------------------------------------------------------- тема на фортепиано
    for b, bt, du, nt, v in THEME:
        at = bar_t(b, bt) + rng.uniform(-0.006, 0.01)
        held = du * BEAT + (0.25 if b < 18 else 0)
        bus.add(piano(m(nt), held, v * 0.95), at, pan=0.05, send=0.26, gain=1.0)
    # ---------------------------------------------------------- виолончели + контрабасы: басы аккордов, связно
    bl, bl2 = [], []
    for b in range(3, 19):
        for i, (bt, (bass, tones)) in enumerate(HARM[b]):
            end_bt = HARM[b][i + 1][0] if i + 1 < len(HARM[b]) else 4
            vel = {3: .10, 4: .12, 5: .14, 6: .15, 7: .16, 8: .18}.get(b, .16)
            if 9 <= b <= 16:
                vel = .42 + .08 * (b >= 13)
            end = bar_t(b, end_bt) if b < 18 else bar_t(18, 5.5)
            bl.append((bar_t(b, bt), end, m(bass) + 12, vel))
            if 9 <= b <= 18:
                bl2.append((bar_t(b, bt), end, m(bass), vel * 0.85))
    sig, ts = legato_line(bl, voices=5, att=0.8, rel=1.2, bright=0.8, vib=0.003, glide=0.05, noise=0.5)
    bus.add(sig, ts, pan=0.35, send=0.25)
    sig, ts = legato_line(bl2, voices=4, att=0.5, rel=1.2, bright=0.6, vib=0.002, glide=0.05, noise=0.3)
    bus.add(sig, ts + 0.02, pan=0.28, send=0.22)
    # ---------------------------------------------------------- альты/вторые скрипки: три голоса держат гармонию, плавно переходя по аккордам
    voicing = [m("A3"), m("D4"), m("F#4")]
    lines = [[], [], []]
    for b in range(5, 19):
        for i, (bt, (bass, tones)) in enumerate(HARM[b]):
            end_bt = HARM[b][i + 1][0] if i + 1 < len(HARM[b]) else 4
            voicing = voice_lead(voicing, tones, m("F#3"), m("E5"))
            vel = (0.05 + 0.012 * (b - 5)) if b < 9 else (0.16 if b < 13 else 0.20)
            if b >= 17:
                vel = 0.07
            for k in range(3):
                lines[k].append((bar_t(b, bt), bar_t(b, end_bt) if b < 18 else bar_t(18, 5.5), voicing[k], vel))
    for k in range(3):
        sig, ts = legato_line(lines[k], voices=4, att=1.2, rel=1.6, bright=0.9, vib=0.004, glide=0.06, noise=0.4)
        bus.add(sig, ts + 0.03 * k, pan=-0.05 + 0.12 * k, send=0.32)
    # ---------------------------------------------------------- вступление: тихий флажолет скрипок
    bus.add(strings(m("A5"), BAR * 1.0, 0.035, voices=6, att=1.2, rel=1.5, bright=1.2), bar_t(0, 0.5), pan=-0.3, send=0.5)
    bus.add(strings(m("F#5"), BAR * 1.2, 0.03, voices=6, att=1.4, rel=1.5, bright=1.2), bar_t(0, 1.5), pan=-0.1, send=0.5)
    # ---------------------------------------------------------- кульминация: первые скрипки поют тему (а в 13–16 — вторые октавой ниже)
    for lo_b, hi_b in ((9, 13), (13, 17)):
        ph = [(bar_t(b, bt) - 0.03, bar_t(b, bt + du) + (0.5 if (b, bt) == (16, 2) else 0.0), m(nt), (0.90 if b < 13 else 1.05))
              for b, bt, du, nt in VIOLINS if lo_b <= b < hi_b]
        sig, ts = legato_line(ph, voices=8, att=0.25, rel=0.9, bright=1.4, vib=0.0055)
        bus.add(sig, ts, pan=-0.38, send=0.34, haas=0.004)
        if lo_b == 13:
            sig, ts = legato_line([(a, b_, mi - 12, v * 0.55) for a, b_, mi, v in ph], voices=6, att=0.3, rel=0.9, bright=1.0, vib=0.005)
            bus.add(sig, ts + 0.01, pan=-0.12, send=0.3)
        phc = [(bar_t(b, bt) - 0.02, bar_t(b, bt + du), m(nt), 0.48) for b, bt, du, nt in CELLOS if lo_b <= b < hi_b]
        sig, ts = legato_line(phc, voices=6, att=0.3, rel=0.8, bright=0.95, vib=0.005)
        bus.add(sig, ts, pan=0.42, send=0.3)
    # ---------------------------------------------------------- валторны и хор в кульминации
    for b in range(9, 17):
        for i, (bt, (bass, tones)) in enumerate(HARM[b]):
            end_bt = HARM[b][i + 1][0] if i + 1 < len(HARM[b]) else 4
            du = (end_bt - bt) * BEAT + 0.2
            hv = 0.08 if b < 13 else 0.14
            for k, tn in enumerate(tones[:3]):
                bus.add(horn(m(tn) + 12, du, hv), bar_t(b, bt) + 0.05 * k, pan=0.15, send=0.45)
            if b >= 13:
                for k, tn in enumerate(tones[:3]):
                    bus.add(choir(m(tn) + 12, du, 0.10), bar_t(b, bt) + 0.08 * k, pan=-0.3 + 0.3 * k, send=0.55)
    # ---------------------------------------------------------- арфа: восходящие переборы в теме (5–8) и в кульминации
    for b in list(range(5, 9)) + list(range(9, 17)):
        bass, tones = chord_at(b, 0)
        notes = [m(x) + 12 for x in tones[:3]]
        notes = notes + [x + 12 for x in notes]
        for k, nt in enumerate(notes):
            bus.add(harp(nt, 0.08 if b < 9 else 0.05), bar_t(b, 0) + 0.075 * k + 0.02, pan=-0.45, send=0.35)
    # ---------------------------------------------------------- челеста в финале
    for k, nt in enumerate(["F#6", "A6", "E6", "D6"]):
        bus.add(celesta(m(nt), 0.12), bar_t(18, 0.5 + k * 0.75), pan=0.3 - 0.2 * k, send=0.5)
    for k, nt in enumerate(["A5", "D6"]):
        bus.add(celesta(m(nt), 0.08), bar_t(0, 2 + k), pan=0.3, send=0.5)
    # ---------------------------------------------------------- литавры и тарелка: подход к кульминации и её вершина
    for k in range(14):
        bus.add(timp(m("A2"), 0.012 + 0.03 * k / 13, 0.6), bar_t(8, 2) + k * BEAT * 2 / 14, pan=0.0, send=0.4)
    bus.add(timp(m("G2"), 0.10), bar_t(9, 0), pan=0.0, send=0.4)
    bus.add(timp(m("G2"), 0.13), bar_t(13, 0), pan=0.0, send=0.4)
    for k in range(10):
        bus.add(timp(m("A2"), 0.015 + 0.035 * k / 9, 0.6), bar_t(16, 2) + k * BEAT * 2 / 10, pan=0.0, send=0.4)
    bus.add(timp(m("D2"), 0.08, 4.0), bar_t(17, 0), pan=0.0, send=0.45)
    bus.add(cymbal_swell(BEAT * 2, 0.012), bar_t(8, 2), pan=0.2, send=0.5)
    bus.add(cymbal_swell(BEAT * 2, 0.016), bar_t(12, 2), pan=0.2, send=0.5)
    return bus


# ============================================================== зал и мастеринг
def hall_ir(seed, rt_low=2.9, rt_high=1.3, pre=0.022, length=3.6):
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    nz = r.normal(0, 1, n)
    low = gaussian_filter1d(nz, 3.0)
    high = nz - low
    tail = low * 2.2 * np.exp(-t * 6.9 / rt_low) + high * 0.6 * np.exp(-t * 6.9 / rt_high)
    tail *= np.clip((t - pre) / 0.04, 0, 1)
    er = np.zeros(n)
    for d, g in ((0.011, .5), (0.019, .42), (0.027, .35), (0.036, .3), (0.049, .26), (0.061, .22), (0.077, .18)):
        er[int((d + r.uniform(-0.002, 0.002)) * SR)] += g * r.choice([-1, 1])
    ir = tail + er * 3
    return ir / np.sqrt(np.sum(ir ** 2))


def compressor(L, R, thr_db=-20, ratio=2.2, att=0.015, rel=0.25):
    x = (L + R) / 2
    pw = gaussian_filter1d(x * x, int(0.03 * SR))
    lev = 10 * np.log10(pw + 1e-12)
    over = np.maximum(0, lev - thr_db)
    gr = -over * (1 - 1 / ratio)
    # сглаживание: быстрее на атаке, медленнее на отпускании
    g = np.empty_like(gr)
    a_a, a_r = math.exp(-1 / (att * SR)), math.exp(-1 / (rel * SR))
    acc = 0.0
    step = 64
    gs = gr[::step]
    out = np.empty_like(gs)
    for i, v in enumerate(gs):
        a = a_a ** step if v < acc else a_r ** step
        acc = a * acc + (1 - a) * v
        out[i] = acc
    g = np.interp(np.arange(len(gr)), np.arange(0, len(gr), step)[:len(out)], out)
    k = 10 ** (g / 20)
    return L * k, R * k


def master(bus):
    irL, irR = hall_ir(11), hall_ir(23)
    wL = fftconvolve(bus.sL + 0.35 * bus.sR, irL)[:len(bus.L)]
    wR = fftconvolve(bus.sR + 0.35 * bus.sL, irR)[:len(bus.R)]
    L = bus.L + 0.55 * wL
    R = bus.R + 0.55 * wR
    # эквалайзер: срез ниже 30 Гц, -2 дБ «каши» 150–450 Гц, +3 дБ воздуха выше ~4,5 кГц
    out = []
    for ch in (L, R):
        ch = ch - gaussian_filter1d(ch, SR / (2 * math.pi * 30))
        band = gaussian_filter1d(ch, SR / (2 * math.pi * 450)) - gaussian_filter1d(ch, SR / (2 * math.pi * 150))
        ch = ch - 0.22 * band
        air = ch - gaussian_filter1d(ch, SR / (2 * math.pi * 4500))
        out.append(ch + AIR * air)
    L, R = out
    peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
    L, R = L / peak, R / peak
    L, R = compressor(L, R, thr_db=-15, ratio=1.8)
    peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
    L, R = L / peak, R / peak
    # мягкий лимитер
    drive = 1.15
    L, R = np.tanh(L * drive) / math.tanh(drive), np.tanh(R * drive) / math.tanh(drive)
    fade_in = int(0.05 * SR)
    for ch in (L, R):
        ch[:fade_in] *= np.linspace(0, 1, fade_in)
        ch[-int(1.5 * SR):] *= np.linspace(1, 0, int(1.5 * SR)) ** 1.5
    return L, R


if __name__ == "__main__":
    import time
    import wave
    t = time.time()
    bus = compose()
    print(f"партитура: {time.time() - t:.0f} с")
    L, R = master(bus)
    peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
    L, R = L / peak * 0.89, R / peak * 0.89
    out = sys.argv[1] if len(sys.argv) > 1 else "theme.wav"
    st = np.empty(2 * len(L))
    st[0::2], st[1::2] = L, R
    with wave.open(out, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype(np.int16).tobytes())
    print(f"готово {out}: {len(L) / SR:.1f} с, {time.time() - t:.0f} с")
