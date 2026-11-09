# Страница CRM «Сервер» — 2026-11-09 17:40 UTC

```
cron: 1 строк
файл отчёта: root 644 3801 байт
/server: 200
строк «Обновлено» на странице: 2
кнопка Обновить: 302
просьба на диске: /var/lib/prostranstvo/server-request
после cron просьба: ls: cannot access '/var/lib/prostranstvo/server-request': No

--- отчёт (начало) ---
Обновлено: 09.11.2026 20:40

=== Сервер «Наш декор», 09.11.2026 20:40 ===
Сайт:   http://nashdekor.ru/  (HTTPS пока нет — команда: prostranstvo-cert)
IP:     20.29.55.1
nginx:  active
Обновление из GitHub: работает (последняя проверка 0 мин назад)
Версия сайта: 2a69a3d от 09.11.2026 20:37 — Сайт: телефон убран с сайта и из оферты; вместо него «Заказать обратный звонок» (главная — кнопка в контактах, страница товара — режим «Звонок» в форме) → CRM как «ПЕРЕЗВОНИТЬ»
Firewall ufw:  active
fail2ban SSH:  active, сейчас заблокировано адресов: 0
Автообновления: enabled
Диск:   86G свободно из 145G

=== Почта ===
Почта nashdekor.ru — проверка (09.11.2026 20:40)
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
   [НЕТ] A mail.nashdekor.ru → 20.29.55.1 — сейчас: 185.60.134.150
   [да]  MX nashdekor.ru → mail.nashdekor.ru
   [НЕТ] SPF (TXT v=spf1 … 20.29.55.1) — сейчас: v=spf1 ip4:185.60.134.150 mx ~all
   [НЕТ] DKIM (mail._domainkey) — не совпадает с ключом сервераv=DKIM1;k=rsa;p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuC+8OpsxmU1z9Y+RCCdRjWVGxyPL+Auk6tZX4O8hTQ9Iq4iXnfwBsGKQkWlOU8ebXCUHwN2OuvGWzyELIIrF9iu95JK/TX6jFEK+Hrs3qVpJwvEboMEWcBulsFmn3rWelAyEq2teZOQYdD+iPYhh77kLZDaZqZAyVcRq/n53Al/1abYMsqA+thc3iRT0UcqLc4XdR8fLg4NfjFqB4bnQ500ncSR0O10IAvze3Wzmz2uPjXPJPMf/Xfl+bI2zfZIk/HInMhMRZlWu+kuboOvbRYH3+0DyBZjcWmk4fOCKISM1P0nPdVbOvLYuwDcYHJmK2WTl9C0mnvgxdzmJx6gDqwIDAQAB
   [да]  DMARC
   [НЕТ] PTR 20.29.55.1 → mail.nashdekor.ru — сейчас: нет (меняется в кабинете FirstVDS)
 Отправка наружу (порт 25 у хостинга):
   [да]  соединение с почтовыми серверами (mxs.mail.ru:25)
   очередь писем пуста

=== CRM ===
CRM nashdekor.ru — проверка (09.11.2026 20:40)
   [да]  служба prostranstvo-crm работает
   [да]  приложение отвечает
   [да]  https://crm.nashdekor.ru/login через nginx
   [НЕТ] сертификат — пока временный (сервер получит сам, когда домен заработает)
   заявки с сайта: включены
   клиентов: 3, заявок: 3, пользователей: 2
   последняя копия: /var/backups/prostranstvo/2026-11-09

=== Нагрузка ===
 20:40:35 up 3 min,  0 user,  load average: 0.37, 0.30, 0.13
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.1Gi        13Gi        50Mi       1.7Gi        14Gi
Swap:          3.0Gi          0B       3.0Gi
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       145G   59G   86G  41% /

=== Вход на сервер по SSH ===
   |- Currently banned:	0
   `- Banned IP list:	
```
