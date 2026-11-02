"""MAX (мессенджер VK) для бота «Пространство»: тонкий клиент Bot API и перевод событий в ядро.

Документация: https://dev.max.ru/docs-api , схема OpenAPI: github.com/max-messenger/api-schema.
  * адрес API — https://platform-api2.max.ru, токен — в заголовке «Authorization» как есть;
  * сервер API подписан сертификатом Минцифры (Russian Trusted Sub CA) — его нет в обычном
    хранилище Ubuntu, поэтому клиент доверяет certs/russian_trusted_ca.pem ДОПОЛНИТЕЛЬНО
    к системным сертификатам и только для запросов к MAX (система не меняется);
  * события — long polling GET /updates (marker хранится в базе, чтобы после перезапуска
    не обработать их дважды); не больше 2 сообщений в секунду в один диалог;
  * разметка — HTML (<b>, <i>, <a>, <code>), текст до 4000 символов, кнопки callback/link/
    request_contact/message, у callback-кнопки payload до 1024 символов.

Своя маленькая обёртка вместо сторонней библиотеки: нужны 8 методов, а лишние зависимости
в боте с персональными данными ни к чему.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import ssl
import time
from collections import OrderedDict
from typing import Any

import aiohttp

from catalog import CatalogStore
from config import CH_MAX, Config
from core import Blocked, Engine, Incoming, Kb, Temporary
from db import Database

log = logging.getLogger("prostranstvo.max")

UPDATE_TYPES = ("message_created", "message_callback", "bot_started")
TEXT_LIMIT = 4000
SEND_INTERVAL_SEC = 0.55        # не больше 2 сообщений в секунду в один диалог
POLL_TIMEOUT_SEC = 30
MARKER_KEY = "max_marker"

CLIENT_COMMANDS = [
    ("start", "Главное меню"), ("calc", "Рассчитать стену"), ("catalog", "Каталог и цены"),
    ("lead", "Оставить заявку"), ("manager", "Связаться с менеджером"), ("help", "Помощь"),
    ("delete_me", "Удалить мои данные"),
]

KIND_BY_ATTACHMENT = {"image": "photo", "video": "video", "audio": "voice", "file": "document",
                      "sticker": "sticker", "location": "location", "contact": "contact"}


class MaxApiError(Exception):
    def __init__(self, status: int, code: str = "", message: str = "") -> None:
        super().__init__(f"HTTP {status} {code} {message}".strip())
        self.status, self.code, self.message = status, code, message


class MaxNetworkError(Exception):
    """Нет связи с API MAX."""


def ssl_context(ca_file: str) -> ssl.SSLContext:
    """Системные сертификаты + сертификаты Минцифры (только для этого клиента)."""
    ctx = ssl.create_default_context()
    if ca_file and os.path.isfile(ca_file):
        ctx.load_verify_locations(cafile=ca_file)
    else:
        log.warning("нет файла сертификатов Минцифры (%s) — соединение с MAX может не установиться", ca_file)
    return ctx


class MaxClient:
    """Методы Bot API MAX, которые нужны боту."""

    def __init__(self, token: str, base_url: str, ca_file: str = "") -> None:
        self._token = token
        self.base_url = base_url.rstrip("/")
        self.ca_file = ca_file
        self._session: aiohttp.ClientSession | None = None

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=ssl_context(self.ca_file)) \
                if self.base_url.startswith("https://") else aiohttp.TCPConnector()
            self._session = aiohttp.ClientSession(connector=connector, headers={"Authorization": self._token})
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    async def request(self, method: str, path: str, *, params: dict[str, Any] | None = None,
                      body: Any = None, timeout: float = 30) -> dict[str, Any]:
        clean = {k: ("true" if v is True else "false" if v is False else v)
                 for k, v in (params or {}).items() if v is not None}
        session = await self.session()
        for attempt in (1, 2):
            try:
                async with session.request(method, self.base_url + path, params=clean, json=body,
                                           timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except ValueError:
                        data = None
                    if resp.status == 429 and attempt == 1:
                        await asyncio.sleep(1)  # слишком часто — пауза и одна повторная попытка
                        continue
                    if resp.status >= 400:
                        data = data if isinstance(data, dict) else {}
                        raise MaxApiError(resp.status, str(data.get("code", "")), str(data.get("message", "")))
                    return data if isinstance(data, dict) else {}
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise MaxNetworkError(type(exc).__name__) from exc
        raise MaxApiError(429, "too.many.requests")  # pragma: no cover

    async def me(self) -> dict[str, Any]:
        return await self.request("GET", "/me")

    async def get_updates(self, marker: int | None, timeout: int = POLL_TIMEOUT_SEC) -> dict[str, Any]:
        return await self.request("GET", "/updates", params={
            "marker": marker, "timeout": timeout, "limit": 100, "types": ",".join(UPDATE_TYPES)},
            timeout=timeout + 15)

    async def send_message(self, user_id: int, body: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/messages", params={"user_id": user_id, "disable_link_preview": True},
                                  body=body)

    async def edit_message(self, message_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PUT", "/messages", params={"message_id": message_id}, body=body)

    async def answer(self, callback_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/answers", params={"callback_id": callback_id}, body=body)

    async def set_commands(self, commands: list[tuple[str, str]]) -> dict[str, Any]:
        return await self.request("PATCH", "/me/commands", body={
            "commands": [{"name": n, "description": d} for n, d in commands]})

    async def subscriptions(self) -> list[dict[str, Any]]:
        return list((await self.request("GET", "/subscriptions")).get("subscriptions") or [])

    async def unsubscribe(self, url: str) -> None:
        await self.request("DELETE", "/subscriptions", params={"url": url})


# =========================================================================== кнопки и вложения
def render(kb: Kb | None) -> list[dict[str, Any]]:
    """Кнопки ядра → вложение inline_keyboard. В MAX все кнопки — под сообщением;
    кнопка-ответ (как клавиатура внизу в Telegram) — тип «message»: её текст приходит как сообщение."""
    if kb is None or not kb.rows:
        return []
    rows = []
    for row in kb.rows:
        out = []
        for b in row:
            if b.url:
                out.append({"type": "link", "text": b.text, "url": b.url})
            elif b.contact:
                out.append({"type": "request_contact", "text": b.text})
            elif b.data and kb.inline:
                out.append({"type": "callback", "text": b.text, "payload": b.data})
            else:
                out.append({"type": "message", "text": b.text})
        rows.append(out)
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


def copy_attachments(atts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Вложения входящего сообщения → вложения для повторной отправки (по токенам)."""
    out = []
    for a in atts or []:
        t, p = a.get("type"), a.get("payload") or {}
        if t in ("image", "video", "audio", "file") and p.get("token"):
            out.append({"type": t, "payload": {"token": p["token"]}})
        elif t == "sticker" and p.get("code"):
            out.append({"type": "sticker", "payload": {"code": p["code"]}})
        elif t == "location":
            out.append({"type": "location", "latitude": a.get("latitude"), "longitude": a.get("longitude")})
        elif t == "contact":
            info = p.get("max_info") or {}
            out.append({"type": "contact", "payload": {"name": info.get("first_name") or None,
                                                       "vcf_info": p.get("vcf_info")}})
        elif t == "share" and p.get("url"):
            out.append({"type": "share", "payload": {"url": p["url"]}})
    return out


