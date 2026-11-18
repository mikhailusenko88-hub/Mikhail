# Голова героя из 3D-модели, построенной нейросетью по обложке (ветка geroi3d): поле расстояний, место глаз, носа, рта и цвет с обложки.
# python3 mesh2hero.py <имя> — читает out/<имя>_h3d.ply, align_<имя>.json, in/<имя>.png, разметку обложки; пишет meshes/<имя>.npz
# Оси модели: x вправо, y вверх, z вперёд (к зрителю). Оси героя: x вправо, y назад, z вверх (метры).
import sys, os, json, math, numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import map_coordinates
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from plyview import read_ply
name = sys.argv[1]; G3 = os.environ.get('G3D', '/home/claude/g3d')   # клон ветки geroi3d (модели out/<имя>_h3d.ply и картинки in/<имя>.png); HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'meshes', 'cfg.json')))[name]
V, Fc = read_ply('%s/out/%s_h3d.ply' % (G3, name)); V = V.astype(np.float64)
AL = json.load(open(os.path.join(HERE, 'meshes', 'align_%s.json' % name))); yaw, s_img, dx, dy = AL['yaw'], AL['s'], AL['dx'], AL['dy']
IMG = np.asarray(Image.open('%s/in/%s.png' % (G3, name)).convert('RGB')).astype(np.float32) / 255
cy_, sy_ = math.cos(yaw), math.sin(yaw)
def to_img(P):   # модель -> пиксель входной картинки и глубина (больше — ближе к зрителю)
    X = P[:, 0] * cy_ + P[:, 2] * sy_; Z = -P[:, 0] * sy_ + P[:, 2] * cy_
    return np.stack([X * s_img + dx, -P[:, 1] * s_img + dy], -1), Z
def from_img(u, v, Z):
    X = (u - dx) / s_img; Y = -(v - dy) / s_img; return np.array([X * cy_ - Z * sy_, Y, X * sy_ + Z * cy_])
# 1) поле расстояний модели: точки поверхности с нормалями -> ближайшая точка, знак по нормали
A, B, C = V[Fc[:, 0]], V[Fc[:, 1]], V[Fc[:, 2]]; Nf = np.cross(B - A, C - A); area = np.linalg.norm(Nf, axis=-1); Nf /= area[:, None] + 1e-12
rng = np.random.default_rng(0); k = rng.choice(len(Fc), 400000, p=area / area.sum()); r1 = np.sqrt(rng.random(len(k))); r2 = rng.random(len(k))
S_pts = A[k] * (1 - r1)[:, None] + B[k] * (r1 * (1 - r2))[:, None] + C[k] * (r1 * r2)[:, None]; S_n = Nf[k]
tree = cKDTree(S_pts)
def sdf(P):
    d, i = tree.query(P, k=4); w = 1 / (d + 1e-6); n = (S_n[i] * w[..., None]).sum(1); q = (S_pts[i] * w[..., None]).sum(1) / w.sum(1)[:, None]
    nn = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9); pl = np.sum((P - q) * nn, -1)
    sg = np.sign(pl); sg[sg == 0] = 1
    dd = np.where(d[:, 0] < 0.012, np.abs(pl), d[:, 0])          # у самой поверхности — расстояние до касательной плоскости (гладко, без «рябизны» точек)
    return dd * sg
# 2) что считать головой: вырезаем по разметке в кадре обложки (шея, комок шарфа)
hc_u, hc_v, hr_px = CFG['head_circle']; neck_v = CFG['neck_v']
HC = None
Pi, Zi = to_img(V); inhead = (np.hypot(Pi[:, 0] - hc_u, Pi[:, 1] - hc_v) < hr_px * 0.8)
HC = np.array([np.median(V[inhead, 0]), np.median(V[inhead, 1]), np.median(V[inhead, 2])])
HC_img, _ = to_img(HC[None]); print('центр головы (модель)', HC.round(3), 'в кадре', HC_img.round(0))
def keep(P):   # < 0 — внутри «головы с ушами»
    Pi, _ = to_img(P); d = (Pi[:, 1] - neck_v) / s_img   # ниже шеи — прочь
    for (u0, v0, u1, v1) in CFG.get('cuts', []):            # прямые разрезы в кадре: убрать всё по правую руку от направления (u0,v0)->(u1,v1)
        t = np.array([u1 - u0, v1 - v0], float); t /= np.linalg.norm(t); nrm_ = np.array([-t[1], t[0]])
        d = np.maximum(d, ((Pi - [u0, v0]) @ nrm_) / s_img)
    return d
