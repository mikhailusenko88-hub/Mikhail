import math, sys
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import fftconvolve
import theme as th
from theme import SR, m, legato_line, piano, harp, hall_ir, compressor
th.NOISE = 0.12; th.AIR = 0.7

def floor(x, t0=3.0, t1=7.0):
    seg = x[int(t0*SR):int(t1*SR)]
    n = 4096
    fr = np.lib.stride_tricks.sliding_window_view(seg, n)[::2048]*np.hanning(n)
    S = (np.abs(np.fft.rfft(fr, axis=1))**2/(n*n/4)).mean(0); f = np.fft.rfftfreq(n, 1/SR)
    out = []
    for lo, hi in ((1000, 4000), (4000, 8000), (8000, 16000)):
        b = (f>=lo)&(f<hi)
        out.append(10*np.log10(np.percentile(S[b], 20)*b.sum()+1e-30))
    return 10*np.log10(np.mean(seg**2)+1e-30), out

def master2(bus, reverb=True, comp=True, lim=True):
    L, R = bus.L.copy(), bus.R.copy()
    if reverb:
        irL, irR = hall_ir(11), hall_ir(23)
        L = L + 0.55*fftconvolve(bus.sL + 0.35*bus.sR, irL)[:len(L)]
        R = R + 0.55*fftconvolve(bus.sR + 0.35*bus.sL, irR)[:len(R)]
    out = []
    for ch in (L, R):
        ch = ch - gaussian_filter1d(ch, SR/(2*math.pi*30))
        band = gaussian_filter1d(ch, SR/(2*math.pi*450)) - gaussian_filter1d(ch, SR/(2*math.pi*150))
        ch = ch - 0.22*band
        air = ch - gaussian_filter1d(ch, SR/(2*math.pi*4500))
        out.append(ch + th.AIR*air)
    L, R = out
    pk = max(np.abs(L).max(), np.abs(R).max()); L, R = L/pk, R/pk
    if comp:
        L, R = compressor(L, R, thr_db=-15, ratio=1.8)
        pk = max(np.abs(L).max(), np.abs(R).max()); L, R = L/pk, R/pk
    if lim:
        d = 1.15; L, R = np.tanh(L*d)/math.tanh(d), np.tanh(R*d)/math.tanh(d)
    return (L+R)/2

def mk(parts):
    th.TOTAL = 10; bus = th.Bus()
    BEAT = 60/76
    if "pad" in parts:
        for k, nt in enumerate(("F3", "A3", "C4")):
            s, ts = legato_line([(0.3, 9.0, m(nt), 0.07)], voices=5, att=1.3, rel=2.5, bright=1.0, vib=0.004, glide=0.07, noise=0.3)
            bus.add(s, ts, pan=-0.3+0.3*k, send=0.34)
    if "bass" in parts:
        s, ts = legato_line([(0.3, 9.0, m("F3"), 0.19)], voices=5, att=0.9, rel=2.5, bright=0.75, vib=0.003, glide=0.05, noise=0.35)
        bus.add(s, ts, pan=0.25, send=0.3)
    if "piano" in parts:
        pat = [m(x) for x in ("F3", "C4", "F4", "A4", "C5", "A4", "F4", "C4")]
        for j in range(22):
            bus.add(piano(pat[j % 8], BEAT*1.2, 0.15), 0.3 + j*BEAT/2, pan=-0.1, send=0.32)
    if "harp" in parts:
        pat = [m(x) for x in ("F4", "A4", "C5", "F5", "A5", "C5", "A4", "F5")]
        for j in range(22):
            bus.add(harp(pat[j % 8], 0.085), 0.3 + j*BEAT/2, pan=-0.3, send=0.35)
    return bus

for parts in (("pad",), ("bass",), ("piano",), ("harp",), ("pad", "bass", "piano")):
    bus = mk(parts)
    for name, kw in (("полный мастер", {}), ("без лимитера", dict(lim=False)), ("без реверба", dict(reverb=False)), ("сухой без всего", dict(reverb=False, comp=False, lim=False))):
        lv, fl = floor(master2(bus, **kw))
        print(f"{'+'.join(parts):16s} {name:16s} уровень {lv:6.1f} · пол 1–4к {fl[0]:7.1f} · 4–8к {fl[1]:7.1f} · 8–16к {fl[2]:7.1f}")
