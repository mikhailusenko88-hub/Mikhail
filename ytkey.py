"""Ключ входа в YouTube для «Kim yutadi?».

Приложение Google (client_id / client_secret) — то же, что у «Білесің бе?» и Flagball Arena: берём его из секрета
FLAGBALL_YT. Вход в сам канал (refresh_token) получает uz_run.py в режиме login (код на google.com/device)
и хранит в ветке зашифрованным (login/uz_token.json) ключом из client_secret: без секрета репозитория он
бесполезен, а копировать что-то с телефона не нужно. Если когда-нибудь появится секрет UZ_YT
(строка {"client_id","client_secret","refresh_token"}) — берётся он.
"""
import base64
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

TOKEN_FILE = Path(__file__).resolve().parent / "login" / "uz_token.json"


def parse_secret(raw):
    """Строка входа как у Flagball: JSON или FB1:<base64>:<проверка>:END (может быть порвана переносами)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if "FB1:" in raw and ":END" in raw:
        body = raw[raw.index("FB1:") + 4:raw.rindex(":END")]
        body = re.sub(r"[^A-Za-z0-9+/=:]", "", body)
        b64, chk = body.rsplit(":", 1)
        data = base64.b64decode(b64 + "=" * (-len(b64) % 4))
        if hashlib.sha256(data).hexdigest()[:8] != chk:
            raise SystemExit("строка входа испорчена (не сходится проверка)")
        return json.loads(data)
    t = raw.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        t = t[i:j + 1]
    t = re.sub(r"[\s​-‏﻿   ]+", "", t)
    return json.loads(t)


def app_client():
    """client_id и client_secret приложения Google (из FLAGBALL_YT)."""
    k = parse_secret(os.environ.get("FLAGBALL_YT", ""))
    if not k or not k.get("client_id") or not k.get("client_secret"):
        raise SystemExit("нет секрета FLAGBALL_YT — не из чего взять ключ приложения Google")
    return k["client_id"], k["client_secret"]


def _key(secret):
    return hashlib.sha256(b"kim-yutadi|" + secret.encode()).digest()


def _stream(key, nonce, n):
    out = bytearray()
    c = 0
    while len(out) < n:
        out += hashlib.sha256(key + nonce + c.to_bytes(4, "big")).digest()
        c += 1
    return bytes(out[:n])


def seal(refresh_token, client_id, client_secret, channel):
    key = _key(client_secret)
    nonce = os.urandom(16)
    pt = refresh_token.encode()
    ct = bytes(a ^ b for a, b in zip(pt, _stream(key, nonce, len(pt))))
    tag = hmac.new(key, nonce + ct, hashlib.sha256).hexdigest()[:32]
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"client_id": client_id, "channel": channel,
                                      "nonce": base64.b64encode(nonce).decode(),
                                      "ct": base64.b64encode(ct).decode(), "tag": tag}, ensure_ascii=False, indent=1))


def credentials():
    """{"client_id","client_secret","refresh_token"} или None, если вход в канал ещё не сделан."""
    own = parse_secret(os.environ.get("UZ_YT", ""))
    if own and all(own.get(x) for x in ("client_id", "client_secret", "refresh_token")):
        return own
    if not TOKEN_FILE.exists():
        return None
    cid, sec = app_client()
    d = json.loads(TOKEN_FILE.read_text())
    if d.get("client_id") != cid:
        raise SystemExit("вход в канал сделан с другим приложением Google — нужен новый вход (mode: login)")
    key = _key(sec)
    nonce, ct = base64.b64decode(d["nonce"]), base64.b64decode(d["ct"])
    if not hmac.compare_digest(hmac.new(key, nonce + ct, hashlib.sha256).hexdigest()[:32], d["tag"]):
        raise SystemExit("ключ входа не расшифровался — нужен новый вход (mode: login)")
    rt = bytes(a ^ b for a, b in zip(ct, _stream(key, nonce, len(ct)))).decode()
    return {"client_id": cid, "client_secret": sec, "refresh_token": rt}
