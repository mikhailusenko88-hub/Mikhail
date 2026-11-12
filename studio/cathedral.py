"""Короткие «соборные» отрывки (~20 с): орган и хор, пианино и виолончель, колокола и струнные — под высокими сводами.
python3 cathedral.py"""
import math
import wave

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import fftconvolve

import theme as th
from theme import SR, m, hz, table, play, drift, env_ar, piano, strings, celesta, timp, compressor

rng = np.random.default_rng(77)


def organ(midi, dur, vel, stops=("8", "4"), rel=0.25):
    """Трубный орган: принципал 8', октава 4', флейта, бурдон 16' — постоянный звук, «чифф» на атаке, лёгкие биения между регистрами."""
    f0 = hz(midi)
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    ranks = {"8": (1.0, lambda h, fh: (1.0 if h == 1 else 0.7 if h == 2 else 0.45 / h ** 0.9) * math.exp(-fh / 6000)),
             "4": (2.0, lambda h, fh: (1.0 / h ** 1.4) * math.exp(-fh / 7000)),
             "fl": (1.0, lambda h, fh: (1.0 if h == 1 else 0.12 if h == 3 else 0.02)),
             "16": (0.5, lambda h, fh: (1.0 if h == 1 else 0.25 if h == 3 else 0.06 / h))}
    gains = {"8": 1.0, "4": 0.45, "fl": 0.8, "16": 0.7}
    for st in stops:
        mul, fn = ranks[st]
        tab = table(f0 * mul, fn, fmax=9000)
        det = 2 ** (rng.uniform(-1.5, 1.5) / 1200)
        out += gains[st] * play(tab, np.full(n, f0 * mul * det) * np.exp(drift(n, 0.6)))
    att = np.clip(t / 0.07, 0, 1) ** 1.5
    r = np.clip((dur + rel - t) / rel, 0, 1)
    k = int(0.05 * SR)
    chiff = np.zeros(n)
    nz = rng.normal(0, 1, k)
    chiff[:k] = (gaussian_filter1d(nz, 2) - gaussian_filter1d(nz, 8)) * np.exp(-np.arange(k) / (0.015 * SR)) * 0.25
    return vel * (out / max(1, len(stops)) * att * r + chiff * th.NOISE)


def bell(midi, vel, dur=7.0):
    f0 = hz(midi)
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for r, a, d in ((0.5, 0.35, 0.35), (1.0, 1.0, 0.6), (1.19, 0.45, 0.9), (1.5, 0.35, 1.1), (2.0, 0.4, 1.4), (2.52, 0.25, 2.0), (3.36, 0.15, 2.8), (4.2, 0.08, 3.6)):
        s += a * np.sin(2 * np.pi * f0 * r * t + rng.uniform(0, 6.28)) * np.exp(-t * d)
    return vel * s * np.minimum(1, t / 0.002) / 2.5


VOWEL_A = [(780, 1.0, 120), (1150, 0.55, 140), (2700, 0.25, 260), (3300, 0.15, 300)]
VOWEL_U = [(350, 1.0, 90), (700, 0.35, 120), (2400, 0.10, 250)]


