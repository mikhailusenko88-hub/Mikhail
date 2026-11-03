# Пик — маленький серый мышонок с красным бантиком (рост с ушами ~0.62 м). Малыш: большая круглая голова, огромные круглые уши,
# крупные тёмные глаза близко друг к другу, короткая аккуратная мордочка с розовым носиком-бусинкой, два зубика, пухлые щёчки
# с румянцем, розовые ручки с пальчиками и длинные ступни с пальцами, гладкий хвостик.
from hero_common import *

class Pik(Hero):
    NAME = 'pik'
    H = V(0, -0.004, 0.414); HEAD_R = V(0.12, 0.108, 0.104)
    RE = 0.041; LID_OFF = 0.87; LID_K = 0.03; LID_NY = 0.12
    EYES = [V(s * 0.045, -0.08, 0.425) for s in (-1, 1)]       # ближе к носу (утверждено)
    IRIS = [(0.018, 0.009, 0.005), (0.075, 0.034, 0.016), (0.33, 0.165, 0.06)]   # ободок, тёмно-карая сверху, светлее книзу
    IRIS_STYLE = 1
    EYE_K = (0.76, 0.935)                                                         # вариант 3: радужка маленькая, белка много
    EYE_S = V(0.88, 1.0, 1.12)
    EYE_CENTER = (0.1, 0.45)  # зрачок почти прямо вперёд, ближе к носу (утверждено)                                                            # радужка в середину видимой части глаза                                                    # глаз овальный: уже и выше (x, вглубь, вверх)
    EYE_AIM = V(0, -1.5, 0.43); EYE_DIV = 0.24                                    # смотрят вперёд, чуть врозь — зрачок по центру глазницы
    EAR_C = [V(s * 0.118, 0.022, 0.537) for s in (-1, 1)]
    SHOULD = [V(s * 0.056, -0.016, 0.262) for s in (-1, 1)]
    WRIST = [V(s * 0.086, -0.06, 0.192) for s in (-1, 1)]
    PAW = [V(s * 0.089, -0.066, 0.176) for s in (-1, 1)]
    HIP = [V(s * 0.044, 0.004, 0.104) for s in (-1, 1)]
    FOOT = [V(s * 0.05, -0.05, 0.014) for s in (-1, 1)]
    TAILC = [V(0, 0.07, 0.085), V(0.04, 0.15, 0.04), V(0.13, 0.23, 0.045), V(0.2, 0.27, 0.12), V(0.195, 0.275, 0.22), V(0.15, 0.29, 0.285), V(0.11, 0.285, 0.3)]
    TAIL = list(spline(TAILC, 22))
    TAIL_R = list(np.linspace(0.0155, 0.0052, 22).astype(F))
    NECK = V(0, -0.006, 0.31)
    SN_A = V(0, -0.058, 0.388); SN_B = V(0, -0.177, 0.374)
    NOSE_C = V(0, -0.191, 0.379)
    MOUTHS = {'a': (V(0, -0.16, 0.346), V(0.016, 0.02, 0.012)), 'o': (V(0, -0.16, 0.347), V(0.009, 0.02, 0.01))}
    TONGUE = (V(0, -0.155, 0.34), V(0.008, 0.012, 0.004))
    PIV = {'head': V(0, -0.006, 0.312), 'armL': SHOULD[0], 'armR': SHOULD[1], 'tail': TAIL[0]}
    BOX = {'head': ((-0.225, -0.2, 0.29), (0.225, 0.12, 0.64)), 'body': ((-0.13, -0.12, 0.03), (0.13, 0.12, 0.37)),
           'armL': ((-0.135, -0.11, 0.135), (-0.02, 0.04, 0.31)), 'armR': ((0.02, -0.11, 0.135), (0.135, 0.04, 0.31)), 'tail': ((-0.03, 0.04, 0.02), (0.24, 0.32, 0.34)),
           'feet': ((-0.1, -0.13, -0.01), (0.1, 0.06, 0.07))}
    ANKLE = 0.05                                       # ниже — отдельная мелкая сетка ступней (пальцы)
    STEP = {'head': 0.0022, 'body': 0.0024, 'tail': 0.0018, 'armL': 0.0011, 'armR': 0.0011, 'feet': 0.0011}
    NECK_PLUG = (V(0, -0.006, 0.3), V(0, -0.008, 0.36), 0.04)
    K_MUZ = 0.03; K_EAR = 0.026; K_TORSO = 0.05

    def ear_sd(self, p, i, inner=False):
        c = self.EAR_C[i]; s = 1 if i else -1
        q = rotz(p - c, -s * 0.32); q = rotx(q, 0.12); q = roty(q, s * 0.22)             # чуть вперёд-в стороны, слегка наклонены
        if inner: return sd_ell(q, V(0, -0.008, 0.003), V(0.067, 0.011, 0.065))
        return sd_ell(q, V(0, 0, 0), V(0.085, 0.0155, 0.083))
    def ear_inner(self, p): return np.minimum(self.ear_sd(p, 0, True), self.ear_sd(p, 1, True))
    def hand(self, p, i):
        s = 1 if i else -1; P = self.PAW[i]
        x = sd_ell(p, P, V(0.0128, 0.0082, 0.0115))                                       # ладошка (тонкая спереди-назад)
        for j in range(4):
            u = -1 + 2 * j / 3; base = P + V(s * u * 0.0085, 0.0005, -0.0075)
            L = 0.021 + 0.004 * (1 - abs(u)); d1 = nrm(V(s * u * 0.3, 0.05, -1.0)); mid = base + d1 * L * 0.55
            d2 = nrm(V(s * u * 0.32, 0.28, -0.92)); tip = mid + d2 * L * 0.45
            fg = smin(sd_rcone(p, base, mid, 0.0035, 0.0031), sd_rcone(p, mid, tip, 0.0031, 0.0028), 0.0015)
            fg = smin(fg, sd_sph(p, tip + d2 * 0.0004, 0.0033), 0.0012)                   # подушечка на кончике
            x = smin(x, fg, 0.0018)
        b = P + V(-s * 0.0105, -0.004, -0.002); t = b + nrm(V(-s * 0.55, -0.55, -0.62)) * 0.013   # большой пальчик внутрь
        x = smin(x, smin(sd_rcone(p, b, t, 0.0036, 0.003), sd_sph(p, t, 0.0033), 0.0012), 0.0028)
        return x
    def arm_sd(self, p, i):
        x = sd_rcone(p, self.SHOULD[i], self.WRIST[i], 0.024, 0.0155)
        x = smin(x, self.hand(p, i), 0.009)
        return smin(x, sd_sph(p, self.SHOULD[i] + V(0, 0.003, 0.003), 0.028), 0.015)
    def foot(self, p, i):
        F0 = self.FOOT[i]
        x = sd_ell(p, F0 + V(0, 0.006, 0), V(0.023, 0.058, 0.0135))                        # длинная мышиная ступня
        x = smin(x, sd_ell(p, F0 + V(0, 0.04, 0.004), V(0.019, 0.022, 0.016)), 0.01)        # пяточка
        for j in range(4):
            u = -1 + 2 * j / 3; b = F0 + V(u * 0.0125, -0.045, -0.002); t = b + nrm(V(u * 0.32, -1.0, -0.12)) * (0.0135 + 0.003 * (1 - abs(u)))
            x = smin(x, smin(sd_rcone(p, b, t, 0.0046, 0.0039), sd_sph(p, t, 0.0044), 0.0014), 0.0028)
        return x
    def leg_sd(self, p, i):
        x = sd_ell(p, self.HIP[i], V(0.044, 0.05, 0.05))
        x = smin(x, sd_rcone(p, self.HIP[i] + V(0, -0.01, -0.02), self.FOOT[i] + V(0, 0.03, 0.014), 0.026, 0.0155), 0.025)
        return smin(x, self.foot(p, i), 0.012)
    def parts(self, p):
        d = {}
        t = sd_ell(p, V(0, 0.006, 0.204), V(0.074, 0.066, 0.106))
        t = smin(t, sd_ell(p, V(0, -0.012, 0.15), V(0.086, 0.078, 0.074)), 0.04)                              # круглый животик
        t = smin(t, sd_cap(p, V(0, 0, 0.27), self.NECK + V(0, -0.004, 0.03), 0.04), 0.035)
        d['torso'] = t
        h = sd_ell(p, self.H, self.HEAD_R)
        for s in (-1, 1): h = smin(h, sd_ell(p, V(s * 0.05, -0.058, 0.372), V(0.06, 0.054, 0.05)), 0.045)     # пухлые щёчки
        h = smin(h, sd_ell(p, V(0, 0.01, 0.47), V(0.1, 0.09, 0.06)), 0.05)                                    # круглая макушка (без «бровей»)
        d['head'] = h
        m = sd_rcone(p, self.SN_A, self.SN_B, 0.05, 0.0185)                                                    # короткая аккуратная мордочка
        for s in (-1, 1): m = smin(m, sd_sph(p, V(s * 0.0158, -0.16, 0.3615), 0.0168), 0.012)                 # подушечки с усами (верхняя губка «w»)
        m = smin(m, sd_ell(p, V(0, -0.141, 0.342), V(0.019, 0.028, 0.0135)), 0.016)                           # маленький подбородок
        d['muzzle'] = m
        d['lid'] = self.lid(p)
        d['ear'] = np.minimum(self.ear_sd(p, 0), self.ear_sd(p, 1))
        d['arm'] = np.minimum(self.arm_sd(p, 0), self.arm_sd(p, 1))
        d['leg'] = np.minimum(self.leg_sd(p, 0), self.leg_sd(p, 1))
        tl = None
        for i in range(len(self.TAIL) - 1):
            x = sd_rcone(p, self.TAIL[i], self.TAIL[i + 1], self.TAIL_R[i], self.TAIL_R[i + 1]); tl = x if tl is None else smin(tl, x, 0.004)
        d['tail'] = tl
        return d
    def colors(self, p, reg, nor):
        """Кожа и шерсть: светло-серый мышонок (чуть сиреневый, без желтизны), светлое брюшко и мордочка, румянец на щёчках,
        розовые уши внутри, ручки, ступни, хвост и нос."""
        N = len(p); x, y, z = p[:, 0], p[:, 1], p[:, 2]; w = wob(p, 1.6) * 0.5
        grey = V(0.34, 0.33, 0.355); light = V(0.8, 0.78, 0.78); pink = V(0.86, 0.5, 0.55); blush = V(0.78, 0.5, 0.55)
        k = np.clip(0.92 + 0.08 * w - 0.16 * np.clip((y + 0.0) * 6, 0, 1), 0.7, 1.08)                     # спинка чуть темнее
        fur = grey[None] * k[:, None]
        belly = np.clip((1.12 - np.linalg.norm((p - V(0, -0.062, 0.185)) / V(0.06, 0.05, 0.105), axis=-1)) * 4, 0, 1) * (reg == 0)
        face = np.clip((1.15 - np.linalg.norm((p - V(0, -0.125, 0.362)) / V(0.068, 0.08, 0.042), axis=-1)) * 3, 0, 1) * ((reg == 1) | (reg == 2))
        cream = np.maximum(belly, face)
        fur = fur * (1 - cream[:, None]) + light[None] * cream[:, None]
        for s in (-1, 1):                                                                                   # румянец под глазками
            b = np.clip((1.0 - np.linalg.norm((p - V(s * 0.072, -0.085, 0.37)) / V(0.03, 0.03, 0.022), axis=-1)) * 2.5, 0, 1) * ((reg == 1) | (reg == 2))
            fur = fur * (1 - 0.55 * b[:, None]) + blush[None] * (0.55 * b[:, None])
        skin = fur * 0.9
        bare = (reg == 7) | (reg == 8) | self.bare(p, reg)
        skin = np.where(bare[:, None], pink[None] * (0.95 + 0.05 * w[:, None]), skin)
        skin = np.where((reg == 7)[:, None], V(0.78, 0.52, 0.55)[None], skin)
        skin = np.where((reg == 10)[:, None], V(0.16, 0.03, 0.03)[None], np.where((reg == 11)[:, None], V(0.75, 0.3, 0.34)[None], skin))
        fur = np.where((reg == 4)[:, None], fur * V(1.06, 1.0, 1.0), fur)
        return skin.astype(F), fur.astype(F)
    def bare(self, p, reg):
        z = p[:, 2]; return ((reg == 5) & (z < self.WRIST[0][2] - 0.001)) | ((reg == 6) & (z < 0.03))
    def fur_ok(self, p, reg):
        z = p[:, 2]; ok = ((reg != 7) & (reg != 8) & (reg != 10) & (reg != 11) & (reg != 2)) | ((reg == 2) & (p[:, 1] > -0.155))
        ok &= ~self.bare(p, reg)
        for E in self.EYES: ok &= self.eye_d(p, E) > self.RE + 0.004
        ok &= np.linalg.norm(p - self.NOSE_C, axis=-1) > 0.022
        ok &= self.acc_fn(p) > 0.004
        return ok
    def nose_fn(self, p):   # носик-бусинка: круглый, чуть шире, чем выше, едва заметные ноздри (не «пятачок»)
        c = self.NOSE_C; d = sd_ell(p, c, V(0.0138, 0.0112, 0.0115))
        d = smin(d, sd_ell(p, c + V(0, 0.004, 0.005), V(0.008, 0.009, 0.0055)), 0.004)
        for s in (-1, 1): d = smax(d, -sd_ell(p, c + V(s * 0.0055, -0.0106, -0.0038), V(0.0018, 0.0016, 0.0012)), 0.0012)
        return d
    NOSE_COL = (0.9, 0.45, 0.55)
    _TC = None
    def teeth_centers(self):   # зубики ставим прямо на поверхность под серединкой улыбки (луч спереди)
        if Pik._TC is None:
            z = self.NOSE_C[2] - 0.0205; o = np.array([[s * 0.0042, -0.4, z] for s in (-1, 1)], F)
            hp = self.hit(o, np.tile(V(0, 1, 0), (2, 1))); Pik._TC = [h + V(0, 0.0032, -0.0038) for h in hp]
        return Pik._TC
    def teeth_fn(self, p):  # два зубика из-под верхней губки
        out = None
        for s, c in zip((-1, 1), self.teeth_centers()):
            q = rotx(p - c, -0.42)
            t = sd_ell(q, V(0, 0, 0), V(0.0036, 0.0016, 0.005)); t = smax(t, q[:, 2] - 0.0035, 0.0008)
            out = t if out is None else np.minimum(out, t)
        return out
    def bow_fn(self, p):    # бантик у правого ушка: два «крылышка» с складкой, узелок, два хвостика ленты
        c = V(0.064, -0.034, 0.512); q = p - c; q = roty(q, -0.38); q = rotx(q, 0.5)
        q2 = q.copy(); q2[:, 1] *= 2.0                                                    # плоский
        d = sd_ell(q, V(0, 0, 0), V(0.0105, 0.0088, 0.0105))
        for s in (-1, 1):
            w = sd_rcone(q2, V(s * 0.004, 0, 0), V(s * 0.027, 0, 0.0), 0.0075, 0.0165) / 2.0 * 1.4
            w = smax(w, -sd_ell(q, V(s * 0.03, -0.0075, 0), V(0.006, 0.004, 0.012)), 0.002)   # складочка на крылышке
            d = smin(d, w, 0.004)
            r = sd_rcone(q2, V(s * 0.003, 0.002, -0.006), V(s * 0.012, 0.004, -0.03), 0.0052, 0.0042) / 2.0 * 1.4
            d = smin(d, r, 0.003)
        return d
    def acc_fn(self, p): return self.bow_fn(p)
    ACCS = [{'name': 'bow', 'fn': 'bow_fn', 'box': ((0.01, -0.075, 0.46), (0.115, 0.01, 0.56)), 'mat': 'satin', 'col': (0.66, 0.02, 0.06), 'h': 0.0007},
            {'name': 'teeth', 'fn': 'teeth_fn', 'box': ((-0.014, -0.182, 0.338), (0.014, -0.14, 0.364)), 'mat': 'tooth', 'col': (0.86, 0.84, 0.8), 'h': 0.0004}]
    def mouth_lines(self):
        lines = []; nz = self.NOSE_C
        phil = [V(0, -0.4, nz[2] - 0.0112 - 0.0078 * i / 6) for i in range(7)]
        lines.append(self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1))))
        for s in (-1, 1):
            ang = np.linspace(0, math.pi, 12); xs = s * (0.0105 - 0.0105 * np.cos(ang)); zs = nz[2] - 0.019 - 0.0048 * np.sin(ang) + 0.003 * (xs * s / 0.021) ** 2
            lines.append(self.hit(np.stack([xs, np.full(12, -0.4, F), zs], -1).astype(F), np.tile(V(0, 1, 0), (12, 1))))
        return lines[:1] if self.MOUTH is not None else lines
    def whiskers(self):
        out = []
        for s in (-1, 1):
            for j, (dz, ang) in enumerate([(0.007, 0.16), (0.0, 0.0), (-0.007, -0.14)]):
                o = V(s * (0.013 + 0.004 * j), -0.4, 0.37 + dz); r0 = self.hit(o, V(0, 1, 0))[0] + V(0, 0.0015, 0)
                dirn = nrm(V(s * 1.0, -0.25, ang)); out.append(np.array([r0 + dirn * 0.1 * (k / 7) + V(0, 0.01 * (k / 7) ** 2, -0.01 * (k / 7) ** 2) for k in range(8)], F))
        return out
    WHISK_R = (0.0005, 0.00012); WHISK_COL = (0.88, 0.87, 0.86)
    # правила шерсти (для телефона): плотность и длина по областям 0..9 (9 — пальцы, у Пика их нет)
    FUR = {'K': 0.66e6, 'dens': [1.0, 1.15, 0.8, 1.4, 0.6, 1.0, 1.0, 0.0, 0.0, 0.0], 'L': [0.0072, 0.0052, 0.0032, 0.0026, 0.0026, 0.0052, 0.0058, 0.0, 0.0, 0.0],
           'lean': [1.22, 1.28, 1.35, 1.35, 1.2, 1.2, 1.2, 1.2, 0.5, 1.3], 'down': [0.3, 0.12, 0.1, 0.1, 0.1, 0.2, 0.2, 0.0, 0.0, 0.1], 'rad': 0.0005, 'radLid': 0.0004,
           'cell': 0.007, 'clump': 0.18, 'frontK': 0.5, 'ruff': None, 'earTip': None, 'chest': None, 'tailTip': None}
    def fur_src(self):
        return {'nose': self.NOSE_C.tolist(), 'earOff': [0, 0.08, -0.03], 'neck': (self.NECK + V(0, 0, 0.02)).tolist(), 'should': [s.tolist() for s in self.SHOULD], 'wrist': [s.tolist() for s in self.WRIST],
                'hip': [(h + V(0, 0, 0.04)).tolist() for h in self.HIP], 'foot': [f.tolist() for f in self.FOOT], 'tail': [t.tolist() for t in self.TAIL[::3]], 'H': self.H.tolist(), 'headR': float(self.HEAD_R[0])}

HERO = Pik()
