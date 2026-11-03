# Общий каркас героя «из глины» (поле расстояний), как build_geo.py у Барсика, но для любого героя.
# Оси Blender: x вправо, y назад (камера со стороны -y), z вверх; метры.
import math
import numpy as np

F = np.float32
def V(*a): return np.array(a, dtype=F)
def nrm(v): return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)

def sd_ell(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1); k1 = np.linalg.norm(q / r, axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
def sd_sph(p, c, r): return np.linalg.norm(p - c, axis=-1) - r
def sd_rcone(p, a, b, r1, r2):
    ba = b - a; l2 = float(ba @ ba); rr = r1 - r2; a2 = l2 - rr * rr; il2 = 1.0 / l2
    pa = p - a; y = pa @ ba; z = y - l2
    x = pa * l2 - y[:, None] * ba[None, :]; x2 = np.einsum('ij,ij->i', x, x)
    y2 = y * y * l2; z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))
def sd_cap(p, a, b, r): return sd_rcone(p, a, b, r, r)
def sd_torus(p, c, R, r, rotx=0.0):
    q = p - c; cs, sn = math.cos(rotx), math.sin(rotx)
    y = q[:, 1] * cs - q[:, 2] * sn; z = q[:, 1] * sn + q[:, 2] * cs
    return np.sqrt((np.sqrt(q[:, 0] ** 2 + y ** 2) - R) ** 2 + z ** 2) - r
def smin(a, b, k):
    if k <= 0: return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25
def smax(a, b, k): return -smin(-a, -b, k)
def rotz(q, a):
    c, s = math.cos(a), math.sin(a); out = q.copy(); out[:, 0] = q[:, 0] * c - q[:, 1] * s; out[:, 1] = q[:, 0] * s + q[:, 1] * c; return out
def roty(q, a):
    c, s = math.cos(a), math.sin(a); out = q.copy(); out[:, 0] = q[:, 0] * c + q[:, 2] * s; out[:, 2] = -q[:, 0] * s + q[:, 2] * c; return out
def spline(P, n):
    """Catmull-Rom через контрольные точки -> n точек (плавный хвост без изломов)."""
    P = [np.asarray(x, F) for x in P]; P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]; out = []
    for k in range(n):
        t = k / (n - 1) * (len(P) - 3); i = min(int(t), len(P) - 4); u = t - i; p0, p1, p2, p3 = P[i:i + 4]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    return np.array(out, F)
def toe_paw(p, c, r, f, ntoe=4, tr=0.015, tk=0.004, groove=True, pads=True, fk=0.8, dk=0.32, spread=0.7):
    """Лапа с пальцами: ладонь-эллипсоид c/r (по осям x, вперёд, вниз), пальцы по дуге спереди, бороздки между пальцами,
    подушечки снизу. f — куда смотрят пальцы. Возвращает (форма, пальцы, подушечки)."""
    f = nrm(np.asarray(f, F)); X = V(1, 0, 0); X = nrm(X - f * (X @ f)); D = np.cross(X, f)   # D — вниз (к подушечкам)
    def loc(q): return np.stack([q @ X, q @ f, q @ D], -1)
    q = loc(p - c); x = sd_ell(q, V(0, 0, 0), V(*r))
    us = np.linspace(-1, 1, ntoe); toes = None; padd = None; T = []
    for u in us:
        tc = V(u * r[0] * spread, r[1] * (fk + 0.07 * (1 - abs(u))), r[2] * dk); T.append(tc)
        t = sd_ell(q, tc, V(tr, tr * 1.12, tr * 0.86)); toes = t if toes is None else np.minimum(toes, t)
        if pads:
            b = sd_ell(q, tc + V(0, tr * 0.12, tr * 0.7), V(tr * 0.56, tr * 0.58, tr * 0.3)); padd = b if padd is None else np.minimum(padd, b)
    x = smin(x, toes, tk)
    if groove:
        for a, b in zip(T[:-1], T[1:]):
            m = (a + b) * 0.5; g = sd_cap(q, m + V(0, -tr * 1.0, -tr * 0.82), m + V(0, tr * 1.3, -tr * 0.5), tr * 0.2); x = smax(x, -g, tk * 0.5)
    if pads:
        mp = sd_ell(q, V(0, r[1] * 0.12, r[2] * 0.9), V(r[0] * 0.52, r[1] * 0.4, r[2] * 0.2)); padd = np.minimum(padd, mp); x = smin(x, padd, 0.002)
    else: padd = np.full(len(p), 9.0, F)
    return x, toes, padd
