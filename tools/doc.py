#!/usr/bin/env python3
"""Положить файл в раздел CRM «Документы» (шифром, как письма) → docs/<id>.json.

  python3 tools/doc.py --folder "Сертификаты и ТУ" --title "Название" [--until 2027-02-23] [--note "…"] файл [файл …]

Сервер раз в минуту забирает ветку, расшифровывает и кладёт файлы в «Документы» (один раз, пуш «Claude добавил в
«Документы»»). Статус: https://crm.nashdekor.ru/api/outbox/status/<id> → saved. Всего до 30 МБ в одном конверте.
Разделы по умолчанию: ИП, Договоры, Сертификаты и ТУ, Налоги и отчётность, Банк, Из почты, Прочее (можно новый).
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send import HERE, seal  # noqa: E402


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("files", nargs="+")
    a.add_argument("--folder", required=True)
    a.add_argument("--title", default="")
    a.add_argument("--until", default="")
    a.add_argument("--note", default="")
    a.add_argument("--name", default="", help="имя файла в CRM (если один файл)")
    a.add_argument("--key", default=os.path.join(HERE, "KEY.pub"))
    o = a.parse_args()
    key = open(o.key, encoding="utf-8").read().strip()
    atts = []
    for path in o.files:
        name = o.name if (o.name and len(o.files) == 1) else os.path.basename(path)
        atts.append({"name": name, "mime": mimetypes.guess_type(name)[0] or "application/octet-stream",
                     "b64": base64.b64encode(open(path, "rb").read()).decode()})
    p = {"id": str(uuid.uuid4()), "kind": "doc", "folder": o.folder, "title": o.title, "until": o.until, "note": o.note,
         "attachments": atts}
    os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
    with open(os.path.join(HERE, "docs", p["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(seal(key, p), f)
    print(p["id"])


if __name__ == "__main__":
    main()
