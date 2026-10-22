import json, wave
import numpy as np, torch
torch.set_num_threads(2)
lines = json.load(open('lines.json', encoding='utf-8'))
m = torch.package.PackageImporter('v4_ru.pt').load_pickle('tts_models', 'model')
m.to('cpu')
for i, t in enumerate(lines):
    a = m.apply_tts(text=t, speaker='aidar', sample_rate=48000, put_accent=True, put_yo=True)
    x = (a.numpy() * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(f'l{i:02d}.wav', 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(x.tobytes())
    print('  фраза', i + 1, 'готова')
