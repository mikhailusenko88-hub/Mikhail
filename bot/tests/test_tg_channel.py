"""Канал в Telegram — зеркало канала MAX (tg_channel.py, 17.11.2026)."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os

import pytest

import texts
import tg_channel as tc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name: str) -> dict:
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))


def all_posts() -> list[tuple[dict, dict]]:
    out = []
    for name in ("channel_posts.json", "channel_queue.json"):
        cfg = load(name)
        out += [(cfg, p) for p in cfg["posts"]]
    return out


def test_adapt_for_telegram():
    assert tc.adapt("Заказать в MAX") == "Заказать в Telegram"
    assert tc.adapt("https://max.ru/id470331302505_bot") == "https://t.me/nashdekor_bot"
    assert tc.adapt("https://nashdekor.ru/?utm_source=max#calc") == "https://nashdekor.ru/?utm_source=tg#calc"


def test_no_max_left_in_telegram_posts():
    for cfg, post in all_posts():
        steps = tc.plan(post, cfg)
        texts_ = [s[2] if s[0] == "photo" else s[1] for s in steps if s[0] in ("text", "photo")]
        btns = [b for s in steps if s[0] in ("text", "photo") for row in s[-1] for b in row]
        for t in texts_:
            assert "max.ru/id470331302505_bot" not in t and " в MAX" not in t, post["id"]
        for label, url in btns:
            assert "MAX" not in label and "max.ru" not in url and url.startswith("https://"), (post["id"], label, url)


def test_plan_fits_telegram_limits():
    for cfg, post in all_posts():
        steps = tc.plan(post, cfg)
        assert steps and steps[-1][0] in ("text", "photo")            # последнее сообщение — с текстом и кнопками
        for s in steps:
            if s[0] == "album":
                assert 1 <= len(s[1]) <= 10
            if s[0] == "photo":
                assert tc.plain_len(s[2]) <= tc.CAPTION_MAX
            if s[0] == "text":
                assert tc.plain_len(s[1]) <= 4096
    paint = next(p for c, p in all_posts() if p["id"] == "paint")
    cfg = load("channel_posts.json")
    assert [s[0] for s in tc.plan(paint, cfg)] == ["album", "text"]
    start = next(p for p in cfg["posts"] if p["id"] == "start")
    assert [s[0] for s in tc.plan(start, cfg)] == ["photo"]


def test_channel_info_fits():
    info = tc.channel_info(load("channel_posts.json"))
    assert info["title"] == "Наш декор — стеновые панели и молдинги"
    assert 0 < len(info["description"]) <= tc.DESCRIPTION_MAX and "@nashdekor_bot" in info["description"]
    assert info["icon"]


class FakeDb:
    def __init__(self) -> None:
        self.s: dict[str, str] = {}

    async def get_setting(self, key: str) -> str:
        return self.s.get(key, "")

    async def set_setting(self, key: str, value: str) -> None:
        self.s[key] = value


def test_remember_channel_and_link():
    async def go():
        db = FakeDb()
        await tc.remember_tg_chat(db, -1001, "Наш декор", "nashdekor_spb", "channel", "administrator", "Юлия", 100)
        chats = json.loads(db.s[tc.TG_CHATS_KEY])
        assert tc.pick(chats) == "-1001"
        assert tc.channel_url(chats) == "https://t.me/nashdekor_spb"
        # бот только подписчик (не админ) или его убрали — не наш канал для постов
        await tc.remember_tg_chat(db, -1002, "Чужой", "other", "channel", "member", at=200)
        await tc.remember_tg_chat(db, -1001, "Наш декор", "nashdekor_spb", "channel", "left", at=300)
        chats = json.loads(db.s[tc.TG_CHATS_KEY])
        assert tc.pick(chats) == "" and tc.channel_url(chats) == ""
        assert tc.chat_ref("-1001") == -1001 and tc.chat_ref("@nashdekor_spb") == "@nashdekor_spb"

    asyncio.run(go())


def test_welcome_points_to_channel():
    assert "Наш канал в MAX" in texts.welcome("https://nashdekor.ru")
    t = texts.welcome("https://nashdekor.ru", True, ("Telegram", "https://t.me/nashdekor_spb"))
    assert "Наш канал в Telegram" in t and "https://t.me/nashdekor_spb" in t and "MAX —" not in t


def test_publish_and_queue_state(tmp_path):
    pytest.importorskip("aiogram")
    sent: list[str] = []

    class Bot:
        async def pin_chat_message(self, chat, mid, disable_notification=True):
            sent.append(f"pin {mid}")

    cfg = load("channel_posts.json")
    state = str(tmp_path / "st.json")
    ch = tc.TgChannel(Bot(), cfg, state, key="-1001", out=lambda *a: None)
    n = {"i": 0}

    async def fake_send(chat, post, done=None, st=None):
        n["i"] += 1
        sent.append(post["id"])
        return f"m:{n['i']}"

    ch.send = fake_send
    assert asyncio.run(ch.publish(-1001)) == len(cfg["posts"])
    assert any(s.startswith("pin ") for s in sent)
    assert asyncio.run(ch.publish(-1001)) == 0                     # второй раз ничего не дублирует
    st = json.load(open(state))["-1001"]
    assert st["_starter"] == "1" and st["_pinned"] == "start"

    q = {"img": cfg["img"], "posts": [
        {"id": "q1", "at": "2026-11-19 12:00", "approved": True, "text": "<b>A910</b>", "images": []},
        {"id": "q2", "at": "2026-11-21 12:00", "approved": False, "text": "нет", "images": []}]}
    chq = tc.TgChannel(Bot(), q, state, key="-1001", out=lambda *a: None)
    chq.send = fake_send
    now = dt.datetime(2026, 11, 19, 12, 5, tzinfo=tc.MSK)
    assert asyncio.run(chq.queue(-1001, now)) == 1
    assert asyncio.run(chq.queue(-1001, now + dt.timedelta(days=5))) == 0   # q2 без «да» не выходит


def test_resume_without_duplicate_album(tmp_path):
    """Запуск оборвался после альбома (ограничение частоты) — следующий не выкладывает альбом второй раз."""
    pytest.importorskip("aiogram")
    from aiogram.exceptions import TelegramNetworkError

    calls: list[str] = []

    class M:
        def __init__(self, i):
            self.message_id = i

    class Bot:
        fail = True

        async def send_media_group(self, chat, media):
            calls.append("album")
            return [M(1), M(2)]

        async def send_message(self, chat, text, **kw):
            calls.append("text")
            if Bot.fail:
                Bot.fail = False
                raise TelegramNetworkError(method=None, message="нет связи")
            return M(3)

    cfg = {"img": "https://nashdekor.ru/img/max/", "posts": [
        {"id": "p", "text": "<b>Пост</b>", "images": ["a.jpg", "b.jpg"], "buttons": []}]}
    state = str(tmp_path / "st.json")
    tc.PAUSE = 0
    ch = tc.TgChannel(Bot(), cfg, state, key="-1", out=lambda *a: None)
    with pytest.raises(TelegramNetworkError):
        asyncio.run(ch.publish(-1))
    assert asyncio.run(ch.publish(-1)) == 1
    assert calls == ["album", "text", "text"]                       # альбом — один раз
    st = json.load(open(state))["-1"]
    assert st["p"] == "m:3" and st["p#0"] == "a:1,2"
