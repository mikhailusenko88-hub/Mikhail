"""Сквозная проверка сценариев бота без сети: настоящий aiogram + поддельный Telegram.

Поддельная сессия отвечает так же, как Bot API (JSON → объекты aiogram), и
записывает все запросы бота — по ним проверяем, что увидят клиент, менеджер и отгрузка.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import re
import time
from datetime import datetime
from typing import Any

import pytest

pytest.importorskip("aiogram")

from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import AnswerCallbackQuery, CopyMessage, EditMessageText, GetMe, SendMessage  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Contact, Message, PhotoSize, Update, User  # noqa: E402
from conftest import SAMPLE_HTML  # noqa: E402

import bot as app  # noqa: E402
from catalog import Catalog, CatalogStore, parse_catalog  # noqa: E402
from config import Config  # noqa: E402
from db import Database  # noqa: E402

BOT_USER = {"id": 42, "is_bot": True, "first_name": "Пространство", "username": "prostranstvo_test_bot"}
CLIENT, CLIENT2, STRANGER = 111, 222, 333
MANAGER, SHIPPER = 900, 901
NAMES = {CLIENT: ("Иван", "Петров", "ivan"), CLIENT2: ("Анна", None, None), STRANGER: ("Кто-то", None, None),
         MANAGER: ("Ольга", None, "olga_mgr"), SHIPPER: ("Сергей", None, "sergey_ship")}
CODE = "246810"
NB = " "


class FakeTelegram(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[Any] = []
        self.blocked: set[int] = set()
        self._ids = itertools.count(1000)

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    def _message(self, chat_id: int, text: str | None, message_id: int | None = None) -> dict:
        data = {"message_id": message_id or next(self._ids), "date": int(time.time()),
                "chat": {"id": chat_id, "type": "private"}, "from": BOT_USER}
        if text is not None:
            data["text"] = text
        return data

    async def make_request(self, bot, method, timeout=None):  # noqa: ANN001
        self.requests.append(method)
        chat_id = getattr(method, "chat_id", None)
        if chat_id in self.blocked:
            body = {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}
            self.check_response(bot, method, 403, json.dumps(body))
        if isinstance(method, GetMe):
            result: Any = BOT_USER
        elif isinstance(method, SendMessage):
            result = self._message(int(method.chat_id), method.text)
        elif isinstance(method, EditMessageText):
            result = self._message(int(method.chat_id or 0), method.text, method.message_id)
        elif isinstance(method, CopyMessage):
            result = {"message_id": next(self._ids)}
        else:
            result = True
        return self.check_response(bot, method, 200, json.dumps({"ok": True, "result": result})).result

    # --- помощники для проверок
    def to(self, chat_id: int) -> list[Any]:
        return [r for r in self.requests if isinstance(r, (SendMessage, EditMessageText))
                and int(r.chat_id or 0) == chat_id]

    def texts(self, chat_id: int) -> list[str]:
        return [r.text for r in self.to(chat_id)]

    def last(self, chat_id: int) -> str:
        texts = self.texts(chat_id)
        return texts[-1] if texts else ""

    def last_req(self, chat_id: int):
        reqs = self.to(chat_id)
        return reqs[-1] if reqs else None

    def find(self, chat_id: int, needle: str):
        for r in reversed(self.to(chat_id)):
            if needle in (r.text or ""):
                return r
        return None

    def count(self, chat_id: int) -> int:
        return len(self.to(chat_id))

    def toasts(self) -> list[str]:
        return [r.text or "" for r in self.requests if isinstance(r, AnswerCallbackQuery)]


def datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


def buttons(markup) -> list[str]:
    return [b.text for row in markup.keyboard for b in row]


class Harness:
    def __init__(self, tmp_path, site_url: str = "") -> None:
        self.cfg = Config(bot_token="42:TEST", site_url=site_url, owner_code=CODE, consent_version="1",
                          db_path=str(tmp_path / "bot.db"), catalog_file="", catalog_url="", catalog_cache="")
        self.db = Database(self.cfg.db_path)
        self.store = CatalogStore("", "", "", 60)
        self.store.set(Catalog(parse_catalog(SAMPLE_HTML), source="тест"))
        self.team = app.Team(self.cfg.admin_ids)
        self.s = FakeTelegram()
        self.bot = app.make_bot(self.cfg.bot_token, session=self.s)
        self.dp = app.build_dispatcher(self.cfg, self.db, self.store, self.team)
        self._upd = itertools.count(1)
        self._msg = itertools.count(1)

    @staticmethod
    def user(uid: int) -> User:
        first, last, username = NAMES[uid]
        return User(id=uid, is_bot=False, first_name=first, last_name=last, username=username)

    async def send(self, uid: int, text: str | None = None, **extra: Any) -> None:
        msg = Message(message_id=next(self._msg), date=datetime.now(), chat=Chat(id=uid, type="private"),
                      from_user=self.user(uid), text=text, **extra)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._upd), message=msg))

    async def press(self, uid: int, data: str, message_id: int | None = None, text: str = "…") -> None:
        msg = Message(message_id=message_id or next(self._msg), date=datetime.now(),
                      chat=Chat(id=uid, type="private"), from_user=User(**BOT_USER), text=text)
        cq = CallbackQuery(id=str(next(self._upd)), from_user=self.user(uid), chat_instance="x",
                           data=data, message=msg)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._upd), callback_query=cq))

    async def reply(self, uid: int, to_message_id: int, text: str) -> None:
        original = Message(message_id=to_message_id, date=datetime.now(), chat=Chat(id=uid, type="private"),
                           from_user=User(**BOT_USER), text="…")
        await self.send(uid, text, reply_to_message=original)

    async def relay_ids(self, chat_id: int, client: int) -> list[int]:
        """message_id сообщений в чате сотрудника, ответ на которые уйдёт этому клиенту."""
        ids = []
        for mid in range(1000, 1000 + len(self.s.requests) + 50):
            if await self.db.relay_target(chat_id, mid) == client:
                ids.append(mid)
        return ids

    async def close(self) -> None:
        self.db.close()
        await self.bot.session.close()


def run(coro):
    return asyncio.run(coro)


async def _make_team(h: Harness) -> None:
    """Менеджер — по коду установщика, отгрузка — по приглашению менеджера."""
    s = h.s
    await h.send(MANAGER, "/owner 000000")
    assert "неверный" in s.last(MANAGER)
    await h.send(MANAGER, f"/owner {CODE}")
    assert "вы менеджер" in s.last(MANAGER)
    menu = buttons(s.last_req(MANAGER).reply_markup)
    assert menu == ["Заявки", "Отгрузки", "Рассчитать стену", "Каталог и цены", "Команда", "Статистика",
                    "Уведомления", "Помощь"]
    await h.send(STRANGER, f"/owner {CODE}")
    assert "неверный, уже использован" in s.last(STRANGER)

    await h.send(MANAGER, "Команда")
    assert "Ольга" in s.last(MANAGER) and "менеджер" in s.last(MANAGER)
    assert {"inv|manager", "inv|shipping"} <= set(datas(s.last_req(MANAGER).reply_markup))
    await h.press(MANAGER, "inv|shipping")
    invite = s.last(MANAGER)
    assert "отгрузка" in invite and "@prostranstvo_test_bot" in invite and "24 часа" in invite
    code = re.search(r"/join (\d{6})", invite).group(1)
    await h.send(MANAGER, f"/join {code}")  # единственный менеджер не «понижает» сам себя
    assert "единственный менеджер" in s.last(MANAGER) and h.team.is_manager(MANAGER)

    await h.send(SHIPPER, "/join 999999")
    assert "неверный" in s.last(SHIPPER)
    await h.send(SHIPPER, f"/join {code}")
    assert "роль «отгрузка»" in s.last(SHIPPER)
    assert buttons(s.last_req(SHIPPER).reply_markup) == [
        "Заявки", "Отгрузки", "Рассчитать стену", "Каталог и цены", "Уведомления", "Помощь"]
    assert "Сергей теперь в команде: отгрузка" in s.last(MANAGER)
    await h.send(STRANGER, f"/join {code}")  # код одноразовый
    assert "неверный" in s.last(STRANGER)
    await h.send(SHIPPER, "/team")
    assert "только менеджер" in s.last(SHIPPER)
    assert h.team.managers() == [MANAGER] and h.team.shipping() == [SHIPPER]


def test_team_leads_and_shipping(tmp_path):
    async def scenario():
        h = Harness(tmp_path)
        s = h.s
        await h.send(CLIENT, "/start")
        assert "Здравствуйте" in s.last(CLIENT) and "Санкт-Петербурге" in s.last(CLIENT)
        assert buttons(s.last_req(CLIENT).reply_markup) == [
            "Рассчитать стену", "Каталог и цены", "Оставить заявку", "Связаться с менеджером"]
        assert "Сайт:" not in s.last(CLIENT)  # SITE_URL пуст — ссылок нет

        await _make_team(h)

        # --- клиент: расчёт A907 на стену 3 × 2,7 м
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
        assert f"1{NB}коробка по 12{NB}шт + 7{NB}шт" in res and f"18{NB}050{NB}₽" in res
        assert "предварительные" in res
        assert datas(s.last_req(CLIENT).reply_markup) == ["ls|A907|3000|2700", "cn"]
        await h.press(CLIENT, "ca|A907")
        await h.send(CLIENT, "3 x 2,7")  # сразу ширина × высота
        assert f"Итого: 19{NB}шт" in s.last(CLIENT)

        # --- «Отправить расчёт менеджеру» → заявка
        await h.press(CLIENT, "ls|A907|3000|2700")
        assert "Отправим расчёт менеджеру" in s.last(CLIENT)
        await h.send(CLIENT, "Иван")
        assert s.last_req(CLIENT).reply_markup.keyboard[0][0].request_contact is True
        await h.send(CLIENT, "привет")
        assert "Не похоже на телефон" in s.last(CLIENT)
        await h.send(CLIENT, None, contact=Contact(phone_number="79991234567", first_name="Иван", user_id=CLIENT))
        await h.send(CLIENT, "Пропустить")
        review, consent = s.texts(CLIENT)[-2:]
        assert "Проверьте заявку" in review and "+79991234567" in review and "A907" in review
        assert "152-ФЗ" in consent  # без сайта — короткий текст согласия прямо в сообщении
        assert (await h.db.stats()).leads_total == 0  # до «Согласен» ничего не сохранено
        await h.press(CLIENT, "lead|yes")
        assert "Заявка №1 принята" in s.last(CLIENT) and "рабочее время" in s.last(CLIENT)
        await h.press(CLIENT, "lead|yes")  # повторное нажатие не создаёт вторую заявку
        assert (await h.db.stats()).leads_total == 1

        card_j = s.find(MANAGER, "Новая заявка №1")
        card_m = s.find(SHIPPER, "Новая заявка №1")
        assert card_j and card_m  # копия заявки — и менеджеру, и отгрузке
        assert "+79991234567" in card_j.text and "@ivan" in card_j.text and "A907" in card_j.text
        assert datas(card_j.reply_markup) == ["shp|1", f"hist|{CLIENT}"]
        assert datas(card_m.reply_markup) == [f"hist|{CLIENT}"]  # у отгрузки нет «Передать на отгрузку»

        # --- сообщения клиента: менеджеру — все, отгрузке — только если включила
        n_misha = s.count(SHIPPER)
        await h.send(CLIENT, "Есть ли A907 в наличии?")
        assert "передано менеджеру" in s.last(CLIENT)
        fwd = s.find(MANAGER, "Есть ли A907 в наличии?")
        assert fwd and "Сообщение от клиента" in fwd.text and "Иван Петров" in fwd.text and "@ivan" in fwd.text
        assert s.count(SHIPPER) == n_misha
        await h.send(SHIPPER, "Уведомления")
        assert "только заявки и отгрузки" in s.last(SHIPPER)
        await h.press(SHIPPER, "ntf|all")
        assert "все сообщения клиентов" in s.last(SHIPPER)
        await h.send(CLIENT, "А доставка есть?")
        assert s.find(SHIPPER, "А доставка есть?")
        await h.send(SHIPPER, "/notify orders")
        assert "только заявки и отгрузки" in s.last(SHIPPER)
        n_misha = s.count(SHIPPER)
        await h.send(CLIENT, "Третий вопрос")
        assert s.count(SHIPPER) == n_misha

        # --- ответ менеджера свайпом (reply) → клиенту
        rid = (await h.relay_ids(MANAGER, CLIENT))[-1]
        await h.reply(MANAGER, rid, "Да, есть, 12 коробок")
        assert "Ответ менеджера" in s.last(CLIENT) and "12 коробок" in s.last(CLIENT)
        assert "Отправлено клиенту" in s.last(MANAGER)

        # --- переписка у отгрузки и ответ из неё
        await h.send(SHIPPER, "/history #1")
        hist = s.last(SHIPPER)
        assert "Переписка: Иван Петров" in hist and "Есть ли A907" in hist and "Магазин (Ольга)" in hist
        assert "№1 (новая)" in hist
        hid = (await h.relay_ids(SHIPPER, CLIENT))[-1]
        await h.reply(SHIPPER, hid, "Отгрузим завтра")
        assert "Отгрузим завтра" in s.last(CLIENT)
        await h.press(SHIPPER, f"hist|{CLIENT}")
        assert "Магазин (Сергей)" in s.last(SHIPPER)

        # --- «Передать на отгрузку»
        await h.press(MANAGER, "shp|1")
        assert "Отгрузка по заявке №1" in s.last(MANAGER) and "A907" in s.last(MANAGER)
        assert buttons(s.last_req(MANAGER).reply_markup) == ["Как в заявке", "Отмена"]
        await h.send(MANAGER, "Как в заявке")
        assert "Адрес доставки" in s.last(MANAGER)
        await h.send(MANAGER, "Самовывоз")
        assert "Когда отгрузить" in s.last(MANAGER)
        await h.send(MANAGER, "Завтра")
        assert "+79991234567" in s.last(MANAGER)
        await h.send(MANAGER, "Как в заявке")
        review = s.last_req(MANAGER)
        assert "Проверьте отгрузку" in review.text and "Самовывоз" in review.text and "завтра" in review.text
        assert datas(review.reply_markup) == ["shc|yes", "shc|no"]
        await h.press(MANAGER, "shc|yes")
        assert (await h.db.get_lead(1)).status == "confirmed"
        ship_m = s.find(SHIPPER, "На отгрузку №1")
        assert ship_m and "Самовывоз" in ship_m.text and "+79991234567" in ship_m.text
        assert "подтверждена" in ship_m.text
        assert datas(ship_m.reply_markup) == ["sh|acc|1", "sh|done|1", f"hist|{CLIENT}"]
        ship_j = s.find(MANAGER, "На отгрузку №1")
        assert "sh|cancel|1" in datas(ship_j.reply_markup)
        assert "Карточку получили: Сергей" in s.last(MANAGER)

        await h.send(SHIPPER, "Отгрузки")
        assert "Открытые отгрузки: 1" in s.find(SHIPPER, "Открытые отгрузки").text
        await h.press(SHIPPER, "sh|cancel|1")
        assert "только менеджер" in s.toasts()[-1]
        await h.press(SHIPPER, "sh|acc|1")
        assert s.toasts()[-1] == "Готово"
        assert (await h.db.get_lead(1)).status == "shipping"
        assert "принял(а) Сергей — статус «на отгрузке»" in s.last(MANAGER)
        edited = s.last_req(SHIPPER)
        assert isinstance(edited, EditMessageText) and datas(edited.reply_markup) == ["sh|done|1", f"hist|{CLIENT}"]
        await h.press(SHIPPER, "sh|acc|1")
        assert s.toasts()[-1] == "Уже отмечено"
        await h.press(SHIPPER, "sh|done|1")
        assert (await h.db.get_lead(1)).status == "shipped"
        assert "Отгрузка №1 (Иван): отгружено (Сергей)" in s.last(MANAGER)
        await h.send(SHIPPER, "/orders")
        assert "Открытых отгрузок нет" in s.last(SHIPPER)

        # --- вторая заявка: всё вводим руками, потом менеджер отменяет отгрузку
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
        assert "Напишите номер" in s.last(MANAGER)  # в заявке нет телефона
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

        # --- заявки и статистика
        await h.send(MANAGER, "Заявки")
        lst = s.last_req(MANAGER)
        assert "№1" in lst.text and "отгружено" in lst.text and "№2" in lst.text
        assert datas(lst.reply_markup) == ["ld|2", "ld|1"]
        await h.press(MANAGER, "ld|1")
        assert "Заявка №1" in s.last(MANAGER) and "Статус: отгружено" in s.last(MANAGER)
        await h.send(MANAGER, "Статистика")
        st = s.last(MANAGER)
        assert "Заявки: сегодня 2" in st and "отгружено за 7 дней 1" in st and "Каталог: 9 позиций" in st
        await h.send(SHIPPER, "/stats")
        assert "только менеджер" in s.last(SHIPPER)

        # /reply по номеру заявки, заблокировавший клиент
        await h.send(MANAGER, "/reply 1 Спасибо за покупку!")
        assert "Спасибо за покупку!" in s.last(CLIENT)
        s.blocked.add(CLIENT2)
        await h.send(MANAGER, "/reply #2 алло")
        assert "Не удалось отправить" in s.last(MANAGER)
        s.blocked.clear()
        await h.send(MANAGER, "/reply #77 нет такой")
        assert "нет" in s.last(MANAGER).lower()

        # сотрудник пишет не ответом — никуда не уходит
        n_client = s.count(CLIENT)
        await h.send(MANAGER, "просто текст")
        assert "никуда не отправлено" in s.last(MANAGER) and s.count(CLIENT) == n_client
        await h.reply(MANAGER, 1, "ответ не туда")
        assert "Не понял, кому ответить" in s.last(MANAGER)

        # клиенту служебные команды недоступны, старые кнопки — «устарела»
        await h.send(CLIENT2, "/leads")
        assert "Последние заявки" not in s.last(CLIENT2)
        await h.press(STRANGER, "sh|done|1")
        assert "больше не действует" in s.toasts()[-1]

        # --- убрать человека из команды
        await h.send(MANAGER, "/remove 900")
        assert "последнего менеджера" in s.last(MANAGER)
        await h.send(MANAGER, "Команда")
        assert f"rm|{SHIPPER}" in datas(s.last_req(MANAGER).reply_markup)
        await h.press(MANAGER, f"rm|{SHIPPER}")
        assert datas(s.last_req(MANAGER).reply_markup) == [f"rmy|{SHIPPER}", "rmn"]
        await h.press(MANAGER, f"rmy|{SHIPPER}")
        assert "больше не в команде" in s.last(MANAGER)
        assert "Вас убрали из команды" in s.last(SHIPPER)
        assert not h.team.is_member(SHIPPER)

        # --- отзыв согласия: отгруженный заказ остаётся, остальное удаляется
        await h.send(CLIENT, "/delete_me")
        assert datas(s.last_req(CLIENT).reply_markup) == ["del|yes", "del|no"]
        await h.press(CLIENT, "del|yes")
        assert "удалены" in s.last(CLIENT) and "требует закон" in s.last(CLIENT)
        assert "попросил(а) удалить свои данные" in s.last(MANAGER)
        assert await h.db.get_lead(1) is not None
        assert await h.db.history(CLIENT) == []
        await h.close()

    run(scenario())


def test_catalog_photo_and_linear(tmp_path):
    async def scenario():
        h = Harness(tmp_path)
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
        assert "kg|plinth" in datas(s.last_req(CLIENT2).reply_markup)
        await h.press(CLIENT2, "kg|plinth")
        cat = s.last(CLIENT2)
        assert "A703" in cat and f"290{NB}₽/шт" in cat and f"коробка 28{NB}шт = 8{NB}120{NB}₽" in cat
        assert "cgn|plinth" in datas(s.last_req(CLIENT2).reply_markup)

        # фото от клиента → менеджеру шапка + копия; второе сообщение подряд — без «передано»
        await h.send(CLIENT2, None, photo=[PhotoSize(file_id="f1", file_unique_id="u1", width=10, height=10)],
                     caption="моя стена")
        assert any(isinstance(r, CopyMessage) and int(r.chat_id) == MANAGER for r in s.requests)
        assert "(фото)" in s.find(MANAGER, "Сообщение от клиента").text
        n = s.count(CLIENT2)
        await h.send(CLIENT2, "ещё вопрос")
        assert s.count(CLIENT2) == n
        await h.close()

    run(scenario())


def test_site_links_and_consent(tmp_path):
    async def scenario():
        h = Harness(tmp_path, site_url="https://example.ru")
        s = h.s
        await h.send(CLIENT, "/start")
        assert "Сайт: https://example.ru" in s.last(CLIENT)
        await h.send(CLIENT, "Оставить заявку")
        await h.send(CLIENT, "Иван")
        await h.send(CLIENT, "8 (999) 123-45-67")
        await h.send(CLIENT, "Нужен расчёт на две стены")
        consent = s.last(CLIENT)
        assert 'href="https://example.ru/consent.html"' in consent
        assert 'href="https://example.ru/privacy.html"' in consent
        await h.press(CLIENT, "lead|yes")
        lead = await h.db.get_lead(1)
        assert lead.contact == "+79991234567" and lead.comment == "Нужен расчёт на две стены"
        await h.press(CLIENT, "kg|panel")
        assert "example.ru" in s.last(CLIENT)
        await h.close()

    run(scenario())


def test_deep_link_and_code_rate_limit(tmp_path):
    async def scenario():
        h = Harness(tmp_path)
        s = h.s
        await h.send(CLIENT, "/start A907")
        assert "ширину стены" in s.last(CLIENT)
        await h.send(CLIENT, "/start catalog")
        assert "Каталог ARTDEC" in s.last(CLIENT)
        for _ in range(5):
            await h.send(CLIENT2, "/owner 111111")
        await h.send(CLIENT2, f"/owner {CODE}")  # даже верный код — после 5 ошибок блок на час
        assert "Слишком много попыток" in s.last(CLIENT2)
        assert not h.team.is_member(CLIENT2)
        await h.close()

    run(scenario())


def test_static_admin_ids(tmp_path):
    async def scenario():
        h = Harness(tmp_path)
        h.team = app.Team(frozenset({MANAGER}))
        h.dp = app.build_dispatcher(h.cfg, h.db, h.store, h.team)
        await h.team.refresh(h.db)
        assert h.team.is_manager(MANAGER)
        await h.send(CLIENT, "Привет")
        assert h.s.find(MANAGER, "Привет")
        await h.send(MANAGER, f"/remove {MANAGER}")
        assert "настройках сервера" in h.s.last(MANAGER)
        await h.close()

    run(scenario())


def test_parse_contact_and_phone():
    assert app.parse_contact("+7 999 123-45-67") == "+79991234567"
    assert app.parse_contact("89991234567") == "+79991234567"
    assert app.parse_contact("9991234567") == "+79991234567"
    assert app.parse_contact("@ivan_petrov") == "Telegram @ivan_petrov"
    assert app.parse_contact("ivan@example.ru") == "ivan@example.ru"
    assert app.parse_contact("123") is None
    assert app.parse_contact("позвоните") is None
    assert app.parse_phone("Telegram @ivan") is None
