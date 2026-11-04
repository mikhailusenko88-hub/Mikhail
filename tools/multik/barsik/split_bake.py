# Свет без чужой тени: туловище запекается без лап, лапы — без туловища (правило для всех героев:
# лапа в покое не должна оставлять на боку тёмную «тень», которая видна, когда лапа поднята).
#   python3 split_bake.py prep   → out/geo_s3b.npz (без лап), out/geo_s3a.npz (только лапы)
#   (export_geo + fur_exp для s3b и s3a)
#   python3 split_bake.py merge  → out/phone_s3_fix.raw: свет туловища из s3b, свет лап из s3a, остальное — из s3
import numpy as np, struct, sys, os
from scipy.spatial import cKDTree
NB = int(os.environ.get('NBODY', '248692'))   # первые NB вершин кожи — туловище, дальше — лапы (build_geo_split.py)
def tau_of(root, w, q, K=40):
    tree = cKDTree(root); out = np.empty(len(q), np.float32)
    for i in range(0, len(q), 100000):
        d, j = tree.query(q[i:i + 100000], k=K); dk = d[:, -1]
        out[i:i + 100000] = (K / (np.pi * np.maximum(dk, 1e-4) ** 2)) * w[j].mean(1)
    return out
if sys.argv[1] == 'prep':
    G = dict(np.load('out/geo_s3.npz')); S = np.load('out/split_vol.npz')
    reg = G['skin_reg'].copy(); reg[NB:][reg[NB:] == 0] = 5; G['skin_reg'] = reg   # швы лапы — тоже лапа
    np.savez_compressed('out/geo_s3.npz', **G)
    P = G['fur_pts']; root = P[:, 0]; L = np.linalg.norm(np.diff(P, axis=1), axis=-1).sum(1); w = 2 * G['fur_rad'] * L
    farm = G['fur_reg'] == 5; f = G['skin_f']; tarm = (f >= NB).any(1)
    for name, keep_arm in (('s3b', False), ('s3a', True)):
        H = dict(G); mine = farm if keep_arm else ~farm
        H['fur_rad'] = np.where(mine, G['fur_rad'], 0).astype(np.float32)           # чужие волоски не дают тени
        H['skin_f'] = f[tarm] if keep_arm else f[~tarm]                              # чужая кожа не дают тени
        H['vol'] = S['arm' if keep_arm else 'body']
        t = np.array(G['fur_tau']); idx = np.nonzero(mine)[0]
        tt = tau_of(root[idx], w[idx], root[idx]); _, j = cKDTree(root[idx]).query(root[idx], k=16); t[idx] = tt[j].mean(1)
        H['fur_tau'] = t.astype(np.float32)
        st = np.array(G['skin_tau']); sv = G['skin_v']; part = np.arange(len(sv)) >= NB if keep_arm else np.arange(len(sv)) < NB
        st[part] = tau_of(root[idx], w[idx], sv[part]); H['skin_tau'] = st.astype(np.float32)
        np.savez_compressed('out/geo_%s.npz' % name, **H); print(name, 'волосков своих', int(mine.sum()))
else:
    def read(path):
        raw = bytearray(open(path, 'rb').read()); o = 0; nf = struct.unpack_from('<I', raw, o)[0]; o += 4; oF = o; o += nf * 216
        nl = struct.unpack_from('<I', raw, o)[0]; o += 4; ln = struct.unpack_from('<I', raw, o)[0]; o += 4 + ln * 4
        nv, nt = struct.unpack_from('<II', raw, o); o += 8; oV = o
        F = np.frombuffer(bytes(raw[oF:oF + nf * 216]), np.float32).reshape(nf, 54).copy(); Vv = np.frombuffer(bytes(raw[oV:oV + nv * 80]), np.float32).reshape(nv, 20).copy()
        return raw, oF, oV, F, Vv
    raw, oF, oV, F, Vv = read('out/phone_s3.raw'); _, _, _, Fb, Vb = read('out/phone_s3b.raw'); _, _, _, Fa, Va = read('out/phone_s3a.raw')
    assert len(Fb) == len(F) == len(Fa) and np.allclose(Fb[:, :3], F[:, :3]) and np.allclose(Fa[:, :3], F[:, :3]), 'волоски не совпали'
    arm = F[:, 53].astype(int) == 5
    F[:, 15:45] = np.where(arm[:, None], Fa[:, 15:45], Fb[:, 15:45])
    nsk = int(os.environ.get('NSKIN', '287042')); iv = np.arange(len(Vv)); varm = (iv >= NB) & (iv < nsk)
    assert len(Vb) == len(Vv) == len(Va)
    Vv[:, 9:15] = np.where(varm[:, None], Va[:, 9:15], Vb[:, 9:15])
    raw[oF:oF + F.nbytes] = F.tobytes(); raw[oV:oV + Vv.nbytes] = Vv.tobytes()
    open('out/phone_s3_fix.raw', 'wb').write(raw); print('свет: лапы %d волосков, туловище %d' % (int(arm.sum()), int((~arm).sum())))
