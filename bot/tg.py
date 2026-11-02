"""Telegram для бота «Пространство»: перевод событий aiogram в ядро и отправка сообщений.

Вся логика — в core.py; здесь только «провода» к Telegram Bot API.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyParameters,
)

import texts
from catalog import CatalogStore
from config import CH_TG, Config
from core import Blocked, Engine, Incoming, Kb, Temporary
from db import ROLE_MANAGER, Database

log = logging.getLogger("prostranstvo.tg")

CLIENT_COMMANDS = [
    ("start", "Главное меню"), ("calc", texts.BTN_CALC), ("catalog", texts.BTN_CATALOG),
    ("lead", texts.BTN_LEAD), ("manager", texts.BTN_MANAGER), ("help", "Помощь"),
    ("delete_me", "Удалить мои данные"),
]
SHIPPING_COMMANDS = [
    ("orders", "Отгрузки"), ("leads", "Последние заявки"), ("history", "Переписка: /history номер_заявки"),
    ("reply", "Ответить клиенту: /reply номер_заявки текст"), ("notify", "Что и куда присылать"),
    ("calc", texts.BTN_CALC), ("catalog", texts.BTN_CATALOG), ("help", "Подсказка"),
]
MANAGER_COMMANDS = [
    ("leads", "Последние заявки"), ("orders", "Отгрузки"), ("history", "Переписка: /history номер_заявки"),
    ("reply", "Ответить клиенту: /reply номер_заявки текст"), ("team", "Команда"),
    ("invite", "Пригласить: /invite manager или shipping"), ("notify", "Что и куда присылать"),
    ("stats", "Статистика"), ("reload", "Обновить цены с сайта"), ("calc", texts.BTN_CALC),
    ("catalog", texts.BTN_CATALOG), ("help", "Подсказка"),
]


def make_bot(token: str, **kwargs: Any) -> Bot:
    return Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
               **kwargs)


def render(kb: Kb | None) -> InlineKeyboardMarkup | ReplyKeyboardMarkup | None:
    if kb is None or not kb.rows:
        return None
    if kb.inline:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=b.text, url=b.url) if b.url else
             InlineKeyboardButton(text=b.text, callback_data=b.data) for b in row] for row in kb.rows])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b.text, request_contact=True) if b.contact else KeyboardButton(text=b.text)
                   for b in row] for row in kb.rows],
        resize_keyboard=True,
        is_persistent=True if kb.menu else None,
        one_time_keyboard=None if kb.menu else True,
    )


class _Errors:
    """Ошибки Telegram → Blocked / Temporary для ядра."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> bool:
        if exc is None:
            return False
        if isinstance(exc, (TelegramForbiddenError, TelegramNotFound)):
            raise Blocked(type(exc).__name__) from exc
        if isinstance(exc, TelegramBadRequest) and "chat not found" in str(exc).lower():
            raise Blocked("chat not found") from exc
        if isinstance(exc, (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)):
            raise Temporary(type(exc).__name__) from exc
        return False


class TgTransport:
    channel = CH_TG

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._link = ""

    async def send(self, user_id: int, text: str, kb: Kb | None = None, reply_to: str = "") -> str:
        reply = ReplyParameters(message_id=int(reply_to), allow_sending_without_reply=True) \
            if reply_to and reply_to.isdigit() else None
        with _Errors():
            msg = await self.bot.send_message(user_id, text, reply_markup=render(kb), reply_parameters=reply)
        return str(msg.message_id)

    async def edit(self, user_id: int, message_id: str, text: str, kb: Kb | None = None) -> bool:
        markup = render(kb) if kb is None or kb.inline else None
        try:
            await self.bot.edit_message_text(text=text, chat_id=user_id, message_id=int(message_id),
                                             reply_markup=markup)  # type: ignore[arg-type]
            return True
        except TelegramBadRequest as exc:
            return "not modified" in str(exc)
        except (TelegramAPIError, ValueError):
            return False

    async def drop_kb(self, user_id: int, message_id: str) -> None:
        with contextlib.suppress(TelegramAPIError, ValueError):
            await self.bot.edit_message_reply_markup(chat_id=user_id, message_id=int(message_id), reply_markup=None)

    async def answer(self, ev: Incoming, text: str = "", alert: bool = False) -> None:
        if ev.callback_id:
            with contextlib.suppress(TelegramAPIError):
                await self.bot.answer_callback_query(ev.callback_id, text=text or None, show_alert=alert or None)

    async def copy(self, user_id: int, media: Any, kb: Kb | None = None) -> str:
        with _Errors():
            msg = await self.bot.copy_message(user_id, from_chat_id=int(media["chat_id"]),
                                              message_id=int(media["message_id"]), reply_markup=render(kb))
        return str(msg.message_id)

    async def link(self) -> str:
        if not self._link:
            me = await self.bot.me()
            self._link = f"https://t.me/{me.username}" if me.username else ""
        return self._link

    async def set_commands(self, user_id: int | None, role: str | None) -> None:
        try:
            if user_id is None:
                await self.bot.set_my_commands(_commands(CLIENT_COMMANDS), scope=BotCommandScopeDefault())
                return
            scope = BotCommandScopeChat(chat_id=user_id)
            if role is None:
                await self.bot.delete_my_commands(scope=scope)
            else:
                items = MANAGER_COMMANDS if role == ROLE_MANAGER else SHIPPING_COMMANDS
                await self.bot.set_my_commands(_commands(items), scope=scope)
        except TelegramAPIError as exc:
            log.debug("список команд не задан: %s", type(exc).__name__)


