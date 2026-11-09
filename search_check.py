#!/usr/bin/env python3
"""Где nashdekor.ru виден в поиске: Яндекс, Google, Bing, DuckDuckGo, Рамблер, Mail.ru, Brave, Startpage,
Яндекс Карты, 2ГИС. Открывает выдачу настоящим Chrome (Playwright), ищет сайт в результатах,
кладёт отчёт в status/search.md, тексты страниц в status/search/*.txt и скриншоты в status/search/*.jpg."""
import base64, json, os, random, re, subprocess, sys, time, urllib.parse, urllib.request

from playwright.sync_api import sync_playwright

SITE = "nashdekor.ru"
OUT = "status/search"
os.makedirs(OUT, exist_ok=True)

ENG = {
    "yandex":    "https://yandex.ru/search/?text={q}&lr=2",
    "yandexcom": "https://yandex.com/search/?text={q}&lr=2",
    "google":    "https://www.google.com/search?q={q}&hl=ru&gl=ru&num=20",
    "bing":      "https://www.bing.com/search?q={q}&setlang=ru&cc=RU&count=20",
    "ddg":       "https://html.duckduckgo.com/html/?q={q}&kl=ru-ru",
    "startpage": "https://www.startpage.com/sp/search?query={q}&language=russian",
    "brave":     "https://search.brave.com/search?q={q}&source=web",
    "rambler":   "https://nova.rambler.ru/search?query={q}",
    "mailru":    "https://go.mail.ru/search?q={q}",
}
SITEQ = f"site:{SITE}"
JOBS = [(e, SITEQ) for e in ENG]                       # индексация — везде
JOBS += [(e, SITE) for e in ("yandex", "google", "bing")]  # просто адрес
BRAND = ["Наш декор СПб", "Наш декор реечные панели", "nashdekor"]
COMM = ["реечные панели под покраску спб", "дюрополимерные панели спб", "артдек панели купить спб",
        "молдинги под покраску купить спб", "плинтус дюрополимер спб", "реечная панель A907"]
for q in BRAND + COMM:
    for e in ("yandex", "google", "bing"):
        JOBS.append((e, q))
for q in BRAND[:1] + COMM[:2]:
    JOBS.append(("rambler", q))
EXTRA = [
    ("ymaps", "Наш декор", "https://yandex.ru/maps/2/saint-petersburg/search/%D0%9D%D0%B0%D1%88%20%D0%B4%D0%B5%D0%BA%D0%BE%D1%80/"),
    ("ymaps", "стеновые панели наш декор", "https://yandex.ru/maps/2/saint-petersburg/search/%D1%81%D1%82%D0%B5%D0%BD%D0%BE%D0%B2%D1%8B%D0%B5%20%D0%BF%D0%B0%D0%BD%D0%B5%D0%BB%D0%B8%20%D0%BD%D0%B0%D1%88%20%D0%B4%D0%B5%D0%BA%D0%BE%D1%80/"),
    ("2gis", "Наш декор", "https://2gis.ru/spb/search/%D0%9D%D0%B0%D1%88%20%D0%B4%D0%B5%D0%BA%D0%BE%D1%80"),
    ("ywm", "siteinfo", f"https://webmaster.yandex.ru/siteinfo/?site=https://{SITE}"),
]

ENGINE_HOSTS = ("yandex.", "ya.ru", "google.", "gstatic.", "bing.", "microsoft.", "msn.", "duckduckgo.", "startpage.",
                "brave.", "rambler.", "mail.ru", "vk.com/away", "2gis.", "youtube.com/redirect")
CAPTCHA = re.compile(r"showcaptcha|captcha|/sorry/|unusual traffic|необычный трафик|я не робот|are you a robot|"
                     r"подтвердите, что запросы|verify you are human|anomaly", re.I)
NOTHING = re.compile(r"ничего не нашл|не найдено|ничего не найдено|did not match any|no results found|"
                     r"по вашему запросу ничего|нет результатов|There are no results|Не нашлось", re.I)


def real_url(h):
    try:
        p = urllib.parse.urlparse(h)
        qs = urllib.parse.parse_qs(p.query)
        if "bing.com" in p.netloc and p.path.startswith("/ck/a") and "u" in qs:
            u = qs["u"][0]
            if u.startswith("a1"):
                u = u[2:]
                return base64.urlsafe_b64decode(u + "=" * (-len(u) % 4)).decode("utf-8", "replace")
        if "duckduckgo.com" in p.netloc and "uddg" in qs:
            return qs["uddg"][0]
        if "google." in p.netloc and p.path == "/url" and "q" in qs:
            return qs["q"][0]
        if "url" in qs and qs["url"][0].startswith("http"):
            return qs["url"][0]
    except Exception:
        pass
    return h


def organic(links):
    seen, res = set(), []
    for l in links:
        u = real_url(l["h"])
        if not u.startswith("http"):
            continue
        host = urllib.parse.urlparse(u).netloc.lower()
        if any(x in host for x in ENGINE_HOSTS) or not host:
            continue
        if host in seen:
            continue
        seen.add(host)
        res.append((host, u, l["t"][:90]))
    return res


