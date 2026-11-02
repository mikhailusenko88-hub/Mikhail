"""Telegram-бот магазина «Пространство» (Санкт-Петербург, декор ARTDEC).

Для клиентов:
  * расчёт панелей и погонажа на стену, каталог с ценами (из index.html сайта);
  * заявка: имя → контакт → комментарий → согласие на обработку ПДн → в базу и команде;
  * любое сообщение пересылается команде магазина; ответ сотрудника приходит сюда же.

Для команды магазина (роли хранятся в базе):
  * «менеджер» — получает все сообщения и заявки, отвечает, передаёт заявки на отгрузку,
    приглашает и убирает людей (/invite, /team, /remove);
  * «отгрузка» — получает заявки и карточки «На отгрузку» (кнопки «Принял», «Отгружено»),
    может читать переписку и отвечать клиенту; все сообщения — по желанию (/notify all).
Статусы заявки: новая → подтверждена → на отгрузке → отгружено.

Запуск на сервере — служба systemd prostranstvo-bot (настройки в /etc/prostranstvo/bot.env).
Для проверки на своём компьютере:
    BOT_TOKEN=... DB_PATH=./bot.db CATALOG_FILE=путь/к/index.html python bot.py
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import re
import sys
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramUnauthorizedError,
)
from aiogram.filters import BaseFilter, Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    User,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import calc
import texts
import yagpt
from catalog import Catalog, CatalogStore, Product, group_title
from config import Config, ConfigError, load_config
from db import (
    NOTIFY_ALL,
    NOTIFY_ORDERS,
    ROLE_MANAGER,
    ROLE_SHIPPING,
    ROLES,
    ST_CONFIRMED,
    ST_SHIPPING,
    Database,
    Lead,
    Shipment,
    iso_now,
    now_local,
)

log = logging.getLogger("prostranstvo.bot")

PAGE_SIZE = 10
ACK_INTERVAL_SEC = 10 * 60      # «сообщение передано» — не чаще раза в 10 минут
MEDIA_GROUP_TTL_SEC = 120
LEAD_NUMBER_MAX = 1_000_000     # «/reply 12 …» — номер заявки; большие числа — Telegram id


# =========================================================================== состояние
class CalcForm(StatesGroup):
    article = State()   # выбор группы / артикула
    width = State()
    height = State()
    length = State()


class LeadForm(StatesGroup):
    name = State()
    contact = State()
    comment = State()
    consent = State()


class ShipForm(StatesGroup):
    items = State()
    address = State()
    when = State()
    phone = State()
    confirm = State()


@dataclass(frozen=True)
class TeamMember:
    tg_id: int
    name: str
    username: str
    role: str
    notify: str
    static: bool = False  # задан в ADMIN_IDS (bot.env) — убрать можно только там


class Team:
    """Команда магазина (из базы) + менеджеры из ADMIN_IDS (bot.env)."""

    def __init__(self, static_managers: frozenset[int] = frozenset()) -> None:
        self.static = set(static_managers)
        self.members: dict[int, TeamMember] = {}

    async def refresh(self, db: Database) -> None:
        for tg_id in self.static:
            await db.ensure_member(tg_id, ROLE_MANAGER)
        self.members = {
            m.tg_id: TeamMember(m.tg_id, m.name, m.username, m.role, m.notify, m.tg_id in self.static)
            for m in await db.team()
        }

    def get(self, user_id: int) -> TeamMember | None:
        return self.members.get(user_id)

    def is_member(self, user_id: int) -> bool:
        return user_id in self.members

    def is_manager(self, user_id: int) -> bool:
        m = self.members.get(user_id)
        return bool(m and m.role == ROLE_MANAGER)

    def role(self, user_id: int) -> str:
        m = self.members.get(user_id)
        return m.role if m else ""

    def ids(self) -> list[int]:
        return sorted(self.members)

    def managers(self) -> list[int]:
        return sorted(i for i, m in self.members.items() if m.role == ROLE_MANAGER)

    def shipping(self) -> list[int]:
        return sorted(i for i, m in self.members.items() if m.role == ROLE_SHIPPING)

    def message_recipients(self) -> list[int]:
        """Кому слать каждое сообщение клиента: включившим «все сообщения», иначе менеджерам."""
        chosen = sorted(i for i, m in self.members.items() if m.notify == NOTIFY_ALL)
        return chosen or self.managers()

    def name(self, user_id: int) -> str:
        m = self.members.get(user_id)
        return (m.name or (f"@{m.username}" if m.username else "")) if m else ""

    def sorted_members(self) -> list[TeamMember]:
        return sorted(self.members.values(), key=lambda m: (m.role != ROLE_MANAGER, m.name))


class AttemptLimiter:
    """Защита /owner и /join от подбора кода: 5 попыток на человека и 50 всего за час."""

    def __init__(self, per_user: int = 5, total: int = 50, window: int = 3600) -> None:
        self.per_user, self.total, self.window = per_user, total, window
        self._all: deque[float] = deque()
        self._users: dict[int, deque[float]] = {}

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        while self._all and now - self._all[0] > self.window:
            self._all.popleft()
        user = self._users.setdefault(user_id, deque())
        while user and now - user[0] > self.window:
            user.popleft()
        if len(user) >= self.per_user or len(self._all) >= self.total:
            return False
        user.append(now)
        self._all.append(now)
        return True


class Runtime:
    """Мелкое состояние в памяти: когда клиенту последний раз писали «передано» и т.п."""

    def __init__(self) -> None:
        self.last_ack: OrderedDict[int, float] = OrderedDict()
        self.media_groups: OrderedDict[str, float] = OrderedDict()

    @staticmethod
    def _trim(d: OrderedDict, limit: int = 5000) -> None:
        while len(d) > limit:
            d.popitem(last=False)

    def need_ack(self, user_id: int) -> bool:
        now = time.monotonic()
        last = self.last_ack.get(user_id)
        if last is not None and now - last < ACK_INTERVAL_SEC:
            return False
        self.last_ack[user_id] = now
        self.last_ack.move_to_end(user_id)
        self._trim(self.last_ack)
        return True

    def first_in_media_group(self, key: str | None) -> bool:
        if not key:
            return True
        now = time.monotonic()
        for old in [k for k, t in self.media_groups.items() if now - t > MEDIA_GROUP_TTL_SEC]:
            del self.media_groups[old]
        if key in self.media_groups:
            return False
        self.media_groups[key] = now
        self._trim(self.media_groups)
        return True


class IsTeam(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, team: Team) -> bool:
        return bool(event.from_user and team.is_member(event.from_user.id))


class IsManager(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, team: Team) -> bool:
        return bool(event.from_user and team.is_manager(event.from_user.id))


# =========================================================================== клавиатуры
def _reply_kb(rows: list[list[str]], **kwargs: Any) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
                               resize_keyboard=True, **kwargs)


def client_menu() -> ReplyKeyboardMarkup:
    return _reply_kb([[texts.BTN_CALC, texts.BTN_CATALOG], [texts.BTN_LEAD, texts.BTN_MANAGER]],
                     is_persistent=True)


def team_menu(role: str) -> ReplyKeyboardMarkup:
    rows = [[texts.BTN_T_LEADS, texts.BTN_T_ORDERS], [texts.BTN_CALC, texts.BTN_CATALOG]]
    if role == ROLE_MANAGER:
        rows.append([texts.BTN_T_TEAM, texts.BTN_T_STATS])
    rows.append([texts.BTN_T_NOTIFY, texts.BTN_T_HELP])
    return _reply_kb(rows, is_persistent=True)


def menu_for(team: Team, user: User | None) -> ReplyKeyboardMarkup:
    member = team.get(user.id) if user else None
    return team_menu(member.role) if member else client_menu()


def name_kb(first_name: str | None) -> ReplyKeyboardMarkup:
    rows = []
    if first_name and len(first_name) <= 60 and first_name not in texts.MENU_BUTTONS:
        rows.append([first_name])
    rows.append([texts.BTN_CANCEL])
    return _reply_kb(rows, one_time_keyboard=True)


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_SEND_PHONE, request_contact=True)],
            [KeyboardButton(text=texts.BTN_WRITE_TG)],
            [KeyboardButton(text=texts.BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def comment_kb() -> ReplyKeyboardMarkup:
    return _reply_kb([[texts.BTN_SKIP, texts.BTN_CANCEL]], one_time_keyboard=True)


def _inline(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows if row
    ])


def consent_kb() -> InlineKeyboardMarkup:
    return _inline([[(texts.BTN_AGREE, "lead|yes"), (texts.BTN_CANCEL, "lead|no")]])


def delete_kb() -> InlineKeyboardMarkup:
    return _inline([[(texts.BTN_DELETE_YES, "del|yes"), (texts.BTN_CANCEL, "del|no")]])


def _cb(*parts: object) -> str | None:
    """callback_data из частей; None — если не помещается в 64 байта Telegram."""
    if any("|" in str(p) for p in parts):
        return None
    data = "|".join(str(p) for p in parts)
    return data if len(data.encode()) <= 64 else None


def groups_kb(catalog: Catalog, prefix: str) -> InlineKeyboardMarkup:
    return _inline([[(title, f"{prefix}|{code}")] for code, title in catalog.groups()])


def _article_button_text(p: Product) -> str:
    if p.kind == "color" and p.short_desc:
        return f"{p.article} · {p.short_desc}"[:40]
    return f"{p.article} · {p.price} ₽"


def articles_kb(group: str, items: list[Product], page: int, pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    count = 0
    for p in items:
        data = _cb("ca", p.article)
        if data:
            kb.button(text=_article_button_text(p), callback_data=data)
            count += 1
    width = 1 if group == "color" else 2
    sizes = [width] * ((count + width - 1) // width)
    markup = kb.adjust(*sizes).as_markup() if sizes else InlineKeyboardMarkup(inline_keyboard=[])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=texts.BTN_PREV, callback_data=f"cp|{group}|{page - 1}"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton(text=texts.BTN_NEXT, callback_data=f"cp|{group}|{page + 1}"))
    if nav:
        markup.inline_keyboard.append(nav)
    markup.inline_keyboard.append([InlineKeyboardButton(text=texts.BTN_TO_GROUPS, callback_data="cb")])
    return markup


def calc_result_kb(send_data: str | None) -> InlineKeyboardMarkup:
    return _inline([[(texts.BTN_SEND_CALC, send_data)] if send_data else [],
                    [(texts.BTN_CALC_AGAIN, "cn")]])


def catalog_group_kb(group: str, site_url: str) -> InlineKeyboardMarkup:
    markup = _inline([[(f"{texts.BTN_CALC_GROUP}: {group_title(group)}", f"cgn|{group}")],
                      [(texts.BTN_OTHER_GROUPS, "kb")]])
    if site_url:
        markup.inline_keyboard.append([InlineKeyboardButton(text=texts.BTN_SITE, url=site_url)])
    return markup


def history_button(tg_id: int) -> tuple[str, str]:
    return texts.BTN_HISTORY, f"hist|{tg_id}"


def lead_kb(lead: Lead, role: str) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    if role == ROLE_MANAGER:
        rows.append([(texts.BTN_TO_SHIPPING, f"shp|{lead.id}")])
    rows.append([history_button(lead.tg_id)])
    return _inline(rows)


def ship_kb(ship: Shipment, is_manager: bool) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    if not ship.cancelled_ts:
        if ship.status == ST_CONFIRMED:
            rows.append([(texts.BTN_SHIP_ACCEPT, f"sh|acc|{ship.lead_id}"),
                         (texts.BTN_SHIP_DONE, f"sh|done|{ship.lead_id}")])
        elif ship.status == ST_SHIPPING:
            rows.append([(texts.BTN_SHIP_DONE, f"sh|done|{ship.lead_id}")])
        if is_manager and ship.status in (ST_CONFIRMED, ST_SHIPPING):
            rows.append([(texts.BTN_SHIP_CANCEL, f"sh|cancel|{ship.lead_id}")])
    rows.append([history_button(ship.client_tg_id)])
    return _inline(rows)


def ship_step_kb(*first_row: str) -> ReplyKeyboardMarkup:
    rows = [list(first_row)] if first_row else []
    rows.append([texts.BTN_CANCEL])
    return _reply_kb(rows, one_time_keyboard=True)


# =========================================================================== помощники
async def _show(target: Message | CallbackQuery, text: str, markup: Any = None) -> None:
    """Для кнопки — заменить сообщение с кнопками, для текста — ответить новым."""
    if isinstance(target, CallbackQuery):
        msg = target.message
        if isinstance(msg, Message):
            try:
                await msg.edit_text(text, reply_markup=markup)
                return
            except TelegramBadRequest as exc:
                if "not modified" in str(exc):
                    return
            await msg.answer(text, reply_markup=markup)
        elif target.from_user and target.bot:
            await target.bot.send_message(target.from_user.id, text, reply_markup=markup)
        return
    await target.answer(text, reply_markup=markup)


async def _drop_buttons(msg: Message) -> None:
    try:
        await msg.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


async def _send_team(bot: Bot, db: Database, ids: list[int], text: str,
                     markup: Callable[[int], Any] | None = None, client_id: int | None = None,
                     lead_id: int | None = None) -> list[int]:
    """Отправить сотрудникам; если указан клиент — запомнить, куда уйдёт ответ на это сообщение."""
    delivered = []
    for uid in ids:
        try:
            sent = await bot.send_message(uid, text, reply_markup=markup(uid) if markup else None)
        except TelegramAPIError as exc:
            log.warning("не удалось отправить сотруднику: %s", type(exc).__name__)
            continue
        delivered.append(uid)
        if client_id is not None:
            await db.add_relay(uid, sent.message_id, client_id, lead_id)
    return delivered


_CLIENT_COMMANDS = [
    ("start", "Главное меню"), ("calc", texts.BTN_CALC), ("catalog", texts.BTN_CATALOG),
    ("lead", texts.BTN_LEAD), ("manager", texts.BTN_MANAGER), ("help", "Помощь"),
    ("delete_me", "Удалить мои данные"),
]
_SHIPPING_COMMANDS = [
    ("orders", "Отгрузки"), ("leads", "Последние заявки"), ("history", "Переписка: /history номер_заявки"),
    ("reply", "Ответить клиенту: /reply номер_заявки текст"), ("notify", "Какие уведомления получать"),
    ("calc", texts.BTN_CALC), ("catalog", texts.BTN_CATALOG), ("help", "Подсказка"),
]
_MANAGER_COMMANDS = [
    ("leads", "Последние заявки"), ("orders", "Отгрузки"), ("history", "Переписка: /history номер_заявки"),
    ("reply", "Ответить клиенту: /reply номер_заявки текст"), ("team", "Команда"),
    ("invite", "Пригласить: /invite manager или shipping"), ("notify", "Какие уведомления получать"),
    ("stats", "Статистика"), ("reload", "Обновить цены с сайта"), ("calc", texts.BTN_CALC),
    ("catalog", texts.BTN_CATALOG), ("help", "Подсказка"),
]


def _commands(items: list[tuple[str, str]]) -> list[BotCommand]:
    return [BotCommand(command=c, description=d[:256]) for c, d in items]


async def _setup_commands(bot: Bot, team: Team, only: int | None = None) -> None:
    """Список команд в меню Telegram: у клиентов свой, у менеджера и отгрузки — свои."""
    try:
        if only is None:
            await bot.set_my_commands(_commands(_CLIENT_COMMANDS), scope=BotCommandScopeDefault())
        for uid in ([only] if only is not None else team.ids()):
            member = team.get(uid)
            scope = BotCommandScopeChat(chat_id=uid)
            try:
                if member is None:
                    await bot.delete_my_commands(scope=scope)
                else:
                    items = _MANAGER_COMMANDS if member.role == ROLE_MANAGER else _SHIPPING_COMMANDS
                    await bot.set_my_commands(_commands(items), scope=scope)
            except TelegramAPIError:
                pass  # человек ещё не открывал чат с ботом
    except TelegramAPIError as exc:
        log.warning("не удалось задать список команд: %s", type(exc).__name__)


async def _resolve_client(arg: str, db: Database) -> tuple[int | None, Lead | None]:
    """«#12», «№12», «12» — номер заявки; большое число — Telegram id клиента."""
    m = re.fullmatch(r"(#|№)?(\d+)", arg.strip())
    if not m:
        return None, None
    number = int(m.group(2))
    if m.group(1) or number < LEAD_NUMBER_MAX:
        lead = await db.get_lead(number)
        return (lead.tg_id, lead) if lead else (None, None)
    return number, None


