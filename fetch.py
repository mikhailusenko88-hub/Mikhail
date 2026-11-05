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
    norm = lambda x: re.sub(r'[^a-zа-яё0-9]', '', (x or '').lower())
    if not ch_url:
        cands = {}
        for q in [chan, 'Кот Барсик Кто перепутал время', 'Кот Барсик Куда пропал дождь', 'Кот Барсик мультик серия', 'Кот Барсик Кто оставил огромные следы']:
            r = run(['yt-dlp', '--flat-playlist', '-J', 'ytsearch20:' + q] + CL)
            try: ents = json.loads(r.stdout).get('entries') or []
            except Exception: ents = []
            for e in ents:
                nm = (e.get('channel') or e.get('uploader') or '').strip()
                if 'барсик' in (e.get('title') or '').lower() or norm(chan) in norm(nm): P('search:', nm, '|', e.get('channel_id'), '|', e.get('title'))
                if norm(chan) in norm(nm) and e.get('channel_id'): cands[e['channel_id']] = nm
            if cands: break
        if cands: ch_url = 'https://www.youtube.com/channel/' + list(cands)[0]
    if not ch_url:
        for h in ['@CartoonFriend3', '@cartoonfriend3', '@Cartoon_Friend3', '@Cartoon_Friend_3', '@CartoonFriend-3', '@cartoon-friend-3']:
            r = run(['yt-dlp', '--flat-playlist', '-J', '--playlist-end', '3', 'https://www.youtube.com/' + h + '/videos'] + CL)
            try: j = json.loads(r.stdout)
            except Exception: j = None
            if j and (j.get('entries') or []): P('нашёл по адресу', h, j.get('channel') or j.get('uploader')); ch_url = 'https://www.youtube.com/' + h; break
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
vid = url.split('v=')[-1]
mp4 = None
for cl in ['youtube:player_client=android_vr;player_skip=webpage,configs', 'youtube:player_client=tv_simply', 'youtube:player_client=mweb', 'youtube:player_client=web_embedded', 'youtube:player_client=ios,web_safari']:
    r = run(['yt-dlp', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4', '-o', 'out/ep.%(ext)s', '--extractor-args', cl, url], timeout=1800)
    mp4 = next((os.path.join('out', f) for f in os.listdir('out') if f.startswith('ep.') and f.endswith('.mp4')), None)
    if mp4: P('вышло через', cl); break
if not mp4:   # запасной путь: открытые зеркала YouTube
    import urllib.request
    def get(u, t=60):
        rq = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}); return urllib.request.urlopen(rq, timeout=t).read()
    for inst in ['https://inv.nadeko.net', 'https://invidious.nerdvpn.de', 'https://yewtu.be', 'https://invidious.f5.si', 'https://iv.datura.network', 'https://invidious.privacyredirect.com']:
        for itag in ['22', '18']:
            try:
                d = get(f'{inst}/latest_version?id={vid}&itag={itag}&local=true', 600)
                if len(d) > 2_000_000: open('out/ep.mp4', 'wb').write(d); mp4 = 'out/ep.mp4'; P('вышло через', inst, itag, len(d)); break
                P(inst, itag, 'мало', len(d))
            except Exception as e: P(inst, itag, 'нет', str(e)[:120])
        if mp4: break
    if not mp4:
        for api in ['https://pipedapi.kavin.rocks', 'https://pipedapi.adminforge.de', 'https://api.piped.private.coffee', 'https://pipedapi.r4fo.com', 'https://pipedapi.leptons.xyz']:
            try:
                j = json.loads(get(f'{api}/streams/{vid}'))
                vs = [v for v in j.get('videoStreams', []) if not v.get('videoOnly') and v.get('url')]
                vs.sort(key=lambda v: int(re.sub(r'\D', '', v.get('quality') or '0') or 0), reverse=True)
                if vs: d = get(vs[0]['url'], 900); open('out/ep.mp4', 'wb').write(d); mp4 = 'out/ep.mp4'; P('вышло через', api, vs[0].get('quality'), len(d)); break
                P(api, 'нет потоков')
            except Exception as e: P(api, 'нет', str(e)[:120])
if not mp4: P('не скачалось'); sys.exit(0)
P('скачано', mp4, os.path.getsize(mp4))
# листы кадров: кадр каждые 4 с, по 30 на лист, с подписью времени
os.makedirs('out/sheets', exist_ok=True)
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', "fps=1/4,scale=480:-1,drawtext=text='%{pts\\:hms}':x=6:y=6:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5", '-q:v', '4', 'out/sheets/f_%04d.jpg'])
run(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', 'scale=-2:540', '-c:v', 'libx264', '-crf', '30', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '96k', 'out/ep_540.mp4'])
P('готово')
