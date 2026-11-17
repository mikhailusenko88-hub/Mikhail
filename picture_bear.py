"""Мордочка медведя для «пыка»: глаза center / left / right / closed."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import shape_bear as S

W, H = S.W, S.H
CX, CY = S.CX, S.CY
SS = 2
FUR = (176, 108, 58)
FUR_L = (214, 146, 84)
INNER = (236, 178, 140)
MUZZLE = (240, 208, 160)
DARK = (44, 26, 20)
WHITE = (255, 255, 250)
CHEEK = (255, 140, 150)
EYES = [(CX - 150, CY - 40), (CX + 150, CY - 40)]
ER = 58


def P(*v):
    return [c * SS for c in v]


def base():
    im = Image.new("RGB", (W * SS, H * SS), FUR)
    glow = Image.new("L", im.size, 0)
    ImageDraw.Draw(glow).ellipse(P(CX - 300, CY - 330, CX + 300, CY + 200), fill=160)
    glow = glow.filter(ImageFilter.GaussianBlur(110 * SS))
    im = Image.composite(Image.new("RGB", im.size, FUR_L), im, glow)
    d = ImageDraw.Draw(im)
    for sgn in (-1, 1):
        ex, ey, er = S.EARS[0 if sgn < 0 else 1]
        d.ellipse(P(ex - er * 0.58, ey - er * 0.58 + 8, ex + er * 0.58, ey + er * 0.58 + 8), fill=INNER)
        d.ellipse(P(CX + sgn * 255 - 52, CY + 90, CX + sgn * 255 + 52, CY + 160), fill=CHEEK)
    d.ellipse(P(CX - 185, CY + 60, CX + 185, CY + 330), fill=MUZZLE)
    d.rounded_rectangle(P(CX - 62, CY + 95, CX + 62, CY + 165), radius=34 * SS, fill=DARK)          # нос
    d.ellipse(P(CX - 38, CY + 104, CX - 6, CY + 124), fill=(120, 90, 80))                         # блик на носу
    d.line([tuple(P(CX, CY + 160)), tuple(P(CX, CY + 215))], fill=DARK, width=16 * SS)
    for sgn in (-1, 1):
        d.arc(P(CX + sgn * 50 - 52, CY + 170, CX + sgn * 50 + 52, CY + 262), 20, 160, fill=DARK, width=16 * SS)
    return im


def eyes_open(im, look=0):
    d = ImageDraw.Draw(im)
    for ex, ey in EYES:
        d.ellipse(P(ex - ER - 8, ey - ER - 8, ex + ER + 8, ey + ER + 8), fill=DARK)
        d.ellipse(P(ex - ER, ey - ER, ex + ER, ey + ER), fill=WHITE)
        px = ex + look * 20
        d.ellipse(P(px - 36, ey - 36, px + 36, ey + 36), fill=DARK)
        d.ellipse(P(px - 30, ey - 30, px - 8, ey - 8), fill=(255, 255, 255))
    return im


def eyes_closed(im):
    d = ImageDraw.Draw(im)
    for ex, ey in EYES:
        d.arc(P(ex - ER, ey - ER - 14, ex + ER, ey + ER - 14), 20, 160, fill=DARK, width=18 * SS)
    return im


def make(state):
    im = base()
    if state == "closed":
        eyes_closed(im)
    else:
        eyes_open(im, {"center": 0, "left": -1, "right": 1}[state])
    return np.asarray(im.resize((W, H), Image.LANCZOS)).astype(np.float32)


def sample(img, xs, ys, rad=5):
    out = np.zeros((len(xs), 3), np.float32)
    for i, (x, y) in enumerate(zip(xs, ys)):
        xi, yi = int(round(x)), int(round(y))
        out[i] = img[max(0, yi - rad):yi + rad + 1, max(0, xi - rad):xi + rad + 1].reshape(-1, 3).mean(0)
    return out


if __name__ == "__main__":
    f = S.field()
    for st in ("center", "closed"):
        a = make(st)
        a[f >= 0] = 0
        Image.fromarray(a.astype(np.uint8)).resize((360, 640)).save(f"/tmp/bear_{st}.png")
