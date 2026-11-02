import asyncio
import os
import sqlite3
import stat

import pytest

from db import ROLE_LINK, ROLE_MANAGER, ROLE_SHIPPING, Database, SchemaError, code_hash

HERE = os.path.dirname(os.path.abspath(__file__))


def run(coro):
    return asyncio.run(coro)


async def _client(db, channel="tg", user_id=111, name="Иван"):
    return await db.upsert_client(channel, user_id, "ivan", name)


async def _lead(db, client, contact="+79991234567", calc="A907: 19 шт"):
    return await db.add_lead(client=client, name=client.name, contact=contact, comment="Купчино, на следующей неделе",
                             calc=calc, consent_at="2026-11-02T18:00:00+03:00", consent_version="1")


def test_clients_leads_messages_stats_and_delete(tmp_path):
    path = str(tmp_path / "sub" / "bot.db")
    db = Database(path)

    async def scenario():
        await db.init()
        ivan = await _client(db)
        anna_max = await db.upsert_client("max", 111, None, "Анна")  # тот же id, другой мессенджер — другой клиент
        assert ivan.id != anna_max.id and anna_max.channel == "max"
        assert (await db.upsert_client("tg", 111, "ivan2", "Иван П.")).id == ivan.id  # обновление имени
        ivan = await db.get_client(ivan.id)
        assert ivan.username == "ivan2" and ivan.name == "Иван П."

        lead_id = await _lead(db, ivan)
        await db.add_lead(client=anna_max, name="Анна", contact="MAX (ответ через этот чат)", comment=None,
                          calc=None, consent_at="2026-11-02T18:05:00+03:00", consent_version="1")
        await db.add_message(client=ivan, direction="in", kind="text", text="Есть в наличии?")
        await db.add_message(client=ivan, direction="out", kind="text", text="Да", admin_id=1, admin_name="Ольга")
        await db.add_relay("max", 999, "mid.abc", ivan.id, lead_id)

        assert await db.relay_target("max", 999, "mid.abc") == ivan.id
        assert await db.relay_target("tg", 999, "mid.abc") is None
        leads = await db.last_leads(10)
        assert [(lead.id, lead.channel) for lead in leads] == [(2, "max"), (1, "tg")]
        lead = await db.get_lead(lead_id)
        assert lead.client_id == ivan.id and lead.user_id == 111 and lead.status == "new"
        hist = await db.history(ivan.id)
        assert [(h.direction, h.text, h.admin_name) for h in hist] == [("in", "Есть в наличии?", ""),
                                                                      ("out", "Да", "Ольга")]
        s = await db.stats()
        assert (s.leads_today, s.leads_total, s.messages_today, s.clients_week) == (2, 2, 1, 2)

        assert await db.delete_client(ivan.id) == (1, 0, 2)
        assert await db.get_client(ivan.id) is None  # ничего не осталось — клиент удалён целиком
        assert await db.relay_target("max", 999, "mid.abc") is None
        assert (await db.stats()).leads_total == 1

    run(scenario())
    db.close()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode & 0o077 == 0, oct(mode)  # файл базы недоступен другим пользователям


def test_team_persons_invites_and_links(tmp_path):
    db = Database(str(tmp_path / "bot.db"))

    async def scenario():
        assert await db.team() == []
        assert await db.claim_owner_code("123456", "max", 42, "olga", "Ольга") is True
        assert await db.claim_owner_code("123456", "tg", 43, "x", "Другой") is False  # код одноразовый
        seats = await db.team()
        assert [(s.channel, s.user_id, s.role, s.notify) for s in seats] == [("max", 42, ROLE_MANAGER, "all")]
        olga = seats[0].person_id

        # второй мессенджер того же человека
        link = await db.create_invite(ROLE_LINK, olga, person_id=olga)
        assert await db.use_invite(link, "tg", 500, "olga_tg", "Ольга") == (ROLE_MANAGER, True)
        seats = await db.team()
        assert {(s.channel, s.user_id): s.person_id for s in seats} == {("max", 42): olga, ("tg", 500): olga}
        assert await db.use_invite(link, "tg", 501, "y", "Y") is None  # второй раз не работает

        code = await db.create_invite(ROLE_SHIPPING, olga)
        assert await db.use_invite(code, "max", 77, "sergey", "Сергей") == (ROLE_SHIPPING, False)
        by_seat = {(s.channel, s.user_id): s for s in await db.team()}
        sergey = by_seat[("max", 77)].person_id
        assert sergey != olga and by_seat[("max", 77)].notify == "orders"

        assert await db.set_notify(sergey, "all") and await db.set_deliver(olga, "tg")
        by_seat = {(s.channel, s.user_id): s for s in await db.team()}
        assert by_seat[("max", 77)].notify == "all" and by_seat[("tg", 500)].deliver == "tg"
        assert by_seat[("max", 42)].deliver == "tg"  # настройка общая для обоих мессенджеров человека

        expired = await db.create_invite(ROLE_MANAGER, olga, ttl_sec=-1)
        assert await db.use_invite(expired, "max", 79, "z", "Z") is None
        with pytest.raises(ValueError):
            await db.create_invite(ROLE_LINK, olga)  # код-связка без человека не бывает

        assert await db.remove_person(sergey) is True
        assert await db.remove_person(sergey) is False
        await db.ensure_member("tg", 600)          # из ADMIN_IDS
        await db.ensure_member("max", 42)          # уже есть — не трогаем
        by_seat = {(s.channel, s.user_id): s for s in await db.team()}
        assert by_seat[("tg", 600)].role == ROLE_MANAGER and by_seat[("max", 42)].name == "Ольга"

    run(scenario())
    db.close()


