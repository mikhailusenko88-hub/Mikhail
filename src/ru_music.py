#!/usr/bin/env python3
"""Фоновые треки в русском народном стиле (своя музыка, мелодии придуманы с нуля).
Балалайка, гусли — Karplus-Strong; баян — синтез язычков; жалейка — духовой;
колокольчики, ложки, бубен — синтез.  Запуск: python3 ru_music.py OUT_DIR
"""
import os
import sys

import numpy as np
from scipy.signal import lfilter, sosfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kz_music import SR, Mix, _sos, finish, frame_drum, kick, master_mp3, mf, pad, shaker  # noqa: E402

TAU = 2 * np.pi


# ---------------------------------------------------------------- струнные
def ks_raw(m, T, bright, dur, rng, pos):
    f = mf(m)
    P = SR / f - 0.5
    N = int(P)
    d = P - N
    if d < 0.1:
        N -= 1
        d += 1.0
    C = (1 - d) / (1 + d)
    n = int(dur * SR)
    exc = rng.uniform(-1, 1, 2 * N)
    exc = sosfilt(_sos("low", 400 + 9000 * bright), exc)[N:]
    p = max(1, int(N * pos))
    exc = exc - 0.6 * np.roll(exc, p)
    x = np.zeros(n)
    x[:N] = exc
    g = np.exp(-1.0 / (f * T))
    a = np.zeros(N + 3)
    a[0], a[1] = 1.0, C
    a[N] -= g / 2 * C
    a[N + 1] -= g / 2 * (1 + C)
    a[N + 2] -= g / 2
    return lfilter([1.0, C], a, x)


BAL1, BAL2, BALHP = _sos("band", [330, 560]), _sos("band", [900, 1500]), _sos("high", 140)
GUS1, GUSHP = _sos("band", [240, 450]), _sos("high", 80)
_cache = {}


def _fin(y):
    y[:66] *= np.linspace(0, 1, 66)
    k = int(0.03 * SR)
    y[-k:] *= np.linspace(1, 0, k)
    return y / (np.max(np.abs(y)) + 1e-9)


def _cached(kind, m, T, bright, dur, rng, make):
    key = (kind, m, round(T, 3), round(bright, 2), dur)
    if key not in _cache:
        _cache[key] = [make(np.random.default_rng(abs(hash(key)) % 2**32 + i)) for i in range(3)]
    return _cache[key][rng.integers(3)]


def balalaika(m, T=0.5, bright=0.85, dur=None, rng=None):
    dur = dur or min(4 * T + 0.2, 4.0)

    def mk(r):
        y = ks_raw(m, T, bright, dur, r, 0.12)
        y = y + 0.7 * sosfilt(BAL1, y) + 0.5 * sosfilt(BAL2, y)
        return _fin(sosfilt(BALHP, y))
    return _cached("bal", m, T, bright, dur, rng, mk)


def gusli(m, T=2.5, bright=0.75, dur=None, rng=None):
    dur = dur or min(3 * T + 0.3, 7.0)

    def mk(r):
        y = ks_raw(m, T, bright, dur, r, 0.3)
        y = y + 0.35 * sosfilt(GUS1, y)
        return _fin(sosfilt(GUSHP, y))
    return _cached("gus", m, T, bright, dur, rng, mk)


