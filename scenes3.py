# -*- coding: utf-8 -*-
"""Новые акварельные сцены (третий месяц, январь–февраль): зимний Тянь-Шань, замёрзшее озеро, снегири на рябине,
фонарь в снегопад, лунный лес, одинокое дерево на закате, кони в зимней степи, морозное окно, подснежники.
Подключаются в quotecard.SCENES при импорте (в конце quotecard.py, после scenes2)."""
import math
import random

import numpy as np

import quotecard as qc
from quotecard import Bloom, Dots, Stroke, Wash, bare_tree, birds, sky, spruce_row, stars, sun, water
from scenes2 import hills, snow_tree, small_house, _clipped


def _sizes(box, hor):
    px0, px1, py0, py1 = box
    return px1 - px0, hor - py0, py1 - hor, px0 + (px1 - px0) / 2


def ell(cx, cy, a, b, rot=0.0, n=30, t0=0.0, t1=2 * math.pi):
    out = []
    for t in np.linspace(t0, t1, n, endpoint=(t1 - t0) < 2 * math.pi - 1e-6):
        x, y = a * math.cos(t), b * math.sin(t)
        out.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
    return out


def snow_field(ops, t0, box, hor, base_col=((0.88, 0.90, 0.97), (0.80, 0.85, 0.95)), shade=(0.70, 0.77, 0.92), seed=0, bands=4, dens=0.26):
    """Снежное поле: прозрачная подложка + мягкие голубые волны-тени."""
    px0, px1, py0, py1 = box
    ops.append(Wash(t0, 1.1, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], list(base_col), dens=dens, blur=4, rough=0.18, seed=seed, streak=0.2, edge=0.12))
    Hg = py1 - hor
    for j in range(bands):
        yv = hor + Hg * (0.08 + 0.24 * j)
        if yv > py1 - 15:
            break
        hh = Hg * (0.07 + 0.04 * j)
        ys = min(py1, yv + hh)
        poly = [(px0 + k * (px1 - px0) / 7, yv + (8 + 4 * j) * math.sin(k * 1.6 + j + seed)) for k in range(8)] + \
               [(px1 - k * (px1 - px0) / 7, ys + 8 * math.cos(k * 1.2 + j)) for k in range(8)]
        ops.append(Wash(t0 + 0.3 + j * 0.25, 0.8, poly, [shade], dens=0.15, blur=9, rough=0.25, direction="right", seed=seed + 10 + j, streak=0.3, edge=0.04))
    return t0 + 0.3 + bands * 0.25 + 0.8


# ------------------------------------------------------------------ зимний Тянь-Шань на рассвете
def snow_range(ops, t0, box, hor, base, peaks_def, Hs, seed=0, cols=((0.99, 0.90, 0.90), (0.92, 0.86, 0.94), (0.78, 0.78, 0.92)), shade=(0.52, 0.56, 0.82),
               dens=0.58, shade_dens=0.45, n=240):
    """Снежный хребет: зубчатый гребень, освещённые склоны слева, синие теневые грани справа, скальные рёбра."""
    px0, px1, py0, py1 = box
    r = random.Random(seed)
    mx = np.linspace(px0 - 10, px1 + 10, n)
    env = np.zeros_like(mx)
    for c, a, w in peaks_def:
        env = np.maximum(env, a * Hs * np.maximum(0, 1 - np.abs(mx - c) / w) ** 1.05)
    det = np.zeros_like(mx)
    for k in range(6):
        per = 90 / 1.8 ** k
        det += (0.55 / 1.7 ** k) * np.sin(mx / per + r.uniform(0, 6.28)) * (0.6 + 0.4 * np.sin(mx / (per * 2.7) + r.uniform(0, 6.28)))
    ridge_y = base - env * (1 + 0.16 * det) - 9 * np.abs(det)
    ridge_y = np.maximum(ridge_y, py0 + 12)
    hills(ops, t0, box, hor, ridge_y, mx, list(cols), dens=dens, seed=seed + 1, blur=1.2, edge=0.35)
    h = base - ridge_y
    t = t0 + 1.1
    # вершины — локальные максимумы высоты; долины — минимумы между ними
    tops = [i for i in range(3, n - 3) if h[i] == h[i - 3:i + 4].max() and h[i] > 0.22 * Hs]
    tops2 = []
    for i in tops:
        if not tops2 or i - tops2[-1] > n * 0.07:
            tops2.append(i)
        elif h[i] > h[tops2[-1]]:
            tops2[-1] = i
    for j, ip in enumerate(tops2):
        nxt = tops2[j + 1] if j + 1 < len(tops2) else n - 1
        iv = ip + 1 + int(np.argmin(h[ip + 1:nxt + 1])) if nxt > ip + 1 else n - 1
        if iv - ip < 3:
            continue
        top = (mx[ip], ridge_y[ip])
        span = mx[iv] - mx[ip]
        right = [(x, y + 2) for x, y in zip(mx[ip:iv + 1], ridge_y[ip:iv + 1])]
        bot = base + 4
        sx0 = mx[ip] + 0.22 * span
        spur = []
        for k in range(7):
            u = k / 6
            y = bot - (bot - top[1]) * u
            x = sx0 + (top[0] - sx0) * u + (r.uniform(-1, 1) * 0.06 * span if 0 < k < 6 else 0)
            spur.append((x, y))
        poly = right + [(sx0 + (mx[iv] - sx0) * 0.45, bot)] + spur[1:]
        ops.append(Wash(t, 0.8, poly, [shade, tuple(min(1, c + 0.08) for c in shade)], dens=shade_dens, blur=1.5, rough=0.14, direction="down", seed=seed + 10 + j, edge=0.12))
        for k in range(4):
            u = r.uniform(0.15, 0.85)
            i = ip + int(u * (iv - ip))
            x, y = mx[i], ridge_y[i] + 6
            ln = (bot - y) * r.uniform(0.25, 0.5)
            ops.append(Stroke(t + 0.4 + k * 0.06, 0.3, [(x, y), (x - ln * 0.25, y + ln * 0.5), (x - ln * 0.35, y + ln)], [3, 2.4, 1.4], tuple(c * 0.75 for c in shade),
                              dens=0.35, blur=0.8, seed=seed + 40 + 5 * j + k))
        t += 0.3
    return ridge_y, mx, t


def scene_tianshan_winter(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.40, 0.50, 0.82), (0.74, 0.72, 0.90), (0.99, 0.84, 0.78)], dens=0.66, seed=4001 + seed)
    ops.append(Bloom(t0 + 1.2, px0 + Wd * 0.22, hor - Hs * 0.25, Hs * 0.55, (1.0, 0.86, 0.72), dens=0.28, dur=1.6, seed=4002, kind="over", soft=3.0).clip_to(px0, py0, px1, hor))
    base = hor - 0.12 * Hs
    peaks_def = [(px0 + Wd * 0.04, 0.30, 150), (px0 + Wd * 0.20, 0.44, 200), (px0 + Wd * 0.33, 0.36, 150), (px0 + Wd * 0.50, 0.72, 250), (px0 + Wd * 0.66, 0.48, 170),
                 (px0 + Wd * 0.82, 0.58, 210), (px0 + Wd * 1.0, 0.40, 170)]
    ridge_y, mx, t = snow_range(ops, t0 + 2.0, box, hor, base, peaks_def, Hs, seed=4003 + seed)
    # предгорья с ельником (синие, в дымке)
    r = random.Random(4029 + seed)
    ph = r.uniform(0, 6.28)
    mid = base + 0.03 * Hs - 0.10 * Hs * np.abs(np.sin(mx / 90 + ph)) - 0.03 * Hs * np.sin(mx / 31 + ph)
    ops.append(Wash(t + 0.2, 1.0, list(zip(mx, mid)) + [(px1 + 10, hor + 4), (px0 - 10, hor + 4)], [(0.46, 0.52, 0.76), (0.38, 0.44, 0.68)], dens=0.62, blur=1.6, rough=0.1,
                    direction="right", seed=4030, edge=0.3))
    spruce_row(ops, t + 1.2, box, hor + 2, (0.22, 0.30, 0.46), hmin=22, hmax=60, step=12, seed=4031, dens=0.75, dur=1.2)
    ops.append(Wash(t + 2.0, 0.9, [(px0, hor - 22), (px1, hor - 22), (px1, hor + 8), (px0, hor + 8)], [(0.96, 0.92, 0.96)], dens=0.34, blur=10, rough=0.3, direction="right",
                    seed=4032, kind="over", edge=0.0))
    t = snow_field(ops, t + 2.3, box, hor, base_col=((0.84, 0.86, 0.96), (0.78, 0.82, 0.94)), dens=0.32, seed=4040)
    # передний план: заснеженные ели по краям (уходят за рамку)
    tt = t - 0.6
    for j, (fx, fy, fh_) in enumerate(((0.03, 0.88, 0.70), (0.14, 0.72, 0.46), (0.86, 0.66, 0.40), (0.97, 0.92, 0.78))):
        x = px0 + Wd * fx
        b = min(py1 + 10, hor + Hg * fy)
        h = Hg * fh_ + 30
        tt = snow_tree(ops, tt, x, b, h, col=(0.12, 0.28, 0.30), seed=4060 + 50 * j) - 0.6
    end = birds(ops, tt + 0.6, [(px0 + Wd * 0.62, py0 + Hs * 0.16, 10), (px0 + Wd * 0.67, py0 + Hs * 0.20, 8)], col=(0.44, 0.40, 0.52))
    return ops, end, "snow"


