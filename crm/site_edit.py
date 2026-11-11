"""«Редактор сайта» в CRM: товары, фото, новые товары и контакты на nashdekor.ru — кнопками, без кода.

Как это работает (без паролей и токенов на сервере):
  1. Владелец меняет товар в CRM → правка записывается в таблицу site_edits (статус «ждёт»), фото — в папку uploads.
  2. GitHub Actions «Сайт — правки из CRM» (ветка main, раз в 10 минут) забирает новые правки с
     https://crm.ДОМЕН/api/site/edits, вносит их в каталог сайта (0f7s1eez/index.html, ветка mebel),
     уменьшает фото, пересобирает страницы build.py и записывает итог в 0f7s1eez/site-edits.json.
  3. Сервер забирает ветку mebel раз в минуту; CRM читает site-edits.json с сайта и отмечает правку
     «на сайте» или «ошибка» (с причиной).
Правка, которую ещё не забрали, можно отменить.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

KINDS = [("panel", "Реечная панель под покраску"), ("color", "Панель с декором (под дерево, бетон)"),
         ("mold", "Молдинг"), ("plinth", "Плинтус напольный"), ("cornice", "Потолочный плинтус (карниз)"),
         ("corner", "Уголок")]
KIND_KEYS = {k for k, _ in KINDS}          # разделы товаров ARTDEC; новые разделы из CRM — в site-content.json (kinds)
HOME_BLOCKS = [("home_h1", "Главный заголовок", 120), ("home_lead", "Текст под заголовком", 700), ("catalog_intro", "Каталог — вводный текст", 500),
               ("pro_intro", "«Дизайнерам и бригадам» — вводный текст", 300), ("pro1_h", "Блок 1 — заголовок", 60), ("pro1_t", "Блок 1 — текст", 300),
               ("pro2_h", "Блок 2 — заголовок", 60), ("pro2_t", "Блок 2 — текст", 300), ("pro3_h", "Блок 3 — заголовок", 60),
               ("pro3_t", "Блок 3 — текст", 300), ("terms_intro", "«Доставка, оплата, возврат» — вводный текст", 300),
               ("return_t", "Возврат — текст", 600)]
AVITO_KINDS = [("", "не выкладывать на Авито"), ("panel", "Авито: стеновые панели"), ("mold", "Авито: молдинги и лепнина"),
               ("plinth", "Авито: плинтусы")]
ART_RE = re.compile(r"^[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9 /.-]{0,19}$")
PHOTO_MAX = 15 * 1024 * 1024
# правила текстов магазина: материал — только «полистирол высокой плотности (дюрополимер)», без класса горючести и т. п.
SOFT_FORBIDDEN = [(r"\bг\s?[1-4]\b", "класс горючести (Г1–Г4)"), (r"горюч|пожарн", "горючесть"), (r"\bрам(к|ок)", "слово «рамки»"),
                  (r"artdec|арт\s?дек", "бренд поставщика (его пишет сам сайт)")]
FORBIDDEN = [(r"\bмдф\b", "МДФ"), (r"\bпвх\b", "ПВХ"), (r"пенопласт", "пенопласт"), (r"вспенен", "«вспененный»"),
             (r"\bг\s?[1-4]\b", "класс горючести (Г1–Г4)"), (r"горюч|пожарн", "горючесть"), (r"\bрам(к|ок)", "слово «рамки»"),
             (r"алюмини", "алюминий"), (r"artdec|арт\s?дек", "бренд поставщика (его пишет сам сайт)")]
STATUS_NAMES = {"new": "ждёт публикации", "applied": "на сайте", "error": "ошибка", "canceled": "отменена"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS site_edits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    created_by  TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL,              -- product | delete | shop
    article     TEXT NOT NULL DEFAULT '',
    data        TEXT NOT NULL DEFAULT '{}', -- JSON: поля товара или контакты
    photo       TEXT NOT NULL DEFAULT '',   -- имя файла в папке uploads (id.jpg / id.png)
    status      TEXT NOT NULL DEFAULT 'new',
    note        TEXT NOT NULL DEFAULT '',   -- причина ошибки / что сделано
    done_at     TEXT NOT NULL DEFAULT ''
)
"""


