#!/usr/bin/env python3
# Какие слова голос бота «Почему так?» смазывает: распознаватель слушает каждую готовую фразу и сверяет с текстом.
#   python bank_words.py <часть> <всего частей>   →  bank_out/words<часть>.json
import difflib, json, os, re, subprocess, sys
import numpy as np
k, n = int(sys.argv[1]), int(sys.argv[2])
SRC = "/tmp/pav"
if not os.path.exists(SRC):
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "pochemu-albina-voice", "--single-branch",
                    "https://github.com/mikhailusenko88-hub/Mikhail", SRC], check=True)
idx = json.load(open(f"{SRC}/index.json", encoding="utf-8"))
keys = sorted(idx)[k::n]
def load16(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()
def norm(t):
    t = t.lower().replace("ё", "е").replace("+", "")
    return re.sub(r"[^а-я0-9 -]+", " ", t).replace("-", " ").split()
from faster_whisper import WhisperModel
m = WhisperModel(os.environ.get("FW", "medium"), device="cpu", compute_type="int8")
out = {}
for i, key in enumerate(keys):
    mp3 = f"{SRC}/v/{key}.mp3"
    if not os.path.exists(mp3):
        continue
    try:
        segs, _ = m.transcribe(load16(mp3), language="ru", beam_size=5, vad_filter=False, condition_on_previous_text=False)
        heard = " ".join(s.text.strip() for s in segs)
        a, b = norm(idx[key]["m"]), norm(heard)
        sm = difflib.SequenceMatcher(None, a, b)
        out[key] = {"heard": heard, "match": round(sm.ratio(), 3),
                    "diff": [(" ".join(a[i1:i2]), " ".join(b[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]}
    except Exception as e:
        out[key] = {"err": str(e)[:200]}
    if i % 20 == 0:
        print(i, "/", len(keys), flush=True)
os.makedirs("bank_out", exist_ok=True)
json.dump(out, open(f"bank_out/words{k}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("готово", k, len(out))
