"""Спокойная оркестровая музыка для роликов-цитат.
make_music(style, total, seed, line_times) -> numpy float mono 44100.
Струнный ансамбль (расстроенные голоса, медленная атака, вибрато), арфа, пианино, флейта, гобой, виолончель,
валторны, хор, челеста; зал-реверберация; аккорды с септимами и нонами; мотивная мелодия с динамикой.
"""
import math
import random

import numpy as np
from scipy.signal import fftconvolve
from scipy.ndimage import gaussian_filter

SR = 44100
NYQ = 9000.0


def _tt(dur):
    return np.arange(int(dur * SR)) / SR


def _env_adsr(tt, att, rel, dur, curve=1.0):
    a = np.minimum(1, tt / max(att, 1e-3)) ** curve
    r = np.minimum(1, np.maximum(0, (dur - tt) / max(rel, 1e-3)))
    return a * r


def _vibrato_phase(f, tt, rate, depth, onset=0.4):
    vib = 1 + depth * np.sin(2 * np.pi * rate * tt + np.random.uniform(0, 6.28)) * np.minimum(1, tt / onset)
    return 2 * np.pi * f * np.cumsum(vib) / SR


class Orchestra:
    def __init__(self, total, seed):
        self.a = np.zeros(int((total + 4) * SR))
        self.r = random.Random(seed)
        self.rng = np.random.default_rng(seed)
        np.random.seed(seed)

    def put(self, sig, at):
        s = int(at * SR)
        if 0 <= s < len(self.a):
            self.a[s:s + len(sig)] += sig[:len(self.a) - s]

    # ---------------------------------------------------------------- секции
    def strings(self, f, dur, vol, voices=4, att=1.1, rel=1.6, bright=1.0):
        tt = _tt(dur)
        out = np.zeros_like(tt)
        nh = int(min(18, NYQ / f))
        for v in range(voices):
            det = 1 + self.r.uniform(-0.0035, 0.0035)
            ph = _vibrato_phase(f * det, tt, self.r.uniform(4.6, 5.8), 0.0028, onset=0.6)
            s = np.zeros_like(tt)
            for h in range(1, nh + 1):
                s += (1.0 / h ** (1.75 / bright)) * np.sin(h * ph + self.r.uniform(0, 6.28))
            delay = int(self.r.uniform(0, 0.04) * SR)
            s = np.roll(s, delay)
            s[:delay] = 0
            out += s
        env = _env_adsr(tt, att, rel, dur, curve=1.6)
        trem = 1 + 0.05 * np.sin(2 * np.pi * self.r.uniform(0.25, 0.45) * tt)
        return vol * env * trem * out / (voices * 1.6)

    def cello(self, f, dur, vol):
        tt = _tt(dur)
        ph = _vibrato_phase(f, tt, 5.2, 0.005, onset=0.35)
        nh = int(min(20, NYQ / f))
        s = np.zeros_like(tt)
        for h in range(1, nh + 1):
            s += (1.0 / h ** 1.15) * np.sin(h * ph)
        bow = gaussian_filter(self.rng.uniform(-1, 1, len(tt)), 3) * 0.03
        env = _env_adsr(tt, 0.28, 0.5, dur, curve=1.3)
        return vol * env * (s / 2.4 + bow)

    def horn(self, f, dur, vol):
        tt = _tt(dur)
        ph = _vibrato_phase(f, tt, 4.5, 0.002, onset=0.8)
        nh = int(min(10, NYQ / f))
        s = np.zeros_like(tt)
        for h in range(1, nh + 1):
            s += (1.0 / h ** 1.6) * np.sin(h * ph)
        env = _env_adsr(tt, 0.45, 0.9, dur, curve=1.4)
        return vol * env * s / 1.6

    def choir(self, f, dur, vol):
        tt = _tt(dur)
        out = np.zeros_like(tt)
        for v in range(3):
            det = 1 + self.r.uniform(-0.004, 0.004)
            ph = _vibrato_phase(f * det, tt, self.r.uniform(4.8, 5.6), 0.004, onset=0.9)
            nh = int(min(16, NYQ / f))
            s = np.zeros_like(tt)
            for h in range(1, nh + 1):
                fh = f * h
                formant = math.exp(-((fh - 750) / 320) ** 2) + 0.6 * math.exp(-((fh - 1300) / 420) ** 2) + 0.25
                s += formant / h ** 0.9 * np.sin(h * ph + v)
            out += s
        env = _env_adsr(tt, 1.2, 1.4, dur, curve=1.5)
        return vol * env * out / 4.5

    def flute(self, f, dur, vol):
        tt = _tt(dur)
        ph = _vibrato_phase(f, tt, 5.4, 0.006, onset=0.5)
        s = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.07 * np.sin(3 * ph)
        breath = gaussian_filter(self.rng.uniform(-1, 1, len(tt)), 2.5) * 0.04
        env = _env_adsr(tt, 0.14, 0.35, dur, curve=1.2)
        return vol * env * (s / 1.3 + breath)

    def oboe(self, f, dur, vol):
        tt = _tt(dur)
        ph = _vibrato_phase(f, tt, 5.0, 0.0045, onset=0.4)
        nh = int(min(12, NYQ / f))
        s = np.zeros_like(tt)
        for h in range(1, nh + 1):
            w = (1.0 / h ** 0.8) * (1.6 if h in (2, 3, 4) else 1.0)
            s += w * np.sin(h * ph)
        env = _env_adsr(tt, 0.12, 0.3, dur, curve=1.2)
        return vol * env * s / 3.2

    def harp(self, f, dur, vol):
        tt = _tt(dur)
        env = np.exp(-tt * 1.4) * np.minimum(1, tt * 900)
        s = np.zeros_like(tt)
        for h in range(1, 8):
            s += (1.0 / h ** 1.1) * np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (0.6 + 1.6 * h))
        return vol * env * s

    def piano(self, f, dur, vol):
        tt = _tt(dur)
        env = np.exp(-tt * 1.3) * np.minimum(1, tt * 150)
        s = np.zeros_like(tt)
        for h, amp, dec in ((1, 1.0, 0), (2, 0.45, 1.5), (3, 0.22, 3), (4, 0.1, 5), (5, 0.05, 7)):
            s += amp * np.sin(2 * np.pi * f * h * tt + 0.3 * h) * np.exp(-tt * dec)
        return vol * env * s

    def celesta(self, f, dur, vol):
        tt = _tt(dur)
        env = np.exp(-tt * 2.0) * np.minimum(1, tt * 600)
        s = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 4.0 * tt) * np.exp(-tt * 6) + 0.12 * np.sin(2 * np.pi * f * 6.0 * tt) * np.exp(-tt * 9)
        return vol * env * s

    def felt(self, f, dur, vol):
        """Мягкое «войлочное» пианино: две струны с расстройкой, негармоничность, долгое послезвучие, тихий удар молоточка."""
        tt = _tt(dur)
        s = np.zeros_like(tt)
        kdec = (f / 262.0) ** 0.5
        nh = int(min(10, NYQ / f))
        for det in (0.9994, 1.0006):
            for h in range(1, nh + 1):
                fh = f * det * h * math.sqrt(1 + 0.00025 * h * h)
                s += (0.9 / h ** 1.7) * np.sin(2 * np.pi * fh * tt + 0.4 * h) * np.exp(-tt * (0.35 + 0.30 * h) * kdec)
        env = (0.55 * np.exp(-tt * 2.2 * kdec) + 0.45 * np.exp(-tt * 0.32 * kdec)) * np.minimum(1, tt / 0.007)
        rel = np.minimum(1, np.maximum(0, (dur - tt) / 0.35))
        n = min(len(tt), int(0.03 * SR))
        thump = np.zeros_like(tt)
        thump[:n] = gaussian_filter(self.rng.uniform(-1, 1, n), 6) * np.exp(-np.arange(n) / (0.006 * SR)) * 0.6
        return vol * (env * rel * s / 1.6 + thump)

    def violin(self, f, dur, vol):
        """Сольная скрипка: яркий смычковый тембр, вибрато вступает не сразу, мягкая атака."""
        tt = _tt(dur)
        ph = _vibrato_phase(f, tt, 5.7, 0.0065, onset=0.7)
        nh = int(min(24, NYQ / f))
        s = np.zeros_like(tt)
        for h in range(1, nh + 1):
            fh = f * h
            body = 1.0 + 0.8 * math.exp(-((fh - 2900) / 900) ** 2) + 0.5 * math.exp(-((fh - 500) / 220) ** 2)
            s += body / h ** 1.05 * np.sin(h * ph)
        bow = gaussian_filter(self.rng.uniform(-1, 1, len(tt)), 2) * 0.02
        env = _env_adsr(tt, 0.32, 0.55, dur, curve=1.4) * (1 + 0.08 * np.sin(np.pi * np.minimum(1, tt / max(dur, 0.1))))
        return vol * env * (s / 3.4 + bow)

    def clarinet(self, f, dur, vol):
        """Кларнет: нечётные гармоники, тёплый и тихий."""
        tt = _tt(dur)
        ph = _vibrato_phase(f, tt, 4.8, 0.0022, onset=0.6)
        nh = int(min(15, NYQ / f))
        s = np.zeros_like(tt)
        for h in range(1, nh + 1):
            w = (1.0 / h) if h % 2 else (0.10 / h)
            s += w * np.sin(h * ph)
        breath = gaussian_filter(self.rng.uniform(-1, 1, len(tt)), 3) * 0.02
        env = _env_adsr(tt, 0.10, 0.32, dur, curve=1.3)
        return vol * env * (s / 1.5 + breath)

    def sax(self, f, dur, vol):
        """Альт-саксофон: все гармоники (конический ствол), форманты, дыхание, подъезд к ноте снизу, вибрато к концу ноты."""
        tt = _tt(dur)
        scoop = 1 - 0.035 * np.exp(-tt / 0.045)
        vib = 1 + 0.0055 * np.sin(2 * np.pi * 5.0 * tt + self.r.uniform(0, 6.28)) * np.clip((tt - 0.35) / 0.6, 0, 1)
        ph = 2 * np.pi * f * np.cumsum(scoop * vib) / SR
        nh = int(min(22, NYQ / f))
        s = np.zeros_like(tt)
        for h in range(1, nh + 1):
            fh = f * h
            form = 0.35 + math.exp(-((fh - 520) / 260) ** 2) + 0.75 * math.exp(-((fh - 1500) / 450) ** 2) + 0.25 * math.exp(-((fh - 2900) / 600) ** 2)
            s += form / h ** 0.85 * np.sin(h * ph + 0.3 * h)
        breath = gaussian_filter(self.rng.uniform(-1, 1, len(tt)), 1.4)
        breath = breath - gaussian_filter(breath, 30)
        env = _env_adsr(tt, 0.07, 0.30, dur, curve=1.2) * (0.9 + 0.1 * np.minimum(1, tt / 0.5))
        return vol * env * (s / 5.0 + 0.10 * breath * (0.4 + 0.6 * np.exp(-tt / 0.15)))

    def timp_roll(self, f, dur, vol):  # очень тихий низкий гул для глубины
        tt = _tt(dur)
        s = np.sin(2 * np.pi * f * tt) * (1 + 0.3 * np.sin(2 * np.pi * 0.5 * tt))
        env = _env_adsr(tt, 1.5, 2.0, dur)
        return vol * env * s

    def surf(self, dur, vol):
        m = int(dur * SR)
        x = gaussian_filter(self.rng.uniform(-1, 1, m), 14)
        tt = np.arange(m) / SR
        lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.09 * tt + 1.0) * np.sin(2 * np.pi * 0.047 * tt)
        return vol * x / (np.abs(x).max() + 1e-9) * lfo

    def reverb(self, sig, size=2.8, wet=0.38, damp=2.0):
        n = int(size * SR)
        tt = np.arange(n) / SR
        ir = self.rng.normal(0, 1, n) * np.exp(-tt * (6.9 / size))
        ir = gaussian_filter(ir, damp)
        for d, g in ((0.019, 0.5), (0.031, 0.4), (0.047, 0.3), (0.071, 0.22)):
            ir[int(d * SR)] += g
        ir /= np.sqrt(np.sum(ir ** 2))
        wet_sig = fftconvolve(sig, ir)[:len(sig)] * 0.09
        return sig * (1 - wet) + wet_sig * wet * 6


MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
DORIAN = [0, 2, 3, 5, 7, 9, 10]
LYDIAN = [0, 2, 4, 6, 7, 9, 11]

# прогрессии — ступени (0 = тоника); аккорды берутся терциями от ступени
PROGS = {
    "pop": [0, 4, 5, 3], "sad": [5, 3, 0, 4], "dream": [0, 3, 5, 3], "jazz": [0, 5, 1, 4], "modal": [0, 1, 0, 6],
    "hymn": [0, 3, 0, 4], "walk": [0, 2, 3, 4],
    # третий месяц — гармонии в духе трендовых спокойных треков (сами мелодии свои, каждый раз новые)
    "epic": [0, 5, 2, 6], "lament": [0, 3, 6, 2], "vamp": [0, 3, 0, 3], "canon": [0, 4, 5, 2, 3, 0, 3, 4], "dvamp": [0, 3, 0, 6],
}

STYLES = {
    "orch_dawn": dict(base=261.63, scale=MAJOR, prog="dream", bar=4.6, lead="flute", harp=True, piano=False, choir=False, horns=False, ext=(6, 8), bg=None),
    "orch_hope": dict(base=196.00, scale=MAJOR, prog="pop", bar=4.2, lead="oboe", harp=False, piano=True, choir=False, horns=True, ext=(6,), bg=None),
    "orch_cello": dict(base=220.00, scale=MINOR, prog="sad", bar=4.8, lead="cello", harp=False, piano=True, choir=False, horns=False, ext=(6,), bg=None),
    "orch_night": dict(base=146.83, scale=MINOR, prog="modal", bar=5.2, lead="celesta", harp=True, piano=False, choir=True, horns=False, ext=(6, 8), bg=None),
    "orch_sea": dict(base=174.61, scale=MAJOR, prog="dream", bar=4.6, lead="flute", harp=True, piano=False, choir=True, horns=False, ext=(6,), bg="surf"),
    "orch_winter": dict(base=164.81, scale=MINOR, prog="hymn", bar=5.0, lead="celesta", harp=False, piano=True, choir=True, horns=False, ext=(6, 8), bg=None),
    "orch_horns": dict(base=233.08, scale=MAJOR, prog="hymn", bar=4.8, lead="cello", harp=True, piano=False, choir=False, horns=True, ext=(6,), bg=None),
    "orch_lullaby": dict(base=293.66, scale=MAJOR, prog="walk", bar=4.4, lead="celesta", harp=True, piano=False, choir=False, horns=False, ext=(6, 8), bg=None),
    "orch_dorian": dict(base=220.00, scale=DORIAN, prog="modal", bar=5.0, lead="oboe", harp=True, piano=False, choir=True, horns=False, ext=(6,), bg=None),
    "orch_lydian": dict(base=261.63, scale=LYDIAN, prog="pop", bar=4.4, lead="flute", harp=False, piano=True, choir=False, horns=True, ext=(6, 8), bg=None),
}
# Третий месяц: «перебор фортепиано + струнные вступают постепенно», сольная скрипка и кларнет, мажорные септаккорды.
STYLES.update({
    "cine_piano": dict(base=220.00, scale=MINOR, prog="epic", bar=4.0, lead="felt", harp=False, piano=False, choir=False, horns=False, ext=(6,), bg=None,
                       arp=[0, 4, 7, 9, 11, 9, 7, 4], build=True),
    "cine_violin": dict(base=164.81, scale=MINOR, prog="lament", bar=4.4, lead="violin", harp=False, piano=False, choir=True, horns=False, ext=(6,), bg=None,
                        arp=[0, 4, 7, 4, 9, 4, 7, 4], build=True),
    "dream_maj7": dict(base=196.00, scale=MAJOR, prog="vamp", bar=4.6, lead="felt", harp=False, piano=False, choir=True, horns=False, ext=(6, 8), ext_p=1.0, bg=None,
                       arp=[0, 4, 6, 9, 11, 9, 6, 4]),
    "cozy_clarinet": dict(base=174.61, scale=MAJOR, prog="pop", bar=4.2, lead="clarinet", harp=False, piano=False, choir=False, horns=False, ext=(6,), bg=None,
                          arp=[0, 4, 7, 9, 7, 4, 7, 4]),
    "ballad_violin": dict(base=196.00, scale=MAJOR, prog="sad", bar=4.4, lead="violin", harp=False, piano=False, choir=False, horns=True, ext=(6,), bg=None,
                          arp=[0, 4, 7, 9, 11, 9, 7, 4], build=True),
    "canon_strings": dict(base=146.83, scale=MAJOR, prog="canon", bar=4.0, lead="violin", harp=True, piano=False, choir=False, horns=False, ext=(), bg=None, build=True),
    "dorian_clarinet": dict(base=146.83, scale=DORIAN, prog="dvamp", bar=4.6, lead="clarinet", harp=False, piano=False, choir=True, horns=False, ext=(6,), bg=None,
                            arp=[0, 4, 7, 9, 7, 4, 2, 4]),
})
# саксофон — Михаил послушал и одобрил (11.11.2026)
STYLES["sax_ballad"] = dict(base=155.56, scale=MAJOR, prog="jazz", bar=4.8, lead="sax", harp=False, piano=False, choir=False, horns=False, ext=(6, 8), ext_p=1.0, bg=None,
                            arp=[0, 4, 6, 9, 11, 9, 6, 4], build=True)
