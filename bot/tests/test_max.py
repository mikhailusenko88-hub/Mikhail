"""Сквозные сценарии в MAX: ядро + наш MaxClient + поддельный сервер Bot API на 127.0.0.1."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import ssl

from fakes import MAX_TOKEN, NB, FakeMax, MaxHarness, kb_rows, labels, make_cfg, make_store, payloads

import max_api
from config import DEFAULT_MAX_CA_FILE
from db import Database

CLIENT, CLIENT2, MANAGER, SHIPPER = 111, 222, 900, 901
NAMES = {CLIENT: ("Иван", "Петров", "ivan"), CLIENT2: ("Анна", None, None),
         MANAGER: ("Ольга", None, "olga_mgr"), SHIPPER: ("Сергей", None, None)}
CODE = "246810"
VCF = "BEGIN:VCARD\r\nVERSION:3.0\r\nTEL;TYPE=cell:79991234567\r\nFN:Иван Петров\r\nEND:VCARD\r\n"


def run(coro):
    return asyncio.run(coro)


async def make(tmp_path, **kw):
    fake = FakeMax()
    url = await fake.start()
    cfg = make_cfg(tmp_path, bot_token="", max_token=MAX_TOKEN, max_api_url=url, **kw)
    h = MaxHarness(cfg, Database(cfg.db_path), make_store(), fake, url, NAMES)
    return fake, h


async def done(fake: FakeMax, h: MaxHarness) -> None:
    await h.close()
    h.db.close()
    await fake.stop()


def test_full_flow_in_max(tmp_path):
    async def scenario():
        f, h = await make(tmp_path)
        await h.engine.start()
        assert ("PATCH", "/me/commands") in [(m, p) for m, p, q, b in f.requests]

        # старт по кнопке «Начать» (bot_started) — приветствие и меню кнопками под сообщением
        await h.start(CLIENT)
        body = f.last_body(CLIENT)
        assert "Здравствуйте" in body["text"] and body["format"] == "html"
        assert "менеджер свяжется с вами" in body["text"]  # в MAX заявки принимаются
        assert labels(body, "message") == ["Рассчитать стену", "Каталог и цены", "Оставить заявку",
                                           "Связаться с менеджером"]

        # команда магазина — те же коды
        await h.send(MANAGER, f"/owner {CODE}")
        assert "вы менеджер" in f.last(MANAGER)
        assert "нажмите на его сообщение, выберите «Ответить»" in f.last(MANAGER)
        await h.press(MANAGER, "inv|shipping")
        invite = f.last(MANAGER)
        assert "max.ru/id000000000000_bot" in invite
        await h.send(SHIPPER, "/join " + re.search(r"/join (\d{6})", invite).group(1))
        assert "роль «отгрузка»" in f.last(SHIPPER)
        assert "Сергей теперь в команде: отгрузка (MAX)" in f.last(MANAGER)

        # расчёт: кнопка-ответ «Рассчитать стену» приходит обычным сообщением
        await h.send(CLIENT, "Рассчитать стену")
        assert "cg|panel" in payloads(f.last_body(CLIENT))
        await h.press(CLIENT, "cg|panel", mid="mid.groups")
        mid, edit = f.edits()[-1]
        assert mid == "mid.groups" and "A907" in edit["text"] and "ca|A907" in payloads(edit)
        await h.press(CLIENT, "ca|A907")
        await h.send(CLIENT, "3,2 x 2,7")
        res = f.last_body(CLIENT)
        assert f"Итого: 20{NB}шт" in res["text"] and payloads(res) == ["ls|A907|3200|2700", "cn"]  # 18 в ряд + 7 %
        assert f.answers()  # на каждое нажатие — ответ /answers

        # заявка с номером через «Отправить номер» (request_contact → вложение contact с vCard)
        await h.press(CLIENT, "ls|A907|3200|2700")
        await h.send(CLIENT, "Иван")
        rows = kb_rows(f.last_body(CLIENT))
        assert rows[0][0] == {"type": "request_contact", "text": "Отправить номер"}
        assert rows[1][0] == {"type": "message", "text": "Напишите мне в MAX"}
        await h.send(CLIENT, None, attachments=[{"type": "contact", "payload": {
            "vcf_info": VCF, "max_info": {"user_id": CLIENT, "first_name": "Иван", "is_bot": False}}}])
        assert "Комментарий" in f.last(CLIENT)
        await h.send(CLIENT, "Пропустить")
        assert payloads(f.last_body(CLIENT)) == ["lead|yes", "lead|no"]
        await h.press(CLIENT, "lead|yes")
        assert "Заявка №1 принята" in f.last(CLIENT)
        lead = await h.db.get_lead(1)
        assert lead.channel == "max" and lead.contact == "+79991234567" and "A907" in lead.calc
        card = f.find(MANAGER, "Новая заявка №1")
        assert card and "+79991234567" in card["text"] and "Откуда: MAX" in card["text"]
        assert payloads(card) == ["shp|1", "hist|1"]
        assert payloads(f.find(SHIPPER, "Новая заявка №1")) == ["hist|1"]

        # вопрос клиента и ответ менеджера через «Ответить» (link.type = reply)
        await h.send(CLIENT, "Когда можно забрать?")
        fwd_mid = f.mid_of(MANAGER, "Когда можно забрать?")
        assert "Иван Петров · @ivan (клиент К1, MAX)" in f.find(MANAGER, "Когда можно забрать?")["text"]
        await h.reply(MANAGER, fwd_mid, "Завтра с 10:00")
        assert "Ответ менеджера" in f.last(CLIENT) and "Завтра с 10:00" in f.last(CLIENT)
        confirm = f.last_body(MANAGER)
        assert confirm["text"] == "Отправлено клиенту." and confirm["link"]["type"] == "reply"

        # фото от клиента — копия вложения по токену, с подписью
        await h.send(CLIENT, "моя стена", attachments=[{"type": "image", "payload": {
            "photo_id": 1, "token": "tok-photo", "url": "https://example/x.jpg"}}])
        copy = f.last_body(MANAGER)
        assert copy["attachments"] == [{"type": "image", "payload": {"token": "tok-photo"}}]
        assert copy["text"] == "моя стена"
        assert "(фото)" in f.find(MANAGER, "Сообщение от клиента (фото)")["text"]

        # отгрузка: менеджер оформляет, отгрузка жмёт «Принял» и «Отгружено»
        await h.press(MANAGER, "shp|1")
        assert labels(f.last_body(MANAGER), "message") == ["Как в заявке", "Отмена"]
        for answer in ("Как в заявке", "Самовывоз", "Завтра", "Как в заявке"):
            await h.send(MANAGER, answer)
        assert payloads(f.last_body(MANAGER)) == ["shc|yes", "shc|no"]
        await h.press(MANAGER, "shc|yes")
        ship = f.find(SHIPPER, "На отгрузку №1")
        assert ship and "+79991234567" in ship["text"] and payloads(ship) == ["sh|acc|1", "sh|done|1", "hist|1"]
        await h.press(SHIPPER, "sh|acc|1", mid="mid.ship")
        assert f.answers()[-1] == {"notification": "Готово"}
        assert f.edits()[-1][0] == "mid.ship" and payloads(f.edits()[-1][1]) == ["sh|done|1", "hist|1"]
        assert "принял(а) Сергей" in f.last(MANAGER)
        await h.press(SHIPPER, "sh|done|1")
        assert (await h.db.get_lead(1)).status == "shipped"

        # клиент заблокировал бота — менеджер узнаёт
        f.blocked.add(CLIENT)
        await h.reply(MANAGER, fwd_mid, "алло")
        assert "Не удалось отправить" in f.last(MANAGER)
        f.blocked.clear()

        # «Уведомления»: второй мессенджер подключить нельзя, пока нет токена Telegram
        await h.send(MANAGER, "Уведомления")
        assert not [p for p in payloads(f.last_body(MANAGER)) if p.startswith("lnk|")]

        # кнопка «Согласен» убирается: после нажатия сообщение правится с пустыми кнопками
        await h.send(CLIENT2, "Оставить заявку")
        await h.send(CLIENT2, "Анна")
        await h.send(CLIENT2, "Напишите мне в MAX")
        await h.send(CLIENT2, "Пропустить")
        consent_mid = f.mid_of(CLIENT2, "Нажимая «Согласен»")
        await h.press(CLIENT2, "lead|no", mid=consent_mid)
        assert (consent_mid, []) in [(m, b["attachments"]) for m, b in f.edits()]
        assert "не сохранены" in f.last(CLIENT2)

        # deep link со страницы сайта / из Telegram: расчёт сразу
        await h.start(CLIENT2, "ls_41393037_3000_2700")
        assert f"Итого: 19{NB}шт" in f.last(CLIENT2) and payloads(f.last_body(CLIENT2))[0] == "ls|A907|3000|2700"

        # отзыв согласия
        await h.send(CLIENT, "/delete_me")
        await h.press(CLIENT, "del|yes")
        assert "удалены" in f.last(CLIENT)
        assert f.unauthorized == 0
        await done(f, h)

    run(scenario())


def test_polling_marker_and_update_parsing(tmp_path):
    async def scenario():
        f, h = await make(tmp_path)
        await h.engine.start()
        f.updates = [h.message_update(CLIENT, "Привет"),
                     {"update_type": "message_created", "timestamp": 1, "message": {   # свои сообщения бота — мимо
                         "sender": {"user_id": 7000, "first_name": "бот", "is_bot": True},
                         "recipient": {"chat_type": "dialog"}, "body": {"mid": "m", "seq": 1, "text": "x"}}},
                     {"update_type": "message_created", "timestamp": 1, "message": {   # групповой чат — мимо
                         "sender": {"user_id": 5, "first_name": "Гость", "is_bot": False},
                         "recipient": {"chat_id": -1, "chat_type": "chat"},
                         "body": {"mid": "m2", "seq": 1, "text": "всем привет"}}},
                     {"update_type": "dialog_muted", "timestamp": 1}]
        await max_api.poll(h.client, h.engine, h.db, once=True)
        assert "передано менеджеру" in f.last(CLIENT)
        assert f.sent(5) == []
        assert await h.db.get_setting(max_api.MARKER_KEY) == "4"
        q = [q for m, p, q, b in f.requests if p == "/updates"][-1]
        assert q["types"] == "message_created,message_callback,bot_started" and q["limit"] == "100"
        await max_api.poll(h.client, h.engine, h.db, once=True)
        q = [q for m, p, q, b in f.requests if p == "/updates"][-1]
        assert q["marker"] == "4"  # после перезапуска продолжим с того же места
        await done(f, h)

    run(scenario())


def test_wrong_token_and_webhook_cleanup(tmp_path):
    async def scenario():
        f = FakeMax()
        url = await f.start()
        f.subscriptions = [{"url": "https://old.example/hook", "time": 1}]
        client = max_api.MaxClient(MAX_TOKEN, url, "")
        assert (await client.me())["username"] == "id000000000000_bot"
        assert len(await client.subscriptions()) == 1
        await client.unsubscribe("https://old.example/hook")
        assert await client.subscriptions() == []
        bad = max_api.MaxClient("wrong", url, "")
        try:
            await bad.me()
            raise AssertionError("ждали 401")
        except max_api.MaxApiError as exc:
            assert exc.status == 401 and exc.code == "verify.token"
        await client.close()
        await bad.close()
        await f.stop()
        # нет сервера — ошибка сети (её бот переживает с повтором)
        down = max_api.MaxClient(MAX_TOKEN, url, "")
        try:
            await down.me()
            raise AssertionError("ждали ошибку сети")
        except max_api.MaxNetworkError:
            pass
        await down.close()

    run(scenario())


def test_render_and_helpers():
    from core import Btn, Kb, ikb, rkb

    assert max_api.render(None) == []
    kb = ikb([Btn("Да", "x|1"), Btn("Сайт", url="https://e.ru")])
    assert max_api.render(kb)[0]["payload"]["buttons"] == [[{"type": "callback", "text": "Да", "payload": "x|1"},
                                                            {"type": "link", "text": "Сайт", "url": "https://e.ru"}]]
    reply = rkb([Btn("Отправить номер", contact=True)], ["Отмена"])
    assert max_api.render(reply)[0]["payload"]["buttons"] == [[{"type": "request_contact", "text": "Отправить номер"}],
                                                              [{"type": "message", "text": "Отмена"}]]
    assert Kb.from_json(kb.to_json()) == kb
    assert max_api.vcf_phone(VCF) == "79991234567"
    assert max_api.vcf_phone("") == ""
    assert max_api.copy_attachments([{"type": "file", "payload": {"token": "t", "url": "u"}, "filename": "a.pdf"},
                                     {"type": "sticker", "payload": {"code": "s1", "url": "u"}},
                                     {"type": "inline_keyboard", "payload": {"buttons": []}}]) == [
        {"type": "file", "payload": {"token": "t"}}, {"type": "sticker", "payload": {"code": "s1"}}]
    ev = max_api.from_update({"update_type": "bot_started", "timestamp": 1, "chat_id": 1,
                              "user": {"user_id": 5, "first_name": "Ира", "is_bot": False}, "payload": "calc"})
    assert ev.text == "/start calc" and ev.user_id == 5


def test_russian_ca_bundle():
    """Сертификаты Минцифры для platform-api2.max.ru: те самые (сверка отпечатков) и загружаются в SSL."""
    assert os.path.isfile(DEFAULT_MAX_CA_FILE)
    with open(DEFAULT_MAX_CA_FILE, encoding="ascii") as fh:
        pems = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", fh.read(), re.S)
    fingerprints = {hashlib.sha256(ssl.PEM_cert_to_DER_cert(p)).hexdigest().upper() for p in pems}
    assert fingerprints == {
        "D26D2D0231B7C39F92CC738512BA54103519E4405D68B5BD703E9788CA8ECF31",  # Russian Trusted Root CA
        "BBBDE2103E790B999EC62BD03CF625A5A2E7C316E10AFE6A490EEDEAD8B3FD9B",  # Russian Trusted Sub CA
    }
    ctx = max_api.ssl_context(DEFAULT_MAX_CA_FILE)
    names = [dict(x[0] for x in c["subject"]).get("commonName") for c in ctx.get_ca_certs()]
    assert "Russian Trusted Root CA" in names and "Russian Trusted Sub CA" in names
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname  # проверка не отключена
