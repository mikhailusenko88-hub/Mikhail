"""Сетка кота из SDF: внутренняя поверхность стекла, горлышко открыто. → cat_mesh.npz (v, f) + cat_sdf.npz (сетка SDF для счётчика и звука)."""
import numpy as np
from skimage import measure
import catsdf as C
h = float(__import__('sys').argv[1]) if len(__import__('sys').argv) > 1 else 0.0025
x0, x1, y0, y1, z0, z1 = -0.18, 0.18, -0.16, 0.16, -0.006, 0.46
xs = np.arange(x0, x1, h); ys = np.arange(y0, y1, h); zs = np.arange(z0, z1, h)
X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
D = C.sdf(np.stack([X, Y, Z], -1)).astype(np.float32)
v, f, n, _ = measure.marching_cubes(D, 0.0, spacing=(h, h, h), gradient_direction='ascent')
v += np.array([x0, y0, z0])
# открыть горлышко: убрать крышку
c = v[f].mean(1)
rxy = np.hypot(c[:, 0] - C.MOUTH_C[0], c[:, 1] - C.MOUTH_C[1])
cap = (c[:, 2] > C.MOUTH_Z1 - 0.0015) & (rxy < C.MOUTH_R + 0.0005)
f = f[~cap]
# нормали наружу? проверка: нормаль грани vs направление от центра масс
tri = v[f]
fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
out = (fn * (tri.mean(1) - v.mean(0))).sum(1)
print('граней', len(f), 'вершин', len(v), 'доля нормалей наружу', round((out > 0).mean(), 3), 'крышка убрана', int(cap.sum()))
if (out > 0).mean() < 0.5:
    f = f[:, ::-1]
    print('развернул нормали')
np.savez_compressed('cat_mesh.npz', v=v.astype(np.float32), f=f.astype(np.int32))
# SDF-сетка 4 мм для счётчика/звука
hs = 0.004
xs = np.arange(x0, x1 + hs, hs); ys = np.arange(y0, y1 + hs, hs); zs = np.arange(z0, z1 + hs, hs)
X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
np.savez_compressed('cat_sdf.npz', d=C.sdf(np.stack([X, Y, Z], -1)).astype(np.float16), o=np.array([x0, y0, z0]), h=hs,
                    mouth=np.array([C.MOUTH_C[0], C.MOUTH_C[1], C.MOUTH_R, C.MOUTH_Z1]))
