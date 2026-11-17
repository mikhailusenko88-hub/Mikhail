# Цветной предпросмотр героя (лучом по полю): глаза с радужкой и бликами, нос, шарф, линии рта, брови, мягкий «плюшевый» свет.
# Запуск из папки heroes: OUT=<папка> python3 prev_cvet.py hero_fila <тег> [a|o|blink] <вид...>   (виды: face face34 front f34 side); два вида — около 15 с.
# Печатает, насколько глаз выступает из головы (в % радиуса): 25–35% — «сидит в голове», больше 50% — «навыкате».
import sys, os, numpy as np, importlib, math
sys.path.insert(0, '.')
from hero_common import *
import eye_open
from PIL import Image
m = importlib.import_module(sys.argv[1]); H = m.HERO; tag = sys.argv[2]; views = sys.argv[3:]
VAR = 'base'
if views and views[0] in ('a', 'o', 'blink'): VAR = views[0]; views = views[1:]
H.set_var('base'); OPEN = eye_open.opening(H)
S = H.EYE_S if H.EYE_S is not None else V(1, 1, 1)
kh, kv = H.EYE_CENTER if isinstance(getattr(H, 'EYE_CENTER', 0), tuple) else (getattr(H, 'EYE_CENTER', 0),) * 2
IDIR = []
for (c, _), E in zip(OPEN, H.EYES):
    if getattr(H, 'EYE_CENTER', 0): yw = math.atan2(c[0], -c[1]) * kh; pt = math.atan2(c[2], -c[1]) * kv; IDIR.append(nrm(V(math.tan(yw), -1, math.tan(pt))))
    else:
        d = nrm(H.EYE_AIM - E); a = float(getattr(H, 'EYE_DIV', 0)) * np.sign(E[0]); cs, sn = math.cos(a), math.sin(a); IDIR.append(V(d[0] * cs - d[1] * sn, d[0] * sn + d[1] * cs, d[2]))
for E in H.EYES[:1]:
    ts = np.linspace(0, 1.6, 400) * H.RE; pp = np.array([E + V(0, -x, 0) for x in ts], F); d0 = H.parts(pp); hd = smin(d0['head'], d0['muzzle'], H.K_MUZ)
    t0 = ts[np.argmax(hd > 0)] if (hd > 0).any() else 0; print('глаз выступает из головы на %.0f%% радиуса' % ((H.RE * float(S[1]) - t0) / H.RE * 100))
H.set_var(VAR)
K = getattr(H, 'EYE_K', (0.70, 0.915)); ACCS = getattr(H, 'ACCS', None) or [dict(fn='acc_fn', col=(0.3, 0.5, 0.8))]
def eyes_sd(p):
    d = np.full(len(p), 9.0, F)
    for E in H.EYES: d = np.minimum(d, (np.linalg.norm((p - E) / S, axis=-1) - H.RE) * float(S.min()))
    return d
def comps(p): return [H.field(p), eyes_sd(p), H.nose_fn(p)] + [getattr(H, a['fn'])(p) for a in ACCS]
def scene(p): return np.minimum.reduce(comps(p))
def seg_d(P, L):
    L = np.asarray(L, F); out = np.full(len(P), 9.0, F)
    for a, b in zip(L[:-1], L[1:]):
        ab = b - a; t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1); out = np.minimum(out, np.linalg.norm(P - a - t[:, None] * ab, axis=-1))
    return out
LINES = H.mouth_lines()
BR = getattr(H, 'BROW', None) or {}
def brow_pts(E, dL):
    up = float(BR.get('up', 1.32)); w = float(BR.get('w', .82)); U0 = nrm(V(0, 0, 1) - dL * dL[2]); Sx = nrm(np.cross(dL, U0)); pts = []
    for j in range(9):
        u = j / 8 * 2 - 1; arch = 1 - u * u; pts.append(E + dL * H.RE * .55 + U0 * H.RE * (up + .14 * arch) + Sx * u * H.RE * w)
    o = np.array(pts, F); return H.hit(o - np.tile(V(0, 1, 0), (9, 1)) * 0.2, np.tile(V(0, 1, 0), (9, 1)), 0.5)
BROWS = [brow_pts(E, d) for E, d in zip(H.EYES, IDIR)] if VAR != 'blink' else []
hz = float(H.H[2]); k = hz / 0.414
VW = {'face': dict(eye=(0.0, -0.95 * k, hz + 0.02), look=(0, 0, hz - 0.005), fov=24, W=400, Hh=400), 'face34': dict(eye=(0.42 * k, -0.85 * k, hz + 0.06), look=(0, -0.02, hz - 0.005), fov=24, W=400, Hh=400),
      'front': dict(eye=(0.0, -2.1 * k, hz * 0.62), look=(0, 0, hz * 0.6), fov=24, W=300, Hh=440), 'f34': dict(eye=(0.95 * k, -1.85 * k, hz * 0.75), look=(0, 0, hz * 0.6), fov=24, W=300, Hh=440),
      'side': dict(eye=(2.1 * k, -0.2 * k, hz * 0.62), look=(0, 0, hz * 0.6), fov=24, W=300, Hh=440)}
