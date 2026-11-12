"""Песни с низким голосом на чистом движке (инструменты и мастеринг из rassvet4, без источников шума).
У каждой песни свои ноты, аккорды, размер, темп и звучание. Ноты пишутся в удобной тональности, `tr` сдвигает всё.
python3 golos.py <песня> <файл.wav>      — рендер (24 бита, −14 LUFS, без лимитера)
python3 golos.py check                    — проверка: диапазон голоса и ноты, спорящие с аккордом"""
import math
import os
import sys

import numpy as np

import theme as th
from theme import SR, m, hz, legato_line, horn, timp, piano
from rassvet4 import voice, harp, celesta, fdrum, taiko, kick, sub, pluck, spad, short, master, write24, lufs
from cathedral import line as cline, VOWEL_A, VOWEL_U, organ

rng = np.random.default_rng(2026)
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def bar(ch, mel=None, sec="verse", br=False):
    """такт: аккорд (или пара аккордов), мелодия [(доля, длительность, нота, гласная)], раздел, вдох после такта"""
    return (ch, mel, sec, br)


def style(pad="str", pv=(0.07, 0.09, 0.14, 0.11), arp="harp", intro_arp="piano", drums="frame", spic=0, horns=0.07,
          viol=0.18, choir=0.0, choir_v="a", harm=True, cello=True, cel_mel=0.0, bells=False, drone=0.0, fin="piano",
          lead=(0.42, 0.58, 0.48)):
    return dict(pad=pad, pv=pv, arp=arp, intro_arp=intro_arp, drums=drums, spic=spic, horns=horns, viol=viol, choir=choir,
                choir_v=choir_v, harm=harm, cello=cello, cel_mel=cel_mel, bells=bells, drone=drone, fin=fin, lead=lead)


# ================================================================ ПЕСНИ
SONGS = {}

# ---------------------------------------------------------------- «Колыбельная»: ре мажор, 3/4, арфа и челеста
SONGS["kolybelnaya"] = dict(
    title="Колыбельная", bpm=88, bpb=3, tr=0, tonic="D", hold=2.0,
    H={"D": ("D2", ["D3", "F#3", "A3"]), "G/D": ("D2", ["D3", "G3", "B3"]), "D/F#": ("F#2", ["F#3", "A3", "D4"]),
       "A": ("A1", ["C#3", "E3", "A3"]), "Bm": ("B1", ["D3", "F#3", "B3"]), "G": ("G1", ["D3", "G3", "B3"]),
       "Em7": ("E2", ["D3", "G3", "B3"]), "A7": ("A1", ["C#3", "G3", "A3"])},
    bars=[
        bar("D", None, "intro"), bar("G/D", None, "intro"),
        bar("D", [(0, 2, "F#4", "o"), (2, 1, "A4", "a")]),
        bar("G/D", [(0, 2, "B4", "o"), (2, 1, "G4", "a")]),
        bar("D/F#", [(0, 2, "A4", "o"), (2, 1, "D5", "a")]),
        bar("A", [(0, 3, "C#5", "a")], br=True),
        bar("Bm", [(0, 2, "D5", "o"), (2, 1, "B4", "a")]),
        bar("G", [(0, 2, "G4", "o"), (2, 1, "B4", "a")]),
        bar("D/F#", [(0, 2, "A4", "o"), (2, 1, "F#4", "a")]),
        bar("A7", [(0, 3, "E4", "a")], br=True),
        bar("D", [(0, 2, "F#4", "o"), (2, 1, "A4", "a")]),
        bar("G/D", [(0, 2, "B4", "o"), (2, 1, "G4", "a")]),
        bar("D/F#", [(0, 2, "A4", "o"), (2, 1, "D5", "a")]),
        bar("A", [(0, 2, "C#5", "a"), (2, 1, "E5", "o")]),
        bar("Bm", [(0, 2, "D5", "o"), (2, 1, "B4", "a")]),
        bar("G", [(0, 2, "G4", "o"), (2, 1, "B4", "a")]),
        bar(("Em7", "A7"), [(0, 2, "G4", "o"), (2, 1, "E4", "a")]),
        bar("D", [(0, 3, "D4", "a")], br=True),
        bar("G", [(0, 1, "B4", "o"), (1, 2, "D5", "a")], "climax"),
        bar("A", [(0, 1, "C#5", "o"), (1, 2, "E5", "a")], "climax"),
        bar("D/F#", [(0, 2, "D5", "o"), (2, 1, "A4", "a")], "climax"),
        bar("G", [(0, 3, "B4", "a")], "climax", True),
        bar("Em7", [(0, 1, "G4", "o"), (1, 1, "B4", "a"), (2, 1, "D5", "a")], "climax"),
        bar("A7", [(0, 2, "C#5", "o"), (2, 1, "E5", "a")], "climax"),
        bar("D", [(0, 3, "D5", "o")], "climax"),
        bar("G/D", [(0, 2, "B4", "a"), (2, 1, "A4", "o")], "climax"),
        bar("D", [(0, 3, "F#4", "a")], "end"),
    ],
    style=style(pad="str", pv=(0.05, 0.06, 0.085, 0.08), arp="harp", intro_arp="harp", drums=None, horns=0.045, viol=0.12,
                cel_mel=0.04, fin="celesta", lead=(0.44, 0.54, 0.46)),
)

