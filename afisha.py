# Обложка-афиша под сценарий: художник (Claude) пишет план под конкретную серию — схему, фон, свет, позы героев, акцент.
# Элементы (герои по одному с мордочками и позами, вещи, фоны мест) рендерит студия: studio.js --only=elements.
#   python3 afisha.py план.json выход.jpg   (нужен compose.py из tools/multik/oblozhka-kadr — логотип, «СЕРИЯ N», свиток)
# план: {"el": "папка элементов", "bg": "f1_beach_day.jpg", "bg_zoom": [cx, cy, k], "blur": 5, "sat": 1.3, "bri": 1.05, "tint": [r,g,b,сила],
#   "rays": {"cx": .5, "cy": .45, "n": 14, "col": [255,240,170], "a": 70}, "spot": {"cx": .5, "cy": .5, "r": .35, "col": [255,250,210], "a": 170},
#   "vignette": .35, "series": "СЕРИЯ 27", "text": "ПОЧЕМУ ЛОДКА|НЕ ТОНЕТ?", "text_at": "right", "logo": .8,
#   "items": [ {"img": "g1_Барсик_pokaz1.png", "cx": .2, "bottom": 1.02, "h": .95, "flip": false, "rot": -4, "outline": 7, "glow": [255,220,90]},
#              {"water": true, "cx": .5, "cy": .8, "w": .4}, {"sparkles": true, "cx": .5, "cy": .4, "r": .2, "n": 9}, {"mark": "?", "cx": .62, "cy": .2, "h": .22} ] }
import sys, json, os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.environ.get('OBLOZHKA', ''), '/home/claude/m3d/tools/multik/oblozhka-kadr'):
    if p and os.path.exists(os.path.join(p, 'compose.py')): sys.path.insert(0, p); break
import compose as C
W, H, S = 1280, 720, 2      # рисуем вдвое крупнее, в конце уменьшаем
BW, BH = W * S, H * S


def layer(): return Image.new('RGBA', (BW, BH), (0, 0, 0, 0))


def background(plan, el):
    bg = Image.open(os.path.join(el, plan['bg'])).convert('RGB')
    cx, cy, k = plan.get('bg_zoom', [.5, .5, 1]); w, h = bg.width / k, bg.height / k
    x0 = min(max(0, cx * bg.width - w / 2), bg.width - w); y0 = min(max(0, cy * bg.height - h / 2), bg.height - h)
    bg = bg.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((BW, BH), Image.LANCZOS)
    if plan.get('blur', 5): bg = bg.filter(ImageFilter.GaussianBlur(plan.get('blur', 5) * S))
    bg = ImageEnhance.Color(bg).enhance(plan.get('sat', 1.3)); bg = ImageEnhance.Brightness(bg).enhance(plan.get('bri', 1.05)); bg = ImageEnhance.Contrast(bg).enhance(plan.get('con', 1.05))
    cv = bg.convert('RGBA')
    if plan.get('tint'): r, g, b, a = plan['tint']; cv.alpha_composite(Image.new('RGBA', (BW, BH), (r, g, b, int(a))))
    if plan.get('rays'):
        R = plan['rays']; L = layer(); d = ImageDraw.Draw(L); cx, cy = R.get('cx', .5) * BW, R.get('cy', .45) * BH; n = R.get('n', 14); rad = BW * 1.3; col = tuple(R.get('col', [255, 240, 170]))
        for i in range(n):
            a0 = 2 * math.pi * i / n + R.get('turn', .1); a1 = a0 + math.pi / n * R.get('wide', .9)
            d.polygon([(cx, cy), (cx + rad * math.cos(a0), cy + rad * math.sin(a0)), (cx + rad * math.cos(a1), cy + rad * math.sin(a1))], fill=col + (R.get('a', 70),))
        cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(3 * S)))
    if plan.get('spot'):
        Sp = plan['spot']; L = Image.new('L', (BW, BH), 0); d = ImageDraw.Draw(L); cx, cy, r = Sp['cx'] * BW, Sp['cy'] * BH, Sp.get('r', .3) * BW
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=Sp.get('a', 170)); L = L.filter(ImageFilter.GaussianBlur(r * .45))
        sp = Image.new('RGBA', (BW, BH), tuple(Sp.get('col', [255, 250, 210])) + (0,)); sp.putalpha(L); cv.alpha_composite(sp)
    return cv


def star(d, cx, cy, r, col):
    pts = []
    for i in range(8): a = math.pi / 4 * i; rr = r if i % 2 == 0 else r * .28; pts.append((cx + rr * math.cos(a - math.pi / 2), cy + rr * math.sin(a - math.pi / 2)))
    d.polygon(pts, fill=col)


