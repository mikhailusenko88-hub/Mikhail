"""Гонки шариков для «Kim yutadi?» (Узбекистан): города и машины. Shorts 1080×1920, 30 к/с.
Движок — тот же, что у «Білесің бе?» (Қай қала жеңеді?), надписи — узбекский + русский.

    build_race(out_path, race_no, points, seed, log, music_dir, league=..., entries=...) -> dict
Всё рисуется кодом: трасса, физика, звук. Музыка — свои треки из папки music/.
Каждый ролик — новая случайная трасса (туннели, лестницы, кочки, батуты, молоты, развилки…).
"""
import colorsys
import json
import math
import random
import subprocess
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import race_leagues as RL

BASE = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30
HZ = 240
STEP = HZ // FPS
DT = 1.0 / HZ
CW = 600          # ширина трассы (всё важное — в безопасной зоне Shorts)
OX = 110          # отступ трассы слева: телефоны срезают края ролика
PX, PY = 722, 392  # таблица мест
R = 19.0          # радиус шарика
TH = 6.0          # полутолщина стенок
G = 1750.0
Y0 = 700          # запас сверху в картинке трассы
GATE_T = 1.2      # старт после отсчёта 3-2-1
POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
FINALE_T = 7.5
WIN_MIN, WIN_MAX = 42.0, 54.0   # победитель приходит за 42–54 с → ролик около минуты
MAX_RACE = 64.0

# текущая лига (ставится в build_race)
LG = RL.LEAGUES["cities"]
LKEY = "cities"
ENT = RL.entries("cities")
N = len(ENT)

# фон верх, фон низ, стены, акцент
THEMES = [
    ((5, 16, 38), (8, 42, 74), (0, 175, 202), (254, 197, 12)),     # цвета флага
    ((20, 8, 38), (52, 16, 72), (180, 100, 255), (255, 210, 80)),
    ((6, 26, 24), (10, 58, 50), (60, 230, 170), (255, 220, 120)),
    ((30, 10, 14), (70, 20, 30), (255, 110, 90), (255, 230, 150)),
]

