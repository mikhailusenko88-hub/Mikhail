# Финальная обработка кадра «как с фотоаппарата»: лёгкая виньетка, плёночное зерно, резкость, подпись.
# python3 post.py in.jpg out.jpg ["подпись"]
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = '/usr/share/fonts/opentype/inter/Inter-Medium.otf'


def process(src, dst, caption='3D-визуализация', vignette=0.10, grain=1.6, sharpen=0.35, quality=92, max_w=None):
    im = Image.open(src).convert('RGB')
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    if sharpen:
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(sharpen * 100), threshold=2))
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    if vignette:
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
        a *= (1 - vignette * np.clip(r, 0, 1) ** 2.2)[..., None]
    if grain:
        rng = np.random.default_rng(7)
        g = rng.normal(0, grain, (h, w)).astype(np.float32)
        lum = a.mean(2) / 255.0
        a += (g * (1.15 - 0.6 * lum))[..., None]          # в светах зерна меньше
    im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    if caption:
        fs = max(13, round(w * 0.0125))
        f = ImageFont.truetype(FONT, fs)
        ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        x, y = round(w * 0.018), h - round(w * 0.018) - fs
        d.text((x + 1, y + 1), caption, font=f, fill=(0, 0, 0, 90))
        d.text((x, y), caption, font=f, fill=(255, 255, 255, 185))
        im = Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')
    im.save(dst, quality=quality, subsampling=0, optimize=True)
    return im.size


if __name__ == '__main__':
    cap = sys.argv[3] if len(sys.argv) > 3 else '3D-визуализация'
    print(process(sys.argv[1], sys.argv[2], cap))
