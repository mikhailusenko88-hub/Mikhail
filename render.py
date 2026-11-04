"""Отрисовка гонки 1920×1080: трасса (тайлы), вращающиеся тела (спрайты), шарики-флаги, живая таблица."""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import countries

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080
VIEW_W = 1440
PANEL_X = 1440
FONT_B = os.path.join(HERE, "fonts", "Poppins-Bold.ttf")
FONT_M = os.path.join(HERE, "fonts", "Poppins-Medium.ttf")
WX0, WX1 = -700, 1700
TILE = 1024
Y_TOP = -420
MIN_S, MAX_S = 0.7, 1.0
_fonts = {}


def font(size, bold=True):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_B if bold else FONT_M, size)
    return _fonts[key]


THEMES = [
    dict(name="neon", bg0=(7, 9, 26), bg1=(16, 8, 42), wall=(80, 215, 255), ramp=(140, 235, 255), peg=(255, 90, 200),
         bump=(255, 200, 60), rings=[(0, 255, 210), (120, 150, 255), (255, 80, 200), (255, 220, 70), (90, 255, 140), (255, 120, 90)],
         spin=(255, 230, 90), flap=(120, 255, 180), accent=(0, 255, 210)),
    dict(name="sunset", bg0=(26, 6, 24), bg1=(46, 12, 22), wall=(255, 130, 80), ramp=(255, 180, 120), peg=(255, 225, 120),
         bump=(120, 255, 210), rings=[(255, 90, 100), (255, 170, 60), (255, 235, 100), (120, 255, 210), (200, 130, 255), (255, 120, 200)],
         spin=(120, 255, 210), flap=(255, 235, 100), accent=(255, 170, 60)),
    dict(name="forest", bg0=(5, 20, 16), bg1=(8, 34, 24), wall=(120, 255, 130), ramp=(180, 255, 160), peg=(255, 250, 140),
         bump=(255, 120, 200), rings=[(150, 255, 90), (255, 240, 100), (90, 220, 255), (255, 140, 90), (220, 140, 255), (255, 255, 255)],
         spin=(255, 240, 100), flap=(90, 220, 255), accent=(150, 255, 90)),
    dict(name="ice", bg0=(6, 16, 36), bg1=(10, 28, 58), wall=(160, 225, 255), ramp=(210, 240, 255), peg=(255, 255, 255),
         bump=(255, 120, 160), rings=[(130, 230, 255), (220, 240, 255), (120, 160, 255), (255, 150, 200), (150, 255, 230), (255, 255, 160)],
         spin=(255, 150, 200), flap=(150, 255, 230), accent=(130, 230, 255)),
    dict(name="lava", bg0=(26, 7, 5), bg1=(46, 12, 7), wall=(255, 110, 40), ramp=(255, 160, 80), peg=(255, 220, 90),
         bump=(90, 220, 255), rings=[(255, 80, 30), (255, 180, 40), (255, 240, 120), (90, 220, 255), (255, 120, 160), (200, 255, 120)],
         spin=(255, 240, 120), flap=(90, 220, 255), accent=(255, 140, 40)),
    dict(name="space", bg0=(12, 6, 30), bg1=(24, 10, 50), wall=(185, 120, 255), ramp=(215, 170, 255), peg=(120, 255, 230),
         bump=(255, 210, 80), rings=[(185, 120, 255), (120, 255, 230), (255, 120, 200), (255, 210, 80), (130, 180, 255), (255, 255, 255)],
         spin=(120, 255, 230), flap=(255, 210, 80), accent=(185, 120, 255)),
    dict(name="gold", bg0=(18, 13, 5), bg1=(32, 24, 8), wall=(255, 205, 80), ramp=(255, 230, 150), peg=(255, 255, 220),
         bump=(255, 110, 90), rings=[(255, 205, 80), (255, 245, 200), (255, 150, 60), (255, 110, 90), (255, 230, 120), (255, 255, 255)],
         spin=(255, 245, 200), flap=(255, 150, 60), accent=(255, 205, 80)),
]


def mix(c, d, k):
    return tuple(int(a + (b - a) * k) for a, b in zip(c, d))


# ---------------------------------------------------------------- флаги
_flag_sq, _flag_rect = {}, {}


