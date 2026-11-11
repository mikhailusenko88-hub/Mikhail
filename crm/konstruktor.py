"""«Конструктор» CRM (Ещё → Конструктор): владелец сам расширяет CRM кнопками, без программиста.

  • Свои поля у заявки и клиента (текст, число, дата, список, галочка, ссылка) — k_fields / k_values.
  • Интеграции: события CRM (новая заявка, смена этапа, оплата, сообщение в чате) уходят по ссылке (вебхук с подписью
    HMAC-SHA256) или в Telegram — k_hooks, очередь k_queue (отправляет cron: prostranstvo-crm hooks, раз в минуту);
    приём заявок из других сервисов по секретной ссылке /api/in/<ключ> — k_inbound.
  • Шаблоны писем (расчёт, напоминания 1 и 2) и быстрые ответы — k_templates; {имя}, {номер}, {итого}… подставляются.
  • Автоправила: «заявка перешла на этап X → задача Y через N дней» — k_rules.
  • Свои ссылки в меню «Ещё» — k_links.
  • Excel: выгрузка клиентов, заявок, склада, оплат; загрузка клиентов и склада (xlsx без сторонних библиотек).
Телефон и e-mail клиента уходят во внешние сервисы, только если у интеграции стоит галочка «передавать контакты».
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
import secrets
import sqlite3
import urllib.error
import urllib.request
import zipfile
from datetime import date
from typing import Any
from xml.sax.saxutils import escape

SCHEMA = """
CREATE TABLE IF NOT EXISTS k_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT NOT NULL, label TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'text',
    options TEXT NOT NULL DEFAULT '', pos INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS k_values (
    entity TEXT NOT NULL, entity_id INTEGER NOT NULL, field_id INTEGER NOT NULL, value TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (entity, entity_id, field_id));