# ---------------------------------------------------------------- «Дорога»: пишется в соль мажоре, звучит в ми мажоре
SONGS["doroga"] = dict(
    title="Дорога", bpm=96, bpb=4, tr=-3, tonic="G", hold=1.2,
    H={"G": ("G1", ["G3", "B3", "D4"]), "C": ("C2", ["E3", "G3", "C4"]), "G/B": ("B1", ["D3", "G3", "B3"]),
       "Am7": ("A1", ["G3", "C4", "E4"]), "Dsus": ("D2", ["G3", "A3", "D4"]), "D7": ("D2", ["F#3", "C4", "D4"]),
       "D": ("D2", ["F#3", "A3", "D4"]), "Em": ("E2", ["E3", "G3", "B3"])},
    bars=[
        bar("G", None, "intro"), bar("G", None, "intro"),
        bar("G", [(0, 1, "D4", "o"), (1, 1, "G4", "a"), (2, 1, "A4", "a"), (3, 1, "B4", "o")]),
        bar("G", [(0, 3, "D5", "a"), (3, 1, "B4", "o")]),
        bar("C", [(0, 1, "C5", "a"), (1, 1, "B4", "a"), (2, 1, "A4", "o"), (3, 1, "G4", "a")]),
        bar("G/B", [(0, 3, "B4", "o")], br=True),
        bar("Am7", [(0, 1, "E4", "o"), (1, 1, "A4", "a"), (2, 1, "B4", "a"), (3, 1, "C5", "o")]),
        bar("C", [(0, 3, "E5", "a"), (3, 1, "C5", "o")]),
        bar("Dsus", [(0, 1, "D5", "a"), (1, 1, "C5", "a"), (2, 1, "B4", "o"), (3, 1, "A4", "a")]),
        bar("D7", [(0, 3, "A4", "o")], br=True),
        bar("C", [(0, 1, "G4", "o"), (1, 1, "C5", "a"), (2, 2, "E5", "o")], "climax"),
        bar("D", [(0, 3, "D5", "a"), (3, 1, "A4", "o")], "climax"),
        bar("Em", [(0, 1, "G4", "o"), (1, 1, "B4", "a"), (2, 2, "E5", "o")], "climax"),
        bar("G/B", [(0, 3, "D5", "a")], "climax", True),
        bar("C", [(0, 1, "C5", "o"), (1, 1, "D5", "a"), (2, 2, "E5", "a")], "climax"),
        bar("D", [(0, 2, "F#5", "o"), (2, 2, "D5", "a")], "climax"),
        bar("G", [(0, 3, "B4", "o"), (3, 1, "D5", "a")], "climax"),
        bar("D7", [(0, 3, "A4", "o")], "climax", True),
        bar("C", [(0, 1, "C5", "o"), (1, 1, "D5", "a"), (2, 2, "E5", "a")], "climax"),
        bar("D", [(0, 2, "F#5", "o"), (2, 1, "E5", "a"), (3, 1, "D5", "a")], "climax"),
        bar(("Am7", "D7"), [(0, 2, "C5", "o"), (2, 1, "B4", "a"), (3, 1, "A4", "a")], "climax"),
        bar("G", [(0, 4, "G4", "a")], "end"),
    ],
    style=style(pad="synth", pv=(0.05, 0.06, 0.085, 0.07), arp="piano", intro_arp="piano", drums="kick", horns=0.0, viol=0.13,
                cello=False, fin="piano"),
)

