"""Сетка банки-кота: внутренняя поверхность стекла, отверстие сверху. → cat_mesh.npz (v, f), cat_sdf.npz (SDF 4 мм, край)."""
import sys
import numpy as np
from skimage import measure
import catsdf as C
h = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0025
x0, x1, y0, y1, z0, z1 = -0.16, 0.16, -0.14, 0.14, -0.006, 0.40
xs = np.arange(x0, x1, h); ys = np.arange(y0, y1, h); zs = np.arange(z0, z1, h)
X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
D = C.sdf(np.stack([X, Y, Z], -1)).astype(np.float32)
v, f, _, _ = measure.marching_cubes(D, 0.0, spacing=(h, h, h), gradient_direction='ascent')
v = v + np.array([x0, y0, z0])
# склеить совпадающие вершины, убрать вырожденные грани
q = np.round(v / 1e-6).astype(np.int64)
_, uidx, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
v = v[uidx]; f = inv.reshape(-1)[f]
tri = v[f]
area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
good = (area > 1e-13) & (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
f = f[good]
cap = C.in_open(v[f].mean(1))
# край отверстия: самые низкие точки — до куда наполнится
f = f[~cap]
used = np.unique(f); remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
v = v[used]; f = remap[f]
tri = v[f]
fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
out = (fn * (tri.mean(1) - v.mean(0))).sum(1)
if (out > 0).mean() < 0.5:
    f = f[:, ::-1]
# край: рёбра, встречающиеся один раз
e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), 1)
eu, cnt = np.unique(e, axis=0, return_counts=True)
rim = v[np.unique(eu[cnt == 1])]
print('граней', len(f), 'вершин', len(v), 'вырожденных убрано', int((~good).sum()), 'крышка', int(cap.sum()),
      'край z от', round(rim[:, 2].min(), 4), 'до', round(rim[:, 2].max(), 4))
np.savez_compressed('cat_mesh.npz', v=v.astype(np.float32), f=f.astype(np.int32))
hs = 0.004
xs = np.arange(x0, x1 + hs, hs); ys = np.arange(y0, y1 + hs, hs); zs = np.arange(z0, z1 + hs, hs)
X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
Ds = C.sdf(np.stack([X, Y, Z], -1))
np.savez_compressed('cat_sdf.npz', d=Ds.astype(np.float16), o=np.array([x0, y0, z0]), h=hs,
                    mouth=np.array([C.OPEN_C[0], C.OPEN_C[1], C.OPEN_R, rim[:, 2].min()]))
zr = rim[:, 2].min()
vol = ((Ds < 0) & (Z < zr)).sum() * hs ** 3
for r in (0.0075, 0.008, 0.009):
    print(f'r={r}: вместимость ~{int(vol * 0.58 / (4 / 3 * np.pi * r ** 3))} (объём до края {vol * 1000:.2f} л)')
