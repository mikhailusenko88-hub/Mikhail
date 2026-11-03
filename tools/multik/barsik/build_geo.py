# Барсик для Blender: форма как поле расстояний (SDF) -> сетка кожи, шерсть-кривые с направлением роста, глаза, нос, рот, усы, шарф.
# Запуск: python build_geo.py [--preview]  -> out/geo.npz (+ out/preview.png)
import sys, math, time
import numpy as np

F = np.float32
def V(*a): return np.array(a, dtype=F)
def nrm(v): return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)

# ---------- примитивы (как у Иниго Килеса) ----------
def sd_ell(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1); k1 = np.linalg.norm(q / r, axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
def sd_sph(p, c, r): return np.linalg.norm(p - c, axis=-1) - r
def sd_rcone(p, a, b, r1, r2):  # скруглённый конус между точками a и b
    ba = b - a; l2 = float(ba @ ba); rr = r1 - r2; a2 = l2 - rr * rr; il2 = 1.0 / l2
    pa = p - a; y = pa @ ba; z = y - l2
    x = pa * l2 - y[:, None] * ba[None, :]; x2 = np.einsum('ij,ij->i', x, x)
    y2 = y * y * l2; z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))
def sd_cap(p, a, b, r): return sd_rcone(p, a, b, r, r)
def sd_torus(p, c, R, r, rotx=0.0):
    q = p - c; cs, sn = math.cos(rotx), math.sin(rotx)
    y = q[:, 1] * cs - q[:, 2] * sn; z = q[:, 1] * sn + q[:, 2] * cs
    return np.sqrt((np.sqrt(q[:, 0] ** 2 + y ** 2) - R) ** 2 + z ** 2) - r
def smin(a, b, k):
    if k <= 0: return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25
def smax(a, b, k): return -smin(-a, -b, k)

# ---------- размеры героя (метры; рост с ушами ~1.07) ----------
H = V(0, -0.01, 0.76)                      # центр головы
RE = 0.061                                  # радиус глаза
EYES = [V(s * 0.081, -0.142, 0.768) for s in (-1, 1)]
EAR_B = [V(s * 0.122, 0.012, 0.893) for s in (-1, 1)]
EAR_T = [V(s * 0.19, 0.035, 1.058) for s in (-1, 1)]
SHOULD = [V(s * 0.128, -0.035, 0.50) for s in (-1, 1)]
WRIST = [V(s * 0.19, -0.1, 0.34) for s in (-1, 1)]
PAW = [V(s * 0.196, -0.115, 0.312) for s in (-1, 1)]
HIP = [V(s * 0.088, -0.005, 0.17) for s in (-1, 1)]
FOOT = [V(s * 0.092, -0.08, 0.036) for s in (-1, 1)]
TAIL = [V(0, 0.13, 0.19), V(0.05, 0.25, 0.2), V(0.13, 0.31, 0.3), V(0.17, 0.31, 0.45), V(0.15, 0.27, 0.58), V(0.1, 0.25, 0.64)]
TAIL_R = [0.044, 0.04, 0.037, 0.035, 0.034, 0.035]
NECK = V(0, -0.005, 0.575)
LID_K = 0.1                                 # наклон века: у переносицы выше
LID_N = nrm(V(0, -0.3, 1.0))
VAR = next((a.split('=')[1] for a in sys.argv if a.startswith('--var=')), 'base')   # base | a | o | blink
LID_OFF = RE * 0.82
def lid_n(E): return nrm(V(np.sign(E[0]) * LID_K, -0.3, 1.0))

def ear_sd(p, i, inner=False):
    b, t = EAR_B[i], EAR_T[i]
    if inner: b = b + V(0, -0.022, 0.012); t = t + V(0, -0.012, -0.012)
    q = p.copy(); c = (b + t) * 0.5
    q[:, 1] = c[1] + (q[:, 1] - c[1]) * (1.9 if not inner else 2.6)    # ухо тонкое по толщине
    return sd_rcone(q, b, t, 0.083 if not inner else 0.06, 0.013 if not inner else 0.006) / (1.9 if not inner else 2.6) * 1.4

