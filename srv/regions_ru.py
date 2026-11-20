# Доступен ли сервер из разных регионов России: Globalping (пробы у людей и в дата-центрах по всей РФ).
# TCP-«пинг» на порты 443 и 22 нашего сервера и, для сравнения, соседа по сети Hoster.kz.
import json, time, urllib.request, collections, sys
API = "https://api.globalping.io/v1"
TARGETS = [("89.126.192.214", 443, "наш сервер :443"), ("89.126.192.214", 22, "наш сервер :22"), ("89.126.192.15", 443, "сосед Hoster.kz :443")]

def req(url, data=None):
    r = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                               headers={"Content-Type": "application/json", "User-Agent": "srv-check"})
    with urllib.request.urlopen(r, timeout=30) as f:
        return json.loads(f.read().decode())

probes = req(API + "/probes")
ru = [p for p in probes if p["location"]["country"] == "RU"]
print(f"Проб Globalping всего: {len(probes)}, в России: {len(ru)}")
cnt = collections.Counter(f'{p["location"]["city"]} — {p["location"].get("network","?")}' for p in ru)
for k, n in sorted(cnt.items()):
    print(f"  {n}× {k}")
sys.stdout.flush()

rows = collections.defaultdict(dict)
for ip, port, name in TARGETS:
    try:
        m = req(API + "/measurements", {"type": "ping", "target": ip, "locations": [{"country": "RU", "limit": 60}],
                                        "measurementOptions": {"packets": 3, "protocol": "TCP", "port": port}})
    except Exception as e:
        print(f"{name}: не удалось запустить ({e})"); continue
    for _ in range(40):
        time.sleep(3)
        res = req(f'{API}/measurements/{m["id"]}')
        if res["status"] != "in-progress":
            break
    for r in res.get("results", []):
        p = r["probe"]; key = f'{p.get("city","?")} ({p.get("state") or p.get("region","")}) — {p.get("network","?")} AS{p.get("asn","")}'
        st = r["result"].get("stats") or {}
        ok = st.get("rcv", 0) > 0
        rows[key][name] = f'ОК {round(st.get("avg") or 0)} мс' if ok else "НЕТ"
    time.sleep(2)

print("\n=== Результат по точкам (регион — сеть: наш :443 | наш :22 | сосед :443)")
yes = 0
for key in sorted(rows):
    v = rows[key]
    a, b, c = (v.get(t[2], "—") for t in TARGETS)
    if a.startswith("ОК") or b.startswith("ОК"): yes += 1
    print(f"{key}: {a} | {b} | {c}")
print(f"\nТочек, откуда НАШ сервер открывается: {yes} из {len(rows)}")
