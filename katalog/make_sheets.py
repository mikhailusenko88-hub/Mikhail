# Листы каталога «для чата Авито»: вертикальные картинки под экран телефона, все позиции каталога с ценами.
# Фирменный стиль (Inter, «Антрацит», «Галерея»), без марки поставщика, без названия магазина, без контактов и ссылок.
# Данные — из каталога сайта (CAT и PHOTO на главной странице, ветка mebel, 0f7s1eez/index.html), фото — img/2x/.
# Запуск: python3 make_sheets_all.py <index.html сайта> <папка с фото 2x> <папка для листов> [цены.json]
#   цены.json — необязательно: {"артикул": цена} из CRM (/api/catalog); если дан, цена берётся оттуда.
# Рядом с листами пишется manifest.json: файл, раздел, название, позиции и цены на момент сборки.
import json, re, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

IDX, IMG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PRICES = json.load(open(sys.argv[4], encoding='utf-8')) if len(sys.argv) > 4 else {}
S = 2                      # рисуем вдвое крупнее, потом уменьшаем
W = 1080
FINAL_W = 1125
ANTH, GAL, BLUE = (0x26, 0x29, 0x2E), (0xF8, 0xF8, 0xF6), (0x7E, 0x97, 0xAD)
HAZE, STONE, SUBD, SUBL = (0xD9, 0xDE, 0xE3), (0xA8, 0x9F, 0x91), (0xC3, 0xCA, 0xD2), (0x58, 0x5E, 0x66)
TILE = (0x24, 0x27, 0x2E)
FD = '/usr/share/fonts/opentype/inter/'
NB = ' '

s = open(IDX, encoding='utf-8', errors='ignore').read()
CAT = json.loads(s[s.find('const CAT=') + len('const CAT='):s.find('];', s.find('const CAT=')) + 1])
PHOTO = json.loads(re.search(r'const PHOTO = (\{.*?\});', s).group(1))
BY = {x['a']: x for x in CAT}
for a, p in PRICES.items():
    if a in BY:
        BY[a]['r'] = int(p)


def font(sz, w='Regular'):
    return ImageFont.truetype(f'{FD}Inter-{w}.otf', int(sz * S))


def P(*v):
    return [int(x * S) for x in v]


def money(n):
    return f'{n:,}'.replace(',', NB) + NB + '₽'


