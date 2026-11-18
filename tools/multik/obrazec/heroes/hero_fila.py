# Филя — маленький белый зайчонок с голубым вязаным шарфом (рост до макушки ~0.58 м, с ушами ~0.84 м). Малыш: большая круглая голова,
# длинные стоячие уши с розовой серединкой, крупные тёмные глаза, короткая мордочка с розовым носиком и двумя зубиками, румянец,
# худенькое тельце, пушистые лапки с пальчиками, длинные заячьи ступни, хвостик-помпон.
# Лепка 3 (17.11.2026): лицо прежнего Фили — огромные тёмные блестящие глаза, румянец, улыбка, кремовый мех, толстый шарф.
from hero_common import *

class Fila(Hero):
    NAME = 'fila'
    def hit(self, o, dirn, tmax=0.4): return self.hit2(o, dirn, tmax)   # линии рта и усы — точно на поверхности
    H = V(0, -0.004, 0.465); HEAD_R = V(0.158, 0.138, 0.13)                       # по сетке с обложки 20: голова приземистая, лоб не выше 0,35 ширины                       # голова-«моти»: шире, чем выше (как на обложках 20–22)
    RE = 0.0428; LID_OFF = 0.99; LID_K = 0.03; LID_NY = 0.12       # глаза большие, но сидят в голове (наружу ~40% радиуса), а не «навыкате»
    EYES = [V(s * 0.062, -0.112, 0.462) for s in (-1, 1)]      # по обложкам: между глазами ~0,6 ширины глаза, нос — между ними, чуть ниже
    IRIS = [(0.02, 0.008, 0.003), (0.16, 0.07, 0.02), (0.66, 0.36, 0.09)]       # тёплые янтарно-карие, книзу светятся (обложки 20, 22)          # карие с янтарём книзу (обложки 20–22)
    IRIS_STYLE = 1
    EYE_K = (0.834, 0.968)                                                          # радужка ~0,72 ширины глаза, зрачок ~0,36 — как на обложках                                                         # большая радужка и большой зрачок, белок виден по краям
    EYE_S = V(1.0, 1.0, 0.928)                                                    # вытянутый вверх овал
    EYE_CENTER = (0.1, 0.45); EYE_TILT = (4.0, -14.3)                              # взгляд чуть вниз — над радужкой больше белка (обложки)                                                       # радужка почти по центру видимой части глаза: белок ровным ободком
    EYE_AIM = V(0, -1.5, 0.48); EYE_DIV = 0.2
    EYE_RING = (0.05, 0.035, 0.035); EYE_RING_TOP = True; EYE_RING_R = 1.07
    LID_SH = 0.45
    LID_LINE = {'r': (0.0016, 0.0034), 'col': (0.035, 0.025, 0.025), 'off': 1.05, 'flick': 0.22, 'lashes': 3}   # тёмная линия ресниц с «хвостиком» у внешнего уголка (обложки 20–22)                           # только линия ресниц сверху                                                  # мягкая подводка, без «тёмных кругов»
    BROW = {'up': 1.62, 'w': 0.78, 'tilt': 0.0, 'r': [0.0058, 0.0026], 'col': (0.32, 0.25, 0.22)}   # tilt — внутренний конец выше: «домик» мягкий, не сердитый (обложки)        # короткие мягкие бровки ближе к глазам                                                  # подводка у глаз мягче, чем у серых героев: мех белый
    SHOULD = [V(s * 0.063, -0.018, 0.293) for s in (-1, 1)]
    WRIST = [V(s * 0.096, -0.067, 0.215) for s in (-1, 1)]
    PAW = [V(s * 0.1, -0.075, 0.198) for s in (-1, 1)]
    HIP = [V(s * 0.05, 0.0045, 0.118) for s in (-1, 1)]
    FOOT = [V(s * 0.057, -0.062, 0.026) for s in (-1, 1)]
    TAIL = [V(0, 0.072, 0.118), V(0, 0.1, 0.132), V(0, 0.12, 0.142)]
    TAIL_R = [0.03, 0.041, 0.034]
    NECK = V(0, -0.007, 0.347)
    SN_A = V(0, -0.09, 0.431); SN_B = V(0, -0.133, 0.426)
    NOSE_C = V(0, -0.154, 0.447)                                                  # нос на высоте нижней части глаз (обложки 20, 22)                                                   # нос почти на уровне глаз (обложки)
    MOUTHS = {'a': (V(0, -0.135, 0.406), V(0.017, 0.02, 0.013)), 'o': (V(0, -0.135, 0.407), V(0.0095, 0.02, 0.011))}
    TONGUE = (V(0, -0.129, 0.4), V(0.0085, 0.012, 0.004))
    PIV = {'head': V(0, -0.007, 0.35), 'armL': SHOULD[0], 'armR': SHOULD[1], 'tail': TAIL[0]}
    BOX = {'head': ((-0.225, -0.25, 0.325), (0.225, 0.17, 0.905)), 'body': ((-0.14, -0.13, 0.03), (0.14, 0.13, 0.41)),
           'armL': ((-0.15, -0.125, 0.15), (-0.02, 0.045, 0.345)), 'armR': ((0.02, -0.125, 0.15), (0.15, 0.045, 0.345)), 'tail': ((-0.075, 0.025, 0.055), (0.075, 0.185, 0.205)),
           'feet': ((-0.115, -0.17, -0.01), (0.115, 0.07, 0.085))}
    ANKLE = 0.06
    STEP = {'head': 0.0024, 'body': 0.0024, 'tail': 0.002, 'armL': 0.0013, 'armR': 0.0013, 'feet': 0.0013}
    NECK_PLUG = (V(0, -0.007, 0.335), V(0, -0.009, 0.4), 0.045)
    K_MUZ = 0.032; K_EAR = 0.03; K_TORSO = 0.055

    EAR_C = [V(s * 0.108, 0.026, 0.68) for s in (-1, 1)]; EAR_BEND = 0.0
    def ear_sd(self, p, i, inner=False):
        s = 1 if i else -1
        q = roty(p - self.EAR_C[i], -s * 0.42); q = rotx(q, 0.1); q = rotz(q, -s * 0.3)       # врозь «галочкой» и чуть назад, развёрнуты наружу
        if i == 1 and self.EAR_BEND:                                                            # (выключено) правое ушко с загнутым кончиком
            zz = q[:, 2] - 0.03; a = np.clip(zz / 0.09, 0, 1) * self.EAR_BEND; cs, sn = np.cos(a), np.sin(a)
            q = np.stack([q[:, 0] * cs - zz * sn, q[:, 1], q[:, 0] * sn + zz * cs + 0.03], -1).astype(F)
        if inner: return sd_ell(q, V(0, -0.019, 0.004), V(0.05, 0.01, 0.094))
        e = sd_ell(q, V(0, 0, 0), V(0.075, 0.03, 0.122))                                    # широкое ухо-«листик»
        return smin(e, sd_ell(q, V(0, 0.002, -0.105), V(0.032, 0.022, 0.055)), 0.02)                 # корень уха толще
    # ---- голова, вылепленная как форма (лепка 5, 18.11.2026): «овал лица» с выпуклостью, нос на её вершине ----
    # радиус головы по направлению из центра C: асимметричный эллипсоид (лоб/затылок/макушка/низ) + мягкие «нашлёпки»
    # A·exp(-(1-cos угла)/w) — как глина пальцем: выпуклость лица, щёки, подушечки, лоб. Так лицо не плоское, а выпуклое.
    FORM = dict(C=V(0, -0.004, 0.462), n=2.15, nz=2.1, Rx=0.16, RyF=0.104, RyB=0.118, RzT=0.13, RzB=0.122,   # голова шире, чем глубже: широкое плоское лицо (обложки 20, 22, 26)
                bumps=[  # (рыскание°, тангаж°, A м, w, зеркально)
                    (0, -12, 0.022, 0.05, False),   # кончик мордочки под носом
                    (0, -20, 0.034, 0.22, False),   # пухлый «холмик» нижней половины лица — вперёд (обложки 20, 22 в 3/4: дальний глаз прячется за ним)
                    (38, -24, 0.03, 0.12, True),    # пухлые щёки вперёд-вбок под глазами
                    (70, -22, 0.026, 0.12, True),   # щёки вширь внизу головы
                    (0, 30, 0.01, 0.1, False),      # круглый лоб
                    (0, -42, -0.012, 0.03, False),  # под ртом форма уходит назад — короткий подбородок
                ])
    NOSE_P, LIP_P = -9, -22; NOSE_Z, LIP_Zf = 0.4266, 0.3873                                                        # где нос и рот на форме (тангаж°)
    EYE_DIR = (33, 3); EYE_XZ = (0.0691, 0.4643)                                      # глаза: по месту на лице (м)                                                               # где глаза на форме (рыскание°, тангаж°)
    EYE_OUT = 0.3                                                                   # насколько глаз выступает из формы (доля радиуса)
    @staticmethod
    def _dir(yaw, pitch):
        a, b = math.radians(yaw), math.radians(pitch); return V(math.sin(a) * math.cos(b), -math.cos(a) * math.cos(b), math.sin(b))
    def form_r(self, dd):
        Fm = self.FORM; dx, dy, dz = dd[:, 0], dd[:, 1], dd[:, 2]
        Ry = np.where(dy < 0, Fm['RyF'], Fm['RyB']); Rz = np.where(dz > 0, Fm['RzT'], Fm['RzB'])
        n = Fm.get('n', 2.0)   # n > 2 — «моти»: широкий плоский перед лица по горизонтали, глаза смотрят вперёд, а не в стороны
        h = (np.abs(dx / Fm['Rx']) ** n + np.abs(dy / Ry) ** n) ** (2.0 / n)
        nz = Fm.get('nz', 2.0); r = 1.0 / (h ** (nz / 2.0) + np.abs(dz / Rz) ** nz) ** (1.0 / nz)   # nz > 2 — макушка шире, голова «моти»
        for yaw, pitch, A, w, mir in Fm['bumps']:
            for sg in ((-1, 1) if mir else (1,)):
                u = self._dir(sg * yaw, pitch); r = r + A * np.exp(-(1.0 - dd @ u) / w)
        return r
    def head_form(self, p):
        q = p - self.FORM['C']; n = np.maximum(np.linalg.norm(q, axis=-1), 1e-6); return ((n - self.form_r(q / n[:, None])) * 0.88).astype(F)
    def surf(self, yaw, pitch):
        u = self._dir(yaw, pitch); return self.FORM['C'] + u * float(self.form_r(u[None])[0]), u
    def place_face(self):
        cls = type(self)
        out = []
        for sg in (-1, 1):   # глаз ставится по месту на лице (x, z), а не по углу: так на широкой плоской голове глаза не сбегаются к носу
            ex, ez = self.EYE_XZ; o = V(sg * ex, -0.6, ez); t = 0.0
            for _ in range(200):
                d = float(self.head_form((o + V(0, t, 0))[None])[0])
                if d < 0.0003: break
                t += d * 0.9
            S = o + V(0, t, 0); e = 0.0008; g = V(*[float(self.head_form((S + dv)[None])[0] - self.head_form((S - dv)[None])[0]) for dv in (V(e, 0, 0), V(0, e, 0), V(0, 0, e))]); u = g / np.linalg.norm(g)
            c0 = S - u * self.RE * (1.0 - self.EYE_OUT) * float(self.EYE_S[1]); c0[0] = sg * ex; c0[2] = ez; out.append(c0.astype(F))   # центр глаза ровно за точкой (x, z)
        cls.EYES = out
        def front(z):
            o = V(0, -0.6, z); t = 0.0
            for _ in range(200):
                d = float(self.head_form((o + V(0, t, 0))[None])[0])
                if d < 0.0003: break
                t += d * 0.9
            return o + V(0, t, 0)
        S = front(self.NOSE_Z); u = nrm(S - self.FORM['C']); cls.NOSE_C = (S + u * 0.003).astype(F); cls.NOSE_N = u
        cls.PADS = [(self.surf(sg * 13, self.NOSE_P - 8)[0] - self.surf(sg * 13, self.NOSE_P - 8)[1] * 0.0125).astype(F) for sg in (-1, 1)]
        S = front(self.LIP_Zf); u = nrm(S - self.FORM['C']); Sc = front(self.LIP_Zf - 0.03); cls.CHIN = (Sc - nrm(Sc - self.FORM['C']) * 0.011).astype(F)
        mc = (S - u * 0.004).astype(F); cls.MOUTHS = {'a': (mc, V(0.017, 0.02, 0.013)), 'o': (mc + V(0, 0, 0.001), V(0.0095, 0.02, 0.011))}
        cls.TONGUE = ((mc + V(0, 0.006, -0.006)).astype(F), V(0.0085, 0.012, 0.004))
        cls.BLUSH = [self.surf(sg * 44, -12)[0] for sg in (-1, 1)]
        cls.SN_A = self.FORM['C']; cls.SN_B = self.NOSE_C; cls.LIP_Z = float(mc[2] + 0.012)
        nz, ny = float(self.NOSE_C[2]), float(self.NOSE_C[1])
        cls.ACCS = [dict(a) for a in cls.ACCS if a['name'] != 'teeth']                 # зубиков на обложках не видно — убраны
        cls._TC = None
    def ear_inner(self, p): return np.minimum(self.ear_sd(p, 0, True), self.ear_sd(p, 1, True))
    TUFT_A = 0.0                                                   # хохолок выключен: на обложках голова гладкая и круглая
    PAW_F = nrm(V(0, -0.037, -0.016))
    def front_paw(self, p, i): return toe_paw(p, self.PAW[i], (0.0245, 0.0275, 0.0215), self.PAW_F, tr=0.0089, tk=0.0034, fk=0.7, dk=0.3)
    def hind_paw(self, p, i): return toe_paw(p, self.FOOT[i], (0.035, 0.074, 0.0245), V(0, -1, 0), tr=0.0128, tk=0.0045, pads=False, fk=0.74, dk=0.28)
    def arm_sd(self, p, i):
        x = sd_rcone(p, self.SHOULD[i], self.WRIST[i], 0.03, 0.025)
        x = smin(x, self.front_paw(p, i)[0], 0.014)
        return smin(x, sd_sph(p, self.SHOULD[i] + V(0, 0.003, 0.003), 0.031), 0.018)
    def leg_sd(self, p, i):
        x = sd_ell(p, self.HIP[i], V(0.05, 0.06, 0.058))
        x = smin(x, sd_rcone(p, self.HIP[i] + V(0, -0.012, -0.02), self.FOOT[i] + V(0, 0.03, 0.018), 0.03, 0.024), 0.026)
        return smin(x, self.hind_paw(p, i)[0], 0.02)
    def extra_regions(self, p, reg):
        limb = (reg == 5) | (reg == 6); toes = np.full(len(p), 9.0, F); pads = np.full(len(p), 9.0, F)
        for i in range(2):
            x, t, pd = self.front_paw(p, i); toes = np.minimum(toes, x); pads = np.minimum(pads, pd)
            x, t, _ = self.hind_paw(p, i); toes = np.minimum(toes, x)
        reg = np.where(limb & (toes < 0.003), 9, reg); return np.where(limb & (pads < 0.001), 12, reg)
    def parts(self, p):
        d = {}
        t = sd_ell(p, V(0, 0.007, 0.228), V(0.08, 0.072, 0.118))
        t = smin(t, sd_ell(p, V(0, -0.014, 0.166), V(0.098, 0.09, 0.086)), 0.045)                             # круглый животик
        t = smin(t, sd_cap(p, V(0, 0, 0.3), self.NECK + V(0, -0.004, 0.034), 0.043), 0.04)
        d['torso'] = t
        h = self.head_form(p)
        d['head'] = h
        m = None
        for c in self.PADS: x = sd_sph(p, c, 0.0165); m = x if m is None else smin(m, x, 0.01)        # подушечки с усами (лежат на форме головы)
        m = smin(m, sd_sph(p, self.CHIN, 0.013), 0.012)                                                     # подбородок
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
        """Белый зайчонок: спинка чуть серее, румянец на щёчках, розовые серединки ушей, подушечки и рот."""
        N = len(p); x, y, z = p[:, 0], p[:, 1], p[:, 2]; w = wob(p, 1.6) * 0.5
        reg = np.where((reg0 == 9) | (reg0 == 12), np.where(z > 0.12, 5, 6), reg0)
        white = V(0.74, 0.7, 0.64); pink = V(0.8, 0.46, 0.5); blush = V(0.78, 0.36, 0.4)   # тёплый кремово-белый, как у прежнего Фили; на солнце не «горит»
        k = np.clip(0.97 + 0.05 * w - 0.1 * np.clip(y * 6, 0, 1), 0.82, 1.04)                      # спинка чуть темнее
        fur = white[None] * k[:, None]
        for s in (-1, 1):                                                                           # румянец под глазками
            b = np.clip((1.0 - np.linalg.norm((p - self.BLUSH[0 if s < 0 else 1]) / V(0.034, 0.034, 0.026), axis=-1)) * 2.5, 0, 1) * ((reg == 1) | (reg == 2))
            fur = fur * (1 - 0.62 * b[:, None]) + blush[None] * (0.62 * b[:, None])
        skin = fur * 0.92
        skin = np.where((reg == 8)[:, None], pink[None] * (0.95 + 0.05 * w[:, None]), skin)
        skin = np.where((reg == 10)[:, None], V(0.16, 0.03, 0.03)[None], np.where((reg == 11)[:, None], V(0.75, 0.3, 0.34)[None], skin))
        skin = np.where((reg0 == 12)[:, None], V(0.84, 0.5, 0.54)[None] * (0.95 + 0.05 * w[:, None]), skin)   # розовые подушечки
        return skin.astype(F), fur.astype(F)
    def fur_ok(self, p, reg):
        ok = (reg != 8) & (reg != 10) & (reg != 11) & (reg != 12)
        for E in self.EYES: ok &= self.eye_d(p, E) > self.RE + 0.009      # мех не заслоняет глаз
        ok &= np.linalg.norm(p - self.NOSE_C, axis=-1) > 0.017
        ok &= self.scarf_fn(p) > 0.0015
        return ok
    def nose_fn(self, p):   # розовый носик «сердечком»: шире сверху, с ложбинкой
        c = self.NOSE_C; d = sd_ell(p, c, V(0.0135, 0.0095, 0.0092))
        d = smin(d, sd_ell(p, c + V(0, 0.003, -0.008), V(0.006, 0.008, 0.006)), 0.004)
        for s in (-1, 1): d = smax(d, -sd_ell(p, c + V(s * 0.0056, -0.0092, -0.0026), V(0.0019, 0.0017, 0.0013)), 0.0012)
        return d
    NOSE_COL = (0.9, 0.47, 0.55)
    _TC = None
    def teeth_centers(self):
        if Fila._TC is None:
            z = self.LIP_Z - 0.001; o = np.array([[s * 0.0049, -0.4, z] for s in (-1, 1)], F)
            hp = self.hit(o, np.tile(V(0, 1, 0), (2, 1))); Fila._TC = [h + V(0, 0.0034, -0.0046) for h in hp]
        return Fila._TC
    def teeth_fn(self, p):  # два заячьих зубика из-под верхней губки
        out = None
        for s, c in zip((-1, 1), self.teeth_centers()):
            q = rotx(p - c, -0.42)
            t = sd_ell(q, V(0, 0, 0), V(0.0044, 0.0018, 0.0062)); t = smax(t, q[:, 2] - 0.004, 0.0008)
            out = t if out is None else np.minimum(out, t)
        return out
    SCARF_C = V(0, -0.006, 0.325); SCARF_R = 0.068; SCARF_T = 0.0275; SCARF_ROT = 0.14   # толстый вязаный, как у прежнего Фили
    def scarf_fn(self, p):  # вязаный шарф: кольцо вокруг шеи, узел спереди слева и свисающий конец; мелкие рубчики вязки
        c = self.SCARF_C; q = p - c; cs, sn = math.cos(self.SCARF_ROT), math.sin(self.SCARF_ROT)
        yy = q[:, 1] * cs - q[:, 2] * sn; zz = q[:, 1] * sn + q[:, 2] * cs
        ang = np.arctan2(q[:, 0], -yy); rr = np.sqrt(q[:, 0] ** 2 + yy ** 2) - self.SCARF_R
        ring = np.sqrt(rr ** 2 + (zz * 0.86) ** 2) - self.SCARF_T                       # кольцо чуть выше, чем толще
        ring = ring + 0.0016 * np.cos(ang * 30) * np.clip(1 - np.abs(ring) * 50, 0, 1)   # крупные рубчики поперёк
        kn = sd_ell(p, V(0.04, -0.084, 0.318), V(0.032, 0.027, 0.029))                     # узел
        e0 = V(0.047, -0.094, 0.238); qe = rotz(p - e0, 0.1)
        end = sd_ell(qe, V(0, 0, 0), V(0.034, 0.014, 0.088))                           # свисающий конец
        end = smax(end, -(qe[:, 2] + 0.078), 0.004)                                      # ровный нижний край
        end = end + 0.0015 * np.cos(qe[:, 0] * (2 * math.pi / 0.0085)) * np.clip(1 - np.abs(end) * 50, 0, 1)   # рубчики вдоль
        return smin(smin(ring, kn, 0.01), end, 0.01)
    def acc_fn(self, p): return self.scarf_fn(p)
    ACCS = [{'name': 'scarf', 'fn': 'scarf_fn', 'box': ((-0.115, -0.135, 0.14), (0.115, 0.108, 0.375)), 'mat': 'cloth', 'col': (0.3, 0.6, 0.86), 'h': 0.0012},
            {'name': 'teeth', 'fn': 'teeth_fn', 'box': ((-0.016, -0.173, 0.392), (0.016, -0.115, 0.43)), 'mat': 'tooth', 'col': (0.88, 0.86, 0.82), 'h': 0.0004}]
    def mouth_lines(self):
        lines = []; nz = self.NOSE_C
        z0 = nz[2] - 0.0105; phil = [V(0, -0.4, z0 + (self.LIP_Z - z0) * i / 6) for i in range(7)]
        lines.append(self.hit(np.array(phil), np.tile(V(0, 1, 0), (7, 1))))
        for s in (-1, 1):
            ang = np.linspace(0, math.pi, 12); xs = s * (0.0145 - 0.0145 * np.cos(ang)); zs = self.LIP_Z - 0.0058 * np.sin(ang) + 0.0062 * (xs * s / 0.029) ** 2   # улыбка: уголки вверх
            lines.append(self.hit(np.stack([xs, np.full(12, -0.4, F), zs], -1).astype(F), np.tile(V(0, 1, 0), (12, 1))))
        return lines[:1] if self.MOUTH is not None else lines
    def whiskers(self):
        out = []
        for s in (-1, 1):
            for j, (dz, ang) in enumerate([(0.008, 0.16), (0.0, 0.0), (-0.008, -0.14)]):
                o = V(s * (0.015 + 0.004 * j), -0.4, float(self.PADS[0][2]) + 0.003 + dz); r0 = self.hit(o, V(0, 1, 0))[0] + V(0, 0.0015, 0)
                dirn = nrm(V(s * 1.0, -0.25, ang)); out.append(np.array([r0 + dirn * 0.11 * (k / 7) + V(0, 0.01 * (k / 7) ** 2, -0.01 * (k / 7) ** 2) for k in range(8)], F))
        return out
    WHISK_R = (0.00055, 0.00013); WHISK_COL = (0.8, 0.79, 0.78)
    FUR = {'K': 0.8e6, 'dens': [1.0, 1.12, 0.9, 1.4, 0.9, 1.0, 1.0, 1.1, 0.0, 1.1], 'L': [0.015, 0.012, 0.0045, 0.003, 0.0055, 0.01, 0.011, 0.026, 0.0, 0.0045],
           'lean': [1.45, 1.55, 1.45, 1.35, 1.3, 1.4, 1.4, 1.0, 0.5, 1.32], 'down': [0.32, 0.14, 0.1, 0.1, 0.05, 0.2, 0.2, 0.0, 0.0, 0.1], 'rad': 0.00058, 'radLid': 0.00042,
           'cell': 0.008, 'clump': 0.12, 'frontK': 0.5, 'tip': 0.0, 'ms': 0.12, 'spec': 0.14, 'ruff': [0.09, 0.36, 0.47, 16.0, 0.9, -0.3], 'earTip': None, 'chest': [0.0, -0.05, 0.275, 1.22], 'tailTip': None}
    def fur_src(self):
        return {'nose': self.NOSE_C.tolist(), 'earOff': [0, 0.08, 0.2], 'neck': (self.NECK + V(0, 0, 0.02)).tolist(), 'should': [s.tolist() for s in self.SHOULD], 'wrist': [s.tolist() for s in self.WRIST],
                'hip': [(h + V(0, 0, 0.045)).tolist() for h in self.HIP], 'foot': [f.tolist() for f in self.FOOT], 'tail': [t.tolist() for t in self.TAIL], 'H': self.H.tolist(), 'headR': float(self.HEAD_R[0])}

HERO = Fila(); HERO.place_face()
