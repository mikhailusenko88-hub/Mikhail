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
        self.reject_open_app = False
        self.me_name = "id470331302505_bot"
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
                if method == "GET" and path == "/me":
                    return self._reply(200, {"user_id": 1, "is_bot": True, "username": fake.me_name})
                if method == "GET" and path == f"/chats/{CHAT}":
                    return self._reply(200, {"chat_id": int(CHAT), "type": "channel", "title": "Наш декор", "participants_count": 3})
                if method == "GET" and path == f"/chats/{CHAT}/members/me":
                    return self._reply(200, {"is_admin": fake.admin, "permissions": fake.perms})
                if method == "PATCH" and path == f"/chats/{CHAT}":
                    if fake.reject_url_images and "url" in (body.get("icon") or {}):
                        return self._reply(400, {"code": "bad.request", "message": "icon url"})
                    return self._reply(200, {"chat_id": int(CHAT)})
                if method == "POST" and path == "/messages":
                    if "notify" in body:      # как настоящий MAX: «тихий» пост в канал — ошибка
                        return self._reply(400, {"code": "proto.payload", "message": "errors.send-message.channel-notify"})
                    imgs = [a for a in body.get("attachments") or [] if a["type"] == "image"]
                    if imgs and fake.not_ready_once:
                        fake.not_ready_once = False
                        return self._reply(400, {"code": "attachment.not.ready", "message": "wait"})
                    if fake.reject_url_images and any("url" in a["payload"] for a in imgs):
                        return self._reply(400, {"code": "bad.request", "message": "image url"})
                    kbs = [b for a in body.get("attachments") or [] if a["type"] == "inline_keyboard"
                           for row in a["payload"]["buttons"] for b in row]
                    if fake.reject_open_app and any(b["type"] == "open_app" for b in kbs):
                        return self._reply(400, {"code": "bad.request", "message": "Invalid button: web app is not set"})
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
    assert first["format"] == "html" and "notify" not in first
    imgs = [a for a in first["attachments"] if a["type"] == "image"]
    assert imgs[0]["payload"]["url"].endswith("/img/max/cover_paint.jpg?v=1")
    kb = [a for a in first["attachments"] if a["type"] == "inline_keyboard"][0]["payload"]["buttons"]
    assert kb[0][0] == {"type": "open_app", "text": "Все 18 панелей", "web_app": "id470331302505_bot", "payload": "c-reechnye-paneli"}
    assert kb[1][1] == {"type": "link", "text": "Заказать в MAX", "url": "https://max.ru/id470331302505_bot"}
    assert "мини-приложение бота id470331302505_bot" in out
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


def test_app_payload_matches_site_routes():
    """Параметры запуска — те же, что разбирает assets/max.js на сайте."""
    P = channel.app_payload
    assert P("https://nashdekor.ru/?utm_source=max") == ""
    assert P("https://nashdekor.ru/?utm_source=max#calc") == "calc"
    assert P("https://nashdekor.ru/?utm_source=max&panel=3-7#calc") == "calc-3-7"
    assert P("https://nashdekor.ru/?panel=A907#calc") == "calc-a907"
    assert P("https://nashdekor.ru/?panel=A907&w=320&h=270#calc") == "calc-a907_320_270"
    assert P("https://nashdekor.ru/?utm_source=max#pro") == "pro"
    assert P("https://nashdekor.ru/catalog/plintusy/?utm_source=max") == "c-plintusy"
    assert P("https://nashdekor.ru/p/a907/") == "p-a907"
    assert P("https://nashdekor.ru/stati/moldingi-na-stene-v-interere/?utm_source=max") == "s-moldingi-na-stene-v-interere"
    assert P("https://nashdekor.ru/dostavka/?utm_source=max") == "dostavka"
    assert P("https://max.ru/id470331302505_bot") is None
    assert P("https://nashdekor.ru/?x=1#neizvestno") is None and P("http://nashdekor.ru/") is None
    d = json.load(open(channel.os.path.join(channel.HERE, "channel_posts.json"), encoding="utf-8"))
    for post in d["posts"]:
        for row in post.get("buttons") or []:
            for b in row:
                pl = P(b["url"])
                assert pl is not None or b["url"].startswith("https://max.ru/"), b
                assert pl is None or (len(pl) <= 512 and channel.re.fullmatch(r"[\w-]*", pl)), pl


