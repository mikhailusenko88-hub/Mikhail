#!/usr/bin/env python3
# Генератор пробной озвучки по gen.txt. Строка: имя | голос | текст для озвучки | эталонный текст (необязательно)
# Голос: silero:kseniya (aidar, baya, eugene, xenia — модель v5_6_ru) или edge:ru-RU-DmitryNeural
# В тексте ударение можно ставить «+» перед гласной (зв+ёзды). Для edge «+» превращается в знак ударения.
import asyncio, hashlib, os, re, subprocess, urllib.request, wave
import numpy as np

os.makedirs("in", exist_ok=True); os.makedirs("models", exist_ok=True)
VOW = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"
_silero = {}

def silero_model(mid="v5_6_ru"):
    if mid not in _silero:
        import torch
        f = f"models/{mid}.pt"
        if not os.path.exists(f):
            urllib.request.urlretrieve(f"https://models.silero.ai/models/tts/ru/{mid}.pt", f)
        m = torch.package.PackageImporter(f).load_pickle("tts_models", "model"); m.to("cpu")
        torch.set_num_threads(2)
        _silero[mid] = m
    return _silero[mid]

def save_wav(x, path, sr=48000):
    x = (np.asarray(x) * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())

def plus_to_acute(t):
    return re.sub(r"\+([" + VOW + "])", lambda m: m.group(1) + "́", t)

def main():
    for line in open("gen.txt", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            print("пропуск (мало полей):", line); continue
        name, voice, text = parts[:3]
        ref = parts[3] if len(parts) > 3 and parts[3] else text
        h = hashlib.md5(line.encode()).hexdigest()
        if os.path.exists(f"in/{name}.gen") and open(f"in/{name}.gen").read().strip() == h:
            print("уже есть:", name); continue
        eng, _, spk = voice.partition(":")
        try:
            if eng == "silero":
                m = silero_model()
                try:
                    a = m.apply_tts(text=text, speaker=spk, sample_rate=48000, put_accent=True, put_yo=True)
                except TypeError:
                    a = m.apply_tts(text=text, speaker=spk, sample_rate=48000)
                save_wav(a.numpy() if hasattr(a, "numpy") else a, f"in/{name}.wav")
            elif eng == "silero_cis":
                # свободная (MIT) модель без авторасстановки ударений — недостающие ставим через ruaccent
                # голос можно уточнить: silero_cis:ru_albina@slow,low  (темп: x-slow/slow/medium/fast, тон: x-low/low/high)
                import voice_check as vc
                spk, _, opts = spk.partition("@")
                ws = vc.tokenize(text)
                vc.accentize(text, ws)
                out = []
                for w in ws:
                    e = w["exp"]
                    if len(w["vows"]) >= 2 and e is not None:
                        k = -1; t2 = ""
                        for c in w["w"]:
                            if c in vc.VOW:
                                k += 1
                                if k == e:
                                    t2 += "+"
                            t2 += c
                        out.append(t2 + w["punct"])
                    else:
                        out.append(w["w"] + w["punct"])
                marked = " ".join(out)
                open(f"in/{name}.marked", "w", encoding="utf-8").write(marked + "\n")
                m = silero_model("v5_cis_base")
                if opts:
                    rate = next((o for o in opts.split(",") if o in ("x-slow", "slow", "medium", "fast", "x-fast")), "medium")
                    pitch = next((o for o in opts.split(",") if o in ("x-low", "low", "medium", "high", "x-high")), "medium")
                    ssml = f'<speak><prosody rate="{rate}" pitch="{pitch}">{marked}</prosody></speak>'
                    a = m.apply_tts(ssml_text=ssml, speaker=spk, sample_rate=48000)
                else:
                    a = m.apply_tts(text=marked, speaker=spk, sample_rate=48000)
                save_wav(a.numpy() if hasattr(a, "numpy") else a, f"in/{name}.wav")
            elif eng == "silero_random":
                # новый, случайно придуманный голос (Silero v4); сохраняется в voices/, чтобы потом звучать так же
                import torch
                m = silero_model("v4_ru")
                os.makedirs("voices", exist_ok=True)
                vp = f"voices/random_{spk}.pt"
                if os.path.exists(vp):
                    a = m.apply_tts(text=text, voice_path=vp, sample_rate=48000, put_accent=True, put_yo=True)
                else:
                    torch.manual_seed(int(spk))
                    a = m.apply_tts(text=text, speaker="random", sample_rate=48000, put_accent=True, put_yo=True)
                    m.save_random_voice(vp)
                save_wav(a.numpy() if hasattr(a, "numpy") else a, f"in/{name}.wav")
            elif eng == "morph":
                # morph:<голос Silero>:<сдвиг формант>:<средняя высота, Гц> — новый тембр из готового голоса (Praat «Change gender»)
                import parselmouth
                from parselmouth.praat import call
                src, fs, pm = spk.split(":")
                m = silero_model()
                a = m.apply_tts(text=text, speaker=src, sample_rate=48000, put_accent=True, put_yo=True)
                x = (a.numpy() if hasattr(a, "numpy") else np.asarray(a)).astype(np.float64)
                snd = parselmouth.Sound(x, 48000)
                out = call(snd, "Change gender", 75, 600, float(fs), float(pm), 1.0, 1.0)
                save_wav(out.values[0], f"in/{name}.wav")
            elif eng == "edge":
                import edge_tts
                asyncio.run(edge_tts.Communicate(plus_to_acute(text), spk).save(f"in/{name}.mp3"))
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"in/{name}.mp3", f"in/{name}.wav"], check=True)
                os.remove(f"in/{name}.mp3")
            else:
                print("неизвестный движок:", voice); continue
            open(f"in/{name}.txt", "w", encoding="utf-8").write(ref + "\n")
            open(f"in/{name}.voice", "w", encoding="utf-8").write(voice + "\n")
            open(f"in/{name}.gen", "w").write(h + "\n")
            print("готово:", name)
        except Exception as e:
            print("ошибка", name, repr(e))

if __name__ == "__main__":
    main()
