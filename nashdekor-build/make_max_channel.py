# Картинки для канала «Наш декор» в MAX: аватар, обложки постов (фирменный стиль) и карточки товаров с подписью.
# python3 make_max_channel.py <папка сайта 0f7s1eez> <папка рендеров paneli-render> <папка превью 3D-моделей> <скриншоты расчёта: телефон1.png,телефон2.png>
# Результат: <сайт>/img/max/*.jpg — их MAX забирает по ссылке https://nashdekor.ru/img/max/… при публикации постов.
import json, os, re, shutil, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SITE, RENDER, MODELS, SHOTS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(',')
OUT = f'{SITE}/img/max'
ANTH, GAL, BLUE = (0x26, 0x29, 0x2E), (0xF8, 0xF8, 0xF6), (0x7E, 0x97, 0xAD)
HAZE, STONE, SUBD = (0xD9, 0xDE, 0xE3), (0xA8, 0x9F, 0x91), (0xC3, 0xCA, 0xD2)
FD = '/usr/share/fonts/opentype/inter/'
BRAND = '/home/claude/brand/brand/files/png/'
font = lambda sz, w='Regular': ImageFont.truetype(f'{FD}Inter-{w}.otf', sz)
W, H, HEAD = 1600, 1200, 300

s = open(f'{SITE}/index.html', encoding='utf-8').read()
CAT = {x['a']: x for x in json.loads(s[s.find('const CAT=') + len('const CAT='):s.find('];', s.find('const CAT=')) + 1])}
PHOTOS = json.loads(re.search(r'const PHOTOS = (\{.*?\});', s, flags=re.S).group(1))
os.makedirs(OUT, exist_ok=True)


def logo(height):
    lg = Image.open(BRAND + 'logo-horizontal-for-dark-transparent-2400.png').convert('RGBA')
    lg = lg.crop(lg.getbbox())
    return lg.resize((round(lg.width * height / lg.height), height), Image.LANCZOS)


def fit(im, w, h, cy=0.5):
    """Заполнить w×h (обрезка по центру; cy — где резать по высоте)."""
    k = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x0 = (im.width - w) // 2
    y0 = round((im.height - h) * cy)
    return im.crop((x0, y0, x0 + w, y0 + h))


def header(title, sub, eyebrow=''):
    im = Image.new('RGB', (W, H), ANTH)
    d = ImageDraw.Draw(im)
    lg = logo(54)
    im.paste(lg, (64, 46), lg)
    if eyebrow:
        d.text((W - 64, 73), eyebrow, font=font(26, 'SemiBold'), fill=BLUE, anchor='rm')
    d.text((64, 140), title, font=font(70, 'SemiBold'), fill=GAL)
    d.text((64, 232), sub, font=font(32), fill=SUBD)
    return im, d


def caption3d(im, d, text='3D-визуализация'):
    f = font(22)
    w = d.textlength(text, font=f)
    d.rounded_rectangle((40, H - 62, 40 + w + 28, H - 26), 8, fill=(38, 41, 46))
    d.text((54, H - 44), text, font=f, fill=SUBD, anchor='lm')


def cover_render(name, title, sub, src, eyebrow='', cy=0.45, note='3D-визуализация'):
    im, d = header(title, sub, eyebrow)
    ph = fit(Image.open(src).convert('RGB'), W, H - HEAD, cy)
    im.paste(ph, (0, HEAD))
    if note:
        caption3d(im, d, note)
    im.save(f'{OUT}/{name}.jpg', quality=88, optimize=True)
    return name


def card_img(a, i=0):
    f = (PHOTOS.get(a) or [None])[i]
    return Image.open(f'{SITE}/img/2x/{f}').convert('RGB')


