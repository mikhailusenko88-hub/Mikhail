# Пробник озвучки: одна фраза в нескольких вариантах. Результат кладётся в out/.
import asyncio, hashlib, os, traceback, wave

os.makedirs("out", exist_ok=True)
log = open("out/log.txt", "w", encoding="utf-8")

def say(*a):
    print(*a); print(*a, file=log); log.flush()

# Как текст обычно приходит в бот: цифры, без «ё», без ударений
RAW = "В 1 чайной ложке нейтронной звезды — около миллиарда тонн. И все это правда!"
# Тот же текст после правил: число словами в нужном падеже, «ё», ударение в омографе (звезды́ — род. падеж)
FIX = "В одной чайной ложке нейтронной звезды́ — около миллиарда тонн. И всё это правда!"
FIX_NOACC = FIX.replace("́", "")
# Для Silero ударение ставится знаком «+» перед ударной гласной
SIL = "В одн+ой ч+айной л+ожке нейтр+онной звезд+ы, +около милли+арда тонн. И всё +это пр+авда!"

VOICE = "ru-RU-DmitryNeural"

async def edge(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="+0%").save(path)

for name, text in [("a_raw", RAW), ("b_fix", FIX), ("b_fix_noacc", FIX_NOACC)]:
    try:
        asyncio.run(edge(text, f"out/{name}.mp3"))
        h = hashlib.md5(open(f"out/{name}.mp3", "rb").read()).hexdigest()
        say(name, "ok", os.path.getsize(f"out/{name}.mp3"), h)
    except Exception:
        say(name, "FAIL", traceback.format_exc())

try:
    import numpy as np, torch
    torch.set_num_threads(2)
    m = torch.package.PackageImporter("v4_ru.pt").load_pickle("tts_models", "model")
    m.to("cpu")
    for spk in ["aidar", "eugene", "xenia"]:
        a = m.apply_tts(text=SIL, speaker=spk, sample_rate=48000, put_accent=True, put_yo=True)
        x = (a.numpy() * 32767).clip(-32768, 32767).astype(np.int16)
        with wave.open(f"out/c_silero_{spk}.wav", "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(x.tobytes())
        say("silero", spk, "ok", len(x) / 48000, "s")
except Exception:
    say("silero FAIL", traceback.format_exc())
