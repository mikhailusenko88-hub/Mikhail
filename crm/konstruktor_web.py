"""Страницы «Конструктора» (Ещё → Конструктор) и приём заявок из других сервисов (/api/in/<ключ>). См. konstruktor.py."""

from __future__ import annotations

import json
import os
import re
import secrets
from typing import Any

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, url_for

from konstruktor import (ENTITIES, EVENTS, FIELD_TYPES, MAIL_TEMPLATES, PLACEHOLDERS, Konstruktor, xlsx)

DEFAULT_MAIL = {
    "calc": ("Расчёт №{номер} — реечные панели и декор, «Наш декор»",
             "Здравствуйте, {имя}!\n\n{заметка}\n\nРасчёт №{номер} от «Наш декор»:\n\n{состав}\n\n{получение}\n\n{ссылка_на_оплату}\n\n"
             "Цены без НДС. Доставка по Санкт-Петербургу и Ленобласти рассчитывается отдельно, самовывоз со склада — бесплатно.\n"
             "Расчёт действует 7 дней; наличие и срок поставки подтвердим при заказе.\n\nЧто дальше:\n"
             "• Если расчёт подходит — ответьте на это письмо или напишите нам: пришлём ссылку на оплату через СБП (компаниям — счёт) и согласуем доставку.\n"
             "• Нужно изменить количество, цвет, добавить плинтус или карниз — напишите, пересчитаем.\n"
             "• Если ответа не будет, через пару дней мы сами напишем или позвоним, чтобы узнать решение.\n\n{подпись}"),
    "followup1": ("Расчёт №{номер} — подошёл ли он вам? «Наш декор»",
                  "Здравствуйте, {имя}!\n\n{дата_расчёта} мы отправили вам расчёт №{номер} на {итого} ({позиции}).\n"
                  "Подскажите, пожалуйста, подходит ли он?\n\n"
                  "• Если да — ответьте на это письмо или напишите нам, и мы пришлём ссылку на оплату через СБП (компаниям — счёт) и согласуем доставку.\n"
                  "• Если нужно что-то изменить — напишите, пересчитаем.\n• Если планы изменились — тоже напишите, мы не будем беспокоить.\n\n{подпись}"),
    "followup2": ("Расчёт №{номер} действует до {действует_до} — «Наш декор»",
                  "Здравствуйте, {имя}!\n\nНапоминаем: расчёт №{номер} на {итого} ({позиции}) действует до {действует_до}; после этого цены и наличие могут измениться.\n"
                  "Чтобы зафиксировать сумму и забронировать товар, ответьте на это письмо или напишите нам — пришлём ссылку на оплату и согласуем доставку.\n\n"
                  "Это последнее напоминание — больше писать не будем.\n\n{подпись}"),
}
QUICK_EXAMPLES = [
    ("Реквизиты для оплаты по счёту", "Здравствуйте, {имя}! Счёт по заявке №{номер} на {итого} отправим на почту. Если нужны реквизиты сразу — напишите, пришлём."),
    ("Товар пришёл на склад", "Здравствуйте, {имя}! Ваш заказ №{номер} пришёл на склад. Когда удобно принять доставку или забрать самовывозом?"),
    ("Просьба об отзыве", "Здравствуйте, {имя}! Спасибо за покупку в «Наш декор». Если не трудно — пришлите пару слов и фото стены: опубликуем на сайте (имя можно сократить)."),
]
FIELD_PRESETS = [
    ("deal", "Откуда узнал", "select", "Авито\nЯндекс\nGoogle\nСоветовали знакомые\nДизайнер\nВывеска/шоурум\nДругое"),
    ("deal", "Объект / адрес монтажа", "text", ""),
    ("deal", "Дата монтажа", "date", ""),
    ("deal", "Цвет покраски", "text", ""),
    ("deal", "Ссылка на проект дизайнера", "link", ""),
    ("client", "День рождения", "date", ""),
    ("client", "Постоянный клиент", "check", ""),
]
GSHEET_SCRIPT = """function doPost(e) {
  var d = JSON.parse(e.postData.contents);
  var deal = d.deal || {}, cl = d.client || {};
  SpreadsheetApp.getActiveSheet().appendRow([
    new Date(), d.event_name, deal.id, cl.name, cl.phone || '', cl.email || '',
    deal.stage_name, deal.total_rub, deal.want, deal.url]);
  return ContentService.createTextOutput('ok');
}"""


