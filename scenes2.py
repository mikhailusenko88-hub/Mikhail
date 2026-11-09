# -*- coding: utf-8 -*-
"""Новые акварельные сцены (второй месяц): Казахстан, зима и Новый год, сад, маки, лодка, каньон.
Подключаются в quotecard.SCENES при импорте (в конце quotecard.py)."""
import math
import random

import numpy as np

import quotecard as qc
from quotecard import Bloom, Dots, Stroke, Wash, birds, round_tree, sky, spruce, spruce_row, stars, sun, water


def hills(ops, t0, box, hor, ry, mx, cols, dens=0.6, seed=0, blur=2.5, dur=1.3, edge=0.3):
    px0, px1, py0, py1 = box
    ops.append(Wash(t0, dur, list(zip(mx, ry)) + [(px1, hor), (px0, hor)], cols, dens=dens, blur=blur, rough=0.12, direction="right", seed=seed, edge=edge))


def reflection(ops, t0, box, hor, ry, mx, col, dens=0.3, seed=0):
    px0, px1, py0, py1 = box
    ops.append(Wash(t0, 1.0, [(x, 2 * hor - y) for x, y in zip(mx, ry)] + [(px1, hor + 3), (px0, hor + 3)], [col], dens=dens, blur=6, rough=0.2, direction="right",
                    seed=seed, streak=0.5, edge=0.05))


def _sizes(box, hor):
    px0, px1, py0, py1 = box
    return px1 - px0, hor - py0, py1 - hor, px0 + (px1 - px0) / 2


def snow_tree(ops, t0, x, base, h, col=(0.12, 0.30, 0.24), snow=True, seed=0):
    """Ель ярусами, с шапками снега на лапах."""
    tiers = 5
    th = h / tiers * 1.35
    for k in range(tiers):
        top = base - h + k * h / tiers * 0.92
        bot = top + th
        hw = h * (0.10 + 0.075 * k)
        poly = [(x, top), (x + hw, bot), (x + hw * 0.5, bot - th * 0.12), (x, bot - 2), (x - hw * 0.5, bot - th * 0.12), (x - hw, bot)]
        ops.append(Wash(t0 + k * 0.1, 0.4, poly, [col], dens=0.9, blur=1.0, rough=0.06, direction="down", seed=seed + k, edge=0.3))
        if snow:
            ops.append(Stroke(t0 + 0.5 + k * 0.08, 0.3, [(x - hw * 0.9, bot - th * 0.05), (x - hw * 0.4, bot - th * 0.18), (x, bot - th * 0.06), (x + hw * 0.4, bot - th * 0.18), (x + hw * 0.9, bot - th * 0.05)],
                              [max(3, h * 0.03)], (0.97, 0.98, 1.0), dens=0.9, blur=1.0, kind="over", seed=seed + 20 + k))
    ops.append(Stroke(t0 + 0.3, 0.2, [(x, base + 2), (x, base - h * 0.08)], [max(4, h * 0.05)], (0.28, 0.20, 0.18), dens=0.9, blur=0.6, seed=seed + 40))
    return t0 + 0.5 + tiers * 0.08 + 0.3


def small_house(ops, t0, cx, cb, wd, hh, seed=0, wall=((0.46, 0.30, 0.22), (0.34, 0.22, 0.18))):
    """Деревянный домик со снежной крышей, тёплым окном и дымом."""
    ops.append(Wash(t0, 0.5, [(cx - wd, cb), (cx + wd, cb), (cx + wd, cb - hh), (cx - wd, cb - hh)], list(wall), dens=0.95, blur=1.0, rough=0.05, direction="up", seed=seed, edge=0.2))
    for j in range(3):
        yl = cb - hh * (0.25 + 0.25 * j)
        ops.append(Stroke(t0 + 0.4 + j * 0.04, 0.2, [(cx - wd, yl), (cx + wd, yl)], [2], (0.20, 0.14, 0.12), dens=0.5, blur=0.5, seed=seed + 3 + j))
    roof = [(cx - wd - wd * 0.22, cb - hh + 4), (cx, cb - hh - wd * 0.75), (cx + wd + wd * 0.22, cb - hh + 4)]
    ops.append(Wash(t0 + 0.5, 0.4, roof, [(0.36, 0.26, 0.28)], dens=0.95, blur=1.0, rough=0.05, direction="up", seed=seed + 8, edge=0.2))
    snowr = [(cx - wd - wd * 0.28, cb - hh + 2), (cx, cb - hh - wd * 0.82), (cx + wd + wd * 0.28, cb - hh + 2), (cx + wd + wd * 0.1, cb - hh + 8), (cx, cb - hh - wd * 0.56), (cx - wd - wd * 0.1, cb - hh + 8)]
    ops.append(Wash(t0 + 0.8, 0.4, snowr, [(0.98, 0.98, 1.0)], dens=0.96, blur=1.2, rough=0.1, direction="right", seed=seed + 9, kind="over", edge=0.0))
    ww = wd * 0.3
    wy = cb - hh * 0.55
    ops.append(Wash(t0 + 1.1, 0.3, [(cx - ww, wy - ww * 0.8), (cx + ww, wy - ww * 0.8), (cx + ww, wy + ww * 0.8), (cx - ww, wy + ww * 0.8)], [(1.0, 0.84, 0.44)], dens=0.98, blur=0.7,
                    rough=0.03, direction="down", seed=seed + 10, kind="over", edge=0.0))
    ops.append(Bloom(t0 + 1.3, cx, wy, wd * 0.9, (1.0, 0.80, 0.40), dens=0.28, dur=0.7, seed=seed + 11, kind="over", soft=4.0))
    ops.append(Stroke(t0 + 1.4, 0.15, [(cx, wy - ww * 0.8), (cx, wy + ww * 0.8)], [2], (0.30, 0.20, 0.18), dens=0.9, blur=0.4, seed=seed + 12))
    sx = cx + wd * 0.5
    sy = cb - hh - wd * 0.45
    for j in range(3):
        ops.append(Bloom(t0 + 1.5 + j * 0.2, sx + j * wd * 0.12, sy - wd * 0.25 - j * wd * 0.32, wd * (0.12 + j * 0.07), (0.92, 0.90, 0.94), dens=0.4 - j * 0.08, dur=0.8, seed=seed + 14 + j,
                         kind="over", soft=2.5))
    return t0 + 2.2


