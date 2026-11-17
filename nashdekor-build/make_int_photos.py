"""Кадры галереи «в интерьере» для главной: из рендеров ветки paneli-render (out/g_<сцена>_<артикул>/…jpg) → 0f7s1eez/img/int/<сцена>/<артикул>.jpg,
маска панелей (g_<сцена>_mask) → img/int/<сцена>/mask.png (белая, альфа = панели), и строка /*INT*/…/*/INT*/ в index.html — какие кадры есть.
    python3 make_int_photos.py /home/claude/render/out
Сцены: tv, tv1, tv2, sofa, bed, hall, cor, cl. Артикул в имени: строчными, без пробелов, «/» → «-» (gs1, a201-2, 3-7).
Сцена попадает в список, только если у неё есть маска. После запуска: поднять INT_V в index.html (если кадры менялись) и build.py."""
import os, sys, re, json
from PIL import Image
src = sys.argv[1]
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '0f7s1eez')
dst = os.path.join(root, 'img', 'int'); n = 0
for d in sorted(os.listdir(src)):
    m = re.match(r'^g_([a-z0-9]+)_(.+)$', d)
    f = os.path.join(src, d, d + '.jpg')
    if not m or not os.path.exists(f): continue
    sc, key = m.group(1), m.group(2).lower()
    os.makedirs(os.path.join(dst, sc), exist_ok=True)
    im = Image.open(f)
    if key == 'mask':
        a = im.convert('L').point(lambda v: 0 if v < 6 else 255 if v > 249 else v)
        out = Image.new('LA', im.size, 255); out.putalpha(a)
        out.save(os.path.join(dst, sc, 'mask.png'), optimize=True)
    else:
        im.convert('RGB').save(os.path.join(dst, sc, key + '.jpg'), quality=80, optimize=True, progressive=True)
    n += 1
INT = {}
for sc in sorted(os.listdir(dst)):
    p = os.path.join(dst, sc)
    if os.path.isdir(p) and os.path.exists(os.path.join(p, 'mask.png')):
        INT[sc] = sorted(f[:-4] for f in os.listdir(p) if f.endswith('.jpg'))
ix = os.path.join(root, 'index.html'); s = open(ix, encoding='utf-8').read()
s2 = re.sub(r'/\*INT\*/.*?/\*/INT\*/', lambda _: '/*INT*/const INT = ' + json.dumps(INT, ensure_ascii=False, separators=(',', ':')) + ';/*/INT*/', s, count=1, flags=re.S)
assert s2 != s or '/*INT*/' in s
open(ix, 'w', encoding='utf-8').write(s2)
print('кадров обработано:', n, '| сцены:', {k: len(v) for k, v in INT.items()})
