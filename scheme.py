# Схема с размерами для объявления (1600×1200): вид спереди, сечение, цифры.
# python3 scheme.py <артикул> <выходной jpg> [текстура декора]
import sys, math, random
from PIL import Image, ImageDraw, ImageFont

S = 2                                   # рисуем вдвое крупнее и уменьшаем — гладкие линии
W, H = 1600 * S, 1200 * S
BG, INK, MUTE, LINE = (244, 241, 235), (34, 34, 36), (120, 116, 110), (70, 70, 74)
FD = '/usr/share/fonts/opentype/inter/'


def font(sz, w='Regular'):
    return ImageFont.truetype(f'{FD}Inter-{w}.otf', sz * S)


def text(d, xy, s, f, fill=INK, anchor='la'):
    d.text((xy[0] * S, xy[1] * S), s, font=f, fill=fill, anchor=anchor)


def dim_h(d, x0, x1, y, label, f, up=True, ext=14):
    """Горизонтальный размер: выносные линии, стрелки, подпись."""
    x0, x1, y = x0 * S, x1 * S, y * S
    e = ext * S
    for x in (x0, x1):
        d.line([(x, y - e), (x, y + e)], fill=LINE, width=S)
    d.line([(x0, y), (x1, y)], fill=LINE, width=S)
    a = 7 * S
    d.polygon([(x0, y), (x0 + a * 1.8, y - a * 0.55), (x0 + a * 1.8, y + a * 0.55)], fill=LINE)
    d.polygon([(x1, y), (x1 - a * 1.8, y - a * 0.55), (x1 - a * 1.8, y + a * 0.55)], fill=LINE)
    d.text(((x0 + x1) / 2, y - 8 * S if up else y + 8 * S), label, font=f, fill=INK, anchor='mb' if up else 'mt')


