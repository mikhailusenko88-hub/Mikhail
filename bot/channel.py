#!/usr/bin/env python3
"""Канал «Наш декор» в MAX: оформление и посты от имени нашего бота.

Бот должен быть администратором канала (права: писать, редактировать, закреплять, менять информацию о канале).
Как только бота добавят в канал, служба prostranstvo-max запомнит канал (настройка max_chats в базе бота).

    python3 channel.py check      — какие каналы видит бот и каких прав не хватает
    python3 channel.py setup      — аватар, название и описание канала
    python3 channel.py publish    — стартовые посты (каждый один раз) и закреп
    python3 channel.py update     — поправить текст и кнопки уже опубликованных постов
    python3 channel.py all        — check + setup + publish
Ключи: --chat ID (если каналов несколько), --dry (только показать), --posts ФАЙЛ,
--links (кнопки — обычные ссылки в браузер, без мини-приложения).

Кнопки на наш сайт открывают сайт внутри MAX (мини-приложение бота): параметр запуска — как в assets/max.js сайта.
Если MAX не примет такие кнопки (мини-приложение не подключено), скрипт сам поставит обычные ссылки.

Только стандартная библиотека Python: запускается системным python3 на сервере. Токен — из /etc/prostranstvo/bot.env,
в вывод не попадает.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from miniapp import app_payload, open_app  # noqa: F401 — app_payload нужен тестам и для проверки ссылок

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = "/etc/prostranstvo/bot.env"
DB_FILE = "/var/lib/prostranstvo/bot.db"
STATE_FILE = "/var/lib/prostranstvo/max_channel.json"
CA_FILE = os.path.join(HERE, "certs", "russian_trusted_ca.pem")
DEFAULT_API = "https://platform-api2.max.ru"
CHATS_KEY = "max_chats"                    # пишет max_api.py, когда бота добавляют в канал или удаляют
NEED = {"write": "публиковать посты", "pin_message": "закреплять", "change_chat_info": "менять аватар и описание",
        "edit": "редактировать посты"}
PAUSE = 1.2                                # между постами, чтобы не упереться в ограничение частоты


class ApiError(Exception):
    def __init__(self, status: int, code: str = "", message: str = "") -> None:
        super().__init__(f"HTTP {status} {code} {message}".strip())
        self.status, self.code, self.message = status, code, message


def read_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


class Api:
    def __init__(self, token: str, base: str, ca_file: str = "") -> None:
        self.token, self.base = token, base.rstrip("/")
        self.ctx = ssl.create_default_context()
        if ca_file and os.path.isfile(ca_file):
            self.ctx.load_verify_locations(cafile=ca_file)

    def call(self, method: str, path: str, params: dict[str, Any] | None = None, body: Any = None) -> dict[str, Any]:
        q = {k: ("true" if v is True else "false" if v is False else v) for k, v in (params or {}).items() if v is not None}
        url = self.base + path + ("?" + urllib.parse.urlencode(q) if q else "")
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        for attempt in range(1, 4):
            req = urllib.request.Request(url, data=data, method=method,
                                         headers={"Authorization": self.token, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60, context=self.ctx) as r:
                    raw = r.read()
                return json.loads(raw or b"{}")
            except urllib.error.HTTPError as e:
                try:
                    j = json.loads(e.read() or b"{}")
                except ValueError:
                    j = {}
                if e.code == 429 and attempt < 3:
                    time.sleep(2 * attempt)
                    continue
                raise ApiError(e.code, str(j.get("code", "")), str(j.get("message", ""))) from None
        raise ApiError(429, "too.many.requests")

    def upload_image(self, img: bytes, name: str) -> dict[str, Any]:
        """Запасной путь, если MAX не забрал картинку по ссылке: загрузить файл и получить токены."""
        up = self.call("POST", "/uploads", {"type": "image"})
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"{name}\"\r\n"
                f"Content-Type: image/jpeg\r\n\r\n").encode() + img + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(up["url"], data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                              "Authorization": self.token})
        with urllib.request.urlopen(req, timeout=120, context=self.ctx) as r:
            res = json.loads(r.read() or b"{}")
        if res.get("photos"):
            return {"photos": res["photos"]}
        if res.get("token") or up.get("token"):
            return {"token": res.get("token") or up.get("token")}
        raise ApiError(500, "upload", "MAX не вернул токен картинки")


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nashdekor-channel"}), timeout=60) as r:
        return r.read()


# ------------------------------------------------------------------------------------------------ данные
def load_posts(path: str) -> dict[str, Any]:
    if path.startswith("http"):
        return json.loads(fetch(path))
    return json.load(open(path, encoding="utf-8"))


def img_url(cfg: dict[str, Any], name: str) -> str:
    url = urllib.parse.urljoin(cfg["img"], name)
    return url + ("&" if "?" in url else "?") + "v=" + str(cfg.get("v", "1"))


def keyboard(rows: list[list[dict[str, str]]], app: str = "") -> list[dict[str, Any]]:
    """Кнопки поста. app — публичное имя бота с мини-приложением: тогда ссылки на сайт открываются внутри MAX."""
    btns = []
    for row in rows or []:
        out = []
        for b in row:
            out.append(open_app(b["text"], b["url"], app) or {"type": "link", "text": b["text"], "url": b["url"]})
        if out:
            btns.append(out)
    return [{"type": "inline_keyboard", "payload": {"buttons": btns}}] if btns else []


def known_chats(db_file: str) -> dict[str, dict[str, Any]]:
    try:
        con = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        row = con.execute("SELECT value FROM settings WHERE key = ?", (CHATS_KEY,)).fetchone()
        con.close()
        return json.loads(row[0]) if row else {}
    except (sqlite3.Error, ValueError):
        return {}


def load_state(path: str) -> dict[str, dict[str, str]]:
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path: str, st: dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------------------ действия
class Channel:
    def __init__(self, api: Api, cfg: dict[str, Any], state_file: str, dry: bool, out=print, app: bool = True) -> None:
        self.api, self.cfg, self.state_file, self.dry, self.out = api, cfg, state_file, dry, out
        self.use_app = app
        self._app: str | None = None if app else ""

    def app(self) -> str:
        """Публичное имя бота (для кнопок мини-приложения); "" — кнопки обычными ссылками."""
        if self._app is None:
            try:
                self._app = str(self.api.call("GET", "/me").get("username") or "")
            except ApiError:
                self._app = ""
        return self._app

    def _no_app(self, e: ApiError) -> bool:
        """MAX не принял кнопки мини-приложения → дальше обычные ссылки. True — есть что повторить."""
        if not self._app:
            return False
        self.out(f"  кнопки мини-приложения MAX не принял ({e}) — ставлю обычные ссылки на сайт. "
                 "Проверьте ссылку мини-приложения в настройках бота.")
        self._app = ""
        return True

    def pick(self, chats: dict[str, dict[str, Any]], wanted: str = "") -> str:
        if wanted:
            return wanted
        active = [cid for cid, c in chats.items() if c.get("active", True) and c.get("channel")]
        if len(active) == 1:
            return active[0]
        if not active:
            raise SystemExit("Бот пока не видит ни одного канала. Добавьте бота «Наш декор» в канал администратором "
                             "и запустите команду ещё раз (или укажите --chat ID канала).")
        raise SystemExit("Бот администратор в нескольких каналах: " + ", ".join(
            f"{cid} «{chats[cid].get('title') or ''}»" for cid in active) + ". Укажите нужный: --chat ID")

    def check(self, chat_id: str) -> list[str]:
        info = self.api.call("GET", f"/chats/{chat_id}")
        me = self.api.call("GET", f"/chats/{chat_id}/members/me")
        perms = set(me.get("permissions") or [])
        self.out(f"Канал: «{info.get('title') or '—'}» (id {chat_id}), подписчиков: {info.get('participants_count', '—')}")
        if not me.get("is_admin"):
            self.out("Бот в канале, но не администратор — сделайте его администратором.")
            return list(NEED)
        missing = [p for p in NEED if p not in perms]
        if missing:
            self.out("Не хватает прав у бота: " + "; ".join(NEED[p] for p in missing))
        else:
            self.out("Права бота — все нужные есть.")
        if self.app():
            self.out(f"Кнопки постов откроют сайт внутри MAX (мини-приложение бота {self.app()}).")
        else:
            self.out("Кнопки постов — обычные ссылки на сайт.")
        return missing

    def setup(self, chat_id: str) -> None:
        ch = self.cfg.get("channel") or {}
        patch: dict[str, Any] = {"notify": False}
        if ch.get("title"):
            patch["title"] = ch["title"]
        if ch.get("description"):
            patch["description"] = ch["description"]
        if ch.get("icon"):
            patch["icon"] = {"url": img_url(self.cfg, ch["icon"])}
        if self.dry:
            self.out("[проверка] оформление: " + json.dumps(patch, ensure_ascii=False)[:300])
            return
        try:
            self.api.call("PATCH", f"/chats/{chat_id}", body=patch)
        except ApiError as e:
            if "icon" not in patch:
                raise
            self.out(f"Аватар по ссылке MAX не принял ({e}) — загружаю файлом")
            patch["icon"] = self.api.upload_image(fetch(patch["icon"]["url"]), "avatar.png")
            self.api.call("PATCH", f"/chats/{chat_id}", body=patch)
        self.out("Оформление канала: название, описание и аватар — готово.")

    def _images(self, names: list[str], uploaded: bool) -> list[dict[str, Any]]:
        out = []
        for n in names:
            url = img_url(self.cfg, n)
            payload = self.api.upload_image(fetch(url), os.path.basename(n)) if uploaded else {"url": url}
            out.append({"type": "image", "payload": payload})
        return out

    def _body(self, post: dict[str, Any], uploaded: bool) -> dict[str, Any]:
        # notify не передаём: MAX отклоняет «тихие» посты в канал (400 errors.send-message.channel-notify)
        return {"text": post["text"], "format": "html",
                "attachments": self._images(post.get("images") or [], uploaded) + keyboard(post.get("buttons") or [], self.app())}

    def _send(self, chat_id: str, post: dict[str, Any]) -> str:
        uploaded = False
        for attempt in range(1, 8):
            body = self._body(post, uploaded)
            try:
                res = self.api.call("POST", "/messages", {"chat_id": chat_id, "disable_link_preview": True}, body)
                return str(((res.get("message") or {}).get("body") or {}).get("mid") or "")
            except ApiError as e:
                if "not.ready" in e.code or "not.ready" in e.message:     # MAX ещё обрабатывает картинки
                    time.sleep(2 * attempt)
                    continue
                if e.status == 400:
                    why = f"{e.code} {e.message}".lower()
                    if "notify" in why:
                        raise
                    if any(k in why for k in ("button", "open_app", "web_app", "keyboard")) and self._no_app(e):
                        continue
                    if post.get("images") and not uploaded:
                        self.out(f"  картинки по ссылке MAX не принял ({e}) — загружаю файлами")
                        uploaded = True
                        continue
                    if self._no_app(e):
                        continue
                raise
        raise ApiError(500, "attachment.not.ready", "картинки так и не обработались")

    def publish(self, chat_id: str) -> int:
        st = load_state(self.state_file)
        done = st.setdefault(chat_id, {})
        n = 0
        posts = self.cfg.get("posts") or []
        for post in posts:
            pid = post["id"]
            if pid in done:
                self.out(f"  «{pid}» — уже опубликован, пропускаю")
                continue
            if self.dry:
                self.out(f"[проверка] пост «{pid}»: {len(post.get('images') or [])} фото, "
                         f"{sum(len(r) for r in post.get('buttons') or [])} кнопок, {len(post['text'])} знаков")
                continue
            mid = self._send(chat_id, post)
            done[pid] = mid
            save_state(self.state_file, st)
            n += 1
            self.out(f"  опубликован «{pid}»")
            time.sleep(PAUSE)
        pin = next((p for p in posts if p.get("pin")), None)
        if pin and done.get(pin["id"]) and not self.dry:
            self.api.call("PUT", f"/chats/{chat_id}/pin", body={"message_id": done[pin["id"]]})   # без notify — см. _body
            self.out(f"  закреплён «{pin['id']}»")
        return n

    def update(self, chat_id: str) -> int:
        st = load_state(self.state_file)
        done = st.get(chat_id, {})
        n = 0
        for post in self.cfg.get("posts") or []:
            mid = done.get(post["id"])
            if not mid:
                continue
            if self.dry:
                self.out(f"[проверка] обновить «{post['id']}»")
                continue
            try:
                self.api.call("PUT", "/messages", {"message_id": mid}, self._body(post, False))
            except ApiError as e:
                if e.status != 400 or not self._no_app(e):
                    raise
                self.api.call("PUT", "/messages", {"message_id": mid}, self._body(post, False))
            n += 1
            self.out(f"  обновлён «{post['id']}»")
            time.sleep(PAUSE)
        return n


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("cmd", choices=["check", "setup", "publish", "update", "all"])
    a.add_argument("--chat", default="")
    a.add_argument("--dry", action="store_true")
    a.add_argument("--posts", default=os.path.join(HERE, "channel_posts.json"))
    a.add_argument("--env", default=ENV_FILE)
    a.add_argument("--db", default=DB_FILE)
    a.add_argument("--state", default=STATE_FILE)
    a.add_argument("--links", action="store_true", help="кнопки — обычные ссылки, без мини-приложения")
    o = a.parse_args(argv)
    env = read_env(o.env)
    token = env.get("MAX_TOKEN") or os.environ.get("MAX_TOKEN", "")
    if not token:
        print(f"Нет токена MAX (MAX_TOKEN в {o.env}).")
        return 2
    api = Api(token, env.get("MAX_API_URL") or DEFAULT_API, env.get("MAX_CA_FILE") or CA_FILE)
    ch = Channel(api, load_posts(o.posts), o.state, o.dry, app=not o.links)
    try:
        chat_id = ch.pick(known_chats(o.db), o.chat)
        if o.cmd in ("check", "all"):
            missing = ch.check(chat_id)
            if o.cmd == "all" and missing and not o.dry:
                print("Дайте боту недостающие права и запустите команду ещё раз.")
                return 3
        if o.cmd in ("setup", "all"):
            ch.setup(chat_id)
        if o.cmd in ("publish", "all"):
            n = ch.publish(chat_id)
            print(f"Опубликовано постов: {n}.")
        if o.cmd == "update":
            print(f"Обновлено постов: {ch.update(chat_id)}.")
    except ApiError as e:
        hint = {401: "MAX не принял токен бота.", 403: "MAX не дал прав: бот не администратор канала или не хватает прав.",
                404: "MAX не нашёл канал — проверьте, что бот в нём, или укажите --chat ID."}.get(e.status, "")
        print(f"Ошибка MAX: {e}. {hint}".strip())
        return 1
    except urllib.error.URLError as e:
        print(f"Нет связи: {e.reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
