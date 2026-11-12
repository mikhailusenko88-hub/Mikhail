"""«Рассвет» с низким голосом — доработка и варианты + короткие версии для Shorts.
Стили: main (голос, арфа, барабаны, скрипки и валторны), tihiy (голос и фортепиано), epik (большие барабаны, медь, хор).
Планы: full (~67 с), kuplet (~23 с), raspev (~29 с).
python3 rassvet3.py <стиль> <план> <файл.wav>"""
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
BEAT = 60 / 76
BAR = 4 * BEAT

H = {
    "F": ("F2", ["F3", "A3", "C4"]), "Bb/F": ("F2", ["F3", "Bb3", "D4"]), "C/E": ("E2", ["E3", "G3", "C4"]),
    "Dm": ("D2", ["D3", "F3", "A3"]), "Bb": ("Bb1", ["D3", "F3", "Bb3"]), "F/A": ("A1", ["F3", "A3", "C4"]),
    "Gm7": ("G1", ["F3", "Bb3", "D4"]), "C7": ("C2", ["E3", "Bb3", "C4"]),
}
PH = ["F", "C/E", "Dm", "Bb", "F/A", "Bb", "Gm7", "C7"]
VERSE = [  # такт фразы -> [(доля, длительность, нота, гласная)]
    [(0, 1, "C4", "o"), (1, 1, "F4", "a"), (2, 2, "A4", "o")],
    [(0, 1.5, "G4", "a"), (1.5, .5, "A4", "a"), (2, 1, "G4", "o"), (3, 1, "E4", "u")],
    [(0, 1, "F4", "o"), (1, 1, "A4", "a"), (2, 2, "D5", "o")],
    [(0, 1.5, "D5", "a"), (1.5, .5, "C5", "a"), (2, 2, "Bb4", "o")],
    [(0, 1.5, "A4", "o"), (1.5, .5, "Bb4", "a"), (2, 2, "C5", "a")],
    [(0, 2, "F5", "o"), (2, 1, "D5", "a"), (3, 1, "Bb4", "o")],
    [(0, 1.5, "C5", "a"), (1.5, .5, "Bb4", "a"), (2, 2, "G4", "o")],
    [(0, 1, "G4", "a"), (1, .5, "A4", "a"), (1.5, .5, "Bb4", "a"), (2, 2, "C5", "o")],
]
CAD = [(0, 1.5, "C5", "a"), (1.5, .5, "Bb4", "a"), (2, 1, "G4", "o"), (3, 1, "Bb4", "a")]   # ii7 → V7 в одном такте
FIN = [(0, 4, "A4", "a")]
PHRASE_END = {3, 7, "cad"}          # после этих тактов — вдох


def plan(name):
    """[(аккорд или (аккорд, аккорд), мелодия, раздел)]"""
    if name == "full":
        return ([("F", None, "intro"), ("Bb/F", None, "intro")] + [(PH[i], i, "verse") for i in range(8)]
                + [(PH[i], i, "climax") for i in range(8)] + [("F", "fin", "end")])
    if name == "kuplet":
        return ([(PH[i], i, "verse") for i in range(3)] + [(PH[4], 4, "climax"), (PH[5], 5, "climax"),
                (("Gm7", "C7"), "cad", "climax"), ("F", "fin", "end")])
    if name == "raspev":
        return [(PH[i], i, "climax") for i in range(6)] + [(("Gm7", "C7"), "cad", "climax"), ("F", "fin", "end")]
    raise ValueError(name)


def mel_of(k):
    return FIN if k == "fin" else CAD if k == "cad" else VERSE[k] if k is not None else []


def halves(ch):
    return [(ch[0], 0, 2), (ch[1], 2, 2)] if isinstance(ch, tuple) else [(ch, 0, 4)]


F_SCALE = [5, 7, 9, 10, 0, 2, 4]


def third_below(mi):
    pc = mi % 12
    if pc not in F_SCALE:
        return mi - 3
    k = F_SCALE.index(pc)
    t = F_SCALE[(k - 2) % 7]
    d = (pc - t) % 12
    return mi - d


