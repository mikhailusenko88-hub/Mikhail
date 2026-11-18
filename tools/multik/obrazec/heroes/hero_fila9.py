# Филя, лепка 9 «из обложки» (менеджер, 18.11.2026): голова с ушами — 3D-модель нейросети по обложке 26, сделанная заново
# (ветка geroi3d-m: чистая вырезка «бюст», жёсткая маска, turbo, сетка 256 — модель fila26b_s1), всё остальное — лепки 7 («да» Михаила 13:04):
# глаза, носик-бусинка, рот, усы, мех, цвет (белый без налёта с обложки), тело, ручки (отведены от туловища), шарф.
# Перенос головы — как в hero_fila3d.py: поле расстояний модели (mesh2hero.py -> meshes/fila26b.npz), симметрия, «заплатки» на глазницы и рот модели.
# Экспорт: MOD=fila9 OUT=<папка> python3 hero_export.py fila
import os, math
from hero_fila7 import *
from hero_fila7 import Fila7
from hero_fila import Fila
from mesh_head import MeshHead

class Fila9(Fila7):
    NAME = 'fila'
    SRC = os.environ.get('FILA_SRC', 'fila26b')
    MH = MeshHead(SRC)
    NEAR = 1
    FORM = dict(Fila.FORM, C=V(0, -0.004, 0.47))
    EYE_OUT = 0.3
    EAR_Z = 0.56
    MUZ_R = 0.05
    HULL = None
    EAR_GAP = 0.016; EAR_SIDE = 1
    BAKE = dict(lo=(-0.29, -0.28, 0.29), hi=(0.29, 0.22, 0.86), step=0.0026, smooth=1.6, smooth_top=5.0)
    EAR_OPEN = 0.024
    HC_M = (0.0, 0.0, 0.47); HC_T = (0.0, 0.0, 0.47); KM = (1.0, 1.0, 1.0)            # растяжка модели (у лепки 7 K — размер мордочки)
    BOX = dict(Fila7.BOX, head=((-0.29, -0.28, 0.3), (0.29, 0.22, 0.98)))
    def p2m(self, p): return np.asarray(self.HC_M) + (np.atleast_2d(np.asarray(p, np.float64)) - np.asarray(self.HC_T)) / np.asarray(self.KM)
    def m2p(self, q): return np.asarray(self.HC_T) + (np.atleast_2d(np.asarray(q, np.float64)) - np.asarray(self.HC_M)) * np.asarray(self.KM)
    def base_sdf(self, p):
        p = self.p2m(p); return self.MH.sdf(p).astype(np.float64) * min(self.KM)
    def sym_sdf(self, p):                                                                 # голова — среднее левой и правой половин модели
        p = np.atleast_2d(np.asarray(p, np.float64)); pm = p * np.array([-1.0, 1, 1]); return 0.5 * (self.base_sdf(p) + self.base_sdf(pm))
    def bake_head(self):
        import hashlib, json as _j
        from mesh_head import bake, Grid, ray_front, quad_fit, quad_y
        from scipy.ndimage import binary_fill_holes, gaussian_filter, binary_opening, distance_transform_edt
        key = hashlib.md5(_j.dumps([self.HC_M, self.HC_T, self.KM, self.SRC, self.EAR_SIDE, self.EAR_GAP, self.PATCH, self.BAKE, self.EAR_Z, 'f9-3', self.EAR_OPEN]).encode()).hexdigest()[:10]
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meshes', self.SRC + '_bake9.npz')
        if os.path.exists(fpath):
            z = np.load(fpath)
            if str(z['key']) == key: self.G = Grid(z['D'], z['lo'], float(z['step'])); return
        B = self.BAKE; D1, g = bake(self.sym_sdf, B['lo'], B['hi'], B['step']); G1 = Grid(D1, B['lo'], B['step'])
        D = D1.astype(np.float64); X, Y, Z = np.meshgrid(*g, indexing='ij')
        for pc in self.PATCH:                                                              # «заплатки»: глазницы и рот модели — гладкая поверхность по краю
            for sg in ((-1, 1) if pc['mir'] else (1,)):
                cx, cz = sg * pc['x'], pc['z']; a = np.linspace(0, 2 * math.pi, 40, endpoint=False); ring = []
                for k in (1.12, 1.3, 1.5):
                    S, ok = ray_front(G1, cx + pc['rx'] * k * np.cos(a), cz + pc['rz'] * k * np.sin(a)); ring.append(S[ok])
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
        R_ = self.EAR_OPEN / B['step']; er = distance_transform_edt(solid) > R_; big = distance_transform_edt(~er) <= R_ + 0.5   # уши модели (тоньше 2·EAR_OPEN) — прочь; уши — лепки 7
        op = np.where(Z > self.EAR_Z - 0.03, op & big, op)
        sdo = (distance_transform_edt(~op) - distance_transform_edt(op)) * B['step']; D = np.maximum(D, sdo - 1.5 * B['step'])
        Ds = gaussian_filter(D, B['smooth']); Dt = gaussian_filter(D, B['smooth_top'])            # макушка круглее: выше лба — сильнее сглажено (там были уши модели)
        wt = np.clip((Z - (self.EAR_Z - 0.03)) / 0.06, 0, 1); wt = wt * wt * (3 - 2 * wt); D = (Ds * (1 - wt) + Dt * wt).astype(np.float32)
        np.savez_compressed(fpath, D=D, lo=np.array(B['lo']), step=B['step'], key=key)
        self.G = Grid(D, B['lo'], B['step'])
    def head_form(self, p): return self.G(p)
    def surf(self, yaw, pitch):
        u = self._dir(yaw, pitch); C = self.FORM['C']; o = C + u * 0.4; t = 0.0
        for _ in range(200):
            d = float(self.head_form((o - u * t)[None])[0])
            if d < 0.0003: break
            t += max(d, 0.0004) * 0.9
        return o - u * t, u
    def place_face(self):
        self.bake_head(); Fila.place_face(self); cls = type(self)
        tops = []
        for sg in (-1, 1):                                                                 # макушка над местом уха: луч сверху
            best = None
            for y in np.linspace(-0.12, 0.08, 21):
                o = V(sg * self.EAR_X, y, 0.95); t = 0.0
                for _ in range(300):
                    d = float(self.head_form((o - V(0, 0, t))[None])[0])
                    if d < 0.0004 or t > 0.6: break
                    t += max(d, 0.0005) * 0.9
                z = 0.95 - t
                if best is None or z > best[1]: best = (y, z)
            tops.append(best)
        y0 = float(np.mean([b[0] for b in tops])); z0 = float(np.mean([b[1] for b in tops]))
        cls.EAR_C = [V(sg * self.EAR_X, y0 + 0.02, z0 + self.EAR_UP) for sg in (-1, 1)]
        cls.NOSE_C = (self.NOSE_C + V(0, -self.NOSE_FWD, 0)).astype(F)                  # носик чуть вперёд: лицо модели плоское, носик лепки 7 не прятать
        n = self.NOSE_C                                                                    # мордочка лепки 7 — к носу модели (те же отступы от носика)
        cls.SN_A = n + V(0, 0.114, 0.01); cls.SN_B = n + V(0, 0.016, -0.006)
        cls.PADS = [n + V(sg * 0.019, 0.035, -0.021) for sg in (-1, 1)]; cls.CHIN = n + V(0, 0.057, -0.042)
        cls.MOUTHS = {'a': (n + V(0, 0.036, -0.038), V(0.018, 0.023, 0.014)), 'o': (n + V(0, 0.036, -0.037), V(0.0104, 0.023, 0.0115))}
        cls.TONGUE = (n + V(0, 0.041, -0.045), V(0.009, 0.014, 0.0046)); cls.LIP_Z = float(n[2] - 0.032)
    EAR_X = 0.075; EAR_UP = 0.07; NOSE_FWD = 0.007
    def head_sd_only(self, p): return self.head_form(p)                                    # голова — модель обложки; мордочка, уши, тело — лепки 7

_m2p = lambda q: np.asarray(Fila9.HC_T) + (np.asarray(q) - np.asarray(Fila9.HC_M)) * np.asarray(Fila9.KM)
_e = _m2p(Fila9.MH.eyes[1, :3]); _n = _m2p(Fila9.MH.nose); _l = _m2p(Fila9.MH.lip)
Fila9.EYE_XZ = (float(abs(_e[0])), float(_e[2])); Fila9.NOSE_Z = float(_n[2]); Fila9.LIP_Zf = float(_l[2])
Fila9.RE = float(np.clip(Fila9.MH.eyes[:, 3].max() / (0.88 * 0.95), 0.04, 0.055))
Fila9.PATCH = [dict(x=float(abs(_e[0])), z=float(_e[2]), rx=0.05, rz=0.052, mir=True),
               dict(x=0.0, z=float(_l[2]) - 0.004, rx=0.04, rz=0.026, mir=False)]
HERO = Fila9(); HERO.place_face()
