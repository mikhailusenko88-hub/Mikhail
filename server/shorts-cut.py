#!/usr/bin/env python3
# Нарезка Shorts «Кот Барсик» на сервере: серии с YouTube (1080p), запас — Rutube.
# Результат: /var/www/mebel/s9kbars-v/<файл>.mp4 + .jpg + feed.json; страница — /var/www/mebel/s9kbars/
import json, os, re, subprocess, sys, math, datetime, wave, array, random, shutil, time
os.environ['PATH'] = '/usr/local/bin:/usr/bin:/bin:' + os.environ.get('PATH', '')

YT_CHANNEL = 'https://www.youtube.com/@Cartoon_Friend3/videos'
YT_CHANNEL_URL = 'https://www.youtube.com/@Cartoon_Friend3'
RUTUBE_CHANNEL = 'https://rutube.ru/channel/82826859/videos/'
CHANNEL_URL = 'https://rutube.ru/channel/82826859/'
OUT = '/var/www/mebel/s9kbars-v'          # готовые ролики (раздаются сервером)
WORK = '/var/www/shorts'                   # состояние, настройки, временные файлы
TMP = os.path.join(WORK, 'tmp')
KEEP_DAYS = 14
for d in (OUT, WORK, TMP): os.makedirs(d, exist_ok=True)
# защита от двойного запуска
import fcntl
_lock = open(os.path.join(WORK, '.lock'), 'w')
try: fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: print('уже идёт другая нарезка — выхожу'); sys.exit(0)
open(os.path.join(OUT, '.keep'), 'a').close()
log = open(os.path.join(WORK, 'log.txt'), 'a', encoding='utf-8')
def P(*a):
    s = datetime.datetime.now().strftime('%d.%m %H:%M ') + ' '.join(str(x) for x in a); print(s, flush=True); log.write(s + '\n'); log.flush()
def run(args, timeout=1800):
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    if r.returncode: P('rc', r.returncode, ' '.join(str(a) for a in args)[:80], '|', (r.stderr or '')[-300:].replace('\n', ' '))
    return r

cfg = {'count': 2, 'length': 32, 'skip_start': 12, 'skip_end': 25, 'episode': '', 'per_episode': 2}
cfg_p = os.path.join(WORK, 'config.txt')
if not os.path.exists(cfg_p):
    open(cfg_p, 'w', encoding='utf-8').write('# Настройки нарезки Shorts\ncount: 2          # роликов в день\nper_episode: 2    # всего роликов с одной серии\nlength: 32        # длина ролика, сек\nskip_start: 12    # пропустить начало серии, сек\nskip_end: 25      # пропустить конец серии, сек\nepisode:          # пусто = по очереди; или номер/часть названия\n')
for l in open(cfg_p, encoding='utf-8'):
    l = l.strip()
    if l and not l.startswith('#') and ':' in l:
        k, v = l.split(':', 1); k = k.strip().lower(); v = v.split('#', 1)[0].strip()
        if k in ('count', 'length', 'skip_start', 'skip_end', 'per_episode'):
            try: cfg[k] = int(v)
            except Exception: pass
        elif k == 'episode': cfg[k] = v
if len(sys.argv) > 1 and sys.argv[1].isdigit(): cfg['count'] = int(sys.argv[1])
if len(sys.argv) > 2: cfg['episode'] = sys.argv[2]
P('старт', cfg)

state_p = os.path.join(WORK, 'state.json')
state = {'episodes': {}, 'made': []}
if os.path.exists(state_p):
    try: state = json.load(open(state_p, encoding='utf-8'))
    except Exception: pass
