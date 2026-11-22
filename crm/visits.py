"""Счётчик посещений сайта «Наш декор» — свой, на нашем сервере.

Что приходит с сайта: какая страница открыта, какие разделы долистали, на какие артикулы нажали,
считали ли стену, крутили ли 3D, начали ли и отправили ли заявку, откуда пришли (только адрес сайта-
источника, например yandex.ru) и тип устройства.

С 23.11.2026 — подробные отметки (assets/an.js на сайте): сколько секунд страница была на экране, докуда долистали,
какие блоки страницы и сколько смотрели, нажатия «в пустоту» (ничего не произошло) и частые нажатия в одно место,
какое фото товара открыли, за сколько загрузилась страница, ошибки страницы. Город — по IP в момент прихода отметки
(geo.py), сам IP не пишется. Выключаются одной галочкой в CRM («Сайт» внизу) — тогда принимается только прежнее.

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
CREATE INDEX IF NOT EXISTS visits_vid ON visits(day, vid);
CREATE TABLE IF NOT EXISTS visit_deals (     -- заявка с сайта → что этот посетитель смотрел в тот день
    deal_id INTEGER PRIMARY KEY,
    day     TEXT NOT NULL,
    vid     TEXT NOT NULL
);
"""
NEW_COLUMNS = (("city", "TEXT NOT NULL DEFAULT ''"),   # город по IP (сам IP не храним)
               ("app", "TEXT NOT NULL DEFAULT ''"),    # открыто внутри приложения (Telegram, ВКонтакте, Авито…)
               ("camp", "TEXT NOT NULL DEFAULT ''"))   # utm_campaign из ссылки с меткой

KEEP_DAYS = 400
MAX_EVENTS = 40          # отметок в одной посылке
MAX_PER_DAY = 1500       # отметок от одного посетителя за сутки (с подробными отметками их больше)

# подробные отметки (с 23.11.2026, assets/an.js): относятся к странице из поля p посылки
DEEP_KINDS = {"time", "scroll", "blk", "dead", "rage", "photo", "load", "err"}
KINDS = {"view", "sec", "item", "cat", "search", "more", "calc", "calcpanel", "3d", "copy", "form", "lead", "leadfail", "iv"} | DEEP_KINDS
SCROLL_MARKS = ("25", "50", "75", "90", "100")
# блоки страниц (data-an на сайте) → подпись; новый блок без подписи показывается как есть
BLOCK_NAMES = {"top": "Первый экран", "catalog": "Каталог", "calc": "Расчёт стены", "live": "Панели в интерьере",
               "pro": "Дизайнерам", "order": "Заявка", "terms": "Доставка и оплата", "footer": "Подвал (контакты)",
               "photo": "Фото / 3D товара", "buy": "Цена и кнопки заказа", "colors": "Выбор цвета", "wall": "Расчёт на стену",
               "about": "Описание и размеры", "rel": "Ещё в разделе", "list": "Список товаров", "text": "Текст страницы",
               "cart": "Корзина", "ship": "Доставка в другой город", "faq": "Вопросы и ответы",
               "title": "Название и описание", "gallery": "Ещё фото", "profile": "Профиль (сечение)", "specs": "Характеристики",
               "reviews": "Отзывы", "with": "С этим берут", "head": "Заголовок раздела", "sections": "Вкладки разделов",
               "more": "Другие статьи", "other": "Вне блоков"}
PAGE_KINDS = {"home": "Главная", "product": "Страница товара", "catalog": "Раздел каталога", "article": "Статья", "info": "Другие страницы"}
APPS = [(re.compile(r"Telegram", re.I), "Telegram"), (re.compile(r"VKAndroidApp|VKClient|com\.vk\.|vkontakte", re.I), "ВКонтакте"),
        (re.compile(r"Instagram"), "Instagram"), (re.compile(r"FBAN|FBAV|FB_IAB"), "Facebook"), (re.compile(r"avito", re.I), "Авито"),
        (re.compile(r"YaApp|YaSearchBrowser|YandexSearch"), "Яндекс"), (re.compile(r"OneMe|MAX/\d"), "MAX"),
        (re.compile(r"OdnoklassnikiApp|OKApp", re.I), "Одноклассники"), (re.compile(r"MailRuApp|MRMail"), "Почта Mail.ru"),
        (re.compile(r"Viber"), "Viber")]