# ---------------------------------------------------------------- каталог сайта (как его читает build.py)
def _js_value(src: str, name: str) -> Any:
    m = re.search(r"\bconst %s\s*=\s*" % re.escape(name), src)
    if not m:
        return None
    i = m.end()
    depth, in_str, esc = 0, False, False
    for j in range(i, len(src)):
        ch = src[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(src[i:j + 1])
                except ValueError:
                    return None
    return None


def _json_file(path: str) -> dict[str, Any]:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def read_site(path: str) -> dict[str, Any]:
    """Товары (как в CAT), фото, контакты и тексты главной + правки из CRM (site-content.json) и сводка сборки (site-index.json)."""
    import html as _html
    d = os.path.dirname(os.path.abspath(path))
    content = _json_file(os.path.join(d, "site-content.json"))
    index = _json_file(os.path.join(d, "site-index.json"))
    custom = {k: v for k, v in content["kinds"].items() if isinstance(v, dict)} if isinstance(content.get("kinds"), dict) else {}
    kinds = KINDS + [(k, v.get("menu") or v.get("label") or k) for k, v in custom.items()]
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"items": [], "photo": {}, "shop": {}, "home": {}, "hero": "", "content": content, "index": index, "kinds": kinds, "custom": custom}
    items = _js_value(src, "CAT")
    items = items if isinstance(items, list) else []
    photo = _js_value(src, "PHOTO")
    photo = photo if isinstance(photo, dict) else {}
    shop: dict[str, str] = {}
    m = re.search(r"const SHOP = \{(.*?)\};", src)
    if m:
        shop = dict(re.findall(r'(\w+):\s*"([^"]*)"', m.group(1)))
    home = {k: _html.unescape(v) for k, v in re.findall(r"<!--ed:(\w+)-->(.*?)<!--/ed:\1-->", src, re.S) if k not in ("navx", "reviews")}
    hm = re.search(r'<div class="wall"><img src="img/([^"]+)"', src)
    return {"items": [x for x in items if isinstance(x, dict) and x.get("a")], "photo": photo, "shop": shop, "home": home,
            "hero": hm.group(1) if hm else "", "content": content, "index": index, "kinds": kinds, "custom": custom}


EDIT_NAMES = {"product": "товар", "delete": "убрать товар", "hide": "скрыть товар", "unhide": "вернуть товар",
              "gallery_add": "фото к товару", "gallery_del": "убрать фото у товара", "kind": "раздел", "kind_del": "удалить раздел",
              "section": "тексты раздела", "home": "главная страница", "article": "статья", "article_del": "убрать статью",
              "review": "отзыв", "review_del": "удалить отзыв", "shop": "контакты"}
EDIT_KINDS = set(EDIT_NAMES)


def edit_title(kind: str, article: str, data: dict[str, Any]) -> str:
    """Короткое название правки для списка «Последние правки»."""
    base = EDIT_NAMES.get(kind, kind)
    extra = article or data.get("menu") or data.get("title") or data.get("name") or data.get("code") or data.get("slug") or ""
    if kind == "kind" and not data.get("code"):
        base = "новый раздел"
    elif kind == "article" and not data.get("slug"):
        base = "новая статья"
    elif kind == "review" and not data.get("id"):
        base = "новый отзыв"
    return f"{base} {extra}".strip() if kind not in ("home", "shop") else base


def norm_art(a: str) -> str:
    return re.sub(r"\s+", " ", str(a or "")).strip()


def text_problems(*texts: str, soft: bool = False) -> list[str]:
    bad = []
    low = " ".join(t or "" for t in texts).lower()
    for rx, name in (SOFT_FORBIDDEN if soft else FORBIDDEN):
        if re.search(rx, low) and name not in bad:
            bad.append(name)
    return bad


