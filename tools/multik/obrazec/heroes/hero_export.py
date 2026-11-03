# Выгрузка героя для движка: кожа по частям (тело, голова + 3 варианта лица, лапы, хвост), на вершинах — область, цвет шерсти,
# «можно ли расти шерсти»; нос, аксессуары, рот, веки, усы; правила роста шерсти (шерсть выращивает сам телефон).
# python hero_export.py barsik|pik|ron  -> /home/claude/obrazec/data4/<имя>.json + <имя>_*.wasm
# v6: лапы с пальцами — кисти и ступни (отдельная кожа 'feet') строятся мелкой сеткой; 9 — пальцы (короткая шерсть), 12 — подушечки
import sys, os, json, time, importlib, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *
from skimage.measure import marching_cubes
OUT = os.environ.get('OUT', '/home/claude/obrazec/data4'); os.makedirs(OUT, exist_ok=True)
T0 = time.time()
def log(*a): print('[%5.1fs]' % (time.time() - T0), *a, flush=True)
def ax(p): p = np.asarray(p, np.float32); return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1).astype(np.float32)

def mc(fn, lo, hi, h):
    lo, hi = V(*lo), V(*hi); n = np.ceil((hi - lo) / h).astype(int) + 1
    xs, ys, zs = [lo[i] + np.arange(n[i], dtype=F) * h for i in range(3)]
    vol = np.empty((n[0], n[1], n[2]), F); YY, ZZ = np.meshgrid(ys, zs, indexing='ij')
    for i, x in enumerate(xs):
        p = np.stack([np.full(YY.size, x, F), YY.ravel(), ZZ.ravel()], -1); vol[i] = fn(p).reshape(YY.shape)
    v, f, _, _ = marching_cubes(vol, 0.0, spacing=(h, h, h))
    return (v + lo).astype(F), f.astype(np.int32)
def grad(fn, p, e=0.0008):
    g = np.zeros_like(p)
    for i in range(3): dp = np.zeros(3, F); dp[i] = e; g[:, i] = fn(p + dp) - fn(p - dp)
    return nrm(g)