state.setdefault('episodes', {}); state.setdefault('made', [])
def save_state(): json.dump(state, open(state_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------- старые ролики: удалить старше KEEP_DAYS ----------
feed_p = os.path.join(OUT, 'feed.json')
feed = {'items': []}
if os.path.exists(feed_p):
    try: feed = json.load(open(feed_p, encoding='utf-8'))
    except Exception: pass
cut_date = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
feed['items'] = [it for it in feed.get('items', []) if it.get('date', '') >= cut_date]
keep = {it['file'] for it in feed['items']} | {it['file'][:-4] + '.jpg' for it in feed['items']}
for n in os.listdir(OUT):
    if n.endswith(('.mp4', '.jpg')) and n not in keep:
        os.remove(os.path.join(OUT, n)); P('удалён старый', n)
for n in os.listdir(TMP): os.remove(os.path.join(TMP, n))

# ---------- список серий ----------
def flat(url, extra=()):
    r = run(['yt-dlp', '--js-runtimes', 'deno', '--flat-playlist', '-J', '--playlist-end', '80', *extra, url], timeout=300)
    try: return json.loads(r.stdout).get('entries') or []
    except Exception: return []
def ep_num(title):
    t = title or ''
    m = re.search(r'(\d+)\s*[-]?\s*сери', t, re.I) or re.search(r'сери[яи]\s*[№#:]?\s*(\d+)', t, re.I)
    return int(m.group(1)) if m else None
STOP = set('кот барсик мультик мультфильм для детей серия серии новая часть и в на с о the a'.split())
def toks(t):
    t = re.sub(r'[\U0001F000-\U0001FFFF☀-➿⬀-⯿️]', ' ', (t or '').lower())
    t = re.sub(r'[^a-zа-яё0-9 ]+', ' ', t)
    return {w for w in t.split() if w not in STOP and len(w) > 2}
def same(t1, t2):
    a, b = toks(t1), toks(t2)
    if not a or not b: return False
    j = len(a & b) / len(a | b)
    p1 = re.search(r'часть\s*(\d)', (t1 or '').lower()); p2 = re.search(r'часть\s*(\d)', (t2 or '').lower())
    if p1 and p2 and p1.group(1) != p2.group(1): return False
    if (p1 and not p2) or (p2 and not p1):
        if (p1 or p2).group(1) != '1': return False
    return j >= 0.3

episodes = []
for e in flat(YT_CHANNEL):
    t = e.get('title') or ''; d = e.get('duration') or 0
    if not e.get('id') or (d and d < 70): continue
    if 'все серии' in t.lower() or 'сборник' in t.lower(): continue
    episodes.append({'id': e['id'], 'title': t, 'url': 'https://www.youtube.com/watch?v=' + e['id'], 'src': 'youtube', 'num': ep_num(t), 'rutube': None, 'rtitle': None})
P('youtube серий:', len(episodes))
rt = []
for e in flat(RUTUBE_CHANNEL):
    t = e.get('title') or ''; d = e.get('duration') or 0
    if not e.get('id') or (d and d < 70): continue
    if 'все серии' in t.lower() or 'сборник' in t.lower(): continue
    rt.append({'id': e['id'], 'title': t, 'url': f"https://rutube.ru/video/{e['id']}/", 'src': 'rutube', 'num': ep_num(t), 'rutube': f"https://rutube.ru/video/{e['id']}/", 'rtitle': t})
P('rutube серий:', len(rt))
for r_ in rt:
    m = next((e for e in episodes if same(e['title'], r_['title'])), None)
    if m: m['rutube'] = r_['url']; m['rtitle'] = r_['title']; m['rnum'] = r_['num']
    else: episodes.append(r_)
if not episodes: P('серий нет'); sys.exit(0)

def key(ep): return ep['id']
def used(ep): return state['episodes'].get(key(ep), {}).get('segments', [])
order = []
if cfg['episode']:
    order = [e for e in episodes if cfg['episode'] in e['id'] or cfg['episode'].lower() in e['title'].lower() or (cfg['episode'].isdigit() and e['num'] == int(cfg['episode']))]
if not order:
    order = sorted(episodes, key=lambda e: (len(used(e)) >= cfg['per_episode'], len(used(e)), -(e['num'] or 0)))

# ---------- скачать ----------
mp4 = os.path.join(TMP, 'ep.mp4')
cand = None
order = order[:5] + [e for e in order[5:] if e.get('rutube')][:4]
for ep in order:
    if os.path.exists(mp4): os.remove(mp4)
    P('серия:', ep['num'], ep['title'][:70])
    if ep['src'] == 'youtube':
        run(['nice', '-n', '10', 'yt-dlp', '--js-runtimes', 'deno', '-f', 'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b', '--merge-output-format', 'mp4', '-o', mp4, '--no-playlist', ep['url']], timeout=1800)
    if not os.path.exists(mp4) and ep.get('rutube'):
        run(['yt-dlp', '-f', 'bv*[height<=1080]+ba/b', '--merge-output-format', 'mp4', '-o', mp4, ep['rutube']], timeout=1800)
    if os.path.exists(mp4) and os.path.getsize(mp4) > 1_000_000: cand = ep; break
    P('не скачалась, следующая')
if not cand: P('ничего не скачалось'); sys.exit(0)
r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4])
DUR = float(r.stdout.strip() or 0)
P('скачано', round(os.path.getsize(mp4) / 1e6, 1), 'МБ', round(DUR), 'сек')

# ---------- анализ звука ----------
wav = os.path.join(TMP, 'a.wav')
run(['ffmpeg', '-y', '-v', 'error', '-i', mp4, '-ac', '1', '-ar', '8000', '-vn', wav])
w = wave.open(wav, 'rb'); raw = w.readframes(w.getnframes()); w.close()
samples = array.array('h'); samples.frombytes(raw)
SR = 8000; sec = int(len(samples) / SR)
rms = []
for i in range(sec):
    ch = samples[i*SR:(i+1)*SR]
    rms.append(math.sqrt(sum(x*x for x in ch) / max(1, len(ch))))
