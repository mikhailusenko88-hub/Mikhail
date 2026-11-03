import json, wave, numpy as np
SR = 44100; T = 10.0
a = np.zeros(int((T + 0.6) * SR)); rng = np.random.default_rng(3)
def put(sig, at, vol=1.0):
    s = int(at * SR)
    if s < 0 or s >= len(a): return
    n = min(len(sig), len(a) - s); a[s:s+n] += sig[:n] * vol
def env(n, att, dec):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(att, 1e-4)) * np.exp(-t * dec)
def tone(f, dur, decay=5.0, harm=(1, 0.3, 0.1), att=0.004):
    n = int(dur * SR); t = np.arange(n) / SR
    s = sum(h * np.sin(2*np.pi*f*(k+1)*t) for k, h in enumerate(harm))
    return s * env(n, att, decay)
def marimba(f, dur=0.9):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2*np.pi*f*t)*np.exp(-t*6) + 0.35*np.sin(2*np.pi*f*4*t)*np.exp(-t*20) + 0.15*np.sin(2*np.pi*f*10*t)*np.exp(-t*40)) * np.minimum(1, t*600)
def noise(dur, decay, lp=8):
    n = int(dur * SR); x = rng.uniform(-1, 1, n)
    x = np.convolve(x, np.ones(lp)/lp, mode='same'); return x * env(n, 0.002, decay)
def lowpass(x, k):
    return np.convolve(x, np.ones(k)/k, mode='same')
land = json.load(open('landings.json'))
# --- wind / meadow ambience
w = rng.uniform(-1, 1, len(a)); w = lowpass(lowpass(w, 400), 200)
mod = 0.6 + 0.4*np.sin(2*np.pi*0.13*np.arange(len(a))/SR + 1.0)
a += w / (np.abs(w).max()+1e-9) * 0.09 * mod
# --- pad chord (warm) : C major add9 with slow swell
tt = np.arange(len(a)) / SR
for f, v in [(130.81, 0.5), (196.0, 0.35), (261.63, 0.3), (329.63, 0.25), (392.0, 0.2), (587.33, 0.12)]:
    vib = 1 + 0.003*np.sin(2*np.pi*5.1*tt + f)
    a += v * 0.09 * np.sin(2*np.pi*f*vib*tt) * (0.5 - 0.5*np.cos(np.pi*np.minimum(1, tt/2.5))) * (0.7 + 0.3*np.sin(2*np.pi*0.21*tt))
# --- melody: pentatonic marimba, one note per hop + fills
pent = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.7]
seq = [0, 2, 4, 2, 5, 4, 2, 1, 0, 2, 4, 6, 5, 4, 2, 4]
hops = [l['t'] for l in land if not l['big']]
for i, t0 in enumerate(hops):
    put(marimba(pent[seq[i % len(seq)]]), t0 - 0.68 + 0.02, 0.38)   # on take-off
    put(marimba(pent[seq[(i+3) % len(seq)] ] / 2, 0.6), t0 - 0.68 + 0.34, 0.16)  # off-beat
    # landing: soft thud + boing
    n = int(0.25*SR); t = np.arange(n)/SR
    put(np.sin(2*np.pi*(95 - 40*t)*t) * np.exp(-t*18), t0, 0.5)
    put(noise(0.08, 40, 6), t0, 0.12)
    put(np.sin(2*np.pi*(260 + 120*np.exp(-t*12))*t) * np.exp(-t*14), t0 + 0.02, 0.1)
    # wing flutter during the hop
    n2 = int(0.5*SR); t2 = np.arange(n2)/SR
    put(np.sin(2*np.pi*170*t2)*(0.5+0.5*np.sin(2*np.pi*14*t2))*np.sin(np.pi*t2/0.5)**0.5, t0-0.62, 0.035)
# --- big jump: whoosh up, then BOOM + shimmer + rumble
big = [l['t'] for l in land if l['big']][0]
n = int(1.1*SR); t = np.arange(n)/SR
ws = rng.uniform(-1, 1, n); ws = lowpass(ws, 30) * np.sin(np.pi*t/1.1)**2
put(ws / (np.abs(ws).max()+1e-9), big - 1.1, 0.22)
put(np.sin(2*np.pi*(300 + 500*t/1.1)*t) * np.sin(np.pi*t/1.1)**2, big - 1.1, 0.05)  # rising
n = int(2.5*SR); t = np.arange(n)/SR
put(np.sin(2*np.pi*(55 - 20*t)*t) * np.exp(-t*3.0), big, 0.9)                      # boom
put(np.sin(2*np.pi*(38)*t) * np.exp(-t*1.2) * (0.6+0.4*np.sin(2*np.pi*7*t)), big+0.05, 0.5)  # rumble
put(noise(0.35, 12, 4), big, 0.3)
for k, f in enumerate([523.25, 659.25, 783.99, 1046.5, 1318.5, 1568.0, 2093.0]):
    put(tone(f, 1.8, decay=2.2, harm=(1, 0.2)), big + 0.08 + k*0.07, 0.11)
# final soft chime
for k, f in enumerate([1046.5, 1318.5, 1568.0]):
    put(tone(f, 1.6, decay=2.0, harm=(1, 0.15)), 9.1 + k*0.12, 0.09)
# fade out tail
fade = np.ones(len(a)); fo = int(0.6*SR); fade[-fo:] = np.linspace(1, 0, fo); a *= fade
a = a[:int(T*SR)]
a = a / max(1e-9, np.abs(a).max()) * 0.9
with wave.open('honey_audio.wav', 'wb') as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((a*32767).astype(np.int16).tobytes())
print('audio ok', len(hops), 'hops, big at', big)
