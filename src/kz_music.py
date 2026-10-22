#!/usr/bin/env python3
"""Фоновые треки в казахском стиле для канала «Білесің бе?».
Всё синтезируется с нуля (своя музыка, без чужих прав):
домбра — Karplus-Strong, кобыз — смычковый синтез, сыбызгы — флейта, ударные — синтез.
Запуск: python3 kz_music.py OUT_DIR
"""
import json
import os
import subprocess
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

SR = 44100


def mf(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _sos(kind, f):
    return butter(2, f, kind, fs=SR, output="sos")


HP60 = _sos("high", 60)
BODY1 = _sos("band", [170, 300])
BODY2 = _sos("band", [420, 700])


# ---------------------------------------------------------------- инструменты
_cache = {}


def dombra(m, T=1.0, bright=0.6, dur=None, rng=None, var=3):
    """Щипок домбры. Кэш с несколькими вариантами, чтобы не было «пулемёта»."""
    key = (m, round(T, 3), round(bright, 2), dur)
    if key not in _cache:
        _cache[key] = [_dombra(m, T, bright, dur, np.random.default_rng(hash(key) % 2**32 + i)) for i in range(var)]
    vs = _cache[key]
    return vs[rng.integers(len(vs))] if rng is not None else vs[0]


def _dombra(m, T, bright, dur, rng):
    f = mf(m)
    dur = dur or min(4 * T + 0.3, 6.0)
    P = SR / f - 0.5          # нужная задержка петли (усреднитель даёт +0.5)
    N = int(P)
    d = P - N
    if d < 0.1:
        N -= 1
        d += 1.0
    C = (1 - d) / (1 + d)     # дробная задержка — allpass, чтобы высокие ноты не «плыли»
    n = int(dur * SR)
    exc = rng.uniform(-1, 1, 2 * N)
    exc = sosfilt(_sos("low", 400 + 7000 * bright), exc)[N:]
    # позиция щипка (гребёнка) — характерный «носовой» тембр домбры
    p = max(1, int(N * 0.18))
    exc = exc - 0.6 * np.roll(exc, p)
    x = np.zeros(n)
    x[:N] = exc
    g = np.exp(-1.0 / (f * T))
    a = np.zeros(N + 3)
    a[0] = 1.0
    a[1] = C
    a[N] -= g / 2 * C
    a[N + 1] -= g / 2 * (1 + C)
    a[N + 2] -= g / 2
    y = lfilter([1.0, C], a, x)
    y = y + 0.8 * sosfilt(BODY1, y) + 0.4 * sosfilt(BODY2, y)
    y = sosfilt(HP60, y)
    k = 88
    y[:k] *= np.linspace(0, 1, k)
    k = int(0.03 * SR)
    y[-k:] *= np.linspace(1, 0, k)
    return y / (np.max(np.abs(y)) + 1e-9)


def pad(midis, dur, rng, att=0.8, rel=1.4, cutoff=1300):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in midis:
        for d in (-0.08, 0.0, 0.08):
            f = mf(m) * 2 ** (d / 12)
            ph = rng.uniform(0, 2 * np.pi)
            for k in range(1, 7):
                if f * k < 12000:
                    s += np.sin(2 * np.pi * f * k * t + ph * k) / k
    env = np.ones(n)
    a = int(att * SR)
    env[:a] = np.linspace(0, 1, a) ** 2
    r0 = int(dur * SR)
    env[r0:] = np.linspace(1, 0, n - r0) ** 2
    s = sosfilt(_sos("low", cutoff), s * env)
    return s / (np.max(np.abs(s)) + 1e-9)


def bowed(m, dur, rng, att=0.18, rel=0.35, vib=0.18, bright=1.0):
    """Кобыз: смычковый тон с вибрато и шумом смычка."""
    f = mf(m)
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    vd = np.clip((t - 0.25) / 0.4, 0, 1) * vib
    inst = f * 2 ** (vd * np.sin(2 * np.pi * 5.2 * t + rng.uniform(0, 6)) / 12)
    ph = 2 * np.pi * np.cumsum(inst) / SR
    s = np.zeros(n)
    for k in range(1, 14):
        if f * k < 14000:
            s += np.sin(k * ph) / k * (1.0 if k % 2 else 0.6)
    noise = sosfilt(_sos("band", [min(f * 2, 3000), min(f * 6, 9000)]), rng.standard_normal(n)) * 0.25
    s = s + noise
    s = 0.5 * s + sosfilt(_sos("band", [450, 2600 * bright]), s) * 1.2
    env = np.ones(n)
    a = int(att * SR)
    env[:a] = np.linspace(0, 1, a) ** 1.5
    r0 = int(dur * SR)
    env[r0:] = np.linspace(1, 0, n - r0) ** 2
    s *= env
    return s / (np.max(np.abs(s)) + 1e-9)


def flute(m, dur, rng, att=0.07, rel=0.18):
    """Сыбызгы: флейта с дыханием."""
    f = mf(m)
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    vd = np.clip((t - 0.2) / 0.3, 0, 1) * 0.14
    inst = f * 2 ** (vd * np.sin(2 * np.pi * 5.0 * t) / 12)
    ph = 2 * np.pi * np.cumsum(inst) / SR
    s = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.07 * np.sin(3 * ph)
    breath = sosfilt(_sos("band", [f * 0.9, min(f * 3, 12000)]), rng.standard_normal(n)) * 0.35
    env = np.ones(n)
    a = int(att * SR)
    env[:a] = np.linspace(0, 1, a)
    r0 = int(dur * SR)
    env[r0:] = np.linspace(1, 0, n - r0) ** 2
    benv = env * (0.5 + 0.5 * np.exp(-t * 8))
    s = s * env + breath * benv
    return s / (np.max(np.abs(s)) + 1e-9)


def kick(rng):
    t = np.arange(int(0.45 * SR)) / SR
    f = 45 + 75 * np.exp(-t * 35)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)
    return s / np.max(np.abs(s))


