# Образцы идей с фирменным стилем: логотип на фото, обложка первого фото, карточка «сколько панелей нужно».
import math, sys
from PIL import Image, ImageDraw
sys.path.insert(0, '/home/claude/render')
from post import process
from scheme_brand import (font, text, P, header, footer, card, ANTH, GAL, BLUE, HAZE, STONE, SUBD, SUBL, S, W, H)

PNG = '/home/claude/brand/brand/files/png/'
OUT = '/home/claude/out_img/ideas'
import os
os.makedirs(OUT, exist_ok=True)


def logo(name, width):
    lg = Image.open(PNG + name)
    lg = lg.crop(lg.getbbox())
    return lg.resize((width, round(lg.height * width / lg.width)), Image.LANCZOS)


# 1. Логотип в уголке фото — на плашке «Галерея» (фото пёстрое, по правилам бренда — на плашку)
def logo_corner(src, dst):
    im = Image.open(src).convert('RGBA')
    lg = logo('logo-horizontal-for-light-transparent-2400.png', 250)
    pad = 16
    pw, ph = lg.width + pad * 2, lg.height + pad * 2
    x, y = im.width - pw - 28, im.height - ph - 28
    pl = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(pl).rounded_rectangle([x, y, x + pw, y + ph], radius=10, fill=GAL + (235,))
    im = Image.alpha_composite(im, pl)
    im.paste(lg, (x + pad, y + pad), lg)
    im.convert('RGB').save(dst, quality=93, subsampling=0)


# 2. Обложка первого фото: интерьер + полоса-антрацит с логотипом и названием
def cover(raw, dst, title, sub):
    tmp = '/tmp/cover_base.jpg'
    process(raw, tmp, caption=None)
    im = Image.open(tmp).convert('RGBA')
    bh = 170
    d = ImageDraw.Draw(im)
    d.rectangle([0, im.height - bh, im.width, im.height], fill=ANTH + (255,))
    lg = logo('logo-horizontal-for-dark-transparent-2400.png', 330)
    im.paste(lg, (48, im.height - bh + (bh - lg.height) // 2), lg)
    from PIL import ImageFont
    f1 = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-SemiBold.otf', 44)
    f2 = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Regular.otf', 24)
    f3 = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Regular.otf', 18)
    d.text((im.width - 48, im.height - bh + 44), title, font=f1, fill=GAL, anchor='ra')
    d.text((im.width - 48, im.height - bh + 104), sub, font=f2, fill=SUBD, anchor='ra')
    d.text((20, im.height - bh - 14), '3D-визуализация', font=f3, fill=(255, 255, 255, 190), anchor='ls')
    im.convert('RGB').save(dst, quality=93, subsampling=0)


# 3. Карточка «Сколько панелей нужно»
def calc(dst, art, width_mm, pack, title):
    im = Image.new('RGB', (W * S, H * S), GAL)
    d = ImageDraw.Draw(im)
    header(im, d, title, 'сколько панелей нужно на стену')
    text(d, (110, 250), 'Панели длиной 3 м ставятся вертикально.', font(30, 'SemiBold'))
    text(d, (110, 300), f'Ширина стены ÷ {width_mm / 1000:.2f} м, округлить вверх — столько панелей'.replace('.', ','), font(25), SUBL)
    text(d, (110, 336), 'на стену высотой до 3 м.', font(25), SUBL)
    rows = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    x0, x1, y = 110, 1490, 410
    d.rounded_rectangle(P(x0, y, x1, y + 70), radius=14 * S, fill=ANTH)
    text(d, (x0 + 40, y + 21), 'Ширина стены', font(26, 'SemiBold'), GAL)
    text(d, (760, y + 21), 'Панелей', font(26, 'SemiBold'), GAL)
    text(d, (1120, y + 21), 'Площадь', font(26, 'SemiBold'), GAL)
    y += 82
    for i, wm in enumerate(rows):
        n = math.ceil(wm * 1000 / width_mm - 1e-9)
        if i % 2 == 0:
            d.rounded_rectangle(P(x0, y, x1, y + 78), radius=12 * S, fill=HAZE)
        text(d, (x0 + 40, y + 20), (f'{wm:g} м').replace('.', ','), font(32, 'Medium'))
        text(d, (760, y + 20), f'{n} шт.', font(32, 'SemiBold'))
        text(d, (1120, y + 20), (f'{wm * 3:.1f} м²').replace('.', ','), font(32, 'Medium'), SUBL)
        y += 86
    text(d, (110, y + 30), f'В упаковке {pack} шт. Пришлите ширину и высоту стены — посчитаем точно.', font(25), SUBL)
    footer(d, 'Расчёт для стены высотой до 3 м')
    im.resize((W, H), Image.LANCZOS).save(dst, quality=93, subsampling=0)


if __name__ == '__main__':
    F = '/home/claude/out_img/final/'
    logo_corner(F + '3-7 — 1 гостиная.jpg', f'{OUT}/идея 1 — логотип в уголке фото.jpg')
    cover('/home/claude/render/out/f1/f1.jpg', f'{OUT}/идея 2 — обложка первого фото.jpg', 'Реечная панель 3-7',
          'дуб натуральный · 120 × 3000 мм')
    calc(f'{OUT}/идея 3 — сколько панелей нужно.jpg', '3-7', 120, 19, 'Реечная панель 3-7')
    print('ok')
