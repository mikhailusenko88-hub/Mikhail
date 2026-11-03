# Вязаный шарф Барсика (как в «Мультиках»: два пухлых оборота, узел сбоку, два конца с кисточками)
# + шерстяные ворсинки на нём (область 12) — они, как шерсть, светятся своим запечённым светом.
# out/geo_s2.npz -> out/geo_s3.npz (шерсть та же, только убраны волоски под новым шарфом)
import sys, time, math, numpy as np
sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a.startswith('--var=')] + sys.argv[1:]
import build_geo as B
F = np.float32; V = B.V; nrm = B.nrm

# ---------- форма (те же числа — в шейдере телефона, KNIT_GLSL) ----------
RINGS = [  # центр, радиус кольца, радиус «трубки», сплющенность трубки по высоте, наклон
    (V(0, -0.012, 0.582), 0.106, 0.044, 0.84, 0.05),    # по талии шеи (z 0,56–0,58): плечи и спина сквозь шарф не выходят
    (V(0, -0.004, 0.614), 0.100, 0.034, 0.84, 0.12)]
KNOT = (V(0.066, -0.128, 0.547), V(0.046, 0.037, 0.041))
KNOT2 = (V(0.05, -0.128, 0.53), V(0.03, 0.026, 0.03))
TAILS = [  # начало, конец, полуширина у начала/у конца, полутолщина
    (V(0.052, -0.141, 0.53), V(0.03, -0.15, 0.385), 0.027, 0.034, 0.0098),
    (V(0.08, -0.137, 0.525), V(0.104, -0.14, 0.42), 0.025, 0.031, 0.0098)]
NTAS = 4; TAS_L = 0.031; TAS_R = 0.0042
ROWH, COLW = 0.0075, 0.0105; NR = [89, 84]; NC = [24, 19]; NCK = 25   # петли: высота ряда, ширина столбика (целые числа петель по кругу)

def ring_sd(p, c, R, r, zs, rx):
    q = p - c; cs, sn = math.cos(rx), math.sin(rx)
    y = q[:, 1] * cs - q[:, 2] * sn; z = q[:, 1] * sn + q[:, 2] * cs
    a = np.sqrt(q[:, 0] ** 2 + y ** 2) - R
    k = np.sqrt(a ** 2 + (z / zs) ** 2)
    return (k - r) * np.where(np.abs(z) > np.abs(a), zs, 1.0) * 0.5 + (k - r) * 0.5 * min(1.0, zs)

def tail_frame(a, b):
    u = b - a; L = float(np.linalg.norm(u)); u = u / L
    n = V(0, -1, 0.0); n = n - u * float(n @ u); n = n / np.linalg.norm(n); w = np.cross(u, n)
    return u, n, w, L

def tail_sd(p, a, b, hw0, hw1, ht):
    u, n, w, L = tail_frame(a, b); q = p - a
    s = q @ u; sc = np.clip(s, 0, L); hw = hw0 + (hw1 - hw0) * sc / L
    # конец чуть изогнут к груди и волной по краю
    dn = q @ n + 0.004 * np.sin(sc / L * 3.0); dw = q @ w; ds = s - sc
    rr = ht
    qx = np.abs(ds); qy = np.abs(dw) - hw + rr; qz = np.abs(dn) - ht + rr
    qq = np.stack([np.maximum(qx, 0), np.maximum(qy, 0), np.maximum(qz, 0)], -1)
    return np.linalg.norm(qq, axis=-1) + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0) - rr

def tassels():
    out = []; rng = np.random.default_rng(5)
    for (a, b, hw0, hw1, ht) in TAILS:
        u, n, w, L = tail_frame(a, b)
        for i in range(NTAS):
            x = (i - (NTAS - 1) / 2) / ((NTAS - 1) / 2) * hw1 * 0.78
            s0 = b + w * x - u * 0.004
            d = nrm(u * 1.0 + w * (x / hw1) * 0.18 + n * 0.12 + V(*(rng.normal(size=3) * 0.05)))
            out.append((s0, s0 + d * TAS_L * (0.85 + 0.3 * rng.random())))
    return out
TAS = tassels()

