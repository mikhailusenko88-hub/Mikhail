"""Движок роликов-цитат на акварели: сцена рисуется сама, поверх — цитата, перевод, автор, своя музыка.
render_quote(cfg, out_path) — cfg: dict(mark, ru, en, author_ru, author_en, scene, music, seed)
"""
import math
import random
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter, zoom

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import fastvid as fv  # noqa: E402
import music as music_mod  # noqa: E402
import orchestra as orchestra_mod  # noqa: E402

W, H = 1080, 1920
FPS = 30
FONTS = str(__import__("pathlib").Path(__file__).parent / "fonts")
F_RU = f"{FONTS}/Prata-Regular.ttf"
F_EN = f"{FONTS}/CormorantGaramond-Italic[wght].ttf"
F_SMALL = f"{FONTS}/PT_Serif-Web-Regular.ttf"
F_MARK = f"{FONTS}/CormorantGaramond[wght].ttf"


def noise(h, w, scale, seed):
    r = np.random.default_rng(seed)
    small = r.random((h // scale + 3, w // scale + 3)).astype(np.float32)
    big = zoom(small, scale, order=3)[:h, :w]
    big -= big.min()
    big /= max(1e-6, big.max())
    return big


# ---------------------------------------------------------------- бумага (один раз)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
HGT = 0.55 * noise(H, W, 3, 1) + 0.3 * noise(H, W, 9, 2) + 0.15 * noise(H, W, 30, 3)
HGT = gaussian_filter(HGT, 0.7)
gx_, gy_ = np.gradient(HGT)
SHADE = np.clip(1 + 1.1 * (-gy_ - gx_), 0.965, 1.035).astype(np.float32)
VALLEY = (1 - HGT).astype(np.float32)
SPEC = gaussian_filter(np.clip((SHADE - 1) * 25, 0, 1), 2.5) * 0.6 + 0.4 * gaussian_filter(np.clip((SHADE - 1) * 25, 0, 1), 12)
GRAIN = noise(H, W, 2, 4)
STREAK = gaussian_filter(np.random.default_rng(5).random((H, W)).astype(np.float32), (0.6, 7))
STREAK = (STREAK - STREAK.min()) / (STREAK.max() - STREAK.min())
PAPER = (np.stack([0.972 + 0 * xx, 0.960 + 0 * xx, 0.930 + 0 * xx], -1) *
         (0.975 + 0.025 * noise(H, W, 40, 8))[..., None]).astype(np.float32)
FACT = (SHADE[..., None] * (1.03 - 0.05 * (xx / W) - 0.04 * (yy / H))[..., None] *
        np.clip(1 - 0.10 * (((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2), 0.88, 1)[..., None]
        ).astype(np.float32)


def clampbox(x0, y0, x1, y1):
    return max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))


def apply(canvas, A, C, box, kind):
    x0, y0, x1, y1 = box
    a = A
    if kind in ("mult", "multgrad"):
        a = np.clip(a * (0.88 + 0.24 * VALLEY[y0:y1, x0:x1]), 0, 1)
        canvas[y0:y1, x0:x1] *= 1 - a[..., None] * (1 - np.asarray(C, np.float32))
    elif kind == "over":
        canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - a[..., None]) + a[..., None] * np.asarray(C, np.float32)
    return a


class Bloom:
    """Капля по мокрому: растекается неровным пятном."""
    def __init__(self, t0, x, y, R, col, dens=0.75, dur=2.2, seed=0, kind="mult", soft=1.0):
        self.t0, self.t1, self.x, self.y, self.R, self.col, self.dens, self.kind = t0, t0 + dur, x, y, R, col, dens, kind
        self.box = clampbox(x - R * 1.4, y - R * 1.4, x + R * 1.4, y + R * 1.4)
        x0, y0, x1, y1 = self.box
        Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        self.d = np.hypot(X - x, Y - y)
        th = np.arctan2(Y - y, X - x)
        r = np.random.default_rng(seed)
        self.wob = sum(r.uniform(0.03, 0.07) * np.sin(k * th + r.uniform(0, 6.28)) for k in (1, 2, 3))
        self.wob += 0.30 * (noise(y1 - y0, x1 - x0, 55, seed) - 0.5) + 0.12 * (noise(y1 - y0, x1 - x0, 12, seed + 7) - 0.5)
        self.tex = 0.75 + 0.35 * noise(y1 - y0, x1 - x0, 70, seed + 1)
        self.soft = soft
        self.clip = None

    def clip_to(self, rx0, ry0, rx1, ry1):
        x0, y0, x1, y1 = self.box
        Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        m = ((X >= rx0) & (X < rx1) & (Y >= ry0) & (Y < ry1)).astype(np.float32)
        self.clip = gaussian_filter(m, 2.0)
        return self

    def alpha(self, t):
        u = min(1.0, max(0.0, (t - self.t0) / (self.t1 - self.t0)))
        rad = self.R * (1 - math.exp(-4.2 * u)) / (1 - math.exp(-4.2)) + 6
        rr = rad * (1 + self.wob)
        m = np.clip((rr - self.d) / ((6 + 0.12 * rad) * self.soft), 0, 1)
        core = 0.55 + 0.45 * np.exp(-self.d / max(rad, 1) * 1.6)
        ring = np.exp(-((rr - self.d) / (6 + 0.035 * rad)) ** 2) * 0.35 * u
        a = np.clip(m * core * self.dens * self.tex + ring * m, 0, 1)
        return a * self.clip if self.clip is not None else a


class Stroke:
    """Мазок по траектории."""
    def __init__(self, t0, dur, pts, widths, col, dens=0.95, blur=1.2, kind="mult", seed=0):
        self.t0, self.t1 = t0, t0 + dur
        self.pts = np.array(pts, np.float32)
        self.w = np.array(widths, np.float32)
        if len(self.w) < len(self.pts):
            self.w = np.full(len(self.pts), self.w[0], np.float32)
        seg = np.hypot(*(self.pts[1:] - self.pts[:-1]).T)
        self.cum = np.concatenate([[0], np.cumsum(seg)])
        m = self.w.max() + 4 * blur
        self.box = clampbox(self.pts[:, 0].min() - m, self.pts[:, 1].min() - m,
                            self.pts[:, 0].max() + m, self.pts[:, 1].max() + m)
        self.col, self.dens, self.blur, self.kind = col, dens, blur, kind

    def _pt(self, t):
        u = min(1.0, max(0.0, (t - self.t0) / (self.t1 - self.t0)))
        u = u * u * (3 - 2 * u)
        L = self.cum[-1] * u
        k = int(min(len(self.pts) - 1, max(1, np.searchsorted(self.cum, L, side="right"))))
        a = (L - self.cum[k - 1]) / max(1e-6, self.cum[k] - self.cum[k - 1])
        return k, self.pts[k - 1] + (self.pts[k] - self.pts[k - 1]) * min(1, max(0, a))

    def alpha(self, t):
        k, p = self._pt(t)
        x0, y0, x1, y1 = self.box
        im = Image.new("L", (x1 - x0, y1 - y0), 0)
        dr = ImageDraw.Draw(im)
        pts = self.pts[:k].tolist() + [p.tolist()]
        for i in range(1, len(pts)):
            wdt = float(self.w[min(i, len(self.w) - 1)])
            (ax, ay), (bx, by) = pts[i - 1], pts[i]
            dr.line([(ax - x0, ay - y0), (bx - x0, by - y0)], fill=255, width=max(1, int(wdt)))
            dr.ellipse([bx - x0 - wdt / 2, by - y0 - wdt / 2, bx - x0 + wdt / 2, by - y0 + wdt / 2], fill=255)
        m = gaussian_filter(np.asarray(im, np.float32) / 255, self.blur)
        st = STREAK[y0:y1, x0:x1]
        return np.clip(m * self.dens * (0.8 + 0.25 * st) * (0.9 + 0.1 * GRAIN[y0:y1, x0:x1]), 0, 1)


class Wash:
    """Заливка многоугольника: рваный край, потемнение по контуру, градиент цвета, мокрый фронт."""
    def __init__(self, t0, dur, poly, cols, dens=0.6, blur=3.0, rough=0.22, direction="down", seed=0,
                 kind="multgrad", streak=0.0, edge=0.5):
        self.t0, self.t1, self.kind = t0, t0 + dur, kind
        P = np.array(poly, np.float32)
        m = 30
        self.box = clampbox(P[:, 0].min() - m, P[:, 1].min() - m, P[:, 0].max() + m, P[:, 1].max() + m)
        x0, y0, x1, y1 = self.box
        im = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in poly], fill=255)
        pm = gaussian_filter(np.asarray(im, np.float32) / 255, blur)
        nz = noise(y1 - y0, x1 - x0, 28, seed) - 0.5
        nz2 = noise(y1 - y0, x1 - x0, 7, seed + 3) - 0.5
        self.m = np.clip((pm - (0.5 + rough * nz + 0.25 * rough * nz2)) / 0.14, 0, 1)
        inner = gaussian_filter(self.m, 7)
        self.edge = np.clip(self.m - inner, 0, 1) * edge
        self.tex = (0.8 + 0.3 * noise(y1 - y0, x1 - x0, 60, seed + 1)) * (0.92 + 0.08 * GRAIN[y0:y1, x0:x1])
        if streak:
            self.tex *= 1 - streak + 2 * streak * STREAK[y0:y1, x0:x1]
        self.dens = dens
        Y, X = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        if direction in ("down", "up"):
            u = (Y - P[:, 1].min()) / max(1.0, P[:, 1].max() - P[:, 1].min())
        else:
            u = (X - P[:, 0].min()) / max(1.0, P[:, 0].max() - P[:, 0].min())
        if direction in ("up", "left"):
            u = 1 - u
        self.front = np.clip(u, 0, 1) + 0.12 * (noise(y1 - y0, x1 - x0, 50, seed + 9) - 0.5)
        cols = np.array(cols, np.float32)
        if len(cols) == 1:
            self.col = np.broadcast_to(cols[0], (y1 - y0, x1 - x0, 3)).astype(np.float32)
        else:
            g = np.clip((Y - P[:, 1].min()) / max(1.0, P[:, 1].max() - P[:, 1].min()), 0, 1) * (len(cols) - 1)
            k = np.clip(np.floor(g).astype(int), 0, len(cols) - 2)
            f = (g - k)[..., None]
            self.col = cols[k] * (1 - f) + cols[k + 1] * f

    def alpha(self, t):
        u = min(1.0, max(0.0, (t - self.t0) / (self.t1 - self.t0)))
        rev = np.clip((u * 1.25 - self.front) / 0.10, 0, 1)
        wetfront = np.exp(-((u * 1.25 - self.front) / 0.05) ** 2) * 0.35 * (1 - u)
        return np.clip((self.m * self.dens * self.tex + self.edge) * rev + wetfront * self.m, 0, 1)


class Dots:
    """Россыпь точек (звёзды, цветы, брызги) — появляются по очереди."""
    def __init__(self, t0, dur, dots, kind="over", blur=0.8):
        # dots: (x, y, r, (col), delay 0..1)
        self.t0, self.t1, self.kind, self.blur = t0, t0 + dur, kind, blur
        xs = [d[0] for d in dots]; ys = [d[1] for d in dots]
        m = max(d[2] for d in dots) * 3 + 6
        self.box = clampbox(min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
        self.dots = dots
        self.col = dots[0][3]
        self.multi = len({tuple(d[3]) for d in dots}) > 1
        self.dens = 1.0

    def alpha(self, t):
        u = min(1.0, max(0.0, (t - self.t0) / (self.t1 - self.t0)))
        x0, y0, x1, y1 = self.box
        im = Image.new("L", (x1 - x0, y1 - y0), 0)
        dr = ImageDraw.Draw(im)
        for x, y, r, c, dl in self.dots:
            if u >= dl:
                dr.ellipse([x - x0 - r, y - y0 - r, x - x0 + r, y - y0 + r], fill=255)
        return np.asarray(im.filter(ImageFilter.GaussianBlur(self.blur)), np.float32) / 255 * 0.95

    def colour(self, t):
        """Для разноцветных точек — массив цвета."""
        if not self.multi:
            return self.col
        x0, y0, x1, y1 = self.box
        im = Image.new("RGB", (x1 - x0, y1 - y0), (0, 0, 0))
        dr = ImageDraw.Draw(im)
        for x, y, r, c, dl in self.dots:
            dr.ellipse([x - x0 - r - 2, y - y0 - r - 2, x - x0 + r + 2, y - y0 + r + 2],
                       fill=tuple(int(v * 255) for v in c))
        return np.asarray(im.filter(ImageFilter.GaussianBlur(self.blur)), np.float32) / 255


# ---------------------------------------------------------------- тексты
def font(path, size, wght=None):
    f = ImageFont.truetype(path, size)
    if wght is not None:
        try:
            f.set_variation_by_axes([wght])
        except Exception:  # noqa: BLE001
            pass
    return f


def text_sprite(s, fnt, fill, spacing=0):
    if spacing:
        widths = [fnt.getlength(ch) for ch in s]
        tw = int(sum(widths) + spacing * (len(s) - 1))
    else:
        tw = int(fnt.getlength(s))
    asc, desc = fnt.getmetrics()
    img = Image.new("RGBA", (tw + 20, asc + desc + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if spacing:
        x = 10
        for ch, w in zip(s, widths):
            d.text((x, 10), ch, font=fnt, fill=fill)
            x += w + spacing
    else:
        d.text((10, 10), s, font=fnt, fill=fill)
    return img


def paste_fade(img, spr, x, y, a):
    if a <= 0:
        return
    if a < 1:
        al = spr.getchannel("A").point(lambda v: int(v * a))
        spr = spr.copy()
        spr.putalpha(al)
    fv.paste(img, spr, int(x), int(y))


def ease(t0, dur, t):
    u = min(1.0, max(0.0, (t - t0) / dur))
    return u * u * (3 - 2 * u)


def fit_font(path, lines, size, max_w=900, min_size=50, wght=None):
    while size > min_size:
        f = font(path, size, wght)
        if max(f.getlength(s) for s in lines) <= max_w:
            return f, size
        size -= 2
    return font(path, size, wght), size


# ---------------------------------------------------------------- элементы сцен
def ridge(mx, base, amp, k1, k2, ph, amp2=0.3):
    return base - amp * np.abs(np.sin(mx / k1 + ph)) - amp * amp2 * np.sin(mx / k2) - amp * 0.12 * np.cos(mx / (k2 * 0.43))


def birds(ops, t0, spots, col=(0.30, 0.30, 0.40)):
    for j, (bx, by, s_) in enumerate(spots):
        pts = [(bx - s_, by + 2), (bx - s_ * 0.5, by - s_ * 0.45), (bx, by + 1), (bx + s_ * 0.5, by - s_ * 0.45),
               (bx + s_, by + 2)]
        ops.append(Stroke(t0 + j * 0.15, 0.25, pts, [3], col, dens=0.8, blur=0.6, seed=100 + j))
    return t0 + 0.15 * len(spots) + 0.3


def bare_tree(ops, t0, x, base, h, seed, col=(0.26, 0.22, 0.24)):
    r = random.Random(seed)
    top = base - h
    ops.append(Stroke(t0, 0.6, [(x, base), (x + 4, base - h * 0.55), (x + 10, top)], [15, 10, 5], col, dens=0.92,
                      blur=0.8, seed=seed))
    t = t0 + 0.4

    def branch(x0, y0, ang, ln, wd, depth):
        nonlocal t
        if depth == 0 or ln < 14:
            return
        x1 = x0 + math.cos(ang) * ln
        y1 = y0 + math.sin(ang) * ln
        xm = x0 + math.cos(ang + r.uniform(-0.25, 0.25)) * ln * 0.5
        ym = y0 + math.sin(ang + r.uniform(-0.25, 0.25)) * ln * 0.5
        ops.append(Stroke(t, 0.3, [(x0, y0), (xm, ym), (x1, y1)], [wd, wd * 0.7, wd * 0.4], col, dens=0.9,
                          blur=0.6, seed=seed + int(x1 + y1)))
        t += 0.08
        for _ in range(r.choice([1, 2, 2, 3])):
            branch(x1, y1, ang + r.uniform(-0.9, 0.9), ln * r.uniform(0.5, 0.75), max(1.6, wd * 0.6), depth - 1)

    for j in range(5):
        fy = base - h * r.uniform(0.35, 0.9)
        side = -1 if j % 2 else 1
        ang = -math.pi / 2 + side * r.uniform(0.45, 1.05)
        branch(x + 4, fy, ang, h * r.uniform(0.28, 0.42), 6, 3)
    return t + 0.3


# ---------------------------------------------------------------- СЦЕНЫ
def scene_sunrise(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.4, [(px0, py0), (px1, py0), (px1, hor + 6), (px0, hor + 6)],
                    [(0.72, 0.80, 0.92), (0.86, 0.84, 0.92), (0.98, 0.82, 0.70), (0.99, 0.90, 0.66)],
                    dens=0.6, blur=4, rough=0.18, seed=11 + seed))
    ops.append(Bloom(t0 + 1.4, px0 + 205, py0 + 330, 220, (0.97, 0.72, 0.70), dens=0.28, dur=1.8, seed=41 + seed, soft=1.8).clip_to(px0, py0, px1, hor))
    ops.append(Bloom(t0 + 1.8, px0 + 705, py0 + 250, 240, (0.99, 0.82, 0.60), dens=0.26, dur=1.8, seed=42 + seed, soft=1.8).clip_to(px0, py0, px1, hor))
    ops.append(Bloom(t0 + 2.2, px0 + 465, py0 + 110, 260, (0.78, 0.82, 0.94), dens=0.22, dur=1.8, seed=43 + seed, soft=2.0).clip_to(px0, py0, px1, hor))
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    far = ridge(mx, hor - 70, 75, 190, 63, 1.0 + seed)
    near = ridge(mx, hor - 24, 42, 125, 41, 2.6 + seed)
    ops.append(Wash(t0 + 2.7, 1.3, list(zip(mx, far)) + [(px1 + 10, hor), (px0 - 10, hor)],
                    [(0.70, 0.74, 0.88), (0.62, 0.66, 0.84)], dens=0.55, blur=2.5, rough=0.14, direction="right", seed=21, edge=0.35))
    ops.append(Wash(t0 + 3.7, 1.1, list(zip(mx, near)) + [(px1 + 10, hor), (px0 - 10, hor)],
                    [(0.50, 0.55, 0.76), (0.42, 0.47, 0.70)], dens=0.68, blur=2, rough=0.12, direction="right", seed=22, edge=0.4))
    ops.append(Wash(t0 + 4.5, 1.6, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)],
                    [(0.99, 0.90, 0.70), (0.97, 0.82, 0.74), (0.80, 0.84, 0.94), (0.68, 0.76, 0.92)],
                    dens=0.55, blur=4, rough=0.18, seed=12, streak=0.25))
    ops.append(Wash(t0 + 5.5, 1.2, [(x, 2 * hor - y) for x, y in zip(mx, far)] + [(px1 + 10, hor + 3), (px0 - 10, hor + 3)],
                    [(0.66, 0.70, 0.86)], dens=0.26, blur=6, rough=0.2, direction="right", seed=23, streak=0.45, edge=0.1))
    ops.append(Wash(t0 + 5.9, 1.0, [(x, 2 * hor - y) for x, y in zip(mx, near)] + [(px1 + 10, hor + 3), (px0 - 10, hor + 3)],
                    [(0.50, 0.55, 0.76)], dens=0.32, blur=5, rough=0.2, direction="right", seed=24, streak=0.5, edge=0.1))
    for j in range(5):
        yv = hor + 150 + j * 70
        if yv < py1 - 20:
            ops.append(Stroke(t0 + 6.2 + j * 0.1, 0.5, [(px0 + 40 + j * 30, yv), (px1 - 40 - j * 25, yv + 4)], [6],
                              (0.60, 0.68, 0.88), dens=0.25, blur=5, seed=60 + j))
    ops.append(Bloom(t0 + 6.5, px0 + 445, hor - 165, 100, (1.0, 0.98, 0.90), dens=0.9, dur=1.2, seed=80, kind="over", soft=4.0))
    ops.append(Bloom(t0 + 7.0, px0 + 445, hor - 165, 38, (1.0, 1.0, 0.97), dens=1.0, dur=0.8, seed=81, kind="over", soft=1.2))
    rr = random.Random(5 + seed)
    for j in range(14):
        yv = hor + 22 + j * 24 + rr.uniform(-4, 4)
        if yv > py1 - 10:
            break
        hw = 25 + j * 13
        cx_ = px0 + 445 + rr.uniform(-hw * 0.5, hw * 0.5)
        ln = rr.uniform(0.25, 0.7) * hw
        ops.append(Stroke(t0 + 7.2 + j * 0.06, 0.25, [(cx_ - ln, yv), (cx_ + ln, yv)], [4 if j < 7 else 5],
                          (1.0, 0.99, 0.95), dens=rr.uniform(0.5, 0.85), blur=1.0, kind="over", seed=90 + j))
    end = birds(ops, t0 + 8.1, [(px0 + 235, py0 + 170, 14), (px0 + 295, py0 + 215, 11), (px0 + 605, py0 + 150, 13),
                                (px0 + 675, py0 + 195, 10), (px0 + 545, py0 + 250, 9)])
    return ops, end, "motes"


