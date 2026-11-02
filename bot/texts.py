"""Все тексты бота «Пространство» — в одном месте, чтобы их было легко править.

Разметка — HTML (её понимают и Telegram, и MAX: <b>, <i>, <a>, <code>).
Всё, что пришло от людей (имена, комментарии, ответы), обязательно пропускать через esc().

pii=False — текст для чата сотрудника в Telegram, пока TELEGRAM_COLLECT_CONTACTS=0:
имена, телефоны, адреса и тексты клиентов в нём не показываются (смотреть — в MAX).
"""

from __future__ import annotations

import html
from decimal import Decimal

from calc import MAX_LINEAR_M, MAX_WALL_HEIGHT_M, MAX_WALL_WIDTH_M, AreaResult, InputError, LinearResult
from catalog import Product, group_title

NBSP = " "
SHOP = "«Пространство»"
CHANNEL_NAMES = {"tg": "Telegram", "max": "MAX"}
HIDDEN = "скрыто — смотрите в MAX"


def esc(text: object) -> str:
    return html.escape(str(text or ""), quote=False)


def attr(text: object) -> str:
    return html.escape(str(text or ""), quote=True)


def ch_name(channel: str) -> str:
    return CHANNEL_NAMES.get(channel, channel)


def rub(amount: int) -> str:
    """18050 → «18 050 ₽» (неразрывные пробелы)."""
    return f"{amount:,}".replace(",", NBSP) + NBSP + "₽"


def meters(mm: int | Decimal) -> str:
    """2700 → «2,7»; 3000 → «3»; 3255 → «3,26»."""
    value = (Decimal(mm) / Decimal(1000)).quantize(Decimal("0.01"))
    text = format(value.normalize(), "f")
    return text.replace(".", ",")


def area(value: Decimal) -> str:
    return format(value.normalize(), "f").replace(".", ",")


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def boxes_word(n: int) -> str:
    return plural(n, "коробка", "коробки", "коробок")


# =========================================================================== кнопки
BTN_CALC = "Рассчитать стену"
BTN_CATALOG = "Каталог и цены"
BTN_LEAD = "Оставить заявку"
BTN_MANAGER = "Связаться с менеджером"
MENU_BUTTONS = (BTN_CALC, BTN_CATALOG, BTN_LEAD, BTN_MANAGER)

BTN_CANCEL = "Отмена"
BTN_SKIP = "Пропустить"
BTN_SEND_PHONE = "Отправить номер"
BTN_AGREE = "Согласен"
BTN_SEND_CALC = "Отправить расчёт менеджеру"
BTN_CALC_AGAIN = "Посчитать другой"
BTN_TO_GROUPS = "« К группам"
BTN_PREV = "‹ Назад"
BTN_NEXT = "Далее ›"
BTN_CALC_GROUP = "Рассчитать"
BTN_OTHER_GROUPS = "Другие группы"
BTN_SITE = "Открыть сайт"
BTN_DELETE_YES = "Да, удалить"
BTN_LEAD_SITE = "Заявка на сайте"
BTN_OPEN_MAX = "Открыть бота в MAX"
BTN_CONTINUE_MAX = "Продолжить в MAX"


def btn_write_here(channel: str) -> str:
    return f"Напишите мне в {ch_name(channel)}"


# =========================================================================== общее
def welcome(site_url: str, collect: bool = True) -> str:
    lead = "менеджер свяжется с вами" if collect else "на сайте или в нашем боте в MAX"
    text = (
        f"Здравствуйте! Это магазин {SHOP} — декор для стен ARTDEC в Санкт-Петербурге: "
        "реечные панели под покраску, панели под дерево и бетон, молдинги, плинтусы, карнизы и уголки.\n\n"
        "Здесь можно:\n"
        f"• <b>{BTN_CALC}</b> — сколько панелей или погонажа нужно и сколько это стоит;\n"
        f"• <b>{BTN_CATALOG}</b> — все артикулы с ценами за штуку и за коробку;\n"
        f"• <b>{BTN_LEAD}</b> — {lead};\n"
        f"• <b>{BTN_MANAGER}</b> — или просто напишите вопрос в этот чат.\n\n"
        "Продаём поштучно и коробками."
    )
    if site_url:
        text += f"\nСайт: {esc(site_url)}"
    return text


def help_client(site_url: str) -> str:
    text = (
        "Выберите нужное кнопками:\n"
        f"• {BTN_CALC} — расчёт количества и стоимости;\n"
        f"• {BTN_CATALOG};\n"
        f"• {BTN_LEAD};\n"
        f"• {BTN_MANAGER} — или просто напишите сообщение.\n\n"
        "/cancel — отменить текущее действие\n"
        "/delete_me — удалить мои данные из базы магазина"
    )
    if site_url:
        text += f"\n\nСайт: {esc(site_url)}"
    return text


MENU_HINT = "Выберите действие кнопками или напишите вопрос — его получит менеджер."
CANCELLED = "Отменено. Чем ещё помочь?"
CATALOG_UNAVAILABLE = (
    "Каталог сейчас обновляется, попробуйте через пару минут. "
    "Или напишите вопрос сюда — менеджер ответит."
)
ERROR_GENERIC = "Что-то пошло не так. Попробуйте ещё раз или напишите вопрос — менеджер ответит."

# =========================================================================== каталог
CATALOG_CHOOSE_GROUP = "Каталог ARTDEC. Выберите группу:"


