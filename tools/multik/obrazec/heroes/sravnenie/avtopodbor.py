# Автоподбор чисел лица героя под несколько обложек сразу.
# Ракурс на каждой обложке уже найден poza.py (/tmp/pz_<ключ>.log). Каждая мерка «привязана» к одному числу героя;
# производные считаются один раз, дальше — шаги Ньютона по всем числам вместе, пока среднее расхождение не станет меньше 3%.
# python3 avtopodbor.py <hero> <ключ1> <ключ2> ...
import sys, os, re, json, math, subprocess, importlib, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, '.')
import mery
hero, keys = sys.argv[1], sys.argv[2:]; OUT = '/home/claude/out/geroi'; RES = 300; FUR = 0.012
cams = {k: re.search(r'\((cam=[^)]*)\)', open('/tmp/pz_%s.log' % k).read()).group(1) for k in keys}
obl = json.load(open('sravnenie/obl.json')); A = {k: mery.cover_metrics(obl[k]) for k in keys}
H = importlib.import_module(hero).HERO
P = {'ex': H.EYE_XZ[0], 'ez': H.EYE_XZ[1], 'RE': H.RE, 'sz': float(H.EYE_S[2]), 'k0': H.EYE_K[0], 'tilt': H.EYE_TILT[1], 'nz': H.NOSE_Z, 'lz': H.LIP_Zf}
PAIR = {'ex': 'между глазами', 'RE': 'ширина глаза', 'sz': 'высота глаза', 'k0': 'радужка / ширина глаза', 'tilt': 'радужка ниже (доля высоты глаза)',
        'nz': 'нос ниже глаз', 'lz': 'рот ниже глаз', 'ez': 'макушка выше глаз'}
STEP = {'ex': 0.004, 'ez': 0.006, 'RE': 0.003, 'sz': 0.06, 'k0': 0.03, 'tilt': 4.0, 'nz': 0.006, 'lz': 0.006}
LIM = {'ex': (P['ex'] - 0.04, P['ex'] + 0.04), 'ez': (P['ez'] - 0.06, P['ez'] + 0.06), 'RE': (P['RE'] * 0.7, P['RE'] * 1.3), 'sz': (0.75, 1.3), 'k0': (0.7, 0.95), 'tilt': (-25, 10), 'nz': (P['nz'] - 0.07, P['nz'] + 0.07), 'lz': (P['lz'] - 0.07, P['lz'] + 0.07)}
def ovr(p):
    S = list(map(float, H.EYE_S)); S[2] = p['sz']
    return {'EYE_XZ': [p['ex'], p['ez']], 'RE': p['RE'], 'EYE_S': S, 'EYE_K': [p['k0'], max(p['k0'] + 0.05, H.EYE_K[1])], 'EYE_TILT': [H.EYE_TILT[0], p['tilt']], 'NOSE_Z': p['nz'], 'LIP_Zf': p['lz']}
def run1(k, p):
    v = cams[k]; env = dict(os.environ, OUT=OUT, LBL='1', RES=str(RES), OVR=json.dumps(ovr(p)))
    return subprocess.Popen(['python3', 'prev_cvet.py', hero, 'ap_' + k, v], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def ev(p):
    out = {}
    for i in range(0, len(keys), 2):
        ps = [(k, run1(k, p)) for k in keys[i:i + 2]]
        for k, pr in ps: pr.wait()
    for k in keys:
        v = cams[k]; mk = json.load(open(OUT + '/ap_%s.json' % k))[v]
        e_, l_, f_ = v[4:].split(':'); d_ = np.linalg.norm(np.array(list(map(float, e_.split(',')))) - np.array(list(map(float, l_.split(',')))))
        out[k] = mery.mine_metrics(OUT + '/ap_%s_0_lbl.png' % k, mk, FUR / (2 * d_ * math.tan(math.radians(float(f_)) / 2) / RES))
    return {q: float(np.mean([out[k][m] - A[k][m] for k in keys])) for q, m in PAIR.items()}, out
def score(r): return float(np.mean([abs(r[q]) / max(0.05, np.mean([abs(A[k][PAIR[q]]) for k in keys])) for q in r]))
r0, _ = ev(P); print('начало: среднее расхождение %.1f%%' % (score(r0) * 100)); D = {}
for q in P:   # производные (по одной мерке на число)
    p2 = dict(P); p2[q] += STEP[q]; r2, _ = ev(p2); D[q] = (r2[q] - r0[q]) / STEP[q]
    print('  %s: d(%s)/d = %.3f' % (q, PAIR[q], D[q]))
r = r0
for it in range(6):
    for q in P:
        if abs(D[q]) > 1e-6: P[q] = float(np.clip(P[q] - 0.8 * r[q] / D[q], *LIM[q]))
    r, out = ev(P); s = score(r); print('шаг %d: среднее расхождение %.1f%%' % (it + 1, s * 100), {q: round(v, 4) for q, v in P.items()})
    if s < 0.03: break
json.dump({'P': P, 'ovr': ovr(P)}, open(OUT + '/avtopodbor_%s.json' % hero, 'w'), ensure_ascii=False, indent=1)
for k in keys:
    print('==', k)
    for m in PAIR.values(): print('   %-36s обложка %.3f  мой %.3f' % (m, A[k][m], out[k][m]))
