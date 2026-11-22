# Обложка 38, схема «сцена» (22.11.2026): окно во весь кадр в белых морозных узорах (веточки от краёв, звёздочки),
# в середине оттаявший глазок — в него заглядывает удивлённый Рон; Барсик удивлён внизу справа; «?»; за окном зима.
#   OBLOZHKA=<папка с compose.py> python3 covers/38/v1.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f1_winter_day.jpg", "bg_zoom": [0.55, 0.45, 1.6], "blur": 9, "sat": 1.15, "bri": 1.08, "tint": [150, 190, 250, 50]}
cv = A.background(plan, el)
# рама окна
X0, Y0, X1, Y1 = BW * .17, BH * .06, BW * .83, BH * .9
L = A.layer(); d = ImageDraw.Draw(L); fr = 26 * S
d.rectangle([X0 - fr, Y0 - fr, X1 + fr, Y1 + fr], fill=(250, 246, 238, 255)); d.rectangle([X0, Y0, X1, Y1], fill=(0, 0, 0, 0))
sh = Image.new('RGBA', (BW, BH), (60, 40, 20, 0)); sh.putalpha(L.split()[3].filter(ImageFilter.GaussianBlur(12 * S)).point(lambda v: v // 3))
cv.alpha_composite(sh, (6 * S, 8 * S))
# Рон заглядывает в глазок (за стеклом)
ron = Image.open(os.path.join(el, 'g2_Рон_udiv.png')).convert('RGBA'); ron = ron.crop(ron.getbbox()); k = BH * .95 / ron.height
ron = ron.resize((int(ron.width * k), int(ron.height * k)), Image.LANCZOS); hx, hy = BW * .5, BH * .47
cv.alpha_composite(ron, (int(hx - ron.width / 2), int(hy - ron.height * .3)))
# иней на стекле с глазком
fz = A.layer(); fd = ImageDraw.Draw(fz); rr = random.Random(38)
g0 = Image.new('L', (BW, BH), 0); gd = ImageDraw.Draw(g0)
for i in range(60):
    t = i / 60; gd.rectangle([X0 + (X1 - X0) * t * .5, Y0 + (Y1 - Y0) * t * .5, X1 - (X1 - X0) * t * .5, Y1 - (Y1 - Y0) * t * .5], outline=int(200 * (1 - t) ** 1.5), width=int((X1 - X0) / 120))
g0 = g0.filter(ImageFilter.GaussianBlur(30 * S)); fz.alpha_composite(Image.merge('RGBA', (Image.new('L', (BW, BH), 236), Image.new('L', (BW, BH), 244), Image.new('L', (BW, BH), 255), g0)))
def fern(x, y, a, ln, w, dep):
    if dep <= 0 or ln < 6 * S: return
    x2, y2 = x + math.cos(a) * ln, y + math.sin(a) * ln; fd.line([(x, y), (x2, y2)], fill=(255, 255, 255, 235), width=max(2, int(w)))
    n = 4 + rr.randint(0, 2)
    for k2 in range(1, n + 1):
        t = k2 / (n + 1); px, py = x + (x2 - x) * t, y + (y2 - y) * t; l2 = ln * (.42 - t * .25)
        fern(px, py, a + .75, l2, w * .7, dep - 1); fern(px, py, a - .75, l2, w * .7, dep - 1)
for i in range(30):
    side = i % 4; t = rr.random()
    x = X0 + (X1 - X0) * t if side in (0, 2) else (X1 if side == 1 else X0); y = Y1 if side == 0 else (Y0 if side == 2 else Y0 + (Y1 - Y0) * t)
    a = math.atan2((Y0 + Y1) / 2 - y, (X0 + X1) / 2 - x) + rr.uniform(-.5, .5); fern(x, y, a, (110 + rr.random() * 120) * S, 4 * S, 3)
for i in range(10):
    x, y, s2 = X0 + rr.random() * (X1 - X0), Y0 + rr.random() * (Y1 - Y0), (9 + rr.random() * 10) * S
    for k2 in range(6): a = k2 * math.pi / 3; fd.line([(x, y), (x + math.cos(a) * s2, y + math.sin(a) * s2)], fill=(255, 255, 255, 230), width=3 * S)
m = Image.new('L', (BW, BH), 0); ImageDraw.Draw(m).rectangle([X0, Y0, X1, Y1], fill=255)
hole = Image.new('L', (BW, BH), 0); R2 = BH * .22; ImageDraw.Draw(hole).ellipse([hx - R2, hy - R2 * .95, hx + R2, hy + R2 * .95], fill=255); hole = hole.filter(ImageFilter.GaussianBlur(14 * S))
m = ImageChops.subtract(m, hole); a = ImageChops.multiply(fz.split()[3], m); fz.putalpha(a); cv.alpha_composite(fz)
L = A.layer(); ImageDraw.Draw(L).ellipse([hx - R2, hy - R2 * .95, hx + R2, hy + R2 * .95], outline=(255, 255, 255, 150), width=5 * S); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(4 * S)))
# рама поверх
FR = A.layer(); d = ImageDraw.Draw(FR); d.rectangle([X0 - fr, Y0 - fr, X1 + fr, Y1 + fr], outline=(250, 246, 238, 255), width=fr)
d.rectangle([X0 - fr * 1.6, Y1 + fr * .6, X1 + fr * 1.6, Y1 + fr * 1.6], fill=(244, 238, 226, 255)); cv.alpha_composite(FR)
for it in [
    {"img": "g1_Барсик_udiv.png", "cx": 0.9, "bottom": 1.06, "h": 0.6, "outline": 6, "flip": True},
    {"mark": "?", "cx": 0.9, "cy": 0.36, "h": 0.24},
]: A.place(cv, it, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 38"); A.C.PAD = 30; A.C.banner(cv, ["КТО РИСУЕТ НА ОКНЕ?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