def catalog_group(group: str, products: list[Product], site_url: str) -> list[str]:
    """Список артикулов группы с ценами — разбит на части по ≤ 3800 символов."""
    head = f"<b>{esc(group_title(group))}</b> — цены за штуку и за коробку:\n"
    lines: list[str] = []
    for p in products:
        desc = f" — {esc(p.short_desc)}" if p.short_desc else ""
        box = f" · коробка {p.per_box}{NBSP}шт = {rub(p.box_price)}" if p.per_box else ""
        lines.append(f"<b>{esc(p.article)}</b>{desc}, {esc(p.size_text)}\n    {rub(p.price)}/шт{box}")
    tail = "\nЦены предварительные — точную сумму и наличие подтвердит менеджер."
    if site_url:
        tail += f"\nФото и 3D-примеры: {esc(site_url)}"
    parts: list[str] = []
    chunk = head
    for line in lines:
        if len(chunk) + len(line) + 2 > 3800:
            parts.append(chunk.rstrip())
            chunk = ""
        chunk += line + "\n"
    chunk += tail
    parts.append(chunk.strip())
    return parts


# =========================================================================== расчёт
CALC_CHOOSE_GROUP = (
    "Что считаем? Выберите группу товаров — или сразу напишите артикул, например <b>A907</b>."
)


def calc_choose_article(group: str, page_items: list[Product], page: int, pages: int) -> str:
    title = esc(group_title(group))
    lines = []
    for p in page_items:
        desc = f" — {esc(p.short_desc)}" if p.short_desc else ""
        lines.append(f"<b>{esc(p.article)}</b>{desc}, {esc(p.size_text)}, {rub(p.price)}/шт")
    pages_text = f" (стр. {page + 1} из {pages})" if pages > 1 else ""
    return (
        f"<b>{title}</b>{pages_text}\n" + "\n".join(lines)
        + "\n\nВыберите артикул кнопкой или напишите его."
    )


def article_not_found(query: str, suggestions: list[Product]) -> str:
    text = f"Не нашёл артикул «{esc(query[:40])}»."
    if suggestions:
        text += " Может быть: " + ", ".join(f"<b>{esc(p.article)}</b>" for p in suggestions) + "?"
    return text + "\nВыберите группу и артикул кнопками или напишите артикул точно, например A907."


def product_card(p: Product) -> str:
    desc = f"\n{esc(p.desc)}" if p.desc else ""
    box = f", в коробке {p.per_box}{NBSP}шт ({rub(p.box_price)})" if p.per_box else ""
    return f"<b>{esc(p.name)}</b>{desc}\nЦена: {rub(p.price)}/шт{box}"


def ask_width(p: Product) -> str:
    return (
        product_card(p) + "\n\n"
        f"Панели ставятся вертикально, ширина панели {p.width}{NBSP}мм, длина {meters(p.length)}{NBSP}м.\n"
        "Введите <b>ширину стены</b> в метрах, например <b>3,2</b> (можно «320 см»).\n"
        "Можно сразу ширину и высоту: <b>3,2 x 2,7</b>"
    )


def ask_height(width_mm: int) -> str:
    return (
        f"Ширина: {meters(width_mm)}{NBSP}м.\n"
        "Теперь <b>высоту стены</b> в метрах, например <b>2,7</b> (можно «270 см»)."
    )


_LINEAR_HINT = {
    "plinth": "периметр комнаты без дверных проёмов",
    "cornice": "периметр потолка",
    "mold": "общую длину всех молдингов (рамок, полос)",
    "corner": "общую длину всех углов",
}


def ask_length(p: Product) -> str:
    hint = _LINEAR_HINT.get(p.kind, "общую длину")
    return (
        product_card(p) + "\n\n"
        f"Длина планки {meters(p.length)}{NBSP}м.\n"
        f"Введите <b>длину в метрах</b> — {hint}. Например <b>15</b> или <b>15,5</b>."
    )


def input_error(err: InputError, what: str) -> str:
    """what: 'width' | 'height' | 'length'."""
    examples = {"width": "3,2", "height": "2,7", "length": "15,5"}
    limits = {"width": MAX_WALL_WIDTH_M, "height": MAX_WALL_HEIGHT_M, "length": MAX_LINEAR_M}
    example = examples.get(what, "3,2")
    if err.code == "too_big":
        return (f"Слишком большое значение — до {limits.get(what, err.max_m)}{NBSP}м. "
                f"Введите в метрах, например <b>{example}</b>. Для больших объектов — оставьте заявку.")
    if err.code in ("zero", "too_small"):
        return f"Значение слишком маленькое. Введите в метрах, например <b>{example}</b>."
    return f"Не понял число. Введите в метрах, например <b>{example}</b> (можно «320 см» или «3200 мм»)."


def _boxes_line(pieces: int, per_box: int, boxes: int, rest: int) -> str:
    if per_box <= 0:
        return f"<b>Итого: {pieces}{NBSP}шт</b>"
    if boxes == 0:
        return f"<b>Итого: {pieces}{NBSP}шт</b> — поштучно (в коробке {per_box}{NBSP}шт)"
    box_part = f"{boxes}{NBSP}{boxes_word(boxes)} по {per_box}{NBSP}шт"
    if rest == 0:
        return f"<b>Итого: {pieces}{NBSP}шт</b> = {box_part} ровно"
    return f"<b>Итого: {pieces}{NBSP}шт</b> = {box_part} + {rest}{NBSP}шт поштучно"


