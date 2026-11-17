# Мерки лица: обложка (ручная разметка) против моего героя (карта меток из prev_cvet.py, LBL=1).
# Всё меряется в «рамке лица»: начало — середина между глазами, ось x — по линии глаз, y — вниз; единица — ширина головы W на уровне глаз
# (вместе с мехом). Так поворот головы в плоскости кадра и размер картинки не мешают сравнению.
# python3 mery.py <obl.json> <ключ обложки> <моя_метка_lbl.png> <мои_метки.json> <вид> [мех, м] [метров в пикселе — авто]
import sys, json, math, numpy as np, cv2

def frame(eL, eR):
    c = (np.array(eL) + np.array(eR)) / 2; ex = np.array(eR, float) - np.array(eL, float); ex /= np.linalg.norm(ex); ey = np.array([-ex[1], ex[0]])
    return c, ex, ey

def loc(p, c, ex, ey): d = np.array(p, float) - c; return np.array([d @ ex, d @ ey])

def cover_metrics(M):
    eL, eR = M['eyes'][0]['c'], M['eyes'][1]['c']; c, ex, ey = frame(eL, eR)
    hl, hr, top = [loc(p, c, ex, ey) for p in M['head']]; W = hr[0] - hl[0]
    eyes = M['eyes']; out = {}
    out['ширина головы, px'] = W
    out['между глазами'] = np.linalg.norm(np.array(eR) - np.array(eL)) / W
    out['ширина глаза'] = np.mean([e['w'] for e in eyes]) / W
    out['высота глаза'] = np.mean([e['h'] for e in eyes]) / W
    out['радужка / ширина глаза'] = np.mean([2 * e['iris'][2] / e['w'] for e in eyes if 'iris' in e])
    ix, iy = [], []
    for k, e in enumerate(eyes):
        if 'iris' not in e: continue
        d = loc(e['iris'][:2], c, ex, ey) - loc(e['c'], c, ex, ey); toN = -1 if k == 1 else 1   # левый глаз: к носу = +x; правый: -x
        ix.append(d[0] * toN / e['w']); iy.append(d[1] / e['h'])
    out['радужка к носу (доля ширины глаза)'] = np.mean(ix); out['радужка ниже (доля высоты глаза)'] = np.mean(iy)
    out['заполненность глаза (овал = 0,785)'] = 0.785
    out['нос ниже глаз'] = loc(M['nose'], c, ex, ey)[1] / W
    out['рот ниже глаз'] = loc(M['lip'], c, ex, ey)[1] / W
    out['макушка выше глаз'] = -top[1] / W
    if M.get('ears'): out['кончик уха выше глаз'] = np.mean([-loc(e[1], c, ex, ey)[1] for e in M['ears']]) / W
    out['поворот (нос от середины головы)'] = (loc(M['nose'], c, ex, ey)[0] - (hl[0] + hr[0]) / 2) / (W / 2)
    return out

