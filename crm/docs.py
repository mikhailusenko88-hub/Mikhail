"""Раздел CRM «Документы»: важные документы ИП и магазина (регистрация, договоры, ТУ, сертификаты, протоколы).

Файлы лежат на сервере магазина в папке DOCS_DIR (рядом с базой CRM), сведения о них — в таблице docs.
Файл никогда не меняется (имя на диске — id), поэтому ежедневная копия может ставить жёсткие ссылки.
Добавить можно: загрузкой в CRM, кнопкой «В документы» у вложения письма и через канал Claude (ветка outbox, docs/*.json).
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DEFAULT_FOLDERS = ["ИП", "Договоры", "Сертификаты и ТУ", "Налоги и отчётность", "Банк", "Из почты", "Прочее"]
MAX_FILE = 25 * 1024 * 1024
WARN_DAYS = 60                       # «срок действия подходит» — за столько дней
ID_RE = re.compile(r"^[0-9a-f]{32}$")
INLINE_OK = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id         TEXT PRIMARY KEY,
    folder     TEXT NOT NULL,
    title      TEXT NOT NULL,
    filename   TEXT NOT NULL,
    mime       TEXT NOT NULL,
    size       INTEGER NOT NULL,
    sha256     TEXT NOT NULL,
    until      TEXT NOT NULL DEFAULT '',     -- действует до (YYYY-MM-DD), если у документа есть срок
    note       TEXT NOT NULL DEFAULT '',
    source     TEXT NOT NULL DEFAULT '',     -- откуда: загрузка, письмо, Claude
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT ''
)
"""


def clean_folder(s: Any) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()[:60]
    return s or "Прочее"


def clean_name(s: Any) -> str:
    s = re.sub(r'[\x00-\x1f\x7f\\/:*?"<>|]', "_", str(s or "")).strip(" .")[:150]
    return s or "документ"


def clean_date(s: Any) -> str:
    s = str(s or "").strip()
    try:
        return date.fromisoformat(s).isoformat() if s else ""
    except ValueError:
        return ""


def fmt_date(s: str) -> str:
    try:
        return date.fromisoformat(s).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return s or ""


class Docs:
    def __init__(self, store: Any, path: str) -> None:
        self.s = store
        self.dir = Path(path)
        with self.s.tx() as c:
            c.execute(SCHEMA)
            c.execute("CREATE INDEX IF NOT EXISTS docs_folder ON docs(folder)")

    def _now(self) -> str:
        from store import now
        return now().isoformat(timespec="seconds")

    def add(self, data: bytes, filename: str, folder: str = "", title: str = "", until: str = "", note: str = "",
            by: str = "", source: str = "", mime: str = "") -> tuple[str, bool]:
        """Сохранить файл. Возвращает (id, новый ли). Тот же файл в том же разделе второй раз не кладём."""
        if not data:
            raise ValueError("файл пустой")
        if len(data) > MAX_FILE:
            raise ValueError("файл больше 25 МБ")
        name = clean_name(filename)
        folder = clean_folder(folder)
        sha = hashlib.sha256(data).hexdigest()
        row = self.s.c().execute("SELECT id FROM docs WHERE sha256=? AND folder=?", (sha, folder)).fetchone()
        if row:
            return row["id"], False
        mime = (mime or mimetypes.guess_type(name)[0] or "application/octet-stream").lower()
        if not re.match(r"^[a-z]+/[a-z0-9.+-]+$", mime):
            mime = "application/octet-stream"
        did = uuid.uuid4().hex
        self.dir.mkdir(mode=0o750, parents=True, exist_ok=True)
        tmp = self.dir / f".{did}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, self.dir / did)
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:200] or os.path.splitext(name)[0]
        with self.s.tx() as c:
            c.execute("INSERT INTO docs(id, folder, title, filename, mime, size, sha256, until, note, source, created_at, created_by)"
                      " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (did, folder, title, name, mime, len(data), sha, clean_date(until), str(note or "").strip()[:1000],
                       str(source or "")[:100], self._now(), str(by or "")[:60]))
        return did, True

    def get(self, did: str) -> Any:
        if not ID_RE.match(did or ""):
            return None
        return self.s.c().execute("SELECT * FROM docs WHERE id=?", (did,)).fetchone()

    def path(self, did: str) -> Path | None:
        if not self.get(did):
            return None
        p = self.dir / did
        return p if p.is_file() else None

    def list(self, folder: str = "", q: str = "") -> list[Any]:
        sql, args = "SELECT * FROM docs WHERE 1=1", []
        if folder:
            sql += " AND folder=?"; args.append(folder)
        rows = self.s.c().execute(sql + " ORDER BY folder, title COLLATE NOCASE, created_at DESC", args).fetchall()
        q = q.strip().lower()
        if q:
            rows = [r for r in rows if q in f"{r['title']} {r['filename']} {r['note']} {r['folder']}".lower()]
        return rows

    def folders(self) -> list[tuple[str, int]]:
        cnt = {r["folder"]: r["n"] for r in self.s.c().execute("SELECT folder, COUNT(*) AS n FROM docs GROUP BY folder")}
        names = DEFAULT_FOLDERS + sorted(f for f in cnt if f not in DEFAULT_FOLDERS)
        return [(f, cnt.get(f, 0)) for f in names]

    def update(self, did: str, folder: Any, title: Any, until: Any, note: Any) -> None:
        r = self.get(did)
        if not r:
            raise ValueError("нет такого документа")
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:200] or r["title"]
        with self.s.tx() as c:
            c.execute("UPDATE docs SET folder=?, title=?, until=?, note=? WHERE id=?",
                      (clean_folder(folder), title, clean_date(until), str(note or "").strip()[:1000], did))

    def delete(self, did: str) -> None:
        if not self.get(did):
            return
        with self.s.tx() as c:
            c.execute("DELETE FROM docs WHERE id=?", (did,))
        try:
            (self.dir / did).unlink()
        except OSError:
            pass

    @staticmethod
    def state(until: str, day: str) -> str:
        """'' — без срока или далеко; 'soon' — подходит; 'over' — истёк."""
        if not until:
            return ""
        if until < day:
            return "over"
        return "soon" if until <= (date.fromisoformat(day) + timedelta(days=WARN_DAYS)).isoformat() else ""

    def expiring(self, day: str, days: int = 30) -> list[Any]:
        lim = (date.fromisoformat(day) + timedelta(days=days)).isoformat()
        return self.s.c().execute("SELECT * FROM docs WHERE until<>'' AND until<=? ORDER BY until", (lim,)).fetchall()