PRICE_NOTE = "Цены предварительные, точную сумму подтвердит менеджер."


def calc_result_area(p: Product, r: AreaResult) -> str:
    rows = "1 по высоте" if r.rows == 1 else f"{r.rows} по высоте (стена выше панели — со стыком)"
    lines = [
        f"<b>Расчёт: {esc(p.name)}</b>",
        f"Стена {meters(r.width_mm)} × {meters(r.height_mm)}{NBSP}м = {area(r.area_m2)}{NBSP}м²",
        f"Панель {p.width}×{p.length}{NBSP}мм, вертикально: {r.columns} в ряд × {rows} = {r.base_pieces}{NBSP}шт",
        f"Запас {r.reserve_percent}% на подрезку: +{r.reserve_pieces}{NBSP}шт",
        _boxes_line(r.pieces, r.per_box, r.boxes, r.rest),
        f"Ориентировочно: {r.pieces} × {rub(r.price)} = <b>{rub(r.total_price)}</b>",
        "",
        PRICE_NOTE,
    ]
    return "\n".join(lines)


def calc_result_linear(p: Product, r: LinearResult) -> str:
    lines = [
        f"<b>Расчёт: {esc(p.name)}</b>",
        f"Длина {meters(r.length_mm)}{NBSP}м + запас {r.reserve_percent}% = {meters(r.length_with_reserve_mm)}{NBSP}м",
        f"Планка {meters(r.piece_length_mm)}{NBSP}м: {r.pieces}{NBSP}шт ({meters(r.bought_length_mm)}{NBSP}м)",
        _boxes_line(r.pieces, r.per_box, r.boxes, r.rest),
        f"Ориентировочно: {r.pieces} × {rub(r.price)} = <b>{rub(r.total_price)}</b>",
        "",
        PRICE_NOTE,
    ]
    return "\n".join(lines)


def calc_summary(p: Product, r: AreaResult | LinearResult) -> str:
    """Коротко для заявки и карточки админу."""
    if isinstance(r, AreaResult):
        what = f"стена {meters(r.width_mm)} × {meters(r.height_mm)} м ({area(r.area_m2)} м²)"
    else:
        what = f"длина {meters(r.length_mm)} м"
    if r.per_box and r.boxes:
        pack = f"{r.boxes} кор. по {r.per_box} шт" + (f" + {r.rest} шт" if r.rest else "")
    else:
        pack = "поштучно"
    total = f"{r.total_price:,}".replace(",", " ")
    return (f"{p.article} ({p.name}): {what} → {r.pieces} шт с запасом {r.reserve_percent}% "
            f"({pack}), ≈ {total} ₽ по {r.price} ₽/шт")


CALC_EXPIRED = "Этот расчёт устарел — посчитайте ещё раз, пожалуйста."

# =========================================================================== заявка
def lead_ask_name(with_calc: bool) -> str:
    start = "Отправим расчёт менеджеру. " if with_calc else "Оставим заявку — менеджер свяжется с вами. "
    return start + "Как к вам обращаться? Напишите имя."


LEAD_BAD_NAME = "Напишите, пожалуйста, имя текстом (до 60 символов)."


def lead_ask_contact(channel: str) -> str:
    return ("Как с вами связаться? Нажмите «Отправить номер», напишите телефон "
            f"или нажмите «{btn_write_here(channel)}».")


def lead_bad_contact(channel: str) -> str:
    return ("Не похоже на телефон. Напишите номер, например +7 999 123-45-67, "
            f"нажмите «Отправить номер» или «{btn_write_here(channel)}».")


LEAD_ASK_COMMENT = (
    "Комментарий: район или адрес объекта, сроки, что нужно (артикулы, количество, "
    f"нужна ли доставка). Можно нажать «{BTN_SKIP}»."
)
LEAD_BAD_COMMENT = f"Напишите комментарий текстом или нажмите «{BTN_SKIP}»."


def contact_here(channel: str, username: str | None) -> str:
    if username:
        return f"{ch_name(channel)} @{username}"
    return f"{ch_name(channel)} (ответ через этот чат)"


def lead_review(name: str, contact: str, comment: str, calc: str) -> str:
    lines = ["<b>Проверьте заявку:</b>", f"Имя: {esc(name)}", f"Контакт: {esc(contact)}"]
    if comment:
        lines.append(f"Комментарий: {esc(comment)}")
    if calc:
        lines.append(f"Расчёт: {esc(calc)}")
    return "\n".join(lines)


def consent_text(site_url: str, operator_name: str) -> str:
    if site_url:
        consent = f"{site_url}/consent.html"
        privacy = f"{site_url}/privacy.html"
        return (
            f"Нажимая «{BTN_AGREE}», вы даёте "
            f'<a href="{attr(consent)}">согласие на обработку персональных данных</a> '
            "(имя, контакт, комментарий и расчёт) — чтобы ответить на заявку и связаться с вами. "
            f'<a href="{attr(privacy)}">Политика обработки персональных данных</a>.\n'
            "Отозвать согласие можно командой /delete_me."
        )
    who = f"оператору {esc(operator_name)} (магазин {SHOP})" if operator_name else f"магазину {SHOP}"
    return (
        f"Нажимая «{BTN_AGREE}», я даю согласие {who} на обработку моих персональных данных: "
        "имени, телефона или ника в мессенджере, комментария и расчёта — чтобы ответить на заявку, "
        "рассчитать количество и стоимость и связаться со мной. Данные хранятся на сервере в России "
        "и не передаются третьим лицам, кроме случаев, предусмотренных законом. Согласие действует "
        "1 год или до отзыва; отозвать его можно командой /delete_me (152-ФЗ, ст. 9)."
    )


