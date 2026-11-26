"""Музыкальная шкатулка «Jingle Bells» (мелодия Дж. Пирпонта, 1857 — общественное достояние; исполнение и аранжировка свои).
python3 music_xmas.py out.wav DUR [LAND] [START]
  DUR — длина ролика, с; LAND — когда приходит последняя нота припева («way»), с (по умолчанию DUR − 1,15);
  START — первая нота (у ёлочных шаров — момент удара), до неё тихая дробь бубенцов.
Чистый звук: у каждого звука только нижние призвуки, бубенцы — синусы (не шум), без лимитера."""
import math
import sys
import wave

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, sosfiltfilt, fftconvolve

SR = 44100
OUT = sys.argv[1]
DUR = float(sys.argv[2])
LAND = float(sys.argv[3]) if len(sys.argv) > 3 else DUR - 1.15
START = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
BEAT = (LAND - START) / 12.0                        # три такта по 4 доли до «way»
rng = np.random.default_rng(5)
n = int((DUR + 0.05) * SR)
L = np.zeros(n)
R = np.zeros(n)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def att(t, ms):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(t / (ms / 1000), 0, 1))


def tine(m, vel, ring=2.2):
    """язычок шкатулки: основной тон + высокий призвук 5,4× (быстро гаснет) + лёгкая октава"""
    f = hz(m)
    t = np.arange(int(ring * SR)) / SR
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 2.0)
    s += 0.18 * np.sin(2 * np.pi * 2 * f * t + 0.7) * np.exp(-t * 4.0)
    if f * 5.4 < 9500:
        s += 0.22 * np.sin(2 * np.pi * 5.4 * f * t + 1.3) * np.exp(-t * 14.0)
    s *= att(t, 3) * np.clip((ring - t) / 0.25, 0, 1)
    return vel * s


def pluck(m, vel):
    f = hz(m)
    t = np.arange(int(1.2 * SR)) / SR
    s = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.35) + 0.25 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.15)
    return vel * s * att(t, 8)


def jingle(vel):
    """бубенец: пучок несвязанных высоких синусов, у каждого свой короткий спад и микросдвиг"""
    t = np.arange(int(0.22 * SR)) / SR
    s = np.zeros_like(t)
    for _ in range(9):
        f = rng.uniform(4200, 8200)
        d = rng.uniform(0, 0.012)
        tt = np.clip(t - d, 0, None)
        s += rng.uniform(0.4, 1) * np.sin(2 * np.pi * f * tt + rng.uniform(0, 6.28)) * np.exp(-tt / rng.uniform(0.02, 0.06)) * (t >= d)
    return vel * s / 9 * att(t, 2)


def put(sig, at, pan=0.0):
    i = int(at * SR)
    if i >= n:
        return
    m = min(len(sig), n - i)
    gl, gr = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    L[i:i + m] += sig[:m] * gl * 1.41
    R[i:i + m] += sig[:m] * gr * 1.41


# припев: E E E- | E E E- | E G C. D | E———   (до мажор, шкатулка — 6-я октава)
E, G, C, D = 76, 79, 72, 74
mel = [(0, E, 1), (1, E, 1), (2, E, 2), (4, E, 1), (5, E, 1), (6, E, 2), (8, E, 1), (9, G, 1), (10, C, 1.5), (11.5, D, 0.5), (12, E, 4)]
for b, m, dd in mel:
    v = 0.30 if b not in (0, 4, 8, 12) else 0.36
    put(tine(m + 12, v, ring=1.6 + dd * BEAT), START + b * BEAT + rng.uniform(0, 0.004), pan=0.15)
    put(tine(m, v * 0.45, ring=1.4 + dd * BEAT), START + b * BEAT + 0.003, pan=-0.1)        # октавой ниже — тело
# бас и аккорды шкатулки: C | C | C(F) G7 | C
bass = [(0, 48), (2, 43), (4, 48), (6, 43), (8, 48), (10, 43), (11, 43), (12, 36)]
for b, m in bass:
    put(pluck(m, 0.20), START + b * BEAT, pan=-0.2)
chords = {0: (60, 64, 67), 2: (60, 64, 67), 4: (60, 64, 67), 6: (60, 64, 67), 8: (60, 65, 69), 10: (59, 65, 67), 12: (60, 64, 67, 72)}
for b, ch in chords.items():
    for k, m in enumerate(ch):
        put(tine(m + 12, 0.07, ring=1.2), START + b * BEAT + 0.5 * BEAT + k * 0.012, pan=0.35 - 0.2 * k)
# финальное арпеджио после «way»
for k, m in enumerate((84, 88, 91, 96)):
    put(tine(m, 0.10 - 0.015 * k, ring=1.6), LAND + 0.5 * BEAT + k * BEAT / 3, pan=0.4 - 0.25 * k)
# бубенцы восьмыми, акцент на долях; к концу тише
for at in (START * 0.25, START * 0.5, START * 0.68, START * 0.82, START * 0.93):   # дробь до удара, ускоряется
    if START > 0.15:
        put(jingle(0.025 + 0.02 * at / START), at, pan=rng.uniform(-0.4, 0.4))
for k in range(int(12 * 2) + 2):
    at = START + k * BEAT / 2
    if at > LAND + 0.05:
        break
    put(jingle(0.04 if k % 2 == 0 else 0.022), at + rng.uniform(0, 0.006), pan=rng.uniform(-0.6, 0.6))
put(jingle(0.08), LAND, pan=0.0)

# тёплый зал: короткий хвост
t = np.arange(int(1.6 * SR)) / SR
ir = gaussian_filter1d(rng.normal(0, 1, len(t)), 2.0) * np.exp(-t * 6.9 / 1.1) * np.clip((t - 0.018) / 0.03, 0, 1)
ir /= np.sqrt(np.sum(ir ** 2))
wet = 0.22
L2 = L + wet * fftconvolve(L, ir)[:n]
R2 = R + wet * fftconvolve(R, np.roll(ir, int(0.009 * SR)))[:n]
hp = butter(2, 90, btype="high", fs=SR, output="sos")
L2, R2 = sosfiltfilt(hp, L2), sosfiltfilt(hp, R2)
fade = np.clip((DUR - np.arange(n) / SR) / 0.35, 0, 1)
L2, R2 = L2 * fade, R2 * fade
pk = max(np.abs(L2).max(), np.abs(R2).max()) + 1e-9
x = np.stack([L2, R2], 1) / pk * 0.8
with wave.open(OUT, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((x * 32767).astype(np.int16).tobytes())
print(f"музыка: {DUR:.2f} с, темп {60 / BEAT:.0f} уд/мин, «way» на {LAND:.2f} с")
