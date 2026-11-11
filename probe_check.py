#!/usr/bin/env python3
# Проверка проб: фразы, озвученные способом бота «Почему так?» (part/v/*.mp3 + part/index.json) — туда ли встало ударение, что слышно.
import json, os, shutil, traceback
import voice_check as vc
vc.IN, vc.OUT = "/tmp/pc_in", "probe_out"
os.makedirs(vc.IN, exist_ok=True); os.makedirs(vc.OUT, exist_ok=True)
try:
    from faster_whisper import WhisperModel
    class FW:
        def __init__(self):
            self.m = WhisperModel(os.environ.get("FW", "medium"), device="cpu", compute_type="int8")
        def transcribe(self, path, language="ru", fp16=False):
            segs, _ = self.m.transcribe(path, language=language, beam_size=5, vad_filter=False, condition_on_previous_text=False)
            return {"text": " ".join(s.text.strip() for s in segs)}
    vc._m["wh"] = FW()
except Exception:
    traceback.print_exc()
idx = json.load(open("part/index.json", encoding="utf-8"))
json.dump(idx, open("probe_out/index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
rows = []
for key, v in idx.items():
    mp3 = f"part/v/{key}.mp3"
    if not os.path.exists(mp3):
        continue
    shutil.copyfile(mp3, f"probe_out/{key}.mp3")
    tp = f"{vc.IN}/{key}.txt"; open(tp, "w", encoding="utf-8").write(v["m"])
    try:
        r = vc.analyze(key, mp3, tp)
        bad = [f"{w['w']}: нужно {vc.mark(w['w'], w['exp'])}, слышно {vc.mark(w['w'], w['det'])} ({w.get('margin')})" for w in r.get("words", [])
               if w.get("exp") is not None and w.get("det") is not None and w["exp"] != w["det"]]
        rows.append(f"- {v['m']}\n  слышно: {r.get('heard')} | совпадение {r.get('match')} | UTMOS {r.get('utmos')} | не туда: {'; '.join(bad) or 'нет'}")
    except Exception:
        rows.append(f"- {v['m']} — сбой: {traceback.format_exc()[-200:]}")
open("probe_out/report.md", "w", encoding="utf-8").write("\n".join(rows) + "\n")
print("\n".join(rows))
