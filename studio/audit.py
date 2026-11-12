"""Ревизия аранжировки по инструментам: python3 audit.py <песня> [golos|rassvet4:<стиль>]
Каждый вызов bus.add запоминается по строке кода. По каждой строке печатается: доля в общей энергии,
сколько её лежит ниже 60 Гц, и «жужжание» — энергия призвуков 250–1600 Гц у звуков с основным тоном ниже 115 Гц
(низкий звук с богатыми призвуками на маленьком динамике слышен как треск)."""
import linecache, sys
import numpy as np
import theme as th
from theme import SR

class ABus(th.Bus):
    def __init__(self):
        super().__init__()
        self.stat = {}
    def add(self, sig, t, pan=0.0, send=0.25, gain=1.0):
        fr = sys._getframe(1)
        key = (fr.f_code.co_filename, fr.f_lineno)
        x = np.asarray(sig, float) * gain
        if len(x) > 64:
            n = len(x)
            S = np.abs(np.fft.rfft(x)) ** 2
            f = np.fft.rfftfreq(n, 1 / SR)
            tot = float((x ** 2).sum())
            sc = tot / (S.sum() + 1e-30)
            lo = S[(f >= 30) & (f < 400)]
            f0 = f[(f >= 30) & (f < 400)][int(np.argmax(lo))] if len(lo) else 0     # самый сильный низкий тон
            st = self.stat.setdefault(key, dict(e=0.0, sub=0.0, buzz=0.0, n=0, f0=[]))
            st["e"] += tot
            st["sub"] += float(S[f < 60].sum() * sc)
            low = S[(f >= 30) & (f < 115)]
            if low.sum() > 0.05 * S.sum():                  # низкий звук: считаем его призвуки выше шестого
                fl = f[(f >= 30) & (f < 115)][int(np.argmax(low))]
                st["buzz"] += float(S[(f >= max(250, 6.5 * fl)) & (f < 3000)].sum() * sc)
            st["n"] += 1
            st["f0"].append(f0)
        super().add(sig, t, pan, send, gain)

def run(compose):
    th.Bus = ABus
    bus, end_t = compose()
    tot = sum(s["e"] for s in bus.stat.values())
    rows = sorted(bus.stat.items(), key=lambda kv: -kv[1]["e"])
    print(f"{'строка':>6} {'вызовов':>7} {'доля':>6} {'<60 Гц':>7} {'жужж.':>7}  осн. тон   код")
    sub_t = buzz_t = 0
    for (fn, ln), s in rows:
        sub_t += s["sub"]; buzz_t += s["buzz"]
        code = linecache.getline(fn, ln).strip()[:78]
        print(f"{ln:6d} {s['n']:7d} {100 * s['e'] / tot:5.1f}% {100 * s['sub'] / tot:6.2f}% {100 * s['buzz'] / tot:6.2f}%  {np.min(s['f0']):4.0f}–{np.max(s['f0']):3.0f}  {code}")
    print(f"ИТОГО: ниже 60 Гц {100 * sub_t / tot:.2f}% энергии, жужжание {100 * buzz_t / tot:.2f}%")

if __name__ == "__main__":
    name = sys.argv[1]
    eng = sys.argv[2] if len(sys.argv) > 2 else "golos"
    if eng == "golos":
        import golos
        run(lambda: golos.compose(golos.SONGS[name]))
    else:
        import rassvet4
        run(lambda: rassvet4.compose(eng.split(":")[1], name))