def parts(p):
    """Возвращает словарь областей -> расстояние (до сглаженного объединения)."""
    d = {}
    # туловище
    t = sd_ell(p, V(0, 0.0, 0.36), V(0.152, 0.138, 0.2))
    t = smin(t, sd_ell(p, V(0, -0.028, 0.295), V(0.148, 0.128, 0.145)), 0.06)
    t = smin(t, sd_ell(p, V(0, -0.02, 0.47), V(0.118, 0.105, 0.095)), 0.06)
    t = smin(t, sd_ell(p, V(0, 0.018, 0.215), V(0.15, 0.13, 0.11)), 0.05)
    t = smin(t, sd_cap(p, V(0, 0.0, 0.5), NECK + V(0, -0.005, 0.06), 0.074), 0.05)
    d['torso'] = t
    # голова
    h = sd_ell(p, H, V(0.205, 0.185, 0.178))
    for s in (-1, 1):
        h = smin(h, sd_ell(p, V(s * 0.105, -0.072, 0.693), V(0.125, 0.105, 0.094)), 0.06)    # скулы/щёки
    h = smin(h, sd_ell(p, V(0, -0.06, 0.825), V(0.15, 0.12, 0.095)), 0.05)                     # лоб
    h = smin(h, sd_cap(p, V(0, -0.165, 0.765), V(0, -0.2, 0.712), 0.024), 0.045)              # переносица
    d['head'] = h
    m = sd_ell(p, V(0, -0.15, 0.686), V(0.076, 0.056, 0.048))                               # мордочка
    for s in (-1, 1): m = smin(m, sd_sph(p, V(s * 0.03, -0.184, 0.676), 0.031), 0.035)       # подушечки с усами
    m = smin(m, sd_ell(p, V(0, -0.152, 0.65), V(0.032, 0.03, 0.022)), 0.035)                  # подбородок
    d['muzzle'] = m
    lid = None
    for E in EYES:
        q = p - E; dd = np.linalg.norm(q, axis=-1)
        sh = np.abs(dd - (RE + 0.0052)) - 0.0034
        cut = q @ lid_n(E) - LID_OFF
        l = smax(sh, -cut, 0.003)
        l = smax(l, q[:, 1] - 0.01, 0.01)       # только передняя половина
        if VAR == 'blink': l = sd_sph(p, E, RE + 0.0045)
        lid = l if lid is None else np.minimum(lid, l)
    d['lid'] = lid
    d['ear'] = np.minimum(ear_sd(p, 0), ear_sd(p, 1))
    a = None
    for i in range(2):
        x = sd_rcone(p, SHOULD[i], WRIST[i], 0.05, 0.039)
        x = smin(x, sd_ell(p, PAW[i], V(0.047, 0.054, 0.044)), 0.03)
        for j in (-1, 0, 1):
            x = smin(x, sd_sph(p, PAW[i] + V(j * 0.02 + (0.004 if i else -0.004), -0.042, -0.018), 0.017), 0.012)
        a = x if a is None else np.minimum(a, x)
    d['arm'] = a
    lg = None
    for i in range(2):
        x = sd_ell(p, HIP[i], V(0.086, 0.1, 0.098))
        x = smin(x, sd_rcone(p, HIP[i] + V(0, -0.02, -0.03), FOOT[i] + V(0, 0.02, 0.025), 0.052, 0.043), 0.04)
        x = smin(x, sd_ell(p, FOOT[i], V(0.062, 0.098, 0.04)), 0.035)
        for j in (-1, 0, 1):
            x = smin(x, sd_sph(p, FOOT[i] + V(j * 0.027, -0.088, -0.006), 0.022), 0.014)
        lg = x if lg is None else np.minimum(lg, x)
    d['leg'] = lg
    tl = None
    for i in range(len(TAIL) - 1):
        x = sd_rcone(p, TAIL[i], TAIL[i + 1], TAIL_R[i], TAIL_R[i + 1])
        tl = x if tl is None else smin(tl, x, 0.02)
    d['tail'] = tl
    return d

