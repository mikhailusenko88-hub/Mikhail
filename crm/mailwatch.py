#!/usr/bin/env python3
"""Новые письма в ящиках магазина → строки JSON для CRM (пуш «Новое письмо», письмо клиента — в его сделку).

Запускается от root из cron (prostranstvo-crm mail-watch) раз в минуту, только читает заголовки писем:
  python3 -I mailwatch.py ДОМЕН zakaz info
Печатает по строке JSON на каждое новое письмо: {"box", "from", "name", "subject"}.
Помнит, что уже видел, в /var/lib/prostranstvo-mailwatch/seen.json; при первом запуске ничего не шлёт (старые письма — не новость).
Пропускает свои уведомления (noreply@ДОМЕН) и письма, помеченные как спам.
"""
import email
import json
import os
import sys
import time
from email.header import decode_header, make_header
from email.policy import compat32
from email.utils import parseaddr

VMAIL = os.environ.get("MAILWATCH_VMAIL", "/var/mail/vhosts")
STATE_DIR = os.environ.get("MAILWATCH_STATE", "/var/lib/prostranstvo-mailwatch")
KEEP = 8 * 86400          # сколько помнить увиденные письма
FRESH = 3 * 86400         # письма старше — не новость (например, перенос ящика)


def dec(v):
    try:
        return str(make_header(decode_header(v or ""))).strip()
    except Exception:  # noqa: BLE001
        return (v or "").strip()


def main(argv):
    if len(argv) < 2:
        print("Нужно: mailwatch.py ДОМЕН ящик [ящик…]", file=sys.stderr)
        return 2
    domain, boxes = argv[0].lower(), argv[1:]
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    path = os.path.join(STATE_DIR, "seen.json")
    first = not os.path.exists(path)
    try:
        seen = json.load(open(path)) if not first else {}
    except Exception:  # noqa: BLE001
        seen, first = {}, True
    now = time.time()
    out = []
    for box in boxes:
        root = os.path.join(VMAIL, domain, box, "Maildir")
        for sub in ("new", "cur"):                       # телефон может сразу забрать письмо из new в cur
            d = os.path.join(root, sub)
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for fn in names:
                key = box + "/" + fn.split(":", 1)[0]
                if key in seen:
                    continue
                full = os.path.join(d, fn)
                try:
                    mt = os.path.getmtime(full)
                except OSError:
                    continue
                seen[key] = now
                if first or now - mt > FRESH:
                    continue
                try:
                    with open(full, "rb") as f:
                        msg = email.message_from_binary_file(f, policy=compat32, _class=email.message.Message)
                except Exception:  # noqa: BLE001
                    continue
                name, addr = parseaddr(dec(msg.get("From", "")))
                addr = addr.lower()
                if addr == "noreply@" + domain or addr.startswith("mailer-daemon@"):
                    continue
                if (msg.get("X-Spam-Flag", "") or "").strip().upper() == "YES" or (msg.get("X-Spam", "") or "").strip().lower() == "yes":
                    continue
                out.append({"box": box, "from": addr, "name": name, "subject": dec(msg.get("Subject", ""))[:200]})
    seen = {k: v for k, v in seen.items() if now - v < KEEP}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(seen, f)
    os.replace(tmp, path)
    for o in out[:30]:
        print(json.dumps(o, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
