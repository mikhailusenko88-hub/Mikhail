# Страница CRM «Сервер» — 2026-11-17 21:52 UTC

```
cron: 1 строк
файл отчёта: root 644 3860 байт
/server: 200
строк «Обновлено» на странице: 2
кнопка Обновить: 302
просьба на диске: /var/lib/prostranstvo/server-request
после cron просьба: ls: cannot access '/var/lib/prostranstvo/server-request': No

--- отчёт (начало) ---
Обновлено: 18.11.2026 00:52

=== Сервер «Наш декор», 18.11.2026 00:52 ===
Сайт:   http://nashdekor.ru/  (HTTPS пока нет — команда: prostranstvo-cert)
IP:     52.165.86.214
nginx:  active
Обновление из GitHub: работает (последняя проверка 0 мин назад)
Версия сайта: 1c7fb2a от 18.11.2026 00:47 — Главная, карусель «в интерьере»: счётчик — какие кадры листали, во весь экран, приближали (сцена.панель)
Firewall ufw:  active
fail2ban SSH:  active, сейчас заблокировано адресов: 0
Автообновления: enabled
Диск:   85G свободно из 145G

=== Почта ===
Почта nashdekor.ru — проверка (18.11.2026 00:52)
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
   [НЕТ] A mail.nashdekor.ru → 52.165.86.214 — сейчас: 185.60.134.150
   [да]  MX nashdekor.ru → mail.nashdekor.ru
   [НЕТ] SPF (TXT v=spf1 … 52.165.86.214) — сейчас: v=spf1 ip4:185.60.134.150 mx ~all
   [НЕТ] DKIM (mail._domainkey) — не совпадает с ключом сервераv=DKIM1;k=rsa;p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuC+8OpsxmU1z9Y+RCCdRjWVGxyPL+Auk6tZX4O8hTQ9Iq4iXnfwBsGKQkWlOU8ebXCUHwN2OuvGWzyELIIrF9iu95JK/TX6jFEK+Hrs3qVpJwvEboMEWcBulsFmn3rWelAyEq2teZOQYdD+iPYhh77kLZDaZqZAyVcRq/n53Al/1abYMsqA+thc3iRT0UcqLc4XdR8fLg4NfjFqB4bnQ500ncSR0O10IAvze3Wzmz2uPjXPJPMf/Xfl+bI2zfZIk/HInMhMRZlWu+kuboOvbRYH3+0DyBZjcWmk4fOCKISM1P0nPdVbOvLYuwDcYHJmK2WTl9C0mnvgxdzmJx6gDqwIDAQAB
   [да]  DMARC
   [НЕТ] PTR 52.165.86.214 → mail.nashdekor.ru — сейчас: нет (меняется в кабинете FirstVDS)
 Отправка наружу (порт 25 у хостинга):
   [да]  соединение с почтовыми серверами (mxs.mail.ru:25)
   очередь писем пуста

=== CRM ===
CRM nashdekor.ru — проверка (18.11.2026 00:52)
   [да]  служба prostranstvo-crm работает
   [да]  приложение отвечает
   [да]  https://crm.nashdekor.ru/login через nginx
   [НЕТ] сертификат — пока временный (сервер получит сам, когда домен заработает)
   заявки с сайта: включены
   клиентов: 4, заявок: 4, пользователей: 2
   последняя копия: /var/backups/prostranstvo/2026-11-18

=== Нагрузка ===
 00:52:48 up 5 min,  0 user,  load average: 0.37, 0.55, 0.28
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.2Gi        12Gi        51Mi       2.4Gi        14Gi
Swap:          3.0Gi          0B       3.0Gi
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       145G   61G   85G  42% /

=== Блокировки входа в CRM (fail2ban) ===
   |- Currently banned:	1
   `- Banned IP list:	203.0.113.5
Свои адреса (не блокируются): 127.0.0.1/8 ::1 198.51.100.7
```