mx = max(rms) or 1; rms = [x / mx for x in rms]
L = cfg['length']
lo, hi = cfg['skip_start'], max(cfg['skip_start'] + L, int(DUR) - cfg['skip_end'])
def score(st):
    seg = rms[st:st+L]
    if len(seg) < L: return -1
    m = sum(seg) / L; v = math.sqrt(sum((x-m)**2 for x in seg) / L)
    return m + v * 1.5 + max(seg) * 0.5
def overlaps(st, segs, gap=15): return any(not (st + L + gap <= a or st >= b + gap) for a, b in segs)
taken = [tuple(s) for s in used(cand)]
left = max(0, cfg['per_episode'] - len(taken))
want = min(cfg['count'], left) if left else cfg['count']
chosen = []
for st in sorted(range(lo, max(lo, hi - L) + 1), key=score, reverse=True):
    if score(st) < 0 or overlaps(st, taken) or overlaps(st, chosen): continue
    best = st
    for d in range(-3, 4):
        s2 = st + d
        if lo <= s2 <= hi - L and rms[s2] < rms[best]: best = s2
    chosen.append((best, best + L))
    if len(chosen) >= want: break
if not chosen: P('моментов нет'); sys.exit(0)
chosen.sort(); P('моменты:', chosen)

# ---------- подписи ----------
def clean_title(t):
    t = re.sub(r'[\U0001F000-\U0001FFFF☀-➿⬀-⯿️‍]', '', t or '')
    if '|' in t:
        chunks = [c.strip() for c in t.split('|') if c.strip()]
        chunks = [c for c in chunks if not re.search(r'кот барсик|мультик|сери[яи]|часть', c, re.I)] or chunks[:1]
        t = chunks[0]
    t = re.sub(r'\s*[|–—-]\s*\d+\s*серия.*$', '', t, flags=re.I)
    t = re.sub(r'\.?\s*\d+\s*серия\s*$', '', t, flags=re.I)
    t = re.sub(r'^\s*Кот Барсик\s*[-–—:]\s*', '', t, flags=re.I)
    t = re.sub(r'\s*Кот Барсик\s*[-–—]\s*мультик для детей.*$', '', t, flags=re.I)
    t = re.sub(r'\s*\(?часть\s*\d[-я ]*\)?', '', t, flags=re.I)
    t = re.sub(r'\s+', ' ', t).strip(' .-—–|,')
    return t or 'Кот Барсик'
