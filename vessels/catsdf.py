"""SDF стеклянной банки-кота (м): сидит на полу z=0, смотрит на камеру (−y), голова сверху открыта (OPEN_*), уши полые.
sdf(P) — P: (...,3) → расстояние (<0 внутри полости)."""
import numpy as np

def ell(p, c, r):
    k0 = np.linalg.norm((p - c) / r, axis=-1)
    k1 = np.linalg.norm((p - c) / (np.asarray(r) ** 2), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)

def rcone(p, a, b, r1, r2):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ba = b - a; l2 = ba @ ba; rr = r1 - r2; a2 = l2 - rr * rr; il2 = 1.0 / l2
    pa = p - a; y = pa @ ba; z = y - l2
    xv = pa * l2 - y[..., None] * ba
    x2 = np.sum(xv * xv, -1); y2 = y * y * l2; z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    out = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    m1 = np.sign(z) * a2 * z2 > k
    m2 = np.sign(y) * a2 * y2 < k
    out = np.where(m1, np.sqrt(x2 + z2) * il2 - r2, out)
    return np.where(m2 & ~m1, np.sqrt(x2 + y2) * il2 - r1, out)

def capsule(p, a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float)
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return np.linalg.norm(pa - h[..., None] * ba, axis=-1) - r

def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)

import os
K = float(os.environ.get("CAT_K", "0.86"))     # масштаб (вместимость)
HEAD_C = np.array([0.0, -0.012, 0.300]) * K
HEAD_R = np.array([0.084, 0.074, 0.068]) * K
OPEN_C = HEAD_C[:2]                         # отверстие: цилиндр по оси головы
OPEN_R = 0.050 * K
OPEN_Z = HEAD_C[2]                          # грани выше этого и внутри цилиндра убираются

def cat(p):
    p = p / K
    d = ell(p, [0, 0.012, 0.092], [0.098, 0.088, 0.100])
    d = smin(d, ell(p, [0, 0.000, 0.175], [0.072, 0.066, 0.085]), 0.04)
    d = smin(d, ell(p, HEAD_C / K, HEAD_R / K), 0.035)
    for sx in (-1, 1):
        d = smin(d, rcone(p, [sx * 0.060, -0.014, 0.318], [sx * 0.086, -0.020, 0.420], 0.030, 0.008), 0.012)
        d = smin(d, ell(p, [sx * 0.040, -0.072, 0.026], [0.030, 0.042, 0.026]), 0.02)
        d = smin(d, ell(p, [sx * 0.072, 0.020, 0.040], [0.034, 0.055, 0.040]), 0.03)
    tail = capsule(p, [0.06, 0.085, 0.024], [0.125, 0.020, 0.024], 0.022)
    tail = smin(tail, capsule(p, [0.125, 0.020, 0.024], [0.105, -0.075, 0.024], 0.021), 0.01)
    d = smin(d, tail, 0.025)
    d = np.maximum(d, -p[..., 2])
    return d * K

def sdf(P):
    return cat(np.asarray(P, float))

def in_open(c):
    """грани крышки: центр внутри цилиндра отверстия и выше OPEN_Z"""
    return (np.hypot(c[..., 0] - OPEN_C[0], c[..., 1] - OPEN_C[1]) < OPEN_R) & (c[..., 2] > OPEN_Z)
