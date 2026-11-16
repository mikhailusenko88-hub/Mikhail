# Приёмка собранной серии: файл, листы кадров, громкость и тишина, слова по сценарию (распознавание), паспорт голосов героев.
#   python qa.py <папка сборки> <ffmpeg>
import sys, os, json, re, subprocess, math, glob, difflib, traceback
OUT, FF = sys.argv[1], sys.argv[2]
QA = os.path.join(OUT, 'qa'); os.makedirs(QA, exist_ok=True)
R = {'ok': True, 'notes': []}
def run(a, **k): return subprocess.run(a, capture_output=True, text=True, **k)
def note(s): R['notes'].append(s); print('!', s)
res = json.load(open(os.path.join(OUT, 'result.json'), encoding='utf-8')) if os.path.exists(os.path.join(OUT, 'result.json')) else {}
mp4s = sorted(glob.glob(os.path.join(OUT, 'video', '*.mp4')), key=os.path.getsize, reverse=True)
if not mp4s: R['ok'] = False; note('нет видео'); json.dump(R, open(os.path.join(QA, 'qa.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1); sys.exit(0)
MP4 = mp4s[0]
sp_path = os.path.join(OUT, 'files', 'speech.json'); SP = json.load(open(sp_path, encoding='utf-8')) if os.path.exists(sp_path) else None

# 1. файл
try:
    e = run([FF, '-hide_banner', '-i', MP4]).stderr
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', e); dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r'Video: (\w+).*?(\d{3,4})x(\d{3,4}).*?([\d.]+) fps', e); a = re.search(r'Audio: (\w+).*?(\d+) Hz, (\w+)', e)
    R['file'] = {'mb': round(os.path.getsize(MP4) / 1048576, 1), 'dur': round(dur, 2), 'video': v.group(1) if v else '?', 'w': int(v.group(2)) if v else 0, 'h': int(v.group(3)) if v else 0,
                 'fps': float(v.group(4)) if v else 0, 'audio': a.group(1) if a else 'НЕТ', 'hz': int(a.group(2)) if a else 0, 'ch': a.group(3) if a else ''}
    if SP: R['file']['plan_dur'] = round(SP['dur'], 2); R['file']['dur_ok'] = abs(dur - SP['dur']) <= 2
    if not a: R['ok'] = False; note('в файле нет звука')
except Exception as ex: note('файл: ' + str(ex))
DUR = R.get('file', {}).get('dur', 0)

# 2. листы кадров: начало (каждую секунду первые 16 с) и вся серия (каждые 6 с)
try:
    run([FF, '-y', '-loglevel', 'error', '-t', '16', '-i', MP4, '-vf', 'fps=1,scale=480:270,tile=4x4', '-frames:v', '1', '-q:v', '4', os.path.join(QA, 'nachalo.jpg')])
    step = 6 if DUR > 150 else max(1, round(DUR / 30))
    run([FF, '-y', '-loglevel', 'error', '-i', MP4, '-vf', f'fps=1/{step},scale=320:180,tile=6x5', '-q:v', '5', os.path.join(QA, 'list_%02d.jpg')])
    R['sheets'] = {'step': step, 'files': sorted(os.path.basename(f) for f in glob.glob(os.path.join(QA, 'list_*.jpg')))}
    # тёмные и одинаковые кадры
    import numpy as np
    from PIL import Image
    raw = run([FF, '-loglevel', 'error', '-i', MP4, '-vf', 'fps=1,scale=64:36,format=gray', '-f', 'rawvideo', '-'], text=False) if False else subprocess.run([FF, '-loglevel', 'error', '-i', MP4, '-vf', 'fps=1,scale=64:36,format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
    fr = np.frombuffer(raw, dtype=np.uint8); n = len(fr) // (64 * 36); fr = fr[:n * 64 * 36].reshape(n, 36, 64).astype(np.float32)
    cuts = [g['t0'] for g in SP['segs']] if SP else []   # затемнение на стыке сцен — это переход, а не брак
    mean = fr.mean(axis=(1, 2)); dark = [int(i) for i in np.where(mean < 18)[0] if not any(abs(i - c) <= 1.5 for c in cuts) and i < n - 2]
    diff = np.abs(fr[1:] - fr[:-1]).mean(axis=(1, 2)); still = []; runlen = 0
    for i, d in enumerate(diff):
        runlen = runlen + 1 if d < 0.35 else 0
        if runlen == 6: still.append(int(i - 5))
    R['frames'] = {'checked': int(n), 'dark_sec': dark[:20], 'still_from_sec': still[:20], 'mean_brightness': round(float(mean.mean()), 1)}
    if dark: note(f'тёмные кадры на секундах: {dark[:10]}')
    if still: note(f'картинка стоит 6 с и дольше, начиная с секунд: {still[:10]}')
except Exception as ex: note('кадры: ' + str(ex)); traceback.print_exc()

# 2а. кадры-кандидаты: моменты восклицаний и вопросов (для обложки и для проверки мордочек)
try:
    if SP:
        cand = [s for s in SP['speech'] if not s.get('vocal') and s['name'] != 'Рассказчик' and re.search(r'[!?]', s['text']) and s['dur'] > 0.8]
        if len(cand) > 24: cand = [cand[round(i * (len(cand) - 1) / 23)] for i in range(24)]
        os.makedirs(os.path.join(QA, 'kadry'), exist_ok=True)
        for s in cand:
            t = s['t'] + min(0.45, s['dur'] / 2)
            run([FF, '-y', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', MP4, '-frames:v', '1', '-vf', 'scale=640:360', '-q:v', '4', os.path.join(QA, 'kadry', f"k_{int(t):04d}_{s['name']}.jpg")])
        R['kadry'] = len(cand)
except Exception as ex: note('кадры-кандидаты: ' + str(ex))

# 3. звук: громкость, пик, тишина
WAV = os.path.join(QA, 'audio16k.wav')
try:
    run([FF, '-y', '-loglevel', 'error', '-i', MP4, '-vn', '-ac', '1', '-ar', '16000', WAV])
    e = run([FF, '-hide_banner', '-nostats', '-i', MP4, '-vn', '-af', 'ebur128=peak=true,silencedetect=noise=-45dB:d=3', '-f', 'null', '-']).stderr
    I = re.findall(r'I:\s+(-?[\d.]+) LUFS', e); LRA = re.findall(r'LRA:\s+([\d.]+) LU', e); PK = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', e)
    sil = [(float(a), float(b)) for a, b in zip(re.findall(r'silence_start: ([\d.]+)', e), re.findall(r'silence_end: ([\d.]+)', e))]
    R['audio'] = {'lufs': float(I[-1]) if I else None, 'lra': float(LRA[-1]) if LRA else None, 'peak_db': float(PK[-1]) if PK else None, 'silences': [[round(a, 1), round(b - a, 1)] for a, b in sil][:20]}
    if I and not (-20 <= float(I[-1]) <= -12): note(f'громкость {I[-1]} LUFS (для YouTube лучше около −14…−16)')
    if sil: note(f'тишина дольше 3 с: {[(round(a), round(b - a, 1)) for a, b in sil][:8]}')
except Exception as ex: note('звук: ' + str(ex))

# 4. слова по сценарию
def norm(s): return re.sub(r'[^а-яa-z0-9 ]', ' ', re.sub(r'([а-яё])(-\1)+', r'\1', s.lower().replace('ё', 'е').replace('+', '').replace('\u0301', '').replace('\u00ad', ''))).split()
try:
    if not SP: raise RuntimeError('нет расписания реплик')
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get('WHISPER', 'small'), device='cpu', compute_type='int8')
    segs, info = model.transcribe(WAV, language='ru', word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    words = []; full = []
    for s in segs:
        full.append(f'[{s.start:.1f}] {s.text.strip()}')
        for w in (s.words or []):
            for t in norm(w.word): words.append((w.start, w.end, t))
    open(os.path.join(QA, 'raspoznano.txt'), 'w', encoding='utf-8').write('\n'.join(full))
    lines = []; by = {}; tot = hit = 0
    for s in SP['speech']:
        if s.get('vocal'): continue
        exp = norm(s['text'])
        if not exp: continue
        got = [w[2] for w in words if w[1] >= s['t'] - 0.4 and w[0] <= s['t'] + s['dur'] + 0.5]; used = [False] * len(got); h = 0; miss = []
        for x in exp:
            best = -1; bs = 0
            for i, g in enumerate(got):
                if used[i]: continue
                r_ = 1.0 if g == x else difflib.SequenceMatcher(None, g, x).ratio()
                if r_ > bs: bs, best = r_, i
            if best >= 0 and bs >= 0.72: used[best] = True; h += 1
            else: miss.append(x)
        tot += len(exp); hit += h; b = by.setdefault(s['name'], [0, 0]); b[0] += h; b[1] += len(exp)
        lines.append({'t': s['t'], 'name': s['name'], 'text': s['text'], 'ok': h, 'n': len(exp), 'miss': miss, 'heard': ' '.join(got)})
    # второй проход: распознаватель иногда пропускает целый кусок — реплики без единого слова слушаем отдельно
    try:
        import numpy as np, wave
        wf = wave.open(WAV, 'rb'); sr = wf.getframerate(); pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0; wf.close(); re2 = 0
        for l in lines:
            if l['n'] >= 2 and l['ok'] == 0:
                sline = next(x for x in SP['speech'] if x['t'] == l['t']); a = max(0, int((l['t'] - 0.8) * sr)); b = min(len(pcm), int((l['t'] + sline['dur'] + 0.8) * sr))
                sg2, _ = model.transcribe(pcm[a:b], language='ru', beam_size=5, condition_on_previous_text=False); got = [t for s2 in sg2 for t in norm(s2.text)]
                exp = norm(l['text']); used = [False] * len(got); h = 0; miss = []
                for x in exp:
                    best = -1; bs = 0
                    for i, g in enumerate(got):
                        if used[i]: continue
                        r_ = 1.0 if g == x else difflib.SequenceMatcher(None, g, x).ratio()
                        if r_ > bs: bs, best = r_, i
                    if best >= 0 and bs >= 0.72: used[best] = True; h += 1
                    else: miss.append(x)
                hit += h; by[l['name']][0] += h; l.update(ok=h, miss=miss, heard=' '.join(got), second=True); re2 += 1
        R['words_second_pass'] = re2
    except Exception as ex: note('слова, второй проход: ' + str(ex))
    bad = sorted([l for l in lines if l['n'] >= 2 and l['ok'] / l['n'] < 0.6], key=lambda l: l['ok'] / l['n'])
    R['words'] = {'pct': round(100 * hit / max(1, tot), 1), 'lines': len(lines), 'by_hero': {k: round(100 * v[0] / max(1, v[1]), 1) for k, v in by.items()}, 'worst': bad[:15]}
    json.dump(lines, open(os.path.join(QA, 'repliki.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    if R['words']['pct'] < 85: note(f"слова по сценарию: распознано {R['words']['pct']}% (порог 85%; музыка под речью снижает число)")
except Exception as ex: note('слова: ' + str(ex)); traceback.print_exc()

# 5. паспорт голосов (чистые реплики героев до музыки)
def passport(p, text):
    import parselmouth, numpy as np
    from parselmouth.praat import call
    snd = parselmouth.Sound(p); d = snd.get_total_duration()
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=110, pitch_ceiling=900); f0 = pitch.selected_array['frequency']; f0 = f0[f0 > 0]
    if len(f0) < 20: return None
    med = float(np.median(f0)); p10, p90 = np.percentile(f0, [10, 90])
    hn = snd.to_harmonicity_cc(time_step=0.01, minimum_pitch=110).values; hn = hn[hn > -100]
    pp = call(snd, 'To PointProcess (periodic, cc)', 110, 900)
    jit = call(pp, 'Get jitter (local)', 0, 0, 0.0001, 0.02, 1.3); shim = call([snd, pp], 'Get shimmer (local)', 0, 0, 0.0001, 0.02, 1.3, 1.6)
    fm = snd.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=7000); F = [[], [], []]
    for t in pitch.xs():
        if pitch.get_value_at_time(t) and not math.isnan(pitch.get_value_at_time(t)):
            for k in range(3):
                v = fm.get_value_at_time(k + 1, t)
                if v and not math.isnan(v): F[k].append(v)
    sp = snd.to_spectrum(); lo = sp.get_band_energy(300, 2500); hi = sp.get_band_energy(2500, 6000); top = sp.get_band_energy(6000, 11000)
    syl = len(re.findall(r'[аеёиоуыэюя]', (text or '').lower()))
    return {'dur': round(d, 2), 'f0': round(med), 'f0_lo': round(float(p10)), 'f0_hi': round(float(p90)), 'range_st': round(12 * math.log2(p90 / p10), 1), 'voiced': round(len(f0) * 0.01 / d, 2),
            'hnr': round(float(hn.mean()), 1) if len(hn) else None, 'jitter': round(100 * jit, 2), 'shimmer': round(100 * shim, 1), 'F1': round(float(np.median(F[0]))) if F[0] else None, 'F2': round(float(np.median(F[1]))) if F[1] else None, 'F3': round(float(np.median(F[2]))) if F[2] else None,
            'bright': round(10 * math.log10(max(hi, 1e-12) / max(lo, 1e-12)), 1), 'air': round(10 * math.log10(max(top, 1e-12) / max(lo, 1e-12)), 1), 'cog': round(sp.get_centre_of_gravity(2)), 'rate': round(syl / d, 1) if syl else None}
try:
    import numpy as np
    V = {}
    for p in sorted(glob.glob(os.path.join(OUT, 'files', 'voices', '*.wav'))):
        name = os.path.basename(p).rsplit('_', 1)[0]; text = open(p + '.txt', encoding='utf-8').read() if os.path.exists(p + '.txt') else ''
        try:
            r_ = passport(p, text)
            if r_: V.setdefault(name, []).append(r_)
        except Exception as ex: print('голос', p, ex)
    P = {}
    for name, rs in V.items():
        g = lambda k: [x[k] for x in rs if x.get(k) is not None]
        P[name] = {k: (round(float(np.median(g(k))), 1) if g(k) else None) for k in ['f0', 'range_st', 'hnr', 'jitter', 'shimmer', 'F1', 'F2', 'F3', 'bright', 'air', 'cog', 'rate', 'voiced']}; P[name]['n'] = len(rs)
        f0 = P[name]['f0'] or 0
        P[name]['age'] = 'мультяшно-детский' if f0 >= 330 else 'детский' if f0 >= 260 else 'подросток/женский' if f0 >= 190 else 'взрослый'
        s = 5.0; why = []
        if P[name]['hnr'] is not None and P[name]['hnr'] < 9: s -= 1; why.append('шумный, сиплый тембр')
        elif P[name]['hnr'] is not None and P[name]['hnr'] < 12: s -= .5; why.append('немного шумный тембр')
        if (P[name]['jitter'] or 0) > 2.5: s -= .7; why.append('дрожит высота')
        if (P[name]['shimmer'] or 0) > 14: s -= .5; why.append('дрожит громкость')
        if (P[name]['bright'] or -99) > -6: s -= .7; why.append('резкий верх (свист, «песок»)')
        if f0 > 460: s -= .7; why.append('писклявый')
        if (P[name]['range_st'] or 9) < 3.5: s -= .6; why.append('монотонный')
        if (P[name]['range_st'] or 9) > 17: s -= .4; why.append('высота скачет')
        P[name]['pleasant'] = round(max(1, s), 1); P[name]['why'] = why
        if 'words' in R and name in R['words']['by_hero']: P[name]['clear_pct'] = R['words']['by_hero'][name]
    names = [n for n in P if P[n]['f0']]; close = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = P[names[i]], P[names[j]]; st = abs(12 * math.log2(a['f0'] / b['f0'])); df = abs((a['F2'] or 0) - (b['F2'] or 0))
            if st < 1.5 and df < 150: close.append([names[i], names[j], round(st, 1)])
    R['voices'] = P; R['voices_close'] = close
    if close: note('голоса почти не различаются: ' + '; '.join(f'{a} и {b}' for a, b, _ in close))
except Exception as ex: note('голоса: ' + str(ex)); traceback.print_exc()

R['build'] = {k: res.get(k) for k in ['ok', 'err', 'total_sec', 'mode', 'gl', 'card', 'stat', 'start']}
json.dump(R, open(os.path.join(QA, 'qa.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
try: os.remove(WAV)
except Exception: pass
print(json.dumps({k: R.get(k) for k in ['file', 'frames', 'audio', 'notes']}, ensure_ascii=False)[:1500])
