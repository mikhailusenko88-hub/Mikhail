"""Рисованные тематические картинки для роликов «Почему так» (PIL, без внешних файлов).

pick(text) -> имя картинки по ключевым словам; draw(name, size, color) -> RGBA с мягким свечением.
"""
import math

from PIL import Image, ImageDraw, ImageFilter

KEYS = [
    ("planet", "планет венер меркур сатурн юпитер марс космос орбит галакт"),
    ("sun", "солнц звезд светил"),
    ("moon", "луна= луны= луне= луну= лунн месяц"),
    ("bolt", "молни электр ток разряд гроз"),
    ("wave", "океан море волн вода тонет плав рыб кит акул"),
    ("snow", "лёд лед снег холод мороз замерз айсберг"),
    ("flame", "огонь горяч жар пламя температур вулкан лава"),
    ("heart", "сердц кровь пульс сосуд"),
    ("dna", "днк ген клетк наследств хромосом"),
    ("brain", "мозг памят мысл нейрон сон спать спящ лунатик"),
    ("eye", "глаз зрен вид слеп смотр цвет"),
    ("paw", "животн кошк собак лев тигр медвед слон страус летуч мыш хамелеон зме птиц прыга бык жираф"),
    ("leaf", "растен дерев лист цвет трав корен банан"),
    ("apple", "еда ест пищ сладк фрукт яблок лук сахар шоколад"),
    ("atom", "атом физик химик молекул радиоакт электрон"),
    ("clock", "врем сутк час минут секунд год лет день"),
    ("globe", "земл матери стран мир географ стена пирамид гор эверест"),
    ("bone", "кост скелет зуб череп волос ногт тело рост смерт"),
    ("rainbow", "радуг спектр призм"),
    ("rocket", "ракет полёт полет самолёт самолет скорост быстр"),
]


def pick(text):
    import re
    t = (text or "").lower()
    best, score = "question", 0
    for name, words in KEYS:
        s = sum(len(re.findall(r"(?<![а-яa-z])" + w.rstrip("=") + (r"(?![а-яa-z])" if w.endswith("=") else ""), t)) for w in words.split())
        if s > score:
            best, score = name, s
    return best


