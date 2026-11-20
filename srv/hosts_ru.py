# Открываются ли из России адреса хостеров-кандидатов (check-host.net): список — hosts.txt («имя | адрес»).
import json, socket, time, urllib.request, urllib.parse
H = {"Accept": "application/json", "User-Agent": "hosts-check"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return json.load(r)
def open_port(host):
    for p in (443, 80, 22):
        try:
            socket.create_connection((host, p), timeout=6).close(); return p
        except Exception: pass
    return None
import subprocess
rows = []
for l in open("hosts.txt", encoding="utf-8"):
    if "|" not in l or l.startswith("#"): continue
    name, host = [x.strip() for x in l.split("|", 1)]
    if host.startswith("scan:"):   # scan:CIDR — взять до 2 живых адресов из сети хостера
        out = subprocess.run(["sudo", "nmap", "-Pn", "-n", "-T4", "--max-retries", "1", "-p", "22,443", "--open", host[5:], "-oG", "-"], capture_output=True, text=True, timeout=120).stdout
        ips = [ln.split()[1] for ln in out.splitlines() if "Ports:" in ln][:2]
        rows += [(f"{name} {ip}", ip) for ip in ips] or [(name + " (живых нет)", "0.0.0.0")]
    else:
        rows.append((name, host))
print("Проверка:", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
for name, host in rows:
    name, host = name.strip(), host.strip()
    try: ip = socket.gethostbyname(host)
    except Exception as e: print(f"\n## {name} ({host}): не резолвится {e}"); continue
    p = open_port(ip)
    print(f"\n## {name} — {host} ({ip}), открытый порт из GitHub: {p}")
    if not p: continue
    rid = None
    for a in range(4):
        try:
            rid = get("https://check-host.net/check-tcp?" + urllib.parse.urlencode({"host": f"{ip}:{p}", "max_nodes": 100}))
            break
        except Exception as e:
            time.sleep(20)
    if not rid: print("   check-host не ответил"); continue
    nodes, res = rid["nodes"], {}
    for _ in range(12):
        time.sleep(5)
        try: res = get("https://check-host.net/check-result/" + rid["request_id"])
        except Exception: continue
        if all(v is not None for v in res.values()): break
    for n, info in sorted(nodes.items(), key=lambda kv: (kv[1][0] != "ru", kv[1][0])):
        if info[0].upper() not in ("RU", "KZ", "DE", "FI"): continue
        v = res.get(n); x = v[0] if v else {}
        s = f"ОК {x['time']*1000:.0f} мс" if isinstance(x, dict) and "time" in x else f"НЕТ ({(x or {}).get('error','?') if isinstance(x, dict) else x})"
        print(f"   {info[0].upper()} {info[2]}: {s}")
    time.sleep(15)