# ---------------------------------------------------------------- «Простор»: пентатоника, пишется в до, звучит в соль мажоре
SONGS["prostor"] = dict(
    title="Простор", bpm=66, bpb=4, tr=-5, tonic="C", hold=1.2,
    H={"C": ("C2", ["E3", "G3", "C4"]), "F/C": ("C2", ["F3", "A3", "C4"]), "F": ("F2", ["F3", "A3", "C4"]),
       "G": ("G2", ["D3", "G3", "B3"]), "Am": ("A1", ["E3", "A3", "C4"]), "C/E": ("E2", ["E3", "G3", "C4"])},
    bars=[
        bar("C", None, "intro"), bar("F/C", None, "intro"),
        bar("C", [(0, 1, "G4", "o"), (1, 1, "A4", "a"), (2, 2, "C5", "o")]),
        bar("F/C", [(0, 1.5, "D5", "a"), (1.5, .5, "C5", "a"), (2, 2, "A4", "o")]),
        bar("C", [(0, 1, "G4", "a"), (1, 1, "E4", "o"), (2, 1, "G4", "a"), (3, 1, "A4", "a")]),
        bar("G", [(0, 4, "G4", "o")], br=True),
        bar("C", [(0, 1, "G4", "o"), (1, 1, "A4", "a"), (2, 2, "C5", "o")]),
        bar("F", [(0, 1.5, "D5", "a"), (1.5, .5, "E5", "a"), (2, 2, "D5", "o")]),
        bar("Am", [(0, 1, "C5", "a"), (1, 1, "A4", "o"), (2, 1, "C5", "a"), (3, 1, "D5", "a")]),
        bar("G", [(0, 4, "D5", "o")], br=True),
        bar("F", [(0, 1, "A4", "o"), (1, 1, "C5", "a"), (2, 2, "E5", "o")], "climax"),
        bar("G", [(0, 2, "D5", "a"), (2, 1, "E5", "o"), (3, 1, "G5", "a")], "climax"),
        bar("C/E", [(0, 2, "G5", "a"), (2, 1, "E5", "o"), (3, 1, "D5", "a")], "climax"),
        bar(("F", "G"), [(0, 2, "E5", "o"), (2, 2, "D5", "a")], "climax"),
        bar("C", [(0, 4, "C5", "a")], "end"),
    ],
    style=style(pad="str", pv=(0.07, 0.09, 0.15, 0.12), arp="harp", intro_arp="harp", drums="taiko", horns=0.11, viol=0.2,
                choir=0.45, drone=0.05, fin="piano"),
)

# ---------------------------------------------------------------- «Гимн»: пишется в до, звучит в си-бемоль мажоре; орган, хор, колокол
SONGS["gimn"] = dict(
    title="Гимн", bpm=72, bpb=4, tr=-2, tonic="C", hold=1.2,
    H={"C": ("C2", ["E3", "G3", "C4"]), "F/C": ("C2", ["F3", "A3", "C4"]), "F": ("F1", ["F3", "A3", "C4"]),
       "C/E": ("E2", ["E3", "G3", "C4"]), "G": ("G1", ["D3", "G3", "B3"]), "Am": ("A1", ["E3", "A3", "C4"]),
       "Dm7": ("D2", ["F3", "A3", "C4"]), "Gsus": ("G1", ["D3", "G3", "C4"])},
    bars=[
        bar("C", None, "intro"), bar("F/C", None, "intro"),
        bar("C", [(0, 2, "E4", "o"), (2, 2, "G4", "a")]),
        bar("F", [(0, 3, "A4", "o"), (3, 1, "G4", "a")]),
        bar("C/E", [(0, 2, "G4", "o"), (2, 2, "C5", "a")]),
        bar("G", [(0, 4, "B4", "o")], br=True),
        bar("Am", [(0, 2, "C5", "a"), (2, 2, "E5", "o")]),
        bar("Dm7", [(0, 3, "D5", "a"), (3, 1, "C5", "o")]),
        bar(("F", "G"), [(0, 2, "A4", "a"), (2, 2, "B4", "o")]),
        bar("C", [(0, 4, "C5", "a")], br=True),
        bar("F", [(0, 2, "A4", "o"), (2, 2, "C5", "a")], "climax"),
        bar("C/E", [(0, 3, "E5", "o"), (3, 1, "D5", "a")], "climax"),
        bar("Dm7", [(0, 2, "C5", "o"), (2, 2, "F5", "a")], "climax"),
        bar("G", [(0, 3, "D5", "o"), (3, 1, "B4", "a")], "climax", True),
        bar(("Am", "F"), [(0, 2, "C5", "a"), (2, 2, "A4", "o")], "climax"),
        bar(("Gsus", "G"), [(0, 2, "C5", "a"), (2, 2, "B4", "o")], "climax"),
        bar("C", [(0, 4, "C5", "a")], "end"),
    ],
    style=style(pad="organ", pv=(0.05, 0.06, 0.085, 0.07), arp="harp_soft", intro_arp="harp_soft", drums="timp", horns=0.08,
                viol=0.13, choir=0.5, choir_v="u", bells=True, fin="piano"),
)


# ================================================================ движок
def vlead(prev, pcs, lo, hi):
    """голосоведение подложки: каждый голос идёт к ближайшему звуку аккорда; аккорд всегда полный (с терцией)"""
    cands = [x for x in range(lo, hi + 1) if x % 12 in pcs]
    out = []
    for p in prev:
        out.append(min((c for c in cands if c not in out), key=lambda c: abs(c - p), default=p))
    for p in [q for q in pcs if q not in {x % 12 for x in out}]:
        cnt = {}
        for i, x in enumerate(out):
            cnt.setdefault(x % 12, []).append(i)
        dup = [i for ix in cnt.values() if len(ix) > 1 for i in ix]
        tgt = [c for c in cands if c % 12 == p and c not in out]
        if not dup or not tgt:
            break
        i, c = min(((i, c) for i in dup for c in tgt), key=lambda ic: abs(ic[1] - out[ic[0]]))
        out[i] = c
    return out