def line(notes, kind="choir", voices=8, att=0.5, rel=1.2, glide=0.06, vib=0.004, bright=1.0, vowel=VOWEL_A):
    """Связная линия (хор или струнные): notes = [(t_start, t_end, midi, vel)] — портаменто, без провалов."""
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
    amp = gaussian_filter1d(amp, 0.08 * CR)
    xa = np.arange(n) / SR * CR
    up = lambda c: np.interp(xa, np.arange(nc), c)
    tt = np.arange(n) / SR + t0
    env = np.clip((tt - notes[0][0] + 0.05) / att, 0, 1) ** 1.4 * np.clip((t1 - tt) / rel, 0, 1) ** 1.2
    sa = up(since)
    mid = float(np.median([x[2] for x in notes]))
    if kind == "choir":
        tab = table(hz(mid), lambda h, fh: (0.05 + sum(a * math.exp(-((fh - c) / w) ** 2) for c, a, w in vowel)) / h ** 0.25, fmax=8000)
        det_c, vib = 12, 0.0035
    else:
        tab = table(hz(mid), lambda h, fh: th.body_string(fh) / h * math.exp(-fh / (6500 * bright)))
        det_c = 7
    out = np.zeros(n)
    for v in range(voices):
        lp = up(gaussian_filter1d(pitch, rng.uniform(0.6, 1.3) * glide * CR))
        lf = (lp - 69) / 12 + rng.uniform(-det_c, det_c) / 1200 + \
            vib * np.clip((sa - rng.uniform(0.2, 0.4)) / 0.5, 0, 1) * np.sin(2 * np.pi * rng.uniform(4.6, 5.8) * tt + rng.uniform(0, 6.28)) / math.log(2) + drift(n, 4) / math.log(2)
        sig = play(tab, 440.0 * 2 ** lf)
        lag = int(rng.uniform(0, 0.04) * SR)
        sig = np.roll(sig, lag)
        sig[:lag] = 0
        kf = min(len(sig) - lag, int(0.006 * SR))   # вход голоса без щелчка
        sig[lag:lag + kf] *= np.linspace(0, 1, kf)
        out += sig
    nz = rng.normal(0, 1, n)
    br = (gaussian_filter1d(nz, 2) - gaussian_filter1d(nz, 10)) * (0.03 if kind == "choir" else 0.015) * th.NOISE
    return up(amp) * env * (out / voices + br), t0


def cathedral_ir(seed, rt_low=5.8, rt_high=2.6, pre=0.055, length=7.5):
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    nz = r.normal(0, 1, n)
    low = gaussian_filter1d(nz, 3.5)
    high = nz - low
    tail = low * 2.4 * np.exp(-t * 6.9 / rt_low) + high * 0.5 * np.exp(-t * 6.9 / rt_high)
    tail *= np.clip((t - pre) / 0.12, 0, 1)
    er = np.zeros(n)
    for d in (0.031, 0.047, 0.063, 0.081, 0.097, 0.121, 0.143, 0.171):
        er[int((d + r.uniform(-0.004, 0.004)) * SR)] += r.uniform(0.15, 0.35) * r.choice([-1, 1])
    ir = tail + er * 2.5
    return ir / np.sqrt(np.sum(ir ** 2))


def mixdown(bus, wet=0.75, name="out.wav", cut=0.18, air_k=0.5):
    irL, irR = cathedral_ir(5), cathedral_ir(9)
    wL = fftconvolve(bus.sL + 0.4 * bus.sR, irL)[:len(bus.L)]
    wR = fftconvolve(bus.sR + 0.4 * bus.sL, irR)[:len(bus.R)]
    L, R = bus.L + wet * wL, bus.R + wet * wR
    out = []
    for ch in (L, R):
        ch = ch - gaussian_filter1d(ch, SR / (2 * math.pi * 32))
        band = gaussian_filter1d(ch, SR / (2 * math.pi * 400)) - gaussian_filter1d(ch, SR / (2 * math.pi * 150))
        ch = ch - cut * band
        air = ch - gaussian_filter1d(ch, SR / (2 * math.pi * 5000))
        out.append(ch + air_k * air)
    L, R = out
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = compressor(L / pk, R / pk, thr_db=-16, ratio=1.7)
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk, R / pk
    L, R = np.tanh(L * 1.1) / math.tanh(1.1), np.tanh(R * 1.1) / math.tanh(1.1)
    f = int(2.5 * SR)
    for ch in (L, R):
        ch[-f:] *= np.linspace(1, 0, f) ** 1.6
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.89, R / pk * 0.89
    st = np.empty(2 * len(L))
    st[0::2], st[1::2] = L, R
    with wave.open(name, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype(np.int16).tobytes())
    print("готово", name, round(len(L) / SR, 1), "с")


def new_bus(total):
    th.TOTAL = total
    return th.Bus()