def knit_uv(q):   # то же, что knitUV в шейдере телефона
    best = np.full(len(q), 1e9, F); res = np.zeros((len(q), 3), F)
    def put(sd, r):
        nonlocal best, res; m = sd < best; best = np.where(m, sd, best); res = np.where(m[:, None], r, res)
    for i, (c, R, r, zs, rx) in enumerate(RINGS):
        d = q - c; cs, sn = math.cos(rx), math.sin(rx); y = d[:, 1] * cs - d[:, 2] * sn; z = d[:, 1] * sn + d[:, 2] * cs; a = np.sqrt(d[:, 0] ** 2 + y ** 2) - R
        put(np.sqrt(a ** 2 + (z / zs) ** 2) - r, np.stack([np.arctan2(z / zs, a) / 6.2832 * NC[i], np.arctan2(y, d[:, 0]) / 6.2832 * NR[i], np.zeros_like(a)], -1))
    d = q - KNOT[0]; put((np.linalg.norm(d / KNOT[1], axis=-1) - 1) * 0.037, np.stack([np.arctan2(d[:, 1], d[:, 0]) / 6.2832 * NCK, np.arctan2(d[:, 2], np.linalg.norm(d[:, :2], axis=-1)) * 0.042 / ROWH, np.zeros(len(q))], -1))
    for (a0, b0, hw0, hw1, ht) in TAILS:
        u, n, w, L = tail_frame(a0, b0); d = q - a0; s_ = d @ u; dn = d @ n; dw = d @ w; sc = np.clip(s_, 0, L); hw = hw0 + (hw1 - hw0) * sc / L
        put(np.maximum(np.maximum(np.abs(dn) - ht, np.abs(dw) - hw), np.maximum(-s_, s_ - L)), np.stack([dw / COLW + np.where(dn > 0, 0.5, 0), s_ / ROWH, np.zeros(len(q))], -1))
    for (a0, b0) in TAS:
        pa = q - a0; ba = b0 - a0; hh = np.clip(pa @ ba / (ba @ ba), 0, 1); rr = pa - ba * hh[:, None]
        bn = ba / np.linalg.norm(ba); e1 = np.cross(bn, V(1, 0, 0)); e1 /= np.linalg.norm(e1); e2 = np.cross(bn, e1)
        put(np.linalg.norm(rr, axis=-1) - 0.0038, np.stack([np.arctan2(rr @ e2, rr @ e1) / 6.2832, hh * np.linalg.norm(ba) / 0.0045, np.ones(len(q))], -1))
    return res
def knit_h(q):
    kv = knit_uv(q); cx = kv[:, 0] - np.floor(kv[:, 0]) - 0.5; cy = kv[:, 1] - np.floor(kv[:, 1]); h = np.zeros(len(q), F)
    for k in (-1, 0, 1):
        y = cy - k - 0.5
        for sx in (-1, 1):
            dx = cx - sx * 0.235; an = sx * 0.52; ca, sa = math.cos(an), math.sin(an); rx_ = ca * dx - sa * y; ry_ = sa * dx + ca * y
            e = np.sqrt((rx_ / 0.2) ** 2 + (ry_ / 0.56) ** 2); h = np.maximum(h, np.sqrt(np.maximum(0, 1 - e * e)) * (0.9 + 0.1 * np.cos(ry_ * 11)))
    tw = 0.5 + 0.5 * np.sin(6.2832 * (kv[:, 1] + kv[:, 0] * 2)); return np.where(kv[:, 2] > 0.5, tw, h)

def scarf_main(p):
    d = None
    for (c, R, r, zs, rx) in RINGS:
        e = ring_sd(p, c, R, r, zs, rx); d = e if d is None else B.smin(d, e, 0.012)
    d = B.smin(d, B.sd_ell(p, *KNOT), 0.02); d = B.smin(d, B.sd_ell(p, *KNOT2), 0.012)
    for t in TAILS: d = B.smin(d, tail_sd(p, *t), 0.012)
    return d

def tassel_sd(p):
    d = np.full(len(p), 9.0, F)
    for (a, b) in TAS: d = np.minimum(d, B.sd_rcone(p, a, b, TAS_R, TAS_R * 0.72))
    return d

def scarf_new(p):
    return np.minimum(B.smin(scarf_main(p), tassel_sd(p), 0.004), 9.0)