# ------------------------------------------------------------------ замёрзшее озеро, низкое солнце
def scene_frozen_lake(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.66, 0.74, 0.90), (0.90, 0.88, 0.88), (0.99, 0.88, 0.70)], dens=0.6, seed=4101 + seed)
    sx, sy = px0 + Wd * 0.62, hor - Hs * 0.22
    sun(ops, t0 + 1.4, sx, sy, r=28, halo=Hs * 0.55, col=(1.0, 0.98, 0.90), hcol=(1.0, 0.90, 0.68), seed=4102)
    ops.append(Wash(t0 + 1.9, 1.0, ell(px0 + Wd * 0.26, py0 + Hs * 0.28, Wd * 0.20, Hs * 0.035), [(0.99, 0.97, 0.94)], dens=0.55, blur=6, rough=0.3, direction="right", seed=4103,
                    kind="over", edge=0.0))
    mx = np.linspace(px0 - 10, px1 + 10, 120)
    far = hor - 0.13 * Hs - 0.10 * Hs * np.abs(np.sin(mx / 120 + 0.7 + seed)) - 0.03 * Hs * np.sin(mx / 37)
    hills(ops, t0 + 2.4, box, hor, far, mx, [(0.72, 0.70, 0.86), (0.64, 0.64, 0.82)], dens=0.5, seed=4104, blur=2.0)
    spruce_row(ops, t0 + 3.0, box, hor + 2, (0.40, 0.44, 0.62), hmin=18, hmax=58, step=11, seed=4105, dens=0.66, dur=1.2)
    # лёд: холодная голубизна, к берегу светлее
    water(ops, t0 + 3.9, box, hor, [(0.78, 0.86, 0.94), (0.70, 0.80, 0.92), (0.84, 0.88, 0.96)], dens=0.42, seed=4106, streak=0.45, edge=0.15)
    # солнечная дорожка на льду
    for j in range(9):
        yv = hor + 10 + j * Hg * 0.07
        if yv > py1 - 30:
            break
        hw = 12 + j * 9
        ops.append(Stroke(t0 + 4.8 + j * 0.06, 0.3, [(sx - hw, yv), (sx + hw, yv)], [5 + j * 0.6], (1.0, 0.94, 0.78), dens=0.5 - j * 0.03, blur=2.5, kind="over", seed=4110 + j))
    # трещины во льду
    r = random.Random(4120 + seed)
    for j in range(5):
        x = px0 + Wd * r.uniform(0.08, 0.92)
        y = hor + Hg * r.uniform(0.25, 0.75)
        pts = [(x, y)]
        for k in range(5):
            x += r.uniform(14, 34) * (1 if j % 2 else -1)
            y += r.uniform(-8, 10)
            pts.append((x, y))
        ops.append(Stroke(t0 + 5.5 + j * 0.1, 0.4, pts, [1.6], (0.56, 0.64, 0.80), dens=0.5, blur=0.5, seed=4130 + j))
        ops.append(Stroke(t0 + 5.6 + j * 0.1, 0.4, [(a, b + 2) for a, b in pts], [1.4], (1.0, 1.0, 1.0), dens=0.6, blur=0.5, kind="over", seed=4140 + j))
    # снежные языки на льду
    for j in range(4):
        x = px0 + Wd * r.uniform(0.0, 0.8)
        y = hor + Hg * r.uniform(0.2, 0.7)
        ln = Wd * r.uniform(0.18, 0.32)
        poly = [(x, y), (x + ln * 0.3, y - 6), (x + ln, y - 2), (x + ln * 0.8, y + 9), (x + ln * 0.2, y + 8)]
        ops.append(Wash(t0 + 6.2 + j * 0.15, 0.5, poly, [(0.99, 0.99, 1.0)], dens=0.7, blur=3, rough=0.3, direction="right", seed=4150 + j, kind="over", edge=0.0))
    # снежный берег внизу и сухой камыш
    shore = [(px0 - 10, py1 - Hg * 0.20), (px0 + Wd * 0.30, py1 - Hg * 0.14), (px0 + Wd * 0.62, py1 - Hg * 0.07), (px1 + 10, py1 - Hg * 0.12), (px1 + 10, py1 + 10), (px0 - 10, py1 + 10)]
    ops.append(Wash(t0 + 6.9, 0.8, shore, [(0.99, 0.98, 1.0), (0.92, 0.93, 0.98)], dens=0.95, blur=2.0, rough=0.15, direction="right", seed=4160, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 7.5, 0.5, [(a, b + 5) for a, b in shore[:4]], [9], (0.72, 0.78, 0.92), dens=0.35, blur=4, seed=4161))
    t = t0 + 7.8
    for j in range(26):
        side = j % 2
        x = (px0 + r.uniform(10, Wd * 0.26)) if side == 0 else (px1 - r.uniform(10, Wd * 0.2))
        b = py1 - Hg * r.uniform(0.04, 0.16)
        h = Hg * r.uniform(0.18, 0.42)
        lean = r.uniform(-18, 18)
        ops.append(Stroke(t + j * 0.025, 0.3, [(x, b), (x + lean * 0.4, b - h * 0.6), (x + lean, b - h)], [3, 2.2, 1.2], (0.58, 0.44, 0.30), dens=0.85, blur=0.5, seed=4170 + j))
        if j % 3 == 0:
            ops.append(Wash(t + 0.3 + j * 0.025, 0.3, ell(x + lean, b - h - 10, 4, 13, rot=lean / 60), [(0.46, 0.32, 0.22)], dens=0.9, blur=0.8, rough=0.05, seed=4200 + j, edge=0.0))
    end = birds(ops, t + 1.1, [(px0 + Wd * 0.30, py0 + Hs * 0.40, 9)], col=(0.44, 0.40, 0.50))
    return ops, end, "snow"


