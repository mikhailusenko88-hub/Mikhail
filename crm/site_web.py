"""Страницы CRM «Редактор сайта» (Ещё → Редактор сайта) и API для GitHub Actions. Только владельцам."""

from __future__ import annotations

import os
import re
from typing import Any

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for

from site_edit import KINDS, PHOTO_MAX, STATUS_NAMES, SiteEdits, clean_product, norm_art, read_site, text_problems

KIND_NAMES = dict(KINDS)
SHOP_FIELDS = [("max", "Ссылка на бота MAX", "https://max.ru/…"), ("telegram", "Ссылка на Telegram-бота", "https://t.me/…_bot"),
               ("avito", "Профиль на Авито", "https://www.avito.ru/brands/…")]


def register(app: Flask, store: Any, edits: SiteEdits, site_index: str, h: dict[str, Any]) -> None:
    admin_required, who = h["admin_required"], h["who"]
    site_dir = os.path.dirname(os.path.abspath(site_index))

    def catalog() -> dict[str, Any]:
        return read_site(site_index)

    def keyed(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(x["a"]).upper().replace(" ", ""): x for x in items}

    @app.route("/site/edit")
    @admin_required
    def site_edit_view() -> Any:
        s = catalog()
        q = (request.args.get("q") or "").strip().lower()
        kind = request.args.get("k", "")
        items = [x for x in s["items"] if (not kind or x.get("c") == kind)
                 and (not q or q in str(x.get("a", "")).lower() or q in str(x.get("n", "")).lower())]
        recent = edits.recent(40)
        pend = {e["article"]: e for e in recent if e["status"] == "new" and e["kind"] in ("product", "delete")}
        return render_template("site_edit.html", items=items, total=len(s["items"]), photo=s["photo"], q=q, k=kind,
                               KINDS=KINDS, KIND_NAMES=KIND_NAMES, recent=recent, pend=pend, shop=s["shop"],
                               SHOP_FIELDS=SHOP_FIELDS, STATUS_NAMES=STATUS_NAMES)

    @app.route("/site/edit/item")
    @admin_required
    def site_item_view() -> Any:
        a = norm_art(request.args.get("a", ""))
        s = catalog()
        x = keyed(s["items"]).get(a.upper().replace(" ", "")) if a else None
        if a and not x:
            abort(404)
        pend = edits.pending_for(x["a"]) if x else None
        cur = dict(pend["data"]) if pend and pend["kind"] == "product" else dict(x or {"c": request.args.get("k", "panel")})
        return render_template("site_item.html", x=x, cur=cur, pend=pend, photo=(s["photo"].get(x["a"]) if x else ""),
                               KINDS=KINDS, errors=[], new=not x, PHOTO_MB=PHOTO_MAX // (1024 * 1024))

    @app.post("/site/edit/item")
    @admin_required
    def site_item_save() -> Any:
        s = catalog()
        by_key = keyed(s["items"])
        old = norm_art(request.form.get("old", ""))
        is_new = not old
        form = dict(request.form)
        if not is_new:
            x = by_key.get(old.upper().replace(" ", ""))
            if not x:
                abort(404)
            form["a"] = x["a"]                     # артикул существующего товара не меняем (адрес страницы)
        data, errs = clean_product(form, is_new, set(by_key))
        f = request.files.get("photo")
        photo = f.read(PHOTO_MAX + 1) if f and f.filename else b""
        if is_new and not photo:
            errs.append("для нового товара нужно фото")
        if not errs:
            try:
                eid = edits.add("product", data["a"], data, who(), photo)
            except ValueError as e:
                errs.append(str(e))
            else:
                c = store.c(); store.log(c, f"Сайт: правка товара {data['a']} (№{eid})", who()); c.commit()
                flash(f"Принято: {data['a']}. На сайте — через 10–20 минут (статус — в списке «Последние правки»).", "ok")
                return redirect(url_for("site_edit_view") + "#recent")
        x = by_key.get(old.upper().replace(" ", "")) if old else None
        return render_template("site_item.html", x=x, cur=data, pend=None, photo=(s["photo"].get(x["a"]) if x else ""),
                               KINDS=KINDS, errors=errs, new=is_new, PHOTO_MB=PHOTO_MAX // (1024 * 1024)), 400

    @app.post("/site/edit/delete")
    @admin_required
    def site_item_delete() -> Any:
        a = norm_art(request.form.get("a", ""))
        x = keyed(catalog()["items"]).get(a.upper().replace(" ", ""))
        if not x:
            abort(404)
        if request.form.get("confirm") != "1":
            flash("Чтобы убрать товар с сайта, отметьте «Да, убрать».", "err")
            return redirect(url_for("site_item_view", a=x["a"]))
        eid = edits.add("delete", x["a"], {"a": x["a"]}, who())
        c = store.c(); store.log(c, f"Сайт: убрать товар {x['a']} (№{eid})", who()); c.commit()
        flash(f"{x['a']} уберётся с сайта через 10–20 минут. Вернуть — «Добавить товар» с тем же артикулом.", "ok")
        return redirect(url_for("site_edit_view") + "#recent")

    @app.post("/site/edit/shop")
    @admin_required
    def site_shop_save() -> Any:
        data: dict[str, str] = {}
        for k, _, _ in SHOP_FIELDS:
            v = (request.form.get(k) or "").strip()
            if v and not re.match(r"^https://[^\s\"<>]{3,200}$", v):
                flash("Ссылки — только вида https://…", "err")
                return redirect(url_for("site_edit_view") + "#shop")
            data[k] = v
        eid = edits.add("shop", "", data, who())
        c = store.c(); store.log(c, f"Сайт: контакты (№{eid})", who()); c.commit()
        flash("Контакты на сайте обновятся через 10–20 минут.", "ok")
        return redirect(url_for("site_edit_view") + "#recent")

    @app.post("/site/edit/<int:eid>/cancel")
    @admin_required
    def site_edit_cancel(eid: int) -> Any:
        flash("Правка отменена." if edits.cancel(eid, who()) else "Эту правку уже нельзя отменить — она на сайте или обработана.",
              "ok")
        return redirect(url_for("site_edit_view") + "#recent")

    @app.route("/site/img/<path:name>")
    @admin_required
    def site_img(name: str) -> Any:
        if not re.match(r"^(2x/)?[A-Za-z0-9._-]{1,80}\.(jpg|jpeg|png|webp)$", name):
            abort(404)
        p = os.path.join(site_dir, "img", name)
        if not os.path.isfile(p):
            abort(404)
        return send_file(p, max_age=3600)

    @app.route("/site/edit/photo/<int:eid>")
    @admin_required
    def site_edit_photo(eid: int) -> Any:
        e = edits.get(eid)
        p = edits.dir / e["photo"] if e and e["photo"] else None
        if not p or not p.is_file():
            abort(404)
        return send_file(p, max_age=0)

    # ---- для GitHub Actions: новые правки и их фото (только то, что и так будет на публичном сайте)
    @app.route("/api/site/edits")
    def api_site_edits() -> Any:
        try:
            after = int(request.args.get("after", "0"))
        except ValueError:
            after = 0
        resp = jsonify({"edits": edits.api_list(after)})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/site/photo/<name>")
    def api_site_photo(name: str) -> Any:
        p = edits.photo_path(name)
        if not p:
            abort(404)
        return send_file(p, max_age=0)

    @app.context_processor
    def site_ctx() -> dict[str, Any]:
        return {"site_text_problems": text_problems}
