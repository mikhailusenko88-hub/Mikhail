# Собирает наборы фото для Авито (12.11.2026, переделка «резко и со срезом»): avito_foto/<артикул>v3/1..N.jpg
# Новые кадры — из out/<имя>/<имя>.jpg (обработка post.process), старые — из avito_foto/<артикул>/<n>.jpg как есть.
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post import process
from main_inset import make as inset

CAP = '3D-визуализация'
CAP_P = '3D-визуализация · панель окрашена, продаётся белой под покраску'
CAP_G = '3D-визуализация · плинтус окрашен в цвет стены, продаётся белым под покраску'
SETS = {
    'A703': ['inset:k703_corner', 'new:h703_top', 'new:f703_cut', ('new:k703_green', CAP_G), 'new:k703_beige', 'old:2', 'old:4', 'old:5'],
    '3-7': ['old:1', 'old:2', 'new:n37_close', 'new:n37_macro', 'new:f37_stack', 'new:f37_cut', 'old:6', 'old:7'],
    '3-15': ['old:1', 'old:2', 'new:n315_mid', 'new:n315_macro', 'new:f315_stack', 'new:f315_cut', 'old:6', 'old:7'],
    '3-9': ['old:1', 'old:2', 'new:n39_close', 'new:n39_macro', 'new:f39_stack', 'new:f39_cut', 'old:6', 'old:7'],
    'A910': [('new:n910_mid', CAP_P), 'old:2', 'old:3', 'new:n910_macro', 'new:f910_stack', 'new:f910_cut', 'old:6', 'old:7'],
}
SUF = 'v3'
miss = []
for art, items in SETS.items():
    dst = f'avito_foto/{art}{SUF}'
    os.makedirs(dst, exist_ok=True)
    for i, it in enumerate(items, 1):
        cap = CAP
        if isinstance(it, tuple):
            it, cap = it
        kind, name = it.split(':')
        out = f'{dst}/{i}.jpg'
        if kind == 'old':
            shutil.copy(f'avito_foto/{art}/{name}.jpg', out)
            continue
        src = f'out/{name}/{name}.jpg'
        if not os.path.exists(src):
            miss.append(name)
            continue
        if kind == 'inset':
            process(src, '/tmp/_inset.jpg', caption=None, grain=1.0, vignette=0.06)
            inset('/tmp/_inset.jpg', out, 0.5)
        else:
            process(src, out, cap, grain=1.0, vignette=0.06)
    print(art, sorted(os.listdir(dst)))
print('нет кадров:', miss or 'все на месте')
