# Барсик «БАРС»: лапки с пальцами из образца 6.2 + лапы отдельной сеткой от туловища (без «перепонок» под мышкой).
# TOE_K=0.22 python3 build_geo_split.py --var=s2   (SKIN_H — шаг сетки кожи, мельче — видны бороздки пальцев)
import sys, os, time, textwrap, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_geo as B
sys.path.insert(0, os.environ.get('OBRAZEC', os.path.join(HERE, '../obrazec/heroes')))
from hero_common import toe_paw
V, nrm, F = B.V, B.nrm, B.F
PAW_F = nrm(V(0, -0.042, -0.018))
def front_paw(p, i): return toe_paw(p, B.PAW[i], (0.046, 0.052, 0.042), PAW_F, tr=0.0168, tk=0.006, fk=0.7, dk=0.3)
def hind_paw(p, i): return toe_paw(p, B.FOOT[i], (0.061, 0.096, 0.039), V(0, -1, 0), tr=0.021, tk=0.007, pads=False, fk=0.72, dk=0.28)
def new_arm(p, i):
    x = B.sd_rcone(p, B.SHOULD[i], B.WRIST[i], 0.05, 0.039); x = B.smin(x, front_paw(p, i)[0], 0.026)
    return B.smin(x, B.sd_sph(p, B.SHOULD[i] + V(0, 0.005, 0.005), 0.056), 0.03)
def new_leg(p, i):
    x = B.sd_ell(p, B.HIP[i], V(0.086, 0.1, 0.098))
    x = B.smin(x, B.sd_rcone(p, B.HIP[i] + V(0, -0.02, -0.03), B.FOOT[i] + V(0, 0.02, 0.025), 0.052, 0.043), 0.04)
    return B.smin(x, hind_paw(p, i)[0], 0.035)
_parts0 = B.parts
def parts2(p):
    d = _parts0(p); d['arm'] = np.minimum(new_arm(p, 0), new_arm(p, 1)); d['leg'] = np.minimum(new_leg(p, 0), new_leg(p, 1)); return d
B.parts = parts2
def paw_masks(p, reg):
    limb = (reg == 5) | (reg == 6); toes = np.full(len(p), 9.0, F); pads = np.full(len(p), 9.0, F)
    for i in range(2):
        x, t, pd = front_paw(p, i); toes = np.minimum(toes, x); pads = np.minimum(pads, pd)
        x, t, _ = hind_paw(p, i); toes = np.minimum(toes, x)
    return limb & (toes < 0.004), limb & (pads < 0.0012)
_reg0 = B.region_of
def region2(p):
    reg = _reg0(p); _, pads = paw_masks(p, reg); return np.where(pads, 8, reg).astype(np.int32)   # подушечки — розовая кожа, как внутри уха
B.region_of = region2
_fur0 = B.make_fur
def make_fur2(v, f, nor, reg, **kw):
    fur = _fur0(v, f, nor, reg, **kw); pts = fur['fur_pts']; N = fur['fur_nrm']; R = pts[:, 0] + N * 0.0015
    rg0 = _reg0(R); toes, pads = paw_masks(R, rg0); onpad = pads | ((fur['fur_reg'] == 8) & (R[:, 2] < 0.42))
    keep = ~onpad; print('лапы: волосков на пальцах', int((toes & keep).sum()), '· убрано с подушечек', int(onpad.sum()))
    sh = np.where(toes, float(os.environ.get('TOE_K', '0.42')), 1.0).astype(F)[:, None, None]; pts = pts[:, :1] + (pts - pts[:, :1]) * sh   # на пальцах шерсть короче — пальцы читаются
    fur['fur_pts'] = pts
    for k in list(fur): fur[k] = fur[k][keep]
    return fur
B.make_fur = make_fur2
_bs0 = B.build_skin
B.build_skin = lambda h=None: _bs0(h=float(os.environ.get('SKIN_H', '0.0029')))

# ---------- лапы отдельно от туловища (без «перепонок» под мышкой) ----------
# Раньше кожа была одной поверхностью: лапа сливалась с боком по всей длине, и при поднятой лапе бок тянулся «крылом».
# Теперь туловище (с головой, ногами, хвостом) и лапы — две отдельные сетки; под лапой у туловища есть свой бок с шерстью.
NOARM = [False]
def parts3(p):
    d = parts2(p)
    if NOARM[0]: d['arm'] = np.full(len(p), 9.0, F)
    return d
B.parts = parts3
def field_body(p):
    NOARM[0] = True
    try: return B.field(p)
    finally: NOARM[0] = False
def field_arm(p): return parts2(p)['arm']
def on_arm(p): return np.abs(field_arm(p)) < np.abs(field_body(p))
def build_skin_split(h=None):
    from skimage.measure import marching_cubes
    h = float(os.environ.get('SKIN_H', '0.0029'))
    lo, hi = V(-0.33, -0.3, -0.01), V(0.33, 0.37, 1.09)
    n = np.ceil((hi - lo) / h).astype(int) + 1
    xs, ys, zs = [lo[i] + np.arange(n[i], dtype=F) * h for i in range(3)]
    vb = np.empty((n[0], n[1], n[2]), dtype=F); va = np.empty_like(vb)
    YY, ZZ = np.meshgrid(ys, zs, indexing='ij')
    for i, x in enumerate(xs):
        p = np.stack([np.full(YY.size, x, F), YY.ravel(), ZZ.ravel()], -1)
        vb[i] = field_body(p).reshape(YY.shape); va[i] = field_arm(p).reshape(YY.shape)
    v1, f1, _, _ = marching_cubes(vb, 0.0, spacing=(h, h, h)); v2, f2, _, _ = marching_cubes(va, 0.0, spacing=(h, h, h))
    v = (np.concatenate([v1, v2]) + lo).astype(F); f = np.concatenate([f1, f2 + len(v1)]).astype(np.int32)
    B.VOL = (np.minimum(vb, va).astype(np.float16), lo, np.array([h], F))
    np.savez_compressed('out/split_vol.npz', body=vb.astype(np.float16), arm=va.astype(np.float16), lo=lo, h=np.array([h], F))
    print('кожа: туловище %d, лапы %d вершин' % (len(v1), len(v2)))
    return v, f
B.build_skin = build_skin_split
def grad_split(p, e=0.0008):
    a = on_arm(p); g = np.zeros_like(p)
    for fn, m in ((field_body, ~a), (field_arm, a)):
        q = p[m]
        if not len(q): continue
        gg = np.stack([fn(q + V(*o)) - fn(q - V(*o)) for o in ((e, 0, 0), (0, e, 0), (0, 0, e))], -1)
        g[m] = nrm(gg)
    return g
B.grad = grad_split
def region3(p):
    a = on_arm(p)
    NOARM[0] = True
    try: rb = _reg0(p)
    finally: NOARM[0] = False
    _, pads = paw_masks(p, np.full(len(p), 5))
    return np.where(a, np.where(pads, 8, 5), rb).astype(np.int32)
B.region_of = region3
src = open(os.path.join(HERE, 'build_geo.py')).read(); main = src[src.index("if __name__ == '__main__':") + len("if __name__ == '__main__':"):]
exec(compile(textwrap.dedent(main), 'build_geo_main', 'exec'), B.__dict__)