# ------------------------------------------------------------------ Большое Алматинское озеро
def scene_almaty_lake(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.50, 0.66, 0.90), (0.70, 0.80, 0.93), (0.92, 0.93, 0.94)], dens=0.6, seed=2011 + seed)
    qc.cloud(ops, t0 + 1.3, px0 + 190, py0 + Hs * 0.18, 60, box, hor, seed=31, shadow=False)
    qc.cloud(ops, t0 + 1.6, px0 + 700, py0 + Hs * 0.12, 48, box, hor, seed=32, shadow=False)
    mx = np.linspace(px0, px1, 140)
    pk_x = cx + 40
    base_far = hor - 0.30 * Hs
    central = 0.56 * Hs * np.maximum(0, 1 - np.abs(mx - pk_x) / 300) ** 1.15
    peaks = base_far - central - 0.14 * Hs * np.abs(np.sin(mx / 64 + 1.3)) - 10 * np.cos(mx / 13)
    peaks = np.maximum(peaks, py0 + 18)
    hills(ops, t0 + 2.2, box, hor, peaks, mx, [(0.58, 0.62, 0.80), (0.46, 0.52, 0.72)], dens=0.72, seed=2012, blur=1.6, edge=0.35)
    cap = [(x, y) for x, y in zip(mx, peaks)] + [(x, y + 22 + 0.30 * (base_far - y) + 14 * math.sin(x / 19)) for x, y in zip(mx[::-1], peaks[::-1])]
    ops.append(Wash(t0 + 3.2, 1.0, cap, [(0.99, 0.99, 1.0)], dens=0.92, blur=1.4, rough=0.3, direction="right", seed=2013, kind="over", edge=0.0))
    # тень на гранях вершины
    shade = [(x, y + 6) for x, y in zip(mx, peaks) if x > pk_x] + [(px1 + 10, base_far + 40), (pk_x + 30, base_far + 40)]
    if len(shade) > 3:
        ops.append(Wash(t0 + 3.9, 0.8, shade, [(0.60, 0.64, 0.82)], dens=0.35, blur=3, rough=0.2, direction="right", seed=2014, edge=0.0))
    # лесистые склоны с двух сторон, сходятся к воде
    ys = hor - 0.40 * Hs
    left = [(px0, ys), (px0 + Wd * 0.16, ys + 0.16 * Hs), (px0 + Wd * 0.28, hor - 0.06 * Hs), (px0 + Wd * 0.36, hor + 2), (px0, hor + 2)]
    right = [(px1, ys - 0.05 * Hs), (px1 - Wd * 0.15, ys + 0.13 * Hs), (px1 - Wd * 0.26, hor - 0.05 * Hs), (px1 - Wd * 0.34, hor + 2), (px1, hor + 2)]
    for j, poly in enumerate((left, right)):
        ops.append(Wash(t0 + 4.4 + j * 0.3, 1.0, poly, [(0.30, 0.48, 0.40), (0.24, 0.42, 0.36), (0.30, 0.50, 0.44)], dens=0.8, blur=1.6, rough=0.12, direction="down", seed=2015 + j, edge=0.3))
    r = random.Random(2020 + seed)
    t = t0 + 5.2
    for side, poly in ((-1, left), (1, right)):
        for k in range(16):
            u = r.random()
            a, b = (poly[1], poly[3])
            x = a[0] + (b[0] - a[0]) * u + r.uniform(-14, 14)
            y = a[1] + (b[1] - a[1]) * u + r.uniform(4, 40) * (1 - u * 0.6)
            h = (26 + 34 * (1 - u)) * (Hs / 420)
            spruce(ops, t + k * 0.04, x, y, max(18, h), (0.10, 0.24, 0.20), seed=2030 + k + (side > 0) * 50)
        t += 0.7
    water(ops, t0 + 6.4, box, hor, [(0.46, 0.84, 0.84), (0.30, 0.72, 0.76), (0.18, 0.56, 0.64)], dens=0.8, seed=2016, streak=0.35)
    reflection(ops, t0 + 7.4, box, hor, peaks, mx, (0.62, 0.74, 0.86), dens=0.22, seed=2017)
    for j, poly in enumerate((left, right)):
        ops.append(Wash(t0 + 7.7 + j * 0.15, 0.8, [(x, 2 * hor - y) for x, y in poly], [(0.14, 0.40, 0.38)], dens=0.28, blur=6, rough=0.2, direction="down", seed=2018 + j, streak=0.5, edge=0.05))
    for j in range(10):
        yv = hor + 30 + r.random() * (Hg - 50)
        ln = 18 + (yv - hor) / max(1, Hg) * 60
        x = r.uniform(px0 + 30 + ln, px1 - 30 - ln)
        ops.append(Stroke(t0 + 8.3 + j * 0.05, 0.3, [(x - ln, yv), (x + ln, yv)], [3], (0.92, 0.99, 0.99), dens=0.55, blur=1, kind="over", seed=2040 + j))
    end = birds(ops, t0 + 8.9, [(px0 + 260, py0 + Hs * 0.30, 12), (px0 + 320, py0 + Hs * 0.36, 10)])
    return ops, end, "motes"


