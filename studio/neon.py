"""«Неон» — своя мелодия в духе синтвейва 80-х (ночной город, неон). Ре мажор, 100 уд/мин, I–V–vi–IV.
Чистый звук по правилам studio/chisto: у каждого звука только нижние призвуки, бас — почти чистый тон, никаких шумовых
тарелок и шейкеров; малый барабан — тональный корпус + короткий шумок, срезанный выше 4 кГц (без «пола» шума).
python3 neon.py full|short out.wav"""
import math
import sys

import numpy as np
from scipy.signal import butter, sosfilt

import theme as th
from theme import SR, m, hz
from chisto import clean_line, master_clean, _cos_in
from rassvet4 import write24

rng = np.random.default_rng(1986)
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT

# аккорды: бас (62–124 Гц, ниже 60 Гц почти ничего — правило чистого низа) и подложка
CH = {
    "D": ("D2", ["D4", "F#4", "A4"]),
    "A": ("A2", ["C#4", "E4", "A4"]),
    "Bm": ("B2", ["D4", "F#4", "B4"]),
    "G": ("G2", ["D4", "G4", "B4"]),
}
PROG = ["D", "A", "Bm", "G"]

# мелодии: (такт, доля, длительность в долях, нота)
VERSE = [
    (0, 0, 1.5, "F#4"), (0, 1.5, .5, "A4"), (0, 2, 1, "F#4"), (0, 3, 1, "E4"),
    (1, 0, 1.5, "E4"), (1, 1.5, 1, "A4"), (1, 2.5, 1.5, "C#5"),
    (2, 0, 2, "D5"), (2, 2, 1, "C#5"), (2, 3, 1, "B4"),
    (3, 0, 1.5, "B4"), (3, 1.5, .5, "A4"), (3, 2, 1, "G4"), (3, 3, 1, "A4"),
    (4, 0, 1.5, "F#4"), (4, 1.5, .5, "A4"), (4, 2, 2, "D5"),
    (5, 0, 1.5, "C#5"), (5, 1.5, 1, "E5"), (5, 2.5, 1.5, "C#5"),
    (6, 0, 1, "B4"), (6, 1, 1, "D5"), (6, 2, 2, "F#5"),
    (7, 0, 2, "E5"), (7, 2, 1, "D5"), (7, 3, 1, "C#5"),
]
CHORUS = [
    (0, 0, 2, "A5"), (0, 2, 1, "F#5"), (0, 3, 1, "A5"),
    (1, 0, 3, "E5"), (1, 3, 1, "C#5"),
    (2, 0, 2, "F#5"), (2, 2, 1, "D5"), (2, 3, 1, "F#5"),
    (3, 0, 1.5, "G5"), (3, 1.5, .5, "F#5"), (3, 2, 1, "E5"), (3, 3, 1, "D5"),
    (4, 0, 2, "A5"), (4, 2, 1, "B5"), (4, 3, 1, "A5"),
    (5, 0, 1.5, "E5"), (5, 1.5, 2.5, "A5"),
    (6, 0, 1, "B5"), (6, 1, 1, "A5"), (6, 2, 2, "F#5"),
    (7, 0, 2, "G5"), (7, 2, 1, "E5"), (7, 3, 1, "C#5"),
]


# ---------------------------------------------------------------- инструменты
def env_ad(t, att, dec):
    return _cos_in(t, att) * np.exp(-np.maximum(t - att, 0) / dec)


def kick(vel):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 66 + 95 * np.exp(-t / 0.025)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.085) + 0.25 * np.sin(2 * np.pi * np.cumsum(2 * f) / SR) * np.exp(-t / 0.03)
    return vel * s * _cos_in(t, 0.003) * np.clip((0.45 - t) / 0.08, 0, 1)


LP_SN = butter(4, 4000, btype="low", fs=SR, output="sos")
HP_SN = butter(2, 900, btype="high", fs=SR, output="sos")


def snare(vel):
    """тональный корпус + короткий шумок до 4 кГц; «гейтованный» хвост — шумок обрезан мягко на 0,22 с"""
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    body = (np.sin(2 * np.pi * 185 * t) * 0.9 + 0.5 * np.sin(2 * np.pi * 330 * t + 1)) * np.exp(-t / 0.07)
    nz = sosfilt(LP_SN, sosfilt(HP_SN, rng.normal(0, 1, n)))
    nz /= np.abs(nz).max()
    gate = np.where(t < 0.16, np.exp(-t / 0.18), np.exp(-0.16 / 0.18) * np.exp(-(t - 0.16) / 0.025))
    s = body * 0.8 + 0.5 * nz * gate * _cos_in(t, 0.005)
    return vel * s * _cos_in(t, 0.002) * np.clip((0.32 - t) / 0.05, 0, 1)


