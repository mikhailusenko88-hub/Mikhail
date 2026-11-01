# Подбор весов «слуха» по out/calib.json (запуск: python3 tune_stress.py). Пишет tune_candidate.json;
# переименовать в tune.json только если точность на новых фразах выше, чем у текущих весов.
import json, sys, numpy as np
sys.path.insert(0, ".")
import voice_check as vc
D = json.load(open("out/calib.json"))
FEATS = sorted(vc.FW.keys())
def mat(d):
    rows = vc.vfeats(d["vf"])
    X = np.array([[r.get(f, 0.0) for f in FEATS] for r in rows])
    y = [i for i, v in enumerate(d["vf"]) if v["k"] == d["told"]]
    return X, (y[0] if y else None)
data = [(mat(d), d) for d in D]
data = [((X, y), d) for (X, y), d in data if y is not None]
def acc(w, items):
    ok = sum(int(np.argmax(X @ w) == y) for (X, y), _ in items)
    return ok / max(1, len(items))
def train(items, l2=0.005, it=2500, lr=1.0):
    w = np.array([vc.FW[f] for f in FEATS], float)
    for _ in range(it):
        g = l2 * w
        for (X, y), _ in items:
            s = X @ w; s -= s.max(); p = np.exp(s); p /= p.sum()
            g += (X.T @ p - X[y]) / len(items)
        w -= lr * g
    return w
w0 = np.array([vc.FW[f] for f in FEATS], float)
print("ручные веса:", round(acc(w0, data), 3), "| случайный выбор:", round(np.mean([1 / len(X) for (X, y), _ in data]), 3))
# перекрёстная проверка по фразам
cv = []
for s in range(10):
    tr = [x for x in data if x[1]["s"] != s]; te = [x for x in data if x[1]["s"] == s]
    w = train(tr); cv += [(int(np.argmax(X @ w) == y), d) for (X, y), d in te]
tot = np.mean([c for c, _ in cv])
print("обученные веса, проверка на новых фразах:", round(tot, 3))
for sh in (False, True):
    print("  ", "сдвинутые" if sh else "правильные", round(np.mean([c for c, d in cv if d["shift"] == sh]), 3))
for spk in sorted({d["spk"] for _, d in cv}):
    print("  ", spk, round(np.mean([c for c, d in cv if d["spk"] == spk]), 3))
w = train(data)
print("на всех:", round(acc(w, data), 3))
print({f: round(float(x), 2) for f, x in zip(FEATS, w)})
json.dump({"FW": {f: round(float(x), 3) for f, x in zip(FEATS, w)}}, open("tune_candidate.json", "w"), ensure_ascii=False, indent=1)
