# Голова героя из 3D-модели нейросети (картинка обложки -> Hunyuan3D-2mini, ветка geroi3d): чтение meshes/<имя>.npz (готовит mesh2hero.py).
# Поле расстояний головы в метрах в осях героя (x вправо, y назад, z вверх) и цвет с обложки (только там, где модель видна с обложки).
import os, math, numpy as np
from scipy.ndimage import map_coordinates, gaussian_filter
F = np.float32
class MeshHead:
    def __init__(self, name, smooth=0.7):
        z = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meshes', name + '.npz'))
        self.D = gaussian_filter(z['D'].astype(np.float32), smooth) if smooth else z['D'].astype(np.float32)
        self.lo = z['lo'].astype(np.float64); self.step = float(z['step']); self.Sx = float(z['Sx']); self.HC = z['HC'].astype(np.float64); self.Hh = z['H'].astype(np.float64)
        self.yaw, self.s_img, self.dx, self.dy = [float(z[k]) for k in ('yaw', 's_img', 'dx', 'dy')]
        self.zb = z['zb']; self.img = z['img'].astype(np.float32) / 255; self.Rm = z['Rm'].astype(np.float64); self.T = z['T'].astype(np.float64) if 'T' in z.files else np.array([-float(z['xshift']), 0, 0])
        self.eyes = z['eyes']; self.nose = z['nose']; self.lip = z['lip']
        self.hi = self.lo + (np.array(self.D.shape) - 1) * self.step
        self.O = self.Hh - np.array([self.HC[0], -self.HC[2], self.HC[1]]) * self.Sx
        # «альбедо» с обложки: делим на сглаженную яркость (снимаем нарисованный свет), цвет и мелкие тёмные детали остаются
        import json, cv2
        cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meshes', 'cfg.json'))).get(name, {})
        if cfg.get('paint_out'):   # стереть нарисованные глаза, брови, нос, рот: у движка они свои, живые
            m = np.zeros(self.img.shape[:2], np.uint8)
            for u, v, ru, rv, a in cfg['paint_out']: cv2.ellipse(m, (int(u), int(v)), (int(ru), int(rv)), a, 0, 360, 255, -1)
            self.img = cv2.inpaint((self.img * 255).astype(np.uint8), m, 21, cv2.INPAINT_TELEA).astype(np.float32) / 255
        mp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meshes', name + '_mask.png')   # вырезка героя с обложки: фон не красим
        if os.path.exists(mp):
            from PIL import Image as _I
            al = np.asarray(_I.open(mp).convert('RGBA'))[..., 3].astype(np.float32) / 255
            self.mask = np.clip((cv2.erode((al > 0.5).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32)), 0, 1)
        else: self.mask = np.ones(self.img.shape[:2], np.float32)
        L = self.img @ np.array([0.3, 0.55, 0.15], np.float32); S = gaussian_filter(L, 9)
        self.alb = np.clip(self.img / np.maximum(S, 0.05)[..., None] * 0.86, 0, 1.2)
    def to_model(self, p):
        p = np.atleast_2d(np.asarray(p, np.float64)); Q = (p - self.T - self.Hh) @ self.Rm + self.Hh   # снять выпрямление
        M = (Q - self.O) / self.Sx; return np.stack([M[:, 0], M[:, 2], -M[:, 1]], -1)
    def sdf(self, p):
        M = self.to_model(p); idx = ((M - self.lo) / self.step).T
        d = map_coordinates(self.D, idx, order=1, mode='nearest').astype(np.float64)
        out = np.linalg.norm(np.maximum(self.lo - M, 0) + np.maximum(M - self.hi, 0), axis=-1)   # за пределами сетки — расстояние до её края
        return ((d + out) * self.Sx).astype(F)
    def to_img(self, M):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw); X = M[:, 0] * cy + M[:, 2] * sy; Z = -M[:, 0] * sy + M[:, 2] * cy
        return X * self.s_img + self.dx, -M[:, 1] * self.s_img + self.dy, Z
    def color(self, p, tol=0.03):
        """-> (rgb альбедо с обложки, видимость 0..1)"""
        u, v, Z = self.to_img(self.to_model(p)); W = self.img.shape[1]
        zu = np.clip((u / 2).astype(int), 0, W // 2 - 1); zv = np.clip((v / 2).astype(int), 0, W // 2 - 1)
        zmax = np.maximum.reduce([self.zb[np.clip(zv + a, 0, W // 2 - 1), np.clip(zu + b, 0, W // 2 - 1)] for a in (-1, 0, 1) for b in (-1, 0, 1)])
        vis = np.clip(1 - (zmax - Z - tol) / tol, 0, 1) * ((u > 0) & (u < W - 1) & (v > 0) & (v < W - 1))
        rgb = np.stack([map_coordinates(self.alb[..., c], np.stack([v, u]), order=1, mode='nearest') for c in range(3)], -1)
        vis = vis * map_coordinates(self.mask, np.stack([v, u]), order=1, mode='constant', cval=0.0)
        return rgb.astype(F), vis.astype(F)

class Grid:
    """Поле на сетке в осях героя (метры): трилинейное чтение, снаружи — расстояние до края."""
    def __init__(self, D, lo, step): self.D = D.astype(np.float32); self.lo = np.asarray(lo, np.float64); self.step = float(step); self.hi = self.lo + (np.array(D.shape) - 1) * self.step
    def __call__(self, p):
        p = np.atleast_2d(np.asarray(p, np.float64)); idx = ((p - self.lo) / self.step).T
        d = map_coordinates(self.D, idx, order=1, mode='nearest').astype(np.float64)
        return (d + np.linalg.norm(np.maximum(self.lo - p, 0) + np.maximum(p - self.hi, 0), axis=-1)).astype(F)
def bake(fn, lo, hi, step, chunk=600000):
    lo = np.asarray(lo, np.float64); n = [int(math.ceil((hi[j] - lo[j]) / step)) + 1 for j in range(3)]
    g = [lo[j] + np.arange(n[j]) * step for j in range(3)]; P = np.stack(np.meshgrid(*g, indexing='ij'), -1).reshape(-1, 3)
    out = np.empty(len(P), np.float32)
    for i in range(0, len(P), chunk): out[i:i + chunk] = fn(P[i:i + chunk])
    return out.reshape(n), g
def ray_front(fn, x, z, y0=-0.45, tmax=0.7):
    """точка поверхности лица: луч из-спереди (−y) вдоль +y в точке (x, z)"""
    x = np.atleast_1d(x).astype(np.float64); z = np.atleast_1d(z).astype(np.float64); t = np.zeros(len(x)); done = np.zeros(len(x), bool)
    for _ in range(300):
        d = fn(np.stack([x, y0 + t, z], -1)).astype(np.float64); done |= (d < 0.0003) | (t > tmax)
        t = np.where(done, t, t + np.maximum(d, 0.0004) * 0.9)
        if done.all(): break
    return np.stack([x, y0 + t, z], -1), t <= tmax
def quad_fit(P):
    A = np.c_[np.ones(len(P)), P[:, 0], P[:, 2], P[:, 0] ** 2, P[:, 0] * P[:, 2], P[:, 2] ** 2]; q, *_ = np.linalg.lstsq(A, P[:, 1], rcond=None); return q
def quad_y(q, x, z): return q[0] + q[1] * x + q[2] * z + q[3] * x * x + q[4] * x * z + q[5] * z * z