def flag_square(a2):
    if a2 not in _flag_sq:
        im = Image.open(os.path.join(HERE, "flags", f"{a2}.png")).convert("RGB")
        w, h = im.size
        _flag_sq[a2] = im.crop(((w - h) // 2, 0, (w - h) // 2 + h, h))
    return _flag_sq[a2]


def flag_rect(a2, w, h, radius=5, border=(255, 255, 255, 60)):
    key = (a2, w, h, radius)
    if key not in _flag_rect:
        S = 3
        im = Image.open(os.path.join(HERE, "flags", f"{a2}.png")).convert("RGBA").resize((w * S, h * S), Image.LANCZOS)
        m = Image.new("L", (w * S, h * S), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius * S, fill=255)
        im.putalpha(m)
        ImageDraw.Draw(im).rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius * S, outline=border, width=S * 2)
        _flag_rect[key] = im.resize((w, h), Image.LANCZOS)
    return _flag_rect[key]


_shade = {}


def _shade_overlay(D):
    if D not in _shade:
        yy, xx = np.mgrid[0:D, 0:D].astype(np.float32)
        c = (D - 1) / 2
        r = np.hypot(xx - c, yy - c) / (D / 2)
        dark = np.clip((r - 0.55) / 0.45, 0, 1) ** 1.6 * 0.55
        hx, hy = c - D * 0.18, c - D * 0.2
        hl = np.exp(-((xx - hx) ** 2 + (yy - hy) ** 2) / (2 * (D * 0.13) ** 2)) * 0.75
        _shade[D] = (dark, hl)
    return _shade[D]


_ball = {}
ROT_STEPS = 24


def ball_sprite(a2, rpx, rot):
    step = int(round((rot % (2 * math.pi)) / (2 * math.pi) * ROT_STEPS)) % ROT_STEPS
    key = (a2, rpx, step)
    if key in _ball:
        return _ball[key]
    S = 3
    D = 2 * rpx
    big = flag_square(a2).resize((D * S, D * S), Image.BILINEAR).rotate(-step * 360 / ROT_STEPS, Image.BICUBIC)
    arr = np.asarray(big.resize((D, D), Image.LANCZOS), np.float32)
    dark, hl = _shade_overlay(D)
    arr = arr * (1 - dark[..., None]) + hl[..., None] * 255 * (1 - arr / 255 * 0.3)
    rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    m = Image.new("L", (D * S, D * S), 0)
    ImageDraw.Draw(m).ellipse([1, 1, D * S - 2, D * S - 2], fill=255)
    m = m.resize((D, D), Image.LANCZOS)
    out = rgb.convert("RGBA")
    out.putalpha(m)
    ring = Image.new("RGBA", (D * S, D * S), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([1, 1, D * S - 2, D * S - 2], outline=(0, 0, 0, 150), width=S * 2)
    out = Image.alpha_composite(out, ring.resize((D, D), Image.LANCZOS))
    _ball[key] = out
    return out


# ---------------------------------------------------------------- трасса: тайлы
class StageArt:
    def __init__(self, T, theme):
        self.T = T
        self.th = theme
        self.y_bot = T.height + 300
        self.tiles = {}
        self.order = []
        self.statics = [s for s in T.static.segs]
        self.sprites = {}
        self.sprite_scaled = {}
        self.ring_hp0 = {i: b.hp for i, b in enumerate(T.bodies) if b.hp > 0}

    def seg_color(self, kind):
        th = self.th
        return {0: th["wall"], 5: th["ramp"], 1: th["peg"], 3: th["bump"], 4: th["spin"], 2: th["rings"][0]}[kind]

    def tile(self, ti):
        if ti in self.tiles:
            return self.tiles[ti]
        th = self.th
        y0 = Y_TOP + ti * TILE
        tw = WX1 - WX0
        # фон: градиент по высоте этапа + тёмные поля вне стенок + точки-сетка
        k = np.clip((np.arange(TILE) + y0 - Y_TOP) / max(1, self.y_bot - Y_TOP), 0, 1)[:, None, None]
        bg0 = np.array(th["bg0"], np.float32)
        bg1 = np.array(th["bg1"], np.float32)
        base = bg0 + (bg1 - bg0) * k
        img = np.repeat(np.repeat(base, 1, 0), tw, 1)
        xs = np.arange(tw) + WX0
        side = ((xs < -10) | (xs > 1010)).astype(np.float32)
        img = img * (1 - 0.35 * side[None, :, None])
        # лёгкая сетка точек внутри трассы
        ys = np.arange(TILE) + y0
        dots = ((ys[:, None] % 60) < 3) & ((xs[None, :] % 60) < 3) & (xs[None, :] > 0) & (xs[None, :] < 1000)
        img[dots] = img[dots] * 0.5 + np.array(th["accent"], np.float32) * 0.12 + 10
        S = 2
        lines = Image.new("RGBA", (tw * S, TILE * S), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lines)
        GM = 64
        gl = Image.new("RGB", (tw // 4, (TILE + 2 * GM) // 4), (0, 0, 0))
        dg = ImageDraw.Draw(gl)
        for (ax, ay, bx, by, rad, kind) in self.statics:
            if max(ay, by) + rad + 90 < y0 or min(ay, by) - rad - 90 > y0 + TILE:
                continue
            col = self.seg_color(kind)
            self._capsule(dl, ax, ay, bx, by, rad, col, kind, WX0, y0, S)
            gx = lambda v: (v - WX0) / 4
            gy = lambda v: (v - y0 + GM) / 4
            wg = max(2, int((rad * 2 + 14) / 4))
            if ax == bx and ay == by:
                rr = (rad + 9) / 4
                dg.ellipse([gx(ax) - rr, gy(ay) - rr, gx(ax) + rr, gy(ay) + rr], fill=col)
            else:
                dg.line([gx(ax), gy(ay), gx(bx), gy(by)], fill=col, width=wg)
        # финиш
        fy = self.T.finish_y
        if y0 - 40 < fy < y0 + TILE + 40:
            for i in range(24):
                for j in range(2):
                    x = 385 + i * (230 / 24)
                    yy = fy - 10 + j * 10
                    c = (255, 255, 255, 255) if (i + j) % 2 == 0 else (20, 20, 20, 255)
                    dl.rectangle([(x - WX0) * S, (yy - y0) * S, (x + 230 / 24 - WX0) * S, (yy + 10 - y0) * S], fill=c)
        glow = gl.filter(ImageFilter.GaussianBlur(5)).resize((tw, TILE + 2 * GM), Image.BILINEAR)
        glow = np.asarray(glow, np.float32)[GM:GM + TILE]
        img = np.clip(img + glow * 0.55, 0, 255).astype(np.uint8)
        out = Image.fromarray(img)
        lines = lines.resize((tw, TILE), Image.LANCZOS)
        out.paste(lines, (0, 0), lines)
        arr = np.asarray(out)
        self.tiles[ti] = arr
        self.order.append(ti)
        if len(self.order) > 5:
            old = self.order.pop(0)
            self.tiles.pop(old, None)
        return arr

    @staticmethod
    def _capsule(d, ax, ay, bx, by, rad, col, kind, ox, oy, S):
        X = lambda v: (v - ox) * S
        Y = lambda v: (v - oy) * S
        hi = mix(col, (255, 255, 255), 0.55)
        if ax == bx and ay == by:
            r = rad * S
            if kind == 3:
                d.ellipse([X(ax) - r, Y(ay) - r, X(ax) + r, Y(ay) + r], fill=mix(col, (0, 0, 0), 0.55) + (255,),
                          outline=col + (255,), width=max(2, int(r * 0.32)))
                r2 = r * 0.35
                d.ellipse([X(ax) - r2, Y(ay) - r2, X(ax) + r2, Y(ay) + r2], fill=hi + (255,))
            else:
                d.ellipse([X(ax) - r, Y(ay) - r, X(ax) + r, Y(ay) + r], fill=col + (255,))
                r2 = r * 0.45
                d.ellipse([X(ax) - r2 - r * 0.15, Y(ay) - r2 - r * 0.15, X(ax) + r2 - r * 0.15, Y(ay) + r2 - r * 0.15],
                          fill=hi + (255,))
            return
        w = int(rad * 2 * S)
        d.line([X(ax), Y(ay), X(bx), Y(by)], fill=col + (255,), width=w)
        r = rad * S
        for (px, py) in ((ax, ay), (bx, by)):
            d.ellipse([X(px) - r, Y(py) - r, X(px) + r, Y(py) + r], fill=col + (255,))
        hw = max(2, int(w * 0.28))
        d.line([X(ax), Y(ay), X(bx), Y(by)], fill=hi + (255,), width=hw)
        for (px, py) in ((ax, ay), (bx, by)):
            d.ellipse([X(px) - hw / 2, Y(py) - hw / 2, X(px) + hw / 2, Y(py) + hw / 2], fill=hi + (255,))

    def full(self):
        """Весь фон этапа одной картинкой (≈90 МБ), из неё каждый кадр — resize окна."""
        if getattr(self, "_full", None) is None:
            nt = int(math.ceil((self.y_bot - Y_TOP) / TILE))
            arr = np.empty((nt * TILE, WX1 - WX0, 3), np.uint8)
            for ti in range(nt):
                arr[ti * TILE:(ti + 1) * TILE] = self.tile(ti)
                self.tiles.pop(ti, None)
            self._full = Image.fromarray(arr)
            self._fullh = nt * TILE
        return self._full

    def background(self, cy, s):
        """Окно камеры (центр x=500) → RGB 1440×1080."""
        big = self.full()
        vw, vh = VIEW_W / s, H / s
        x0 = 500 - vw / 2
        y0 = cy - vh / 2
        bx0, by0 = x0 - WX0, y0 - Y_TOP
        bx0 = min(max(bx0, 0), big.size[0] - vw)
        by0 = min(max(by0, 0), big.size[1] - vh)
        im = big.resize((VIEW_W, H), Image.BILINEAR, box=(bx0, by0, bx0 + vw, by0 + vh))
        return im, bx0 + WX0, by0 + Y_TOP

    # ------------------------------------------------ динамические тела
    def body_sprite(self, bi, level=0):
        key = (bi, level)
        if key in self.sprites:
            return self.sprites[key]
        b = self.T.bodies[bi]
        th = self.th
        if b.look == "ring":
            col = th["rings"][b.ring_idx % len(th["rings"])]
            col = mix(col, (255, 255, 255), [0, 0.3, 0.55, 0.8][level])
        elif b.look == "flap":
            col = th["flap"]
        else:
            col = th["spin"]
        ext = 0
        for (ax, ay, bx, by, rad, kind) in b.segs:
            ext = max(ext, math.hypot(ax, ay) + rad, math.hypot(bx, by) + rad)
        half = int(ext + 18)
        S = 2
        size = 2 * half
        lay = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for (ax, ay, bx, by, rad, kind) in b.segs:
            self._capsule(d, ax, ay, bx, by, rad, col, kind if kind != 3 else 1, -half, -half, S)
        if b.look == "ring" and level > 0:
            rr = random_state(bi * 7 + level)
            for _ in range(6 * level):
                a = rr.uniform(0, 2 * math.pi)
                R0 = b.ring_r
                px, py = (half + R0 * math.cos(a)) * S, (half + R0 * math.sin(a)) * S
                pts = [(px, py)]
                for _k in range(3):
                    px += rr.uniform(-9, 9) * S
                    py += rr.uniform(-9, 9) * S
                    pts.append((px, py))
                d.line(pts, fill=(30, 10, 10, 230), width=3 * S)
        lay = lay.resize((size, size), Image.LANCZOS)
        glow = Image.new("RGBA", (size // 2, size // 2), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for (ax, ay, bx, by, rad, kind) in b.segs:
            X = lambda v: (v + half) / 2
            gd.line([X(ax), X(ay), X(bx), X(by)], fill=col + (150,), width=int((rad * 2 + 16) / 2))
        glow = glow.filter(ImageFilter.GaussianBlur(5)).resize((size, size), Image.BILINEAR)
        spr = Image.alpha_composite(glow, lay)
        self.sprites[key] = (spr, half)
        return spr, half

    def body_sprite_scaled(self, bi, level, s):
        sq = round(s * 50) / 50
        key = (bi, level, sq)
        if key not in self.sprite_scaled:
            spr, half = self.body_sprite(bi, level)
            n = max(4, int(round(spr.size[0] * sq)))
            self.sprite_scaled[key] = (spr.resize((n, n), Image.LANCZOS), half * sq)
            if len(self.sprite_scaled) > 200:
                self.sprite_scaled.pop(next(iter(self.sprite_scaled)))
        return self.sprite_scaled[key]


def random_state(seed):
    import random
    return random.Random(seed)


def paste_center(img, spr, cx, cy):
    w, h = spr.size
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    W_, H_ = img.size
    if x >= W_ or y >= H_ or x + w <= 0 or y + h <= 0:
        return
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(w, W_ - x), min(h, H_ - y)
    part = spr.crop((sx0, sy0, sx1, sy1))
    img.paste(part, (x + sx0, y + sy0), part)


def text_center(d, cx, y, s, f, fill, stroke=0, sfill=(0, 0, 0)):
    w = d.textlength(s, font=f)
    d.text((cx - w / 2, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
