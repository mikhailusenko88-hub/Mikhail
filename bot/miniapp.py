"""Мини-приложение MAX = наш сайт внутри MAX. Ссылка на сайт → параметр запуска (startapp) для кнопки open_app.

Те же правила разбирает assets/max.js на сайте (ветка mebel). Используют бот (max_api.render) и channel.py.
Только стандартная библиотека: channel.py запускается системным python3.
"""
from __future__ import annotations

import re
import urllib.parse

SITE_HOSTS = {"nashdekor.ru", "www.nashdekor.ru"}
APP_BLOCKS = {"calc", "catalog", "models", "order", "contacts", "live", "pro"}   # блоки главной (id на странице)
APP_PAGES = {"/dostavka/": "dostavka", "/oplata/": "oplata", "/stati/": "stati"}
APP_DIRS = {"catalog": "c-", "p": "p-", "stati": "s-"}
_SLUG = re.compile(r"[a-z0-9-]{1,60}")


def app_payload(url: str) -> str | None:
    """"" — главная без параметра; None — ссылка не на сайт или такой раздел не открывается (останется ссылкой)."""
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if u.scheme != "https" or (u.hostname or "") not in SITE_HOSTS:
        return None
    path, frag = u.path or "/", u.fragment
    if path == "/":
        if not frag:
            return ""
        if frag not in APP_BLOCKS:
            return None
        q = urllib.parse.parse_qs(u.query)
        panel = (q.get("panel") or [""])[0].lower()
        if frag != "calc" or not _SLUG.fullmatch(panel):
            return frag
        w, h = (q.get("w") or [""])[0], (q.get("h") or [""])[0]
        dims = f"_{w}_{h}" if re.fullmatch(r"\d{1,4}", w) and re.fullmatch(r"\d{1,4}", h) else ""
        return f"calc-{panel}{dims}"
    if frag:
        return None
    if path in APP_PAGES:
        return APP_PAGES[path]
    m = re.fullmatch(r"/(catalog|p|stati)/([a-z0-9-]{1,60})/", path)
    return APP_DIRS[m.group(1)] + m.group(2) if m else None


def open_app(text: str, url: str, app: str) -> dict | None:
    """Кнопка, открывающая сайт внутри MAX, или None (тогда — обычная ссылка). app — публичное имя бота."""
    pl = app_payload(url) if app else None
    if pl is None:
        return None
    return {"type": "open_app", "text": text, "web_app": app, **({"payload": pl} if pl else {})}