def bass(midi, dur, vel):
    """октавный бас: почти чистый тон + тихие 2-я и 3-я гармоники, короткий «щипок» фильтра"""
    n = int((dur + 0.06) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    br = np.exp(-t / 0.09)
    s = np.sin(2 * np.pi * f * t) + (0.18 + 0.25 * br) * np.sin(4 * np.pi * f * t) + 0.12 * br * np.sin(6 * np.pi * f * t)
    return vel * s * _cos_in(t, 0.006) * np.clip((dur + 0.06 - t) / 0.06, 0, 1)


def pluck(midi, vel, dec=0.24):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    s = np.zeros(n)
    for h, a in ((1, 1.0), (2, 0.45), (3, 0.28), (4, 0.12), (5, 0.06)):
        if f * h > 5500:
            break
        s += a * np.sin(2 * np.pi * f * h * t + 0.7 * h) * np.exp(-t * h ** 0.6 / dec)
    return vel * s * _cos_in(t, 0.004) * np.clip((0.9 - t) / 0.2, 0, 1)


def pad(midi, dur, vel, bright=1.0):
    """синт-подложка: 4 расстроенных голоса, призвуки до 6-го, медленный «вдох» яркости"""
    n = int((dur + 1.4) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    s = np.zeros(n)
    for det in (-10, -3, 4, 11):
        fd = f * 2 ** (det / 1200)
        p0 = rng.uniform(0, 6.28)
        for h in range(1, 7):
            if fd * h > 4000:
                break
            s += np.sin(2 * np.pi * fd * h * t + p0 * h) / h ** (2.0 - 0.4 * bright)
    e = np.clip(t / 0.5, 0, 1) ** 1.2 * np.clip((dur + 1.4 - t) / 1.4, 0, 1) ** 1.3
    return vel * s * e / 4


def sp_lead(fc=2300.0):
    """«квадрат» с мягкими верхами: нечётные призвуки сильнее, спад выше fc"""
    return lambda h, fh: (1.0 / h if h % 2 else 0.35 / h) * math.exp(-fh / fc)


def riser(dur, vel):
    """взлёт перед припевом: тональные высокие ноты ре мажора (без шума)"""
    n = int((dur + 0.8) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k, nt in enumerate(("A5", "D6", "F#6", "A6")):
        f = hz(m(nt))
        for det in (-5, 5):
            s += np.sin(2 * np.pi * f * 2 ** (det / 1200) * t + k) / (1 + 0.5 * k)
    e = np.where(t < dur, (t / dur) ** 3, np.exp(-(t - dur) / 0.3))
    return vel * 0.3 * s * e


# ---------------------------------------------------------------- аранжировка
def plan(kind):
    """список тактов: (аккорд, часть, такт мелодии)"""
    if kind == "full":
        P = [(PROG[i % 4], "intro", None) for i in range(4)]
        P += [(PROG[i % 4], "verse", i) for i in range(8)]
        P += [(PROG[i % 4], "chorus", i) for i in range(8)]
        P += [(PROG[i % 4], "outro", i) for i in range(4)]
        P += [("D", "end", None)]
    else:   # short ~27 с: такт разгона, сразу припев, финал на тонике
        P = [("G", "pre", None)]
        P += [(PROG[i % 4], "chorus", i) for i in range(8)]
        P += [("D", "end", None)]
    return P


def compose(kind):
    P = plan(kind)
    T0 = 0.15
    total = T0 + len(P) * BAR + 4.5
    th.TOTAL = total
    bus = th.Bus()
    tb = lambda b, beat=0.0: T0 + b * BAR + beat * BEAT  # noqa: E731

    lead_notes = []
    for b, (ch, sec, mb) in enumerate(P):
        root, tones = CH[ch]
        r = m(root)
        tp = [m(x) for x in tones]
        drums = sec in ("verse", "chorus", "pre") or (sec == "outro" and mb < 2)
        hot = sec == "chorus"

        # подложка
        pv = {"intro": 0.06, "verse": 0.07, "chorus": 0.085, "outro": 0.065, "end": 0.08, "pre": 0.07}[sec]
        dur = BAR * (2.6 if sec == "end" else 1.0)
        for i, mi in enumerate(tp):
            bus.add(pad(mi, dur, pv, bright=1.4 if hot else 1.0), tb(b), pan=(-0.45, 0.0, 0.45)[i], send=0.45)
        if hot:
            bus.add(pad(tp[0] - 12, dur, 0.05), tb(b), pan=0, send=0.35)

        if sec == "end":
            bus.add(bass(r, 3.2, 0.32), tb(b), send=0.05)
            bus.add(kick(0.55), tb(b), send=0.05)
            for k, mi in enumerate(sorted(tp + [tp[0] + 12])):
                bus.add(pluck(mi + 12, 0.11, dec=0.5), tb(b, 0.12 * k), pan=(-0.5 + 0.33 * k), send=0.5)
            continue

        # арпеджио шестнадцатыми с эхом на пунктирную восьмую (лево-право)
        if sec != "pre" or True:
            seq = [tp[0], tp[1], tp[2], tp[0] + 12, tp[2], tp[1]] * 3
            av = {"intro": 0.10, "verse": 0.085, "chorus": 0.075, "outro": 0.09, "pre": 0.09}[sec]
            for k in range(16):
                acc = 1.0 if k % 4 == 0 else 0.72
                t = tb(b, 0.25 * k)
                sg = pluck(seq[k] + 12, av * acc)
                bus.add(sg, t, pan=0.12, send=0.25)
                bus.add(sg * 0.32, t + 0.75 * BEAT, pan=-0.6, send=0.35)
                bus.add(sg * 0.16, t + 1.5 * BEAT, pan=0.6, send=0.4)

        # бас восьмыми «октавой»
        if sec in ("verse", "chorus", "pre") or (sec == "intro" and b >= 2) or (sec == "outro" and mb < 2):
            bv = 0.30 if sec != "intro" else 0.22
            for k in range(8):
                mi = r if k % 2 == 0 else r + 12
                bus.add(bass(mi, 0.42 * BEAT, bv * (1.0 if k % 2 == 0 else 0.8)), tb(b, 0.5 * k), send=0.03)

        # барабаны: бочка на каждую долю, малый на 2 и 4
        if drums:
            for k in range(4):
                bus.add(kick(0.5), tb(b, k), send=0.04)
            for k in (1, 3):
                bus.add(snare(0.30), tb(b, k), pan=0.05, send=0.55)
            if sec == "pre":   # дробь малого в конце разгонного такта
                for k, v in ((2.5, 0.16), (2.75, 0.2), (3.25, 0.22), (3.5, 0.26), (3.75, 0.3)):
                    bus.add(snare(v), tb(b, k), send=0.5)

        # мелодия
        mel = VERSE if sec == "verse" else CHORUS if sec == "chorus" else None
        if sec == "outro" and mb < 2:
            mel = VERSE
        if mel is not None:
            vv = 0.58 if sec == "chorus" else 0.5 if sec == "verse" else 0.38
            for (mb2, bt, dl, nt) in mel:
                if mb2 == mb:
                    a = tb(b, bt)
                    lead_notes.append((a, a + dl * BEAT * 0.93, m(nt), vv))

        # взлёт перед припевом
        nxt = P[b + 1][1] if b + 1 < len(P) else None
        if nxt == "chorus" and sec != "chorus":
            bus.add(riser(BAR, 0.5), tb(b), pan=0, send=0.6)

    # финальная нота мелодии на тонике
    end_b = len(P) - 1
    lead_notes.append((tb(end_b), tb(end_b) + 2.2 * BEAT, m("D5"), 0.5))

    # мелодия одной связной линией (фразы разрываем на паузах > 1 доли)
    phrases, cur = [], [lead_notes[0]]
    for nt in lead_notes[1:]:
        if nt[0] - cur[-1][1] > BEAT:
            phrases.append(cur)
            cur = [nt]
        else:
            cur.append(nt)
    phrases.append(cur)
    for ph in phrases:
        sig, t0 = clean_line(ph, sp_lead(), voices=3, att=0.02, rel=0.35, glide=0.035, vib=0.0022, fmax=3200, det=7)
        bus.add(sig * 0.9, t0, pan=-0.08, send=0.35)
        bus.add(sig * 0.22, t0 + 0.75 * BEAT, pan=0.55, send=0.45)   # эхо мелодии

    L, R = master_clean(bus, air=0.18)
    # хвост: 2,6 с после финального такта, мягкий спад
    end_t = tb(end_b) + 2.6 * BEAT + 2.6
    n = min(len(L), int(end_t * SR))
    L, R = L[:n].copy(), R[:n].copy()
    fo = int(1.2 * SR)
    L[-fo:] *= np.linspace(1, 0, fo) ** 2
    R[-fo:] *= np.linspace(1, 0, fo) ** 2
    pk = max(np.abs(L).max(), np.abs(R).max())
    return L / pk * 0.89, R / pk * 0.89


if __name__ == "__main__":
    kind, out = sys.argv[1], sys.argv[2]
    L, R = compose(kind)
    write24(out, L, R)
    print(out, f"{len(L) / SR:.1f} с")
