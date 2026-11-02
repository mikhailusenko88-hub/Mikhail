import asyncio
import os
import stat
import time

from db import ROLE_MANAGER, ROLE_SHIPPING, Database


def run(coro):
    return asyncio.run(coro)


async def _lead(db, tg_id=111, name="Иван", contact="+79991234567", calc="A907: 19 шт"):
    return await db.add_lead(tg_id=tg_id, username="ivan", name=name, contact=contact,
                             comment="Купчино, на следующей неделе", calc=calc,
                             consent_at="2026-11-02T18:00:00+03:00", consent_version="1")


def test_leads_messages_stats_and_delete(tmp_path):
    path = str(tmp_path / "sub" / "bot.db")
    db = Database(path)

    async def scenario():
        await db.init()
        lead_id = await _lead(db)
        await db.add_lead(tg_id=222, username=None, name="Анна", contact="Telegram (ответ через этот чат)",
                          comment=None, calc=None, consent_at="2026-11-02T18:05:00+03:00", consent_version="1")
        await db.add_message(tg_id=111, username="ivan", name="Иван И.", direction="in", kind="text",
                             text="Есть в наличии?")
        await db.add_message(tg_id=111, username="ivan", name="Иван И.", direction="out", kind="text",
                             text="Да", admin_id=999, admin_name="Ольга")
        await db.add_relay(999, 5001, 111, lead_id)

        assert await db.relay_target(999, 5001) == 111
        assert await db.relay_target(999, 5002) is None
        assert await db.client_name(111) == ("Иван И.", "ivan")

        leads = await db.last_leads(10)
        assert [lead.id for lead in leads] == [2, 1]
        assert leads[0].username == "" and leads[0].comment == ""
        lead = await db.get_lead(lead_id)
        assert lead.contact == "+79991234567" and lead.consent_version == "1" and lead.status == "new"

        hist = await db.history(111)
        assert [(h.direction, h.text, h.admin_name) for h in hist] == [("in", "Есть в наличии?", ""),
                                                                      ("out", "Да", "Ольга")]

        s = await db.stats()
        assert (s.leads_today, s.leads_week, s.leads_total) == (2, 2, 2)
        assert (s.messages_today, s.messages_week) == (1, 1)  # считаем только входящие
        assert s.clients_week == 2 and s.shipments_open == 0

        assert await db.delete_client(111) == (1, 0, 2)
        assert await db.relay_target(999, 5001) is None
        assert await db.is_known_client(111) is False
        assert await db.is_known_client(222) is True
        assert (await db.stats()).leads_total == 1

    run(scenario())
    db.close()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode & 0o077 == 0, oct(mode)  # файл базы недоступен другим пользователям


def test_owner_code_and_invites(tmp_path):
    db = Database(str(tmp_path / "bot.db"))

    async def scenario():
        assert await db.team() == []
        assert await db.claim_owner_code("123456", 42, "olga_mgr", "Ольга") is True
        assert await db.claim_owner_code("123456", 43, "other", "Другой") is False  # код одноразовый
        assert await db.owner_code_used("123456") is True
        team = await db.team()
        assert [(m.tg_id, m.role, m.notify) for m in team] == [(42, ROLE_MANAGER, "all")]

        code = await db.create_invite(ROLE_SHIPPING, 42)
        assert len(code) == 6 and code.isdigit()
        assert await db.use_invite("000000", 77, "x", "X") is None
        assert await db.use_invite(code, 77, "sergey_ship", "Сергей") == ROLE_SHIPPING
        assert await db.use_invite(code, 78, "y", "Y") is None  # второй раз не работает
        members = {m.tg_id: m for m in await db.team()}
        assert members[77].role == ROLE_SHIPPING and members[77].notify == "orders"

        assert await db.set_notify(77, "all") is True
        assert {m.tg_id: m.notify for m in await db.team()}[77] == "all"

        expired = await db.create_invite(ROLE_MANAGER, 42, ttl_sec=-1)
        assert await db.use_invite(expired, 79, "z", "Z") is None  # истёк

        assert await db.remove_member(77) is True
        assert await db.remove_member(77) is False
        await db.ensure_member(500)          # из ADMIN_IDS
        await db.ensure_member(42)           # уже есть — не трогаем
        members = {m.tg_id: m for m in await db.team()}
        assert members[500].role == ROLE_MANAGER and members[42].name == "Ольга"

    run(scenario())
    db.close()


def test_shipment_statuses(tmp_path):
    db = Database(str(tmp_path / "bot.db"))

    async def scenario():
        lead_id = await _lead(db)
        assert (await db.change_shipment(lead_id, "accept", 77, "Сергей"))[0] == "missing"
        ship = await db.save_shipment(lead_id, items="A907 19 шт", address="Самовывоз", when_text="завтра",
                                      phone="+79991234567", by_id=42, by_name="Ольга")
        assert ship.status == "confirmed" and ship.client_name == "Иван" and ship.client_tg_id == 111
        assert (await db.get_lead(lead_id)).status == "confirmed"
        assert [s.lead_id for s in await db.open_shipments()] == [lead_id]

        result, ship = await db.change_shipment(lead_id, "accept", 77, "Сергей")
        assert result == "ok" and ship.status == "shipping" and ship.accepted_name == "Сергей"
        assert (await db.change_shipment(lead_id, "accept", 77, "Сергей"))[0] == "already"
        result, ship = await db.change_shipment(lead_id, "done", 77, "Сергей")
        assert result == "ok" and ship.status == "shipped" and ship.shipped_ts
        assert (await db.change_shipment(lead_id, "done", 77, "Сергей"))[0] == "already"
        assert (await db.change_shipment(lead_id, "cancel", 42, "Ольга"))[0] == "shipped"
        assert await db.open_shipments() == []
        s = await db.stats()
        assert s.shipped_week == 1 and s.shipments_open == 0

        # отмена и повторная передача
        lead2 = await _lead(db, tg_id=222, name="Анна")
        await db.save_shipment(lead2, items="x", address="ул. Примерная", when_text="05.11",
                               phone="+79990000000", by_id=42, by_name="Ольга")
        result, ship = await db.change_shipment(lead2, "cancel", 42, "Ольга")
        assert result == "ok" and ship.cancelled_ts and ship.status == "new"
        assert (await db.change_shipment(lead2, "accept", 77, "Сергей"))[0] == "cancelled"
        ship = await db.save_shipment(lead2, items="y", address="ул. Примерная", when_text="06.11",
                                      phone="+79990000000", by_id=42, by_name="Ольга")
        assert ship.status == "confirmed" and not ship.cancelled_ts and not ship.accepted_ts
        # «Отгружено» без «Принял» — тоже можно
        result, ship = await db.change_shipment(lead2, "done", 77, "Сергей")
        assert result == "ok" and ship.accepted_name == "Сергей" and ship.status == "shipped"

        # отзыв согласия: отгруженные заказы остаются (договор), переписка удаляется
        await db.add_message(tg_id=111, username="ivan", name="Иван", direction="in", kind="text", text="?")
        lead3 = await _lead(db, tg_id=111)
        assert await db.delete_client(111) == (1, 1, 1)
        assert await db.get_lead(lead_id) is not None and await db.get_lead(lead3) is None

    run(scenario())
    db.close()


def test_reopen_keeps_data(tmp_path):
    path = str(tmp_path / "bot.db")
    db = Database(path)
    run(db.add_member(7, "a", "A", ROLE_SHIPPING))
    db.close()
    db2 = Database(path)
    assert [(m.tg_id, m.role) for m in run(db2.team())] == [(7, ROLE_SHIPPING)]
    db2.close()
    assert time.time() > 0
