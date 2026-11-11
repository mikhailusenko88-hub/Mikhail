#!/usr/bin/env python3
# Проверка пробной озвучки: фразы из папки (v/*.mp3 + index.json) — что слышно, идёт ли голос за ударениями, естественность.
#   python stage_check.py <папка с озвучкой> <куда записать json>
import json, os, sys, traceback
src, out_path = sys.argv[1], sys.argv[2]
import voice_check as vc
vc.IN, vc.OUT = "/tmp/sc_in", "/tmp/sc_out"
os.makedirs(vc.IN, exist_ok=True); os.makedirs(vc.OUT, exist_ok=True)
vc.plot = lambda *a, **kw: None
try:
    from faster_whisper import WhisperModel
    class FW:
        def __init__(self):
            self.m = WhisperModel(os.environ.get("FW", "medium"), device="cpu", compute_type="int8")
        def transcribe(self, path, language="ru", fp16=False):
            segs, _ = self.m.transcribe(vc.load16(path), language=language, beam_size=5, vad_filter=False, condition_on_previous_text=False)
            return {"text": " ".join(s.text.strip() for s in segs)}
    vc._m["wh"] = FW()
except Exception:
    traceback.print_exc()
idx = json.load(open(f"{src}/index.json", encoding="utf-8"))
out = {}
for i, (key, v) in enumerate(idx.items()):
    mp3 = f"{src}/v/{key}.mp3"
    if not os.path.exists(mp3):
        continue
    tp = f"{vc.IN}/{key}.txt"; open(tp, "w", encoding="utf-8").write(v["m"])
    try:
        r = vc.analyze(key, mp3, tp)
        o = {f: r.get(f) for f in ("dur", "heard", "match", "diff", "utmos", "f0_range", "f0_median_hz", "rate", "stress_errors", "stress_maybe", "intonation", "pauses")}
        o["t"] = v["t"]; o["m"] = v["m"]
        o["words"] = [[w["w"], w.get("exp"), w.get("det"), (round(float(w["margin"]), 2) if w.get("margin") is not None else None), w.get("ph"),
                       (round(w["t0"], 2) if w.get("t0") is not None else None), (round(w["t1"], 2) if w.get("t1") is not None else None), w.get("map_ok")] for w in r.get("words", [])]
        o["vowels"] = [[x["w"], x["k"], round(float(x["c"]), 3), x.get("L", "")] for x in r.get("vowels", [])]
        out[key] = o
    except Exception:
        out[key] = {"t": v["t"], "m": v["m"], "err": traceback.format_exc()[-400:]}
    if i % 10 == 0:
        print(i, "/", len(idx), flush=True)
os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("готово", len(out))
