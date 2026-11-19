#!/usr/bin/env python3
"""Пополнить CRM → «База дизайнеров» (шифром, как письма) → dz/<id>.json.

  python3 tools/dz.py leads.json [--settings settings.json] [--title "…"]
  python3 tools/dz.py - --marks marks.json [--title "…"]     → только отметки Claude, без карточек

marks.json — {"replies": [{"code": "Д03", "channel": "email", "result": "interest|question|later|refused", "comment": "…"}],
"marks": [{"code": "Д06", "touch": "заметка в историю", "status": "…", "next_step": "…", "next_at": "ГГГГ-ММ-ДД"}]}
(CRM от 19.11: ответ ставит статус и следующий шаг, как кнопка «Ответили?» в карточке).

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
    a.add_argument("--marks", default="", help="отметки Claude: replies и marks (JSON)")
    a.add_argument("--key", default=os.path.join(HERE, "KEY.pub"))
    o = a.parse_args()
    key = open(o.key, encoding="utf-8").read().strip()
    items = [] if o.leads == "-" else json.load(open(o.leads, encoding="utf-8"))
    if not isinstance(items, list) or not all(isinstance(i, dict) and i.get("code") and i.get("name") for i in items):
        sys.exit("нужен список карточек с code и name")
    marks = json.load(open(o.marks, encoding="utf-8")) if o.marks else {}
    if not items and not marks:
        sys.exit("нечего отправлять: нет ни карточек, ни отметок")
    n = len(marks.get("replies") or []) + len(marks.get("marks") or [])
    p = {"id": str(uuid.uuid4()), "kind": "dz",
         "title": o.title or (f"База дизайнеров: {len(items)} карточек" if items else f"Отметки Claude: {n}"),
         "items": items, "settings": json.load(open(o.settings, encoding="utf-8")) if o.settings else {},
         "replies": marks.get("replies") or [], "marks": marks.get("marks") or []}
    os.makedirs(os.path.join(HERE, "dz"), exist_ok=True)
    with open(os.path.join(HERE, "dz", p["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(seal(key, p), f)
    print(p["id"])


if __name__ == "__main__":
    main()
