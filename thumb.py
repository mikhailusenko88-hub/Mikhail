"""Обложка 1280×720 для ролика: кольца, из которых вылетают шарики-флаги, и крупный текст."""
import json
import math
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import countries
import render
from render import font, mix

W, H = 1280, 720


def make(codes, race_no, out, final=False):
    rr = random.Random(race_no)
    th = render.THEMES[race_no % (len(render.THEMES) - 1)] if not final else render.THEMES[-1]
    g = np.linspace(0, 1, H)[:, None, None]
    a, b = np.array(th["bg0"], np.float32), np.array(th["bg1"], np.float32) * 1.6
    arr = np.repeat(a + (b - a) * g, W, 1)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    S = 2
    lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0))
    d, gd = ImageDraw.Draw(lay), ImageDraw.Draw(glow)
    cx, cy = 400, 380
    for i, (R, gap, rot) in enumerate([(130, 40, 20), (205, 34, 150), (280, 30, 260)]):
        col = th["rings"][i]
        a0, a1 = rot + gap / 2, rot + 360 - gap / 2
        d.arc([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], a0, a1, fill=col + (255,), width=16 * S)
        gd.arc([(cx - R) / 2, (cy - R) / 2, (cx + R) / 2, (cy + R) / 2], a0, a1, fill=col + (200,), width=14)
    lay = lay.resize((W, H), Image.LANCZOS)
    glow = glow.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    img.paste(glow, (0, 0), glow)
    img.paste(lay, (0, 0), lay)
    # шарики: часть внутри, часть вылетает
    pts = []
    for k, c in enumerate(codes[:22]):
        for _ in range(600):
            if k < 9:
                ang, dist = rr.uniform(0, 6.28), rr.uniform(0, 88)
                r = 27
            else:
                ang, dist = rr.uniform(-2.6, 0.9), rr.uniform(300, 520)
                r = rr.choice([40, 46, 52])
            x, y = cx + dist * math.cos(ang), cy + dist * math.sin(ang)
            if not (40 < x < 760 and 40 < y < 690) or (x < 200 and y < 130):
                continue
            if all(math.hypot(x - px, y - py) > r + pr + 4 for px, py, pr, _ in pts):
                pts.append((x, y, r, c))
                break
    for (x, y, r, c) in sorted(pts, key=lambda p: p[2]):
        spr = render.ball_sprite(c, r, rr.uniform(-0.6, 0.6))
        render.paste_center(img, spr, x, y)
    dr = ImageDraw.Draw(img)
    x0 = 790
    if final:
        dr.text((x0, 70), "MONTH", font=font(96), fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
        dr.text((x0, 170), "FINAL", font=font(150), fill=render.THEMES[-1]["wall"], stroke_width=8, stroke_fill=(0, 0, 0))
    else:
        dr.text((x0, 40), "32", font=font(230), fill=(255, 214, 64), stroke_width=9, stroke_fill=(0, 0, 0))
        dr.text((x0, 290), "COUNTRIES", font=font(84), fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    dr.text((x0, 410), "WHO", font=font(118), fill=(70, 235, 130), stroke_width=7, stroke_fill=(0, 0, 0))
    dr.text((x0, 545), "WINS?", font=font(118), fill=(70, 235, 130), stroke_width=7, stroke_fill=(0, 0, 0))
    tag = f"#{race_no}"
    dr.rounded_rectangle([20, 20, 40 + dr.textlength(tag, font=font(44)), 84], 14, fill=(235, 60, 70))
    dr.text((30, 22), tag, font=font(44), fill=(255, 255, 255))
    img.save(out, quality=92)


if __name__ == "__main__":
    meta = json.load(open(sys.argv[1]))
    a2 = {v: k for k, v in countries.A3.items()}
    codes = [a2[c] for c in meta["ranking"]]
    random.Random(meta["race_no"] * 3).shuffle(codes)   # не выдаём победителя
    make(codes, meta["race_no"], sys.argv[2], meta["kind"] == "final")
