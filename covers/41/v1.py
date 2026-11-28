# Обложка 41, схема «пополам» (28.11.2026): слева день — яркое солнце, на голубом небе звёзды едва-едва видны пунктиром
# («они там, просто не видно»), Рон удивлённо показывает вверх; справа ночь — небо в ярких звёздах, Барсик ликует.
# Ответ на вопрос названия виден без чтения. Без «?» в кадре, тёплое солнце против синей ночи (H33: радость, мало мелочей).
#   OBLOZHKA=<папка с compose.py> python3 covers/41/v1.py папка_элементов выход.jpg
import sys, os, math, random, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
def bgf(*keys):
    for k in keys:
        f = sorted(glob.glob(os.path.join(el, f'f*_{k}.jpg')))
        if f: return os.path.basename(f[0])
    raise SystemExit('нет фона ' + str(keys))
day = A.background({"bg": bgf('winter_day', 'winter_morning'), "bg_zoom": [0.5, 0.35, 1.15], "blur": 4, "sat": 1.35, "bri": 1.10,
                    "spot": {"cx": 0.36, "cy": 0.16, "r": 0.30, "col": [255, 244, 200], "a": 170}}, el)
nb = bgf('winter_night', 'winter_evening')
night = A.background({"bg": nb, "bg_zoom": [0.5, 0.35, 1.15], "blur": 4, "sat": 1.25, "bri": 1.0 if 'night' in nb else .55,
                      "tint": [10, 20, 70, 0 if 'night' in nb else 120]}, el)
# граница дня и ночи — наклонная, мягкая
X0, X1 = .56, .46            # x границы вверху и внизу (доля ширины)
M = Image.new('L', (BW, BH), 0); d = ImageDraw.Draw(M); d.polygon([(BW * X0, 0), (BW, 0), (BW, BH), (BW * X1, BH)], fill=255)
M = M.filter(ImageFilter.GaussianBlur(10 * S))
# днём небо голубое (сверху синее, к горизонту светлее) — на нём солнце и едва видные звёзды
sky = Image.new('RGBA', (BW, BH), (0, 0, 0, 0)); dd = ImageDraw.Draw(sky)
for y in range(0, int(BH * .62), 4):
    k = y / (BH * .62); dd.rectangle([0, y, BW, y + 4], fill=(int(60 + 120 * k), int(140 + 85 * k), 255, int(225 * (1 - k) ** 1.1)))
day = day.convert('RGBA'); day.alpha_composite(sky.filter(ImageFilter.GaussianBlur(6 * S)))
cv = Image.composite(night.convert('RGBA'), day, M)
def xb(y): return BW * (X0 + (X1 - X0) * y / BH)
# солнце слева сверху: тёплый диск с лучами
L = A.layer(); d = ImageDraw.Draw(L); sx, sy, sr = BW * .36, BH * .15, BH * .085
for i in range(14):
    a = 2 * math.pi * i / 14 + .1; r0, r1 = sr * 1.35, sr * (2.1 if i % 2 else 1.75)
    d.polygon([(sx + r0 * math.cos(a - .09), sy + r0 * math.sin(a - .09)), (sx + r1 * math.cos(a), sy + r1 * math.sin(a)), (sx + r0 * math.cos(a + .09), sy + r0 * math.sin(a + .09))], fill=(255, 214, 90, 230))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.5 * S)))
G = A.layer(); d = ImageDraw.Draw(G); d.ellipse([sx - sr * 1.8, sy - sr * 1.8, sx + sr * 1.8, sy + sr * 1.8], fill=(255, 236, 150, 150)); cv.alpha_composite(G.filter(ImageFilter.GaussianBlur(30 * S)))
L = A.layer(); d = ImageDraw.Draw(L); d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 216, 70, 255)); d.ellipse([sx - sr * .72, sy - sr * .78, sx + sr * .55, sy + sr * .4], fill=(255, 238, 140, 255))
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1 * S)))
def starpoly(cx, cy, R, r, n=5, rot=0):
    return [(cx + (R if i % 2 == 0 else r) * math.cos(-math.pi / 2 + rot + i * math.pi / n), cy + (R if i % 2 == 0 else r) * math.sin(-math.pi / 2 + rot + i * math.pi / n)) for i in range(2 * n)]