def test_shipment_statuses_and_delete_keeps_orders(tmp_path):
    db = Database(str(tmp_path / "bot.db"))

    async def scenario():
        ivan = await _client(db, "max", 111)
        lead_id = await _lead(db, ivan)
        assert (await db.change_shipment(lead_id, "accept", 2, "Сергей"))[0] == "missing"
        ship = await db.save_shipment(lead_id, items="A907 19 шт", address="Самовывоз", when_text="завтра",
                                      phone="+79991234567", by_id=1, by_name="Ольга")
        assert ship.status == "confirmed" and ship.client_name == "Иван" and ship.client_id == ivan.id
        assert ship.client_channel == "max"
        assert [s.lead_id for s in await db.open_shipments()] == [lead_id]
        result, ship = await db.change_shipment(lead_id, "accept", 2, "Сергей")
        assert result == "ok" and ship.status == "shipping" and ship.accepted_name == "Сергей"
        assert (await db.change_shipment(lead_id, "accept", 2, "Сергей"))[0] == "already"
        result, ship = await db.change_shipment(lead_id, "done", 2, "Сергей")
        assert result == "ok" and ship.status == "shipped"
        assert (await db.change_shipment(lead_id, "cancel", 1, "Ольга"))[0] == "shipped"

        anna = await _client(db, "tg", 222, "Анна")
        lead2 = await _lead(db, anna)
        await db.save_shipment(lead2, items="x", address="ул. Примерная", when_text="05.11", phone="+79990000000",
                               by_id=1, by_name="Ольга")
        result, ship = await db.change_shipment(lead2, "cancel", 1, "Ольга")
        assert result == "ok" and ship.cancelled_ts and ship.status == "new"
        assert (await db.change_shipment(lead2, "accept", 2, "Сергей"))[0] == "cancelled"
        result, ship = await db.change_shipment(lead2, "done", 2, "Сергей")
        assert result == "cancelled"

        # отзыв согласия: отгруженный заказ остаётся (договор), переписка и прочие заявки — удаляются
        await db.add_message(client=ivan, direction="in", kind="text", text="?")
        lead3 = await _lead(db, ivan)
        assert await db.delete_client(ivan.id) == (1, 1, 1)
        assert await db.get_lead(lead_id) is not None and await db.get_lead(lead3) is None
        assert await db.get_client(ivan.id) is not None  # нужен для заказа

    run(scenario())
    db.close()


def test_outbox(tmp_path):
    db = Database(str(tmp_path / "bot.db"))

    async def scenario():
        a = await db.enqueue("tg", 10, {"t": "text", "text": "привет"})
        b = await db.enqueue("max", 20, {"t": "lead", "lead_id": 1}, client_id=5)
        assert [(i.id, i.chat_id, i.item) for i in await db.outbox_pending("tg")] == [(a, 10, {"t": "text",
                                                                                              "text": "привет"})]
        await db.outbox_retry(a, 60, "нет связи")
        assert await db.outbox_pending("tg") == []          # повтор позже
        assert await db.outbox_count("tg") == 1
        await db.outbox_done(b)
        assert await db.outbox_pending("max") == [] and await db.outbox_count("max") == 0
        assert await db.get_setting("x") == ""
        await db.set_setting("x", "1")
        assert await db.get_setting("x") == "1"

    run(scenario())
    db.close()