REGIONS = ['torso', 'head', 'muzzle', 'lid', 'ear', 'arm', 'leg', 'tail']
MOUTH = {'a': (V(0, -0.197, 0.65), V(0.034, 0.03, 0.026)), 'o': (V(0, -0.197, 0.652), V(0.017, 0.03, 0.019))}.get(VAR)
TONGUE = (V(0, -0.19, 0.641), V(0.019, 0.022, 0.009))
def mouth_cav(p): return sd_ell(p, *MOUTH) if MOUTH is not None else np.full(len(p), 9.0, F)
def field(p, want_parts=False):
    d = parts(p)
    h = smin(d['head'], d['muzzle'], 0.035)
    if VAR != 'blink':
        for E in EYES: h = smax(h, -(np.linalg.norm(p - E, axis=-1) - (RE + 0.003)), 0.012)   # глазницы
    h = smin(h, d['lid'], 0.006)
    if MOUTH is not None:
        h = smax(h, -mouth_cav(p), 0.006); h = np.minimum(h, sd_ell(p, *TONGUE))
    h = smin(h, d['ear'], 0.05)
    inner = np.minimum(ear_sd(p, 0, True), ear_sd(p, 1, True))
    h = smax(h, -inner, 0.008)                                                               # выемка в ухе
    f = smin(d['torso'], h, 0.07)
    f = smin(f, d['arm'], 0.035)
    f = smin(f, d['leg'], 0.05)
    f = smin(f, d['tail'], 0.03)
    if want_parts: return f, d, inner
    return f

# ---------- сетка кожи ----------
def build_skin(h=0.0034):
    from skimage.measure import marching_cubes
    lo, hi = V(-0.33, -0.3, -0.01), V(0.33, 0.37, 1.09)
    n = np.ceil((hi - lo) / h).astype(int) + 1
    xs, ys, zs = [lo[i] + np.arange(n[i], dtype=F) * h for i in range(3)]
    vol = np.empty((n[0], n[1], n[2]), dtype=F)
    YY, ZZ = np.meshgrid(ys, zs, indexing='ij')
    for i, x in enumerate(xs):   # послойно — экономия памяти
        p = np.stack([np.full(YY.size, x, F), YY.ravel(), ZZ.ravel()], -1)
        vol[i] = field(p).reshape(YY.shape)
    v, f, _, _ = marching_cubes(vol, 0.0, spacing=(h, h, h))
    v = (v + lo).astype(F)
    global VOL; VOL = (vol.astype(np.float16), lo, np.array([h], F))
    return v, f.astype(np.int32)

def grad(p, e=0.0008):
    g = np.zeros_like(p)
    for i in range(3):
        dp = np.zeros(3, F); dp[i] = e
        g[:, i] = field(p + dp) - field(p - dp)
    return nrm(g)

# ---------- немного шума для полосок ----------
RNG = np.random.default_rng(7)
_W = RNG.normal(size=(12, 3)).astype(F) * 6; _P = RNG.uniform(0, 6.28, 12).astype(F)
def wob(p, s=1.0):
    return (np.sin(p @ (_W.T * s) + _P).sum(-1) / 12 * 2.2).astype(F)

