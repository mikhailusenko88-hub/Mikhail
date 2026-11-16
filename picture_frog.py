"""Мордочка лягушки для «пыка»: глаза center / left / right / closed."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import shape_frog as S

W, H = S.W, S.H
CX, CY = S.CX, S.CY
SS = 2

GREEN = (96, 196, 66)
GREEN_L = (150, 226, 96)
BELLY = (196, 236, 132)
DARK = (34, 92, 30)
WHITE = (255, 255, 250)
PUPIL = (16, 18, 22)
CHEEK = (255, 132, 160)
EYES = [(CX - 205, CY - 262), (CX + 205, CY - 262)]
ER = 108


def P(*v):
    return [c * SS for c in v]


def base():
    im = Image.new("RGB", (W * SS, H * SS), GREEN)
    glow = Image.new("L", im.size, 0)
    ImageDraw.Draw(glow).ellipse(P(CX - 330, CY - 220, CX + 330, CY + 250), fill=170)
    glow = glow.filter(ImageFilter.GaussianBlur(110 * SS))
    im = Image.composite(Image.new("RGB", im.size, GREEN_L), im, glow)
    d = ImageDraw.Draw(im)
    d.ellipse(P(CX - 250, CY + 170, CX + 250, CY + 400), fill=BELLY)        # светлый подбородок
    for sgn in (-1, 1):
        d.ellipse(P(CX + sgn * 270 - 62, CY + 70, CX + sgn * 270 + 62, CY + 170), fill=CHEEK)  # щёчки
        d.ellipse(P(CX + sgn * 42 - 13, CY + 10, CX + sgn * 42 + 13, CY + 36), fill=DARK)       # ноздри
    # широкая улыбка
    d.arc(P(CX - 250, CY - 60, CX + 250, CY + 190), 22, 158, fill=DARK, width=24 * SS)
    return im


def eyes_open(im, look=0):
    d = ImageDraw.Draw(im)
    for ex, ey in EYES:
        d.ellipse(P(ex - ER - 12, ey - ER - 12, ex + ER + 12, ey + ER + 12), fill=DARK)
        d.ellipse(P(ex - ER, ey - ER, ex + ER, ey + ER), fill=WHITE)
        px = ex + look * 40
        d.ellipse(P(px - 50, ey - 50, px + 50, ey + 50), fill=PUPIL)
        d.ellipse(P(px - 40, ey - 40, px - 12, ey - 12), fill=(255, 255, 255))
    return im


def eyes_closed(im):
    d = ImageDraw.Draw(im)
    for ex, ey in EYES:
        d.ellipse(P(ex - ER - 12, ey - ER - 12, ex + ER + 12, ey + ER + 12), fill=GREEN)
        d.arc(P(ex - ER + 10, ey - ER + 10, ex + ER - 10, ey + ER - 30), 20, 160, fill=DARK, width=24 * SS)
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
        Image.fromarray(a.astype(np.uint8)).resize((360, 640)).save(f"/tmp/frog_{st}.png")