# ------------------------------------------------------------------ степь с юртами на закате
def yurt(ops, t0, cx, base, R, seed=0):
    wall_top = base - R * 0.55
    dome = [(cx + R * math.cos(a), wall_top - R * 0.62 * math.sin(a)) for a in np.linspace(0, math.pi, 24)]
    body = [(cx - R, base), (cx + R, base), (cx + R, wall_top)] + dome + [(cx - R, wall_top)]
    ops.append(Wash(t0, 0.6, body, [(0.99, 0.97, 0.92), (0.95, 0.91, 0.84)], dens=0.97, blur=1.0, rough=0.06, direction="up", seed=seed, kind="over", edge=0.0))
    ops.append(Wash(t0 + 0.6, 0.5, [(cx + R * 0.25, base), (cx + R, base), (cx + R, wall_top)] + [p for p in dome if p[0] > cx + R * 0.25] + [(cx + R * 0.25, wall_top - R * 0.55)],
                    [(0.80, 0.76, 0.86)], dens=0.38, blur=2.0, rough=0.08, direction="right", seed=seed + 1, edge=0.0))
    # узорная полоса по верху стены и решётка-кереге
    ops.append(Stroke(t0 + 0.9, 0.3, [(cx - R, wall_top + 3), (cx + R, wall_top + 3)], [max(4, R * 0.07)], (0.70, 0.24, 0.20), dens=0.85, blur=0.7, seed=seed + 2))
    for k in range(7):
        xx = cx - R + (k + 0.5) * 2 * R / 7
        ops.append(Stroke(t0 + 1.0 + k * 0.03, 0.15, [(xx - R * 0.12, base - 4), (xx + R * 0.12, wall_top + 8)], [2], (0.62, 0.52, 0.44), dens=0.35, blur=0.6, seed=seed + 5 + k))
    # купол: рёбра-уыки
    top = (cx, wall_top - R * 0.62)
    for k in range(5):
        a = math.pi * (0.15 + 0.7 * k / 4)
        ops.append(Stroke(t0 + 1.2 + k * 0.03, 0.15, [(top[0], top[1] + 4), (cx + R * 0.98 * math.cos(a), wall_top - R * 0.62 * math.sin(a) * 0.15)], [2], (0.70, 0.64, 0.60),
                          dens=0.3, blur=0.7, seed=seed + 15 + k))
    ops.append(Wash(t0 + 1.4, 0.3, [(cx - R * 0.18, top[1] + 2), (cx + R * 0.18, top[1] + 2), (cx + R * 0.12, top[1] - R * 0.05), (cx - R * 0.12, top[1] - R * 0.05)],
                    [(0.40, 0.30, 0.28)], dens=0.9, blur=0.8, rough=0.05, direction="right", seed=seed + 22, edge=0.0))
    # дверь
    dw, dh = R * 0.17, R * 0.42
    dx = cx - R * 0.25
    ops.append(Wash(t0 + 1.6, 0.3, [(dx - dw, base), (dx + dw, base), (dx + dw, base - dh), (dx - dw, base - dh)], [(0.86, 0.44, 0.22), (0.72, 0.30, 0.18)], dens=0.96, blur=0.7,
                    rough=0.03, direction="down", seed=seed + 23, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 1.8, 0.2, [(dx - dw, base - dh * 0.5), (dx + dw, base - dh * 0.5)], [2], (0.96, 0.80, 0.40), dens=0.8, blur=0.5, seed=seed + 24))
    for j in range(3):
        ops.append(Bloom(t0 + 2.0 + j * 0.2, top[0] + j * R * 0.08, top[1] - R * 0.25 - j * R * 0.3, R * (0.10 + j * 0.06), (0.94, 0.92, 0.94), dens=0.35 - j * 0.08, dur=0.8,
                         seed=seed + 26 + j, kind="over", soft=2.5))
    ops.append(Stroke(t0 + 2.2, 0.4, [(cx - R * 1.05, base + 3), (cx + R * 1.4, base + 6)], [max(6, R * 0.12)], (0.56, 0.42, 0.40), dens=0.3, blur=4, seed=seed + 30))
    return t0 + 2.6


