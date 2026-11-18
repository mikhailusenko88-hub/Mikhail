"""«Дизайнеры → База дизайнеров»: кому предлагаем «Наш декор» — студии с сайтов, Zoon и рейтингов
и дизайнеры с Авито (только питерские, удалёнщиков из других городов в базу не берём).

Кто в базе — ещё не клиент: это «кому написать». Карточка собирает всё для связи в одном месте:
письмо от mikhail@ (текст с личной строкой, перед отправкой его видно и можно поправить), сообщение для
Telegram / WhatsApp / MAX (скопировать и открыть чат), звонок со сценарием и кнопками итога, ссылки на сайт,
VK и Авито (в чат Авито не пишем — по правилам Авито сообщения только по сделке). Каждое касание — в историю,
следующий шаг CRM ставит сама. Кто заинтересовался — «В клиенты» (тогда в заявке можно указать, кто привёл).

Базу пополняет Claude через ветку outbox (папка dz/, шифр, как письма и документы) или люди вручную.
Тексты писем и сообщений — в базе CRM (Дизайнеры → База → «Тексты»), в открытом репозитории их нет.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from typing import Any, Iterable
from urllib.parse import quote

from store import iso_now, norm_phone, today

SCHEMA = """
CREATE TABLE IF NOT EXISTS dz_leads (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    source       TEXT NOT NULL DEFAULT 'other',
    prio         TEXT NOT NULL DEFAULT 'B',
    name         TEXT NOT NULL,
    person       TEXT NOT NULL DEFAULT '',
    kind         TEXT NOT NULL DEFAULT '',
    phone        TEXT NOT NULL DEFAULT '',
    phone2       TEXT NOT NULL DEFAULT '',
    email        TEXT NOT NULL DEFAULT '',
    telegram     TEXT NOT NULL DEFAULT '',
    whatsapp     TEXT NOT NULL DEFAULT '',
    max_link     TEXT NOT NULL DEFAULT '',
    vk           TEXT NOT NULL DEFAULT '',
    instagram    TEXT NOT NULL DEFAULT '',
    site         TEXT NOT NULL DEFAULT '',
    avito_profile TEXT NOT NULL DEFAULT '',
    avito_ad     TEXT NOT NULL DEFAULT '',
    area         TEXT NOT NULL DEFAULT '',
    about        TEXT NOT NULL DEFAULT '',
    hook         TEXT NOT NULL DEFAULT '',
    line         TEXT NOT NULL DEFAULT '',
    link         TEXT NOT NULL DEFAULT '',
    rating       TEXT NOT NULL DEFAULT '',
    city_check   TEXT NOT NULL DEFAULT '',
    price_from   TEXT NOT NULL DEFAULT '',
    contacts_note TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'new',
    next_step    TEXT NOT NULL DEFAULT '',
    next_at      TEXT NOT NULL DEFAULT '',
    note         TEXT NOT NULL DEFAULT '',
    last_subject TEXT NOT NULL DEFAULT '',
    client_id    INTEGER,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    updated_by   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS dz_leads_status ON dz_leads(status, next_at);
CREATE TABLE IF NOT EXISTS dz_touches (
    id       INTEGER PRIMARY KEY,
    lead_id  INTEGER NOT NULL REFERENCES dz_leads(id) ON DELETE CASCADE,
    at       TEXT NOT NULL,
    by_name  TEXT NOT NULL DEFAULT '',
    channel  TEXT NOT NULL DEFAULT 'note',
    text     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS dz_touches_lead ON dz_touches(lead_id, id);
"""

SOURCES: list[tuple[str, str]] = [("avito", "Авито"), ("zoon", "Zoon"), ("sostav", "Рейтинги"), ("site", "Заявка с сайта"),
                                  ("other", "Другое")]
SOURCE_NAMES = dict(SOURCES)
STATUSES: list[tuple[str, str]] = [
    ("new", "Новый"), ("found", "Контакт найден"), ("sent", "Написали"), ("nocall", "Не дозвонились"),
    ("reminded", "Напомнили"), ("interest", "Интерес"), ("models", "Модели и каталог отправлены"),
    ("talk", "Разговор с Михаилом"), ("partner", "Партнёр"), ("refused", "Отказ"), ("wrong", "Не по адресу"),
    ("skip", "Не писать")]
STATUS_NAMES = dict(STATUSES)
CLOSED = ("partner", "refused", "wrong", "skip")
# фильтры списка: ключ → (надпись, статусы)
FILTERS: list[tuple[str, str, tuple[str, ...]]] = [
    ("new", "Новые", ("new", "found")),
    ("work", "Написали", ("sent", "nocall", "reminded")),
    ("hot", "Интерес", ("interest", "models", "talk")),
    ("partner", "Партнёры", ("partner",)),
    ("closed", "Отказ и прочее", ("refused", "wrong", "skip")),
]
CHANNEL_NAMES = {"email": "Письмо", "telegram": "Telegram", "whatsapp": "WhatsApp", "max": "MAX", "vk": "VK",
                 "call": "Звонок", "form": "Форма на сайте", "models": "3D-модели и каталог", "note": "Заметка",
                 "status": "Статус", "import": "База"}
PRIOS = ("A", "B", "C")
# поля, которые можно править в карточке и присылать через канал
TEXT_FIELDS = ("name", "person", "kind", "phone", "phone2", "email", "telegram", "whatsapp", "max_link", "vk", "instagram",
               "site", "avito_profile", "avito_ad", "area", "about", "hook", "line", "link", "rating", "city_check",
               "price_from", "contacts_note")
CONTACT_FIELDS = ("phone", "phone2", "email", "telegram", "whatsapp", "max_link", "vk", "instagram", "site")
FIELD_MAX = {"about": 600, "hook": 400, "line": 600, "contacts_note": 600, "note": 2000}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]{1,64}@[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,24}$")
TG_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/(\+?[A-Za-z0-9_]{4,64})/?$|^@?([A-Za-z][A-Za-z0-9_]{3,31})$")
GMAIL = ("gmail.com", "googlemail.com")
DEFAULT_DAILY = 15            # писем в сутки из базы: новый домен — малыми партиями, чтобы не попасть в спам

# раздел сайта для письма: путь → подпись
LINKS: list[tuple[str, str]] = [
    ("/catalog/stenovye-paneli/", "Все стеновые панели с ценой за м²"),
    ("/catalog/reechnye-paneli/", "Реечные панели под покраску"),
    ("/catalog/paneli-pod-derevo/", "Панели под дерево и бетон"),
    ("/catalog/moldingi/", "Молдинги"),
    ("/catalog/plintusy/", "Плинтусы"),
    ("/catalog/karnizy/", "Потолочный плинтус"),
    ("/catalog/plintus-s-podsvetkoy/", "Плинтус с подсветкой"),
    ("/catalog/ugolki/", "Уголки"),
    ("/stati/moldingi-na-stene-v-interere/", "Статья «Молдинги на стене в интерьере»"),
    ("/stati/rejki-na-stenu-v-interere/", "Статья «Рейки на стену в интерьере»"),
]
LINK_NAMES = dict(LINKS)

# Тексты по умолчанию; свои (согласованные) — в настройках CRM (dz_tpl_*), их правят на странице «Тексты».
# Метки: {строка} — личная строка, {раздел} — «подпись: ссылка» на раздел сайта, {сайт}, {телефон}, {имя}, {тема},
# {кому} — «вашей студии» / «вашей компании» / «вам», {макс} — канал в MAX, {домен}.
MAX_CHANNEL = "https://max.ru/id470331302505_biz"
TEMPLATES: dict[str, tuple[str, str]] = {
    "m1_subject": ("Письмо 1 — тема", "Рейки, молдинги и плинтусы для ваших проектов — 3D-модели профилей"),
    "m1": ("Письмо 1 — текст", """Здравствуйте{имя}!

Меня зовут Михаил, магазин «Наш декор» в Санкт-Петербурге. Мы продаём стеновые реечные панели, плинтусы, молдинги и потолочные плинтусы из дюрополимера (ударопрочного полистирола): белые под покраску и с готовым декором под дерево и бетон.

{строка} {раздел}

Что можем предложить {кому}:
— 3D-модели всех профилей для 3ds Max, SketchUp, ArchiCAD, Revit и Blender, сечения в DXF — пришлём архивом;
— на сайте у каждого профиля — 3D-просмотр, чертёж сечения, любой цвет по RAL/NCS и примерка на стену нужного размера с расчётом количества;
— расчёт по вашему проекту — стены, проёмы, запас;
— отдельные условия для дизайнеров и студий — расскажу лично.

Если интересно — ответьте на это письмо, пришлю модели и каталог. Если не по адресу — напишите «нет», больше не побеспокою.

С уважением,
Михаил
«Наш декор» (ИП Усенко Ю. В.), Санкт-Петербург
{сайт}
{телефон}"""),
    "m2": ("Письмо 2 — напоминание (через 3 рабочих дня, один раз)", """Здравствуйте! Пишу ещё раз по поводу письма ниже: можем бесплатно прислать 3D-модели наших реек, молдингов и плинтусов для ваших проектов. Посмотреть профили в 3D и примерить на стену можно на сайте: {сайт}
Если сейчас не нужно — ответьте «нет», больше не напишем.

Михаил, «Наш декор», {телефон}
{сайт}
Канал в MAX: {макс}"""),
    "reply": ("Ответ тем, кому интересно", """Спасибо за ответ! Архив 3D-моделей и каталог придут отдельным письмом с info@{домен}. Цены, наличие и 3D каждого профиля — на сайте {сайт}: на странице панели во вкладке «3D · моя стена» можно ввести размеры стены заказчика и сразу увидеть количество. Условия для студий удобнее обсудить голосом — когда Михаилу позвонить вам и по какому номеру?

Михаил, «Наш декор», {телефон}
{сайт}
Канал в MAX: {макс}"""),
    "msg": ("Сообщение в Telegram / WhatsApp / MAX", """Здравствуйте! Это «Наш декор» из Петербурга — реечные панели, плинтусы и молдинги под покраску и под дерево. Работаем с дизайнерами: бесплатно присылаем 3D-модели всех профилей (3ds Max, SketchUp, ArchiCAD, Revit, Blender), считаем количество по проекту, для студий — свои условия. Каталог с 3D, ценами и расчётом стены: {сайт}
Прислать вам модели? Куда удобнее — сюда или на почту?"""),
    "call": ("Звонок — как говорить", """1. «Здравствуйте! Меня зовут Юлия, магазин «Наш декор», Санкт-Петербург. Мы продаём рейки, молдинги и плинтусы под покраску и под дерево. Подскажите, кто у вас подбирает отделочные материалы для проектов?»
2. Когда соединили: «Мы работаем с дизайнерами: бесплатно присылаем 3D-модели всех профилей и считаем количество по проекту. Весь каталог с 3D и ценами — на сайте nashdekor.ru. Для студий есть свои условия — их Михаил расскажет лично.»
3. «Куда прислать ссылку на сайт, модели и каталог — на почту или в Telegram?» → внизу «Итог звонка: дали контакт».
4. «Не нужно» → «Отказ», больше не звоним.
Звонить 11:00–13:00 и 15:00–17:00. Ремонтным компаниям — просить снабженца или того, кто закупает отделку."""),
}
TEMPLATE_KEYS = tuple(TEMPLATES)


def add_workdays(start: str, n: int) -> str:
    d = date.fromisoformat(start)
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.isoformat()


def add_days(start: str, n: int) -> str:
    return (date.fromisoformat(start) + timedelta(days=n)).isoformat()


def tg_user(v: str) -> str:
    """Имя в Telegram из «@name», «t.me/name» или ссылки-приглашения → то, что идёт после t.me/ (или '')."""
    m = TG_RE.match((v or "").strip())
    return (m.group(1) or m.group(2)) if m else ""


def safe_http(v: str) -> str:
    """Ссылка на сайт / VK / Авито — только http(s), без пробелов и кавычек; иначе ''."""
    v = (v or "").strip()
    if not v:
        return ""
    if not re.match(r"^https?://", v, re.I):
        v = "https://" + v
    return v if re.fullmatch(r"https?://[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?:[/?#][^\s\"'<>]*)?", v) else ""


def wa_digits(v: str) -> str:
    d = re.sub(r"\D", "", v or "")
    if len(d) == 11 and d[0] == "8":
        d = "7" + d[1:]
    return d if 10 <= len(d) <= 15 else ""


def first_name(person: str) -> str:
    p = (person or "").strip().split()
    if not p:
        return ""
    # «Фамилия Имя» встречается у Авито-профилей; берём слово, похожее на имя (не на фамилию с -ова/-ев/-ин)
    if len(p) >= 2 and re.search(r"(ов|ев|ин|ова|ева|ина|ский|ская|ко|ук|юк)$", p[0]):
        return p[1]
    return p[0]


class DzLeads:
    def __init__(self, store: Any, domain: str = "") -> None:
        self.s = store
        self.domain = domain or "nashdekor.ru"
        c = self.s.c()
        for stmt in [x.strip() for x in SCHEMA.split(";") if x.strip()]:
            c.execute(stmt)

    # ------------------------------------------------------------------ чтение
    def get(self, lid: int) -> sqlite3.Row | None:
        return self.s.c().execute("SELECT * FROM dz_leads WHERE id=?", (lid,)).fetchone()

    def by_code(self, code: str) -> sqlite3.Row | None:
        return self.s.c().execute("SELECT * FROM dz_leads WHERE code=?", (code,)).fetchone()

    def touches(self, lid: int, limit: int = 100) -> list[sqlite3.Row]:
        return self.s.c().execute("SELECT * FROM dz_touches WHERE lead_id=? ORDER BY id DESC LIMIT ?", (lid, limit)).fetchall()

    def list(self, group: str = "", f: str = "", q: str = "", prio: str = "") -> list[sqlite3.Row]:
        sql, args = "SELECT * FROM dz_leads WHERE 1=1", []
        if group == "avito":
            sql += " AND source='avito'"
        elif group == "other":
            sql += " AND source<>'avito'"
        if prio in PRIOS:
            sql += " AND prio=?"
            args.append(prio)
        if f == "today":
            sql += f" AND next_at<>'' AND next_at<=? AND status NOT IN ({','.join('?' * len(CLOSED))})"
            args += [today(), *CLOSED]
        elif f == "contact":
            sql += " AND status IN ('new','found') AND (email<>'' OR telegram<>'' OR whatsapp<>'' OR max_link<>'' OR phone<>'')"
        else:
            for key, _n, sts in FILTERS:
                if f == key:
                    sql += f" AND status IN ({','.join('?' * len(sts))})"
                    args += list(sts)
        sql += " ORDER BY CASE WHEN status IN ('partner','refused','wrong','skip') THEN 1 ELSE 0 END, prio, " \
               "CASE WHEN source='avito' THEN 1 ELSE 0 END, code"
        rows = self.s.c().execute(sql, args).fetchall()
        q = (q or "").strip().casefold()                 # lower() в SQLite не знает кириллицу — ищем в Python
        if q:
            rows = [r for r in rows if q in " ".join(str(r[k] or "") for k in
                                                     ("code", "name", "person", "area", "about", "email", "phone", "telegram")).casefold()]
        return rows

    def counts(self) -> dict[str, int]:
        c = self.s.c()
        out: dict[str, int] = {}
        for g, cond in (("all", "1=1"), ("avito", "source='avito'"), ("other", "source<>'avito'")):
            out[g] = int(c.execute(f"SELECT COUNT(*) FROM dz_leads WHERE {cond}").fetchone()[0])
        out["today"] = self.due_today()
        return out

    def due_today(self) -> int:
        return int(self.s.c().execute(
            f"SELECT COUNT(*) FROM dz_leads WHERE next_at<>'' AND next_at<=? AND status NOT IN ({','.join('?' * len(CLOSED))})",
            (today(), *CLOSED)).fetchone()[0])

    def sent_today(self) -> int:
        return int(self.s.c().execute("SELECT COUNT(*) FROM dz_touches WHERE channel='email' AND substr(at,1,10)=?",
                                      (today(),)).fetchone()[0])

    def daily_limit(self) -> int:
        try:
            return max(1, min(60, int(self.s.setting("dz_mail_day", str(DEFAULT_DAILY)))))
        except ValueError:
            return DEFAULT_DAILY

    def by_email(self, email: str) -> sqlite3.Row | None:
        if not email:
            return None
        return self.s.c().execute("SELECT * FROM dz_leads WHERE lower(email)=lower(?) ORDER BY id LIMIT 1", (email.strip(),)).fetchone()

    # ------------------------------------------------------------------ запись
    def _touch(self, c: sqlite3.Connection, lid: int, channel: str, text: str, by: str) -> None:
        c.execute("INSERT INTO dz_touches(lead_id, at, by_name, channel, text) VALUES (?,?,?,?,?)",
                  (lid, iso_now(), by[:60], channel if channel in CHANNEL_NAMES else "note", (text or "")[:4000]))

    def touch(self, lid: int, channel: str, text: str, by: str) -> None:
        with self.s.tx() as c:
            self._touch(c, lid, channel, text, by)
            c.execute("UPDATE dz_leads SET updated_at=?, updated_by=? WHERE id=?", (iso_now(), by[:60], lid))

    def _clean(self, k: str, v: Any) -> str:
        v = re.sub(r"[ \t]+", " ", str(v or "").replace("\r\n", "\n")).strip()[:FIELD_MAX.get(k, 300)]
        if k in ("phone", "phone2") and v:
            v = norm_phone(v) or v
        if k == "email":
            v = v.lower()
            if v and not EMAIL_RE.match(v):
                v = ""
        if k in ("site", "vk", "avito_profile", "avito_ad", "instagram", "max_link") and v:
            v = safe_http(v)
        if k == "telegram" and v:
            u = tg_user(v)
            v = ("@" + u) if u and not u.startswith("+") else (f"https://t.me/{u}" if u else "")
        if k == "whatsapp" and v:
            v = wa_digits(v)
        return v

    def update(self, lid: int, by: str, **f: Any) -> list[str]:
        """Правка данных карточки. Возвращает список изменённых полей."""
        row = self.get(lid)
        if not row:
            return []
        sets = {k: self._clean(k, v) for k, v in f.items() if k in TEXT_FIELDS}
        if "prio" in f and f["prio"] in PRIOS:
            sets["prio"] = f["prio"]
        if "source" in f and f["source"] in SOURCE_NAMES:
            sets["source"] = f["source"]
        if "name" in sets and not sets["name"]:
            sets.pop("name")
        changed = [k for k, v in sets.items() if str(row[k] or "") != v]
        if not changed:
            return []
        with self.s.tx() as c:
            c.execute("UPDATE dz_leads SET " + ", ".join(f"{k}=?" for k in changed) + ", updated_at=?, updated_by=? WHERE id=?",
                      [sets[k] for k in changed] + [iso_now(), by[:60], lid])
            if row["status"] == "new" and any(k in CONTACT_FIELDS and sets[k] for k in changed) and \
                    any(sets.get(k) or row[k] for k in ("email", "telegram", "whatsapp", "max_link")):
                c.execute("UPDATE dz_leads SET status='found' WHERE id=?", (lid,))
            self._touch(c, lid, "note", "Изменено: " + ", ".join(changed), by)
        return changed

    def set_status(self, lid: int, status: str, by: str, next_step: str | None = None, next_at: str | None = None,
                   note: str | None = None, quiet: bool = False) -> None:
        row = self.get(lid)
        if not row or status not in STATUS_NAMES:
            return
        sets: dict[str, str] = {"status": status}
        if next_step is not None:
            sets["next_step"] = next_step.strip()[:200]
        if next_at is not None:
            sets["next_at"] = next_at if re.fullmatch(r"\d{4}-\d{2}-\d{2}", next_at or "") else ""
        if status in CLOSED and next_at is None:
            sets["next_step"], sets["next_at"] = "", ""
        if note is not None:
            sets["note"] = note.strip()[:FIELD_MAX["note"]]
        with self.s.tx() as c:
            c.execute("UPDATE dz_leads SET " + ", ".join(f"{k}=?" for k in sets) + ", updated_at=?, updated_by=? WHERE id=?",
                      list(sets.values()) + [iso_now(), by[:60], lid])
            if not quiet and status != row["status"]:
                self._touch(c, lid, "status", f"{STATUS_NAMES.get(row['status'], row['status'])} → {STATUS_NAMES[status]}"
                            + (f"; дальше: {sets.get('next_step')}" if sets.get("next_step") else ""), by)

    def add(self, by: str, name: str, source: str = "other", **f: Any) -> int:
        name = re.sub(r"\s+", " ", name or "").strip()[:200]
        if not name:
            raise ValueError("нужно имя или название студии")
        code = self._next_code(source)
        ts = iso_now()
        with self.s.tx() as c:
            cur = c.execute("INSERT INTO dz_leads(code, source, name, created_at, updated_at, updated_by) VALUES (?,?,?,?,?,?)",
                            (code, source if source in SOURCE_NAMES else "other", name, ts, ts, by[:60]))
            lid = int(cur.lastrowid)
            self._touch(c, lid, "import", "Добавлен в базу", by)
        self.update(lid, by, **f)
        return lid

    def _next_code(self, source: str) -> str:
        pre = "АВ" if source == "avito" else "Д"
        n = 0
        for r in self.s.c().execute("SELECT code FROM dz_leads WHERE code LIKE ?", (pre + "%",)).fetchall():
            m = re.fullmatch(re.escape(pre) + r"(\d+)", r["code"])
            if m:
                n = max(n, int(m.group(1)))
        return f"{pre}{n + 1:02d}"

    def import_items(self, items: Iterable[dict[str, Any]], by: str = "Claude") -> tuple[int, int]:
        """Загрузка из канала Claude: новые — целиком; существующие (по коду) — данные обновляются,
        пустые контакты дописываются, а статус и следующий шаг меняются, только если их ещё никто не трогал."""
        added = updated = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            code = re.sub(r"\s+", "", str(it.get("code") or ""))[:12]
            name = re.sub(r"\s+", " ", str(it.get("name") or "")).strip()[:200]
            if not code or not name:
                continue
            row = self.by_code(code)
            fields = {k: it[k] for k in TEXT_FIELDS if k in it}
            ts = iso_now()
            if not row:
                with self.s.tx() as c:
                    cur = c.execute("INSERT INTO dz_leads(code, source, prio, name, created_at, updated_at, updated_by) VALUES (?,?,?,?,?,?,?)",
                                    (code, it.get("source") if it.get("source") in SOURCE_NAMES else "other",
                                     it.get("prio") if it.get("prio") in PRIOS else "B", name, ts, ts, by))
                    lid = int(cur.lastrowid)
                    self._touch(c, lid, "import", str(it.get("history") or "Добавлен в базу")[:1000], by)
                sets = {k: self._clean(k, v) for k, v in fields.items()}
                st = it.get("status") if it.get("status") in STATUS_NAMES else ("found" if any(
                    sets.get(k) for k in ("email", "telegram", "whatsapp", "max_link")) else "new")
                with self.s.tx() as c:
                    if sets:
                        c.execute("UPDATE dz_leads SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?", [*sets.values(), lid])
                    c.execute("UPDATE dz_leads SET status=?, next_step=?, next_at=?, note=?, last_subject=? WHERE id=?",
                              (st, str(it.get("next_step") or "")[:200],
                               str(it.get("next_at") or "") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(it.get("next_at") or "")) else "",
                               str(it.get("note") or "")[:FIELD_MAX["note"]], str(it.get("last_subject") or "")[:200], lid))
                added += 1
                continue
            lid = int(row["id"])
            sets = {}
            for k, v in fields.items():
                v = self._clean(k, v)
                if not v:
                    continue
                if k in CONTACT_FIELDS and row[k]:
                    continue                                   # контакт, который вписали люди, не трогаем
                if str(row[k] or "") != v:
                    sets[k] = v
            if it.get("prio") in PRIOS and it.get("prio") != row["prio"] and row["updated_by"] == by:
                sets["prio"] = it["prio"]
            untouched = row["updated_by"] == by and not self.s.c().execute(
                "SELECT 1 FROM dz_touches WHERE lead_id=? AND by_name<>? LIMIT 1", (lid, by)).fetchone()
            with self.s.tx() as c:
                if sets:
                    c.execute("UPDATE dz_leads SET " + ", ".join(f"{k}=?" for k in sets) + ", updated_at=? WHERE id=?",
                              [*sets.values(), ts, lid])
                    self._touch(c, lid, "import", "Дополнено: " + ", ".join(sets), by)
                if untouched and it.get("status") in STATUS_NAMES and it.get("status") != row["status"]:
                    c.execute("UPDATE dz_leads SET status=?, next_step=?, next_at=? WHERE id=?",
                              (it["status"], str(it.get("next_step") or "")[:200],
                               str(it.get("next_at") or "") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(it.get("next_at") or "")) else "",
                               lid))
                elif row["status"] == "new" and any((sets.get(k) or row[k]) for k in ("email", "telegram", "whatsapp", "max_link")):
                    c.execute("UPDATE dz_leads SET status='found' WHERE id=?", (lid,))
            if sets:
                updated += 1
        return added, updated

    def import_payload(self, p: dict[str, Any]) -> tuple[int, int, str]:
        """Конверт из outbox/dz: {"kind": "dz", "items": [...], "settings": {"dz_tpl_m1": "…", "dz_phone": "…"}}."""
        if p.get("kind") != "dz":
            return 0, 0, "не тот формат"
        for k, v in (p.get("settings") or {}).items():
            if k.startswith("dz_tpl_") and k[7:] in TEMPLATES or k in ("dz_phone", "dz_mail_day", "dz_max"):
                self.s.set_setting(k, str(v)[:6000])
        a, u = self.import_items(p.get("items") or [])
        return a, u, ""

    # ------------------------------------------------------------------ тексты
    def tpl(self, key: str) -> str:
        return self.s.setting("dz_tpl_" + key, "") or TEMPLATES[key][1]

    def set_tpl(self, key: str, text: str) -> None:
        if key in TEMPLATES:
            text = (text or "").replace("\r\n", "\n").strip()[:6000]
            self.s.set_setting("dz_tpl_" + key, "" if text == TEMPLATES[key][1] else text)

    def phone(self) -> str:
        return self.s.setting("dz_phone", "")

    @staticmethod
    def whom(lead: Any) -> str:
        """«вашей студии» / «вашей компании» (ремонт, стройка) / «вам» (частный дизайнер)."""
        kind = ((lead["kind"] if lead is not None else "") or "").lower()
        if re.match(r"(ремонт|строит|стройк)", kind):
            return "вашей компании"
        if re.search(r"частн|самозан|команда", kind):
            return "вам"
        return "вашей студии"

    def site_url(self) -> str:
        return f"https://{self.domain}"

    def section(self, lead: Any) -> str:
        path = (lead["link"] or "").strip()
        if path.startswith("http"):
            path = re.sub(r"^https?://[^/]+", "", path)
        if not path or path == "/":
            return f"Сайт: {self.site_url()}"
        name = LINK_NAMES.get(path, "Подробнее")
        return f"{name}: {self.site_url()}{path}"

    def render(self, key: str, lead: Any) -> str:
        nm = first_name(lead["person"]) if lead is not None else ""
        subj = self.tpl("m1_subject")
        vals = {"{строка}": (lead["line"] or "").strip() if lead is not None else "",
                "{раздел}": self.section(lead) if lead is not None else self.site_url(),
                "{сайт}": self.site_url(), "{телефон}": self.phone(), "{имя}": (", " + nm) if nm else "", "{тема}": subj,
                "{кому}": self.whom(lead), "{макс}": self.s.setting("dz_max", MAX_CHANNEL) or MAX_CHANNEL, "{домен}": self.domain}
        t = self.tpl(key)
        for k, v in vals.items():
            t = t.replace(k, v)
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"(?m)^[ \t]+", "", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()

    def mail_draft(self, lead: Any) -> tuple[str, str, str]:
        """(вид, тема, текст) — что предложить в карточке: письмо 1, напоминание или ответ тем, кому интересно."""
        st = lead["status"]
        sent = self.s.c().execute("SELECT COUNT(*) FROM dz_touches WHERE lead_id=? AND channel='email'", (lead["id"],)).fetchone()[0]
        if st in ("interest", "models", "talk"):
            return "reply", "Re: " + (lead["last_subject"] or self.tpl("m1_subject")), self.render("reply", lead)
        if sent or st in ("sent", "reminded"):
            return "m2", "Re: " + (lead["last_subject"] or self.tpl("m1_subject")), self.render("m2", lead)
        return "m1", self.tpl("m1_subject"), self.render("m1", lead)

    # ------------------------------------------------------------------ события
    def after_mail(self, lid: int, kind: str, subject: str, body: str, by: str) -> None:
        row = self.get(lid)
        if not row:
            return
        with self.s.tx() as c:
            self._touch(c, lid, "email", f"{subject}\n\n{body}", by)
            c.execute("UPDATE dz_leads SET last_subject=? WHERE id=?", (re.sub(r"^(Re:\s*)+", "", subject)[:200], lid))
        t = today()
        if kind == "m2":
            self.set_status(lid, "reminded" if row["status"] not in ("interest", "models", "talk", "partner") else row["status"], by,
                            "Если молчат — Telegram или звонок", add_workdays(t, 3))
        elif kind == "reply":
            self.set_status(lid, row["status"] if row["status"] in ("models", "talk") else "interest", by,
                            "Отправить 3D-модели и каталог; договориться о звонке Михаила", t)
        elif row["status"] in ("new", "found", "nocall"):
            self.set_status(lid, "sent", by, "Напоминание (письмо 2), если не ответят", add_workdays(t, 3))
        else:
            self.set_status(lid, row["status"], by, row["next_step"], row["next_at"], quiet=True)

    def after_message(self, lid: int, channel: str, text: str, by: str) -> None:
        row = self.get(lid)
        if not row:
            return
        self.touch(lid, channel, text or "Отправлено сообщение", by)
        if row["status"] in ("new", "found", "nocall"):
            self.set_status(lid, "sent", by, "Если молчат — звонок", add_workdays(today(), 3))

    def after_call(self, lid: int, result: str, comment: str, by: str, **contacts: str) -> str:
        row = self.get(lid)
        if not row:
            return ""
        t = today()
        got = {k: v for k, v in contacts.items() if k in ("email", "telegram", "whatsapp", "phone2", "person") and (v or "").strip()}
        if got:
            self.update(lid, by, **got)
        text = {"noanswer": "Не дозвонились", "contact": "Дали контакт", "interest": "Интересно",
                "refused": "Отказ", "wrong": "Не по адресу", "later": "Перезвонить позже"}.get(result, "Звонок")
        self.touch(lid, "call", text + (f": {comment.strip()}" if (comment or "").strip() else "")
                   + (" · " + ", ".join(f"{k}: {v}" for k, v in got.items()) if got else ""), by)
        if result == "noanswer":
            self.set_status(lid, "nocall" if row["status"] in ("new", "found", "nocall") else row["status"], by,
                            "Перезвонить (11–13 или 15–17)", add_workdays(t, 1))
        elif result == "later":
            self.set_status(lid, row["status"], by, "Перезвонить: " + (comment or "").strip()[:150], add_workdays(t, 1))
        elif result == "contact":
            self.set_status(lid, "found", by, "Отправить письмо 1 или сообщение", t)
        elif result == "interest":
            self.set_status(lid, "interest", by, "Отправить 3D-модели и каталог", t)
        elif result == "refused":
            self.set_status(lid, "refused", by)
        elif result == "wrong":
            self.set_status(lid, "wrong", by)
        return text

    def after_models(self, email: str, titles: list[str], by: str) -> None:
        row = self.by_email(email)
        if not row:
            return
        self.touch(int(row["id"]), "models", "Отправлены по почте: " + ", ".join(titles), by)
        if row["status"] not in ("talk", "partner"):
            self.set_status(int(row["id"]), "models", by, "Проверить, скачал ли; предложить расчёт и звонок Михаила",
                            add_workdays(today(), 2))

    def to_client(self, lid: int, by: str) -> int | None:
        row = self.get(lid)
        if not row:
            return None
        if row["client_id"] and self.s.client(int(row["client_id"])):
            return int(row["client_id"])
        with self.s.tx() as c:
            cid = self.s.find_client(c, phone=norm_phone(row["phone"]) if row["phone"] else "", email=row["email"])
            if not cid:
                messenger = row["telegram"] or (("WhatsApp +" + row["whatsapp"]) if row["whatsapp"] else "") or row["max_link"]
                cid = self.s.add_client(c, row["person"] or row["name"], norm_phone(row["phone"]) if row["phone"] else "",
                                        row["email"], messenger, kind="d", company=row["name"] if row["person"] else "")
                self.s.log(c, f"Клиент из базы дизайнеров ({row['code']})", by, client_id=cid)
            c.execute("UPDATE dz_leads SET client_id=?, updated_at=?, updated_by=? WHERE id=?", (cid, iso_now(), by[:60], lid))
            self._touch(c, lid, "note", "Добавлен в «Клиенты»", by)
        return cid

    # ------------------------------------------------------------------ ссылки для кнопок
    def links(self, lead: Any) -> dict[str, str]:
        out: dict[str, str] = {}
        u = tg_user(lead["telegram"])
        if u:
            out["telegram"] = f"https://t.me/{u}"
        wa = wa_digits(lead["whatsapp"])
        if wa:
            out["whatsapp"] = f"https://wa.me/{wa}?text=" + quote(self.render("msg", lead))
        for k in ("max_link", "vk", "instagram", "site", "avito_profile", "avito_ad"):
            v = safe_http(lead[k])
            if v:
                out[k] = v
        for k in ("phone", "phone2"):
            p = norm_phone(lead[k]) if lead[k] else ""
            if p:
                out[k] = "tel:" + p
        return out

    def gmail(self, lead: Any) -> bool:
        return (lead["email"] or "").lower().rsplit("@", 1)[-1] in GMAIL