# ------------------------------------------------------------------ снегири на рябине
def bullfinch(ops, t0, x, y, s, facing=1, seed=0):
    """Снегирь: красная грудка, серая спинка, чёрная шапочка, крыло с белой полосой."""
    f = facing

    def P(dx, dy):
        return (x + f * dx * s, y + dy * s)

    body = [P(*p) for p in [(-0.9, -0.1), (-0.6, -0.55), (0.0, -0.75), (0.55, -0.6), (0.8, -0.2), (0.7, 0.35), (0.25, 0.7), (-0.35, 0.6), (-0.8, 0.3)]]
    ops.append(Wash(t0, 0.4, body, [(0.60, 0.60, 0.66), (0.66, 0.64, 0.68)], dens=0.95, blur=1.0, rough=0.05, direction="down", seed=seed, kind="over", edge=0.0))
    breast = [P(*p) for p in [(0.75, -0.35), (0.85, 0.05), (0.7, 0.42), (0.3, 0.72), (-0.2, 0.66), (-0.1, 0.2), (0.25, -0.15)]]
    ops.append(Wash(t0 + 0.3, 0.4, breast, [(0.92, 0.36, 0.30), (0.86, 0.30, 0.28)], dens=0.97, blur=1.0, rough=0.05, direction="down", seed=seed + 1, kind="over", edge=0.0))
    ops.append(Bloom(t0 + 0.5, *P(0.45, 0.25), 0.25 * s, (1.0, 0.62, 0.52), dens=0.35, dur=0.4, seed=seed + 2, kind="over", soft=2.0))
    cap = [P(*p) for p in [(0.35, -0.62), (0.62, -0.95), (0.95, -1.05), (1.18, -0.85), (1.2, -0.55), (1.0, -0.38), (0.7, -0.42)]]
    head = [P(*p) for p in [(0.4, -0.55), (0.65, -0.95), (1.0, -1.05), (1.22, -0.8), (1.2, -0.42), (0.95, -0.22), (0.6, -0.28)]]
    ops.append(Wash(t0 + 0.5, 0.3, head, [(0.90, 0.36, 0.30)], dens=0.97, blur=0.9, rough=0.05, direction="down", seed=seed + 3, kind="over", edge=0.0))
    ops.append(Wash(t0 + 0.7, 0.3, cap, [(0.12, 0.11, 0.13)], dens=0.97, blur=0.9, rough=0.05, direction="down", seed=seed + 4, kind="over", edge=0.0))
    beak = [P(*p) for p in [(1.15, -0.78), (1.42, -0.66), (1.16, -0.52)]]
    ops.append(Wash(t0 + 0.85, 0.2, beak, [(0.14, 0.12, 0.14)], dens=0.97, blur=0.6, rough=0.03, seed=seed + 5, kind="over", edge=0.0))
    ops.append(Bloom(t0 + 0.95, *P(0.98, -0.74), 0.06 * s, (0.95, 0.95, 0.98), dens=0.9, dur=0.2, seed=seed + 6, kind="over", soft=0.6))
    wing = [P(*p) for p in [(0.3, -0.5), (-0.2, -0.55), (-0.85, -0.25), (-1.25, 0.05), (-0.75, 0.22), (-0.1, 0.18), (0.25, -0.05)]]
    ops.append(Wash(t0 + 0.9, 0.3, wing, [(0.16, 0.15, 0.18), (0.22, 0.20, 0.24)], dens=0.96, blur=0.9, rough=0.05, direction="right", seed=seed + 7, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 1.1, 0.25, [P(0.15, -0.28), P(-0.3, -0.25), P(-0.75, -0.08)], [0.11 * s, 0.09 * s, 0.06 * s], (0.94, 0.94, 0.96), dens=0.9, blur=0.7, kind="over", seed=seed + 8))
    ops.append(Stroke(t0 + 1.2, 0.25, [P(-0.8, 0.0), P(-1.3, 0.3), P(-1.65, 0.62)], [0.32 * s, 0.26 * s, 0.2 * s], (0.12, 0.11, 0.13), dens=0.96, blur=0.7, kind="over", seed=seed + 9))
    for k in (-0.05, 0.2):
        ops.append(Stroke(t0 + 1.3, 0.2, [P(k, 0.62), P(k + 0.05, 0.9)], [0.06 * s], (0.30, 0.24, 0.24), dens=0.9, blur=0.4, seed=seed + 10 + int(k * 10)))
    return t0 + 1.5


