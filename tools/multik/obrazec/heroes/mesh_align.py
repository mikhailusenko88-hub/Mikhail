# подгонка вида модели спереди к вырезке с обложки: масштаб, сдвиг, поворот вокруг вертикали (по совпадению силуэтов)
import sys, json, math, numpy as np, cv2
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from plyview import read_ply; G3 = os.environ.get('G3D', '/home/claude/g3d')
n = sys.argv[1]; V, F = read_ply(G3 + '/out/%s_h3d.ply' % n)
m = cv2.imread(G3 + '/out/%s_mask.png' % n, cv2.IMREAD_UNCHANGED); A = (m[..., 3] > 128).astype(np.uint8)
D = 192; k = D / A.shape[0]; Ad = cv2.resize(A, (D, D), interpolation=cv2.INTER_AREA) > 0
def sil(yaw, s, dx, dy):
    c, sn = math.cos(yaw), math.sin(yaw); X = V[:, 0] * c + V[:, 2] * sn
    P = np.stack([X * s + dx, -V[:, 1] * s + dy], -1) * k; img = np.zeros((D, D), np.uint8)
    cv2.fillPoly(img, list(P[F].astype(np.int32)), 1); return img > 0
best = (0, None)
s0 = 300.0
for yaw in np.radians([-20, -10, 0, 10, 20]):
    for s in np.linspace(0.7, 1.4, 8) * s0:
        for dx in np.linspace(250, 520, 10):
            for dy in np.linspace(200, 520, 10):
                B = sil(yaw, s, dx, dy); iou = (Ad & B).sum() / max(1, (Ad | B).sum())
                if iou > best[0]: best = (iou, (yaw, s, dx, dy))
iou, (yaw, s, dx, dy) = best
for it in range(3):   # уточнение
    st = [math.radians(4) / (it + 1), s * 0.04 / (it + 1), 10 / (it + 1), 10 / (it + 1)]; p = [yaw, s, dx, dy]
    for j in range(4):
        for dd in (-1, 1):
            q = list(p); q[j] += dd * st[j]; B = sil(*q); v = (Ad & B).sum() / max(1, (Ad | B).sum())
            if v > iou: iou, p = v, q
    yaw, s, dx, dy = p
print(n, 'IoU %.3f' % iou, 'поворот %.1f°' % math.degrees(yaw), 'масштаб %.1f' % s, 'сдвиг', round(dx), round(dy))
json.dump({'yaw': yaw, 's': s, 'dx': dx, 'dy': dy, 'iou': iou}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meshes', 'align_%s.json' % n), 'w'))
B = cv2.resize(sil(yaw, s, dx, dy).astype(np.uint8) * 255, A.shape[::-1], interpolation=cv2.INTER_NEAREST)
vis = np.zeros(A.shape + (3,), np.uint8); vis[..., 1] = A * 255; vis[..., 2] = B; cv2.imwrite(os.environ.get('OUT', '/tmp') + '/align_%s.jpg' % n, vis)
