# Обложка «радость вместо удивления» (H33, 24.11.2026; Михаил: «у нас все лица удивлённые… чтобы лучше зацепило ребёнка»).
# Берёт готовый скрипт обложки серии и меняет только героев и краски: удивлённые лица → улыбка «ω» (элементы ulyb/ulybm из движка ulybka-eng),
# без «?», ярче и теплее. Композиция, вещь и надписи — как в исходной обложке (для честного A/B-теста в Studio).
#   OBLOZHKA=<папка с compose.py> python3 covers/radost.py covers/<N>/vX.py папка_элементов_серии папка_улыбок выход.jpg
import sys, os, re, glob, runpy, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import afisha as A
from PIL import Image, ImageEnhance
src, el, sm, out = sys.argv[1:5]
MAP = {'udiv': 'ulyb', 'rad': 'ulyb', 'vot': 'ulyb', 'dumaet': 'ulybm', 'pokaz1': 'ulybm', 'pokaz2': 'ulybm'}
_place = A.place
SWAP = json.loads(os.environ.get('SWAP', '{}'))   # точечная замена: {"g2_Рон_udiv.png": "ep:g*_Рон_mashet.png", "g1_Барсик_udiv.png": "sm:g*_Топа_ulyb.png"}
def place(cv, it, el0):
    if it.get('mark') == '?': return   # «?» на каждой обложке — убираем
    if it.get('img') in SWAP:
        where, pat = SWAP[it['img']].split(':', 1); c = sorted(glob.glob(os.path.join(el0 if where == 'ep' else sm, pat)))
        if c: it = dict(it); it['img'] = os.path.relpath(c[0], el0); return _place(cv, it, el0)
    if it.get('img'):
        m = re.match(r'g\d+_(.+?)_([a-z]+\d?)\.png$', it['img'])
        if m and m.group(2) in MAP:
            hero, tag = m.group(1), MAP[m.group(2)]
            c = sorted(glob.glob(os.path.join(sm, f'g*_{hero}_{tag}.png')))
            if c:
                it = dict(it); it['img'] = os.path.relpath(c[0], el0); it['sat'] = it.get('sat', 1.12) * 1.1
                if tag == 'ulyb': it['h'] = it.get('h', .5) * 1.06
    return _place(cv, it, el0)
A.place = place
sys.argv = [src, el, out]
runpy.run_path(src, run_name='__main__')
im = Image.open(out).convert('RGB')
im = ImageEnhance.Color(im).enhance(1.18); im = ImageEnhance.Contrast(im).enhance(1.06); im = ImageEnhance.Brightness(im).enhance(1.03)
r, g, b = im.split(); r = r.point(lambda v: min(255, int(v * 1.035))); b = b.point(lambda v: int(v * .965)); im = Image.merge('RGB', (r, g, b))   # теплее: зима не «белым по белому»
im.save(out, quality=93, optimize=True); im.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
