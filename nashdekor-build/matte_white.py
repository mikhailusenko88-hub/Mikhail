"""Белые изделия на карточках — «матовый белый»: убрать разводы и пятна на гранях, рельеф и зерно среза оставить.

Изделие — вытянутый профиль: вдоль длины свет почти не меняется, а пятна меняются. Поэтому сглаживаем ВДОЛЬ длины
(по лучам к точке схода продольных кромок) — рисунок поперёк профиля остаётся нетронутым.

    python3 matte_white.py in2x.jpg out2x.jpg [out1x.jpg] [--standing]
    python3 matte_white.py --batch <папка img/2x> <папка img> файл1.jpg файл2.jpg …      (файлы *_3.jpg считаются «стоя»)
"""
import sys, os, cv2, numpy as np


def field(v, w, h, sc=1.0):
    """единичные направления лучей к точке v (однородные координаты, в тысячах пикселей исходника); sc — пикселей исходника в одном пикселе сетки"""
    X, Y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    dx = v[0] - v[2] * X * sc / 1000; dy = v[1] - v[2] * Y * sc / 1000; n = np.sqrt(dx * dx + dy * dy) + 1e-9
    return X, Y, (dx / n).astype(np.float32), (dy / n).astype(np.float32)


def smear(Ls, v, inner, body, sc, reach=48):
    """насколько картинка меняется, если размазать её вдоль лучей к точке v: вдоль длины профиля — почти никак.
       Считаем только в середине изделия по ходу луча — у концов срез, он к рисунку профиля не относится. Срез бывает высоким
       (у молдингов), поэтому пробуем отступ от края 112, 176 и 240 точек исходника и берём лучший результат."""
    h, w = Ls.shape; X, Y, dx, dy = field(v, w, h, sc); acc = Ls.copy(); n = 1; ins = body.copy(); marks = {}
    ts = sorted(set([reach * k / 6 for k in range(1, 7)] + list(range(64, 241, 16))))
    for t in ts:
        for sg in (1, -1):
            mx = X + sg * t / sc * dx; my = Y + sg * t / sc * dy
            ins *= cv2.remap(body, mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            if t <= reach: acc += cv2.remap(Ls, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE); n += 1
        if t in (112, 176, 240): marks[t] = ins > 0
    d = acc / n - Ls; d = d * d; best = float("inf")
    for m in marks.values():
        mid = inner & m
        if mid.sum() >= 5000 / (sc * sc): best = min(best, float(d[mid].mean()))
    return best


def by_lines(L8, obj):
    """точки схода семейств прямых кромок (до трёх)"""
    h, w = L8.shape
    segs = cv2.createLineSegmentDetector(0).detect(L8)[0]
    if segs is None: return []
    S = segs.reshape(-1, 4).astype(np.float64); ln = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1])
    near = cv2.dilate((obj > .5).astype(np.uint8), np.ones((15, 15), np.uint8))
    mid = np.clip(((S[:, :2] + S[:, 2:]) / 2).astype(int), 0, [w - 1, h - 1])
    ok = (ln > .05 * w) & (near[mid[:, 1], mid[:, 0]] > 0); S, ln = S[ok], ln[ok]
    if len(S) < 2: return []
    o = np.argsort(-ln)[:90]; S, ln = S[o], ln[o]
    P1 = np.c_[S[:, :2] / 1000, np.ones(len(S))]; P2 = np.c_[S[:, 2:] / 1000, np.ones(len(S))]
    Ls = np.cross(P1, P2); Ls /= np.linalg.norm(Ls[:, :2], axis=1, keepdims=True)
    M = (P1 + P2) / 2; D = P2 - P1; D = D[:, :2] / np.linalg.norm(D[:, :2], axis=1, keepdims=True)

    def inliers(v):
        d = v[:2][None] - v[2] * M[:, :2]; n = np.linalg.norm(d, axis=1) + 1e-12
        return np.abs((d * D).sum(1) / n) > np.cos(np.radians(1.3))
    free = np.ones(len(S), bool); out = []
    for _ in range(3):
        idx = np.where(free)[0][:30]; best, bi = -1, None
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                v = np.cross(Ls[idx[a]], Ls[idx[b]]); nv = np.linalg.norm(v)
                if nv < 1e-9: continue
                inl = inliers(v / nv) & free; sc = ln[inl].sum()
                if sc > best: best, bi = sc, inl
        if bi is None or bi.sum() < 2: break
        A = (Ls[bi] * ln[bi, None]).T @ Ls[bi]; out.append(np.linalg.eigh(A)[1][:, 0]); free &= ~bi
    return out


