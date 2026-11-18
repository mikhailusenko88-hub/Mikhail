# Топа, лепка 7 (18.11.2026) — в манере Рона и Пика (Михаил: «как Пик и Рон»): та же «рука», что у утверждённого Рона.
# Голова — шар со щеками и лбом, короткая широкая светлая морда-конус с переносицей, брылями и подбородком, крупный тёмный нос,
# глаза над мордой с большой радужкой (без «испуга»), круглые ушки на макушке, мех как у Рона. От обложек — узнаваемость:
# бурый медвежонок, светлая мордочка и животик, зелёный вязаный шарф. Тело, лапы, шарф, хвост — прежние (hero_topa.py).
# Экспорт: MOD=topa7 python3 hero_export.py topa
from hero_topa import *
from hero_topa import Topa

class Topa7(Topa):
    NAME = 'topa'
    H = V(0, 0.0, 0.68); HEAD_R = V(0.178, 0.162, 0.158)
    RE = 0.05; LID_OFF = 0.9; LID_K = 0.04; LID_NY = 0.12                           # веко поднято: взгляд открытый, не сонный
    EYES = [V(s * 0.068, -0.121, 0.705) for s in (-1, 1)]                            # над мордой, ближе к носу, как у Рона
    IRIS = [(0.03, 0.015, 0.006), (0.2, 0.1, 0.035), (0.44, 0.25, 0.09)]             # тёплые карие, как у Рона
    IRIS_STYLE = 0
    EYE_K = (0.70, 0.915)                                                            # большая радужка, как у Рона — взгляд добрый, не испуганный
    EYE_S = V(0.9, 1.0, 1.1)
    EYE_CENTER = (0.1, 0.45); EYE_AIM = V(0, -1.6, 0.72); EYE_DIV = 0.2
    EYE_TILT = (0.0, 0.0); EYE_RING = (0.05, 0.035, 0.03); EYE_RING_TOP = False; EYE_RING_R = 1.18
    LID_SH = None; LID_LINE = None; BROW = None
    SN_A = V(0, -0.09, 0.636); SN_B = V(0, -0.2, 0.615)
    NOSE_C = V(0, -0.233, 0.634)
    MOUTHS = {'a': (V(0, -0.206, 0.589), V(0.036, 0.036, 0.022)), 'o': (V(0, -0.207, 0.589), V(0.021, 0.036, 0.022))}
    TONGUE = (V(0, -0.177, 0.573), V(0.02, 0.027, 0.006))
    LIP_Z = 0.594
    BLUSH = [V(s * 0.115, -0.11, 0.645) for s in (-1, 1)]
    K_MUZ = 0.045; K_EAR = 0.03; K_TORSO = 0.075
    EAR_C = [V(s * 0.14, 0.012, 0.81) for s in (-1, 1)]
    def ear_sd(self, p, i, inner=False):                                             # круглое медвежье ушко
        s = 1 if i else -1
        q = rotz(p - self.EAR_C[i], -s * 0.3); q = rotx(q, 0.1); q = roty(q, s * 0.35)
        if inner: return sd_ell(q, V(0, -0.017, -0.004), V(0.036, 0.01, 0.034))
        return sd_ell(q, V(0, 0, 0), V(0.058, 0.027, 0.055))
    def ear_inner(self, p): return np.minimum(self.ear_sd(p, 0, True), self.ear_sd(p, 1, True))
    def parts(self, p):
        d = {}
        t = sd_ell(p, V(0, 0.006, 0.3), V(0.16, 0.146, 0.185))
        t = smin(t, sd_ell(p, V(0, -0.03, 0.385), V(0.142, 0.128, 0.125)), 0.06)          # грудь
        t = smin(t, sd_ell(p, V(0, -0.012, 0.2), V(0.166, 0.152, 0.115)), 0.06)           # круглый живот
        t = smin(t, sd_cap(p, V(0, 0, 0.45), self.NECK + V(0, -0.005, 0.05), 0.082), 0.05)
        d['torso'] = t
        h = sd_ell(p, self.H, self.HEAD_R)
        for s in (-1, 1): h = smin(h, sd_ell(p, V(s * 0.09, -0.075, 0.63), V(0.1, 0.085, 0.08)), 0.055)    # щёки
        h = smin(h, sd_ell(p, V(0, -0.02, 0.75), V(0.13, 0.11, 0.08)), 0.055)                             # лоб и макушка
        d['head'] = h
        m = sd_rcone(p, self.SN_A, self.SN_B, 0.075, 0.05)                                                 # короткая широкая морда
        m = smin(m, sd_cap(p, V(0, -0.13, 0.664), V(0, -0.205, 0.642), 0.026), 0.03)                      # переносица
        for s in (-1, 1): m = smin(m, sd_ell(p, V(s * 0.03, -0.196, 0.597), V(0.036, 0.042, 0.03)), 0.026) # брыли (подушечки)
        m = smin(m, sd_ell(p, V(0, -0.168, 0.566), V(0.032, 0.048, 0.02)), 0.026)                         # подбородок
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
    def fur_ok(self, p, reg):
        ok = (reg != 10) & (reg != 11) & (reg != 8) & (reg != 12)
        for E in self.EYES: ok &= self.eye_d(p, E) > self.RE + 0.005
        ok &= np.linalg.norm(p - self.NOSE_C, axis=-1) > 0.036
        ok &= self.scarf_fn(p) > 0.0015
        return ok
    def mouth_lines(self):   # как у Рона (× 0,85: морда короче)
        lines = []; nz = self.NOSE_C; k = 0.85
        phil = [V(0, -0.5, nz[2] - (0.026 + 0.02 * i / 6) * k) for i in range(7)]
        ph = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6)
        if self.MOUTH is not None:
            m0 = self.MOUTH; self.MOUTH = None; pb = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6); self.MOUTH = m0
            keep = np.linalg.norm(ph - pb, axis=-1) < 0.003; ph = ph[keep] if keep.sum() >= 2 else pb[:2]
        lines.append(ph)
        for s in (-1, 1):
            ang = np.linspace(0, math.pi, 12); xs = s * (0.026 - 0.026 * np.cos(ang)) * k; zs = nz[2] - (0.047 + 0.012 * np.sin(ang)) * k
            lines.append(self.hit(np.stack([xs, np.full(12, -0.5, F), zs], -1).astype(F), np.tile(V(0, 1, 0), (12, 1)), 0.6))
        return lines[:1] if self.MOUTH is not None else lines
    FUR = {'K': 0.62e6, 'dens': [1.0, 1.1, 1.0, 1.4, 0.9, 1.0, 1.0, 1.05, 0.0, 1.1], 'L': [0.012, 0.008, 0.005, 0.0038, 0.005, 0.0095, 0.0105, 0.016, 0.0, 0.0045],   # мех мягче и тоньше, чем у Рона: бурый ворс не «щетина»
           'lean': [1.22, 1.26, 1.35, 1.35, 1.3, 1.22, 1.22, 1.05, 0.5, 1.32], 'down': [0.35, 0.2, 0.15, 0.1, 0.4, 0.2, 0.2, 0.0, 0.0, 0.1], 'rad': 0.0006, 'radLid': 0.00045,
           'cell': 0.01, 'clump': 0.2, 'frontK': 0.5, 'ruff': None, 'earTip': None, 'chest': [0.0, -0.06, 0.41, 1.2], 'tailTip': None}

HERO = Topa7()
