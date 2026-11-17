# Элемент «зеркальце с отражением героя» для афиши серии 28: в стекло v_mirror_GLAVNOE.png вписывается зеркально повёрнутый герой.
#   python3 zerkalo.py <папка элементов> [g2_Рон_pokaz1.png]  →  v_mirror_ron.png в той же папке
import sys, os
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageChops, ImageDraw
EL = sys.argv[1]; HERO = sys.argv[2] if len(sys.argv) > 2 else 'g2_Рон_pokaz1.png'
m = Image.open(os.path.join(EL, 'v_mirror_GLAVNOE.png')).convert('RGBA')
m = m.resize((m.width * 3, m.height * 3), Image.LANCZOS).rotate(52, expand=True, resample=Image.BICUBIC)   # стекло вверх, ручка вниз
a = np.array(m).astype(float); R, G, B, A = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
mx = np.maximum(np.maximum(R, G), B); mn = np.minimum(np.minimum(R, G), B); sat = (mx - mn) / np.maximum(mx, 1)
gm = Image.fromarray((((A > 200) & (sat < .22) & (B >= R)) * 255).astype('uint8')).filter(ImageFilter.MedianFilter(9))   # стекло — серо-голубое, рамка — розовая
ys, xs = np.where(np.array(gm) > 128); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max(); gw, gh = x1 - x0, y1 - y0
gm = gm.filter(ImageFilter.GaussianBlur(2))
r = Image.open(os.path.join(EL, HERO)).convert('RGBA'); r = r.crop(r.getbbox()).transpose(Image.FLIP_LEFT_RIGHT)
head = r.crop((0, 0, r.width, int(r.height * .62))); k = max(gw / head.width, gh / head.height) * 1.02
head = head.resize((int(head.width * k), int(head.height * k)), Image.LANCZOS)
refl = Image.new('RGBA', m.size, (0, 0, 0, 0)); gl = Image.new('RGBA', m.size, (190, 225, 250, 255)); d = ImageDraw.Draw(gl)
for i in range(y0, y1): t = (i - y0) / max(1, gh); d.line([(x0, i), (x1, i)], fill=(int(215 - 45 * t), int(238 - 28 * t), int(255 - 10 * t), 255))
refl.alpha_composite(gl); tmp = Image.new('RGBA', m.size, (0, 0, 0, 0)); tmp.alpha_composite(head, (x0 + (gw - head.width) // 2, y0 + int(gh * .10)))
rgb = ImageEnhance.Brightness(ImageEnhance.Color(tmp.convert('RGB')).enhance(.9)).enhance(1.05).convert('RGBA'); rgb.putalpha(tmp.getchannel('A')); refl.alpha_composite(rgb)
refl.alpha_composite(Image.new('RGBA', m.size, (170, 215, 255, 38)))
bl = Image.new('L', m.size, 0); ImageDraw.Draw(bl).polygon([(x0 + gw * .08, y0 + gh * .55), (x0 + gw * .30, y0 + gh * .02), (x0 + gw * .44, y0 + gh * .02), (x0 + gw * .16, y0 + gh * .70)], fill=120)
w = Image.new('RGBA', m.size, (255, 255, 255, 0)); w.putalpha(bl.filter(ImageFilter.GaussianBlur(6))); refl.alpha_composite(w)
refl.putalpha(ImageChops.multiply(refl.getchannel('A'), gm)); out = m.copy(); out.alpha_composite(refl); out = out.crop(out.getbbox()); out.save(os.path.join(EL, 'v_mirror_ron.png')); print(out.size)