FONT_FILES = [BASE / "fonts" / "DejaVuSans-Bold.ttf",
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
_fonts = {}


def font(size):
    size = int(size)
    if size not in _fonts:
        for p in FONT_FILES:
            if p.exists():
                _fonts[size] = ImageFont.truetype(str(p), size)
                break
        else:
            raise RuntimeError("нет шрифта DejaVuSans-Bold.ttf (папка fonts/)")
    return _fonts[size]


def make_colors():
    out = []
    if LG.get("teams"):
        k = {"boys": 0, "girls": 0}
        for e in ENT:
            t = e.get("team", "boys")
            j = k[t]
            k[t] += 1
            h = (0.47 + 0.27 * j / 9) if t == "boys" else ((0.84 + 0.22 * j / 9) % 1.0)
            s = 0.85 if j % 2 == 0 else 0.6
            v = 1.0 if j % 3 else 0.86
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            out.append((int(r * 255), int(g * 255), int(b * 255)))
        return out
    if all(e.get("color") for e in ENT):          # свои цвета (клубы)
        return [tuple(e["color"]) for e in ENT]
    for i in range(N):
        h = (0.03 + i * 0.618034) % 1.0
        s = 0.82 if i % 2 == 0 else 0.55
        v = 1.0 if i % 3 else 0.86
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        out.append((int(r * 255), int(g * 255), int(b * 255)))
    return out


COLORS = make_colors()


def set_league(league, entries=None):
    global LG, LKEY, ENT, N, COLORS, MINI
    LKEY = league
    LG = RL.LEAGUES[league]
    ENT = entries or RL.entries(league)
    N = len(ENT)
    COLORS = make_colors()
    MINI = None


TEAM_COL = {"boys": (70, 170, 255), "girls": (255, 95, 170)}
GOLD = (255, 205, 40)
TITLES = {}       # сколько раз участник становился чемпионом недели / месяца


def stars(key):
    n = TITLES.get(key, 0)
    return "" if not n else ("★" * n if n <= 3 else f"★{n}")


def text_stars(d, x, y, name, f, fill, key, im=None):
    """Имя и звёзды чемпиона (золотом) сразу после него."""
    d.text((x, y), name, font=f, fill=fill)
    st = stars(key)
    if st:
        d.text((x + d.textlength(name, font=f) + 5, y), st, font=f, fill=GOLD)


def light(col, need=140):
    """Цвет для надписи: тёмные цвета шариков осветляем, чтобы текст читался на тёмном фоне."""
    lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
    if lum >= need:
        return tuple(col)
    k = min(0.6, (need - lum) / (255 - lum + 1e-9) + 0.08)
    return tuple(int(c + (255 - c) * k) for c in col)


# ---------------- трасса ----------------

class Course:
    """Трасса из случайных участков. segs: x1,y1,x2,y2,упругость; pegs: x,y,r,упругость,вид;
    spins: cx,cy,длина,лопастей,скорость,фаза,вид(0 мельница, 1 молот),размах,толщина."""
    NEW = ("tunnel", "stairs", "bumpy", "tramps", "hammers", "split")
    OLD = ("pegs", "spinners", "funnel", "bumpers")

    def __init__(self, rnd, n=20, sections=7):
        self.rnd = rnd
        self.segs, self.pegs, self.spins = [], [], []
        self.tubes, self.tramps, self.marks = [], [], []
        if n <= 21:     # как было: 3 ряда по 7
            self.start = [(60 + c * 76 + (38 if r_ % 2 else 0), 50 + r_ * 48) for r_ in range(3) for c in range(7)][:n]
        else:           # городов больше 21 (просят в комментариях) — те же 3 ряда, но плотнее
            cols = math.ceil(n / 3)
            sp = min(76.0, (CW - 90) / (cols - 0.5))
            self.start = [(45 + c * sp + (sp / 2 if r_ % 2 else 0), 50 + r_ * 48)
                          for r_ in range(3) for c in range(cols)][:n]
        self.gate_y = 190
        self.segs.append([0, self.gate_y, CW, self.gate_y, 0.2])   # ворота (индекс 0)
        y = 260.0
        y = self.zigzag(y, rnd.randint(3, 4), rnd.random() < 0.5)
        new, old = list(self.NEW), list(self.OLD)
        rnd.shuffle(new)
        rnd.shuffle(old)
        chosen = new[:4] + old[:max(0, sections - 4)]
        rnd.shuffle(chosen)
        self.plan = chosen
        for k, name in enumerate(chosen):
            y = getattr(self, "sec_" + name)(y)
            if k < len(chosen) - 1 and rnd.random() < 0.5:
                y = self.zigzag(y, rnd.randint(2, 3), rnd.random() < 0.5)
        y = self.zigzag(y, 2, rnd.random() < 0.5)
        y = self.sec_pegs(y, rnd.randint(6, 8))
        self.finish_y = y + 220
        fy = self.finish_y
        # лоток за финишем
        self.segs.append([0, fy + 170, CW / 2, fy + 215, 0.1])
        self.segs.append([CW, fy + 170, CW / 2, fy + 215, 0.1])
        self.end_y = fy + 420
        self.segs.append([0, -Y0, 0, self.end_y, 0.3])
        self.segs.append([CW, -Y0, CW, self.end_y, 0.3])

    # --- полки ---
    def shelf(self, y, from_left, gap=94, deg=None, e=0.2):
        """Наклонная полка от стены вниз, у другой стены щель gap. Возвращает y низа."""
        ang = math.radians(deg if deg is not None else self.rnd.uniform(10.5, 14.5))
        L = CW - gap
        drop = L * math.tan(ang)
        if from_left:
            self.segs.append([0, y, L, y + drop, e])
        else:
            self.segs.append([CW, y, CW - L, y + drop, e])
        return y + drop

    def zigzag(self, y, n, first_left):
        for k in range(n):
            y = self.shelf(y, (k % 2 == 0) == first_left) + 100
        return y + 30

    def collector(self, y, start_left):
        """Полка-сборщик: все шарики скатываются к нужной стене и падают в начало участка."""
        return self.shelf(y, not start_left, gap=100) + 110

    # --- старые участки ---
    def sec_pegs(self, y, rows=None):
        rows = rows or self.rnd.randint(8, 10)
        sx, sy = 74, 62
        y += 40
        for r_ in range(rows):
            x = 74.0 if r_ % 2 == 0 else 111.0
            while x <= CW - 60:
                self.pegs.append([x, y + r_ * sy, 8.0, 0.5, 0])
                x += sx
        return y + rows * sy + 40

    def sec_spinners(self, y, k=2):
        rnd = self.rnd
        side = rnd.choice([-1, 1])
        for _ in range(k):
            L = rnd.uniform(90, 112)
            cx = CW / 2 + side * rnd.uniform(55, 90)
            cy = y + 140 + L
            if side < 0:
                self.segs.append([CW, cy - L - 120, cx + L + 45, cy - L, 0.3])
            else:
                self.segs.append([0, cy - L - 120, cx - L - 45, cy - L, 0.3])
            self.spins.append([cx, cy, L, rnd.choice([2, 3, 4]), -side * rnd.uniform(1.9, 2.8),
                               rnd.uniform(0, 6.283), 0, 0.0, 7.0])
            self.pegs.append([cx, cy, 13.0, 0.4, 0])
            side = -side
            y = cy + L + 60
        return y + 20

    def sec_funnel(self, y):
        gap, h = 76, 400
        self.segs.append([0, y, CW / 2 - gap / 2, y + h, 0.25])
        self.segs.append([CW, y, CW / 2 + gap / 2, y + h, 0.25])
        cy = y + h + 95
        self.spins.append([CW / 2, cy, 62, 2, self.rnd.choice([-1, 1]) * 4.0, 0.0, 0, 0.0, 7.0])
        self.pegs.append([CW / 2, cy, 10.0, 0.4, 0])
        return y + h + 230

    def sec_bumpers(self, y, n=None):
        n = n or self.rnd.randint(5, 7)
        pts, tries = [], 0
        while len(pts) < n and tries < 800:
            tries += 1
            x, yy = self.rnd.uniform(96, CW - 96), self.rnd.uniform(y + 70, y + 560)
            if all(math.hypot(x - a, yy - b) > 150 for a, b in pts):
                pts.append((x, yy))
        for x, yy in pts:
            self.pegs.append([x, yy, 30.0, 1.0, 1])
        return y + 640

    # --- новые участки ---
    def sec_tunnel(self, y):
        """Туннель-серпантин: полка с потолком, шарики идут по одному, обгонять нельзя."""
        rnd = self.rnd
        start_left = rnd.random() < 0.5
        y = self.collector(y, start_left)
        self.marks.append((y - 60, RL.UI["marks"]["tunnel"]))
        legs = rnd.choice([2, 3])
        hgt, gap, ent = 76, 100, 120
        ang = math.radians(rnd.uniform(15, 18))
        tn = math.tan(ang)
        L = CW - gap
        drop = L * tn
        for k in range(legs):
            left = (k % 2 == 0) == start_left
            x0, x1 = (0.0, L) if left else (float(CW), CW - L)
            xc0 = x0 + ent if left else x0 - ent
            yc0 = y + ent * tn
            self.segs.append([x0, y, x1, y + drop, 0.15])
            self.segs.append([xc0, yc0 - hgt, x1, y + drop - hgt, 0.15])
            self.tubes.append([(xc0, yc0 - hgt), (x1, y + drop - hgt), (x1, y + drop), (xc0, yc0)])
            y += drop + 125
        return y + 10

    def sec_stairs(self, y):
        """Лестница: шарики прыгают со ступеньки на ступеньку — тадым-тадым."""
        rnd = self.rnd
        start_left = rnd.random() < 0.5
        y = self.collector(y, start_left)
        self.marks.append((y - 60, RL.UI["marks"]["stairs"]))
        sw, rise = 68, rnd.uniform(38, 46)
        tilt = math.tan(math.radians(5))
        nsteps = int((CW - 100) // sw)
        for f in range(2):
            left = (f % 2 == 0) == start_left
            d = 1 if left else -1
            x, yy = (0.0 if left else float(CW)), y
            for s in range(nsteps):
                x2, y2 = x + d * sw, yy + sw * tilt
                self.segs.append([x, yy, x2, y2, 0.42])
                if s < nsteps - 1:
                    self.segs.append([x2, y2, x2, yy + rise, 0.42])
                x, yy = x2, yy + rise
            y = yy + 115
        return y + 10

    def sec_bumpy(self, y):
        """Горка с кочками: шарики подпрыгивают на каждой кочке."""
        rnd = self.rnd
        start_left = rnd.random() < 0.5
        y = self.collector(y, start_left)
        self.marks.append((y - 60, RL.UI["marks"]["bumps"]))
        tn = math.tan(math.radians(12))
        bw, A = 56, rnd.uniform(10, 14)
        L = CW - 100
        nb = int(L // bw)
        for k in range(2):
            left = (k % 2 == 0) == start_left
            d = 1 if left else -1
            x0 = 0.0 if left else float(CW)
            pts = []
            for b in range(nb):
                s0 = b * bw
                pts.append((s0, 0.0))
                pts.append((s0 + bw / 2, -A))
            pts.append((nb * bw, 0.0))
            for (s1, a1), (s2, a2) in zip(pts, pts[1:]):
                self.segs.append([x0 + d * s1, y + s1 * tn + a1, x0 + d * s2, y + s2 * tn + a2, 0.45])
            y = y + nb * bw * tn + 115
        return y + 10

    def sec_tramps(self, y):
        """Батуты: шарики падают на пружинящие площадки и летят через всю трассу."""
        rnd = self.rnd
        start_left = rnd.random() < 0.5
        y = self.shelf(y, not start_left, gap=110) + 170
        self.marks.append((y - 80, RL.UI["marks"]["tramp"]))
        left = start_left
        for k in range(3):
            if left:
                p = [8, y, 205, y + 66]
            else:
                p = [CW - 8, y, CW - 205, y + 66]
            p.append(0.9)
            self.segs.append(p)
            self.tramps.append(p[:4])
            left = not left
            y += 175
        return y + 120

    def sec_hammers(self, y):
        """Молоты-маятники качаются над длинной полкой и сбивают шарики."""
        rnd = self.rnd
        start_left = rnd.random() < 0.5
        y = self.collector(y, start_left) + 150
        self.marks.append((y - 210, RL.UI["marks"]["hammer"]))
        tn = math.tan(math.radians(9))
        L = CW - 100
        x0, x1 = (0.0, L) if start_left else (float(CW), CW - L)
        self.segs.append([x0, y, x1, y + L * tn, 0.2])
        for k in range(2):
            fx = 0.32 + 0.4 * k
            px = x0 + (x1 - x0) * fx
            sy = y + L * tn * fx
            Lh = 170
            om = 2 * math.pi / rnd.uniform(1.5, 1.9)
            self.spins.append([px, sy - 26 - Lh, Lh, 1, om, rnd.uniform(0, 6.283), 1,
                               math.radians(rnd.uniform(48, 58)), 20.0])
        return y + L * tn + 130

    def sec_split(self, y):
        """Развилка: два пути — слева полки, справа штырьки. Какой быстрее?"""
        rnd = self.rnd
        mid = CW / 2
        h = rnd.uniform(600, 700)
        self.marks.append((y + 10, RL.UI["marks"]["fork"]))
        self.segs.append([mid, y + 60, mid, y + h, 0.3])
        self.pegs.append([mid, y + 60, 12.0, 0.5, 0])
        left_shelves = rnd.random() < 0.5
        x_a, x_b = (0.0, mid) if left_shelves else (mid, float(CW))
        yy, k = y + 110, 0
        tn = math.tan(math.radians(14))
        Ls = mid - 72
        while yy < y + h - 100:
            if k % 2 == 0:
                self.segs.append([x_a, yy, x_a + Ls, yy + Ls * tn, 0.2])
            else:
                self.segs.append([x_b, yy, x_b - Ls, yy + Ls * tn, 0.2])
            yy += Ls * tn + 82
            k += 1
        px0, px1 = (mid, float(CW)) if left_shelves else (0.0, mid)
        r_, py = 0, y + 120
        while py < y + h - 60:
            x = px0 + (44 if r_ % 2 == 0 else 76)
            while x <= px1 - 40:
                self.pegs.append([x, py, 8.0, 0.5, 0])
                x += 64
            py += 58
            r_ += 1
        return y + h + 60


# ---------------- физика ----------------

class Sim:
    def __init__(self, c, seed):
        self.c = c
        rng = np.random.default_rng(seed)
        self.rng = rng
        perm = rng.permutation(N)
        self.pos = np.array([c.start[perm[i]] for i in range(N)], float)
        self.pos[:, 0] += rng.uniform(-3, 3, N)
        self.vel = np.zeros((N, 2))
        self.vel[:, 0] = rng.uniform(-40, 40, N)
        self.racing = np.ones(N, bool)
        S = np.array(c.segs, float)
        self.SA, self.SB, self.SE = S[:, 0:2], S[:, 2:4], S[:, 4]
        self.SAB = self.SB - self.SA
        self.SL2 = np.maximum((self.SAB ** 2).sum(1), 1e-9)
        self.SYmin = np.minimum(self.SA[:, 1], self.SB[:, 1]) - 40
        self.SYmax = np.maximum(self.SA[:, 1], self.SB[:, 1]) + 40
        self.Son = np.ones(len(S), bool)
        P = np.array(c.pegs, float)
        self.PC, self.PR, self.PE, self.PK = P[:, 0:2], P[:, 2], P[:, 3], P[:, 4]
        self.t = 0.0
        self.n = 0
        self.finish = []
        self.events = []
        self.snap = self.pos.copy()
        self._near_t = -1
        self._sidx = np.arange(len(S))
        self._pidx = np.arange(len(P))

    def _ev(self, ii, s):
        k = s > 260
        if k.any():
            for i, v in zip(ii[k], s[k]):
                self.events.append((self.t, float(self.pos[i, 0]), float(v)))

    def _resolve(self, ii, nrm, pen, e, vs=None, bumper=None):
        np.add.at(self.pos, ii, nrm * pen[:, None])
        v = self.vel[ii] if vs is None else self.vel[ii] - vs
        vn = (v * nrm).sum(1)
        imp = np.where(vn < 0, -(1 + e) * vn, 0.0)
        if bumper is not None:
            imp = np.where(bumper & (vn < 0), np.maximum(imp, 620 - vn), imp)
        vt = v - nrm * vn[:, None]
        np.add.at(self.vel, ii, nrm * imp[:, None] - 0.004 * vt)
        self._ev(ii, -vn)

    def _update_near(self):
        """Раз в 1/8 с выбираем только стенки и штырьки рядом с шариками — трасса длинная, так быстрее."""
        lo = self.pos[:, 1].min() - 420
        hi = self.pos[:, 1].max() + 420
        self._sidx = np.nonzero((self.SYmax > lo) & (self.SYmin < hi))[0]
        self._pidx = np.nonzero((self.PC[:, 1] > lo) & (self.PC[:, 1] < hi))[0]

    def step(self):
        if self.t >= GATE_T:
            self.Son[0] = False
        if self.n % 30 == 0:
            self._update_near()
        p, v = self.pos, self.vel
        v[:, 1] += G * DT
        v *= 0.9996
        sp = np.sqrt((v ** 2).sum(1))
        f = sp > 1500
        if f.any():
            v[f] *= (1500 / sp[f])[:, None]
        p += v * DT
        # стенки и полки
        P = p[:, None, :]
        si = self._sidx
        if len(si):
            SA, SAB = self.SA[si], self.SAB[si]
            tt = np.clip(((P - SA[None]) * SAB[None]).sum(-1) / self.SL2[si][None], 0, 1)
            D = P - (SA[None] + SAB[None] * tt[..., None])
            dist = np.sqrt((D ** 2).sum(-1)) + 1e-9
            pen = R + TH - dist
            m = (pen > 0) & self.Son[si][None]
            if m.any():
                ii, jj = np.nonzero(m)
                self._resolve(ii, D[ii, jj] / dist[ii, jj, None], pen[ii, jj], self.SE[si][jj])
        # штырьки и отбойники
        pi = self._pidx
        if len(pi):
            D = P - self.PC[pi][None]
            dist = np.sqrt((D ** 2).sum(-1)) + 1e-9
            pen = R + self.PR[pi][None] - dist
            m = pen > 0
            if m.any():
                ii, jj = np.nonzero(m)
                self._resolve(ii, D[ii, jj] / dist[ii, jj, None], pen[ii, jj], self.PE[pi][jj],
                              bumper=self.PK[pi][jj] > 0)
        # мельницы и молоты
        lo, hi = p[:, 1].min() - 300, p[:, 1].max() + 300
        for cx, cy, L, arms, om, ph, kind, amp, thk in self.c.spins:
            if cy < lo or cy > hi:
                continue
            if kind == 0:
                a0, w = ph + om * self.t, om
            else:
                a0 = math.pi / 2 + amp * math.sin(om * self.t + ph)
                w = amp * om * math.cos(om * self.t + ph)
            ang = a0 + np.arange(arms) * (2 * math.pi / arms)
            tips = np.stack([cx + L * np.cos(ang), cy + L * np.sin(ang)], 1)
            A = np.array([cx, cy])
            AB = tips - A
            tt = np.clip(((P - A) * AB[None]).sum(-1) / (L * L), 0, 1)
            C = A + AB[None] * tt[..., None]
            D = P - C
            dist = np.sqrt((D ** 2).sum(-1)) + 1e-9
            pen = R + thk - dist
            m = pen > 0
            if m.any():
                ii, jj = np.nonzero(m)
                Cc = C[ii, jj] - A
                vs = w * np.stack([-Cc[:, 1], Cc[:, 0]], 1)
                self._resolve(ii, D[ii, jj] / dist[ii, jj, None], pen[ii, jj], 0.35 if kind == 0 else 0.55, vs=vs)
        # шарики между собой
        D = p[:, None] - p[None]
        dist = np.sqrt((D ** 2).sum(-1)) + 1e-9
        pen = 2 * R - dist
        m = np.triu(pen > 0, 1)
        if m.any():
            a, b = np.nonzero(m)
            nr = D[a, b] / dist[a, b, None]
            corr = nr * (pen[a, b] / 2)[:, None]
            np.add.at(p, a, corr)
            np.add.at(p, b, -corr)
            rel = ((v[a] - v[b]) * nr).sum(1)
            j = np.where(rel < 0, -0.78 * rel, 0.0)
            np.add.at(v, a, nr * j[:, None])
            np.add.at(v, b, -nr * j[:, None])
        np.clip(p[:, 0], R + TH, CW - R - TH, out=p[:, 0])
        # финиш
        crossed = self.racing & (p[:, 1] > self.c.finish_y)
        for i in np.nonzero(crossed)[0]:
            self.finish.append((int(i), self.t))
            self.racing[i] = False
        # застрявших подталкиваем
        self.n += 1
        if self.n % HZ == 0:
            moved = np.sqrt(((p - self.snap) ** 2).sum(1))
            stuck = self.racing & (moved < 12) & (self.t > GATE_T + 1)
            for i in np.nonzero(stuck)[0]:
                v[i] += (self.rng.uniform(-380, 380), self.rng.uniform(-450, -220))
            self.snap = p.copy()
        self.t += DT

    def run(self, max_race=MAX_RACE, post=5.0, give_up=None):
        frames, winner_t = [], None
        while True:
            self.step()
            if self.n % STEP == 0:
                frames.append((self.pos.copy(), self.racing.copy(), len(self.finish), self.t))
            if winner_t is None and self.finish:
                winner_t = self.finish[0][1]
                if give_up and winner_t - GATE_T < give_up[0]:
                    break        # слишком быстро — трасса не подходит, дальше не считаем
            if winner_t is None and give_up and self.t - GATE_T > give_up[1]:
                break            # слишком долго — не подходит
            if not self.racing.any() and self.t > self.finish[-1][1] + 1.0:
                break
            if winner_t is not None and self.t > winner_t + post:
                break
            if self.t > GATE_T + max_race:
                break
        return frames

    def ranking(self):
        done = [i for i, _ in self.finish]
        rest = sorted([i for i in range(N) if self.racing[i]], key=lambda i: -self.pos[i, 1])
        return done + rest


def order_at(pos, racing, finish, nfin):
    done = [i for i, _ in finish[:nfin]]
    rest = sorted([i for i in range(N) if racing[i]], key=lambda i: -pos[i, 1])
    return done + rest


def pick_race(seed, tries=10, log=print):
    best = None
    for k in range(tries):
        s = seed + k * 7919
        rnd = random.Random(s)
        c = Course(rnd, N, sections=rnd.choice([7, 8, 8, 9]))
        sim = Sim(c, s)
        t0 = time.time()
        frames = sim.run(give_up=(WIN_MIN - 6, WIN_MAX + 6))
        if not sim.finish:
            log(f"  трасса {k + 1}: никто не доехал за {WIN_MAX + 6:.0f} с — не подходит")
            continue
        wt = sim.finish[0][1] - GATE_T
        leaders, changes = None, 0
        for pos, racing, nfin, t in frames:
            if t < GATE_T + 2 or nfin:
                continue
            ld = int(np.argmax(np.where(racing, pos[:, 1], -1e9)))
            if leaders is not None and ld != leaders:
                changes += 1
            leaders = ld
        margin = sim.finish[1][1] - sim.finish[0][1] if len(sim.finish) > 1 else 9
        score = min(changes, 16) + (3 if margin < 0.8 else 0) + len(sim.finish) / 4
        ok = WIN_MIN <= wt <= WIN_MAX
        log(f"  трасса {k + 1} ({', '.join(c.plan)}): победа на {wt:.1f} с, смен лидера {changes}, "
            f"финишировали {len(sim.finish)}, расчёт {time.time() - t0:.0f} с{'' if ok else ' — не подходит'}")
        if ok and (best is None or score > best[0]):
            best = (score, c, sim, frames)
        if best and best[0] >= 14 and k >= 2:
            break
    if best is None:
        raise RuntimeError("не нашлась подходящая трасса")
    return best[1], best[2], best[3]


# ---------------- надписи ----------------

def fit_size(s, size, max_w):
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while size > 16 and tmp.textlength(s, font=font(size)) > max_w:
        size -= 2
    return size


def pair_size(lines, size, max_w):
    """Один размер для казахской и русской строки — чтобы обе были одинаково заметны."""
    return min(fit_size(s, size, max_w) for s in lines)


def differs(kk, ru):
    return RL.differs(kk, ru)


def ent_lines(i, full=False, upper=False):
    e = ENT[i]
    kk, ru = (e["full_kk"], e["full_ru"]) if full else (e["kk"], e["ru"])
    if upper:
        kk, ru = kk.upper(), ru.upper()
    if LG.get("plate") and not full:
        kk = f"{e['code']} · {kk}"
        ru = f"{e['code']} · {ru}"
    return [kk, ru] if differs(kk, ru) else [kk]


def ent_pair(i):
    e = ENT[i]
    s = f"{e['kk']} · {e['ru']}" if differs(e["kk"], e["ru"]) else e["kk"]
    return s


def text_c(d, cx, y, s, size, fill, stroke=6, sfill=(0, 0, 0)):
    f = font(size)
    w = d.textlength(s, font=f)
    d.text((cx - w / 2, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)


# ---------------- графика трассы ----------------

def draw_course(c, theme):
    """Картинка всей трассы. Рисуем кусками по высоте — так хватает памяти даже на длинную трассу."""
    top, bot, wall, acc = theme
    HC = int(c.end_y + Y0 + 200)
    yy = np.arange(HC)[:, None]
    m = (0.5 + 0.5 * np.sin(yy / 1100.0)).astype(np.float32)
    col = (np.array(top, np.float32)[None] * (1 - m) + np.array(bot, np.float32)[None] * m).astype(np.uint8)
    img = Image.fromarray(np.ascontiguousarray(np.repeat(col[:, None, :], W, axis=1)))
    del col, m
    TILE, PAD = 1500, 60
    for t0 in range(0, HC, TILE):
        t1 = min(HC, t0 + TILE)
        a0, a1 = max(0, t0 - PAD), min(HC, t1 + PAD)
        hh = a1 - a0
        glow = Image.new("RGBA", (W, hh), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        lay = Image.new("RGBA", (W, hh), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        off = Y0 - a0

        def Y(v):
            return v + off

        def vis(*ys):
            return max(ys) + off > -120 and min(ys) + off < hh + 120

        for y in range((a0 // 90) * 90, a1, 90):
            for x in range(OX + 45, OX + CW, 90):
                d.ellipse([x - 2, y - a0 - 2, x + 2, y - a0 + 2], fill=(255, 255, 255, 22))
        # туннели: стеклянная труба под шариками
        for poly in c.tubes:
            if vis(*[p[1] for p in poly]):
                pts = [(OX + x, Y(y)) for x, y in poly]
                d.polygon(pts, fill=wall + (46,))
                gd.polygon(pts, fill=wall + (60,))
                (x1, y1), (x2, y2) = poly[0], poly[1]
                d.line([(OX + x1, Y(y1) + 12), (OX + x2, Y(y2) + 12)], fill=(255, 255, 255, 70), width=4)
        for x1, y1, x2, y2, e in c.segs[1:]:
            if not vis(y1, y2):
                continue
            gd.line([(OX + x1, Y(y1)), (OX + x2, Y(y2))], fill=wall + (150,), width=30)
            d.line([(OX + x1, Y(y1)), (OX + x2, Y(y2))], fill=wall + (255,), width=12)
            for (x, y) in ((x1, y1), (x2, y2)):
                d.ellipse([OX + x - 6, Y(y) - 6, OX + x + 6, Y(y) + 6], fill=wall + (255,))
        # батуты: яркая площадка с пружинами
        for x1, y1, x2, y2 in c.tramps:
            if not vis(y1, y2):
                continue
            for k in range(4):
                f = (k + 0.5) / 4
                bx, by = x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
                zz = [(OX + bx + (8 if j % 2 else -8), Y(by) + 8 + j * 9) for j in range(6)]
                d.line(zz, fill=(255, 255, 255, 200), width=4)
            gd.line([(OX + x1, Y(y1)), (OX + x2, Y(y2))], fill=acc + (200,), width=40)
            d.line([(OX + x1, Y(y1)), (OX + x2, Y(y2))], fill=acc + (255,), width=16)
        for x, y, r, e, kind in c.pegs:
            if not vis(y):
                continue
            if kind:
                gd.ellipse([OX + x - r - 10, Y(y) - r - 10, OX + x + r + 10, Y(y) + r + 10], fill=acc + (150,))
                d.ellipse([OX + x - r, Y(y) - r, OX + x + r, Y(y) + r], fill=(30, 30, 40, 255),
                          outline=acc + (255,), width=7)
                d.ellipse([OX + x - 9, Y(y) - 9, OX + x + 9, Y(y) + 9], fill=acc + (255,))
            else:
                gd.ellipse([OX + x - r - 6, Y(y) - r - 6, OX + x + r + 6, Y(y) + r + 6], fill=wall + (140,))
                d.ellipse([OX + x - r, Y(y) - r, OX + x + r, Y(y) + r], fill=(235, 250, 255, 255))
        # таблички участков (туннель, батут…)
        for my_, s in c.marks:
            if vis(my_):
                f = font(26)
                tw = d.textlength(s, font=f)
                cx = OX + CW / 2
                d.rounded_rectangle([cx - tw / 2 - 16, Y(my_) - 4, cx + tw / 2 + 16, Y(my_) + 36], radius=18,
                                    fill=(0, 0, 0, 120), outline=acc + (180,), width=3)
                d.text((cx - tw / 2, Y(my_)), s, font=f, fill=acc + (255,))
        fy = c.finish_y
        if vis(fy):
            sq = 18
            for k, x in enumerate(range(OX, OX + CW, sq)):
                for row in range(2):
                    colr = (255, 255, 255, 255) if (k + row) % 2 == 0 else (10, 10, 10, 255)
                    d.rectangle([x, Y(fy) - sq + row * sq, min(x + sq, OX + CW) - 1, Y(fy) + row * sq - 1], fill=colr)
            text_c(d, OX + CW / 2, Y(fy) - 80, RL.UI["finish"], 44, acc + (255,), 5)
        glow = glow.filter(ImageFilter.GaussianBlur(9))
        part = img.crop((0, a0, W, a1)).convert("RGBA")
        part.alpha_composite(glow)
        part.alpha_composite(lay)
        img.paste(part.crop((0, t0 - a0, W, t0 - a0 + (t1 - t0))).convert("RGB"), (0, t0))
        del glow, lay, gd, d, part
    return img


def num_ball(col, num, r):
    s = int(2 * r + 4)
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s / 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=col + (255,), outline=(255, 255, 255, 230), width=max(2, int(r / 12)))
    t = str(num)
    f = font(max(10, int(r * (1.05 if len(t) < 2 else 0.95))))
    w = d.textlength(t, font=f)
    d.text((c - w / 2, c - r * 0.62), t, font=f, fill=(255, 255, 255), stroke_width=max(2, int(r / 6)),
           stroke_fill=(0, 0, 0))
    return im


def ball_sprite(col, num=None):
    s = int(2 * R + 4)
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s / 2
    d.ellipse([c - R, c - R, c + R, c + R], fill=tuple(int(v * 0.55) for v in col) + (255,))
    for k in range(8):
        rr = R * (1 - k * 0.09)
        f = 0.65 + k * 0.06
        sh = -k * 1.1
        d.ellipse([c - rr + sh, c - rr + sh, c + rr + sh, c + rr + sh],
                  fill=tuple(min(255, int(v * f + 20 * k / 8)) for v in col) + (255,))
    d.ellipse([c - 8, c - 12, c - 1, c - 5], fill=(255, 255, 255, 200))
    d.ellipse([c - R, c - R, c + R, c + R], outline=(255, 255, 255, 120), width=2)
    if num is not None:
        t = str(num)
        f = font(19 if len(t) < 2 else 17)
        w = d.textlength(t, font=f)
        d.text((c - w / 2, c - 11), t, font=f, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    return im


def label_sprite(i):
    """Подпись над шариком. Где русское название другое — вторая строка тем же размером."""
    e = ENT[i]
    two = LG.get("label") == "two" and differs(e["kk"], e["ru"])
    lines = [e["kk"], e["ru"]] if two else [e["kk"]]
    st = stars(e["key"])
    if st:
        lines[0] = st + " " + lines[0]
    f = font(21 if two else 22)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w = int(max(tmp.textlength(s, font=f) for s in lines)) + 10
    hgt = 30 * len(lines) + 4
    im = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for j, s in enumerate(lines):
        sw = d.textlength(s, font=f)
        d.text(((w - sw) / 2, 2 + j * 28), s, font=f, fill=(255, 255, 255, 255), stroke_width=4,
               stroke_fill=(0, 0, 0, 255))
    return im


def plate_sprite(code, scale=1.0):
    """Казахстанский номер: флаг-полоска KZ, «777 ABC», код региона."""
    w, h = int(330 * scale), int(78 * scale)
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, w + 3, h + 3], radius=int(10 * scale), fill=(250, 250, 250, 255),
                        outline=(20, 20, 20, 255), width=max(3, int(4 * scale)))
    sx = int(56 * scale)
    d.rounded_rectangle([8, 8, 4 + sx, h - 1], radius=int(6 * scale), fill=(0, 165, 200, 255))
    d.ellipse([4 + sx / 2 - 12 * scale, 14 * scale, 4 + sx / 2 + 12 * scale, 38 * scale], fill=(254, 197, 12, 255))
    fk = font(22 * scale)
    tw = d.textlength("KZ", font=fk)
    d.text((4 + sx / 2 - tw / 2, 44 * scale), "KZ", font=fk, fill=(255, 255, 255, 255))
    fm = font(46 * scale)
    d.text((sx + 16 * scale, 13 * scale), "777 AAA", font=fm, fill=(20, 20, 20, 255))
    bx = w - int(86 * scale)
    d.line([(bx, 10), (bx, h - 2)], fill=(20, 20, 20, 255), width=max(2, int(3 * scale)))
    fc = font(50 * scale)
    tw = d.textlength(code, font=fc)
    d.text((bx + (w - bx) / 2 - tw / 2 + 2, 10 * scale), code, font=fc, fill=(20, 20, 20, 255))
    return im


def paste(img, sp, x, y):
    img.paste(sp, (int(x), int(y)), sp)


def header_band(race_no, acc, final=False):
    a = np.zeros((380, W, 4), np.uint8)
    a[..., 3] = (np.linspace(215, 0, 380)[:, None]).astype(np.uint8)
    im = Image.fromarray(a, "RGBA")
    d = ImageDraw.Draw(im)
    # казахский и русский — одним шрифтом, одним размером и цветом
    t1, t2 = LG["head"]
    sz = pair_size([t1, t2], 48, 800)
    text_c(d, W / 2, 206, t1, sz, (255, 255, 255), 6)
    text_c(d, W / 2, 206 + sz + 8, t2, sz, (255, 255, 255), 6)
    lab = RL.stxt(LKEY)["final_label"] if final else RL.UI["race_band"].format(n=race_no)
    f = font(30)
    lw = d.textlength(lab, font=f)
    py = 206 + 2 * sz + 30
    d.rounded_rectangle([W / 2 - lw / 2 - 22, py, W / 2 + lw / 2 + 22, py + 44], radius=22, fill=acc + (255,))
    d.text((W / 2 - lw / 2, py + 4), lab, font=f, fill=(20, 20, 26))
    return im


def early_pill(acc, lines=None):
    """Призыв в начале заезда — пока смотрят все: «Кто победит? Пиши прогноз!»"""
    s1, s2 = lines or LG["early"]
    sz = pair_size([s1, s2], 30, CW - 60)
    im = Image.new("RGBA", (CW, 2 * sz + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 0, CW - 10, 2 * sz + 34], radius=24, fill=(0, 0, 0, 175), outline=acc + (255,), width=4)
    text_c(d, CW / 2, 10, s1, sz, acc, 4)
    text_c(d, CW / 2, 16 + sz, s2, sz, (255, 255, 255), 4)
    return im


MINI = None


def panel_img(order, nfin, acc, timer, race_no=0):
    global MINI
    if MINI is None:
        MINI = [num_ball(COLORS[i], ENT[i]["num"], 12) for i in range(N)]
    mode = LG.get("panel", "kk")
    rowh, top = (46 if mode == "two" else 28), 50
    pw = 250
    hgt = top + rowh * N + 10
    im = Image.new("RGBA", (pw, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw - 1, hgt - 1], radius=16, fill=(0, 0, 0, 155))
    text_c(d, pw / 2, 10, f"№{race_no}  ·  {timer}" if race_no else timer, 28, (255, 255, 255), 4)
    medal = [(255, 205, 40), (215, 220, 230), (225, 150, 80)]
    for k, i in enumerate(order):
        y = top + k * rowh
        fin = k < nfin
        e = ENT[i]
        if fin:
            d.rounded_rectangle([4, y - 1, pw - 5, y + rowh - 3], radius=8, fill=(255, 255, 255, 34))
        nc = medal[k] if (k < 3 and fin) else (200, 200, 210)
        d.text((8, y + 2), f"{k + 1}", font=font(19), fill=nc)
        im.paste(MINI[i], (36, y), MINI[i])
        colr = acc if fin else (255, 255, 255)
        if LG.get("teams"):
            colr = acc if fin else TEAM_COL[e["team"]]
        st = stars(e["key"])
        room = pw - 72 - (d.textlength(st, font=font(19)) + 5 if st else 0)
        if mode == "two":
            text_stars(d, 66, y + 1, e["kk"], font(19), colr, e["key"])
            d.text((66, y + 22), e["ru"], font=font(19), fill=colr)
        elif mode == "slash" and differs(e["kk"], e["ru"]):
            s = f"{e['kk']} / {e['ru']}"
            text_stars(d, 66, y + 1, s, font(fit_size(s, 21, room)), colr, e["key"])
        else:
            text_stars(d, 66, y + 1, e["kk"], font(fit_size(e["kk"], 21, room)), colr, e["key"])
    return im


def confetti(rng, x, y, n=140):
    out = []
    for _ in range(n):
        a = rng.uniform(-math.pi, 0)
        sp = rng.uniform(300, 1100)
        out.append([x, y, math.cos(a) * sp, math.sin(a) * sp, rng.uniform(5, 11),
                    COLORS[rng.integers(N)], rng.uniform(0, 6.28)])
    return out


def uz_map(box_h, winner, acc):
    """Карта Узбекистана (контур — uz_outline.json, Natural Earth 1:50m) и точки городов."""
    f = BASE / "uz_outline.json"
    polys = json.loads(f.read_text())["polygons"] if f.exists() else []
    lat_c = 41.3
    k = math.cos(math.radians(lat_c))
    lon0, lon1, lat0, lat1 = 55.7, 73.4, 37.0, 45.8
    sc = (box_h - 8) / (lat1 - lat0)
    bw = int((lon1 - lon0) * k * sc) + 8

    def pr(lon, lat):
        return 4 + (lon - lon0) * k * sc, 4 + (lat1 - lat) * sc

    im = Image.new("RGBA", (bw, box_h), (0, 0, 0, 0))
    glow = Image.new("RGBA", (bw, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gd = ImageDraw.Draw(glow)
    if not polys:      # контура ещё нет (первый запуск) — просто рамка
        d.rounded_rectangle([2, 2, bw - 3, box_h - 3], radius=30, fill=(0, 120, 150, 120), outline=acc + (255,), width=4)
    # самые большие кольца — первыми, анклавы (Сох, Шахимардан) потом
    for poly in sorted(polys, key=lambda p: -len(p[0])):
        ring = [pr(lo, la) for lo, la in poly[0]]
        if len(ring) < 3:
            continue
        gd.polygon(ring, fill=(0, 153, 181, 120))
        d.polygon(ring, fill=(0, 125, 160, 235))
        d.line(ring + [ring[0]], fill=acc + (255,), width=4)
    im = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)), im)
    d = ImageDraw.Draw(im)
    pts = {}
    for i, e in enumerate(ENT):
        x, y = pr(e["lon"], e["lat"])
        pts[i] = (x, y)
        if i != winner:
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 230))
    return im, pts


# ---------------- машина победителя (гонка машин) ----------------

# силуэты сбоку: точки кузова (x — длина 0..1, y — вниз), окна, колёса (x, радиус)
CAR_SHAPES = {
    "sedan": ([(0.02, .31), (.03, .22), (.18, .19), (.31, .175), (.41, .085), (.62, .075), (.75, .17), (.95, .195),
               (.985, .25), (.985, .32), (.02, .335)],
              [[(.34, .175), (.43, .1), (.505, .1), (.505, .175)], [(.53, .175), (.53, .1), (.61, .095), (.71, .175)]],
              [(.215, .075), (.79, .075)]),
    "hatch": ([(0.03, .31), (.04, .22), (.19, .19), (.32, .175), (.42, .08), (.74, .075), (.86, .16), (.95, .2),
               (.965, .32), (.03, .335)],
              [[(.35, .175), (.44, .1), (.56, .1), (.56, .175)], [(.585, .175), (.585, .1), (.73, .1), (.82, .175)]],
              [(.22, .075), (.78, .075)]),
    "mini": ([(0.12, .31), (.13, .22), (.23, .19), (.35, .07), (.74, .06), (.85, .16), (.88, .2), (.885, .32),
              (.12, .335)],
             [[(.37, .18), (.44, .09), (.56, .085), (.56, .18)], [(.585, .18), (.585, .085), (.72, .085), (.81, .18)]],
             [(.27, .07), (.745, .07)]),
    "van": ([(0.08, .33), (.08, .2), (.13, .07), (.2, .055), (.93, .05), (.94, .33)],
            [[(.12, .19), (.16, .08), (.26, .075), (.26, .19)], [(.29, .19), (.29, .075), (.47, .075), (.47, .19)],
             [(.5, .19), (.5, .075), (.69, .075), (.69, .19)], [(.72, .19), (.72, .075), (.9, .075), (.9, .19)]],
            [(.24, .072), (.8, .072)]),
    "pickup": ([(0.05, .33), (.05, .2), (.1, .075), (.15, .06), (.41, .06), (.42, .2), (.95, .2), (.955, .33)],
               [[(.1, .19), (.14, .085), (.26, .08), (.26, .19)], [(.29, .19), (.29, .08), (.39, .08), (.39, .19)]],
               [(.2, .072), (.8, .072)]),
    "suv": ([(0.02, .3), (.03, .2), (.16, .165), (.29, .15), (.37, .055), (.86, .05), (.94, .15), (.98, .19),
             (.985, .32), (.02, .325)],
            [[(.33, .15), (.4, .075), (.56, .07), (.56, .15)], [(.585, .15), (.585, .07), (.73, .07), (.73, .15)],
             [(.755, .15), (.755, .07), (.85, .07), (.9, .15)]],
            [(.21, .088), (.8, .088)]),
    "classic": ([(0.02, .31), (.02, .22), (.25, .205), (.35, .09), (.66, .085), (.75, .205), (.98, .215),
                 (.98, .31)],
                [[(.37, .2), (.42, .11), (.5, .105), (.5, .2)], [(.53, .2), (.53, .105), (.635, .105), (.69, .2)]],
                [(.2, .072), (.8, .072)]),
}


def car_img(body, col, width):
    """Нарисованная машина сбоку (без марок и логотипов), цвет — как у шарика победителя."""
    shape, wins, wheels = CAR_SHAPES.get(body, CAR_SHAPES["sedan"])
    S = 3
    w = width * S
    hh = int(w * 0.44)
    im = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P = lambda pts: [(x * w, y * w + 0.02 * w) for x, y in pts]
    d.ellipse([0.04 * w, 0.37 * w, 0.96 * w, 0.43 * w], fill=(0, 0, 0, 110))         # тень на земле
    dark = tuple(int(v * 0.55) for v in col)
    d.polygon(P(shape), fill=col + (255,), outline=dark + (255,))
    d.line(P(shape) + [P(shape)[0]], fill=(255, 255, 255, 90), width=int(w * 0.004))
    # нижняя тёмная полоса и блик по борту
    ys = [p[1] for p in shape]
    yb = max(ys)
    lo = [(x, max(y, yb - 0.06)) for x, y in shape if y >= yb - 0.06]
    if len(lo) >= 2:
        d.rectangle([min(p[0] for p in lo) * w, (yb - 0.05) * w + 0.02 * w, max(p[0] for p in lo) * w,
                     yb * w + 0.02 * w], fill=dark + (255,))
    xs0 = [p[0] for p in shape]
    d.line([((min(xs0) + 0.03) * w, 0.245 * w), ((max(xs0) - 0.03) * w, 0.245 * w)], fill=tuple(min(255, int(v * 1.25 + 30)) for v in col) + (255,),
           width=int(w * 0.006))
    for win in wins:
        d.polygon(P(win), fill=(170, 215, 240, 255), outline=(40, 50, 60, 255))
        a, b = P(win)[0], P(win)[1]
        d.line([a, b], fill=(255, 255, 255, 120), width=int(w * 0.004))
    # фары
    xs = [p[0] for p in shape]
    fx = max(xs)
    d.ellipse([(fx - 0.035) * w, 0.215 * w, (fx - 0.005) * w, 0.245 * w], fill=(255, 240, 160, 255))
    rx = min(xs)
    d.rectangle([(rx + 0.002) * w, 0.22 * w, (rx + 0.02) * w, 0.255 * w], fill=(230, 40, 40, 255))
    for x, r in wheels:
        cx, cy = x * w, (yb + 0.005) * w + 0.02 * w
        R_ = r * w
        d.ellipse([cx - R_ * 1.12, cy - R_ * 1.12, cx + R_ * 1.12, cy + R_ * 1.12], fill=dark + (255,))
        d.ellipse([cx - R_, cy - R_, cx + R_, cy + R_], fill=(25, 25, 30, 255))
        d.ellipse([cx - R_ * 0.58, cy - R_ * 0.58, cx + R_ * 0.58, cy + R_ * 0.58], fill=(190, 195, 205, 255))
        for k in range(5):
            a = k * 2 * math.pi / 5
            d.line([(cx, cy), (cx + R_ * 0.5 * math.cos(a), cy + R_ * 0.5 * math.sin(a))], fill=(120, 125, 135, 255),
                   width=int(w * 0.006))
        d.ellipse([cx - R_ * 0.15, cy - R_ * 0.15, cx + R_ * 0.15, cy + R_ * 0.15], fill=(90, 95, 105, 255))
    return im.resize((width, int(hh / S)), Image.LANCZOS)


def mid_car(winner, acc):
    im = Image.new("RGBA", (W, MID_H), (0, 0, 0, 0))
    col = COLORS[winner]
    glow = Image.new("RGBA", (W, MID_H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W / 2 - 360, 40, W / 2 + 360, 320], fill=col + (120,))
    im = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)), im)
    d = ImageDraw.Draw(im)
    for k in range(7):                      # линии скорости позади машины
        y = 120 + k * 26
        L = 120 + (k * 53) % 140
        d.rounded_rectangle([150 - L * 0.2, y, 150 + L, y + 7], radius=4, fill=(255, 255, 255, 60 + 12 * (k % 3)))
    car = car_img(ENT[winner].get("body", "sedan"), col, 700)
    im.paste(car, (int(W / 2 - car.size[0] / 2 + 40), int(MID_H / 2 - car.size[1] / 2 + 8)), car)
    return im


