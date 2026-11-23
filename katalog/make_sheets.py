# Листы каталога «для чата»: вертикальные картинки под экран телефона.
# Фирменный стиль (Inter, «Антрацит», «Галерея»), без марки поставщика, без названия магазина и контактов.
# Данные — из каталога сайта (CAT на главной странице ветки mebel), фото — 0f7s1eez/img/2x/<артикул>.jpg.
# Запуск: python3 make_sheets.py <index.html сайта> <папка с фото> <папка для листов>
import json, re, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

IDX, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
S = 2                      # рисуем вдвое крупнее, потом уменьшаем
W = 1080
FINAL_W = 1440
ANTH, GAL, BLUE = (0x26, 0x29, 0x2E), (0xF8, 0xF8, 0xF6), (0x7E, 0x97, 0xAD)
HAZE, STONE, SUBD, SUBL = (0xD9, 0xDE, 0xE3), (0xA8, 0x9F, 0x91), (0xC3, 0xCA, 0xD2), (0x58, 0x5E, 0x66)
FD = '/usr/share/fonts/opentype/inter/'
NB = ' '


def font(sz, w='Regular'):
    return ImageFont.truetype(f'{FD}Inter-{w}.otf', int(sz * S))


def P(*v):
    return [int(x * S) for x in v]


def money(n):
    s = f'{n:,}'.replace(',', NB)
    return s + NB + '₽'


def load_cat():
    t = open(IDX, encoding='utf-8', errors='ignore').read()
    cat = {}
    for e in re.findall(r'\{"a":"[^{}]*\}', t):
        try:
            o = json.loads(e)
        except Exception:
            continue
        cat[o['a']] = o
    return cat