def run():
    rep = [f"# Сайт {SITE} в поиске — {time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC", ""]
    # сайт сам: метки вебмастеров и счётчики
    try:
        html = urllib.request.urlopen(urllib.request.Request(f"https://{SITE}/", headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode("utf-8", "replace")
    except Exception as e:
        html = ""
        rep.append(f"главная не открылась: {e}")
    def has(p):
        m = re.search(p, html, re.I)
        return m.group(0)[:120] if m else "нет"
    checks = [
        ("yandex-verification", r'<meta[^>]+yandex-verification[^>]*>'),
        ("google-site-verification", r'<meta[^>]+google-site-verification[^>]*>'),
        ("msvalidate (Bing)", r'<meta[^>]+msvalidate[^>]*>'),
        ("Яндекс Метрика", r'mc\.yandex\.ru[^"\' ]*'),
        ("Google Analytics/Tag", r'googletagmanager|google-analytics'),
        ("ссылка на Яндекс Карты/Бизнес", r'yandex\.ru/(maps|profile)[^"\' ]*'),
        ("ссылка на 2ГИС", r'2gis\.ru[^"\' ]*'),
        ("ссылка на Авито", r'avito\.ru[^"\' ]*'),
    ]
    rep += ["## Метки на главной", "```"] + [f"{k}: {has(v)}" for k, v in checks] + ["```", ""]
    try:
        import socket
        s = socket.create_connection(("whois.tcinet.ru", 43), timeout=20)
        s.sendall((SITE + "\r\n").encode())
        w = b""
        while True:
            d = s.recv(4096)
            if not d:
                break
            w += d
        w = w.decode("utf-8", "replace")
        rep += ["## Домен", "```"] + [l for l in w.splitlines() if re.match(r"\s*(created|paid-till|state|nserver)", l)] + ["```", ""]
    except Exception as e:
        rep.append(f"whois: {e}")

    rows, details = [], []
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel="chrome", headless=True, args=["--disable-blink-features=AutomationControlled"])
        tmp = br.new_page()
        ua = tmp.evaluate("navigator.userAgent").replace("HeadlessChrome", "Chrome")
        tmp.close()
        ctx = br.new_context(locale="ru-RU", timezone_id="Europe/Moscow", viewport={"width": 1280, "height": 1600},
                             user_agent=ua,
                             extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5"})
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        jobs = [(e, q, ENG[e].format(q=urllib.parse.quote(q))) for e, q in JOBS] + EXTRA
        for n, (e, q, url) in enumerate(jobs, 1):
            tag = f"{n:02d}_{e}"
            st, cnt, pos, top, text, final = "ok", "", "", [], "", url
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                time.sleep(1.5)
                final = page.url
                text = page.evaluate("document.body ? document.body.innerText : ''")
                html = page.content()
                links = page.evaluate("[...document.querySelectorAll('a[href]')].map(a=>({h:a.href,t:(a.innerText||'').trim().replace(/\\s+/g,' ')}))")
                page.screenshot(path=f"{OUT}/{tag}.jpg", type="jpeg", quality=45, full_page=False)
                if CAPTCHA.search(final) or (len(text) < 1500 and CAPTCHA.search(text)):
                    st = "КАПЧА"
                elif NOTHING.search(text[:4000]) and SITE not in html:
                    st = "ничего не найдено"
                org = organic(links)
                top = org[:12]
                hits = [i + 1 for i, (h, u, t) in enumerate(org) if SITE in h]
                pos = str(hits[0]) if hits else ("—" if st == "ok" else "")
                m = re.search(r"(Результатов|результатов|Нашлось|нашлось|About|Около|около)[^\n]{0,40}?\d[\d\s,.]*(тыс\.|млн)?[^\n]{0,25}", text)
                cnt = m.group(0).strip()[:60] if m else ""
                mentions = html.count(SITE)
                pages = sorted({real_url(l["h"]) for l in links if SITE in real_url(l["h"])})
            except Exception as ex:
                st, mentions, pages = f"ошибка: {str(ex)[:80]}", 0, []
            rows.append(f"| {n} | {e} | {q} | {st} | {pos} | {mentions} | {cnt} |")
            details += [f"### {n}. {e} — «{q}» — {st}", f"адрес: {final[:160]}", f"скрин: {tag}.jpg", ""]
            if pages:
                details += ["страницы сайта в выдаче:"] + [f"- {p}" for p in pages[:25]] + [""]
            if top:
                details += ["первые сайты в выдаче:"] + [f"{i+1}. {h} — {t}" for i, (h, u, t) in enumerate(top)] + [""]
            with open(f"{OUT}/{tag}.txt", "w") as f:
                f.write(f"{final}\n\n{text[:6000]}")
            print(rows[-1], flush=True)
            time.sleep(random.uniform(3, 6))
        br.close()
    rep += ["## Выдача", "", "| № | поисковик | запрос | статус | место сайта | упоминаний nashdekor.ru на странице | найдено |",
            "|---|---|---|---|---|---|---|"] + rows + ["", "## Подробно", ""] + details
    open("status/search.md", "w").write("\n".join(rep))


if __name__ == "__main__":
    run()
