# Обложка 37, схема «действие» (22.11.2026): Рон в прыжке по диагонали летит на замёрзшую лужу — лёд голубой, блестит,
# белый иней по краю и трещинки; «?» над льдом; Филя смеётся справа (мельче). Лёд рисуется здесь (как в движке led-eng).
#   OBLOZHKA=<папка с compose.py> python3 covers/37/v1.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f1_winter_day.jpg", "bg_zoom": [0.5, 0.45, 1.35], "blur": 6, "sat": 1.25, "bri": 1.05, "tint": [140, 190, 250, 35]}
cv = A.background(plan, el)
def blob(cx, cy, rx, ry, seed, n=90):
    pts = []
    for i in range(n):
        a = i / n * 2 * math.pi; k = 1 + .1 * math.sin(a * 3 + seed) + .06 * math.sin(a * 5 + seed * 2.3) + .03 * math.sin(a * 9 + seed * .7)
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return pts
# лёд: иней по краю, голубая гладь с градиентом, отражение неба, трещинки, блики
cx, cy, rx, ry = BW * .5, BH * .8, BW * .3, BH * .13
L = A.layer(); d = ImageDraw.Draw(L); d.polygon(blob(cx, cy + 8 * S, rx * 1.06, ry * 1.12, 1.3), fill=(70, 110, 160, 90)); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(14 * S)))
L = A.layer(); d = ImageDraw.Draw(L); d.polygon(blob(cx, cy, rx * 1.04, ry * 1.08, 1.3), fill=(246, 251, 255, 255)); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(2 * S)))
m = Image.new('L', (BW, BH), 0); ImageDraw.Draw(m).polygon(blob(cx, cy, rx * .95, ry * .95, 1.3), fill=255)
g = Image.new('RGBA', (BW, BH)); gd = ImageDraw.Draw(g)
for y in range(int(cy - ry * 1.1), int(cy + ry * 1.1)):
    t = (y - (cy - ry)) / (2 * ry); t = min(1, max(0, t)); c = (int(150 + 60 * t), int(205 + 30 * t), int(238 + 12 * t), 255); gd.line([(cx - rx * 1.2, y), (cx + rx * 1.2, y)], fill=c)
g.putalpha(m); cv.alpha_composite(g)
L = A.layer(); d = ImageDraw.Draw(L); rnd = random.Random(5)
for (x0, y0, ln, a) in [(-.45, -.1, .5, .25), (.05, .25, .45, -.4), (.35, -.2, .35, .9), (-.1, -.35, .3, 2.6), (-.6, .3, .25, -.2)]:
    px, py = cx + x0 * rx, cy + y0 * ry; pts = [(px, py)]
    for k in range(5): a += rnd.uniform(-.5, .5); px += math.cos(a) * ln * rx / 5; py += math.sin(a) * ln * ry / 5 * 1.6; pts.append((px, py))
    d.line(pts, fill=(255, 255, 255, 230), width=3 * S)
for (x0, y0, w0, h0) in [(-.25, -.3, .32, .1), (.3, .15, .18, .06)]:
    d.ellipse([cx + (x0 - w0) * rx, cy + (y0 - h0) * ry, cx + (x0 + w0) * rx, cy + (y0 + h0) * ry], fill=(255, 255, 255, 120))
L2 = Image.new('RGBA', (BW, BH)); L2.paste(L, (0, 0), m); cv.alpha_composite(L2)
for it in [
    {"img": "g3_Филя_likuet1.png", "cx": 0.87, "bottom": 1.04, "h": 0.56, "outline": 6, "flip": True},
    {"img": "g2_Рон_pryg.png", "cx": 0.36, "bottom": 0.74, "h": 0.66, "rot": -18, "outline": 7},
    {"sparkles": True, "cx": 0.55, "cy": 0.79, "r": 0.2, "n": 7},
    {"mark": "?", "cx": 0.68, "cy": 0.33, "h": 0.24},
]: A.place(cv, it, el)
# линии движения за Роном
L = A.layer(); d = ImageDraw.Draw(L)
for k, (x0, y0) in enumerate([(.13, .2), (.11, .3), (.14, .4)]):
    d.line([(BW * x0, BH * y0), (BW * (x0 + .08), BH * (y0 + .08))], fill=(255, 255, 255, 200), width=6 * S)
cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1 * S)))
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 37"); A.C.PAD = 30; A.C.banner(cv, ["ЛУЖА СТАЛА ЛЬДОМ?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
