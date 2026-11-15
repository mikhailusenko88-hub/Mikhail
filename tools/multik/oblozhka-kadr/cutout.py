# Вырезка героя из двух кадров studio.js (тот же кадр на чёрном и на сером фоне) → PNG с прозрачностью.
#   python3 cutout.py st_T_k.png st_T_g.png герой.png [keep=1]
# Прозрачность по разнице фонов: на чёрном видно α·F, на сером α·F + (1-α)·B. Серый фон после виньетки неровный —
# берём его там, где героя нет, и размазываем на всю картинку. keep=1 — оставить только самое большое пятно (без «!» над головой).
import sys
import numpy as np
from PIL import Image, ImageFilter


def matte(kp, gp, keep_main=True):
    k = np.asarray(Image.open(kp).convert('RGB'), dtype=np.float32) / 255
    g = np.asarray(Image.open(gp).convert('RGB'), dtype=np.float32) / 255
    d = (g - k).mean(axis=2)                                   # = (1-α)·B
    bgmask = (k.max(axis=2) < 0.012).astype(np.float32)        # точно фон: на чёрном ничего нет
    gb = g.mean(axis=2) * bgmask
    # фон под героем: нормированное размытие (заполняем дыру соседним фоном)
    S = 61
    num = np.asarray(Image.fromarray((gb * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(S)), dtype=np.float32) / 255
    den = np.asarray(Image.fromarray((bgmask * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(S)), dtype=np.float32) / 255
    B = np.where(den > 1e-3, num / np.maximum(den, 1e-3), 0.72)
    B = np.asarray(Image.fromarray(np.clip(B * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(25)), dtype=np.float32) / 255
    a = np.clip(1 - d / np.maximum(B, .2), 0, 1)
    a[bgmask > 0] = 0
    a = np.where(a < .04, 0, a)
    a = np.where(a > .96, 1, a)
    F = np.clip(k / np.maximum(a[..., None], 1e-3), 0, 1)
    F[a == 0] = 0
    A = (a * 255).astype(np.uint8)
    if keep_main:
        from scipy import ndimage
        lab, n = ndimage.label(A > 20)
        if n > 1:
            sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)); big = 1 + int(np.argmax(sizes))
            keep = ndimage.binary_dilation(lab == big, iterations=6)
            A = (A * keep).astype(np.uint8)
    out = Image.fromarray(np.dstack([(F * 255).astype(np.uint8), A]), 'RGBA')
    return out.crop(out.getbbox())


if __name__ == '__main__':
    kp, gp, op = sys.argv[1:4]
    opt = dict(x.split('=', 1) for x in sys.argv[4:])
    im = matte(kp, gp, opt.get('keep', '1') == '1'); im.save(op); print(op, im.size)
