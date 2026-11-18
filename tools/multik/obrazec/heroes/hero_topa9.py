# Топа, лепка 9 «из обложки» (менеджер, 18.11.2026): голова — 3D-модель нейросети по обложке 23, сделанная заново
# (ветка geroi3d-m: чистая вырезка «бюст» без лапы у подбородка, жёсткая маска, turbo, сетка 256 — модель topa23b_s2).
# Всё остальное — лепки 7 («да» Михаила 13:04): глаза с большой радужкой, морда с переносицей и брылями, крупный тёмный нос,
# круглые ушки, рот, мех и цвет, тело, шарф. Ушки и морда стоят по месту на голове модели.
# Перенос головы — как в hero_fila9.py: поле расстояний модели (mesh2hero.py -> meshes/topa23b.npz), симметрия, «заплатки» на глазницы и рот.
# Экспорт: MOD=topa9 OUT=<папка> python3 hero_export.py topa
import os, math
from hero_topa7 import *
from hero_topa7 import Topa7
from mesh_head import MeshHead

class Topa9(Topa7):
    NAME = 'topa'
    SRC = os.environ.get('TOPA_SRC', 'topa23b')
    MH = MeshHead(SRC)
    EAR_Z = 0.78; EAR_OPEN = 0.03
    BAKE = dict(lo=(-0.33, -0.36, 0.45), hi=(0.33, 0.25, 1.0), step=0.0028, smooth=1.6, smooth_top=4.0)
    HC_M = (0.0, 0.0, 0.69); HC_T = (0.0, 0.0, 0.69); KM = (1.0, 1.0, 1.0)
    BOX = dict(Topa7.BOX, head=((-0.33, -0.36, 0.45), (0.33, 0.25, 1.0)))
    EYE_OUT = 0.3
    EAR_X = 0.14; EAR_UP = 0.025; NOSE_FWD = 0.014
    FORM = dict(C=V(0, -0.02, 0.69))
    def p2m(self, p): return np.asarray(self.HC_M) + (np.atleast_2d(np.asarray(p, np.float64)) - np.asarray(self.HC_T)) / np.asarray(self.KM)
    def base_sdf(self, p): return self.MH.sdf(self.p2m(p)).astype(np.float64) * min(self.KM)
    def sym_sdf(self, p):
        p = np.atleast_2d(np.asarray(p, np.float64)); pm = p * np.array([-1.0, 1, 1]); return 0.5 * (self.base_sdf(p) + self.base_sdf(pm))
    def bake_head(self):
        import hashlib, json as _j
        from mesh_head import bake, Grid, ray_front, quad_fit, quad_y
        from scipy.ndimage import binary_fill_holes, gaussian_filter, binary_opening, distance_transform_edt
        key = hashlib.md5(_j.dumps([self.HC_M, self.HC_T, self.KM, self.SRC, self.PATCH, self.BAKE, self.EAR_Z, self.EAR_OPEN, 't9-1']).encode()).hexdigest()[:10]
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meshes', self.SRC + '_bake9.npz')
        if os.path.exists(fpath):
            z = np.load(fpath)
            if str(z['key']) == key: self.G = Grid(z['D'], z['lo'], float(z['step'])); return
        B = self.BAKE; D1, g = bake(self.sym_sdf, B['lo'], B['hi'], B['step']); G1 = Grid(D1, B['lo'], B['step'])
        D = D1.astype(np.float64); X, Y, Z = np.meshgrid(*g, indexing='ij')
        for pc in self.PATCH:
            for sg in ((-1, 1) if pc['mir'] else (1,)):
                cx, cz = sg * pc['x'], pc['z']; a = np.linspace(0, 2 * math.pi, 40, endpoint=False); ring = []
                for k in (1.12, 1.3, 1.5):
                    S, ok = ray_front(G1, cx + pc['rx'] * k * np.cos(a), cz + pc['rz'] * k * np.sin(a), y0=-0.55, tmax=0.9); ring.append(S[ok])
                Rr = np.concatenate(ring); q = quad_fit(Rr)
                for _ in range(3):
                    res = Rr[:, 1] - quad_y(q, Rr[:, 0], Rr[:, 2]); Rr = Rr[np.abs(res) < max(0.006, 2.0 * np.median(np.abs(res)))]; q = quad_fit(Rr)
                ys = quad_y(q, X, Z); rr = np.sqrt(((X - cx) / pc['rx']) ** 2 + ((Z - cz) / pc['rz']) ** 2)
                wz = np.clip((1.0 - rr) / 0.3, 0, 1); wz = wz * wz * (3 - 2 * wz)
                wd = np.clip(1 - (Y - ys - 0.03) / 0.04, 0, 1); w = wz * wd
                D = D * (1 - w) + (ys - Y) * 0.95 * w
        solid = binary_fill_holes(D < 0); D = np.where(solid & (D >= 0), -B['step'], D)
        rr = 3; b = np.linalg.norm(np.mgrid[-rr:rr + 1, -rr:rr + 1, -rr:rr + 1], axis=0) <= rr
        op = binary_opening(solid, b)
        R_ = self.EAR_OPEN / B['step']; er = distance_transform_edt(solid) > R_; big = distance_transform_edt(~er) <= R_ + 0.5   # ушки модели — прочь (ушки — лепки 7)
        op = np.where(Z > self.EAR_Z - 0.03, op & big, op)
        sdo = (distance_transform_edt(~op) - distance_transform_edt(op)) * B['step']; D = np.maximum(D, sdo - 1.5 * B['step'])
        Ds = gaussian_filter(D, B['smooth']); Dt = gaussian_filter(D, B['smooth_top'])
        wt = np.clip((Z - (self.EAR_Z - 0.03)) / 0.06, 0, 1); wt = wt * wt * (3 - 2 * wt); D = (Ds * (1 - wt) + Dt * wt).astype(np.float32)
        np.savez_compressed(fpath, D=D, lo=np.array(B['lo']), step=B['step'], key=key)
        self.G = Grid(D, B['lo'], B['step'])
    def head_form(self, p): return self.G(p)
    def ray_y(self, x, z, y0=-0.6):
        o = V(x, y0, z); t = 0.0
        for _ in range(300):
            d = float(self.head_form((o + V(0, t, 0))[None])[0])
            if d < 0.0003 or t > 1.0: break
            t += max(d, 0.0004) * 0.9
        return o + V(0, t, 0)
    def grad(self, S, e=0.0008):
        g = V(*[float(self.head_form((S + dv)[None])[0] - self.head_form((S - dv)[None])[0]) for dv in (V(e, 0, 0), V(0, e, 0), V(0, 0, e))]); return g / np.linalg.norm(g)
    def place_face(self):
        self.bake_head(); cls = type(self)
        ex, ez = self.EYE_XZ; eyes = []
        for sg in (-1, 1):
            S = self.ray_y(sg * ex, ez); u = self.grad(S); c0 = S - u * self.RE * (1.0 - self.EYE_OUT) * float(self.EYE_S[1]); c0[0] = sg * ex; c0[2] = ez; eyes.append(c0.astype(F))
        cls.EYES = eyes
        S = self.ray_y(0.0, self.NOSE_Z); n = (S + V(0, -self.NOSE_FWD, 0)).astype(F); cls.NOSE_C = n
        cls.SN_A = n + V(0, 0.143, 0.002); cls.SN_B = n + V(0, 0.033, -0.019)
        cls.BRIDGE = (n + V(0, 0.103, 0.03), n + V(0, 0.028, 0.008))
        cls.JOWL = [n + V(sg * 0.03, 0.037, -0.037) for sg in (-1, 1)]; cls.CHIN_T = n + V(0, 0.065, -0.068)
        cls.MOUTHS = {'a': (n + V(0, 0.027, -0.045), V(0.036, 0.036, 0.022)), 'o': (n + V(0, 0.026, -0.045), V(0.021, 0.036, 0.022))}
        cls.TONGUE = (n + V(0, 0.056, -0.061), V(0.02, 0.027, 0.006)); cls.LIP_Z = float(n[2] - 0.04)
        cls.BLUSH = [e + V(np.sign(e[0]) * 0.047, 0.011, -0.06) for e in eyes]
        cls.EYE_AIM = V(0, -1.6, float(ez) + 0.015)
        tops = []
        for sg in (-1, 1):
            best = None
            for y in np.linspace(-0.14, 0.1, 25):
                o = V(sg * self.EAR_X, y, 1.1); t = 0.0
                for _ in range(300):
                    d = float(self.head_form((o - V(0, 0, t))[None])[0])
                    if d < 0.0004 or t > 0.7: break
                    t += max(d, 0.0005) * 0.9
                z = 1.1 - t
                if best is None or z > best[1]: best = (y, z)
            tops.append(best)
        y0 = float(np.mean([b[0] for b in tops])); z0 = float(np.mean([b[1] for b in tops]))
        cls.EAR_C = [V(sg * self.EAR_X, y0, z0 + self.EAR_UP) for sg in (-1, 1)]
    def parts(self, p):
        d = Topa7.parts(self, p)
        d['head'] = self.head_form(p)                                                      # голова — модель обложки
        m = sd_rcone(p, self.SN_A, self.SN_B, 0.075, 0.05)                                 # морда лепки 7 — по месту носа модели
        m = smin(m, sd_cap(p, self.BRIDGE[0], self.BRIDGE[1], 0.026), 0.03)
        for c in self.JOWL: m = smin(m, sd_ell(p, c, V(0.036, 0.042, 0.03)), 0.026)
        m = smin(m, sd_ell(p, self.CHIN_T, V(0.032, 0.048, 0.02)), 0.026)
        d['muzzle'] = m
        return d

_m2p = lambda q: np.asarray(Topa9.HC_T) + (np.asarray(q) - np.asarray(Topa9.HC_M)) * np.asarray(Topa9.KM)
_e = _m2p(Topa9.MH.eyes[0, :3]); _n = _m2p(Topa9.MH.nose); _l = _m2p(Topa9.MH.lip)
Topa9.EYE_XZ = (float(abs(_e[0])), float(_e[2])); Topa9.NOSE_Z = float(_n[2]); Topa9.LIP_Zf = float(_l[2])
Topa9.RE = float(np.clip(Topa9.MH.eyes[:, 3].max() / (0.9 * 0.95), 0.042, 0.058))
Topa9.PATCH = [dict(x=float(abs(_e[0])), z=float(_e[2]), rx=0.055, rz=0.055, mir=True),
               dict(x=0.0, z=float(_l[2]), rx=0.05, rz=0.032, mir=False)]
HERO = Topa9(); HERO.place_face()
