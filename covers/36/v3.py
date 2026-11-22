# Обложка 36 v3, схема «пропажа» (22.11.2026, элементы сборки 36): на снегу лужа, над ней пунктиром — контур снеговика, которого нет;
# знак «?»; Рон-сыщик с лупой слева показывает на лужу, Барсик удивлён справа (оба мельче вещи). v_luzha.png — covers/31/luzha.py.
#   OBLOZHKA=<папка с compose.py> python3 covers/36/v3.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f1_winter_day.jpg", "bg_zoom": [0.62, 0.5, 1.4], "blur": 6, "sat": 1.3, "bri": 1.04, "tint": [120, 170, 240, 30]}
cv = A.background(plan, el)
# солнышко справа сверху
L = A.layer(); d = ImageDraw.Draw(L); sx, sy, sr = BW * .38, BH * .14, BH * .085
d.ellipse([sx - sr * 1.8, sy - sr * 1.8, sx + sr * 1.8, sy + sr * 1.8], fill=(255, 230, 140, 90)); cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(20 * S)))
L = A.layer(); d = ImageDraw.Draw(L); d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 214, 70, 255)); cv.alpha_composite(L)
# лужа
lz = Image.open(os.path.join(el, 'v_luzha.png')).convert('RGBA'); lz = lz.crop(lz.getbbox()); k = BW * .46 / lz.width
lz = lz.resize((int(lz.width * k), int(lz.height * k)), Image.LANCZOS); cx, cy = BW * .5, BH * .78
cv.alpha_composite(lz, (int(cx - lz.width / 2), int(cy - lz.height / 2)))
# контур снеговика пунктиром — «был тут»
sm = Image.open(os.path.join(el, 'v_snowman.png')).convert('RGBA'); sm = sm.crop(sm.getbbox()); k = BH * .58 / sm.height
sm = sm.resize((int(sm.width * k), int(sm.height * k)), Image.LANCZOS); a = sm.split()[3].point(lambda v: 255 if v > 90 else 0)
edge = ImageChops.subtract(a.filter(ImageFilter.MaxFilter(21)), a)
dash = Image.new('L', sm.size, 0); dd = ImageDraw.Draw(dash)
for y in range(0, sm.height, 34): dd.rectangle([0, y, sm.width, y + 18], fill=255)
edge = ImageChops.multiply(edge, dash)
ghost = Image.new('RGBA', sm.size, (255, 255, 255, 0)); ghost.putalpha(edge)
fill = Image.new('RGBA', sm.size, (255, 255, 255, 0)); fill.putalpha(a.point(lambda v: int(v * .18)))
gx, gy = int(cx - sm.width / 2), int(cy - BH * .02 - sm.height)
cv.alpha_composite(fill, (gx, gy)); sh = Image.new('RGBA', sm.size, (30, 50, 100, 0)); sh.putalpha(edge.filter(ImageFilter.GaussianBlur(3 * S)).point(lambda v: min(255, v * 2)))
cv.alpha_composite(sh, (gx + 3 * S, gy + 3 * S)); cv.alpha_composite(ghost, (gx, gy))
for it in [
    {"img": "g2_Рон_pokaz1.png", "cx": 0.16, "bottom": 1.04, "h": 0.66, "outline": 6},
    {"img": "v_magnifier.png", "cx": 0.255, "bottom": 0.66, "h": 0.17, "rot": 35, "outline": 4},
    {"img": "g1_Барсик_udiv.png", "cx": 0.86, "bottom": 1.05, "h": 0.64, "outline": 6, "flip": True},
    {"mark": "?", "cx": 0.64, "cy": 0.32, "h": 0.24},
    {"sparkles": True, "cx": 0.5, "cy": 0.78, "r": 0.16, "n": 6},
]: A.place(cv, it, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 36"); A.C.PAD = 30; A.C.banner(cv, ["КУДА УШЁЛ СНЕГОВИК?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