def scene_steppe_yurts(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.56, 0.62, 0.86), (0.84, 0.74, 0.84), (0.99, 0.80, 0.62), (0.99, 0.88, 0.62)], dens=0.62, seed=2101 + seed)
    ops.append(Bloom(t0 + 1.4, px0 + Wd * 0.25, py0 + Hs * 0.35, Wd * 0.25, (0.96, 0.70, 0.72), dens=0.22, dur=1.6, seed=2102, soft=2.0).clip_to(px0, py0, px1, hor))
    sun(ops, t0 + 1.8, px0 + Wd * 0.74, hor - Hs * 0.16, r=34, halo=120, col=(1.0, 0.96, 0.84), hcol=(1.0, 0.86, 0.62), seed=seed)
    mx = np.linspace(px0, px1, 90)
    far = qc.ridge(mx, hor - 10, 0.10 * Hs, 230, 70, 0.4 + seed)
    hills(ops, t0 + 2.6, box, hor, far, mx, [(0.66, 0.56, 0.74), (0.58, 0.50, 0.70)], dens=0.5, seed=2103, blur=3)
    ops.append(Wash(t0 + 3.4, 1.6, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.96, 0.82, 0.56), (0.88, 0.70, 0.42), (0.74, 0.56, 0.34)],
                    dens=0.62, blur=4, rough=0.2, seed=2104, streak=0.2, edge=0.25))
    ops.append(Bloom(t0 + 4.4, px0 + Wd * 0.74, hor + Hg * 0.10, Wd * 0.3, (1.0, 0.88, 0.62), dens=0.3, dur=1.2, seed=2105, kind="over", soft=3.0).clip_to(px0, hor, px1, py1))
    s = Hg / 600
    end = yurt(ops, t0 + 4.8, px0 + Wd * 0.62, hor + Hg * 0.20, 70 * s + 20, seed=2110)
    end = yurt(ops, end - 1.2, px0 + Wd * 0.30, hor + Hg * 0.42, 120 * s + 30, seed=2140)
    r = random.Random(2160 + seed)
    for j in range(46):
        u = r.random() ** 0.6
        yv = hor + Hg * (0.30 + 0.68 * u)
        x = r.uniform(px0 + 8, px1 - 8)
        h = 8 + 34 * u
        ops.append(Stroke(end + j * 0.02, 0.2, [(x, yv), (x + r.uniform(-6, 6), yv - h)], [2 + 2 * u], r.choice([(0.60, 0.46, 0.26), (0.72, 0.58, 0.30), (0.50, 0.40, 0.24)]), dens=0.6,
                          blur=0.7, seed=2170 + j))
    end = birds(ops, end + 1.2, [(px0 + Wd * 0.42, py0 + Hs * 0.30, 18)], col=(0.32, 0.26, 0.30))
    return ops, end, "motes"


# ------------------------------------------------------------------ яблоневый сад под горами
def scene_apple_orchard(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.60, 0.74, 0.92), (0.80, 0.86, 0.94), (0.96, 0.94, 0.88)], dens=0.55, seed=2201 + seed)
    mx = np.linspace(px0, px1, 120)
    peaks = hor - 0.30 * Hs - 0.45 * Hs * np.abs(np.sin(mx / 150 + 0.4)) - 0.10 * Hs * np.abs(np.sin(mx / 41 + 1)) - 6 * np.cos(mx / 12)
    peaks = np.maximum(peaks, py0 + 15)
    hills(ops, t0 + 1.8, box, hor, peaks, mx, [(0.62, 0.68, 0.84), (0.54, 0.60, 0.78)], dens=0.55, seed=2202, blur=2.5)
    cap = [(x, y) for x, y in zip(mx, peaks)] + [(x, y + 16 + 0.25 * (hor - 0.3 * Hs - y) + 10 * math.sin(x / 17)) for x, y in zip(mx[::-1], peaks[::-1])]
    ops.append(Wash(t0 + 2.7, 0.8, cap, [(0.98, 0.98, 1.0)], dens=0.85, blur=1.4, rough=0.3, direction="right", seed=2203, kind="over", edge=0.0))
    near = qc.ridge(mx, hor - 6, 0.10 * Hs, 120, 40, 2.2 + seed)
    hills(ops, t0 + 3.3, box, hor, near, mx, [(0.42, 0.58, 0.44), (0.36, 0.52, 0.40)], dens=0.65, seed=2204, blur=2)
    ops.append(Wash(t0 + 3.9, 1.4, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.70, 0.82, 0.48), (0.54, 0.72, 0.38), (0.40, 0.60, 0.32)],
                    dens=0.6, blur=4, rough=0.2, seed=2205, streak=0.15, edge=0.25))
    r = random.Random(2210 + seed)
    t = t0 + 5.0
    greens = [(0.30, 0.56, 0.30), (0.40, 0.64, 0.32), (0.24, 0.48, 0.28), (0.36, 0.60, 0.36)]
    crowns = []
    for j in range(5):
        d = (1 - j / 4) ** 1.4
        h = 46 + 250 * d * (Hg / 650)
        for side in (-1, 1):
            x = cx + side * (64 + 270 * d) + r.uniform(-12, 12)
            base = hor + 8 + (Hg - 40) * d
            round_tree(ops, t, x, base, h, [greens[(j + (side > 0)) % 4], greens[(j + 2) % 4], greens[(j + 1) % 4]], seed=2220 + j * 2 + (side > 0), spread=1.1)
            crowns.append((x, base - h * 0.80, h * 0.42, d))
            t += 0.22
    apples = []
    for (x, y, R_, d) in crowns:
        for _ in range(int(6 + 16 * d)):
            a, rr_ = r.uniform(0, 6.28), R_ * math.sqrt(r.random()) * 0.95
            apples.append((x + rr_ * math.cos(a), y + rr_ * math.sin(a) * 0.85, 1.6 + 5.5 * d, r.choice([(0.88, 0.18, 0.16), (0.94, 0.34, 0.18), (0.80, 0.14, 0.18)]), r.random()))
    ops.append(Dots(t + 0.2, 1.4, apples, blur=0.7))
    path = []
    for k in np.linspace(0, 1, 18):
        yv = py1 + 10 - k * (Hg + 6)
        hw = 3 + 120 * (1 - k) ** 1.8
        path.append((cx - hw, yv))
    path += [(2 * cx - x, y) for x, y in path[::-1]]
    ops.append(Wash(t + 1.0, 1.0, path, [(0.88, 0.84, 0.62)], dens=0.6, blur=2.5, rough=0.2, direction="up", seed=2290, kind="over", edge=0.0))
    end = birds(ops, t + 2.0, [(px0 + 200, py0 + Hs * 0.35, 11), (px0 + 250, py0 + Hs * 0.42, 9)])
    return ops, end, "petals"


