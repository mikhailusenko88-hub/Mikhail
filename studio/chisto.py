"""Чистые инструменты: у каждого звука только нижние призвуки (редкий спектр). Никаких шумов, никакой «пилы»:
бас — почти чистый тон, струнные и хор — несколько призвуков, орган — флейтовый, большой барабан — без гула ниже 55 Гц.
Причина: десятки расстроенных голосов с 60 призвуками каждый сливаются в треск и шипение (12 ноября 2026)."""
import math

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, sosfiltfilt, fftconvolve

from theme import SR, hz, drift, body_string, compressor
from rassvet4 import hall_dark

rng = np.random.default_rng(404)


# ---------------------------------------------------------------- спектры
def sp_strings(fc=1800.0, tilt=1.3):
    return lambda h, fh: body_string(fh) / h ** tilt * math.exp(-fh / fc)


def sp_bass(fc=320.0):
    return lambda h, fh: 1.0 / h ** 1.5 * math.exp(-fh / fc)


def sp_choir(vowel):
    return lambda h, fh: (0.01 + sum(a * math.exp(-((fh - c) / w) ** 2) for c, a, w in vowel)) / h ** 0.7


def _table(f_mid, spec, fmax):
    N = 4096
    ph = np.arange(N) / N * 2 * np.pi
    w = np.zeros(N)
    for h in range(1, 61):
        fh = f_mid * h
        if h > 1 and fh > fmax:
            break
        w += spec(h, fh) * np.sin(h * ph + rng.uniform(0, 6.28))
    w *= 0.26 / (np.sqrt(np.mean(w ** 2)) + 1e-9)      # громкость по энергии, как у прежних струнных (а не по пику)
    return np.append(w, w[0])


def _play(tab, fcurve, ph0):
    phase = np.cumsum(fcurve) / SR + ph0
    phase -= np.floor(phase)
    return np.interp(phase * (len(tab) - 1), np.arange(len(tab)), tab)


def _cos_in(t, d):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(t / d, 0, 1))


# ---------------------------------------------------------------- связная линия с чистым спектром
def clean_line(notes, spec, voices=3, att=0.9, rel=2.5, glide=0.05, vib=0.003, fmax=2600.0, det=6.0, lo_hz=None):
    """notes = [(начало, конец, midi, громкость)]; призвуки только до fmax (на средней ноте линии); без шумов.
    lo_hz — ноты ниже этой частоты поднимаются на октаву. Возвращает (сигнал, время начала)."""
    if lo_hz:
        fixed = []
        for a, b, mi, v in notes:
            while hz(mi) < lo_hz:
                mi += 12
            fixed.append((a, b, mi, v))
        notes = fixed
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
    sl = int((notes[-1][1] - t0) * CR)
    pitch[sl:] = notes[-1][2]
    since[sl:] = since[sl - 1] + np.arange(nc - sl) / CR
    amp = gaussian_filter1d(amp, 0.06 * CR)
    xa = np.arange(n) / SR * CR
    up = lambda c: np.interp(xa, np.arange(nc), c)  # noqa: E731
    tt = np.arange(n) / SR + t0
    env = _cos_in(tt - notes[0][0] + 0.05, att) * (1 - _cos_in(tt - (t1 - rel), rel))
    sa = up(gaussian_filter1d(since, 0.02 * CR))
    tab = _table(hz(float(np.median([x[2] for x in notes]))), spec, fmax)
    out = np.zeros(n)
    for v in range(voices):
        lp = up(gaussian_filter1d(pitch, rng.uniform(0.7, 1.2) * glide * CR))
        d = rng.uniform(-det, det) / 1200 if voices > 1 else 0.0
        vd = vib * np.clip((sa - rng.uniform(0.15, 0.3)) / 0.4, 0, 1)
        lf = (lp - 69) / 12 + d + vd * np.sin(2 * np.pi * rng.uniform(4.7, 5.8) * tt + rng.uniform(0, 6.28)) / math.log(2) \
            + drift(n, 3 if voices > 1 else 1) / math.log(2)
        out += _play(tab, 440.0 * 2 ** lf, rng.uniform(0, 1))
    return up(amp) * env * out / voices, t0


