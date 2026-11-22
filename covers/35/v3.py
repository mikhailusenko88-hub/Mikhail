# Обложка 35, схема «сцена в разрезе» (22.11.2026): толстое снежное одеяло на земле, в нём тёплая «пещерка» —
# там зелёный росток светится (под снегом тепло); сверху падает снег, Рон слева показывает, Барсик справа удивлён.
#   OBLOZHKA=<папка с compose.py> python3 covers/35/v3.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f1_winter_day.jpg", "bg_zoom": [0.75, 0.32, 1.7], "blur": 6, "sat": 1.35, "bri": 1.0, "con": 1.08, "tint": [90, 140, 220, 40],
        "rays": {"cx": 0.5, "cy": 0.05, "n": 18, "col": [255, 250, 220], "a": 34}}
cv = A.background(plan, el)
top = BH * .44                      # верх снежного одеяла
rnd = random.Random(7)
# земля внизу
L = A.layer(); d = ImageDraw.Draw(L); d.rectangle([0, BH * .8, BW, BH], fill=(104, 70, 44, 255))
for i in range(60): x = rnd.random() * BW; y = BH * .8 + rnd.random() * BH * .2; r = (3 + rnd.random() * 6) * S; d.ellipse([x - r, y - r, x + r, y + r], fill=(84, 56, 36, 255))
cv.alpha_composite(L)
# снежное одеяло: волнистый верх, голубая тень книзу
mask = Image.new('L', (BW, BH), 0); m = ImageDraw.Draw(mask)
pts = [(0, BH * .8)] + [(x, top + math.sin(x / BW * math.pi * 3.2 + .6) * BH * .035 + math.sin(x / BW * 17) * BH * .008) for x in range(0, BW + 8, 8)] + [(BW, BH * .8)]
m.polygon(pts, fill=255)
grad = Image.new('RGBA', (BW, BH)); g = ImageDraw.Draw(grad)
for y in range(BH): t = max(0, min(1, (y - top) / (BH * .8 - top))); g.line([(0, y), (BW, y)], fill=(int(252 - 50 * t), int(253 - 35 * t), 255, 255))
snow = A.layer(); snow.paste(grad, (0, 0), mask); cv.alpha_composite(snow)
# пещерка в снегу: тёплый свет
cx, cb = BW * .5, BH * .8
cave = Image.new('L', (BW, BH), 0); c = ImageDraw.Draw(cave); c.ellipse([cx - BW * .18, cb - BH * .38, cx + BW * .18, cb + BH * .3], fill=255)
cave = cave.filter(ImageFilter.GaussianBlur(9 * S))
warm = Image.new('RGBA', (BW, BH), (255, 200, 120, 0)); warm.putalpha(cave.point(lambda v: int(v * .8))); cv.alpha_composite(warm)
glow = Image.new('L', (BW, BH), 0); ImageDraw.Draw(glow).ellipse([cx - BW * .1, cb - BH * .3, cx + BW * .1, cb], fill=200); glow = glow.filter(ImageFilter.GaussianBlur(30 * S))
gl = Image.new('RGBA', (BW, BH), (255, 248, 200, 0)); gl.putalpha(glow); cv.alpha_composite(gl)
# росток на земле в пещерке
sp = Image.open(os.path.join(el, 'v_sprout_GLAVNOE.png')).convert('RGBA'); sp = sp.crop(sp.getbbox()); k = BH * .5 / sp.height
sp = sp.resize((int(sp.width * k), int(sp.height * k)), Image.LANCZOS); sp = ImageEnhance.Color(sp).enhance(1.25)
cv.alpha_composite(sp, (int(cx - sp.width * .5), int(cb + BH * .02 - sp.height)))
# кромка пещерки — тонкая голубая тень
L = A.layer(); d = ImageDraw.Draw(L); d.arc([cx - BW * .18, cb - BH * .38, cx + BW * .18, cb + BH * .3], 180, 360, fill=(160, 195, 235, 200), width=int(4 * S))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(2 * S)))
for it in [
    {"img": "g2_Рон_pokaz1.png", "cx": 0.16, "bottom": 0.9, "h": 0.6, "outline": 6},
    {"img": "g1_Барсик_udiv.png", "cx": 0.85, "bottom": 0.92, "h": 0.58, "outline": 6},
    {"sparkles": True, "cx": 0.5, "cy": 0.6, "r": 0.13, "n": 6, "col": [255, 250, 200]},
    {"mark": "?", "cx": 0.66, "cy": 0.24, "h": 0.2},
]: A.place(cv, it, el)
# падает снег
L = A.layer(); d = ImageDraw.Draw(L)
for i in range(150):
    x, y, r = rnd.random() * BW, rnd.random() * BH * .55, (2 + rnd.random() ** 2 * 9) * S
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(160 + rnd.random() * 90)))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.2 * S)))
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 35"); A.C.PAD = 30; A.C.banner(cv, ["РОСТОК ПОД СНЕГОМ?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
