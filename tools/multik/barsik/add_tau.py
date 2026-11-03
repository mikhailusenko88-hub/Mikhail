# Плотность меха над каждой точкой — по соседним волоскам (без сетки): сколько «тени» даёт свой слой меха.
import numpy as np, sys
from scipy.spatial import cKDTree
var = sys.argv[1]; G = dict(np.load('out/geo_%s.npz' % var))
P = G['fur_pts']; root = P[:, 0]; L = np.linalg.norm(np.diff(P, axis=1), axis=-1).sum(1); w = 2 * G['fur_rad'] * L
tree = cKDTree(root); K = 40
def tau_at(q):
    out = np.empty(len(q), np.float32)
    for i in range(0, len(q), 100000):
        d, j = tree.query(q[i:i + 100000], k=K); dk = d[:, -1]
        out[i:i + 100000] = (K / (np.pi * np.maximum(dk, 1e-4) ** 2)) * w[j].mean(1)
    return out
t = tau_at(root)
# сгладить по соседям — без шума
_, j = tree.query(root, k=16); t = t[j].mean(1).astype(np.float32)
G['fur_tau'] = t; G['skin_tau'] = tau_at(G['skin_v'])
print('fur_tau: медиана %.1f, 5%% %.1f, 95%% %.1f' % tuple(np.percentile(t, [50, 5, 95])))
np.savez_compressed('out/geo_%s.npz' % var, **G)
