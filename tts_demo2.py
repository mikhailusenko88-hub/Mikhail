# Пробник №2: больше голосов + автоматическая оценка (UTMOS — естественность, Whisper — разборчивость).
import asyncio, difflib, json, os, re, subprocess, traceback, urllib.request, wave
import numpy as np, torch, yaml

import shutil
O = "out2"
shutil.rmtree(O, ignore_errors=True)
os.makedirs(O, exist_ok=True)
log = open(f"{O}/log.txt", "w", encoding="utf-8")
def say(*a):
    print(*a, flush=True); print(*a, file=log); log.flush()

FIX = "В одной чайной ложке нейтронной звезды́ — около миллиарда тонн. И всё это правда!"
SIL = "В одн+ой ч+айной л+ожке нейтр+онной звезд+ы, +около милли+арда тонн. И всё +это пр+авда!"
REF = "в одной чайной ложке нейтронной звезды около миллиарда тонн и все это правда"

def save_wav(x, path, sr=48000):
    x = (np.asarray(x) * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())

def to_mp3(src, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-b:a", "160k", dst], check=True)

# ---------- Microsoft (edge-tts): русские + мультиязычные голоса ----------
async def edge_all():
    import edge_tts
    vs = await edge_tts.list_voices()
    names = sorted(v["ShortName"] for v in vs)
    ru = [n for n in names if n.startswith("ru-RU")]
    multi = [n for n in names if "Multilingual" in n]
    say("edge ru:", ru); say("edge multilingual:", multi)
    for v in ru + multi:
        try:
            await asyncio.wait_for(edge_tts.Communicate(FIX, v).save(f"{O}/edge__{v}.mp3"), 40)
        except Exception as e:
            say("edge fail", v, repr(e))
        if os.path.exists(f"{O}/edge__{v}.mp3") and os.path.getsize(f"{O}/edge__{v}.mp3") < 2000:
            os.remove(f"{O}/edge__{v}.mp3")
try:
    asyncio.run(edge_all())
except Exception:
    say("edge FAIL", traceback.format_exc())

# ---------- Silero v5: ищем модели в models.yml ----------
pk = {}
try:
    y = yaml.safe_load(urllib.request.urlopen(
        "https://raw.githubusercontent.com/snakers4/silero-models/master/models.yml").read())
    def walk(n, path):
        if isinstance(n, dict):
            if "package" in n:
                pk["/".join(path)] = n["package"]
            for k, v in n.items():
                walk(v, path + [str(k)])
    walk(y.get("tts_models", y), [])
    for k, v in pk.items():
        if "v5" in k:
            say("silero model:", k, v)
except Exception:
    say("models.yml FAIL", traceback.format_exc())

def pick(sub, bad=()):
    c = [(k, v) for k, v in pk.items() if sub in k and not any(b in k for b in bad)]
    c.sort(key=lambda kv: ("latest" not in kv[0], kv[0]))
    return c[0][1] if c else None

def silero(url, tag, text, only=None):
    f = f"{tag}.pt"
    urllib.request.urlretrieve(url, f)
    m = torch.package.PackageImporter(f).load_pickle("tts_models", "model")
    m.to("cpu")
    spk = [s for s in getattr(m, "speakers", []) if s != "random"]
    say(tag, "speakers:", spk)
    for s in spk:
        if only and not only(s):
            continue
        try:
            try:
                a = m.apply_tts(text=text, speaker=s, sample_rate=48000, put_accent=True, put_yo=True)
            except TypeError:
                a = m.apply_tts(text=text, speaker=s, sample_rate=48000)
            save_wav(a.numpy() if hasattr(a, "numpy") else a, f"{O}/tmp.wav")
            to_mp3(f"{O}/tmp.wav", f"{O}/{tag}__{s}.mp3")
        except Exception as e:
            say(tag, s, "fail", repr(e))

torch.set_num_threads(2)
for sub, bad, tag, only in [("v5_6_ru", (), "silero56", None),
                            ("v5_cis_ext", ("nostress",), "sileroEXT", lambda s: s.startswith("ru_")),
                            ("v5_cis_base", ("nostress",), "sileroCIS", lambda s: s.startswith("ru_"))]:
    try:
        u = pick(sub, bad)
        say("use", tag, u)
        if u:
            silero(u, tag, SIL, only)
    except Exception:
        say(tag, "FAIL", traceback.format_exc())
if os.path.exists(f"{O}/tmp.wav"):
    os.remove(f"{O}/tmp.wav")

# ---------- Оценка: UTMOS (1–5, естественность) + Whisper (совпадение текста) ----------
files = sorted(f for f in os.listdir(O) if f.endswith(".mp3"))
res = {f: {} for f in files}

def load16(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

try:
    mos = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
    for f in files:
        try:
            x = torch.from_numpy(load16(f"{O}/{f}")).unsqueeze(0)
            with torch.no_grad():
                res[f]["utmos"] = round(float(mos(x, 16000)), 3)
        except Exception as e:
            say("utmos", f, repr(e))
except Exception:
    say("utmos FAIL", traceback.format_exc())

def norm(t):
    t = t.lower().replace("ё", "е")
    t = re.sub(r"[^а-я0-9 ]+", " ", t)
    return t.split()
try:
    import whisper
    wm = whisper.load_model("small")
    for f in files:
        try:
            r = wm.transcribe(f"{O}/{f}", language="ru", fp16=False)
            t = r["text"].strip()
            res[f]["text"] = t
            res[f]["match"] = round(difflib.SequenceMatcher(None, norm(t), norm(REF)).ratio(), 3)
        except Exception as e:
            say("whisper", f, repr(e))
except Exception:
    say("whisper FAIL", traceback.format_exc())

json.dump(res, open(f"{O}/results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for f, r in sorted(res.items(), key=lambda kv: -kv[1].get("utmos", 0)):
    say(f"{r.get('utmos', '-'):>6}  {r.get('match', '-'):>5}  {f}  | {r.get('text', '')}")
