# Кадр для обложки: обрезка + вставки. Выход 1280×720 PNG (дальше — compose.py).
#   python3 extras.py кадр.png выход.png [crop=x,y,w,h] [lupa=вещь.png,cx,cy,r,hx,hy] [moon=луна.png,cx,cy,r] [bri=1.0]
# lupa — главный предмет крупно в лупе (ручка тянется к лапе героя hx,hy); вещь.png — лист sheet.js с одной вещью (фон убирается сам).
# moon — луна из движка крупнее в небе, с «укусом» (серия про фазы Луны). Координаты — в кадре 1280×720 после обрезки.
import sys, math
from PIL import Image, ImageDraw, ImageFilter, ImageChops


def cut(path, light_bg=True):
    im = Image.open(path).convert('RGB'); im = im.crop((0, 30, im.width, im.height))   # без подписи листа sheet.js
    h, s, v = im.convert('HSV').split()
    m = ImageChops.lighter(Image.eval(s, lambda x: 255 if x > 40 else 0), Image.eval(v, lambda x: 255 if x < 175 else 0))
    m = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9)); bb = m.getbbox()
    out = im.convert('RGBA'); out.putalpha(m.filter(ImageFilter.GaussianBlur(1.5))); return out.crop(bb)


def lupa(img, obj, cx, cy, r, hx, hy):
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    a = math.atan2(hy - cy, hx - cx); x1, y1 = cx + math.cos(a) * (r + 6), cy + math.sin(a) * (r + 6)
    sd.line([(x1 + 5, y1 + 8), (hx + 5, hy + 8)], fill=(0, 0, 0, 110), width=30)
    sd.ellipse([cx - r - 9, cy - r - 6, cx + r + 19, cy + r + 22], fill=(0, 0, 0, 110)); img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    L = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.line([(x1, y1), (hx, hy)], fill=(92, 48, 18, 255), width=28); d.line([(x1, y1), (hx, hy)], fill=(168, 96, 40, 255), width=18)
    d.ellipse([cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16], fill=(92, 48, 18, 255)); d.ellipse([cx - r - 11, cy - r - 11, cx + r + 11, cy + r + 11], fill=(214, 140, 52, 255))
    for i in range(r, 0, -2):
        t = i / r; d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(int(255 - 25 * t), int(252 - 18 * t), int(236 - 40 * t), 255))
    o = obj.copy(); k = (r * 1.72) / max(o.size); o = o.resize((int(o.width * k), int(o.height * k)), Image.LANCZOS)
    L.alpha_composite(o, (int(cx - o.width / 2), int(cy - o.height / 2 + 6)))
    ImageDraw.Draw(L).arc([cx - r + 14, cy - r + 14, cx + r - 14, cy + r - 14], 200, 255, fill=(255, 255, 255, 170), width=10)
    img.alpha_composite(L)


def moon(img, obj, cx, cy, r, bites=((.95, -.55, .42), (1.12, .1, .36))):
    o = obj.resize((2 * r, 2 * r), Image.LANCZOS); m = Image.new('L', o.size, 0); md = ImageDraw.Draw(m)
    md.ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
    for bx, by, br in bites:
        md.ellipse([r + bx * r - br * r, r + by * r - br * r, r + bx * r + br * r, r + by * r + br * r], fill=0)
    m = m.filter(ImageFilter.GaussianBlur(1.2))
    o = Image.blend(o.convert('RGB'), Image.new('RGB', o.size, (255, 244, 190)), .25).convert('RGBA'); o.putalpha(m)
    gm = Image.new('L', img.size, 0); gm.paste(m, (cx - r, cy - r)); gm = gm.filter(ImageFilter.GaussianBlur(r * .45))
    glow = Image.new('RGBA', img.size, (0, 0, 0, 0)); glow.paste((255, 236, 160, 255), (0, 0), gm.point(lambda v: int(v * .75)))
    img.alpha_composite(glow); img.alpha_composite(o, (cx - r, cy - r))


if __name__ == '__main__':
    src, out = sys.argv[1:3]; opt = dict(a.split('=', 1) for a in sys.argv[3:])
    im = Image.open(src).convert('RGB')
    if 'crop' in opt:
        x, y, w, h = map(int, opt['crop'].split(',')); im = im.crop((x, y, x + w, y + h))
    im = im.resize((1280, 720), Image.LANCZOS)
    if 'bri' in opt:
        k = float(opt['bri']); im = Image.eval(im, lambda v: min(255, int(v * k)))
    img = im.convert('RGBA')
    if 'lupa' in opt:
        p, *n = opt['lupa'].split(','); lupa(img, cut(p), *map(int, n))
    if 'moon' in opt:
        p, *n = opt['moon'].split(','); moon(img, cut(p), *map(int, n))
    img.convert('RGB').save(out); print('ok', out)
