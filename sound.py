"""Подробности звука в выбранных роликах: название, исполнитель, ссылка на страницу звука."""
import re, subprocess, json, codecs
ids = [l.strip() for l in open("request.txt", encoding="utf-8").read().split("\n")[2].split(",") if l.strip()]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def get(url):
    return subprocess.run(["curl", "-sL", "--max-time", "25", "-H", "Accept-Language: ru,en;q=0.8", "-H", "Cookie: CONSENT=YES+1; SOCS=CAI", "-A", UA, url],
                          capture_output=True, text=True).stdout
def unesc(s):
    try:
        return codecs.decode(s.replace("\\x", "\\\\x"), "unicode_escape").encode("latin-1", "ignore").decode("utf-8", "ignore")
    except Exception:
        return s
out = []
for vid in ids:
    h = get(f"https://www.youtube.com/shorts/{vid}")
    hu = h.replace("\\x22", '"').replace("\\x7b", "{").replace("\\x7d", "}").replace("\\x5b", "[").replace("\\x5d", "]").replace("\\/", "/")
    rec = {"id": vid}
    i = hu.find("MUSIC_NOTE_SYMBOL")
    ctx = hu[max(0, i - 1500): i + 2500] if i >= 0 else ""
    rec["button"] = re.findall(r'"content":"([^"]{2,200})"', ctx)[:6]
    rec["source"] = sorted(set(re.findall(r'/source/([A-Za-z0-9_-]{11})/shorts', hu)))[:5]
    rec["browse"] = sorted(set(re.findall(r'"browseId":"([^"]+)"', ctx)))[:5]
    rec["urls"] = sorted(set(re.findall(r'"url":"(/[^"]{3,120})"', ctx)))[:8]
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    for s in rec["source"][:1]:
        hs = get(f"https://www.youtube.com/source/{s}/shorts")
        hsu = hs.replace("\\x22", '"').replace("\\/", "/")
        t = re.search(r"<title>(.*?)</title>", hs)
        m = re.findall(r'"(?:title|subtitle|text|content)":"([^"]{2,150})"', hsu)[:40]
        print("  страница звука:", t.group(1) if t else None, "|", m[:25], flush=True)
        hv = get(f"https://www.youtube.com/watch?v={s}")
        t2 = re.search(r"<title>(.*?)</title>", hv)
        d2 = re.search(r'"shortDescription":"(.*?)","', hv)
        ch = re.search(r'"ownerChannelName":"([^"]+)"', hv)
        print("  исходный ролик звука:", t2.group(1) if t2 else None, "| канал:", ch.group(1) if ch else None, "|", (d2.group(1)[:300] if d2 else None), flush=True)
json.dump(out, open("status/sound.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
