# Вопросы бота новым голосом ru_nash3 с поправкой мелодии (начало вопроса ровнее) — и для сравнения Альбина тем же кодом.
import os, sys, json, subprocess
sys.path.insert(0, "/opt/multik-tts")
import server
server.CACHE = "/tmp/nash_cache3"; os.makedirs(server.CACHE, exist_ok=True)
server.load(); assert server.state.get("ready"), server.state
Q = json.load(open("nashtest/questions.json", encoding="utf-8"))
os.makedirs("/tmp/o2/v", exist_ok=True); idx = {}
for q in Q:
    for spk, p in (("ru_nash3", "q"), ("ru_albina", "b")):
        wav = server.make(q["t"], spk, True, "medium", "medium", "bot")
        open("/tmp/o2/x.wav", "wb").write(wav); name = f"{p}_{q['i']:03d}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "/tmp/o2/x.wav", "-ac", "1", "-ar", "24000", "-b:a", "64k", f"/tmp/o2/v/{name}.mp3"], check=True)
        idx[name] = {"t": q["t"], "m": q["t"]}
json.dump(idx, open("/tmp/o2/index.json", "w", encoding="utf-8"), ensure_ascii=False)
print("готово", len(idx))