def _int(v: Any, lo: int, hi: int) -> int | None:
    try:
        n = int(round(float(str(v).replace(",", ".").replace(" ", "").replace(" ", ""))))
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def clean_product(form: dict[str, Any], is_new: bool, existing: set[str], custom: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    """Проверить поля формы товара → (данные для CAT, ошибки). custom — новые разделы (код → описание)."""
    custom = custom or {}
    err: list[str] = []
    a = norm_art(form.get("a", ""))
    if not ART_RE.match(a):
        err.append("артикул: буквы, цифры, пробел, «-», «/», до 20 знаков")
    elif is_new and a.upper().replace(" ", "") in existing:
        err.append(f"товар {a} уже есть на сайте — откройте его в списке")
    c = str(form.get("c", ""))
    if c not in KIND_KEYS and c not in custom:
        err.append("выберите раздел")
    n = re.sub(r"\s+", " ", str(form.get("n", ""))).strip()
    d = re.sub(r"\s+", " ", str(form.get("d", ""))).strip()
    if not 10 <= len(n) <= 160:
        err.append("название: от 10 до 160 знаков")
    if not 5 <= len(d) <= 600:
        err.append("описание: от 5 до 600 знаков")
    w, t, ln = _int(form.get("w"), 1, 3000), _int(form.get("t"), 1, 500), _int(form.get("l"), 50, 6000)
    if w is None or t is None or ln is None:
        err.append("размеры в мм: ширина 1–3000, толщина 1–500, длина 50–6000")
    b = _int(form.get("b"), 1, 1000)
    if b is None:
        err.append("штук в коробке: 1–1000")
    r = _int(form.get("r"), 1, 1_000_000)
    if r is None:
        err.append("цена: число в рублях за штуку")
    m_, mk = re.sub(r"\s+", " ", str(form.get("m", ""))).strip()[:120], re.sub(r"\s+", " ", str(form.get("mk", ""))).strip()[:120]
    bad = text_problems(n, d, m_, mk, soft=c in custom)
    if bad:
        err.append("в тексте нельзя: " + ", ".join(bad) + " (правила магазина)")
    data = {"a": a, "c": c, "n": n, "d": d, "w": w or 0, "t": t or 0, "l": ln or 0, "b": b or 0, "r": r or 0}
    if c in custom:
        if m_: data["m"] = m_
        if mk: data["mk"] = mk
    return data, err


def parse_faq(text: str) -> list[list[str]]:
    """FAQ из текстового поля: блоки через пустую строку; первая строка — вопрос, остальные — ответ."""
    out = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [x.strip() for x in block.strip().split("\n") if x.strip()]
        if len(lines) >= 2:
            out.append([lines[0][:200], " ".join(lines[1:])[:1200]])
    return out[:15]


def faq_text(faq: list[Any]) -> str:
    return "\n\n".join(f"{q[0]}\n{q[1]}" for q in faq or [] if isinstance(q, (list, tuple)) and len(q) == 2)


def check_image(data: bytes) -> str:
    """Расширение файла по содержимому: jpg / png; иначе ''."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return ""


def image_size(data: bytes) -> tuple[int, int]:
    """Ширина и высота JPG/PNG по заголовку файла (без библиотек); (0, 0) — не удалось прочитать."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] != b"\xff\xd8":
        return 0, 0
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            i += 1 if marker == 0xFF else 2
            continue
        seg = int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + seg
    return 0, 0


def photo_problem(data: bytes, min_w: int) -> str:
    """Понятная причина, почему фото не подойдёт сайту; '' — подходит (поворот с телефона учитываем: берём бóльшую сторону)."""
    if not check_image(data):
        return "фото — только JPG или PNG (с iPhone: «Настройки → Камера → Форматы → Наиболее совместимый»)"
    if len(data) > PHOTO_MAX:
        return "фото больше 15 МБ"
    w, h = image_size(data)
    if w and h and max(w, h) < min_w:
        return f"фото маленькое ({max(w, h)} точек), нужно от {min_w} — пришлите оригинал, не скриншот"
    return ""


class SiteEdits:
    def __init__(self, store: Any, uploads: str, site_index: str) -> None:
        self.s = store
        self.dir = Path(uploads)
        self.index = site_index
        self.result_file = os.path.join(os.path.dirname(os.path.abspath(site_index)), "site-edits.json")
        self._result_mtime = -1.0
        with self.s.tx() as c:
            c.execute(SCHEMA)

    def _now(self) -> str:
        from store import now
        return now().isoformat(timespec="seconds")

    # ---- запись
    def add(self, kind: str, article: str, data: dict[str, Any], by: str, photo: bytes = b"",
            photos: list[bytes] | None = None) -> int:
        files = ([photo] if photo else []) + list(photos or [])
        exts = []
        for ph in files:
            if len(ph) > PHOTO_MAX:
                raise ValueError("фото больше 15 МБ")
            ext = check_image(ph)
            if not ext:
                raise ValueError("фото — только JPG или PNG (с iPhone: «Настройки → Камера → Форматы → Наиболее совместимый»)")
            exts.append(ext)
        if len(files) > 12:
            raise ValueError("за один раз — до 12 фото")
        with self.s.tx() as c:
            # прежняя неопубликованная правка того же товара больше не нужна — новая её заменяет
            if kind in ("product", "delete") and article:
                c.execute("UPDATE site_edits SET status='canceled', note='заменена новой правкой', done_at=? "
                          "WHERE status='new' AND article=? AND kind IN ('product','delete')", (self._now(), article))
            elif kind == "shop":
                c.execute("UPDATE site_edits SET status='canceled', note='заменена новой правкой', done_at=? "
                          "WHERE status='new' AND kind='shop'", (self._now(),))
            cur = c.execute("INSERT INTO site_edits(created_at, created_by, kind, article, data) VALUES (?,?,?,?,?)",
                            (self._now(), by, kind, article, json.dumps(data, ensure_ascii=False)))
            eid = int(cur.lastrowid)
            names = []
            for n, (ph, ext) in enumerate(zip(files, exts), 1):
                self.dir.mkdir(parents=True, exist_ok=True)
                name = f"{eid}.{ext}" if len(files) == 1 else f"{eid}-{n}.{ext}"
                tmp = self.dir / (name + ".part")
                tmp.write_bytes(ph)
                os.replace(tmp, self.dir / name)
                names.append(name)
            if names:
                c.execute("UPDATE site_edits SET photo=? WHERE id=?", (",".join(names), eid))
        return eid

    def cancel(self, eid: int, by: str) -> bool:
        with self.s.tx() as c:
            n = c.execute("UPDATE site_edits SET status='canceled', note=?, done_at=? WHERE id=? AND status='new'",
                          (f"отменил {by}", self._now(), eid)).rowcount
        return bool(n)

    # ---- чтение
    def get(self, eid: int) -> dict[str, Any] | None:
        self.sync()
        r = self.s.c().execute("SELECT * FROM site_edits WHERE id=?", (eid,)).fetchone()
        return self._row(r) if r else None

    def _row(self, r: Any) -> dict[str, Any]:
        d = dict(r)
        try:
            d["data"] = json.loads(d["data"] or "{}")
        except ValueError:
            d["data"] = {}
        d["status_name"] = STATUS_NAMES.get(d["status"], d["status"])
        d["photos"] = [x for x in (d.get("photo") or "").split(",") if x]
        d["title"] = edit_title(d["kind"], d["article"], d["data"] if isinstance(d["data"], dict) else {})
        return d

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        self.sync()
        return [self._row(r) for r in self.s.c().execute("SELECT * FROM site_edits ORDER BY id DESC LIMIT ?", (limit,))]

    def pending_for(self, article: str) -> dict[str, Any] | None:
        self.sync()
        r = self.s.c().execute("SELECT * FROM site_edits WHERE status='new' AND article=? AND kind IN ('product','delete') "
                               "ORDER BY id DESC LIMIT 1", (article,)).fetchone()
        return self._row(r) if r else None

    def pending(self, *kinds: str) -> list[dict[str, Any]]:
        """Правки, которые ещё не на сайте (по видам)."""
        self.sync()
        q = "SELECT * FROM site_edits WHERE status='new'" + (" AND kind IN (%s)" % ",".join("?" * len(kinds)) if kinds else "")
        return [self._row(r) for r in self.s.c().execute(q + " ORDER BY id", kinds).fetchall()]

    def api_list(self, after: int = 0) -> list[dict[str, Any]]:
        """Новые правки для GitHub Actions (только содержимое для публичного сайта)."""
        self.sync()
        out = []
        for r in self.s.c().execute("SELECT * FROM site_edits WHERE status='new' AND id>? ORDER BY id LIMIT 50", (after,)):
            d = self._row(r)
            out.append({"id": d["id"], "kind": d["kind"], "article": d["article"], "data": d["data"],
                        "photo": d["photos"][0] if d["photos"] else "", "photos": d["photos"], "at": d["created_at"]})
        return out

    def photo_path(self, name: str) -> Path | None:
        m = re.match(r"^([0-9]{1,9})(-[0-9]{1,3})?\.(jpg|png)$", name or "")
        if not m:
            return None
        r = self.s.c().execute("SELECT status FROM site_edits WHERE id=?", (int(m.group(1)),)).fetchone()
        p = self.dir / name
        return p if r and r[0] == "new" and p.is_file() else None

    # ---- итог от GitHub Actions (файл на сайте)
    def sync(self) -> None:
        try:
            mt = os.path.getmtime(self.result_file)
        except OSError:
            return
        if mt == self._result_mtime:
            return
        try:
            res = json.loads(Path(self.result_file).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self._result_mtime = mt
        done = res.get("edits", {}) if isinstance(res, dict) else {}
        with self.s.tx() as c:
            for k, v in done.items():
                try:
                    eid = int(k)
                except ValueError:
                    continue
                ok = isinstance(v, dict) and v.get("ok")
                note = str((v or {}).get("note", "") if isinstance(v, dict) else v)[:300]
                c.execute("UPDATE site_edits SET status=?, note=?, done_at=? WHERE id=? AND status='new'",
                          ("applied" if ok else "error", note, str((v or {}).get("at", "") if isinstance(v, dict) else ""), eid))
        for p in self.dir.glob("*.*") if self.dir.is_dir() else []:   # фото опубликованных правок больше не нужны
            m = re.match(r"^([0-9]+)(-[0-9]+)?\.(jpg|png)$", p.name)
            if m:
                r = self.s.c().execute("SELECT status FROM site_edits WHERE id=?", (int(m.group(1)),)).fetchone()
                if r and r[0] in ("applied", "canceled"):
                    try:
                        p.unlink()
                    except OSError:
                        pass