def ss(a, b, x): t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
def render(eye, look, fov, W, Hh):
    eye = V(*eye); look = V(*look); fw = nrm(look - eye); rt = nrm(np.cross(fw, V(0, 0, 1))); up = np.cross(rt, fw)
    ys, xs = np.mgrid[0:Hh, 0:W]; t = math.tan(math.radians(fov) / 2)
    u = ((xs + .5) / W * 2 - 1) * t * W / Hh; v = -((ys + .5) / Hh * 2 - 1) * t
    dirs = nrm(fw[None] + u.reshape(-1, 1) * rt[None] + v.reshape(-1, 1) * up[None]).astype(F)
    o = np.tile(eye, (len(dirs), 1)); tt = np.full(len(dirs), max(0.0, float(np.linalg.norm(eye)) - 1.1), F); hitm = np.zeros(len(dirs), bool); live = np.ones(len(dirs), bool)
    for _ in range(150):
        idx = np.nonzero(live)[0]
        if not len(idx): break
        d = scene(o[idx] + dirs[idx] * tt[idx, None]); h = d < 0.0006; hitm[idx[h]] = True; tt[idx] = np.where(h, tt[idx], tt[idx] + np.maximum(d, 0.0008)); live[idx[h]] = False; live[idx[tt[idx] > 6]] = False
    sky = np.linspace(0, 1, Hh)[:, None, None]; img = (V(0.62, 0.78, 0.93)[None, None] * (1 - sky) + V(0.5, 0.72, 0.42)[None, None] * sky) * np.ones((Hh, W, 1), F); img = img.reshape(-1, 3).copy()
    hi = np.nonzero(hitm)[0]
    if not len(hi): return img.reshape(Hh, W, 3)
    P = o[hi] + dirs[hi] * tt[hi, None]; g = np.zeros_like(P); e = 0.0007
    for kk in range(3): dp = np.zeros(3, F); dp[kk] = e; g[:, kk] = scene(P + dp) - scene(P - dp)
    n = nrm(g); Vv = -dirs[hi]; C = np.stack(comps(P), -1); who = np.argmin(C, -1)
    Lk = nrm(V(-0.45, -0.62, 0.65)); Lr = nrm(V(0.5, 0.7, 0.5))
    ndl = n @ Lk; fres = np.clip(1 - np.sum(n * Vv, -1), 0, 1)
    col = np.zeros((len(P), 3), F); spec = np.zeros(len(P), F)
    b = who == 0
    if b.any():
        Pb = P[b]; reg = H.region_of(Pb); skin, fur = H.colors(Pb, reg, n[b]); ok = H.fur_ok(Pb, reg); base = np.where(ok[:, None], fur, skin)
        ring = np.zeros(len(Pb), bool)
        for E in H.EYES: q = Pb - E; ring |= (np.linalg.norm(q / S, axis=-1) < H.RE * 1.18) & (q[:, 1] < H.RE * 0.16)
        base = np.where((ring & ~ok)[:, None], V(*getattr(H, 'EYE_RING', (0.05, 0.035, 0.03)))[None], base)
        ld = np.full(len(Pb), 9.0, F)
        for L in LINES: ld = np.minimum(ld, seg_d(Pb, L))
        base = np.where((ld < 0.0016)[:, None], V(0.12, 0.04, 0.03)[None], base)
        if BROWS:
            bd = np.full(len(Pb), 9.0, F)
            for L in BROWS: bd = np.minimum(bd, seg_d(Pb, L))
            bw = BR.get('r', .0034); bw = float(bw[0] if isinstance(bw, (list, tuple)) else bw); bc = V(*BR['col']) if 'col' in BR else base.mean(0) * .4
            base = np.where((bd < bw)[:, None], bc[None], base)
        wrap = np.clip((ndl[b] + 0.45) / 1.45, 0, 1); amb = 0.42 + 0.2 * n[b][:, 2]
        fz = np.where(ok, fres[b] ** 2.2 * 0.55, 0.0)                                   # пушок по контуру
        rim = np.where(ok, np.clip(n[b] @ Lr, 0, 1) * fres[b] ** 1.5 * 0.9, 0.0)
        col[b] = base * (wrap[:, None] * 0.95 + amb[:, None]) * 0.86 + (fz + rim)[:, None] * (base * 0.5 + 0.5) * 0.55
    for i, (E, dL) in enumerate(zip(H.EYES, IDIR)):
        q = (P - E) / S; on = (who == 1) & (np.linalg.norm(P - E, axis=-1) < H.RE * 1.3)
        if not on.any(): continue
        qn = nrm(q[on]); cz = qn @ dL; U0 = nrm(V(0, 0, 1) - dL * dL[2]); upc = (qn @ U0) / max(math.sqrt(1 - K[0] ** 2), .1)
        I0, I1, I2 = [V(*c) for c in H.IRIS]
        if getattr(H, 'IRIS_STYLE', 0):
            tq = np.clip((K[1] - cz) / max(K[1] - K[0], 1e-3), 0, 1); ir = I1[None] + (I2 - I1)[None] * ss(0.15, -0.85, upc)[:, None]; ir = ir + (I0[None] - ir) * ss(.8, .98, tq)[:, None]
        else: ir = np.tile(I1, (len(cz), 1))
        a = V(0.9, 0.88, 0.86)[None] + (ir - V(0.9, 0.88, 0.86)[None]) * ss(K[0], K[0] + .015, cz)[:, None]; a = a + (V(0.004, 0.003, 0.003)[None] - a) * ss(K[1], K[1] + .007, cz)[:, None]
        nn = n[on]; sh = np.clip((nn @ Lk + 0.6) / 1.6, 0, 1) * 0.9 + 0.35; lidsh = 1 - 0.45 * ss(0.25, 0.95, qn @ V(0, 0, 1))      # тень от верхнего века
        c = a * (sh * lidsh)[:, None] * 1.5
        R = 2 * np.sum(nn * Vv[on], -1)[:, None] * nn - Vv[on]
        h1 = ss(0.965, 0.985, R @ nrm(V(-0.42, -0.55, 0.72))); h2 = ss(0.992, 0.997, R @ nrm(V(0.3, -0.85, -0.28)))
        c = c + (h1 * 1.6 + h2 * 0.9)[:, None] + (fres[on] ** 3 * 0.35)[:, None] * V(0.6, 0.75, 0.95)[None]
        col[on] = c
    b = who == 2
    if b.any():
        R = 2 * np.sum(n[b] * Vv[b], -1)[:, None] * n[b] - Vv[b]
        col[b] = V(*getattr(H, 'NOSE_COL', (0.05, 0.04, 0.04)))[None] * (np.clip((ndl[b] + 0.4) / 1.4, 0, 1) * 0.9 + 0.45)[:, None] + ss(0.93, 0.985, R @ nrm(V(-0.35, -0.5, 0.8)))[:, None] * 0.7 + (fres[b] ** 3 * 0.25)[:, None]
    for j, a in enumerate(ACCS):
        b = who == 3 + j
        if b.any(): col[b] = V(*a.get('col', (0.5, 0.5, 0.5)))[None] * (np.clip((ndl[b] + 0.35) / 1.35, 0, 1) * 0.95 + 0.45 + 0.15 * n[b][:, 2])[:, None]
    # мягкая тень сверху вниз (окклюзия по полю)
    ao = np.clip(scene(P + n * 0.02) / 0.02, 0.35, 1) ** 0.6
    img[hi] = col * ao[:, None]
    return img.reshape(Hh, W, 3)
