# Собирает готовые кадры: обработка «как с фотоаппарата» + подпись, понятные имена файлов.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post import process

CAP = '3D-визуализация'
CAP_P = '3D-визуализация · панель окрашена, продаётся белой под покраску'
MAP = {
    'f1': ('3-7 — 1 гостиная', CAP), 'a37_arch': ('3-7 — 2 арка', CAP), 'a37_close': ('3-7 — 3 у тумбы', CAP),
    'a37_macro': ('3-7 — 4 крупно', CAP), 'a37_sample2': ('3-7 — 5 образец', CAP),
    'b315_diag': ('3-15 — 1 гостиная', CAP), 'b315_arch': ('3-15 — 2 арка', CAP), 'b315_mid': ('3-15 — 3 у тумбы', CAP),
    'b315_macro': ('3-15 — 4 крупно', CAP), 'b315_sample2': ('3-15 — 5 образец', CAP),
    'c39_tv': ('3-9 — 1 ТВ-зона', CAP), 'c39_arch': ('3-9 — 2 арка', CAP), 'c39_close': ('3-9 — 3 у тумбы', CAP),
    'c39_macro': ('3-9 — 4 крупно', CAP), 'c39_sample2': ('3-9 — 5 образец', CAP),
    'd910_mid': ('A910 — 1 окрашена, у тумбы', CAP_P), 'd910_white': ('A910 — 2 белая, гостиная', CAP),
    'd910_arch': ('A910 — 3 арка, окрашена', CAP_P), 'd910_macro': ('A910 — 4 крупно', CAP), 'd910_sample2': ('A910 — 5 образец', CAP),
    'e703_close': ('A703 — 1 крупно', CAP), 'e703_wide': ('A703 — 2 в комнате', CAP), 'e703_light': ('A703 — 3 светлая стена', CAP),
}
OUT = '/home/claude/out_img/final'
os.makedirs(OUT, exist_ok=True)
only = sys.argv[1:]
for name, (title, cap) in MAP.items():
    if only and name not in only:
        continue
    src = f'out/{name}/{name}.jpg'
    if not os.path.exists(src):
        print('нет', name)
        continue
    dst = f'{OUT}/{title}.jpg'
    print(name, '->', dst, process(src, dst, cap), round(os.path.getsize(dst) / 1e6, 2), 'МБ')