def vcf_phone(vcf: str) -> str:
    """Телефон из vCard: строка TEL;TYPE=cell:+79991234567."""
    for line in (vcf or "").replace("\r\n", "\n").split("\n"):
        key, _, value = line.partition(":")
        if key.split(";", 1)[0].strip().upper() == "TEL" and value.strip():
            return value.strip()
    return ""


def _user_fields(user: dict[str, Any]) -> dict[str, Any]:
    return {"user_id": int(user.get("user_id") or 0), "first_name": user.get("first_name") or user.get("name") or "",
            "last_name": user.get("last_name") or "", "username": user.get("username") or ""}


def from_update(update: dict[str, Any]) -> Incoming | None:
    """Событие MAX → Incoming (None — не нужно боту: группы, свои сообщения, прочие типы)."""
    kind = update.get("update_type")
    if kind == "message_created":
        msg = update.get("message") or {}
        sender = msg.get("sender") or {}
        if not sender or sender.get("is_bot"):
            return None
        recipient = msg.get("recipient") or {}
        body = msg.get("body") or {}
        atts = [a for a in (body.get("attachments") or []) if a.get("type") != "inline_keyboard"]
        media_atts = [a for a in atts if a.get("type") != "share"]
        text = body.get("text")
        link = msg.get("link") or {}
        ev = Incoming(**_user_fields(sender), message_id=str(body.get("mid") or ""),
                      private=recipient.get("chat_type", "dialog") == "dialog",
                      reply_to=str((link.get("message") or {}).get("mid") or "") if link.get("type") == "reply" else "")
        if media_atts:
            first = media_atts[0]
            ev.kind = KIND_BY_ATTACHMENT.get(first.get("type", ""), first.get("type", "file"))
            ev.text, ev.caption = None, text or ""
            ev.media = {"text": text or "", "attachments": copy_attachments(atts)}
            if first.get("type") == "contact":
                payload = first.get("payload") or {}
                ev.contact_phone = vcf_phone(payload.get("vcf_info") or "")
        else:
            ev.text = text if text is not None else ""
        return ev
    if kind == "message_callback":
        callback = update.get("callback") or {}
        msg = update.get("message") or {}
        recipient = msg.get("recipient") or {}
        return Incoming(**_user_fields(callback.get("user") or {}), data=str(callback.get("payload") or ""),
                        callback_id=str(callback.get("callback_id") or ""),
                        message_id=str((msg.get("body") or {}).get("mid") or ""),
                        private=recipient.get("chat_type", "dialog") == "dialog")
    if kind == "bot_started":
        payload = (update.get("payload") or "").strip()
        return Incoming(**_user_fields(update.get("user") or {}), text="/start" + (f" {payload}" if payload else ""))
    return None