# ---------------------------------------------------------------- орган: флейтовый, без «пилы»
def organ_soft(midi, dur, vel, rel=0.7, bright=False, deep=False):
    f0 = hz(midi)
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    if deep:                                               # педаль: почти чистый тон, нижняя октава только если она не ниже 55 Гц
        parts = [(1.0, 1.0), (2.0, 0.22), (3.0, 0.10), (4.0, 0.03)]
        if f0 / 2 >= 55:
            parts.append((0.5, 0.55))
    else:
        parts = [(1.0, 1.0), (2.0, 0.30), (3.0, 0.14), (4.0, 0.06), (5.0, 0.03)]
        if bright:                                         # тихая октава 4' для кульминации
            parts += [(2.0 * 2 ** (2.5 / 1200), 0.16), (4.0 * 2 ** (2.5 / 1200), 0.04), (6.0, 0.015)]
    ph = 2 * np.pi * np.cumsum(f0 * np.exp(drift(n, 0.6))) / SR
    out = np.zeros(n)
    norm = 0.0
    for r, a in parts:
        if f0 * r > 6000:
            continue
        out += a * np.sin(r * ph + rng.uniform(0, 6.28))
        norm += a
    return vel * 0.39 * out / norm * _cos_in(t, 0.09) * (1 - _cos_in(t - dur, rel))


# ---------------------------------------------------------------- большой барабан: основной тон 60 Гц, без гула
def taiko(vel):
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    f = 60 * (1 + 0.5 * np.exp(-t / 0.03))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = 0.8 * np.sin(ph) * np.exp(-t / 0.32) + 0.4 * np.sin(1.59 * ph + 1) * np.exp(-t / 0.14) + 0.18 * np.sin(2.3 * ph) * np.exp(-t / 0.07)
    return vel * s * _cos_in(t, 0.005) * (1 - _cos_in(t - 1.0, 0.2))


# ---------------------------------------------------------------- мастеринг: без насыщения, срез гула ниже 40 Гц
HP = butter(2, 40, btype="high", fs=SR, output="sos")


def master_clean(bus, air=0.3):
    irL, irR = hall_dark(11), hall_dark(23)
    L = bus.L + 0.55 * fftconvolve(bus.sL + 0.35 * bus.sR, irL)[:len(bus.L)]
    R = bus.R + 0.55 * fftconvolve(bus.sR + 0.35 * bus.sL, irR)[:len(bus.R)]
    out = []
    for ch in (L, R):
        ch = sosfiltfilt(HP, ch)
        band = gaussian_filter1d(ch, SR / (2 * math.pi * 450)) - gaussian_filter1d(ch, SR / (2 * math.pi * 150))
        ch = ch - 0.22 * band
        hi = ch - gaussian_filter1d(ch, SR / (2 * math.pi * 4500))
        out.append(ch + air * hi)
    L, R = out
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = compressor(L / pk, R / pk, thr_db=-15, ratio=1.8)
    fi = int(0.03 * SR)
    for ch in (L, R):
        ch[:fi] *= np.linspace(0, 1, fi)
    return L, R


# ---------------------------------------------------------------- арфа с мягким щипком и гул вместо дроби
def harp(midi, vel):
    f0 = hz(midi)
    n = int(3.2 * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for h in range(1, 9):
        fh = f0 * h
        if fh > 6000:
            break
        s += (1 / h ** 1.4) * np.sin(2 * np.pi * fh * t + (rng.uniform(0, 6.28) if h > 1 else 0)) * np.exp(-t * (0.9 + 1.4 * h) * (f0 / 300) ** 0.3)
    return vel * s * _cos_in(t, 0.008) * np.clip((3.2 - t) / 0.3, 0, 1)


def low_swell(midi, dur, vel):
    """нарастающий гул литавры перед кульминацией: один плавный звук вместо дроби из отдельных ударов"""
    f0 = hz(midi)
    n = int((dur + 0.5) * SR)
    t = np.arange(n) / SR
    env = np.where(t < dur, (t / dur) ** 2, np.exp(-(t - dur) / 0.15)) * (0.8 + 0.2 * np.sin(2 * np.pi * 8 * t))
    s = np.sin(2 * np.pi * f0 * t) + 0.5 * np.sin(2 * np.pi * 1.5 * f0 * t + 1) + 0.25 * np.sin(2 * np.pi * 1.98 * f0 * t + 2)
    return vel * s * env / 1.75