def colors(p, reg, nor):
    """Меланин и краснота для каждой точки (как у Principled Hair в Blender) + маска «кремовых» мест."""
    N = len(p); mel = np.full(N, 0.2, F); red = np.full(N, 1.0, F)
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    stripe = np.zeros(N, F)
    w = wob(p, 1.0) * 0.6
    # туловище и бока: кольца поперёк тела, сверху шире, к животу сходят на нет
    b = (reg == 0)
    band = np.sin((z * 21 + w + np.abs(x) * 3) * 1.0) ; stripe = np.where(b, np.clip((band - 0.25) * 2.2, 0, 1) * np.clip((y + 0.04) * 9 + 0.6, 0, 1), stripe)
    # голова: «М» на лбу (вертикальные полоски) и две полоски на щеках
    hd = (reg == 1) | (reg == 2)
    fore = np.clip((z - 0.8) * 14, 0, 1) * np.clip(-(y + 0.0) * 6 + 0.3, 0, 1)
    vert = np.clip((np.cos(x * 62 + w * 0.6) - 0.35) * 2.0, 0, 1) * fore
    top = np.clip((np.sin((y * 26 + w * 0.4)) - 0.2) * 1.8, 0, 1) * np.clip((z - 0.86) * 12, 0, 1) * np.clip(y * 8 + 0.6, 0, 1)
    cheek = np.clip((np.sin(z * 70 + w) - 0.55) * 2.5, 0, 1) * np.clip((np.abs(x) - 0.17) * 20, 0, 1) * np.clip((0.76 - z) * 20, 0, 1) * np.clip((z - 0.63) * 20, 0, 1)
    stripe = np.where(hd, np.maximum(np.maximum(vert, top), cheek), stripe)
    # лапы и хвост: кольца
    li = (reg == 5) | (reg == 6)
    stripe = np.where(li, np.clip((np.sin(z * 34 + w) - 0.3) * 2.2, 0, 1) * np.clip((z - 0.06) * 10, 0, 1), stripe)
    tl = reg == 7
    stripe = np.where(tl, np.clip((np.sin((y * 18 + z * 18) + w) - 0.1) * 2.2, 0, 1), stripe)
    # кремовые места: грудка+живот, мордочка+подбородок, кончики лап, кончик хвоста
    cream = np.zeros(N, F)
    q = (p - V(0, -0.11, 0.37)) / V(0.105, 0.09, 0.21); cream = np.maximum(cream, np.clip((1.15 - np.linalg.norm(q, axis=-1)) * 4, 0, 1) * (reg == 0))
    q = (p - V(0, -0.175, 0.665)) / V(0.085, 0.07, 0.06); cream = np.maximum(cream, np.clip((1.2 - np.linalg.norm(q, axis=-1)) * 4, 0, 1) * ((reg == 1) | (reg == 2)))
    cream = np.maximum(cream, np.clip((0.36 - z) * 40, 0, 1) * (reg == 5))      # кисти лап
    cream = np.maximum(cream, np.clip((0.07 - z) * 40, 0, 1) * (reg == 6))      # стопы
    stripe *= (1 - cream)
    mel = mel + stripe * 0.27; red = red - stripe * 0.04
    mel = mel * (1 - cream) + 0.05 * cream; red = red * (1 - cream) + 0.5 * cream
    # внутри уха — светлые волоски
    mel = np.where(reg == 8, 0.03, mel); red = np.where(reg == 8, 0.3, red)
    return mel, red, stripe, cream

def mel_rgb(mel):
    xs = np.array([0.03, 0.05, 0.2, 0.47, 0.8]); cs = np.array([[0.9, 0.85, 0.8], [0.86, 0.6, 0.36], [0.64, 0.19, 0.022], [0.3, 0.065, 0.012], [0.1, 0.03, 0.01]])
    return np.stack([np.interp(mel, xs, cs[:, i]) for i in range(3)], -1)

def region_of(p):
    f, d, inner = field(p, True)
    names = ['torso', 'head', 'muzzle', 'lid', 'ear', 'arm', 'leg', 'tail']
    D = np.stack([d[k] for k in names], -1)
    reg = np.argmin(D, -1)
    # 0 torso,1 head,2 muzzle,3 lid,4 ear,5 arm,6 leg,7 tail ; 8 — внутренняя часть уха (розовая)
    reg = np.where(np.abs(inner) < 0.0065, 8, reg)
    if MOUTH is not None:
        reg = np.where(np.abs(mouth_cav(p)) < 0.004, 10, reg); reg = np.where(sd_ell(p, *TONGUE) < 0.002, 11, reg)
    return reg.astype(np.int32)

