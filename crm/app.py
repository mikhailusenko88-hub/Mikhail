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
import logging
import os
import re
import secrets
import sys
import time
from collections import defaultdict, deque
from email.message import EmailMessage
from typing import Any

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from store import (KIND_NAMES, KIND_TITLES, KINDS, OPEN_STAGES, ROLE_NAMES, ROLES, SOURCE_NAMES, SOURCES,
                   STAGE_NAMES, STAGES, Catalog, Store, fmt_day, fmt_dt, now, rub, today)
from visits import Visits, is_bot, parse_body

log = logging.getLogger("crm")

LOGIN_WINDOW = 15 * 60
LOGIN_MAX_FAILS = 10
LEAD_WINDOW = 10 * 60
LEAD_MAX = 5
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
    app.extensions["visits"] = visits
    hits_by_ip: dict[str, deque[float]] = defaultdict(deque)
    fails: dict[str, deque[float]] = defaultdict(deque)
    leads_by_ip: dict[str, deque[float]] = defaultdict(deque)

    def ip() -> str:
        return request.remote_addr or "?"

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
                "nav_new": getattr(g, "nav_new", 0)}

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
            if len(q) >= LOGIN_MAX_FAILS:
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
                               vb=visits.brief(t))

    # ------------------------------------------------------------ Воронка и сделки
    @app.route("/board")
    @login_required
    def board() -> Any:
        q = (request.args.get("q") or "").strip()
        show_closed = request.args.get("all") == "1"
        deals = store.deals(q=q, limit=1000)
        cols = []
        for st, name in STAGES:
            ds = [d for d in deals if d["stage"] == st]
            if not show_closed and st in ("shipped", "lost"):
                ds = ds[:15]
            cols.append((st, name, ds, sum(Store.total(d["gross"], d["discount"]) for d in ds)))
        return render_template("board.html", cols=cols, q=q, show_closed=show_closed)

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
                               stock=stock, tasks=store.tasks(deal_id=did, open_only=False),
                               events=store.events(deal_id=did), bot=bot, msgs=msgs,
                               catalog=store.catalog.all(), other=store.deals(client_id=d["client_id"], limit=20))

    @app.post("/deals/<int:did>/stage")
    @login_required
    def deal_stage(did: int) -> Any:
        st = request.form.get("stage", "")
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
                                          roles=("manager", "shipping"))
        return redirect(safe_next(request.form.get("back")) if request.form.get("back") else url_for("deal_view", did=did))

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
            got = store.add_line(did, art, int(qty) if qty.strip().isdigit() else 0, who())
            if got and not store.catalog.get(got):
                flash(f"Артикула {got} нет в каталоге сайта — цену впишите сами.", "err")
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
                               conf=conf, bot=bool(store._bot()))

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
    def cors(resp: Response) -> Response:
        origin = request.headers.get("Origin", "").rstrip("/")
        if origin and origin in conf["SITE_ORIGINS"]:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Max-Age"] = "600"
        resp.headers["Cache-Control"] = "no-store"
        return resp

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
        did = store.create_deal("сайт", None, name=name, contact=contact, kind=who_kind, want=msg, source="site",
                                calc=calc, consent_at=str(data.get("consentAt") or "")[:40] or store_now(),
                                consent_version=str(data.get("consentVersion") or "")[:40])
        txt = f"Новая заявка с сайта №{did}: {name}, {contact}" + (f"\n{msg}" if msg else "")
        store.notify_team(txt)
        send_mail(conf["NOTIFY_EMAIL"], f"Заявка с сайта №{did}", txt + f"\n\nCRM: https://crm.{conf['SHOP_DOMAIN']}/deals/{did}"
                  if conf["SHOP_DOMAIN"] else txt)
        return cors(jsonify(ok=True, id=did)), 200

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
                or request.headers.get("DNT") == "1" or request.headers.get("Sec-GPC") == "1"):
            return cors(Response(status=204))   # свои (вошли в CRM), боты и «не отслеживать» — не считаем
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


def store_now() -> str:
    from store import iso_now
    return iso_now()


def send_mail(to: str, subject: str, body: str) -> None:
    """Письмо через почту своего сервера (Postfix на 127.0.0.1:25). Нет почты — тихо пропускаем."""
    if not to:
        return
    import smtplib
    m = EmailMessage()
    m["To"] = to
    m["From"] = "noreply@" + to.split("@", 1)[-1]
    m["Subject"] = subject
    m.set_content(body)
    try:
        with smtplib.SMTP("127.0.0.1", 25, timeout=15) as smtp:
            smtp.send_message(m)
    except Exception:  # noqa: BLE001
        log.warning("не удалось отправить письмо-уведомление")


logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
app = create_app() if os.environ.get("CRM_DB") else None