# =========================================================================== транспорт для ядра
class MaxTransport:
    channel = CH_MAX

    def __init__(self, client: MaxClient, send_interval: float = SEND_INTERVAL_SEC) -> None:
        self.client = client
        self.send_interval = send_interval
        self._last: dict[int, float] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._texts: OrderedDict[str, str] = OrderedDict()  # mid → текст (чтобы убрать кнопки, не трогая текст)
        self._link = ""

    def _remember(self, mid: str, text: str) -> None:
        if mid:
            self._texts[mid] = text
            self._texts.move_to_end(mid)
            while len(self._texts) > 2000:
                self._texts.popitem(last=False)

    @staticmethod
    def _errors(exc: Exception) -> Exception:
        if isinstance(exc, MaxNetworkError):
            return Temporary(str(exc))
        if isinstance(exc, MaxApiError):
            if exc.status in (403, 404):
                return Blocked(exc.code or str(exc.status))
            if exc.status == 429 or exc.status >= 500:
                return Temporary(str(exc.status))
        return exc

    async def _post(self, user_id: int, body: dict[str, Any]) -> str:
        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            wait = self._last.get(user_id, 0) + self.send_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                try:
                    res = await self.client.send_message(user_id, body)
                except MaxApiError as exc:
                    if exc.status != 400 or not body.get("link"):
                        raise
                    # сообщение, на которое отвечаем, удалено — отправить без ответа
                    res = await self.client.send_message(user_id, {k: v for k, v in body.items() if k != "link"})
            except (MaxApiError, MaxNetworkError) as exc:
                raise self._errors(exc) from exc
            finally:
                self._last[user_id] = time.monotonic()
        return str(((res.get("message") or {}).get("body") or {}).get("mid") or "")

    async def send(self, user_id: int, text: str, kb: Kb | None = None, reply_to: str = "") -> str:
        body: dict[str, Any] = {"text": text[:TEXT_LIMIT], "format": "html"}
        atts = render(kb)
        if atts:
            body["attachments"] = atts
        if reply_to:
            body["link"] = {"type": "reply", "mid": reply_to}
        mid = await self._post(user_id, body)
        self._remember(mid, body["text"])
        return mid

    async def edit(self, user_id: int, message_id: str, text: str, kb: Kb | None = None) -> bool:
        body = {"text": text[:TEXT_LIMIT], "format": "html", "attachments": render(kb)}
        try:
            await self.client.edit_message(message_id, body)
        except (MaxApiError, MaxNetworkError):
            return False
        self._remember(message_id, body["text"])
        return True

    async def drop_kb(self, user_id: int, message_id: str) -> None:
        text = self._texts.get(message_id)
        if text is not None:  # текст сообщения не знаем (после перезапуска) — кнопки оставляем
            with contextlib.suppress(MaxApiError, MaxNetworkError):
                await self.client.edit_message(message_id, {"text": text, "format": "html", "attachments": []})

    async def answer(self, ev: Incoming, text: str = "", alert: bool = False) -> None:
        if ev.callback_id:
            with contextlib.suppress(MaxApiError, MaxNetworkError):
                await self.client.answer(ev.callback_id, {"notification": text} if text else {})

    async def copy(self, user_id: int, media: Any, kb: Kb | None = None) -> str:
        media = media or {}
        body: dict[str, Any] = {"attachments": list(media.get("attachments") or []) + render(kb)}
        if media.get("text"):
            body["text"] = str(media["text"])[:TEXT_LIMIT]
        if not body["attachments"] and "text" not in body:
            body["text"] = "(вложение)"
        return await self._post(user_id, body)

    async def link(self) -> str:
        if not self._link:
            me = await self.client.me()
            username = me.get("username") or ""
            self._link = f"https://max.ru/{username}" if username else ""
        return self._link

    async def set_commands(self, user_id: int | None, role: str | None) -> None:
        if user_id is None:  # в MAX один список команд на всех — клиентский
            with contextlib.suppress(MaxApiError, MaxNetworkError):
                await self.client.set_commands(CLIENT_COMMANDS)


