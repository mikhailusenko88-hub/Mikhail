"""channel.py: оформление канала и посты от имени бота — на поддельном сервере Bot API (только стандартная библиотека)."""

from __future__ import annotations

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import channel

CHAT = "-7001"


class Fake:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict]] = []
        self.perms = ["write", "edit", "pin_message", "change_chat_info"]
        self.admin = True
        self.not_ready_once = True
        self.reject_url_images = False
        self.n = 0
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # тишина в выводе тестов
                pass

            def _reply(self, code: int, obj) -> None:
                raw = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _do(self, method: str) -> None:
                ln = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(ln) if ln else b""
                path = self.path.split("?")[0]
                body = {}
                if raw and self.headers.get("Content-Type", "").startswith("application/json"):
                    body = json.loads(raw)
                if not path.startswith("/img/") and path != "/upload-target":
                    assert self.headers.get("Authorization") == "TOKEN"
                fake.requests.append((method, self.path, body))
                if path.startswith("/img/"):
                    return self._reply(200, b"\xff\xd8JPEG")
                if method == "GET" and path == f"/chats/{CHAT}":
                    return self._reply(200, {"chat_id": int(CHAT), "type": "channel", "title": "Наш декор", "participants_count": 3})
                if method == "GET" and path == f"/chats/{CHAT}/members/me":
                    return self._reply(200, {"is_admin": fake.admin, "permissions": fake.perms})
                if method == "PATCH" and path == f"/chats/{CHAT}":
                    if fake.reject_url_images and "url" in (body.get("icon") or {}):
                        return self._reply(400, {"code": "bad.request", "message": "icon url"})
                    return self._reply(200, {"chat_id": int(CHAT)})
                if method == "POST" and path == "/messages":
                    imgs = [a for a in body.get("attachments") or [] if a["type"] == "image"]
                    if imgs and fake.not_ready_once:
                        fake.not_ready_once = False
                        return self._reply(400, {"code": "attachment.not.ready", "message": "wait"})
                    if fake.reject_url_images and any("url" in a["payload"] for a in imgs):
                        return self._reply(400, {"code": "bad.request", "message": "image url"})
                    fake.n += 1
                    return self._reply(200, {"message": {"body": {"mid": f"mid.{fake.n}"}}})
                if method == "PUT" and path == f"/chats/{CHAT}/pin":
                    return self._reply(200, {"success": True})
                if method == "PUT" and path == "/messages":
                    return self._reply(200, {"success": True})
                if method == "POST" and path == "/uploads":
                    return self._reply(200, {"url": f"http://127.0.0.1:{fake.port}/upload-target"})
                if method == "POST" and path == "/upload-target":
                    return self._reply(200, {"photos": {"p1": {"token": "TOK"}}})
                return self._reply(404, {"code": "not.found"})

            def do_GET(self):
                self._do("GET")

            def do_POST(self):
                self._do("POST")

            def do_PUT(self):
                self._do("PUT")

            def do_PATCH(self):
                self._do("PATCH")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def calls(self, method: str, path: str) -> list[dict]:
        return [b for m, p, b in self.requests if m == method and p.split("?")[0] == path]


def setup_files(tmp_path, fake: Fake, chats: dict | None = None):
    env = tmp_path / "bot.env"
    env.write_text(f"# токены\nMAX_TOKEN=TOKEN\nMAX_API_URL={fake.url()}\n", encoding="utf-8")
    db = tmp_path / "bot.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    if chats is not None:
        con.execute("INSERT INTO settings VALUES (?, ?)", (channel.CHATS_KEY, json.dumps(chats)))
    con.commit()
    con.close()
    posts = json.load(open(channel.os.path.join(channel.HERE, "channel_posts.json"), encoding="utf-8"))
    posts["img"] = fake.url() + "/img/max/"
    pf = tmp_path / "posts.json"
    pf.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
    return ["--env", str(env), "--db", str(db), "--state", str(tmp_path / "state.json"), "--posts", str(pf)], posts


def test_real_posts_file_is_clean():
    """Стартовые посты: без бренда поставщика, «рамок» и оплаты картой; лимиты MAX соблюдены."""
    d = json.load(open(channel.os.path.join(channel.HERE, "channel_posts.json"), encoding="utf-8"))
    assert len(d["channel"]["description"]) <= 400 and len(d["channel"]["title"]) <= 200
    ids = [p["id"] for p in d["posts"]]
    assert len(ids) == len(set(ids)) and sum(1 for p in d["posts"] if p.get("pin")) == 1
    for p in d["posts"]:
        t = p["text"].lower()
        assert len(p["text"]) <= 4000 and len(p.get("images") or []) <= 10, p["id"]
        for bad in ("artdec", "арт дек", "рамк", "картой", "горюч", "бесплатно", "лучшие цены", "%"):
            assert bad not in t, (p["id"], bad)
        for row in p.get("buttons") or []:
            assert 1 <= len(row) <= 3 and all(b["url"].startswith("https://") for b in row)


