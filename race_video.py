"""«Қай қала жеңеді?» — гонка шариков: 20 городов Казахстана. Shorts 1080×1920, 30 к/с.

    build_race(out_path, race_no, points, seed, log, music_dir) -> dict
Всё рисуется кодом: трасса, физика, звук. Музыка — свои треки из папки music/.
Каждый ролик — новая случайная трасса и новый заезд; очки копятся в турнирной таблице.
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

BASE = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30
HZ = 240
STEP = HZ // FPS
DT = 1.0 / HZ
CW = 740          # ширина трассы
OX = 24           # отступ трассы слева на экране
R = 19.0          # радиус шарика
TH = 6.0          # полутолщина стенок
G = 1750.0
Y0 = 700          # запас сверху в картинке трассы
GATE_T = 1.2      # старт после отсчёта 3-2-1
POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
FINALE_T = 7.0

# казахское название, русское, широта, долгота
CITIES = [
    ("Астана", "Астана", 51.17, 71.45),
    ("Алматы", "Алматы", 43.24, 76.95),
    ("Шымкент", "Шымкент", 42.32, 69.60),
    ("Қарағанды", "Караганда", 49.80, 73.10),
    ("Ақтөбе", "Актобе", 50.28, 57.17),
    ("Тараз", "Тараз", 42.90, 71.37),
    ("Павлодар", "Павлодар", 52.29, 76.97),
    ("Өскемен", "Усть-Каменогорск", 49.95, 82.61),
    ("Семей", "Семей", 50.41, 80.25),
    ("Атырау", "Атырау", 47.10, 51.92),
    ("Қостанай", "Костанай", 53.21, 63.62),
    ("Қызылорда", "Кызылорда", 44.85, 65.51),
    ("Орал", "Уральск", 51.23, 51.37),
    ("Петропавл", "Петропавловск", 54.87, 69.15),
    ("Ақтау", "Актау", 43.65, 51.20),
    ("Түркістан", "Туркестан", 43.30, 68.25),
    ("Көкшетау", "Кокшетау", 53.28, 69.39),
    ("Талдықорған", "Талдыкорган", 45.02, 78.37),
    ("Жезқазған", "Жезказган", 47.80, 67.71),
    ("Қонаев", "Конаев", 43.87, 77.07),
]
N = len(CITIES)

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
    if size not in _fonts:
        for p in FONT_FILES:
            if p.exists():
                _fonts[size] = ImageFont.truetype(str(p), size)
                break
        else:
            raise RuntimeError("нет шрифта DejaVuSans-Bold.ttf (папка fonts/)")
    return _fonts[size]


def city_colors():
    out = []
    for i in range(N):
        h = (0.03 + i * 0.618034) % 1.0
        s = 0.82 if i % 2 == 0 else 0.55
        v = 1.0 if i % 3 else 0.86
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        out.append((int(r * 255), int(g * 255), int(b * 255)))
    return out


COLORS = city_colors()


# ---------------- трасса ----------------

class Course:
    def __init__(self, rnd):
        self.rnd = rnd
        self.segs = []    # x1, y1, x2, y2, упругость
        self.pegs = []    # x, y, r, упругость, вид (0 — штырёк, 1 — отбойник)
        self.spins = []   # cx, cy, длина, лопастей, скорость, фаза
        self.start = [(70 + c * 67 + (33 if r_ else 0), 60 + r_ * 52) for r_ in range(2) for c in range(10)]
        self.segs.append([0, 150, CW, 150, 0.2])   # ворота (индекс 0)
        y = 230.0
        y = self.zigzag(y, rnd.randint(4, 5), rnd.random() < 0.5)
        mids = [lambda y: self.pegs_sec(y, rnd.randint(8, 10)), lambda y: self.spinners(y, 2),
                lambda y: self.funnel(y), lambda y: self.bumpers(y, rnd.randint(5, 7))]
        rnd.shuffle(mids)
        for f in mids[:2]:
            y = f(y)
        y = self.zigzag(y, rnd.randint(3, 4), rnd.random() < 0.5)
        for f in mids[2:]:
            y = f(y)
        y = self.zigzag(y, rnd.randint(2, 3), rnd.random() < 0.5)
        y = self.pegs_sec(y, rnd.randint(6, 8))
        self.finish_y = y + 220
        fy = self.finish_y
        # лоток за финишем
        self.segs.append([0, fy + 170, CW / 2, fy + 215, 0.1])
        self.segs.append([CW, fy + 170, CW / 2, fy + 215, 0.1])
        self.end_y = fy + 420
        self.segs.append([0, -Y0, 0, self.end_y, 0.3])
        self.segs.append([CW, -Y0, CW, self.end_y, 0.3])

    def zigzag(self, y, n, first_left):
        ang = math.radians(self.rnd.uniform(10.5, 14.5))
        gap = 94
        L = CW - gap
        drop = L * math.tan(ang)
        for k in range(n):
            left = (k % 2 == 0) == first_left
            if left:
                self.segs.append([0, y, L, y + drop, 0.2])
            else:
                self.segs.append([CW, y, CW - L, y + drop, 0.2])
            y += drop + 100
        return y + 30

    def pegs_sec(self, y, rows):
        sx, sy = 74, 62
        y += 40
        for r_ in range(rows):
            x = 74.0 if r_ % 2 == 0 else 111.0
            while x <= CW - 60:
                self.pegs.append([x, y + r_ * sy, 8.0, 0.5, 0])
                x += sx
        return y + rows * sy + 40

    def spinners(self, y, k):
        rnd = self.rnd
        side = rnd.choice([-1, 1])
        for _ in range(k):
            L = rnd.uniform(100, 130)
            cx = CW / 2 + side * rnd.uniform(70, 140)
            cy = y + 140 + L
            if side < 0:
                self.segs.append([CW, cy - L - 120, cx + L + 45, cy - L, 0.3])
            else:
                self.segs.append([0, cy - L - 120, cx - L - 45, cy - L, 0.3])
            self.spins.append([cx, cy, L, rnd.choice([2, 3, 4]), -side * rnd.uniform(1.9, 2.8), rnd.uniform(0, 6.283)])
            self.pegs.append([cx, cy, 13.0, 0.4, 0])
            side = -side
            y = cy + L + 60
        return y + 20

    def funnel(self, y):
        gap, h = 76, 400
        self.segs.append([0, y, CW / 2 - gap / 2, y + h, 0.25])
        self.segs.append([CW, y, CW / 2 + gap / 2, y + h, 0.25])
        cy = y + h + 95
        self.spins.append([CW / 2, cy, 62, 2, self.rnd.choice([-1, 1]) * 4.0, 0.0])
        self.pegs.append([CW / 2, cy, 10.0, 0.4, 0])
        return y + h + 230

    def bumpers(self, y, n):
        pts, tries = [], 0
        while len(pts) < n and tries < 800:
            tries += 1
            x, yy = self.rnd.uniform(96, CW - 96), self.rnd.uniform(y + 70, y + 560)
            if all(math.hypot(x - a, yy - b) > 150 for a, b in pts):
                pts.append((x, yy))
        for x, yy in pts:
            self.pegs.append([x, yy, 30.0, 1.0, 1])
        return y + 640


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
        self.Son = np.ones(len(S), bool)
        P = np.array(c.pegs, float)
        self.PC, self.PR, self.PE, self.PK = P[:, 0:2], P[:, 2], P[:, 3], P[:, 4]
        self.t = 0.0
        self.n = 0
        self.finish = []
        self.events = []
        self.snap = self.pos.copy()

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

    def step(self):
        if self.t >= GATE_T:
            self.Son[0] = False
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
        tt = np.clip(((P - self.SA[None]) * self.SAB[None]).sum(-1) / self.SL2[None], 0, 1)
        D = P - (self.SA[None] + self.SAB[None] * tt[..., None])
        dist = np.sqrt((D ** 2).sum(-1)) + 1e-9
        pen = R + TH - dist
        m = (pen > 0) & self.Son[None]
        if m.any():
            ii, jj = np.nonzero(m)
            self._resolve(ii, D[ii, jj] / dist[ii, jj, None], pen[ii, jj], self.SE[jj])
        # штырьки и отбойники
        D = P - self.PC[None]
        dist = np.sqrt((D ** 2).sum(-1)) + 1e-9
        pen = R + self.PR[None] - dist
        m = pen > 0
        if m.any():
            ii, jj = np.nonzero(m)
            self._resolve(ii, D[ii, jj] / dist[ii, jj, None], pen[ii, jj], self.PE[jj], bumper=self.PK[jj] > 0)
        # мельницы
        for cx, cy, L, arms, om, ph in self.c.spins:
            a0 = ph + om * self.t
            ang = a0 + np.arange(arms) * (2 * math.pi / arms)
            tips = np.stack([cx + L * np.cos(ang), cy + L * np.sin(ang)], 1)
            A = np.array([cx, cy])
            AB = tips - A
            tt = np.clip(((P - A) * AB[None]).sum(-1) / (L * L), 0, 1)
            C = A + AB[None] * tt[..., None]
            D = P - C
            dist = np.sqrt((D ** 2).sum(-1)) + 1e-9
            pen = R + 7 - dist
            m = pen > 0
            if m.any():
                ii, jj = np.nonzero(m)
                Cc = C[ii, jj] - A
                vs = om * np.stack([-Cc[:, 1], Cc[:, 0]], 1)
                self._resolve(ii, D[ii, jj] / dist[ii, jj, None], pen[ii, jj], 0.35, vs=vs)
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

    def run(self, max_race=46.0, post=5.0):
        frames, winner_t = [], None
        while True:
            self.step()
            if self.n % STEP == 0:
                frames.append((self.pos.copy(), self.racing.copy(), len(self.finish), self.t))
            if winner_t is None and self.finish:
                winner_t = self.finish[0][1]
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


def pick_race(seed, tries=8, log=print):
    best = None
    for k in range(tries):
        s = seed + k * 7919
        c = Course(random.Random(s))
        sim = Sim(c, s)
        t0 = time.time()
        frames = sim.run()
        if not sim.finish:
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
        score = min(changes, 12) + (3 if margin < 0.8 else 0) + len(sim.finish) / 4
        ok = 19 <= wt <= 34
        log(f"  трасса {k + 1}: победа на {wt:.1f} с, смен лидера {changes}, финишировали {len(sim.finish)}, "
            f"расчёт {time.time() - t0:.0f} с{'' if ok else ' — не подходит'}")
        if ok and (best is None or score > best[0]):
            best = (score, c, sim, frames)
        if best and best[0] >= 12 and k >= 2:
            break
    if best is None:
        raise RuntimeError("не нашлась подходящая трасса")
    return best[1], best[2], best[3]


# ---------------- графика ----------------

def fit_size(s, size, max_w):
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while size > 20 and tmp.textlength(s, font=font(size)) > max_w:
        size -= 4
    return size


def text_c(d, cx, y, s, size, fill, stroke=6, sfill=(0, 0, 0)):
    f = font(size)
    w = d.textlength(s, font=f)
    d.text((cx - w / 2, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)


def draw_course(c, theme):
    top, bot, wall, acc = theme
    HC = int(c.end_y + Y0 + 200)
    yy = np.arange(HC)[:, None]
    m = (0.5 + 0.5 * np.sin(yy / 1100.0)).astype(np.float32)
    col = np.array(top, np.float32)[None] * (1 - m) + np.array(bot, np.float32)[None] * m
    arr = np.repeat(col[:, None, :], W, axis=1)
    img = Image.fromarray(arr.astype(np.uint8))
    glow = Image.new("RGBA", (W, HC), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    lay = Image.new("RGBA", (W, HC), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for y in range(0, HC, 90):
        for x in range(OX + 45, OX + CW, 90):
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, 22))

    def Y(v):
        return v + Y0

    for x1, y1, x2, y2, e in c.segs[1:]:
        gd.line([(OX + x1, Y(y1)), (OX + x2, Y(y2))], fill=wall + (150,), width=30)
        d.line([(OX + x1, Y(y1)), (OX + x2, Y(y2))], fill=wall + (255,), width=12)
        for (x, y) in ((x1, y1), (x2, y2)):
            d.ellipse([OX + x - 6, Y(y) - 6, OX + x + 6, Y(y) + 6], fill=wall + (255,))
    for x, y, r, e, kind in c.pegs:
        if kind:
            gd.ellipse([OX + x - r - 10, Y(y) - r - 10, OX + x + r + 10, Y(y) + r + 10], fill=acc + (150,))
            d.ellipse([OX + x - r, Y(y) - r, OX + x + r, Y(y) + r], fill=(30, 30, 40, 255), outline=acc + (255,), width=7)
            d.ellipse([OX + x - 9, Y(y) - 9, OX + x + 9, Y(y) + 9], fill=acc + (255,))
        else:
            gd.ellipse([OX + x - r - 6, Y(y) - r - 6, OX + x + r + 6, Y(y) + r + 6], fill=wall + (140,))
            d.ellipse([OX + x - r, Y(y) - r, OX + x + r, Y(y) + r], fill=(235, 250, 255, 255))
    fy = Y(c.finish_y)
    sq = 18
    for k, x in enumerate(range(OX, OX + CW, sq)):
        for row in range(2):
            col = (255, 255, 255, 255) if (k + row) % 2 == 0 else (10, 10, 10, 255)
            d.rectangle([x, fy - sq + row * sq, min(x + sq, OX + CW) - 1, fy + row * sq - 1], fill=col)
    text_c(d, OX + CW / 2, fy - 80, "МӘРЕ", 44, acc + (255,), 5)
    glow = glow.filter(ImageFilter.GaussianBlur(9))
    img = img.convert("RGBA")
    img.alpha_composite(glow)
    img.alpha_composite(lay)
    return img.convert("RGB")


def ball_sprite(col):
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
    return im


def label_sprite(name):
    f = font(24)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w = int(tmp.textlength(name, font=f)) + 10
    im = Image.new("RGBA", (w, 34), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((5, 2), name, font=f, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 255))
    return im


def paste(img, sp, x, y):
    img.paste(sp, (int(x), int(y)), sp)


def header_band(race_no, acc):
    im = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    a = np.zeros((260, W, 4), np.uint8)
    a[..., 3] = (np.linspace(215, 0, 260)[:, None]).astype(np.uint8)
    im = Image.fromarray(a, "RGBA")
    d = ImageDraw.Draw(im)
    text_c(d, W / 2, 46, "ҚАЙ ҚАЛА ЖЕҢЕДІ?", 76, (255, 255, 255), 7)
    text_c(d, W / 2, 142, f"Какой город победит?  ·  Жарыс №{race_no}", 36, acc, 5)
    return im


def panel_img(order, nfin, acc):
    rowh = 41
    im = Image.new("RGBA", (290, 26 + rowh * N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 289, 25 + rowh * N], radius=18, fill=(0, 0, 0, 150))
    medal = [(255, 205, 40), (215, 220, 230), (225, 150, 80)]
    for k, i in enumerate(order):
        y = 14 + k * rowh
        fin = k < nfin
        if fin:
            d.rounded_rectangle([6, y - 3, 283, y + rowh - 7], radius=10, fill=(255, 255, 255, 34))
        nc = medal[k] if (k < 3 and fin) else (200, 200, 210)
        d.text((10, y), f"{k + 1}", font=font(24), fill=nc)
        d.ellipse([46, y + 6, 64, y + 24], fill=COLORS[i], outline=(255, 255, 255), width=2)
        d.text((72, y + 2), CITIES[i][0], font=font(24), fill=(255, 255, 255) if not fin else acc)
    return im


def confetti(rng, x, y, n=140):
    out = []
    for _ in range(n):
        a = rng.uniform(-math.pi, 0)
        sp = rng.uniform(300, 1100)
        out.append([x, y, math.cos(a) * sp, math.sin(a) * sp, rng.uniform(5, 11),
                    COLORS[rng.integers(N)], rng.uniform(0, 6.28)])
    return out


def kz_map(box_w, winner, acc):
    data = json.loads((BASE / "kz_outline.json").read_text())
    k = math.cos(math.radians(48.2))
    lon0, lon1, lat0, lat1 = 46.3, 87.5, 40.4, 55.6
    sc = box_w / ((lon1 - lon0) * k)
    hh = int((lat1 - lat0) * sc) + 4

    def pr(lon, lat):
        return (lon - lon0) * k * sc, (lat1 - lat) * sc

    im = Image.new("RGBA", (box_w, hh), (0, 0, 0, 0))
    glow = Image.new("RGBA", (box_w, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gd = ImageDraw.Draw(glow)
    for poly in data["polygons"]:
        ring = [pr(lo, la) for lo, la in poly[0]]
        if len(ring) < 3:
            continue
        gd.polygon(ring, fill=(0, 175, 202, 120))
        d.polygon(ring, fill=(0, 140, 175, 235))
        d.line(ring + [ring[0]], fill=acc + (255,), width=4)
    im = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)), im)
    d = ImageDraw.Draw(im)
    pts = {}
    for i, (kk, ru, la, lo) in enumerate(CITIES):
        x, y = pr(lo, la)
        pts[i] = (x, y)
        if i != winner:
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 230))
    return im, pts


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


# ---------------- сборка ролика ----------------

def build_race(out_path, race_no=1, points=None, seed=None, log=print, music_dir=None,
               handle="@bilesin_be_kz", tries=8):
    t_start = time.time()
    out_path = Path(out_path)
    points = dict(points or {})
    seed = int(time.time()) % 100000 if seed is None else seed
    rnd = random.Random(seed)
    theme = THEMES[0] if rnd.random() < 0.5 else rnd.choice(THEMES[1:])
    top_c, bot_c, wall, acc = theme

    log("Подбираю трассу и заезд…")
    c, sim, frames = pick_race(seed, tries, log)
    finish = sim.finish
    ranking = sim.ranking()
    winner = ranking[0]
    for place, i in enumerate(ranking[:len(POINTS)]):
        points[CITIES[i][0]] = points.get(CITIES[i][0], 0) + POINTS[place]
    table = sorted(points.items(), key=lambda kv: -kv[1])

    log("Рисую трассу…")
    course_img = draw_course(c, theme)
    HC = course_img.size[1]
    balls = [ball_sprite(col) for col in COLORS]
    labels = [label_sprite(cc[0]) for cc in CITIES]
    head = header_band(race_no, acc)
    hand = Image.new("RGBA", (420, 50), (0, 0, 0, 0))
    ImageDraw.Draw(hand).text((0, 0), handle, font=font(30), fill=(255, 255, 255, 170))

    race_n = len(frames)
    race_end = race_n / FPS
    total = race_end + FINALE_T
    tmp_video = str(out_path) + ".video.mp4"
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-b:v", "6000k",
         "-maxrate", "8000k", "-bufsize", "12000k", "-pix_fmt", "yuv420p", tmp_video], stdin=subprocess.PIPE)

    def emit(img):
        proc.stdin.write(np.asarray(img, np.uint8).tobytes())

    log(f"Рисую кадры: заезд {race_end:.0f} с + финал {FINALE_T:.0f} с…")
    rng = np.random.default_rng(seed)
    cam = -330.0
    panel_cache = {}
    conf, win_shown_t = [], None
    winner_t = finish[0][1] if finish else None
    last = None
    for fi, (pos, racing, nfin, t) in enumerate(frames):
        lead_y = pos[racing, 1].max() if racing.any() else c.finish_y
        target = min(lead_y, c.finish_y + 120) - H * 0.56
        target = max(target, -330.0)
        cam += (target - cam) * (0.10 if t > GATE_T else 0.0)
        cam = min(cam, c.end_y - H + 200)
        top = int(cam + Y0)
        top = max(0, min(top, HC - H))
        img = course_img.crop((0, top, W, top + H))
        d = ImageDraw.Draw(img, "RGBA")
        oy = Y0 - top
        if t < GATE_T:
            d.line([(OX, 150 + oy), (OX + CW, 150 + oy)], fill=acc + (255,), width=12)
        for cx, cy, L, arms, om, ph in c.spins:
            sy = cy + oy
            if -200 < sy < H + 200:
                a0 = ph + om * t
                for k in range(arms):
                    a = a0 + k * 2 * math.pi / arms
                    tip = (OX + cx + L * math.cos(a), sy + L * math.sin(a))
                    d.line([(OX + cx, sy), tip], fill=wall + (110,), width=26)
                    d.line([(OX + cx, sy), tip], fill=(255, 255, 255, 255), width=12)
                d.ellipse([OX + cx - 16, sy - 16, OX + cx + 16, sy + 16], fill=acc + (255,))
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
                paste(img, lb, lx, sy - R - 36)
        img.paste(head, (0, 0), head)
        order = order_at(pos, racing, finish, nfin)
        key = (tuple(order), nfin)
        if key not in panel_cache:
            if len(panel_cache) > 400:
                panel_cache.clear()
            panel_cache[key] = panel_img(order, nfin, acc)
        pn = panel_cache[key]
        img.paste(pn, (OX + CW + 14, 270), pn)
        tt = max(0.0, t - GATE_T)
        text_c(d, OX + CW + 14 + 145, 270 + pn.size[1] + 18, f"{int(tt // 60)}:{tt % 60:04.1f}", 40, (255, 255, 255), 5)
        if t < GATE_T:
            n = 3 - int(t / 0.4)
            text_c(d, OX + CW / 2, 640, str(n), 230, acc, 12)
        elif t < GATE_T + 0.7:
            text_c(d, OX + CW / 2, 680, "СТАРТ!", 120, (255, 255, 255), 10)
        if winner_t is not None and t >= winner_t:
            if win_shown_t is None:
                win_shown_t = t
                conf = confetti(rng, OX + CW / 2, c.finish_y + oy)
            k = min(1.0, (t - win_shown_t) / 0.25)
            d.rounded_rectangle([OX + 40, 330, OX + CW - 40, 610], radius=30, fill=(0, 0, 0, int(170 * k)))
            text_c(d, OX + CW / 2, 352, "ЖЕҢІМПАЗ!", int(46 + 22 * k), acc, 6)
            text_c(d, OX + CW / 2, 440, CITIES[winner][0], fit_size(CITIES[winner][0], int(60 + 40 * k), CW - 110),
                   COLORS[winner], 8)
            for p_ in conf:
                age = t - win_shown_t
                px = p_[0] + p_[2] * age
                py = p_[1] + p_[3] * age + 900 * age * age
                if 0 < py < H and age < 3:
                    s_ = p_[4]
                    d.rectangle([px - s_, py - s_ / 2, px + s_, py + s_ / 2], fill=p_[5])
        paste(img, hand, 30, H - 70)
        emit(img)
        last = img
        if fi % 150 == 0:
            log(f"  кадр {fi}/{race_n}, {time.time() - t_start:.0f} с")

    # финал: карта, победитель, таблица
    base = Image.blend(last.filter(ImageFilter.GaussianBlur(10)), Image.new("RGB", (W, H), (0, 0, 0)), 0.62)
    mp, pts = kz_map(960, winner, acc)
    mx, my = 60, 560
    blocks = []
    b1 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(b1)
    text_c(d1, W / 2, 230, "ЖЕҢІМПАЗ", 64, acc, 6)
    text_c(d1, W / 2, 315, CITIES[winner][0].upper(), fit_size(CITIES[winner][0].upper(), 104, W - 80),
           COLORS[winner], 9)
    if CITIES[winner][1] != CITIES[winner][0]:
        text_c(d1, W / 2, 440, f"({CITIES[winner][1]})", 38, (230, 230, 240), 5)
    blocks.append((0.3, b1))
    b2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(b2)
    y = my + mp.size[1] + 40
    medal = [(255, 205, 40), (215, 220, 230), (225, 150, 80)]
    if race_no >= 2:
        text_c(d2, W / 2, y, "ТУРНИР КЕСТЕСІ · Турнирная таблица", 36, acc, 5)
        for k, (name, pt) in enumerate(table[:5]):
            yy = y + 62 + k * 56
            i = [j for j in range(N) if CITIES[j][0] == name][0]
            d2.rounded_rectangle([150, yy - 6, W - 150, yy + 46], radius=14, fill=(255, 255, 255, 26))
            d2.text((175, yy), f"{k + 1}", font=font(36), fill=medal[k] if k < 3 else (220, 220, 230))
            d2.ellipse([228, yy + 6, 258, yy + 36], fill=COLORS[i], outline=(255, 255, 255), width=2)
            d2.text((276, yy), name, font=font(36), fill=(255, 255, 255))
            s_ = f"{pt} ұпай"
            d2.text((W - 175 - d2.textlength(s_, font=font(36)), yy), s_, font=font(36), fill=acc)
    else:
        text_c(d2, W / 2, y, "ҮЗДІК ҮШТІК · Тройка лидеров", 36, acc, 5)
        for k in range(3):
            i = ranking[k]
            yy = y + 66 + k * 64
            d2.rounded_rectangle([200, yy - 6, W - 200, yy + 52], radius=14, fill=(255, 255, 255, 26))
            d2.text((228, yy), f"{k + 1}", font=font(40), fill=medal[k])
            d2.ellipse([285, yy + 6, 321, yy + 42], fill=COLORS[i], outline=(255, 255, 255), width=2)
            d2.text((340, yy), CITIES[i][0], font=font(40), fill=(255, 255, 255))
    blocks.append((1.2, b2))
    b3 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(b3)
    text_c(d3, W / 2, 1640, "Сен қай қалаға жанкүйерсің?", 50, (255, 255, 255), 6)
    text_c(d3, W / 2, 1712, "За какой город болеешь? Пиши в комментариях ↓", 32, acc, 5)
    blocks.append((2.2, b3))
    wx, wy = pts[winner]
    nfin_frames = int(FINALE_T * FPS)
    for fi in range(nfin_frames):
        t = fi / FPS
        img = base.copy()
        a = min(1.0, t / 0.4)
        if a < 1:
            m2 = mp.copy()
            m2.putalpha(m2.getchannel("A").point(lambda v: int(v * a)))
            img.paste(m2, (mx, my), m2)
        else:
            img.paste(mp, (mx, my), mp)
        d = ImageDraw.Draw(img, "RGBA")
        if t > 0.5:
            pt_ = min(1.0, (t - 0.5) / 0.25)
            px, py = mx + wx, my + wy - (1 - pt_) * 160
            pulse = (t * 1.6) % 1.0
            if pt_ >= 1:
                rr = 16 + 60 * pulse
                d.ellipse([px - rr, py - rr, px + rr, py + rr], outline=acc + (int(220 * (1 - pulse)),), width=6)
            d.ellipse([px - 20, py - 20, px + 20, py + 20], fill=acc + (255,), outline=(255, 255, 255), width=4)
            lb = labels[winner]
            paste(img, lb, px - lb.size[0] / 2, py - 62)
        for t0, b in blocks:
            if t >= t0:
                k = min(1.0, (t - t0) / 0.3)
                if k < 1:
                    b2_ = b.copy()
                    b2_.putalpha(b2_.getchannel("A").point(lambda v: int(v * k)))
                    img.paste(b2_, (0, 0), b2_)
                else:
                    img.paste(b, (0, 0), b)
        paste(img, hand, 30, H - 70)
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

    win = CITIES[winner]
    title = f"Қай қала жеңеді? 🏁 Жарыс №{race_no} | Какой город победит?"
    desc = ("Жиырма қала — бір мәре! Сен қай қалаға жанкүйерсің? Пікірге жаз 👇\n"
            "20 городов Казахстана в одной гонке. За какой город болеешь? Пиши в комментариях!\n\n"
            "Күн сайын — жаңа жарыс. Каждый день новая гонка и турнирная таблица.\n\n"
            "#қазақстан #казахстан #жарыс #алматы #астана #шымкент #гонкашариков #shorts")
    tags = ["қазақстан", "казахстан", "жарыс", "гонка шариков", "marble race", "алматы", "астана",
            "шымкент", "города казахстана", "қалалар"]
    log(f"Готово за {time.time() - t_start:.0f} с: победил {win[0]}, ролик {total:.0f} с")
    return {"title": title, "description": desc, "tags": tags, "winner": win[0],
            "ranking": [CITIES[i][0] for i in ranking], "points": points, "duration": total,
            "seed": seed}


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "race.mp4"
    no = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    sd = int(sys.argv[3]) if len(sys.argv) > 3 else None
    info = build_race(out, no, {}, sd, music_dir=BASE / "music")
    print(json.dumps({k: v for k, v in info.items() if k != "description"}, ensure_ascii=False))