def _content_type(message: Message) -> str:
    ct = message.content_type
    return str(getattr(ct, "value", ct))


def _role_help(role: str) -> str:
    return texts.help_manager() if role == ROLE_MANAGER else texts.help_shipping()


# =========================================================================== общее меню
async def cmd_start(message: Message, state: FSMContext, command: CommandObject, cfg: Config,
                    store: CatalogStore, team: Team) -> None:
    await state.clear()
    member = team.get(message.from_user.id) if message.from_user else None
    payload = (command.args or "").strip()
    if member and not payload:
        await message.answer(_role_help(member.role), reply_markup=team_menu(member.role))
        return
    menu = menu_for(team, message.from_user)
    route = {"calc": open_calc, "catalog": open_catalog, "lead": open_lead, "manager": open_manager}
    await message.answer(texts.welcome(cfg.site_url), reply_markup=menu)
    if payload in route:
        await route[payload](message, state, store=store, team=team)
        return
    catalog = store.get()
    product = catalog.find(payload) if catalog and payload else None
    if product:
        await _start_product(message, state, product, team)


async def cmd_help(message: Message, cfg: Config, team: Team) -> None:
    member = team.get(message.from_user.id) if message.from_user else None
    if member:
        await message.answer(_role_help(member.role), reply_markup=team_menu(member.role))
        return
    await message.answer(texts.help_client(cfg.site_url), reply_markup=client_menu())


