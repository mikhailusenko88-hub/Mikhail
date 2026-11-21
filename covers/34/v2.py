# Обложка 34, схема «лупа» (21.11.2026): огромная лупа, в стекле — росток из жёлудя с корешком; Пик показывает, Рон радуется сбоку.
#   OBLOZHKA=/tmp/fontfix python3 covers/34/v2.py папка_элементов выход.jpg
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f6_meadow_day.jpg", "bg_zoom": [0.5, 0.6, 1.3], "blur": 6, "sat": 1.35, "bri": 1.05,
        "rays": {"cx": 0.56, "cy": 0.45, "n": 20, "col": [255, 244, 190], "a": 46}}
cv = A.background(plan, el)
# маленький росток на земле под лупой
A.place(cv, {"img": "v_sprout.png", "cx": 0.56, "bottom": 0.93, "h": 0.17, "outline": 3}, el)
# лупа: стекло — круг, внутри росток крупно; оправа и ручка
cx, cy, R = BW * .56, BH * .47, BH * .36
lens = Image.new('RGBA', (BW, BH), (0, 0, 0, 0)); L = ImageDraw.Draw(lens)
bgz = cv.crop((int(cx - R * .55), int(cy - R * .55), int(cx + R * .55), int(cy + R * .55))).resize((int(R * 2), int(R * 2)), Image.LANCZOS)
lens.paste(bgz, (int(cx - R), int(cy - R)))
sp = Image.open(os.path.join(el, 'v_sprout.png')).convert('RGBA'); sp = sp.crop(sp.getbbox()); k = R * 1.75 / sp.height; sp = sp.resize((int(sp.width * k), int(sp.height * k)), Image.LANCZOS)
lens.alpha_composite(sp, (int(cx - sp.width / 2), int(cy + R * .92 - sp.height)))
mask = Image.new('L', (BW, BH), 0); ImageDraw.Draw(mask).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
glass = Image.new('RGBA', (BW, BH), (0, 0, 0, 0)); glass.paste(lens, (0, 0), mask)
# ручка (за стеклом, вниз-вправо)
d = ImageDraw.Draw(cv); a = math.radians(48); x0, y0 = cx + math.cos(a) * R * .98, cy + math.sin(a) * R * .98; x1, y1 = cx + math.cos(a) * R * 1.75, cy + math.sin(a) * R * 1.75
d.line([(x0, y0), (x1, y1)], fill=(60, 30, 15, 255), width=int(R * .2)); d.line([(x0, y0), (x1, y1)], fill=(150, 80, 40, 255), width=int(R * .15))
cv.alpha_composite(glass)
# блик и оправа
hl = Image.new('RGBA', (BW, BH), (0, 0, 0, 0)); H = ImageDraw.Draw(hl); H.arc([cx - R * .8, cy - R * .8, cx + R * .8, cy + R * .8], 200, 250, fill=(255, 255, 255, 150), width=int(R * .07)); cv.alpha_composite(hl.filter(ImageFilter.GaussianBlur(3 * S)))
d = ImageDraw.Draw(cv); d.ellipse([cx - R - 14 * S, cy - R - 14 * S, cx + R + 14 * S, cy + R + 14 * S], outline=(60, 35, 15, 255), width=int(24 * S)); d.ellipse([cx - R - 10 * S, cy - R - 10 * S, cx + R + 10 * S, cy + R + 10 * S], outline=(235, 180, 60, 255), width=int(16 * S))
for it in [
    {"img": "g4_Пик_pokaz1.png", "cx": 0.17, "bottom": 1.04, "h": 0.8, "outline": 6},
    {"img": "g2_Рон_likuet2.png", "cx": 0.9, "bottom": 1.06, "h": 0.6, "outline": 5},
    {"sparkles": True, "cx": 0.56, "cy": 0.45, "r": 0.3, "n": 7},
]: A.place(cv, it, el)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 34"); A.C.PAD = 30; A.C.banner(cv, ["ЖЁЛУДЬ ПРОСНУЛСЯ?"], 'center', maxw=.5, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
