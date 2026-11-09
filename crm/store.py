"""База CRM «Наш декор»: SQLite-файл /var/lib/prostranstvo/crm.db.

Свои таблицы: пользователи CRM, клиенты, сделки и их позиции, задачи, история, склад.
Заявки из бота (Telegram/MAX) не копируются руками — они подтягиваются из базы бота
(/var/lib/prostranstvo/bot.db) по номеру заявки, сама база бота только читается.
Единственная запись в базу бота — уведомление сотрудникам в очередь outbox
(бот доставляет его в MAX или Telegram, как настроил сотрудник).

Цены и список товаров — из каталога сайта (массив CAT в index.html), остатки и
свои цены — в таблице stock этой базы.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable

try:
    from zoneinfo import ZoneInfo

    TZ: Any = ZoneInfo("Europe/Moscow")
except Exception:  # pragma: no cover
    TZ = timezone(timedelta(hours=3), "MSK")

SCHEMA_VERSION = 1

# Этапы воронки (порядок важен: «→» двигает на следующий)
STAGES: list[tuple[str, str]] = [
    ("new", "Новая"),
    ("work", "В работе"),
    ("quote", "Расчёт отправлен"),
    ("paid", "Оплачено"),
    ("shipped", "Отгружено"),
    ("lost", "Отказ"),
]
STAGE_NAMES = dict(STAGES)
OPEN_STAGES = ("new", "work", "quote", "paid")
RESERVE_STAGES = ("work", "quote", "paid")      # товар отложен под клиента
SOURCES: list[tuple[str, str]] = [
    ("site", "Сайт"), ("max", "MAX"), ("tg", "Telegram"), ("avito", "Авито"),
    ("phone", "Звонок"), ("mail", "Почта"), ("other", "Другое"),
]
SOURCE_NAMES = dict(SOURCES)
KINDS: list[tuple[str, str]] = [("p", "Частный"), ("d", "Дизайнер"), ("c", "Компания")]
KIND_NAMES = dict(KINDS)
ROLES: list[tuple[str, str]] = [("admin", "Владелец"), ("staff", "Сотрудник")]
ROLE_NAMES = dict(ROLES)
DESIGNER_DISCOUNT = 10  # % для дизайнеров по умолчанию

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sid        TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL DEFAULT '',
    contact    TEXT NOT NULL DEFAULT '',
    page       TEXT NOT NULL DEFAULT '',
    deal_id    INTEGER,
    unread     INTEGER NOT NULL DEFAULT 0,
    consent_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    seen_at    TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chat_msgs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    who        TEXT NOT NULL,
    author     TEXT NOT NULL DEFAULT '',
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chat_msgs_chat ON chat_msgs(chat_id, id);
CREATE TABLE IF NOT EXISTS push_subs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    endpoint   TEXT NOT NULL UNIQUE,
    p256dh     TEXT NOT NULL,
    auth       TEXT NOT NULL,
    ua         TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_ok    TEXT NOT NULL DEFAULT '',
    fails      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    login      TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'staff',
    pw_hash    TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login TEXT
);
CREATE TABLE IF NOT EXISTS clients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    phone         TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    messenger     TEXT NOT NULL DEFAULT '',      -- @ник или «MAX: имя»
    kind          TEXT NOT NULL DEFAULT 'p',     -- p частный, d дизайнер, c компания
    company       TEXT NOT NULL DEFAULT '',
    inn           TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT '',
    bot_client_id INTEGER UNIQUE,                -- «клиент К5» в боте
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS clients_phone ON clients(phone);
CREATE TABLE IF NOT EXISTS deals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id     INTEGER NOT NULL REFERENCES clients(id),
    want          TEXT NOT NULL DEFAULT '',      -- что хочет клиент
    source        TEXT NOT NULL DEFAULT 'other',
    stage         TEXT NOT NULL DEFAULT 'new',
    discount      INTEGER NOT NULL DEFAULT 0,    -- %
    address       TEXT NOT NULL DEFAULT '',
    ship_date     TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT '',
    lost_reason   TEXT NOT NULL DEFAULT '',
    calc          TEXT NOT NULL DEFAULT '',      -- расчёт из калькулятора сайта/бота
    bot_lead_id   INTEGER UNIQUE,                -- заявка №… в боте
    consent_at    TEXT NOT NULL DEFAULT '',
    consent_version TEXT NOT NULL DEFAULT '',
    stock_written INTEGER NOT NULL DEFAULT 0,    -- остатки уже списаны (отгружено)
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    stage_at      TEXT NOT NULL,
    created_by    INTEGER
);
CREATE INDEX IF NOT EXISTS deals_stage ON deals(stage);
CREATE INDEX IF NOT EXISTS deals_client ON deals(client_id);
CREATE TABLE IF NOT EXISTS lines (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id  INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    article  TEXT NOT NULL,
    qty      INTEGER NOT NULL DEFAULT 0,
    price    INTEGER NOT NULL DEFAULT 0          -- ₽ за штуку до скидки
);
CREATE INDEX IF NOT EXISTS lines_deal ON lines(deal_id);
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id    INTEGER REFERENCES deals(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    due        TEXT NOT NULL,                    -- YYYY-MM-DD
    done_at    TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tasks_open ON tasks(done_at, due);
CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id   INTEGER,
    client_id INTEGER,
    at        TEXT NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    text      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_deal ON events(deal_id);
CREATE TABLE IF NOT EXISTS stock (
    article    TEXT PRIMARY KEY,
    qty        INTEGER NOT NULL DEFAULT 0,
    price      INTEGER,                          -- своя цена (если пусто — цена сайта)
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''
);
"""


def now() -> datetime:
    return datetime.now(TZ)


def iso_now() -> str:
    return now().isoformat(timespec="seconds")


def today() -> str:
    return now().date().isoformat()


def fmt_dt(s: str | None) -> str:
    if not s:
        return ""
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return s
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    d = d.astimezone(TZ)
    return d.strftime("%d.%m.%Y %H:%M")


MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def fmt_day(s: str | None) -> str:
    if not s:
        return ""
    try:
        d = date.fromisoformat(s[:10])
    except ValueError:
        return s
    return f"{d.day} {MONTHS[d.month - 1]}"


def rub(n: float | int | None) -> str:
    n = int(round(n or 0))
    return f"{n:,}".replace(",", " ") + " ₽"


PHONE_RE = re.compile(r"\+?\d[\d\s()\-]{8,}\d")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def split_contact(contact: str) -> tuple[str, str, str]:
    """«+7 911 …» / «a@b.ru» / «@nick» → (телефон, почта, мессенджер)."""
    contact = (contact or "").strip()
    phone = email = messenger = ""
    m = EMAIL_RE.search(contact)
    if m:
        email = m.group(0)
    m = PHONE_RE.search(contact)
    if m:
        phone = norm_phone(m.group(0))
    if not phone and not email and contact:
        messenger = contact[:100]
    return phone, email, messenger


def norm_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    return ("+" + digits) if digits else ""


# ------------------------------------------------------------------ каталог сайта
@dataclass(frozen=True)
class Product:
    article: str
    kind: str
    name: str
    size: str
    per_box: int
    price: int          # цена сайта, ₽/шт


