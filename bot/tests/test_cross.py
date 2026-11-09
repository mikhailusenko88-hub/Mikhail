"""Оба мессенджера сразу: два процесса (Telegram и MAX) с общей базой и очередью доставки.

Сценарий как на сервере: менеджер подключён и в Telegram, и в MAX — уведомления
ему идут в MAX; отгрузка — только в Telegram. Telegram без сбора контактов
(TELEGRAM_COLLECT_CONTACTS=0, по выбору).
"""

from __future__ import annotations

import asyncio
import re

from fakes import MAX_TOKEN, NB, FakeMax, MaxHarness, TgHarness, datas, flush, make_cfg, make_store, payloads, urls

from db import Database

TG_CLIENT, MAX_CLIENT = 111, 5111
MGR_TG, MGR_MAX = 900, 5900
SHIP_TG = 901
NAMES = {TG_CLIENT: ("Иван", "Петров", "ivan"), MAX_CLIENT: ("Мария", None, "maria"),
         MGR_TG: ("Ольга", None, "olga_tg"), MGR_MAX: ("Ольга", None, "olga_max"),
         SHIP_TG: ("Сергей", None, "sergey")}
CODE = "246810"


def run(coro):
    return asyncio.run(coro)


async def setup(tmp_path, **kw):
    fake = FakeMax()
    url = await fake.start()
    cfg = make_cfg(tmp_path, bot_token="42:TEST", max_token=MAX_TOKEN, max_api_url=url,
                   telegram_collect_contacts=False, site_url="https://example.ru", **kw)
    store = make_store()
    t = TgHarness(cfg, Database(cfg.db_path), store, NAMES)        # процесс Telegram
    m = MaxHarness(cfg, Database(cfg.db_path), store, fake, url, NAMES)  # процесс MAX (свой коннект к базе)
    await t.engine.start()
    await m.engine.start()
    return t, m, fake


async def teardown(t: TgHarness, m: MaxHarness, fake: FakeMax) -> None:
    await t.close()
    await m.close()
    t.db.close()
    m.db.close()
    await fake.stop()