def lead_thanks(lead_id: int) -> str:
    return f"Спасибо! Заявка №{lead_id} принята. Менеджер ответит в рабочее время."


LEAD_CANCELLED = "Заявка не отправлена, данные не сохранены."
LEAD_EXPIRED = "Заявка устарела — начните заново кнопкой «Оставить заявку»."


def lead_elsewhere(has_site: bool, has_max: bool, with_calc: bool = False) -> str:
    """Telegram без сбора контактов: куда идти за заявкой."""
    where = []
    if has_site:
        where.append("на сайте")
    if has_max:
        where.append("в нашем боте в MAX")
    start = "Чтобы менеджер связался с вами по этому расчёту, " if with_calc else "Чтобы менеджер связался с вами, "
    if where:
        text = start + "оставьте заявку " + " или ".join(where) + "."
        if has_max and with_calc:
            text += " По кнопке «Продолжить в MAX» расчёт откроется там сразу."
    else:
        text = "Напишите вопрос прямо сюда — менеджер ответит в этом чате."
    return text + "\nЗдесь можно считать стену, смотреть цены и задавать вопросы."


# =========================================================================== менеджер
def manager_prompt(collect: bool = True) -> str:
    text = ("Напишите ваш вопрос прямо сюда — менеджер ответит в этом чате в рабочее время. "
            "Можно прислать фото стены или проекта.")
    if not collect:
        text += f"\nТелефон для связи лучше оставить через «{BTN_LEAD}» — на сайте или в MAX."
    return text


MESSAGE_RECEIVED = "Спасибо, сообщение передано менеджеру. Ответ придёт сюда в рабочее время."


def manager_reply(text: str) -> str:
    return f"<b>Ответ менеджера {SHOP}:</b>\n{esc(text)}"


# =========================================================================== удаление данных
DELETE_CONFIRM = (
    "Удалить ваши заявки и переписку из базы магазина? Это отзыв согласия на обработку "
    "персональных данных. Отменить удаление будет нельзя."
)


def delete_done(leads: int, kept: int, messages: int) -> str:
    if leads == 0 and kept == 0 and messages == 0:
        return "Ваших данных в базе магазина нет."
    text = "Готово: ваши заявки и переписка удалены из базы магазина."
    if kept:
        text += (" Заказы, которые уже переданы на отгрузку, хранятся столько, сколько требует закон "
                 "(договор и бухгалтерия), и затем удаляются.")
    return text


DELETE_CANCELLED = "Ничего не удалено."

# =========================================================================== команда магазина
ROLE_NAMES = {"manager": "менеджер", "shipping": "отгрузка"}
NOTIFY_NAMES = {"all": "все сообщения клиентов, заявки и отгрузки", "orders": "только заявки и отгрузки"}
STATUS_NAMES = {"new": "новая", "confirmed": "подтверждена", "shipping": "на отгрузке", "shipped": "отгружено"}


def role_name(role: str) -> str:
    return ROLE_NAMES.get(role, role)


def status_name(status: str) -> str:
    return STATUS_NAMES.get(status, status)


# кнопки меню сотрудников
BTN_T_LEADS = "Заявки"
BTN_T_ORDERS = "Отгрузки"
BTN_T_TEAM = "Команда"
BTN_T_STATS = "Статистика"
BTN_T_NOTIFY = "Уведомления"
BTN_T_HELP = "Помощь"
BTN_HISTORY = "Переписка"
BTN_TO_SHIPPING = "Передать на отгрузку"
BTN_SHIP_ACCEPT = "Принял"
BTN_SHIP_DONE = "Отгружено"
BTN_SHIP_CANCEL = "Отменить отгрузку"
BTN_AS_IN_LEAD = "Как в заявке"
BTN_PICKUP = "Самовывоз"
BTN_TODAY = "Сегодня"
BTN_TOMORROW = "Завтра"
BTN_INVITE_MANAGER = "Пригласить менеджера"
BTN_INVITE_SHIPPING = "Пригласить на отгрузку"
BTN_NOTIFY_ALL = "Все сообщения клиентов"
BTN_NOTIFY_ORDERS = "Только заявки и отгрузки"
BTN_REMOVE_YES = "Да, убрать"
STAFF_MENU_BUTTONS = (BTN_T_LEADS, BTN_T_ORDERS, BTN_T_TEAM, BTN_T_STATS, BTN_T_NOTIFY, BTN_T_HELP)
# Подписи кнопок шагов: нажатые позже, вне шага, не пересылаются менеджеру как вопрос
STEP_BUTTONS = frozenset({BTN_SKIP, BTN_AS_IN_LEAD, BTN_PICKUP, BTN_TODAY, BTN_TOMORROW,
                          btn_write_here("tg"), btn_write_here("max"), *STAFF_MENU_BUTTONS})


def btn_link(channel: str) -> str:
    return f"Подключить {ch_name(channel)}"


