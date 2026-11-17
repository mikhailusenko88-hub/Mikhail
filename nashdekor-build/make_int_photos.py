"""Кадры «панели в интерьере»: из рендеров ветки paneli-render (out/g_<сцена>_<артикул>/…jpg) →
    0f7s1eez/img/int/<сцена>/<артикул>.jpg      — кадр 1350×900 (качество 80)
    0f7s1eez/img/int/<сцена>/t/<артикул>.jpg    — уменьшенный 450×300 для сеток
    0f7s1eez/img/int/<сцена>/mask.png           — маска панелей (белая, альфа = панели) для перекраски в браузере
    0f7s1eez/img/int/manifest.json              — какие кадры есть: {"v": версия, "scenes": {сцена: [артикулы]}}
и, если в index.html есть строка /*INT*/…/*/INT*/ (галерея на главной), обновляет её.

    python3 make_int_photos.py /home/claude/render/out [--clean]      (--clean — сначала удалить img/int целиком)

Сцены: tv, tv1, tv2, tvc, sofa, sofa1, sofa2, bed, bed1, hall, half, desk, cor, cl; крупные планы — tvd, sofad, bedd, halld, deskd, cord. Артикул в имени: строчными, без пробелов,
«/» → «-» (gs1, a201-2, 3-7). Сцена попадает в список, только если у неё есть маска. Страница-проба «панель в интерьере» — /vizual/ (карточки панелей для неё берутся из каталога главной), все кадры по сценам — /vizual/sceny/."""
import os, sys, re, json, shutil, time
from PIL import Image

def door_corner(im):
    """Прихожая (hall, half): в рендерах до 17.11 на углу наличника двери (справа вверху) чёрный ромбик — совпавшие грани
    двух планок. Закрашивается цветом стойки наличника под ним (тот же столбец кадра). В новых рендерах ромбика нет — кадр не меняется."""
    import numpy as np
    a = np.asarray(im).copy()
    h, w = a.shape[:2]
    x0, x1, y1 = int(w * .952), int(w * .993), int(h * .078)
    d = a[:y1, x0:x1].astype(int).sum(2) < 200
    if d.sum() < 40:
        return im
    for _ in range(2):                                      # край ромбика со сглаживанием — на 2 точки шире
        e = d.copy(); e[1:] |= d[:-1]; e[:-1] |= d[1:]; e[:, 1:] |= d[:, :-1]; e[:, :-1] |= d[:, 1:]; d = e
    for x in np.unique(np.nonzero(d)[1]):
        col = np.nonzero(d[:, x])[0]
        yb = col.max()
        a[col, x0 + x] = a[yb + 4:yb + 22, x0 + x].mean(0)
    return Image.fromarray(a)


src = sys.argv[1]
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '0f7s1eez')
dst = os.path.join(root, 'img', 'int')
if '--clean' in sys.argv and os.path.isdir(dst):
    shutil.rmtree(dst)
n = 0
for d in sorted(os.listdir(src)):
    m = re.match(r'^g_([a-z0-9]+)_(.+)$', d)
    f = os.path.join(src, d, d + '.jpg')
    if not m or not os.path.exists(f):
        continue
    sc, key = m.group(1), m.group(2).lower()
    os.makedirs(os.path.join(dst, sc, 't'), exist_ok=True)
    out = os.path.join(dst, sc, 'mask.png' if key == 'mask' else key + '.jpg')
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(f):
        continue                                             # уже обработан
    im = Image.open(f)
    if key == 'mask':
        a = im.convert('L').point(lambda v: 0 if v < 6 else 255 if v > 249 else v)
        o = Image.new('LA', im.size, 255)
        o.putalpha(a)
        o.save(out, optimize=True)
    else:
        im = im.convert('RGB')
        if sc in ('hall', 'half'):
            im = door_corner(im)
        im.save(out, quality=80, optimize=True, progressive=True)
        im.resize((450, 300), Image.LANCZOS).save(os.path.join(dst, sc, 't', key + '.jpg'), quality=72, optimize=True)
    n += 1
INT = {}
for sc in sorted(os.listdir(dst)) if os.path.isdir(dst) else []:
    p = os.path.join(dst, sc)
    if os.path.isdir(p) and os.path.exists(os.path.join(p, 'mask.png')):
        ks = sorted(f[:-4] for f in os.listdir(p) if f.endswith('.jpg'))
        if ks:                                  # сцена без единого кадра (посчитана только маска) на странице не показывается
            INT[sc] = ks
mf = os.path.join(dst, 'manifest.json')
try:
    old = json.load(open(mf, encoding='utf-8'))
except Exception:  # noqa
    old = {}
if n or old.get('scenes') != INT:       # версия меняется только вместе с кадрами: по ней браузер решает, качать ли картинки заново
    json.dump({'v': time.strftime('%m%d%H%M'), 'scenes': INT}, open(mf, 'w'), ensure_ascii=False, separators=(',', ':'))
ix = os.path.join(root, 'index.html')
s = open(ix, encoding='utf-8').read()
if '/*INT*/' in s:
    s = re.sub(r'/\*INT\*/.*?/\*/INT\*/', lambda _: '/*INT*/const INT = ' + json.dumps(INT, ensure_ascii=False, separators=(',', ':')) + ';/*/INT*/', s, count=1, flags=re.S)
    open(ix, 'w', encoding='utf-8').write(s)
# карточки панелей для страницы-пробы /vizual/ — из каталога главной: артикул, вид, размеры, фото
vz = os.path.join(root, 'vizual', 'index.html')
if os.path.exists(vz) and 'const CAT=' in s:
    dec = json.JSONDecoder()
    cat = dec.raw_decode(s, s.index('const CAT=') + len('const CAT='))[0]
    photo = dec.raw_decode(s, s.index('const PHOTO = ') + len('const PHOTO = '))[0]
    pv = re.search(r'const PHOTO_V = "([^"]*)"', s).group(1)
    cards = [{'a': x['a'], 'c': x['c'], 'd': x['d'].split(',')[0], 'w': x['w'], 't': x['t'], 'l': x['l'], 'p': photo.get(x['a'], '')}
             for x in cat if x['c'] in ('panel', 'color')]
    v = open(vz, encoding='utf-8').read()
    v2 = re.sub(r'/\*CARDS\*/.*?/\*/CARDS\*/', lambda _: '/*CARDS*/const CARDS = ' + json.dumps(cards, ensure_ascii=False, separators=(',', ':')) + f', PHOTO_V = "{pv}";/*/CARDS*/', v, count=1, flags=re.S)
    if v2 != v:
        open(vz, 'w', encoding='utf-8').write(v2)
print('новых кадров:', n, '| сцены:', {k: len(v) for k, v in INT.items()})
