"""База бота: SQLite-файл на сервере (/var/lib/prostranstvo/bot.db).

Общая для обоих мессенджеров (Telegram и MAX — отдельные процессы, один файл).
Хранится: клиенты (у каждого — свой мессенджер), заявки и статусы, отгрузки,
переписка, команда магазина (человек может быть подключён в обоих мессенджерах),
одноразовые коды, очередь доставки сообщений между процессами (outbox) и связи
«сообщение в чате сотрудника → клиент» (чтобы ответ уходил нужному клиенту).
Данные клиентов никуда, кроме этого файла и чатов сотрудников, не уходят;
в журнал они не пишутся.

Версии схемы: 1 — только Telegram; 2 — каналы tg/max. Старая база переводится
на версию 2 автоматически при первом запуске, без потери данных.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
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

SCHEMA_VERSION = 2
ROLE_MANAGER = "manager"
ROLE_SHIPPING = "shipping"
ROLES = (ROLE_MANAGER, ROLE_SHIPPING)
ROLE_LINK = "link"        # код «подключить второй мессенджер» для того же человека
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

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,   -- «клиент К5»
    channel     TEXT    NOT NULL,                    -- 'tg' | 'max'
    user_id     INTEGER NOT NULL,                    -- id в мессенджере
    username    TEXT,
    name        TEXT,
    created_ts  INTEGER NOT NULL,
    last_ts     INTEGER NOT NULL,
    UNIQUE (channel, user_id)
);

CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts      INTEGER NOT NULL,
    created_at      TEXT    NOT NULL,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    name            TEXT    NOT NULL,
    contact         TEXT    NOT NULL,
    comment         TEXT,
    calc            TEXT,
    consent_at      TEXT    NOT NULL,
    consent_version TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'new',
    status_ts       INTEGER,
    channel         TEXT    NOT NULL DEFAULT 'tg',
    client_id       INTEGER
);
CREATE INDEX IF NOT EXISTS leads_ts ON leads(created_ts);
CREATE INDEX IF NOT EXISTS leads_client ON leads(client_id);

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
    user_id     INTEGER NOT NULL,          -- клиент (id в мессенджере)
    username    TEXT,
    name        TEXT,
    direction   TEXT    NOT NULL,          -- 'in' от клиента, 'out' ответ магазина
    kind        TEXT    NOT NULL DEFAULT 'text',
    text        TEXT,
    admin_id    INTEGER,                   -- кто из команды ответил (для 'out')
    admin_name  TEXT,
    channel     TEXT    NOT NULL DEFAULT 'tg',
    client_id   INTEGER
);
CREATE INDEX IF NOT EXISTS messages_ts ON messages(created_ts);
CREATE INDEX IF NOT EXISTS messages_client ON messages(client_id);

-- сообщение в чате сотрудника → клиент, которому уйдёт ответ на него
CREATE TABLE IF NOT EXISTS relay (
    channel     TEXT    NOT NULL,
    chat_id     INTEGER NOT NULL,          -- сотрудник (id в мессенджере)
    message_id  TEXT    NOT NULL,
    client_id   INTEGER NOT NULL,
    lead_id     INTEGER,
    created_ts  INTEGER NOT NULL,
    PRIMARY KEY (channel, chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS relay_client ON relay(client_id);

-- человек из команды магазина: роль и настройки общие для всех его мессенджеров
CREATE TABLE IF NOT EXISTS persons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role        TEXT NOT NULL,             -- 'manager' | 'shipping'
    notify      TEXT NOT NULL,             -- 'all' | 'orders'
    deliver     TEXT NOT NULL DEFAULT '',  -- '' (по умолчанию) | 'tg' | 'max'
    created_at  TEXT NOT NULL
);

-- его аккаунты в мессенджерах
CREATE TABLE IF NOT EXISTS team (
    channel    TEXT    NOT NULL,
    user_id    INTEGER NOT NULL,
    person_id  INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    username   TEXT,
    name       TEXT,
    added_at   TEXT    NOT NULL,
    added_by   INTEGER,
    PRIMARY KEY (channel, user_id)
);
CREATE INDEX IF NOT EXISTS team_person ON team(person_id);

CREATE TABLE IF NOT EXISTS invites (
    code_hash    TEXT PRIMARY KEY,
    role         TEXT    NOT NULL,         -- 'manager' | 'shipping' | 'link'
    created_ts   INTEGER NOT NULL,
    expires_ts   INTEGER NOT NULL,
    created_by   INTEGER,
    used_by      INTEGER,
    used_ts      INTEGER,
    person_id    INTEGER,                  -- для 'link': чей второй мессенджер
    used_channel TEXT
);

-- очередь доставки: что и кому отправить в каком мессенджере
CREATE TABLE IF NOT EXISTS outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts  INTEGER NOT NULL,
    channel     TEXT    NOT NULL,
    chat_id     INTEGER NOT NULL,
    item        TEXT    NOT NULL,          -- JSON
    client_id   INTEGER,
    attempts    INTEGER NOT NULL DEFAULT 0,
    next_ts     INTEGER NOT NULL,
    done_ts     INTEGER,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(channel, done_ts, next_ts);

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


class SchemaError(Exception):
    """База создана более новой версией программы."""


@dataclass(frozen=True)
class Client:
    id: int
    channel: str
    user_id: int
    username: str
    name: str
    created_ts: int
    last_ts: int


@dataclass(frozen=True)
class Lead:
    id: int
    created_ts: int
    created_at: str
    user_id: int
    username: str
    name: str
    contact: str
    comment: str
    calc: str
    consent_at: str
    consent_version: str
    status: str
    status_ts: int
    channel: str
    client_id: int

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
    client_id: int
    client_channel: str


@dataclass(frozen=True)
class Seat:
    """Аккаунт сотрудника в одном мессенджере."""

    channel: str
    user_id: int
    person_id: int
    username: str
    name: str
    added_at: str
    role: str
    notify: str
    deliver: str


@dataclass(frozen=True)
class HistoryItem:
    created_ts: int
    direction: str
    kind: str
    text: str
    admin_name: str


@dataclass(frozen=True)
class OutboxItem:
    id: int
    chat_id: int
    item: dict
    attempts: int


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


_INT_FIELDS = {"status_ts", "created_by", "accepted_by", "accepted_ts", "shipped_by", "shipped_ts",
               "cancelled_ts", "created_ts", "client_id", "last_ts", "user_id", "person_id"}


def _clean(row: sqlite3.Row) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in row.keys():  # noqa: SIM118 - у sqlite3.Row итерация идёт по значениям
        value = row[key]
        out[key] = value if value is not None else (0 if key in _INT_FIELDS else "")
    return out


def _table_exists(c: sqlite3.Connection, name: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _columns(c: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


def _migrate_1_to_2(c: sqlite3.Connection) -> None:
    """Версия 1 (только Telegram) → 2 (каналы tg/max). Всё в одной транзакции."""
    for table in ("leads", "messages"):
        cols = _columns(c, table)
        if "tg_id" in cols:
            c.execute(f"ALTER TABLE {table} RENAME COLUMN tg_id TO user_id")
        if "channel" not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN channel TEXT NOT NULL DEFAULT 'tg'")
        if "client_id" not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN client_id INTEGER")
    if "admin_name" not in _columns(c, "messages"):
        c.execute("ALTER TABLE messages ADD COLUMN admin_name TEXT")
    c.execute("DROP INDEX IF EXISTS leads_tg")
    c.execute("DROP INDEX IF EXISTS messages_tg")

    # таблицы, которых в версии 1 не было (executescript не годится: он делает COMMIT)
    for stmt in _split_sql(SCHEMA_V2):
        if stmt.upper().startswith("CREATE TABLE IF NOT EXISTS RELAY") or \
                stmt.upper().startswith("CREATE TABLE IF NOT EXISTS TEAM") or \
                stmt.upper().startswith("CREATE INDEX IF NOT EXISTS RELAY_") or \
                stmt.upper().startswith("CREATE INDEX IF NOT EXISTS TEAM_"):
            continue
        c.execute(stmt)

    # клиенты — из заявок и сообщений
    users: dict[int, dict[str, Any]] = {}
    for table in ("leads", "messages"):
        extra = "AND direction = 'in'" if table == "messages" else ""
        for r in c.execute(f"SELECT user_id, username, name, created_ts FROM {table} WHERE 1 {extra} ORDER BY id"):
            u = users.setdefault(r[0], {"first": r[3], "last": r[3], "username": "", "name": ""})
            u["first"], u["last"] = min(u["first"], r[3]), max(u["last"], r[3])
            if r[1]:
                u["username"] = r[1]
            if r[2] and (table == "messages" or not u["name"]):
                u["name"] = r[2]
    for r in c.execute("SELECT DISTINCT user_id, created_ts FROM messages WHERE direction = 'out'"):
        users.setdefault(r[0], {"first": r[1], "last": r[1], "username": "", "name": ""})
    for uid, u in users.items():
        c.execute("INSERT OR IGNORE INTO clients(channel, user_id, username, name, created_ts, last_ts)"
                  " VALUES ('tg', ?, ?, ?, ?, ?)", (uid, u["username"], u["name"], u["first"], u["last"]))
    for table in ("leads", "messages"):
        c.execute(f"UPDATE {table} SET client_id = (SELECT id FROM clients c WHERE c.channel = {table}.channel"
                  f" AND c.user_id = {table}.user_id) WHERE client_id IS NULL")

    # связи ответов: теперь с каналом и номером клиента
    if _table_exists(c, "relay") and "admin_chat_id" in _columns(c, "relay"):
        c.execute("ALTER TABLE relay RENAME TO relay_v1")
        c.execute(_create_stmt("relay"))
        c.execute(
            "INSERT OR IGNORE INTO relay(channel, chat_id, message_id, client_id, lead_id, created_ts)"
            " SELECT 'tg', r.admin_chat_id, CAST(r.admin_message_id AS TEXT), c.id, r.lead_id, r.created_ts"
            " FROM relay_v1 r JOIN clients c ON c.channel = 'tg' AND c.user_id = r.tg_id")
        c.execute("DROP TABLE relay_v1")
    else:
        c.execute(_create_stmt("relay"))
    c.execute("CREATE INDEX IF NOT EXISTS relay_client ON relay(client_id)")

    # команда: человек (роль, настройки) + его аккаунты
    if _table_exists(c, "team") and "tg_id" in _columns(c, "team"):
        c.execute("ALTER TABLE team RENAME TO team_v1")
        c.execute(_create_stmt("team"))
        for r in c.execute("SELECT tg_id, username, name, role, notify, added_at, added_by FROM team_v1"
                           " ORDER BY added_at").fetchall():
            cur = c.execute("INSERT INTO persons(role, notify, deliver, created_at) VALUES (?, ?, '', ?)",
                            (r[3], r[4], r[5]))
            c.execute("INSERT INTO team(channel, user_id, person_id, username, name, added_at, added_by)"
                      " VALUES ('tg', ?, ?, ?, ?, ?, ?)", (r[0], cur.lastrowid, r[1], r[2], r[5], r[6]))
        c.execute("DROP TABLE team_v1")
    else:
        c.execute(_create_stmt("team"))
    c.execute("CREATE INDEX IF NOT EXISTS team_person ON team(person_id)")

    cols = _columns(c, "invites")
    if "person_id" not in cols:
        c.execute("ALTER TABLE invites ADD COLUMN person_id INTEGER")
    if "used_channel" not in cols:
        c.execute("ALTER TABLE invites ADD COLUMN used_channel TEXT")


def _split_sql(script: str) -> list[str]:
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def _create_stmt(table: str) -> str:
    for stmt in _split_sql(SCHEMA_V2):
        if stmt.upper().startswith(f"CREATE TABLE IF NOT EXISTS {table.upper()} "):
            return stmt
    raise KeyError(table)  # pragma: no cover


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
            conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30, isolation_level=None)
        finally:
            os.umask(old_umask)
        for suffix in ("", "-wal", "-shm"):  # заявки — только для пользователя бота
            with contextlib.suppress(OSError):
                if os.stat(self.path + suffix).st_uid == os.getuid():
                    os.chmod(self.path + suffix, 0o600)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("BEGIN IMMEDIATE")  # два процесса (Telegram и MAX) могут стартовать одновременно
        try:
            version = None
            if _table_exists(conn, "settings"):
                row = conn.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()
                version = int(row[0]) if row else None
            if not _table_exists(conn, "leads"):
                for stmt in _split_sql(SCHEMA_V2):
                    conn.execute(stmt)
            elif version is None or version < 2:
                _migrate_1_to_2(conn)
            elif version > SCHEMA_VERSION:
                raise SchemaError(f"база версии {version}, а программа знает только {SCHEMA_VERSION}")
            else:
                for stmt in _split_sql(SCHEMA_V2):
                    conn.execute(stmt)
            conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('schema_version', ?)",
                         (str(SCHEMA_VERSION),))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            conn.close()
            raise
        return conn

    def _run(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            c = self._conn
            c.execute("BEGIN IMMEDIATE")
            try:
                result = fn(c)
                c.execute("COMMIT")
                return result
            except BaseException:
                c.execute("ROLLBACK")
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

    # ------------------------------------------------------------------ настройки
    async def get_setting(self, key: str) -> str:
        def q(c: sqlite3.Connection) -> str:
            row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return str(row[0]) if row else ""

        return await self._call(q)

    async def set_setting(self, key: str, value: str) -> None:
        await self._call(lambda c: c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                                             (key, value)))

    # ------------------------------------------------------------------ клиенты
    async def upsert_client(self, channel: str, user_id: int, username: str | None, name: str | None) -> Client:
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> Client:
            c.execute(
                "INSERT INTO clients(channel, user_id, username, name, created_ts, last_ts) VALUES (?,?,?,?,?,?)"
                " ON CONFLICT(channel, user_id) DO UPDATE SET username = excluded.username,"
                " name = excluded.name, last_ts = excluded.last_ts",
                (channel, user_id, username or "", name or "", ts, ts))
            row = c.execute("SELECT * FROM clients WHERE channel = ? AND user_id = ?", (channel, user_id)).fetchone()
            return Client(**_clean(row))

        return await self._call(q)

    async def get_client(self, client_id: int) -> Client | None:
        def q(c: sqlite3.Connection) -> Client | None:
            row = c.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
            return Client(**_clean(row)) if row else None

        return await self._call(q)

    async def find_client(self, channel: str, user_id: int) -> Client | None:
        def q(c: sqlite3.Connection) -> Client | None:
            row = c.execute("SELECT * FROM clients WHERE channel = ? AND user_id = ?", (channel, user_id)).fetchone()
            return Client(**_clean(row)) if row else None

        return await self._call(q)

    # ------------------------------------------------------------------ заявки
    async def add_lead(
        self, *, client: Client, name: str, contact: str, comment: str | None, calc: str | None,
        consent_at: str, consent_version: str,
    ) -> int:
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> int:
            cur = c.execute(
                "INSERT INTO leads(created_ts, created_at, user_id, username, name, contact, comment, calc,"
                " consent_at, consent_version, status, status_ts, channel, client_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts, iso_now(), client.user_id, client.username, name, contact, comment or "", calc or "",
                 consent_at, consent_version, ST_NEW, ts, client.channel, client.id),
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

    async def client_leads(self, client_id: int) -> list[Lead]:
        def q(c: sqlite3.Connection) -> list[Lead]:
            rows = c.execute("SELECT * FROM leads WHERE client_id = ? ORDER BY id", (client_id,)).fetchall()
            return [Lead(**_clean(r)) for r in rows]

        return await self._call(q)

    # ------------------------------------------------------------------ отгрузки
    _SHIP_SQL = (
        "SELECT s.*, l.status AS status, l.name AS client_name, l.username AS client_username,"
        " l.client_id AS client_id, l.channel AS client_channel"
        " FROM shipments s JOIN leads l ON l.id = s.lead_id"
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
        self, *, client: Client, direction: str, kind: str, text: str | None,
        admin_id: int | None = None, admin_name: str | None = None,
    ) -> int:
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> int:
            cur = c.execute(
                "INSERT INTO messages(created_ts, created_at, user_id, username, name, direction, kind, text,"
                " admin_id, admin_name, channel, client_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts, iso_now(), client.user_id, client.username, client.name, direction, kind, text or "",
                 admin_id, admin_name or "", client.channel, client.id),
            )
            return int(cur.lastrowid or 0)

        return await self._call(q)

    async def get_message(self, message_id: int) -> dict[str, Any] | None:
        def q(c: sqlite3.Connection) -> dict[str, Any] | None:
            row = c.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
            return _clean(row) if row else None

        return await self._call(q)

    async def history(self, client_id: int, limit: int = 30) -> list[HistoryItem]:
        def q(c: sqlite3.Connection) -> list[HistoryItem]:
            rows = c.execute(
                "SELECT created_ts, direction, kind, text, admin_name FROM messages WHERE client_id = ?"
                " ORDER BY id DESC LIMIT ?", (client_id, limit),
            ).fetchall()
            return [HistoryItem(**_clean(r)) for r in reversed(rows)]

        return await self._call(q)

    async def add_relay(self, channel: str, chat_id: int, message_id: str, client_id: int,
                        lead_id: int | None = None) -> None:
        ts = int(time.time())
        await self._call(lambda c: c.execute(
            "INSERT OR REPLACE INTO relay(channel, chat_id, message_id, client_id, lead_id, created_ts)"
            " VALUES (?,?,?,?,?,?)", (channel, chat_id, str(message_id), client_id, lead_id, ts),
        ))

    async def relay_target(self, channel: str, chat_id: int, message_id: str) -> int | None:
        def q(c: sqlite3.Connection) -> int | None:
            row = c.execute("SELECT client_id FROM relay WHERE channel = ? AND chat_id = ? AND message_id = ?",
                            (channel, chat_id, str(message_id))).fetchone()
            return int(row[0]) if row else None

        return await self._call(q)

    async def delete_client(self, client_id: int) -> tuple[int, int, int]:
        """Отзыв согласия: удалить заявки и переписку клиента.

        Заявки, переданные на отгрузку или отгруженные, — это уже заказ (договор),
        их храним по закону. → (удалено заявок, оставлено заказов, удалено сообщений).
        """
        placeholders = ",".join("?" * len(KEEP_ON_DELETE))

        def q(c: sqlite3.Connection) -> tuple[int, int, int]:
            leads = c.execute(f"DELETE FROM leads WHERE client_id = ? AND status NOT IN ({placeholders})",
                              (client_id, *KEEP_ON_DELETE)).rowcount
            kept = int(c.execute("SELECT COUNT(*) FROM leads WHERE client_id = ?", (client_id,)).fetchone()[0])
            messages = c.execute("DELETE FROM messages WHERE client_id = ?", (client_id,)).rowcount
            c.execute("DELETE FROM outbox WHERE client_id = ?", (client_id,))
            if kept:
                c.execute("DELETE FROM relay WHERE client_id = ? AND (lead_id IS NULL OR lead_id NOT IN"
                          " (SELECT id FROM leads WHERE client_id = ?))", (client_id, client_id))
            else:
                c.execute("DELETE FROM relay WHERE client_id = ?", (client_id,))
                c.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            return leads, kept, messages

        result = await self._call(q)
        await asyncio.to_thread(self._checkpoint)
        return result

    def _checkpoint(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

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
                    "SELECT COUNT(DISTINCT client_id) FROM (SELECT client_id FROM messages WHERE direction = 'in'"
                    " AND created_ts >= ? UNION SELECT client_id FROM leads WHERE created_ts >= ?)",
                    start_week, start_week),
                shipments_open=one("SELECT COUNT(*) FROM leads WHERE status IN (?, ?)", *OPEN_SHIPMENT),
                shipped_week=one("SELECT COUNT(*) FROM shipments WHERE shipped_ts >= ?", start_week),
            )

        return await self._call(q)

    # ------------------------------------------------------------------ команда
    _TEAM_SQL = ("SELECT t.channel, t.user_id, t.person_id, t.username, t.name, t.added_at,"
                 " p.role, p.notify, p.deliver FROM team t JOIN persons p ON p.id = t.person_id")

    async def team(self) -> list[Seat]:
        def q(c: sqlite3.Connection) -> list[Seat]:
            rows = c.execute(self._TEAM_SQL + " ORDER BY p.id, t.channel").fetchall()
            return [Seat(**_clean(r)) for r in rows]

        return await self._call(q)

    @staticmethod
    def _seat_person(c: sqlite3.Connection, channel: str, user_id: int) -> int | None:
        row = c.execute("SELECT person_id FROM team WHERE channel = ? AND user_id = ?", (channel, user_id)).fetchone()
        return int(row[0]) if row else None

    @classmethod
    def _join(cls, c: sqlite3.Connection, channel: str, user_id: int, username: str | None, name: str | None,
              role: str, added_by: int | None, person_id: int | None = None) -> int:
        """Посадить аккаунт в команду. person_id — привязать к существующему человеку."""
        current = cls._seat_person(c, channel, user_id)
        if person_id is None:
            if current is not None:  # уже в команде — меняем роль
                old = c.execute("SELECT role FROM persons WHERE id = ?", (current,)).fetchone()
                if old and old[0] != role:
                    c.execute("UPDATE persons SET role = ?, notify = ? WHERE id = ?",
                              (role, default_notify(role), current))
                c.execute("UPDATE team SET username = ?, name = ? WHERE channel = ? AND user_id = ?",
                          (username or "", name or "", channel, user_id))
                return current
            cur = c.execute("INSERT INTO persons(role, notify, deliver, created_at) VALUES (?, ?, '', ?)",
                            (role, default_notify(role), iso_now()))
            person_id = int(cur.lastrowid or 0)
        elif current is not None and current != person_id:
            c.execute("DELETE FROM team WHERE channel = ? AND user_id = ?", (channel, user_id))
            c.execute("DELETE FROM persons WHERE id = ? AND NOT EXISTS (SELECT 1 FROM team WHERE person_id = ?)",
                      (current, current))
        c.execute("INSERT OR REPLACE INTO team(channel, user_id, person_id, username, name, added_at, added_by)"
                  " VALUES (?,?,?,?,?,?,?)", (channel, user_id, person_id, username or "", name or "",
                                              iso_now(), added_by))
        return person_id

    async def ensure_member(self, channel: str, user_id: int, role: str = ROLE_MANAGER) -> None:
        """Сотрудник из ADMIN_IDS (bot.env): добавить, если его ещё нет в базе."""
        def q(c: sqlite3.Connection) -> None:
            if self._seat_person(c, channel, user_id) is None:
                self._join(c, channel, user_id, "", "", role, None)

        await self._call(q)

    async def add_member(self, channel: str, user_id: int, username: str | None, name: str | None, role: str,
                         added_by: int | None = None) -> int:
        if role not in ROLES:
            raise ValueError(role)
        return await self._call(lambda c: self._join(c, channel, user_id, username, name, role, added_by))

    async def remove_person(self, person_id: int) -> bool:
        def q(c: sqlite3.Connection) -> bool:
            c.execute("DELETE FROM team WHERE person_id = ?", (person_id,))
            return c.execute("DELETE FROM persons WHERE id = ?", (person_id,)).rowcount > 0

        return await self._call(q)

    async def set_notify(self, person_id: int, mode: str) -> bool:
        if mode not in (NOTIFY_ALL, NOTIFY_ORDERS):
            raise ValueError(mode)
        return await self._call(
            lambda c: c.execute("UPDATE persons SET notify = ? WHERE id = ?", (mode, person_id)).rowcount > 0)

    async def set_deliver(self, person_id: int, channel: str) -> bool:
        return await self._call(
            lambda c: c.execute("UPDATE persons SET deliver = ? WHERE id = ?", (channel, person_id)).rowcount > 0)

    async def owner_code_used(self, code: str) -> bool:
        key = "owner_code_used:" + code_hash(code)
        return await self._call(
            lambda c: c.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone() is not None)

    async def claim_owner_code(self, code: str, channel: str, user_id: int, username: str | None,
                               name: str | None) -> bool:
        """Код из установщика: первый, кто его отправит (в любом мессенджере), — менеджер. Код одноразовый."""
        key = "owner_code_used:" + code_hash(code)

        def q(c: sqlite3.Connection) -> bool:
            cur = c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, iso_now()))
            if cur.rowcount == 0:
                return False
            self._join(c, channel, user_id, username, name, ROLE_MANAGER, None)
            return True

        return await self._call(q)

    async def create_invite(self, role: str, created_by: int, ttl_sec: int = INVITE_TTL_SEC,
                            person_id: int | None = None) -> str:
        """Одноразовый код (6 цифр, 24 часа): пригласить человека или подключить свой второй мессенджер."""
        if role not in (*ROLES, ROLE_LINK) or (role == ROLE_LINK and not person_id):
            raise ValueError(role)
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> str:
            c.execute("DELETE FROM invites WHERE expires_ts < ?", (ts - 30 * 24 * 3600,))
            for _ in range(20):
                code = f"{secrets.randbelow(900000) + 100000}"
                cur = c.execute(
                    "INSERT OR IGNORE INTO invites(code_hash, role, created_ts, expires_ts, created_by, person_id)"
                    " VALUES (?,?,?,?,?,?)", (code_hash(code, "invite"), role, ts, ts + ttl_sec, created_by,
                                             person_id))
                if cur.rowcount:
                    return code
            raise RuntimeError("не удалось создать код приглашения")  # pragma: no cover

        return await self._call(q)

    async def use_invite(self, code: str, channel: str, user_id: int, username: str | None,
                         name: str | None) -> tuple[str, bool] | None:
        """Принять код. → (роль, это_второй_мессенджер) или None (код неверный, использован или истёк)."""
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> tuple[str, bool] | None:
            h = code_hash(code, "invite")
            row = c.execute("SELECT role, created_by, person_id FROM invites WHERE code_hash = ?"
                            " AND used_by IS NULL AND expires_ts > ?", (h, ts)).fetchone()
            if not row:
                return None
            role, created_by, person_id = row[0], row[1], row[2]
            if role == ROLE_LINK:
                person = c.execute("SELECT role FROM persons WHERE id = ?", (person_id,)).fetchone()
                if not person:
                    return None
                role = person[0]
            c.execute("UPDATE invites SET used_by = ?, used_ts = ?, used_channel = ? WHERE code_hash = ?",
                      (user_id, ts, channel, h))
            self._join(c, channel, user_id, username, name, role, created_by,
                       person_id if row[0] == ROLE_LINK else None)
            return role, row[0] == ROLE_LINK

        return await self._call(q)

    # ------------------------------------------------------------------ очередь доставки
    async def enqueue(self, channel: str, chat_id: int, item: dict, client_id: int | None = None) -> int:
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> int:
            cur = c.execute("INSERT INTO outbox(created_ts, channel, chat_id, item, client_id, next_ts)"
                            " VALUES (?,?,?,?,?,?)",
                            (ts, channel, chat_id, json.dumps(item, ensure_ascii=False), client_id, ts))
            return int(cur.lastrowid or 0)

        return await self._call(q)

    async def outbox_pending(self, channel: str, limit: int = 20) -> list[OutboxItem]:
        ts = int(time.time())

        def q(c: sqlite3.Connection) -> list[OutboxItem]:
            rows = c.execute("SELECT id, chat_id, item, attempts FROM outbox WHERE channel = ? AND done_ts IS NULL"
                             " AND next_ts <= ? ORDER BY id LIMIT ?", (channel, ts, limit)).fetchall()
            return [OutboxItem(r[0], r[1], json.loads(r[2]), r[3]) for r in rows]

        return await self._call(q)

    async def outbox_done(self, item_id: int, error: str = "") -> None:
        ts = int(time.time())
        await self._call(lambda c: c.execute("UPDATE outbox SET done_ts = ?, error = ? WHERE id = ?",
                                             (ts, error[:300], item_id)))

    async def outbox_retry(self, item_id: int, delay_sec: int, error: str) -> None:
        ts = int(time.time())
        await self._call(lambda c: c.execute(
            "UPDATE outbox SET attempts = attempts + 1, next_ts = ?, error = ? WHERE id = ?",
            (ts + delay_sec, error[:300], item_id)))

    async def outbox_cleanup(self, keep_sec: int = 2 * 24 * 3600) -> int:
        border = int(time.time()) - keep_sec
        return await self._call(lambda c: c.execute(
            "DELETE FROM outbox WHERE (done_ts IS NOT NULL AND done_ts < ?) OR created_ts < ?",
            (border, border - 5 * 24 * 3600)).rowcount)

    async def outbox_count(self, channel: str) -> int:
        return await self._call(lambda c: int(c.execute(
            "SELECT COUNT(*) FROM outbox WHERE channel = ? AND done_ts IS NULL", (channel,)).fetchone()[0]))
