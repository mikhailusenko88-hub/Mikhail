# Барсик для «неонового» проектора: кожа (одна сетка), шерсть, нос, шарф, глаза, усы, рот + кости для походки.
# Геометрия — из build_geo.py (как в Blender). Выход: cat.bin (заголовок JSON + бинарные секции).
# Координаты переводятся из Blender (z вверх, морда к -y) в движок (y вверх, морда к -z).
import sys, json, math, time, struct
import numpy as np
sys.argv = [sys.argv[0]]
import build_geo as B
from build_geo import V, F, nrm

T0 = time.time()
def log(*a): print('[%5.1fs]' % (time.time() - T0), *a, flush=True)
OUT = sys.argv[1] if len(sys.argv) > 1 else 'cat.bin'
H_SKIN = 0.0048
N_FUR = 130000

# ---------- кости (в координатах Blender) ----------
# 0 body, 1 head, 2 armL, 3 armR, 4 legL_up, 5 legL_low, 6 legR_up, 7 legR_low, 8 tail1, 9 tail2
PIV = [V(0, 0, 0.36), B.NECK, B.SHOULD[0], B.SHOULD[1],
       B.HIP[0] + V(0, -0.005, 0.03), V(-0.09, -0.045, 0.1), B.HIP[1] + V(0, -0.005, 0.03), V(0.09, -0.045, 0.1),
       B.TAIL[0], B.TAIL[3]]
def ss(a, b, x): t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
def weights(p, reg):
    """Две кости и вес второй для каждой точки."""
    n = len(p); x, y, z = p[:, 0], p[:, 1], p[:, 2]
    a = np.zeros(n, np.int32); b = np.zeros(n, np.int32); w = np.zeros(n, F)
    head = (reg == 1) | (reg == 2) | (reg == 3) | (reg == 4) | (reg == 8)
    # голова <- тело у шеи
    a[head] = 0; b[head] = 1; w[head] = ss(0.53, 0.60, z[head])
    tor = reg == 0
    a[tor] = 0; b[tor] = 1; w[tor] = ss(0.55, 0.63, z[tor])
    arm = reg == 5
    for s, bone in ((-1, 2), (1, 3)):
        m = arm & ((x * s) > 0); a[m] = 0; b[m] = bone; w[m] = ss(0.09, 0.15, np.abs(x[m]))
    leg = reg == 6
    for s, up, low in ((-1, 4, 5), (1, 6, 7)):
        m = leg & ((x * s) > 0)
        wl = ss(0.135, 0.085, z[m])            # ниже колена -> нижняя кость
        wb = ss(0.21, 0.27, z[m])              # верх бедра -> тело
        # три влияния: тело / верх / низ -> оставляем две сильнейшие
        upw = (1 - wb) * (1 - wl); loww = (1 - wb) * wl
        A = np.where(wb > upw, 0, up); Bn = np.where(loww > 0.0, low, 0)
        # простая схема: если ниже колена — up/low, иначе body/up
        lowm = wl > 0.001
        a[m] = np.where(lowm, up, 0); b[m] = np.where(lowm, low, up); w[m] = np.where(lowm, wl, 1 - wb)
    tail = reg == 7
    mids = np.array([(B.TAIL[j + 1] + B.TAIL[j]) / 2 for j in range(len(B.TAIL) - 1)])
    if tail.any():
        near = np.argmin(np.linalg.norm(p[tail][:, None, :] - mids[None], axis=-1), -1).astype(F)
        a[tail] = 8; b[tail] = 9; w[tail] = ss(1.0, 3.5, near)
        base = tail & (y < 0.17); a[base] = 0; b[base] = 8; w[base] = ss(0.12, 0.17, y[base])
    return a, b, np.clip(w, 0, 1)

# ---------- кожа ----------
log('кожа…')
v, f = B.build_skin(H_SKIN); log('кожа', len(v), 'вершин', len(f), 'треугольников')
nor = B.grad(v); reg = B.region_of(v)
mel, red, stripe, cream = B.colors(v, reg, nor)
col = B.mel_rgb(mel).astype(F)
# кожа под шерстью — чуть темнее и теплее, чтобы просвечивала как подшёрсток; мордочка/внутр. ухо — свои цвета
col = np.where((reg == 8)[:, None], V(0.95, 0.6, 0.62), col)
col = np.where((reg == 2)[:, None], V(0.97, 0.9, 0.84), col)              # мордочка кремовая
col = np.where((reg == 3)[:, None], col * 0.85, col)                       # веки
furred = ~((reg == 2) | (reg == 8) | (reg == 10) | (reg == 11))
sa, sb, sw = weights(v, reg)
log('веса кожи готовы')

# ---------- шерсть ----------
log('шерсть…')
fur = B.make_fur(v, f, nor, reg, total=N_FUR, P=4, seed=3)
P = fur['fur_pts']; n_f = len(P); log('шерсть', n_f, 'волосков')
R = P[:, 0]; freg = fur['fur_reg'].astype(np.int32)
fa, fb, fw = weights(R, freg)
fn = nrm(P[:, 1] - P[:, 0])
# нормаль кожи в корне волоска — для освещения
fnor = B.grad(R)

# ---------- нос, шарф, глаза, усы, рот ----------
nv, nf = B.small_mesh(B.nose_fn, (-0.05, -0.25, 0.67), (0.05, -0.18, 0.74), h=0.0015)
nn = nrm(np.stack([B.nose_fn(nv + d) - B.nose_fn(nv - d) for d in (V(0.0008, 0, 0), V(0, 0.0008, 0), V(0, 0, 0.0008))], -1))
sv, sf = B.small_mesh(B.scarf_fn, (-0.15, -0.17, 0.36), (0.16, 0.12, 0.66), h=0.003)
sn = nrm(np.stack([B.scarf_fn(sv + d) - B.scarf_fn(sv - d) for d in (V(0.0008, 0, 0), V(0, 0.0008, 0), V(0, 0, 0.0008))], -1))
whisk = np.array(B.whiskers(), F)            # 8 x 8 x 3
mouth = [m.astype(F) for m in B.mouth_lines()]
log('нос', len(nv), 'шарф', len(sv), 'усы', whisk.shape, 'рот', [len(m) for m in mouth])

