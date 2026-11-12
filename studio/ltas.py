"""Спектральная чистота: python3 ltas.py файл...
доли энергии по полосам (дБ от всей), плотность спектра 1–8 кГц (0 = редкие чистые линии, больше = «каша» из призвуков)."""
import subprocess, sys
import numpy as np
def load(p):
    raw = subprocess.run(["ffmpeg","-v","quiet","-i",p,"-ac","1","-ar","44100","-f","f32le","-"],capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)
BANDS = [(20,60),(60,120),(120,250),(250,500),(500,1000),(1000,2000),(2000,4000),(4000,8000),(8000,16000)]
def stats(x):
    n = 8192
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::4096]*np.hanning(n)
    S = np.abs(np.fft.rfft(fr, axis=1))**2; f = np.fft.rfftfreq(n, 1/44100)
    P = S.mean(0); tot = P.sum()
    row = [10*np.log10(P[(f>=lo)&(f<hi)].sum()/tot + 1e-20) for lo,hi in BANDS]
    b = (f>=1000)&(f<8000)
    act = S.sum(1) > 0.01*S.sum(1).max()
    p = S[act][:, b] + 1e-20
    flat = float(np.median(np.exp(np.log(p).mean(1))/p.mean(1)))
    return row, flat
if __name__ == "__main__":
    print(f"{'':22s}" + " ".join(f"{lo}-{hi}".rjust(9) for lo,hi in BANDS) + "  плотность")
    for fn in sys.argv[1:]:
        row, flat = stats(load(fn))
        print(f"{fn:22s}" + " ".join(f"{v:9.1f}" for v in row) + f"  {flat:.5f}")
