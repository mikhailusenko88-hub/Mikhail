# Снимает страницы по списку pages/urls.txt (публичные сайты, без секретов) → status/pages/NN.txt + ссылки
import html, os, re, sys, urllib.request, urllib.error, ssl
urls = [u.strip() for u in open('pages/urls.txt', encoding='utf-8') if u.strip() and not u.startswith('#')]
os.makedirs('status/pages', exist_ok=True)
for f in os.listdir('status/pages'):
    os.remove(os.path.join('status/pages', f))
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE   # у части госсайтов сертификат Минцифры
index = ['# Снятые страницы', '']
for n, u in enumerate(urls, 1):
    try:
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15', 'Accept-Language': 'ru'})
        r = urllib.request.urlopen(req, timeout=40, context=ctx)
        raw = r.read(3_000_000); cs = r.headers.get_content_charset()
        if not cs:
            m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', raw[:4000])
            cs = m.group(1).decode() if m else 'utf-8'
        b = raw.decode(cs, 'replace')
        if b.count('\ufffd') > 50:
            b = raw.decode('cp1251', 'replace')
        code = r.status
    except urllib.error.HTTPError as e:
        b, code = e.read(200000).decode('utf-8', 'replace'), e.code
    except Exception as e:
        b, code = '', f'ошибка: {e}'
    links = sorted(set(re.findall(r'href="([^"#]+)"', b)))
    t = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', b)
    t = re.sub(r'(?i)<br\s*/?>|</(p|div|li|tr|h\d|td|th)>', '\n', t)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    t = re.sub(r'[ \t\xa0]+', ' ', t); t = re.sub(r'\n\s*\n+', '\n', t).strip()
    with open(f'status/pages/{n:02d}.txt', 'w', encoding='utf-8') as f:
        f.write(f'URL: {u}\nКОД: {code}\n\n{t[:60000]}\n\nССЫЛКИ:\n' + '\n'.join(links[:400]))
    index.append(f'- {n:02d} {code} {u} ({len(t)} симв.)')
open('status/pages.md', 'w', encoding='utf-8').write('\n'.join(index) + '\n')
print('\n'.join(index))