async def cmd_cancel(message: Message, state: FSMContext, team: Team) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=menu_for(team, message.from_user))


# =========================================================================== каталог
async def open_catalog(message: Message, state: FSMContext, store: CatalogStore, team: Team, **_: Any) -> None:
    await state.clear()
    catalog = store.get()
    if not catalog:
        await message.answer(texts.CATALOG_UNAVAILABLE, reply_markup=menu_for(team, message.from_user))
        return
    await message.answer(texts.CATALOG_CHOOSE_GROUP, reply_markup=groups_kb(catalog, "kg"))


async def cb_catalog_group(cb: CallbackQuery, store: CatalogStore, cfg: Config) -> None:
    await cb.answer()
    catalog = store.get()
    group = (cb.data or "").split("|", 1)[-1]
    items = catalog.in_group(group) if catalog else []
    if not items or not isinstance(cb.message, Message):
        await _show(cb, texts.CATALOG_UNAVAILABLE)
        return
    parts = texts.catalog_group(group, items, cfg.site_url)
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        await cb.message.answer(part, reply_markup=catalog_group_kb(group, cfg.site_link()) if last else None)


async def cb_catalog_groups(cb: CallbackQuery, store: CatalogStore) -> None:
    await cb.answer()
    catalog = store.get()
    if not catalog or not isinstance(cb.message, Message):
        await _show(cb, texts.CATALOG_UNAVAILABLE)
        return
    await cb.message.answer(texts.CATALOG_CHOOSE_GROUP, reply_markup=groups_kb(catalog, "kg"))


# =========================================================================== расчёт
async def open_calc(target: Message | CallbackQuery, state: FSMContext, store: CatalogStore,
                    **_: Any) -> None:
    await state.clear()
    catalog = store.get()
    if not catalog:
        await _show(target, texts.CATALOG_UNAVAILABLE)
        return
    await state.set_state(CalcForm.article)
    msg = target.message if isinstance(target, CallbackQuery) else target
    if isinstance(msg, Message):
        await msg.answer(texts.CALC_CHOOSE_GROUP, reply_markup=groups_kb(catalog, "cg"))


async def _show_group_page(target: Message | CallbackQuery, catalog: Catalog, group: str, page: int) -> None:
    items = catalog.in_group(group)
    if not items:
        await _show(target, texts.CALC_CHOOSE_GROUP, groups_kb(catalog, "cg"))
        return
    pages = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, pages - 1))
    chunk = items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    await _show(target, texts.calc_choose_article(group, chunk, page, pages),
                articles_kb(group, chunk, page, pages))


async def cb_calc_group(cb: CallbackQuery, state: FSMContext, store: CatalogStore) -> None:
    await cb.answer()
    catalog = store.get()
    if not catalog:
        await _show(cb, texts.CATALOG_UNAVAILABLE)
        return
    await state.clear()
    await state.set_state(CalcForm.article)
    prefix, _, group = (cb.data or "").partition("|")
    if prefix == "cg":
        await _show_group_page(cb, catalog, group, 0)
    elif isinstance(cb.message, Message):
        # «Рассчитать» под списком цен: список не трогаем, выбор артикула — новым сообщением
        await _show_group_page(cb.message, catalog, group, 0)


async def cb_calc_page(cb: CallbackQuery, state: FSMContext, store: CatalogStore) -> None:
    await cb.answer()
    catalog = store.get()
    parts = (cb.data or "").split("|")
    if not catalog or len(parts) != 3 or not parts[2].isdigit():
        await _show(cb, texts.CATALOG_UNAVAILABLE)
        return
    await state.set_state(CalcForm.article)
    await _show_group_page(cb, catalog, parts[1], int(parts[2]))


async def cb_calc_back(cb: CallbackQuery, state: FSMContext, store: CatalogStore) -> None:
    await cb.answer()
    catalog = store.get()
    if not catalog:
        await _show(cb, texts.CATALOG_UNAVAILABLE)
        return
    await state.set_state(CalcForm.article)
    await _show(cb, texts.CALC_CHOOSE_GROUP, groups_kb(catalog, "cg"))


async def cb_calc_article(cb: CallbackQuery, state: FSMContext, store: CatalogStore, team: Team) -> None:
    await cb.answer()
    catalog = store.get()
    article = (cb.data or "").split("|", 1)[-1]
    product = catalog.find(article) if catalog else None
    if not product or not isinstance(cb.message, Message):
        await _show(cb, texts.CALC_EXPIRED)
        return
    await _start_product(cb.message, state, product, team, cb.from_user)


async def _start_product(message: Message, state: FSMContext, product: Product, team: Team,
                         user: User | None = None) -> None:
    await state.clear()
    await state.update_data(article=product.article)
    menu = menu_for(team, user or message.from_user)
    if product.is_area:
        await state.set_state(CalcForm.width)
        await message.answer(texts.ask_width(product), reply_markup=menu)
    else:
        await state.set_state(CalcForm.length)
        await message.answer(texts.ask_length(product), reply_markup=menu)


async def calc_article_text(message: Message, state: FSMContext, store: CatalogStore, team: Team) -> None:
    catalog = store.get()
    if not catalog:
        await message.answer(texts.CATALOG_UNAVAILABLE)
        return
    query = (message.text or "").strip()
    product = catalog.find(query)
    if product:
        await _start_product(message, state, product, team)
        return
    await message.answer(texts.article_not_found(query, catalog.search(query)),
                         reply_markup=groups_kb(catalog, "cg"))


async def _current_product(state: FSMContext, store: CatalogStore) -> Product | None:
    data = await state.get_data()
    catalog = store.get()
    article = data.get("article")
    return catalog.find(article) if catalog and article else None


async def _calc_expired(message: Message, state: FSMContext, team: Team) -> None:
    await state.clear()
    await message.answer(texts.CALC_EXPIRED, reply_markup=menu_for(team, message.from_user))


async def _finish_area(message: Message, state: FSMContext, cfg: Config, product: Product,
                       width_mm: int, height_mm: int) -> None:
    result = calc.calc_area(width_mm, height_mm, product.width, product.length,
                            product.per_box, product.price, cfg.reserve_percent)
    await state.clear()
    await message.answer(texts.calc_result_area(product, result),
                         reply_markup=calc_result_kb(_cb("ls", product.article, width_mm, height_mm)))


async def calc_width(message: Message, state: FSMContext, store: CatalogStore, cfg: Config, team: Team) -> None:
    product = await _current_product(state, store)
    if not product:
        await _calc_expired(message, state, team)
        return
    text = message.text or ""
    try:
        pair = calc.parse_wall_pair(text)
        if pair:
            await _finish_area(message, state, cfg, product, *pair)
            return
        width_mm = calc.parse_length_mm(text, calc.MAX_WALL_WIDTH_M)
    except calc.InputError as err:
        await message.answer(texts.input_error(err, "width"))
        return
    await state.update_data(width_mm=width_mm)
    await state.set_state(CalcForm.height)
    await message.answer(texts.ask_height(width_mm))


