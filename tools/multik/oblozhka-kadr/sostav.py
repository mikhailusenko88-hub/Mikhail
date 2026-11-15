# Обложка-композиция «герои — главное» (по просьбе Михаила 15.11): вырезанные герои движка крупно вокруг главного предмета,
# фон — место серии с мягким размытием, надпись небольшая (маленькие дети не читают).
#   python3 sostav.py план.json выход.jpg
# план.json: {"bg": "фон.png", "blur": 6, "series": "СЕРИЯ 27", "text": "ПОЧЕМУ ЛОДКА|НЕ ТОНЕТ?", "text_at": "right",
#   "items": [ {"img": "cut/topa.png", "x": .30, "y": .02, "h": .62, "flip": false}, ... ]}   — по порядку от дальнего к ближнему;
#   x, y — левый верхний угол в долях кадра, h — высота в долях кадра. Для вещи (лист sheet.js) — "sheet": true.
import sys, json, os
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose as C          # логотип, «СЕРИЯ N», шрифт
from extras import cut as cut_sheet

W, H = 1280, 720


def glow(im, r=7, col=(255, 255, 255), k=.85):
    a = im.split()[3].filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(r))
    g = Image.new('RGBA', im.size, col + (0,)); g.putalpha(a.point(lambda v: int(v * k))); return g


def splash(canvas, it):
    # рябь и пена под плавающей вещью: «на воде», а не на песке
    cx, cy, w = int(W * it['cx']), int(H * it['cy']), int(W * it['w'])
    L = Image.new('RGBA', canvas.size, (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for k, a in ((1.0, 70), (.78, 95), (.56, 120)):
        ww, hh = int(w * k), int(w * k * .22); d.ellipse([cx - ww // 2, cy - hh // 2, cx + ww // 2, cy + hh // 2], outline=(255, 255, 255, a), width=max(3, int(w * .012)))
    d.ellipse([cx - int(w * .42), cy - int(w * .07), cx + int(w * .42), cy + int(w * .07)], fill=(60, 140, 210, 120))
    canvas.alpha_composite(L.filter(ImageFilter.GaussianBlur(2)))


def place(canvas, it):
    if it.get('splash'): return splash(canvas, it)
    im = cut_sheet(it['img']) if it.get('sheet') else Image.open(it['img']).convert('RGBA')
    if it.get('flip'): im = im.transpose(Image.FLIP_LEFT_RIGHT)
    hh = int(H * it['h']); ww = int(im.width * hh / im.height); im = im.resize((ww, hh), Image.LANCZOS)
    if it.get('sat'): im = Image.merge('RGBA', (*ImageEnhance.Color(im.convert('RGB')).enhance(it['sat']).split(), im.split()[3]))
    pad = 24; big = Image.new('RGBA', (ww + 2 * pad, hh + 2 * pad), (0, 0, 0, 0)); big.alpha_composite(im, (pad, pad))
    x, y = int(W * it['x']) - pad, int(H * it['y']) - pad
    sh = Image.new('RGBA', big.size, (0, 0, 0, 0)); sh.putalpha(big.split()[3].filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * .35)))
    canvas.alpha_composite(sh, (x + 8, y + 12))
    canvas.alpha_composite(glow(big, r=it.get('glow', 6)), (x, y))
    canvas.alpha_composite(big, (x, y))


def caption(img, lines, where):
    # небольшая плашка-свиток в углу: 2 строки, высота ~ 1/5 кадра
    C.PAD = 30
    C.banner(img, lines, where, maxw=.30, base=46)


def main():
    plan = json.load(open(sys.argv[1], encoding='utf-8')); out = sys.argv[2]
    bg = Image.open(plan['bg']).convert('RGB').resize((W, H), Image.LANCZOS)
    if plan.get('crop'):
        x, y, w, h = plan['crop']; bg = Image.open(plan['bg']).convert('RGB').crop((x, y, x + w, y + h)).resize((W, H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(plan.get('blur', 6)))
    bg = ImageEnhance.Color(bg).enhance(1.15); bg = ImageEnhance.Brightness(bg).enhance(plan.get('bri', 1.05))
    cv = bg.convert('RGBA')
    for it in plan['items']: place(cv, it)
    # плашки на холсте вдвое крупнее (как в compose.py), потом уменьшаем
    S = C.S; big = cv.resize((W * S, H * S), Image.LANCZOS)
    C.logo(big, plan.get('logo', .62)); C.pill(big, plan['series'])
    if plan.get('text'): caption(big, plan['text'].split('|'), plan.get('text_at', 'right'))
    res = big.convert('RGB').resize((W, H), Image.LANCZOS)
    res = ImageEnhance.Contrast(res).enhance(1.04)
    res.save(out, quality=93, optimize=True); res.resize((320, 180), Image.LANCZOS).save(out.replace('.jpg', '_mini.png')); print(out)


main()
