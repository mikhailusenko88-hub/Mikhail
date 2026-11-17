"""Своя мелодия «крадущийся круг» для ролика с медведем: минор, каждый круг выше и быстрее, кульминация на 100%,
на «пыке» — светлый мажор. Чистые тембры: у каждого звука несколько нижних призвуков, бас почти чистый тон,
барабаны тональные, шумов нет (правила навыка muzyka-sluh).
python3 music_bear.py out.wav notes.txt   →  wav (сырой, нормализовать enc.py) и времена нот (для рождения шариков)."""
import math
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else "bear_music.wav"
NOTES_OUT = sys.argv[2] if len(sys.argv) > 2 else "bear_notes.txt"
rng = np.random.default_rng(7)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------------- мелодия: восьмые (midi, длина в восьмых)
CYCLE = [(52, 1), (55, 1), (54, 1), (57, 1), (55, 1), (59, 1), (57, 2),
         (60, 1), (59, 1), (57, 1), (55, 1), (54, 1), (51, 1), (52, 2),
         (52, 1), (55, 1), (54, 1), (57, 1), (55, 1), (59, 1), (57, 1), (60, 1),
         (59, 1), (63, 1), (66, 1), (63, 1), (59, 4)]
BASS = [[40, 47, 40, 47], [45, 47, 40, 40], [40, 47, 40, 45], [47, 47, 47, 47]]   # четверти по тактам
assert sum(d for _, d in CYCLE) == 32
MEL = [(m + 12, d, 0) for m, d in CYCLE] + [(m + 24, d, 1) for m, d in CYCLE]   # выше на октаву: светлее
N8 = 64
D0, D1 = 0.26, 0.105                                   # длина восьмой: в начале и в конце (ускорение)
d8 = [D0 * (D1 / D0) ** (i / (N8 - 1)) for i in range(N8)]
t8 = np.concatenate([[0.0], np.cumsum(d8)])            # время начала каждой восьмой
T_FULL = float(t8[-1])                                 # конец второго круга = 100%
TOTAL = T_FULL + 6.0
n = int(TOTAL * SR)
L = np.zeros(n)
R = np.zeros(n)
WET = np.zeros(n)


def cos_in(t, d):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(t / d, 0, 1))


def put(sig, at, pan=0.0, wet=0.2):
    s = int(at * SR)
    if s >= n:
        return
    m = min(len(sig), n - s)
    gl, gr = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    L[s:s + m] += sig[:m] * gl * 1.41
    R[s:s + m] += sig[:m] * gr * 1.41
    WET[s:s + m] += sig[:m] * wet


def pluck(midi, vel, decay=4.0, bright=1.0, dur=1.2):
    """щипок: 6 нижних призвуков, верхние гаснут быстрее; атака 8 мс (как harp в chisto)"""
    f0 = hz(midi)
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for h in range(1, 9):
        if f0 * h > 7000:
            break
        a = (1 / h ** (1.7 - 0.5 * bright))
        s += a * np.sin(2 * np.pi * f0 * h * t + (0 if h == 1 else rng.uniform(0, 6.28))) * np.exp(-t * decay * (0.6 + 0.5 * h))
    return vel * s * cos_in(t, 0.008) * np.clip((dur - t) / 0.05, 0, 1)


def bass(midi, vel, dur):
    f0 = hz(midi)
    t = np.arange(int((dur + 0.06) * SR)) / SR
    s = np.sin(2 * np.pi * f0 * t) + 0.22 * np.sin(4 * np.pi * f0 * t + 0.7) + 0.06 * np.sin(6 * np.pi * f0 * t + 1.3)
    env = cos_in(t, 0.006) * np.exp(-t * 2.5) * np.clip((dur + 0.06 - t) / 0.06, 0, 1)
    return vel * s * env


def kick(vel):
    t = np.arange(int(0.35 * SR)) / SR
    f = 66 * (1 + 0.9 * np.exp(-t / 0.03))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return vel * (np.sin(ph) * np.exp(-t / 0.11) + 0.25 * np.sin(2 * ph) * np.exp(-t / 0.05)) * cos_in(t, 0.006)


def tom(midi, vel):
    f0 = hz(midi)
    t = np.arange(int(0.4 * SR)) / SR
    f = f0 * (1 + 0.25 * np.exp(-t / 0.04))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return vel * (np.sin(ph) + 0.3 * np.sin(1.5 * ph + 1)) * np.exp(-t / 0.12) * cos_in(t, 0.006)


def pad(midis, vel, dur, att=0.02, rel=1.6, fmax=2600):
    """чистая подложка: 4 призвука, 2 голоса с расстройкой ±4 цента"""
    t = np.arange(int((dur + rel) * SR)) / SR
    s = np.zeros_like(t)
    for m in midis:
        for det in (-4, 4):
            f0 = hz(m) * 2 ** (det / 1200)
            for h in range(1, 5):
                if f0 * h > fmax:
                    break
                s += (0.5 / h ** 1.3) * np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 6.28))
    env = cos_in(t, att) * np.where(t < dur, 1.0, np.exp(-(t - dur) / (rel / 3)))
    return vel * s * env / (len(midis) * 2)