async def calc_height(message: Message, state: FSMContext, store: CatalogStore, cfg: Config, team: Team) -> None:
    product = await _current_product(state, store)
    width_mm = (await state.get_data()).get("width_mm")
    if not product or not isinstance(width_mm, int):
        await _calc_expired(message, state, team)
        return
    try:
        height_mm = calc.parse_length_mm(message.text or "", calc.MAX_WALL_HEIGHT_M)
    except calc.InputError as err:
        await message.answer(texts.input_error(err, "height"))
        return
    await _finish_area(message, state, cfg, product, width_mm, height_mm)


async def calc_length(message: Message, state: FSMContext, store: CatalogStore, cfg: Config, team: Team) -> None:
    product = await _current_product(state, store)
    if not product:
        await _calc_expired(message, state, team)
        return
    try:
        length_mm = calc.parse_length_mm(message.text or "", calc.MAX_LINEAR_M)
    except calc.InputError as err:
        await message.answer(texts.input_error(err, "length"))
        return
    result = calc.calc_linear(length_mm, product.length, product.per_box, product.price, cfg.reserve_percent)
    await state.clear()
    await message.answer(texts.calc_result_linear(product, result),
                         reply_markup=calc_result_kb(_cb("ll", product.article, length_mm)))


async def calc_bad_input(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    what = {CalcForm.width.state: "width", CalcForm.height.state: "height"}.get(current or "", "length")
    await message.answer(texts.input_error(calc.InputError("format"), what))


async def cb_calc_again(cb: CallbackQuery, state: FSMContext, store: CatalogStore) -> None:
    await cb.answer()
    await open_calc(cb, state, store=store)


def _summary_from_callback(data: str, catalog: Catalog | None, cfg: Config) -> str | None:
    parts = data.split("|")
    if not catalog or len(parts) < 3 or not all(p.isdigit() for p in parts[2:]):
        return None
    product = catalog.find(parts[1])
    if not product:
        return None
    nums = [int(p) for p in parts[2:]]
    try:
        if parts[0] == "ls" and len(nums) == 2 and product.is_area:
            result: calc.AreaResult | calc.LinearResult = calc.calc_area(
                nums[0], nums[1], product.width, product.length, product.per_box, product.price,
                cfg.reserve_percent)
        elif parts[0] == "ll" and len(nums) == 1 and not product.is_area:
            result = calc.calc_linear(nums[0], product.length, product.per_box, product.price,
                                      cfg.reserve_percent)
        else:
            return None
    except ValueError:
        return None
    return texts.calc_summary(product, result)


async def cb_send_calc(cb: CallbackQuery, state: FSMContext, store: CatalogStore, cfg: Config) -> None:
    await cb.answer()
    summary = _summary_from_callback(cb.data or "", store.get(), cfg)
    if not summary or not isinstance(cb.message, Message):
        await _show(cb, texts.CALC_EXPIRED)
        return
    await _drop_buttons(cb.message)
    await _begin_lead(cb.message, state, cb.from_user.first_name if cb.from_user else None, summary)


# =========================================================================== заявка
async def open_lead(message: Message, state: FSMContext, **_: Any) -> None:
    await _begin_lead(message, state, message.from_user.first_name if message.from_user else None, "")


async def _begin_lead(message: Message, state: FSMContext, first_name: str | None, calc_summary: str) -> None:
    await state.clear()
    await state.update_data(calc=calc_summary)
    await state.set_state(LeadForm.name)
    await message.answer(texts.lead_ask_name(bool(calc_summary)), reply_markup=name_kb(first_name))


async def lead_name(message: Message, state: FSMContext) -> None:
    name = re.sub(r"\s+", " ", message.text or "").strip()
    if not name or len(name) > 60 or name.startswith("/"):
        await message.answer(texts.LEAD_BAD_NAME)
        return
    await state.update_data(name=name)
    await state.set_state(LeadForm.contact)
    await message.answer(texts.LEAD_ASK_CONTACT, reply_markup=contact_kb())


_PHONE_CHARS_RE = re.compile(r"^[\d\s()+\-.]{10,25}$")
_TG_NICK_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{3,31}$")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")


def parse_phone(text: str) -> str | None:
    s = text.strip()
    digits = re.sub(r"\D", "", s)
    if not (_PHONE_CHARS_RE.match(s) and 10 <= len(digits) <= 15):
        return None
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        digits = "7" + digits
    return "+" + digits


def parse_contact(text: str) -> str | None:
    """Телефон / @ник / e-mail из текста; None — если не похоже ни на что."""
    s = text.strip()
    phone = parse_phone(s)
    if phone:
        return phone
    if s.startswith("@") and _TG_NICK_RE.match(s):
        return "Telegram " + s
    if _EMAIL_RE.match(s):
        return s
    return None


async def lead_contact(message: Message, state: FSMContext) -> None:
    contact: str | None = None
    if message.contact and message.contact.phone_number:
        digits = re.sub(r"\D", "", message.contact.phone_number)
        contact = "+" + digits if digits else None
    elif message.text == texts.BTN_WRITE_TG:
        contact = texts.contact_tg(message.from_user.username if message.from_user else None)
    elif message.text:
        contact = parse_contact(message.text)
    if not contact:
        await message.answer(texts.LEAD_BAD_CONTACT, reply_markup=contact_kb())
        return
    await state.update_data(contact=contact)
    await state.set_state(LeadForm.comment)
    await message.answer(texts.LEAD_ASK_COMMENT, reply_markup=comment_kb())


async def lead_comment(message: Message, state: FSMContext, cfg: Config, team: Team) -> None:
    text = message.text if message.text is not None else message.caption
    if text is None:
        await message.answer(texts.LEAD_BAD_COMMENT)
        return
    comment = "" if text == texts.BTN_SKIP else text.strip()
    if len(comment) > 1000:
        comment = comment[:999] + "…"
    await state.update_data(comment=comment)
    await state.set_state(LeadForm.consent)
    data = await state.get_data()
    await message.answer(
        texts.lead_review(data.get("name", ""), data.get("contact", ""), comment, data.get("calc", "")),
        reply_markup=menu_for(team, message.from_user),
    )
    await message.answer(texts.consent_text(cfg.site_url, cfg.operator_name), reply_markup=consent_kb())


async def lead_consent_text(message: Message) -> None:
    await message.answer(f"Нажмите «{texts.BTN_AGREE}» или «{texts.BTN_CANCEL}» под сообщением выше.",
                         reply_markup=consent_kb())


async def cb_lead_consent(cb: CallbackQuery, state: FSMContext, bot: Bot, db: Database,
                          team: Team, cfg: Config) -> None:
    await cb.answer()
    msg = cb.message if isinstance(cb.message, Message) else None
    menu = menu_for(team, cb.from_user)
    if await state.get_state() != LeadForm.consent.state or not cb.from_user:
        if msg:
            await _drop_buttons(msg)
            await msg.answer(texts.LEAD_EXPIRED, reply_markup=menu)
        return
    data = await state.get_data()
    await state.clear()
    if msg:
        await _drop_buttons(msg)
    if (cb.data or "").endswith("|no"):
        if msg:
            await msg.answer(texts.LEAD_CANCELLED, reply_markup=menu)
        return

    user = cb.from_user
    lead_id = await db.add_lead(
        tg_id=user.id, username=user.username, name=data.get("name", ""), contact=data.get("contact", ""),
        comment=data.get("comment", ""), calc=data.get("calc", ""), consent_at=iso_now(),
        consent_version=cfg.consent_version,
    )
    log.info("заявка №%d сохранена", lead_id)
    if msg:
        await msg.answer(texts.lead_thanks(lead_id), reply_markup=menu)
    lead = await db.get_lead(lead_id)
    if lead is None:  # pragma: no cover - только что сохранили
        return
    # копия заявки — всем в команде: менеджеру с кнопкой «Передать на отгрузку»
    delivered = await _send_team(bot, db, team.ids(), texts.lead_card(lead),
                                 markup=lambda uid: lead_kb(lead, team.role(uid)),
                                 client_id=user.id, lead_id=lead_id)
    if not delivered:
        log.warning("заявка №%d не доставлена никому из команды (команды ещё нет: /owner КОД)", lead_id)


