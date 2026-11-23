"""«Ещё → Каталог для Авито»: листы каталога картинками — отправлять покупателю в чат Авито.

В чат Авито нельзя вставить ссылку (Авито её не пропускает и может ограничить профиль) и нельзя приложить файл
каталога — уходят только картинки. Поэтому каталог нарезан на вертикальные листы под экран телефона: фото, артикул,
размер, цена за штуку. На листах нет названия магазина, контактов и ссылок.

Листы — это раздел «Каталог для Авито» в «Документах» (docs.py), поэтому попадают в резервную копию. Кладёт их Claude
через ветку outbox (docs2/*.json — новая версия заменяет прежнюю по имени файла); можно и загрузкой в «Документах».
Какие цены нарисованы на листе, записано в заметке документа: «Цены на 23.11.2026: A703 — 475, A005 — 525».
Страница сверяет их с ценами CRM (те же, что видит сайт) и помечает лист, если цена с тех пор изменилась, —
такой лист отправлять нельзя, пока его не пересоберут.
"""
from __future__ import annotations

import re
from typing import Any

from flask import Flask, abort, render_template, request, send_file

from docs import Docs
from pochta import size_h

FOLDER = "Каталог для Авито"
IMAGES = {"image/jpeg", "image/png", "image/webp"}
PAIR_RE = re.compile(r"^\s*(.+?)\s+—\s+(\d[\d\s ]*)\s*$")
DAY_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})")


def parse_note(note: str) -> tuple[str, list[tuple[str, int]]]:
    """«Цены на 23.11.2026: A703 — 475, GS 1 — 1425» → ('23.11.2026', [('A703', 475), ('GS 1', 1425)])."""
    head, sep, tail = str(note or "").partition(":")
    if not sep:
        return "", []
    m = DAY_RE.search(head)
    items = []
    for part in tail.split(","):
        pm = PAIR_RE.match(part)
        if pm:
            items.append((pm.group(1), int(re.sub(r"\D", "", pm.group(2)))))
    return (m.group(1) if m else ""), items


def register(app: Flask, store: Any, docs: Docs, h: dict[str, Any]) -> None:
    login_required = h["login_required"]

    def sheets() -> list[dict[str, Any]]:
        try:
            cat = store.public_catalog()
        except Exception:  # noqa: BLE001 — без цен CRM страница всё равно показывает листы, просто без сверки
            cat = {}
        out = []
        for d in docs.list(FOLDER):
            if d["mime"] not in IMAGES:
                continue
            day, items = parse_note(d["note"])
            title = re.sub(r"^\d+\.\s*", "", d["title"])
            stale = [(a, p, int(cat[a]["p"])) for a, p in items if a in cat and int(cat[a]["p"]) != p]
            gone = [a for a, _ in items if cat and a not in cat]
            out.append({"id": d["id"], "title": title, "section": re.split(r" — |, лист ", title)[0], "filename": d["filename"],
                        "mime": d["mime"], "size_h": size_h(d["size"]), "day": day, "arts": [a for a, _ in items],
                        "stale": stale, "gone": gone,
                        # по этой строке ищет поле поиска: название листа, артикулы и названия товаров («орех», «плинтус»)
                        "find": " ".join([title] + [a for a, _ in items]
                                         + [getattr(store.catalog.get(a), "name", "") for a, _ in items]).lower()})
        return out

    @app.route("/avito-katalog")
    @login_required
    def avito_katalog_view() -> Any:
        rows = sheets()
        sections: list[tuple[str, list[dict[str, Any]]]] = []
        for r in rows:
            if not sections or sections[-1][0] != r["section"]:
                sections.append((r["section"], []))
            sections[-1][1].append(r)
        days = sorted({r["day"] for r in rows if r["day"]}, key=lambda s: s[6:] + s[3:5] + s[:2])
        return render_template("avito_katalog.html", sections=sections, n=len(rows), n_items=sum(len(r["arts"]) for r in rows),
                               bad=[r for r in rows if r["stale"] or r["gone"]], days=days, FOLDER=FOLDER)

    @app.route("/avito-katalog/f/<did>")
    @login_required
    def avito_katalog_file(did: str) -> Any:
        r, path = docs.get(did), docs.path(did)
        if not r or not path or r["folder"] != FOLDER or r["mime"] not in IMAGES:      # другие документы отсюда не достать
            abort(404, "Листа нет.")
        dl = request.args.get("dl") == "1"
        resp = send_file(str(path), mimetype="application/octet-stream" if dl else r["mime"], as_attachment=dl,
                         download_name=r["filename"], max_age=0)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        # файл документа не меняется (новая версия — новый id), поэтому телефон может держать картинку у себя
        resp.headers["Cache-Control"] = "private, max-age=604800, immutable"
        if not dl:
            resp.headers["Content-Security-Policy"] = "sandbox"
        return resp
