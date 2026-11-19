"""Справка для своих (19.11.2026): менеджер или отгрузка пишет артикул или номер — фото, цена, ответ клиенту.

Ядро с простым поддельным мессенджером — без aiogram и сети (работает и локально)."""

from __future__ import annotations

import asyncio
import itertools

from conftest import SAMPLE_HTML

import texts
from catalog import Catalog, CatalogStore, apply_crm, parse_catalog
from config import Config
from core import Engine, Incoming
from db import Database

CLIENT, MANAGER = 111, 900
PHOTOS_HTML = SAMPLE_HTML + '<script>const PHOTO_V = "3"; const PHOTOS = {"A703":["A703.jpg","A703_2.jpg"],' \
                            '"A907":["A907.jpg"],"2-3":["2-3.jpg"]};</script>'


class Fake:
    channel = "max"

    def __init__(self, photo_ok: bool | None = True) -> None:
        self.ids = itertools.count(1)
        self.log: list[tuple] = []
        if photo_ok is None:          # мессенджер без фото — у транспорта нет send_photo
            self.send_photo = None    # type: ignore[assignment]
        self.photo_ok = photo_ok

    async def send(self, uid, text, kb=None, reply_to=""):
        self.log.append(("text", uid, text, kb))
        return str(next(self.ids))

    async def send_photo(self, uid, url, caption, kb=None):
        if not self.photo_ok:
            raise RuntimeError("фото не принято")
        self.log.append(("photo", uid, url, caption, kb))
        return str(next(self.ids))

    async def edit(self, uid, mid, text, kb=None):
        self.log.append(("text", uid, text, kb))
        return True

    async def drop_kb(self, uid, mid):
        pass

    async def answer(self, ev, text="", alert=False):
        pass

    async def copy(self, uid, media, kb=None):
        return str(next(self.ids))

    async def link(self):
        return "https://max.ru/id000000000000_bot"

    async def set_commands(self, uid, role):
        pass

    def to(self, uid):
        return [x for x in self.log if x[1] == uid]


def run(coro):
    return asyncio.run(coro)


async def make(tmp_path, photo_ok: bool | None = True, stock: dict | None = None):
    products = parse_catalog(PHOTOS_HTML)
    if stock:
        products = apply_crm(products, stock)
    store = CatalogStore("", "", "", 60)
    store.set(Catalog(products, source="тест"))
    cfg = Config(bot_token="", max_token="x", owner_code="111222", consent_version="1",
                 db_path=str(tmp_path / "bot.db"), catalog_file="", catalog_url="", catalog_cache="",
                 site_url="https://nashdekor.ru")
    db = Database(cfg.db_path)
    await db.init()
    t = Fake(photo_ok)
    e = Engine(cfg, db, store, t)
    await e.start()
    await e.handle(Incoming(user_id=MANAGER, first_name="Юлия", text="/owner 111222", message_id="in"))
    t.log.clear()
    return e, t, db


async def say(e, uid, text):
    await e.handle(Incoming(user_id=uid, first_name="Юлия" if uid == MANAGER else "Иван", text=text, message_id="in"))


def test_number_without_letter_gives_photo_price_and_answer(tmp_path):
    async def scenario():
        e, t, db = await make(tmp_path, stock={"A703": (290, 0)})
        await say(e, MANAGER, "а 0703")
        out = t.to(MANAGER)
        assert [x[0] for x in out] == ["photo", "text"]
        _, _, url, caption, kb = out[0]
        assert url == "https://nashdekor.ru/img/2x/A703.jpg?v=3"
        assert "<b>A703</b>" in caption and "290" in caption and "145" in caption   # за штуку и за метр
        assert "Под заказ, 3–4 недели" in caption and texts.LOOKUP_HINT in caption
        assert [b.data for row in kb.rows for b in row if b.data] == ["ca|A703"]
        assert any("nashdekor.ru/p/a703/" in (b.url or "") for row in kb.rows for b in row)
        answer = out[1][2]
        assert answer.startswith("<code>Здравствуйте! A703 — плинтус напольный A703") and answer.endswith("</code>")
        assert "290 ₽ за штуку (2 м) — это 145 ₽ за метр" in answer and "под заказ, срок 3–4 недели" in answer
        assert "Сколько метров нужно?" in answer and "http" not in answer   # для Авито — без ссылок
        assert e.state(MANAGER) == ""                                     # расчёт не начинается сам
        db.close()
    run(scenario())


