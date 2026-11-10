"""Исходящие письма с zapros@ДОМЕН («Наш декор — запросы»): поставщикам, лабораториям, перевозчикам.

Как устроено (паролей нигде нет):
  * у CRM своя пара ключей X25519; закрытый ключ — только в базе CRM на сервере, открытый — /api/outbox/key;
  * письмо шифруется открытым ключом (seal) и кладётся файлом outbox/<id>.json в ветку outbox репозитория
    на GitHub — там лежит только шифр, прочитать его может лишь сервер;
  * раз в минуту cron (prostranstvo-crm outbox) забирает ветку, расшифровывает новые письма и отправляет
    их через почту своего сервера от «Наш декор <zapros@ДОМЕН>»; ответы — на info@ (zapros@ пересылается туда же);
  * каждое письмо отправляется один раз (id в базе), в сутки — не больше лимита, отправку можно выключить
    в CRM → Ещё → Исходящие; статус письма без содержимого — /api/outbox/status/<id>, открытый ключ — /api/outbox/key.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

log = logging.getLogger("crm.outbox")

INFO = b"nashdekor-outbox-v1"
REPO_URL = "https://github.com/mikhailusenko88-hub/Mikhail.git"
BRANCH = "outbox"
ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]{1,64}@[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,24}$")
MAX_RCPT = 5
MAX_BODY = 100_000
MAX_ATTACH = 7 * 1024 * 1024
DEFAULT_DAILY = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox_mail (
    id          TEXT PRIMARY KEY,
    received_at TEXT NOT NULL,
    sent_at     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'new',   -- new | sent | retry | error
    attempts    INTEGER NOT NULL DEFAULT 0,
    error       TEXT NOT NULL DEFAULT '',
    to_addr     TEXT NOT NULL DEFAULT '',
    reply_to    TEXT NOT NULL DEFAULT '',
    subject     TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL DEFAULT '',
    att_names   TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT ''       -- расшифрованное письмо (для повторной попытки), после отправки очищается
)
"""


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _ub64(s: str) -> bytes:
    return base64.b64decode(s.encode(), validate=True)


def _key(shared: bytes, epk: bytes, pk: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO + epk + pk).derive(shared)