def rotx(q, a):
    c, s = math.cos(a), math.sin(a); out = q.copy(); out[:, 1] = q[:, 1] * c - q[:, 2] * s; out[:, 2] = q[:, 1] * s + q[:, 2] * c; return out

RNG = np.random.default_rng(7)
_W = RNG.normal(size=(12, 3)).astype(F) * 6; _P = RNG.uniform(0, 6.28, 12).astype(F)
def wob(p, s=1.0): return (np.sin(p @ (_W.T * s) + _P).sum(-1) / 12 * 2.2).astype(F)

REGIONS = ['torso', 'head', 'muzzle', 'lid', 'ear', 'arm', 'leg', 'tail']

class Hero:
    """Подкласс задаёт: размеры (H, RE, EYES, SHOULD, WRIST, PAW, HIP, FOOT, TAIL, NECK, PIV, BOX), parts(p), ear_inner(p),
    arm_sd(p, i), colors(p, reg, nor) -> (кожа rgb, шерсть rgb), nose_fn, acc_fn (аксессуар), mouth_lines, whiskers, FUR (правила шерсти)."""
    VAR = 'base'; LID_NY = -0.3; EYE_S = None; MOUTH = None; MOUTHS = {}; TONGUE = None; LID_K = 0.1; K_MUZ = 0.035; K_EAR = 0.05; K_TORSO = 0.07
    def set_var(self, v): self.VAR = v; self.MOUTH = self.MOUTHS.get(v)
    def lid_n(self, E): return nrm(V(np.sign(E[0]) * self.LID_K, self.LID_NY, 1.0))
    def eye_q(self, q): return q / self.EYE_S if self.EYE_S is not None else q      # овальный глаз: меряем в «сплюснутых» координатах
    def eye_d(self, p, E): return np.linalg.norm(self.eye_q(p - E), axis=-1)
    def lid(self, p):
        out = None
        for E in self.EYES:
            q = self.eye_q(p - E); dd = np.linalg.norm(q, axis=-1)
            sh = np.abs(dd - (self.RE + self.RE * 0.085)) - self.RE * 0.056
            cut = q @ self.lid_n(E) - self.RE * self.LID_OFF
            l = smax(sh, -cut, 0.003); l = smax(l, q[:, 1] - self.RE * 0.16, 0.01)
            if self.VAR == 'blink': l = self.eye_d(p, E) - self.RE * 1.074
            out = l if out is None else np.minimum(out, l)
        return out
    def mouth_cav(self, p): return sd_ell(p, *self.MOUTH) if self.MOUTH is not None else np.full(len(p), 9.0, F)
    def head_sd(self, p, d=None):
        d = d if d is not None else self.parts(p)
        h = smin(d['head'], d['muzzle'], self.K_MUZ)
        if self.VAR != 'blink':
            for E in self.EYES: h = smax(h, -(self.eye_d(p, E) - self.RE * 1.05), 0.012)
        h = smin(h, d['lid'], 0.006)
        if self.MOUTH is not None:
            h = smax(h, -self.mouth_cav(p), 0.006); h = np.minimum(h, sd_ell(p, *self.TONGUE))
        h = smin(h, d['ear'], self.K_EAR)
        h = smax(h, -self.ear_inner(p), 0.008)
        return h
    def field(self, p, want_parts=False):
        d = self.parts(p); h = self.head_sd(p, d)
        f = smin(d['torso'], h, self.K_TORSO); f = smin(f, d['arm'], 0.035); f = smin(f, d['leg'], 0.05); f = smin(f, d['tail'], 0.03)
        if want_parts: return f, d, self.ear_inner(p)
        return f
    def region_of(self, p):
        f, d, inner = self.field(p, True)
        D = np.stack([d[k] for k in REGIONS], -1); reg = np.argmin(D, -1)
        reg = np.where(np.abs(inner) < 0.0065, 8, reg)
        if self.MOUTH is not None:
            reg = np.where(np.abs(self.mouth_cav(p)) < 0.004, 10, reg); reg = np.where(sd_ell(p, *self.TONGUE) < 0.002, 11, reg)
        reg = self.extra_regions(p, reg)
        return reg.astype(np.int32)
    def extra_regions(self, p, reg): return reg      # 9 — пальцы (короткая шерсть), 12 — подушечки (голые)
    def hit(self, o, dirn, tmax=0.4):
        o = np.atleast_2d(o).astype(F); dirn = nrm(np.atleast_2d(dirn).astype(F)); t = np.zeros(len(o), F)
        for _ in range(90):
            d = self.field(o + dirn * t[:, None]); t = np.minimum(t + np.maximum(d, 0.0004) * 0.9, tmax)
            if np.all(np.abs(d) < 0.0005): break
        return o + dirn * t[:, None]
    def creases(self):
        out = []; RE = self.RE
        for E in self.EYES:
            s = np.sign(E[0]); xs = np.linspace(-0.85, 0.85, 12) * RE
            zs = E[2] - 0.12 * RE - 0.22 * RE * (1 - (xs / (0.85 * RE)) ** 2)
            dirn = np.tile(nrm(V(-0.16 * s, 1.0, 0.0)), (12, 1))
            o = (np.stack([E[0] + xs, np.full(12, E[1]), zs], -1) - dirn * 0.15).astype(F)
            out.append(self.hit(o, dirn, 0.3) - dirn * 0.0015)
        return out
    def small_mesh(self, fn, lo, hi, h=0.0012):
        from skimage.measure import marching_cubes
        lo, hi = V(*lo), V(*hi); n = np.ceil((hi - lo) / h).astype(int) + 1
        g = np.stack(np.meshgrid(*[lo[i] + np.arange(n[i], dtype=F) * h for i in range(3)], indexing='ij'), -1).reshape(-1, 3)
        vol = fn(g).reshape(n[0], n[1], n[2])
        v, f, nn, _ = marching_cubes(vol, 0.0, spacing=(h, h, h))
        return (v + lo).astype(F), f.astype(np.int32)
    # ---- быстрый предпросмотр формы лучом по полю (для проверки силуэта и цвета) ----
    def preview(self, path, W=360, Hh=480, eye=(0.55, -1.55, 0.8), look=(0, -0.02, 0.6), fov=34, extra=None):
        from PIL import Image
        eye = V(*eye); look = V(*look); fw = nrm(look - eye); rt = nrm(np.cross(fw, V(0, 0, 1))); up = np.cross(rt, fw)
        ys, xs = np.mgrid[0:Hh, 0:W]; t = math.tan(math.radians(fov) / 2)
        u = (xs / W * 2 - 1) * t * W / Hh; v = -(ys / Hh * 2 - 1) * t
        dirs = nrm(fw[None] + u.reshape(-1, 1) * rt[None] + v.reshape(-1, 1) * up[None]).astype(F)
        fn = (lambda p: np.minimum(self.field(p), extra(p))) if extra else self.field
        o = np.tile(eye, (len(dirs), 1)); tt = np.zeros(len(dirs), F); hitm = np.zeros(len(dirs), bool)
        for _ in range(140):
            P = o + dirs * tt[:, None]; d = fn(P); hitm |= d < 0.0008; tt = np.where(hitm, tt, tt + np.maximum(d, 0.001));
            if np.all(hitm | (tt > 5)): break
        img = np.zeros((len(dirs), 3), F) + V(0.82, 0.88, 0.9); hi = np.nonzero(hitm)[0]
        if len(hi):
            Pp = o[hi] + dirs[hi] * tt[hi, None]; g = np.zeros_like(Pp); e = 0.0008
            for k in range(3): dp = np.zeros(3, F); dp[k] = e; g[:, k] = fn(Pp + dp) - fn(Pp - dp)
            nn = nrm(g); Ld = nrm(V(-0.5, -0.7, 0.8)); dif = np.clip(nn @ Ld, 0, 1); amb = 0.35 + 0.25 * nn[:, 2]
            reg = self.region_of(Pp); skin, fur = self.colors(Pp, reg, nn)
            base = np.where((reg == 8)[:, None] | (reg == 2)[:, None], skin, fur)
            if extra is not None: base = np.where((extra(Pp) < self.field(Pp))[:, None], V(0.9, 0.9, 0.88), base)
            for E in self.EYES:
                q = Pp - E; on = np.linalg.norm(q, axis=-1) < self.RE * 1.02
                c = nrm(q) @ nrm(V(np.sign(E[0]) * 0.18, -1, 0.02)); base = np.where(on[:, None], np.where((c > 0.93)[:, None], V(0.03, 0.02, 0.02), np.where((c > 0.72)[:, None], V(*self.IRIS[1]), V(0.95, 0.95, 0.94))), base)
            img[hi] = base * (dif[:, None] * 0.8 + amb[:, None])
        Image.fromarray((np.clip(img.reshape(Hh, W, 3), 0, 1) ** (1 / 1.8) * 255).astype(np.uint8)).save(path)
