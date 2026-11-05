"""Поддельные Telegram и MAX для сквозных тестов — без сети и без токенов.

Telegram: настоящий aiogram, подменена только HTTP-сессия (ответы в формате Bot API).
MAX: настоящий HTTP-сервер на 127.0.0.1 (aiohttp), с которым работает наш MaxClient —
проверяются запросы, заголовок авторизации, кнопки, ответы на callback, long polling.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from datetime import datetime
from typing import Any

import pytest

pytest.importorskip("aiogram")

from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import AnswerCallbackQuery, CopyMessage, EditMessageText, GetMe, SendMessage  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, Update, User  # noqa: E402
from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestServer  # noqa: E402
from conftest import SAMPLE_HTML  # noqa: E402

import max_api  # noqa: E402
import tg  # noqa: E402
from catalog import Catalog, CatalogStore, parse_catalog  # noqa: E402
from config import Config  # noqa: E402
from core import Engine  # noqa: E402
from db import Database  # noqa: E402

TG_BOT = {"id": 42, "is_bot": True, "first_name": "Наш декор", "username": "prostranstvo_test_bot"}
MAX_BOT = {"user_id": 7000, "first_name": "Наш декор", "username": "id000000000000_bot", "is_bot": True}
MAX_TOKEN = "max-test-token-0123456789"
NB = " "


def make_cfg(tmp_path, **kw: Any) -> Config:
    base = dict(bot_token="42:TEST", max_token="", owner_code="246810", consent_version="1",
                db_path=str(tmp_path / "bot.db"), catalog_file="", catalog_url="", catalog_cache="",
                telegram_collect_contacts=True)
    base.update(kw)
    return Config(**base)


def make_store() -> CatalogStore:
    store = CatalogStore("", "", "", 60)
    store.set(Catalog(parse_catalog(SAMPLE_HTML), source="тест"))
    return store


# =========================================================================== Telegram
class FakeTelegram(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[Any] = []
        self.blocked: set[int] = set()
        self._ids = itertools.count(1000)

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    def _message(self, chat_id: int, text: str | None, message_id: int | None = None) -> dict:
        data = {"message_id": message_id or next(self._ids), "date": int(time.time()),
                "chat": {"id": chat_id, "type": "private"}, "from": TG_BOT}
        if text is not None:
            data["text"] = text
        return data

    async def make_request(self, bot, method, timeout=None):  # noqa: ANN001
        self.requests.append(method)
        chat_id = getattr(method, "chat_id", None)
        if chat_id in self.blocked:
            body = {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}
            self.check_response(bot, method, 403, json.dumps(body))
        if isinstance(method, GetMe):
            result: Any = TG_BOT
        elif isinstance(method, SendMessage):
            result = self._message(int(method.chat_id), method.text)
        elif isinstance(method, EditMessageText):
            result = self._message(int(method.chat_id or 0), method.text, method.message_id)
        elif isinstance(method, CopyMessage):
            result = {"message_id": next(self._ids)}
        else:
            result = True
        return self.check_response(bot, method, 200, json.dumps({"ok": True, "result": result})).result

    def to(self, chat_id: int) -> list[Any]:
        return [r for r in self.requests if isinstance(r, (SendMessage, EditMessageText))
                and int(r.chat_id or 0) == chat_id]

    def texts(self, chat_id: int) -> list[str]:
        return [r.text for r in self.to(chat_id)]

    def last(self, chat_id: int) -> str:
        t = self.texts(chat_id)
        return t[-1] if t else ""

    def last_req(self, chat_id: int):
        reqs = self.to(chat_id)
        return reqs[-1] if reqs else None

    def find(self, chat_id: int, needle: str):
        for r in reversed(self.to(chat_id)):
            if needle in (r.text or ""):
                return r
        return None

    def count(self, chat_id: int) -> int:
        return len(self.to(chat_id))

    def toasts(self) -> list[str]:
        return [r.text or "" for r in self.requests if isinstance(r, AnswerCallbackQuery)]

    def copies_to(self, chat_id: int) -> list[Any]:
        return [r for r in self.requests if isinstance(r, CopyMessage) and int(r.chat_id) == chat_id]


def datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


def urls(markup) -> list[str]:
    return [b.url for row in markup.inline_keyboard for b in row if b.url]


def buttons(markup) -> list[str]:
    return [b.text for row in markup.keyboard for b in row]


class TgHarness:
    """Telegram-процесс: ядро + aiogram с поддельной сессией."""

    def __init__(self, cfg: Config, db: Database, store: CatalogStore, names: dict[int, tuple]) -> None:
        self.cfg, self.db, self.names = cfg, db, names
        self.s = FakeTelegram()
        self.bot = tg.make_bot(cfg.bot_token or "42:TEST", session=self.s)
        self.engine = Engine(cfg, db, store, tg.TgTransport(self.bot))
        self.dp = tg.build_dispatcher(self.engine)
        self._upd = itertools.count(1)
        self._msg = itertools.count(1)

    @property
    def team(self):
        return self.engine.team

    def user(self, uid: int) -> User:
        first, last, username = self.names[uid]
        return User(id=uid, is_bot=False, first_name=first, last_name=last, username=username)

    async def send(self, uid: int, text: str | None = None, **extra: Any) -> None:
        msg = Message(message_id=next(self._msg), date=datetime.now(), chat=Chat(id=uid, type="private"),
                      from_user=self.user(uid), text=text, **extra)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._upd), message=msg))

    async def press(self, uid: int, data: str, message_id: int | None = None) -> None:
        msg = Message(message_id=message_id or next(self._msg), date=datetime.now(),
                      chat=Chat(id=uid, type="private"), from_user=User(**TG_BOT), text="…")
        cq = CallbackQuery(id=str(next(self._upd)), from_user=self.user(uid), chat_instance="x", data=data, message=msg)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._upd), callback_query=cq))

    async def reply(self, uid: int, to_message_id: int | str, text: str | None, **extra: Any) -> None:
        original = Message(message_id=int(to_message_id), date=datetime.now(), chat=Chat(id=uid, type="private"),
                           from_user=User(**TG_BOT), text="…")
        await self.send(uid, text, reply_to_message=original, **extra)

    async def relay_ids(self, chat_id: int, client_id: int) -> list[int]:
        out = []
        for mid in range(1000, 1000 + len(self.s.requests) + 50):
            if await self.db.relay_target("tg", chat_id, str(mid)) == client_id:
                out.append(mid)
        return out

    async def close(self) -> None:
        await self.bot.session.close()


# =========================================================================== MAX
class FakeMax:
    """Поддельный сервер Bot API MAX."""

    def __init__(self, token: str = MAX_TOKEN) -> None:
        self.token = token
        self.requests: list[tuple[str, str, dict, Any]] = []
        self.updates: list[dict] = []
        self.marker = 0
        self.blocked: set[int] = set()
        self.subscriptions: list[dict] = []
        self._mid = itertools.count(1)
        self.server: TestServer | None = None
        self.unauthorized = 0

    async def start(self) -> str:
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", self._handle)
        self.server = TestServer(app, host="127.0.0.1")
        await self.server.start_server()
        return str(self.server.make_url("")).rstrip("/")

    async def stop(self) -> None:
        if self.server:
            await self.server.close()

    async def _handle(self, request: web.Request) -> web.Response:
        if request.headers.get("Authorization") != self.token:
            self.unauthorized += 1
            return web.json_response({"code": "verify.token", "message": "Invalid access_token"}, status=401)
        body = await request.json() if request.can_read_body else None
        path, q = "/" + request.match_info["path"], dict(request.query)
        self.requests.append((request.method, path, q, body))
        if path == "/me":
            return web.json_response(MAX_BOT)
        if path == "/subscriptions":
            if request.method == "DELETE":
                self.subscriptions = [s for s in self.subscriptions if s["url"] != q.get("url")]
                return web.json_response({"success": True})
            return web.json_response({"subscriptions": self.subscriptions})
        if path == "/me/commands":
            return web.json_response({**MAX_BOT, "commands": body["commands"]})
        if path == "/updates":
            batch, self.updates = self.updates, []
            if batch:
                self.marker += len(batch)
            return web.json_response({"updates": batch, "marker": self.marker})
        if path == "/messages" and request.method == "POST":
            uid = int(q["user_id"])
            mid = f"mid.{next(self._mid):04d}"  # номер = порядковый номер запроса (см. mid_of)
            if uid in self.blocked:
                return web.json_response({"code": "chat.denied", "message": "dialog.suspended"}, status=403)
            return web.json_response({"message": {
                "sender": MAX_BOT, "recipient": {"chat_id": uid + 10_000_000, "chat_type": "dialog", "user_id": uid},
                "timestamp": int(time.time() * 1000), "body": {"mid": mid, "seq": 1, "text": body.get("text")}}})
        if path == "/messages" and request.method == "PUT":
            return web.json_response({"success": True})
        if path == "/answers":
            return web.json_response({"success": True})
        return web.json_response({"code": "not.found", "message": path}, status=404)

    # --- помощники для проверок
    def sent(self, uid: int | None = None) -> list[dict]:
        out = []
        for method, path, q, body in self.requests:
            if method == "POST" and path == "/messages" and (uid is None or int(q["user_id"]) == uid):
                out.append(body)
        return out

    def texts(self, uid: int) -> list[str]:
        return [b.get("text") or "" for b in self.sent(uid)]

    def last(self, uid: int) -> str:
        t = self.texts(uid)
        return t[-1] if t else ""

    def last_body(self, uid: int) -> dict:
        s = self.sent(uid)
        return s[-1] if s else {}

    def find(self, uid: int, needle: str) -> dict | None:
        for b in reversed(self.sent(uid)):
            if needle in (b.get("text") or ""):
                return b
        return None

    def edits(self) -> list[tuple[str, dict]]:
        return [(q["message_id"], body) for m, p, q, body in self.requests if m == "PUT" and p == "/messages"]

    def answers(self) -> list[dict]:
        return [body for m, p, q, body in self.requests if p == "/answers"]

    def mid_of(self, uid: int, needle: str) -> str:
        """mid сообщения бота, текст которого содержит needle (для «Ответить»)."""
        n = 0
        mids = []
        for method, path, q, body in self.requests:
            if method == "POST" and path == "/messages":
                n += 1
                if int(q["user_id"]) == uid and needle in (body.get("text") or ""):
                    mids.append(f"mid.{n:04d}")
        assert mids, needle
        return mids[-1]


def kb_rows(body: dict) -> list[list[dict]]:
    for a in body.get("attachments") or []:
        if a.get("type") == "inline_keyboard":
            return a["payload"]["buttons"]
    return []


def payloads(body: dict) -> list[str]:
    return [b["payload"] for row in kb_rows(body) for b in row if b["type"] == "callback"]


def labels(body: dict, kind: str | None = None) -> list[str]:
    return [b["text"] for row in kb_rows(body) for b in row if kind is None or b["type"] == kind]


class MaxHarness:
    """MAX-процесс: ядро + наш MaxClient, который ходит на поддельный сервер."""

    def __init__(self, cfg: Config, db: Database, store: CatalogStore, fake: FakeMax, base_url: str,
                 names: dict[int, tuple]) -> None:
        self.fake, self.db, self.names = fake, db, names
        self.client = max_api.MaxClient(fake.token, base_url, "")
        self.transport = max_api.MaxTransport(self.client, send_interval=0)
        self.engine = Engine(cfg, db, store, self.transport)
        self._mid = itertools.count(1)
        self._cb = itertools.count(1)

    @property
    def team(self):
        return self.engine.team

    def user(self, uid: int) -> dict:
        first, last, username = self.names[uid]
        return {"user_id": uid, "first_name": first, "last_name": last, "username": username, "is_bot": False}

    def message_update(self, uid: int, text: str | None = None, attachments: list | None = None,
                       reply_to: str = "") -> dict:
        body: dict[str, Any] = {"mid": f"mid.u{next(self._mid)}", "seq": 1, "text": text, "attachments": attachments}
        msg: dict[str, Any] = {"sender": self.user(uid), "timestamp": 1,
                               "recipient": {"chat_id": uid + 10_000_000, "chat_type": "dialog"}, "body": body}
        if reply_to:
            msg["link"] = {"type": "reply", "message": {"mid": reply_to, "seq": 1}}
        return {"update_type": "message_created", "timestamp": 1, "message": msg}

    async def send(self, uid: int, text: str | None = None, **kw: Any) -> None:
        await self.engine.handle(max_api.from_update(self.message_update(uid, text, **kw)))

    async def start(self, uid: int, payload: str = "") -> None:
        await self.engine.handle(max_api.from_update({"update_type": "bot_started", "timestamp": 1,
                                                      "chat_id": uid + 10_000_000, "user": self.user(uid),
                                                      "payload": payload or None}))

    async def press(self, uid: int, payload: str, mid: str = "mid.x") -> None:
        upd = {"update_type": "message_callback", "timestamp": 1,
               "callback": {"timestamp": 1, "callback_id": f"cb{next(self._cb)}", "payload": payload,
                            "user": self.user(uid)},
               "message": {"recipient": {"chat_id": uid + 10_000_000, "chat_type": "dialog"}, "timestamp": 1,
                           "body": {"mid": mid, "seq": 1, "text": "…"}}}
        await self.engine.handle(max_api.from_update(upd))

    async def reply(self, uid: int, to_mid: str, text: str) -> None:
        await self.send(uid, text, reply_to=to_mid)

    async def close(self) -> None:
        await self.client.close()


async def flush(*harnesses: Any, rounds: int = 3) -> None:
    """Доставить очереди между процессами (как это сделали бы их фоновые циклы)."""
    for _ in range(rounds):
        for h in harnesses:
            await h.engine.flush_outbox()
        await asyncio.sleep(0)