# ---------------------------------------------------------------- голос: контральто, вдохи между фразами
def voice(notes, vowels, vib=0.0055, vib_rate=5.0, vib_delay=0.45, glide=0.022, breath=0.02, detune=0.0, seed=1):
    r = np.random.default_rng(seed)
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
        nxt = notes[i + 1][0] if i + 1 < len(notes) else b
        s1 = int((nxt - t0) * CR)
        se = int((b - t0) * CR) if nxt - b > 0.04 else s1     # пауза-вдох: громкость в ноль, высота держится
        pitch[s0:s1] = mi
        amp[s0:se] = v
        since[s0:s1] = np.arange(s1 - s0) / CR
        vix[s0:s1] = names.index(vowels[i])
    sl = int((notes[-1][1] - t0) * CR)
    pitch[sl:] = notes[-1][2]
    since[sl:] = since[sl - 1] + np.arange(nc - sl) / CR
    lp = gaussian_filter1d(pitch, glide * CR) + detune / 100
    lp += gaussian_filter1d(r.normal(0, 1, nc), 0.25 * CR) * 0.6       # живая неровность строя (±несколько центов)
    tc = np.arange(nc) / CR + t0
    ph0 = r.uniform(0, 6.28)
    vibr = vib * np.clip((since - vib_delay) / 0.6, 0, 1) * np.sin(2 * np.pi * vib_rate * tc + ph0 + 0.2 * np.sin(2 * np.pi * 0.3 * tc))
    f0c = 440.0 * 2 ** ((lp - 69) / 12) * np.exp(vibr)
    amp = gaussian_filter1d(amp, 0.06 * CR)
    env = np.clip((tc - notes[0][0] + 0.1) / 0.3, 0, 1) * np.clip((t1 - tc) / 1.1, 0, 1) ** 1.3
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
            out += up(a_h / P * 0.6) * np.sin(h * ph + 0.5 * h + r.uniform(0, 0.3))
    nz = r.normal(0, 1, n)
    br = gaussian_filter1d(nz, 1.5) - gaussian_filter1d(nz, 5)
    sig = up(amp) * (out / 2.2 + br * breath)
    # вдохи в паузах
    for i in range(len(notes) - 1):
        gap = notes[i + 1][0] - notes[i][1]
        if gap > 0.15:
            k0 = int((notes[i][1] + 0.03 - t0) * SR)
            k1 = int((notes[i + 1][0] - 0.02 - t0) * SR)
            L = k1 - k0
            if L > 100:
                z = r.normal(0, 1, L)
                z = gaussian_filter1d(z, 1.2) - gaussian_filter1d(z, 9)
                e = np.sin(np.pi * np.linspace(0, 1, L)) ** 1.5
                sig[k0:k1] += 0.05 * notes[i + 1][3] * z * e
    return sig, t0


def taiko(vel):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    f = 52 * (1 + 0.6 * np.exp(-t / 0.025))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45)
    nz = rng.normal(0, 1, n)
    skin = (gaussian_filter1d(nz, 3) - gaussian_filter1d(nz, 20)) * np.exp(-t / 0.05) * 0.5
    return vel * (s + skin) * np.minimum(1, t / 0.003)


