# Открывает страницы из request.txt в Chromium, ждёт загрузки, прокручивает и сохраняет текст.
# Строка "follow: <regex>" — со следующей страницы дополнительно открыть ссылки, подходящие под regex (до 12).
import re, asyncio, datetime
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

async def grab(page, url):
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(4000)
        for _ in range(12):
            await page.mouse.wheel(0, 1500); await page.wait_for_timeout(400)
        await page.wait_for_timeout(1500)
        text = await page.inner_text('body')
        links = await page.eval_on_selector_all('a[href]', 'els => els.map(e => [e.href, (e.innerText||"").trim().slice(0,80)])')
        return text, links
    except Exception as e:
        return f'ОШИБКА: {e}', []

def slug(u):
    p = urlparse(u); s = (p.netloc + p.path).strip('/').replace('/', '_')
    return re.sub(r'[^A-Za-z0-9_.-]', '-', s)[:90] or 'page'

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
            if l.startswith('follow:'):
                follow = re.compile(l.split(':', 1)[1].strip(), re.I); continue
            queue = [l]
            text, links = await grab(page, l)
            seen.add(l)
            open(f'status/{slug(l)}.txt', 'w', encoding='utf-8').write(f'URL: {l}\n\n{text}\n\n--- ССЫЛКИ ---\n' + '\n'.join(f'{h} | {t}' for h, t in links))
            index.append(f'{slug(l)}.txt  {l}  ({len(text)} симв.)')
            if follow:
                host = urlparse(l).netloc
                extra = [h for h, t in links if urlparse(h).netloc.endswith(host.replace('www.', '')) and follow.search(h + ' ' + t)]
                for h in list(dict.fromkeys(extra))[:12]:
                    if h in seen: continue
                    seen.add(h)
                    t2, l2 = await grab(page, h)
                    open(f'status/{slug(h)}.txt', 'w', encoding='utf-8').write(f'URL: {h}\n\n{t2}\n')
                    index.append(f'{slug(h)}.txt  {h}  ({len(t2)} симв.)  [по ссылке с {l}]')
                follow = None
        await b.close()
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    open('status/_index.txt', 'w', encoding='utf-8').write(f'{now}\n' + '\n'.join(index) + '\n')
    print('\n'.join(index))

asyncio.run(main())