def scene_bullfinches(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd = px1 - px0
    Hh = py1 - py0
    ops = []
    # размытый зимний лес позади
    ops.append(Wash(t0, 2.0, [(px0, py0), (px1, py0), (px1, py1), (px0, py1)], [(0.76, 0.80, 0.92), (0.86, 0.86, 0.94), (0.90, 0.88, 0.92)], dens=0.55, blur=4, rough=0.16,
                    seed=4301 + seed, edge=0.12))
    r = random.Random(4302 + seed)
    for j in range(12):
        bx = px0 + r.uniform(0, Wd)
        by = py0 + r.uniform(0.1, 0.95) * Hh
        ops.append(Bloom(t0 + 1.0 + j * 0.08, bx, by, r.uniform(40, 110), r.choice([(0.60, 0.66, 0.82), (0.70, 0.74, 0.88), (0.54, 0.62, 0.74)]), dens=r.uniform(0.15, 0.3), dur=1.2,
                         seed=4310 + j, soft=3.5).clip_to(px0, py0, px1, py1))
    for j in range(8):
        bx = px0 + r.uniform(0, Wd)
        by = py0 + r.uniform(0.05, 0.9) * Hh
        ops.append(Bloom(t0 + 1.8 + j * 0.06, bx, by, r.uniform(16, 40), (0.99, 0.99, 1.0), dens=r.uniform(0.35, 0.6), dur=0.9, seed=4330 + j, kind="over", soft=2.5).clip_to(px0, py0, px1, py1))
    # ветка по диагонали
    a = (px0 - 20, py0 + Hh * 0.80)
    b = (px1 + 20, py0 + Hh * 0.42)

    def on_branch(u):
        return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - 22 * math.sin(u * math.pi)

    br = [on_branch(u) for u in np.linspace(0, 1, 12)]
    bc = (0.34, 0.26, 0.24)
    ops.append(Stroke(t0 + 2.6, 0.8, br, list(np.linspace(20, 9, 12)), bc, dens=0.95, blur=0.9, seed=4340))
    twigs = []
    for j, (u, ang, ln) in enumerate(((0.18, -2.3, 0.22), (0.36, -0.6, 0.17), (0.55, -2.0, 0.16), (0.72, 0.5, 0.14), (0.84, -0.9, 0.15))):
        x0_, y0_ = on_branch(u)
        x1_ = x0_ + math.cos(ang) * ln * Wd
        y1_ = y0_ + math.sin(ang) * ln * Wd
        ops.append(Stroke(t0 + 3.2 + j * 0.1, 0.35, [(x0_, y0_), ((x0_ + x1_) / 2, (y0_ + y1_) / 2 - 6), (x1_, y1_)], [8, 5, 2.5], bc, dens=0.92, blur=0.7, seed=4350 + j))
        twigs.append((x1_, y1_))
    # снег на ветке
    snow = [(x, y - 9) for x, y in br[1:-1]]
    ops.append(Stroke(t0 + 3.9, 0.6, snow, [9, 11, 12, 10, 12, 9, 10, 11, 8, 7], (0.99, 0.99, 1.0), dens=0.92, blur=1.1, kind="over", seed=4360))
    # гроздья рябины
    t = t0 + 4.4
    for j, (x_, y_) in enumerate(twigs[:4] + [on_branch(0.64)]):
        cl = []
        for k in range(11):
            ang = r.uniform(0, 6.28)
            d = r.uniform(0, 22)
            cl.append((x_ + math.cos(ang) * d, y_ + 14 + math.sin(ang) * d * 0.8 + 10, r.uniform(5.5, 8), r.choice([(0.86, 0.22, 0.16), (0.92, 0.32, 0.18), (0.78, 0.16, 0.14)]), k / 11))
        ops.append(Dots(t + j * 0.2, 0.6, cl, blur=0.8))
        ops.append(Dots(t + 0.5 + j * 0.2, 0.3, [(xx - 2, yy - 2, 1.6, (1.0, 0.92, 0.88), 0) for xx, yy, *_ in cl[::2]], blur=0.4))
    # два снегиря
    u1, u2 = 0.33, 0.66
    x1, y1 = on_branch(u1)
    x2, y2 = on_branch(u2)
    s = Wd * 0.064
    t = bullfinch(ops, t0 + 5.6, x1, y1 - s * 0.95, s, facing=1, seed=4400)
    t = bullfinch(ops, t - 0.6, x2, y2 - s * 0.9, s * 0.92, facing=-1, seed=4420)
    return ops, t + 0.3, "snow"


# ------------------------------------------------------------------ фонарь в снегопад
def scene_street_lamp(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.14, 0.16, 0.34), (0.22, 0.24, 0.44), (0.40, 0.36, 0.54)], dens=0.9, seed=4501 + seed)
    r = random.Random(4502 + seed)
    # домики вдали с тёплыми окнами
    t = t0 + 1.8
    xs = px0 + 10
    k = 0
    while xs < px1 - 20:
        wd = r.uniform(70, 120)
        hh = r.uniform(0.18, 0.32) * Hs
        bt = hor + 4
        col = r.choice([(0.26, 0.24, 0.40), (0.30, 0.26, 0.42), (0.22, 0.22, 0.36)])
        ops.append(Wash(t, 0.5, [(xs, bt), (xs + wd, bt), (xs + wd, bt - hh), (xs + wd / 2, bt - hh - wd * 0.35), (xs, bt - hh)], [col], dens=0.9, blur=1.0, rough=0.05,
                        direction="up", seed=4510 + k, edge=0.15))
        ops.append(Stroke(t + 0.3, 0.3, [(xs - 4, bt - hh + 2), (xs + wd / 2, bt - hh - wd * 0.35 - 4), (xs + wd + 4, bt - hh + 2)], [7], (0.92, 0.94, 1.0), dens=0.9, blur=1.2, kind="over",
                          seed=4530 + k))
        for w_ in range(r.choice([1, 2, 2])):
            wx = xs + wd * (0.3 + 0.4 * w_) + r.uniform(-4, 4)
            wy = bt - hh * 0.55
            if r.random() < 0.8:
                ops.append(Wash(t + 0.5, 0.2, [(wx - 9, wy - 11), (wx + 9, wy - 11), (wx + 9, wy + 11), (wx - 9, wy + 11)], [(1.0, 0.82, 0.44)], dens=0.95, blur=0.7, rough=0.03,
                                seed=4550 + 3 * k + w_, kind="over", edge=0.0))
                ops.append(Bloom(t + 0.6, wx, wy, 26, (1.0, 0.78, 0.40), dens=0.22, dur=0.5, seed=4570 + 3 * k + w_, kind="over", soft=3.0))
        xs += wd + r.uniform(10, 50)
        t += 0.25
        k += 1
    # снег на земле
    ops.append(Wash(t, 1.0, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.56, 0.58, 0.76), (0.46, 0.48, 0.68), (0.40, 0.42, 0.62)], dens=0.75, blur=3, rough=0.16, seed=4600,
                    streak=0.2, edge=0.1))
    # дорожка к фонарю
    lx = px0 + Wd * 0.60
    lb = hor + Hg * 0.62
    ops.append(Wash(t + 0.6, 0.8, [(lx - 30, hor + 6), (lx + 10, hor + 6), (px0 + Wd * 0.52, py1 + 5), (px0 + Wd * 0.18, py1 + 5)], [(0.36, 0.38, 0.58)], dens=0.35, blur=6, rough=0.25,
                    direction="up", seed=4601, edge=0.0))
    # круг света на снегу
    ops.append(Bloom(t + 1.1, lx, lb + 10, Wd * 0.30, (1.0, 0.86, 0.60), dens=0.42, dur=1.0, seed=4602, kind="over", soft=4.0).clip_to(px0, hor, px1, py1))
    # столб и фонарь
    top = lb - Hs * 0.62 - Hg * 0.5
    top = max(py0 + 60, top)
    pc = (0.12, 0.12, 0.18)
    ops.append(Stroke(t + 1.6, 0.6, [(lx, lb), (lx, top + 30)], [10, 7], pc, dens=0.95, blur=0.7, seed=4603))
    ops.append(Stroke(t + 2.1, 0.3, [(lx, top + 34), (lx + 22, top + 26), (lx + 34, top + 34)], [5], pc, dens=0.95, blur=0.6, seed=4604))
    lamp = [(lx + 18, top + 36), (lx + 50, top + 36), (lx + 44, top + 76), (lx + 24, top + 76)]
    ops.append(Bloom(t + 2.3, lx + 34, top + 58, Hs * 0.42, (1.0, 0.80, 0.46), dens=0.42, dur=1.0, seed=4605, kind="over", soft=4.5).clip_to(px0, py0, px1, py1))
    ops.append(Wash(t + 2.4, 0.3, lamp, [(1.0, 0.90, 0.60)], dens=0.97, blur=0.8, rough=0.03, seed=4606, kind="over", edge=0.0))
    ops.append(Stroke(t + 2.6, 0.2, [(lx + 14, top + 36), (lx + 54, top + 36)], [6], pc, dens=0.95, blur=0.5, seed=4607))
    ops.append(Stroke(t + 2.7, 0.2, [(lx + 16, top + 34), (lx + 52, top + 34)], [5], (0.94, 0.95, 1.0), dens=0.9, blur=0.8, kind="over", seed=4608))
    ops.append(Bloom(t + 2.8, lx + 34, top + 58, 14, (1.0, 1.0, 0.92), dens=1.0, dur=0.3, seed=4609, kind="over", soft=1.0))
    # конус света
    ops.append(Wash(t + 3.0, 0.8, [(lx + 24, top + 76), (lx + 44, top + 76), (lx + Wd * 0.22, lb + 20), (lx - Wd * 0.18, lb + 20)], [(1.0, 0.88, 0.62)], dens=0.12, blur=10, rough=0.2,
                    direction="down", seed=4610, kind="over", edge=0.0))
    # скамейка под фонарём, с шапкой снега
    bx0, bx1, byb = lx - Wd * 0.26, lx - Wd * 0.06, lb + 4
    sy_ = byb - Hg * 0.10
    ops.append(Stroke(t + 3.5, 0.3, [(bx0, sy_), (bx1, sy_)], [8], (0.20, 0.16, 0.20), dens=0.95, blur=0.6, seed=4611))
    ops.append(Stroke(t + 3.6, 0.3, [(bx0, sy_ - 26), (bx1, sy_ - 26)], [6], (0.20, 0.16, 0.20), dens=0.95, blur=0.6, seed=4612))
    for j, lxx in enumerate((bx0 + 8, bx1 - 8)):
        ops.append(Stroke(t + 3.7 + j * 0.05, 0.2, [(lxx, sy_ - 30), (lxx, byb)], [5], (0.16, 0.14, 0.18), dens=0.95, blur=0.5, seed=4613 + j))
    ops.append(Stroke(t + 3.9, 0.3, [(bx0 - 3, sy_ - 6), (bx1 + 3, sy_ - 6)], [8], (0.94, 0.95, 1.0), dens=0.92, blur=1.2, kind="over", seed=4615))
    ops.append(Stroke(t + 4.0, 0.3, [(bx0 - 2, sy_ - 31), (bx1 + 2, sy_ - 31)], [6], (0.94, 0.95, 1.0), dens=0.9, blur=1.2, kind="over", seed=4616))
    # сугробы на переднем плане
    for j in range(3):
        x = px0 + Wd * (0.1 + 0.4 * j) + r.uniform(-30, 30)
        ops.append(Bloom(t + 4.2 + j * 0.15, x, py1 - 10, r.uniform(60, 110), (0.80, 0.84, 0.96), dens=0.45, dur=0.6, seed=4620 + j, kind="over", soft=2.5).clip_to(px0, hor, px1, py1))
    return ops, t + 5.0, "snow"


# ------------------------------------------------------------------ лунный зимний лес
def scene_moon_forest(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.10, 0.12, 0.30), (0.16, 0.20, 0.42), (0.30, 0.36, 0.58)], dens=0.92, seed=4701 + seed)
    stars(ops, t0 + 1.8, box, hor, n=70, seed=4702 + seed, frac=0.7)
    mxp, myp = px0 + Wd * 0.68, py0 + Hs * 0.30
    ops.append(Bloom(t0 + 2.2, mxp, myp, Hs * 0.42, (0.80, 0.84, 0.96), dens=0.32, dur=1.2, seed=4703, kind="over", soft=4.5).clip_to(px0, py0, px1, hor))
    ops.append(Bloom(t0 + 2.6, mxp, myp, 44, (0.99, 0.98, 0.92), dens=1.0, dur=0.6, seed=4704, kind="over", soft=0.9))
    ops.append(Bloom(t0 + 2.9, mxp - 12, myp - 6, 10, (0.90, 0.88, 0.84), dens=0.35, dur=0.3, seed=4705, soft=1.2))
    spruce_row(ops, t0 + 3.2, box, hor - 6, (0.34, 0.40, 0.62), hmin=40, hmax=110, step=15, seed=4706, dens=0.6)
    spruce_row(ops, t0 + 3.9, box, hor + 8, (0.16, 0.20, 0.38), hmin=60, hmax=160, step=17, seed=4707, dens=0.85)
    # лунный снег
    ops.append(Wash(t0 + 4.8, 1.0, [(px0, hor + 4), (px1, hor + 4), (px1, py1), (px0, py1)], [(0.60, 0.66, 0.86), (0.70, 0.76, 0.92), (0.62, 0.68, 0.88)], dens=0.6, blur=3, rough=0.18,
                    seed=4708, streak=0.2, edge=0.1))
    ops.append(Bloom(t0 + 5.4, mxp - Wd * 0.1, hor + Hg * 0.35, Wd * 0.34, (0.86, 0.90, 1.0), dens=0.35, dur=1.0, seed=4709, kind="over", soft=4.0).clip_to(px0, hor, px1, py1))
    # большие ели по краям, длинные лунные тени
    r = random.Random(4710 + seed)
    t = t0 + 5.8
    for j, (fx, fh_) in enumerate(((0.05, 1.05), (0.17, 0.8), (0.86, 0.95), (0.96, 1.2))):
        x = px0 + Wd * fx
        b = min(py1 - 8, hor + Hg * r.uniform(0.55, 0.85))
        h = Hs * 0.55 * fh_ + Hg * 0.3
        sh = [(x, b), (x - Wd * 0.25, b + Hg * 0.10), (x - Wd * 0.28, b + Hg * 0.13), (x + 8, b + 6)]
        ops.append(Wash(t, 0.5, sh, [(0.36, 0.40, 0.66)], dens=0.4, blur=4, rough=0.2, direction="left", seed=4720 + j, edge=0.0))
        t = snow_tree(ops, t + 0.1, x, b, h, col=(0.08, 0.12, 0.24), seed=4730 + 40 * j) - 0.7
    # дорожка следов
    for j in range(9):
        u = j / 8
        x = px0 + Wd * (0.36 + 0.2 * u) + 10 * math.sin(j * 1.7)
        y = py1 - 14 - u * Hg * 0.7
        ops.append(Bloom(t + 0.8 + j * 0.05, x, y, 6 - 3 * u, (0.40, 0.46, 0.72), dens=0.5, dur=0.2, seed=4780 + j, soft=1.0))
    return ops, t + 1.6, "snow"


