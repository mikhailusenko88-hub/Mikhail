# Схема с размерами в фирменном стиле «Наш декор» (1600×1200): шапка-антрацит с логотипом,
# размерные линии серо-голубые, цифры на плашках «Дымка», фон «Галерея», шрифт Inter.
# python3 scheme_brand.py <артикул> <выходной jpg> [текстура декора]
import sys, math, random, json
from PIL import Image, ImageDraw, ImageFont

S = 2
W, H = 1600, 1200
ANTH, GAL, BLUE = (0x26, 0x29, 0x2E), (0xF8, 0xF8, 0xF6), (0x7E, 0x97, 0xAD)
HAZE, STONE, SUBD, SUBL = (0xD9, 0xDE, 0xE3), (0xA8, 0x9F, 0x91), (0xC3, 0xCA, 0xD2), (0x58, 0x5E, 0x66)
BLACK = (17, 17, 18)                     # чёрная основа самой панели (цвет товара)
FD = '/usr/share/fonts/opentype/inter/'
LOGO = '/home/claude/brand/brand/files/png/logo-horizontal-for-dark-transparent-2400.png'
HEAD = 190


def font(sz, w='Regular'):
    return ImageFont.truetype(f'{FD}Inter-{w}.otf', int(sz * S))


def P(*v):
    return [c * S for c in v]


def text(d, xy, s, f, fill=ANTH, anchor='la'):
    d.text((xy[0] * S, xy[1] * S), s, font=f, fill=fill, anchor=anchor)


def arrow(d, x, y, dx, dy):
    a = 7 * S
    nx, ny = -dy, dx
    d.polygon([(x, y), (x + dx * a * 1.8 + nx * a * 0.5, y + dy * a * 1.8 + ny * a * 0.5),
               (x + dx * a * 1.8 - nx * a * 0.5, y + dy * a * 1.8 - ny * a * 0.5)], fill=BLUE)


def dim_h(d, x0, x1, y, label, up=True, ext=13, f=None):
    f = f or font(25, 'Medium')
    x0, x1, y = x0 * S, x1 * S, y * S
    e = ext * S
    for x in (x0, x1):
        d.line([(x, y - e), (x, y + e)], fill=BLUE, width=S)
    d.line([(x0, y), (x1, y)], fill=BLUE, width=S)
    arrow(d, x0, y, 1, 0)
    arrow(d, x1, y, -1, 0)
    d.text(((x0 + x1) / 2, y - 9 * S if up else y + 9 * S), label, font=f, fill=ANTH, anchor='mb' if up else 'mt')


