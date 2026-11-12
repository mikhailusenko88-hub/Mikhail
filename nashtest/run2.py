# Настоящие фразы бота «Почему так?»: новый голос ru_nash3 тем же путём, что ферма (режим бота, мягкий тон), и Альбина из готовой озвучки.
import os, sys, json, subprocess, shutil, time
sys.path.insert(0, "/opt/multik-tts")
import server
server.CACHE = "/tmp/nash_cache2"; os.makedirs(server.CACHE, exist_ok=True)
server.load(); assert server.state.get("ready"), server.state
P = json.load(open("nashtest/phrases.json", encoding="utf-8"))
os.makedirs("/tmp/o2/v", exist_ok=True); idx = {}
for i, p in enumerate(P):
    wav = server.make(p["t"], "ru_nash3", True, "medium", "medium", "bot")
    open("/tmp/o2/x.wav", "wb").write(wav)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "/tmp/o2/x.wav", "-ac", "1", "-ar", "24000", "-b:a", "64k", f"/tmp/o2/v/n_{i:03d}.mp3"], check=True)
    a = f"/tmp/pav/v/{p['key']}.mp3"
    if os.path.exists(a): shutil.copy(a, f"/tmp/o2/v/a_{i:03d}.mp3")
    idx[f"n_{i:03d}"] = {"t": p["t"], "m": p["t"]}; idx[f"a_{i:03d}"] = {"t": p["t"], "m": p["t"]}
    if i % 10 == 0: print(i, flush=True)
json.dump(idx, open("/tmp/o2/index.json", "w", encoding="utf-8"), ensure_ascii=False)
