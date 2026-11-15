# Обложка «Кот Барсик»: кадр из движка + плашки как на прошлых обложках.
# python3 compose.py кадр.png выход.jpg "СЕРИЯ 27" "ПОЧЕМУ ЛОДКА|НЕ ТОНЕТ?" crop=x,y,w,h banner=left|center|right
import sys, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops

BLACK = '/usr/share/fonts/truetype/inter/Inter-Black.ttf'
import glob
c = glob.glob('/usr/share/fonts/**/Inter*Black*.[ot]tf', recursive=True) + glob.glob('/usr/share/fonts/**/Inter-Black*', recursive=True)
c = [x for x in c if 'Italic' not in x and 'Display' not in x] or c
BLACK = c[0]
S = 2  # рисуем вдвое крупнее, потом уменьшаем — ровные края
W, H = 1280 * S, 720 * S


def font(px):
    return ImageFont.truetype(BLACK, int(px))


def outlined_text(img, xy, text, f, fill, stroke, sw, anchor='la', shadow=True, grad=None):
    d = ImageDraw.Draw(img)
    if shadow:
        sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((xy[0] + sw * .5, xy[1] + sw * .9), text, font=f, fill=(0, 0, 0, 120), stroke_width=sw, stroke_fill=(0, 0, 0, 120), anchor=anchor)
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(sw * .6)))
    d.text(xy, text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke, anchor=anchor)
    if grad:  # градиент по буквам (сверху вниз)
        m = Image.new('L', img.size, 0)
        ImageDraw.Draw(m).text(xy, text, font=f, fill=255, anchor=anchor)
        bb = m.getbbox()
        g = Image.new('RGBA', img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        for y in range(bb[1], bb[3] + 1):
            t = (y - bb[1]) / max(1, bb[3] - bb[1])
            col = tuple(int(grad[0][i] * (1 - t) + grad[1][i] * t) for i in range(3)) + (255,)
            gd.line([(bb[0], y), (bb[2], y)], fill=col)
        img.paste(g, (0, 0), m)


def logo(img, k=1.0):
    L = Image.new('RGBA', (560 * S, 300 * S), (0, 0, 0, 0))
    f1, f2 = font(70 * S), font(96 * S)
    # белая подложка-обводка, коричневый контур, жёлто-оранжевые буквы
    for (xy, t, f) in (((40 * S, 20 * S), 'Кот', f1), ((20 * S, 96 * S), 'Барсик', f2)):
        ImageDraw.Draw(L).text(xy, t, font=f, fill='white', stroke_width=17 * S, stroke_fill='white')
    sh = L.split()[3].filter(ImageFilter.GaussianBlur(8 * S))
    base = Image.new('RGBA', L.size, (0, 0, 0, 0)); base.paste((60, 30, 10, 140), (6 * S, 10 * S), sh)
    L = Image.alpha_composite(base, L)
    for (xy, t, f) in (((40 * S, 20 * S), 'Кот', f1), ((20 * S, 96 * S), 'Барсик', f2)):
        outlined_text(L, xy, t, f, (255, 190, 40, 255), (110, 52, 14, 255), 7 * S, shadow=False, grad=((255, 226, 92), (246, 128, 22)))
    # лапка у «Кот»
    d = ImageDraw.Draw(L)
    px, py, r = 205 * S, 52 * S, 15 * S
    col, oc = (246, 128, 22, 255), (110, 52, 14, 255)
    for (dx, dy, rr) in ((0, 14, 1.05), (-17, -6, .5), (-6, -17, .5), (8, -17, .5), (19, -6, .5)):
        cx, cy, R = px + dx * S, py + dy * S, r * rr
        d.ellipse([cx - R - 4 * S, cy - R - 4 * S, cx + R + 4 * S, cy + R + 4 * S], fill='white')
    for (dx, dy, rr) in ((0, 14, 1.05), (-17, -6, .5), (-6, -17, .5), (8, -17, .5), (19, -6, .5)):
        cx, cy, R = px + dx * S, py + dy * S, r * rr
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=col, outline=oc, width=3 * S)
    L = L.rotate(5, resample=Image.BICUBIC, expand=True)
    L = L.resize((int(L.width * k), int(L.height * k)), Image.LANCZOS)
    img.alpha_composite(L, (int(10 * S), int(2 * S)))