def test_several_and_panel_answer(tmp_path):
    async def scenario():
        e, t, db = await make(tmp_path, stock={"A907": (950, 4), "2-3": (660, 0)})
        await say(e, MANAGER, "907 2-3")
        out = t.to(MANAGER)
        assert [x[0] for x in out] == ["photo", "text"]          # смесь «907 2-3» — понимаем одно (2-3), не падаем
        await say(e, MANAGER, "А907, 2-3")
        out = t.to(MANAGER)[2:]
        assert [x[0] for x in out] == ["photo", "photo", "text"]
        answer = out[-1][2]
        assert "Здравствуйте! Цены:" in answer and "A907" in answer and "2-3" in answer
        assert "(есть в наличии)" in answer and "Чего нет в наличии — под заказ" in answer
        await say(e, MANAGER, "907")
        one = t.to(MANAGER)[-1][2]
        assert "≈ 1 759 ₽ за м²" in one and "Есть в наличии в Санкт-Петербурге." in one
        assert "ширину и высоту стены" in one
        db.close()
    run(scenario())


def test_photo_failure_falls_back_to_text(tmp_path):
    async def scenario():
        for mode in (False, None):
            (tmp_path / str(mode)).mkdir()
            e, t, db = await make(tmp_path / str(mode), photo_ok=mode)
            await say(e, MANAGER, "703")
            out = t.to(MANAGER)
            assert [x[0] for x in out] == ["text", "text"], mode
            assert "<b>A703</b>" in out[0][2] and out[1][2].startswith("<code>")
            db.close()
    run(scenario())


def test_client_number_is_not_lookup(tmp_path):
    async def scenario():
        e, t, db = await make(tmp_path)
        await say(e, CLIENT, "/start")
        await say(e, CLIENT, "703")
        assert not [x for x in t.to(CLIENT) if x[0] == "photo"]
        assert not any("Здравствуйте! A703" in (x[2] or "") for x in t.to(CLIENT))
        db.close()
    run(scenario())


def test_not_found_and_calc_number(tmp_path):
    async def scenario():
        e, t, db = await make(tmp_path)
        await say(e, MANAGER, "999")
        assert "Не нашёл «999»" in t.to(MANAGER)[-1][2]
        await say(e, MANAGER, "привет")                           # обычный текст — как раньше
        assert t.to(MANAGER)[-1][2] == texts.TEAM_FREE_TEXT
        # посреди расчёта число — это длина, а не артикул
        await e.handle(Incoming(user_id=MANAGER, first_name="Юлия", data="ca|A703", message_id="5", callback_id="c"))
        assert e.state(MANAGER) == "calc_length"
        await say(e, MANAGER, "15")
        assert "Расчёт" in t.to(MANAGER)[-1][2] or "Итого" in t.to(MANAGER)[-1][2]
        # а артикул с буквой посреди расчёта — справка
        await e.handle(Incoming(user_id=MANAGER, first_name="Юлия", data="ca|A703", message_id="6", callback_id="c"))
        await say(e, MANAGER, "А907")
        assert t.to(MANAGER)[-2][0] == "photo" and e.state(MANAGER) == ""
        db.close()
    run(scenario())


def test_card_without_photo_field(tmp_path):
    """Фото нет на сайте (A80L, A100L) — справка текстом."""
    async def scenario():
        e, t, db = await make(tmp_path)
        p = e.store.get().find("A38")
        assert p.photo == ""
        await say(e, MANAGER, "38")
        assert [x[0] for x in t.to(MANAGER)] == ["text", "text"]
        db.close()
    run(scenario())
