"""Раздел CRM «Почта»: письма на info@ и zakaz@ — текст и вложения.

Письма выгружает root (cron prostranstvo-crm mail-watch → mailwatch.py --export) в папку,
которую CRM только читает: index.json — список, <id>.json — письмо, <id>/<n> — вложения.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from store import TZ

ID_RE = re.compile(r"^[0-9a-f]{20}$")
DEFAULT_DIR = "/var/lib/prostranstvo-pochta"
INLINE_OK = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}   # открываются в браузере, остальное — скачиваются


def fmt_ts(ts: Any) -> str:
    try:
        d = datetime.fromtimestamp(int(ts), TZ)
    except (TypeError, ValueError, OverflowError, OSError):
        return ""
    return d.strftime("%d.%m.%Y %H:%M")


def size_h(n: Any) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n < 1024:
        return f"{n} Б"
    if n < 1024 * 1024:
        return f"{n // 1024} КБ"
    return f"{n / 1024 / 1024:.1f} МБ".replace(".", ",")


class Pochta:
    def __init__(self, path: str = "") -> None:
        self.dir = Path(path or os.environ.get("MAIL_DIR", DEFAULT_DIR))
        self._cache: tuple[float, list[dict[str, Any]]] = (-1.0, [])

    def ready(self) -> bool:
        return (self.dir / "index.json").is_file()

    def index(self) -> list[dict[str, Any]]:
        p = self.dir / "index.json"
        try:
            mt = p.stat().st_mtime
        except OSError:
            return []
        if mt != self._cache[0]:
            try:
                letters = json.loads(p.read_text(encoding="utf-8")).get("letters", [])
            except (OSError, ValueError):
                return self._cache[1]
            self._cache = (mt, [e for e in letters if ID_RE.match(str(e.get("id", "")))])
        return self._cache[1]

    def letters(self, box: str = "", q: str = "", limit: int = 300) -> list[dict[str, Any]]:
        q = q.strip().lower()
        out = []
        for e in self.index():
            if bool(e.get("spam")) != (box == "spam"):          # спам — только во вкладке «Спам»
                continue
            if box in ("info", "zakaz") and e.get("box") != box:
                continue
            if q and q not in (f"{e.get('from', '')} {e.get('name', '')} {e.get('subject', '')}").lower():
                continue
            out.append(e)
            if len(out) >= limit:
                break
        return out

    def get(self, mid: str) -> dict[str, Any] | None:
        if not ID_RE.match(mid or ""):
            return None
        try:
            return json.loads((self.dir / f"{mid}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def attachment(self, mid: str, n: int) -> tuple[Path, dict[str, Any]] | None:
        m = self.get(mid)
        if not m:
            return None
        for a in m.get("atts", []):
            if a.get("n") == n and a.get("saved"):
                p = self.dir / mid / str(int(n))
                return (p, a) if p.is_file() else None
        return None

    def read_bytes(self, mid: str, n: int) -> bytes | None:
        r = self.attachment(mid, n)
        if not r:
            return None
        try:
            return r[0].read_bytes()
        except OSError:
            return None