def btn_deliver(channel: str) -> str:
    return f"Присылать в {ch_name(channel)}"


def reply_how(channel: str) -> str:
    if channel == "max":
        return ("Чтобы ответить клиенту, нажмите на его сообщение, выберите «Ответить» и напишите "
                "ответ — бот отправит его клиенту от имени магазина.")
    return ("Чтобы ответить клиенту, смахните его сообщение влево (или нажмите на него → «Ответить») "
            "и напишите ответ — бот отправит его клиенту от имени магазина. Можно фото и файлы.")


def help_manager(channel: str) -> str:
    return (
        "<b>Вы — менеджер магазина.</b>\n"
        "Сюда приходят сообщения клиентов и заявки.\n\n"
        + reply_how(channel) + "\n\n"
        f"<b>{BTN_T_LEADS}</b> — последние заявки. Под заявкой: «{BTN_TO_SHIPPING}» и «{BTN_HISTORY}».\n"
        f"<b>{BTN_T_ORDERS}</b> — что сейчас на отгрузке.\n"
        f"<b>{BTN_T_TEAM}</b> — кто помогает с ботом, пригласить или убрать человека.\n"
        f"<b>{BTN_T_NOTIFY}</b> — что получать и куда: в MAX или в Telegram; подключить второй мессенджер.\n"
        f"<b>{BTN_T_STATS}</b> — сколько заявок и сообщений за сегодня и неделю.\n\n"
        "То же командами: /leads, /orders, /team, /notify, /stats, /history номер_заявки, "
        "/reply номер_заявки текст, /invite shipping, /reload (обновить цены с сайта). "
        "Меню — команда /start."
    )


def help_shipping(channel: str) -> str:
    return (
        "<b>Вы — отгрузка.</b>\n"
        "Сюда приходят новые заявки и карточки «На отгрузку». Под карточкой: "
        f"«{BTN_SHIP_ACCEPT}» — взяли в работу, «{BTN_SHIP_DONE}» — товар отдан.\n\n"
        + reply_how(channel) + "\n\n"
        f"<b>{BTN_T_ORDERS}</b> — что сейчас нужно отгрузить.\n"
        f"<b>{BTN_T_LEADS}</b> — последние заявки, под каждой — «{BTN_HISTORY}» с клиентом.\n"
        f"<b>{BTN_T_NOTIFY}</b> — только заявки и отгрузки (так сейчас) или все сообщения клиентов; "
        "куда присылать; подключить второй мессенджер.\n\n"
        "То же командами: /orders, /leads, /history номер_заявки, /notify all или /notify orders. "
        "Меню — команда /start."
    )


# --- вход в команду
OWNER_USAGE = "Отправьте: /owner КОД — код показал установщик бота."
OWNER_ALREADY = "Вы уже в команде магазина."
CODE_BAD = "Код неверный, уже использован или истёк."
CODE_LOCKED = "Слишком много попыток. Попробуйте через час."
OWNER_NO_CODE = "Код ещё не задан. Попросите запустить установщик бота с параметром --new-code."
JOIN_USAGE = "Отправьте: /join КОД — код даёт менеджер магазина."
JOIN_LAST_MANAGER = "Вы единственный менеджер — код приглашения нужен другому человеку. Перешлите его."


def joined(role: str, channel: str, linked: bool = False) -> str:
    if linked:
        return (f"Готово: {ch_name(channel)} подключён. Куда присылать заявки и сообщения — "
                f"выберите в «{BTN_T_NOTIFY}».")
    if role == "manager":
        return ("Готово, вы менеджер магазина. Сюда будут приходить сообщения клиентов и заявки.\n\n"
                + reply_how(channel) + f"\n\nКнопки: «{BTN_T_LEADS}», «{BTN_T_ORDERS}», «{BTN_T_TEAM}». "
                f"Подсказка — «{BTN_T_HELP}».")
    return ("Готово, вы в команде магазина — роль «отгрузка». Сюда будут приходить новые заявки и "
            f"карточки «На отгрузку».\n\nКнопки: «{BTN_T_ORDERS}», «{BTN_T_LEADS}». "
            f"Подсказка — «{BTN_T_HELP}».")


def member_joined(name: str, role: str, channel: str, linked: bool = False) -> str:
    who = esc(name) or "Сотрудник"
    if linked:
        return f"{who} подключил(а) ещё и {ch_name(channel)}."
    return f"{who} теперь в команде: {role_name(role)} ({ch_name(channel)})."


def invite_text(role: str, code: str, bot_links: dict[str, str]) -> str:
    where = " или ".join(f"{ch_name(ch)}: {esc(link)}" for ch, link in bot_links.items() if link) or "бота магазина"
    return (
        f"Код для входа в команду (роль «{role_name(role)}»): <b>{esc(code)}</b>\n"
        "Действует 24 часа и только один раз.\n\n"
        f"Перешлите человеку: пусть откроет бота ({where}) и отправит сообщение\n"
        f"<code>/join {esc(code)}</code>"
    )


def link_text(channel: str, code: str, bot_link: str) -> str:
    where = f" ({esc(bot_link)})" if bot_link else ""
    return (f"Код, чтобы подключить {ch_name(channel)}: <b>{esc(code)}</b> (24 часа, один раз).\n"
            f"Откройте бота в {ch_name(channel)}{where} и отправьте <code>/join {esc(code)}</code>")


