# Наборы фото для Авито v4 (12.11.2026): реечные панели пересняты по живому образцу (рейка 29,5 / паз 10,5, полый профиль,
# вспененный срез), A910 — окрашенная под углом. Плинтус A703 не менялся (остаётся avito_foto/A703v3).
# new — out/<имя>/<имя>.jpg через post.process; old — avito_foto/<артикул>/<n>.jpg; v3 — avito_foto/<артикул>v3/<n>.jpg; scheme — схема заново.
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post import process

CAP = '3D-визуализация'
CAP_P = '3D-визуализация · панель окрашена, продаётся белой под покраску'
SETS = {
    '3-7': ['new:w37_main', 'new:w37_arch', 'new:w37_close', 'new:w37_macro', 'new:w37_two', 'new:w37_cut', 'old:6', 'scheme'],
    '3-15': ['new:w315_diag', 'new:w315_arch', 'new:w315_mid', 'new:w315_macro', 'new:w315_two', 'new:w315_cut', 'old:6', 'scheme'],
    '3-9': ['new:w39_tv', 'new:w39_arch', 'new:w39_close', 'new:w39_macro', 'new:w39_two', 'new:w39_cut', 'old:6', 'scheme'],
    'A910': [('new:w910_angle', CAP_P), 'v3:2', 'v3:3', 'v3:4', 'v3:5', 'v3:6', 'v3:7', 'v3:8'],
}
SUF = 'v4'
miss = []
for art, items in SETS.items():
    dst = f'avito_foto/{art}{SUF}'
    os.makedirs(dst, exist_ok=True)
    for i, it in enumerate(items, 1):
        cap = CAP
        if isinstance(it, tuple):
            it, cap = it
        out = f'{dst}/{i}.jpg'
        if it == 'scheme':
            subprocess.run([sys.executable, 'scheme_brand.py', '--nologo', art, out, f'out/p10/decor_{art}.jpg'], check=True)
            continue
        kind, name = it.split(':')
        if kind == 'old':
            shutil.copy(f'avito_foto/{art}/{name}.jpg', out)
        elif kind == 'v3':
            shutil.copy(f'avito_foto/{art}v3/{name}.jpg', out)
        else:
            src = f'out/{name}/{name}.jpg'
            if not os.path.exists(src):
                miss.append(name)
                continue
            process(src, out, cap, grain=1.0, vignette=0.06)
    print(art, sorted(os.listdir(dst)))
print('нет кадров:', miss or 'все на месте')
