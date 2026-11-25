import sys, subprocess, numpy as np
from scipy import signal
def load(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "44100", "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)
def stats(x, sr=44100):
    hop = 441; n = len(x) // hop
    e = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    act = e > e.max() - 45
    a, b = np.where(act)[0][[0, -1]]
    e = e[a:b + 1]
    f, t, S = signal.spectrogram(x[a * hop:(b + 1) * hop], sr, nperseg=1024, noverlap=512)
    P = S.mean(1)
    band = lambda lo, hi: 10 * np.log10(P[(f >= lo) & (f < hi)].mean() + 1e-15)
    ref = band(300, 3000)
    # глубина провалов: громкость 10-го процентиля кадров относительно 90-го; модуляция огибающей 4-16 Гц
    return {"p90-p10": round(np.percentile(e, 90) - np.percentile(e, 10), 1), "p90-p2": round(np.percentile(e, 90) - np.percentile(e, 2), 1),
            "3-6k": round(band(3000, 6000) - ref, 1), "6-10k": round(band(6000, 10000) - ref, 1), "10-16k": round(band(10000, 16000) - ref, 1), "80-300": round(band(80, 300) - ref, 1)}
for spec in sys.argv[1:]:
    name, p = spec.split("=", 1)
    print(name.ljust(28), stats(load(p)))
