# Барсик по частям для анимации: голова (варианты рта и век), тело, две лапы, хвост — отдельные сетки и шерсть.
# python anim_geo.py -> out/anim.npz
import sys, time
import numpy as np
sys.argv = [sys.argv[0]]          # build_geo читает --var из argv
import build_geo as B
from build_geo import V, F, nrm, smin, smax, sd_cap, sd_sph, sd_ell, sd_rcone

T0 = time.time()
def log(*a): print('[%5.1fs]' % (time.time() - T0), *a, flush=True)

def set_var(v):
    B.VAR = v
    B.MOUTH = {'a': (V(0, -0.197, 0.65), V(0.034, 0.03, 0.026)), 'o': (V(0, -0.197, 0.652), V(0.017, 0.03, 0.019))}.get(v)

PIV = {'head': V(0, -0.01, 0.6), 'armL': B.SHOULD[0], 'armR': B.SHOULD[1], 'tail': B.TAIL[0], 'body': V(0, 0, 0)}

def arm_sd(p, i):
    x = sd_rcone(p, B.SHOULD[i], B.WRIST[i], 0.05, 0.039)
    x = smin(x, sd_ell(p, B.PAW[i], V(0.047, 0.054, 0.044)), 0.03)
    for j in (-1, 0, 1):
        x = smin(x, sd_sph(p, B.PAW[i] + V(j * 0.02 + (0.004 if i else -0.004), -0.042, -0.018), 0.017), 0.012)
    return smin(x, sd_sph(p, B.SHOULD[i] + V(0, 0.005, 0.005), 0.056), 0.03)   # плечо — чтобы на стыке не было щели

def f_head(p):
    d = B.parts(p)
    h = smin(d['head'], d['muzzle'], 0.035)
    if B.VAR != 'blink':
        for E in B.EYES: h = smax(h, -(np.linalg.norm(p - E, axis=-1) - (B.RE + 0.003)), 0.012)
    h = smin(h, d['lid'], 0.006)
    if B.MOUTH is not None:
        h = smax(h, -B.mouth_cav(p), 0.006); h = np.minimum(h, sd_ell(p, *B.TONGUE))
    h = smin(h, d['ear'], 0.05)
    inner = np.minimum(B.ear_sd(p, 0, True), B.ear_sd(p, 1, True)); h = smax(h, -inner, 0.008)
    return smin(h, sd_cap(p, V(0, -0.008, 0.565), V(0, -0.012, 0.66), 0.068), 0.03)     # шея-пробка под шарфом
def f_body(p):
    d = B.parts(p); return smin(d['torso'], d['leg'], 0.05)
def f_armL(p): return arm_sd(p, 0)
def f_armR(p): return arm_sd(p, 1)
def f_tail(p): return B.parts(p)['tail']
FN = {'head': f_head, 'body': f_body, 'armL': f_armL, 'armR': f_armR, 'tail': f_tail}
BOX = {'head': ((-0.3, -0.28, 0.5), (0.3, 0.2, 1.09)), 'body': ((-0.24, -0.25, -0.01), (0.24, 0.2, 0.68)),
       'armL': ((-0.28, -0.2, 0.22), (-0.04, 0.08, 0.58)), 'armR': ((0.04, -0.2, 0.22), (0.28, 0.08, 0.58)), 'tail': ((-0.06, 0.05, 0.12), (0.24, 0.38, 0.7))}

def mc(fn, lo, hi, h=0.0034):
    from skimage.measure import marching_cubes
    lo, hi = V(*lo), V(*hi); n = np.ceil((hi - lo) / h).astype(int) + 1
    xs, ys, zs = [lo[i] + np.arange(n[i], dtype=F) * h for i in range(3)]
    vol = np.empty((n[0], n[1], n[2]), F); YY, ZZ = np.meshgrid(ys, zs, indexing='ij')
    for i, x in enumerate(xs):
        p = np.stack([np.full(YY.size, x, F), YY.ravel(), ZZ.ravel()], -1); vol[i] = fn(p).reshape(YY.shape)
    v, f, _, _ = marching_cubes(vol, 0.0, spacing=(h, h, h))
    return (v + lo).astype(F), f.astype(np.int32)
