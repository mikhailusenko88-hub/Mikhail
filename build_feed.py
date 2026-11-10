#!/usr/bin/env python3
"""Генератор фида Авито Автозагрузки (XML) для магазина «Наш декор».

Запуск:  python3 build_feed.py [путь/к/config.json] [--check-photos]
         --check-photos — дополнительно открыть каждую ссылку на фото и убедиться, что это картинка
         (запускать там, где есть доступ к photo_base, например на сервере).
Берёт каталог из index.html (const CAT / const PHOTO), тексты из avito_texts.json
(если файла нет — заглушки из названия и описания каталога), пишет avito.xml и проверяет его.
"""
import html
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from clean_texts import clean, problems  # noqa: E402  правила текстов магазина

CATALOG_SIZE = 107          # артикулов в каталоге сайта


def load_config(path):
    with open(path, encoding='utf-8') as f:
        cfg = json.load(f)
    cfg = {k: v for k, v in cfg.items() if not k.startswith('_')}
    base = os.path.dirname(os.path.abspath(path))
    for k in ('catalog_html', 'texts_json', 'output_xml'):
        if cfg.get(k) and not os.path.isabs(cfg[k]):
            cfg[k] = os.path.join(base, cfg[k])
    return cfg


def load_catalog(index_html):
    s = open(index_html, encoding='utf-8').read()
    m = re.search(r'const CAT=(\[.*?\]);', s, re.S)
    if not m:
        sys.exit('В index.html не найден const CAT=[...];')
    cat = json.loads(m.group(1))
    m = re.search(r'const PHOTO\s*=\s*(\{.*?\});', s, re.S)
    photo = json.loads(m.group(1)) if m else {}
    return cat, photo


def load_texts(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):            # на случай формата {артикул: {...}}
        data = [dict(v, a=k) for k, v in data.items()]
    return {str(x['a']).strip(): x for x in data if x.get('a')}


def ad_id(article):
    """Id объявления = артикул, где / и пробелы заменены (A002/2 -> A002-2, GS 1 -> GS1)."""
    return re.sub(r'\s+', '', article.replace('/', '-'))


