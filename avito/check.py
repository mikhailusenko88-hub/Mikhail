#!/usr/bin/env python3
"""Авито снаружи: наши объявления (просмотры, статус), страница компании, конкуренты по запросам в СПб.
Список — avito/list.txt. Результат — status/avito.md, status/avito.json, status/avito/*.jpg."""
import json, os, random, re, sys, time, traceback, urllib.parse
from playwright.sync_api import sync_playwright

OUT = 'status/avito'; os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
ours, brand, queries, comp_n, PAUSE, mine = [], None, [], 10, 2, set()
for l in open('avito/list.txt', encoding='utf-8'):
    if '|' not in l or l.startswith('#'): continue
    c = [x.strip() for x in l.split('|')]
    if c[0] == 'ours': ours.append({'art': c[1], 'id': c[2]})
    elif c[0] == 'brand': brand = c[1]
    elif c[0] == 'q': queries.append({'q': c[1], 'pages': int(c[2]) if len(c) > 2 else 1})
    elif c[0] == 'comp': comp_n = int(c[1])
    elif c[0] == 'pause': PAUSE = float(c[1])
    elif c[0] == 'mine': mine.add(c[1])

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
log = []
def L(s):
    log.append(s); print(s, flush=True)

def blocked(pg):
    t = (pg.title() or '') + ' ' + (pg.inner_text('body')[:600] if pg.locator('body').count() else '')
    if re.search(r'Доступ ограничен|проблема с IP|captcha|Подтвердите, что вы не робот|geetest|Just a moment|403 Forbidden|429', t, re.I):
        return t[:200].replace('\n', ' ')
    return ''

def goto(pg, url, wait_sel=None, shot=None):
    for attempt in range(3):
        try:
            resp = pg.goto(url, wait_until='domcontentloaded', timeout=45000)
            st = resp.status if resp else 0
            if wait_sel:
                try: pg.wait_for_selector(wait_sel, timeout=12000)
                except Exception: pass
            time.sleep(random.uniform(PAUSE, PAUSE * 1.5))
            b = blocked(pg)
            if b:
                L(f'  блок ({st}) на {url}: {b}')
                if attempt < 2: time.sleep(random.uniform(8, 15)); continue
                return st, b
            if shot:
                try: pg.screenshot(path=os.path.join(OUT, shot), full_page=False, type='jpeg', quality=70)
                except Exception: pass
            return st, ''
        except Exception as e:
            L(f'  ошибка {url}: {str(e)[:120]}')
            time.sleep(5)
    return 0, 'не открылось'

def txt(pg, sel):
    try:
        loc = pg.locator(sel).first
        return loc.inner_text(timeout=2000).strip() if loc.count() else ''
    except Exception: return ''

def attr(pg, sel, a):
    try:
        loc = pg.locator(sel).first
        return (loc.get_attribute(a, timeout=2000) or '') if loc.count() else ''
    except Exception: return ''

def item_page(pg, url, shot=None):
    st, b = goto(pg, url, '[data-marker="item-view/title-info"], [data-marker="item-view/closed-warning"], h1', shot)
    d = {'url': url, 'http': st, 'blocked': b}
    if b: return d
    body = pg.inner_text('body') if pg.locator('body').count() else ''
    d['title'] = txt(pg, 'h1')
    d['price'] = attr(pg, '[itemprop="price"]', 'content') or txt(pg, '[data-marker="item-view/item-price"]')
    d['views'] = txt(pg, '[data-marker="item-view/total-views"]')
    d['today'] = txt(pg, '[data-marker="item-view/today-views"]')
    d['date'] = txt(pg, '[data-marker="item-view/item-date"]')
    d['seller'] = txt(pg, '[data-marker="seller-info/name"], [data-marker="seller-link/link"], [data-marker="seller-info/label"]')
    d['closed'] = txt(pg, '[data-marker="item-view/closed-warning"]')
    d['photos'] = pg.locator('[data-marker^="image-preview/item"]').count() or pg.locator('[data-marker="image-frame/image-wrapper"] img').count()
    d['address'] = txt(pg, '[data-marker="item-view/item-address"], [itemprop="address"]')
    d['favorites'] = ''
    m = re.search(r'(\d+)\s+(человек|чел\.?)\s+добавил', body)
    if m: d['favorites'] = m.group(0)
    desc = txt(pg, '[data-marker="item-view/item-description"]')
    d['desc_first'] = desc.split('\n')[0][:160] if desc else ''
    d['status_text'] = ''
    for pat in (r'Объявление снято с публикации', r'Объявление закрыто', r'на проверке', r'отклонено', r'Объявление не найдено', r'удалено'):
        if re.search(pat, body, re.I): d['status_text'] += pat + '; '
    params = txt(pg, '[data-marker="item-view/item-params"]')
    d['params'] = re.sub(r'\s+', ' ', params)[:300]
    return d