# =========================================================================== сообщения клиентов
async def open_manager(message: Message, state: FSMContext, team: Team, **_: Any) -> None:
    await state.clear()
    await message.answer(texts.MANAGER_PROMPT, reply_markup=menu_for(team, message.from_user))


_KIND_NAMES = {
    "photo": "фото", "document": "файл", "voice": "голосовое", "video": "видео",
    "video_note": "видео-кружок", "audio": "аудио", "sticker": "стикер", "animation": "GIF",
    "location": "геопозиция", "contact": "контакт", "venue": "место", "poll": "опрос",
}


async def client_message(message: Message, bot: Bot, db: Database, team: Team, cfg: Config,
                         rt: Runtime) -> None:
    """Свободное сообщение клиента → в базу и команде магазина."""
    user = message.from_user
    if not user:
        return
    if message.text and message.text.startswith("/"):
        await message.answer(texts.help_client(cfg.site_url), reply_markup=client_menu())
        return
    kind = "text" if message.text is not None else _content_type(message)
    kind_ru = _KIND_NAMES.get(kind, kind)
    body = message.text if message.text is not None else (message.caption or "")
    if kind == "contact" and message.contact:
        body = f"{message.contact.first_name or ''} {message.contact.phone_number or ''}".strip()
    await db.add_message(tg_id=user.id, username=user.username, name=user.full_name, direction="in",
                         kind="text" if kind == "text" else kind_ru, text=body)

    history_kb = _inline([[history_button(user.id)]])
    delivered = 0
    for uid in team.message_recipients():
        try:
            if kind == "text":
                sent = await bot.send_message(
                    uid, texts.client_message_text(user.full_name, user.username, body), reply_markup=history_kb)
                await db.add_relay(uid, sent.message_id, user.id)
            else:
                group_key = f"{uid}:{message.media_group_id}" if message.media_group_id else None
                if rt.first_in_media_group(group_key):
                    head = await bot.send_message(
                        uid, texts.client_message_header(user.full_name, user.username, kind_ru),
                        reply_markup=history_kb)
                    await db.add_relay(uid, head.message_id, user.id)
                copied = await bot.copy_message(uid, from_chat_id=message.chat.id, message_id=message.message_id)
                await db.add_relay(uid, copied.message_id, user.id)
            delivered += 1
        except TelegramAPIError as exc:
            log.warning("сообщение клиента не переслано сотруднику: %s", type(exc).__name__)
    if not delivered:
        log.warning("сообщение клиента сохранено, но не переслано: в команде никого нет или все недоступны")

    if yagpt.is_enabled(cfg) and kind == "text" and delivered:
        draft = await yagpt.suggest_reply(cfg, body)
        if draft:
            await _send_team(bot, db, team.message_recipients(),
                             "Черновик ответа (клиенту не отправлен):\n" + texts.esc(draft), client_id=user.id)

    if rt.need_ack(user.id):
        await message.answer(texts.MESSAGE_RECEIVED, reply_markup=client_menu())


async def unexpected_in_lead(message: Message) -> None:
    await message.answer(texts.LEAD_BAD_NAME)


# =========================================================================== удаление данных
async def cmd_delete_me(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.DELETE_CONFIRM, reply_markup=delete_kb())


async def cb_delete(cb: CallbackQuery, bot: Bot, db: Database, team: Team) -> None:
    await cb.answer()
    msg = cb.message if isinstance(cb.message, Message) else None
    if msg:
        await _drop_buttons(msg)
    if not cb.from_user:
        return
    menu = menu_for(team, cb.from_user)
    if not (cb.data or "").endswith("|yes"):
        if msg:
            await msg.answer(texts.DELETE_CANCELLED, reply_markup=menu)
        return
    name, _ = await db.client_name(cb.from_user.id)
    leads, kept, messages = await db.delete_client(cb.from_user.id)
    log.info("клиент отозвал согласие: удалено заявок %d, сообщений %d, оставлено заказов %d",
             leads, messages, kept)
    if leads or messages or kept:
        await _send_team(bot, db, team.managers(),
                         texts.client_deleted(name or cb.from_user.full_name, leads, kept, messages))
    if msg:
        await msg.answer(texts.delete_done(leads, kept, messages), reply_markup=menu)


# =========================================================================== вход в команду
async def _after_join(message: Message, bot: Bot, db: Database, team: Team, role: str) -> None:
    user = message.from_user
    if user is None:  # pragma: no cover
        return
    await team.refresh(db)
    await _setup_commands(bot, team, only=user.id)
    log.info("в команде новый человек, роль %s (всего %d)", role, len(team.ids()))
    await message.answer(texts.joined(role), reply_markup=team_menu(role))
    others = [uid for uid in team.managers() if uid != user.id]
    await _send_team(bot, db, others, texts.member_joined(user.full_name, role))


async def cmd_owner(message: Message, command: CommandObject, bot: Bot, db: Database, team: Team,
                    cfg: Config, limiter: AttemptLimiter) -> None:
    user = message.from_user
    if not user:
        return
    if team.is_member(user.id):
        await message.answer(texts.OWNER_ALREADY, reply_markup=menu_for(team, user))
        return
    code = re.sub(r"\s+", "", command.args or "")
    if not code:
        await message.answer(texts.OWNER_USAGE)
        return
    if not cfg.owner_code:
        await message.answer(texts.OWNER_NO_CODE)
        return
    if not limiter.allow(user.id):
        await message.answer(texts.CODE_LOCKED)
        return
    if not hmac.compare_digest(code.encode(), cfg.owner_code.encode()) or \
            not await db.claim_owner_code(code, user.id, user.username, user.full_name):
        log.warning("/owner: неверный или уже использованный код")
        await message.answer(texts.CODE_BAD)
        return
    await _after_join(message, bot, db, team, ROLE_MANAGER)


async def cmd_join(message: Message, command: CommandObject, bot: Bot, db: Database, team: Team,
                   limiter: AttemptLimiter) -> None:
    user = message.from_user
    if not user:
        return
    code = re.sub(r"\s+", "", command.args or "")
    if not code:
        await message.answer(texts.JOIN_USAGE)
        return
    if not limiter.allow(user.id):
        await message.answer(texts.CODE_LOCKED)
        return
    if team.is_manager(user.id) and team.managers() == [user.id]:
        # единственный менеджер не может сам себя «понизить» — иначе некому будет приглашать
        await message.answer(texts.JOIN_LAST_MANAGER, reply_markup=menu_for(team, user))
        return
    role = await db.use_invite(code, user.id, user.username, user.full_name) if code.isdigit() else None
    if not role:
        log.warning("/join: неверный, использованный или просроченный код")
        await message.answer(texts.CODE_BAD)
        return
    await _after_join(message, bot, db, team, role)


async def _invite(target: Message, bot: Bot, db: Database, role: str, by: int) -> None:
    code = await db.create_invite(role, by)
    me = await bot.me()
    await target.answer(texts.invite_text(role, code, me.username or ""))


def invite_kb() -> InlineKeyboardMarkup:
    return _inline([[(texts.BTN_INVITE_MANAGER, "inv|manager")], [(texts.BTN_INVITE_SHIPPING, "inv|shipping")]])


async def cmd_invite(message: Message, command: CommandObject, bot: Bot, db: Database) -> None:
    arg = (command.args or "").strip().lower()
    role = {"manager": ROLE_MANAGER, "менеджер": ROLE_MANAGER, "shipping": ROLE_SHIPPING,
            "отгрузка": ROLE_SHIPPING}.get(arg)
    if not role or not message.from_user:
        await message.answer(texts.INVITE_USAGE, reply_markup=invite_kb())
        return
    await _invite(message, bot, db, role, message.from_user.id)


async def cb_invite(cb: CallbackQuery, bot: Bot, db: Database) -> None:
    await cb.answer()
    role = (cb.data or "").split("|", 1)[-1]
    if role in ROLES and isinstance(cb.message, Message):
        await _invite(cb.message, bot, db, role, cb.from_user.id)


def team_kb(team: Team, me: int) -> InlineKeyboardMarkup:
    rows = [[(texts.BTN_INVITE_MANAGER, "inv|manager")], [(texts.BTN_INVITE_SHIPPING, "inv|shipping")]]
    for m in team.sorted_members():
        if m.tg_id != me and not m.static:
            rows.append([(f"Убрать: {m.name or m.username or m.tg_id}"[:60], f"rm|{m.tg_id}")])
    return _inline(rows)


