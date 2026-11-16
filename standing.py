"""Образец стоит лицом к камере (фото с телефона): точное выравнивание.
python3 standing.py <cut.png> <src.jpg> <out.png>
Что делает (v4, 16.11.2026 — после замечаний Михаила «мушки / округлые / подрезанные, угла нет»):
  1) грубая рамка — по маске нейросети (только чтобы знать, где искать);
  2) настоящие края ищем по самому снимку (перепад яркости «белый образец — серый фон»), а не по маске:
     маска на белом по светлому фону плавает на 3–10 px — от неё и были кривые бока и съеденные углы;
  3) по четырём углам — перспектива в прямоугольник (телефон снимает близко и сверху: отрезок выходит трапецией);
  4) альфа: бока — строго по прямым, верх и низ — по настоящему силуэту (профиль на срезе), углы целые;
  5) фото внутри не трогаем (ни размытия, ни «проявления граней») — свет и тени как на снимке.
Результат — PNG с альфой в исходном масштабе; фон, тень и тон добавляет compose.py --rawalpha."""
import sys
import numpy as np, cv2
from PIL import Image
from scipy.ndimage import median_filter


def robust_line(u, v, tol=1.2, it=6):
    """v = k*u + b; выбросы отбрасываем."""
    u = np.asarray(u, float); v = np.asarray(v, float)
    k, b = np.polyfit(u, v, 1)
    for _ in range(it):
        r = np.abs(v - (k * u + b))
        ok = r <= max(tol, np.percentile(r, 50))
        if ok.sum() < 8:
            break
        k, b = np.polyfit(u[ok], v[ok], 1)
    return k, b


def edge_pos(g, lo, hi, sign):
    """Позиция сильнейшего перепада нужного знака в отрезке [lo, hi) одномерного градиента g (с субпикселем)."""
    seg = g[lo:hi] * sign
    i = int(np.argmax(seg))
    val = seg[i]
    if 0 < i < len(seg) - 1:
        a, b_, c = seg[i - 1], seg[i], seg[i + 1]
        den = a - 2 * b_ + c
        off = 0.5 * (a - c) / den if abs(den) > 1e-6 else 0.0
    else:
        off = 0.0
    return lo + i + off, val