CREATE TABLE IF NOT EXISTS k_hooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'url', url TEXT NOT NULL DEFAULT '',
    secret TEXT NOT NULL DEFAULT '', events TEXT NOT NULL DEFAULT '', pd INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
    last_at TEXT NOT NULL DEFAULT '', last_status TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS k_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, event TEXT NOT NULL, deal_id INTEGER, client_id INTEGER,
    data TEXT NOT NULL DEFAULT '{}', targets TEXT NOT NULL DEFAULT '', tries INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS k_inbound (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, token TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT '', last_at TEXT NOT NULL DEFAULT '', count INTEGER NOT NULL DEFAULT 0,
    hour TEXT NOT NULL DEFAULT '', hour_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS k_templates (
    key TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'quick', title TEXT NOT NULL DEFAULT '', subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '', updated_by TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS k_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, stage TEXT NOT NULL, title TEXT NOT NULL, days INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS k_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, pos INTEGER NOT NULL DEFAULT 0);
"""

ENTITIES = [("deal", "Заявка"), ("client", "Клиент")]
FIELD_TYPES = [("text", "Текст"), ("long", "Длинный текст"), ("number", "Число"), ("date", "Дата"), ("select", "Список"),
               ("check", "Галочка"), ("link", "Ссылка")]
EVENTS = [("deal.created", "Новая заявка"), ("deal.stage", "Смена этапа"), ("payment.paid", "Оплата пришла"),
          ("chat.message", "Сообщение в чате с сайта")]
EVENT_NAMES = dict(EVENTS)
URL_RE = re.compile(r"^https://[^\s\"<>\\]{4,300}$")
TG_TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{30,60}$")
MAIL_TEMPLATES = [("calc", "Письмо-расчёт клиенту"), ("followup1", "Напоминание 1 — «подошёл ли расчёт?»"),
                  ("followup2", "Напоминание 2 — «расчёт действует до…»")]
PLACEHOLDERS = [("{имя}", "имя клиента"), ("{номер}", "номер заявки"), ("{итого}", "сумма к оплате"),
                ("{состав}", "позиции, скидка и итог (только в письме-расчёте)"), ("{позиции}", "коротко: артикулы и штуки"),
                ("{получение}", "адрес доставки или самовывоз"), ("{ссылка_на_оплату}", "ссылка СБП, если создана"),
                ("{дата_расчёта}", "когда отправлен расчёт"), ("{действует_до}", "до какого дня действует расчёт"),
                ("{заметка}", "заметка для клиента из карточки"), ("{менеджер}", "кто ведёт заявку"), ("{подпись}", "подпись магазина")]
INBOUND_PER_HOUR = 60


def _now() -> str:
    from store import iso_now
    return iso_now()


class Konstruktor:
    def __init__(self, store: Any) -> None:
        self.s = store
        self.s.c().executescript(SCHEMA)
        store.k = self              # store.set_stage / create_deal / chat_post / оплата зовут k.on_event внутри своей транзакции

    # ================================================================ свои поля
    def fields(self, entity: str = "", active_only: bool = False) -> list[sqlite3.Row]:
        q = "SELECT * FROM k_fields WHERE 1=1" + (" AND entity=?" if entity else "") + (" AND active=1" if active_only else "")
        return self.s.c().execute(q + " ORDER BY entity, pos, id", (entity,) if entity else ()).fetchall()

    def field_add(self, entity: str, label: str, ftype: str, options: str) -> int | str:
        label = re.sub(r"\s+", " ", label or "").strip()[:60]
        if entity not in dict(ENTITIES):
            return "выберите, где поле: в заявке или у клиента"
        if not label:
            return "напишите название поля"
        if ftype not in dict(FIELD_TYPES):
            return "выберите тип поля"
        opts = self._options(options)
        if ftype == "select" and len(opts) < 2:
            return "для списка напишите варианты — каждый с новой строки (не меньше двух)"
        with self.s.tx() as c:
            if c.execute("SELECT 1 FROM k_fields WHERE entity=? AND lower(label)=lower(?)", (entity, label)).fetchone():
                return "поле с таким названием уже есть"
            pos = int(c.execute("SELECT COALESCE(MAX(pos),0)+1 FROM k_fields WHERE entity=?", (entity,)).fetchone()[0])
            cur = c.execute("INSERT INTO k_fields(entity, label, type, options, pos, created_at) VALUES (?,?,?,?,?,?)",
                            (entity, label, ftype, "\n".join(opts), pos, _now()))
            return int(cur.lastrowid)

    @staticmethod
    def _options(text: str) -> list[str]:
        out: list[str] = []
        for x in (text or "").replace("\r", "").split("\n"):
            x = x.strip()[:80]
            if x and x not in out:
                out.append(x)
        return out[:40]

    def field_update(self, fid: int, label: str, options: str, active: bool) -> str:
        label = re.sub(r"\s+", " ", label or "").strip()[:60]
        f = self.s.c().execute("SELECT * FROM k_fields WHERE id=?", (fid,)).fetchone()
        if not f:
            return "нет такого поля"
        if not label:
            return "название не может быть пустым"
        opts = self._options(options)
        if f["type"] == "select" and len(opts) < 2:
            return "в списке нужно не меньше двух вариантов"
        with self.s.tx() as c:
            c.execute("UPDATE k_fields SET label=?, options=?, active=? WHERE id=?", (label, "\n".join(opts), 1 if active else 0, fid))
        return ""

    def field_move(self, fid: int, up: bool) -> None:
        with self.s.tx() as c:
            f = c.execute("SELECT * FROM k_fields WHERE id=?", (fid,)).fetchone()
            if not f:
                return
            other = c.execute(f"SELECT * FROM k_fields WHERE entity=? AND pos {'<' if up else '>'} ? ORDER BY pos {'DESC' if up else ''} LIMIT 1",
                              (f["entity"], f["pos"])).fetchone()
            if other:
                c.execute("UPDATE k_fields SET pos=? WHERE id=?", (other["pos"], fid))
                c.execute("UPDATE k_fields SET pos=? WHERE id=?", (f["pos"], other["id"]))

    def field_delete(self, fid: int) -> None:
        with self.s.tx() as c:
            c.execute("DELETE FROM k_values WHERE field_id=?", (fid,))
            c.execute("DELETE FROM k_fields WHERE id=?", (fid,))

    def values(self, entity: str, eid: int) -> dict[int, str]:
        return {int(r["field_id"]): r["value"] for r in
                self.s.c().execute("SELECT field_id, value FROM k_values WHERE entity=? AND entity_id=?", (entity, eid))}

    def form_rows(self, entity: str, eid: int) -> list[dict[str, Any]]:
        vals = self.values(entity, eid)
        return [{"f": f, "value": vals.get(int(f["id"]), ""), "options": f["options"].split("\n") if f["options"] else []}
                for f in self.fields(entity, active_only=True)]

    @staticmethod
    def clean_value(f: Any, raw: Any) -> tuple[str, str]:
        v = str(raw if raw is not None else "").replace("\r", "").strip()
        t = f["type"]
        if t == "check":
            return ("да" if v in ("1", "да", "on", "true", "True") else ""), ""
        if not v:
            return "", ""
        if t == "number":
            try:
                n = float(v.replace(" ", "").replace(" ", "").replace(",", "."))
            except ValueError:
                return "", f"«{f['label']}»: нужно число"
            return (str(int(n)) if n == int(n) else str(round(n, 4))).replace(".", ","), ""
        if t == "date":
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", v) or re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", v)
            if not m:
                return "", f"«{f['label']}»: дата в виде ДД.ММ.ГГГГ"
            y, mo, d = (m.group(1), m.group(2), m.group(3)) if len(m.group(1)) == 4 else (m.group(3), m.group(2), m.group(1))
            try:
                return date(int(y), int(mo), int(d)).isoformat(), ""
            except ValueError:
                return "", f"«{f['label']}»: такой даты нет"
        if t == "select":
            opts = f["options"].split("\n") if f["options"] else []
            return (v, "") if v in opts else ("", f"«{f['label']}»: выберите из списка")
        if t == "link":
            if not re.match(r"^https?://\S{3,500}$", v):
                return "", f"«{f['label']}»: ссылка должна начинаться с https://"
            return v[:500], ""
        return v[:4000 if t == "long" else 300], ""

    def save_values(self, entity: str, eid: int, form: dict[str, Any], user: str) -> list[str]:
        errs, changed = [], []
        cur = self.values(entity, eid)
        with self.s.tx() as c:
            for f in self.fields(entity, active_only=True):
                key = f"k{f['id']}"
                if key not in form and f["type"] != "check":
                    continue
                v, err = self.clean_value(f, form.get(key))
                if err:
                    errs.append(err)
                    continue
                if v != cur.get(int(f["id"]), ""):
                    c.execute("INSERT INTO k_values(entity, entity_id, field_id, value) VALUES (?,?,?,?) "
                              "ON CONFLICT(entity, entity_id, field_id) DO UPDATE SET value=excluded.value", (entity, eid, f["id"], v))
                    changed.append(f"{f['label']}: {v or '—'}")
            if changed:
                self.s.log(c, "Свои поля: " + "; ".join(changed)[:900], user,
                           deal_id=eid if entity == "deal" else None, client_id=eid if entity == "client" else None)
        return errs

    def labeled(self, entity: str, eid: int) -> dict[str, str]:
        vals = self.values(entity, eid)
        return {f["label"]: vals.get(int(f["id"]), "") for f in self.fields(entity, active_only=True) if vals.get(int(f["id"]))}

    # ================================================================ события → интеграции и автоправила
    def on_event(self, c: sqlite3.Connection, event: str, deal_id: int | None = None, client_id: int | None = None,
                 user: str = "", **data: Any) -> None:
        """Зовётся из Store внутри его транзакции: автоправила сразу, интеграции — в очередь (отправит cron)."""
        if event in ("deal.created", "deal.stage") and deal_id:
            stage = data.get("to") or "new"
            for r in c.execute("SELECT * FROM k_rules WHERE active=1 AND stage=?", (stage,)).fetchall():
                self.s.auto_task(c, deal_id, r["title"], int(r["days"]), user or "автоправило")
        targets = [str(h["id"]) for h in c.execute("SELECT id, events FROM k_hooks WHERE active=1").fetchall()
                   if event in (h["events"] or "").split(",")]
        if targets:
            c.execute("INSERT INTO k_queue(created_at, event, deal_id, client_id, data, targets) VALUES (?,?,?,?,?,?)",
                      (_now(), event, deal_id, client_id, json.dumps(data, ensure_ascii=False), ",".join(targets)))

    # ---- интеграции
    def hooks(self) -> list[sqlite3.Row]:
        return self.s.c().execute("SELECT * FROM k_hooks ORDER BY id").fetchall()

    def hook_save(self, hid: int | None, name: str, kind: str, url: str, chat: str, events: list[str], pd: bool, active: bool) -> str:
        name = re.sub(r"\s+", " ", name or "").strip()[:60]
        url = (url or "").strip()
        chat = (chat or "").strip()
        events = [e for e in events if e in EVENT_NAMES]
        if not name:
            return "напишите название (например, «Таблица заявок» или «Telegram Юлии»)"
        if not events:
            return "отметьте хотя бы одно событие"
        old = self.s.c().execute("SELECT * FROM k_hooks WHERE id=?", (hid,)).fetchone() if hid else None
        if kind == "telegram":
            if not url and old:
                url = old["url"]                  # токен не показываем на странице — пустое поле = оставить прежний
            if not TG_TOKEN_RE.match(url):
                return "токен Telegram-бота вида 123456789:AAE… (выдаёт @BotFather)"
            if not re.match(r"^-?\d{3,20}$", chat):
                return "номер чата Telegram — только цифры (для группы — с минусом впереди)"
            secret = chat
        elif kind == "url":
            if not URL_RE.match(url):
                return "адрес должен начинаться с https://"
            secret = old["secret"] if old and old["kind"] == "url" else secrets.token_hex(16)
        else:
            return "неизвестный вид интеграции"
        with self.s.tx() as c:
            if old:
                c.execute("UPDATE k_hooks SET name=?, kind=?, url=?, secret=?, events=?, pd=?, active=? WHERE id=?",
                          (name, kind, url, secret, ",".join(events), 1 if pd else 0, 1 if active else 0, hid))
            else:
                c.execute("INSERT INTO k_hooks(name, kind, url, secret, events, pd, active, created_at) VALUES (?,?,?,?,?,?,?,?)",
                          (name, kind, url, secret, ",".join(events), 1 if pd else 0, 1 if active else 0, _now()))
        return ""

    def hook_delete(self, hid: int) -> None:
        with self.s.tx() as c:
            c.execute("DELETE FROM k_hooks WHERE id=?", (hid,))

    def payload(self, ev: Any, pd: bool, base_url: str) -> dict[str, Any]:
        from store import SOURCE_NAMES, STAGE_NAMES
        data = json.loads(ev["data"] or "{}")
        out: dict[str, Any] = {"event": ev["event"], "event_name": EVENT_NAMES.get(ev["event"], ev["event"]), "at": ev["created_at"]}
        if ev["deal_id"]:
            d = self.s.deal(int(ev["deal_id"]))
            if d:
                gross, total = self.s.deal_total(int(d["id"]))
                out["deal"] = {"id": d["id"], "stage": d["stage"], "stage_name": STAGE_NAMES.get(d["stage"], d["stage"]),
                               "source": SOURCE_NAMES.get(d["source"], d["source"]), "want": (d["want"] or "")[:500], "total_rub": total,
                               "url": f"{base_url}/deals/{d['id']}", "custom": self.labeled("deal", int(d["id"]))}
                out["client"] = {"id": d["client_id"], "name": d["client_name"], "company": d["company"] or "",
                                 "custom": self.labeled("client", int(d["client_id"]))}
                if pd:
                    out["client"].update(phone=d["phone"] or "", email=d["email"] or "", messenger=d["messenger"] or "")
        if "from" in data:
            out["from_stage"] = STAGE_NAMES.get(data["from"], data["from"])
            out["to_stage"] = STAGE_NAMES.get(data.get("to", ""), data.get("to", ""))
        if "amount_rub" in data:
            out["payment"] = {"amount_rub": data["amount_rub"], "method": data.get("method", "")}
        if ev["event"] == "chat.message":
            out["chat"] = {"id": data.get("chat_id"), "text": (data.get("text") or "")[:1000] if pd else "", "url": f"{base_url}/chats/{data.get('chat_id')}"}
        return out

    @staticmethod
    def tg_text(p: dict[str, Any]) -> str:
        d, cl = p.get("deal") or {}, p.get("client") or {}
        parts = [f"«Наш декор»: {p['event_name']}"]
        if d:
            parts.append(f"№{d['id']} · {cl.get('name', '')}" + (f" · {cl['company']}" if cl.get("company") else ""))
            if p.get("to_stage"):
                parts.append(f"{p['from_stage']} → {p['to_stage']}")
            if p.get("payment"):
                parts.append(f"Оплата {p['payment']['amount_rub']:,} ₽".replace(",", " "))
            elif d.get("total_rub"):
                parts.append(f"Сумма {d['total_rub']:,} ₽".replace(",", " "))
            if cl.get("phone"):
                parts.append(f"Тел.: {cl['phone']}")
            if d.get("want"):
                parts.append(d["want"][:300])
            parts.append(d["url"])
        if p.get("chat"):
            if p["chat"].get("text"):
                parts.append(p["chat"]["text"][:500])
            parts.append(p["chat"]["url"])
        return "\n".join(parts)

    def send_one(self, h: Any, p: dict[str, Any], opener: Any = None) -> tuple[bool, str]:
        opener = opener or urllib.request.urlopen
        try:
            if h["kind"] == "telegram":
                body = json.dumps({"chat_id": h["secret"], "text": self.tg_text(p), "disable_web_page_preview": True}).encode()
                req = urllib.request.Request(f"https://api.telegram.org/bot{h['url']}/sendMessage", data=body,
                                             headers={"Content-Type": "application/json"})
            else:
                body = json.dumps(p, ensure_ascii=False).encode()
                sig = hmac.new(h["secret"].encode(), body, hashlib.sha256).hexdigest()
                req = urllib.request.Request(h["url"], data=body, headers={
                    "Content-Type": "application/json; charset=utf-8", "User-Agent": "nashdekor-crm/1",
                    "X-Nashdekor-Event": p["event"], "X-Nashdekor-Signature": "sha256=" + sig})
            with opener(req, timeout=10) as r:
                code = getattr(r, "status", 200)
            return (200 <= int(code) < 300), f"ответ {code}"
        except urllib.error.HTTPError as e:
            return False, f"ответ {e.code}"
        except Exception as e:  # noqa: BLE001 — сеть: любая ошибка = попробовать позже
            return False, f"нет связи ({type(e).__name__})"

    def run_queue(self, base_url: str, opener: Any = None, limit: int = 50) -> list[str]:
        """Отправить накопившиеся события (cron раз в минуту). 5 попыток, потом событие отбрасывается с ошибкой у интеграции."""
        out: list[str] = []
        hooks = {str(h["id"]): h for h in self.hooks()}
        for ev in self.s.c().execute("SELECT * FROM k_queue ORDER BY id LIMIT ?", (limit,)).fetchall():
            left = []
            for hid in [x for x in ev["targets"].split(",") if x]:
                h = hooks.get(hid)
                if not h or not h["active"]:
                    continue
                ok, why = self.send_one(h, self.payload(ev, bool(h["pd"]), base_url), opener)
                with self.s.tx() as c:
                    c.execute("UPDATE k_hooks SET last_at=?, last_status=? WHERE id=?",
                              (_now(), ("отправлено" if ok else "ошибка: ") + ("" if ok else why), hid))
                out.append(f"{h['name']}: {EVENT_NAMES.get(ev['event'], ev['event'])} — {'ок' if ok else why}")
                if not ok:
                    left.append(hid)
            with self.s.tx() as c:
                if left and ev["tries"] < 4:
                    c.execute("UPDATE k_queue SET targets=?, tries=tries+1 WHERE id=?", (",".join(left), ev["id"]))
                else:
                    c.execute("DELETE FROM k_queue WHERE id=?", (ev["id"],))
        return out

    def hook_test(self, hid: int, base_url: str, opener: Any = None) -> tuple[bool, str]:
        h = self.s.c().execute("SELECT * FROM k_hooks WHERE id=?", (hid,)).fetchone()
        if not h:
            return False, "нет такой интеграции"
        p = {"event": "test", "event_name": "Проверка связи", "at": _now(),
             "deal": {"id": 0, "stage_name": "—", "want": "Это проверка из CRM «Наш декор» — всё работает.", "total_rub": 0,
                      "url": base_url + "/k"}, "client": {"name": "Проверка"}}
        ok, why = self.send_one(h, p, opener)
        with self.s.tx() as c:
            c.execute("UPDATE k_hooks SET last_at=?, last_status=? WHERE id=?", (_now(), "проверка: " + ("ок" if ok else why), hid))
        return ok, why

    # ---- приём заявок из других сервисов
    def inbound(self) -> list[sqlite3.Row]:
        return self.s.c().execute("SELECT * FROM k_inbound ORDER BY id").fetchall()

    def inbound_add(self, name: str) -> str:
        name = re.sub(r"\s+", " ", name or "").strip()[:60]
        if not name:
            return "напишите, откуда заявки (например, «Квиз» или «Яндекс Формы»)"
        with self.s.tx() as c:
            c.execute("INSERT INTO k_inbound(name, token, created_at) VALUES (?,?,?)", (name, secrets.token_urlsafe(18), _now()))
        return ""

    def inbound_set(self, iid: int, active: bool | None = None, new_token: bool = False, delete: bool = False) -> None:
        with self.s.tx() as c:
            if delete:
                c.execute("DELETE FROM k_inbound WHERE id=?", (iid,))
                return
            if active is not None:
                c.execute("UPDATE k_inbound SET active=? WHERE id=?", (1 if active else 0, iid))
            if new_token:
                c.execute("UPDATE k_inbound SET token=? WHERE id=?", (secrets.token_urlsafe(18), iid))

    def inbound_take(self, token: str, data: dict[str, Any]) -> tuple[int, str]:
        """Заявка из внешнего сервиса → (номер заявки, ошибка)."""
        if not re.match(r"^[A-Za-z0-9_-]{16,40}$", token or ""):
            return 0, "нет такой ссылки"
        row = self.s.c().execute("SELECT * FROM k_inbound WHERE token=?", (token,)).fetchone()
        if not row or not row["active"]:
            return 0, "нет такой ссылки"
        hour = _now()[:13]
        if row["hour"] == hour and int(row["hour_count"]) >= INBOUND_PER_HOUR:
            return 0, "слишком много заявок за час"
        g = lambda *keys: next((str(data[k]).strip() for k in keys if data.get(k) not in (None, "")), "")  # noqa: E731
        name = g("name", "имя", "Имя", "fio", "ФИО")[:120] or "Без имени"
        phone, email = g("phone", "телефон", "Телефон", "tel")[:30], g("email", "e-mail", "почта", "Email")[:120]
        messenger = g("messenger", "telegram", "мессенджер")[:120]
        text = g("text", "comment", "message", "want", "комментарий", "сообщение", "Комментарий")[:1500]
        if not (phone or email or messenger):
            return 0, "нужен телефон, e-mail или мессенджер"
        extra = [f"{k}: {str(v)[:200]}" for k, v in data.items() if k not in (
            "name", "имя", "Имя", "fio", "ФИО", "phone", "телефон", "Телефон", "tel", "email", "e-mail", "почта", "Email",
            "messenger", "telegram", "мессенджер", "text", "comment", "message", "want", "комментарий", "сообщение", "Комментарий",
            "token", "csrf") and str(v).strip()][:15]
        want = f"[{row['name']}] " + (text or "заявка") + (("\n" + "\n".join(extra)) if extra else "")
        did = self.s.create_deal(f"интеграция «{row['name']}»", None, name=name, phone=phone, email=email, messenger=messenger,
                                 want=want, source="other")
        with self.s.tx() as c:
            c.execute("UPDATE k_inbound SET last_at=?, count=count+1, hour=?, hour_count=CASE WHEN hour=? THEN hour_count+1 ELSE 1 END "
                      "WHERE id=?", (_now(), hour, hour, row["id"]))
        return did, ""

    # ================================================================ шаблоны
    def template(self, key: str) -> sqlite3.Row | None:
        return self.s.c().execute("SELECT * FROM k_templates WHERE key=?", (key,)).fetchone()

    def templates(self, kind: str) -> list[sqlite3.Row]:
        return self.s.c().execute("SELECT * FROM k_templates WHERE kind=? ORDER BY title", (kind,)).fetchall()

    def template_save(self, key: str, kind: str, title: str, subject: str, body: str, user: str) -> str:
        body = (body or "").replace("\r\n", "\n").strip()
        subject = re.sub(r"\s+", " ", subject or "").strip()[:200]
        title = re.sub(r"\s+", " ", title or "").strip()[:80]
        if kind == "mail" and key not in dict(MAIL_TEMPLATES):
            return "нет такого письма"
        if kind == "mail" and not subject:
            return "напишите тему письма"
        if kind == "quick" and not title:
            return "напишите название быстрого ответа"
        if not 10 <= len(body) <= 8000:
            return "текст: от 10 до 8000 знаков"
        bad = re.findall(r"\{[^{}\s]{1,30}\}", subject + body)
        unknown = sorted({b for b in bad if b not in dict(PLACEHOLDERS)})
        if unknown:
            return "неизвестные подстановки: " + ", ".join(unknown) + " (список — справа от формы)"
        if kind == "quick" and not key:
            key = "q" + secrets.token_hex(4)
        with self.s.tx() as c:
            c.execute("INSERT INTO k_templates(key, kind, title, subject, body, updated_at, updated_by) VALUES (?,?,?,?,?,?,?) "
                      "ON CONFLICT(key) DO UPDATE SET title=excluded.title, subject=excluded.subject, body=excluded.body, "
                      "updated_at=excluded.updated_at, updated_by=excluded.updated_by", (key, kind, title, subject, body, _now(), user))
        return ""

    def template_delete(self, key: str) -> None:
        with self.s.tx() as c:
            c.execute("DELETE FROM k_templates WHERE key=?", (key,))

    @staticmethod
    def render(text: str, ctx: dict[str, str]) -> str:
        for k, v in ctx.items():
            text = text.replace("{" + k + "}", v)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    # ================================================================ автоправила и ссылки
    def rules(self) -> list[sqlite3.Row]:
        return self.s.c().execute("SELECT * FROM k_rules ORDER BY stage, id").fetchall()

    def rule_add(self, stage: str, title: str, days: Any) -> str:
        from store import STAGE_NAMES
        title = re.sub(r"\s+", " ", title or "").strip()[:120]
        if stage not in STAGE_NAMES or stage == "lost":
            return "выберите этап"
        if not 3 <= len(title) <= 120:
            return "напишите задачу (от 3 знаков)"
        try:
            d = int(str(days).strip() or "0")
        except ValueError:
            return "через сколько дней — числом"
        if not 0 <= d <= 365:
            return "срок — от 0 до 365 дней"
        with self.s.tx() as c:
            c.execute("INSERT INTO k_rules(stage, title, days, created_at) VALUES (?,?,?,?)", (stage, title, d, _now()))
        return ""

    def rule_set(self, rid: int, active: bool | None = None, delete: bool = False) -> None:
        with self.s.tx() as c:
            if delete:
                c.execute("DELETE FROM k_rules WHERE id=?", (rid,))
            elif active is not None:
                c.execute("UPDATE k_rules SET active=? WHERE id=?", (1 if active else 0, rid))

    def links(self) -> list[sqlite3.Row]:
        try:
            return self.s.c().execute("SELECT * FROM k_links ORDER BY pos, id").fetchall()
        except sqlite3.Error:
            return []

    def link_add(self, title: str, url: str) -> str:
        title = re.sub(r"\s+", " ", title or "").strip()[:30]
        url = (url or "").strip()
        if not title:
            return "напишите, как подписать ссылку"
        if not re.match(r"^https://[^\s\"<>\\]{4,500}$", url):
            return "ссылка должна начинаться с https://"
        with self.s.tx() as c:
            pos = int(c.execute("SELECT COALESCE(MAX(pos),0)+1 FROM k_links").fetchone()[0])
            c.execute("INSERT INTO k_links(title, url, pos) VALUES (?,?,?)", (title, url, pos))
        return ""

    def link_delete(self, lid: int) -> None:
        with self.s.tx() as c:
            c.execute("DELETE FROM k_links WHERE id=?", (lid,))


# ==================================================================== Excel (xlsx без библиотек)
def _col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx(sheets: list[tuple[str, list[list[Any]]]]) -> bytes:
    """Простая книга Excel: первая строка — жирные заголовки, числа — числами, остальное — текстом."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        names = [re.sub(r"[\[\]:*?/\\]", " ", n)[:31] or f"Лист{i + 1}" for i, (n, _) in enumerate(sheets)]
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(len(sheets))) + "</Types>")
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(names)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                             for i in range(len(sheets)))
                   + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
                   '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
                   '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
                   '<cellXfs count="2"><xf fontId="0"/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>')
        for i, (_, rows) in enumerate(sheets):
            out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                   '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>']
            width = max((len(r) for r in rows), default=0)
            if width:
                out.append("<cols>" + "".join(f'<col min="{c + 1}" max="{c + 1}" width="{min(60, max(10, max(len(str(r[c])) if c < len(r) else 0 for r in rows[:200]) + 2))}" customWidth="1"/>'
                                              for c in range(width)) + "</cols>")
            out.append("<sheetData>")
            for ri, row in enumerate(rows, 1):
                cells = []
                for ci, v in enumerate(row, 1):
                    ref = f"{_col(ci)}{ri}"
                    st = ' s="1"' if ri == 1 else ""
                    if isinstance(v, bool) or v is None or v == "":
                        if v:
                            cells.append(f'<c r="{ref}" t="inlineStr"{st}><is><t>да</t></is></c>')
                        continue
                    if isinstance(v, (int, float)) and ri > 1:
                        cells.append(f'<c r="{ref}"{st}><v>{v}</v></c>')
                    else:
                        t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v))[:32000]
                        cells.append(f'<c r="{ref}" t="inlineStr"{st}><is><t xml:space="preserve">{escape(t)}</t></is></c>')
                out.append(f'<row r="{ri}">' + "".join(cells) + "</row>")
            out.append("</sheetData></worksheet>")
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", "".join(out))
    return buf.getvalue()
