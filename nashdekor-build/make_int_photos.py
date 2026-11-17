"""Кадры режима «Фото» для расчёта стены: из рендеров ветки paneli-render (out/f_<сцена>_<артикул>/…jpg) → 0f7s1eez/img/int/<сцена>/<артикул>.jpg
и маска стены (f_<сцена>_mask) → img/int/<сцена>/mask.png (белая, альфа = стена).
    python3 make_int_photos.py /home/claude/render/out [префикс=f]
Сцены: tv — ТВ-зона, lv — гостиная, cl — крупно. Артикул в имени: строчными, без пробелов, «/» → «-» (gs1, a201-2, 3-7)."""
import os, sys, re
from PIL import Image
src = sys.argv[1]; pre = sys.argv[2] if len(sys.argv) > 2 else 'f'
dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '0f7s1eez', 'img', 'int')
n = 0
for d in sorted(os.listdir(src)):
    m = re.match(rf'^{pre}_(tv|lv|cl)_(.+)$', d)
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
        im.convert('RGB').save(os.path.join(dst, sc, key + '.jpg'), quality=82, optimize=True, progressive=True)
    n += 1
print('кадров:', n, '→', os.path.normpath(dst))