# ============================================================== 1. Орган и хор (фа мажор, 60 уд/мин)
def piece_organ():
    BEAT = 1.0
    BAR = 4 * BEAT
    T0 = 0.6
    bt = lambda b, x=0.0: T0 + b * BAR + x * BEAT
    bus = new_bus(T0 + 5 * BAR + 8)
    harm = [(0, ["F2", "C3", "F3", "A3", "C4"]), (1, ["E2", "C3", "E3", "G3", "C4"]), (2, ["D2", "A2", "D3", "F3", "A3"]),
            (3, ["Bb1", "F2", "D3", "F3", "Bb3"]), (3.5, ["C2", "G2", "C3", "E3", "G3"]), (4, ["F2", "C3", "F3", "A3", "C4"])]
    for i, (b, notes) in enumerate(harm):
        t_s = bt(int(b), (b % 1) * 4)
        t_e = bt(int(harm[i + 1][0]), (harm[i + 1][0] % 1) * 4) if i + 1 < len(harm) else bt(4, 4) + 2.5
        for k, nt in enumerate(notes):
            stops = ("16", "8") if k == 0 else ("8", "fl", "4") if k >= 3 else ("8", "fl")
            v = 0.10 if k == 0 else 0.10
            bus.add(organ(m(nt), t_e - t_s + 0.05, v, stops), t_s, pan=-0.3 + 0.15 * k, send=0.7)
    mel = [(0, 0, 1, "A4"), (0, 1, 1, "C5"), (0, 2, 2, "F5"), (1, 0, 1, "E5"), (1, 1, 1, "D5"), (1, 2, 2, "C5"),
           (2, 0, 1, "D5"), (2, 1, 1, "C5"), (2, 2, 1, "A4"), (2, 3, 1, "F4"), (3, 0, 2, "G4"), (3, 2, 1, "A4"), (3, 3, 1, "G4"), (4, 0, 4, "A4")]
    notes = [(bt(b, x) - 0.05, bt(b, x + d) + (1.5 if b == 4 else 0), m(nt), 0.55) for b, x, d, nt in mel]
    sig, ts = line(notes, "choir", voices=10, att=0.6, rel=2.0)
    bus.add(sig, ts, pan=0.0, send=0.75, gain=0.9)
    # альты хора — тянут терции под мелодией, «у»
    alto = [(bt(0) - 0.05, bt(1), m("F4"), .3), (bt(1), bt(2), m("E4"), .3), (bt(2), bt(3), m("D4"), .3), (bt(3), bt(3, 2), m("D4"), .3),
            (bt(3, 2), bt(4), m("E4"), .3), (bt(4), bt(4, 4) + 1.5, m("F4"), .3)]
    sig, ts = line(alto, "choir", voices=8, att=1.0, rel=2.0, vowel=VOWEL_U)
    bus.add(sig, ts, pan=-0.25, send=0.75, gain=0.7)
    bus.add(bell(m("F4"), 0.22), bt(0), pan=0.35, send=0.8)
    bus.add(bell(m("C5"), 0.12), bt(0, 2), pan=0.4, send=0.8)
    bus.add(bell(m("F4"), 0.2), bt(4), pan=0.35, send=0.8)
    bus.add(bell(m("A4"), 0.12), bt(4, 1.5), pan=0.4, send=0.8)
    mixdown(bus, wet=0.85, name="ex1_organ_choir.wav", cut=0.22, air_k=0.7)


