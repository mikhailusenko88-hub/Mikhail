# Лапа и туловище — две сетки. Шерсть и кожа, спрятанные в покое внутри другой части (бок под лапой, внутренняя
# сторона лапы в боку), запеклись тёмными: свет туда не доходит. Когда лапа поднимается, они открываются —
# даём им свет соседних открытых волосков той же части (не у самой подмышки, где тоже тень).
# RAW=out/phone_s3.raw python3 fix_hidden.py  → out/phone_s3_fix.raw
import numpy as np, struct, os
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
src = os.environ.get('RAW', 'out/phone_s3.raw'); dst = src.replace('.raw', '_fix.raw')
raw = bytearray(open(src, 'rb').read()); o = 0
nf = struct.unpack_from('<I', raw, o)[0]; o += 4
offF = o; F = np.frombuffer(bytes(raw[o:o + nf * 216]), np.float32).reshape(nf, 54).copy(); o += nf * 216
nl = struct.unpack_from('<I', raw, o)[0]; o += 4; ln = struct.unpack_from('<I', raw, o)[0]; o += 4 + ln * 4
nv, nt = struct.unpack_from('<II', raw, o); o += 8
offV = o; Vv = np.frombuffer(bytes(raw[o:o + nv * 80]), np.float32).reshape(nv, 20).copy()
S = np.load('out/split_vol.npz'); lo = S['lo']; h = float(S['h'][0]); VB = S['body'].astype(np.float32); VA = S['arm'].astype(np.float32)
def sd(vol, p): return map_coordinates(vol, ((p - lo) / h).T, order=1, mode='nearest')
def fix(p, vals, ok):
    db, da = sd(VB, p), sd(VA, p); arm = np.abs(da) < np.abs(db)
    hid = ok & ((arm & (db < -0.0015)) | (~arm & (da < -0.0015)))
    clear = ok & ~hid & ((arm & (db > 0.012)) | (~arm & (da > 0.012)))
    out = vals.copy()
    for m in (arm, ~arm):
        H = np.nonzero(hid & m)[0]; D = np.nonzero(clear & m)[0]
        if not len(H) or not len(D): continue
        _, j = cKDTree(p[D]).query(p[H], k=12)
        out[H] = np.median(vals[D][j], axis=1)
    return out, int(hid.sum())
reg = F[:, 53].astype(int)
bf, nh = fix(F[:, :3], F[:, 15:45], reg < 9)
F[:, 15:45] = bf
mat = Vv[:, 19].astype(int)
bs, nh2 = fix(Vv[:, :3], Vv[:, 9:15], mat < 9)
Vv[:, 9:15] = bs
raw[offF:offF + nf * 216] = F.astype(np.float32).tobytes(); raw[offV:offV + nv * 80] = Vv.astype(np.float32).tobytes()
open(dst, 'wb').write(raw)
print('спрятанных волосков: %d из %d, вершин кожи: %d из %d → %s' % (nh, nf, nh2, nv, dst))