def register(app: Flask, store: Any, k: Konstruktor, h: dict[str, Any]) -> None:
    admin_required, login_required, who = h["admin_required"], h["login_required"], h["who"]
    conf, send_mail, letter_ctx = h["conf"], h["send_mail"], h["letter_ctx"]
    imp_dir = os.path.join(os.path.dirname(os.path.abspath(conf["CRM_DB"])), "k-import")

    def base_url() -> str:
        dom = conf.get("SHOP_DOMAIN") or "nashdekor.ru"
        return f"https://crm.{dom}"

    def done(msg: str, err: str, back: str) -> Any:
        flash(err if err else msg, "err" if err else "ok")
        return redirect(back)

    # ------------------------------------------------------------------ свои поля
    @app.route("/k")
    @admin_required
    def k_fields_view() -> Any:
        have = {(f["entity"], f["label"].lower()) for f in k.fields()}
        presets = [p for p in FIELD_PRESETS if (p[0], p[1].lower()) not in have]
        return render_template("k_fields.html", fields=k.fields(), ENTITIES=ENTITIES, FIELD_TYPES=FIELD_TYPES,
                               TYPE_NAMES=dict(FIELD_TYPES), ENTITY_NAMES=dict(ENTITIES), presets=presets, tab="fields")

    @app.post("/k/fields/add")
    @admin_required
    def k_field_add() -> Any:
        r = k.field_add(request.form.get("entity", ""), request.form.get("label", ""), request.form.get("type", ""),
                        request.form.get("options", ""))
        return done("Поле добавлено — оно уже есть в карточках.", r if isinstance(r, str) else "", url_for("k_fields_view"))

    @app.post("/k/fields/presets")
    @admin_required
    def k_field_presets() -> Any:
        chosen = set(request.form.getlist("p"))
        n = 0
        for ent, label, t, opts in FIELD_PRESETS:
            if f"{ent}:{label}" in chosen and isinstance(k.field_add(ent, label, t, opts), int):
                n += 1
        return done(f"Добавлено полей: {n}.", "" if n else "Отметьте поля, которые добавить.", url_for("k_fields_view"))

    @app.post("/k/fields/<int:fid>")
    @admin_required
    def k_field_edit(fid: int) -> Any:
        act = request.form.get("action", "save")
        if act in ("up", "down"):
            k.field_move(fid, act == "up")
            return redirect(url_for("k_fields_view"))
        if act == "delete":
            if request.form.get("confirm") != "1":
                return done("", "Чтобы удалить поле со всеми значениями, отметьте «Да, удалить».", url_for("k_fields_view"))
            k.field_delete(fid)
            return done("Поле удалено.", "", url_for("k_fields_view"))
        err = k.field_update(fid, request.form.get("label", ""), request.form.get("options", ""), request.form.get("active") == "1")
        return done("Сохранено.", err, url_for("k_fields_view"))

    @app.post("/k/values/<entity>/<int:eid>")
    @login_required
    def k_values_save(entity: str, eid: int) -> Any:
        if entity not in dict(ENTITIES):
            abort(404)
        if (entity == "deal" and not store.deal(eid)) or (entity == "client" and not store.client(eid)):
            abort(404)
        errs = k.save_values(entity, eid, dict(request.form), who())
        flash("; ".join(errs) if errs else "Сохранено.", "err" if errs else "ok")
        return redirect((url_for("deal_view", did=eid) if entity == "deal" else url_for("client_view", cid=eid)) + "#kfields")

    # ------------------------------------------------------------------ интеграции
    @app.route("/k/integrations")
    @admin_required
    def k_integrations_view() -> Any:
        return render_template("k_integrations.html", hooks=k.hooks(), inbound=k.inbound(), EVENTS=EVENTS,
                               EVENT_NAMES=dict(EVENTS), base=base_url(), GSHEET_SCRIPT=GSHEET_SCRIPT,
                               edit=next((x for x in k.hooks() if str(x["id"]) == request.args.get("edit", "")), None),
                               queued=store.c().execute("SELECT COUNT(*) FROM k_queue").fetchone()[0], tab="integrations")

    @app.post("/k/hooks/save")
    @admin_required
    def k_hook_save() -> Any:
        f = request.form
        hid = int(f["id"]) if (f.get("id") or "").isdigit() else None
        err = k.hook_save(hid, f.get("name", ""), f.get("kind", "url"), f.get("url", ""), f.get("chat", ""), f.getlist("events"),
                          f.get("pd") == "1", f.get("active", "1") == "1")
        return done("Интеграция сохранена. Проверьте её кнопкой «Проверить».", err,
                    url_for("k_integrations_view") + ("" if not err else (f"?edit={hid}" if hid else "#new")))

    @app.post("/k/hooks/<int:hid>")
    @admin_required
    def k_hook_act(hid: int) -> Any:
        act = request.form.get("action", "")
        if act == "test":
            ok, why = k.hook_test(hid, base_url())
            return done(f"Связь есть: {why}.", "" if ok else f"Не получилось: {why}. Проверьте адрес или токен.", url_for("k_integrations_view"))
        if act == "delete":
            k.hook_delete(hid)
            return done("Интеграция удалена.", "", url_for("k_integrations_view"))
        abort(400)

    @app.post("/k/inbound")
    @admin_required
    def k_inbound_act() -> Any:
        f = request.form
        if f.get("action") == "add":
            return done("Ссылка для приёма заявок создана.", k.inbound_add(f.get("name", "")), url_for("k_integrations_view") + "#inbound")
        iid = int(f.get("id", "0") or 0)
        act = f.get("action")
        if act == "delete" and f.get("confirm") != "1":
            return done("", "Отметьте «Да, удалить».", url_for("k_integrations_view") + "#inbound")
        k.inbound_set(iid, active={"on": True, "off": False}.get(act or ""), new_token=act == "token", delete=act == "delete")
        return done({"token": "Ссылка заменена — старая больше не работает.", "delete": "Удалено."}.get(act or "", "Сохранено."), "",
                    url_for("k_integrations_view") + "#inbound")

    @app.route("/api/in/<token>", methods=["POST"])
    def k_inbound_api(token: str) -> Any:
        data: dict[str, Any] = {}
        if request.is_json:
            js = request.get_json(silent=True)
            data = js if isinstance(js, dict) else {}
        else:
            data = {key: v for key, v in request.form.items()}
        data = {str(key)[:40]: (v if isinstance(v, (str, int, float)) else json.dumps(v, ensure_ascii=False))
                for key, v in list(data.items())[:40]}
        did, err = k.inbound_take(token, data)
        if err:
            return jsonify({"ok": False, "error": err}), 404 if err == "нет такой ссылки" else (429 if "много" in err else 400)
        return jsonify({"ok": True, "deal": did})

    # ------------------------------------------------------------------ шаблоны
    @app.route("/k/templates")
    @admin_required
    def k_templates_view() -> Any:
        mails = [(key, title, k.template(key)) for key, title in MAIL_TEMPLATES]
        return render_template("k_templates.html", mails=mails, quick=k.templates("quick"), PLACEHOLDERS=PLACEHOLDERS,
                               QUICK_EXAMPLES=QUICK_EXAMPLES, tab="templates")

    @app.route("/k/templates/<key>", methods=["GET", "POST"])
    @admin_required
    def k_template_edit(key: str) -> Any:
        is_mail = key in dict(MAIL_TEMPLATES)
        if not is_mail and key != "new" and not (k.template(key) or None):
            abort(404)
        cur = k.template(key) if key != "new" else None
        if request.method == "POST":
            f = request.form
            if f.get("action") == "reset":
                k.template_delete(key)
                return done("Вернули текст как был." if is_mail else "Быстрый ответ удалён.", "", url_for("k_templates_view"))
            err = k.template_save("" if key == "new" else key, "mail" if is_mail else "quick", f.get("title", ""), f.get("subject", ""),
                                  f.get("body", ""), who())
            if not err:
                return done("Сохранено. Новые письма пойдут с этим текстом." if is_mail else "Быстрый ответ сохранён.", "", url_for("k_templates_view"))
            flash(err, "err")
            cur = {"title": f.get("title", ""), "subject": f.get("subject", ""), "body": f.get("body", "")}
        if not cur and is_mail:
            subj, body = DEFAULT_MAIL[key]
            cur = {"title": dict(MAIL_TEMPLATES)[key], "subject": subj, "body": body}
        if not cur and key == "new":
            ex = int(request.args.get("ex", "-1") or -1)
            cur = {"title": QUICK_EXAMPLES[ex][0], "subject": "", "body": QUICK_EXAMPLES[ex][1]} if 0 <= ex < len(QUICK_EXAMPLES) else \
                {"title": "", "subject": "", "body": ""}
        return render_template("k_template.html", key=key, is_mail=is_mail, cur=cur, saved=bool(k.template(key)) if key != "new" else False,
                               title=dict(MAIL_TEMPLATES).get(key, "Быстрый ответ"), PLACEHOLDERS=PLACEHOLDERS, tab="templates")

    @app.route("/k/quick/<int:did>", methods=["GET", "POST"])
    @login_required
    def k_quick(did: int) -> Any:
        d = store.deal(did)
        t = k.template(request.values.get("t", ""))
        if not d or not t or t["kind"] != "quick":
            abort(404)
        text = k.render(t["body"], letter_ctx(d, store.lines(did), who()))
        if request.method == "POST":
            body = (request.form.get("body") or text).replace("\r\n", "\n").strip()[:8000]
            email = (d["email"] or "").strip()
            if "@" not in email:
                flash("У клиента нет e-mail — скопируйте текст и отправьте в мессенджер.", "err")
            else:
                dom = conf.get("SHOP_DOMAIN") or "nashdekor.ru"
                if send_mail(email, f"{t['title']} — заявка №{did}, «Наш декор»", body, sender=f"Наш декор <noreply@{dom}>", reply_to=f"zakaz@{dom}"):
                    c = store.c(); store.log(c, f"Письмо «{t['title']}» отправлено на {email}", who(), deal_id=did, client_id=d["client_id"]); c.commit()
                    flash(f"Отправлено на {email}.", "ok")
                    return redirect(url_for("deal_view", did=did))
                flash("Почта не ответила — попробуйте ещё раз позже.", "err")
        return render_template("k_quick.html", d=d, t=t, text=text, tab="")

    # ------------------------------------------------------------------ автоправила и ссылки
    @app.route("/k/rules")
    @admin_required
    def k_rules_view() -> Any:
        from store import STAGE_NAMES, STAGES
        return render_template("k_rules.html", rules=k.rules(), links=k.links(), STAGES=[s for s in STAGES if s[0] != "lost"],
                               STAGE_NAMES=STAGE_NAMES, tab="rules")

    @app.post("/k/rules")
    @admin_required
    def k_rules_act() -> Any:
        f = request.form
        act = f.get("action")
        if act == "add":
            return done("Автоправило добавлено — сработает на следующих заявках.", k.rule_add(f.get("stage", ""), f.get("title", ""), f.get("days", "0")),
                        url_for("k_rules_view"))
        rid = int(f.get("id", "0") or 0)
        k.rule_set(rid, active={"on": True, "off": False}.get(act or ""), delete=act == "delete")
        return redirect(url_for("k_rules_view"))

    @app.post("/k/links")
    @admin_required
    def k_links_act() -> Any:
        f = request.form
        if f.get("action") == "add":
            return done("Ссылка добавлена в меню «Ещё».", k.link_add(f.get("title", ""), f.get("url", "")), url_for("k_rules_view") + "#links")
        k.link_delete(int(f.get("id", "0") or 0))
        return redirect(url_for("k_rules_view") + "#links")

    # ------------------------------------------------------------------ Excel
    def sheet_clients() -> list[list[Any]]:
        fl = k.fields("client", active_only=True)
        rows: list[list[Any]] = [["ID", "Имя", "Телефон", "E-mail", "Мессенджер", "Тип", "Компания", "ИНН", "Заметка", "Создан"] + [f["label"] for f in fl]]
        from store import KIND_NAMES
        for c in store.c().execute("SELECT * FROM clients ORDER BY id").fetchall():
            v = k.values("client", int(c["id"]))
            rows.append([c["id"], c["name"], c["phone"], c["email"], c["messenger"], KIND_NAMES.get(c["kind"], c["kind"]), c["company"],
                         c["inn"], c["note"], (c["created_at"] or "")[:10]] + [v.get(int(f["id"]), "") for f in fl])
        return rows

    def sheet_deals() -> list[list[Any]]:
        from store import SOURCE_NAMES, STAGE_NAMES
        fl = k.fields("deal", active_only=True)
        rows: list[list[Any]] = [["№", "Создана", "Этап", "Источник", "Клиент", "Телефон", "E-mail", "Компания", "Что нужно", "Позиции",
                                  "Сумма без скидки, ₽", "Скидка, %", "Итого, ₽", "Оплачено, ₽", "Адрес"] + [f["label"] for f in fl]]
        for d in store.c().execute("SELECT d.*, cl.name AS client_name, cl.phone, cl.email, cl.company FROM deals d "
                                   "JOIN clients cl ON cl.id=d.client_id ORDER BY d.id").fetchall():
            lines = store.lines(int(d["id"]))
            gross, total = store.deal_total(int(d["id"]))
            paid = store.c().execute("SELECT COALESCE(SUM(amount-refunded),0) FROM payments WHERE deal_id=? AND paid_at!=''",
                                     (d["id"],)).fetchone()[0]
            v = k.values("deal", int(d["id"]))
            rows.append([d["id"], (d["created_at"] or "")[:10], STAGE_NAMES.get(d["stage"], d["stage"]), SOURCE_NAMES.get(d["source"], d["source"]),
                         d["client_name"], d["phone"], d["email"], d["company"], d["want"],
                         "; ".join(f"{ln['article']} × {ln['qty']}" for ln in lines), gross, d["discount"], total, int(paid) // 100,
                         d["address"]] + [v.get(int(f["id"]), "") for f in fl])
        return rows

    def sheet_stock() -> list[list[Any]]:
        rows: list[list[Any]] = [["Артикул", "Название", "Размер", "Шт в коробке", "Остаток, шт", "Отложено, шт", "Цена на сайте, ₽", "Своя цена, ₽"]]
        for x in store.stock_rows():
            rows.append([x["article"], x["name"], x["size"], x["per_box"] or "", x["qty"], x["reserved"], x["site_price"] or "",
                         x["price"] if x["own_price"] else ""])
        return rows

    def sheet_payments() -> list[list[Any]]:
        rows: list[list[Any]] = [["ID", "Заявка №", "Вид", "Сумма, ₽", "Возвращено, ₽", "Статус", "Оплачено", "Способ", "Создано", "Кто"]]
        kinds = {"link": "ссылка Точки", "invoice": "по счёту", "manual": "вручную"}
        for p in store.c().execute("SELECT * FROM payments ORDER BY id").fetchall():
            rows.append([p["id"], p["deal_id"], kinds.get(p["kind"], p["kind"]), int(p["amount"]) // 100, int(p["refunded"]) // 100,
                         p["status"], (p["paid_at"] or "")[:16].replace("T", " "), {"card": "картой", "sbp": "СБП"}.get(p["pay_type"], p["pay_type"]),
                         (p["created_at"] or "")[:16].replace("T", " "), p["created_by"]])
        return rows

    EXPORTS = {"clients": ("Клиенты", sheet_clients), "deals": ("Заявки", sheet_deals), "stock": ("Склад", sheet_stock),
               "payments": ("Оплаты", sheet_payments)}

    @app.route("/k/excel")
    @admin_required
    def k_excel_view() -> Any:
        return render_template("k_excel.html", EXPORTS=EXPORTS, preview=None, tab="excel",
                               client_fields=[f["label"] for f in k.fields("client", active_only=True)])

    @app.route("/k/export/<what>.xlsx")
    @admin_required
    def k_export(what: str) -> Any:
        from store import today
        if what == "all":
            sheets = [(title, fn()) for title, fn in EXPORTS.values()]
        elif what in EXPORTS:
            sheets = [(EXPORTS[what][0], EXPORTS[what][1]())]
        else:
            abort(404)
        c = store.c(); store.log(c, f"Выгрузка в Excel: {what}", who()); c.commit()
        name = {"all": "vse"}.get(what, what)
        return Response(xlsx(sheets), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="nashdekor-{name}-{today()}.xlsx"',
                                 "Cache-Control": "no-store"})

    def norm(s: Any) -> str:
        return re.sub(r"[\s.:,;()_-]+", "", str(s or "").lower().replace("ё", "е"))

    def parse_import(kind: str, data: bytes) -> tuple[list[dict[str, Any]], list[str]]:
        from buh import read_xlsx
        from store import KIND_NAMES, norm_phone
        try:
            sheets = read_xlsx(data)
        except Exception:  # noqa: BLE001
            return [], ["не получилось прочитать файл — нужен .xlsx (в Numbers: Файл → Экспортировать → Excel)"]
        rows = next((r for _, r in sheets if r and any(str(x).strip() for x in r[0])), [])
        if not rows:
            return [], ["в файле нет данных"]
        head = [norm(x) for x in rows[0]]

        def col(*names: str) -> int:
            for n in names:
                if norm(n) in head:
                    return head.index(norm(n))
            return -1

        out: list[dict[str, Any]] = []
        errs: list[str] = []
        if kind == "clients":
            ci = {key: col(*names) for key, names in {"id": ("ID",), "name": ("Имя", "Клиент", "ФИО"), "phone": ("Телефон",),
                                                       "email": ("E-mail", "Email", "Почта"), "messenger": ("Мессенджер",),
                                                       "kind": ("Тип",), "company": ("Компания",), "inn": ("ИНН",), "note": ("Заметка",)}.items()}
            if ci["name"] < 0 and ci["phone"] < 0 and ci["email"] < 0:
                return [], ["нет столбцов «Имя», «Телефон» или «E-mail» в первой строке"]
            kinds = {norm(v): kk for kk, v in KIND_NAMES.items()}
            cfs = [(f, head.index(norm(f["label"]))) for f in k.fields("client", active_only=True) if norm(f["label"]) in head]
            for n, r in enumerate(rows[1:], 2):
                g = lambda key: str(r[ci[key]]).strip() if 0 <= ci[key] < len(r) and r[ci[key]] is not None else ""  # noqa: E731
                rec = {key: g(key) for key in ci}
                if not any(rec.values()):
                    continue
                if rec["phone"]:
                    rec["phone"] = norm_phone(rec["phone"]) or rec["phone"]
                if rec["kind"]:
                    rec["kind"] = kinds.get(norm(rec["kind"]), "")
                rec["custom"] = {}
                for f, i in cfs:
                    v, err = Konstruktor.clean_value(f, r[i] if i < len(r) else "")
                    if err:
                        errs.append(f"строка {n}: {err}")
                    elif v:
                        rec["custom"][str(f["id"])] = v
                ex = None
                if rec["id"].isdigit():
                    ex = store.client(int(rec["id"]))
                if not ex and rec["phone"]:
                    ex = store.c().execute("SELECT * FROM clients WHERE phone=? ORDER BY id LIMIT 1", (rec["phone"],)).fetchone()
                if not ex and "@" in rec["email"]:
                    ex = store.c().execute("SELECT * FROM clients WHERE lower(email)=lower(?) ORDER BY id LIMIT 1", (rec["email"],)).fetchone()
                if not ex and not (rec["name"] and (rec["phone"] or rec["email"] or rec["messenger"])):
                    errs.append(f"строка {n}: новому клиенту нужны имя и телефон, e-mail или мессенджер")
                    continue
                rec["row"], rec["match"] = n, int(ex["id"]) if ex else 0
                rec["match_name"] = ex["name"] if ex else ""
                out.append(rec)
        else:
            ai, qi, pi = col("Артикул"), col("Остаток", "Остаток, шт", "Количество", "Кол-во"), col("Своя цена", "Своя цена, ₽", "Цена", "Цена, ₽")
            if ai < 0 or (qi < 0 and pi < 0):
                return [], ["нужны столбцы «Артикул» и «Остаток» и/или «Своя цена» в первой строке"]
            for n, r in enumerate(rows[1:], 2):
                a = str(r[ai]).strip() if ai < len(r) and r[ai] is not None else ""
                if not a:
                    continue
                p = store.catalog.get(a)
                if not p:
                    errs.append(f"строка {n}: артикула {a} нет в каталоге")
                    continue

                def num(i: int) -> Any:
                    if i < 0 or i >= len(r) or r[i] in (None, ""):
                        return None
                    try:
                        return int(round(float(str(r[i]).replace(" ", "").replace(" ", "").replace(",", "."))))
                    except ValueError:
                        errs.append(f"строка {n}: «{r[i]}» — не число")
                        return None
                q, pr = num(qi), num(pi)
                if q is None and pr is None:
                    continue
                if (q is not None and not 0 <= q <= 1_000_000) or (pr is not None and not 0 <= pr <= 10_000_000):
                    errs.append(f"строка {n}: {a} — число вне разумных пределов")
                    continue
                out.append({"row": n, "article": p.article, "name": p.name, "qty": q, "price": pr})
        return out, errs[:50]

    @app.post("/k/import")
    @admin_required
    def k_import() -> Any:
        kind = request.form.get("kind", "")
        if kind not in ("clients", "stock"):
            abort(400)
        f = request.files.get("file")
        data = f.read(2 * 1024 * 1024 + 1) if f and f.filename else b""
        if not data:
            return done("", "Выберите файл .xlsx.", url_for("k_excel_view"))
        if len(data) > 2 * 1024 * 1024:
            return done("", "Файл больше 2 МБ.", url_for("k_excel_view"))
        recs, errs = parse_import(kind, data)
        token = ""
        if recs:
            os.makedirs(imp_dir, exist_ok=True)
            token = secrets.token_urlsafe(12)
            with open(os.path.join(imp_dir, token + ".json"), "w", encoding="utf-8") as fh:
                json.dump({"kind": kind, "recs": recs, "by": who()}, fh, ensure_ascii=False)
        return render_template("k_excel.html", EXPORTS=EXPORTS, tab="excel", preview={"kind": kind, "recs": recs, "errs": errs, "token": token},
                               client_fields=[f["label"] for f in k.fields("client", active_only=True)])

    @app.post("/k/import/apply")
    @admin_required
    def k_import_apply() -> Any:
        token = request.form.get("token", "")
        if not re.match(r"^[A-Za-z0-9_-]{10,30}$", token):
            abort(400)
        path = os.path.join(imp_dir, token + ".json")
        try:
            with open(path, encoding="utf-8") as fh:
                job = json.load(fh)
            os.remove(path)
        except OSError:
            return done("", "Загрузка устарела — выберите файл ещё раз.", url_for("k_excel_view"))
        n_new = n_upd = 0
        if job["kind"] == "stock":
            for r in job["recs"]:
                store.set_stock(r["article"], who(), qty=r["qty"], price=r["price"])
                n_upd += 1
            return done(f"Склад обновлён: {n_upd} артикулов.", "", url_for("k_excel_view"))
        for r in job["recs"]:
            upd = {key: r[key] for key in ("name", "phone", "email", "messenger", "kind", "company", "inn", "note") if r.get(key)}
            if r["match"]:
                cid = int(r["match"])
                if upd:
                    store.update_client(cid, who(), **upd)
                n_upd += 1
            else:
                with store.tx() as c:
                    cid = store.add_client(c, r["name"], r.get("phone", ""), r.get("email", ""), r.get("messenger", ""),
                                           r.get("kind") or "p", r.get("company", ""))
                    store.log(c, "Клиент добавлен из Excel", who(), client_id=cid)
                extra = {key: r[key] for key in ("inn", "note") if r.get(key)}
                if extra:
                    store.update_client(cid, who(), **extra)
                n_new += 1
            if r.get("custom"):
                k.save_values("client", cid, {f"k{fid}": v for fid, v in r["custom"].items()}, who())
        return done(f"Готово: новых клиентов {n_new}, обновлено {n_upd}.", "", url_for("k_excel_view"))

    # ------------------------------------------------------------------ для шаблонов CRM
    @app.context_processor
    def k_ctx() -> dict[str, Any]:
        return {"k_links": k.links, "k_form": k.form_rows, "k_quick": lambda: k.templates("quick")}
