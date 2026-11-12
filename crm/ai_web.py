"""«Помощник» — своя нейросеть в телефоне (приложение «Замер 3D») работает с CRM по личному ключу.

Телефон спрашивает список команд (GET /api/ai/tools) и вызывает их (POST /api/ai/call). Нейросеть считает
в телефоне; сервер только выполняет команды с правами того сотрудника, чей ключ. Опасные команды без
подтверждения хозяина на телефоне («confirmed») не выполняются. Знания о магазине лежат в базе CRM
(не в GitHub): телефон их забирает (GET /api/ai/knowledge) и может сохранять копию своей базы (POST).
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from typing import Any, Callable

from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, url_for

from store import STAGE_NAMES, STAGES, fmt_day, iso_now, rub, today

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_keys (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    name       TEXT NOT NULL DEFAULT '',
    token_hash TEXT NOT NULL UNIQUE,
    tail       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    used_at    TEXT NOT NULL DEFAULT '',
    active     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ai_knowledge (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    text       TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT 'CRM',
    pinned     INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ai_backup (
    user_id    INTEGER PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      TEXT NOT NULL,
    user_id INTEGER,
    tool    TEXT NOT NULL,
    args    TEXT NOT NULL DEFAULT '',
    ok      INTEGER NOT NULL DEFAULT 1,
    result  TEXT NOT NULL DEFAULT ''
)
"""

STAGE_BY_WORD = {**{k: k for k in STAGE_NAMES}, **{v.lower(): k for k, v in STAGE_NAMES.items()},
                 "расчёт": "quote", "расчет": "quote", "расчет отправлен": "quote", "оплачен": "paid", "отгружен": "shipped",
                 "отказался": "lost", "отказ клиента": "lost", "в работу": "work", "новый": "new"}


def tok_hash(t: str) -> str:
    return hashlib.sha256(("nashdekor-ai:" + t).encode()).hexdigest()


