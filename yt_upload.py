"""Вход в YouTube для бота «Живые строки» (код как у «Білесің бе?»).

Первый вход (один раз):  .venv/bin/python yt_upload.py --setup
  — спросит Client ID и Client secret из Google Cloud,
  — покажет код: открываешь google.com/device на телефоне, вводишь код, «Разрешить».
Проверка:               .venv/bin/python yt_upload.py --check
"""
import json
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
TOKEN = BASE / "yt_token.json"           # сюда сохраняется доступ (никому не отправлять)
SCOPE = "https://www.googleapis.com/auth/youtube"
# с правом на комментарии (первый комментарий под роликом, чтение имён из комментариев)
SCOPES_FULL = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl"]
LOGIN = BASE / "yt_login.json"
TOKEN_URL = "https://oauth2.googleapis.com/token"


# ---------- вход по коду (google.com/device) ----------

def _client_from_file():
    """Ищет скачанный из Google Cloud файл client_secret_*.json рядом с ботом."""
    for f in sorted(BASE.glob("client_secret*.json")):
        try:
            d = json.loads(f.read_text())
            d = d.get("installed") or d.get("web") or d
            if d.get("client_id") and d.get("client_secret"):
                print(f"Беру ключ из файла {f.name}")
                return d["client_id"], d["client_secret"]
        except Exception:
            pass
    return None