def _commands(items: list[tuple[str, str]]) -> list[BotCommand]:
    return [BotCommand(command=c, description=d[:256]) for c, d in items]


def _content_type(message: Message) -> str:
    ct = message.content_type
    return str(getattr(ct, "value", ct))


def from_message(message: Message) -> Incoming | None:
    user = message.from_user
    if not user or user.is_bot:
        return None
    kind = "text" if message.text is not None else _content_type(message)
    contact = message.contact
    return Incoming(
        user_id=user.id, first_name=user.first_name or "", last_name=user.last_name or "",
        username=user.username or "", text=message.text, caption=message.caption or "", kind=kind,
        contact_phone=contact.phone_number if contact and contact.phone_number else "",
        message_id=str(message.message_id),
        reply_to=str(message.reply_to_message.message_id) if message.reply_to_message else "",
        media_group=message.media_group_id or "", private=message.chat.type == ChatType.PRIVATE,
        media={"chat_id": message.chat.id, "message_id": message.message_id} if kind != "text" else None,
    )


def from_callback(query: CallbackQuery) -> Incoming:
    user = query.from_user
    msg = query.message if isinstance(query.message, Message) else None
    return Incoming(
        user_id=user.id, first_name=user.first_name or "", last_name=user.last_name or "",
        username=user.username or "", data=query.data or "", callback_id=query.id,
        message_id=str(msg.message_id) if msg else "",
        private=msg.chat.type == ChatType.PRIVATE if msg else True,
    )


def build_dispatcher(engine: Engine) -> Dispatcher:
    router = Router(name="prostranstvo-tg")

    async def on_message(message: Message) -> None:
        ev = from_message(message)
        if ev:
            await engine.handle(ev)

    async def on_callback(query: CallbackQuery) -> None:
        await engine.handle(from_callback(query))

    router.message.register(on_message)
    router.callback_query.register(on_callback)
    dp = Dispatcher(disable_fsm=True)
    dp.include_router(router)
    return dp


async def run(cfg: Config, db: Database, store: CatalogStore) -> int:
    bot = make_bot(cfg.bot_token)
    engine = Engine(cfg, db, store, TgTransport(bot))
    tasks: list[asyncio.Task] = []
    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            log.error("Telegram не принял токен (BOT_TOKEN в /etc/prostranstvo/bot.env). "
                      "Запустите установщик с новым токеном: --tg 'ТОКЕН'")
            await asyncio.sleep(60)
            return 3
        except TelegramNetworkError as exc:
            log.error("нет связи с Telegram (%s) — повтор через 30 секунд", type(exc).__name__)
            await asyncio.sleep(30)
            return 4
        await bot.delete_webhook(drop_pending_updates=False)
        await engine.start()
        log.info("Telegram-бот @%s запущен; каталог: %d позиций; в команде: %d (менеджеров %d, отгрузка %d); "
                 "заявки в Telegram: %s", me.username, len(store.get() or ()), len(engine.team.all()),
                 len(engine.team.managers()), len(engine.team.shipping()),
                 "принимаются" if cfg.telegram_collect_contacts else "на сайт и в MAX")
        if not engine.team.managers():
            log.warning("менеджера ещё нет: отправьте боту /owner КОД (код показал установщик)")
        tasks = [asyncio.create_task(engine.outbox_loop()), asyncio.create_task(store.refresh_forever())]
        dp = build_dispatcher(engine)
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        for task in tasks:
            task.cancel()
        await bot.session.close()
    return 0