class AI:
    """Ключи, знания, журнал и сами команды помощника."""

    LIMIT_PER_HOUR = 400

    def __init__(self, store: Any) -> None:
        self.s = store
        c = self.s.c()
        c.executescript(SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(ai_knowledge)").fetchall()}
        if "kind" not in cols:          # 12.11.2026: навыки (как делать) с версиями
            c.execute("ALTER TABLE ai_knowledge ADD COLUMN kind TEXT NOT NULL DEFAULT 'знание'")
        if "version" not in cols:
            c.execute("ALTER TABLE ai_knowledge ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        c.commit()
        self._hits: dict[int, list[float]] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- ключи
    def new_key(self, user_id: int, name: str) -> str:
        t = "ndai_" + secrets.token_urlsafe(30)
        c = self.s.c()
        c.execute("INSERT INTO ai_keys(user_id, name, token_hash, tail, created_at) VALUES (?,?,?,?,?)",
                  (user_id, (name or "телефон").strip()[:40], tok_hash(t), t[-4:], iso_now()))
        c.commit()
        return t

    def keys(self, user_id: int | None = None) -> list[Any]:
        q = "SELECT k.*, u.name AS user_name FROM ai_keys k LEFT JOIN users u ON u.id=k.user_id WHERE k.active=1"
        args: tuple[Any, ...] = ()
        if user_id is not None:
            q += " AND k.user_id=?"
            args = (user_id,)
        return self.s.c().execute(q + " ORDER BY k.id DESC", args).fetchall()

    def revoke(self, kid: int, user_id: int | None = None) -> bool:
        c = self.s.c()
        q, a = "UPDATE ai_keys SET active=0 WHERE id=?", [kid]
        if user_id is not None:
            q += " AND user_id=?"
            a.append(user_id)
        n = c.execute(q, a).rowcount
        c.commit()
        return n > 0

    def user_by_token(self, t: str) -> Any:
        if not t or not t.startswith("ndai_") or len(t) > 100:
            return None
        row = self.s.c().execute("SELECT * FROM ai_keys WHERE token_hash=? AND active=1", (tok_hash(t),)).fetchone()
        if not row:
            return None
        u = self.s.user(int(row["user_id"]))
        if not u or not u["active"]:
            return None
        c = self.s.c()
        c.execute("UPDATE ai_keys SET used_at=? WHERE id=?", (iso_now(), row["id"]))
        c.commit()
        return u

    def allow(self, uid: int) -> bool:
        with self._lock:
            t = time.time()
            h = [x for x in self._hits.get(uid, []) if t - x < 3600]
            if len(h) >= self.LIMIT_PER_HOUR:
                self._hits[uid] = h
                return False
            h.append(t)
            self._hits[uid] = h
            return True

    # ---------------------------------------------------------------- знания (только в базе CRM)
    def knowledge(self) -> list[Any]:
        return self.s.c().execute("SELECT * FROM ai_knowledge ORDER BY kind='навык' DESC, pinned DESC, title").fetchall()

    def k_save(self, title: str, text: str, pinned: bool, who: str, kid: int | None = None, source: str = "CRM",
               kind: str | None = None) -> None:
        """Сохранить знание или навык. У навыка при изменении текста растёт версия — телефон покажет «что поняла»."""
        title, text = title.strip()[:120], text.strip()[:20000]
        if not title or not text:
            return
        c = self.s.c()
        row = (c.execute("SELECT * FROM ai_knowledge WHERE id=?", (kid,)).fetchone() if kid else
               c.execute("SELECT * FROM ai_knowledge WHERE lower(title)=lower(?)", (title,)).fetchone())
        if row:
            k = kind or row["kind"]
            ver = int(row["version"]) + (1 if row["text"] != text else 0)
            c.execute("UPDATE ai_knowledge SET title=?, text=?, pinned=?, source=?, kind=?, version=?, updated_at=?, updated_by=? WHERE id=?",
                      (title, text, int(pinned and k != "навык"), source if not kid else row["source"], k, ver, iso_now(), who, row["id"]))
        else:
            k = kind or "знание"
            c.execute("INSERT INTO ai_knowledge(title, text, source, pinned, kind, version, updated_at, updated_by) VALUES (?,?,?,?,?,1,?,?)",
                      (title, text, source, int(pinned and k != "навык"), k, iso_now(), who))
        c.commit()

    def k_delete(self, kid: int) -> None:
        c = self.s.c()
        c.execute("DELETE FROM ai_knowledge WHERE id=?", (kid,))
        c.commit()

    def k_import(self, raw: bytes, name: str, who: str) -> int:
        """Пакет знаний: .json [{title,text,pinned?}] или .md («# ОСНОВА» — постоянные разделы, «## Тема» — раздел)."""
        text = raw.decode("utf-8", errors="replace")
        n = 0
        if name.lower().endswith(".json"):
            try:
                items = json.loads(text)
            except ValueError:
                return 0
            for it in items if isinstance(items, list) else []:
                if isinstance(it, dict) and it.get("title") and it.get("text"):
                    self.k_save(str(it["title"]), str(it["text"]), bool(it.get("pinned")), who, source=str(it.get("source") or "пакет"),
                                kind="навык" if it.get("kind") == "навык" else "знание")
                    n += 1
            return n
        # «#НАВЫК Название» … — блоки навыков (как их присылает Claude)
        blocks = re.split(r"(?m)^\s*#\s*НАВЫК[:\s]*", text, flags=re.I)
        if len(blocks) > 1:
            for b in blocks[1:]:
                head, _, body = b.partition("\n")
                t = head.strip(" :—-«»\"")
                if t and body.strip():
                    self.k_save(t, body.strip(), False, who, source="пакет", kind="навык")
                    n += 1
            return n
        pinned, skills, title, body = False, False, None, []

        def flush() -> None:
            nonlocal n
            if title and "".join(body).strip():
                self.k_save(title, "\n".join(body).strip(), pinned, who, source="пакет", kind="навык" if skills else "знание")
                n += 1

        for line in text.splitlines():
            if line.startswith("# "):
                flush(); title, body = None, []
                pinned = "ОСНОВА" in line.upper()
                skills = "НАВЫК" in line.upper()
            elif line.startswith("## "):
                flush(); body = []
                title = line[3:].strip()
            elif title is not None:
                body.append(line)
        flush()
        return n

    def backup_save(self, uid: int, data: Any) -> int:
        items = data if isinstance(data, list) else []
        items = [i for i in items if isinstance(i, dict)][:5000]
        c = self.s.c()
        c.execute("INSERT OR REPLACE INTO ai_backup(user_id, data, updated_at) VALUES (?,?,?)",
                  (uid, json.dumps(items, ensure_ascii=False)[:5_000_000], iso_now()))
        c.commit()
        return len(items)

    def backup_get(self, uid: int) -> list[Any]:
        row = self.s.c().execute("SELECT data FROM ai_backup WHERE user_id=?", (uid,)).fetchone()
        try:
            return json.loads(row["data"]) if row else []
        except ValueError:
            return []

    # ---------------------------------------------------------------- журнал
    def log(self, uid: int, tool: str, args: dict[str, Any], ok: bool, result: str) -> None:
        c = self.s.c()
        c.execute("INSERT INTO ai_log(at, user_id, tool, args, ok, result) VALUES (?,?,?,?,?,?)",
                  (iso_now(), uid, tool, json.dumps(args, ensure_ascii=False)[:1000], int(ok), result[:400]))
        c.execute("DELETE FROM ai_log WHERE id < (SELECT MAX(id) - 3000 FROM ai_log)")
        c.commit()

    def recent(self, limit: int = 60) -> list[Any]:
        return self.s.c().execute("SELECT l.*, u.name AS user_name FROM ai_log l LEFT JOIN users u ON u.id=l.user_id"
                                  " ORDER BY l.id DESC LIMIT ?", (limit,)).fetchall()


# ==================================================================== команды

def P(name: str, desc: str, typ: str = "string", required: bool = True) -> dict[str, Any]:
    return {"name": name, "desc": desc, "type": typ, "required": required}


TOOLS: list[dict[str, Any]] = [
    {"name": "crm_today", "desc": "Сводка CRM на сегодня: новые заявки, задачи на сегодня и просроченные, ждут оплаты/отгрузки, непрочитанные чаты.",
     "params": []},
    {"name": "crm_find", "desc": "Найти клиентов и заявки по имени, телефону, e-mail, тексту заявки или номеру заявки.",
     "params": [P("q", "что искать")]},
    {"name": "crm_deal", "desc": "Заявка целиком: клиент и контакты, этап, позиции и сумма, оплаты, задачи, последние события.",
     "params": [P("id", "номер заявки", "integer")]},
    {"name": "crm_new_deal", "desc": "Создать заявку (клиент найдётся по телефону/e-mail или будет создан).", "danger": True,
     "params": [P("name", "имя клиента"), P("text", "что хочет клиент"), P("phone", "телефон", required=False),
                P("email", "e-mail", required=False), P("source", "откуда: звонок, авито, почта, сайт, telegram, max, другое", required=False)]},
    {"name": "crm_stage", "desc": "Сменить этап заявки: новая, в работе, расчёт отправлен, оплачено, отгружено, отказ.", "danger": True,
     "params": [P("id", "номер заявки", "integer"), P("stage", "новый этап")]},
    {"name": "crm_note", "desc": "Записать заметку в историю заявки.",
     "params": [P("id", "номер заявки", "integer"), P("text", "текст заметки")]},
    {"name": "crm_task", "desc": "Поставить задачу (к заявке или общую).",
     "params": [P("text", "что сделать"), P("due", "срок ГГГГ-ММ-ДД", required=False), P("id", "номер заявки", "integer", False)]},
    {"name": "crm_task_done", "desc": "Отметить задачу выполненной.", "params": [P("task_id", "номер задачи", "integer")]},
    {"name": "crm_stock", "desc": "Склад: остатки, отложено под заявки и цены. Без q — что заканчивается.",
     "params": [P("q", "название или артикул товара", required=False)]},
    {"name": "crm_add_item", "desc": "Добавить товар в расчёт заявки (артикул и количество штук).", "danger": True,
     "params": [P("id", "номер заявки", "integer"), P("article", "артикул"), P("qty", "штук", "integer")]},
    {"name": "crm_send_calc", "desc": "Отправить клиенту письмо-расчёт по заявке.", "danger": True,
     "params": [P("id", "номер заявки", "integer"), P("email", "e-mail, если у клиента не указан", required=False)]},
    {"name": "crm_chats", "desc": "Последние переписки из чата на сайте (непрочитанные сверху).", "params": []},
    {"name": "crm_mail", "desc": "Последние письма в ящиках info@ и zakaz@ (поиск по отправителю или теме).", "admin": True,
     "params": [P("q", "что искать", required=False)]},
    {"name": "crm_letter", "desc": "Прочитать письмо из почты по его номеру из crm_mail.", "admin": True,
     "params": [P("letter_id", "номер письма")]},
    {"name": "crm_money", "desc": "Деньги за месяц: поступления, ждут оплаты по ссылкам, итог за год.", "admin": True,
     "params": [P("month", "ГГГГ-ММ, по умолчанию текущий", required=False)]},
    {"name": "crm_server", "desc": "Кнопки страницы «Сервер»: update (обновить CRM), sync (обновить сайт), backup (копия баз), restart-crm,"
                                   " restart-mail, reload-web, unban (снять блокировки), reboot (перезагрузить сервер).",
     "danger": True, "admin": True, "params": [P("action", "какая кнопка")]},
    {"name": "crm_server_status", "desc": "Чем закончилась последняя команда сервера.", "admin": True, "params": []},
]
TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def rub_kop(kop: Any) -> str:
    return rub(int(kop or 0) / 100)


def register(app: Flask, store: Any, ai: AI, h: dict[str, Any]) -> None:
    admin_required: Callable[..., Any] = h["admin_required"]
    login_required: Callable[..., Any] = h["login_required"]
    who: Callable[[], str] = h["who"]
    send_calc_to: Callable[[int, str], tuple[bool, str]] = h["send_calc_to"]
    pochta = h["pochta"]
    server = h["server"]          # {"keys": set, "request": path, "last": fn}

    def bearer_user() -> Any:
        a = request.headers.get("Authorization", "")
        t = a[7:].strip() if a.lower().startswith("bearer ") else ""
        u = ai.user_by_token(t)
        if u is None:
            # та же строка, что у неверного пароля, — fail2ban считает и подбор ключей
            app.logger.warning("crm login failed login=ai-key ip=%s", request.remote_addr or "?")
        return u

    def api_auth() -> Any:
        u = bearer_user()
        if u is None:
            abort(Response(json.dumps({"error": "ключ не подходит"}, ensure_ascii=False), 401, mimetype="application/json"))
        if not ai.allow(int(u["id"])):
            abort(Response(json.dumps({"error": "слишком много команд за час — подождите"}, ensure_ascii=False), 429, mimetype="application/json"))
        g.user = u
        return u

    def visible_tools(u: Any) -> list[dict[str, Any]]:
        return [{k: v for k, v in t.items() if k != "admin"} for t in TOOLS if not t.get("admin") or u["role"] == "admin"]

    @app.route("/api/ai/tools")
    def ai_tools() -> Any:
        u = api_auth()
        resp = jsonify({"tools": visible_tools(u), "user": u["name"], "role": u["role"]})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/ai/knowledge", methods=["GET", "POST"])
    def ai_knowledge() -> Any:
        u = api_auth()
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            n = ai.backup_save(int(u["id"]), data.get("items"))
            return jsonify({"ok": True, "saved": n})
        items = [{"title": r["title"], "text": r["text"], "pinned": bool(r["pinned"]), "source": r["source"] or "CRM",
                  "kind": r["kind"], "version": int(r["version"])} for r in ai.knowledge()]
        resp = jsonify({"items": items, "backup": ai.backup_get(int(u["id"])) if request.args.get("backup") == "1" else []})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.post("/api/ai/call")
    def ai_call() -> Any:
        u = api_auth()
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", ""))
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        t = TOOL_BY_NAME.get(name)
        if not t or (t.get("admin") and u["role"] != "admin"):
            return jsonify({"ok": False, "text": f"Нет такой команды CRM: {name}"})
        if t.get("danger") and data.get("confirmed") is not True:
            return jsonify({"ok": False, "text": "Это действие выполняется только после подтверждения хозяина на телефоне."})
        try:
            text = run_tool(name, args, u)
            ok = True
        except ToolError as e:
            text, ok = str(e), False
        except Exception as e:  # noqa: BLE001 — нейросеть должна получить понятный ответ, а не 500
            app.logger.exception("ai: %s", name)
            text, ok = f"Ошибка CRM при выполнении {name}: {type(e).__name__}", False
        ai.log(int(u["id"]), name, args, ok, text)
        return jsonify({"ok": ok, "text": text})

    # ------------------------------------------------------------ исполнение
    def num(a: dict[str, Any], k: str) -> int:
        v = a.get(k)
        m = re.search(r"\d+", str(v if v is not None else ""))
        if not m:
            raise ToolError(f"Нужен номер ({k}).")
        return int(m.group(0))

    def deal_line(d: Any) -> str:
        total = store.total(int(d["gross"] or 0), int(d["discount"] or 0)) if "gross" in d.keys() else 0
        task = f" · задача: {d['task_title']} до {fmt_day(d['task_due'])}" if "task_title" in d.keys() and d["task_title"] else ""
        return (f"№{d['id']} {d['client_name']} — {STAGE_NAMES.get(d['stage'], d['stage'])}"
                f"{' · ' + rub(total) if total else ''} · {(d['want'] or '').strip()[:80]}{task}")

    def run_tool(name: str, a: dict[str, Any], u: Any) -> str:
        t = today()
        if name == "crm_today":
            dg = store.digest(t)
            new = store.deals(stage="new", limit=15)
            due = store.tasks(until=t)
            paid = store.deals(stage="paid", limit=15)
            out = [f"Сегодня {fmt_day(t)}. Новых заявок: {dg['new']}, задач на сегодня: {dg['today']}, просрочено: {dg['overdue']},"
                   f" оплачено и ждёт отгрузки: {dg['paid']}, непрочитанных чатов: {store.chat_unread()}."]
            if new:
                out.append("Новые заявки:\n" + "\n".join("• " + deal_line(d) for d in new))
            if due:
                out.append("Задачи (сегодня и просроченные):\n" + "\n".join(
                    f"• [{x['id']}] {x['title']} — до {fmt_day(x['due'])}{' · №' + str(x['deal_id']) + ' ' + (x['client_name'] or '') if x['deal_id'] else ''}"
                    for x in due[:25]))
            if paid:
                out.append("Оплачено, отгрузить:\n" + "\n".join("• " + deal_line(d) for d in paid))
            return "\n\n".join(out)

        if name == "crm_find":
            q = str(a.get("q", "")).strip()[:100]
            if not q:
                raise ToolError("Пустой запрос.")
            rows = []
            if re.fullmatch(r"№?\s*\d{1,7}", q):
                d = store.deal(int(re.sub(r"\D", "", q)))
                if d:
                    rows.append(f"Заявка №{d['id']} {d['client_name']} — {STAGE_NAMES.get(d['stage'], d['stage'])}")
            digits = re.sub(r"\D", "", q)
            deals = store.deals(q=digits[-10:] if len(digits) >= 6 else q, limit=12)
            rows += ["• " + deal_line(d) for d in deals]
            cl = store.clients(q, limit=8) if not deals else []
            rows += [f"• клиент {c['name']} {c['phone'] or ''} {c['email'] or ''}".rstrip() for c in cl]
            return "\n".join(rows) if rows else "Ничего не нашлось."

        if name == "crm_deal":
            did = num(a, "id")
            d = store.deal(did)
            if not d:
                raise ToolError(f"Заявки №{did} нет.")
            gross, total = store.deal_total(did)
            lines = store.lines(did)
            pays = store.payments(did)
            tasks = store.tasks(deal_id=did)
            ev = store.events(deal_id=did, limit=8)
            contacts = ", ".join(x for x in (d["phone"], d["email"], d["messenger"]) if x)
            out = [f"Заявка №{did} — {STAGE_NAMES.get(d['stage'], d['stage'])}, создана {fmt_day(d['created_at'][:10])}",
                   f"Клиент: {d['client_name']}{' (' + d['company'] + ')' if d['company'] else ''}; контакты: {contacts or 'нет'}",
                   f"Хочет: {(d['want'] or '').strip()[:500]}"]
            if lines:
                out.append("Позиции:\n" + "\n".join(f"• {ln['article']} × {ln['qty']} по {rub(ln['price'])}" for ln in lines))
                out.append(f"Сумма: {rub(total)}" + (f" (скидка {d['discount']}%)" if d["discount"] else ""))
            if pays:
                out.append("Оплаты:\n" + "\n".join(f"• {rub_kop(p['amount'])} — {'оплачено ' + fmt_day(p['paid_at'][:10]) if p['paid_at'] else p['status'] or 'ждёт'}" for p in pays))
            if tasks:
                out.append("Открытые задачи:\n" + "\n".join(f"• [{x['id']}] {x['title']} до {fmt_day(x['due'])}" for x in tasks))
            if ev:
                out.append("Последние события:\n" + "\n".join(f"• {fmt_day(e['at'][:10])} {e['text']}" for e in ev))
            return "\n".join(out)

        if name == "crm_new_deal":
            nm = str(a.get("name", "")).strip()[:120]
            text = str(a.get("text", "")).strip()[:2000]
            if not nm or not text:
                raise ToolError("Нужны имя клиента и что он хочет.")
            src_word = str(a.get("source", "")).strip().lower()
            src = {"звонок": "phone", "телефон": "phone", "авито": "avito", "почта": "mail", "сайт": "site",
                   "telegram": "tg", "телеграм": "tg", "max": "max", "макс": "max"}.get(src_word, "phone" if a.get("phone") else "other")
            did = store.create_deal(who(), int(u["id"]), name=nm, phone=str(a.get("phone", "")), email=str(a.get("email", "")).strip()[:120],
                                    want=text, source=src)
            return f"Создана заявка №{did} ({nm}). Задача «Связаться с клиентом» поставлена."

        if name == "crm_stage":
            did = num(a, "id")
            st = STAGE_BY_WORD.get(str(a.get("stage", "")).strip().lower())
            if not st:
                raise ToolError("Этапы: " + ", ".join(n.lower() for _, n in STAGES))
            if not store.deal(did):
                raise ToolError(f"Заявки №{did} нет.")
            old = store.set_stage(did, st, who())
            return f"№{did}: этап «{STAGE_NAMES[st]}»." if old else f"№{did} уже на этапе «{STAGE_NAMES[st]}»."

        if name == "crm_note":
            did = num(a, "id")
            d = store.deal(did)
            if not d:
                raise ToolError(f"Заявки №{did} нет.")
            with store.tx() as c:
                store.log(c, "Заметка: " + str(a.get("text", "")).strip()[:450], who(), deal_id=did, client_id=d["client_id"])
            return f"Заметка добавлена в №{did}."

        if name == "crm_task":
            text = str(a.get("text", "")).strip()
            due = str(a.get("due", "")).strip()[:10]
            did = None
            if a.get("id") not in (None, "", 0):
                did = num(a, "id")
                if not store.deal(did):
                    raise ToolError(f"Заявки №{did} нет.")
            if not text:
                raise ToolError("Нужен текст задачи.")
            store.add_task(did, text, due, who(), int(u["id"]))
            return f"Задача поставлена{' к №' + str(did) if did else ''}: {text} (срок {fmt_day(due) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', due) else 'сегодня'})."

        if name == "crm_task_done":
            tid = num(a, "task_id")
            r = store.done_task(tid, True, who())
            return f"Задача [{tid}] выполнена." if r is not None else f"Задачи [{tid}] нет."

        if name == "crm_stock":
            q = str(a.get("q", "")).strip().lower()
            rows = store.stock_rows()
            if q:
                rows = [r for r in rows if q in f"{r['article']} {r['name']} {r['size']}".lower()][:25]
            else:
                rows = sorted([r for r in rows if r["in_catalog"]], key=lambda r: r["qty"] - r["reserved"])[:15]
            if not rows:
                return "Ничего не нашлось на складе."
            return "\n".join(f"• {r['article']} {r['name']} {r['size']}: на складе {r['qty']}, отложено {r['reserved']},"
                             f" свободно {max(r['qty'] - r['reserved'], 0)}, цена {rub(r['price'])}" for r in rows)

        if name == "crm_add_item":
            did = num(a, "id")
            qty = num(a, "qty")
            if not store.deal(did):
                raise ToolError(f"Заявки №{did} нет.")
            art = str(a.get("article", "")).strip()
            if not store.catalog.get(art) and not any(r["article"] == art.upper() for r in store.stock_rows()):
                raise ToolError(f"Артикула {art} нет в каталоге — уточни через crm_stock.")
            err = store.add_line(did, art, qty, who())
            if err:
                raise ToolError(err)
            _, total = store.deal_total(did)
            return f"Добавлено в №{did}. Сумма заявки: {rub(total)}."

        if name == "crm_send_calc":
            did = num(a, "id")
            ok, why = send_calc_to(did, str(a.get("email", "")).strip())
            return f"Расчёт №{did} отправлен на {why}." if ok else f"Не отправлено: {why}."

        if name == "crm_chats":
            rows = store.chats(limit=10)
            if not rows:
                return "Переписок в чате нет."
            return "\n".join(f"• {'🔵 ' if r['unread'] else ''}{r['name'] or 'посетитель'}{' ' + r['contact'] if r['contact'] else ''}:"
                             f" {(r['last_text'] or '')[:120]}{' · №' + str(r['deal_id']) if r['deal_id'] else ''}" for r in rows)

        if name == "crm_mail":
            rows = pochta.letters("", str(a.get("q", ""))[:80], limit=12)
            if not rows:
                return "Писем не нашлось (или почта ещё не выгружена)."
            return "\n".join(f"• [{e.get('id')}] {e.get('box', '')}@ {fmt_ts(e.get('ts'))} от {e.get('name') or e.get('from', '')}: {e.get('subject', '')[:100]}"
                             for e in rows)

        if name == "crm_letter":
            m = pochta.get(str(a.get("letter_id", "")).strip())
            if not m:
                raise ToolError("Письма нет.")
            body = (m.get("text") or m.get("body") or "").strip()
            atts = ", ".join(x.get("name", "") for x in m.get("attachments", []) if isinstance(x, dict))
            return (f"От: {m.get('name') or ''} <{m.get('from', '')}>\nТема: {m.get('subject', '')}\n"
                    f"{'Вложения: ' + atts + chr(10) if atts else ''}\n{body[:2500]}")

        if name == "crm_money":
            month = str(a.get("month", "")).strip()[:7] or t[:7]
            if not re.fullmatch(r"\d{4}-\d{2}", month):
                raise ToolError("Месяц в виде ГГГГ-ММ.")
            m = store.money(month)
            out = [f"{month}: поступило {rub_kop(m['got'])} (по ссылкам {rub_kop(m['links'])}), за {month[:4]} год {rub_kop(m['year'])}."]
            if m["waiting"]:
                out.append("Ждут оплаты по ссылкам:\n" + "\n".join(f"• №{p['deal_id']} {p['client_name']}: {rub_kop(p['amount'])}" for p in m["waiting"][:10]))
            if m["closing"]:
                out.append(f"Нужны чеки «Полный расчёт»: {len(m['closing'])}.")
            return "\n".join(out)

        if name == "crm_server":
            act = str(a.get("action", "")).strip().lower()
            if act not in server["keys"]:
                raise ToolError("Кнопки: " + ", ".join(sorted(server["keys"])))
            import os
            if os.path.exists(server["request"]) or server["last"]()[1]:
                raise ToolError("Предыдущая команда сервера ещё выполняется — подождите минуту.")
            with open(server["request"], "w", encoding="utf-8") as f:
                f.write(f"{act} {u['login']}\n")
            app.logger.info("сервер: действие %s запросил %s (помощник)", act, u["login"])
            return f"Принято: «{act}». Сервер выполнит в течение минуты; результат — crm_server_status через 1–3 минуты."

        if name == "crm_server_status":
            text, running = server["last"]()
            if not text:
                return "Команд сервера ещё не было."
            return ("Выполняется…\n" if running else "") + text.strip()[-1500:]

        raise ToolError(f"Нет такой команды: {name}")

    def fmt_ts(ts: Any) -> str:
        try:
            from datetime import datetime
            return datetime.fromtimestamp(int(ts)).strftime("%d.%m %H:%M")
        except (TypeError, ValueError, OSError):
            return ""

    # ------------------------------------------------------------ страница в CRM
    @app.route("/ai")
    @login_required
    def ai_view() -> Any:
        mine = g.user["role"] != "admin"
        return render_template("ai.html", keys=ai.keys(int(g.user["id"]) if mine else None), know=ai.knowledge(),
                               log=ai.recent() if not mine else [], new_key=request.args.get("k", ""), tools=visible_tools(g.user))

    @app.post("/ai/key")
    @login_required
    def ai_key() -> Any:
        act = request.form.get("action", "")
        if act == "new":
            t = ai.new_key(int(g.user["id"]), request.form.get("name", ""))
            with store.tx() as c:
                store.log(c, f"Помощник: выдан ключ «{request.form.get('name', '')[:40] or 'телефон'}»", who())
            # ключ показываем один раз — без перехода по ссылке, чтобы не остался в журнале nginx
            return render_template("ai_key.html", token=t)
        if act == "revoke":
            ok = ai.revoke(int(request.form.get("id", "0") or 0), None if g.user["role"] == "admin" else int(g.user["id"]))
            flash("Ключ отключён — телефон с ним больше не работает." if ok else "Ключа нет.", "ok" if ok else "err")
        return redirect(url_for("ai_view"))

    @app.post("/ai/knowledge")
    @admin_required
    def ai_knowledge_edit() -> Any:
        act = request.form.get("action", "")
        if act == "save":
            ai.k_save(request.form.get("title", ""), request.form.get("text", ""), request.form.get("pinned") == "1", who(),
                      int(request.form.get("id") or 0) or None,
                      kind=("навык" if request.form.get("kind") == "навык" else "знание") if request.form.get("kind") else None)
            flash("Сохранено. Телефон заберёт при следующем обновлении знаний.", "ok")
        elif act == "delete":
            ai.k_delete(int(request.form.get("id", "0") or 0))
            flash("Удалено.", "ok")
        elif act == "import":
            f = request.files.get("file")
            if not f or not f.filename:
                flash("Выберите файл .md или .json.", "err")
            else:
                n = ai.k_import(f.read(2_000_000), f.filename, who())
                flash(f"Загружено разделов: {n}." if n else "В файле не нашлось разделов («## Тема» или JSON-список).", "ok" if n else "err")
        return redirect(url_for("ai_view") + "#know")


class ToolError(Exception):
    pass