def scene_winter(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.2, [(px0, py0), (px1, py0), (px1, hor + 4), (px0, hor + 4)],
                    [(0.74, 0.79, 0.88), (0.84, 0.86, 0.91), (0.92, 0.90, 0.90)], dens=0.6, blur=4, rough=0.18, seed=31 + seed))
    ops.append(Bloom(t0 + 1.2, px0 + 300, py0 + 160, 230, (0.80, 0.82, 0.90), dens=0.22, dur=1.8, seed=44 + seed, soft=2.0).clip_to(px0, py0, px1, hor))
    ops.append(Bloom(t0 + 1.6, px0 + 650, py0 + 260, 200, (0.95, 0.88, 0.82), dens=0.18, dur=1.8, seed=45 + seed, soft=2.0).clip_to(px0, py0, px1, hor))
    # далёкий лес — зубчатый силуэт елей
    r = random.Random(7 + seed)
    xs = np.arange(px0 - 10, px1 + 12, 14)
    base_y = hor - 20
    pts = []
    for x in xs:
        hgt = 28 + 46 * abs(math.sin(x / 160 + 1.3)) + r.uniform(-8, 16)
        pts.append((x, base_y - hgt))
        pts.append((x + 7, base_y - hgt * 0.45))
    ops.append(Wash(t0 + 2.4, 1.4, pts + [(px1 + 12, hor + 2), (px0 - 10, hor + 2)], [(0.58, 0.60, 0.72), (0.50, 0.52, 0.66)],
                    dens=0.55, blur=1.4, rough=0.08, direction="right", seed=32, edge=0.3))
    # дымка над лесом
    ops.append(Wash(t0 + 3.6, 1.0, [(px0, hor - 60), (px1, hor - 60), (px1, hor + 2), (px0, hor + 2)], [(0.96, 0.95, 0.95)],
                    dens=0.45, blur=12, rough=0.3, direction="right", seed=33, kind="over", edge=0.0))
    # снежное поле: общая прозрачная подложка и лёгкие голубые тени
    ops.append(Wash(t0 + 3.9, 1.2, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.86, 0.89, 0.95), (0.80, 0.85, 0.94)],
                    dens=0.16, blur=4, rough=0.18, seed=39, streak=0.2, edge=0.15))
    for j, (yv, hh, dn) in enumerate(((hor + 40, 50, 0.16), (hor + 150, 80, 0.14), (hor + 300, 110, 0.18), (hor + 470, 120, 0.15))):
        if yv > py1:
            break
        ys = min(py1, yv + hh)
        poly = [(px0, yv + 12 * math.sin(k)) for k in np.linspace(0, 3, 6)]
        poly = [(px0 + k * (px1 - px0) / 7, yv + 14 * math.sin(k * 1.7 + j)) for k in range(8)] + \
               [(px1 - k * (px1 - px0) / 7, ys + 10 * math.cos(k * 1.3 + j)) for k in range(8)]
        ops.append(Wash(t0 + 4.2 + j * 0.3, 0.9, poly, [(0.76, 0.82, 0.93)], dens=dn, blur=9, rough=0.25, direction="right",
                        seed=34 + j, streak=0.3, edge=0.05))
    # одинокое дерево
    end = bare_tree(ops, t0 + 5.4, px0 + 600, min(py1 - 40, hor + 230), 290, seed=9 + seed)
    # снежные шапки на земле у дерева — след
    ops.append(Stroke(end, 0.5, [(px0 + 540, min(py1 - 30, hor + 236)), (px0 + 670, min(py1 - 26, hor + 240))], [10],
                      (0.70, 0.76, 0.90), dens=0.25, blur=5, seed=36))
    end = birds(ops, end + 0.4, [(px0 + 250, py0 + 140, 11), (px0 + 300, py0 + 175, 9)], col=(0.40, 0.40, 0.48))
    return ops, end, "snow"


def scene_night(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.6, [(px0, py0), (px1, py0), (px1, hor + 4), (px0, hor + 4)],
                    [(0.13, 0.15, 0.34), (0.22, 0.20, 0.44), (0.46, 0.34, 0.54), (0.82, 0.62, 0.60)],
                    dens=0.9, blur=4, rough=0.16, seed=51 + seed, edge=0.25))
    ops.append(Bloom(t0 + 1.5, px0 + 250, py0 + 200, 200, (0.26, 0.30, 0.56), dens=0.25, dur=1.6, seed=46 + seed, soft=2.2).clip_to(px0, py0, px1, hor))
    # звёзды
    r = random.Random(13 + seed)
    stars = [(r.uniform(px0 + 15, px1 - 15), r.uniform(py0 + 12, py0 + (hor - py0) * 0.62),
              r.choice([1.3, 1.6, 2.0, 2.4, 3.0]), (1.0, 0.98, 0.92), r.random()) for _ in range(75)]
    ops.append(Dots(t0 + 2.6, 1.6, stars, blur=0.7))
    # луна
    mxp, myp = px0 + 640, py0 + 175
    ops.append(Bloom(t0 + 3.0, mxp, myp, 120, (0.95, 0.93, 0.88), dens=0.45, dur=1.4, seed=82, kind="over", soft=4.5))
    ops.append(Bloom(t0 + 3.4, mxp, myp, 40, (1.0, 0.99, 0.93), dens=1.0, dur=0.8, seed=83, kind="over", soft=0.9))
    mx = np.linspace(px0 - 10, px1 + 10, 90)
    far = ridge(mx, hor - 110, 120, 150, 47, 0.4 + seed, amp2=0.35)
    near = ridge(mx, hor - 40, 62, 96, 33, 2.2 + seed, amp2=0.4)
    ops.append(Wash(t0 + 4.2, 1.4, list(zip(mx, far)) + [(px1 + 10, hor), (px0 - 10, hor)],
                    [(0.40, 0.36, 0.60), (0.30, 0.28, 0.50)], dens=0.78, blur=2, rough=0.1, direction="right", seed=52, edge=0.3))
    ops.append(Wash(t0 + 5.2, 1.2, list(zip(mx, near)) + [(px1 + 10, hor), (px0 - 10, hor)],
                    [(0.18, 0.17, 0.32), (0.12, 0.12, 0.24)], dens=0.9, blur=1.6, rough=0.08, direction="right", seed=53, edge=0.3))
    # озеро и дорожка луны
    ops.append(Wash(t0 + 6.2, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)],
                    [(0.30, 0.26, 0.46), (0.18, 0.18, 0.36), (0.10, 0.11, 0.24)], dens=0.85, blur=4, rough=0.16, seed=54, streak=0.35, edge=0.2))
    ops.append(Wash(t0 + 7.0, 1.0, [(x, 2 * hor - y) for x, y in zip(mx, near)] + [(px1 + 10, hor + 3), (px0 - 10, hor + 3)],
                    [(0.10, 0.10, 0.20)], dens=0.4, blur=6, rough=0.2, direction="right", seed=55, streak=0.5, edge=0.05))
    rr = random.Random(3 + seed)
    for j in range(12):
        yv = hor + 18 + j * 26 + rr.uniform(-3, 3)
        if yv > py1 - 10:
            break
        hw = 18 + j * 9
        cx_ = mxp + rr.uniform(-hw * 0.4, hw * 0.4)
        ln = rr.uniform(0.3, 0.7) * hw
        ops.append(Stroke(t0 + 7.6 + j * 0.07, 0.25, [(cx_ - ln, yv), (cx_ + ln, yv)], [3 if j < 6 else 4],
                          (0.96, 0.94, 0.86), dens=rr.uniform(0.45, 0.8), blur=0.9, kind="over", seed=92 + j))
    # туман у подножия
    ops.append(Wash(t0 + 8.2, 1.2, [(px0, hor - 30), (px1, hor - 30), (px1, hor + 30), (px0, hor + 30)], [(0.70, 0.62, 0.74)],
                    dens=0.3, blur=12, rough=0.35, direction="right", seed=56, kind="over", edge=0.0))
    return ops, t0 + 9.6, "fireflies"


def scene_meadow(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.2, [(px0, py0), (px1, py0), (px1, hor + 6), (px0, hor + 6)],
                    [(0.64, 0.77, 0.92), (0.84, 0.88, 0.94), (0.98, 0.91, 0.76)], dens=0.55, blur=4, rough=0.18, seed=61 + seed))
    ops.append(Bloom(t0 + 1.3, px0 + 620, py0 + 120, 170, (0.99, 0.90, 0.70), dens=0.22, dur=1.6, seed=47 + seed, soft=2.0).clip_to(px0, py0, px1, hor))
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    far = ridge(mx, hor - 50, 55, 210, 70, 0.8 + seed)
    ops.append(Wash(t0 + 2.3, 1.3, list(zip(mx, far)) + [(px1 + 10, hor + 2), (px0 - 10, hor + 2)],
                    [(0.62, 0.74, 0.72), (0.56, 0.70, 0.66)], dens=0.42, blur=4, rough=0.16, direction="right", seed=62, edge=0.25))
    ops.append(Wash(t0 + 3.4, 1.7, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)],
                    [(0.80, 0.84, 0.56), (0.66, 0.78, 0.44), (0.52, 0.70, 0.38)], dens=0.62, blur=4, rough=0.18, seed=63, streak=0.15, edge=0.3))
    # тропинка — сужается к горизонту, вьётся
    left, right = [], []
    for k in np.linspace(0, 1, 24):
        yv = py1 + 10 - k * (py1 + 10 - hor - 6)
        cx_ = px0 + 470 + 90 * math.sin(k * 3.4 + 0.5) * (1 - k * 0.6)
        hw = 6 + 150 * (1 - k) ** 1.9
        left.append((cx_ - hw, yv))
        right.append((cx_ + hw, yv))
    ops.append(Wash(t0 + 5.2, 1.6, left + right[::-1], [(0.95, 0.89, 0.72)], dens=0.88, blur=2.5, rough=0.2, direction="up",
                    seed=64, kind="over", edge=0.0))
    ops.append(Wash(t0 + 5.3, 1.6, [(x - 10, y) for x, y in left] + [(x + 10, y) for x, y in right[::-1]], [(0.58, 0.60, 0.38)],
                    dens=0.22, blur=5, rough=0.25, direction="up", seed=65, edge=0.0))
    # дерево с кроной слева
    tx, tb = px0 + 150, hor + 10
    ops.append(Stroke(t0 + 6.6, 0.5, [(tx, tb + 30), (tx + 3, tb - 60), (tx + 8, tb - 110)], [12, 8, 4], (0.32, 0.26, 0.24), dens=0.9, blur=0.8, seed=66))
    for j, (dx, dy, R_, c) in enumerate(((0, -150, 72, (0.40, 0.58, 0.34)), (-55, -120, 55, (0.46, 0.64, 0.36)), (55, -125, 58, (0.36, 0.54, 0.32)),
                                          (10, -95, 50, (0.44, 0.62, 0.36)))):
        ops.append(Bloom(t0 + 6.9 + j * 0.15, tx + dx, tb + dy, R_, c, dens=0.62, dur=1.0, seed=67 + j, soft=1.3))
    # цветы
    r = random.Random(17 + seed)
    cols = [(0.62, 0.46, 0.80), (0.96, 0.96, 0.98), (0.92, 0.56, 0.68), (0.98, 0.84, 0.36)]
    flowers = []
    for _ in range(140):
        k = r.random() ** 0.6
        yv = hor + 60 + k * (py1 - hor - 70)
        flowers.append((r.uniform(px0 + 12, px1 - 12), yv, 1.5 + 4.5 * (yv - hor) / (py1 - hor), r.choice(cols), r.random()))
    ops.append(Dots(t0 + 7.6, 1.6, flowers, blur=0.9))
    end = birds(ops, t0 + 8.6, [(px0 + 560, py0 + 110, 12), (px0 + 620, py0 + 150, 10), (px0 + 700, py0 + 95, 9)])
    return ops, end, "motes"


def scene_sea(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.2, [(px0, py0), (px1, py0), (px1, hor + 6), (px0, hor + 6)],
                    [(0.54, 0.70, 0.90), (0.76, 0.84, 0.93), (0.95, 0.91, 0.84)], dens=0.62, blur=4, rough=0.18, seed=71 + seed))
    r = random.Random(23 + seed)
    for j in range(4):
        cx_, cy_ = px0 + 120 + j * 230 + r.uniform(-40, 40), py0 + 90 + r.uniform(0, 120)
        R_ = r.uniform(85, 130)
        ops.append(Bloom(t0 + 1.4 + j * 0.3, cx_ + 20, cy_ + 30, R_ * 1.1, (0.72, 0.76, 0.86), dens=0.14, dur=1.3, seed=48 + j, soft=2.5).clip_to(px0, py0, px1, hor))
        ops.append(Bloom(t0 + 1.5 + j * 0.3, cx_, cy_, R_, (0.99, 0.99, 0.98), dens=0.75, dur=1.4, seed=58 + j, kind="over", soft=2.2).clip_to(px0, py0, px1, hor))
    ops.append(Wash(t0 + 3.2, 1.8, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)],
                    [(0.54, 0.72, 0.86), (0.38, 0.60, 0.80), (0.26, 0.47, 0.72)], dens=0.74, blur=4, rough=0.2, seed=72, streak=0.35, edge=0.3))
    ops.append(Stroke(t0 + 4.6, 0.8, [(px0, hor + 6), (px1, hor + 6)], [8], (0.30, 0.50, 0.74), dens=0.35, blur=3, seed=73))
    # волны-блики
    for j in range(22):
        yv = hor + 30 + r.uniform(0, 1) ** 0.7 * (py1 - hor - 50)
        ln = 12 + (yv - hor) / (py1 - hor) * 70
        x = r.uniform(px0 + 20 + ln, px1 - 20 - ln)
        ops.append(Stroke(t0 + 5.0 + j * 0.07, 0.3, [(x - ln, yv), (x + ln, yv + r.uniform(-2, 2))], [3 if yv < hor + 150 else 5],
                          (0.97, 0.98, 0.98), dens=r.uniform(0.45, 0.8), blur=0.9, kind="over", seed=93 + j))
    # парусник
    bx, by = px0 + 560, hor + 160
    ops.append(Wash(t0 + 6.8, 0.6, [(bx - 48, by), (bx + 52, by), (bx + 38, by + 16), (bx - 36, by + 16)], [(0.22, 0.20, 0.26)],
                    dens=0.95, blur=1.0, rough=0.04, direction="right", seed=74, edge=0.0))
    ops.append(Stroke(t0 + 7.2, 0.4, [(bx + 2, by), (bx + 2, by - 150)], [3], (0.22, 0.20, 0.26), dens=0.9, blur=0.6, seed=75))
    ops.append(Wash(t0 + 7.5, 0.8, [(bx + 6, by - 146), (bx + 6, by - 6), (bx + 72, by - 6)], [(0.99, 0.98, 0.95)],
                    dens=0.96, blur=1.2, rough=0.05, direction="down", seed=76, kind="over", edge=0.0))
    ops.append(Wash(t0 + 7.7, 0.8, [(bx - 2, by - 120), (bx - 2, by - 8), (bx - 50, by - 8)], [(0.90, 0.90, 0.90)],
                    dens=0.92, blur=1.2, rough=0.05, direction="down", seed=77, kind="over", edge=0.0))
    ops.append(Wash(t0 + 7.8, 0.8, [(bx + 6, by - 146), (bx + 6, by - 60), (bx + 30, by - 60)], [(0.84, 0.84, 0.86)],
                    dens=0.5, blur=1.5, rough=0.05, direction="down", seed=78, edge=0.0))
    ops.append(Stroke(t0 + 8.3, 0.3, [(bx + 2, by - 150), (bx + 18, by - 143)], [4], (0.88, 0.24, 0.22), dens=0.95, blur=0.5, seed=79))
    ops.append(Stroke(t0 + 8.5, 0.6, [(bx - 40, by + 26), (bx + 46, by + 28)], [12], (0.22, 0.34, 0.56), dens=0.35, blur=5, seed=80))
    end = birds(ops, t0 + 9.0, [(px0 + 190, py0 + 150, 13), (px0 + 250, py0 + 190, 11), (px0 + 720, py0 + 120, 12), (px0 + 790, py0 + 165, 9)])
    return ops, end, "none"


SCENES = {"sunrise": (scene_sunrise, 0.6), "winter": (scene_winter, 0.42), "night": (scene_night, 0.62),
          "meadow": (scene_meadow, 0.38), "sea": (scene_sea, 0.5)}