def dim_v(im, d, x, y0, y1, label, left=True, ext=13, f=None):
    f = f or font(25, 'Medium')
    x, y0, y1 = x * S, y0 * S, y1 * S
    e = ext * S
    for y in (y0, y1):
        d.line([(x - e, y), (x + e, y)], fill=BLUE, width=S)
    d.line([(x, y0), (x, y1)], fill=BLUE, width=S)
    arrow(d, x, y0, 0, 1)
    arrow(d, x, y1, 0, -1)
    tmp = Image.new('RGBA', (400 * S, 60 * S), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((200 * S, 30 * S), label, font=f, fill=ANTH, anchor='mm')
    tmp = tmp.rotate(90, expand=True)
    im.paste(tmp, (int(x - (52 if left else -8) * S - (0 if left else 0)), int((y0 + y1) / 2 - tmp.height / 2)), tmp)


NOLOGO = False                           # для Авито: без логотипа и названия магазина на картинке


def header(im, d, title, sub):
    d.rectangle(P(0, 0, W, HEAD), fill=ANTH)
    if NOLOGO:
        text(d, (70, 52), title, font(50, 'SemiBold'), GAL)
        text(d, (72, 120), sub, font(24), SUBD)
        return
    lg = Image.open(LOGO)
    lg = lg.crop(lg.getbbox())
    lw = 430 * S
    lg = lg.resize((lw, round(lg.height * lw / lg.width)), Image.LANCZOS)
    im.paste(lg, (70 * S, (HEAD * S - lg.height) // 2), lg)
    text(d, (1530, 66), title, font(44, 'SemiBold'), GAL, 'ra')
    text(d, (1530, 124), sub, font(23), SUBD, 'ra')


def footer(d, left='Размеры в миллиметрах'):
    d.line(P(70, 1122, 1530, 1122), fill=STONE, width=S)
    text(d, (70, 1142), left, font(20), SUBL)
    text(d, (1530, 1142), 'Стена как галерея', font(20, 'Italic'), SUBL, 'ra')


def card(d, x0, y0, x1, y1, big, small, big_sz=44):
    d.rounded_rectangle(P(x0, y0, x1, y1), radius=16 * S, fill=HAZE)
    text(d, (x0 + 28, y0 + 24), big, font(big_sz, 'SemiBold'))
    text(d, (x0 + 28, y1 - 26), small, font(22), SUBL, 'ls')


def decor_tex(art, tex_path):
    if not tex_path:
        return None, 1000
    import numpy as np
    import cv2
    tex = Image.open(tex_path).convert('RGB')
    c = json.load(open('decors.json', encoding='utf-8'))['decors'].get(art, {})
    lab = cv2.cvtColor(np.asarray(tex), cv2.COLOR_RGB2LAB).astype(np.float32)
    lab[..., 0] -= c.get('dl', 0.0)                       # вернуть цвет каталога (текстура для рендера темнее)
    for ch in (1, 2):
        lab[..., ch] = (lab[..., ch] - 128) / c.get('sat', 1.0) + 128
    tex = Image.fromarray(cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB))
    return tex, c.get('size_mm', 1000)


def slat(art, title, sub, tex_path, out, pack=19):
    im = Image.new('RGB', (W * S, H * S), GAL)
    d = ImageDraw.Draw(im)
    header(im, d, title, sub)
    tex, size_mm = decor_tex(art, tex_path)
    # ---- вид спереди
    k, px, py, ph = 3.3, 160, 300, 740
    pw = 120 * k
    rnd = random.Random(5)
    d.rectangle(P(px, py, px + pw, py + ph), fill=BLACK)
    for i in range(3):
        xl, lw = px + (i * 40) * k, 29.5 * k
        if tex:
            tw = max(8, int(tex.width * 29.5 / size_mm))
            th = min(tex.height - 1, int(tw * ph / lw))
            x0, y0 = rnd.randint(0, tex.width - tw - 1), rnd.randint(0, tex.height - th - 1)
            im.paste(tex.crop((x0, y0, x0 + tw, y0 + th)).resize((int(lw * S), int(ph * S)), Image.LANCZOS), (int(xl * S), int(py * S)))
        else:
            d.rectangle(P(xl, py, xl + lw, py + ph), fill=(188, 146, 119))
    by = py + ph * 0.52
    pts = [((px - 12 + (pw + 24) * j / 12) * S, (by + (9 if j % 2 else -9)) * S) for j in range(13)]
    for dy in (-11, 11):
        d.line([(x, y + dy * S) for x, y in pts], fill=GAL, width=14 * S, joint='curve')
    dim_h(d, px, px + pw, py - 34, '120 мм')
    dim_v(im, d, px - 48, py, py + ph, '3000 мм')
    text(d, (px + pw / 2, py + ph + 26), 'вид спереди', font(21), SUBL, 'ma')
    # ---- сечение
    k2, sx, sy = 6.3, 700, 400
    text(d, (sx, 262), 'Сечение панели', font(30, 'SemiBold'))
    wood = tex.resize((1, 1), Image.BOX).getpixel((0, 0)) if tex else (188, 146, 119)
    import slat_profile as SP                      # настоящий профиль по живому образцу: «змейка» с пустотами под рейками
    prof = SP.rounded(SP.outline(3))
    d.polygon([((sx + x * k2) * S, (sy + (12 - z) * k2) * S) for x, z, _ in prof], fill=BLACK)
    for i in range(3):
        xl = sx + (i * 40) * k2
        d.rectangle(P(xl + 0.6 * k2, sy - 3, xl + 28.9 * k2, sy + 3), fill=wood)
    dim_h(d, sx + 40 * k2, sx + 69.5 * k2, sy - 32, 'рейка ≈30')
    dim_h(d, sx + 69.5 * k2, sx + 80 * k2, sy - 32, '≈10')
    dim_h(d, sx, sx + 120 * k2, sy + 12 * k2 + 44, '120 мм', up=False)
    dim_v(im, d, sx + 120 * k2 + 40, sy, sy + 12 * k2, '12 мм', left=False)
    text(d, (sx, sy + 12 * k2 + 102), 'профиль полый, чёрный · лицевая сторона реек — «под дерево»', font(22), SUBL)
    # ---- цифры
    area = 0.12 * 3.0
    card(d, 700, 690, 1500, 830, '120 × 3000 × 12 мм', 'ширина × длина × толщина')
    card(d, 700, 850, 1090, 990, f'{area:.2f}'.replace('.', ',') + ' м²', 'закрывает одна панель')
    card(d, 1110, 850, 1500, 990, f'{pack} шт. · ' + f'{area * pack:.2f}'.replace('.', ',') + ' м²', 'в одной упаковке', 40)
    footer(d)
    im.resize((W, H), Image.LANCZOS).save(out, quality=93, subsampling=0)


def a910(out, pack=10):
    im = Image.new('RGB', (W * S, H * S), GAL)
    d = ImageDraw.Draw(im)
    header(im, d, 'Реечная панель «волна» A910', 'белая, под покраску · полукруглые валики')
    k, sx, sy = 7.4, 135, 380
    text(d, (sx, 262), 'Сечение панели', font(30, 'SemiBold'))
    import a910_profile as AP                      # настоящий профиль по живому образцу: валики и канавки с тыльной стороны
    pts = [((sx + x * k) * S, (sy + (12 - z) * k) * S) for x, z, _ in AP.outline()]
    d.polygon(pts, fill=(255, 255, 255))
    d.line(pts + [pts[0]], fill=ANTH, width=2 * S, joint='curve')
    dim_h(d, sx + 20 * k, sx + 40 * k, sy - 30, '20 мм')
    dim_h(d, sx, sx + 180 * k, sy + 12 * k + 46, '180 мм', up=False)
    dim_v(im, d, sx + 180 * k + 42, sy, sy + 12 * k, '12 мм', left=False)
    text(d, (sx, sy + 12 * k + 104), '9 валиков на панели · сзади продольные канавки · поставляется белой', font(22), SUBL)
    area = 0.18 * 3.0
    card(d, 135, 640, 655, 780, '180 × 3000 × 12 мм', 'ширина × длина × толщина')
    card(d, 675, 640, 1045, 780, f'{area:.2f}'.replace('.', ',') + ' м²', 'закрывает одна панель')
    card(d, 1065, 640, 1467, 780, f'{pack} шт. · ' + f'{area * pack:.1f}'.replace('.', ',') + ' м²', 'в одной упаковке')
    text(d, (135, 836), 'Красится в любой цвет', font(30, 'SemiBold'))
    cols = [(239, 238, 234), (127, 144, 128), (200, 190, 176), BLUE, (184, 150, 130), ANTH]
    for i, c in enumerate(cols):
        x = 135 + i * 150
        d.rounded_rectangle(P(x, 896, x + 120, 1016), radius=14 * S, fill=c, outline=(205, 208, 212), width=S)
    footer(d)
    im.resize((W, H), Image.LANCZOS).save(out, quality=93, subsampling=0)


A703 = [[0.0, 6.99], [9.97, 15.0], [80.0, 15.0], [80.0, 9.82], [65.01, 9.82], [65.01, 0.0], [60.92, 0.0], [60.73, 0.57], [60.11, 0.93],
        [59.41, 0.74], [59.17, 0.47], [59.04, 0.0], [54.78, 0.0], [54.78, 9.82], [13.28, 9.79], [12.37, 9.54], [11.57, 9.08],
        [10.66, 8.05], [10.3, 7.2], [10.17, 6.25], [10.17, 0.0], [5.97, 0.0], [5.7, 0.66], [5.16, 0.93], [4.45, 0.74], [4.16, 0.36],
        [4.09, 0.0], [0.0, 0.0]]


def a703(out, pack=28):
    im = Image.new('RGB', (W * S, H * S), GAL)
    d = ImageDraw.Draw(im)
    header(im, d, 'Плинтус напольный A703', 'белый, под покраску · высота 80 мм')
    k, sx, sy = 8.2, 330, 322
    text(d, (110, 232), 'Сечение', font(30, 'SemiBold'))
    floor_y = sy + 80 * k
    d.rectangle(P(sx - 70, sy - 20, sx, floor_y), fill=HAZE)
    fl = tuple(int(a * 0.45 + b * 0.55) for a, b in zip(STONE, GAL))
    d.rectangle(P(sx - 70, floor_y, sx + 420, floor_y + 40), fill=fl)
    hatch = Image.new('RGBA', (490 * S, 40 * S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for i in range(-40, 520, 18):
        hd.line([(i * S, 40 * S), ((i + 30) * S, 0)], fill=STONE, width=S)
    im.paste(hatch, ((sx - 70) * S, int(floor_y * S)), hatch)
    d.rectangle(P(sx - 70, floor_y, sx + 420, floor_y + 40), outline=STONE, width=S)
    text(d, (sx - 35, sy - 50), 'стена', font(20), SUBL, 'ma')
    text(d, (sx + 300, floor_y + 52), 'пол', font(20), SUBL)
    poly = [((sx + t * k) * S, (sy + u * k) * S) for u, t in A703]
    d.polygon(poly, fill=(255, 255, 255))
    d.line(poly + [poly[0]], fill=ANTH, width=2 * S, joint='curve')
    dim_v(im, d, sx + 15 * k + 56, sy, floor_y, '80 мм', left=False)
    dim_h(d, sx, sx + 15 * k, floor_y + 92, '15 мм', up=False)
    text(d, (sx + 15 * k + 118, sy + 286), 'сзади — канал\nдля кабеля', font(22), SUBL)
    card(d, 820, 300, 1150, 460, '80 × 15 мм', 'высота × толщина')
    card(d, 1170, 300, 1500, 460, '2000 мм', 'длина одной планки')
    card(d, 820, 480, 1150, 640, f'{pack} шт. · {pack * 2} м', 'в одной упаковке')
    card(d, 1170, 480, 1500, 640, 'белый', 'красится в любой цвет')
    text(d, (820, 700), 'Фаска сверху, канал для кабеля сзади.', font(23), SUBL)
    footer(d)
    im.resize((W, H), Image.LANCZOS).save(out, quality=93, subsampling=0)


if __name__ == '__main__':
    if '--nologo' in sys.argv:
        sys.argv.remove('--nologo')
        NOLOGO = True
    art, out = sys.argv[1], sys.argv[2]
    tex = sys.argv[3] if len(sys.argv) > 3 else None
    subs = {'3-7': 'под дерево · дуб натуральный · 3 рейки, чёрные пазы',
            '3-15': 'под дерево · светлое натуральное дерево · 3 рейки, чёрные пазы',
            '3-9': 'под дерево · орех тёмный · 3 рейки, чёрные пазы'}
    if art in subs:
        slat(art, f'Реечная панель {art}', subs[art], tex, out)
    elif art == 'A910':
        a910(out)
    elif art == 'A703':
        a703(out)
    print('scheme', art, out)
