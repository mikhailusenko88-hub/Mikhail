"""Обложка 1280×720: три самых «кликабельных» флага заезда лицом к лицу, большое VS, «WHO SURVIVES?»
и сколько выживает. Без спойлеров (кто выжил — не показываем)."""
import json
import math
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import countries
import popular
import render
from render import font

W, H = 1280, 720
GOLD = (255, 214, 64)
GREEN = (70, 235, 130)
RED = (235, 60, 70)
WHITE = (255, 255, 255)


def _bg(race_no, final):
    th = render.THEMES[race_no % (len(render.THEMES) - 1)] if not final else render.THEMES[-1]
    g = np.linspace(0, 1, H)[:, None, None]
    a, b = np.array(th["bg0"], np.float32), np.array(th["bg1"], np.float32) * 1.5
    arr = np.repeat(a + (b - a) * g, W, 1)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    # лучи из центра + лёгкая виньетка
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    cx, cy = 430, 360
    for k in range(18):
        a0 = k * 20
        rd.pieslice([cx - 1400, cy - 1400, cx + 1400, cy + 1400], a0, a0 + 7, fill=(255, 255, 255, 22))
    img = Image.alpha_composite(img, rays.filter(ImageFilter.GaussianBlur(3)))
    v = Image.new("L", (W, H), 0)
    ImageDraw.Draw(v).ellipse([-200, -150, W + 200, H + 150], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img = Image.composite(img, Image.alpha_composite(img, Image.new("RGBA", (W, H), (0, 0, 0, 110))), v)
    return img, th


def _ball_shadow(img, x, y, r):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([x - r, y - r + 18, x + r, y + r + 18], fill=(0, 0, 0, 150))
    return Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(14)))


def make(codes, race_no, out, final=False, n=32, surv=1, tag="", ranking=None, feat=None):
    rr = random.Random(race_no)
    img, th = _bg(race_no, final)
    feat = list(feat) if feat else popular.featured(codes, 3)
    # три шара: слева два по диагонали, справа один крупный — «лицом к лицу»
    layout = [(230, 300, 150), (470, 470, 125), (640, 250, 118)] if len(feat) == 3 else [(260, 330, 160), (600, 360, 160)]
    for (x, y, r), c in zip(layout, feat):
        img = _ball_shadow(img, x, y, r)
        spr = render.ball_sprite(c, r, rr.uniform(-0.5, 0.5))
        render.paste_center(img, spr, x, y)
    d = ImageDraw.Draw(img)
    # VS
    vx, vy = 455, 318
    d.ellipse([vx - 62, vy - 62, vx + 62, vy + 62], fill=(20, 20, 26, 235), outline=GOLD, width=6)
    render.text_center(d, vx, vy - 34, "VS", font(64), GOLD, 4)
    # мелкие флаги остальных — строкой снизу слева (ещё 8 стран), чтобы было видно масштаб
    rest = [c for c in codes if c not in feat]
    rr.shuffle(rest)
    for i, c in enumerate(rest[:9]):
        x = 60 + i * 76
        spr = render.ball_sprite(c, 30, 0)
        render.paste_center(img, spr, x, 650)
    if len(rest) > 9:
        render.text_center(d, 60 + 9 * 76 + 10, 632, f"+{len(rest) - 9}", font(40), WHITE, 4)
    # текст справа
    x0 = 790
    st = dict(stroke_fill=(0, 0, 0))
    if final:
        d.text((x0, 70), "GRAND", font=font(118), fill=WHITE, stroke_width=7, **st)
        d.text((x0, 195), "FINAL", font=font(150), fill=GOLD, stroke_width=8, **st)
        d.text((x0, 420), "WHO", font=font(110), fill=GREEN, stroke_width=7, **st)
        d.text((x0, 540), "WINS?", font=font(110), fill=GREEN, stroke_width=7, **st)
    else:
        d.text((x0, 60), "WHO", font=font(132), fill=WHITE, stroke_width=8, **st)
        d.text((x0, 205), "SURVIVES?", font=font(86), fill=WHITE, stroke_width=6, **st)
        d.rounded_rectangle([x0 - 10, 380, W - 30, 520], 24, fill=(0, 0, 0, 150), outline=RED, width=6)
        d.text((x0 + 14, 392), f"ONLY {surv}", font=font(100), fill=GREEN, stroke_width=6, **st)
        d.text((x0 + 14, 522), f"OF {n} COUNTRIES", font=font(52), fill=GOLD, stroke_width=4, **st)
        # красный крест — намёк на вылет
        d.line([W - 150, 600, W - 60, 690], fill=RED, width=18)
        d.line([W - 60, 600, W - 150, 690], fill=RED, width=18)
    if tag:
        d.rounded_rectangle([20, 20, 40 + d.textlength(tag, font=font(40)), 80], 14, fill=RED)
        d.text((30, 24), tag, font=font(40), fill=WHITE)
    img.convert("RGB").save(out, quality=92)


if __name__ == "__main__":
    meta = json.load(open(sys.argv[1]))
    a2 = {v: k for k, v in countries.A3.items()}
    codes = meta.get("codes") or [a2[c] for c in meta["ranking"]]
    if meta.get("final"):
        tag = f"SEASON {meta['season']}"
    else:
        rn = {1: "ROUND 1", 2: "ROUND 2", 3: "SEMI-FINAL"}[meta["round"]]
        tag = f"{rn} · {meta.get('heat_label') or f'HEAT {meta['heat']}/{meta['heats']}'}"
    make(codes, meta["race_no"], sys.argv[2], meta.get("final", False), meta.get("n", 32), meta.get("survive", 1), tag,
         feat=meta.get("featured"))