def dim_v(d, x, y0, y1, label, f, left=True, ext=14):
    x, y0, y1 = x * S, y0 * S, y1 * S
    e = ext * S
    for y in (y0, y1):
        d.line([(x - e, y), (x + e, y)], fill=LINE, width=S)
    d.line([(x, y0), (x, y1)], fill=LINE, width=S)
    a = 7 * S
    d.polygon([(x, y0), (x - a * 0.55, y0 + a * 1.8), (x + a * 0.55, y0 + a * 1.8)], fill=LINE)
    d.polygon([(x, y1), (x - a * 0.55, y1 - a * 1.8), (x + a * 0.55, y1 - a * 1.8)], fill=LINE)
    tmp = Image.new('RGBA', (400 * S, 60 * S), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    td.text((200 * S, 30 * S), label, font=f, fill=INK, anchor='mm')
    tmp = tmp.rotate(90, expand=True)
    return tmp, (int(x - (54 if left else -6) * S), int((y0 + y1) / 2 - tmp.height / 2))


def facts(d, x, y, rows):
    fb, fs = font(54, 'SemiBold'), font(25)
    for big, small in rows:
        text(d, (x, y), big, fb)
        text(d, (x, y + 64), small, fs, MUTE)
        y += 122


def slat(art, name, sub, tex_path, out, pack=19):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    text(d, (80, 62), name, font(58, 'SemiBold'))
    text(d, (82, 138), sub, font(28), MUTE)
    fdim = font(26, 'Medium')
    # ---- вид спереди: 3 ламели, разрыв по длине
    k = 3.3                                    # px на мм
    px, py, ph = 150, 250, 800
    pw = 120 * k
    tex = Image.open(tex_path).convert('RGB') if tex_path else None
    if tex is not None:
        # текстура подготовлена под рендер (темнее и насыщеннее); для схемы возвращаем цвет каталога
        import json
        import numpy as np
        import cv2
        c = json.load(open('decors.json', encoding='utf-8'))['decors'].get(art, {})
        lab = cv2.cvtColor(np.asarray(tex), cv2.COLOR_RGB2LAB).astype(np.float32)
        lab[..., 0] -= c.get('dl', 0.0)
        for ch in (1, 2):
            lab[..., ch] = (lab[..., ch] - 128) / c.get('sat', 1.0) + 128
        tex = Image.fromarray(cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB))
    rnd = random.Random(5)
    d.rectangle([px * S, py * S, (px + pw) * S, (py + ph) * S], fill=(14, 14, 15))
    for i in range(3):
        xl = px + (i * 40 + 15.2) * k
        lw = 24.8 * k
        if tex:
            tw = max(8, int(tex.width * 24.8 / 1000))
            th = min(tex.height - 1, int(tw * ph / lw))
            x0 = rnd.randint(0, tex.width - tw - 1)
            y0 = rnd.randint(0, tex.height - th - 1)
            piece = tex.crop((x0, y0, x0 + tw, y0 + th)).resize((int(lw * S), int(ph * S)), Image.LANCZOS)
            im.paste(piece, (int(xl * S), int(py * S)))
        else:
            d.rectangle([xl * S, py * S, (xl + lw) * S, (py + ph) * S], fill=(188, 146, 119))
    # разрыв
    by = py + ph * 0.52
    pts = []
    for j in range(13):
        pts.append(((px - 12 + (pw + 24) * j / 12) * S, (by + (9 if j % 2 else -9)) * S))
    for dy in (-11, 11):
        d.line([(x, y + dy * S) for x, y in pts], fill=BG, width=14 * S, joint='curve')
    dim_h(d, px, px + pw, py - 42, '120 мм', fdim)
    t, pos = dim_v(d, px - 52, py, py + ph, '3000 мм', fdim)
    im.paste(t, pos, t)
    text(d, (px + pw / 2, py + ph + 34), 'вид спереди', font(22), MUTE, 'ma')
    # ---- сечение
    k2 = 6.6
    sx, sy = 700, 345
    text(d, (sx, sy - 128), 'Сечение панели', font(30, 'Medium'))
    dim_h(d, sx + (40 + 15.2) * k2, sx + 80 * k2, sy - 34, 'ламель ≈25', fdim)
    dim_h(d, sx + 80 * k2, sx + (80 + 15.2) * k2, sy - 34, '≈15', fdim)
    d.rectangle([sx * S, (sy + 7.8 * k2) * S, (sx + 120 * k2) * S, (sy + 12 * k2) * S], fill=(16, 16, 17))
    wood = (188, 146, 119)
    if tex:
        wood = tex.resize((1, 1), Image.BOX).getpixel((0, 0))
    for i in range(3):
        xl = sx + (i * 40 + 15.2) * k2
        d.rectangle([xl * S, sy * S, (xl + 24.8 * k2) * S, (sy + 7.8 * k2 + 1) * S], fill=(16, 16, 17))
        d.rectangle([xl * S, (sy - 3) * S, (xl + 24.8 * k2) * S, (sy + 3) * S], fill=wood)
    dim_h(d, sx, sx + 120 * k2, sy + 12 * k2 + 46, '120 мм', fdim, up=False)
    t, pos = dim_v(d, sx + 120 * k2 + 44, sy, sy + 12 * k2, '12 мм', fdim, left=False)
    im.paste(t, pos, t)
    text(d, (sx, sy + 12 * k2 + 104), 'основа чёрная · лицевая сторона ламелей — «под дерево»', font(23), MUTE)
    # ---- цифры
    area = 0.12 * 3.0
    facts(d, 700, 600, [('120 × 3000 × 12 мм', 'ширина × длина × толщина'),
                        (f'{area:.2f}'.replace('.', ',') + ' м²', 'закрывает одна панель'),
                        (f'{pack} шт. = ' + f'{area * pack:.2f}'.replace('.', ',') + ' м²', 'в одной упаковке')])
    im = im.resize((W // S, H // S), Image.LANCZOS)
    im.save(out, quality=93, subsampling=0)


def a910(out, pack=10):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    text(d, (80, 62), 'Реечная панель «волна» A910', font(58, 'SemiBold'))
    text(d, (82, 138), 'белая, под покраску · полукруглые валики', font(28), MUTE)
    fdim = font(26, 'Medium')
    k = 7.4
    sx, sy = 135, 360
    text(d, (sx, sy - 130), 'Сечение панели', font(30, 'Medium'))
    h, p = 3.78, 20.0
    rr = ((p / 2) ** 2 + h * h) / (2 * h)
    top = []
    for i in range(9):
        for j in range(41):
            x = i * p + p * j / 40
            t = 8.22 + math.sqrt(max(0, rr * rr - (x - i * p - p / 2) ** 2)) - (rr - h)
            top.append(((sx + x * k) * S, (sy + (12 - t) * k) * S))
    poly = top + [((sx + 180 * k) * S, (sy + 12 * k) * S), (sx * S, (sy + 12 * k) * S)]
    d.polygon(poly, fill=(250, 250, 248), outline=None)
    d.line(top + [((sx + 180 * k) * S, (sy + 12 * k) * S), (sx * S, (sy + 12 * k) * S), top[0]], fill=(60, 60, 64), width=2 * S, joint='curve')
    dim_h(d, sx, sx + 180 * k, sy + 12 * k + 50, '180 мм', fdim, up=False)
    dim_h(d, sx + 20 * k, sx + 40 * k, sy - 30, '20 мм', fdim)
    t, pos = dim_v(d, sx + 180 * k + 46, sy, sy + 12 * k, '12 мм', fdim, left=False)
    im.paste(t, pos, t)
    text(d, (sx, sy + 12 * k + 112), '9 валиков на панели · поставляется белой, красится в любой цвет', font(23), MUTE)
    area = 0.18 * 3.0
    fb, fs = font(54, 'SemiBold'), font(25)
    rows = [('180 × 3000 × 12 мм', 'ширина × длина × толщина'), (f'{area:.2f}'.replace('.', ',') + ' м²', 'закрывает одна панель'),
            (f'{pack} шт. = ' + f'{area * pack:.1f}'.replace('.', ',') + ' м²', 'в одной упаковке')]
    x = 135
    for big, small in rows:
        text(d, (x, 690), big, fb)
        text(d, (x, 754), small, fs, MUTE)
        x += 560 if big.startswith('180') else 400
    # палитра «примеры покраски»
    text(d, (135, 900), 'Красится в любой цвет', font(30, 'Medium'))
    cols = [(239, 238, 234), (127, 144, 128), (200, 190, 176), (95, 116, 116), (184, 150, 130), (60, 66, 72)]
    for i, c in enumerate(cols):
        d.rounded_rectangle([(135 + i * 150) * S, 960 * S, (135 + i * 150 + 120) * S, 1080 * S], radius=14 * S, fill=c, outline=(200, 196, 190), width=S)
    im = im.resize((W // S, H // S), Image.LANCZOS)
    im.save(out, quality=93, subsampling=0)


A703 = [[0.0, 6.99], [9.97, 15.0], [80.0, 15.0], [80.0, 9.82], [65.01, 9.82], [65.01, 0.0], [60.92, 0.0], [60.73, 0.57], [60.11, 0.93],
        [59.41, 0.74], [59.17, 0.47], [59.04, 0.0], [54.78, 0.0], [54.78, 9.82], [13.28, 9.79], [12.37, 9.54], [11.57, 9.08],
        [10.66, 8.05], [10.3, 7.2], [10.17, 6.25], [10.17, 0.0], [5.97, 0.0], [5.7, 0.66], [5.16, 0.93], [4.45, 0.74], [4.16, 0.36],
        [4.09, 0.0], [0.0, 0.0]]


def a703(out, pack=28):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    text(d, (80, 62), 'Плинтус напольный A703', font(58, 'SemiBold'))
    text(d, (82, 138), 'белый, под покраску · высота 80 мм', font(28), MUTE)
    fdim = font(26, 'Medium')
    k = 9.0
    sx, sy = 330, 290                      # стена слева, пол снизу
    text(d, (82, sy - 62), 'Сечение', font(30, 'Medium'))
    # стена и пол
    d.rectangle([(sx - 60) * S, (sy - 30) * S, sx * S, (sy + 80 * k) * S], fill=(214, 209, 200))
    d.rectangle([(sx - 60) * S, (sy + 80 * k) * S, (sx + 420) * S, (sy + 80 * k + 46) * S], fill=(198, 176, 150))
    text(d, (sx - 30, sy - 58), 'стена', font(20), MUTE, 'ma')
    text(d, (sx + 300, sy + 80 * k + 12), 'пол', font(20), MUTE)
    poly = [((sx + t * k) * S, (sy + u * k) * S) for u, t in A703]
    d.polygon(poly, fill=(251, 251, 249))
    d.line(poly + [poly[0]], fill=(60, 60, 64), width=2 * S, joint='curve')
    t, pos = dim_v(d, sx + 15 * k + 60, sy, sy + 80 * k, '80 мм', fdim, left=False)
    im.paste(t, pos, t)
    dim_h(d, sx, sx + 15 * k, sy + 80 * k + 92, '15 мм', fdim, up=False)
    text(d, (sx + 15 * k + 130, sy + 300), 'сзади — канал\nдля кабеля', font(23), MUTE)
    facts(d, 880, 330, [('80 × 15 мм', 'высота × толщина'), ('2000 мм', 'длина одной планки'),
                        (f'{pack} шт. = {pack * 2} м', 'в одной упаковке'), ('под покраску', 'поставляется белым')])
    im = im.resize((W // S, H // S), Image.LANCZOS)
    im.save(out, quality=93, subsampling=0)


if __name__ == '__main__':
    art, out = sys.argv[1], sys.argv[2]
    tex = sys.argv[3] if len(sys.argv) > 3 else None
    if art == '3-7':
        slat(art, 'Реечная панель 3-7', 'под дерево · дуб натуральный · 3 ламели на чёрной основе', tex, out)
    elif art == '3-15':
        slat(art, 'Реечная панель 3-15', 'под дерево · светлое натуральное дерево · 3 ламели на чёрной основе', tex, out)
    elif art == '3-9':
        slat(art, 'Реечная панель 3-9', 'под дерево · орех тёмный · 3 ламели на чёрной основе', tex, out)
    elif art == 'A910':
        a910(out)
    elif art == 'A703':
        a703(out)
    print('scheme', art, out)
