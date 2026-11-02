"""Сквозные сценарии в Telegram: настоящий aiogram + ядро + поддельный Bot API."""

from __future__ import annotations

import asyncio
import re

from aiogram.methods import CopyMessage, EditMessageText
from aiogram.types import Contact, PhotoSize
from fakes import NB, TgHarness, buttons, datas, make_cfg, make_store, urls

import core
from db import Database

CLIENT, CLIENT2, STRANGER = 111, 222, 333
MANAGER, SHIPPER = 900, 901
NAMES = {CLIENT: ("Иван", "Петров", "ivan"), CLIENT2: ("Анна", None, None), STRANGER: ("Кто-то", None, None),
         MANAGER: ("Ольга", None, "olga_mgr"), SHIPPER: ("Сергей", None, "sergey_ship")}
CODE = "246810"


def run(coro):
    return asyncio.run(coro)


def harness(tmp_path, **kw) -> TgHarness:
    cfg = make_cfg(tmp_path, **kw)
    return TgHarness(cfg, Database(cfg.db_path), make_store(), NAMES)


async def make_team(h: TgHarness) -> None:
    """Менеджер — по коду установщика, отгрузка — по приглашению менеджера."""
    s = h.s
    await h.send(MANAGER, "/owner 000000")
    assert "неверный" in s.last(MANAGER)
    await h.send(MANAGER, f"/owner {CODE}")
    assert "вы менеджер" in s.last(MANAGER)
    assert buttons(s.last_req(MANAGER).reply_markup) == [
        "Заявки", "Отгрузки", "Рассчитать стену", "Каталог и цены", "Команда", "Статистика", "Уведомления", "Помощь"]
    await h.send(STRANGER, f"/owner {CODE}")
    assert "неверный, уже использован" in s.last(STRANGER)
    await h.send(MANAGER, "Команда")
    assert "Ольга" in s.last(MANAGER) and "менеджер" in s.last(MANAGER)
    await h.press(MANAGER, "inv|shipping")
    invite = s.last(MANAGER)
    assert "отгрузка" in invite and "t.me/prostranstvo_test_bot" in invite and "24 часа" in invite
    code = re.search(r"/join (\d{6})", invite).group(1)
    await h.send(MANAGER, f"/join {code}")  # единственный менеджер не «понижает» сам себя
    assert "единственный менеджер" in s.last(MANAGER)
    await h.send(SHIPPER, "/join 999999")
    assert "неверный" in s.last(SHIPPER)
    await h.send(SHIPPER, f"/join {code}")
    assert "роль «отгрузка»" in s.last(SHIPPER)
    assert buttons(s.last_req(SHIPPER).reply_markup) == [
        "Заявки", "Отгрузки", "Рассчитать стену", "Каталог и цены", "Уведомления", "Помощь"]
    assert "Сергей теперь в команде: отгрузка (Telegram)" in s.last(MANAGER)
    await h.send(STRANGER, f"/join {code}")  # код одноразовый
    assert "неверный" in s.last(STRANGER)
    await h.send(SHIPPER, "/team")
    assert "только менеджер" in s.last(SHIPPER)


