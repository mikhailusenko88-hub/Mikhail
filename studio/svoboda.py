"""Своя мелодия в характере «Now We Are Free»: женский голос без слов, рамочный барабан и шейкер, струнные, арфа,
к кульминации — хор, валторны, большой барабан. Ноты и гармония свои. Фа мажор / ре минор, 70 уд/мин, ~65 с.
python3 svoboda.py"""
import math
import wave

import numpy as np
from scipy.ndimage import gaussian_filter1d

import theme as th
from theme import SR, m, hz, legato_line, voice_lead, horn, timp, master, piano
from cathedral import line as cline, VOWEL_A
from quartet import pizz

rng = np.random.default_rng(2000)
BEAT = 60 / 70
BAR = 4 * BEAT
T0 = 0.3
NB = 19


def bt(b, x=0.0):
    return T0 + b * BAR + x * BEAT


# ---------------------------------------------------------------- голос: формантный синтез, связно, с переливами
VOW = {"a": [(850, 1.0, 110), (1250, 0.55, 130), (2850, 0.28, 220), (3800, 0.12, 300)],
       "o": [(520, 1.0, 90), (900, 0.65, 110), (2800, 0.16, 220), (3700, 0.08, 300)],
       "e": [(560, 1.0, 90), (1900, 0.45, 160), (2800, 0.30, 220), (3900, 0.12, 300)],
       "u": [(380, 1.0, 80), (820, 0.40, 110), (2700, 0.08, 220), (3600, 0.05, 300)]}


def formant_gain(fh, vw):
    return 0.03 + sum(a * math.exp(-((fh - c) / w) ** 2) for c, a, w in vw)


def voice(notes, vowels, vib=0.011, breath=0.035):
    """notes = [(t_start, t_end, midi, vel)], vowels = гласная на каждую ноту. Возвращает (сигнал, t0)."""
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
    # плавные переходы высоты (портаменто) и маленький «подъезд» снизу на каждой новой ноте
    lp = gaussian_filter1d(pitch, 0.045 * CR) - 0.35 * np.exp(-since / 0.06) * (since < 0.3)
    tc = np.arange(nc) / CR + t0
    vibr = vib * np.clip((since - 0.25) / 0.45, 0, 1) * np.sin(2 * np.pi * 5.4 * tc + 0.3 * np.sin(2 * np.pi * 0.4 * tc))
    f0c = 440.0 * 2 ** ((lp - 69) / 12) * np.exp(vibr)
    amp = gaussian_filter1d(amp, 0.07 * CR)
    env = np.clip((tc - notes[0][0] + 0.1) / 0.35, 0, 1) * np.clip((t1 - tc) / 1.1, 0, 1) ** 1.3
    # «дыхание» громкости внутри долгих нот
    amp = amp * env * (0.9 + 0.1 * np.sin(np.pi * np.clip(since / 2.5, 0, 1)))
    # веса гласных во времени (плавно)
    W = np.zeros((len(names), nc))
    W[vix, np.arange(nc)] = 1
    W = gaussian_filter1d(W, 0.09 * CR, axis=1)
    W /= W.sum(0, keepdims=True) + 1e-9
    xa = np.arange(n) / SR * CR
    up = lambda c: np.interp(xa, np.arange(nc), c)
    f0a = up(f0c)
    ph = 2 * np.pi * np.cumsum(f0a) / SR
    out = np.zeros(n)
    H = 18
    AH = []
    for h in range(1, H + 1):
        fh = f0c * h
        g = np.zeros(nc)
        for k, nm in enumerate(names):
            g += W[k] * (0.03 + sum(a * np.exp(-((fh - c) / w) ** 2) for c, a, w in VOW[nm]))
        tilt = 1.15 + 0.9 * np.clip((f0c - 650) / 450, 0, 1)      # высокие ноты — мягче, как у сопрано
        src = 1.0 / h ** tilt * np.exp(-fh / 6500)
        AH.append(g * src * (fh < 9000))
    # выровнять громкость: разные гласные на разной высоте не должны «выстреливать»
    P = np.sqrt(sum(a * a for a in AH)) + 1e-9
    P = gaussian_filter1d(P, 0.05 * CR)
    for h, a_h in enumerate(AH, start=1):
        if not a_h.any():
            continue
        out += up(a_h / P * 0.6) * np.sin(h * ph + 0.5 * h)
    nz = rng.normal(0, 1, n)
    br = gaussian_filter1d(nz, 1.5) - gaussian_filter1d(nz, 5)
    sig = out / 2.2 + br * breath
    return up(amp) * sig, t0


# ---------------------------------------------------------------- ударные
def frame_drum(vel, low=True):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = (68 if low else 120) * (1 + 0.35 * np.exp(-t / 0.03))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.32 if low else 0.15))
    nz = rng.normal(0, 1, n)
    skin = (gaussian_filter1d(nz, 2) - gaussian_filter1d(nz, 12)) * np.exp(-t / 0.03) * 0.35
    return vel * (s + skin) * np.minimum(1, t / 0.002)