def soccer_ball(r, col):
    """Футбольный мяч: белый шар с тёмными пятиугольниками, снизу — цвет клуба."""
    s = int(2 * r + 6)
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s / 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=(245, 245, 245, 255), outline=(30, 30, 30, 255), width=max(2, int(r / 14)))
    import math
    for cx, cy, rr in [(c, c, r * 0.22), (c - r * 0.6, c - r * 0.35, r * 0.17), (c + r * 0.6, c - r * 0.35, r * 0.17),
                       (c - r * 0.38, c + r * 0.62, r * 0.16), (c + r * 0.38, c + r * 0.62, r * 0.16), (c, c - r * 0.85, r * 0.1)]:
        pts = [(cx + rr * math.cos(math.radians(90 + 72 * k)), cy - rr * math.sin(math.radians(90 + 72 * k))) for k in range(5)]
        d.polygon(pts, fill=(35, 35, 40, 255))
    sh = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([c - r, c - r, c + r, c + r], fill=col + (90,))
    return Image.alpha_composite(im, sh)


def mid_club(winner, acc):
    im = Image.new("RGBA", (W, MID_H), (0, 0, 0, 0))
    col = COLORS[winner]
    glow = Image.new("RGBA", (W, MID_H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W / 2 - 150, 0, W / 2 + 150, 250], fill=col + (150,))
    im = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)), im)
    ball = soccer_ball(96, col)
    im.paste(ball, (int(W / 2 - ball.size[0] / 2), 20), ball)
    d = ImageDraw.Draw(im)
    e = ENT[winner]
    c1, c2 = e.get("city", ""), e.get("city_ru", "")
    s = c1 if c1.lower() == c2.lower() else f"{c1} · {c2}"
    text_c(d, W / 2, 236, s, fit_size(s, 44, 800), (255, 255, 255), 5)
    s2 = "Superliga · Суперлига"
    text_c(d, W / 2, 290, s2, fit_size(s2, 30, 800), acc, 4)
    return im