# днём звёзды тоже на небе — едва видны (пунктирный контур)
L = A.layer(); d = ImageDraw.Draw(L)
for (fx, fy, R, rot) in [(.08, .40, 30, .2), (.47, .36, 30, -.15), (.24, .34, 24, .4)]:
    pts = starpoly(BW * fx, BH * fy, R * S, R * S * .45, 5, rot); pts.append(pts[0])
    for k in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[k], pts[k + 1]
        for t in (0.0, .5):
            d.line([(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t), (x0 + (x1 - x0) * (t + .3), y0 + (y1 - y0) * (t + .3))], fill=(255, 255, 255, 190), width=5 * S)
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(.6 * S)))
# ночью — небо в звёздах: мелкие точки и пять больших сияющих
rnd = random.Random(41); L = A.layer(); d = ImageDraw.Draw(L)
for i in range(240):
    y = BH * rnd.uniform(0, .62); x = rnd.uniform(xb(y) + 10 * S, BW)
    r = S * rnd.choice([1.2, 1.6, 2.2, 3.0]); a = rnd.randint(150, 255)
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 250, 225, a))
cv.alpha_composite(L)
for (fx, fy, R, col) in [(.70, .14, 46, (255, 222, 90)), (.86, .30, 38, (255, 240, 160)), (.62, .36, 30, (255, 230, 120)), (.94, .10, 28, (255, 246, 200)), (.77, .44, 22, (255, 236, 150))]:
    cx, cy = BW * fx, BH * fy
    G = A.layer(); d = ImageDraw.Draw(G); d.ellipse([cx - R * 2.6 * S, cy - R * 2.6 * S, cx + R * 2.6 * S, cy + R * 2.6 * S], fill=col + (150,)); cv.alpha_composite(G.filter(ImageFilter.GaussianBlur(R * 1.1 * S)))
    L = A.layer(); d = ImageDraw.Draw(L)
    d.line([(cx - R * 2.2 * S, cy), (cx + R * 2.2 * S, cy)], fill=(255, 255, 240, 200), width=3 * S); d.line([(cx, cy - R * 2.2 * S), (cx, cy + R * 2.2 * S)], fill=(255, 255, 240, 200), width=3 * S)
    d.polygon(starpoly(cx, cy, R * S, R * S * .45, 5), fill=col + (255,)); d.polygon(starpoly(cx - R * .12 * S, cy - R * .15 * S, R * .55 * S, R * .25 * S, 5), fill=(255, 252, 230, 255))
    cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(.8 * S)))
# тонкая светлая полоса по границе — «линия заката»
L = A.layer(); d = ImageDraw.Draw(L); d.line([(xb(0), 0), (xb(BH), BH)], fill=(255, 230, 170, 140), width=10 * S); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(8 * S)))
def pick(name, *poses):
    for p in poses:
        f = sorted(glob.glob(os.path.join(el, f'g*_{name}_{p}.png')))
        if f: return os.path.basename(f[0])
tel = [{"img": "v_telescope.png", "cx": 0.34, "bottom": 0.98, "h": 0.42, "outline": 5}] if os.path.exists(os.path.join(el, 'v_telescope.png')) else []   # телескоп Рона — днём в него звёзд не видно
for it in tel + [
    {"img": pick('Рон', 'pokaz1', 'pokaz2', 'udiv'), "cx": 0.17, "bottom": 1.04, "h": 0.70, "outline": 7},
    {"img": pick('Барсик', 'mashet', 'likuet1', 'rad'), "cx": 0.81, "bottom": 1.04, "h": 0.76, "outline": 7, "flip": True},   # машет звёздам: «Звёзды, привет!»
]: A.place(cv, it, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 41"); A.C.PAD = 30; A.C.banner(cv, ["КУДА ПРЯЧУТСЯ ЗВЁЗДЫ?"], 'center', maxw=.52, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
