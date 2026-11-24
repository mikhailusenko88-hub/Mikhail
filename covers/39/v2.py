# v2 (24.11, проба «радость вместо удивления»): герои ликуют, без «?», ярче. Обложка 39, схема «находка — вещь на весь кадр» (23.11.2026): огромная снежинка (шесть лучиков с веточками, ледяная, синий контур, сияние)
# на вечернем зимнем небе; Пик с лупой слева внизу, Филя удивлён справа; «?».
# Снежинка рисуется здесь (как в движке snezhinka-eng: та же форма лучиков и веточек).
#   OBLOZHKA=<папка с compose.py> python3 covers/39/v1.py папка_элементов выход.jpg
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f4_winter_evening.jpg", "bg_zoom": [0.5, 0.45, 1.2], "blur": 6, "sat": 1.5, "bri": 1.0, "tint": [40, 30, 140, 55]}
cv = A.background(plan, el)
cx, cy, R = BW * .5, BH * .43, BH * .37
# сияние за снежинкой
gl = Image.new('L', (BW, BH), 0); ImageDraw.Draw(gl).ellipse([cx - R * 1.25, cy - R * 1.25, cx + R * 1.25, cy + R * 1.25], fill=190)
gl = gl.filter(ImageFilter.GaussianBlur(R * .35)); lay = Image.new('RGBA', (BW, BH), (190, 230, 255, 0)); lay.putalpha(gl); cv.alpha_composite(lay)
def bar(d, x0, y0, ang, L, W, col):
    ca, sa = math.cos(ang), math.sin(ang); px, py = -sa, ca
    pts = [(x0 + px * W / 2, y0 + py * W / 2), (x0 + ca * (L - W * .6) + px * W / 2, y0 + sa * (L - W * .6) + py * W / 2), (x0 + ca * L, y0 + sa * L),
           (x0 + ca * (L - W * .6) - px * W / 2, y0 + sa * (L - W * .6) - py * W / 2), (x0 - px * W / 2, y0 - py * W / 2)]
    d.polygon(pts, fill=col)
def flake(d, k, dl, col):
    for i in range(6):
        a = -math.pi / 2 + i * math.pi / 3
        bar(d, cx, cy, a, R + dl, R * .085 * k, col)
        for t0, l0, w0 in ((.38, .42, .065), (.66, .30, .055), (.86, .14, .045)):
            bx, by = cx + math.cos(a) * R * t0, cy + math.sin(a) * R * t0
            for sg in (-1, 1): bar(d, bx, by, a + sg * math.pi / 3, R * l0 + dl, R * w0 * k, col)
    rr = R * .16 + dl; d.polygon([(cx + rr * math.cos(math.pi / 6 + j * math.pi / 3), cy + rr * math.sin(math.pi / 6 + j * math.pi / 3)) for j in range(6)], fill=col)
L1 = Image.new('RGBA', (BW, BH), (0, 0, 0, 0)); d1 = ImageDraw.Draw(L1)
flake(d1, 2.0, 9 * S, (255, 255, 255, 255))           # белая наклейка-обводка
flake(d1, 1.6, 5 * S, (36, 104, 190, 255))             # синий контур
flake(d1, 1.0, 0, (226, 244, 255, 255))                # лёд
sh = L1.split()[3].filter(ImageFilter.GaussianBlur(10 * S)); shl = Image.new('RGBA', (BW, BH), (10, 30, 80, 0)); shl.putalpha(sh.point(lambda v: v * .55))
cv.alpha_composite(shl, (0, 8 * S)); cv.alpha_composite(L1)
# блик на льду
d = ImageDraw.Draw(cv)
for i in range(6):
    a = -math.pi / 2 + i * math.pi / 3; x, y = cx + math.cos(a) * R * .55, cy + math.sin(a) * R * .55
    d.ellipse([x - 5 * S, y - 5 * S, x + 5 * S, y + 5 * S], fill=(255, 255, 255, 230))
for it in [
    {"img": "g5_Пик_likuet1.png", "cx": 0.14, "bottom": 1.04, "h": 0.74, "outline": 7},
    {"img": "g3_Филя_likuet2.png", "cx": 0.87, "bottom": 1.05, "h": 0.7, "outline": 7, "flip": True},
    {"sparkles": True, "cx": 0.5, "cy": 0.44, "r": 0.32, "n": 10},
]: A.place(cv, it, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 39"); A.C.PAD = 30; A.C.banner(cv, ["ПОЧЕМУ У СНЕЖИНКИ ЛУЧИКИ?"], 'center', maxw=.56, base=36)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Color(ImageEnhance.Contrast(res).enhance(1.1)).enhance(1.25); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
