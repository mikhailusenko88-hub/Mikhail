# Картинки для очереди автопостинга канала «Наш декор» в MAX: 3D-кадры из наборов avito_foto (ветка paneli-render)
# → <сайт>/img/max/q/*.jpg (1600 px по ширине). Посты и расписание — bot/channel_queue.json (ветка server).
# python3 make_max_queue.py <папка сайта 0f7s1eez> <папка рендеров paneli-render>
import os, sys
from PIL import Image

SITE, RENDER = sys.argv[1], sys.argv[2]
OUT = f'{SITE}/img/max/q'
A = RENDER + '/avito_foto/'
PICK = {  # имя в очереди: кадр
    'a910_1': 'A910v6/3', 'a910_2': 'A910v6/6', 'a910_3': 'A910v6/8', 'a910_4': 'A910v6/4', 'a910_5': 'A910v6/5',
    'a703_1': 'A703v5/6', 'a703_2': 'A703v5/3', 'a703_3': 'A703v5/8', 'a703_paint': 'A703v5/4', 'a703_beige': 'A703v5/5',
    '3-9_1': '3-9v5/3', '3-9_2': '3-9v5/6', '3-9_3': '3-9v5/8',
    '3-15_1': '3-15v5/3', '3-15_2': '3-15v5/6', '3-15_3': '3-15v5/8', '3-15_4': '3-15v5/4',
    '3-7_1': '3-7v5/3', '3-7_2': '3-7v5/6', '3-7_3': '3-7v5/8',
}
os.makedirs(OUT, exist_ok=True)
for name, src in PICK.items():
    im = Image.open(f'{A}{src}.jpg').convert('RGB')
    if im.width > 1600:
        im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    im.save(f'{OUT}/{name}.jpg', quality=86, optimize=True, progressive=True)
print('готово:', len(PICK), 'картинок в', OUT)
