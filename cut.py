# Ежедневная нарезка Shorts из серий «Кот Барсик».
# Берёт серию с Rutube (запас — YouTube), ищет самые живые моменты по звуку,
# режет вертикальные ролики 1080×1920 с подписями, кладёт mp4 в GitHub Release
# и обновляет ленту feed.json на странице в ветке mebel.
import json, os, re, subprocess, sys, math, datetime, wave, array, random, shutil

RUTUBE_CHANNEL = 'https://rutube.ru/channel/82826859/videos/'
YT_CHANNEL = 'https://www.youtube.com/@Cartoon_Friend3/videos'
RELEASE_TAG = 'shorts-kids'
REPO = os.environ.get('GITHUB_REPOSITORY', 'mikhailusenko88-hub/mikhail')
ASSET_BASE = f'https://github.com/{REPO}/releases/download/{RELEASE_TAG}/'
PAGE_CODE = os.environ.get('PAGE_CODE', 's9kbars')
CHANNEL_URL = 'https://rutube.ru/channel/82826859/'

os.makedirs('out', exist_ok=True)
log = open('out/log.txt', 'a', encoding='utf-8')
def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.write(s + '\n'); log.flush()
def run(args, timeout=1200, check=False):
    P('$', ' '.join(str(a) for a in args)[:260])
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    if r.returncode: P('rc', r.returncode, (r.stderr or '')[-1200:])
    if check and r.returncode: sys.exit('fail: ' + ' '.join(str(a) for a in args)[:100])
    return r

# ---------- настройки ----------
cfg = {'count': 2, 'length': 32, 'skip_start': 12, 'skip_end': 25, 'episode': ''}
if os.path.exists('config.txt'):
    for l in open('config.txt', encoding='utf-8'):
        l = l.strip()
        if l and not l.startswith('#') and ':' in l:
            k, v = l.split(':', 1); k = k.strip().lower(); v = v.split('#', 1)[0].strip()
            if k in ('count', 'length', 'skip_start', 'skip_end'):
                try: cfg[k] = int(v)
                except Exception: pass
            elif k == 'episode': cfg[k] = v
env_count = os.environ.get('COUNT', '').strip()
if env_count.isdigit(): cfg['count'] = int(env_count)
if os.environ.get('EPISODE', '').strip(): cfg['episode'] = os.environ['EPISODE'].strip()
P('config', cfg)

state = {'episodes': {}, 'made': []}
if os.path.exists('state.json'):
    try: state = json.load(open('state.json', encoding='utf-8'))
    except Exception: pass
state.setdefault('episodes', {}); state.setdefault('made', [])

# ---------- список серий ----------
def flat(url, extra=()):
    r = run(['yt-dlp', '--flat-playlist', '-J', '--playlist-end', '60', *extra, url], timeout=300)
    try: return json.loads(r.stdout).get('entries') or []
    except Exception: return []

def ep_num(title):
    m = re.search(r'(\d+)\s*сери', title or '', re.I)
    return int(m.group(1)) if m else None

episodes = []
for e in flat(RUTUBE_CHANNEL):
    t = e.get('title') or ''
    d = e.get('duration') or 0
    if not e.get('id'): continue
    if d and d < 70: continue                      # шортсы и трейлеры пропускаем
    if 'все серии' in t.lower() or 'сборник' in t.lower(): continue
    episodes.append({'id': e['id'], 'title': t, 'url': f"https://rutube.ru/video/{e['id']}/", 'src': 'rutube', 'dur': d, 'num': ep_num(t)})
P('rutube episodes:', len(episodes))
if not episodes:
    for e in flat(YT_CHANNEL, ['--extractor-args', 'youtube:player_client=default,web_safari,ios,tv']):
        t = e.get('title') or ''
        d = e.get('duration') or 0
        if not e.get('id') or (d and d < 70): continue
        episodes.append({'id': e['id'], 'title': t, 'url': 'https://www.youtube.com/watch?v=' + e['id'], 'src': 'youtube', 'dur': d, 'num': ep_num(t)})
    P('youtube episodes:', len(episodes))