def test_all_publishes_once_and_pins(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(channel.time, "sleep", lambda s: None)
    fake = Fake()
    args, posts = setup_files(tmp_path, fake, {CHAT: {"active": True, "channel": True, "by": "Юлия"},
                                               "-9": {"active": False, "channel": True}})
    assert channel.main(["all", *args]) == 0
    out = capsys.readouterr().out
    assert "«Наш декор»" in out and "все нужные есть" in out and f"Опубликовано постов: {len(posts['posts'])}" in out
    patch = fake.calls("PATCH", f"/chats/{CHAT}")[0]
    assert patch["title"] == posts["channel"]["title"] and patch["icon"]["url"].endswith("/img/max/avatar.png?v=1")
    sent = fake.calls("POST", "/messages")
    assert len(sent) == len(posts["posts"]) + 1            # +1: первый раз «картинки ещё обрабатываются»
    first = sent[1]
    assert first["format"] == "html" and first["notify"] is False
    imgs = [a for a in first["attachments"] if a["type"] == "image"]
    assert imgs[0]["payload"]["url"].endswith("/img/max/cover_paint.jpg?v=1")
    kb = [a for a in first["attachments"] if a["type"] == "inline_keyboard"][0]["payload"]["buttons"]
    assert kb[0][0]["type"] == "link" and kb[0][0]["text"] == "Все 18 панелей"
    live = [b for b in sent if "Наши панели в интерьере" in b["text"]][0]
    assert [a for a in live["attachments"] if a["type"] == "image"][0]["payload"]["url"].endswith("/img/live/2x/1.jpg?v=1")
    pin = fake.calls("PUT", f"/chats/{CHAT}/pin")
    assert len(pin) == 1 and pin[0]["message_id"] == f"mid.{len(posts['posts'])}"
    # второй запуск ничего не дублирует
    assert channel.main(["publish", *args]) == 0
    assert len(fake.calls("POST", "/messages")) == len(sent)
    assert "Опубликовано постов: 0" in capsys.readouterr().out
    # правка текста уже опубликованных постов
    assert channel.main(["update", *args]) == 0
    assert len(fake.calls("PUT", "/messages")) == len(posts["posts"])


def test_missing_rights_and_no_channel(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(channel.time, "sleep", lambda s: None)
    fake = Fake()
    fake.perms = ["write"]
    args, _ = setup_files(tmp_path, fake, {CHAT: {"active": True, "channel": True}})
    assert channel.main(["all", *args]) == 3
    out = capsys.readouterr().out
    assert "закреплять" in out and "менять аватар" in out
    assert fake.calls("POST", "/messages") == []
    sub = tmp_path / "x"
    sub.mkdir()
    args2, _ = setup_files(sub, fake, {})
    try:
        channel.main(["check", *args2])
        raise AssertionError("должно было остановиться")
    except SystemExit as e:
        assert "Добавьте бота" in str(e)
    assert channel.main(["check", *args2, "--chat", CHAT]) == 0       # id канала можно указать вручную


def test_dry_run_sends_nothing(tmp_path, capsys):
    fake = Fake()
    args, posts = setup_files(tmp_path, fake, {CHAT: {"active": True, "channel": True}})
    assert channel.main(["all", *args, "--dry"]) == 0
    assert fake.calls("POST", "/messages") == [] and fake.calls("PATCH", f"/chats/{CHAT}") == []
    assert capsys.readouterr().out.count("[проверка] пост") == len(posts["posts"])


def test_images_uploaded_when_url_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(channel.time, "sleep", lambda s: None)
    fake = Fake()
    fake.reject_url_images, fake.not_ready_once = True, False
    args, posts = setup_files(tmp_path, fake, {CHAT: {"active": True, "channel": True}})
    assert channel.main(["all", *args]) == 0
    assert fake.calls("PATCH", f"/chats/{CHAT}")[-1]["icon"] == {"photos": {"p1": {"token": "TOK"}}}
    ok = [b for b in fake.calls("POST", "/messages") if not any("url" in a.get("payload", {}) for a in b["attachments"]
                                                                if a["type"] == "image")]
    assert len(ok) == len(posts["posts"])
    assert len(fake.calls("POST", "/uploads")) == 1 + sum(len(p["images"]) for p in posts["posts"])
    assert "загружаю файлами" in capsys.readouterr().out
