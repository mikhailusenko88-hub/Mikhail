# Собирает serii.json для вкладки «Новые серии» страницы s9kbars из папок serii/<N>/ (scenario.txt, meta.json, cover.jpg).
# Запуск из корня ветки mebel:  python3 s9kbars/serii/_build.py
import json, os, glob, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
YT = 'https://www.youtube.com/@Cartoon_Friend3?sub_confirmation=1'
RT = 'https://rutube.ru/channel/82826859/'
TAGS = '#КотБарсик #Мультики #МультикиДляДетей #Мультфильм'
TAGS_RT = '#КотБарсик #МультикиДляДетей #Мультфильмы #ДетскиеМультфильмы'
FAMILY = 'Добрый мультфильм на русском языке для детей и всей семьи.'
SUB = '❤️ Подписывайтесь на канал, чтобы не пропустить новые серии!'
WD = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']


def desc(m, rt):
    lines = [m['lead'], SUB, ('📺 Все серии на канале: ' + RT) if rt else ('📺 Подписаться: ' + YT), '', m['plot'], '',
             'Герои: ' + m['heroes'], '', FAMILY, (TAGS_RT if rt else TAGS) + ' ' + m['tag']]
    return '\n'.join(lines)


items = []
for d in sorted(glob.glob(os.path.join(HERE, '[0-9]*')), key=lambda p: int(os.path.basename(p))):
    n = os.path.basename(d)
    mp = os.path.join(d, 'meta.json')
    if not os.path.exists(mp):
        continue
    m = json.load(open(mp, encoding='utf-8'))
    sc = open(os.path.join(d, 'scenario.txt'), encoding='utf-8').read().strip() + '\n'
    dt = datetime.date.fromisoformat(m['date'])
    it = {'num': int(n), 'date': m['date'], 'when': f"{WD[dt.weekday()]} {dt.strftime('%d.%m')} в {m['time']} МСК",
          'title': m['yt_title'], 'main': m.get('main', ''), 'scenario': sc, 'scenario_file': f'serii/{n}/scenario.txt',
          'yt_desc': desc(m, False), 'rt_desc': desc(m, True), 'shorts': m.get('shorts', ''), 'note': m.get('note', ''),
          'author': m.get('author', 'Claude'), 'build': m.get('build', ''), 'status': m.get('status', 'new'), 'v': m.get('v', 1)}
    if os.path.exists(os.path.join(d, 'cover.jpg')):
        it['cover'] = f'serii/{n}/cover.jpg'
    items.append(it)

now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
json.dump({'updated': now.strftime('%d.%m %H:%M'), 'items': items}, open(os.path.join(os.path.dirname(HERE), 'serii.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('serii.json:', [i['num'] for i in items])
