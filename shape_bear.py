"""Силуэт медведя: SDF (минус — внутри). Те же числа — в sim_bear.c."""
import numpy as np
from shape import W, H, sd_circle, smin

CX, CY = 540.0, 1060.0
HEAD = [(CX, CY, 380.0), (CX, CY + 90.0, 340.0)]
EARS = [(CX - 285.0, CY - 290.0, 118.0), (CX + 285.0, CY - 290.0, 118.0)]


def sdf(x, y):
    d = smin(sd_circle(x, y, HEAD[0]), sd_circle(x, y, HEAD[1]), 80.0)
    for c in EARS:
        d = smin(d, sd_circle(x, y, c), 60.0)
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
    img[inside] = (170, 110, 60)
    img[np.abs(f) < 3] = (255, 255, 255)
    Image.fromarray(img).resize((270, 480)).save("/tmp/bear_shape.png")