# ---------- перевод в движок: (x, y, z)_blender -> (x, z, y)_engine ----------
def E(p): p = np.asarray(p, F); return np.stack([p[..., 0], p[..., 2], p[..., 1]], -1).astype(F)
SCALE = 1 / 20000.0
def q16(a): return np.clip(np.round(a / SCALE), -32767, 32767).astype(np.int16)
def oct8(n):
    n = nrm(np.asarray(n, F)); l = np.abs(n).sum(-1, keepdims=True); pq = n[:, :2] / l
    neg = n[:, 2] < 0
    sgn = np.where(pq >= 0, 1.0, -1.0)
    alt = (1 - np.abs(pq[:, ::-1])) * sgn
    pq = np.where(neg[:, None], alt, pq)
    return np.clip(np.round(pq * 127), -127, 127).astype(np.int8)
def u8(a): return np.clip(np.round(np.asarray(a) * 255), 0, 255).astype(np.uint8)

secs = {}; blob = bytearray()
def put(name, arr):
    while len(blob) % 4: blob.append(0)
    off = len(blob); b = np.ascontiguousarray(arr).tobytes(); blob.extend(b); secs[name] = {'off': off, 'len': len(b)}; return off

# кожа: pos i16x3 | oct i8x2 | col u8x3 | boneA u8 | boneB u8 | w u8 | furred u8 | pad  = 16 B
skin = np.zeros(len(v), dtype=[('p', np.int16, 3), ('n', np.int8, 2), ('c', np.uint8, 3), ('a', np.uint8), ('b', np.uint8), ('w', np.uint8), ('f', np.uint8), ('pad', np.uint8)])
skin['p'] = q16(E(v)); skin['n'] = oct8(E(nor)); skin['c'] = u8(col); skin['a'] = sa; skin['b'] = sb; skin['w'] = u8(sw); skin['f'] = furred.astype(np.uint8)
put('skin_v', skin); put('skin_i', f.astype(np.uint32))
# шерсть: 4 точки i16x3 (24) | oct нормали кожи i8x2 (2) | col u8x3 (3) | a,b,w u8 (3) | rad u8 (×0.02 мм) | reg u8 | pad 2 = 36 B
furv = np.zeros(n_f, dtype=[('p', np.int16, (4, 3)), ('n', np.int8, 2), ('c', np.uint8, 3), ('a', np.uint8), ('b', np.uint8), ('w', np.uint8), ('r', np.uint8), ('g', np.uint8), ('pad', np.uint8, 2)])
furv['p'] = q16(E(P)); furv['n'] = oct8(E(fnor)); furv['c'] = u8(fur['fur_col']); furv['a'] = fa; furv['b'] = fb; furv['w'] = u8(fw)
furv['r'] = np.clip(np.round(fur['fur_rad'] / 0.00002), 1, 255).astype(np.uint8); furv['g'] = freg.astype(np.uint8)
put('fur', furv)
# нос, шарф: pos f32x3, normal f32x3 (24 B); индексы u32; кости — голова / тело+голова
def mesh_sec(name, vv, nn_, ff, bone_fn):
    m = np.zeros(len(vv), dtype=[('p', np.float32, 3), ('n', np.float32, 3), ('a', np.uint8), ('b', np.uint8), ('w', np.uint8), ('pad', np.uint8)])
    m['p'] = E(vv); m['n'] = E(nn_); a_, b_, w_ = bone_fn(vv); m['a'] = a_; m['b'] = b_; m['w'] = u8(w_)
    put(name + '_v', m); put(name + '_i', ff.astype(np.uint32))
mesh_sec('nose', nv, nn, nf, lambda p: (np.full(len(p), 0), np.full(len(p), 1), np.ones(len(p), F)))
mesh_sec('scarf', sv, sn, sf, lambda p: (np.full(len(p), 0), np.full(len(p), 1), ss(0.55, 0.63, p[:, 2])))
put('whisk', E(whisk).astype(np.float32))                 # 8 усов по 8 точек
mouth_pts = np.concatenate([E(m) for m in mouth], 0).astype(np.float32); put('mouth', mouth_pts)
eyes = E(np.array(B.EYES, F)).astype(np.float32); put('eyes', eyes)
piv = E(np.array(PIV, F)).astype(np.float32); put('piv', piv)

hdr = {'scale': SCALE, 'skin': {'nv': len(v), 'ni': len(f) * 3}, 'fur': {'n': n_f},
       'nose': {'nv': len(nv), 'ni': len(nf) * 3}, 'scarf': {'nv': len(sv), 'ni': len(sf) * 3},
       'whisk': {'n': int(whisk.shape[0]), 'pts': int(whisk.shape[1])}, 'mouth': [len(m) for m in mouth],
       'eyeR': float(B.RE), 'bones': ['body', 'head', 'armL', 'armR', 'legL_up', 'legL_low', 'legR_up', 'legR_low', 'tail1', 'tail2'],
       'sec': secs}
hb = json.dumps(hdr).encode(); pad = (4 - len(hb) % 4) % 4
with open(OUT, 'wb') as fp:
    fp.write(b'NCAT'); fp.write(struct.pack('<I', len(hb))); fp.write(hb); fp.write(b'\0' * pad); fp.write(bytes(blob))
log('готово', OUT, len(blob) // 1024, 'КБ')