INVITE_USAGE = ("Кого пригласить? Нажмите кнопку ниже или отправьте /invite manager (менеджер) "
                "или /invite shipping (отгрузка).")


def team_list(persons: list, me: int) -> str:
    """persons: [core.Person]"""
    lines = ["<b>Команда магазина</b>"]
    for p in persons:
        who = esc(p.name) or "без имени"
        if p.person_id == me:
            who += " — это вы"
        accounts = ", ".join(ch_name(s.channel) + (f" @{esc(s.username)}" if s.username else "") for s in p.seats)
        extra = " · задан в настройках сервера" if p.static else ""
        lines.append(f"• №{p.person_id} {who}: <b>{role_name(p.role)}</b>; {accounts}; получает "
                     f"{NOTIFY_NAMES.get(p.notify, p.notify)}{extra}")
    lines.append("\nПригласить человека — кнопкой ниже: он получит одноразовый код.")
    return "\n".join(lines)


def remove_confirm(name: str) -> str:
    return f"Убрать {esc(name) or 'этого человека'} из команды? Он перестанет получать заявки и сообщения."


REMOVE_USAGE = "Отправьте: /remove номер — номер есть в списке «Команда» (№…)."
REMOVE_NOT_FOUND = "Такого человека в команде нет."
REMOVE_STATIC = "Этот человек задан в настройках сервера (ADMIN_IDS в bot.env) — убрать можно только там."
REMOVE_LAST_MANAGER = "Нельзя убрать последнего менеджера — сначала пригласите другого."


def removed(name: str) -> str:
    return f"{esc(name) or 'Сотрудник'} больше не в команде."


REMOVED_YOU = "Вас убрали из команды магазина. Теперь бот работает для вас как для клиента."


def notify_current(mode: str, deliver: str, channels: list[str]) -> str:
    text = f"Сейчас вы получаете: <b>{NOTIFY_NAMES.get(mode, mode)}</b>."
    if len(channels) > 1:
        text += f"\nПодключены: {', '.join(ch_name(c) for c in channels)}; присылаю в <b>{ch_name(deliver)}</b>."
    return text + "\nЧто получать?"


def notify_set(mode: str) -> str:
    return f"Готово. Теперь вы получаете: {NOTIFY_NAMES.get(mode, mode)}."


def deliver_set(channel: str) -> str:
    return f"Готово. Заявки и сообщения буду присылать в {ch_name(channel)}."


NOTIFY_USAGE = "Отправьте /notify all (все сообщения клиентов) или /notify orders (только заявки и отгрузки)."
ONLY_MANAGER = "Это может сделать только менеджер."

# --- ответы клиентам
NOT_REPLY_TARGET = ("Не понял, кому ответить. Ответьте на сообщение клиента, его заявку или "
                    "«Переписку» и напишите текст.")
TEAM_FREE_TEXT = ("Это сообщение никуда не отправлено. Чтобы ответить клиенту, ответьте на его "
                  f"сообщение (нажмите на него → «Ответить»). Подсказка — «{BTN_T_HELP}».")
SENT_TO_CLIENT = "Отправлено клиенту."
SEND_FAILED = "Не удалось отправить: клиент заблокировал бота или удалил чат."


def sending_to(channel: str) -> str:
    return f"Отправляю клиенту в {ch_name(channel)}…"


def media_other_channel(channel: str) -> str:
    return (f"Клиент пишет из {ch_name(channel)} — фото и файлы туда отсюда не переслать. "
            f"Напишите текстом или отправьте файл из {ch_name(channel)}.")


REPLY_USAGE = "Отправьте: /reply номер_заявки текст — например: /reply 12 Здравствуйте! (клиент: /reply К5 …)"
NO_SUCH_LEAD = "Заявки или клиента с таким номером нет."
LEADS_EMPTY = "Заявок пока нет."
LEAD_USAGE = "Отправьте: /lead номер — например /lead 12"
HISTORY_USAGE = "Отправьте: /history номер_заявки — например /history 12 (или номер клиента: /history К5)"
HISTORY_EMPTY = "Переписки с этим клиентом нет."
REPLY_HINT = "Ответьте на это сообщение — ответ уйдёт клиенту."


def client_tag(client_id: int, channel: str) -> str:
    return f"клиент К{client_id}, {ch_name(channel)}"


def who_line(name: str, username: str | None, client_id: int, channel: str, pii: bool = True) -> str:
    if not pii:
        tag = client_tag(client_id, channel)
        return tag[:1].upper() + tag[1:]
    text = esc(name) or "Без имени"
    if username:
        text += f" · @{esc(username)}"
    return f"{text} ({client_tag(client_id, channel)})"


def client_message_header(name: str, username: str | None, kind: str, client_id: int, channel: str,
                          pii: bool = True) -> str:
    what = "Сообщение от клиента" if kind == "text" else f"Сообщение от клиента ({esc(kind)})"
    return f"<b>{what}</b>\n{who_line(name, username, client_id, channel, pii)}"


def client_message_text(name: str, username: str | None, text: str, client_id: int, channel: str,
                        pii: bool = True) -> str:
    body = esc(text) if pii else f"<i>текст {HIDDEN}</i>"
    return client_message_header(name, username, "text", client_id, channel, pii) + "\n\n" + body