def search(pg, q, pages, shot=None):
    res = {'q': q, 'count': '', 'items': [], 'blocked': ''}
    for p in range(1, pages + 1):
        url = 'https://www.avito.ru/sankt-peterburg?' + urllib.parse.urlencode({'q': q, 'p': p}) if p > 1 else 'https://www.avito.ru/sankt-peterburg?' + urllib.parse.urlencode({'q': q})
        st, b = goto(pg, url, '[data-marker="item"]', shot if p == 1 else None)
        if b: res['blocked'] = b; return res
        if p == 1:
            res['count'] = txt(pg, '[data-marker="page-title/count"]')
            res['title'] = txt(pg, 'h1')
        cards = pg.locator('[data-marker="item"]')
        n = cards.count()
        L(f'  «{q}» стр. {p}: карточек {n}, всего «{res["count"]}»')
        for k in range(n):
            c = cards.nth(k)
            try:
                iid = c.get_attribute('data-item-id') or c.get_attribute('id') or ''
                t = c.locator('[itemprop="name"], [data-marker="item-title"]').first
                title = t.inner_text(timeout=1500).strip() if t.count() else ''
                href = ''
                a = c.locator('a[data-marker="item-title"], a[itemprop="url"]').first
                if a.count(): href = a.get_attribute('href') or ''
                pr = c.locator('[data-marker="item-price"] meta[itemprop="price"], [itemprop="price"]').first
                price = (pr.get_attribute('content') or '') if pr.count() else ''
                if not price:
                    pt = c.locator('[data-marker="item-price"]').first
                    price = pt.inner_text(timeout=1000).strip() if pt.count() else ''
                full = re.sub(r'\s+', ' ', c.inner_text(timeout=2000))[:400]
                promoted = bool(c.locator('[data-marker*="promo"], [data-marker*="vas"], [data-marker*="highlight"]').count())
                res['items'].append({'pos': len(res['items']) + 1, 'page': p, 'id': iid.replace('i', ''), 'title': title, 'price': price, 'href': ('https://www.avito.ru' + href) if href.startswith('/') else href, 'promoted': promoted, 'text': full})
            except Exception as e:
                res['items'].append({'pos': len(res['items']) + 1, 'page': p, 'err': str(e)[:80]})
    return res

def brand_page(pg, url):
    st, b = goto(pg, url, '[data-marker="item"], h1', 'brand.jpg')
    d = {'url': url, 'http': st, 'blocked': b}
    if b: return d
    body = pg.inner_text('body') if pg.locator('body').count() else ''
    d['title'] = txt(pg, 'h1')
    d['items_on_page'] = pg.locator('[data-marker="item"]').count()
    m = re.search(r'(\d+[,.]?\d*)\s*(★|\n)?\s*(\d+)\s*отзыв', body)
    d['rating_text'] = m.group(0) if m else ''
    for pat in (r'\d+\s+объявлени[еяй]', r'Реквизиты проверены', r'На Авито с[^\n]{0,20}', r'Отвечает[^\n]{0,40}', r'\d+ отзыв\w*', r'Нет отзывов'):
        mm = re.search(pat, body)
        if mm: d.setdefault('facts', []).append(mm.group(0))
    d['items'] = []
    cards = pg.locator('[data-marker="item"]')
    for k in range(min(cards.count(), 40)):
        c = cards.nth(k)
        try:
            t = c.locator('[itemprop="name"], [data-marker="item-title"]').first
            pr = c.locator('[itemprop="price"]').first
            d['items'].append({'id': (c.get_attribute('data-item-id') or ''), 'title': t.inner_text(timeout=1500).strip() if t.count() else '', 'price': (pr.get_attribute('content') or '') if pr.count() else ''})
        except Exception: pass
    d['body_head'] = re.sub(r'\s+', ' ', body[:700])
    return d