def shaker(vel):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    nz = rng.normal(0, 1, n)
    hi = gaussian_filter1d(nz, 0.6) - gaussian_filter1d(nz, 2.2)
    e = np.minimum(1, t / 0.012) * np.exp(-t / 0.035)
    return vel * hi * e


# ---------------------------------------------------------------- партитура
HARM = {
    0: ("D2", ["D3", "A3", "F4"]), 1: ("D2", ["D3", "A3", "F4"]),
    2: ("D2", ["D3", "F3", "A3"]), 3: ("Bb1", ["D3", "F3", "Bb3"]), 4: ("F2", ["C3", "F3", "A3"]), 5: ("C2", ["C3", "E3", "G3"]),
    6: ("D2", ["D3", "F3", "A3"]), 7: ("Bb1", ["D3", "F3", "Bb3"]), 8: ("C2", ["C3", "E3", "G3"]), 9: ("C2", ["C3", "F3", "G3"]),
    10: ("Bb1", ["D3", "F3", "Bb3"]), 11: ("F2", ["C3", "F3", "A3"]), 12: ("C2", ["C3", "E3", "G3"]), 13: ("D2", ["D3", "F3", "A3"]),
    14: ("Bb1", ["D3", "F3", "Bb3"]), 15: ("A1", ["C3", "F3", "A3"]), 16: ("G1", ["D3", "F3", "Bb3"]), 17: ("C2", ["C3", "E3", "G3"]),
    18: ("F1", ["C3", "F3", "A3"]),
}
MEL = [  # (такт, доля, длительность, нота, гласная)
    (2, 0, 1.5, "D5", "a"), (2, 1.5, .5, "E5", "a"), (2, 2, 2, "F5", "o"),
    (3, 0, 1, "D5", "e"), (3, 1, 1, "C5", "a"), (3, 2, 2, "Bb4", "o"),
    (4, 0, 1.5, "A4", "a"), (4, 1.5, .5, "C5", "a"), (4, 2, 1, "F5", "e"), (4, 3, 1, "E5", "a"),
    (5, 0, 2.5, "E5", "o"), (5, 2.5, .5, "D5", "o"), (5, 3, 1, "C5", "u"),
    (6, 0, 1.5, "D5", "a"), (6, 1.5, .5, "E5", "a"), (6, 2, 1, "F5", "e"), (6, 3, 1, "A5", "a"),
    (7, 0, 2, "G5", "o"), (7, 2, 1, "F5", "a"), (7, 3, 1, "D5", "e"),
    (8, 0, 1.5, "E5", "a"), (8, 1.5, .5, "F5", "a"), (8, 2, 2, "G5", "o"),
    (9, 0, 2, "F5", "a"), (9, 2, 2, "E5", "o"),
    (10, 0, 1, "F5", "a"), (10, 1, 1, "Bb5", "a"), (10, 2, 2, "D6", "o"),
    (11, 0, 1.5, "C6", "a"), (11, 1.5, .5, "A5", "e"), (11, 2, 2, "F5", "o"),
    (12, 0, 1, "G5", "a"), (12, 1, 1, "A5", "a"), (12, 2, 1, "Bb5", "e"), (12, 3, 1, "C6", "a"),
    (13, 0, 3, "A5", "o"), (13, 3, .5, "G5", "a"), (13, 3.5, .5, "F5", "a"),
    (14, 0, 1, "F5", "e"), (14, 1, 1, "G5", "a"), (14, 2, 1, "Bb5", "a"), (14, 3, 1, "D6", "o"),
    (15, 0, 2, "C6", "a"), (15, 2, 2, "A5", "o"),
    (16, 0, 1.5, "Bb5", "a"), (16, 1.5, .5, "A5", "e"), (16, 2, 2, "G5", "o"),
    (17, 0, 2, "G5", "a"), (17, 2, 2, "E5", "o"),
    (18, 0, 4, "F5", "a"),
]