def tg_message_notice(client_id: int, kind: str) -> str:
    """Сообщение клиента из Telegram, пока контакты там не собираем: без имени, телефона и текста."""
    what = "сообщение" if kind == "text" else f"сообщение ({esc(kind)})"
    return (f"<b>Новое {what} в Telegram</b> — клиент К{client_id}.\n"
            f"Откройте переписку: /history К{client_id} (или кнопкой ниже).")


def media_unavailable(kind: str, channel: str) -> str:
    return f"<i>{esc(kind)} — посмотреть можно в {ch_name(channel)}</i>"


def lead_card(lead, title: str = "Новая заявка", pii: bool = True) -> str:  # lead: db.Lead
    lines = [f"<b>{title} №{lead.id}</b> · {esc(lead.created_dt.strftime('%d.%m.%Y %H:%M'))}",
             f"Откуда: {ch_name(lead.channel)}, клиент К{lead.client_id}"]
    if pii:
        lines.append(f"Имя: {esc(lead.name)}")
        lines.append(f"Контакт: {esc(lead.contact)}")
        if lead.username:
            lines.append(f"{ch_name(lead.channel)}: @{esc(lead.username)}")
        if lead.comment:
            lines.append(f"Комментарий: {esc(lead.comment)}")
    else:
        lines.append(f"Имя, контакт и комментарий: {HIDDEN}")
    if lead.calc:
        lines.append(f"Расчёт: {esc(lead.calc)}")
    lines.append(f"Статус: {status_name(lead.status)}")
    lines.append("")
    lines.append(REPLY_HINT)
    return "\n".join(lines)


def leads_list(leads: list, pii: bool = True) -> str:
    out = ["<b>Последние заявки</b> — нажмите номер, чтобы открыть"]
    for lead in leads:
        calc = lead.calc.split(" (")[0] if lead.calc else ""
        who = f"{esc(lead.name)} · {esc(lead.contact)}" if pii else f"клиент К{lead.client_id}"
        line = (f"\n<b>№{lead.id}</b> · {esc(lead.created_dt.strftime('%d.%m %H:%M'))} · {ch_name(lead.channel)} · "
                f"{who} · <i>{status_name(lead.status)}</i>")
        if calc:
            line += f"\n    расчёт: {esc(calc)}"
        if pii and lead.comment:
            comment = lead.comment if len(lead.comment) <= 100 else lead.comment[:97] + "…"
            line += f"\n    {esc(comment)}"
        out.append(line)
    return "\n".join(out)


def history(name: str, username: str, client_id: int, channel: str, leads: list, items: list,
            pii: bool = True) -> list[str]:
    from db import fmt_ts  # noqa: PLC0415 - чтобы texts не тянул базу при импорте

    head = f"<b>Переписка: {who_line(name, username, client_id, channel, pii)}</b>"
    if leads:
        head += "\nЗаявки: " + ", ".join(f"№{lead.id} ({status_name(lead.status)})" for lead in leads)
    lines = []
    for it in items:
        who = "Клиент" if it.direction == "in" else f"Магазин ({esc(it.admin_name)})" if it.admin_name else "Магазин"
        if not pii and it.direction == "in":
            body = f"<i>{HIDDEN}</i>"
        else:
            body = esc(it.text) if it.text else ""
            if it.kind != "text":
                body = f"[{esc(it.kind)}] {body}".strip()
        lines.append(f"<i>{fmt_ts(it.created_ts)}</i> <b>{who}:</b> {body}")
    if not lines:
        lines.append(HISTORY_EMPTY)
    parts, chunk = [], head + "\n"
    for line in lines:
        if len(chunk) + len(line) > 3500:
            parts.append(chunk)
            chunk = ""
        chunk += "\n" + line
    chunk += "\n\n" + REPLY_HINT
    parts.append(chunk)
    return parts


# --- отгрузка
def ship_ask_items(lead_id: int, default: str) -> str:
    text = f"<b>Отгрузка по заявке №{lead_id}</b>\nЧто отгрузить?"
    if default:
        text += (f"\n\nПо заявке: {esc(default)}\n\nНажмите «{BTN_AS_IN_LEAD}» или напишите, "
                 "что именно отгрузить (артикулы и количество).")
    else:
        text += " Напишите артикулы и количество."
    return text


SHIP_ASK_ADDRESS = f"Адрес доставки? Напишите адрес или нажмите «{BTN_PICKUP}»."
SHIP_ASK_WHEN = "Когда отгрузить? Например: «завтра после 14:00» или «05.11 в 10:00»."


def ship_ask_phone(default: str) -> str:
    if default:
        return f"Телефон получателя? По заявке: {esc(default)} — нажмите «{BTN_AS_IN_LEAD}» или напишите другой."
    return "Телефон получателя? Напишите номер, например +7 999 123-45-67."


SHIP_BAD_TEXT = "Напишите, пожалуйста, текстом."
SHIP_BAD_PHONE = "Не похоже на телефон. Напишите номер, например +7 999 123-45-67."
SHIP_LEAD_MISSING = "Заявка не найдена (возможно, клиент удалил свои данные)."
SHIP_EXPIRED = "Это оформление отгрузки устарело — нажмите «Передать на отгрузку» под заявкой ещё раз."
SHIP_ONLY_IN_MAX = ("Отгрузку с адресом и телефоном оформляйте в боте MAX: в Telegram адреса и телефоны "
                    "клиентов не передаём.")
