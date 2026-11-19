# Свои элементы обложки серии 30 «Кто откусил Луну?!» — из элементов студии (studio-30b, elementy.zip):
#   v_moon_bitten.png  — Луна с «укусом» (три круга по правому верхнему краю, тень по краю укуса)
#   v_cookie_bitten.png — печенье Рона с таким же укусом (подсказка «кто подозреваемый»)
#   v_kroshki.png      — крошки Луны (кусочки того же цвета) — у мордочки Рона
#   python3 luna.py <папка el>
import sys, os, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

el = sys.argv[1] if len(sys.argv) > 1 else '.'


def bite(im, circles, rim=(120, 90, 40), rim_a=110):
    im = im.convert('RGBA'); w, h = im.size
    m = Image.new('L', im.size, 0); d = ImageDraw.Draw(m)
    for cx, cy, r in circles: d.ellipse([(cx - r) * w, (cy - r) * h, (cx + r) * w, (cy + r) * h], fill=255)
    a = im.split()[3]
    # тень по краю укуса: полоска внутри оставшейся части
    edge = m.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(5))
    shade = ImageChops.multiply(edge, a)
    sh = Image.new('RGBA', im.size, rim + (0,)); sh.putalpha(shade.point(lambda v: int(v * rim_a / 255)))
    out = im.copy(); out.alpha_composite(sh)
    out.putalpha(ImageChops.multiply(a, ImageChops.invert(m)))
    return out


moon = Image.open(os.path.join(el, 'v_moon_GLAVNOE.png'))
bite(moon, [(.98, .28, .2), (1.03, .5, .19), (.88, .1, .14)], rim=(150, 120, 50), rim_a=120).save(os.path.join(el, 'v_moon_bitten.png'))
cookie = Image.open(os.path.join(el, 'v_cookie.png'))
bite(cookie, [(.97, .32, .2), (1.02, .68, .19)], rim=(90, 50, 20), rim_a=140).save(os.path.join(el, 'v_cookie_bitten.png'))

# крошки: кусочки луны неправильной формы, цвет — с самой Луны
rnd = random.Random(30); W = 400; K = Image.new('RGBA', (W, W), (0, 0, 0, 0)); d = ImageDraw.Draw(K)
for i in range(7):
    cx, cy, r = rnd.uniform(.15, .85) * W, rnd.uniform(.15, .85) * W, rnd.uniform(.05, .11) * W
    pts = []
    for k in range(7):
        import math
        a = 2 * math.pi * k / 7 + rnd.random() * .5; rr = r * rnd.uniform(.6, 1.1); pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=(246, 232, 170, 255), outline=(170, 145, 70, 255))
    d.ellipse([cx - r * .25, cy - r * .2, cx + r * .1, cy + r * .15], fill=(222, 205, 140, 255))
K.save(os.path.join(el, 'v_kroshki.png'))
print('ok')
