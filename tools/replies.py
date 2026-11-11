#!/usr/bin/env python3
"""Ответы на письма с zapros@ — читает только Claude (шифр для его ключа).

1) Ключ (один раз на сеанс; закрытый — только в ~/.nashdekor-reader, в git его нет):
       python3 tools/replies.py key            → пишет READER.pub (закоммитить и запушить в ветку outbox)
   Сервер подхватит ключ в течение минуты (в CRM придёт пуш «Claude подключился к ответам на запросы»).
2) Забрать шифр: https://crm.nashdekor.ru/api/outbox/replies (из облака — через workflow replies-fetch,
   ветка replies, файл replies.json).
3) Прочитать:
       python3 tools/replies.py read replies.json [--out папка]   → текст писем; вложения — в папку
"""
import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO = b"nashdekor-replies-v1"
HOME = Path(os.environ.get("READER_HOME", Path.home() / ".nashdekor-reader"))
MSK = timezone(timedelta(hours=3))


def pub_b64(sk):
    return base64.b64encode(sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def load_sk():
    p = HOME / "sk"
    if not p.exists():
        sys.exit("Ключа нет — сначала: python3 tools/replies.py key (и запушить READER.pub)")
    return X25519PrivateKey.from_private_bytes(base64.b64decode(p.read_text().strip()))


def cmd_key(a):
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    p = HOME / "sk"
    if p.exists() and not a.new:
        sk = load_sk()
    else:
        sk = X25519PrivateKey.generate()
        raw = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(base64.b64encode(raw).decode() + "\n")
    pub = pub_b64(sk)
    Path(a.repo, "READER.pub").write_text(pub + "\n")
    print(pub)


def unseal(sk, env):
    pk = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    epk = base64.b64decode(env["epk"])
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO + epk + pk).derive(
        sk.exchange(X25519PublicKey.from_public_bytes(epk)))
    return json.loads(ChaCha20Poly1305(key).decrypt(base64.b64decode(env["nonce"]), base64.b64decode(env["ct"]), INFO))


def cmd_read(a):
    d = json.loads(Path(a.file).read_text(encoding="utf-8"))
    if d.get("off"):
        sys.exit("В CRM выключено «Claude видит ответы на свои запросы».")
    if d.get("nokey"):
        sys.exit("Сервер ещё не видит READER.pub — запушить ключ и подождать минуту.")
    sk = load_sk()
    if d.get("key") and not pub_b64(sk).startswith(d["key"]):
        sys.exit(f"Шифр для другого ключа ({d['key']}…) — сервер ещё не подхватил новый READER.pub, снять заново через минуту.")
    items = d.get("items", [])
    print(f"Ответов: {len(items)}")
    for env in items:
        x = unseal(sk, env)
        when = datetime.fromtimestamp(int(x.get("ts") or 0), MSK).strftime("%d.%m.%Y %H:%M")
        print("=" * 60)
        print(f"{when} МСК · {x.get('name') or ''} <{x.get('from')}>{' · В СПАМЕ' if x.get('spam') else ''}")
        print(f"Тема: {x.get('subject')}")
        print("-" * 60)
        print((x.get("text") or "(без текста)").strip())
        for at in x.get("atts") or []:
            line = f"Вложение: {at['name']} ({at.get('size', 0)} байт)"
            if at.get("b64") and a.out:
                dd = Path(a.out, x["id"]); dd.mkdir(parents=True, exist_ok=True)
                fn = dd / (re.sub(r'[\\/:*?"<>|]', "_", at["name"]) or "file")
                fn.write_bytes(base64.b64decode(at["b64"]))
                line += f" → {fn}"
            elif at.get("skipped"):
                line += " — слишком большое, не передано"
            print(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("key"); k.add_argument("--new", action="store_true", help="новый ключ"); k.add_argument("--repo", default=".")
    r = sub.add_parser("read"); r.add_argument("file"); r.add_argument("--out", default="")
    a = ap.parse_args()
    {"key": cmd_key, "read": cmd_read}[a.cmd](a)


if __name__ == "__main__":
    main()
