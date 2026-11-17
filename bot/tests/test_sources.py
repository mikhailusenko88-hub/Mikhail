"""Откуда пришли в бота и метки ссылок на сайт (17.11.2026): статистика без имён и номеров."""
from __future__ import annotations

import asyncio
import sqlite3

import core
import texts
import tg_channel as tc
from config import Config, with_utm
from db import Database


def run(coro):
    return asyncio.run(coro)


def test_split_source():
    assert core.split_source("site") == ("site", "")
    assert core.split_source("site_A907") == ("site", "A907")
    assert core.split_source("site_ls_41393037_3000_2700") == ("site", "ls_41393037_3000_2700")
    assert core.split_source("ch") == ("channel", "")
    assert core.split_source("ch_calc") == ("channel", "calc")
    assert core.split_source("calc") == ("link", "calc")
    assert core.split_source("3-7") == ("link", "3-7")
    assert core.split_source("") == ("direct", "")
    assert core.split_source("  ") == ("direct", "")
    assert core.split_source("catalog") == ("link", "catalog")   # «catalog» не путаем с меткой «ch»


def test_with_utm_and_site_link():
    assert with_utm("https://x.ru/", "tg_bot") == "https://x.ru/?utm_source=tg_bot"
    assert with_utm("https://x.ru/#order", "tg_bot") == "https://x.ru/?utm_source=tg_bot#order"
    assert with_utm("https://x.ru/p/a907/?a=1", "tg_bot") == "https://x.ru/p/a907/?a=1&utm_source=tg_bot"
    assert with_utm("https://x.ru/?utm_source=max", "tg_bot") == "https://x.ru/?utm_source=max"   # чужую метку не трогаем
    assert with_utm("https://x.ru/", "") == "https://x.ru/" and with_utm("", "tg_bot") == ""
    cfg = Config(bot_token="", site_url="https://x.ru")
    assert cfg.site_link("#order") == "https://x.ru/#order"
    assert cfg.site_link("p/a907/", utm="tg_bot") == "https://x.ru/p/a907/?utm_source=tg_bot"
    assert Config(bot_token="", site_url="").site_link("", utm="tg_bot") == ""


def test_channel_buttons_to_bot_have_tag():
    post = {"buttons": [[{"text": "Написать в MAX", "url": tc.MAX_BOT_URL}, {"text": "Сайт", "url": "https://nashdekor.ru/?utm_source=max#calc"}]]}
    assert tc.buttons(post) == [[("Написать в Telegram", "https://t.me/nashdekor_bot?start=ch"),
                                 ("Сайт", "https://nashdekor.ru/?utm_source=tg#calc")]]


def test_starts_first_touch_link_stats_and_delete(tmp_path):
    path = str(tmp_path / "bot.db")
    db = Database(path)

    async def scenario():
        await db.init()
        assert await db.note_start("tg", 501, "site") is True
        assert await db.note_start("tg", 501, "channel") is False        # повторный вход источник не меняет
        assert await db.note_start("max", 501, "channel") is True        # другой мессенджер — другой человек
        assert await db.note_start("tg", 502, "что-то") is True          # неизвестная метка → «сами»
        await db.note_start("tg", 503, "link")
        s = await db.stats()
        assert s.starts_week_by_channel == {"tg": 3, "max": 1}
        assert s.starts_week_by_src == {"site": 1, "channel": 1, "direct": 1, "link": 1}
        assert s.starts_week_active == 0
        anna = await db.upsert_client("tg", 501, "anna", "Анна")          # написала — связали с первым входом
        await db.add_message(client=anna, direction="in", kind="text", text="Здравствуйте")
        s = await db.stats()
        assert s.starts_week_active == 1 and s.clients_week_by_channel == {"tg": 1}
        assert "Новые в боте за 7 дней: 4 (MAX — 1, Telegram — 3)" in texts.stats(s, 9, "CRM", "17.11 19:40", "")
        assert "с сайта — 1, из канала — 1, по ссылке на товар или расчёт — 1, сами — 1" in texts.stats(s, 9, "CRM", "", "")
        assert "Из новых написали или оставили заявку: 1" in texts.stats(s, 9, "CRM", "", "")
        assert "Клиентов за 7 дней: 1 (Telegram — 1)" in texts.stats(s, 9, "CRM", "", "")
        await db.delete_client(anna.id)                                    # отзыв согласия — и метка входа удалена
        assert (await db.stats()).starts_week_by_src.get("site", 0) == 0

    run(scenario())
    db.close()
    c = sqlite3.connect(path)
    blob = " ".join(str(r) for r in c.execute("SELECT * FROM starts").fetchall())
    assert "501" not in blob and "502" not in blob                        # id в мессенджере в таблице не хранится
    c.close()


def test_client_who_wrote_before_start_is_linked(tmp_path):
    db = Database(str(tmp_path / "bot.db"))

    async def scenario():
        await db.init()
        old = await db.upsert_client("max", 777, None, "Олег")             # писал до учёта источников
        await db.note_start("max", 777, "site")
        s = await db.stats()
        assert s.starts_week_active == 1
        assert old.id

    run(scenario())
    db.close()


def test_stats_text_without_starts():
    class S:
        leads_today = leads_week = leads_total = messages_today = messages_week = clients_week = 0
        shipments_open = shipped_week = 0
    t = texts.stats(S(), 0, "нет", "—", "")
    assert "Новые в боте за 7 дней: 0" in t and "Клиентов за 7 дней: 0\n" in t