def place(cv, it, el):
    if it.get('water'):
        cx, cy, w = it['cx'] * BW, it['cy'] * BH, it['w'] * BW; L = layer(); d = ImageDraw.Draw(L)
        d.ellipse([cx - w * .46, cy - w * .09, cx + w * .46, cy + w * .09], fill=tuple(it.get('col', [70, 160, 230])) + (150,))
        for k, a in ((1.0, 110), (.76, 150), (.52, 190)): d.ellipse([cx - w * k / 2, cy - w * k * .11, cx + w * k / 2, cy + w * k * .11], outline=(255, 255, 255, a), width=max(4, int(w * .014)))
        cv.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.5 * S))); return
    if it.get('sparkles'):
        rnd = random.Random(it.get('seed', 7)); L = layer(); d = ImageDraw.Draw(L); cx, cy, r = it['cx'] * BW, it['cy'] * BH, it.get('r', .2) * BW
        for i in range(it.get('n', 9)):
            a = 2 * math.pi * i / it.get('n', 9) + rnd.random() * .5; rr = r * (.75 + rnd.random() * .5); star(d, cx + rr * math.cos(a), cy + rr * math.sin(a) * .8, BW * (.012 + rnd.random() * .016), tuple(it.get('col', [255, 255, 255])) + (235,))
        g = L.filter(ImageFilter.GaussianBlur(5 * S)); cv.alpha_composite(g); cv.alpha_composite(L); return
    if it.get('mark'):
        f = C.font(int(it.get('h', .2) * BH)); L = layer()
        C.outlined_text(L, (int(it['cx'] * BW), int(it['cy'] * BH)), it['mark'], f, tuple(it.get('col', [255, 214, 40])), (110, 52, 14), max(8, int(it.get('h', .2) * BH * .09)), anchor='mm')
        if it.get('rot'): L = L.rotate(it['rot'], resample=Image.BICUBIC, center=(it['cx'] * BW, it['cy'] * BH))
        cv.alpha_composite(L); return
    im = Image.open(os.path.join(el, it['img'])).convert('RGBA')
    if it.get('flip'): im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if it.get('crop'): a, b, c, d_ = it['crop']; im = im.crop((int(a * im.width), int(b * im.height), int(c * im.width), int(d_ * im.height)))
    hh = int(BH * it['h']); ww = int(im.width * hh / im.height); im = im.resize((ww, hh), Image.LANCZOS)
    rgb = ImageEnhance.Color(im.convert('RGB')).enhance(it.get('sat', 1.12)); rgb = ImageEnhance.Contrast(rgb).enhance(it.get('con', 1.04)); im = Image.merge('RGBA', (*rgb.split(), im.split()[3]))
    if it.get('fade'):   # низ обрезан кадром — растворяем
        a = im.split()[3]; g = Image.new('L', im.size, 255); d = ImageDraw.Draw(g); n = int(hh * it['fade'])
        for y in range(n): d.line([(0, hh - 1 - y), (ww, hh - 1 - y)], fill=int(255 * y / n))
        im.putalpha(ImageChops.multiply(a, g))
    if it.get('rot'): im = im.rotate(it['rot'], resample=Image.BICUBIC, expand=True)
    pad = 40 * S; big = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); big.alpha_composite(im, (pad, pad)); A = big.split()[3]
    cx = it['cx'] * BW; x = int(cx - big.width / 2); y = int(it['bottom'] * BH - im.height - pad) if 'bottom' in it else int(it.get('top', 0) * BH - pad)
    sh = Image.new('RGBA', big.size, (20, 10, 30, 0)); sh.putalpha(A.filter(ImageFilter.GaussianBlur(11 * S)).point(lambda v: int(v * it.get('shadow', .45)))); cv.alpha_composite(sh, (x + 7 * S, y + 10 * S))
    if it.get('glow'): g = Image.new('RGBA', big.size, tuple(it['glow']) + (0,)); g.putalpha(A.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(16 * S)).point(lambda v: min(255, int(v * 1.5)))); cv.alpha_composite(g, (x, y))
    ow = it.get('outline', 5)
    if ow:   # белая «наклейка» вокруг героя — читается на любом фоне и в маленьком размере
        k = ow * S * 2 + 1; o = A.filter(ImageFilter.GaussianBlur(ow * S * .55)).point(lambda v: 255 if v > 24 else 0).filter(ImageFilter.GaussianBlur(1.2 * S))
        ol = Image.new('RGBA', big.size, tuple(it.get('outline_col', [255, 255, 255])) + (0,)); ol.putalpha(o); cv.alpha_composite(ol, (x, y))
    cv.alpha_composite(big, (x, y))


def make(plan, out):
    el = plan.get('el', '.'); cv = background(plan, el)
    for it in plan['items']: place(cv, it, el)
    if plan.get('vignette'):
        v = Image.new('L', (BW, BH), 0); d = ImageDraw.Draw(v); d.ellipse([-BW * .12, -BH * .2, BW * 1.12, BH * 1.2], fill=255); v = v.filter(ImageFilter.GaussianBlur(BW * .09))
        dark = Image.new('RGBA', (BW, BH), (20, 8, 40, 0)); dark.putalpha(v.point(lambda x: int((255 - x) * plan['vignette']))); cv.alpha_composite(dark)
    if plan.get('logo', .8): C.logo(cv, plan.get('logo', .8))
    if plan.get('series'): C.pill(cv, plan['series'])
    if plan.get('text'): C.PAD = 30; C.banner(cv, plan['text'].split('|'), plan.get('text_at', 'right'), maxw=plan.get('text_w', .30), base=plan.get('text_px', 46))
    res = cv.convert('RGB').resize((W, H), Image.LANCZOS); res = ImageEnhance.Contrast(res).enhance(1.03)
    res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.jpg'), quality=88); print(out)


if __name__ == '__main__':
    make(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2])
