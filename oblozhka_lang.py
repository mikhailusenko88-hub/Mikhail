# Обложка серии на другом языке (для YouTube Studio → Языки → Thumbnail): та же картинка, что у русской, но логотип, «серия N» и вопрос на свитке — на этом языке.
# Рядом нужны afisha.py и compose.py из ветки studio, элементы — elementy.zip из релиза studio-<сборка> (+ свои вещи серии: covers/<N>/*.py).
#   python3 oblozhka_lang.py <covers/N/plan.json | covers/N/vN.py> выход.jpg "EPISODE 31" "DID THE SUN DRINK THE PUDDLE?" en [аргументы скрипта: папка_элементов выход.jpg]
#   (в плане .json поле "el" — путь к папке элементов; скрипту vN.py поправить sys.path на папку с afisha.py)
import sys, json, os, runpy
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import afisha as A
import compose as C
S = C.S
LOGO = {"hi": ("बारसिक", "बिल्ला"), "en": ("Barsik", "the Cat"), "es": ("Barsik", "el Gato"), "pt": ("Barsik", "o Gato"), "de": ("Barsik", "der Kater")}


def make_logo(big, small):
    def logo(img, k=1.0):
        L = Image.new('RGBA', (680 * S, 300 * S), (0, 0, 0, 0))
        f1, f2 = C.font(64 * S), C.font(96 * S)
        rows = (((20 * S, 14 * S), big, f2), ((78 * S, 120 * S), small, f1))
        for (xy, t, f) in rows:
            ImageDraw.Draw(L).text(xy, t, font=f, fill='white', stroke_width=17 * S, stroke_fill='white')
        sh = L.split()[3].filter(ImageFilter.GaussianBlur(8 * S))
        base = Image.new('RGBA', L.size, (0, 0, 0, 0)); base.paste((60, 30, 10, 140), (6 * S, 10 * S), sh)
        L = Image.alpha_composite(base, L)
        for (xy, t, f) in rows:
            C.outlined_text(L, xy, t, f, (255, 190, 40, 255), (110, 52, 14, 255), 7 * S, shadow=False, grad=((255, 226, 92), (246, 128, 22)))
        d = ImageDraw.Draw(L)   # лапка после мелкой строки, как у «Кот»
        px, py, r = 78 * S + d.textlength(small, font=f1) + 30 * S, 150 * S, 15 * S
        col, oc = (246, 128, 22, 255), (110, 52, 14, 255)
        for grow, fl in ((4 * S, 'white'), (0, None)):
            for (dx, dy, rr) in ((0, 14, 1.05), (-17, -6, .5), (-6, -17, .5), (8, -17, .5), (19, -6, .5)):
                cx, cy, R = px + dx * S, py + dy * S, r * rr + grow
                d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=fl or col, outline=None if fl else oc, width=0 if fl else 3 * S)
        L = L.rotate(5, resample=Image.BICUBIC, expand=True)
        L = L.resize((int(L.width * k), int(L.height * k)), Image.LANCZOS)
        img.alpha_composite(L, (int(10 * S), int(2 * S)))
    return logo


src, out, series, text = sys.argv[1:5]
lang = sys.argv[5] if len(sys.argv) > 5 else 'en'
if lang == 'hi':   # у Inter нет деванагари: FreeSans Bold (свободный шрифт GNU), буквы собирает raqm
    from PIL import ImageFont
    HI = '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf'
    C.font = lambda px: ImageFont.truetype(HI, int(px), layout_engine=ImageFont.Layout.RAQM)
C.logo = make_logo(*LOGO[lang])
_pill, _banner = C.pill, C.banner
C.pill = lambda img, t: _pill(img, series)
K = 1.3 if lang == 'hi' else 1.0   # буквы деванагари ниже латиницы — свиток крупнее
C.banner = lambda img, lines, where, maxw=.52, base=None: _banner(img, text.split('|'), where, maxw, base and base * K)
if src.endswith('.json'):
    A.make(json.load(open(src, encoding='utf-8')), out)
else:   # скрипт обложки серии (covers/<N>/vN.py): ему — свои аргументы
    sys.argv = [src] + sys.argv[6:]
    runpy.run_path(src, run_name='__main__')
