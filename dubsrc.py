# Исходники для дубляжа из готового ролика (серии 1–26 сняты в телефоне — у них нет dub.zip студии).
#   python dubsrc.py <имя> <файл звука или видео>
# 1) голоса отдельно от музыки и шумов — demucs (htdemucs, MIT), 2) реплики и время — faster-whisper по дорожке голосов,
# реплика режется по паузе между словами > 0,35 с, 3) кто говорит — голосовой отпечаток ECAPA (speechbrain) и кластеры;
# имена героев кластерам даёт человек (geroi.json → rename.<имя>), 4) упаковка как у студии: dub/lines.json, dub/lines/NNN.wav,
# dub/me_00.wav (музыка и шумы), dub/full.wav (всё вместе) → dub.zip — дальше обычный dub.py.
import json, os, re, subprocess, sys, zipfile

import numpy as np
import soundfile as sf

NAME, SRC = sys.argv[1], sys.argv[2]
SR = 44100
W = os.path.join("tmp_dubsrc", NAME)
OUT = os.path.join("dubsrc", NAME)
os.makedirs(os.path.join(W, "dub", "lines"), exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def log(*a):
    print(*a, flush=True)


def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *a], check=True)


def load(p, sr=SR):
    a, s = sf.read(p, always_2d=True)
    a = a.mean(axis=1).astype(np.float32)
    if s != sr:
        import librosa
        a = librosa.resample(a, orig_sr=s, target_sr=sr).astype(np.float32)
    return a


# 1. всё вместе и разделение
full_p = os.path.join(W, "dub", "full.wav")
ff("-i", SRC, "-vn", "-ac", "1", "-ar", str(SR), full_p)
stereo = os.path.join(W, "src_st.wav")
ff("-i", SRC, "-vn", "-ac", "2", "-ar", str(SR), stereo)
log("demucs…")
subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", os.path.join(W, "sep"), stereo], check=True)
sd = os.path.join(W, "sep", "htdemucs", "src_st")
voc = load(os.path.join(sd, "vocals.wav"))
me = load(os.path.join(sd, "no_vocals.wav"))
full = load(full_p)
n = min(len(voc), len(me), len(full))
voc, me, full = voc[:n], me[:n], full[:n]
sf.write(os.path.join(W, "dub", "me_00.wav"), me, SR)
voc_p = os.path.join(W, "vocals.wav")
sf.write(voc_p, voc, SR)
dur = n / SR
log(f"длина {dur:.1f} с")

# 2. реплики
from faster_whisper import WhisperModel
model = WhisperModel(os.environ.get("WHISPER", "medium"), device="cpu", compute_type="int8")
segs, _ = model.transcribe(voc_p, language="ru", word_timestamps=True, vad_filter=True, beam_size=5,
                           vad_parameters={"min_silence_duration_ms": 300})
pieces = []
for s in segs:
    ws = [w for w in (s.words or []) if w.word.strip()]
    if not ws:
        continue
    cur = [ws[0]]
    for w in ws[1:]:
        if w.start - cur[-1].end > 0.35:
            pieces.append(cur)
            cur = [w]
        else:
            cur.append(w)
    pieces.append(cur)
lines = []
for p in pieces:
    t0, t1 = max(0.0, p[0].start - 0.08), min(dur, p[-1].end + 0.12)
    text = "".join(w.word for w in p).strip()
    if t1 - t0 < 0.25 or not re.search(r"\w", text):
        continue
    lines.append({"t": round(t0, 3), "bdur": round(t1 - t0, 3), "text": text})
log(f"реплик {len(lines)}")

# 3. кто говорит
import torch
from speechbrain.inference.speaker import EncoderClassifier
enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir=os.path.expanduser("~/.cache/ecapa"))
import librosa
v16 = librosa.resample(voc, orig_sr=SR, target_sr=16000)
emb, f0s = [], []
for ln in lines:
    a = v16[int(ln["t"] * 16000):int((ln["t"] + ln["bdur"]) * 16000)]
    if len(a) < 16000 * 0.5:
        a = np.pad(a, (0, int(16000 * 0.5) - len(a)))
    with torch.no_grad():
        e = enc.encode_batch(torch.tensor(a).unsqueeze(0)).squeeze().numpy()
    emb.append(e / (np.linalg.norm(e) + 1e-9))
    try:
        f, vf, _ = librosa.pyin(a, fmin=120, fmax=700, sr=16000)
        f0s.append(float(np.nanmedian(f[vf])) if np.any(vf) else 0.0)
    except Exception:
        f0s.append(0.0)
