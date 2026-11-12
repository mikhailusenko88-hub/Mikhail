import json, os, numpy as np, soundfile as sf, subprocess
os.makedirs('out', exist_ok=True)
x, sr = sf.read('ep16.wav'); x = x.astype(np.float32)
from transformers import pipeline
clf = pipeline('audio-classification', model='MIT/ast-finetuned-audioset-10-10-0.4593', top_k=None)
LAUGH = {'Laughter', 'Giggle', 'Baby laughter', 'Belly laugh', 'Chuckle, chortle', 'Snicker', 'Children shouting'}
res = []; W, H = int(1.0 * sr), int(.5 * sr)
for i in range(0, max(1, len(x) - W), H):
    seg = x[i:i + W]
    if np.abs(seg).max() < 1e-3: continue
    out = clf({'raw': seg, 'sampling_rate': sr})
    sc = {o['label']: o['score'] for o in out}
    lp = max(sc.get(k, 0) for k in LAUGH if k != 'Children shouting')
    top = sorted(out, key=lambda o: -o['score'])[:4]
    res.append({'t': round(i / sr, 1), 'laugh': round(float(lp), 3), 'top': [(o['label'], round(o['score'], 2)) for o in top]})
json.dump(res, open('out/frames.json', 'w'), ensure_ascii=False)
# участки смеха
segs = []; cur = None
for r in res:
    if r['laugh'] >= .25:
        if cur and r['t'] - cur['t1'] <= 1.0: cur['t1'] = r['t'] + 1; cur['peak'] = max(cur['peak'], r['laugh'])
        else:
            cur = {'t0': r['t'], 't1': r['t'] + 1, 'peak': r['laugh']}; segs.append(cur)
from faster_whisper import WhisperModel
m = WhisperModel('small', device='cpu', compute_type='int8')
ws, _ = m.transcribe('ep16.wav', language='ru', word_timestamps=False, vad_filter=False)
tr = [{'t0': round(s.start, 1), 't1': round(s.end, 1), 'text': s.text.strip()} for s in ws]
json.dump(tr, open('out/transcript.json', 'w'), ensure_ascii=False, indent=0)
for k, s in enumerate(segs):
    s['near'] = [t for t in tr if t['t1'] >= s['t0'] - 6 and t['t0'] <= s['t1'] + 4]
    a, b = max(0, s['t0'] - 2), s['t1'] + 2
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(a), '-t', str(b - a), '-i', 'ep16.wav', 'out/laugh_%02d_%s.wav' % (k, str(s['t0']).replace('.', '_'))])
json.dump(segs, open('out/laughs.json', 'w'), ensure_ascii=False, indent=1)
subprocess.run(['cp', 'ep.mp3', 'out/'])
for s in segs:
    print('СМЕХ %6.1f–%6.1f пик %.2f' % (s['t0'], s['t1'], s['peak']))
    for t in s['near']: print('      %6.1f %s' % (t['t0'], t['text']))
