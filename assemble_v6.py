# Набор фото плинтуса A703 для Авито v4 (12.11.2026): срез белый зернистый, как у живого образца A910
# (замечание Михаила: «у плинтуса гладкий край, а он такой же, как на белом 910 — переделай»).
# Кадры 2 (отрезки на полу) и 3 (срез крупно) — новые; остальные — из A703v3.
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post import process

NEW = {2: 'm703_top', 3: 'm703_cut'}
src_dir, dst = 'avito_foto/A703v3', 'avito_foto/A703v4'
os.makedirs(dst, exist_ok=True)
miss = []
for i in range(1, 9):
    out = f'{dst}/{i}.jpg'
    if i in NEW:
        src = f'out/{NEW[i]}/{NEW[i]}.jpg'
        if not os.path.exists(src):
            miss.append(NEW[i])
            continue
        process(src, out, '3D-визуализация', grain=1.0, vignette=0.06)
    else:
        shutil.copy(f'{src_dir}/{i}.jpg', out)
print('A703', sorted(os.listdir(dst)))
print('нет кадров:', miss or 'все на месте')