def pill(img, text):
    f = font(50 * S)
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=f)
    w, h = int(tw + 64 * S), 82 * S
    x, y = W - w - 30 * S, 30 * S
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x + 4 * S, y + 8 * S, x + w + 4 * S, y + h + 8 * S], h // 2, fill=(0, 0, 0, 110))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 * S)))
    d.rounded_rectangle([x, y, x + w, y + h], h // 2, fill='white')
    i = 7 * S
    d.rounded_rectangle([x + i, y + i, x + w - i, y + h - i], (h - 2 * i) // 2, fill=(226, 36, 30))
    d.rounded_rectangle([x + i, y + i, x + w - i, y + h // 2], (h - 2 * i) // 2, fill=(240, 66, 50))
    d.rectangle([x + i + 20 * S, y + h // 2 - 10 * S, x + w - i - 20 * S, y + h // 2], fill=(240, 66, 50))
    d.text((x + w / 2, y + h / 2 + 2 * S), text, font=f, fill='white', anchor='mm', stroke_width=2 * S, stroke_fill=(150, 20, 15))


PAD = 70
def banner(img, lines, where, maxw=.52, base=None):
    sizes = {1: 112, 2: 100}
    fs = int((base or sizes[len(lines)]) * S)
    f = font(fs)
    d = ImageDraw.Draw(img)
    while max(d.textlength(t, font=f) for t in lines) > (W * maxw if where != 'center' else W * .74):
        fs -= 2 * S; f = font(fs)
    tw = max(d.textlength(t, font=f) for t in lines)
    lh = fs * 1.02
    bw, bh = int(tw + 150 * S), int(lh * len(lines) + PAD * S)
    if where == 'left': x0 = 22 * S
    elif where == 'right': x0 = W - bw - 22 * S
    else: x0 = (W - bw) // 2
    y0 = H - bh - 22 * S
    # свиток: волнистые верх и низ, загнутые края
    P = Image.new('RGBA', img.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(P)
    top = [(x0 + 30 * S + t * (bw - 60 * S), y0 + math.sin(t * math.pi * 2.2 + .4) * 7 * S) for t in [i / 40 for i in range(41)]]
    bot = [(x0 + 30 * S + t * (bw - 60 * S), y0 + bh + math.sin(t * math.pi * 2.2 + 1.9) * 7 * S) for t in [i / 40 for i in range(41)]][::-1]
    poly = top + bot
    shp = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shp).polygon([(px + 6 * S, py + 12 * S) for px, py in poly], fill=(40, 20, 5, 140))
    img.alpha_composite(shp.filter(ImageFilter.GaussianBlur(9 * S)))
    pd.polygon(poly, fill=(246, 228, 184, 255), outline=(120, 74, 30, 255), width=6 * S)
    # загнутые края-рулоны
    for side in (0, 1):
        cx = x0 + (30 * S if side == 0 else bw - 30 * S)
        pd.rounded_rectangle([cx - 26 * S, y0 - 12 * S, cx + 26 * S, y0 + bh + 12 * S], 26 * S, fill=(222, 186, 124), outline=(120, 74, 30), width=6 * S)
        pd.rounded_rectangle([cx - 10 * S, y0 + 4 * S, cx + 4 * S, y0 + bh - 4 * S], 7 * S, fill=(240, 214, 160))
    # лёгкая неоднородность бумаги
    m = P.split()[3]
    noise = Image.effect_noise(img.size, 30).filter(ImageFilter.GaussianBlur(14 * S))
    tint = Image.merge('RGBA', (noise.point(lambda v: 120), noise.point(lambda v: 80), noise.point(lambda v: 30), noise.point(lambda v: max(0, v - 120))))
    tm = ImageChops.multiply(tint.split()[3], m)
    tint.putalpha(tm)
    P.alpha_composite(tint)
    img.alpha_composite(P)
    cy = y0 + bh / 2 - lh * (len(lines) - 1) / 2 + 4 * S
    for i, t in enumerate(lines):
        outlined_text(img, (x0 + bw / 2, cy + i * lh), t, f, (150, 26, 12, 255), (255, 246, 222, 255), 5 * S, anchor='mm', shadow=False)


def main():
    src, out, ser, q = sys.argv[1:5]
    opt = dict(a.split('=', 1) for a in sys.argv[5:])
    im = Image.open(src).convert('RGB')
    if 'crop' in opt:
        x, y, w, h = map(int, opt['crop'].split(','))
        im = im.crop((x, y, x + w, y + h))
    im = im.resize((W, H), Image.LANCZOS)
    im = ImageEnhance.Color(im).enhance(float(opt.get('sat', 1.15)))
    im = ImageEnhance.Contrast(im).enhance(float(opt.get('con', 1.06)))
    im = ImageEnhance.Brightness(im).enhance(float(opt.get('bri', 1.0)))
    img = im.convert('RGBA')
    global PAD
    PAD = int(opt.get('pad', 70))
    logo(img, float(opt.get('logo', .72)))
    pill(img, ser)
    banner(img, q.split('|'), opt.get('banner', 'left'), float(opt.get('maxw', .5)), float(opt['fs']) if 'fs' in opt else None)
    img = img.convert('RGB').resize((1280, 720), Image.LANCZOS)
    img.save(out, quality=93, optimize=True)
    img.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.png'))
    print(out)


if __name__ == '__main__':
    main()