def by_search(L, obj):
    """перебор направлений: ищем то, вдоль которого рисунок не меняется (для изделий без прямых кромок)"""
    h, w = L.shape
    q = cv2.resize(L, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    body = cv2.erode((cv2.resize(obj, (w // 4, h // 4)) > .9).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32)
    inner = cv2.erode(body, np.ones((5, 5), np.uint8)) > 0
    ys, xs = np.nonzero(body > 0)
    if len(xs) < 300: return None
    cx, cy = xs.mean() * 4, ys.mean() * 4

    def vec(th, kap):
        c, s = np.cos(np.radians(th)), np.sin(np.radians(th))
        return np.array([c, s, 0.0]) if abs(kap) < 1e-9 else np.array([(cx + c / kap) / 1000, (cy + s / kap) / 1000, 1.0])
    best = (float("inf"), 0, 0)
    for kap in (0, 1 / 6000, -1 / 6000, 1 / 3000, -1 / 3000, 1 / 1800, -1 / 1800, 1 / 1100, -1 / 1100, 1 / 700, -1 / 700):
        for th in range(0, 180, 6):
            e = smear(q, vec(th, kap), inner, body, 4.0)
            if e < best[0]: best = (e, th, kap)
    if not np.isfinite(best[0]): return None
    hq = cv2.resize(L, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    body2 = cv2.erode((cv2.resize(obj, (w // 2, h // 2)) > .9).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32); inner2 = cv2.erode(body2, np.ones((9, 9), np.uint8)) > 0
    e, th, kap = best; e = smear(hq, vec(th, kap), inner2, body2, 2.0, 96); dth, dk = 3.0, 1 / 9000
    for _ in range(5):
        for a, b in ((dth, 0), (-dth, 0), (0, dk), (0, -dk)):
            e2 = smear(hq, vec(th + a, kap + b), inner2, body2, 2.0, 96)
            if e2 < e: e, th, kap = e2, th + a, kap + b
        dth /= 2; dk /= 2
    return vec(th, kap)


def direction(L, obj, standing=False):
    """точка схода продольных кромок. Образцы короткие: кромки среза бывают длиннее продольных, поэтому выбираем по самому рисунку"""
    if standing: return np.array([0.0, 1.0, 0.0]), 0.0                       # стоячие снимки выровнены: длина — строго по вертикали
    h, w = L.shape
    small = cv2.resize(L, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    body = cv2.erode((cv2.resize(obj, (w // 2, h // 2)) > .9).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)
    inner = cv2.erode(body, np.ones((9, 9), np.uint8)) > 0
    cands = by_lines(np.clip(L, 0, 255).astype(np.uint8), obj)
    es = [smear(small, v, inner, body, 2.0) for v in cands]
    if not es or min(es) > 2.2:
        v = by_search(L, obj)
        if v is not None: cands.append(v); es.append(smear(small, v, inner, body, 2.0))
    if not es or not np.isfinite(min(es)): return None, None
    k = int(np.argmin(es)); return cands[k], es[k]


def along(L, v, sig_t=110.0, sig_r=6.0, step=3, cross=False):
    """сглаживание вдоль лучей к точке схода; через границы (фон, срез, чужая грань) не переходит.
       cross — то же поперёк лучей (второй, слабый проход: убирает оставшиеся бледные полосы на широких гладких гранях)"""
    h, w = L.shape; X, Y, dx, dy = field(v, w, h)
    if cross: dx, dy = -dy, dx
    ref = cv2.GaussianBlur(L, (0, 0), 1.3); acc = L.copy(); ws = np.ones_like(L)
    for sgn in (1, -1):
        alive = np.ones_like(L)
        for t in range(step, int(2.2 * sig_t) + 1, step):
            mx = X + sgn * t * dx; my = Y + sgn * t * dy
            s = cv2.remap(L, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE); r = cv2.remap(ref, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            d = np.abs(r - ref); alive *= (d < 2.4 * sig_r)
            k = np.exp(-t * t / (2 * sig_t * sig_t)) * np.exp(-d * d / (2 * sig_r * sig_r)) * alive
            acc += s * k; ws += k
    return acc / ws


def flat_faces(D, obj):
    """широкие ПЛОСКИЕ грани: убрать большое мягкое пятно (тень от телефона, отсвет) — свет на плоской грани должен меняться ровно.
       Грань — связная область без перепадов; подгоняем к ней плоскость и убираем 80 % отклонения. Выгнутые грани (отклонение большое) не трогаем."""
    b = cv2.GaussianBlur(D, (0, 0), 3.0); g = np.hypot(cv2.Sobel(b, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(b, cv2.CV_32F, 0, 1, ksize=3)) / 8
    sm = cv2.morphologyEx(((g < .12) & (obj > .98)).astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(sm, connectivity=4); C = np.zeros_like(D); done = 0
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 9000: continue
        ys, xs = np.nonzero(lab == i); z = D[ys, xs]; A = np.c_[xs, ys, np.ones(len(xs))].astype(np.float64)
        k = np.linalg.lstsq(A, z.astype(np.float64), rcond=None)[0]; r = z - (A @ k).astype(np.float32)
        if r.std() > 5.5: continue
        C[ys, xs] = -.8 * r; done += 1
    return D + cv2.GaussianBlur(C, (0, 0), 6.0), done


def matte(im, standing=False, info=None):
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32); L = lab[..., 0]
    obj = cv2.GaussianBlur(np.clip((L - 120) / 50, 0, 1), (0, 0), 1.2)                 # изделие (светлое) против тёмного фона
    v, e = direction(L, obj, standing)
    if info is not None: info.update(v=None if v is None else [round(float(x), 4) for x in v], e=None if e is None else round(e, 2))
    if v is None or e > 4.0: return None                                               # направление не нашлось — не трогаем, смотреть глазами
    D = along(L, v)
    D = along(D, v, 60.0, 2.5, 3, True)                                                 # порог 2,5 ступени яркости: рельеф (перепады от 6) не задевает
    D, nf = flat_faces(D, obj)
    if info is not None: info.update(faces=nf)
    H = L - cv2.GaussianBlur(L, (0, 0), 2.2)                                           # мелкие детали: зерно среза, кромки
    A = cv2.GaussianBlur(np.abs(H), (0, 0), 4.0); w = np.clip((A - 1.2) / 1.6, 0, 1); w = w * w * (3 - 2 * w)
    out = D * (1 - w) + (cv2.GaussianBlur(D, (0, 0), 2.2) + H) * w
    out += np.random.default_rng(7).normal(0, .35, L.shape).astype(np.float32) * (1 - w)   # едва заметное зерно — грань не выглядит «пластиком»
    lab[..., 0] = L * (1 - obj) + out * obj
    res = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    return np.where((obj > .004)[..., None], res, im)                                  # фон — пиксель в пиксель прежний


def save(res, p2, p1=None):
    cv2.imwrite(p2, res, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if p1: cv2.imwrite(p1, cv2.resize(res, (res.shape[1] // 2, res.shape[0] // 2), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--batch":
        d2, d1 = a[1], a[2]
        for f in a[3:]:
            info = {}; im = cv2.imread(os.path.join(d2, f)); res = matte(im, f.endswith("_3.jpg"), info)
            if res is None: print("ПРОПУСК", f, info, flush=True); continue
            save(res, os.path.join(d2, f), os.path.join(d1, f)); print("ok", f, info, flush=True)
    else:
        st = "--standing" in a; a = [x for x in a if x != "--standing"]
        res = matte(cv2.imread(a[0]), st)
        if res is None: sys.exit("направление не нашлось")
        save(res, a[1], a[2] if len(a) > 2 else None)
