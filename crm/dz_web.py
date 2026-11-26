"""Страницы «База дизайнеров»: список (вкладки Авито / не Авито) и карточка со всеми способами связи."""
from __future__ import annotations

import re
from typing import Any

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

from pochta import fmt_ts
from store import today
from dz_leads import (CHANNEL_NAMES, CLOSED, FILTERS, LINKS, PRIO_ABOUT, PRIO_NAMES, PRIOS, REPLY_RESULTS, SOURCE_NAMES, SOURCES,
                      SENDERS, STATUS_NAMES, STATUSES, TEMPLATES, WORK_KIND, WORK_SECTIONS,
                      TEXT_FIELDS, DzLeads, EMAIL_RE)

MSG_CHANNELS = {"telegram": "Telegram", "whatsapp": "WhatsApp", "max": "MAX", "vk": "VK", "form": "Форма на сайте"}


def register(app: Flask, store: Any, dz: DzLeads, h: dict[str, Any]) -> None:
    @app.template_filter("dz_phone")
    def _dz_phone(v: str) -> str:
        """+78122197770 → +7 812 219-77-70 (как удобно читать и диктовать)."""
        d = re.sub(r"\D", "", v or "")
        if len(d) == 11 and d[0] in "78":
            return f"+7 {d[1:4]} {d[4:7]}-{d[7:9]}-{d[9:11]}"
        return v or ""

    login_required, admin_required, who, send_mail = h["login_required"], h["admin_required"], h["who"], h["send_mail"]
    pochta = h.get("pochta")
    dom = h["shop_domain"]

    @app.context_processor
    def dz_ctx() -> dict[str, Any]:
        return {"DZ_STATUS": STATUS_NAMES, "DZ_STATUSES": STATUSES, "DZ_SOURCES": SOURCES, "DZ_SOURCE_NAMES": SOURCE_NAMES,
                "DZ_CHANNELS": CHANNEL_NAMES, "DZ_FILTERS": FILTERS, "DZ_LINKS": LINKS, "DZ_PRIOS": PRIOS, "DZ_PRIO_NAMES": PRIO_NAMES, "DZ_PRIO_ABOUT": PRIO_ABOUT,
                "DZ_REPLY": REPLY_RESULTS, "DZ_SECTIONS": WORK_SECTIONS,
                "dz_due": lambda: dz.due_today() if getattr(g, "user", None) else 0,
                "dz_todo": lambda upcoming=False: dz.todo(upcoming=upcoming) if getattr(g, "user", None) else [],
                "dz_waiting": lambda: dz.waiting() if getattr(g, "user", None) else 0,
                "dz_todo_tabs": lambda upcoming=False: dz.todo_tabs(upcoming) if getattr(g, "user", None) else []}

    def group_rows(rows: list[Any]) -> list[dict[str, Any]]:
        """Список по разделам работы: сегодня — первый контакт / напомнить / ответили; потом ждём ответа, не писали, закрытые."""
        t = today()
        names = {k: (title, hint) for k, title, hint in WORK_SECTIONS}
        order = [("first", *names["first"]), ("remind", *names["remind"]), ("hot", *names["hot"]),
                 ("wait", "Ждём ответа", "Написали — CRM напомнит, когда придёт срок (дата справа)."),
                 ("later", "Ещё не писали", "Контакт есть или ищем — срок позже или не задан."),
                 ("closed", "Отказ, не по адресу, не писать", "")]
        box: dict[str, list[Any]] = {k: [] for k, *_ in order}
        for r in rows:
            k = WORK_KIND.get(r["status"])
            due = bool(r["next_at"]) and r["next_at"] <= t
            if r["status"] in CLOSED:
                box["closed"].append(r)
            elif k == "hot":
                box["hot"].append(r)
            elif k == "remind":
                box["remind" if due else "wait"].append(r)
            else:
                box["first" if due else "later"].append(r)
        for k in ("first", "remind", "wait"):
            box[k].sort(key=lambda r: (r["next_at"] or "9999", r["prio"], r["code"]))
        tabs = []
        for k, _title, hint in order:
            rs = box[k]
            due = k in ("first", "remind", "hot")
            late = sum(1 for r in rs if due and r["next_at"] and r["next_at"] < t)
            now = sum(1 for r in rs if due and r["next_at"] == t)
            if rs or k in ("first", "remind", "hot"):
                tab = dz.make_tab(k, rs, late, now, hint)
                if k == "later":
                    tab["title"] = "Не писали"
                tabs.append(tab)
        return tabs

    def lead_or_404(lid: int) -> Any:
        row = dz.get(lid)
        if not row:
            abort(404, "Такого дизайнера в базе нет.")
        return row

    def back(lid: int, anchor: str = "") -> Any:
        return redirect(url_for("dz_card", lid=lid) + (f"#{anchor}" if anchor else ""))

    @app.route("/dz")
    @login_required
    def dz_list() -> Any:
        grp = request.args.get("g", "")
        grp = grp if grp in ("avito", "other") else ""
        f = request.args.get("f", "")
        prio = request.args.get("p", "")
        q = (request.args.get("q") or "").strip()[:80]
        rows = dz.list(grp, f, q, prio)
        sections = group_rows(rows) if f in ("", "today") else []
        has_due = any(x["n"] for x in sections if x["key"] in ("first", "remind", "hot"))
        return render_template("dz_list.html", rows=rows, sections=sections, has_due=has_due, grp=grp, f=f, prio=prio, q=q, cnt=dz.counts(), last=dz.last_out(),
                               sent_today=dz.sent_today(), limit=dz.daily_limit())

    @app.route("/dz/<int:lid>")
    @login_required
    def dz_card(lid: int) -> Any:
        row = lead_or_404(lid)
        sender = request.args.get("from", "")
        sender = sender if sender in SENDERS else dz.sender_for(g.user["login"], g.user["name"])
        kind, subj, body = dz.mail_draft(row, sender)
        letters = []
        if pochta is not None and row["email"] and g.user["role"] == "admin":
            try:
                letters = [{"id": e["id"], "subject": e.get("subject") or "", "when": fmt_ts(e.get("ts"))}
                           for e in pochta.letters(q=row["email"], limit=20) if (e.get("from") or "").lower() == row["email"]]
            except Exception:  # noqa: BLE001 — почта не обязательна для карточки
                letters = []
        client = store.client(int(row["client_id"])) if row["client_id"] else None
        return render_template("dz_card.html", d=row, links=dz.links(row), last=dz.last_out(lid).get(lid),
                               prio_about=dz.prio_about(row), mail_kind=kind, mail_subject=subj, mail_body=body,
                               msg=dz.render("msg", row, sender), call_script=dz.render("call", row, sender), touches=dz.touches(lid),
                               no_phone=not dz.phone(sender), me_sender=dz.sender_for(g.user["login"], g.user["name"]),
                               letters=letters, client=client, gmail=dz.gmail(row), sent_today=dz.sent_today(),
                               limit=dz.daily_limit(), MSG_CHANNELS=MSG_CHANNELS, mail_from=dz.sender_addr(sender),
                               sender=sender, SENDERS=SENDERS)

    @app.post("/dz/<int:lid>/edit")
    @login_required
    def dz_edit(lid: int) -> Any:
        lead_or_404(lid)
        f = {k: request.form.get(k, "") for k in TEXT_FIELDS if k in request.form}
        for k in ("prio", "source"):
            if k in request.form:
                f[k] = request.form.get(k, "")
        changed = dz.update(lid, who(), **f)
        flash("Сохранено." if changed else "Ничего не изменилось.", "ok")
        return back(lid, "data")

    @app.post("/dz/<int:lid>/status")
    @login_required
    def dz_status(lid: int) -> Any:
        lead_or_404(lid)
        st = request.form.get("status", "")
        if st not in STATUS_NAMES:
            flash("Выберите статус.", "err")
            return back(lid)
        dz.set_status(lid, st, who(), request.form.get("next_step", ""), request.form.get("next_at", ""),
                      request.form.get("note") if "note" in request.form else None)
        flash("Сохранено.", "ok")
        return back(lid)

    @app.post("/dz/<int:lid>/mail")
    @login_required
    def dz_mail(lid: int) -> Any:
        row = lead_or_404(lid)
        email = (row["email"] or "").strip()
        if not EMAIL_RE.match(email):
            flash("У этого дизайнера нет почты — впишите её в «Данные».", "err")
            return back(lid, "mail")
        subject = re.sub(r"\s+", " ", request.form.get("subject") or "").strip()[:150]
        body = (request.form.get("text") or "").replace("\r\n", "\n").strip()[:8000]
        kind = request.form.get("kind", "m1")
        if not subject or not body:
            flash("Тема и текст письма не должны быть пустыми.", "err")
            return back(lid, "mail")
        if dz.sent_today() >= dz.daily_limit():
            flash(f"Сегодня из базы уже отправлено {dz.sent_today()} писем — остальное завтра (новый домен: малыми партиями, "
                  "чтобы не попасть в спам).", "err")
            return back(lid, "mail")
        sender = request.form.get("sender", "")
        sender = sender if sender in SENDERS else dz.sender_for(g.user["login"], g.user["name"])
        ok = send_mail(email, subject, body, sender=dz.sender_addr(sender), reply_to=f"info@{dom}")
        if not ok:
            flash("Письмо не ушло — почтовый сервер не принял. Попробуйте позже или напишите в мессенджер.", "err")
            return back(lid, "mail")
        dz.after_mail(lid, kind if kind in ("m1", "m2", "reply") else "m1", subject, body, who(),
                      sender=SENDERS[sender]["box"] + "@" + dom)
        flash(f"Письмо отправлено на {email}. Ответ придёт в «Почту» (info@). Следующий шаг поставлен.", "ok")
        return back(lid)

    @app.post("/dz/<int:lid>/message")
    @login_required
    def dz_message(lid: int) -> Any:
        lead_or_404(lid)
        ch = request.form.get("channel", "")
        if ch not in MSG_CHANNELS:
            flash("Выберите, куда написали.", "err")
            return back(lid, "msg")
        dz.after_message(lid, ch, (request.form.get("text") or "").strip()[:4000], who())
        flash(f"Записано: написали в {MSG_CHANNELS[ch]}.", "ok")
        return back(lid)

    @app.post("/dz/<int:lid>/reply")
    @login_required
    def dz_reply(lid: int) -> Any:
        lead_or_404(lid)
        res, ch = request.form.get("result", ""), request.form.get("channel", "")
        if res not in REPLY_RESULTS:
            flash("Выберите, что ответили.", "err")
            return back(lid)
        label = dz.after_reply(lid, ch if ch in CHANNEL_NAMES else "note", res, request.form.get("comment", ""), who())
        flash(f"Записано: ответили — {label.lower()}.", "ok")
        return back(lid)

    @app.post("/dz/<int:lid>/call")
    @login_required
    def dz_call(lid: int) -> Any:
        lead_or_404(lid)
        res = request.form.get("result", "")
        if res not in ("noanswer", "contact", "interest", "refused", "wrong", "later"):
            flash("Выберите итог звонка.", "err")
            return back(lid, "call")
        text = dz.after_call(lid, res, request.form.get("comment", ""), who(),
                             **{k: request.form.get(k, "") for k in ("email", "telegram", "whatsapp", "phone2", "person")})
        flash(f"Записано: {text}.", "ok")
        return back(lid)

    @app.post("/dz/<int:lid>/note")
    @login_required
    def dz_note(lid: int) -> Any:
        lead_or_404(lid)
        t = (request.form.get("text") or "").strip()
        if t:
            dz.touch(lid, "note", t[:2000], who())
        return back(lid, "hist")

    @app.post("/dz/<int:lid>/client")
    @login_required
    def dz_client(lid: int) -> Any:
        lead_or_404(lid)
        cid = dz.to_client(lid, who())
        if not cid:
            abort(404)
        flash("Дизайнер в «Клиентах». Укажите налоговый статус (ИП / самозанятый), если будет вознаграждение.", "ok")
        return redirect(url_for("client_view", cid=cid))

    @app.post("/dz/new")
    @login_required
    def dz_new() -> Any:
        try:
            lid = dz.add(who(), request.form.get("name", ""), request.form.get("source", "other"),
                         **{k: request.form.get(k, "") for k in ("phone", "email", "telegram", "site", "area", "about")})
        except ValueError as e:
            flash(str(e).capitalize() + ".", "err")
            return redirect(url_for("dz_list"))
        flash("Добавлен в базу.", "ok")
        return redirect(url_for("dz_card", lid=lid))

    @app.route("/dz/texts", methods=["GET", "POST"])
    @admin_required
    def dz_texts() -> Any:
        if request.method == "POST":
            for k in TEMPLATES:
                if k in request.form:
                    dz.set_tpl(k, request.form.get(k, ""))
            store.set_setting(dz.phone_key("mikhail"), re.sub(r"[^\d+()\- ]", "", request.form.get("phone", ""))[:30].strip())
            store.set_setting("dz_phone_yulia", re.sub(r"[^\d+()\- ]", "", request.form.get("phone_yulia", ""))[:30].strip())
            try:
                store.set_setting("dz_mail_day", str(max(1, min(60, int(request.form.get("daily", "15"))))))
            except ValueError:
                pass
            flash("Тексты сохранены.", "ok")
            return redirect(url_for("dz_texts"))
        return render_template("dz_texts.html", tpls=[(k, TEMPLATES[k][0], dz.tpl(k)) for k in TEMPLATES], phone=dz.phone("mikhail"),
                               phone_yulia=dz.s.setting("dz_phone_yulia", ""),
                               daily=dz.daily_limit())
