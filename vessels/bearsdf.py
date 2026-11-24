"""SDF стеклянной банки-мишки (м): сидит на полу z=0, смотрит на камеру (−y), макушка открыта, круглые уши полые.
sdf(P) — P: (...,3) → расстояние (<0 внутри полости). Форма «плюшевый мишка»: круглая голова, уши-шары, морда, лапы вперёд."""
import numpy as np
from catsdf import ell, capsule, smin

import os
K = float(os.environ.get("BEAR_K", "0.84"))   # масштаб (вместимость)
HEAD_C = np.array([0.0, -0.008, 0.268]) * K
OPEN_C = HEAD_C[:2]
OPEN_RX = float(os.environ.get("BEAR_ORX", "0.049")) * K   # отверстие — овал между ушами, вытянут вперёд-назад (ловит больше струи)
OPEN_RY = float(os.environ.get("BEAR_ORY", "0.049")) * K
OPEN_R = OPEN_RX
OPEN_Z = HEAD_C[2]


def bear(p):
    p = p / K
    d = ell(p, [0, 0.008, 0.105], [0.104, 0.092, 0.118])                    # туловище
    d = smin(d, ell(p, HEAD_C / K, [0.090, 0.080, 0.078]), 0.030)           # голова
    d = smin(d, ell(p, [0, -0.074, 0.250], [0.040, 0.034, 0.030]), 0.018)   # морда
    for sx in (-1, 1):
        d = smin(d, ell(p, [sx * 0.087, -0.004, 0.331], [0.034, 0.026, 0.034]), 0.010)          # уши
        d = smin(d, capsule(p, [sx * 0.086, -0.012, 0.185], [sx * 0.124, -0.060, 0.118], 0.030), 0.022)   # передние лапы
        d = smin(d, capsule(p, [sx * 0.062, -0.030, 0.042], [sx * 0.092, -0.108, 0.040], 0.038), 0.025)   # задние лапы
        d = smin(d, ell(p, [sx * 0.094, -0.128, 0.046], [0.040, 0.026, 0.044]), 0.014)          # ступни к камере
    d = np.maximum(d, -p[..., 2])
    return d * K


def sdf(P):
    return bear(np.asarray(P, float))


def in_open(c):
    return ((((c[..., 0] - OPEN_C[0]) / OPEN_RX) ** 2 + ((c[..., 1] - OPEN_C[1]) / OPEN_RY) ** 2) < 1) & (c[..., 2] > OPEN_Z)
