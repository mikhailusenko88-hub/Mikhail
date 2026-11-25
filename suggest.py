#!/usr/bin/env python3
"""Подсказки поиска YouTube по странам (что люди набирают): suggest-request.txt — строки «hl gl запрос». Итог — out_suggest/suggest.json и .md.
Нужно для главного запроса в названиях на языке дубляжа (Франция; Египет и Саудовская Аравия)."""
import json, time, urllib.parse, urllib.request

rows = []
for line in open("suggest-request.txt", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    hl, gl, q = line.split(" ", 2)
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode({"client": "firefox", "ds": "yt", "hl": hl, "gl": gl, "q": q})
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": hl})
            raw = urllib.request.urlopen(req, timeout=20).read()
            try:
                J = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                J = json.loads(raw.decode("latin-1"))
            rows.append({"hl": hl, "gl": gl, "q": q, "s": J[1]})
            break
        except Exception as e:
            err = repr(e)[:200]; time.sleep(2)
    else:
        rows.append({"hl": hl, "gl": gl, "q": q, "error": err})
    time.sleep(0.4)
json.dump(rows, open("out_suggest/suggest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
md = ["# Подсказки поиска YouTube", ""]
for r in rows:
    md.append(f"- **{r['q']}** ({r['hl']}-{r['gl']}): " + (", ".join(r.get("s", [])) or r.get("error", "—")))
open("out_suggest/suggest.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md))