E = np.array(emb)
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
best = (None, -1, 2)
for k in range(2, min(8, len(lines) - 1) + 1):
    lab = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(E)
    sc = silhouette_score(E, lab, metric="cosine")
    log(f"k={k} силуэт {sc:.3f}")
    if sc > best[1] + 0.01:
        best = (lab, sc, k)
lab, sc, k = best
# голоса iPhone у героев из телефона — один и тот же голос с разной высотой: тембром (ECAPA) их не развести,
# поэтому кластер делим по высоте, если внутри есть заметный разрыв (Пик ~370 Гц и Рон ~300 Гц — 3,5 полутона)
def st(a, b):
    return 12 * np.log2(a / b)
lab = np.array(lab)
for _ in range(4):
    split = False
    for c in sorted(set(lab.tolist())):
        idx = [i for i in range(len(lines)) if lab[i] == c and f0s[i] > 0]
        if len(idx) < 6:
            continue
        srt = sorted(idx, key=lambda i: f0s[i])
        gaps = [(st(f0s[srt[j + 1]], f0s[srt[j]]), j) for j in range(2, len(srt) - 3)]
        if not gaps:
            continue
        g, j = max(gaps)
        lo, hi = srt[:j + 1], srt[j + 1:]
        dm = st(np.median([f0s[i] for i in hi]), np.median([f0s[i] for i in lo]))
        if g >= 0.8 and dm >= 2.5:
            nc = int(lab.max()) + 1
            for i in hi:
                lab[i] = nc
            log(f"кластер {c} разделён по высоте: {np.median([f0s[i] for i in lo]):.0f} / {np.median([f0s[i] for i in hi]):.0f} Гц (разрыв {g:.1f} пт)")
            split = True
    if not split:
        break
k = int(lab.max()) + 1
# кластеры — по убыванию высоты голоса: S1 — самый высокий
cl = {}
for c in range(k):
    idx = [i for i in range(len(lines)) if lab[i] == c]
    fs = [f0s[i] for i in idx if f0s[i] > 0]
    cl[c] = {"n": len(idx), "sec": round(sum(lines[i]["bdur"] for i in idx), 1), "f0": round(float(np.median(fs)), 0) if fs else 0}
order = sorted(cl, key=lambda c: -cl[c]["f0"])
names = {c: f"S{j + 1}" for j, c in enumerate(order)}
VOC = re.compile(r"^[\s\W]*((ха|хи|хе|хо|ах|ох|ой|эх|ух|а|о|м|хм|ммм?)[\s\W-]*)+$", re.I)
L = {"dur": round(dur, 3), "src": os.path.basename(SRC), "lines": []}
for i, ln in enumerate(lines):
    a = voc[int(ln["t"] * SR):int((ln["t"] + ln["bdur"]) * SR)]
    sf.write(os.path.join(W, "dub", "lines", f"{i:03d}.wav"), a, SR)
    L["lines"].append({"i": i, "t": ln["t"], "bdur": ln["bdur"], "name": names[lab[i]], "text": ln["text"],
                       "vocal": bool(VOC.match(ln["text"])), "f0": round(f0s[i]), "soft": False})
json.dump(L, open(os.path.join(W, "dub", "lines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
summary = {"name": NAME, "dur": L["dur"], "lines": len(lines), "k": k, "silhouette": round(float(sc), 3),
           "clusters": {names[c]: {**cl[c], "examples": [lines[i]["text"] for i in range(len(lines)) if lab[i] == c][:12]} for c in order}}
json.dump(summary, open(os.path.join(OUT, "clusters.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(L, open(os.path.join(OUT, "lines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "lines.txt"), "w", encoding="utf-8") as f:
    for x in L["lines"]:
        f.write(f"{x['i']:3d} {x['t']:7.2f} {x['bdur']:5.2f} {x['name']} {x['f0']:4d}{' V' if x['vocal'] else '  '} | {x['text']}\n")
# 4. упаковка
with zipfile.ZipFile(os.path.join(W, "dub.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(os.path.join(W, "dub")):
        for fn in files:
            p = os.path.join(root, fn)
            z.write(p, os.path.relpath(p, W))
log(json.dumps({k2: v for k2, v in summary.items() if k2 != "clusters"}, ensure_ascii=False))
for s2, c in summary["clusters"].items():
    log(s2, c["n"], c["sec"], c["f0"], " / ".join(c["examples"][:4]))
