import sys, numpy as np, importlib
sys.path.insert(0, '.')
from hero_common import *
m = importlib.import_module(sys.argv[1]); H = m.HERO
def extra(p):
    d = np.full(len(p), 9.0, F)
    for E in H.EYES: d = np.minimum(d, sd_sph(p, E, H.RE))
    return d
tag = sys.argv[2]; i = 0
for spec in sys.argv[3:]:
    e, l, fov = spec.split('/'); H.preview('%s_%d.png' % (tag, i), extra=extra, W=270, Hh=300, eye=tuple(map(float, e.split(','))), look=tuple(map(float, l.split(','))), fov=float(fov)); i += 1