def compose():
    th.TOTAL = T0 + NB * BAR + 7
    bus = th.Bus()
    # ---------- голос
    notes = [(bt(b, x) - 0.03, bt(b, x + d) + (2.5 if b == 18 else 0), m(nt), (0.55 if b < 10 else 0.66) if b < 18 else 0.55) for b, x, d, nt, _ in MEL]
    sig, ts = voice(notes, [v for *_, v in MEL])
    bus.add(sig, ts, pan=0.0, send=0.42, gain=1.2)
    # ---------- басовый бурдон и бас аккордов (виолончели/контрабасы) связно
    bl = []
    for b in range(NB):
        bass, _ = HARM[b]
        end = bt(b + 1) if b < NB - 1 else bt(b, 4) + 3
        bl.append((bt(b), end, m(bass) + 12, 0.22 if b < 2 else 0.21 if b < 10 else 0.28 if b < 18 else 0.20))
    sig, ts = legato_line(bl, voices=5, att=1.2, rel=2.5, bright=0.75, vib=0.003, glide=0.06, noise=0.4)
    bus.add(sig, ts, pan=0.25, send=0.3)
    bl2 = [(a, b_, mi - 12, v * 0.8) for a, b_, mi, v in bl if a >= bt(10)]
    sig, ts = legato_line(bl2, voices=4, att=0.8, rel=2.5, bright=0.55, vib=0.002, glide=0.06, noise=0.3)
    bus.add(sig, ts, pan=0.2, send=0.25)
    # ---------- струнные: три голоса гармонии с голосоведением
    voicing = [m("A3"), m("D4"), m("F4")]
    lines = [[], [], []]
    for b in range(NB):
        voicing = voice_lead(voicing, HARM[b][1], m("F3"), m("D5"))
        end = bt(b + 1) if b < NB - 1 else bt(b, 4) + 3
        v = 0.09 if b < 2 else 0.09 if b < 6 else 0.11 if b < 10 else 0.16 if b < 18 else 0.10
        for k in range(3):
            lines[k].append((bt(b), end, voicing[k], v))
    for k in range(3):
        sig, ts = legato_line(lines[k], voices=5, att=1.5, rel=2.5, bright=1.0, vib=0.004, glide=0.08, noise=0.35)
        bus.add(sig, ts + 0.04 * k, pan=-0.3 + 0.25 * k, send=0.38)
    # ---------- высокие скрипки в кульминации — дублируют голос октавой ниже, мягко
    vn = [(a, b_, mi - 12, 0.22) for (a, b_, mi, v) in notes if a >= bt(10) - 0.1 and a < bt(18)]
    sig, ts = legato_line(vn, voices=8, att=0.3, rel=1.0, bright=1.3, vib=0.005, glide=0.035)
    bus.add(sig, ts, pan=-0.35, send=0.35)
    # ---------- арфа/щипки: перебор восьмыми со 2-го такта
    for b in range(1, NB):
        bass, tones = HARM[b]
        mids = [m(x) + 12 for x in tones]
        pat = [mids[0], mids[1], mids[2], mids[1] + 12, mids[2], mids[1], mids[2] + 12, mids[1]]
        if b == NB - 1:
            pat = pat[:5]
        v = 0.10 if b < 10 else 0.08
        for j, nt in enumerate(pat):
            bus.add(pizz(nt, v * (1.0 if j % 4 == 0 else 0.7)), bt(b, j / 2) + rng.uniform(0, 0.01), pan=-0.4 + 0.1 * (j % 3), send=0.32)
    # ---------- хор и валторны в кульминации
    for b in range(10, 18):
        _, tones = HARM[b]
        for k, tn in enumerate(tones):
            bus.add(horn(m(tn) + 12, BAR + 0.15, 0.06 if b < 14 else 0.09), bt(b) + 0.03 * k, pan=0.2, send=0.45)
    ch = [(bt(b), bt(b + 1), m(HARM[b][1][2]) + 12, 0.32) for b in range(10, 18)]
    sig, ts = cline(ch, "choir", voices=10, att=1.2, rel=2.0, vowel=VOWEL_A)
    bus.add(sig, ts, pan=0.0, send=0.55, gain=0.6)
    # ---------- ударные: «сердце» рамочного барабана, шейкер; большой барабан на кульминации
    for b in range(0, NB):
        if b == NB - 1:
            bus.add(frame_drum(0.17), bt(b, 0), pan=0.0, send=0.3)
            break
        v = 0.13 if b < 2 else 0.15 if b < 10 else 0.19
        bus.add(frame_drum(v), bt(b, 0), pan=0.0, send=0.25)
        bus.add(frame_drum(v * 0.65), bt(b, 1.5), pan=0.0, send=0.25)
        bus.add(frame_drum(v * 0.5, low=False), bt(b, 2.5), pan=0.15, send=0.25)
        if b >= 2:
            for j in range(8):
                bus.add(shaker(0.035 if j % 2 else 0.05), bt(b, j / 2 + 0.02), pan=0.35, send=0.15)
    for b in (10, 14):
        bus.add(timp(m("D2"), 0.16, 4.0), bt(b), pan=0.0, send=0.4)
    for k in range(12):
        bus.add(timp(m("C2"), 0.02 + 0.05 * k / 11, 0.6), bt(9, 2) + k * BEAT * 2 / 12, pan=0.0, send=0.4)
    bus.add(timp(m("F2"), 0.12, 4.5), bt(18), pan=0.0, send=0.45)
    # ---------- тихие ноты фортепиано в конце
    for k, nt in enumerate(["F5", "C6", "A5"]):
        bus.add(piano(m(nt), 3.5, 0.25), bt(18, 1 + k), pan=0.2, send=0.5)
    return bus


if __name__ == "__main__":
    import time
    t = time.time()
    bus = compose()
    print(f"партитура {time.time() - t:.0f} с")
    L, R = master(bus)
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.89, R / pk * 0.89
    st = np.empty(2 * len(L))
    st[0::2], st[1::2] = L, R
    with wave.open("svoboda.wav", "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype(np.int16).tobytes())
    print("готово", round(len(L) / SR, 1), "с;", f"{time.time() - t:.0f} с")
