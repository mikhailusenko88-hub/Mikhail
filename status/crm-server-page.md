# Страница CRM «Сервер» — 2026-11-16 18:40 UTC

```
cron: 1 строк
файл отчёта: root 644 4165 байт
/server: 200
строк «Обновлено» на странице: 2
кнопка Обновить: 302
просьба на диске: /var/lib/prostranstvo/server-request
после cron просьба: ls: cannot access '/var/lib/prostranstvo/server-request': No

--- отчёт (начало) ---
Обновлено: 16.11.2026 21:40

=== Сервер «Наш декор», 16.11.2026 21:40 ===
Сайт:   http://nashdekor.ru/  (HTTPS пока нет — команда: prostranstvo-cert)
IP:     3.42.157.55
nginx:  active
Обновление из GitHub: работает (последняя проверка 0 мин назад)
Версия сайта: ff2dce8 от 16.11.2026 20:53 — Сайт: по легенде коробок образцов — живые фото переставлены на A701 (были на AP1-100) и A25 (были на A605), у AP1-100 и A605 — 3D-отрезки; A608 — 40×20 мм (было 44×22)
Firewall ufw:  active
fail2ban SSH:  active, сейчас заблокировано адресов: 0
Автообновления: enabled
Нужна перезагрузка: сделается сама в 04:30 (или сейчас: reboot)
Диск:   87G свободно из 145G

=== Почта ===
Почта nashdekor.ru — проверка (16.11.2026 21:40)
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
   [НЕТ] A mail.nashdekor.ru → 3.42.157.55 — сейчас: 185.60.134.150
   [да]  MX nashdekor.ru → mail.nashdekor.ru
   [НЕТ] SPF (TXT v=spf1 … 3.42.157.55) — сейчас: v=spf1 ip4:185.60.134.150 mx ~all
   [НЕТ] DKIM (mail._domainkey) — не совпадает с ключом сервераv=DKIM1;k=rsa;p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuC+8OpsxmU1z9Y+RCCdRjWVGxyPL+Auk6tZX4O8hTQ9Iq4iXnfwBsGKQkWlOU8ebXCUHwN2OuvGWzyELIIrF9iu95JK/TX6jFEK+Hrs3qVpJwvEboMEWcBulsFmn3rWelAyEq2teZOQYdD+iPYhh77kLZDaZqZAyVcRq/n53Al/1abYMsqA+thc3iRT0UcqLc4XdR8fLg4NfjFqB4bnQ500ncSR0O10IAvze3Wzmz2uPjXPJPMf/Xfl+bI2zfZIk/HInMhMRZlWu+kuboOvbRYH3+0DyBZjcWmk4fOCKISM1P0nPdVbOvLYuwDcYHJmK2WTl9C0mnvgxdzmJx6gDqwIDAQAB
   [да]  DMARC
   [НЕТ] PTR 3.42.157.55 → mail.nashdekor.ru — сейчас: ec2-3-42-157-55.us-west-2.compute.amazonaws.com (меняется в кабинете FirstVDS)
 Отправка наружу (порт 25 у хостинга):
   [НЕТ] соединение с почтовыми серверами по порту 25 — хостинг блокирует? написать в поддержку FirstVDS
   очередь писем пуста

=== CRM ===
CRM nashdekor.ru — проверка (16.11.2026 21:41)
   [да]  служба prostranstvo-crm работает
   [да]  приложение отвечает
   [да]  https://crm.nashdekor.ru/login через nginx
   [НЕТ] сертификат — пока временный (сервер получит сам, когда домен заработает)
   заявки с сайта: включены
   клиентов: 4, заявок: 4, пользователей: 2
   последняя копия: /var/backups/prostranstvo/2026-11-16

=== Нагрузка ===
 21:41:09 up 14 min,  0 user,  load average: 0.15, 0.30, 0.28
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.2Gi        10Gi        50Mi       4.0Gi        14Gi
Swap:          3.0Gi          0B       3.0Gi
Filesystem            Size  Used Avail Use% Mounted on
/dev/mapper/cow-root  145G   58G   87G  40% /

=== Блокировки входа в CRM (fail2ban) ===
   |- Currently banned:	1
   `- Banned IP list:	203.0.113.5
```
