# Обложка 35, схема «сцена» (22.11.2026): яркий снежный луг, падает снег; в центре — ямка в сугробе, из неё крупно
# зелёный росток (Рон раскопал); Рон слева показывает, Барсик справа удивлён — оба мельче вещи (H30).
#   OBLOZHKA=<папка с compose.py> python3 covers/35/v2.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f1_winter_day.jpg", "bg_zoom": [0.72, 0.55, 1.55], "blur": 5, "sat": 1.25, "bri": 1.06,
        "rays": {"cx": 0.52, "cy": 0.2, "n": 18, "col": [255, 248, 210], "a": 40}, "spot": {"cx": .52, "cy": .55, "r": .3, "col": [255, 252, 225], "a": 150}}
cv = A.background(plan, el)
cx, base = BW * .52, BH * .86            # центр ямки, низ сугроба
# сугроб: большой белый холм с голубой тенью снизу
L = A.layer(); d = ImageDraw.Draw(L)
d.ellipse([cx - BW * .26, base - BH * .2, cx + BW * .26, base + BH * .1], fill=(214, 228, 245, 255))
d.ellipse([cx - BW * .25, base - BH * .23, cx + BW * .25, base + BH * .04], fill=(250, 252, 255, 255))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(4 * S)))
# ямка (тёмная, видна земля)
L = A.layer(); d = ImageDraw.Draw(L)
d.ellipse([cx - BW * .09, base - BH * .16, cx + BW * .09, base - BH * .06], fill=(120, 150, 190, 255))
d.ellipse([cx - BW * .075, base - BH * .15, cx + BW * .075, base - BH * .075], fill=(92, 62, 40, 255))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(2 * S)))
# росток крупно — из ямки
sp = Image.open(os.path.join(el, 'v_sprout_GLAVNOE.png')).convert('RGBA'); sp = sp.crop(sp.getbbox()); k = BH * .62 / sp.height
sp = sp.resize((int(sp.width * k), int(sp.height * k)), Image.LANCZOS)
glow = Image.new('RGBA', sp.size, (255, 255, 200, 0)); glow.putalpha(sp.split()[3].filter(ImageFilter.GaussianBlur(14 * S)).point(lambda v: int(v * .7)))
gx, gy = int(cx - sp.width * .5), int(base - BH * .1 - sp.height)
cv.alpha_composite(glow, (gx, gy)); cv.alpha_composite(sp, (gx, gy))
# передний край ямки — снег закрывает низ холмика земли
L = A.layer(); d = ImageDraw.Draw(L)
d.chord([cx - BW * .11, base - BH * .14, cx + BW * .11, base - BH * .02], 0, 180, fill=(250, 252, 255, 255))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.5 * S)))
# лопатка воткнута в сугроб
sh = Image.open(os.path.join(el, 'v_shovel.png')).convert('RGBA'); sh = sh.crop(sh.getbbox()); k = BH * .3 / sh.height
sh = sh.resize((int(sh.width * k), int(sh.height * k)), Image.LANCZOS).rotate(-18, expand=True, resample=Image.BICUBIC)
cv.alpha_composite(sh, (int(cx + BW * .1), int(base - BH * .3)))
for it in [
    {"img": "g2_Рон_pokaz1.png", "cx": 0.17, "bottom": 1.04, "h": 0.66, "outline": 6},
    {"img": "g1_Барсик_udiv.png", "cx": 0.86, "bottom": 1.05, "h": 0.6, "outline": 6},
    {"sparkles": True, "cx": 0.52, "cy": 0.42, "r": 0.2, "n": 7},
    {"mark": "?", "cx": 0.7, "cy": 0.2, "h": 0.2},
]: A.place(cv, it, el)
# падает снег
rnd = random.Random(35); L = A.layer(); d = ImageDraw.Draw(L)
for i in range(140):
    x, y, r = rnd.random() * BW, rnd.random() * BH * .92, (2 + rnd.random() ** 2 * 9) * S
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(150 + rnd.random() * 100)))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.2 * S)))
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 35"); A.C.PAD = 30; A.C.banner(cv, ["РОСТОК ПОД СНЕГОМ?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
