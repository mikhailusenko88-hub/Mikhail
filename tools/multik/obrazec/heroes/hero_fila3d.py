# Филя «из обложки» (18.11.2026): голова с ушами — 3D-модель, которую нейросеть (Hunyuan3D-2mini) построила по обложке серии 26
# (ветка geroi3d, mesh2hero.py -> meshes/fila26.npz). Тело, лапы, шарф, хвост, скелет — прежние (hero_fila.py).
# Цвет головы — с обложки (нарисованный свет снят, глаза/брови/нос/рот стёрты: у движка свои, живые); мех и глаза — движка.
# Экспорт: MOD=fila3d OUT=<папка> python3 hero_export.py fila
import os
from hero_fila import *
from hero_fila import Fila
from mesh_head import MeshHead

class Fila3D(Fila):
    NAME = 'fila'
    SRC = os.environ.get('FILA_SRC', 'fila26')
    MH = MeshHead(SRC)
    NEAR = -1 if SRC == 'fila20' else 1                                                     # какая половина лица ближе к зрителю на обложке (с неё цвет и ухо)
    FORM = dict(Fila.FORM, C=V(0, -0.004, 0.47))
    EYE_XZ = (0.066, 0.469); RE = 0.046; EYE_S = V(0.94, 1.0, 1.12); EYE_OUT = 0.24; LID_OFF = 0.84  # видимая ширина глаза = 2·0,8·RE·0,94 ≈ 7,8 см, как на обложке          # глаза — по обложке 26: крупные, высокие овалы
    EYE_TILT = (2.0, -6.0); EYE_K = (0.886, 0.969)                                           # радужка ~0,58 видимой ширины, зрачок ~0,31 (обложка 26)
    IRIS = [(0.01, 0.012, 0.02), (0.06, 0.15, 0.34), (0.42, 0.64, 0.92)]                  # голубые, как на обложке 26
    BROW = {'up': 1.5, 'w': 0.72, 'tilt': 0.2, 'r': [0.0062, 0.003], 'col': (0.38, 0.27, 0.22)}
    NOSE_Z = 0.4254; LIP_Zf = 0.394
    EAR_Z = 0.605                                                                          # выше — уши (короткий мех), ниже — голова
    MUZ_R = 0.05
    K_MUZ = 0.0015; K_EAR = 0.0015
    BOX = dict(Fila.BOX, head=((-0.27, -0.26, 0.31), (0.27, 0.2, 0.92)))
    # голова «запекается» в сетку в осях героя (meshes/fila26_bake.npz):
    # 1) поле модели; убрать лапку у щеки и «пластины» плеч (оболочка головы + зона ушей)
    # 2) симметрия: голова — среднее левой и правой половин, уши — правое ухо (ближнее к зрителю на обложке) и его зеркало
    # 3) «заплатки»: глазницы модели и открытый рот — гладкая поверхность, натянутая по краю (глаза и рот у движка свои, живые)
    HULL = dict(c=(0.0, -0.02, 0.475), r=(0.165, 0.19, 0.175), ear_z=0.57)
    PAW_CUT = dict(x=0.085, y=0.0, z=(0.3, 0.462))
    EAR_GAP = 0.016
    PATCH = [dict(x=0.066, z=0.47, rx=0.05, rz=0.055, mir=True),
             dict(x=0.0, z=0.398, rx=0.05, rz=0.03, mir=False, fixed=(-0.128, -0.5, 6.0, 0.395))]   # рот закрыт: под носом — «мордочка», y = a + b·(z − z0) + c·x²
    BAKE = dict(lo=(-0.27, -0.26, 0.29), hi=(0.27, 0.2, 0.93), step=0.0026, smooth=0.8)
    HC_M = (0.0, 0.0, 0.47); HC_T = (0.0, 0.0, 0.47); K = (1.0, 1.0, 1.0)                  # растяжка модели по осям вокруг центра головы (HC_M — в осях модели, HC_T — в осях героя)
    def p2m(self, p): return np.asarray(self.HC_M) + (np.atleast_2d(np.asarray(p, np.float64)) - np.asarray(self.HC_T)) / np.asarray(self.K)
    def m2p(self, q): return np.asarray(self.HC_T) + (np.atleast_2d(np.asarray(q, np.float64)) - np.asarray(self.HC_M)) * np.asarray(self.K)
    def base_sdf(self, p):
        p = self.p2m(p); d = self.MH.sdf(p).astype(np.float64) * min(self.K)
        Hc = self.HULL
        if Hc is None: return d
        q = (p - Hc['c']) / Hc['r']; ell = (np.linalg.norm(q, axis=-1) - 1) * min(Hc['r'])
        earz = np.maximum(np.maximum(Hc['ear_z'] - p[:, 2], np.abs(p[:, 0]) - 0.25), np.abs(p[:, 1] + 0.0) - 0.16)
        d = np.maximum(d, np.minimum(ell, earz))
        return d
    def sym_sdf(self, p):
        p = np.atleast_2d(np.asarray(p, np.float64)); pm = p * np.array([-1.0, 1, 1]); a = self.base_sdf(p); b = self.base_sdf(pm)
        z = p[:, 2]; ez = self.EAR_Z; w = np.clip((z - (ez - 0.035)) / 0.045, 0, 1); w = w * w * (3 - 2 * w)
        c = np.where(p[:, 0] * self.EAR_SIDE > 0, a, b)
        P = self.PAW_CUT or dict(x=9.0, y=0.0, z=(0.3, 0.46)); ax_ = np.abs(p[:, 0])                                              # у правой щеки на обложке лежит лапка: там обе щёки — с левой стороны модели
        wp = np.clip((ax_ - P['x']) / 0.025, 0, 1) * np.clip((P['z'][1] - z) / 0.02, 0, 1) * np.clip((P['y'] - p[:, 1]) / 0.03, 0, 1)
        left = np.where(p[:, 0] > 0, b, a); avg = (1 - wp) * 0.5 * (a + b) + wp * left
        gap = np.maximum(np.abs(p[:, 0]) - self.EAR_GAP, (ez + 0.012) - z); c = np.maximum(c, -gap)
        return (1 - w) * avg + w * c
    def bake_head(self):
        import hashlib, json as _j
        from mesh_head import bake, Grid, ray_front, quad_fit, quad_y
        from scipy.ndimage import binary_fill_holes, gaussian_filter
        key = hashlib.md5(_j.dumps([self.HC_M, self.HC_T, self.K, self.SRC, self.EAR_SIDE, self.HULL, self.PAW_CUT, self.EAR_GAP, self.PATCH, self.BAKE, self.EAR_Z, 6]).encode()).hexdigest()[:10]
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meshes', self.SRC + '_bake.npz')
        if os.path.exists(fpath):
            z = np.load(fpath)
            if str(z['key']) == key: self.G = Grid(z['D'], z['lo'], float(z['step'])); self.PQ = list(z['pq']); return
        B = self.BAKE; D1, g = bake(self.sym_sdf, B['lo'], B['hi'], B['step']); G1 = Grid(D1, B['lo'], B['step'])
        D = D1.astype(np.float64); X, Y, Z = np.meshgrid(*g, indexing='ij'); pq = []
        for pc in self.PATCH:
            for sg in ((-1, 1) if pc['mir'] else (1,)):
                cx, cz = sg * pc['x'], pc['z']; a = np.linspace(0, 2 * math.pi, 40, endpoint=False); ring = []
                for k in (1.12, 1.3, 1.5):
                    S, ok = ray_front(G1, cx + pc['rx'] * k * np.cos(a), cz + pc['rz'] * k * np.sin(a)); ring.append(S[ok])
                R = np.concatenate(ring); q = quad_fit(R)
                for _ in range(3):                                                             # без точек, улетевших за подбородок или в бок головы
                    res = R[:, 1] - quad_y(q, R[:, 0], R[:, 2]); R = R[np.abs(res) < max(0.006, 2.0 * np.median(np.abs(res)))]; q = quad_fit(R)
                if 'fixed' in pc: fa, fb, fc, fz = pc['fixed']; q = np.array([fa - fb * fz, 0, fb, fc, 0, 0])
                pq.append(np.r_[cx, cz, pc['rx'], pc['rz'], q])
                ys = quad_y(q, X, Z); rr = np.sqrt(((X - cx) / pc['rx']) ** 2 + ((Z - cz) / pc['rz']) ** 2)
                wz = np.clip((1.0 - rr) / 0.3, 0, 1); wz = wz * wz * (3 - 2 * wz)
                wd = np.clip(1 - (Y - ys - 0.03) / 0.04, 0, 1); w = wz * wd
                D = D * (1 - w) + (ys - Y) * 0.95 * w
        solid = binary_fill_holes(D < 0); D = np.where(solid & (D >= 0), -B['step'], D)      # пустоты внутри головы (рот, глазницы) — сплошные
        from scipy.ndimage import binary_opening, distance_transform_edt                    # тонкие «пластины» и «полки» (тоньше ~1,5 см) ниже ушей — прочь
        rr = int(B.get('open', 3)); b = np.linalg.norm(np.mgrid[-rr:rr + 1, -rr:rr + 1, -rr:rr + 1], axis=0) <= rr
        op = np.where(Z < self.EAR_Z - 0.01, binary_opening(solid, b), solid)
        sdo = (distance_transform_edt(~op) - distance_transform_edt(op)) * B['step']; D = np.maximum(D, sdo - 1.5 * B['step'])
        D = gaussian_filter(D, B['smooth']).astype(np.float32)
        np.savez_compressed(fpath, D=D, lo=np.array(B['lo']), step=B['step'], key=key, pq=np.array(pq))
        self.G = Grid(D, B['lo'], B['step']); self.PQ = pq
    def hit_img(self, u, v):
        mh = self.MH; cy, sy = math.cos(mh.yaw), math.sin(mh.yaw); X = (u - mh.dx) / mh.s_img; Y = -(v - mh.dy) / mh.s_img
        Zs = np.linspace(2.0, -2.0, 1601); M = np.stack([X * cy - Zs * sy, np.full_like(Zs, Y), X * sy + Zs * cy], -1)
        Q = np.stack([M[:, 0], -M[:, 2], M[:, 1]], -1) * mh.Sx + mh.O; P = (Q - mh.Hh) @ mh.Rm.T + mh.Hh + mh.T
        d = mh.sdf(P); i = int(np.argmax(d < 0)) if (d < 0).any() else len(d) - 1; return self.m2p(P[max(i, 0)])[0].astype(F)
    def head_form(self, p): return self.G(p)
    def surf(self, yaw, pitch):
        u = self._dir(yaw, pitch); C = self.FORM['C']; o = C + u * 0.4; t = 0.0
        for _ in range(200):
            d = float(self.head_form((o - u * t)[None])[0])
            if d < 0.0003: break
            t += max(d, 0.0004) * 0.9
        return o - u * t, u
    def place_face(self):
        self.bake_head(); Fila.place_face(self)
    def ear_inner(self, p): return np.full(len(p), 9.0, F)
    def whiskers(self):   # усы — от щёк у уголков рта, наружу и чуть вниз (на обложке не пересекают глаза)
        out = []; z0 = float(self.NOSE_C[2]) - 0.022
        for sg in (-1, 1):
            for j, (dz, ang) in enumerate([(0.006, 0.02), (0.0, -0.12), (-0.006, -0.26)]):
                o = V(sg * (0.022 + 0.004 * j), -0.4, z0 + dz); r0 = self.hit(o, V(0, 1, 0))[0] + V(0, 0.0015, 0)
                dirn = nrm(V(sg * 1.0, 0.1, ang)); out.append(np.array([r0 + dirn * 0.1 * (k / 7) + V(0, 0.008 * (k / 7) ** 2, -0.01 * (k / 7) ** 2) for k in range(8)], F))
        return out
    def parts(self, p):
        d = {}
        t = sd_ell(p, V(0, 0.007, 0.228), V(0.08, 0.072, 0.118))
        t = smin(t, sd_ell(p, V(0, -0.014, 0.166), V(0.098, 0.09, 0.086)), 0.045)
        t = smin(t, sd_cap(p, V(0, 0, 0.3), self.NECK + V(0, -0.004, 0.034), 0.043), 0.04)
        d['torso'] = t
        D = self.head_form(p); e = p[:, 2] - self.EAR_Z; m = sd_sph(p, self.NOSE_C + V(0, 0.01, -0.015), self.MUZ_R)
        d['head'] = np.maximum(np.maximum(D, e), -m); d['muzzle'] = np.maximum(np.maximum(D, m), e); d['ear'] = np.maximum(D, -e)
        d['lid'] = self.lid(p)
        d['arm'] = np.minimum(self.arm_sd(p, 0), self.arm_sd(p, 1))
        d['leg'] = np.minimum(self.leg_sd(p, 0), self.leg_sd(p, 1))
        tl = None
        for i in range(len(self.TAIL) - 1):
            x = sd_rcone(p, self.TAIL[i], self.TAIL[i + 1], self.TAIL_R[i], self.TAIL_R[i + 1]); tl = x if tl is None else smin(tl, x, 0.01)
        d['tail'] = tl
        return d
    def colors(self, p, reg0, nor):
        skin, fur = Fila.colors(self, p, reg0, nor)
        hd = (reg0 == 1) | (reg0 == 2) | (reg0 == 3) | (reg0 == 4)
        if hd.any():
            ph = p[hd].copy(); ph[:, 0] = np.abs(ph[:, 0]) * self.NEAR; rgb, vis = self.MH.color(self.p2m(ph), tol=0.05); base = fur[hd]
            if not hasattr(self, '_ref'):                                                    # общий тёплый оттенок обложки (свет сцены) — снять: белый мех = наш белый
                al = self.MH.alb[self.MH.mask > 0.5]; sat = al.max(1) - al.min(1); self._ref = np.median(al[sat < np.percentile(sat, 40)], 0)
            white = V(0.74, 0.7, 0.64); rgb = np.clip(rgb / self._ref * white, 0, 1)
            col = rgb * vis[:, None] + base * (1 - vis[:, None])
            ph = p[hd]
            for B in self.BLUSH:                                                              # румянец на щёчках, как на обложке
                b = np.clip((1.0 - np.linalg.norm((ph - B) / V(0.036, 0.03, 0.026), axis=-1)) * 2.0, 0, 1)[:, None] * 0.45
                col = col * (1 - b) + V(0.86, 0.5, 0.52)[None] * b
            fur[hd] = col; skin[hd] = col * 0.92
        tint = V(1.06, 1.1, 1.16)                                                              # белый, а не бежевый: свет сцен тёплый, мех берём холоднее
        return np.clip(skin * tint, 0, 1).astype(F), np.clip(fur * tint, 0, 1).astype(F)

