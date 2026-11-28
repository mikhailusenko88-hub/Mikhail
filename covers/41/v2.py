# Обложка 41, запасная — схема «сцена» (28.11.2026): вся картинка — ночное небо в звёздах над зимним лесом, герои внизу смотрят вверх,
# у Пика светится фонарик. Без солнца — загадку («куда днём?») не показывает, поэтому запасная.
#   OBLOZHKA=<папка с compose.py> python3 covers/41/v2.py папка_элементов выход.jpg
import sys, os, math, random, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
nb = sorted(glob.glob(os.path.join(el, 'f*_winter_night.jpg')))[0]
cv = A.background({"bg": os.path.basename(nb), "bg_zoom": [0.5, 0.62, 1.0], "blur": 3, "sat": 1.3, "bri": 1.05}, el)
def starpoly(cx, cy, R, r, n=5):
    return [(cx + (R if i % 2 == 0 else r) * math.cos(-math.pi / 2 + i * math.pi / n), cy + (R if i % 2 == 0 else r) * math.sin(-math.pi / 2 + i * math.pi / n)) for i in range(2 * n)]
rnd = random.Random(41); L = A.layer(); d = ImageDraw.Draw(L)
for i in range(420):
    x = rnd.uniform(0, BW); y = BH * rnd.uniform(0, .55) ** 1.3 * .9; r = S * rnd.choice([1.2, 1.6, 2.2, 3.0]); d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 250, 225, rnd.randint(140, 255)))
cv.alpha_composite(L)
for (fx, fy, R, col) in [(.50, .16, 56, (255, 222, 90)), (.30, .10, 34, (255, 240, 160)), (.70, .08, 30, (255, 230, 120)), (.18, .28, 26, (255, 246, 200)), (.82, .30, 28, (255, 236, 150)), (.62, .30, 22, (255, 246, 200))]:
    cx, cy = BW * fx, BH * fy
    G = A.layer(); d = ImageDraw.Draw(G); d.ellipse([cx - R * 2.6 * S, cy - R * 2.6 * S, cx + R * 2.6 * S, cy + R * 2.6 * S], fill=col + (150,)); cv.alpha_composite(G.filter(ImageFilter.GaussianBlur(R * 1.1 * S)))
    L = A.layer(); d = ImageDraw.Draw(L); d.line([(cx - R * 2.2 * S, cy), (cx + R * 2.2 * S, cy)], fill=(255, 255, 240, 200), width=3 * S); d.line([(cx, cy - R * 2.2 * S), (cx, cy + R * 2.2 * S)], fill=(255, 255, 240, 200), width=3 * S)
    d.polygon(starpoly(cx, cy, R * S, R * S * .45), fill=col + (255,)); d.polygon(starpoly(cx - R * .12 * S, cy - R * .15 * S, R * .55 * S, R * .25 * S), fill=(255, 252, 230, 255)); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(.8 * S)))
def pick(name, *poses):
    for p in poses:
        f = sorted(glob.glob(os.path.join(el, f'g*_{name}_{p}.png')))
        if f: return os.path.basename(f[0])
lan = os.path.join(el, 'v_lantern_GLAVNOE.png')
for it in [{"img": pick('Пик', 'likuet1', 'rad', 'vot'), "cx": 0.16, "bottom": 1.04, "h": 0.56, "outline": 6},
           {"img": pick('Рон', 'pokaz1', 'pokaz2'), "cx": 0.82, "bottom": 1.04, "h": 0.62, "outline": 6, "flip": True},
           {"img": pick('Барсик', 'mashet', 'rad'), "cx": 0.50, "bottom": 1.06, "h": 0.60, "outline": 6}]: A.place(cv, it, el)
if os.path.exists(lan):
    G = A.layer(); d = ImageDraw.Draw(G); cx, cy = BW * .30, BH * .80; d.ellipse([cx - 120 * S, cy - 120 * S, cx + 120 * S, cy + 120 * S], fill=(255, 214, 120, 170)); cv.alpha_composite(G.filter(ImageFilter.GaussianBlur(50 * S)))
    A.place(cv, {"img": 'v_lantern_GLAVNOE.png', "cx": 0.30, "bottom": 0.98, "h": 0.30, "outline": 4}, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 41"); A.C.PAD = 30; A.C.banner(cv, ["КУДА ПРЯЧУТСЯ ЗВЁЗДЫ?"], 'center', maxw=.52, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
