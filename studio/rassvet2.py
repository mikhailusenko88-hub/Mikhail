"""«Рассвет-2» (светлее по слуху): 84 уд/мин, фортепиано перебором весь трек, струнные тише, без хора;
«Рассвет» — светлая версия в духе «Now We Are Free»: фа мажор, 76 уд/мин, мелодия идёт вверх,
без всхлипов. Два варианта ведущего голоса:
  A — без голоса: в куплете поёт виолончель, в кульминации скрипки октавой выше + валторны;
  B — низкий женский голос (контральто, как у Лизы Джеррард) без подъездов и дрожи.
python3 rassvet.py A|B"""
import math
import sys
import wave

import numpy as np
from scipy.ndimage import gaussian_filter1d

import theme as th
from theme import SR, m, legato_line, voice_lead, horn, timp, master, piano, harp, celesta, cymbal_swell
from cathedral import line as cline, VOWEL_A
from quartet import short
from svoboda import VOW, frame_drum, shaker

rng = np.random.default_rng(76)
BEAT = 60 / 84
BAR = 4 * BEAT
T0 = 0.3
NB = 20


def bt(b, x=0.0):
    return T0 + b * BAR + x * BEAT


# ---------------------------------------------------------------- голос: контральто, чистое ведение
def voice(notes, vowels, vib=0.0055, vib_rate=5.0, vib_delay=0.45, glide=0.022, scoop=0.0, breath=0.02):
    CR = 500
    t0 = notes[0][0] - 0.1
    t1 = notes[-1][1] + 1.2
    n = int((t1 - t0) * SR)
    nc = int((t1 - t0) * CR) + 2
    pitch = np.full(nc, float(notes[0][2]))
    amp = np.zeros(nc)
    since = np.zeros(nc)
    vix = np.zeros(nc, dtype=int)
    names = list(VOW)
    for i, (a, b, mi, v) in enumerate(notes):
        s0 = int((a - t0) * CR)
        s1 = int(((notes[i + 1][0] if i + 1 < len(notes) else b) - t0) * CR)
        pitch[s0:s1] = mi
        amp[s0:s1] = v
        since[s0:s1] = np.arange(s1 - s0) / CR
        vix[s0:s1] = names.index(vowels[i])
    sl = int((notes[-1][1] - t0) * CR)
    pitch[sl:] = notes[-1][2]
    since[sl:] = since[sl - 1] + np.arange(nc - sl) / CR
    lp = gaussian_filter1d(pitch, glide * CR) - scoop * np.exp(-since / 0.06) * (since < 0.3)
    tc = np.arange(nc) / CR + t0
    vibr = vib * np.clip((since - vib_delay) / 0.6, 0, 1) * np.sin(2 * np.pi * vib_rate * tc + 0.2 * np.sin(2 * np.pi * 0.3 * tc))
    f0c = 440.0 * 2 ** ((lp - 69) / 12) * np.exp(vibr)
    amp = gaussian_filter1d(amp, 0.06 * CR)
    env = np.clip((tc - notes[0][0] + 0.1) / 0.3, 0, 1) * np.clip((t1 - tc) / 1.1, 0, 1) ** 1.3
    # нота чуть «расцветает», а не тает: лёгкий подъём громкости к середине долгой ноты
    amp = amp * env * (0.92 + 0.08 * np.clip(since / 0.8, 0, 1))
    W = np.zeros((len(names), nc))
    W[vix, np.arange(nc)] = 1
    W = gaussian_filter1d(W, 0.09 * CR, axis=1)
    W /= W.sum(0, keepdims=True) + 1e-9
    xa = np.arange(n) / SR * CR
    up = lambda c: np.interp(xa, np.arange(nc), c)  # noqa: E731
    ph = 2 * np.pi * np.cumsum(up(f0c)) / SR
    AH = []
    for h in range(1, 31):
        fh = f0c * h
        g = np.zeros(nc)
        for k, nm in enumerate(names):
            g += W[k] * (0.03 + sum(a * np.exp(-((fh - c) / w) ** 2) for c, a, w in VOW[nm]))
        tilt = 1.25 + 0.6 * np.clip((f0c - 500) / 300, 0, 1)
        AH.append(g * (1.0 / h ** tilt) * np.exp(-fh / 6000) * (fh < 8500))
    P = gaussian_filter1d(np.sqrt(sum(a * a for a in AH)) + 1e-9, 0.05 * CR)
    out = np.zeros(n)
    for h, a_h in enumerate(AH, start=1):
        if a_h.any():
            out += up(a_h / P * 0.6) * np.sin(h * ph + 0.5 * h)
    nz = rng.normal(0, 1, n)
    br = gaussian_filter1d(nz, 1.5) - gaussian_filter1d(nz, 5)
    return up(amp) * (out / 2.2 + br * breath), t0