# ---------------------------------------------------------------- аранжировка
def compose(style, plan_name):
    P = plan(plan_name)
    pre = 0.8 if plan_name == "raspev" else 0.3
    nb = len(P)

    def bt(b, x=0.0):
        return pre + b * BAR + x * BEAT

    fin_b = nb - 1
    hold = 1.15 * BAR if plan_name == "full" else 1.25 * BAR
    end_t = bt(fin_b) + hold
    th.TOTAL = end_t + 6
    bus = th.Bus()
    LV = {"intro": 0, "verse": 1, "climax": 2, "end": 3}
    # ---------- мелодия
    lead = []
    for b, (ch, mk, sec) in enumerate(P):
        for x, d, nt, vw in mel_of(mk):
            a = bt(b, x) - 0.02
            e = end_t if mk == "fin" else bt(b, x + d)
            lead.append([a, e, m(nt), vw, b, sec])
    for i in range(len(lead) - 1):                       # вдох в конце фразы
        b0, b1 = lead[i][4], lead[i + 1][4]
        if b1 != b0 and (P[b0][1] in PHRASE_END or P[b0][2] != P[b1][2]):
            lead[i][1] -= 0.30
    lead_vel = {"verse": 0.42, "climax": 0.58, "end": 0.48}
    if style == "tihiy":
        lead_vel = {"verse": 0.44, "climax": 0.52, "end": 0.46}
    notes = [(a, e, mi, lead_vel[sec]) for a, e, mi, vw, b, sec in lead]
    vows = [vw for a, e, mi, vw, b, sec in lead]
    sig, ts = voice(notes, vows, seed=11)
    bus.add(sig, ts, pan=-0.08, send=0.34, gain=1.15)
    sig, ts = voice(notes, vows, seed=29, detune=6, vib=0.005)          # второй дубль
    bus.add(sig, ts + 0.019, pan=0.1, send=0.38, gain=0.6)
    # второй голос терцией ниже в кульминации
    harm = [(a, e, third_below(mi), lead_vel[sec] * 0.62) for a, e, mi, vw, b, sec in lead if sec == "climax"]
    if harm and style != "tihiy":
        sig, ts = voice(harm, ["o"] * len(harm), seed=47, vib=0.004)
        bus.add(sig, ts + 0.01, pan=0.22, send=0.42, gain=0.75)
    # виолончель тихо поддерживает голос октавой ниже в куплете
    vc = [(a, e, mi - 12, 0.09) for a, e, mi, vw, b, sec in lead if sec == "verse"]
    if vc:
        sig, ts = legato_line(vc, voices=3, att=0.4, rel=1.0, bright=0.8, vib=0.004, glide=0.03, noise=0.4)
        bus.add(sig, ts, pan=0.25, send=0.3)
    # ---------- скрипки октавой выше и валторны в кульминации
    vn_vel = {"main": 0.18, "tihiy": 0.10, "epik": 0.21}[style]
    vn = [(a, e, mi + 12, vn_vel) for a, e, mi, vw, b, sec in lead if sec == "climax"]
    if vn:
        sig, ts = legato_line(vn, voices=8, att=0.3, rel=2.0, bright=1.0, vib=0.0038, glide=0.022, noise=0.3)
        bus.add(sig, ts, pan=-0.3, send=0.34)
    if style != "tihiy":
        hv = 0.07 if style == "main" else 0.11
        for a, e, mi, vw, b, sec in lead:
            if sec == "climax":
                bus.add(horn(mi, e - a + 0.05, hv), a + 0.01, pan=0.25, send=0.45)
                if style == "epik":
                    bus.add(horn(mi - 12, e - a + 0.05, hv * 0.7), a + 0.01, pan=0.3, send=0.45)
    # ---------- гармония: бас и три голоса струнных
    segs = []                                              # (начало, конец, аккорд, раздел)
    for b, (ch, mk, sec) in enumerate(P):
        for c, x, d in halves(ch):
            segs.append([bt(b, x), bt(b, x + d), c, sec, b, x])
    segs[-1][1] = end_t
    bv = {0: 0.19, 1: 0.21, 2: 0.27, 3: 0.20}
    bl = [(a, e, m(H[c][0]) + 12, bv[LV[sec]]) for a, e, c, sec, b, x in segs]
    sig, ts = legato_line(bl, voices=5, att=0.9, rel=2.5, bright=0.75, vib=0.003, glide=0.05, noise=0.35)
    bus.add(sig, ts, pan=0.25, send=0.3)
    bl2 = [(a, e, mi - 12, v * (0.8 if style != "epik" else 1.0)) for (a, e, mi, v), s in zip(bl, segs) if s[3] in ("climax", "end")]
    if bl2 and style != "tihiy":
        sig, ts = legato_line(bl2, voices=4, att=0.8, rel=2.5, bright=0.55, vib=0.002, glide=0.05, noise=0.3)
        bus.add(sig, ts, pan=0.2, send=0.25)
    pv = {"main": (0.07, 0.09, 0.14, 0.11), "tihiy": (0.05, 0.06, 0.08, 0.08), "epik": (0.08, 0.10, 0.15, 0.12)}[style]
    voicing = [m("A3"), m("C4"), m("F4")]
    lines = [[], [], []]
    for a, e, c, sec, b, x in segs:
        voicing = voice_lead(voicing, H[c][1], m("E3"), m("D5"))
        for k in range(3):
            lines[k].append((a, e, voicing[k], pv[LV[sec]]))
    for k in range(3):
        sig, ts = legato_line(lines[k], voices=5, att=1.3, rel=2.5, bright=1.0, vib=0.004, glide=0.07, noise=0.3)
        bus.add(sig, ts + 0.04 * k, pan=-0.35 + 0.3 * k, send=0.34)
    sig, ts = legato_line([(bt(fin_b), end_t, m("G4"), 0.06)], voices=5, att=1.5, rel=2.5, bright=1.0, vib=0.004)
    bus.add(sig, ts, pan=-0.2, send=0.5)
    # ---------- перебор: арфа (main, epik) или фортепиано (tihiy и вступление)
    for a, e, c, sec, b, x in segs:
        if sec == "end":
            continue
        bass, tones = H[c]
        nsteps = int(round((e - a) / (BEAT / 2)))
        if style == "tihiy" or sec == "intro":
            r_ = m(bass) + 12
            while r_ < m("F3"):
                r_ += 12
            pcs = [m(t) % 12 for t in tones]
            up_ = sorted({t for t in range(m("C4"), m("C6")) if t % 12 in pcs})
            pat = [r_, up_[0], up_[1], up_[2], up_[3], up_[2], up_[1], up_[0]]
            vel = 0.15 if sec == "intro" else 0.12 if sec == "verse" else 0.14
            for j in range(nsteps):
                acc = 1.0 if j % 8 == 0 else 0.85 if j % 8 == 4 else 0.68
                bus.add(piano(pat[(j + int(x * 2)) % 8], BEAT * 1.2, vel * acc), a + j * BEAT / 2 + rng.uniform(0, 0.006),
                        pan=-0.2 + 0.06 * (j % 4), send=0.32)
        else:
            mids = [m(t) + 12 for t in tones]
            pat = [mids[0], mids[1], mids[2], mids[0] + 12, mids[1] + 12, mids[2], mids[1], mids[0] + 12]
            v = 0.085 if sec == "verse" else 0.10
            for j in range(nsteps):
                jj = (j + int(x * 2)) % 8
                bus.add(harp(pat[jj], v * (1.0 if jj % 4 == 0 else 0.75)), a + j * BEAT / 2 + rng.uniform(0, 0.008),
                        pan=-0.45 + 0.08 * (jj % 4), send=0.35)
    # ---------- отрывистые струнные: движение (main — со второй половины куплета, epik — всё время)
    for a, e, c, sec, b, x in segs:
        if sec in ("intro", "end") or style == "tihiy":
            continue
        if style == "main" and sec == "verse" and P[b][1] in (0, 1, 2, 3):
            continue
        r_ = m(H[c][0]) + 12
        sub = 4 if (style == "epik" and sec == "climax") else 2
        nsteps = int(round((e - a) / (BEAT / sub)))
        for j in range(nsteps):
            nt = [r_, r_ + 7, r_ + 12, r_ + 7][j % 4] if sub == 4 else (r_ if j % 2 == 0 else r_ + 7)
            v = (0.10 if sec == "verse" else 0.13) * (1.0 if j % sub == 0 else 0.7)
            bus.add(short(nt, v), a + j * BEAT / sub, pan=0.35, send=0.22)
    # ---------- хор (только epik, тихо)
    if style == "epik":
        ch = [(a, e, m(H[c][1][2]) + 12, 0.24) for a, e, c, sec, b, x in segs if sec == "climax"]
        if ch:
            sig, ts = cline(ch, "choir", voices=10, att=1.2, rel=2.0, vowel=VOWEL_A)
            bus.add(sig, ts, pan=0.0, send=0.55, gain=0.45)
    # ---------- ударные
    for b, (ch, mk, sec) in enumerate(P):
        if sec == "end":
            break
        lv = LV[sec]
        if style == "tihiy":
            if sec == "climax":
                bus.add(frame_drum(0.08), bt(b), pan=0.0, send=0.35)
            continue
        v = (0.10, 0.115, 0.19)[lv]
        bus.add(frame_drum(v), bt(b, 0), pan=0.0, send=0.25)
        bus.add(frame_drum(v * 0.6), bt(b, 1.5), pan=0.0, send=0.25)
        bus.add(frame_drum(v * 0.5, low=False), bt(b, 2.5), pan=0.15, send=0.25)
        if sec == "climax":
            bus.add(frame_drum(v * 0.75), bt(b, 2), pan=0.0, send=0.25)
            bus.add(frame_drum(v * 0.35, low=False), bt(b, 3.5), pan=-0.15, send=0.25)
            if style == "epik":
                for x_, tv in ((0, 0.30), (0.75, 0.16), (1.5, 0.2), (2, 0.26), (3, 0.2), (3.5, 0.14)):
                    bus.add(taiko(tv), bt(b, x_), pan=0.0, send=0.35)
        elif style == "epik" and sec == "verse":
            bus.add(taiko(0.14), bt(b, 0), pan=0.0, send=0.35)
            bus.add(taiko(0.10), bt(b, 2), pan=0.0, send=0.35)
        if sec != "intro":
            for j in range(8):
                bus.add(shaker(0.046 if j % 2 == 0 else 0.032), bt(b, j / 2 + 0.02), pan=0.35, send=0.15)
    # подводки и удары
    secs = [s for _, _, s in P]
    for b in range(1, nb):
        if secs[b] == "climax" and secs[b - 1] != "climax":
            if style != "tihiy":
                bus.add(cymbal_swell(BAR * 0.95, 0.10), bt(b - 1) + BAR * 0.05, pan=0.0, send=0.4)
                for k in range(12):
                    bus.add(timp(m("C2"), 0.02 + 0.05 * k / 11, 0.6), bt(b - 1, 2) + k * BEAT * 2 / 12, pan=0.0, send=0.4)
            bus.add(timp(m("F2"), 0.15 if style != "tihiy" else 0.07, 4.0), bt(b), pan=0.0, send=0.4)
    if secs[0] == "climax":           # Shorts «Распев»: сразу с удара, перед ним короткий взлёт тарелки
        bus.add(cymbal_swell(0.7, 0.09), 0.05, pan=0.0, send=0.4)
        bus.add(timp(m("F2"), 0.16, 4.0), bt(0), pan=0.0, send=0.4)
        bus.add(frame_drum(0.2), bt(0), pan=0.0, send=0.3)
    if "climax" in secs and style != "tihiy":
        cb = [b for b in range(nb) if secs[b] == "climax"]
        if len(cb) >= 5:
            bus.add(timp(m("F2"), 0.13, 4.0), bt(cb[4]), pan=0.0, send=0.4)
    if style != "tihiy" and secs[-2] == "climax":
        bus.add(cymbal_swell(BAR * 0.95, 0.08), bt(fin_b - 1) + BAR * 0.05, pan=0.0, send=0.4)
    bus.add(timp(m("F2"), 0.12 if style != "tihiy" else 0.06, 4.5), bt(fin_b), pan=0.0, send=0.45)
    bus.add(frame_drum(0.15 if style != "tihiy" else 0.07), bt(fin_b), pan=0.0, send=0.35)
    # ---------- финал: фортепиано вверх и челеста
    for k, nt in enumerate(["F4", "C5", "G5", "A5", "C6", "F6"]):
        bus.add(piano(m(nt), 4.0, 0.15 - 0.012 * k), bt(fin_b, 0.5 * k + 0.5), pan=0.15, send=0.55)
    for k, nt in enumerate(["C7", "A6", "F6"]):
        bus.add(celesta(m(nt), 0.05), bt(fin_b, 4.2 + k * 0.5), pan=-0.2, send=0.6)
    return bus, end_t


if __name__ == "__main__":
    import time
    style, pl, out = sys.argv[1], sys.argv[2], sys.argv[3]
    t = time.time()
    bus, end_t = compose(style, pl)
    L, R = master(bus)
    cut = int((end_t + (4.5 if pl == "full" else 2.6)) * SR)
    L, R = L[:cut].copy(), R[:cut].copy()
    fo = int(1.5 * SR)
    L[-fo:] *= np.linspace(1, 0, fo) ** 1.5
    R[-fo:] *= np.linspace(1, 0, fo) ** 1.5
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.89, R / pk * 0.89
    st = np.empty(2 * len(L))
    st[0::2], st[1::2] = L, R
    with wave.open(out, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype(np.int16).tobytes())
    print(out, "готово", round(len(L) / SR, 1), "с;", f"{time.time() - t:.0f} с")
