"""Ревизия-2: стем на каждую строку bus.add и его «шероховатость».
python3 audit2.py <песня>
Шероховатость = насколько огибающая полосы 300–5000 Гц дрожит с частотой 25–130 Гц (так слышится дребезг и треск).
Вклад = шероховатость × доля энергии стема в этой полосе: кто из инструментов даёт треск в общей картине."""
import linecache, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt, hilbert
import theme as th
from theme import SR

class SBus(th.Bus):
    def __init__(self):
        super().__init__()
        self.stems = {}
    def add(self, sig, t, pan=0.0, send=0.25, gain=1.0):
        fr = sys._getframe(1)
        key = (fr.f_code.co_filename, fr.f_lineno)
        st = self.stems.setdefault(key, np.zeros(len(self.L), dtype=np.float32))
        s = int(t * SR)
        x = np.asarray(sig, float)[:len(st) - s] * gain
        st[s:s + len(x)] += x
        super().add(sig, t, pan, send, gain)

SOS = butter(4, [300, 5000], btype="band", fs=SR, output="sos")

def rough(x):
    y = sosfiltfilt(SOS, x.astype(float))
    env = np.abs(hilbert(y))[::10]
    fs = SR / 10
    n = int(fs)
    vals, wts = [], []
    pk = env.max() + 1e-12
    for i in range(0, len(env) - n, n // 2):
        e = env[i:i + n]
        if e.mean() < 0.05 * pk:
            continue
        S = np.abs(np.fft.rfft((e - e.mean()) * np.hanning(n))) / (n / 4)
        f = np.fft.rfftfreq(n, 1 / fs)
        b = (f >= 25) & (f <= 130)
        vals.append(float(np.sqrt((S[b] ** 2).sum()) / e.mean()))
        wts.append(float(e.mean()))
    return (float(np.average(vals, weights=wts)) if vals else 0.0), float((y ** 2).sum())

def run(compose):
    th.Bus = SBus
    bus, end_t = compose()
    res = []
    for (fn, ln), st in bus.stems.items():
        r, e = rough(st)
        res.append((ln, r, e, linecache.getline(fn, ln).strip()[:70]))
    tot = sum(e for _, _, e, _ in res)
    mix = sum(bus.stems.values())
    rm, _ = rough(mix)
    print(f"{'строка':>6} {'шерох.':>7} {'доля 0,3–5к':>12} {'вклад':>7}  код")
    for ln, r, e, code in sorted(res, key=lambda q: -q[1] * q[2]):
        if e / tot > 0.002:
            print(f"{ln:6d} {r:7.3f} {100 * e / tot:11.1f}% {100 * r * e / tot:7.2f}  {code}")
    print(f"ВСЯ СМЕСЬ (сухая): шероховатость {rm:.3f}")

if __name__ == "__main__":
    import golos
    run(lambda: golos.compose(golos.SONGS[sys.argv[1]]))