def cover_grid(name, title, sub, arts, eyebrow=''):
    """Обложка из 4 карточек товара 2×2 на антраците (фон карточек — тот же антрацит)."""
    im, d = header(title, sub, eyebrow)
    cw, ch = W // 2, (H - HEAD) // 2
    for k, a in enumerate(arts[:4]):
        c = fit(card_img(a), cw, ch)
        im.paste(c, ((k % 2) * cw, HEAD + (k // 2) * ch))
        d.text(((k % 2) * cw + 28, HEAD + (k // 2) * ch + ch - 30), a, font=font(30, 'SemiBold'), fill=SUBD, anchor='lm')
    im.save(f'{OUT}/{name}.jpg', quality=88, optimize=True)
    return name


def shot(path, w):
    ph = Image.open(path).convert('RGB')
    ph = ph.crop((0, 0, ph.width, min(ph.height, round(ph.width * 2.0))))
    ph = ph.resize((w, round(ph.height * w / ph.width)), Image.LANCZOS)
    m = Image.new('L', ph.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), 34, fill=255)
    return ph, m


def cover_calc(name):
    im, d = header('Расчёт стены в 3D', 'Размер стены → панель → цвет: штуки, коробки и сумма сразу', 'НА САЙТЕ')
    area = Image.new('RGB', (W, H - HEAD), (0xEC, 0xEF, 0xF2))
    im.paste(area, (0, HEAD))
    x = 250
    for p in SHOTS:
        ph, m = shot(p, 470)
        sh = Image.new('RGBA', (ph.width + 60, ph.height + 60), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((30, 36, ph.width + 30, ph.height + 36), 34, fill=(0, 0, 0, 70))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        y = HEAD + 50
        im.paste(sh, (x - 30, y - 30), sh)
        im.paste(ph, (x, y), m)
        x += 640
    im = im.crop((0, 0, W, H))
    im.save(f'{OUT}/{name}.jpg', quality=88, optimize=True)
    return name


def cover_models(name):
    im, d = header('3D-модели для дизайнеров', 'FBX · SketchUp (DAE) · OBJ · GLB · сечения DXF — 105 профилей', 'ДИЗАЙНЕРАМ')
    picks = ['1 Панели белые под покраску/A907/A907', '1 Панели белые под покраску/A910/A910', '2 Панели с декором/3-7/3-7',
             '2 Панели с декором/5-10/5-10', '1 Панели белые под покраску/A920/A920', '2 Панели с декором/2-12/2-12',
             '3 Плинтусы напольные/A703/A703', '3 Плинтусы напольные/A31/A31', '4 Потолочные плинтусы/A172/A172',
             '5 Молдинги/A161/A161', '5 Молдинги/A302/A302', '5 Молдинги/A151/A151']
    cw, ch = W // 4, (H - HEAD) // 3
    for k, p in enumerate(picks):
        f = f'{MODELS}/{p}.jpg'
        if not os.path.exists(f):
            print('нет превью', f); continue
        c = fit(Image.open(f).convert('RGB'), cw, ch)
        im.paste(c, ((k % 4) * cw, HEAD + (k // 4) * ch))
    im.save(f'{OUT}/{name}.jpg', quality=88, optimize=True)
    return name


def cover_brand(name, src, note):
    """Обложка закреплённого поста: интерьер на весь кадр, сверху — логотип и строка о магазине."""
    src = Image.open(src).convert('RGB')
    src = src.crop((0, 0, src.width, src.height - 70))          # без подписи, впечатанной в рендер
    im = fit(src, W, H, 0.5)
    band = Image.new('RGBA', (W, 330), (0x26, 0x29, 0x2E, 236))
    im.paste(band, (0, 0), band)
    d = ImageDraw.Draw(im)
    lg = logo(96)
    im.paste(lg, (64, 52), lg)
    d.text((64, 196), 'Стеновые панели, плинтусы и молдинги', font=font(48, 'SemiBold'), fill=GAL)
    d.text((64, 268), 'Санкт-Петербург и Ленобласть · отправка по России · nashdekor.ru', font=font(30), fill=SUBD)
    caption3d(im, d, note)
    im.save(f'{OUT}/{name}.jpg', quality=88, optimize=True)
    return name


CABLE = {'A703'}          # канал для кабеля сзади — по чертежу и тексту объявления (в описании сайта не написано)


def label(x):
    """Подпись под фото: что это за изделие, по-человечески."""
    d = (x['d'] + ' ' + x['n']).lower()
    if x['c'] == 'plinth':
        t = f"Плинтус напольный, высота {x['w']} мм"
        return t + (' · сзади канал для кабеля' if 'кабел' in d or x['a'] in CABLE else '') + (' · с подсветкой' if 'подсвет' in d else '')
    if x['c'] == 'mold':
        return 'Молдинг под покраску' + (' · с кабель-каналом' if 'кабел' in d else '')
    if x['c'] == 'cornice':
        return 'Потолочный плинтус' + (' с подсветкой' if 'подсвет' in d else '')
    if x['c'] == 'corner':
        return 'Уголок для внешнего угла'
    return short(x)


def short(x):
    t = x['d'].split(',')[0].strip()
    t = re.sub(r'\s+на ч[её]рной основе$', '', t)
    if re.match(r'^\d', t):
        t = re.split(r',| — ', x['n'])[0].strip()
    return t[:1].upper() + t[1:]


def label_card(a, i=0):
    """Фото товара как на сайте + полоса снизу: артикул, описание, размер."""
    x = CAT[a]
    ph = card_img(a, i).resize((1280, 728), Image.LANCZOS)
    im = Image.new('RGB', (1280, 728 + 150), ANTH)
    im.paste(ph, (0, 0))
    d = ImageDraw.Draw(im)
    d.line((48, 728, 1232, 728), fill=(0x40, 0x45, 0x4D), width=2)
    d.text((48, 772), a, font=font(46, 'SemiBold'), fill=GAL, anchor='lm')
    aw = d.textlength(a, font=font(46, 'SemiBold'))
    d.text((48 + aw + 24, 774), label(x), font=font(30), fill=SUBD, anchor='lm')
    d.text((48, 830), f"{x['w']}×{x['t']}×{x['l']} мм", font=font(28, 'Medium'), fill=BLUE, anchor='lm')
    name = 'c_' + re.sub(r'[^a-z0-9]+', '-', a.lower()).strip('-')
    im.save(f'{OUT}/{name}.jpg', quality=86, optimize=True)
    return name


made = {}
shutil.copy(BRAND + 'icon-square-anthracite-512.png', f'{OUT}/avatar.png')
R = RENDER + '/avito_foto/'
made['brand'] = cover_brand('cover_brand', R + 'A910v4/1.jpg', '3D-визуализация · панели окрашены в цвет стены, продаются белыми')
made['paint'] = cover_render('cover_paint', 'Реечные панели под покраску', '18 профилей · белые, красятся в любой цвет · длина 3 м',
                             R + 'A910v4/2.jpg', 'ПОД ПОКРАСКУ', cy=0.3)
made['wood'] = cover_render('cover_wood', 'Панели под дерево', '28 декоров · серии на 2, 3 и 5 реек · красить не нужно',
                            R + '3-7v4/1.jpg', 'ПОД ДЕРЕВО', cy=0.3)
made['plinth'] = cover_render('cover_plinth', 'Напольные плинтусы', 'Белые, под покраску в цвет стены · есть с каналом для кабеля',
                              R + 'A703v4/3.jpg', 'ПЛИНТУСЫ', cy=0.5)
made['mold'] = cover_grid('cover_mold', 'Молдинги', 'Под покраску: обрамление стен, проёмов и зеркал, буазери',
                          ['A161', 'A302', 'A151', 'A400'], 'МОЛДИНГИ')
made['cornice'] = cover_grid('cover_cornice', 'Потолочные плинтусы и уголки', 'Под покраску · галтель с подсветкой',
                             ['A172', 'A503', 'A38', 'A116'], 'ПОТОЛОК И УГЛЫ')
made['calc'] = cover_calc('cover_calc')
made['models'] = cover_models('cover_models')

GROUPS = {
    'paint': ['A907', 'A902', 'A910', 'A913', 'A920', 'A916', 'GS 1', 'A905', 'A908'],
    'wood': ['3-7', '3-9', '3-15', '3-12', '5-5', '5-10', '5-6', '2-7', '2-12'],
    'plinth': ['A703', 'A704', 'A705', 'A707', 'A701', 'A702', 'A31', 'A15', 'A11-80'],
    'mold': ['A161', 'A302', 'A151', 'A400', 'A002/2', 'A611/2', 'A301', 'A10', 'A25'],
    'cornice': ['A172', 'A503', 'A38', 'A116', 'A06'],
}
cards = {g: [label_card(a) for a in arts] for g, arts in GROUPS.items()}
json.dump({'covers': made, 'cards': cards, 'groups': GROUPS}, open(f'{OUT}/index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('готово:', len(os.listdir(OUT)), 'файлов в', OUT)
