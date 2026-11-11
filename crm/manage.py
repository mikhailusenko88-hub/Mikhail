"""Служебные команды CRM (запускаются от пользователя prostranstvo, пароль — только через stdin).

  python3 manage.py init                       — создать/проверить базу
  python3 manage.py ensure-user LOGIN ИМЯ РОЛЬ  — создать, если нет (пароль из stdin); выводит created/exists
  python3 manage.py passwd LOGIN               — новый пароль из stdin
  python3 manage.py users                      — список пользователей (без паролей)
  python3 manage.py import-bot                 — подтянуть заявки из бота сейчас
  python3 manage.py backup ФАЙЛ                — копия базы (sqlite backup)
  python3 manage.py stats                      — сколько клиентов и заявок
  python3 manage.py followups                  — разослать напоминания клиентам, не ответившим на расчёт (cron, раз в день)
  python3 manage.py mail-in                    — новые письма (JSON-строки из mailwatch.py на stdin) → пуши и сделки
  python3 manage.py digest                     — утренняя сводка пушем (cron, раз в день)
  python3 manage.py push "Заголовок" "Текст"   — пуш всем сотрудникам с включёнными уведомлениями
  python3 manage.py tochka-poll                — спросить Точку об открытых ссылках на оплату (cron, раз в 5 минут)
  python3 manage.py outbox                     — отправить новые письма с zapros@ из ветки outbox (cron, раз в минуту)
  python3 manage.py outbox-key                 — открытый ключ для шифрования писем
  python3 manage.py offsite-config             — настройки копий в облако (JSON; пусто, если выключены)
  python3 manage.py offsite-result ok|error ТЕКСТ — записать итог ночной копии в облако
"""

from __future__ import annotations

import os
import sys

from werkzeug.security import generate_password_hash

from store import Catalog, Store


def store() -> Store:
    return Store(os.environ.get("CRM_DB", "/var/lib/prostranstvo/crm.db"),
                 os.environ.get("BOT_DB", "/var/lib/prostranstvo/bot.db"),
                 Catalog(os.environ.get("CATALOG_FILE", "/var/www/prostranstvo/index.html")))


def read_pw() -> str:
    pw = sys.stdin.readline().rstrip("\n")
    if len(pw) < 10:
        sys.exit("пароль короче 10 символов")
    return pw


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd, args = argv[0], argv[1:]
    s = store()
    if cmd == "init":
        print("ok")
    elif cmd == "ensure-user" and len(args) == 3:
        if s.user_by_login(args[0]):
            print("exists")
        else:
            s.add_user(args[0], args[1], args[2], generate_password_hash(read_pw()))
            print("created")
    elif cmd == "passwd" and len(args) == 1:
        u = s.user_by_login(args[0])
        if not u:
            sys.exit(f"нет пользователя {args[0]}")
        s.set_password(int(u["id"]), generate_password_hash(read_pw()))
        s.set_user(int(u["id"]), active=True)
        print("ok")
    elif cmd == "users":
        for u in s.users():
            print(f"{u['login']:<14} {u['name']:<20} {u['role']:<6} {'вкл' if u['active'] else 'выкл'}  вход: {u['last_login'] or '—'}")
    elif cmd == "import-bot":
        print(s.import_bot_leads(force=True))
    elif cmd == "backup" and len(args) == 1:
        s.backup(args[0])
        print("ok")
    elif cmd in ("mail-in", "digest", "push"):
        import json as _json
        from app import create_app
        app = create_app({"PUSH_SYNC": True})
        if cmd == "mail-in":
            items = []
            for line in sys.stdin:
                try:
                    items.append(_json.loads(line))
                except ValueError:
                    pass
            for line in app.extensions["mail_in"](items):
                print(line)
        elif cmd == "digest":
            print(app.extensions["digest"]() or "нечего сообщать")
        else:
            ok, bad = app.extensions["push"].notify(args[0] if args else "Наш декор", args[1] if len(args) > 1 else "", "/")
            print(f"доставлено: {ok}, не доставлено: {bad}")
        print("ok")
    elif cmd == "tochka-poll":
        from app import create_app
        lines = create_app({"PUSH_SYNC": True}).extensions["tochka_poll"]()
        for line in lines:
            print(line)
        print("ok")
    elif cmd in ("outbox", "outbox-key"):
        from app import create_app
        app = create_app({"PUSH_SYNC": True})
        if cmd == "outbox-key":
            print(app.extensions["outbox"].public_key())
        else:
            for line in app.extensions["outbox_run"]():
                print(line)
            print("ok")
    elif cmd == "followups":
        from app import create_app
        for line in create_app().extensions["run_followups"]():
            print(line)
        print("ok")
    elif cmd == "offsite-config":
        import json as _json
        if s.setting("offsite_on", "0") == "1":
            conf = {k: s.setting("offsite_" + k, "") for k in ("endpoint", "region", "bucket", "key", "secret", "prefix")}
            if all(conf[k] for k in ("endpoint", "bucket", "key", "secret")):
                print(_json.dumps(conf))
    elif cmd == "offsite-result" and len(args) >= 1:
        import json as _json
        from datetime import datetime as _dt
        try:
            last = _json.loads(s.setting("offsite_last", "") or "{}")
        except ValueError:
            last = {}
        now = _dt.now().strftime("%Y-%m-%d %H:%M")
        text = " ".join(args[1:])[:300]
        last.update({"at": now, "status": "ok" if args[0] == "ok" else "error", "text": text})
        if args[0] == "ok":
            last["ok_at"] = now
        s.set_setting("offsite_last", _json.dumps(last, ensure_ascii=False))
        print("ok")
    elif cmd == "stats":
        c = s.c()
        print(f"клиентов: {c.execute('SELECT COUNT(*) FROM clients').fetchone()[0]}, "
              f"заявок: {c.execute('SELECT COUNT(*) FROM deals').fetchone()[0]}, "
              f"пользователей: {c.execute('SELECT COUNT(*) FROM users').fetchone()[0]}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
