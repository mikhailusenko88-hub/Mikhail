# Страница CRM «Сервер» — 2026-11-11 17:58 UTC

```
cron: 1 строк
файл отчёта: root 644 3785 байт
/server: 200
строк «Обновлено» на странице: 2
кнопка Обновить: 302
просьба на диске: /var/lib/prostranstvo/server-request
после cron просьба: ls: cannot access '/var/lib/prostranstvo/server-request': No

--- отчёт (начало) ---
Обновлено: 11.11.2026 20:58

=== Сервер «Наш декор», 11.11.2026 20:58 ===
Сайт:   http://nashdekor.ru/  (HTTPS пока нет — команда: prostranstvo-cert)
IP:     40.124.216.243
nginx:  active
Обновление из GitHub: работает (последняя проверка 0 мин назад)
Версия сайта: 831fb9c от 11.11.2026 20:56 — Фиды Авито и Яндекс Товаров: цены и наличие из CRM (2026-11-11 17:56 UTC)
Firewall ufw:  active
fail2ban SSH:  active, сейчас заблокировано адресов: 0
Автообновления: enabled
Диск:   86G свободно из 145G

=== Почта ===
Почта nashdekor.ru — проверка (11.11.2026 20:58)
 Службы:
   [да]  postfix работает
   [да]  dovecot работает
   [да]  rspamd работает
   [да]  redis-server работает
 Порты (снаружи открыты в firewall):
   [да]  порт 25 слушается
   [да]  порт 465 слушается
   [да]  порт 587 слушается
   [да]  порт 993 слушается
 Ящики: info@nashdekor.ru zakaz@nashdekor.ru yulia@nashdekor.ru mikhail@nashdekor.ru
   [НЕТ] сертификат mail.nashdekor.ru (Let's Encrypt) — пока временный; сервер получит сам, когда домен заработает
 DNS (как видит интернет):
   [НЕТ] A mail.nashdekor.ru → 40.124.216.243 — сейчас: 185.60.134.150
   [да]  MX nashdekor.ru → mail.nashdekor.ru
   [НЕТ] SPF (TXT v=spf1 … 40.124.216.243) — сейчас: v=spf1 ip4:185.60.134.150 mx ~all
   [НЕТ] DKIM (mail._domainkey) — не совпадает с ключом сервераv=DKIM1;k=rsa;p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuC+8OpsxmU1z9Y+RCCdRjWVGxyPL+Auk6tZX4O8hTQ9Iq4iXnfwBsGKQkWlOU8ebXCUHwN2OuvGWzyELIIrF9iu95JK/TX6jFEK+Hrs3qVpJwvEboMEWcBulsFmn3rWelAyEq2teZOQYdD+iPYhh77kLZDaZqZAyVcRq/n53Al/1abYMsqA+thc3iRT0UcqLc4XdR8fLg4NfjFqB4bnQ500ncSR0O10IAvze3Wzmz2uPjXPJPMf/Xfl+bI2zfZIk/HInMhMRZlWu+kuboOvbRYH3+0DyBZjcWmk4fOCKISM1P0nPdVbOvLYuwDcYHJmK2WTl9C0mnvgxdzmJx6gDqwIDAQAB
   [да]  DMARC
   [НЕТ] PTR 40.124.216.243 → mail.nashdekor.ru — сейчас: нет (меняется в кабинете FirstVDS)
 Отправка наружу (порт 25 у хостинга):
   [да]  соединение с почтовыми серверами (mxs.mail.ru:25)
   очередь писем пуста

=== CRM ===
CRM nashdekor.ru — проверка (11.11.2026 20:58)
   [да]  служба prostranstvo-crm работает
   [да]  приложение отвечает
   [да]  https://crm.nashdekor.ru/login через nginx
   [НЕТ] сертификат — пока временный (сервер получит сам, когда домен заработает)
   заявки с сайта: включены
   клиентов: 4, заявок: 4, пользователей: 2
   последняя копия: /var/backups/prostranstvo/2026-11-11

=== Нагрузка ===
 20:58:51 up 5 min,  0 user,  load average: 0.45, 0.51, 0.26
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.2Gi        12Gi        52Mi       1.8Gi        14Gi
Swap:          3.0Gi          0B       3.0Gi
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       145G   60G   86G  41% /

=== Блокировки входа в CRM (fail2ban) ===
   |- Currently banned:	1
   `- Banned IP list:	203.0.113.5
Свои адреса (не блокируются): 127.0.0.1/8 ::1 198.51.100.7
```
