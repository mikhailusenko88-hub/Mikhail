#!/usr/bin/env python3
"""Зашифровать письмо для отправки сервером «Наш декор» с zapros@ → outbox/<id>.json (см. README.md).

  python3 tools/send.py --to a@b.ru [--to c@d.ru] --subject "Тема" (--body "текст" | --body-file f.txt)
                        [--attach файл ...] [--reply-to info@nashdekor.ru] [--key KEY.pub]
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import uuid
from datetime import datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO = b"nashdekor-outbox-v1"          # как в crm/outbox.py (ветка server)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def seal(pk_b64, payload):
    pk = base64.b64decode(pk_b64)
    eph = X25519PrivateKey.generate()
    epk = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO + epk + pk).derive(
        eph.exchange(X25519PublicKey.from_public_bytes(pk)))
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, json.dumps(payload, ensure_ascii=False).encode(), INFO)
    b = lambda x: base64.b64encode(x).decode()  # noqa: E731
    return {"v": 1, "id": payload["id"], "ts": datetime.now().astimezone().isoformat(timespec="microseconds"),
            "epk": b(epk), "nonce": b(nonce), "ct": b(ct)}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--to", action="append", required=True)
    a.add_argument("--subject", required=True)
    a.add_argument("--body")
    a.add_argument("--body-file")
    a.add_argument("--attach", action="append", default=[])
    a.add_argument("--reply-to", default="")
    a.add_argument("--key", default=os.path.join(HERE, "KEY.pub"))
    o = a.parse_args()
    body = o.body if o.body is not None else open(o.body_file, encoding="utf-8").read()
    key = open(o.key, encoding="utf-8").read().strip() if os.path.exists(o.key) else o.key.strip()
    if len(base64.b64decode(key)) != 32:
        sys.exit("нет открытого ключа сервера (KEY.pub)")
    atts = []
    for path in o.attach:
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        atts.append({"name": os.path.basename(path), "mime": mime, "b64": base64.b64encode(open(path, "rb").read()).decode()})
    p = {"id": str(uuid.uuid4()), "to": o.to, "subject": o.subject, "body": body, "attachments": atts}
    if o.reply_to:
        p["reply_to"] = o.reply_to
    os.makedirs(os.path.join(HERE, "outbox"), exist_ok=True)
    with open(os.path.join(HERE, "outbox", p["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(seal(key, p), f)
    print(p["id"])


if __name__ == "__main__":
    main()
