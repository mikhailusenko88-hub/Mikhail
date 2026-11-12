# Набор фото A910 для Авито v5 (12.11.2026): модель по живому образцу (валик 6,5…12 мм, сзади канавки, срез белый зернистый)
# Живое фото стены Михаил в объявление не берёт (12.11: «в таком качестве не использую»). Остальные артикулы — v4 (панели) и v3 (плинтус).
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post import process

CAP = '3D-визуализация'
CAP_P = '3D-визуализация · панель окрашена, продаётся белой под покраску'
ITEMS = [('new:x910_angle', CAP_P), 'new:x910_white',
         ('new:x910_arch', CAP_P), 'new:x910_macro', 'new:x910_two', 'new:x910_cut', 'old:6', 'scheme']
art, dst = 'A910', 'avito_foto/A910v5'
os.makedirs(dst, exist_ok=True)
miss = []
for i, it in enumerate(ITEMS, 1):
    cap = CAP
    if isinstance(it, tuple):
        it, cap = it
    out = f'{dst}/{i}.jpg'
    if it == 'scheme':
        subprocess.run([sys.executable, 'scheme_brand.py', '--nologo', art, out], check=True)
        continue
    kind, name = it.split(':')
    if kind == 'old':
        shutil.copy(f'avito_foto/{art}/{name}.jpg', out)
    elif kind == 'photo':
        process(name, out, cap, vignette=0, grain=0, sharpen=0)
    else:
        src = f'out/{name}/{name}.jpg'
        if not os.path.exists(src):
            miss.append(name)
            continue
        process(src, out, cap, grain=1.0, vignette=0.06)
print(art, sorted(os.listdir(dst)))
print('нет кадров:', miss or 'все на месте')