# ------------------------------------------------------------------ одинокий дуб на зимнем закате
def scene_lone_tree(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.46, 0.50, 0.76), (0.86, 0.62, 0.70), (1.0, 0.76, 0.56), (1.0, 0.86, 0.62)], dens=0.68, seed=4801 + seed)
    sx, sy = px0 + Wd * 0.30, hor - 16
    sun(ops, t0 + 1.4, sx, sy, r=34, halo=Hs * 0.6, col=(1.0, 0.92, 0.70), hcol=(1.0, 0.76, 0.48), seed=4802)
    for j, (fx, fy, fw) in enumerate(((0.70, 0.20, 0.20), (0.40, 0.12, 0.14))):
        ops.append(Wash(t0 + 1.9 + j * 0.3, 1.0, ell(px0 + Wd * fx, py0 + Hs * fy, Wd * fw, Hs * 0.03), [(1.0, 0.84, 0.80)], dens=0.5, blur=6, rough=0.3, direction="right",
                        seed=4803 + j, kind="over", edge=0.0))
    # дальний лес полосой
    spruce_row(ops, t0 + 2.4, box, hor + 3, (0.50, 0.38, 0.52), hmin=10, hmax=34, step=9, seed=4804, dens=0.55, dur=1.0)
    # заснеженное поле в розовом свете
    ops.append(Wash(t0 + 3.2, 1.1, [(px0, hor + 2), (px1, hor + 2), (px1, py1), (px0, py1)], [(1.0, 0.86, 0.80), (0.92, 0.84, 0.90), (0.82, 0.82, 0.94)], dens=0.34, blur=4, rough=0.18,
                    seed=4805, streak=0.2, edge=0.1))
    r = random.Random(4806 + seed)
    for j in range(4):
        yv = hor + Hg * (0.12 + 0.22 * j)
        poly = [(px0 + k * Wd / 7, yv + 10 * math.sin(k * 1.4 + j)) for k in range(8)] + [(px1 - k * Wd / 7, min(py1, yv + Hg * 0.08) + 6 * math.cos(k + j)) for k in range(8)]
        ops.append(Wash(t0 + 3.8 + j * 0.2, 0.7, poly, [(0.68, 0.66, 0.88)], dens=0.16, blur=9, rough=0.25, direction="right", seed=4810 + j, streak=0.3, edge=0.03))
    # дуб
    tx, tb = px0 + Wd * 0.66, hor + Hg * 0.42
    th = (Hs + Hg * 0.42) * 0.82
    # длинная синяя тень от дуба — к зрителю, вправо
    ops.append(Wash(t0 + 4.7, 0.8, [(tx - 8, tb), (tx + 8, tb), (px1 + 10, py1 - Hg * 0.05), (px1 + 10, py1 + 10), (px1 - Wd * 0.12, py1 + 10)], [(0.56, 0.56, 0.82)], dens=0.32, blur=6,
                    rough=0.25, direction="down", seed=4820, edge=0.0))
    t = bare_tree(ops, t0 + 5.0, tx, tb, th, seed=4821 + seed, col=(0.24, 0.18, 0.22))
    ops.append(Stroke(t, 0.4, [(tx - 40, tb + 4), (tx + 46, tb + 6)], [10], (0.98, 0.94, 0.96), dens=0.7, blur=3, kind="over", seed=4822))
    # изгородь со снежными шапками
    for j in range(7):
        u = j / 6
        x = px0 + Wd * (0.04 + 0.40 * u)
        b = hor + Hg * (0.30 + 0.55 * u)
        h = 26 + 46 * u
        ops.append(Stroke(t + 0.2 + j * 0.07, 0.2, [(x, b), (x + 2, b - h)], [4 + 4 * u], (0.30, 0.22, 0.24), dens=0.92, blur=0.6, seed=4830 + j))
        ops.append(Bloom(t + 0.4 + j * 0.07, x + 1, b - h - 2, 4 + 4 * u, (0.99, 0.97, 0.98), dens=0.9, dur=0.2, seed=4840 + j, kind="over", soft=1.0))
        if j:
            xp = px0 + Wd * (0.04 + 0.40 * (j - 1) / 6)
            bp = hor + Hg * (0.30 + 0.55 * (j - 1) / 6)
            hp = 26 + 46 * (j - 1) / 6
            ops.append(Stroke(t + 0.3 + j * 0.07, 0.2, [(xp, bp - hp * 0.6), (x, b - h * 0.6)], [2 + 2 * u], (0.34, 0.26, 0.28), dens=0.85, blur=0.6, seed=4850 + j))
    end = birds(ops, t + 1.0, [(px0 + Wd * 0.42, py0 + Hs * 0.34, 11), (px0 + Wd * 0.48, py0 + Hs * 0.30, 9), (px0 + Wd * 0.52, py0 + Hs * 0.37, 8)], col=(0.36, 0.28, 0.36))
    return ops, end, "motes"


# ------------------------------------------------------------------ кони в зимней степи
def horse(ops, t0, x, base, s, col=(0.30, 0.20, 0.16), facing=1, graze=False, seed=0):
    """Силуэт коня: бочка, грудь, круп, шея с гривой, голова, ноги со скакательным суставом, хвост."""
    u = s / 100.0
    f = facing

    def P(dx, dy):
        return (x + f * dx * u, base + dy * u)

    def E(cx_, cy_, a, b, rot=0.0):
        return [P(cx_ + px_, cy_ + py_) for px_, py_ in ell(0, 0, a, b, rot)]

    dark = tuple(c * 0.62 for c in col)
    bl = max(0.5, u * 0.9)
    kw = dict(dens=0.96, blur=bl, rough=0.03, kind="over", edge=0.0)
    ops.append(Wash(t0, 0.35, E(0, -54, 38, 15), [col], direction="right", seed=seed, **kw))
    ops.append(Wash(t0 + 0.1, 0.3, E(-30, -56, 16, 17, 0.2), [col], direction="right", seed=seed + 1, **kw))
    ops.append(Wash(t0 + 0.15, 0.3, E(29, -56, 15, 16, -0.3), [col], direction="right", seed=seed + 2, **kw))
    if graze:
        neck = [P(20, -68), P(36, -44), P(62, -14), P(56, -4), P(40, -30), P(22, -50)]
        head = E(62, -8, 13, 6, 1.25)
        ear = [P(58, -16), P(54, -24)]
        mane = [P(22, -68), P(42, -42), P(58, -16)]
    else:
        neck = [P(18, -66), P(36, -48), P(56, -88), P(46, -102), P(32, -84)]
        head = E(60, -94, 14, 6.5, 0.62)
        ear = [P(48, -104), P(46, -114)]
        mane = [P(20, -68), P(34, -86), P(46, -103)]
    ops.append(Wash(t0 + 0.2, 0.3, neck, [col], direction="down", seed=seed + 3, **kw))
    ops.append(Wash(t0 + 0.35, 0.2, head, [col], direction="right", seed=seed + 4, **kw))
    ops.append(Stroke(t0 + 0.45, 0.15, ear, [4.5 * u, 2 * u], col, dens=0.96, blur=0.5, kind="over", seed=seed + 5))
    ops.append(Stroke(t0 + 0.5, 0.25, mane, [7 * u, 6 * u, 4 * u], dark, dens=0.95, blur=bl, kind="over", seed=seed + 6))
    legs = (((24, -46), (25, -22), (24, -2)), ((32, -46), (35, -22), (37, -2)), ((-30, -46), (-36, -24), (-31, -2)), ((-22, -46), (-26, -24), (-20, -2)))
    for j, pts in enumerate(legs):
        ops.append(Stroke(t0 + 0.55 + j * 0.04, 0.2, [P(*p) for p in pts], [9 * u, 5 * u, 4 * u], col if j % 2 == 0 else tuple(c * 0.85 for c in col), dens=0.96, blur=bl, kind="over",
                          seed=seed + 7 + j))
        hx, hy = P(*pts[-1])
        ops.append(Stroke(t0 + 0.7, 0.1, [(hx - 3 * u, hy + u), (hx + 3 * u, hy + u)], [4 * u], dark, dens=0.95, blur=0.5, kind="over", seed=seed + 12 + j))
    ops.append(Stroke(t0 + 0.75, 0.25, [P(-44, -62), P(-54, -48), P(-55, -30), P(-50, -18)], [8 * u, 7 * u, 5 * u, 3 * u], dark, dens=0.95, blur=bl, kind="over", seed=seed + 17))
    return t0 + 1.0


