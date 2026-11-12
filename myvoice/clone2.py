# Голос Михаила, круг 2: образцы по 10 с из его минутной записи × настройки модели → выбор по программам распознавания говорящего.
#   python clone2.py <вся запись.wav> <старая запись 9 с.wav> <папка>
import sys, os, json, time, subprocess, numpy as np, torch, soundfile as sf
full, old, out = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(out, exist_ok=True)
torch.set_num_threads(os.cpu_count() or 4)
W, SR = sf.read(full, dtype='float32', always_2d=True); W = W.mean(1)
def cut(a, b, name):
    p = f"/tmp/k/{name}.wav"; sf.write(p, W[int(a * SR):int(b * SR)], SR); return p
REFS = {"r0": old, "r1": cut(8.3, 18.3, "r1"), "r2": cut(14.6, 24.6, "r2"), "r3": cut(25.0, 35.0, "r3"),
        "r4": cut(36.6, 46.6, "r4"), "r5": cut(41.8, 51.8, "r5")}
PARTS = [cut(0, 7.9, "p0"), cut(8.3, 24.6, "p1"), cut(25.0, 36.3, "p2"), cut(36.6, 51.8, "p3")]   # его речь для сравнения
T = [("t1", "Привет! Это мой голос, только сказала это за меня нейросеть."),
     ("t2", "Почему у жирафа такая длинная шея? Учёные считают, что так ему проще дотянуться до листьев на высоких деревьях."),
     ("t3", "А ты это знал?")]
CFG = {"c1": dict(exaggeration=0.5, cfg_weight=0.5), "c2": dict(exaggeration=0.35, cfg_weight=0.3)}
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
t0 = time.time(); m = ChatterboxMultilingualTTS.from_pretrained(device="cpu"); print("модель", round(time.time() - t0), "с", flush=True)
for r, rp in REFS.items():
    for c, kw in CFG.items():
        t1 = time.time()
        for n, t in T:
            torch.manual_seed(7)
            w = m.generate(t, language_id="ru", audio_prompt_path=rp, **kw); sf.write(f"{out}/A_{r}_{c}_{n}.wav", w.squeeze().cpu().numpy(), m.sr)
        print("A", r, c, round(time.time() - t1), "с", flush=True)
del m
from chatterbox.vc import ChatterboxVC
vc = ChatterboxVC.from_pretrained(device="cpu")
for r, rp in REFS.items():
    for n in ("a", "b", "z"):
        w = vc.generate(audio=f"myvoice/src_{n}.mp3", target_voice_path=rp); sf.write(f"{out}/B_{r}_{n}.wav", w.squeeze().cpu().numpy(), vc.sr)
    print("B", r, flush=True)
del vc
# --- программы распознавания говорящего ---
files = sorted(f for f in os.listdir(out) if f.endswith(".wav"))
def load16(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()
M = {}
try:
    from speechbrain.inference.speaker import EncoderClassifier
    ec = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="/tmp/ecapa", run_opts={"device": "cpu"})
    def e1(p):
        with torch.no_grad(): e = ec.encode_batch(torch.from_numpy(load16(p)).unsqueeze(0)).squeeze().numpy()
        return e / np.linalg.norm(e)
    M["ecapa"] = e1
except Exception as ex: print("ECAPA нет:", ex, flush=True)
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    ve = VoiceEncoder("cpu")
    def e2(p):
        e = ve.embed_utterance(preprocess_wav(load16(p), source_sr=16000)); return e / np.linalg.norm(e)
    M["resemblyzer"] = e2
except Exception as ex: print("Resemblyzer нет:", ex, flush=True)
res = {"models": list(M), "files": {}, "self": {}, "nash3": {}}
for mn, f in M.items():
    P = [f(p) for p in PARTS]; tgt = np.mean(P, 0); tgt /= np.linalg.norm(tgt)
    # он сам: каждый кусок против остальных — уровень «это он»
    res["self"][mn] = [float(P[i] @ (lambda v: v / np.linalg.norm(v))(np.mean([P[j] for j in range(4) if j != i], 0))) for i in range(4)]
    res["nash3"][mn] = float(f("myvoice/src_a.mp3") @ tgt)
    for fn in files: res["files"].setdefault(fn, {})[mn] = float(f(f"{out}/{fn}") @ tgt)
# --- что слышно ---
try:
    from faster_whisper import WhisperModel
    wm = WhisperModel("small", device="cpu", compute_type="int8")
    for fn in files:
        segs, _ = wm.transcribe(load16(f"{out}/{fn}"), language="ru", beam_size=5)
        res["files"][fn]["heard"] = " ".join(s.text.strip() for s in segs)
except Exception as ex: print("Whisper нет:", ex, flush=True)
json.dump(res, open(f"{out}/metrics.json", "w"), ensure_ascii=False, indent=0)
print("готово", flush=True)