# ---------------- звук ----------------

class Sfx:
    def __init__(self, seconds, sr=44100):
        self.sr = sr
        self.a = np.zeros(int((seconds + 1) * sr))
        self.rng = np.random.default_rng(5)

    def put(self, sig, at):
        s = int(at * self.sr)
        if 0 <= s < len(self.a):
            self.a[s:s + len(sig)] += sig[:len(self.a) - s]

    def tone(self, f, dur, vol, decay=8.0, h2=0.3):
        t = np.arange(int(dur * self.sr)) / self.sr
        env = np.exp(-t * decay) * np.minimum(1, t * 400)
        return vol * env * (np.sin(2 * np.pi * f * t) + h2 * np.sin(4 * np.pi * f * t))

    def noise(self, dur, vol, decay=6.0):
        m = int(dur * self.sr)
        x = np.convolve(self.rng.uniform(-1, 1, m), np.ones(4) / 4, mode="same")
        return vol * x * np.exp(-np.arange(m) / self.sr * decay)


def make_sfx(total, events, finish, race_end, video_offset=0.0):
    s = Sfx(total)
    for k in range(3):
        s.put(s.tone(660, 0.18, 0.22, 14), k * 0.4)
    for f in (990, 1320):
        s.put(s.tone(f, 0.5, 0.18, 6), GATE_T)
    penta = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21]
    used = {}
    for t, x, st in sorted(events, key=lambda e: -e[2]):
        b = int(t * 40)
        if used.get(b, 0) >= 2 or t > race_end:
            continue
        used[b] = used.get(b, 0) + 1
        semi = penta[min(9, int(x / CW * 10))]
        s.put(s.tone(523.25 * 2 ** (semi / 12), 0.14, 0.03 + 0.07 * min(1.0, st / 900), 32), t)
    for place, (i, t) in enumerate(finish):
        if t > race_end:
            break
        if place == 0:
            for j, semi in enumerate((0, 4, 7, 12, 16, 19, 24)):
                s.put(s.tone(523.25 * 2 ** (semi / 12), 1.2, 0.16, 3.5), t + j * 0.07)
            s.put(s.noise(0.8, 0.25, 5), t)
        else:
            s.put(s.tone(1046.5 * 2 ** (-min(place, 12) / 12), 0.35, 0.12 if place < 3 else 0.06, 9), t)
    fs = race_end + 0.5
    s.put(s.tone(110, 0.4, 0.45, 9, 0.0), fs)
    s.put(s.tone(1318.5, 0.3, 0.16, 10), fs)
    for j, semi in enumerate((0, 7, 12, 16)):
        s.put(s.tone(392 * 2 ** (semi / 12), 1.6, 0.1, 2.5), fs + 0.25 + j * 0.12)
    return s.a[:int(total * s.sr)]