# =========================================================================== запуск
async def poll(client: MaxClient, engine: Engine, db: Database, *, once: bool = False) -> None:
    """Long polling: получать события и отдавать их ядру по одному (порядок важен для диалогов)."""
    saved = await db.get_setting(MARKER_KEY)
    marker: int | None = int(saved) if saved.isdigit() else None
    delay = 5.0
    while True:
        try:
            res = await client.get_updates(marker, timeout=0 if once else POLL_TIMEOUT_SEC)
        except MaxApiError as exc:
            if exc.status == 401:
                raise
            log.warning("MAX: ошибка получения событий (%s) — повтор через %d с", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        except MaxNetworkError as exc:
            log.warning("MAX: нет связи (%s) — повтор через %d с", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        delay = 5.0
        for update in res.get("updates") or []:
            ev = from_update(update)
            if ev is not None:
                await engine.handle(ev)
        new = res.get("marker")
        if isinstance(new, int) and new != marker:
            marker = new
            await db.set_setting(MARKER_KEY, str(marker))
        if once:
            return


async def run(cfg: Config, db: Database, store: CatalogStore) -> int:
    client = MaxClient(cfg.max_token, cfg.max_api_url, cfg.max_ca_file)
    engine = Engine(cfg, db, store, MaxTransport(client))
    tasks: list[asyncio.Task] = []
    try:
        try:
            me = await client.me()
            for sub in await client.subscriptions():
                # webhook и long polling одновременно не работают: пока подписка есть, события не приходят
                log.warning("MAX: найдена подписка webhook — отключаю, бот получает события через long polling")
                await client.unsubscribe(str(sub.get("url") or ""))
        except MaxApiError as exc:
            if exc.status == 401:
                log.error("MAX не принял токен (MAX_TOKEN в /etc/prostranstvo/bot.env). "
                          "Запустите установщик с новым токеном: --max 'ТОКЕН'")
                await asyncio.sleep(60)
                return 3
            log.error("MAX ответил ошибкой (%s) — повтор через 30 секунд", exc)
            await asyncio.sleep(30)
            return 4
        except MaxNetworkError as exc:
            log.error("нет связи с MAX (%s) — повтор через 30 секунд", exc)
            await asyncio.sleep(30)
            return 4
        await engine.start()
        log.info("MAX-бот %s запущен; каталог: %d позиций; в команде: %d (менеджеров %d, отгрузка %d)",
                 me.get("username") or me.get("first_name") or "", len(store.get() or ()), len(engine.team.all()),
                 len(engine.team.managers()), len(engine.team.shipping()))
        if not engine.team.managers():
            log.warning("менеджера ещё нет: отправьте боту /owner КОД (код показал установщик)")
        tasks = [asyncio.create_task(engine.outbox_loop()), asyncio.create_task(store.refresh_forever())]
        try:
            await poll(client, engine, db)
        except MaxApiError as exc:  # 401: токен отозвали
            log.error("MAX перестал принимать токен (%s)", exc)
            await asyncio.sleep(60)
            return 3
    finally:
        for task in tasks:
            task.cancel()
        await client.close()
    return 0
