"""Три свои пьесы «киношного» склада на чистых инструментах (ноты и гармония свои, от образцов — только характер):
  vremya  — «Время»:  медленный круг из четырёх аккордов, слой за слоем от фортепиано до полного оркестра и тихая кода
  orbita  — «Орбита»: орган и неизменная звенящая фигура фортепиано над плавно сходящим басом, размер 3/4
  polyot  — «Полёт»:  бегущий перебор фортепиано по кругу аккордов, струнные волнами, низкий голос в кульминации
python3 kino.py <пьеса> <файл.wav> [LUFS]     — рендер (24 бита, по умолчанию −18 LUFS, без лимитера)"""
import math
import os
import sys
import time

import numpy as np

import theme as th
from theme import SR, m, horn, timp, piano
from rassvet4 import voice, celesta, fdrum, write24, lufs
from cathedral import VOWEL_A, VOWEL_U
from chisto import clean_line, sp_strings, sp_bass, sp_choir, organ_soft, taiko, master_clean, harp, low_swell
import golos as G

rng = np.random.default_rng(77)
MAJ = (0, 2, 4, 5, 7, 9, 11)


class Grid:
    """сетка тактов: bt(такт, доля) -> секунды"""

    def __init__(self, bpm, bpb, tr, pre=0.4):
        self.BEAT = 60 / bpm
        self.bpb = bpb
        self.BAR = bpb * self.BEAT
        self.tr = tr
        self.pre = pre

    def bt(self, b, x=0.0):
        return self.pre + b * self.BAR + x * self.BEAT

    def n(self, name):
        return m(name) + self.tr

    def chords(self, H):
        return {k: (self.n(b), [self.n(x) for x in ts]) for k, (b, ts) in H.items()}


def mel_notes(g, mel, vel, shift=0, breaths=()):
    """mel = {такт: [(доля, длительность, нота, гласная)]} -> [(начало, конец, midi, громкость, гласная)]"""
    out = []
    for b in sorted(mel):
        for x, d, nt, vw in mel[b]:
            out.append([g.bt(b, x) - 0.02, g.bt(b, x + d), g.n(nt) + shift, vel[b] if isinstance(vel, dict) else vel, vw, b])
    for i in range(len(out) - 1):
        if out[i][5] in breaths and out[i + 1][5] != out[i][5]:
            out[i][1] -= min(0.30, 0.45 * (out[i][1] - out[i][0]))
    return out


def with_rests(notes):
    """для clean_line: нота тянется до начала следующей, поэтому паузы вставляются нотами нулевой громкости"""
    out = []
    for i, (a, e, mi, v) in enumerate(notes):
        out.append((a, e, mi, v))
        if i + 1 < len(notes) and notes[i + 1][0] - e > 0.06:
            out.append((e, notes[i + 1][0], mi, 0.0))
    return out


def sing(bus, notes, gain=1.0, send=0.36):
    """низкий голос двумя дублями"""
    nt = [(a, e, mi, v) for a, e, mi, v, vw, b in notes]
    vw = [x[4] for x in notes]
    sig, ts = voice(nt, vw, seed=11)
    bus.add(sig, ts, pan=-0.08, send=send, gain=1.2 * gain)
    sig, ts = voice(nt, vw, seed=29, detune=6, vib=0.005)
    bus.add(sig, ts + 0.019, pan=0.1, send=send + 0.04, gain=0.62 * gain)


def third_below(mi, pcs, scale):
    """второй голос: терция вниз по ладу, а если она спорит с аккордом — кварта"""
    pc = mi % 12
    if pc not in scale:
        return mi - 3
    k = scale.index(pc)
    third = mi - (pc - scale[(k - 2) % 7]) % 12
    fourth = mi - (pc - scale[(k - 3) % 7]) % 12
    return third if (third % 12 in pcs or fourth % 12 not in pcs) else fourth


def strings(bus, notes, kind="viol", pan=-0.3, send=0.34, gain=1.0):
    nt = with_rests([(a, e, mi, v) for a, e, mi, v, *_ in notes])
    if kind == "viol":
        sig, ts = clean_line(nt, sp_strings(3500, 1.1), voices=4, att=0.3, rel=2.0, vib=0.0038, glide=0.022, fmax=6500)
    else:                                                    # виолончели
        sig, ts = clean_line(nt, sp_strings(1500, 1.3), voices=2, att=0.4, rel=1.2, vib=0.004, glide=0.03, fmax=2500)
    bus.add(sig, ts, pan=pan, send=send, gain=gain)