KIND_TITLES = {"panel": "Рейки под покраску", "color": "Под дерево и бетон", "mold": "Молдинги",
               "plinth": "Плинтусы", "cornice": "Карнизы", "corner": "Уголки"}
_CAT_RE = re.compile(r"\bCAT\s*=\s*\[")


def _to_int(v: Any) -> int:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return 0


def parse_catalog(html: str) -> list[Product]:
    m = _CAT_RE.search(html)
    if not m:
        return []
    start = m.end() - 1
    depth, i, in_str, esc = 0, start, False, False
    while i < len(html):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
        i += 1
    try:
        raw = json.loads(html[start:i + 1])
    except ValueError:
        return []
    out: list[Product] = []
    seen: set[str] = set()
    for x in raw:
        if not isinstance(x, dict):
            continue
        a = str(x.get("a", "")).strip()
        if not a or a in seen:
            continue
        seen.add(a)
        w, t, ln = _to_int(x.get("w")), _to_int(x.get("t")), _to_int(x.get("l"))
        size = "×".join(str(v) for v in (w, t, ln) if v)
        out.append(Product(a, str(x.get("c", "")), str(x.get("n", "")).strip(), size,
                           _to_int(x.get("b")), max(_to_int(x.get("r")), 0)))
    return out


class Catalog:
    """Каталог сайта; перечитывается, если файл сайта изменился."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._mtime = -1.0
        self._items: list[Product] = []
        self._by: dict[str, Product] = {}
        self._lock = threading.Lock()

    def _load(self) -> None:
        try:
            mt = os.path.getmtime(self.path)
        except OSError:
            return
        if mt == self._mtime:
            return
        with self._lock:
            try:
                with open(self.path, encoding="utf-8", errors="replace") as f:
                    items = parse_catalog(f.read())
            except OSError:
                return
            if items:
                self._items = items
                self._by = {p.article.upper().replace(" ", ""): p for p in items}
            self._mtime = mt

    def all(self) -> list[Product]:
        self._load()
        return list(self._items)

    def get(self, article: str) -> Product | None:
        self._load()
        return self._by.get((article or "").upper().replace(" ", "").translate(_LOOKALIKE))

    def find(self, text: str) -> Product | None:
        """Нестрогий поиск: точный артикул; без буквы («902» → A902); единственное совпадение по цифрам."""
        p = self.get(text)
        if p:
            return p
        key = (text or "").upper().replace(" ", "").translate(_LOOKALIKE)
        if not key:
            return None
        for pref in ("A", "GS", "AP"):
            p = self._by.get(pref + key)
            if p:
                return p
        hits = [v for k, v in self._by.items() if k.endswith(key) or k.replace("-", "").replace("/", "") == key.replace("-", "").replace("/", "")]
        return hits[0] if len(hits) == 1 else None


_LOOKALIKE = str.maketrans("АВЕКМНОРСТХУЛ", "ABEKMHOPCTXYL")


# ------------------------------------------------------------------ база
class Store:
    def __init__(self, path: str, bot_db: str = "", catalog: Catalog | None = None) -> None:
        self.path = path
        self.bot_db = bot_db
        self.catalog = catalog or Catalog("")
        self._local = threading.local()
        self._import_lock = threading.Lock()
        self._last_import = 0.0
        self.on_notify: Callable[[str, str, str], Any] | None = None   # пуш на телефоны команды (title, text, url) — ставит app.py
        self._init()

    # соединение на поток (gunicorn с потоками)
    def c(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._open()
            self._local.conn = conn
        return conn

    def _open(self) -> sqlite3.Connection:
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        old = os.umask(0o077)
        try:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        finally:
            os.umask(old)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init(self) -> None:
        c = self.c()
        c.execute("BEGIN IMMEDIATE")
        try:
            for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
                c.execute(stmt)
            cols = {r[1] for r in c.execute("PRAGMA table_info(deals)").fetchall()}
            for col in ("client_note", "pay_link"):          # 09.11.2026: текст клиенту и ссылка на оплату в письме-расчёте
                if col not in cols:
                    c.execute(f"ALTER TABLE deals ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            for col, typ in (("followups", "INTEGER NOT NULL DEFAULT 0"), ("followup_at", "TEXT NOT NULL DEFAULT ''"),
                             ("no_followup", "INTEGER NOT NULL DEFAULT 0")):   # 09.11.2026: автонапоминания клиенту о расчёте
                if col not in cols:
                    c.execute(f"ALTER TABLE deals ADD COLUMN {col} {typ}")
            row = c.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
            if row and int(row[0]) > SCHEMA_VERSION:
                raise RuntimeError(f"база CRM версии {row[0]}, программа знает только {SCHEMA_VERSION}")
            c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    @contextlib.contextmanager
    def tx(self) -> Iterable[sqlite3.Connection]:
        c = self.c()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def setting(self, key: str, default: str = "") -> str:
        row = self.c().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.c().execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (key, value))

    # ---------------------------------------------------------------- пользователи
    def users(self) -> list[sqlite3.Row]:
        return self.c().execute("SELECT * FROM users ORDER BY active DESC, id").fetchall()

    def user(self, uid: int) -> sqlite3.Row | None:
        return self.c().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    def user_by_login(self, login: str) -> sqlite3.Row | None:
        return self.c().execute("SELECT * FROM users WHERE login=?", ((login or "").strip().lower(),)).fetchone()

    def add_user(self, login: str, name: str, role: str, pw_hash: str) -> int:
        login = (login or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,30}", login):
            raise ValueError("логин: латиница, цифры, точка, дефис (2–31 символ)")
        if role not in ROLE_NAMES:
            raise ValueError("роль: admin или staff")
        cur = self.c().execute("INSERT INTO users(login, name, role, pw_hash, created_at) VALUES (?,?,?,?,?)",
                               (login, name.strip() or login, role, pw_hash, iso_now()))
        return int(cur.lastrowid)

    def set_password(self, uid: int, pw_hash: str) -> None:
        self.c().execute("UPDATE users SET pw_hash=? WHERE id=?", (pw_hash, uid))

    def set_user(self, uid: int, *, name: str | None = None, role: str | None = None, active: bool | None = None) -> None:
        if name is not None:
            self.c().execute("UPDATE users SET name=? WHERE id=?", (name.strip()[:60] or "?", uid))
        if role is not None and role in ROLE_NAMES:
            self.c().execute("UPDATE users SET role=? WHERE id=?", (role, uid))
        if active is not None:
            self.c().execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, uid))

    def touch_login(self, uid: int) -> None:
        self.c().execute("UPDATE users SET last_login=? WHERE id=?", (iso_now(), uid))

    # ---------------------------------------------------------------- история
    def log(self, c: sqlite3.Connection, text: str, user: str = "", deal_id: int | None = None,
            client_id: int | None = None) -> None:
        c.execute("INSERT INTO events(deal_id, client_id, at, user_name, text) VALUES (?,?,?,?,?)",
                  (deal_id, client_id, iso_now(), user, text[:500]))

    def events(self, deal_id: int | None = None, client_id: int | None = None, limit: int = 100) -> list[sqlite3.Row]:
        if deal_id:
            return self.c().execute("SELECT * FROM events WHERE deal_id=? ORDER BY id DESC LIMIT ?", (deal_id, limit)).fetchall()
        return self.c().execute("SELECT * FROM events WHERE client_id=? ORDER BY id DESC LIMIT ?", (client_id, limit)).fetchall()

    # ---------------------------------------------------------------- клиенты
    def find_client(self, c: sqlite3.Connection, phone: str = "", email: str = "", bot_client_id: int | None = None) -> int | None:
        if bot_client_id:
            row = c.execute("SELECT id FROM clients WHERE bot_client_id=?", (bot_client_id,)).fetchone()
            if row:
                return int(row[0])
        if phone:
            row = c.execute("SELECT id FROM clients WHERE phone=? ORDER BY id LIMIT 1", (phone,)).fetchone()
            if row:
                return int(row[0])
        if email:
            row = c.execute("SELECT id FROM clients WHERE lower(email)=lower(?) ORDER BY id LIMIT 1", (email,)).fetchone()
            if row:
                return int(row[0])
        return None

    def add_client(self, c: sqlite3.Connection, name: str, phone: str = "", email: str = "", messenger: str = "",
                   kind: str = "p", company: str = "", bot_client_id: int | None = None) -> int:
        ts = iso_now()
        cur = c.execute("INSERT INTO clients(name, phone, email, messenger, kind, company, bot_client_id, created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        ((name or "Без имени").strip()[:120], phone[:30], email[:120], messenger[:120],
                         kind if kind in KIND_NAMES else "p", company[:120], bot_client_id, ts, ts))
        return int(cur.lastrowid)

    def client(self, cid: int) -> sqlite3.Row | None:
        return self.c().execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()

    def update_client(self, cid: int, user: str, **f: str) -> None:
        allowed = ("name", "phone", "email", "messenger", "kind", "company", "inn", "note")
        sets = {k: (v or "").strip() for k, v in f.items() if k in allowed}
        if "phone" in sets and sets["phone"]:
            sets["phone"] = norm_phone(sets["phone"]) or sets["phone"]
        if "kind" in sets and sets["kind"] not in KIND_NAMES:
            sets.pop("kind")
        if "name" in sets and not sets["name"]:
            sets.pop("name")
        if not sets:
            return
        with self.tx() as c:
            old = c.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
            if not old:
                return
            c.execute(f"UPDATE clients SET {', '.join(k + '=?' for k in sets)}, updated_at=? WHERE id=?",
                      (*sets.values(), iso_now(), cid))
            changed = [k for k, v in sets.items() if str(old[k]) != v]
            if "kind" in changed and sets["kind"] == "d":
                # дизайнеру — скидка по умолчанию в открытых сделках без своей скидки
                c.execute("UPDATE deals SET discount=? WHERE client_id=? AND discount=0 AND stage IN ('new','work','quote')",
                          (DESIGNER_DISCOUNT, cid))
            if changed:
                names = {"name": "имя", "phone": "телефон", "email": "почта", "messenger": "мессенджер", "kind": "тип",
                         "company": "компания", "inn": "ИНН", "note": "заметка"}
                self.log(c, "Клиент: изменено " + ", ".join(names[k] for k in changed), user, client_id=cid)

    def clients(self, q: str = "", limit: int = 300) -> list[sqlite3.Row]:
        sql = ("SELECT cl.*, (SELECT COUNT(*) FROM deals d WHERE d.client_id=cl.id) AS deals_n,"
               " (SELECT MAX(d.updated_at) FROM deals d WHERE d.client_id=cl.id) AS last_deal FROM clients cl")
        args: list[Any] = []
        if q:
            like = f"%{q.strip().lower()}%"
            sql += (" WHERE lower(cl.name) LIKE ? OR cl.phone LIKE ? OR lower(cl.email) LIKE ? OR lower(cl.company) LIKE ?"
                    " OR lower(cl.messenger) LIKE ? OR cl.inn LIKE ?")
            args += [like, like, like, like, like, like]
        sql += " ORDER BY COALESCE(last_deal, cl.updated_at) DESC LIMIT ?"
        args.append(limit)
        return self.c().execute(sql, args).fetchall()

    # ---------------------------------------------------------------- сделки
    def create_deal(self, user: str, user_id: int | None, *, name: str, contact: str = "", phone: str = "",
                    email: str = "", messenger: str = "", kind: str = "p", company: str = "", want: str = "",
                    source: str = "other", client_id: int | None = None, calc: str = "", consent_at: str = "",
                    consent_version: str = "", bot_lead_id: int | None = None, bot_client_id: int | None = None,
                    stage: str = "new", c: sqlite3.Connection | None = None) -> int:
        if contact and not (phone or email or messenger):
            phone, email, messenger = split_contact(contact)
        phone = norm_phone(phone) if phone else ""
        source = source if source in SOURCE_NAMES else "other"

        def run(c: sqlite3.Connection) -> int:
            cid = client_id or self.find_client(c, phone, email, bot_client_id)
            if cid:
                cl = c.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
                upd = {}
                if phone and not cl["phone"]:
                    upd["phone"] = phone
                if email and not cl["email"]:
                    upd["email"] = email
                if messenger and not cl["messenger"]:
                    upd["messenger"] = messenger
                if bot_client_id and not cl["bot_client_id"]:
                    upd["bot_client_id"] = bot_client_id
                if upd:
                    c.execute(f"UPDATE clients SET {', '.join(k + '=?' for k in upd)}, updated_at=? WHERE id=?",
                              (*upd.values(), iso_now(), cid))
                k = cl["kind"]
            else:
                cid = self.add_client(c, name, phone, email, messenger, kind, company, bot_client_id)
                k = kind
            ts = iso_now()
            cur = c.execute("INSERT INTO deals(client_id, want, source, stage, discount, calc, bot_lead_id, consent_at,"
                            " consent_version, created_at, updated_at, stage_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (cid, want.strip()[:2000], source, stage if stage in STAGE_NAMES else "new",
                             DESIGNER_DISCOUNT if k == "d" else 0, calc[:4000], bot_lead_id, consent_at, consent_version,
                             ts, ts, ts, user_id))
            did = int(cur.lastrowid)
            self.log(c, f"Создана заявка ({SOURCE_NAMES[source]})", user, deal_id=did, client_id=cid)
            self.auto_task(c, did, "Связаться с клиентом", 0, user)
            return did

        if c is not None:
            return run(c)
        with self.tx() as c2:
            return run(c2)

    def deal(self, did: int) -> sqlite3.Row | None:
        return self.c().execute(
            "SELECT d.*, cl.name AS client_name, cl.phone, cl.email, cl.messenger, cl.kind, cl.company, cl.inn,"
            " cl.note AS client_note, cl.bot_client_id FROM deals d JOIN clients cl ON cl.id=d.client_id WHERE d.id=?",
            (did,)).fetchone()

    def deals(self, stage: str | None = None, q: str = "", client_id: int | None = None, limit: int = 500) -> list[sqlite3.Row]:
        t = today()
        sql = ("SELECT d.*, cl.name AS client_name, cl.phone, cl.kind,"
               " (SELECT COALESCE(SUM(qty*price),0) FROM lines l WHERE l.deal_id=d.id) AS gross,"
               " (SELECT COUNT(*) FROM tasks tk WHERE tk.deal_id=d.id AND tk.done_at IS NULL) AS open_tasks,"
               " (SELECT COUNT(*) FROM tasks tk WHERE tk.deal_id=d.id AND tk.done_at IS NULL AND tk.due<?) AS overdue_tasks,"
               " (SELECT tk.title FROM tasks tk WHERE tk.deal_id=d.id AND tk.done_at IS NULL ORDER BY tk.due, tk.id LIMIT 1) AS task_title,"
               " (SELECT tk.due FROM tasks tk WHERE tk.deal_id=d.id AND tk.done_at IS NULL ORDER BY tk.due, tk.id LIMIT 1) AS task_due"
               " FROM deals d JOIN clients cl ON cl.id=d.client_id WHERE 1=1")
        args: list[Any] = [t]
        if stage:
            sql += " AND d.stage=?"
            args.append(stage)
        if client_id:
            sql += " AND d.client_id=?"
            args.append(client_id)
        if q:
            like = f"%{q.strip().lower()}%"
            sql += " AND (lower(cl.name) LIKE ? OR lower(d.want) LIKE ? OR cl.phone LIKE ?)"
            args += [like, like, like]
        sql += " ORDER BY d.updated_at DESC LIMIT ?"
        args.append(limit)
        return self.c().execute(sql, args).fetchall()

    @staticmethod
    def total(gross: int, discount: int) -> int:
        return int(round(gross * (100 - max(0, min(discount, 90))) / 100))

    def set_deal_text(self, did: int, user: str, client_note: str, pay_link: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE deals SET client_note=?, pay_link=?, updated_at=? WHERE id=?",
                      (client_note.strip()[:2000], pay_link.strip()[:500], iso_now(), did))

    def deal_total(self, did: int) -> tuple[int, int]:
        d = self.c().execute("SELECT discount FROM deals WHERE id=?", (did,)).fetchone()
        gross = int(self.c().execute("SELECT COALESCE(SUM(qty*price),0) FROM lines WHERE deal_id=?", (did,)).fetchone()[0])
        return gross, self.total(gross, int(d[0]) if d else 0)

    def update_deal(self, did: int, user: str, **f: Any) -> None:
        allowed = ("want", "discount", "address", "ship_date", "note", "lost_reason", "source")
        sets: dict[str, Any] = {}
        for k, v in f.items():
            if k not in allowed:
                continue
            if k == "discount":
                sets[k] = max(0, min(_to_int(v), 90))
            elif k == "source":
                if v in SOURCE_NAMES:
                    sets[k] = v
            elif k == "ship_date":
                v = (v or "").strip()
                if not v or re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                    sets[k] = v
            else:
                sets[k] = (v or "").strip()[:4000]
        if not sets:
            return
        with self.tx() as c:
            old = c.execute("SELECT * FROM deals WHERE id=?", (did,)).fetchone()
            if not old:
                return
            c.execute(f"UPDATE deals SET {', '.join(k + '=?' for k in sets)}, updated_at=? WHERE id=?",
                      (*sets.values(), iso_now(), did))
            names = {"want": "запрос", "discount": "скидка", "address": "адрес", "ship_date": "дата отгрузки",
                     "note": "заметка", "lost_reason": "причина отказа", "source": "источник"}
            changed = [k for k, v in sets.items() if str(old[k]) != str(v)]
            if changed:
                txt = ", ".join(names[k] + (f" {sets[k]}%" if k == "discount" else "") for k in changed)
                self.log(c, "Изменено: " + txt, user, deal_id=did, client_id=old["client_id"])

    def set_stage(self, did: int, stage: str, user: str) -> str | None:
        """Сменить этап. Отгрузка списывает товар со склада, возврат из «Отгружено» — возвращает."""
        if stage not in STAGE_NAMES:
            return None
        with self.tx() as c:
            d = c.execute("SELECT * FROM deals WHERE id=?", (did,)).fetchone()
            if not d or d["stage"] == stage:
                return None
            ts = iso_now()
            c.execute("UPDATE deals SET stage=?, stage_at=?, updated_at=? WHERE id=?", (stage, ts, ts, did))
            self.log(c, f"Этап: {STAGE_NAMES[d['stage']]} → {STAGE_NAMES[stage]}", user, deal_id=did, client_id=d["client_id"])
            # воронка замыкается задачами: что делать дальше на каждом этапе
            if stage == "work":
                self.close_tasks(c, did, user, "Связаться с клиентом")
                self.auto_task(c, did, "Отправить расчёт клиенту", 1, user)
            elif stage == "quote":
                self.close_tasks(c, did, user, "Связаться с клиентом"); self.close_tasks(c, did, user, "Отправить расчёт")
                self.auto_task(c, did, "Узнать решение по расчёту, предложить оплату", 2, user)
            elif stage == "paid":
                self.close_tasks(c, did, user, "Узнать решение"); self.close_tasks(c, did, user, "Отправить расчёт"); self.close_tasks(c, did, user, "Связаться с клиентом")
                self.auto_task(c, did, "Отгрузить: собрать заказ, согласовать доставку", 1, user)
            elif stage == "shipped":
                self.close_tasks(c, did, user)
                self.auto_task(c, did, "Попросить отзыв и фото стены", 7, user)
            elif stage == "lost":
                self.close_tasks(c, did, user)
            if stage == "shipped" and not d["stock_written"]:
                self._move_stock(c, did, -1, user)
                c.execute("UPDATE deals SET stock_written=1 WHERE id=?", (did,))
            elif stage != "shipped" and d["stock_written"]:
                self._move_stock(c, did, +1, user)
                c.execute("UPDATE deals SET stock_written=0 WHERE id=?", (did,))
            return d["stage"]

    def followup_candidates(self, day: str) -> list[sqlite3.Row]:
        """Сделки на этапе «Расчёт отправлен», где задача «Узнать решение…» подошла или просрочена, а менеджер её не закрыл:
        клиенту уходит вежливое напоминание (не больше двух), если у него есть e-mail и напоминания не выключены."""
        return self.c().execute(
            "SELECT d.id, d.followups FROM deals d JOIN clients cl ON cl.id=d.client_id"
            " WHERE d.stage='quote' AND d.no_followup=0 AND d.followups<2 AND cl.email LIKE '%@%'"
            " AND EXISTS (SELECT 1 FROM tasks t WHERE t.deal_id=d.id AND t.done_at IS NULL AND t.title LIKE 'Узнать решение%' AND t.due<=?)"
            " AND (d.followup_at='' OR substr(d.followup_at,1,10)<?) ORDER BY d.id", (day, day)).fetchall()

    def mark_followup(self, did: int, user: str, email: str, n: int, postpone_days: int = 3) -> None:
        """Записать отправленное напоминание и сдвинуть задачу «Узнать решение…» на несколько дней вперёд."""
        with self.tx() as c:
            c.execute("UPDATE deals SET followups=?, followup_at=?, updated_at=? WHERE id=?", (n, iso_now(), iso_now(), did))
            c.execute("UPDATE tasks SET due=? WHERE deal_id=? AND done_at IS NULL AND title LIKE 'Узнать решение%'",
                      ((date.fromisoformat(today()) + timedelta(days=postpone_days)).isoformat(), did))
            d = c.execute("SELECT client_id FROM deals WHERE id=?", (did,)).fetchone()
            self.log(c, f"Клиенту отправлено напоминание №{n} о расчёте на {email}", user, deal_id=did,
                     client_id=d["client_id"] if d else None)

    def set_no_followup(self, did: int, user: str, off: bool) -> None:
        with self.tx() as c:
            c.execute("UPDATE deals SET no_followup=?, updated_at=? WHERE id=?", (1 if off else 0, iso_now(), did))
            d = c.execute("SELECT client_id FROM deals WHERE id=?", (did,)).fetchone()
            self.log(c, "Автонапоминания клиенту выключены" if off else "Автонапоминания клиенту включены", user,
                     deal_id=did, client_id=d["client_id"] if d else None)

    # ---------------------------------------------------------------- чат на сайте
    def chat_by_sid(self, sid: str) -> sqlite3.Row | None:
        return self.c().execute("SELECT * FROM chats WHERE sid=?", (sid,)).fetchone()

    def chat(self, cid: int) -> sqlite3.Row | None:
        return self.c().execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone()

    def chat_post(self, sid: str, who: str, text: str, author: str = "", name: str = "", contact: str = "",
                  page: str = "", consent: bool = False) -> tuple[int, int, bool]:
        """Сообщение в чат (who: client | staff | note). Возвращает (номер чата, номер сообщения или 0, новый ли чат)."""
        ts = iso_now()
        with self.tx() as c:
            ch = c.execute("SELECT * FROM chats WHERE sid=?", (sid,)).fetchone()
            new = ch is None
            if new:
                c.execute("INSERT INTO chats(sid, name, contact, page, consent_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                          (sid, name[:120], contact[:200], page[:300], ts if consent else "", ts, ts))
                cid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
            else:
                cid = int(ch["id"])
                sets, args = ["updated_at=?"], [ts]
                if name and name != ch["name"]:
                    sets.append("name=?"); args.append(name[:120])
                if contact and contact != ch["contact"]:
                    sets.append("contact=?"); args.append(contact[:200])
                if page:
                    sets.append("page=?"); args.append(page[:300])
                if consent and not ch["consent_at"]:
                    sets.append("consent_at=?"); args.append(ts)
                c.execute(f"UPDATE chats SET {', '.join(sets)} WHERE id=?", (*args, cid))
            mid = 0
            if text:
                c.execute("INSERT INTO chat_msgs(chat_id, who, author, text, created_at) VALUES (?,?,?,?,?)",
                          (cid, who, author[:60], text[:2000], ts))
                mid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
                if who == "client":
                    c.execute("UPDATE chats SET unread=unread+1 WHERE id=?", (cid,))
                elif who == "staff":
                    c.execute("UPDATE chats SET unread=0 WHERE id=?", (cid,))
        return cid, mid, new

    def chat_msgs(self, cid: int, after: int = 0, limit: int = 300) -> list[sqlite3.Row]:
        return self.c().execute("SELECT * FROM chat_msgs WHERE chat_id=? AND id>? ORDER BY id LIMIT ?", (cid, after, limit)).fetchall()

    def chats(self, limit: int = 200) -> list[sqlite3.Row]:
        return self.c().execute(
            "SELECT ch.*, (SELECT text FROM chat_msgs m WHERE m.chat_id=ch.id ORDER BY m.id DESC LIMIT 1) AS last_text,"
            " (SELECT who FROM chat_msgs m WHERE m.chat_id=ch.id ORDER BY m.id DESC LIMIT 1) AS last_who,"
            " (SELECT COUNT(*) FROM chat_msgs m WHERE m.chat_id=ch.id) AS n"
            " FROM chats ch WHERE EXISTS (SELECT 1 FROM chat_msgs m WHERE m.chat_id=ch.id)"
            " ORDER BY ch.unread>0 DESC, ch.updated_at DESC LIMIT ?", (limit,)).fetchall()

    def chat_stats(self) -> dict[str, Any]:
        c = self.c()
        week = (date.fromisoformat(today()) - timedelta(days=7)).isoformat()
        return {
            "total": int(c.execute("SELECT COUNT(*) FROM chats WHERE EXISTS (SELECT 1 FROM chat_msgs m WHERE m.chat_id=chats.id)").fetchone()[0]),
            "week": int(c.execute("SELECT COUNT(*) FROM chats WHERE created_at>=? AND EXISTS (SELECT 1 FROM chat_msgs m WHERE m.chat_id=chats.id)", (week,)).fetchone()[0]),
            "deals": int(c.execute("SELECT COUNT(*) FROM chats WHERE deal_id IS NOT NULL").fetchone()[0]),
            "unread": self.chat_unread(),
            "last": (c.execute("SELECT MAX(created_at) FROM chat_msgs WHERE who='client'").fetchone()[0] or ""),
        }

    def chat_unread(self) -> int:
        return int(self.c().execute("SELECT COUNT(*) FROM chats WHERE unread>0").fetchone()[0])

    def chat_read(self, cid: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE chats SET unread=0 WHERE id=?", (cid,))

    def chat_seen(self, cid: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE chats SET seen_at=? WHERE id=?", (iso_now(), cid))

    def chat_link_deal(self, cid: int, did: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE chats SET deal_id=? WHERE id=?", (did, cid))

    def chat_of_deal(self, did: int) -> sqlite3.Row | None:
        return self.c().execute("SELECT * FROM chats WHERE deal_id=? ORDER BY id DESC LIMIT 1", (did,)).fetchone()

    # ---------------------------------------------------------------- пуши
    def push_sub_save(self, user_id: int, endpoint: str, p256dh: str, auth: str, ua: str) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO push_subs(user_id, endpoint, p256dh, auth, ua, created_at) VALUES (?,?,?,?,?,?)"
                      " ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, p256dh=excluded.p256dh,"
                      " auth=excluded.auth, ua=excluded.ua, fails=0", (user_id, endpoint, p256dh, auth, ua, iso_now()))

    def push_subs(self, user_ids: list[int] | None = None) -> list[sqlite3.Row]:
        sql = "SELECT s.* FROM push_subs s JOIN users u ON u.id=s.user_id WHERE u.active=1"
        args: list[Any] = []
        if user_ids is not None:
            if not user_ids:
                return []
            sql += f" AND s.user_id IN ({','.join('?' * len(user_ids))})"
            args += list(user_ids)
        return self.c().execute(sql + " ORDER BY s.id", args).fetchall()

    def push_subs_all(self) -> list[sqlite3.Row]:
        return self.c().execute("SELECT s.*, u.name AS user_name FROM push_subs s JOIN users u ON u.id=s.user_id ORDER BY u.name, s.id").fetchall()

    def push_sub_result(self, sid: int, ok: bool) -> None:
        with self.tx() as c:
            if ok:
                c.execute("UPDATE push_subs SET last_ok=?, fails=0 WHERE id=?", (iso_now(), sid))
            else:
                c.execute("UPDATE push_subs SET fails=fails+1 WHERE id=?", (sid,))
                c.execute("DELETE FROM push_subs WHERE id=? AND fails>=20", (sid,))

    def push_sub_delete(self, sid: int | None = None, endpoint: str = "", user_id: int | None = None) -> None:
        with self.tx() as c:
            if sid is not None:
                c.execute("DELETE FROM push_subs WHERE id=?", (sid,))
            elif endpoint:
                c.execute("DELETE FROM push_subs WHERE endpoint=?" + (" AND user_id=?" if user_id else ""),
                          (endpoint, user_id) if user_id else (endpoint,))

    def mail_in(self, from_email: str, subject: str) -> tuple[int | None, str]:
        """Письмо на ящик магазина: если от клиента — запись в сделку, задача «Ответить на письмо клиента»,
        автонапоминание о расчёте откладывается. Возвращает (номер сделки или None, имя клиента)."""
        em = (from_email or "").strip().lower()
        if "@" not in em:
            return None, ""
        cl = self.c().execute("SELECT id, name FROM clients WHERE lower(email)=? ORDER BY id DESC LIMIT 1", (em,)).fetchone()
        if not cl:
            return None, ""
        d = self.c().execute("SELECT id FROM deals WHERE client_id=? ORDER BY (stage IN ('shipped','lost')), updated_at DESC LIMIT 1",
                             (cl["id"],)).fetchone()
        if not d:
            return None, cl["name"]
        did = int(d["id"])
        with self.tx() as c:
            self.log(c, f"Письмо от клиента: «{(subject or '(без темы)')[:150]}»", "почта", deal_id=did, client_id=cl["id"])
            self.auto_task(c, did, "Ответить на письмо клиента", 0, "почта")
            later = (date.fromisoformat(today()) + timedelta(days=2)).isoformat()
            c.execute("UPDATE tasks SET due=? WHERE deal_id=? AND done_at IS NULL AND title LIKE 'Узнать решение%' AND due<?",
                      (later, did, later))
            c.execute("UPDATE deals SET updated_at=? WHERE id=?", (iso_now(), did))
        return did, cl["name"]

    def digest(self, day: str) -> dict[str, int]:
        c = self.c()
        return {
            "new": int(c.execute("SELECT COUNT(*) FROM deals WHERE stage='new'").fetchone()[0]),
            "today": int(c.execute("SELECT COUNT(*) FROM tasks WHERE done_at IS NULL AND due=?", (day,)).fetchone()[0]),
            "overdue": int(c.execute("SELECT COUNT(*) FROM tasks WHERE done_at IS NULL AND due<?", (day,)).fetchone()[0]),
            "paid": int(c.execute("SELECT COUNT(*) FROM deals WHERE stage='paid'").fetchone()[0]),
        }

    def rename_open_task(self, did: int, old: str, new: str, user: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE tasks SET title=? WHERE deal_id=? AND done_at IS NULL AND title=?", (new, did, old))

    def next_stage(self, did: int, user: str) -> str | None:
        d = self.c().execute("SELECT stage FROM deals WHERE id=?", (did,)).fetchone()
        if not d:
            return None
        order = [s for s, _ in STAGES if s != "lost"]
        if d["stage"] not in order or d["stage"] == order[-1]:
            return None
        nxt = order[order.index(d["stage"]) + 1]
        self.set_stage(did, nxt, user)
        return nxt

    def _move_stock(self, c: sqlite3.Connection, did: int, sign: int, user: str) -> None:
        rows = c.execute("SELECT article, SUM(qty) q FROM lines WHERE deal_id=? GROUP BY article", (did,)).fetchall()
        ts = iso_now()
        parts = []
        for r in rows:
            if not r["q"]:
                continue
            c.execute("INSERT INTO stock(article, qty, updated_at, updated_by) VALUES (?,0,?,?) ON CONFLICT(article) DO NOTHING",
                      (r["article"], ts, user))
            c.execute("UPDATE stock SET qty=qty+?, updated_at=?, updated_by=? WHERE article=?",
                      (sign * int(r["q"]), ts, user, r["article"]))
            parts.append(f"{r['article']} {sign * int(r['q']):+d}")
        if parts:
            self.log(c, ("Списано со склада: " if sign < 0 else "Возвращено на склад: ") + ", ".join(parts), user, deal_id=did)

    def delete_deal(self, did: int, user: str) -> bool:
        with self.tx() as c:
            d = c.execute("SELECT * FROM deals WHERE id=?", (did,)).fetchone()
            if not d:
                return False
            if d["stock_written"]:
                self._move_stock(c, did, +1, user)
            c.execute("DELETE FROM deals WHERE id=?", (did,))
            self.log(c, f"Удалена заявка №{did}", user, client_id=d["client_id"])
            return True

    # позиции
    def lines(self, did: int) -> list[sqlite3.Row]:
        return self.c().execute("SELECT * FROM lines WHERE deal_id=? ORDER BY id", (did,)).fetchall()

    def lines_from_calc(self, did: int, calc: str, user: str) -> int:
        """Разобрать расчёт с сайта и сразу положить позиции в сделку. Возвращает число позиций."""
        n = 0
        for m in re.finditer(r"(?:^|\n|Товар:\s*)([A-ZА-Я]{0,2}\s?[0-9][0-9A-Za-zА-Яа-я/\-]*)(?:\s*\([^)]*\))?\s*[—-]\s*(\d+)\s*шт", calc or ""):
            p = self.catalog.find(m.group(1))
            if p and self.add_line(did, p.article, int(m.group(2)), user):
                n += 1
        return n

    def add_line(self, did: int, article: str, qty: int, user: str, price: int | None = None) -> str | None:
        p = self.catalog.get(article)
        art = p.article if p else (article or "").strip().upper()[:30]
        if not art:
            return None
        if price is None:
            price = self.price_of(art)
        qty = max(0, min(_to_int(qty), 100000))
        with self.tx() as c:
            d = c.execute("SELECT * FROM deals WHERE id=?", (did,)).fetchone()
            if not d:
                return None
            ex = c.execute("SELECT id, qty FROM lines WHERE deal_id=? AND article=?", (did, art)).fetchone()
            if ex:
                c.execute("UPDATE lines SET qty=? WHERE id=?", (qty, ex["id"]))
            else:
                c.execute("INSERT INTO lines(deal_id, article, qty, price) VALUES (?,?,?,?)", (did, art, qty, price))
            c.execute("UPDATE deals SET updated_at=? WHERE id=?", (iso_now(), did))
            if d["stock_written"]:  # уже отгружено — склад поправить на разницу
                diff = qty - (int(ex["qty"]) if ex else 0)
                if diff:
                    c.execute("INSERT INTO stock(article, qty, updated_at, updated_by) VALUES (?,0,?,?) ON CONFLICT(article) DO NOTHING",
                              (art, iso_now(), user))
                    c.execute("UPDATE stock SET qty=qty-? WHERE article=?", (diff, art))
            self.log(c, f"Позиция {art}: {qty} шт", user, deal_id=did)
            return art

    def set_line(self, line_id: int, qty: int, price: int | None, user: str) -> None:
        with self.tx() as c:
            ln = c.execute("SELECT l.*, d.stock_written FROM lines l JOIN deals d ON d.id=l.deal_id WHERE l.id=?", (line_id,)).fetchone()
            if not ln:
                return
            qty = max(0, min(_to_int(qty), 100000))
            price = max(0, _to_int(price)) if price is not None else ln["price"]
            c.execute("UPDATE lines SET qty=?, price=? WHERE id=?", (qty, price, line_id))
            if ln["stock_written"] and qty != ln["qty"]:
                c.execute("UPDATE stock SET qty=qty-? WHERE article=?", (qty - ln["qty"], ln["article"]))
            c.execute("UPDATE deals SET updated_at=? WHERE id=?", (iso_now(), ln["deal_id"]))
            if qty != ln["qty"] or price != ln["price"]:
                self.log(c, f"Позиция {ln['article']}: {qty} шт × {price} ₽", user, deal_id=ln["deal_id"])

    def del_line(self, line_id: int, user: str) -> int | None:
        with self.tx() as c:
            ln = c.execute("SELECT l.*, d.stock_written FROM lines l JOIN deals d ON d.id=l.deal_id WHERE l.id=?", (line_id,)).fetchone()
            if not ln:
                return None
            if ln["stock_written"] and ln["qty"]:
                c.execute("UPDATE stock SET qty=qty+? WHERE article=?", (ln["qty"], ln["article"]))
            c.execute("DELETE FROM lines WHERE id=?", (line_id,))
            self.log(c, f"Убрана позиция {ln['article']}", user, deal_id=ln["deal_id"])
            return int(ln["deal_id"])

    # ---------------------------------------------------------------- задачи
    def add_task(self, did: int | None, title: str, due: str, user: str, user_id: int | None) -> None:
        title = (title or "").strip()[:300]
        if not title:
            return
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due or ""):
            due = today()
        with self.tx() as c:
            c.execute("INSERT INTO tasks(deal_id, title, due, created_by, created_at) VALUES (?,?,?,?,?)",
                      (did, title, due, user_id, iso_now()))
            if did:
                self.log(c, f"Задача: {title} (до {fmt_day(due)})", user, deal_id=did)

    def auto_task(self, c: sqlite3.Connection, did: int, title: str, days: int, user: str) -> None:
        """Задача по воронке (если такой открытой ещё нет): срок — через days дней."""
        if c.execute("SELECT 1 FROM tasks WHERE deal_id=? AND title=? AND done_at IS NULL", (did, title)).fetchone():
            return
        due = (date.fromisoformat(today()) + timedelta(days=days)).isoformat()
        c.execute("INSERT INTO tasks(deal_id, title, due, created_by, created_at) VALUES (?,?,?,?,?)", (did, title, due, None, iso_now()))
        self.log(c, f"Задача: {title} (до {fmt_day(due)})", user or "воронка", deal_id=did)

    def close_tasks(self, c: sqlite3.Connection, did: int, user: str, title_like: str = "") -> int:
        """Закрыть открытые задачи сделки (все или по началу названия)."""
        rows = c.execute("SELECT id, title FROM tasks WHERE deal_id=? AND done_at IS NULL" + (" AND title LIKE ?" if title_like else ""),
                         (did, title_like + "%") if title_like else (did,)).fetchall()
        for r in rows:
            c.execute("UPDATE tasks SET done_at=? WHERE id=?", (iso_now(), r["id"]))
            self.log(c, f"Сделано: {r['title']}", user or "воронка", deal_id=did)
        return len(rows)

    def done_task(self, tid: int, done: bool, user: str) -> int | None:
        with self.tx() as c:
            t = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
            if not t:
                return None
            c.execute("UPDATE tasks SET done_at=? WHERE id=?", (iso_now() if done else None, tid))
            if t["deal_id"] and done and not t["done_at"]:
                self.log(c, f"Сделано: {t['title']}", user, deal_id=t["deal_id"])
            return t["deal_id"]

    def tasks(self, deal_id: int | None = None, open_only: bool = True, until: str | None = None) -> list[sqlite3.Row]:
        sql = ("SELECT t.*, d.client_id, cl.name AS client_name FROM tasks t LEFT JOIN deals d ON d.id=t.deal_id"
               " LEFT JOIN clients cl ON cl.id=d.client_id WHERE 1=1")
        args: list[Any] = []
        if deal_id:
            sql += " AND t.deal_id=?"
            args.append(deal_id)
        if open_only:
            sql += " AND t.done_at IS NULL"
        if until:
            sql += " AND t.due<=?"
            args.append(until)
        sql += " ORDER BY t.done_at IS NOT NULL, t.due, t.id"
        return self.c().execute(sql, args).fetchall()

    # ---------------------------------------------------------------- склад
    def price_of(self, article: str) -> int:
        row = self.c().execute("SELECT price FROM stock WHERE article=?", (article,)).fetchone()
        if row and row[0] is not None:
            return int(row[0])
        p = self.catalog.get(article)
        return p.price if p else 0

    def reserved(self) -> dict[str, int]:
        rows = self.c().execute(
            "SELECT l.article, SUM(l.qty) FROM lines l JOIN deals d ON d.id=l.deal_id"
            f" WHERE d.stage IN ({','.join('?' * len(RESERVE_STAGES))}) GROUP BY l.article", RESERVE_STAGES).fetchall()
        return {r[0]: int(r[1] or 0) for r in rows}

    def stock_rows(self) -> list[dict[str, Any]]:
        own = {r["article"]: r for r in self.c().execute("SELECT * FROM stock").fetchall()}
        res = self.reserved()
        out = []
        seen = set()
        for p in self.catalog.all():
            s = own.get(p.article)
            out.append({"article": p.article, "kind": p.kind, "name": p.name, "size": p.size, "per_box": p.per_box,
                        "site_price": p.price, "price": (s["price"] if s and s["price"] is not None else p.price),
                        "own_price": s is not None and s["price"] is not None, "qty": int(s["qty"]) if s else 0,
                        "reserved": res.get(p.article, 0), "in_catalog": True})
            seen.add(p.article)
        for a, s in own.items():  # артикулы, которых уже нет на сайте
            if a not in seen:
                out.append({"article": a, "kind": "", "name": "нет на сайте", "size": "", "per_box": 0, "site_price": 0,
                            "price": s["price"] or 0, "own_price": s["price"] is not None, "qty": int(s["qty"]),
                            "reserved": res.get(a, 0), "in_catalog": False})
        return out

    def public_catalog(self) -> dict[str, dict[str, int]]:
        """Для сайта и Авито: цена (своя из CRM или сайта) и свободный остаток (на складе минус отложено).
        Только то, что и так видит покупатель — без себестоимости и заявок."""
        out: dict[str, dict[str, int]] = {}
        for r in self.stock_rows():
            if r["in_catalog"]:
                out[r["article"]] = {"p": int(r["price"] or 0), "q": max(int(r["qty"]) - int(r["reserved"]), 0)}
        return out

    def set_stock(self, article: str, user: str, qty: Any = None, price: Any = None) -> bool:
        p = self.catalog.get(article)
        art = p.article if p else (article or "").strip().upper()
        if not art:
            return False
        with self.tx() as c:
            c.execute("INSERT INTO stock(article, qty, updated_at, updated_by) VALUES (?,0,?,?) ON CONFLICT(article) DO NOTHING",
                      (art, iso_now(), user))
            old = c.execute("SELECT * FROM stock WHERE article=?", (art,)).fetchone()
            if qty is not None and str(qty).strip() != "":
                q = max(0, _to_int(qty))
                if q != old["qty"]:
                    c.execute("UPDATE stock SET qty=?, updated_at=?, updated_by=? WHERE article=?", (q, iso_now(), user, art))
                    self.log(c, f"Склад {art}: {old['qty']} → {q} шт", user)
            if price is not None:
                pr = str(price).strip()
                newp = None if pr == "" else max(0, _to_int(pr))
                if p and newp == p.price:
                    newp = None  # совпадает с сайтом — своей цены нет
                if newp != old["price"]:
                    c.execute("UPDATE stock SET price=?, updated_at=?, updated_by=? WHERE article=?", (newp, iso_now(), user, art))
                    self.log(c, f"Цена {art}: {newp if newp is not None else 'как на сайте'}", user)
        return True

    # ---------------------------------------------------------------- сводка
    def summary(self) -> dict[str, Any]:
        c = self.c()
        by_stage = {r[0]: (int(r[1]), int(r[2] or 0)) for r in c.execute(
            "SELECT d.stage, COUNT(*), SUM((SELECT COALESCE(SUM(qty*price),0) FROM lines l WHERE l.deal_id=d.id)*(100-d.discount)/100)"
            " FROM deals d GROUP BY d.stage").fetchall()}
        week = (now() - timedelta(days=7)).isoformat(timespec="seconds")
        shipped_week = int(c.execute(
            "SELECT COALESCE(SUM((SELECT COALESCE(SUM(qty*price),0) FROM lines l WHERE l.deal_id=d.id)*(100-d.discount)/100),0)"
            " FROM deals d WHERE d.stage IN ('paid','shipped') AND d.stage_at>=?", (week,)).fetchone()[0])
        by_source = c.execute(
            "SELECT source, COUNT(*) n, SUM(stage IN ('paid','shipped')) won FROM deals GROUP BY source ORDER BY n DESC").fetchall()
        return {"by_stage": by_stage, "paid_week": shipped_week, "by_source": by_source}

    # ---------------------------------------------------------------- бот
    def _bot(self, readonly: bool = True) -> sqlite3.Connection | None:
        if not self.bot_db or not os.path.exists(self.bot_db):
            return None
        try:
            if readonly:
                conn = sqlite3.connect(f"file:{self.bot_db}?mode=ro", uri=True, timeout=10)
            else:
                conn = sqlite3.connect(self.bot_db, timeout=10, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=10000")
            return conn
        except sqlite3.Error:
            return None

    def import_bot_leads(self, force: bool = False) -> int:
        """Новые заявки из бота → сделки CRM (раз в 20 секунд, не чаще)."""
        if not force and time.monotonic() - self._last_import < 20:
            return 0
        if not self._import_lock.acquire(blocking=False):
            return 0
        try:
            self._last_import = time.monotonic()
            b = self._bot()
            if b is None:
                return 0
            try:
                last = int(self.setting("bot_last_lead", "0") or 0)
                rows = b.execute("SELECT l.*, c.username AS c_username, c.name AS c_name FROM leads l"
                                 " LEFT JOIN clients c ON c.id=l.client_id WHERE l.id>? ORDER BY l.id LIMIT 200",
                                 (last,)).fetchall()
            except sqlite3.Error:
                return 0
            finally:
                b.close()
            n = 0
            bot_new: list[tuple[Any, ...]] = []
            for r in rows:
                with self.tx() as c:
                    if not c.execute("SELECT 1 FROM deals WHERE bot_lead_id=?", (r["id"],)).fetchone():
                        phone, email, messenger = split_contact(r["contact"] or "")
                        uname = r["username"] or r["c_username"] or ""
                        if uname and not messenger:
                            messenger = "@" + uname.lstrip("@")
                        ch = r["channel"] if r["channel"] in ("tg", "max") else "tg"
                        if not messenger:
                            messenger = "MAX" if ch == "max" else "Telegram"
                        bot_new.append((r["name"] or r["c_name"] or "Клиент", r["comment"] or "", ch))
                        bot_new[-1] += (self.create_deal("бот", None, name=r["name"] or r["c_name"] or "Клиент", phone=phone, email=email,
                                         messenger=messenger, want=r["comment"] or "", source=ch, calc=r["calc"] or "",
                                         consent_at=r["consent_at"] or "", consent_version=r["consent_version"] or "",
                                         bot_lead_id=int(r["id"]), bot_client_id=r["client_id"], c=c),)
                        n += 1
                    c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('bot_last_lead', ?)", (str(r["id"]),))
            if self.on_notify:
                for nm, want, ch, did in bot_new:
                    try:
                        self.on_notify(f"Новая заявка из {'MAX' if ch == 'max' else 'Telegram'} №{did}", f"{nm}" + (f": {want[:150]}" if want else ""), f"/deals/{did}")
                    except Exception:  # noqa: BLE001
                        pass
            return n
        finally:
            self._import_lock.release()

    def bot_lead(self, lead_id: int) -> dict[str, Any] | None:
        b = self._bot()
        if b is None:
            return None
        try:
            r = b.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            ship = b.execute("SELECT * FROM shipments WHERE lead_id=?", (lead_id,)).fetchone()
            return {"lead": dict(r) if r else None, "ship": dict(ship) if ship else None}
        except sqlite3.Error:
            return None
        finally:
            b.close()

    def bot_messages(self, bot_client_id: int, limit: int = 60) -> list[dict[str, Any]]:
        b = self._bot()
        if b is None:
            return []
        try:
            rows = b.execute("SELECT created_at, direction, kind, text, admin_name, channel FROM messages"
                             " WHERE client_id=? ORDER BY id DESC LIMIT ?", (bot_client_id, limit)).fetchall()
            return [dict(r) for r in reversed(rows)]
        except sqlite3.Error:
            return []
        finally:
            b.close()

    def notify_team(self, text: str, roles: tuple[str, ...] = ("manager",), title: str = "", url: str = "") -> int:
        """Оповестить команду: пуш на телефоны (если включены) и текст через очередь бота (MAX/Telegram, если бот есть)."""
        if self.on_notify:
            try:
                body = text[len(title):].lstrip(" :,\n") if title and text.startswith(title) else text
                self.on_notify(title or "Наш декор", body, url or "/")
            except Exception:  # noqa: BLE001 — пуш не должен ломать заявку
                pass
        b = self._bot(readonly=False)
        if b is None:
            return 0
        try:
            persons = b.execute(f"SELECT id, deliver FROM persons WHERE role IN ({','.join('?' * len(roles))})", roles).fetchall()
            n = 0
            ts = int(time.time())
            for p in persons:
                seats = {r["channel"]: r["user_id"] for r in
                         b.execute("SELECT channel, user_id FROM team WHERE person_id=?", (p["id"],)).fetchall()}
                if not seats:
                    continue
                ch = p["deliver"] if p["deliver"] in seats else ("max" if "max" in seats else next(iter(seats)))
                b.execute("INSERT INTO outbox(created_ts, channel, chat_id, item, client_id, next_ts) VALUES (?,?,?,?,?,?)",
                          (ts, ch, seats[ch], json.dumps({"t": "text", "text": text}, ensure_ascii=False), None, ts))
                n += 1
            return n
        except sqlite3.Error:
            return 0
        finally:
            b.close()

    # ---------------------------------------------------------------- копия
    def backup(self, dest: str) -> None:
        dst = sqlite3.connect(dest)
        try:
            self.c().backup(dst)
        finally:
            dst.close()