if os.path.exists('episodes.txt'):
    for l in open('episodes.txt', encoding='utf-8'):
        l = l.strip()
        if not l or l.startswith('#'): continue
        parts = l.split('\t')
        if len(parts) >= 2 and not any(e['id'] == parts[0] for e in episodes):
            episodes.append({'id': parts[0], 'title': parts[1], 'url': f'https://rutube.ru/video/{parts[0]}/', 'src': 'rutube', 'dur': 0, 'num': ep_num(parts[1])})
    P('episodes.txt:', len(episodes))
if not episodes: P('серий не найдено'); sys.exit(0)

# ---------- выбор серии ----------
# Принцип: по кругу, начиная с самой новой; серия, из которой уже сделано ≥3 ролика, уходит в конец.
def used(ep): return state['episodes'].get(ep['id'], {}).get('segments', [])
cand = None
if cfg['episode']:
    cand = next((e for e in episodes if cfg['episode'] in e['id'] or cfg['episode'].lower() in e['title'].lower()), None)
if not cand:
    episodes.sort(key=lambda e: (-(e['num'] or 0)))
    # сначала серии, из которых ещё ничего не брали (самая новая первой), потом по минимуму взятого
    cand = min(episodes, key=lambda e: (len(used(e)), -(e['num'] or 0)))
P('серия:', cand['num'], cand['title'], cand['url'], 'уже взято:', len(used(cand)))

# ---------- скачать ----------
mp4 = 'out/ep.mp4'
if os.path.exists(mp4): os.remove(mp4)
if cand['src'] == 'rutube':
    run(['yt-dlp', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4', '-o', mp4, cand['url']], timeout=1500)
if not os.path.exists(mp4):
    for cl in ['youtube:player_client=android_vr;player_skip=webpage,configs', 'youtube:player_client=tv_simply', 'youtube:player_client=mweb', 'youtube:player_client=ios,web_safari']:
        yurl = cand['url'] if cand['src'] == 'youtube' else None
        if not yurl:
            # найти ту же серию на YouTube по номеру
            for e in flat(YT_CHANNEL, ['--extractor-args', 'youtube:player_client=default,web_safari,ios,tv']):
                if ep_num(e.get('title')) == cand['num'] and cand['num']: yurl = 'https://www.youtube.com/watch?v=' + e['id']; break
        if not yurl: break
        run(['yt-dlp', '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4', '-o', mp4, '--extractor-args', cl, yurl], timeout=1500)
        if os.path.exists(mp4): break
if not os.path.exists(mp4): P('не скачалось'); sys.exit(0)

# длительность
r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4])
DUR = float(r.stdout.strip() or 0)
P('длительность', DUR)

# ---------- анализ звука: где живее всего ----------
run(['ffmpeg', '-y', '-v', 'error', '-i', mp4, '-ac', '1', '-ar', '8000', '-vn', 'out/a.wav'], check=True)
w = wave.open('out/a.wav', 'rb'); n = w.getnframes(); raw = w.readframes(n); w.close()
samples = array.array('h'); samples.frombytes(raw)
SR = 8000
sec = int(len(samples) / SR)
rms = []
for i in range(sec):
    ch = samples[i*SR:(i+1)*SR]
    rms.append(math.sqrt(sum(x*x for x in ch) / max(1, len(ch))))
mx = max(rms) or 1
rms = [x / mx for x in rms]

L = cfg['length']
lo, hi = cfg['skip_start'], max(cfg['skip_start'] + L, int(DUR) - cfg['skip_end'])
def score(st):
    seg = rms[st:st+L]
    if len(seg) < L: return -1
    m = sum(seg) / L
    v = math.sqrt(sum((x-m)**2 for x in seg) / L)
    peak = max(seg)
    # шумные и переменчивые куски = смех, крики, действие
    return m * 1.0 + v * 1.5 + peak * 0.5
def overlaps(st, segs, gap=15):
    return any(not (st + L + gap <= a or st >= b + gap) for a, b in segs)
taken = [tuple(s) for s in used(cand)]
chosen = []
cands = sorted(range(lo, max(lo, hi - L) + 1), key=score, reverse=True)
for st in cands:
    if score(st) < 0: continue
    if overlaps(st, taken) or overlaps(st, chosen): continue
    # выравниваем начало на тихое место рядом (±3 с), чтобы не рубить слово
    best = st
    for d in range(-3, 4):
        s2 = st + d
        if lo <= s2 <= hi - L and rms[s2] < rms[best]: best = s2
    chosen.append((best, best + L))
    if len(chosen) >= cfg['count']: break