def grad(fn, p, e=0.0008):
    g = np.zeros_like(p)
    for i in range(3):
        dp = np.zeros(3, F); dp[i] = e; g[:, i] = fn(p + dp) - fn(p - dp)
    return nrm(g)
def area(v, f): return float(np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=-1).sum() * 0.5)

def others(name):
    names = [k for k in FN if k != name]
    return lambda p: np.min(np.stack([FN[k](p) for k in names], -1), -1)

def skin_of(name):
    v, f = mc(FN[name], *BOX[name]); n = grad(FN[name], v); reg = B.region_of(v)
    mel, red, stripe, cream = B.colors(v, reg, n)
    return v, f, n, reg, B.mel_rgb(mel).astype(F)

def fur_of(name, v, f, n, reg, K=0.56e6, seed=3):
    tot = int(area(v, f) * K)
    fur = B.make_fur(v, f, n, reg, total=tot, seed=seed)
    R = fur['fur_pts'][:, 0]
    keep = others(name)(R) > 0.0015          # не растить шерсть внутри соседних частей
    return {k: a[keep] for k, a in fur.items()}

out = {}
set_var('base')
for name in ['body', 'armL', 'armR', 'tail', 'head']:
    v, f, n, reg, col = skin_of(name)
    fur = fur_of(name, v, f, n, reg, seed=3 + len(name))
    out.update({f'{name}_v': v, f'{name}_f': f, f'{name}_n': n, f'{name}_reg': reg.astype(np.int8), f'{name}_col': col})
    out.update({f'{name}_{k}': a for k, a in fur.items()})
    log(name, len(v), 'шерсть', len(fur['fur_pts']))
# варианты головы: та же шерсть, меняется только кожа (рот, веки)
for var in ['a', 'o', 'blink']:
    set_var(var)
    v, f, n, reg, col = skin_of('head')
    out.update({f'head_{var}_v': v, f'head_{var}_f': f, f'head_{var}_n': n, f'head_{var}_reg': reg.astype(np.int8), f'head_{var}_col': col})
    if var == 'blink':     # шерсть на сомкнутых веках — отдельно, видна только когда глаза закрыты
        fur = fur_of('head', v, f, n, reg, seed=99)
        R = fur['fur_pts'][:, 0]; near = np.zeros(len(R), bool)
        for E in B.EYES: near |= np.linalg.norm(R - E, axis=-1) < B.RE + 0.012
        out.update({f'blinkfur_{k}': a[near] for k, a in fur.items()})
        out['creases'] = np.array(B.creases())
    log('голова', var, len(v))
set_var('base')
out['mouth_base'] = np.array([np.pad(m, ((0, 12 - len(m)), (0, 0)), mode='edge') for m in B.mouth_lines()])
set_var('a'); out['mouth_open'] = np.array([np.pad(m, ((0, 12 - len(m)), (0, 0)), mode='edge') for m in B.mouth_lines()]); set_var('base')
nv, nf = B.small_mesh(B.nose_fn, (-0.05, -0.25, 0.67), (0.05, -0.18, 0.74))
sv, sf = B.small_mesh(B.scarf_fn, (-0.15, -0.17, 0.36), (0.16, 0.12, 0.66), h=0.0022)
out.update(nose_v=nv, nose_f=nf, scarf_v=sv, scarf_f=sf, whisk=np.array(B.whiskers()), eyes=np.array(B.EYES), re=np.array([B.RE]),
           piv=np.array([PIV[k] for k in ['head', 'armL', 'armR', 'tail']]))
np.savez_compressed('out/anim.npz', **out)
log('готово', sum(len(out[k]) for k in out if k.endswith('fur_pts')), 'волосков')