DEFAULT_SPAM = ("aimanhunt.online",)   # реферальный спам: подставляют свой адрес в «откуда пришли» (22.11.2026)
_BLK_RE = re.compile(r"[a-z0-9_-]{1,24}")
_DESC_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё _.#:/«»,()+-]{1,60}")
_CAMP_RE = re.compile(r"[0-9a-zа-яё_.-]{1,40}")
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
ITEM_ACTS = {"use": "В расчёт", "ask": "Узнать", "decor": "Выбрали декор", "paint": "Выбрали цвет", "order": "Заказать"}
# карусель «панель в интерьере» на главной (с 18.11.2026): кадр = сцена × панель; что делали с кадром
IV_SCENES = {"tvd": "ТВ-зона — крупно", "tv": "ТВ-зона — вся стена", "tv1": "ТВ-зона — полоса за экраном",
             "tv2": "ТВ-зона — две полосы", "tvc": "ТВ-зона — полоса с переходом на потолок",
             "sofad": "У дивана — крупно", "sofa": "За диваном — вся стена", "sofa1": "За диваном — одна полоса",
             "sofa2": "За диваном — две полосы и полка", "bedd": "Спальня — крупно", "bed": "Спальня — вся стена",
             "bed1": "Спальня — полоса за кроватью", "halld": "Прихожая — крупно", "hall": "Прихожая — вся стена",
             "half": "Прихожая — панели до середины стены", "deskd": "Рабочее место — крупно", "desk": "Рабочее место — вся стена",
             "cord": "Коридор — крупно", "cl": "Рельеф крупно"}
IV_ACTS = {"go": "Листали к кадру", "full": "Во весь экран", "zoom": "Приближали"}
_SCENE_RE = re.compile(r"[a-z0-9]{1,12}")
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
        "max_ch": "MAX — канал", "max_bot": "MAX — бот", "vk_ch": "ВКонтакте", "vk_bot": "ВКонтакте — бот",
        # с 23.11.2026: ссылки с меткой из CRM («Сайт» → «Ссылка с меткой»)
        "email": "Письмо", "dz": "Письмо дизайнеру", "avito_chat": "Авито — переписка", "yandex_maps": "Яндекс Карты",
        "2gis": "2ГИС", "print": "Печать (листовка, наклейка)", "other": "Другое"}
KNOWN_SOURCES = {DIRECT, INTERNAL, "QR-код", "Визитка"} | {n for _, n in _REF} | set(_UTM.values())
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


def in_app(ua: str) -> str:
    """Сайт открыт внутри приложения (по строке браузера): «Telegram», «ВКонтакте», «Авито»… или «»."""
    for rx, name in APPS:
        if rx.search(ua or ""):
            return name
    return ""


def _int(v: Any, lo: int, hi: int) -> int | None:
    try:
        n = int(float(str(v)[:12]))
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, n)) if n >= lo else None


def _median(xs: list[int]) -> int:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return 0
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) // 2


def fmt_sec(n: int) -> str:
    """45 → «45 с», 130 → «2 мин 10 с», 3600 → «60 мин»."""
    n = int(n or 0)
    if n < 60:
        return f"{n} с"
    m, s = divmod(n, 60)
    return f"{m} мин" + (f" {s} с" if s and m < 10 else "")


def block_name(blk: str) -> str:
    return BLOCK_NAMES.get(blk, blk)


TAG_NAMES = {"img": "фото", "h1": "заголовок", "h2": "заголовок", "h3": "заголовок", "b": "текст", "span": "текст", "p": "текст",
             "div": "блок", "li": "пункт списка", "td": "таблица", "svg": "значок", "section": "блок", "main": "страница",
             "body": "страница", "html": "страница", "footer": "подвал", "picture": "фото"}


def click_label(on: str) -> str:
    """«buy:b#price «1 950»» → «Цена и кнопки заказа: текст «1 950»» (как место нажатия выглядит для человека)."""
    blk, _, rest = (on or "").partition(":")
    tag, _, text = rest.partition(" «")
    tag = re.split(r"[#.]", tag, 1)[0]
    what = TAG_NAMES.get(tag, tag or "место")
    return f"{block_name(blk)}: {what}" + (f" «{text}" if text else "")


def page_short(path: str, catalog: Any = None) -> str:
    """Короткое название страницы для ленты и таблиц: у товара — до первой запятой."""
    n = page_name(path, catalog)
    return n.split(",", 1)[0] if path.startswith("/p/") else n


