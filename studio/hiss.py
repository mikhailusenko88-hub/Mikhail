"""Шипение и треск: python3 hiss.py a.wav [b.wav ...]
шипение — уровень «пола» шума в 6–16 кГц (20-й перцентиль по частотам, т.е. между гармониками) относительно всей энергии кадра;
шум между нотами — то же в тихих кадрах; треск — короткие (≤3 мс) всплески высоких частот выше местного фона в 6 раз."""
import subprocess, sys
import numpy as np
from scipy.ndimage import uniform_filter1d, median_filter

def load(p, sr=44100):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", p, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)

def hiss(x, sr=44100):
    n, hop = 2048, 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    tot = S.sum(1) + 1e-15
    band = (f >= 6000) & (f < 16000)
    floor = np.percentile(S[:, band], 20, axis=1) * band.sum()
    db = 10 * np.log10(floor / tot + 1e-15)
    loud = 10 * np.log10(tot) > 10 * np.log10(tot.max()) - 35
    quiet = (10 * np.log10(tot) < np.percentile(10 * np.log10(tot[loud]), 25)) & loud
    hp = np.diff(x, 2)
    e = uniform_filter1d(hp ** 2, 44)[::44]
    base = median_filter(e, 101) + 1e-15
    r = e / base
    tick = (r[1:-3] > 6) & (r[:-4] < 2.5) & (r[4:] < 2.5) & (e[1:-3] > 1e-9)
    return np.median(db[loud]), np.percentile(db[loud], 90), (np.median(db[quiet]) if quiet.any() else float("nan")), int(tick.sum()) / (len(x) / sr)

for p in sys.argv[1:]:
    a, b, q, t = hiss(load(p))
    print(f"{p:34s} шипение {a:6.1f} дБ (90%: {b:6.1f}) · в тихих местах {q:6.1f} дБ · треск {t:5.2f}/с")