hook = clean_title(cand.get('rtitle') or cand['title'])
num = cand.get('rnum') or cand['num']
HOOKS = ['Что тут происходит?!', 'Ну и дела!', 'Вот это поворот!', 'Кто бы мог подумать!', 'Смотри, что было дальше!', 'Самый смешной момент!', 'Ты только посмотри!', 'Вот это да!']
TAGS = '#КотБарсик #МультикиДляДетей #Shorts #Мультфильмы #ДетскиеМультфильмы #МультикиПроЖивотных #ДобрыеМультики #МультикДляМалышей #КотенокБарсик'
TAGS_YT = '#КотБарсик #МультикиДляДетей #Shorts #Мультфильмы #ДетскиеМультфильмы #МультикДляМалышей #cartoon #kidscartoon #shorts'
today = datetime.date.today().isoformat()
k0 = len([m for m in state['made'] if m.get('ep') == key(cand)])
font = next((f for f in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'] if os.path.exists(f)), None)
def wrap(s, n=20):
    out, line = [], ''
    for wd in s.split():
        if len(line) + len(wd) + 1 > n and line: out.append(line); line = wd
        else: line = (line + ' ' + wd).strip()
    if line: out.append(line)
    return out[:3]

new_items = []
for i, (a, b) in enumerate(chosen):
    k = k0 + i + 1
    name = f'barsik_ep{num or 0:02d}_{k}_{today}_{datetime.datetime.now().strftime("%H%M")}.mp4'
    outp = os.path.join(OUT, name); dur = b - a
    vf = ('[0:v]split=2[bg0][fg0];'
          '[bg0]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=luma_radius=28:luma_power=2,eq=brightness=-0.18:saturation=1.2[bg];'
          '[fg0]scale=1080:-2[fg];[bg][fg]overlay=0:(H-h)/2[v1];')
    parts = []
    if font:
        tf = lambda nm, txt: (open(os.path.join(TMP, nm), 'w', encoding='utf-8').write(txt), os.path.join(TMP, nm))[1]
        parts.append(f"[v1]drawtext=fontfile={font}:textfile={tf('badge.txt', 'КОТ БАРСИК')}:fontsize=44:fontcolor=white:box=1:boxcolor=0xE8452C@0.95:boxborderw=18:x=(w-tw)/2:y=250")
        for li, ln in enumerate(wrap(hook.upper())):
            parts.append(f"drawtext=fontfile={font}:textfile={tf(f'top{li}.txt', ln)}:fontsize=72:fontcolor=white:borderw=5:bordercolor=black@0.85:x=(w-tw)/2:y={360 + li*88}")
        parts.append(f"drawtext=fontfile={font}:textfile={tf('bot.txt', 'ПОЛНАЯ СЕРИЯ — НА КАНАЛЕ')}:fontsize=46:fontcolor=0xFFE14D:borderw=4:bordercolor=black@0.85:x=(w-tw)/2:y=1440")
        parts.append(f"fade=t=in:st=0:d=0.4,fade=t=out:st={dur-0.5}:d=0.5[v]")
    else:
        parts.append(f"[v1]fade=t=in:st=0:d=0.4,fade=t=out:st={dur-0.5}:d=0.5[v]")
    af = f"[0:a]afade=t=in:st=0:d=0.3,afade=t=out:st={dur-0.5}:d=0.5[a]"
    run(['nice', '-n', '10', 'ffmpeg', '-y', '-v', 'error', '-ss', a, '-t', dur, '-i', mp4, '-filter_complex', vf + ','.join(parts) + ';' + af,
         '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-threads', '2', '-pix_fmt', 'yuv420p', '-r', '30',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', outp], timeout=2400)
    if not os.path.exists(outp): P('не собрался', name); continue
    run(['ffmpeg', '-y', '-v', 'error', '-ss', '2', '-i', outp, '-frames:v', '1', '-vf', 'scale=270:-2', outp[:-4] + '.jpg'])
    h2 = random.choice(HOOKS)
    title = f'{hook} 🐱 Кот Барсик' + (f' | {num} серия' if num else '') + ' #shorts'
    if len(title) > 100: title = f'{hook[:55]} 🐱 Кот Барсик' + (f' | {num} серия' if num else '') + ' #shorts'
    head = f'{h2} 😺 Отрывок из мультика «Кот Барсик»' + (f', {num} серия' if num else '') + '.\n\n'
    body = 'Котёнок Барсик, мышонок Пик и щенок Рон — добрые и смешные истории о дружбе для детей.\n❤️ Подписывайтесь, чтобы не пропустить новые серии!\n\n'
    rt_ep = cand.get('rutube'); yt_ep = cand['url'] if cand['src'] == 'youtube' else None
    desc_rt = head + (f'🎬 Полная серия: {rt_ep}\n' if rt_ep else '') + f'📺 Все серии на канале: {CHANNEL_URL}\n\n' + body + TAGS
    desc_yt = head + (f'🎬 Полная серия: {yt_ep}\n' if yt_ep else '') + f'📺 Все серии на канале: {YT_CHANNEL_URL}\n\n' + body + TAGS_YT
    item = {'date': today, 'file': name, 'url': '../s9kbars-v/' + name, 'thumb': '../s9kbars-v/' + name[:-4] + '.jpg', 'local': True,
            'title': title, 'desc': desc_rt, 'desc_rt': desc_rt, 'desc_yt': desc_yt, 'tags': TAGS,
            'ep': key(cand), 'ep_num': num, 'ep_title': cand['title'], 'ep_url': rt_ep or cand['url'], 'yt_url': yt_ep,
            'start': a, 'end': b, 'size': os.path.getsize(outp)}
    new_items.append(item)
    state['made'].append({'date': today, 'ep': key(cand), 'file': name, 'seg': [a, b]})
    state['episodes'].setdefault(key(cand), {'title': cand['title'], 'segments': []})['segments'].append([a, b])
    P('готово', name, round(os.path.getsize(outp) / 1e6, 1), 'МБ')

feed['items'] = new_items + feed['items']
feed['updated'] = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
feed['channel'] = CHANNEL_URL
json.dump(feed, open(feed_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
save_state()
for n in os.listdir(TMP): os.remove(os.path.join(TMP, n))
# жёсткий лимит 1 ГБ на папку роликов
total = sum(os.path.getsize(os.path.join(OUT, n)) for n in os.listdir(OUT))
if total > 1e9:
    for it in sorted(feed['items'], key=lambda x: x['date'])[:10]:
        for n in (it['file'], it['file'][:-4] + '.jpg'):
            p = os.path.join(OUT, n)
            if os.path.exists(p): os.remove(p)
    feed['items'] = feed['items'][:-10]; json.dump(feed, open(feed_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
P('итого новых:', len(new_items), '| в папке', round(total / 1e6), 'МБ')
