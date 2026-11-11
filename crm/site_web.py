"""Страницы CRM «Редактор сайта» (Ещё → Редактор сайта) и API для GitHub Actions. Только владельцам.

Вкладки: Товары (фото, доп. фото, скрыть на время) · Разделы (тексты и новые разделы) · Главная (тексты и картинка) ·
Статьи · Отзывы и фото работ · Контакты и последние правки. Каждая кнопка «Сохранить» — одна правка в site_edits;
GitHub забирает её раз в 10 минут и пересобирает сайт (см. site_edit.py).
"""

from __future__ import annotations

import os
import re
from typing import Any

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for

from site_edit import (AVITO_KINDS, HOME_BLOCKS, KIND_KEYS, KINDS, PHOTO_MAX, STATUS_NAMES, SiteEdits, clean_product, faq_text,
                       norm_art, parse_faq, photo_problem, read_site, text_problems)

SHOP_FIELDS = [("max", "Ссылка на бота MAX", "https://max.ru/…"), ("telegram", "Ссылка на Telegram-бота", "https://t.me/…_bot"),
               ("avito", "Профиль на Авито", "https://www.avito.ru/brands/…")]
GALLERY_MAX = 12
PRODUCT_KINDS = ("product", "delete", "hide", "unhide", "gallery_add", "gallery_del")
PILL = {"product": "правка ждёт", "delete": "уберётся", "hide": "скроется", "unhide": "вернётся", "gallery_add": "фото ждут",
        "gallery_del": "фото уберутся"}
SECTION_LIMITS = (("menu", "Название в меню", 3, 40), ("h1", "Заголовок страницы", 0, 120), ("intro", "Вводный текст", 20, 1500),
                  ("title", "Заголовок для поиска (title)", 0, 120), ("description", "Описание для поиска", 0, 250))


def key(a: str) -> str:
    return str(a).upper().replace(" ", "")


