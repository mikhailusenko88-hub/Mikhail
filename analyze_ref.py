import sys, numpy as np, librosa, librosa.display, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
wav, title, url = sys.argv[1], sys.argv[2], sys.argv[3]
y2, sr = librosa.load(wav, sr=22050, mono=False)
y = librosa.to_mono(y2)
dur = len(y) / sr
out = [f"## {title}\n{url}\nДлительность: {dur:.1f} с"]
if y2.ndim == 2:
    c = np.corrcoef(y2[0], y2[1])[0, 1]
    out.append(f"Стерео: корреляция L/R {c:.2f} ({'почти моно' if c > 0.95 else 'широкое' if c < 0.6 else 'умеренное'})")
yh, yp = librosa.effects.hpss(y)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
tempo = float(np.atleast_1d(tempo)[0])
bt = librosa.frames_to_time(beats, sr=sr)
out.append(f"Темп: {tempo:.1f} уд/мин; долей найдено: {len(bt)}")
ep, eh = float(np.sum(yp ** 2)), float(np.sum(yh ** 2))
out.append(f"Ударные/перкуссия: {100 * ep / (ep + eh):.0f}% энергии (гармоническая часть {100 * eh / (ep + eh):.0f}%)")
# тональность (Крумхансл)
chroma = librosa.feature.chroma_cqt(y=yh, sr=sr)
cm = chroma.mean(1)
names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
maj = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
mnr = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
sc = [(np.corrcoef(np.roll(maj, k), cm)[0, 1], names[k] + " мажор") for k in range(12)] + [(np.corrcoef(np.roll(mnr, k), cm)[0, 1], names[k] + " минор") for k in range(12)]
sc.sort(reverse=True)
out.append("Тональность: " + ", ".join(f"{n} ({v:.2f})" for v, n in sc[:3]))
out.append("Профиль нот (средняя хрома): " + " ".join(f"{names[i]}:{cm[i]:.2f}" for i in np.argsort(-cm)[:7]))
# аккорды по долям (шаблоны мажор/минор/септ)
tmpl = []
for r in range(12):
    for q, iv in (("", (0, 4, 7)), ("m", (0, 3, 7)), ("7", (0, 4, 7, 10)), ("m7", (0, 3, 7, 10)), ("maj7", (0, 4, 7, 11))):
        v = np.zeros(12); v[[(r + i) % 12 for i in iv]] = 1
        tmpl.append((names[r] + q, v / np.linalg.norm(v)))
bsync = librosa.util.sync(chroma, beats, aggregate=np.median) if len(beats) > 2 else chroma
seq = []
for k in range(bsync.shape[1]):
    v = bsync[:, k]; v = v / (np.linalg.norm(v) + 1e-9)
    best = max(tmpl, key=lambda t: float(t[1] @ v))
    seq.append(best[0])
# сжать повторы
comp = []
for s in seq:
    if comp and comp[-1][0] == s: comp[-1][1] += 1
    else: comp.append([s, 1])
out.append("Аккорды по долям (аккорд×долей): " + " ".join(f"{a}×{n}" for a, n in comp[:80]))
# мелодия (верхний голос) — pyin по гармонической части
f0, vf, vp = librosa.pyin(yh, fmin=librosa.note_to_hz("C3"), fmax=librosa.note_to_hz("C7"), sr=sr, frame_length=2048, hop_length=256)
tt = librosa.times_like(f0, sr=sr, hop_length=256)
notes = []
cur = None
for t, f, v in zip(tt, f0, vf):
    n = librosa.hz_to_note(f) if (v and f and not np.isnan(f)) else None
    if n != (cur[0] if cur else None):
        if cur and cur[0] and t - cur[1] >= 0.09:
            notes.append((cur[0], cur[1], t - cur[1]))
        cur = (n, t)
mel = " ".join(f"{n}({d:.2f})" for n, s, d in notes[:160])
out.append(f"Мелодия (нота(длительность с), первые {min(160, len(notes))} из {len(notes)}): " + mel)
vr = float(np.mean(vf))
out.append(f"Доля кадров с ясной высотой (мелодичность): {vr:.2f}")
# тембр
cen = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
roll = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85).mean()
flat = librosa.feature.spectral_flatness(y=y).mean()
out.append(f"Тембр: центроид {cen:.0f} Гц, 85%-спад {roll:.0f} Гц, «шумность» {flat:.3f}")
S = np.abs(librosa.stft(y, n_fft=4096)) ** 2
fr = librosa.fft_frequencies(sr=sr, n_fft=4096)
tot = S.sum()
bands = [(20, 60), (60, 120), (120, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4000), (4000, 8000), (8000, 11025)]
out.append("Спектр по полосам, дБ: " + ", ".join(f"{a}-{b}:{10*np.log10(S[(fr>=a)&(fr<b)].sum()/tot+1e-12):.0f}" for a, b in bands))
rms = librosa.feature.rms(y=y, hop_length=sr // 2)[0]
out.append("Громкость по полсекунды, дБ: " + " ".join(f"{20*np.log10(r+1e-9):.0f}" for r in rms))
on = librosa.onset.onset_detect(y=yp, sr=sr, units="time")
out.append(f"Ударов/атак в секунду (перкуссия): {len(on)/dur:.1f}")
# картинки
fig, ax = plt.subplots(3, 1, figsize=(16, 11))
D = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=2048, hop_length=512)), ref=np.max)
librosa.display.specshow(D, sr=sr, hop_length=512, x_axis="time", y_axis="log", ax=ax[0]); ax[0].set_title("спектрограмма")
librosa.display.specshow(chroma, sr=sr, x_axis="time", y_axis="chroma", ax=ax[1]); ax[1].set_title("хрома (ноты)")
ax[2].plot(tt, f0); ax[2].set_yscale("log"); ax[2].set_title("мелодия f0"); ax[2].set_xlim(0, dur)
plt.tight_layout(); plt.savefig("status/" + wav.split("/")[-1].replace(".wav", ".png"), dpi=70)
print("\n".join(out))