name = sys.argv[1]
if name == 'barsik':
    sys.path.insert(0, '/home/claude/bt'); sys.argv = [sys.argv[0]]
    import build_geo as B
    class Barsik(Hero):
        NAME = 'barsik'; H = B.H; RE = B.RE; EYES = B.EYES; NOSE_C = V(0, -0.214, 0.704); NECK = B.NECK
        IRIS = [(0.06, 0.2, 0.05), (0.16, 0.42, 0.08), (0.35, 0.62, 0.12)]
        def set_var(self, v): self.VAR = v; B.VAR = v; B.MOUTH = {'a': (V(0, -0.197, 0.65), V(0.034, 0.03, 0.026)), 'o': (V(0, -0.197, 0.652), V(0.017, 0.03, 0.019))}.get(v); self.MOUTH = B.MOUTH
        def parts(self, p): return B.parts(p)
        def region_of(self, p): return B.region_of(p)
        def colors(self, p, reg, nor):
            mel, red, stripe, cream = B.colors(p, reg, nor); col = B.mel_rgb(mel).astype(F); skin = col * 0.9
            skin[reg == 2] = (0.9, 0.76, 0.6); skin[reg == 8] = (0.62, 0.3, 0.32); skin[reg == 10] = (0.16, 0.03, 0.03); skin[reg == 11] = (0.72, 0.28, 0.32)
            return skin.astype(F), col
        def fur_ok(self, p, reg):
            ok = (reg != 2) & (reg != 10) & (reg != 11)
            if self.VAR != 'blink':
                for E in self.EYES: ok &= np.linalg.norm(p - E, axis=-1) > self.RE + 0.0045
            return ok & (B.scarf_fn(p) > 0.004)
    # v6: лапы с пальцами (передние — с розовыми подушечками), кисти и ступни — мелкой сеткой
    PAW_F = nrm(V(0, -0.042, -0.018))
    def front_paw(p, i): return toe_paw(p, B.PAW[i], (0.046, 0.052, 0.042), PAW_F, tr=0.0168, tk=0.006, fk=0.7, dk=0.3)
    def hind_paw(p, i): return toe_paw(p, B.FOOT[i], (0.061, 0.096, 0.039), V(0, -1, 0), tr=0.021, tk=0.007, pads=False, fk=0.72, dk=0.28)
    def new_arm(p, i):
        x = sd_rcone(p, B.SHOULD[i], B.WRIST[i], 0.05, 0.039); x = smin(x, front_paw(p, i)[0], 0.026)
        return smin(x, sd_sph(p, B.SHOULD[i] + V(0, 0.005, 0.005), 0.056), 0.03)
    def new_leg(p, i):
        x = sd_ell(p, B.HIP[i], V(0.086, 0.1, 0.098))
        x = smin(x, sd_rcone(p, B.HIP[i] + V(0, -0.02, -0.03), B.FOOT[i] + V(0, 0.02, 0.025), 0.052, 0.043), 0.04)
        return smin(x, hind_paw(p, i)[0], 0.035)
    _parts0 = B.parts
    def _parts2(p):
        d = _parts0(p); d['arm'] = np.minimum(new_arm(p, 0), new_arm(p, 1)); d['leg'] = np.minimum(new_leg(p, 0), new_leg(p, 1)); return d
    B.parts = _parts2
    def extra_regions(p, reg):
        limb = (reg == 5) | (reg == 6); toes = np.full(len(p), 9.0, F); pads = np.full(len(p), 9.0, F)
        for i in range(2):     # вся кисть/ступня — короткая шерсть (9), чтобы пальцы читались
            x, t, pd = front_paw(p, i); toes = np.minimum(toes, x); pads = np.minimum(pads, pd)
            x, t, _ = hind_paw(p, i); toes = np.minimum(toes, x)
        reg = np.where(limb & (toes < 0.004), 9, reg); return np.where(limb & (pads < 0.0012), 12, reg)
    _colors0 = Barsik.colors
    def _colors2(self, p, reg0, nor):
        reg = np.where((reg0 == 9) | (reg0 == 12), np.where(p[:, 2] > 0.2, 5, 6), reg0)
        skin, col = _colors0(self, p, reg, nor); skin[reg0 == 12] = (0.8, 0.42, 0.47); return skin, col
    Barsik.colors = _colors2
    Barsik.region_of = lambda self, p: extra_regions(p, B.region_of(p)).astype(np.int32)
    _fok0 = Barsik.fur_ok
    Barsik.fur_ok = lambda self, p, reg: _fok0(self, p, reg) & (reg != 12)
    HERO = Barsik(); A = np.load('/home/claude/bt/out/anim.npz')
    import anim_geo_fns as AG  # те же функции частей, что в anim_geo.py
    FN = AG.make_fn(B)
    Z0 = 0.085; OV = 0.004
    def fn_body_full(p): d = B.parts(p); return smin(d['torso'], d['leg'], 0.05)
    FN['body'] = lambda p: np.maximum(fn_body_full(p), Z0 - p[:, 2]); FN['feet'] = lambda p: np.maximum(fn_body_full(p), p[:, 2] - (Z0 + OV))
    FN['armL'] = lambda p: new_arm(p, 0); FN['armR'] = lambda p: new_arm(p, 1)
    NFN = dict(FN, body=fn_body_full, feet=fn_body_full)
    BOXB = {'body': ((-0.24, -0.25, 0.06), (0.24, 0.2, 0.68)), 'feet': ((-0.18, -0.22, -0.02), (0.18, 0.08, 0.095)),
            'armL': ((-0.28, -0.2, 0.22), (-0.04, 0.08, 0.58)), 'armR': ((0.04, -0.2, 0.22), (0.28, 0.08, 0.58))}
    STEPB = {'body': 0.0034, 'feet': 0.002, 'armL': 0.002, 'armR': 0.002}
    SKINS = {}
    HERO.set_var('base')
    for nm in ['body', 'feet', 'armL', 'armR']:
        v, f = mc(FN[nm], *BOXB[nm], h=STEPB[nm]); n = grad(NFN[nm], v); reg = HERO.region_of(v); SKINS[nm] = (v, f, n, reg); log(nm, len(v), 'пальцы', int((reg == 9).sum()), 'подушечки', int((reg == 12).sum()))
    SKINS['tail'] = (A['tail_v'], A['tail_f'], A['tail_n'], A['tail_reg'])
    SKINS['head'] = (A['head_v'], A['head_f'], A['head_n'], A['head_reg'])
    for var in ['a', 'o', 'blink']: SKINS['head_' + var] = (A['head_%s_v' % var], A['head_%s_f' % var], A['head_%s_n' % var], A['head_%s_reg' % var])
    SMALL = {'nose': (A['nose_v'], A['nose_f'], 'nose', (0.78, 0.36, 0.42)), 'scarf': (A['scarf_v'], A['scarf_f'], 'scarf', (0.015, 0.09, 0.45))}
    LINES = {'mouth_base': A['mouth_base'], 'mouth_open': A['mouth_open'], 'creases': A['creases'], 'whisk': A['whisk']}
    PIV = {k: A['piv'][i] for i, k in enumerate(['head', 'armL', 'armR', 'tail'])}
    WHISK = {'r': [0.0011, 0.00025], 'col': [0.92, 0.9, 0.86]}; NOSE = {'col': [0.78, 0.36, 0.42], 'wet': False}
    FUR = {'K': 0.42e6, 'dens': [1.0, 1.15, 0.0, 1.6, 0.85, 1.0, 1.0, 1.1, 0.2, 1.1], 'L': [0.021, 0.0155, 0.015, 0.0075, 0.009, 0.016, 0.017, 0.03, 0.026, 0.0072],
           'lean': [1.18, 1.2, 1.18, 1.35, 1.15, 1.18, 1.18, 1.18, 0.5, 1.3], 'down': [0.35, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.0, 0.2, 0.1], 'rad': 0.00085, 'radLid': 0.0006,
           'cell': 0.012, 'clump': 0.3, 'front': [float(B.H[1]), 0.18, 0.45, 2.2, 0.86, 8.0, 0.6, 0.2], 'ruff': [0.15, 0.6, 0.75, 18.0, 0.9, -0.25],
           'chest': [-0.06, 0.43, 1.3], 'earTip': [1.0, 45.0], 'tailTip': [0.52, 1.25]}
    SRC = {'nose': [0, -0.225, 0.705], 'earOff': [0, 0.1, -0.05], 'neck': (B.NECK + V(0, 0, 0.03)).tolist(), 'should': [s.tolist() for s in B.SHOULD], 'wrist': [s.tolist() for s in B.WRIST],
           'hip': [(h + V(0, 0, 0.06)).tolist() for h in B.HIP], 'foot': [f.tolist() for f in B.FOOT], 'tail': [t.tolist() for t in B.TAIL]}