def pad(bus, segs, start, lo="E3", hi="D5", kind="str", tr=0):
    """три голоса подложки с голосоведением; segs = [(начало, конец, [тоны аккорда], громкость, ярко?)]"""
    voicing = list(start)
    lines = [[], [], []]
    for a, e, tones, v, *_ in segs:
        voicing = G.vlead(voicing, {p % 12 for p in tones}, m(lo) + tr, m(hi) + tr)
        for k in range(3):
            lines[k].append((a, e, voicing[k], v))
    for k in range(3):
        if kind == "str":
            sig, ts = clean_line(lines[k], sp_strings(1800, 1.3), voices=3, att=1.3, rel=2.5, vib=0.004, glide=0.07, fmax=2600)
            bus.add(sig, ts + 0.04 * k, pan=-0.35 + 0.3 * k, send=0.34)
        else:                                                # орган
            for (a, e, mi, v), sg in zip(lines[k], segs):
                if v > 0:
                    bus.add(organ_soft(mi, e - a + 0.1, v * 1.8, rel=0.7, bright=bool(sg[4]) if len(sg) > 4 else False), a,
                            pan=-0.3 + 0.3 * k, send=0.6)


def bass_str(bus, notes):
    sig, ts = clean_line(notes, sp_bass(), voices=1, att=0.9, rel=2.5, vib=0.0, glide=0.05, fmax=420, lo_hz=55)
    bus.add(sig, ts, pan=0.15, send=0.25)


def finale(bus, g, t0, tonic4, vel=0.15, cel=True):
    """тихий финал: фортепиано поднимается по звукам тоники, наверху — челеста"""
    for k, d in enumerate((0, 7, 12, 16, 19, 24)):
        bus.add(piano(tonic4 + d, 4.5, vel - 0.012 * k), t0 + 0.5 * g.BEAT * k, pan=0.12, send=0.55)
    if cel:
        for k, d in enumerate((31, 28, 24)):
            bus.add(celesta(tonic4 + d, 0.045), t0 + g.BEAT * (3.4 + 0.5 * k), pan=-0.2, send=0.6)