def test_two_messengers_one_shop(tmp_path):
    async def scenario():
        t, m, f = await setup(tmp_path)
        s = t.s

        # менеджер — по коду установщика в Telegram, затем подключает MAX кодом-связкой
        await t.send(MGR_TG, f"/owner {CODE}")
        await t.send(MGR_TG, "Уведомления")
        assert "lnk|max" in datas(s.last_req(MGR_TG).reply_markup)
        await t.press(MGR_TG, "lnk|max")
        text = s.last(MGR_TG)
        assert "подключить MAX" in text and "max.ru/id000000000000_bot" in text  # ссылку записал процесс MAX
        await m.send(MGR_MAX, "/join " + re.search(r"/join (\d{6})", text).group(1))
        assert "MAX подключён" in f.last(MGR_MAX)
        mgr = m.team.person_of("max", MGR_MAX)
        assert mgr.person_id == t.team.person_of("tg", MGR_TG).person_id and mgr.channels == ["max", "tg"]

        # отгрузка — только Telegram; приглашение показывает обе ссылки
        await m.press(MGR_MAX, "inv|shipping")
        invite = f.last(MGR_MAX)
        assert "t.me/prostranstvo_test_bot" in invite and "max.ru/id000000000000_bot" in invite
        await t.send(SHIP_TG, "/join " + re.search(r"/join (\d{6})", invite).group(1))
        assert "роль «отгрузка»" in s.last(SHIP_TG)
        await flush(t, m)
        assert "Сергей теперь в команде: отгрузка (Telegram)" in f.last(MGR_MAX)  # менеджеру — в MAX

        # клиент пишет в Telegram: менеджеру в MAX — только «новое сообщение», без имени и текста
        await t.send(TG_CLIENT, "Сколько стоит A907? Мой номер 8 999 123-45-67")
        assert s.find(MGR_TG, "Новое сообщение") is None  # в Telegram менеджеру не дублируем
        await flush(t, m)
        notice = f.find(MGR_MAX, "Новое сообщение в Telegram")
        assert notice and "/history К1" in notice["text"]
        assert "Иван" not in notice["text"] and "8 999" not in notice["text"]
        # переписку она открывает в MAX — там видно всё (данные на сервере в России)
        await m.press(MGR_MAX, "hist|1")
        hist = f.last(MGR_MAX)
        assert "Иван Петров" in hist and "8 999 123-45-67" in hist
        # ответ из MAX уходит клиенту в Telegram — через очередь процесса Telegram
        await m.reply(MGR_MAX, f.mid_of(MGR_MAX, "Переписка"), "A907 — 950 ₽ за штуку")
        assert "Отправляю клиенту в Telegram" in f.last(MGR_MAX)
        assert "950 ₽" not in s.last(TG_CLIENT)
        await flush(t, m)
        assert "Ответ менеджера" in s.last(TG_CLIENT) and "950 ₽" in s.last(TG_CLIENT)
        assert f.last(MGR_MAX) == "Отправлено клиенту."

        # клиент в MAX оставляет заявку: менеджеру — полная карточка в MAX, отгрузке в Telegram — без ПДн
        await m.send(MAX_CLIENT, "Оставить заявку")
        await m.send(MAX_CLIENT, "Мария")
        await m.send(MAX_CLIENT, "+7 921 000-00-01")
        await m.send(MAX_CLIENT, "Васильевский остров, на выходных")
        await m.press(MAX_CLIENT, "lead|yes")
        assert "Заявка №1 принята" in f.last(MAX_CLIENT)
        card = f.find(MGR_MAX, "Новая заявка №1")
        assert card and "+79210000001" in card["text"] and "Васильевский" in card["text"]
        assert payloads(card) == ["shp|1", "hist|2"]
        assert s.find(SHIP_TG, "Новая заявка №1") is None
        await flush(t, m)
        tg_card = s.find(SHIP_TG, "Новая заявка №1")
        assert tg_card and "Откуда: MAX" in tg_card.text and "скрыто" in tg_card.text
        assert "Мария" not in tg_card.text and "+7921" not in tg_card.text and "Васильевский" not in tg_card.text

        # отгрузка: менеджер оформляет в MAX, отгрузка в Telegram видит без адреса и телефона и жмёт «Принял»
        await m.press(MGR_MAX, "shp|1")
        for answer in ("A907 — 20 шт", "Васильевский остров, 5-я линия", "Завтра", "Как в заявке"):
            await m.send(MGR_MAX, answer)
        await m.press(MGR_MAX, "shc|yes")
        assert "Карточка отправлена: Сергей (Telegram)" in f.last(MGR_MAX)
        await flush(t, m)
        ship = s.find(SHIP_TG, "На отгрузку №1")
        assert ship and "A907 — 20 шт" in ship.text and "5-я линия" not in ship.text and "+7921" not in ship.text
        assert datas(ship.reply_markup) == ["sh|acc|1", "sh|done|1", "hist|2"]
        await t.press(SHIP_TG, "sh|acc|1")
        await flush(t, m)
        assert "Отгрузка №1 (Мария): принял(а) Сергей" in f.last(MGR_MAX)  # в MAX — с именем клиента
        await t.press(SHIP_TG, "sh|done|1")
        await flush(t, m)
        assert "отгружено (Сергей)" in f.last(MGR_MAX)
        assert (await m.db.get_lead(1)).status == "shipped"

        # отгрузка отвечает из Telegram клиентке из MAX — ответ уходит в MAX
        await t.reply(SHIP_TG, (await t.relay_ids(SHIP_TG, 2))[-1], "Груз у вас?")
        await flush(t, m)
        assert "Груз у вас?" in f.last(MAX_CLIENT) and "Отправлено клиенту" in s.last(SHIP_TG)
        # а фото из Telegram в MAX не переслать — честно говорим об этом
        from aiogram.types import PhotoSize
        await t.reply(SHIP_TG, (await t.relay_ids(SHIP_TG, 2))[-1], None,
                      photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)])
        assert "Клиент пишет из MAX — фото и файлы туда отсюда не переслать" in s.last(SHIP_TG)

        # менеджер переключает доставку на Telegram — дальше уведомления туда (в Telegram — без ПДн)
        await m.send(MGR_MAX, "Уведомления")
        assert {"dlv|max", "dlv|tg"} <= set(payloads(f.last_body(MGR_MAX)))
        await m.press(MGR_MAX, "dlv|tg")
        assert "буду присылать в Telegram" in f.edits()[-1][1]["text"]  # в MAX сообщение с кнопками правится
        await m.send(MAX_CLIENT, "Спасибо, всё пришло!")
        await flush(t, m)
        fwd = s.find(MGR_TG, "Сообщение от клиента")
        assert fwd and "Клиент К2, MAX" in fwd.text and "Спасибо, всё пришло" not in fwd.text

        # Telegram-клиент с расчётом: продолжить в MAX — расчёт откроется сразу
        await t.send(TG_CLIENT, "Рассчитать стену")
        await t.send(TG_CLIENT, "A907")
        await t.send(TG_CLIENT, "3 x 2,7")
        link = urls(s.last_req(TG_CLIENT).reply_markup)[0]
        assert link.startswith("https://max.ru/id000000000000_bot?start=ls_")
        await m.start(MAX_CLIENT, link.split("start=", 1)[1])  # клиент открыл ссылку в MAX
        assert f"Итого: 19{NB}шт" in f.last(MAX_CLIENT)
        assert payloads(f.last_body(MAX_CLIENT))[0] == "ls|A907|3000|2700"  # там можно отправить менеджеру
        await teardown(t, m, f)

    run(scenario())


