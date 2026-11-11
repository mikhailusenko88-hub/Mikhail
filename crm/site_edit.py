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
KIND_KEYS = {k for k, _ in KINDS}
ART_RE = re.compile(r"^[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9 /.-]{0,19}$")
PHOTO_MAX = 15 * 1024 * 1024
# правила текстов магазина: материал — только «полистирол высокой плотности (дюрополимер)», без класса горючести и т. п.
FORBIDDEN = [(r"\bмдф\b", "МДФ"), (r"\bпвх\b", "ПВХ"), (r"пенопласт", "пенопласт"), (r"вспенен", "«вспененный»"),
             (r"\bг\s?[1-4]\b", "класс горючести (Г1–Г4)"), (r"горюч", "горючесть"), (r"\bрамк", "слово «рамки»"),
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


def read_site(path: str) -> dict[str, Any]:
    """Товары (как в CAT), фото и контакты с главной страницы сайта."""
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"items": [], "photo": {}, "shop": {}}
    items = _js_value(src, "CAT") or []
    photo = _js_value(src, "PHOTO") or {}
    shop: dict[str, str] = {}
    m = re.search(r"const SHOP = \{(.*?)\};", src)
    if m:
        shop = dict(re.findall(r'(\w+):\s*"([^"]*)"', m.group(1)))
    return {"items": [x for x in items if isinstance(x, dict) and x.get("a")], "photo": photo, "shop": shop}


def norm_art(a: str) -> str:
    return re.sub(r"\s+", " ", str(a or "")).strip()


def text_problems(*texts: str) -> list[str]:
    bad = []
    low = " ".join(t or "" for t in texts).lower()
    for rx, name in FORBIDDEN:
        if re.search(rx, low) and name not in bad:
            bad.append(name)
    return bad


def _int(v: Any, lo: int, hi: int) -> int | None:
    try:
        n = int(round(float(str(v).replace(",", ".").replace(" ", "").replace(" ", ""))))
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def clean_product(form: dict[str, Any], is_new: bool, existing: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Проверить поля формы товара → (данные для CAT, ошибки)."""
    err: list[str] = []
    a = norm_art(form.get("a", ""))
    if not ART_RE.match(a):
        err.append("артикул: буквы, цифры, пробел, «-», «/», до 20 знаков")
    elif is_new and a.upper().replace(" ", "") in existing:
        err.append(f"товар {a} уже есть на сайте — откройте его в списке")
    c = str(form.get("c", ""))
    if c not in KIND_KEYS:
        err.append("выберите раздел")
    n = re.sub(r"\s+", " ", str(form.get("n", ""))).strip()
    d = re.sub(r"\s+", " ", str(form.get("d", ""))).strip()
    if not 10 <= len(n) <= 160:
        err.append("название: от 10 до 160 знаков")
    if not 5 <= len(d) <= 600:
        err.append("описание: от 5 до 600 знаков")
    w, t, ln = _int(form.get("w"), 1, 2000), _int(form.get("t"), 1, 500), _int(form.get("l"), 100, 6000)
    if w is None or t is None or ln is None:
        err.append("размеры в мм: ширина 1–2000, толщина 1–500, длина 100–6000")
    b = _int(form.get("b"), 1, 1000)
    if b is None:
        err.append("штук в коробке: 1–1000")
    r = _int(form.get("r"), 1, 1_000_000)
    if r is None:
        err.append("цена: число в рублях за штуку")
    bad = text_problems(n, d)
    if bad:
        err.append("в тексте нельзя: " + ", ".join(bad) + " (правила магазина)")
    data = {"a": a, "c": c, "n": n, "d": d, "w": w or 0, "t": t or 0, "l": ln or 0, "b": b or 0, "r": r or 0}
    return data, err


def check_image(data: bytes) -> str:
    """Расширение файла по содержимому: jpg / png; иначе ''."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
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
    def add(self, kind: str, article: str, data: dict[str, Any], by: str, photo: bytes = b"") -> int:
        ext = ""
        if photo:
            if len(photo) > PHOTO_MAX:
                raise ValueError("фото больше 15 МБ")
            ext = check_image(photo)
            if not ext:
                raise ValueError("фото — только JPG или PNG (с iPhone: «Настройки → Камера → Форматы → Наиболее совместимый»)")
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
            if ext:
                self.dir.mkdir(parents=True, exist_ok=True)
                name = f"{eid}.{ext}"
                tmp = self.dir / (name + ".part")
                tmp.write_bytes(photo)
                os.replace(tmp, self.dir / name)
                c.execute("UPDATE site_edits SET photo=? WHERE id=?", (name, eid))
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
        return d

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        self.sync()
        return [self._row(r) for r in self.s.c().execute("SELECT * FROM site_edits ORDER BY id DESC LIMIT ?", (limit,))]

    def pending_for(self, article: str) -> dict[str, Any] | None:
        self.sync()
        r = self.s.c().execute("SELECT * FROM site_edits WHERE status='new' AND article=? AND kind IN ('product','delete') "
                               "ORDER BY id DESC LIMIT 1", (article,)).fetchone()
        return self._row(r) if r else None

    def api_list(self, after: int = 0) -> list[dict[str, Any]]:
        """Новые правки для GitHub Actions (только содержимое для публичного сайта)."""
        self.sync()
        out = []
        for r in self.s.c().execute("SELECT * FROM site_edits WHERE status='new' AND id>? ORDER BY id LIMIT 50", (after,)):
            d = self._row(r)
            out.append({"id": d["id"], "kind": d["kind"], "article": d["article"], "data": d["data"],
                        "photo": d["photo"], "at": d["created_at"]})
        return out

    def photo_path(self, name: str) -> Path | None:
        if not re.match(r"^[0-9]{1,9}\.(jpg|png)$", name or ""):
            return None
        r = self.s.c().execute("SELECT status FROM site_edits WHERE photo=?", (name,)).fetchone()
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
            m = re.match(r"^([0-9]+)\.(jpg|png)$", p.name)
            if m:
                r = self.s.c().execute("SELECT status FROM site_edits WHERE id=?", (int(m.group(1)),)).fetchone()
                if r and r[0] in ("applied", "canceled"):
                    try:
                        p.unlink()
                    except OSError:
                        pass
