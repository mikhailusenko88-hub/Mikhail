#!/usr/bin/env python3
"""IndexNow для nashdekor.ru: сообщает Bing и Яндексу (а через них Naver, Seznam, Yep) о новых и изменённых
страницах сайта. Запускается на каждый push в ветку mebel, который меняет папку 0f7s1eez/ или файл indexnow.txt.
Изменение indexnow.txt (или файла-ключа) — отправить ВСЕ адреса из sitemap.xml."""
import json, os, re, subprocess, time, urllib.request, urllib.error

HOST = "nashdekor.ru"
KEY = os.environ["INDEXNOW_KEY"]
KEY_URL = f"https://{HOST}/{KEY}.txt"
SITE_DIR = "0f7s1eez/"
SKIP = re.compile(r"^(pochta/|google[0-9a-f]+\.html$|yandex_[0-9a-f]+\.html$)")
ENDPOINTS = ["https://www.bing.com/indexnow", "https://yandex.com/indexnow"]
log = []


def say(s):
    print(s, flush=True)
    log.append(s)


def get(url, timeout=30):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nashdekor-indexnow"}), timeout=timeout)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def changed_files():
    before, after = os.environ.get("BEFORE", ""), os.environ.get("AFTER", "HEAD")
    if not before or set(before) == {"0"}:
        return None
    r = subprocess.run(["git", "diff", "--no-renames", "--name-only", before, after], capture_output=True, text=True)
    return r.stdout.split() if r.returncode == 0 else None


def file_to_url(f):
    p = f[len(SITE_DIR):]
    if SKIP.match(p) or not p.endswith(".html"):
        return None
    if p == "index.html":
        return f"https://{HOST}/"
    if p.endswith("/index.html"):
        return f"https://{HOST}/{p[:-len('index.html')]}"
    return f"https://{HOST}/{p}"


files = changed_files()
full = files is None or "indexnow.txt" in files or f"{SITE_DIR}{KEY}.txt" in files
say(f"# IndexNow — {time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC, коммит {os.environ.get('AFTER', '')[:7]}")

# 1) ключ должен открываться на сайте (сервер забирает ветку mebel раз в минуту)
for i in range(40):
    st, body = get(KEY_URL)
    if st == 200 and body.strip() == KEY:
        say(f"- ключ на сайте: {KEY_URL} → 200, совпадает")
        break
    time.sleep(10)
else:
    say(f"- ОШИБКА: ключ не открылся на сайте ({KEY_URL} → {st}); ничего не отправлено")
    raise SystemExit(1)

# 2) какие адреса отправить
if full:
    st, sm = get(f"https://{HOST}/sitemap.xml")
    urls = re.findall(r"<loc>([^<]+)</loc>", sm)
    say(f"- режим: все адреса из sitemap.xml ({len(urls)})")
else:
    urls = sorted({u for u in (file_to_url(f) for f in files if f.startswith(SITE_DIR)) if u})
    say(f"- режим: изменённые страницы ({len(urls)}) из {len(files)} изменённых файлов")
    if urls:
        time.sleep(90)  # дать серверу забрать новую версию
if not urls:
    say("- отправлять нечего (изменились не страницы)")
else:
    for u in urls[:15]:
        say(f"  {u}")
    if len(urls) > 15:
        say(f"  … и ещё {len(urls) - 15}")
    data = json.dumps({"host": HOST, "key": KEY, "keyLocation": KEY_URL, "urlList": urls[:10000]}).encode()
    meaning = {200: "принято, ключ проверен", 202: "принято, ключ ещё проверяется", 400: "ошибка запроса",
               403: "ключ не подошёл", 422: "адреса не с этого сайта", 429: "слишком часто"}
    for ep in ENDPOINTS:
        try:
            r = urllib.request.urlopen(urllib.request.Request(ep, data=data, method="POST",
                                       headers={"Content-Type": "application/json; charset=utf-8"}), timeout=60)
            code, body = r.status, r.read().decode("utf-8", "replace")[:200]
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read().decode("utf-8", "replace")[:200]
        except Exception as e:
            code, body = 0, str(e)[:200]
        say(f"- {ep}: HTTP {code} — {meaning.get(code, '?')} {body.strip()}")

if full:  # заодно проверить файлы подтверждения вебмастеров
    for f in ("google8ff025c950c4f362.html", "yandex_9b48db37dadc94c9.html", "robots.txt"):
        st, _ = get(f"https://{HOST}/{f}")
        say(f"- /{f} → {st}")

out = os.environ.get("STATUS_FILE")
if out:
    old = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    runs = [b for b in old.split("\n\n---\n\n") if b.strip()][:29]
    open(out, "w", encoding="utf-8").write("\n\n---\n\n".join(["\n".join(log)] + runs) + "\n")