EAR_SIDE_DEFAULT = 1
Fila3D.EAR_SIDE = 1                                   # ухо, которое отражаем на обе стороны: +1 — правое (x > 0)
if Fila3D.SRC == 'fila20':                            # обложка 20: рот закрыт (улыбка), глаза янтарные, голова повёрнута вправо от зрителя
    Fila3D.IRIS = Fila.IRIS; Fila3D.RE = 0.046; Fila3D.EYE_S = V(0.94, 1.0, 1.06); Fila3D.EYE_OUT = 0.3
    Fila3D.BROW = {'up': 1.75, 'w': 0.8, 'tilt': 0.0, 'r': [0.0048, 0.0024], 'col': (0.36, 0.3, 0.28)}
    Fila3D.HC_M = (0.0, -0.05, 0.455); Fila3D.HC_T = (0.0, -0.004, 0.462); Fila3D.K = (1.2, 1.05, 1.0)   # голова шире (как «моти» на обложке), сидит над шеей
    Fila3D.HULL = dict(c=(0.0, -0.05, 0.46), r=(0.175, 0.17, 0.155), ear_z=0.57); Fila3D.PAW_CUT = None
    _m2p = lambda q: np.asarray(Fila3D.HC_T) + (np.asarray(q) - np.asarray(Fila3D.HC_M)) * np.asarray(Fila3D.K)
    _e = _m2p(Fila3D.MH.eyes[1, :3]); _n = _m2p(Fila3D.MH.nose); _l = _m2p(Fila3D.MH.lip)
    Fila3D.EYE_XZ = (float(abs(_e[0])), float(_e[2])); Fila3D.NOSE_Z = float(_n[2]); Fila3D.LIP_Zf = float(_l[2]) - 0.012
    Fila3D.PATCH = [dict(x=float(abs(_e[0])), z=float(_e[2]), rx=0.058, rz=0.056, mir=True)]
HERO = Fila3D(); HERO.place_face()