def test_team_leads_and_shipping_in_telegram(tmp_path):
    """Telegram с приёмом заявок (TELEGRAM_COLLECT_CONTACTS=1) — как первый выпуск бота."""
    async def scenario():
        h = harness(tmp_path)
        s = h.s
        await h.send(CLIENT, "/start")
        assert "Здравствуйте" in s.last(CLIENT) and "Санкт-Петербурге" in s.last(CLIENT)
        assert buttons(s.last_req(CLIENT).reply_markup) == [
            "Рассчитать стену", "Каталог и цены", "Оставить заявку", "Связаться с менеджером"]
        assert "Сайт:" not in s.last(CLIENT)
        await make_team(h)

        # расчёт A907 на стену 3 × 2,7 м
        await h.send(CLIENT, "Рассчитать стену")
        assert "cg|panel" in datas(s.last_req(CLIENT).reply_markup)
        await h.press(CLIENT, "cg|panel")
        assert "ca|A907" in datas(s.last_req(CLIENT).reply_markup)
        await h.press(CLIENT, "ca|A907")
        assert "ширину стены" in s.last(CLIENT)
        await h.send(CLIENT, "abc")
        assert "Не понял число" in s.last(CLIENT)
        await h.send(CLIENT, "3")
        assert "высоту стены" in s.last(CLIENT)
        await h.send(CLIENT, "2,7")
        res = s.last(CLIENT)
        assert "17 в ряд" in res and f"+2{NB}шт" in res and f"Итого: 19{NB}шт" in res
        assert f"1{NB}коробка по 12{NB}шт + 7{NB}шт" in res and f"18{NB}050{NB}₽" in res and "предварительные" in res
        assert datas(s.last_req(CLIENT).reply_markup) == ["ls|A907|3000|2700", "cn"]
        await h.press(CLIENT, "ca|A907")
        await h.send(CLIENT, "3 x 2,7")
        assert f"Итого: 19{NB}шт" in s.last(CLIENT)

        # «Отправить расчёт менеджеру» → заявка
        await h.press(CLIENT, "ls|A907|3000|2700")
        assert "Отправим расчёт менеджеру" in s.last(CLIENT)
        await h.send(CLIENT, "Иван")
        assert s.last_req(CLIENT).reply_markup.keyboard[0][0].request_contact is True
        assert buttons(s.last_req(CLIENT).reply_markup)[1] == "Напишите мне в Telegram"
        await h.send(CLIENT, "привет")
        assert "Не похоже на телефон" in s.last(CLIENT)
        await h.send(CLIENT, None, contact=Contact(phone_number="79991234567", first_name="Иван", user_id=CLIENT))
        await h.send(CLIENT, "Пропустить")
        review, consent = s.texts(CLIENT)[-2:]
        assert "Проверьте заявку" in review and "+79991234567" in review and "A907" in review
        assert "152-ФЗ" in consent
        assert (await h.db.stats()).leads_total == 0  # до «Согласен» ничего не сохранено
        await h.press(CLIENT, "lead|yes")
        assert "Заявка №1 принята" in s.last(CLIENT) and "рабочее время" in s.last(CLIENT)
        await h.press(CLIENT, "lead|yes")  # повторное нажатие не создаёт вторую заявку
        assert (await h.db.stats()).leads_total == 1
        card_m, card_s = s.find(MANAGER, "Новая заявка №1"), s.find(SHIPPER, "Новая заявка №1")
        assert card_m and card_s
        assert "+79991234567" in card_m.text and "@ivan" in card_m.text and "A907" in card_m.text
        assert "клиент К1" in card_m.text and "Откуда: Telegram" in card_m.text
        assert datas(card_m.reply_markup) == ["shp|1", "hist|1"]
        assert datas(card_s.reply_markup) == ["hist|1"]

        # сообщения клиента: менеджеру — все, отгрузке — только если включила
        n = s.count(SHIPPER)
        await h.send(CLIENT, "Есть ли A907 в наличии?")
        assert "передано менеджеру" in s.last(CLIENT)
        fwd = s.find(MANAGER, "Есть ли A907 в наличии?")
        assert fwd and "Иван Петров" in fwd.text and "@ivan" in fwd.text and "клиент К1, Telegram" in fwd.text
        assert s.count(SHIPPER) == n
        await h.send(SHIPPER, "Уведомления")
        assert "только заявки и отгрузки" in s.last(SHIPPER)
        assert "lnk|max" not in datas(s.last_req(SHIPPER).reply_markup)  # MAX не подключён — не предлагаем
        await h.press(SHIPPER, "ntf|all")
        assert "все сообщения клиентов" in s.last(SHIPPER)
        await h.send(CLIENT, "А доставка есть?")
        assert s.find(SHIPPER, "А доставка есть?")
        await h.send(SHIPPER, "/notify orders")
        n = s.count(SHIPPER)
        await h.send(CLIENT, "Третий вопрос")
        assert s.count(SHIPPER) == n

        # ответ менеджера (reply) → клиенту
        rid = (await h.relay_ids(MANAGER, 1))[-1]
        await h.reply(MANAGER, rid, "Да, есть, 12 коробок")
        assert "Ответ менеджера" in s.last(CLIENT) and "12 коробок" in s.last(CLIENT)
        assert "Отправлено клиенту" in s.last(MANAGER)

        # переписка у отгрузки и ответ из неё
        await h.send(SHIPPER, "/history #1")
        hist = s.last(SHIPPER)
        assert "Переписка: Иван Петров" in hist and "Есть ли A907" in hist and "Магазин (Ольга)" in hist
        assert "№1 (новая)" in hist
        await h.reply(SHIPPER, (await h.relay_ids(SHIPPER, 1))[-1], "Отгрузим завтра")
        assert "Отгрузим завтра" in s.last(CLIENT)
        await h.send(SHIPPER, "/history К1")
        assert "Магазин (Сергей)" in s.last(SHIPPER)

        # «Передать на отгрузку»
        await h.press(MANAGER, "shp|1")
        assert "Отгрузка по заявке №1" in s.last(MANAGER)
        assert buttons(s.last_req(MANAGER).reply_markup) == ["Как в заявке", "Отмена"]
        await h.send(MANAGER, "Как в заявке")
        await h.send(MANAGER, "Самовывоз")
        await h.send(MANAGER, "Завтра")
        assert "+79991234567" in s.last(MANAGER)
        await h.send(MANAGER, "Как в заявке")
        review = s.last_req(MANAGER)
        assert "Проверьте отгрузку" in review.text and "Самовывоз" in review.text and "завтра" in review.text
        assert datas(review.reply_markup) == ["shc|yes", "shc|no"]
        await h.press(MANAGER, "shc|yes")
        assert (await h.db.get_lead(1)).status == "confirmed"
        ship_s = s.find(SHIPPER, "На отгрузку №1")
        assert ship_s and "Самовывоз" in ship_s.text and "+79991234567" in ship_s.text and "подтверждена" in ship_s.text
        assert datas(ship_s.reply_markup) == ["sh|acc|1", "sh|done|1", "hist|1"]
        assert "sh|cancel|1" in datas(s.find(MANAGER, "На отгрузку №1").reply_markup)
        assert "Карточка отправлена: Сергей (Telegram)" in s.last(MANAGER)

        await h.send(SHIPPER, "Отгрузки")
        assert s.find(SHIPPER, "Открытые отгрузки: 1")
        await h.press(SHIPPER, "sh|cancel|1")
        assert "только менеджер" in s.toasts()[-1]
        await h.press(SHIPPER, "sh|acc|1")
        assert s.toasts()[-1] == "Готово" and (await h.db.get_lead(1)).status == "shipping"
        assert "принял(а) Сергей — статус «на отгрузке»" in s.last(MANAGER)
        edited = s.last_req(SHIPPER)
        assert isinstance(edited, EditMessageText) and datas(edited.reply_markup) == ["sh|done|1", "hist|1"]
        await h.press(SHIPPER, "sh|acc|1")
        assert s.toasts()[-1] == "Уже отмечено"
        await h.press(SHIPPER, "sh|done|1")
        assert (await h.db.get_lead(1)).status == "shipped"
        assert "Отгрузка №1 (Иван): отгружено (Сергей)" in s.last(MANAGER)
        await h.send(SHIPPER, "/orders")
        assert "Открытых отгрузок нет" in s.last(SHIPPER)

        # вторая заявка: всё руками, потом менеджер отменяет отгрузку
        await h.send(CLIENT2, "Оставить заявку")
        await h.send(CLIENT2, "Анна")
        await h.send(CLIENT2, "Напишите мне в Telegram")
        await h.send(CLIENT2, "Плинтус A703, 15 м")
        await h.press(CLIENT2, "lead|yes")
        assert "Заявка №2 принята" in s.last(CLIENT2)
        await h.press(MANAGER, "shp|2")
        await h.send(MANAGER, "A703 — 9 шт")
        await h.send(MANAGER, "Приморский район, ул. Примерная, 1")
        await h.send(MANAGER, "05.11 в 10:00")
        assert "Напишите номер" in s.last(MANAGER)
        await h.send(MANAGER, "телефон")
        assert "Не похоже на телефон" in s.last(MANAGER)
        await h.send(MANAGER, "8 911 000-00-00")
        await h.press(MANAGER, "shc|yes")
        assert "+79110000000" in s.find(SHIPPER, "На отгрузку №2").text
        await h.press(MANAGER, "sh|cancel|2")
        assert "Отгрузка №2 (Анна) отменена (Ольга)" in s.last(SHIPPER)
        assert (await h.db.get_lead(2)).status == "new"
        await h.press(SHIPPER, "sh|acc|2")
        assert s.toasts()[-1] == "Отгрузка отменена"

        # заявки и статистика
        await h.send(MANAGER, "Заявки")
        lst = s.last_req(MANAGER)
        assert "№1" in lst.text and "отгружено" in lst.text and datas(lst.reply_markup) == ["ld|2", "ld|1"]
        await h.press(MANAGER, "ld|1")
        assert "Заявка №1" in s.last(MANAGER) and "Статус: отгружено" in s.last(MANAGER)
        await h.send(MANAGER, "Статистика")
        st = s.last(MANAGER)
        assert "Заявки: сегодня 2" in st and "отгружено за 7 дней 1" in st and "Каталог: 9 позиций" in st
        await h.send(SHIPPER, "/stats")
        assert "только менеджер" in s.last(SHIPPER)

        # /reply по номеру заявки и клиента, заблокировавший клиент
        await h.send(MANAGER, "/reply 1 Спасибо за покупку!")
        assert "Спасибо за покупку!" in s.last(CLIENT)
        await h.send(MANAGER, "/reply К1 И ещё раз спасибо")
        assert "И ещё раз спасибо" in s.last(CLIENT)
        s.blocked.add(CLIENT2)
        await h.send(MANAGER, "/reply #2 алло")
        assert "Не удалось отправить" in s.last(MANAGER)
        s.blocked.clear()
        await h.send(MANAGER, "/reply #77 нет такой")
        assert "нет" in s.last(MANAGER).lower()

        # сотрудник пишет не ответом — никуда не уходит; старые кнопки — «не действует»
        n = s.count(CLIENT)
        await h.send(MANAGER, "просто текст")
        assert "никуда не отправлено" in s.last(MANAGER) and s.count(CLIENT) == n
        await h.reply(MANAGER, 1, "ответ не туда")
        assert "Не понял, кому ответить" in s.last(MANAGER)
        await h.send(CLIENT2, "/leads")
        assert "Последние заявки" not in s.last(CLIENT2)
        await h.press(STRANGER, "sh|done|1")
        assert "больше не действует" in s.toasts()[-1]
        n = s.count(MANAGER)
        await h.send(CLIENT2, "Пропустить")  # кнопка шага, нажатая позже, — не вопрос менеджеру
        assert s.count(MANAGER) == n and "кнопками" in s.last(CLIENT2)

        # убрать человека из команды (по номеру из «Команды»)
        olga = h.team.person_of("tg", MANAGER).person_id
        sergey = h.team.person_of("tg", SHIPPER).person_id
        await h.send(MANAGER, f"/remove {olga}")
        assert "последнего менеджера" in s.last(MANAGER)
        await h.send(MANAGER, "Команда")
        assert f"rm|{sergey}" in datas(s.last_req(MANAGER).reply_markup)
        await h.press(MANAGER, f"rm|{sergey}")
        assert datas(s.last_req(MANAGER).reply_markup) == [f"rmy|{sergey}", "rmn"]
        await h.press(MANAGER, f"rmy|{sergey}")
        assert "больше не в команде" in s.last(MANAGER) and "Вас убрали из команды" in s.last(SHIPPER)
        assert h.team.person_of("tg", SHIPPER) is None

        # отзыв согласия: отгруженный заказ остаётся, остальное удаляется
        await h.send(CLIENT, "/delete_me")
        assert datas(s.last_req(CLIENT).reply_markup) == ["del|yes", "del|no"]
        await h.press(CLIENT, "del|yes")
        assert "удалены" in s.last(CLIENT) and "требует закон" in s.last(CLIENT)
        assert "попросил(а) удалить свои данные" in s.last(MANAGER) and "Иван" not in s.last(MANAGER)
        assert await h.db.get_lead(1) is not None and await h.db.history(1) == []
        await h.close()
        h.db.close()

    run(scenario())


