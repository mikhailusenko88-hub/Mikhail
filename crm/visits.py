"""Счётчик посещений сайта «Наш декор» — свой, на нашем сервере.

Что приходит с сайта: какая страница открыта, какие разделы долистали, на какие артикулы нажали,
считали ли стену, крутили ли 3D, начали ли и отправили ли заявку, откуда пришли (только адрес сайта-
источника, например yandex.ru) и тип устройства.

Чего нет: cookie, IP-адресов и строки браузера в базе. IP и браузер нужны только в момент прихода
отметки — из них с ключом текущих суток получается обезличенный «номер посетителя на сегодня».
Ключ хранится только для текущих суток и заменяется в новые сутки, после чего связать записи
с человеком нельзя. Записи старше 400 дней удаляются.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS visits (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    day   TEXT NOT NULL,                 -- YYYY-MM-DD (Москва)
    at    TEXT NOT NULL DEFAULT '',      -- ЧЧ:ММ
    vid   TEXT NOT NULL,                 -- обезличенный номер посетителя на эти сутки
    kind  TEXT NOT NULL,
    key   TEXT NOT NULL DEFAULT '',
    act   TEXT NOT NULL DEFAULT '',
    src   TEXT NOT NULL DEFAULT '',
    dev   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS visits_day ON visits(day, kind);
"""

KEEP_DAYS = 400
MAX_EVENTS = 40          # отметок в одной посылке
MAX_PER_DAY = 600        # отметок от одного посетителя за сутки

KINDS = {"view", "sec", "item", "cat", "search", "more", "calc", "calcpanel", "3d", "copy", "form", "lead", "leadfail"}
SECTIONS = [("catalog", "Каталог"), ("calc", "Расчёт стены и 3D"), ("pro", "Дизайнерам"),
            ("terms", "Доставка и оплата"), ("order", "Заявка")]
PAGES = {"/": "Главная", "/oferta.html": "Оферта", "/privacy.html": "Политика", "/consent.html": "Согласие",
         "/dostavka/": "Доставка", "/oplata/": "Оплата и возврат", "/stati/": "Статьи"}
# страницы сайта, которые считаем с 17.11.2026 (раньше счётчик принимал только главную и документы)
CATALOG_PAGES = {"stenovye-paneli": "Стеновые панели", "reechnye-paneli": "Реечные панели под покраску",
                 "paneli-pod-derevo": "Панели под дерево и бетон", "plintusy": "Плинтусы напольные",
                 "plintus-s-podsvetkoy": "Плинтус с подсветкой", "karnizy": "Потолочные плинтусы",
                 "moldingi": "Молдинги", "ugolki": "Уголки"}
ARTICLE_TITLES = {"duropolimer-chto-eto": "Дюрополимер — что это",
                  "kak-kleit-plintus-iz-duropolimera": "Чем клеить плинтус",
                  "kak-otrezat-ugol-potolochnogo-plintusa": "Как отрезать угол потолочного плинтуса",
                  "kak-pokrasit-plintus-i-paneli": "Как покрасить плинтус и панели",
                  "moldingi-na-stene-v-interere": "Молдинги на стене в интерьере",
                  "montazh-stenovyh-panelej": "Монтаж стеновых панелей",
                  "rejki-na-stenu-v-interere": "Рейки на стену в интерьере"}
ITEM_ACTS = {"use": "В расчёт", "ask": "Узнать", "decor": "Выбрали декор", "paint": "Выбрали цвет"}
COPY_NAMES = {"phone": "Скопировали телефон", "max": "Нажали «MAX» — написать в бота",
              "telegram": "Нажали «Telegram» — написать в бота", "channel": "Нажали «Канал в MAX»",
              "tgchannel": "Нажали «Канал в Telegram»", "avito": "Перешли на Авито"}
INTERNAL = "внутри сайта"
DIRECT = "Прямой заход"