def _make_v1(path: str) -> None:
    """База версии 1 (только Telegram) с данными — как у бота первого выпуска."""
    con = sqlite3.connect(path)
    with open(os.path.join(HERE, "schema_v1.sql"), encoding="utf-8") as fh:
        con.executescript(fh.read())
    con.execute("INSERT INTO settings VALUES ('schema_version', '1')")
    con.execute("INSERT INTO settings VALUES (?, '2026-11-02')", ("owner_code_used:" + code_hash("123456"),))
    con.execute("INSERT INTO leads(created_ts, created_at, tg_id, username, name, contact, comment, calc, consent_at,"
                " consent_version, status, status_ts) VALUES (1000, 'x', 111, 'ivan', 'Иван', '+79991234567', 'к',"
                " 'A907', 'x', '1', 'confirmed', 1000)")
    con.execute("INSERT INTO leads(created_ts, created_at, tg_id, username, name, contact, comment, calc, consent_at,"
                " consent_version) VALUES (1001, 'x', 222, '', 'Анна', 'Telegram', '', '', 'x', '1')")
    con.execute("INSERT INTO shipments(lead_id, items, address, when_text, phone, created_by, created_name,"
                " created_ts) VALUES (1, 'A907', 'Самовывоз', 'завтра', '+79991234567', 900, 'Ольга', 1002)")
    con.execute("INSERT INTO messages(created_ts, created_at, tg_id, username, name, direction, kind, text)"
                " VALUES (1003, 'x', 111, 'ivan', 'Иван Петров', 'in', 'text', 'Есть в наличии?')")
    con.execute("INSERT INTO messages(created_ts, created_at, tg_id, username, name, direction, kind, text,"
                " admin_id, admin_name) VALUES (1004, 'x', 111, 'ivan', 'Иван Петров', 'out', 'text', 'Да', 900,"
                " 'Ольга')")
    con.execute("INSERT INTO relay VALUES (900, 5001, 111, 1, 1005)")
    con.execute("INSERT INTO team VALUES (900, 'olga', 'Ольга', 'manager', 'all', '2026-11-01', NULL)")
    con.execute("INSERT INTO team VALUES (901, 'sergey', 'Сергей', 'shipping', 'orders', '2026-11-02', 900)")
    con.execute("INSERT INTO invites(code_hash, role, created_ts, expires_ts, created_by) VALUES ('h', 'shipping',"
                " 1, 2, 900)")
    con.commit()
    con.close()


def test_migration_from_v1_keeps_everything(tmp_path):
    path = str(tmp_path / "bot.db")
    _make_v1(path)
    os.chmod(path, 0o644)
    db = Database(path)

    async def scenario():
        await db.init()
        assert await db.get_setting("schema_version") == "2"
        assert await db.owner_code_used("123456")
        lead = await db.get_lead(1)
        assert (lead.channel, lead.user_id, lead.name, lead.status) == ("tg", 111, "Иван", "confirmed")
        client = await db.get_client(lead.client_id)
        assert (client.channel, client.user_id, client.name, client.username) == ("tg", 111, "Иван Петров", "ivan")
        anna = await db.get_client((await db.get_lead(2)).client_id)
        assert (anna.user_id, anna.name) == (222, "Анна")
        hist = await db.history(client.id)
        assert [(h.direction, h.text) for h in hist] == [("in", "Есть в наличии?"), ("out", "Да")]
        ship = await db.get_shipment(1)
        assert ship.client_id == client.id and ship.client_channel == "tg" and ship.address == "Самовывоз"
        assert await db.relay_target("tg", 900, "5001") == client.id
        seats = {(s.channel, s.user_id): s for s in await db.team()}
        assert seats[("tg", 900)].role == "manager" and seats[("tg", 901)].role == "shipping"
        assert seats[("tg", 901)].notify == "orders" and seats[("tg", 900)].person_id != seats[("tg", 901)].person_id
        # после миграции всё работает как обычно
        new = await db.upsert_client("max", 111, "", "Иван в MAX")
        assert new.id not in (client.id, anna.id)
        await db.add_message(client=client, direction="in", kind="text", text="ещё вопрос")
        assert len(await db.history(client.id)) == 3

    run(scenario())
    db.close()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600  # права исправлены при открытии
    # повторное открытие — без повторной миграции
    db2 = Database(path)
    assert run(db2.get_setting("schema_version")) == "2"
    assert len(run(db2.team())) == 2
    db2.close()


def test_newer_schema_is_refused(tmp_path):
    path = str(tmp_path / "bot.db")
    db = Database(path)
    run(db.init())
    run(db.set_setting("schema_version", "9"))
    db.close()
    with pytest.raises(SchemaError):
        run(Database(path).init())


def test_two_processes_share_file(tmp_path):
    """Telegram и MAX — разные процессы с одним файлом: оба видят изменения друг друга."""
    path = str(tmp_path / "bot.db")
    a, b = Database(path), Database(path)

    async def scenario():
        await a.init()
        await b.init()
        client = await a.upsert_client("max", 1, "", "Клиент")
        await b.enqueue("max", 5, {"t": "text", "text": "из Telegram"}, client.id)
        assert [i.item["text"] for i in await a.outbox_pending("max")] == ["из Telegram"]

    run(scenario())
    a.close()
    b.close()