notes_t = []
# ---------------- мелодия
k = 0
for m, d, cyc in MEL:
    at = t8[k]
    notes_t.append(at)
    prog = k / N8
    v = 0.30 + 0.25 * prog
    put(pluck(m, v, decay=5.0 + 4 * prog, bright=0.6 + 0.6 * cyc), at, pan=-0.05, wet=0.18)
    if cyc == 1:
        put(pluck(m - 12, v * 0.55, decay=6.0, bright=0.4), at, pan=0.15, wet=0.15)   # удвоение октавой ниже
    k += d
# ---------------- бас четвертями (2 восьмые), барабаны во втором круге
for bar in range(8):
    for q in range(4):
        i = bar * 8 + q * 2
        at, dur = t8[i], t8[i + 2] - t8[i]
        cyc = bar // 4
        put(bass(BASS[bar % 4][q], 0.28 + 0.08 * cyc, dur * 0.9), at, pan=0.0, wet=0.05)
        if cyc == 1:
            put(kick(0.55 + 0.1 * (bar - 4) / 3), at, wet=0.03)
        if bar == 7:                                     # последний такт: томы восьмыми вверх
            for j, mm in enumerate((45, 47, 50, 52) if q < 2 else (52, 55, 57, 59)):
                pass
    if bar == 7:
        for j in range(8):
            put(tom(43 + 2 * j, 0.32), t8[bar * 8 + j], pan=-0.3 + 0.08 * j, wet=0.12)
# ---------------- кульминация на 100%: ми-минорный удар
hit = T_FULL
put(kick(0.9), hit, wet=0.1)
put(bass(40, 0.6, 0.9), hit, wet=0.1)
put(pad([52, 56, 59, 64, 68], 0.85, 0.35, att=0.008, rel=0.9), hit, wet=0.35)   # мажор уже на ударе
for j, m in enumerate((76, 80, 83, 88)):
    put(pluck(m, 0.3, decay=3.0, bright=1.0, dur=1.5), hit + 0.012 * j, pan=-0.3 + 0.2 * j, wet=0.3)
# ---------------- «пык» (через 0,45 с): мажорная волна вверх и светлая подложка
pyk = T_FULL + 0.45
arp = [64, 68, 71, 76, 80, 83, 88, 92]
for j, m in enumerate(arp):
    put(pluck(m, 0.24, decay=3.2, bright=1.0, dur=1.6), pyk + j * 0.055, pan=-0.5 + j / 7, wet=0.35)
put(pad([52, 56, 59, 64, 68, 71], 0.55, 3.6, att=0.25, rel=2.0, fmax=5000), pyk + 0.05, wet=0.4)
for j in range(10):                                   # «искры» сверху
    put(pluck([88, 92, 95, 100][j % 4], 0.09, decay=4.0, dur=1.0), pyk + 0.5 + j * 0.13, pan=-0.6 + 0.13 * j, wet=0.5)
put(bass(40, 0.35, 3.0), pyk + 0.05, wet=0.1)


# ---------------- моргания и взгляды (как в ролике): чистые «блипы»
def blip(f0, f1, dur, vel):
    t = np.arange(int(dur * SR)) / SR
    f = f0 + (f1 - f0) * t / dur
    return vel * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16) * cos_in(t, 0.008)


TA = T_FULL + 0.45 + 0.9
for r in (0.5, 2.5, 2.75):
    put(blip(1300, 820, 0.12, 0.22), TA + r, wet=0.2)
put(blip(520, 700, 0.16, 0.16), TA + 1.0, pan=-0.4, wet=0.2)
put(blip(700, 520, 0.16, 0.16), TA + 1.6, pan=0.4, wet=0.2)
for j, m in enumerate((64, 68, 71, 76)):
    put(pluck(m, 0.2, decay=2.0, dur=2.0), TA + 3.0 + 0.08 * j, pan=-0.3 + 0.2 * j, wet=0.35)

# ---------------- зал: короткий затухающий отклик без шумового «пола» (IR — сумма редких отражений)
ir_n = int(1.4 * SR)
ir = np.zeros(ir_n)
taps = np.sort(rng.uniform(0.008, 1.3, 900))
for tp in taps:
    ir[int(tp * SR)] += rng.choice([-1, 1]) * math.exp(-tp / 0.38)
lp = butter(2, 3500, btype="low", fs=SR, output="sos")
ir = sosfiltfilt(lp, ir)
ir /= np.abs(ir).sum() ** 0.5 * 6
rev = fftconvolve(WET, ir)[:n]
irR = np.roll(ir, int(0.011 * SR))
revR = fftconvolve(WET, irR)[:n]
L += rev
R += revR
hp = butter(2, 60, btype="high", fs=SR, output="sos")
L, R = sosfiltfilt(hp, L), sosfiltfilt(hp, R)
end = int((TA + 4.3) * SR)
L, R = L[:end], R[:end]
fo = int(0.25 * SR)
L[-fo:] *= np.linspace(1, 0, fo)
R[-fo:] *= np.linspace(1, 0, fo)
pk = max(np.abs(L).max(), np.abs(R).max())
st = np.stack([L, R], 1) / pk * 0.89
with wave.open(OUT, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((st * 32767).astype(np.int16).tobytes())
open(NOTES_OUT, "w").write("\n".join(f"{x:.4f}" for x in notes_t) + "\n")
print(f"T_FULL {T_FULL:.2f}  длина {len(L) / SR:.2f} c  нот {len(notes_t)}")
