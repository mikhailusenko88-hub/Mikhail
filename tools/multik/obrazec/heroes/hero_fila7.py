# Филя, лепка 7 (18.11.2026) — в манере Пика и Рона (Михаил: «как Пик и Рон»): та же «рука», что у утверждённого Пика.
# Голова — шар со щёчками и макушкой, короткая мордочка-конус с подушечками и подбородком, глаза близко к носу,
# радужка небольшая, белка много (как у Пика), носик-бусинка, два зубика, короткий ровный мех. От обложек — узнаваемость:
# белый зайчонок, длинные уши с розовой серединкой, голубой вязаный шарф, румянец. Тело, лапы, шарф, хвост — прежние (hero_fila.py).
# Экспорт: MOD=fila7 python3 hero_export.py fila
from hero_fila import *
from hero_fila import Fila

class Fila7(Fila):
    NAME = 'fila'
    K = 1.15                                                                           # Филя крупнее Пика: все размеры головы — Пик × K
    H = V(0, -0.004, 0.465); HEAD_R = V(0.138, 0.124, 0.12)
    RE = 0.047; LID_OFF = 0.87; LID_K = 0.03; LID_NY = 0.12
    EYES = [V(s * 0.052, -0.095, 0.478) for s in (-1, 1)]                             # близко к носу, как у Пика
    IRIS = [(0.02, 0.01, 0.005), (0.12, 0.055, 0.018), (0.5, 0.27, 0.08)]            # тёплые карие с янтарём книзу (обложки 20, 22)
    IRIS_STYLE = 1
    EYE_K = (0.76, 0.935)                                                             # радужка маленькая, белка много (как у Пика)
    EYE_S = V(0.88, 1.0, 1.12)
    EYE_CENTER = (0.1, 0.45); EYE_AIM = V(0, -1.5, 0.48); EYE_DIV = 0.24
    EYE_TILT = (0.0, 0.0); EYE_RING = (0.05, 0.035, 0.03); EYE_RING_TOP = False; EYE_RING_R = 1.18   # всё лицо — как у Пика: без своих линий век и бровей
    LID_SH = None; LID_LINE = None; BROW = None
    SN_A = V(0, -0.067, 0.436); SN_B = V(0, -0.165, 0.42)
    NOSE_C = V(0, -0.181, 0.426)
    MOUTHS = {'a': (V(0, -0.145, 0.388), V(0.018, 0.023, 0.014)), 'o': (V(0, -0.145, 0.389), V(0.0104, 0.023, 0.0115))}
    TONGUE = (V(0, -0.14, 0.381), V(0.009, 0.014, 0.0046))
    PADS = [V(s * 0.019, -0.146, 0.405) for s in (-1, 1)]
    CHIN = V(0, -0.124, 0.384)
    BLUSH = [V(s * 0.083, -0.097, 0.414) for s in (-1, 1)]
    K_MUZ = 0.034; K_EAR = 0.026; K_TORSO = 0.055
    EAR_C = [V(s * 0.07, 0.03, 0.685) for s in (-1, 1)]
    def ear_sd(self, p, i, inner=False):                                              # длинное заячье ухо: стоит «галочкой», слегка назад, развёрнуто наружу
        s = 1 if i else -1
        q = roty(p - self.EAR_C[i], -s * 0.3); q = rotx(q, 0.12); q = rotz(q, -s * 0.28)
        if inner: return sd_ell(q, V(0, -0.016, 0.008), V(0.034, 0.008, 0.098))
        e = sd_ell(q, V(0, 0, 0), V(0.052, 0.024, 0.125))
        return smin(e, sd_ell(q, V(0, 0.002, -0.105), V(0.026, 0.02, 0.05)), 0.018)
    def ear_inner(self, p): return np.minimum(self.ear_sd(p, 0, True), self.ear_sd(p, 1, True))
    def head_sd_only(self, p):
        h = sd_ell(p, self.H, self.HEAD_R)
        for s in (-1, 1): h = smin(h, sd_ell(p, V(s * 0.058, -0.067, 0.417), V(0.069, 0.062, 0.058)), 0.052)     # пухлые щёчки
        return smin(h, sd_ell(p, V(0, 0.012, 0.53), V(0.115, 0.104, 0.069)), 0.058)                              # круглая макушка
    def parts(self, p):
        d = {}
        t = sd_ell(p, V(0, 0.007, 0.228), V(0.08, 0.072, 0.118))
        t = smin(t, sd_ell(p, V(0, -0.014, 0.166), V(0.098, 0.09, 0.086)), 0.045)                             # круглый животик
        t = smin(t, sd_cap(p, V(0, 0, 0.3), self.NECK + V(0, -0.004, 0.034), 0.043), 0.04)
        d['torso'] = t
        d['head'] = self.head_sd_only(p)
        m = sd_rcone(p, self.SN_A, self.SN_B, 0.057, 0.024)                                                    # короткая мордочка
        for c in self.PADS: m = smin(m, sd_sph(p, c, 0.0195), 0.014)                                          # подушечки с усами (верхняя губка «w»)
        m = smin(m, sd_ell(p, self.CHIN, V(0.022, 0.032, 0.0155)), 0.018)                                     # маленький подбородок
        d['muzzle'] = m
        d['lid'] = self.lid(p)
        d['ear'] = np.minimum(self.ear_sd(p, 0), self.ear_sd(p, 1))
        d['arm'] = np.minimum(self.arm_sd(p, 0), self.arm_sd(p, 1))
        d['leg'] = np.minimum(self.leg_sd(p, 0), self.leg_sd(p, 1))
        tl = None
        for i in range(len(self.TAIL) - 1):
            x = sd_rcone(p, self.TAIL[i], self.TAIL[i + 1], self.TAIL_R[i], self.TAIL_R[i + 1]); tl = x if tl is None else smin(tl, x, 0.01)
        d['tail'] = tl
        return d
    def colors(self, p, reg0, nor):
        """Белый зайчонок (чуть холоднее, без желтизны), спинка чуть серее, румянец, розовые серединки ушей, подушечки и рот."""
        N = len(p); x, y, z = p[:, 0], p[:, 1], p[:, 2]; w = wob(p, 1.6) * 0.5
        reg = np.where((reg0 == 9) | (reg0 == 12), np.where(z > 0.12, 5, 6), reg0)
        white = V(0.82, 0.81, 0.8); pink = V(0.86, 0.5, 0.55); blush = V(0.8, 0.5, 0.55)
        k = np.clip(0.97 + 0.05 * w - 0.1 * np.clip(y * 6, 0, 1), 0.82, 1.04)
        fur = white[None] * k[:, None]
        for B in self.BLUSH:                                                                                   # румянец под глазками
            b = np.clip((1.0 - np.linalg.norm((p - B) / V(0.034, 0.034, 0.025), axis=-1)) * 2.5, 0, 1) * ((reg == 1) | (reg == 2))
            fur = fur * (1 - 0.55 * b[:, None]) + blush[None] * (0.55 * b[:, None])
        skin = fur * 0.9
        skin = np.where((reg == 8)[:, None], pink[None] * (0.95 + 0.05 * w[:, None]), skin)
        skin = np.where((reg == 10)[:, None], V(0.16, 0.03, 0.03)[None], np.where((reg == 11)[:, None], V(0.75, 0.3, 0.34)[None], skin))
        skin = np.where((reg0 == 12)[:, None], V(0.84, 0.5, 0.54)[None] * (0.95 + 0.05 * w[:, None]), skin)
        return skin.astype(F), fur.astype(F)
    def fur_ok(self, p, reg):
        ok = ((reg != 8) & (reg != 10) & (reg != 11) & (reg != 12) & (reg != 2)) | ((reg == 2) & (p[:, 1] > -0.165))
        for E in self.EYES: ok &= self.eye_d(p, E) > self.RE + 0.004
        ok &= np.linalg.norm(p - self.NOSE_C, axis=-1) > 0.024
        ok &= self.scarf_fn(p) > 0.0015
        return ok
    def nose_fn(self, p):   # носик-бусинка, как у Пика (× K)
        c = self.NOSE_C; k = self.K; q = c + (p - c) / k
        d = sd_ell(q, c, V(0.0138, 0.0112, 0.0115))
        d = smin(d, sd_ell(q, c + V(0, 0.004, 0.005), V(0.008, 0.009, 0.0055)), 0.004)
        for s in (-1, 1): d = smax(d, -sd_ell(q, c + V(s * 0.0055, -0.0106, -0.0038), V(0.0018, 0.0016, 0.0012)), 0.0012)
        return d * k
    NOSE_COL = (0.9, 0.47, 0.55)
    _TC7 = None
    def teeth_centers(self):
        if Fila7._TC7 is None:
            z = self.NOSE_C[2] - 0.0236; o = np.array([[s * 0.0048, -0.4, z] for s in (-1, 1)], F)
            hp = self.hit(o, np.tile(V(0, 1, 0), (2, 1))); Fila7._TC7 = [h + V(0, 0.0037, -0.0044) for h in hp]
        return Fila7._TC7
    def teeth_fn(self, p):  # два зубика из-под верхней губки
        out = None
        for s, c in zip((-1, 1), self.teeth_centers()):
            q = rotx(p - c, -0.42)
            t = sd_ell(q, V(0, 0, 0), V(0.0041, 0.0018, 0.0058)); t = smax(t, q[:, 2] - 0.004, 0.0009)
            out = t if out is None else np.minimum(out, t)
        return out
    ACCS = [Fila.ACCS[0]]                                                             # без зубиков (Михаил 18.11: у наших зверей зубов нет)
    def mouth_lines(self):
        lines = []; nz = self.NOSE_C; k = self.K
        phil = [V(0, -0.4, nz[2] - (0.0112 + 0.0078 * i / 6) * k) for i in range(7)]
        lines.append(self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1))))
        for s in (-1, 1):
            ang = np.linspace(0, math.pi, 12); xs = s * (0.0105 - 0.0105 * np.cos(ang)) * k; zs = nz[2] - (0.019 + 0.0048 * np.sin(ang)) * k + 0.003 * k * (xs * s / (0.021 * k)) ** 2
            lines.append(self.hit(np.stack([xs, np.full(12, -0.4, F), zs], -1).astype(F), np.tile(V(0, 1, 0), (12, 1))))
        return lines[:1] if self.MOUTH is not None else lines
    def whiskers(self):
        out = []; z0 = float(self.PADS[0][2]) + 0.01
        for s in (-1, 1):
            for j, (dz, ang) in enumerate([(0.008, 0.16), (0.0, 0.0), (-0.008, -0.14)]):
                o = V(s * (0.015 + 0.0046 * j), -0.4, z0 + dz); r0 = self.hit(o, V(0, 1, 0))[0] + V(0, 0.0015, 0)
                dirn = nrm(V(s * 1.0, -0.25, ang)); out.append(np.array([r0 + dirn * 0.115 * (k / 7) + V(0, 0.011 * (k / 7) ** 2, -0.011 * (k / 7) ** 2) for k in range(8)], F))
        return out
    WHISK_R = (0.0005, 0.00012); WHISK_COL = (0.88, 0.87, 0.86)
    FUR = {'K': 0.66e6, 'dens': [1.0, 1.15, 0.85, 1.4, 0.8, 1.0, 1.0, 1.1, 0.0, 1.0], 'L': [0.009, 0.0062, 0.0035, 0.0028, 0.0032, 0.006, 0.0065, 0.016, 0.0, 0.0035],
           'lean': [1.22, 1.28, 1.35, 1.35, 1.2, 1.2, 1.2, 1.0, 0.5, 1.3], 'down': [0.3, 0.12, 0.1, 0.1, 0.1, 0.2, 0.2, 0.0, 0.0, 0.1], 'rad': 0.0005, 'radLid': 0.0004,
           'cell': 0.007, 'clump': 0.18, 'frontK': 0.5, 'ruff': None, 'earTip': None, 'chest': None, 'tailTip': None}

HERO = Fila7()