# ---------- шерсть ----------
def make_fur(v, f, nor, reg, total=760000, P=5, seed=3):
    rng = np.random.default_rng(seed)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=-1) * 0.5
    freg = reg[f[:, 0]]
    dens = np.array([1.0, 1.15, 0.0, 1.6, 0.85, 1.0, 1.0, 1.1, 0.2, 0, 0, 0], F)[freg]   # на мордочке и внутри уха — нет
    w = area * dens; w /= w.sum()
    tri = rng.choice(len(f), size=total, p=w)
    u1, u2 = rng.random(total, dtype=F), rng.random(total, dtype=F); sw = u1 + u2 > 1; u1[sw] = 1 - u1[sw]; u2[sw] = 1 - u2[sw]; w0 = 1 - u1 - u2
    fi = f[tri]
    R = v[fi[:, 0]] * w0[:, None] + v[fi[:, 1]] * u1[:, None] + v[fi[:, 2]] * u2[:, None]
    N = nrm(nor[fi[:, 0]] * w0[:, None] + nor[fi[:, 1]] * u1[:, None] + nor[fi[:, 2]] * u2[:, None])
    rg = freg[tri]
    # точнее определить область для самой точки (мордочка рядом с головой)
    rg = region_of(R)
    # убрать с мордочки, из глаз и с внутренней части уха
    keep = (rg != 2) & (rg != 10) & (rg != 11)
    if VAR != 'blink':
        for E in EYES: keep &= np.linalg.norm(R - E, axis=-1) > RE + 0.0045
    keep &= scarf_fn(R) > 0.004   # под шарфом шерсти нет
    R, N, rg = R[keep], N[keep], rg[keep]
    n = len(R)
    # откуда растёт шерсть
    src = np.zeros((n, 3), F)
    nose = V(0, -0.225, 0.705)
    src[(rg == 1) | (rg == 3)] = nose
    src[rg == 4] = nose + V(0, 0.1, -0.05)
    src[rg == 0] = NECK + V(0, 0, 0.03)
    for i, s in enumerate((-1, 1)):
        side = (R[:, 0] * s) > 0
        src[(rg == 5) & side] = SHOULD[i]; src[(rg == 6) & side] = HIP[i] + V(0, 0, 0.06)
    src[rg == 7] = TAIL[0] - V(0, 0.05, 0)
    flow = R - src; flow = nrm(flow)
    for i, s in enumerate((-1, 1)):
        side = (R[:, 0] * s) > 0
        flow[(rg == 5) & side] = nrm(WRIST[i] - SHOULD[i]) + 0 * flow[(rg == 5) & side]
        flow[(rg == 6) & side] = nrm(FOOT[i] - HIP[i] + V(0, -0.03, 0)) + 0 * flow[(rg == 6) & side]
    tl = np.nonzero(rg == 7)[0]
    if len(tl):
        segs = np.array([TAIL[j + 1] - TAIL[j] for j in range(len(TAIL) - 1)]); mids = np.array([(TAIL[j + 1] + TAIL[j]) / 2 for j in range(len(TAIL) - 1)])
        near = np.argmin(np.linalg.norm(R[tl, None, :] - mids[None], axis=-1), -1); flow[tl] = nrm(segs[near])
    flow[rg == 8] = nrm(V(0, 0, 1) + 0 * flow[rg == 8])
    down = V(0, 0, -1)
    flow = flow + down * np.where(rg == 0, 0.35, np.where(rg == 7, 0.0, 0.2))[:, None]
    flow = flow - N * np.einsum('ij,ij->i', flow, N)[:, None]; flow = nrm(flow)
    # длина и наклон по местам
    L = np.select([rg == 0, rg == 1, rg == 3, rg == 4, rg == 5, rg == 6, rg == 7, rg == 8], [0.021, 0.0155, 0.0075, 0.009, 0.016, 0.017, 0.03, 0.026], 0.015).astype(F)
    lean = np.select([rg == 1, rg == 3, rg == 4, rg == 8], [1.2, 1.35, 1.15, 0.5], 1.18).astype(F)   # радианы от нормали
    x, y, z = R[:, 0], R[:, 1], R[:, 2]
    # лицо спереди: короче и плотнее прижато
    hd = rg == 1
    front = np.clip((-(y - H[1]) / 0.18 - 0.45) * 2.2, 0, 1) * np.clip((0.86 - z) * 8, 0, 1)
    L = np.where(hd, L * (1 - 0.6 * front), L); lean = np.where(hd, lean + 0.2 * front, lean)
    # бакенбарды по бокам щёк, жабо на грудке, кисточки на ушах
    ruff = hd & (np.abs(x) > 0.15) & (z < 0.75) & (z > 0.6)
    L = np.where(ruff, L * (1 + np.clip((np.abs(x) - 0.15) * 18, 0, 0.9)), L); lean = np.where(ruff, lean - 0.25, lean)
    chest = (rg == 0) & (y < -0.06) & (z > 0.43)
    L = np.where(chest, L * 1.3, L)
    tip_ear = (rg == 4) & (z > 1.0)
    L = np.where(tip_ear, L * (1 + (z - 1.0) * 45), L); lean = np.where(tip_ear, 0.5, lean)
    tailtip = (rg == 7) & (z > 0.52)
    L = np.where(tailtip, L * 1.25, L)
    L *= (0.82 + 0.36 * rng.random(n, dtype=F))
    guard = rng.random(n) < 0.12; L = np.where(guard & ~(rg == 3), L * 1.35, L)
    jit = nrm(rng.normal(size=(n, 3)).astype(F)); jit -= N * np.einsum('ij,ij->i', jit, N)[:, None]
    flow = nrm(flow + jit * 0.28)
    d0 = nrm(N * np.cos(lean)[:, None] + flow * np.sin(lean)[:, None])
    # пряди: кончики соседних волосков тянутся к общему центру
    import os
    CM = os.environ.get('CLUMP', 'surf')
    if CM == 'lattice':
        CELL = 0.012
        key = np.floor((R + V(0.0057, 0.0031, 0.0043)) / CELL).astype(np.int64); kid = (key[:, 0] * 73856093) ^ (key[:, 1] * 19349663) ^ (key[:, 2] * 83492791)
        _, inv = np.unique(kid, return_inverse=True)
    else:   # пряди — по случайным центрам на коже (ячейки Вороного), без «колец» от кубической сетки
        from scipy.spatial import cKDTree
        nc = max(1, n // 42); ci = rng.choice(n, nc, replace=False); _, inv = cKDTree(R[ci]).query(R, k=1)
        if CM == 'none': inv = np.arange(n)
    cnt = np.bincount(inv); ctr = np.stack([np.bincount(inv, R[:, i]) for i in range(3)], -1) / cnt[:, None]
    pull = ctr[inv] - R; pull -= N * np.einsum('ij,ij->i', pull, N)[:, None]
    clump = np.where(rg == 3, 0.0, 0.3).astype(F)
    t = np.linspace(0, 1, P, dtype=F)
    pts = np.empty((n, P, 3), F)
    curl = nrm(np.cross(N, flow)) * ((rng.random(n, dtype=F) - 0.5) * 0.25)[:, None]
    for k, tt in enumerate(t):
        bend = (flow * 0.35 + down * 0.12 + curl) * (tt * tt)
        pts[:, k] = R + (d0 * tt + bend)[...] * L[:, None] + pull * (clump * tt ** 1.6)[:, None]
    pts[:, 0] -= N * 0.0015  # корень чуть в коже
    mel, red, stripe, cream = colors(R, rg, N)
    mel = mel * (0.94 + 0.12 * rng.random(n, dtype=F)); mel = np.where(guard, mel * 0.92, mel)
    rad = np.where(rg == 3, 0.0006, 0.00085).astype(F)
    col = mel_rgb(mel)
    return dict(fur_nrm=N.astype(F), fur_pts=pts, fur_rad=rad, fur_mel=mel.astype(F), fur_red=red.astype(F), fur_col=col.astype(F), fur_reg=rg.astype(np.int8))

# ---------- поверхность по лучу (для рта и усов) ----------
def hit(o, dirn, tmax=0.4):
    o = np.atleast_2d(o).astype(F); dirn = nrm(np.atleast_2d(dirn).astype(F)); t = np.zeros(len(o), F)
    for _ in range(80):
        d = field(o + dirn * t[:, None]); t = np.minimum(t + np.maximum(d, 0.0004) * 0.9, tmax)
        if np.all(np.abs(d) < 0.0005): break
    return o + dirn * t[:, None]

def creases():   # линия сомкнутых век (дуга чуть вниз)
    out = []
    for E in EYES:
        s = np.sign(E[0]); xs = np.linspace(-0.85, 0.85, 12) * RE
        zs = E[2] - 0.12 * RE - 0.22 * RE * (1 - (xs / (0.85 * RE)) ** 2)
        dirn = np.tile(nrm(V(-0.16 * s, 1.0, 0.0)), (12, 1))
        o = (np.stack([E[0] + xs, np.full(12, E[1]), zs], -1) - dirn * 0.15).astype(F)
        out.append(hit(o, dirn, 0.3) - dirn * 0.0015)
    return out

def mouth_lines():
    # «ω»: от носа вниз короткая черта, потом две дуги в стороны
    lines = []
    phil = [V(0, -0.4, 0.693 - 0.022 * i / 6) for i in range(7)]
    lines.append(hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1))))
    for s in (-1, 1):
        ang = np.linspace(0, math.pi, 12)
        xs = s * (0.0185 - 0.0185 * np.cos(ang)); zs = 0.671 - 0.011 * np.sin(ang)
        arc = np.stack([xs, np.full(12, -0.4, F), zs], -1).astype(F)
        lines.append(hit(arc, np.tile(V(0, 1, 0), (12, 1))))
    return lines[:1] if MOUTH is not None else lines

