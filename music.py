"""Генератор музыки для роликов-цитат: 12 стилей, 8 инструментов, бас, мотивы с вариациями.
make_music(style, total, seed, line_times) -> numpy float mono 44100.
"""
import math
import random

import numpy as np
from scipy.ndimage import gaussian_filter

SR = 44100


class Synth:
    def __init__(self, total, seed):
        self.a = np.zeros(int((total + 3) * SR))
        self.r = random.Random(seed)
        self.rng = np.random.default_rng(seed)

    def put(self, sig, at):
        s = int(at * SR)
        if 0 <= s < len(self.a):
            self.a[s:s + len(sig)] += sig[:len(self.a) - s]

    @staticmethod
    def _tt(dur):
        return np.arange(int(dur * SR)) / SR

    # ---- инструменты
    def piano(self, f, dur, vol):
        tt = self._tt(dur)
        env = np.exp(-tt * 1.5) * np.minimum(1, tt * 150)
        s = np.zeros_like(tt)
        for h, amp, dec in ((1, 1.0, 0), (2, 0.45, 1.5), (3, 0.22, 3), (4, 0.1, 5), (5, 0.05, 7), (6, 0.03, 9)):
            s += amp * np.sin(2 * np.pi * f * h * tt + 0.3 * h) * np.exp(-tt * dec)
        return vol * env * s

    def bell(self, f, dur, vol):
        tt = self._tt(dur)
        env = np.exp(-tt * 2.4) * np.minimum(1, tt * 500)
        s = np.zeros_like(tt)
        for h, amp, dec in ((1, 1.0, 0), (2.0, 0.35, 2), (2.98, 0.22, 4), (4.05, 0.1, 7), (5.4, 0.05, 10)):
            s += amp * np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * dec)
        return vol * env * s

    def pad(self, f, dur, vol):
        tt = self._tt(dur)
        att = np.minimum(1, tt / 0.9)
        rel = np.minimum(1, np.maximum(0, (dur - tt) / 1.2))
        s = (np.sin(2 * np.pi * f * 0.997 * tt) + np.sin(2 * np.pi * f * 1.003 * tt) + 0.6 * np.sin(2 * np.pi * f * tt + 1)
             + 0.25 * np.sin(2 * np.pi * f * 2.0 * tt)) / 2.85
        trem = 1 + 0.06 * np.sin(2 * np.pi * 0.35 * tt)
        return vol * att * rel * trem * s

    def strings(self, f, dur, vol):
        tt = self._tt(dur)
        att = np.minimum(1, tt / 0.6) ** 1.5
        rel = np.minimum(1, np.maximum(0, (dur - tt) / 1.0))
        s = np.zeros_like(tt)
        for h in range(1, 8):
            det = 1 + 0.0015 * (h % 3 - 1)
            s += (1.0 / h ** 1.3) * np.sin(2 * np.pi * f * h * det * tt + 0.7 * h)
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * tt) * np.minimum(1, tt / 1.5)
        s = s * vib
        return vol * att * rel * s / 2.2

    def pluck(self, f, dur, vol):
        tt = self._tt(dur)
        env = np.exp(-tt * 2.8) * np.minimum(1, tt * 900)
        s = np.zeros_like(tt)
        for h in range(1, 7):
            s += (1.0 / h) * np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (1.2 + 2.2 * h))
        return vol * env * s

    def guitar(self, f, dur, vol):
        tt = self._tt(dur)
        env = np.exp(-tt * 1.9) * np.minimum(1, tt * 600)
        s = np.zeros_like(tt)
        for h in range(1, 9):
            s += (1.0 / h ** 0.9) * np.sin(2 * np.pi * f * h * tt + 0.2 * h) * np.exp(-tt * (0.8 + 1.4 * h))
        return vol * env * s * 0.8

    def kalimba(self, f, dur, vol):
        tt = self._tt(dur)
        env = np.exp(-tt * 3.6) * np.minimum(1, tt * 800)
        s = np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 3.9 * tt) * np.exp(-tt * 9) + 0.2 * np.sin(2 * np.pi * f * 7.2 * tt) * np.exp(-tt * 14)
        return vol * env * s

    def flute(self, f, dur, vol):
        tt = self._tt(dur)
        att = np.minimum(1, tt / 0.12)
        rel = np.minimum(1, np.maximum(0, (dur - tt) / 0.35))
        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * tt) * np.minimum(1, tt / 0.6)
        ph = 2 * np.pi * f * np.cumsum(vib) / SR
        s = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
        breath = gaussian_filter(self.rng.uniform(-1, 1, len(tt)), 2) * 0.05
        return vol * att * rel * (s / 1.3 + breath)

    # ---- фоны
    def surf(self, dur, vol):
        m = int(dur * SR)
        x = gaussian_filter(self.rng.uniform(-1, 1, m), 14)
        tt = np.arange(m) / SR
        lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.09 * tt + 1.0) * np.sin(2 * np.pi * 0.047 * tt)
        return vol * x / (np.abs(x).max() + 1e-9) * lfo

    def wind(self, dur, vol):
        m = int(dur * SR)
        x = gaussian_filter(self.rng.uniform(-1, 1, m), 30)
        tt = np.arange(m) / SR
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * tt) * np.sin(2 * np.pi * 0.071 * tt + 2)
        return vol * x / (np.abs(x).max() + 1e-9) * lfo

    def rain(self, dur, vol):
        m = int(dur * SR)
        x = self.rng.uniform(-1, 1, m)
        x = gaussian_filter(x, 1.2) - gaussian_filter(x, 6)
        ticks = (self.rng.random(m) < 0.0008) * self.rng.uniform(0.5, 1, m)
        ticks = np.convolve(ticks, np.exp(-np.arange(400) / 60), mode="same")
        return vol * (x / (np.abs(x).max() + 1e-9) * 0.5 + ticks)

    def crickets(self, dur, vol):
        m = int(dur * SR)
        tt = np.arange(m) / SR
        chirp = (np.sin(2 * np.pi * 4200 * tt) * (np.sin(2 * np.pi * 28 * tt) > 0.6)) * (np.sin(2 * np.pi * 0.9 * tt + 1) > 0.2)
        return vol * chirp * 0.35

    def birds(self, dur, vol):
        m = int(dur * SR)
        out = np.zeros(m)
        t = 1.0
        while t < dur - 1:
            f0 = self.r.uniform(1800, 3200)
            n = self.r.randint(2, 5)
            for k in range(n):
                d = self.r.uniform(0.06, 0.14)
                tt = np.arange(int(d * SR)) / SR
                sweep = f0 * (1 + 0.25 * np.sin(2 * np.pi * tt / d * 1.5))
                sig = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.sin(np.pi * tt / d) ** 1.5
                s = int((t + k * d * 1.4) * SR)
                if s + len(sig) < m:
                    out[s:s + len(sig)] += sig * self.r.uniform(0.4, 1)
            t += self.r.uniform(2.5, 6)
        return vol * out


MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
DORIAN = [0, 2, 3, 5, 7, 9, 10]
LYDIAN = [0, 2, 4, 6, 7, 9, 11]
PENTA_MAJ = [0, 2, 4, 7, 9, 12, 14]
PENTA_MIN = [0, 3, 5, 7, 10, 12, 15]

# прогрессии — ступени аккордов (в градусах гаммы), тройки нот
P_POP = [[0, 2, 4], [4, 6, 8], [5, 7, 9], [3, 5, 7]]          # I V vi IV
P_SAD = [[5, 7, 9], [3, 5, 7], [0, 2, 4], [4, 6, 8]]          # vi IV I V
P_JAZZ = [[0, 2, 4], [5, 7, 9], [1, 3, 5], [4, 6, 8]]         # I vi ii V
P_FOLK = [[0, 2, 4], [3, 5, 7], [4, 6, 8], [3, 5, 7]]         # I IV V IV
P_MODAL = [[0, 2, 4], [1, 3, 5], [0, 2, 4], [6, 8, 10]]       # i ii i VII
P_DREAM = [[0, 2, 4], [3, 5, 7], [5, 7, 9], [3, 5, 7]]        # I IV vi IV

STYLES = {
    "piano_dawn": dict(base=261.63, scale=MAJOR, prog=P_POP, beat=0.82, lead="piano", bed="piano", bass="piano", bg=None, rhythm=[2, 1, 1, 2, 2], arp="up"),
    "musicbox": dict(base=220.00, scale=MINOR, prog=P_SAD, beat=0.6, lead="bell", bed="bell", bass="bell", bg="wind", rhythm=[1, 1, 2, 1, 1, 2], arp="waltz"),
    "night_pad": dict(base=146.83, scale=MINOR, prog=P_MODAL, beat=1.0, lead="piano", bed="pad", bass="pad", bg="crickets", rhythm=[3, 1, 2, 2], arp="hold"),
    "harp_walk": dict(base=196.00, scale=PENTA_MAJ, prog=P_FOLK, beat=0.55, lead="pluck", bed="pluck", bass="pluck", bg=None, rhythm=[1, 1, 1, 1, 2, 2], arp="updown"),
    "piano_sea": dict(base=174.61, scale=MAJOR, prog=P_DREAM, beat=0.72, lead="piano", bed="piano", bass="piano", bg="surf", rhythm=[2, 1, 1, 2, 2], arp="updown"),
    "flute_meadow": dict(base=293.66, scale=LYDIAN, prog=P_FOLK, beat=0.7, lead="flute", bed="pluck", bass="guitar", bg="birds", rhythm=[2, 2, 1, 1, 2], arp="up"),
    "strings_dusk": dict(base=164.81, scale=MINOR, prog=P_SAD, beat=0.95, lead="piano", bed="strings", bass="strings", bg=None, rhythm=[3, 1, 2, 2], arp="hold"),
    "kalimba_rain": dict(base=233.08, scale=PENTA_MAJ, prog=P_POP, beat=0.5, lead="kalimba", bed="kalimba", bass="guitar", bg="rain", rhythm=[1, 1, 2, 1, 1, 1, 1], arp="up"),
    "guitar_fire": dict(base=220.00, scale=DORIAN, prog=P_MODAL, beat=0.62, lead="guitar", bed="guitar", bass="guitar", bg=None, rhythm=[1, 1, 2, 2, 1, 1], arp="updown"),
    "celesta_stars": dict(base=329.63, scale=MAJOR, prog=P_DREAM, beat=0.9, lead="bell", bed="pad", bass="pad", bg="wind", rhythm=[2, 2, 4], arp="hold"),
    "piano_hope": dict(base=196.00, scale=MAJOR, prog=P_POP, beat=0.68, lead="flute", bed="piano", bass="piano", bg=None, rhythm=[1, 1, 2, 2, 2], arp="up"),
    "pad_aurora": dict(base=138.59, scale=DORIAN, prog=P_MODAL, beat=1.1, lead="bell", bed="pad", bass="pad", bg="wind", rhythm=[4, 2, 2], arp="hold"),
}