if __name__ == '__main__':
    t0 = time.time()
    if '--preview' in sys.argv:
        fn = lambda q: np.minimum(B.field(q), scarf_new(q))
        B.preview('out/knit_prev_front.png', eye=(0.35, -1.6, 0.62), look=(0.02, -0.05, 0.52), fov=26, fn=fn)
        B.preview('out/knit_prev_34.png', eye=(1.0, -1.25, 0.75), look=(0.02, -0.03, 0.55), fov=28, fn=fn)
        B.preview('out/knit_prev_back.png', eye=(-0.9, 1.3, 0.8), look=(0, 0, 0.58), fov=28, fn=fn)
        print('preview', time.time() - t0); sys.exit()

    # ---------- сборка ----------
    from skimage.measure import marching_cubes
    def mesh_chunked(fn, lo, hi, h):
        lo, hi = V(*lo), V(*hi); n = np.ceil((hi - lo) / h).astype(int) + 1
        xs = [lo[i] + np.arange(n[i], dtype=F) * h for i in range(3)]; vol = np.empty((n[0], n[1], n[2]), F)
        for i in range(n[0]):
            g = np.stack(np.meshgrid(np.array([xs[0][i]], F), xs[1], xs[2], indexing='ij'), -1).reshape(-1, 3); vol[i] = fn(g).reshape(n[1], n[2])
        v, f, _, _ = marching_cubes(vol, 0.0, spacing=(h, h, h)); return (v + lo).astype(F), f.astype(np.int32)
    G = dict(np.load('out/geo_s2.npz'))
    mv, mf = mesh_chunked(scarf_main, (-0.17, -0.2, 0.36), (0.17, 0.12, 0.68), 0.0018)
    tl = np.array([np.minimum(a, b) for a, b in TAS]).min(0) - 0.008; th = np.array([np.maximum(a, b) for a, b in TAS]).max(0) + 0.008
    tv, tf = mesh_chunked(tassel_sd, tl, th, 0.0007)
    sv = np.concatenate([mv, tv]); sf = np.concatenate([mf, tf + len(mv)])
    print('шарф: %d + %d вершин' % (len(mv), len(tv)), time.time() - t0)
    # волоски шерсти под новым шарфом и насквозь — убрать
    P = G['fur_pts']; n0 = len(P)
    dr = scarf_new(P[:, 0]); dmin = np.min(np.stack([scarf_new(P[:, k]) for k in range(1, P.shape[1])], -1), -1)
    keep = dr > 0.0015
    # волоски, которые упираются в шарф, не убираем, а прижимаем к нему (как мех под шарфом)
    hitm = keep & (dmin < 0.0012); Q = P[hitm].copy(); e = 0.0006; MG = 0.0012
    def grad(q): return nrm(np.stack([scarf_new(q + V(*o)) - scarf_new(q - V(*o)) for o in ((e, 0, 0), (0, e, 0), (0, 0, e))], -1))
    for k in range(1, Q.shape[1]):   # идём от корня: упёрся — ложится вдоль шарфа со своей стороны
        a = Q[:, k - 1]; b = Q[:, k]; m = scarf_new(b) < MG
        if not m.any(): continue
        A, Bq = a[m], b[m]; lo = np.zeros(len(A), F); hi = np.ones(len(A), F)
        for it in range(14):
            mid = (lo + hi) / 2; inside = scarf_new(A + (Bq - A) * mid[:, None]) < MG; hi = np.where(inside, mid, hi); lo = np.where(inside, lo, mid)
        ph = A + (Bq - A) * lo[:, None]; g = grad(ph); rem = (Bq - A) * (1 - lo)[:, None]; dn = np.einsum('ij,ij->i', rem, g); rem -= g * np.minimum(dn, 0)[:, None]
        nb = ph + rem; d2 = scarf_new(nb); nb += grad(nb) * np.maximum(0, MG - d2)[:, None]
        delta = nb - Bq; Q[np.nonzero(m)[0], k:] += delta[:, None, :]
    P = P.copy(); P[hitm] = Q; G['fur_pts'] = P
    print('прижато к шарфу: %d' % hitm.sum())
    for k in [k for k in G if k.startswith('fur_')]: G[k] = G[k][keep]
    print('шерсть: %d -> %d' % (n0, keep.sum()))
    # покрывает ли новый шарф старый (иначе будет голая кожа)
    old = B.scarf_fn(G['skin_v']) < 0.004; bare = old & (scarf_new(G['skin_v']) > 0.004)
    print('голая кожа из-под старого шарфа: %d вершин из %d' % (bare.sum(), old.sum()))
    # дорастить мех там, где лежал старый шарф, а нового нет (тем же генератором, что весь мех)
    old_fn = B.scarf_fn; B.scarf_fn = lambda q: scarf_new(q) + 0.0025
    FF = B.make_fur(G['skin_v'], G['skin_f'], G['skin_n'], G['skin_reg'].astype(int), seed=31); B.scarf_fn = old_fn
    from scipy.spatial import cKDTree
    gap, _ = cKDTree(G['fur_pts'][:, 0]).query(FF['fur_pts'][:, 0], k=1)
    near = scarf_new(FF['fur_pts'][:, 0]) < 0.03   # только у шарфа (остальной мех не трогаем)
    sel = near & (gap > 0.0032) & (scarf_new(FF['fur_pts'][:, 0]) > 0.0015) & (np.min(np.stack([scarf_new(FF['fur_pts'][:, k]) for k in range(5)], -1), -1) > -0.0025)
    for k in FF: G[k] = np.concatenate([G[k], FF[k][sel]]).astype(G[k].dtype)
    print('дорощено волосков: %d' % sel.sum(), time.time() - t0)
    # шерстяные ворсинки на шарфе (область 12)
    rng = np.random.default_rng(12); NF = int(sys.argv[sys.argv.index('--fibers') + 1]) if '--fibers' in sys.argv else 110000
    a, b, c = sv[sf[:, 0]], sv[sf[:, 1]], sv[sf[:, 2]]; area = np.linalg.norm(np.cross(b - a, c - a), axis=-1) * 0.5
    tri = rng.choice(len(sf), NF, p=area / area.sum()); u1, u2 = rng.random(NF, dtype=F), rng.random(NF, dtype=F); sw = u1 + u2 > 1; u1[sw] = 1 - u1[sw]; u2[sw] = 1 - u2[sw]
    R = a[tri] * (1 - u1 - u2)[:, None] + b[tri] * u1[:, None] + c[tri] * u2[:, None]
    e = 0.0006; N = nrm(np.stack([scarf_new(R + V(*d)) - scarf_new(R - V(*d)) for d in ((e, 0, 0), (0, e, 0), (0, 0, e))], -1))
    hk = knit_h(R); vis = (B.field(R + N * 0.002) > 0.0025) & (rng.random(len(R)) < hk ** 2.5)
    R, N, hk = R[vis], N[vis], hk[vis]; n = len(R)
    tg = nrm(np.cross(N, nrm(rng.normal(size=(n, 3)).astype(F))))
    stray = rng.random(n) < 0.06
    L = np.where(stray, 0.0045 + 0.0035 * rng.random(n), 0.0013 + 0.0017 * rng.random(n) ** 1.5).astype(F)
    lean = np.where(stray, 0.8 + 0.35 * rng.random(n), 1.28 + 0.22 * rng.random(n)).astype(F)
    d0 = nrm(N * np.cos(lean)[:, None] + tg * np.sin(lean)[:, None]); side = nrm(np.cross(N, tg)) * ((rng.random(n) - 0.5) * 0.9).astype(F)[:, None]
    tt = np.linspace(0, 1, 5, dtype=F); pts = np.empty((n, 5, 3), F)
    for k, t in enumerate(tt): pts[:, k] = R + (d0 * t + side * t * t + N * (-0.15 * t * t)) * L[:, None]
    pts[:, 0] -= N * 0.0006
    ok = np.min(np.stack([B.field(pts[:, k]) for k in range(5)], -1), -1) > 0.0015
    pts, N, R, hk = pts[ok], N[ok], R[ok], hk[ok]; n = len(R)
    A = np.array([0.07, 0.27, 0.66], F) * ((0.9 + 0.2 * rng.random(n, dtype=F)) * (0.72 + 0.36 * hk))[:, None]
    col = (np.clip(A / 0.95, 0, 1) ** (1 / 0.55)).astype(F)
    fib = dict(fur_nrm=N.astype(F), fur_pts=pts, fur_rad=np.full(n, 0.00024, F), fur_mel=np.zeros(n, F), fur_red=np.zeros(n, F), fur_col=col, fur_reg=np.full(n, 12, np.int8))
    for k, v in fib.items(): G[k] = np.concatenate([G[k], v]).astype(G[k].dtype)
    G.pop('fur_tau', None); G['scarf_v'] = sv; G['scarf_f'] = sf; G['var'] = np.array(['s3'])
    print('ворсинки: %d' % n, time.time() - t0)
    np.savez_compressed('out/geo_s3.npz', **G); print('готово', time.time() - t0)