def setup():
    found = _client_from_file()
    if found:
        cid, secret = found
    else:
        print("\nВставь данные из Google Cloud (Clients → клиент «TVs and Limited Input»).")
        cid = input("Client ID: ").strip()
        secret = input("Client secret: ").strip()
    r = requests.post("https://oauth2.googleapis.com/device/code",
                      data={"client_id": cid, "scope": SCOPE}, timeout=30).json()
    if "device_code" not in r:
        sys.exit(f"Google не выдал код: {r}\nПроверь, что тип клиента — «TVs and Limited Input devices».")
    print("\n" + "=" * 50)
    print(f"  На телефоне открой:  {r['verification_url']}")
    print(f"  Введи код:           {r['user_code']}")
    print("  Выбери канал «Living Lines» и нажми «Разрешить».")
    print("  (Если Google напишет «приложение не проверено» —")
    print("   «Дополнительные настройки» → «Перейти на страницу…»)")
    print("=" * 50 + "\nЖду подтверждения...")
    interval = r.get("interval", 5)
    deadline = time.time() + r.get("expires_in", 1800)
    while time.time() < deadline:
        time.sleep(interval)
        t = requests.post(TOKEN_URL, data={
            "client_id": cid, "client_secret": secret, "device_code": r["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, timeout=30).json()
        err = t.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        if err:
            sys.exit(f"Ошибка входа: {t}")
        if "refresh_token" not in t:
            sys.exit(f"Google не выдал постоянный доступ: {t}")
        TOKEN.write_text(json.dumps({"client_id": cid, "client_secret": secret,
                                     "refresh_token": t["refresh_token"]}))
        TOKEN.chmod(0o600)
        print("\n✅ Доступ сохранён.")
        check()
        return
    sys.exit("Время на ввод кода вышло. Запусти --setup ещё раз.")


def _creds():
    from google.oauth2.credentials import Credentials
    d = json.loads(TOKEN.read_text())
    return Credentials(None, refresh_token=d["refresh_token"], token_uri=TOKEN_URL,
                       client_id=d["client_id"], client_secret=d["client_secret"],
                       scopes=d.get("scopes") or [SCOPE])


# ---------- вход заново с правом на комментарии — без ожидания в окне (для «Команд» на iPhone) ----------

def login_start():
    """Показывает код для google.com/device и сразу выходит; подтверждение ждёт фоновый процесс."""
    import subprocess
    if TOKEN.exists():
        d = json.loads(TOKEN.read_text())
        cid, secret = d["client_id"], d["client_secret"]
    else:
        found = _client_from_file()
        if not found:
            sys.exit("Нет ключа клиента — запусти --setup")
        cid, secret = found
    # для входа по коду Google разрешает только право «youtube» (выкладка) — без права на комментарии
    r = requests.post("https://oauth2.googleapis.com/device/code",
                      data={"client_id": cid, "scope": SCOPE}, timeout=30).json()
    if "device_code" not in r:
        print(f"Google не выдал код: {r}", flush=True)
        sys.exit(1)
    LOGIN.write_text(json.dumps({"client_id": cid, "client_secret": secret, "device_code": r["device_code"],
                                 "interval": r.get("interval", 5),
                                 "deadline": time.time() + r.get("expires_in", 1800)}))
    LOGIN.chmod(0o600)
    with open(BASE / "bot.log", "a") as lf:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--login-wait"], cwd=str(BASE),
                         stdout=lf, stderr=lf, start_new_session=True)
    print(f"1) Открой на телефоне:  {r['verification_url']}")
    print(f"2) Введи код:  {r['user_code']}")
    print("3) Выбери аккаунт и канал «Living Lines», нажми «Разрешить»")
    print("   (если «приложение не проверено» — «Дополнительно» → «Перейти…»)")
    print("4) Через минуту проверь:  quotes check")
    print("Код действует 30 минут.")


def login_wait():
    d = json.loads(LOGIN.read_text())
    interval = d["interval"]
    while time.time() < d["deadline"]:
        time.sleep(interval)
        t = requests.post(TOKEN_URL, data={
            "client_id": d["client_id"], "client_secret": d["client_secret"], "device_code": d["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, timeout=30).json()
        err = t.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        if err or "refresh_token" not in t:
            print(f"YouTube вход: ошибка {t}", flush=True)
            LOGIN.unlink(missing_ok=True)
            return
        if TOKEN.exists():
            TOKEN.rename(TOKEN.with_name(f"yt_token.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
        TOKEN.write_text(json.dumps({"client_id": d["client_id"], "client_secret": d["client_secret"],
                                     "refresh_token": t["refresh_token"], "scopes": [SCOPE]}))
        TOKEN.chmod(0o600)
        LOGIN.unlink(missing_ok=True)
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  YouTube вход: готово", flush=True)
        try:
            check()
        except SystemExit as e:
            print(e, flush=True)
        return
    print("YouTube вход: время на ввод кода вышло — запусти quotes login ещё раз", flush=True)
    LOGIN.unlink(missing_ok=True)


def _yt():
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    c = _creds()
    c.refresh(Request())
    return build("youtube", "v3", credentials=c, cache_discovery=False)


def check():
    ch = _yt().channels().list(part="snippet", mine=True).execute()
    items = ch.get("items", [])
    if not items:
        sys.exit("Под этим входом нет канала. Запусти quotes login и выбери канал «Living Lines».")
    sn = items[0]["snippet"]
    print(f"Канал для выкладки: {sn['title']} ({sn.get('customUrl', '')})")
    want = json.loads((BASE / "config.json").read_text(encoding="utf-8")).get("channel_name", "Living Lines")
    if want.lower() not in sn["title"].lower():
        print(f"⚠️ Это не «{want}». Запусти quotes login и выбери нужный канал.")


# ---------- загрузка ----------

def upload(path, title, description, tags, cfg):
    from googleapiclient.http import MediaFileUpload
    yt = _yt()
    body = {
        "snippet": {"title": f"{title[:91].rstrip()} #shorts", "description": description[:4900],
                    "tags": list(dict.fromkeys([t for t in tags if t] + cfg.get("yt_extra_tags", ["интересные факты", "почему так", "факты"])))[:15],
                    "categoryId": str(cfg.get("youtube_category_id", "27")),
                    "defaultLanguage": cfg.get("lang", "ru"), "defaultAudioLanguage": cfg.get("lang", "ru")},
        "status": {"privacyStatus": cfg.get("youtube_privacy", "public"),
                   "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024,
                                                        resumable=True, mimetype="video/mp4"))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtube.com/shorts/{resp['id']}"


if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup()
    elif "--check" in sys.argv:
        check()
    elif "--login-start" in sys.argv:
        login_start()
    elif "--login-wait" in sys.argv:
        login_wait()
    else:
        print(__doc__)