def frame_drum(rng):
    """Дауылпаз — рамочный барабан."""
    t = np.arange(int(0.35 * SR)) / SR
    nz = sosfilt(_sos("band", [120, 900]), rng.standard_normal(len(t))) * np.exp(-t * 26)
    s = nz + 2.0 * np.sin(2 * np.pi * 165 * t) * np.exp(-t * 16)
    return s / np.max(np.abs(s))


def shaker(rng):
    t = np.arange(int(0.09 * SR)) / SR
    s = sosfilt(_sos("high", 5000), rng.standard_normal(len(t))) * np.exp(-t * 55)
    return s / np.max(np.abs(s))


# ---------------------------------------------------------------- микшер
class Mix:
    def __init__(self, dur, seed):
        self.len = dur
        self.n = int((dur + 4.0) * SR)
        self.dry = np.zeros((2, self.n))
        self.wet = np.zeros((2, self.n))
        self.rng = np.random.default_rng(seed)

    def add(self, sig, t, gain=1.0, pan=0.0, rev=0.25):
        i = int(t * SR)
        if i >= self.n or i < 0:
            return
        sig = sig[: self.n - i]
        th = (pan + 1) * np.pi / 4
        for ch, w in ((0, np.cos(th)), (1, np.sin(th))):
            self.dry[ch, i : i + len(sig)] += sig * gain * w
            self.wet[ch, i : i + len(sig)] += sig * gain * w * rev

    def strum(self, notes, t, vel, T=0.4, bright=0.6, gain=0.22, spread=0.010, rev=0.25):
        for j, m in enumerate(notes):
            jit = self.rng.uniform(-0.002, 0.002)
            self.add(dombra(m, T, bright, rng=self.rng), t + j * spread + jit,
                     gain * vel * (1 - 0.12 * j), pan=-0.25 + 0.25 * j, rev=rev)


def reverb_ir(t60, seed):
    rng = np.random.default_rng(seed)
    n = int(t60 * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-6.9 * t / t60)
    ir = sosfilt(_sos("low", 5500), ir)
    ir[: int(0.012 * SR)] = 0  # предзадержка
    return ir / np.sqrt(np.sum(ir ** 2))


def finish(mix, path_wav, t60=2.4):
    irs = (reverb_ir(t60, 11), reverb_ir(t60, 12))
    out = mix.dry.copy()
    for ch in range(2):
        out[ch] += fftconvolve(mix.wet[ch], irs[ch])[: mix.n] * 0.9
    end = int((mix.len + 2.5) * SR)
    out = out[:, :end]
    fi = int(0.15 * SR)
    out[:, :fi] *= np.linspace(0, 1, fi)
    fo = int(2.0 * SR)
    out[:, -fo:] *= np.linspace(1, 0, fo) ** 1.5
    out = sosfilt(_sos("high", 35), out, axis=1)
    out = np.tanh(out / np.max(np.abs(out)) * 1.2) / np.tanh(1.2) * 0.9
    wavfile.write(path_wav, SR, (out.T * 32767).astype(np.int16))