# ------------------------------------------------------------------ маковое поле
def scene_poppies(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.62, 0.76, 0.94), (0.84, 0.88, 0.94), (0.98, 0.94, 0.84)], dens=0.55, seed=2301 + seed)
    qc.cloud(ops, t0 + 1.3, px0 + Wd * 0.7, py0 + Hs * 0.30, 70, box, hor, seed=33)
    mx = np.linspace(px0, px1, 90)
    far = qc.ridge(mx, hor - 8, 0.18 * Hs, 210, 66, 0.9 + seed)
    hills(ops, t0 + 2.0, box, hor, far, mx, [(0.60, 0.70, 0.80), (0.54, 0.66, 0.72)], dens=0.5, seed=2302, blur=3)
    ops.append(Wash(t0 + 2.8, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.80, 0.84, 0.50), (0.60, 0.74, 0.38), (0.44, 0.62, 0.32)],
                    dens=0.6, blur=4, rough=0.2, seed=2303, streak=0.15, edge=0.25))
    r = random.Random(2310 + seed)
    # дальние маки — красная дымка у горизонта
    far_dots = []
    for _ in range(260):
        u = r.random() ** 1.6
        far_dots.append((r.uniform(px0 + 5, px1 - 5), hor + Hg * (0.03 + 0.45 * u), 1.2 + 3.2 * u, r.choice([(0.90, 0.20, 0.16), (0.94, 0.30, 0.18)]), r.random()))
    ops.append(Dots(t0 + 4.8, 1.2, far_dots, blur=0.7))
    t = t0 + 5.8
    items = sorted([(r.uniform(px0 + 20, px1 - 20), hor + Hg * (0.45 + 0.52 * r.random())) for _ in range(30)], key=lambda p: p[1])
    for j, (x, y) in enumerate(items):
        u = (y - hor) / Hg
        R_ = 6 + 26 * u ** 1.5
        ops.append(Stroke(t + j * 0.05, 0.25, [(x, y + R_ * 0.5), (x + r.uniform(-8, 8), y + R_ * 2.6)], [max(2, R_ * 0.12)], (0.30, 0.50, 0.26), dens=0.8, blur=0.6, seed=2330 + j))
        ops.append(Bloom(t + 0.15 + j * 0.05, x, y, R_, r.choice([(0.92, 0.18, 0.14), (0.96, 0.28, 0.16), (0.86, 0.14, 0.16)]), dens=0.9, dur=0.5, seed=2360 + j, kind="over", soft=1.0))
        ops.append(Bloom(t + 0.45 + j * 0.05, x + R_ * 0.1, y - R_ * 0.1, max(2, R_ * 0.22), (0.20, 0.12, 0.14), dens=0.9, dur=0.3, seed=2400 + j, kind="over", soft=0.8))
    end = birds(ops, t + 2.2, [(px0 + 220, py0 + Hs * 0.25, 12), (px0 + 280, py0 + Hs * 0.32, 10)])
    return ops, end, "motes"


# ------------------------------------------------------------------ лодка на закате, камыши
def scene_boat_dusk(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.40, 0.40, 0.66), (0.70, 0.54, 0.72), (0.96, 0.66, 0.62), (0.99, 0.82, 0.60)], dens=0.68, seed=2501 + seed)
    sun(ops, t0 + 1.8, px0 + Wd * 0.58, hor - 18, r=40, halo=130, col=(1.0, 0.94, 0.80), hcol=(1.0, 0.80, 0.58), seed=seed)
    mx = np.linspace(px0, px1, 90)
    shore = qc.ridge(mx, hor + 2, 0.06 * Hs, 260, 80, 1.7 + seed)
    hills(ops, t0 + 2.6, box, hor, shore, mx, [(0.34, 0.26, 0.42)], dens=0.75, seed=2502, blur=1.6)
    spruce_row(ops, t0 + 3.0, box, hor + 2, (0.24, 0.18, 0.32), hmin=10, hmax=46, step=12, seed=2503, dens=0.8)
    water(ops, t0 + 3.8, box, hor, [(0.99, 0.80, 0.62), (0.90, 0.62, 0.66), (0.62, 0.48, 0.70), (0.38, 0.36, 0.62)], dens=0.68, seed=2504, streak=0.35)
    reflection(ops, t0 + 4.8, box, hor, shore - 30, mx, (0.30, 0.24, 0.40), dens=0.4, seed=2505)
    r = random.Random(2510 + seed)
    for j in range(14):
        yv = hor + 10 + j * Hg * 0.035
        hw = 20 + j * 10
        x = px0 + Wd * 0.58 + r.uniform(-hw * 0.4, hw * 0.4)
        ln = r.uniform(0.3, 0.8) * hw
        ops.append(Stroke(t0 + 5.4 + j * 0.05, 0.25, [(x - ln, yv), (x + ln, yv)], [3 if j < 7 else 4], (1.0, 0.94, 0.82), dens=r.uniform(0.5, 0.85), blur=1, kind="over", seed=2520 + j))
    # лодка
    bx, by = px0 + Wd * 0.38, hor + Hg * 0.36
    L = 120 * (Hg / 600) + 40
    hull = [(bx - L, by - L * 0.10), (bx + L, by - L * 0.14), (bx + L * 0.75, by + L * 0.10), (bx - L * 0.72, by + L * 0.10)]
    ops.append(Wash(t0 + 6.4, 0.5, hull, [(0.22, 0.16, 0.24)], dens=0.95, blur=0.9, rough=0.04, direction="right", seed=2540, edge=0.0))
    ops.append(Stroke(t0 + 6.8, 0.3, [(bx - L * 0.2, by - L * 0.12), (bx - L * 1.1, by + L * 0.32)], [3], (0.24, 0.18, 0.24), dens=0.9, blur=0.6, seed=2541))
    ops.append(Stroke(t0 + 6.9, 0.3, [(bx + L * 0.2, by - L * 0.12), (bx + L * 0.95, by + L * 0.34)], [3], (0.24, 0.18, 0.24), dens=0.9, blur=0.6, seed=2542))
    ops.append(Wash(t0 + 7.1, 0.6, [(x, 2 * by - y + L * 0.18) for x, y in hull], [(0.30, 0.24, 0.36)], dens=0.4, blur=4, rough=0.25, direction="right", seed=2543, streak=0.5, edge=0.0))
    # камыши
    t = t0 + 7.5
    for j in range(26):
        x = px0 + 10 + r.random() ** 1.6 * Wd * 0.34
        y0_ = py1 - r.uniform(0, 30)
        h = r.uniform(0.18, 0.42) * Hg
        bend = r.uniform(-30, 30)
        pts = [(x, y0_), (x + bend * 0.3, y0_ - h * 0.5), (x + bend, y0_ - h)]
        ops.append(Stroke(t + j * 0.03, 0.3, pts, [4, 3, 2], (0.22, 0.18, 0.28), dens=0.85, blur=0.6, seed=2550 + j))
        if j % 3 == 0:
            ops.append(Stroke(t + 0.2 + j * 0.03, 0.2, [(x + bend * 0.85, y0_ - h * 0.82), (x + bend * 0.95, y0_ - h * 0.97)], [9], (0.34, 0.22, 0.20), dens=0.9, blur=0.8, seed=2590 + j))
    end = birds(ops, t + 1.4, [(px0 + Wd * 0.75, py0 + Hs * 0.35, 12), (px0 + Wd * 0.81, py0 + Hs * 0.42, 9)], col=(0.30, 0.24, 0.36))
    return ops, end, "fireflies"


