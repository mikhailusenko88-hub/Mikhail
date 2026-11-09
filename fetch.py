# Разбор последней серии мультика (только чтение): список роликов YouTube-канала, последняя серия,
# видео с YouTube или ту же серию с Rutube, кадры, расшифровка речи, проверка звука.
import json, os, re, subprocess, sys, urllib.request
os.makedirs('out', exist_ok=True)
log = open('out/log.txt', 'w')
def P(*a):
    s = ' '.join(str(x) for x in a); print(s); log.write(s + '\n'); log.flush()
def run(args, timeout=900):
    P('$', ' '.join(args)[:300])
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode: P('rc', r.returncode, r.stderr[-1500:])
    return r
def get(u, t=60):
    rq = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}); return urllib.request.urlopen(rq, timeout=t).read()
req = [l.strip() for l in open('request.txt', encoding='utf-8') if l.strip() and not l.startswith('#')]
opt = lambda k: next((l.split(':', 1)[1].strip() for l in req if l.lower().startswith(k + ':')), '')
chan, vid, rt_chan, pick = opt('channel') or '@Cartoon_Friend3', opt('video'), opt('rutube') or '82826859', opt('title')
CL = ['--extractor-args', 'youtube:player_client=default,web_safari,ios,tv']
ep_num = lambda t: (lambda m: int(m.group(1)) if m else None)(re.search(r'сери[яи]\s*(\d+)', (t or '').lower()))

# 1) список роликов YouTube
ch_url = 'https://www.youtube.com/' + chan if chan.startswith('@') else chan
r = run(['yt-dlp', '--flat-playlist', '-J', '--playlist-end', '20', ch_url + '/videos'] + CL)
try: pj = json.loads(r.stdout)
except Exception: pj = {}
ents = pj.get('entries') or []
cid = pj.get('channel_id') or pj.get('id')
P('канал', pj.get('channel') or pj.get('title'), cid)
with open('out/list.txt', 'w') as f:
    for e in ents:
        f.write(f"{e.get('id')}\t{e.get('title')}\t{e.get('duration')}\t{e.get('view_count')}\n")
        P('video:', e.get('id'), e.get('title'), e.get('duration'), e.get('view_count'))
