"""Звук для «ведра шариков»: шорох тысяч бусин (тональные «тики», без шума), мягкая подложка ре мажор,
на «пыке» — переливы и аккорд, моргания — «блипы». python3 pour_audio.py out.wav TR TA TEND"""
import math
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve

SR = 44100
OUT = sys.argv[1]
TR, TA, TEND = (float(v) for v in sys.argv[2:5])
st = np.load("pour_stats.npy")                 # (t, moved, spawned, n) по кадрам
rng = np.random.default_rng(11)
n = int((TEND + 0.5) * SR)
L = np.zeros(n); R = np.zeros(n); WET = np.zeros(n)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def cos_in(t, d):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(t / d, 0, 1))


def put(sig, at, pan=0.0, wet=0.2):
    s = int(at * SR)
    if s >= n or s < 0:
        return
    m = min(len(sig), n - s)
    gl, gr = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    L[s:s + m] += sig[:m] * gl * 1.41
    R[s:s + m] += sig[:m] * gr * 1.41
    WET[s:s + m] += sig[:m] * wet


def tick(f, vel, tau=0.013):
    t = np.arange(int(0.09 * SR)) / SR
    return vel * (np.sin(2 * np.pi * f * t) + 0.08 * np.sin(4 * np.pi * f * t + 1)) * np.exp(-t / tau) * cos_in(t, 0.005)


def thump(f, vel):
    t = np.arange(int(0.18 * SR)) / SR
    return vel * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.045) * cos_in(t, 0.006)


def pluck(midi, vel, decay=3.0, dur=1.4):
    f0 = hz(midi)
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for h in range(1, 7):
        if f0 * h > 7000:
            break
        s += (1 / h ** 1.5) * np.sin(2 * np.pi * f0 * h * t + (0 if h == 1 else rng.uniform(0, 6.28))) * np.exp(-t * decay * (0.6 + 0.5 * h))
    return vel * s * cos_in(t, 0.008) * np.clip((dur - t) / 0.05, 0, 1)


def pad(midis, vel, dur, att=0.6, rel=1.5, fmax=3000):
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


def blip(f0, f1, dur, vel):
    t = np.arange(int(dur * SR)) / SR
    f = f0 + (f1 - f0) * t / dur
    return vel * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16) * cos_in(t, 0.008)


# ---------- шорох бусин: частота «тиков» по тому, сколько шариков в движении
PENTA = [74, 76, 78, 81, 83, 86, 88, 90, 93]             # ре мажорная пентатоника, 590–1760 Гц — «стеклянные бусины»
for t, moved, spawned, cnt in st:
    if t >= TR:
        break
    rate = min(300.0, 30 + moved / 9.0)                   # тиков в секунду
    k = rng.poisson(rate / 30.0)
    for _ in range(k):
        at = t + rng.uniform(0, 1 / 30)
        m = PENTA[rng.integers(len(PENTA))]
        put(tick(hz(m) * 2 ** (rng.normal(0, 0.15) / 12), rng.uniform(0.02, 0.055)), at, pan=rng.uniform(-0.7, 0.7), wet=0.12)
    if rng.random() < 0.5 and t > 0.5:                    # глухие удары о кучу
        put(thump(rng.uniform(170, 260), 0.07), t + rng.uniform(0, 1 / 30), pan=rng.uniform(-0.4, 0.4), wet=0.05)
# ---------- бодрый фон: перебор восьмыми ре мажор I–V–vi–IV, 120 уд/мин, нарастает; бас четвертями, лёгкий бочонок
def bass(midi, vel, dur):
    f0 = hz(midi)
    t = np.arange(int((dur + 0.05) * SR)) / SR
    return vel * (np.sin(2 * np.pi * f0 * t) + 0.2 * np.sin(4 * np.pi * f0 * t)) * np.exp(-t * 3) * cos_in(t, 0.006) * np.clip((dur + 0.05 - t) / 0.05, 0, 1)


def kick(vel):
    t = np.arange(int(0.3 * SR)) / SR
    ph = 2 * np.pi * np.cumsum(70 * (1 + 0.8 * np.exp(-t / 0.03))) / SR
    return vel * np.sin(ph) * np.exp(-t / 0.1) * cos_in(t, 0.006)


CH = [[62, 66, 69, 74], [61, 64, 69, 73], [62, 66, 71, 74], [62, 67, 71, 74]]      # D, A, Bm, G (верх)
BS = [50, 45, 47, 43]
E8 = 0.25
i8 = 0
while i8 * E8 < TR - 0.05:
    t0 = i8 * E8
    bar = int(t0 // 2.0) % 4
    pat = [0, 1, 2, 3, 2, 1, 2, 3][i8 % 8]
    grow = min(1.0, t0 / TR)
    put(pluck(CH[bar][pat] + 12, 0.07 + 0.08 * grow, decay=4.0, dur=0.9), t0, pan=-0.3 if i8 % 2 else 0.3, wet=0.25)
    if i8 % 2 == 0:
        put(bass(BS[bar] + 12 if BS[bar] < 45 else BS[bar], 0.10 + 0.08 * grow, E8 * 1.8), t0, wet=0.05)
        if t0 > 3.0:
            put(kick(0.10 + 0.10 * grow), t0, wet=0.02)
    i8 += 1
# ---------- «пык»: переливы вверх и светлый аккорд
for j, m in enumerate([74, 78, 81, 86, 90, 93, 90, 93]):
    put(pluck(m, 0.22, decay=3.0), TR + j * 0.06, pan=-0.5 + j / 7, wet=0.35)
put(pad([50, 57, 62, 66, 69], 0.5, 3.4, att=0.15, rel=2.0, fmax=5000), TR + 0.05, wet=0.4)
for r in (0.5, 2.5, 2.75):
    put(blip(1300, 820, 0.12, 0.2), TA + r, wet=0.2)
put(blip(520, 700, 0.16, 0.15), TA + 1.0, pan=-0.4, wet=0.2)
put(blip(700, 520, 0.16, 0.15), TA + 1.6, pan=0.4, wet=0.2)
for j, m in enumerate((74, 78, 81, 86)):
    put(pluck(m, 0.18, decay=2.0, dur=2.0), TA + 3.0 + 0.08 * j, pan=-0.3 + 0.2 * j, wet=0.35)
# ---------- зал без шумового пола
ir = np.zeros(int(1.3 * SR))
for tp in np.sort(rng.uniform(0.008, 1.2, 900)):
    ir[int(tp * SR)] += rng.choice([-1, 1]) * math.exp(-tp / 0.35)
ir = sosfiltfilt(butter(2, 3500, btype="low", fs=SR, output="sos"), ir)
ir /= np.abs(ir).sum() ** 0.5 * 6
L += fftconvolve(WET, ir)[:n]
R += fftconvolve(WET, np.roll(ir, int(0.011 * SR)))[:n]
hp = butter(2, 60, btype="high", fs=SR, output="sos")
L, R = sosfiltfilt(hp, L), sosfiltfilt(hp, R)
end = int(TEND * SR)
L, R = L[:end], R[:end]
fo = int(0.25 * SR)
L[-fo:] *= np.linspace(1, 0, fo); R[-fo:] *= np.linspace(1, 0, fo)
pk = max(np.abs(L).max(), np.abs(R).max())
x = np.stack([L, R], 1) / pk * 0.89
with wave.open(OUT, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((x * 32767).astype(np.int16).tobytes())
print("звук", round(len(L) / SR, 2), "с")
