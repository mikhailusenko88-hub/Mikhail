"""Силуэт головы кота: SDF (минус — внутри). Те же числа — в sim.c."""
import numpy as np

W, H = 1080, 1920
CX, CY = 540.0, 1090.0
# голова: верхний круг + две щеки, уши — скруглённые треугольники
HEAD = (CX, CY - 30.0, 375.0)
CHEEKS = [(CX - 165.0, CY + 95.0, 270.0), (CX + 165.0, CY + 95.0, 270.0), (CX, CY + 110.0, 280.0)]
EARS = [((CX - 300.0, CY - 180.0), (CX - 325.0, CY - 600.0), (CX - 95.0, CY - 330.0)),
        ((CX + 300.0, CY - 180.0), (CX + 325.0, CY - 600.0), (CX + 95.0, CY - 330.0))]
EAR_ROUND = 20.0
K_CHEEK, K_EAR = 90.0, 60.0


def sd_circle(x, y, c):
    return np.hypot(x - c[0], y - c[1]) - c[2]


def sd_tri(x, y, p0, p1, p2):
    e0 = (p1[0] - p0[0], p1[1] - p0[1]); e1 = (p2[0] - p1[0], p2[1] - p1[1]); e2 = (p0[0] - p2[0], p0[1] - p2[1])
    v0 = (x - p0[0], y - p0[1]); v1 = (x - p1[0], y - p1[1]); v2 = (x - p2[0], y - p2[1])

    def pq(v, e):
        t = np.clip((v[0] * e[0] + v[1] * e[1]) / (e[0] * e[0] + e[1] * e[1]), 0, 1)
        return (v[0] - e[0] * t, v[1] - e[1] * t)
    q0, q1, q2 = pq(v0, e0), pq(v1, e1), pq(v2, e2)
    s = np.sign(e0[0] * e2[1] - e0[1] * e2[0])
    d0 = q0[0] ** 2 + q0[1] ** 2; c0 = s * (v0[0] * e0[1] - v0[1] * e0[0])
    d1 = q1[0] ** 2 + q1[1] ** 2; c1 = s * (v1[0] * e1[1] - v1[1] * e1[0])
    d2 = q2[0] ** 2 + q2[1] ** 2; c2 = s * (v2[0] * e2[1] - v2[1] * e2[0])
    d = np.minimum(np.minimum(d0, d1), d2)
    c = np.minimum(np.minimum(c0, c1), c2)
    return -np.sqrt(d) * np.sign(c)


def smin(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def sdf(x, y):
    d = sd_circle(x, y, HEAD)
    for c in CHEEKS:
        d = smin(d, sd_circle(x, y, c), K_CHEEK)
    for t in EARS:
        d = smin(d, sd_tri(x, y, *t) - EAR_ROUND, K_EAR)
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
    img[inside] = (200, 120, 40)
    img[np.abs(f) < 3] = (255, 255, 255)
    Image.fromarray(img).resize((270, 480)).save("/tmp/shape.png")