else:
    M = importlib.import_module('hero_' + os.environ.get('MOD', name)); HERO = M.HERO; Hh = HERO
    hstep = {'pik': 0.0024, 'ron': 0.003}[name]; STEP = getattr(Hh, 'STEP', {})
    def fn_head(p): return smin(Hh.head_sd(p), sd_cap(p, *Hh.NECK_PLUG), 0.03)
    def fn_body_full(p): d = Hh.parts(p); return smin(d['torso'], d['leg'], 0.05)
    Z0 = getattr(Hh, 'ANKLE', None); OV = 0.004
    if Z0 is None: fn_body = fn_body_full
    else:
        def fn_body(p): return np.maximum(fn_body_full(p), Z0 - p[:, 2])
        def fn_feet(p): return np.maximum(fn_body_full(p), p[:, 2] - (Z0 + OV))
    FN = {'head': fn_head, 'body': fn_body, 'armL': lambda p: Hh.arm_sd(p, 0), 'armR': lambda p: Hh.arm_sd(p, 1), 'tail': lambda p: Hh.parts(p)['tail']}
    NFN = dict(FN, body=fn_body_full)
    if Z0 is not None: FN['feet'] = fn_feet; NFN['feet'] = fn_body_full
    SKINS = {}
    Hh.set_var('base')
    for nm in [k for k in ['body', 'feet', 'armL', 'armR', 'tail', 'head'] if k in FN]:
        v, f = mc(FN[nm], *Hh.BOX[nm], h=STEP.get(nm, hstep)); n = grad(NFN[nm], v); reg = Hh.region_of(v); SKINS[nm] = (v, f, n, reg); log(nm, len(v))
    for var in ['a', 'o', 'blink']:
        Hh.set_var(var); v, f = mc(fn_head, *Hh.BOX['head'], h=STEP.get('head', hstep)); n = grad(fn_head, v); reg = Hh.region_of(v); SKINS['head_' + var] = (v, f, n, reg); log('голова', var, len(v))
    Hh.set_var('base')
    SMALL = {}
    nv, nf = Hh.small_mesh(Hh.nose_fn, Hh.NOSE_C - V(0.045, 0.035, 0.035), Hh.NOSE_C + V(0.045, 0.035, 0.035), h=0.0008 if name == 'pik' else 0.0011)
    SMALL['nose'] = (nv, nf, 'nose', getattr(Hh, 'NOSE_COL', (0.85, 0.47, 0.52)))
    accs = getattr(Hh, 'ACCS', None) or [dict(Hh.ACC, fn='acc_fn')]
    for a in accs:
        av, af = Hh.small_mesh(getattr(Hh, a['fn']), *a['box'], h=a['h']); SMALL[a['name']] = (av, af, a['mat'], a['col']); log(a['name'], len(av))
    Hh.set_var('base'); mb = Hh.mouth_lines(); Hh.set_var('a'); mo = Hh.mouth_lines(); Hh.set_var('blink'); cr = Hh.creases(); Hh.set_var('base')
    pad = lambda ls: np.array([np.pad(m, ((0, 12 - len(m)), (0, 0)), mode='edge') for m in ls])
    LINES = {'mouth_base': pad(mb), 'mouth_open': pad(mo), 'creases': np.array(cr), 'whisk': np.array(Hh.whiskers())}
    PIV = Hh.PIV; WHISK = {'r': list(Hh.WHISK_R), 'col': list(Hh.WHISK_COL)}; NOSE = {'col': list(getattr(Hh, 'NOSE_COL', (0.85, 0.47, 0.52))), 'wet': bool(getattr(Hh, 'NOSE_WET', False))}
    FUR = dict(Hh.FUR); src = Hh.fur_src(); SRC = {k: src[k] for k in ['nose', 'earOff', 'neck', 'should', 'wrist', 'hip', 'foot', 'tail']}
    if FUR.get('chest') and len(FUR['chest']) == 4: FUR['chest'] = FUR['chest'][1:]
    FUR['front'] = [float(Hh.H[1]), float(Hh.HEAD_R[1]) * 1.2, 0.45, 2.2, float(Hh.EYES[0][2] + Hh.RE * 1.8), 8.0, 0.6, 0.2]
