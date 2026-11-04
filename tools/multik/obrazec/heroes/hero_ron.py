# Рон — маленький серый пёс: белый живот и лапки, белая длинная морда и проточина, висячие тёмные уши-«листики», хвост бубликом,
# белая кепка, красный ошейник с золотым жетоном. Крепкий, рост до макушки ~0.82 м.
from hero_common import *

class Ron(Hero):
    NAME = 'ron'
    H = V(0, 0.0, 0.645); HEAD_R = V(0.158, 0.15, 0.142)
    RE = 0.046; LID_OFF = 0.86; LID_K = 0.05
    EYES = [V(s * 0.061, -0.121, 0.671) for s in (-1, 1)]       # ближе к носу, как у Пика
    IRIS = [(0.06, 0.03, 0.01), (0.26, 0.13, 0.04), (0.48, 0.28, 0.1)]     # тёплые карие
    EYE_AIM = V(0, -1.6, 0.68); EYE_DIV = 0.2
    EYE_CENTER = (0.1, 0.45)  # зрачок почти прямо вперёд, ближе к носу, как у Пика
    EYE_S = V(0.9, 1.0, 1.1)                                     # слегка овальные                                                            # радужка в середину видимой части глаза                               # оба глаза смотрят вперёд, зрачок по центру глазницы
    SHOULD = [V(s * 0.102, -0.032, 0.43) for s in (-1, 1)]
    WRIST = [V(s * 0.148, -0.095, 0.29) for s in (-1, 1)]
    PAW = [V(s * 0.153, -0.107, 0.265) for s in (-1, 1)]
    HIP = [V(s * 0.074, 0.005, 0.15) for s in (-1, 1)]
    FOOT = [V(s * 0.08, -0.07, 0.03) for s in (-1, 1)]
    TAIL = [V(0, 0.12, 0.19), V(0, 0.19, 0.26), V(0, 0.215, 0.36), V(0, 0.18, 0.44), V(0, 0.125, 0.45), V(0, 0.1, 0.4)]
    TAIL_R = [0.036, 0.034, 0.032, 0.03, 0.028, 0.026]
    NECK = V(0, -0.01, 0.49)
    SN_A = V(0, -0.085, 0.622); SN_B = V(0, -0.252, 0.594)
    NOSE_C = V(0, -0.272, 0.61)
    # рот крупнее и ближе к кончику морды — открытый виден спереди (v6.3); язык внутри рта, не высунут
    MOUTHS = {'a': (V(0, -0.24, 0.559), V(0.042, 0.042, 0.026)), 'o': (V(0, -0.242, 0.559), V(0.025, 0.042, 0.026))}
    TONGUE = (V(0, -0.205, 0.541), V(0.023, 0.032, 0.007))
    PIV = {'head': V(0, -0.01, 0.5), 'armL': SHOULD[0], 'armR': SHOULD[1], 'tail': TAIL[0]}
    BOX = {'head': ((-0.27, -0.34, 0.47), (0.27, 0.2, 0.83)), 'body': ((-0.22, -0.2, -0.01), (0.22, 0.2, 0.58)),
           'armL': ((-0.22, -0.16, 0.2), (-0.04, 0.06, 0.5)), 'armR': ((0.04, -0.16, 0.2), (0.22, 0.06, 0.5)), 'tail': ((-0.06, 0.06, 0.13), (0.06, 0.27, 0.5)),
           'feet': ((-0.16, -0.18, -0.01), (0.16, 0.07, 0.09))}
    NECK_PLUG = (V(0, -0.01, 0.47), V(0, -0.012, 0.56), 0.064)
    K_MUZ = 0.045; K_EAR = 0.03; K_TORSO = 0.07

    def ear_parts(self, p, i):
        s = 1 if i else -1
        a = sd_ell(p, V(s * 0.118, 0.01, 0.742), V(0.045, 0.032, 0.038))          # корень у макушки (под кепкой)
        b = sd_ell(p, V(s * 0.172, -0.004, 0.665), V(0.052, 0.024, 0.078))         # широкая часть
        c = sd_ell(p, V(s * 0.18, -0.026, 0.565), V(0.034, 0.019, 0.05))           # узкий кончик у щеки
        return smin(smin(a, b, 0.04), c, 0.04)
    def ear_sd(self, p, i, inner=False): return self.ear_parts(p, i)
    def ear_inner(self, p): return np.full(len(p), 9.0, F)                           # висячее ухо — без розовой выемки
    PAW_F = nrm(V(0, -0.037, -0.016))
    def front_paw(self, p, i): return toe_paw(p, self.PAW[i], (0.039, 0.044, 0.034), self.PAW_F, tr=0.0142, tk=0.0052, fk=0.7, dk=0.3)
    def hind_paw(self, p, i): return toe_paw(p, self.FOOT[i], (0.051, 0.082, 0.033), V(0, -1, 0), tr=0.0182, tk=0.006, pads=False, fk=0.72, dk=0.28)
    def arm_sd(self, p, i):
        x = sd_rcone(p, self.SHOULD[i], self.WRIST[i], 0.043, 0.034)
        x = smin(x, self.front_paw(p, i)[0], 0.022)
        return smin(x, sd_sph(p, self.SHOULD[i] + V(0, 0.005, 0.005), 0.05), 0.03)
    def extra_regions(self, p, reg):
        limb = (reg == 5) | (reg == 6); toes = np.full(len(p), 9.0, F); pads = np.full(len(p), 9.0, F)
        for i in range(2):     # вся кисть/ступня — короткая шерсть (9), чтобы пальцы читались
            x, t, pd = self.front_paw(p, i); toes = np.minimum(toes, x); pads = np.minimum(pads, pd)
            x, t, _ = self.hind_paw(p, i); toes = np.minimum(toes, x)
        reg = np.where(limb & (toes < 0.004), 9, reg); return np.where(limb & (pads < 0.0012), 12, reg)
    ANKLE = 0.08
    STEP = {'armL': 0.0019, 'armR': 0.0019, 'feet': 0.0019}
    def parts(self, p):
        d = {}
        t = sd_ell(p, V(0, 0.004, 0.3), V(0.128, 0.118, 0.17))
        t = smin(t, sd_ell(p, V(0, -0.03, 0.37), V(0.118, 0.108, 0.12)), 0.06)          # грудь
        t = smin(t, sd_ell(p, V(0, 0.02, 0.19), V(0.122, 0.11, 0.09)), 0.05)
        t = smin(t, sd_cap(p, V(0, 0, 0.44), self.NECK + V(0, -0.005, 0.05), 0.07), 0.05)
        d['torso'] = t
        h = sd_ell(p, self.H, self.HEAD_R)
        for s in (-1, 1): h = smin(h, sd_ell(p, V(s * 0.085, -0.07, 0.6), V(0.09, 0.08, 0.075)), 0.05)    # щёки
        h = smin(h, sd_ell(p, V(0, -0.05, 0.72), V(0.12, 0.1, 0.075)), 0.05)                              # лоб со «стопом»
        d['head'] = h
        m = sd_rcone(p, self.SN_A, self.SN_B, 0.07, 0.038)                                                 # длинная морда, к носу уже
        m = smin(m, sd_cap(p, V(0, -0.12, 0.656), V(0, -0.245, 0.62), 0.025), 0.035)                      # спинка носа
        for s in (-1, 1): m = smin(m, sd_ell(p, V(s * 0.029, -0.2, 0.573), V(0.035, 0.052, 0.03)), 0.028)  # брыли
        m = smin(m, sd_ell(p, V(0, -0.168, 0.542), V(0.03, 0.055, 0.02)), 0.028)                          # подбородок
        d['muzzle'] = m
        d['lid'] = self.lid(p)
        d['ear'] = np.minimum(self.ear_sd(p, 0), self.ear_sd(p, 1))
        d['arm'] = np.minimum(self.arm_sd(p, 0), self.arm_sd(p, 1))
        lg = None
        for i in range(2):
            x = sd_ell(p, self.HIP[i], V(0.074, 0.088, 0.085))
            x = smin(x, sd_rcone(p, self.HIP[i] + V(0, -0.015, -0.025), self.FOOT[i] + V(0, 0.02, 0.022), 0.045, 0.036), 0.035)
            x = smin(x, self.hind_paw(p, i)[0], 0.03)
            lg = x if lg is None else np.minimum(lg, x)
        d['leg'] = lg
        tl = None
        for i in range(len(self.TAIL) - 1):
            x = sd_rcone(p, self.TAIL[i], self.TAIL[i + 1], self.TAIL_R[i], self.TAIL_R[i + 1]); tl = x if tl is None else smin(tl, x, 0.02)
        d['tail'] = tl
        return d
    def colors(self, p, reg0, nor):
        N = len(p); x, y, z = p[:, 0], p[:, 1], p[:, 2]; w = wob(p, 1.3) * 0.5
        reg = np.where((reg0 == 9) | (reg0 == 12), np.where(z > 0.15, 5, 6), reg0)          # пальцы и подушечки красим как лапу
        grey = V(0.2, 0.21, 0.23); white = V(0.82, 0.82, 0.8); dark = V(0.08, 0.075, 0.08)
        k = np.clip(0.92 + 0.1 * w - 0.15 * np.clip(y * 6, 0, 1), 0.65, 1.1); fur = grey[None] * k[:, None]
        wm = np.zeros(N, F)
        wm = np.maximum(wm, np.clip((1.12 - np.linalg.norm((p - V(0, -0.1, 0.3)) / V(0.09, 0.07, 0.16), axis=-1)) * 4, 0, 1) * (reg == 0))   # живот и грудь
        wm = np.maximum(wm, (reg == 2).astype(F))                                                                                          # вся морда белая
        blaze = np.clip((0.024 + 0.25 * np.clip(0.72 - z, 0, 1) * 0.1 - np.abs(x)) * 120, 0, 1) * np.clip((-y - 0.08) * 20, 0, 1) * np.clip((0.76 - z) * 25, 0, 1)
        wm = np.maximum(wm, blaze * ((reg == 1) | (reg == 3)))                                                                              # белая проточина
        wm = np.maximum(wm, np.clip((0.33 - z) * 30, 0, 1) * (reg == 5)); wm = np.maximum(wm, np.clip((0.085 - z) * 30, 0, 1) * (reg == 6))  # белые лапки
        wm = np.maximum(wm, np.clip((-(y - 0.12) * 0 + 0.0), 0, 0) * 0)
        fur = fur * (1 - wm[:, None]) + white[None] * wm[:, None]
        fur = np.where((reg == 4)[:, None], dark[None] * (0.9 + 0.2 * w[:, None]), fur)                                                    # тёмные уши
        skin = fur * 0.9
        skin = np.where((reg == 10)[:, None], V(0.14, 0.03, 0.03)[None], np.where((reg == 11)[:, None], V(0.72, 0.3, 0.34)[None], skin))
        skin = np.where((reg0 == 12)[:, None], V(0.075, 0.062, 0.065)[None] * (0.95 + 0.1 * w[:, None]), skin)            # тёмные подушечки
        return skin.astype(F), fur.astype(F)
    def cap_head(self, p): return smin(sd_ell(p, self.H, self.HEAD_R), sd_ell(p, V(0, -0.05, 0.72), V(0.12, 0.1, 0.075)), 0.05)
    def cap_fn(self, p):   # белая кепка: оболочка по полю головы (с запасом на шерсть) + козырёк + пуговка
        hd = self.cap_head(p)
        dome = smax(np.abs(hd - 0.016) - 0.0055, -(p[:, 2] - (self.H[2] + 0.088)), 0.008)
        # козырёк назад (как носит Рон)
        vis = sd_ell(p, V(0, 0.19, 0.744), V(0.105, 0.085, 0.0075)); vis = smax(vis, -(hd - 0.014), 0.004); vis = smax(vis, -(p[:, 1] - 0.09), 0.01)
        btn = sd_sph(p, V(0, -0.02, 0.818), 0.012)
        return np.minimum(smin(dome, vis, 0.01), btn)
    def collar_fn(self, p): return sd_torus(p, self.NECK + V(0, -0.006, 0.0), 0.1, 0.015, rotx=0.16)      # v6.3: выше, на шее (был на плечах)
    def tag_fn(self, p):
        q = p - V(0, -0.118, 0.466); q = rotx(q, -0.25); return smax(np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - 0.021, np.abs(q[:, 1]) - 0.0035, 0.002)
    def acc_fn(self, p): return np.minimum(np.minimum(self.cap_fn(p), self.collar_fn(p)), self.tag_fn(p))
    ACCS = [{'name': 'cap', 'fn': 'cap_fn', 'box': ((-0.2, -0.2, 0.64), (0.2, 0.31, 0.84)), 'mat': 'cloth', 'col': (0.86, 0.86, 0.84), 'h': 0.0016},
            {'name': 'collar', 'fn': 'collar_fn', 'box': ((-0.13, -0.14, 0.43), (0.13, 0.11, 0.53)), 'mat': 'satin', 'col': (0.6, 0.03, 0.03), 'h': 0.0014},
            {'name': 'tag', 'fn': 'tag_fn', 'box': ((-0.03, -0.14, 0.43), (0.03, -0.09, 0.5)), 'mat': 'gold', 'col': (1.0, 0.72, 0.28), 'h': 0.0008}]
    def fur_ok(self, p, reg):
        ok = (reg != 10) & (reg != 11) & (reg != 8) & (reg != 12)
        for E in self.EYES: ok &= self.eye_d(p, E) > self.RE + 0.005
        ok &= np.linalg.norm(p - self.NOSE_C, axis=-1) > 0.04
        ok &= self.collar_fn(p) > 0.006
        ok &= ~((p[:, 2] > self.H[2] + 0.082) & ((reg == 1) | (reg == 3)))    # под кепкой не растёт
        return ok
    def nose_fn(self, p):
        c = self.NOSE_C; d = sd_ell(p, c, V(0.033, 0.022, 0.024))
        d = smin(d, sd_ell(p, c + V(0, 0.004, -0.018), V(0.011, 0.014, 0.012)), 0.01)
        for s in (-1, 1): d = smax(d, -sd_ell(p, c + V(s * 0.013, -0.02, -0.002), V(0.0065, 0.006, 0.0045)), 0.003)
        return d
    NOSE_COL = (0.03, 0.028, 0.03); NOSE_WET = True
    def mouth_lines(self):
        lines = []; nz = self.NOSE_C
        phil = [V(0, -0.5, nz[2] - 0.026 - 0.02 * i / 6) for i in range(7)]
        ph = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6)
        if self.MOUTH is not None:      # открытый рот: желобок кончается у верхней губы (где кожа та же, что у закрытого)
            m0 = self.MOUTH; self.MOUTH = None; pb = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6); self.MOUTH = m0
            keep = np.linalg.norm(ph - pb, axis=-1) < 0.003; ph = ph[keep] if keep.sum() >= 2 else pb[:2]
        lines.append(ph)
        for s in (-1, 1):
            ang = np.linspace(0, math.pi, 12); xs = s * (0.026 - 0.026 * np.cos(ang)); zs = nz[2] - 0.047 - 0.012 * np.sin(ang)
            lines.append(self.hit(np.stack([xs, np.full(12, -0.5, F), zs], -1).astype(F), np.tile(V(0, 1, 0), (12, 1)), 0.6))
        return lines[:1] if self.MOUTH is not None else lines
    def whiskers(self):
        out = []
        for s in (-1, 1):
            for j, (dz, ang) in enumerate([(0.006, 0.12), (-0.006, -0.1)]):
                o = V(s * (0.026 + 0.008 * j), -0.5, 0.582 + dz); r0 = self.hit(o, V(0, 1, 0), 0.6)[0] + V(0, 0.002, 0)
                dirn = nrm(V(s * 1.0, -0.5, ang)); out.append(np.array([r0 + dirn * 0.07 * (k / 7) + V(0, 0.006 * (k / 7) ** 2, -0.01 * (k / 7) ** 2) for k in range(8)], F))
        return out
    WHISK_R = (0.0008, 0.0002); WHISK_COL = (0.12, 0.11, 0.11)
    FUR = {'K': 0.5e6, 'dens': [1.0, 1.1, 1.0, 1.4, 0.9, 1.0, 1.0, 1.05, 0.0, 1.1], 'L': [0.014, 0.0095, 0.0055, 0.004, 0.0055, 0.011, 0.012, 0.02, 0.0, 0.005],
           'lean': [1.18, 1.22, 1.35, 1.35, 1.3, 1.2, 1.2, 1.05, 0.5, 1.32], 'down': [0.35, 0.2, 0.15, 0.1, 0.4, 0.2, 0.2, 0.0, 0.0, 0.1], 'rad': 0.0008, 'radLid': 0.0006,
           'cell': 0.012, 'clump': 0.28, 'frontK': 0.5, 'ruff': None, 'earTip': None, 'chest': [0.0, -0.06, 0.4, 1.25], 'tailTip': None}
    def fur_src(self):
        return {'nose': self.NOSE_C.tolist(), 'earOff': [0, 0.12, 0.08], 'neck': (self.NECK + V(0, 0, 0.03)).tolist(), 'should': [s.tolist() for s in self.SHOULD], 'wrist': [s.tolist() for s in self.WRIST],
                'hip': [(h + V(0, 0, 0.06)).tolist() for h in self.HIP], 'foot': [f.tolist() for f in self.FOOT], 'tail': [t.tolist() for t in self.TAIL], 'H': self.H.tolist(), 'headR': float(self.HEAD_R[0])}

HERO = Ron()
