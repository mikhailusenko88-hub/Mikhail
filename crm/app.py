"""CRM магазина «Наш декор» — веб-приложение (Flask).

Запуск на сервере — служба prostranstvo-crm (gunicorn, 127.0.0.1:8081, за nginx на crm.ДОМЕН).
Настройки — переменные окружения из /etc/prostranstvo/crm.env:
  CRM_DB, BOT_DB, CATALOG_FILE, CRM_SECRET_FILE, SITE_ORIGINS, SITE_LEADS (1/0),
  NOTIFY_EMAIL, COOKIE_SECURE (1/0).
Пароли хранятся только хешами; в журнал пишутся лишь неудачные входы (логин и IP) — для fail2ban.
"""

from __future__ import annotations

import functools
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from store import (KIND_NAMES, KIND_TITLES, KINDS, OPEN_STAGES, ROLE_NAMES, ROLES, SOURCE_NAMES, SOURCES,
                   STAGE_NAMES, STAGES, Catalog, Store, fmt_day, fmt_dt, now, rub, today, split_contact)
from push import WebPush
from tochka import (KEY_URL, PAY_TYPES, STATUS_NAMES, TAX_SYSTEMS, Tochka, TochkaError, http_request, jwt_claims,
                    parse_jwk, receipt_items, verify_rs256)
from visits import Visits, is_bot, parse_body

log = logging.getLogger("crm")

LOGIN_WINDOW = 15 * 60
LOGIN_MAX_FAILS = 10
LEAD_WINDOW = 10 * 60
LEAD_MAX = 5
CHAT_MAX = 30                     # сообщений в чат с одного адреса за 10 минут
SID_RE = re.compile(r"^[A-Za-z0-9_-]{24,64}$")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+7|\b8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}\b")
HIT_WINDOW = 10 * 60
# Кнопки страницы «Сервер»: (код, надпись, пояснение). Выполняет их root по cron (prostranstvo-crm server-page),
# и только из этого списка — произвольных команд из CRM нет.
SERVER_ACTIONS: list[tuple[str, str, str]] = [
    ("update", "Обновить CRM", "свежая версия из GitHub, 1–3 минуты; пароли не меняются"),
    ("sync", "Обновить сайт", "сразу забрать сайт из GitHub (сам обновляется раз в минуту)"),
    ("backup", "Копия баз", "копия CRM и бота сейчас (ночью делается сама)"),
    ("restart-crm", "Перезапустить CRM", "если CRM тормозит или выдаёт ошибку"),
    ("restart-mail", "Перезапустить почту", "если письма не уходят или не приходят"),
    ("reload-web", "Перезапустить веб-сервер", "если сайт не открывается"),
    ("unban", "Снять блокировки", "если сервер заблокировал вас после неверных паролей (fail2ban)"),
    ("leads-on", "Включить заявки с сайта", "форма на сайте снова принимает заявки"),
    ("leads-off", "Выключить заявки с сайта", "форма перестанет принимать заявки"),
    ("reboot", "Перезагрузить сервер", "сайт, почта и CRM недоступны 1–2 минуты"),
]
SERVER_ACTION_KEYS = {k for k, _, _ in SERVER_ACTIONS}
HIT_MAX = 150


def _secret(path: str) -> str:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            s = f.read().strip()
            if len(s) >= 32:
                return s
    return os.environ.get("CRM_SECRET", "") or secrets.token_hex(32)


