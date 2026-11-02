"""Настройки бота «Пространство».

Все значения берутся из переменных окружения. На сервере их задаёт systemd
из файла /etc/prostranstvo/bot.env (его создаёт install-bot.sh, chmod 600).
В коде и в репозитории секретов нет и быть не должно — репозиторий открытый.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_CATALOG_FILE = "/var/www/prostranstvo/index.html"
DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/mebel/0f7s1eez/index.html"
)
DEFAULT_DB_PATH = "/var/lib/prostranstvo/bot.db"
DEFAULT_CATALOG_CACHE = "/var/lib/prostranstvo/bot-catalog.json"


class ConfigError(Exception):
    """Ошибка в настройках (например, нет токена)."""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "yes", "true", "on", "да"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = _env(name)
    if not value:
        return default
    try:
        number = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} должно быть целым числом") from exc
    return max(minimum, min(maximum, number))


def _parse_ids(value: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in value.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lstrip("-").isdigit():
            raise ConfigError("ADMIN_IDS: укажите числовые Telegram id через запятую")
        ids.add(int(part))
    return frozenset(ids)


@dataclass(frozen=True)
class Config:
    bot_token: str = field(repr=False)
    site_url: str = ""
    owner_code: str = field(default="", repr=False)
    consent_version: str = "1"
    admin_ids: frozenset[int] = frozenset()
    operator_name: str = ""
    db_path: str = DEFAULT_DB_PATH
    catalog_file: str = DEFAULT_CATALOG_FILE
    catalog_url: str = DEFAULT_CATALOG_URL
    catalog_cache: str = DEFAULT_CATALOG_CACHE
    catalog_refresh_min: int = 60
    reserve_percent: int = 7
    log_level: str = "INFO"
    # Заготовка (выключена): подсказки ответов через YandexGPT.
    yandexgpt_enabled: bool = False
    yandexgpt_api_key: str = field(default="", repr=False)
    yandexgpt_folder_id: str = ""

    def site_link(self, page: str = "") -> str:
        """Адрес страницы сайта или пустая строка, если SITE_URL не задан."""
        if not self.site_url:
            return ""
        return f"{self.site_url}/{page.lstrip('/')}" if page else f"{self.site_url}/"


def load_config(require_token: bool = True) -> Config:
    token = _env("BOT_TOKEN")
    if require_token and not token:
        raise ConfigError("нет BOT_TOKEN (он задаётся в /etc/prostranstvo/bot.env)")

    site_url = _env("SITE_URL").rstrip("/")
    if site_url and not site_url.startswith(("http://", "https://")):
        site_url = "https://" + site_url

    owner_code = _env("OWNER_CODE")
    if owner_code and not (owner_code.isdigit() and 4 <= len(owner_code) <= 12):
        raise ConfigError("OWNER_CODE должен состоять из 4–12 цифр")

    return Config(
        bot_token=token,
        site_url=site_url,
        owner_code=owner_code,
        consent_version=_env("CONSENT_VERSION", "1") or "1",
        admin_ids=_parse_ids(_env("ADMIN_IDS")),
        operator_name=_env("OPERATOR_NAME"),
        db_path=_env("DB_PATH", DEFAULT_DB_PATH) or DEFAULT_DB_PATH,
        catalog_file=_env("CATALOG_FILE", DEFAULT_CATALOG_FILE),
        catalog_url=_env("CATALOG_URL", DEFAULT_CATALOG_URL),
        catalog_cache=_env("CATALOG_CACHE", DEFAULT_CATALOG_CACHE),
        catalog_refresh_min=_env_int("CATALOG_REFRESH_MIN", 60, 5, 24 * 60),
        reserve_percent=_env_int("RESERVE_PERCENT", 7, 0, 30),
        log_level=(_env("LOG_LEVEL", "INFO") or "INFO").upper(),
        yandexgpt_enabled=_env_bool("YANDEXGPT_ENABLED"),
        yandexgpt_api_key=_env("YANDEXGPT_API_KEY"),
        yandexgpt_folder_id=_env("YANDEXGPT_FOLDER_ID"),
    )