# ---------------------------------------------------------------- духовые
def bayan(midis, dur, rng, att=0.05, rel=0.14, dark=False):
    """Баян: по два язычка на ноту с лёгкой расстройкой, формант корпуса, мех."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in midis:
        for det in (-0.05, 0.05):
            f = mf(m) * 2 ** (det / 12)
            ph = TAU * f * t + rng.uniform(0, TAU)
            for k in range(1, 16):
                if f * k < 10000:
                    s += np.sin(k * ph) / k ** 0.9
    s = 0.35 * s + sosfilt(_sos("band", [700, 3200]), s)
    if dark:
        s = sosfilt(_sos("low", 1300), s)
    env = np.ones(n)
    a = max(1, int(att * SR))
    env[:a] = np.linspace(0, 1, a)
    r0 = int(dur * SR)
    env[r0:] = np.linspace(1, 0, n - r0) ** 2
    env *= 0.88 + 0.12 * np.sin(np.pi * np.clip(t / max(dur, 1e-3), 0, 1))
    s *= env
    return s / (np.max(np.abs(s)) + 1e-9)


def zhaleika(m, dur, rng, att=0.05, rel=0.15):
    """Жалейка: «носовой» язычковый духовой с вибрато и дыханием."""
    f = mf(m)
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    vd = np.clip((t - 0.18) / 0.3, 0, 1) * 0.16
    ph = TAU * np.cumsum(f * 2 ** (vd * np.sin(TAU * 5.6 * t) / 12)) / SR
    s = np.sin(ph) + 0.15 * np.sin(2 * ph) + 0.5 * np.sin(3 * ph) + 0.25 * np.sin(5 * ph) + 0.1 * np.sin(7 * ph)
    s = 0.6 * s + sosfilt(_sos("band", [900, 3000]), s) * 0.8
    breath = sosfilt(_sos("band", [f, min(f * 4, 12000)]), rng.standard_normal(n)) * 0.25
    env = np.ones(n)
    a = int(att * SR)
    env[:a] = np.linspace(0, 1, a)
    r0 = int(dur * SR)
    env[r0:] = np.linspace(1, 0, n - r0) ** 2
    s = s * env + breath * env * (0.4 + 0.6 * np.exp(-t * 10))
    return s / (np.max(np.abs(s)) + 1e-9)


# ---------------------------------------------------------------- перкуссия и колокола
def glock(m, rng, dur=2.5):
    """Колокольчик-челеста для «сказочных» мелодий."""
    f = mf(m)
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for r, amp, dec in ((1, 1.0, 1.6), (2.76, 0.35, 4.0), (5.40, 0.18, 7.0), (8.93, 0.08, 10.0)):
        if f * r < 16000:
            s += amp * np.sin(TAU * f * r * t + rng.uniform(0, TAU)) * np.exp(-t * dec)
    s[:44] *= np.linspace(0, 1, 44)
    return s / np.max(np.abs(s))


def church_bell(m, rng, dur=6.0):
    f = mf(m)
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for r, amp, dec in ((0.5, 0.6, 0.5), (1, 1.0, 0.8), (1.19, 0.6, 1.0), (1.5, 0.4, 1.3),
                        (2.0, 0.5, 1.6), (2.52, 0.25, 2.2), (3.0, 0.2, 2.8)):
        s += amp * np.sin(TAU * f * r * t + rng.uniform(0, TAU)) * np.exp(-t * dec)
    s[:88] *= np.linspace(0, 1, 88)
    return s / np.max(np.abs(s))


def spoons(rng):
    """Деревянные ложки."""
    t = np.arange(int(0.07 * SR)) / SR
    nz = sosfilt(_sos("band", [1400, 5000]), rng.standard_normal(len(t))) * np.exp(-t * 95)
    s = nz + 0.8 * np.sin(TAU * (2100 + rng.uniform(-80, 80)) * t) * np.exp(-t * 130)
    return s / np.max(np.abs(s))


def jingles(rng):
    """Бубенцы (тройка, зима)."""
    t = np.arange(int(0.22 * SR)) / SR
    s = sosfilt(_sos("high", 6000), rng.standard_normal(len(t))) * np.exp(-t * 30) * 0.5
    for _ in range(5):
        s += np.sin(TAU * rng.uniform(4200, 8500) * t) * np.exp(-t * rng.uniform(12, 25)) * 0.3
    return s / np.max(np.abs(s))


# ---------------------------------------------------------------- помощники
def trem(M, m, t, dur, gain, pan, rng, rate=0.058):
    """Тремоло балалайки — быстрые повторы на длинной ноте."""
    k = max(1, int(dur / rate))
    for i in range(k):
        M.add(balalaika(m, 0.28, 0.85, rng=rng), t + i * rate + rng.uniform(-0.003, 0.003),
              gain * (1.0 if i == 0 else 0.62), pan=pan, rev=0.28)


def strum(M, inst, notes, t, vel, gain, rng, T=0.4, spread=0.012, rev=0.25):
    for j, m in enumerate(notes):
        M.add(inst(m, T, rng=rng), t + j * spread + rng.uniform(-0.002, 0.002),
              gain * vel * (1 - 0.1 * j), pan=-0.25 + 0.25 * j, rev=rev)


def play(M, fn, phrase, t0, unit, gain, pan, rev, rng, **kw):
    for m, s, l in phrase:
        M.add(fn(m, l * unit * 0.97, rng, **kw), t0 + s * unit, gain, pan=pan, rev=rev)


# ---------------------------------------------------------------- треки
def track_berezka():
    """1. «Берёзка» — лирично и спокойно. 4/4, 72 уд/мин, ля минор. ~67 с."""
    beat = 60 / 72
    e8 = beat / 2
    bar = 4 * beat
    nb = 20
    M = Mix(nb * bar, 21)
    rng = M.rng
    ch = [(45, [57, 60, 64]), (50, [57, 62, 65]), (43, [55, 59, 62]), (48, [55, 60, 64]),
          (41, [57, 60, 65]), (50, [57, 62, 65]), (40, [56, 59, 64]), (45, [57, 60, 64])]
    mel = [
        [(76, 0, 4), (74, 4, 2), (72, 6, 2), (74, 8, 4), (77, 12, 2), (76, 14, 2)],
        [(74, 0, 4), (71, 4, 2), (67, 6, 2), (72, 8, 6), (76, 14, 2)],
        [(72, 0, 4), (69, 4, 2), (65, 6, 2), (69, 8, 4), (74, 12, 4)],
        [(71, 0, 4), (68, 4, 2), (71, 6, 2), (69, 8, 8)],
    ]
    for b in range(nb):
        t0 = b * bar
        root, v = ch[b % 8]
        last = b == nb - 1
        # гусли: перебор вверх-вниз восьмыми
        arp = [v[0], v[1], v[2], v[0] + 12, v[2], v[1] + 12, v[2] + 12, v[1] + 12]
        for i in range(1 if last else 8):
            M.add(gusli(arp[i] + 12, 2.2 if not last else 4.0, 0.7, rng=rng),
                  t0 + i * e8 + rng.uniform(-0.006, 0.006),
                  0.20 * (1.0 if i % 4 == 0 else 0.7), pan=0.35 if i % 2 else -0.1, rev=0.4)
        if last:
            strum(M, gusli, [v[0] + 12, v[1] + 12, v[2] + 12, v[0] + 24], t0 + 0.03, 0.9, 0.18, rng, T=4.0,
                  spread=0.06, rev=0.5)
        M.add(gusli(root, 2.5, 0.4, rng=rng), t0, 0.40, rev=0.2)
        if not last:
            M.add(gusli(root + 7, 2.0, 0.4, rng=rng), t0 + 2 * beat, 0.25, rev=0.2)
        if 2 <= b < nb - 1:
            M.add(pad(v, bar, rng, att=1.0, rel=1.8, cutoff=1100), t0, 0.09, pan=-0.4, rev=0.5)
            M.add(pad(v, bar, rng, att=1.0, rel=1.8, cutoff=1100), t0, 0.09, pan=0.4, rev=0.5)
        if 4 <= b < nb - 1 and (b - 4) % 2 == 0:
            ph = mel[(b % 8) // 2]
            play(M, zhaleika, ph, t0, e8, 0.24, -0.1, 0.45, rng)
            if b >= 12:  # второй проход — гусли подхватывают октавой ниже
                for m, s, l in ph:
                    M.add(gusli(m, 1.5, 0.8, rng=rng), t0 + s * e8, 0.16, pan=0.3, rev=0.4)
    return M


def track_yarmarka():
    """2. «Ярмарка» — весело и задорно. 2/4, 132 уд/мин, ре мажор. ~62 с."""
    beat = 60 / 132
    e8 = beat / 2
    bar = 2 * beat
    nb = 68
    M = Mix(nb * bar, 22)
    rng = M.rng
    cyc = ["D", "A", "D", "A", "D", "G", "A", "D"]
    chord = {"D": [62, 66, 69], "A": [61, 64, 69], "G": [62, 67, 71]}
    bass = {"D": (38, 45), "A": (45, 40), "G": (43, 38)}
    Y = [
        [(78, 1), (76, 1), (74, 1), (76, 1), (73, 1), (76, 1), (81, 2)],
        [(78, 1), (81, 1), (78, 1), (74, 1), (76, 1), (73, 1), (69, 2)],
        [(74, 1), (78, 1), (81, 1), (78, 1), (79, 1), (83, 1), (79, 2)],
        [(76, 1), (73, 1), (69, 1), (73, 1), (74, 4)],
    ]

    def melody(b, t0, who):
        k = b % 8
        if k % 2:
            return
        pos = 0
        for m, l in Y[k // 2]:
            ts = t0 + pos * e8
            if who in ("bal", "both"):
                if l >= 2:
                    trem(M, m, ts, l * e8 * 0.95, 0.30, 0.3, rng)
                else:
                    M.add(balalaika(m, 0.3, 0.9, rng=rng), ts, 0.34, pan=0.3, rev=0.25)
            if who in ("bay", "both"):
                M.add(bayan([m], l * e8 * 0.9, rng), ts, 0.20 if who == "both" else 0.26, pan=-0.2, rev=0.3)
            pos += l

    for b in range(nb):
        t0 = b * bar
        c = cyc[b % 8]
        if b == nb - 1:
            M.add(bayan([38, 50] + chord["D"], 1.6, rng), t0, 0.32, rev=0.35)
            strum(M, balalaika, chord["D"] + [74], t0, 1.0, 0.24, rng, T=1.2)
            M.add(kick(rng), t0, 0.45)
            break
        brk = 36 <= b < 44
        # баян: «бас-аккорд-бас-аккорд»
        if not brk:
            M.add(bayan([bass[c][0]], beat * 0.45, rng, dark=True), t0, 0.30, rev=0.15)
            M.add(bayan(chord[c], e8 * 0.7, rng), t0 + e8, 0.16, pan=-0.15, rev=0.2)
            M.add(bayan([bass[c][1]], beat * 0.45, rng, dark=True), t0 + beat, 0.26, rev=0.15)
            M.add(bayan(chord[c], e8 * 0.7, rng), t0 + 3 * e8, 0.16, pan=-0.15, rev=0.2)
        else:
            M.add(balalaika(bass[c][0], 0.6, 0.4, rng=rng), t0, 0.35, rev=0.1)
            M.add(balalaika(bass[c][1], 0.6, 0.4, rng=rng), t0 + beat, 0.30, rev=0.1)
        # ложки и бубен
        if b >= 4:
            for i in range(4):
                M.add(spoons(rng), t0 + i * e8, (0.20 if i % 2 == 0 else 0.13) * (1.2 if brk else 1.0),
                      pan=0.45, rev=0.1)
            if not brk:
                M.add(frame_drum(rng), t0 + beat, 0.14, pan=-0.35)
                M.add(shaker(rng), t0 + beat, 0.10, pan=-0.35)
                M.add(kick(rng), t0, 0.30, rev=0.05)
        if 20 <= b < 36:
            strum(M, balalaika, chord[c], t0 + e8, 0.6, 0.14, rng, T=0.25)
            strum(M, balalaika, chord[c], t0 + 3 * e8, 0.6, 0.14, rng, T=0.25)
        if 4 <= b < 20:
            melody(b, t0, "bal")
        elif 20 <= b < 36:
            melody(b, t0, "bay")
        elif 44 <= b < nb - 1:
            melody(b, t0, "both")
    return M


def track_zagadka():
    """3. «Загадка» — таинственно, для необычных фактов. 4/4, 80 уд/мин, ми минор. ~66 с."""
    beat = 0.75
    e8 = beat / 2
    bar = 4 * beat
    nb = 22
    M = Mix(nb * bar, 23)
    rng = M.rng
    ch = [(40, [52, 55, 59]), (36, [48, 52, 55]), (45, [45, 48, 52]), (35, [47, 51, 54])]
    Z = [
        [(64, 0, 4), (67, 4, 4), (72, 8, 6), (71, 14, 2), (69, 16, 4), (72, 20, 4), (71, 24, 8)],
        [(79, 0, 6), (78, 6, 2), (76, 8, 4), (72, 12, 4), (69, 16, 6), (72, 22, 2), (71, 24, 4), (66, 28, 4)],
        [(71, 0, 4), (76, 4, 4), (79, 8, 4), (76, 12, 4), (72, 16, 4), (76, 20, 4), (75, 24, 8)],
    ]
    total = nb * bar
    # тёмный бурдон баяна — медленно «дышит»
    for m, g, pn, ph0 in ((40, 0.15, -0.2, 0.0), (47, 0.09, 0.2, 1.9)):
        d = bayan([m], total, rng, att=3.0, rel=2.0, dark=True)
        tt = np.arange(len(d)) / SR
        d *= 0.65 + 0.35 * np.sin(TAU * tt / 12.0 + ph0)
        M.add(d, 0.0, g, pan=pn, rev=0.5)
    for b in range(nb):
        t0 = b * bar
        root, v = ch[b % 4]
        if b % 4 == 0:
            M.add(church_bell(40 if b % 8 == 0 else 47, rng), t0, 0.10, pan=-0.3, rev=0.7)
        if b >= 2:  # глухой пульс балалайки
            for i in range(8):
                m = v[0] + 12 if i % 2 == 0 else v[2] + 12
                M.add(balalaika(m, 0.1, 0.4, dur=0.35, rng=rng), t0 + i * e8 + rng.uniform(-0.004, 0.004),
                      0.15 * (1.0 if i % 4 == 0 else 0.7), pan=0.3 if i % 2 else -0.3, rev=0.25)
        if b >= 4:
            M.add(pad(v, bar, rng, att=1.2, rel=2.0, cutoff=850), t0, 0.08, pan=-0.4, rev=0.5)
            M.add(pad(v, bar, rng, att=1.2, rel=2.0, cutoff=850), t0, 0.08, pan=0.4, rev=0.5)
            for i in range(4):
                M.add(shaker(rng), t0 + i * beat + e8, 0.05, pan=0.35)
        if b in (5, 6, 10, 14, 18):  # блики гуслей
            for k, m in enumerate([v[0] + 24, v[2] + 24, v[1] + 36]):
                M.add(gusli(m, 3.0, 0.9, rng=rng), t0 + k * beat * 0.75, 0.12, pan=0.45, rev=0.65)
        if b >= 8:
            M.add(kick(rng), t0, 0.30, rev=0.1)
            M.add(kick(rng), t0 + 2 * beat, 0.24, rev=0.1)
        if 8 <= b < 20 and (b - 8) % 4 == 0:
            play(M, zhaleika, Z[(b - 8) // 4], t0, e8, 0.22, 0.1, 0.5, rng)
    return M


def track_khorovod():
    """4. «Хоровод» — светло и плавно. 2/4, 96 уд/мин, соль мажор ↔ ми минор. ~63 с."""
    beat = 0.625
    e8 = beat / 2
    bar = 2 * beat
    nb = 50
    M = Mix(nb * bar, 24)
    rng = M.rng
    cyc = ["G", "G", "D", "G", "Em", "Am", "D", "Em"]
    chord = {"G": [62, 67, 71], "D": [62, 66, 69], "Em": [64, 67, 71], "Am": [64, 69, 72]}
    bass = {"G": (43, 38), "D": (38, 45), "Em": (40, 47), "Am": (45, 40)}
    H = [
        [(71, 0, 2), (74, 2, 2), (74, 4, 2), (71, 6, 1), (69, 7, 1)],
        [(69, 0, 2), (66, 2, 2), (67, 4, 4)],
        [(71, 0, 2), (76, 2, 2), (72, 4, 2), (69, 6, 2)],
        [(69, 0, 1), (71, 1, 1), (69, 2, 1), (66, 3, 1), (64, 4, 4)],
    ]
    for b in range(nb):
        t0 = b * bar
        c = cyc[b % 8]
        if b == nb - 1:
            M.add(bayan([40, 52] + chord["Em"], 2.0, rng), t0, 0.30, rev=0.4)
            strum(M, gusli, chord["Em"] + [76], t0, 0.9, 0.18, rng, T=3.0, spread=0.05, rev=0.5)
            break
        M.add(bayan([bass[c][0]], beat * 0.5, rng, dark=True), t0, 0.26, rev=0.2)
        M.add(bayan(chord[c], e8 * 0.8, rng), t0 + e8, 0.13, pan=-0.15, rev=0.25)
        M.add(bayan([bass[c][1]], beat * 0.5, rng, dark=True), t0 + beat, 0.22, rev=0.2)
        M.add(bayan(chord[c], e8 * 0.8, rng), t0 + 3 * e8, 0.13, pan=-0.15, rev=0.25)
        if b >= 18:
            M.add(frame_drum(rng), t0, 0.10, pan=-0.3)
            M.add(shaker(rng), t0 + beat, 0.08, pan=0.4)
        if 18 <= b < 34:  # гусли — перебор шестнадцатыми
            v = chord[c]
            for i, m in enumerate([v[0] + 12, v[1] + 12, v[2] + 12, v[1] + 12] * 2):
                M.add(gusli(m, 1.2, 0.75, rng=rng), t0 + i * e8 / 2, 0.10, pan=0.4, rev=0.35)
        if b >= 2 and (b - 2) % 2 == 0 and b < nb - 1:
            ph = H[(b % 8) // 2]
            if b < 18:
                play(M, zhaleika, ph, t0, e8, 0.25, -0.1, 0.4, rng)
            elif b < 34:
                for m, s, l in ph:
                    if l >= 2:
                        trem(M, m, t0 + s * e8, l * e8 * 0.95, 0.24, 0.25, rng)
                    else:
                        M.add(balalaika(m, 0.35, 0.85, rng=rng), t0 + s * e8, 0.28, pan=0.25, rev=0.25)
            else:
                play(M, zhaleika, ph, t0, e8, 0.22, -0.1, 0.4, rng)
                for m, s, l in ph:
                    M.add(bayan([m - 12], l * e8 * 0.9, rng), t0 + s * e8, 0.12, pan=0.2, rev=0.3)
    return M


def track_skazka():
    """5. «Зимняя сказка» — волшебно, вальс. 3/4, 132 уд/мин, ре минор. ~63 с."""
    beat = 60 / 132
    bar = 3 * beat
    nb = 46
    M = Mix(nb * bar, 25)
    rng = M.rng
    ch = [(38, [62, 65, 69]), (43, [62, 67, 70]), (36, [60, 64, 67]), (41, [60, 65, 69]),
          (46, [62, 65, 70]), (43, [62, 67, 70]), (45, [61, 64, 69]), (38, [62, 65, 69])]
    W = [
        [(74, 0, 2), (77, 2, 1), (82, 3, 2), (79, 5, 1)],
        [(79, 0, 2), (76, 2, 1), (77, 3, 3)],
        [(74, 0, 2), (77, 2, 1), (74, 3, 2), (70, 5, 1)],
        [(73, 0, 2), (76, 2, 1), (74, 3, 3)],
    ]
    for b in range(nb):
        t0 = b * bar
        root, v = ch[b % 8]
        end = b >= nb - 2
        if end:
            if b == nb - 2:
                M.add(gusli(38, 5.0, 0.4, rng=rng), t0, 0.40, rev=0.3)
                strum(M, gusli, [62, 65, 69, 74, 77], t0, 0.9, 0.16, rng, T=5.0, spread=0.07, rev=0.6)
                M.add(glock(86, rng, dur=4.0), t0 + 0.4, 0.16, pan=0.3, rev=0.6)
                M.add(pad(v, 2 * bar, rng, att=0.5, rel=2.0, cutoff=1200), t0, 0.12, rev=0.6)
            continue
        # вальс: бас на 1, аккорд гуслей на 2 и 3
        M.add(gusli(root, 2.5, 0.4, rng=rng), t0, 0.36, rev=0.25)
        for k in (1, 2):
            strum(M, gusli, [m + 12 for m in v], t0 + k * beat, 0.55, 0.11, rng, T=1.2, spread=0.015, rev=0.35)
        M.add(pad(v, bar, rng, att=0.4, rel=1.5, cutoff=1500), t0, 0.08, pan=-0.4, rev=0.5)
        M.add(pad(v, bar, rng, att=0.4, rel=1.5, cutoff=1500), t0, 0.08, pan=0.4, rev=0.5)
        if b >= 28:
            for k in range(3):
                M.add(jingles(rng), t0 + k * beat, 0.07 if k else 0.10, pan=0.45, rev=0.3)
        k = None
        if 4 <= b < 20:
            k, who = b % 8, "bells"
        elif 20 <= b < 28:
            k, who = b % 8, "gusli"
        elif 28 <= b < 44:
            k, who = b % 8, "both"
        if k is not None and k % 2 == 0:
            for m, s, l in W[k // 2]:
                ts = t0 + s * beat
                if who in ("bells", "both"):
                    M.add(glock(m + 12 if who == "both" else m, rng), ts, 0.22, pan=0.25, rev=0.5)
                if who in ("gusli", "both"):
                    M.add(gusli(m, 2.0, 0.85, rng=rng), ts, 0.26 if who == "gusli" else 0.18, pan=-0.2, rev=0.45)
    return M


TRACKS = [
    ("ru01_Berezka_lirichno", track_berezka),
    ("ru02_Yarmarka_veselo", track_yarmarka),
    ("ru03_Zagadka_tainstvenno", track_zagadka),
    ("ru04_Khorovod_svetlo", track_khorovod),
    ("ru05_Zimnyaya_skazka", track_skazka),
]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    only = sys.argv[2:]
    for name, fn in TRACKS:
        if only and not any(o in name for o in only):
            continue
        M = fn()
        wav = os.path.join(out, name + ".wav")
        finish(M, wav)
        master_mp3(wav, os.path.join(out, name + ".mp3"))
        os.remove(wav)
        print("ok", name, round(M.len, 1), "s", flush=True)