def _raw_pub(k: X25519PrivateKey) -> bytes:
    return k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def seal(pk_b64: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Зашифровать письмо открытым ключом сервера. Конверт: {v, id, ts, epk, nonce, ct}."""
    pk = _ub64(pk_b64)
    eph = X25519PrivateKey.generate()
    epk = _raw_pub(eph)
    key = _key(eph.exchange(X25519PublicKey.from_public_bytes(pk)), epk, pk)
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, json.dumps(payload, ensure_ascii=False).encode(), INFO)
    ts = datetime.now().astimezone().isoformat(timespec="microseconds")     # порядок отправки (не секрет)
    return {"v": 1, "id": payload["id"], "ts": ts, "epk": _b64(epk), "nonce": _b64(nonce), "ct": _b64(ct)}


def unseal(sk: X25519PrivateKey, env: dict[str, Any]) -> dict[str, Any]:
    pk = _raw_pub(sk)
    epk = _ub64(env["epk"])
    key = _key(sk.exchange(X25519PublicKey.from_public_bytes(epk)), epk, pk)
    return json.loads(ChaCha20Poly1305(key).decrypt(_ub64(env["nonce"]), _ub64(env["ct"]), INFO).decode())


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Outbox:
    def __init__(self, store: Any, domain: str, send: Callable[..., bool], notify: Callable[[str, str, str], Any],
                 repo_url: str = "", workdir: str = "") -> None:
        self.s = store
        self.domain = domain or "nashdekor.ru"
        self.send = send
        self.notify = notify
        self.repo_url = repo_url or os.environ.get("OUTBOX_REPO", REPO_URL)
        self.workdir = Path(workdir or os.environ.get("OUTBOX_DIR", "/var/lib/prostranstvo/outbox-git"))
        c = self.s.c()
        c.execute(SCHEMA)

    # ------------------------------------------------------------------ ключи
    def _sk(self) -> X25519PrivateKey:
        raw = self.s.setting("outbox_sk", "")
        if not raw:
            k = X25519PrivateKey.generate()
            new = _b64(k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                       serialization.NoEncryption()))
            with self.s.tx() as c:                        # если ключ уже создал другой процесс — остаётся его ключ
                c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES ('outbox_sk', ?)", (new,))
            raw = self.s.setting("outbox_sk", new)
        return X25519PrivateKey.from_private_bytes(_ub64(raw))

    def public_key(self) -> str:
        return _b64(_raw_pub(self._sk()))

    # ------------------------------------------------------------------ настройки
    def enabled(self) -> bool:
        return self.s.setting("outbox_on", "1") == "1"

    def daily_limit(self) -> int:
        try:
            return max(1, min(200, int(self.s.setting("outbox_daily", str(DEFAULT_DAILY)))))
        except ValueError:
            return DEFAULT_DAILY

    def set_options(self, on: bool, daily: Any) -> None:
        self.s.set_setting("outbox_on", "1" if on else "0")
        try:
            self.s.set_setting("outbox_daily", str(max(1, min(200, int(str(daily).strip())))))
        except ValueError:
            pass

    def sender(self) -> str:
        return f"Наш декор <zapros@{self.domain}>"

    # ------------------------------------------------------------------ git
    def _git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.workdir.parent),
               "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"}
        base = cwd or self.workdir.parent                 # не текущая папка: у cron это /root, недоступный пользователю CRM
        base.mkdir(parents=True, exist_ok=True)
        return subprocess.run(["git", *args], cwd=str(base), env=env, capture_output=True,
                              text=True, timeout=90, check=False)

    def fetch(self) -> list[Path]:
        """Забрать ветку outbox (только если она изменилась). Возвращает файлы писем."""
        r = self._git("ls-remote", self.repo_url, f"refs/heads/{BRANCH}")
        if r.returncode != 0:
            raise RuntimeError("GitHub не ответил: " + (r.stderr.strip().splitlines() or ["?"])[-1][:200])
        head = (r.stdout.split() or [""])[0]
        if not head:
            return []                                     # ветки ещё нет — писем нет
        if not (self.workdir / ".git").is_dir():
            self.workdir.parent.mkdir(parents=True, exist_ok=True)
            r = self._git("clone", "--quiet", "--depth", "1", "--single-branch", "--branch", BRANCH,
                          self.repo_url, str(self.workdir))
            if r.returncode != 0:
                raise RuntimeError("не удалось скачать ветку outbox: " + r.stderr.strip()[-200:])
        elif self.s.setting("outbox_head", "") != head:
            for args in (("fetch", "--quiet", "--depth", "1", "origin", BRANCH), ("reset", "--quiet", "--hard", "FETCH_HEAD")):
                r = self._git(*args, cwd=self.workdir)
                if r.returncode != 0:
                    raise RuntimeError("не удалось обновить ветку outbox: " + r.stderr.strip()[-200:])
        self.s.set_setting("outbox_head", head)
        d = self.workdir / "outbox"
        return sorted(d.glob("*.json")) if d.is_dir() else []

    # ------------------------------------------------------------------ письма
    def _row(self, mid: str) -> Any:
        return self.s.c().execute("SELECT * FROM outbox_mail WHERE id=?", (mid,)).fetchone()

    def _validate(self, p: dict[str, Any], mid: str) -> tuple[dict[str, Any] | None, str]:
        if p.get("id") != mid:
            return None, "id письма не совпадает с конвертом"
        to = p.get("to")
        to_list = [to] if isinstance(to, str) else list(to or [])
        to_list = [str(x).strip() for x in to_list if str(x).strip()]
        if not to_list or len(to_list) > MAX_RCPT:
            return None, f"получателей должно быть от 1 до {MAX_RCPT}"
        bad = [x for x in to_list if not EMAIL_RE.match(x)]
        if bad:
            return None, "непонятный адрес: " + bad[0][:80]
        subject = str(p.get("subject") or "").strip()
        if not subject or len(subject) > 200 or "\n" in subject or "\r" in subject:
            return None, "тема письма пустая, длиннее 200 символов или в несколько строк"
        body = str(p.get("body") or "")
        if not body.strip() or len(body) > MAX_BODY:
            return None, "текст письма пустой или слишком длинный"
        reply = str(p.get("reply_to") or f"info@{self.domain}").strip()
        if not EMAIL_RE.match(reply):
            return None, "непонятный адрес для ответа"
        atts, total = [], 0
        for a in p.get("attachments") or []:
            try:
                data = _ub64(str(a.get("b64") or ""))
            except Exception:  # noqa: BLE001
                return None, "вложение повреждено"
            total += len(data)
            name = re.sub(r"[\\/\r\n\t\"]", "_", str(a.get("name") or "file"))[:120] or "file"
            mime = str(a.get("mime") or "application/octet-stream")
            if not re.match(r"^[a-z]+/[A-Za-z0-9.+-]+$", mime):
                mime = "application/octet-stream"
            atts.append((name, data, mime))
        if total > MAX_ATTACH:
            return None, "вложения больше 7 МБ"
        return {"to": ", ".join(to_list), "subject": subject, "body": body, "reply_to": reply, "attachments": atts}, ""

    def sent_today(self) -> int:
        day = datetime.now().astimezone().date().isoformat()
        return int(self.s.c().execute("SELECT COUNT(*) FROM outbox_mail WHERE status='sent' AND substr(sent_at,1,10)=?",
                                      (day,)).fetchone()[0])

    def _record(self, mid: str, **f: Any) -> None:
        with self.s.tx() as c:
            if not c.execute("SELECT 1 FROM outbox_mail WHERE id=?", (mid,)).fetchone():
                c.execute("INSERT INTO outbox_mail(id, received_at) VALUES (?,?)", (mid, _now()))
            if f:
                c.execute("UPDATE outbox_mail SET " + ", ".join(f"{k}=?" for k in f) + " WHERE id=?", (*f.values(), mid))

    def _deliver(self, mid: str, m: dict[str, Any]) -> str:
        ok = self.send(m["to"], m["subject"], m["body"], sender=self.sender(), reply_to=m["reply_to"],
                       attachments=m["attachments"])
        row = self._row(mid)
        attempts = int(row["attempts"]) + 1 if row else 1
        if ok:
            self._record(mid, status="sent", sent_at=_now(), attempts=attempts, error="", payload="")
            self.notify("Письмо отправлено с zapros@", f"{m['to']}: {m['subject']}"[:180], "/outbox")
            return f"{mid}: отправлено → {m['to']}"
        if attempts >= 3:
            self._record(mid, status="error", attempts=attempts, error="почтовый сервер не принял письмо", payload="")
            self.notify("Письмо НЕ отправлено", f"{m['to']}: {m['subject']}"[:180], "/outbox")
            return f"{mid}: ошибка — почтовый сервер не принял (3 попытки)"
        self._record(mid, status="retry", attempts=attempts, error="почтовый сервер не принял, повторю")
        return f"{mid}: не принято, попытка {attempts}"

    def run(self) -> list[str]:
        """Одна проходка cron: новые письма из ветки outbox и повторы неотправленных."""
        if not self.enabled():
            return ["отправка выключена в CRM"]
        out: list[str] = []
        sk = self._sk()
        limit = self.daily_limit()
        # повторы (почтовый сервер не принял в прошлый раз)
        for row in self.s.c().execute("SELECT * FROM outbox_mail WHERE status='retry' ORDER BY received_at").fetchall():
            if self.sent_today() >= limit:
                return out + [f"лимит {limit} писем в сутки — остальное завтра"]
            m, err = self._validate(json.loads(row["payload"] or "{}"), row["id"])
            out.append(self._deliver(row["id"], m) if m else f"{row['id']}: {err}")
        try:
            files = self.fetch()
        except Exception as e:  # noqa: BLE001
            return out + [str(e)]
        todo = []
        for f in files:
            mid = f.stem
            if not ID_RE.match(mid) or self._row(mid):
                continue
            try:
                env = json.loads(f.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                env = {}
            todo.append((str(env.get("ts") or ""), mid, env))
        for _ts, mid, env in sorted(todo, key=lambda x: (x[0], x[1])):   # в том порядке, в каком письма написаны
            if self.sent_today() >= limit:
                out.append(f"лимит {limit} писем в сутки — остальное завтра")
                break
            try:
                if env.get("v") != 1 or env.get("id") != mid:
                    raise ValueError("не тот формат")
                p = unseal(sk, env)
            except Exception:  # noqa: BLE001
                self._record(mid, status="error", error="не расшифровалось (чужой ключ или повреждённый файл)")
                out.append(f"{mid}: не расшифровалось")
                continue
            m, err = self._validate(p, mid)
            if not m:
                self._record(mid, status="error", error=err, subject=str(p.get("subject") or "")[:200],
                             to_addr=str(p.get("to") or "")[:300])
                self.notify("Письмо НЕ отправлено", err[:180], "/outbox")
                out.append(f"{mid}: {err}")
                continue
            self._record(mid, status="new", to_addr=m["to"], reply_to=m["reply_to"], subject=m["subject"], body=m["body"],
                         att_names=", ".join(a[0] for a in m["attachments"]),
                         payload=json.dumps(p, ensure_ascii=False))
            out.append(self._deliver(mid, m))
        return out

    def status(self, mid: str) -> dict[str, str]:
        row = self._row(mid) if ID_RE.match(mid or "") else None
        if not row:
            return {"status": "unknown"}
        return {"status": row["status"], "sent_at": row["sent_at"], "error": row["error"]}

    def recent(self, limit: int = 100) -> list[Any]:
        return self.s.c().execute("SELECT id, received_at, sent_at, status, attempts, error, to_addr, reply_to, subject, body,"
                                  " att_names FROM outbox_mail ORDER BY received_at DESC LIMIT ?", (limit,)).fetchall()