# 3) сетка поля в рамке головы
lo = V.min(0) - 0.05; hi = V.max(0) + 0.05; Pi_all, _ = to_img(V); sel = keep(V) < 0.02
lo = V[sel].min(0) - 0.06; hi = V[sel].max(0) + 0.06; step = float(CFG.get('step', 0.012))
nx, ny, nz = [int(math.ceil((hi[j] - lo[j]) / step)) + 1 for j in range(3)]
gx, gy, gz = [lo[j] + np.arange(n) * step for j, n in enumerate((nx, ny, nz))]
GP = np.stack(np.meshgrid(gx, gy, gz, indexing='ij'), -1).reshape(-1, 3)
D = np.maximum(sdf(GP), keep(GP)).reshape(nx, ny, nz).astype(np.float32)
print('сетка', D.shape, 'шаг', step, 'внутри', int((D < 0).sum()))
# 4) масштаб и место в герое
Sx = float(CFG['head_width_m']) / (CFG['head_width_px'] / s_img)          # метров на единицу модели
Hh = np.array(CFG['H'], float)
def m2h(P): P = np.atleast_2d(P); return np.stack([P[:, 0], -P[:, 2], P[:, 1]], -1) * Sx + (Hh - np.array([HC[0], -HC[2], HC[1]]) * Sx)
def h2m(Q): Q = np.atleast_2d(Q); M = (Q - (Hh - np.array([HC[0], -HC[2], HC[1]]) * Sx)) / Sx; return np.stack([M[:, 0], M[:, 2], -M[:, 1]], -1)
# 5) глаза: луч из кадра обложки в точку разметки -> поверхность; сфера по точкам модели вокруг
def hit_img(u, v):
    Z = 2.0
    for _ in range(200):
        P = from_img(u, v, Z)[None]; d = float(np.maximum(sdf(P), -9)[0])
        if d < 0.002: break
        Z -= max(d, 0.002) * 0.9
    return from_img(u, v, Z)
def fit_sphere(P):
    Aq = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1); x, *_ = np.linalg.lstsq(Aq, b, rcond=None); c = x[:3]; return c, math.sqrt(max(x[3] + c @ c, 1e-9))
eyes = []
for (u, v, w) in CFG['eyes_img']:
    Hp = hit_img(u, v); r0 = w / 2 / s_img
    eyes.append((m2h(Hp)[0], r0 * Sx)); print('глаз: точка на поверхности (герой)', m2h(Hp)[0].round(4), 'видимая полуширина %.4f м' % (r0 * Sx))   # точка, куда смотрит центр глаза обложки (сфера по соседям врала)
nose = m2h(hit_img(*CFG['nose_img']))[0]; lip = m2h(hit_img(*CFG['lip_img']))[0]
# 5б) выпрямить голову: линия глаз — по x (без крена и поворота), «вверх» — как на обложке (камера на уровне глаз); середина глаз — в точку EYE_MID
eL, eR = sorted([e[0] for e in eyes], key=lambda q: q[0]); mid = (eL + eR) / 2
ex = (eR - eL) / np.linalg.norm(eR - eL); fw = np.cross(ex, [0, 0, 1.0]); fw /= np.linalg.norm(fw); up = np.cross(fw, ex)
Rm = np.stack([ex, -fw, up])          # строки: куда идут оси героя x, y, z
T = np.array(CFG.get('eye_mid', [0.0, -0.145, 0.468])) - ((mid - Hh) @ Rm.T + Hh)
def fix(Q): Q = np.atleast_2d(Q); return (Q - Hh) @ Rm.T + Hh + T
eyes = [(fix(e[0])[0], e[1]) for e in eyes]; nose = fix(nose)[0]; lip = fix(lip)[0]
print('после выпрямления: глаза', [e[0].round(4) for e in eyes], 'нос', nose.round(4), 'рот', lip.round(4))
print('нос', nose.round(4), 'рот', lip.round(4))
# 6) глубина кадра обложки — чтобы красить только видимое с обложки
Wi = IMG.shape[1]; Pi, Zi = to_img(S_pts); zb = np.full((Wi // 2, Wi // 2), -9.0, np.float32)
ui = np.clip((Pi[:, 0] / 2).astype(int), 0, Wi // 2 - 1); vi = np.clip((Pi[:, 1] / 2).astype(int), 0, Wi // 2 - 1); np.maximum.at(zb, (vi, ui), Zi.astype(np.float32))
np.savez_compressed(os.path.join(HERE, 'meshes', '%s.npz' % name), D=D, lo=lo, step=step, Sx=Sx, HC=HC, H=Hh, yaw=yaw, s_img=s_img, dx=dx, dy=dy,
                    zb=zb, img=(IMG * 255).astype(np.uint8), Rm=Rm, T=T, eyes=np.array([np.r_[e[0], e[1]] for e in eyes]), nose=nose, lip=lip)
print('записано meshes/%s.npz' % name)