def scene_steppe_horses(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.56, 0.68, 0.88), (0.80, 0.84, 0.92), (0.98, 0.90, 0.80)], dens=0.6, seed=4901 + seed)
    sun(ops, t0 + 1.3, px0 + Wd * 0.80, hor - Hs * 0.30, r=26, halo=Hs * 0.45, col=(1.0, 0.98, 0.92), hcol=(1.0, 0.92, 0.76), seed=4902)
    for j, (fx, fy, fw) in enumerate(((0.24, 0.30, 0.22), (0.56, 0.16, 0.16))):
        ops.append(Wash(t0 + 1.7 + j * 0.3, 1.0, ell(px0 + Wd * fx, py0 + Hs * fy, Wd * fw, Hs * 0.03), [(0.99, 0.98, 0.96)], dens=0.6, blur=6, rough=0.3, direction="right",
                        seed=4903 + j, kind="over", edge=0.0))
    mx = np.linspace(px0 - 10, px1 + 10, 120)
    far = hor - 0.10 * Hs - 0.06 * Hs * np.abs(np.sin(mx / 150 + 0.4 + seed)) - 0.02 * Hs * np.sin(mx / 41)
    hills(ops, t0 + 2.4, box, hor, far, mx, [(0.74, 0.74, 0.90), (0.70, 0.72, 0.88)], dens=0.45, seed=4905, blur=2.2)
    ops.append(Wash(t0 + 3.0, 0.8, [(px0, hor - 14), (px1, hor - 14), (px1, hor + 6), (px0, hor + 6)], [(0.98, 0.94, 0.92)], dens=0.4, blur=8, rough=0.3, direction="right", seed=4906,
                    kind="over", edge=0.0))
    snow_field(ops, t0 + 3.3, box, hor, base_col=((0.96, 0.92, 0.90), (0.86, 0.88, 0.96)), seed=4907, bands=3)
    # сухая степная трава из-под снега
    r = random.Random(4910 + seed)
    t = t0 + 4.8
    for j in range(60):
        u = r.random() ** 0.8
        y = hor + 6 + u * (Hg - 12)
        x = px0 + r.uniform(5, Wd - 5)
        h = 4 + 26 * u
        lean = r.uniform(-0.4, 0.4) * h
        ops.append(Stroke(t + j * 0.012, 0.2, [(x, y), (x + lean, y - h)], [1 + 1.6 * u], r.choice([(0.78, 0.64, 0.40), (0.70, 0.56, 0.36), (0.84, 0.72, 0.48)]), dens=0.7, blur=0.4,
                          seed=4920 + j))
    # табун на среднем плане: кто пасётся, кто смотрит вдаль
    t = t + 1.0
    herd = [(0.12, 0.30, 1, True, 0.9), (0.30, 0.22, 1, False, 0.8), (0.44, 0.34, -1, True, 1.0), (0.60, 0.26, 1, True, 0.85), (0.76, 0.42, -1, False, 1.15),
            (0.90, 0.24, -1, True, 0.8)]
    cols = [(0.32, 0.20, 0.16), (0.46, 0.30, 0.20), (0.22, 0.17, 0.17), (0.54, 0.38, 0.26), (0.36, 0.22, 0.16), (0.28, 0.20, 0.18)]
    for j, (fx, fy, fc, gz, sc_) in enumerate(herd):
        b = hor + Hg * fy
        s = min(110, Hg * 0.20) * sc_ * (0.75 + 0.6 * fy)
        ops.append(Stroke(t + 0.5, 0.3, [(px0 + Wd * fx - s * 0.5, b + 2), (px0 + Wd * fx + s * 0.55, b + 3)], [max(5, s * 0.08)], (0.66, 0.70, 0.88), dens=0.35, blur=4, seed=5100 + j))
        t = horse(ops, t, px0 + Wd * fx, b, s, col=cols[j], facing=fc, graze=gz, seed=4960 + 20 * j) - 0.7
    t += 0.7
    end = birds(ops, t + 0.2, [(px0 + Wd * 0.40, py0 + Hs * 0.40, 10), (px0 + Wd * 0.45, py0 + Hs * 0.45, 8)], col=(0.40, 0.38, 0.48))
    return ops, end, "motes"


