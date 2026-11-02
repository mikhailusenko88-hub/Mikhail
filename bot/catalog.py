"""Каталог товаров из сайта «Пространство».

Товары лежат в index.html сайта в массиве `const CAT=[...]` (JSON):
  a — артикул, c — тип (panel / color / mold / plinth / cornice / corner),
  n — название, d — описание, w — ширина, t — толщина, l — длина (мм),
  b — штук в коробке, r — цена ₽ за штуку.

Откуда берём (по порядку): файл сайта на сервере → GitHub (raw) → последняя
удачная копия в кеше на диске. Перечитываем раз в час — цены меняются.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
import urllib.request
from collections.abc import Iterable
from dataclasses import asdict, dataclass

log = logging.getLogger("prostranstvo.catalog")

MAX_HTML_BYTES = 8 * 1024 * 1024

# Группы в том порядке, в котором их видит клиент.
GROUPS: dict[str, str] = {
    "panel": "Реечные панели под покраску",
    "color": "Панели под дерево и бетон",
    "mold": "Молдинги",
    "plinth": "Плинтусы",
    "cornice": "Карнизы потолочные",
    "corner": "Уголки",
}
OTHER_GROUP = "other"
OTHER_TITLE = "Другое"
AREA_KINDS = frozenset({"panel", "color"})  # считаются по площади стены

_CAT_RE = re.compile(r"\bCAT\s*=\s*\[")

# Похожие кириллические буквы → латиница (клиент может набрать «А907» по-русски)
_LOOKALIKE = str.maketrans("АВЕКМНОРСТХУЛ", "ABEKMHOPCTXYL")


class CatalogError(Exception):
    """Не удалось получить или разобрать каталог."""


@dataclass(frozen=True)
class Product:
    article: str
    kind: str
    name: str
    desc: str
    width: int       # мм
    thickness: int   # мм
    length: int      # мм
    per_box: int     # штук в коробке
    price: int       # ₽ за штуку

    @property
    def is_area(self) -> bool:
        return self.kind in AREA_KINDS

    @property
    def group(self) -> str:
        return self.kind if self.kind in GROUPS else OTHER_GROUP

    @property
    def box_price(self) -> int:
        return self.price * self.per_box

    @property
    def size_text(self) -> str:
        parts = [self.width, self.thickness, self.length] if self.thickness else [self.width, self.length]
        return "×".join(str(p) for p in parts) + " мм"

    @property
    def short_desc(self) -> str:
        """Описание без размеров и материала: «широкие ламели с тонкими швами»."""
        first = self.desc.split(",")[0].strip()
        if re.fullmatch(r"[\d×x\s]+мм", first):
            return ""
        return first


def norm_article(text: str) -> str:
    """Ключ для поиска артикула: верхний регистр, без пробелов, кириллица → латиница."""
    s = (text or "").strip().upper().translate(_LOOKALIKE)
    return re.sub(r"\s+", "", s)


def _loose_key(text: str) -> str:
    """Ещё грубее: без разделителей («A2012» ~ «A201/2», «23» ~ «2-3»)."""
    return re.sub(r"[^0-9A-Z]", "", norm_article(text))


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"не число: {value!r}")


def _product_from_raw(raw: object) -> Product | None:
    if not isinstance(raw, dict):
        return None
    try:
        article = str(raw["a"]).strip()
        kind = str(raw.get("c", "")).strip() or OTHER_GROUP
        name = str(raw.get("n") or article).strip()
        width = _to_int(raw["w"])
        length = _to_int(raw["l"])
        thickness = _to_int(raw.get("t", 0) or 0)
        per_box = _to_int(raw.get("b", 0) or 0)
        price = _to_int(raw.get("r", 0) or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if not article or width <= 0 or length <= 0 or per_box < 0 or price < 0:
        return None
    return Product(
        article=article, kind=kind, name=name, desc=str(raw.get("d") or "").strip(),
        width=width, thickness=max(thickness, 0), length=length, per_box=per_box, price=price,
    )


def parse_catalog(html: str) -> list[Product]:
    """Достать товары из текста index.html. Битые позиции пропускаются."""
    match = _CAT_RE.search(html or "")
    if not match:
        raise CatalogError("в странице нет массива CAT")
    start = match.end() - 1  # позиция «[»
    try:
        raw, _ = json.JSONDecoder().raw_decode(html, start)
    except json.JSONDecodeError as exc:
        raise CatalogError(f"массив CAT не разобран: {exc.msg} (символ {exc.pos})") from exc
    if not isinstance(raw, list):
        raise CatalogError("CAT — не массив")
    products: list[Product] = []
    seen: set[str] = set()
    skipped = 0
    for item in raw:
        product = _product_from_raw(item)
        if product is None or norm_article(product.article) in seen:
            skipped += 1
            continue
        seen.add(norm_article(product.article))
        products.append(product)
    if skipped:
        log.warning("каталог: пропущено позиций с ошибками или повторами: %d", skipped)
    if not products:
        raise CatalogError("в CAT нет ни одной правильной позиции")
    return products


class Catalog:
    """Неизменяемый снимок каталога с поиском по артикулу и группам."""

    def __init__(self, products: Iterable[Product], source: str = "", loaded_at: float | None = None):
        self.products: tuple[Product, ...] = tuple(products)
        self.source = source
        self.loaded_at = time.time() if loaded_at is None else loaded_at
        self._by_key = {norm_article(p.article): p for p in self.products}
        loose: dict[str, list[Product]] = {}
        for p in self.products:
            loose.setdefault(_loose_key(p.article), []).append(p)
        self._by_loose = {k: v[0] for k, v in loose.items() if len(v) == 1}

    def __len__(self) -> int:
        return len(self.products)

    def find(self, text: str) -> Product | None:
        """Точный артикул (без учёта регистра, пробелов и русских букв-двойников)."""
        key = norm_article(text)
        if not key:
            return None
        return self._by_key.get(key) or self._by_loose.get(_loose_key(text))

    def search(self, text: str, limit: int = 8) -> list[Product]:
        """Похожие артикулы — для подсказки «может быть, вы имели в виду…»."""
        key = _loose_key(text)
        if len(key) < 2:
            return []
        found = [p for p in self.products if key in _loose_key(p.article)]
        return found[:limit]

    def groups(self) -> list[tuple[str, str]]:
        """[(код группы, название)] — только непустые, в порядке GROUPS."""
        present = {p.group for p in self.products}
        result = [(code, title) for code, title in GROUPS.items() if code in present]
        if OTHER_GROUP in present:
            result.append((OTHER_GROUP, OTHER_TITLE))
        return result

    def in_group(self, group: str) -> list[Product]:
        return [p for p in self.products if p.group == group]


def group_title(group: str) -> str:
    return GROUPS.get(group, OTHER_TITLE)


# --------------------------------------------------------------------------- загрузка
def _read_file(path: str) -> str:
    with open(path, "rb") as fh:
        data = fh.read(MAX_HTML_BYTES + 1)
    if len(data) > MAX_HTML_BYTES:
        raise CatalogError("файл сайта слишком большой")
    return data.decode("utf-8")


def _fetch_url(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "prostranstvo-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - адрес из настроек
        data = resp.read(MAX_HTML_BYTES + 1)
    if len(data) > MAX_HTML_BYTES:
        raise CatalogError("страница слишком большая")
    return data.decode("utf-8")


def _save_cache(path: str, products: list[Product]) -> None:
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".catalog-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump([asdict(p) for p in products], fh, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_cache(path: str) -> list[Product]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    products = [Product(**item) for item in raw]
    if not products:
        raise CatalogError("кеш каталога пуст")
    return products


def load_catalog_sync(catalog_file: str, catalog_url: str, cache_path: str = "") -> Catalog:
    """Файл сайта → GitHub → кеш. Ошибки пишутся в журнал, наружу — только если всё не удалось."""
    errors: list[str] = []
    sources: list[tuple[str, str]] = []
    if catalog_file:
        sources.append(("файл сайта", catalog_file))
    if catalog_url:
        sources.append(("GitHub", catalog_url))
    for label, where in sources:
        try:
            html = _read_file(where) if label == "файл сайта" else _fetch_url(where)
            products = parse_catalog(html)
        except (OSError, UnicodeDecodeError, CatalogError, ValueError) as exc:
            errors.append(f"{label}: {exc}")
            continue
        if cache_path:
            try:
                _save_cache(cache_path, products)
            except OSError as exc:
                log.warning("не удалось сохранить кеш каталога: %s", exc)
        return Catalog(products, source=label)
    if cache_path:
        try:
            products = _load_cache(cache_path)
            log.warning("каталог взят из кеша (%s)", "; ".join(errors))
            return Catalog(products, source="кеш", loaded_at=os.path.getmtime(cache_path))
        except (OSError, ValueError, TypeError, CatalogError) as exc:
            errors.append(f"кеш: {exc}")
    raise CatalogError("; ".join(errors) or "не задан ни один источник каталога")


class CatalogStore:
    """Текущий каталог + фоновое обновление раз в N минут."""

    def __init__(self, catalog_file: str, catalog_url: str, cache_path: str = "", refresh_min: int = 60):
        self.catalog_file = catalog_file
        self.catalog_url = catalog_url
        self.cache_path = cache_path
        self.refresh_sec = max(60, refresh_min * 60)
        self._catalog: Catalog | None = None
        self.last_error = ""

    def get(self) -> Catalog | None:
        return self._catalog

    def set(self, catalog: Catalog) -> None:
        self._catalog = catalog

    async def reload(self) -> Catalog | None:
        """Перечитать каталог. При неудаче остаётся прежний."""
        try:
            catalog = await asyncio.to_thread(
                load_catalog_sync, self.catalog_file, self.catalog_url, self.cache_path
            )
        except CatalogError as exc:
            self.last_error = str(exc)
            log.error("каталог не обновлён: %s", exc)
            return self._catalog
        old = self._catalog
        self._catalog = catalog
        self.last_error = ""
        if old is None or len(old) != len(catalog) or old.source != catalog.source:
            log.info("каталог: %d позиций (источник: %s)", len(catalog), catalog.source)
        return catalog

    async def refresh_forever(self) -> None:
        while True:
            # каталога ещё нет (сайт и GitHub были недоступны) — пробуем каждые 5 минут
            await asyncio.sleep(self.refresh_sec if self._catalog else min(300, self.refresh_sec))
            await self.reload()
