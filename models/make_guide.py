# Инструкция к архиву 3D-моделей в фирменном стиле «Наш декор» (PDF, A4) + «Как пользоваться.txt».
# python3 make_guide.py <папка «Наш декор — 3D-модели»>
import os, sys, glob, json
from PIL import Image, ImageDraw, ImageFont

ROOT = sys.argv[1]
ANTH, GAL, BLUE = (0x26, 0x29, 0x2E), (0xF8, 0xF8, 0xF6), (0x7E, 0x97, 0xAD)
HAZE, STONE, SUBD, SUBL = (0xD9, 0xDE, 0xE3), (0xA8, 0x9F, 0x91), (0xC3, 0xCA, 0xD2), (0x58, 0x5E, 0x66)
FD = '/usr/share/fonts/opentype/inter/'
LOGO = '/home/claude/brand/brand/files/png/logo-horizontal-for-dark-transparent-2400.png'
W, H = 1654, 2339                       # A4, 200 dpi
M = 120


def font(sz, w='Regular'):
    return ImageFont.truetype(f'{FD}Inter-{w}.otf', sz)


def page(title):
    im = Image.new('RGB', (W, H), GAL)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 250], fill=ANTH)
    lg = Image.open(LOGO)
    lg = lg.crop(lg.getbbox())
    lw = 520
    lg = lg.resize((lw, round(lg.height * lw / lg.width)), Image.LANCZOS)
    im.paste(lg, (M, (250 - lg.height) // 2), lg)
    d.text((W - M, 98), title, font=font(46, 'SemiBold'), fill=GAL, anchor='ra')
    d.text((W - M, 160), 'панели · плинтусы · молдинги', font=font(26), fill=SUBD, anchor='ra')
    d.line([M, H - 130, W - M, H - 130], fill=STONE, width=2)
    d.text((M, H - 100), 'Наш декор · Санкт-Петербург · nashdekor.ru', font=font(24), fill=SUBL)
    d.text((W - M, H - 100), 'Стена как галерея', font=font(24, 'Italic'), fill=SUBL, anchor='ra')
    return im, d


def wrap(d, text, f, width):
    out, line = [], ''
    for w in text.split(' '):
        t = (line + ' ' + w).strip()
        if d.textlength(t, font=f) <= width:
            line = t
        else:
            out.append(line)
            line = w
    out.append(line)
    return out


def para(d, y, text, f=None, fill=ANTH, width=W - 2 * M, gap=10, x=M):
    f = f or font(30)
    for ln in wrap(d, text, f, width):
        d.text((x, y), ln, font=f, fill=fill)
        y += f.size + gap
    return y


cats = sorted(d for d in os.listdir(ROOT) if os.path.isdir(f'{ROOT}/{d}') and d[0].isdigit())
counts = {c: len([x for x in os.listdir(f'{ROOT}/{c}') if os.path.isdir(f'{ROOT}/{c}/{x}')]) for c in cats}
total = sum(counts.values())

# ---------------- страница 1
im, d = page('3D-модели для дизайнеров')
y = 330
d.text((M, y), f'{total} моделей в натуральную величину', font=font(56, 'SemiBold'), fill=ANTH)
y += 96
y = para(d, y, 'Точные сечения профилей, длина как у товара. В каждой папке модели — один и тот же профиль в нескольких форматах и превью.', font(30), SUBL)
y += 30
for c in cats:
    d.rounded_rectangle([M, y, W - M, y + 74], radius=14, fill=HAZE)
    d.text((M + 30, y + 20), c.split(' ', 1)[1], font=font(30, 'Medium'), fill=ANTH)
    d.text((W - M - 30, y + 20), f'{counts[c]} шт.', font=font(30, 'SemiBold'), fill=ANTH, anchor='ra')
    y += 86
y += 30
d.text((M, y), 'Форматы', font=font(40, 'SemiBold'), fill=ANTH)
y += 70
rows = [('FBX', '3ds Max, Corona, V-Ray, Blender — единицы сохранены (мм), импорт без масштабирования.'),
        ('OBJ + MTL', '3ds Max, Cinema 4D, Blender и большинство программ. Единицы — миллиметры.'),
        ('DAE', 'SketchUp: Файл → Импорт → COLLADA (*.dae).'),
        ('GLB', 'Blender, онлайн-просмотрщики, AR. Единицы — метры, текстура внутри файла.'),
        ('DXF', 'Сечение профиля в мм — для AutoCAD, развёрток и чертежей.')]
for k, v in rows:
    d.text((M, y), k, font=font(30, 'SemiBold'), fill=BLUE)
    y = para(d, y, v, font(28), ANTH, width=W - 2 * M - 260, x=M + 260) + 14
y += 20
d.text((M, y), 'Как устроены модели', font=font(40, 'SemiBold'), fill=ANTH)
y += 70
for t in ['Панели стоят вертикально: длина — по высоте стены, лицевая сторона смотрит на вид «Спереди». Ставьте в ряд вплотную, шаг равен ширине панели.',
          'Плинтусы, молдинги, карнизы и уголки лежат горизонтально, задняя сторона — к стене (плоскость XZ). Длина — как у товара: подрезайте под проект.',
          'Материал paint_white — панели под покраску: задайте свой цвет. Панели с декором: base_black (чёрная основа) и decor_<код> — текстура в масштабе 1:1, папка textures.',
          'Нужен расчёт по проекту — пришлите развёртку стены, вернём спецификацию по артикулам.']:
    d.ellipse([M, y + 12, M + 12, y + 24], fill=BLUE)
    y = para(d, y, t, font(28), ANTH, width=W - 2 * M - 40, x=M + 40) + 16
pages = [im]

# ---------------- страницы с превью
thumbs = []
for c in cats:
    for it in sorted(os.listdir(f'{ROOT}/{c}')):
        p = f'{ROOT}/{c}/{it}/{it}.jpg'
        if os.path.exists(p):
            thumbs.append((c, it, p))
cols, tw, th = 4, (W - 2 * M - 3 * 24) // 4, 0
th = tw * 3 // 4
per = 5 * cols
for s in range(0, len(thumbs), per):
    im, d = page('Каталог моделей')
    y0 = 310
    cur = None
    for k, (c, it, p) in enumerate(thumbs[s:s + per]):
        r, q = divmod(k, cols)
        x, y = M + q * (tw + 24), y0 + r * (th + 92)
        t = Image.open(p).convert('RGB').resize((tw, th), Image.LANCZOS)
        im.paste(t, (x, y))
        d.text((x, y + th + 12), it, font=font(28, 'SemiBold'), fill=ANTH)
        d.text((x, y + th + 50), c.split(' ', 1)[1], font=font(20), fill=SUBL)
    pages.append(im)

out_pdf = f'{ROOT}/Инструкция и каталог моделей.pdf'
pages[0].save(out_pdf, save_all=True, append_images=pages[1:], resolution=200, quality=88)
txt = f'''«Наш декор» — 3D-модели для дизайнеров ({total} шт.)

Папки по видам товара, в каждой папке модели:
  <артикул>.fbx  — 3ds Max, Corona, V-Ray, Blender (единицы мм)
  <артикул>.obj + .mtl — большинство программ (единицы мм)
  <артикул>.dae  — SketchUp (Файл → Импорт → COLLADA)
  <артикул>.glb  — Blender, онлайн-просмотр (единицы метры)
  <артикул>_профиль.dxf — сечение профиля в мм (AutoCAD)
  <артикул>.jpg  — превью
Папка textures — текстуры декоров (масштаб 1:1), на них ссылаются OBJ, FBX и DAE — держите её рядом с папками моделей.

Панели стоят вертикально (длина по высоте), лицевая сторона — к виду «Спереди».
Погонаж (плинтусы, молдинги, карнизы, уголки) лежит горизонтально, задней стороной к стене.
Материалы: paint_white — под покраску, задайте свой цвет; base_black — чёрная основа панелей с декором; decor_<код> — декор.

Расчёт по проекту — пришлите развёртку стены, вернём спецификацию по артикулам.
Наш декор · Санкт-Петербург · nashdekor.ru
'''
open(f'{ROOT}/Как пользоваться.txt', 'w', encoding='utf-8').write(txt)
print('pages', len(pages), 'models', total, out_pdf, os.path.getsize(out_pdf) // 1024, 'KB')