# ---------------------------------------------------------------- музыка
class Music:
    def __init__(self, total, seed, sr=44100):
        self.sr = sr
        self.a = np.zeros(int((total + 2) * sr))
        self.r = random.Random(seed)
        self.rng = np.random.default_rng(seed)

    def put(self, sig, at):
        s = int(at * self.sr)
        if 0 <= s < len(self.a):
            self.a[s:s + len(sig)] += sig[:len(self.a) - s]

    def _tt(self, dur):
        return np.arange(int(dur * self.sr)) / self.sr

    def piano(self, f, dur, vol):
        tt = self._tt(dur)
        env = np.exp(-tt * 1.6) * np.minimum(1, tt * 120)
        s = np.zeros_like(tt)
        for h, amp, dec in ((1, 1.0, 0), (2, 0.42, 1.5), (3, 0.2, 3), (4, 0.09, 5), (5, 0.05, 7)):
            s += amp * np.sin(2 * np.pi * f * h * tt + 0.3 * h) * np.exp(-tt * dec)
        return vol * env * s

    def bell(self, f, dur, vol):  # музыкальная шкатулка / челеста
        tt = self._tt(dur)
        env = np.exp(-tt * 2.4) * np.minimum(1, tt * 400)
        s = np.zeros_like(tt)
        for h, amp, dec in ((1, 1.0, 0), (2.0, 0.35, 2), (2.98, 0.2, 4), (4.05, 0.1, 7), (5.4, 0.05, 10)):
            s += amp * np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * dec)
        return vol * env * s

    def pad(self, f, dur, vol):  # тёплый пад
        tt = self._tt(dur)
        att = np.minimum(1, tt / 0.9)
        rel = np.minimum(1, np.maximum(0, (dur - tt) / 1.2))
        s = (np.sin(2 * np.pi * f * 0.997 * tt) + np.sin(2 * np.pi * f * 1.003 * tt) + 0.6 * np.sin(2 * np.pi * f * tt + 1)
             + 0.25 * np.sin(2 * np.pi * f * 2.0 * tt)) / 2.85
        trem = 1 + 0.06 * np.sin(2 * np.pi * 0.35 * tt)
        return vol * att * rel * trem * s

    def pluck(self, f, dur, vol):  # арфа / гитара
        tt = self._tt(dur)
        env = np.exp(-tt * 2.8) * np.minimum(1, tt * 900)
        s = np.zeros_like(tt)
        for h in range(1, 7):
            s += (1.0 / h) * np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (1.2 + 2.2 * h))
        return vol * env * s

    def surf(self, dur, vol):
        m = int(dur * self.sr)
        x = self.rng.uniform(-1, 1, m)
        x = gaussian_filter(x, 14)
        tt = np.arange(m) / self.sr
        lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.09 * tt + 1.0) * np.sin(2 * np.pi * 0.047 * tt)
        return vol * x / (np.abs(x).max() + 1e-9) * lfo

    def wind(self, dur, vol):
        m = int(dur * self.sr)
        x = self.rng.uniform(-1, 1, m)
        x = gaussian_filter(x, 30)
        tt = np.arange(m) / self.sr
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * tt) * np.sin(2 * np.pi * 0.071 * tt + 2)
        return vol * x / (np.abs(x).max() + 1e-9) * lfo


MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
PENTA = [0, 2, 4, 7, 9]


def make_music(style, total, seed, line_times):
    """Своя мелодия под стиль: аккорды + сгенерированная мелодия + фон."""
    mu = Music(total, seed)
    r = mu.r
    styles = {
        "piano_dawn": dict(base=261.63, scale=MAJOR, prog=[[0, 2, 4], [5, 0, 2], [3, 5, 0], [4, 6, 1]], beat=0.85, lead="piano", bed="piano", bg=None),
        "musicbox": dict(base=220.0, scale=MINOR, prog=[[0, 2, 4], [5, 0, 2], [3, 5, 0], [4, 6, 1]], beat=0.62, lead="bell", bed="bell", bg="wind"),
        "night_pad": dict(base=146.83, scale=MINOR, prog=[[0, 2, 4], [5, 0, 2], [2, 4, 6], [3, 5, 0]], beat=1.0, lead="piano", bed="pad", bg=None),
        "harp_walk": dict(base=196.0, scale=MAJOR, prog=[[0, 2, 4], [3, 5, 0], [4, 6, 1], [0, 2, 4]], beat=0.55, lead="pluck", bed="pluck", bg=None),
        "piano_sea": dict(base=174.61, scale=MAJOR, prog=[[0, 2, 4], [5, 0, 2], [1, 3, 5], [4, 6, 1]], beat=0.72, lead="piano", bed="piano", bg="surf"),
    }
    st = styles[style]
    base, scale, prog, beat = st["base"], st["scale"], st["prog"], st["beat"]
    voice = {"piano": mu.piano, "bell": mu.bell, "pad": mu.pad, "pluck": mu.pluck}

    def freq(deg, octave=0):
        return base * 2 ** ((scale[deg % 7] + 12 * (deg // 7) + 12 * octave) / 12)

    bed = voice[st["bed"]]
    lead = voice[st["lead"]]
    bar = beat * 4
    t = 0.5
    ci = 0
    while t < total - 1.5:
        ch = prog[ci % len(prog)]
        if st["bed"] == "pad":
            for j, d in enumerate(ch):
                mu.put(bed(freq(d, -1 if j == 0 else 0), bar + 1.0, 0.07 if j else 0.09), t)
        elif st["bed"] == "bell":
            for j in range(4):
                d = ch[[0, 2, 1, 2][j]]
                mu.put(bed(freq(d, 0), 1.6, 0.05 if j else 0.07), t + j * beat)
        else:
            order = [0, 1, 2, 1, 0, 1, 2, 1] if st["bed"] == "pluck" else [0, 1, 2, 1]
            step = bar / len(order)
            for j, k in enumerate(order):
                mu.put(bed(freq(ch[k], -1 if k == 0 and j == 0 else 0), 2.4, 0.08 if j == 0 else 0.055), t + j * step)
        t += bar
        ci += 1
    # мелодия — случайное блуждание по гамме, рифмуется с аккордами
    deg = 7 + r.choice([0, 2, 4])
    t = 0.5 + bar
    rhythm = {"piano_dawn": [2, 1, 1, 2, 2], "musicbox": [1, 1, 2, 1, 1, 2], "night_pad": [3, 1, 2, 2], "harp_walk": [1, 1, 1, 1, 2, 2],
              "piano_sea": [2, 1, 1, 2, 2]}[style]
    ri = 0
    while t < total - 2.5:
        n_beats = rhythm[ri % len(rhythm)]
        ri += 1
        chord = prog[int((t - 0.5) // bar) % len(prog)]
        chord_tones = [c % 7 for c in chord]
        if r.random() < 0.55:
            deg += r.choice([-2, -1, 1, 2])
        else:
            cand = [d for d in range(7, 16) if d % 7 in chord_tones]
            deg = min(cand, key=lambda d: abs(d - deg) + r.random() * 2)
        deg = max(5, min(16, deg))
        if r.random() > 0.18:
            mu.put(lead(freq(deg), n_beats * beat * 1.6 + 0.6, 0.075 if st["lead"] != "pluck" else 0.09), t)
        t += n_beats * beat
    # колокольчик на появление строк
    for tl in line_times:
        mu.put(mu.bell(freq(14 + r.choice([0, 2, 4])), 2.0, 0.035), tl + 0.1)
    if st["bg"] == "surf":
        mu.put(mu.surf(total + 1, 0.06), 0)
    elif st["bg"] == "wind":
        mu.put(mu.wind(total + 1, 0.035), 0)
    a = mu.a[:int((total + 0.5) * mu.sr)]
    fade = int(1.8 * mu.sr)
    a[-fade:] *= np.linspace(1, 0, fade)
    a[:int(0.3 * mu.sr)] *= np.linspace(0, 1, int(0.3 * mu.sr))
    return a


# ---------------------------------------------------------------- рендер ролика
def render_quote(cfg, out_path, preview=None, log=print):
    t_start = time.time()
    seed = cfg.get("seed", 0)
    ru, en = cfg["ru"], cfg["en"]
    f_mark = font(F_MARK, 30, 600)
    f_ru, ru_size = fit_font(F_RU, ru, 66)
    f_en, en_size = fit_font(F_EN, en, 56, min_size=46, wght=500)
    f_auth = font(F_SMALL, 31)
    S_MARK = text_sprite(cfg.get("mark", "ЖИВЫЕ СТРОКИ  ·  LIVING LINES"), f_mark, (120, 104, 92, 255), spacing=5)
    S_RU = [text_sprite(s, f_ru, (48, 40, 36, 255)) for s in ru]
    S_EN = [text_sprite(s, f_en, (104, 90, 80, 255)) for s in en]
    S_A1 = text_sprite(cfg["author_ru"], f_auth, (122, 108, 98, 255))
    S_A2 = text_sprite(cfg["author_en"], f_auth, (140, 126, 116, 255))
    DIV = Image.new("RGBA", (140, 3), (170, 140, 90, 200))
    # раскладка
    y = 290
    Y_RU = [y + i * int(ru_size * 1.42) for i in range(len(ru))]
    y_div = Y_RU[-1] + int(ru_size * 1.42) + 8
    Y_EN = [y_div + 34 + i * int(en_size * 1.24) for i in range(len(en))]
    y_auth = Y_EN[-1] + int(en_size * 1.24) + 34
    py0 = y_auth + 112
    px0, px1, py1 = 95, 985, 1760
    scene_fn, hor_frac = SCENES[cfg["scene"]]
    hor = int(py0 + hor_frac * (py1 - py0))
    ops, paint_end, particles = scene_fn((px0, px1, py0, py1), hor, seed=seed)
    # тайминг текста
    T_RU = [2.4 + 1.1 * i for i in range(len(ru))]
    T_EN = [T_RU[-1] + 1.5 + 0.35 * i for i in range(len(en))]
    T_AUTHOR = T_EN[-1] + 1.5
    TOTAL = max(19.0, T_AUTHOR + 7.5, paint_end + 5.5)
    T_END = TOTAL - 1.6
    log(f"{cfg['scene']}: {TOTAL:.1f} с, строк {len(ru)}+{len(en)}, шрифт {ru_size}/{en_size}, картина {py0}-{py1}, горизонт {hor}")
    # частицы
    rnd = random.Random(3 + seed)
    if particles == "snow":
        parts = [(rnd.uniform(px0, px1), rnd.uniform(py0, py1), rnd.uniform(1.8, 3.6), rnd.uniform(0, 6.28), rnd.uniform(22, 48)) for _ in range(70)]
        pcol, prange = (255, 255, 255, 200), (py0, py1)
    elif particles == "fireflies":
        parts = [(rnd.uniform(px0, px1), rnd.uniform(py0 + 60, py1), rnd.uniform(2, 4), rnd.uniform(0, 6.28), rnd.uniform(4, 10)) for _ in range(22)]
        pcol, prange = (255, 230, 150, 170), (py0, py1)
    elif particles == "motes":
        parts = [(rnd.uniform(60, 1020), rnd.uniform(500, 1700), rnd.uniform(3, 7), rnd.uniform(0, 6.28), rnd.uniform(6, 14)) for _ in range(26)]
        pcol, prange = (255, 215, 140, 150), (500, 1700)
    else:
        parts, pcol, prange = [], None, (0, 1)
    spr_cache = {}

    def psprite(sz):
        k = int(sz * 2)
        if k not in spr_cache:
            S = int(sz * 4) + 4
            im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse([S / 2 - sz, S / 2 - sz, S / 2 + sz, S / 2 + sz], fill=pcol)
            spr_cache[k] = im.filter(ImageFilter.GaussianBlur(max(0.6, sz * 0.5)))
        return spr_cache[k]

    base = PAPER.copy()
    WET = np.full((H, W), -100.0, np.float32)
    writer = None if preview else fv.Writer(out_path, fps=FPS)
    grain = fv.GrainPool(sigma=1.5)
    done = [False] * len(ops)
    nfr = int(TOTAL * FPS)
    preview_idx = {int(v * FPS) for v in preview} if preview else None
    previews = {}
    for i in range(nfr):
        t = i / FPS
        canvas = base.copy()
        for k, op in enumerate(ops):
            if done[k] or t < op.t0:
                continue
            A = op.alpha(t)
            col = op.colour(t) if isinstance(op, Dots) and op.multi else op.col
            x0, y0, x1, y1 = op.box
            if t >= op.t1 + 0.05:
                apply(base, A, col, op.box, op.kind)
                done[k] = True
            ap = apply(canvas, A, col, op.box, op.kind)
            WET[y0:y1, x0:x1] = np.where(ap > 0.06, t, WET[y0:y1, x0:x1])
        if preview_idx is not None and i not in preview_idx:
            continue
        wet = np.exp(-np.clip(t - WET, 0, None) / 1.8)
        disp = canvas * (1 - 0.07 * wet[..., None])
        disp += (1 - disp) * (0.13 * wet * SPEC)[..., None]
        disp *= FACT
        img = Image.fromarray((np.clip(disp, 0, 1) * 255).astype(np.uint8))
        for (mx_, my_, sz, ph, sp) in parts:
            if particles == "snow":
                px = mx_ + 22 * math.sin(t * 0.7 + ph)
                py = prange[0] + (my_ + sp * t - prange[0]) % (prange[1] - prange[0])
                a = 0.75
                if not (px0 < px < px1):
                    continue
            else:
                px = mx_ + 18 * math.sin(t * 0.5 + ph)
                py = prange[0] + (my_ - sp * t + 10 * math.sin(t * 0.8 + ph * 2) - prange[0]) % (prange[1] - prange[0])
                a = (0.5 + 0.5 * math.sin(t * 1.3 + ph * 3)) * (0.6 if particles == "motes" else 0.9)
            if t > 1.0:
                paste_fade(img, psprite(sz), px, py, a * min(1, (t - 1.0) / 2))
        fade_all = 1.0 if t < T_END else max(0.0, 1 - (t - T_END) / 1.2)
        paste_fade(img, S_MARK, (W - S_MARK.size[0]) / 2, 140, ease(0.5, 1.0, t) * fade_all)
        for spr, t0, yv in zip(S_RU, T_RU, Y_RU):
            a = ease(t0, 0.9, t)
            paste_fade(img, spr, (W - spr.size[0]) / 2, yv + 14 * (1 - a), a * fade_all)
        paste_fade(img, DIV, (W - DIV.size[0]) / 2, y_div, ease(T_EN[0] - 0.3, 0.8, t) * fade_all)
        for spr, t0, yv in zip(S_EN, T_EN, Y_EN):
            a = ease(t0, 0.9, t)
            paste_fade(img, spr, (W - spr.size[0]) / 2, yv + 12 * (1 - a), a * fade_all)
        a = ease(T_AUTHOR, 1.0, t)
        paste_fade(img, S_A1, (W - S_A1.size[0]) / 2, y_auth, a * fade_all)
        paste_fade(img, S_A2, (W - S_A2.size[0]) / 2, y_auth + 44, a * fade_all)
        z = 1.0 + 0.05 * (t / TOTAL)
        x0, y0, cw, ch = fv.camera_window(W / 2, H / 2, z)
        img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)
        frame = grain.apply(img, i)
        if t > T_END + 0.4:
            k_ = min(1.0, (t - T_END - 0.4) / 1.2)
            frame = (frame * (1 - 0.6 * k_) + np.array([246, 243, 236]) * 0.6 * k_).astype(np.uint8)
        if preview_idx is not None:
            previews[i] = Image.fromarray(frame)
        else:
            writer.add(frame)
    if preview_idx is not None:
        return previews
    audio = make_music(cfg["music"], TOTAL, seed + 100, T_RU + [T_EN[0], T_AUTHOR])
    writer.close(audio, peak=0.7)
    log(f"готово {out_path}: {time.time() - t_start:.0f} с")
    return TOTAL


# ================================================================ ДОПОЛНИТЕЛЬНЫЕ СЦЕНЫ
def sky(ops, t0, box, hor, cols, dens=0.6, seed=0, dur=2.2, rough=0.18):
    px0, px1, py0, py1 = box
    ops.append(Wash(t0, dur, [(px0, py0), (px1, py0), (px1, hor + 6), (px0, hor + 6)], cols, dens=dens, blur=4,
                    rough=rough, seed=seed))


def water(ops, t0, box, hor, cols, dens=0.6, seed=0, streak=0.3, dur=1.6, edge=0.3):
    px0, px1, py0, py1 = box
    ops.append(Wash(t0, dur, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], cols, dens=dens, blur=4, rough=0.18,
                    seed=seed, streak=streak, edge=edge))


def hills(ops, t0, box, hor, ry, mx, cols, dens=0.6, seed=0, blur=2.5, dur=1.3, edge=0.3):
    px0, px1, py0, py1 = box
    ops.append(Wash(t0, dur, list(zip(mx, ry)) + [(px1 + 10, hor), (px0 - 10, hor)], cols, dens=dens, blur=blur,
                    rough=0.12, direction="right", seed=seed, edge=edge))


def reflection(ops, t0, box, hor, ry, mx, col, dens=0.3, seed=0):
    px0, px1, py0, py1 = box
    ops.append(Wash(t0, 1.0, [(x, 2 * hor - y) for x, y in zip(mx, ry)] + [(px1 + 10, hor + 3), (px0 - 10, hor + 3)],
                    [col], dens=dens, blur=6, rough=0.2, direction="right", seed=seed, streak=0.5, edge=0.05))


def sun(ops, t0, x, y, r=38, halo=100, col=(1.0, 1.0, 0.97), hcol=(1.0, 0.98, 0.90), seed=0):
    ops.append(Bloom(t0, x, y, halo, hcol, dens=0.9, dur=1.2, seed=80 + seed, kind="over", soft=4.0))
    ops.append(Bloom(t0 + 0.5, x, y, r, col, dens=1.0, dur=0.8, seed=81 + seed, kind="over", soft=1.2))


def stars(ops, t0, box, hor, n=70, seed=0, frac=0.62):
    px0, px1, py0, py1 = box
    r = random.Random(13 + seed)
    pts = [(r.uniform(px0 + 15, px1 - 15), r.uniform(py0 + 12, py0 + (hor - py0) * frac),
            r.choice([1.3, 1.6, 2.0, 2.4, 3.0]), (1.0, 0.98, 0.92), r.random()) for _ in range(n)]
    ops.append(Dots(t0, 1.6, pts, blur=0.7))


def round_tree(ops, t0, x, base, h, cols, seed=0, trunk=(0.32, 0.26, 0.24), spread=1.0):
    R0 = h * 0.44
    blobs = [(0, -h * 0.92, R0), (-R0 * 0.8 * spread, -h * 0.74, R0 * 0.8), (R0 * 0.8 * spread, -h * 0.76, R0 * 0.82), (R0 * 0.15, -h * 0.58, R0 * 0.72), (-R0 * 0.3, -h * 1.05, R0 * 0.6)]
    for j, (dx, dy, R_) in enumerate(blobs):
        ops.append(Bloom(t0 + j * 0.12, x + dx, base + dy, R_, cols[j % len(cols)], dens=0.74, dur=1.0, seed=seed + 7 * j + 1, soft=1.2))
    # ствол — после кроны и только под ней
    ops.append(Stroke(t0 + 0.9, 0.4, [(x, base), (x + 2, base - h * 0.3), (x + 4, base - h * 0.5)], [max(6, h * 0.08), max(5, h * 0.065), max(3, h * 0.04)],
                      trunk, dens=0.9, blur=0.8, seed=seed))
    return t0 + 1.3


def spruce_row(ops, t0, box, base_y, col, hmin=40, hmax=120, step=16, seed=0, dens=0.7, dur=1.4):
    px0, px1, py0, py1 = box
    r = random.Random(seed)
    xs = np.arange(px0 - 10, px1 + 12, step)
    pts = []
    for x in xs:
        hgt = hmin + (hmax - hmin) * abs(math.sin(x / 150 + r.random())) + r.uniform(-8, 10)
        pts.append((x, base_y - hgt))
        pts.append((x + step / 2, base_y - hgt * 0.42))
    ops.append(Wash(t0, dur, pts + [(px1 + 12, base_y + 2), (px0 - 10, base_y + 2)], [col], dens=dens, blur=1.3, rough=0.08,
                    direction="right", seed=seed, edge=0.3))


def spruce(ops, t0, x, base, h, col, seed=0):
    pts = []
    n = 7
    for k in range(n):
        f = k / (n - 1)
        hw = 4 + h * 0.28 * f
        yv = base - h + f * (h - 6)
        pts += [(x - hw, yv + 8 * f), (x, yv - 6)]
    pts += [(x + 4 + h * 0.28, base + 2)]
    left = pts[::-1]
    poly = [(x, base - h)] + [(x + (xx_ - x) * -1, yy_) for xx_, yy_ in reversed(pts)][::-1]
    poly = [(x, base - h)]
    for k in range(n):
        f = k / (n - 1)
        hw = 4 + h * 0.28 * f
        yv = base - h + f * (h - 6)
        poly += [(x + hw, yv + 8 * f), (x + 2, yv + 2)] if k < n - 1 else [(x + hw, base)]
    for k in reversed(range(n)):
        f = k / (n - 1)
        hw = 4 + h * 0.28 * f
        yv = base - h + f * (h - 6)
        poly += [(x - hw, base)] if k == n - 1 else [(x - 2, yv + 2), (x - hw, yv + 8 * f)]
    ops.append(Wash(t0, 0.5, poly, [col], dens=0.85, blur=1.0, rough=0.06, direction="down", seed=seed, edge=0.25))


def cloud(ops, t0, x, y, R, box, hor, seed=0, shadow=True):
    px0, px1, py0, py1 = box
    if shadow:
        ops.append(Bloom(t0, x + 20, y + 30, R * 1.1, (0.72, 0.76, 0.86), dens=0.14, dur=1.3, seed=48 + seed, soft=2.5).clip_to(px0, py0, px1, hor))
    ops.append(Bloom(t0 + 0.1, x, y, R, (0.99, 0.99, 0.98), dens=0.75, dur=1.4, seed=58 + seed, kind="over", soft=2.2).clip_to(px0, py0, px1, hor))


def scene_autumn(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.80, 0.84, 0.90), (0.94, 0.90, 0.82), (0.99, 0.92, 0.72)], dens=0.5, seed=101 + seed)
    ops.append(Wash(t0 + 2.0, 1.6, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.90, 0.78, 0.50), (0.82, 0.60, 0.34), (0.70, 0.46, 0.28)],
                    dens=0.55, blur=4, rough=0.2, seed=102, streak=0.15, edge=0.25))
    left, right = [], []
    for k in np.linspace(0, 1, 20):
        yv = py1 + 10 - k * (py1 + 10 - hor - 4)
        cx_ = px0 + 445 + 30 * math.sin(k * 2.5)
        hw = 4 + 190 * (1 - k) ** 1.8
        left.append((cx_ - hw, yv)); right.append((cx_ + hw, yv))
    ops.append(Wash(t0 + 3.4, 1.5, left + right[::-1], [(0.96, 0.90, 0.74)], dens=0.85, blur=2.5, rough=0.2, direction="up", seed=103, kind="over", edge=0.0))
    r = random.Random(5 + seed)
    t = t0 + 4.6
    cols_l = [(0.95, 0.56, 0.22), (0.98, 0.72, 0.26), (0.88, 0.40, 0.20), (0.96, 0.64, 0.24)]
    for j in range(5):
        f = j / 4
        d = (1 - f) ** 1.4
        h = 60 + 300 * d
        for side in (-1, 1):
            x = px0 + 445 + side * (60 + 330 * d) + r.uniform(-15, 15)
            base = hor + 6 + (py1 - hor - 40) * d
            round_tree(ops, t, x, base, h, [cols_l[(j + (side > 0)) % 4], cols_l[(j + 2) % 4], cols_l[(j + 1) % 4]], seed=110 + j * 2 + (side > 0), spread=1.1)
            t += 0.25
    for j in range(40):
        yv = hor + 40 + r.random() ** 0.7 * (py1 - hor - 50)
        x = r.uniform(px0 + 10, px1 - 10)
        s_ = 2 + 4 * (yv - hor) / (py1 - hor)
        ops.append(Stroke(t + j * 0.03, 0.2, [(x - s_, yv), (x + s_, yv - 1)], [s_ * 1.4], r.choice(cols_l), dens=0.7, blur=0.8, seed=130 + j))
    end = birds(ops, t + 1.5, [(px0 + 180, py0 + 110, 12), (px0 + 240, py0 + 150, 10), (px0 + 760, py0 + 130, 11)])
    return ops, end, "leaves"