def main():
    cut, src, out = sys.argv[1:4]
    rgb = np.asarray(Image.open(src).convert('RGB'), dtype=np.float32)
    mask = np.asarray(Image.open(cut).convert('RGBA'))[..., 3] > 128
    Hh, Ww = mask.shape
    # --- 1. грубая рамка: колонки, занятые почти на всю высоту (полоса полки за образцом так не умеет)
    cnt = mask.sum(0); cols = np.where(cnt > 0.45 * cnt.max())[0]
    x0, x1 = cols.min(), cols.max()
    rc = mask[:, x0:x1 + 1].sum(1); rows = np.where(rc > 0.3 * rc.max())[0]
    y0, y1 = rows.min(), rows.max()
    W, H = x1 - x0, y1 - y0
    # --- 2. края по снимку. Яркость (L) — образец самый светлый в кадре
    L = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
    Lb = cv2.GaussianBlur(L, (0, 0), 1.3)
    gx = cv2.Sobel(Lb, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(Lb, cv2.CV_32F, 0, 1, ksize=3)
    win = max(12, int(0.03 * W))
    ys = np.arange(y0 + int(0.08 * H), y1 - int(0.16 * H), 2)
    xl, xr, yv = [], [], []
    for y in ys:
        a, va = edge_pos(gx[y], max(0, x0 - win), x0 + win, +1)
        b, vb = edge_pos(gx[y], x1 - win, min(Ww, x1 + win), -1)
        xl.append(a); xr.append(b); yv.append(y)
    # первый проход — по широкому окну, второй — узкое окно вокруг найденной прямой
    def refine(sign, first, x_from, x_to):
        k, b = robust_line(yv, first, tol=2.0)
        pts = []
        for y in ys:
            xe = k * y + b
            p, v = edge_pos(gx[y], int(max(0, xe - 6)), int(min(Ww, xe + 7)), sign)
            pts.append(p)
        return robust_line(yv, pts, tol=0.8)
    kl, bl = refine(+1, xl, 0, 0)
    kr, br = refine(-1, xr, 0, 0)
    xs = np.arange(x0 + int(0.04 * W), x1 - int(0.04 * W), 2)
    yt = [edge_pos(gy[:, x], max(0, y0 - win), y0 + win, +1)[0] for x in xs]
    kt, bt = robust_line(xs, yt, tol=2.0)
    yt = [edge_pos(gy[:, x], int(max(0, kt * x + bt - 8)), int(kt * x + bt + 9), +1)[0] for x in xs]
    kt, bt = robust_line(xs, yt, tol=1.0)
    res = np.asarray(yt) - (kt * xs + bt)
    bt += np.percentile(res, 4)                       # верхняя огибающая: выступающие рёбра не срезаем
    yb = [edge_pos(gy[:, x], y1 - win, min(Hh, y1 + win), -1)[0] for x in xs]
    yb = np.asarray(yb); sel = yb >= np.percentile(yb, 65)
    kb, bb = robust_line(xs[sel], yb[sel], tol=1.5)   # линия, на которой образец стоит (самые нижние точки)
    def cross(kx, bx, ky, by):                         # x = kx*y + bx ; y = ky*x + by
        y = (ky * bx + by) / (1 - ky * kx); return kx * y + bx, y
    TL, TR = cross(kl, bl, kt, bt), cross(kr, br, kt, bt)
    BL, BR = cross(kl, bl, kb, bb), cross(kr, br, kb, bb)
    # --- 3. перспектива в прямоугольник
    w = (np.hypot(TR[0] - TL[0], TR[1] - TL[1]) + np.hypot(BR[0] - BL[0], BR[1] - BL[1])) / 2
    h = (np.hypot(BL[0] - TL[0], BL[1] - TL[1]) + np.hypot(BR[0] - TR[0], BR[1] - TR[1])) / 2
    pad = 60
    OW, OH = int(round(w)) + 2 * pad, int(round(h)) + 2 * pad
    dst = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])
    M = cv2.getPerspectiveTransform(np.float32([TL, TR, BR, BL]), dst)
    img = cv2.warpPerspective(rgb, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    mk = cv2.warpPerspective(mask.astype(np.float32), M, (OW, OH), flags=cv2.INTER_LINEAR) > 0.5
    # --- 4. альфа. Верх и низ — по силуэту на выровненном снимке
    lab2 = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    L2 = cv2.GaussianBlur(lab2[..., 0], (0, 0), 1.1)
    g2 = cv2.Sobel(L2, cv2.CV_32F, 0, 1, ksize=3)
    Lx, Rx, Ty, By = pad, pad + w, pad, pad + h
    cx = np.arange(int(np.ceil(Lx)), int(np.floor(Rx)) + 1)
    # низ: образец белый и нейтральный (b* ≈ 133), стол бежевый (b* ≈ 152), тень под образцом тёмная.
    # «Фоновость» f = желтизна + темнота; граница — где f переходит через 0,5 (с субпикселем).
    inner = lab2[int(Ty + 0.3 * h):int(Ty + 0.7 * h), int(Lx + 0.1 * w):int(Rx - 0.1 * w)]
    b_ref = float(np.median(inner[..., 2])); L_ref = float(np.median(inner[..., 0]))
    strip0 = int(By - 0.25 * h); strip1 = int(min(OH - 1, By + 16))
    b_tab = float(np.median(lab2[int(min(OH - 1, By + 8)):strip1 + 1, int(Lx):int(Rx), 2]))
    f = np.clip((lab2[..., 2] - b_ref) / max(b_tab - b_ref, 4.0), 0, 1.2) + np.clip((L_ref - lab2[..., 0]) / 140.0, 0, 1)
    f = cv2.GaussianBlur(f, (0, 0), 0.8)
    top = np.zeros(len(cx)); bot = np.full(len(cx), np.nan); tv = np.zeros(len(cx)); bv = np.ones(len(cx))
    found = np.zeros(len(cx), bool); crosses = []
    for i, x in enumerate(cx):
        top[i], tv[i] = edge_pos(g2[:, x], int(Ty - 5), int(Ty + 0.10 * h), +1)
        col = f[strip0:strip1 + 1, x]
        idx = np.where(mk[strip0:strip1 + 1, x])[0]
        mb = float(idx.max()) if len(idx) else float(By - strip0)       # низ по маске нейросети — как подсказка
        # все переходы «образец → фон» сверху вниз; берём ближайший к подсказке (в тёмном пазу образец
        # сам похож на тень — там перехода нет, и остаётся подсказка)
        cr = np.where((col[:-1] < 0.5) & (col[1:] >= 0.5))[0]
        cr = [j0 for j0 in cr if j0 >= 3 and (col[j0 - 3:j0 + 1] < 0.5).all()]
        sub = lambda j0: strip0 + j0 + float(np.clip((0.5 - col[j0]) / max(col[j0 + 1] - col[j0], 1e-6), 0, 1))
        crosses.append([sub(j0) for j0 in cr])
        near = [c for c in crosses[-1] if abs(c - (strip0 + mb)) <= 12]
        if near:
            bot[i] = min(near, key=lambda c: abs(c - (strip0 + mb))); found[i] = True
        else:
            bot[i] = strip0 + mb + 0.5
    # второй проход: маска нейросети в тёмном пазу иногда уходит «шипом» вверх — там перехода рядом с ней нет.
    # Берём переход, ближайший к уровню соседних надёжных колонок; нет и такого — уровень соседей.
    gi = np.where(found)[0]
    if len(gi) > 10:
        for i in np.where(~found)[0]:
            k = np.searchsorted(gi, i)
            nb = [gi[j] for j in (k - 1, k) if 0 <= j < len(gi) and abs(gi[j] - i) <= 90]
            if not nb:
                continue
            target = float(np.mean([bot[j] for j in nb])) if len(nb) == 1 else \
                float(np.interp(i, nb, [bot[j] for j in nb]))
            cand = [c for c in crosses[i] if abs(c - target) <= 18]
            bot[i] = min(cand, key=lambda c: abs(c - target)) if cand else target
    bad = np.isnan(bot)
    if bad.any():
        bot[bad] = np.interp(np.where(bad)[0], np.where(~bad)[0], bot[~bad])
    # срез ножовкой даёт «бахрому» — медиана её убирает; слабый перепад сверху (блик) — берём соседей
    def clean(v, strength, k):
        v = v.copy(); bd = strength < 0.35 * np.median(strength)
        if bd.any() and (~bd).sum() > 10:
            v[bd] = np.interp(np.where(bd)[0], np.where(~bd)[0], v[~bd])
        return median_filter(v, size=k, mode='nearest')
    from scipy.ndimage import gaussian_filter1d
    top = clean(top, tv, 9); bot = clean(bot, bv, 13)
    from scipy.ndimage import grey_closing, grey_opening
    ks = max(9, int(0.022 * w)) | 1                         # узкие «шипы» (уже любого паза) — убрать в обе стороны
    bot = grey_opening(grey_closing(bot, size=ks, mode='nearest'), size=ks, mode='nearest')
    bot = gaussian_filter1d(bot, 1.5, mode='nearest')      # заусенцы среза — долой, форма профиля остаётся
    top = np.clip(top, Ty - 1, None)
    yy = np.arange(OH, dtype=np.float32)[:, None]
    alpha = np.zeros((OH, OW), np.float32)
    a = np.clip(yy - top[None, :] + 0.5, 0, 1) * np.clip(bot[None, :] - yy + 0.5, 0, 1)
    alpha[:, cx] = a
    # бока: строго вертикальные, на 1 px внутрь (без нитки фона), со сглаживанием в полпикселя
    xx = np.arange(OW, dtype=np.float32)[None, :]
    alpha *= np.clip(xx - (Lx + 1.0) + 0.5, 0, 1) * np.clip((Rx - 1.0) - xx + 0.5, 0, 1)
    if '--flatten' in sys.argv:
        # Образец — «выдавленный» профиль: вдоль высоты яркость каждой колонки должна быть ровной.
        # На фото снизу лежит тень/рефлекс от стола, сверху пересвет. Поле освещённости = яркость / медиана колонки,
        # сглаженное (только по образцу); делим на него. Рельеф (разница между колонками) и мелкая фактура остаются.
        amt = float(sys.argv[sys.argv.index('--flatten') + 1])
        lum = 0.2126 * img[..., 0] + 0.7152 * img[..., 1] + 0.0722 * img[..., 2]
        solid = (alpha > 0.98).astype(np.float32)
        r0, r1 = int(Ty + 0.25 * h), int(Ty + 0.6 * h)
        colmed = np.median(lum[r0:r1], axis=0) + 1e-3
        ratio = (lum / colmed[None, :]).astype(np.float32)
        sg = float(sys.argv[sys.argv.index("--flatsigma") + 1]) if "--flatsigma" in sys.argv else max(6.0, 0.012 * h)
        field = cv2.GaussianBlur(ratio * solid, (0, 0), sg) / np.maximum(cv2.GaussianBlur(solid, (0, 0), sg), 1e-3)
        field = np.where(solid > 0, np.clip(field, 0.6, 1.4), 1.0)
        img = img / (field[..., None] ** amt)
    out_rgba = np.dstack([np.clip(img, 0, 255), alpha * 255]).astype(np.uint8)
    Image.fromarray(out_rgba, 'RGBA').save(out)
    ang = lambda k: np.degrees(np.arctan(k))
    print('corners', [tuple(round(float(c)) for c in p) for p in (TL, TR, BR, BL)],
          'tilt L %.2f R %.2f top %.2f bottom %.2f' % (ang(kl), ang(kr), ang(kt), ang(kb)), 'size %dx%d' % (w, h))


if __name__ == '__main__':
    main()
