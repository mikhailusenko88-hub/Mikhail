"""Силуэт лягушки: SDF (минус — внутри). Те же числа — в sim_frog.c."""
import numpy as np
from shape import W, H, sd_circle, smin

CX, CY = 540.0, 1090.0
FACE = [(CX, CY + 50.0, 350.0), (CX - 150.0, CY + 90.0, 290.0), (CX + 150.0, CY + 90.0, 290.0)]
EYES = [(CX - 205.0, CY - 270.0, 150.0), (CX + 205.0, CY - 270.0, 150.0)]


def sdf(x, y):
    d = sd_circle(x, y, FACE[0])
    for c in FACE[1:]:
        d = smin(d, sd_circle(x, y, c), 90.0)
    for c in EYES:
        d = smin(d, sd_circle(x, y, c), 70.0)
    return d


def field(scale=1):
    yy, xx = np.mgrid[0:H:scale, 0:W:scale].astype(np.float64)
    return sdf(xx + 0.5, yy + 0.5)


if __name__ == "__main__":
    from PIL import Image
    f = field()
    inside = f < 0
    print("площадь", inside.sum(), "bbox y", np.where(inside.any(1))[0][[0, -1]], "x", np.where(inside.any(0))[0][[0, -1]])
    img = np.zeros((H, W, 3), np.uint8)
    img[inside] = (90, 190, 70)
    img[np.abs(f) < 3] = (255, 255, 255)
    Image.fromarray(img).resize((270, 480)).save("/tmp/frog_shape.png")