def thumb(art, tw, th):
    """Фото с сайта, обрезанное по изделию, в плитке tw×th (в единицах листа)."""
    im = Image.open(f'{IMG}/{art}.jpg').convert('RGB')
    bg = im.getpixel((6, 6))
    g = im.convert('L')
    # изделие = всё, что заметно светлее или цветнее фона; чёрная основа реек сливается с фоном — не страшно
    diff = Image.eval(g, lambda v: 255 if abs(v - sum(bg) // 3) > 26 else 0).filter(ImageFilter.MedianFilter(5))
    bb = diff.getbbox() or (0, 0, im.width, im.height)
    x0, y0, x1, y1 = bb
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw, bh = (x1 - x0) * 1.16, (y1 - y0) * 1.22
    ar = tw / th
    if bw / bh < ar:
        bw = bh * ar
    else:
        bh = bw / ar
    bw, bh = min(bw, im.width), min(bh, im.height)
    if bw / bh > ar:
        bw = bh * ar
    else:
        bh = bw / ar
    l = min(max(cx - bw / 2, 0), im.width - bw)
    t = min(max(cy - bh / 2, 0), im.height - bh)
    cr = im.crop((round(l), round(t), round(l + bw), round(t + bh))).resize((tw * S, th * S), Image.LANCZOS)
    mask = Image.new('L', cr.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cr.width - 1, cr.height - 1], radius=18 * S, fill=255)
    return cr, mask


def fit(d, s, w, sz, weight, lo=26):
    """Шрифт такого размера, чтобы строка влезла в ширину w."""
    while sz > lo:
        f = font(sz, weight)
        if d.textlength(s, font=f) <= w * S:
            return f
        sz -= 1
    return font(lo, weight)


def sheet(name, title, sub, rows, cat, rowh, note):
    HEAD, FOOT = 214, 190
    H = HEAD + rowh * len(rows) + FOOT
    im = Image.new('RGB', (W * S, H * S), GAL)
    d = ImageDraw.Draw(im)
    d.rectangle(P(0, 0, W, HEAD), fill=ANTH)
    d.text(P(56, 50), title, font=fit(d, title, W - 112, 64, 'SemiBold', 40), fill=GAL)
    d.text(P(58, 138), sub, font=fit(d, sub, W - 116, 31, 'Regular', 22), fill=SUBD)
    tw = 430
    th = min(rowh - 44, round(tw * 0.66))
    for i, r in enumerate(rows):
        art, head, line = r
        o = cat[art]
        y = HEAD + i * rowh
        if i:
            d.line(P(56, y, W - 56, y), fill=HAZE, width=S)
        cr, mask = thumb(art, tw, th)
        ty = y + (rowh - th) // 2
        im.paste(cr, (56 * S, ty * S), mask)
        x = 56 + tw + 36
        tw_text = W - 56 - x
        # артикул — плашка
        fa = font(25, 'Medium')
        lab = 'арт. ' + art
        lw = d.textlength(lab, font=fa) / S
        d.rounded_rectangle(P(x, ty + 2, x + lw + 28, ty + 44), radius=21 * S, fill=HAZE)
        d.text(P(x + 14, ty + 8), lab, font=fa, fill=ANTH)
        # название: одна или две строки
        yy = ty + 62
        for hl in head.split('\n'):
            d.text(P(x, yy), hl, font=fit(d, hl, tw_text, 38, 'SemiBold', 28), fill=ANTH)
            yy += 46
        d.text(P(x, yy + 4), line, font=fit(d, line, tw_text, 29, 'Regular', 22), fill=SUBL)
        # цена — внизу плитки
        fp = font(54, 'Bold')
        pr = money(o['r'])
        d.text(P(x, ty + th - 62), pr, font=fp, fill=ANTH)
        pw = d.textlength(pr, font=fp) / S
        d.text(P(x + pw + 14, ty + th - 36), 'за штуку', font=font(26), fill=SUBL)
    y = HEAD + rowh * len(rows)
    d.line(P(56, y + 14, W - 56, y + 14), fill=STONE, width=S)
    d.text(P(56, y + 36), 'Цена за 1 шт.  ·  Под заказ, срок 3–4 недели', font=font(28, 'SemiBold'), fill=ANTH)
    d.text(P(56, y + 80), 'Материал — дюрополимер (ударопрочный полистирол), влагостойкий.', font=font(25), fill=SUBL)
    d.text(P(56, y + 116), note, font=font(25), fill=SUBL)
    d.text(P(56, y + 152), 'Изображения — фото образцов и 3D-визуализация.', font=font(21), fill=STONE)
    im = im.resize((FINAL_W, round(H * FINAL_W / W)), Image.LANCZOS)
    path = f'{OUT}/{name}.jpg'
    im.save(path, quality=90, subsampling=0, optimize=True)
    return path, im.size


def size(o, lam=None):
    L = f"{o['l'] / 1000:g}".replace('.', ',')
    s = f"{o['w']} × {o['t']} мм, длина {L} м"
    return (f'{lam} · ' + s) if lam else s


def main():
    cat = load_cat()
    dec = lambda a: re.search(r'«([^»]+)»', cat[a]['n']).group(1)
    cap = lambda s: s[0].upper() + s[1:]
    lam = {'2': '2 широкие ламели', '3': '3 ламели', '5': '5 узких ламелей'}
    slats = ['3-7', '3-9', '3-15', '2-7', '5-6', '5-10']
    rows1 = [(a, cap(dec(a)), size(cat[a], lam[a[0]])) for a in slats]
    shape = {'A910': 'Частые полукруглые\nрейки', 'A902': 'Полукруглые рейки\n(каннелюры)',
             'A907': 'Широкие ламели\nс тонкими швами', 'A912': 'Частые треугольные\nграни (зигзаг)'}
    rows2 = [(a, shape[a], size(cat[a])) for a in ['A910', 'A902', 'A907', 'A912']]
    rows3 = [('A703', 'Плинтус напольный\n80 мм', size(cat['A703'])),
             ('A005', 'Плинтус напольный\n80 мм', size(cat['A005'])),
             ('A704', 'Плинтус напольный\n100 мм', size(cat['A704'])),
             ('A35', 'Молдинг для стен\n25 мм', size(cat['A35'])),
             ('A157', 'Молдинг для стен\n30 мм', size(cat['A157']))]
    res = []
    res.append(sheet('1-reiki-pod-derevo', 'Рейки под дерево', 'Стеновые панели с готовым декором — красить не нужно', rows1, cat, 282,
                     'Декор под дерево на чёрной основе. Крепятся на монтажный клей.'))
    res.append(sheet('2-belye-paneli', 'Белые реечные панели', 'Стеновые панели под покраску — красятся в любой цвет', rows2, cat, 336,
                     'Длина 3 м — от пола до потолка без стыка. Крепятся на монтажный клей.'))
    res.append(sheet('3-plintusy-moldingi', 'Плинтусы и молдинги', 'Белые, под покраску, длина 2 м', rows3, cat, 326,
                     'Крепятся на монтажный клей (жидкие гвозди).'))
    for p, s in res:
        print(p, s)
    for name, rr in (('1', rows1), ('2', rows2), ('3', rows3)):
        for a, h, l in rr:
            print(name, a, '|', h.replace('\n', ' '), '|', l, '|', cat[a]['r'])


main()
