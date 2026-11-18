# Просмотр сетки PLY без внешних библиотек: читаю PLY (ascii/binary), рисую «глину» с пяти сторон z-буфером (numpy).
# python3 plyview.py <сетка.ply> <выход.jpg> [углы через запятую] [ось вверх: y|z]
import sys, math, numpy as np
from PIL import Image
def read_ply(p):
    f = open(p, 'rb'); hdr = [];
    while True:
        l = f.readline().decode('latin1').strip(); hdr.append(l)
        if l == 'end_header': break
    fmt = [l for l in hdr if l.startswith('format')][0].split()[1]
    els = []; cur = None
    for l in hdr:
        t = l.split()
        if t[0] == 'element': cur = [t[1], int(t[2]), []]; els.append(cur)
        elif t[0] == 'property': cur[2].append(t[1:])
    TY = {'float': 'f4', 'float32': 'f4', 'double': 'f8', 'uchar': 'u1', 'uint8': 'u1', 'int': 'i4', 'int32': 'i4', 'uint': 'u4', 'uint32': 'u4', 'short': 'i2', 'ushort': 'u2', 'char': 'i1'}
    V = F = None
    if fmt == 'ascii':
        rest = f.read().decode('latin1').split('\n'); i = 0
        for name, n, props in els:
            rows = rest[i:i + n]; i += n
            if name == 'vertex': V = np.array([[float(x) for x in r.split()[:3]] for r in rows], np.float32)
            if name == 'face': F = np.array([[int(x) for x in r.split()[1:4]] for r in rows], np.int64)
        return V, F
    end = '<' if 'little' in fmt else '>'
    for name, n, props in els:
        if name == 'vertex':
            dt = np.dtype([(pp[1], end + TY[pp[0]]) for pp in props]); a = np.frombuffer(f.read(dt.itemsize * n), dt, n)
            V = np.stack([a['x'], a['y'], a['z']], -1).astype(np.float32)
        elif name == 'face':
            pp = props[0]; ct, it = TY[pp[1]], TY[pp[2]]
            dt = np.dtype([('n', end + ct), ('i', end + it, (3,))]); a = np.frombuffer(f.read(dt.itemsize * n), dt, n); F = a['i'].astype(np.int64)
    return V, F
def render(V, F, yaw, pitch=8, W=420, up='y'):
    if up == 'y': V = V[:, [0, 2, 1]] * np.array([1, -1, 1], np.float32)   # y-вверх -> z-вверх, смотрим со стороны -y
    c = (V.max(0) + V.min(0)) / 2; R = np.linalg.norm(V.max(0) - V.min(0)) * 0.55
    a, b = math.radians(yaw), math.radians(pitch); eye = c + np.array([math.sin(a) * math.cos(b), -math.cos(a) * math.cos(b), math.sin(b)]) * R * 2.6
    fw = c - eye; fw /= np.linalg.norm(fw); rt = np.cross(fw, [0, 0, 1]); rt /= np.linalg.norm(rt); upv = np.cross(rt, fw)
    d = V - eye; x = d @ rt; y = d @ upv; z = d @ fw; t = math.tan(math.radians(15))
    px = (x / z / t * 0.5 + 0.5) * W; py = (0.5 - y / z / t * 0.5) * W
    T = F; n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]); n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
    L = np.array([-0.4, -0.7, 0.6]); L /= np.linalg.norm(L); sh = np.clip(np.abs(n @ L) * 0.75 + 0.3, 0, 1)
    zb = np.full((W, W), np.inf, np.float32); col = np.full((W, W), 0.92, np.float32)
    zt = (z[T[:, 0]] + z[T[:, 1]] + z[T[:, 2]]) / 3; order = np.argsort(-zt)
    X = px[T]; Y = py[T]
    for k in order:   # маленькие треугольники: красим по ограничивающей рамке с проверкой барицентрик
        xs, ys = X[k], Y[k]; x0, x1 = int(max(0, xs.min())), int(min(W - 1, xs.max() + 1)); y0, y1 = int(max(0, ys.min())), int(min(W - 1, ys.max() + 1))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-9: continue
        l0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den; l1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
        m = (l0 >= -1e-3) & (l1 >= -1e-3) & (1 - l0 - l1 >= -1e-3)
        col[y0:y1 + 1, x0:x1 + 1][m] = sh[k]
    return col
if __name__ == '__main__':
    V, F = read_ply(sys.argv[1]); out = sys.argv[2]; yaws = [float(a) for a in (sys.argv[3] if len(sys.argv) > 3 else '0,35,-35,90,180').split(',')]; up = sys.argv[4] if len(sys.argv) > 4 else 'y'
    if len(F) > 60000: F = F[np.random.default_rng(0).choice(len(F), 60000, replace=False)] if False else F
    ims = [render(V, F, y, up=up) for y in yaws]
    S = np.concatenate(ims, 1); rgb = np.stack([S * 0.86, S * 0.78, S * 0.68], -1)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(out, quality=88); print('ok', V.shape, F.shape)