# ============================================================== 2. Пианино и виолончель под сводами (ля минор, 66 уд/мин)
def piece_piano_cello():
    BEAT = 60 / 66
    BAR = 4 * BEAT
    T0 = 0.3
    bt = lambda b, x=0.0: T0 + b * BAR + x * BEAT
    bus = new_bus(T0 + 6 * BAR + 7)
    prog = [("A2", ["A3", "C4", "E4"]), ("F2", ["F3", "A3", "C4"]), ("C3", ["G3", "C4", "E4"]), ("G2", ["G3", "B3", "D4"]),
            ("A2", ["A3", "C4", "E4"]), ("F2", ["F3", "A3", "C4"])]
    for b, (bass, tones) in enumerate(prog):
        mids = [m(x) for x in tones]
        pat = [m(bass), mids[0], mids[1], mids[2], mids[1] + 12, mids[2], mids[1], mids[0]]
        for j, nt in enumerate(pat):
            held = BAR - j * BEAT / 2 + (2.5 if b == 5 else 0)
            v = (0.42 if j == 0 else 0.30) * (0.9 if b < 5 else 0.75)
            bus.add(piano(nt, held, v), bt(b, j / 2) + rng.uniform(0, 0.01), pan=float(np.clip((nt - 60) / 40, -0.4, 0.4)), send=0.5)
    cello = [(0, 0, 2, "E4"), (0, 2, 1, "C4"), (0, 3, 1, "B3"), (1, 0, 2, "A3"), (1, 2, 1, "C4"), (1, 3, 1, "F4"),
             (2, 0, 1.5, "E4"), (2, 1.5, .5, "D4"), (2, 2, 1, "C4"), (2, 3, 1, "G3"), (3, 0, 2, "B3"), (3, 2, 2, "D4"),
             (4, 0, 2, "C4"), (4, 2, 1, "B3"), (4, 3, 1, "A3"), (5, 0, 4, "A3")]
    notes = [(bt(b, x) - 0.03, bt(b, x + d) + (2.0 if b == 5 else 0), m(nt), 0.75) for b, x, d, nt in cello]
    sig, ts = line(notes, "strings", voices=3, att=0.35, rel=1.5, glide=0.05, vib=0.006, bright=0.9)
    bus.add(sig, ts, pan=0.25, send=0.55, gain=1.0)
    # тихие высокие струнные-флажолеты с 3-го такта
    pad = [(bt(2), bt(3), m("E5"), .12), (bt(3), bt(4), m("D5"), .12), (bt(4), bt(5), m("E5"), .14), (bt(5), bt(6) + 2, m("C5"), .12)]
    sig, ts = line(pad, "strings", voices=6, att=1.5, rel=2.5, glide=0.1, vib=0.003, bright=1.3)
    bus.add(sig, ts, pan=-0.35, send=0.8)
    mixdown(bus, wet=0.6, name="ex2_piano_cello.wav", cut=0.32, air_k=1.0)


# ============================================================== 3. Колокола и струнные (ре мажор, 56 уд/мин)
def piece_bells_strings():
    BEAT = 60 / 56
    BAR = 4 * BEAT
    T0 = 0.4
    bt = lambda b, x=0.0: T0 + b * BAR + x * BEAT
    bus = new_bus(T0 + 5 * BAR + 8)
    prog = [("D2", ["F#3", "A3", "D4"]), ("B1", ["F#3", "B3", "D4"]), ("G1", ["G3", "B3", "D4"]), ("A1", ["E3", "A3", "C#4"]), ("D2", ["F#3", "A3", "D4"])]
    # струнные: бас и три голоса — связно
    bass = [(bt(b), bt(b + 1) + (3 if b == 4 else 0), m(bs) + 12, 0.45) for b, (bs, _) in enumerate(prog)]
    sig, ts = line(bass, "strings", voices=5, att=1.0, rel=2.0, glide=0.08, vib=0.003, bright=0.8)
    bus.add(sig, ts, pan=0.3, send=0.6)
    for k in range(3):
        vl = [(bt(b), bt(b + 1) + (3 if b == 4 else 0), m(tones[k]), 0.26) for b, (_, tones) in enumerate(prog)]
        sig, ts = line(vl, "strings", voices=5, att=1.4, rel=2.5, glide=0.1, vib=0.0035, bright=1.0)
        bus.add(sig, ts + 0.03 * k, pan=-0.2 + 0.15 * k, send=0.65)
    # мелодия колоколами и челестой — медленно, как перезвон
    mel = [(0, 0, "A5"), (0, 1.5, "F#5"), (0, 3, "D5"), (1, 0, "F#5"), (1, 1.5, "B5"), (1, 3, "A5"), (2, 0, "G5"), (2, 1.5, "B5"), (2, 3, "D6"),
           (3, 0, "C#6"), (3, 1.5, "A5"), (3, 3, "E5"), (4, 0, "D5")]
    for b, x, nt in mel:
        bus.add(bell(m(nt) - 12, 0.16), bt(b, x), pan=float(np.clip((m(nt) - 76) / 20, -0.4, 0.4)), send=0.75)
        bus.add(celesta(m(nt), 0.10), bt(b, x) + 0.01, pan=0.2, send=0.7)
    bus.add(bell(m("D3"), 0.25, dur=8), bt(0), pan=0.0, send=0.85)
    bus.add(bell(m("D3"), 0.25, dur=8), bt(4), pan=0.0, send=0.85)
    bus.add(timp(m("D2"), 0.05, 4.0), bt(4), pan=0.0, send=0.6)
    mixdown(bus, wet=0.8, name="ex3_bells_strings.wav", cut=0.32, air_k=1.0)