# ------------------------------------------------------------------ зимняя деревня
def scene_winter_village(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    sky(ops, t0, box, hor, [(0.64, 0.70, 0.90), (0.86, 0.80, 0.90), (0.99, 0.84, 0.76), (0.99, 0.90, 0.78)], dens=0.6, seed=2601 + seed)
    sun(ops, t0 + 1.6, px0 + Wd * 0.22, hor - Hs * 0.2, r=30, halo=110, col=(1.0, 0.97, 0.88), hcol=(1.0, 0.88, 0.72), seed=seed)
    spruce_row(ops, t0 + 2.3, box, hor + 4, (0.50, 0.54, 0.74), hmin=20, hmax=70, step=13, seed=2602, dens=0.6)
    mx = np.linspace(px0, px1, 90)
    ops.append(Wash(t0 + 3.0, 1.4, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.94, 0.94, 0.98), (0.88, 0.90, 0.98), (0.82, 0.86, 0.96)], dens=0.35, blur=4, rough=0.2,
                    seed=2603, streak=0.2, edge=0.1))
    # холмы снега с голубыми тенями
    for j in range(3):
        yb = hor + Hg * (0.25 + 0.25 * j)
        ry = yb - Hg * 0.10 * np.abs(np.sin(mx / (160 + 40 * j) + j))
        ops.append(Wash(t0 + 4.0 + j * 0.25, 0.8, [(x, y + Hg * 0.04) for x, y in zip(mx, ry)] + [(px1 + 10, yb + Hg * 0.10), (px0 - 10, yb + Hg * 0.10)], [(0.74, 0.80, 0.94)],
                        dens=0.18, blur=9, rough=0.2, direction="right", seed=2604 + j, edge=0.0))
    s = Hg / 650
    t = t0 + 4.8
    houses = [(px0 + Wd * 0.70, hor + Hg * 0.14, 36 * s + 10), (px0 + Wd * 0.30, hor + Hg * 0.22, 46 * s + 12), (px0 + Wd * 0.55, hor + Hg * 0.42, 70 * s + 16)]
    for j, (hx, hb, wd) in enumerate(houses):
        t = small_house(ops, t, hx, hb, wd, wd * 0.8, seed=2610 + j * 30) - 1.2
    t += 1.3
    r = random.Random(2700 + seed)
    for j, (x, b, h) in enumerate(((px0 + Wd * 0.12, py1 - Hg * 0.05, Hg * 0.55), (px0 + Wd * 0.86, py1 - Hg * 0.08, Hg * 0.45), (px0 + Wd * 0.22, hor + Hg * 0.30, Hg * 0.20))):
        t = snow_tree(ops, t - 0.6, x, b, h, seed=2720 + j * 50)
    return ops, t + 0.8, "snow"


