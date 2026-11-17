# Топа — бурый медвежонок с зелёным вязаным шарфом (рост до макушки ~0.84 м). Пухлый малыш: большая круглая голова, маленькие круглые
# уши, короткая светлая мордочка с крупным чёрным носом, тёмные глаза, румянец, светлый животик, толстые короткие лапы с пальцами
# и тёмными подушечками, хвостик-пуговка.
# Лепка 3 (17.11.2026): лицо прежнего Топы — огромные тёмные блестящие глаза, румянец, светлая мордочка с улыбкой, насыщенно-бурый мех, толстый шарф.
from hero_common import *

class Topa(Hero):
    NAME = 'topa'
    H = V(0, 0.0, 0.67); HEAD_R = V(0.205, 0.185, 0.178)
    RE = 0.056; LID_OFF = 0.93; LID_K = 0.02                     # глаза большие, но сидят в голове, взгляд спокойный и добрый
    EYES = [V(s * 0.084, -0.138, 0.692) for s in (-1, 1)]
    IRIS = [(0.012, 0.006, 0.003), (0.07, 0.03, 0.012), (0.38, 0.18, 0.05)]      # медовые карие: сверху темнее, книзу светятся
    IRIS_STYLE = 1
    EYE_K = (0.64, 0.885)                                                         # большая радужка и большой зрачок, белок виден по краям
    EYE_AIM = V(0, -1.6, 0.7); EYE_DIV = 0.18
    EYE_CENTER = (0.6, 0.5)
    EYE_S = V(0.9, 1.0, 1.1)
    EYE_RING = (0.07, 0.035, 0.02)
    BROW = {'up': 1.24, 'w': 0.58, 'r': [0.0066, 0.0036], 'col': (0.06, 0.026, 0.011)}      # короткие густые бровки ближе к глазам
    SHOULD = [V(s * 0.128, -0.03, 0.44) for s in (-1, 1)]
    WRIST = [V(s * 0.186, -0.092, 0.292) for s in (-1, 1)]
    PAW = [V(s * 0.192, -0.106, 0.264) for s in (-1, 1)]
    HIP = [V(s * 0.092, 0.005, 0.15) for s in (-1, 1)]
    FOOT = [V(s * 0.1, -0.075, 0.036) for s in (-1, 1)]
    TAIL = [V(0, 0.135, 0.19), V(0, 0.165, 0.205), V(0, 0.18, 0.215)]
    TAIL_R = [0.036, 0.04, 0.032]
    NECK = V(0, -0.01, 0.495)
    SN_A = V(0, -0.115, 0.615); SN_B = V(0, -0.208, 0.606)
    NOSE_C = V(0, -0.252, 0.64)
    MOUTHS = {'a': (V(0, -0.214, 0.57), V(0.046, 0.042, 0.028)), 'o': (V(0, -0.216, 0.571), V(0.027, 0.042, 0.028))}
    TONGUE = (V(0, -0.184, 0.552), V(0.025, 0.032, 0.007))
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
        if inner: return sd_ell(q, V(0, -0.018, -0.002), V(0.043, 0.012, 0.041))
        return sd_ell(q, V(0, 0, 0), V(0.072, 0.03, 0.068))
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
        h = sd_ell(p, self.H, self.HEAD_R)
        for s in (-1, 1): h = smin(h, sd_ell(p, V(s * 0.115, -0.075, 0.625), V(0.11, 0.098, 0.092)), 0.06)   # щёки
        h = smin(h, sd_ell(p, V(0, -0.008, 0.76), V(0.15, 0.13, 0.085)), 0.055)                               # круглый лоб
        d['head'] = h
        m = sd_rcone(p, self.SN_A, self.SN_B, 0.09, 0.068)                                                    # короткая широкая морда
        m = smin(m, sd_ell(p, V(0, -0.2, 0.636), V(0.052, 0.05, 0.03)), 0.03)                                   # переносица к носу
        for s in (-1, 1): m = smin(m, sd_ell(p, V(s * 0.036, -0.218, 0.59), V(0.043, 0.047, 0.034)), 0.028)    # губы-подушечки
        m = smin(m, sd_ell(p, V(0, -0.178, 0.556), V(0.038, 0.056, 0.023)), 0.028)                            # подбородок
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
    def colors(self, p, reg0, nor):
        """Бурый медвежонок: светлая мордочка и животик, уши внутри светлее, румянец, тёмные подушечки."""
        N = len(p); x, y, z = p[:, 0], p[:, 1], p[:, 2]; w = wob(p, 1.3) * 0.5
        reg = np.where((reg0 == 9) | (reg0 == 12), np.where(z > 0.15, 5, 6), reg0)
        brown = V(0.23, 0.085, 0.022); cream = V(0.62, 0.47, 0.3); blush = V(0.72, 0.26, 0.26)   # в кадре мех выходит примерно в полтора раза светлее заданного
        k = np.clip(0.94 + 0.1 * w - 0.14 * np.clip(y * 5, 0, 1), 0.68, 1.1); fur = brown[None] * k[:, None]
        wm = np.zeros(N, F)
        wm = np.maximum(wm, np.clip((1.1 - np.linalg.norm((p - V(0, -0.12, 0.27)) / V(0.105, 0.08, 0.15), axis=-1)) * 4, 0, 1) * (reg == 0))   # животик
        wm = np.maximum(wm, (reg == 2).astype(F))                                                                                           # мордочка
        fur = fur * (1 - wm[:, None]) + cream[None] * wm[:, None]
        for s in (-1, 1):                                                                                                                   # румянец
            b = np.clip((1.0 - np.linalg.norm((p - V(s * 0.146, -0.13, 0.612)) / V(0.046, 0.046, 0.032), axis=-1)) * 2.5, 0, 1) * (reg == 1)
            fur = fur * (1 - 0.58 * b[:, None]) + blush[None] * (0.58 * b[:, None])
        skin = fur * 0.9
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
        ok &= np.linalg.norm(p - self.NOSE_C, axis=-1) > 0.044
        ok &= self.scarf_fn(p) > 0.0015                                # мех растёт вплотную к шарфу — без голой полоски на шее
        return ok
    def nose_fn(self, p):   # крупный мягкий нос-«фасолина» с ноздрями
        c = self.NOSE_C; d = sd_ell(p, c, V(0.04, 0.024, 0.027))
        d = smin(d, sd_ell(p, c + V(0, 0.004, -0.02), V(0.012, 0.015, 0.013)), 0.01)
        for s in (-1, 1): d = smax(d, -sd_ell(p, c + V(s * 0.016, -0.022, -0.003), V(0.0075, 0.0065, 0.005)), 0.003)
        return d
    NOSE_COL = (0.035, 0.022, 0.018); NOSE_WET = False     # тёмно-шоколадный, с мягким бликом (не «хром»)
    def mouth_lines(self):
        lines = []; nz = self.NOSE_C
        phil = [V(0, -0.5, nz[2] - 0.03 - 0.022 * i / 6) for i in range(7)]
        ph = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6)
        if self.MOUTH is not None:
            m0 = self.MOUTH; self.MOUTH = None; pb = self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1)), 0.6); self.MOUTH = m0
            keep = np.linalg.norm(ph - pb, axis=-1) < 0.003; ph = ph[keep] if keep.sum() >= 2 else pb[:2]
        lines.append(ph)
        for s in (-1, 1):
            ang = np.linspace(0, math.pi, 12); xs = s * (0.03 - 0.03 * np.cos(ang)); zs = nz[2] - 0.05 - 0.012 * np.sin(ang) + 0.016 * (xs * s / 0.06) ** 2   # улыбка: уголки вверх
            lines.append(self.hit(np.stack([xs, np.full(12, -0.5, F), zs], -1).astype(F), np.tile(V(0, 1, 0), (12, 1)), 0.6))
        return lines[:1] if self.MOUTH is not None else lines
    def whiskers(self):   # у медвежонка усов почти нет — по две короткие щетинки
        out = []
        for s in (-1, 1):
            for j, (dz, ang) in enumerate([(0.006, 0.12), (-0.006, -0.1)]):
                o = V(s * (0.036 + 0.008 * j), -0.5, 0.592 + dz); r0 = self.hit(o, V(0, 1, 0), 0.6)[0] + V(0, 0.002, 0)
                dirn = nrm(V(s * 1.0, -0.5, ang)); out.append(np.array([r0 + dirn * 0.035 * (k / 7) + V(0, 0.004 * (k / 7) ** 2, -0.006 * (k / 7) ** 2) for k in range(8)], F))
        return out
    WHISK_R = (0.0007, 0.0002); WHISK_COL = (0.16, 0.1, 0.07)
    FUR = {'K': 0.56e6, 'dens': [1.0, 1.1, 1.0, 1.4, 1.0, 1.0, 1.0, 1.05, 0.0, 1.1], 'L': [0.015, 0.011, 0.006, 0.004, 0.007, 0.013, 0.014, 0.018, 0.0, 0.0055],
           'lean': [1.15, 1.2, 1.35, 1.35, 1.25, 1.18, 1.18, 1.0, 0.5, 1.32], 'down': [0.35, 0.2, 0.15, 0.1, 0.1, 0.22, 0.22, 0.0, 0.0, 0.1], 'rad': 0.00085, 'radLid': 0.0006,
           'cell': 0.012, 'clump': 0.2, 'frontK': 0.5, 'spec': 0.08, 'gold': 0.1, 'ruff': [0.125, 0.56, 0.68, 10.0, 0.8, -0.2], 'earTip': None, 'chest': [0.0, -0.06, 0.41, 1.2], 'tailTip': None}
    def fur_src(self):
        return {'nose': self.NOSE_C.tolist(), 'earOff': [0, 0.1, 0.1], 'neck': (self.NECK + V(0, 0, 0.03)).tolist(), 'should': [s.tolist() for s in self.SHOULD], 'wrist': [s.tolist() for s in self.WRIST],
                'hip': [(h + V(0, 0, 0.06)).tolist() for h in self.HIP], 'foot': [f.tolist() for f in self.FOOT], 'tail': [t.tolist() for t in self.TAIL], 'H': self.H.tolist(), 'headR': float(self.HEAD_R[0])}

HERO = Topa()