def test_one_messenger_down_other_works(tmp_path):
    async def scenario():
        t, m, f = await setup(tmp_path)
        await m.send(MGR_MAX, f"/owner {CODE}")
        # Telegram «лежит»: его процесс не разбирает очередь — MAX-клиенты и менеджер в MAX работают
        await m.send(MAX_CLIENT, "Добрый день! Есть плинтус A703?")
        assert f.find(MGR_MAX, "Есть плинтус A703?")
        await m.send(MAX_CLIENT, "Рассчитать стену")
        await m.send(MAX_CLIENT, "A703")
        await m.send(MAX_CLIENT, "15")
        assert f"Итого: 9{NB}шт" in f.last(MAX_CLIENT)
        # ответ клиенту из Telegram, пока MAX «лежит», ждёт в очереди и уходит, когда MAX поднимется
        await m.send(MGR_MAX, "Уведомления")
        await m.press(MGR_MAX, "lnk|tg")
        link_code = re.search(r"/join (\d{6})", f.last(MGR_MAX)).group(1)
        await t.send(MGR_TG, f"/join {link_code}")
        await t.send(MGR_TG, "/reply К1 Есть, 28 штук в коробке")
        assert "Отправляю клиенту в MAX" in t.s.last(MGR_TG)
        assert await m.db.outbox_count("max") == 1
        await flush(t)  # процесс MAX ещё не работает
        assert "28 штук" not in f.last(MAX_CLIENT)
        await flush(m, t)  # MAX поднялся
        assert "28 штук" in f.last(MAX_CLIENT) and await m.db.outbox_count("max") == 0
        assert "Отправлено клиенту" in t.s.last(MGR_TG)
        # MAX API недоступен совсем — элемент очереди не теряется, а ждёт повтора
        await f.stop()
        await t.send(MGR_TG, "/reply К1 Ещё одно сообщение")
        await flush(m)
        assert await m.db.outbox_count("max") == 1
        items = await m.db.outbox_pending("max")
        assert items == []  # отложено на потом (повтор через 15 секунд, потом реже)
        await t.close()
        await m.close()
        t.db.close()
        m.db.close()

    run(scenario())
