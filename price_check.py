# Открывает страницы из request.txt в Chromium, ждёт загрузки, прокручивает и сохраняет текст.
# Строки request.txt:
#   <URL>                 — открыть и сохранить (как раньше)
#   follow: <regex>       — со следующей страницы открыть подходящие ссылки (до 12)
#   open: <URL>           — открыть без сохранения (для сценария действий)
#   click: <текст>        — нажать видимый элемент с таким текстом (точно, потом — по вхождению)
#   type: <текст>         — набрать текст в поле с фокусом
#   wait: <мс>            — подождать
#   snap: <имя>           — сохранить текст текущей страницы в status/<имя>.txt
#   fill: <css> => <текст> — вписать текст в первое видимое поле по CSS-селектору
#   press: <клавиша>      — нажать клавишу (Enter и т.п.)
#   size: <ширина>x<высота> — размер окна (390x844 — как телефон)
#   shot: <имя>           — снимок всей страницы в status/<имя>.png
import re, asyncio, datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright

LOG = []

async def scroll(page):
    for _ in range(12):
        await page.mouse.wheel(0, 1500); await page.wait_for_timeout(350)
    await page.wait_for_timeout(1200)

async def grab(page, url):
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(4000)
        await scroll(page)
        return await dump(page)
    except Exception as e:
        return f'ОШИБКА: {e}', []

async def dump(page):
    text = await page.inner_text('body')
    links = await page.eval_on_selector_all('a[href]', 'els => els.map(e => [e.href, (e.innerText||"").trim().slice(0,80)])')
    return text, links

def save(name, url, text, links):
    open(f'status/{name}.txt', 'w', encoding='utf-8').write(
        f'URL: {url}\n\n{text}\n\n--- ССЫЛКИ ---\n' + '\n'.join(f'{h} | {t}' for h, t in links))

def slug(u):
    p = urlparse(u); s = (p.netloc + p.path).strip('/').replace('/', '_')
    return re.sub(r'[^A-Za-z0-9_.-]', '-', s)[:90] or 'page'

async def click_text(page, t):
    for exact in (True, False):
        loc = page.get_by_text(t, exact=exact)
        n = await loc.count()
        for i in range(min(n, 40)):
            el = loc.nth(i)
            try:
                if await el.is_visible():
                    await el.scroll_into_view_if_needed(timeout=3000)
                    await el.click(timeout=5000)
                    return f'ok (exact={exact}, {i+1}/{n})'
            except Exception as e:
                last = str(e)[:120]
    return 'НЕ НАЙДЕНО'

async def main():
    lines = [l.strip() for l in open('request.txt', encoding='utf-8') if l.strip() and not l.startswith('#')]
    seen, index = set(), []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(locale='ru-RU', viewport={'width': 1366, 'height': 900},
                                  user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36')
        page = await ctx.new_page()
        follow = None
        for l in lines:
            cmd, _, arg = l.partition(':')
            cmd = cmd.strip().lower(); arg = arg.strip()
            try:
                if cmd == 'follow':
                    follow = re.compile(arg, re.I); continue
                if cmd == 'open':
                    await page.goto(arg, wait_until='domcontentloaded', timeout=60000)
                    await page.wait_for_timeout(4000)
                    LOG.append(f'open {arg}: ok'); continue
                if cmd == 'click':
                    r = await click_text(page, arg); await page.wait_for_timeout(2500)
                    LOG.append(f'click «{arg}»: {r}'); continue
                if cmd == 'type':
                    await page.keyboard.type(arg, delay=60); await page.wait_for_timeout(2500)
                    LOG.append(f'type «{arg}»: ok'); continue
                if cmd == 'fill':
                    css, _, txt = arg.partition('=>')
                    loc = page.locator(css.strip())
                    n = await loc.count(); done = 'НЕ НАЙДЕНО'
                    for i in range(min(n, 20)):
                        el = loc.nth(i)
                        if await el.is_visible():
                            await el.click(timeout=5000); await el.fill(txt.strip(), timeout=5000); done = f'ok ({i+1}/{n})'; break
                    await page.wait_for_timeout(1500)
                    LOG.append(f'fill «{css.strip()}»: {done}'); continue
                if cmd == 'press':
                    await page.keyboard.press(arg); await page.wait_for_timeout(2500)
                    LOG.append(f'press {arg}: ok'); continue
                if cmd == 'size':
                    w, h = [int(x) for x in arg.lower().split('x')]
                    await page.set_viewport_size({'width': w, 'height': h})
                    LOG.append(f'size {w}x{h}: ok'); continue
                if cmd == 'shot':
                    await page.evaluate('window.scrollTo(0,0)'); await page.wait_for_timeout(800)
                    await page.screenshot(path=f'status/{arg}.png', full_page=True)
                    index.append(f'{arg}.png  {page.url}')
                    LOG.append(f'shot {arg}: ok'); continue
                if cmd == 'wait':
                    await page.wait_for_timeout(int(arg)); continue
                if cmd == 'snap':
                    await scroll(page)
                    text, links = await dump(page)
                    save(arg, page.url, text, links)
                    index.append(f'{arg}.txt  {page.url}  ({len(text)} симв.)')
                    LOG.append(f'snap {arg}: {len(text)} симв.'); continue
            except Exception as e:
                LOG.append(f'{cmd} «{arg}»: ОШИБКА {str(e)[:200]}'); continue
            # иначе — это адрес страницы
            text, links = await grab(page, l)
            seen.add(l)
            save(slug(l), l, text, links)
            index.append(f'{slug(l)}.txt  {l}  ({len(text)} симв.)')
            if follow:
                host = urlparse(l).netloc
                extra = [h for h, t in links if urlparse(h).netloc.endswith(host.replace('www.', '')) and follow.search(h + ' ' + t)]
                for h in list(dict.fromkeys(extra))[:12]:
                    if h in seen: continue
                    seen.add(h)
                    t2, l2 = await grab(page, h)
                    save(slug(h), h, t2, l2)
                    index.append(f'{slug(h)}.txt  {h}  ({len(t2)} симв.)  [по ссылке с {l}]')
                follow = None
        await b.close()
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    open('status/_index.txt', 'w', encoding='utf-8').write(f'{now}\n' + '\n'.join(index) + '\n\n--- ЖУРНАЛ ---\n' + '\n'.join(LOG) + '\n')
    print('\n'.join(index)); print('\n'.join(LOG))

asyncio.run(main())
