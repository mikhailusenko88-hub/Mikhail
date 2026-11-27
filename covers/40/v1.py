# Обложка 40, схема «вещь в действии» + радость (27.11.2026, H33): пустые санки сами мчатся с горки на закате —
# большие, по диагонали, за ними снежный шлейф и полосы скорости; Рон ликует справа, Топа слева (бурый — виден на снегу). Без «?», тёплый фон.
#   OBLOZHKA=<папка с compose.py> python3 covers/40/v1.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f6_winter_evening.jpg", "bg_zoom": [0.3, 0.55, 1.25], "blur": 5, "sat": 1.35, "bri": 1.08, "tint": [255, 170, 110, 28],
        "spot": {"cx": 0.47, "cy": 0.52, "r": 0.33, "col": [255, 236, 200], "a": 150}}
cv = A.background(plan, el)
# склон горки по диагонали (сверху-слева вниз-вправо): снег с тёплым отсветом заката и голубой тенью у края
def yl(x): return BH * (.30 + .55 * x / BW)
L = A.layer(); d = ImageDraw.Draw(L); d.polygon([(0, yl(0)), (BW, yl(BW)), (BW, BH), (0, BH)], fill=(255, 246, 240, 255))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(2 * S)))
L = A.layer(); d = ImageDraw.Draw(L); d.line([(0, yl(0) + 10 * S), (BW, yl(BW) + 10 * S)], fill=(150, 160, 215, 120), width=26 * S)
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(16 * S)))
L = A.layer(); d = ImageDraw.Draw(L)
for k in range(5):   # следы полозьев
    off = 30 * S + k * 3 * S
    d.line([(0, yl(0) + 60 * S + (k > 2) * 46 * S), (BW * .42, yl(BW * .42) + 60 * S + (k > 2) * 46 * S)], fill=(200, 200, 235, 70), width=4 * S)
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(2 * S)))
# снежный шлейф за санками (вверх-влево по склону)
rnd = random.Random(40); L = A.layer(); d = ImageDraw.Draw(L)
for i in range(170):
    k = rnd.random(); x = BW * (.36 - .30 * k + rnd.uniform(-.04, .04)); y = yl(x) + BH * rnd.uniform(-.10, .01); r = S * rnd.uniform(4, 15) * (1 - .5 * k)
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(235 * (1 - .6 * k))))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.5 * S)))
# полосы скорости
L = A.layer(); d = ImageDraw.Draw(L)
for (x0, y0, ln) in [(.10, .30, .16), (.06, .40, .20), (.12, .50, .14), (.16, .22, .10)]:
    d.line([(BW * x0, BH * y0), (BW * (x0 + ln), BH * (y0 + ln * .62))], fill=(255, 255, 255, 215), width=7 * S)
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1 * S)))
# санки — главное, крупно, наклон вниз по склону, с тёплым сиянием
sl = Image.open(os.path.join(el, 'v_sled_GLAVNOE.png')).convert('RGBA')
w = int(BW * .50); sl = sl.resize((w, int(sl.height * w / sl.width)), Image.LANCZOS).rotate(-17, resample=Image.BICUBIC, expand=True)
cx = BW * .50; cy = yl(cx) - sl.height * .06
glow = Image.new('RGBA', sl.size, (255, 230, 150, 0)); glow.putalpha(sl.split()[3].point(lambda a: 255 if a > 20 else 0))
G = A.layer(); G.alpha_composite(glow, (int(cx - sl.width / 2), int(cy - sl.height / 2))); G = G.filter(ImageFilter.GaussianBlur(18 * S))
cv.alpha_composite(G); cv.alpha_composite(G)
# тень под санками
L = A.layer(); d = ImageDraw.Draw(L); d.polygon([(cx - sl.width * .42, cy + sl.height * .10), (cx + sl.width * .44, cy + sl.height * .42), (cx + sl.width * .40, cy + sl.height * .50), (cx - sl.width * .46, cy + sl.height * .18)], fill=(120, 110, 170, 70))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(10 * S)))
cv.alpha_composite(sl, (int(cx - sl.width / 2), int(cy - sl.height / 2)))
for it in [
    {"img": "g5_Топа_likuet1.png", "cx": 0.13, "bottom": 1.04, "h": 0.52, "outline": 6},
    {"img": "g2_Рон_likuet1.png", "cx": 0.85, "bottom": 1.04, "h": 0.72, "outline": 7, "flip": True},
    {"sparkles": True, "cx": 0.48, "cy": 0.55, "r": 0.24, "n": 8, "col": [255, 250, 220]},
]: A.place(cv, it, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 40"); A.C.PAD = 30; A.C.banner(cv, ["САНКИ ЕДУТ САМИ?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
