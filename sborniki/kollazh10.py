#!/usr/bin/env python3
"""Обложка большого сборника: 10 обложек серий карточками (два ряда по 5) + «10 СЕРИЙ ПОДРЯД!» + плашка с минутами.
python3 sborniki/kollazh10.py <выход.jpg> <минуты> <N1> … <N10>   (обложки — covers/<N>/cover.jpg)"""
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
out, mins, nums = sys.argv[1], sys.argv[2], sys.argv[3:]
FB = next(p for p in ['/usr/share/fonts/truetype/inter/Inter-Black.ttf', '/usr/share/fonts/opentype/inter/Inter-Black.otf'] if os.path.exists(p))
W, H = 1280, 720
bg = Image.new('RGB', (W, H))
d = ImageDraw.Draw(bg)
for y in range(H):                                   # небо: голубое сверху, светлое снизу
    t = y / H; d.line([(0, y), (W, y)], fill=(int(120 + 110 * t), int(190 + 50 * t), int(240 + 12 * t)))


def card(n, cx, cy, w, ang):
    im = Image.open(f'covers/{n}/cover.jpg').convert('RGB').resize((w, int(w * 9 / 16)), Image.LANCZOS)
    b = 6; c = Image.new('RGBA', (im.width + 2 * b, im.height + 2 * b), (255, 255, 255, 255)); c.paste(im, (b, b))
    m = Image.new('L', c.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, c.width - 1, c.height - 1], 14, fill=255); c.putalpha(m)
    c = c.rotate(ang, resample=Image.BICUBIC, expand=True)
    sh = Image.new('RGBA', c.size, (0, 0, 0, 0)); sh.putalpha(c.split()[3].point(lambda a: a * 0.35)); sh = sh.filter(ImageFilter.GaussianBlur(8))
    bg.paste(sh, (cx - c.width // 2 + 5, cy - c.height // 2 + 8), sh); bg.paste(c, (cx - c.width // 2, cy - c.height // 2), c)


angs = [2.5, -1.5, 1.5, -2.5, 2, -2, 1.5, -1.5, 2.5, -2]
xs = [134, 387, 640, 893, 1146]
for i, n in enumerate(nums[:5]):
    card(n, xs[i], 250, 246, angs[i])
for i, n in enumerate(nums[5:10]):
    card(n, xs[i], 548, 246, angs[5 + i])
f1 = ImageFont.truetype(FB, 64); txt = '10 СЕРИЙ ПОДРЯД!'
tw = d.textlength(txt, font=f1); x0 = (W - tw) / 2 - 44
ban = Image.new('RGBA', (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(ban)
bd.rounded_rectangle([x0, 14, x0 + tw + 88, 104], 30, fill=(225, 45, 50, 255), outline=(255, 255, 255, 255), width=6)
bd.text((x0 + 44 + 3, 22 + 3), txt, font=f1, fill=(120, 0, 0, 255)); bd.text((x0 + 44, 22), txt, font=f1, fill=(255, 255, 255, 255))
ban = ban.rotate(1.2, resample=Image.BICUBIC, center=(W / 2, 60)); bg.paste(ban, (0, 0), ban)
f2 = ImageFont.truetype(FB, 36); t2 = f'{mins} минут'; w2 = d.textlength(t2, font=f2)
d.rounded_rectangle([(W - w2) / 2 - 28, 375, (W + w2) / 2 + 28, 431], 28, fill=(255, 205, 40), outline=(255, 255, 255), width=4)
d.text(((W - w2) / 2, 380), t2, font=f2, fill=(40, 30, 10))
bg.save(out, quality=92); bg.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=90)
print(out)