# ------------------------------------------------------------------ морозное окно, чай и мандарины
def scene_frost_window(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd = px1 - px0
    Hh = py1 - py0
    ops = []
    # тёплая стена комнаты
    ops.append(Wash(t0, 2.0, [(px0, py0), (px1, py0), (px1, py1), (px0, py1)], [(0.56, 0.40, 0.32), (0.62, 0.44, 0.34), (0.50, 0.36, 0.28)], dens=0.85, blur=4, rough=0.14,
                    seed=5201 + seed, edge=0.1))
    sill = py1 - Hh * 0.22
    wx0, wx1, wy0 = px0 + Wd * 0.12, px1 - Wd * 0.12, py0 + Hh * 0.07
    win = (wx0, wx1, wy0, sill)
    # вид за окном: синие сумерки, снег, ели и огоньки
    whor = wy0 + (sill - wy0) * 0.68
    ops.append(Wash(t0 + 1.4, 1.4, [(wx0, wy0), (wx1, wy0), (wx1, sill), (wx0, sill)], [(0.20, 0.24, 0.48), (0.36, 0.38, 0.62), (0.62, 0.56, 0.72)], dens=0.95, blur=1.5, rough=0.06,
                    seed=5202, kind="over", edge=0.0))
    r = random.Random(5203 + seed)
    st = [(r.uniform(wx0 + 10, wx1 - 10), r.uniform(wy0 + 8, wy0 + (whor - wy0) * 0.6), r.choice([1.3, 1.7, 2.2]), (1.0, 0.98, 0.92), r.random()) for _ in range(30)]
    ops.append(Dots(t0 + 2.6, 1.0, st, blur=0.6))
    mx = np.linspace(wx0, wx1, 80)
    ridge_ = whor - 10 - 36 * np.abs(np.sin(mx / 60 + 1.1 + seed)) - 12 * np.sin(mx / 23)
    ops.append(Wash(t0 + 2.8, 0.8, list(zip(mx, ridge_)) + [(wx1, whor + 4), (wx0, whor + 4)], [(0.16, 0.18, 0.34)], dens=0.85, blur=1.0, rough=0.06, direction="right", seed=5204, edge=0.1))
    ops.append(Wash(t0 + 3.4, 0.8, [(wx0, whor), (wx1, whor), (wx1, sill), (wx0, sill)], [(0.70, 0.74, 0.90), (0.80, 0.84, 0.96)], dens=0.95, blur=1.0, rough=0.08, seed=5205, kind="over",
                    edge=0.0))
    for j in range(5):
        lx_ = r.uniform(wx0 + 30, wx1 - 30)
        ly_ = whor - r.uniform(4, 20)
        ops.append(Bloom(t0 + 3.9 + j * 0.08, lx_, ly_, 16, (1.0, 0.80, 0.42), dens=0.5, dur=0.4, seed=5206 + j, kind="over", soft=2.0))
        ops.append(Bloom(t0 + 4.0 + j * 0.08, lx_, ly_, 4, (1.0, 0.94, 0.70), dens=1.0, dur=0.2, seed=5216 + j, kind="over", soft=0.8))
    # рама: переплёт крестом
    fc = (0.92, 0.88, 0.80)
    fw = max(14, Wd * 0.022)
    xm = (wx0 + wx1) / 2
    ym = wy0 + (sill - wy0) * 0.42
    ops.append(Stroke(t0 + 4.5, 0.4, [(xm, wy0), (xm, sill)], [fw], fc, dens=0.97, blur=0.8, kind="over", seed=5230))
    ops.append(Stroke(t0 + 4.7, 0.4, [(wx0, ym), (wx1, ym)], [fw * 0.8], fc, dens=0.97, blur=0.8, kind="over", seed=5231))
    for j, pts in enumerate(([(wx0, wy0), (wx1, wy0)], [(wx0, wy0), (wx0, sill)], [(wx1, wy0), (wx1, sill)])):
        ops.append(Stroke(t0 + 4.9 + j * 0.1, 0.3, pts, [fw * 1.5], fc, dens=0.97, blur=0.8, kind="over", seed=5232 + j))
    # морозные узоры по углам стёкол
    t = t0 + 5.3
    k = 0
    for (cx_, cy_, dx, dy) in ((wx0 + fw, sill - fw * 0.3, 1, -1), (wx1 - fw, sill - fw * 0.3, -1, -1), (xm - fw * 0.5, ym - fw * 0.5, -1, -1), (xm + fw * 0.5, ym - fw * 0.5, 1, -1),
                               (wx0 + fw, wy0 + fw, 1, 1), (wx1 - fw, wy0 + fw, -1, 1)):
        ops.append(Bloom(t, cx_, cy_, Wd * 0.13, (0.92, 0.95, 1.0), dens=0.45, dur=0.6, seed=5240 + k, kind="over", soft=3.0).clip_to(wx0, wy0, wx1, sill))
        for m in range(6):
            ang = r.uniform(0.15, 1.4)
            ln = r.uniform(0.06, 0.16) * Wd
            x0_, y0_ = cx_, cy_
            pts = [(x0_, y0_)]
            for s_ in range(4):
                ang += r.uniform(-0.35, 0.35)
                x0_ += dx * math.cos(ang) * ln / 4
                y0_ += dy * math.sin(ang) * ln / 4
                pts.append((x0_, y0_))
            ops.append(Stroke(t + 0.2 + m * 0.04, 0.3, pts, [2.4, 2, 1.6, 1.2, 1], (0.97, 0.98, 1.0), dens=0.75, blur=0.7, kind="over", seed=5260 + 10 * k + m))
            for s_ in (1, 2, 3):
                bx_, by_ = pts[s_]
                for sgn in (-1, 1):
                    a2 = ang + sgn * 0.8
                    ops.append(Stroke(t + 0.35 + m * 0.04, 0.2, [(bx_, by_), (bx_ + dx * math.cos(a2) * ln * 0.14, by_ + dy * math.sin(a2) * ln * 0.14 + sgn * 3)], [1.2],
                                      (0.97, 0.98, 1.0), dens=0.6, blur=0.5, kind="over", seed=5400 + 30 * k + 6 * m + s_ + (sgn > 0)))
        t += 0.2
        k += 1
    # подоконник
    ops.append(Wash(t, 0.6, [(px0 - 10, sill), (px1 + 10, sill), (px1 + 10, sill + Hh * 0.06), (px0 - 10, sill + Hh * 0.06)], [(0.94, 0.90, 0.84)], dens=0.97, blur=1.0, rough=0.04,
                    direction="right", seed=5600, kind="over", edge=0.0))
    ops.append(Stroke(t + 0.4, 0.3, [(px0 - 10, sill + Hh * 0.06 + 3), (px1 + 10, sill + Hh * 0.06 + 3)], [6], (0.30, 0.20, 0.16), dens=0.5, blur=2.5, seed=5601))
    # чашка с чаем и паром
    cxp, cb = px0 + Wd * 0.34, sill + Hh * 0.025
    cw, chh = Wd * 0.065, Hh * 0.12
    cup = [(cxp - cw, cb - chh), (cxp + cw, cb - chh), (cxp + cw * 0.86, cb), (cxp - cw * 0.86, cb)]
    ops.append(Wash(t + 0.7, 0.4, cup, [(0.86, 0.30, 0.26), (0.72, 0.22, 0.22)], dens=0.97, blur=0.9, rough=0.04, direction="down", seed=5602, kind="over", edge=0.0))
    for j in range(3):
        ops.append(Bloom(t + 0.9 + j * 0.05, cxp - cw * 0.5 + j * cw * 0.5, cb - chh * 0.55, cw * 0.12, (0.99, 0.96, 0.90), dens=0.95, dur=0.2, seed=5603 + j, kind="over", soft=0.8))
    ops.append(Stroke(t + 1.0, 0.3, [(cxp + cw, cb - chh * 0.8), (cxp + cw * 1.45, cb - chh * 0.72), (cxp + cw * 1.4, cb - chh * 0.3), (cxp + cw * 0.92, cb - chh * 0.25)], [6],
                      (0.74, 0.24, 0.22), dens=0.95, blur=0.6, kind="over", seed=5606))
    ops.append(Wash(t + 1.1, 0.2, ell(cxp, cb - chh, cw, cw * 0.18), [(0.52, 0.30, 0.18)], dens=0.95, blur=0.6, rough=0.03, seed=5607, kind="over", edge=0.0))
    for j in range(3):
        ops.append(Stroke(t + 1.2 + j * 0.15, 0.6, [(cxp - 10 + j * 10, cb - chh - 6), (cxp - 18 + j * 12, cb - chh - 40), (cxp - 4 + j * 10, cb - chh - 76), (cxp - 14 + j * 12, cb - chh - 110)],
                          [6, 5, 4, 3], (0.98, 0.96, 0.94), dens=0.35 - j * 0.06, blur=3.0, kind="over", seed=5610 + j))
    # мандарины и еловая веточка
    t2 = t + 1.6
    for j, (mx_, mr) in enumerate(((0.58, 0.042), (0.66, 0.036), (0.62, 0.032))):
        xx = px0 + Wd * mx_
        rr_ = Wd * mr
        yy = sill + Hh * 0.025 - rr_ * (0.9 if j < 2 else 2.3)
        ops.append(Bloom(t2 + j * 0.15, xx, yy, rr_, (0.98, 0.56, 0.18), dens=0.97, dur=0.4, seed=5620 + j, kind="over", soft=0.7))
        ops.append(Bloom(t2 + 0.2 + j * 0.15, xx - rr_ * 0.3, yy - rr_ * 0.3, rr_ * 0.35, (1.0, 0.78, 0.46), dens=0.6, dur=0.3, seed=5630 + j, kind="over", soft=1.5))
        ops.append(Stroke(t2 + 0.3 + j * 0.15, 0.2, [(xx, yy - rr_ * 0.9), (xx + rr_ * 0.45, yy - rr_ * 1.2)], [4], (0.26, 0.48, 0.24), dens=0.9, blur=0.5, kind="over", seed=5640 + j))
    bx_, by_ = px0 + Wd * 0.80, sill + Hh * 0.02
    ops.append(Stroke(t2 + 0.8, 0.3, [(bx_ - 50, by_), (bx_ + 60, by_ - 26)], [5], (0.36, 0.24, 0.18), dens=0.9, blur=0.5, kind="over", seed=5650))
    for j in range(16):
        u = j / 15
        x = bx_ - 50 + 110 * u
        y = by_ - 26 * u
        for sgn in (-1, 1):
            ops.append(Stroke(t2 + 0.9 + j * 0.02, 0.15, [(x, y), (x + 12, y + sgn * 14)], [3], (0.16, 0.36, 0.28), dens=0.9, blur=0.4, kind="over", seed=5660 + 2 * j + (sgn > 0)))
    return ops, t2 + 1.6, "motes"


# ------------------------------------------------------------------ подснежники
def petal(cx, cy, L, Wm, ang, n=16):
    """Лепесток-капля, свисающий из точки (cx, cy) под углом ang от вертикали."""
    left, right = [], []
    for k in range(n + 1):
        u = k / n
        hw = Wm * math.sin(math.pi * min(1.0, u ** 0.75)) * (1 - 0.15 * u)
        d = L * u
        bx, by = cx + math.sin(ang) * d, cy + math.cos(ang) * d
        nx, ny = math.cos(ang), -math.sin(ang)
        left.append((bx - nx * hw, by - ny * hw))
        right.append((bx + nx * hw, by + ny * hw))
    return left + right[::-1]


def snowdrop(ops, t0, x, base, h, seed=0, lean=1):
    r = random.Random(seed)
    top = (x + lean * h * 0.14, base - h)
    stem = [(x, base), (x + lean * h * 0.04, base - h * 0.5), top]
    ops.append(Stroke(t0, 0.3, stem, [4, 3.4, 2.6], (0.30, 0.50, 0.32), dens=0.95, blur=0.6, kind="over", seed=seed))
    for sgn in (-1, 1):
        lh = h * r.uniform(0.45, 0.65)
        ops.append(Stroke(t0 + 0.1, 0.3, [(x + sgn * 4, base), (x + sgn * 8, base - lh * 0.5), (x + sgn * 13, base - lh)], [11, 10, 3], (0.40, 0.58, 0.46), dens=0.9, blur=0.7, kind="over",
                          seed=seed + 1 + (sgn > 0)))
    # дуга цветоножки и поникший колокольчик
    hook = [top, (top[0] + lean * h * 0.09, top[1] - h * 0.035), (top[0] + lean * h * 0.15, top[1] + h * 0.03)]
    ops.append(Stroke(t0 + 0.3, 0.2, hook, [2.4, 2, 1.8], (0.30, 0.50, 0.32), dens=0.95, blur=0.5, seed=seed + 3))
    fx, fy = hook[-1]
    L = h * 0.20
    for k, ang in enumerate((-0.42, 0.42, 0.0)):
        ops.append(Wash(t0 + 0.45 + k * 0.06, 0.25, petal(fx, fy + h * 0.012, L, L * 0.30, ang * lean), [(1.0, 1.0, 1.0), (0.93, 0.95, 0.97)], dens=0.97, blur=0.7, rough=0.03,
                        direction="down", seed=seed + 5 + k, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 0.7, 0.15, [(fx - L * 0.10, fy + L * 0.80), (fx, fy + L * 0.90), (fx + L * 0.10, fy + L * 0.80)], [2.2], (0.36, 0.62, 0.40), dens=0.8, blur=0.5, kind="over",
                      seed=seed + 9))
    ops.append(Wash(t0 + 0.4, 0.2, ell(fx, fy + h * 0.008, h * 0.018, h * 0.026), [(0.34, 0.56, 0.32)], dens=0.95, blur=0.5, rough=0.03, seed=seed + 4, kind="over", edge=0.0))
    return t0 + 0.9


def scene_snowdrops(box, hor, t0=0.8, seed=0):
    """Подснежники крупным планом: проталины в снегу, весеннее солнце, размытый лес позади."""
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    ops.append(Wash(t0, 2.0, [(px0, py0), (px1, py0), (px1, hor + 8), (px0, hor + 8)], [(0.74, 0.84, 0.92), (0.88, 0.92, 0.88), (0.94, 0.94, 0.84)], dens=0.55, blur=4, rough=0.16,
                    seed=5301 + seed, edge=0.12))
    ops.append(Bloom(t0 + 1.0, px0 + Wd * 0.78, py0 + Hs * 0.30, Hs * 0.7, (1.0, 0.97, 0.82), dens=0.5, dur=1.4, seed=5302, kind="over", soft=4.0).clip_to(px0, py0, px1, hor))
    r = random.Random(5303 + seed)
    for j in range(14):
        bx = px0 + r.uniform(0, Wd)
        by = py0 + r.uniform(0.2, 1.0) * Hs
        ops.append(Bloom(t0 + 1.5 + j * 0.06, bx, by, r.uniform(30, 80), r.choice([(0.62, 0.72, 0.62), (0.70, 0.76, 0.70), (0.58, 0.66, 0.72), (0.76, 0.70, 0.62)]),
                         dens=r.uniform(0.18, 0.32), dur=1.0, seed=5310 + j, soft=3.5).clip_to(px0, py0, px1, hor + 20))
    # снег с голубыми тенями
    ops.append(Wash(t0 + 2.6, 1.0, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.90, 0.92, 0.98), (0.84, 0.88, 0.97)], dens=0.3, blur=4, rough=0.2, seed=5340, streak=0.2, edge=0.1))
    for j in range(3):
        yv = hor + Hg * (0.1 + 0.3 * j)
        poly = [(px0 + k * Wd / 7, yv + 10 * math.sin(k * 1.5 + j)) for k in range(8)] + [(px1 - k * Wd / 7, min(py1, yv + Hg * 0.1) + 6 * math.cos(k + j)) for k in range(8)]
        ops.append(Wash(t0 + 3.0 + j * 0.2, 0.7, poly, [(0.74, 0.80, 0.94)], dens=0.16, blur=9, rough=0.25, direction="right", seed=5345 + j, streak=0.3, edge=0.03))
    # проталины с землёй и прошлогодними листьями — вокруг каждого кустика
    clumps = ((0.22, 0.62, 4, 0.85), (0.52, 0.86, 5, 1.0), (0.80, 0.55, 3, 0.8))
    t = t0 + 3.6
    for k, (fx, fy, n, sc_) in enumerate(clumps):
        bx_, by_ = px0 + Wd * fx, min(py1 - 10, hor + Hg * fy)
        R = Wd * 0.12 * sc_
        ops.append(Wash(t + k * 0.2, 0.6, ell(bx_, by_ - R * 0.05, R, R * 0.32), [(0.52, 0.40, 0.30), (0.42, 0.32, 0.26)], dens=0.75, blur=2.5, rough=0.3, direction="down",
                        seed=5360 + k, edge=0.2))
        for m in range(6):
            lx_ = bx_ + r.uniform(-R * 0.8, R * 0.8)
            ly_ = by_ + r.uniform(-R * 0.2, R * 0.15)
            ops.append(Wash(t + 0.4 + k * 0.2 + m * 0.03, 0.3, ell(lx_, ly_, r.uniform(8, 15) * sc_, r.uniform(4, 6) * sc_, r.uniform(-0.6, 0.6)),
                            [r.choice([(0.70, 0.46, 0.24), (0.62, 0.38, 0.22), (0.78, 0.56, 0.30)])], dens=0.85, blur=0.8, rough=0.05, seed=5380 + 10 * k + m, edge=0.1))
    t += 1.3
    for k, (fx, fy, n, sc_) in enumerate(clumps):
        bx_, by_ = px0 + Wd * fx, min(py1 - 10, hor + Hg * fy)
        hs = min(Hs + Hg * fy, 520) * 0.62 * sc_
        for m in range(n):
            xx = bx_ + (m - (n - 1) / 2) * hs * 0.15 + r.uniform(-6, 6)
            t = snowdrop(ops, t + 0.05, xx, by_ + r.uniform(-4, 4), hs * r.uniform(0.75, 1.05), seed=5420 + 20 * k + 2 * m, lean=r.choice((-1, 1))) - 0.75
    return ops, t + 1.0, "motes"