def make_music(style, total, seed, line_times=()):
    st = STYLES[style]
    sy = Synth(total, seed)
    r = sy.r
    voice = {"piano": sy.piano, "bell": sy.bell, "pad": sy.pad, "pluck": sy.pluck, "flute": sy.flute, "kalimba": sy.kalimba,
             "strings": sy.strings, "guitar": sy.guitar}
    base, scale, prog, beat = st["base"], st["scale"], st["prog"], st["beat"]
    n_sc = len(scale)

    def freq(deg, octave=0):
        return base * 2 ** ((scale[deg % n_sc] + 12 * (deg // n_sc) + 12 * octave) / 12)

    lead, bed, bass = voice[st["lead"]], voice[st["bed"]], voice[st["bass"]]
    bar = beat * 4
    t = 0.6
    ci = 0
    # ---- аккомпанемент и бас
    while t < total - 1.0:
        ch = prog[ci % len(prog)]
        root = ch[0]
        if st["arp"] == "hold":
            for j, d in enumerate(ch):
                sy.put(bed(freq(d, 0), bar + 0.8, 0.07 if j else 0.085), t + j * 0.05)
            sy.put(bass(freq(root, -1), bar + 0.6, 0.075), t)
        elif st["arp"] == "waltz":
            sy.put(bass(freq(root, -1), 1.4, 0.09), t)
            for j in (1, 2):
                for d in ch[1:]:
                    sy.put(bed(freq(d, 0), 1.0, 0.045), t + j * beat * 1.333 + r.uniform(0, 0.015))
            sy.put(bass(freq(ch[1], -1), 1.2, 0.06), t + 2 * beat)
        else:
            order = {"up": [0, 1, 2, 1, 0, 1, 2, 1], "updown": [0, 1, 2, 1, 2, 1, 0, 1]}[st["arp"]]
            step = bar / len(order)
            for j, k in enumerate(order):
                sy.put(bed(freq(ch[k], 0), step * 2.6, 0.06 if j % 4 else 0.075), t + j * step + r.uniform(0, 0.012))
            sy.put(bass(freq(root, -1), bar * 0.9, 0.08), t)
            if r.random() < 0.5:
                sy.put(bass(freq(ch[2], -1), bar * 0.45, 0.05), t + bar / 2)
        t += bar
        ci += 1
    n_bars = ci
    # ---- мелодия: мотив из 2 тактов + вариации, фразы по 4 такта
    rhythm = st["rhythm"]

    def gen_motif():
        deg = n_sc + r.choice([0, 2, 4])
        notes = []
        tt = 0.0
        ri = r.randrange(len(rhythm))
        while tt < 2 * bar - 1e-6:
            nb = rhythm[ri % len(rhythm)]
            ri += 1
            dur = min(nb * beat, 2 * bar - tt)
            if r.random() < 0.6:
                deg += r.choice([-2, -1, 1, 2])
            else:
                deg += r.choice([-4, -3, 3, 4])
            deg = max(n_sc - 1, min(2 * n_sc + 2, deg))
            rest = r.random() < 0.15
            notes.append((tt, dur, deg, rest))
            tt += dur
        return notes

    motif = gen_motif()
    t = 0.6 + bar
    phrase = 0
    while t < total - 2.5:
        var = phrase % 4
        notes = motif
        if var == 1:
            notes = [(a, b, d + r.choice([0, 0, 1, -1]), rs) for a, b, d, rs in motif]
        elif var == 2:
            notes = [(a, b, d + 2, rs) for a, b, d, rs in motif]
        elif var == 3:
            motif = gen_motif()
            notes = motif
        for j, (a, dur, deg, rest) in enumerate(notes):
            at = t + a
            if at > total - 2.0:
                break
            chord = prog[int((at - 0.6) // bar) % len(prog)]
            tones = {c % n_sc for c in chord}
            if j == len(notes) - 1 or r.random() < 0.45:
                cand = [d for d in range(n_sc - 1, 2 * n_sc + 3) if d % n_sc in tones]
                deg = min(cand, key=lambda d: abs(d - deg))
            if rest:
                continue
            vol = 0.085 if st["lead"] not in ("flute", "strings") else 0.065
            sy.put(lead(freq(deg), dur * (1.5 if st["lead"] in ("piano", "bell", "pluck", "kalimba", "guitar") else 0.95) + 0.3, vol), at + r.uniform(0, 0.02))
        t += 2 * bar
        phrase += 1
    # ---- колокольчик на появление строк
    for tl in line_times:
        sy.put(sy.bell(freq(2 * n_sc + r.choice([0, 2, 4])), 2.0, 0.03), tl + 0.1)
    # ---- фон
    bg = st["bg"]
    if bg == "surf":
        sy.put(sy.surf(total + 1, 0.06), 0)
    elif bg == "wind":
        sy.put(sy.wind(total + 1, 0.035), 0)
    elif bg == "rain":
        sy.put(sy.rain(total + 1, 0.025), 0)
    elif bg == "crickets":
        sy.put(sy.crickets(total + 1, 0.025), 0)
    elif bg == "birds":
        sy.put(sy.birds(total + 1, 0.05), 0)
    a = sy.a[:int((total + 0.5) * SR)]
    # финальный аккорд-разрешение и затухание
    tonic = prog[0]
    for j, d in enumerate(tonic):
        sy.put(bed(freq(d, 0), 3.0, 0.06), max(0.0, total - 2.4) + j * 0.06)
    a = sy.a[:int((total + 0.5) * SR)]
    fade = int(1.8 * SR)
    a[-fade:] *= np.linspace(1, 0, fade)
    a[:int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
    # мягкий лимитер
    a = np.tanh(a * 1.6) / 1.6
    return a