def shimmer(dur, vel, t4):
    """взлёт перед кульминацией: тоника, квинта и нона — не спорят ни с одним аккордом лада"""
    n = int((dur + 1.2) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k, d in enumerate((12, 19, 24, 26, 31)):
        for det in (-4, 4):
            s += np.sin(2 * np.pi * hz(t4 + d) * 2 ** (det / 1200) * t + k) / (1 + 0.4 * k)
    e = np.where(t < dur, (t / dur) ** 3, np.exp(-(t - dur) / 0.35))
    return vel * 0.35 * s * e


def bell_major(midi, vel, dur=7.0):
    """колокол с БОЛЬШОЙ терцией в призвуках: у обычного колокола терция малая, и над мажорным аккордом она звучит минором"""
    f0 = hz(midi)
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for r, a, d in ((0.5, 0.35, 0.35), (1.0, 1.0, 0.6), (1.25, 0.3, 0.9), (1.5, 0.35, 1.1), (2.0, 0.4, 1.4), (2.5, 0.2, 2.0),
                    (3.0, 0.15, 2.8), (4.0, 0.08, 3.6)):
        s += a * np.sin(2 * np.pi * f0 * r * t + rng.uniform(0, 6.28)) * np.exp(-t * d)
    return vel * s / 2.5 * (0.5 - 0.5 * np.cos(np.pi * np.clip(t / 0.004, 0, 1))) * np.clip((dur - t) / 0.5, 0, 1)


def tfit(p, lo=38, hi=50):
    while p < lo:
        p += 12
    while p > hi:
        p -= 12
    return p


def prep(song):
    tr, bpb = song["tr"], song["bpb"]
    Hc = {k: (m(b) + tr, [m(x) + tr for x in ts]) for k, (b, ts) in song["H"].items()}
    t4 = m(song["tonic"] + "4") + tr
    while t4 > 68:
        t4 -= 12
    while t4 < 57:
        t4 += 12
    scale = [(t4 + d) % 12 for d in (0, 2, 4, 5, 7, 9, 11)]

    def split(ch):
        if isinstance(ch, tuple):
            return [(ch[0], 0, 2), (ch[1], 2, bpb - 2)]
        return [(ch, 0, bpb)]
    return tr, bpb, Hc, t4, scale, split


def compose(song, over=None):
    St = dict(song["style"])
    St.update(over or {})
    tr, bpb, Hc, t4, scale, split = prep(song)
    BEAT = 60 / song["bpm"]
    BAR = bpb * BEAT
    P = song["bars"]
    nb = len(P)
    secs = [p[2] for p in P]
    pre = 0.8 if secs[0] == "climax" else 0.3

    def bt(b, x=0.0):
        return pre + b * BAR + x * BEAT

    fin_b = nb - 1
    end_t = bt(fin_b) + song.get("hold", 1.2) * BAR
    th.TOTAL = end_t + 6
    bus = th.Bus()
    LV = {"intro": 0, "verse": 1, "climax": 2, "end": 3}
    L8 = 2 * bpb

    def harm_note(mi, c):
        pcs = {Hc[c][0] % 12} | {x % 12 for x in Hc[c][1]}
        pc = mi % 12
        if pc not in scale:
            return mi - 3
        k = scale.index(pc)
        third = mi - (pc - scale[(k - 2) % 7]) % 12
        fourth = mi - (pc - scale[(k - 3) % 7]) % 12
        if third % 12 in pcs or fourth % 12 not in pcs:
            return third
        return fourth

    # ---------- мелодия: низкий голос двумя дублями
    lead = []
    for b, (ch, mel, sec, br) in enumerate(P):
        sg = split(ch)
        for x, d, nt, vw in (mel or []):
            c = [c for c, x0, d0 in sg if x0 <= x + 1e-6][-1]
            lead.append([bt(b, x) - 0.02, end_t if sec == "end" else bt(b, x + d), m(nt) + tr, vw, b, sec, c])
    for i in range(len(lead) - 1):
        b0, b1 = lead[i][4], lead[i + 1][4]
        if b1 != b0 and (P[b0][3] or P[b0][2] != P[b1][2]):
            lead[i][1] -= min(0.30, 0.45 * (lead[i][1] - lead[i][0]))
    lv = dict(zip(("verse", "climax", "end"), St["lead"]))
    notes = [(a, e, mi, lv[sec]) for a, e, mi, vw, b, sec, c in lead]
    vows = [x[3] for x in lead]
    sig, ts = voice(notes, vows, seed=11)
    bus.add(sig, ts, pan=-0.08, send=0.34, gain=1.2)
    sig, ts = voice(notes, vows, seed=29, detune=6, vib=0.005)
    bus.add(sig, ts + 0.019, pan=0.1, send=0.38, gain=0.62)
    hm = [(a, e, harm_note(mi, c), lv[sec] * 0.62) for a, e, mi, vw, b, sec, c in lead if sec == "climax"]
    if hm and St["harm"]:
        sig, ts = voice(hm, ["o"] * len(hm), seed=47, vib=0.004)
        bus.add(sig, ts + 0.01, pan=0.22, send=0.42, gain=0.75)
    vc = [(a, e, mi - 12, 0.09) for a, e, mi, vw, b, sec, c in lead if sec == "verse"]
    if vc and St["cello"]:
        sig, ts = legato_line(vc, voices=3, att=0.4, rel=1.0, bright=0.55, vib=0.004, glide=0.03, noise=0)
        bus.add(sig, ts, pan=0.25, send=0.3)
    # ---------- кульминация: скрипки октавой выше, валторны, челеста
    vn = [(a, e, mi + 12, St["viol"]) for a, e, mi, vw, b, sec, c in lead if sec == "climax"]
    if vn and St["viol"]:
        sig, ts = legato_line(vn, voices=8, att=0.3, rel=2.0, bright=0.62, vib=0.0038, glide=0.022, noise=0)
        bus.add(sig, ts, pan=-0.3, send=0.34)
    for a, e, mi, vw, b, sec, c in lead:
        if sec == "climax" and St["horns"]:
            bus.add(horn(mi, e - a + 0.05, St["horns"]), a + 0.01, pan=0.25, send=0.45)
            if St["drums"] == "taiko":
                bus.add(horn(mi - 12, e - a + 0.05, St["horns"] * 0.7), a + 0.01, pan=0.3, send=0.45)
        if St["cel_mel"] and sec in ("climax", "end"):
            bus.add(celesta(mi + 24, St["cel_mel"]), a + 0.02, pan=0.3, send=0.5)
    # ---------- гармония: бас
    segs = []
    for b, (ch, mel, sec, br) in enumerate(P):
        for c, x, d in split(ch):
            segs.append([bt(b, x), bt(b, x + d), c, sec, b, x])
    segs[-1][1] = end_t
    bv = {0: 0.19, 1: 0.21, 2: 0.27, 3: 0.20}
    if St["pad"] == "synth":
        for a, e, c, sec, b, x in segs:
            p = Hc[c][0]
            bus.add(sub(p + (12 if p < 36 else 0), e - a, bv[LV[sec]] * 1.1), a, pan=0.0, send=0.05)
    elif St["pad"] == "organ":
        for a, e, c, sec, b, x in segs:
            bus.add(organ(Hc[c][0] + 12, e - a + 0.1, bv[LV[sec]] * 0.55, stops=("16", "8"), rel=0.6), a, pan=0.0, send=0.5)
    else:
        bl = [(a, e, Hc[c][0] + 12, bv[LV[sec]]) for a, e, c, sec, b, x in segs]
        sig, ts = legato_line(bl, voices=5, att=0.9, rel=2.5, bright=0.42, vib=0.003, glide=0.05, noise=0)
        bus.add(sig, ts, pan=0.25, send=0.3)
        deep = 1.0 if St["drums"] == "taiko" else 0.8
        bl2 = [(a, e, mi - 12, v * deep) for (a, e, mi, v), sg in zip(bl, segs) if sg[3] in ("climax", "end") and mi - 12 >= 31]
        if bl2 and St["drums"]:
            sig, ts = legato_line(bl2, voices=4, att=0.8, rel=2.5, bright=0.4, vib=0.002, glide=0.05, noise=0)
            bus.add(sig, ts, pan=0.2, send=0.25)
    # ---------- гармония: три голоса подложки с голосоведением
    voicing = [t4 - 8, t4 - 5, t4]
    lines = [[], [], []]
    for a, e, c, sec, b, x in segs:
        voicing = vlead(voicing, {p % 12 for p in Hc[c][1]}, m("E3"), m("D5"))
        for k in range(3):
            lines[k].append((a, e, voicing[k], St["pv"][LV[sec]]))
    for k in range(3):
        if St["pad"] == "str":
            sig, ts = legato_line(lines[k], voices=5, att=1.3, rel=2.5, bright=0.32, vib=0.004, glide=0.07, noise=0)
            bus.add(sig, ts + 0.04 * k, pan=-0.35 + 0.3 * k, send=0.34)
        elif St["pad"] == "organ":
            for (a, e, mi, v), sg in zip(lines[k], segs):
                stops = ("8", "fl", "4") if sg[3] in ("climax", "end") else ("8", "fl")
                bus.add(organ(mi, e - a + 0.1, v * 1.5, stops=stops, rel=0.7), a, pan=-0.3 + 0.3 * k, send=0.6)
        else:
            for a, e, mi, v in lines[k]:
                bus.add(spad(mi, e - a, v * 1.3), a - 0.1, pan=-0.4 + 0.4 * k, send=0.4)
                if k == 2:
                    bus.add(spad(mi + 12, e - a, v * 0.5), a - 0.1, pan=0.3, send=0.45)
    if St["pad"] == "str":
        sig, ts = legato_line([(bt(fin_b), end_t, t4 + 2, 0.06)], voices=5, att=1.5, rel=2.5, bright=0.35, vib=0.004, noise=0)
        bus.add(sig, ts, pan=-0.2, send=0.5)
    if St["drone"]:                                       # тихая квинта на весь трек — «воздух» простора
        sig, ts = legato_line([(bt(0), end_t, t4 - 17, St["drone"])], voices=4, att=2.0, rel=3.0, bright=0.35, vib=0.002, noise=0)
        bus.add(sig, ts, pan=0.0, send=0.4)
    # ---------- перебор восьмыми
    for a, e, c, sec, b, x in segs:
        if sec == "end":
            continue
        bass, tones = Hc[c]
        nst = int(round((e - a) / (BEAT / 2)))
        off = int(round(x * 2))
        arp = St["intro_arp"] if sec == "intro" else St["arp"]
        pcs = [t % 12 for t in tones]
        if arp == "piano":
            r_ = bass + 12
            while r_ < 50:
                r_ += 12
            u = sorted({t for t in range(60 + min(0, tr), 84 + min(0, tr)) if t % 12 in pcs})
            pat = [r_, u[0], u[1], u[2], u[3], u[2], u[1], u[0]] if bpb == 4 else [r_, u[0], u[1], u[2], u[1], u[0]]
            vel = 0.15 if sec == "intro" else 0.12 if sec == "verse" else 0.14
            for j in range(nst):
                jj = (j + off) % L8
                acc = 1.0 if jj == 0 else 0.85 if jj == bpb else 0.68
                bus.add(piano(pat[jj], BEAT * 1.2, vel * acc), a + j * BEAT / 2 + rng.uniform(0, 0.006), pan=-0.2 + 0.06 * (jj % 4), send=0.32)
        elif arp in ("harp", "harp_soft"):
            md = [t + 12 for t in tones]
            pat = ([md[0], md[1], md[2], md[0] + 12, md[1] + 12, md[2], md[1], md[0] + 12] if bpb == 4
                   else [md[0], md[1], md[2], md[0] + 12, md[2], md[1]])
            v = (0.085 if sec != "climax" else 0.10) * (0.7 if arp == "harp_soft" else 1.0)
            for j in range(nst):
                jj = (j + off) % L8
                bus.add(harp(pat[jj], v * (1.0 if jj % bpb == 0 else 0.75)), a + j * BEAT / 2 + rng.uniform(0, 0.008),
                        pan=-0.45 + 0.08 * (jj % 4), send=0.35)
        elif arp == "celesta":
            u = sorted({t for t in range(72, 98) if t % 12 in pcs})
            pat = [u[0], u[2], u[1], u[3], u[2], u[4], u[3], u[1]] if bpb == 4 else [u[0], u[2], u[1], u[3], u[2], u[1]]
            v = 0.05 if sec == "intro" else 0.042 if sec == "verse" else 0.05
            for j in range(nst):
                jj = (j + off) % L8
                bus.add(celesta(pat[jj], v * (1.0 if jj % bpb == 0 else 0.7)), a + j * BEAT / 2 + rng.uniform(0, 0.006),
                        pan=-0.3 + 0.15 * (jj % 4), send=0.45)
            if x == 0:
                bus.add(harp(bass + 12, 0.10), a, pan=0.1, send=0.35)
        elif arp == "pluck":
            md = [t + 12 for t in tones]
            pat = ([md[0], md[2], md[1] + 12, md[2], md[0] + 12, md[2], md[1] + 12, md[2]] if bpb == 4
                   else [md[0], md[2], md[1] + 12, md[2], md[0] + 12, md[2]])
            v = 0.07 if sec == "intro" else 0.06 if sec == "verse" else 0.075
            for j in range(nst):
                jj = (j + off) % L8
                tt = a + j * BEAT / 2
                vv = v * (1.0 if jj % bpb == 0 else 0.75)
                bus.add(pluck(pat[jj], vv), tt, pan=-0.35, send=0.3)
                bus.add(pluck(pat[jj], vv * 0.33), tt + 0.75 * BEAT, pan=0.4, send=0.4)
                bus.add(pluck(pat[jj], vv * 0.14), tt + 1.5 * BEAT, pan=-0.1, send=0.5)
    # ---------- отрывистые струнные
    for a, e, c, sec, b, x in segs:
        if not St["spic"] or sec in ("intro", "end") or (St["spic"] == 1 and sec != "climax"):
            continue
        r_ = Hc[c][0] + 12
        for j in range(int(round((e - a) / (BEAT / 2)))):
            bus.add(short(r_ if j % 2 == 0 else r_ + 7, 0.12 * (1.0 if j % 2 == 0 else 0.7)), a + j * BEAT / 2, pan=0.35, send=0.22)
    # ---------- хор
    if St["choir"]:
        ch = [(a, e, Hc[c][1][2] + 12, 0.24) for a, e, c, sec, b, x in segs if sec == "climax"]
        if ch:
            sig, ts = cline(ch, "choir", voices=10, att=1.2, rel=2.0, vowel=VOWEL_U if St["choir_v"] == "u" else VOWEL_A)
            bus.add(sig, ts, pan=0.0, send=0.55, gain=St["choir"])
    # ---------- колокол: начало раздела, середина раздела, финал
    if St["bells"]:
        k_in = 0
        for b in range(nb):
            k_in = 0 if (b == 0 or secs[b] != secs[b - 1]) else k_in + 1
            if secs[b] == "intro":
                continue
            if k_in % 4 == 0:
                c0 = split(P[b][0])[0][0]
                pcs0 = {Hc[c0][0] % 12} | {x % 12 for x in Hc[c0][1]}
                p = t4 if (t4 % 12 in pcs0 or secs[b] == "end") else t4 + 7      # тоника лада, а над доминантой — квинта
                if p < 62:
                    p += 12
                bus.add(bell_major(p, 0.16 if secs[b] != "verse" else 0.11), bt(b), pan=0.15, send=0.6)
    # ---------- ударные
    for b, (ch, mel, sec, br) in enumerate(P):
        if sec == "end":
            break
        k = LV[sec]
        D = St["drums"]
        if D in ("frame", "taiko"):
            v = (0.10, 0.115, 0.19)[k]
            bus.add(fdrum(v), bt(b, 0), pan=0.0, send=0.25)
            if bpb == 4:
                bus.add(fdrum(v * 0.6), bt(b, 1.5), pan=0.0, send=0.25)
                bus.add(fdrum(v * 0.5, low=False), bt(b, 2.5), pan=0.15, send=0.25)
                if sec == "climax":
                    bus.add(fdrum(v * 0.75), bt(b, 2), pan=0.0, send=0.25)
                    bus.add(fdrum(v * 0.35, low=False), bt(b, 3.5), pan=-0.15, send=0.25)
                    if D == "taiko":
                        for x_, tv in ((0, 0.30), (0.75, 0.16), (1.5, 0.2), (2, 0.26), (3, 0.2), (3.5, 0.14)):
                            bus.add(taiko(tv), bt(b, x_), pan=0.0, send=0.35)
                elif D == "taiko" and sec == "verse":
                    bus.add(taiko(0.14), bt(b, 0), pan=0.0, send=0.35)
                    bus.add(taiko(0.10), bt(b, 2), pan=0.0, send=0.35)
            else:
                bus.add(fdrum(v * 0.45, low=False), bt(b, 2), pan=0.15, send=0.25)
                if sec == "climax":
                    bus.add(fdrum(v * 0.4, low=False), bt(b, 1), pan=-0.15, send=0.25)
        elif D == "kick":
            if bpb == 4:
                if sec == "verse":
                    bus.add(kick(0.22), bt(b, 0), pan=0.0, send=0.05)
                    bus.add(kick(0.13), bt(b, 2.5), pan=0.0, send=0.05)
                elif sec == "climax":
                    for x_ in (0, 1, 2, 3):
                        bus.add(kick(0.26 if x_ in (0, 2) else 0.2), bt(b, x_), pan=0.0, send=0.05)
                    bus.add(fdrum(0.10, low=False), bt(b, 1), pan=0.2, send=0.3)
                    bus.add(fdrum(0.10, low=False), bt(b, 3), pan=0.2, send=0.3)
            elif sec != "intro":
                bus.add(kick(0.2 if sec == "verse" else 0.25), bt(b, 0), pan=0.0, send=0.05)
                if sec == "climax":
                    bus.add(fdrum(0.09, low=False), bt(b, 2), pan=0.2, send=0.3)
    # ---------- подводки, литавры (по басу аккорда), финал
    D = St["drums"]
    big = D in ("frame", "taiko", "kick", "timp")
    root_of = lambda b, last=False: Hc[split(P[b][0])[-1 if last else 0][0]][0]  # noqa: E731
    for b in range(1, nb):
        if secs[b] == "climax" and secs[b - 1] != "climax":
            if big:
                bus.add(shimmer(BAR * 0.95, 0.10, t4), bt(b - 1) + BAR * 0.05, pan=0.0, send=0.4)
            if D in ("frame", "taiko", "timp"):
                for k in range(12):
                    bus.add(timp(tfit(root_of(b - 1, True)), 0.02 + 0.05 * k / 11, 0.6), bt(b - 1, bpb - 2) + k * BEAT * 2 / 12, pan=0.0, send=0.4)
            bus.add(timp(tfit(root_of(b)), 0.15 if big else 0.07, 4.0), bt(b), pan=0.0, send=0.4)
    cb = [b for b in range(nb) if secs[b] == "climax"]
    if len(cb) >= 5 and big:
        bus.add(timp(tfit(root_of(cb[4])), 0.13, 4.0), bt(cb[4]), pan=0.0, send=0.4)
    if big and secs[-2] == "climax":
        bus.add(shimmer(BAR * 0.95, 0.08, t4), bt(fin_b - 1) + BAR * 0.05, pan=0.0, send=0.4)
    bus.add(timp(tfit(Hc[split(P[fin_b][0])[0][0]][0]), 0.12 if big else 0.06, 4.5), bt(fin_b), pan=0.0, send=0.45)
    if D in ("frame", "taiko"):
        bus.add(fdrum(0.15), bt(fin_b), pan=0.0, send=0.35)
    if D == "kick":
        bus.add(kick(0.24), bt(fin_b), pan=0.0, send=0.1)
    for k, d in enumerate((0, 7, 14, 16, 19, 24)):
        tt = bt(fin_b, 0.5 * k + 0.5)
        if St["fin"] == "celesta":
            bus.add(celesta(t4 + d + 12, 0.06 - 0.004 * k), tt, pan=0.15, send=0.55)
        elif St["fin"] == "pluck":
            bus.add(pluck(t4 + d, 0.09 - 0.008 * k), tt, pan=0.15, send=0.55)
        else:
            bus.add(piano(t4 + d, 4.0, 0.15 - 0.012 * k), tt, pan=0.15, send=0.55)
    for k, d in enumerate((31, 28, 24)):
        bus.add(celesta(t4 + d, 0.05), bt(fin_b, bpb + 0.2 + k * 0.5), pan=-0.2, send=0.6)
    return bus, end_t


def nn(p):
    return f"{NAMES[p % 12]}{p // 12 - 1}"


def check(name):
    """диапазон голоса и ноты, которые спорят с аккордом (полутон НАД звуком аккорда — резко; долгие неаккордовые — мягко)"""
    song = SONGS[name]
    tr, bpb, Hc, t4, scale, split = prep(song)
    lo, hi, n = 200, 0, 0
    BAR = bpb * 60 / song["bpm"]
    print(f"== {name}: «{song['title']}», тоника {NAMES[t4 % 12]}, {song['bpm']} уд/мин, размер {bpb}/4, тактов {len(song['bars'])}, "
          f"длина ≈ {(len(song['bars']) - 1 + song.get('hold', 1.2)) * BAR + 4.8:.0f} с")
    for b, (ch, mel, sec, br) in enumerate(song["bars"]):
        used = sum(d for _, d, _, _ in (mel or []))
        if mel and abs(used - bpb) > 1e-6 and not (br or sec == "end"):
            pass
        for x, d, nt, vw in (mel or []):
            if x + d > bpb + 1e-6:
                print(f"   такт {b}: нота {nt} выходит за такт")
            mi = m(nt) + tr
            lo, hi, n = min(lo, mi), max(hi, mi), n + 1
            c = [c for c, x0, d0 in split(ch) if x0 <= x + 1e-6][-1]
            pcs = {Hc[c][0] % 12} | {p % 12 for p in Hc[c][1]}
            if mi % 12 not in scale:
                print(f"   такт {b} {c}: {nt} вне лада")
            if any((mi - p) % 12 == 1 for p in pcs) and d >= 1:
                print(f"   такт {b} {c}: {nt} ({d} д.) — полутон НАД звуком аккорда, резко")
            elif mi % 12 not in pcs and d >= 2:
                print(f"   такт {b} {c}: {nt} ({d} д.) — долгая неаккордовая (мягкое напряжение)")
    print(f"   нот {n}, диапазон голоса {nn(lo)}–{nn(hi)}")


if __name__ == "__main__":
    import time
    if sys.argv[1] == "check":
        for nm in SONGS:
            check(nm)
        sys.exit()
    name, out = sys.argv[1], sys.argv[2]
    t = time.time()
    bus, end_t = compose(SONGS[name])
    L, R = master(bus, 0.3)
    cut = int((end_t + 4.5) * SR)
    L, R = L[:cut].copy(), R[:cut].copy()
    fo = int(1.5 * SR)
    w = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo))
    L[-fo:] *= w
    R[-fo:] *= w
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.5, R / pk * 0.5
    tmp = out + ".tmp.wav"
    write24(tmp, L, R)
    g = min(10 ** ((-14.0 - lufs(tmp)) / 20), 0.89 / 0.5)
    write24(out, L * g, R * g)
    os.remove(tmp)
    print(out, "готово", round(len(L) / SR, 1), "с; пик", round(20 * math.log10(0.5 * g), 1), "дБFS;", f"{time.time() - t:.0f} с")
