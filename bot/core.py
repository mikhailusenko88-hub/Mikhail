"""Ядро бота «Наш декор»: все сценарии без привязки к мессенджеру.

Одно и то же ядро работает в Telegram (tg.py) и в MAX (max_api.py). Мессенджер
даёт ядру входящие события (Incoming) и умеет отправлять сообщения с кнопками
(Transport). Всё остальное — расчёт, каталог, заявки, роли, отгрузки — здесь.

Клиенты: расчёт стены и погонажа, каталог, заявка с согласием, сообщение менеджеру.
Команда магазина (роли в базе): «менеджер» и «отгрузка». Человек может быть подключён
в обоих мессенджерах; заявки и сообщения ему приходят в один — по его выбору
(по умолчанию MAX). Ответ клиенту уходит в тот мессенджер, откуда клиент писал.

Между процессами (у каждого мессенджера свой) сообщения идут через очередь outbox
в базе: каждый процесс доставляет только в свой мессенджер, поэтому сбой одного
мессенджера не мешает другому.

Telegram и персональные данные: пока TELEGRAM_COLLECT_CONTACTS=0, Telegram-бот
не принимает заявки с телефоном (ведёт на сайт и в MAX), а сотрудникам в Telegram
не показываются имена, телефоны, адреса и тексты клиентов.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
import re
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

import calc
import texts
import yagpt
from catalog import Catalog, CatalogStore, Product, group_title
from config import CH_MAX, CH_TG, CHANNELS, Config
from db import (
    NOTIFY_ALL,
    NOTIFY_ORDERS,
    ROLE_LINK,
    ROLE_MANAGER,
    ROLE_SHIPPING,
    ROLES,
    ST_CONFIRMED,
    ST_NEW,
    ST_SHIPPING,
    Client,
    Database,
    Lead,
    Seat,
    Shipment,
    iso_now,
    now_local,
)

log = logging.getLogger("prostranstvo.core")

PAGE_SIZE = 10
ACK_INTERVAL_SEC = 10 * 60      # «сообщение передано» — не чаще раза в 10 минут
MEDIA_GROUP_TTL_SEC = 120
STATE_TTL_SEC = 6 * 3600        # незаконченный диалог (только в памяти) забывается через 6 часов
OUTBOX_POLL_SEC = 1.0
OUTBOX_MAX_ATTEMPTS = 12

KIND_NAMES = {
    "photo": "фото", "document": "файл", "voice": "голосовое", "video": "видео",
    "video_note": "видео-кружок", "audio": "аудио", "sticker": "стикер", "animation": "GIF",
    "location": "геопозиция", "contact": "контакт", "venue": "место", "poll": "опрос",
}


# =========================================================================== кнопки
@dataclass(frozen=True)
class Btn:
    text: str
    data: str = ""          # callback
    url: str = ""           # ссылка
    contact: bool = False   # «Отправить номер»


@dataclass
class Kb:
    rows: list[list[Btn]]
    inline: bool = True     # False — кнопки-ответы (их текст приходит как сообщение)
    menu: bool = False      # главное меню (в Telegram — постоянная клавиатура внизу)

    def to_json(self) -> dict:
        return {"inline": self.inline, "menu": self.menu,
                "rows": [[[b.text, b.data, b.url, b.contact] for b in row] for row in self.rows]}

    @classmethod
    def from_json(cls, data: dict | None) -> Kb | None:
        if not data:
            return None
        return cls([[Btn(*b) for b in row] for row in data["rows"]], data.get("inline", True), data.get("menu", False))


def ikb(*rows: list[Btn] | None) -> Kb:
    return Kb([list(r) for r in rows if r], inline=True)


def rkb(*rows: list[str | Btn], menu: bool = False) -> Kb:
    return Kb([[b if isinstance(b, Btn) else Btn(b) for b in row] for row in rows if row], inline=False, menu=menu)


def client_menu() -> Kb:
    return rkb([texts.BTN_CALC, texts.BTN_CATALOG], [texts.BTN_LEAD, texts.BTN_MANAGER], menu=True)


def team_menu(role: str) -> Kb:
    rows: list[list[str | Btn]] = [[texts.BTN_T_LEADS, texts.BTN_T_ORDERS], [texts.BTN_CALC, texts.BTN_CATALOG]]
    if role == ROLE_MANAGER:
        rows.append([texts.BTN_T_TEAM, texts.BTN_T_STATS])
    rows.append([texts.BTN_T_NOTIFY, texts.BTN_T_HELP])
    return rkb(*rows, menu=True)


def cb(*parts: object) -> str | None:
    """callback-данные из частей; None — если не помещаются в 64 байта (лимит Telegram)."""
    if any("|" in str(p) for p in parts):
        return None
    data = "|".join(str(p) for p in parts)
    return data if len(data.encode()) <= 64 else None


# =========================================================================== мессенджер
@dataclass
class Incoming:
    """Входящее событие: сообщение или нажатие кнопки (data не None)."""

    user_id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    text: str | None = None       # текст сообщения (у фото и файлов — None, подпись в caption)
    caption: str = ""
    kind: str = "text"            # text | photo | document | video | voice | sticker | contact | …
    contact_phone: str = ""
    message_id: str = ""          # id этого сообщения (у кнопки — сообщения с кнопкой)
    reply_to: str = ""            # на какое сообщение ответили
    callback_id: str = ""
    data: str | None = None       # данные кнопки
    media_group: str = ""
    private: bool = True
    media: Any = None             # как скопировать вложение (зависит от мессенджера, JSON)

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p).strip()


class Blocked(Exception):
    """Получатель недоступен: заблокировал бота или удалил чат."""


class Temporary(Exception):
    """Временная ошибка (сеть, перегрузка) — повторить позже."""


class Transport(Protocol):
    channel: str

    async def send(self, user_id: int, text: str, kb: Kb | None = None, reply_to: str = "") -> str: ...
    async def edit(self, user_id: int, message_id: str, text: str, kb: Kb | None = None) -> bool: ...
    async def drop_kb(self, user_id: int, message_id: str) -> None: ...
    async def answer(self, ev: Incoming, text: str = "", alert: bool = False) -> None: ...
    async def copy(self, user_id: int, media: Any, kb: Kb | None = None) -> str: ...
    async def link(self) -> str: ...
    async def set_commands(self, user_id: int | None, role: str | None) -> None: ...


# =========================================================================== команда
@dataclass(frozen=True)
class Person:
    person_id: int
    role: str
    notify: str
    deliver: str
    seats: tuple[Seat, ...]
    static: bool = False

    @property
    def name(self) -> str:
        for s in self.seats:
            if s.name:
                return s.name
        for s in self.seats:
            if s.username:
                return "@" + s.username
        return ""

    @property
    def channels(self) -> list[str]:
        return [s.channel for s in self.seats]


class Team:
    """Команда магазина из базы (читается заново на каждое событие — её меняют оба процесса)."""

    def __init__(self, static: dict[str, frozenset[int]] | None = None) -> None:
        self.static = {ch: set(ids) for ch, ids in (static or {}).items()}
        self._seats: dict[tuple[str, int], Seat] = {}
        self._persons: dict[int, Person] = {}

    async def refresh(self, db: Database) -> None:
        seats = await db.team()
        by_person: dict[int, list[Seat]] = {}
        for s in seats:
            by_person.setdefault(s.person_id, []).append(s)
        self._seats = {(s.channel, s.user_id): s for s in seats}
        self._persons = {
            pid: Person(pid, ss[0].role, ss[0].notify, ss[0].deliver, tuple(ss),
                        any(s.user_id in self.static.get(s.channel, ()) for s in ss))
            for pid, ss in by_person.items()
        }

    def seat(self, channel: str, user_id: int) -> Seat | None:
        return self._seats.get((channel, user_id))

    def person(self, person_id: int) -> Person | None:
        return self._persons.get(person_id)

    def person_of(self, channel: str, user_id: int) -> Person | None:
        s = self._seats.get((channel, user_id))
        return self._persons.get(s.person_id) if s else None

    def persons(self) -> list[Person]:
        return sorted(self._persons.values(), key=lambda p: (p.role != ROLE_MANAGER, p.person_id))

    def all(self) -> list[int]:
        return sorted(self._persons)

    def managers(self) -> list[int]:
        return sorted(p for p, v in self._persons.items() if v.role == ROLE_MANAGER)

    def shipping(self) -> list[int]:
        return sorted(p for p, v in self._persons.items() if v.role == ROLE_SHIPPING)

    def message_recipients(self) -> list[int]:
        """Кому слать каждое сообщение клиента: включившим «все сообщения», иначе менеджерам."""
        chosen = sorted(p for p, v in self._persons.items() if v.notify == NOTIFY_ALL)
        return chosen or self.managers()

    def deliver_channel(self, person: Person, enabled: tuple[str, ...], default: str) -> str:
        chans = [c for c in person.channels if c in enabled] or person.channels
        for want in (person.deliver, default):
            if want in chans:
                return want
        return chans[0] if chans else ""

    def target(self, person_id: int, enabled: tuple[str, ...], default: str) -> Seat | None:
        person = self._persons.get(person_id)
        if not person:
            return None
        ch = self.deliver_channel(person, enabled, default)
        return next((s for s in person.seats if s.channel == ch), None)

    def name(self, person_id: int) -> str:
        p = self._persons.get(person_id)
        return p.name if p else ""


class AttemptLimiter:
    """Защита /owner и /join от подбора кода: 5 попыток на человека и 50 всего за час."""

    def __init__(self, per_user: int = 5, total: int = 50, window: int = 3600) -> None:
        self.per_user, self.total, self.window = per_user, total, window
        self._all: deque[float] = deque()
        self._users: dict[int, deque[float]] = {}

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        while self._all and now - self._all[0] > self.window:
            self._all.popleft()
        user = self._users.setdefault(user_id, deque())
        while user and now - user[0] > self.window:
            user.popleft()
        if len(user) >= self.per_user or len(self._all) >= self.total:
            return False
        user.append(now)
        self._all.append(now)
        return True


class Runtime:
    """Мелкое состояние в памяти: когда клиенту последний раз писали «передано» и т.п."""

    def __init__(self) -> None:
        self.last_ack: OrderedDict[int, float] = OrderedDict()
        self.media_groups: OrderedDict[str, float] = OrderedDict()

    @staticmethod
    def _trim(d: OrderedDict, limit: int = 5000) -> None:
        while len(d) > limit:
            d.popitem(last=False)

    def need_ack(self, user_id: int) -> bool:
        now = time.monotonic()
        last = self.last_ack.get(user_id)
        if last is not None and now - last < ACK_INTERVAL_SEC:
            return False
        self.last_ack[user_id] = now
        self.last_ack.move_to_end(user_id)
        self._trim(self.last_ack)
        return True

    def first_in_media_group(self, key: str | None) -> bool:
        if not key:
            return True
        now = time.monotonic()
        for old in [k for k, t in self.media_groups.items() if now - t > MEDIA_GROUP_TTL_SEC]:
            del self.media_groups[old]
        if key in self.media_groups:
            return False
        self.media_groups[key] = now
        self._trim(self.media_groups)
        return True


# =========================================================================== разбор ввода
_CMD_RE = re.compile(r"^/([A-Za-z_]+)(?:@[\w.]+)?(?:\s+(.*))?$", re.S)
_PHONE_CHARS_RE = re.compile(r"^[\d\s()+\-.]{10,25}$")
_TG_NICK_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{3,31}$")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")
_CALC_LINK_RE = re.compile(r"^(ls|ll)_([0-9a-f]{2,40})_(\d{1,7})(?:_(\d{1,7}))?$")
_CLIENT_REF_RE = re.compile(r"^[КкKk](\d+)$")
_LEAD_REF_RE = re.compile(r"^[#№]?(\d+)$")


def parse_cmd(text: str | None) -> tuple[str, str]:
    m = _CMD_RE.match((text or "").strip())
    return (m.group(1).lower(), (m.group(2) or "").strip()) if m else ("", "")


def parse_phone(text: str) -> str | None:
    s = text.strip()
    digits = re.sub(r"\D", "", s)
    if not (_PHONE_CHARS_RE.match(s) and 10 <= len(digits) <= 15):
        return None
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        digits = "7" + digits
    return "+" + digits


def phone_from_contact(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    return "+" + digits if digits else ""


def parse_contact(text: str) -> str | None:
    """Телефон / @ник / e-mail из текста; None — если не похоже ни на что."""
    s = text.strip()
    phone = parse_phone(s)
    if phone:
        return phone
    if s.startswith("@") and _TG_NICK_RE.match(s):
        return "Telegram " + s
    if _EMAIL_RE.match(s):
        return s
    return None


def calc_link_payload(prefix: str, article: str, *nums: int) -> str:
    """Расчёт для ссылки «продолжить в другом мессенджере»: ls_<артикул hex>_<ширина>_<высота>."""
    return "_".join([prefix, article.encode().hex(), *(str(n) for n in nums)])


# =========================================================================== ядро
class Engine:
    def __init__(self, cfg: Config, db: Database, store: CatalogStore, transport: Transport, *,
                 limiter: AttemptLimiter | None = None, rt: Runtime | None = None) -> None:
        self.cfg, self.db, self.store, self.t = cfg, db, store, transport
        self.ch: str = transport.channel
        self.team = Team({CH_TG: cfg.admin_ids, CH_MAX: cfg.max_admin_ids})
        self.limiter = limiter or AttemptLimiter()
        self.rt = rt or Runtime()
        self._states: OrderedDict[int, list[Any]] = OrderedDict()

    # ------------------------------------------------------------------ свойства
    @property
    def collect(self) -> bool:
        """Собирает ли этот мессенджер контакты клиентов и показывает ли их сотрудникам."""
        return self.ch != CH_TG or self.cfg.telegram_collect_contacts

    @property
    def enabled(self) -> tuple[str, ...]:
        return self.cfg.channels or (self.ch,)

    async def bot_link(self, channel: str) -> str:
        if channel == self.ch:
            with contextlib.suppress(Exception):
                return await self.t.link()
        if channel == CH_MAX and self.cfg.max_bot_url:
            return self.cfg.max_bot_url
        return await self.db.get_setting(f"{channel}_bot_url")

    async def start(self) -> None:
        for ch, ids in ((CH_TG, self.cfg.admin_ids), (CH_MAX, self.cfg.max_admin_ids)):
            for uid in ids:
                await self.db.ensure_member(ch, uid)
        await self.team.refresh(self.db)
        link = ""
        with contextlib.suppress(Exception):
            link = await self.t.link()
        if link:
            await self.db.set_setting(f"{self.ch}_bot_url", link)
        await self.t.set_commands(None, None)
        for person in self.team.persons():
            for s in person.seats:
                if s.channel == self.ch:
                    await self.t.set_commands(s.user_id, person.role)

    # ------------------------------------------------------------------ состояние диалога (только в памяти)
    def state(self, uid: int) -> str:
        item = self._states.get(uid)
        if not item:
            return ""
        if time.monotonic() - item[2] > STATE_TTL_SEC:
            del self._states[uid]
            return ""
        return item[0]

    def data(self, uid: int) -> dict[str, Any]:
        item = self._states.get(uid)
        return item[1] if item else {}

    def set_state(self, uid: int, state: str, **data: Any) -> None:
        self._states[uid] = [state, dict(data), time.monotonic()]
        self._states.move_to_end(uid)
        while len(self._states) > 5000:
            self._states.popitem(last=False)

    def update(self, uid: int, **data: Any) -> None:
        item = self._states.get(uid)
        if item:
            item[1].update(data)
            item[2] = time.monotonic()

    def go(self, uid: int, state: str, **data: Any) -> None:
        """Перейти к следующему шагу, сохранив собранные данные."""
        merged = {**self.data(uid), **data}
        self.set_state(uid, state, **merged)

    def clear(self, uid: int) -> None:
        self._states.pop(uid, None)

    # ------------------------------------------------------------------ отправка
    def menu(self, me: Person | None) -> Kb:
        return team_menu(me.role) if me else client_menu()

    async def say(self, uid: int, text: str, kb: Kb | None = None, reply_to: str = "") -> str:
        return await self.t.send(uid, text, kb, reply_to)

    async def show(self, ev: Incoming, text: str, kb: Kb | None = None) -> None:
        """Для кнопки — заменить сообщение с кнопками, для текста — ответить новым."""
        if ev.data is not None and ev.message_id and (kb is None or kb.inline) \
                and await self.t.edit(ev.user_id, ev.message_id, text, kb):
            return
        await self.say(ev.user_id, text, kb)

    async def drop_kb(self, ev: Incoming) -> None:
        if ev.message_id:
            with contextlib.suppress(Exception):
                await self.t.drop_kb(ev.user_id, ev.message_id)

    async def relay(self, uid: int, message_id: str, client_id: int, lead_id: int | None = None) -> None:
        if message_id and client_id:
            await self.db.add_relay(self.ch, uid, message_id, client_id, lead_id)

    # ------------------------------------------------------------------ доставка
    # свой мессенджер — сразу, чужой — через очередь outbox
    async def post(self, channel: str, uid: int, item: dict, client_id: int | None = None) -> None:
        if channel != self.ch:
            await self.db.enqueue(channel, uid, item, client_id)
            return
        try:
            await self.deliver(uid, item)
        except Blocked:
            await self._on_blocked(item)
        except Temporary as exc:
            log.warning("временная ошибка отправки (%s) — повторю из очереди", exc)
            await self.db.enqueue(channel, uid, item, client_id)
        except Exception as exc:  # noqa: BLE001 - сбой уведомления не должен ломать ответ клиенту
            log.error("не удалось доставить: %s", type(exc).__name__, exc_info=exc)
            await self._on_blocked(item)

    async def notify(self, person_ids: list[int], item: dict, client_id: int | None = None,
                     exclude: int | None = None) -> list[Seat]:
        """Отправить сотрудникам — каждому в мессенджер, который он выбрал."""
        seats = []
        for pid in person_ids:
            if pid == exclude:
                continue
            seat = self.team.target(pid, self.enabled, self.cfg.staff_default_channel)
            if seat:
                seats.append(seat)
                await self.post(seat.channel, seat.user_id, item, client_id)
        return seats

    async def outbox_loop(self) -> None:
        """Доставить то, что для этого мессенджера поставил в очередь другой процесс."""
        rounds = 0
        while True:
            try:
                await self.flush_outbox()
                rounds += 1
                if rounds % 3600 == 0:
                    await self.db.outbox_cleanup()
            except Exception as exc:  # noqa: BLE001 - цикл не должен останавливаться
                log.error("очередь доставки: %s", type(exc).__name__)
            await asyncio.sleep(OUTBOX_POLL_SEC)

    async def flush_outbox(self) -> int:
        items = await self.db.outbox_pending(self.ch)
        if items:
            await self.team.refresh(self.db)
        for it in items:
            try:
                await self.deliver(it.chat_id, it.item)
            except Blocked:
                await self.db.outbox_done(it.id, "получатель недоступен")
                await self._on_blocked(it.item)
                continue
            except Temporary as exc:
                if it.attempts + 1 >= OUTBOX_MAX_ATTEMPTS:
                    await self.db.outbox_done(it.id, f"не доставлено: {exc}")
                else:
                    await self.db.outbox_retry(it.id, min(3600, 15 * 2 ** it.attempts), str(exc))
                continue
            except Exception as exc:  # noqa: BLE001
                log.error("не удалось доставить из очереди: %s", type(exc).__name__, exc_info=exc)
                await self.db.outbox_done(it.id, type(exc).__name__)
                await self._on_blocked(it.item)
                continue
            await self.db.outbox_done(it.id)
        return len(items)

    async def _on_blocked(self, item: dict) -> None:
        if item.get("t") == "to_client":
            staff = item.get("staff") or {}
            await self.post(staff.get("ch", self.ch), int(staff.get("uid", 0)),
                            {"t": "text", "text": texts.SEND_FAILED, "reply_to": staff.get("reply_to", "")})

    async def deliver(self, uid: int, item: dict) -> None:
        """Показать элемент очереди сотруднику (или клиенту) в этом мессенджере."""
        t = item.get("t")
        pii = self.collect
        seat = self.team.seat(self.ch, uid)
        if t == "text":
            reply_to = item.get("reply_to", "") if item.get("reply_ch", self.ch) == self.ch else ""
            mid = await self.say(uid, item["text"], Kb.from_json(item.get("kb")), reply_to)
            if item.get("client_id"):
                await self.relay(uid, mid, int(item["client_id"]))
        elif t == "lead":
            lead = await self.db.get_lead(int(item["lead_id"]))
            if lead:
                mid = await self.say(uid, texts.lead_card(lead, item.get("title", "Новая заявка"), pii),
                                     self.lead_kb(lead, seat.role if seat else ROLE_SHIPPING))
                await self.relay(uid, mid, lead.client_id, lead.id)
        elif t == "ship":
            ship = await self.db.get_shipment(int(item["lead_id"]))
            if ship:
                mid = await self.say(uid, texts.shipment_card(ship, pii),
                                     self.ship_kb(ship, bool(seat and seat.role == ROLE_MANAGER)))
                await self.relay(uid, mid, ship.client_id, ship.lead_id)
        elif t == "ship_note":
            ship = await self.db.get_shipment(int(item["lead_id"]))
            name = ship.client_name if ship and pii else ""
            await self.say(uid, texts.ship_status_note(int(item["lead_id"]), item["action"], item.get("by", ""), name))
        elif t == "msg":
            await self._deliver_client_message(uid, item, pii)
        elif t == "msg_notice":
            client_id = int(item["client_id"])
            mid = await self.say(uid, texts.tg_message_notice(client_id, item.get("kind", "text")),
                                 ikb([self.history_btn(client_id)]))
            await self.relay(uid, mid, client_id)
        elif t == "to_client":
            await self._deliver_to_client(uid, item)
        elif t == "removed":
            with contextlib.suppress(Exception):
                await self.t.set_commands(uid, None)
            await self.say(uid, texts.REMOVED_YOU, client_menu())
        else:
            log.warning("неизвестный элемент очереди: %s", t)

    async def _deliver_client_message(self, uid: int, item: dict, pii: bool) -> None:
        msg = await self.db.get_message(int(item["message_id"]))
        if not msg:
            return  # клиент успел удалить свои данные
        client = await self.db.get_client(int(msg["client_id"]))
        if not client:
            return
        hist = ikb([self.history_btn(client.id)])
        if msg["kind"] == "text":
            mid = await self.say(uid, texts.client_message_text(client.name, client.username, msg["text"],
                                                                client.id, client.channel, pii), hist)
            await self.relay(uid, mid, client.id)
            return
        same = item.get("src") == self.ch and item.get("media") is not None and pii
        group = item.get("group") or ""
        if self.rt.first_in_media_group(f"{uid}:{group}" if group else None):
            head = texts.client_message_header(client.name, client.username, msg["kind"], client.id,
                                               client.channel, pii)
            if not same:
                head += "\n" + texts.media_unavailable(msg["kind"], client.channel)
            mid = await self.say(uid, head, hist)
            await self.relay(uid, mid, client.id)
        if same:
            mid = await self.t.copy(uid, item["media"])
            await self.relay(uid, mid, client.id)

    async def _deliver_to_client(self, uid: int, item: dict) -> None:
        client = await self.db.get_client(int(item["client_id"]))
        staff = item.get("staff") or {}
        if not client:
            return
        if item.get("text") is not None:
            await self.say(uid, texts.manager_reply(item["text"]))
            kind, body = "text", item["text"]
        else:
            await self.t.copy(uid, item.get("media"))
            kind, body = item.get("kind", "файл"), item.get("caption", "")
        await self.db.add_message(client=client, direction="out", kind=kind, text=body,
                                  admin_id=staff.get("pid"), admin_name=staff.get("name", ""))
        await self.post(staff.get("ch", self.ch), int(staff.get("uid", 0)),
                        {"t": "text", "text": texts.SENT_TO_CLIENT, "reply_to": staff.get("reply_to", ""),
                         "reply_ch": staff.get("ch", self.ch)})

    # ------------------------------------------------------------------ вход
    async def handle(self, ev: Incoming) -> None:
        if not ev.private:
            return
        await self.team.refresh(self.db)
        me = self.team.person_of(self.ch, ev.user_id)
        if ev.data is not None:
            toast = ""
            try:
                toast = await self._callback(ev, me) or ""
            except Exception as exc:  # noqa: BLE001
                await self._fail(ev, exc)
            finally:
                with contextlib.suppress(Exception):
                    await self.t.answer(ev, toast, alert=toast == texts.ONLY_MANAGER)
            return
        try:
            await self._message(ev, me)
        except Exception as exc:  # noqa: BLE001
            await self._fail(ev, exc)

    async def _fail(self, ev: Incoming, exc: Exception) -> None:
        log.error("ошибка при обработке: %s", type(exc).__name__, exc_info=exc)
        with contextlib.suppress(Exception):
            await self.say(ev.user_id, texts.ERROR_GENERIC)

    async def _message(self, ev: Incoming, me: Person | None) -> None:
        uid, text = ev.user_id, ev.text
        cmd, args = parse_cmd(text)
        manager = bool(me and me.role == ROLE_MANAGER)

        # команды работают в любом состоянии (прерывают начатый сценарий)
        if cmd == "start":
            return await self.cmd_start(ev, me, args)
        if cmd == "help" or (me and text == texts.BTN_T_HELP):
            return await self.cmd_help(ev, me)
        if cmd == "cancel" or text == texts.BTN_CANCEL:
            self.clear(uid)
            await self.say(uid, texts.CANCELLED, self.menu(me))
            return
        if cmd == "delete_me":
            self.clear(uid)
            await self.say(uid, texts.DELETE_CONFIRM, ikb([Btn(texts.BTN_DELETE_YES, "del|yes"),
                                                           Btn(texts.BTN_CANCEL, "del|no")]))
            return
        if cmd == "owner":
            return await self.cmd_owner(ev, me, args)
        if cmd == "join":
            return await self.cmd_join(ev, me, args)
        if me and await self._staff_command(ev, me, cmd, args, text):
            return

        # меню
        if text == texts.BTN_CALC or cmd == "calc":
            return await self.open_calc(ev)
        if text == texts.BTN_CATALOG or cmd == "catalog":
            return await self.open_catalog(ev, me)
        if text == texts.BTN_LEAD or cmd == "lead":
            return await self.open_lead(ev, me)
        if text == texts.BTN_MANAGER or cmd == "manager":
            self.clear(uid)
            await self.say(uid, texts.manager_prompt(self.collect), self.menu(me))
            return

        st = self.state(uid)
        if manager and st.startswith("ship_"):
            return await self.ship_step(ev, me, st)
        if me and ev.reply_to:
            return await self.staff_reply(ev, me)
        if st.startswith("calc_"):
            return await self.calc_step(ev, me, st)
        if st.startswith("lead_"):
            return await self.lead_step(ev, me, st)
        if me:
            if text and text.startswith("/"):
                await self.cmd_help(ev, me)
            else:
                await self.say(uid, texts.TEAM_FREE_TEXT)
            return
        if text in texts.STEP_BUTTONS:
            await self.say(uid, texts.MENU_HINT, client_menu())
            return
        await self.client_message(ev)

    async def _staff_command(self, ev: Incoming, me: Person, cmd: str, args: str, text: str | None) -> bool:
        uid = ev.user_id
        if cmd == "leads" or text == texts.BTN_T_LEADS:
            await self.cmd_leads(uid)
        elif cmd == "lead" and args:
            await self.cmd_lead(uid, me, args)
        elif cmd == "orders" or text == texts.BTN_T_ORDERS:
            await self.cmd_orders(uid, me)
        elif cmd == "history":
            await self.cmd_history(uid, args)
        elif cmd == "reply":
            await self.cmd_reply(ev, me, args)
        elif cmd == "notify" or text == texts.BTN_T_NOTIFY:
            await self.cmd_notify(uid, me, args if cmd == "notify" else "")
        elif cmd in ("team", "invite", "remove", "stats", "reload") or text in (texts.BTN_T_TEAM, texts.BTN_T_STATS):
            if me.role != ROLE_MANAGER:
                await self.say(uid, texts.ONLY_MANAGER)
            elif cmd == "team" or text == texts.BTN_T_TEAM:
                await self.cmd_team(uid, me)
            elif cmd == "invite":
                await self.cmd_invite(uid, me, args)
            elif cmd == "remove":
                await self.cmd_remove(uid, args)
            elif cmd == "stats" or text == texts.BTN_T_STATS:
                await self.cmd_stats(uid)
            else:
                await self.cmd_reload(uid)
        else:
            return False
        return True

    async def _callback(self, ev: Incoming, me: Person | None) -> str:
        d = ev.data or ""
        manager = bool(me and me.role == ROLE_MANAGER)
        if d.startswith("kg|"):
            await self.cb_catalog_group(ev)
        elif d == "kb":
            await self.cb_catalog_groups(ev)
        elif d.startswith(("cg|", "cgn|")):
            await self.cb_calc_group(ev)
        elif d.startswith("cp|"):
            await self.cb_calc_page(ev)
        elif d == "cb":
            await self.cb_calc_back(ev)
        elif d.startswith("ca|"):
            await self.cb_calc_article(ev, me)
        elif d == "cn":
            await self.open_calc(ev)
        elif d.startswith(("ls|", "ll|")):
            await self.cb_send_calc(ev)
        elif d in ("lead|yes", "lead|no"):
            await self.cb_lead_consent(ev, me)
        elif d in ("del|yes", "del|no"):
            await self.cb_delete(ev, me)
        elif me and d.startswith("ld|"):
            await self.cb_open_lead(ev, me)
        elif me and d.startswith("hist|"):
            arg = d.split("|", 1)[1]
            if arg.isdigit():
                await self.send_history(ev.user_id, int(arg))
        elif me and d.startswith("ntf|"):
            mode = d.split("|", 1)[1]
            if mode in (NOTIFY_ALL, NOTIFY_ORDERS):
                await self.db.set_notify(me.person_id, mode)
                await self.show(ev, texts.notify_set(mode))
        elif me and d.startswith("dlv|"):
            ch = d.split("|", 1)[1]
            if ch in me.channels:
                await self.db.set_deliver(me.person_id, ch)
                await self.show(ev, texts.deliver_set(ch))
        elif me and d.startswith("lnk|"):
            await self.cb_link(ev, me, d.split("|", 1)[1])
        elif me and d.startswith("sh|"):
            return await self.cb_ship_action(ev, me)
        elif manager and d.startswith("shp|"):
            await self.cb_ship_start(ev)
        elif manager and d in ("shc|yes", "shc|no"):
            await self.cb_ship_confirm(ev, me)
        elif manager and d.startswith("inv|"):
            role = d.split("|", 1)[1]
            if role in ROLES:
                await self.send_invite(ev.user_id, me, role)
        elif manager and (d.startswith(("rm|", "rmy|")) or d == "rmn"):
            await self.cb_remove(ev)
        else:
            return texts.BUTTON_STALE
        return ""

    # ------------------------------------------------------------------ общее меню
    async def cmd_start(self, ev: Incoming, me: Person | None, payload: str) -> None:
        uid = ev.user_id
        self.clear(uid)
        if me and not payload:
            await self.say(uid, self.role_help(me.role), team_menu(me.role))
            return
        await self.say(uid, texts.welcome(self.cfg.site_url, self.collect), self.menu(me))
        route = {"calc": self.open_calc, "catalog": lambda e: self.open_catalog(e, me),
                 "lead": lambda e: self.open_lead(e, me),
                 "manager": lambda e: self.say(e.user_id, texts.manager_prompt(self.collect), self.menu(me))}
        if payload in route:
            await route[payload](ev)
            return
        catalog = self.store.get()
        if not catalog or not payload:
            return
        m = _CALC_LINK_RE.match(payload)
        if m:
            with contextlib.suppress(ValueError, UnicodeDecodeError):
                product = catalog.find(bytes.fromhex(m.group(2)).decode())
                if product and m.group(1) == "ls" and m.group(4) and product.is_area:
                    await self._finish_area(uid, product, int(m.group(3)), int(m.group(4)))
                elif product and m.group(1) == "ll" and not product.is_area:
                    await self._finish_linear(uid, product, int(m.group(3)))
            return
        product = catalog.find(payload)
        if product:
            await self.start_product(uid, product, me)

    def role_help(self, role: str) -> str:
        return texts.help_manager(self.ch) if role == ROLE_MANAGER else texts.help_shipping(self.ch)

    async def cmd_help(self, ev: Incoming, me: Person | None) -> None:
        if me:
            await self.say(ev.user_id, self.role_help(me.role), team_menu(me.role))
        else:
            await self.say(ev.user_id, texts.help_client(self.cfg.site_url), client_menu())

    # ------------------------------------------------------------------ каталог
    def groups_kb(self, catalog: Catalog, prefix: str) -> Kb:
        return ikb(*[[Btn(title, f"{prefix}|{code}")] for code, title in catalog.groups()])

    async def open_catalog(self, ev: Incoming, me: Person | None) -> None:
        self.clear(ev.user_id)
        catalog = self.store.get()
        if not catalog:
            await self.say(ev.user_id, texts.CATALOG_UNAVAILABLE, self.menu(me))
            return
        await self.say(ev.user_id, texts.CATALOG_CHOOSE_GROUP, self.groups_kb(catalog, "kg"))

    async def cb_catalog_group(self, ev: Incoming) -> None:
        catalog = self.store.get()
        group = (ev.data or "").split("|", 1)[-1]
        items = catalog.in_group(group) if catalog else []
        if not items:
            await self.show(ev, texts.CATALOG_UNAVAILABLE)
            return
        parts = texts.catalog_group(group, items, self.cfg.site_url)
        kb = ikb([Btn(f"{texts.BTN_CALC_GROUP}: {group_title(group)}", f"cgn|{group}")],
                 [Btn(texts.BTN_OTHER_GROUPS, "kb")],
                 [Btn(texts.BTN_SITE, url=self.cfg.site_link())] if self.cfg.site_url else None)
        for i, part in enumerate(parts):
            await self.say(ev.user_id, part, kb if i == len(parts) - 1 else None)

    async def cb_catalog_groups(self, ev: Incoming) -> None:
        catalog = self.store.get()
        if not catalog:
            await self.show(ev, texts.CATALOG_UNAVAILABLE)
            return
        await self.say(ev.user_id, texts.CATALOG_CHOOSE_GROUP, self.groups_kb(catalog, "kg"))

    # ------------------------------------------------------------------ расчёт
    async def open_calc(self, ev: Incoming) -> None:
        uid = ev.user_id
        self.clear(uid)
        catalog = self.store.get()
        if not catalog:
            await self.show(ev, texts.CATALOG_UNAVAILABLE)
            return
        self.set_state(uid, "calc_article")
        await self.say(uid, texts.CALC_CHOOSE_GROUP, self.groups_kb(catalog, "cg"))

    def articles_kb(self, group: str, items: list[Product], page: int, pages: int) -> Kb:
        buttons = []
        for p in items:
            data = cb("ca", p.article)
            if data:
                label = f"{p.article} · {p.short_desc}"[:40] if p.kind == "color" and p.short_desc \
                    else f"{p.article} · {p.price} ₽"
                buttons.append(Btn(label, data))
        width = 1 if group == "color" else 2
        rows = [buttons[i:i + width] for i in range(0, len(buttons), width)]
        nav = []
        if page > 0:
            nav.append(Btn(texts.BTN_PREV, f"cp|{group}|{page - 1}"))
        if page + 1 < pages:
            nav.append(Btn(texts.BTN_NEXT, f"cp|{group}|{page + 1}"))
        if nav:
            rows.append(nav)
        rows.append([Btn(texts.BTN_TO_GROUPS, "cb")])
        return Kb(rows)

    async def _show_group_page(self, ev: Incoming, catalog: Catalog, group: str, page: int, edit: bool) -> None:
        items = catalog.in_group(group)
        if not items:
            await self.show(ev, texts.CALC_CHOOSE_GROUP, self.groups_kb(catalog, "cg"))
            return
        pages = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE
        page = max(0, min(page, pages - 1))
        chunk = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        text = texts.calc_choose_article(group, chunk, page, pages)
        kb = self.articles_kb(group, chunk, page, pages)
        if edit:
            await self.show(ev, text, kb)
        else:
            await self.say(ev.user_id, text, kb)

    async def cb_calc_group(self, ev: Incoming) -> None:
        catalog = self.store.get()
        if not catalog:
            await self.show(ev, texts.CATALOG_UNAVAILABLE)
            return
        self.set_state(ev.user_id, "calc_article")
        prefix, _, group = (ev.data or "").partition("|")
        # «Рассчитать» под списком цен (cgn): список не трогаем, выбор артикула — новым сообщением
        await self._show_group_page(ev, catalog, group, 0, edit=prefix == "cg")

    async def cb_calc_page(self, ev: Incoming) -> None:
        catalog = self.store.get()
        parts = (ev.data or "").split("|")
        if not catalog or len(parts) != 3 or not parts[2].isdigit():
            await self.show(ev, texts.CATALOG_UNAVAILABLE)
            return
        self.set_state(ev.user_id, "calc_article")
        await self._show_group_page(ev, catalog, parts[1], int(parts[2]), edit=True)

    async def cb_calc_back(self, ev: Incoming) -> None:
        catalog = self.store.get()
        if not catalog:
            await self.show(ev, texts.CATALOG_UNAVAILABLE)
            return
        self.set_state(ev.user_id, "calc_article")
        await self.show(ev, texts.CALC_CHOOSE_GROUP, self.groups_kb(catalog, "cg"))

    async def cb_calc_article(self, ev: Incoming, me: Person | None) -> None:
        catalog = self.store.get()
        product = catalog.find((ev.data or "").split("|", 1)[-1]) if catalog else None
        if not product:
            await self.show(ev, texts.CALC_EXPIRED)
            return
        await self.start_product(ev.user_id, product, me)

    async def start_product(self, uid: int, product: Product, me: Person | None) -> None:
        if product.is_area:
            self.set_state(uid, "calc_width", article=product.article)
            await self.say(uid, texts.ask_width(product), self.menu(me))
        else:
            self.set_state(uid, "calc_length", article=product.article)
            await self.say(uid, texts.ask_length(product), self.menu(me))

    async def calc_step(self, ev: Incoming, me: Person | None, st: str) -> None:
        uid = ev.user_id
        catalog = self.store.get()
        if st == "calc_article":
            if ev.text is None:
                if me:
                    await self.say(uid, texts.TEAM_FREE_TEXT)
                else:
                    await self.client_message(ev)
                return
            if not catalog:
                await self.say(uid, texts.CATALOG_UNAVAILABLE)
                return
            query = ev.text.strip()
            product = catalog.find(query)
            if product:
                await self.start_product(uid, product, me)
            else:
                await self.say(uid, texts.article_not_found(query, catalog.search(query)),
                               self.groups_kb(catalog, "cg"))
            return
        what = {"calc_width": "width", "calc_height": "height"}.get(st, "length")
        if ev.text is None:
            await self.say(uid, texts.input_error(calc.InputError("format"), what))
            return
        data = self.data(uid)
        product = catalog.find(data.get("article", "")) if catalog else None
        if not product:
            self.clear(uid)
            await self.say(uid, texts.CALC_EXPIRED, self.menu(me))
            return
        try:
            if st == "calc_width":
                pair = calc.parse_wall_pair(ev.text)
                if pair:
                    await self._finish_area(uid, product, *pair)
                    return
                width_mm = calc.parse_length_mm(ev.text, calc.MAX_WALL_WIDTH_M)
                self.go(uid, "calc_height", width_mm=width_mm)
                await self.say(uid, texts.ask_height(width_mm))
            elif st == "calc_height":
                height_mm = calc.parse_length_mm(ev.text, calc.MAX_WALL_HEIGHT_M)
                await self._finish_area(uid, product, int(data.get("width_mm", 0)), height_mm)
            else:
                await self._finish_linear(uid, product, calc.parse_length_mm(ev.text, calc.MAX_LINEAR_M))
        except calc.InputError as err:
            await self.say(uid, texts.input_error(err, what))
        except ValueError:
            self.clear(uid)
            await self.say(uid, texts.CALC_EXPIRED, self.menu(self.team.person_of(self.ch, uid)))

    async def calc_result_kb(self, prefix: str, product: Product, *nums: int) -> Kb:
        again = [Btn(texts.BTN_CALC_AGAIN, "cn")]
        if self.collect:
            data = cb(prefix, product.article, *nums)
            return ikb([Btn(texts.BTN_SEND_CALC, data)] if data else None, again)
        rows: list[list[Btn] | None] = []
        max_link = await self.bot_link(CH_MAX)
        if max_link:
            rows.append([Btn(texts.BTN_CONTINUE_MAX,
                             url=f"{max_link}?start={calc_link_payload(prefix, product.article, *nums)}")])
        if self.cfg.site_url:
            rows.append([Btn(texts.BTN_LEAD_SITE, url=self.cfg.site_link("#order"))])
        rows.append(again)
        return ikb(*rows)

    async def _finish_area(self, uid: int, product: Product, width_mm: int, height_mm: int) -> None:
        result = calc.calc_area(width_mm, height_mm, product.width, product.length,
                                product.per_box, product.price, self.cfg.reserve_percent)
        self.clear(uid)
        await self.say(uid, texts.calc_result_area(product, result),
                       await self.calc_result_kb("ls", product, width_mm, height_mm))

    async def _finish_linear(self, uid: int, product: Product, length_mm: int) -> None:
        result = calc.calc_linear(length_mm, product.length, product.per_box, product.price, self.cfg.reserve_percent)
        self.clear(uid)
        await self.say(uid, texts.calc_result_linear(product, result),
                       await self.calc_result_kb("ll", product, length_mm))

    def _summary_from_callback(self, data: str) -> str | None:
        parts = data.split("|")
        catalog = self.store.get()
        if not catalog or len(parts) < 3 or not all(p.isdigit() for p in parts[2:]):
            return None
        product = catalog.find(parts[1])
        if not product:
            return None
        nums = [int(p) for p in parts[2:]]
        try:
            if parts[0] == "ls" and len(nums) == 2 and product.is_area:
                result: calc.AreaResult | calc.LinearResult = calc.calc_area(
                    nums[0], nums[1], product.width, product.length, product.per_box, product.price,
                    self.cfg.reserve_percent)
            elif parts[0] == "ll" and len(nums) == 1 and not product.is_area:
                result = calc.calc_linear(nums[0], product.length, product.per_box, product.price,
                                          self.cfg.reserve_percent)
            else:
                return None
        except ValueError:
            return None
        return texts.calc_summary(product, result)

    async def cb_send_calc(self, ev: Incoming) -> None:
        if not self.collect:
            await self.lead_elsewhere(ev.user_id, with_calc=True)
            return
        summary = self._summary_from_callback(ev.data or "")
        if not summary:
            await self.show(ev, texts.CALC_EXPIRED)
            return
        await self.drop_kb(ev)
        await self.begin_lead(ev, summary)

    # ------------------------------------------------------------------ заявка
    async def lead_elsewhere(self, uid: int, with_calc: bool = False) -> None:
        max_link = await self.bot_link(CH_MAX)
        kb = ikb([Btn(texts.BTN_LEAD_SITE, url=self.cfg.site_link("#order"))] if self.cfg.site_url else None,
                 [Btn(texts.BTN_OPEN_MAX, url=f"{max_link}?start=lead")] if max_link else None)
        await self.say(uid, texts.lead_elsewhere(bool(self.cfg.site_url), bool(max_link), with_calc),
                       kb if kb.rows else client_menu())

    async def open_lead(self, ev: Incoming, me: Person | None) -> None:
        if not self.collect:
            self.clear(ev.user_id)
            await self.lead_elsewhere(ev.user_id)
            return
        await self.begin_lead(ev, "")

    async def begin_lead(self, ev: Incoming, calc_summary: str) -> None:
        self.set_state(ev.user_id, "lead_name", calc=calc_summary)
        rows: list[list[str | Btn]] = []
        if ev.first_name and len(ev.first_name) <= 60 and ev.first_name not in texts.MENU_BUTTONS:
            rows.append([ev.first_name])
        rows.append([texts.BTN_CANCEL])
        await self.say(ev.user_id, texts.lead_ask_name(bool(calc_summary)), rkb(*rows))

    def contact_kb(self) -> Kb:
        return rkb([Btn(texts.BTN_SEND_PHONE, contact=True)], [texts.btn_write_here(self.ch)], [texts.BTN_CANCEL])

    async def lead_step(self, ev: Incoming, me: Person | None, st: str) -> None:
        uid = ev.user_id
        if st == "lead_name":
            name = re.sub(r"\s+", " ", ev.text or "").strip()
            if not name or len(name) > 60 or name.startswith("/"):
                await self.say(uid, texts.LEAD_BAD_NAME)
                return
            self.go(uid, "lead_contact", name=name)
            await self.say(uid, texts.lead_ask_contact(self.ch), self.contact_kb())
        elif st == "lead_contact":
            contact: str | None = None
            if ev.contact_phone:
                contact = phone_from_contact(ev.contact_phone) or None
            elif ev.text == texts.btn_write_here(self.ch):
                contact = texts.contact_here(self.ch, ev.username)
            elif ev.text:
                contact = parse_contact(ev.text)
            if not contact:
                await self.say(uid, texts.lead_bad_contact(self.ch), self.contact_kb())
                return
            self.go(uid, "lead_comment", contact=contact)
            await self.say(uid, texts.LEAD_ASK_COMMENT, rkb([texts.BTN_SKIP, texts.BTN_CANCEL]))
        elif st == "lead_comment":
            text = ev.text if ev.text is not None else (ev.caption or None)
            if text is None:
                await self.say(uid, texts.LEAD_BAD_COMMENT)
                return
            comment = "" if text == texts.BTN_SKIP else text.strip()
            if len(comment) > 1000:
                comment = comment[:999] + "…"
            self.go(uid, "lead_consent", comment=comment)
            data = self.data(uid)
            await self.say(uid, texts.lead_review(data.get("name", ""), data.get("contact", ""), comment,
                                                  data.get("calc", "")), self.menu(me))
            await self.say(uid, texts.consent_text(self.cfg.site_url, self.cfg.operator_name),
                           ikb([Btn(texts.BTN_AGREE, "lead|yes"), Btn(texts.BTN_CANCEL, "lead|no")]))
        else:  # lead_consent
            await self.say(uid, f"Нажмите «{texts.BTN_AGREE}» или «{texts.BTN_CANCEL}» под сообщением выше.",
                           ikb([Btn(texts.BTN_AGREE, "lead|yes"), Btn(texts.BTN_CANCEL, "lead|no")]))

    async def cb_lead_consent(self, ev: Incoming, me: Person | None) -> None:
        uid = ev.user_id
        await self.drop_kb(ev)
        if self.state(uid) != "lead_consent":
            await self.say(uid, texts.LEAD_EXPIRED, self.menu(me))
            return
        data = self.data(uid)
        self.clear(uid)
        if (ev.data or "").endswith("|no"):
            await self.say(uid, texts.LEAD_CANCELLED, self.menu(me))
            return
        client = await self.db.upsert_client(self.ch, uid, ev.username, ev.full_name)
        lead_id = await self.db.add_lead(client=client, name=data.get("name", ""), contact=data.get("contact", ""),
                                         comment=data.get("comment", ""), calc=data.get("calc", ""),
                                         consent_at=iso_now(), consent_version=self.cfg.consent_version)
        log.info("заявка №%d сохранена (%s)", lead_id, self.ch)
        await self.say(uid, texts.lead_thanks(lead_id), self.menu(me))
        seats = await self.notify(self.team.all(), {"t": "lead", "lead_id": lead_id}, client.id)
        if not seats:
            log.warning("заявка №%d никому не отправлена: в команде пока никого (/owner КОД)", lead_id)

    # ------------------------------------------------------------------ сообщения клиентов
    async def client_message(self, ev: Incoming) -> None:
        uid = ev.user_id
        if ev.text and ev.text.startswith("/"):
            await self.say(uid, texts.help_client(self.cfg.site_url), client_menu())
            return
        kind = "text" if ev.text is not None else KIND_NAMES.get(ev.kind, ev.kind)
        body = ev.text if ev.text is not None else ev.caption
        if ev.kind == "contact" and ev.contact_phone:
            body = phone_from_contact(ev.contact_phone)
        client = await self.db.upsert_client(self.ch, uid, ev.username, ev.full_name)
        msg_id = await self.db.add_message(client=client, direction="in", kind=kind, text=body)
        recipients = self.team.message_recipients()
        if self.collect:
            item = {"t": "msg", "message_id": msg_id, "src": self.ch, "group": ev.media_group,
                    "media": ev.media if kind != "text" else None}
        else:
            item = {"t": "msg_notice", "client_id": client.id, "kind": kind}
        seats = await self.notify(recipients, item, client.id)
        if not seats:
            log.warning("сообщение клиента сохранено, но в команде пока никого нет")
        if self.collect and yagpt.is_enabled(self.cfg) and kind == "text" and seats:
            draft = await yagpt.suggest_reply(self.cfg, body or "")
            if draft:
                await self.notify(recipients, {"t": "text", "client_id": client.id,
                                               "text": "Черновик ответа (клиенту не отправлен):\n" + texts.esc(draft)},
                                  client.id)
        if self.rt.need_ack(uid):
            await self.say(uid, texts.MESSAGE_RECEIVED, client_menu())

    # ------------------------------------------------------------------ удаление данных
    async def cb_delete(self, ev: Incoming, me: Person | None) -> None:
        uid = ev.user_id
        await self.drop_kb(ev)
        if not (ev.data or "").endswith("|yes"):
            await self.say(uid, texts.DELETE_CANCELLED, self.menu(me))
            return
        client = await self.db.find_client(self.ch, uid)
        leads = kept = messages = 0
        if client:
            leads, kept, messages = await self.db.delete_client(client.id)
            log.info("клиент отозвал согласие: удалено заявок %d, сообщений %d, оставлено заказов %d",
                     leads, messages, kept)
            if leads or messages or kept:
                note = texts.client_deleted("", client.id, client.channel, leads, kept, messages, pii=False)
                await self.notify(self.team.managers(), {"t": "text", "text": note})
        await self.say(uid, texts.delete_done(leads, kept, messages), self.menu(me))

    # ------------------------------------------------------------------ вход в команду
    async def _after_join(self, ev: Incoming, role: str, linked: bool) -> None:
        uid = ev.user_id
        await self.team.refresh(self.db)
        me = self.team.person_of(self.ch, uid)
        with contextlib.suppress(Exception):
            await self.t.set_commands(uid, role)
        log.info("в команде: %s подключён (%s)", role, self.ch)
        await self.say(uid, texts.joined(role, self.ch, linked), team_menu(role))
        note = texts.member_joined(ev.full_name, role, self.ch, linked)
        await self.notify(self.team.managers(), {"t": "text", "text": note},
                          exclude=me.person_id if me else None)

    async def cmd_owner(self, ev: Incoming, me: Person | None, args: str) -> None:
        uid = ev.user_id
        if me:
            await self.say(uid, texts.OWNER_ALREADY, self.menu(me))
            return
        code = re.sub(r"\s+", "", args)
        if not code:
            await self.say(uid, texts.OWNER_USAGE)
            return
        if not self.cfg.owner_code:
            await self.say(uid, texts.OWNER_NO_CODE)
            return
        if not self.limiter.allow(uid):
            await self.say(uid, texts.CODE_LOCKED)
            return
        if not hmac.compare_digest(code.encode(), self.cfg.owner_code.encode()) or \
                not await self.db.claim_owner_code(code, self.ch, uid, ev.username, ev.full_name):
            log.warning("/owner: неверный или уже использованный код")
            await self.say(uid, texts.CODE_BAD)
            return
        await self._after_join(ev, ROLE_MANAGER, False)

    async def cmd_join(self, ev: Incoming, me: Person | None, args: str) -> None:
        uid = ev.user_id
        code = re.sub(r"\s+", "", args)
        if not code:
            await self.say(uid, texts.JOIN_USAGE)
            return
        if not self.limiter.allow(uid):
            await self.say(uid, texts.CODE_LOCKED)
            return
        if me and me.role == ROLE_MANAGER and self.team.managers() == [me.person_id]:
            # единственный менеджер не может сам себя «понизить» — иначе некому будет приглашать
            await self.say(uid, texts.JOIN_LAST_MANAGER, self.menu(me))
            return
        result = await self.db.use_invite(code, self.ch, uid, ev.username, ev.full_name) if code.isdigit() else None
        if not result:
            log.warning("/join: неверный, использованный или просроченный код")
            await self.say(uid, texts.CODE_BAD)
            return
        await self._after_join(ev, result[0], result[1])

    async def send_invite(self, uid: int, me: Person, role: str) -> None:
        code = await self.db.create_invite(role, me.person_id)
        links = {ch: await self.bot_link(ch) for ch in self.enabled}
        await self.say(uid, texts.invite_text(role, code, links))

    async def cmd_invite(self, uid: int, me: Person, args: str) -> None:
        role = {"manager": ROLE_MANAGER, "менеджер": ROLE_MANAGER, "shipping": ROLE_SHIPPING,
                "отгрузка": ROLE_SHIPPING}.get(args.strip().lower())
        if not role:
            await self.say(uid, texts.INVITE_USAGE, self.invite_kb())
            return
        await self.send_invite(uid, me, role)

    @staticmethod
    def invite_kb() -> Kb:
        return ikb([Btn(texts.BTN_INVITE_MANAGER, "inv|manager")], [Btn(texts.BTN_INVITE_SHIPPING, "inv|shipping")])

    async def cb_link(self, ev: Incoming, me: Person, channel: str) -> None:
        if channel not in CHANNELS or channel in me.channels:
            return
        code = await self.db.create_invite(ROLE_LINK, me.person_id, person_id=me.person_id)
        await self.say(ev.user_id, texts.link_text(channel, code, await self.bot_link(channel)))

    async def cmd_team(self, uid: int, me: Person) -> None:
        kb = self.invite_kb()
        for p in self.team.persons():
            if p.person_id != me.person_id and not p.static:
                kb.rows.append([Btn(f"Убрать: {p.name or p.person_id}"[:60], f"rm|{p.person_id}")])
        await self.say(uid, texts.team_list(self.team.persons(), me.person_id), kb)

    async def _remove_person(self, person_id: int) -> str:
        person = self.team.person(person_id)
        if not person:
            return texts.REMOVE_NOT_FOUND
        if person.static:
            return texts.REMOVE_STATIC
        if person.role == ROLE_MANAGER and len(self.team.managers()) <= 1:
            return texts.REMOVE_LAST_MANAGER
        await self.db.remove_person(person_id)
        log.info("человек убран из команды")
        for s in person.seats:
            await self.post(s.channel, s.user_id, {"t": "removed"})
        await self.team.refresh(self.db)
        return texts.removed(person.name)

    async def cmd_remove(self, uid: int, args: str) -> None:
        arg = args.strip().lstrip("№#")
        if not arg.isdigit():
            await self.say(uid, texts.REMOVE_USAGE)
            return
        await self.say(uid, await self._remove_person(int(arg)))

    async def cb_remove(self, ev: Incoming) -> None:
        action, _, arg = (ev.data or "").partition("|")
        if action == "rmn":
            await self.show(ev, texts.CANCELLED)
            return
        if not arg.isdigit():
            return
        if action == "rm":
            person = self.team.person(int(arg))
            if not person:
                await self.show(ev, texts.REMOVE_NOT_FOUND)
                return
            await self.say(ev.user_id, texts.remove_confirm(person.name),
                           ikb([Btn(texts.BTN_REMOVE_YES, f"rmy|{arg}"), Btn(texts.BTN_CANCEL, "rmn")]))
            return
        await self.show(ev, await self._remove_person(int(arg)))

    async def cmd_notify(self, uid: int, me: Person, args: str) -> None:
        arg = args.strip().lower()
        if arg in (NOTIFY_ALL, NOTIFY_ORDERS):
            await self.db.set_notify(me.person_id, arg)
            await self.say(uid, texts.notify_set(arg))
            return
        if arg:
            await self.say(uid, texts.NOTIFY_USAGE)
        mark = "• "
        rows = [[Btn((mark if me.notify == NOTIFY_ALL else "") + texts.BTN_NOTIFY_ALL, "ntf|all")],
                [Btn((mark if me.notify == NOTIFY_ORDERS else "") + texts.BTN_NOTIFY_ORDERS, "ntf|orders")]]
        deliver = self.team.deliver_channel(me, self.enabled, self.cfg.staff_default_channel)
        if len(me.channels) > 1:
            rows.append([Btn((mark if deliver == ch else "") + texts.btn_deliver(ch), f"dlv|{ch}")
                         for ch in me.channels])
        for ch in self.enabled:
            if ch not in me.channels:
                rows.append([Btn(texts.btn_link(ch), f"lnk|{ch}")])
        await self.say(uid, texts.notify_current(me.notify, deliver, me.channels), Kb(rows))

    # ------------------------------------------------------------------ заявки, переписка, ответы
    def history_btn(self, client_id: int) -> Btn:
        return Btn(texts.BTN_HISTORY, f"hist|{client_id}")

    def lead_kb(self, lead: Lead, role: str) -> Kb:
        rows: list[list[Btn] | None] = []
        if role == ROLE_MANAGER and self.collect:
            rows.append([Btn(texts.BTN_TO_SHIPPING, f"shp|{lead.id}")])
        rows.append([self.history_btn(lead.client_id)])
        return ikb(*rows)

    def ship_kb(self, ship: Shipment, is_manager: bool) -> Kb:
        rows: list[list[Btn] | None] = []
        if not ship.cancelled_ts:
            if ship.status == ST_CONFIRMED:
                rows.append([Btn(texts.BTN_SHIP_ACCEPT, f"sh|acc|{ship.lead_id}"),
                             Btn(texts.BTN_SHIP_DONE, f"sh|done|{ship.lead_id}")])
            elif ship.status == ST_SHIPPING:
                rows.append([Btn(texts.BTN_SHIP_DONE, f"sh|done|{ship.lead_id}")])
            if is_manager and ship.status in (ST_CONFIRMED, ST_SHIPPING):
                rows.append([Btn(texts.BTN_SHIP_CANCEL, f"sh|cancel|{ship.lead_id}")])
        rows.append([self.history_btn(ship.client_id)])
        return ikb(*rows)

    async def cmd_leads(self, uid: int) -> None:
        leads = await self.db.last_leads(10)
        if not leads:
            await self.say(uid, texts.LEADS_EMPTY)
            return
        buttons = [Btn(f"№{lead.id}", f"ld|{lead.id}") for lead in leads]
        await self.say(uid, texts.leads_list(leads, self.collect), Kb([buttons[i:i + 5] for i in range(0, 10, 5)
                                                                      if buttons[i:i + 5]]))

    async def send_lead_card(self, uid: int, me: Person, lead: Lead) -> None:
        mid = await self.say(uid, texts.lead_card(lead, "Заявка", self.collect), self.lead_kb(lead, me.role))
        await self.relay(uid, mid, lead.client_id, lead.id)

    async def cmd_lead(self, uid: int, me: Person, args: str) -> None:
        m = _LEAD_REF_RE.match(args.strip())
        if not m:
            await self.say(uid, texts.LEAD_USAGE)
            return
        lead = await self.db.get_lead(int(m.group(1)))
        if not lead:
            await self.say(uid, texts.NO_SUCH_LEAD)
            return
        await self.send_lead_card(uid, me, lead)

    async def cb_open_lead(self, ev: Incoming, me: Person) -> None:
        arg = (ev.data or "").split("|", 1)[-1]
        lead = await self.db.get_lead(int(arg)) if arg.isdigit() else None
        if not lead:
            await self.say(ev.user_id, texts.NO_SUCH_LEAD)
            return
        await self.send_lead_card(ev.user_id, me, lead)

    async def resolve_client(self, arg: str) -> int | None:
        """«К5» — клиент №5; «12», «#12», «№12» — клиент из заявки №12."""
        arg = arg.strip()
        m = _CLIENT_REF_RE.match(arg)
        if m:
            client = await self.db.get_client(int(m.group(1)))
            return client.id if client else None
        m = _LEAD_REF_RE.match(arg)
        if m:
            lead = await self.db.get_lead(int(m.group(1)))
            return lead.client_id if lead else None
        return None

    async def send_history(self, uid: int, client_id: int) -> None:
        client = await self.db.get_client(client_id)
        if not client:
            await self.say(uid, texts.NO_SUCH_LEAD)
            return
        parts = texts.history(client.name, client.username, client.id, client.channel,
                              await self.db.client_leads(client.id), await self.db.history(client.id), self.collect)
        for part in parts:
            mid = await self.say(uid, part)
            await self.relay(uid, mid, client.id)

    async def cmd_history(self, uid: int, args: str) -> None:
        if not args.strip():
            await self.say(uid, texts.HISTORY_USAGE)
            return
        client_id = await self.resolve_client(args)
        if client_id is None:
            await self.say(uid, texts.NO_SUCH_LEAD)
            return
        await self.send_history(uid, client_id)

    async def send_to_client(self, ev: Incoming, me: Person, client_id: int, text: str | None = None) -> None:
        client: Client | None = await self.db.get_client(client_id)
        if not client:
            await self.say(ev.user_id, texts.NO_SUCH_LEAD)
            return
        body = text if text is not None else ev.text
        if body is None and client.channel != self.ch:
            await self.say(ev.user_id, texts.media_other_channel(client.channel))
            return
        item = {"t": "to_client", "client_id": client.id, "text": body,
                "media": ev.media if body is None else None, "caption": ev.caption,
                "kind": KIND_NAMES.get(ev.kind, ev.kind),
                "staff": {"ch": self.ch, "uid": ev.user_id, "pid": me.person_id,
                          "name": self.team.name(me.person_id) or ev.first_name, "reply_to": ev.message_id}}
        if client.channel != self.ch:
            await self.say(ev.user_id, texts.sending_to(client.channel))
        await self.post(client.channel, client.user_id, item, client.id)

    async def staff_reply(self, ev: Incoming, me: Person) -> None:
        client_id = await self.db.relay_target(self.ch, ev.user_id, ev.reply_to)
        if client_id is None:
            await self.say(ev.user_id, texts.NOT_REPLY_TARGET)
            return
        await self.send_to_client(ev, me, client_id)

    async def cmd_reply(self, ev: Incoming, me: Person, args: str) -> None:
        m = re.match(r"^\s*(\S+)\s+(.+)$", args, flags=re.S)
        if not m:
            await self.say(ev.user_id, texts.REPLY_USAGE)
            return
        client_id = await self.resolve_client(m.group(1))
        if client_id is None:
            await self.say(ev.user_id, texts.NO_SUCH_LEAD)
            return
        await self.send_to_client(ev, me, client_id, text=m.group(2).strip())

    # ------------------------------------------------------------------ отгрузка
    async def cb_ship_start(self, ev: Incoming) -> None:
        uid = ev.user_id
        if not self.collect:
            await self.say(uid, texts.SHIP_ONLY_IN_MAX)
            return
        arg = (ev.data or "").split("|", 1)[-1]
        lead = await self.db.get_lead(int(arg)) if arg.isdigit() else None
        if not lead:
            await self.say(uid, texts.SHIP_LEAD_MISSING)
            return
        default_items = lead.calc or lead.comment
        self.set_state(uid, "ship_items", lead_id=lead.id, default_items=default_items,
                       default_phone=parse_phone(lead.contact) or "",
                       old_status=lead.status if lead.status != ST_NEW else "")
        await self.say(uid, texts.ship_ask_items(lead.id, default_items),
                       self.step_kb(texts.BTN_AS_IN_LEAD) if default_items else self.step_kb())

    @staticmethod
    def step_kb(*first_row: str) -> Kb:
        return rkb(list(first_row) if first_row else [], [texts.BTN_CANCEL])

    @staticmethod
    def _ship_text(text: str | None, limit: int) -> str | None:
        text = (text or "").strip()
        if not text or text.startswith("/"):
            return None
        return text if len(text) <= limit else text[: limit - 1] + "…"

    async def ship_step(self, ev: Incoming, me: Person, st: str) -> None:
        uid, data = ev.user_id, self.data(ev.user_id)
        if st == "ship_items":
            items = data.get("default_items") if ev.text == texts.BTN_AS_IN_LEAD and data.get("default_items") \
                else self._ship_text(ev.text, 1000)
            if not items:
                await self.say(uid, texts.SHIP_BAD_TEXT)
                return
            self.go(uid, "ship_address", items=items)
            await self.say(uid, texts.SHIP_ASK_ADDRESS, self.step_kb(texts.BTN_PICKUP))
        elif st == "ship_address":
            address = "Самовывоз" if ev.text == texts.BTN_PICKUP else self._ship_text(ev.text, 300)
            if not address:
                await self.say(uid, texts.SHIP_BAD_TEXT)
                return
            self.go(uid, "ship_when", address=address)
            await self.say(uid, texts.SHIP_ASK_WHEN, self.step_kb(texts.BTN_TODAY, texts.BTN_TOMORROW))
        elif st == "ship_when":
            today = now_local()
            if ev.text == texts.BTN_TODAY:
                when: str | None = f"сегодня, {today.strftime('%d.%m')}"
            elif ev.text == texts.BTN_TOMORROW:
                when = f"завтра, {(today + timedelta(days=1)).strftime('%d.%m')}"
            else:
                when = self._ship_text(ev.text, 100)
            if not when:
                await self.say(uid, texts.SHIP_BAD_TEXT)
                return
            self.go(uid, "ship_phone", when=when)
            default_phone = data.get("default_phone", "")
            await self.say(uid, texts.ship_ask_phone(default_phone),
                           self.step_kb(texts.BTN_AS_IN_LEAD) if default_phone else self.step_kb())
        elif st == "ship_phone":
            if ev.text == texts.BTN_AS_IN_LEAD and data.get("default_phone"):
                phone: str | None = data["default_phone"]
            elif ev.contact_phone:
                phone = phone_from_contact(ev.contact_phone)
            else:
                phone = parse_phone(ev.text or "")
            if not phone:
                await self.say(uid, texts.SHIP_BAD_PHONE)
                return
            self.go(uid, "ship_confirm", phone=phone)
            await self.say(uid, texts.SHIP_CHECK, self.menu(me))
            await self.say(uid, texts.ship_review(data["lead_id"], data["items"], data["address"], data["when"],
                                                  phone, data.get("old_status", "")),
                           ikb([Btn(texts.BTN_TO_SHIPPING, "shc|yes"), Btn(texts.BTN_CANCEL, "shc|no")]))
        else:
            await self.say(uid, f"Нажмите «{texts.BTN_TO_SHIPPING}» или «{texts.BTN_CANCEL}» под сообщением выше.")

    async def cb_ship_confirm(self, ev: Incoming, me: Person) -> None:
        uid = ev.user_id
        await self.drop_kb(ev)
        if self.state(uid) != "ship_confirm":
            await self.say(uid, texts.SHIP_EXPIRED)
            return
        data = self.data(uid)
        self.clear(uid)
        if (ev.data or "").endswith("|no"):
            await self.say(uid, texts.CANCELLED, self.menu(me))
            return
        actor_name = self.team.name(me.person_id) or ev.full_name
        ship = await self.db.save_shipment(int(data["lead_id"]), items=data["items"], address=data["address"],
                                           when_text=data["when"], phone=data["phone"], by_id=me.person_id,
                                           by_name=actor_name)
        if ship is None:
            await self.say(uid, texts.SHIP_LEAD_MISSING)
            return
        log.info("заявка №%d передана на отгрузку", ship.lead_id)
        seats = await self.notify(self.team.shipping(), {"t": "ship", "lead_id": ship.lead_id}, ship.client_id,
                                  exclude=me.person_id)
        mid = await self.say(uid, texts.shipment_card(ship, self.collect), self.ship_kb(ship, True))
        await self.relay(uid, mid, ship.client_id, ship.lead_id)
        receivers = [f"{self.team.name(s.person_id) or 'сотрудник'} ({texts.ch_name(s.channel)})" for s in seats]
        await self.say(uid, texts.ship_created(ship.lead_id, receivers), self.menu(me))
        await self.notify(self.team.managers(), {"t": "ship_note", "lead_id": ship.lead_id, "action": "created",
                                                 "by": actor_name}, exclude=me.person_id)

    async def cb_ship_action(self, ev: Incoming, me: Person) -> str:
        parts = (ev.data or "").split("|")
        if len(parts) != 3 or parts[1] not in ("acc", "done", "cancel") or not parts[2].isdigit():
            return ""
        action = {"acc": "accept", "done": "done", "cancel": "cancel"}[parts[1]]
        if action == "cancel" and me.role != ROLE_MANAGER:
            return texts.ONLY_MANAGER
        actor_name = self.team.name(me.person_id) or ev.full_name
        result, ship = await self.db.change_shipment(int(parts[2]), action, me.person_id, actor_name)
        if ship and ev.message_id:
            await self.t.edit(ev.user_id, ev.message_id, texts.shipment_card(ship, self.collect),
                              self.ship_kb(ship, me.role == ROLE_MANAGER))
        if result == "ok" and ship:
            log.info("отгрузка №%d: %s", ship.lead_id, action)
            receivers = set(self.team.managers())
            if action == "cancel":
                receivers |= set(self.team.shipping())
            await self.notify(sorted(receivers), {"t": "ship_note", "lead_id": ship.lead_id, "action": action,
                                                  "by": actor_name}, exclude=me.person_id)
        return texts.SHIP_TOAST.get(result, "")

    async def cmd_orders(self, uid: int, me: Person) -> None:
        ships = await self.db.open_shipments(10)
        if not ships:
            await self.say(uid, texts.ORDERS_EMPTY)
            return
        await self.say(uid, texts.orders_head(len(ships)))
        for ship in ships:
            mid = await self.say(uid, texts.shipment_card(ship, self.collect),
                                 self.ship_kb(ship, me.role == ROLE_MANAGER))
            await self.relay(uid, mid, ship.client_id, ship.lead_id)

    async def cmd_stats(self, uid: int) -> None:
        stats = await self.db.stats()
        catalog = self.store.get()
        when = time.strftime("%d.%m %H:%M", time.localtime(catalog.loaded_at)) if catalog else "—"
        queues = {ch: await self.db.outbox_count(ch) for ch in CHANNELS}
        await self.say(uid, texts.stats(stats, len(catalog) if catalog else 0, catalog.source if catalog else "нет",
                                        when, self.store.last_error, queues))

    async def cmd_reload(self, uid: int) -> None:
        catalog = await self.store.reload()
        await self.say(uid, texts.reload_result(len(catalog) if catalog else 0,
                                                catalog.source if catalog else "", self.store.last_error))

