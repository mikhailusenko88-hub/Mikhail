"""Картинка для кучи: панда на пастельном фоне (центр ниже, чтобы уши не срезала неровная верхушка кучи).
make(state) → массив 1920×1080×3; состояния center / left / right / closed."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
CX, CY = 540.0, 1190.0
SS = 2
WHITE = (250, 250, 250)
BLACK = (28, 28, 34)
GRAY = (70, 70, 82)
PINK = (255, 150, 170)


def P(*v):
    return [c * SS for c in v]


def head_mask():
    m = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(m)
    d.ellipse(P(CX - 380, CY - 380, CX + 380, CY + 380), fill=255)
    d.ellipse(P(CX - 340, CY - 250, CX + 340, CY + 430), fill=255)
    return m


def base():
    g = np.linspace(0, 1, H * SS)[:, None, None]
    top, bot = np.array([150, 205, 250]), np.array([170, 235, 190])
    bg = (top + (bot - top) * g) * np.ones((1, W * SS, 1))
    im = Image.fromarray(bg.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for sgn in (-1, 1):                                                  # уши
        ex, ey = CX + sgn * 285, CY - 300
        d.ellipse(P(ex - 125, ey - 125, ex + 125, ey + 125), fill=BLACK)
        d.ellipse(P(ex - 62, ey - 62, ex + 62, ey + 62), fill=GRAY)
    m = head_mask()
    ring = m.filter(ImageFilter.MaxFilter(21))
    im.paste(Image.new("RGB", im.size, GRAY), (0, 0), ring)
    im.paste(Image.new("RGB", im.size, WHITE), (0, 0), m)
    d = ImageDraw.Draw(im)
    for sgn in (-1, 1):                                                  # пятна вокруг глаз (наклонённые овалы)
        patch = Image.new("L", (360 * SS, 360 * SS), 0)
        ImageDraw.Draw(patch).ellipse(P(90, 50, 270, 310), fill=255)
        patch = patch.rotate(sgn * 32, resample=Image.BICUBIC)
        im.paste(Image.new("RGB", patch.size, BLACK), (int((CX + sgn * 150 - 180) * SS), int((CY - 60 - 180) * SS)), patch)
        d.ellipse(P(CX + sgn * 255 - 50, CY + 110, CX + sgn * 255 + 50, CY + 170), fill=PINK)   # щёчки
    d.rounded_rectangle(P(CX - 64, CY + 95, CX + 64, CY + 165), radius=34 * SS, fill=BLACK)     # нос
    d.line([tuple(P(CX, CY + 160)), tuple(P(CX, CY + 215))], fill=BLACK, width=16 * SS)
    for sgn in (-1, 1):
        d.arc(P(CX + sgn * 50 - 52, CY + 170, CX + sgn * 50 + 52, CY + 262), 20, 160, fill=BLACK, width=16 * SS)
    return im


def eyes(im, state):
    d = ImageDraw.Draw(im)
    for sgn in (-1, 1):
        ex, ey = CX + sgn * 150, CY - 40
        if state == "closed":
            d.arc(P(ex - 60, ey - 70, ex + 60, ey + 40), 20, 160, fill=WHITE, width=18 * SS)
            continue
        look = {"center": 0, "left": -1, "right": 1}[state]
        d.ellipse(P(ex - 46, ey - 46, ex + 46, ey + 46), fill=WHITE)
        px = ex + look * 16
        d.ellipse(P(px - 28, ey - 28, px + 28, ey + 28), fill=BLACK)
        d.ellipse(P(px - 22, ey - 22, px - 4, ey - 4), fill=WHITE)
    return im


K, CY2 = 0.9, 1235.0      # уменьшить и опустить, чтобы уши не срезала неровная верхушка кучи


def make(state="center"):
    im = eyes(base(), state).resize((W, H), Image.LANCZOS)
    a = 1 / K
    im = im.transform((W, H), Image.AFFINE, (a, 0, CX - CX * a, 0, a, CY - CY2 * a), resample=Image.BICUBIC,
                      fillcolor=(160, 222, 222))
    return np.asarray(im)


if __name__ == "__main__":
    Image.fromarray(make("center")).resize((360, 640)).save("/tmp/panda.png")
    Image.fromarray(make("closed")).resize((360, 640)).save("/tmp/panda_c.png")
