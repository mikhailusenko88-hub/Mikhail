"""ЗАГОТОВКА (выключена): черновики ответов на вопросы клиентов через YandexGPT.

Сейчас ничего не делает. Как включить потом:
  1. В Yandex Cloud создать сервисный аккаунт с ролью ai.languageModels.user и API-ключ.
  2. В /etc/prostranstvo/bot.env (НЕ в GitHub!) прописать:
         YANDEXGPT_ENABLED=1
         YANDEXGPT_API_KEY=...
         YANDEXGPT_FOLDER_ID=...
  3. Дописать запрос в suggest_reply() (API: foundationModels/v1/completion)
     и перезапустить: systemctl restart prostranstvo-bot

Задумано так: черновик получает ТОЛЬКО администратор (как подсказку под сообщением
клиента), клиенту автоматически ничего не уходит — отвечает менеджер.
"""

from __future__ import annotations

import logging

from config import Config

log = logging.getLogger("prostranstvo.yagpt")


def is_enabled(cfg: Config) -> bool:
    return bool(cfg.yandexgpt_enabled and cfg.yandexgpt_api_key and cfg.yandexgpt_folder_id)


async def suggest_reply(cfg: Config, question: str) -> str | None:
    """Черновик ответа менеджеру на вопрос клиента или None.

    Заглушка: всегда None. Ключи берутся только из bot.env на сервере.
    """
    if not cfg.yandexgpt_enabled:
        return None
    if not is_enabled(cfg):
        log.warning("YANDEXGPT_ENABLED=1, но не заданы YANDEXGPT_API_KEY / YANDEXGPT_FOLDER_ID")
        return None
    # Здесь будет запрос к YandexGPT. Текст вопроса в журнал не писать.
    return None