NEW3 = ["cine_piano", "cine_violin", "dream_maj7", "cozy_clarinet", "ballad_violin", "canon_strings", "dorian_clarinet", "sax_ballad"]
ORCH = [k for k in STYLES if k not in NEW3]


def make_music(style, total, seed, line_times=()):
    st = STYLES[style]
    o = Orchestra(total, seed)
    r = o.r
    base, scale, bar = st["base"], st["scale"], st["bar"]
    prog = PROGS[st["prog"]]
    n_sc = len(scale)

    def freq(deg, octave=0):
        return base * 2 ** ((scale[deg % n_sc] + 12 * (deg // n_sc) + 12 * octave) / 12)

    lead = {"flute": o.flute, "oboe": o.oboe, "cello": o.cello, "celesta": o.celesta, "felt": o.felt, "violin": o.violin, "clarinet": o.clarinet, "sax": o.sax}[st["lead"]]
    n_bars = int(math.ceil((total - 1.0) / bar))
    # ---------------------------------------------------------- струнные + бас + расширения
    t = 0.4
    for b in range(n_bars):
        root = prog[b % len(prog)]
        chord = [root, root + 2, root + 4] + [root + e for e in st["ext"] if r.random() < st.get("ext_p", 0.7)]
        # динамика: мягкая волна по фразам из 4 тактов
        phrase_pos = (b % 4) / 4
        dyn = 0.75 + 0.25 * math.sin(math.pi * phrase_pos)
        if b == n_bars - 1:
            dyn *= 0.8
        dur = bar + 1.2
        if st.get("arp"):
            # перебор фортепиано восьмыми с педалью: бас — нижняя тоника аккорда
            step8 = bar / 8
            acc = [1.0, 0.62, 0.7, 0.66, 0.8, 0.62, 0.7, 0.6]
            for j, d in enumerate(st["arp"]):
                oc = -2 if j == 0 else -1
                o.put(o.felt(freq(root + d, oc), min(3.2, bar * 0.8), 0.085 * acc[j] * (0.85 + 0.15 * dyn)), t + j * step8 + r.uniform(0, 0.012))
        if st.get("build"):
            # струнные вступают постепенно: сначала тихий фон, к 3-му такту — в полную силу
            dyn *= 0.30 + 0.70 * min(1.0, b / 3.0)
        # контрабас + виолончели (корень, квинта)
        o.put(o.strings(freq(root, -2), dur, 0.050 * dyn, voices=2, att=0.9, bright=0.8), t)
        o.put(o.strings(freq(root, -1), dur, 0.045 * dyn, voices=3, att=1.0, bright=0.9), t + 0.05)
        o.put(o.strings(freq(root + 4, -1), dur, 0.035 * dyn, voices=3, att=1.1, bright=0.9), t + 0.08)
        # альты и скрипки — терция, септима/нона
        for j, d in enumerate(chord[1:]):
            o.put(o.strings(freq(d, 0 if j < 2 else 1), dur, 0.03 * dyn, voices=4, att=1.2 + 0.1 * j), t + 0.1 + 0.06 * j)
        o.put(o.strings(freq(root, 1), dur, 0.022 * dyn, voices=4, att=1.6), t + 0.2)
        if st["horns"]:
            o.put(o.horn(freq(root, -1), dur * 0.9, 0.05 * dyn), t + 0.15)
            o.put(o.horn(freq(root + 4, -1), dur * 0.9, 0.035 * dyn), t + 0.2)
        if st["choir"] and b % 2 == 1:
            for j, d in enumerate(chord[:3]):
                o.put(o.choir(freq(d, 0), dur, 0.035 * dyn), t + 0.3 + 0.1 * j)
        if st["harp"]:
            arp = [root, root + 2, root + 4, root + 7, root + 9, root + 11, root + 9, root + 7]
            step = bar / len(arp)
            for j, d in enumerate(arp):
                o.put(o.harp(freq(d, -1), 2.6, (0.075 if j == 0 else 0.055) * dyn), t + j * step + r.uniform(0, 0.015))
        if st["piano"]:
            for j, d in enumerate([root, root + 4, root + 2, root + 4]):
                o.put(o.piano(freq(d, 0 if j else -1), 3.0, (0.07 if j == 0 else 0.05) * dyn), t + j * bar / 4 + r.uniform(0, 0.015))
        t += bar
    # ---------------------------------------------------------- мелодия: мотив + вариации, фразы по 2 такта
    rhythms = [[2, 1, 1, 2, 2], [3, 1, 2, 2], [2, 2, 1, 1, 2], [1, 1, 2, 4]]
    beat = bar / 4

    def gen_motif():
        deg = n_sc + r.choice([0, 2, 4])
        rh = r.choice(rhythms)
        notes, tt, ri = [], 0.0, 0
        while tt < 2 * bar - 1e-6:
            nb = rh[ri % len(rh)]
            ri += 1
            dur = min(nb * beat, 2 * bar - tt)
            deg += r.choice([-2, -1, 1, 2]) if r.random() < 0.7 else r.choice([-4, -3, 3, 4])
            deg = max(n_sc - 2, min(2 * n_sc + 2, deg))
            notes.append((tt, dur, deg, r.random() < 0.12))
            tt += dur
        return notes

    motif = gen_motif()
    t = 0.4 + bar
    phrase = 0
    lead_oct = {"flute": 1, "oboe": 0, "cello": -1, "celesta": 1, "felt": 1, "violin": 0, "clarinet": 0, "sax": 0}[st["lead"]]
    while t < total - 3.0:
        var = phrase % 4
        notes = motif if var in (0, 2) else ([(a, b, d + r.choice([1, -1, 2]), rs) for a, b, d, rs in motif] if var == 1 else gen_motif())
        if var == 3:
            motif = notes
        swell = 0.8 + 0.2 * math.sin(math.pi * (phrase % 2) / 2 + 0.3)
        for j, (a, dur, deg, rest) in enumerate(notes):
            at = t + a
            if at > total - 2.5:
                break
            chord_root = prog[int((at - 0.4) // bar) % len(prog)]
            tones = {(chord_root + k) % n_sc for k in (0, 2, 4)}
            if j == len(notes) - 1 or r.random() < 0.5:
                cand = [d for d in range(n_sc - 2, 2 * n_sc + 3) if d % n_sc in tones]
                deg = min(cand, key=lambda d: abs(d - deg))
            if rest:
                continue
            vol = {"flute": 0.075, "oboe": 0.07, "cello": 0.11, "celesta": 0.1, "felt": 0.15, "violin": 0.085, "clarinet": 0.08, "sax": 0.11}[st["lead"]] * swell
            o.put(lead(freq(deg, lead_oct), dur * (1.8 if st["lead"] in ("celesta", "felt") else 1.0) + 0.2, vol), at + r.uniform(0, 0.02))
        t += 2 * bar
        phrase += 1
    # ---------------------------------------------------------- искорки челесты на появление строк
    for tl in line_times:
        o.put(o.celesta(freq(2 * n_sc + r.choice([0, 2, 4]), 1), 2.2, 0.035), tl + 0.1)
    # ---------------------------------------------------------- финальный аккорд
    o.put(o.strings(freq(0, -2), 4.5, 0.05, voices=3, att=1.0), total - 3.0)
    for j, d in enumerate((0, 2, 4, 7)):
        o.put(o.strings(freq(d, 0 if j < 3 else 1), 4.5, 0.03, voices=4, att=1.4), total - 3.0 + 0.08 * j)
    if st["bg"] == "surf":
        o.put(o.surf(total + 1, 0.05), 0)
    a = o.a[:int((total + 0.5) * SR)]
    a = o.reverb(a, size=3.0, wet=0.42, damp=3.2)
    fade = int(2.0 * SR)
    a[-fade:] *= np.linspace(1, 0, fade)
    a[:int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
    a = np.tanh(a * 1.5) / 1.5
    return a
