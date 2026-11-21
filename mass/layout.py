"""Сцена «1000 шарик» (пиксели кадра 1080×1920). Каждый ролик — свой вариант трассы (scene(rnd)),
чтобы ролики не были одинаковыми: цвет неона, штырьки, вертушки, место кубка, ширина выхода."""
import math

W, H = 1080, 1920
R = 8.0
NEONS = [(0, 200, 220), (255, 70, 190), (60, 230, 120), (150, 110, 255), (255, 150, 40)]


class Scene:
    def __init__(self, rnd=None, fixed=False):
        r = rnd
        pick = (lambda a, b: (a + b) / 2) if fixed or r is None else r.uniform
        self.neon = NEONS[0] if fixed or r is None else r.choice(NEONS)
        self.hop = (70, 1010, 290, 590)                    # воронка: x0 x1 y0 y1
        ex_c = 540 + (0 if fixed or r is None else r.choice([-90, -45, 0, 0, 45, 90]))
        ex_w = pick(80, 104)
        self.ex = (ex_c - ex_w / 2, ex_c + ex_w / 2)       # выход из воронки
        cup_c = 540 + (0 if fixed or r is None else r.choice([-110, -55, 0, 0, 55, 110]))
        self.cup = (cup_c - 115, cup_c + 115, 1265, 1605)  # кубок изнутри: x0 x1 y_top y_bottom
        self.peg_dx = pick(64, 78)
        self.peg_dy = pick(52, 64)
        self.peg_off = pick(0, 1)
        sp = pick(2.0, 3.2)
        s1 = 1 if fixed or r is None else r.choice([1, -1])
        s2 = -s1 if fixed or r is None or r.random() < 0.7 else s1
        lx = cup_c - 240 + (0 if fixed or r is None else r.uniform(-30, 30))
        rx = cup_c + 240 + (0 if fixed or r is None else r.uniform(-30, 30))
        lx, rx = max(170, lx), min(910, rx)
        self.spin = [(lx, 1215, pick(200, 250), sp * s1, 0.0), (rx, 1215, pick(200, 250), sp * s2, 1.0)]

    def balls(self, n, rnd):
        dx, dy = 2 * R + 0.6, (2 * R + 0.6) * math.sqrt(3) / 2
        pts, row, y = [], 0, self.hop[3] - R - 1
        while len(pts) < n:
            x = self.hop[0] + R + 1 + (dx / 2 if row % 2 else 0)
            while x < self.hop[1] - R - 1 and len(pts) < n:
                pts.append((x + rnd.uniform(-0.3, 0.3), y))
                x += dx
            y -= dy
            row += 1
        return pts

    def pegs(self):
        out, y, row = [], 760, 0
        while y < 1130:
            off = self.peg_dx / 2 if row % 2 else 0
            x = 75 + off + self.peg_off * 10
            while x < 1010:
                out.append((round(x, 1), round(y, 1), 7.0))
                x += self.peg_dx
            y += self.peg_dy
            row += 1
        return out

    def segs(self):
        h, ex = self.hop, self.ex
        x0, x1, yt, yb = self.cup
        return [
            (h[0] - 10, h[2] - 120, h[0] - 10, h[3] + 10), (h[1] + 10, h[2] - 120, h[1] + 10, h[3] + 10),
            (h[0] - 10, h[3] + 10, ex[0], 690), (h[1] + 10, h[3] + 10, ex[1], 690),
            (36, 700, 36, 1330), (1044, 700, 1044, 1330),
            (36, 700, ex[0], 692), (1044, 700, ex[1], 692),
            (x0, yt, x0, yb), (x0, yb, x1, yb), (x1, yb, x1, yt),
        ]

    def spinners(self):
        return self.spin
