"""Веб-пуши CRM на телефоны сотрудников (Web Push: RFC 8030, шифрование RFC 8291, ключи VAPID RFC 8292).

Без сторонних сервисов и библиотек, кроме cryptography (пакет Ubuntu python3-cryptography).
Подписки хранятся в таблице push_subs (одна строка — один телефон/браузер сотрудника),
ключи VAPID — в settings (создаются при первом обращении). iPhone: iOS 16.4+, CRM открыта со значка на экране «Домой».
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import urlsplit

log = logging.getLogger("crm.push")

try:  # без cryptography CRM работает, просто без пушей
    from cryptography.hazmat.primitives import hashes, hmac, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAVE_CRYPTO = True
except Exception:  # noqa: BLE001
    HAVE_CRYPTO = False

# Куда разрешено слать (защита от подмены адреса подписки): службы пушей браузеров
PUSH_HOSTS = ("push.apple.com", "fcm.googleapis.com", "push.services.mozilla.com", "notify.windows.com", "push.yandex.net")


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hmac(key: bytes, data: bytes) -> bytes:
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def encrypt(payload: bytes, ua_public: bytes, auth_secret: bytes, salt: bytes | None = None,
            as_private: Any = None) -> bytes:
    """Тело пуша по RFC 8291 (aes128gcm, одна запись): заголовок salt|rs|idlen|keyid + шифротекст."""
    salt = salt or os.urandom(16)
    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    as_public = as_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    ecdh = as_private.exchange(ec.ECDH(), ua_key)
    prk_key = _hmac(auth_secret, ecdh)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_public + as_public + b"\x01")
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    ct = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    rs = 4096
    return salt + rs.to_bytes(4, "big") + bytes([len(as_public)]) + as_public + ct


def decrypt(body: bytes, ua_private: Any, auth_secret: bytes) -> bytes:
    """Обратная операция (как в браузере) — для проверок и тестов."""
    salt, idlen = body[:16], body[20]
    as_public = body[21:21 + idlen]
    ct = body[21 + idlen:]
    ua_public = ua_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    ecdh = ua_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))
    prk_key = _hmac(auth_secret, ecdh)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_public + as_public + b"\x01")
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    pt = AESGCM(cek).decrypt(nonce, ct, None)
    return pt.rstrip(b"\x00")[:-1]


def http_post(url: str, headers: dict[str, str], body: bytes) -> int:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001 — сеть, DNS, таймаут
        return 0


class WebPush:
    def __init__(self, store: Any, subject: str, allow_hosts: tuple[str, ...] = PUSH_HOSTS) -> None:
        self.store = store
        self.subject = subject                     # mailto:… — так служба пушей знает, кому писать о проблемах
        self.allow_hosts = allow_hosts
        self.transport: Callable[[str, dict[str, str], bytes], int] = http_post
        self.sync = False                          # в тестах и в cron — без фонового потока
        self._jwt: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return HAVE_CRYPTO

    # -------------------------------------------------------------- ключи VAPID
    def _private(self) -> Any:
        with self._lock:
            pem = self.store.setting("vapid_private", "")
            if not pem:
                k = ec.generate_private_key(ec.SECP256R1())
                pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()).decode()
                self.store.set_setting("vapid_private", pem)
            return serialization.load_pem_private_key(pem.encode(), password=None)

    def public_key(self) -> str:
        if not self.enabled:
            return ""
        return b64u(self._private().public_key().public_bytes(serialization.Encoding.X962,
                                                               serialization.PublicFormat.UncompressedPoint))

    def _vapid(self, endpoint: str) -> str:
        p = urlsplit(endpoint)
        aud = f"{p.scheme}://{p.netloc}"
        now = time.time()
        cached = self._jwt.get(aud)
        if cached and cached[0] > now + 300:
            return cached[1]
        exp = int(now) + 1800                       # Apple принимает токены не длиннее часа
        head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
        claims = b64u(json.dumps({"aud": aud, "exp": exp, "sub": self.subject}, separators=(",", ":")).encode())
        signing = f"{head}.{claims}".encode()
        r, s = decode_dss_signature(self._private().sign(signing, ec.ECDSA(hashes.SHA256())))
        tok = f"{head}.{claims}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"
        self._jwt[aud] = (exp, tok)
        return tok

    # -------------------------------------------------------------- подписки
    def endpoint_ok(self, endpoint: str) -> bool:
        p = urlsplit(endpoint)
        host = (p.hostname or "").lower()
        return p.scheme == "https" and any(host == h or host.endswith("." + h) for h in self.allow_hosts)

    def subscribe(self, user_id: int, sub: dict[str, Any], ua: str = "") -> str:
        """Сохранить подписку браузера. Возвращает '' или текст ошибки."""
        endpoint = str(sub.get("endpoint") or "")
        keys = sub.get("keys") or {}
        p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
        if not self.endpoint_ok(endpoint):
            return "неизвестная служба уведомлений"
        try:
            if len(unb64u(p256dh)) != 65 or len(unb64u(auth)) != 16:
                return "неверные ключи подписки"
        except Exception:  # noqa: BLE001
            return "неверные ключи подписки"
        self.store.push_sub_save(user_id, endpoint, p256dh, auth, ua[:200])
        return ""

    # -------------------------------------------------------------- отправка
    def send_one(self, sub: Any, data: dict[str, Any]) -> int:
        body = json.dumps(data, ensure_ascii=False).encode()[:3000]
        enc = encrypt(body, unb64u(sub["p256dh"]), unb64u(sub["auth"]))
        headers = {
            "Content-Type": "application/octet-stream", "Content-Encoding": "aes128gcm",
            "TTL": "86400", "Urgency": "high",
            "Authorization": f"vapid t={self._vapid(sub['endpoint'])}, k={self.public_key()}",
        }
        st = self.transport(sub["endpoint"], headers, enc)
        if st in (200, 201, 202):
            self.store.push_sub_result(int(sub["id"]), True)
        elif st in (404, 410):                       # подписка больше не действует (удалили значок, сбросили разрешение)
            self.store.push_sub_delete(int(sub["id"]))
        else:
            log.warning("пуш не принят службой: %s", st)
            self.store.push_sub_result(int(sub["id"]), False)
        return st

    def _send_many(self, subs: list[Any], data: dict[str, Any]) -> tuple[int, int]:
        ok = bad = 0
        for s in subs:
            try:
                st = self.send_one(s, data)
            except Exception:  # noqa: BLE001
                log.exception("пуш не отправлен")
                st = 0
            if st in (200, 201, 202):
                ok += 1
            else:
                bad += 1
        return ok, bad

    def notify(self, title: str, body: str = "", url: str = "/", user_ids: list[int] | None = None, tag: str = "") -> tuple[int, int]:
        """Пуш всем сотрудникам с включёнными уведомлениями (или выбранным). В веб-приложении — в фоне."""
        if not self.enabled:
            return 0, 0
        subs = self.store.push_subs(user_ids=user_ids)
        if not subs:
            return 0, 0
        data = {"title": title[:120], "body": body[:300], "url": url or "/", "tag": tag[:60]}
        if self.sync:
            return self._send_many(subs, data)
        threading.Thread(target=self._send_many, args=(subs, data), daemon=True).start()
        return len(subs), 0