def whiskers():
    out = []
    for s in (-1, 1):
        for j, (dz, ang) in enumerate([(0.012, 0.18), (0.0, 0.0), (-0.012, -0.16), (0.006, 0.09)]):
            o = V(s * (0.03 + 0.006 * j), -0.4, 0.678 + dz)
            r0 = hit(o, V(0, 1, 0))[0] + V(0, 0.002, 0)
            dirn = nrm(V(s * 1.0, -0.42, ang))
            pts = []
            for k in range(8):
                tt = k / 7
                pts.append(r0 + dirn * 0.17 * tt + V(0, 0.02 * tt * tt, -0.03 * tt * tt))
            out.append(np.array(pts, F))
    return out

def small_mesh(fn, lo, hi, h=0.0012):
    from skimage.measure import marching_cubes
    lo, hi = V(*lo), V(*hi); n = np.ceil((hi - lo) / h).astype(int) + 1
    g = np.stack(np.meshgrid(*[lo[i] + np.arange(n[i], dtype=F) * h for i in range(3)], indexing='ij'), -1).reshape(-1, 3)
    vol = fn(g).reshape(n[0], n[1], n[2])
    v, f, nn, _ = marching_cubes(vol, 0.0, spacing=(h, h, h))
    return (v + lo).astype(F), f.astype(np.int32)

