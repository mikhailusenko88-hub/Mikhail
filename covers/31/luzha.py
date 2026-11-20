# Свои элементы обложки серии 31 «Солнце выпило лужу?!» (лужу студия на сером фоне не отрисует — в студии вода отражает серое):
#   v_luzha.png  — лужа в перспективе: тёмный мокрый след прежнего края (была больше) и вода поменьше, в ней небо и блики
#   v_par.png    — три волнистые струйки пара от лужи вверх (как вода «улетает»)
#   v_solnce.png — солнце: жёлтый круг с тёплым ободком и мягким сиянием
#   python3 luzha.py <папка el>
import sys, os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

el = sys.argv[1] if len(sys.argv) > 1 else '.'
S = 2


def blob(d, cx, cy, rx, ry, seed, fill, k=(.10, .06, .035)):
    pts = []
    for i in range(160):
        a = 2 * math.pi * i / 160
        r = 1 + k[0] * math.sin(3 * a + seed) + k[1] * math.sin(5 * a + seed * 2.3) + k[2] * math.sin(9 * a + seed * .7)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    d.polygon(pts, fill=fill)


# --- лужа ---
W, H = 1400 * S, 520 * S
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
wet = Image.new('L', (W, H), 0); blob(ImageDraw.Draw(wet), W / 2, H / 2, W * .39, H * .38, 1.3, 255)
wet = wet.filter(ImageFilter.GaussianBlur(10 * S))
L = Image.new('RGBA', (W, H), (60, 66, 78, 0)); L.putalpha(wet.point(lambda v: int(v * .55))); im.alpha_composite(L)   # тёмный мокрый след — где лужа была утром
water = Image.new('L', (W, H), 0); blob(ImageDraw.Draw(water), W * .52, H * .53, W * .26, H * .26, 2.1, 255)
water = water.filter(ImageFilter.GaussianBlur(2 * S))
sky = Image.new('RGBA', (W, H)); dd = ImageDraw.Draw(sky)
for y in range(H):   # отражение неба: у дальнего края светлее
    t = y / H; c = (int(150 + 95 * (1 - t)), int(200 + 50 * (1 - t)), int(245 + 10 * (1 - t))); dd.line([(0, y), (W, y)], fill=c + (255,))
sky.putalpha(water); im.alpha_composite(sky)
hm = Image.new('L', (W, H), 0); dh = ImageDraw.Draw(hm)   # блики солнца и облачко в воде (маска отдельно — без тёмной каймы)
dh.ellipse([W * .40, H * .36, W * .58, H * .46], fill=200); dh.ellipse([W * .60, H * .52, W * .68, H * .57], fill=150); dh.ellipse([W * .31, H * .55, W * .45, H * .64], fill=110)
hm = ImageChops.multiply(hm.filter(ImageFilter.GaussianBlur(9 * S)), water); hl = Image.new('RGBA', (W, H), (255, 255, 255, 0)); hl.putalpha(hm); im.alpha_composite(hl)
rim = water.filter(ImageFilter.MaxFilter(9)); rim = ImageChops.subtract(rim, water).filter(ImageFilter.GaussianBlur(2 * S))
R = Image.new('RGBA', (W, H), (255, 255, 255, 0)); R.putalpha(rim.point(lambda v: int(v * .55))); im.alpha_composite(R)   # светлый край воды
im.resize((W // S, H // S), Image.LANCZOS).save(os.path.join(el, 'v_luzha.png'))

# --- пар ---
W, H = 700 * S, 900 * S
pm = Image.new('L', (W, H), 0); d = ImageDraw.Draw(pm)
for k, x0 in enumerate((.22, .5, .78)):
    pts = []
    for i in range(60):
        t = i / 59; y = H * (1 - t) * .96 + H * .02; x = W * x0 + W * .08 * math.sin(t * 8 + k * 1.7) * (0.4 + t)
        pts.append((x, y))
    for i in range(len(pts) - 1):
        a = int(250 * (1 - (i / 59) ** 1.8)); wdt = int((30 + 22 * (i / 59)) * S)
        d.line([pts[i], pts[i + 1]], fill=a, width=wdt)
        d.ellipse([pts[i][0] - wdt / 2, pts[i][1] - wdt / 2, pts[i][0] + wdt / 2, pts[i][1] + wdt / 2], fill=a)
im = Image.new('RGBA', (W, H), (255, 255, 255, 0)); im.putalpha(pm.filter(ImageFilter.GaussianBlur(6 * S)))
im.resize((W // S, H // S), Image.LANCZOS).save(os.path.join(el, 'v_par.png'))

# --- солнце ---
W = 900 * S
im = Image.new('RGBA', (W, W), (0, 0, 0, 0))
g = Image.new('RGBA', (W, W), (255, 214, 90, 0)); m = Image.new('L', (W, W), 0); ImageDraw.Draw(m).ellipse([W * .12, W * .12, W * .88, W * .88], fill=200)
g.putalpha(m.filter(ImageFilter.GaussianBlur(W * .08))); im.alpha_composite(g)
d = ImageDraw.Draw(im)
d.ellipse([W * .25, W * .25, W * .75, W * .75], fill=(255, 176, 40, 255))
d.ellipse([W * .27, W * .27, W * .73, W * .73], fill=(255, 214, 60, 255))
hm = Image.new('L', (W, W), 0); ImageDraw.Draw(hm).ellipse([W * .33, W * .31, W * .55, W * .48], fill=170)
hl = Image.new('RGBA', (W, W), (255, 248, 200, 0)); hl.putalpha(hm.filter(ImageFilter.GaussianBlur(12 * S))); im.alpha_composite(hl)
im.resize((W // S, W // S), Image.LANCZOS).save(os.path.join(el, 'v_solnce.png'))
print('ok')
