"""Поиск треска: python3 tresk.py a.wav b.wav ...
1) «дребезг»: насколько огибающая полосы 300–4000 Гц дрожит с частотой 25–110 Гц (низкий жужжащий бас слышен как треск);
2) импульсы: всплески второй разности выше местного уровня (щелчки);
3) доля энергии ниже 60 Гц и ниже 120 Гц (телефонный динамик на большой громкости от неё хрипит)."""
import subprocess, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt, hilbert

SR = 44100
def load(p):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)

def rough(x, win=1.0):
    sos = butter(4, [300, 4000], btype="band", fs=SR, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, x)))
    env = env[::10]                                   # 4410 Гц
    fs = SR / 10
    n = int(win * fs)
    out = []
    for i in range(0, len(env) - n, n // 2):
        e = env[i:i + n]
        if e.mean() < 1e-4:
            out.append(0.0); continue
        S = np.abs(np.fft.rfft((e - e.mean()) * np.hanning(n))) / (n / 4)
        f = np.fft.rfftfreq(n, 1 / fs)
        b = (f >= 25) & (f <= 110)
        out.append(float(np.sqrt((S[b] ** 2).sum()) / e.mean()))
    return np.array(out)

def impulses(x):
    d2 = np.abs(np.diff(x, 2))
    k = 2205
    loc = np.sqrt(np.convolve(d2 ** 2, np.ones(k) / k, mode="same")) + 1e-9
    r = d2 / loc
    idx = np.where((r > 12) & (d2 > 2e-4))[0]
    ev = []
    for i in idx:
        if not ev or i - ev[-1][0] > 441:
            ev.append([i, r[i]])
    return ev

def lows(x):
    S = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    tot = S.sum()
    return 10 * np.log10(S[f < 60].sum() / tot + 1e-12), 10 * np.log10(S[f < 120].sum() / tot + 1e-12)

if __name__ == "__main__":
    for p in sys.argv[1:]:
        x = load(p)
        r = rough(x)
        ev = impulses(x)
        l60, l120 = lows(x)
        top = np.argsort(r)[::-1][:5]
        print(f"{p:22s} дребезг: медиана {np.median(r):.3f}, 90% {np.percentile(r, 90):.3f}, макс {r.max():.3f} (на {', '.join(f'{t * 0.5:.0f}с' for t in sorted(top))}) · "
              f"импульсов {len(ev)} · ниже 60 Гц {l60:5.1f} дБ, ниже 120 Гц {l120:5.1f} дБ")
