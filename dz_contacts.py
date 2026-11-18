#!/usr/bin/env python3
"""Открытые контакты студий и дизайнеров: поиск Google (запасной — DuckDuckGo) → сайт, taplink, Zoon, t.me, VK.
Вход: dz/q.txt — строки «код|запрос|сайт|приметы через запятую» (запрос может быть пустым — тогда только сайт).
Части: python dz_contacts.py <номер части> <всего частей>. Выход — status/dz/part-<n>.json, зашифрован ключом dz/key.pub
(X25519 + HKDF + ChaCha20-Poly1305), и короткий status/dz/part-<n>.txt без имён — сколько сделано."""
import base64, json, os, random, re, sys, time, urllib.parse
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from playwright.sync_api import sync_playwright

PART, PARTS = int(sys.argv[1]), int(sys.argv[2])
OUT = "status/dz"
os.makedirs(OUT, exist_ok=True)
INFO = b"dz-contacts-v1"
PK = base64.b64decode(open("dz/key.pub").read().strip())

SKIP = ("avito.", "youtube.", "youtu.be", "google.", "yandex.", "ya.ru", "pinterest.", "wikipedia.", "hh.ru", "rusprofile.",
        "list-org.", "checko.", "zachestnyibiznes", "sbis.ru", "audit-it", "instagram.", "facebook.", "tiktok.", "rutube.",
        "ozon.", "wildberries.", "cian.", "domclick.", "dzen.ru", "ok.ru", "bing.", "duckduckgo.", "microsoft.", "apple.",
        "orgpage.", "spark-interfax", "nalog.", "egrul", "vbankcenter", "companies.rbc", "kartoteka", "focus.kontur",
        "2gis.", "mail.ru", "otzovik", "irecommend", "pikabu", "reddit", "livejournal", "telegra.ph", "tgstat", "telemetr")
CAPTCHA = re.compile(r"/sorry/|unusual traffic|необычный трафик|я не робот|are you a robot|verify you are human|captcha", re.I)
SPB = re.compile(r"санкт[- ]петербург|петербург|\bспб\b|\bspb\b|saint[- ]petersburg|st\.? ?petersburg|ленинградская обл", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,12}")
PHONE = re.compile(r"(?<!\d)(?:\+7|8)[\s\-‑ (]*\d{3}[\s\-‑ )]*\d{3}[\s\-‑ ]*\d{2}[\s\-‑ ]*\d{2}(?!\d)")
BAD_MAIL = re.compile(r"\.(png|jpe?g|gif|webp|svg|css|js)$|sentry|wixpress|example\.|domain\.|email\.com|yourmail|@2x|"
                      r"u00|noreply|no-reply|tilda\.|mysite|site\.ru$|mail@mail|test@|name@|ivanov@", re.I)


def seal(payload):
    eph = X25519PrivateKey.generate()
    epk = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO + epk + PK).derive(
        eph.exchange(X25519PublicKey.from_public_bytes(PK)))
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, json.dumps(payload, ensure_ascii=False).encode(), INFO)
    b = lambda x: base64.b64encode(x).decode()  # noqa: E731
    return {"v": 1, "part": PART, "epk": b(epk), "nonce": b(nonce), "ct": b(ct)}


def unwrap(h):
    """Ссылка-переадресация (Google /url, DDG uddg, Zoon redirect, VK away) → настоящий адрес."""
    try:
        p = urllib.parse.urlparse(h)
        for k, vs in urllib.parse.parse_qs(p.query).items():
            for v in vs:
                if v.startswith("http") and k in ("q", "url", "u", "to", "uddg", "target", "link", "redirect", "href"):
                    return v
    except Exception:
        pass
    return h


def host(u):
    try:
        return urllib.parse.urlparse(u).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def norm_phone(s):
    d = re.sub(r"\D", "", s)
    if len(d) == 11 and d[0] in "78":
        return "+7" + d[1:]
    return ""