async def cmd_team(message: Message, team: Team) -> None:
    me = message.from_user.id if message.from_user else 0
    await message.answer(texts.team_list(team.sorted_members(), me), reply_markup=team_kb(team, me))


async def _remove_member(bot: Bot, db: Database, team: Team, target: int) -> str:
    member = team.get(target)
    if not member:
        return texts.REMOVE_NOT_FOUND
    if member.static:
        return texts.REMOVE_STATIC
    if member.role == ROLE_MANAGER and len(team.managers()) <= 1:
        return texts.REMOVE_LAST_MANAGER
    await db.remove_member(target)
    await team.refresh(db)
    log.info("человек убран из команды (осталось %d)", len(team.ids()))
    await _setup_commands(bot, team, only=target)
    try:
        await bot.send_message(target, texts.REMOVED_YOU, reply_markup=client_menu())
    except TelegramAPIError:
        pass
    return texts.removed(member.name or member.username)


async def cmd_remove(message: Message, command: CommandObject, bot: Bot, db: Database, team: Team) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer(texts.REMOVE_USAGE)
        return
    await message.answer(await _remove_member(bot, db, team, int(arg)))


async def cb_remove(cb: CallbackQuery, bot: Bot, db: Database, team: Team) -> None:
    await cb.answer()
    if not isinstance(cb.message, Message):
        return
    action, _, arg = (cb.data or "").partition("|")
    if action == "rmn":
        await _show(cb, texts.CANCELLED)
        return
    if not arg.isdigit():
        return
    target = int(arg)
    if action == "rm":
        member = team.get(target)
        if not member:
            await _show(cb, texts.REMOVE_NOT_FOUND)
            return
        await cb.message.answer(texts.remove_confirm(member.name or member.username),
                                reply_markup=_inline([[(texts.BTN_REMOVE_YES, f"rmy|{target}"),
                                                       (texts.BTN_CANCEL, "rmn")]]))
        return
    await _show(cb, await _remove_member(bot, db, team, target))


def notify_kb(current: str) -> InlineKeyboardMarkup:
    mark = "• "
    return _inline([
        [((mark if current == NOTIFY_ALL else "") + texts.BTN_NOTIFY_ALL, "ntf|all")],
        [((mark if current == NOTIFY_ORDERS else "") + texts.BTN_NOTIFY_ORDERS, "ntf|orders")],
    ])


async def _set_notify(db: Database, team: Team, user_id: int, mode: str) -> str:
    await db.set_notify(user_id, mode)
    await team.refresh(db)
    return texts.notify_set(mode)


async def cmd_notify(message: Message, command: CommandObject, db: Database, team: Team) -> None:
    member = team.get(message.from_user.id) if message.from_user else None
    if not member:
        return
    arg = (command.args or "").strip().lower()
    if arg in (NOTIFY_ALL, NOTIFY_ORDERS):
        await message.answer(await _set_notify(db, team, member.tg_id, arg))
        return
    if arg:
        await message.answer(texts.NOTIFY_USAGE)
    await message.answer(texts.notify_current(member.notify), reply_markup=notify_kb(member.notify))


async def btn_notify(message: Message, team: Team) -> None:
    member = team.get(message.from_user.id) if message.from_user else None
    if member:
        await message.answer(texts.notify_current(member.notify), reply_markup=notify_kb(member.notify))


async def cb_notify(cb: CallbackQuery, db: Database, team: Team) -> None:
    await cb.answer()
    mode = (cb.data or "").split("|", 1)[-1]
    if mode in (NOTIFY_ALL, NOTIFY_ORDERS) and cb.from_user:
        await _show(cb, await _set_notify(db, team, cb.from_user.id, mode))


# =========================================================================== заявки, переписка, ответы
async def cmd_leads(message: Message, db: Database) -> None:
    leads = await db.last_leads(10)
    if not leads:
        await message.answer(texts.LEADS_EMPTY)
        return
    kb = InlineKeyboardBuilder()
    for lead in leads:
        kb.button(text=f"№{lead.id}", callback_data=f"ld|{lead.id}")
    kb.adjust(5)
    await message.answer(texts.leads_list(leads), reply_markup=kb.as_markup())


async def _send_lead_card(chat: Message, db: Database, team: Team, uid: int, lead: Lead) -> None:
    sent = await chat.answer(texts.lead_card(lead, title="Заявка"), reply_markup=lead_kb(lead, team.role(uid)))
    await db.add_relay(chat.chat.id, sent.message_id, lead.tg_id, lead.id)


async def cmd_lead(message: Message, command: CommandObject, db: Database, team: Team) -> None:
    arg = (command.args or "").strip().lstrip("#№")
    if not arg.isdigit():
        await message.answer(texts.LEAD_USAGE)
        return
    lead = await db.get_lead(int(arg))
    if not lead:
        await message.answer(texts.NO_SUCH_LEAD)
    elif message.from_user:
        await _send_lead_card(message, db, team, message.from_user.id, lead)


async def cb_open_lead(cb: CallbackQuery, db: Database, team: Team) -> None:
    await cb.answer()
    arg = (cb.data or "").split("|", 1)[-1]
    lead = await db.get_lead(int(arg)) if arg.isdigit() else None
    if not isinstance(cb.message, Message):
        return
    if not lead:
        await cb.message.answer(texts.NO_SUCH_LEAD)
        return
    await _send_lead_card(cb.message, db, team, cb.from_user.id, lead)


async def _send_history(chat: Message, db: Database, tg_id: int) -> None:
    name, username = await db.client_name(tg_id)
    parts = texts.history(name, username, await db.client_leads(tg_id), await db.history(tg_id))
    for part in parts:
        sent = await chat.answer(part)
        await db.add_relay(chat.chat.id, sent.message_id, tg_id)


async def cmd_history(message: Message, command: CommandObject, db: Database) -> None:
    arg = (command.args or "").strip()
    tg_id, _ = await _resolve_client(arg, db) if arg else (None, None)
    if tg_id is None:
        await message.answer(texts.NO_SUCH_LEAD if arg else texts.HISTORY_USAGE)
        return
    await _send_history(message, db, tg_id)


async def cb_history(cb: CallbackQuery, db: Database) -> None:
    await cb.answer()
    arg = (cb.data or "").split("|", 1)[-1]
    if arg.isdigit() and isinstance(cb.message, Message):
        await _send_history(cb.message, db, int(arg))


async def _send_to_client(staff_msg: Message, bot: Bot, db: Database, team: Team, client_id: int,
                          text: str | None = None) -> None:
    staff = staff_msg.from_user
    if text is None and staff_msg.text is not None:
        text = staff_msg.text
    try:
        if text is not None:
            await bot.send_message(client_id, texts.manager_reply(text))
            kind, body = "text", text
        else:
            await bot.copy_message(client_id, from_chat_id=staff_msg.chat.id, message_id=staff_msg.message_id)
            ct = _content_type(staff_msg)
            kind, body = _KIND_NAMES.get(ct, ct), staff_msg.caption or ""
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        log.warning("ответ клиенту не доставлен: %s", type(exc).__name__)
        await staff_msg.reply(texts.SEND_FAILED)
        return
    name, username = await db.client_name(client_id)
    staff_name = (team.name(staff.id) or staff.first_name) if staff else ""
    await db.add_message(tg_id=client_id, username=username, name=name, direction="out", kind=kind, text=body,
                         admin_id=staff.id if staff else None, admin_name=staff_name)
    await staff_msg.reply(texts.SENT_TO_CLIENT)


async def staff_reply(message: Message, bot: Bot, db: Database, team: Team) -> None:
    replied = message.reply_to_message
    target = await db.relay_target(message.chat.id, replied.message_id) if replied else None
    if target is None:
        await message.answer(texts.NOT_REPLY_TARGET)
        return
    await _send_to_client(message, bot, db, team, target)


async def cmd_reply(message: Message, command: CommandObject, bot: Bot, db: Database, team: Team) -> None:
    m = re.match(r"^\s*(\S+)\s+(.+)$", command.args or "", flags=re.S)
    if not m:
        await message.answer(texts.REPLY_USAGE)
        return
    tg_id, _ = await _resolve_client(m.group(1), db)
    if tg_id is None:
        await message.answer(texts.NO_SUCH_LEAD)
        return
    await _send_to_client(message, bot, db, team, tg_id, text=m.group(2).strip())