def scene_sakura(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.80, 0.86, 0.94), (0.92, 0.90, 0.94), (0.98, 0.90, 0.90)], dens=0.5, seed=141 + seed)
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    far = ridge(mx, hor - 60, 60, 220, 70, 0.6 + seed)
    hills(ops, t0 + 1.8, box, hor, far, mx, [(0.74, 0.80, 0.84), (0.66, 0.76, 0.78)], dens=0.4, seed=142, blur=4)
    water(ops, t0 + 2.8, box, hor, [(0.86, 0.84, 0.90), (0.70, 0.80, 0.88), (0.60, 0.74, 0.84)], dens=0.5, seed=143, streak=0.3)
    reflection(ops, t0 + 3.8, box, hor, far, mx, (0.70, 0.76, 0.82), dens=0.22, seed=144)
    # большое дерево сакуры справа, склоняется над водой
    tx, tb = px0 + 720, hor + 30
    ops.append(Stroke(t0 + 4.4, 0.7, [(tx, tb), (tx - 10, tb - 90), (tx - 60, tb - 170), (tx - 120, tb - 230)], [16, 12, 8, 5], (0.34, 0.26, 0.26), dens=0.92, blur=0.8, seed=145))
    ops.append(Stroke(t0 + 4.9, 0.5, [(tx - 60, tb - 170), (tx - 20, tb - 250), (tx + 20, tb - 300)], [7, 5, 3], (0.34, 0.26, 0.26), dens=0.9, blur=0.7, seed=146))
    ops.append(Stroke(t0 + 5.1, 0.5, [(tx - 120, tb - 230), (tx - 200, tb - 270), (tx - 280, tb - 280)], [5, 4, 3], (0.34, 0.26, 0.26), dens=0.9, blur=0.7, seed=147))
    pinks = [(0.97, 0.76, 0.84), (0.99, 0.84, 0.90), (0.95, 0.68, 0.78), (0.98, 0.80, 0.86)]
    for j, (dx, dy, R_) in enumerate(((-120, -310, 130), (-10, -330, 115), (50, -270, 95), (-240, -300, 110), (-310, -270, 85), (-170, -240, 100), (-50, -210, 85), (-120, -380, 90), (-230, -360, 80))):
        ops.append(Bloom(t0 + 5.4 + j * 0.12, tx + dx, tb + dy, R_, pinks[j % 4], dens=0.66, dur=1.1, seed=150 + j, soft=1.3))
    r = random.Random(9 + seed)
    for j in range(16):
        yv = hor + 10 + j * 14
        if yv > py1 - 10:
            break
        x = tx - 120 + r.uniform(-120, 120)
        ln = r.uniform(10, 40)
        ops.append(Stroke(t0 + 6.8 + j * 0.05, 0.25, [(x - ln, yv), (x + ln, yv)], [4], (0.97, 0.80, 0.86), dens=0.4, blur=1.2, seed=170 + j))
    # лепестки на воде
    petals = [(r.uniform(px0 + 10, px1 - 10), r.uniform(hor + 20, py1 - 10), r.uniform(1.5, 3.2), (0.98, 0.84, 0.90), r.random()) for _ in range(60)]
    ops.append(Dots(t0 + 7.4, 1.2, petals, blur=0.8))
    end = birds(ops, t0 + 8.0, [(px0 + 200, py0 + 120, 11), (px0 + 260, py0 + 160, 9)])
    return ops, end, "petals"


def scene_lavender(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.66, 0.62, 0.84), (0.90, 0.72, 0.76), (0.99, 0.84, 0.60)], dens=0.6, seed=181 + seed)
    sun(ops, t0 + 1.6, px0 + 520, hor - 70, r=42, halo=130, col=(1.0, 0.97, 0.85), hcol=(1.0, 0.92, 0.72), seed=seed)
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    far = ridge(mx, hor - 40, 45, 260, 80, 1.1 + seed)
    hills(ops, t0 + 2.4, box, hor, far, mx, [(0.60, 0.54, 0.74)], dens=0.5, seed=182, blur=4)
    ops.append(Wash(t0 + 3.4, 1.6, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.70, 0.60, 0.84), (0.56, 0.44, 0.76), (0.46, 0.34, 0.68)],
                    dens=0.6, blur=4, rough=0.18, seed=183, streak=0.2, edge=0.25))
    # ряды лаванды, сходящиеся к горизонту
    vx = px0 + 445
    for j in range(9):
        f = (j - 4) / 4
        xb = vx + f * 620
        xt = vx + f * 40
        pts = [(xt + (xb - xt) * k, hor + 10 + (py1 - hor - 14) * k ** 1.3) for k in np.linspace(0.05, 1, 10)]
        wd = [3 + 34 * k ** 1.3 for k in np.linspace(0.05, 1, 10)]
        ops.append(Stroke(t0 + 4.8 + j * 0.16, 0.7, pts, wd, (0.42, 0.30, 0.66), dens=0.55, blur=3, seed=190 + j))
        pts2 = [(x + 6, y - 6) for x, y in pts]
        ops.append(Stroke(t0 + 5.0 + j * 0.16, 0.7, pts2, [w * 0.5 for w in wd], (0.76, 0.62, 0.90), dens=0.4, blur=2, seed=200 + j))
    r = random.Random(11 + seed)
    dots = [(r.uniform(px0 + 10, px1 - 10), hor + 80 + r.random() ** 0.8 * (py1 - hor - 90), r.uniform(1.5, 4), (0.82, 0.70, 0.94), r.random()) for _ in range(90)]
    ops.append(Dots(t0 + 6.6, 1.4, dots, blur=0.9))
    end = birds(ops, t0 + 7.6, [(px0 + 180, py0 + 120, 12), (px0 + 230, py0 + 160, 10), (px0 + 760, py0 + 100, 10)])
    return ops, end, "motes"


def scene_alpine(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.52, 0.68, 0.90), (0.72, 0.82, 0.93), (0.90, 0.92, 0.94)], dens=0.6, seed=221 + seed)
    cloud(ops, t0 + 1.4, px0 + 220, py0 + 90, 70, box, hor, seed=1, shadow=False)
    cloud(ops, t0 + 1.7, px0 + 640, py0 + 140, 55, box, hor, seed=2, shadow=False)
    mx = np.linspace(px0 - 10, px1 + 10, 100)
    peaks = hor - 150 - 170 * np.abs(np.sin(mx / 120 + 0.7)) - 50 * np.abs(np.sin(mx / 37 + 1)) - 20 * np.cos(mx / 15)
    hills(ops, t0 + 2.4, box, hor, peaks, mx, [(0.56, 0.60, 0.76), (0.44, 0.48, 0.66)], dens=0.7, seed=222, blur=1.8, edge=0.35)
    # снег на вершинах
    snowcap = [(x, y) for x, y in zip(mx, peaks)] + [(x, y + 55 + 25 * math.sin(x / 23)) for x, y in zip(mx[::-1], peaks[::-1])]
    ops.append(Wash(t0 + 3.5, 1.0, snowcap, [(0.98, 0.98, 0.99)], dens=0.9, blur=1.5, rough=0.3, direction="right", seed=223, kind="over", edge=0.0))
    near = ridge(mx, hor - 40, 60, 90, 31, 2.0 + seed, amp2=0.35)
    hills(ops, t0 + 4.3, box, hor, near, mx, [(0.30, 0.46, 0.40), (0.22, 0.38, 0.34)], dens=0.8, seed=224, blur=1.6, edge=0.3)
    spruce_row(ops, t0 + 5.0, box, hor + 2, (0.16, 0.30, 0.26), hmin=25, hmax=75, step=14, seed=225, dens=0.85)
    water(ops, t0 + 5.8, box, hor, [(0.52, 0.76, 0.80), (0.36, 0.66, 0.74), (0.26, 0.54, 0.66)], dens=0.75, seed=226, streak=0.35)
    reflection(ops, t0 + 6.9, box, hor, near, mx, (0.20, 0.36, 0.34), dens=0.4, seed=227)
    reflection(ops, t0 + 7.3, box, hor, peaks, mx, (0.50, 0.56, 0.72), dens=0.22, seed=228)
    r = random.Random(7 + seed)
    for j in range(10):
        yv = hor + 60 + r.random() * (py1 - hor - 80)
        ln = 20 + (yv - hor) / (py1 - hor) * 60
        x = r.uniform(px0 + 30 + ln, px1 - 30 - ln)
        ops.append(Stroke(t0 + 8.0 + j * 0.06, 0.3, [(x - ln, yv), (x + ln, yv)], [3], (0.94, 0.98, 0.98), dens=0.55, blur=1, kind="over", seed=230 + j))
    end = birds(ops, t0 + 8.7, [(px0 + 300, py0 + 110, 12), (px0 + 360, py0 + 150, 10)])
    return ops, end, "motes"


def scene_lighthouse(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.46, 0.44, 0.66), (0.86, 0.62, 0.62), (0.99, 0.84, 0.62)], dens=0.65, seed=241 + seed)
    sun(ops, t0 + 1.5, px0 + 250, hor - 60, r=34, halo=110, col=(1.0, 0.96, 0.84), hcol=(1.0, 0.88, 0.66), seed=seed)
    water(ops, t0 + 2.4, box, hor, [(0.94, 0.76, 0.62), (0.56, 0.58, 0.78), (0.30, 0.40, 0.64)], dens=0.75, seed=242, streak=0.35)
    r = random.Random(3 + seed)
    for j in range(16):
        yv = hor + 30 + r.random() ** 0.8 * (py1 - hor - 50)
        ln = 14 + (yv - hor) / (py1 - hor) * 60
        x = r.uniform(px0 + 20 + ln, px1 - 300)
        ops.append(Stroke(t0 + 3.8 + j * 0.06, 0.3, [(x - ln, yv), (x + ln, yv)], [3 if yv < hor + 150 else 5], (0.98, 0.94, 0.90), dens=r.uniform(0.4, 0.75), blur=0.9, kind="over", seed=250 + j))
    # скала справа
    rock = [(px0 + 560, py1 + 10), (px0 + 600, hor + 120), (px0 + 660, hor + 40), (px0 + 720, hor - 10), (px0 + 800, hor - 30), (px0 + 880, hor - 20), (px1 + 10, hor + 30), (px1 + 10, py1 + 10)]
    ops.append(Wash(t0 + 4.9, 1.2, rock, [(0.36, 0.32, 0.42), (0.22, 0.20, 0.30)], dens=0.9, blur=1.8, rough=0.14, direction="right", seed=243, edge=0.3))
    ops.append(Stroke(t0 + 5.8, 0.6, [(px0 + 600, hor + 125), (px0 + 680, hor + 50)], [10], (0.98, 0.94, 0.92), dens=0.45, blur=4, kind="over", seed=244))
    # маяк
    lx, lb, lh = px0 + 790, hor - 22, 190
    ops.append(Wash(t0 + 6.2, 0.7, [(lx - 26, lb), (lx + 26, lb), (lx + 18, lb - lh), (lx - 18, lb - lh)], [(0.98, 0.96, 0.94)], dens=0.95, blur=1.0, rough=0.04, direction="up", seed=245, kind="over", edge=0.0))
    for j, yb in enumerate((lb - lh * 0.28, lb - lh * 0.62)):
        ops.append(Wash(t0 + 6.8 + j * 0.2, 0.4, [(lx - 25 + 7 * (lb - yb) / lh, yb), (lx + 25 - 7 * (lb - yb) / lh, yb), (lx + 25 - 7 * (lb - yb + 26) / lh, yb - 26), (lx - 25 + 7 * (lb - yb + 26) / lh, yb - 26)],
                        [(0.86, 0.28, 0.24)], dens=0.95, blur=0.8, rough=0.04, direction="right", seed=246 + j, kind="over", edge=0.0))
    ops.append(Wash(t0 + 7.2, 0.4, [(lx - 24, lb - lh), (lx + 24, lb - lh), (lx + 20, lb - lh - 34), (lx - 20, lb - lh - 34)], [(0.26, 0.24, 0.32)], dens=0.95, blur=0.8, rough=0.04, direction="up", seed=248, edge=0.0))
    ops.append(Wash(t0 + 7.4, 0.3, [(lx - 24, lb - lh - 34), (lx + 24, lb - lh - 34), (lx, lb - lh - 56)], [(0.26, 0.24, 0.32)], dens=0.95, blur=0.8, rough=0.04, direction="up", seed=249, edge=0.0))
    ops.append(Bloom(t0 + 7.6, lx, lb - lh - 17, 48, (1.0, 0.96, 0.70), dens=0.75, dur=0.9, seed=251, kind="over", soft=3.5))
    ops.append(Bloom(t0 + 7.8, lx, lb - lh - 17, 12, (1.0, 1.0, 0.90), dens=1.0, dur=0.5, seed=252, kind="over", soft=1.0))
    end = birds(ops, t0 + 8.3, [(px0 + 150, py0 + 150, 13), (px0 + 215, py0 + 190, 11), (px0 + 420, py0 + 120, 10)])
    return ops, end, "none"


