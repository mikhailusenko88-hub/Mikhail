"""Сцена «1000 шарик» (координаты в пикселях кадра 1080×1920)."""
import math
import random

W, H = 1080, 1920
R = 8.0
HOP = (70, 1010, 290, 590)                  # воронка с шарами: x0 x1 y0 y1
CUP = (425, 655, 1265, 1605)
EX = (505, 575)                             # выход из воронки                # кубок изнутри: x0 x1 y_top y_bottom


def balls(n, rnd):
    dx, dy = 2 * R + 0.6, (2 * R + 0.6) * math.sqrt(3) / 2
    pts = []
    row = 0
    y = HOP[3] - R - 1
    while len(pts) < n:
        x = HOP[0] + R + 1 + (dx / 2 if row % 2 else 0)
        while x < HOP[1] - R - 1 and len(pts) < n:
            pts.append((x + rnd.uniform(-0.3, 0.3), y))
            x += dx
        y -= dy
        row += 1
    return pts


def pegs():
    out = []
    y, row = 760, 0
    while y < 1130:
        off = 35 if row % 2 else 0
        x = 75 + off
        while x < 1010:
            out.append((x, y, 7.0))
            x += 70
        y += 58
        row += 1
    return out


def segs():
    s = []
    s.append((HOP[0] - 10, HOP[2] - 120, HOP[0] - 10, HOP[3] + 10))     # стенки воронки
    s.append((HOP[1] + 10, HOP[2] - 120, HOP[1] + 10, HOP[3] + 10))
    s.append((HOP[0] - 10, HOP[3] + 10, EX[0], 690))                     # сужение к выходу
    s.append((HOP[1] + 10, HOP[3] + 10, EX[1], 690))
    s.append((36, 700, 36, 1330))                                        # боковые стенки поля
    s.append((1044, 700, 1044, 1330))
    s.append((36, 700, EX[0], 692)); s.append((1044, 700, EX[1], 692))   # «плечи» под воронкой
    x0, x1, yt, yb = CUP
    s.append((x0, yt, x0, yb)); s.append((x0, yb, x1, yb)); s.append((x1, yb, x1, yt))   # кубок
    return s


def spinners():
    return [(300, 1215, 230, 2.6, 0.0), (780, 1215, 230, -2.6, 1.0)]


def in_cup(x, y):
    x0, x1, yt, yb = CUP
    return x0 < x < x1 and yt - 4 < y < yb
