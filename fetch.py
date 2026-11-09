# Разбор серий мультика (только чтение): найти серии по номеру на YouTube/Rutube, скачать, кадры, расшифровка речи, звук.
# Результат кладётся в res/epNN/ и коммитится в ветку yt-video-res (артефакты из облака Claude не скачать).
import json, os, re, subprocess, sys, urllib.request
os.makedirs('res', exist_ok=True)
log = open('res/log.txt', 'a')
def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.write(s + '\n'); log.flush()
def run(args, timeout=1800):
    P('$', ' '.join(args)[:240])
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode: P('rc', r.returncode, r.stderr[-800:])
    return r
def get(u, t=60):
    return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=t).read()
req = [l.strip() for l in open('request.txt', encoding='utf-8') if l.strip() and not l.startswith('#')]
opt = lambda k: next((l.split(':', 1)[1].strip() for l in req if l.lower().startswith(k + ':')), '')
chan, rt_chan = opt('channel') or '@Cartoon_Friend3', opt('rutube') or '82826859'
want = [int(x) for x in re.findall(r'\d+', opt('episodes'))]
ep_num = lambda t: (lambda m: int(m.group(1)) if m else None)(re.search(r'сери[яи]\s*(\d+)', (t or '').lower()))
r = run(['yt-dlp', '--flat-playlist', '-J', '--playlist-end', '40', 'https://www.youtube.com/' + chan + '/videos'])
try: ents = json.loads(r.stdout).get('entries') or []
except Exception: ents = []
yt = {}
for e in ents:
    n = ep_num(e.get('title')); P('yt:', e.get('id'), n, e.get('title'), e.get('duration'), e.get('view_count'))
    if n and n not in yt: yt[n] = e
rts = []
for page in range(1, 6):
    try:
        j = json.loads(get(f'https://rutube.ru/api/video/person/{rt_chan}/?page={page}')); rts += j.get('results') or []
        if not j.get('has_next'): break
    except Exception as ex: P('rutube api', ex); break
for v in rts: P('rt:', v.get('id'), ep_num(v.get('title')), v.get('title'), v.get('duration'))
for n in want:
    d = f'res/ep{n:02d}'; os.makedirs(d + '/sheets', exist_ok=True); os.makedirs(d + '/big', exist_ok=True)
    mp4 = f'/tmp/ep{n}.mp4'; info = {'num': n}
    if n in yt:
        info.update(yt_id=yt[n]['id'], title=yt[n].get('title'), views=yt[n].get('view_count'))
        for cl in ['youtube:player_client=android_vr;player_skip=webpage,configs', 'youtube:player_client=tv_simply']:
            run(['yt-dlp', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4', '-o', mp4, '--extractor-args', cl, 'https://www.youtube.com/watch?v=' + yt[n]['id']], timeout=1200)
            if os.path.exists(mp4): info['src'] = 'youtube'; break
        try: open(d + '/thumb.jpg', 'wb').write(get(f'https://i.ytimg.com/vi/{yt[n]["id"]}/hqdefault.jpg'))
        except Exception: pass
    if not os.path.exists(mp4):
        c = [v for v in rts if ep_num(v.get('title')) == n and (v.get('duration') or 0) > 120]
        if c:
            info.update(rt_url=c[0].get('video_url'), rt_title=c[0].get('title'))
            run(['yt-dlp', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4', '-o', mp4, c[0].get('video_url')], timeout=1800)
            if os.path.exists(mp4): info['src'] = 'rutube'
    json.dump(info, open(d + '/info.json', 'w'), ensure_ascii=False, indent=1)
    if not os.path.exists(mp4): P('серия', n, 'не скачалась'); continue
    P('серия', n, 'скачана', info.get('src'), os.path.getsize(mp4))
    lab = "drawtext=text='%{pts\\:hms}':x=6:y=6:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6"
    run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', f"fps=1/3,scale=480:-2,{lab},tile=4x3", '-q:v', '5', d + '/sheets/s_%03d.jpg'])
    run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', f"fps=1/10,scale=960:-2,{lab}", '-q:v', '5', d + '/big/b_%03d.jpg'])
    run(['ffmpeg', '-v', 'error', '-i', mp4, '-vn', '-ac', '1', '-ar', '16000', '/tmp/a16.wav'])
    rr = run(['ffmpeg', '-v', 'info', '-i', mp4, '-vn', '-af', 'ebur128=peak=true,silencedetect=n=-45dB:d=2.5', '-f', 'null', '-'])
    open(d + '/audio_stats.txt', 'w').write('\n'.join(l for l in rr.stderr.splitlines() if any(k in l for k in ['silence_', ' I:', 'LRA:', 'Peak:'])))
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel('small', device='cpu', compute_type='int8')
        segs, _ = m.transcribe('/tmp/a16.wav', language='ru', beam_size=3, vad_filter=False)
        with open(d + '/transcript.txt', 'w') as f:
            for s in segs: mm, ss = divmod(s.start, 60); f.write(f"{int(mm):02d}:{ss:05.2f}  {s.text.strip()}\n")
        P('расшифровка', n, 'готова')
    except Exception as ex: P('расшифровка нет', ex)
    os.remove(mp4)
P('готово')