def others_fn(nm):
    skip = {'body': 'feet', 'feet': 'body'}.get(nm); names = [k for k in FN if k != nm and k != skip]
    base = lambda p: np.min(np.stack([FN[k](p) for k in names], -1), -1)
    if skip is None or skip not in FN: return base
    zc = Z0 + OV * 0.5
    if nm == 'body': return lambda p: np.where(p[:, 2] > zc, base(p), -1.0)      # шерсть на ноге ниже шва — у ступней
    return lambda p: np.where(p[:, 2] < zc, base(p), -1.0)

# ---------- вершины: цвета кожи и шерсти, где расти шерсти ----------
man = {'info': {}, 'skins': {}, 'small': {}}; blobs = {}; LIMIT = 40_000_000
def put(arr, key):
    arr = np.ascontiguousarray(arr); b = arr.tobytes(); fi = 0
    while True:
        fn = '%s_%d.wasm' % (name, fi); cur = blobs.setdefault(fn, bytearray())
        if len(cur) + len(b) + 16 <= LIMIT or len(cur) == 0: break
        fi += 1
    cur = blobs[fn]; cur.extend(b'\0' * ((-len(cur)) % 16)); off = len(cur); cur.extend(b)
    return {'file': fn, 'off': off, 'n': int(arr.size), 'type': str(arr.dtype)}
