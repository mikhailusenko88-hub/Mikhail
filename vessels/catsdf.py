"""SDF стеклянного сидящего кота (м). Смотрит на камеру (−y), сидит на полу z=0.
sdf(P) — P: (...,3) → расстояние (<0 внутри полости)."""
import numpy as np

def ell(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm((p - c) / (np.asarray(r) ** 2), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)

def rcone(p, a, b, r1, r2):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ba = b - a
    l2 = ba @ ba
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - y[..., None] * ba
    x2 = np.sum(xv * xv, -1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    out = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    m1 = np.sign(z) * a2 * z2 > k
    m2 = np.sign(y) * a2 * y2 < k
    out = np.where(m1, np.sqrt(x2 + z2) * il2 - r2, out)
    out = np.where(m2 & ~m1, np.sqrt(x2 + y2) * il2 - r1, out)
    return out

def capsule(p, a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float)
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return np.linalg.norm(pa - h[..., None] * ba, axis=-1) - r

def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)

# ---- размеры
S = 1.0
HEAD_C = np.array([0.0, -0.012, 0.300])
MOUTH_R = 0.045          # внутренний радиус горлышка
MOUTH_C = np.array([0.0, 0.045, 0.0])   # горлышко на затылке (x, y), высота ниже
MOUTH_Z0, MOUTH_Z1 = 0.33, 0.385       # от головы вверх до среза

def cat(p):
    d = ell(p, [0, 0.012, 0.092], [0.098, 0.088, 0.100])                 # низ туловища (сидит)
    d = smin(d, ell(p, [0, 0.000, 0.175], [0.072, 0.066, 0.085]), 0.04)  # грудь
    d = smin(d, ell(p, HEAD_C, [0.082, 0.072, 0.068]), 0.035)           # голова
    for sx in (-1, 1):
        d = smin(d, rcone(p, [sx * 0.052, -0.014, 0.330], [sx * 0.078, -0.020, 0.432], 0.034, 0.008), 0.012)   # уши
        d = smin(d, ell(p, [sx * 0.040, -0.072, 0.026], [0.030, 0.042, 0.026]), 0.02)      # передние лапы
        d = smin(d, ell(p, [sx * 0.072, 0.020, 0.040], [0.034, 0.055, 0.040]), 0.03)      # задние лапы
    # хвост вдоль пола вокруг лап
    tail = capsule(p, [0.06, 0.085, 0.024], [0.125, 0.020, 0.024], 0.022)
    tail = smin(tail, capsule(p, [0.125, 0.020, 0.024], [0.105, -0.075, 0.024], 0.021), 0.01)
    d = smin(d, tail, 0.025)
    # горлышко на затылке
    q = p - np.array([MOUTH_C[0], MOUTH_C[1], 0])
    rxy = np.linalg.norm(q[..., :2], axis=-1) - MOUTH_R
    neck = np.maximum(rxy, np.maximum(MOUTH_Z0 - 0.06 - p[..., 2], p[..., 2] - MOUTH_Z1))
    d = smin(d, neck, 0.012)
    d = np.maximum(d, -p[..., 2])          # низ — пол
    return d

def sdf(P):
    return cat(np.asarray(P, float))