def _canvas(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _poly(cx, cy, r, n, rot=0.0):
    return [(cx + r * math.cos(rot + 2 * math.pi * k / n), cy + r * math.sin(rot + 2 * math.pi * k / n)) for k in range(n)]


def _star(cx, cy, r1, r2, n=5, rot=-math.pi / 2):
    pts = []
    for k in range(2 * n):
        r = r1 if k % 2 == 0 else r2
        a = rot + math.pi * k / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_icon(name, size, col, line=None):
    """Контурная картинка цветом col (RGB) на прозрачном фоне."""
    im, d = _canvas(size)
    s = size
    c = s / 2
    lw = line or max(8, s // 28)
    C = col + (255,)
    F = col + (70,)
    if name == "planet":
        d.ellipse([c - s * 0.26, c - s * 0.26, c + s * 0.26, c + s * 0.26], outline=C, width=lw, fill=F)
        ring = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.ellipse([c - s * 0.46, c - s * 0.13, c + s * 0.46, c + s * 0.13], outline=C, width=lw)
        ring = ring.rotate(-22, resample=Image.BICUBIC)
        im.alpha_composite(ring)
        d.ellipse([c - s * 0.1, c - s * 0.14, c + s * 0.02, c - s * 0.04], fill=col + (140,))
    elif name == "sun":
        d.ellipse([c - s * 0.2, c - s * 0.2, c + s * 0.2, c + s * 0.2], outline=C, width=lw, fill=F)
        for k in range(12):
            a = 2 * math.pi * k / 12
            d.line([(c + s * 0.28 * math.cos(a), c + s * 0.28 * math.sin(a)),
                    (c + s * 0.42 * math.cos(a), c + s * 0.42 * math.sin(a))], fill=C, width=lw)
    elif name == "moon":
        d.ellipse([c - s * 0.32, c - s * 0.32, c + s * 0.32, c + s * 0.32], fill=C)
        hole = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(hole).ellipse([c - s * 0.18, c - s * 0.42, c + s * 0.42, c + s * 0.18], fill=(0, 0, 0, 255))
        r, g, b, a = im.split()
        from PIL import ImageChops
        a = ImageChops.subtract(a, hole.split()[3])
        im = Image.merge("RGBA", (r, g, b, a))
        d = ImageDraw.Draw(im)
        for x, y, rr in ((0.72, 0.3, 0.035), (0.8, 0.5, 0.02), (0.66, 0.62, 0.025)):
            d.ellipse([s * x - s * rr, s * y - s * rr, s * x + s * rr, s * y + s * rr], fill=C)
    elif name == "bolt":
        pts = [(0.58, 0.08), (0.3, 0.55), (0.48, 0.55), (0.4, 0.92), (0.72, 0.42), (0.54, 0.42), (0.64, 0.08)]
        d.polygon([(x * s, y * s) for x, y in pts], fill=F, outline=C, width=lw)
    elif name == "wave":
        for j in range(3):
            y0 = s * (0.32 + 0.18 * j)
            pts = [(x, y0 + s * 0.06 * math.sin(x / s * 4 * math.pi + j)) for x in range(int(s * 0.08), int(s * 0.92), 4)]
            d.line(pts, fill=C, width=lw, joint="curve")
        for x, y, rr in ((0.3, 0.2, 0.03), (0.42, 0.14, 0.02), (0.36, 0.08, 0.015)):
            d.ellipse([s * x - s * rr, s * y - s * rr, s * x + s * rr, s * y + s * rr], outline=C, width=max(3, lw // 2))
    elif name == "snow":
        for k in range(6):
            a = math.pi * k / 3
            dx, dy = math.cos(a), math.sin(a)
            d.line([(c, c), (c + s * 0.42 * dx, c + s * 0.42 * dy)], fill=C, width=lw)
            for t in (0.22, 0.32):
                px, py = c + s * t * dx, c + s * t * dy
                for sgn in (1, -1):
                    b = a + sgn * math.pi / 3
                    d.line([(px, py), (px + s * 0.09 * math.cos(b), py + s * 0.09 * math.sin(b))], fill=C, width=lw)
    elif name == "flame":
        pts = []
        for k in range(60):
            t = k / 59
            a = math.pi * t
            x = c + s * 0.3 * math.sin(a) * (1 - 0.5 * t) * (1 if k % 2 == 0 else 1)
            y = s * 0.9 - s * 0.8 * t
            pts.append((x, y))
        left = [(c - (x - c), y) for x, y in reversed(pts)]
        d.polygon(pts + left, fill=F, outline=C, width=lw)
        d.ellipse([c - s * 0.12, s * 0.55, c + s * 0.12, s * 0.85], fill=C)
    elif name == "heart":
        pts = []
        for k in range(200):
            t = 2 * math.pi * k / 200
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((c + x * s * 0.026, c - y * s * 0.026 + s * 0.02))
        d.polygon(pts, fill=F, outline=C, width=lw)
        # пульс
        zig = [(0.12, 0.52), (0.32, 0.52), (0.38, 0.38), (0.46, 0.66), (0.54, 0.44), (0.6, 0.52), (0.88, 0.52)]
        d.line([(x * s, y * s) for x, y in zig], fill=C, width=lw)
    elif name == "dna":
        a1, a2 = [], []
        for y in range(int(s * 0.08), int(s * 0.92), 3):
            ph = y / s * 2.2 * math.pi
            a1.append((c + s * 0.26 * math.sin(ph), y))
            a2.append((c - s * 0.26 * math.sin(ph), y))
        d.line(a1, fill=C, width=lw, joint="curve")
        d.line(a2, fill=C, width=lw, joint="curve")
        for y in range(int(s * 0.12), int(s * 0.92), int(s * 0.1)):
            ph = y / s * 2.2 * math.pi
            d.line([(c + s * 0.26 * math.sin(ph), y), (c - s * 0.26 * math.sin(ph), y)], fill=col + (170,), width=max(4, lw // 2))
    elif name == "brain":
        d.ellipse([c - s * 0.34, c - s * 0.28, c + s * 0.02, c + s * 0.26], outline=C, width=lw, fill=F)
        d.ellipse([c - s * 0.02, c - s * 0.28, c + s * 0.34, c + s * 0.26], outline=C, width=lw, fill=F)
        d.line([(c, c - s * 0.26), (c, c + s * 0.24)], fill=C, width=lw)
        for x0, y0 in ((-0.2, -0.08), (0.12, -0.12), (-0.14, 0.1), (0.16, 0.08)):
            d.arc([c + s * x0 - s * 0.07, c + s * y0 - s * 0.07, c + s * x0 + s * 0.07, c + s * y0 + s * 0.07], 200, 340, fill=C, width=max(4, lw // 2))
    elif name == "eye":
        pts = [(c - s * 0.44 + (s * 0.88) * k / 80, c - s * 0.26 * math.sin(math.pi * k / 80)) for k in range(81)]
        pts += [(c + s * 0.44 - (s * 0.88) * k / 80, c + s * 0.26 * math.sin(math.pi * k / 80)) for k in range(81)]
        d.polygon(pts, outline=C, width=lw, fill=F)
        d.ellipse([c - s * 0.15, c - s * 0.15, c + s * 0.15, c + s * 0.15], fill=C)
        d.ellipse([c - s * 0.05, c - s * 0.1, c + s * 0.03, c - s * 0.02], fill=(255, 255, 255, 230))
    elif name == "paw":
        d.ellipse([c - s * 0.2, c - s * 0.02, c + s * 0.2, c + s * 0.32], fill=C)
        for x, y, r in ((-0.27, -0.14, 0.085), (-0.1, -0.26, 0.085), (0.1, -0.26, 0.085), (0.27, -0.14, 0.085)):
            d.ellipse([c + s * x - s * r, c + s * y - s * r, c + s * x + s * r, c + s * y + s * r], fill=C)
    elif name == "leaf":
        pts = [(c - s * 0.3 + s * 0.6 * k / 60, c + s * 0.3 * math.sin(math.pi * k / 60) - s * 0.3 * (k / 60) + s * 0.15) for k in range(61)]
        pts += [(c + s * 0.3 - s * 0.6 * k / 60, c - s * 0.3 * math.sin(math.pi * k / 60) - s * 0.3 * (1 - k / 60) + s * 0.15) for k in range(61)]
        d.polygon(pts, outline=C, width=lw, fill=F)
        d.line([(c - s * 0.28, c + s * 0.42), (c + s * 0.3, c - s * 0.16)], fill=C, width=lw)
    elif name == "apple":
        d.ellipse([c - s * 0.3, c - s * 0.18, c + s * 0.04, c + s * 0.34], outline=C, width=lw, fill=F)
        d.ellipse([c - s * 0.04, c - s * 0.18, c + s * 0.3, c + s * 0.34], outline=C, width=lw, fill=F)
        d.line([(c, c - s * 0.16), (c + s * 0.06, c - s * 0.36)], fill=C, width=lw)
        d.ellipse([c + s * 0.05, c - s * 0.4, c + s * 0.22, c - s * 0.28], fill=C)
    elif name == "atom":
        d.ellipse([c - s * 0.06, c - s * 0.06, c + s * 0.06, c + s * 0.06], fill=C)
        for ang in (0, 60, 120):
            ring = Image.new("RGBA", (s, s), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse([c - s * 0.44, c - s * 0.16, c + s * 0.44, c + s * 0.16], outline=C, width=lw)
            im.alpha_composite(ring.rotate(ang, resample=Image.BICUBIC))
        d = ImageDraw.Draw(im)
    elif name == "clock":
        d.ellipse([c - s * 0.4, c - s * 0.4, c + s * 0.4, c + s * 0.4], outline=C, width=lw, fill=F)
        for k in range(12):
            a = 2 * math.pi * k / 12
            d.line([(c + s * 0.33 * math.cos(a), c + s * 0.33 * math.sin(a)), (c + s * 0.37 * math.cos(a), c + s * 0.37 * math.sin(a))], fill=C, width=max(4, lw // 2))
        d.line([(c, c), (c, c - s * 0.26)], fill=C, width=lw)
        d.line([(c, c), (c + s * 0.18, c + s * 0.1)], fill=C, width=lw)
    elif name == "globe":
        d.ellipse([c - s * 0.4, c - s * 0.4, c + s * 0.4, c + s * 0.4], outline=C, width=lw, fill=F)
        d.ellipse([c - s * 0.16, c - s * 0.4, c + s * 0.16, c + s * 0.4], outline=C, width=max(4, lw // 2))
        d.line([(c - s * 0.4, c), (c + s * 0.4, c)], fill=C, width=max(4, lw // 2))
        d.arc([c - s * 0.4, c - s * 0.62, c + s * 0.4, c - s * 0.1], 20, 160, fill=C, width=max(4, lw // 2))
        d.arc([c - s * 0.4, c + s * 0.1, c + s * 0.4, c + s * 0.62], 200, 340, fill=C, width=max(4, lw // 2))
    elif name == "bone":
        d.line([(c - s * 0.24, c + s * 0.24), (c + s * 0.24, c - s * 0.24)], fill=C, width=lw * 2)
        for x, y in ((-0.3, 0.18), (-0.18, 0.3), (0.3, -0.18), (0.18, -0.3)):
            d.ellipse([c + s * x - s * 0.1, c + s * y - s * 0.1, c + s * x + s * 0.1, c + s * y + s * 0.1], fill=C)
    elif name == "rainbow":
        cols = [(255, 70, 70), (255, 160, 40), (250, 230, 60), (80, 200, 90), (70, 150, 255), (150, 90, 230)]
        for j, cc in enumerate(cols):
            r = s * (0.46 - 0.05 * j)
            d.arc([c - r, c + s * 0.2 - r, c + r, c + s * 0.2 + r], 180, 360, fill=cc + (255,), width=int(s * 0.045))
    elif name == "rocket":
        body = [(0.5, 0.06), (0.64, 0.26), (0.66, 0.62), (0.34, 0.62), (0.36, 0.26)]
        d.polygon([(x * s, y * s) for x, y in body], fill=F, outline=C, width=lw)
        d.polygon([(0.34 * s, 0.44 * s), (0.2 * s, 0.7 * s), (0.34 * s, 0.62 * s)], fill=C)
        d.polygon([(0.66 * s, 0.44 * s), (0.8 * s, 0.7 * s), (0.66 * s, 0.62 * s)], fill=C)
        d.ellipse([0.44 * s, 0.3 * s, 0.56 * s, 0.42 * s], fill=C)
        d.polygon([(0.42 * s, 0.64 * s), (0.58 * s, 0.64 * s), (0.5 * s, 0.9 * s)], fill=col + (180,))
    else:  # question
        d.arc([c - s * 0.22, c - s * 0.4, c + s * 0.22, c + s * 0.02], 180, 400, fill=C, width=lw * 2)
        d.line([(c + s * 0.16, c - s * 0.08), (c, c + s * 0.1), (c, c + s * 0.22)], fill=C, width=lw * 2, joint="curve")
        d.ellipse([c - s * 0.06, c + s * 0.3, c + s * 0.06, c + s * 0.42], fill=C)
    return im


def draw(name, size, col):
    """Картинка со свечением под ней."""
    ic = draw_icon(name, size, col)
    glow = ic.filter(ImageFilter.GaussianBlur(size // 18))
    r, g, b, a = glow.split()
    a = a.point(lambda v: int(v * 0.8))
    glow = Image.merge("RGBA", (r, g, b, a))
    return Image.alpha_composite(glow, ic)


if __name__ == "__main__":
    names = [k for k, _ in KEYS] + ["question"]
    sheet = Image.new("RGB", (5 * 300, ((len(names) + 4) // 5) * 300), (18, 22, 34))
    for i, n in enumerate(names):
        sheet.paste(draw(n, 260, (255, 200, 80)), (20 + (i % 5) * 300, 20 + (i // 5) * 300), draw(n, 260, (255, 200, 80)))
    sheet.save("/tmp/icons_sheet.png")
    print("ok", len(names))