EY = np.array(HERO.EYES); RE = float(HERO.RE)
# v6.1 упаковка: координаты — разности соседних точек (байты отдельно), номера треугольников — «шаг назад от новой точки» переменной длины,
# нормали не храним — телефон считает их сам по треугольникам (крышки срезов ступни/тела пропускает)
def pack_pos(pq):
    q = pq.astype(np.int32); d = (np.diff(np.vstack([np.zeros((1, 3), np.int32), q]), axis=0)) & 0xFFFF
    d = np.where(d >= 32768, d - 65536, d); z = ((d << 1) ^ (d >> 31)).astype(np.uint32) & 0xFFFF
    return np.concatenate([(z & 255).astype(np.uint8).T.ravel(), (z >> 8).astype(np.uint8).T.ravel()])
def pack_idx(f):
    I = f.astype(np.int64).ravel(); mx = np.maximum.accumulate(np.concatenate([[-1], I[:-1]])); back = mx + 1 - I
    z = np.where(back >= 0, back * 2, -back * 2 - 1).astype(np.int64); out = bytearray()
    for v in z.tolist():
        while v >= 128: out.append((v & 127) | 128); v >>= 7
        out.append(v)
    return np.frombuffer(bytes(out), np.uint8)
CUTZ = {}
if Z0 is not None: CUTZ = {'body': Z0, 'feet': Z0 + OV}
for sk, (v, f, n, reg) in SKINS.items():
    var = sk.split('_')[1] if sk.startswith('head_') else 'base'; part = 'head' if sk.startswith('head') else sk
    HERO.set_var(var)
    reg = np.asarray(reg).astype(np.int32); skin, fur = HERO.colors(v, reg, n)
    if part == 'head' and var != 'blink':   # тёмная «подводка» вокруг глаз
        ring = np.zeros(len(v), bool)
        for c in EY: q = v - c; ring |= (np.linalg.norm(HERO.eye_q(q) if hasattr(HERO, 'eye_q') else q, axis=-1) < RE * 1.18) & (q[:, 1] < RE * 0.16)
        skin[ring] = (0.09, 0.04, 0.02) if name == 'barsik' else (0.05, 0.035, 0.03)
    sss = np.where(reg == 8, 0.9, np.where(reg == 4, 0.5, 0.18))
    ok = HERO.fur_ok(v, reg)
    if var == 'blink':     # на закрытых веках — только шерсть у глаз (отдельная, видна при моргании)
        near = np.zeros(len(v), bool)
        for c in EY: near |= np.linalg.norm(HERO.eye_q(v - c) if hasattr(HERO, 'eye_q') else v - c, axis=-1) < RE + 0.012
        ok &= near
    if var in ('base', 'blink'): ok &= others_fn(part)(v) > 0.0015
    else: ok[:] = False
    HERO.set_var('base')
    pa = ax(v); lo = pa.min(0); hi = pa.max(0); sc = np.maximum(hi - lo, 1e-6) / 65535.0; pq = np.round((pa - lo) / sc).astype(np.uint16)
    fdat = put(np.clip(np.round(np.concatenate([fur, ok[:, None].astype(F), (reg[:, None] / 255.0)], -1) * 255), 0, 255).astype(np.uint8), sk) if var in ('base', 'blink') else None
    man['skins'][sk] = {'pz': put(pack_pos(pq), sk), 'lo': lo.tolist(), 'sc': sc.tolist(), 'iv': put(pack_idx(f), sk), 'ni': int(f.size), 'cut': CUTZ.get(sk),
        'c': put(np.clip(np.round(np.concatenate([skin, sss[:, None]], -1) * 255), 0, 255).astype(np.uint8), sk),
        'f': fdat, 'nv': int(len(v)), 'part': part}
    log('кожа', sk, len(v), 'шерсть растёт на', int(ok.sum()))