def scene_balloons(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.60, 0.74, 0.92), (0.84, 0.88, 0.94), (0.99, 0.90, 0.76)], dens=0.55, seed=261 + seed)
    cloud(ops, t0 + 1.4, px0 + 160, py0 + 110, 60, box, hor, seed=3, shadow=False)
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    far = ridge(mx, hor - 50, 50, 230, 70, 0.3 + seed)
    hills(ops, t0 + 2.2, box, hor, far, mx, [(0.66, 0.76, 0.70), (0.58, 0.72, 0.62)], dens=0.45, seed=262, blur=4)
    ops.append(Wash(t0 + 3.2, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.80, 0.84, 0.54), (0.62, 0.76, 0.42), (0.50, 0.68, 0.36)],
                    dens=0.6, blur=4, rough=0.18, seed=263, streak=0.2, edge=0.25))
    for j in range(5):
        yv = hor + 60 + j * 60
        if yv < py1 - 20:
            ops.append(Stroke(t0 + 4.4 + j * 0.1, 0.5, [(px0 + 20, yv + 10 * math.sin(j)), (px1 - 20, yv - 8)], [8], (0.46, 0.62, 0.36), dens=0.25, blur=4, seed=264 + j))
    cols = [((0.92, 0.36, 0.30), (0.98, 0.80, 0.30)), ((0.30, 0.52, 0.86), (0.96, 0.96, 0.96)), ((0.95, 0.60, 0.24), (0.90, 0.30, 0.40)), ((0.46, 0.72, 0.46), (0.98, 0.90, 0.40))]
    places = [(px0 + 300, py0 + 190, 62), (px0 + 620, py0 + 120, 46), (px0 + 760, py0 + 300, 34), (px0 + 160, py0 + 330, 28)]
    t = t0 + 5.0
    for j, ((x, y, R_), (c1, c2)) in enumerate(zip(places, cols)):
        ops.append(Wash(t, 0.7, [(x - R_, y), (x - R_ * 0.9, y - R_ * 0.6), (x, y - R_ * 1.15), (x + R_ * 0.9, y - R_ * 0.6), (x + R_, y), (x + R_ * 0.55, y + R_ * 0.9), (x + R_ * 0.2, y + R_ * 1.25), (x - R_ * 0.2, y + R_ * 1.25), (x - R_ * 0.55, y + R_ * 0.9)],
                        [c1], dens=0.88, blur=1.5, rough=0.06, direction="down", seed=270 + j, edge=0.3))
        for k in (-0.5, 0.0, 0.5):
            ops.append(Stroke(t + 0.4, 0.4, [(x + k * R_ * 0.9, y - R_ * 0.95 + abs(k) * R_ * 0.3), (x + k * R_ * 0.55, y + R_ * 1.1)], [max(3, R_ * 0.12)], c2, dens=0.8, blur=0.8, kind="over", seed=280 + j))
        by = y + R_ * 1.25 + R_ * 0.55
        ops.append(Stroke(t + 0.7, 0.3, [(x - R_ * 0.2, y + R_ * 1.25), (x - R_ * 0.12, by)], [2], (0.36, 0.28, 0.22), dens=0.9, blur=0.5, seed=290 + j))
        ops.append(Stroke(t + 0.7, 0.3, [(x + R_ * 0.2, y + R_ * 1.25), (x + R_ * 0.12, by)], [2], (0.36, 0.28, 0.22), dens=0.9, blur=0.5, seed=295 + j))
        ops.append(Wash(t + 0.9, 0.3, [(x - R_ * 0.22, by), (x + R_ * 0.22, by), (x + R_ * 0.2, by + R_ * 0.28), (x - R_ * 0.2, by + R_ * 0.28)], [(0.46, 0.34, 0.24)], dens=0.95, blur=0.8, rough=0.04, direction="down", seed=300 + j, edge=0.0))
        t += 0.55
    end = birds(ops, t + 0.4, [(px0 + 480, py0 + 400, 9), (px0 + 520, py0 + 430, 8)])
    return ops, end, "motes"


def scene_cabin(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.14, 0.18, 0.38), (0.26, 0.28, 0.52), (0.52, 0.46, 0.64)], dens=0.88, seed=311 + seed, rough=0.14)
    stars(ops, t0 + 2.0, box, hor, n=60, seed=seed, frac=0.75)
    ops.append(Bloom(t0 + 2.6, px0 + 180, py0 + 120, 80, (0.95, 0.94, 0.86), dens=0.4, dur=1.2, seed=312, kind="over", soft=4.0))
    ops.append(Bloom(t0 + 2.9, px0 + 180, py0 + 120, 28, (1.0, 0.99, 0.92), dens=1.0, dur=0.7, seed=313, kind="over", soft=0.9))
    spruce_row(ops, t0 + 3.4, box, hor - 10, (0.12, 0.16, 0.30), hmin=50, hmax=150, step=15, seed=314, dens=0.9)
    # снег
    ops.append(Wash(t0 + 4.4, 1.3, [(px0, hor - 14), (px1, hor - 14), (px1, py1), (px0, py1)], [(0.78, 0.82, 0.94), (0.86, 0.88, 0.96), (0.80, 0.84, 0.94)],
                    dens=0.3, blur=4, rough=0.2, seed=315, streak=0.25, edge=0.1))
    # изба
    cx_, cb = px0 + 540, hor + 150
    wd, hh = 150, 100
    ops.append(Wash(t0 + 5.4, 0.8, [(cx_ - wd, cb), (cx_ + wd, cb), (cx_ + wd, cb - hh), (cx_ - wd, cb - hh)], [(0.30, 0.22, 0.20), (0.22, 0.16, 0.16)], dens=0.95, blur=1.2, rough=0.05, direction="up", seed=316, edge=0.2))
    for j in range(4):
        yl = cb - 15 - j * 24
        ops.append(Stroke(t0 + 5.9 + j * 0.05, 0.3, [(cx_ - wd, yl), (cx_ + wd, yl)], [3], (0.16, 0.12, 0.12), dens=0.6, blur=0.6, seed=320 + j))
    ops.append(Wash(t0 + 6.2, 0.6, [(cx_ - wd - 24, cb - hh + 6), (cx_, cb - hh - 95), (cx_ + wd + 24, cb - hh + 6)], [(0.36, 0.28, 0.30)], dens=0.95, blur=1.2, rough=0.05, direction="up", seed=324, edge=0.2))
    ops.append(Wash(t0 + 6.6, 0.6, [(cx_ - wd - 30, cb - hh + 2), (cx_, cb - hh - 104), (cx_ + wd + 30, cb - hh + 2), (cx_ + wd + 10, cb - hh + 8), (cx_, cb - hh - 72), (cx_ - wd - 10, cb - hh + 8)],
                    [(0.97, 0.97, 0.99)], dens=0.96, blur=1.5, rough=0.1, direction="right", seed=325, kind="over", edge=0.0))
    # окна тёплые
    for j, wx in enumerate((cx_ - 70, cx_ + 70)):
        ops.append(Wash(t0 + 7.2 + j * 0.2, 0.4, [(wx - 24, cb - 36), (wx + 24, cb - 36), (wx + 24, cb - 76), (wx - 24, cb - 76)], [(1.0, 0.86, 0.46)], dens=0.98, blur=0.8, rough=0.03, direction="down", seed=330 + j, kind="over", edge=0.0))
        ops.append(Bloom(t0 + 7.4 + j * 0.2, wx, cb - 56, 60, (1.0, 0.82, 0.40), dens=0.35, dur=0.8, seed=335 + j, kind="over", soft=4.0))
        ops.append(Stroke(t0 + 7.6 + j * 0.2, 0.2, [(wx, cb - 36), (wx, cb - 76)], [3], (0.30, 0.22, 0.20), dens=0.9, blur=0.4, seed=340 + j))
        ops.append(Stroke(t0 + 7.6 + j * 0.2, 0.2, [(wx - 24, cb - 56), (wx + 24, cb - 56)], [3], (0.30, 0.22, 0.20), dens=0.9, blur=0.4, seed=345 + j))
    # труба и дым
    ops.append(Wash(t0 + 7.9, 0.3, [(cx_ + 70, cb - hh - 40), (cx_ + 96, cb - hh - 40), (cx_ + 96, cb - hh - 80), (cx_ + 70, cb - hh - 80)], [(0.30, 0.22, 0.22)], dens=0.95, blur=0.8, rough=0.04, direction="up", seed=350, edge=0.0))
    for j in range(4):
        ops.append(Bloom(t0 + 8.2 + j * 0.25, cx_ + 90 + j * 22, cb - hh - 110 - j * 45, 22 + j * 12, (0.90, 0.88, 0.92), dens=0.45 - j * 0.08, dur=1.0, seed=355 + j, kind="over", soft=2.5))
    ops.append(Stroke(t0 + 8.4, 0.6, [(cx_ - 20, cb + 2), (cx_ + 10, py1 - 10)], [26, 60], (0.70, 0.74, 0.90), dens=0.3, blur=6, seed=360))
    return ops, t0 + 9.6, "snow"


def scene_aurora(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.08, 0.10, 0.26), (0.12, 0.16, 0.36), (0.18, 0.28, 0.44)], dens=0.92, seed=371 + seed, rough=0.14)
    stars(ops, t0 + 2.0, box, hor, n=80, seed=seed, frac=0.8)
    # ленты сияния
    r = random.Random(21 + seed)
    for j, (c, a) in enumerate((((0.30, 0.95, 0.66), 0.55), ((0.52, 0.92, 0.74), 0.4), ((0.62, 0.46, 0.92), 0.35), ((0.30, 0.86, 0.80), 0.3))):
        pts_top, pts_bot = [], []
        for k in np.linspace(0, 1, 12):
            x = px0 - 20 + k * (px1 - px0 + 40)
            y = py0 + 120 + j * 70 + 90 * math.sin(k * 3.2 + j + seed) + 30 * math.sin(k * 9 + j)
            pts_top.append((x, y))
            pts_bot.append((x + 20, y + 110 + 60 * math.sin(k * 5 + j)))
        ops.append(Wash(t0 + 2.4 + j * 0.5, 1.6, pts_top + pts_bot[::-1], [c], dens=a, blur=14, rough=0.35, direction="right", seed=372 + j, kind="over", edge=0.0))
    spruce_row(ops, t0 + 5.0, box, hor + 2, (0.06, 0.10, 0.20), hmin=50, hmax=160, step=15, seed=373, dens=0.95)
    water(ops, t0 + 6.0, box, hor, [(0.16, 0.30, 0.38), (0.10, 0.18, 0.30), (0.06, 0.10, 0.20)], dens=0.9, seed=374, streak=0.4)
    for j in range(10):
        yv = hor + 20 + j * 30
        if yv > py1 - 10:
            break
        x = px0 + 200 + r.uniform(-60, 60) + j * 30
        ln = r.uniform(40, 120)
        ops.append(Stroke(t0 + 7.2 + j * 0.08, 0.3, [(x - ln, yv), (x + ln, yv)], [3], (0.40, 0.90, 0.70), dens=0.35, blur=2, kind="over", seed=380 + j))
    return ops, t0 + 8.6, "none"


def scene_birch(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.86, 0.88, 0.90), (0.96, 0.92, 0.80), (0.99, 0.90, 0.66)], dens=0.5, seed=401 + seed)
    ops.append(Bloom(t0 + 1.2, px0 + 445, py0 + 120, 240, (0.99, 0.88, 0.56), dens=0.3, dur=1.6, seed=402, soft=2.0).clip_to(px0, py0, px1, hor))
    ops.append(Wash(t0 + 2.0, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.94, 0.84, 0.50), (0.88, 0.70, 0.36), (0.78, 0.58, 0.32)],
                    dens=0.55, blur=4, rough=0.2, seed=403, streak=0.15, edge=0.25))
    # дальняя листва — золотое марево
    for j in range(5):
        ops.append(Bloom(t0 + 3.0 + j * 0.2, px0 + 90 + j * 200, hor - 80, 120, (0.98, 0.82, 0.40), dens=0.4, dur=1.2, seed=410 + j, soft=1.8).clip_to(px0, py0, px1, hor + 10))
    r = random.Random(31 + seed)
    t = t0 + 4.2
    for j, (fx, fd) in enumerate(((0.12, 1.0), (0.30, 0.8), (0.52, 1.0), (0.70, 0.75), (0.88, 0.95), (0.42, 0.55), (0.80, 0.5))):
        x = px0 + fx * (px1 - px0)
        h = (py1 - py0) * (0.55 + 0.45 * fd)
        base = py1 + 6 if fd > 0.7 else hor + 40 + (py1 - hor - 40) * fd
        wdt = 10 + 14 * fd
        ops.append(Stroke(t, 0.7, [(x, base), (x + 3 * fd, base - h * 0.5), (x + 8 * fd, base - h)], [wdt, wdt * 0.8, wdt * 0.45], (0.97, 0.96, 0.93), dens=0.95, blur=0.8, kind="over", seed=420 + j))
        for k in range(int(5 + 4 * fd)):
            yl = base - h * r.uniform(0.08, 0.92)
            xl = x + (yl - base) / (-h) * 8 * fd
            ln = wdt * r.uniform(0.5, 1.0)
            ops.append(Stroke(t + 0.5, 0.2, [(xl - ln * 0.6, yl), (xl + ln * 0.5, yl + r.uniform(-2, 2))], [r.uniform(2, 4)], (0.14, 0.12, 0.12), dens=0.9, blur=0.5, seed=430 + j * 10 + k))
        for k in range(3):
            yb = base - h * r.uniform(0.55, 0.95)
            xb = x + (yb - base) / (-h) * 8 * fd
            side = r.choice([-1, 1])
            ops.append(Stroke(t + 0.7, 0.3, [(xb, yb), (xb + side * 30 * fd, yb - 40 * fd), (xb + side * 45 * fd, yb - 95 * fd)], [3, 2, 1.5], (0.28, 0.26, 0.24), dens=0.85, blur=0.5, seed=440 + j * 10 + k))
            ops.append(Bloom(t + 0.9, xb + side * 40 * fd, yb - 80 * fd, 30 + 30 * fd, (0.99, 0.84, 0.36), dens=0.5, dur=0.8, seed=450 + j * 10 + k, soft=1.5))
        t += 0.45
    for j in range(30):
        yv = hor + 30 + r.random() ** 0.7 * (py1 - hor - 40)
        x = r.uniform(px0 + 10, px1 - 10)
        s_ = 2 + 3 * (yv - hor) / (py1 - hor)
        ops.append(Stroke(t + j * 0.03, 0.2, [(x - s_, yv), (x + s_, yv - 1)], [s_ * 1.3], (0.96, 0.74, 0.28), dens=0.7, blur=0.8, seed=460 + j))
    return ops, t + 1.4, "leaves"


def scene_sunflowers(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.46, 0.66, 0.92), (0.70, 0.82, 0.94), (0.90, 0.92, 0.94)], dens=0.6, seed=471 + seed)
    cloud(ops, t0 + 1.4, px0 + 200, py0 + 100, 70, box, hor, seed=4, shadow=False)
    cloud(ops, t0 + 1.7, px0 + 660, py0 + 150, 55, box, hor, seed=5, shadow=False)
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    far = ridge(mx, hor - 30, 35, 260, 80, 0.9 + seed)
    hills(ops, t0 + 2.4, box, hor, far, mx, [(0.64, 0.76, 0.56)], dens=0.4, seed=472, blur=4)
    ops.append(Wash(t0 + 3.2, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.74, 0.76, 0.40), (0.50, 0.62, 0.30), (0.36, 0.50, 0.26)],
                    dens=0.65, blur=4, rough=0.18, seed=473, streak=0.15, edge=0.25))
    r = random.Random(41 + seed)
    t = t0 + 4.4
    heads = []
    for row in range(6):
        f = row / 5
        yv = hor + 30 + (py1 - hor - 60) * f ** 1.4
        R_ = 8 + 44 * f ** 1.3
        n = int(9 - 4 * f)
        for k in range(n):
            x = px0 + (k + 0.5 + 0.4 * (row % 2)) * (px1 - px0) / n + r.uniform(-15, 15)
            heads.append((x, yv, R_, f))
    for j, (x, yv, R_, f) in enumerate(heads):
        if f > 0.3:
            ops.append(Stroke(t + j * 0.04, 0.3, [(x, yv + R_ * 0.5), (x + 3, yv + R_ * 2.2 + 30)], [max(2, R_ * 0.14)], (0.32, 0.46, 0.22), dens=0.8, blur=0.7, seed=480 + j))
        ops.append(Bloom(t + 0.1 + j * 0.04, x, yv, R_, (0.98, 0.78, 0.18), dens=0.9, dur=0.5, seed=490 + j, soft=0.6))
        ops.append(Bloom(t + 0.3 + j * 0.04, x, yv, R_ * 0.45, (0.36, 0.24, 0.14), dens=0.95, dur=0.4, seed=500 + j, soft=0.8))
    t += 0.04 * len(heads) + 0.6
    sun(ops, t0 + 1.0, px0 + 760, py0 + 90, r=36, halo=110, seed=seed)
    end = birds(ops, t, [(px0 + 420, py0 + 90, 11), (px0 + 470, py0 + 125, 9)])
    return ops, end, "motes"


def scene_moon_sea(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.10, 0.12, 0.30), (0.18, 0.20, 0.42), (0.36, 0.34, 0.56)], dens=0.9, seed=511 + seed, rough=0.14)
    stars(ops, t0 + 2.0, box, hor, n=70, seed=seed, frac=0.7)
    mxp, myp = px0 + 560, py0 + 150
    ops.append(Bloom(t0 + 2.8, mxp, myp, 130, (0.94, 0.92, 0.86), dens=0.45, dur=1.4, seed=512, kind="over", soft=4.5))
    ops.append(Bloom(t0 + 3.2, mxp, myp, 44, (1.0, 0.99, 0.93), dens=1.0, dur=0.8, seed=513, kind="over", soft=0.9))
    for j in range(3):
        ops.append(Bloom(t0 + 3.6 + j * 0.3, px0 + 150 + j * 320, py0 + 240 + j * 30, 90, (0.30, 0.30, 0.52), dens=0.3, dur=1.2, seed=515 + j, soft=2.5).clip_to(px0, py0, px1, hor))
    water(ops, t0 + 4.6, box, hor, [(0.26, 0.28, 0.50), (0.16, 0.20, 0.42), (0.08, 0.10, 0.26)], dens=0.9, seed=516, streak=0.4)
    r = random.Random(51 + seed)
    for j in range(18):
        yv = hor + 14 + j * 22 + r.uniform(-3, 3)
        if yv > py1 - 10:
            break
        hw = 20 + j * 14
        cx_ = mxp + r.uniform(-hw * 0.4, hw * 0.4)
        ln = r.uniform(0.3, 0.7) * hw
        ops.append(Stroke(t0 + 6.0 + j * 0.06, 0.25, [(cx_ - ln, yv), (cx_ + ln, yv)], [3 if j < 8 else 4], (0.96, 0.94, 0.86), dens=r.uniform(0.45, 0.85), blur=0.9, kind="over", seed=520 + j))
    for j in range(14):
        yv = hor + 40 + r.random() * (py1 - hor - 60)
        ln = 15 + (yv - hor) / (py1 - hor) * 60
        x = r.uniform(px0 + 20 + ln, px1 - 20 - ln)
        ops.append(Stroke(t0 + 7.0 + j * 0.05, 0.3, [(x - ln, yv), (x + ln, yv)], [3], (0.60, 0.64, 0.84), dens=0.35, blur=1.2, kind="over", seed=540 + j))
    bx, by = px0 + 300, hor + 190
    ops.append(Wash(t0 + 7.8, 0.6, [(bx - 40, by), (bx + 44, by), (bx + 32, by + 14), (bx - 30, by + 14)], [(0.08, 0.08, 0.14)], dens=0.98, blur=1.0, rough=0.04, direction="right", seed=550, edge=0.0))
    ops.append(Stroke(t0 + 8.2, 0.3, [(bx + 2, by), (bx + 2, by - 60)], [3], (0.08, 0.08, 0.14), dens=0.95, blur=0.5, seed=551))
    ops.append(Bloom(t0 + 8.5, bx + 2, by - 62, 10, (1.0, 0.90, 0.60), dens=1.0, dur=0.4, seed=552, kind="over", soft=1.0))
    ops.append(Bloom(t0 + 8.6, bx + 2, by - 62, 36, (1.0, 0.86, 0.50), dens=0.4, dur=0.6, seed=553, kind="over", soft=4.0))
    return ops, t0 + 9.4, "none"


