# Обложка 33, схема «погода пополам» (21.11.2026): слева солнечный двор и раскрытая шишка, справа дождь и закрытая — крупно, без лиц на переднем плане.
#   OBLOZHKA=/tmp/fontfix python3 covers/33/v2.py папка_элементов выход.jpg
import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import afisha as A
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
el, out = sys.argv[1], sys.argv[2]; BW, BH, S = A.BW, A.BH, A.S
plan = {"el": el, "bg": "f1_yard_day.jpg", "bg_zoom": [0.5, 0.5, 1.15], "blur": 5, "sat": 1.35, "bri": 1.08}
cv = A.background(plan, el)
# правая половина — дождь: темнее, синее, косые струи; граница — диагональ
rain = cv.copy(); rain = ImageEnhance.Brightness(rain.convert('RGB')).enhance(.55).convert('RGBA'); rain.alpha_composite(Image.new('RGBA', (BW, BH), (40, 70, 130, 90)))
d = ImageDraw.Draw(rain); random.seed(33)
for _ in range(420):
    x, y = random.uniform(0, BW), random.uniform(0, BH); l = random.uniform(30, 70) * S
    d.line([(x, y), (x - l * .25, y + l)], fill=(200, 225, 255, random.randint(70, 140)), width=max(2, int(1.6 * S)))
m = Image.new('L', (BW, BH), 0); md = ImageDraw.Draw(m); md.polygon([(BW * .56, 0), (BW, 0), (BW, BH), (BW * .44, BH)], fill=255); m = m.filter(ImageFilter.GaussianBlur(10 * S))
cv = Image.composite(rain, cv, m)
# тёплый свет слева
sun = Image.new('L', (BW, BH), 0); sd = ImageDraw.Draw(sun); sd.ellipse([BW * .05, BH * .0, BW * .55, BH * .9], fill=150); sun = sun.filter(ImageFilter.GaussianBlur(BW * .08))
warm = Image.new('RGBA', (BW, BH), (255, 236, 160, 0)); warm.putalpha(sun); cv.alpha_composite(warm)
for it in [
    {"img": "v_cone_open.png", "cx": 0.31, "bottom": 0.86, "h": 0.66, "outline": 6, "glow": [255, 220, 110]},
    {"img": "v_cone_closed.png", "cx": 0.69, "bottom": 0.86, "h": 0.66, "outline": 6, "glow": [150, 200, 255]},
    {"img": "g5_Топа_likuet1.png", "cx": 0.075, "bottom": 1.08, "h": 0.5, "outline": 5},
    {"img": "g3_Филя_likuet1.png", "cx": 0.93, "bottom": 1.08, "h": 0.46, "outline": 5, "flip": True},
]: A.place(cv, it, el)
d = ImageDraw.Draw(cv)
# солнце (между логотипом и шишкой) и капли на закрытой шишке
sx, sy, r = BW * .43, BH * .2, 44 * S
for i in range(12):
    a = i / 12 * 2 * math.pi; d.line([(sx + math.cos(a) * (r + 10 * S), sy + math.sin(a) * (r + 10 * S)), (sx + math.cos(a) * (r + 30 * S), sy + math.sin(a) * (r + 30 * S))], fill=(255, 196, 40, 255), width=9 * S)
d.ellipse([sx - r - 5 * S, sy - r - 5 * S, sx + r + 5 * S, sy + r + 5 * S], fill=(60, 40, 20, 255)); d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 214, 60, 255))
def drop(x, y, k):
    d.polygon([(x, y - 16 * k), (x - 10 * k, y + 4 * k), (x + 10 * k, y + 4 * k)], fill=(30, 50, 100, 255)); d.ellipse([x - 12 * k, y - 6 * k, x + 12 * k, y + 16 * k], fill=(30, 50, 100, 255))
    d.polygon([(x, y - 12 * k), (x - 7.5 * k, y + 4 * k), (x + 7.5 * k, y + 4 * k)], fill=(120, 190, 250, 255)); d.ellipse([x - 9 * k, y - 3 * k, x + 9 * k, y + 13 * k], fill=(120, 190, 250, 255)); d.ellipse([x - 4 * k, y + 0 * k, x - 1 * k, y + 5 * k], fill=(240, 250, 255, 255))
for x, y, k in [(.6, .3, 1.3), (.78, .36, 1.1), (.64, .55, 1.0), (.8, .62, 1.2), (.57, .7, .9)]: drop(BW * x, BH * y, k * S)
A.C.logo(cv, .8); A.C.pill(cv, "СЕРИЯ 33"); A.C.PAD = 30; A.C.banner(cv, ["ШИШКА ЗНАЕТ ПОГОДУ?"], 'center', maxw=.52, base=40)
res = cv.convert('RGB').resize((A.W, A.H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03); res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)