# ------------------------------------------------------------------ новогодняя ёлка в ночном лесу
def scene_xmas_tree(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    ops.append(Wash(t0, 2.2, [(px0, py0), (px1, py0), (px1, hor + 6), (px0, hor + 6)], [(0.10, 0.14, 0.32), (0.16, 0.20, 0.42), (0.30, 0.32, 0.56)], dens=0.9, blur=4, rough=0.14,
                    seed=2801 + seed))
    stars(ops, t0 + 1.8, box, hor, n=70, seed=seed, frac=0.85)
    ops.append(Bloom(t0 + 2.4, px0 + Wd * 0.82, py0 + Hs * 0.18, 70, (0.95, 0.94, 0.86), dens=0.35, dur=1.0, seed=2802, kind="over", soft=4.0))
    ops.append(Bloom(t0 + 2.7, px0 + Wd * 0.82, py0 + Hs * 0.18, 24, (1.0, 0.99, 0.92), dens=1.0, dur=0.6, seed=2803, kind="over", soft=0.9))
    spruce_row(ops, t0 + 3.0, box, hor - 4, (0.08, 0.12, 0.26), hmin=40, hmax=130, step=15, seed=2804, dens=0.9)
    ops.append(Wash(t0 + 3.8, 1.2, [(px0, hor - 8), (px1, hor - 8), (px1, py1), (px0, py1)], [(0.70, 0.74, 0.92), (0.80, 0.82, 0.94), (0.74, 0.78, 0.92)], dens=0.32, blur=4, rough=0.2,
                    seed=2805, streak=0.2, edge=0.1))
    # тёплое сияние вокруг ёлки
    th = (py1 - py0) * 0.62
    tb = py1 - Hg * 0.12
    ops.append(Bloom(t0 + 4.6, cx, tb - th * 0.45, th * 0.55, (1.0, 0.84, 0.50), dens=0.3, dur=1.2, seed=2806, kind="over", soft=4.0))
    t = snow_tree(ops, t0 + 5.0, cx, tb, th, col=(0.08, 0.30, 0.22), seed=2810)
    # гирлянда-огоньки по ярусам
    r = random.Random(2850 + seed)
    lights = []
    cols = [(1.0, 0.86, 0.36), (1.0, 0.40, 0.30), (0.44, 0.70, 1.0), (1.0, 0.96, 0.80), (0.50, 0.92, 0.56)]
    for k in range(5):
        y_top = tb - th + k * th / 5 * 0.92
        bot = y_top + th / 5 * 1.35
        hw = th * (0.10 + 0.075 * k)
        for m in range(6 + k * 2):
            u = (m + 0.5) / (6 + k * 2)
            x = cx - hw * 0.85 + 2 * hw * 0.85 * u
            y = bot - th / 5 * 0.30 - (bot - y_top) * 0.25 * math.sin(u * math.pi)
            lights.append((x, y, 3.0 + th / 260, r.choice(cols), r.random()))
    ops.append(Dots(t, 1.4, lights, blur=1.2))
    for j in range(0, len(lights), 3):
        x, y = lights[j][0], lights[j][1]
        ops.append(Bloom(t + 0.4 + j * 0.01, x, y, 10 + th / 60, lights[j][3], dens=0.35, dur=0.5, seed=2900 + j, kind="over", soft=3.0))
    # звезда на макушке
    sx, sy = cx, tb - th - 6
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr_ = (16 + th / 40) * (1 if k % 2 == 0 else 0.45)
        pts.append((sx + rr_ * math.cos(a), sy + rr_ * math.sin(a)))
    ops.append(Wash(t + 1.4, 0.4, pts, [(1.0, 0.88, 0.40)], dens=0.98, blur=0.8, rough=0.03, direction="down", seed=2990, kind="over", edge=0.0))
    ops.append(Bloom(t + 1.6, sx, sy, 40 + th / 20, (1.0, 0.90, 0.56), dens=0.45, dur=0.6, seed=2991, kind="over", soft=3.5))
    # подарки
    for j, (gx, gw, c) in enumerate(((cx - th * 0.22, th * 0.07, (0.86, 0.24, 0.24)), (cx + th * 0.20, th * 0.06, (0.30, 0.50, 0.86)), (cx + th * 0.05, th * 0.05, (0.96, 0.80, 0.30)))):
        gy = tb + 4
        ops.append(Wash(t + 1.8 + j * 0.15, 0.3, [(gx - gw, gy), (gx + gw, gy), (gx + gw, gy - gw * 1.4), (gx - gw, gy - gw * 1.4)], [c], dens=0.95, blur=0.8, rough=0.03,
                        direction="up", seed=2995 + j, kind="over", edge=0.0))
        ops.append(Stroke(t + 2.0 + j * 0.15, 0.2, [(gx, gy), (gx, gy - gw * 1.4)], [3], (1.0, 0.96, 0.86), dens=0.9, blur=0.5, kind="over", seed=3000 + j))
    return ops, t + 2.6, "snow"


# ------------------------------------------------------------------ Чарынский каньон
def scene_canyon(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    Wd, Hs, Hg, cx = _sizes(box, hor)
    ops = []
    vy = hor + 0.30 * Hg          # где река уходит за поворот
    sky(ops, t0, box, int(vy), [(0.46, 0.62, 0.90), (0.68, 0.78, 0.94), (0.96, 0.90, 0.80)], dens=0.6, seed=3101 + seed)
    qc.cloud(ops, t0 + 1.2, px0 + Wd * 0.28, py0 + Hs * 0.40, 50, box, hor, seed=34, shadow=False)
    r = random.Random(3110 + seed)
    # дальние столовые горы
    mx = np.linspace(cx - 230, cx + 250, 80)
    mesa = vy - 0.10 * Hs - 0.22 * Hs * (np.abs(np.sin(mx / 85 + 0.6)) > 0.5) - 0.04 * Hs * np.sin(mx / 23)
    ops.append(Wash(t0 + 2.0, 1.2, list(zip(mx, mesa)) + [(mx[-1], vy), (mx[0], vy)], [(0.84, 0.62, 0.62), (0.76, 0.56, 0.60)], dens=0.5, blur=2, rough=0.12,
                    direction="right", seed=3102, edge=0.3))
    # русло: от поворота вниз, расширяясь
    ks = np.linspace(0, 1, 24)
    cen = [cx + 20 + 70 * math.sin(k * 3.6 + 0.4) * k for k in ks]
    ys_ = [vy + (py1 - vy) * k for k in ks]
    hw = [6 + 120 * k ** 1.5 for k in ks]
    rl = [(c_ - w_, y_) for c_, w_, y_ in zip(cen, hw, ys_)]
    rr = [(c_ + w_, y_) for c_, w_, y_ in zip(cen, hw, ys_)]

    def wall(side, t, cols, shade, sd):
        # верх — башни-«замки»: ступеньки разной высоты от края картины к повороту реки
        top = []
        n = 10
        x_edge = px0 if side < 0 else px1
        x_in = rl[0][0] - 4 if side < 0 else rr[0][0] + 4
        for k in range(n):
            u0, u1 = k / n, (k + 1) / n
            xa = x_edge + (x_in - x_edge) * u0
            xb = x_edge + (x_in - x_edge) * u1
            ytop = hor - 0.30 * Hs * (1 - u0) ** 1.3 + (vy - hor) * u0 - r.uniform(0, 0.12) * Hs * (1 - u0)
            notch = r.uniform(0.25, 0.75)
            xm = xa + (xb - xa) * notch
            top += [(xa, ytop), (xm, ytop), (xm, ytop + r.uniform(8, 22) * (1 - u0)), (xb, ytop + r.uniform(4, 16) * (1 - u0))]
        bank = rl if side < 0 else rr
        poly = top + [(x_in, vy)] + [(x - side * 2, y) for x, y in bank] + [(x_edge, py1)]
        ops.append(Wash(t, 1.4, poly, cols, dens=0.96, blur=1.2, rough=0.06, direction="down", seed=sd, kind="over", edge=0.0))
        ops.append(Wash(t + 0.9, 0.6, poly, [shade], dens=0.10, blur=2.0, rough=0.2, direction="down", seed=sd + 1, edge=0.6))
        # тень на гранях: широкие вертикальные мазки
        for j in range(9):
            u = (j + r.random()) / 9
            x = x_edge + (x_in - x_edge) * u
            y0_ = hor - 0.30 * Hs * (1 - u) ** 1.3 + (vy - hor) * u + 10
            ln = (py1 - y0_) * r.uniform(0.35, 0.8) * (1 - 0.5 * u)
            ops.append(Stroke(t + 0.9 + j * 0.05, 0.4, [(x, y0_), (x - side * 4, y0_ + ln)], [10 + 18 * (1 - u)], shade, dens=0.30, blur=4, seed=sd + 10 + j))
        # слои породы
        for j in range(7):
            yv = hor + (py1 - hor) * (0.08 + 0.13 * j)
            xb = (cx - 110 if side < 0 else cx + 130)
            ops.append(Stroke(t + 1.4 + j * 0.05, 0.3, [(x_edge + side * -6, yv), ((x_edge + xb) / 2, yv + 6), (xb, yv + 14)], [3], (1.0, 0.88, 0.74), dens=0.28, blur=1.6, kind="over",
                              seed=sd + 30 + j))
        return t + 1.9

    t = wall(-1, t0 + 2.8, [(0.97, 0.66, 0.42), (0.90, 0.50, 0.32), (0.74, 0.38, 0.26)], (0.62, 0.30, 0.24), 3120)
    t = wall(1, t - 0.8, [(0.74, 0.46, 0.42), (0.60, 0.36, 0.36), (0.46, 0.28, 0.30)], (0.36, 0.20, 0.24), 3160)
    ops.append(Wash(t, 1.1, rl + rr[::-1], [(0.56, 0.86, 0.82), (0.34, 0.70, 0.72), (0.24, 0.60, 0.66)], dens=0.9, blur=1.2, rough=0.1, direction="up", seed=3200, kind="over", edge=0.0))
    for j in range(12):
        k = 0.15 + 0.85 * r.random()
        i = int(k * 23)
        ln = 4 + 40 * k
        ops.append(Stroke(t + 0.9 + j * 0.05, 0.3, [(cen[i] - ln, ys_[i]), (cen[i] + ln, ys_[i])], [2 + 2 * k], (0.92, 0.99, 0.98), dens=0.6, blur=1, kind="over", seed=3210 + j))
    for j in range(14):
        i = r.randrange(8, 24)
        side = r.choice((-1, 1))
        x = (rl[i][0] - r.uniform(4, 30)) if side < 0 else (rr[i][0] + r.uniform(4, 30))
        ops.append(Bloom(t + 1.4 + j * 0.05, x, ys_[i] - r.uniform(0, 10), r.uniform(5, 14) * (0.5 + ys_[i] / py1), (0.44, 0.58, 0.32), dens=0.8, dur=0.4, seed=3230 + j, soft=1.2))
    end = birds(ops, t + 2.1, [(px0 + Wd * 0.55, py0 + Hs * 0.30, 16)], col=(0.30, 0.24, 0.28))
    return ops, end, "motes"


def _clipped(fn):
    """Пятна (кроны, ореолы) не растекаются за край картины."""
    def wrapped(box, hor, t0=0.8, seed=0):
        ops, end, parts = fn(box, hor, t0=t0, seed=seed)
        px0, px1, py0, py1 = box
        for op in ops:
            if isinstance(op, Bloom) and op.clip is None:
                op.clip_to(px0, py0, px1, py1)
        return ops, end, parts
    return wrapped


NEW_SCENES = {"almaty_lake": (scene_almaty_lake, 0.5), "steppe_yurts": (scene_steppe_yurts, 0.5), "apple_orchard": (scene_apple_orchard, 0.42),
              "poppies": (scene_poppies, 0.45), "boat_dusk": (scene_boat_dusk, 0.5), "winter_village": (scene_winter_village, 0.4),
              "xmas_tree": (scene_xmas_tree, 0.62), "canyon": (scene_canyon, 0.35)}
NEW_SCENES = {k: (_clipped(f), fr) for k, (f, fr) in NEW_SCENES.items()}
qc.SCENES.update(NEW_SCENES)
