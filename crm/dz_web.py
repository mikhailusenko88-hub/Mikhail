"""Страницы «База дизайнеров»: список (вкладки Авито / не Авито) и карточка со всеми способами связи."""
from __future__ import annotations

import re
from typing import Any

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

from pochta import fmt_ts
from dz_leads import (CHANNEL_NAMES, FILTERS, LINKS, PRIOS, SOURCE_NAMES, SOURCES, STATUS_NAMES, STATUSES, TEMPLATES,
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
                "DZ_CHANNELS": CHANNEL_NAMES, "DZ_FILTERS": FILTERS, "DZ_LINKS": LINKS, "DZ_PRIOS": PRIOS,
                "dz_due": lambda: dz.due_today() if getattr(g, "user", None) else 0}

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
        return render_template("dz_list.html", rows=rows, grp=grp, f=f, prio=prio, q=q, cnt=dz.counts(),
                               sent_today=dz.sent_today(), limit=dz.daily_limit())

    @app.route("/dz/<int:lid>")
    @login_required
    def dz_card(lid: int) -> Any:
        row = lead_or_404(lid)
        kind, subj, body = dz.mail_draft(row)
        letters = []
        if pochta is not None and row["email"] and g.user["role"] == "admin":
            try:
                letters = [{"id": e["id"], "subject": e.get("subject") or "", "when": fmt_ts(e.get("ts"))}
                           for e in pochta.letters(q=row["email"], limit=20) if (e.get("from") or "").lower() == row["email"]]
            except Exception:  # noqa: BLE001 — почта не обязательна для карточки
                letters = []
        client = store.client(int(row["client_id"])) if row["client_id"] else None
        return render_template("dz_card.html", d=row, links=dz.links(row), mail_kind=kind, mail_subject=subj, mail_body=body,
                               msg=dz.render("msg", row), call_script=dz.render("call", row), touches=dz.touches(lid),
                               letters=letters, client=client, gmail=dz.gmail(row), sent_today=dz.sent_today(),
                               limit=dz.daily_limit(), MSG_CHANNELS=MSG_CHANNELS, mail_from=f"Михаил — Наш декор <mikhail@{dom}>")

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
        ok = send_mail(email, subject, body, sender=f"Михаил — Наш декор <mikhail@{dom}>", reply_to=f"info@{dom}")
        if not ok:
            flash("Письмо не ушло — почтовый сервер не принял. Попробуйте позже или напишите в мессенджер.", "err")
            return back(lid, "mail")
        dz.after_mail(lid, kind if kind in ("m1", "m2", "reply") else "m1", subject, body, who())
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
            store.set_setting("dz_phone", re.sub(r"[^\d+()\- ]", "", request.form.get("phone", ""))[:30])
            try:
                store.set_setting("dz_mail_day", str(max(1, min(60, int(request.form.get("daily", "15"))))))
            except ValueError:
                pass
            flash("Тексты сохранены.", "ok")
            return redirect(url_for("dz_texts"))
        return render_template("dz_texts.html", tpls=[(k, TEMPLATES[k][0], dz.tpl(k)) for k in TEMPLATES], phone=dz.phone(),
                               daily=dz.daily_limit())
