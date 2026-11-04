#!/bin/bash
# Flagball Arena: вход в YouTube для выкладки с GitHub. Ничего не ставит и не трогает (VPN, бот — как были).
# Запуск (с iPhone «Сервер» или в Терминале на сервере):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/flagball/fb-login.sh | bash
# 1-й раз — покажет код для google.com/device. После «Разрешить» запусти ещё раз — покажет строку для GitHub.
# Начать вход заново:  ... | bash -s -- --again
set -u
D=/root/flagball-login
mkdir -p "$D" && chmod 700 "$D"
[ "${1:-}" = "--again" ] && rm -f "$D/token.json" "$D/login.json"
cat > "$D/login.py" <<'PY'
import json, os, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

D = Path("/root/flagball-login")
TOKEN, LOGIN = D / "token.json", D / "login.json"
SCOPE = "https://www.googleapis.com/auth/youtube"


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
    return items[0]["snippet"]["title"] if items else ""


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
        title = channel(tok)
        if title is None:
            print("Вход устарел. Запусти с --again")
            return
        if "flagball" not in title.lower():
            TOKEN.unlink()
            print(f"Вход сделан в канал «{title}», а нужен Flagball Arena.")
            print("Запусти команду ещё раз и на шаге выбора канала выбери Flagball Arena.")
            return
        print(f"✅ Вход сделан: канал «{title}».")
        print("Скопируй строку ниже целиком (от { до }) и вставь в GitHub, как скажет Claude:\n")
        print(json.dumps(tok, separators=(",", ":")))
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
    print(f"1) Открой на телефоне:  {r['verification_url']}")
    print(f"2) Введи код:  {r['user_code']}")
    print("3) Выбери аккаунт, потом канал Flagball Arena, нажми «Разрешить»")
    print("   (если «приложение не проверено» — «Дополнительно» → «Перейти…»)")
    print("4) Запусти эту же команду ещё раз — появится строка для GitHub.")
    print("Код действует 30 минут.")


main()
PY
python3 "$D/login.py" "$@"
