"""Оформление канала «Живые строки»: аватар 800×800, шапка 2560×1440, водяной знак 150×150.
Рисуется тем же акварельным движком, что и ролики."""
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter, zoom

sys.path.insert(0, "/home/claude/quotes")
import quotecard as qc  # noqa: E402

OUT = "/home/claude/quotes/brand"


def noise(h, w, scale, seed):
    r = np.random.default_rng(seed)
    small = r.random((h // scale + 3, w // scale + 3)).astype(np.float32)
    big = zoom(small, scale, order=3)[:h, :w]
    big -= big.min()
    big /= max(1e-6, big.max())
    return big


def paper(w, h, seed=1):
    hgt = 0.55 * noise(h, w, 3, seed) + 0.3 * noise(h, w, 9, seed + 1) + 0.15 * noise(h, w, 30, seed + 2)
    hgt = gaussian_filter(hgt, 0.7)
    gx, gy = np.gradient(hgt)
    shade = np.clip(1 + 1.1 * (-gy - gx), 0.965, 1.035)
    base = np.stack([0.972 + 0 * hgt, 0.960 + 0 * hgt, 0.930 + 0 * hgt], -1) * (0.975 + 0.025 * noise(h, w, 40, seed + 3))[..., None]
    return base.astype(np.float32), shade.astype(np.float32), (1 - hgt).astype(np.float32)


def blot(canvas, valley, cx, cy, R, col, dens, seed, soft=1.0, wob=0.3):
    """Акварельное пятно с неровным краем и тёмной каймой."""
    h, w = canvas.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot(xx - cx, yy - cy)
    th = np.arctan2(yy - cy, xx - cx)
    r = np.random.default_rng(seed)
    wb = sum(r.uniform(0.03, 0.07) * np.sin(k * th + r.uniform(0, 6.28)) for k in (1, 2, 3))
    wb += wob * (noise(h, w, max(8, int(R / 4)), seed) - 0.5) + 0.1 * (noise(h, w, 10, seed + 7) - 0.5)
    rr = R * (1 + wb)
    m = np.clip((rr - d) / ((6 + 0.12 * R) * soft), 0, 1)
    core = 0.6 + 0.4 * np.exp(-d / max(R, 1) * 1.5)
    ring = np.exp(-((rr - d) / (5 + 0.03 * R)) ** 2) * 0.35
    tex = 0.8 + 0.3 * noise(h, w, max(10, int(R / 3)), seed + 1)
    a = np.clip(m * core * dens * tex + ring * m, 0, 1)
    a = np.clip(a * (0.88 + 0.24 * valley), 0, 1)
    canvas *= 1 - a[..., None] * (1 - np.asarray(col, np.float32))


def finish(canvas, shade):
    out = canvas * shade[..., None]
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def avatar():
    S = 800
    canvas, shade, valley = paper(S, S, 11)
    # тёплый рассвет: небо, солнце, вода — в круге
    blot(canvas, valley, 400, 330, 310, (0.70, 0.78, 0.94), 0.8, 21, soft=2.0)
    blot(canvas, valley, 400, 450, 260, (0.98, 0.74, 0.58), 0.75, 22, soft=2.0)
    blot(canvas, valley, 370, 430, 140, (0.99, 0.86, 0.56), 0.8, 23, soft=2.5)
    # линия горизонта-холмы
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    ridge = 470 - 40 * np.abs(np.sin(xx / 90 + 0.8)) - 15 * np.sin(xx / 31)
    hill = np.clip((yy - ridge) / 2.5, 0, 1) * np.clip((560 - yy) / 40, 0, 1) * (np.hypot(xx - 400, yy - 400) < 330)
    hill = gaussian_filter(hill.astype(np.float32), 1.2) * 0.82
    canvas *= 1 - hill[..., None] * (1 - np.array([0.48, 0.52, 0.72], np.float32))
    img = finish(canvas, shade)
    d = ImageDraw.Draw(img, "RGBA")
    # солнце
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([360 - 70, 430 - 70, 360 + 70, 430 + 70], fill=(255, 250, 230, 200))
    img.paste(glow.filter(ImageFilter.GaussianBlur(26)), (0, 0), glow.filter(ImageFilter.GaussianBlur(26)))
    d.ellipse([360 - 30, 430 - 30, 360 + 30, 430 + 30], fill=(255, 253, 244, 245))
    # перо над рассветом — универсальный знак без букв
    import math as _m
    pts_l, pts_r = [], []
    x0, y0, x1, y1 = 585, 110, 425, 575          # от кончика опахала к кончику пера
    for k in range(41):
        t = k / 40
        x = x0 + (x1 - x0) * t + 40 * _m.sin(_m.pi * t) * 0.6
        y = y0 + (y1 - y0) * t
        w = (0 if t > 0.86 else 58 * _m.sin(_m.pi * min(1, t / 0.86)) ** 0.8)
        nx, ny = (y1 - y0), -(x1 - x0)
        L = _m.hypot(nx, ny)
        nx, ny = nx / L, ny / L
        pts_l.append((x + nx * w * 0.55, y + ny * w * 0.55))
        pts_r.append((x - nx * w, y - ny * w))
    d.polygon(pts_l + pts_r[::-1], fill=(58, 50, 62, 235))
    # стержень и бородки
    d.line([(x0 + 4, y0 + 6), (x1, y1)], fill=(236, 228, 214, 230), width=4)
    for k in range(6, 34, 3):
        t = k / 40
        x = x0 + (x1 - x0) * t + 40 * _m.sin(_m.pi * t) * 0.6
        y = y0 + (y1 - y0) * t
        d.line([(x, y), (x - 34 * (1 - t), y - 10)], fill=(236, 228, 214, 110), width=2)
    d.polygon([(x1 - 9, y1 - 18), (x1 + 9, y1 - 14), (x1 - 2, y1 + 22)], fill=(40, 34, 44, 255))
    img.save(f"{OUT}/avatar_800.png")
    # превью в круге, как увидит YouTube
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, S - 1, S - 1], fill=255)
    circ = Image.new("RGB", (S, S), (255, 255, 255))
    circ.paste(img, (0, 0), mask)
    circ.resize((200, 200), Image.LANCZOS).save(f"{OUT}/avatar_preview.png")
    return img


