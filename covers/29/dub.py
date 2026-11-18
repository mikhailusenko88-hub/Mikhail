# Элемент обложки 29: дуб с луга (фон движка f4_meadow_day) — вырезан по цвету; правый край кроны, срезанный кадром, достроен зеркально с левой стороны
import sys
import numpy as np
from PIL import Image, ImageFilter
src, out = sys.argv[1], sys.argv[2]
A = np.array(Image.open(src).convert('RGB')).astype(int)
X0, Y1 = 1302, 560
C = A[:Y1, X0:]; r, g, b = C[..., 0], C[..., 1], C[..., 2]
h, w = r.shape; yy, xx = np.mgrid[0:h, 0:w]; ax = 415
leaf = (g - b > 22) & (r < 95) & (g < 175) & (g > r + 15)
leaf &= (yy < 262) | ((yy < 300) & (np.abs(xx - ax) < 140))
hw = np.where(yy < 420, 52, 52 + (yy - 420) * 0.36)
trunk = (np.abs(xx - ax) < hw) & (yy > 180) & (((r >= g - 6) & (b < 70)) | ((r + g + b) < 60))
m = leaf | trunk
# дыры в кроне: в каждой строке кроны закрасить от крайней левой до крайней правой точки листвы
for y in range(0, 226):
    xs = np.where(leaf[y])[0]
    if len(xs) > 8:
        a, z = xs.min(), xs.max(); m[y, a:z + 1] = True
# холст: слева ось + 330, справа ось + 330
W2 = 2 * 330; T = np.zeros((h, W2, 4), np.uint8)
for dx in range(-330, 330):
    xs = ax + dx; xd = dx + 330
    if 0 <= xs < w:
        T[:, xd, :3] = C[:, xs]; T[:, xd, 3] = m[:, xs] * 255
    else:                               # за краем кадра — зеркало левой стороны
        xm = ax - dx
        T[:, xd, :3] = C[:, xm]; T[:, xd, 3] = m[:, xm] * 255
img = Image.fromarray(T, 'RGBA'); a = img.split()[3].filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.0)); img.putalpha(a)
img = img.crop(img.getbbox()); img.save(out); print(img.size)
