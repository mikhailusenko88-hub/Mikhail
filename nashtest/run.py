# Свои голоса в модели бота (torch, как в ферме озвучки): озвучить пробные фразы режимом бота, с мягким тоном и без.
import os, sys, json, subprocess, time
sys.path.insert(0, "/opt/multik-tts")
import server
server.CACHE = "/tmp/nash_cache"; os.makedirs(server.CACHE, exist_ok=True)
t0 = time.time(); server.load(); print("загрузка", round(time.time() - t0, 1), "с", server.state, flush=True)
assert server.state.get("ready"), server.state
T = {"a": "Почему у жирафа такая длинная шея? Учёные считают, что так ему проще дотянуться до листьев на высоких деревьях.",
     "b": "А вы знали, что осьминог может менять цвет кожи всего за долю секунды? Так он прячется от врагов и охотится.",
     "c": "Однажды утром друзья пошли в лес. У реки стоял старый замок, а в его окнах горел тёплый свет.",
     "q": "Верблюд хранит воду в горбу?", "z": "А ты это знал?"}
os.makedirs("/tmp/out/v", exist_ok=True); idx = {}
for spk in ["ru_nash1", "ru_nash2", "ru_nash3", "ru_albina"]:
    for k, t in T.items():
        for soft in (False, True):
            wav = server.make(t, spk, soft, "medium", "medium", "bot")
            name = f"t_{spk[3:]}_{k}{'_soft' if soft else ''}"
            open(f"/tmp/out/{name}.wav", "wb").write(wav)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"/tmp/out/{name}.wav", "-ac", "1", "-ar", "24000", "-b:a", "64k", f"/tmp/out/v/{name}.mp3"], check=True)
            if not soft: idx[name] = {"t": t, "m": t}
        print(spk, k, "готово", flush=True)
json.dump(idx, open("/tmp/out/index.json", "w", encoding="utf-8"), ensure_ascii=False)