def banner():
    W, H = 2560, 1440
    canvas, shade, valley = paper(W, H, 31)
    # мягкая акварельная панорама по всей ширине: небо, холмы, вода
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    hor = 905
    sky = np.clip((hor - yy) / (hor - 200), 0, 1)
    sky_col = np.stack([0.72 + 0.26 * (1 - sky), 0.80 + 0.06 * (1 - sky), 0.93 - 0.25 * (1 - sky)], -1)
    edge = (noise(H, W, 40, 41) - 0.5) * 60
    a_sky = np.clip((yy - (240 + edge)) / 30, 0, 1) * np.clip((hor + 4 - yy) / 3, 0, 1) * 0.62
    a_sky *= 0.85 + 0.3 * noise(H, W, 90, 42)
    canvas[:] = canvas * (1 - a_sky[..., None] * (1 - sky_col))
    for j, (cx, cy, R, c) in enumerate(((520, 700, 420, (0.97, 0.70, 0.68)), (2050, 720, 460, (0.99, 0.80, 0.56)),
                                       (1280, 520, 460, (0.84, 0.86, 0.95)))):
        blot(canvas, valley, cx, cy, R, c, 0.3, 50 + j, soft=2.4)
    far = hor - 25 - 50 * np.abs(np.sin(xx / 330 + 1.0)) - 16 * np.sin(xx / 97)
    a_far = np.clip((yy - far) / 2.5, 0, 1) * np.clip((hor - yy) / 2, 0, 1) * 0.58
    canvas[:] = canvas * (1 - a_far[..., None] * (1 - np.array([0.66, 0.70, 0.86], np.float32)))
    near = hor - 8 - 22 * np.abs(np.sin(xx / 210 + 2.6)) - 8 * np.sin(xx / 61)
    a_near = np.clip((yy - near) / 2, 0, 1) * np.clip((hor - yy) / 2, 0, 1) * 0.78
    canvas[:] = canvas * (1 - a_near[..., None] * (1 - np.array([0.46, 0.51, 0.72], np.float32)))
    wat = np.clip((yy - hor) / 2, 0, 1) * np.clip((H - 140 + edge * 0.6 - yy) / 30, 0, 1)
    wcol = np.stack([0.98 - 0.3 * (yy - hor) / (H - hor), 0.88 - 0.12 * (yy - hor) / (H - hor), 0.74 + 0.18 * (yy - hor) / (H - hor)], -1)
    streak = gaussian_filter(np.random.default_rng(5).random((H, W)).astype(np.float32), (0.8, 9))
    streak = (streak - streak.min()) / (streak.max() - streak.min())
    a_w = wat * 0.6 * (0.75 + 0.5 * streak)
    canvas[:] = canvas * (1 - a_w[..., None] * (1 - wcol))
    refl = (2 * hor - far)
    a_r = np.clip((refl - yy) / 3, 0, 1) * np.clip((yy - hor - 3) / 2, 0, 1) * 0.25 * (0.6 + 0.8 * streak)
    canvas[:] = canvas * (1 - a_r[..., None] * (1 - np.array([0.62, 0.66, 0.84], np.float32)))
    img = finish(canvas, shade)
    d = ImageDraw.Draw(img, "RGBA")
    # солнце и дорожка
    sx, sy = 2290, hor - 48
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([sx - 120, sy - 120, sx + 120, sy + 120], fill=(255, 248, 225, 210))
    g = glow.filter(ImageFilter.GaussianBlur(40))
    img.paste(g, (0, 0), g)
    d.ellipse([sx - 44, sy - 44, sx + 44, sy + 44], fill=(255, 253, 245, 240))
    rnd = np.random.default_rng(3)
    for j in range(16):
        y = hor + 20 + j * 26
        hw = 30 + j * 16
        x0 = sx + rnd.uniform(-hw * 0.4, hw * 0.4)
        ln = rnd.uniform(0.3, 0.7) * hw
        d.line([(x0 - ln, y), (x0 + ln, y)], fill=(255, 252, 244, int(rnd.uniform(120, 210))), width=5)
    for bx, by, s in ((300, 600, 18), (355, 635, 14), (2330, 560, 16), (2395, 590, 12)):
        d.line([(bx - s, by + 2), (bx - s * 0.5, by - s * 0.45), (bx, by + 1), (bx + s * 0.5, by - s * 0.45), (bx + s, by + 2)],
               fill=(80, 78, 98, 220), width=4, joint="curve")
    # текст — в безопасной зоне 1546×423 по центру
    d = ImageDraw.Draw(img, "RGBA")
    f1 = qc.font(qc.F_RU, 100)
    f2 = qc.font(qc.F_EN, 58, 500)
    t1, t2 = "Живые строки · Living Lines", "мысли классиков на акварели  ·  timeless words on watercolor"
    y = 545
    d.text(((W - d.textlength(t1, font=f1)) / 2, y), t1, font=f1, fill=(46, 38, 34, 255))
    d.text(((W - d.textlength(t2, font=f2)) / 2, y + 140), t2, font=f2, fill=(98, 82, 72, 255))
    img.save(f"{OUT}/banner_2560x1440.jpg", quality=92)
    # превью: как видно на телефоне (центр 1546×423) и на ПК (2560×423)
    tv = img.resize((640, 360), Image.LANCZOS)
    dr = ImageDraw.Draw(tv, "RGBA")
    dr.rectangle([(640 - 1546 / 4) / 2, (360 - 423 / 4) / 2, (640 + 1546 / 4) / 2, (360 + 423 / 4) / 2], outline=(220, 40, 40, 255), width=2)
    dr.rectangle([0, (360 - 423 / 4) / 2, 639, (360 + 423 / 4) / 2], outline=(40, 120, 220, 255), width=2)
    tv.save(f"{OUT}/banner_zones.png")
    img.crop((int((W - 1546) / 2), int((H - 423) / 2), int((W + 1546) / 2), int((H + 423) / 2))).save(f"{OUT}/banner_phone_view.png")
    return img


def watermark():
    S = 300
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([6, 6, S - 6, S - 6], fill=(250, 246, 238, 235), outline=(170, 140, 90, 255), width=8)
    f = qc.font(qc.F_RU, 120)
    s = "ЖС"
    w = d.textlength(s, font=f)
    d.text(((S - w) / 2, 70), s, font=f, fill=(52, 44, 40, 255))
    img.resize((150, 150), Image.LANCZOS).save(f"{OUT}/watermark_150.png")


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    avatar()
    banner()
    watermark()
    print("ok")