# ---------------------------------------------------------------- партитура
H = {
    "F": ("F2", ["F3", "A3", "C4"]), "Bb/F": ("F2", ["F3", "Bb3", "D4"]), "C/E": ("E2", ["E3", "G3", "C4"]),
    "Dm": ("D2", ["D3", "F3", "A3"]), "Bb": ("Bb1", ["D3", "F3", "Bb3"]), "F/A": ("A1", ["F3", "A3", "C4"]),
    "Gm7": ("G1", ["F3", "Bb3", "D4"]), "Bb/C": ("C2", ["D3", "F3", "Bb3"]), "C": ("C2", ["E3", "G3", "C4"]), "C7": ("C2", ["E3", "Bb3", "C4"]),
}
PROG = ["F", "Bb/F"] + ["F", "C/E", "Dm", "Bb", "F/A", "Bb", "Bb/C", "C7"] * 2 + ["F", "F"]
VERSE = [  # (такт от начала фразы, доля, длительность, нота, гласная)
    (0, 0, 1, "C4", "o"), (0, 1, 1, "F4", "a"), (0, 2, 2, "A4", "o"),
    (1, 0, 1.5, "G4", "a"), (1, 1.5, .5, "A4", "a"), (1, 2, 1, "G4", "o"), (1, 3, 1, "E4", "u"),
    (2, 0, 1, "F4", "o"), (2, 1, 1, "A4", "a"), (2, 2, 2, "D5", "o"),
    (3, 0, 1.5, "D5", "a"), (3, 1.5, .5, "C5", "a"), (3, 2, 2, "Bb4", "o"),
    (4, 0, 1.5, "A4", "o"), (4, 1.5, .5, "Bb4", "a"), (4, 2, 2, "C5", "a"),
    (5, 0, 2, "F5", "o"), (5, 2, 1, "D5", "a"), (5, 3, 1, "Bb4", "o"),
    (6, 0, 1.5, "C5", "a"), (6, 1.5, .5, "Bb4", "a"), (6, 2, 2, "G4", "o"),
    (7, 0, 1, "G4", "a"), (7, 1, .5, "A4", "a"), (7, 1.5, .5, "Bb4", "a"), (7, 2, 2, "C5", "o"),
]
MEL = [(2 + b, x, d, nt, vw) for b, x, d, nt, vw in VERSE] + [(10 + b, x, d, nt, vw) for b, x, d, nt, vw in VERSE] \
    + [(18, 0, 4, "A4", "a")]


