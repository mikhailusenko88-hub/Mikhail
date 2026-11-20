# Проверка сервера с точек check-host.net (в первую очередь Россия): TCP-порты и HTTP.
import json, sys, time, urllib.request, urllib.parse
IP = "89.126.192.214"
H = {"Accept": "application/json", "User-Agent": "srv-check"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return json.load(r)
def run(kind, target):
    q = urllib.parse.urlencode({"host": target, "max_nodes": 100})
    try:
        req = get(f"https://check-host.net/check-{kind}?{q}")
    except Exception as e:
        print(f"## {kind} {target}: check-host не ответил ({e})"); return
    nodes = req.get("nodes", {})
    rid = req.get("request_id")
    res = {}
    for _ in range(12):
        time.sleep(5)
        try: res = get(f"https://check-host.net/check-result/{rid}")
        except Exception: continue
        if all(v is not None for v in res.values()): break
    print(f"## {kind} {target}")
    rows = []
    for n, info in nodes.items():
        cc, city = info[0], info[2]
        v = res.get(n)
        if v is None: s = "нет данных"
        elif kind == "tcp":
            x = v[0] if v else {}
            s = f"ОК {x['time']*1000:.0f} мс" if isinstance(x, dict) and "time" in x else f"НЕТ ({(x or {}).get('error','?')})"
        else:
            x = v[0] if v and v[0] else None
            s = f"{x[3]} {x[2]} за {x[1]:.1f} с" if x and len(x) > 3 and x[0] == 1 else f"НЕТ ({x[2] if x and len(x)>2 else '?'})"
        rows.append((0 if cc.upper() == "RU" else 1, cc.upper(), city, s))
    for _, cc, city, s in sorted(rows):
        print(f"- {cc} {city}: {s}")
    print()
for kind, t in [("tcp", f"{IP}:22"), ("tcp", f"{IP}:443"), ("tcp", f"{IP}:8443"), ("tcp", f"{IP}:8080"), ("http", f"http://{IP}:8080/mebel/s9kbars/index.html")]:
    run(kind, t)

# Соседи по сети хостера (для сравнения: блок именно нашего IP или всей сети/маршрута)
import os
nb = [l.strip() for l in open("/tmp/neighbors.txt")] if os.path.exists("/tmp/neighbors.txt") else []
nb = [x for x in nb if x and not x.startswith(IP + ":")][:4]
print("=== Соседи по сети хостера:", ", ".join(nb) or "не найдены")
print()
for t in nb + ["hoster.kz:443"]:
    run("tcp", t)
