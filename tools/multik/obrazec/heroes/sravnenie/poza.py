# Подбор ракурса моего героя под обложку: поворот (рыскание) — по смещению носа от середины головы, наклон (тангаж) — по высоте макушки над глазами.
# Потом — таблица мерок в найденном ракурсе. python3 poza.py <hero> <ключ обложки> [мех, м]
import sys, os, json, math, subprocess, numpy as np, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, '.')
import mery
hero, key = sys.argv[1:3]; fur = float(sys.argv[3]) if len(sys.argv) > 3 else 0.012
OUT = '/home/claude/out/geroi'; A = mery.cover_metrics(json.load(open('sravnenie/obl.json'))[key])
H = importlib.import_module(hero).HERO; C = getattr(H, 'FORM', {}).get('C', H.H); C = [float(v) for v in C]
def cam(yaw, pitch, D=1.25):
    a, b = math.radians(yaw), math.radians(pitch)
    return 'cam=%.4f,%.4f,%.4f:%.4f,%.4f,%.4f:28' % (C[0] + D * math.sin(a) * math.cos(b), C[1] - D * math.cos(a) * math.cos(b), C[2] + D * math.sin(b), C[0], C[1], C[2] + 0.04)
def meas(yaw, pitch, res=260):
    v = cam(yaw, pitch); env = dict(os.environ, OUT=OUT, LBL='1', RES=str(res))
    subprocess.run(['python3', 'prev_cvet.py', hero, 'pz_' + key, v], env=env, capture_output=True, check=True)
    mk = json.load(open(OUT + '/pz_%s.json' % key))[v]
    e_, l_, f_ = v[4:].split(':'); d_ = np.linalg.norm(np.array(list(map(float, e_.split(',')))) - np.array(list(map(float, l_.split(',')))))
    fur_px = fur / (2 * d_ * math.tan(math.radians(float(f_)) / 2) / res)
    return mery.mine_metrics(OUT + '/pz_%s_0_lbl.png' % key, mk, fur_px), v
T = A['поворот (нос от середины головы)']
lo, hi = -65.0, 65.0                       # поворот меняется с рысканием монотонно: делим пополам
sg = 1 if meas(hi, -5)[0]['поворот (нос от середины головы)'] > meas(lo, -5)[0]['поворот (нос от середины головы)'] else -1
for _ in range(7):
    mid = (lo + hi) / 2; m, _v = meas(mid, -5)
    if (m['поворот (нос от середины головы)'] - T) * sg < 0: lo = mid
    else: hi = mid
yaw = (lo + hi) / 2
best = None
for pitch in (-20, -12, -5, 2, 9):
    m, _v = meas(yaw, pitch); e = abs(m['макушка выше глаз'] - A['макушка выше глаз'])
    if best is None or e < best[0]: best = (e, pitch)
pitch = best[1]; B, v = meas(yaw, pitch, 600)
print('ракурс: поворот %.1f°, наклон %d°   (%s)' % (yaw, pitch, v))
print('%-38s %9s %9s %8s' % ('мерка (доля ширины головы)', key, 'мой', 'разница'))
for k in A:
    if k not in B or 'px' in k: continue
    a, b = A[k], B[k]
    if 'доля' in k: print('%-38s %9.3f %9.3f %+7.0f п.%s' % (k, a, b, (b - a) * 100, '  ←' if abs(b - a) > 0.06 else '')); continue
    d = (b - a) / abs(a) * 100; print('%-38s %9.3f %9.3f %7.0f%%%s' % (k, a, b, d, '  ←' if abs(d) > 10 else ''))

