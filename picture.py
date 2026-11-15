"""Мордочка кота для «пыка»: открытые глаза (центр / влево / вправо) и закрытые."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import shape as S

W, H = S.W, S.H
CX, CY = S.CX, S.CY
SS = 2  # рисуем вдвое крупнее

FUR = (240, 146, 52)
FUR_LIGHT = (252, 182, 92)
STRIPE = (178, 88, 28)
PINK = (246, 150, 168)
WHITE = (255, 248, 236)
IRIS = (120, 214, 70)
IRIS_DARK = (60, 150, 40)
PUPIL = (18, 16, 24)
LINE = (70, 34, 16)

EYE_Y = CY - 70
EYES = [CX - 168, CX + 168]
EW, EH = 172, 146


def P(*v):
    return [c * SS for c in v]


def base():
    im = Image.new("RGB", (W * SS, H * SS), FUR)
    d = ImageDraw.Draw(im)
    # светлее к центру лба
    glow = Image.new("L", im.size, 0)
    ImageDraw.Draw(glow).ellipse(P(CX - 300, CY - 360, CX + 300, CY + 200), fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(120 * SS))
    im = Image.composite(Image.new("RGB", im.size, FUR_LIGHT), im, glow)
    d = ImageDraw.Draw(im)
    # внутренняя часть ушей
    for sgn in (-1, 1):
        a = (CX + sgn * 268, CY - 250); b = (CX + sgn * 300, CY - 540); c = (CX + sgn * 140, CY - 340)
        d.polygon([tuple(P(*a)), tuple(P(*b)), tuple(P(*c))], fill=PINK)
    # полоски на лбу («М»)
    for dx, h in ((-70, 150), (0, 190), (70, 150)):
        d.rounded_rectangle(P(CX + dx - 17, CY - 400, CX + dx + 17, CY - 400 + h), radius=17 * SS, fill=STRIPE)
    # полоски на щеках
    for sgn in (-1, 1):
        for k, yy in enumerate((CY + 40, CY + 100)):
            x0 = CX + sgn * 300
            d.line([tuple(P(x0, yy)), tuple(P(x0 + sgn * 110, yy - 20 + 10 * k))], fill=STRIPE, width=30 * SS)
    # белая мордочка
    for sgn in (-1, 1):
        d.ellipse(P(CX + sgn * 62 - 98, CY + 70, CX + sgn * 62 + 98, CY + 250), fill=WHITE)
    d.ellipse(P(CX - 90, CY + 170, CX + 90, CY + 320), fill=WHITE)
    return im


def eyes_open(im, look=0):
    d = ImageDraw.Draw(im)
    for ex in EYES:
        box = P(ex - EW / 2, EYE_Y - EH / 2, ex + EW / 2, EYE_Y + EH / 2)
        d.ellipse([box[0] - 10 * SS, box[1] - 10 * SS, box[2] + 10 * SS, box[3] + 10 * SS], fill=LINE)
        d.ellipse(box, fill=IRIS)
        d.ellipse(P(ex - EW / 2 + 14, EYE_Y + 6, ex + EW / 2 - 14, EYE_Y + EH / 2 - 6), fill=IRIS_DARK)
        px = ex + look * 34
        d.ellipse(P(px - 30, EYE_Y - 60, px + 30, EYE_Y + 60), fill=PUPIL)
        d.ellipse(P(px - 46, EYE_Y - 46, px - 10, EYE_Y - 10), fill=(255, 255, 255))
    return im


def eyes_closed(im):
    d = ImageDraw.Draw(im)
    for ex in EYES:
        d.arc(P(ex - EW / 2, EYE_Y - EH / 2 - 10, ex + EW / 2, EYE_Y + EH / 2 - 10), 20, 160, fill=LINE, width=22 * SS)
    return im


def nose_mouth(im):
    d = ImageDraw.Draw(im)
    ny = CY + 70
    d.polygon([tuple(P(CX - 52, ny - 4)), tuple(P(CX + 52, ny - 4)), tuple(P(CX, ny + 50))], fill=PINK)
    d.line([tuple(P(CX, ny + 40)), tuple(P(CX, ny + 82))], fill=LINE, width=18 * SS)
    for sgn in (-1, 1):
        d.arc(P(CX + sgn * 46 - 46, ny + 40, CX + sgn * 46 + 46, ny + 112), 20, 160, fill=LINE, width=18 * SS)
    # усы
    for sgn in (-1, 1):
        for k, dy in enumerate((-30, 5, 40)):
            d.line([tuple(P(CX + sgn * 150, ny + 60 + dy * 0.4)), tuple(P(CX + sgn * 360, ny + 30 + dy * 1.3))],
                   fill=WHITE, width=16 * SS)
    return im


def make(state):
    im = base()
    if state == "closed":
        eyes_closed(im)
    else:
        eyes_open(im, {"center": 0, "left": -1, "right": 1}[state])
    nose_mouth(im)
    return np.asarray(im.resize((W, H), Image.LANCZOS)).astype(np.float32)


def sample(img, xs, ys, rad=4):
    """Средний цвет в квадрате вокруг центра шарика."""
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
        Image.fromarray(a.astype(np.uint8)).resize((360, 640)).save(f"/tmp/pic_{st}.png")
