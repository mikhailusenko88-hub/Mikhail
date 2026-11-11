#!/usr/bin/env python3
# «Послушать» готовую озвучку бота «Почему так?» (ветка pochemu-albina-voice): все фразы банка, по частям.
#   python bank_listen.py <часть> <всего частей>   →  bank_out/part<часть>.json
# На каждую фразу: что услышал распознаватель (смазанные слова), идёт ли голос за метками ударений, естественность (UTMOS),
# размах мелодии, темп, интонация конца фразы. Эталон ударений — метки самого бота («+»), так видно, где Альбина их не послушалась.
import json, os, subprocess, sys, traceback
k, n = int(sys.argv[1]), int(sys.argv[2])
SRC = "/tmp/pav"
if not os.path.exists(SRC):
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "pochemu-albina-voice", "--single-branch",
                    "https://github.com/mikhailusenko88-hub/Mikhail", SRC], check=True)
idx = json.load(open(f"{SRC}/index.json", encoding="utf-8"))
keys = sorted(idx)[k::n]
import voice_check as vc
vc.IN, vc.OUT = "/tmp/vc_in", "/tmp/vc_out"
os.makedirs(vc.IN, exist_ok=True); os.makedirs(vc.OUT, exist_ok=True)
vc.plot = lambda *a, **kw: None          # картинки не нужны — только цифры
try:
    from faster_whisper import WhisperModel
    class FW:
        def __init__(self):
            self.m = WhisperModel(os.environ.get("FW", "medium"), device="cpu", compute_type="int8")
        def transcribe(self, path, language="ru", fp16=False):
            segs, _ = self.m.transcribe(vc.load16(path), language=language, beam_size=5, vad_filter=False, condition_on_previous_text=False)   # звук читаем сами: новый PyAV ломает чтение файла
            return {"text": " ".join(s.text.strip() for s in segs)}
    vc._m["wh"] = FW()
except Exception:
    traceback.print_exc()
out = {}
for i, key in enumerate(keys):
    mp3 = f"{SRC}/v/{key}.mp3"
    if not os.path.exists(mp3):
        out[key] = {"err": "нет файла"}; continue
    tp = f"{vc.IN}/{key}.txt"
    open(tp, "w", encoding="utf-8").write(idx[key]["m"])
    try:
        r = vc.analyze(key, mp3, tp)
        o = {f: r.get(f) for f in ("dur", "heard", "match", "diff", "utmos", "f0_range", "f0_median_hz", "rate", "stress_errors",
                                   "stress_maybe", "intonation", "pauses", "align_error", "accent_source")}
        o["bad"] = [[w["w"], w.get("exp"), w.get("det"), round(float(w.get("margin") or 0), 2)] for w in r.get("words", [])
                    if w.get("exp") is not None and w.get("det") is not None and w["exp"] != w["det"] and (w.get("margin") or 0) >= 0.5]
        out[key] = o
    except Exception:
        out[key] = {"err": traceback.format_exc()[-400:]}
    if i % 10 == 0:
        print(i, "/", len(keys), flush=True)
os.makedirs("bank_out", exist_ok=True)
json.dump(out, open(f"bank_out/part{k}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("готово", k, len(out))