def test_open_app_rejected_falls_back_to_links(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(channel.time, "sleep", lambda s: None)
    fake = Fake()
    fake.reject_open_app, fake.not_ready_once = True, False
    args, posts = setup_files(tmp_path, fake, {CHAT: {"active": True, "channel": True}})
    assert channel.main(["publish", *args]) == 0
    ok = [b for b in fake.calls("POST", "/messages") if all(
        x["type"] == "link" for a in b["attachments"] if a["type"] == "inline_keyboard" for r in a["payload"]["buttons"] for x in r)]
    assert len(ok) == len(posts["posts"])
    out = capsys.readouterr().out
    assert out.count("кнопки мини-приложения MAX не принял") == 1 and f"Опубликовано постов: {len(posts['posts'])}" in out


def test_links_flag_skips_mini_app(tmp_path, monkeypatch):
    monkeypatch.setattr(channel.time, "sleep", lambda s: None)
    fake = Fake()
    fake.not_ready_once = False
    args, posts = setup_files(tmp_path, fake, {CHAT: {"active": True, "channel": True}})
    assert channel.main(["publish", *args, "--links"]) == 0
    assert fake.calls("GET", "/me") == []
    kinds = {x["type"] for b in fake.calls("POST", "/messages") for a in b["attachments"] if a["type"] == "inline_keyboard"
             for r in a["payload"]["buttons"] for x in r}
    assert kinds == {"link"}


def queue_file(tmp_path, fake, posts):
    q = {"img": fake.url() + "/img/max/", "v": "1", "posts": posts}
    f = tmp_path / "queue.json"
    f.write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
    return str(f)


def test_queue_posts_one_due_approved_post_per_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(channel.time, "sleep", lambda s: None)
    fake = Fake()
    fake.not_ready_once = False
    args, _ = setup_files(tmp_path, fake, {CHAT: {"active": True, "channel": True}})
    now = channel.dt.datetime.now(channel.MSK)
    at = lambda h: (now + channel.dt.timedelta(hours=h)).strftime("%Y-%m-%d %H:%M")
    btn = [[{"text": "Расчёт стены", "url": "https://nashdekor.ru/?utm_source=max#calc"}]]
    q = queue_file(tmp_path, fake, [
        {"id": "late", "at": at(-24 * 5), "approved": True, "text": "давний", "images": ["a.jpg"], "buttons": btn},
        {"id": "p2", "at": at(-1), "approved": True, "text": "<b>Второй</b>", "images": ["b.jpg"], "buttons": btn},
        {"id": "p1", "at": at(-2), "approved": True, "text": "<b>Первый</b>", "images": ["a.jpg"], "buttons": btn},
        {"id": "draft", "at": at(-3), "text": "черновик без «да»", "images": []},
        {"id": "future", "at": at(5), "approved": True, "text": "завтра", "images": []},
    ])
    assert channel.main(["queue", *args, "--queue", q]) == 0
    sent = fake.calls("POST", "/messages")
    assert len(sent) == 1 and sent[0]["text"] == "<b>Первый</b>"            # самый ранний из подошедших, по одному
    assert sent[0]["attachments"][-1]["payload"]["buttons"][0][0]["type"] == "open_app"
    out = capsys.readouterr().out
    assert "«late» — пропущен" in out and "опубликован «p1»" in out
    assert channel.main(["queue", *args, "--queue", q]) == 0
    assert channel.main(["queue", *args, "--queue", q]) == 0               # больше подошедших нет — тишина
    sent = fake.calls("POST", "/messages")
    assert [b["text"] for b in sent] == ["<b>Первый</b>", "<b>Второй</b>"]
    capsys.readouterr()
    assert channel.main(["queue", *args, "--queue", q, "--list"]) == 0
    out = capsys.readouterr().out
    assert "вышел" in out and "ждёт «да»" in out and "ждёт времени" in out and "пропущен" in out


def test_queue_file_in_repo_is_clean():
    """Очередь в репозитории: даты по Москве, без бренда поставщика и запретных слов, кнопки — https."""
    path = channel.os.path.join(channel.HERE, "channel_queue.json")
    if not channel.os.path.exists(path):
        return
    d = json.load(open(path, encoding="utf-8"))
    ids = [p["id"] for p in d["posts"]]
    assert len(ids) == len(set(ids))
    for p in d["posts"]:
        assert channel.post_time(p), p["id"]
        t = p["text"].lower()
        assert len(p["text"]) <= 4000 and len(p.get("images") or []) <= 10, p["id"]
        for bad in ("artdec", "арт дек", "рамк", "картой", "горюч", "бесплатно", "лучшие цены", "%"):
            assert bad not in t, (p["id"], bad)
        for row in p.get("buttons") or []:
            assert 1 <= len(row) <= 3 and all(b["url"].startswith("https://") for b in row)

