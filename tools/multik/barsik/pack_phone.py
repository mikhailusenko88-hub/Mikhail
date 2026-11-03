# out/phone.raw -> /home/claude/phone/barsik_data.js (gzip + base64): волоски с готовым светом, кожа, нос, шарф, усы
import numpy as np, struct, gzip, base64, json, sys, os
raw = open(os.environ.get('RAW', 'out/phone.raw'), 'rb').read(); o = 0
def take(n, dt=np.float32):
    global o; a = np.frombuffer(raw, dt, n, o); o += n * np.dtype(dt).itemsize; return a
nf = struct.unpack_from('<I', raw, o)[0]; o += 4
F = take(nf * 54).reshape(nf, 54)
KEEP = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
rng = np.random.default_rng(1)
reg = F[:, 53].astype(int); pri = np.where(reg == 12, 1e9, np.where(np.isin(reg, [1, 3, 4, 8]), 3.0, 1.0))   # лицо и уши — гуще, ворсинки шарфа — все
KEEP += int((reg == 12).sum())
sel = np.argsort(rng.random(nf) / pri)[:KEEP]; sel.sort(); F = F[sel]; n = len(F)
pos = F[:, :15].reshape(n, 5, 3); bake = F[:, 15:45].reshape(n, 5, 6); alb = F[:, 45:48]; rad = F[:, 48]; w = F[:, 49:53]; rg = F[:, 53]
root = np.round(pos[:, 0] * 20000).astype(np.int16)
off = pos[:, 1:] - root[:, None, :].astype(np.float32) / 20000
print('макс. смещение кончика, мм', np.abs(off).max() * 1000)
offq = np.clip(np.round(off * 1580), -127, 127).astype(np.int8)               # 0,59 мм
bq = np.clip(np.round(bake[:, 2:] * 255), 0, 255).astype(np.uint8)            # свет в точках t=0,5 / 0,75 / 1
aq = np.clip(np.round(np.sqrt(np.clip(alb, 0, 1)) * 255), 0, 255).astype(np.uint8)
rq = np.clip(np.round(rad * 100000), 1, 255).astype(np.uint8)
wq = np.stack([np.round(w[:, 0] * 255), np.where(w[:, 1] < 0, 255, np.round(w[:, 1] * 254)), np.round(w[:, 2] * 127) % 256, np.round(w[:, 3] * 255)], -1).astype(np.uint8)
fur = np.concatenate([root.view(np.uint8).reshape(n, 6), offq.view(np.uint8).reshape(n, 12), bq.reshape(n, 18), aq, rq[:, None], wq, rg.astype(np.uint8)[:, None]], 1)
assert fur.shape[1] == 45
# усы и рот
nl = struct.unpack_from('<I', raw, o)[0]; o += 4; ln = struct.unpack_from('<I', raw, o)[0]; o += 4; L = take(ln); lines = []; k = 0
for i in range(nl):
    np_ = int(L[k]); which = int(L[k + 1]); k += 2; pts = L[k:k + np_ * 4].reshape(np_, 4); k += np_ * 4
    lines.append({'w': which, 'p': np.round(pts[:, :3], 5).tolist(), 'h': np.round(pts[:, 3], 3).tolist()})
# кожа: склеить вершины в ячейках (лишние под шерстью), мордочку — мельче
nv, nt = struct.unpack_from('<II', raw, o); o += 8
V = take(nv * 20).reshape(nv, 20); T = take(nt * 4, np.int32).reshape(nt, 4)
p = V[:, :3]; mat_v = V[:, 19].astype(int)
cell = np.where(np.isin(mat_v, [2, 8]), 0.0026, np.where(mat_v == 21, 0.0012, np.where(mat_v == 22, 0.003, 0.0065)))   # мордочка/ухо, нос, шарф, остальное
if os.environ.get('KNIT'):
    sys.argv = sys.argv[:1]; import knit_scarf as KS; cell = np.where((mat_v == 22) & (KS.tassel_sd(p.astype(np.float32)) < 0.002), 0.0011, cell)   # кисточки — мелко
eyes = take(17)
E0, E1 = eyes[0:3], eyes[3:6]; RE = eyes[13]
for E in (E0, E1): cell = np.where((np.linalg.norm(p - E, axis=1) < RE + 0.02) & (mat_v < 20), 0.0026, cell)   # у глаз — мельче
key = np.concatenate([np.floor(p / cell[:, None]).astype(np.int64), np.round(cell * 1e5).astype(np.int64)[:, None], mat_v.astype(np.int64)[:, None]], 1)
uk, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel(); m = len(uk)   # точные ключи, без совпадений хэша
cnt = np.bincount(inv, minlength=m).astype(np.float32)
def avg(a): return np.stack([np.bincount(inv, a[:, j], m) for j in range(a.shape[1])], -1) / cnt[:, None]
P2 = avg(p); N2 = avg(V[:, 3:6]); N2 /= np.maximum(np.linalg.norm(N2, axis=1, keepdims=True), 1e-9); A2 = avg(V[:, 6:9]); B2 = avg(V[:, 9:15]); W2 = avg(V[:, 15:19])
M2 = np.zeros(m, int); M2[inv] = mat_v
T2 = inv[T[:, :3]]; ok = (T2[:, 0] != T2[:, 1]) & (T2[:, 1] != T2[:, 2]) & (T2[:, 0] != T2[:, 2]); T2 = T2[ok]; tm = T[ok, 3]
print('кожа: %d -> %d вершин, %d -> %d треугольников' % (nv, m, nt, len(T2)))
def oct(nn):
    nn = nn / np.abs(nn).sum(1, keepdims=True); x, y = nn[:, 0].copy(), nn[:, 1].copy(); neg = nn[:, 2] < 0
    x2 = (1 - np.abs(y)) * np.sign(x + 1e-12); y2 = (1 - np.abs(x)) * np.sign(y + 1e-12); x[neg], y[neg] = x2[neg], y2[neg]
    return np.stack([np.round(x * 127), np.round(y * 127)], -1).astype(np.int8)
skin = np.concatenate([np.round(P2 * 20000).astype(np.int16).view(np.uint8).reshape(m, 6), oct(N2).view(np.uint8).reshape(m, 2),
                       np.clip(np.round(np.sqrt(np.clip(A2, 0, 1)) * 255), 0, 255).astype(np.uint8), np.clip(np.round(B2 * 255), 0, 255).astype(np.uint8),
                       np.stack([np.round(W2[:, 0] * 255), np.where(W2[:, 1] < 0, 255, np.round(np.clip(W2[:, 1], 0, 1) * 254)), np.round(W2[:, 2] * 127) % 256, np.round(W2[:, 3] * 255)], -1).astype(np.uint8),
                       M2.astype(np.uint8)[:, None], np.zeros((m, 2), np.uint8)], 1)
assert skin.shape[1] == 24
idx = T2.astype(np.uint32)
blob = fur.tobytes() + skin.tobytes() + idx.tobytes()
hdr = {'nfur': n, 'nskin': m, 'ntri': len(idx), 'lines': lines, 'eyes': np.round(eyes.astype(float), 6).tolist()}
gz = gzip.compress(blob, 9)
js = 'window.BARSIK_HDR=' + json.dumps(hdr, separators=(',', ':')) + ';\nwindow.BARSIK_GZ="' + base64.b64encode(gz).decode() + '";\n'
open(os.environ.get('OUT', '../../../Resources/Mebel/barsik/barsik_data.js'), 'w').write(js)
print('данные: сырые %.1f МБ, gzip %.1f МБ, js %.1f МБ' % (len(blob) / 1e6, len(gz) / 1e6, len(js) / 1e6))
