#!/usr/bin/env python3
"""«Зимняя сказка» в разных жанрах: техно, лоу-фай, синтвейв, фонк, рэп (бум-бэп), кино.
Мелодия и гармония — из ru_music.track_skazka (своя музыка). Всё синтезируется с нуля.
Запуск: python3 skazka_remix.py OUT_DIR [фильтр]
"""
import os
import sys

import numpy as np
from scipy.signal import lfilter, sawtooth, sosfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kz_music import SR, Mix, _sos, bowed, finish, master_mp3, pad  # noqa: E402
from ru_music import glock, gusli, jingles  # noqa: E402

TAU = 2 * np.pi


def mf(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# гармония «Зимней сказки»: Dm Gm C F | Bb Gm A Dm
CH = [(38, [62, 65, 69]), (43, [62, 67, 70]), (36, [60, 64, 67]), (41, [60, 65, 69]),
      (46, [62, 65, 70]), (43, [62, 67, 70]), (45, [61, 64, 69]), (38, [62, 65, 69])]
CH7 = [[53, 57, 60, 64], [55, 58, 62, 65], [52, 55, 58, 62], [53, 57, 60, 64],
       [53, 57, 58, 62], [55, 58, 62, 65], [55, 61, 64, 67], [53, 57, 60, 65]]
# мелодия, переложенная на 4/4: (нота, начало, длина) в восьмых, по 2 такта
W4 = [
    [(74, 0, 6), (77, 6, 2), (82, 8, 6), (79, 14, 2)],
    [(79, 0, 6), (76, 6, 2), (77, 8, 8)],
    [(74, 0, 6), (77, 6, 2), (74, 8, 6), (70, 14, 2)],
    [(73, 0, 6), (76, 6, 2), (74, 8, 8)],
]
# оригинальный вальс 3/4: (нота, начало, длина) в четвертях, по 2 такта
W3 = [
    [(74, 0, 2), (77, 2, 1), (82, 3, 2), (79, 5, 1)],
    [(79, 0, 2), (76, 2, 1), (77, 3, 3)],
    [(74, 0, 2), (77, 2, 1), (74, 3, 2), (70, 5, 1)],
    [(73, 0, 2), (76, 2, 1), (74, 3, 3)],
]


# ---------------------------------------------------------------- синтез
def biquad_lp(x, fc, Q=0.707):
    w = TAU * min(fc, SR * 0.45) / SR
    al = np.sin(w) / (2 * Q)
    c = np.cos(w)
    b = np.array([(1 - c) / 2, 1 - c, (1 - c) / 2])
    a = np.array([1 + al, -2 * c, 1 - al])
    return lfilter(b / a[0], a / a[0], x)


def env_ar(n, att, rel_start, rel):
    e = np.ones(n)
    a = max(1, int(att * SR))
    e[:a] = np.linspace(0, 1, a)
    r0 = min(n, int(rel_start * SR))
    if r0 < n:
        e[r0:] = np.linspace(1, 0, n - r0) ** 2
    return e


def saw(f, t, ph=0.0):
    return sawtooth(TAU * f * t + ph)


def supersaw(midis, dur, rng, cutoff=2500, att=0.3, rel=0.8, voices=5):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    dets = np.linspace(-0.14, 0.14, voices)
    for m in midis:
        for d in dets:
            s += saw(mf(m + d), t, rng.uniform(0, TAU))
    s = biquad_lp(s, cutoff, 0.9) * env_ar(n, att, dur, rel)
    return s / (np.max(np.abs(s)) + 1e-9)


def pluck_synth(m, rng, dur=0.5, bright=4500):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = saw(mf(m), t, rng.uniform(0, TAU)) + 0.5 * saw(mf(m + 0.08), t)
    y = biquad_lp(s, bright, 1.2) * np.exp(-t * 14) + biquad_lp(s, 900) * np.exp(-t * 5)
    y[:44] *= np.linspace(0, 1, 44)
    return y / (np.max(np.abs(y)) + 1e-9)


def saw_lead(m, dur, rng, cutoff=3500, att=0.02, rel=0.25, vib=0.12):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    vd = np.clip((t - 0.15) / 0.3, 0, 1) * vib
    s = np.zeros(n)
    for d in (-0.07, 0, 0.07):
        inst = mf(m + d) * 2 ** (vd * np.sin(TAU * 5.5 * t) / 12)
        ph = np.cumsum(inst) / SR
        s += 2 * (ph - np.floor(ph + 0.5))
    s = biquad_lp(s, cutoff, 1.0) * env_ar(n, att, dur, rel)
    return s / (np.max(np.abs(s)) + 1e-9)


def rhodes(midis, dur, rng, rel=0.8):
    """Электропиано (FM)."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in midis:
        f = mf(m)
        idx = 1.8 * np.exp(-t * 3.5) + 0.2
        s += np.sin(TAU * f * t + idx * np.sin(TAU * f * t)) * np.exp(-t * 0.9)
        s += 0.12 * np.sin(TAU * f * 7 * t) * np.exp(-t * 9)
    s *= (0.86 + 0.14 * np.sin(TAU * 4.2 * t)) * env_ar(n, 0.004, dur, rel)
    return s / (np.max(np.abs(s)) + 1e-9)


def bass_808(m, dur, rng, drive=2.2):
    n = int((dur + 0.08) * SR)
    t = np.arange(n) / SR
    f = mf(m) * (1 + 0.6 * np.exp(-t * 45))
    s = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 0.9)
    s = np.tanh(s * drive) / np.tanh(drive)
    s *= env_ar(n, 0.003, dur, 0.08)
    return s / (np.max(np.abs(s)) + 1e-9)


def acid(m, dur, rng, cutoff, Q=4.0):
    n = int((dur + 0.02) * SR)
    t = np.arange(n) / SR
    s = saw(mf(m), t)
    y = biquad_lp(s, cutoff * (0.4 + 0.6 * np.exp(-t * 18)) .mean(), Q) * np.exp(-t * 7)
    y *= env_ar(n, 0.002, dur, 0.02)
    return y / (np.max(np.abs(y)) + 1e-9)


def cowbell(m, rng, dur=0.22):
    """808-ковбелл (фонк), подстроен под ноту мелодии."""
    f = mf(m)
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for ff in (f, f * 1.48):
        for k in range(1, 12, 2):
            if ff * k < 15000:
                s += np.sin(TAU * ff * k * t) / k
    s = sosfilt(_sos("band", [700, 5000]), s) * np.exp(-t * 14)
    s[:44] *= np.linspace(0, 1, 44)
    return s / (np.max(np.abs(s)) + 1e-9)


def kick909(rng, punch=1.0, dist=1.0):
    t = np.arange(int(0.5 * SR)) / SR
    f = 50 + 130 * np.exp(-t * 28)
    s = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 6)
    click = sosfilt(_sos("high", 2500), rng.standard_normal(len(t))) * np.exp(-t * 400) * 0.4 * punch
    s = s + click
    if dist > 1:
        s = np.tanh(s * dist) / np.tanh(dist)
    return s / np.max(np.abs(s))


def clap(rng):
    t = np.arange(int(0.35 * SR)) / SR
    nz = sosfilt(_sos("band", [900, 3200]), rng.standard_normal(len(t)))
    e = np.zeros_like(t)
    for d in (0.0, 0.011, 0.022):
        e += np.where(t >= d, np.exp(-(t - d) * 90), 0)
    e += np.where(t >= 0.03, np.exp(-(t - 0.03) * 14), 0) * 0.6
    s = nz * e
    return s / np.max(np.abs(s))


def snare(rng, tone=185, dec=14, lp=8000):
    t = np.arange(int(0.4 * SR)) / SR
    nz = sosfilt(_sos("band", [250, lp]), rng.standard_normal(len(t))) * np.exp(-t * dec)
    s = nz + 0.8 * np.sin(TAU * tone * t) * np.exp(-t * 25)
    return s / np.max(np.abs(s))


def hat(rng, open_=False):
    t = np.arange(int((0.3 if open_ else 0.06) * SR)) / SR
    s = sosfilt(_sos("high", 7500), rng.standard_normal(len(t))) * np.exp(-t * (11 if open_ else 85))
    return s / np.max(np.abs(s))


def timpani(m, rng):
    t = np.arange(int(2.0 * SR)) / SR
    f = mf(m) * (1 + 0.04 * np.exp(-t * 6))
    ph = TAU * np.cumsum(f) / SR
    s = (np.sin(ph) + 0.5 * np.sin(1.5 * ph) + 0.25 * np.sin(2.0 * ph)) * np.exp(-t * 1.6)
    s += sosfilt(_sos("low", 400), rng.standard_normal(len(t))) * np.exp(-t * 30) * 0.8
    return s / np.max(np.abs(s))


def swell(dur, rng):
    """Нарастающий «реверс-тарелка» перед кульминацией."""
    t = np.arange(int(dur * SR)) / SR
    s = sosfilt(_sos("band", [3000, 9000]), rng.standard_normal(len(t))) * (t / dur) ** 3
    return s / np.max(np.abs(s))


def vinyl(dur, rng):
    n = int(dur * SR)
    hiss = sosfilt(_sos("band", [800, 6000]), rng.standard_normal(n)) * 0.06
    clicks = np.zeros(n)
    pos = rng.integers(0, n, int(dur * 7))
    clicks[pos] = rng.uniform(0.3, 1.0, len(pos)) * rng.choice([-1, 1], len(pos))
    clicks = sosfilt(_sos("band", [1500, 7000]), clicks)
    s = hiss + clicks
    return s / np.max(np.abs(s))


def ensemble(m, dur, rng, att=0.4, rel=0.8):
    s = sum(bowed(m + d, dur, rng, att=att, rel=rel, vib=0.12) for d in (-0.06, 0.0, 0.06))
    return s / np.max(np.abs(s))


def melody_bar(b, phrases):
    """Фраза мелодии, которая начинается в такте b (по 2 такта, по кругу из 8)."""
    return phrases[(b % 8) // 2] if b % 2 == 0 else None


# ---------------------------------------------------------------- треки
def techno():
    """Техно, 128 BPM."""
    beat = 60 / 128
    e8, s16, bar = beat / 2, beat / 4, 4 * beat
    nb = 32
    M = Mix(nb * bar, 31)
    rng = M.rng
    for b in range(nb):
        t0 = b * bar
        root, v = CH[b % 8]
        if b == nb - 1:
            M.add(kick909(rng), t0, 0.6)
            M.add(supersaw(v, 1.5, rng, cutoff=3000, att=0.01, rel=2.0), t0, 0.18, rev=0.5)
            M.add(glock(86, rng, dur=3.0), t0, 0.2, pan=0.3, rev=0.6)
            break
        brk = 16 <= b < 20
        drop = b >= 20
        if not brk:
            for i in range(4):
                M.add(kick909(rng), t0 + i * beat, 0.55, rev=0.02)
        for i in range(4):
            M.add(hat(rng), t0 + i * beat + e8, 0.12 if b >= 2 else 0.07, pan=0.3)
            if drop:
                M.add(hat(rng, True), t0 + i * beat + e8, 0.06, pan=0.3)
        if b >= 8 and not brk:
            M.add(clap(rng), t0 + beat, 0.22, rev=0.3)
            M.add(clap(rng), t0 + 3 * beat, 0.22, rev=0.3)
            for i in range(16):
                if i % 2:
                    M.add(hat(rng), t0 + i * s16, 0.05, pan=-0.3)
        if b >= 4 and not brk:  # «катящийся» бас на слабых восьмых
            for i in range(4):
                cut = 500 + 900 * (0.5 + 0.5 * np.sin(TAU * (b * 4 + i) / 32))
                M.add(acid(root + 12, e8 * 0.9, rng, cut), t0 + i * beat + e8, 0.30, rev=0.05)
        if b >= 8:  # арпеджио колокольчиков шестнадцатыми
            arp = [v[0] + 12, v[1] + 12, v[2] + 12, v[1] + 12]
            for i in range(16):
                M.add(glock(arp[i % 4], rng, dur=0.6), t0 + i * s16, 0.06 if brk else 0.08, pan=0.4, rev=0.35)
        if brk or drop:
            M.add(supersaw(v, bar, rng, cutoff=1200 if brk else 2200, att=0.4 if brk else 0.05, rel=0.6),
                  t0, 0.10, pan=-0.3, rev=0.5)
            ph = melody_bar(b, W4)
            if ph:
                for m, s, l in ph:
                    M.add(glock(m, rng), t0 + s * e8, 0.20, pan=0.15, rev=0.5)
                    if drop:
                        M.add(pluck_synth(m, rng, dur=l * e8), t0 + s * e8, 0.16, pan=-0.15, rev=0.35)
        if b == 19:
            M.add(swell(bar, rng), t0, 0.035, rev=0.3)
    return M


def lofi():
    """Лоу-фай хип-хоп, 82 BPM, свинг."""
    beat = 60 / 82
    e8, bar = beat / 2, 4 * beat
    nb = 22
    M = Mix(nb * bar, 32)
    rng = M.rng
    M.add(vinyl(nb * bar + 2, rng), 0.0, 0.03, rev=0.0)
    sw = e8 * 0.18  # свинг
    for b in range(nb):
        t0 = b * bar
        root, _ = CH[b % 8]
        v = CH7[b % 8]
        last = b == nb - 1
        M.add(sosfilt(_sos("low", 3500), rhodes(v, bar * (0.6 if last else 0.95), rng)), t0, 0.22, pan=-0.1, rev=0.35)
        M.add(bass_808(root, beat * 1.6 if not last else 2.5, rng, drive=1.3), t0, 0.32, rev=0.05)
        if last:
            break
        M.add(bass_808(root, beat * 0.8, rng, drive=1.3), t0 + 2.5 * beat, 0.24, rev=0.05)
        if b >= 2:
            M.add(sosfilt(_sos("low", 2500), kick909(rng, punch=0.3)), t0, 0.40)
            M.add(sosfilt(_sos("low", 2500), kick909(rng, punch=0.3)), t0 + 2.5 * beat, 0.30)
            for k in (1, 3):
                M.add(snare(rng, tone=200, dec=18, lp=4500), t0 + k * beat, 0.20, rev=0.25)
            for i in range(8):
                M.add(sosfilt(_sos("low", 9000), hat(rng)), t0 + i * e8 + (sw if i % 2 else 0),
                      0.07 if i % 2 else 0.09, pan=0.3)
        if b >= 6:
            ph = melody_bar(b, W4)
            if ph:
                for m, s, l in ph:
                    ts = t0 + s * e8 + rng.uniform(0, 0.015)
                    M.add(sosfilt(_sos("low", 5000), glock(m, rng)), ts, 0.20, pan=0.2, rev=0.45)
                    if b >= 14:
                        M.add(sosfilt(_sos("low", 3000), rhodes([m], l * e8, rng, rel=0.4)), ts, 0.10,
                              pan=-0.25, rev=0.4)
    return M


def synthwave():
    """Синтвейв, 100 BPM."""
    beat = 0.6
    e8, s16, bar = beat / 2, beat / 4, 4 * beat
    nb = 26
    M = Mix(nb * bar, 33)
    rng = M.rng
    for b in range(nb):
        t0 = b * bar
        root, v = CH[b % 8]
        last = b == nb - 1
        M.add(supersaw([m - 12 for m in v], bar * (0.5 if last else 1.0), rng, cutoff=1800, att=0.25,
                       rel=1.5 if last else 0.5), t0, 0.13, pan=-0.2, rev=0.5)
        if last:
            M.add(kick909(rng), t0, 0.5)
            M.add(snare(rng), t0, 0.3, rev=0.8)
            break
        brk = 18 <= b < 22
        for i in range(16):  # арпеджио с «эхом»
            m = [v[0], v[1], v[2], v[1] + 12][i % 4]
            M.add(pluck_synth(m, rng, dur=0.35, bright=3500), t0 + i * s16, 0.10, pan=0.35, rev=0.3)
            M.add(pluck_synth(m, rng, dur=0.35, bright=2000), t0 + i * s16 + 3 * s16, 0.04, pan=-0.35, rev=0.3)
        if b >= 4 and not brk:
            for i in range(8):
                m = root + 12 if i % 2 else root
                M.add(sosfilt(_sos("low", 900), saw_lead(m, e8 * 0.8, rng, cutoff=1200, vib=0)), t0 + i * e8,
                      0.20, rev=0.05)
            M.add(kick909(rng), t0, 0.5)
            M.add(kick909(rng), t0 + 2 * beat, 0.5)
            for k in (1, 3):
                M.add(snare(rng, dec=9), t0 + k * beat, 0.26, rev=0.8)
            for i in range(8):
                M.add(hat(rng), t0 + i * e8, 0.05, pan=0.3)
        ph = melody_bar(b, W4)
        if ph and (10 <= b < 18 or b >= 22):
            for m, s, l in ph:
                M.add(saw_lead(m, l * e8 * 0.95, rng), t0 + s * e8, 0.18, pan=0.05, rev=0.45)
        if ph and brk:
            for m, s, l in ph:
                M.add(glock(m, rng), t0 + s * e8, 0.20, pan=0.2, rev=0.6)
        if b == 21:
            M.add(swell(bar, rng), t0, 0.035)
    return M


def phonk():
    """Фонк (дрифт), 140 BPM, половинный размер."""
    beat = 60 / 140
    e8, s16, bar = beat / 2, beat / 4, 4 * beat
    nb = 36
    M = Mix(nb * bar, 34)
    rng = M.rng
    for b in range(nb):
        t0 = b * bar
        root, v = CH[b % 8]
        last = b == nb - 1
        intro = b < 4
        brk = 20 <= b < 24
        ph = melody_bar(b, W4)
        if intro or brk:
            M.add(pad(v, bar, rng, att=0.5, rel=1.2, cutoff=1400), t0, 0.10, rev=0.5)
            if ph:
                for m, s, l in ph:
                    M.add(glock(m, rng), t0 + s * e8, 0.22, pan=0.2, rev=0.6)
        if last:
            M.add(kick909(rng, dist=3), t0, 0.55)
            M.add(bass_808(root - 12 if root > 40 else root, 2.5, rng), t0, 0.45)
            M.add(cowbell(74, rng, dur=0.8), t0, 0.22, rev=0.4)
            break
        if b >= 2:
            M.add(bass_808(root - 12 if root > 40 else root, beat * 2.4, rng), t0, 0.42 if not brk else 0.32)
            if not brk:
                M.add(bass_808(root - 12 if root > 40 else root, beat * 1.2, rng), t0 + 2.75 * beat, 0.34)
        if b >= 4 and not brk:
            M.add(kick909(rng, dist=3), t0, 0.50)
            M.add(kick909(rng, dist=3), t0 + 2.5 * beat, 0.42)
            M.add(clap(rng), t0 + 2 * beat, 0.26, rev=0.25)
            M.add(snare(rng, dec=20), t0 + 2 * beat, 0.14, rev=0.25)
            roll = b % 4 == 3
            for i in range(8 if not roll else 6):
                M.add(hat(rng), t0 + i * e8, 0.09, pan=0.3)
            if roll:  # триольная дробь хэтов в конце фразы
                for i in range(6):
                    M.add(hat(rng), t0 + 3 * beat + i * beat / 6, 0.07, pan=0.3)
            if ph:  # ковбелл: каждая длинная нота дробится на восьмые
                for m, s, l in ph:
                    for k in range(max(1, l)):
                        M.add(cowbell(m, rng), t0 + (s + k) * e8, 0.20 if k == 0 else 0.14, pan=0.15, rev=0.3)
    return M


def boombap():
    """Рэп-бит (бум-бэп), 90 BPM. Минусовка без голоса."""
    beat = 60 / 90
    e8, bar = beat / 2, 4 * beat
    nb = 24
    M = Mix(nb * bar, 35)
    rng = M.rng
    M.add(vinyl(nb * bar + 2, rng), 0.0, 0.022, rev=0.0)
    sw = e8 * 0.12
    for b in range(nb):
        t0 = b * bar
        root, v = CH[b % 8]
        last = b == nb - 1
        # «сэмпл»: нарезка колокольчиков и гуслей на аккорд, как с пластинки
        chop = [(0, v[0] + 12), (3, v[2] + 12), (6, v[1] + 12)]
        for pos, m in chop:
            M.add(sosfilt(_sos("low", 4500), gusli(m, 1.4, 0.7, rng=rng)), t0 + pos * e8, 0.16, pan=-0.2, rev=0.35)
        M.add(sosfilt(_sos("low", 2200), rhodes([m - 12 for m in v], bar * 0.9, rng)), t0, 0.10, rev=0.3)
        M.add(bass_808(root, beat * 1.4 if not last else 2.5, rng, drive=1.6), t0, 0.34)
        if last:
            M.add(kick909(rng, punch=0.6), t0, 0.5)
            break
        M.add(bass_808(root, beat * 0.9, rng, drive=1.6), t0 + 2.5 * beat, 0.26)
        if b >= 2:
            # классический рисунок: бочка 1, «и» 2, 3½; снейр 2 и 4
            for tb, g in ((0, 0.5), (1.5, 0.34), (2.5, 0.42)):
                M.add(sosfilt(_sos("low", 3500), kick909(rng, punch=0.8, dist=1.5)), t0 + tb * beat, g)
            for k in (1, 3):
                M.add(snare(rng, tone=190, dec=12, lp=7000), t0 + k * beat, 0.30, rev=0.2)
                M.add(clap(rng), t0 + k * beat, 0.08, rev=0.2)
            for i in range(8):
                M.add(hat(rng), t0 + i * e8 + (sw if i % 2 else 0), 0.08 if i % 2 else 0.11, pan=0.3)
        ph = melody_bar(b, W4)
        if ph and b >= 8 and not (16 <= b < 18):
            for m, s, l in ph:
                M.add(sosfilt(_sos("low", 6000), glock(m, rng)), t0 + s * e8, 0.17, pan=0.25, rev=0.4)
    return M


def cinema():
    """Эпичная киноверсия, вальс 3/4, 120 BPM."""
    beat = 0.5
    bar = 3 * beat
    nb = 42
    M = Mix(nb * bar, 36)
    rng = M.rng
    for b in range(nb):
        t0 = b * bar
        root, v = CH[b % 8]
        ph = W3[(b % 8) // 2] if b % 2 == 0 else None
        climax = 32 <= b < 40
        if b >= nb - 2:
            if b == nb - 2:
                M.add(timpani(38, rng), t0, 0.5, rev=0.4)
                for m in (50, 57, 62, 65, 69, 74):
                    M.add(ensemble(m, 2 * bar, rng, att=0.05, rel=2.5), t0, 0.08, pan=(m - 62) / 20, rev=0.6)
                M.add(glock(86, rng, dur=4.0), t0 + 0.3, 0.2, pan=0.3, rev=0.7)
            continue
        dyn = 0.6 if b < 8 else (0.8 if b < 24 else (0.8 + 0.2 * (b - 24) / 8 if b < 32 else 1.0))
        # струнные — аккорд на весь такт
        for j, m in enumerate(v):
            M.add(ensemble(m - 12, bar, rng, att=0.3, rel=0.6), t0, 0.07 * dyn, pan=-0.4 + 0.4 * j, rev=0.55)
        M.add(ensemble(root, bar, rng, att=0.2, rel=0.6), t0, 0.10 * dyn, rev=0.4)
        if b >= 8:  # пиццикато вальса на 2 и 3
            for k in (1, 2):
                for m in v:
                    M.add(gusli(m, 0.5, 0.6, rng=rng), t0 + k * beat, 0.06 * dyn, pan=0.3, rev=0.4)
        if b >= 24:
            M.add(timpani(root if root < 44 else root - 12, rng), t0, 0.22 * dyn, rev=0.4)
        if climax:
            for k in (1, 2):
                M.add(jingles(rng), t0 + k * beat, 0.06, pan=0.45, rev=0.3)
        if b == 30:
            M.add(swell(2 * bar, rng), t0, 0.04, rev=0.4)
        if ph:
            for m, s, l in ph:
                ts = t0 + s * beat
                dur = l * beat
                if b < 8:
                    M.add(glock(m, rng), ts, 0.22, pan=0.2, rev=0.6)
                elif b < 24:
                    M.add(ensemble(m, dur * 0.95, rng, att=0.12, rel=0.4), ts, 0.20, pan=-0.1, rev=0.5)
                    M.add(glock(m + 12, rng), ts, 0.08, pan=0.3, rev=0.6)
                else:
                    M.add(ensemble(m, dur * 0.95, rng, att=0.1, rel=0.4), ts, 0.20 * dyn, pan=-0.1, rev=0.5)
                    M.add(saw_lead(m - 12, dur * 0.95, rng, cutoff=1800, att=0.06, vib=0.08), ts, 0.13 * dyn,
                          pan=0.1, rev=0.5)
                    M.add(glock(m + 12, rng), ts, 0.10, pan=0.3, rev=0.6)
    return M


TRACKS = [
    ("skazka_01_Tehno", techno),
    ("skazka_02_LoFi", lofi),
    ("skazka_03_Synthwave", synthwave),
    ("skazka_04_Fonk", phonk),
    ("skazka_05_Rep_bit", boombap),
    ("skazka_06_Kino_epik", cinema),
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
        finish(M, wav, t60=2.0)
        master_mp3(wav, os.path.join(out, name + ".mp3"))
        os.remove(wav)
        print("ok", name, round(M.len, 1), "s", flush=True)