def test_telegram_without_contacts(tmp_path):
    """TELEGRAM_COLLECT_CONTACTS=0 (по умолчанию): заявки — на сайт и в MAX, сотрудникам в Telegram — без ПДн."""
    async def scenario():
        h = harness(tmp_path, telegram_collect_contacts=False, site_url="https://example.ru",
                    max_bot_url="https://max.ru/id000000000000_bot")
        s = h.s
        await h.send(MANAGER, f"/owner {CODE}")
        await h.send(CLIENT, "/start")
        assert "на сайте или в нашем боте в MAX" in s.last(CLIENT)

        await h.send(CLIENT, "Оставить заявку")
        assert "оставьте заявку на сайте или в нашем боте в MAX" in s.last(CLIENT)
        assert urls(s.last_req(CLIENT).reply_markup) == ["https://example.ru/#order",
                                                          "https://max.ru/id000000000000_bot?start=lead"]
        assert h.engine.state(CLIENT) == ""  # имя и телефон здесь не спрашиваем

        await h.send(CLIENT, "Рассчитать стену")
        await h.send(CLIENT, "A907")
        await h.send(CLIENT, "3 x 2,7")
        res = s.last_req(CLIENT)
        assert f"Итого: 19{NB}шт" in res.text
        payload = core.calc_link_payload("ls", "A907", 3000, 2700)
        assert payload == "ls_41393037_3000_2700"
        assert urls(res.reply_markup) == [f"https://max.ru/id000000000000_bot?start={payload}",
                                          "https://example.ru/#order"]
        assert datas(res.reply_markup) == ["cn"]
        await h.press(CLIENT, "ls|A907|3000|2700")  # старая кнопка — снова ссылки, без анкеты
        assert "Продолжить в MAX" in s.last(CLIENT) and h.engine.state(CLIENT) == ""

        await h.send(CLIENT, "Связаться с менеджером")
        assert "на сайте или в MAX" in s.last(CLIENT)
        await h.send(CLIENT, "Мой телефон 8 999 123-45-67, перезвоните")
        notice = s.last(MANAGER)
        assert "Новое сообщение в Telegram" in notice and "/history К1" in notice
        assert "Иван" not in notice and "8 999" not in notice and "перезвоните" not in notice
        assert datas(s.last_req(MANAGER).reply_markup) == ["hist|1"]
        await h.send(CLIENT, None, photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)])
        assert "Новое сообщение (фото) в Telegram" in s.last(MANAGER)
        assert not any(isinstance(r, CopyMessage) for r in s.requests)  # фото в Telegram сотрудникам не пересылаем

        # в Telegram сотрудник видит переписку без имён и текстов клиента
        await h.press(MANAGER, "hist|1")
        hist = s.last(MANAGER)
        assert "Клиент К1, Telegram" in hist and "скрыто" in hist and "перезвоните" not in hist and "Иван" not in hist
        # но ответить может
        await h.reply(MANAGER, (await h.relay_ids(MANAGER, 1))[-1], "Перезвоним через час")
        assert "Перезвоним через час" in s.last(CLIENT) and "Отправлено клиенту" in s.last(MANAGER)

        # расчёт из ссылки MAX открывается сразу (так это сработает и в боте MAX)
        await h.send(CLIENT2, f"/start {payload}")
        assert f"Итого: 19{NB}шт" in s.last(CLIENT2)
        await h.close()
        h.db.close()

    run(scenario())


