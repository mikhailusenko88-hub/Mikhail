# Каталог «Наш декор» (PDF, A4) из данных сайта: index.html (CAT, PHOTO) и фото img/2x. Без бренда поставщика.
# python3 make_katalog.py <папка сайта 0f7s1eez> <выход.pdf> <дата цен ДД.ММ.ГГГГ>
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont

SITE, OUT, DAY = sys.argv[1], sys.argv[2], sys.argv[3]
ANTH, GAL, BLUE = (0x26, 0x29, 0x2E), (0xF8, 0xF8, 0xF6), (0x7E, 0x97, 0xAD)
HAZE, STONE, SUBD, SUBL = (0xD9, 0xDE, 0xE3), (0xA8, 0x9F, 0x91), (0xC3, 0xCA, 0xD2), (0x58, 0x5E, 0x66)
FD = '/usr/share/fonts/opentype/inter/'
LOGO = '/home/claude/brand/brand/files/png/logo-horizontal-for-dark-transparent-2400.png'
W, H, M = 1654, 2339, 110                      # A4, 200 dpi
font = lambda sz, w='Regular': ImageFont.truetype(f'{FD}Inter-{w}.otf', sz)
fmt = lambda n: f'{int(round(n)):,}'.replace(',', ' ')

s = open(f'{SITE}/index.html', encoding='utf-8').read()
CAT = json.loads(s[s.find('const CAT=') + len('const CAT='):s.find('];', s.find('const CAT=')) + 1])
PHOTO = json.loads(re.search(r'const PHOTO = (\{.*?\});', s).group(1))
SECTIONS = [('panel', 'Стеновые панели под покраску', 'Реечные панели из полистирола высокой плотности: белые, ударопрочные, влагостойкие. Длина 3 м — без стыков до потолка.'),
            ('color', 'Реечные панели под дерево', 'Готовый декор на чёрной основе — красить не нужно. Три серии по числу реек на панели шириной 120 мм.'),
            ('plinth', 'Напольные плинтусы', 'Белые плинтусы под покраску, в том числе с каналом для кабеля и под подсветку.'),
            ('cornice', 'Потолочные плинтусы', 'Потолочные плинтусы (галтели) под покраску.'),
            ('mold', 'Молдинги', 'Настенные молдинги под покраску: рамки, обрамление проёмов, стыки.'),
            ('corner', 'Уголки', 'Уголки под покраску для внешних углов.')]