def mine_metrics(lbl_path, marks, fur_px):
    L = np.array(cv2.imread(lbl_path, cv2.IMREAD_UNCHANGED))
    eye0 = np.isin(L, (2, 5)).astype(np.uint8); n0, lab0, st0, cen0 = cv2.connectedComponentsWithStats(eye0)
    cc = sorted(range(1, n0), key=lambda i: -st0[i][4])[:2]
    if len(cc) == 2:   # центр глаза — середина видимого глаза (как на обложке), а не центр шара
        bb = [(st0[i][0] + st0[i][2] / 2.0, st0[i][1] + st0[i][3] / 2.0) for i in cc]; eL, eR = sorted(bb)
    else: eL, eR = sorted(marks['eyes'])
    c, ex, ey = frame(eL, eR); out = {}
    head = np.isin(L, (1, 2, 3, 5)); ys, xs = np.nonzero(head); P = np.stack([xs, ys], -1).astype(float); Q = (P - c) @ np.stack([ex, ey], -1)
    band = np.abs(Q[:, 1]) < 2.0; W = (Q[band, 0].max() - Q[band, 0].min()) + 2 * fur_px; hcx = (Q[band, 0].max() + Q[band, 0].min()) / 2
    Wb = Q[band, 0].max() - Q[band, 0].min(); tops = []
    for x0 in np.linspace(-0.2 * Wb, 0.2 * Wb, 21):   # макушка: медиана по полосе у середины (без «перемычки» между корнями ушей)
        m = np.abs(Q[:, 0] - x0) < 1.5
        if m.any(): tops.append(-Q[m, 1].min())
    top = float(np.median(tops)) + fur_px
    out['ширина головы, px'] = W
    out['между глазами'] = np.linalg.norm(np.array(eR) - np.array(eL)) / W
    ew, eh, ir = [], [], []
    eye = np.isin(L, (2, 5)).astype(np.uint8); n, lab, st, cen = cv2.connectedComponentsWithStats(eye)
    comps = sorted(range(1, n), key=lambda i: -st[i][4])[:2]
    ixs, iys, fills = [], [], []
    for i in comps:
        m = lab == i; yy, xx = np.nonzero(m); q = (np.stack([xx, yy], -1) - c) @ np.stack([ex, ey], -1)
        x0, x1, y0, y1 = q[:, 0].min(), q[:, 0].max(), q[:, 1].min(), q[:, 1].max(); ew.append(x1 - x0); eh.append(y1 - y0)
        ia = ((L == 5) & m).sum(); ir.append(2 * math.sqrt(ia / math.pi) / ew[-1]); fills.append(m.sum() / (ew[-1] * eh[-1]))
        yi, xi = np.nonzero((L == 5) & m); qi = (np.stack([xi, yi], -1) - c) @ np.stack([ex, ey], -1); ci = qi.mean(0)
        toN = 1 if (x0 + x1) / 2 < 0 else -1; ixs.append((ci[0] - (x0 + x1) / 2) * toN / ew[-1]); iys.append((ci[1] - (y0 + y1) / 2) / eh[-1])
    out['ширина глаза'] = np.mean(ew) / W; out['высота глаза'] = np.mean(eh) / W; out['радужка / ширина глаза'] = np.mean(ir)
    out['радужка к носу (доля ширины глаза)'] = np.mean(ixs); out['радужка ниже (доля высоты глаза)'] = np.mean(iys); out['заполненность глаза (овал = 0,785)'] = np.mean(fills)
    out['нос ниже глаз'] = loc(marks['nose'], c, ex, ey)[1] / W
    if 'lip' in marks: out['рот ниже глаз'] = loc(marks['lip'], c, ex, ey)[1] / W
    out['макушка выше глаз'] = top / W
    if (L == 6).any():
        yy, xx = np.nonzero(L == 6); q = (np.stack([xx, yy], -1) - c) @ np.stack([ex, ey], -1); out['кончик уха выше глаз'] = (-q[:, 1].min() + fur_px) / W
    out['поворот (нос от середины головы)'] = (loc(marks['nose'], c, ex, ey)[0] - hcx) / (W / 2)
    return out

if __name__ == '__main__':
    obl, key, lbl, mk, view = sys.argv[1:6]; fur_m = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
    e_, l_, f_ = view[4:].split(':'); d_ = np.linalg.norm(np.array(list(map(float, e_.split(',')))) - np.array(list(map(float, l_.split(','))))); Hpx = cv2.imread(lbl, cv2.IMREAD_UNCHANGED).shape[0]
    fur_px = fur_m / (2 * d_ * math.tan(math.radians(float(f_)) / 2) / Hpx)   # мех (м) -> px
    A = cover_metrics(json.load(open(obl))[key]); B = mine_metrics(lbl, json.load(open(mk))[view], fur_px)
    print('%-34s %9s %9s %8s' % ('мерка (доля ширины головы)', 'обложка', 'мой', 'разница'))
    for k in A:
        if k not in B: continue
        a, b = A[k], B[k]
        if 'px' in k: print('%-34s %9.0f %9.0f' % (k, a, b)); continue
        if 'доля' in k: d = (b - a) * 100; print('%-34s %9.3f %9.3f %+7.0f п.%s' % (k, a, b, d, '  ←' if abs(d) > 6 else '')); continue
        d = (b - a) / abs(a) * 100 if abs(a) > 1e-3 else float('nan')
        print('%-34s %9.3f %9.3f %7.0f%%%s' % (k, a, b, d, '  ←' if abs(d) > 10 else ''))