def nose_fn(p):
    c = V(0, -0.214, 0.704)
    d = sd_ell(p, c, V(0.024, 0.016, 0.014))
    for s in (-1, 1): d = smin(d, sd_ell(p, c + V(s * 0.012, 0.0, 0.007), V(0.014, 0.012, 0.01)), 0.012)
    d = smin(d, sd_ell(p, c + V(0, -0.002, -0.009), V(0.008, 0.01, 0.009)), 0.01)
    for s in (-1, 1): d = smax(d, -sd_ell(p, c + V(s * 0.0105, -0.016, -0.002), V(0.005, 0.006, 0.0032)), 0.003)   # ноздри
    return d

def scarf_fn(p):
    d = sd_torus(p, NECK + V(0, -0.006, 0.004), 0.097, 0.037, rotx=0.17)
    k = V(0.062, -0.112, 0.55)
    d = smin(d, sd_ell(p, k, V(0.036, 0.03, 0.034)), 0.02)
    for e, w in [(V(0.085, -0.115, 0.4), 0.0), (V(0.035, -0.128, 0.42), 0.0)]:
        q = p.copy(); c = (k + e) / 2
        d = smin(d, sd_cap(q, k + V(0, -0.005, -0.02), e, 0.022) , 0.015)
    # сплющить концы: вырезаем толщину спереди-сзади
    tails = sd_cap(p, k, V(0.06, -0.12, 0.4), 0.06)
    flat = np.abs(p[:, 1] - (-0.12 + (p[:, 2] - 0.4) * 0.15)) - 0.011
    d = np.where(tails < 0, np.maximum(d, flat - 0.0) * 0 + smax(d, flat, 0.006), d)
    return d

