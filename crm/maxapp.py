"""Мини-приложение MAX (сайт внутри MAX): проверка подписей, которые MAX ставит токеном бота.

Сайт, открытый из MAX, присылает в заявке:
  max.init    — строка WebAppData (данные запуска: пользователь MAX, start_param, auth_date, hash);
  max.contact — ответ WebApp.requestContact(): {phone, authDate, hash} — номер, который человек отправил из MAX.
CRM проверяет обе подписи ключом /etc/prostranstvo/max-app.key (тот же токен бота MAX, пишет install-bot.sh).

Данные запуска — по документации dev.max.ru/docs/webapps/validation:
  secret = HMAC_SHA256(key="WebAppData", msg=токен); hash = hex(HMAC_SHA256(secret, "k=v\\n…" по алфавиту, без hash)).
Номер телефона — dev.max.ru/docs/webapps/bridge (requestContact): HMAC_SHA256 от «authDate=…\\nphone=…\\nuserId=…»
(по алфавиту, телефон без «+»), ключ — токен бота. Формат результата там не уточнён: принимаем hex и base64,
ключ — токен или secret из данных запуска; какой вариант совпал — пишем в журнал.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any

log = logging.getLogger("crm.maxapp")

INIT_MAX_AGE = 7 * 24 * 3600        # данные запуска: мини-приложение могут держать открытым долго
CONTACT_MAX_AGE = 24 * 3600         # номер из MAX: заявку отправляют сразу после «Отправить номер»


def read_key(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _hmac(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def _same(digest: bytes, given: str) -> bool:
    g = (given or "").strip()
    if not g:
        return False
    if hmac.compare_digest(digest.hex(), g.lower()):
        return True
    return any(hmac.compare_digest(enc.rstrip("="), g.rstrip("="))
               for enc in (base64.b64encode(digest).decode(), base64.urlsafe_b64encode(digest).decode()))


def _age_ok(ts: Any, max_age: int, now: float | None = None) -> bool:
    try:
        t = float(ts)
    except (TypeError, ValueError):
        return False
    if t > 1e12:                      # миллисекунды
        t /= 1000
    n = time.time() if now is None else now
    return -300 <= n - t <= max_age


def check_init(raw: str, token: str, now: float | None = None) -> dict[str, Any] | None:
    """Данные запуска мини-приложения → {"id", "name", "start_param"} или None, если подпись не сошлась."""
    if not raw or not token or len(raw) > 8000:
        return None
    try:
        s = raw if "&" in raw else urllib.parse.unquote(raw)     # бывает закодирована целиком ещё раз
        pairs = urllib.parse.parse_qsl(s, keep_blank_values=True, strict_parsing=False)
    except ValueError:
        return None
    keys = [k for k, _ in pairs]
    if keys.count("hash") != 1 or len(set(keys)) != len(keys):
        return None
    d = dict(pairs)
    given = d.pop("hash")
    check = "\n".join(f"{k}={d[k]}" for k in sorted(d)).encode()
    secret = _hmac(b"WebAppData", token.encode())
    if not _same(_hmac(secret, check), given):
        return None
    if not _age_ok(d.get("auth_date"), INIT_MAX_AGE, now):
        return None
    try:
        user = json.loads(d.get("user") or "{}")
    except ValueError:
        user = {}
    uid = user.get("id") if isinstance(user, dict) else None
    if uid in (None, ""):
        return None
    name = " ".join(str(user.get(k) or "").strip() for k in ("first_name", "last_name")).strip()
    return {"id": str(uid), "name": name[:120], "start_param": str(d.get("start_param") or "")[:200]}


def check_contact(contact: Any, user_id: str, token: str, now: float | None = None) -> str:
    """Номер из WebApp.requestContact() → «+7…», если подпись MAX сошлась; иначе пустая строка."""
    if not isinstance(contact, dict) or not user_id or not token:
        return ""
    phone = "".join(ch for ch in str(contact.get("phone") or "") if ch.isdigit())
    auth = str(contact.get("authDate") or contact.get("auth_date") or "").strip()
    given = str(contact.get("hash") or "")
    if not (10 <= len(phone) <= 15) or not auth or not given or not _age_ok(auth, CONTACT_MAX_AGE, now):
        return ""
    keys = {"токен": token.encode(), "secret": _hmac(b"WebAppData", token.encode())}
    for pv in (phone, "+" + phone):
        msg = f"authDate={auth}\nphone={pv}\nuserId={user_id}".encode()
        for kname, key in keys.items():
            if _same(_hmac(key, msg), given):
                log.info("мини-приложение MAX: номер подтверждён (ключ: %s, телефон %s)", kname,
                         "без +" if pv == phone else "с +")
                return "+" + phone
    log.warning("мини-приложение MAX: подпись номера не сошлась — номер записан без пометки «подтверждён»")
    return ""


def lead_info(data: Any, key_file: str) -> dict[str, Any]:
    """Поле max из заявки сайта → {"user": {...} | None, "phone": "+7…" | ""}. Без ключа — ничего не подтверждаем."""
    out: dict[str, Any] = {"user": None, "phone": ""}
    if not isinstance(data, dict):
        return out
    token = read_key(key_file)
    if not token:
        return out
    user = check_init(str(data.get("init") or ""), token)
    out["user"] = user
    if user:
        out["phone"] = check_contact(data.get("contact"), user["id"], token)
    return out
