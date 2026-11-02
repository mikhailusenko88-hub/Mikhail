# Голос Барсика для образца: Silero (ru), детский тембр (сдвиг высоты), длительности реплик.
import torch, urllib.request, subprocess, json, os, wave, numpy as np
os.makedirs('out/voice', exist_ok=True)
torch.set_num_threads(4)
urllib.request.urlretrieve('https://models.silero.ai/models/tts/ru/v5_6_ru.pt', 'ru.pt')
m = torch.package.PackageImporter('ru.pt').load_pickle('tts_models', 'model'); m.to('cpu')
print('speakers', m.speakers)
LINES = {'l1': 'Привет! Я Барсик!', 'l2': 'Ой... Кто это там шуршит в кустах?', 'l3': 'Пойдём посмотрим! Ура!'}
info = {}
for spk in ['xenia', 'baya', 'kseniya']:
    for k, txt in LINES.items():
        try: a = m.apply_tts(text=txt, speaker=spk, sample_rate=48000, put_accent=True, put_yo=True)
        except TypeError: a = m.apply_tts(text=txt, speaker=spk, sample_rate=48000)
        a = (np.clip(a.numpy(), -1, 1) * 32767).astype(np.int16)
        raw = f'out/voice/{spk}_{k}_raw.wav'
        with wave.open(raw, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(a.tobytes())
        out = f'out/voice/{spk}_{k}.wav'   # чуть выше и моложе: высота x1.12 без изменения скорости
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', 'asetrate=53760,aresample=48000,atempo=0.9286,loudnorm=I=-16:TP=-1.5', '-ar', '48000', '-ac', '1', out], check=True)
        os.remove(raw)
        with wave.open(out) as w: info[f'{spk}_{k}'] = w.getnframes() / w.getframerate()
json.dump(info, open('out/voice/durations.json', 'w'), ensure_ascii=False, indent=1); print(info)
