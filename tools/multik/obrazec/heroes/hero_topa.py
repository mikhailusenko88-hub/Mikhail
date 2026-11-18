# Топа — бурый медвежонок с зелёным вязаным шарфом (рост до макушки ~0.84 м). Пухлый малыш: большая круглая голова, маленькие круглые
# уши, короткая светлая мордочка с крупным чёрным носом, тёмные глаза, румянец, светлый животик, толстые короткие лапы с пальцами
# и тёмными подушечками, хвостик-пуговка.
# Лепка 3 (17.11.2026): лицо прежнего Топы — огромные тёмные блестящие глаза, румянец, светлая мордочка с улыбкой, насыщенно-бурый мех, толстый шарф.
from hero_common import *

class Topa(FormHead, Hero):
    NAME = 'topa'
    def hit(self, o, dirn, tmax=0.4): return self.hit2(o, dirn, tmax)   # линии рта и усы — точно на поверхности
    H = V(0, 0.0, 0.69); HEAD_R = V(0.2, 0.185, 0.178)                          # круглая голова (обложки)
    RE = 0.0423; LID_OFF = 0.99; LID_K = 0.03; LID_NY = 0.12                     # глаза большие, но сидят в голове, взгляд спокойный и добрый
    EYES = [V(s * 0.075, -0.14, 0.684) for s in (-1, 1)]      # по сетке с обложек 22–23: лоб высокий, низ лица короткий      # над мордочкой, между глазами ~0,5 ширины глаза (обложки 18, 22, 26)
    IRIS = [(0.012, 0.006, 0.003), (0.07, 0.03, 0.012), (0.38, 0.18, 0.05)]      # медовые карие: сверху темнее, книзу светятся
    IRIS_STYLE = 1
    EYE_K = (0.833, 0.968)                                                          # большая радужка — без «испуга»                                                         # большая радужка и большой зрачок, белок виден по краям
    EYE_AIM = V(0, -1.6, 0.7); EYE_DIV = 0.18
    EYE_CENTER = (0.1, 0.3)                                                       # зрачок чуть ниже середины — веко касается радужки, взгляд мягкий
    EYE_S = V(1.0, 1.0, 1.017)                                                    # вытянутый вверх овал
    EYE_RING = (0.04, 0.02, 0.012); EYE_RING_TOP = True; EYE_RING_R = 1.07
    LID_SH = 0.45                                                                  # тень от верхнего века на глазу — взгляд мягче, глаз не «стеклянный»
    LID_LINE = {'r': (0.0014, 0.0032), 'col': (0.035, 0.018, 0.01), 'off': 1.06, 'flick': 0.12}   # тёмная линия ресниц по верхнему веку (как на обложках)
    BROW = {'up': 1.38, 'w': 0.5, 'r': [0.0058, 0.003], 'col': (0.13, 0.06, 0.025)}      # короткие густые бровки ближе к глазам
    SHOULD = [V(s * 0.128, -0.03, 0.44) for s in (-1, 1)]
    WRIST = [V(s * 0.186, -0.092, 0.292) for s in (-1, 1)]
    PAW = [V(s * 0.192, -0.106, 0.264) for s in (-1, 1)]
    HIP = [V(s * 0.092, 0.005, 0.15) for s in (-1, 1)]
    FOOT = [V(s * 0.1, -0.075, 0.036) for s in (-1, 1)]
    TAIL = [V(0, 0.135, 0.19), V(0, 0.165, 0.205), V(0, 0.18, 0.215)]
    TAIL_R = [0.036, 0.04, 0.032]
    NECK = V(0, -0.01, 0.495)
    SN_A = V(0, -0.11, 0.626); SN_B = V(0, -0.2, 0.618)
    NOSE_C = V(0, -0.262, 0.66)                                                  # на мордочке, а не внутри неё (иначе нос тонет в мехе)
    MOUTHS = {'a': (V(0, -0.204, 0.586), V(0.038, 0.04, 0.024)), 'o': (V(0, -0.206, 0.587), V(0.022, 0.04, 0.024))}
    TONGUE = (V(0, -0.18, 0.57), V(0.021, 0.03, 0.006))
    PIV = {'head': V(0, -0.01, 0.505), 'armL': SHOULD[0], 'armR': SHOULD[1], 'tail': TAIL[0]}
    BOX = {'head': ((-0.3, -0.335, 0.47), (0.3, 0.23, 0.935)), 'body': ((-0.24, -0.22, -0.01), (0.24, 0.22, 0.59)),
           'armL': ((-0.28, -0.19, 0.19), (-0.05, 0.07, 0.52)), 'armR': ((0.05, -0.19, 0.19), (0.28, 0.07, 0.52)), 'tail': ((-0.07, 0.07, 0.13), (0.07, 0.24, 0.27)),
           'feet': ((-0.2, -0.2, -0.01), (0.2, 0.08, 0.1))}
    NECK_PLUG = (V(0, -0.01, 0.475), V(0, -0.012, 0.565), 0.075)
    K_MUZ = 0.045; K_EAR = 0.035; K_TORSO = 0.075

    EAR_C = [V(s * 0.165, 0.012, 0.818) for s in (-1, 1)]
    def ear_sd(self, p, i, inner=False):
        s = 1 if i else -1
        q = rotz(p - self.EAR_C[i], -s * 0.3); q = rotx(q, 0.1)
        if inner: return sd_ell(q, V(0, -0.019, -0.004), V(0.05, 0.012, 0.047))
        return sd_ell(q, V(0, 0, 0), V(0.08, 0.032, 0.076))
    def ear_inner(self, p): return np.minimum(self.ear_sd(p, 0, True), self.ear_sd(p, 1, True))
    PAW_F = nrm(V(0, -0.037, -0.016))
    def front_paw(self, p, i): return toe_paw(p, self.PAW[i], (0.05, 0.054, 0.042), self.PAW_F, tr=0.0172, tk=0.0062, fk=0.7, dk=0.3)
    def hind_paw(self, p, i): return toe_paw(p, self.FOOT[i], (0.068, 0.098, 0.04), V(0, -1, 0), tr=0.0225, tk=0.0072, pads=False, fk=0.72, dk=0.28)
    def arm_sd(self, p, i):
        x = sd_rcone(p, self.SHOULD[i], self.WRIST[i], 0.056, 0.046)
        x = smin(x, self.front_paw(p, i)[0], 0.028)
        return smin(x, sd_sph(p, self.SHOULD[i] + V(0, 0.005, 0.005), 0.064), 0.035)
    def extra_regions(self, p, reg):
        limb = (reg == 5) | (reg == 6); toes = np.full(len(p), 9.0, F); pads = np.full(len(p), 9.0, F)
        for i in range(2):
            x, t, pd = self.front_paw(p, i); toes = np.minimum(toes, x); pads = np.minimum(pads, pd)
            x, t, _ = self.hind_paw(p, i); toes = np.minimum(toes, x)
        reg = np.where(limb & (toes < 0.004), 9, reg); return np.where(limb & (pads < 0.0012), 12, reg)
    ANKLE = 0.085
    STEP = {'armL': 0.002, 'armR': 0.002, 'feet': 0.002}
    def parts(self, p):
        d = {}
        t = sd_ell(p, V(0, 0.006, 0.3), V(0.16, 0.146, 0.185))
        t = smin(t, sd_ell(p, V(0, -0.03, 0.385), V(0.142, 0.128, 0.125)), 0.06)          # грудь
        t = smin(t, sd_ell(p, V(0, -0.012, 0.2), V(0.166, 0.152, 0.115)), 0.06)           # круглый живот
        t = smin(t, sd_cap(p, V(0, 0, 0.45), self.NECK + V(0, -0.005, 0.05), 0.082), 0.05)
        d['torso'] = t
        h = self.head_form(p)
        d['head'] = h
        z0 = self.MZ_Z; k = self.MZ_S; yb = self.MZ_Y                                                       # мордочка: овал вперёд, с переносицей, губами-подушечками и подбородком
        m = sd_rcone(p, V(0, yb + 0.09 * k, z0), V(0, yb, z0 - 0.008 * k), 0.094 * k, 0.07 * k)
        m = smin(m, sd_ell(p, V(0, yb + 0.01 * k, z0 + 0.019 * k), V(0.042, 0.042, 0.026) * k), 0.026 * k)
        for s in (-1, 1): m = smin(m, sd_ell(p, V(s * 0.036 * k, yb - 0.006 * k, z0 - 0.029 * k), V(0.042, 0.042, 0.032) * k), 0.026 * k)
        m = smin(m, sd_ell(p, V(0, yb + 0.02 * k, z0 - 0.054 * k), V(0.032, 0.048, 0.02) * k), 0.024 * k)
        d['muzzle'] = m
        d['lid'] = self.lid(p)
        d['ear'] = np.minimum(self.ear_sd(p, 0), self.ear_sd(p, 1))
        d['arm'] = np.minimum(self.arm_sd(p, 0), self.arm_sd(p, 1))
        lg = None
        for i in range(2):
            x = sd_ell(p, self.HIP[i], V(0.098, 0.108, 0.1))
            x = smin(x, sd_rcone(p, self.HIP[i] + V(0, -0.015, -0.025), self.FOOT[i] + V(0, 0.022, 0.026), 0.062, 0.05), 0.04)
            x = smin(x, self.hind_paw(p, i)[0], 0.035)
            lg = x if lg is None else np.minimum(lg, x)
        d['leg'] = lg
        tl = None
        for i in range(len(self.TAIL) - 1):
            x = sd_rcone(p, self.TAIL[i], self.TAIL[i + 1], self.TAIL_R[i], self.TAIL_R[i + 1]); tl = x if tl is None else smin(tl, x, 0.015)
        d['tail'] = tl
        return d
    # ---- лепка 5 (18.11.2026): голова — форма, черты — по месту на лице; числа подобраны по обложкам 18, 22, 23 (sravnenie/) ----
    FORM = dict(C=V(0, 0.0, 0.69), n=2.1, nz=2.1, Rx=0.2, RyF=0.175, RyB=0.185, RzT=0.18, RzB=0.17,
                bumps=[(55, -20, 0.03, 0.14, True),    # щёки
                       (0, 30, 0.01, 0.1, False)])     # лоб
    EYE_XZ = (0.0666, 0.6866); EYE_OUT = 0.3; EYE_TILT = (0.0, -18.4)
    MZ_Z, MZ_S, MZ_Y = 0.626, 0.82, -0.2                # мордочка: высота, размер, насколько вперёд
    NOSE_Z, LIP_Zf = 0.6216, 0.5764
    def place_face(self):
        cls = type(self); cls.MZ_Z = self.NOSE_Z - 0.034; self.place_eyes()                    # мордочка идёт за носом
        S = self.front_hit(0, self.NOSE_Z, self.field); cls.NOSE_C = (S + V(0, -0.006, 0)).astype(F)
        cls.LIP_Z = float(self.LIP_Zf); Sm = self.front_hit(0, self.LIP_Zf - 0.012, self.field); mc = (Sm + V(0, 0.046, 0)).astype(F)
        cls.MOUTHS = {'a': (mc, V(0.038, 0.04, 0.024)), 'o': (mc + V(0, -0.002, 0.001), V(0.022, 0.04, 0.024))}
        cls.TONGUE = ((mc + V(0, 0.024, -0.016)).astype(F), V(0.021, 0.03, 0.006))
        ex, ez = self.EYE_XZ; cls.BLUSH = [self.front_hit(sg * (ex + 0.065), ez - 0.05) for sg in (-1, 1)]
    def colors(self, p, reg0, nor):
        """Бурый медвежонок: светлая мордочка и животик, уши внутри светлее, румянец, тёмные подушечки."""
        N = len(p); x, y, z = p[:, 0], p[:, 1], p[:, 2]; w = wob(p, 1.3) * 0.5
        reg = np.where((reg0 == 9) | (reg0 == 12), np.where(z > 0.15, 5, 6), reg0)
        brown = V(0.3, 0.1, 0.022); cream = V(0.72, 0.5, 0.26); blush = V(0.72, 0.26, 0.26)   # карамельно-бурый и светлая мордочка, как на обложках
        k = np.clip(0.94 + 0.1 * w - 0.14 * np.clip(y * 5, 0, 1), 0.68, 1.1); fur = brown[None] * k[:, None]
        wm = np.zeros(N, F)
        wm = np.maximum(wm, np.clip((1.1 - np.linalg.norm((p - V(0, -0.12, 0.27)) / V(0.105, 0.08, 0.15), axis=-1)) * 4, 0, 1) * (reg == 0))   # животик
        wm = np.maximum(wm, (reg == 2).astype(F))                                                                                           # мордочка
        fur = fur * (1 - wm[:, None]) + cream[None] * wm[:, None]
        for s in (-1, 1):                                                                                                                   # румянец
            b = np.clip((1.0 - np.linalg.norm((p - self.BLUSH[0 if s < 0 else 1]) / V(0.046, 0.046, 0.032), axis=-1)) * 2.5, 0, 1) * (reg == 1)
            fur = fur * (1 - 0.58 * b[:, None]) + blush[None] * (0.58 * b[:, None])
        skin = fur * 0.55
        skin = np.where((reg == 8)[:, None], V(0.46, 0.28, 0.18)[None] * (0.95 + 0.05 * w[:, None]), skin)                                    # уши внутри
        skin = np.where((reg == 10)[:, None], V(0.14, 0.03, 0.03)[None], np.where((reg == 11)[:, None], V(0.72, 0.3, 0.34)[None], skin))
        skin = np.where((reg0 == 12)[:, None], V(0.1, 0.06, 0.045)[None] * (0.95 + 0.1 * w[:, None]), skin)                                  # тёмные подушечки
        return skin.astype(F), fur.astype(F)
    SCARF_C = V(0, -0.008, 0.475); SCARF_R = 0.124; SCARF_T = 0.045; SCARF_ROT = 0.14   # толстый вязаный, как у прежнего Топы
    def scarf_fn(self, p):  # вязаный шарф: кольцо вокруг шеи, узел спереди слева и свисающий конец; рубчики вязки
        c = self.SCARF_C; q = p - c; cs, sn = math.cos(self.SCARF_ROT), math.sin(self.SCARF_ROT)
        yy = q[:, 1] * cs - q[:, 2] * sn; zz = q[:, 1] * sn + q[:, 2] * cs
        ang = np.arctan2(q[:, 0], -yy); rr = np.sqrt(q[:, 0] ** 2 + yy ** 2) - self.SCARF_R
        ring = np.sqrt(rr ** 2 + (zz * 0.86) ** 2) - self.SCARF_T
        ring = ring + 0.0024 * np.cos(ang * 34) * np.clip(1 - np.abs(ring) * 35, 0, 1)
        kn = sd_ell(p, V(0.07, -0.152, 0.458), V(0.052, 0.043, 0.047))
        e0 = V(0.08, -0.168, 0.335); qe = rotz(p - e0, 0.1)
        end = sd_ell(qe, V(0, 0, 0), V(0.058, 0.022, 0.14)); end = smax(end, -(qe[:, 2] + 0.125), 0.006)
        end = end + 0.0022 * np.cos(qe[:, 0] * (2 * math.pi / 0.013)) * np.clip(1 - np.abs(end) * 35, 0, 1)
        return smin(smin(ring, kn, 0.015), end, 0.015)
    def acc_fn(self, p): return self.scarf_fn(p)
    ACCS = [{'name': 'scarf', 'fn': 'scarf_fn', 'box': ((-0.2, -0.235, 0.18), (0.2, 0.185, 0.555)), 'mat': 'cloth', 'col': (0.2, 0.62, 0.14), 'h': 0.0018}]
    def fur_ok(self, p, reg):
        ok = (reg != 10) & (reg != 11) & (reg != 8) & (reg != 12)
        for E in self.EYES: ok &= self.eye_d(p, E) > self.RE + 0.005
        ok &= np.linalg.norm(p - self.NOSE_C, axis=-1) > 0.042
        ok &= self.scarf_fn(p) > 0.0015                                # мех растёт вплотную к шарфу — без голой полоски на шее
        return ok
    def nose_fn(self, p):   # крупный мягкий нос-«фасолина» с ноздрями
        c = self.NOSE_C; d = sd_ell(p, c, V(0.036, 0.021, 0.023))
        d = smin(d, sd_ell(p, c + V(0, 0.003, -0.016), V(0.0095, 0.012, 0.01)), 0.008)
        for s in (-1, 1): d = smax(d, -sd_ell(p, c + V(s * 0.0125, -0.017, -0.0025), V(0.006, 0.005, 0.004)), 0.0025)
        return d
    NOSE_COL = (0.07, 0.035, 0.022); NOSE_WET = False     # тёмно-шоколадный, с мягким бликом (не «хром»)
    def mouth_lines(self):
        lines = []; nz = self.NOSE_C
        z0 = nz[2] - 0.024; phil = [V(0, -0.5, z0 + (self.LIP_Z - z0) * i / 6) for i in range(7)]
        ph = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6)
        if self.MOUTH is not None:
            m0 = self.MOUTH; self.MOUTH = None; pb = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6); self.MOUTH = m0
            keep = np.linalg.norm(ph - pb, axis=-1) < 0.003; ph = ph[keep] if keep.sum() >= 2 else pb[:2]
        lines.append(ph)
        for s in (-1, 1):
            ang = np.linspace(0, math.pi, 12); xs = s * (0.025 - 0.025 * np.cos(ang)); zs = self.LIP_Z - 0.01 * np.sin(ang) + 0.014 * (xs * s / 0.05) ** 2   # улыбка: уголки вверх
            lines.append(self.hit(np.stack([xs, np.full(12, -0.5, F), zs], -1).astype(F), np.tile(V(0, 1, 0), (12, 1)), 0.6))
        return lines[:1] if self.MOUTH is not None else lines
    def whiskers(self):   # у медвежонка усов почти нет — по две короткие щетинки
        out = []
        for s in (-1, 1):
            for j, (dz, ang) in enumerate([(0.006, 0.12), (-0.006, -0.1)]):
                o = V(s * (0.03 + 0.007 * j), -0.5, self.LIP_Z + 0.018 + dz); r0 = self.hit(o, V(0, 1, 0), 0.6)[0] + V(0, 0.002, 0)
                dirn = nrm(V(s * 1.0, -0.5, ang)); out.append(np.array([r0 + dirn * 0.035 * (k / 7) + V(0, 0.004 * (k / 7) ** 2, -0.006 * (k / 7) ** 2) for k in range(8)], F))
        return out
    WHISK_R = (0.0007, 0.0002); WHISK_COL = (0.16, 0.1, 0.07)
    FUR = {'K': 0.56e6, 'dens': [1.0, 1.1, 1.0, 1.4, 1.0, 1.0, 1.0, 1.05, 0.0, 1.1], 'L': [0.015, 0.011, 0.006, 0.004, 0.007, 0.013, 0.014, 0.018, 0.0, 0.0055],
           'lean': [1.15, 1.2, 1.35, 1.35, 1.25, 1.18, 1.18, 1.0, 0.5, 1.32], 'down': [0.35, 0.2, 0.15, 0.1, 0.1, 0.22, 0.22, 0.0, 0.0, 0.1], 'rad': 0.00085, 'radLid': 0.0006,
           'cell': 0.012, 'clump': 0.2, 'frontK': 0.5, 'spec': 0.06, 'gold': 0.15, 'tip': 0.18, 'ms': 0.12, 'ruff': [0.125, 0.56, 0.68, 10.0, 0.8, -0.2], 'earTip': None, 'chest': [0.0, -0.06, 0.41, 1.2], 'tailTip': None}
    def fur_src(self):
        return {'nose': self.NOSE_C.tolist(), 'earOff': [0, 0.1, 0.1], 'neck': (self.NECK + V(0, 0, 0.03)).tolist(), 'should': [s.tolist() for s in self.SHOULD], 'wrist': [s.tolist() for s in self.WRIST],
                'hip': [(h + V(0, 0, 0.06)).tolist() for h in self.HIP], 'foot': [f.tolist() for f in self.FOOT], 'tail': [t.tolist() for t in self.TAIL], 'H': self.H.tolist(), 'headR': float(self.HEAD_R[0])}

HERO = Topa(); HERO.place_face()