def compose(variant):
    th.TOTAL = T0 + NB * BAR + 7
    bus = th.Bus()
    end_t = bt(18, 4) + BAR + 1.5          # финальная нота держится до конца 19-го такта
    lead = []
    for b, x, d, nt, vw in MEL:
        t1 = bt(b, x + d) if b < 18 else end_t
        lead.append((bt(b, x) - 0.02, t1, m(nt), vw, b))
    # ---------- ведущий голос
    if variant == "B":
        notes = [(a, e, mi, 0.50 if b < 10 else 0.60 if b < 18 else 0.52) for a, e, mi, vw, b in lead]
        sig, ts = voice(notes, [vw for *_, vw, b in lead])
        bus.add(sig, ts, pan=0.0, send=0.36, gain=1.25)
        # виолончель тихо подпевает в куплете октавой ниже — опора голосу
        vc = [(a, e, mi - 12, 0.10) for a, e, mi, vw, b in lead if b < 10]
        sig, ts = legato_line(vc, voices=3, att=0.4, rel=1.0, bright=0.8, vib=0.004, glide=0.03, noise=0.4)
        bus.add(sig, ts, pan=0.25, send=0.3)
    else:
        vc = [(a, e, mi, 0.30 if b < 10 else 0.20) for a, e, mi, vw, b in lead if b < 18]
        sig, ts = legato_line(vc, voices=2, att=0.25, rel=1.0, bright=0.9, vib=0.0055, glide=0.022, noise=0.55)
        bus.add(sig, ts, pan=0.1, send=0.32, gain=1.1)
        fin = [(a, e, mi, 0.24) for a, e, mi, vw, b in lead if b == 18]
        sig, ts = legato_line(fin, voices=3, att=0.6, rel=2.5, bright=0.85, vib=0.005, glide=0.02, noise=0.4)
        bus.add(sig, ts, pan=0.1, send=0.4)
    # ---------- кульминация: скрипки октавой выше, валторны в унисон с темой
    vn = [(a, e, mi + 12, 0.24 if variant == "A" else 0.19) for a, e, mi, vw, b in lead if b >= 10]
    sig, ts = legato_line(vn, voices=8, att=0.2, rel=2.0, bright=1.05, vib=0.0032, glide=0.016, noise=0.3)
    bus.add(sig, ts, pan=-0.3, send=0.28)
    for a, e, mi, vw, b in lead:
        if 10 <= b < 18:
            bus.add(horn(mi, e - a + 0.05, 0.12 if variant == "A" else 0.07), a + 0.01, pan=0.25, send=0.45)
    # ---------- бас (виолончели + контрабасы) связно
    bl = []
    for b in range(NB):
        bass = H[PROG[b]][0]
        e = bt(b + 1) if b < NB - 1 else end_t
        bl.append((bt(b), e, m(bass) + 12, 0.20 if b < 2 else 0.22 if b < 10 else 0.27 if b < 18 else 0.20))
    sig, ts = legato_line(bl, voices=5, att=1.0, rel=2.5, bright=0.75, vib=0.003, glide=0.05, noise=0.35)
    bus.add(sig, ts, pan=0.25, send=0.3)
    bl2 = [(a, e, mi - 12, v * 0.8) for a, e, mi, v in bl if a >= bt(10) - 0.01]
    sig, ts = legato_line(bl2, voices=4, att=0.8, rel=2.5, bright=0.55, vib=0.002, glide=0.05, noise=0.3)
    bus.add(sig, ts, pan=0.2, send=0.25)
    # ---------- струнные аккорды: три голоса с голосоведением; в финале фа мажор с ноной
    voicing = [m("A3"), m("C4"), m("F4")]
    lines = [[], [], []]
    for b in range(NB):
        tones = H[PROG[b]][1]
        voicing = voice_lead(voicing, tones, m("E3"), m("D5"))
        e = bt(b + 1) if b < NB - 1 else end_t
        v = 0.05 if b < 2 else 0.06 if b < 6 else 0.07 if b < 10 else 0.09 if b < 18 else 0.09
        for k in range(3):
            lines[k].append((bt(b), e, voicing[k], v))
    for k in range(3):
        sig, ts = legato_line(lines[k], voices=5, att=1.4, rel=2.5, bright=1.0, vib=0.004, glide=0.07, noise=0.3)
        bus.add(sig, ts + 0.04 * k, pan=-0.35 + 0.3 * k, send=0.28)
    sig, ts = legato_line([(bt(18), end_t, m("G4"), 0.07)], voices=5, att=1.5, rel=2.5, bright=1.0, vib=0.004)
    bus.add(sig, ts, pan=-0.2, send=0.5)
    # ---------- вступление и финал: фортепиано перебором
    for b in range(0, 18):
        bass, tones = H[PROG[b]]
        r = m(bass) + 12
        while r < m("F3"):
            r += 12
        pcs = [m(x) % 12 for x in tones]
        up_ = sorted({x for x in range(m("C4"), m("C6")) if x % 12 in pcs})
        pat = [r, up_[0], up_[1], up_[2], up_[3], up_[2], up_[1], up_[0]]
        vel = 0.17 if b < 2 else 0.15 if b < 10 else 0.16
        for j, nt in enumerate(pat):
            acc = 1.0 if j == 0 else 0.85 if j == 4 else 0.68
            bus.add(piano(nt, BEAT * 1.2, vel * acc), bt(b, j / 2) + rng.uniform(0, 0.006), pan=-0.2 + 0.06 * (j % 4), send=0.3)
    for k, nt in enumerate(["F4", "C5", "G5", "A5", "C6", "F6"]):
        bus.add(piano(m(nt), 4.0, 0.16 - 0.012 * k), bt(18, 0.5 * k + 0.5), pan=0.15, send=0.55)
    for k, nt in enumerate(["C7", "A6", "F6"]):
        bus.add(celesta(m(nt), 0.05), bt(19, 1 + k * 0.5), pan=-0.2, send=0.6)
    # ---------- арфа: перебор восьмыми вверх-вниз в куплете и кульминации
    for b in range(10, 18):
        _, tones = H[PROG[b]]
        mids = [m(x) + 24 for x in tones]
        pat = [mids[0], mids[1], mids[2], mids[0] + 12, mids[1] + 12, mids[2], mids[1], mids[0] + 12]
        v = 0.07
        for j, nt in enumerate(pat):
            bus.add(harp(nt, v * (1.0 if j % 4 == 0 else 0.75)), bt(b, j / 2) + rng.uniform(0, 0.008), pan=-0.45 + 0.08 * (j % 4), send=0.35)
    # ---------- отрывистые струнные восьмыми с 6-го такта — движение вперёд
    for b in range(6, 18):
        bass, tones = H[PROG[b]]
        r = m(bass) + 12
        f5 = r + 7
        for j in range(8):
            nt = r if j % 2 == 0 else f5
            v = (0.11 if b < 10 else 0.14) * (1.0 if j % 4 == 0 else 0.7)
            bus.add(short(nt, v), bt(b, j / 2), pan=0.35, send=0.22)
    # ---------- хор «а» тихо в кульминации
    # ---------- ударные
    for b in range(0, 18):
        v = 0.10 if b < 2 else 0.13 if b < 10 else 0.17
        bus.add(frame_drum(v), bt(b, 0), pan=0.0, send=0.25)
        bus.add(frame_drum(v * 0.6), bt(b, 1.5), pan=0.0, send=0.25)
        bus.add(frame_drum(v * 0.5, low=False), bt(b, 2.5), pan=0.15, send=0.25)
        if b >= 10:
            bus.add(frame_drum(v * 0.75), bt(b, 2), pan=0.0, send=0.25)
            bus.add(frame_drum(v * 0.35, low=False), bt(b, 3.5), pan=-0.15, send=0.25)
        if b >= 2:
            k16 = 16 if b >= 10 else 8
            for j in range(k16):
                acc = 0.05 if j % (k16 // 4) == 0 else 0.03
                bus.add(shaker(acc), bt(b, j * 4 / k16 + 0.02), pan=0.35, send=0.12)
    bus.add(frame_drum(0.15), bt(18), pan=0.0, send=0.35)
    bus.add(cymbal_swell(BAR * 0.95, 0.10), bt(9) + BAR * 0.05, pan=0.0, send=0.4)
    bus.add(cymbal_swell(BAR * 0.95, 0.08), bt(17) + BAR * 0.05, pan=0.0, send=0.4)
    for b in (10, 14):
        bus.add(timp(m("F2"), 0.15, 4.0), bt(b), pan=0.0, send=0.4)
    for k in range(12):
        bus.add(timp(m("C2"), 0.02 + 0.05 * k / 11, 0.6), bt(9, 2) + k * BEAT * 2 / 12, pan=0.0, send=0.4)
    bus.add(timp(m("F2"), 0.12, 4.5), bt(18), pan=0.0, send=0.45)
    return bus


if __name__ == "__main__":
    import time
    var = sys.argv[1] if len(sys.argv) > 1 else "A"
    t = time.time()
    bus = compose(var)
    print(f"партитура {time.time() - t:.0f} с")
    L, R = master(bus)
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.89, R / pk * 0.89
    st = np.empty(2 * len(L))
    st[0::2], st[1::2] = L, R
    with wave.open(f"rassvet2_{var}.wav", "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype(np.int16).tobytes())
    print("готово", round(len(L) / SR, 1), "с;", f"{time.time() - t:.0f} с")