if cid and cid.startswith('UC'):
    try: open('out/rss.xml', 'wb').write(get('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid)); P('rss ok')
    except Exception as e: P('rss нет', e)
if not vid:
    ch = [e for e in ents if not pick or pick.lower() in (e.get('title') or '').lower()]
    if not ch: P('роликов нет'); sys.exit(0)
    vid, title = ch[0]['id'], ch[0].get('title')
else: title = next((e.get('title') for e in ents if e.get('id') == vid), '')
num = ep_num(title)
P('последняя серия:', vid, title, 'номер', num)
json.dump({'id': vid, 'title': title, 'num': num}, open('out/pick.json', 'w'), ensure_ascii=False)
for q in ['maxresdefault', 'hqdefault']:
    try: open('out/thumb.jpg', 'wb').write(get(f'https://i.ytimg.com/vi/{vid}/{q}.jpg')); P('обложка', q); break
    except Exception as e: P('обложка нет', q, e)

# 2) видео: сначала YouTube, потом та же серия на Rutube
mp4 = 'out/ep.mp4'
FMT = 'bv*[height<=1080]+ba/b[height<=1080]/b'
for cl in ['youtube:player_client=android_vr;player_skip=webpage,configs', 'youtube:player_client=tv_simply', 'youtube:player_client=mweb']:
    run(['yt-dlp', '-f', FMT, '--merge-output-format', 'mp4', '-o', mp4, '--extractor-args', cl, 'https://www.youtube.com/watch?v=' + vid], timeout=1500)
    if os.path.exists(mp4): P('скачано с youtube через', cl); break
if not os.path.exists(mp4):
    rts = []
    for page in range(1, 4):
        try:
            j = json.loads(get(f'https://rutube.ru/api/video/person/{rt_chan}/?page={page}'))
            rts += j.get('results') or []
            if not j.get('has_next'): break
        except Exception as e: P('rutube api нет', e); break
    with open('out/rutube_list.txt', 'w') as f:
        for v in rts: f.write(f"{v.get('id')}\t{v.get('title')}\t{v.get('duration')}\t{v.get('hits')}\t{v.get('created_ts')}\n")
    P('rutube роликов', len(rts))
    cand = [v for v in rts if num and ep_num(v.get('title')) == num and (v.get('duration') or 0) > 120]
    if not cand: cand = [v for v in rts if (v.get('title') or '').strip().lower() == (title or '').strip().lower()]
    if cand:
        v = cand[0]; P('на rutube:', v.get('title'), v.get('video_url'), v.get('duration'))
        json.dump({'rutube_title': v.get('title'), 'rutube_url': v.get('video_url'), 'rutube_hits': v.get('hits')}, open('out/rutube_pick.json', 'w'), ensure_ascii=False)
        run(['yt-dlp', '-f', FMT, '--merge-output-format', 'mp4', '-o', mp4, v.get('video_url')], timeout=1500)
        if os.path.exists(mp4): P('скачано с rutube')
    else: P('на rutube этой серии нет')
if not os.path.exists(mp4): P('не скачалось'); sys.exit(0)
P('скачано', os.path.getsize(mp4))
open('out/probe.json', 'w').write(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,width,height,r_frame_rate,sample_rate,channels', '-of', 'json', mp4]).stdout)

# 3) кадры: листы (кадр раз в 2 с, 5×4 на лист) и крупные кадры раз в 10 с
os.makedirs('out/sheets', exist_ok=True); os.makedirs('out/big', exist_ok=True)
lab = "drawtext=text='%{pts\\:hms}':x=6:y=6:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6"
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', f"fps=1/2,scale=384:-2,{lab},tile=5x4", '-q:v', '4', 'out/sheets/s_%03d.jpg'], timeout=1500)
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', f"fps=1/10,scale=1280:-2,{lab}", '-q:v', '3', 'out/big/b_%03d.jpg'], timeout=1500)
# смены сцен
r = run(['ffmpeg', '-v', 'info', '-i', mp4, '-vf', "select='gt(scene,0.35)',showinfo", '-an', '-f', 'null', '-'], timeout=1500)
open('out/scenes.txt', 'w').write('\n'.join(re.findall(r'pts_time:([\d.]+)', r.stderr)))

# 4) звук: громкость, тишина, клиппинг, расшифровка речи
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vn', '-ac', '1', '-ar', '16000', 'out/a16.wav'])
r = run(['ffmpeg', '-v', 'info', '-i', mp4, '-vn', '-af', 'ebur128=peak=true,silencedetect=n=-45dB:d=2.5,volumedetect', '-f', 'null', '-'], timeout=900)
open('out/audio_stats.txt', 'w').write('\n'.join(l for l in r.stderr.splitlines() if any(k in l for k in ['silence_', 'I:', 'LRA:', 'Peak:', 'max_volume', 'mean_volume', 'histogram'])))
try:
    from faster_whisper import WhisperModel
    m = WhisperModel('medium', device='cpu', compute_type='int8')
    segs, info = m.transcribe('out/a16.wav', language='ru', beam_size=5, vad_filter=False)
    with open('out/transcript.txt', 'w') as f:
        for s in segs:
            mm, ss = divmod(s.start, 60); f.write(f"{int(mm):02d}:{ss:05.2f}  {s.text.strip()}\n")
    P('расшифровка готова')
except Exception as e: P('расшифровка нет', e)
os.remove('out/a16.wav')
# лёгкая копия видео
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', 'scale=-2:540', '-c:v', 'libx264', '-crf', '30', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '96k', 'out/ep_540.mp4'], timeout=1500)
os.remove(mp4)
P('готово')