def test_catalog_photo_linear_and_deep_links(tmp_path):
    async def scenario():
        h = harness(tmp_path)
        s = h.s
        await h.send(MANAGER, f"/owner {CODE}")
        await h.send(CLIENT2, "Рассчитать стену")
        await h.send(CLIENT2, "а703")  # русская «а»
        assert "длину в метрах" in s.last(CLIENT2)
        await h.send(CLIENT2, "15")
        res = s.last(CLIENT2)
        assert f"Итого: 9{NB}шт" in res and "поштучно" in res and f"2{NB}610{NB}₽" in res
        assert datas(s.last_req(CLIENT2).reply_markup) == ["ll|A703|15000", "cn"]
        await h.send(CLIENT2, "Рассчитать стену")
        await h.send(CLIENT2, "A9")
        assert "Не нашёл артикул" in s.last(CLIENT2)

        await h.send(CLIENT2, "Каталог и цены")
        await h.press(CLIENT2, "kg|plinth")
        cat = s.last(CLIENT2)
        assert "A703" in cat and f"290{NB}₽/шт" in cat and f"коробка 28{NB}шт = 8{NB}120{NB}₽" in cat
        assert "cgn|plinth" in datas(s.last_req(CLIENT2).reply_markup)

        await h.send(CLIENT2, None, photo=[PhotoSize(file_id="f1", file_unique_id="u1", width=10, height=10)],
                     caption="моя стена")
        assert s.copies_to(MANAGER) and "(фото)" in s.find(MANAGER, "Сообщение от клиента").text
        n = s.count(CLIENT2)
        await h.send(CLIENT2, "ещё вопрос")
        assert s.count(CLIENT2) == n  # «передано менеджеру» не чаще раза в 10 минут

        await h.send(CLIENT, "/start A907")
        assert "ширину стены" in s.last(CLIENT)
        await h.send(CLIENT, "/start catalog")
        assert "Каталог ARTDEC" in s.last(CLIENT)
        for _ in range(5):
            await h.send(STRANGER, "/owner 111111")
        await h.send(STRANGER, f"/owner {CODE}")
        assert "Слишком много попыток" in s.last(STRANGER)
        await h.close()
        h.db.close()

    run(scenario())


def test_static_admin_ids(tmp_path):
    async def scenario():
        h = harness(tmp_path, admin_ids=frozenset({MANAGER}))
        await h.engine.start()
        await h.send(CLIENT, "Привет")
        assert h.s.find(MANAGER, "Привет")
        olga = h.team.person_of("tg", MANAGER).person_id
        await h.send(MANAGER, f"/remove {olga}")
        assert "настройках сервера" in h.s.last(MANAGER)
        await h.close()
        h.db.close()

    run(scenario())


def test_parse_helpers():
    assert core.parse_contact("+7 999 123-45-67") == "+79991234567"
    assert core.parse_contact("89991234567") == "+79991234567"
    assert core.parse_contact("9991234567") == "+79991234567"
    assert core.parse_contact("@ivan_petrov") == "Telegram @ivan_petrov"
    assert core.parse_contact("ivan@example.ru") == "ivan@example.ru"
    assert core.parse_contact("123") is None and core.parse_contact("позвоните") is None
    assert core.parse_phone("Telegram @ivan") is None
    assert core.phone_from_contact("8 (999) 123-45-67") == "+79991234567"
    assert core.parse_cmd("/history@prostranstvo_bot К5") == ("history", "К5")
    assert core.parse_cmd("привет") == ("", "")
