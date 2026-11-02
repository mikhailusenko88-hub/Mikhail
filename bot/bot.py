"""Запуск бота магазина «Пространство» (Санкт-Петербург, декор ARTDEC).

    python bot.py                 — Telegram (служба prostranstvo-bot)
    python bot.py --channel max   — MAX      (служба prostranstvo-max)

Каждый мессенджер — отдельный процесс и отдельная служба systemd: если один
мессенджер недоступен или его служба упала, второй работает дальше. Общие у них
база (/var/lib/prostranstvo/bot.db), каталог и настройки (/etc/prostranstvo/bot.env).

Логика — в core.py, Telegram — tg.py, MAX — max_api.py.
Для проверки на своём компьютере:
    BOT_TOKEN=... DB_PATH=./bot.db CATALOG_FILE=путь/к/index.html python bot.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from catalog import CatalogStore
from config import CH_MAX, CH_TG, ConfigError, load_config
from db import Database, SchemaError

log = logging.getLogger("prostranstvo.bot")


async def run(channel: str) -> int:
    fmt = f"%(levelname)s [{channel}] %(name)s: %(message)s"
    try:
        cfg = load_config(channel)
    except ConfigError as exc:
        logging.basicConfig(level="INFO", format=fmt, stream=sys.stdout)
        log.error("ошибка настроек: %s", exc)
        await asyncio.sleep(30)  # не перезапускаться слишком часто
        return 2
    level = logging.getLevelName(cfg.log_level)
    logging.basicConfig(level=level if isinstance(level, int) else logging.INFO, format=fmt, stream=sys.stdout)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)  # без строки на каждое сообщение

    db = Database(cfg.db_path)
    try:
        await db.init()
    except SchemaError as exc:
        log.error("%s — обновите бота: curl … install-bot.sh | bash", exc)
        await asyncio.sleep(60)
        return 5
    store = CatalogStore(cfg.catalog_file, cfg.catalog_url, cfg.catalog_cache, cfg.catalog_refresh_min)
    if not await store.reload():
        log.error("каталог пока не загружен — расчёт и цены заработают после обновления")
    try:
        if channel == CH_MAX:
            import max_api

            return await max_api.run(cfg, db, store)
        import tg

        return await tg.run(cfg, db, store)
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Бот магазина «Пространство»")
    parser.add_argument("--channel", choices=(CH_TG, CH_MAX), default=CH_TG,
                        help="мессенджер: tg (Telegram, по умолчанию) или max")
    args = parser.parse_args(argv)
    return asyncio.run(run(args.channel))


if __name__ == "__main__":
    sys.exit(main())