def thumb(art, tw, th):
    """Фото с сайта, обрезанное по изделию, в плитке tw×th (в единицах листа). Нет фото — плитка с надписью."""
    ph = PHOTO.get(art)
    mask = Image.new('L', (tw * S, th * S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, tw * S - 1, th * S - 1], radius=18 * S, fill=255)
    if not ph:
        cr = Image.new('RGB', (tw * S, th * S), TILE)
        ImageDraw.Draw(cr).text((tw * S // 2, th * S // 2), 'Фото — по запросу', font=font(26), fill=SUBD, anchor='mm')
        return cr, mask
    im = Image.open(f'{IMG}/{ph}').convert('RGB')
    bg = im.getpixel((6, 6))
    g = im.convert('L')
    # изделие = всё, что заметно светлее или цветнее фона; чёрная основа реек сливается с фоном — не страшно
    diff = Image.eval(g, lambda v: 255 if abs(v - sum(bg) // 3) > 26 else 0).filter(ImageFilter.MedianFilter(5))
    x0, y0, x1, y1 = diff.getbbox() or (0, 0, im.width, im.height)
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
    return cr, mask


def fit(d, text, w, sz, weight, lo=24):
    """Шрифт такого размера, чтобы строка влезла в ширину w."""
    while sz > lo:
        f = font(sz, weight)
        if d.textlength(text, font=f) <= w * S:
            return f
        sz -= 1
    return font(lo, weight)


def wrap2(d, text, w, sz=38, weight='SemiBold'):
    """Название в одну или две строки."""
    f = font(sz, weight)
    if d.textlength(text, font=f) <= w * S:
        return [text]
    words, best = text.split(' '), None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        m = max(d.textlength(a, font=f), d.textlength(b, font=f))
        if best is None or m < best[0]:
            best = (m, [a, b])
    return best[1]


def sheet(name, title, sub, rows, note):
    """rows: [(артикул, [строки названия], строка размера)]"""
    two = any(len(h) > 1 for _, h, _ in rows)
    rowh = 326 if two else 282
    HEAD, FOOT = 214, 190
    H = HEAD + rowh * len(rows) + FOOT
    im = Image.new('RGB', (W * S, H * S), GAL)
    d = ImageDraw.Draw(im)
    d.rectangle(P(0, 0, W, HEAD), fill=ANTH)
    d.text(P(56, 50), title, font=fit(d, title, W - 112, 64, 'SemiBold', 40), fill=GAL)
    d.text(P(58, 138), sub, font=fit(d, sub, W - 116, 31, 'Regular', 20), fill=SUBD)
    tw = 430
    th = min(rowh - 44, round(tw * 0.66))
    for i, (art, head, line) in enumerate(rows):
        o = BY[art]
        y = HEAD + i * rowh
        if i:
            d.line(P(56, y, W - 56, y), fill=HAZE, width=S)
        cr, mask = thumb(art, tw, th)
        ty = y + (rowh - th) // 2
        im.paste(cr, (56 * S, ty * S), mask)
        x = 56 + tw + 36
        wt = W - 56 - x
        fa = font(25, 'Medium')
        lab = 'арт. ' + art
        lw = d.textlength(lab, font=fa) / S
        d.rounded_rectangle(P(x, ty + 2, x + lw + 28, ty + 44), radius=21 * S, fill=HAZE)
        d.text(P(x + 14, ty + 8), lab, font=fa, fill=ANTH)
        yy = ty + 62
        for hl in head:
            d.text(P(x, yy), hl, font=fit(d, hl, wt, 38, 'SemiBold', 26), fill=ANTH)
            yy += 46
        d.text(P(x, yy + 4), line, font=fit(d, line, wt, 29, 'Regular', 21), fill=SUBL)
        fp = font(54, 'Bold')
        pr = money(o['r'])
        d.text(P(x, ty + th - 62), pr, font=fp, fill=ANTH)
        pw = d.textlength(pr, font=fp) / S
        d.text(P(x + pw + 14, ty + th - 36), 'за штуку', font=font(26), fill=SUBL)
    y = HEAD + rowh * len(rows)
    d.line(P(56, y + 14, W - 56, y + 14), fill=STONE, width=S)
    d.text(P(56, y + 36), 'Цена за 1 шт.  ·  Под заказ, срок 3–4 недели', font=font(28, 'SemiBold'), fill=ANTH)
    d.text(P(56, y + 80), 'Материал — дюрополимер (ударопрочный полистирол), влагостойкий.', font=font(25), fill=SUBL)
    d.text(P(56, y + 116), note, font=fit(d, note, W - 112, 25, 'Regular', 18), fill=SUBL)
    d.text(P(56, y + 152), 'Изображения — фото образцов и 3D-визуализация.', font=font(21), fill=STONE)
    im = im.resize((FINAL_W, round(H * FINAL_W / W)), Image.LANCZOS)
    im.save(f'{OUT}/{name}.jpg', quality=86, subsampling=2, optimize=True, progressive=True)
    return im.size


def size(o, pre=''):
    L = f"{o['l'] / 1000:g}".replace('.', ',')
    return f"{pre}{o['w']} × {o['t']} мм, длина {L} м"


def chunks(items, per=6):
    """Поровну по листам, не больше per на лист."""
    n = -(-len(items) // per)
    base, extra = divmod(len(items), n)
    out, i = [], 0
    for k in range(n):
        m = base + (1 if k < extra else 0)
        out.append(items[i:i + m]); i += m
    return out


def cap(t):
    return t[:1].upper() + t[1:]


GLUE = 'Крепятся на монтажный клей (жидкие гвозди).'
d0 = ImageDraw.Draw(Image.new('RGB', (10, 10)))
WT = W - 56 - (56 + 430 + 36)
groups = []   # (ключ, раздел, заголовок листа, подзаголовок, позиции, как подписать, примечание, метка в названии)

# 1. Рейки под дерево — по сериям (число ламелей)
LAM = {'3': '3 ламели', '2': '2 широкие ламели', '5': '5 узких ламелей'}
num = lambda a: [int(x) for x in re.findall(r'\d+', a)]
for ser in ('3', '2', '5'):
    items = sorted([x for x in CAT if x['c'] == 'color' and x['a'].startswith(ser + '-')], key=lambda x: num(x['a']))
    groups.append(('color', 'Рейки под дерево', 'Рейки под дерево', f'Готовый декор — красить не нужно · {LAM[ser]}', items,
                   lambda o: ([cap(re.search(r'«([^»]+)»', o['n']).group(1))], size(o, LAM[o['a'][0]] + ' · ')),
                   'Декор на чёрной основе. ' + GLUE, LAM[ser]))

# 2. Белые панели под покраску
pan = [x for x in CAT if x['c'] == 'panel']
p3 = sorted([x for x in pan if x['a'].startswith('A9')], key=lambda x: num(x['a']))
rest = [x for x in pan if not x['a'].startswith('A9')]
shape = lambda o: (wrap2(d0, cap(o['d'].split(',')[0].strip()), WT), size(o))
groups.append(('panel', 'Белые панели под покраску', 'Белые реечные панели', 'Под покраску — красятся в любой цвет · длина 3 м', p3, shape,
               'Длина 3 м — от пола до потолка без стыка. ' + GLUE, 'длина 3 м'))
groups.append(('panel', 'Белые панели под покраску', 'Белые реечные панели', 'Под покраску — красятся в любой цвет', rest, shape, GLUE, 'другие размеры'))

# 3. Плинтусы напольные — по высоте
pl = sorted([x for x in CAT if x['c'] == 'plinth'], key=lambda x: (x['w'], x['r']))
led = lambda o: 'с подсветкой' in o['n']
plh = lambda o: (['Плинтус напольный', f"{o['w']} мм" + (', с подсветкой' if led(o) else '')], size(o))
for lo, hi in ((0, 80), (81, 100), (101, 999)):
    items = [x for x in pl if lo <= x['w'] <= hi]
    rng = f"{items[0]['w']}–{items[-1]['w']} мм"
    groups.append(('plinth', 'Плинтусы напольные', 'Плинтусы напольные', f'Белые, под покраску · высота {rng} · длина 2 м', items, plh, GLUE, rng))

# 4. Потолочные плинтусы и уголки
co = sorted([x for x in CAT if x['c'] == 'cornice'], key=lambda x: x['r']) + sorted([x for x in CAT if x['c'] == 'corner'], key=lambda x: x['w'])
coh = lambda o: ((['Потолочный плинтус'] + (['с подсветкой'] if led(o) else [])) if o['c'] == 'cornice' else ['Уголок декоративный'], size(o))
groups.append(('cornice', 'Потолочные плинтусы и уголки', 'Потолочные плинтусы и уголки', 'Белые, под покраску · длина 2 м', co, coh, GLUE, ''))

# 5. Молдинги — по ширине
mo = sorted([x for x in CAT if x['c'] == 'mold'], key=lambda x: (x['w'], num(x['a'])))


def moh(o):
    extra = ', с кабель-каналом' if 'кабель-каналом' in o['n'] else (', универсальный' if 'универсальный' in o['n'] else '')
    return (['Молдинг для стен', f"{o['w']} мм{extra}"], size(o))


groups.append(('mold', 'Молдинги для стен', 'Молдинги для стен', 'Белые, под покраску', mo, moh, GLUE, ''))

manifest, n = [], 0
for key, section, title, sub, items, how, note, tag in groups:
    parts = chunks(items)
    for k, part in enumerate(parts, 1):
        n += 1
        rows = [(o['a'],) + how(o) for o in part]
        if key == 'mold':
            rng = f"{part[0]['w']}–{part[-1]['w']} мм"
            sub_k, tag_k = f'{sub} · ширина {rng}', rng
        else:
            sub_k, tag_k = sub, tag
        if len(parts) > 1:
            sub_k += f' · лист {k} из {len(parts)}'
        name = f'avito-{n:02d}'
        sz = sheet(name, title, sub_k, rows, note)
        label = section + (f' — {tag_k}' if tag_k else '') + (f', лист {k} из {len(parts)}' if len(parts) > 1 else '')
        manifest.append({'n': n, 'file': name + '.jpg', 'section': section, 'key': key, 'title': f'{n:02d}. {label}',
                         'items': [[o['a'], o['r']] for o in part], 'size': list(sz)})
        print(f"{n:02d}", label, '|', ' '.join(f"{o['a']}={o['r']}" for o in part), '|', sz)
json.dump({'sheets': manifest}, open(f'{OUT}/manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
allp = [a for m in manifest for a, _ in m['items']]
print('листов', len(manifest), '| позиций', len(allp), '| разных', len(set(allp)), '| в каталоге', len(CAT),
      '| не попали:', [x['a'] for x in CAT if x['a'] not in allp])