ENGAGED = {"item", "calc", "calcpanel", "3d", "copy", "form", "lead", "leadfail", "iv", "search", "cat", "more",
           "dead", "rage", "photo", "blk"}
ACT_NAMES = {"calc": "считал стену", "form": "начал заявку", "lead": "отправил заявку", "leadfail": "заявка не ушла",
             "3d:home": "трогал кадр «в интерьере»", "3d:p": "крутил 3D товара", "more": "«Показать ещё» в каталоге",
             "iv:go": "листал интерьеры", "iv:full": "интерьер во весь экран", "iv:zoom": "приближал интерьер"}


class Visits:
    """Работает поверх базы CRM (store.Store)."""

    def __init__(self, store: Any, shop_domain: str = "") -> None:
        self.store = store
        self.shop_domain = (shop_domain or "").lower()
        c = store.c()
        for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
            if stmt.startswith("--"):
                stmt = "\n".join(x for x in stmt.splitlines() if not x.strip().startswith("--")).strip()
            if stmt:
                c.execute(stmt)
        have = {r[1] for r in c.execute("PRAGMA table_info(visits)").fetchall()}
        for col, decl in NEW_COLUMNS:
            if col not in have:
                c.execute(f"ALTER TABLE visits ADD COLUMN {col} {decl}")
        c.commit()

    # ------------------------------------------------------------ настройки
    def deep_on(self) -> bool:
        """Подробные отметки (прокрутка, блоки, время…) — аварийный выключатель в CRM «Сайт»."""
        return self.store.setting("visit_deep", "1") != "0"

    def set_deep(self, on: bool) -> None:
        self.store.set_setting("visit_deep", "1" if on else "0")

    def spam_hosts(self) -> set[str]:
        own = {h for h in self.store.setting("visit_spam", "").split() if h}
        off = {h for h in self.store.setting("visit_spam_off", "").split() if h}
        return (set(DEFAULT_SPAM) | own) - off

    def mark_spam(self, host: str, on: bool) -> bool:
        h = (host or "").strip().lower()
        if h.startswith("www."):
            h = h[4:]
        if not _HOST_RE.fullmatch(h) or "." not in h or h in KNOWN_SOURCES:
            return False
        own = [x for x in self.store.setting("visit_spam", "").split() if x and x != h]
        off = [x for x in self.store.setting("visit_spam_off", "").split() if x and x != h]
        if on:
            own.append(h)
        elif h in DEFAULT_SPAM:
            off.append(h)
        self.store.set_setting("visit_spam", "\n".join(own[-200:]))
        self.store.set_setting("visit_spam_off", "\n".join(off[-200:]))
        return True

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
                c.execute("DELETE FROM visit_deals WHERE day < ?", (old,))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return salt

    def visitor(self, day: str, ip: str, ua: str) -> str:
        return hmac.new(self._salt(day).encode(), f"{ip}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]

    # ------------------------------------------------------------ приём отметок
    def clean(self, raw: Any, page: str = "") -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        if not isinstance(raw, list):
            return out
        deep = None
        for e in raw[:MAX_EVENTS]:
            if not isinstance(e, (list, tuple)) or not e:
                continue
            kind = str(e[0])[:12]
            lim = 80 if kind == "view" else 60 if kind in DEEP_KINDS else 40
            key = str(e[1]).strip()[:lim] if len(e) > 1 and e[1] is not None else ""
            act = str(e[2])[:10] if len(e) > 2 and e[2] is not None else ""
            if kind not in KINDS:
                continue
            if kind in DEEP_KINDS:
                if deep is None:
                    deep = self.deep_on()
                got = self._clean_deep(kind, key, act, page) if deep and page else None
                if got:
                    out.append(got)
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
            elif kind == "iv":   # «tv1.a907» + go/full/zoom → «tv1|A907»
                scene, _, slug = key.partition(".")
                by_slug = getattr(self.store.catalog, "by_slug", None)
                p = by_slug(slug) if by_slug and slug else None
                if not _SCENE_RE.fullmatch(scene) or not p or act not in IV_ACTS:
                    continue
                key = f"{scene}|{p.article}"
            elif kind == "3d":   # главная (кадр «в интерьере») — без артикула; страница товара — с артикулом
                key = "p" if key else ""
            else:
                key = ""
            if kind not in ("item", "iv"):
                act = ""
            out.append((kind, key, act))
        return out

    def _clean_deep(self, kind: str, key: str, act: str, page: str) -> tuple[str, str, str] | None:
        """Подробная отметка → (вид, ключ, значение); ключ — адрес страницы (+ блок / место нажатия)."""
        if kind == "time":                 # секунд на экране (сайт шлёт нарастающим итогом — берём наибольшее)
            n = _int(act, 1, 3600)
            return (kind, page, str(n)) if n else None
        if kind == "scroll":               # докуда долистали, %
            return (kind, page, act) if act in SCROLL_MARKS else None
        if kind == "blk":                  # блок страницы был на экране N секунд
            n = _int(act, 1, 3600)
            return (kind, f"{page}#{key}", str(n)) if n and _BLK_RE.fullmatch(key) else None
        if kind in ("dead", "rage"):       # нажали — ничего не произошло / нажимали много раз подряд
            return (kind, f"{page}|{key}", "") if _DESC_RE.fullmatch(key) else None
        if kind == "photo":                # открыли фото товара №N
            p = self.store.catalog.get(key)
            n = _int(act, 1, 40)
            return (kind, p.article, str(n)) if p and n else None
        if kind == "load":                 # страница загрузилась за N мс
            n = _int(act, 1, 120000)
            return (kind, page, str(n)) if n else None
        if kind == "err":                  # ошибка скрипта на странице (только наши файлы)
            return (kind, f"{page}|{key if _DESC_RE.fullmatch(key) else 'ошибка'}", "")
        return None

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

    def add(self, *, day: str, at: str, ip: str, ua: str, body: dict[str, Any], city: str = "") -> int:
        if body.get("w"):                  # автоматический браузер (navigator.webdriver) — не человек
            return 0
        page = self.view_key(str(body.get("p") or "")) if body.get("p") else ""
        events = self.clean(body.get("e"), page)
        if not events:
            return 0
        vid = self.visitor(day, ip, ua)
        src = source(str(body.get("r") or ""), str(body.get("u") or ""), self.shop_domain)
        dev = device(ua, bool(body.get("m")))
        app = in_app(ua)
        camp = str(body.get("c") or "").strip().lower()[:40]
        camp = camp if _CAMP_RE.fullmatch(camp) else ""
        city = (city or "")[:60]
        c = self.store.c()
        n = c.execute("SELECT COUNT(*) FROM visits WHERE day=? AND vid=?", (day, vid)).fetchone()[0]
        room = MAX_PER_DAY - int(n)
        if room <= 0:
            return 0
        events = events[:room]
        c.execute("BEGIN IMMEDIATE")
        try:
            c.executemany("INSERT INTO visits(day, at, vid, kind, key, act, src, dev, city, app, camp) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          [(day, at, vid, k, key, act, src, dev, city, app, camp) for k, key, act in events])
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return len(events)

    # ------------------------------------------------------------ заявка → что смотрел на сайте
    def link_deal(self, deal_id: int, day: str, ip: str, ua: str) -> None:
        """Заявка с сайта: запоминаем обезличенный номер посетителя на этот день (сам IP не храним)."""
        vid = self.visitor(day, ip, ua)
        c = self.store.c()
        c.execute("INSERT OR IGNORE INTO visit_deals(deal_id, day, vid) VALUES (?,?,?)", (int(deal_id), day, vid))
        c.commit()

    def deal_path(self, deal_id: int) -> dict[str, Any] | None:
        row = self.store.c().execute("SELECT day, vid FROM visit_deals WHERE deal_id=?", (int(deal_id),)).fetchone()
        if not row:
            return None
        rows = self.store.c().execute("SELECT id, day, at, vid, kind, key, act, src, dev, city, app, camp FROM visits"
                                      " WHERE day=? AND vid=? ORDER BY id", (row["day"], row["vid"])).fetchall()
        who = self._people(rows)
        w = who.get((row["day"], row["vid"]))
        return self._feed_item(w) if w and w["seq"] else None

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
        c.execute("DELETE FROM visit_deals")
        c.commit()
        return n

    def _people(self, rows: list[Any]) -> dict[tuple[str, str], dict[str, Any]]:
        """Отметки → посетители (день, номер): откуда, путь по страницам со временем и прокруткой, что делал."""
        who: dict[tuple[str, str], dict[str, Any]] = {}
        cat = self.store.catalog
        for r in rows:
            v = (r["day"], r["vid"])
            w = who.get(v)
            if w is None:
                w = who[v] = {"day": r["day"], "vid": r["vid"], "src": "", "dev": r["dev"], "did": set(), "secs": set(), "pk": set(),
                              "seq": [], "first": r["at"], "last": r["at"], "city": "", "app": "", "camp": "", "acts": [],
                              "views": 0, "photos": set(), "searches": []}
            w["last"] = r["at"] or w["last"]
            keys = r.keys()
            if not w["city"] and "city" in keys and r["city"]:
                w["city"] = r["city"]
            if not w["app"] and "app" in keys and r["app"]:
                w["app"] = r["app"]
            if not w["camp"] and "camp" in keys and r["camp"]:
                w["camp"] = r["camp"]
            k = r["kind"]
            w["did"].add(k)
            if k == "view":
                w["views"] += 1
                w["pk"].add(page_kind(r["key"]))
                if not w["src"] and r["src"] != INTERNAL:
                    w["src"] = r["src"]
                w["seq"].append({"path": r["key"], "name": page_short(r["key"], cat), "at": r["at"], "sec": 0, "scroll": 0,
                                 "blk": {}, "dead": 0, "rage": 0, "load": 0})
            elif k in ("time", "scroll", "blk", "dead", "rage", "load", "err"):
                path, sep, rest = r["key"].partition("#" if k == "blk" else "|")
                ent = next((x for x in reversed(w["seq"]) if x["path"] == path), None)
                if ent is None:
                    continue
                if k == "time":
                    ent["sec"] = max(ent["sec"], int(r["act"] or 0))
                elif k == "scroll":
                    ent["scroll"] = max(ent["scroll"], int(r["act"] or 0))
                elif k == "blk":
                    ent["blk"][rest] = max(ent["blk"].get(rest, 0), int(r["act"] or 0))
                elif k == "load":
                    ent["load"] = ent["load"] or int(r["act"] or 0)
                elif k in ("dead", "rage"):
                    ent[k] += 1
                    ent.setdefault(k + "_on", []).append(rest)
                elif k == "err":
                    ent.setdefault("err", []).append(rest)
            elif k == "sec":
                w["secs"].add(r["key"])
            elif k == "copy":
                w["did"].add("copy:" + r["key"])
                w["acts"].append(COPY_NAMES.get(r["key"], r["key"]))
            elif k == "3d":
                w["did"].add("3d:p" if r["key"] == "p" else "3d:home")
            elif k == "iv":
                w["did"].add("iv:" + (r["act"] or "go"))
            elif k == "item":
                w["acts"].append(f"{ITEM_ACTS.get(r['act'], r['act'])} {r['key']}")
            elif k == "calcpanel":
                w["acts"].append(f"в расчёте {r['key']}")
            elif k == "photo":
                w["photos"].add((r["key"], r["act"]))
            elif k == "search":
                w["searches"].append(r["key"])
        return who

    def _robot(self, w: dict[str, Any], spam: set[str]) -> str:
        """Почему не считаем посетителя человеком: «спам-ссылка» / «похоже на робота» / «»."""
        src = w["src"] or DIRECT
        if src in spam:
            return "спам-ссылка"
        unknown_site = src not in KNOWN_SOURCES and not src.startswith("Метка: ")
        if not unknown_site:
            return ""
        engaged = bool(w["did"] & ENGAGED)
        longest = max([x["sec"] for x in w["seq"]] or [0])
        deepest = max([x["scroll"] for x in w["seq"]] or [0])
        if not engaged and w["views"] <= 1 and longest < 5 and deepest < 50:
            return "похоже на робота"
        return ""

    def _feed_item(self, w: dict[str, Any]) -> dict[str, Any]:
        acts: list[str] = []
        for k, name in ACT_NAMES.items():
            if k in w["did"]:
                acts.append(name)
        acts += [a for a in w["acts"] if a not in acts]
        if w["photos"]:
            acts.append("листал фото: " + ", ".join(sorted({f"{a} №{n}" for a, n in w["photos"]}))[:120])
        if w["searches"]:
            acts.append("искал: " + ", ".join(f"«{q}»" for q in w["searches"][:5]))
        pages = []
        for x in w["seq"]:
            blk = sorted(x["blk"].items(), key=lambda kv: -kv[1])
            pages.append({"path": x["path"], "name": x["name"], "at": x["at"], "sec": x["sec"], "scroll": x["scroll"],
                          "load": x["load"], "dead": x["dead"], "rage": x["rage"],
                          "dead_on": [click_label(o) for o in x.get("dead_on", [])[:5]], "rage_on": [click_label(o) for o in x.get("rage_on", [])[:5]],
                          "dead_raw": x.get("dead_on", [])[:5], "rage_raw": x.get("rage_on", [])[:5], "err": x.get("err", [])[:3],
                          "blk": [(b, block_name(b), s) for b, s in blk[:8]]})
        src = w["src"] or DIRECT
        return {"day": w["day"], "first": w["first"], "last": w["last"], "src": src, "app": w["app"], "camp": w["camp"],
                "city": w["city"], "dev": w["dev"], "pages": pages, "acts": acts, "lead": "lead" in w["did"],
                "robot": w.get("robot", ""), "total_sec": sum(x["sec"] for x in w["seq"])}

    @staticmethod
    def src_label(w: dict[str, Any]) -> str:
        src = w["src"] or DIRECT
        if src == DIRECT and w.get("app"):
            return f"{DIRECT} · из приложения {w['app']}"
        return src

    def report(self, day: str, days: int, feed_limit: int = 150) -> dict[str, Any]:
        days = max(1, min(int(days), KEEP_DAYS))
        start = (date.fromisoformat(day) - timedelta(days=days - 1)).isoformat()
        rows = self.store.c().execute(
            "SELECT id, day, at, vid, kind, key, act, src, dev, city, app, camp FROM visits WHERE day>=? AND day<=? ORDER BY id",
            (start, day)).fetchall()
        who = self._people(rows)
        spam = self.spam_hosts()
        filtered: dict[tuple[str, str], int] = defaultdict(int)
        for w in who.values():
            if "view" in w["did"]:
                w["robot"] = self._robot(w, spam)
                if w["robot"]:
                    filtered[(w["src"] or DIRECT, w["robot"])] += 1
        robots = {v for v, w in who.items() if w.get("robot")}
        cat = self.store.catalog
        views = 0
        pages: dict[str, set] = defaultdict(set)
        items: dict[str, dict[str, Any]] = {}
        searches: dict[str, int] = defaultdict(int)
        cats: dict[str, int] = defaultdict(int)
        iv_scenes: dict[str, dict[str, set]] = {}
        iv_panels: dict[str, set] = defaultdict(set)
        photos: dict[tuple[str, str], set] = defaultdict(set)
        for r in rows:
            v = (r["day"], r["vid"])
            if v in robots:
                continue
            k = r["kind"]
            if k == "view":
                views += 1
                pages[r["key"]].add(v)
                m = _PROD_RE.fullmatch(r["key"])
                p = cat.by_slug(m.group(1)) if m and hasattr(cat, "by_slug") else None
                if p:
                    it = items.setdefault(p.article, {"who": set(), "use": 0, "ask": 0, "decor": 0, "paint": 0, "calc": 0, "opened": set()})
                    it["who"].add(v)
                    it.setdefault("opened", set()).add(v)
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
            elif k == "iv":
                scene, _, art = (r["key"] or "").partition("|")
                act = r["act"] or "go"
                sc = iv_scenes.setdefault(scene, {"who": set(), "full": set(), "zoom": set()})
                sc["who"].add(v)
                if act in ("full", "zoom"):
                    sc[act].add(v)
                if art:
                    iv_panels[art].add(v)
            elif k == "photo":
                photos[(r["key"], r["act"])].add(v)
        people = {v: w for v, w in who.items() if v not in robots}
        visitors = [w for w in people.values() if "view" in w["did"]]
        total = len(visitors)

        def count(pred: Any) -> int:
            return sum(1 for w in visitors if pred(w))

        by_day = []
        d0 = date.fromisoformat(start)
        per_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for (d, _), w in people.items():
            if "view" in w["did"]:
                per_day[d][0] += 1
            if "lead" in w["did"]:
                per_day[d][1] += 1
        view_day: dict[str, int] = defaultdict(int)
        for r in rows:
            if r["kind"] == "view" and (r["day"], r["vid"]) not in robots:
                view_day[r["day"]] += 1
        for i in range(days):
            d = (d0 + timedelta(days=i)).isoformat()
            by_day.append({"day": d, "visitors": per_day[d][0], "views": view_day[d], "leads": per_day[d][1]})
        by_day.reverse()

        def tally(key: Any) -> list[tuple[str, int]]:
            t: dict[str, int] = defaultdict(int)
            for w in visitors:
                t[(key(w) if callable(key) else w[key]) or DIRECT] += 1
            return sorted(t.items(), key=lambda x: (-x[1], x[0]))

        funnel = [
            ("Зашли на сайт", total),
            ("Смотрели каталог", count(lambda w: "catalog" in w["secs"] or w["did"] & {"item", "cat", "search", "more"}
                                       or w["pk"] & {"product", "catalog"})),
            ("Открывали страницы товаров", count(lambda w: "product" in w["pk"])),
            ("Нажимали на товары", count(lambda w: "item" in w["did"])),
            ("Считали стену", count(lambda w: w["did"] & {"calc", "calcpanel"})),
            ("Смотрели панели в интерьере (главная)", count(lambda w: w["did"] & {"iv", "3d:home"})),
            ("Крутили 3D на странице товара", count(lambda w: "3d:p" in w["did"])),
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
                              "use": it["use"], "ask": it["ask"] + it.get("order", 0), "color": it["decor"] + it["paint"], "calc": it["calc"]})
        item_rows.sort(key=lambda x: (-x["visitors"], -(x["use"] + x["ask"] + x["color"] + x["calc"]), x["article"]))
        ux = self._ux(visitors, cat)
        feed = sorted((self._feed_item(w) for w in visitors), key=lambda x: (x["day"], x["first"]), reverse=True)
        return {
            "days": days, "start": start, "end": day, "visitors": total, "views": views,
            "leads": count(lambda w: "lead" in w["did"]),
            "by_day": by_day, "sources": tally(self.src_label), "devices": tally("dev"),
            "funnel": funnel, "sections": sections, "copies": [c for c in copies if c[1]],
            "items": item_rows[:60],
            "searches": sorted(searches.items(), key=lambda x: (-x[1], x[0]))[:20],
            "cats": sorted(cats.items(), key=lambda x: (-x[1], x[0])),
            "pages": sorted(((page_name(p, cat), len(s)) for p, s in pages.items()), key=lambda x: (-x[1], x[0]))[:60],
            "copy_counts": {k: count(lambda w, k=k: "copy:" + k in w["did"]) for k in COPY_NAMES},
            "iv": {
                "touched": count(lambda w: w["did"] & {"iv", "3d:home"}),
                "go": count(lambda w: "iv:go" in w["did"]),
                "full": count(lambda w: "iv:full" in w["did"]),
                "zoom": count(lambda w: "iv:zoom" in w["did"]),
                "scenes": sorted(({"scene": sc, "name": IV_SCENES.get(sc, sc), "who": len(d["who"]), "full": len(d["full"]),
                                   "zoom": len(d["zoom"])} for sc, d in iv_scenes.items()), key=lambda x: (-x["who"], x["name"])),
                "panels": sorted(((a, (cat.get(a).name.replace(a, "").strip(" ·,—-") if cat.get(a) else ""), len(ws))
                                  for a, ws in iv_panels.items()), key=lambda x: (-x[2], x[0]))[:40],
            },
            # с 23.11.2026
            "cities": tally(lambda w: w["city"] or "Не определён") if any(w["city"] for w in visitors) else [],
            "camps": sorted(((f"{w_src} · {camp}", n) for (w_src, camp), n in
                             _count_pairs(((w["src"] or DIRECT, w["camp"]) for w in visitors if w["camp"]))), key=lambda x: (-x[1], x[0])),
            "filtered": sorted(((src, why, n) for (src, why), n in filtered.items()), key=lambda x: (-x[2], x[0])),
            "photos": sorted(((a, n, len(ws)) for (a, n), ws in photos.items()), key=lambda x: (x[0], int(x[1] or 0)))[:80],
            "ux": ux, "feed": feed[:feed_limit], "feed_total": len(feed),
            "deep": self.deep_on(),
        }

    def _ux(self, visitors: list[dict[str, Any]], cat: Any) -> dict[str, Any]:
        """«Где теряем людей»: время и прокрутка по страницам, с какой ушли, какие блоки смотрят, что мешает."""
        pg: dict[str, dict[str, Any]] = {}
        blocks: dict[tuple[str, str], dict[str, Any]] = {}
        dead: dict[tuple[str, str, str], set] = defaultdict(set)
        errs: dict[tuple[str, str], set] = defaultdict(set)
        landing: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        has_time = False
        for w in visitors:
            seq = w["seq"]
            if not seq:
                continue
            v = (w["day"], w["vid"])
            per: dict[str, dict[str, int]] = {}
            for x in seq:
                a = per.setdefault(x["path"], {"sec": 0, "scroll": 0, "load": 0, "dead": 0, "rage": 0})
                a["sec"] += x["sec"]
                a["scroll"] = max(a["scroll"], x["scroll"])
                a["load"] = a["load"] or x["load"]
                kind = page_kind(x["path"])
                for b, s in x["blk"].items():
                    bb = blocks.setdefault((kind, b), {"who": set(), "secs": {}})
                    bb["who"].add(v)
                    bb["secs"][v] = bb["secs"].get(v, 0) + s
                for what in ("dead", "rage"):
                    for on in x.get(what + "_on", []):
                        dead[(what, x["path"], on)].add(v)
                for e in x.get("err", []):
                    errs[(x["path"], e)].add(v)
            for path, a in per.items():
                p = pg.setdefault(path, {"who": set(), "secs": [], "s50": set(), "s90": set(), "exit": set(), "loads": [],
                                         "dead": set(), "rage": set()})
                p["who"].add(v)
                if a["sec"]:
                    p["secs"].append(a["sec"])
                    has_time = True
                if a["scroll"] >= 50:
                    p["s50"].add(v)
                if a["scroll"] >= 90:
                    p["s90"].add(v)
                if a["load"]:
                    p["loads"].append(a["load"])
            last = seq[-1]["path"]
            pg[last]["exit"].add(v)
            first = seq[0]
            landing[first["path"]][0] += 1
            if len(seq) == 1 and first["sec"] < 10 and not (w["did"] & ENGAGED):
                landing[first["path"]][1] += 1
        for (what, path, on), ws in dead.items():
            if path in pg:
                pg[path][what].update(ws)
        pages = []
        for path, p in pg.items():
            n = len(p["who"])
            pages.append({"path": path, "name": page_short(path, cat), "who": n, "median_sec": _median(p["secs"]),
                          "timed": len(p["secs"]), "s50": len(p["s50"]), "s90": len(p["s90"]), "exit": len(p["exit"]),
                          "load_med": _median(p["loads"]), "slow": sum(1 for x in p["loads"] if x > 4000),
                          "dead": len(p["dead"]), "rage": len(p["rage"]),
                          "landing": landing[path][0], "bounce": landing[path][1]})
        pages.sort(key=lambda x: (-x["who"], x["name"]))
        blk = []
        for (kind, b), d in blocks.items():
            blk.append({"kind": kind, "kind_name": PAGE_KINDS.get(kind, kind), "blk": b, "name": block_name(b), "who": len(d["who"]),
                        "median_sec": _median(list(d["secs"].values()))})
        blk.sort(key=lambda x: (list(PAGE_KINDS).index(x["kind"]) if x["kind"] in PAGE_KINDS else 9, -x["who"], -x["median_sec"], x["name"]))
        clicks = sorted(({"what": what, "page": page_short(path, cat), "path": path, "on": on, "label": click_label(on), "who": len(ws)}
                         for (what, path, on), ws in dead.items()), key=lambda x: (-x["who"], x["what"], x["page"]))
        errors = sorted(({"page": page_short(path, cat), "msg": e, "who": len(ws)} for (path, e), ws in errs.items()),
                        key=lambda x: -x["who"])
        return {"pages": pages[:60], "blocks": blk[:80], "clicks": clicks[:40], "errors": errors[:20], "has_time": has_time}

    def export(self, day: str) -> dict[str, Any]:
        """Сводка для Claude (только шифром, /api/site/export): 30 дней с лентой посетителей и 7 дней кратко."""
        r30 = self.report(day, 30, feed_limit=400)
        r7 = self.report(day, 7, feed_limit=0)
        r7.pop("feed", None)
        return {"v": 1, "day": day, "d30": r30, "d7": r7}


def _count_pairs(pairs: Any) -> list[tuple[tuple[str, str], int]]:
    t: dict[tuple[str, str], int] = defaultdict(int)
    for p in pairs:
        t[p] += 1
    return list(t.items())


def parse_body(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8", "replace")[:20000])
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
