#!/usr/bin/env python3
"""Канал «Наш декор» в Telegram — зеркало канала в MAX: те же оформление, стартовые посты и очередь автопостинга.

Как подключить (17.11.2026): Юля создаёт публичный канал в Telegram и добавляет бота @nashdekor_bot
администратором (права: изменение профиля канала, публикация, редактирование и удаление сообщений).
Служба prostranstvo-bot сама запоминает канал (настройка tg_chats в базе бота), а этот скрипт по cron
(раз в 10 минут, `auto`) оформляет канал, выкладывает стартовые посты один раз и дальше — посты из очереди.

    venv/bin/python tg_channel.py check   — какой канал видит бот и каких прав не хватает
    venv/bin/python tg_channel.py all     — check + оформление + стартовые посты (каждый один раз) + закреп
    venv/bin/python tg_channel.py auto    — то же, если ещё не сделано, и очередной пост из очереди (cron)
    venv/bin/python tg_channel.py queue [--list]
Ключи: --chat @имя_канала или id (если бот не запомнил канал сам), --dry (только показать).

Тексты и кнопки берутся из channel_posts.json / channel_queue.json (как для MAX) и переделываются под Telegram:
ссылки на бота MAX → t.me/nashdekor_bot, «в MAX» → «в Telegram», utm_source=max → tg.
Связь с Telegram — как у бота: через TELEGRAM_PROXY (туннель через Казахстан), в базу ничего не пишет.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import re
import sqlite3
import sys
from typing import Any

from channel import (LATE, MSK, QUEUE_URL, fetch, img_url, load_posts, load_queue, load_state, post_time,
                     read_env, save_state)

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = "/etc/prostranstvo/bot.env"
DB_FILE = "/var/lib/prostranstvo/bot.db"
STATE_FILE = "/var/lib/prostranstvo/tg_channel.json"
TG_CHATS_KEY = "tg_chats"          # пишет tg.py, когда бота добавляют в канал или убирают
TG_BOT_URL = "https://t.me/nashdekor_bot"
MAX_BOT_URL = "https://max.ru/id470331302505_bot"
CAPTION_MAX = 1024                 # подпись к фото в Telegram
DESCRIPTION_MAX = 255              # описание канала в Telegram
PAUSE = 1.5
REPLACE = [(MAX_BOT_URL, TG_BOT_URL), ("utm_source=max", "utm_source=tg"), (" в MAX", " в Telegram")]
NEED = {"can_post_messages": "публиковать посты", "can_edit_messages": "редактировать и закреплять посты",
        "can_change_info": "менять название, описание и фото канала"}


# ------------------------------------------------------------------------------------------------ без сети
def adapt(text: str) -> str:
    for a, b in REPLACE:
        text = text.replace(a, b)
    return text


def plain_len(html: str) -> int:
    return len(re.sub(r"<[^>]+>", "", html).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


def buttons(post: dict[str, Any]) -> list[list[tuple[str, str]]]:
    return [[(adapt(b["text"]), adapt(b["url"])) for b in row] for row in post.get("buttons") or [] if row]


def plan(post: dict[str, Any], cfg: dict[str, Any]) -> list[tuple]:
    """Как пост выйдет в Telegram: ("album", [картинки]) / ("photo", картинка, текст, кнопки) / ("text", текст, кнопки).
    Альбом в Telegram без кнопок и с подписью до 1024 знаков — поэтому после альбома идёт текст с кнопками."""
    text, kb = adapt(post["text"]), buttons(post)
    imgs = [img_url(cfg, n) for n in post.get("images") or []][:10]
    if len(imgs) >= 2:
        return [("album", imgs), ("text", text, kb)]
    if len(imgs) == 1 and plain_len(text) <= CAPTION_MAX:
        return [("photo", imgs[0], text, kb)]
    if imgs:
        return [("album", imgs), ("text", text, kb)]
    return [("text", text, kb)]


def channel_info(cfg: dict[str, Any]) -> dict[str, str]:
    ch = dict(cfg.get("channel") or {})
    ch.update(cfg.get("channel_tg") or {})
    desc = adapt(ch.get("description") or "")
    if len(desc) > DESCRIPTION_MAX:
        desc = desc[:DESCRIPTION_MAX - 1].rsplit(" ", 1)[0] + "…"
    return {"title": (ch.get("title") or "")[:128], "description": desc, "icon": ch.get("icon") or ""}


def known_chats(db_file: str) -> dict[str, dict[str, Any]]:
    try:
        con = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        row = con.execute("SELECT value FROM settings WHERE key = ?", (TG_CHATS_KEY,)).fetchone()
        con.close()
        return json.loads(row[0]) if row else {}
    except (sqlite3.Error, ValueError):
        return {}


def chat_ref(chat: str) -> int | str:
    """id канала числом, @имя — строкой (так их принимает Telegram)."""
    return int(chat) if re.fullmatch(r"-?\d+", str(chat)) else chat


def pick(chats: dict[str, dict[str, Any]], wanted: str = "") -> str:
    if wanted:
        return wanted
    active = sorted(((c.get("at") or 0, cid) for cid, c in chats.items()
                     if c.get("active") and c.get("admin") and c.get("channel")), reverse=True)
    return active[0][1] if active else ""


async def remember_tg_chat(db: Any, chat_id: int | str, title: str, username: str, kind: str, status: str,
                           by: str = "", at: int = 0) -> dict[str, Any]:
    """Бота добавили в канал/группу Telegram или убрали — запомнить (для tg_channel.py и ссылки в приветствии)."""
    try:
        chats = json.loads(await db.get_setting(TG_CHATS_KEY) or "{}")
    except ValueError:
        chats = {}
    cid = str(chat_id)
    item = dict(chats.get(cid) or {})
    item.update(title=title or "", username=username or "", channel=kind == "channel",
                active=status in ("administrator", "creator", "member"), admin=status in ("administrator", "creator"),
                at=int(at or 0))
    if by:
        item["by"] = by
    chats[cid] = item
    await db.set_setting(TG_CHATS_KEY, json.dumps(chats, ensure_ascii=False))
    return item


def channel_url(chats: dict[str, dict[str, Any]]) -> str:
    """Ссылка на наш публичный канал в Telegram (для приветствия бота); "" — канала нет."""
    cid = pick(chats)
    user = (chats.get(cid) or {}).get("username") if cid else ""
    return f"https://t.me/{user}" if user else ""


# ------------------------------------------------------------------------------------------------ Telegram
class TgChannel:
    def __init__(self, bot: Any, cfg: dict[str, Any], state_file: str, dry: bool = False, out=print,
                 key: str = "") -> None:
        self.bot, self.cfg, self.state_file, self.dry, self.out = bot, cfg, state_file, dry, out
        self.key = key

    @staticmethod
    def _kb(rows: list[list[tuple[str, str]]]) -> Any:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        rows = [[InlineKeyboardButton(text=t, url=u) for t, u in row] for row in rows if row]
        return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

    async def _retry(self, fn, *args, **kwargs):
        from aiogram.exceptions import TelegramRetryAfter
        for _ in range(5):
            try:
                return await fn(*args, **kwargs)
            except TelegramRetryAfter as e:
                await asyncio.sleep(int(e.retry_after) + 1)
        return await fn(*args, **kwargs)

    async def _media(self, url: str, upload: bool) -> Any:
        from aiogram.types import BufferedInputFile
        if not upload:
            return url
        return BufferedInputFile(await asyncio.to_thread(fetch, url), os.path.basename(url.split("?")[0]) or "photo.jpg")

    async def check(self, chat: str) -> list[str]:
        info = await self.bot.get_chat(chat)
        me = await self.bot.get_me()
        member = await self.bot.get_chat_member(info.id, me.id)
        self.out(f"Канал: «{info.title}» (@{info.username or '—'}, id {info.id})")
        if member.status not in ("administrator", "creator"):
            self.out("Бот в канале, но не администратор — сделайте его администратором.")
            return list(NEED)
        missing = [k for k in NEED if not getattr(member, k, False)]
        self.out("Не хватает прав у бота: " + "; ".join(NEED[k] for k in missing) if missing
                 else "Права бота — все нужные есть.")
        return missing

    async def check_quiet(self, chat: str) -> list[str]:
        """Как check, но без вывода (cron раз в 10 минут не засоряет журнал)."""
        out, self.out = self.out, (lambda *_: None)
        try:
            return await self.check(chat)
        finally:
            self.out = out

    async def setup(self, chat: str) -> None:
        from aiogram.exceptions import TelegramBadRequest
        from aiogram.types import BufferedInputFile
        info = channel_info(self.cfg)
        st = load_state(self.state_file)
        done = st.setdefault(self.key or str(chat), {})
        if self.dry:
            self.out(f"[проверка] название «{info['title']}», описание {len(info['description'])} знаков, фото {info['icon']}")
            return
        for fn, value in ((self.bot.set_chat_title, info["title"]), (self.bot.set_chat_description, info["description"])):
            if not value:
                continue
            try:
                await self._retry(fn, chat, value)
            except TelegramBadRequest as e:
                if "not modified" not in str(e).lower():
                    raise
        if info["icon"] and not done.get("_photo"):
            img = await asyncio.to_thread(fetch, img_url(self.cfg, info["icon"]))
            await self._retry(self.bot.set_chat_photo, chat, BufferedInputFile(img, "avatar.png"))
            done["_photo"] = "1"
            save_state(self.state_file, st)
        self.out("Оформление канала: название, описание и фото — готово.")

    async def send(self, chat: str, post: dict[str, Any]) -> str:
        """Выложить пост; вернуть «тип:id» главного сообщения (m — текст, c — фото с подписью)."""
        from aiogram.exceptions import TelegramBadRequest
        from aiogram.types import InputMediaPhoto, LinkPreviewOptions
        main = ""
        for step in plan(post, self.cfg):
            for upload in (False, True):          # сначала Telegram забирает картинки по ссылке, не вышло — загружаем
                try:
                    if step[0] == "album":
                        media = [InputMediaPhoto(media=await self._media(u, upload)) for u in step[1]]
                        await self._retry(self.bot.send_media_group, chat, media)
                    elif step[0] == "photo":
                        m = await self._retry(self.bot.send_photo, chat, await self._media(step[1], upload),
                                              caption=step[2], reply_markup=self._kb(step[3]))
                        main = f"c:{m.message_id}"
                    else:
                        m = await self._retry(self.bot.send_message, chat, step[1], reply_markup=self._kb(step[2]),
                                              link_preview_options=LinkPreviewOptions(is_disabled=True))
                        main = f"m:{m.message_id}"
                    break
                except TelegramBadRequest as e:
                    if upload or step[0] == "text":
                        raise
                    self.out(f"  картинки по ссылке Telegram не взял ({e}) — загружаю файлами")
            await asyncio.sleep(PAUSE)
        return main

    async def publish(self, chat: str) -> int:
        st = load_state(self.state_file)
        done = st.setdefault(self.key or str(chat), {})
        posts, n = self.cfg.get("posts") or [], 0
        for post in posts:
            if post["id"] in done:
                continue
            if self.dry:
                self.out(f"[проверка] пост «{post['id']}»: " + ", ".join(s[0] for s in plan(post, self.cfg)))
                continue
            done[post["id"]] = await self.send(chat, post)
            save_state(self.state_file, st)
            n += 1
            self.out(f"  опубликован «{post['id']}»")
        pin = next((p for p in posts if p.get("pin")), None)
        if pin and done.get(pin["id"]) and not done.get("_pinned") and not self.dry:
            await self._retry(self.bot.pin_chat_message, chat, int(done[pin["id"]].split(":")[1]),
                              disable_notification=True)
            done["_pinned"] = pin["id"]
            save_state(self.state_file, st)
            self.out(f"  закреплён «{pin['id']}»")
        if not self.dry:
            done["_starter"] = "1"
            save_state(self.state_file, st)
        return n

    async def queue(self, chat: str, now: dt.datetime | None = None) -> int:
        now = now or dt.datetime.now(MSK)
        st = load_state(self.state_file)
        done = st.setdefault(self.key or str(chat), {})
        due = sorted((p for p in self.cfg.get("posts") or [] if p.get("approved") and p.get("id") and p["id"] not in done
                      and post_time(p) and post_time(p) <= now), key=post_time)
        for post in due:
            if now - post_time(post) > LATE:
                done[post["id"]] = "пропущен"
                save_state(self.state_file, st)
                continue
            if self.dry:
                self.out(f"[проверка] вышел бы пост «{post['id']}» ({post['at']})")
                return 0
            done[post["id"]] = await self.send(chat, post)
            save_state(self.state_file, st)
            self.out(f"{now:%d.%m %H:%M} опубликован «{post['id']}» (по плану {post['at']})")
            return 1
        return 0


async def amain(o: argparse.Namespace) -> int:
    env = read_env(o.env)
    token = env.get("BOT_TOKEN") or os.environ.get("BOT_TOKEN", "")
    if not token:
        print(f"Нет токена Telegram (BOT_TOKEN в {o.env}).")
        return 2
    chat = pick(known_chats(o.db), o.chat)
    st = load_state(o.state)
    if o.cmd == "auto":
        if not chat:
            return 0                                           # канала ещё нет — молча
        starter = bool(st.get(str(chat), {}).get("_starter"))
        hourly = dt.datetime.now(MSK).minute < 10
        if starter and not hourly:
            return 0                                           # всё выложено, очередь смотрим раз в час
    elif not chat:
        print("Бот не видит канал в Telegram. Добавьте @nashdekor_bot в канал администратором "
              "(или укажите --chat @имя_канала).")
        return 1
    from tg import make_bot
    bot = make_bot(token, env.get("TELEGRAM_PROXY", ""))
    key, chat = str(chat), chat_ref(chat)
    try:
        if o.cmd in ("queue",) or (o.cmd == "auto" and st.get(key, {}).get("_starter")):
            cfg = load_queue(o.queue)
            ch = TgChannel(bot, cfg, o.state, o.dry, key=key)
            if o.list:
                done = load_state(o.state).get(key, {})
                for p in sorted(cfg.get("posts") or [], key=lambda p: str(p.get("at") or "")):
                    mark = "вышел" if p.get("id") in done else ("ждёт времени" if p.get("approved") else "ждёт «да»")
                    print(f"  {p.get('at', '—')}  {mark:13}  {p.get('id', '—')}")
            else:
                await ch.queue(chat)
            return 0
        ch = TgChannel(bot, load_posts(o.posts), o.state, o.dry, key=key)
        quiet = o.cmd == "auto" and dt.datetime.now(MSK).minute >= 10
        missing = await ch.check(chat) if not quiet else await ch.check_quiet(chat)
        if o.cmd == "check":
            return 0
        if missing:
            if not quiet:
                print("Дайте боту недостающие права в настройках канала (Администраторы → Наш декор).")
            return 3
        await ch.setup(chat)
        print(f"Опубликовано стартовых постов: {await ch.publish(chat)}.")
        return 0
    finally:
        await bot.session.close()


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("cmd", choices=["check", "all", "auto", "queue"])
    a.add_argument("--chat", default="")
    a.add_argument("--dry", action="store_true")
    a.add_argument("--list", action="store_true")
    a.add_argument("--posts", default=os.path.join(HERE, "channel_posts.json"))
    a.add_argument("--queue", default=QUEUE_URL)
    a.add_argument("--env", default=ENV_FILE)
    a.add_argument("--db", default=DB_FILE)
    a.add_argument("--state", default=STATE_FILE)
    o = a.parse_args(argv)
    try:
        return asyncio.run(amain(o))
    except Exception as e:  # noqa: BLE001 — cron: одна строка в журнал вместо трассировки
        print(f"{dt.datetime.now(MSK):%d.%m %H:%M} ошибка: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
