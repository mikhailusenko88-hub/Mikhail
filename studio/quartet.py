"""Струнный квартет играет поп-мелодию — в характере каверов Duomo/«Бриджертонов». Мелодия и гармония свои.
Соль мажор (ми минор), 70 уд/мин (поп 140 в половинном). python3 quartet.py"""
import math
import wave

import numpy as np

import theme as th
from theme import SR, m, hz, strings, legato_line, master

rng = np.random.default_rng(31)
BEAT = 60 / 70
BAR = 4 * BEAT
T0 = 0.25


def bt(b, x=0.0):
    return T0 + b * BAR + x * BEAT


def pizz(midi, vel):
    f0 = hz(midi)
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for h in range(1, 12):
        fh = f0 * h
        if fh > 9000:
            break
        body = 1 + 0.8 * math.exp(-((fh - 300) / 120) ** 2) + 0.5 * math.exp(-((fh - 1000) / 400) ** 2)
        s += body / h ** 1.3 * np.sin(2 * np.pi * fh * t + rng.uniform(0, 6.28)) * np.exp(-t * (2.2 + 1.6 * h) * (f0 / 200) ** 0.25)
    thump = np.exp(-t / 0.01) * np.sin(2 * np.pi * 110 * t) * 0.3
    return vel * (s / 2.0 + thump) * np.minimum(1, t / 0.002)


def short(midi, vel, dur=0.16):
    """спиккато / отрывистый штрих"""
    return strings(midi, dur, vel, voices=2, att=0.012, rel=0.09, bright=1.25, vib=0.0)


HARM = [("E2", ["E3", "G3", "B3"]), ("C2", ["E3", "G3", "C4"]), ("G1", ["D3", "G3", "B3"]), ("D2", ["D3", "F#3", "A3"])]


def compose():
    nb = 7
    th.TOTAL = T0 + nb * BAR + 5
    bus = th.Bus()
    # -------------------------------------------------- виолончель: щипки во вступлении, потом пульс восьмыми смычком
    for b in range(nb):
        bass, tones = HARM[b % 4]
        bm = m(bass) + 12
        if b < 2:
            for x, v in ((0, .5), (1.5, .35), (2.5, .4), (3.5, .3)):
                bus.add(pizz(bm, v), bt(b, x), pan=0.35, send=0.25)
        elif b < 6:
            for j in range(8):
                acc = 1.0 if j in (0, 3, 6) else 0.6
                bus.add(strings(bm, BEAT / 2 * 0.85, 0.30 * acc, voices=2, att=0.02, rel=0.10, bright=0.9, vib=0.0), bt(b, j / 2), pan=0.35, send=0.25)
        else:
            bus.add(strings(bm, BAR + 1.5, 0.30, voices=2, att=0.1, rel=1.2, bright=0.9, vib=0.004), bt(b), pan=0.35, send=0.3)
            bus.add(pizz(bm - 12, 0.45), bt(b, 0), pan=0.35, send=0.3)
    # -------------------------------------------------- вторая скрипка: отрывистые шестнадцатые по звукам аккорда (с 1-го такта)
    for b in range(1, 6):
        bass, tones = HARM[b % 4]
        mids = [m(x) + 12 for x in tones]
        pat = [mids[2], mids[1], mids[2], mids[0]] * 4
        for j, nt in enumerate(pat):
            acc = 1.0 if j % 4 == 0 else 0.55
            v = (0.10 if b < 2 else 0.14) * acc
            bus.add(short(nt, v, dur=BEAT / 4 * 0.6), bt(b, j / 4), pan=-0.15, send=0.22)
    # -------------------------------------------------- альт: тянет середину аккорда связно
    va = [(bt(b) - 0.02, bt(b + 1) if b < nb - 1 else bt(b) + BAR + 1.5, m(HARM[b % 4][1][1]) + (12 if b >= 2 else 0), 0.16 if b >= 2 else 0.12) for b in range(nb)]
    sig, ts = legato_line(va, voices=2, att=0.6, rel=1.4, bright=1.0, vib=0.004, glide=0.05, noise=0.5)
    bus.add(sig, ts, pan=0.12, send=0.3)
    # -------------------------------------------------- первая скрипка: певучая мелодия (с синкопами, как в поп-кавере)
    mel = [(2, 0.5, .5, "E5"), (2, 1, .5, "G5"), (2, 1.5, 1, "B5"), (2, 2.5, .5, "A5"), (2, 3, 1, "G5"),
           (3, 0, 1.5, "E5"), (3, 1.5, .5, "D5"), (3, 2, 1, "E5"), (3, 3, 1, "G5"),
           (4, 0.5, .5, "D5"), (4, 1, .5, "G5"), (4, 1.5, 1, "B5"), (4, 2.5, .5, "A5"), (4, 3, .5, "G5"), (4, 3.5, .5, "A5"),
           (5, 0, 2, "F#5"), (5, 2, 1, "E5"), (5, 3, 1, "D5"),
           (6, 0, 4, "E5")]
    notes = [(bt(b, x) - 0.02, bt(b, x + d) + (1.2 if b == 6 else 0), m(nt), 0.62 if b < 6 else 0.5) for b, x, d, nt in mel]
    sig, ts = legato_line(notes, voices=2, att=0.12, rel=1.6, bright=1.35, vib=0.0065, glide=0.028, noise=0.9)
    bus.add(sig, ts, pan=-0.35, send=0.3, haas=0.003)
    # -------------------------------------------------- лёгкий щипок-«колокольчик» на начало мелодии и в конце
    for b, x, nt in ((2, 0, "B5"), (4, 0, "D6"), (6, 0, "E6"), (6, 1, "B5")):
        bus.add(pizz(m(nt), 0.18), bt(b, x), pan=-0.2, send=0.35)
    return bus


if __name__ == "__main__":
    bus = compose()
    L, R = master(bus)
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.89, R / pk * 0.89
    st = np.empty(2 * len(L))
    st[0::2], st[1::2] = L, R
    with wave.open("ex6_quartet_pop.wav", "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype(np.int16).tobytes())
    print("готово", round(len(L) / SR, 1), "с")