def contacts(text, links):
    links = [unwrap(x) for x in links]
    em, ph, tg, wa, vk, mx, ig, other = set(), set(), set(), set(), set(), set(), set(), set()
    for x in links:
        lx = x.lower()
        if lx.startswith("mailto:"):
            em.add(urllib.parse.unquote(x[7:].split("?")[0]).strip())
        elif lx.startswith("tel:"):
            n = norm_phone(x[4:])
            if n:
                ph.add(n)
        m = re.search(r"(?:t\.me|telegram\.me)/(\+?[A-Za-z0-9_]{4,64})", x)
        if m and m.group(1).lower() not in ("share", "joinchat", "s", "iv", "addstickers", "proxy"):
            tg.add("t.me/" + m.group(1))
        m = re.search(r"(?:wa\.me/|whatsapp\.com/send/?\?phone=|whatsapp://send\?phone=)\+?(\d{10,13})", x)
        if m:
            wa.add(m.group(1))
        m = re.search(r"(?:^|//)(?:m\.)?vk\.(?:com|ru)/([A-Za-z0-9_.]{3,64})(?:[/?#]|$)", x)
        if m and m.group(1).lower() not in ("share.php", "away.php", "widget_community.php", "js", "images", "doc", "video",
                                             "wall", "feed", "login", "join", "app", "dev", "about", "support", "terms",
                                             "legal", "blog", "jobs", "safety", "privacy", "photo"):
            vk.add("vk.com/" + m.group(1))
        m = re.search(r"(?:^|//)max\.ru/([A-Za-z0-9_./-]{3,80})", x)
        if m:
            mx.add("max.ru/" + m.group(1).rstrip("/"))
        m = re.search(r"instagram\.com/([A-Za-z0-9_.]{2,40})", x)
        if m and m.group(1).lower() not in ("p", "explore", "accounts", "reel", "stories", "direct"):
            ig.add(m.group(1))
        h = host(x)
        if any(t in h for t in ("taplink", "linktr.ee", "mssg.me", "hipolink", "behance.", "houzz.", "profi.ru", "yell.ru",
                                "zoon.ru", "flamp.ru")):
            other.add(x[:160])
    for m in EMAIL.findall(text):
        em.add(m)
    for m in PHONE.findall(text):
        n = norm_phone(m)
        if n:
            ph.add(n)
    em = {e.strip(".").lower() for e in em if not BAD_MAIL.search(e) and EMAIL.fullmatch(e.strip("."))}
    c = {"email": sorted(em)[:6], "phone": sorted(ph)[:6], "tg": sorted(tg)[:4], "wa": sorted(wa)[:3], "vk": sorted(vk)[:4],
         "max": sorted(mx)[:3], "ig": sorted(ig)[:3], "other": sorted(other)[:4]}
    return {k: v for k, v in c.items() if v}


def hits(text, toks):
    low = text.lower()
    return [t for t in toks if t and t in low]


JS_PAGE = """() => ({title: document.title || '', text: document.body ? document.body.innerText.slice(0, 150000) : '',
  links: [...document.querySelectorAll('a[href]')].map(a => a.href).slice(0, 1500),
  contact: [...document.querySelectorAll('a[href]')].filter(a => /контакт|contact|связаться|kontakt/i.test((a.innerText||'') + ' ' + a.getAttribute('href'))).map(a => a.href).slice(0, 5),
  html: (document.documentElement.innerHTML.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,12}/g) || []).slice(0, 40)})"""
JS_GOOGLE = """() => { const out = [], seen = new Set();
  for (const a of document.querySelectorAll('#search a:has(h3), #rso a:has(h3), a:has(h3)')) {
    if (seen.has(a.href)) continue; seen.add(a.href);
    const b = a.closest('div.MjjYud, div.g, div[data-hveid]') || a.parentElement;
    out.push({u: a.href, t: a.querySelector('h3').innerText, s: (b ? b.innerText : '').replace(/\\s+/g, ' ').slice(0, 320)}); }
  return {res: out.slice(0, 10), text: document.body ? document.body.innerText.slice(0, 20000) : ''}; }"""
JS_DDG = """() => ({res: [...document.querySelectorAll('.result')].map(r => { const a = r.querySelector('a.result__a');
  return a ? {u: a.href, t: a.innerText, s: ((r.querySelector('.result__snippet') || {}).innerText || '').slice(0, 320)} : null; })
  .filter(Boolean).slice(0, 10), text: document.body ? document.body.innerText.slice(0, 20000) : ''})"""