for k, (v, f, mat, col) in SMALL.items():
    pa = ax(v); lo = pa.min(0); hi = pa.max(0); sc = np.maximum(hi - lo, 1e-6) / 65535.0; pq = np.round((pa - lo) / sc).astype(np.uint16)
    man['small'][k] = {'pz': put(pack_pos(pq), k), 'lo': lo.tolist(), 'sc': sc.tolist(), 'nv': int(len(v)), 'iv': put(pack_idx(f), k), 'ni': int(f.size), 'mat': mat, 'col': list(col), 'part': 'body' if k in ('scarf', 'collar', 'tag') else 'head'}
man['info'] = {'name': name, 'eyes': ax(EY).tolist(), 're': RE, 'iris': [list(c) for c in HERO.IRIS], 'piv': {k: ax(PIV[k]).tolist() for k in PIV},
               'lines': {k: ax(LINES[k]).tolist() for k in LINES}, 'whisk': WHISK, 'nose': NOSE, 'fur': FUR,
               'src': {k: (ax(SRC[k]).tolist() if not isinstance(SRC[k][0], (list, tuple)) else [ax(x).tolist() for x in SRC[k]]) for k in SRC}, 'up': [0, 1, 0]}
man['info']['src']['earOff'] = ax(SRC['earOff']).tolist()
if getattr(HERO, 'EYE_AIM', None) is not None:
    man['info']['eyeAim'] = ax(HERO.EYE_AIM).tolist(); dv = float(getattr(HERO, 'EYE_DIV', 0.0)); aims = []
    for E in HERO.EYES:
        d = nrm(HERO.EYE_AIM - E); a = dv * np.sign(E[0]); c, sn = math.cos(a), math.sin(a); d = V(d[0] * c - d[1] * sn, d[0] * sn + d[1] * c, d[2]); aims.append(ax(E + d * 1.5).tolist())
    man['info']['eyeAims'] = aims
if getattr(HERO, 'EYE_K', None) is not None: man['info']['eyeK'] = list(HERO.EYE_K)
if getattr(HERO, 'EYE_CENTER', 0):   # радужка — в середину видимой части глаза (чуть к «прямо»), без косоглазия
    import eye_open; dirs = []
    kh, kv = HERO.EYE_CENTER if isinstance(HERO.EYE_CENTER, tuple) else (HERO.EYE_CENTER, HERO.EYE_CENTER)
    for c, _ in eye_open.opening(HERO):
        yw = math.atan2(c[0], -c[1]) * kh; pt = math.atan2(c[2], -c[1]) * kv; d = nrm(V(math.tan(yw), -1, math.tan(pt))); dirs.append(ax(d).tolist())
    man['info']['eyeDirs'] = dirs; log('радужка смотрит', [[round(x, 3) for x in d] for d in dirs])
if getattr(HERO, 'EYE_S', None) is not None: es = HERO.EYE_S; man['info']['eyeS'] = [float(es[0]), float(es[2]), float(es[1])]   # в осях глаза: вбок, вверх, вперёд
man['info']['toeY'] = float(getattr(HERO, 'TOE_Z', 0.0)); man['info']['irisS'] = int(getattr(HERO, 'IRIS_STYLE', 0))
import gzip
for fn, b in blobs.items():
    z = gzip.compress(bytes(b), 9); open(os.path.join(OUT, fn), 'wb').write(z); log(fn, round(len(b) / 1e6, 1), 'МБ ->', round(len(z) / 1e6, 1), 'МБ сжато')
json.dump(man, open(os.path.join(OUT, name + '.json'), 'w')); log('готово')