BOT_RE = re.compile(r"bot/|bot\)|bot;|crawl|spider|slurp|headless|lighthouse|pagespeed|python|curl/|wget|"
                    r"httpclient|okhttp|go-http|java/|scrapy|puppeteer|playwright|phantomjs|facebookexternalhit|"
                    r"telegrambot|whatsapp|vkshare|preview", re.I)
_KEY_RE = re.compile(r"[A-Za-z0-9_./-]{0,40}")
_SEARCH_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё .,-]{2,30}")
_HOST_RE = re.compile(r"[a-z0-9.-]{1,80}")

_REF = [  # (часть адреса, название)
    (("yandex.", "ya.ru", "dzen.ru"), "Яндекс"),
    (("google.",), "Google"),
    (("avito.",), "Авито"),
    (("t.me", "telegram."), "Telegram"),
    (("max.ru",), "MAX"),
    (("vk.com", "vk.ru", "vk.me", "vkontakte."), "ВКонтакте"),
    (("whatsapp.", "wa.me"), "WhatsApp"),
    (("ok.ru",), "Одноклассники"),
    (("mail.ru",), "Mail.ru"),
    (("bing.",), "Bing"),
    (("duckduckgo.",), "DuckDuckGo"),
    (("instagram.",), "Instagram"),
    (("pinterest.",), "Pinterest"),
    (("houzz.",), "Houzz"),
]
_UTM = {"avito": "Авито", "yandex": "Яндекс", "ya": "Яндекс", "direct": "Яндекс", "google": "Google",
        "telegram": "Telegram", "max": "MAX", "vk": "ВКонтакте", "wa": "WhatsApp",
        "whatsapp": "WhatsApp", "qr": "QR-код", "card": "Визитка",
        # с 17.11.2026: из какого места мессенджера (метки ставят бот и посты каналов)
        "tg": "Telegram — канал", "tg_ch": "Telegram — канал", "tg_bot": "Telegram — бот",
        "max_ch": "MAX — канал", "max_bot": "MAX — бот", "vk_ch": "ВКонтакте", "vk_bot": "ВКонтакте — бот"}
_PROD_RE = re.compile(r"/p/([a-z0-9-]{1,30})/?")
_CAT_RE = re.compile(r"/catalog/([a-z0-9-]{2,40})/?")
_ART_RE = re.compile(r"/stati/([a-z0-9-]{2,70})/?")


def page_name(path: str, catalog: Any = None) -> str:
    """/p/a907/ → «Товар A907 · Реечная панель…»; /catalog/moldingi/ → «Раздел: Молдинги»; /stati/… → «Статья: …»."""
    if path in PAGES:
        return PAGES[path]
    m = _PROD_RE.fullmatch(path)
    if m:
        p = catalog.by_slug(m.group(1)) if catalog is not None and hasattr(catalog, "by_slug") else None
        return f"Товар {p.article}" + (f" · {p.name.replace(p.article, '').strip(' ·,—-')}" if p and p.name else "") if p else path
    m = _CAT_RE.fullmatch(path)
    if m:
        return "Раздел: " + CATALOG_PAGES.get(m.group(1), m.group(1))
    m = _ART_RE.fullmatch(path)
    if m:
        slug = m.group(1)
        title = ARTICLE_TITLES.get(slug) or next((t for k, t in ARTICLE_TITLES.items() if k.startswith(slug)), slug)
        return "Статья: " + title
    return path


def page_kind(path: str) -> str:
    if path == "/":
        return "home"
    if path.startswith("/p/"):
        return "product"
    if path.startswith("/catalog/"):
        return "catalog"
    if path.startswith("/stati/"):
        return "article"
    return "info"


def source(ref_host: str, utm: str, shop_domain: str) -> str:
    u = (utm or "").strip().lower()[:30]
    if u:
        return _UTM.get(u) or ("Метка: " + re.sub(r"[^a-z0-9_-]", "", u)[:20] if re.sub(r"[^a-z0-9_-]", "", u) else DIRECT)
    h = (ref_host or "").strip().lower()
    if not h or not _HOST_RE.fullmatch(h):
        return DIRECT
    if h.startswith("www."):
        h = h[4:]
    if shop_domain and (h == shop_domain or h.endswith("." + shop_domain)):
        return INTERNAL
    for parts, name in _REF:
        if any(p in h for p in parts):
            return name
    return h[:40]


