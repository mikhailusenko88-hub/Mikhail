#!/bin/bash
# «Кот Барсик»: разовый вход в YouTube-канал для выкладки серий из студии GitHub. Ничего не ставит и не трогает (VPN, боты — как были).
# Запуск на первом сервере (89.126.192.214) — с iPhone командой «Сервер»:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/studio/barsik-login.sh | bash
# 1-й запуск — покажет код для google.com/device. Код вводит ВЛАДЕЛЕЦ канала (не «менеджер»: менеджеров YouTube к API не пускает).
# После «Разрешить» запустить ещё раз — покажет строку для секрета GitHub BARSIK_YT.
# Начать вход заново:  ... | bash -s -- --again
set -u
D=/root/barsik-login
mkdir -p "$D" && chmod 700 "$D"
[ "${1:-}" = "--again" ] && rm -f "$D/token.json" "$D/login.json"
cat > "$D/login.py" <<'PY'
import base64, hashlib, json, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

D = Path("/root/barsik-login")
TOKEN, LOGIN = D / "token.json", D / "login.json"
SCOPE = "https://www.googleapis.com/auth/youtube"
CHANNEL_ID = "UCe72zB7nk8xkf3cHFL15luA"   # @cartoon_friend3 «Кот Барсик»
CMD = "curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/studio/barsik-login.sh | bash"


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def client():
    for f in [Path("/root/kz-bot/yt_token.json")] + sorted(Path("/root/kz-bot").glob("client_secret*.json")):
        try:
            d = json.loads(f.read_text())
            d = d.get("installed") or d.get("web") or d
            if d.get("client_id") and d.get("client_secret"):
                return d["client_id"], d["client_secret"]
        except Exception:
            pass
    sys.exit("Не нашёл ключ Google бота «Білесің бе?» в /root/kz-bot")


def channel(tok):
    t = post("https://oauth2.googleapis.com/token", {"client_id": tok["client_id"], "client_secret": tok["client_secret"],
             "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
    if "access_token" not in t:
        return None
    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                                 headers={"Authorization": "Bearer " + t["access_token"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.loads(r.read()).get("items", [])
    return (items[0]["id"], items[0]["snippet"]["title"]) if items else ("", "")


def wait():
    d = json.loads(LOGIN.read_text())
    iv = d["interval"]
    while time.time() < d["deadline"]:
        time.sleep(iv)
        t = post("https://oauth2.googleapis.com/token", {"client_id": d["cid"], "client_secret": d["sec"],
                 "device_code": d["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        e = t.get("error")
        if e == "authorization_pending":
            continue
        if e == "slow_down":
            iv += 5
            continue
        if "refresh_token" in t:
            TOKEN.write_text(json.dumps({"client_id": d["cid"], "client_secret": d["sec"], "refresh_token": t["refresh_token"]}))
            TOKEN.chmod(0o600)
        LOGIN.unlink(missing_ok=True)
        return
    LOGIN.unlink(missing_ok=True)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--wait":
        return wait()
    if TOKEN.exists():
        tok = json.loads(TOKEN.read_text())
        ch = channel(tok)
        if ch is None:
            print("Вход устарел. Начать заново:  " + CMD + " -s -- --again")
            return
        cid, title = ch
        if cid != CHANNEL_ID:
            TOKEN.unlink()
            print(f"Вход сделан в канал «{title or 'без канала'}», а нужен «Кот Барсик».")
            print("Скорее всего, код ввели с аккаунта менеджера. Нужен аккаунт ВЛАДЕЛЬЦА канала.")
            print("Запусти команду ещё раз — будет новый код.")
            return
        raw = json.dumps(tok, separators=(",", ":")).encode()
        s = "BK1:" + base64.b64encode(raw).decode() + ":" + hashlib.sha256(raw).hexdigest()[:8] + ":END"
        print(f"✅ Вход сделан: канал «{title}».")
        print("Скопируй ВСЕ строки ниже (от BK1 до END) и вставь в GitHub: секрет BARSIK_YT.\n")
        rows = [s[i:i + 24] for i in range(0, len(s), 24)]
        for r in rows:
            print(r)
        print(f"\nПроверь перед тем, как вставлять: строк {len(rows)}, первая начинается с «BK1:», последняя кончается на «END».")
        print("Проще всего скопировать весь этот ответ целиком — лишние слова не мешают.")
        return
    if LOGIN.exists() and time.time() < json.loads(LOGIN.read_text())["deadline"]:
        d = json.loads(LOGIN.read_text())
        print("Жду подтверждения на google.com/device")
        print(f"Код: {d['user_code']}")
        print("После «Разрешить» запусти команду ещё раз.")
        return
    cid, sec = client()
    r = post("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": SCOPE})
    if "device_code" not in r:
        sys.exit(f"Google не выдал код: {r}")
    LOGIN.write_text(json.dumps({"cid": cid, "sec": sec, "device_code": r["device_code"], "user_code": r["user_code"],
                                 "interval": r.get("interval", 5), "deadline": time.time() + r.get("expires_in", 1800)}))
    LOGIN.chmod(0o600)
    with open(D / "login.log", "a") as lf:
        subprocess.Popen([sys.executable, __file__, "--wait"], stdout=lf, stderr=lf, start_new_session=True)
    print(f"1) На телефоне ВЛАДЕЛЬЦА канала открой:  {r['verification_url']}")
    print(f"2) Введи код:  {r['user_code']}")
    print("3) Выбери аккаунт владельца, потом канал «Кот Барсик», нажми «Разрешить»")
    print("   (если «приложение не проверено» — «Дополнительно» → «Перейти…»)")
    print("4) Запусти эту же команду ещё раз — появится строка для GitHub.")
    print("Код действует 30 минут.")


main()
PY
python3 "$D/login.py" "$@"