async def staff_free(message: Message) -> None:
    await message.answer(texts.TEAM_FREE_TEXT)


# =========================================================================== отгрузка
async def cb_ship_start(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    await cb.answer()
    arg = (cb.data or "").split("|", 1)[-1]
    lead = await db.get_lead(int(arg)) if arg.isdigit() else None
    if not isinstance(cb.message, Message):
        return
    if not lead:
        await cb.message.answer(texts.SHIP_LEAD_MISSING)
        return
    default_items = lead.calc or lead.comment
    default_phone = parse_phone(lead.contact) or ""
    await state.clear()
    await state.set_state(ShipForm.items)
    await state.update_data(lead_id=lead.id, default_items=default_items, default_phone=default_phone,
                            old_status=lead.status if lead.status != "new" else "")
    kb = ship_step_kb(texts.BTN_AS_IN_LEAD) if default_items else ship_step_kb()
    await cb.message.answer(texts.ship_ask_items(lead.id, default_items), reply_markup=kb)


def _ship_text(message: Message, limit: int) -> str | None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def ship_items(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.text == texts.BTN_AS_IN_LEAD and data.get("default_items"):
        items = data["default_items"]
    else:
        items = _ship_text(message, 1000)
    if not items:
        await message.answer(texts.SHIP_BAD_TEXT)
        return
    await state.update_data(items=items)
    await state.set_state(ShipForm.address)
    await message.answer(texts.SHIP_ASK_ADDRESS, reply_markup=ship_step_kb(texts.BTN_PICKUP))


async def ship_address(message: Message, state: FSMContext) -> None:
    address = "Самовывоз" if message.text == texts.BTN_PICKUP else _ship_text(message, 300)
    if not address:
        await message.answer(texts.SHIP_BAD_TEXT)
        return
    await state.update_data(address=address)
    await state.set_state(ShipForm.when)
    await message.answer(texts.SHIP_ASK_WHEN, reply_markup=ship_step_kb(texts.BTN_TODAY, texts.BTN_TOMORROW))


async def ship_when(message: Message, state: FSMContext) -> None:
    today = now_local()
    if message.text == texts.BTN_TODAY:
        when = f"сегодня, {today.strftime('%d.%m')}"
    elif message.text == texts.BTN_TOMORROW:
        when = f"завтра, {(today + timedelta(days=1)).strftime('%d.%m')}"
    else:
        when = _ship_text(message, 100)
    if not when:
        await message.answer(texts.SHIP_BAD_TEXT)
        return
    await state.update_data(when=when)
    await state.set_state(ShipForm.phone)
    default_phone = (await state.get_data()).get("default_phone", "")
    kb = ship_step_kb(texts.BTN_AS_IN_LEAD) if default_phone else ship_step_kb()
    await message.answer(texts.ship_ask_phone(default_phone), reply_markup=kb)


async def ship_phone(message: Message, state: FSMContext, team: Team) -> None:
    data = await state.get_data()
    if message.text == texts.BTN_AS_IN_LEAD and data.get("default_phone"):
        phone: str | None = data["default_phone"]
    elif message.contact and message.contact.phone_number:
        phone = "+" + re.sub(r"\D", "", message.contact.phone_number)
    else:
        phone = parse_phone(message.text or "")
    if not phone:
        await message.answer(texts.SHIP_BAD_PHONE)
        return
    await state.update_data(phone=phone)
    await state.set_state(ShipForm.confirm)
    await message.answer(texts.SHIP_CHECK, reply_markup=menu_for(team, message.from_user))
    await message.answer(texts.ship_review(data["lead_id"], data["items"], data["address"], data["when"], phone,
                                           data.get("old_status", "")),
                         reply_markup=_inline([[(texts.BTN_TO_SHIPPING, "shc|yes"), (texts.BTN_CANCEL, "shc|no")]]))


async def ship_confirm_text(message: Message) -> None:
    await message.answer(f"Нажмите «{texts.BTN_TO_SHIPPING}» или «{texts.BTN_CANCEL}» под сообщением выше.")


async def cb_ship_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot, db: Database, team: Team) -> None:
    await cb.answer()
    msg = cb.message if isinstance(cb.message, Message) else None
    if msg:
        await _drop_buttons(msg)
    if await state.get_state() != ShipForm.confirm.state:
        if msg:
            await msg.answer(texts.SHIP_EXPIRED)
        return
    data = await state.get_data()
    await state.clear()
    if (cb.data or "").endswith("|no"):
        if msg:
            await msg.answer(texts.CANCELLED, reply_markup=menu_for(team, cb.from_user))
        return
    actor = cb.from_user
    actor_name = team.name(actor.id) or actor.full_name
    ship = await db.save_shipment(int(data["lead_id"]), items=data["items"], address=data["address"],
                                  when_text=data["when"], phone=data["phone"], by_id=actor.id, by_name=actor_name)
    if ship is None:
        if msg:
            await msg.answer(texts.SHIP_LEAD_MISSING)
        return
    log.info("заявка №%d передана на отгрузку", ship.lead_id)
    card = texts.shipment_card(ship)
    receivers = await _send_team(bot, db, [u for u in team.shipping() if u != actor.id], card,
                                 markup=lambda uid: ship_kb(ship, team.is_manager(uid)),
                                 client_id=ship.client_tg_id, lead_id=ship.lead_id)
    if msg:
        sent = await msg.answer(card, reply_markup=ship_kb(ship, True))
        await db.add_relay(msg.chat.id, sent.message_id, ship.client_tg_id, ship.lead_id)
        await msg.answer(texts.ship_created(ship.lead_id, [team.name(u) or "сотрудник" for u in receivers]),
                         reply_markup=menu_for(team, actor))
    others = [u for u in team.managers() if u != actor.id]
    await _send_team(bot, db, others, texts.ship_status_note(ship.lead_id, "created", actor_name, ship.client_name))


async def cb_ship_action(cb: CallbackQuery, bot: Bot, db: Database, team: Team) -> None:
    parts = (cb.data or "").split("|")
    if len(parts) != 3 or parts[1] not in ("acc", "done", "cancel") or not parts[2].isdigit():
        await cb.answer()
        return
    action = {"acc": "accept", "done": "done", "cancel": "cancel"}[parts[1]]
    actor = cb.from_user
    if action == "cancel" and not team.is_manager(actor.id):
        await cb.answer(texts.ONLY_MANAGER, show_alert=True)
        return
    actor_name = team.name(actor.id) or actor.full_name
    result, ship = await db.change_shipment(int(parts[2]), action, actor.id, actor_name)
    await cb.answer(texts.SHIP_TOAST.get(result, ""))
    if ship and isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(texts.shipment_card(ship), reply_markup=ship_kb(ship, team.is_manager(actor.id)))
        except TelegramBadRequest:
            pass
    if result != "ok" or not ship:
        return
    log.info("отгрузка №%d: %s", ship.lead_id, action)
    note = texts.ship_status_note(ship.lead_id, action, actor_name, ship.client_name)
    receivers = set(team.managers())
    if action == "cancel":
        receivers |= set(team.shipping())
    await _send_team(bot, db, sorted(receivers - {actor.id}), note)


async def cmd_orders(message: Message, db: Database, team: Team) -> None:
    ships = await db.open_shipments(10)
    if not ships:
        await message.answer(texts.ORDERS_EMPTY)
        return
    await message.answer(texts.orders_head(len(ships)))
    is_manager = bool(message.from_user and team.is_manager(message.from_user.id))
    for ship in ships:
        sent = await message.answer(texts.shipment_card(ship), reply_markup=ship_kb(ship, is_manager))
        await db.add_relay(message.chat.id, sent.message_id, ship.client_tg_id, ship.lead_id)


async def cmd_stats(message: Message, db: Database, store: CatalogStore) -> None:
    stats = await db.stats()
    catalog = store.get()
    when = time.strftime("%d.%m %H:%M", time.localtime(catalog.loaded_at)) if catalog else "—"
    await message.answer(texts.stats(stats, len(catalog) if catalog else 0,
                                     catalog.source if catalog else "нет", when, store.last_error))


async def cmd_reload(message: Message, store: CatalogStore) -> None:
    catalog = await store.reload()
    await message.answer(texts.reload_result(len(catalog) if catalog else 0,
                                             catalog.source if catalog else "", store.last_error))


async def cmd_only_manager(message: Message) -> None:
    await message.answer(texts.ONLY_MANAGER)


async def cb_stale(cb: CallbackQuery) -> None:
    await cb.answer(texts.BUTTON_STALE)


async def on_error(event: ErrorEvent, bot: Bot) -> bool:
    log.error("ошибка при обработке обновления: %s", type(event.exception).__name__, exc_info=event.exception)
    update = event.update
    chat_id = None
    if update.message and update.message.chat.type == ChatType.PRIVATE:
        chat_id = update.message.chat.id
    elif update.callback_query and update.callback_query.from_user:
        chat_id = update.callback_query.from_user.id
    if chat_id is not None:
        try:
            await bot.send_message(chat_id, texts.ERROR_GENERIC)
        except TelegramAPIError:
            pass
    return True


# =========================================================================== сборка
def build_router() -> Router:
    r = Router(name="prostranstvo")
    r.message.filter(F.chat.type == ChatType.PRIVATE)
    r.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
    staff, manager = IsTeam(), IsManager()
    m, c = r.message.register, r.callback_query.register

    # Команды и кнопки меню работают в любом состоянии (прерывают начатый сценарий).
    m(cmd_start, CommandStart())
    m(cmd_help, Command("help"))
    m(cmd_help, staff, F.text == texts.BTN_T_HELP)
    m(cmd_cancel, Command("cancel"))
    m(cmd_cancel, F.text == texts.BTN_CANCEL)
    m(cmd_delete_me, Command("delete_me"))
    m(cmd_owner, Command("owner"))
    m(cmd_join, Command("join"))

    # команда магазина
    m(cmd_leads, staff, Command("leads"))
    m(cmd_leads, staff, F.text == texts.BTN_T_LEADS)
    m(cmd_lead, staff, Command("lead"), F.text.regexp(r"^/lead(@\w+)?\s+\S"))
    m(cmd_orders, staff, Command("orders"))
    m(cmd_orders, staff, F.text == texts.BTN_T_ORDERS)
    m(cmd_history, staff, Command("history"))
    m(cmd_reply, staff, Command("reply"))
    m(cmd_notify, staff, Command("notify"))
    m(btn_notify, staff, F.text == texts.BTN_T_NOTIFY)
    m(cmd_team, manager, Command("team"))
    m(cmd_team, manager, F.text == texts.BTN_T_TEAM)
    m(cmd_invite, manager, Command("invite"))
    m(cmd_remove, manager, Command("remove"))
    m(cmd_stats, manager, Command("stats"))
    m(cmd_stats, manager, F.text == texts.BTN_T_STATS)
    m(cmd_reload, manager, Command("reload"))
    m(cmd_only_manager, staff, Command("team", "invite", "remove", "stats", "reload"))

    # меню клиента
    m(open_calc, F.text == texts.BTN_CALC)
    m(open_calc, Command("calc"))
    m(open_catalog, F.text == texts.BTN_CATALOG)
    m(open_catalog, Command("catalog"))
    m(open_lead, F.text == texts.BTN_LEAD)
    m(open_lead, Command("lead"))
    m(open_manager, F.text == texts.BTN_MANAGER)
    m(open_manager, Command("manager"))

    # оформление отгрузки (менеджер)
    m(ship_items, manager, StateFilter(ShipForm.items))
    m(ship_address, manager, StateFilter(ShipForm.address))
    m(ship_when, manager, StateFilter(ShipForm.when))
    m(ship_phone, manager, StateFilter(ShipForm.phone))
    m(ship_confirm_text, manager, StateFilter(ShipForm.confirm))

    # ответ сотрудника клиенту: «Ответить» на пересланное сообщение, заявку или переписку
    m(staff_reply, staff, F.reply_to_message)

    # расчёт
    m(calc_article_text, StateFilter(CalcForm.article), F.text)
    m(calc_width, StateFilter(CalcForm.width), F.text)
    m(calc_height, StateFilter(CalcForm.height), F.text)
    m(calc_length, StateFilter(CalcForm.length), F.text)
    m(calc_bad_input, StateFilter(CalcForm.width, CalcForm.height, CalcForm.length))

    # заявка
    m(lead_name, StateFilter(LeadForm.name), F.text)
    m(lead_contact, StateFilter(LeadForm.contact))
    m(lead_comment, StateFilter(LeadForm.comment))
    m(lead_consent_text, StateFilter(LeadForm.consent))
    m(unexpected_in_lead, StateFilter(LeadForm.name))

    # всё остальное: от сотрудника — подсказка, от клиента — команде магазина
    m(staff_free, staff, ~F.text.startswith("/"))
    m(client_message)

    # кнопки под сообщениями
    c(cb_catalog_group, F.data.startswith("kg|"))
    c(cb_catalog_groups, F.data == "kb")
    c(cb_calc_group, F.data.startswith("cg|") | F.data.startswith("cgn|"))
    c(cb_calc_page, F.data.startswith("cp|"))
    c(cb_calc_back, F.data == "cb")
    c(cb_calc_article, F.data.startswith("ca|"))
    c(cb_calc_again, F.data == "cn")
    c(cb_send_calc, F.data.startswith("ls|") | F.data.startswith("ll|"))
    c(cb_lead_consent, F.data.in_({"lead|yes", "lead|no"}))
    c(cb_delete, F.data.in_({"del|yes", "del|no"}))
    c(cb_open_lead, staff, F.data.startswith("ld|"))
    c(cb_history, staff, F.data.startswith("hist|"))
    c(cb_notify, staff, F.data.startswith("ntf|"))
    c(cb_ship_action, staff, F.data.startswith("sh|"))
    c(cb_ship_start, manager, F.data.startswith("shp|"))
    c(cb_ship_confirm, manager, F.data.in_({"shc|yes", "shc|no"}))
    c(cb_invite, manager, F.data.startswith("inv|"))
    c(cb_remove, manager, F.data.startswith("rm|") | F.data.startswith("rmy|") | (F.data == "rmn"))
    c(cb_stale)

    r.errors.register(on_error)
    return r


def build_dispatcher(cfg: Config, db: Database, store: CatalogStore, team: Team) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage(), cfg=cfg, db=db, store=store, team=team,
                    limiter=AttemptLimiter(), rt=Runtime())
    dp.include_router(build_router())
    return dp