# ====================================================================== «ВРЕМЯ»
def vremya():
    """Си-бемоль мажор (пишется в до), 60 уд/мин. Круг C – G/B – Am – F пять раз, с каждым кругом новый слой; кода — одно фортепиано."""
    g = Grid(60, 4, -2)
    Hc = g.chords({"C": ("C2", ["E3", "G3", "C4"]), "G/B": ("B1", ["D3", "G3", "B3"]), "Am": ("A1", ["E3", "A3", "C4"]),
                   "F": ("F1", ["F3", "A3", "C4"]), "G": ("G1", ["D3", "G3", "B3"]), "F/C": ("C2", ["F3", "A3", "C4"])})
    t4 = g.n("C4")
    scale = [(t4 + d) % 12 for d in MAJ]
    CYC = ["C", "G/B", "Am", "F"]
    bars = [CYC[b % 4] for b in range(20)]
    bars[19] = ("F", "G")
    bars += ["C", "F/C", "C"]
    NB = len(bars)                                           # 23; последний такт — финальный аккорд
    fin = NB - 1
    end_t = g.bt(fin) + 1.6 * g.BAR
    th.TOTAL = end_t + 7
    bus = th.Bus()
    cyc = lambda b: min(b // 4, 5)                           # noqa: E731  0..4 круги, 5 — кода

    segs = []
    for b, ch in enumerate(bars):
        for c, x, d in ([(ch[0], 0, 2), (ch[1], 2, 2)] if isinstance(ch, tuple) else [(ch, 0, 4)]):
            segs.append((g.bt(b, x), g.bt(b, x + d), c, b))
    segs[-1] = (segs[-1][0], end_t, segs[-1][2], segs[-1][3])

    # тема (4 такта) и её окончания
    A = {0: [(0, 2, "E4", "o"), (2, 1, "G4", "a"), (3, 1, "C5", "a")],
         1: [(0, 3, "D5", "o"), (3, 1, "B4", "a")],
         2: [(0, 2, "C5", "a"), (2, 2, "E5", "o")],
         3: [(0, 1, "D5", "a"), (1, 1, "C5", "a"), (2, 2, "A4", "o")]}
    A_last = [(0, 1, "D5", "a"), (1, 1, "C5", "a"), (2, 2, "B4", "o")]          # над F → G, ведёт в тонику
    Bc = {0: [(0, 4, "G5", "a")], 1: [(0, 3, "G5", "a"), (3, 1, "D5", "a")],     # верхний подголосок скрипок
          2: [(0, 2, "E5", "a"), (2, 2, "A5", "a")], 3: [(0, 2, "A5", "a"), (2, 1, "G5", "a"), (3, 1, "F5", "a")]}

    def theme(c, last=False):
        d = {4 * c + k: v for k, v in A.items()}
        if last:
            d[4 * c + 3] = A_last
        return d

    # ---- фортепиано: шаг четвертями все пять кругов
    PIA = {"C": ["E3", "G3", "C4", "G3"], "G/B": ["G3", "B3", "D4", "B3"], "Am": ["E3", "A3", "C4", "A3"],
           "F": ["F3", "A3", "C4", "A3"], "G": ["G3", "B3", "D4", "B3"], "F/C": ["F3", "A3", "C4", "A3"]}   # не ниже ре малой октавы
    pv = [0.21, 0.19, 0.17, 0.15, 0.15]
    for a, e, c, b in segs:
        if b >= 20:
            continue
        pat = [g.n(x) for x in PIA[c]]
        x0 = int(round((a - g.bt(b)) / g.BEAT))
        for j in range(int(round((e - a) / g.BEAT))):
            jj = x0 + j
            bus.add(piano(pat[jj], g.BEAT * 1.6, pv[cyc(b)] * (1.0 if jj == 0 else 0.72)), a + j * g.BEAT + rng.uniform(0, 0.006),
                    pan=-0.15 + 0.07 * jj, send=0.38)
    # ---- подложка струнных: входит со второй половины первого круга
    padv = {0: 0.0, 1: 0.12, 2: 0.13, 3: 0.13, 4: 0.15}
    ps = []
    for a, e, c, b in segs:
        v = 0.065 if b in (2, 3) else padv.get(cyc(b), 0.0)
        if b == 20:
            v = 0.10
        elif b == 21:
            v = 0.055
        elif b == 22:
            v = 0.05
        ps.append((a, e, Hc[c][1], v))
    pad(bus, [s for s in ps if s[0] >= g.bt(2) - 1e-6], [t4 - 8, t4 - 5, t4], tr=g.tr)
    # ---- бас струнных со второго круга
    bv = {0: 0.13, 1: 0.18, 2: 0.21, 3: 0.23, 4: 0.27}
    bass_str(bus, [(a, e, Hc[c][0] + 12, bv.get(cyc(b), 0.12 if b == 20 else 0.08) * 0.75) for a, e, c, b in segs])
    # ---- круг 2: тема у виолончелей
    strings(bus, mel_notes(g, theme(1), 0.24, shift=-12, breaths=(5, 7)), kind="cello", pan=0.25, send=0.3)
    # ---- круг 3: тема у скрипок октавой выше, перебор арфы, мягкий большой барабан
    strings(bus, mel_notes(g, theme(2), 0.32, shift=12, breaths=(9, 11)))
    # ---- круг 4: тема у низкого голоса, скрипки ведут верхний подголосок
    v4 = mel_notes(g, theme(3), 0.36, breaths=(13, 15))
    strings(bus, mel_notes(g, {12 + k: v for k, v in Bc.items()}, 0.16, breaths=(13, 15)), pan=-0.3)
    # ---- круг 5: голос с вторым голосом, скрипки — тема, хор, полные ударные; такт 20 — общий приход в тонику
    v5 = mel_notes(g, theme(4, last=True), 0.47, breaths=(17,))
    arrive = mel_notes(g, {20: [(0, 3.4, "C5", "a")]}, 0.40)
    sing(bus, v4 + v5 + arrive)
    hm = []
    for a, e, mi, v, vw, b in v5 + arrive:
        c = [s[2] for s in segs if s[0] <= a + 0.03][-1]
        pcs = {Hc[c][0] % 12} | {x % 12 for x in Hc[c][1]}
        hm.append((a, e, third_below(mi, pcs, scale), v * 0.62))
    sig, ts = voice(hm, ["o"] * len(hm), seed=47, vib=0.004)
    bus.add(sig, ts + 0.01, pan=0.22, send=0.42, gain=0.75)
    strings(bus, mel_notes(g, theme(4, last=True), 0.19, shift=12, breaths=(17,)) + mel_notes(g, {20: [(0, 3.6, "C5", "a")]}, 0.15, shift=12))
    ch = [(a, e, Hc[c][1][2] + 12, 0.24) for a, e, c, b in segs if 16 <= b <= 20]
    sig, ts = clean_line(ch, sp_choir(VOWEL_A), voices=6, att=1.2, rel=2.2, vib=0.0035, glide=0.06, fmax=4000, det=10)
    bus.add(sig, ts, pan=0.0, send=0.55, gain=0.42)
    # ---- арфа восьмыми (круги 3–5), валторны (круги 4–5)
    for a, e, c, b in segs:
        k = cyc(b)
        tn = Hc[c][1]
        if 2 <= k <= 4:
            md = [t + 12 for t in tn]
            pat = [md[0], md[1], md[2], md[0] + 12, md[1] + 12, md[2], md[1], md[0] + 12]
            x0 = int(round((a - g.bt(b)) / (g.BEAT / 2)))
            v = (0.09, 0.09, 0.10)[k - 2]
            for j in range(int(round((e - a) / (g.BEAT / 2)))):
                jj = x0 + j
                bus.add(harp(pat[jj], v * (1.0 if jj % 4 == 0 else 0.75)), a + j * g.BEAT / 2 + rng.uniform(0, 0.008),
                        pan=-0.45 + 0.08 * (jj % 4), send=0.35)
        if 3 <= k <= 4:
            bus.add(horn(tn[1] + (12 if tn[1] < g.n("G3") else 0), e - a + 0.05, 0.055 if k == 3 else 0.075), a + 0.01, pan=0.25, send=0.45)
    # ---- ударные
    for b in range(8, 20):
        k = cyc(b)
        if k == 2:
            bus.add(taiko(0.17), g.bt(b), send=0.35)
            bus.add(fdrum(0.08, low=False), g.bt(b, 2), pan=0.15, send=0.25)
        elif k == 3:
            bus.add(taiko(0.20), g.bt(b), send=0.35)
            bus.add(taiko(0.12), g.bt(b, 2), send=0.35)
            bus.add(fdrum(0.08), g.bt(b, 1.5), send=0.25)
            bus.add(fdrum(0.06, low=False), g.bt(b, 3.5), pan=-0.15, send=0.25)
        else:
            for x_, tv in ((0, 0.30), (1.5, 0.15), (2, 0.24), (3, 0.17), (3.5, 0.12)):
                bus.add(taiko(tv), g.bt(b, x_), send=0.35)
            bus.add(fdrum(0.09, low=False), g.bt(b, 1), pan=0.15, send=0.25)
            bus.add(fdrum(0.09, low=False), g.bt(b, 2.5), pan=-0.15, send=0.25)
    for b, v in ((12, 0.13), (16, 0.16), (18, 0.12), (20, 0.17)):
        bus.add(timp(G.tfit(Hc[bars[b] if isinstance(bars[b], str) else bars[b][0]][0]), v, 4.0), g.bt(b), send=0.4)
    for b in (16, 20):
        bus.add(G.shimmer(g.BAR * 0.95, 0.09, t4), g.bt(b - 1) + g.BAR * 0.05, send=0.4)
        bus.add(low_swell(G.tfit(Hc["F" if b == 16 else "G"][0]), 2 * g.BEAT, 0.07), g.bt(b - 1, 2), send=0.4)
    bus.add(taiko(0.28), g.bt(20), send=0.4)
    # ---- кода: одно фортепиано, тема шёпотом, и финальный аккорд
    for b, c in ((20, "C"), (21, "F/C")):
        for j, nt in enumerate(PIA[c]):
            bus.add(piano(g.n(nt), g.BEAT * 1.8, (0.15 if b == 20 else 0.14) * (1.0 if j == 0 else 0.72)), g.bt(b, j), pan=-0.15 + 0.07 * j, send=0.42)
    for x, nt, v in ((1, "E5", 0.11), (3, "G5", 0.10)):
        bus.add(piano(g.n(nt), 3.0, v), g.bt(21, x), pan=0.2, send=0.5)
    bus.add(timp(G.tfit(Hc["C"][0]), 0.06, 4.5), g.bt(fin), send=0.45)
    finale(bus, g, g.bt(fin), t4)
    return bus, end_t, 5.0


# ====================================================================== «ОРБИТА»
def orbita():
    """Ля мажор (пишется в до), 3/4, 100 уд/мин. Над сходящим басом C–B–A–G–F–E–D–G звенит одна и та же фигура фортепиано;
    орган растёт от еле слышного до полного, в третьем проведении вступает низкий голос."""
    g = Grid(100, 3, -3)
    Hc = g.chords({"C": ("C2", ["E3", "G3", "C4"]), "G/B": ("B1", ["D3", "G3", "B3"]), "Am7": ("A1", ["E3", "G3", "C4"]),
                   "C/G": ("G1", ["E3", "G3", "C4"]), "F": ("F1", ["F3", "A3", "C4"]), "C/E": ("E2", ["E3", "G3", "C4"]),
                   "Dm7": ("D2", ["F3", "A3", "C4"]), "G": ("G1", ["D3", "G3", "B3"])})
    FIG = {"C": ["E5", "G5", "C6", "G5", "E5", "G5"], "G": ["D5", "G5", "B5", "G5", "D5", "G5"], "F": ["F5", "A5", "C6", "A5", "F5", "A5"]}
    FOF = {"C": "C", "G/B": "G", "Am7": "C", "C/G": "C", "F": "F", "C/E": "C", "Dm7": "F", "G": "G"}
    t4 = g.n("C4") + 12                                      # тоника ля: A3 -> A4
    scale = [(t4 + d) % 12 for d in MAJ]
    PASS = ["C", "G/B", "Am7", "C/G", "F", "C/E", "Dm7", "G"]
    bars = PASS * 4 + ["C", "C", "C"]
    NB = len(bars)                                           # 35
    fin = NB - 1
    end_t = g.bt(fin) + 2.6 * g.BAR
    th.TOTAL = end_t + 7
    bus = th.Bus()
    ps_ = lambda b: min(b // 8, 4)                           # noqa: E731  0..3 проведения, 4 — кода
    segs = [(g.bt(b), g.bt(b + 1), c, b) for b, c in enumerate(bars)]
    segs[-1] = (segs[-1][0], end_t, "C", fin)

    # ---- звенящая фигура: фортепиано, со второго проведения — челеста октавой выше
    pv = [0.21, 0.18, 0.13, 0.125, 0.14]
    acc = [1.0, 0.66, 0.6, 0.85, 0.6, 0.68]
    for a, e, c, b in segs[:-1]:
        k = ps_(b)
        fade = 1.0 if b < 33 else 0.8
        for j, nt in enumerate(FIG[FOF[c]]):
            tt = a + j * g.BEAT / 2 + rng.uniform(0, 0.005)
            bus.add(piano(g.n(nt), g.BEAT * 1.4, pv[k] * acc[j] * fade), tt, pan=-0.2 + 0.08 * (j % 3), send=0.4)
            if 1 <= k <= 3 and j in (0, 2, 3):
                bus.add(celesta(g.n(nt) + 12, (0.032, 0.032, 0.036)[k - 1] * (1.0 if j != 2 else 0.8)), tt + 0.004, pan=0.3, send=0.5)
    # ---- орган: педаль с самого начала (еле слышно), аккорды — со второго проведения
    ov = [0.17, 0.19, 0.17, 0.21, 0.12]
    for a, e, c, b in segs:
        bus.add(organ_soft(Hc[c][0] + 12, e - a + 0.1, ov[ps_(b)] * 0.5, rel=0.8, deep=True), a, pan=0.0, send=0.4)
    opad = {0: 0.0, 1: 0.09, 2: 0.075, 3: 0.10, 4: 0.055}
    pad(bus, [(a, e, Hc[c][1], opad[ps_(b)], ps_(b) == 3) for a, e, c, b in segs if b >= 8], [t4 - 8, t4 - 5, t4], kind="organ", tr=g.tr)
    spad_ = {2: 0.05, 3: 0.085, 4: 0.04}
    pad(bus, [(a, e, Hc[c][1], spad_[ps_(b)]) for a, e, c, b in segs if b >= 16], [t4 - 8, t4 - 5, t4], tr=g.tr)
    # ---- мелодия: третье проведение — голос и виолончели; четвёртое — голос, второй голос, скрипки, валторны
    M3 = {16: [(0, 3, "E4", "o")], 17: [(0, 2, "D4", "o"), (2, 1, "G4", "a")], 18: [(0, 3, "C5", "a")],
          19: [(0, 2, "G4", "o"), (2, 1, "E4", "a")], 20: [(0, 3, "A4", "o")], 21: [(0, 2, "G4", "a"), (2, 1, "C5", "a")],
          22: [(0, 2, "D5", "o"), (2, 1, "C5", "a")], 23: [(0, 3, "B4", "o")]}
    M4 = {24: [(0, 2, "C5", "o"), (2, 1, "E5", "a")], 25: [(0, 3, "D5", "o")], 26: [(0, 2, "C5", "a"), (2, 1, "E5", "a")],
          27: [(0, 3, "E5", "o")], 28: [(0, 1, "A4", "a"), (1, 1, "C5", "a"), (2, 1, "F5", "o")], 29: [(0, 3, "E5", "a")],
          30: [(0, 3, "D5", "o")], 31: [(0, 2, "D5", "a"), (2, 1, "B4", "o")], 32: [(0, 5.4, "C5", "a")]}
    v3 = mel_notes(g, M3, 0.37, breaths=(19, 23))
    v4 = mel_notes(g, M4, 0.50, breaths=(27, 31))
    sing(bus, v3 + v4)
    strings(bus, mel_notes(g, M3, 0.075, shift=-12, breaths=(19, 23)), kind="cello", pan=0.25, send=0.3)
    strings(bus, mel_notes(g, M4, 0.17, shift=12, breaths=(27, 31)))
    hm = []
    for a, e, mi, v, vw, b in v4:
        c = bars[b]
        pcs = {Hc[c][0] % 12} | {x % 12 for x in Hc[c][1]}
        hm.append((a, e, third_below(mi, pcs, scale), v * 0.6))
        bus.add(horn(mi, e - a + 0.05, 0.06), a + 0.01, pan=0.25, send=0.45)
    sig, ts = voice(hm, ["o"] * len(hm), seed=47, vib=0.004)
    bus.add(sig, ts + 0.01, pan=0.22, send=0.42, gain=0.72)
    ch = [(a, e, Hc[c][1][2] + 12, 0.22) for a, e, c, b in segs if 24 <= b <= 32]
    sig, ts = clean_line(ch, sp_choir(VOWEL_U), voices=6, att=1.2, rel=2.2, vib=0.0035, glide=0.06, fmax=4000, det=10)
    bus.add(sig, ts, pan=0.0, send=0.55, gain=0.42)
    # ---- редкие удары: большой барабан в начале каждой пары тактов, литавры на гранях
    for b in range(16, 32):
        if b % 2 == 0:
            bus.add(taiko(0.11 if b < 24 else 0.22), g.bt(b), send=0.38)
        elif b >= 24:
            bus.add(taiko(0.10), g.bt(b, 1), send=0.38)
    for b, v in ((24, 0.16), (28, 0.12), (32, 0.14)):
        bus.add(timp(G.tfit(Hc[bars[b]][0]), v, 4.0), g.bt(b), send=0.4)
    bus.add(G.shimmer(g.BAR * 1.9, 0.09, t4 - 12), g.bt(22) + 0.1, send=0.4)
    bus.add(low_swell(G.tfit(Hc["G"][0]), 3 * g.BEAT, 0.07), g.bt(23), send=0.4)
    # ---- финал: аккорд органа и три звёздочки челесты
    for k, d in enumerate((12, 16, 19)):
        bus.add(celesta(t4 + d, 0.05 - 0.006 * k), g.bt(fin, 0.5 + k), pan=-0.15 + 0.15 * k, send=0.6)
    bus.add(piano(t4 - 12, 6.0, 0.12), g.bt(fin), pan=0.0, send=0.5)
    return bus, end_t, 5.0


# ====================================================================== «ПОЛЁТ»
def polyot():
    """Соль мажор (пишется в до), 92 уд/мин. Круг F – G – Am – C/E: бас поднимается ступенями и не садится на тонику
    до самого конца; фортепиано бежит восьмыми, струнные входят волнами, в кульминации — низкий голос."""
    g = Grid(92, 4, -5)
    Hc = g.chords({"F": ("F2", ["F3", "A3", "C4"]), "G": ("G2", ["D3", "G3", "B3"]), "Am": ("A2", ["E3", "A3", "C4"]),
                   "C/E": ("E2", ["E3", "G3", "C4"]), "C": ("C2", ["E3", "G3", "C4"])})
    PIA = {"F": ["A3", "C4", "A4", "F4", "C5", "F4", "A4", "F4"], "G": ["G3", "D4", "B4", "G4", "D5", "G4", "B4", "G4"],
           "Am": ["A3", "E4", "C5", "A4", "E5", "A4", "C5", "A4"], "C/E": ["G3", "C4", "G4", "E4", "C5", "E4", "G4", "E4"]}   # звучит не ниже ре малой октавы
    t4 = g.n("C4") + 12                                      # тоника соль: G3 -> G4
    scale = [(t4 + d) % 12 for d in MAJ]
    LOOP = ["F", "G", "Am", "C/E"]
    bars = [LOOP[b % 4] for b in range(28)] + ["F", "G", "C"]
    NB = len(bars)                                           # 31
    fin = NB - 1
    end_t = g.bt(fin) + 1.5 * g.BAR
    th.TOTAL = end_t + 7
    bus = th.Bus()

    def ps_(b):                                              # 0 — соло фортепиано, 1..3 — волны, 4 — кода
        return 0 if b < 4 else 1 if b < 12 else 2 if b < 20 else 3 if b < 28 else 4
    segs = [(g.bt(b), g.bt(b + 1), c, b) for b, c in enumerate(bars)]
    segs[-1] = (segs[-1][0], end_t, "C", fin)

    # ---- фортепиано восьмыми
    pv = [0.22, 0.17, 0.16, 0.125, 0.15]
    for a, e, c, b in segs[:-1]:
        k = ps_(b)
        for j, nt in enumerate(PIA[c]):
            accn = 1.0 if j == 0 else 0.82 if j == 4 else 0.62
            bus.add(piano(g.n(nt), g.BEAT * 1.2, pv[k] * accn), a + j * g.BEAT / 2 + rng.uniform(0, 0.006), pan=-0.22 + 0.06 * (j % 4), send=0.34)
    # ---- подложка и бас: со второй волны
    padv = {1: 0.09, 2: 0.13, 3: 0.125, 4: 0.06}
    pad(bus, [(a, e, Hc[c][1], padv[ps_(b)]) for a, e, c, b in segs if b >= 4], [t4 - 8, t4 - 5, t4], tr=g.tr)
    bv = {1: 0.19, 2: 0.22, 3: 0.25, 4: 0.13}
    bass_str(bus, [(a, e, Hc[c][0], bv[ps_(b)] * 0.75) for a, e, c, b in segs if b >= 4])
    # ---- мелодия (8 тактов)
    A = {0: [(0, 2, "C5", "o"), (2, 1, "A4", "a"), (3, 1, "C5", "a")],
         1: [(0, 3, "D5", "o"), (3, 1, "B4", "a")],
         2: [(0, 2, "C5", "a"), (2, 2, "E5", "o")],
         3: [(0, 2, "E5", "a"), (2, 1, "C5", "a"), (3, 1, "G4", "o")],
         4: [(0, 1, "A4", "o"), (1, 1, "C5", "a"), (2, 2, "E5", "o")],
         5: [(0, 2, "D5", "a"), (2, 2, "B4", "o")],
         6: [(0, 1, "C5", "a"), (1, 1, "B4", "a"), (2, 2, "A4", "o")],
         7: [(0, 4, "G4", "a")]}
    at = lambda b0: {b0 + k: v for k, v in A.items()}        # noqa: E731
    strings(bus, mel_notes(g, at(4), 0.19, shift=-12, breaths=(7, 11)), kind="cello", pan=0.25, send=0.3)
    strings(bus, mel_notes(g, at(12), 0.31, shift=12, breaths=(15, 19)))
    v3 = mel_notes(g, at(20), 0.41, breaths=(23, 27))
    coda = mel_notes(g, {28: [(0, 4, "A4", "o")], 29: [(0, 4, "B4", "a")], 30: [(0, 5.0, "C5", "o")]}, 0.21)
    sing(bus, v3 + coda)
    strings(bus, mel_notes(g, at(20), 0.185, shift=12, breaths=(23, 27)))
    hm = []
    for a, e, mi, v, vw, b in v3:
        c = bars[b]
        pcs = {Hc[c][0] % 12} | {x % 12 for x in Hc[c][1]}
        hm.append((a, e, third_below(mi, pcs, scale), v * 0.6))
        bus.add(horn(mi, e - a + 0.05, 0.065), a + 0.01, pan=0.25, send=0.45)
    sig, ts = voice(hm, ["o"] * len(hm), seed=47, vib=0.004)
    bus.add(sig, ts + 0.01, pan=0.22, send=0.42, gain=0.72)
    ch = [(a, e, Hc[c][1][2] + 12, 0.23) for a, e, c, b in segs if 20 <= b < 28]
    sig, ts = clean_line(ch, sp_choir(VOWEL_A), voices=6, att=1.2, rel=2.2, vib=0.0035, glide=0.06, fmax=4000, det=10)
    bus.add(sig, ts, pan=0.0, send=0.55, gain=0.42)
    # ---- арфа восьмыми навстречу фортепиано (волны 2–3)
    for a, e, c, b in segs:
        k = ps_(b)
        if k in (2, 3):
            md = [t + 12 for t in Hc[c][1]]
            pat = [md[2] + 12, md[1] + 12, md[0] + 12, md[2], md[1] + 12, md[0] + 12, md[2], md[1]]
            v = 0.09 if k == 2 else 0.09
            for j in range(8):
                bus.add(harp(pat[j], v * (1.0 if j % 4 == 0 else 0.75)), a + j * g.BEAT / 2 + rng.uniform(0, 0.008), pan=0.4 - 0.08 * (j % 4), send=0.36)
    # ---- ударные
    for b in range(12, 28):
        if ps_(b) == 2:
            bus.add(fdrum(0.14), g.bt(b), send=0.25)
            bus.add(fdrum(0.08), g.bt(b, 1.5), send=0.25)
            bus.add(fdrum(0.07, low=False), g.bt(b, 2.5), pan=0.15, send=0.25)
        else:
            bus.add(taiko(0.24), g.bt(b), send=0.35)
            bus.add(taiko(0.15), g.bt(b, 2), send=0.35)
            bus.add(fdrum(0.11), g.bt(b, 1.5), send=0.25)
            bus.add(fdrum(0.08, low=False), g.bt(b, 2.5), pan=0.15, send=0.25)
            bus.add(fdrum(0.07, low=False), g.bt(b, 3.5), pan=-0.15, send=0.25)
    for b, v in ((20, 0.16), (24, 0.12), (30, 0.07)):
        bus.add(timp(G.tfit(Hc[bars[b]][0]), v, 4.0), g.bt(b), send=0.4)
    bus.add(G.shimmer(g.BAR * 0.95, 0.09, t4), g.bt(19) + g.BAR * 0.05, send=0.4)
    bus.add(low_swell(G.tfit(Hc["C/E"][0]), 2 * g.BEAT, 0.07), g.bt(19, 2), send=0.4)
    # ---- финал: первый и единственный раз бас приходит в тонику
    finale(bus, g, g.bt(fin), t4, vel=0.14)
    return bus, end_t, 4.5


PIECES = {"vremya": ("Время", vremya), "orbita": ("Орбита", orbita), "polyot": ("Полёт", polyot)}


def render(name, target=-18.0, tmp_dir="/tmp"):
    global rng
    rng = np.random.default_rng(77)
    G.rng = np.random.default_rng(2026)
    bus, end_t, tail = PIECES[name][1]()
    L, R = master_clean(bus, 0.3)
    cut = int(round((end_t + tail) * SR))
    L, R = L[:cut].copy(), R[:cut].copy()
    fo = int(2.0 * SR)
    w = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo))
    L[-fo:] *= w
    R[-fo:] *= w
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.5, R / pk * 0.5
    tmp = os.path.join(tmp_dir, f"kino_{os.getpid()}_{name}.wav")
    write24(tmp, L, R)
    gain = min(10 ** ((target - lufs(tmp)) / 20), 0.89 / 0.5)
    os.remove(tmp)
    return L * gain, R * gain


if __name__ == "__main__":
    name, out = sys.argv[1], sys.argv[2]
    tgt = float(sys.argv[3]) if len(sys.argv) > 3 else -18.0
    t0 = time.time()
    L, R = render(name, tgt)
    write24(out, L, R)
    pk = max(np.abs(L).max(), np.abs(R).max())
    print(out, "готово:", PIECES[name][0], round(len(L) / SR, 1), "с; пик", round(20 * math.log10(pk), 1), "дБFS;", f"{time.time() - t0:.0f} с")
