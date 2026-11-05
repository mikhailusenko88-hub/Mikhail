# Скачать серию мультика с YouTube для разбора (только чтение): найти канал, взять последний ролик, сделать 720p mp4 + листы кадров.
import json, os, re, subprocess, sys
os.makedirs('out', exist_ok=True)
log = open('out/log.txt', 'w')
def P(*a):
    s = ' '.join(str(x) for x in a); print(s); log.write(s + '\n'); log.flush()
def run(args, timeout=900):
    P('$', ' '.join(args)[:300])
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode: P('rc', r.returncode, r.stderr[-1500:])
    return r
req = [l.strip() for l in open('request.txt', encoding='utf-8') if l.strip() and not l.startswith('#')]
chan = next((l.split(':', 1)[1].strip() for l in req if l.lower().startswith('channel:')), '')
vid = next((l.split(':', 1)[1].strip() for l in req if l.lower().startswith('video:')), '')
pick = next((l.split(':', 1)[1].strip() for l in req if l.lower().startswith('title:')), '')
CL = ['--extractor-args', 'youtube:player_client=default,web_safari,ios,tv']
url = None
if vid: url = 'https://www.youtube.com/watch?v=' + vid
else:
    ch_url = chan if chan.startswith('http') or chan.startswith('@') else None
    if ch_url and ch_url.startswith('@'): ch_url = 'https://www.youtube.com/' + ch_url
    if not ch_url:
        r = run(['yt-dlp', '--flat-playlist', '-J', 'ytsearch20:' + chan] + CL)
        try:
            ents = json.loads(r.stdout).get('entries') or []
        except Exception: ents = []
        cands = {}
        for e in ents:
            nm = (e.get('channel') or e.get('uploader') or '').strip()
            P('search:', nm, '|', e.get('channel_id'), '|', e.get('title'))
            if nm.lower() == chan.lower() and e.get('channel_id'): cands[e['channel_id']] = nm
        if cands: ch_url = 'https://www.youtube.com/channel/' + list(cands)[0]
    if not ch_url: P('канал не найден'); sys.exit(0)
    P('канал', ch_url)
    r = run(['yt-dlp', '--flat-playlist', '-J', '--playlist-end', '15', ch_url + '/videos'] + CL)
    try: ents = json.loads(r.stdout).get('entries') or []
    except Exception: ents = []
    with open('out/list.txt', 'w') as f:
        for e in ents: f.write(f"{e.get('id')}\t{e.get('title')}\t{e.get('duration')}\n"); P('video:', e.get('id'), e.get('title'), e.get('duration'))
    ch = [e for e in ents if not pick or pick.lower() in (e.get('title') or '').lower()]
    if not ch: P('роликов нет'); sys.exit(0)
    url = 'https://www.youtube.com/watch?v=' + ch[0]['id']
P('качаю', url)
r = run(['yt-dlp', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4', '-o', 'out/ep.%(ext)s', '--write-info-json', url] + CL, timeout=1800)
mp4 = next((os.path.join('out', f) for f in os.listdir('out') if f.startswith('ep.') and f.endswith('.mp4')), None)
if not mp4: P('не скачалось'); sys.exit(0)
P('скачано', mp4, os.path.getsize(mp4))
# листы кадров: кадр каждые 4 с, по 30 на лист, с подписью времени
os.makedirs('out/sheets', exist_ok=True)
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', "fps=1/4,scale=480:-1,drawtext=text='%{pts\\:hms}':x=6:y=6:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5", '-q:v', '4', 'out/sheets/f_%04d.jpg'])
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', 'scale=-2:540', '-c:v', 'libx264', '-crf', '30', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '96k', 'out/ep_540.mp4'])
P('готово')