def create_app(cfg: dict[str, Any] | None = None) -> Flask:
    cfg = dict(cfg or {})
    env = os.environ.get
    conf = {
        "CRM_DB": cfg.get("CRM_DB") or env("CRM_DB", "/var/lib/prostranstvo/crm.db"),
        "BOT_DB": cfg.get("BOT_DB", env("BOT_DB", "/var/lib/prostranstvo/bot.db")),
        "CATALOG_FILE": cfg.get("CATALOG_FILE") or env("CATALOG_FILE", "/var/www/prostranstvo/index.html"),
        "SITE_ORIGINS": [o.strip().rstrip("/") for o in (cfg.get("SITE_ORIGINS") or env("SITE_ORIGINS", "")).split(",") if o.strip()],
        "SITE_LEADS": str(cfg.get("SITE_LEADS", env("SITE_LEADS", "0"))) == "1",
        "NOTIFY_EMAIL": cfg.get("NOTIFY_EMAIL", env("NOTIFY_EMAIL", "")),
        "COOKIE_SECURE": str(cfg.get("COOKIE_SECURE", env("COOKIE_SECURE", "1"))) == "1",
        "SHOP_DOMAIN": cfg.get("SHOP_DOMAIN", env("SHOP_DOMAIN", "")),
    }
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=cfg.get("SECRET_KEY") or _secret(env("CRM_SECRET_FILE", "")),
        SESSION_COOKIE_NAME="crm",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=conf["COOKIE_SECURE"],
        PERMANENT_SESSION_LIFETIME=30 * 24 * 3600,
        MAX_CONTENT_LENGTH=256 * 1024,
        TESTING=bool(cfg.get("TESTING")),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]
    store = Store(conf["CRM_DB"], conf["BOT_DB"], Catalog(conf["CATALOG_FILE"]))
    app.extensions["store"] = store
    app.extensions["crm_conf"] = conf
    visits = Visits(store, conf["SHOP_DOMAIN"])
    wp = WebPush(store, f"mailto:zakaz@{conf['SHOP_DOMAIN'] or 'nashdekor.ru'}")
    wp.sync = bool(cfg.get("TESTING")) or bool(cfg.get("PUSH_SYNC"))
    app.extensions["push"] = wp
    store.on_notify = lambda title, text, url: wp.notify(title, text, url, tag=url)
    app.extensions["tochka_http"] = cfg.get("TOCHKA_HTTP")      # в тестах — подставной банк; на сервере — None (urllib)
    app.extensions["visits"] = visits
    hits_by_ip: dict[str, deque[float]] = defaultdict(deque)
    fails: dict[str, deque[float]] = defaultdict(deque)
    leads_by_ip: dict[str, deque[float]] = defaultdict(deque)
    chat_by_ip: dict[str, deque[float]] = defaultdict(deque)

    def ip() -> str:
        return request.remote_addr or "?"

    def own_ips() -> list[str]:
        """Свои IP-адреса и сети (дом, офис, VPN) из настроек — заходы с них счётчик не считает."""
        return [t for t in store.setting("hit_ignore_ips", "").replace(",", " ").split() if t]

    def ip_is_own(addr: str) -> bool:
        toks = own_ips()
        if not toks:
            return False
        try:
            a = ipaddress.ip_address(addr)
        except ValueError:
            return False
        for tok in toks:
            try:
                if a in ipaddress.ip_network(tok, strict=False):
                    return True
            except ValueError:
                continue
        return False

    def _recent(q: deque[float], window: int) -> deque[float]:
        t = time.monotonic()
        while q and t - q[0] > window:
            q.popleft()
        return q

    # ------------------------------------------------------------ шаблоны
    @app.context_processor
    def ctx() -> dict[str, Any]:
        return {"STAGES": STAGES, "STAGE_NAMES": STAGE_NAMES, "SOURCES": SOURCES, "SOURCE_NAMES": SOURCE_NAMES,
                "KINDS": KINDS, "KIND_NAMES": KIND_NAMES, "ROLES": ROLES, "ROLE_NAMES": ROLE_NAMES,
                "KIND_TITLES": KIND_TITLES, "rub": rub, "fmt_dt": fmt_dt, "fmt_day": fmt_day, "today": today(),
                "me": getattr(g, "user", None), "csrf": session.get("csrf", ""), "total": Store.total,
                "nav_new": getattr(g, "nav_new", 0), "nav_chat": getattr(g, "nav_chat", 0), "SHOP_DOMAIN": conf["SHOP_DOMAIN"] or "nashdekor.ru",
                "PUSH_KEY": wp.public_key() if getattr(g, "user", None) and wp.enabled else "",
                "rubk": rubk, "PAY_STATUS": STATUS_NAMES, "PAY_TYPES": PAY_TYPES}

    @app.template_filter("ts_iso")
    def ts_iso(ts: Any) -> str:
        try:
            return datetime.fromtimestamp(int(ts), now().tzinfo).isoformat(timespec="seconds")
        except (TypeError, ValueError, OverflowError, OSError):
            return ""

    @app.after_request
    def headers(resp: Response) -> Response:
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if not request.path.startswith("/api/"):
            resp.headers.setdefault("Content-Security-Policy",
                                    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self';"
                                    " form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    # ------------------------------------------------------------ вход
    @app.before_request
    def load_user() -> Any:
        g.user = None
        api = request.path.startswith("/api/")
        if "csrf" not in session and not api:  # посетителям сайта (заявка, счётчик) cookie не ставим
            session["csrf"] = secrets.token_urlsafe(24)
        uid = session.get("uid")
        if uid:
            u = store.user(int(uid))
            if u and u["active"] and hmac.compare_digest(session.get("pwv", ""), u["pw_hash"][-16:]):
                g.user = u
            else:
                session.pop("uid", None)
        if request.method == "POST" and not request.path.startswith("/api/"):
            tok = request.form.get("csrf", "")
            if not tok or not hmac.compare_digest(tok, session.get("csrf", "")):
                abort(400, "Страница устарела — обновите её и повторите.")
        if g.user is not None and not api:
            store.import_bot_leads()
            g.nav_new = len(store.deals(stage="new", limit=99))
            g.nav_chat = store.chat_unread()
        return None

    def login_required(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrap(*a: Any, **kw: Any) -> Any:
            if g.user is None:
                return redirect(url_for("login", next=request.full_path if request.method == "GET" else ""))
            return fn(*a, **kw)
        return wrap

    def admin_required(fn: Any) -> Any:
        @functools.wraps(fn)
        @login_required
        def wrap(*a: Any, **kw: Any) -> Any:
            if g.user["role"] != "admin":
                abort(403)
            return fn(*a, **kw)
        return wrap

    def who() -> str:
        return g.user["name"] if g.user else ""

    def safe_next(n: str | None) -> str:
        n = n or ""
        if not n.startswith("/") or n.startswith("//") or "\\" in n:
            return url_for("today_view")
        return n.rstrip("?") or url_for("today_view")

    @app.route("/login", methods=["GET", "POST"])
    def login() -> Any:
        if g.user:
            return redirect(url_for("today_view"))
        err = ""
        if request.method == "POST":
            q = _recent(fails[ip()], LOGIN_WINDOW)
            login_s = (request.form.get("login") or "").strip().lower()[:40]
            if len(q) >= LOGIN_MAX_FAILS and not ip_is_own(ip()):   # свои адреса (VPN семьи) не блокируем
                err = "Слишком много попыток. Подождите 15 минут."
                log.warning("crm login blocked login=%s ip=%s", login_s, ip())
            else:
                u = store.user_by_login(login_s)
                pw = request.form.get("password") or ""
                if u and u["active"] and check_password_hash(u["pw_hash"], pw):
                    session.clear()
                    session["uid"] = int(u["id"])
                    session["pwv"] = u["pw_hash"][-16:]
                    session["csrf"] = secrets.token_urlsafe(24)
                    session.permanent = True
                    store.touch_login(int(u["id"]))
                    fails.pop(ip(), None)
                    return redirect(safe_next(request.form.get("next")))
                q.append(time.monotonic())
                log.warning("crm login failed login=%s ip=%s", login_s, ip())
                err = "Неверный логин или пароль."
        return render_template("login.html", err=err, next=request.values.get("next", "")), (401 if err else 200)

    @app.post("/logout")
    def logout() -> Any:
        session.clear()
        return redirect(url_for("login"))

    # ------------------------------------------------------------ приложение на экране «Домой» и пуши
    @app.route("/manifest.webmanifest")
    def manifest() -> Any:
        m = {"name": "Наш декор — CRM", "short_name": "Наш декор", "lang": "ru", "start_url": "/", "scope": "/",
             "display": "standalone", "background_color": "#f3f2ee", "theme_color": "#1d5e57",
             "icons": [{"src": url_for("static", filename="icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                       {"src": url_for("static", filename="icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}
        return Response(json.dumps(m, ensure_ascii=False), mimetype="application/manifest+json")

    @app.route("/sw.js")
    def service_worker() -> Any:
        return Response(SW_JS, mimetype="application/javascript")

    @app.post("/push/subscribe")
    @login_required
    def push_subscribe() -> Any:
        if not wp.enabled:
            return jsonify(ok=False, error="на сервере нет python3-cryptography — обновите CRM"), 200
        try:
            sub = json.loads(request.form.get("sub") or "{}")
        except ValueError:
            sub = {}
        err = wp.subscribe(int(g.user["id"]), sub if isinstance(sub, dict) else {}, request.headers.get("User-Agent", ""))
        if err:
            return jsonify(ok=False, error=err), 200
        c = store.c(); store.log(c, "Включены уведомления на устройстве", who()); c.commit()
        return jsonify(ok=True)

    @app.post("/push/unsubscribe")
    @login_required
    def push_unsubscribe() -> Any:
        store.push_sub_delete(endpoint=request.form.get("endpoint", ""), user_id=int(g.user["id"]))
        return jsonify(ok=True)

    @app.post("/push/test")
    @login_required
    def push_test() -> Any:
        subs = store.push_subs(user_ids=[int(g.user["id"])])
        ep = request.form.get("endpoint", "")
        if ep:
            subs = [s for s in subs if s["endpoint"] == ep]
        if not subs:
            return jsonify(ok=False, error="на этом устройстве уведомления ещё не включены")
        ok, bad = wp._send_many(subs, {"title": "Проверка уведомлений", "body": f"{g.user['name']}, уведомления CRM работают на этом телефоне.",
                                       "url": "/settings#push", "tag": "test"})
        return jsonify(ok=ok > 0, sent=ok, failed=bad, error="" if ok else "служба уведомлений не приняла пуш — выключите и включите снова")

    @app.post("/settings/push-delete")
    @admin_required
    def settings_push_delete() -> Any:
        store.push_sub_delete(sid=request.form.get("id", type=int))
        flash("Устройство отключено от уведомлений.", "ok")
        return redirect(url_for("settings_view") + "#push")

    def mail_in_push(items: list[dict[str, Any]]) -> list[str]:
        """Новые письма на ящики магазина (присылает cron mail-watch): письмо от клиента — в его сделку и пуш, иначе — просто пуш."""
        out = []
        for it in items[:30]:
            frm, name, subj, box = str(it.get("from") or ""), str(it.get("name") or ""), str(it.get("subject") or "(без темы)"), str(it.get("box") or "zakaz")
            did, cname = store.mail_in(frm, subj)
            if did:
                title, url = f"Письмо от клиента: {cname} · №{did}", f"/deals/{did}"
            else:
                title, url = f"Новое письмо на {box}@", "/"
            body = subj[:150] + (f" — {name or frm}" if not did else "")
            wp.notify(title, body, url, tag=f"mail-{did or box}")
            out.append(f"{box}: {frm} → " + (f"сделка №{did}" if did else "без сделки"))
        return out
    app.extensions["mail_in"] = mail_in_push

    def morning_digest(day: str | None = None) -> str:
        s = store.digest(day or today())
        if not (s["new"] or s["today"] or s["overdue"] or s["paid"]):
            return ""
        parts = []
        if s["overdue"]: parts.append(f"просрочено задач: {s['overdue']}")
        if s["today"]: parts.append(f"задач на сегодня: {s['today']}")
        if s["new"]: parts.append(f"новых заявок: {s['new']}")
        if s["paid"]: parts.append(f"оплачено, ждут отгрузки: {s['paid']}")
        text = "; ".join(parts).capitalize() + "."
        wp.notify("Наш декор — на сегодня", text, "/board?hot=1" if s["overdue"] else "/", tag="digest")
        return text
    app.extensions["digest"] = morning_digest

    # ------------------------------------------------------------ Сегодня
    @app.route("/")
    @login_required
    def today_view() -> Any:
        t = today()
        new = store.deals(stage="new", limit=50)
        tasks = store.tasks(until=t)
        paid = store.deals(stage="paid", limit=50)
        rows = store.stock_rows()
        low = [r for r in rows if r["qty"] > 0 and r["per_box"] and r["qty"] - r["reserved"] < r["per_box"] * 0.5]
        short = [r for r in rows if r["reserved"] > r["qty"]]
        s = store.summary()
        return render_template("today.html", new=new, tasks=tasks, paid=paid, low=low[:20], short=short[:20], s=s,
                               chats_unread=[c for c in store.chats(limit=50) if c["unread"]],
                               vb=visits.brief(t))

    # ------------------------------------------------------------ Воронка и сделки
    @app.route("/board")
    @login_required
    def board() -> Any:
        q = (request.args.get("q") or "").strip()
        show_closed = request.args.get("all") == "1"
        deals = store.deals(q=q, limit=1000)
        hot_only = request.args.get("hot") == "1"
        if hot_only:
            deals = [d for d in deals if d["overdue_tasks"] or (d["open_tasks"] and d["stage"] in ("new", "work", "quote", "paid"))]
        cols = []
        for st, name in STAGES:
            ds = [d for d in deals if d["stage"] == st]
            if not show_closed and st in ("shipped", "lost"):
                ds = ds[:15]
            cols.append((st, name, ds, sum(Store.total(d["gross"], d["discount"]) for d in ds)))
        hot = sum(1 for d in deals if d["overdue_tasks"])
        return render_template("board.html", cols=cols, q=q, show_closed=show_closed, hot_only=hot_only, hot=hot)

    @app.route("/deals/new", methods=["GET", "POST"])
    @login_required
    def deal_new() -> Any:
        cid = request.values.get("client", type=int)
        cl = store.client(cid) if cid else None
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            if not cl and not name:
                flash("Укажите имя клиента.", "err")
                return render_template("deal_new.html", cl=cl, f=request.form), 400
            did = store.create_deal(who(), int(g.user["id"]), name=name, phone=request.form.get("phone", ""),
                                    email=request.form.get("email", ""), messenger=request.form.get("messenger", ""),
                                    kind=request.form.get("kind", "p"), company=request.form.get("company", ""),
                                    want=request.form.get("want", ""), source=request.form.get("source", "other"),
                                    client_id=cl["id"] if cl else None)
            flash("Заявка создана.", "ok")
            return redirect(url_for("deal_view", did=did))
        return render_template("deal_new.html", cl=cl, f={})

    @app.route("/deals/<int:did>")
    @login_required
    def deal_view(did: int) -> Any:
        d = store.deal(did)
        if not d:
            abort(404)
        lines = store.lines(did)
        gross = sum(int(ln["qty"]) * int(ln["price"]) for ln in lines)
        stock = {r["article"]: r for r in store.stock_rows()}
        bot = store.bot_lead(d["bot_lead_id"]) if d["bot_lead_id"] else None
        msgs = store.bot_messages(d["bot_client_id"]) if d["bot_client_id"] else []
        return render_template("deal.html", d=d, lines=lines, gross=gross, total_sum=Store.total(gross, d["discount"]),
                               calc_text=calc_text(d, lines, who()) if lines else "",
                               stock=stock, tasks=store.tasks(deal_id=did, open_only=False),
                               events=store.events(deal_id=did), bot=bot, msgs=msgs,
                               catalog=store.catalog.all(), other=store.deals(client_id=d["client_id"], limit=20),
                               chat=store.chat_of_deal(did), payments=store.payments(did), paid_kop=store.paid_kop(did),
                               tochka_on=tochka_on(), closing=store.closing_receipts_due(did),
                               tochka_method=store.setting("tochka_method", "full_prepayment"))

    def mail_contacts() -> str:
        """Строка контактов в письмах клиентам (Настройки → Письма клиентам)."""
        return store.setting("mail_contacts", "чат на сайте nashdekor.ru")

    def mail_signature(manager: str = "") -> list[str]:
        dom = conf["SHOP_DOMAIN"] or "nashdekor.ru"
        return ["", f"Ответить на это письмо или написать: zakaz@{dom}" + (f" · {mail_contacts()}" if mail_contacts() else ""),
                f"Сайт: https://{dom}", "", "С уважением, " + (f"{manager}, " if manager else "") + "«Наш декор»"]

    def calc_text(d: Any, lines: list[Any], manager: str = "") -> str:
        """Расчёт для клиента: позиции, суммы, итог, что дальше, контакты — в письмо или в мессенджер."""
        gross = sum(int(ln["qty"]) * int(ln["price"]) for ln in lines)
        total = Store.total(gross, d["discount"])
        is_order = (d["want"] or "").startswith("ЗАКАЗ.")
        out = [f"Здравствуйте, {d['client_name']}!", ""]
        if (d["client_note"] or "").strip():
            out += [d["client_note"].strip(), ""]
        out += [f"Ваш заказ №{d['id']} в «Наш декор» — состав и сумма к оплате:" if is_order else f"Расчёт №{d['id']} от «Наш декор»:", ""]
        for ln in lines:
            p = store.catalog.get(ln["article"])
            nm = p.name if p and ln["article"] in p.name else (f"{ln['article']} {p.name}" if p else ln["article"])
            out.append(f"• {nm} — {ln['qty']} шт × {int(ln['price']):,} ₽ = {int(ln['qty']) * int(ln['price']):,} ₽".replace(",", " "))
        if d["discount"]:
            out += ["", f"Без скидки: {gross:,} ₽".replace(",", " "), f"Скидка {d['discount']}%"]
        out += ["", f"Итого: {total:,} ₽".replace(",", " ")]
        if (d["address"] or "").strip():
            out += ["", f"Получение: {d['address'].strip()}"]
        if (d["pay_link"] or "").strip():
            out += ["", f"Оплатить картой или через СБП: {d['pay_link'].strip()}",
                    "Оплата проходит на защищённой странице банка, ссылка действует 7 дней. Электронный чек придёт на e-mail. После оплаты пришлём подтверждение и согласуем доставку."]
        out += ["",
                "Цены без НДС. Доставка по Санкт-Петербургу и Ленобласти рассчитывается отдельно, самовывоз со склада — бесплатно.",
                "Расчёт действует 7 дней; наличие и срок поставки подтвердим при заказе.", "",
                "Что дальше:"]
        if (d["pay_link"] or "").strip():
            out += ["• Если всё верно — оплатите по ссылке выше, и мы начнём собирать заказ. Или просто ответьте «подтверждаю» — свяжемся и согласуем доставку."]
        else:
            out += ["• Если расчёт подходит — ответьте на это письмо или напишите нам: пришлём ссылку на оплату картой или через СБП (компаниям — счёт) и согласуем доставку."]
        out += ["• Нужно изменить количество, цвет, добавить плинтус или карниз — напишите, пересчитаем.",
                "• Если ответа не будет, через пару дней мы сами напишем или позвоним, чтобы узнать решение. Если планы изменились — просто скажите, беспокоить не будем."]
        out += mail_signature(manager)
        return "\n".join(out)

    def followup_text(d: Any, lines: list[Any], n: int) -> tuple[str, str]:
        """Вежливое напоминание №n (1 или 2) клиенту, который не ответил на расчёт."""
        gross = sum(int(ln["qty"]) * int(ln["price"]) for ln in lines)
        total = Store.total(gross, d["discount"])
        sent = fmt_day(d["stage_at"][:10]) if d["stage_at"] else ""
        until = (datetime.fromisoformat(d["stage_at"][:19]) + timedelta(days=7)).date().isoformat() if d["stage_at"] else ""
        items = "; ".join(f"{ln['article']} — {ln['qty']} шт" for ln in lines[:6]) + (" …" if len(lines) > 6 else "")
        tot = f"{total:,} ₽".replace(",", " ")
        if n == 1:
            subj = f"Расчёт №{d['id']} — подошёл ли он вам? «Наш декор»"
            body = [f"Здравствуйте, {d['client_name']}!", "",
                    f"{sent} мы отправили вам расчёт №{d['id']} на {tot} ({items}).",
                    "Подскажите, пожалуйста, подходит ли он?", "",
                    "• Если да — ответьте на это письмо или напишите нам, и мы пришлём ссылку на оплату картой или через СБП (компаниям — счёт) и согласуем доставку.",
                    "• Если нужно что-то изменить — количество, цвет, добавить плинтус или карниз — напишите, пересчитаем.",
                    "• Если планы изменились — тоже напишите, мы не будем беспокоить."]
        else:
            subj = f"Расчёт №{d['id']} действует до {fmt_day(until) if until else 'конца недели'} — «Наш декор»"
            body = [f"Здравствуйте, {d['client_name']}!", "",
                    f"Напоминаем: расчёт №{d['id']} на {tot} ({items}) действует до {fmt_day(until) if until else 'конца недели'}; после этого цены и наличие могут измениться.",
                    "Чтобы зафиксировать сумму и забронировать товар, ответьте на это письмо или напишите нам — пришлём ссылку на оплату и согласуем доставку.", "",
                    "Это последнее напоминание — больше писать не будем. Если решите позже, просто напишите: сделаем новый расчёт по актуальным ценам."]
        return subj, "\n".join(body + mail_signature())

    def run_followups(day: str | None = None) -> list[str]:
        """Разослать напоминания клиентам, от которых нет ответа на расчёт (вызывается раз в день из cron: manage.py followups)."""
        day = day or today()
        if store.setting("followup_auto", "1") != "1":
            return ["автонапоминания выключены в настройках"]
        out: list[str] = []
        dom = conf["SHOP_DOMAIN"] or "nashdekor.ru"
        for row in store.followup_candidates(day):
            d = store.deal(int(row["id"]))
            lines = store.lines(int(row["id"]))
            if not d or not lines:
                continue
            n = int(row["followups"]) + 1
            subj, body = followup_text(d, lines, n)
            if send_mail(d["email"], subj, body, sender=f"Наш декор <noreply@{dom}>", reply_to=f"zakaz@{dom}"):
                store.mark_followup(int(row["id"]), "авто", d["email"], n, postpone_days=3 if n == 1 else 4)
                out.append(f"№{row['id']}: напоминание {n} → {d['email']}")
            else:
                out.append(f"№{row['id']}: почта не ответила")
        return out
    app.extensions["run_followups"] = run_followups

    def send_calc_to(did: int, email: str) -> tuple[bool, str]:
        """Отправить письмо-расчёт клиенту. Возвращает (ушло?, почему нет)."""
        d = store.deal(did)
        if not d:
            return False, "нет сделки"
        lines = store.lines(did)
        if not lines:
            return False, "в расчёте нет позиций"
        email = (email or d["email"] or "").strip()[:120]
        if not email or "@" not in email or " " in email:
            return False, "у клиента нет e-mail"
        if email != (d["email"] or ""):
            store.update_client(int(d["client_id"]), who(), email=email)
        dom = conf["SHOP_DOMAIN"] or "nashdekor.ru"
        is_order = (d["want"] or "").startswith("ЗАКАЗ.")
        ok = send_mail(email, (f"Заказ №{did} — состав и сумма к оплате, «Наш декор»" if is_order else f"Расчёт №{did} — реечные панели и декор, «Наш декор»"),
                       calc_text(d, lines, who()), sender=f"Наш декор <noreply@{dom}>", reply_to=f"zakaz@{dom}")
        c = store.c()
        if ok:
            store.log(c, f"Расчёт отправлен на {email}", who(), deal_id=did, client_id=d["client_id"]); c.commit()
            if d["stage"] in ("new", "work"):
                store.set_stage(did, "quote", who())
            return True, email
        store.log(c, f"Не удалось отправить расчёт на {email} (почта не ответила)", who(), deal_id=did, client_id=d["client_id"]); c.commit()
        return False, "почта не ответила"

    @app.post("/deals/<int:did>/followup")
    @login_required
    def deal_followup(did: int) -> Any:
        """Напоминание клиенту вручную («Напомнить сейчас») и выключатель автонапоминаний по сделке."""
        d = store.deal(did)
        if not d:
            abort(404)
        if request.form.get("toggle"):
            store.set_no_followup(did, who(), not d["no_followup"])
            flash("Автонапоминания по этой сделке " + ("включены." if d["no_followup"] else "выключены."), "ok")
            return redirect(url_for("deal_view", did=did) + "#lines")
        lines = store.lines(did)
        email = (d["email"] or "").strip()
        if not lines or "@" not in email:
            flash("Нельзя напомнить: " + ("в расчёте нет позиций." if not lines else "у клиента нет e-mail."), "err")
            return redirect(url_for("deal_view", did=did) + "#lines")
        n = min(int(d["followups"] or 0) + 1, 2)
        subj, body = followup_text(d, lines, n)
        dom = conf["SHOP_DOMAIN"] or "nashdekor.ru"
        if send_mail(email, subj, body, sender=f"Наш декор <noreply@{dom}>", reply_to=f"zakaz@{dom}"):
            store.mark_followup(did, who(), email, n)
            flash(f"Напоминание отправлено на {email}.", "ok")
        else:
            flash("Почта не ответила — напоминание не ушло.", "err")
        return redirect(url_for("deal_view", did=did) + "#lines")

    @app.post("/deals/<int:did>/send-calc")
    @login_required
    def deal_send_calc(did: int) -> Any:
        """Кнопки под расчётом: отправить на почту / сохранить текст / «отправил сам» (мессенджер, звонок)."""
        d = store.deal(did)
        if not d:
            abort(404)
        store.set_deal_text(did, who(), request.form.get("client_note", ""), request.form.get("pay_link", ""))
        if request.form.get("save_only"):
            flash("Текст для клиента сохранён.", "ok")
            return redirect(url_for("deal_view", did=did) + "#lines")
        if request.form.get("manual"):
            if not store.lines(did):
                flash("В расчёте нет позиций — добавьте товар.", "err")
                return redirect(url_for("deal_view", did=did) + "#lines")
            c = store.c(); store.log(c, "Расчёт отправлен вручную (мессенджер / по телефону)", who(), deal_id=did, client_id=d["client_id"]); c.commit()
            if d["stage"] in ("new", "work"):
                store.set_stage(did, "quote", who())
            flash("Отмечено: расчёт отправлен вручную.", "ok")
            return redirect(url_for("deal_view", did=did) + "#lines")
        ok, info = send_calc_to(did, request.form.get("email", ""))
        if ok:
            flash(f"Расчёт отправлен на {info}.", "ok")
        elif info == "у клиента нет e-mail":
            flash("Укажите e-mail клиента — или скопируйте расчёт в мессенджер и нажмите «Отправил сам».", "err")
        elif info == "почта не ответила":
            flash("Почта не ответила — письмо не ушло. Скопируйте расчёт в мессенджер и нажмите «Отправил сам».", "err")
        else:
            flash(info[0].upper() + info[1:] + " — добавьте товар.", "err")
        return redirect(url_for("deal_view", did=did) + "#lines")

    @app.post("/deals/<int:did>/stage")
    @login_required
    def deal_stage(did: int) -> Any:
        st = request.form.get("stage", "")
        d = store.deal(did)
        if not d:
            abort(404)
        target = st
        if request.form.get("next") == "1":
            order = [s for s, _ in STAGES if s != "lost"]
            target = order[order.index(d["stage"]) + 1] if d["stage"] in order and d["stage"] != order[-1] else ""
        if target == "shipped" and d["stage"] != "shipped":
            _, total = store.deal_total(did)
            paid = store.paid_kop(did)
            if 0 < paid < total * 100:
                flash(f"Не отгружаем: оплачено {rubk(paid)} из {rubk(total * 100)}. Возьмите доплату и отметьте её в блоке «Оплата».", "err")
                return redirect(safe_next(request.form.get("back")) if request.form.get("back") else url_for("deal_view", did=did) + "#pay")
        if target == "quote" and d["stage"] != "quote":
            # «Расчёт отправлен» нельзя поставить руками: либо письмо ушло, либо «Отправил сам» в карточке
            ok, info = send_calc_to(did, "")
            if ok:
                flash(f"Расчёт отправлен на {info}, этап — «Расчёт отправлен».", "ok")
            else:
                flash(f"Этап не сменён: расчёт клиенту ещё не отправлен ({info}). Откройте сделку: отправьте на почту или скопируйте в мессенджер и нажмите «Отправил сам».", "err")
            return redirect(safe_next(request.form.get("back")) if request.form.get("back") else url_for("deal_view", did=did) + "#lines")
        if request.form.get("next") == "1":
            nxt = store.next_stage(did, who())
            if nxt:
                flash(f"Этап: {STAGE_NAMES[nxt]}", "ok")
        elif st in STAGE_NAMES:
            if store.set_stage(did, st, who()) is not None:
                flash(f"Этап: {STAGE_NAMES[st]}", "ok")
                if st == "paid":
                    d = store.deal(did)
                    if d:
                        store.notify_team(f"CRM: заявка №{did} ({d['client_name']}) оплачена — можно готовить отгрузку.",
                                          title=f"Оплачено №{did} — готовить отгрузку", url=f"/deals/{did}",
                                          roles=("manager", "shipping"))
        return redirect(safe_next(request.form.get("back")) if request.form.get("back") else url_for("deal_view", did=did))

    # ------------------------------------------------------------ Точка Банк: ссылки на оплату с чеком, вебхук, деньги
    def bank() -> Tochka | None:
        tok = store.setting("tochka_jwt", "")
        if not tok:
            return None
        return Tochka(tok, store.setting("tochka_customer", ""), store.setting("tochka_merchant", ""),
                      http=app.extensions.get("tochka_http"))

    def tochka_info() -> dict[str, Any]:
        try:
            v = json.loads(store.setting("tochka_info", "") or "{}")
            return v if isinstance(v, dict) else {}
        except ValueError:
            return {}

    def tochka_on() -> bool:
        """Можно создавать ссылки: ключ есть, клиент банка выбран, приём включён в Настройках."""
        return bool(store.setting("tochka_jwt", "") and store.setting("tochka_customer", "")) and store.setting("tochka_enabled", "0") == "1"

    def notify_money(did: int, kop: int, how: str, result: str) -> None:
        d = store.deal(did)
        if not d:
            return
        if result == "paid":
            store.notify_team(f"Оплачено №{did} — {rubk(kop)} {how}: {d['client_name']}. Можно готовить отгрузку.",
                              title=f"Оплачено №{did} — {rubk(kop)} {how}", url=f"/deals/{did}", roles=("manager", "shipping"))
        elif result == "part":
            store.notify_team(f"Предоплата №{did} — {rubk(kop)} {how}: {d['client_name']}. Остаток — до отгрузки.",
                              title=f"Предоплата №{did} — {rubk(kop)} {how}", url=f"/deals/{did}")

    def check_payment(p: Any, user: str = "банк") -> str:
        """Спросить банк о ссылке и записать итог. Сумму и статус берём только отсюда, не из вебхука."""
        t = bank()
        if t is None:
            return "Точка не подключена"
        op = t.payment(str(p["operation_id"]))
        if op is None:
            return "банк не нашёл операцию"
        status = str(op.get("status") or "")
        pay_type = str(op.get("paymentType") or "")
        refunds = [float(o.get("amount") or 0) for o in (op.get("Order") or []) if isinstance(o, dict) and o.get("type") == "refund"]
        refunded: int | None = int(round(sum(refunds) * 100)) if refunds else None
        if status == "REFUNDED" and not refunded:
            refunded = int(p["amount"])
        newly = store.payment_update(int(p["id"]), user, status=status, pay_type=pay_type, refunded_kop=refunded)
        if newly:
            res = store.after_payment(int(p["deal_id"]), user)
            notify_money(int(p["deal_id"]), int(p["amount"]), PAY_TYPES.get(pay_type, "по ссылке"), res)
        return status

    def run_tochka_poll() -> list[str]:
        """Опрос банка по открытым ссылкам (cron раз в 5 минут): вебхук приходит только об оплате, а истечение
        и возвраты узнаём сами. Свежие ссылки — каждые 5 минут, за первые сутки — раз в 15 минут, дальше — раз в час."""
        if bank() is None:
            return ["Точка не подключена"]
        out: list[str] = []
        t0 = now()
        for p in store.open_payments():
            age = (t0 - datetime.fromisoformat(p["created_at"])).total_seconds()
            gap = (t0 - datetime.fromisoformat(p["checked_at"])).total_seconds() if p["checked_at"] else 1e9
            if gap < (240 if age < 3600 else 840 if age < 86400 else 3540):
                continue
            try:
                out.append(f"№{p['deal_id']} ссылка {p['id']}: {check_payment(p, 'банк (проверка)')}")
            except TochkaError as e:
                out.append(f"№{p['deal_id']} ссылка {p['id']}: {e.human()}")
        return out
    app.extensions["tochka_poll"] = run_tochka_poll

    def money_back(did: int) -> Any:
        return redirect(url_for("deal_view", did=did) + "#pay")

    @app.post("/deals/<int:did>/paylink")
    @login_required
    def deal_paylink(did: int) -> Any:
        """Ссылка на оплату с чеком 54-ФЗ на сумму расчёта (+ доставка), вставляется в письмо-расчёт."""
        d = store.deal(did)
        if not d:
            abort(404)
        t = bank()
        if t is None or not tochka_on():
            flash("Точка не подключена: Ещё → Настройки → «Точка Банк».", "err")
            return money_back(did)
        lines = store.lines(did)
        if not lines:
            flash("В расчёте нет позиций — добавьте товар.", "err")
            return money_back(did)
        if store.paid_kop(did) > 0:
            flash("По сделке уже есть оплата. Доплату по ссылке с чеком банк не поддерживает: возьмите остаток по счёту "
                  "или сделайте возврат и новую ссылку на всю сумму.", "err")
            return money_back(did)
        live = [p for p in store.payments(did) if p["kind"] == "link" and p["status"] in ("CREATED", "AUTHORIZED")]
        if live and not request.form.get("again"):
            flash("Предыдущая ссылка ещё действует. Если состав изменился — отметьте «Новая ссылка вместо прежней» и предупредите "
                  "клиента не платить по старой (если заплатит дважды — лишнее вернёте кнопкой «Возврат»).", "err")
            return money_back(did)
        email = (request.form.get("email") or d["email"] or "").strip()[:120]
        if not EMAIL_RE.fullmatch(email):
            flash("Нужен e-mail клиента — на него банк пришлёт кассовый чек.", "err")
            return money_back(did)
        if email != (d["email"] or ""):
            store.update_client(int(d["client_id"]), who(), email=email)
        try:
            delivery = max(0, min(int(re.sub(r"\D", "", request.form.get("delivery", "") or "0") or 0), 300000))
        except ValueError:
            delivery = 0
        method = "full_payment" if request.form.get("full") else store.setting("tochka_method", "full_prepayment")
        method = method if method in ("full_payment", "full_prepayment") else "full_prepayment"
        _, total = store.deal_total(did)
        rows = []
        for ln in lines:
            p = store.catalog.get(ln["article"])
            nm = p.name if p and ln["article"] in p.name else (f"{ln['article']} {p.name}" if p else ln["article"])
            rows.append((nm, int(ln["qty"]), int(ln["price"])))
        try:
            items, kop = receipt_items(rows, int(d["discount"] or 0), delivery, method, goods_total=total)
        except ValueError as e:
            flash(f"Не получилось собрать чек: {e}.", "err")
            return money_back(did)
        if kop < 100:
            flash("Сумма к оплате меньше 1 ₽.", "err")
            return money_back(did)
        dom = conf["SHOP_DOMAIN"] or "nashdekor.ru"
        modes = [m for m in (tochka_info().get("retailer") or {}).get("paymentModes") or [] if m in ("card", "sbp")] or ["card", "sbp"]
        client: dict[str, str] = {"name": (d["client_name"] or "")[:100], "email": email}
        if re.fullmatch(r"\+7\d{10}", d["phone"] or ""):
            client["phone"] = d["phone"]
        link_id = f"ND{did}-{len(store.payments(did)) + 1}-{secrets.token_hex(3)}"
        data = {"amount": kop / 100, "purpose": f"Заказ №{did} в магазине «Наш декор»", "paymentMode": modes,
                "paymentLinkId": link_id, "ttl": 10080, "redirectUrl": f"https://{dom}/oplata/?paid={did}",
                "failRedirectUrl": f"https://{dom}/oplata/?fail={did}", "taxSystemCode": store.setting("tochka_tax", "usn_income_outcome"),
                "Client": client, "Items": items}
        try:
            out = t.create_link(data)
        except TochkaError as e:
            c = store.c(); store.log(c, f"Ссылка на оплату не создана: {e.human()}", who(), deal_id=did, client_id=d["client_id"]); c.commit()
            flash("Ссылка не создана: " + e.human(), "err")
            return money_back(did)
        store.add_payment(did, who(), kind="link", amount_kop=kop, link_id=link_id, operation_id=str(out["operationId"]),
                          url=str(out["paymentLink"]), method=method, status=str(out.get("status") or "CREATED"), email=email)
        flash(f"Ссылка на {rubk(kop)} создана и вставлена в расчёт — отправьте его клиенту: «Отправить расчёт на почту» "
              "или «Скопировать расчёт для мессенджера». Когда клиент оплатит, сделка сама станет «Оплачено».", "ok")
        return redirect(url_for("deal_view", did=did) + "#lines")

    @app.post("/deals/<int:did>/payments/<int:pid>/check")
    @login_required
    def payment_check(did: int, pid: int) -> Any:
        p = store.payment(pid)
        if not p or int(p["deal_id"]) != did or p["kind"] != "link":
            abort(404)
        try:
            st = check_payment(p, who())
            flash(f"Банк: {STATUS_NAMES.get(st, st)}.", "ok")
        except TochkaError as e:
            flash("Не удалось проверить: " + e.human(), "err")
        return money_back(did)

    @app.post("/deals/<int:did>/payments/<int:pid>/refund")
    @admin_required
    def payment_refund(did: int, pid: int) -> Any:
        """Возврат по оплате ссылкой (полный или часть). Чек возврата формирует банк."""
        p = store.payment(pid)
        if not p or int(p["deal_id"]) != did:
            abort(404)
        if p["kind"] != "link" or not p["paid_at"] or not p["operation_id"]:
            flash("Через банк возвращается только оплата по ссылке. Оплату по счёту возвращают платёжкой из интернет-банка.", "err")
            return money_back(did)
        if request.form.get("confirm") != "1":
            flash("Поставьте галочку «Да, вернуть» — возврат не отменить.", "err")
            return money_back(did)
        raw = (request.form.get("amount") or "").replace(" ", "").replace(",", ".")
        try:
            kop = int(round(float(raw) * 100))
        except ValueError:
            kop = 0
        left = int(p["amount"]) - int(p["refunded"])
        if kop <= 0 or kop > left:
            flash(f"Сумма возврата — от 1 ₽ до {rubk(left)}.", "err")
            return money_back(did)
        t = bank()
        if t is None:
            flash("Точка не подключена.", "err")
            return money_back(did)
        try:
            r = t.refund(str(p["operation_id"]), kop / 100)
        except TochkaError as e:
            flash("Возврат не прошёл: " + e.human(), "err")
            return money_back(did)
        if r.get("isRefund") is False:
            flash("Банк отказал в возврате — уточните в чате Точки.", "err")
            return money_back(did)
        store.payment_update(pid, who(), status="ON-REFUND", refunded_kop=int(p["refunded"]) + kop)
        c = store.c(); store.log(c, f"Возврат {rubk(kop)} отправлен в банк", who(), deal_id=did); c.commit()
        flash(f"Возврат {rubk(kop)} отправлен в банк. Деньги вернутся клиенту на карту или счёт, с которых он платил; статус обновится сам.", "ok")
        return money_back(did)

    @app.post("/deals/<int:did>/payments/manual")
    @login_required
    def payment_manual(did: int) -> Any:
        """Отметить оплату, которая прошла мимо CRM: по счёту с расчётного счёта или по ссылке из интернет-банка."""
        d = store.deal(did)
        if not d:
            abort(404)
        raw = (request.form.get("amount") or "").replace(" ", "").replace(",", ".")
        try:
            kop = int(round(float(raw) * 100))
        except ValueError:
            kop = 0
        if kop <= 0 or kop > 100_000_000:
            flash("Укажите сумму оплаты.", "err")
            return money_back(did)
        kind = "invoice" if request.form.get("kind") == "invoice" else "manual"
        store.add_payment(did, who(), kind=kind, amount_kop=kop, status="APPROVED", paid=True,
                          note=(request.form.get("note") or "").strip()[:200])
        res = store.after_payment(did, who())
        notify_money(did, kop, "по счёту" if kind == "invoice" else "", res)
        flash("Оплата отмечена." + (" Этап — «Оплачено»." if res == "paid" else " Остаток — задачей до отгрузки." if res == "part" else ""), "ok")
        return money_back(did)

    @app.post("/deals/<int:did>/closing-done")
    @login_required
    def payment_closing_done(did: int) -> Any:
        n = store.set_closing_done(did, who())
        flash("Отмечено: чек «Полный расчёт» оформлен." if n else "Нечего отмечать.", "ok" if n else "err")
        return money_back(did)

    def bank_keys(refresh: bool = False) -> list[dict[str, Any]]:
        """Открытый ключ банка для подписи вебхуков: из настроек, при отсутствии — с сайта Точки (не чаще раза в 10 минут)."""
        txt = store.setting("tochka_jwk", "")
        if (not txt or refresh) and (app.extensions.get("tochka_http") or not app.testing):
            last = float(store.setting("tochka_jwk_try", "0") or 0)
            if time.time() - last > 600:
                store.set_setting("tochka_jwk_try", str(int(time.time())))
                st, body = (app.extensions.get("tochka_http") or http_request)("GET", KEY_URL, {"Accept": "application/json"}, None)
                if st == 200:
                    try:
                        parse_jwk(body.decode("utf-8"))
                        txt = body.decode("utf-8")
                        store.set_setting("tochka_jwk", txt)
                    except (ValueError, UnicodeDecodeError):
                        log.warning("Точка: ключ для вебхуков не разобран")
        try:
            return parse_jwk(txt) if txt else []
        except ValueError:
            return []

    @app.route("/api/tochka/webhook", methods=["POST"])
    def tochka_webhook() -> Any:
        """Вебхук Точки: тело — JWT, подписанный банком (RS256). Ответ 200 — принято; 400 — подпись не банка;
        503 — банк не ответил на проверку (Точка повторит). Тестовые вебхуки банка при регистрации — 200."""
        raw = request.get_data(cache=False)[:65536]
        token = raw.decode("ascii", "ignore").strip()
        claims = jwt_claims(token)
        if not claims:
            return Response("not a jwt", status=400, mimetype="text/plain")
        verified = False
        keys = bank_keys()
        if keys:
            for attempt in (0, 1):
                for k in keys:
                    try:
                        claims = verify_rs256(token, k)
                        verified = True
                        break
                    except (ValueError, KeyError):
                        continue
                if verified or attempt:
                    break
                keys = bank_keys(refresh=True)     # банк мог сменить ключ
            if not verified:
                log.warning("Точка: вебхук с неверной подписью от %s", ip())
                return Response("bad signature", status=400, mimetype="text/plain")
        our = store.setting("tochka_customer", "")
        if not our or str(claims.get("customerCode") or "") != our:
            return Response("ok", mimetype="text/plain")            # чужой или тестовый вебхук
        kind = str(claims.get("webhookType") or "")
        if kind == "acquiringInternetPayment":
            p = store.payment_by_op(str(claims.get("operationId") or ""))
            if p:
                try:
                    check_payment(p, "банк")
                except TochkaError as e:
                    log.warning("Точка: проверка оплаты не прошла: %s", e.human())
                    return Response("retry", status=503, mimetype="text/plain")
        elif kind == "incomingPayment" and verified:                # без подписи поступлению не верим: перепроверить его нечем
            payer = claims.get("SidePayer") or {}
            try:
                kop = int(round(float(str(payer.get("amount") or claims.get("amount") or "0").replace(",", ".")) * 100))
            except ValueError:
                kop = 0
            pid = str(claims.get("paymentId") or claims.get("documentNumber") or "")
            if kop > 0 and pid:
                purpose = str(claims.get("purpose") or "")
                eid, new = store.add_bank_event(pid, kop, str(payer.get("name") or ""), str(payer.get("inn") or ""), purpose,
                                                str(claims.get("date") or ""))
                if new:
                    did = store.match_bank_event(str(payer.get("inn") or ""), purpose)
                    if did:
                        store.link_bank_event(eid, did, "банк")
                        notify_money(did, kop, "по счёту", store.after_payment(did, "банк"))
                    elif "эквайр" not in purpose.lower():
                        store.notify_team(f"Поступило {rubk(kop)} от {payer.get('name') or 'плательщика'} — сделку не нашли. "
                                          f"Назначение: {purpose[:120]}", title=f"Поступило {rubk(kop)} — привяжите к сделке",
                                          url="/money", roles=("admin",))
        return Response("ok", mimetype="text/plain")

    @app.route("/money")
    @admin_required
    def money_view() -> Any:
        month = request.args.get("m", "") or today()[:7]
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            month = today()[:7]
        y, mo = int(month[:4]), int(month[5:])
        prev = f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"
        nxt = f"{y + 1}-01" if mo == 12 else f"{y}-{mo + 1:02d}"
        names = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
        return render_template("money.html", m=store.money(month), month=month, prev=prev, nxt=nxt, month_name=f"{names[mo - 1]} {y}",
                               events=store.bank_events(60), tochka=tochka_on(), info=tochka_info())

    @app.post("/money/link")
    @admin_required
    def money_link() -> Any:
        try:
            eid, did = int(request.form.get("event", "0")), int(re.sub(r"\D", "", request.form.get("deal", "")) or 0)
        except ValueError:
            eid, did = 0, 0
        if store.link_bank_event(eid, did, who()):
            res = store.after_payment(did, who())
            flash(f"Поступление привязано к заявке №{did}." + (" Этап — «Оплачено»." if res == "paid" else ""), "ok")
        else:
            flash("Не привязано: проверьте номер заявки (или поступление уже привязано).", "err")
        return redirect(url_for("money_view"))

    @app.post("/settings/tochka")
    @admin_required
    def settings_tochka() -> Any:
        """Точка Банк: ключ, проверка связи (клиент банка, торговая точка, касса), вебхук, включение приёма оплат."""
        act = request.form.get("act", "save")
        back = redirect(url_for("settings_view") + "#tochka")
        if act == "forget":
            for k in ("tochka_jwt", "tochka_customer", "tochka_merchant", "tochka_info", "tochka_client_id", "tochka_webhook"):
                store.set_setting(k, "")
            store.set_setting("tochka_enabled", "0")
            c = store.c(); store.log(c, "Точка: ключ удалён из CRM", who()); c.commit()
            flash("Ключ Точки удалён из CRM. Удалите его и в интернет-банке: «Интеграции и API».", "ok")
            return back
        if act == "save":
            tok = re.sub(r"\s+", "", request.form.get("jwt", ""))
            if tok:
                if tok.count(".") != 2 or len(tok) > 8000 or not jwt_claims(tok):
                    flash("Это не похоже на JWT-ключ: он длинный и состоит из трёх частей через точку.", "err")
                    return back
                store.set_setting("tochka_jwt", tok)
                store.set_setting("tochka_enabled", "0")
                c = store.c(); store.log(c, "Точка: сохранён новый JWT-ключ", who()); c.commit()
            for k, f in (("tochka_customer", "customer"), ("tochka_merchant", "merchant"), ("tochka_client_id", "client_id")):
                if f in request.form:
                    store.set_setting(k, re.sub(r"[^\w-]", "", request.form.get(f, ""))[:64])
            tax = request.form.get("tax", "")
            if tax in dict(TAX_SYSTEMS):
                store.set_setting("tochka_tax", tax)
            meth = request.form.get("method", "")
            if meth in ("full_prepayment", "full_payment"):
                store.set_setting("tochka_method", meth)
            flash("Сохранено." + (" Теперь нажмите «Проверить связь с банком»." if tok else ""), "ok")
            return back
        t = bank()
        if t is None:
            flash("Сначала вставьте JWT-ключ из интернет-банка Точки.", "err")
            return back
        if act == "check":
            info: dict[str, Any] = {"checked_at": iso_now_app(), "exp": t.expires(), "client_id": t.client_id()}
            try:
                custs = t.customers()
                biz = [c for c in custs if c.get("customerType") == "Business"]
                info["customers"] = [{"code": c.get("customerCode"), "name": c.get("shortName") or c.get("fullName"),
                                      "type": c.get("customerType"), "inn": c.get("taxCode")} for c in custs]
                if not store.setting("tochka_customer", "") and len(biz) == 1:
                    store.set_setting("tochka_customer", str(biz[0].get("customerCode") or ""))
                code = store.setting("tochka_customer", "")
                if not code:
                    store.set_setting("tochka_info", json.dumps(info, ensure_ascii=False))
                    flash("Ключ работает. Выберите, чей счёт — ИП: " + ", ".join(f"{c['code']} ({c['name']})" for c in info["customers"]), "err")
                    return back
                rs = Tochka(t.token, code, "", http=t.http).retailers(code)
                info["retailers"] = [{k: r.get(k) for k in ("merchantId", "status", "isActive", "name", "url", "cashbox", "paymentModes", "rate", "mcc")} for r in rs]
                mine = [r for r in rs if r.get("merchantId") == store.setting("tochka_merchant", "")] or \
                       [r for r in rs if r.get("status") == "REG" and r.get("isActive")]
                if mine:
                    if not store.setting("tochka_merchant", ""):
                        store.set_setting("tochka_merchant", str(mine[0].get("merchantId") or ""))
                    info["retailer"] = info["retailers"][rs.index(mine[0])]
            except TochkaError as e:
                info["error"] = e.human()
                store.set_setting("tochka_info", json.dumps(info, ensure_ascii=False))
                flash("Проверка не прошла: " + e.human(), "err")
                return back
            store.set_setting("tochka_info", json.dumps(info, ensure_ascii=False))
            store.set_setting("tochka_jwk_try", "0")
            bank_keys(refresh=True)                       # открытый ключ банка для подписи вебхуков — заранее
            r = info.get("retailer") or {}
            if not r:
                flash("Ключ работает, но интернет-эквайринга у ИП ещё нет (или он не одобрен). Подайте заявку в интернет-банке: «Интернет-эквайринг».", "err")
            elif r.get("status") != "REG" or not r.get("isActive"):
                flash(f"Эквайринг ещё оформляется (статус {r.get('status')}). Проверьте позже.", "err")
            elif not r.get("cashbox"):
                flash("Эквайринг работает, но к нему не подключены «Чеки» или облачная касса — без них ссылку с чеком банк не создаст. "
                      "Подключите «Чеки» в интернет-банке и проверьте снова.", "err")
            else:
                flash("Связь с банком есть: эквайринг и чеки подключены. Можно включать приём оплат.", "ok")
            return back
        if act == "webhook":
            cid = store.setting("tochka_client_id", "") or t.client_id()
            if not cid:
                flash("Не знаю client_id ключа — впишите его в поле «client_id» (показан в интернет-банке рядом с ключом).", "err")
                return back
            url = f"https://{request.host}/api/tochka/webhook"
            only_links = False
            try:
                t.set_webhook(cid, url)
            except TochkaError as e:
                if e.status not in (400, 403, 422):
                    flash("Уведомления не подключены: " + e.human(), "err")
                    return back
                try:                                   # ключу не разрешены поступления на счёт — хотя бы оплаты по ссылкам
                    t.set_webhook(cid, url, ["acquiringInternetPayment"])
                    only_links = True
                except TochkaError as e2:
                    flash("Уведомления не подключены: " + e2.human(), "err")
                    return back
            store.set_setting("tochka_webhook", f"{url} · {iso_now_app()}" + (" · только оплаты по ссылкам" if only_links else ""))
            flash("Уведомления подключены: банк будет сообщать CRM об оплате по ссылке" + (
                  ". Поступления по счетам банк этому ключу не отдаёт — их отмечайте кнопкой в сделке." if only_links else
                  " и о поступлениях на расчётный счёт."), "ok")
            return back
        if act in ("enable", "disable"):
            if act == "enable":
                r = tochka_info().get("retailer") or {}
                ok = r.get("status") == "REG" and r.get("isActive") and (r.get("cashbox") or request.form.get("force") == "1")
                if not (store.setting("tochka_customer", "") and ok):
                    flash("Включить нельзя: сначала «Проверить связь с банком» — эквайринг должен быть активен и с подключёнными чеками.", "err")
                    return back
            store.set_setting("tochka_enabled", "1" if act == "enable" else "0")
            c = store.c(); store.log(c, "Точка: приём оплат по ссылкам " + ("включён" if act == "enable" else "выключен"), who()); c.commit()
            flash("Приём оплат по ссылкам " + ("включён: в сделках появилась кнопка «Создать ссылку на оплату»." if act == "enable" else "выключен."), "ok")
            return back
        abort(400)

    def iso_now_app() -> str:
        return now().isoformat(timespec="seconds")

    @app.post("/deals/<int:did>/edit")
    @login_required
    def deal_edit(did: int) -> Any:
        f = {k: request.form[k] for k in ("want", "discount", "address", "ship_date", "note", "lost_reason", "source")
             if k in request.form}
        store.update_deal(did, who(), **f)
        flash("Сохранено.", "ok")
        return redirect(url_for("deal_view", did=did) + "#" + (request.form.get("anchor") or "top"))

    @app.post("/deals/<int:did>/delete")
    @admin_required
    def deal_delete(did: int) -> Any:
        d = store.deal(did)
        if d and store.payments(did):
            flash("У заявки есть платежи — удалить нельзя, иначе пропадут записи о деньгах. Поставьте этап «Отказ».", "err")
            return redirect(url_for("deal_view", did=did))
        if d and request.form.get("confirm") == "1" and store.delete_deal(did, who()):
            flash(f"Заявка №{did} удалена.", "ok")
            return redirect(url_for("client_view", cid=d["client_id"]))
        flash("Отметьте «Да, удалить».", "err")
        return redirect(url_for("deal_view", did=did))

    @app.post("/deals/<int:did>/lines")
    @login_required
    def line_add(did: int) -> Any:
        art = (request.form.get("article") or "").strip()
        qty = request.form.get("qty", "0")
        if art:
            p = store.catalog.find(art)
            if not p:
                flash(f"Артикула «{art}» нет в каталоге сайта. Проверьте написание — например A902, GS 1, 2-7, A611/2.", "err")
                return redirect(url_for("deal_view", did=did) + "#lines")
            store.add_line(did, p.article, int(qty) if qty.strip().isdigit() else 0, who())
            if p.article.upper() != art.upper().replace(" ", ""):
                flash(f"Добавлен {p.article} («{art}»).", "ok")
        return redirect(url_for("deal_view", did=did) + "#lines")

    @app.post("/lines/<int:lid>")
    @login_required
    def line_set(lid: int) -> Any:
        did = int(request.form.get("deal", "0") or 0)
        if request.form.get("delete") == "1":
            did = store.del_line(lid, who()) or did
        else:
            q = request.form.get("qty", "")
            p = request.form.get("price", "")
            store.set_line(lid, int(q) if q.strip().isdigit() else 0, int(p) if p.strip().isdigit() else None, who())
        return redirect(url_for("deal_view", did=did) + "#lines")

    @app.post("/deals/<int:did>/tasks")
    @login_required
    def task_add(did: int) -> Any:
        store.add_task(did, request.form.get("title", ""), request.form.get("due", ""), who(), int(g.user["id"]))
        return redirect(url_for("deal_view", did=did) + "#tasks")

    @app.post("/tasks/<int:tid>")
    @login_required
    def task_done(tid: int) -> Any:
        store.done_task(tid, request.form.get("done") == "1", who())
        return redirect(safe_next(request.form.get("back")))

    @app.route("/tasks", methods=["GET", "POST"])
    @login_required
    def tasks_view() -> Any:
        if request.method == "POST":
            store.add_task(None, request.form.get("title", ""), request.form.get("due", ""), who(), int(g.user["id"]))
            return redirect(url_for("tasks_view"))
        return render_template("tasks.html", tasks=store.tasks())

    # ------------------------------------------------------------ клиенты
    @app.route("/clients")
    @login_required
    def clients_view() -> Any:
        q = (request.args.get("q") or "").strip()
        return render_template("clients.html", clients=store.clients(q), q=q)

    @app.route("/clients/<int:cid>", methods=["GET", "POST"])
    @login_required
    def client_view(cid: int) -> Any:
        cl = store.client(cid)
        if not cl:
            abort(404)
        if request.method == "POST":
            store.update_client(cid, who(), **{k: request.form[k] for k in
                                               ("name", "phone", "email", "messenger", "kind", "company", "inn", "note")
                                               if k in request.form})
            flash("Клиент сохранён.", "ok")
            return redirect(url_for("client_view", cid=cid))
        return render_template("client.html", cl=cl, deals=store.deals(client_id=cid), events=store.events(client_id=cid, limit=30))

    # ------------------------------------------------------------ склад
    @app.route("/stock")
    @login_required
    def stock_view() -> Any:
        kind = request.args.get("kind", "")
        q = (request.args.get("q") or "").strip().lower()
        only = request.args.get("only", "")
        rows = store.stock_rows()
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        if q:
            rows = [r for r in rows if q in (r["article"] + " " + r["name"]).lower()]
        if only == "have":
            rows = [r for r in rows if r["qty"] > 0]
        value = sum(r["qty"] * r["price"] for r in store.stock_rows())
        return render_template("stock.html", rows=rows, kind=kind, q=q, only=only, value=value)

    @app.post("/stock/<path:article>")
    @login_required
    def stock_set(article: str) -> Any:
        store.set_stock(article, who(), qty=request.form.get("qty"), price=request.form.get("price"))
        flash(f"{article}: сохранено.", "ok")
        back = request.form.get("back") or url_for("stock_view")
        return redirect(safe_next(back) + f"#a-{re.sub(r'[^A-Za-z0-9-]', '-', article)}")

    # ------------------------------------------------------------ отчёты
    @app.route("/reports")
    @login_required
    def reports_view() -> Any:
        return render_template("reports.html", s=store.summary(), lost=store.deals(stage="lost", limit=50))

    # ------------------------------------------------------------ посещаемость сайта
    @app.route("/site")
    @login_required
    def site_view() -> Any:
        try:
            d = int(request.args.get("d", "7"))
        except ValueError:
            d = 7
        d = d if d in (1, 7, 30, 90) else 7
        return render_template("site.html", r=visits.report(today(), d), d=d)

    # ------------------------------------------------------------ настройки
    @app.route("/settings")
    @login_required
    def settings_view() -> Any:
        return render_template("settings.html", users=store.users() if g.user["role"] == "admin" else [],
                               conf=conf, bot=bool(store._bot()), hit_ips="\n".join(own_ips()), my_ip=ip(),
                               my_ip_own=ip_is_own(ip()), visits_total=visits.count(),
                               followup_auto=store.setting("followup_auto", "1") == "1", mail_contacts=mail_contacts(),
                               push_devices=store.push_subs_all() if g.user["role"] == "admin" else [],
                               chat_stats=store.chat_stats(), push_total=len(store.push_subs_all()),
                               tochka=dict(has_key=bool(store.setting("tochka_jwt", "")), on=tochka_on(), info=tochka_info(),
                                           customer=store.setting("tochka_customer", ""), merchant=store.setting("tochka_merchant", ""),
                                           client_id=store.setting("tochka_client_id", ""), tax=store.setting("tochka_tax", "usn_income_outcome"),
                                           method=store.setting("tochka_method", "full_prepayment"), webhook=store.setting("tochka_webhook", ""),
                                           unlinked=len(store.bank_events(200, unlinked=True))),
                               TAX_SYSTEMS=TAX_SYSTEMS)

    @app.post("/settings/hit-ips")
    @admin_required
    def settings_hit_ips() -> Any:
        """Свои IP для счётчика: сохранить список, добавить текущий адрес или обнулить статистику."""
        if request.form.get("reset"):
            n = visits.clear()
            c = store.c(); store.log(c, f"Обнулена статистика сайта: {n} отметок", who()); c.commit()
            flash(f"Статистика сайта обнулена ({n} отметок).", "ok")
            return redirect(url_for("settings_view"))
        raw = request.form.get("ips", "")
        if request.form.get("add_mine"):
            raw += "\n" + ip()
        good: list[str] = []
        bad: list[str] = []
        for tok in raw.replace(",", " ").split():
            try:
                ipaddress.ip_network(tok, strict=False)
                if tok not in good:
                    good.append(tok)
            except ValueError:
                bad.append(tok)
        store.set_setting("hit_ignore_ips", "\n".join(good))
        flash(("Свои адреса сохранены: %d." % len(good)) + (" Не похоже на IP: " + ", ".join(bad) if bad else ""), "err" if bad else "ok")
        return redirect(url_for("settings_view"))

    @app.post("/settings/mail")
    @admin_required
    def settings_mail() -> Any:
        """Письма клиентам: автонапоминания вкл/выкл и строка контактов в подписи."""
        store.set_setting("followup_auto", "1" if request.form.get("followup_auto") else "0")
        store.set_setting("mail_contacts", (request.form.get("mail_contacts") or "").strip()[:200])
        flash("Настройки писем сохранены.", "ok")
        return redirect(url_for("settings_view"))

    @app.post("/settings/password")
    @login_required
    def settings_password() -> Any:
        old, new, new2 = (request.form.get(k, "") for k in ("old", "new", "new2"))
        if not check_password_hash(g.user["pw_hash"], old):
            flash("Старый пароль неверный.", "err")
        elif new != new2:
            flash("Новые пароли не совпали.", "err")
        elif len(new) < 10:
            flash("Новый пароль — от 10 символов.", "err")
        else:
            h = generate_password_hash(new)
            store.set_password(int(g.user["id"]), h)
            session["pwv"] = h[-16:]
            flash("Пароль изменён.", "ok")
        return redirect(url_for("settings_view"))

    @app.post("/settings/users")
    @admin_required
    def settings_user_add() -> Any:
        pw = request.form.get("password", "")
        if len(pw) < 10:
            flash("Пароль — от 10 символов.", "err")
        else:
            try:
                store.add_user(request.form.get("login", ""), request.form.get("name", ""),
                               request.form.get("role", "staff"), generate_password_hash(pw))
                flash("Пользователь добавлен.", "ok")
            except Exception as exc:  # noqa: BLE001
                flash(f"Не добавлен: {exc}", "err")
        return redirect(url_for("settings_view"))

    @app.post("/settings/users/<int:uid>")
    @admin_required
    def settings_user_set(uid: int) -> Any:
        if uid == int(g.user["id"]) and (request.form.get("active") == "0" or request.form.get("role") == "staff"):
            flash("Себя нельзя отключить или лишить прав владельца.", "err")
            return redirect(url_for("settings_view"))
        pw = request.form.get("password", "")
        if pw:
            if len(pw) < 10:
                flash("Пароль — от 10 символов.", "err")
                return redirect(url_for("settings_view"))
            store.set_password(uid, generate_password_hash(pw))
        store.set_user(uid, name=request.form.get("name"), role=request.form.get("role"),
                       active=(request.form.get("active") == "1") if "active" in request.form else None)
        flash("Сохранено.", "ok")
        return redirect(url_for("settings_view"))

    # ------------------------------------------------------------ сервер (только просмотр)
    # Отчёт пишет root (prostranstvo-crm server-page, cron раз в минуту); CRM только читает его
    # и по кнопке оставляет файл-просьбу «обновить». Никаких команд из CRM на сервере не выполняется.
    status_file = cfg.get("SERVER_STATUS_FILE") or os.path.join(
        os.path.dirname(os.path.abspath(conf["CRM_DB"])), "server-status.txt")
    request_file = os.path.join(os.path.dirname(status_file), "server-request")
    action_file = os.path.join(os.path.dirname(status_file), "server-action.txt")

    def last_action() -> tuple[str, bool]:
        try:
            with open(action_file, encoding="utf-8", errors="replace") as f:
                t = f.read(60_000)
        except OSError:
            return "", False
        return t, "Состояние: выполняется" in t

    @app.route("/server")
    @admin_required
    def server_view() -> Any:
        text, age = "", None
        try:
            st = os.stat(status_file)
            with open(status_file, encoding="utf-8", errors="replace") as f:
                text = f.read(200_000)
            age = max(0, int((time.time() - st.st_mtime) // 60))
        except OSError:
            pass
        act, running = last_action()
        actions = [a for a in SERVER_ACTIONS if a[0] != ("leads-off" if not conf["SITE_LEADS"] else "leads-on")]
        return render_template("server.html", text=text, age=age, pending=os.path.exists(request_file) or running,
                               act=act, running=running, actions=actions)

    @app.post("/server/run")
    @admin_required
    def server_run() -> Any:
        a = request.form.get("action", "")
        if a not in SERVER_ACTION_KEYS:
            abort(400, "Нет такого действия.")
        if a == "reboot" and request.form.get("confirm") != "1":
            flash("Для перезагрузки отметьте «Да, перезагрузить».", "err")
            return redirect(url_for("server_view"))
        if os.path.exists(request_file) or last_action()[1]:
            flash("Предыдущая команда ещё выполняется — дождитесь её.", "err")
            return redirect(url_for("server_view"))
        try:
            with open(request_file, "w", encoding="utf-8") as f:
                f.write(f"{a} {g.user['login']}\n")
            log.info("сервер: действие %s запросил %s", a, g.user["login"])
            flash("Принято — выполню в течение минуты, результат появится ниже. Страница обновится сама.", "ok")
        except OSError:
            flash("Не удалось передать команду серверу.", "err")
        return redirect(url_for("server_view"))

    @app.post("/server/refresh")
    @admin_required
    def server_refresh() -> Any:
        try:
            with open(request_file, "w", encoding="utf-8") as f:
                f.write("refresh\n")
            flash("Обновлю в течение минуты — страница обновится сама.", "ok")
        except OSError:
            flash("Не удалось запросить обновление.", "err")
        return redirect(url_for("server_view"))

    # ------------------------------------------------------------ API: заявка с сайта
    def cors(resp: Response, cache: str = "no-store") -> Response:
        origin = request.headers.get("Origin", "").rstrip("/")
        if origin and origin in conf["SITE_ORIGINS"]:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Max-Age"] = "600"
        resp.headers["Vary"] = "Origin"
        resp.headers["Cache-Control"] = cache
        return resp

    # ------------------------------------------------------------ API: цены и наличие для сайта
    # Цены и остатки ведём в CRM («Склад и цены»), сайт показывает их отсюда.
    # Отдаём только цену и свободный остаток по артикулу — то, что и так видит покупатель.
    @app.route("/api/catalog", methods=["GET", "OPTIONS"])
    def api_catalog() -> Any:
        if request.method == "OPTIONS":
            return cors(Response(status=204))
        try:
            items = store.public_catalog()
        except Exception:  # noqa: BLE001 — сайт тогда покажет свои вшитые цены
            log.warning("каталог для сайта не собран")
            return cors(jsonify(ok=False)), 500
        return cors(jsonify(ok=True, items=items), cache="public, max-age=30")

    @app.route("/api/lead", methods=["POST", "OPTIONS"])
    def api_lead() -> Any:
        if request.method == "OPTIONS":
            return cors(Response(status=204))
        origin = request.headers.get("Origin", "").rstrip("/")
        if origin and origin not in conf["SITE_ORIGINS"]:
            return cors(jsonify(ok=False, error="origin")), 403
        if not conf["SITE_LEADS"]:
            return cors(jsonify(ok=False, error="off")), 503
        q = _recent(leads_by_ip[ip()], LEAD_WINDOW)
        if len(q) >= LEAD_MAX:
            return cors(jsonify(ok=False, error="rate")), 429
        data = request.get_json(silent=True) or request.form.to_dict()
        if not isinstance(data, dict):
            return cors(jsonify(ok=False, error="format")), 400
        if str(data.get("website") or "").strip():  # ловушка для ботов — поле скрыто от людей
            return cors(jsonify(ok=True)), 200
        name = str(data.get("name") or "").strip()[:120]
        contact = str(data.get("contact") or "").strip()[:200]
        consent = data.get("consent") in (True, "1", 1, "true", "on")
        if not name or not contact or not consent:
            return cors(jsonify(ok=False, error="fields")), 400
        q.append(time.monotonic())
        who_kind = {"designer": "d", "дизайнер": "d", "company": "c", "компания": "c"}.get(str(data.get("who") or "").lower(), "p")
        msg = str(data.get("message") or "").strip()[:2000]
        calc = str(data.get("calc") or "").strip()[:4000]
        email = str(data.get("email") or "").strip()[:120]
        if email and ("@" not in email or " " in email):
            email = ""
        intent = str(data.get("intent") or "").lower()
        is_order = intent == "buy"
        is_call = intent == "call"
        address = str(data.get("address") or "").strip()[:500]
        if is_order:
            msg = ("ЗАКАЗ. " + (f"Доставка: {address}. " if address else "") + msg).strip()
        elif is_call:
            msg = ("ПЕРЕЗВОНИТЬ. " + msg).strip()
        phone, cemail, messenger = split_contact(contact)
        did = store.create_deal("сайт", None, name=name, contact=contact, phone=phone, email=email or cemail, messenger=messenger,
                                kind=who_kind, want=msg, source="site",
                                calc=calc, consent_at=str(data.get("consentAt") or "")[:40] or store_now(),
                                consent_version=str(data.get("consentVersion") or "")[:40])
        if calc:
            store.lines_from_calc(did, calc, "сайт")
        if is_order and address:
            store.update_deal(did, "сайт", address=address)
        if is_call:
            store.rename_open_task(did, "Связаться с клиентом", "Перезвонить клиенту", "сайт")
        head = f"Новый ЗАКАЗ с сайта №{did}" if is_order else f"Просьба ПЕРЕЗВОНИТЬ с сайта №{did}" if is_call else f"Новая заявка с сайта №{did}"
        txt = head + f": {name}, {contact}" + (f", {email}" if email else "") + (f"\n{msg}" if msg else "")
        store.notify_team(txt, title=head, url=f"/deals/{did}")
        send_mail(conf["NOTIFY_EMAIL"], head, txt + f"\n\nCRM: https://crm.{conf['SHOP_DOMAIN']}/deals/{did}"
                  if conf["SHOP_DOMAIN"] else txt)
        return cors(jsonify(ok=True, id=did)), 200

    # ------------------------------------------------------------ API: чат на сайте
    # Окно «Чат» на каждой странице сайта. Посетитель — без входа: его переписку определяет случайный
    # ключ sid в его браузере (localStorage). Сообщения — в CRM («Чат»), сотрудникам — пуш; ответ виден в том же окне.
    def chat_json(rows: list[Any]) -> list[dict[str, Any]]:
        return [{"id": int(r["id"]), "who": "me" if r["who"] == "client" else r["who"], "author": r["author"] if r["who"] == "staff" else "",
                 "text": r["text"], "at": r["created_at"][:16]} for r in rows if r["who"] in ("client", "staff")]

    def chat_contact_in(text: str) -> str:
        m = EMAIL_RE.search(text) or PHONE_RE.search(text)
        return m.group(0).strip() if m else ""

    def chat_to_deal(cid: int) -> int | None:
        """Есть контакт, а сделки ещё нет — создаём заявку из чата (воронка: задача «Связаться с клиентом»)."""
        ch = store.chat(cid)
        if not ch or ch["deal_id"] or not ch["contact"]:
            return ch["deal_id"] if ch else None
        first = " / ".join(r["text"] for r in store.chat_msgs(cid) if r["who"] == "client")[:300]
        phone, email, messenger = split_contact(ch["contact"])
        did = store.create_deal("сайт", None, name=ch["name"] or "Посетитель чата", contact=ch["contact"], phone=phone, email=email,
                                messenger=messenger, want=("Чат с сайта: " + first).strip(), source="site",
                                consent_at=ch["consent_at"] or store_now(), consent_version="chat-2026-11-09")
        store.chat_link_deal(cid, did)
        return did

    @app.route("/api/chat", methods=["GET", "POST", "OPTIONS"])
    def api_chat() -> Any:
        if request.method == "OPTIONS":
            return cors(Response(status=204))
        origin = request.headers.get("Origin", "").rstrip("/")
        if origin and origin not in conf["SITE_ORIGINS"]:
            return cors(jsonify(ok=False, error="origin")), 403
        if not conf["SITE_LEADS"]:
            return cors(jsonify(ok=False, error="off")), 503
        if request.method == "GET":
            sid = request.args.get("sid", "")
            if not SID_RE.match(sid):
                return cors(jsonify(ok=False, error="sid")), 400
            ch = store.chat_by_sid(sid)
            if not ch:
                return cors(jsonify(ok=True, msgs=[]))
            store.chat_seen(int(ch["id"]))
            return cors(jsonify(ok=True, msgs=chat_json(store.chat_msgs(int(ch["id"]), request.args.get("after", 0, type=int)))))
        data = request.get_json(silent=True) or request.form.to_dict()
        if not isinstance(data, dict):
            return cors(jsonify(ok=False, error="format")), 400
        if str(data.get("website") or "").strip():
            return cors(jsonify(ok=True, msgs=[])), 200
        sid = str(data.get("sid") or "")
        text = str(data.get("text") or "").strip()[:1000]
        name = str(data.get("name") or "").strip()[:120]
        contact = str(data.get("contact") or "").strip()[:200]
        consent = data.get("consent") in (True, "1", 1, "true", "on")
        if not SID_RE.match(sid) or not (text or contact):
            return cors(jsonify(ok=False, error="fields")), 400
        ch = store.chat_by_sid(sid)
        if not consent and not (ch and ch["consent_at"]):
            return cors(jsonify(ok=False, error="consent")), 400
        q = _recent(chat_by_ip[ip()], LEAD_WINDOW)
        if len(q) >= CHAT_MAX:
            return cors(jsonify(ok=False, error="rate")), 429
        q.append(time.monotonic())
        if not contact and text and not (ch and ch["contact"]):
            contact = chat_contact_in(text)
        cid, mid, new = store.chat_post(sid, "client", text, name=name, contact=contact,
                                        page=str(data.get("page") or "")[:300], consent=consent)
        if contact and not text:
            store.chat_post(sid, "note", f"Оставил контакт: {name + ', ' if name else ''}{contact}")
        did = chat_to_deal(cid)
        ch = store.chat(cid)
        who_s = ch["name"] or (ch["contact"] if ch["contact"] else "посетитель")
        wp.notify(f"Чат с сайта: {who_s}" + (f" · №{did}" if did else ""), text or f"Оставил контакт: {contact}", f"/chats/{cid}", tag=f"chat-{cid}")
        return cors(jsonify(ok=True, msgs=chat_json(store.chat_msgs(cid, data.get("after", 0) if isinstance(data.get("after"), int) else 0))))

    # ------------------------------------------------------------ Чат — сотрудникам
    @app.route("/chats")
    @login_required
    def chats_view() -> Any:
        return render_template("chats.html", chats=store.chats())

    @app.route("/chats/<int:cid>")
    @login_required
    def chat_view(cid: int) -> Any:
        ch = store.chat(cid)
        if not ch:
            abort(404)
        store.chat_read(cid)
        g.nav_chat = store.chat_unread()
        return render_template("chat.html", ch=ch, msgs=store.chat_msgs(cid), deal=store.deal(ch["deal_id"]) if ch["deal_id"] else None)

    @app.route("/chats/<int:cid>/msgs")
    @login_required
    def chat_msgs_json(cid: int) -> Any:
        ch = store.chat(cid)
        if not ch:
            abort(404)
        rows = store.chat_msgs(cid, request.args.get("after", 0, type=int))
        if rows:
            store.chat_read(cid)
        return jsonify(ok=True, seen=ch["seen_at"][:16], msgs=[{"id": int(r["id"]), "who": r["who"], "author": r["author"], "text": r["text"],
                                                                 "at": fmt_dt(r["created_at"])} for r in rows])

    @app.post("/chats/<int:cid>/reply")
    @login_required
    def chat_reply(cid: int) -> Any:
        ch = store.chat(cid)
        if not ch:
            abort(404)
        text = (request.form.get("text") or "").strip()[:2000]
        if text:
            store.chat_post(ch["sid"], "staff", text, author=g.user["name"])
            # клиент ушёл с сайта, а e-mail оставил — ответ уходит и письмом
            em = EMAIL_RE.search(ch["contact"] or "")
            gone = not ch["seen_at"] or (now() - datetime.fromisoformat(ch["seen_at"])).total_seconds() > 120
            if em and gone:
                dom = conf["SHOP_DOMAIN"] or "nashdekor.ru"
                body = (f"Здравствуйте{', ' + ch['name'] if ch['name'] else ''}!\n\nОтвет на ваш вопрос в чате на сайте «Наш декор»:\n\n{text}\n\n"
                        f"Продолжить переписку — в окне «Чат» на https://{dom} (с того же устройства) или ответом на это письмо.")
                if send_mail(em.group(0), "Ответ в чате — «Наш декор»", "\n".join([body] + mail_signature(g.user["name"])),
                             sender=f"Наш декор <noreply@{dom}>", reply_to=f"zakaz@{dom}"):
                    store.chat_post(ch["sid"], "note", f"Ответ также отправлен на {em.group(0)} (клиент не на сайте)")
            if ch["deal_id"]:
                c = store.c(); store.log(c, f"Ответ в чате: {text[:150]}", who(), deal_id=int(ch["deal_id"])); c.commit()
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify(ok=True)
        return redirect(url_for("chat_view", cid=cid) + "#bottom")

    @app.post("/chats/<int:cid>/deal")
    @login_required
    def chat_deal(cid: int) -> Any:
        ch = store.chat(cid)
        if not ch:
            abort(404)
        if ch["deal_id"]:
            return redirect(url_for("deal_view", did=int(ch["deal_id"])))
        name = (request.form.get("name") or ch["name"] or "Посетитель чата").strip()[:120]
        contact = (request.form.get("contact") or ch["contact"] or "").strip()[:200]
        if contact or name != ch["name"]:
            store.chat_post(ch["sid"], "note", "", name=name, contact=contact)
        if not contact:
            first = " / ".join(r["text"] for r in store.chat_msgs(cid) if r["who"] == "client")[:300]
            did = store.create_deal(who(), int(g.user["id"]), name=name, want=("Чат с сайта: " + first).strip(), source="site",
                                    consent_at=ch["consent_at"] or "", consent_version="chat-2026-11-09")
            store.chat_link_deal(cid, did)
        else:
            did = chat_to_deal(cid)
        flash("Заявка создана из чата.", "ok")
        return redirect(url_for("deal_view", did=did))

    # ------------------------------------------------------------ API: счётчик посещений
    # Сайт присылает отметки «что открыли и нажали» (navigator.sendBeacon, text/plain).
    # IP и браузер в базу не пишутся — только обезличенный номер посетителя на текущие сутки.
    @app.route("/api/hit", methods=["POST", "OPTIONS"])
    def api_hit() -> Any:
        if request.method == "OPTIONS":
            return cors(Response(status=204))
        origin = request.headers.get("Origin", "").rstrip("/")
        ua = request.headers.get("User-Agent", "")[:400]
        if (not origin or origin not in conf["SITE_ORIGINS"] or g.user is not None or is_bot(ua)
                or request.headers.get("DNT") == "1" or request.headers.get("Sec-GPC") == "1" or ip_is_own(ip())):
            return cors(Response(status=204))   # свои (вошли в CRM или со своих IP), боты и «не отслеживать» — не считаем
        if len(hits_by_ip) > 20000:
            hits_by_ip.clear()
        q = _recent(hits_by_ip[ip()], HIT_WINDOW)
        if len(q) >= HIT_MAX:
            return cors(Response(status=204))
        q.append(time.monotonic())
        body = parse_body(request.get_data(cache=False)[:20000])
        if body:
            t = now()
            try:
                visits.add(day=t.date().isoformat(), at=t.strftime("%H:%M"), ip=ip(), ua=ua, body=body)
            except Exception:  # noqa: BLE001 — счётчик не должен ронять CRM
                log.warning("счётчик: отметка не записана")
        return cors(Response(status=204))

    @app.route("/api/health")
    def api_health() -> Any:
        try:
            store.c().execute("SELECT 1").fetchone()
            return jsonify(ok=True)
        except Exception:  # noqa: BLE001
            return jsonify(ok=False), 500

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def err_page(e: Any) -> Any:
        code = getattr(e, "code", 500)
        text = {403: "Нет доступа.", 404: "Не найдено."}.get(code) or getattr(e, "description", "") or "Ошибка."
        return render_template("error.html", code=code, text=text), code

    return app


def rubk(kop: Any) -> str:
    """Копейки → «12 345 ₽» или «12 345,50 ₽»."""
    kop = int(kop or 0)
    r, k = divmod(abs(kop), 100)
    return ("−" if kop < 0 else "") + f"{r:,}".replace(",", " ") + (f",{k:02d}" if k else "") + " ₽"


def store_now() -> str:
    from store import iso_now
    return iso_now()


SW_JS = """/* Наш декор CRM — service worker: пуши и переход в нужную сделку по нажатию */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "Наш декор", {
    body: d.body || "", tag: d.tag || undefined, renotify: !!d.tag, data: { url: d.url || "/" },
    icon: "/static/icon-192.png", badge: "/static/icon-192.png", lang: "ru"
  }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "/", self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
    for (const c of list) {
      if (c.url.startsWith(self.location.origin) && "focus" in c) {
        return c.focus().then(w => (w && "navigate" in w) ? w.navigate(url) : w);
      }
    }
    return self.clients.openWindow(url);
  }));
});
"""


def send_mail(to: str, subject: str, body: str, sender: str = "", reply_to: str = "") -> bool:
    """Письмо через почту своего сервера (Postfix на 127.0.0.1:25). Нет почты — тихо пропускаем.
    sender — адрес нашего домена (для писем клиентам); по умолчанию noreply@ домена получателя (свои уведомления)."""
    if not to:
        return False
    import smtplib
    m = EmailMessage()
    m["To"] = to
    m["From"] = sender or ("noreply@" + to.split("@", 1)[-1])
    if reply_to:
        m["Reply-To"] = reply_to
    m["Subject"] = subject
    m.set_content(body)
    try:
        with smtplib.SMTP("127.0.0.1", 25, timeout=15) as smtp:
            smtp.send_message(m)
        return True
    except Exception:  # noqa: BLE001
        log.warning("не удалось отправить письмо")
        return False


logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
app = create_app() if os.environ.get("CRM_DB") else None
