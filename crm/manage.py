"""Служебные команды CRM (запускаются от пользователя prostranstvo, пароль — только через stdin).

  python3 manage.py init                       — создать/проверить базу
  python3 manage.py ensure-user LOGIN ИМЯ РОЛЬ  — создать, если нет (пароль из stdin); выводит created/exists
  python3 manage.py passwd LOGIN               — новый пароль из stdin
  python3 manage.py users                      — список пользователей (без паролей)
  python3 manage.py import-bot                 — подтянуть заявки из бота сейчас
  python3 manage.py backup ФАЙЛ                — копия базы (sqlite backup)
  python3 manage.py stats                      — сколько клиентов и заявок
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
