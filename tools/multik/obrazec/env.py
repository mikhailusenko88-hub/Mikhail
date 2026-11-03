# Туманный лес ровно как в render.py (build_world, rng 11): стволы, мшистые камни, 90 тыс. травинок -> data/env.json + data/grass.bin
import json, numpy as np, os
out = '/home/claude/obrazec/data'; os.makedirs(out, exist_ok=True)
def ax(p): p = np.asarray(p, np.float32); return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1).astype(np.float32)
rng = np.random.default_rng(11)
trunks = []
for i in range(16):
    x = rng.uniform(-5.5, 5.5); y = rng.uniform(1.6, 10.0); r = rng.uniform(0.16, 0.42)
    if abs(x) < 0.9 and y < 3: x += 1.6 * np.sign(x or 1)
    trunks.append([float(x), float(-y), float(r)])          # у нас: x, z, радиус
stones = []
for i in range(5):
    x = rng.uniform(-2.5, 2.5); y = rng.uniform(1.2, 4.5); r = rng.uniform(0.2, 0.45)
    stones.append([float(x), float(-y), float(r)])
n = 90000; R = np.sqrt(rng.random(n)) * 3.2; A = rng.random(n) * 6.283
root = np.stack([np.cos(A) * R, np.sin(A) * R * 1.6 + 0.6, np.zeros(n)], -1)
ok = ~((np.abs(root[:, 0]) < 0.12) & (np.abs(root[:, 1] + 0.03) < 0.1)); root = root[ok]; n = len(root)
hgt = rng.uniform(0.04, 0.11, n); lean = rng.normal(0, 0.35, (n, 2))
k = 4; t = np.linspace(0, 1, k)
pts = root[:, None, :] + np.stack([lean[:, 0][:, None] * t * t * hgt[:, None], lean[:, 1][:, None] * t * t * hgt[:, None], hgt[:, None] * t], -1)
pts = ax(pts)
pts.astype(np.float32).tofile(os.path.join(out, 'grass.bin'))
json.dump({'trunks': trunks, 'stones': stones, 'grass_n': int(n), 'grass_k': k, 'grass_rad': [0.0028, 0.0022, 0.0014, 0.0002]}, open(os.path.join(out, 'env.json'), 'w'))
print('grass', n, os.path.getsize(os.path.join(out, 'grass.bin')) / 1e6, 'MB'); print(trunks[:3], stones)