if not chosen: P('свободных моментов в серии больше нет'); state['episodes'].setdefault(cand['id'], {})['done'] = True; json.dump(state, open('state.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1); sys.exit(0)
chosen.sort()
P('моменты:', chosen)

# ---------- подписи ----------
def clean_title(t):
    t = re.sub(r'[\U0001F000-\U0001FFFF☀-➿⬀-⯿️]', '', t)
    t = re.sub(r'\s*[|–—-]\s*\d+\s*серия.*$', '', t, flags=re.I)
    t = re.sub(r'\.?\s*\d+\s*серия\s*$', '', t, flags=re.I)
    t = re.sub(r'^\s*Кот Барсик\s*[-–—:]\s*', '', t, flags=re.I)
    t = re.sub(r'\s*Кот Барсик\s*[-–—]\s*мультик для детей.*$', '', t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip(' .-—–|')
    return t or 'Кот Барсик'
hook = clean_title(cand['title'])
num = cand['num']
P('hook:', hook)

HOOKS = ['Что тут происходит?!', 'Ну и дела!', 'Вот это поворот!', 'Кто бы мог подумать!', 'Смотри, что было дальше!', 'Самый смешной момент!', 'Ты только посмотри!', 'Вот это да!']
TAGS = '#КотБарсик #МультикиДляДетей #Shorts #Мультфильмы #ДетскиеМультфильмы #МультикиПроЖивотных #ДобрыеМультики #МультикДляМалышей #КотенокБарсик'

today = datetime.date.today().isoformat()
made_today = [m for m in state['made'] if m.get('date') == today]
k0 = len([m for m in state['made'] if m.get('ep') == cand['id']])

font = next((f for f in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'] if os.path.exists(f)), None)
def esc(s): return s.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'").replace('%', '\\%')
def wrap(s, n=22):
    out, line = [], ''
    for wd in s.split():
        if len(line) + len(wd) + 1 > n and line: out.append(line); line = wd
        else: line = (line + ' ' + wd).strip()
    if line: out.append(line)
    return out[:3]

new_items = []
for i, (a, b) in enumerate(chosen):
    k = k0 + i + 1
    name = f'barsik_ep{num or 0:02d}_{k}_{today}.mp4'
    outp = os.path.join('out', name)
    top_lines = wrap(hook.upper(), 20)
    top = '\n'.join(top_lines)
    dur = b - a
    vf = ('[0:v]split=2[bg0][fg0];'
          '[bg0]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=luma_radius=28:luma_power=2,eq=brightness=-0.18:saturation=1.2[bg];'
          '[fg0]scale=1080:-2[fg];'
          '[bg][fg]overlay=0:(H-h)/2[v1];')
    draw = ''
    if font:
        open('out/bot.txt', 'w', encoding='utf-8').write('ПОЛНАЯ СЕРИЯ — НА КАНАЛЕ')
        open('out/badge.txt', 'w', encoding='utf-8').write('КОТ БАРСИК')
        parts = [f"[v1]drawtext=fontfile={font}:textfile=out/badge.txt:fontsize=44:fontcolor=white:box=1:boxcolor=0xE8452C@0.95:boxborderw=18:x=(w-tw)/2:y=250"]
        for li, ln in enumerate(top_lines):
            open(f'out/top{li}.txt', 'w', encoding='utf-8').write(ln)
            parts.append(f"drawtext=fontfile={font}:textfile=out/top{li}.txt:fontsize=72:fontcolor=white:borderw=5:bordercolor=black@0.85:x=(w-tw)/2:y={360 + li*88}")
        parts.append(f"drawtext=fontfile={font}:textfile=out/bot.txt:fontsize=46:fontcolor=0xFFE14D:borderw=4:bordercolor=black@0.85:x=(w-tw)/2:y=1440")
        parts.append(f"fade=t=in:st=0:d=0.4,fade=t=out:st={dur-0.5}:d=0.5[v]")
        draw = ','.join(parts)
    else:
        draw = f"[v1]fade=t=in:st=0:d=0.4,fade=t=out:st={dur-0.5}:d=0.5[v]"
    af = f"[0:a]afade=t=in:st=0:d=0.3,afade=t=out:st={dur-0.5}:d=0.5[a]"
    r = run(['ffmpeg', '-y', '-v', 'error', '-ss', str(a), '-t', str(dur), '-i', mp4,
             '-filter_complex', vf + draw + ';' + af, '-map', '[v]', '-map', '[a]',
             '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p', '-r', '30',
             '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', outp], timeout=1500)
    if not os.path.exists(outp): P('не собрался', name); continue
    # превью
    run(['ffmpeg', '-y', '-v', 'error', '-ss', '2', '-i', outp, '-frames:v', '1', '-vf', 'scale=270:-2', outp.replace('.mp4', '.jpg')])
    h2 = random.choice(HOOKS)
    title = f'{hook} 🐱 Кот Барсик | момент {k} #shorts'
    if len(title) > 100: title = f'{hook[:60]} 🐱 Кот Барсик #shorts'
    desc = (f'{h2} 😺 Отрывок из мультика «Кот Барсик»' + (f', {num} серия' if num else '') + '.\n\n'
            f'🎬 Полная серия: {cand["url"]}\n'
            f'📺 Все серии на канале: {CHANNEL_URL}\n\n'
            f'Котёнок Барсик, мышонок Пик и щенок Рон — добрые и смешные истории о дружбе для детей.\n'
            f'❤️ Подписывайтесь, чтобы не пропустить новые серии!\n\n{TAGS}')
    item = {'date': today, 'file': name, 'url': ASSET_BASE + name, 'thumb': ASSET_BASE + name.replace('.mp4', '.jpg'),
            'title': title, 'desc': desc, 'tags': TAGS, 'ep': cand['id'], 'ep_num': num, 'ep_title': cand['title'], 'ep_url': cand['url'],
            'start': a, 'end': b, 'size': os.path.getsize(outp)}
    new_items.append(item)
    state['made'].append({'date': today, 'ep': cand['id'], 'file': name, 'seg': [a, b]})
    state['episodes'].setdefault(cand['id'], {'title': cand['title'], 'segments': []})['segments'].append([a, b])
    P('готово', name, os.path.getsize(outp))

if not new_items: P('ничего не сделано'); sys.exit(0)

# ---------- выложить в Release ----------
env = dict(os.environ); env['GH_TOKEN'] = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
r = subprocess.run(['gh', 'release', 'view', RELEASE_TAG, '-R', REPO], capture_output=True, text=True, env=env)
if r.returncode:
    run(['gh', 'release', 'create', RELEASE_TAG, '-R', REPO, '-t', 'Shorts Кот Барсик', '-n', 'Готовые вертикальные ролики для выкладки', '--latest=false'])
for it in new_items:
    f = os.path.join('out', it['file'])
    subprocess.run(['gh', 'release', 'upload', RELEASE_TAG, f, f.replace('.mp4', '.jpg'), '-R', REPO, '--clobber'], env=env, check=True)
    P('загружено', it['file'])

# ---------- лента на странице (ветка mebel) ----------
feed_dir = os.path.join('mebel', PAGE_CODE)
os.makedirs(feed_dir, exist_ok=True)
feed_p = os.path.join(feed_dir, 'feed.json')
feed = {'items': []}
if os.path.exists(feed_p):
    try: feed = json.load(open(feed_p, encoding='utf-8'))
    except Exception: pass
feed['items'] = new_items + feed.get('items', [])
feed['items'] = feed['items'][:90]
feed['updated'] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%d.%m.%Y %H:%M')
feed['channel'] = CHANNEL_URL
json.dump(feed, open(feed_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# старые ролики в Release (старше 60 дней) удаляем, чтобы не копить
r = subprocess.run(['gh', 'release', 'view', RELEASE_TAG, '-R', REPO, '--json', 'assets', '-q', '.assets[].name'], capture_output=True, text=True, env=env)
keep = {it['file'] for it in feed['items']} | {it['file'].replace('.mp4', '.jpg') for it in feed['items']}
for nm in (r.stdout or '').split():
    if nm not in keep:
        subprocess.run(['gh', 'release', 'delete-asset', RELEASE_TAG, nm, '-R', REPO, '-y'], env=env)
        P('удалён старый', nm)

json.dump(state, open('state.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
P('итого новых:', len(new_items))