def make_bot(token: str, **kwargs: Any) -> Bot:
    return Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
               **kwargs)


async def run() -> int:
    try:
        cfg = load_config()
    except ConfigError as exc:
        logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
        log.error("ошибка настроек: %s", exc)
        await asyncio.sleep(30)  # не перезапускаться слишком часто
        return 2
    level = logging.getLevelName(cfg.log_level)
    logging.basicConfig(level=level if isinstance(level, int) else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)  # без строки на каждое сообщение

    db = Database(cfg.db_path)
    await db.init()
    store = CatalogStore(cfg.catalog_file, cfg.catalog_url, cfg.catalog_cache, cfg.catalog_refresh_min)
    if not await store.reload():
        log.error("каталог пока не загружен — расчёт и цены заработают после обновления")
    team = Team(cfg.admin_ids)
    await team.refresh(db)

    bot = make_bot(cfg.bot_token)
    refresher: asyncio.Task | None = None
    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            log.error("Telegram не принял токен (BOT_TOKEN в /etc/prostranstvo/bot.env). "
                      "Запустите установщик с новым токеном.")
            await asyncio.sleep(60)
            return 3
        except TelegramNetworkError as exc:
            log.error("нет связи с Telegram (%s) — повтор через 30 секунд", type(exc).__name__)
            await asyncio.sleep(30)
            return 4
        log.info("бот @%s запущен; каталог: %d позиций; в команде: %d (менеджеров %d, отгрузка %d)",
                 me.username, len(store.get() or ()), len(team.ids()), len(team.managers()), len(team.shipping()))
        if not team.managers():
            log.warning("менеджера ещё нет: отправьте боту /owner КОД (код показал установщик)")
        await bot.delete_webhook(drop_pending_updates=False)
        await _setup_commands(bot, team)
        dp = build_dispatcher(cfg, db, store, team)
        refresher = asyncio.create_task(store.refresh_forever())
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if refresher:
            refresher.cancel()
        db.close()
        await bot.session.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