SCENES.update({"autumn": (scene_autumn, 0.4), "sakura": (scene_sakura, 0.5), "lavender": (scene_lavender, 0.4),
               "alpine": (scene_alpine, 0.55), "lighthouse": (scene_lighthouse, 0.5), "balloons": (scene_balloons, 0.6),
               "cabin": (scene_cabin, 0.5), "aurora": (scene_aurora, 0.68), "birch": (scene_birch, 0.3),
               "sunflowers": (scene_sunflowers, 0.35), "moon_sea": (scene_moon_sea, 0.5)})


# ================================================================ ТРИ ЦИТАТЫ В ОДНОМ РОЛИКЕ
PARTICLES = {
    "snow": dict(n=70, col=(255, 255, 255, 200), size=(1.8, 3.6), speed=(22, 48), down=True, sway=22, paint=True, alpha=0.75, twinkle=False),
    "petals": dict(n=45, col=(250, 200, 215, 215), size=(2.2, 4.0), speed=(18, 40), down=True, sway=30, paint=True, alpha=0.85, twinkle=False),
    "leaves": dict(n=40, col=(235, 140, 60, 215), size=(2.5, 4.5), speed=(20, 45), down=True, sway=34, paint=True, alpha=0.85, twinkle=False),
    "motes": dict(n=26, col=(255, 215, 140, 150), size=(3, 7), speed=(6, 14), down=False, sway=18, paint=False, alpha=0.6, twinkle=True),
    "fireflies": dict(n=22, col=(255, 230, 150, 170), size=(2, 4), speed=(4, 10), down=False, sway=18, paint=True, alpha=0.9, twinkle=True),
}


def wrap_text(text, fnt, max_w):
    """Перенос по словам с выравниванием длин строк."""
    if isinstance(text, list):
        return text
    words = []
    for w in text.split():
        if w in ("—", "–") and words:   # тире не переносим в начало строки
            words[-1] += " " + w
        else:
            words.append(w)

    def greedy(width):
        lines, cur = [], ""
        for w in words:
            cand = (cur + " " + w).strip()
            if fnt.getlength(cand) <= width or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    best = greedy(max_w)
    n = len(best)
    if n > 1:
        total = fnt.getlength(text)
        for mult in (1.05, 1.1, 1.18, 1.26):
            cand = greedy(min(max_w, max(total / n * mult, max(fnt.getlength(w) for w in words))))
            if len(cand) == n:
                spread = max(fnt.getlength(s) for s in cand) - min(fnt.getlength(s) for s in cand)
                spread_b = max(fnt.getlength(s) for s in best) - min(fnt.getlength(s) for s in best)
                if spread < spread_b:
                    best = cand
                break
    return best


def prepare_segment(seg, idx, seed):
    big = 66
    f_ru0 = font(F_RU, big)
    ru = wrap_text(seg["ru"], f_ru0, 900)
    f_en0 = font(F_EN, 56, 500)
    en = wrap_text(seg["en"], f_en0, 900)
    if len(ru) + len(en) > 6:
        big = 58
        ru = wrap_text(seg["ru"], font(F_RU, big), 900)
        en = wrap_text(seg["en"], font(F_EN, 50, 500), 900)
    f_ru, ru_size = fit_font(F_RU, ru, big, min_size=46)
    f_en, en_size = fit_font(F_EN, en, 56 if big == 66 else 50, min_size=42, wght=500)
    f_auth = font(F_SMALL, 31)
    S_RU = [text_sprite(s, f_ru, (48, 40, 36, 255)) for s in ru]
    S_EN = [text_sprite(s, f_en, (104, 90, 80, 255)) for s in en]
    S_A1 = text_sprite(seg["author_ru"], f_auth, (122, 108, 98, 255))
    S_A2 = text_sprite(seg["author_en"], f_auth, (140, 126, 116, 255))
    y = 290
    Y_RU = [y + i * int(ru_size * 1.42) for i in range(len(ru))]
    y_div = Y_RU[-1] + int(ru_size * 1.42) + 8
    Y_EN = [y_div + 34 + i * int(en_size * 1.24) for i in range(len(en))]
    y_auth = Y_EN[-1] + int(en_size * 1.24) + 34
    py0 = y_auth + 112
    px0, px1, py1 = 95, 985, 1760
    scene_fn, hor_frac = SCENES[seg["scene"]]
    hor = int(py0 + hor_frac * (py1 - py0))
    ops, paint_end, particles = scene_fn((px0, px1, py0, py1), hor, seed=seed + idx)
    T_RU = [2.2 + 1.1 * i for i in range(len(ru))]
    T_EN = [T_RU[-1] + 1.4 + 0.35 * i for i in range(len(en))]
    T_AUTHOR = T_EN[-1] + 1.4
    seg_total = max(13.0, T_AUTHOR + 4.8, paint_end + 3.2)
    rnd = random.Random(3 + seed + idx)
    spec = PARTICLES.get(particles)
    parts = []
    if spec:
        for _ in range(spec["n"]):
            if spec["paint"]:
                parts.append((rnd.uniform(px0, px1), rnd.uniform(py0, py1), rnd.uniform(*spec["size"]), rnd.uniform(0, 6.28), rnd.uniform(*spec["speed"])))
            else:
                parts.append((rnd.uniform(60, 1020), rnd.uniform(500, 1700), rnd.uniform(*spec["size"]), rnd.uniform(0, 6.28), rnd.uniform(*spec["speed"])))
    return dict(S_RU=S_RU, S_EN=S_EN, S_A1=S_A1, S_A2=S_A2, Y_RU=Y_RU, Y_EN=Y_EN, y_div=y_div, y_auth=y_auth, ops=ops,
                T_RU=T_RU, T_EN=T_EN, T_AUTHOR=T_AUTHOR, total=seg_total, T_END=seg_total - 1.1, parts=parts, spec=spec,
                box=(px0, px1, py0, py1), ru=ru, en=en, sizes=(ru_size, en_size), scene=seg["scene"])


def render_multi(cfg, out_path, preview=None, log=print):
    """cfg: dict(mark, music, seed, segments=[dict(scene, ru, en, author_ru, author_en), ...])"""
    t_start = time.time()
    seed = cfg.get("seed", 0)
    segs = [prepare_segment(s, i, seed) for i, s in enumerate(cfg["segments"])]
    f_mark = font(F_MARK, 30, 600)
    S_MARK = text_sprite(cfg.get("mark", "ЖИВЫЕ СТРОКИ  ·  LIVING LINES"), f_mark, (120, 104, 92, 255), spacing=5)
    DIV = Image.new("RGBA", (140, 3), (170, 140, 90, 200))
    TOTAL = sum(s["total"] for s in segs)
    offsets = np.cumsum([0] + [s["total"] for s in segs[:-1]])
    for s, off in zip(segs, offsets):
        log(f"  {s['scene']}: {s['total']:.1f} с, строк {len(s['ru'])}+{len(s['en'])}, шрифт {s['sizes']}, картина {s['box'][2]}-{s['box'][3]}")
    log(f"всего {TOTAL:.1f} с")
    writer = None if preview else fv.Writer(out_path, fps=FPS)
    grain = fv.GrainPool(sigma=1.5)
    nfr_total = int(TOTAL * FPS)
    preview_idx = {int(v * FPS) for v in preview} if preview else None
    previews = {}
    spr_cache = {}
    paper_rgb = np.array([246, 243, 236], np.float32)
    gi = 0
    for si, S in enumerate(segs):
        base = PAPER.copy()
        WET = np.full((H, W), -100.0, np.float32)
        ops = S["ops"]
        done = [False] * len(ops)
        spec = S["spec"]
        px0, px1, py0, py1 = S["box"]
        nfr = int(S["total"] * FPS)
        if si == len(segs) - 1:
            nfr = nfr_total - gi
        for i in range(nfr):
            t = i / FPS
            tg = gi / FPS
            canvas = base.copy()
            for k, op in enumerate(ops):
                if done[k] or t < op.t0:
                    continue
                A = op.alpha(t)
                col = op.colour(t) if isinstance(op, Dots) and op.multi else op.col
                x0, y0, x1, y1 = op.box
                if t >= op.t1 + 0.05:
                    apply(base, A, col, op.box, op.kind)
                    done[k] = True
                ap = apply(canvas, A, col, op.box, op.kind)
                WET[y0:y1, x0:x1] = np.where(ap > 0.06, t, WET[y0:y1, x0:x1])
            if preview_idx is not None and gi not in preview_idx:
                gi += 1
                continue
            wet = np.exp(-np.clip(t - WET, 0, None) / 1.8)
            disp = canvas * (1 - 0.07 * wet[..., None])
            disp += (1 - disp) * (0.13 * wet * SPEC)[..., None]
            disp *= FACT
            img = Image.fromarray((np.clip(disp, 0, 1) * 255).astype(np.uint8))
            if spec and t > 0.8:
                key = spec["col"]
                for (mx_, my_, sz, ph, sp) in S["parts"]:
                    if spec["paint"]:
                        lo, hi = py0, py1
                    else:
                        lo, hi = 500, 1700
                    px = mx_ + spec["sway"] * math.sin(t * 0.6 + ph)
                    if spec["down"]:
                        py = lo + (my_ + sp * t - lo) % (hi - lo)
                    else:
                        py = lo + (my_ - sp * t + 10 * math.sin(t * 0.8 + ph * 2) - lo) % (hi - lo)
                    if spec["paint"] and not (px0 < px < px1):
                        continue
                    a = spec["alpha"] * ((0.5 + 0.5 * math.sin(t * 1.3 + ph * 3)) if spec["twinkle"] else 1.0)
                    kk = (key, int(sz * 2))
                    if kk not in spr_cache:
                        Sz = int(sz * 4) + 4
                        im = Image.new("RGBA", (Sz, Sz), (0, 0, 0, 0))
                        ImageDraw.Draw(im).ellipse([Sz / 2 - sz, Sz / 2 - sz, Sz / 2 + sz, Sz / 2 + sz], fill=key)
                        spr_cache[kk] = im.filter(ImageFilter.GaussianBlur(max(0.6, sz * 0.5)))
                    paste_fade(img, spr_cache[kk], px, py, a * min(1, (t - 0.8) / 2))
            for spr, t0, yv in zip(S["S_RU"], S["T_RU"], S["Y_RU"]):
                a = ease(t0, 0.9, t)
                paste_fade(img, spr, (W - spr.size[0]) / 2, yv + 14 * (1 - a), a)
            paste_fade(img, DIV, (W - DIV.size[0]) / 2, S["y_div"], ease(S["T_EN"][0] - 0.3, 0.8, t))
            for spr, t0, yv in zip(S["S_EN"], S["T_EN"], S["Y_EN"]):
                a = ease(t0, 0.9, t)
                paste_fade(img, spr, (W - spr.size[0]) / 2, yv + 12 * (1 - a), a)
            a = ease(S["T_AUTHOR"], 1.0, t)
            paste_fade(img, S["S_A1"], (W - S["S_A1"].size[0]) / 2, S["y_auth"], a)
            paste_fade(img, S["S_A2"], (W - S["S_A2"].size[0]) / 2, S["y_auth"] + 44, a)
            # переход: уход в бумагу в конце сегмента
            k_ = 0.0
            if t > S["T_END"]:
                k_ = min(1.0, (t - S["T_END"]) / 1.0)
            arr = np.asarray(img, np.float32)
            if k_ > 0:
                arr = arr * (1 - k_) + paper_rgb * k_
            img = Image.fromarray(arr.astype(np.uint8))
            # шапка и точки-индикатор — поверх, без затухания (кроме самого конца)
            last = si == len(segs) - 1
            top_a = 1.0 if not last else max(0.0, 1 - max(0.0, (t - S["T_END"] - 0.3) / 0.7))
            top_a *= ease(0.3, 1.0, tg) if si == 0 else 1.0
            paste_fade(img, S_MARK, (W - S_MARK.size[0]) / 2, 140, top_a)
            dr = ImageDraw.Draw(img, "RGBA")
            n = len(segs)
            for j in range(n):
                cx_ = W / 2 + (j - (n - 1) / 2) * 30
                cy_ = 204
                if j <= si:
                    dr.ellipse([cx_ - 5, cy_ - 5, cx_ + 5, cy_ + 5], fill=(150, 130, 110, int(255 * top_a)))
                else:
                    dr.ellipse([cx_ - 5, cy_ - 5, cx_ + 5, cy_ + 5], outline=(160, 142, 124, int(200 * top_a)), width=2)
            z = 1.0 + 0.04 * (gi / nfr_total)
            x0, y0, cw, ch = fv.camera_window(W / 2, H / 2, z)
            img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)
            frame = grain.apply(img, gi)
            if preview_idx is not None:
                previews[gi] = Image.fromarray(frame)
            else:
                writer.add(frame)
            gi += 1
    if preview_idx is not None:
        return previews
    line_times = []
    for S, off in zip(segs, offsets):
        line_times += [off + tt for tt in S["T_RU"] + [S["T_EN"][0], S["T_AUTHOR"]]]
    mm = orchestra_mod if cfg["music"] in orchestra_mod.STYLES else music_mod
    audio = mm.make_music(cfg["music"], TOTAL, seed + 100, line_times)
    writer.close(audio, peak=0.7)
    log(f"готово {out_path}: {time.time() - t_start:.0f} с")
    return TOTAL


# ================================================================ ЕЩЁ СЦЕНЫ (17–28)
def scene_rain_window(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    # вид за окном: сумерки, размытые огни города
    ops.append(Wash(t0, 2.2, [(px0, py0), (px1, py0), (px1, py1), (px0, py1)], [(0.30, 0.34, 0.50), (0.40, 0.38, 0.52), (0.26, 0.26, 0.38)],
                    dens=0.85, blur=4, rough=0.14, seed=601 + seed, edge=0.15))
    r = random.Random(61 + seed)
    for j in range(14):
        x = r.uniform(px0 + 40, px1 - 40)
        y = r.uniform(hor - 120, hor + 160)
        R_ = r.uniform(26, 60)
        c = r.choice([(1.0, 0.86, 0.50), (1.0, 0.72, 0.40), (0.95, 0.90, 0.70), (0.80, 0.90, 1.0)])
        ops.append(Bloom(t0 + 1.6 + j * 0.12, x, y, R_, c, dens=r.uniform(0.3, 0.55), dur=1.0, seed=610 + j, kind="over", soft=3.5).clip_to(px0, py0, px1, py1))
    # капли и потёки на стекле
    for j in range(90):
        x = r.uniform(px0 + 8, px1 - 8)
        y = r.uniform(py0 + 8, py1 - 8)
        s_ = r.uniform(1.5, 4)
        ops.append(Stroke(t0 + 3.4 + j * 0.02, 0.2, [(x, y), (x + 0.5, y + s_ * r.uniform(1, 6))], [s_], (0.85, 0.90, 0.98), dens=r.uniform(0.35, 0.7), blur=0.8, kind="over", seed=630 + j))
    # рама окна
    fr = (0.30, 0.24, 0.20)
    ops.append(Wash(t0 + 5.4, 0.6, [(px0 + 435, py0), (px0 + 455, py0), (px0 + 455, py1), (px0 + 435, py1)], [fr], dens=0.95, blur=0.8, rough=0.03, direction="down", seed=650, edge=0.0))
    ops.append(Wash(t0 + 5.6, 0.6, [(px0, hor - 20), (px1, hor - 20), (px1, hor), (px0, hor)], [fr], dens=0.95, blur=0.8, rough=0.03, direction="right", seed=651, edge=0.0))
    for j, (x0_, x1_, y0_, y1_) in enumerate(((px0, px0 + 18, py0, py1), (px1 - 18, px1, py0, py1), (px0, px1, py0, py0 + 16))):
        ops.append(Wash(t0 + 5.8 + j * 0.1, 0.4, [(x0_, y0_), (x1_, y0_), (x1_, y1_), (x0_, y1_)], [fr], dens=0.95, blur=0.8, rough=0.03, direction="down", seed=652 + j, edge=0.0))
    # подоконник и чашка
    ops.append(Wash(t0 + 6.3, 0.7, [(px0 - 10, py1 - 70), (px1 + 10, py1 - 70), (px1 + 10, py1 + 6), (px0 - 10, py1 + 6)], [(0.84, 0.74, 0.60), (0.70, 0.58, 0.44)], dens=0.9, blur=1, rough=0.05, direction="right", seed=660, edge=0.2))
    cx_, cy_ = px0 + 660, py1 - 72
    ops.append(Wash(t0 + 6.9, 0.5, [(cx_ - 46, cy_ - 70), (cx_ + 46, cy_ - 70), (cx_ + 38, cy_), (cx_ - 38, cy_)], [(0.96, 0.95, 0.92)], dens=0.96, blur=1, rough=0.04, direction="down", seed=661, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 7.2, 0.3, [(cx_ + 46, cy_ - 55), (cx_ + 68, cy_ - 48), (cx_ + 66, cy_ - 20), (cx_ + 40, cy_ - 14)], [6], (0.90, 0.88, 0.86), dens=0.95, blur=0.6, kind="over", seed=662))
    ops.append(Stroke(t0 + 7.3, 0.3, [(cx_ - 46, cy_ - 70), (cx_ + 46, cy_ - 70)], [4], (0.82, 0.60, 0.40), dens=0.6, blur=0.8, seed=663))
    for j in range(3):
        ops.append(Bloom(t0 + 7.5 + j * 0.2, cx_ - 10 + j * 14, cy_ - 110 - j * 40, 16 + j * 8, (0.95, 0.95, 0.97), dens=0.4 - j * 0.08, dur=0.9, seed=665 + j, kind="over", soft=2.5))
    return ops, t0 + 8.6, "none"


def scene_windmill(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.56, 0.72, 0.92), (0.80, 0.86, 0.94), (0.96, 0.92, 0.88)], dens=0.58, seed=701 + seed)
    cloud(ops, t0 + 1.3, px0 + 180, py0 + 90, 70, box, hor, seed=6, shadow=False)
    cloud(ops, t0 + 1.6, px0 + 700, py0 + 130, 60, box, hor, seed=7, shadow=False)
    ops.append(Wash(t0 + 2.4, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.70, 0.80, 0.48), (0.56, 0.72, 0.40), (0.46, 0.64, 0.34)], dens=0.6, blur=4, rough=0.18, seed=702, streak=0.15, edge=0.25))
    r = random.Random(71 + seed)
    cols = [(0.90, 0.22, 0.24), (0.98, 0.78, 0.22), (0.94, 0.46, 0.60), (0.98, 0.56, 0.20)]
    t = t0 + 3.6
    for row in range(7):
        f = row / 6
        yv = hor + 30 + (py1 - hor - 50) * f ** 1.3
        n = int(14 - 5 * f)
        c = cols[row % 4]
        dots = []
        for k in range(n):
            x = px0 + (k + 0.5 + 0.3 * (row % 2)) * (px1 - px0) / n + r.uniform(-8, 8)
            dots.append((x, yv, 2.5 + 7 * f ** 1.2, c, r.random()))
        ops.append(Dots(t + row * 0.18, 0.7, dots, blur=0.9))
        if f > 0.25:
            ops.append(Stroke(t + row * 0.18 + 0.3, 0.4, [(px0 + 10, yv + 10 + 6 * f), (px1 - 10, yv + 12 + 6 * f)], [3 + 10 * f], (0.40, 0.58, 0.30), dens=0.4, blur=2, seed=710 + row))
    # мельница
    mx_, mb = px0 + 690, hor + 6
    ops.append(Wash(t + 1.4, 0.7, [(mx_ - 44, mb), (mx_ + 44, mb), (mx_ + 30, mb - 150), (mx_ - 30, mb - 150)], [(0.36, 0.30, 0.30), (0.28, 0.22, 0.24)], dens=0.92, blur=1, rough=0.05, direction="up", seed=720, edge=0.2))
    ops.append(Wash(t + 1.9, 0.4, [(mx_ - 36, mb - 148), (mx_ + 36, mb - 148), (mx_, mb - 188)], [(0.50, 0.30, 0.28)], dens=0.92, blur=1, rough=0.05, direction="up", seed=721, edge=0.0))
    for j in range(4):
        ang = math.radians(35 + 90 * j)
        ex, ey = mx_ + 110 * math.cos(ang), mb - 160 + 110 * math.sin(ang)
        ops.append(Stroke(t + 2.3 + j * 0.15, 0.3, [(mx_, mb - 160), (ex, ey)], [5], (0.30, 0.24, 0.26), dens=0.9, blur=0.6, seed=725 + j))
        px_, py_ = -math.sin(ang), math.cos(ang)
        ops.append(Wash(t + 2.4 + j * 0.15, 0.3, [(mx_ + 30 * math.cos(ang) + px_ * 2, mb - 160 + 30 * math.sin(ang) + py_ * 2), (ex + px_ * 2, ey + py_ * 2), (ex + px_ * 22, ey + py_ * 22), (mx_ + 30 * math.cos(ang) + px_ * 22, mb - 160 + 30 * math.sin(ang) + py_ * 22)],
                        [(0.94, 0.92, 0.88)], dens=0.85, blur=0.8, rough=0.05, direction="right", seed=730 + j, kind="over", edge=0.0))
    end = birds(ops, t + 3.2, [(px0 + 250, py0 + 140, 12), (px0 + 310, py0 + 180, 10)])
    return ops, end, "motes"