SHIP_CHECK = "Проверьте отгрузку и нажмите кнопку под ней."
BUTTON_STALE = "Эта кнопка больше не действует."


def ship_review(lead_id: int, items: str, address: str, when: str, phone: str, replaces: str) -> str:
    text = (f"<b>Проверьте отгрузку по заявке №{lead_id}</b>\n"
            f"Что: {esc(items)}\nКуда: {esc(address)}\nКогда: {esc(when)}\nТелефон получателя: {esc(phone)}")
    if replaces:
        text += f"\n\nПо этой заявке уже есть отгрузка (статус: {status_name(replaces)}) — она будет заменена."
    return text


def shipment_card(ship, pii: bool = True) -> str:  # ship: db.Shipment
    from db import fmt_ts  # noqa: PLC0415

    lines = [
        f"<b>На отгрузку №{ship.lead_id}</b>",
        f"Что: {esc(ship.items)}",
        f"Куда: {esc(ship.address) if pii else HIDDEN}",
        f"Когда: {esc(ship.when_text)}",
        f"Телефон получателя: {esc(ship.phone) if pii else HIDDEN}",
        f"Клиент: {who_line(ship.client_name, ship.client_username, ship.client_id, ship.client_channel, pii)}",
        f"Передал(а): {esc(ship.created_name)} · {fmt_ts(ship.created_ts)}",
    ]
    if ship.cancelled_ts:
        lines.append(f"<b>Статус: отменена</b> · {fmt_ts(ship.cancelled_ts)}")
    else:
        status = f"<b>Статус: {status_name(ship.status)}</b>"
        if ship.shipped_ts:
            status += f" · {esc(ship.shipped_name)}, {fmt_ts(ship.shipped_ts)}"
        elif ship.accepted_ts:
            status += f" · принял(а) {esc(ship.accepted_name)}, {fmt_ts(ship.accepted_ts)}"
        lines.append(status)
    return "\n".join(lines)


def ship_created(lead_id: int, receivers: list[str]) -> str:
    if receivers:
        return f"Заявка №{lead_id} передана на отгрузку. Карточка отправлена: {esc(', '.join(receivers))}."
    return (f"Заявка №{lead_id} сохранена со статусом «подтверждена», но в команде пока нет никого "
            f"на отгрузке. Пригласите: «{BTN_T_TEAM}» → «{BTN_INVITE_SHIPPING}».")


def ship_status_note(lead_id: int, action: str, by_name: str, client_name: str) -> str:
    who = esc(by_name) or "сотрудник"
    client = f" ({esc(client_name)})" if client_name else ""
    if action == "created":
        return f"Отгрузка №{lead_id}{client}: передал(а) {who} — статус «подтверждена»."
    if action == "accept":
        return f"Отгрузка №{lead_id}{client}: принял(а) {who} — статус «на отгрузке»."
    if action == "done":
        return f"Отгрузка №{lead_id}{client}: отгружено ({who})."
    return f"Отгрузка №{lead_id}{client} отменена ({who})."


SHIP_TOAST = {
    "ok": "Готово",
    "already": "Уже отмечено",
    "shipped": "Уже отгружено",
    "cancelled": "Отгрузка отменена",
    "missing": "Отгрузка не найдена",
}
ORDERS_EMPTY = "Открытых отгрузок нет."


def orders_head(count: int) -> str:
    return f"<b>Открытые отгрузки: {count}</b>"


# --- статистика и каталог
def stats(s, catalog_count: int, catalog_source: str, catalog_time: str, catalog_error: str,
          queues: dict[str, int] | None = None) -> str:
    text = (
        "<b>Статистика</b>\n"
        f"Заявки: сегодня {s.leads_today}, за 7 дней {s.leads_week}, всего {s.leads_total}\n"
        f"Сообщения клиентов: сегодня {s.messages_today}, за 7 дней {s.messages_week}\n"
        f"Клиентов за 7 дней: {s.clients_week}\n"
        f"Отгрузки: открытых {s.shipments_open}, отгружено за 7 дней {s.shipped_week}\n"
        f"Каталог: {catalog_count} позиций (откуда: {esc(catalog_source)}, {esc(catalog_time)})"
    )
    waiting = {ch: n for ch, n in (queues or {}).items() if n}
    if waiting:
        text += "\nЖдут отправки: " + ", ".join(f"{ch_name(ch)} — {n}" for ch, n in waiting.items())
    if catalog_error:
        text += f"\nПоследний раз цены обновить не удалось: {esc(catalog_error[:300])}"
    return text


def reload_result(count: int, source: str, error: str) -> str:
    if error:
        return f"Цены не обновились: {esc(error[:300])}\nПока работает прежний каталог: {count} позиций."
    return f"Каталог и цены обновлены: {count} позиций (откуда: {esc(source)})."


def client_deleted(name: str, client_id: int, channel: str, leads: int, kept: int, messages: int,
                   pii: bool = True) -> str:
    who = f"{esc(name) or 'Клиент'} ({client_tag(client_id, channel)})" if pii else client_tag(client_id, channel)
    text = f"{who[:1].upper() + who[1:]} попросил(а) удалить свои данные: удалено заявок {leads}, сообщений {messages}."
    if kept:
        text += f" Заказы на отгрузке и отгруженные ({kept}) остались — их храним по закону."
    return text + " Удалите этого клиента и из своих заметок, если он там есть."