import json as _js
for vn in list(views):
    if vn.startswith('cam='):
        e_, l_, f_ = vn[4:].split(':'); VW[vn] = dict(eye=tuple(map(float, e_.split(','))), look=tuple(map(float, l_.split(','))), fov=float(f_), W=600, Hh=600)
def proj(P, eye, look, fov, W, Hh):
    eye = V(*eye); look = V(*look); fw = nrm(look - eye); rt = nrm(np.cross(fw, V(0, 0, 1))); up = np.cross(rt, fw); d = P - eye; t = math.tan(math.radians(fov) / 2)
    x = (d @ rt) / (d @ fw) / (t * W / Hh); y = (d @ up) / (d @ fw) / t; return [float((x + 1) / 2 * W), float((1 - y) / 2 * Hh)]
marks = {}
outs = []
for vn in views:
    marks[vn] = {'eyes': [proj(E, **VW[vn]) for E in H.EYES], 'nose': proj(H.NOSE_C, **VW[vn])}
    im = render(**VW[vn]); im = im / (1 + 0.18 * im); im = np.clip(im, 0, 1) ** (1 / 2.2); outs.append(Image.fromarray((im * 255).astype(np.uint8)))
Wt = sum(x.size[0] for x in outs); Ht = max(x.size[1] for x in outs); sheet = Image.new('RGB', (Wt, Ht), (255, 255, 255)); x = 0
for im in outs: sheet.paste(im, (x, 0)); x += im.size[0]
sheet.save(os.path.join(os.environ.get('OUT', '.'), '%s.jpg' % tag), quality=92)
open(os.path.join(os.environ.get('OUT', '.'), '%s.json' % tag), 'w').write(_js.dumps(marks)); print('ok', sheet.size)