def load_crm(cfg):
    """Цены и свободные остатки из CRM: {"ok": true, "items": {"A902": {"p": 1780, "q": 0}, ...}}.
    Источник — файл (--crm-json=путь) или адрес crm_catalog_url. Если CRM не ответила — фид НЕ собираем
    (иначе на Авито уйдут неверные цены/наличие), старый фид остаётся как был."""
    import urllib.request
    src = cfg.get('crm_json') or cfg.get('crm_catalog_url')
    if not src:
        return None
    try:
        if os.path.exists(src):
            data = json.load(open(src, encoding='utf-8'))
        else:
            req = urllib.request.Request(src, headers={'User-Agent': 'nashdekor-avito-feed/1.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        sys.exit(f'CRM не ответила ({src}): {e} — фид не собран, старый остаётся')
    items = data.get('items') if isinstance(data, dict) else None
    if not items or (isinstance(data, dict) and data.get('ok') is False):
        sys.exit(f'CRM вернула пустой каталог ({src}) — фид не собран, старый остаётся')
    return {str(k).strip(): v for k, v in items.items()}


def price_for(item, cfg):
    crm = cfg.get('_crm') or {}
    c = crm.get(item['a'])
    if c and isinstance(c.get('p'), (int, float)) and c['p'] > 0:
        return int(round(c['p']))
    prices = cfg.get('prices') or {}
    if item['a'] in prices:
        return int(prices[item['a']])
    step = int(cfg.get('price_round_to', 10)) or 1
    raw = float(item['r']) * float(cfg.get('price_multiplier', 1.0))
    return int(math.ceil(round(raw, 6) / step) * step)


def cut_title(t, article, limit):
    """Укладывает заголовок в лимит Авито, не теряя артикул:
    1) убирает слово ARTDEC; 2) если всё ещё длинно — режет текст перед артикулом по границе слова."""
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= limit:
        return t
    t2 = re.sub(r'\s+', ' ', re.sub(r'\bARTDEC\b', ' ', t)).strip(' ,')
    if len(t2) <= limit:
        return t2
    head = t2[:-len(article)].rstrip(' ,') if t2.endswith(article) else t2
    tail = f' {article}' if t2.endswith(article) else ''
    room = limit - len(tail)
    cut = head[:room + 1].rsplit(' ', 1)[0] if len(head) > room else head
    return (cut[:room].rstrip(' ,.;:—-') + tail).strip()


KIND_WORD = {'panel': 'панели', 'color': 'панели', 'mold': 'молдинга', 'plinth': 'плинтуса',
             'cornice': 'карниза', 'corner': 'уголка'}


def stub_text(item):
    """Заглушка, пока исполнитель не прислал avito_texts.json."""
    lines = [f"{item['n']} — ARTDEC (Казахстан).",
             f"{item['d'][:1].upper()}{item['d'][1:]}.",
             '',
             'Материал — дюрополимер (полистирол высокой плотности): лёгкий, влагостойкий, не гниёт.',
             f"Длина {KIND_WORD.get(item['c'], 'изделия')} {item['l']} мм, ширина {item['w']} мм, толщина {item['t']} мм.",
             f"В коробке {item['b']} шт. Цена указана за 1 шт.",
             '',
             'Продаём поштучно и коробками. Поможем рассчитать количество на вашу стену — напишите размеры.']
    return {'title': item['n'], 'description': '\n'.join(lines), 'kind': item['c'], 'stub': True}


def to_html(text):
    """Простой текст -> разрешённые Авито теги: <p>, <br>, <ul>/<li>."""
    out = []
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = [l.rstrip() for l in block.split('\n') if l.strip()]
        if not lines:
            continue
        if all(re.match(r'^\s*([-—–•·✓✔]|\d+[.)])\s+', l) for l in lines):
            items = [re.sub(r'^\s*([-—–•·✓✔]|\d+[.)])\s+', '', l) for l in lines]
            out.append('<ul>' + ''.join(f'<li>{html.escape(i, quote=False)}</li>' for i in items) + '</ul>')
        else:
            out.append('<p>' + '<br>'.join(html.escape(l, quote=False) for l in lines) + '</p>')
    return ''.join(out)


def is_placeholder(v):
    v = (v or '').strip()
    return not v or (v.startswith('[') and v.endswith(']'))


def build(cfg):
    cat, photo = load_catalog(cfg['catalog_html'])
    texts = load_texts(cfg.get('texts_json'))
    crm = cfg.get('_crm')
    in_stock = {str(a).strip() for a in cfg.get('in_stock', [])}
    unknown_stock = in_stock - {x['a'] for x in cat}
    qty = {}
    if crm is not None:
        qty = {a: int(v.get('q') or 0) for a, v in crm.items() if isinstance(v, dict)}
        in_stock = {a for a, q in qty.items() if q > 0}
        unknown_stock = set()
        missing = sorted({x['a'] for x in cat} - set(crm))
        if missing:
            warnings_pre = f'в CRM нет артикулов (цена с сайта, «под заказ»): {missing}'
        else:
            warnings_pre = None
    extra = cfg.get('extra_photos') or {}
    img_dir = os.path.join(os.path.dirname(cfg['catalog_html']), 'img')
    base = cfg['photo_base'] if cfg['photo_base'].endswith('/') else cfg['photo_base'] + '/'

    warnings, no_photo, stubs, rows, shortened = [], [], [], [], []
    if crm is not None and warnings_pre:
        warnings.append(warnings_pre)
    if unknown_stock:
        warnings.append(f'in_stock: нет в каталоге артикулов {sorted(unknown_stock)}')
    if texts is None:
        warnings.append(f"Файл текстов не найден ({cfg.get('texts_json')}) — у всех объявлений заглушки из каталога")

    skip = {str(a).strip() for a in cfg.get('skip', [])}
    avito_ids = {str(k).strip(): int(v) for k, v in (cfg.get('avito_ids') or {}).items()}
    unknown = (skip | set(avito_ids)) - {x['a'] for x in cat}
    if unknown:
        warnings.append(f'skip/avito_ids: нет в каталоге артикулов {sorted(unknown)}')

    root = ET.Element('Ads', formatVersion='3', target='Avito.ru')
    for item in cat:
        a = item['a']
        if a in skip:
            continue
        t = (texts or {}).get(a)
        if not t:
            t = stub_text(item)
            stubs.append(a)
        src_title = clean((t.get('title') or item['n']).strip())
        title = cut_title(src_title, a, int(cfg.get('title_max', 50)))
        if title != re.sub(r'\s+', ' ', src_title):
            shortened.append(f'{a}: «{src_title}» ({len(src_title)}) → «{title}» ({len(title)})')
        body = clean((t.get('description') or '').strip())
        q_line = (cfg.get('quality_line') or '').strip()
        if q_line and q_line not in body:          # про систему качества — перед строкой «Цена в объявлении…», если она есть
            m = re.search(r'\n\n(Цена в объявлении[^\n]*)$', body)
            body = f'{body[:m.start()]}\n\n{q_line}{body[m.start():]}' if m else f'{body}\n\n{q_line}'

        stocked = a in in_stock
        avail_line = (cfg['stock_line'].format(q=qty.get(a, '')) if stocked
                      else cfg['order_line'].format(lead_time=cfg.get('lead_time', '[срок]')))
        body = f'{avail_line}\n\n{body}' if cfg.get('availability_line_position', 'start') == 'start' else f'{body}\n\n{avail_line}'
        desc = to_html(body) if cfg.get('description_html', True) else body

        mapping = cfg['category_map'].get(item['c'])
        if not mapping:
            sys.exit(f'Нет category_map для вида «{item["c"]}» (артикул {a})')

        imgs = []
        if photo.get(a):
            imgs.append(photo[a])
        else:
            no_photo.append(a)
        for fn in list(extra.get(a, [])) + list(extra.get(item['c'], [])):
            if fn not in imgs:
                imgs.append(fn)
        for fn in imgs:
            if not os.path.exists(os.path.join(img_dir, fn)):
                warnings.append(f'{a}: файла img/{fn} нет на диске — ссылка будет битой')

        ad = ET.SubElement(root, 'Ad')
        def add(tag, val):
            el = ET.SubElement(ad, tag); el.text = str(val); return el
        add('Id', ad_id(a))
        if a in avito_ids:
            add('AvitoId', avito_ids[a])
        add('Category', cfg['category'])
        add('GoodsType', cfg['goods_type'])
        for k, v in mapping.items():
            add(k, v)
        add('AdType', cfg['ad_type'])
        add('Condition', cfg['condition'])
        if cfg.get('availability_tag'):
            add('Availability', 'В наличии' if stocked else 'Под заказ')
        add('Address', cfg['address'])
        if not is_placeholder(cfg.get('contact_phone')):
            add('ContactPhone', cfg['contact_phone'])
        if not is_placeholder(cfg.get('manager_name')):
            add('ManagerName', cfg['manager_name'])
        add('ContactMethod', cfg['contact_method'])
        if cfg.get('multi_item') in ('Да', 'Нет'):
            add('MultiItem', cfg['multi_item'])
        add('Title', title)
        add('Description', desc)
        add('Price', price_for(item, cfg))
        if imgs:
            ims = ET.SubElement(ad, 'Images')
            for fn in imgs[:10]:
                ET.SubElement(ims, 'Image', url=base + fn)
        rows.append({'a': a, 'id': ad_id(a), 'title': title, 'desc': desc, 'imgs': imgs,
                     'stocked': stocked, 'price': price_for(item, cfg)})

    shared = {}
    for r in rows:
        if r['imgs']:
            shared.setdefault(r['imgs'][0], []).append(r['a'])
    shared = {k: v for k, v in shared.items() if len(v) > 1}
    if shared:
        warnings.append('одно и то же главное фото у разных объявлений (Авито может счесть их повторами — '
                        'лучше своё фото для каждой длины): ' + '; '.join(f'{k}: {", ".join(v)}' for k, v in shared.items()))
    if shortened:
        warnings.append(f'заголовки длиннее {cfg.get("title_max", 50)} симв. укорочены автоматически ({len(shortened)}):\n    '
                        + '\n    '.join(shortened))
    if is_placeholder(cfg.get('contact_phone')):
        warnings.append('contact_phone — заглушка: тег ContactPhone не записан (Авито возьмёт телефон из профиля)')
    if is_placeholder(cfg.get('manager_name')):
        warnings.append('manager_name — заглушка: тег ManagerName не записан')
    if '[' in str(cfg.get('lead_time', '')):
        warnings.append('lead_time — заглушка, в описаниях будет «[срок]»')
    return root, rows, no_photo, stubs, warnings


def serialize(root, path, use_cdata):
    """Пишем XML вручную, чтобы Description шёл в CDATA (так Авито рекомендует для HTML)."""
    def esc(s):
        return html.escape(s, quote=False)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<Ads formatVersion="{root.get("formatVersion")}" target="{root.get("target")}">']
    for ad in root:
        out.append('  <Ad>')
        for el in ad:
            if el.tag == 'Images':
                out.append('    <Images>')
                for im in el:
                    out.append(f'      <Image url="{html.escape(im.get("url"), quote=True)}"/>')
                out.append('    </Images>')
            elif el.tag == 'Description' and use_cdata:
                out.append(f'    <Description><![CDATA[{el.text.replace("]]>", "]]&gt;")}]]></Description>')
            else:
                out.append(f'    <{el.tag}>{esc(el.text)}</{el.tag}>')
        out.append('  </Ad>')
    out.append('</Ads>\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))


def visible_len(desc):
    return len(html.unescape(re.sub(r'<[^>]+>', '', desc)))


def validate(path, rows, cfg, no_photo):
    errors = []
    try:
        tree = ET.parse(path)                      # валидный XML?
    except ET.ParseError as e:
        return [f'XML невалиден: {e}']
    ads = tree.getroot().findall('Ad')
    expected = CATALOG_SIZE - len(set(cfg.get('skip', [])))
    if len(ads) != expected:
        errors.append(f'объявлений {len(ads)}, ожидалось {expected} (каталог {CATALOG_SIZE} минус skip)')
    aids = [ad.findtext('AvitoId') for ad in ads if ad.findtext('AvitoId')]
    if len(aids) != len(set(aids)):
        errors.append(f'AvitoId повторяется: {aids}')
    ids = [ad.findtext('Id') for ad in ads]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errors.append(f'повторяются Id: {dup}')
    tmax, dmax = int(cfg.get('title_max', 50)), int(cfg.get('description_max', 7500))
    # общие поля — лимиты из спецификации Авито
    if len(cfg['address']) > 256:
        errors.append('Address длиннее 256 символов')
    if not is_placeholder(cfg.get('manager_name')) and len(cfg['manager_name']) > 40:
        errors.append('ManagerName длиннее 40 символов')
    if not is_placeholder(cfg.get('contact_phone')):
        digits = re.sub(r'\D', '', cfg['contact_phone'])
        if not (len(digits) == 10 or (len(digits) == 11 and digits[0] in '78')):
            errors.append(f'ContactPhone «{cfg["contact_phone"]}» — нужен один российский номер с кодом')
    if cfg.get('contact_method') not in ('По телефону и в сообщениях', 'По телефону', 'В сообщениях'):
        errors.append(f'ContactMethod «{cfg.get("contact_method")}» не из списка Авито')
    for ad in ads:
        i = ad.findtext('Id')
        if len(i or '') > 100:
            errors.append(f'{i}: Id длиннее 100 символов')
        if len(ad.findall('Images/Image')) > 10:
            errors.append(f'{i}: больше 10 фото')
        t = ad.findtext('Title') or ''
        d = ad.findtext('Description') or ''
        for pr in problems(t + ' ' + d):
            errors.append(f'{i}: в тексте {pr} — правило магазина')
        if not t or len(t) > tmax:
            errors.append(f'{i}: заголовок {len(t)} симв. (лимит {tmax})')
        if not d or len(d) > dmax:
            errors.append(f'{i}: описание {len(d)} симв. с тегами (лимит {dmax})')
        for tag in ('Category', 'GoodsType', 'GoodsSubType', 'AdType', 'Condition', 'Address', 'Price'):
            if not (ad.findtext(tag) or '').strip():
                errors.append(f'{i}: пустой {tag}')
        p = ad.findtext('Price') or '0'
        if not p.isdigit() or int(p) <= 0:
            errors.append(f'{i}: цена «{p}»')
        if ad.findtext('Address') != cfg['address']:
            errors.append(f'{i}: адрес не из config')
        if ad.find('Images') is None and i not in {ad_id(a) for a in no_photo}:
            errors.append(f'{i}: нет фото')
        for im in ad.iter('Image'):
            u = im.get('url', '')
            if not re.match(r'^https?://\S+\.(jpe?g|png)$', u, re.I):
                errors.append(f'{i}: подозрительная ссылка на фото {u}')
    return errors


def check_photos_online(path):
    """Проверяет, что каждая ссылка на фото отдаёт картинку (HTTP 200 и Content-Type image/*)."""
    import urllib.request
    urls = sorted({im.get('url') for im in ET.parse(path).getroot().iter('Image')})
    bad = []
    for n, u in enumerate(urls):
        if n == 5 and len(bad) == 5:
            print('Фото онлайн: первые 5 ссылок не открываются как картинка — проверка остановлена:')
            for b in bad:
                print('  -', b)
            return False
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                ctype = r.headers.get('Content-Type', '')
                if r.status != 200 or not ctype.startswith('image/'):
                    bad.append(f'{u} → HTTP {r.status}, {ctype or "без типа"}')
        except Exception as e:
            bad.append(f'{u} → {str(e)[:80]}')
    print(f'Фото онлайн: проверено {len(urls)}, не открываются как картинка: {len(bad)}')
    for b in bad[:20]:
        print('  -', b)
    if len(bad) > 20:
        print(f'  … и ещё {len(bad) - 20}')
    return not bad


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opts = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
    cfg_path = args[0] if args else os.path.join(HERE, 'config.json')
    cfg = load_config(cfg_path)
    # переопределения для запуска на GitHub: --catalog=…/index.html --out=…/avito.xml --crm-json=файл
    if opts.get('catalog'):
        cfg['catalog_html'] = os.path.abspath(opts['catalog'])
    if opts.get('out'):
        cfg['output_xml'] = os.path.abspath(opts['out'])
    if opts.get('crm-json'):
        cfg['crm_json'] = os.path.abspath(opts['crm-json'])
    if '--no-crm' in sys.argv:
        cfg['crm_catalog_url'] = cfg['crm_json'] = None
    cfg['_crm'] = load_crm(cfg)
    root, rows, no_photo, stubs, warnings = build(cfg)
    out = cfg.get('output_xml') or os.path.join(HERE, 'avito.xml')
    serialize(root, out, cfg.get('description_html', True))
    errors = validate(out, rows, cfg, no_photo)

    n_stock = sum(r['stocked'] for r in rows)
    tl = [len(r['title']) for r in rows]
    dl = [len(r['desc']) for r in rows]
    print(f'Файл: {out}  ({os.path.getsize(out) // 1024} КБ)')
    print('Цены и наличие: ' + ('из CRM' if cfg.get('_crm') is not None else 'из каталога сайта и config.json'))
    print(f'Объявлений: {len(rows)} (в наличии {n_stock}, под заказ {len(rows) - n_stock})'
          + (f'; не выгружаем: {", ".join(cfg.get("skip", []))}' if cfg.get('skip') else ''))
    if cfg.get('avito_ids'):
        print('Привязка к существующим объявлениям: ' + ', '.join(f'{k} → {v}' for k, v in cfg['avito_ids'].items()))
    print(f'Заголовки: {min(tl)}–{max(tl)} симв. (лимит {cfg.get("title_max", 50)}); '
          f'описания: {min(dl)}–{max(dl)} симв. с тегами (лимит {cfg.get("description_max", 7500)})')
    print(f'Тексты: {len(rows) - len(stubs)} из avito_texts.json, заглушек {len(stubs)}'
          + (f' — {", ".join(stubs)}' if 0 < len(stubs) < len(rows) else ''))
    print('Без фото: ' + (', '.join(no_photo) if no_photo else 'нет'))
    for w in warnings:
        print('ВНИМАНИЕ:', w)
    if errors:
        print(f'ОШИБКИ ({len(errors)}):')
        for e in errors:
            print('  -', e)
        sys.exit(1)
    print('Проверка пройдена: XML валиден, Id уникальны, лимиты соблюдены.')
    if '--check-photos' in sys.argv and not check_photos_online(out):
        sys.exit(2)


if __name__ == '__main__':
    main()
