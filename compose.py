"""Карточка товара для сайта из вырезанного образца: фон «Антрацит», мягкая тень, баланс белого, кадр 16:9.
python3 compose.py <cut.png> <исходник.jpg> <выход_2x.jpg> <выход_1x.jpg> [--wb r,g,b] [--white]
--wb — множители баланса белого (общие для серии снимков); --white — белое изделие: тянем светлое к ~245."""
import sys
import cv2
import numpy as np
from PIL import Image, ImageFilter

BG = np.array([0x26, 0x29, 0x2E], dtype=np.float64)
W2, H2 = 1580, 898


def load(cut, src):
    a = np.asarray(Image.open(cut).convert('RGBA'), dtype=np.float64)
    rgb = np.asarray(Image.open(src).convert('RGB'), dtype=np.float64)
    alpha = a[..., 3] / 255.0
    return rgb, alpha


def clean_alpha(alpha):
    # убрать «пух» и ореол: мягкий порог и сжатие на 1 px
    al = np.clip((alpha - 0.15) / 0.7, 0, 1)
    im = Image.fromarray((al * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    return np.asarray(im, dtype=np.float64) / 255.0


def fix_hollows(rgb, alpha):
    """Сквозь пустоты профиля виден стол: мелкие «коричневые» пятна внизу образца, окружённые чёрным
    срезом, перекрашиваем в цвет среза. Крупные области (лицо реек) не трогаем."""
    m = alpha > 0.5
    hsv = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
    brown = (m & (hsv[..., 1] > 55) & (hsv[..., 2] > 40)).astype(np.uint8)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(brown, 8)
    ys, xs = np.where(m)
    y0, y1, area = ys.min(), ys.max(), m.sum()
    lum = rgb.mean(-1)
    dark = m & (lum < 50)
    dark[: int(y0 + 0.6 * (y1 - y0))] = False
    foam = np.median(rgb[dark], 0) if dark.sum() > 50 else np.array([28.0, 27.0, 29.0])
    fix = np.zeros(m.shape, np.uint8)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 0.015 * area and cent[i][1] > y0 + 0.62 * (y1 - y0):
            fix[lab == i] = 1
    if fix.any():
        fix = cv2.dilate(fix, np.ones((5, 5), np.uint8)).astype(bool) & m
        noise = np.random.default_rng(1).normal(0, 4, (fix.sum(), 1))
        rgb = rgb.copy()
        rgb[fix] = np.clip(foam[None, :] + noise, 0, 255)
    return rgb, int(fix.sum())


def drop_table(rgb, alpha):
    """Сквозь пустоты профиля виден стол. Ищем «цвет стола» только в узкой полосе у нижнего края
    силуэта (там, где срез), по образцу стола вокруг низа образца, и делаем такие места прозрачными —
    сквозь пустоту будет виден фон. Лицо изделия выше полосы не трогаем."""
    m = alpha > 0.5
    ys, xs = np.where(m)
    y0, y1 = ys.min(), ys.max()
    H = y1 - y0
    u8 = np.clip(rgb, 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(u8, cv2.COLOR_RGB2LAB).astype(np.float64)
    mu8 = m.astype(np.uint8)
    ring = cv2.dilate(mu8, np.ones((61, 61), np.uint8)).astype(bool) & ~cv2.dilate(mu8, np.ones((15, 15), np.uint8)).astype(bool)
    ring[: y0 + H // 2] = False
    if ring.sum() < 500:
        return alpha, 0
    mu, sd = lab[ring].mean(0), lab[ring].std(0) + np.array([6.0, 3.0, 3.0])
    hb = max(6, int(0.075 * H))
    cols = np.where(m.any(0))[0]
    yb = np.full(m.shape[1], -10 ** 6)
    yb[cols] = m.shape[0] - 1 - np.argmax(m[::-1, cols], axis=0)
    yy = np.arange(m.shape[0])[:, None]
    band = (yy <= yb[None, :]) & (yy >= yb[None, :] - hb)
    d = np.sqrt((((lab - mu) / sd) ** 2).sum(-1))
    dark = (m & band & (lab[..., 0] < 50)).astype(np.uint8)   # чёрная основа/пена
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))  # тонкие тёмные волокна декора — не пена
    below = np.cumsum(dark, axis=0) > 0              # только ниже начала чёрного торца — лицо рейки не трогаем
    chroma = np.hypot(lab[..., 1] - 128, lab[..., 2] - 128)
    table = band & m & below & (((d < 3.4) & (lab[..., 0] > 80)) | ((chroma > 7) & (lab[..., 0] > 30)))
    t8 = cv2.morphologyEx(table.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    t8 = cv2.dilate(t8, np.ones((3, 3), np.uint8))
    tb = cv2.GaussianBlur(t8.astype(np.float64), (0, 0), 1.0)
    return alpha * (1 - np.clip(tb, 0, 1)), int(t8.sum())


def fill_white(rgb, alpha):
    """Белое изделие: нейросеть иногда «выедает» низ торца (белая пена похожа на светлый фон).
    Возвращаем в маску светлые нейтральные пиксели, связанные с изделием, у его нижнего края.
    Стол (бежевый, цветной) и тени в пустотах профиля не трогаем."""
    m = alpha > 0.5
    ys, xs = np.where(m)
    y0, y1 = ys.min(), ys.max()
    H = y1 - y0
    lab = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float64)
    L = lab[..., 0]
    chroma = np.hypot(lab[..., 1] - 128, lab[..., 2] - 128)
    # нейтральность считаем относительно самого изделия (баланс белого снимка может быть тёплым)
    ref = lab[m & (L > np.percentile(L[m], 50))]
    a0, b0 = np.median(ref[:, 1]), np.median(ref[:, 2])
    dch = np.hypot(lab[..., 1] - a0, lab[..., 2] - b0)
    cand = (~m) & (L > 130) & (dch < 14)          # стол даёт dch ≈ 25+, торец с тёплым отсветом ≈ 8
    cand[: y0 + int(0.5 * H)] = False
    cand[min(m.shape[0], y1 + int(0.03 * H)):] = False
    # растим маску только через кандидатов (геодезическое расширение)
    grown = m.copy()
    k = np.ones((3, 3), np.uint8)
    for _ in range(200):
        nxt = cv2.dilate(grown.astype(np.uint8), k).astype(bool) & (cand | m)
        if (nxt == grown).all():
            break
        grown = nxt
    add = grown & ~m
    add8 = cv2.morphologyEx(add.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool) & (cand | add)
    # перекрываем старую мягкую кромку маски, иначе на шве остаётся тёмная нитка
    reg = cv2.dilate(add8.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & (cand | (alpha > 0.02))
    fill = cv2.GaussianBlur(reg.astype(np.float64), (0, 0), 0.8)
    return np.maximum(alpha, np.clip(fill * 1.2, 0, 1)), int(add8.sum())


def deskew(rgb, alpha, lim=9.0):
    """Выравниваем ближний (нижний) край образца по горизонтали — все карточки стоят одинаково."""
    m = alpha > 0.5
    ys, xs = np.where(m)
    x0, x1 = xs.min(), xs.max()
    cols = np.arange(x0 + int(0.12 * (x1 - x0)), x1 - int(0.12 * (x1 - x0)))
    yb = (m.shape[0] - 1 - np.argmax(m[::-1, cols], axis=0)).astype(np.float64)
    k, b = np.polyfit(cols, yb, 1)
    for _ in range(2):
        res = np.abs(yb - (k * cols + b))
        keep = res <= np.percentile(res, 60)
        k, b = np.polyfit(cols[keep], yb[keep], 1)
    ang = float(np.degrees(np.arctan(k)))
    if abs(ang) < 0.6 or abs(ang) > lim:
        return rgb, alpha, 0.0
    R = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).rotate(ang, Image.BICUBIC, expand=True)
    A = Image.fromarray((alpha * 255).astype(np.uint8)).rotate(ang, Image.BICUBIC, expand=True)
    return np.asarray(R, dtype=np.float64), np.asarray(A, dtype=np.float64) / 255, ang


def main():
    cut, src, out2, out1 = sys.argv[1:5]
    wb = [1.0, 1.0, 1.0]
    white = '--white' in sys.argv
    if '--wb' in sys.argv:
        wb = [float(x) for x in sys.argv[sys.argv.index('--wb') + 1].split(',')]
    rgb, alpha = load(cut, src)
    alpha = clean_alpha(alpha)
    if '--table' in sys.argv:          # стол сквозь пустоты (реечные на чёрной основе)
        alpha, ntab = drop_table(rgb, alpha)
        print('table pixels removed', ntab)
    if white and '--nofill' not in sys.argv:
        alpha, nfill = fill_white(rgb, alpha)
        print('white fill', nfill)
    if '--nodeskew' not in sys.argv:
        rgb, alpha, ang = deskew(rgb, alpha)
        print('deskew %.1f' % ang)
    rgb = rgb * np.array(wb)
    if white and '--autowb' in sys.argv:   # белое изделие: нейтрализуем по нему самому
        mm = alpha > 0.9
        l0 = rgb.mean(-1)
        sel = mm & (l0 > np.percentile(l0[mm], 40))
        mu = rgb[sel].mean(0)
        rgb = rgb * (mu.mean() / mu)
    if not white and '--hollows' in sys.argv:
        rgb, nfix = fix_hollows(rgb, alpha)
        print('hollow pixels fixed', nfix)
    m = alpha > 0.9
    lumv = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])[m]
    if white:
        hi = np.percentile(lumv, 97)
        rgb = np.clip(rgb * (246.0 / max(hi, 1)), 0, 255)
        lum2 = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])
        med = np.median(lum2[m & (lum2 > 120)])
        g = np.log(232.0 / 246) / np.log(max(min(med, 245), 150) / 246)   # медиана белых -> 232, верх остаётся 246
        rgb = 246.0 * (rgb / 246.0) ** g
    else:
        hi = np.percentile(lumv, 99.5)
        if hi > 250:
            rgb = rgb * (250.0 / hi)
    rgb = np.clip(rgb, 0, 255)
    ys, xs = np.where(alpha > 0.5)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    s = min(W2 * 0.80 / bw, H2 * 0.82 / bh)
    nw, nh = int(round(rgb.shape[1] * s)), int(round(rgb.shape[0] * s))
    rgb_s = np.asarray(Image.fromarray(rgb.astype(np.uint8)).resize((nw, nh), Image.LANCZOS), dtype=np.float64)
    al_s = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS), dtype=np.float64) / 255
    cx, cy = (x0 + x1) / 2 * s, (y0 + y1) / 2 * s
    ox, oy = int(round(W2 / 2 - cx)), int(round(H2 * 0.52 - cy))
    canvas_rgb = np.zeros((H2, W2, 3))
    canvas_al = np.zeros((H2, W2))
    sy0, sx0 = max(0, -oy), max(0, -ox)
    dy0, dx0 = max(0, oy), max(0, ox)
    hh, ww = min(nh - sy0, H2 - dy0), min(nw - sx0, W2 - dx0)
    canvas_rgb[dy0:dy0 + hh, dx0:dx0 + ww] = rgb_s[sy0:sy0 + hh, sx0:sx0 + ww]
    canvas_al[dy0:dy0 + hh, dx0:dx0 + ww] = al_s[sy0:sy0 + hh, sx0:sx0 + ww]
    # фон: «Антрацит», чуть светлее в центре
    yy, xx = np.mgrid[0:H2, 0:W2]
    r = np.sqrt(((xx - W2 / 2) / (W2 * 0.6)) ** 2 + ((yy - H2 * 0.5) / (H2 * 0.7)) ** 2)
    glow = np.clip(1 - r, 0, 1) ** 1.5
    bg = BG[None, None, :] * (1 + 0.18 * glow[..., None])
    # тени: широкая мягкая и контактная
    A = Image.fromarray((canvas_al * 255).astype(np.uint8))
    soft = np.asarray(A.transform(A.size, Image.AFFINE, (1, 0, 0, 0, 1, -18)).filter(ImageFilter.GaussianBlur(28)), dtype=np.float64) / 255
    cont = np.asarray(A.transform(A.size, Image.AFFINE, (1, 0, 0, 0, 1, -4)).filter(ImageFilter.GaussianBlur(5)), dtype=np.float64) / 255
    shade = 1 - 0.55 * soft - 0.35 * cont
    bg = bg * np.clip(shade, 0.25, 1)[..., None]
    out = canvas_rgb * canvas_al[..., None] + bg * (1 - canvas_al[..., None])
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    img.save(out2, quality=90, optimize=True, progressive=True)
    img.resize((W2 // 2, H2 // 2), Image.LANCZOS).save(out1, quality=88, optimize=True, progressive=True)
    print('ok', out2, 'scale %.2f' % s)


if __name__ == '__main__':
    main()