if __name__ == "__main__":
    piece_organ()
    piece_piano_cello()
    piece_bells_strings()


# ============================================================== 4. Органное остинато (ля минор, 90 уд/мин) — в духе «космического» органа из соборных роликов
def piece_organ_ostinato():
    BEAT = 60 / 90
    BAR = 4 * BEAT
    T0 = 0.3
    bt = lambda b, x=0.0: T0 + b * BAR + x * BEAT
    nb = 10
    bus = new_bus(T0 + nb * BAR + 8)
    prog = [("A", ["A3", "C4", "E4"]), ("A", ["A3", "C4", "E4"]), ("F", ["F3", "A3", "C4"]), ("C", ["G3", "C4", "E4"]), ("G", ["G3", "B3", "D4"]),
            ("A", ["A3", "C4", "E4"]), ("F", ["F3", "A3", "C4"]), ("D", ["F3", "A3", "D4"]), ("E", ["G#3", "B3", "E4"]), ("A", ["A3", "C4", "E4"])]
    bassn = {"A": "A1", "F": "F1", "C": "C2", "G": "G1", "D": "D2", "E": "E2"}
    for b, (root, tones) in enumerate(prog):
        mids = [m(x) for x in tones]
        fig = [mids[0], mids[2], mids[1] + 12, mids[2], mids[0] + 12, mids[2], mids[1] + 12, mids[2]]
        last = b == nb - 1
        for j, nt in enumerate(fig if not last else fig[:1]):
            dur = BEAT / 2 * 0.92 if not last else 5.0
            stops = ("fl",) if b < 2 else ("fl", "8") if b < 4 else ("fl", "8", "4")
            v = 0.07 + 0.012 * min(b, 7)
            bus.add(organ(nt, dur, v, stops, rel=0.12), bt(b, j / 2), pan=float(np.clip((nt - 64) / 30, -0.4, 0.4)), send=0.7)
        if b >= 2:
            # левая рука: тянущийся аккорд
            for k, nt in enumerate(mids[:2]):
                bus.add(organ(nt - 12, BAR + (5 if last else 0.02), 0.06 + 0.01 * min(b, 7), ("8", "fl")), bt(b), pan=-0.2 + 0.2 * k, send=0.7)
        if b >= 4:
            # педаль 16'
            bus.add(organ(m(bassn[root]) + 12, BAR + (5 if last else 0.02), 0.11 if b < 7 else 0.14, ("16", "8")), bt(b), pan=0.0, send=0.6)
        if b >= 6:
            ch = [(bt(b), bt(b + 1) + (4 if last else 0), mids[2] + 12, 0.35)]
            sig, ts = line(ch, "choir", voices=10, att=0.8, rel=2.5)
            bus.add(sig, ts, pan=0.0, send=0.8, gain=0.7)
    # редкая мелодия фортепиано поверх
    mel = [(2, 0, "A4"), (3, 0, "C5"), (3, 2, "B4"), (4, 0, "E5"), (5, 0, "D5"), (5, 1, "C5"), (5, 2, "B4"), (6, 0, "C5"), (7, 0, "D5"), (7, 2, "F5"),
           (8, 0, "E5"), (8, 2, "G#4"), (9, 0, "A4")]
    for b, x, nt in mel:
        bus.add(piano(m(nt), 3.0 if b < 9 else 6.0, 0.55), bt(b, x), pan=0.1, send=0.55, gain=1.1)
    bus.add(bell(m("A3"), 0.2, dur=8), bt(9), pan=0.0, send=0.85)
    bus.add(timp(m("A2"), 0.06, 4.0), bt(9), pan=0.0, send=0.6)
    mixdown(bus, wet=0.8, name="ex4_organ_ostinato.wav", cut=0.25, air_k=0.8)
