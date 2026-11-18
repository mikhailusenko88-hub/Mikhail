#!/usr/bin/env python3
"""Пополнить CRM → «База дизайнеров» (шифром, как письма) → dz/<id>.json.

  python3 tools/dz.py leads.json [--settings settings.json] [--title "…"]

leads.json — список карточек: {"code": "Д01" | "АВ01", "source": "avito|zoon|sostav|site|other", "prio": "A|B|C",
"name": "…", "person", "kind", "phone", "phone2", "email", "telegram", "whatsapp", "max_link", "vk", "instagram", "site",
"avito_profile", "avito_ad", "area", "about", "hook", "line", "link", "rating", "city_check", "price_from",
"contacts_note", "status", "next_step", "next_at", "note", "last_subject", "history"}.
Новые карточки добавляются целиком. У существующих (по коду) дописываются пустые поля; контакты, вписанные людьми,
не трогаются; статус меняется, только если карточку ещё никто не трогал.
settings.json — {"dz_phone": "…", "dz_mail_day": "15", "dz_max": "…", "dz_tpl_m1": "…"} (необязательно).

Сервер раз в минуту забирает ветку, расшифровывает и загружает (один раз, пуш «Claude пополнил базу дизайнеров»).
Статус: https://crm.nashdekor.ru/api/outbox/status/<id> → saved (в теме — «добавлено N, дополнено M»).
Нужна CRM от 18.11.2026 (раздел «База дизайнеров»).
"""
import argparse
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send import HERE, seal  # noqa: E402


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("leads")
    a.add_argument("--settings", default="")
    a.add_argument("--title", default="")
    a.add_argument("--key", default=os.path.join(HERE, "KEY.pub"))
    o = a.parse_args()
    key = open(o.key, encoding="utf-8").read().strip()
    items = json.load(open(o.leads, encoding="utf-8"))
    if not isinstance(items, list) or not all(isinstance(i, dict) and i.get("code") and i.get("name") for i in items):
        sys.exit("нужен список карточек с code и name")
    p = {"id": str(uuid.uuid4()), "kind": "dz", "title": o.title or f"База дизайнеров: {len(items)} карточек",
         "items": items, "settings": json.load(open(o.settings, encoding="utf-8")) if o.settings else {}}
    os.makedirs(os.path.join(HERE, "dz"), exist_ok=True)
    with open(os.path.join(HERE, "dz", p["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(seal(key, p), f)
    print(p["id"])


if __name__ == "__main__":
    main()