def master_mp3(wav, mp3, lufs=-18.0):
    """Двухпроходная нормализация громкости (EBU R128) и экспорт в mp3."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
                        f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr
    js = json.loads(txt[txt.rfind("{"): txt.rfind("}") + 1])
    af = (f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", wav, "-af", af,
                    "-ar", "44100", "-b:a", "192k", mp3], check=True)


# ---------------------------------------------------------------- треки
def track_dala():
    """1. «Дала» — спокойная степь. 6/8, 60 уд/мин, ре минор. ~64 с."""
    e = 1 / 3
    bar = 6 * e
    nb = 32
    M = Mix(nb * bar, 1)
    rng = M.rng
    ch = [(50, [50, 57, 62, 65]), (48, [48, 55, 60, 64]), (46, [46, 53, 58, 62]), (48, [48, 55, 60, 64]),
          (50, [50, 57, 62, 65]), (45, [45, 52, 57, 60]), (46, [46, 53, 58, 62]), (48, [48, 55, 60, 64])]
    p1 = [(69, 0, 3), (72, 3, 3), (74, 6, 6), (72, 12, 2), (69, 14, 1), (67, 15, 3), (69, 18, 6)]
    p2 = [(65, 0, 3), (67, 3, 3), (69, 6, 3), (72, 9, 3), (69, 12, 6), (67, 18, 2), (65, 20, 1), (62, 21, 3)]
    for b in range(nb):
        root, v = ch[0] if b == nb - 1 else ch[b % 8]
        t0 = b * bar
        arp = [v[0] + 12, v[1] + 12, v[3] + 12, v[1] + 12, v[2] + 12, v[1] + 12]
        steps = 1 if b == nb - 1 else 6
        for i in range(steps):
            vel = (0.95 if i in (0, 3) else 0.6) * (0.85 if b < 4 else 1.0)
            T = 3.0 if b == nb - 1 else 1.1
            M.add(dombra(arp[i], T, 0.55, rng=rng), t0 + i * e + rng.uniform(-0.006, 0.006),
                  0.30 * vel, pan=0.2 if i % 2 else -0.15, rev=0.3)
        if b == nb - 1:
            M.strum([v[0] + 12, v[1] + 12, v[2] + 12], t0 + 0.02, 0.8, T=3.0, bright=0.5, gain=0.2, spread=0.03, rev=0.4)
        if 4 <= b < nb - 2:
            M.add(dombra(root - 12, 2.0, 0.3, rng=rng), t0, 0.42, rev=0.15)
            M.add(pad(v, bar, rng, att=0.7, rel=1.6), t0, 0.10, pan=-0.45, rev=0.45)
            M.add(pad(v, bar, rng, att=0.7, rel=1.6), t0, 0.10, pan=0.45, rev=0.45)
        if 12 <= b < 24 and (b - 12) % 4 == 0:
            phrase = p2 if (b - 12) // 4 == 1 else p1
            for m, s, l in phrase:
                M.add(bowed(m, l * e, rng), t0 + s * e, 0.30, pan=0.1, rev=0.45)
    return M


def track_tulpar():
    """2. «Тұлпар» — скачущий конь, энергично. 6/8, 100 уд/мин, ля минор. ~63 с."""
    e = 0.2
    bar = 6 * e
    nb = 52
    M = Mix(nb * bar, 2)
    rng = M.rng
    roots = [45, 43, 45, 40, 41, 43, 45, 45]
    strum_v = {45: [57, 64, 69], 43: [55, 62, 67], 40: [52, 59, 64], 41: [53, 60, 65]}
    M1 = [76, 76, 74, 72, 69, 72, 74, None, 76, 79, 76, 74]
    M2 = [72, None, 72, 69, 67, 69, 64, None, 67, 69, None, None]
    M3 = [81, 79, 76, 79, 76, 74, 76, 74, 72, 74, 72, 69]
    M4 = [67, 69, 72, 69, None, 67, 69, None, None, 69, None, None]
    secA, secB = [M1, M2, M1, M4], [M3, M2, M3, M4]
    vels = [1.0, 0.4, 0.65, 0.9, 0.4, 0.65]
    for b in range(nb):
        t0 = b * bar
        r = roots[b % 8]
        final = b == nb - 1
        breakdown = 28 <= b < 36
        if final:
            M.strum(strum_v[45], t0, 1.0, T=1.8, gain=0.26, spread=0.02)
            M.add(dombra(45, 2.0, 0.3, rng=rng), t0, 0.45)
            M.add(kick(rng), t0, 0.5, rev=0.1)
            continue
        for i, v in enumerate(vels):
            M.strum(strum_v[r], t0 + i * e, v * (0.6 if breakdown else 1.0) * (0.85 if b < 4 else 1.0),
                    T=0.32, bright=0.6, gain=0.20)
        if b >= 4 and not breakdown:
            M.add(dombra(r, 0.5, 0.3, rng=rng), t0, 0.38, rev=0.1)
            M.add(dombra(r, 0.5, 0.3, rng=rng), t0 + 3 * e, 0.30, rev=0.1)
            M.add(kick(rng), t0, 0.45, rev=0.05)
            M.add(kick(rng), t0 + 3 * e, 0.38, rev=0.05)
            M.add(frame_drum(rng), t0 + 2 * e, 0.16, pan=-0.3)
            M.add(frame_drum(rng), t0 + 5 * e, 0.22, pan=-0.3)
            for i in range(6):
                M.add(shaker(rng), t0 + i * e, 0.07 if i % 3 else 0.10, pan=0.4)
        if breakdown:
            if b == 28:
                M.add(bowed(45, 8 * bar, rng, att=2.5, rel=1.5, vib=0.08), t0, 0.16, pan=-0.2, rev=0.5)
                M.add(bowed(52, 8 * bar, rng, att=3.0, rel=1.5, vib=0.08), t0, 0.12, pan=0.2, rev=0.5)
            M.add(frame_drum(rng), t0, 0.15, pan=-0.2, rev=0.4)
        mel_bar = None
        if 12 <= b < 28:
            k = b - 12
            sec = secA if k < 8 else secB
            mel_bar = (sec[(k % 8) // 2], (k % 8) % 2)
        elif 36 <= b < 51:
            k = b - 36
            sec = secA if k < 8 else secB
            mel_bar = (sec[(k % 8) // 2], (k % 8) % 2)
        if mel_bar:
            mot, half = mel_bar
            for i in range(6):
                m = mot[half * 6 + i]
                if m is not None:
                    M.add(dombra(m, 0.55, 0.75, rng=rng), t0 + i * e + rng.uniform(-0.004, 0.004),
                          0.36, pan=0.3, rev=0.3)
    return M


def track_kupiya():
    """3. «Құпия» — загадка, для интересных фактов. 4/4, 88 уд/мин, ми минор. ~65 с."""
    beat = 60 / 88
    s8 = beat / 2
    bar = 4 * beat
    nb = 24
    M = Mix(nb * bar, 3)
    rng = M.rng
    ch = [(40, [52, 59, 64, 67]), (36, [48, 55, 60, 64]), (45, [45, 52, 57, 60]), (35, [47, 54, 59, 63])]
    q1 = [(71, 0, 6), (69, 6, 2), (67, 8, 4), (64, 12, 4), (69, 16, 6), (72, 22, 2), (71, 24, 8)]
    q2 = [(67, 0, 4), (71, 4, 4), (72, 8, 6), (71, 14, 2), (69, 16, 4), (64, 20, 4), (66, 24, 4), (63, 28, 4)]
    q3 = [(76, 0, 6), (74, 6, 2), (72, 8, 4), (67, 12, 4), (69, 16, 6), (71, 22, 2), (75, 24, 4), (71, 28, 4)]
    q4 = [(76, 0, 4), (71, 4, 4), (72, 8, 4), (76, 12, 4), (72, 16, 4), (69, 20, 4), (71, 24, 8)]
    total = nb * bar
    # бурдон кобыза на всю длину (Е + Н), медленно «дышит»
    for m, g, pn in ((40, 0.13, -0.2), (47, 0.08, 0.2)):
        d = bowed(m, total, rng, att=3.0, rel=2.0, vib=0.05, bright=0.6)
        tt = np.arange(len(d)) / SR
        d *= 0.7 + 0.3 * np.sin(2 * np.pi * tt / 11.0 + (0 if m == 40 else 1.7))
        M.add(d, 0.0, g, pan=pn, rev=0.5)
    bells = [(0, 76), (3, 79), (6, 83)], [(0, 83), (4, 79), (10, 78)]
    for b in range(nb):
        t0 = b * bar
        root, v = ch[b % 4]
        if b >= 2:
            for i in range(8):
                m = v[0] + 12 if i % 2 == 0 else v[1] + 12
                if root in (36, 35):
                    m = v[0] if i % 2 == 0 else v[1]
                M.add(dombra(m, 0.12, 0.35, dur=0.45, rng=rng), t0 + i * s8 + rng.uniform(-0.004, 0.004),
                      0.20 * (1.0 if i % 4 == 0 else 0.7), pan=-0.3 if i % 2 else 0.3, rev=0.25)
        if 4 <= b < nb:
            M.add(pad(v, bar, rng, att=1.0, rel=2.0, cutoff=900), t0, 0.09, pan=-0.4, rev=0.5)
            M.add(pad(v, bar, rng, att=1.0, rel=2.0, cutoff=900), t0, 0.09, pan=0.4, rev=0.5)
        if b in (5, 6, 9, 13, 17, 21):
            for pos, m in bells[b % 2]:
                M.add(dombra(m, 2.5, 0.9, rng=rng), t0 + pos * (beat / 4), 0.13, pan=0.45, rev=0.6)
        if b >= 8:
            M.add(kick(rng), t0, 0.34, rev=0.1)
            M.add(kick(rng), t0 + 2 * beat, 0.28, rev=0.1)
        if b >= 4:
            for i in range(4):
                M.add(shaker(rng), t0 + i * beat + s8, 0.06, pan=0.35)
        if b >= 8 and (b - 8) % 4 == 0:
            phrase = [q1, q2, q3, q4][(b - 8) // 4 % 4]
            for m, s, l in phrase:
                M.add(bowed(m, l * s8, rng), t0 + s * s8, 0.26, pan=0.1, rev=0.5)
    return M


def track_toy():
    """4. «Той» — светлое, позитивное. 6/8, 92 уд/мин, соль мажор. ~63 с."""
    e = 60 / 92 / 3
    bar = 6 * e
    nb = 48
    M = Mix(nb * bar, 4)
    rng = M.rng
    cyc = ["G", "C", "D", "G", "Em", "C", "D", "G"]
    sv = {"G": [55, 59, 62], "C": [55, 60, 64], "D": [57, 62, 66], "Em": [55, 59, 64]}
    bass = {"G": 43, "C": 48, "D": 38, "Em": 40}
    F1 = [(74, 0, 2), (71, 2, 1), (74, 3, 2), (76, 5, 1), (74, 6, 3), (71, 9, 3)]
    F2 = [(69, 0, 2), (71, 2, 1), (74, 3, 2), (71, 5, 1), (69, 6, 3), (67, 9, 3)]
    F3 = [(76, 0, 2), (79, 2, 1), (76, 3, 2), (74, 5, 1), (71, 6, 3), (74, 9, 3)]
    F4 = [(69, 0, 2), (71, 2, 1), (69, 3, 2), (67, 5, 1), (67, 6, 6)]
    phr = [F1, F2, F3, F4]
    hits = [(0, 0.9), (2, 0.55), (3, 0.8), (5, 0.55)]
    for b in range(nb):
        t0 = b * bar
        c = cyc[b % 8]
        if b == nb - 1:
            M.strum(sv["G"], t0, 1.0, T=2.0, gain=0.24, spread=0.025)
            M.add(dombra(43, 2.0, 0.3, rng=rng), t0, 0.42)
            M.add(kick(rng), t0, 0.45, rev=0.1)
            continue
        for i, v in hits:
            M.strum(sv[c], t0 + i * e, v * (0.85 if b < 4 else 1.0), T=0.45, bright=0.65, gain=0.20)
        if 4 <= b < 44:
            M.add(dombra(bass[c], 0.6, 0.3, rng=rng), t0, 0.36, rev=0.1)
            M.add(dombra(bass[c] + 7, 0.6, 0.3, rng=rng), t0 + 3 * e, 0.26, rev=0.1)
            M.add(kick(rng), t0, 0.40, rev=0.05)
            M.add(kick(rng), t0 + 3 * e, 0.30, rev=0.05)
            M.add(frame_drum(rng), t0 + 3 * e, 0.14, pan=-0.3)
            for i in range(6):
                M.add(shaker(rng), t0 + i * e, 0.06 if i % 3 else 0.09, pan=0.4)
        k = None
        if 12 <= b < 28:
            k = (b - 12) % 8
            inst = "flute"
        elif 28 <= b < 36:
            k = (b - 28) % 8
            inst = "dombra"
        elif 36 <= b < 44:
            k = (b - 36) % 8
            inst = "both"
        if k is not None and k % 2 == 0:
            for m, s, l in phr[k // 2]:
                if inst in ("flute", "both"):
                    M.add(flute(m, l * e * 0.95, rng), t0 + s * e, 0.28, pan=-0.15, rev=0.35)
                if inst in ("dombra", "both"):
                    M.add(dombra(m, 0.7, 0.75, rng=rng), t0 + s * e, 0.34 if inst == "dombra" else 0.22,
                          pan=0.3, rev=0.3)
    return M


TRACKS = [
    ("01_Dala_spokoyno", track_dala),
    ("02_Tulpar_energichno", track_tulpar),
    ("03_Kupiya_zagadka", track_kupiya),
    ("04_Toy_pozitiv", track_toy),
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
        print("ok", name, round(M.len, 1), "s", flush=True)