def scene_dunes(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.52, 0.44, 0.62), (0.94, 0.62, 0.52), (1.0, 0.84, 0.54)], dens=0.66, seed=801 + seed)
    sun(ops, t0 + 1.5, px0 + 330, hor - 40, r=46, halo=140, col=(1.0, 0.95, 0.80), hcol=(1.0, 0.86, 0.60), seed=seed)
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    layers = [(hor - 10, 40, 300, (0.86, 0.62, 0.42), 0.55), (hor + 110, 70, 220, (0.92, 0.70, 0.46), 0.6), (hor + 260, 90, 180, (0.84, 0.56, 0.36), 0.7), (hor + 420, 60, 150, (0.94, 0.74, 0.50), 0.65)]
    for j, (base_y, amp, k1, c, dn) in enumerate(layers):
        ry = base_y - amp * np.abs(np.sin(mx / k1 + j * 1.3 + seed)) - amp * 0.3 * np.sin(mx / (k1 * 0.37))
        ry = np.minimum(ry, py1 - 5)
        ops.append(Wash(t0 + 2.4 + j * 0.8, 1.2, list(zip(mx, ry)) + [(px1 + 10, py1 + 10), (px0 - 10, py1 + 10)], [c], dens=dn, blur=2, rough=0.1, direction="right", seed=810 + j, edge=0.3))
        shade = [(x, y) for x, y in zip(mx, ry)] + [(x, min(py1 + 10, y + 26 + 50 * (0.5 + 0.5 * math.sin(x / k1 + j * 1.3 + seed)))) for x, y in zip(mx[::-1], ry[::-1])]
        ops.append(Wash(t0 + 2.9 + j * 0.8, 0.9, shade, [(0.60, 0.36, 0.30)], dens=0.3, blur=5, rough=0.2, direction="right", seed=820 + j, edge=0.0))
    end = birds(ops, t0 + 6.2, [(px0 + 620, py0 + 130, 12), (px0 + 690, py0 + 165, 10)], col=(0.40, 0.30, 0.34))
    return ops, end, "motes"


def scene_forest_rays(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.0, [(px0, py0), (px1, py0), (px1, py1), (px0, py1)], [(0.78, 0.84, 0.74), (0.62, 0.72, 0.56), (0.42, 0.54, 0.38)], dens=0.62, blur=4, rough=0.14, seed=851 + seed, edge=0.1))
    r = random.Random(85 + seed)
    t = t0 + 1.8
    for depth in range(3):
        n = (7, 5, 4)[depth]
        col = [(0.58, 0.64, 0.58), (0.38, 0.42, 0.38), (0.20, 0.22, 0.20)][depth]
        wd = (8, 16, 30)[depth]
        for k in range(n):
            x = px0 + (k + 0.3 + 0.5 * r.random()) * (px1 - px0) / n + depth * 37
            if x > px1 - 10:
                x -= (px1 - px0) * 0.5
            top = py0 - 10
            base = py1 + 10 if depth else hor + 80 + 200 * r.random()
            ops.append(Stroke(t, 0.5, [(x, base), (x + 2, (base + top) / 2), (x + 4 - depth * 2, top)], [wd, wd * 0.9, wd * 0.7], col, dens=0.9 if depth else 0.6, blur=0.8 + (2 - depth) * 1.2, seed=860 + depth * 10 + k))
            t += 0.08
        # дымка между рядами
        ops.append(Wash(t, 0.8, [(px0, hor - 100 + depth * 90), (px1, hor - 100 + depth * 90), (px1, hor + 60 + depth * 90), (px0, hor + 60 + depth * 90)], [(0.94, 0.96, 0.92)], dens=0.35, blur=14, rough=0.35, direction="right", seed=880 + depth, kind="over", edge=0.0))
        t += 0.3
    # лучи
    for j in range(5):
        x = px0 + 140 + j * 180 + r.uniform(-40, 40)
        w = r.uniform(26, 60)
        ops.append(Wash(t + j * 0.2, 1.2, [(x - w, py0), (x + w, py0), (x + w + 170, py1), (x - w + 170, py1)], [(1.0, 0.96, 0.78)], dens=0.22, blur=12, rough=0.3, direction="down", seed=890 + j, kind="over", edge=0.0))
    # папоротник и подлесок
    for j in range(26):
        x = r.uniform(px0 + 10, px1 - 10)
        yv = r.uniform(py1 - 160, py1 - 10)
        ln = r.uniform(18, 46)
        ang = r.uniform(-1.3, -0.4) * r.choice([-1, 1])
        ops.append(Stroke(t + 1.4 + j * 0.04, 0.25, [(x, yv), (x + ln * math.cos(ang), yv + ln * math.sin(ang) * 0.5 - 10)], [4, 2], (0.30, 0.52, 0.30), dens=0.75, blur=0.8, seed=900 + j))
    return ops, t + 2.8, "motes"


def scene_waterfall(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor - 200, [(0.70, 0.80, 0.92), (0.88, 0.90, 0.92)], dens=0.5, seed=951 + seed, dur=1.6)
    # скалы
    ops.append(Wash(t0 + 1.4, 1.4, [(px0, py0 + 120), (px0 + 330, py0 + 60), (px0 + 360, py1 + 10), (px0 - 10, py1 + 10)], [(0.46, 0.50, 0.46), (0.28, 0.34, 0.30)], dens=0.85, blur=2, rough=0.14, direction="down", seed=952, edge=0.3))
    ops.append(Wash(t0 + 1.9, 1.4, [(px0 + 560, py0 + 40), (px1 + 10, py0 + 100), (px1 + 10, py1 + 10), (px0 + 530, py1 + 10)], [(0.42, 0.46, 0.42), (0.26, 0.32, 0.28)], dens=0.85, blur=2, rough=0.14, direction="down", seed=953, edge=0.3))
    # зелень на скалах
    r = random.Random(95 + seed)
    for j in range(12):
        side = j % 2
        x = px0 + (r.uniform(40, 300) if side == 0 else r.uniform(600, 860))
        y = r.uniform(py0 + 60, py1 - 200)
        ops.append(Bloom(t0 + 3.2 + j * 0.12, x, y, r.uniform(30, 70), r.choice([(0.34, 0.58, 0.34), (0.46, 0.66, 0.36), (0.28, 0.48, 0.30)]), dens=0.7, dur=0.9, seed=960 + j, soft=1.3))
    # водопад
    ops.append(Wash(t0 + 4.6, 1.6, [(px0 + 380, py0 + 70), (px0 + 510, py0 + 70), (px0 + 540, py1 - 160), (px0 + 350, py1 - 160)], [(0.96, 0.98, 1.0)], dens=0.9, blur=2, rough=0.12, direction="down", seed=965, kind="over", edge=0.0))
    for j in range(10):
        x = px0 + 375 + j * 15 + r.uniform(-4, 4)
        ops.append(Stroke(t0 + 5.6 + j * 0.05, 0.6, [(x, py0 + 80), (x + 10, py1 - 170)], [3], (0.80, 0.90, 0.96), dens=0.35, blur=1.2, seed=970 + j))
    # бассейн и туман
    ops.append(Wash(t0 + 6.2, 1.2, [(px0 + 60, py1 - 170), (px1 - 60, py1 - 170), (px1 + 10, py1 + 10), (px0 - 10, py1 + 10)], [(0.56, 0.78, 0.84), (0.34, 0.60, 0.72)], dens=0.75, blur=3, rough=0.2, direction="down", seed=975, streak=0.3, edge=0.2))
    for j in range(4):
        ops.append(Bloom(t0 + 7.0 + j * 0.2, px0 + 445 + r.uniform(-80, 80), py1 - 170 + r.uniform(-20, 30), 60 + j * 15, (0.97, 0.98, 1.0), dens=0.5, dur=1.0, seed=980 + j, kind="over", soft=3.5))
    # радуга
    for j, c in enumerate([(0.95, 0.40, 0.40), (0.98, 0.72, 0.30), (0.96, 0.92, 0.40), (0.50, 0.80, 0.50), (0.50, 0.70, 0.95), (0.60, 0.50, 0.85)]):
        R_ = 230 + j * 9
        pts = [(px0 + 445 + R_ * math.cos(a), py1 - 160 - R_ * math.sin(a) * 0.75) for a in np.linspace(0.25, math.pi - 0.25, 30)]
        ops.append(Stroke(t0 + 7.6 + j * 0.08, 0.8, pts, [9], c, dens=0.2, blur=4, kind="over", seed=990 + j))
    return ops, t0 + 9.0, "motes"


def scene_deer(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.62, 0.60, 0.78), (0.90, 0.76, 0.80), (0.98, 0.88, 0.84)], dens=0.6, seed=1001 + seed)
    spruce_row(ops, t0 + 2.0, box, hor - 30, (0.56, 0.58, 0.72), hmin=50, hmax=140, step=16, seed=1002, dens=0.5)
    spruce_row(ops, t0 + 2.8, box, hor + 10, (0.34, 0.38, 0.54), hmin=70, hmax=190, step=18, seed=1003, dens=0.75)
    ops.append(Wash(t0 + 3.8, 1.2, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.86, 0.88, 0.96), (0.78, 0.82, 0.94)], dens=0.2, blur=4, rough=0.2, seed=1004, streak=0.25, edge=0.1))
    for j, (yv, hh) in enumerate(((hor + 60, 40), (hor + 200, 60), (hor + 360, 70))):
        if yv < py1 - 20:
            poly = [(px0 + k * (px1 - px0) / 7, yv + 12 * math.sin(k * 1.5 + j)) for k in range(8)] + [(px1 - k * (px1 - px0) / 7, min(py1, yv + hh) + 8 * math.cos(k + j)) for k in range(8)]
            ops.append(Wash(t0 + 4.6 + j * 0.3, 0.8, poly, [(0.72, 0.78, 0.92)], dens=0.16, blur=8, rough=0.25, direction="right", seed=1010 + j, edge=0.03))
    # олень (силуэт)
    dx_, dy_ = px0 + 560, min(py1 - 60, hor + 230)
    dc = (0.30, 0.22, 0.20)
    body = [(dx_ - 70, dy_ - 10), (dx_ - 60, dy_ - 60), (dx_ + 40, dy_ - 64), (dx_ + 72, dy_ - 40), (dx_ + 70, dy_ + 6), (dx_ - 66, dy_ + 10)]
    ops.append(Wash(t0 + 5.8, 0.6, body, [dc], dens=0.95, blur=1.2, rough=0.06, direction="right", seed=1020, edge=0.0))
    ops.append(Stroke(t0 + 6.2, 0.4, [(dx_ + 60, dy_ - 50), (dx_ + 86, dy_ - 110), (dx_ + 96, dy_ - 150)], [22, 16, 12], dc, dens=0.95, blur=0.8, seed=1021))
    ops.append(Wash(t0 + 6.5, 0.3, [(dx_ + 84, dy_ - 160), (dx_ + 130, dy_ - 152), (dx_ + 128, dy_ - 138), (dx_ + 92, dy_ - 134)], [dc], dens=0.95, blur=0.8, rough=0.05, direction="right", seed=1022, edge=0.0))
    for j, (lx, lean) in enumerate(((dx_ - 56, -6), (dx_ - 38, 4), (dx_ + 40, -4), (dx_ + 58, 8))):
        ops.append(Stroke(t0 + 6.6 + j * 0.08, 0.3, [(lx, dy_), (lx + lean, dy_ + 70)], [9, 5], dc, dens=0.95, blur=0.6, seed=1025 + j))
    for j, (ax, ay, pts) in enumerate(((dx_ + 92, dy_ - 158, [(0, 0), (-14, -40), (-30, -70)]), (dx_ + 92, dy_ - 158, [(0, 0), (6, -44), (0, -80)]), (dx_ + 86, dy_ - 184, [(0, 0), (-22, -22)]), (dx_ + 96, dy_ - 190, [(0, 0), (18, -24)]))):
        ops.append(Stroke(t0 + 7.0 + j * 0.1, 0.3, [(ax + a, ay + b) for a, b in pts], [4, 3, 2], dc, dens=0.95, blur=0.5, seed=1030 + j))
    ops.append(Stroke(t0 + 7.4, 0.4, [(dx_ - 60, dy_ + 76), (dx_ + 70, dy_ + 78)], [14], (0.66, 0.70, 0.88), dens=0.3, blur=6, seed=1035))
    return ops, t0 + 8.2, "snow"


def scene_lotus(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.2, [(px0, py0), (px1, py0), (px1, py1), (px0, py1)], [(0.52, 0.70, 0.68), (0.38, 0.60, 0.60), (0.28, 0.48, 0.52)], dens=0.75, blur=4, rough=0.16, seed=1101 + seed, streak=0.2, edge=0.15))
    r = random.Random(110 + seed)
    for j in range(5):
        ops.append(Bloom(t0 + 1.6 + j * 0.2, r.uniform(px0 + 60, px1 - 60), r.uniform(py0 + 60, py1 - 60), r.uniform(60, 120), (0.80, 0.90, 0.86), dens=0.25, dur=1.2, seed=1105 + j, kind="over", soft=3.0).clip_to(px0, py0, px1, py1))
    t = t0 + 2.8
    pads = []
    for j in range(13):
        x, y = r.uniform(px0 + 60, px1 - 60), r.uniform(py0 + 80, py1 - 60)
        R_ = r.uniform(36, 80) * (0.6 + 0.6 * (y - py0) / (py1 - py0))
        ang = r.uniform(0, 6.28)
        poly = [(x + R_ * math.cos(a), y + R_ * 0.62 * math.sin(a)) for a in np.linspace(ang + 0.5, ang + 6.28 - 0.5, 24)] + [(x, y)]
        ops.append(Wash(t + j * 0.15, 0.6, poly, [r.choice([(0.34, 0.60, 0.34), (0.42, 0.66, 0.38), (0.28, 0.52, 0.32)])], dens=0.85, blur=1.2, rough=0.08, direction="right", seed=1110 + j, edge=0.3))
        pads.append((x, y, R_))
    t += 2.2
    for j in range(4):
        x, y, R_ = pads[r.randrange(len(pads))]
        fy = y - 10
        for k in range(7):
            a = -math.pi / 2 + (k - 3) * 0.42
            ln = R_ * 0.9
            ops.append(Stroke(t + j * 0.35 + k * 0.03, 0.3, [(x, fy), (x + ln * math.cos(a) * 0.7, fy + ln * math.sin(a))], [max(5, R_ * 0.28), 3], r.choice([(0.98, 0.70, 0.80), (0.99, 0.80, 0.86)]), dens=0.9, blur=1.0, kind="over", seed=1130 + j * 10 + k))
        ops.append(Bloom(t + j * 0.35 + 0.25, x, fy - 6, max(6, R_ * 0.16), (1.0, 0.88, 0.40), dens=0.95, dur=0.4, seed=1150 + j, kind="over", soft=0.8))
    t += 1.8
    for j in range(8):
        x, y = r.uniform(px0 + 30, px1 - 30), r.uniform(py0 + 40, py1 - 40)
        ops.append(Stroke(t + j * 0.08, 0.3, [(x - 30, y), (x + 30, y)], [3], (0.90, 0.96, 0.96), dens=0.5, blur=1.2, kind="over", seed=1160 + j))
    return ops, t + 1.2, "motes"


