# Резолвятся ли имена бесплатных DDNS из России и открываются ли их сайты (check-host.net). Список — dns.txt
import json, time, urllib.request, urllib.parse
H = {"Accept": "application/json", "User-Agent": "dns-check"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r: return json.load(r)
def run(kind, target):
    for a in range(4):
        try: req = get(f"https://check-host.net/check-{kind}?" + urllib.parse.urlencode({"host": target, "max_nodes": 100})); break
        except Exception: time.sleep(20)
    else: print(f"## {kind} {target}: check-host не ответил"); return
    res = {}
    for _ in range(12):
        time.sleep(5)
        try: res = get("https://check-host.net/check-result/" + req["request_id"])
        except Exception: continue
        if all(v is not None for v in res.values()): break
    print(f"## {kind} {target}")
    for n, info in sorted(req["nodes"].items(), key=lambda kv: kv[1][0] != "ru"):
        if info[0].upper() not in ("RU", "DE"): continue
        v = res.get(n)
        if kind == "dns":
            x = v[0] if v else {}
            s = ("A " + ",".join(x.get("A", []))) if isinstance(x, dict) and x.get("A") else f"НЕТ ({x})"
        else:
            x = v[0] if v and v[0] else None
            s = f"{x[3]} {x[2]}" if x and len(x) > 3 and x[0] == 1 else f"НЕТ ({x[2] if x and len(x)>2 else '?'})"
        print(f"   {info[0].upper()} {info[2]}: {s}")
    print(); time.sleep(12)
for line in open("dns.txt", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#"): continue
    kind, target = line.split(None, 1); run(kind, target)
