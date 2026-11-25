# Пары «образец — находка» рядом: спектр до 14 кГц + высота
import sys, subprocess, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import signal
files = sys.argv[2:]; out = sys.argv[1]
def load(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "44100", "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float), 44100
def f0tr(x, sr, lo=55, hi=700):
    hop, win = int(sr * .01), int(sr * .045); t, f = [], []
    e = np.sqrt(np.mean(x * x))
    for s in range(0, len(x) - win, hop):
        fr = x[s:s + win]; t.append(s / sr)
        if np.sqrt(np.mean(fr * fr)) < .12 * e: f.append(np.nan); continue
        fr = fr - fr.mean(); ac = np.correlate(fr, fr, "full")[win - 1:]; ac /= ac[0] + 1e-12
        a, b = int(sr / hi), int(sr / lo); k = a + int(np.argmax(ac[a:b])); f.append(sr / k if ac[k] > .5 else np.nan)
    return np.array(t), np.array(f)
fig, ax = plt.subplots(len(files), 1, figsize=(13, 2.6 * len(files)))
for r, spec in enumerate(files):
    name, p = spec.split("=", 1)
    x, sr = load(p)
    f, t, S = signal.spectrogram(x, sr, nperseg=1024, noverlap=768)
    D = 10 * np.log10(S + 1e-12)
    ax[r].pcolormesh(t, f / 1000, D, vmin=D.max() - 75, vmax=D.max() - 5, cmap="magma", shading="auto"); ax[r].set_ylim(0, 14)
    tt, ff = f0tr(x, sr); a2 = ax[r].twinx(); a2.plot(tt, ff, color="cyan", lw=2); a2.set_ylim(40, float(sys.argv[0] and 450))
    ax[r].set_title(f"{name}  (высота {np.nanmedian(ff):.0f} Гц, длина {len(x)/sr:.2f} с)", fontsize=10)
fig.tight_layout(); fig.savefig(out, dpi=75)
