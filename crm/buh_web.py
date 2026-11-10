"""Страницы CRM для учёта и отчётности: «Закупки», «Налоги», «Дизайнеры», товары для документов, реквизиты по ИНН.

Закупки, налоги и выплаты дизайнерам — только владельцам (там закупочные цены и деньги).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

from buh import (CONTRACT_LIMIT_KOP, DOPP_STATUS, EAEU, EAEU_FROM, TRANSPORTS, VAT_FREE_LIMIT_KOP, VAT_RATE, Buh, calendar_known, dmy,
                 egrul_lookup, iso, kop_in)
from store import TAX_STATUSES, Store, today


def register(app: Flask, store: Store, buh: Buh, h: dict[str, Any]) -> None:
    login_required, admin_required, who, safe_next = h["login_required"], h["admin_required"], h["who"], h["safe_next"]

    @app.context_processor
    def buh_ctx() -> dict[str, Any]:
        return {"kop_in": kop_in, "dmy": dmy, "TRANSPORTS": TRANSPORTS, "TRANSPORT_NAMES": dict(TRANSPORTS), "EAEU": EAEU,
                "DOPP_STATUS": DOPP_STATUS, "EAEU_FROM": EAEU_FROM, "TAX_STATUSES": TAX_STATUSES, "TAX_STATUS_NAMES": dict(TAX_STATUSES),
                "VAT_RATE": VAT_RATE}

    # ------------------------------------------------------------ реквизиты по ИНН
    @app.post("/clients/<int:cid>/egrul")
    @login_required
    def client_egrul(cid: int) -> Any:
        cl = store.client(cid)
        if not cl:
            abort(404)
        inn = re.sub(r"\D", "", request.form.get("inn") or cl["inn"] or "")
        try:
            info = egrul_lookup(inn, buh.egrul_http)
        except ValueError as e:
            flash(f"Не заполнилось: {e}.", "err")
            return redirect(url_for("client_view", cid=cid) + "#req")
        fields = {k: info[k] for k in ("inn", "full_name", "kpp", "ogrn", "legal_address", "signer") if info.get(k)}
        if info.get("company") and not cl["company"]:
            fields["company"] = info["company"]
        if cl["kind"] == "p" and len(inn) == 10:
            fields["kind"] = "c"
        store.update_client(cid, who(), **fields)
        msg = "Реквизиты заполнены из ЕГРЮЛ/ЕГРИП ФНС — проверьте подписанта и почту для документов."
        if info.get("closed"):
            flash(f"Внимание: по данным ФНС деятельность прекращена {info['closed']}. " + msg, "err")
        else:
            flash(msg, "ok")
        return redirect(url_for("client_view", cid=cid) + "#req")

    # ------------------------------------------------------------ товары для документов
    @app.route("/stock/docs")
    @login_required
    def stock_docs_view() -> Any:
        q = (request.args.get("q") or "").strip().lower()
        rows = buh.products()
        if q:
            rows = [r for r in rows if q in (r["article"] + " " + r["name"]).lower()]
        no_w = sum(1 for r in buh.products() if not r["weight_g"])
        return render_template("stock_docs.html", rows=rows, q=q, no_w=no_w)

    @app.post("/stock/docs/<path:article>")
    @login_required
    def stock_docs_set(article: str) -> Any:
        buh.set_product_info(article, who(), request.form.get("tnved", ""), request.form.get("weight_g", ""),
                             request.form.get("doc_name", ""))
        flash(f"{article}: сохранено.", "ok")
        back = request.form.get("back") or url_for("stock_docs_view")
        return redirect(safe_next(back) + f"#a-{re.sub(r'[^A-Za-z0-9-]', '-', article)}")

    # ------------------------------------------------------------ закупки
    @app.route("/purchases")
    @admin_required
    def purchases_view() -> Any:
        ps = buh.purchases()
        return render_template("purchases.html", ps=[(p, buh.status(p)) for p in ps], contracts=buh.contract_paid(),
                               limit=CONTRACT_LIMIT_KOP, unk=store.setting("contract_unk", ""), lots=buh.lots())

    @app.post("/purchases/new")
    @admin_required
    def purchase_new() -> Any:
        pid = buh.create_purchase(who(), request.form.get("num", ""), request.form.get("transport", "auto"))
        flash("Закупка создана — добавьте позиции спецификации.", "ok")
        return redirect(url_for("purchase_view", pid=pid))

    @app.post("/purchases/contract")
    @admin_required
    def purchases_contract() -> Any:
        store.set_setting("contract_unk", (request.form.get("unk") or "").strip()[:40])
        flash("Сохранено.", "ok")
        return redirect(url_for("purchases_view"))

    @app.route("/purchases/<int:pid>", methods=["GET", "POST"])
    @admin_required
    def purchase_view(pid: int) -> Any:
        p = buh.purchase(pid)
        if not p:
            abort(404)
        if request.method == "POST":
            form = request.form.to_dict()
            form.pop("csrf", None)
            ch = buh.update_purchase(pid, who(), form)
            flash("Сохранено." if ch else "Изменений нет.", "ok")
            return redirect(url_for("purchase_view", pid=pid) + "#" + (request.form.get("sec") or "top"))
        lines = buh.purchase_lines(pid)
        costs = buh.cost_split(p, lines) if lines else []
        cp = [x for x in buh.contract_paid() if x["contract"] == p["contract"]]
        return render_template("purchase.html", p=p, lines=lines, costs=costs, steps=buh.steps(p), need=buh.dopp_needed(p),
                               vat=buh.vat_kop(p), guar=buh.guarantee_kop(p), lots=buh.lots(pid),
                               catalog=store.catalog.all(), cpaid=cp[0]["paid"] if cp else 0, limit=CONTRACT_LIMIT_KOP,
                               unk=store.setting("contract_unk", ""))

    @app.post("/purchases/<int:pid>/lines")
    @admin_required
    def purchase_lines_add(pid: int) -> Any:
        if (request.form.get("paste") or "").strip():
            n, errs = buh.paste_lines(pid, who(), request.form["paste"])
            if n:
                flash(f"Добавлено позиций: {n}.", "ok")
            for e in errs[:8]:
                flash(e, "err")
        else:
            err = buh.add_purchase_line(pid, who(), request.form.get("article", ""), request.form.get("qty", ""),
                                        request.form.get("price", ""))
            flash(err or "Позиция добавлена.", "err" if err else "ok")
        return redirect(url_for("purchase_view", pid=pid) + "#lines")

    @app.post("/purchases/<int:pid>/lines/<int:lid>/del")
    @admin_required
    def purchase_line_del(pid: int, lid: int) -> Any:
        err = buh.del_purchase_line(pid, lid, who())
        if err:
            flash(err, "err")
        return redirect(url_for("purchase_view", pid=pid) + "#lines")

    @app.post("/purchases/<int:pid>/receive")
    @admin_required
    def purchase_receive(pid: int) -> Any:
        err = buh.receive(pid, who(), request.form.get("day", ""))
        flash(err or "Оприходовано: остатки на складе выросли, себестоимость партии записана.", "err" if err else "ok")
        return redirect(url_for("purchase_view", pid=pid) + "#stock")

    @app.post("/purchases/<int:pid>/unreceive")
    @admin_required
    def purchase_unreceive(pid: int) -> Any:
        err = buh.unreceive(pid, who())
        flash(err or "Оприходование отменено, остатки уменьшены.", "err" if err else "ok")
        return redirect(url_for("purchase_view", pid=pid) + "#stock")

    @app.post("/purchases/<int:pid>/delete")
    @admin_required
    def purchase_delete(pid: int) -> Any:
        err = buh.delete_purchase(pid, who())
        if err:
            flash(err, "err")
            return redirect(url_for("purchase_view", pid=pid))
        flash("Закупка удалена.", "ok")
        return redirect(url_for("purchases_view"))

    # ------------------------------------------------------------ налоги и отчётность
    @app.route("/taxes")
    @admin_required
    def taxes_view() -> Any:
        t = today()
        ys = request.args.get("y") or t[:4]
        y = int(ys) if ys.isdigit() and 2020 <= int(ys) <= 2100 else int(t[:4])
        cal = buh.calendar(t)
        soon = (date.fromisoformat(t) + timedelta(days=14)).isoformat()
        return render_template("taxes.html", cal=cal, soon=soon, inc=buh.income_year(int(t[:4])),
                               limit=VAT_FREE_LIMIT_KOP, cost=buh.cost_by_quarter(y), y=y,
                               reg=store.setting("ip_reg_date", "2026-11-02"), known=calendar_known(int(t[:4]) + 1))

    @app.post("/taxes/done")
    @admin_required
    def taxes_done() -> Any:
        buh.set_done(request.form.get("key", ""), request.form.get("done") == "1", who())
        return redirect(url_for("taxes_view") + "#cal")

    @app.post("/taxes/settings")
    @admin_required
    def taxes_settings() -> Any:
        v = iso(request.form.get("ip_reg_date"))
        if v:
            store.set_setting("ip_reg_date", v)
            flash("Сохранено.", "ok")
        return redirect(url_for("taxes_view") + "#set")

    @app.route("/taxes/sales.csv")
    @admin_required
    def taxes_sales_csv() -> Any:
        y = request.args.get("y", today()[:4])
        y = int(y) if y.isdigit() else int(today()[:4])
        return Response(buh.sales_csv(y), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=sebestoimost-{y}.csv"})

    # ------------------------------------------------------------ дизайнеры
    @app.route("/designers")
    @admin_required
    def designers_view() -> Any:
        return render_template("designers.html", ds=buh.designer_summary(), rewards=buh.rewards(), payouts=buh.payouts())

    @app.post("/designers/<int:cid>/payout")
    @admin_required
    def designer_payout(cid: int) -> Any:
        err = buh.add_payout(cid, who(), request.form.get("amount"), request.form.get("paid_at"), request.form.get("doc", ""))
        flash(err or "Выплата записана.", "err" if err else "ok")
        return redirect(url_for("designers_view") + f"#d{cid}")

    @app.post("/designers/payout/<int:pid>/del")
    @admin_required
    def designer_payout_del(pid: int) -> Any:
        buh.del_payout(pid, who())
        flash("Выплата удалена.", "ok")
        return redirect(url_for("designers_view"))

    @app.post("/deals/<int:did>/designer")
    @login_required
    def deal_designer(did: int) -> Any:
        err = buh.set_deal_designer(did, who(), request.form.get("designer_id"), request.form.get("pct"))
        flash(err or "Сохранено.", "err" if err else "ok")
        return redirect(url_for("deal_view", did=did) + "#designer")
