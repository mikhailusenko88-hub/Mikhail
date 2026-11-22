#!/usr/bin/env python3
"""Ответы на письма с zapros@ — читает только Claude (шифр для его ключа).

1) Ключ (один раз на сеанс; закрытый — только в ~/.nashdekor-reader, в git его нет):
       python3 tools/replies.py key            → пишет READER.pub (закоммитить и запушить в ветку outbox)
   Сервер подхватит ключ в течение минуты (в CRM придёт пуш «Claude подключился к ответам на запросы»).
2) Забрать шифр: https://crm.nashdekor.ru/api/outbox/replies (из облака — через workflow replies-fetch,
   ветка replies, файл replies.json).
3) Прочитать:
       python3 tools/replies.py read replies.json [--out папка] [--json ответы.json]   → текст писем; вложения — в папку
   У ответа дизайнера из «Базы дизайнеров» — строка «Дизайнер: Д03 …» (его карточка).
4) Сводка базы дизайнеров (CRM от 19.11): https://crm.nashdekor.ru/api/dz/export (тот же workflow, файл dz.json):
       python3 tools/replies.py dz dz.json --out база.json        → карточки, касания, отправки моделей, тексты
5) Статистика сайта (CRM от 23.11): https://crm.nashdekor.ru/api/site/export (тот же workflow, файл site.json).
   Свой ключ SITE.pub — чтобы разбор сайта не сбивал READER.pub у сеанса, который ведёт дизайнеров:
       python3 tools/replies.py key --site                         → пишет SITE.pub (закоммитить и запушить в outbox)
       python3 tools/replies.py site site.json --out сайт.json     → 30 дней: лента посетителей, где теряем людей, блоки, нажатия
   Нет SITE.pub на сервере — CRM шифрует для READER.pub.
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
INFO_DZ = b"nashdekor-dz-v1"
INFO_SITE = b"nashdekor-site-v1"
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
    Path(a.repo, "SITE.pub" if a.site else "READER.pub").write_text(pub + "\n")
    print(pub)


def unseal(sk, env, info=INFO):
    pk = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    epk = base64.b64decode(env["epk"])
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info + epk + pk).derive(
        sk.exchange(X25519PublicKey.from_public_bytes(epk)))
    return json.loads(ChaCha20Poly1305(key).decrypt(base64.b64decode(env["nonce"]), base64.b64decode(env["ct"]), info))


def check_head(d, sk):
    if d.get("off"):
        sys.exit("В CRM выключено «Claude видит ответы» (CRM → Ещё → Исходящие).")
    if d.get("nokey"):
        sys.exit("Сервер ещё не видит READER.pub — запушить ключ и подождать минуту.")
    if d.get("key") and not pub_b64(sk).startswith(d["key"]):
        sys.exit(f"Шифр для другого ключа ({d['key']}…) — сервер ещё не подхватил новый READER.pub, снять заново через минуту.")


def cmd_dz(a):
    d = json.loads(Path(a.file).read_text(encoding="utf-8"))
    sk = load_sk()
    check_head(d, sk)
    x = unseal(sk, d["item"], INFO_DZ)
    Path(a.out).write_text(json.dumps(x, ensure_ascii=False, indent=1), encoding="utf-8")
    st = {}
    for l in x.get("leads", []):
        st[l["status"]] = st.get(l["status"], 0) + 1
    print(f"Сводка на {x.get('at')}: карточек {len(x.get('leads', []))}, касаний {len(x.get('touches', []))}, "
          f"отправок моделей {len(x.get('docs', []))}; статусы {st}; писем сегодня {x.get('sent_today')}/{x.get('limit')} → {a.out}")


def cmd_site(a):
    d = json.loads(Path(a.file).read_text(encoding="utf-8"))
    if d.get("off"):
        sys.exit("В CRM выключено «Claude видит статистику сайта» (CRM → Сайт → Выключатели) или общая галочка в «Исходящих».")
    if d.get("nokey"):
        sys.exit("Сервер ещё не видит ключ — запушить SITE.pub (или READER.pub) и подождать минуту.")
    sk = load_sk()
    check_head(d, sk)
    x = unseal(sk, d["item"], INFO_SITE)
    Path(a.out).write_text(json.dumps(x, ensure_ascii=False, indent=1), encoding="utf-8")
    r30, r7 = x.get("d30") or {}, x.get("d7") or {}
    print(f"Статистика на {x.get('day')}: за 7 дней {r7.get('visitors')} чел., {r7.get('leads')} заявок; "
          f"за 30 дней {r30.get('visitors')} чел., {r30.get('leads')} заявок; в ленте {len(r30.get('feed') or [])} посетителей → {a.out}")
    print("Откуда (30 дн.):", ", ".join(f"{n} {c}" for n, c in (r30.get("sources") or [])[:8]))
    ux = r30.get("ux") or {}
    for p in (ux.get("pages") or [])[:8]:
        print(f"  {p['name'][:50]}: {p['who']} чел., смотрят {p['median_sec']} с, до конца {p['s90']}, ушли с неё {p['exit']}, сразу ушли {p['bounce']}/{p['landing']}")
    if ux.get("clicks"):
        print("Нажатия без ответа:", "; ".join(f"{c['page'][:30]} — {c['label']} ({c['who']})" for c in ux["clicks"][:6]))
    if r30.get("filtered"):
        print("Отсеяно:", ", ".join(f"{s} — {w} ({n})" for s, w, n in r30["filtered"][:6]))


def cmd_read(a):
    d = json.loads(Path(a.file).read_text(encoding="utf-8"))
    if d.get("off"):
        sys.exit("В CRM выключено «Claude видит ответы на свои запросы».")
    if d.get("nokey"):
        sys.exit("Сервер ещё не видит READER.pub — запушить ключ и подождать минуту.")
    sk = load_sk()
    check_head(d, sk)
    items = d.get("items", [])
    out_json = []
    print(f"Ответов: {len(items)}")
    for env in items:
        x = unseal(sk, env)
        when = datetime.fromtimestamp(int(x.get("ts") or 0), MSK).strftime("%d.%m.%Y %H:%M")
        print("=" * 60)
        print(f"{when} МСК · {x.get('name') or ''} <{x.get('from')}>{' · В СПАМЕ' if x.get('spam') else ''}")
        if x.get("dz"):
            print(f"Дизайнер: {x['dz'].get('code')} {x['dz'].get('name')} (статус {x['dz'].get('status')})")
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
        out_json.append({k: v for k, v in x.items() if k != "atts"} | {"atts": [at.get("name") for at in x.get("atts") or []]})
    if a.json:
        Path(a.json).write_text(json.dumps(out_json, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("key"); k.add_argument("--new", action="store_true", help="новый ключ"); k.add_argument("--repo", default=".")
    k.add_argument("--site", action="store_true", help="записать ключ в SITE.pub (статистика сайта), а не в READER.pub")
    r = sub.add_parser("read"); r.add_argument("file"); r.add_argument("--out", default=""); r.add_argument("--json", default="")
    z = sub.add_parser("dz"); z.add_argument("file"); z.add_argument("--out", default="dz-base.json")
    st = sub.add_parser("site"); st.add_argument("file"); st.add_argument("--out", default="site-stats.json")
    a = ap.parse_args()
    {"key": cmd_key, "read": cmd_read, "dz": cmd_dz, "site": cmd_site}[a.cmd](a)


if __name__ == "__main__":
    main()