# ---------- быстрый предпросмотр формы (луч по полю) ----------
def preview(path, W=420, Hh=560, eye=(0.55, -1.55, 0.8), look=(0, -0.02, 0.6), fov=34, fn=None, eyes=True):
    from PIL import Image
    fn0 = fn; fn = fn or field
    eye = V(*eye); look = V(*look); fw = nrm(look - eye); rt = nrm(np.cross(fw, V(0, 0, 1))); up = np.cross(rt, fw)
    j, i = np.meshgrid(np.arange(Hh), np.arange(W), indexing='ij')
    s = math.tan(math.radians(fov / 2))
    dirs = nrm(fw + rt * ((i - W / 2) / (Hh / 2) * s)[..., None] + up * (-(j - Hh / 2) / (Hh / 2) * s)[..., None]).reshape(-1, 3).astype(F)
    if fn is field and eyes:
        base_fn = fn
        def fn(q):
            d = base_fn(q)
            for E in EYES: d = np.minimum(d, np.linalg.norm(q - E, axis=-1) - RE)
            return d
    o = np.tile(eye, (len(dirs), 1)); t = np.full(len(dirs), 0.8, F); alive = np.ones(len(dirs), bool); hitm = np.zeros(len(dirs), bool)
    for _ in range(110):
        idx = np.nonzero(alive)[0]
        if not len(idx): break
        d = fn(o[idx] + dirs[idx] * t[idx, None]); t[idx] += d * 0.95
        hitm[idx[d < 0.0007]] = True; alive[idx[(d < 0.0007) | (t[idx] > 3.5)]] = False
    P = o + dirs * t[:, None]; img = np.zeros((len(dirs), 3), F) + V(0.82, 0.88, 0.9)
    hi = np.nonzero(hitm)[0]
    if len(hi):
        Pp = P[hi]; g = np.zeros_like(Pp); e = 0.0008
        for k in range(3):
            dp = np.zeros(3, F); dp[k] = e; g[:, k] = fn(Pp + dp) - fn(Pp - dp)
        nn = nrm(g); Ld = nrm(V(-0.5, -0.7, 0.8))
        dif = np.clip(nn @ Ld, 0, 1); amb = 0.35 + 0.25 * nn[:, 2]
        ao = np.clip(fn(Pp + nn * 0.02) / 0.02, 0, 1) * 0.5 + 0.5
        reg = region_of(Pp) if fn0 is None else np.zeros(len(Pp), int)
        mel, red, stripe, cream = colors(Pp, reg, nn)
        base = np.stack([0.95 - mel * 0.6, 0.62 - mel * 0.7, 0.3 - mel * 0.5], -1); base = np.clip(base, 0, 1)
        base = np.where((reg == 8)[:, None], V(0.95, 0.6, 0.62), base)
        base = np.where((reg == 3)[:, None], base * 0.9, base)
        for E in EYES:
            q = Pp - E; on = np.abs(np.linalg.norm(q, axis=-1) - RE) < 0.0015
            fwd = nrm(V(np.sign(E[0]) * 0.18, -1, 0.02)); c = nrm(q) @ fwd
            ec = np.where((c > 0.93)[:, None], V(0.03, 0.02, 0.02), np.where((c > 0.72)[:, None], V(0.25, 0.6, 0.22), V(0.97, 0.97, 0.96)))
            base = np.where(on[:, None], ec, base)
        img[hi] = base * (dif[:, None] * 0.8 + amb[:, None]) * ao[:, None]
    # глаза поверх (сферы)
    Image.fromarray((np.clip(img.reshape(Hh, W, 3), 0, 1) ** (1 / 1.6) * 255).astype(np.uint8)).save(path)

if __name__ == '__main__':
    t0 = time.time()
    if '--preview' in sys.argv:
        preview('out/prev_34.png', eye=(0.75, -2.1, 0.75), look=(0, -0.02, 0.52)); preview('out/prev_face.png', eye=(0.3, -1.0, 0.78), look=(0, -0.08, 0.74), fov=30); preview('out/prev_side.png', eye=(2.1, -0.3, 0.6), look=(0, 0, 0.52))
        print('preview', time.time() - t0); sys.exit()
    v, f = build_skin(); print('skin', len(v), len(f), time.time() - t0)
    nor = grad(v); reg = region_of(v)
    mel, red, stripe, cream = colors(v, reg, nor)
    fur = make_fur(v, f, nor, reg); print('fur', len(fur['fur_pts']), time.time() - t0)
    nv, nf = small_mesh(nose_fn, (-0.05, -0.25, 0.67), (0.05, -0.18, 0.74))
    sv, sf = small_mesh(scarf_fn, (-0.15, -0.17, 0.36), (0.16, 0.12, 0.66), h=0.0022)
    ml = mouth_lines(); wh = whiskers()
    np.savez_compressed('out/geo_%s.npz' % VAR, skin_v=v, skin_f=f, skin_n=nor, skin_reg=reg.astype(np.int8), skin_mel=mel, skin_red=red, skin_cream=cream,
                        nose_v=nv, nose_f=nf, scarf_v=sv, scarf_f=sf,
                        mouth=np.array([np.pad(m, ((0, 12 - len(m)), (0, 0)), mode='edge') for m in ml]), whisk=np.array(wh),
                        creases=np.array(creases() if VAR == 'blink' else np.zeros((0, 12, 3), F)), eyes=np.array(EYES), re=np.array([RE]), lid_n=LID_N, lid_ns=np.array([lid_n(E) for E in EYES]), var=np.array([VAR]), lid_off=np.array([LID_OFF]), skin_col=mel_rgb(mel).astype(F), vol=VOL[0], vol_lo=VOL[1], vol_h=VOL[2], **fur)
    print('done', time.time() - t0)
