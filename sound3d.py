"""Звук из физики: каждый удар шара (резкая смена скорости между кадрами) — короткий модальный «стук» нужной силы,
панорама по положению. О стекло — звонче, о шары — сухой щелчок, о пол/кучу — глуше. Без шумов (чистые затухающие моды).
python3 sound3d.py pos.npz out.wav [начало_с] [длина_с]"""
import math
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve

SR = 44100
d = np.load(sys.argv[1])
pos = d["pos"].astype(np.float32)          # кадры × шары × 3
FPS = int(d["fps"])
GW, GD, GH, T = (float(v) for v in d["glass"])
OUT = sys.argv[2]
T0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
DUR = float(sys.argv[4]) if len(sys.argv) > 4 else pos.shape[0] / FPS - T0
rng = np.random.default_rng(3)
n = int((DUR + 0.6) * SR)
L = np.zeros(n); R = np.zeros(n)

vel = np.diff(pos, axis=0) * FPS                      # скорость между кадрами
dv = np.diff(vel, axis=0)                             # изменение скорости
dv[..., 2] += 9.81 / FPS                              # убрать вклад тяжести
J = np.linalg.norm(dv, axis=2)                        # «удар» в кадре f+1
P = pos[2:]                                           # где был шар в момент удара
TH = 0.35                                             # порог удара, м/с


def modal(freqs, amps, taus, vel, dur=0.12):
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for f, a, tau in zip(freqs, amps, taus):
        s += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    att = np.clip(t / 0.0015, 0, 1)                   # 1,5 мс — без щелчка ступенькой
    return vel * s * att


# заготовки звуков (по 12 вариантов, чтобы не звучало одинаково)
def bank(kind):
    out = []
    for _ in range(12):
        k = 2 ** rng.normal(0, 0.12)
        if kind == "glass":     # шар о стекло: звонко
            f0 = 1900 * k
            out.append(modal([f0, f0 * 1.61, f0 * 2.13], [1.0, 0.45, 0.2], [0.018, 0.010, 0.006], 1.0, 0.09))
        elif kind == "ball":    # шар о шар: сухой щелчок
            f0 = 2600 * k
            out.append(modal([f0, f0 * 1.37], [1.0, 0.35], [0.006, 0.004], 1.0, 0.04))
        else:                   # пол и куча: глуше
            f0 = 950 * k
            out.append(modal([f0, f0 * 1.9, 320 * k], [0.8, 0.25, 0.5], [0.008, 0.005, 0.012], 1.0, 0.05))
    return out


B = {k: bank(k) for k in ("glass", "ball", "floor")}
lp = butter(2, 5200, btype="low", fs=SR, output="sos")
B = {k: [sosfiltfilt(lp, s) for s in v] for k, v in B.items()}

f_from = int(T0 * FPS)
f_to = min(J.shape[0], int((T0 + DUR) * FPS))
total = 0
for f in range(f_from, f_to):
    idx = np.where(J[f] > TH)[0]
    if not len(idx):
        continue
    if len(idx) > 140:                                # слишком много — берём часть, громкость по числу
        keep = rng.choice(idx, 140, replace=False)
        gain = math.sqrt(len(idx) / 140)
    else:
        keep, gain = idx, 1.0
    for i in keep:
        x, y, z = P[f, i]
        j = min(J[f, i], 4.0)
        near_wall = (abs(abs(x) - GW / 2) < 0.02 or abs(abs(y) - GD / 2) < 0.02) and z < GH + T + 0.01 and abs(x) < GW / 2 + 0.03
        if near_wall:
            kind = "glass"
        elif z < 0.03 and (abs(x) > GW / 2 + 0.02 or abs(y) > GD / 2 + 0.02):
            kind = "floor"
        else:
            kind = "ball" if rng.random() < 0.75 else "floor"
        s = B[kind][rng.integers(12)]
        v = 0.045 * (j / 2.0) ** 0.8 * gain
        at = (f + 2 - f_from) / FPS + rng.uniform(0, 1 / FPS)
        si = int(at * SR)
        if si >= n:
            continue
        pan = float(np.clip(x / 0.35, -1, 1))
        gl, gr = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        m = min(len(s), n - si)
        L[si:si + m] += s[:m] * v * gl * 1.41
        R[si:si + m] += s[:m] * v * gr * 1.41
        total += 1
# маленькая комната: редкие отражения
ir = np.zeros(int(0.5 * SR))
for tp in np.sort(rng.uniform(0.004, 0.45, 400)):
    ir[int(tp * SR)] += rng.choice([-1, 1]) * math.exp(-tp / 0.09)
ir = sosfiltfilt(butter(2, 4000, btype="low", fs=SR, output="sos"), ir)
ir /= np.abs(ir).sum() ** 0.5 * 8
L2 = L + fftconvolve(L, ir)[:n] * 0.6
R2 = R + fftconvolve(R, np.roll(ir, int(0.007 * SR)))[:n] * 0.6
hp = butter(2, 70, btype="high", fs=SR, output="sos")
L2, R2 = sosfiltfilt(hp, L2), sosfiltfilt(hp, R2)
L2, R2 = L2[:int(DUR * SR)], R2[:int(DUR * SR)]
pk = max(np.abs(L2).max(), np.abs(R2).max()) + 1e-9
x = np.stack([L2, R2], 1) / pk * 0.89
with wave.open(OUT, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((x * 32767).astype(np.int16).tobytes())
print("ударов озвучено:", total, "длина", round(DUR, 2), "с")
