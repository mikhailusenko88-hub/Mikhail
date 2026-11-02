"""База бота: SQLite-файл на сервере (/var/lib/prostranstvo/bot.db).

Хранится: заявки и их статусы, отгрузки, сообщения клиентов и ответы магазина,
команда магазина (роли «менеджер» и «отгрузка»), одноразовые коды приглашений,
связи «сообщение в чате сотрудника → клиент» (чтобы ответ уходил нужному клиенту).
Данные клиентов никуда, кроме этого файла и чатов сотрудников, не уходят;
в журнал они не пишутся.

Работаем через стандартный sqlite3 в отдельном потоке (asyncio.to_thread),
одно соединение, доступ под замком.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

try:
    from zoneinfo import ZoneInfo

    TZ: Any = ZoneInfo("Europe/Moscow")
except Exception:  # pragma: no cover - нет базы часовых поясов
    TZ = timezone(timedelta(hours=3), "MSK")

T = TypeVar("T")

SCHEMA_VERSION = 1
ROLE_MANAGER = "manager"
ROLE_SHIPPING = "shipping"
ROLES = (ROLE_MANAGER, ROLE_SHIPPING)
NOTIFY_ALL = "all"        # все сообщения клиентов + заявки + отгрузки
NOTIFY_ORDERS = "orders"  # только заявки и отгрузки
INVITE_TTL_SEC = 24 * 3600

# Статусы заявки: новая → подтверждена (передана на отгрузку) → на отгрузке (принял) → отгружено
ST_NEW = "new"
ST_CONFIRMED = "confirmed"
ST_SHIPPING = "shipping"
ST_SHIPPED = "shipped"
OPEN_SHIPMENT = (ST_CONFIRMED, ST_SHIPPING)
KEEP_ON_DELETE = (ST_CONFIRMED, ST_SHIPPING, ST_SHIPPED)  # заказ по договору — храним

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts      INTEGER NOT NULL,
    created_at      TEXT    NOT NULL,
    tg_id           INTEGER NOT NULL,
    username        TEXT,
    name            TEXT    NOT NULL,
    contact         TEXT    NOT NULL,
    comment         TEXT,
    calc            TEXT,
    consent_at      TEXT    NOT NULL,
    consent_version TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'new',
    status_ts       INTEGER
);
CREATE INDEX IF NOT EXISTS leads_ts ON leads(created_ts);
CREATE INDEX IF NOT EXISTS leads_tg ON leads(tg_id);

CREATE TABLE IF NOT EXISTS shipments (
    lead_id       INTEGER PRIMARY KEY REFERENCES leads(id) ON DELETE CASCADE,
    items         TEXT NOT NULL,
    address       TEXT NOT NULL,
    when_text     TEXT NOT NULL,
    phone         TEXT NOT NULL,
    created_by    INTEGER,
    created_name  TEXT,
    created_ts    INTEGER NOT NULL,
    accepted_by   INTEGER,
    accepted_name TEXT,
    accepted_ts   INTEGER,
    shipped_by    INTEGER,
    shipped_name  TEXT,
    shipped_ts    INTEGER,
    cancelled_ts  INTEGER
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    tg_id       INTEGER NOT NULL,          -- клиент
    username    TEXT,
    name        TEXT,
    direction   TEXT    NOT NULL,          -- 'in' от клиента, 'out' ответ магазина
    kind        TEXT    NOT NULL DEFAULT 'text',
    text        TEXT,
    admin_id    INTEGER,                   -- кто из команды ответил (для 'out')
    admin_name  TEXT
);
CREATE INDEX IF NOT EXISTS messages_ts ON messages(created_ts);
CREATE INDEX IF NOT EXISTS messages_tg ON messages(tg_id);

-- сообщение в чате сотрудника → клиент, которому уйдёт ответ на него
CREATE TABLE IF NOT EXISTS relay (
    admin_chat_id    INTEGER NOT NULL,
    admin_message_id INTEGER NOT NULL,
    tg_id            INTEGER NOT NULL,
    lead_id          INTEGER,
    created_ts       INTEGER NOT NULL,
    PRIMARY KEY (admin_chat_id, admin_message_id)
);
CREATE INDEX IF NOT EXISTS relay_tg ON relay(tg_id);

CREATE TABLE IF NOT EXISTS team (
    tg_id     INTEGER PRIMARY KEY,
    username  TEXT,
    name      TEXT,
    role      TEXT NOT NULL,               -- 'manager' | 'shipping'
    notify    TEXT NOT NULL,               -- 'all' | 'orders'
    added_at  TEXT NOT NULL,
    added_by  INTEGER
);

CREATE TABLE IF NOT EXISTS invites (
    code_hash  TEXT PRIMARY KEY,
    role       TEXT    NOT NULL,
    created_ts INTEGER NOT NULL,
    expires_ts INTEGER NOT NULL,
    created_by INTEGER,
    used_by    INTEGER,
    used_ts    INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now_local() -> datetime:
    return datetime.now(TZ)


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")


def fmt_ts(ts: int | None, fmt: str = "%d.%m %H:%M") -> str:
    return datetime.fromtimestamp(ts, TZ).strftime(fmt) if ts else ""


def code_hash(code: str, purpose: str = "owner") -> str:
    return hashlib.sha256(f"prostranstvo-{purpose}:{code}".encode()).hexdigest()


def default_notify(role: str) -> str:
    return NOTIFY_ALL if role == ROLE_MANAGER else NOTIFY_ORDERS


@dataclass(frozen=True)
class Lead:
    id: int
    created_ts: int
    created_at: str
    tg_id: int
    username: str
    name: str
    contact: str
    comment: str
    calc: str
    consent_at: str
    consent_version: str
    status: str
    status_ts: int

    @property
    def created_dt(self) -> datetime:
        return datetime.fromtimestamp(self.created_ts, TZ)


@dataclass(frozen=True)
class Shipment:
    lead_id: int
    items: str
    address: str
    when_text: str
    phone: str
    created_by: int
    created_name: str
    created_ts: int
    accepted_by: int
    accepted_name: str
    accepted_ts: int
    shipped_by: int
    shipped_name: str
    shipped_ts: int
    cancelled_ts: int
    # из заявки
    status: str
    client_name: str
    client_username: str
    client_tg_id: int


@dataclass(frozen=True)
class Member:
    tg_id: int
    username: str
    name: str
    role: str
    notify: str
    added_at: str


@dataclass(frozen=True)
class HistoryItem:
    created_ts: int
    direction: str
    kind: str
    text: str
    admin_name: str


@dataclass(frozen=True)
class Stats:
    leads_today: int
    leads_week: int
    leads_total: int
    messages_today: int
    messages_week: int
    clients_week: int
    shipments_open: int
    shipped_week: int


def _clean(row: sqlite3.Row) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in row.keys():  # noqa: SIM118 - у sqlite3.Row итерация идёт по значениям
        value = row[key]
        out[key] = value if value is not None else ("" if key not in _INT_FIELDS else 0)
    return out


_INT_FIELDS = {"status_ts", "created_by", "accepted_by", "accepted_ts", "shipped_by", "shipped_ts",
               "cancelled_ts", "created_ts", "client_tg_id"}


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ служебное
    def _connect(self) -> sqlite3.Connection:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        old_umask = os.umask(0o077)  # файл базы — только для пользователя бота
        try:
            conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        finally:
            os.umask(old_umask)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES ('schema_version', ?)",
                     (str(SCHEMA_VERSION),))
        conn.commit()
        return conn

    def _run(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            try:
                result = fn(self._conn)
                self._conn.commit()
                return result
            except BaseException:
                self._conn.rollback()
                raise

    async def _call(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self._run, fn)

    async def init(self) -> None:
        await self._call(lambda c: None)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------ заявки
    async def add_lead(
        self, *, tg_id: int, username: str | None, name: str, contact: str,
        comment: str | None, calc: str | None, consent_at: str, consent_version: str,
    ) -> int:
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> int:
            cur = c.execute(
                "INSERT INTO leads(created_ts, created_at, tg_id, username, name, contact, comment,"
                " calc, consent_at, consent_version, status, status_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts, iso_now(), tg_id, username or "", name, contact, comment or "", calc or "",
                 consent_at, consent_version, ST_NEW, ts),
            )
            return int(cur.lastrowid or 0)

        return await self._call(q)

    async def get_lead(self, lead_id: int) -> Lead | None:
        def q(c: sqlite3.Connection) -> Lead | None:
            row = c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
            return Lead(**_clean(row)) if row else None

        return await self._call(q)

    async def last_leads(self, limit: int = 10) -> list[Lead]:
        def q(c: sqlite3.Connection) -> list[Lead]:
            rows = c.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [Lead(**_clean(r)) for r in rows]

        return await self._call(q)

    # ------------------------------------------------------------------ отгрузки
    _SHIP_SQL = (
        "SELECT s.*, l.status AS status, l.name AS client_name, l.username AS client_username,"
        " l.tg_id AS client_tg_id FROM shipments s JOIN leads l ON l.id = s.lead_id"
    )

    def _shipment(self, c: sqlite3.Connection, lead_id: int) -> Shipment | None:
        row = c.execute(self._SHIP_SQL + " WHERE s.lead_id = ?", (lead_id,)).fetchone()
        return Shipment(**_clean(row)) if row else None

    async def get_shipment(self, lead_id: int) -> Shipment | None:
        return await self._call(lambda c: self._shipment(c, lead_id))

    async def save_shipment(self, lead_id: int, *, items: str, address: str, when_text: str, phone: str,
                            by_id: int, by_name: str) -> Shipment | None:
        """Передать заявку на отгрузку (заново — тоже): статус «подтверждена»."""
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> Shipment | None:
            if not c.execute("SELECT 1 FROM leads WHERE id = ?", (lead_id,)).fetchone():
                return None
            c.execute(
                "INSERT OR REPLACE INTO shipments(lead_id, items, address, when_text, phone, created_by,"
                " created_name, created_ts) VALUES (?,?,?,?,?,?,?,?)",
                (lead_id, items, address, when_text, phone, by_id, by_name, ts),
            )
            c.execute("UPDATE leads SET status = ?, status_ts = ? WHERE id = ?", (ST_CONFIRMED, ts, lead_id))
            return self._shipment(c, lead_id)

        return await self._call(q)

    async def change_shipment(self, lead_id: int, action: str, by_id: int, by_name: str
                              ) -> tuple[str, Shipment | None]:
        """action: 'accept' | 'done' | 'cancel'.

        Ответ: ('ok' | 'already' | 'shipped' | 'cancelled' | 'missing', отгрузка).
        """
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> tuple[str, Shipment | None]:
            ship = self._shipment(c, lead_id)
            if ship is None:
                return "missing", None
            status = ship.status
            if ship.cancelled_ts or status == ST_NEW:
                return "cancelled", ship
            if status == ST_SHIPPED:
                return ("already" if action == "done" else "shipped"), ship
            if action == "accept":
                if status == ST_SHIPPING:
                    return "already", ship
                c.execute("UPDATE shipments SET accepted_by=?, accepted_name=?, accepted_ts=? WHERE lead_id=?",
                          (by_id, by_name, ts, lead_id))
                new_status = ST_SHIPPING
            elif action == "done":
                if not ship.accepted_ts:
                    c.execute("UPDATE shipments SET accepted_by=?, accepted_name=?, accepted_ts=?"
                              " WHERE lead_id=?", (by_id, by_name, ts, lead_id))
                c.execute("UPDATE shipments SET shipped_by=?, shipped_name=?, shipped_ts=? WHERE lead_id=?",
                          (by_id, by_name, ts, lead_id))
                new_status = ST_SHIPPED
            elif action == "cancel":
                c.execute("UPDATE shipments SET cancelled_ts=? WHERE lead_id=?", (ts, lead_id))
                new_status = ST_NEW
            else:
                return "missing", ship
            c.execute("UPDATE leads SET status = ?, status_ts = ? WHERE id = ?", (new_status, ts, lead_id))
            return "ok", self._shipment(c, lead_id)

        return await self._call(q)

    async def open_shipments(self, limit: int = 20) -> list[Shipment]:
        def q(c: sqlite3.Connection) -> list[Shipment]:
            rows = c.execute(
                self._SHIP_SQL + " WHERE l.status IN (?, ?) AND s.cancelled_ts IS NULL"
                " ORDER BY s.lead_id LIMIT ?", (*OPEN_SHIPMENT, limit),
            ).fetchall()
            return [Shipment(**_clean(r)) for r in rows]

        return await self._call(q)

    # ------------------------------------------------------------------ сообщения
    async def add_message(
        self, *, tg_id: int, username: str | None, name: str | None, direction: str,
        kind: str, text: str | None, admin_id: int | None = None, admin_name: str | None = None,
    ) -> int:
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> int:
            cur = c.execute(
                "INSERT INTO messages(created_ts, created_at, tg_id, username, name, direction,"
                " kind, text, admin_id, admin_name) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ts, iso_now(), tg_id, username or "", name or "", direction, kind, text or "",
                 admin_id, admin_name or ""),
            )
            return int(cur.lastrowid or 0)

        return await self._call(q)

    async def history(self, tg_id: int, limit: int = 30) -> list[HistoryItem]:
        def q(c: sqlite3.Connection) -> list[HistoryItem]:
            rows = c.execute(
                "SELECT created_ts, direction, kind, text, admin_name FROM messages WHERE tg_id = ?"
                " ORDER BY id DESC LIMIT ?", (tg_id, limit),
            ).fetchall()
            return [HistoryItem(**_clean(r)) for r in reversed(rows)]

        return await self._call(q)

    async def client_leads(self, tg_id: int) -> list[Lead]:
        def q(c: sqlite3.Connection) -> list[Lead]:
            rows = c.execute("SELECT * FROM leads WHERE tg_id = ? ORDER BY id", (tg_id,)).fetchall()
            return [Lead(**_clean(r)) for r in rows]

        return await self._call(q)

    async def add_relay(self, admin_chat_id: int, admin_message_id: int, tg_id: int,
                        lead_id: int | None = None) -> None:
        ts = int(time.time())
        await self._call(lambda c: c.execute(
            "INSERT OR REPLACE INTO relay(admin_chat_id, admin_message_id, tg_id, lead_id, created_ts)"
            " VALUES (?,?,?,?,?)",
            (admin_chat_id, admin_message_id, tg_id, lead_id, ts),
        ))

    async def relay_target(self, admin_chat_id: int, admin_message_id: int) -> int | None:
        def q(c: sqlite3.Connection) -> int | None:
            row = c.execute(
                "SELECT tg_id FROM relay WHERE admin_chat_id = ? AND admin_message_id = ?",
                (admin_chat_id, admin_message_id),
            ).fetchone()
            return int(row["tg_id"]) if row else None

        return await self._call(q)

    async def client_name(self, tg_id: int) -> tuple[str, str]:
        """(имя, username) клиента из последнего сообщения или заявки."""
        def q(c: sqlite3.Connection) -> tuple[str, str]:
            row = c.execute(
                "SELECT name, username FROM messages WHERE tg_id = ? AND direction = 'in'"
                " ORDER BY id DESC LIMIT 1", (tg_id,),
            ).fetchone() or c.execute(
                "SELECT name, username FROM leads WHERE tg_id = ? ORDER BY id DESC LIMIT 1", (tg_id,),
            ).fetchone()
            return (row["name"] or "", row["username"] or "") if row else ("", "")

        return await self._call(q)

    async def is_known_client(self, tg_id: int) -> bool:
        def q(c: sqlite3.Connection) -> bool:
            return bool(
                c.execute("SELECT 1 FROM messages WHERE tg_id = ? LIMIT 1", (tg_id,)).fetchone()
                or c.execute("SELECT 1 FROM leads WHERE tg_id = ? LIMIT 1", (tg_id,)).fetchone()
            )

        return await self._call(q)

    async def delete_client(self, tg_id: int) -> tuple[int, int, int]:
        """Отзыв согласия: удалить заявки и переписку клиента.

        Заявки, переданные на отгрузку или отгруженные, — это уже заказ (договор),
        их храним по закону. → (удалено заявок, оставлено заказов, удалено сообщений).
        """
        placeholders = ",".join("?" * len(KEEP_ON_DELETE))

        def q(c: sqlite3.Connection) -> tuple[int, int, int]:
            leads = c.execute(f"DELETE FROM leads WHERE tg_id = ? AND status NOT IN ({placeholders})",
                              (tg_id, *KEEP_ON_DELETE)).rowcount
            kept = c.execute("SELECT COUNT(*) FROM leads WHERE tg_id = ?", (tg_id,)).fetchone()[0]
            messages = c.execute("DELETE FROM messages WHERE tg_id = ?", (tg_id,)).rowcount
            if kept:
                c.execute("DELETE FROM relay WHERE tg_id = ? AND (lead_id IS NULL OR lead_id NOT IN"
                          " (SELECT id FROM leads WHERE tg_id = ?))", (tg_id, tg_id))
            else:
                c.execute("DELETE FROM relay WHERE tg_id = ?", (tg_id,))
            return leads, int(kept), messages

        result = await self._call(q)
        await self._call(lambda c: c.execute("PRAGMA wal_checkpoint(TRUNCATE)"))
        return result

    # ------------------------------------------------------------------ статистика
    async def stats(self) -> Stats:
        now = now_local()
        start_today = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        start_week = int((now - timedelta(days=7)).timestamp())

        def q(c: sqlite3.Connection) -> Stats:
            def one(sql: str, *args: Any) -> int:
                return int(c.execute(sql, args).fetchone()[0])

            return Stats(
                leads_today=one("SELECT COUNT(*) FROM leads WHERE created_ts >= ?", start_today),
                leads_week=one("SELECT COUNT(*) FROM leads WHERE created_ts >= ?", start_week),
                leads_total=one("SELECT COUNT(*) FROM leads"),
                messages_today=one(
                    "SELECT COUNT(*) FROM messages WHERE direction = 'in' AND created_ts >= ?", start_today),
                messages_week=one(
                    "SELECT COUNT(*) FROM messages WHERE direction = 'in' AND created_ts >= ?", start_week),
                clients_week=one(
                    "SELECT COUNT(DISTINCT tg_id) FROM (SELECT tg_id FROM messages WHERE direction = 'in'"
                    " AND created_ts >= ? UNION SELECT tg_id FROM leads WHERE created_ts >= ?)",
                    start_week, start_week),
                shipments_open=one("SELECT COUNT(*) FROM leads WHERE status IN (?, ?)", *OPEN_SHIPMENT),
                shipped_week=one("SELECT COUNT(*) FROM shipments WHERE shipped_ts >= ?", start_week),
            )

        return await self._call(q)

    # ------------------------------------------------------------------ команда
    async def team(self) -> list[Member]:
        def q(c: sqlite3.Connection) -> list[Member]:
            rows = c.execute("SELECT tg_id, username, name, role, notify, added_at FROM team"
                             " ORDER BY role, added_at").fetchall()
            return [Member(**_clean(r)) for r in rows]

        return await self._call(q)

    @staticmethod
    def _put_member(c: sqlite3.Connection, tg_id: int, username: str | None, name: str | None, role: str,
                    added_by: int | None) -> None:
        old = c.execute("SELECT role, notify FROM team WHERE tg_id = ?", (tg_id,)).fetchone()
        notify = old["notify"] if old and old["role"] == role else default_notify(role)
        c.execute(
            "INSERT OR REPLACE INTO team(tg_id, username, name, role, notify, added_at, added_by)"
            " VALUES (?,?,?,?,?,?,?)",
            (tg_id, username or "", name or "", role, notify, iso_now(), added_by),
        )

    async def add_member(self, tg_id: int, username: str | None, name: str | None, role: str,
                         added_by: int | None = None) -> None:
        if role not in ROLES:
            raise ValueError(role)
        await self._call(lambda c: self._put_member(c, tg_id, username, name, role, added_by))

    async def ensure_member(self, tg_id: int, role: str = ROLE_MANAGER) -> None:
        """Сотрудник из ADMIN_IDS (bot.env): добавить, если его ещё нет в базе."""
        await self._call(lambda c: c.execute(
            "INSERT OR IGNORE INTO team(tg_id, username, name, role, notify, added_at) VALUES (?,?,?,?,?,?)",
            (tg_id, "", "", role, default_notify(role), iso_now()),
        ))

    async def remove_member(self, tg_id: int) -> bool:
        return await self._call(lambda c: c.execute("DELETE FROM team WHERE tg_id = ?", (tg_id,)).rowcount > 0)

    async def set_notify(self, tg_id: int, mode: str) -> bool:
        if mode not in (NOTIFY_ALL, NOTIFY_ORDERS):
            raise ValueError(mode)
        return await self._call(
            lambda c: c.execute("UPDATE team SET notify = ? WHERE tg_id = ?", (mode, tg_id)).rowcount > 0)

    async def owner_code_used(self, code: str) -> bool:
        key = "owner_code_used:" + code_hash(code)
        return await self._call(
            lambda c: c.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone() is not None)

    async def claim_owner_code(self, code: str, tg_id: int, username: str | None, name: str | None) -> bool:
        """Код из установщика: первый, кто его отправит, становится менеджером. Код одноразовый."""
        key = "owner_code_used:" + code_hash(code)

        def q(c: sqlite3.Connection) -> bool:
            cur = c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, iso_now()))
            if cur.rowcount == 0:
                return False
            self._put_member(c, tg_id, username, name, ROLE_MANAGER, None)
            return True

        return await self._call(q)

    async def create_invite(self, role: str, created_by: int, ttl_sec: int = INVITE_TTL_SEC) -> str:
        """Новый одноразовый код приглашения (6 цифр, действует 24 часа)."""
        if role not in ROLES:
            raise ValueError(role)
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> str:
            c.execute("DELETE FROM invites WHERE expires_ts < ?", (ts - 30 * 24 * 3600,))
            for _ in range(20):
                code = f"{secrets.randbelow(900000) + 100000}"
                cur = c.execute(
                    "INSERT OR IGNORE INTO invites(code_hash, role, created_ts, expires_ts, created_by)"
                    " VALUES (?,?,?,?,?)", (code_hash(code, "invite"), role, ts, ts + ttl_sec, created_by))
                if cur.rowcount:
                    return code
            raise RuntimeError("не удалось создать код приглашения")

        return await self._call(q)

    async def use_invite(self, code: str, tg_id: int, username: str | None, name: str | None) -> str | None:
        """Принять приглашение: роль из кода или None (код неверный, использован или истёк)."""
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> str | None:
            h = code_hash(code, "invite")
            row = c.execute("SELECT role, created_by FROM invites WHERE code_hash = ? AND used_by IS NULL"
                            " AND expires_ts > ?", (h, ts)).fetchone()
            if not row:
                return None
            cur = c.execute("UPDATE invites SET used_by = ?, used_ts = ? WHERE code_hash = ? AND used_by IS NULL",
                            (tg_id, ts, h))
            if cur.rowcount == 0:
                return None
            self._put_member(c, tg_id, username, name, row["role"], row["created_by"])
            return str(row["role"])

        return await self._call(q)
