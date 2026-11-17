"""Прогон бота «как клиент» без сети и без токенов: ядро + поддельный мессенджер + каталог сайта.

Запуск (из папки bot):
    python3 tests/sim_dialog.py --site /путь/к/0f7s1eez/index.html            # стандартный обход
    python3 tests/sim_dialog.py --site … --crm '{"A907": [1950, 12]}'         # наличие как из CRM
    python3 tests/sim_dialog.py --script мой_сценарий.txt                     # свой сценарий

Сценарий — строки:  «> текст» — клиент пишет; «* Кнопка» — клиент жмёт кнопку (по началу подписи);
«M> текст» — пишет менеджер; «M* Кнопка» — менеджер жмёт кнопку; «# …» — комментарий. Без --site берётся маленький каталог из тестов.
Печатает всё, что бот отправил: текст (без HTML) и кнопки — так видно логику целиком.
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from catalog import Catalog, CatalogStore, apply_crm, parse_catalog  # noqa: E402
from config import Config  # noqa: E402
from core import Engine, Incoming  # noqa: E402
from db import Database  # noqa: E402

CLIENT, MANAGER = 111, 900

DEFAULT_SCRIPT = """
M> /owner 111222
> /start
# артикул просто текстом
> А907
> 3,2 на 2,7
> панель а907 3 на 2,7
> плинтус А703 15 м
> Есть ли А703 в наличии?
> А доставка в Мурино есть?
> 15
> A907 и A703
* Рассчитать A703
> 20 м
# кнопки меню
* Каталог и цены
* Панели под дерево
* Рассчитать
* 2-7
> 3 x 2.7
* Отправить расчёт менеджеру
> Иван
* Напишите мне
* Пропустить
* Согласен
* Написать менеджеру
> Сколько ждать доставку?
> А907 есть в наличии?
M* Ответить
M> Доставим завтра, А907 есть
M> Что-нибудь ещё?
> Спасибо, а плинтус к ней?
M* Закончить
* Рассчитать стену
> /cancel
"""


class FakeTransport:
    channel = "max"

    def __init__(self) -> None:
        self.ids = itertools.count(1)
        self.log: list[tuple] = []

    async def send(self, uid, text, kb=None, reply_to=""):
        mid = str(next(self.ids))
        self.log.append(("send", uid, mid, text, kb))
        return mid

    async def edit(self, uid, mid, text, kb=None):
        self.log.append(("edit", uid, mid, text, kb))
        return True

    async def drop_kb(self, uid, mid):
        pass

    async def answer(self, ev, text="", alert=False):
        if text:
            self.log.append(("toast", ev.user_id, "", text, None))

    async def copy(self, uid, media, kb=None):
        return str(next(self.ids))

    async def link(self):
        return "https://max.ru/id000000000000_bot"

    async def set_commands(self, uid, role):
        pass


def kb_text(kb) -> str:
    kind = "кнопки" if kb.inline else ("меню" if kb.menu else "ответы")
    rows = [" / ".join(b.text + (f" →{b.url}" if b.url else "") for b in row) for row in kb.rows]
    return f"     [{kind}] " + " | ".join(rows)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="", help="index.html сайта (ветка mebel, 0f7s1eez/index.html)")
    ap.add_argument("--crm", default="", help='наличие как из CRM: {"A907": [цена, остаток], …}')
    ap.add_argument("--script", default="", help="файл сценария")
    ap.add_argument("--site-url", default="https://nashdekor.ru")
    args = ap.parse_args()

    if args.site:
        html = open(args.site, encoding="utf-8").read()
    else:
        from conftest import SAMPLE_HTML
        html = SAMPLE_HTML
    products = parse_catalog(html)
    if args.crm:
        products = apply_crm(products, {k.upper(): tuple(v) for k, v in json.loads(args.crm).items()})
    store = CatalogStore("", "", "", 60)
    store.set(Catalog(products, source="сайт"))

    tmp = tempfile.mkdtemp()
    cfg = Config(bot_token="", max_token="x", owner_code="111222", consent_version="1",
                 db_path=os.path.join(tmp, "bot.db"), catalog_file="", catalog_url="", catalog_cache="",
                 site_url=args.site_url)
    t = FakeTransport()
    db = Database(cfg.db_path)
    await db.init()
    engine = Engine(cfg, db, store, t)
    await engine.start()

    script = open(args.script, encoding="utf-8").read() if args.script else DEFAULT_SCRIPT
    pos = 0
    for line in script.strip().splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            if line:
                print("\n" + line)
            continue
        if line.startswith("M> "):
            uid, text = MANAGER, line[3:]
            print(f"\n→ менеджер: «{text}»")
            await engine.handle(Incoming(user_id=uid, first_name="Юлия", text=text, message_id="in"))
        elif line.startswith("> "):
            text = line[2:]
            print(f"\n→ клиент: «{text}»")
            await engine.handle(Incoming(user_id=CLIENT, first_name="Иван", text=text, message_id="in"))
        elif line.startswith(("* ", "M* ")):
            who_uid, name = (MANAGER, "Юлия") if line.startswith("M") else (CLIENT, "Иван")
            label = line.split("* ", 1)[1]
            hit = None
            for kind, uid, mid, _text, kb in reversed(t.log):
                if uid == who_uid and kb:
                    hit = next(((mid, b) for row in kb.rows for b in row if b.text.startswith(label)), None)
                    if hit:
                        break
            role = "менеджера" if who_uid == MANAGER else "клиента"
            if not hit:
                print(f"\n!! у {role} нет кнопки «{label}»")
                continue
            mid, b = hit
            print(f"\n⊙ {'менеджер' if who_uid == MANAGER else 'клиент'} жмёт [{b.text}]")
            if b.url:
                print(f"     (ссылка {b.url})")
                continue
            if b.data:
                await engine.handle(Incoming(user_id=who_uid, first_name=name, data=b.data, message_id=mid,
                                             callback_id="c"))
            else:
                await engine.handle(Incoming(user_id=who_uid, first_name=name, text=b.text, message_id="in"))
        for kind, uid, mid, text, kb in t.log[pos:]:
            who = "клиенту" if uid == CLIENT else "менеджеру" if uid == MANAGER else str(uid)
            if kind == "toast":
                print(f"   ⚑ {who}: всплывашка «{text}»")
                continue
            body = re.sub(r"<[^>]+>", "", text)
            print(f"   {'✎' if kind == 'edit' else '←'} бот {who}:\n" + "\n".join("     " + x for x in body.splitlines()))
            if kb:
                print(kb_text(kb))
        pos = len(t.log)
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
