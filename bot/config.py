"""Настройки бота «Наш декор».

Все значения берутся из переменных окружения. На сервере их задаёт systemd
из файла /etc/prostranstvo/bot.env (его создаёт install-bot.sh, chmod 600).
В коде и в репозитории секретов нет и быть не должно — репозиторий открытый.

Один и тот же код работает в двух мессенджерах: Telegram (BOT_TOKEN) и MAX
(MAX_TOKEN). Каждый мессенджер — отдельная служба systemd со своим процессом.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

APP_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CATALOG_FILE = "/var/www/prostranstvo/index.html"
DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/mebel/0f7s1eez/index.html"
)
DEFAULT_DB_PATH = "/var/lib/prostranstvo/bot.db"
DEFAULT_CATALOG_CACHE = "/var/lib/prostranstvo/bot-catalog.json"
DEFAULT_MAX_API_URL = "https://platform-api2.max.ru"
DEFAULT_MAX_CA_FILE = os.path.join(APP_DIR, "certs", "russian_trusted_ca.pem")

CH_TG = "tg"
CH_MAX = "max"
CHANNELS = (CH_TG, CH_MAX)


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


def _parse_ids(name: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in _env(name).replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ConfigError(f"{name}: укажите числовые id через запятую")
        ids.add(int(part))
    return frozenset(ids)


def _url(value: str) -> str:
    value = value.strip().rstrip("/")
    if value and not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value


@dataclass(frozen=True)
class Config:
    bot_token: str = field(default="", repr=False)      # Telegram
    max_token: str = field(default="", repr=False)      # MAX
    site_url: str = ""
    owner_code: str = field(default="", repr=False)
    consent_version: str = "1"
    admin_ids: frozenset[int] = frozenset()             # постоянные менеджеры (Telegram id)
    max_admin_ids: frozenset[int] = frozenset()         # постоянные менеджеры (MAX id)
    operator_name: str = ""
    db_path: str = DEFAULT_DB_PATH
    catalog_file: str = DEFAULT_CATALOG_FILE
    catalog_url: str = DEFAULT_CATALOG_URL
    catalog_cache: str = DEFAULT_CATALOG_CACHE
    catalog_refresh_min: int = 60
    reserve_percent: int = 7
    log_level: str = "INFO"
    # Telegram: собирать ли контакты клиентов (заявки). 0 — нет: пока не подано уведомление
    # в Роскомнадзор о трансграничной передаче, заявки принимает сайт и бот в MAX.
    telegram_collect_contacts: bool = False
    staff_default_channel: str = CH_MAX                 # куда слать сотруднику, если он в обоих
    max_bot_url: str = ""                               # https://max.ru/<ник бота>
    max_api_url: str = DEFAULT_MAX_API_URL
    max_ca_file: str = DEFAULT_MAX_CA_FILE
    # Заготовка (выключена): подсказки ответов через YandexGPT.
    yandexgpt_enabled: bool = False
    yandexgpt_api_key: str = field(default="", repr=False)
    yandexgpt_folder_id: str = ""

    @property
    def channels(self) -> tuple[str, ...]:
        """Мессенджеры, для которых задан токен (их службы работают)."""
        out = []
        if self.bot_token:
            out.append(CH_TG)
        if self.max_token:
            out.append(CH_MAX)
        return tuple(out)

    def token(self, channel: str) -> str:
        return self.bot_token if channel == CH_TG else self.max_token

    def site_link(self, page: str = "") -> str:
        """Адрес страницы сайта или пустая строка, если SITE_URL не задан."""
        if not self.site_url:
            return ""
        return f"{self.site_url}/{page.lstrip('/')}" if page else f"{self.site_url}/"


def load_config(channel: str | None = None) -> Config:
    """channel — для какого мессенджера запускаемся: его токен обязателен."""
    cfg = Config(
        bot_token=_env("BOT_TOKEN"),
        max_token=_env("MAX_TOKEN"),
        site_url=_url(_env("SITE_URL")),
        owner_code=_env("OWNER_CODE"),
        consent_version=_env("CONSENT_VERSION", "1") or "1",
        admin_ids=_parse_ids("ADMIN_IDS"),
        max_admin_ids=_parse_ids("MAX_ADMIN_IDS"),
        operator_name=_env("OPERATOR_NAME"),
        db_path=_env("DB_PATH", DEFAULT_DB_PATH) or DEFAULT_DB_PATH,
        catalog_file=_env("CATALOG_FILE", DEFAULT_CATALOG_FILE),
        catalog_url=_env("CATALOG_URL", DEFAULT_CATALOG_URL),
        catalog_cache=_env("CATALOG_CACHE", DEFAULT_CATALOG_CACHE),
        catalog_refresh_min=_env_int("CATALOG_REFRESH_MIN", 60, 5, 24 * 60),
        reserve_percent=_env_int("RESERVE_PERCENT", 7, 0, 30),
        log_level=(_env("LOG_LEVEL", "INFO") or "INFO").upper(),
        telegram_collect_contacts=_env_bool("TELEGRAM_COLLECT_CONTACTS", False),
        staff_default_channel=_env("STAFF_DEFAULT_CHANNEL", CH_MAX) or CH_MAX,
        max_bot_url=_url(_env("MAX_BOT_URL")),
        max_api_url=_url(_env("MAX_API_URL", DEFAULT_MAX_API_URL)) or DEFAULT_MAX_API_URL,
        max_ca_file=_env("MAX_CA_FILE", DEFAULT_MAX_CA_FILE) or DEFAULT_MAX_CA_FILE,
        yandexgpt_enabled=_env_bool("YANDEXGPT_ENABLED"),
        yandexgpt_api_key=_env("YANDEXGPT_API_KEY"),
        yandexgpt_folder_id=_env("YANDEXGPT_FOLDER_ID"),
    )
    if cfg.owner_code and not (cfg.owner_code.isdigit() and 4 <= len(cfg.owner_code) <= 12):
        raise ConfigError("OWNER_CODE должен состоять из 4–12 цифр")
    if cfg.staff_default_channel not in CHANNELS:
        raise ConfigError("STAFF_DEFAULT_CHANNEL: tg или max")
    if channel == CH_TG and not cfg.bot_token:
        raise ConfigError("нет BOT_TOKEN (токен Telegram задаётся в /etc/prostranstvo/bot.env)")
    if channel == CH_MAX and not cfg.max_token:
        raise ConfigError("нет MAX_TOKEN (токен MAX задаётся в /etc/prostranstvo/bot.env)")
    return cfg