# ---------------- финал: середина экрана для разных тем ----------------

MID_Y, MID_H = 476, 370       # место под карту / большой шарик / счёт команд
TABLE_Y = MID_Y + MID_H + 14


def mid_mushel(winner, acc):
    im = Image.new("RGBA", (W, MID_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    big = num_ball(COLORS[winner], ENT[winner]["num"], 92)
    glow = Image.new("RGBA", (W, MID_H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W / 2 - 120, 10, W / 2 + 120, 250], fill=COLORS[winner] + (140,))
    im = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(24)), im)
    d = ImageDraw.Draw(im)
    im.paste(big, (int(W / 2 - big.size[0] / 2), 34), big)
    yrs = ENT[winner].get("years", [])
    s1, s2 = "Туған жылдар", "Годы рождения"
    hs = pair_size([s1 + " · " + s2], 28, 760)
    text_c(d, W / 2, 238, f"{s1} · {s2}", hs, (255, 255, 255), 4)
    ys = "  ·  ".join(map(str, yrs))
    text_c(d, W / 2, 282, ys, fit_size(ys, 52, 800), acc, 6)
    return im


def mid_teams(race_team, total_team, races, acc, final=False):
    im = Image.new("RGBA", (W, MID_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    b, g = race_team.get("boys", 0), race_team.get("girls", 0)
    t1, t2 = "ҰЛДАР vs ҚЫЗДАР", "МАЛЬЧИКИ vs ДЕВОЧКИ"
    sz = pair_size([t1, t2], 40 if final else 44, 800)
    text_c(d, W / 2, 6, t1, sz, (255, 255, 255), 5)
    text_c(d, W / 2, 12 + sz, t2, sz, (255, 255, 255), 5)
    y = (22 if final else 30) + 2 * sz
    fb = font(78 if final else 96)
    sb, sg = str(b), str(g)
    d.text((W / 2 - 40 - d.textlength(sb, font=fb), y), sb, font=fb, fill=TEAM_COL["boys"], stroke_width=6,
           stroke_fill=(0, 0, 0))
    text_c(d, W / 2, y + 4, ":", 90, (255, 255, 255), 6)
    d.text((W / 2 + 40, y), sg, font=fb, fill=TEAM_COL["girls"], stroke_width=6, stroke_fill=(0, 0, 0))
    y += 100 if final else 120
    L, Rr = 170, W - 170
    tot = max(1, b + g)
    xm = L + (Rr - L) * b / tot
    d.rounded_rectangle([L, y, Rr, y + 34], radius=17, fill=TEAM_COL["girls"] + (255,))
    d.rounded_rectangle([L, y, max(L + 34, xm), y + 34], radius=17, fill=TEAM_COL["boys"] + (255,))
    y += 48 if final else 52
    tb, tg = total_team.get("boys", 0), total_team.get("girls", 0)
    if final:
        win = "boys" if tb > tg else "girls"
        s = f"{RL.stxt(LKEY)['team_sum']}:  {tb} : {tg}"
        text_c(d, W / 2, y, s, fit_size(s, 28, 800), (255, 255, 255), 4)
        w0 = "АЙ ЖЕҢІМПАЗЫ · ПОБЕДИТЕЛЬ МЕСЯЦА" if tb != tg else "ТЕҢ · НИЧЬЯ"
        text_c(d, W / 2, y + 36, w0, fit_size(w0, 28, 800), acc, 4)
        if tb != tg:
            w1 = f"{RL.TEAMS[win][0]} · {RL.TEAMS[win][1]} ★"
            text_c(d, W / 2, y + 72, w1, fit_size(w1, 46, 800), TEAM_COL[win], 6)
    elif (tb, tg) != (b, g):
        s = f"{RL.stxt(LKEY)['team_sum']}:  {tb} : {tg}"
        text_c(d, W / 2, y, s, fit_size(s, 32, 800), acc, 4)
    return im


# ---------------- сборка ролика ----------------

def build_race(out_path, race_no=1, points=None, seed=None, log=print, music_dir=None,
               handle="@kimyutadi_uz", tries=10, league="cities", entries=None, team_total=None,
               final=False, season_races=None, champions=None, season_id="", final_in=None, extra=None, new=None):
    t_start = time.time()
    set_league(league, entries)
    champions = list(champions or [])
    TITLES.clear()
    for ch in champions:
        TITLES[ch["champion"]] = TITLES.get(ch["champion"], 0) + 1
    allents = {e["key"]: e for e in RL.entries(league, extra)}
    new_ents = [allents[k] for k in (new or []) if k in allents]
    out_path = Path(out_path)
    points = dict(points or {})
    seed = int(time.time()) % 100000 if seed is None else seed
    rnd = random.Random(seed)
    theme = THEMES[0] if (final or rnd.random() < 0.5) else rnd.choice(THEMES[1:])
    top_c, bot_c, wall, acc = theme

    log(f"Тема: {LG['name']}. Подбираю трассу и заезд…")
    c, sim, frames = pick_race(seed, tries, log)
    finish = sim.finish
    ranking = sim.ranking()
    winner = ranking[0]
    gained = {}
    race_team = {"boys": 0, "girls": 0}
    for place, i in enumerate(ranking[:len(POINTS)] if (not final or LG.get("teams")) else []):
        key = ENT[i]["key"]
        points[key] = points.get(key, 0) + POINTS[place]
        gained[key] = POINTS[place]
        if LG.get("teams"):
            race_team[ENT[i]["team"]] += POINTS[place]
    team_total = dict(team_total or {})
    if LG.get("teams"):
        for t in ("boys", "girls"):
            team_total[t] = team_total.get(t, 0) + race_team[t]
    table = sorted(points.items(), key=lambda kv: -kv[1])
    idx = {e["key"]: i for i, e in enumerate(ENT)}

    log("Рисую трассу…")
    course_img = draw_course(c, theme)
    HC = course_img.size[1]
    balls = [ball_sprite(col, ENT[i]["num"]) for i, col in enumerate(COLORS)]
    labels = [label_sprite(i) for i in range(N)]
    head = header_band(race_no, acc, final)
    TX = RL.stxt(league)
    pill = early_pill(acc, RL.UI["final_q"] if final else None)
    CD = None if final else RL.countdown(final_in)
    pill2 = early_pill(acc, (CD[0] + "!", CD[1] + "!") if CD and CD[0][-1] != "!" else (CD or TX["pill2"])) \
        if not final else None
    pill3 = None
    if not final and champions and champions[-1]["champion"] in allents:
        ce = allents[champions[-1]["champion"]]
        pill3 = early_pill(acc, (TX["prev"][0].format(kk=ce["kk"]), TX["prev"][1].format(ru=ce["ru"])))
    elif not final and champions and LG.get("teams") and champions[-1]["champion"] in RL.TEAMS:
        tm = RL.TEAMS[champions[-1]["champion"]]
        pill3 = early_pill(acc, (f"Өткен ай жеңімпазы — {tm[0]} ★", f"Победитель прошлого месяца — {tm[1]} ★"))
    pill_new = None
    if new_ents and not final:
        nu = ", ".join(e["kk"] for e in new_ents[:3]) + ("…" if len(new_ents) > 3 else "")
        nr = ", ".join(e["ru"] for e in new_ents[:3]) + ("…" if len(new_ents) > 3 else "")
        pill_new = early_pill(acc, (RL.UI["new"][0].format(uz=nu), RL.UI["new"][1].format(ru=nr)))
    hand = Image.new("RGBA", (420, 50), (0, 0, 0, 0))
    ImageDraw.Draw(hand).text((0, 0), handle, font=font(26), fill=(255, 255, 255, 170))

    race_n = len(frames)
    race_end = race_n / FPS
    total = race_end + FINALE_T
    tmp_video = str(out_path) + ".video.mp4"
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
         "-x264-params", "rc-lookahead=8:sync-lookahead=0", "-b:v", "6000k",
         "-maxrate", "8000k", "-bufsize", "12000k", "-pix_fmt", "yuv420p", tmp_video], stdin=subprocess.PIPE)

    def emit(img):
        proc.stdin.write(np.asarray(img, np.uint8).tobytes())

    log(f"Рисую кадры: заезд {race_end:.0f} с + финал {FINALE_T:.0f} с…")
    rng = np.random.default_rng(seed)
    cam = -380.0
    panel_cache = {}
    conf, win_shown_t = [], None
    winner_t = finish[0][1] if finish else None
    last = None
    for fi, (pos, racing, nfin, t) in enumerate(frames):
        lead_y = pos[racing, 1].max() if racing.any() else c.finish_y
        target = min(lead_y, c.finish_y + 120) - H * 0.46
        target = max(target, -380.0)
        cam += (target - cam) * (0.10 if t > GATE_T else 0.0)
        cam = min(cam, c.end_y - H + 200)
        top = int(cam + Y0)
        top = max(0, min(top, HC - H))
        img = course_img.crop((0, top, W, top + H))
        d = ImageDraw.Draw(img, "RGBA")
        oy = Y0 - top
        if t < GATE_T:
            d.line([(OX, c.gate_y + oy), (OX + CW, c.gate_y + oy)], fill=acc + (255,), width=12)
        for cx, cy, L, arms, om, ph, kind, amp, thk in c.spins:
            sy = cy + oy
            if not (-260 < sy < H + 260):
                continue
            if kind == 0:
                a0 = ph + om * t
                for k in range(arms):
                    a = a0 + k * 2 * math.pi / arms
                    tip = (OX + cx + L * math.cos(a), sy + L * math.sin(a))
                    d.line([(OX + cx, sy), tip], fill=wall + (110,), width=26)
                    d.line([(OX + cx, sy), tip], fill=(255, 255, 255, 255), width=12)
                d.ellipse([OX + cx - 16, sy - 16, OX + cx + 16, sy + 16], fill=acc + (255,))
            else:      # молот-маятник
                a = math.pi / 2 + amp * math.sin(om * t + ph)
                tx, ty = OX + cx + L * math.cos(a), sy + L * math.sin(a)
                d.line([(OX + cx, sy), (tx, ty)], fill=(200, 200, 215, 255), width=12)
                d.ellipse([tx - 26, ty - 26, tx + 26, ty + 26], fill=(60, 60, 75, 255), outline=acc + (255,), width=6)
                d.ellipse([tx - 9, ty - 9, tx + 9, ty + 9], fill=acc + (255,))
                d.ellipse([OX + cx - 12, sy - 12, OX + cx + 12, sy + 12], fill=acc + (255,))
        for i in range(N):
            x, y = pos[i]
            sy = y + oy
            if -60 < sy < H + 60:
                paste(img, balls[i], OX + x - R - 2, sy - R - 2)
        for i in range(N):
            x, y = pos[i]
            sy = y + oy
            if racing[i] and -60 < sy < H + 60:
                lb = labels[i]
                lx = min(max(OX + x - lb.size[0] / 2, 0), OX + CW + 30 - lb.size[0])
                paste(img, lb, lx, sy - R - 6 - lb.size[1])
        img.paste(head, (0, 0), head)
        order = order_at(pos, racing, finish, nfin)
        tt = max(0.0, t - GATE_T)
        timer = f"{int(tt // 60)}:{tt % 60:04.1f}"
        key = (tuple(order), nfin, timer)
        if key not in panel_cache:
            if len(panel_cache) >= 6:     # каждая таблица ~1 МБ — держим только последние
                panel_cache.pop(next(iter(panel_cache)))
            panel_cache[key] = panel_img(order, nfin, acc, timer, race_no)
        pn = panel_cache[key]
        img.paste(pn, (PX, PY), pn)
        if GATE_T + 1.5 < t < GATE_T + 9.5:
            k = min(1.0, (t - GATE_T - 1.5) / 0.3, (GATE_T + 9.5 - t) / 0.3)
            p2 = pill
            if k < 1:
                p2 = pill.copy()
                p2.putalpha(p2.getchannel("A").point(lambda v: int(v * k)))
            paste(img, p2, OX, 1386)
        if pill3 is not None and GATE_T + 33 < t < GATE_T + 40 and (winner_t is None or t < winner_t):
            k = min(1.0, (t - GATE_T - 33) / 0.3, (GATE_T + 40 - t) / 0.3)
            p3 = pill3
            if k < 1:
                p3 = pill3.copy()
                p3.putalpha(p3.getchannel("A").point(lambda v: int(v * k)))
            paste(img, p3, OX, 1386)
        if pill_new is not None and GATE_T + 11 < t < GATE_T + 18 and (winner_t is None or t < winner_t):
            k = min(1.0, (t - GATE_T - 11) / 0.3, (GATE_T + 18 - t) / 0.3)
            p4 = pill_new
            if k < 1:
                p4 = pill_new.copy()
                p4.putalpha(p4.getchannel("A").point(lambda v: int(v * k)))
            paste(img, p4, OX, 1386)
        if pill2 is not None and GATE_T + 22 < t < GATE_T + 29 and (winner_t is None or t < winner_t):
            k = min(1.0, (t - GATE_T - 22) / 0.3, (GATE_T + 29 - t) / 0.3)
            p2 = pill2
            if k < 1:
                p2 = pill2.copy()
                p2.putalpha(p2.getchannel("A").point(lambda v: int(v * k)))
            paste(img, p2, OX, 1386)
        if t < GATE_T:
            n = 3 - int(t / 0.4)
            text_c(d, OX + CW / 2, 640, str(n), 230, acc, 12)
            if final:
                text_c(d, OX + CW / 2, 900, "FINAL", 64, acc, 7)
                s_ = "ҰЛДАР vs ҚЫЗДАР" if LG.get("teams") else f"TOP-{N}"
                text_c(d, OX + CW / 2, 976, s_, fit_size(s_, 56, CW - 40), (255, 255, 255), 7)
            else:
                text_c(d, OX + CW / 2, 900, RL.UI["race"][0].format(n=race_no), 56, (255, 255, 255), 7)
                text_c(d, OX + CW / 2, 968, RL.UI["race"][1].format(n=race_no), 56, (255, 255, 255), 7)
        elif t < GATE_T + 0.7:
            text_c(d, OX + CW / 2, 680, RL.UI["start"], 120, (255, 255, 255), 10)
        if winner_t is not None and t >= winner_t:
            if win_shown_t is None:
                win_shown_t = t
                conf = confetti(rng, OX + CW / 2, c.finish_y + oy)
            k = min(1.0, (t - win_shown_t) / 0.25)
            wl = ent_lines(winner)
            ts = pair_size(list(RL.UI["winner"]), int(32 + 8 * k), CW - 90)
            cs = pair_size(wl, int((50 + 30 * k) if len(wl) == 1 else (40 + 18 * k)), CW - 90)
            cy0 = 432 + 2 * ts + 26
            bottom = cy0 + len(wl) * (cs + 8) + 18
            d.rounded_rectangle([OX + 20, 412, OX + CW - 20, bottom], radius=30, fill=(0, 0, 0, int(170 * k)))
            text_c(d, OX + CW / 2, 430, RL.UI["winner"][0], ts, acc, 6)
            text_c(d, OX + CW / 2, 430 + ts + 6, RL.UI["winner"][1], ts, acc, 6)
            for j, s_ in enumerate(wl):
                text_c(d, OX + CW / 2, cy0 + j * (cs + 8), s_, cs, light(COLORS[winner]), 8)
            for p_ in conf:
                age = t - win_shown_t
                px = p_[0] + p_[2] * age
                py = p_[1] + p_[3] * age + 900 * age * age
                if 0 < py < H and age < 3:
                    s_ = p_[4]
                    d.rectangle([px - s_, py - s_ / 2, px + s_, py + s_ / 2], fill=p_[5])
        paste(img, hand, OX + 6, 1338)
        emit(img)
        last = img
        if fi % 300 == 0:
            log(f"  кадр {fi}/{race_n}, {time.time() - t_start:.0f} с")
    del course_img

    # финал: середина (карта / шарик с годами / счёт команд), победитель, таблица
    base = Image.blend(last.filter(ImageFilter.GaussianBlur(10)), Image.new("RGB", (W, H), (0, 0, 0)), 0.62)
    # всё на финале — на двух языках одинаковым размером: казахская строка, под ней русская
    blocks = []
    mp = pts = None
    if LG.get("map"):
        mp, pts = uz_map(MID_H - 6, winner, acc)
        mx, my = (W - mp.size[0]) // 2, MID_Y
        pin_lb = plate_sprite(ENT[winner]["code"], 0.62) if LG.get("plate") else labels[winner]
    else:
        if LG.get("car"):
            mid = mid_car(winner, acc)
        elif LG.get("club"):
            mid = mid_club(winner, acc)
        else:
            mid = mid_teams(race_team, team_total, race_no, acc, final) if LG.get("teams") else mid_mushel(winner, acc)
    b1 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(b1)
    h1, h2 = TX["champ"] if (final and not LG.get("teams")) else \
        tuple(x.format(n=race_no) for x in RL.UI["race_winner"])
    hs = pair_size([h1, h2], 40, 760)
    text_c(d1, W / 2, 196, h1, hs, acc, 5)
    text_c(d1, W / 2, 196 + hs + 6, h2, hs, acc, 5)
    wl = ent_lines(winner, full=True, upper=True)
    cs = pair_size(wl, 84 if len(wl) == 1 else 60, W - 260)
    if len(wl) == 2:
        cs = min(cs, int((MID_Y - 30 - (196 + 2 * hs + 22)) / 2 - 6))
    cy0 = 196 + 2 * hs + 22
    if len(wl) == 1:
        cy0 += 6
    for j, s_ in enumerate(wl):
        text_c(d1, W / 2, cy0 + j * (cs + 6), s_, cs, light(COLORS[winner]), 8)
    blocks.append((0.3, b1))
    if mp is None:
        bm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bm.paste(mid, (0, MID_Y), mid)
        blocks.append((0.6, bm))
    b2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(b2)
    y = TABLE_Y
    MB = [num_ball(COLORS[j], ENT[j]["num"], 15) for j in range(N)]
    medal = [(255, 205, 40), (215, 220, 230), (225, 150, 80)]
    L, Rr = 150, 890   # края строк таблицы (справа — кнопки Shorts)
    wk = season_races if season_races is not None else race_no
    if final and not LG.get("teams"):
        g1, g2 = RL.UI["final_res"]
        rows = [(i, None) for i in ranking[:3]]
    elif LG.get("teams"):
        g1, g2 = (x.format(n=race_no) for x in RL.UI["race_res"])
        rows = [(i, None) for i in ranking[:5]]
    elif wk >= 2:
        zz = "заезда" if wk % 10 == 1 and wk % 100 != 11 else "заездов"
        if season_races is not None and CD:
            g1, g2 = f"{TX['table'][0]} · {CD[0]}", f"{TX['table'][1]} · {CD[1]}"
        elif season_races is not None:
            g1, g2 = f"{TX['table'][0]} · {RL.UI['after'].format(n=wk)}", f"{TX['table'][1]} · после {wk} {zz}"
        else:
            g1, g2 = f"{RL.UI['tour']} · {RL.UI['after'].format(n=wk)}", f"ТУРНИРНАЯ ТАБЛИЦА · после {wk} {zz}"
        rows = [(idx[k_], pt) for k_, pt in table if k_ in idx][:5]
    else:
        g1, g2 = RL.UI["top5"]
        rows = [(i, None) for i in ranking[:5]]
    gs = pair_size([g1, g2], 28, Rr - L)
    text_c(d2, (L + Rr) / 2, y, g1, gs, acc, 4)
    text_c(d2, (L + Rr) / 2, y + gs + 6, g2, gs, acc, 4)
    # очки — числом (единицы понятны из заголовка), так влезает и русское название
    ns = pair_size([ent_pair(i) for i, _ in rows], 28, Rr - L - 250)
    for k, (i, pt) in enumerate(rows):
        yy = y + 2 * gs + 24 + k * 44
        d2.rounded_rectangle([L, yy - 5, Rr, yy + 38], radius=12, fill=(255, 255, 255, 26))
        d2.text((L + 14, yy), f"{k + 1}", font=font(30), fill=medal[k] if k < 3 else (220, 220, 230))
        b2.paste(MB[i], (L + 52, yy - 1), MB[i])
        name_col = TEAM_COL[ENT[i]["team"]] if LG.get("teams") else (255, 255, 255)
        text_stars(d2, L + 96, yy + (30 - ns) * 0.6, ent_pair(i), font(ns), name_col, ENT[i]["key"])
        s_ = f"{pt}" if pt is not None else ("" if final else f"+{POINTS[k]}")
        px_ = Rr - 16 - d2.textlength(s_, font=font(30))
        d2.text((px_, yy), s_, font=font(30), fill=acc if pt is not None else (120, 255, 140))
        g_ = gained.get(ENT[i]["key"])
        if pt is not None and g_:
            g = f"+{g_}"
            d2.text((px_ - 14 - d2.textlength(g, font=font(24)), yy + 5), g, font=font(24), fill=(120, 255, 140))
    if final and not LG.get("teams"):
        # зал славы: чемпионы недель / месяцев по порядку (сохраняются навсегда)
        hall = champions + [{"champion": ENT[winner]["key"], "season": season_id}]
        TITLES[ENT[winner]["key"]] = TITLES.get(ENT[winner]["key"], 0) + 1
        yh = y + 2 * gs + 24 + len(rows) * 44 + 6
        hh1 = TX["hall"]
        text_c(d2, (L + Rr) / 2, yh, hh1, fit_size(hh1, 26, Rr - L), acc, 4)
        first = max(0, len(hall) - 3)
        for j, ch in enumerate(hall[first:]):
            wn = first + j + 1
            yy = yh + 36 + j * 36
            e = allents.get(ch["champion"], {"kk": ch["champion"], "ru": ch["champion"], "key": ch["champion"]})
            d2.rounded_rectangle([L, yy - 4, Rr, yy + 30], radius=10,
                                 fill=(255, 205, 40, 46) if j == len(hall[first:]) - 1 else (255, 255, 255, 20))
            d2.text((L + 14, yy), RL.season_label(league, ch, wn), font=font(23), fill=(220, 220, 230))
            nm = e["kk"] if not differs(e["kk"], e["ru"]) else f"{e['kk']} · {e['ru']}"
            fnm = font(fit_size(nm, 24, 330))
            nw = d2.textlength(nm, font=fnm) + 5 + d2.textlength(stars(e["key"]), font=fnm)
            text_stars(d2, Rr - 16 - nw, yy, nm, fnm, (255, 255, 255), e["key"])
    blocks.append((1.2, b2))
    b3 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(b3)
    s1, s2 = TX["next"] if final else LG["cta"]
    s3 = RL.UI["write"]
    qs = pair_size([s1, s2], 36 if not final else 32, 640)
    cy_ = 1196 if not final else 1236
    text_c(d3, W / 2 - 20, cy_, s1, qs, (255, 255, 255), 5)
    text_c(d3, W / 2 - 20, cy_ + qs + 6, s2, qs, (255, 255, 255), 5)
    if not final:
        text_c(d3, W / 2 - 20, cy_ + 2 * qs + 16, s3, fit_size(s3, 26, 640), acc, 4)
    blocks.append((2.2, b3))
    nfin_frames = int(FINALE_T * FPS)
    for fi in range(nfin_frames):
        t = fi / FPS
        img = base.copy()
        d = ImageDraw.Draw(img, "RGBA")
        if mp is not None:
            a = min(1.0, t / 0.4)
            if a < 1:
                m2 = mp.copy()
                m2.putalpha(m2.getchannel("A").point(lambda v: int(v * a)))
                img.paste(m2, (mx, my), m2)
            else:
                img.paste(mp, (mx, my), mp)
            if t > 0.5:
                wx, wy = pts[winner]
                pt_ = min(1.0, (t - 0.5) / 0.25)
                px, py = mx + wx, my + wy - (1 - pt_) * 160
                pulse = (t * 1.6) % 1.0
                if pt_ >= 1:
                    rr = 16 + 60 * pulse
                    d.ellipse([px - rr, py - rr, px + rr, py + rr], outline=acc + (int(220 * (1 - pulse)),), width=6)
                d.ellipse([px - 20, py - 20, px + 20, py + 20], fill=acc + (255,), outline=(255, 255, 255), width=4)
                lb = pin_lb
                lx = min(max(px - lb.size[0] / 2, 20), W - 20 - lb.size[0])
                paste(img, lb, lx, py - 30 - lb.size[1])
        for t0, b in blocks:
            if t >= t0:
                k = min(1.0, (t - t0) / 0.3)
                if k < 1:
                    b2_ = b.copy()
                    b2_.putalpha(b2_.getchannel("A").point(lambda v: int(v * k)))
                    img.paste(b2_, (0, 0), b2_)
                else:
                    img.paste(b, (0, 0), b)
        paste(img, hand, OX + 6, 1338)
        emit(img)
    proc.stdin.close()
    proc.wait()

    log("Свожу звук…")
    sfx = make_sfx(total, sim.events, finish, race_end)
    wav = str(out_path) + ".sfx.wav"
    a = sfx / max(1e-9, float(np.abs(sfx).max())) * 0.9
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes((a * 32767).astype(np.int16).tobytes())
    music = None
    if music_dir and Path(music_dir).exists():
        prefer = ["02_Tulpar_energichno.mp3", "bit_02_Motor.mp3", "04_Toy_pozitiv.mp3", "bit_01_Staryy_dvor.mp3"]
        files = [Path(music_dir) / f for f in prefer if (Path(music_dir) / f).exists()] or \
            sorted(Path(music_dir).glob("*.mp3"))
        music = rnd.choice(files) if files else None
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_video, "-i", wav]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                f"[2:a]volume=0.42,afade=t=out:st={total - 1.8:.2f}:d=1.8[m];[1:a]volume=0.9[s];"
                f"[s][m]amix=inputs=2:duration=first:normalize=0,volume=1.7,alimiter=limit=0.95[a]", "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart",
            str(out_path)]
    subprocess.run(cmd, check=True)
    for f in (tmp_video, wav):
        Path(f).unlink(missing_ok=True)

    # оба языка в самом начале названия — в ленте Shorts видно только начало
    title = RL.make_title(league, race_no, ENT, final)
    desc = RL.make_desc(league, ENT, final, n=len(allents), new=new_ents if not final else None)
    if CD:
        desc = f"⏳ {CD[0]} · {CD[1]}\n\n" + desc
    if champions and allents and not final:
        ce = allents.get(champions[-1]["champion"])
        if ce:
            desc = TX["prev_desc"].format(kk=ce["kk"], ru=ce["ru"]) + "\n\n" + desc
    tags = LG["tags"]
    log(f"Готово за {time.time() - t_start:.0f} с: победил {ENT[winner]['kk']}, ролик {total:.0f} с")
    return {"title": title, "description": desc, "tags": tags, "winner": ENT[winner]["key"],
            "ranking": [ENT[i]["key"] for i in ranking], "points": points, "duration": total,
            "seed": seed, "race_team": race_team, "team_total": team_total, "plan": c.plan, "final": final}


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lg = sys.argv[sys.argv.index("--league") + 1] if "--league" in sys.argv else "cities"
    args = [a for a in args if a != lg]
    out = args[0] if args else f"race_{lg}.mp4"
    no = int(args[1]) if len(args) > 1 else 1
    sd = int(args[2]) if len(args) > 2 else None
    if "--check" in sys.argv:      # быстрая проверка на сервере: трасса и физика без рисования
        for k_ in ("cities", "cars"):
            set_league(k_)
            rnd_ = random.Random(1)
            c_ = Course(rnd_, N)
            s_ = Sim(c_, 1)
            for _ in range(HZ * 3):
                s_.step()
            print(f"   {k_}: участников {N}, трасса {len(c_.segs)} стенок, проверка физики — ок")
        sys.exit(0)
    info = build_race(out, no, {}, sd, music_dir=BASE / "music", league=lg)
    print(json.dumps({k: v for k, v in info.items() if k not in ("description", "points")}, ensure_ascii=False))