def main():
    rows = []
    for i, line in enumerate(l for l in open("dz/q.txt", encoding="utf-8") if l.strip() and not l.startswith("#")):
        if i % PARTS == PART:
            code, q, site, toks = (line.rstrip("\n").split("|") + ["", "", ""])[:4]
            rows.append((code.strip(), q.strip(), site.strip(), [t.strip().lower() for t in toks.split(",") if t.strip()]))
    out, log = [], []
    google_ok = True
    t0 = time.time()
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel="chrome", headless=True, args=["--disable-blink-features=AutomationControlled"])
        tmp = br.new_page()
        ua = tmp.evaluate("navigator.userAgent").replace("HeadlessChrome", "Chrome")
        tmp.close()
        ctx = br.new_context(locale="ru-RU", timezone_id="Europe/Moscow", viewport={"width": 1280, "height": 1400}, user_agent=ua,
                             extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5"})
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        page.set_default_timeout(25000)

        def load(u, wait=1.2):
            page.goto(u, wait_until="domcontentloaded", timeout=25000)
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass
            time.sleep(wait)

        def fetch(u, toks):
            rec = {"u": u[:200]}
            try:
                load(u)
                d = page.evaluate(JS_PAGE)
                rec["final"] = page.url[:200]
                rec["title"] = d["title"][:90]
                txt = d["title"] + "\n" + d["text"]
                rec["hit"] = hits(txt, toks)
                rec["spb"] = bool(SPB.search(txt))
                rec["c"] = contacts(txt + "\n" + " ".join(d["html"]), d["links"])
                rec["contact_links"] = [x for x in d["contact"] if host(x) == host(page.url)][:2]
                if len(d["text"]) < 300:
                    rec["short"] = d["text"][:200]
            except Exception as e:
                rec["err"] = str(e).split("\n")[0][:120]
            return rec

        for n, (code, q, site, toks) in enumerate(rows, 1):
            item = {"code": code, "q": q, "site": site, "res": [], "pages": []}
            if q:
                eng = "google" if google_ok else "ddg"
                url = (f"https://www.google.com/search?q={urllib.parse.quote(q)}&hl=ru&gl=ru&num=10" if eng == "google"
                       else f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}&kl=ru-ru")
                try:
                    load(url, 1.5)
                    d = page.evaluate(JS_GOOGLE if eng == "google" else JS_DDG)
                    if eng == "google" and (CAPTCHA.search(page.url) or (not d["res"] and CAPTCHA.search(d["text"][:3000]))):
                        google_ok = False
                        log.append(f"{n}: google капча → ddg")
                        eng = "ddg"
                        load(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}&kl=ru-ru", 1.5)
                        d = page.evaluate(JS_DDG)
                    item["eng"] = eng
                    for r in d["res"]:
                        u = unwrap(r["u"])
                        if not u.startswith("http"):
                            continue
                        item["res"].append({"u": u[:200], "t": r["t"][:100], "s": r["s"][:320],
                                            "hit": hits(r["t"] + " " + r["s"], toks), "c": contacts(r["s"], [])})
                except Exception as e:
                    item["err"] = str(e).split("\n")[0][:120]
                time.sleep(random.uniform(6, 11))
            # что открыть: сайт из списка, потом найденное (свой сайт, taplink, t.me, vk, zoon…) — до 5 страниц
            cand, seen_hosts = [], set()
            if site:
                cand.append("https://" + site.removeprefix("https://").removeprefix("http://").strip("/") + "/")
            for r in item["res"]:
                h = host(r["u"])
                if not h or any(s in h for s in SKIP):
                    continue
                key = h if not any(x in h for x in ("t.me", "vk.com", "vk.ru", "taplink", "zoon.ru", "yell.ru", "houzz", "behance",
                                                       "profi.ru", "linktr.ee")) else r["u"]
                if key in seen_hosts:
                    continue
                if not r["hit"] and not any(x in h for x in ("t.me", "taplink", "linktr.ee")):
                    continue                     # без примет в заголовке и описании — скорее всего не тот
                seen_hosts.add(key)
                cand.append(r["u"])
            done = set()
            for u in cand[:5]:
                if u in done:
                    continue
                done.add(u)
                rec = fetch(u, toks)
                item["pages"].append(rec)
                for cu in rec.get("contact_links", [])[:1]:
                    if cu not in done and len(item["pages"]) < 7:
                        done.add(cu)
                        r2 = fetch(cu, toks)
                        r2["from"] = "contacts"
                        item["pages"].append(r2)
                # с найденных страниц — taplink/t.me, на которые ссылается свой сайт
                for extra in (rec.get("c", {}).get("other", []) + [("https://" + t) for t in rec.get("c", {}).get("tg", [])[:1]]):
                    if "taplink" in extra or "linktr.ee" in extra or "t.me/" in extra:
                        if extra not in done and len(item["pages"]) < 7:
                            done.add(extra)
                            r3 = fetch(extra, toks)
                            r3["from"] = "link"
                            item["pages"].append(r3)
            out.append(item)
            npages = len(item["pages"])
            log.append(f"{n}/{len(rows)} {item.get('eng', '-')} рез {len(item['res'])} стр {npages} {int(time.time() - t0)}с")
            print(log[-1], flush=True)
            json.dump(seal({"items": out, "log": log}), open(f"{OUT}/part-{PART}.json", "w"))
            open(f"{OUT}/part-{PART}.txt", "w").write(datetime.now(timezone.utc).strftime("%F %H:%M UTC") + "\n" + "\n".join(log) + "\n")
        br.close()


if __name__ == "__main__":
    main()
