# -*- coding: utf-8 -*-
"""Проверка avito_texts.json. Запуск: python3 check_avito_texts.py <index.html> <avito_texts.json>"""
import json, re, sys
from collections import Counter

html = open(sys.argv[1], encoding='utf-8').read()
CAT = json.loads(re.search(r'const CAT=(\[.*?\]);', html, re.S).group(1))
BY = {x['a']: x for x in CAT}
data = json.load(open(sys.argv[2], encoding='utf-8'))

KINDS = {'Стеновые панели', 'Молдинги', 'Плинтусы', 'Карнизы', 'Уголки'}
KIND = {'panel': 'Стеновые панели', 'color': 'Стеновые панели', 'mold': 'Молдинги',
        'plinth': 'Плинтусы', 'cornice': 'Карнизы', 'corner': 'Уголки'}
BAD = [r'claude', r'anthropic', r'\bИИ\b', r'нейросет', r'искусственн', r'\bAI\b', r'GPT',
       r'сертифик', r'гарант', r'наличи[еияю]', r'под заказ', r'\bсрок', r'₽', r'\bруб',
       r'http', r'www', r'\.ru\b', r'@', r'\+7', r'телефон', r'адрес', r'звукоизол', r'шумоизол',
       r'акустич', r'whatsapp', r'telegram', r'телеграм', r'ватсап', r'скидк', r'экологически чист']
errs = []
if len(data) != 107:
    errs.append(f'записей {len(data)} != 107')
arts = [d['a'] for d in data]
if set(arts) != set(BY) or len(arts) != len(set(arts)):
    errs.append(f'артикулы: лишние {set(arts) - set(BY)}, нет {set(BY) - set(arts)}, повторы {[a for a, n in Counter(arts).items() if n > 1]}')
titles = Counter(d['title'] for d in data)
for t, n in titles.items():
    if n > 1:
        errs.append(f'повтор заголовка: {t}')
lens = []
for d in data:
    a, t, s, k = d['a'], d['title'], d['description'], d['kind']
    x = BY.get(a)
    if set(d) != {'a', 'title', 'description', 'kind'}:
        errs.append(f'{a}: поля {set(d)}')
    if len(t) > 50:
        errs.append(f'{a}: заголовок {len(t)} > 50: {t}')
    if a not in t:
        errs.append(f'{a}: нет артикула в заголовке: {t}')
    if not 700 <= len(s) <= 1500:
        errs.append(f'{a}: описание {len(s)} знаков')
    lens.append(len(s))
    if k not in KINDS or (x and KIND[x['c']] != k):
        errs.append(f'{a}: kind {k}')
    if s.strip().split('\n')[-1] != 'Цена в объявлении — за 1 шт.':
        errs.append(f'{a}: последняя строка')
    for b in BAD:
        for fld in (t, s):
            if re.search(b, fld, re.I if b not in (r'\bИИ\b', r'\bAI\b') else 0):
                errs.append(f'{a}: запрещённое «{b}»')
    if x:
        if ('Г2' in s) != ('под покраску' in x['d']):
            errs.append(f'{a}: Г2 не соответствует (под покраску={"под покраску" in x["d"]})')
        if 'каналом под кабель' in x['d'] and 'канал' not in s:
            errs.append(f'{a}: не указан канал под кабель')
        if 'канал' in s and 'каналом под кабель' not in x['d']:
            errs.append(f'{a}: канал упомянут без данных')
        if f'{x["w"]}×{x["t"]}×{x["l"]} мм' not in s:
            errs.append(f'{a}: нет размера')
        if 'поштучно' not in s.lower() or 'Ленобласт' not in s and 'Ленинградск' not in s or '3D-примерк' not in s:
            errs.append(f'{a}: нет блока продаж')
        if x['c'] in ('panel', 'color') and 'м²' not in s:
            errs.append(f'{a}: нет м²')
        if x['c'] not in ('panel', 'color') and 'погонн' not in s:
            errs.append(f'{a}: нет погонных метров')
        if f'{x["b"]} шт' not in s:
            errs.append(f'{a}: нет штук в коробке')

print('записей:', len(data), '| описания min/max:', min(lens), max(lens),
      '| заголовок max:', max(len(d['title']) for d in data))
print('ошибок:', len(errs))
for e in errs:
    print(' -', e)
sys.exit(1 if errs else 0)