NEW_SCENES3 = {"tianshan_winter": (scene_tianshan_winter, 0.55), "frozen_lake": (scene_frozen_lake, 0.45), "bullfinches": (scene_bullfinches, 0.5),
               "street_lamp": (scene_street_lamp, 0.6), "moon_forest": (scene_moon_forest, 0.55), "lone_tree": (scene_lone_tree, 0.5),
               "steppe_horses": (scene_steppe_horses, 0.5), "frost_window": (scene_frost_window, 0.5), "snowdrops": (scene_snowdrops, 0.36)}


def _clip_all(fn):
    """Всё (и заливки, и мазки) обрезается по краю картины — деревья на краю уходят за рамку, как на листе со скотчем."""
    def wrapped(box, hor, t0=0.8, seed=0):
        ops, end, parts = fn(box, hor, t0=t0, seed=seed)
        px0, px1, py0, py1 = box
        for op in ops:
            if isinstance(op, Bloom):
                if op.clip is None:
                    op.clip_to(px0, py0, px1, py1)
                continue
            x0, y0, x1, y1 = op.box
            if x0 >= px0 and y0 >= py0 and x1 <= px1 and y1 <= py1:
                continue
            Y, X = np.mgrid[y0:y1, x0:x1]
            m = ((X >= px0) & (X < px1) & (Y >= py0) & (Y < py1)).astype(np.float32)
            orig = op.alpha
            op.alpha = (lambda o, mm: (lambda t: o(t) * mm))(orig, m)
        return ops, end, parts
    return wrapped


NEW_SCENES3 = {k: (_clip_all(f), fr) for k, (f, fr) in NEW_SCENES3.items()}
qc.SCENES.update(NEW_SCENES3)