def page(title):
    im = Image.new('RGB', (W, H), GAL)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 210], fill=ANTH)
    lg = Image.open(LOGO); lg = lg.crop(lg.getbbox()); lw = 460
    lg = lg.resize((lw, round(lg.height * lw / lg.width)), Image.LANCZOS)
    im.paste(lg, (M, (210 - lg.height) // 2), lg)
    d.text((W - M, 105), title, font=font(40, 'SemiBold'), fill=GAL, anchor='rm')
    d.line([M, H - 120, W - M, H - 120], fill=STONE, width=2)
    d.text((M, H - 92), 'Наш декор · Санкт-Петербург · nashdekor.ru', font=font(24), fill=SUBL)
    d.text((W - M, H - 92), f'цены на {DAY}', font=font(24), fill=SUBL, anchor='ra')
    return im, d


def wrap(d, text, f, width):
    out, line = [], ''
    for w in text.split(' '):
        t = (line + ' ' + w).strip()
        if d.textlength(t, font=f) <= width:
            line = t
        else:
            out.append(line); line = w
    out.append(line)
    return out


def short(x):
    """Короткая подпись: первая часть описания до размеров."""
    t = x['d'].split(',')[0].strip()
    t = re.sub(r'\s+на чёрной основе$', '', t)
    if re.match(r'^\d', t):                     # описание начинается с размеров — берём начало названия
        t = re.split(r',| — ', x['n'])[0].strip()
    return t[:1].upper() + t[1:]


pages = []
# ---------------- обложка
im = Image.new('RGB', (W, H), ANTH); d = ImageDraw.Draw(im)
lg = Image.open(LOGO); lg = lg.crop(lg.getbbox()); lw = 900
lg = lg.resize((lw, round(lg.height * lw / lg.width)), Image.LANCZOS)
im.paste(lg, (M, 330), lg)
d.text((M, 760), 'Каталог', font=font(150, 'SemiBold'), fill=GAL)
d.text((M, 960), 'Стеновые панели, плинтусы и молдинги', font=font(58), fill=SUBD)
d.text((M, 1040), 'под покраску и под дерево', font=font(58), fill=SUBD)
y = 1260
for c, title, _ in SECTIONS:
    n = sum(1 for x in CAT if x['c'] == c)
    d.text((M, y), title, font=font(40, 'Medium'), fill=GAL); d.text((W - M, y), f'{n} позиций', font=font(40), fill=BLUE, anchor='ra')
    d.line([M, y + 66, W - M, y + 66], fill=(70, 75, 82), width=2); y += 92
d.text((M, H - 300), 'Санкт-Петербург и Ленинградская область · доставка по России', font=font(34), fill=SUBD)
d.text((M, H - 240), 'nashdekor.ru · info@nashdekor.ru', font=font(34, 'SemiBold'), fill=GAL)
d.text((M, H - 170), f'Цены на {DAY}. Актуальные цены и наличие — на сайте.', font=font(28), fill=SUBD)
pages.append(im)

# ---------------- разделы
cols, gap = 2, 44
tw = (W - 2 * M - gap) // cols
th = round(tw * 449 / 790)
rowh = th + 200
for c, title, lead in SECTIONS:
    items = [x for x in CAT if x['c'] == c]
    first = True
    k = 0
    while k < len(items):
        im, d = page(title)
        y0 = 270
        if first:
            for ln in wrap(d, lead, font(30), W - 2 * M):
                d.text((M, y0), ln, font=font(30), fill=SUBL); y0 += 44
            y0 += 26
            first = False
        rows = (H - 150 - y0) // rowh
        for r in range(rows):
            for q in range(cols):
                if k >= len(items):
                    break
                x = items[k]; k += 1
                px, py = M + q * (tw + gap), y0 + r * rowh
                ph = PHOTO.get(x['a'])
                if ph and os.path.exists(f'{SITE}/img/2x/{ph}'):
                    t = Image.open(f'{SITE}/img/2x/{ph}').convert('RGB')
                    t = t.resize((tw, round(t.height * tw / t.width)), Image.LANCZOS).crop((0, 0, tw, th))
                    im.paste(t, (px, py))
                else:
                    d.rectangle([px, py, px + tw, py + th], fill=HAZE)
                yy = py + th + 16
                d.text((px, yy), x['a'], font=font(40, 'SemiBold'), fill=ANTH)
                d.text((px + tw, yy + 4), f"{fmt(x['r'])} ₽ / шт", font=font(36, 'SemiBold'), fill=ANTH, anchor='ra')
                yy += 56
                for ln in wrap(d, short(x), font(25), tw)[:2]:
                    d.text((px, yy), ln, font=font(25), fill=SUBL); yy += 34
                dims = f"{x['w']}×{x['t']}×{x['l']} мм · в коробке {x['b']} шт"
                if c in ('panel', 'color'):
                    dims += f" · ≈ {fmt(x['r'] / (x['w'] / 1000 * x['l'] / 1000))} ₽/м²"
                d.text((px, py + th + 16 + 56 + 2 * 34 + 2), dims, font=font(24, 'Medium'), fill=BLUE)
        pages.append(im)

# ---------------- последняя страница
im, d = page('Как мы работаем')
y = 300
blocks = [('Расчёт по проекту', 'Пришлите развёртку стены или размеры помещения — вернём спецификацию по артикулам, количество с запасом и смету. На сайте есть расчёт стены в 3D.'),
          ('3D-модели для дизайнеров', 'Все профили в натуральную величину: FBX для 3ds Max, DAE для SketchUp, OBJ, GLB и DXF-сечения для AutoCAD, ArchiCAD и Revit. Пришлём по запросу.'),
          ('Покраска', 'Белые панели, плинтусы и молдинги — под покраску: цвет подбираете под стену или в контраст.'),
          ('Доставка', 'Самовывоз со склада — бесплатно. По Петербургу — 1–2 дня, по Ленобласти — 1–3 дня после оплаты, по тарифу перевозчика. В Москву и другие регионы отправляем транспортной компанией. Стоимость доставки называем до оплаты.'),
          ('Оплата', 'Частным покупателям — картой или через СБП по ссылке, электронный чек на e-mail. Компаниям и ИП — по счёту. Цены без НДС.'),
          ('Документы для объекта', 'Счёт, накладная и закрывающие документы для компаний и ИП, по ЭДО или на бумаге.')]
for t, txt in blocks:
    d.text((M, y), t, font=font(44, 'SemiBold'), fill=ANTH); y += 66
    for ln in wrap(d, txt, font(30), W - 2 * M):
        d.text((M, y), ln, font=font(30), fill=SUBL); y += 44
    y += 44
d.rounded_rectangle([M, y + 10, W - M, y + 250], radius=18, fill=ANTH)
d.text((M + 50, y + 56), 'nashdekor.ru', font=font(64, 'SemiBold'), fill=GAL)
d.text((M + 50, y + 150), 'info@nashdekor.ru · каталог, цены, 3D-просмотр и расчёт стены', font=font(32), fill=SUBD)
pages.append(im)

pages[0].save(OUT, save_all=True, append_images=pages[1:], resolution=200, quality=86)
print('pages', len(pages), 'items', len(CAT), OUT, os.path.getsize(OUT) // 1024, 'KB')
