# центр видимой части глаза (что не закрыто головой и веком) — по нему ставим радужку, чтобы не было «косоглазия»
import sys, numpy as np, importlib, math
sys.path.insert(0, '.')
from hero_common import *
def opening(H, n=6000):
    H.set_var('base'); rng = np.random.default_rng(1); d = nrm(rng.normal(size=(n, 3)).astype(F)); out = []
    S = H.EYE_S if H.EYE_S is not None else V(1, 1, 1)
    for E in H.EYES:
        P = E + d * S * H.RE * 1.0                                   # точки на поверхности глаза
        parts = H.parts(P); head = smin(parts['head'], parts['muzzle'], H.K_MUZ); head = smin(head, parts['ear'], H.K_EAR)
        lidc = (d @ H.lid_n(E)) > H.LID_OFF / 1.085                  # под веком
        vis = (head > 0.0005) & ~lidc & (d[:, 1] < 0.2)
        c = nrm(d[vis].mean(0)); out.append((c, int(vis.sum())))
    return out
if __name__ == '__main__':
    H = importlib.import_module(sys.argv[1]).HERO
    for E, (c, k) in zip(H.EYES, opening(H)):
        print('eye', np.round(E, 3), 'center dir', np.round(c, 3), 'yaw out %.1f°' % math.degrees(math.atan2(c[0], -c[1])), 'pitch %.1f°' % math.degrees(math.atan2(c[2], -c[1])), 'pts', k)
