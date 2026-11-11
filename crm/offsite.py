"""Копии баз у другого провайдера (S3: Selectel и любой совместимый) — без сторонних библиотек.

Подпись запросов — AWS Signature V4 (её понимают Selectel, Yandex Object Storage, VK Cloud, MinIO).
Настройки (адрес, регион, бакет, ключи) хранятся в базе CRM; сюда они приходят словарём.

Командная строка (настройки — JSON на stdin, чтобы ключи не светились в списке процессов):
  python3 offsite.py put ФАЙЛ КЛЮЧ_ОБЪЕКТА   — загрузить файл, проверить размер (HEAD)
  python3 offsite.py check                   — записать маленький файл-проверку и прочитать его заголовок
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

EMPTY_SHA = hashlib.sha256(b"").hexdigest()
TIMEOUT = 120


class OffsiteError(Exception):
    pass


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _q(s: str, safe: str = "-_.~") -> str:
    return urllib.parse.quote(s, safe=safe)


def sign(method: str, host: str, path: str, query: dict[str, str] | None, headers: dict[str, str],
         payload_sha: str, access_key: str, secret_key: str, region: str, now: _dt.datetime,
         service: str = "s3") -> dict[str, str]:
    """Возвращает заголовки с подписью SigV4 (Authorization, x-amz-date, x-amz-content-sha256, host)."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    h = {k.lower(): " ".join(str(v).strip().split()) for k, v in headers.items()}
    h["host"] = host
    h["x-amz-date"] = amz_date
    h["x-amz-content-sha256"] = payload_sha
    names = sorted(h)
    canon_headers = "".join(f"{k}:{h[k]}\n" for k in names)
    signed = ";".join(names)
    q = query or {}
    canon_query = "&".join(f"{_q(k)}={_q(v)}" for k, v in sorted(q.items()))
    canon_path = _q(path, safe="/-_.~")
    creq = "\n".join([method, canon_path, canon_query, canon_headers, signed, payload_sha])
    scope = f"{day}/{region}/{service}/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(creq.encode("utf-8")).hexdigest()])
    k = _hmac(("AWS4" + secret_key).encode("utf-8"), day)
    k = _hmac(k, region)
    k = _hmac(k, service)
    k = _hmac(k, "aws4_request")
    sig = hmac.new(k, sts.encode("utf-8"), hashlib.sha256).hexdigest()
    out = {k2: v for k2, v in h.items()}
    out["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
                            f"SignedHeaders={signed}, Signature={sig}")
    return out


def check_conf(conf: dict[str, Any]) -> dict[str, str]:
    c = {k: str(conf.get(k, "") or "").strip() for k in ("endpoint", "region", "bucket", "key", "secret", "prefix")}
    if not c["endpoint"].startswith(("https://", "http://")):
        raise OffsiteError("адрес хранилища должен начинаться с https://")
    if not c["bucket"] or "/" in c["bucket"]:
        raise OffsiteError("не указан бакет")
    if not c["key"] or not c["secret"]:
        raise OffsiteError("не указаны ключи доступа")
    c["region"] = c["region"] or "ru-1"
    c["prefix"] = c["prefix"].strip("/")
    return c


class S3:
    def __init__(self, conf: dict[str, Any], ctx: ssl.SSLContext | None = None) -> None:
        c = check_conf(conf)
        u = urllib.parse.urlsplit(c["endpoint"].rstrip("/"))
        self.scheme, self.host = u.scheme, u.netloc
        self.base = u.path.rstrip("/")
        self.bucket, self.region = c["bucket"], c["region"]
        self.ak, self.sk = c["key"], c["secret"]
        self.prefix = c["prefix"]
        self.ctx = ctx
        # Selectel и другие облака — адрес бакета поддоменом (virtual-hosted); свой сервер/IP с портом (MinIO) — путём
        host_only = self.host.split(":")[0]
        self.vhost = (":" not in self.host and "." not in self.bucket and not re.match(r"^[0-9.]+$", host_only)
                      and host_only != "localhost")

    def full_key(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def _req(self, method: str, key: str, body: Any = None, size: int = 0, payload_sha: str = EMPTY_SHA,
             headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
        if self.vhost:
            host, path = f"{self.bucket}.{self.host}", f"{self.base}/{key}"
        else:
            host, path = self.host, f"{self.base}/{self.bucket}/{key}"
        hdrs = dict(headers or {})
        if body is not None:
            hdrs["content-length"] = str(size)
        signed = sign(method, host, path, None, hdrs, payload_sha, self.ak, self.sk, self.region,
                      _dt.datetime.now(_dt.timezone.utc))
        url = f"{self.scheme}://{host}{_q(path, safe='/-_.~')}"
        req = urllib.request.Request(url, data=body, method=method, headers=signed)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=self.ctx) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(4096)
        except urllib.error.HTTPError as e:
            return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read(4096)
        except (urllib.error.URLError, OSError) as e:
            raise OffsiteError(f"хранилище не отвечает: {getattr(e, 'reason', e)}") from e

    @staticmethod
    def _why(code: int, body: bytes) -> str:
        m = re.search(r"<Code>([^<]{1,80})</Code>", body.decode("utf-8", "replace"))
        hint = {403: "доступ запрещён — проверьте ключи и права пользователя на бакет",
                404: "бакет не найден — проверьте имя бакета и адрес хранилища",
                301: "бакет в другом регионе — проверьте адрес хранилища"}.get(code, "")
        return f"ошибка {code}{' (' + m.group(1) + ')' if m else ''}{' — ' + hint if hint else ''}"

    def put_file(self, path: str, key: str) -> int:
        h = hashlib.sha256()
        size = 0
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
                size += len(chunk)
        with open(path, "rb") as f:
            code, _, body = self._req("PUT", self.full_key(key), body=f, size=size, payload_sha=h.hexdigest(),
                                      headers={"content-type": "application/octet-stream"})
        if code not in (200, 201):
            raise OffsiteError(self._why(code, body))
        got = self.head(key)
        if got != size:
            raise OffsiteError(f"файл в хранилище другого размера ({got} вместо {size})")
        return size

    def put_bytes(self, data: bytes, key: str) -> None:
        code, _, body = self._req("PUT", self.full_key(key), body=data, size=len(data),
                                  payload_sha=hashlib.sha256(data).hexdigest(), headers={"content-type": "text/plain"})
        if code not in (200, 201):
            raise OffsiteError(self._why(code, body))

    def head(self, key: str) -> int:
        code, hdrs, body = self._req("HEAD", self.full_key(key))
        if code != 200:
            raise OffsiteError(self._why(code, body))
        return int(hdrs.get("content-length", "-1"))


def check(conf: dict[str, Any], ctx: ssl.SSLContext | None = None) -> str:
    s = S3(conf, ctx)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data = f"Проверка связи CRM «Наш декор»: {stamp}\n".encode("utf-8")
    s.put_bytes(data, "proverka.txt")
    n = s.head("proverka.txt")
    if n != len(data):
        raise OffsiteError("проверочный файл записался не полностью")
    return f"связь есть: записан и прочитан {s.full_key('proverka.txt')} в бакете {s.bucket}"


def main(argv: list[str]) -> int:
    try:
        conf = json.loads(sys.stdin.read() or "{}")
        if argv[:1] == ["check"]:
            print(check(conf))
        elif argv[:1] == ["put"] and len(argv) == 3:
            n = S3(conf).put_file(argv[1], argv[2])
            print(f"загружено {n} байт")
        else:
            print(__doc__)
            return 2
    except (OffsiteError, ValueError, OSError) as e:
        print(f"ОШИБКА: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