def device(ua: str, coarse: bool) -> str:
    u = ua or ""
    if "iPad" in u or "Tablet" in u or ("Android" in u and "Mobile" not in u):
        return "Планшет"
    if "iPhone" in u or "Android" in u or "Mobile" in u:
        return "Телефон"
    if "Macintosh" in u and coarse:
        return "Планшет"      # iPad выдаёт себя за Mac
    return "Компьютер"


def is_bot(ua: str) -> bool:
    return not ua or bool(BOT_RE.search(ua))


class Visits:
    """Работает поверх базы CRM (store.Store)."""

    def __init__(self, store: Any, shop_domain: str = "") -> None:
        self.store = store
        self.shop_domain = (shop_domain or "").lower()
        c = store.c()
        for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
            c.execute(stmt)

    # ------------------------------------------------------------ ключ суток
    def _salt(self, day: str) -> str:
        c = self.store.c()
        row = c.execute("SELECT value FROM settings WHERE key='visit_salt'").fetchone()
        if row and row[0].startswith(day + ":"):
            return row[0].split(":", 1)[1]
        c.execute("BEGIN IMMEDIATE")
        try:
            row = c.execute("SELECT value FROM settings WHERE key='visit_salt'").fetchone()
            if row and row[0].startswith(day + ":"):
                salt = row[0].split(":", 1)[1]
            else:  # новые сутки: старый ключ стираем, новый — случайный
                salt = secrets.token_hex(32)
                c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('visit_salt', ?)", (f"{day}:{salt}",))
                old = (date.fromisoformat(day) - timedelta(days=KEEP_DAYS)).isoformat()
                c.execute("DELETE FROM visits WHERE day < ?", (old,))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return salt

    def visitor(self, day: str, ip: str, ua: str) -> str:
        return hmac.new(self._salt(day).encode(), f"{ip}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]

    # ------------------------------------------------------------ приём отметок
    def clean(self, raw: Any) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        if not isinstance(raw, list):
            return out
        for e in raw[:MAX_EVENTS]:
            if not isinstance(e, (list, tuple)) or not e:
                continue
            kind = str(e[0])[:12]
            key = str(e[1]).strip()[:80 if kind == "view" else 40] if len(e) > 1 and e[1] is not None else ""
            act = str(e[2])[:10] if len(e) > 2 and e[2] is not None else ""
            if kind not in KINDS:
                continue
            if kind == "view":
                key = self.view_key(key)
                if not key:
                    continue
            elif kind == "sec":
                if key not in dict(SECTIONS):
                    continue
            elif kind in ("item", "calcpanel"):
                p = self.store.catalog.get(key)
                if not p:
                    continue
                key = p.article
                if kind == "item" and act not in ITEM_ACTS:
                    continue
            elif kind == "search":
                key = key.lower()
                if not _SEARCH_RE.fullmatch(key) or sum(ch.isdigit() for ch in key) > 4:
                    continue   # длинные цифры не храним — вдруг это телефон
            elif kind == "copy":
                if key not in COPY_NAMES:
                    continue
            elif kind == "cat":
                if not _KEY_RE.fullmatch(key):
                    continue
            else:
                key = ""
            if kind != "item":
                act = ""
            out.append((kind, key, act))
        return out

    def view_key(self, raw: str) -> str:
        """Адрес открытой страницы → как храним; пусто — не считаем (служебные и несуществующие страницы)."""
        key = (raw or "").split("?", 1)[0].split("#", 1)[0].lower()
        if key.endswith("/index.html"):
            key = key[:-len("index.html")]
        key = "/" if key in ("", "/index.html") else key
        if key in PAGES:
            return key
        m = _PROD_RE.fullmatch(key)
        if m:
            by_slug = getattr(self.store.catalog, "by_slug", None)
            return f"/p/{m.group(1)}/" if by_slug and by_slug(m.group(1)) else ""
        m = _CAT_RE.fullmatch(key)
        if m:
            return f"/catalog/{m.group(1)}/" if m.group(1) in CATALOG_PAGES else ""
        m = _ART_RE.fullmatch(key)
        if m:   # длинный адрес статьи сайт мог обрезать — оставляем как есть, название найдём по началу
            return key if key.endswith("/") or len(key) >= 36 else key + "/"
        return ""

    def add(self, *, day: str, at: str, ip: str, ua: str, body: dict[str, Any]) -> int:
        events = self.clean(body.get("e"))
        if not events:
            return 0
        vid = self.visitor(day, ip, ua)
        src = source(str(body.get("r") or ""), str(body.get("u") or ""), self.shop_domain)
        dev = device(ua, bool(body.get("m")))
        c = self.store.c()
        n = c.execute("SELECT COUNT(*) FROM visits WHERE day=? AND vid=?", (day, vid)).fetchone()[0]
        room = MAX_PER_DAY - int(n)
        if room <= 0:
            return 0
        events = events[:room]
        c.execute("BEGIN IMMEDIATE")
        try:
            c.executemany("INSERT INTO visits(day, at, vid, kind, key, act, src, dev) VALUES (?,?,?,?,?,?,?,?)",
                          [(day, at, vid, k, key, act, src, dev) for k, key, act in events])
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return len(events)

    # ------------------------------------------------------------ отчёт
    def brief(self, day: str) -> dict[str, int]:
        c = self.store.c()
        y = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        def n(d: str, kind: str) -> int:
            return int(c.execute("SELECT COUNT(DISTINCT vid) FROM visits WHERE day=? AND kind=?", (d, kind)).fetchone()[0])
        return {"today": n(day, "view"), "yesterday": n(y, "view"), "leads": n(day, "lead")}

    def count(self) -> int:
        return int(self.store.c().execute("SELECT COUNT(*) FROM visits").fetchone()[0])

    def clear(self) -> int:
        """Обнулить статистику сайта (все отметки). Возвращает, сколько удалено."""
        c = self.store.c()
        n = self.count()
        c.execute("DELETE FROM visits")
        c.commit()
        return n

    def report(self, day: str, days: int) -> dict[str, Any]:
        days = max(1, min(int(days), KEEP_DAYS))
        start = (date.fromisoformat(day) - timedelta(days=days - 1)).isoformat()
        rows = self.store.c().execute(
            "SELECT day, vid, kind, key, act, src, dev FROM visits WHERE day>=? AND day<=? ORDER BY id",
            (start, day)).fetchall()
        who: dict[tuple[str, str], dict[str, Any]] = {}
        cat = self.store.catalog
        views = 0
        pages: dict[str, set] = defaultdict(set)
        items: dict[str, dict[str, Any]] = {}
        searches: dict[str, int] = defaultdict(int)
        cats: dict[str, int] = defaultdict(int)
        for r in rows:
            v = (r["day"], r["vid"])
            w = who.setdefault(v, {"src": "", "dev": r["dev"], "did": set(), "secs": set(), "pk": set()})
            k = r["kind"]
            w["did"].add(k)
            if k == "view":
                views += 1
                pages[r["key"]].add(v)
                w["pk"].add(page_kind(r["key"]))
                if not w["src"] and r["src"] != INTERNAL:
                    w["src"] = r["src"]
                m = _PROD_RE.fullmatch(r["key"])
                p = cat.by_slug(m.group(1)) if m and hasattr(cat, "by_slug") else None
                if p:
                    it = items.setdefault(p.article, {"who": set(), "use": 0, "ask": 0, "decor": 0, "paint": 0, "calc": 0, "opened": set()})
                    it["who"].add(v)
                    it.setdefault("opened", set()).add(v)
            elif k == "sec":
                w["secs"].add(r["key"])
            elif k in ("item", "calcpanel"):
                it = items.setdefault(r["key"], {"who": set(), "use": 0, "ask": 0, "decor": 0, "paint": 0, "calc": 0, "opened": set()})
                it["who"].add(v)
                if k == "item":
                    it[r["act"]] = it.get(r["act"], 0) + 1
                else:
                    it["calc"] += 1
            elif k == "search":
                searches[r["key"]] += 1
            elif k == "cat":
                cats[r["key"]] += 1
            elif k == "copy":
                w["did"].add("copy:" + r["key"])
        visitors = [w for w in who.values() if "view" in w["did"]]
        total = len(visitors)

        def count(pred: Any) -> int:
            return sum(1 for w in visitors if pred(w))

        by_day = []
        d0 = date.fromisoformat(start)
        per_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for (d, _), w in who.items():
            if "view" in w["did"]:
                per_day[d][0] += 1
            if "lead" in w["did"]:
                per_day[d][1] += 1
        view_day: dict[str, int] = defaultdict(int)
        for r in rows:
            if r["kind"] == "view":
                view_day[r["day"]] += 1
        for i in range(days):
            d = (d0 + timedelta(days=i)).isoformat()
            by_day.append({"day": d, "visitors": per_day[d][0], "views": view_day[d], "leads": per_day[d][1]})
        by_day.reverse()

        def tally(key: str) -> list[tuple[str, int]]:
            t: dict[str, int] = defaultdict(int)
            for w in visitors:
                t[w[key] or DIRECT] += 1
            return sorted(t.items(), key=lambda x: (-x[1], x[0]))

        funnel = [
            ("Зашли на сайт", total),
            ("Смотрели каталог", count(lambda w: "catalog" in w["secs"] or w["did"] & {"item", "cat", "search", "more"}
                                       or w["pk"] & {"product", "catalog"})),
            ("Открывали страницы товаров", count(lambda w: "product" in w["pk"])),
            ("Нажимали на товары", count(lambda w: "item" in w["did"])),
            ("Считали стену", count(lambda w: w["did"] & {"calc", "calcpanel"})),
            ("Крутили 3D-стену", count(lambda w: "3d" in w["did"])),
            ("Начали заполнять заявку", count(lambda w: "form" in w["did"])),
            ("Отправили заявку", count(lambda w: "lead" in w["did"])),
        ]
        sections = [(name, count(lambda w, s=s: s in w["secs"])) for s, name in SECTIONS]
        copies = [(name, count(lambda w, k=k: "copy:" + k in w["did"])) for k, name in COPY_NAMES.items()]
        item_rows = []
        for a, it in items.items():
            p = cat.get(a)
            item_rows.append({"article": a, "name": (p.name.replace(a, "").strip(" ·,—-") if p else ""), "visitors": len(it["who"]),
                              "opened": len(it.get("opened") or ()),
                              "use": it["use"], "ask": it["ask"], "color": it["decor"] + it["paint"], "calc": it["calc"]})
        item_rows.sort(key=lambda x: (-x["visitors"], -(x["use"] + x["ask"] + x["color"] + x["calc"]), x["article"]))
        return {
            "days": days, "start": start, "end": day, "visitors": total, "views": views,
            "leads": count(lambda w: "lead" in w["did"]),
            "by_day": by_day, "sources": tally("src"), "devices": tally("dev"),
            "funnel": funnel, "sections": sections, "copies": [c for c in copies if c[1]],
            "items": item_rows[:60],
            "searches": sorted(searches.items(), key=lambda x: (-x[1], x[0]))[:20],
            "cats": sorted(cats.items(), key=lambda x: (-x[1], x[0])),
            "pages": sorted(((page_name(p, cat), len(s)) for p, s in pages.items()), key=lambda x: (-x[1], x[0]))[:60],
            "copy_counts": {k: count(lambda w, k=k: "copy:" + k in w["did"]) for k in COPY_NAMES},
        }


def parse_body(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8", "replace")[:20000])
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
