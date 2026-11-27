# Обложка 40, схема «все вместе на горке» (27.11.2026, H33): день, яркое солнце; Барсик и Топа радуются по бокам,
# между ними санки мчатся вниз по склону сами; тёплый свет, без «?».
#   OBLOZHKA=<папка с compose.py> python3 covers/40/v2.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f1_winter_day.jpg", "bg_zoom": [0.25, 0.4, 1.3], "blur": 5, "sat": 1.4, "bri": 1.06, "tint": [255, 210, 140, 26],
        "rays": {"cx": 0.5, "cy": 0.12, "n": 16, "col": [255, 244, 200], "a": 55}, "spot": {"cx": 0.5, "cy": 0.45, "r": 0.3, "col": [255, 250, 220], "a": 140}}
cv = A.background(plan, el)
def yl(x): return BH * (.38 + .45 * x / BW)
L = A.layer(); d = ImageDraw.Draw(L); d.polygon([(0, yl(0)), (BW, yl(BW)), (BW, BH), (0, BH)], fill=(250, 252, 255, 255)); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(2 * S)))
L = A.layer(); d = ImageDraw.Draw(L); d.line([(0, yl(0) + 10 * S), (BW, yl(BW) + 10 * S)], fill=(140, 180, 235, 120), width=26 * S); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(16 * S)))
rnd = random.Random(41); L = A.layer(); d = ImageDraw.Draw(L)
for i in range(150):
    k = rnd.random(); x = BW * (.40 - .28 * k + rnd.uniform(-.04, .04)); y = yl(x) + BH * rnd.uniform(-.09, .01); r = S * rnd.uniform(4, 14) * (1 - .5 * k)
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(235 * (1 - .6 * k))))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.5 * S)))
sl = Image.open(os.path.join(el, 'v_sled_GLAVNOE.png')).convert('RGBA'); w = int(BW * .44)
sl = sl.resize((w, int(sl.height * w / sl.width)), Image.LANCZOS).rotate(-14, resample=Image.BICUBIC, expand=True)
cx = BW * .52; cy = yl(cx) - sl.height * .06
glow = Image.new('RGBA', sl.size, (255, 240, 170, 0)); glow.putalpha(sl.split()[3].point(lambda a: 255 if a > 20 else 0))
G = A.layer(); G.alpha_composite(glow, (int(cx - sl.width / 2), int(cy - sl.height / 2))); G = G.filter(ImageFilter.GaussianBlur(16 * S)); cv.alpha_composite(G); cv.alpha_composite(G)
cv.alpha_composite(sl, (int(cx - sl.width / 2), int(cy - sl.height / 2)))
for it in [
    {"img": "g1_Барсик_rad.png", "cx": 0.16, "bottom": 1.06, "h": 0.80, "outline": 7},
    {"img": "g5_Топа_likuet1.png", "cx": 0.86, "bottom": 1.04, "h": 0.66, "outline": 7, "flip": True},
    {"sparkles": True, "cx": 0.52, "cy": 0.55, "r": 0.22, "n": 8},
]: A.place(cv, it, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 40"); A.C.PAD = 30; A.C.banner(cv, ["САНКИ ЕДУТ САМИ?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