def register(app: Flask, store: Any, edits: SiteEdits, site_index: str, h: dict[str, Any]) -> None:
    admin_required, who = h["admin_required"], h["who"]
    site_dir = os.path.dirname(os.path.abspath(site_index))

    def site() -> dict[str, Any]:
        return read_site(site_index)

    def keyed(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {key(x["a"]): x for x in items}

    def uploads(field: str, min_w: int, errs: list[str], limit: int = GALLERY_MAX) -> list[bytes]:
        out = []
        for f in request.files.getlist(field):
            if not f or not f.filename:
                continue
            data = f.read(PHOTO_MAX + 1)
            why = photo_problem(data, min_w)
            if why:
                errs.append(f"«{f.filename}»: {why}")
            out.append(data)
        if len(out) > limit:
            errs.append(f"за один раз — до {limit} фото")
        return out

    def submit(kind: str, article: str, data: dict[str, Any], photos: list[bytes] | None = None, log: str = "") -> int | None:
        try:
            eid = edits.add(kind, article, data, who(), photos=photos or [])
        except ValueError as e:
            flash(str(e), "err")
            return None
        c = store.c(); store.log(c, f"Сайт: {log or kind} (№{eid})", who()); c.commit()
        return eid

    def accepted(what: str) -> None:
        flash(f"Принято: {what}. На сайте — через 10–20 минут (статус — во вкладке «Контакты и правки»).", "ok")

    def sections(s: dict[str, Any]) -> list[dict[str, Any]]:
        lst = s["index"].get("sections")
        if isinstance(lst, list) and lst:
            return [x for x in lst if isinstance(x, dict) and x.get("code")]
        return [{"code": k, "menu": v, "slug": "", "h1": "", "intro": "", "title": "", "description": "", "faq": [], "custom": False}
                for k, v in KINDS]

    def pend_by(kinds: tuple[str, ...], field: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in edits.pending(*kinds):
            v = e["article"] if field == "article" else str(e["data"].get(field, "") or "")
            if v:
                out[key(v) if field == "article" else v] = e
        return out

    # ------------------------------------------------------------------ Товары
    @app.route("/site/edit")
    @admin_required
    def site_edit_view() -> Any:
        s = site()
        q = (request.args.get("q") or "").strip().lower()
        kind = request.args.get("k", "")
        items = [x for x in s["items"] if (not kind or x.get("c") == kind)
                 and (not q or q in str(x.get("a", "")).lower() or q in str(x.get("n", "")).lower())]
        hidden = s["content"].get("hidden", {}) if isinstance(s["content"].get("hidden"), dict) else {}
        return render_template("site_edit.html", items=items, total=len(s["items"]), photo=s["photo"], q=q, k=kind,
                               kinds=s["kinds"], kind_names=dict(s["kinds"]), pend=pend_by(PRODUCT_KINDS, "article"), PILL=PILL,
                               hidden=hidden, gallery=s["content"].get("gallery", {}), tab="items")

    def item_page(s: dict[str, Any], x: dict[str, Any] | None, cur: dict[str, Any], errors: list[str], pend: Any = None) -> Any:
        a = x["a"] if x else ""
        gal_pend = [e for e in edits.pending("gallery_add", "gallery_del") if key(e["article"]) == key(a)] if x else []
        return render_template("site_item.html", x=x, cur=cur, pend=pend, photo=(s["photo"].get(a) if x else ""),
                               kinds=s["kinds"], custom=s["custom"], errors=errors, new=not x, PHOTO_MB=PHOTO_MAX // (1024 * 1024),
                               gallery=(s["content"].get("gallery", {}).get(a, []) if x else []), gal_pend=gal_pend,
                               GALLERY_MAX=GALLERY_MAX, tab="items")

    @app.route("/site/edit/item")
    @admin_required
    def site_item_view() -> Any:
        a = norm_art(request.args.get("a", ""))
        s = site()
        x = keyed(s["items"]).get(key(a)) if a else None
        if a and not x:
            abort(404)
        pend = edits.pending_for(x["a"]) if x else None
        cur = dict(pend["data"]) if pend and pend["kind"] == "product" else dict(x or {"c": request.args.get("k") or "panel"})
        return item_page(s, x, cur, [], pend)

    @app.post("/site/edit/item")
    @admin_required
    def site_item_save() -> Any:
        s = site()
        by_key = keyed(s["items"])
        old = norm_art(request.form.get("old", ""))
        is_new = not old
        form = dict(request.form)
        x = by_key.get(key(old)) if old else None
        if old and not x:
            abort(404)
        if x:
            form["a"] = x["a"]                     # артикул существующего товара не меняем (адрес страницы)
        data, errs = clean_product(form, is_new, set(by_key), s["custom"])
        if is_new and key(data["a"]) in {key(k) for k in s["content"].get("hidden", {})}:
            errs.append(f"товар {data['a']} сейчас скрыт — верните его кнопкой в списке «Скрытые товары»")
        main = uploads("photo", 600, errs, 1)
        more = uploads("more", 600, errs) if is_new else []
        if is_new and not main:
            errs.append("для нового товара нужно фото")
        if not errs:
            eid = submit("product", data["a"], data, main, f"товар {data['a']}")
            if eid:
                if more:
                    submit("gallery_add", data["a"], {"a": data["a"]}, more, f"доп. фото {data['a']}")
                accepted(data["a"])
                return redirect(url_for("site_edit_view"))
        return item_page(s, x, data, errs), 400

    @app.post("/site/edit/delete")
    @admin_required
    def site_item_delete() -> Any:
        x = keyed(site()["items"]).get(key(norm_art(request.form.get("a", ""))))
        if not x:
            abort(404)
        if request.form.get("confirm") != "1":
            flash("Чтобы убрать товар с сайта, отметьте «Да, убрать».", "err")
            return redirect(url_for("site_item_view", a=x["a"]))
        if submit("delete", x["a"], {"a": x["a"]}, log=f"убрать товар {x['a']}"):
            flash(f"{x['a']} уберётся с сайта через 10–20 минут.", "ok")
        return redirect(url_for("site_edit_view"))

    @app.post("/site/edit/hide")
    @admin_required
    def site_item_hide() -> Any:
        x = keyed(site()["items"]).get(key(norm_art(request.form.get("a", ""))))
        if not x:
            abort(404)
        if submit("hide", x["a"], {"a": x["a"]}, log=f"скрыть товар {x['a']}"):
            flash(f"{x['a']} скроется с сайта через 10–20 минут. Вернуть — в списке «Скрытые товары» внизу вкладки.", "ok")
        return redirect(url_for("site_edit_view"))

    @app.post("/site/edit/unhide")
    @admin_required
    def site_item_unhide() -> Any:
        a = norm_art(request.form.get("a", ""))
        hk = next((k for k in site()["content"].get("hidden", {}) if key(k) == key(a)), None)
        if not hk:
            abort(404)
        if submit("unhide", hk, {"a": hk}, log=f"вернуть товар {hk}"):
            flash(f"{hk} вернётся на сайт через 10–20 минут.", "ok")
        return redirect(url_for("site_edit_view") + "#hidden")

    @app.post("/site/edit/gallery")
    @admin_required
    def site_gallery() -> Any:
        s = site()
        x = keyed(s["items"]).get(key(norm_art(request.form.get("a", ""))))
        if not x:
            abort(404)
        have = s["content"].get("gallery", {}).get(x["a"], [])
        if request.form.get("action") == "del":
            files = [f for f in request.form.getlist("f") if f in have]
            if not files:
                flash("Отметьте фото, которые убрать.", "err")
            elif submit("gallery_del", x["a"], {"a": x["a"], "files": files}, log=f"убрать доп. фото {x['a']}"):
                accepted(f"уберётся фото: {len(files)}")
        else:
            errs: list[str] = []
            photos = uploads("more", 600, errs)
            if not photos and not errs:
                errs.append("выберите фото")
            if len(have) + len(photos) > GALLERY_MAX:
                errs.append(f"у товара может быть до {GALLERY_MAX} доп. фото (сейчас {len(have)})")
            if errs:
                for e in errs:
                    flash(e, "err")
            elif submit("gallery_add", x["a"], {"a": x["a"]}, photos, f"доп. фото {x['a']}"):
                accepted(f"фото к {x['a']}: {len(photos)}")
        return redirect(url_for("site_item_view", a=x["a"]) + "#gallery")

    # ------------------------------------------------------------------ Разделы
    @app.route("/site/edit/sections")
    @admin_required
    def site_sections_view() -> Any:
        s = site()
        pend = pend_by(("section", "kind", "kind_del"), "code")
        counts: dict[str, int] = {}
        for x in s["items"]:
            counts[x.get("c", "")] = counts.get(x.get("c", ""), 0) + 1
        return render_template("site_sections.html", sections=sections(s), pend=pend, counts=counts,
                               new_pending=[e for e in edits.pending("kind") if not e["data"].get("code")], tab="sections")

    def section_page(s: dict[str, Any], code: str, cur: dict[str, Any], errors: list[str], pend: Any = None) -> Any:
        sec = next((x for x in sections(s) if x["code"] == code), None) if code else None
        custom = (not code) or code in s["custom"]
        n_items = sum(1 for x in s["items"] if x.get("c") == code) if code else 0
        return render_template("site_section.html", code=code, sec=sec, cur=cur, custom=custom, errors=errors, pend=pend,
                               AVITO_KINDS=AVITO_KINDS, n_items=n_items, tab="sections")

    @app.route("/site/edit/section")
    @admin_required
    def site_section_view() -> Any:
        s = site()
        code = request.args.get("code", "")
        sec = next((x for x in sections(s) if x["code"] == code), None) if code else None
        if code and not sec:
            abort(404)
        pend = pend_by(("section", "kind"), "code").get(code) if code else None
        if pend:
            cur = dict(pend["data"])
            cur["faq_text"] = faq_text(cur.get("faq", []))
        elif sec:
            cur = dict(sec)
            if code in s["custom"]:
                cur.update(s["custom"][code])
            cur["faq_text"] = faq_text(cur.get("faq", []))
        else:
            cur = {}
        return section_page(s, code, cur, [], pend)

    @app.post("/site/edit/section")
    @admin_required
    def site_section_save() -> Any:
        s = site()
        code = request.form.get("code", "")
        sec = next((x for x in sections(s) if x["code"] == code), None) if code else None
        if code and not sec:
            abort(404)
        custom = (not code) or code in s["custom"]
        f = {k: re.sub(r"[ \t]+", " ", str(request.form.get(k, "") or "")).strip() for k in
             ("label", "menu", "h1", "intro", "title", "description", "about", "material", "maker", "avito")}
        faq_src = request.form.get("faq_text", "")
        faq = parse_faq(faq_src)
        errs = []
        for k, name, lo, hi in SECTION_LIMITS:
            if not (lo <= len(f[k]) <= hi) and (f[k] or lo):
                errs.append(f"{name}: от {lo} до {hi} знаков" if lo else f"{name}: до {hi} знаков")
        if faq_src.strip() and not faq:
            errs.append("вопросы и ответы: вопрос на первой строке, ответ — на следующих; между парами — пустая строка")
        texts = [f[k] for k in f] + [x for q in faq for x in q]
        if custom:
            if not 3 <= len(f["label"]) <= 60:
                errs.append("как называется один товар: от 3 до 60 знаков (например, «Бамбуковая панель»)")
            if len(f["about"]) > 1500:
                errs.append("текст «о товарах раздела»: до 1500 знаков")
            bad = text_problems(*texts, soft=True)
            data: dict[str, Any] = {"code": code, **{k: f[k] for k in ("label", "menu", "h1", "intro", "title", "description", "about",
                                                                    "material", "maker")},
                                    "faq": faq, "avito": f["avito"] if f["avito"] in {k for k, _ in AVITO_KINDS} else ""}
            kind = "kind"
        else:
            bad = text_problems(*texts)
            data = {"code": code, **{k: f[k] for k in ("menu", "h1", "intro", "title", "description")}, "faq": faq}
            kind = "section"
        if bad:
            errs.append("в тексте нельзя: " + ", ".join(bad) + " (правила магазина)")
        if not errs and submit(kind, "", data, log=("новый раздел " if not code else "раздел ") + f["menu"]):
            accepted(("новый раздел «%s»" if not code else "раздел «%s»") % f["menu"])
            return redirect(url_for("site_sections_view"))
        data["faq_text"] = faq_src
        return section_page(s, code, data, errs), 400

    @app.post("/site/edit/section/delete")
    @admin_required
    def site_section_delete() -> Any:
        s = site()
        code = request.form.get("code", "")
        if code not in s["custom"]:
            abort(404)
        if any(x.get("c") == code for x in s["items"]):
            flash("В разделе есть товары — сначала уберите их или перенесите в другой раздел.", "err")
        elif request.form.get("confirm") != "1":
            flash("Отметьте «Да, удалить раздел».", "err")
        elif submit("kind_del", "", {"code": code, "menu": s["custom"][code].get("menu", "")}, log=f"удалить раздел {code}"):
            accepted("раздел удалится")
            return redirect(url_for("site_sections_view"))
        return redirect(url_for("site_section_view", code=code))

    # ------------------------------------------------------------------ Главная
    @app.route("/site/edit/home", methods=["GET", "POST"])
    @admin_required
    def site_home_view() -> Any:
        s = site()
        blocks = [(k, name, lim) for k, name, lim in HOME_BLOCKS if k in s["home"]]
        cur = dict(s["home"])
        pend = edits.pending("home")
        for e in pend:
            cur.update(e["data"].get("texts", {}))
        errs: list[str] = []
        if request.method == "POST":
            texts = {}
            for k, name, lim in blocks:
                if k not in request.form:
                    continue
                v = re.sub(r"[ \t]+", " ", str(request.form.get(k, "") or "")).strip()
                if v != cur.get(k, ""):
                    if not 2 <= len(v) <= lim:
                        errs.append(f"«{name}»: от 2 до {lim} знаков")
                    texts[k] = v
                cur[k] = v
            bad = text_problems(*texts.values())
            if bad:
                errs.append("в тексте нельзя: " + ", ".join(bad) + " (правила магазина)")
            hero = uploads("hero", 1000, errs, 1)
            if not texts and not hero and not errs:
                flash("Ничего не изменилось.", "ok")
                return redirect(url_for("site_home_view"))
            if not errs and submit("home", "", {"texts": texts}, hero, "главная страница"):
                accepted("главная страница")
                return redirect(url_for("site_home_view"))
        return render_template("site_home.html", blocks=blocks, cur=cur, hero=s["hero"], pend=pend, errors=errs,
                               tab="home"), (400 if errs else 200)

    # ------------------------------------------------------------------ Статьи
    def custom_article(s: dict[str, Any], slug: str) -> dict[str, Any] | None:
        return next((x for x in s["content"].get("articles", []) if isinstance(x, dict) and x.get("slug") == slug), None)

    @app.route("/site/edit/articles")
    @admin_required
    def site_articles_view() -> Any:
        s = site()
        arts = s["index"].get("articles") if isinstance(s["index"].get("articles"), list) else []
        return render_template("site_articles.html", arts=arts, pend=pend_by(("article", "article_del"), "slug"),
                               new_pending=[e for e in edits.pending("article") if not e["data"].get("slug")], tab="articles")

    def article_page(s: dict[str, Any], slug: str, cur: dict[str, Any], errors: list[str], pend: Any = None) -> Any:
        info = next((x for x in s["index"].get("articles", []) if x.get("slug") == slug), None) if slug else None
        builtin = bool(info and not info.get("custom"))
        ca = custom_article(s, slug) if slug and not builtin else None
        return render_template("site_article.html", slug=slug, info=info, builtin=builtin, photos=(ca or {}).get("photos", []),
                               cur=cur, errors=errors, pend=pend, tab="articles")

    @app.route("/site/edit/article")
    @admin_required
    def site_article_view() -> Any:
        s = site()
        slug = request.args.get("slug", "")
        info = next((x for x in s["index"].get("articles", []) if x.get("slug") == slug), None) if slug else None
        if slug and not info:
            abort(404)
        pend = pend_by(("article",), "slug").get(slug) if slug else None
        if pend:
            cur = dict(pend["data"])
        elif info and info.get("custom"):
            cur = dict(custom_article(s, slug) or info)
        else:
            cur = dict(info or {})
        return article_page(s, slug, cur, [], pend)

    @app.post("/site/edit/article")
    @admin_required
    def site_article_save() -> Any:
        s = site()
        slug = request.form.get("slug", "")
        info = next((x for x in s["index"].get("articles", []) if x.get("slug") == slug), None) if slug else None
        if slug and not info:
            abort(404)
        builtin = bool(info and not info.get("custom"))
        f = {k: re.sub(r"[ \t]+", " ", str(request.form.get(k, "") or "")).strip() for k in ("title", "h1", "description", "lead")}
        body = str(request.form.get("body", "") or "").replace("\r\n", "\n").strip()
        hidden = request.form.get("hidden") == "1"
        errs: list[str] = []
        if not 10 <= len(f["title"]) <= 120:
            errs.append("заголовок: от 10 до 120 знаков")
        if not 20 <= len(f["description"]) <= 250:
            errs.append("описание для поиска: от 20 до 250 знаков")
        if len(f["h1"]) > 160 or len(f["lead"]) > 600:
            errs.append("заголовок на странице — до 160 знаков, вступление — до 600")
        data: dict[str, Any] = {"slug": slug, **f, "hidden": hidden}
        photos: list[bytes] = []
        if builtin:
            data["builtin"] = True
            bad = text_problems(*f.values())
        else:
            if not 100 <= len(body) <= 30000:
                errs.append("текст статьи: от 100 до 30 000 знаков")
            data["body"] = body
            have = [p["f"] for p in (custom_article(s, slug) or {}).get("photos", [])] if slug else []
            data["drop_photos"] = [x for x in request.form.getlist("drop") if x in have]
            photos = uploads("photos", 600, errs)
            data["caps"] = [x.strip()[:150] for x in str(request.form.get("caps", "")).replace("\r\n", "\n").split("\n")][:len(photos)]
            if len(have) - len(data["drop_photos"]) + len(photos) > 20:
                errs.append("в статье — до 20 фото")
            bad = text_problems(*f.values(), body)
        if bad:
            errs.append("в тексте нельзя: " + ", ".join(bad) + " (правила магазина)")
        if not errs and submit("article", "", data, photos, ("статья " if slug else "новая статья ") + f["title"]):
            accepted(("статья «%s»" if slug else "новая статья «%s»") % f["title"])
            return redirect(url_for("site_articles_view"))
        return article_page(s, slug, data, errs), 400

    @app.post("/site/edit/article/delete")
    @admin_required
    def site_article_delete() -> Any:
        s = site()
        slug = request.form.get("slug", "")
        info = next((x for x in s["index"].get("articles", []) if x.get("slug") == slug), None)
        if not info:
            abort(404)
        if request.form.get("confirm") != "1":
            flash("Отметьте «Да, убрать статью».", "err")
            return redirect(url_for("site_article_view", slug=slug))
        if submit("article_del", "", {"slug": slug, "builtin": not info.get("custom"), "title": info.get("title", "")},
                  log=f"убрать статью {slug}"):
            accepted("статья уберётся с сайта")
        return redirect(url_for("site_articles_view"))

    # ------------------------------------------------------------------ Отзывы
    def reviews(s: dict[str, Any]) -> list[dict[str, Any]]:
        r = s["content"].get("reviews", [])
        return [x for x in r if isinstance(x, dict)] if isinstance(r, list) else []

    @app.route("/site/edit/reviews")
    @admin_required
    def site_reviews_view() -> Any:
        s = site()
        return render_template("site_reviews.html", reviews=reviews(s)[::-1], pend=pend_by(("review", "review_del"), "id"),
                               new_pending=[e for e in edits.pending("review") if not e["data"].get("id")], tab="reviews")

    def review_page(s: dict[str, Any], rid: str, cur: dict[str, Any], errors: list[str], pend: Any = None) -> Any:
        rv = next((x for x in reviews(s) if str(x.get("id")) == rid), None) if rid else None
        return render_template("site_review.html", rid=rid, rv=rv, cur=cur, errors=errors, pend=pend,
                               items=s["items"], tab="reviews")

    @app.route("/site/edit/review")
    @admin_required
    def site_review_view() -> Any:
        s = site()
        rid = request.args.get("id", "")
        rv = next((x for x in reviews(s) if str(x.get("id")) == rid), None) if rid else None
        if rid and not rv:
            abort(404)
        pend = pend_by(("review",), "id").get(rid) if rid else None
        return review_page(s, rid, dict(pend["data"] if pend else (rv or {})), [], pend)

    @app.post("/site/edit/review")
    @admin_required
    def site_review_save() -> Any:
        s = site()
        rid = request.form.get("id", "")
        rv = next((x for x in reviews(s) if str(x.get("id")) == rid), None) if rid else None
        if rid and not rv:
            abort(404)
        f = {k: re.sub(r"[ \t]+", " ", str(request.form.get(k, "") or "")).strip() for k in ("name", "place", "date", "article")}
        text = str(request.form.get("text", "") or "").replace("\r\n", "\n").strip()
        errs: list[str] = []
        if not 2 <= len(f["name"]) <= 60:
            errs.append("имя: от 2 до 60 знаков (можно «Анна» или «Анна, Купчино»)")
        if not 10 <= len(text) <= 2000:
            errs.append("текст отзыва: от 10 до 2000 знаков")
        if f["date"] and not re.match(r"^\d{4}-\d{2}-\d{2}$", f["date"]):
            errs.append("дата — в календаре")
        if f["article"] and key(f["article"]) not in keyed(s["items"]):
            errs.append(f"товара {f['article']} нет на сайте — оставьте поле пустым или выберите из списка")
        have = (rv or {}).get("photos", [])
        drop = [x for x in request.form.getlist("drop") if x in have]
        photos = uploads("photos", 400, errs, 8)
        if len(have) - len(drop) + len(photos) > 8:
            errs.append("у отзыва — до 8 фото")
        bad = text_problems(text, f["place"])
        if bad:
            errs.append("в тексте нельзя: " + ", ".join(bad) + " (правила магазина)")
        data = {"id": rid, **f, "text": text, "drop_photos": drop}
        if not errs and submit("review", "", data, photos, ("отзыв " if rid else "новый отзыв ") + f["name"]):
            accepted(("отзыв «%s»" if rid else "новый отзыв «%s»") % f["name"])
            return redirect(url_for("site_reviews_view"))
        return review_page(s, rid, data, errs), 400

    @app.post("/site/edit/review/delete")
    @admin_required
    def site_review_delete() -> Any:
        s = site()
        rid = request.form.get("id", "")
        rv = next((x for x in reviews(s) if str(x.get("id")) == rid), None)
        if not rv:
            abort(404)
        if request.form.get("confirm") != "1":
            flash("Отметьте «Да, удалить отзыв».", "err")
            return redirect(url_for("site_review_view", id=rid))
        if submit("review_del", "", {"id": rid, "name": rv.get("name", "")}, log=f"удалить отзыв {rid}"):
            accepted("отзыв удалится")
        return redirect(url_for("site_reviews_view"))

    # ------------------------------------------------------------------ Контакты и правки
    @app.route("/site/edit/recent")
    @admin_required
    def site_recent_view() -> Any:
        s = site()
        return render_template("site_recent.html", recent=edits.recent(60), shop=s["shop"], SHOP_FIELDS=SHOP_FIELDS,
                               STATUS_NAMES=STATUS_NAMES, tab="recent")

    @app.post("/site/edit/shop")
    @admin_required
    def site_shop_save() -> Any:
        data: dict[str, str] = {}
        for k, _, _ in SHOP_FIELDS:
            v = (request.form.get(k) or "").strip()
            if v and not re.match(r"^https://[^\s\"<>\\]{3,200}$", v):
                flash("Ссылки — только вида https://…", "err")
                return redirect(url_for("site_recent_view") + "#shop")
            data[k] = v
        if submit("shop", "", data, log="контакты"):
            accepted("контакты")
        return redirect(url_for("site_recent_view"))

    @app.post("/site/edit/<int:eid>/cancel")
    @admin_required
    def site_edit_cancel(eid: int) -> Any:
        flash("Правка отменена." if edits.cancel(eid, who()) else "Эту правку уже нельзя отменить — она на сайте или обработана.",
              "ok")
        return redirect(request.form.get("back") if str(request.form.get("back", "")).startswith("/site/edit")
                        else url_for("site_recent_view"))

    # ------------------------------------------------------------------ картинки
    @app.route("/site/img/<path:name>")
    @admin_required
    def site_img(name: str) -> Any:
        if not re.match(r"^(2x/|stati/|otzyvy/)?[A-Za-z0-9._-]{1,80}\.(jpg|jpeg|png|webp)$", name):
            abort(404)
        p = os.path.join(site_dir, "img", name)
        if not os.path.isfile(p):
            abort(404)
        return send_file(p, max_age=3600)

    @app.route("/site/edit/photo/<int:eid>", defaults={"n": 0})
    @app.route("/site/edit/photo/<int:eid>/<int:n>")
    @admin_required
    def site_edit_photo(eid: int, n: int) -> Any:
        e = edits.get(eid)
        p = edits.dir / e["photos"][n] if e and n < len(e["photos"]) else None
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
        return {"site_text_problems": text_problems, "SITE_BUILTIN": KIND_KEYS}