def scene_wheat(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.44, 0.64, 0.92), (0.70, 0.82, 0.94), (0.92, 0.92, 0.90)], dens=0.6, seed=1201 + seed)
    cloud(ops, t0 + 1.3, px0 + 230, py0 + 80, 75, box, hor, seed=8, shadow=False)
    cloud(ops, t0 + 1.6, px0 + 560, py0 + 150, 50, box, hor, seed=9, shadow=False)
    ops.append(Wash(t0 + 2.4, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.96, 0.86, 0.52), (0.92, 0.74, 0.36), (0.84, 0.62, 0.30)], dens=0.6, blur=4, rough=0.18, seed=1202, streak=0.2, edge=0.25))
    r = random.Random(120 + seed)
    t = t0 + 3.6
    for j in range(70):
        f = r.random() ** 0.8
        yv = hor + 30 + (py1 - hor - 50) * f
        x = r.uniform(px0 + 8, px1 - 8)
        h = 14 + 60 * f
        lean = r.uniform(-8, 8) * f
        ops.append(Stroke(t + j * 0.03, 0.3, [(x, yv + h * 0.3), (x + lean, yv - h)], [1.5 + 2 * f], (0.80, 0.62, 0.26), dens=0.7, blur=0.6, seed=1210 + j))
        ops.append(Stroke(t + j * 0.03 + 0.15, 0.2, [(x + lean, yv - h), (x + lean * 1.1, yv - h - 10 - 12 * f)], [3 + 5 * f], (0.90, 0.72, 0.32), dens=0.8, blur=0.7, seed=1300 + j))
    t += 2.4
    # дуб на горизонте
    tx, tb = px0 + 640, hor + 40
    end = round_tree(ops, t, tx, tb, 190, [(0.30, 0.50, 0.28), (0.40, 0.58, 0.32), (0.26, 0.44, 0.26)], seed=1320, trunk=(0.30, 0.22, 0.18), spread=1.2)
    end = birds(ops, end + 0.2, [(px0 + 320, py0 + 150, 12), (px0 + 380, py0 + 185, 10), (px0 + 450, py0 + 140, 9)])
    return ops, end, "motes"


def scene_savanna(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.60, 0.30, 0.40), (0.95, 0.50, 0.32), (1.0, 0.80, 0.42)], dens=0.72, seed=1401 + seed)
    sun(ops, t0 + 1.5, px0 + 600, hor - 60, r=58, halo=170, col=(1.0, 0.90, 0.62), hcol=(1.0, 0.74, 0.40), seed=seed)
    ops.append(Wash(t0 + 2.5, 1.5, [(px0, hor), (px1, hor), (px1, py1), (px0, py1)], [(0.70, 0.40, 0.30), (0.46, 0.26, 0.24), (0.30, 0.18, 0.18)], dens=0.85, blur=4, rough=0.18, seed=1402, streak=0.2, edge=0.2))
    r = random.Random(140 + seed)
    for j in range(30):
        yv = hor + 20 + r.random() * (py1 - hor - 40)
        x = r.uniform(px0 + 8, px1 - 8)
        h = 8 + 30 * (yv - hor) / (py1 - hor)
        ops.append(Stroke(t0 + 3.8 + j * 0.03, 0.25, [(x, yv), (x + r.uniform(-5, 5), yv - h)], [2], (0.22, 0.14, 0.14), dens=0.8, blur=0.6, seed=1410 + j))
    # акация
    ax, ab = px0 + 300, hor + 120
    dk = (0.16, 0.10, 0.12)
    ops.append(Stroke(t0 + 5.0, 0.6, [(ax, ab), (ax + 8, ab - 90), (ax + 20, ab - 160)], [14, 10, 6], dk, dens=0.95, blur=0.7, seed=1420))
    for j, (ex, ey) in enumerate(((ax - 90, ab - 215), (ax - 30, ab - 230), (ax + 60, ab - 228), (ax + 120, ab - 210), (ax + 160, ab - 190))):
        ops.append(Stroke(t0 + 5.5 + j * 0.1, 0.4, [(ax + 20, ab - 160), (ex, ey)], [5, 3], dk, dens=0.95, blur=0.6, seed=1425 + j))
    crown = [(ax - 140, ab - 210), (ax - 110, ab - 250), (ax + 20, ab - 268), (ax + 150, ab - 250), (ax + 200, ab - 205), (ax + 150, ab - 192), (ax + 20, ab - 200), (ax - 100, ab - 195)]
    ops.append(Wash(t0 + 6.1, 0.9, crown, [dk], dens=0.95, blur=3, rough=0.3, direction="right", seed=1430, edge=0.0))
    end = birds(ops, t0 + 7.2, [(px0 + 700, py0 + 160, 13), (px0 + 760, py0 + 200, 11), (px0 + 820, py0 + 150, 9)], col=(0.20, 0.12, 0.14))
    return ops, end, "none"


def scene_swans(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.86, 0.80, 0.90), (0.98, 0.86, 0.84), (0.99, 0.92, 0.80)], dens=0.5, seed=1501 + seed)
    mx = np.linspace(px0 - 10, px1 + 10, 80)
    far = ridge(mx, hor - 40, 40, 240, 70, 0.9 + seed)
    hills(ops, t0 + 1.8, box, hor, far, mx, [(0.74, 0.74, 0.84)], dens=0.4, seed=1502, blur=4)
    water(ops, t0 + 2.8, box, hor, [(0.96, 0.88, 0.86), (0.82, 0.84, 0.92), (0.70, 0.78, 0.90)], dens=0.5, seed=1503, streak=0.3)
    reflection(ops, t0 + 3.8, box, hor, far, mx, (0.72, 0.72, 0.82), dens=0.2, seed=1504)
    # камыши
    r = random.Random(150 + seed)
    for j in range(18):
        x = px0 + (r.uniform(10, 150) if j % 2 == 0 else r.uniform(740, 880))
        base = r.uniform(hor + 20, py1 - 20)
        h = r.uniform(60, 150)
        ops.append(Stroke(t0 + 4.4 + j * 0.05, 0.3, [(x, base), (x + r.uniform(-6, 6), base - h)], [2.5], (0.46, 0.50, 0.34), dens=0.8, blur=0.6, seed=1510 + j))
        ops.append(Stroke(t0 + 4.6 + j * 0.05, 0.2, [(x, base - h), (x, base - h - 18)], [6], (0.42, 0.30, 0.22), dens=0.9, blur=0.6, seed=1530 + j))
    # лебеди
    def swan(t, x, y, s, flip):
        f = -1 if flip else 1
        body = [(x - 40 * s * f, y), (x - 30 * s * f, y - 16 * s), (x + 10 * s * f, y - 22 * s), (x + 44 * s * f, y - 14 * s), (x + 40 * s * f, y + 6 * s), (x - 36 * s * f, y + 8 * s)]
        ops.append(Wash(t, 0.5, body, [(0.99, 0.98, 0.97)], dens=0.97, blur=1.0, rough=0.05, direction="right", seed=1540 + int(x), kind="over", edge=0.0))
        ops.append(Stroke(t + 0.3, 0.4, [(x + 36 * s * f, y - 14 * s), (x + 50 * s * f, y - 44 * s), (x + 40 * s * f, y - 70 * s), (x + 52 * s * f, y - 80 * s)], [10 * s, 8 * s, 7 * s, 7 * s], (0.99, 0.98, 0.97), dens=0.97, blur=0.8, kind="over", seed=1545 + int(x)))
        ops.append(Stroke(t + 0.6, 0.2, [(x + 52 * s * f, y - 80 * s), (x + 66 * s * f, y - 76 * s)], [5 * s, 3 * s], (0.92, 0.50, 0.24), dens=0.95, blur=0.5, seed=1550 + int(x)))
        ops.append(Stroke(t + 0.7, 0.4, [(x - 44 * s * f, y + 14 * s), (x + 48 * s * f, y + 16 * s)], [8 * s], (0.78, 0.80, 0.90), dens=0.3, blur=4, seed=1555 + int(x)))
    swan(t0 + 5.6, px0 + 380, hor + 160, 1.1, False)
    swan(t0 + 6.4, px0 + 560, hor + 220, 1.3, True)
    for j in range(8):
        yv = hor + 30 + r.random() * (py1 - hor - 60)
        x = r.uniform(px0 + 200, px1 - 200)
        ops.append(Stroke(t0 + 7.4 + j * 0.06, 0.3, [(x - 40, yv), (x + 40, yv)], [3], (0.98, 0.96, 0.96), dens=0.5, blur=1.2, kind="over", seed=1560 + j))
    end = birds(ops, t0 + 8.0, [(px0 + 240, py0 + 120, 11), (px0 + 300, py0 + 160, 9)])
    return ops, end, "motes"


def scene_candle(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    ops.append(Wash(t0, 2.2, [(px0, py0), (px1, py0), (px1, py1), (px0, py1)], [(0.26, 0.18, 0.18), (0.40, 0.26, 0.20), (0.30, 0.20, 0.16)], dens=0.9, blur=4, rough=0.14, seed=1601 + seed, edge=0.1))
    # стол
    ops.append(Wash(t0 + 1.8, 1.0, [(px0 - 10, py1 - 230), (px1 + 10, py1 - 230), (px1 + 10, py1 + 10), (px0 - 10, py1 + 10)], [(0.52, 0.36, 0.24), (0.38, 0.26, 0.18)], dens=0.85, blur=2, rough=0.1, direction="right", seed=1602, streak=0.3, edge=0.2))
    # книга
    bx, by = px0 + 300, py1 - 150
    ops.append(Wash(t0 + 2.8, 0.8, [(bx - 150, by), (bx + 150, by), (bx + 165, by + 60), (bx - 165, by + 60)], [(0.96, 0.93, 0.86)], dens=0.95, blur=1.2, rough=0.05, direction="right", seed=1603, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 3.4, 0.3, [(bx, by - 4), (bx, by + 64)], [3], (0.70, 0.62, 0.52), dens=0.7, blur=0.6, seed=1604))
    r = random.Random(160 + seed)
    for j in range(10):
        side = -1 if j < 5 else 1
        yl = by + 10 + (j % 5) * 10
        ops.append(Stroke(t0 + 3.5 + j * 0.05, 0.2, [(bx + side * 20, yl), (bx + side * (120 + r.uniform(-20, 10)), yl + 1)], [1.5], (0.62, 0.56, 0.50), dens=0.6, blur=0.4, seed=1610 + j))
    ops.append(Wash(t0 + 4.1, 0.4, [(bx - 150, by + 60), (bx + 150, by + 60), (bx + 165, by + 74), (bx - 165, by + 74)], [(0.60, 0.36, 0.30)], dens=0.9, blur=1, rough=0.05, direction="right", seed=1620, edge=0.0))
    # свеча
    cx_, cb = px0 + 650, py1 - 160
    ops.append(Wash(t0 + 4.6, 0.6, [(cx_ - 24, cb), (cx_ + 24, cb), (cx_ + 22, cb - 150), (cx_ - 22, cb - 150)], [(0.98, 0.94, 0.84)], dens=0.95, blur=1.2, rough=0.06, direction="up", seed=1621, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 5.1, 0.3, [(cx_ - 18, cb - 150), (cx_ - 20, cb - 110)], [8], (0.98, 0.94, 0.84), dens=0.9, blur=1.5, kind="over", seed=1622))
    ops.append(Wash(t0 + 5.3, 0.4, [(cx_ - 40, cb), (cx_ + 40, cb), (cx_ + 46, cb + 22), (cx_ - 46, cb + 22)], [(0.52, 0.44, 0.34)], dens=0.9, blur=1, rough=0.06, direction="right", seed=1623, edge=0.0))
    ops.append(Stroke(t0 + 5.5, 0.2, [(cx_, cb - 150), (cx_, cb - 166)], [3], (0.20, 0.14, 0.12), dens=0.9, blur=0.5, seed=1624))
    ops.append(Bloom(t0 + 5.7, cx_, cb - 200, 150, (1.0, 0.72, 0.36), dens=0.45, dur=1.2, seed=1625, kind="over", soft=4.5))
    ops.append(Bloom(t0 + 6.0, cx_, cb - 186, 22, (1.0, 0.86, 0.46), dens=0.95, dur=0.5, seed=1626, kind="over", soft=1.4))
    ops.append(Bloom(t0 + 6.2, cx_, cb - 180, 9, (1.0, 1.0, 0.92), dens=1.0, dur=0.4, seed=1627, kind="over", soft=0.8))
    ops.append(Wash(t0 + 6.4, 0.6, [(cx_ - 20, cb + 20), (cx_ + 20, cb + 20), (cx_ + 150, cb + 60), (cx_ - 150, cb + 60)], [(0.20, 0.12, 0.10)], dens=0.35, blur=6, rough=0.2, direction="right", seed=1628, edge=0.0))
    # чашка
    tx_, tb_ = px0 + 820, py1 - 120
    ops.append(Wash(t0 + 6.8, 0.5, [(tx_ - 34, tb_ - 50), (tx_ + 34, tb_ - 50), (tx_ + 28, tb_), (tx_ - 28, tb_)], [(0.90, 0.86, 0.80)], dens=0.95, blur=1, rough=0.05, direction="down", seed=1629, kind="over", edge=0.0))
    ops.append(Stroke(t0 + 7.1, 0.3, [(tx_ + 34, tb_ - 40), (tx_ + 52, tb_ - 34), (tx_ + 50, tb_ - 14), (tx_ + 30, tb_ - 10)], [5], (0.86, 0.82, 0.76), dens=0.95, blur=0.6, kind="over", seed=1630))
    for j in range(3):
        ops.append(Bloom(t0 + 7.3 + j * 0.2, tx_ - 6 + j * 10, tb_ - 80 - j * 32, 12 + j * 6, (0.95, 0.92, 0.90), dens=0.35 - j * 0.07, dur=0.8, seed=1632 + j, kind="over", soft=2.5))
    return ops, t0 + 8.3, "fireflies"


def scene_beach(box, hor, t0=0.8, seed=0):
    px0, px1, py0, py1 = box
    ops = []
    sky(ops, t0, box, hor, [(0.46, 0.70, 0.94), (0.74, 0.86, 0.95), (0.96, 0.94, 0.90)], dens=0.58, seed=1701 + seed)
    cloud(ops, t0 + 1.3, px0 + 230, py0 + 90, 70, box, hor, seed=10, shadow=False)
    sun(ops, t0 + 1.6, px0 + 720, py0 + 110, r=40, halo=120, seed=seed)
    sea_b = hor + (py1 - hor) * 0.55
    ops.append(Wash(t0 + 2.4, 1.4, [(px0, hor), (px1, hor), (px1, sea_b), (px0, sea_b)], [(0.24, 0.60, 0.82), (0.36, 0.78, 0.86), (0.60, 0.88, 0.88)], dens=0.75, blur=4, rough=0.18, seed=1702, streak=0.3, edge=0.25))
    ops.append(Wash(t0 + 3.6, 1.2, [(px0, sea_b - 20), (px1, sea_b - 30), (px1, py1), (px0, py1)], [(0.98, 0.94, 0.82), (0.96, 0.88, 0.70)], dens=0.5, blur=4, rough=0.25, seed=1703, streak=0.2, edge=0.15))
    r = random.Random(170 + seed)
    for j in range(8):
        x = px0 + 40 + j * 120 + r.uniform(-30, 30)
        ops.append(Stroke(t0 + 4.6 + j * 0.08, 0.5, [(x - 70, sea_b - 14 + r.uniform(-8, 8)), (x + 70, sea_b - 10 + r.uniform(-8, 8))], [8], (0.99, 0.99, 0.98), dens=0.6, blur=2.5, kind="over", seed=1710 + j))
    for j in range(12):
        yv = hor + 20 + r.random() * (sea_b - hor - 60)
        ln = 15 + (yv - hor) / (sea_b - hor) * 50
        x = r.uniform(px0 + 20 + ln, px1 - 20 - ln)
        ops.append(Stroke(t0 + 5.2 + j * 0.05, 0.3, [(x - ln, yv), (x + ln, yv)], [3], (0.96, 0.99, 0.99), dens=0.55, blur=1, kind="over", seed=1720 + j))
    # пальма слева
    pxp, pb = px0 + 170, py1 - 20
    ops.append(Stroke(t0 + 6.0, 0.7, [(pxp, pb), (pxp - 30, pb - 180), (pxp - 90, pb - 340), (pxp - 130, pb - 440)], [22, 16, 12, 9], (0.44, 0.32, 0.22), dens=0.92, blur=0.8, seed=1730))
    top = (pxp - 130, pb - 440)
    for j, (ang, ln) in enumerate(((-2.6, 160), (-2.0, 190), (-1.2, 170), (-0.5, 180), (0.2, 150), (-2.9, 120))):
        pts = [(top[0] + ln * k * math.cos(ang), top[1] + ln * k * math.sin(ang) + 70 * k * k) for k in np.linspace(0, 1, 6)]
        ops.append(Stroke(t0 + 6.7 + j * 0.12, 0.4, pts, [14, 12, 9, 6, 4, 2], (0.26, 0.56, 0.34), dens=0.85, blur=1.2, seed=1735 + j))
        for k in range(5):
            u = 0.25 + k * 0.16
            bx_, by_ = top[0] + ln * u * math.cos(ang), top[1] + ln * u * math.sin(ang) + 70 * u * u
            ops.append(Stroke(t0 + 6.9 + j * 0.12, 0.25, [(bx_, by_), (bx_ + 18 * math.cos(ang + 1.3), by_ + 28)], [3], (0.30, 0.60, 0.36), dens=0.75, blur=0.8, seed=1760 + j * 10 + k))
    ops.append(Stroke(t0 + 7.9, 0.4, [(pxp - 20, pb + 4), (pxp + 160, pb - 20)], [16], (0.70, 0.62, 0.50), dens=0.3, blur=5, seed=1790))
    end = birds(ops, t0 + 8.2, [(px0 + 500, py0 + 140, 12), (px0 + 560, py0 + 180, 10)])
    return ops, end, "motes"


SCENES.update({"rain_window": (scene_rain_window, 0.55), "windmill": (scene_windmill, 0.42), "dunes": (scene_dunes, 0.42),
               "forest_rays": (scene_forest_rays, 0.5), "waterfall": (scene_waterfall, 0.5), "deer": (scene_deer, 0.45),
               "lotus": (scene_lotus, 0.5), "wheat": (scene_wheat, 0.45), "savanna": (scene_savanna, 0.55),
               "swans": (scene_swans, 0.45), "candle": (scene_candle, 0.5), "beach": (scene_beach, 0.42)})
