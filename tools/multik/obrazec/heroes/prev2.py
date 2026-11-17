import sys, numpy as np, importlib
sys.path.insert(0, '.')
from hero_common import *
m = importlib.import_module(sys.argv[1]); H = m.HERO
def extra(p):
    d = np.full(len(p), 9.0, F)
    for E in H.EYES: d = np.minimum(d, sd_sph(p, E, H.RE))
    d = np.minimum(d, H.nose_fn(p))
    for a in (getattr(H, 'ACCS', None) or [dict(fn='acc_fn')]): d = np.minimum(d, getattr(H, a['fn'])(p))
    return d
tag = sys.argv[2]; views = sys.argv[3:]
V_ = {'34': dict(eye=(0.42, -1.2, 0.42), look=(0, -0.02, 0.3)), 'face': dict(eye=(0.16, -0.62, 0.45), look=(0, -0.05, 0.41), fov=30),
      'side': dict(eye=(1.2, -0.25, 0.36), look=(0, 0, 0.3)), 'hand': dict(eye=(0.2, -0.36, 0.2), look=(0.088, -0.07, 0.165), fov=26),
      'foot': dict(eye=(0.18, -0.36, 0.14), look=(0.05, -0.06, 0.02), fov=28), 'back': dict(eye=(0.5, 1.1, 0.45), look=(0, 0.02, 0.3))}
for v in views: H.preview('%s_%s.png' % (tag, v), extra=extra, W=270, Hh=360, **V_[v])
