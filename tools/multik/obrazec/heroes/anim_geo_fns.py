# Функции частей Барсика ровно как в anim_geo.py (без запуска сборки)
import numpy as np
def make_fn(B):
    from build_geo import V, smin, smax, sd_cap, sd_sph, sd_ell, sd_rcone
    def arm_sd(p, i):
        x = sd_rcone(p, B.SHOULD[i], B.WRIST[i], 0.05, 0.039)
        x = smin(x, sd_ell(p, B.PAW[i], V(0.047, 0.054, 0.044)), 0.03)
        for j in (-1, 0, 1): x = smin(x, sd_sph(p, B.PAW[i] + V(j * 0.02 + (0.004 if i else -0.004), -0.042, -0.018), 0.017), 0.012)
        return smin(x, sd_sph(p, B.SHOULD[i] + V(0, 0.005, 0.005), 0.056), 0.03)
    def f_head(p):
        d = B.parts(p); h = smin(d['head'], d['muzzle'], 0.035)
        if B.VAR != 'blink':
            for E in B.EYES: h = smax(h, -(np.linalg.norm(p - E, axis=-1) - (B.RE + 0.003)), 0.012)
        h = smin(h, d['lid'], 0.006)
        if B.MOUTH is not None: h = smax(h, -B.mouth_cav(p), 0.006); h = np.minimum(h, sd_ell(p, *B.TONGUE))
        h = smin(h, d['ear'], 0.05); inner = np.minimum(B.ear_sd(p, 0, True), B.ear_sd(p, 1, True)); h = smax(h, -inner, 0.008)
        return smin(h, sd_cap(p, V(0, -0.008, 0.565), V(0, -0.012, 0.66), 0.068), 0.03)
    def f_body(p): d = B.parts(p); return smin(d['torso'], d['leg'], 0.05)
    return {'head': f_head, 'body': f_body, 'armL': lambda p: arm_sd(p, 0), 'armR': lambda p: arm_sd(p, 1), 'tail': lambda p: B.parts(p)['tail']}
