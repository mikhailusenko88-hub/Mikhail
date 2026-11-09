# Сервер магазина «Наш декор» (FirstVDS, Ubuntu 24.04)

Ветка `server`: установщики сервера, CRM и бот. Сайт лежит в ветке `mebel` (папка `0f7s1eez`),
проверки из облака — в ветке `domain-check`. Репозиторий открытый: паролей, токенов, реквизитов
и данных клиентов здесь нет и быть не должно.

| Что | Где | Установка / обновление (от root) |
|---|---|---|
| Сайт https://ДОМЕН | `setup-prostranstvo.sh` | `curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/setup-prostranstvo.sh \| bash -s -- ДОМЕН EMAIL` |
| Почта (Postfix, Dovecot, Rspamd, Roundcube) | `setup-pochta.sh` | `… /setup-pochta.sh \| bash` |
| CRM https://crm.ДОМЕН | `setup-crm.sh`, папка `crm/` | `prostranstvo-crm update` или кнопка в CRM «Ещё → Сервер → Обновить CRM» |
| Бот MAX / Telegram | папка `bot/` | `… /bot/install-bot.sh \| bash -s -- --tg 'ТОКЕН' --max 'ТОКЕН'` |

## Сайт

- nginx отдаёт сайт из `/var/www/prostranstvo`; раз в минуту cron забирает ветку `mebel`
  (`prostranstvo-sync`, журнал `/var/log/prostranstvo-sync.log`). Старые ссылки `/mebel/0f7s1eez/…`
  (фото и фид Авито `avito.xml`) работают.
- HTTPS — Let's Encrypt, продление само. Защита: ufw (22, 80, 443 и порты почты), fail2ban,
  автообновления безопасности (перезагрузка при необходимости — в 04:30 МСК).
- Проверка: `prostranstvo-status`.

## CRM (`crm/`, Flask + gunicorn, SQLite)

- Вкладки: «Сегодня», «Воронка», «Клиенты», «Склад», **«Сайт»** (посещаемость), «Ещё» →
  «Задачи», «Отчёты», «Настройки», **«Сервер»**.
- Заявки с формы сайта — `POST /api/lead` (включаются `prostranstvo-crm site-leads on`),
  письмо на `NOTIFY_EMAIL` и сообщение сотрудникам через бота.
- **Счётчик посещений** — `POST /api/hit` (сайт шлёт `navigator.sendBeacon`): страницы, разделы,
  нажатия на артикулы, расчёт стены, 3D, заявка, источник (только домен) и тип устройства.
  Без cookie; IP и браузер в базу не пишутся — только обезличенный номер посетителя на сутки
  (ключ меняется каждые сутки), хранение 400 дней. Боты, «Не отслеживать» и вошедшие в CRM
  не считаются. Код — `crm/visits.py`, страница — `/site`.
- **Страница «Сервер»** (только владельцы): отчёт о сайте, почте, CRM, нагрузке и входах +
  кнопки: обновить CRM, обновить сайт, копия баз, перезапуск CRM / почты / nginx, снять
  блокировки fail2ban, заявки вкл/выкл, перезагрузка (с подтверждением). CRM только оставляет
  просьбу в `/var/lib/prostranstvo/server-request`; root по cron раз в минуту
  (`prostranstvo-crm server-page`) выполняет **только действия из списка** (`server_action`
  в `setup-crm.sh`) и пишет результат в `server-action.txt`. Произвольных команд из CRM нет.
- Ночные копии баз — `/var/backups/prostranstvo` (03:15, 14 дней).
- Команды: `prostranstvo-crm` (проверка), `help` — список, `passwords` — пароли входа
  (не фотографировать), `update`, `backup`, `site-leads on|off`.

## Разработка и проверка

- Тесты CRM: `cd crm && python3 -m unittest -q test_crm` (их же запускает установщик,
  в чистом окружении — на настоящую почту не пишут).
- Проверка установки на чистой Ubuntu 24.04 — ветка `domain-check`, workflow `crm-test`
  (результаты в `status/crm-*.md`); проверка живого сайта снаружи — workflow `site-check`
  (`status/site.md`).
