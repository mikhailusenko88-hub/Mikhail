"""Шум по-настоящему: python3 noise2.py a.wav b.m4a ...
тишина в начале/конце (дБFS), доля верхов 5–16 кГц от всей энергии (вступление и весь трек),
абсолютный «пол» между гармониками 4–8 и 8–16 кГц (дБFS) во вступлении и в среднем."""
import subprocess, sys
import numpy as np

def load(p, sr=44100):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", p, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)

def stats(x, sr=44100):
    db = lambda v: 10 * np.log10(v + 1e-20)
    on = np.where(np.abs(x) > 1e-4)[0]
    s0 = on[0] if len(on) else 0
    head = db(np.mean(x[:max(1, s0 - 200)] ** 2)) if s0 > 400 else float("nan")
    tail = db(np.mean(x[-int(0.2 * sr):] ** 2))
    n, hop = 4096, 2048
    fr = np.lib.stride_tricks.sliding_window_view(x[s0:], n)[::hop] * np.hanning(n)
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2 / (n * n / 4) * 2 / 1.5
    f = np.fft.rfftfreq(n, 1 / sr)
    tot = S.sum(1)
    hf = S[:, (f >= 5000) & (f < 16000)].sum(1)
    k6 = int(6 * sr / hop)
    loud = db(tot) > db(tot.max()) - 40
    out = {"тишина до": head, "тишина в конце": tail,
           "верхи вступл.": db(hf[:k6].sum() / tot[:k6].sum()), "верхи весь": db(hf[loud].sum() / tot[loud].sum())}
    for lo, hi in ((4000, 8000), (8000, 16000)):
        b = (f >= lo) & (f < hi)
        fl = db(np.percentile(S[:, b], 20, axis=1) * b.sum())
        out[f"пол {lo // 1000}-{hi // 1000}к вступл."] = float(np.median(fl[:k6]))
        out[f"пол {lo // 1000}-{hi // 1000}к весь"] = float(np.median(fl[loud]))
    return out

if __name__ == "__main__":
    for p in sys.argv[1:]:
        s = stats(load(p))
        print(f"{p:26s}", " · ".join(f"{k} {v:6.1f}" for k, v in s.items()))