data = {'when': time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()), 'ours': [], 'brand': None, 'search': [], 'competitors': []}
with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', headless=True, args=['--disable-blink-features=AutomationControlled', '--lang=ru-RU'])
    ctx = br.new_context(viewport={'width': 1366, 'height': 900}, user_agent=UA, locale='ru-RU', timezone_id='Europe/Moscow',
                         extra_http_headers={'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.5'})
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    pg = ctx.new_page()
    try:
        st, b = goto(pg, 'https://www.avito.ru/sankt-peterburg', 'body', 'home.jpg')
        L(f'Главная СПб: {st} {b or "ок"}; IP-проверка пропущена')
        our_ids = {o['id'] for o in ours} | mine
        seen = {}
        for i, qq in enumerate(queries):
            L(f'Поиск «{qq["q"]}»')
            r = search(pg, qq['q'], qq['pages'], f'q{i+1}.jpg')
            r['ours_positions'] = [{'pos': it['pos'], 'page': it['page'], 'id': it['id']} for it in r['items'] if it.get('id') in our_ids]
            data['search'].append(r)
            for it in r['items']:
                if it.get('id') and it['id'] not in our_ids and it.get('href') and it['id'] not in seen:
                    seen[it['id']] = {'id': it['id'], 'href': it['href'], 'first_q': qq['q'], 'pos': it['pos'], 'title': it['title'], 'price': it['price']}
        for o in ours:
            L(f'Наше {o["art"]} {o["id"]}')
            d = item_page(pg, f'https://www.avito.ru/{o["id"]}', f'our-{o["art"].replace("/", "-").replace(" ", "_")}.jpg')
            d.update(o); data['ours'].append(d)
            L(f'  → {d.get("title","")[:50]} | {d.get("price","")} | {d.get("views","")} {d.get("today","")} | {d.get("date","")} | {d.get("closed","")} {d.get("status_text","")}')
        if brand:
            L('Страница компании'); data['brand'] = brand_page(pg, brand); L(f'  → {json.dumps(data["brand"], ensure_ascii=False)[:300]}')
        # чужие объявления: первые из выдачи по порядку запросов, не дубли, не промо-«за просмотры» — открыть и снять просмотры
        comp = list(seen.values())[:comp_n]
        for c in comp:
            L(f'Конкурент {c["id"]} ({c["first_q"]}, поз. {c["pos"]})')
            d = item_page(pg, c['href'].split('?')[0])
            d.update({k: c[k] for k in ('first_q', 'pos')})
            data['competitors'].append(d)
            L(f'  → {d.get("title","")[:50]} | {d.get("price","")} | {d.get("views","")} {d.get("today","")} | {d.get("date","")} | {d.get("seller","")}')
    except Exception:
        L('СБОЙ: ' + traceback.format_exc()[-1500:])
    finally:
        br.close()

json.dump(data, open('status/avito.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# --- отчёт
def vnum(s):
    m = re.search(r'\d[\d\s\xa0]*', s or ''); return int(re.sub(r'\D', '', m.group(0))) if m else None
md = [f'# Авито снаружи — {data["when"]}', '']
md += ['## Наши объявления', '', '| Артикул | № | Заголовок | Цена | Просмотров | Сегодня | Дата | Статус |', '|---|---|---|---|---|---|---|---|']
for d in data['ours']:
    stt = d.get('blocked') or d.get('closed') or d.get('status_text') or ('ок' if d.get('title') else f'http {d.get("http")}')
    md.append(f'| {d["art"]} | {d["id"]} | {d.get("title","")[:60]} | {d.get("price","")} | {d.get("views","")} | {d.get("today","")} | {d.get("date","")} | {stt} |')
md.append('')
for d in data['ours']:
    if d.get('title'):
        md.append(f'- {d["art"]}: фото {d.get("photos")}, {d.get("favorites") or "избранное не показано"}, адрес «{d.get("address","")}», продавец «{d.get("seller","")}», первая строка: «{d.get("desc_first","")}»; параметры: {d.get("params","")[:200]}')
md.append('')
b = data['brand'] or {}
md += ['## Страница компании', '', f'- {b.get("url")}: http {b.get("http")}, {b.get("blocked") or "ок"}; заголовок «{b.get("title","")}», объявлений на странице {b.get("items_on_page")}, факты: {b.get("facts")}; {b.get("rating_text","")}', '']
for it in b.get('items', []): md.append(f'  - {it["id"]} {it["title"][:70]} — {it["price"]}')
md.append('')
md += ['## Поиск по Санкт-Петербургу', '']
for r in data['search']:
    md.append(f'### «{r["q"]}» — {r.get("count") or r.get("blocked") or "?"}; наши в выдаче: {r.get("ours_positions") or "нет"}')
    for it in r['items'][:25]:
        if 'err' in it: continue
        flag = ' **НАШЕ**' if it['id'] in ({o['id'] for o in ours} | mine) else ''
        md.append(f'{it["pos"]}. {it["title"][:70]} — {it["price"]} ₽{flag} — {it["text"][len(it["title"]):][:120].strip()}')
    md.append('')
md += ['## Чужие объявления: просмотры', '', '| Поз. (запрос) | Заголовок | Цена | Просмотров | Сегодня | Дата | Продавец | Фото |', '|---|---|---|---|---|---|---|---|']
for d in data['competitors']:
    md.append(f'| {d.get("pos")} ({d.get("first_q")}) | {d.get("title","")[:55]} | {d.get("price","")} | {d.get("views","")} | {d.get("today","")} | {d.get("date","")} | {d.get("seller","")[:30]} | {d.get("photos","")} |')
md += ['', '## Журнал', ''] + [f'    {l}' for l in log]
open('status/avito.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print('\n'.join(md[:80]))
